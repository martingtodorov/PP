"""Iteration 57: privacy/sanitization regressions with disposable DB + temp filesystem only."""

import copy
import importlib
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from pymongo import MongoClient
from pymongo.errors import ConfigurationError
from pymongo.uri_parser import parse_uri

from conftest import run
from scripts import check_repository_privacy
from scripts import preserve_runtime_data
from scripts import purge_preview_data


# -------- shared disposable/local guards --------
@pytest.fixture(scope="module")
def loopback_mongo_url():
    uri = os.environ["MONGO_URL"]
    parsed = parse_uri(uri)
    if not uri.startswith("mongodb://"):
        pytest.skip("Isolation tests require standalone mongodb:// URI")
    hosts = [host for host, _ in parsed.get("nodelist", [])]
    if not hosts or any(h not in ("localhost", "127.0.0.1", "::1") for h in hosts):
        pytest.skip("Isolation tests refuse non-loopback Mongo targets")
    if len(hosts) != 1:
        pytest.skip("Isolation tests require single-host standalone Mongo")
    return uri


@pytest.fixture()
def disposable_db(loopback_mongo_url):
    client = MongoClient(loopback_mongo_url, serverSelectionTimeoutMS=3000)
    db_name = f"{os.environ['DB_NAME']}_iter57_{uuid.uuid4().hex[:8]}"
    db = client[db_name]
    yield db
    client.drop_database(db_name)
    client.close()


def _base_env(tmp_backend: Path, mongo_url: str, db_name: str):
    media_root = tmp_backend / ".media"
    image_cache = tmp_backend / ".image_cache"
    data_dir = tmp_backend / "data"
    media_root.mkdir(parents=True, exist_ok=True)
    image_cache.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    return {
        "APP_ENV": "privacy-preview",
        "PREVIEW_ONLY": "true",
        "ALLOW_MANAGED_STORAGE": "false",
        "DB_NAME": db_name,
        "MONGO_URL": mongo_url,
        "MEDIA_ROOT": str(media_root),
    }


# -------- purge_preview_data.validate_target safety gates --------
@pytest.mark.parametrize(
    "patches,preview_url,error_snippet",
    [
        ({"APP_ENV": "production"}, "https://peptide-checkout-32.preview.emergentagent.com", "privacy-preview"),
        ({"PREVIEW_ONLY": "false"}, "https://peptide-checkout-32.preview.emergentagent.com", "privacy-preview"),
        ({"ALLOW_MANAGED_STORAGE": "true"}, "https://peptide-checkout-32.preview.emergentagent.com", "Managed storage"),
        ({}, "https://example.com", "preview origin"),
        ({"MONGO_URL": "mongodb://mongo.example.com:27017/test_db"}, "https://peptide-checkout-32.preview.emergentagent.com", "loopback"),
        ({"MONGO_URL": "mongodb+srv://cluster.example.mongodb.net/test_db"}, "https://peptide-checkout-32.preview.emergentagent.com", "standalone loopback"),
        ({"MONGO_URL": "mongodb://127.0.0.1:27017,localhost:27018/test_db"}, "https://peptide-checkout-32.preview.emergentagent.com", "multi-host"),
        ({"MONGO_URL": "mongodb://127.0.0.1:27017/test_db?replicaSet=rs0"}, "https://peptide-checkout-32.preview.emergentagent.com", "Replica/proxy"),
        ({"MONGO_URL": "mongodb://127.0.0.1:27017/test_db?loadBalanced=true"}, "https://peptide-checkout-32.preview.emergentagent.com", "Replica/proxy"),
    ],
)
def test_validate_target_refuses_unsafe_targets(patches, preview_url, error_snippet):
    with tempfile.TemporaryDirectory() as td:
        backend = Path(td) / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        env = _base_env(backend, "mongodb://127.0.0.1:27017/test_db", "test_db")
        env.update(patches)
        with pytest.raises(ValueError) as exc:
            purge_preview_data.validate_target(env, "test_db", preview_url, backend=backend)
        assert error_snippet.lower() in str(exc.value).lower()


