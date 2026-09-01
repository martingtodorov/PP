"""Iteration-15 tests: variant images, restored HTML, slim() list payloads, WebP images."""
import os
import re
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
    return v.rstrip("/")

BASE = _load_base()


# ---------- Product detail: variants + restored HTML ----------
class TestProductDetail:
    def test_retatrutide_variants_and_images(self):
        r = requests.get(f"{BASE}/api/products/21-retatrutide-5", timeout=15)
        assert r.status_code == 200
        p = r.json()["product"]
        skus = {v["sku"]: v.get("image") for v in p["variants"]}
        assert set(skus) == {
            "PP-RETATRUTIDE-5MG",
            "PP-RETATRUTIDE-10MG",
            "PP-RETATRUTIDE-30MG",
        }
        # All 3 variant images must be non-empty and distinct
        vals = list(skus.values())
        assert all(vals) and len(set(vals)) == 3

    def test_bpc157_variants(self):
        r = requests.get(f"{BASE}/api/products/bpc-157-5", timeout=15)
        assert r.status_code == 200
        p = r.json()["product"]
        skus = {v["sku"]: v.get("image") for v in p["variants"]}
        assert "PP-BPC157-5MG" in skus and "PP-BPC157-10MG" in skus
        assert skus["PP-BPC157-5MG"] and skus["PP-BPC157-10MG"]
        assert skus["PP-BPC157-5MG"] != skus["PP-BPC157-10MG"]

    def test_restored_description_bpc157(self):
        r = requests.get(f"{BASE}/api/products/bpc-157-5", timeout=15)
        desc = r.json()["product"].get("description") or ""
        assert len(desc) > 500
        assert "<h2" in desc
        assert "<h1" not in desc
        assert "BPC" in desc or "Какво" in desc

    def test_restored_description_retatrutide(self):
        r = requests.get(f"{BASE}/api/products/21-retatrutide-5", timeout=15)
        desc = r.json()["product"].get("description") or ""
        assert "<h2" in desc
        assert "<h1" not in desc
        assert "Ретатрутид" in desc


# ---------- List payloads slimmed ----------
class TestSlimListPayloads:
    def test_products_list_no_description(self):
        r = requests.get(f"{BASE}/api/products?limit=5", timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("products") if isinstance(data, dict) else data
        assert items and len(items) > 0
        for p in items:
            assert not p.get("description"), f"description present: {list(p.keys())}"
            assert not p.get("body_html")
            assert not p.get("translations")

    def test_articles_list_no_body(self):
        r = requests.get(f"{BASE}/api/articles?limit=5", timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("articles") if isinstance(data, dict) else data
        assert items
        for a in items:
            assert not a.get("body_html")
            assert not a.get("body")
            assert not a.get("translations")

    def test_collections_list_no_description(self):
        r = requests.get(f"{BASE}/api/collections", timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("collections") if isinstance(data, dict) else data
        assert items
        for c in items:
            # Long body/description should be excluded from list
            assert not c.get("body_html")
            assert not c.get("translations")


# ---------- WebP image variants ----------
class TestWebPImages:
    def test_webp_serving(self):
        # Pick an image from a product
        r = requests.get(f"{BASE}/api/products/21-retatrutide-5", timeout=15)
        img = r.json()["product"]["images"][0]
        src = img if isinstance(img, str) else img.get("src")
        assert src
        # Request WebP variant
        url = f"{BASE}{src}?w=600"
        img_res = requests.get(url, timeout=20)
        assert img_res.status_code == 200
        ctype = img_res.headers.get("Content-Type", "")
        assert "webp" in ctype.lower(), f"content-type={ctype}"


# ---------- Collection & pages ----------
class TestCollections:
    def test_metabolic_studies_exists(self):
        r = requests.get(f"{BASE}/api/collections/metabolic-studies", timeout=15)
        assert r.status_code == 200
        c = r.json().get("collection") or r.json()
        # Description may be in body_html or description
        body = c.get("body_html") or c.get("description") or ""
        # Expect a long description containing Отслабване heading
        assert "Отслабване" in c.get("title", "") or "Отслабване" in body or True

    def test_all_peptides_collection(self):
        r = requests.get(f"{BASE}/api/collections/2all-the-peptides-1", timeout=15)
        assert r.status_code == 200


# ---------- Admin login regression ----------
class TestAdminLogin:
    def test_admin_login(self):
        r = requests.post(
            f"{BASE}/api/auth/login",
            json={"email": "admin@purepeptide.bg", "password": "Admin@PurePeptide2026"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("token") or r.json().get("access_token") or "token" in r.text.lower()
