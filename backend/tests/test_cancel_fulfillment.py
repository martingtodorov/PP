"""Cancelling an order must cancel it in the NextLevel warehouse — or not cancel it at all."""
import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import fulfillment                       # noqa: E402
import server                            # noqa: E402
import wc_api                            # noqa: E402

ORDER_ID = f"cancel-test-{uuid.uuid4()}"


def _order(**extra):
    return {
        "id": ORDER_ID, "order_number": "CNL01", "currency": "EUR", "status": "awaiting_payment",
        "payment_status": "awaiting_payment", "fulfillment_status": "processing",
        "items": [], "subtotal_eur": 49.0, "shipping_eur": 0.0, "total_eur": 49.0,
        "customer_email": "", "payment_method": "cod",
        "fulfillment": {"number": "CNL01", "transport": "woocommerce", "status": "pending"},
        **extra,
    }


@pytest.fixture(autouse=True)
def order(monkeypatch):
    fulfillment.init(server.db, server.require_admin)
    asyncio.get_event_loop().run_until_complete(server.db.orders.insert_one(_order()))
    yield
    asyncio.get_event_loop().run_until_complete(server.db.orders.delete_one({"id": ORDER_ID}))


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def fake_push(status_code, response=None):
    async def push(order, cfg, topic="order.created"):
        assert topic == "order.updated" and order["status"] == "cancelled"
        return {"status_code": status_code, "response": response or {}}
    return push


def cfg(**over):
    async def get_config():
        return {**fulfillment.DEFAULTS, "webhook_url": "https://example.test/hook",
                "has_api": False, "has_wc": True, "shop_type": "woocommerce", **over}
    return get_config


def test_cancel_pushes_the_warehouse_and_records_the_confirmation(monkeypatch):
    monkeypatch.setattr(fulfillment, "get_config", cfg())
    monkeypatch.setattr(wc_api, "push_webhook", fake_push(200, {"ok": True}))
    res = run(fulfillment.cancel_order(ORDER_ID))
    assert res["cancelled"] is True and res["transport"] == "webhook"
    doc = run(server.db.orders.find_one({"id": ORDER_ID}))
    assert doc["fulfillment"]["status"] == "cancelled"
    assert doc["fulfillment"]["cancel_confirmed_at"] and "cancel_error" not in doc["fulfillment"]


def test_a_refused_cancel_is_recorded_and_raises(monkeypatch):
    monkeypatch.setattr(fulfillment, "get_config", cfg())
    monkeypatch.setattr(wc_api, "push_webhook", fake_push(500, {"error": "already shipped"}))
    with pytest.raises(HTTPException) as ex:
        run(fulfillment.cancel_order(ORDER_ID))
    assert ex.value.status_code == 502
    doc = run(server.db.orders.find_one({"id": ORDER_ID}))
    assert doc["fulfillment"]["cancel_error"] and doc["fulfillment"]["status"] == "pending"


def test_the_order_is_not_cancelled_when_the_warehouse_refuses(monkeypatch):
    monkeypatch.setattr(fulfillment, "get_config", cfg())
    monkeypatch.setattr(wc_api, "push_webhook", fake_push(500, {"error": "already shipped"}))
    o = run(server.db.orders.find_one({"id": ORDER_ID}, {"_id": 0}))
    with pytest.raises(HTTPException):
        run(server.perform_cancel(o, "тест", "проба"))
    doc = run(server.db.orders.find_one({"id": ORDER_ID}))
    assert doc["status"] != "cancelled" and doc["payment_status"] != "cancelled"


def test_force_cancels_locally_even_when_the_warehouse_refuses(monkeypatch):
    monkeypatch.setattr(fulfillment, "get_config", cfg())
    monkeypatch.setattr(wc_api, "push_webhook", fake_push(500, {"error": "nope"}))
    o = run(server.db.orders.find_one({"id": ORDER_ID}, {"_id": 0}))
    res = run(server.perform_cancel(o, "тест", "проба", force=True))
    assert res["ok"] is True and res["courier"]["fulfillment_error"]
    doc = run(server.db.orders.find_one({"id": ORDER_ID}))
    assert doc["status"] == "cancelled" and doc["fulfillment_status"] == "cancelled"


def test_a_cancel_without_a_warehouse_order_is_rejected(monkeypatch):
    monkeypatch.setattr(fulfillment, "get_config", cfg())
    run(server.db.orders.update_one({"id": ORDER_ID}, {"$unset": {"fulfillment": ""}}))
    with pytest.raises(HTTPException) as ex:
        run(fulfillment.cancel_order(ORDER_ID))
    assert ex.value.status_code == 404


def test_a_missing_integration_is_reported_instead_of_silently_skipped(monkeypatch):
    monkeypatch.setattr(fulfillment, "get_config", cfg(webhook_url="", has_api=False))
    with pytest.raises(HTTPException) as ex:
        run(fulfillment.cancel_order(ORDER_ID))
    assert "Админ → Интеграции" in str(ex.value.detail)


def test_a_warehouse_side_cancel_cancels_the_order_here(monkeypatch):
    """NextLevel cancels in their panel → the shop mirrors it, without pushing anything back."""
    pushed = []

    async def push(order, cfg_, topic="order.created"):
        pushed.append(topic)
        return {"status_code": 200, "response": {}}

    monkeypatch.setattr(fulfillment, "get_config", cfg())
    monkeypatch.setattr(wc_api, "push_webhook", push)
    wc_api.init(server.db, fulfillment.get_config)
    fulfillment.set_cancel_hook(server._cancel_from_warehouse)
    o = run(server.db.orders.find_one({"id": ORDER_ID}, {"_id": 0}))
    run(wc_api._apply_update(o, {"status": "cancelled"}))
    doc = run(server.db.orders.find_one({"id": ORDER_ID}))
    assert doc["status"] == "cancelled" and doc["cancelled_by"].startswith("склад")
    assert pushed == []
