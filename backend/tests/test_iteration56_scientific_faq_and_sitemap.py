"""Iteration 56: scientific-literature + EN FAQ + collections sitemap regressions.

Isolated Mongo for page/article behavior, plus host-aware sitemap checks through the real API.
"""
import json
import os
import re
import time
import uuid
from html import unescape
from urllib.parse import urlsplit

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

import prerender
import server
from conftest import run
from i18n import LOCALES, SITE_ORIGINS


SHELL = '<!doctype html><html lang="bg"><head><title>shell</title></head><body><div id="root"></div></body></html>'
FAQ_SEO_FALLBACK = (
    "Answers to frequently asked questions about PurePeptide, laboratory analysis, "
    "certificates, peptide storage and delivery."
)
API_LOCAL = "http://localhost:8001/api"


def _host(loc: str) -> str:
    return SITE_ORIGINS[loc]["origin"].replace("https://", "")


def _route(loc: str, path: str) -> str:
    prefix = SITE_ORIGINS[loc].get("prefix", "")
    return f"{prefix}{path}" if prefix else path


@pytest.fixture()
def isolated_db(monkeypatch):
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db_name = f"{os.environ['DB_NAME']}_iter56_{uuid.uuid4().hex[:8]}"
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

    run(temp_db.settings.insert_one({
        "key": "site",
        "value": {"site_name": "PurePeptide", "locale_routes": SITE_ORIGINS},
        "updated_at": "2026-02-01T00:00:00+00:00",
    }))
    run(temp_db.pages.insert_one({
        "id": "faq-bg",
        "slug": "faq",
        "locale": "bg",
        "title": "FAQ BG",
        "html": "<p>Често задавани въпроси</p>",
        "faq_items": [{"q": "BG q", "a": "BG a"}],
        "updated_at": "2026-02-01T00:00:00+00:00",
    }))

    run(temp_db.articles.insert_many([
        {
            "id": "art-live-1",
            "handle": "science-live-1",
            "title": "Science live one",
            "excerpt": "Useful excerpt for researchers.",
            "body": "<p>Body one</p>",
            "published": True,
            "published_at": "2026-02-01T00:00:00+00:00",
            "translations": {"en": {"handle": "science-live-1-en", "title": "Science EN one"}},
        },
        {
            "id": "art-live-2",
            "handle": "science-live-2",
            "title": "Unsafe <script>alert(1)</script> title",
            "excerpt": "<script>alert('x')</script> excerpt <b>safe</b>",
            "body": "<p>Body two</p>",
            "published": True,
            "published_at": "2026-02-02T00:00:00+00:00",
            "translations": {
                "en": {"handle": "science-live-2-en", "title": "Unsafe EN <b>title</b>"}
            },
            "rotations": [{"locale": "en", "from": "science-live-2-old", "to": "science-live-2-en", "code": "abc"}],
        },
        {
            "id": "art-draft",
            "handle": "science-draft",
            "title": "Draft should not render",
            "excerpt": "draft",
            "body": "<p>draft</p>",
            "published": False,
            "published_at": "2026-02-03T00:00:00+00:00",
            "translations": {},
        },
    ]))

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


# Scientific literature + FAQ API/SSR behavior
def test_scientific_literature_is_localized_with_published_links_meta_hreflang_and_single_h1(isolated_db):
    for loc in LOCALES:
        api = run(server.public_page("scientific-literature", locale=loc))["page"]
        assert api["slug"] == "scientific-literature"
        assert api["source_locale"] == loc
        assert api["seo"]["description"].strip()
        assert "data-testid=\"scientific-literature-intro\"" in api["html"]
        assert "scientific-literature-articles" in api["html"]
        assert "Draft should not render" not in api["html"]
        assert "<script>" not in api["html"]
        assert "/articles/science-live-2-old" not in api["html"]

        path = _route(loc, "/pages/scientific-literature")
        rendered = run(prerender.render(path, _host(loc)))
        assert rendered is not None
        html, status = rendered
        assert status == 200
        assert html.count("<h1") == 1
        assert 'name="robots" content="index, follow' in html
        assert "noindex" not in html
        assert f'<link rel="canonical" href="{prerender.url_for(loc, "/pages/scientific-literature")}"' in html
        assert html.count('rel="alternate" hreflang=') == 12

        hrefs = re.findall(r'<a[^>]+data-testid="scientific-article-[^"]+"[^>]+href="([^"]+)"', html)
        assert hrefs
        for href in hrefs[:2]:
            assert href.startswith("/") and not href.startswith("//")
            p = urlsplit(href).path
            target = run(prerender.render(p, _host(loc)))
            assert target is not None and target[1] == 200


