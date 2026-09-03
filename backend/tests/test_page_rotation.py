"""Rotation of a static page URL: /pages/faq -> /pages/faq-xyz (per locale, code replaced not stacked)."""
import os
import re

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
BASE = "http://localhost:8001/api"
ADMIN = {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}


def test_page_rotation():
    cli = MongoClient(os.environ["MONGO_URL"])
    pages = cli[os.environ["DB_NAME"]].pages
    original = pages.find_one({"slug": "faq", "locale": "bg"})
    assert original, "the bg FAQ page must exist"
    s = requests.Session()
    try:
        assert s.post(f"{BASE}/auth/login", json=ADMIN, timeout=30).status_code == 200
        link = s.post(f"{BASE}/admin/delisted-links", timeout=30, json={
            "url": "https://purepeptide.bg/pages/faq", "locale": "bg", "reason": "test"}).json()["link"]
        rot = s.post(f"{BASE}/admin/delisted-links/{link['id']}/rotate", timeout=240).json()["rotated"]
        new_slug = rot["handle"]
        assert re.fullmatch(r"faq-[a-z]{3}", new_slug), new_slug

        assert s.get(f"{BASE}/pages/{new_slug}", params={"locale": "bg"}, timeout=30).status_code == 200
        assert s.get(f"{BASE}/pages/faq", params={"locale": "bg"}, timeout=30).status_code == 404
        assert s.get(f"{BASE}/links", params={"locale": "bg"}, timeout=30).json().get("faq") == f"/pages/{new_slug}"
        assert s.get(f"{BASE}/pages/faq", params={"locale": "en"}, timeout=30).status_code == 200

        link2 = s.post(f"{BASE}/admin/delisted-links", timeout=30, json={
            "url": f"https://purepeptide.bg/pages/{new_slug}", "locale": "bg", "reason": "test"}).json()["link"]
        rot2 = s.post(f"{BASE}/admin/delisted-links/{link2['id']}/rotate", timeout=240).json()["rotated"]
        assert re.fullmatch(r"faq-[a-z]{3}", rot2["handle"]), rot2["handle"]
        assert rot2["handle"] != new_slug
        assert s.get(f"{BASE}/pages/{new_slug}", params={"locale": "bg"}, timeout=30).status_code == 404
        assert s.get(f"{BASE}/pages/{rot2['handle']}", params={"locale": "bg"}, timeout=30).status_code == 200

        s.delete(f"{BASE}/admin/delisted-links/{link['id']}", timeout=30)
        s.delete(f"{BASE}/admin/delisted-links/{link2['id']}", timeout=30)
    finally:
        pages.replace_one({"slug": "faq", "locale": "bg"}, original)
        cli.close()
