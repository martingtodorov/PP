"""Iteration 54: focused SSR/internal-link/metadata regressions with isolated Mongo.

Coverage highlights:
- per-locale published handles/slugs in SSR + /api/link-index
- legacy alias pages excluded; missing locale page keeps base slug
- prerender cache invalidation after rotations (+ stale concurrent render guard)
- internal-link crawler (ASGITransport) full crawl + source reporting on broken anchors
- SEO head basics on live pages: robots index, hreflang count, parseable JSON-LD
"""
import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import prerender
import server
from conftest import run
from i18n import DEFAULT_LOCALE, LOCALES, SITE_ORIGINS
from pages_seed import LEGACY_PAGE_ALIASES, PAGE_SLUGS

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_internal_links import audit  # noqa: E402


SHELL = '<!doctype html><html lang="bg"><head><title>shell</title></head><body><div id="root"></div></body></html>'


def _host(locale: str) -> str:
    return SITE_ORIGINS[locale]["origin"].replace("https://", "")


def _prefixed_home(locale: str) -> str:
    prefix = SITE_ORIGINS[locale].get("prefix", "")
    return f"{prefix}/" if prefix else "/"


def _head_value(head_html: str, key: str) -> str:
    m = re.search(fr'name="{re.escape(key)}"\s+content="([^"]*)"', head_html)
    return m.group(1) if m else ""


async def _seed_isolated_catalog(db):
    now = "2026-02-01T00:00:00+00:00"
    await db.settings.insert_one({
        "key": "site",
        "value": {"site_name": "PurePeptide", "locale_routes": SITE_ORIGINS},
        "updated_at": now,
    })

    catalog_translations = {
        loc: {"handle": f"catalog-{loc}", "title": f"Catalog {loc}"}
        for loc in LOCALES
    }
    catalog_translations["bg"]["handle"] = "catalog-bg-live"
    await db.collections_cat.insert_one({
        "id": "col-catalog",
        "handle": "catalog-bg-live",
        "link_key": "catalog",
        "title": "Catalog main",
        "description": "<p>All products</p>",
        "translations": catalog_translations,
        "rotations": [{"locale": "bg", "from": "2all-the-peptides-1", "to": "catalog-bg-live", "code": "cat"}],
        "delisted": False,
        "nav_hidden": False,
        "sort_order": 0,
    })

    await db.collections_cat.insert_one({
        "id": "col-metabolic",
        "handle": "metabolic-base",
        "title": "Metabolic studies",
        "description": "<p>Metabolic collection</p>",
        "translations": {
            "bg": {"handle": "metabolic-bg", "title": "Метаболитни"},
            "en": {"handle": "metabolic-en-live", "title": "Metabolic EN"},
        },
        "rotations": [{"locale": "en", "from": "metabolic-en-old", "to": "metabolic-en-live", "code": "enx"}],
        "delisted": False,
        "nav_hidden": False,
        "sort_order": 1,
    })

    await db.collections_cat.insert_one({
        "id": "col-delisted",
        "handle": "delisted-col",
        "title": "Delisted",
        "description": "<p>Hidden</p>",
        "delisted": True,
        "nav_hidden": False,
        "sort_order": 2,
    })

    await db.products.insert_many([
        {
            "id": "prod-main",
            "handle": "bpc-base",
            "title": "BPC-157 5mg",
            "description": "<h1>Raw body H1</h1><p>Body copy</p>",
            "image": "/og-image.jpg",
            "images": ["/og-image.jpg"],
            "variants": [{"name": "5mg", "price_eur": 49.0, "stock": 3, "sku": "BPC-5"}],
            "collections": ["catalog-bg-live", "metabolic-en-old", "delisted-col"],
            "active": True,
            "translations": {
                "en": {"handle": "bpc-en-live", "title": "BPC EN"},
                "de": {"handle": "bpc-de-live", "title": "BPC DE"},
            },
            "rotations": [{"locale": "en", "from": "bpc-en-old", "to": "bpc-en-live", "code": "enb"}],
        },
        {
            "id": "prod-related-active",
            "handle": "active-related",
            "title": "Active related",
            "description": "<p>related</p>",
            "image": "/og-image.jpg",
            "variants": [{"name": "5mg", "price_eur": 20.0, "stock": 2, "sku": "REL-A"}],
            "collections": ["catalog-bg-live"],
            "active": True,
        },
        {
            "id": "prod-related-inactive",
            "handle": "inactive-related",
            "title": "Inactive related",
            "description": "<p>inactive</p>",
            "image": "/og-image.jpg",
            "variants": [{"name": "5mg", "price_eur": 20.0, "stock": 0, "sku": "REL-I"}],
            "collections": ["catalog-bg-live"],
            "active": False,
        },
    ])

    await db.articles.insert_one({
        "id": "art-1",
        "handle": "science-1",
        "title": "Science article",
        "excerpt": "Excerpt",
        "body": "<p>Article body</p>",
        "published": True,
        "published_at": now,
        "translations": {},
    })

    page_docs = []
    for slug in PAGE_SLUGS:
        page_docs.append({
            "id": f"page-bg-{uuid.uuid4().hex[:8]}",
            "slug": slug,
            "locale": "bg",
            "title": f"{slug} bg",
            "html": f"<p>{slug} body</p>",
            "faq_items": [],
            "updated_at": now,
        })
    # Simulate a bg-only rotated slug; missing locale pages must keep base slug.
    for page in page_docs:
        if page["slug"] == "faq":
            page["pub_slug"] = "faq-bg-rot"
            page["rotations"] = [{"locale": "bg", "from": "faq", "to": "faq-bg-rot", "code": "fbg"}]
    page_docs.append({
        "id": "page-en-faq",
        "slug": "faq",
        "locale": "en",
        "title": "faq en",
        "html": "<p>faq en body</p>",
        "faq_items": [],
        "updated_at": now,
    })
    await db.pages.insert_many(page_docs)


