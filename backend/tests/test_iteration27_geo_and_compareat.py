"""Iteration 27 — geo (IP + reverse) and compare-at pricing for Retatrutide.

Tests the two live-user bugs:
1. /api/geo/country must NEVER guess a city (city == "" and ip_city carries the raw guess).
2. /api/geo/reverse returns local Cyrillic names via Nominatim.
3. Retatrutide product must expose compare_at_eur on variants and it must be visible on /products.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
LOCAL = "http://localhost:8001"

BG_IPS = ["78.90.11.5", "95.43.100.20", "46.10.150.1"]


# --- /api/geo/country --------------------------------------------------------

class TestGeoCountry:
    def _get(self, ip=None, header="cf-connecting-ip"):
        h = {header: ip} if ip else {}
        return requests.get(f"{LOCAL}/api/geo/country", headers=h, timeout=10)

    def test_no_ip_returns_default_country_no_city(self):
        r = requests.get(f"{LOCAL}/api/geo/country", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("country") == "BG"
        assert d.get("source") == "default"
        # must not carry a city hint
        assert not d.get("city")

    @pytest.mark.parametrize("ip", BG_IPS)
    def test_bg_ip_returns_bg_and_empty_city(self, ip):
        r = self._get(ip)
        assert r.status_code == 200
        d = r.json()
        assert d.get("country") == "BG", d
        # HARD requirement of this iteration
        assert d.get("city") == "", f"city must be empty, got {d!r}"
        # ip_city is informational — may be present even if empty string
        assert "ip_city" in d, d
        assert d.get("source") == "ip"

    @pytest.mark.parametrize("header", ["x-forwarded-for", "x-real-ip"])
    def test_forwarded_headers_are_respected(self, header):
        r = self._get(BG_IPS[0], header=header)
        assert r.status_code == 200
        d = r.json()
        assert d.get("country") == "BG"
        assert d.get("city") == ""


# --- /api/geo/reverse --------------------------------------------------------

class TestGeoReverse:
    @pytest.mark.parametrize("lat,lon,expected", [
        (42.4185, 27.6957, "Созопол"),
        (43.0757, 25.6172, "Велико Търново"),
        (42.6977, 23.3219, "София"),
    ])
    def test_bulgarian_cities_in_cyrillic(self, lat, lon, expected):
        r = requests.get(f"{LOCAL}/api/geo/reverse", params={"lat": lat, "lon": lon}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("source") == "device"
        assert expected in (d.get("city") or ""), f"expected {expected}, got {d}"
        assert d.get("country") == "BG"

    def test_sozopol_postcode(self):
        r = requests.get(f"{LOCAL}/api/geo/reverse",
                         params={"lat": 42.4185, "lon": 27.6957}, timeout=15)
        assert r.status_code == 200
        # Sozopol postcode is 8130 per BG post
        pc = str((r.json() or {}).get("postal_code") or "")
        assert pc.startswith("81"), f"expected Burgas-region 81xx postcode, got {pc}"

    def test_ocean_coordinate_returns_the_position_without_a_city(self):
        # middle of the Atlantic — no city, but the coordinates still rank the courier offices
        r = requests.get(f"{LOCAL}/api/geo/reverse",
                         params={"lat": 0.0, "lon": -30.0}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["city"] == "" and d["lat"] == 0.0 and d["lng"] == -30.0


# --- Retatrutide compare-at -------------------------------------------------

BASE = BASE_URL or LOCAL


class TestRetatrutideCompareAt:
    HANDLE = "21-retatrutide-5"

    def test_product_returns_compare_at_on_all_variants(self):
        r = requests.get(f"{BASE}/api/products/{self.HANDLE}", timeout=15)
        assert r.status_code == 200, r.text
        payload = r.json()
        p = payload.get("product") or payload
        variants = p.get("variants") or []
        assert variants, "product has no variants"
        expected = {
            "5": (49.0, 59.0),
            "10": (89.0, 99.0),
            "30": (159.0, 179.0),
        }
        seen = {}
        for v in variants:
            title = (v.get("title") or v.get("name") or "") + " " + (v.get("option1") or "")
            price = float(v.get("price_eur") or v.get("price") or 0)
            cmp_at = v.get("compare_at_eur")
            assert cmp_at is not None, f"variant {title!r} has no compare_at_eur"
            cmp_at = float(cmp_at)
            for key in expected:
                if key in title:
                    seen[key] = (price, cmp_at)
        for key, (want_p, want_c) in expected.items():
            got = seen.get(key)
            assert got, f"variant {key}mg not found in {[v.get('title') for v in variants]}"
            assert abs(got[0] - want_p) < 0.5, f"{key}mg price {got[0]} != {want_p}"
            assert abs(got[1] - want_c) < 0.5, f"{key}mg compare_at {got[1]} != {want_c}"

    def test_no_regression_other_products_have_no_compare_at(self):
        # Sample a handful of other products — none should carry a compare_at_eur
        r = requests.get(f"{BASE}/api/products", params={"limit": 40}, timeout=15)
        assert r.status_code == 200
        items = r.json()
        if isinstance(items, dict):
            items = items.get("products") or items.get("items") or []
        offenders = []
        for p in items:
            handle = p.get("handle") or ""
            if "retatrutide" in handle:
                continue
            for v in (p.get("variants") or []):
                cmp_at = v.get("compare_at_eur")
                if cmp_at is not None and float(cmp_at) > 0:
                    offenders.append((handle, v.get("title"), cmp_at))
        assert not offenders, f"unexpected compare_at on: {offenders[:5]}"
