"""A customer who has paid must never get the „you forgot something in your cart" e-mail.

The checkout form debounces the cart snapshot by 1.5 s, so the snapshot could land AFTER the order
was placed: a fresh "open" cart appeared, the sweeper only looked for orders newer than that cart,
found none and mailed the buyer. Reported by the owner on 21.06.2026.
"""
import uuid
from datetime import datetime, timedelta, timezone

import abandoned
import email_service
import server
from conftest import run

abandoned.init(server.db, server.require_admin)


def _iso(dt):
    return dt.isoformat()


def _order(email, when):
    return {"id": str(uuid.uuid4()), "order_number": "PP-TEST", "customer_email": email,
            "customer_name": "Тест", "created_at": _iso(when), "items": [], "total_eur": 10.0}


def _cart(email, created, updated):
    return {"id": str(uuid.uuid4()), "email": email, "customer_name": "Тест", "phone": "",
            "locale": "bg", "items": [{"title": "BPC-157", "price_eur": 29.0, "quantity": 1}],
            "subtotal_eur": 29.0, "status": "open", "created_at": created, "updated_at": updated,
            "reminded_at": None}


def _cleanup(email):
    run(abandoned._db.orders.delete_many({"customer_email": email}))
    run(abandoned._db.abandoned_carts.delete_many({"email": email}))


def test_a_snapshot_that_lands_after_the_order_is_not_tracked():
    email = f"buyer-{uuid.uuid4().hex[:6]}@example.com"
    now = datetime.now(timezone.utc)
    run(abandoned._db.orders.insert_one(_order(email, now - timedelta(seconds=5))))
    try:
        payload = abandoned.CartTrackIn(email=email, locale="bg",
                                        items=[{"title": "BPC-157", "price_eur": 29.0, "quantity": 1}])
        assert run(abandoned.track_cart(payload)).get("skipped") == "ordered"
        assert run(abandoned._db.abandoned_carts.find_one({"email": email, "status": "open"})) is None
    finally:
        _cleanup(email)


def test_the_sweeper_never_mails_a_customer_who_ordered_just_before():
    email = f"buyer-{uuid.uuid4().hex[:6]}@example.com"
    now = datetime.now(timezone.utc)
    run(abandoned._db.orders.insert_one(_order(email, now - timedelta(hours=3))))
    # the cart record was created 10 seconds AFTER the order — the old guard missed exactly this
    cart = _cart(email, now - timedelta(hours=3) + timedelta(seconds=10), now - timedelta(hours=2))
    run(abandoned._db.abandoned_carts.insert_one(cart.copy()))
    sent = []
    original = email_service.send_abandoned_cart

    async def spy(*args, **kwargs):
        sent.append(args)
        return {"sent": False, "reason": "test"}

    email_service.send_abandoned_cart = spy
    try:
        run(abandoned.sweep())
        after = run(abandoned._db.abandoned_carts.find_one({"id": cart["id"]}, {"_id": 0}))
        assert after["status"] == "recovered"
        assert not sent
    finally:
        email_service.send_abandoned_cart = original
        _cleanup(email)


def test_a_real_abandoned_cart_is_still_reminded():
    email = f"lost-{uuid.uuid4().hex[:6]}@example.com"
    now = datetime.now(timezone.utc)
    cart = _cart(email, now - timedelta(hours=4), now - timedelta(hours=3))
    run(abandoned._db.abandoned_carts.insert_one(cart.copy()))
    sent = []
    original = email_service.send_abandoned_cart

    async def spy(*args, **kwargs):
        sent.append(args)
        return {"sent": True}

    email_service.send_abandoned_cart = spy
    try:
        run(abandoned.sweep())
        after = run(abandoned._db.abandoned_carts.find_one({"id": cart["id"]}, {"_id": 0}))
        assert after["status"] == "reminded"
        assert len(sent) == 1
    finally:
        email_service.send_abandoned_cart = original
        _cleanup(email)
