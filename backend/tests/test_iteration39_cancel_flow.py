"""Iteration 39 — customer & admin order cancellation (integration).

Seeds fake orders directly in Mongo so the real NextLevel warehouse is not touched.
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PW = "Admin@PurePeptide2026"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def loop():
    l = asyncio.new_event_loop()
    yield l
    l.close()


@pytest.fixture(scope="module")
def db(loop):
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, r.text
    return s


async def _pick_product(db):
    p = await db.products.find_one({"variants.0": {"$exists": True}}, {"_id": 0})
    assert p, "no product with variant in DB"
    v = p["variants"][0]
    return p, v


async def _seed_order(db, *, order_id, order_number, fulfillment_status="unfulfilled",
                      status="pending", payment_status="awaiting_payment", email="TEST_cancel@example.com"):
    p, v = await _pick_product(db)
    doc = {
        "id": order_id,
        "order_number": order_number,
        "status": status,
        "payment_status": payment_status,
        "fulfillment_status": fulfillment_status,
        "customer_email": email,
        "customer_info": {"email": email, "first_name": "TEST", "last_name": "Cancel",
                          "phone": "+359888000000", "country": "BG", "city": "Sofia",
                          "address": "TEST 1", "postcode": "1000"},
        "items": [{
            "product_id": p["id"], "product_name": p.get("name", "TEST"),
            "variant_sku": v["sku"], "variant_name": v.get("name", "default"),
            "quantity": 1, "price_eur": float(v.get("price") or 10),
        }],
        "total_eur": float(v.get("price") or 10),
        "currency": "EUR",
        "notes": "cancel-selftest",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.orders.insert_one(doc)
    return doc, p, v


def _run(loop, coro):
    return loop.run_until_complete(coro)


def test_customer_cancel_endpoint(loop, db, admin_session):
    """POST /api/orders/{id}/cancel — cancels a fresh order, restores stock, logs inventory."""
    oid = f"TEST-{uuid.uuid4().hex[:10]}"
    onum = f"TEST-{uuid.uuid4().hex[:6].upper()}"

    async def prep():
        doc, p, v = await _seed_order(db, order_id=oid, order_number=onum)
        stock_before = int(v.get("stock") or 0)
        return stock_before, p["id"], v["sku"]

    stock_before, pid, sku = _run(loop, prep())

    # cancel as guest (no auth cookie)
    r = requests.post(f"{BASE}/orders/{oid}/cancel", json={"reason": "changed my mind"}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True

    # verify persistence via GET
    r2 = requests.get(f"{BASE}/orders/{oid}", timeout=15)
    assert r2.status_code == 200, r2.text
    got = r2.json().get("order", {})
    assert got["status"] == "cancelled"
    assert got["payment_status"] == "cancelled"
    assert got["fulfillment_status"] == "cancelled"
    assert got["cancellable"] is False
    assert got.get("cancelled_by")
    assert got.get("cancel_reason") == "changed my mind"

    # stock restored (+1)
    async def check():
        p = await db.products.find_one({"id": pid}, {"_id": 0})
        v = next(x for x in p["variants"] if x["sku"] == sku)
        assert int(v.get("stock") or 0) == stock_before + 1
        # inventory log exists
        row = await db.inventory_log.find_one({"reason": f"Отказана поръчка {onum}"})
        assert row is not None
        assert row["change"] > 0
        # cleanup
        await db.orders.delete_one({"id": oid})
        await db.inventory_log.delete_many({"reason": f"Отказана поръчка {onum}"})
        await db.products.update_one({"id": pid, "variants.sku": sku}, {"$inc": {"variants.$.stock": -1}})

    _run(loop, check())


def test_customer_cancel_twice_returns_400(loop, db):
    oid = f"TEST-{uuid.uuid4().hex[:10]}"
    onum = f"TEST-{uuid.uuid4().hex[:6].upper()}"

    async def prep():
        return await _seed_order(db, order_id=oid, order_number=onum, status="cancelled",
                                 payment_status="cancelled", fulfillment_status="cancelled")
    _run(loop, prep())

    r = requests.post(f"{BASE}/orders/{oid}/cancel", json={"reason": ""}, timeout=15)
    assert r.status_code == 400
    assert "вече е отказана" in r.json().get("detail", "")

    _run(loop, db.orders.delete_one({"id": oid}))


def test_shipped_order_cannot_be_cancelled(loop, db, admin_session):
    oid = f"TEST-{uuid.uuid4().hex[:10]}"
    onum = f"TEST-{uuid.uuid4().hex[:6].upper()}"

    async def prep():
        await _seed_order(db, order_id=oid, order_number=onum, fulfillment_status="shipped")
    _run(loop, prep())

    # customer endpoint
    r = requests.post(f"{BASE}/orders/{oid}/cancel", json={"reason": ""}, timeout=15)
    assert r.status_code == 400
    assert "изпратена" in r.json().get("detail", "")

    # admin endpoint should also refuse
    r2 = admin_session.post(f"{BASE}/admin/orders/{oid}/cancel", json={"reason": "test"}, timeout=15)
    assert r2.status_code == 400
    assert "изпратена" in r2.json().get("detail", "")

    _run(loop, db.orders.delete_one({"id": oid}))


def test_admin_cancel_endpoint(loop, db, admin_session):
    oid = f"TEST-{uuid.uuid4().hex[:10]}"
    onum = f"TEST-{uuid.uuid4().hex[:6].upper()}"

    async def prep():
        doc, p, v = await _seed_order(db, order_id=oid, order_number=onum)
        return p["id"], v["sku"], int(v.get("stock") or 0)
    pid, sku, stock_before = _run(loop, prep())

    r = admin_session.post(f"{BASE}/admin/orders/{oid}/cancel",
                           json={"reason": "admin test cancel"}, timeout=15)
    assert r.status_code == 200, r.text

    # admin detail view shows cancellation info
    r2 = admin_session.get(f"{BASE}/admin/orders/{oid}", timeout=15)
    assert r2.status_code == 200
    got = r2.json().get("order", {})
    assert got["payment_status"] == "cancelled"
    assert got["fulfillment_status"] == "cancelled"
    assert got.get("cancelled_by", "").startswith("админ")
    assert got.get("cancel_reason") == "admin test cancel"

    async def cleanup():
        await db.orders.delete_one({"id": oid})
        await db.inventory_log.delete_many({"reason": f"Отказана поръчка {onum}"})
        await db.products.update_one({"id": pid, "variants.sku": sku}, {"$inc": {"variants.$.stock": -1}})
    _run(loop, cleanup())


def test_cancel_nonexistent_order_404(admin_session):
    r = requests.post(f"{BASE}/orders/does-not-exist/cancel", json={"reason": ""}, timeout=15)
    assert r.status_code == 404
    r2 = admin_session.post(f"{BASE}/admin/orders/does-not-exist/cancel", json={"reason": ""}, timeout=15)
    assert r2.status_code == 404


def test_admin_cancel_requires_auth():
    oid = "TEST-noauth"
    r = requests.post(f"{BASE}/admin/orders/{oid}/cancel", json={"reason": ""}, timeout=15)
    assert r.status_code in (401, 403)