@pytest.fixture()
def isolated_db(monkeypatch):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db_name = f"{os.environ['DB_NAME']}_seo_{uuid.uuid4().hex[:8]}"
    temp_db = mongo[db_name]

    old_db = server.db
    old_prerender_db = prerender._db
    old_shell = dict(prerender._shell_cache)
    old_pages = dict(prerender._pages)
    old_stamp = prerender._stamp

    monkeypatch.setattr(server, "db", temp_db, raising=True)
    prerender.init(temp_db)
    prerender._shell_cache.update(html=SHELL, at=time.time())
    prerender._pages.clear()
    prerender._stamp = 0

    run(_seed_isolated_catalog(temp_db))
    yield temp_db

    run(mongo.drop_database(db_name))
    monkeypatch.setattr(server, "db", old_db, raising=True)
    prerender.init(old_prerender_db)
    prerender._shell_cache.clear()
    prerender._shell_cache.update(old_shell)
    prerender._pages.clear()
    prerender._pages.update(old_pages)
    prerender._stamp = old_stamp
    mongo.close()


def test_ssr_home_and_catalog_use_per_locale_published_handles(isolated_db):
    for loc in LOCALES:
        idx = run(server.link_index(loc))
        expected = f"catalog-{loc}" if loc != "bg" else "catalog-bg-live"
        assert any(c["handle"] == expected for c in idx["collections"])

        html, status = run(prerender.render(_prefixed_home(loc), _host(loc)))
        assert status == 200
        assert prerender.url_for(loc, f"/collections/{expected}") in html

        cat_html, cat_status = run(prerender.render(f"{SITE_ORIGINS[loc]['prefix']}/collections", _host(loc)))
        assert cat_status == 200
        assert f"/collections/{expected}" in cat_html


def test_link_index_pages_use_locale_slug_and_exclude_legacy_aliases(isolated_db):
    ro_page = run(server.public_page("faq", locale="ro"))["page"]
    assert ro_page["source_locale"] in {"en", "bg"}
    assert ro_page["slugs"]["bg"] == "faq-bg-rot"
    assert ro_page["slugs"]["ro"] == "faq"  # base slug, never bg rotated pub_slug

    pages = run(server.link_index("ro"))["pages"]
    slugs = {p["slug"] for p in pages}
    assert "faq" in slugs
    assert "faq-bg-rot" not in slugs

    for alias in LEGACY_PAGE_ALIASES:
        with pytest.raises(server.HTTPException) as exc:
            run(server.public_page(alias, locale=DEFAULT_LOCALE))
        assert exc.value.status_code == 404


