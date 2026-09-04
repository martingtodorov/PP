"""Public order tracking (order number + phone) — /api/orders/track."""
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"


def track(number, phone):
    return requests.post(f"{API}/orders/track", json={"order_number": number, "phone": phone}, timeout=30)


def _any_order():
    """A real order from the database, straight from the admin API."""
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]},
           timeout=20).raise_for_status()
    rows = s.get(f"{API}/admin/orders", params={"limit": 50}, timeout=20).json()["orders"]
    for row in rows:
        full = s.get(f"{API}/admin/orders/{row['id']}", timeout=20).json()["order"]
        if full["customer"]["phone"]:
            return full
    raise AssertionError("no order with a phone number in the database")


def test_order_is_found_by_number_and_phone():
    o = _any_order()
    r = track(o["order_number"].lower(), o["customer"]["phone"])
    assert r.status_code == 200, r.text[:300]
    view = r.json()["order"]
    assert view["order_number"] == o["order_number"]
    assert view["items"] and view["total_display"] >= 0
    assert set(view["steps"]) == {"placed", "paid", "shipped", "delivered"}
    assert view["steps"]["placed"] is True


def test_the_last_digits_of_the_phone_are_enough():
    o = _any_order()
    digits = "".join(c for c in o["customer"]["phone"] if c.isdigit())
    assert track(o["order_number"], digits[-8:]).status_code == 200


def test_no_personal_data_leaks():
    o = _any_order()
    view = track(o["order_number"], o["customer"]["phone"]).json()["order"]
    blob = str(view).lower()
    assert o["customer"]["email"].lower() not in blob
    assert (o["customer"]["name"] or "@@").lower() not in blob


def test_a_wrong_phone_does_not_reveal_the_order():
    o = _any_order()
    assert track(o["order_number"], "0000000000").status_code == 404


def test_an_unknown_order_number_is_404():
    assert track("ZZZ99", "0888000111").status_code == 404


def test_a_short_phone_is_rejected():
    assert track("ZZZ99", "12").status_code == 422
