"""Iteration 61 — re-verification of the new /checkout page end-to-end.

Backend focus (frontend is exercised separately via Playwright):
 * POST /api/checkout — courier office (BG, COD) creates order with dispatch_at ≈ +5 min
 * POST /api/checkout — address delivery + bank_transfer payment on a prepaid market (ES/GLS)
 * Validation: empty items, missing terms, empty payload — must NOT create an order
 * GET  /api/orders/{id} — returns the order for the success page (guest-viewable)
 * Stock decrement on the ordered variant
 * Discount code still applied when passed at /checkout
 * Upsells endpoint appears with open window right after checkout
 * Add-to-order inside grace window keeps shipping pinned and grows total
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[1].splitlines()[0]).rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) QATestAgent/1.0"}
JSON = {**UA, "Content-Type": "application/json"}


# --------- helpers ---------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _product(s, handle):
    r = s.get(f"{BASE}/api/products/{handle}?locale=bg", headers=UA)
    assert r.status_code == 200, f"{handle}: {r.status_code}"
    return r.json()["product"]


def _payload_office_bg(product, qty=1, terms=True, extra=None):
    v = product["variants"][0]
    p = {
        "items": [{"product_id": product["id"], "variant_sku": v["sku"], "quantity": qty}],
        "customer_email": f"qa_{uuid.uuid4().hex[:8]}@example.com",
        "customer_name": "QA Buyer",
        "customer_phone": "+359888123456",
        "shipping": {
            "full_name": "QA Buyer", "first_name": "QA", "last_name": "Buyer",
            "line1": "ул. Тестова 1", "address1": "ул. Тестова 1",
            "city": "София", "postal_code": "1000", "country": "BG",
            "phone": "+359888123456",
        },
        "shipping_method": "econt_office",
        "delivery": {
            "carrier": "econt", "provider_key": "econt", "method_key": "econt_office",
            "destination_type": "office",
            "office": {"code": "1000", "name": "офис Тест", "city": "София"},
            "price_amount": 5.99,
        },
        "payment_method": "cod",
        "terms_accepted": terms,
        "locale": "bg",
    }
    if extra:
        p.update(extra)
    return p


def _payload_address_es(product, qty=1):
    """Prepaid ES market — bank_transfer + GLS address delivery."""
    v = product["variants"][0]
    return {
        "items": [{"product_id": product["id"], "variant_sku": v["sku"], "quantity": qty}],
        "customer_email": f"qa_{uuid.uuid4().hex[:8]}@example.com",
        "customer_name": "QA ES Buyer",
        "customer_phone": "+34600123456",
        "shipping": {
            "full_name": "QA ES Buyer", "first_name": "QA", "last_name": "ES",
            "line1": "Calle Test 1", "address1": "Calle Test 1",
            "city": "Madrid", "postal_code": "28001", "country": "ES",
            "phone": "+34600123456",
        },
        "shipping_method": "gls_address",
        "delivery": {
            "carrier": "gls", "provider_key": "gls", "method_key": "gls_address",
            "destination_type": "address",
            "price_amount": 8.99,
        },
        "payment_method": "bank_transfer",
        "terms_accepted": True,
        "locale": "es",
    }


# --------- 1. BG courier-office + COD ---------
def test_checkout_bg_office_cod_creates_order(s):
    prod = _product(s, "demo-sample-a")
    before = datetime.now(timezone.utc)
    r = s.post(f"{BASE}/api/checkout", json=_payload_office_bg(prod), headers=JSON)
    assert r.status_code == 200, r.text[:400]
    order = r.json()["order"]
    assert order["id"] and order["order_number"]
    assert order["payment_method"] == "cod"
    assert order["shipping"]["country"] == "BG"
    assert order["delivery"]["destination_type"] == "office"
    assert order["delivery"]["office"]["name"] == "офис Тест"
    assert order["shipping_eur"] > 0
    assert order["total_eur"] >= order["subtotal_eur"]
    assert order["locale"] == "bg"
    # dispatch_at ≈ +5 min
    da = datetime.fromisoformat(order["dispatch_at"])
    delta = (da - before).total_seconds()
    assert 250 <= delta <= 360, f"dispatch_at ~+5min expected, got {delta}s"
    assert not order.get("dispatch_claimed_at")


# --------- 2. ES address + bank_transfer ---------
def test_checkout_es_address_bank_transfer(s):
    prod = _product(s, "demo-sample-a")
    r = s.post(f"{BASE}/api/checkout", json=_payload_address_es(prod), headers=JSON)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    order = body["order"]
    assert order["payment_method"] == "bank_transfer", (
        f"ES must offer bank_transfer, got {order['payment_method']}"
    )
    assert order["shipping"]["country"] == "ES"
    assert order["delivery"]["destination_type"] == "address"
    # bank details block accompanies the response
    assert body.get("bank_transfer") is not None, "bank_transfer block missing for prepaid order"


# --------- 3. Validation ---------
def test_checkout_rejects_missing_terms(s):
    prod = _product(s, "demo-sample-a")
    payload = _payload_office_bg(prod, terms=False)
    r = s.post(f"{BASE}/api/checkout", json=payload, headers=JSON)
    assert r.status_code == 400
    assert "общите условия" in r.text or "условия" in r.text


def test_checkout_rejects_empty_items(s):
    prod = _product(s, "demo-sample-a")
    payload = _payload_office_bg(prod)
    payload["items"] = []
    r = s.post(f"{BASE}/api/checkout", json=payload, headers=JSON)
    assert r.status_code in (400, 422)


def test_checkout_rejects_missing_customer_fields(s):
    prod = _product(s, "demo-sample-a")
    payload = _payload_office_bg(prod)
    payload["customer_email"] = ""
    payload["customer_name"] = ""
    payload["customer_phone"] = ""
    r = s.post(f"{BASE}/api/checkout", json=payload, headers=JSON)
    assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}"


def test_checkout_rejects_invalid_email(s):
    prod = _product(s, "demo-sample-a")
    payload = _payload_office_bg(prod)
    payload["customer_email"] = "not-an-email"
    r = s.post(f"{BASE}/api/checkout", json=payload, headers=JSON)
    # Pydantic EmailStr → 422, otherwise app-level 400
    assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}"


# --------- 4. GET /api/orders/{id} for the success page ---------
def test_get_order_for_success_page(s):
    prod = _product(s, "demo-sample-a")
    r = s.post(f"{BASE}/api/checkout", json=_payload_office_bg(prod), headers=JSON)
    assert r.status_code == 200
    oid = r.json()["order"]["id"]
    # success page reads the order — no auth required for the just-created guest order
    r2 = s.get(f"{BASE}/api/orders/{oid}", headers=UA)
    assert r2.status_code == 200, f"guest fetch of order failed: {r2.status_code} {r2.text[:200]}"
    body = r2.json()
    order = body.get("order") or body
    assert order["id"] == oid
    assert order["items"] and order["items"][0]["variant_sku"] == "DEMO-A"


def test_get_order_404(s):
    r = s.get(f"{BASE}/api/orders/does-not-exist-xyzzy", headers=UA)
    assert r.status_code == 404


# --------- 5. Stock decrement ---------
def test_stock_decremented_after_checkout(s):
    before = _product(s, "demo-sample-a")["variants"][0]["stock"]
    r = s.post(f"{BASE}/api/checkout", json=_payload_office_bg(_product(s, "demo-sample-a")),
               headers=JSON)
    assert r.status_code == 200
    after = _product(s, "demo-sample-a")["variants"][0]["stock"]
    assert after == before - 1, f"stock {before} -> {after}"


# --------- 6. Discount code still works at /api/checkout ---------
def test_checkout_applies_discount_code_if_available(s):
    # try to fetch admin discounts through the public list endpoint — if none, skip
    r = s.get(f"{BASE}/api/discounts/active", headers=UA)
    if r.status_code != 200:
        pytest.skip(f"public active-discounts endpoint unavailable: {r.status_code}")
    codes = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if not codes:
        pytest.skip("no active discount codes seeded")
    code = codes[0].get("code")
    if not code:
        pytest.skip("no code field in discount payload")
    prod = _product(s, "demo-sample-a")
    payload = _payload_office_bg(prod, extra={"discount_code": code})
    r = s.post(f"{BASE}/api/checkout", json=payload, headers=JSON)
    assert r.status_code == 200, r.text[:200]
    order = r.json()["order"]
    assert order.get("discount", {}).get("code", "").lower() == code.lower()


# --------- 7. Upsells window right after checkout ---------
def test_upsells_open_right_after_checkout(s):
    prod = _product(s, "demo-sample-a")
    r = s.post(f"{BASE}/api/checkout", json=_payload_office_bg(prod), headers=JSON)
    oid = r.json()["order"]["id"]
    u = s.get(f"{BASE}/api/orders/{oid}/upsells?locale=bg", headers=UA)
    assert u.status_code == 200
    data = u.json()
    assert data["window"]["open"] is True
    assert 0 < data["window"]["seconds_left"] <= 300
    # demo-sample-b should appear as an upsell (it wasn't ordered)
    handles = {p["handle"] for p in data["products"]}
    assert "demo-sample-b" in handles


# --------- 8. Add to order inside grace, shipping pinned ---------
def test_add_upsell_keeps_shipping_and_grows_total(s):
    prod = _product(s, "demo-sample-a")
    r = s.post(f"{BASE}/api/checkout", json=_payload_office_bg(prod), headers=JSON)
    order = r.json()["order"]
    ship_before = order["shipping_eur"]
    total_before = order["total_eur"]
    other = _product(s, "demo-sample-b")
    v = other["variants"][0]
    r2 = s.post(f"{BASE}/api/orders/{order['id']}/items",
                json={"items": [{"product_id": other["id"], "variant_sku": v["sku"], "quantity": 1}]},
                headers=JSON)
    assert r2.status_code == 200, r2.text[:200]
    o2 = r2.json()["order"]
    assert o2["shipping_eur"] == ship_before, "shipping must stay pinned"
    assert o2["total_eur"] > total_before, "total must grow"
    assert any(li["variant_sku"] == "DEMO-B" for li in o2["items"])
