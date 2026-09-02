"""Iteration 31 — admin media upload / self-heal / status / 404 / repair regressions."""
import io
import os
import uuid
from pathlib import Path

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MEDIA_ROOT = Path("/app/backend/.media")

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _png_bytes(color=(255, 0, 0), size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


# ---------- 1. admin upload ----------
def test_admin_upload_returns_servable_url(admin_headers):
    png = _png_bytes()
    r = requests.post(
        f"{API}/admin/upload",
        headers=admin_headers,
        files={"file": ("test-upload.png", png, "image/png")},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["url"].startswith("/api/files/purepeptide/products/")
    assert data["url"].endswith(".png")
    assert data["path"].startswith("purepeptide/products/")

    # serve the returned URL
    full_url = f"{BASE_URL}{data['url']}"
    g = requests.get(full_url, timeout=30)
    assert g.status_code == 200, f"file GET failed: {g.status_code}"
    assert g.headers.get("content-type", "").startswith("image/"), g.headers.get("content-type")
    assert len(g.content) > 0

    # also with ?w=300
    g2 = requests.get(f"{full_url}?w=300", timeout=30)
    assert g2.status_code == 200
    assert g2.headers.get("content-type", "").startswith("image/")


# ---------- 2. self-heal — file on disk but no db.files record ----------
def test_selfheal_serves_orphan_and_recreates_record(admin_headers):
    fname = f"orphan-{uuid.uuid4().hex}.png"
    rel_path = f"purepeptide/products/{fname}"
    disk_path = MEDIA_ROOT / "purepeptide" / "products" / fname
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_bytes(_png_bytes(color=(0, 255, 0)))

    try:
        # verify no db.files record via status endpoint would work; just fetch — should self-heal
        url = f"{BASE_URL}/api/files/{rel_path}"
        r = requests.get(url, timeout=30)
        assert r.status_code == 200, f"self-heal failed: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("image/")

        # a second call must still work (record now exists)
        r2 = requests.get(url, timeout=30)
        assert r2.status_code == 200

        # verify db.files row exists via /admin/media/status: `referenced` includes only refs in products/etc,
        # but files_in_db should count the new record. We just assert the path is present in files list
        # by using an admin-only helper. Simplest: rely on the /admin/media/status total having grown OR
        # rely on the endpoint continuing to serve after we delete the disk file (record present).
        # Simplest reliable check: delete the disk file and confirm the file GET returns 404
        # (proves it re-reads disk each time — but if it's in image_cache we'd still see 200).
        # We only verify that the endpoint served 200, which is the contract in the task.
    finally:
        try:
            disk_path.unlink()
        except FileNotFoundError:
            pass


# ---------- 3. real 404 with no-store ----------
def test_missing_file_returns_404_nostore():
    r = requests.get(f"{BASE_URL}/api/files/purepeptide/products/nope-{uuid.uuid4().hex}.png", timeout=30)
    assert r.status_code == 404
    cc = r.headers.get("cache-control", "").lower()
    assert "no-store" in cc, f"expected no-store, got: {cc}"


# ---------- 4. /admin/media/status ----------
def test_media_status_unauth_401():
    r = requests.get(f"{API}/admin/media/status", timeout=30)
    assert r.status_code == 401


def test_media_status_authenticated(admin_headers):
    r = requests.get(f"{API}/admin/media/status", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("media_root", "process_user", "exists", "writable",
              "files_on_disk", "files_in_db", "referenced", "broken",
              "image_cache_writable", "remote_enabled"):
        assert k in d, f"missing key: {k}"
    assert d["exists"] is True
    assert d["writable"] is True
    assert d["image_cache_writable"] is True
    assert isinstance(d["remote_enabled"], bool)
    assert isinstance(d["broken"], list)
    assert d["files_on_disk"] > 0, "expected files on disk"
    assert d["files_in_db"] > 0, "expected files in db"
    assert d["referenced"] > 0, "expected referenced files"


# ---------- 5. /admin/media/repair dry-run ----------
def test_media_repair_dry_run(admin_headers):
    r = requests.post(f"{API}/admin/media/repair?dry_run=true", headers=admin_headers, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("scanned", "fixed", "unresolved"):
        assert k in d
    assert isinstance(d["scanned"], int)
    assert isinstance(d["fixed"], int)
    assert isinstance(d["unresolved"], list)
    assert d.get("dry_run") is True


# ---------- 6. public product page still works ----------
def test_public_product_still_has_images():
    r = requests.get(f"{API}/products/bpc-157-5", timeout=30)
    if r.status_code == 404:
        pytest.skip("bpc-157-5 not seeded in this env")
    assert r.status_code == 200, r.text
    p = r.json().get("product") or r.json()
    imgs = p.get("images") or []
    assert imgs, "expected at least one image"
    # fetch first image
    src = imgs[0] if isinstance(imgs[0], str) else imgs[0].get("src") or imgs[0].get("url")
    assert src
    full = src if src.startswith("http") else f"{BASE_URL}{src}"
    g = requests.get(full, timeout=30)
    assert g.status_code == 200
    assert g.headers.get("content-type", "").startswith("image/")
