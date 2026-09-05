"""Analytics geo: the country comes from Cloudflare on every visit, the city from the IP lookup."""
import os
import uuid

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")


def _admin():
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"],
                                      "password": os.environ["ADMIN_PASSWORD"]},
           timeout=20).raise_for_status()
    return s


def _visit(country: str):
    """One human page view from a Cloudflare edge in `country`, from a private IP (no lookup)."""
    r = requests.post(f"{API}/track", json={"session_id": uuid.uuid4().hex, "path": "/", "locale": "bg"},
                      headers={"User-Agent": UA, "CF-IPCountry": country,
                               "X-Forwarded-For": "10.0.0.7"}, timeout=20)
    assert r.status_code == 200, r.text


def test_the_visit_records_the_cloudflare_country():
    _visit("GR")
    geo = _admin().get(f"{API}/admin/analytics", params={"range": "today"}, timeout=30).json()["geo"]
    codes = [c["country"] for c in geo["countries"]]
    assert "GR" in codes, codes
    row = next(c for c in geo["countries"] if c["country"] == "GR")
    assert row["country_name"] == "Гърция" and row["visitors"] >= 1


def test_the_lists_are_sorted_and_never_show_a_blank_place():
    geo = _admin().get(f"{API}/admin/analytics", params={"range": "30d"}, timeout=30).json()["geo"]
    for key in ("countries", "cities"):
        rows = geo[key]
        assert rows == sorted(rows, key=lambda r: (-r["visitors"], -r["views"]))
        assert len(rows) <= 12
    assert all(r["city"] for r in geo["cities"])
    assert all(r["country"] for r in geo["countries"])
