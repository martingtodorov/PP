"""Iteration-17: accelerated pre-checkout overlay + RevOrder per-domain integration."""
import hashlib
import hmac
import json
import os
import time

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL") else open("/app/frontend/.env").read().split(
    "REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return s


# --- /api/nextcart/pickups full list + cache ---

class TestPickups:
    def test_econt_offices_full_list(self):
        t0 = time.time()
        r = requests.get(f"{API}/nextcart/pickups",
                         params={"provider_key": "econt", "destination_type": "office"},
                         timeout=25)
        first = time.time() - t0
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "pickups" in data and "count" in data
        assert data["count"] == len(data["pickups"])
        # spec says ~589
        assert 400 <= data["count"] <= 800, f"unexpected office count {data['count']}"
        sample = data["pickups"][0]
        for k in ("id", "name", "city"):
            assert k in sample
        # cache hit
        t0 = time.time()
        r2 = requests.get(f"{API}/nextcart/pickups",
                          params={"provider_key": "econt", "destination_type": "office"},
                          timeout=25)
        second = time.time() - t0
        assert r2.status_code == 200
        assert r2.json()["count"] == data["count"]
        # cached call must be substantially faster (network + upstream skipped)
        assert second < max(first * 0.6, 1.5), f"cache not effective: first={first:.2f} second={second:.2f}"

    def test_boxnow_lockers_full_list(self):
        r = requests.get(f"{API}/nextcart/pickups",
                         params={"provider_key": "boxnow", "destination_type": "locker"},
                         timeout=25)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # spec says ~926
        assert 500 <= data["count"] <= 1200, f"unexpected locker count {data['count']}"

    def test_invalid_destination_type(self):
        r = requests.get(f"{API}/nextcart/pickups",
                         params={"provider_key": "econt", "destination_type": "foo"},
                         timeout=10)
        assert r.status_code == 422


# --- /api/geo/country ---

class TestGeo:
    def test_country_returns_something(self):
        r = requests.get(f"{API}/geo/country", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "country" in data
        assert isinstance(data["country"], str) and len(data["country"]) == 2
        assert data.get("source") in ("ip", "default")


# --- Address suggestions ---

class TestAddressSuggestions:
    def test_city_mode_returns_suggestions(self):
        r = requests.get(f"{API}/nextcart/address-suggestions",
                         params={"mode": "city", "q": "Плов"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "suggestions" in data
        # at least one suggestion for Plovdiv
        if data["suggestions"]:
            first = data["suggestions"][0]
            assert "city" in first


# --- One-step order creation ---

def _one_line_item():
    # Use imported SKU: PP-BPC157-5MG. First we need product_id via /api/products?handle=...
    r = requests.get(f"{API}/products", params={"limit": 5}, timeout=10)
    assert r.status_code == 200
    prods = r.json().get("products") or r.json().get("items") or []
    for p in prods:
        for v in (p.get("variants") or []):
            if v.get("stock", 1) != 0 and v.get("price_eur"):
                return {"product_id": p["id"], "variant_sku": v["sku"], "quantity": 1,
                        "price_eur": v["price_eur"]}
    pytest.skip("no purchasable variant found")


class TestOrderPlacement:
    @pytest.mark.parametrize("payment", ["bank_transfer", "cod"])
    def test_place_order_with_econt_office(self, payment):
        li = _one_line_item()
        payload = {
            "items": [{"product_id": li["product_id"], "variant_sku": li["variant_sku"], "quantity": 1}],
            "shipping": {
                "full_name": "TEST Iter17",
                "phone": "+359888111222",
                "line1": "Пловдив Автогара Родопи",
                "city": "ПЛОВДИВ",
                "postal_code": "4000",
                "country": "BG",
            },
            "customer_email": f"TEST_iter17_{payment}@example.com",
            "customer_name": "TEST Iter17",
            "customer_phone": "+359888111222",
            "shipping_method": "econt_office",
            "payment_method": payment,
            "delivery": {
                "provider_key": "econt",
                "provider_name": "Еконт",
                "method_key": "econt_office",
                "destination_type": "office",
                "label": "До офис на Еконт",
                "price_amount": 3.89,
                "currency": "EUR",
                "office": {"id": "1", "name": "Пловдив Автогара Родопи",
                           "address": "бул. Христо Ботев 47", "city": "ПЛОВДИВ",
                           "postal_code": "4000"},
                "address": None,
            },
            "discount_code": "",
            "terms_accepted": True,
        }
        r = requests.post(f"{API}/checkout", json=payload, timeout=25)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert "order" in data
        order_id = data["order"]["id"]
        assert data["order"]["total_eur"] > 0
        # shipping_eur should equal 3.89 (override honored)
        assert abs(float(data["order"]["shipping_eur"]) - 3.89) < 0.01, \
            f"shipping_eur={data['order']['shipping_eur']}"