def test_product_membership_handles_historical_collection_refs_and_filters_inactive(isolated_db):
    out = run(server.get_product("bpc-base", locale="bg"))
    collection_titles = {c.get("title") for c in out["collections"]}
    assert "Метаболитни" in collection_titles or "Metabolic studies" in collection_titles

    related_handles = {p.get("handle") for p in out["related"]}
    assert "active-related" in related_handles
    assert "inactive-related" not in related_handles


def test_prerender_cache_invalidates_on_rotate_content_and_rotate_page(isolated_db, monkeypatch):
    # prime cache
    before_html, before_status = run(prerender.render("/products/bpc-base", "purepeptide.bg"))
    assert before_status == 200
    assert "bpc-base" in before_html

    # Product rotation: explicit handle (no paid AI rewrite call).
    rotated = run(server.rotate_content("products", "bpc-base", "bg", "pytest@purepeptide.bg", to="bpc-rotated"))
    assert rotated["handle"] == "bpc-rotated"

    old_html, old_status = run(prerender.render("/products/bpc-base", "purepeptide.bg"))
    assert old_status == 404
    new_html, new_status = run(prerender.render("/products/bpc-rotated", "purepeptide.bg"))
    assert new_status == 200
    assert "/products/bpc-rotated" in new_html

    # Page rotation: mock paid AI rewrite in tests only.
    async def fake_rewrite(markup, locale, context=""):
        return markup.replace("body", "body rewritten")

    monkeypatch.setattr(server, "ai_rewrite_html", fake_rewrite, raising=True)
    page_rotated = run(server.rotate_page(
        {"id": "x", "url": "/pages/privacy-policy"},
        "privacy-policy",
        "bg",
        "pytest@purepeptide.bg",
    ))
    new_slug = page_rotated["handle"]
    page_after = run(server.public_page(new_slug, locale="bg"))["page"]
    assert page_after["slug"] == "privacy-policy"
    assert page_after["source_locale"] == "bg"


def test_concurrent_render_does_not_repopulate_cache_after_bump(isolated_db, monkeypatch):
    original_route = prerender._route

    async def slow_route(locale, route):
        await asyncio.sleep(0.08)
        return await original_route(locale, route)

    monkeypatch.setattr(prerender, "_route", slow_route, raising=True)

    async def run_case():
        key = ("purepeptide.bg", "/")
        prerender._pages.pop(key, None)
        task = asyncio.create_task(prerender.render("/", "purepeptide.bg"))
        await asyncio.sleep(0.02)
        prerender.bump()
        out = await task
        assert out is not None
        assert key not in prerender._pages

    run(run_case())


def test_internal_link_audit_full_crawl_with_asgi_transport(isolated_db):
    async def run_audit():
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False, timeout=60) as client:
            return await audit(client, "http://testserver")

    report = run(run_audit())
    assert report["checked"] > 0
    assert report["broken"] == []
    assert report["noncanonical"] == []
    assert report["sitemap_errors"] == []


def test_crawler_does_not_treat_image_sitemap_metadata_as_page_urls(isolated_db):
    run(isolated_db.products.update_one({"id": "prod-main"},
        {"$set": {"image": "/not-an-anchor.png", "images": ["/not-an-anchor.png"]}}))

    async def run_audit():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),
                                    base_url="http://testserver", follow_redirects=False, timeout=60) as client:
            return await audit(client, "http://testserver")

    report = run(run_audit())
    assert report["broken"] == []
    assert report["sitemap_errors"] == []


def test_internal_link_audit_records_source_urls_for_broken_anchors(isolated_db):
    run(server.db.pages.update_one(
        {"slug": "about-1", "locale": "bg"},
        {"$set": {"html": '<p><a href="/pages/does-not-exist">bad link</a></p>'}},
    ))
    prerender.bump()

    async def run_audit():
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False, timeout=60) as client:
            return await audit(client, "http://testserver")

    report = run(run_audit())
    bad = next((b for b in report["broken"] if b["url"].endswith("/pages/does-not-exist")), None)
    assert bad is not None
    assert bad["status"] == 404
    assert any("/pages/about-1" in s for s in bad["sources"])


