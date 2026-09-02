"""Who may cancel an order and when."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402


def order(**over):
    base = {"status": "pending", "payment_status": "awaiting_payment", "fulfillment_status": "unfulfilled"}
    base.update(over)
    return base


def test_open_order_is_cancellable():
    assert server.cancel_blocker(order()) == ""
    assert server.cancel_blocker(order(payment_status="paid")) == ""
    assert server.cancel_blocker(order(fulfillment={"number": "AB1", "status": "pending"})) == ""


def test_shipped_order_cannot_be_cancelled():
    for o in (order(fulfillment_status="shipped"), order(fulfillment_status="fulfilled"),
              order(fulfillment_status="delivered"), order(status="shipped")):
        assert "изпратена" in server.cancel_blocker(o)


def test_already_cancelled_order_reports_it():
    assert "вече е отказана" in server.cancel_blocker(order(status="cancelled"))
    assert "вече е отказана" in server.cancel_blocker(order(payment_status="cancelled"))
