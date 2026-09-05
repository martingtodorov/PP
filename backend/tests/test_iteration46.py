"""Iteration 46 tests — SSR prerender for homepage + hard 404, COA image import."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") \
    else "https://shopify-migrate-3.preview.emergentagent.com"
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PW = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def _prerender(path: str) -> requests.Response:
    return requests.get(f"{API}/seo/prerender", params={"path": path}, timeout=30)


# ---------------- Homepage prerender ----------------

class TestHomepagePrerender:
    def test_home_200(self):
        r = _prerender("/")
        assert r.status_code == 200
        html = r.text
        # exactly one h1
        assert html.lower().count("<h1") == 1, f"h1 count wrong: {html.lower().count('<h1')}"
        assert '<link rel="canonical"' in html or "<link rel='canonical'" in html
        assert "<title>" in html
        assert 'name="description"' in html
        assert "hreflang" in html
        # JSON-LD types
        for t in ["Organization", "WebSite", "ItemList"]:
            assert t in html, f"missing @type {t} in homepage JSON-LD"


# ---------------- Hard 404 for missing content ----------------

@pytest.mark.parametrize("path", [
    "/products/does-not-exist-xyz",
    "/collections/nope-xyz",
    "/articles/nope-xyz",
    "/pages/nope-xyz",
])
def test_hard_404(path):
    r = _prerender(path)
    assert r.status_code == 404, f"{path} -> {r.status_code} (soft 200 regression)"
    assert "noindex" in r.text.lower(), f"{path} missing robots noindex"


# ---------------- Real product still 200 ----------------

@pytest.mark.parametrize("handle", ["sermorelin", "bpc-157-5"])
def test_real_product_200(handle):
    r = _prerender(f"/products/{handle}")
    assert r.status_code == 200, f"/products/{handle} -> {r.status_code}"
    assert "<h1" in r.text
    assert '"Product"' in r.text or "'Product'" in r.text


def test_locale_prefix_canonical_on_eu():
    r = _prerender("/en/products/bpc-157-5")
    assert r.status_code == 200
    assert "hreflang" in r.text
    # canonical must be on .eu origin for /en/
    import re as _re
    m = _re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', r.text)
    assert m, "no canonical link"
    assert "purepeptide.eu" in m.group(1), f"canonical not on .eu: {m.group(1)}"


# ---------------- Private routes: 200 shell ----------------

@pytest.mark.parametrize("path", ["/cart", "/checkout", "/track", "/admin"])
def test_private_routes_200_shell(path):
    r = _prerender(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}"


# ---------------- COA import auth ----------------

def test_coa_import_requires_admin():
    r = requests.post(f"{API}/admin/import/coa-images", timeout=15)
    assert r.status_code in (401, 403), f"unauth got {r.status_code}"


# ---------------- COA import dry_run ----------------

class TestCOAImport:
    def test_dry_run(self, admin_session):
        r = admin_session.post(f"{API}/admin/import/coa-images", params={"dry_run": "true"}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["scanned"] == 22, f"scanned={data['scanned']} expected 22"
        assert data.get("failed") == [] or len(data.get("failed", [])) == 0, f"failed: {data.get('failed')}"
        assert data.get("dry_run") is True

    def test_idempotent_real_run(self, admin_session):
        # already run once by main agent — second call should skip everything
        r = admin_session.post(f"{API}/admin/import/coa-images", timeout=180)
        assert r.status_code == 200
        d = r.json()
        assert d["scanned"] == 22
        assert len(d.get("added", [])) == 0, f"expected added=0 (idempotent), got {len(d['added'])}"
        assert len(d.get("skipped", [])) == 22, f"expected skipped=22, got {len(d.get('skipped', []))}"

    def test_coa_image_is_last_in_gallery(self, admin_session):
        for handle in ["sermorelin", "bpc-157-5"]:
            r = requests.get(f"{API}/products/{handle}", timeout=15)
            assert r.status_code == 200, f"{handle} -> {r.status_code}"
            p = r.json().get("product", r.json())
            imgs = p.get("images") or []
            coa = p.get("coa_image")
            assert coa, f"{handle} has no coa_image"
            assert imgs and imgs[-1] == coa, f"{handle}: coa {coa} not last in images {imgs[-3:]}"
            # main image unchanged (should not equal coa)
            main = p.get("image") or (imgs[0] if imgs else None)
            assert main and main != coa, f"{handle}: main image equals COA (main={main})"

    def test_coa_file_serves(self, admin_session):
        r = requests.get(f"{API}/products/sermorelin", timeout=15)
        coa = r.json().get("product", r.json()).get("coa_image")
        assert coa
        # coa is relative like /api/files/...
        url = coa if coa.startswith("http") else BASE + coa
        img = requests.get(url, timeout=30)
        assert img.status_code == 200, f"COA file {url} -> {img.status_code}"
        ctype = img.headers.get("content-type", "")
        assert "image" in ctype or "octet" in ctype or "pdf" in ctype, f"COA content-type={ctype}"
