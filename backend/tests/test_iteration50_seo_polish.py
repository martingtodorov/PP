"""Iteration 50 — SEO polish acceptance suite.

Covers:
- robots.txt: single "User-agent: *" group + Content-Signal + own-domain-only sitemaps
- Homepage title/description per locale (owner's exact copy), <= 60 chars
- HTML sitemap prerender pages (200 vs 404 for unknown slug), per-locale labels
- Organization JSON-LD shape (logo ImageObject w/h, image, email, contactPoint EU CS)
- og:locale en_GB for English while hreflang stays "en"
- Image-adopt on save endpoints (product create/update stores /api/files/ locally)
"""
import json
import os
import re

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "http://localhost:8001"
SHOPIFY_IMG = ("https://etb7zb-gy.myshopify.com/cdn/shop/files/"
               "Test_Report_Sermorelin.png?v=1776971696&width=3840")


@pytest.fixture(scope="module")
def db():
    c = MongoClient(os.environ["MONGO_URL"])
    yield c[os.environ["DB_NAME"]]
    c.close()


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": "admin@purepeptide.bg",
                     "password": "Admin@PurePeptide2026"}, timeout=20)
    assert r.status_code == 200, r.text[:200]
    return s


# ---------- robots.txt ----------
class TestRobots:
    HOSTS = ["purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr"]

    @pytest.mark.parametrize("host", HOSTS)
    def test_single_user_agent_group_with_content_signal(self, host):
        r = requests.get(f"{BASE}/api/robots.txt", headers={"Host": host}, timeout=15)
        assert r.status_code == 200
        body = r.text
        ua_lines = [ln for ln in body.splitlines() if ln.lower().startswith("user-agent:")]
        assert ua_lines == ["User-agent: *"], f"{host}: {ua_lines}"
        assert "Content-Signal: search=yes, ai-input=yes, ai-train=yes, use=full" in body
        assert "Allow: /" in body
        for p in ("/admin", "/checkout", "/cart", "/account"):
            assert f"Disallow: {p}" in body

    @pytest.mark.parametrize("host,expect_domain", [
        ("purepeptide.bg", "purepeptide.bg"),
        ("purepeptide.ro", "purepeptide.ro"),
        ("purepeptide.gr", "purepeptide.gr"),
        ("purepeptide.eu", "purepeptide.eu"),
    ])
    def test_only_own_domain_sitemaps_listed(self, host, expect_domain):
        r = requests.get(f"{BASE}/api/robots.txt", headers={"Host": host}, timeout=15)
        sitemaps = [ln for ln in r.text.splitlines() if ln.startswith("Sitemap:")]
        assert sitemaps, f"no sitemaps for {host}"
        for sm in sitemaps:
            assert expect_domain in sm, f"foreign domain in {host}: {sm}"
        # no cross-pollination
        others = {"purepeptide.bg", "purepeptide.eu", "purepeptide.ro",
                  "purepeptide.gr"} - {expect_domain}
        for other in others:
            assert not any(other in sm for sm in sitemaps)


