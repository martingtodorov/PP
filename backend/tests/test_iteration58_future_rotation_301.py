"""Iteration 58: future-rotation 301 policy regression tests (isolated Mongo).

Focus:
- A->B->C->D resolves old aliases directly to live D (no chain), per locale and kind
- markerless legacy rotations remain 404 (no retroactive backfill)
- API 404 middleware emits relative /api... redirects with preserved query string
- prerender endpoint emits 301 + no-store, and uses X-Original-URI query verbatim
- disabled/delisted/draft/empty content never redirects to 404 targets
- manual redirects keep precedence and collapse to final managed target when local
"""

import os
import uuid
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorCollection

import prerender
import server
from conftest import run
from i18n import LOCALES, SITE_ORIGINS
from rotation_redirects import LATEST_ROTATION_301


SHELL = '<!doctype html><html lang="bg"><head><title>shell</title></head><body><div id="root"></div></body></html>'


def _ok_res(status: int):
    class _R:
        matched_count = status
    return _R()


async def _seed(db):
    await db.settings.insert_one({
        "key": "site",
        "value": {"site_name": "PurePeptide", "locale_routes": SITE_ORIGINS},
    })

    product_tr = {loc: {"handle": f"prod-{loc}-d", "title": f"prod {loc}"} for loc in LOCALES}
    product_rot = []
    for loc in LOCALES:
        product_rot += [
            {"locale": loc, "from": f"prod-{loc}-a", "to": f"prod-{loc}-b", "code": "aaa", "redirect_mode": LATEST_ROTATION_301},
            {"locale": loc, "from": f"prod-{loc}-b", "to": f"prod-{loc}-c", "code": "bbb", "redirect_mode": LATEST_ROTATION_301},
            {"locale": loc, "from": f"prod-{loc}-c", "to": f"prod-{loc}-d", "code": "ccc", "redirect_mode": LATEST_ROTATION_301},
        ]
    await db.products.insert_one({
        "id": "prod-main",
        "handle": "prod-bg-d",
        "title": "Product BG",
        "description": "<p>Main product</p>",
        "active": True,
        "variants": [{"name": "5mg", "price_eur": 10.0, "stock": 5, "sku": "P-5"}],
        "collections": [],
        "translations": product_tr,
        "rotations": product_rot,
    })

    await db.collections_cat.insert_one({
        "id": "col-main",
        "handle": "col-bg-d",
        "title": "Collection BG",
        "description": "<p>Collection body</p>",
        "delisted": False,
        "nav_hidden": False,
        "sort_order": 0,
        "translations": {loc: {"handle": f"col-{loc}-d", "title": f"col {loc}"} for loc in LOCALES},
        "rotations": [
            item
            for loc in LOCALES
            for item in (
                {"locale": loc, "from": f"col-{loc}-a", "to": f"col-{loc}-b", "code": "aaa", "redirect_mode": LATEST_ROTATION_301},
                {"locale": loc, "from": f"col-{loc}-b", "to": f"col-{loc}-c", "code": "bbb", "redirect_mode": LATEST_ROTATION_301},
                {"locale": loc, "from": f"col-{loc}-c", "to": f"col-{loc}-d", "code": "ccc", "redirect_mode": LATEST_ROTATION_301},
            )
        ],
    })

    await db.articles.insert_one({
        "id": "art-main",
        "handle": "art-bg-d",
        "title": "Article BG",
        "excerpt": "x",
        "body": "<p>article body</p>",
        "published": True,
        "published_at": "2026-02-01T00:00:00+00:00",
        "translations": {loc: {"handle": f"art-{loc}-d", "title": f"art {loc}"} for loc in LOCALES},
        "rotations": [
            item
            for loc in LOCALES
            for item in (
                {"locale": loc, "from": f"art-{loc}-a", "to": f"art-{loc}-b", "code": "aaa", "redirect_mode": LATEST_ROTATION_301},
                {"locale": loc, "from": f"art-{loc}-b", "to": f"art-{loc}-c", "code": "bbb", "redirect_mode": LATEST_ROTATION_301},
                {"locale": loc, "from": f"art-{loc}-c", "to": f"art-{loc}-d", "code": "ccc", "redirect_mode": LATEST_ROTATION_301},
            )
        ],
    })

    await db.pages.insert_many([
        {
            "id": f"page-{loc}",
            "slug": "faq-fixture",
            "pub_slug": f"faq-{loc}-d",
            "locale": loc,
            "title": f"faq {loc}",
            "html": "<p>" + ("fixture text " * 8) + "</p>",
            "faq_items": [{"q": "q", "a": "a"}],
            "rotations": [
                {"locale": loc, "from": f"faq-{loc}-a", "to": f"faq-{loc}-b", "code": "aaa", "redirect_mode": LATEST_ROTATION_301},
                {"locale": loc, "from": f"faq-{loc}-b", "to": f"faq-{loc}-c", "code": "bbb", "redirect_mode": LATEST_ROTATION_301},
                {"locale": loc, "from": f"faq-{loc}-c", "to": f"faq-{loc}-d", "code": "ccc", "redirect_mode": LATEST_ROTATION_301},
            ],
        }
        for loc in LOCALES
    ])

    # Pre-existing history without marker: must stay 404 forever unless explicitly re-rotated now.
    await db.products.insert_one({
        "id": "legacy-no-marker",
        "handle": "legacy-new",
        "title": "legacy",
        "description": "<p>legacy</p>",
        "active": True,
        "variants": [{"name": "5mg", "price_eur": 1.0, "stock": 1, "sku": "LEG"}],
        "translations": {"bg": {"handle": "legacy-new"}},
        "rotations": [{"locale": "bg", "from": "legacy-old", "to": "legacy-new", "code": "l01"}],
    })

    # Disabled targets: must not 301 to a dead destination.
    await db.products.insert_one({
        "id": "prod-off",
        "handle": "prod-off-live",
        "title": "off",
        "description": "<p>off</p>",
        "active": False,
        "variants": [{"name": "5mg", "price_eur": 1.0, "stock": 0, "sku": "OFF"}],
        "translations": {"bg": {"handle": "prod-off-live"}},
        "rotations": [{"locale": "bg", "from": "prod-off-old", "to": "prod-off-live", "code": "off", "redirect_mode": LATEST_ROTATION_301}],
    })
    await db.collections_cat.insert_one({
        "id": "col-off",
        "handle": "col-off-live",
        "title": "off col",
        "description": "<p>off</p>",
        "delisted": True,
        "translations": {"bg": {"handle": "col-off-live"}},
        "rotations": [{"locale": "bg", "from": "col-off-old", "to": "col-off-live", "code": "off", "redirect_mode": LATEST_ROTATION_301}],
    })
    await db.articles.insert_one({
        "id": "art-off",
        "handle": "art-off-live",
        "title": "off art",
        "excerpt": "x",
        "body": "<p>x</p>",
        "published": False,
        "translations": {"bg": {"handle": "art-off-live"}},
        "rotations": [{"locale": "bg", "from": "art-off-old", "to": "art-off-live", "code": "off", "redirect_mode": LATEST_ROTATION_301}],
    })
    await db.pages.insert_one({
        "id": "page-off",
        "slug": "off-page",
        "pub_slug": "off-page-live",
        "locale": "bg",
        "title": "",
        "html": "",
        "faq_items": [],
        "rotations": [{"locale": "bg", "from": "off-page-old", "to": "off-page-live", "code": "off", "redirect_mode": LATEST_ROTATION_301}],
    })

    # Same source handle in two locales must resolve independently.
    await db.products.insert_one({
        "id": "prod-shared",
        "handle": "shared-bg-d",
        "title": "shared",
        "description": "<p>shared</p>",
        "active": True,
        "variants": [{"name": "5mg", "price_eur": 11.0, "stock": 2, "sku": "S-5"}],
        "translations": {"bg": {"handle": "shared-bg-d"}, "en": {"handle": "shared-en-d"}},
        "rotations": [
            {"locale": "bg", "from": "shared-a", "to": "shared-bg-d", "code": "sbg", "redirect_mode": LATEST_ROTATION_301},
            {"locale": "en", "from": "shared-a", "to": "shared-en-d", "code": "sen", "redirect_mode": LATEST_ROTATION_301},
        ],
    })


