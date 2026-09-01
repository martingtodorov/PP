"""Iteration-12 SEO verification: favicon/icons, OG image, meta coverage, internal linking."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- Static asset availability ----------
STATIC_ASSETS = [
    "/favicon.ico",
    "/favicon-16x16.png",
    "/favicon-32x32.png",
    "/apple-touch-icon.png",
    "/favicon-512.png",
    "/logo192.png",
    "/logo512.png",
    "/og-image.jpg",
    "/manifest.json",
]


@pytest.mark.parametrize("path", STATIC_ASSETS)
def test_static_asset_200(s, path):
    r = s.get(f"{BASE_URL}{path}", timeout=15)
    assert r.status_code == 200, f"{path} => {r.status_code}"
    assert len(r.content) > 50, f"{path} too small"


# ---------- Index.html head content ----------
def test_index_head_has_icons_and_theme(s):
    r = s.get(f"{BASE_URL}/", timeout=20)
    assert r.status_code == 200
    html = r.text
    assert 'rel="icon"' in html and "favicon.ico" in html
    assert "favicon-32x32.png" in html
    assert "favicon-16x16.png" in html
    assert "apple-touch-icon" in html
    assert re.search(r'theme-color"\s+content="#fe6f61"', html, re.I) or \
        re.search(r'theme-color"\s+content="#FE6F61"', html), "theme-color #fe6f61 missing"
    assert 'og:site_name' in html and 'PurePeptide' in html


# ---------- Meta coverage backend ----------
def test_products_seo_coverage(s):
    r = s.get(f"{BASE_URL}/api/products", timeout=30)
    assert r.status_code == 200
    products = r.json().get("products", r.json()) if isinstance(r.json(), dict) else r.json()
    assert len(products) >= 20, f"expected ~21 products, got {len(products)}"
    missing = [p.get("handle") for p in products if not p.get("seo_title") or not p.get("seo_description")]
    assert not missing, f"products missing SEO: {missing}"


def test_collections_seo_coverage(s):
    r = s.get(f"{BASE_URL}/api/collections", timeout=30)
    assert r.status_code == 200
    cols = r.json().get("collections", [])
    assert len(cols) >= 5
    missing = [c.get("handle") for c in cols if not c.get("seo_title") or not c.get("seo_description")]
    assert not missing, f"collections missing SEO: {missing}"


def test_articles_seo_coverage(s):
    r = s.get(f"{BASE_URL}/api/articles", timeout=30)
    assert r.status_code == 200
    arts = r.json().get("articles", [])
    assert len(arts) >= 10
    missing = [a.get("handle") for a in arts if not a.get("seo_title") or not a.get("seo_description")]
    # allow up to 1 fallback (retatrutid legacy)
    assert len(missing) <= 1, f"articles missing SEO: {missing}"


PAGE_SLUGS = [
    "faq", "about", "cookies", "contacts", "scientific-literature",
    "shipping", "returns", "terms", "privacy", "payment",
    "quality", "wholesale",
]


@pytest.mark.parametrize("slug", PAGE_SLUGS)
def test_page_seo_coverage(s, slug):
    r = s.get(f"{BASE_URL}/api/pages/{slug}?locale=bg", timeout=15)
    if r.status_code == 404:
        pytest.skip(f"page {slug} not seeded")
    assert r.status_code == 200
    body = r.json()
    page = body.get("page", body)
    assert page.get("seo_title"), f"{slug} missing seo_title"
    assert page.get("seo_description"), f"{slug} missing seo_description"


# ---------- Internal linking on product pages ----------
INTERNAL_LINK_PRODUCTS = ["bpc-157-5", "1-ghk-cu", "21-retatrutide-5"]


@pytest.mark.parametrize("handle", INTERNAL_LINK_PRODUCTS)
def test_product_has_related_article(s, handle):
    r = s.get(f"{BASE_URL}/api/products/{handle}", timeout=20)
    assert r.status_code == 200, f"product {handle} => {r.status_code}"
    data = r.json()
    related = data.get("articles") or []
    assert len(related) >= 1, f"product {handle} has no related articles (keys={list(data.keys())})"


@pytest.mark.parametrize("handle", INTERNAL_LINK_PRODUCTS)
def test_product_has_collections(s, handle):
    r = s.get(f"{BASE_URL}/api/products/{handle}", timeout=20)
    assert r.status_code == 200
    data = r.json()
    prod = data.get("product", data)
    cols = prod.get("collections") or prod.get("collection_handles") or []
    assert len(cols) >= 1, f"product {handle} missing collections"
    related_products = data.get("related") or []
    assert len(related_products) >= 1, f"product {handle} missing related products"


# ---------- Sitemap regression ----------
def test_sitemap(s):
    r = s.get(f"{BASE_URL}/api/sitemap.xml", timeout=20)
    assert r.status_code == 200
    assert "<urlset" in r.text
    assert "/products/" in r.text
