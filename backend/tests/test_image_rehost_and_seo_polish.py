"""Nothing may be served from someone else's domain, and two cosmetic SEO defects.

The Janoshik lab reports were still hot-linked from the old Shopify store (etb7zb-gy.myshopify.com)
in both <img> tags and the JSON-LD `image` array — the day that store lapses, 14 products lose
their proof images. og:locale for English was a bare "en", and one product title had no space
before the pipe.
"""
import os

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import prerender                          # noqa: E402
import server                             # noqa: E402

BASE = "http://localhost:8001"
SHOPIFY_IMG = ("https://etb7zb-gy.myshopify.com/cdn/shop/files/Test_Report_Sermorelin.png"
               "?v=1776971696&width=3840")
HANDLE = "rehost-test-product"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture
def external_product(db):
    db.products.delete_many({"handle": HANDLE})
    db.products.insert_one({
        "id": HANDLE, "handle": HANDLE, "title": "Rehost test", "active": False,
        "image": SHOPIFY_IMG, "images": [SHOPIFY_IMG],
        "description": f'<p>Анализ <img src="{SHOPIFY_IMG}"></p>',
        "variants": [{"name": "5mg", "price_eur": 10.0, "stock": 1, "sku": "X"}],
    })
    yield
    db.products.delete_many({"handle": HANDLE})


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "admin@purepeptide.bg", "password": "Admin@PurePeptide2026"}, timeout=20)
    assert r.status_code == 200, r.text[:200]
    return s


def test_only_off_site_pictures_are_adopted():
    assert server._is_external_image(SHOPIFY_IMG)
    assert server._is_external_image("https://cdn.shopify.com/s/files/1/x.png")
    assert server._is_external_image("https://example.com/photo.jpg")
    assert not server._is_external_image("/api/files/import/abc.png")
    assert not server._is_external_image("https://purepeptide.bg/api/files/import/abc.png")
    assert not server._is_external_image("https://purepeptide.eu/en/products/sermorelin")


def test_a_dry_run_reports_without_touching_the_data(admin, external_product, db):
    r = admin.post(f"{BASE}/api/admin/media/rehost?dry_run=true", timeout=180)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data["dry_run"] is True and data["documents_changed"] >= 1
    assert db.products.find_one({"handle": HANDLE})["images"] == [SHOPIFY_IMG]


def test_rehosting_rewrites_the_gallery_the_main_image_and_the_html(admin, external_product, db):
    r = admin.post(f"{BASE}/api/admin/media/rehost", timeout=180)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["failed"] == []
    doc = db.products.find_one({"handle": HANDLE})
    assert doc["images"][0].startswith("/api/files/")
    assert doc["image"].startswith("/api/files/")
    assert "myshopify" not in doc["description"] and "/api/files/" in doc["description"]
    # and the copy really is readable from our own storage
    served = requests.get(f"{BASE}{doc['images'][0]}", timeout=60)
    assert served.status_code == 200 and served.headers["content-type"].startswith("image/")


def test_nothing_off_site_is_left_anywhere(admin, db):
    admin.post(f"{BASE}/api/admin/media/rehost", timeout=180)
    for coll in ("products", "collections_cat", "articles", "pages"):
        left = db[coll].count_documents({"$or": [
            {"images": {"$elemMatch": {"$regex": "shopify"}}},
            {"image": {"$regex": "shopify"}},
            {"description": {"$regex": "cdn/shop"}},
            {"html": {"$regex": "cdn/shop"}},
        ]})
        assert left == 0, coll


def test_an_image_pasted_as_a_link_in_the_admin_is_downloaded():
    src = open(os.path.join(os.path.dirname(__file__), "..", "server.py"), encoding="utf-8").read()
    for call in ("adopt_external_images(payload.model_dump())",
                 "adopt_external_images(changes)",
                 "adopt_external_images(payload.value)",
                 "adopt_external_images(payload.html)"):
        assert call in src, call


def test_english_declares_a_territory_in_og_locale():
    assert prerender._og_locale("en") == "en_GB"
    assert prerender._og_locale("fr") == "fr_FR"
    assert prerender._og_locale("cz") == "cs_CZ"
    head = prerender._head("en", "", "T", "D", "")
    assert 'og:locale" content="en_GB"' in head
    # hreflang must stay the generic English tag
    assert 'hreflang="en"' in head


def test_the_pipe_in_a_title_always_has_its_spaces():
    assert prerender._tidy("CJC-1295 - аналог за секреция на GH| цена").endswith("GH | цена")
    assert prerender._tidy("A |B") == "A | B"
    assert prerender._tidy("A | B") == "A | B"
    r = requests.get(f"{BASE}/api/seo/prerender?path=/products/acjc-1295", timeout=30)
    assert "GH | цена" in r.text
