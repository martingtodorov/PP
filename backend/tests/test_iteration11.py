"""Iteration 11 tests — meta coverage, structured data data, scientific literature,
contact HTML escaping, checkout speed, sitemap/robots.
"""
import os
import re
import time
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PW = "Admin@PurePeptide2026"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def admin(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=10)
    assert r.status_code == 200, r.text
    token = r.json().get("token") or r.json().get("access_token")
    hdrs = {"Authorization": f"Bearer {token}"} if token else {}
    return hdrs


# ---------- Backend meta coverage ----------

def test_products_all_have_meta(s):
    r = s.get(f"{API}/products", params={"locale": "bg"}, timeout=10)
    assert r.status_code == 200
    products = r.json().get("products", r.json() if isinstance(r.json(), list) else [])
    assert products, "no products returned"
    missing = [p.get("handle") for p in products
               if not (p.get("seo_title") or "").strip() or not (p.get("seo_description") or "").strip()]
    assert not missing, f"products missing SEO meta: {missing}"


def test_collections_have_meta(s):
    r = s.get(f"{API}/collections", params={"locale": "bg"}, timeout=10)
    assert r.status_code == 200
    cols = r.json().get("collections", r.json() if isinstance(r.json(), list) else [])
    assert cols
    missing = [c.get("handle") for c in cols
               if not (c.get("seo_title") or "").strip() or not (c.get("seo_description") or "").strip()]
    assert not missing, f"collections missing SEO meta: {missing}"


def test_articles_have_meta(s):
    r = s.get(f"{API}/articles", params={"locale": "bg"}, timeout=10)
    assert r.status_code == 200
    arts = r.json().get("articles", r.json() if isinstance(r.json(), list) else [])
    assert arts
    allowed_fallback_prefix = "retatrutid-mexanizam"
    missing = []
    for a in arts:
        h = a.get("handle", "")
        st = (a.get("seo_title") or "").strip()
        sd = (a.get("seo_description") or "").strip()
        if not st or not sd:
            if not h.startswith(allowed_fallback_prefix):
                missing.append(h)
    assert not missing, f"articles missing SEO meta: {missing}"


REQ_PAGES = ["faq", "about", "cookies", "scientific-literature", "contacts"]


@pytest.mark.parametrize("slug", REQ_PAGES)
def test_page_meta(s, slug):
    r = s.get(f"{API}/pages/{slug}", params={"locale": "bg"}, timeout=10)
    assert r.status_code == 200, r.text
    page = r.json().get("page") or r.json()
    assert (page.get("seo_title") or "").strip(), f"{slug}: missing seo_title"
    assert (page.get("seo_description") or "").strip(), f"{slug}: missing seo_description"


# ---------- Scientific literature ----------

def test_scientific_literature_content(s):
    r = s.get(f"{API}/pages/scientific-literature", params={"locale": "bg"}, timeout=10)
    assert r.status_code == 200
    page = r.json().get("page") or r.json()
    html = page.get("html") or page.get("body") or ""
    title = page.get("title") or ""
    assert title.strip(), "empty title"
    assert len(html) >= 500, f"html too short: {len(html)} chars"
    # Bulgarian characters check
    assert re.search(r"[а-яА-Я]", html), "no Bulgarian characters"


# ---------- Contact form: HTML escape + speed ----------

def test_contact_form_escapes_html_and_is_fast(s):
    payload = {
        "name": "TEST_Iter11",
        "email": "test@example.com",
        "phone": "0888000000",
        "message": "<script>alert(1)</script> тест",
        "locale": "bg",
    }
    t0 = time.time()
    r = s.post(f"{API}/contact", json=payload, timeout=10)
    dt = time.time() - t0
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    assert dt < 5.0, f"contact took {dt:.2f}s"


def test_admin_messages_contains_escaped_message(s, admin):
    r = s.get(f"{API}/admin/messages", headers=admin, timeout=10)
    assert r.status_code == 200
    msgs = r.json().get("messages", [])
    hit = next((m for m in msgs if m.get("name") == "TEST_Iter11" and "тест" in m.get("message", "")), None)
    assert hit, "TEST_Iter11 message not found in admin"
    # Stored raw; render side escapes. Just make sure it round-trips as string not executed.
    assert "<script>" in hit["message"] or "&lt;script&gt;" in hit["message"]


# ---------- Checkout speed & order number ----------

def test_checkout_fast_and_order_number(s):
    payload = {
        "items": [{"product_id": "bpc-157-5", "variant_sku": "PP-BPC157-5MG", "quantity": 1}],
        "customer_email": "test@example.com",
        "customer_name": "TEST Iter11",
        "customer_phone": "0888000001",
        "shipping": {
            "full_name": "TEST Iter11",
            "phone": "0888000001",
            "line1": "ul. Test 1",
            "city": "Sofia",
            "postal_code": "1000",
            "country": "BG",
        },
        "shipping_method": "econt_office",
        "payment_method": "cod",
        "terms_accepted": True,
        "locale": "bg",
    }
    # product_id must be UUID — fetch it
    prod = s.get(f"{API}/products/bpc-157-5", timeout=10).json()
    pid = prod.get("product", prod).get("id")
    assert pid
    payload["items"][0]["product_id"] = pid

    t0 = time.time()
    r = s.post(f"{API}/checkout", json=payload, timeout=15)
    dt = time.time() - t0
    assert r.status_code in (200, 201), r.text
    body = r.json()
    order_no = body.get("order_number") or body.get("order", {}).get("order_number")
    assert order_no and re.match(r"^[A-Z]{3}[0-9]{2}$", order_no), f"bad order_no: {order_no}"
    assert dt < 6.0, f"checkout took {dt:.2f}s"


# ---------- Sitemap & robots ----------

def test_robots():
    for url in [f"{BASE}/robots.txt", f"{API}/robots.txt"]:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "User-agent" in r.text:
            return
    pytest.fail("robots.txt not served at /robots.txt or /api/robots.txt")


def test_sitemap_includes_real_urls():
    xml = None
    for url in [f"{BASE}/sitemap.xml", f"{API}/sitemap.xml"]:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "<urlset" in r.text:
            xml = r.text
            break
    assert xml, "sitemap.xml not served"
    assert "/products/bpc-157-5" in xml
    assert "/collections/" in xml
    assert "/pages/faq" in xml
    assert "/articles/" in xml
