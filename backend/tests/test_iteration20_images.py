"""Iteration-20 backend tests: image WebP/JPEG negotiation, site media in storage,
CMS content free of shopify CDN URLs, and courier config regression."""
import os
import re
import time

import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def a_product_image_path(api):
    r = api.get(f"{BASE_URL}/api/products", params={"limit": 20})
    assert r.status_code == 200
    products = r.json().get("products", r.json() if isinstance(r.json(), list) else [])
    for p in products:
        for img in (p.get("images") or []):
            src = img if isinstance(img, str) else (img.get("src") or img.get("url") or "")
            m = re.search(r"/api/files/(.+?)(?:\?|$)", src)
            if m:
                return m.group(1)
    pytest.skip("No /api/files/... product image found")


# ---------- Image serving ----------
class TestImageServing:
    def test_webp_negotiation(self, api, a_product_image_path):
        r = api.get(f"{BASE_URL}/api/files/{a_product_image_path}",
                    headers={"Accept": "image/webp,image/*,*/*"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/webp"
        assert "Accept" in r.headers.get("Vary", "")
        assert len(r.content) > 100

    def test_jpeg_fallback(self, api, a_product_image_path):
        r = api.get(f"{BASE_URL}/api/files/{a_product_image_path}",
                    headers={"Accept": "image/jpeg,*/*"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/jpeg"
        assert "Accept" in r.headers.get("Vary", "")

    def test_width_param_smaller(self, api, a_product_image_path):
        full = api.get(f"{BASE_URL}/api/files/{a_product_image_path}",
                       headers={"Accept": "image/webp"})
        resized = api.get(f"{BASE_URL}/api/files/{a_product_image_path}",
                          params={"w": 600},
                          headers={"Accept": "image/webp"})
        assert full.status_code == 200 and resized.status_code == 200
        assert len(resized.content) < len(full.content), (
            f"resized {len(resized.content)} not smaller than full {len(full.content)}"
        )

    def test_disk_cache_is_fast(self, api, a_product_image_path):
        # warm
        api.get(f"{BASE_URL}/api/files/{a_product_image_path}",
                params={"w": 600}, headers={"Accept": "image/webp"})
        t0 = time.time()
        r = api.get(f"{BASE_URL}/api/files/{a_product_image_path}",
                    params={"w": 600}, headers={"Accept": "image/webp"})
        elapsed = time.time() - t0
        assert r.status_code == 200
        assert elapsed < 2.0, f"cached image took {elapsed:.2f}s"


# ---------- Site media (hero) ----------
class TestSiteMedia:
    def test_hero_lives_in_storage(self, api):
        r = api.get(f"{BASE_URL}/api/settings")
        assert r.status_code == 200
        media = (r.json() or {}).get("media", {}) or {}
        hero = media.get("hero") or ""
        assert hero, "settings.media.hero is empty"
        assert "/api/files/" in hero, f"hero not in storage: {hero}"
        # And it must actually load
        img = api.get(hero if hero.startswith("http") else f"{BASE_URL}{hero}",
                      headers={"Accept": "image/webp"})
        assert img.status_code == 200
        assert img.headers["content-type"].startswith("image/")


# ---------- CMS content free of Shopify CDN ----------
class TestCmsShopifyFree:
    def test_chemical_analysis_no_shopify_cdn(self, api):
        r = api.get(f"{BASE_URL}/api/pages/chemical-analysis")
        assert r.status_code == 200
        html = (r.json() or {}).get("html", "")
        assert "cdn.shopify.com" not in html, "shopify cdn still referenced"
        # images in that page must load from /api/files/
        srcs = re.findall(r'<img[^>]+src="([^"]+)"', html)
        for src in srcs[:5]:
            full = src if src.startswith("http") else f"{BASE_URL}{src}"
            img = api.get(full, headers={"Accept": "image/webp"})
            assert img.status_code == 200, f"image {src} -> {img.status_code}"


# ---------- Courier regression ----------
class TestCourierRegression:
    def test_bg_config_has_econt(self, api):
        r = api.get(f"{BASE_URL}/api/nextcart/config", params={"country": "BG"})
        assert r.status_code == 200
        d = r.json()
        assert any(m.get("provider_key") == "econt" for m in d.get("delivery_methods", []))
        assert (d.get("payment_methods") or [{}])[0].get("key") == "cod"

    def test_countries_list(self, api):
        r = api.get(f"{BASE_URL}/api/nextcart/countries")
        assert r.status_code == 200
        d = r.json()
        assert d.get("default") == "BG"
        isos = [c["iso2"] for c in d.get("countries", [])]
        for c in ("BG", "RO", "GR", "DE"):
            assert c in isos

    def test_bank_details(self, api):
        r = api.get(f"{BASE_URL}/api/bank-details")
        assert r.status_code == 200
        d = r.json()
        assert d.get("iban") == "BG61STSA93000032400775"
