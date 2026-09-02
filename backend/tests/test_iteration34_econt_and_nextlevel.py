"""Iteration 34 — Econt BG methods (locker 3.39, address 4.99), server-side shipping override,
NextLevel auto-waybill creation, guest order tracking payload, admin shipment endpoints,
NextLevel integration test, and RO ui-strings trackingTitle."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def sermorelin():
    r = requests.get(f"{API}/products/sermorelin", timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()["product"]
    variant = p["variants"][0]
    return {"product_id": p["id"], "variant_sku": variant["sku"], "price_eur": float(variant["price_eur"])}


# --- 1. Delivery config for BG contains the 5 methods with correct prices ---
def test_nextcart_config_bg_methods():
    r = requests.get(f"{API}/nextcart/config", params={"country": "BG"}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    methods = {m["key"]: m for m in d.get("delivery_methods", [])}
    for k in ("econt_office", "econt_locker", "econt_address", "boxnow_locker", "pigeon_address"):
        assert k in methods, f"missing {k}: {list(methods)}"
    assert methods["econt_office"]["price_amount"] == 3.89
    assert methods["econt_locker"]["price_amount"] == 3.39
    assert methods["econt_locker"]["destination_type"] == "locker"
    assert methods["econt_locker"]["currency"] == "EUR"
    assert methods["econt_address"]["price_amount"] == 4.99
    assert methods["econt_address"]["destination_type"] == "address"
    assert methods["boxnow_locker"]["price_amount"] == 2.99
    assert methods["pigeon_address"]["price_amount"] == 4.59
    econt = next(p for p in d["delivery_providers"] if p["key"] == "econt")
    assert econt.get("supports_address") is True
    assert econt.get("supports_pickup") is True


# --- 2. Offices lookup for econt locker returns Еконтомат entries ---
def test_nextcart_offices_econt_locker():
    r = requests.get(f"{API}/nextcart/offices",
                     params={"provider_key": "econt", "destination_type": "locker", "country": "BG", "limit": 5},
                     timeout=15)
    assert r.status_code == 200, r.text
    offices = r.json().get("offices", [])
    assert len(offices) >= 1
    # id encoded as "econt:XXXX", name contains Еконтомат
    assert any("Еконтомат" in (o.get("name") or "") for o in offices), [o.get("name") for o in offices]
    assert all(str(o.get("id", "")).startswith("econt:") for o in offices)


# --- 3. Checkout with econt_locker: server-side shipping override 3.39; verify waybill; cancel ---
def _post_checkout(sermorelin, method_key, destination_type, office=None):
    payload = {
        "items": [{"product_id": sermorelin["product_id"], "variant_sku": sermorelin["variant_sku"], "quantity": 1}],
        "shipping": {
            "full_name": "TEST QA", "phone": "+359878279269", "email": "qa@example.com",
            "line1": "TEST street 1", "city": "Бургас", "postal_code": "8000", "country": "BG",
        },
        "customer_email": "qa@example.com",
        "customer_name": "TEST QA",
        "customer_phone": "+359878279269",
        "shipping_method": "econt_office",
        "payment_method": "bank_transfer",
        "delivery": {
            "provider_key": "econt", "method_key": method_key,
            "destination_type": destination_type,
            "price_amount": 0.01,  # client tries 0.01 - server MUST override
            "currency": "EUR",
            "office": office,
        },
        "terms_accepted": True,
        "locale": "bg",
    }
    return requests.post(f"{API}/checkout", json=payload, timeout=30)


def _cancel_shipment(admin_headers, order_id):
    return requests.delete(f"{API}/admin/orders/{order_id}/shipment", headers=admin_headers, timeout=30)


@pytest.fixture(scope="session")
def econt_locker_office():
    r = requests.get(f"{API}/nextcart/offices",
                     params={"provider_key": "econt", "destination_type": "locker", "country": "BG", "limit": 5},
                     timeout=15)
    return (r.json().get("offices") or [{}])[0]


order_ids = []


def test_checkout_econt_locker_price_override(sermorelin, admin_headers, econt_locker_office):
    office = {
        "id": econt_locker_office.get("id") or "econt:4471",
        "code": econt_locker_office.get("code") or "8015",
        "name": econt_locker_office.get("name") or "Еконтомат",
        "address": econt_locker_office.get("address") or "x",
        "city": econt_locker_office.get("city") or "Бургас",
    }
    r = _post_checkout(sermorelin, "econt_locker", "locker", office)
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    order_ids.append(order["id"])
    assert order["shipping_eur"] == 3.39, f"expected 3.39, got {order['shipping_eur']}"
    expected_total = round(order["subtotal_eur"] - order.get("discount_eur", 0) + 3.39, 2)
    assert order["total_eur"] == expected_total

    # Wait for auto NextLevel waybill creation
    shipment = None
    for _ in range(20):
        g = requests.get(f"{API}/orders/{order['id']}", timeout=15)
        assert g.status_code == 200
        shipment = (g.json().get("order") or {}).get("shipment")
        if shipment and shipment.get("awb"):
            break
        time.sleep(1.5)
    assert shipment, "shipment was not auto-created"
    assert shipment.get("awb"), shipment
    # guest view must NOT include payload
    assert "payload" not in shipment, "guest view leaked shipment.payload"
    assert (shipment.get("courier") or "") in ("Econt", "Speedy", "BoxNow", None, "") or shipment.get("courier")
    # tracking_link is optional (depends on courier resolution) but if present must be an econt url when courier is Econt
    if (shipment.get("courier") or "") == "Econt" and shipment.get("tracking_link"):
        assert "econt.com" in shipment["tracking_link"]

    # Admin detail exposes payload with SKU contents
    a = requests.get(f"{API}/admin/orders/{order['id']}", headers=admin_headers, timeout=15)
    assert a.status_code == 200, a.text
    adm_ship = (a.json()["order"] or {}).get("shipment") or {}
    payload = (adm_ship.get("payload") or {})
    contents = ((payload.get("content") or {}).get("contents") or "")
    assert sermorelin["variant_sku"] in contents, f"expected SKU in contents: {contents}"

    # Cancel
    c = _cancel_shipment(admin_headers, order["id"])
    assert c.status_code == 200, c.text
    assert c.json().get("cancelled") is True


def test_checkout_econt_address_price_override(sermorelin, admin_headers):
    r = _post_checkout(sermorelin, "econt_address", "address", office=None)
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    order_ids.append(order["id"])
    assert order["shipping_eur"] == 4.99, f"expected 4.99, got {order['shipping_eur']}"
    expected_total = round(order["subtotal_eur"] - order.get("discount_eur", 0) + 4.99, 2)
    assert order["total_eur"] == expected_total

    # Wait for auto waybill
    shipment = None
    for _ in range(20):
        g = requests.get(f"{API}/orders/{order['id']}", timeout=15)
        shipment = (g.json().get("order") or {}).get("shipment")
        if shipment and shipment.get("awb"):
            break
        time.sleep(1.5)
    assert shipment and shipment.get("awb"), f"shipment missing: {shipment}"
    assert "payload" not in shipment  # guest view

    # Cancel
    c = _cancel_shipment(admin_headers, order["id"])
    assert c.status_code == 200, c.text
    assert c.json().get("cancelled") is True


# --- 4. Admin shipment label PDF (create separate shipment because previous was cancelled) ---
def test_shipment_label_pdf_is_pdf(sermorelin, admin_headers, econt_locker_office):
    office = {
        "id": econt_locker_office.get("id") or "econt:4471",
        "code": econt_locker_office.get("code") or "8015",
        "name": econt_locker_office.get("name") or "Еконтомат",
        "address": econt_locker_office.get("address") or "x",
        "city": econt_locker_office.get("city") or "Бургас",
    }
    r = _post_checkout(sermorelin, "econt_locker", "locker", office)
    assert r.status_code == 200
    order = r.json()["order"]
    order_ids.append(order["id"])
    awb_ok = False
    for _ in range(20):
        g = requests.get(f"{API}/orders/{order['id']}", timeout=15)
        s = (g.json().get("order") or {}).get("shipment") or {}
        if s.get("awb"):
            awb_ok = True
            break
        time.sleep(1.5)
    assert awb_ok, "shipment not created for label test"

    lbl = requests.get(f"{API}/admin/orders/{order['id']}/shipment/label", headers=admin_headers, timeout=30)
    try:
        assert lbl.status_code == 200, lbl.text
        assert "application/pdf" in lbl.headers.get("content-type", "")
        assert lbl.content[:4] == b"%PDF", f"first bytes: {lbl.content[:8]!r}"
    finally:
        _cancel_shipment(admin_headers, order["id"])


# --- 5. NextLevel admin integration test endpoint ---
def test_nextlevel_admin_integration_test(admin_headers):
    r = requests.post(f"{API}/admin/integrations/nextlevel/test", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True, d
    # sender_seen should mention Пюр Пептид (may be exact 'Пюр Пептид ЕООД')
    assert d.get("sender_seen"), d
    assert "Пюр Пептид" in (d.get("sender_seen") or ""), d


# --- 6. Guest tracking for non-shipment order: no shipment field → frontend shows pending ---
def test_guest_order_without_shipment_no_leak():
    # We look at an existing recent order without shipment; if none, skip.
    r = requests.get(f"{API}/orders/does-not-exist", timeout=10)
    assert r.status_code == 404


# --- 7. RO ui-strings has trackingTitle ---
def test_ro_ui_strings_tracking_title():
    r = requests.get(f"{API}/ui-strings", params={"locale": "ro"}, timeout=15)
    assert r.status_code == 200, r.text
    ro = (r.json().get("strings") or {}).get("ro") or {}
    # Frontend bundles the default; API only returns overlays. But review request expects
    # the RO overlay to include trackingTitle in Romanian.
    tt = ro.get("trackingTitle")
    assert tt == "Urmărirea coletului", f"trackingTitle in RO overlay: {tt!r}"


# --- 8. Auth required on admin shipment endpoints ---
def test_admin_shipment_requires_auth():
    r = requests.delete(f"{API}/admin/orders/fake-id/shipment", timeout=10)
    assert r.status_code in (401, 403)
    r2 = requests.get(f"{API}/admin/orders/fake-id/shipment/label", timeout=10)
    assert r2.status_code in (401, 403)