# ---------- Homepage title/description per locale ----------
class TestHomepageMeta:
    # (path, host, needle_in_title, must_be_le_60)
    LOCALE_TITLE_NEEDLE = {
        "bg":  ("/",     "purepeptide.bg", "България"),
        "en":  ("/en/",  "purepeptide.eu", "Europe"),
        "cz":  ("/cz/",  "purepeptide.eu", "Česku"),
        "ro":  ("/",     "purepeptide.ro", "România"),
        "gr":  ("/",     "purepeptide.gr", "Ελλάδα"),
        "pl":  ("/pl/",  "purepeptide.eu", "Polsce"),
        "sk":  ("/sk/",  "purepeptide.eu", "Slovensku"),
        "si":  ("/si/",  "purepeptide.eu", "Sloveniji"),
        "hu":  ("/hu/",  "purepeptide.eu", "Magyarországon"),
        "de":  ("/de/",  "purepeptide.eu", "Deutschland"),
        "fr":  ("/fr/",  "purepeptide.eu", "France"),
    }

    @pytest.mark.parametrize("loc", list(LOCALE_TITLE_NEEDLE.keys()))
    def test_homepage_title_names_the_local_market_and_is_short(self, loc):
        path, host, needle = self.LOCALE_TITLE_NEEDLE[loc]
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": path},
                         headers={"Host": host}, timeout=20)
        assert r.status_code == 200
        m = re.search(r"<title>([^<]+)</title>", r.text)
        assert m, f"no title for {loc}"
        title = m.group(1)
        assert needle in title, f"{loc}: {title!r} missing {needle!r}"
        assert len(title) <= 60, f"{loc}: title {len(title)} chars > 60: {title!r}"

    @pytest.mark.parametrize("loc,path,host,needle_desc", [
        ("bg", "/",    "purepeptide.bg", "Janoshik Labs"),
        ("en", "/en/", "purepeptide.eu", "Janoshik Labs"),
        ("cz", "/cz/", "purepeptide.eu", "Janoshik Labs"),
        ("ro", "/",    "purepeptide.ro", "Janoshik Labs"),
        ("de", "/de/", "purepeptide.eu", "Janoshik Labs"),
    ])
    def test_meta_description_is_the_janoshik_lyophilised_text(
            self, loc, path, host, needle_desc):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": path},
                         headers={"Host": host}, timeout=20)
        m = re.search(r'name="description"\s+content="([^"]+)"', r.text)
        assert m, f"no description for {loc}"
        assert needle_desc in m.group(1)


# ---------- HTML sitemap prerender ----------
class TestHtmlSitemap:
    @pytest.mark.parametrize("slug,expect", [
        ("html-sitemap", 200),
        ("html-sitemap-products", 200),
        ("html-sitemap-collections", 200),
        ("html-sitemap-blogs", 200),
        ("html-sitemap-articles", 200),
        ("html-sitemap-pages", 200),
        ("html-sitemap-nope", 404),
    ])
    def test_html_sitemap_status(self, slug, expect):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": f"/pages/{slug}"},
                         headers={"Host": "purepeptide.bg"}, timeout=20)
        assert r.status_code == expect, f"{slug}: {r.status_code}"

    def test_html_sitemap_has_h1_and_links(self):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": "/pages/html-sitemap"},
                         headers={"Host": "purepeptide.bg"}, timeout=20)
        assert "<h1" in r.text and "HTML sitemap" in r.text
        # has product & article links
        assert "/products/" in r.text
        assert "/articles/" in r.text or "/blogs/" in r.text

    def test_czech_html_sitemap_uses_czech_labels(self):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": "/cz/pages/html-sitemap"},
                         headers={"Host": "purepeptide.eu"}, timeout=20)
        assert r.status_code == 200
        # Czech word for products/articles/pages should appear
        assert any(w in r.text.lower()
                   for w in ("produkty", "články", "stránky", "kategorie"))


# ---------- Organization JSON-LD ----------
class TestOrganizationLd:
    def _org(self, path, host="purepeptide.bg"):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": path},
                         headers={"Host": host}, timeout=20)
        for m in re.finditer(
                r'<script type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.S):
            data = json.loads(m.group(1))
            graph = data.get("@graph", [data]) if isinstance(data, dict) else data
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "Organization":
                    return node
        return None

    @pytest.mark.parametrize("path", [
        "/", "/products/sermorelin", "/collections/2all-the-peptides-1-phc",
        "/articles/tesamorelin", "/pages/faq", "/pages/html-sitemap",
    ])
    def test_organization_shape_on_all_route_kinds(self, path):
        org = self._org(path)
        assert org is not None, f"no Organization on {path}"
        # logo as ImageObject with width/height
        logo = org.get("logo")
        assert isinstance(logo, dict) and logo.get("@type") == "ImageObject"
        assert isinstance(logo.get("width"), int) and logo["width"] > 0
        assert isinstance(logo.get("height"), int) and logo["height"] > 0
        assert org.get("image"), "image missing"
        assert org.get("email"), "email missing"
        cp = org.get("contactPoint")
        assert isinstance(cp, dict)
        assert cp.get("contactType") == "customer service"
        assert cp.get("areaServed") == "EU"


# ---------- og:locale / hreflang / pipe spacing ----------
class TestLocalePolish:
    def test_english_og_locale_is_en_GB(self):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": "/en/"},
                         headers={"Host": "purepeptide.eu"}, timeout=20)
        assert 'property="og:locale" content="en_GB"' in r.text
        assert 'hreflang="en"' in r.text  # bare "en" for x-default English

    @pytest.mark.parametrize("path,host,tag", [
        ("/",    "purepeptide.bg", "bg_BG"),
        ("/cz/", "purepeptide.eu", "cs_CZ"),
        ("/fr/", "purepeptide.eu", "fr_FR"),
        ("/si/", "purepeptide.eu", "sl_SI"),
        ("/",    "purepeptide.gr", "el_GR"),
        ("/",    "purepeptide.ro", "ro_RO"),
    ])
    def test_other_locales_unchanged(self, path, host, tag):
        r = requests.get(f"{BASE}/api/seo/prerender",
                         params={"path": path},
                         headers={"Host": host}, timeout=20)
        assert f'property="og:locale" content="{tag}"' in r.text, tag