@pytest.fixture()
def isolated_db(monkeypatch):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db_name = f"{os.environ['DB_NAME']}_iter58_{uuid.uuid4().hex[:8]}"
    temp_db = client[db_name]

    old_db = server.db
    old_prerender_db = prerender._db
    old_shell = dict(prerender._shell_cache)
    old_pages = dict(prerender._pages)
    old_stamp = prerender._stamp

    monkeypatch.setattr(server, "db", temp_db, raising=True)
    prerender.init(temp_db)
    prerender._shell_cache.update(html=SHELL, at=10**9)
    prerender._pages.clear()
    prerender._stamp = 0

    run(_seed(temp_db))
    yield temp_db

    run(client.drop_database(db_name))
    monkeypatch.setattr(server, "db", old_db, raising=True)
    prerender.init(old_prerender_db)
    prerender._shell_cache.clear(); prerender._shell_cache.update(old_shell)
    prerender._pages.clear(); prerender._pages.update(old_pages)
    prerender._stamp = old_stamp
    client.close()


def _call(path: str, method: str = "GET", headers=None):
    async def run_req():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app),
            base_url="http://testserver",
            follow_redirects=False,
            timeout=30,
        ) as client:
            return await client.request(method, path, headers=headers or {})
    return run(run_req())


def test_all_kinds_all_locales_old_aliases_directly_301_to_current_live_and_head_supported(isolated_db):
    matrix = [
        ("products", "prod"),
        ("collections", "col"),
        ("articles", "art"),
        ("pages", "faq"),
    ]
    for kind, stem in matrix:
        for loc in LOCALES:
            for old in ("a", "b", "c"):
                src = f"/api/{kind}/{stem}-{loc}-{old}?locale={loc}&utm=1"
                r_get = _call(src, "GET")
                r_head = _call(src, "HEAD")
                assert r_get.status_code == 301
                assert r_head.status_code == 301
                assert r_get.headers.get("cache-control") == "no-store"
                assert r_head.headers.get("cache-control") == "no-store"
                assert r_get.headers["location"] == f"/api/{kind}/{stem}-{loc}-d?locale={loc}&utm=1"

            live = _call(f"/api/{kind}/{stem}-{loc}-d?locale={loc}", "GET")
            assert live.status_code == 200