def test_public_reads_generate_scientific_page_without_mongo_writes_and_unknown_slug_stays_404(isolated_db):
    before_count = run(isolated_db.pages.count_documents({}))
    out = run(server.public_page("scientific-literature", locale="pl"))["page"]
    after_count = run(isolated_db.pages.count_documents({}))
    assert out["html"] and out["title"]
    assert before_count == after_count

    with pytest.raises(server.HTTPException) as exc:
        run(server.public_page("unknown-scientific-slug", locale="pl"))
    assert exc.value.status_code == 404


def test_rotated_original_slug_stays_404_even_with_pub_slug_only_and_empty_markup(isolated_db):
    run(isolated_db.pages.insert_one({
        "id": "sci-ro",
        "slug": "scientific-literature",
        "locale": "ro",
        "title": "",
        "html": "<p><br></p>",
        "faq_items": [],
        "pub_slug": "scientific-literature-ro-live",
        "updated_at": "2026-02-01T00:00:00+00:00",
    }))

    with pytest.raises(server.HTTPException) as exc:
        run(server.public_page("scientific-literature", locale="ro"))
    assert exc.value.status_code == 404

    moved = run(server.public_page("scientific-literature-ro-live", locale="ro"))["page"]
    assert moved["slug"] == "scientific-literature"
    assert "scientific-literature-intro" in moved["html"]


def test_nonempty_owner_scientific_copy_and_explicit_seo_are_preserved(isolated_db):
    owner_html = "<p>Owner curated scientific copy</p>"
    run(isolated_db.pages.insert_one({
        "id": "sci-en-owner",
        "slug": "scientific-literature",
        "locale": "en",
        "title": "Owner EN literature",
        "html": owner_html,
        "faq_items": [],
        "seo_title": "Owner SEO title",
        "seo_description": "Owner SEO description",
        "updated_at": "2026-02-01T00:00:00+00:00",
    }))

    page = run(server.public_page("scientific-literature", locale="en"))["page"]
    assert page["title"] == "Owner EN literature"
    assert page["html"] == owner_html
    assert page["seo_title"] == "Owner SEO title"
    assert page["seo_description"] == "Owner SEO description"


def test_english_faq_fallback_and_preservation_rules(isolated_db):
    fallback = run(server.public_page("faq", locale="en"))["page"]
    assert fallback["source_locale"] == "en"
    assert fallback["seo"]["description"].strip()
    assert len(fallback["faq_items"]) >= 4

    custom_items = [{"q": "Custom q1", "a": "Custom a1"}, {"q": "Custom q2", "a": "Custom a2"}]
    run(isolated_db.pages.update_one(
        {"slug": "faq", "locale": "en"},
        {"$set": {"title": "EN FAQ custom", "html": "&nbsp;\u200b<p><br></p>", "faq_items": custom_items,
                  "seo_title": "", "seo_description": "", "updated_at": "2026-02-01T00:00:00+00:00"}},
        upsert=True,
    ))
    preserved_items = run(server.public_page("faq", locale="en"))["page"]
    assert preserved_items["title"] == "EN FAQ custom"
    assert preserved_items["faq_items"] == custom_items
    assert preserved_items["html"] == ""
    assert preserved_items["seo"]["description"] == FAQ_SEO_FALLBACK

    run(isolated_db.pages.update_one(
        {"slug": "faq", "locale": "en"},
        {"$set": {"title": "EN FAQ rich", "html": "<p>Owner authored EN FAQ body.</p>", "faq_items": custom_items,
                  "seo_description": "", "updated_at": "2026-02-02T00:00:00+00:00"}},
    ))
    preserved_html = run(server.public_page("faq", locale="en"))["page"]
    assert "Owner authored EN FAQ body." in preserved_html["html"]
    assert preserved_html["faq_items"] == custom_items
    assert preserved_html["seo"]["description"].strip()


