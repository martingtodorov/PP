"""The analytics day is the shop's day: it starts at midnight in Sofia and shows all 24 hours."""
import os
from datetime import datetime, timedelta

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


def test_today_starts_at_local_midnight_and_spans_24_hours():
    d = _admin().get(f"{API}/admin/analytics", params={"range": "today"}, timeout=30).json()
    assert d["timezone"] == "Europe/Sofia"
    start = datetime.fromisoformat(d["from"])
    from zoneinfo import ZoneInfo
    local = start.astimezone(ZoneInfo("Europe/Sofia"))
    assert (local.hour, local.minute) == (0, 0), local
    labels = [row["t"][11:13] for row in d["current"]["series"]]
    assert labels == [f"{h:02d}" for h in range(24)], labels


def test_hours_that_have_not_happened_yet_are_empty_not_zero():
    d = _admin().get(f"{API}/admin/analytics", params={"range": "today"}, timeout=30).json()
    series = d["current"]["series"]
    now_hour = datetime.fromisoformat(d["to"]).astimezone(
        __import__("zoneinfo").ZoneInfo("Europe/Sofia")).hour
    assert series[now_hour]["sessions"] is not None
    if now_hour < 23:
        assert series[now_hour + 1]["sessions"] is None


def test_the_previous_period_is_the_same_window_one_day_earlier():
    d = _admin().get(f"{API}/admin/analytics", params={"range": "today"}, timeout=30).json()
    cur_start = datetime.fromisoformat(d["from"])
    assert len(d["previous"]["series"]) == len(d["current"]["series"]) == 24
    # the previous window starts exactly 24 hours before the current one
    prev_first = d["previous"]["series"][0]["t"]
    assert prev_first == (cur_start.astimezone(
        __import__("zoneinfo").ZoneInfo("Europe/Sofia")) - timedelta(days=1)).isoformat()[:13]
