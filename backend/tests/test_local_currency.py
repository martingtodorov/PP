"""CZ/HU/PL/RO storefronts are priced and charged in their own currency."""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api" if os.environ.get(
    "REACT_APP_BACKEND_URL") else "http://localhost:8001/api"

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from currency import currency_for_locale, nice_price, order_amounts  # noqa: E402


def test_only_the_non_euro_countries_switch_currency():
    assert currency_for_locale("ro") == "RON"
    assert currency_for_locale("cz") == "CZK"
    assert currency_for_locale("hu") == "HUF"
    assert currency_for_locale("pl") == "PLN"
    for euro in ("bg", "en", "de", "gr", "sk", "si", "fr", None, ""):
        assert currency_for_locale(euro) == "EUR"


def test_psychological_rounding_never_goes_below_the_converted_price():
    assert nice_price(29, "RON", 5.2567) == 159        # 152.44 -> 159 lei
    assert nice_price(3.89, "RON", 5.2567) == 21       # small amounts stay round
    assert nice_price(58, "HUF", 395.0) == 22990       # 22 910 -> 22 990 Ft
    assert nice_price(29, "CZK", 24.159) == 709        # 700.6 -> 709 Kc
    assert nice_price(12.5, "EUR", 1.0) == 12.5        # euro shops are untouched
    for eur in (1, 4.99, 19, 29, 58, 149, 999):
        raw = eur * 5.2567
        assert nice_price(eur, "RON", 5.2567) >= raw


def test_rounding_is_idempotent():
    once = nice_price(29, "RON", 5.2567)
    assert nice_price(once, "RON", 1.0) == once


def test_order_totals_are_built_from_the_rounded_unit_prices():
    items = [{"price_eur": 29.0, "quantity": 2}, {"price_eur": 58.0, "quantity": 1}]
    totals = {"shipping_eur": 3.89, "discount_eur": 0}
    out = order_amounts(items, totals, {}, "RON", 5.2567)
    assert out["currency"] == "RON"
    assert out["item_prices"] == [159.0, 309.0]
    assert out["subtotal_orig"] == 159 * 2 + 309
    assert out["shipping_orig"] == 21
    assert out["total_orig"] == out["subtotal_orig"] + 21


def test_percentage_discount_applies_to_the_local_subtotal():
    items = [{"price_eur": 29.0, "quantity": 1}]
    out = order_amounts(items, {"shipping_eur": 0, "discount_eur": 2.9},
                        {"type": "percent", "value": 10}, "RON", 5.2567)
    assert out["discount_orig"] == round(159 * 0.10)
    assert out["total_orig"] == 159 - out["discount_orig"]


def test_euro_orders_carry_no_local_mirror():
    out = order_amounts([{"price_eur": 29.0, "quantity": 1}], {"shipping_eur": 0}, {}, "EUR", 1.0)
    assert out == {"currency": "EUR", "currency_rate": 1.0}


def test_currency_endpoint_serves_the_daily_ecb_rate():
    for locale, code in (("ro", "RON"), ("cz", "CZK"), ("hu", "HUF"), ("pl", "PLN")):
        data = requests.get(f"{API}/currency", params={"locale": locale}, timeout=20).json()
        assert data["currency"] == code
        assert data["rate"] > 1
        assert data["date"], "the ECB snapshot must be dated"
    assert requests.get(f"{API}/currency", params={"locale": "bg"}, timeout=20).json() == {
        "currency": "EUR", "rate": 1.0, "date": None, "intl_locale": "bg-BG"}
