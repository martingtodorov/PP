"""Predictive address input (city + street) for delivery to an address.

NextCart's address database is unreachable, so the suggestions come from our GeoNames city index
and from OpenStreetMap (Photon) for the streets.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"


def suggest(**params):
    r = requests.get(f"{API}/nextcart/address-suggestions", params=params, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()["suggestions"]


def test_city_suggestions_come_with_the_postal_code():
    out = suggest(mode="city", q="Бург", country="BG")
    assert out, "Бургас must be suggested"
    first = out[0]
    assert first["city"] == "Бургас" and first["postal_code"] == "8000"
    assert isinstance(first["place_id"], int)


def test_city_suggestions_are_diacritics_and_case_insensitive():
    assert any(s["city"].startswith("Sofia") or s["city"] == "София"
               for s in suggest(mode="city", q="софи", country="BG"))
    assert suggest(mode="city", q="buchar", country="RO"), "Bucharest must resolve"
    assert suggest(mode="city", q="athin", country="GR") or suggest(mode="city", q="athen", country="GR")


def test_a_too_short_query_is_rejected():
    r = requests.get(f"{API}/nextcart/address-suggestions",
                     params={"mode": "city", "q": "б", "country": "BG"}, timeout=15)
    assert r.status_code == 422


def test_street_suggestions_are_limited_to_the_typed_text_and_the_chosen_city():
    city = suggest(mode="city", q="Бургас", country="BG")[0]
    streets = suggest(mode="street", q="Алекс", country="BG", place_id=city["place_id"])
    assert streets, "Photon must return Burgas streets"
    assert all("алекс" in s["address1"].lower() for s in streets), streets
    assert streets[0]["city"] == "Бургас"
    assert streets[0]["postal_code"]


def test_unknown_mode_is_rejected():
    r = requests.get(f"{API}/nextcart/address-suggestions",
                     params={"mode": "county", "q": "Бургас", "country": "BG"}, timeout=15)
    assert r.status_code == 422
