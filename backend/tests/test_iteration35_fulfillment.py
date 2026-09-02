"""Iteration 35 — NextLevel Fulfillment integration module + RevOrder removal + geolocation UX.

Covers:
- Admin config GET/PUT (validation + restore)
- Test endpoint (webhook mode)
- Preview endpoint for existing order SUB29
- Missing-fulfillment endpoints return 404
- RevOrder is gone (404 for admin route + webhook)
- NextLevel delivery config still exposes default_weight 0.1
- Checkout still creates real waybill (fulfillment disabled) — deletes shipment right after
- mark-paid does not crash (on_paid hook safe when fulfillment disabled)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"
PREVIEW_ORDER_ID = "4f1deeca-ce40-4da0-a9dc-09ca410b7127"


@pytest.fixture(scope="session")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ----- 1. Fulfillment config -----
def test_fulfillment_config_requires_auth():
    r = requests.get(f"{API}/admin/integrations/nextlevel-fulfillment", timeout=15)
    assert r.status_code in (401, 403), r.text


def test_fulfillment_config_defaults(admin_headers):
    r = requests.get(f"{API}/admin/integrations/nextlevel-fulfillment", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg.get("enabled") is False
    assert cfg.get("auto_create") is True
    assert cfg.get("app_id") == "ff-OcTywYtADkJDKfs6i"
    assert cfg.get("webhook_url") == "https://api.nextlevel.delivery/webhooks/orders/ff-OcTywYtADkJDKfs6i"
    assert float(cfg.get("weight")) == 0.1
    assert cfg.get("bank_transfer_when") == "paid"
    assert cfg.get("has_api") is False


def test_fulfillment_config_update_and_validation(admin_headers):
    # Invalid bank_transfer_when
    r_bad = requests.put(f"{API}/admin/integrations/nextlevel-fulfillment",
                         headers=admin_headers, json={"bank_transfer_when": "bogus"}, timeout=15)
    assert r_bad.status_code == 422, r_bad.text

    # Valid update
    r = requests.put(f"{API}/admin/integrations/nextlevel-fulfillment",
                     headers=admin_headers, json={"weight": 0.2, "bank_transfer_when": "immediately"}, timeout=15)
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert float(cfg["weight"]) == 0.2
    assert cfg["bank_transfer_when"] == "immediately"
    assert cfg["enabled"] is False  # sanity: unchanged

    # Restore defaults
    r2 = requests.put(f"{API}/admin/integrations/nextlevel-fulfillment",
                      headers=admin_headers, json={"weight": 0.1, "bank_transfer_when": "paid"}, timeout=15)
    assert r2.status_code == 200, r2.text
    cfg2 = r2.json()
    assert float(cfg2["weight"]) == 0.1
    assert cfg2["bank_transfer_when"] == "paid"


def test_fulfillment_test_endpoint_webhook_mode(admin_headers):
    r = requests.post(f"{API}/admin/integrations/nextlevel-fulfillment/test", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True, d
    assert d.get("mode") == "webhook"
    assert "webhook_url" in d and d["webhook_url"].startswith("https://api.nextlevel.delivery/webhooks/orders/ff-")


# ----- 2. Preview -----
def test_fulfillment_preview_sub29(admin_headers):
    r = requests.get(f"{API}/admin/integrations/nextlevel-fulfillment/preview/{PREVIEW_ORDER_ID}",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True, d
    p = d["payload"]
    assert p["order_id"] == "SUB29", p
    assert p["currency"] == "EUR"
    assert p["is_paid"] is True
    assert p["receiver"].get("office_id") == 4471, p["receiver"]
    products = p["products"]
    assert len(products) >= 1
    assert products[0]["sku"] == "PP-SERMORELIN-5MG"
    assert float(products[0]["weight"]) == 0.1
    # Product name: no duplicated '5mg 5mg'
    name = products[0]["name"]
    assert name == "Серморелин (Sermorelin) 5mg", f"unexpected product name: {name!r}"
    assert "5mg 5mg" not in name.lower().replace("mg  mg", "mg 5mg")
    assert p["contents"].startswith("PP-SERMORELIN-5MG x1"), p["contents"]


# ----- 3. Missing fulfillment endpoints -> 404 -----
def test_fulfillment_cancel_when_missing(admin_headers):
    r = requests.delete(f"{API}/admin/orders/{PREVIEW_ORDER_ID}/fulfillment", headers=admin_headers, timeout=15)
    assert r.status_code == 404, r.text


def test_fulfillment_refresh_when_missing(admin_headers):
    r = requests.post(f"{API}/admin/orders/{PREVIEW_ORDER_ID}/fulfillment/refresh", headers=admin_headers, timeout=15)
    assert r.status_code == 404, r.text


# ----- 4. RevOrder removal -----
def test_revorder_admin_route_removed(admin_headers):
    r = requests.get(f"{API}/admin/integrations/revorder", headers=admin_headers, timeout=15)
    assert r.status_code == 404, r.text


def test_revorder_webhook_removed():
    r = requests.post(f"{API}/webhooks/revorder/purepeptide.bg", json={}, timeout=15)
    assert r.status_code == 404, r.text


# ----- 5. NextLevel delivery config default_weight 0.1 -----
def test_nextlevel_delivery_default_weight(admin_headers):
    r = requests.get(f"{API}/admin/integrations/nextlevel", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert float(d.get("default_weight")) == 0.1, d


# ----- 6. Checkout regression: waybill still created via nextlevel (ff disabled) -----
@pytest.fixture(scope="session")
def sermorelin():
    r = requests.get(f"{API}/products/sermorelin", timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()["product"]
    return {"product_id": p["id"], "variant_sku": p["variants"][0]["sku"]}


@pytest.fixture(scope="session")
def econt_locker_office():
    r = requests.get(f"{API}/nextcart/offices",
                     params={"provider_key": "econt", "destination_type": "locker", "country": "BG", "limit": 5},
                     timeout=15)
    for o in r.json().get("offices", []):
        if str(o.get("id")) == "econt:4471":
            return o
    return (r.json().get("offices") or [{}])[0]


def test_checkout_creates_shipment_weight_0_1(sermorelin, admin_headers, econt_locker_office):
    office = {
        "id": econt_locker_office.get("id") or "econt:4471",
        "code": econt_locker_office.get("code") or "8015",
        "name": econt_locker_office.get("name") or "Еконтомат",
        "address": econt_locker_office.get("address") or "x",
        "city": econt_locker_office.get("city") or "Бургас",
    }
    payload = {
        "items": [{"product_id": sermorelin["product_id"], "variant_sku": sermorelin["variant_sku"], "quantity": 1}],
        "shipping": {"full_name": "TEST QA", "phone": "+359878279269", "email": "qa@example.com",
                     "line1": "TEST street 1", "city": "Бургас", "postal_code": "8000", "country": "BG"},
        "customer_email": "qa@example.com", "customer_name": "TEST QA", "customer_phone": "+359878279269",
        "shipping_method": "econt_locker", "payment_method": "bank_transfer",
        "delivery": {"provider_key": "econt", "method_key": "econt_locker", "destination_type": "locker",
                     "price_amount": 3.39, "currency": "EUR", "office": office},
        "terms_accepted": True, "locale": "bg",
    }
    r = requests.post(f"{API}/checkout", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    order = r.json()["order"]
    order_id = order["id"]

    try:
        # Wait for auto waybill
        awb = None
        for _ in range(25):
            g = requests.get(f"{API}/orders/{order_id}", timeout=15)
            s = (g.json().get("order") or {}).get("shipment") or {}
            if s.get("awb"):
                awb = s["awb"]
                break
            time.sleep(1.0)
        assert awb, "shipment.awb not created within timeout"

        # Admin detail: shipment.payload.content.weight == 0.1
        a = requests.get(f"{API}/admin/orders/{order_id}", headers=admin_headers, timeout=15)
        assert a.status_code == 200, a.text
        adm_ship = (a.json()["order"] or {}).get("shipment") or {}
        weight = ((adm_ship.get("payload") or {}).get("content") or {}).get("weight")
        assert float(weight) == 0.1, f"expected weight 0.1 in shipment.payload.content, got {weight!r}"

        # mark-paid should not raise even though fulfillment.on_paid is called
        mp = requests.post(f"{API}/admin/orders/{order_id}/mark-paid", headers=admin_headers, timeout=15)
        assert mp.status_code == 200, mp.text
    finally:
        # ALWAYS cancel (live courier API)
        c = requests.delete(f"{API}/admin/orders/{order_id}/shipment", headers=admin_headers, timeout=30)
        assert c.status_code == 200, c.text
        assert c.json().get("cancelled") is True
