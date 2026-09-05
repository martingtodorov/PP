"""Fulfillment payload builder + delivered e-mail template (offline, no NextLevel calls)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import email_templates  # noqa: E402
import fulfillment  # noqa: E402

CFG = {**fulfillment.DEFAULTS, "has_api": False}


def order(**over):
    base = {
        "id": "4f1deeca-ce40-4da0-a9dc-09ca410b7127", "order_number": "SUB29", "customer_email": "qa@example.com",
        "customer_name": "TEST QA", "customer_phone": "+359878279269", "locale": "bg",
        "items": [{"title": "Серморелин (Sermorelin) 5mg", "variant_sku": "PP-SERMORELIN-5MG", "variant_name": "5mg",
                   "price_eur": 59.0, "quantity": 2}],
        "shipping": {"full_name": "TEST QA", "phone": "+359878279269", "email": "qa@example.com", "line1": "TEST street 1",
                     "city": "Бургас", "postal_code": "8000", "country": "BG", "note": ""},
        "delivery": {"provider_key": "econt", "method_key": "econt_locker", "destination_type": "locker",
                     "office": {"id": "econt:4471"}},
        "subtotal_eur": 118.0, "discount_eur": 0.0, "shipping_eur": 3.39, "total_eur": 121.39, "currency": "EUR",
        "payment_method": "bank_transfer", "payment_status": "awaiting_payment", "notes": "",
    }
    base.update(over)
    return base


def test_locker_bank_transfer_payload():
    p = fulfillment.build_order(order(), CFG)
    assert p["order_id"] == "SUB29" and p["currency"] == "EUR"
    assert p["products"] == [{"sku": "PP-SERMORELIN-5MG", "name": "Серморелин (Sermorelin) 5mg", "quantity": 2,
                              "unit_price": 59.0, "weight": 0.1}]
    # NextLevel rejects a shipment without receiver.country, office deliveries included
    assert p["receiver"] == {"name": "TEST QA", "phone": "+359878279269", "email": "qa@example.com",
                             "office_id": 4471, "country": "BG", "place": "Бургас"}
    # a bank transfer is prepaid, so the warehouse must see the shipping as free (owner's decision)
    assert p["price"] == 118.0 and p["shipping_price"] == 0.0 and p["is_shipping_free"] is True
    assert p["is_paid"] is True and p["payment_method"] == "bank_transfer" and "services" not in p
    assert "courier" not in p  # the office decides the courier
    assert p["contents"] == "аминокиселини"    # the waybill never declares the SKUs


def test_office_order_without_country_falls_back_to_the_shop_country():
    """NextLevel answered 400 'The receiver.country field is required' for office orders (WLH05)."""
    o = order(shipping={"full_name": "TEST QA", "phone": "+359878279269", "city": "Бургас"})
    p = fulfillment.build_order(o, {**CFG, "wc_country": "bg"})
    assert p["receiver"]["country"] == "BG"
    assert p["receiver"]["office_id"] == 4471


def test_office_order_without_any_country_fails_with_a_clear_reason():
    o = order(shipping={"full_name": "TEST QA", "phone": "+359878279269"})
    with pytest.raises(ValueError, match="receiver.country"):
        fulfillment.build_order(o, {**CFG, "wc_country": ""})


def test_address_cod_ron_payload():
    o = order(shipping={"full_name": "Ion Pop", "phone": "+40712345678", "line1": "Str. Unirii 5", "line2": "ap. 3",
                        "city": "Cluj-Napoca", "postal_code": "400001", "country": "RO"},
              delivery={"provider_key": "fancourier", "destination_type": "address", "office": None},
              payment_method="cod", currency="RON", subtotal_orig=590.0, discount_orig=59.0, shipping_orig=19.0,
              total_orig=550.0, items=[{"title": "BPC-157", "variant_sku": "PP-BPC157-5MG", "variant_name": "5mg",
                                        "price_eur": 59.0, "price_orig": 295.0, "quantity": 2}])
    p = fulfillment.build_order(o, CFG)
    assert p["currency"] == "RON" and p["price"] == 531.0 and p["shipping_price"] == 19.0
    assert p["products"][0]["unit_price"] == 295.0 and p["products"][0]["name"] == "BPC-157 5mg"
    assert p["receiver"]["country"] == "RO" and p["receiver"]["post_code"] == "400001" and p["receiver"]["other"] == "ap. 3"
    assert p["courier"] == "FAN"
    assert p["is_paid"] is False
    assert p["services"] == {"cod": {"amount": 550.0, "currency": "RON", "processing_type": "CASH", "included_shipping_price": True},
                             "obpd": {"option": "OPEN", "return_shipment_payer": "SENDER"}}


def test_wrong_currency_for_country_is_rejected():
    o = order(shipping={**order()["shipping"], "country": "RO"}, delivery={"destination_type": "address"}, currency="EUR")
    with pytest.raises(ValueError, match="RON"):
        fulfillment.build_order(o, CFG)


def test_missing_sku_and_missing_office_id():
    with pytest.raises(ValueError, match="SKU"):
        fulfillment.build_order(order(items=[{"title": "X", "quantity": 1, "price_eur": 1}]), CFG)
    with pytest.raises(ValueError, match="идентификатор"):
        fulfillment.build_order(order(delivery={"destination_type": "office", "office": {"id": "abc"}}), CFG)


def test_send_courier_can_be_switched_off():
    o = order(delivery={"provider_key": "econt", "destination_type": "address", "office": None})
    assert fulfillment.build_order(o, CFG)["courier"] == "Econt"
    assert "courier" not in fulfillment.build_order(o, {**CFG, "send_courier": False})


def test_summary_from_api_response():
    s = fulfillment._summary({"number": "00270417", "id": 7, "status": {"id": 2, "name": "shipped"}, "awb": "1000030801324",
                              "courier": "Econt", "tracking_link": "https://nextlevel.delivery/track?awb=1000030801324"}, "api")
    assert s["number"] == "00270417" and s["status"] == "shipped" and s["status_id"] == 2
    assert s["awb"] == "1000030801324" and s["tracking_link"].endswith("1000030801324")
    assert fulfillment._summary({"number": "1", "status": "new"}, "api")["awb"] is None


@pytest.mark.parametrize("loc", ["bg", "en", "fr", "de", "cz", "hu", "pl", "sk", "si", "gr", "ro"])
def test_delivered_email_all_locales(loc):
    o = order(locale=loc, shipment={"awb": "1000030801324", "courier": "Econt"})
    subject, html = email_templates.render_delivered(o, loc, "contact@purepeptide.bg")
    assert "SUB29" in subject and "{n}" not in subject
    assert "1000030801324" in html and "/checkout/success/4f1deeca" in html
    assert email_templates.T[loc]["dv_title"] in html


def test_open_before_pay_can_be_switched_off_and_is_cod_only():
    o = order(payment_method="cod", delivery={"destination_type": "office", "office": {"id": "econt:4434"}})
    assert "obpd" not in fulfillment.build_order(o, {**CFG, "open_before_pay": False})["services"]
    bank = order(payment_method="bank_transfer", delivery={"destination_type": "office", "office": {"id": "econt:4434"}})
    assert "obpd" not in (fulfillment.build_order(bank, CFG).get("services") or {})