def test_seo_metadata_alignment_for_html_sitemap_articles_and_privacy_page(isolated_db):
    idx = run(server.link_index("bg"))
    for slug in ("html-sitemap", "html-sitemap-products", "html-sitemap-collections",
                 "html-sitemap-blogs", "html-sitemap-articles", "html-sitemap-pages"):
        rendered = run(prerender._html_sitemap("bg", slug))
        assert rendered is not None
        head = rendered["head"]
        assert f"<title>{prerender.esc(prerender.brand_title(idx['seo'][slug]['title']))}</title>" in head
        assert _head_value(head, "description") == idx["seo"][slug]["description"]

    articles = run(server.list_articles(locale="bg"))
    articles_html = run(prerender._articles_index("bg"))["head"]
    assert f"<title>{prerender.esc(prerender.brand_title(articles['seo']['title']))}</title>" in articles_html
    assert _head_value(articles_html, "description") == articles["seo"]["description"]

    page = run(server.public_page("privacy-policy", locale="bg"))["page"]
    page_html = run(prerender._page("bg", "privacy-policy"))["head"]
    assert f"<title>{prerender.esc(prerender.brand_title(page['seo']['title']))}</title>" in page_html
    assert _head_value(page_html, "description") == page["seo"]["description"]


def test_live_prerender_head_has_indexing_hreflang_and_parseable_jsonld(isolated_db):
    html, status = run(prerender.render("/products/bpc-base", "purepeptide.bg"))
    assert status == 200
    assert 'name="robots" content="index, follow' in html
    assert 'noindex' not in html
    assert html.count('rel="alternate" hreflang=') == 12  # 11 locales + x-default

    blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    assert blocks
    parsed = [json.loads(block) for block in blocks]
    assert all(isinstance(b, dict) for b in parsed)


def test_release_gate_script_still_invokes_internal_link_audit():
    src = (Path(__file__).resolve().parents[1] / "scripts/check_sitemap.py").read_text("utf-8")
    assert "from check_internal_links import audit" in src
    assert "internal = await audit(" in src


def test_long_static_metadata_is_identical_in_api_and_ssr(isolated_db):
    import html
    text = "Текст & данни за поверителност. " * 8
    run(isolated_db.pages.update_one({"slug": "privacy-policy", "locale": "bg"},
        {"$set": {"html": f"<p>{html.escape(text)}</p>", "seo_description": ""}}))
    page = run(server.public_page("privacy-policy", "bg"))["page"]
    description = page["seo"]["description"]
    assert len(description) > 155
    assert description == text.strip()
    rendered = run(prerender._page("bg", "privacy-policy"))
    assert html.unescape(_head_value(rendered["head"], "description")) == description
    explicit = "Редактирано мета описание & важно уточнение. " * 10
    run(isolated_db.pages.update_one({"slug": "privacy-policy", "locale": "bg"},
        {"$set": {"seo_description": explicit}}))
    assert run(server.public_page("privacy-policy", "bg"))["page"]["seo"]["description"] == explicit
    assert html.unescape(_head_value(run(prerender._page("bg", "privacy-policy"))["head"], "description")) == explicit


def test_rotating_collection_immediately_retargets_cached_indexes(isolated_db):
    for path in ("/", "/collections", "/pages/html-sitemap-collections"):
        run(prerender.render(path, _host("bg")))
    run(server.rotate_content("collections", "metabolic-base", "bg", "pytest@purepeptide.bg", to="metabolic-next"))
    for path in ("/", "/collections", "/pages/html-sitemap-collections"):
        markup, status = run(prerender.render(path, _host("bg")))
        assert status == 200
        assert 'href="https://purepeptide.bg/collections/metabolic-next"' in markup
        assert 'href="https://purepeptide.bg/collections/metabolic-base"' not in markup
        assert 'href="https://purepeptide.bg/collections/metabolic-bg"' not in markup
    assert run(prerender.render("/collections/metabolic-bg", _host("bg")))[1] == 404
    assert run(prerender.render("/en/collections/metabolic-en-live", _host("en")))[1] == 200