def test_validate_target_refuses_proxy_like_uri_options():
    with tempfile.TemporaryDirectory() as td:
        backend = Path(td) / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        env = _base_env(backend, "mongodb://127.0.0.1:27017/test_db?proxyHost=127.0.0.1", "test_db")
        with pytest.raises((ValueError, ConfigurationError)):
            purge_preview_data.validate_target(env, "test_db", "https://peptide-checkout-32.preview.emergentagent.com", backend=backend)


def test_validate_target_refuses_mismatched_db_confirmation():
    with tempfile.TemporaryDirectory() as td:
        backend = Path(td) / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        env = _base_env(backend, "mongodb://127.0.0.1:27017/preview_db", "preview_db")
        with pytest.raises(ValueError) as exc:
            purge_preview_data.validate_target(env, "other_db", "https://peptide-checkout-32.preview.emergentagent.com", backend=backend)
        assert "explicitly confirmed database" in str(exc.value)


def test_validate_target_refuses_uri_db_mismatch():
    with tempfile.TemporaryDirectory() as td:
        backend = Path(td) / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        env = _base_env(backend, "mongodb://127.0.0.1:27017/db_in_uri", "db_env")
        with pytest.raises(ValueError) as exc:
            purge_preview_data.validate_target(env, "db_env", "https://peptide-checkout-32.preview.emergentagent.com", backend=backend)
        assert "URI database differs" in str(exc.value)


def test_validate_target_refuses_symlinked_or_external_runtime_paths():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        backend = base / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        outside = base / "outside"
        outside.mkdir(parents=True, exist_ok=True)

        env = _base_env(backend, "mongodb://127.0.0.1:27017/test_db", "test_db")

        # MEDIA_ROOT symlinked outside
        media_link = backend / ".media"
        shutil.rmtree(media_link)
        media_link.symlink_to(outside, target_is_directory=True)
        env["MEDIA_ROOT"] = str(media_link)
        with pytest.raises(ValueError) as exc:
            purge_preview_data.validate_target(env, "test_db", "https://peptide-checkout-32.preview.emergentagent.com", backend=backend)
        assert "MEDIA_ROOT" in str(exc.value)


def test_validate_target_accepts_literal_loopback_preview_target():
    with tempfile.TemporaryDirectory() as td:
        backend = Path(td) / "backend"
        backend.mkdir(parents=True, exist_ok=True)
        env = _base_env(backend, "mongodb://127.0.0.1:27017/test_db", "test_db")
        uri = purge_preview_data.validate_target(
            env,
            "test_db",
            "https://peptide-checkout-32.preview.emergentagent.com",
            backend=backend,
        )
        assert uri.startswith("mongodb://127.0.0.1")


# -------- purge_preview_data.clean_database isolation --------
def test_clean_database_preserves_configured_admin_and_replaces_settings(disposable_db):
    admin = {
        "id": "admin-1",
        "email": "admin@example.invalid",
        "role": "admin",
        "password_hash": "$2b$12$abcdefghijklmnopqrstuvabcdefghijklmnopqrstuvabcd",
        "name": "Configured Admin",
    }
    disposable_db.users.insert_many([
        copy.deepcopy(admin),
        {"id": "cust-1", "email": "customer@example.invalid", "role": "customer", "password_hash": "x"},
    ])
    disposable_db.products.insert_one({"id": "p1"})
    disposable_db.orders.insert_one({"id": "o1"})
    disposable_db.settings.insert_one({"key": "site", "value": {"legacy": True}})

    new_settings = {"site_name": "Fictional", "hero": "/demo-fixture.svg"}
    counts = purge_preview_data.clean_database(disposable_db, admin["email"], new_settings)

    kept_admin = disposable_db.users.find_one({"id": "admin-1"}, {"_id": 0})
    assert kept_admin == admin
    assert disposable_db.users.count_documents({}) == 1
    assert disposable_db.products.count_documents({}) == 0
    assert disposable_db.orders.count_documents({}) == 0
    site = disposable_db.settings.find_one({"key": "site"}, {"_id": 0})
    assert site == {"key": "site", "value": new_settings}
    assert counts["users"] == 1


