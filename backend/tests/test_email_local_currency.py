"""Customer emails speak the storefront currency (RON/PLN/HUF/CZK) exactly like the cart does."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import email_templates as et  # noqa: E402
from currency import nice_price  # noqa: E402

BANK = {"name": "Bank", "iban": "BG00XXXX", "bic": "BICX", "holder": "PurePeptide"}


def _order(currency="RON", rate=4.975):
    items = [{"title": "Sermorelin", "variant_name": "5 mg", "quantity": 2, "price_eur": 59.0}]
    o = {"id": "o1", "order_number": "T1", "customer_name": "Ana Pop", "customer_email": "a@x.ro",
         "items": items, "locale": "ro", "payment_method": "bank_transfer", "shipping": {"country": "RO"},
         "subtotal_eur": 118.0, "discount_eur": 0.0, "shipping_eur": 0.0, "total_eur": 118.0,
         "currency": "EUR", "currency_rate": 1.0}
    if currency != "EUR":
        o = et.localize_order(o, {"currency": currency, "rate": rate})
    return o


def test_money_matches_the_storefront_layout():
    assert et._money(638, "RON") == "638\u00a0RON"
    assert et._money(1299, "CZK") == "1\u00a0299\u00a0Kč"
    assert et._money(12990, "HUF") == "12\u00a0990\u00a0Ft"
    assert et._money(249, "PLN") == "249\u00a0zł"
    assert et._money(118, "EUR") == "€118.00"


def test_order_email_shows_local_currency_and_eur_transfer_note():
    o = _order()
    assert o["currency"] == "RON" and o["items"][0]["price_orig"] == nice_price(59, "RON", 4.975) == 299.0
    assert o["total_orig"] == 598.0
    subject, html = et.render_order(o, BANK, "ro", "info@purepeptide.ro")
    assert "598\u00a0RON" in html and "299" not in subject
    assert "Suma de transferat în EUR" in html and "€118.00" in html
    assert "€59" not in html and "€598" not in html


def test_localize_order_is_a_noop_for_the_same_currency_and_reverts_to_eur():
    ron = _order()
    assert et.localize_order(ron, {"currency": "RON", "rate": 5.0}) is ron
    eur = et.localize_order(ron, {"currency": "EUR", "rate": 1.0})
    assert eur["currency"] == "EUR" and "total_orig" not in eur and "price_orig" not in eur["items"][0]
    _, html = et.render_order(eur, BANK, "en", "i@x.eu")
    assert "€118.00" in html and "RON" not in html


def test_abandoned_cart_email_uses_the_storefront_currency():
    cart = {"id": "c1", "email": "a@x.pl", "customer_name": "Jan", "locale": "pl",
            "items": [{"title": "BPC-157", "quantity": 1, "price_eur": 45.0, "image": ""}]}
    _, html = et.render_abandoned(cart, "pl", "i@x.eu", "", {"currency": "PLN", "rate": 4.3})
    expected = et._money(nice_price(45, "PLN", 4.3), "PLN")
    assert expected in html and "€" not in html
    _, html_eur = et.render_abandoned(cart, "en", "i@x.eu", "", {"currency": "EUR", "rate": 1.0})
    assert "€45.00" in html_eur


def test_admin_email_shows_local_total_with_eur_equivalent():
    subject, html = et.render_admin_order(_order("CZK", 25.2))
    total = et._money(_order("CZK", 25.2)["total_orig"], "CZK")
    assert total in subject and re.search(r"\(€118\.00\)", html)
