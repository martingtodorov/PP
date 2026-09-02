"""Iteration 26 — RETEST after the cart/checkout local-currency fix and dynamic links.

Focus:
1. /ro end-to-end price consistency: /api/currency -> nice_price mirror -> /api/checkout total.
2. /cz /hu /pl same shape; /bg /de /en still EUR.
3. Place a COD-style order on /ro, confirm success/detail totals match, then clean up.
4. /api/links: every logical key resolves, each target opens with real content.
"""
import os
import sys
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

from currency import nice_price, order_amounts  # noqa: E402
from links_map import LINK_TARGETS  # noqa: E402


# --- currency helpers ---

def _fx(locale):
    return requests.get(f"{API}/currency", params={"locale": locale}, timeout=20).json()


def _pick_product():
    """Return a real in-stock product/variant to build a checkout payload."""
    products = requests.get(f"{API}/products", params={"limit": 200}, timeout=30).json()
    if isinstance(products, dict):
        products = products.get("items") or products.get("products") or []
    for p in products:
        for v in p.get("variants") or []:
            price = v.get("price_eur") or v.get("price") or 0
            if (v.get("stock") or 0) > 0 and price > 0:
                return p, v
    pytest.skip("no in-stock variant available")


# --- 1. RON round-trip ---

class TestRonEndToEnd:
    def test_currency_endpoint_returns_dated_ron_rate(self):
        fx = _fx("ro")
        assert fx["currency"] == "RON"
        assert fx["rate"] > 1 and fx["date"]

    def test_29_eur_rounds_to_159_lei_when_rate_is_reasonable(self):
        fx = _fx("ro")
        # keep in sync with the frontend money.js and backend currency.py
        assert nice_price(29, "RON", fx["rate"]) == 159, (
            f"29 EUR at {fx['rate']} should still round to 159 lei psychologically")

    def test_order_amounts_mirrors_backend(self):
        fx = _fx("ro")
        items = [{"price_eur": 29.0, "quantity": 2}]
        out = order_amounts(items, {"shipping_eur": 5.99, "discount_eur": 0}, {},
                            "RON", fx["rate"])
        assert out["item_prices"] == [nice_price(29, "RON", fx["rate"])]
        assert out["subtotal_orig"] == nice_price(29, "RON", fx["rate"]) * 2
        assert out["shipping_orig"] == nice_price(5.99, "RON", fx["rate"])
        assert out["total_orig"] == out["subtotal_orig"] + out["shipping_orig"]


# --- 2. non-BG storefront currency shape ---

@pytest.mark.parametrize("locale,code", [("ro", "RON"), ("cz", "CZK"),
                                          ("hu", "HUF"), ("pl", "PLN")])
def test_local_currency_is_switched_for(locale, code):
    fx = _fx(locale)
    assert fx["currency"] == code and fx["rate"] > 1 and fx["date"]


@pytest.mark.parametrize("locale", ["bg", "de", "en", "gr"])
def test_euro_locales_stay_euro(locale):
    fx = _fx(locale)
    assert fx["currency"] == "EUR" and fx["rate"] == 1.0 and fx["date"] is None


# --- 3. Real /ro checkout, verify recorded order matches computed total, cleanup ---

class TestRoCheckoutRoundTrip:
    order_ids = []

    @classmethod
    def teardown_class(cls):
        for oid in cls.order_ids:
            DB.orders.delete_one({"id": oid})

    def test_place_ro_order_and_verify_total(self):
        fx = _fx("ro")
        product, variant = _pick_product()
        qty = 2
        price_eur = float(variant.get("price_eur") or variant.get("price"))
        payload = {
            "items": [{"product_id": product["id"],
                       "variant_sku": variant["sku"], "quantity": qty}],
            "shipping": {"full_name": "TEST Iter26", "phone": "+40711111111",
                         "email": "TEST_iter26_ro@example.com",
                         "line1": "Str. Test 1", "city": "Bucuresti",
                         "postal_code": "010101", "country": "RO"},
            "customer_email": "TEST_iter26_ro@example.com",
            "customer_name": "TEST Iter26",
            "customer_phone": "+40711111111",
            "shipping_method": "econt_address",
            "notes": "iter26 automated test",
            "terms_accepted": True,
            "locale": "ro",
        }
        r = requests.post(f"{API}/checkout", json=payload,
                          headers={"X-Locale": "ro"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        oid = data["order"]["id"]
        self.__class__.order_ids.append(oid)

        # persisted totals must equal the mirror computation
        order = DB.orders.find_one({"id": oid})
        assert order is not None
        assert order.get("currency") == "RON"
        expected_line = nice_price(price_eur, "RON", order["currency_rate"])
        expected_subtotal = expected_line * qty
        expected_shipping = nice_price(order.get("shipping_eur") or 0,
                                        "RON", order["currency_rate"])
        expected_total = expected_subtotal + expected_shipping
        assert order["subtotal_orig"] == expected_subtotal
        assert order["shipping_orig"] == expected_shipping
        assert order["total_orig"] == expected_total, (
            f"persisted total {order['total_orig']} != computed {expected_total}")

        # admin/detail endpoint reports RON amounts too
        detail_resp = requests.get(f"{API}/orders/{oid}", timeout=20)
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        # be tolerant of wrapper shape ({order: {...}} vs flat)
        node = detail.get("order") if isinstance(detail.get("order"), dict) else detail
        display_total = (node.get("total_display") or node.get("total_orig")
                         or node.get("total"))
        assert display_total == expected_total, (
            f"detail total {display_total} != {expected_total}; keys={list(node.keys())}")


# --- 4. Dynamic links ---

class TestDynamicLinks:
    def test_every_key_resolves_for_bg(self):
        data = requests.get(f"{API}/links", params={"locale": "bg"},
                            timeout=20).json()
        for key in LINK_TARGETS:
            assert data.get(key), f"missing link key {key}"

    def test_targets_open_with_real_content(self):
        data = requests.get(f"{API}/links", params={"locale": "bg"},
                            timeout=20).json()
        # pages we know Shopify export left thin (from the review's other_misc_info)
        thin_ok = {"contacts", "scientificLiterature", "refund"}
        for key, path in data.items():
            if path.startswith("/pages/"):
                slug = path.rsplit("/", 1)[-1]
                r = requests.get(f"{API}/pages/{slug}",
                                 params={"locale": "bg"}, timeout=20)
                assert r.status_code == 200, f"{key} -> {slug} = {r.status_code}"
                body = r.json().get("page") or {}
                text = body.get("html") or body.get("body_html") or body.get("content") or ""
                if key not in thin_ok:
                    assert len(text) > 400, f"{key} body too short ({len(text)})"
            elif path.startswith("/collections/"):
                slug = path.rsplit("/", 1)[-1]
                r = requests.get(f"{API}/collections/{slug}",
                                 params={"locale": "bg"}, timeout=20)
                assert r.status_code == 200, f"{key} -> {slug} = {r.status_code}"

    def test_imported_page_bodies_intact(self):
        # explicit slugs the review calls out
        for slug in ["terms-conditions", "delivery-and-payment",
                     "какво-са-пептиди", "cookies", "about-1", "faq"]:
            r = requests.get(f"{API}/pages/{slug}",
                             params={"locale": "bg"}, timeout=20)
            assert r.status_code == 200, slug
            body = r.json().get("page") or {}
            text = body.get("html") or body.get("body_html") or ""
            assert len(text) > 500, f"{slug} body only {len(text)} chars"