# ---------- Image adopt on save endpoints ----------
class TestAdoptOnSave:
    def test_creating_a_product_with_external_image_adopts_it(self, admin, db):
        handle = "TEST-adopt-create-50"
        db.products.delete_many({"handle": handle})
        try:
            payload = {
                "handle": handle, "title": "TEST adopt create",
                "active": False, "image": SHOPIFY_IMG, "images": [SHOPIFY_IMG],
                "description": f'<p><img src="{SHOPIFY_IMG}"></p>',
                "variants": [{"name": "5mg", "price_eur": 1.0,
                              "stock": 1, "sku": "TSTCR"}],
            }
            r = admin.post(f"{BASE}/api/admin/products", json=payload, timeout=90)
            assert r.status_code in (200, 201), r.text[:300]
            doc = db.products.find_one({"handle": handle})
            assert doc, "product not persisted"
            assert doc["image"].startswith("/api/files/"), doc["image"]
            assert all(i.startswith("/api/files/") for i in doc["images"])
            assert "myshopify" not in doc.get("description", "")
        finally:
            db.products.delete_many({"handle": handle})

    def test_updating_a_product_with_external_image_adopts_it(self, admin, db):
        handle = "TEST-adopt-update-50"
        db.products.delete_many({"handle": handle})
        try:
            create = admin.post(f"{BASE}/api/admin/products", json={
                "handle": handle, "title": "TEST adopt upd",
                "active": False, "images": [],
                "variants": [{"name": "5mg", "price_eur": 1.0,
                              "stock": 1, "sku": "TSTUP"}],
            }, timeout=60)
            assert create.status_code in (200, 201), create.text[:300]
            pid = (create.json().get("id")
                   or db.products.find_one({"handle": handle})["id"])
            r = admin.put(f"{BASE}/api/admin/products/{pid}",
                          json={"handle": handle, "title": "TEST adopt upd",
                                "active": False,
                                "image": SHOPIFY_IMG,
                                "images": [SHOPIFY_IMG],
                                "variants": [{"name": "5mg", "price_eur": 1.0,
                                              "stock": 1, "sku": "TSTUP"}]},
                          timeout=90)
            assert r.status_code == 200, r.text[:300]
            doc = db.products.find_one({"handle": handle})
            assert doc["image"].startswith("/api/files/"), doc["image"]
            assert all(i.startswith("/api/files/") for i in doc["images"])
        finally:
            db.products.delete_many({"handle": handle})


# ---------- Rehost idempotency ----------
class TestRehostIdempotent:
    def test_second_run_is_a_noop(self, admin):
        # first run
        admin.post(f"{BASE}/api/admin/media/rehost", timeout=180)
        r = admin.post(f"{BASE}/api/admin/media/rehost", timeout=180)
        assert r.status_code == 200
        data = r.json()
        assert data.get("failed", []) == []
        # After the exhaustive first run, second run should touch nothing.
        assert data.get("documents_changed", 0) == 0, data
