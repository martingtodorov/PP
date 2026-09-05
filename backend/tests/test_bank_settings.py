"""Bank account shown on the site and in the e-mail comes from the admin settings."""
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"


def _admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"],
                                          "password": os.environ["ADMIN_PASSWORD"]}, timeout=20)
    r.raise_for_status()
    return s


def test_the_admin_can_change_the_bank_account_and_the_shop_uses_it():
    s = _admin()
    original = s.get(f"{API}/admin/settings", timeout=20).json()["settings"]
    edited = {**original, "bank_holder": "Тест ЕООД", "bank_name": "Тест Банк",
              "bank_iban": "BG00TEST00000000000000", "bank_bic": "TESTBGSF"}
    try:
        assert s.put(f"{API}/admin/settings", json={"value": edited}, timeout=20).status_code == 200
        order = next(o for o in s.get(f"{API}/admin/orders", params={"limit": 50}, timeout=20).json()["orders"]
                     if o.get("payment_method", "bank_transfer") == "bank_transfer")
        bank = requests.get(f"{API}/orders/{order['id']}", timeout=20).json()["bank_transfer"]
        if bank:            # a paid or cancelled order carries no instructions
            assert bank["iban"] == "BG00TEST00000000000000"
            assert bank["holder"] == "Тест ЕООД" and bank["bic"] == "TESTBGSF"

        import bank as bank_module
        rendered = bank_module.from_settings(edited, "ABC12", 53.99)
        assert rendered == {"name": "Тест Банк", "iban": "BG00TEST00000000000000", "bic": "TESTBGSF",
                            "holder": "Тест ЕООД", "reference": "ABC12", "amount_eur": 53.99}
    finally:
        s.put(f"{API}/admin/settings", json={"value": original}, timeout=20)


def test_an_empty_field_falls_back_to_the_environment():
    import bank as bank_module
    out = bank_module.from_settings({"bank_iban": "  "}, "X1")
    assert out["iban"] == os.environ.get("BANK_IBAN", "")


def test_the_company_details_never_reach_a_customer_mail():
    """Owner's rule: the company (name, EIK, VAT, address, bank holder) is not mentioned in any e-mail."""
    import email_templates as et
    s = _admin()
    original = s.get(f"{API}/admin/settings", timeout=20).json()["settings"]
    edited = {**original, "company_name": "Пюърпептид ЕООД", "company_eik": "207123456",
              "company_vat": "BG207123456", "company_address": "гр. София, ул. Тест 1"}
    try:
        assert s.put(f"{API}/admin/settings", json={"value": edited}, timeout=20).status_code == 200
        stored = s.get(f"{API}/admin/settings", timeout=20).json()["settings"]
        assert stored["company_eik"] == "207123456" and stored["company_address"] == "гр. София, ул. Тест 1"

        seller = et.seller_lines(stored)
        assert seller == ""
        order = {"id": "x", "order_number": "TST01", "locale": "bg", "currency": "EUR",
                 "items": [{"title": "Ipamorelin", "quantity": 1, "price_eur": 49.0}],
                 "subtotal_eur": 49.0, "shipping_eur": 4.99, "total_eur": 53.99,
                 "payment_method": "bank_transfer", "delivery": {}, "shipping": {}}
        bank = {"name": "Тест Банк", "iban": "BG00TEST", "bic": "TESTBGSF", "holder": "Пюърпептид ЕООД"}
        _, html = et.render_order(order, bank, "bg", "info@purepeptide.bg", "Пюърпептид ЕООД · ЕИК 207123456")
        assert "ЕООД" not in html and "207123456" not in html and "ул. Тест 1" not in html
        assert "BG00TEST" in html and "Тест Банк" in html          # the transfer details themselves stay
    finally:
        s.put(f"{API}/admin/settings", json={"value": original}, timeout=20)


def test_without_company_details_nothing_extra_is_printed():
    import email_templates as et
    assert et.seller_lines({}) == ""
    _, html = et.render_shipment({"order_number": "T", "shipment": {"awb": "1", "courier": "Еконт"}},
                                 "bg", "info@purepeptide.bg")
    assert "ЕИК" not in html