def test_markerless_legacy_history_remains_404_before_and_after_new_rotation(isolated_db):
    before = _call("/api/products/legacy-old?locale=bg")
    assert before.status_code == 404

    run(server.rotate_content("products", "legacy-new", "bg", "pytest@iter58", to="legacy-next"))

    still_old = _call("/api/products/legacy-old?locale=bg")
    now_prev = _call("/api/products/legacy-new?locale=bg")
    assert still_old.status_code == 404
    assert now_prev.status_code == 301
    assert now_prev.headers["location"] == "/api/products/legacy-next?locale=bg"


def test_disabled_or_unpublished_targets_do_not_redirect(isolated_db):
    assert _call("/api/products/prod-off-old?locale=bg").status_code == 404
    assert _call("/api/collections/col-off-old?locale=bg").status_code == 404
    assert _call("/api/articles/art-off-old?locale=bg").status_code == 404
    assert _call("/api/pages/off-page-old?locale=bg").status_code == 404


def test_api_redirect_preserves_query_string_with_plus_percent_and_repeated_params(isolated_db):
    r = _call("/api/products/prod-en-a?locale=en&utm=a+b&x=1%2B2&many=1&many=2")
    assert r.status_code == 301
    assert r.headers["location"].startswith("/api/products/prod-en-d?")
    parsed = parse_qs(urlsplit(r.headers["location"]).query, keep_blank_values=True)
    assert parsed["locale"] == ["en"]
    assert parsed["utm"] == ["a b"]
    assert parsed["x"] == ["1+2"]
    assert parsed["many"] == ["1", "2"]


