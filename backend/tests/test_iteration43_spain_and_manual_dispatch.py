"""Iteration 43 — Spain market, prepaid-only server-side guard, waybill contents default,
bank-transfer never auto-pushed to NextLevel, bank details only after confirmation."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"

# In-stock SKUs to use for orders (from review request)
IN_STOCK_HANDLES = ["3-ipamorelin-1", "dsip-5mg", "aasghrp-2", "cahexarelin"]


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def any_product():
    for h in IN_STOCK_HANDLES:
        r = requests.get(f"{API}/products/{h}", timeout=15)
        if r.status_code == 200:
            p = r.json()["product"]
            v = next((v for v in p.get("variants", []) if int(v.get("stock", 0)) > 0), None)
            if v:
                return {"product_id": p["id"], "variant_sku": v["sku"], "price_eur": float(v["price_eur"]), "title": p["title"]}
    pytest.skip("No in-stock product available")


def _cleanup(order_id, headers):
    try:
        requests.post(f"{API}/admin/orders/{order_id}/cancel", headers=headers,
                      json={"reason": "TEST cleanup"}, timeout=15)
    except Exception:
        pass


# --- 1. /api/nextcart/countries: ES present ---
def test_countries_include_ES():
    r = requests.get(f"{API}/nextcart/countries", timeout=15)
    assert r.status_code == 200
    countries = r.json()["countries"]
    es = next((c for c in countries if c["iso2"] == "ES"), None)
    assert es is not None, "ES not in countries"
    assert es["name"] == "Испания"
    assert str(es.get("dial")) == "34"


# --- 2. /api/nextcart/config?country=ES → GLS address only, bank_transfer only, no COD ---
def test_nextcart_config_ES_prepaid_only():
    r = requests.get(f"{API}/nextcart/config", params={"country": "ES"}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    dms = d.get("delivery_methods") or d.get("methods") or []
    # Expect exactly one method: gls address at 8.99
    assert len(dms) == 1, f"expected 1 delivery method, got {dms}"
    m = dms[0]
    assert m.get("provider_key") == "gls" or "gls" in (m.get("method_key", "") + m.get("provider_key", ""))
    assert m.get("destination_type") == "address"
    assert float(m.get("price") or m.get("price_amount") or m.get("price_eur")) == 8.99
    pms = d.get("payment_methods") or []
    keys = [(p["key"] if isinstance(p, dict) else p) for p in pms]
    assert keys == ["bank_transfer"], f"expected only bank_transfer, got {keys}"
    assert d.get("cod_available") is False


# --- 3. Regression: the COD markets still have COD first (DE went prepaid-only) ---
@pytest.mark.parametrize("country", ["BG", "RO", "GR", "DE"])
def test_regression_cod_first_available(country):
    r = requests.get(f"{API}/nextcart/config", params={"country": country}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("cod_available") is True, f"{country} should have cod_available=True"
    pms = d.get("payment_methods") or []
    keys = [(p["key"] if isinstance(p, dict) else p) for p in pms]
    assert keys and keys[0] == "cod", f"{country} should have cod first, got {keys}"


# --- 4. Server-side guard: ES + cod → stored as bank_transfer ---
def test_es_checkout_forces_bank_transfer(any_product, admin_headers):
    payload = {
        "items": [{"product_id": any_product["product_id"], "variant_sku": any_product["variant_sku"], "quantity": 1}],
        "customer_email": "TEST_es_guard@example.com",
        "customer_name": "TEST ES Guard",
        "customer_phone": "+34600000001",
        "shipping": {
            "full_name": "TEST ES Guard", "phone": "+34600000001", "email": "TEST_es_guard@example.com",
            "line1": "Calle Mayor 1", "city": "Madrid", "postal_code": "28001", "country": "ES",
        },
        "delivery": {
            "provider_key": "gls", "method_key": "gls_address", "destination_type": "address",
            "price_amount": 8.99,
        },
        "shipping_method": "gls",
        "payment_method": "cod",  # client trying to force COD
        "terms_accepted": True,
        "locale": "bg",
    }
    r = requests.post(f"{API}/checkout", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    order_id = r.json()["order"]["id"]
    try:
        # Fetch back
        # There's typically /api/orders/{id} public
        assert r.json()["order"]["payment_method"] == "bank_transfer"
        assert r.json()["order"]["shipping"]["country"] == "ES"
        assert float(r.json()["order"]["shipping_eur"]) == 8.99
    finally:
        _cleanup(order_id, admin_headers)


# --- 5. ES full happy-path bank_transfer order ---
def test_es_bank_transfer_checkout(any_product, admin_headers):
    payload = {
        "items": [{"product_id": any_product["product_id"], "variant_sku": any_product["variant_sku"], "quantity": 1}],
        "customer_email": "TEST_es_bt@example.com",
        "customer_name": "TEST ES BT",
        "customer_phone": "+34600111222",
        "shipping": {
            "full_name": "TEST ES BT", "phone": "+34600111222", "email": "TEST_es_bt@example.com",
            "line1": "Calle Sol 5", "city": "Barcelona", "postal_code": "08001", "country": "ES",
        },
        "delivery": {
            "provider_key": "gls", "method_key": "gls_address", "destination_type": "address",
            "price_amount": 8.99,
        },
        "shipping_method": "gls",
        "payment_method": "bank_transfer",
        "terms_accepted": True,
        "locale": "bg",
    }
    r = requests.post(f"{API}/checkout", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    o = r.json()["order"]
    try:
        assert o["payment_method"] == "bank_transfer"
        assert o["shipping"]["country"] == "ES"
        assert float(o["shipping_eur"]) == 8.99
        # Expected total = subtotal + shipping (no discount)
        assert abs(float(o["total_eur"]) - (float(o["subtotal_eur"]) + 8.99)) < 0.01
    finally:
        _cleanup(o["id"], admin_headers)


# --- 6. Admin nextlevel-fulfillment config: default contents_text='аминокиселини' ---
def test_admin_fulfillment_defaults(admin_headers):
    r = requests.get(f"{API}/admin/integrations/nextlevel-fulfillment", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("contents_text") == "аминокиселини", f"got {d.get('contents_text')!r}"


def test_admin_fulfillment_update_contents_roundtrip(admin_headers):
    orig = requests.get(f"{API}/admin/integrations/nextlevel-fulfillment", headers=admin_headers, timeout=15).json()
    original_text = orig.get("contents_text")
    try:
        new_text = "TEST_content_iter43"
        r = requests.put(f"{API}/admin/integrations/nextlevel-fulfillment",
                         headers=admin_headers, json={"contents_text": new_text}, timeout=15)
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/admin/integrations/nextlevel-fulfillment", headers=admin_headers, timeout=15).json()
        assert d.get("contents_text") == new_text
    finally:
        # Restore
        requests.put(f"{API}/admin/integrations/nextlevel-fulfillment",
                     headers=admin_headers, json={"contents_text": original_text or "аминокиселини"}, timeout=15)


# --- 7. Bank-transfer order is NOT auto-submitted to warehouse ---
def test_bank_transfer_not_auto_pushed(any_product, admin_headers):
    payload = {
        "items": [{"product_id": any_product["product_id"], "variant_sku": any_product["variant_sku"], "quantity": 1}],
        "customer_email": "TEST_bt_manual@example.com",
        "customer_name": "TEST BT Manual",
        "customer_phone": "+359888000111",
        "shipping": {
            "full_name": "TEST BT Manual", "phone": "+359888000111", "email": "TEST_bt_manual@example.com",
            "line1": "ул. Тест 1", "city": "София", "postal_code": "1000", "country": "BG",
        },
        "delivery": {
            "provider_key": "econt", "method_key": "econt_address", "destination_type": "address",
            "price_amount": 4.99,
        },
        "shipping_method": "econt",
        "payment_method": "bank_transfer",
        "terms_accepted": True,
        "locale": "bg",
    }
    r = requests.post(f"{API}/checkout", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    o = r.json()["order"]
    order_id = o["id"]
    try:
        # Wait a bit for any background task
        time.sleep(3)
        # Fetch as admin
        adm = requests.get(f"{API}/admin/orders/{order_id}", headers=admin_headers, timeout=15)
        assert adm.status_code == 200, adm.text
        full = adm.json()
        # Bank-transfer order should NOT have wc_id/fulfillment set from auto-push
        fulfillment_field = full.get("fulfillment") or {}
        # wc_id may be set by internal facade shim but no *warehouse* order id
        assert not fulfillment_field.get("wc_id"), f"bank transfer order was auto-pushed: {fulfillment_field}"
        assert not fulfillment_field.get("nextlevel_id"), f"bank transfer order was auto-pushed: {fulfillment_field}"

        # Mark as paid — should still NOT push
        pay_endpoints = [
            f"{API}/admin/orders/{order_id}/mark-paid",
            f"{API}/admin/orders/{order_id}/pay",
        ]
        marked = False
        for ep in pay_endpoints:
            rp = requests.post(ep, headers=admin_headers, timeout=15)
            if rp.status_code < 400:
                marked = True
                break
        # Try PATCH-style if POST didn't work
        if not marked:
            rp = requests.patch(f"{API}/admin/orders/{order_id}",
                                headers=admin_headers,
                                json={"payment_status": "paid"},
                                timeout=15)
            marked = rp.status_code < 400
        time.sleep(3)
        adm2 = requests.get(f"{API}/admin/orders/{order_id}", headers=admin_headers, timeout=15).json()
        f2 = adm2.get("fulfillment") or {}
        assert not f2.get("nextlevel_id"), f"bank transfer order pushed after marking paid: {f2}"
    finally:
        _cleanup(order_id, admin_headers)


# --- 8. Bank details come with the order (the public endpoint was removed) ---
def test_bank_details_endpoint():
    assert requests.get(f"{API}/bank-details", timeout=15).status_code == 404
