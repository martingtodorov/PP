"""Iteration 55: deploy data-safety regressions for seed_catalog/seed_pages using isolated Mongo only.

Focus:
- seed_catalog must never overwrite existing catalog/settings (including stale/missing seed_version,
  catalog_imported true/false and ALLOW_RESEED=1)
- partial catalogs (only collections OR only articles) must stay untouched
- empty catalog initialization + second-call idempotency
- seed_pages must preserve edited/rotated pages and legacy alias DB records
- legacy alias URLs stay 404 in API + SSR and never appear in HTML link-index pages
"""

import copy
import json
import os
import time
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import prerender
import server
from conftest import run
from pages_seed import DEFAULT_PAGES, LEGACY_PAGE_ALIASES
from seed_data import ARTICLES, COLLECTIONS, PRODUCTS


SHELL = '<!doctype html><html lang="bg"><head><title>shell</title></head><body><div id="root"></div></body></html>'


def _doc_key(doc):
    return json.dumps(doc, ensure_ascii=False, sort_keys=True)


async def _dump_collection(db, name: str):
    docs = []
    async for row in db[name].find({}, {"_id": 0}):
        docs.append(row)
    return sorted(docs, key=_doc_key)


async def _snapshot_catalog_state(db):
    return {
        "products": await _dump_collection(db, "products"),
        "collections_cat": await _dump_collection(db, "collections_cat"),
        "articles": await _dump_collection(db, "articles"),
        "settings": await _dump_collection(db, "settings"),
    }


@pytest.fixture()
def isolated_db(monkeypatch):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db_name = f"{os.environ['DB_NAME']}_iter55_{uuid.uuid4().hex[:8]}"
    temp_db = mongo[db_name]

    old_db = server.db
    old_prerender_db = prerender._db
    old_shell = dict(prerender._shell_cache)
    old_pages = dict(prerender._pages)
    old_stamp = prerender._stamp

    monkeypatch.setattr(server, "db", temp_db, raising=True)
    prerender.init(temp_db)
    prerender._shell_cache.clear()
    prerender._shell_cache.update(html=SHELL, at=time.time())
    prerender._pages.clear()
    prerender._stamp = 0

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


# seed_catalog data neutrality against existing shop data
@pytest.mark.parametrize(
    "site_value,allow_reseed",
    [
        ({"site_name": "Keep stale version", "seed_version": "legacy-v1", "catalog_imported": False}, False),
        ({"site_name": "Keep no version", "catalog_imported": False}, False),
        ({"site_name": "Keep imported", "seed_version": "legacy-v2", "catalog_imported": True}, False),
        ({"site_name": "Keep under reseed flag", "seed_version": "legacy-v3", "catalog_imported": False}, True),
    ],
)
def test_seed_catalog_leaves_existing_catalog_and_settings_byte_identical(isolated_db, monkeypatch, site_value, allow_reseed):
    if allow_reseed:
        monkeypatch.setenv("ALLOW_RESEED", "1")
    else:
        monkeypatch.delenv("ALLOW_RESEED", raising=False)

    now = "2026-02-01T00:00:00+00:00"
    run(isolated_db.settings.insert_one({
        "key": "site",
        "value": {**site_value, "custom_flag": "DO_NOT_TOUCH", "hero_title": "Custom hero"},
        "updated_at": now,
    }))
    run(isolated_db.products.insert_one({
        "id": "prod-existing",
        "handle": "existing-handle",
        "title": "Existing product",
        "variants": [{"sku": "EXIST-1", "price_eur": 11.0, "stock": 5}],
        "active": True,
    }))
    run(isolated_db.collections_cat.insert_one({"id": "col-existing", "handle": "existing-col", "title": "Existing collection"}))
    run(isolated_db.articles.insert_one({"id": "art-existing", "handle": "existing-article", "title": "Existing article", "published": True}))

    before = run(_snapshot_catalog_state(isolated_db))
    run(server.seed_catalog())
    after = run(_snapshot_catalog_state(isolated_db))

    assert after == before


# partial-catalog protection (real prior regression gap)
@pytest.mark.parametrize(
    "seed_doc,expected_counts",
    [
        (
            ("collections_cat", {"id": "col-only", "handle": "partial-col", "title": "Partial collection"}),
            {"collections_cat": 1, "products": 0, "articles": 0},
        ),
        (
            ("articles", {"id": "art-only", "handle": "partial-art", "title": "Partial article", "published": True}),
            {"collections_cat": 0, "products": 0, "articles": 1},
        ),
    ],
)
def test_seed_catalog_does_not_fill_missing_parts_of_partial_catalog(isolated_db, seed_doc, expected_counts):
    name, doc = seed_doc
    run(isolated_db[name].insert_one(doc))
    run(isolated_db.settings.insert_one({"key": "site", "value": {"catalog_imported": False, "site_name": "Partial"}}))

    before = {
        "collections_cat": run(isolated_db.collections_cat.count_documents({})),
        "products": run(isolated_db.products.count_documents({})),
        "articles": run(isolated_db.articles.count_documents({})),
    }
    run(server.seed_catalog())
    after = {
        "collections_cat": run(isolated_db.collections_cat.count_documents({})),
        "products": run(isolated_db.products.count_documents({})),
        "articles": run(isolated_db.articles.count_documents({})),
    }

    assert before == expected_counts
    assert after == expected_counts


