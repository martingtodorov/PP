"""NextLevel payload rules measured against the live API (memory/nextlevel_mapping.md)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nextlevel as nl  # noqa: E402

CFG = {**nl.DEFAULTS, "sender_id": 594}


def _order(**over):
    base = {"id": "o1", "order_number": "01046442", "customer_name": "Иван Иванов", "customer_phone": "+359888123456",
            "customer_email": "i@x.bg", "payment_method": "cod", "currency": "EUR", "total_eur": 62.89,
            "items": [{"title": "Sermorelin 5mg", "quantity": 2}],
            "shipping": {"country": "BG", "city": "София", "postal_code": "1000", "line1": "бул. Витоша 1", "phone": "+359888123456"},
            "delivery": {"destination_type": "address", "provider_key": "econt"}}
    base.update(over)
    return base


def test_office_from_nextcart_id_and_cod_cash_not_included():
    o = _order(delivery={"destination_type": "office", "provider_key": "econt", "office": {"id": "econt:4434", "code": "9040"}})
    p = nl.build_payload(o, CFG)
    assert p["receiver"]["office_id"] == 4434 and "country" not in p["receiver"]
    assert p["services"]["cod"] == {"amount": 62.89, "currency": "EUR", "processing_type": "CASH", "included_shipping_price": False}
    assert p["sender"] == {"id": 594, "office_id": 1} and "courier" not in p
    assert p["content"]["weight"] == 0.4 and p["ref"] == "01046442"


def test_address_requires_post_code():
    with pytest.raises(ValueError, match="пощенски код"):
        nl.build_payload(_order(shipping={"country": "BG", "city": "Бистрица", "postal_code": "", "line1": "Главна 5"}), CFG)


def test_bank_transfer_has_no_cod():
    assert "services" not in nl.build_payload(_order(payment_method="bank_transfer"), CFG)


def test_ro_cod_in_ron_from_local_total():
    o = _order(currency="RON", total_orig=319.0, shipping={"country": "RO", "city": "București", "postal_code": "010101", "line1": "Calea Victoriei 1", "phone": "+40700000000"})
    assert nl.build_payload(o, CFG)["services"]["cod"] == {"amount": 319.0, "currency": "RON", "processing_type": "CASH", "included_shipping_price": False}


def test_ro_cod_refuses_wrong_currency():
    o = _order(shipping={"country": "RO", "city": "București", "postal_code": "010101", "line1": "x", "phone": "+40700000000"})
    with pytest.raises(ValueError, match="RON"):
        nl.build_payload(o, CFG)


def test_office_without_nextlevel_id_is_refused():
    with pytest.raises(ValueError, match="идентификатор"):
        nl.build_payload(_order(delivery={"destination_type": "office", "office": {"id": "1", "name": "x"}}), CFG)


def test_tracking_urls_use_courier_number():
    assert nl.tracking_url_for("Econt", "1055241178079", "1000030801027") == "https://www.econt.com/services/track-shipment/1055241178079"
    assert nl.tracking_url_for("Unknown", "1", "2") == "" and nl.tracking_url_for("Econt", None, "2") == ""
