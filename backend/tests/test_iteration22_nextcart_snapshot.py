"""Iteration 22: NextCart snapshot-only flow (NEXTCART_SNAPSHOT_ONLY=true)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/nextcart"

EXPECTED_COUNTRIES = {"BG", "RO", "GR", "HU", "PL", "SK", "CZ", "SI", "HR", "IT", "DE"}

PICKUP_CASES = [
    ("BG", "econt", "office"),
    ("BG", "boxnow", "locker"),
    ("RO", "fancourier", "locker"),
    ("GR", "speedex", "office"),
    ("HU", "gls", "office"),
    ("PL", "gls", "office"),
    ("SK", "gls", "office"),
    ("SI", "gls", "office"),
    ("HR", "gls", "office"),
    ("DE", "gls", "office"),
]


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# --- /countries ---------------------------------------------------------------
def test_countries(s):
    r = s.get(f"{API}/countries", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("default") == "BG"
    isos = {c["iso2"] for c in data.get("countries", [])}
    assert EXPECTED_COUNTRIES.issubset(isos), f"missing: {EXPECTED_COUNTRIES - isos}"
    for c in data["countries"]:
        assert c.get("name")
        # dial code should be present (string), may be empty for some
        assert "dial" in c


# --- /config per country ------------------------------------------------------
@pytest.mark.parametrize("iso", sorted(EXPECTED_COUNTRIES))
def test_config_per_country(s, iso):
    r = s.get(f"{API}/config", params={"country": iso}, timeout=20)
    assert r.status_code == 200, f"{iso}: {r.text[:300]}"
    d = r.json()
    methods = d.get("delivery_methods") or []
    assert methods, f"{iso}: no delivery methods"
    # at least one EUR-priced method
    eur_priced = [m for m in methods if (m.get("currency") == "EUR" and float(m.get("price_amount") or 0) >= 0)]
    assert eur_priced, f"{iso}: no EUR-priced method"
    assert not d.get("delivery_unavailable_message"), f"{iso}: delivery_unavailable_message set"


# --- /pickups -----------------------------------------------------------------
@pytest.mark.parametrize("iso,pk,dt", PICKUP_CASES)
def test_pickups_non_empty(s, iso, pk, dt):
    r = s.get(f"{API}/pickups", params={"country": iso, "provider_key": pk, "destination_type": dt}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("count", 0) > 0, f"{iso}/{pk}/{dt}: empty pickups"
    assert isinstance(d.get("pickups"), list) and d["pickups"]
    first = d["pickups"][0]
    for f in ("id", "name", "city"):
        assert f in first


# --- /offices with q filter ---------------------------------------------------
def test_offices_search_bg_econt(s):
    r = s.get(f"{API}/offices", params={
        "country": "BG", "provider_key": "econt", "destination_type": "office",
        "q": "София", "limit": 10,
    }, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    offices = d.get("offices") or []
    assert offices, "expected offices matching 'София'"
    assert len(offices) <= 10
    # each returned office should mention Sofia in some field
    for o in offices:
        blob = " ".join(str(o.get(f) or "") for f in ("name", "city", "address", "address1", "postal_code")).lower()
        assert "софия" in blob or "sofia" in blob


def test_offices_search_limit_respected(s):
    r = s.get(f"{API}/offices", params={
        "country": "BG", "provider_key": "econt", "destination_type": "office", "limit": 3,
    }, timeout=20)
    assert r.status_code == 200
    assert len(r.json().get("offices") or []) <= 3


# --- /address-suggestions -----------------------------------------------------
def test_address_suggestions_returns_empty_200(s):
    r = s.get(f"{API}/address-suggestions", params={"mode": "city", "q": "Sof", "country": "BG"}, timeout=20)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    d = r.json()
    assert d.get("suggestions") == []


def test_address_suggestions_street_empty_200(s):
    r = s.get(f"{API}/address-suggestions", params={"mode": "street", "q": "Vit", "country": "BG"}, timeout=20)
    assert r.status_code == 200
    assert r.json().get("suggestions") == []