def test_cross_locale_same_source_handle_resolves_independently(isolated_db):
    bg = _call("/api/products/shared-a?locale=bg")
    en = _call("/api/products/shared-a?locale=en")
    assert bg.status_code == 301 and en.status_code == 301
    assert bg.headers["location"] == "/api/products/shared-bg-d?locale=bg"
    assert en.headers["location"] == "/api/products/shared-en-d?locale=en"


def test_prerender_redirect_uses_x_original_uri_raw_query_and_no_store(isolated_db):
    headers = {
        "x-forwarded-host": "purepeptide.gr",
        "x-original-uri": "/products/prod-gr-a?utm=ab+cd&x=1%2B2&many=1&many=2",
    }
    r = _call("/api/seo/prerender?path=/products/prod-gr-a", headers=headers)
    assert r.status_code == 301
    assert r.headers.get("cache-control") == "no-store"
    assert r.headers["location"].startswith("https://purepeptide.gr/products/prod-gr-d?")
    out_q = urlsplit(r.headers["location"]).query
    assert "utm=ab+cd" in out_q
    assert "x=1%2B2" in out_q
    assert "many=1" in out_q and "many=2" in out_q


def test_manual_redirect_has_precedence_and_local_target_collapses_to_latest_live(isolated_db):
    run(isolated_db.redirects.insert_one({
        "id": "man-1",
        "from_path": "/manual-legacy",
        "to_url": "/products/prod-bg-b",
        "active": True,
        "hits": 0,
        "last_hit": "",
    }))
    target = run(server.find_redirect("/manual-legacy", "purepeptide.bg"))
    assert target == "https://purepeptide.bg/products/prod-bg-d"

    run(isolated_db.redirects.insert_one({
        "id": "man-2",
        "from_path": "/manual-external",
        "to_url": "https://external.example/path",
        "active": True,
    }))
    assert run(server.find_redirect("/manual-external", "purepeptide.bg")) == "https://external.example/path"


def test_rotations_do_not_auto_create_manual_redirect_records(isolated_db):
    before = run(isolated_db.redirects.count_documents({}))
    run(server.rotate_content("products", "prod-bg-d", "bg", "pytest@iter58", to="prod-bg-restored"))
    after = run(isolated_db.redirects.count_documents({}))
    assert before == after == 0


def test_same_target_as_current_rejected_and_conflicting_write_returns_409(isolated_db, monkeypatch):
    with pytest.raises(server.HTTPException) as same:
        run(server.rotate_content("products", "prod-bg-d", "bg", "pytest@iter58", to="prod-bg-d"))
    assert same.value.status_code == 400

    original = AsyncIOMotorCollection.update_one

    async def conflict(self, *args, **kwargs):
        if getattr(self, "name", "") == "products":
            return _ok_res(0)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(AsyncIOMotorCollection, "update_one", conflict, raising=True)
    with pytest.raises(server.HTTPException) as conflict_exc:
        run(server.rotate_content("products", "prod-bg-d", "bg", "pytest@iter58", to="prod-bg-z"))
    assert conflict_exc.value.status_code == 409


def test_restoring_historical_handle_makes_it_live_without_self_redirect_loop(isolated_db):
    run(server.rotate_content("products", "prod-bg-d", "bg", "pytest@iter58", to="prod-bg-b"))
    live = _call("/api/products/prod-bg-b?locale=bg")
    old = _call("/api/products/prod-bg-d?locale=bg")
    assert live.status_code == 200
    assert old.status_code == 301
    assert old.headers["location"] == "/api/products/prod-bg-b?locale=bg"