def test_clean_database_fails_before_write_when_admin_missing(disposable_db):
    disposable_db.users.insert_one({"id": "u1", "email": "other@example.invalid", "role": "customer"})
    disposable_db.products.insert_one({"id": "p1"})
    with pytest.raises(ValueError) as exc:
        purge_preview_data.clean_database(disposable_db, "admin@example.invalid", {"x": 1})
    assert "administrator not found" in str(exc.value)
    assert disposable_db.products.count_documents({}) == 1


def test_clean_database_fails_before_write_on_unknown_populated_collections(disposable_db):
    disposable_db.users.insert_one({
        "id": "admin-1", "email": "admin@example.invalid", "role": "admin", "password_hash": "x"
    })
    disposable_db["unknown_collection"].insert_one({"k": 1})
    disposable_db.products.insert_one({"id": "p1"})
    with pytest.raises(ValueError) as exc:
        purge_preview_data.clean_database(disposable_db, "admin@example.invalid", {"x": 1})
    assert "Unreviewed collections" in str(exc.value)
    assert disposable_db.products.count_documents({}) == 1


# -------- preserve_runtime_data safety --------
def test_preserve_backend_adopts_runtime_data_and_never_overwrites_shared_files(tmp_path):
    app_root = tmp_path / "app"
    current_backend = app_root / "releases" / "old" / "backend"
    new_backend = app_root / "releases" / "new" / "backend"
    for p in (current_backend, new_backend):
        p.mkdir(parents=True, exist_ok=True)
        (p / "server.py").write_text("ok")
    (current_backend / "data" / "nextcart").mkdir(parents=True, exist_ok=True)
    (current_backend / "data" / "nextcart" / "countries.json").write_text("old-data")
    (new_backend / "data" / "nextcart").mkdir(parents=True, exist_ok=True)
    (new_backend / "data" / "nextcart" / "local.json").write_text("new-local")
    (app_root / "shared" / "nextcart").mkdir(parents=True, exist_ok=True)
    (app_root / "shared" / "nextcart" / "countries.json").write_text("shared-wins")

    preserve_runtime_data.preserve_backend(app_root, current_backend, new_backend)

    target = new_backend / "data" / "nextcart"
    assert target.is_symlink()
    shared = app_root / "shared" / "nextcart"
    assert (shared / "countries.json").read_text() == "shared-wins"
    assert (shared / "local.json").read_text() == "new-local"
    adopted = list((app_root / "shared").glob("adopted-nextcart-*"))
    assert adopted, "occupied new runtime dir should be preserved as backup, not deleted"
    assert (current_backend / "data" / "nextcart" / "countries.json").read_text() == "old-data"


def test_preserve_backend_refuses_unknown_runtime_symlink(tmp_path):
    app_root = tmp_path / "app"
    current_backend = app_root / "releases" / "old" / "backend"
    new_backend = app_root / "releases" / "new" / "backend"
    for p in (current_backend, new_backend):
        p.mkdir(parents=True, exist_ok=True)
        (p / "server.py").write_text("ok")

    weird_target = tmp_path / "other-runtime"
    weird_target.mkdir(parents=True, exist_ok=True)
    (new_backend / "data").mkdir(parents=True, exist_ok=True)
    (new_backend / "data" / "nextcart").symlink_to(weird_target, target_is_directory=True)

    with pytest.raises(ValueError) as exc:
        preserve_runtime_data.preserve_backend(app_root, current_backend, new_backend)
    assert "Unexpected runtime symlink" in str(exc.value)