def test_faq_ssr_has_visible_qa_and_valid_faqpage_jsonld(isolated_db):
    items = [
        {"q": "What is purity?", "a": "Purity is verified per batch."},
        {"q": "How to store?", "a": "Store in cool dark place."},
    ]
    run(isolated_db.pages.update_one(
        {"slug": "faq", "locale": "en"},
        {"$set": {"title": "FAQ EN", "html": "<p>FAQ intro</p>", "faq_items": items,
                  "seo_description": "", "updated_at": "2026-02-03T00:00:00+00:00"}},
        upsert=True,
    ))
    api = run(server.public_page("faq", locale="en"))["page"]

    rendered = run(prerender.render("/en/pages/faq", "purepeptide.eu"))
    assert rendered is not None and rendered[1] == 200
    html = rendered[0]
    for item in items:
        assert item["q"] in html
        assert item["a"] in html
    assert "data-testid=\"faq-prerender\"" in html

    desc_match = re.search(r'name="description" content="([^"]*)"', html)
    assert desc_match
    assert unescape(desc_match.group(1)).strip() == api["seo"]["description"]

    blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    parsed = [json.loads(block) for block in blocks]
    faq_nodes = [node for blob in parsed for node in blob.get("@graph", []) if node.get("@type") == "FAQPage"]
    assert faq_nodes and faq_nodes[0].get("mainEntity")


# Collections index URL in XML sitemap
def _locs(xml_text: str):
    return re.findall(r"<loc>([^<]+)</loc>", xml_text)


@pytest.mark.parametrize("host,expected", [
    ("purepeptide.bg", "https://purepeptide.bg/collections"),
    ("purepeptide.ro", "https://purepeptide.ro/collections"),
    ("purepeptide.gr", "https://purepeptide.gr/collections"),
])
def test_single_domain_collection_index_once_in_collections_sitemap_only(host, expected):
    collections_xml = requests.get(f"{API_LOCAL}/sitemap_collections_1.xml", headers={"Host": host}, timeout=60).text
    assert collections_xml.count(f"<loc>{expected}</loc>") == 1
    assert "/pages/collections" not in collections_xml
    assert "index.html" not in collections_xml

    for kind in ("products", "pages", "blogs"):
        xml = requests.get(f"{API_LOCAL}/sitemap_{kind}_1.xml", headers={"Host": host}, timeout=60).text
        assert f"<loc>{expected}</loc>" not in xml


@pytest.mark.parametrize("loc", ["en", "fr", "de", "cz", "hu", "pl", "sk", "si"])
def test_eu_collection_index_once_per_locale_and_nowhere_else(loc):
    expected = f"https://purepeptide.eu/{loc}/collections"
    col_xml = requests.get(f"{API_LOCAL}/sitemap_collections_{loc}_1.xml", headers={"Host": "purepeptide.eu"}, timeout=60).text
    assert col_xml.count(f"<loc>{expected}</loc>") == 1
    assert "/pages/collections" not in col_xml
    assert "index.html" not in col_xml

    pages_xml = requests.get(f"{API_LOCAL}/sitemap_pages_{loc}_1.xml", headers={"Host": "purepeptide.eu"}, timeout=60).text
    assert f"<loc>{expected}</loc>" not in pages_xml
