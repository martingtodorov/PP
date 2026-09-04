"""Bank-transfer orders: the customer pays the courier price, the warehouse must see it as free."""
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import fulfillment                       # noqa: E402
import wc_api                            # noqa: E402

ORDER = {
    "id": "abc-123", "order_number": "TST01", "currency": "EUR",
    "items": [{"title": "Ipamorelin", "variant_sku": "PP-IPAMORELIN-10MG", "quantity": 1, "price_eur": 49.0}],
    "subtotal_eur": 49.0, "shipping_eur": 4.99, "total_eur": 53.99, "discount_eur": 0.0,
    "customer_email": "buyer@example.com", "customer_name": "Ivan Ivanov", "customer_phone": "+359888123456",
    "shipping": {"full_name": "Ivan Ivanov", "phone": "+359888123456", "line1": "ул. Тест 1",
                 "city": "София", "postal_code": "1000", "country": "BG"},
    "delivery": {"provider_key": "econt", "provider_name": "Еконт", "method_key": "econt_address",
                 "destination_type": "address", "label": "До адрес с Еконт", "price_amount": 4.99},
    "created_at": "2026-06-04T10:00:00+00:00", "locale": "bg", "payment_status": "paid",
}
CFG = {"wc_country": "BG", "contents_text": "аминокиселини", "send_courier": True}


def test_the_customer_is_charged_for_the_shipping():
    """The change is only about what the warehouse sees — the order itself keeps its shipping price."""
    assert ORDER["total_eur"] == ORDER["subtotal_eur"] + ORDER["shipping_eur"]


def test_a_prepaid_order_reaches_nextlevel_with_free_shipping():
    p = fulfillment.build_order({**ORDER, "payment_method": "bank_transfer"}, CFG)
    assert p["shipping_price"] == 0.0 and p["is_shipping_free"] is True
    assert p["payment_method"] == "bank_transfer" and "services" not in p


def test_cash_on_delivery_still_carries_the_shipping_price():
    p = fulfillment.build_order({**ORDER, "payment_method": "cod", "payment_status": "awaiting_payment"}, CFG)
    assert p["shipping_price"] == 4.99 and p["is_shipping_free"] is False
    assert p["services"]["cod"]["amount"] == 53.99


def test_the_woocommerce_view_marks_a_prepaid_shipping_as_free():
    o = wc_api.to_wc_order({**ORDER, "payment_method": "bank_transfer"}, CFG)
    assert o["shipping_total"] == "0.00"
    assert o["shipping_lines"][0]["total"] == "0.00"
    assert o["payment_method"] == "bacs"


def test_the_woocommerce_view_keeps_the_shipping_for_cash_on_delivery():
    o = wc_api.to_wc_order({**ORDER, "payment_method": "cod"}, CFG)
    assert o["shipping_total"] == "4.99" and o["shipping_lines"][0]["total"] == "4.99"
