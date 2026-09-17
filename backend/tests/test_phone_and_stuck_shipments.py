"""Two owner requests (16.06.2026):

1. A customer who types his own country code into the prefixed phone field must not break the
   order — the duplicate prefix is ignored (it made NextLevel stamp shipments "unknown_number").
2. When NextLevel parks an order in the hub (need_correction, unknown_number, …) the admin gets a
   push notification, once per status, and the order is flagged in the panel.
"""
import pytest
from conftest import run

import fulfillment
import server
from nextcart import normalize_phone


@pytest.mark.parametrize("typed,country,expected", [
    ("888123456", "BG", "+359888123456"),          # as intended
    ("0888123456", "BG", "+359888123456"),         # trunk zero
    ("+359888123456", "BG", "+359888123456"),      # prefix typed with a plus
    ("359888123456", "BG", "+359888123456"),       # prefix typed without a plus
    ("00359888123456", "BG", "+359888123456"),     # international 00 form
    ("+359 (0) 888 123 456", "BG", "+359888123456"),
    ("+359359888123456", "BG", "+359888123456"),   # the prefix twice (the actual complaint)
    ("0049 151 23456789", "DE", "+4915123456789"),
    ("306912345678", "GR", "+306912345678"),
    ("0721234567", "RO", "+40721234567"),
    ("", "BG", ""),
])
def test_the_typed_prefix_is_ignored(typed, country, expected):
    assert normalize_phone(typed, country) == expected


def test_a_short_number_keeps_its_leading_digits():
    """Only a real number may be cut off a prefix: 359 alone is not a Bulgarian phone."""
    assert normalize_phone("359", "BG") == "+359359"
    assert normalize_phone("35912", "BG") == "+35935912"


def test_the_courier_receiver_is_built_from_the_clean_number():
    order = {"id": "x", "order_number": "ZZ1", "customer_name": "Иван Тестов",
             "customer_phone": "+359359888123456", "customer_email": "zz@example.com",
             "shipping": {"full_name": "Иван Тестов", "phone": "+359359888123456", "country": "BG",
                          "city": "София", "postal_code": "1000", "line1": "ул. Тест 1"},
             "delivery": {"provider_key": "econt", "destination_type": "office",
                          "office": {"id": "econt:4434"}},
             "items": [{"variant_sku": "ZZ", "title": "ZZ", "quantity": 1, "price_eur": 10}],
             "total_eur": 10}
    payload = fulfillment.build_order(order, {"wc_country": "BG", "weight": 0.1})
    assert payload["receiver"]["phone"] == "+359888123456"


ATTENTION = "need_correction"


def _order(**over):
    doc = {"id": "zz-attention-1", "order_number": "ZZATT", "customer_name": "Иван Тестов",
           "shipping": {"full_name": "Иван Тестов"}, "fulfillment": {"number": "F1"}}
    doc.update(over)
    return doc


def test_a_parked_order_notifies_the_admin_once_and_is_flagged(monkeypatch):
    sent = []

    async def fake_push(title, body, url="", tag=""):
        sent.append({"title": title, "body": body, "url": url, "tag": tag})

    monkeypatch.setattr(server, "notify_admin_push_bg", fake_push)
    orders = fulfillment._db.orders
    try:
        run(orders.delete_many({"id": "zz-attention-1"}))
        run(orders.insert_one(_order()))
        order = run(orders.find_one({"id": "zz-attention-1"}, {"_id": 0}))

        run(fulfillment._alert_if_stuck(order, order["fulfillment"], {"status": "need_correction"}))
        assert len(sent) == 1
        assert "ZZATT" in sent[0]["title"] and "корекция" in sent[0]["title"]
        assert sent[0]["url"] == "/admin/orders/zz-attention-1"

        after = run(orders.find_one({"id": "zz-attention-1"}, {"_id": 0}))
        assert after["needs_attention"]["status"] == ATTENTION
        assert after["fulfillment"]["alerted_status"] == ATTENTION
        assert server._order_view(after)["needs_attention"]["status"] == ATTENTION

        # the sync loop revisits the same order every 10 minutes — no second push
        run(fulfillment._alert_if_stuck(after, after["fulfillment"], {"status": "Need Correction"}))
        assert len(sent) == 1

        # a different problem is worth its own notification
        run(fulfillment._alert_if_stuck(after, after["fulfillment"], {"status": "unknown_number"}))
        assert len(sent) == 2
        assert "телефонът" in sent[1]["title"]

        # once the office sorts it out the flag goes away
        fixed = run(orders.find_one({"id": "zz-attention-1"}, {"_id": 0}))
        run(fulfillment._alert_if_stuck(fixed, fixed["fulfillment"], {"status": "processing"}))
        cleared = run(orders.find_one({"id": "zz-attention-1"}, {"_id": 0}))
        assert "needs_attention" not in cleared
        assert len(sent) == 2
    finally:
        run(orders.delete_many({"id": "zz-attention-1"}))


def test_every_blocking_status_of_the_nextlevel_docs_is_covered():
    """https://nextlevel-delivery.readme.io/reference/order-status — the statuses that stop an order."""
    assert set(fulfillment.ATTENTION_STATUSES) == {
        "need_correction", "waiting", "unconfirmed", "unknown_number", "no_answer", "problem",
        "reclamation", "duplicated"}


def test_the_admin_list_can_filter_the_parked_orders():
    assert server.ORDER_FILTERS["attention"] == {"needs_attention": {"$ne": None},
                                                 "status": {"$ne": "cancelled"}}
