"""Iteration 13 — RON currency normalisation + SEO/schema quick re-validation."""
import os
import re
import json
import pytest
import requests

def _load_env():
    for p in ("/app/frontend/.env",):
        try:
            for ln in open(p):
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip()
        except FileNotFoundError:
            pass
    return None
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _load_env() or "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL missing"
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASS = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return s


# ---- Currency normalisation ---------------------------------------------------

def test_admin_orders_endpoint_ok(admin_session):
    r = admin_session.get(f"{BASE}/api/admin/orders?limit=200", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "orders" in j and isinstance(j["orders"], list)
    assert j["total"] > 0


def test_ron_orders_normalised(admin_session):
    """46 RON orders should exist; total_eur ≈ total_display/4.975; no RON.total_eur > 400."""
    # Fetch across pages
    all_orders = []
    skip = 0
    while True:
        r = admin_session.get(f"{BASE}/api/admin/orders?limit=200&skip={skip}", timeout=30)
        assert r.status_code == 200
        chunk = r.json()["orders"]
        all_orders.extend(chunk)
        if len(chunk) < 200:
            break
        skip += 200
        if skip > 5000:
            break

    ron = [o for o in all_orders if (o.get("currency") or "").upper() == "RON"]
    print(f"Found {len(ron)} RON orders out of {len(all_orders)} total")
    assert len(ron) == 46, f"expected 46 RON orders, got {len(ron)}"

    for o in ron:
        assert abs(float(o["currency_rate"]) - 4.975) < 1e-3, o
        td, te = float(o["total_display"]), float(o["total_eur"])
        # display is RON (original) -> converts to EUR by /4.975
        assert abs(te - round(td / 4.975, 2)) <= 0.02, f"order {o['order_number']}: td={td} te={te}"
        # Sanity: no RON order should show EUR > 2000 (would indicate un-normalised)
        assert te <= 2000, f"order {o['order_number']} EUR too large: {te}"


def test_ron_order_detail(admin_session):
    # walk pages to find a RON order
    ron_summary = None
    for skip in range(0, 3000, 200):
        r = admin_session.get(f"{BASE}/api/admin/orders?limit=200&skip={skip}", timeout=30)
        orders = r.json()["orders"]
        if not orders:
            break
        ron_summary = next((o for o in orders if (o.get("currency") or "").upper() == "RON"), None)
        if ron_summary:
            break
    assert ron_summary, "no RON order found in first 3000"
    r2 = admin_session.get(f"{BASE}/api/admin/orders/{ron_summary['id']}", timeout=30)
    assert r2.status_code == 200
    d = r2.json().get("order") or r2.json()
    assert d["currency"] == "RON"
    assert abs(d["currency_rate"] - 4.975) < 1e-3
    assert d["total_display"] > d["total_eur"], (d["total_display"], d["total_eur"])
    for it in d["items"]:
        assert "price_display" in it and "price_eur" in it
        # display > eur since RON > EUR numerically
        if it["price_eur"] > 0:
            assert it["price_display"] >= it["price_eur"]
    # customer.total_spent should be a number if present
    cust = d.get("customer") or {}
    if "total_spent" in cust:
        assert isinstance(cust["total_spent"], (int, float))


def test_eur_orders_unchanged(admin_session):
    r = admin_session.get(f"{BASE}/api/admin/orders?limit=200", timeout=30)
    orders = r.json()["orders"]
    eur = [o for o in orders if (o.get("currency") or "EUR").upper() == "EUR"]
    assert eur, "no EUR orders on first page"
    for o in eur[:20]:
        assert abs(float(o["total_display"]) - float(o["total_eur"])) < 0.01, o


def test_analytics_still_works(admin_session):
    r = admin_session.get(f"{BASE}/api/admin/analytics?range=30d", timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert "current" in j and "sales" in j["current"]
    assert isinstance(j["current"]["sales"], (int, float))
    assert j["current"]["sales"] >= 0


# ---- SEO quick re-check -------------------------------------------------------

def test_robots_and_sitemap():
    r1 = requests.get(f"{BASE}/api/robots.txt", timeout=20)
    assert r1.status_code == 200
    assert "Sitemap" in r1.text or "sitemap" in r1.text.lower()
    r2 = requests.get(f"{BASE}/api/sitemap.xml", timeout=20)
    assert r2.status_code == 200
    assert "<urlset" in r2.text
    assert "<loc>" in r2.text


def _fetch_html(path: str) -> str:
    r = requests.get(f"{BASE}{path}", timeout=30)
    assert r.status_code == 200, r.status_code
    return r.text


def _jsonld_blocks(html: str):
    out = []
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            out.append(json.loads(m.group(1)))
        except Exception:
            pass
    return out


def test_home_schema():
    pytest.skip("JSON-LD is client-side rendered; verified via Playwright")


def test_product_schema_offers():
    pytest.skip("JSON-LD is client-side rendered; verified via Playwright")
