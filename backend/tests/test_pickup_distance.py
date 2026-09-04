"""Pickup points ranked by distance from the visitor (postal-code / city centroids)."""
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
BURGAS = {"lat": 42.5048, "lng": 27.4626}


APPROX_PENALTY_KM = 3.0     # mirrors nextcart.APPROX_PENALTY_KM


def _rank(o):
    """The order the API promises: distance, with a penalty for centroid guesses."""
    return (o["distance_km"] or 0) + (0 if o["distance_exact"] else APPROX_PENALTY_KM)


def _pickups(params):
    r = requests.get(f"{API}/nextcart/pickups", params=params, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()


def test_pickups_without_a_position_are_unsorted_and_carry_no_distance():
    d = _pickups({"provider_key": "econt", "destination_type": "office", "country": "BG"})
    assert d["count"] > 100
    assert "sorted_by" not in d
    assert all("distance_km" not in o for o in d["pickups"])


def test_pickups_are_sorted_by_distance_from_the_visitor():
    d = _pickups({"provider_key": "econt", "destination_type": "office", "country": "BG", **BURGAS})
    assert d["sorted_by"] == "distance"
    known = [o["distance_km"] for o in d["pickups"] if o["distance_km"] is not None]
    assert len(known) > d["count"] * 0.9, "most offices must resolve to coordinates"
    ranks = [_rank(o) for o in d["pickups"] if o["distance_km"] is not None]
    assert ranks == sorted(ranks)
    exact_km = [o["distance_km"] for o in d["pickups"] if o["distance_exact"]]
    assert exact_km == sorted(exact_km), "exact points must stay in ascending order"
    assert known[0] < 20, f"the closest Burgas office should be within 20 km, got {known[0]}"
    # Econt publishes its own coordinates, so Burgas offices differ from each other
    exact = [o for o in d["pickups"] if o["distance_exact"]]
    assert len(exact) > d["count"] * 0.9, "Econt offices must use the courier's own coordinates"
    burgas = [o["distance_km"] for o in d["pickups"][:8]]
    assert len(set(burgas)) > 3, f"offices in one town must not share one distance: {burgas}"
    # offices we cannot place go last
    tail = [o["distance_km"] for o in d["pickups"][len(known):]]
    assert all(x is None for x in tail)
    # a Sofia office must be far away from Burgas
    sofia = next((o for o in d["pickups"] if "софия" in (o["city"] or "").lower()
                  and o["distance_km"] is not None), None)
    assert sofia and sofia["distance_km"] > 200, sofia


def test_boxnow_lockers_use_the_published_locker_coordinates():
    d = _pickups({"provider_key": "boxnow", "destination_type": "locker", "country": "BG", **BURGAS})
    assert d["sorted_by"] == "distance"
    exact = [o for o in d["pickups"] if o["distance_exact"]]
    assert len(exact) > d["count"] * 0.95, "BOX NOW publishes coordinates for every locker"
    known = [o["distance_km"] for o in d["pickups"] if o["distance_km"] is not None]
    ranks = [_rank(o) for o in d["pickups"] if o["distance_km"] is not None]
    assert ranks == sorted(ranks) and known[0] < 20
    # the nearest locker must be an exact one — a centroid guess may never take the first row
    assert d["pickups"][0]["distance_exact"], d["pickups"][0]


def test_pigeon_offices_have_their_own_coordinates():
    """Pigeon publishes no API — the offices are geocoded, so distances must differ per office."""
    d = _pickups({"provider_key": "pigeon", "destination_type": "office", "country": "BG",
                  "lat": 42.6870, "lng": 23.3170})       # Sofia, NDK
    exact = [o for o in d["pickups"] if o["distance_exact"]]
    assert len(exact) > d["count"] * 0.8, f"only {len(exact)} of {d['count']} located"
    top = d["pickups"][:6]
    assert top[0]["distance_exact"] and top[0]["distance_km"] < 2
    assert len({o["distance_km"] for o in top}) > 3, [o["distance_km"] for o in top]


def test_greek_lockers_rank_by_city_centroid():
    d = _pickups({"provider_key": "speedex", "destination_type": "office", "country": "GR",
                  "lat": 37.9838, "lng": 23.7275})     # Athens
    assert d["sorted_by"] == "distance"
    known = [o["distance_km"] for o in d["pickups"] if o["distance_km"] is not None]
    ranks = [_rank(o) for o in d["pickups"] if o["distance_km"] is not None]
    assert known and ranks == sorted(ranks)
    assert known[0] < 40


def test_bad_coordinates_are_rejected():
    r = requests.get(f"{API}/nextcart/pickups", timeout=15, params={
        "provider_key": "econt", "destination_type": "office", "country": "BG", "lat": 999, "lng": 0})
    assert r.status_code == 422


def test_settings_expose_the_delivery_terms_for_the_product_schema():
    """Google merchant listings need shipping + return terms inside every product offer."""
    for locale, country, price in (("bg", "BG", 4.59), ("gr", "GR", None), ("en", "DE", 8.99)):
        d = requests.get(f"{API}/settings", params={"locale": locale}, timeout=30).json()["shipping"]
        assert d["country"] == country
        assert d["currency"] == "EUR"
        assert d["return_days"] == 14
        assert d["handling_days"] == [1, 3] and d["transit_days"] == [1, 3]
        assert isinstance(d["price"], (int, float)) and d["price"] > 0
        if price:
            assert d["price"] == price
