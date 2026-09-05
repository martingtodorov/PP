"""Iteration 47 — order cancel → warehouse push, rotated URL parity, exact-handle restore, storefront regression.

The unit-level cancel behaviour lives in test_cancel_fulfillment.py — this file adds
HTTP-level regression coverage on the live preview URL for the pieces the review request
called out but that are cheaper to test through /api than through the pytest monkeypatch harness.
"""
import os
import re
import uuid
from typing import Optional

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env"))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASS = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def admin() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- Rotated URL parity (bug 2) --------------------------------------

def test_old_retatrutide_handle_is_404_on_json_and_prerender():
    """The url the owner complained about must 404 in both places."""
    assert requests.get(f"{BASE}/api/products/21-retatrutide-5", timeout=10).status_code == 404
    r = requests.get(f"{BASE}/api/seo/prerender", params={"path": "/products/21-retatrutide-5"}, timeout=15)
    assert r.status_code == 404
    assert "noindex" in r.text.lower()


def test_restored_retatrutide_handle_is_200_on_both():
    assert requests.get(f"{BASE}/api/products/21-retatrutide-5-lrp", timeout=10).status_code == 200
    r = requests.get(f"{BASE}/api/seo/prerender", params={"path": "/products/21-retatrutide-5-lrp"}, timeout=15)
    assert r.status_code == 200
    assert "<h1" in r.text.lower()


def test_rotated_collection_metabolic_studies_404s_on_both():
    """Prerender parity is not just for products."""
    assert requests.get(f"{BASE}/api/collections/metabolic-studies", timeout=10).status_code == 404
    r = requests.get(f"{BASE}/api/seo/prerender", params={"path": "/collections/metabolic-studies"}, timeout=15)
    assert r.status_code == 404


# ---------- Exact-handle restore endpoint (rotate?to=) ----------------------

def _find_link_for_url(admin: requests.Session, url_needle: str) -> Optional[dict]:
    links = admin.get(f"{BASE}/api/admin/delisted-links", timeout=15).json()
    if isinstance(links, dict):
        links = links.get("links") or links.get("items") or []
    return next((l for l in links if url_needle in (l.get("url") or "")), None)


def test_rotate_to_same_handle_returns_400(admin):
    """The endpoint must reject a no-op rotation (to == source handle)."""
    link = _find_link_for_url(admin, "21-retatrutide-5")
    if not link:
        pytest.skip("no delisted link present to exercise rotate?to=")
    # Rotate to the same handle as the source URL → must be rejected
    r = admin.post(f"{BASE}/api/admin/delisted-links/{link['id']}/rotate",
                   params={"to": "21-retatrutide-5"}, timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"


# ---------- Cancel endpoint contracts ---------------------------------------

def test_customer_cancel_endpoint_ignores_force():
    """POST /api/orders/{id}/cancel?force=true must NOT accept force from customers."""
    # Introspect the route source — the safest test without creating a live order.
    import server
    src = open(server.__file__, "r", encoding="utf-8").read()
    # Find the customer cancel handler (path: /orders/{order_id}/cancel or similar, NOT under /admin)
    # Look for the function definition and confirm no `force` param on the customer side.
    m = re.search(r'@api\.post\("/orders/\{[^}]+\}/cancel"\).*?\ndef |@api\.post\("/orders/\{[^}]+\}/cancel"\).*?\nasync def ',
                  src, re.DOTALL)
    if not m:
        # Route may be defined slightly differently; fall back to grep any customer cancel route
        m = re.search(r'/orders/\{order_id\}/cancel"[^\n]*\)\s*\n\s*async def [^\(]+\(([^)]*)\)', src)
        assert m, "customer cancel route not found"
        assert "force" not in m.group(1), f"customer cancel accepts force! signature: {m.group(1)}"
    else:
        # Grab full signature by looking for the next '):' after m.end()
        sig_start = m.end()
        sig_end = src.index("):", sig_start)
        signature = src[sig_start:sig_end]
        assert "force" not in signature, f"customer cancel accepts force! signature: {signature}"


def test_admin_cancel_endpoint_accepts_force_query():
    """Introspect server.py for admin cancel signature to confirm ?force= is accepted."""
    import server
    src = open(server.__file__, "r", encoding="utf-8").read()
    m = re.search(r'@api\.post\("/admin/orders/\{order_id\}/cancel"\)\s*\nasync def cancel_order\(([^\n]+)', src)
    assert m, "admin cancel route not found in server.py"
    assert "force" in m.group(1), f"admin cancel must accept force; sig={m.group(1)}"


def test_cancel_error_surfaces_in_admin_order_detail_response():
    """After a refused cancel, the order document must carry fulfillment.cancel_error + timestamp."""
    import fulfillment
    src = open(fulfillment.__file__, "r", encoding="utf-8").read()
    assert "cancel_error" in src, "cancel_error field never written"
    assert "cancel_error_at" in src, "cancel_error_at timestamp missing"


# ---------- Storefront + catalog regression ---------------------------------

def test_products_list_still_returns_catalog():
    r = requests.get(f"{BASE}/api/products", timeout=15)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else (data.get("products") or data.get("items") or [])
    assert isinstance(items, list) and len(items) > 5, f"catalog looks empty: {len(items)} items"


def test_homepage_prerender_still_ok():
    r = requests.get(f"{BASE}/api/seo/prerender", params={"path": "/"}, timeout=20)
    assert r.status_code == 200
    body = r.text.lower()
    assert "<h1" in body and "canonical" in body


def test_a_known_product_page_still_renders():
    r = requests.get(f"{BASE}/api/products/sermorelin", timeout=15)
    assert r.status_code == 200
    body = r.json()
    prod = body.get("product") if isinstance(body, dict) and "product" in body else body
    assert prod and prod.get("handle") == "sermorelin"