def test_preserve_frontend_adopts_previous_assets_and_is_idempotent(tmp_path):
    web_root = tmp_path / "web"
    build = web_root / "build"
    stage = web_root / "build.new"
    build.mkdir(parents=True, exist_ok=True)
    for name in preserve_runtime_data.ASSETS:
        (build / name).write_text(f"old-{name}")

    preserve_runtime_data.preserve_frontend(web_root, stage)
    shared = web_root / "shared" / "public-media"
    for name in preserve_runtime_data.ASSETS:
        assert (shared / name).read_text() == f"old-{name}"
        assert (stage / name).read_text() == f"old-{name}"

    # Re-run with preexisting shared/staged values; must not overwrite
    (shared / preserve_runtime_data.ASSETS[0]).write_text("shared-custom")
    preserve_runtime_data.preserve_frontend(web_root, stage)
    assert (shared / preserve_runtime_data.ASSETS[0]).read_text() == "shared-custom"


# -------- storage + privacy behavior --------
def test_storage_preview_mode_disables_managed_storage_even_with_key(monkeypatch, tmp_path):
    import storage
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Privacy preview must never contact managed storage")
    try:
        with monkeypatch.context() as scope:
            scope.setenv("EMERGENT_LLM_KEY", "fictional-provider-key")
            scope.setenv("ALLOW_MANAGED_STORAGE", "false")
            scope.setenv("APP_ENV", "privacy-preview")
            scope.setenv("MEDIA_ROOT", str(tmp_path))
            for method in ("get", "post", "put"):
                scope.setattr(storage.requests, method, forbidden_network)
            importlib.reload(storage)
            assert storage.REMOTE_ENABLED is False
            assert storage.init_storage() == "local"
            with pytest.raises(FileNotFoundError):
                storage.get_object("not-present.png")
            result = storage.put_object("fictional.png", b"synthetic fixture", "image/png")
            assert result["mirrored"] is False
            assert storage.get_object("fictional.png")[0] == b"synthetic fixture"
    finally:
        importlib.reload(storage)


def test_storage_production_branch_retains_existing_enabled_behavior(monkeypatch, tmp_path):
    import storage
    try:
        with monkeypatch.context() as scope:
            scope.setenv("APP_ENV", "production")
            scope.delenv("ALLOW_MANAGED_STORAGE", raising=False)
            scope.setenv("EMERGENT_LLM_KEY", "fictional-provider-key")
            scope.setenv("MEDIA_ROOT", str(tmp_path))
            importlib.reload(storage)
            assert storage.REMOTE_ENABLED is True
    finally:
        importlib.reload(storage)


def test_track_privacy_preview_returns_disabled_without_db_write(monkeypatch):
    import server
    from starlette.requests import Request
    from starlette.responses import Response

    class _NoWriteDB:
        class visits:
            @staticmethod
            async def insert_one(_):
                raise AssertionError("track should not insert in privacy-preview")

    monkeypatch.setenv("APP_ENV", "privacy-preview")
    monkeypatch.setattr(server, "db", _NoWriteDB(), raising=True)
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/track",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    res = Response()
    payload = server.TrackIn(path="/", referrer="", locale="bg")
    out = run(server.track_visit(payload, req, res))
    assert out["tracking"] == "disabled-in-privacy-preview"
    assert not res.headers.get("set-cookie")


# -------- publication guard --------
def test_repository_privacy_guard_reports_zero_for_current_checkout():
    findings = check_repository_privacy.findings()
    assert findings == []


def test_cleanup_scripts_are_not_imported_by_startup_or_deploy():
    source = Path("/app/backend/server.py").read_text(encoding="utf-8")
    deploy_backend = Path("/app/deploy/hetzner/ansible/playbooks/deploy_backend.yml").read_text(encoding="utf-8")
    assert "purge_preview_data" not in source
    assert "purge_preview_data" not in deploy_backend
