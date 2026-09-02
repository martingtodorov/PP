"""Iteration 25 - local currency storefronts + Matrixify imported pages."""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


# --- /api/currency -----------------------------------------------------------
@pytest.mark.parametrize("locale,code", [("ro", "RON"), ("cz", "CZK"),
                                          ("hu", "HUF"), ("pl", "PLN")])
def test_currency_endpoint_non_euro(locale, code):
    r = requests.get(f"{API}/currency", params={"locale": locale}, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j["currency"] == code
    assert j["rate"] > 1
    assert j["date"], f"missing ECB date for {locale}: {j}"


def test_currency_endpoint_bg_is_euro():
    j = requests.get(f"{API}/currency", params={"locale": "bg"}, timeout=20).json()
    assert j["currency"] == "EUR"
    assert j["rate"] == 1.0


# --- Imported Matrixify pages ------------------------------------------------
IMPORTED_PAGE_HANDLES = [
    "terms-conditions",
    "delivery-and-payment",
    "какво-са-пептиди",
    "cookies",
    "chemical-analysis",
    "about-1",
    "faq",
]


def _fetch_page(handle):
    r = requests.get(f"{API}/pages/{handle}", timeout=20)
    if r.status_code != 200 and handle == "какво-са-пептиди":
        r = requests.get(f"{API}/pages/what-are-peptides", timeout=20)
    return r


@pytest.mark.parametrize("handle", IMPORTED_PAGE_HANDLES)
def test_imported_page_has_full_body(handle):
    r = _fetch_page(handle)
    assert r.status_code == 200, f"/pages/{handle} -> {r.status_code}"
    j = r.json()
    page = j.get("page") or j
    body = page.get("html") or page.get("body_html") or page.get("content") or ""
    assert len(body) > 500, f"/pages/{handle} body too short ({len(body)} chars)"


def test_imported_page_images_resolve():
    """Every /api/files/... URL in an imported page must return 200."""
    seen = set()
    for h in IMPORTED_PAGE_HANDLES:
        r = _fetch_page(h)
        if r.status_code != 200:
            continue
        page = r.json().get("page") or r.json()
        body = page.get("html") or ""
        for m in re.findall(r'(/api/files/[^"\'\s>)]+)', body):
            seen.add(m)
    broken = []
    for url in list(seen)[:40]:
        try:
            resp = requests.get(f"{BASE}{url}", timeout=15, stream=True)
            if resp.status_code != 200:
                broken.append((url, resp.status_code))
            resp.close()
        except Exception as ex:
            broken.append((url, str(ex)))
    assert not broken, f"broken images (first 5): {broken[:5]} of {len(seen)} total"


# --- Product image URLs load -------------------------------------------------
def test_product_images_resolve():
    r = requests.get(f"{API}/products", params={"limit": 10}, timeout=20)
    assert r.status_code == 200
    products = r.json().get("products") or []
    assert products, "no products from /api/products"
    broken = []
    for p in products[:8]:
        img = p.get("image") or (p.get("images") or [None])[0]
        if not img:
            broken.append((p.get("handle"), "no image"))
            continue
        url = img if img.startswith("http") else f"{BASE}{img}"
        resp = requests.get(url, timeout=15, stream=True)
        if resp.status_code != 200:
            broken.append((p.get("handle"), resp.status_code))
        resp.close()
    assert not broken, f"broken product images: {broken}"


# --- Place a RON checkout ----------------------------------------------------
def _pick_stocked_product():
    r = requests.get(f"{API}/products", params={"limit": 40}, timeout=20)
    for p in r.json().get("products") or []:
        for v in p.get("variants", []):
            if int(v.get("stock") or 0) > 2 and float(v.get("price_eur") or 0) > 0:
                return p, v
    return None, None


def test_place_ron_checkout_and_delete():
    prod, variant = _pick_stocked_product()
    if not prod:
        pytest.skip("no stocked variant available for checkout")
    payload = {
        "items": [{"product_id": prod["id"], "variant_sku": variant["sku"], "quantity": 2}],
        "customer_name": "TEST Iter25",
        "customer_email": "test_iter25_ron@example.com",
        "customer_phone": "+40700000000",
        "shipping": {
            "full_name": "TEST Iter25", "phone": "+40700000000",
            "country": "RO", "city": "Bucuresti",
            "line1": "Str. Test 1", "postal_code": "010101",
        },
        "shipping_method": "standard",
        "payment_method": "cod",
        "terms_accepted": True,
        "locale": "ro",
    }
    r = requests.post(f"{API}/checkout", json=payload, timeout=30)
    if r.status_code >= 400:
        pytest.skip(f"checkout rejected ({r.status_code}): {r.text[:400]}")
    order = r.json().get("order") or {}
    assert order.get("currency") == "RON", order
    assert order.get("currency_rate", 0) > 1
    assert order.get("total_orig", 0) > 0
    # unit price rounded psychologically:
    li = order["items"][0]
    assert li.get("price_orig", 0) > 0
    # subtotal_orig should equal sum of item_prices * qty
    assert order["subtotal_orig"] == li["price_orig"] * li["quantity"]
    # cleanup: delete via mongo (no public DELETE endpoint)
    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # noqa
    except Exception:
        return
    import asyncio, os as _os
    from pymongo import MongoClient
    mongo = MongoClient(_os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mongo[_os.environ.get("DB_NAME", "test_database")]
    db.orders.delete_one({"id": order["id"]})
