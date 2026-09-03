"""Iteration-18: per-country couriers, COD-first, EUR pricing, bank details, terms enforcement."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL") else open("/app/frontend/.env").read().split(
    "REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
API = f"{BASE}/api"


# --- /api/bank-details ---
class TestBankDetails:
    def test_bank_details(self):
        r = requests.get(f"{API}/bank-details", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "DSK Bank"
        assert d["iban"] == "BG61STSA93000032400775"
        assert d["bic"] == "STSABGSF"
        assert d["holder"] == "Purepeptide LTD"


# --- /api/nextcart/countries ---
class TestCountries:
    def test_countries(self):
        r = requests.get(f"{API}/nextcart/countries", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["default"] == "BG"
        countries = data["countries"]
        codes = {c["iso2"] for c in countries}
        expected = {"BG", "RO", "GR", "HU", "PL", "SK", "CZ", "SI", "HR", "IT", "DE", "ES"}
        assert codes == expected, f"unexpected countries: {codes}"
        assert len(countries) == len(expected)
        bg = next(c for c in countries if c["iso2"] == "BG")
        assert bg["name"] == "България"
        # dial code should be set for most (from precheckout territories)
        for c in countries:
            assert "dial" in c


# --- /api/nextcart/config?country=XX ---
EXPECTED_COURIERS = {
    "BG": {"econt", "boxnow", "pigeon"},
    "RO": {"fancourier"},
    "GR": {"speedex"},
    "HU": {"gls"}, "PL": {"gls"}, "SK": {"gls"}, "CZ": {"gls"},
    "SI": {"gls"}, "HR": {"gls"}, "IT": {"gls"}, "DE": {"gls"}, "ES": {"gls"},
}

# Spain was opened as a prepaid-only market with GLS to the address at 8.99 EUR
PREPAID_ONLY = {"ES"}


class TestConfigPerCountry:
    @pytest.mark.parametrize("country,expected", list(EXPECTED_COURIERS.items()))
    def test_couriers_per_country(self, country, expected):
        r = requests.get(f"{API}/nextcart/config", params={"country": country}, timeout=25)
        assert r.status_code == 200, r.text[:300]
        cfg = r.json()
        methods = cfg.get("delivery_methods") or []
        assert methods, f"{country}: no delivery methods"
        got_providers = {m.get("provider_key") for m in methods}
        # allow subset only if courier truly missing upstream (CZ/IT); at least one expected
        assert got_providers.issubset(expected), \
            f"{country}: unexpected providers {got_providers - expected}"
        assert got_providers, f"{country}: no providers matched"
        # every method EUR
        for m in methods:
            assert m.get("currency") == "EUR", f"{country}: non-EUR method {m}"
            assert isinstance(m.get("price_amount"), (int, float))
        # payment: cod first + default
        pms = cfg.get("payment_methods") or []
        if country in PREPAID_ONLY:
            assert [m["key"] for m in pms] == ["bank_transfer"]
            assert cfg.get("cod_available") is False
            assert [(m["key"], m["price_amount"]) for m in methods] == [("gls_address", 8.99)]
        else:
            assert pms[0]["key"] == "cod"
            assert pms[0].get("is_default") is True
            assert cfg.get("cod_available") is True
        # storefront currency
        assert cfg.get("storefront_delivery_currency") == "EUR"


# --- /api/nextcart/pickups per-country ---
class TestPickupsCountry:
    def test_gls_hu_office(self):
        r = requests.get(f"{API}/nextcart/pickups",
                         params={"provider_key": "gls", "destination_type": "office",
                                 "country": "HU"}, timeout=25)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["count"] > 0, "HU GLS should have offices"

    def test_fancourier_ro_locker(self):
        r = requests.get(f"{API}/nextcart/pickups",
                         params={"provider_key": "fancourier", "destination_type": "locker",
                                 "country": "RO"}, timeout=25)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # locker list may be empty upstream but response must be well-formed
        assert "pickups" in data and "count" in data

    def test_speedex_gr_office(self):
        r = requests.get(f"{API}/nextcart/pickups",
                         params={"provider_key": "speedex", "destination_type": "office",
                                 "country": "GR"}, timeout=25)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["count"] > 0, "GR Speedex should have offices"


# --- POST /api/checkout with COD + terms enforcement ---
def _one_line_item():
    r = requests.get(f"{API}/products", params={"limit": 8}, timeout=10)
    assert r.status_code == 200
    prods = r.json().get("products") or r.json().get("items") or []
    for p in prods:
        for v in (p.get("variants") or []):
            if v.get("stock", 1) != 0 and v.get("price_eur"):
                return {"product_id": p["id"], "variant_sku": v["sku"],
                        "price_eur": v["price_eur"]}
    pytest.skip("no purchasable variant")


def _payload(li, terms=True, payment="cod"):
    return {
        "items": [{"product_id": li["product_id"], "variant_sku": li["variant_sku"], "quantity": 1}],
        "shipping": {
            "full_name": "TEST Iter18",
            "phone": "+359888111333",
            "line1": "Пловдив Автогара Родопи",
            "city": "ПЛОВДИВ",
            "postal_code": "4000",
            "country": "BG",
        },
        "customer_email": f"TEST_iter18_{payment}@example.com",
        "customer_name": "TEST Iter18",
        "customer_phone": "+359888111333",
        "shipping_method": "econt_office",
        "payment_method": payment,
        "delivery": {
            "provider_key": "econt", "provider_name": "Еконт",
            "method_key": "econt_office", "destination_type": "office",
            "label": "До офис на Еконт", "price_amount": 3.89, "currency": "EUR",
            "office": {"id": "1", "name": "Пловдив Автогара Родопи",
                       "address": "бул. Христо Ботев 47", "city": "ПЛОВДИВ", "postal_code": "4000"},
            "address": None,
        },
        "discount_code": "",
        "terms_accepted": terms,
    }


class TestCheckout:
    def test_cod_checkout_ok(self):
        li = _one_line_item()
        r = requests.post(f"{API}/checkout", json=_payload(li, terms=True, payment="cod"), timeout=25)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert "order" in d
        assert d["order"]["total_eur"] > 0

    def test_terms_rejected(self):
        li = _one_line_item()
        r = requests.post(f"{API}/checkout", json=_payload(li, terms=False, payment="cod"), timeout=15)
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"
