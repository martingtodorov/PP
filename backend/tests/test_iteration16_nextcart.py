"""Iteration 16 — NextCart proxy tests."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://shopify-migrate-3.preview.emergentagent.com"
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def cfg():
    r = requests.get(f"{API}/nextcart/config", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


class TestNextCartConfig:
    def test_providers_present(self, cfg):
        keys = {p["key"] for p in cfg.get("delivery_providers", [])}
        assert {"econt", "boxnow", "pigeon"}.issubset(keys), keys

    def test_methods_and_prices(self, cfg):
        methods = {m["key"]: m for m in cfg.get("delivery_methods", [])}
        assert "econt_office" in methods
        assert "boxnow_locker" in methods
        assert "pigeon_address" in methods
        assert abs(methods["econt_office"]["price_amount"] - 3.89) < 0.01
        assert abs(methods["boxnow_locker"]["price_amount"] - 2.99) < 0.01
        assert abs(methods["pigeon_address"]["price_amount"] - 4.59) < 0.01

    def test_phone_territories_245(self, cfg):
        assert len(cfg.get("precheckout_phone_territories", [])) == 245


class TestOffices:
    def test_econt_offices_plovdiv(self):
        r = requests.get(f"{API}/nextcart/offices",
                         params={"provider_key": "econt", "destination_type": "office", "q": "Пловдив"},
                         timeout=15)
        assert r.status_code == 200
        offs = r.json().get("offices", [])
        assert len(offs) > 0
        o = offs[0]
        for k in ("id", "name", "city"):
            assert k in o, f"missing {k} in {o}"

    def test_boxnow_lockers(self):
        r = requests.get(f"{API}/nextcart/offices",
                         params={"provider_key": "boxnow", "destination_type": "locker", "q": "София"},
                         timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json().get("offices", []), list)

    def test_invalid_destination_type(self):
        r = requests.get(f"{API}/nextcart/offices",
                         params={"provider_key": "econt", "destination_type": "foo"},
                         timeout=10)
        assert r.status_code in (400, 422)

    def test_bogus_provider_no_crash(self):
        r = requests.get(f"{API}/nextcart/offices",
                         params={"provider_key": "bogus", "destination_type": "office", "q": "xx"},
                         timeout=15)
        # Either 4xx/5xx from upstream or 200 empty — must not 500 our proxy fatally
        assert r.status_code in (200, 400, 422, 502, 503)
        if r.status_code == 200:
            assert r.json().get("offices", []) == [] or isinstance(r.json().get("offices"), list)


class TestAddressSuggestions:
    def test_city_suggest(self):
        # Snapshot-only mode (production) has no address database — an empty list is the contract.
        r = requests.get(f"{API}/nextcart/address-suggestions",
                         params={"mode": "city", "q": "Пло"}, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json().get("suggestions", []), list)

    def test_q_too_short(self):
        r = requests.get(f"{API}/nextcart/address-suggestions",
                         params={"mode": "city", "q": "a"}, timeout=10)
        assert r.status_code in (400, 422)

    def test_unknown_mode(self):
        r = requests.get(f"{API}/nextcart/address-suggestions",
                         params={"mode": "xyz", "q": "abc"}, timeout=10)
        assert r.status_code in (400, 422)


class TestEvent:
    def test_event_never_errors(self):
        r = requests.post(f"{API}/nextcart/event",
                          json={"event_name": "precheckout_opened", "event_data": {}},
                          timeout=10)
        assert r.status_code == 200
        assert "forwarded" in r.json()


class TestRegression:
    def test_admin_login(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": "admin@purepeptide.bg", "password": "Admin@PurePeptide2026"},
                          timeout=10)
        assert r.status_code == 200
        assert "token" in r.json() or "access_token" in r.json()
