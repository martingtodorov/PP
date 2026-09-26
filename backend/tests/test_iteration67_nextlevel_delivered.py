"""Iteration 67 — NextLevel 'delivered' marks the order paid+delivered automatically.

Covers:
* pytest of nextlevel.mark_delivered against the preview Mongo
* admin API filters (delivered / unfulfilled / detail)
* public tracking endpoint (steps.paid & steps.delivered)
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

# --- allow importing backend package ---------------------------------------
BACKEND_DIR = Path("/app/backend")
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

BASE_URL = os.environ["PUBLIC_SITE_URL"].rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PW = os.environ["ADMIN_PASSWORD"]
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ---------- fixtures -------------------------------------------------------
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def db(event_loop):
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(MONGO_URL, io_loop=event_loop)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# helper to run an async coroutine
def run(loop, coro):
    return loop.run_until_complete(coro)


# ---------- mark_delivered (COD path) --------------------------------------
def test_mark_delivered_sets_paid_and_delivered(event_loop, db):
    import nextlevel
    nextlevel._db = db
    loop = event_loop

    # pick a COD order that is NOT already delivered
    order = run(loop, db.orders.find_one(
        {"payment_method": "cod", "status": {"$ne": "cancelled"},
         "fulfillment_status": {"$ne": "delivered"}}, {"_id": 0}))
    if not order:
        pytest.skip("no eligible COD order in preview DB")

    order_id = order["id"]
    original = {
        "payment_status": order.get("payment_status"),
        "paid_at": order.get("paid_at"),
        "paid_by": order.get("paid_by"),
        "fulfillment_status": order.get("fulfillment_status"),
        "status": order.get("status"),
        "shipment": order.get("shipment") or {},
    }
    unset_keys = [k for k in ("paid_at", "paid_by") if original[k] is None]

    try:
        # call mark_delivered
        run(loop, nextlevel.mark_delivered(order_id))
        after = run(loop, db.orders.find_one({"id": order_id}, {"_id": 0}))
        assert after["payment_status"] == "paid"
        assert after["paid_by"] == "nextlevel_delivered"
        assert after["fulfillment_status"] == "delivered"
        assert after["status"] == "delivered"
        assert (after.get("shipment") or {}).get("delivered_at")

        first_notified = (after.get("shipment") or {}).get("delivered_notified_at")

        # second call — must not re-notify
        run(loop, nextlevel.mark_delivered(order_id))
        after2 = run(loop, db.orders.find_one({"id": order_id}, {"_id": 0}))
        second_notified = (after2.get("shipment") or {}).get("delivered_notified_at")
        assert first_notified == second_notified, "delivered_notified_at changed on second call"
    finally:
        # restore
        setops = {"fulfillment_status": original["fulfillment_status"],
                  "status": original["status"],
                  "shipment": original["shipment"]}
        if original["payment_status"] is not None:
            setops["payment_status"] = original["payment_status"]
        if original["paid_at"] is not None:
            setops["paid_at"] = original["paid_at"]
        if original["paid_by"] is not None:
            setops["paid_by"] = original["paid_by"]
        unset_map = {k: "" for k in unset_keys}
        upd = {"$set": setops}
        if unset_map:
            upd["$unset"] = unset_map
        run(loop, db.orders.update_one({"id": order_id}, upd))


# ---------- mark_delivered on already-paid order ---------------------------
def test_mark_delivered_preserves_paid_at_and_paid_by(event_loop, db):
    import nextlevel
    nextlevel._db = db
    loop = event_loop

    order = run(loop, db.orders.find_one(
        {"status": {"$ne": "cancelled"},
         "fulfillment_status": {"$ne": "delivered"}}, {"_id": 0}))
    if not order:
        pytest.skip("no eligible order")

    order_id = order["id"]
    original = {k: order.get(k) for k in
                ("payment_status", "paid_at", "paid_by",
                 "fulfillment_status", "status")}
    original["shipment"] = order.get("shipment") or {}

    # force it to paid via bank_transfer
    run(loop, db.orders.update_one({"id": order_id}, {"$set": {
        "payment_status": "paid",
        "paid_at": "2025-01-01T00:00:00+00:00",
        "paid_by": "bank_transfer",
    }}))

    try:
        run(loop, nextlevel.mark_delivered(order_id))
        after = run(loop, db.orders.find_one({"id": order_id}, {"_id": 0}))
        assert after["payment_status"] == "paid"
        # must NOT overwrite prior paid_at / paid_by
        assert after["paid_at"] == "2025-01-01T00:00:00+00:00"
        assert after["paid_by"] == "bank_transfer"
        assert after["fulfillment_status"] == "delivered"
        assert after["status"] == "delivered"
        assert (after.get("shipment") or {}).get("delivered_at")
    finally:
        setops = {"fulfillment_status": original["fulfillment_status"],
                  "status": original["status"],
                  "shipment": original["shipment"]}
        unset_map = {}
        for k in ("payment_status", "paid_at", "paid_by"):
            if original[k] is None:
                unset_map[k] = ""
            else:
                setops[k] = original[k]
        upd = {"$set": setops}
        if unset_map:
            upd["$unset"] = unset_map
        run(loop, db.orders.update_one({"id": order_id}, upd))


# ---------- admin filters + track view -------------------------------------
def test_admin_filters_and_track(event_loop, db, admin_headers):
    """Mark an order delivered, hit the admin/track APIs, then restore."""
    import nextlevel
    nextlevel._db = db
    loop = event_loop

    order = run(loop, db.orders.find_one(
        {"payment_method": "cod",
         "status": {"$ne": "cancelled"},
         "fulfillment_status": {"$ne": "delivered"},
         "customer_email": {"$nin": ["", None]}}, {"_id": 0}))
    if not order:
        pytest.skip("no eligible COD order with email")

    order_id = order["id"]
    order_number = order["order_number"]
    customer_email = order["customer_email"]
    customer_phone = order.get("customer_phone") or (order.get("shipping") or {}).get("phone") or ""
    original = {k: order.get(k) for k in
                ("payment_status", "paid_at", "paid_by",
                 "fulfillment_status", "status")}
    original["shipment"] = order.get("shipment") or {}
    unset_keys = [k for k in ("paid_at", "paid_by") if original[k] is None]

    try:
        run(loop, nextlevel.mark_delivered(order_id))

        # admin/orders?status=delivered
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"status": "delivered", "limit": 200},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        ids = [o["id"] for o in r.json().get("orders", [])]
        assert order_id in ids, "delivered order missing from status=delivered listing"

        # admin/orders?status=unfulfilled — must NOT include it
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"status": "unfulfilled", "limit": 200},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert order_id not in [o["id"] for o in r.json().get("orders", [])]

        # detail
        r = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json().get("order") or r.json()
        assert d["payment_status"] == "paid"
        assert d["fulfillment_status"] == "delivered"

        # public track (endpoint requires order_number + phone)
        r = requests.post(f"{BASE_URL}/api/orders/track",
                          json={"order_number": order_number,
                                "phone": customer_phone}, timeout=30)
        assert r.status_code == 200, r.text
        steps = ((r.json().get("order") or {}).get("steps") or {})
        assert steps.get("paid") is True, f"steps.paid not true: {steps}"
        assert steps.get("delivered") is True, f"steps.delivered not true: {steps}"
    finally:
        setops = {"fulfillment_status": original["fulfillment_status"],
                  "status": original["status"],
                  "shipment": original["shipment"]}
        if original["payment_status"] is not None:
            setops["payment_status"] = original["payment_status"]
        if original["paid_at"] is not None:
            setops["paid_at"] = original["paid_at"]
        if original["paid_by"] is not None:
            setops["paid_by"] = original["paid_by"]
        upd = {"$set": setops}
        if unset_keys:
            upd["$unset"] = {k: "" for k in unset_keys}
        run(loop, db.orders.update_one({"id": order_id}, upd))