# empty-catalog initialization and idempotency
def test_seed_catalog_initializes_empty_db_and_second_call_is_idempotent(isolated_db):
    run(server.seed_catalog())
    first_counts = {
        "collections_cat": run(isolated_db.collections_cat.count_documents({})),
        "products": run(isolated_db.products.count_documents({})),
        "articles": run(isolated_db.articles.count_documents({})),
    }
    assert first_counts == {
        "collections_cat": len(COLLECTIONS),
        "products": len(PRODUCTS),
        "articles": len(ARTICLES),
    }

    first_settings = run(isolated_db.settings.find_one({"key": "site"}, {"_id": 0}))
    assert first_settings is not None

    state_after_first = run(_snapshot_catalog_state(isolated_db))
    run(server.seed_catalog())
    state_after_second = run(_snapshot_catalog_state(isolated_db))
    assert state_after_second == state_after_first


# preserve custom settings values when seeding into an empty catalog
def test_seed_catalog_preserves_existing_custom_settings_when_catalog_is_empty(isolated_db):
    custom = {
        "site_name": "Owner brand text",
        "catalog_imported": False,
        "hero_title": "Owner Hero",
        "nested": {"a": 1, "b": ["x", "y"]},
    }
    run(isolated_db.settings.insert_one({"key": "site", "value": copy.deepcopy(custom), "updated_at": "2026-02-01T00:00:00+00:00"}))

    run(server.seed_catalog())
    out = run(isolated_db.settings.find_one({"key": "site"}, {"_id": 0}))
    assert out is not None
    assert out["value"]["site_name"] == custom["site_name"]
    assert out["value"]["hero_title"] == custom["hero_title"]
    assert out["value"]["nested"] == custom["nested"]


# seed_pages safety for edited/rotated pages and alias records
def test_seed_pages_keeps_existing_rotated_page_and_legacy_alias_records(isolated_db, monkeypatch):
    edited = {
        "id": "faq-bg-edited",
        "slug": "faq",
        "locale": "bg",
        "title": "Edited FAQ",
        "html": "<p>Owner edited body</p>",
        "faq_items": [{"q": "q", "a": "a"}],
        "pub_slug": "faq-owner-rot",
        "rotations": [{"locale": "bg", "from": "faq", "to": "faq-owner-rot", "code": "own"}],
        "updated_at": "2026-02-01T00:00:00+00:00",
    }
    alias_slug = LEGACY_PAGE_ALIASES[0]
    legacy_alias = {
        "id": "alias-keep-1",
        "slug": alias_slug,
        "locale": "bg",
        "title": "Legacy alias row",
        "html": "<p>legacy</p>",
        "faq_items": [],
        "updated_at": "2026-02-01T00:00:00+00:00",
    }
    run(isolated_db.pages.insert_many([copy.deepcopy(edited), copy.deepcopy(legacy_alias)]))
    monkeypatch.setenv("RERUN_MIGRATION", "drop_page_aliases")

    run(server.seed_pages())

    kept = run(isolated_db.pages.find_one({"id": edited["id"]}, {"_id": 0}))
    kept_alias = run(isolated_db.pages.find_one({"id": legacy_alias["id"]}, {"_id": 0}))
    assert kept == edited
    assert kept_alias == legacy_alias


# legacy alias URLs must stay removed from public surface
def test_legacy_aliases_are_404_and_absent_from_link_indexes(isolated_db):
    run(server.seed_pages())
    run(isolated_db.settings.update_one(
        {"key": "site"},
        {"$set": {"key": "site", "value": {"site_name": "PurePeptide"}, "updated_at": "2026-02-01T00:00:00+00:00"}},
        upsert=True,
    ))

    index_pages = {p["slug"] for p in run(server.link_index("bg"))["pages"]}
    sitemap_pages = run(prerender._html_sitemap("bg", "html-sitemap-pages"))
    assert sitemap_pages is not None
    body = sitemap_pages["body"]

    for alias in LEGACY_PAGE_ALIASES:
        with pytest.raises(server.HTTPException) as exc:
            run(server.public_page(alias, locale="bg"))
        assert exc.value.status_code == 404

        rendered = run(prerender.render(f"/pages/{alias}", "purepeptide.bg"))
        assert rendered is not None
        html, status = rendered
        assert status == 404
        assert "noindex" in html

        assert alias not in index_pages
        assert f"/pages/{alias}" not in body

    # sanity: canonical seeded page still present so this is not a blanket-empty sitemap
    assert any(p["slug"] in DEFAULT_PAGES for p in run(server.link_index("bg"))["pages"])
