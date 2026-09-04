"""A courier chosen for another country must never reach checkout (order WER27: Econt to France)."""
import os

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _cleanup(order):
    """Test orders must not stay in the shop's books — restock and delete."""
    for li in order.get("items") or []:
        DB.products.update_one({"id": li["product_id"], "variants.sku": li["variant_sku"]},
                               {"$inc": {"variants.$.stock": li["quantity"]}})
    DB.orders.delete_one({"id": order["id"]})
    DB.inventory_log.delete_many({"reason": {"$regex": order["order_number"]}})


def _product():
    for p in requests.get(f"{API}/products", params={"locale": "bg"}, timeout=30).json()["products"]:
        for v in p["variants"]:
            if (v.get("stock") or 0) > 0:
                return p["id"], v["sku"]
    raise AssertionError("no product in stock")


def _payload(country, provider, method_key, price):
    pid, sku = _product()
    return {
        "items": [{"product_id": pid, "variant_sku": sku, "quantity": 1}],
        "shipping": {"full_name": "Stale Selection", "phone": "+33699686974", "line1": "1 rue de Test",
                     "city": "Paris", "postal_code": "75001", "country": country},
        "customer_email": "stale-selection@example.com", "customer_name": "Stale Selection",
        "customer_phone": "+33699686974", "shipping_method": method_key,
        "payment_method": "bank_transfer", "terms_accepted": True, "locale": "fr",
        "delivery": {"provider_key": provider, "provider_name": provider, "method_key": method_key,
                     "destination_type": "address", "label": "to address", "price_amount": price,
                     "currency": "EUR", "address": {"city": "Paris"}},
    }


def test_a_bulgarian_courier_is_swapped_for_the_one_serving_france():
    """Econt does not ship to France — the order becomes a GLS address delivery, not an error."""
    r = requests.post(f"{API}/checkout", json=_payload("FR", "econt", "econt_address", 4.99), timeout=60)
    assert r.status_code == 200, r.text[:300]
    o = r.json()["order"]
    assert o["delivery"]["provider_key"] == "gls"
    assert o["payment_method"] == "bank_transfer" and o["shipping_eur"] == 0.0   # prepaid ships free
    _cleanup(o)


def test_an_unknown_delivery_selection_is_rejected():
    body = _payload("FR", "gls", "gls_teleport", 0.5)
    body["delivery"]["destination_type"] = "teleport"
    r = requests.post(f"{API}/checkout", json=body, timeout=60)
    assert r.status_code == 400, r.text[:300]


def test_the_offer_of_the_destination_country_is_validated_server_side():
    import asyncio
    from importlib import import_module
    resolve = import_module("nextcart").resolve_delivery
    fr = asyncio.run(resolve("FR", "econt", "econt_address", "address"))
    assert fr["ok"] and fr["price"] == 8.99 and fr["method"]["provider_key"] == "gls"
    assert asyncio.run(resolve("FR", "econt", "econt_office", "office"))["ok"] is False
    assert asyncio.run(resolve("BG", "econt", "econt_address", "address"))["price"] == 4.99
    assert asyncio.run(resolve("FR", "gls", "gls_address", "address"))["price"] == 8.99


def test_bank_transfer_orders_ship_free():
    body = _payload("BG", "econt", "econt_address", 4.99)
    body["shipping"].update({"country": "BG", "city": "София", "postal_code": "1000", "line1": "ул. Тест 1"})
    body["payment_method"] = "bank_transfer"
    r = requests.post(f"{API}/checkout", json=body, timeout=60)
    assert r.status_code == 200, r.text[:300]
    o = r.json()["order"]
    assert o["shipping_eur"] == 0.0 and o["delivery"]["price_amount"] == 0.0
    assert o["total_eur"] == o["subtotal_eur"]
    _cleanup(o)


def test_cash_on_delivery_still_pays_the_courier_price():
    body = _payload("BG", "econt", "econt_address", 99.0)
    body["shipping"].update({"country": "BG", "city": "София", "postal_code": "1000", "line1": "ул. Тест 1"})
    body["payment_method"] = "cod"
    r = requests.post(f"{API}/checkout", json=body, timeout=60)
    assert r.status_code == 200, r.text[:300]
    o = r.json()["order"]
    assert o["shipping_eur"] == 4.99, o["shipping_eur"]
    _cleanup(o)
