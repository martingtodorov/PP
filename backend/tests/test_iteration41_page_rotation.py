"""Iteration 41 — static page rotation (terms-conditions) + product rotation regression.

Rotation calls Claude and takes ~30-60s per link, so this file keeps rotations to a minimum
and restores the pages/products documents afterwards so the shop is left clean."""
import os
import re

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
BASE = "http://localhost:8001/api"
ADMIN = {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}


def _login():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return s


# --- static page rotation --------------------------------------------------------------------
def test_terms_conditions_page_rotation_bg():
    cli = MongoClient(os.environ["MONGO_URL"])
    pages = cli[os.environ["DB_NAME"]].pages
    original = pages.find_one({"slug": "terms-conditions", "locale": "bg"})
    assert original, "the bg terms-conditions page must exist"
    s = _login()
    link_ids = []
    try:
        r = s.post(f"{BASE}/admin/delisted-links", json={
            "url": "https://purepeptide.bg/pages/terms-conditions", "locale": "bg", "reason": "iter41"}, timeout=30)
        assert r.status_code == 200, r.text
        link = r.json()["link"]
        link_ids.append(link["id"])

        rot = s.post(f"{BASE}/admin/delisted-links/{link['id']}/rotate", timeout=240).json()["rotated"]
        new_slug = rot["handle"]
        assert re.fullmatch(r"terms-conditions-[a-z]{3}", new_slug), new_slug

        # new URL serves, old URL 404s, /api/links updated, other locale untouched
        assert s.get(f"{BASE}/pages/{new_slug}", params={"locale": "bg"}, timeout=30).status_code == 200
        assert s.get(f"{BASE}/pages/terms-conditions", params={"locale": "bg"}, timeout=30).status_code == 404
        links = s.get(f"{BASE}/links", params={"locale": "bg"}, timeout=30).json()
        assert links.get("terms") == f"/pages/{new_slug}", links.get("terms")
        assert s.get(f"{BASE}/pages/terms-conditions", params={"locale": "en"}, timeout=30).status_code == 200

        # rotate again — code REPLACED, not stacked
        r2 = s.post(f"{BASE}/admin/delisted-links", json={
            "url": f"https://purepeptide.bg/pages/{new_slug}", "locale": "bg", "reason": "iter41"}, timeout=30)
        link2 = r2.json()["link"]
        link_ids.append(link2["id"])
        rot2 = s.post(f"{BASE}/admin/delisted-links/{link2['id']}/rotate", timeout=240).json()["rotated"]
        h2 = rot2["handle"]
        assert re.fullmatch(r"terms-conditions-[a-z]{3}", h2), h2
        assert h2 != new_slug
        assert s.get(f"{BASE}/pages/{new_slug}", params={"locale": "bg"}, timeout=30).status_code == 404
        assert s.get(f"{BASE}/pages/{h2}", params={"locale": "bg"}, timeout=30).status_code == 200
    finally:
        for lid in link_ids:
            s.delete(f"{BASE}/admin/delisted-links/{lid}", timeout=30)
        pages.replace_one({"slug": "terms-conditions", "locale": "bg"}, original)
        cli.close()


# --- product rotation regression -------------------------------------------------------------
def test_product_rotation_regression_bg():
    cli = MongoClient(os.environ["MONGO_URL"])
    products = cli[os.environ["DB_NAME"]].products
    # use an in-stock product from the review request
    handle = "1-ghk-cu"
    original = products.find_one({"handle": handle})
    assert original, f"product {handle} must exist"
    s = _login()
    link_ids = []
    try:
        r = s.post(f"{BASE}/admin/delisted-links", json={
            "url": f"https://purepeptide.bg/products/{handle}", "locale": "bg", "reason": "iter41"}, timeout=30)
        link = r.json()["link"]
        link_ids.append(link["id"])
        rot = s.post(f"{BASE}/admin/delisted-links/{link['id']}/rotate", timeout=240).json()["rotated"]
        new_h = rot["handle"]
        assert re.fullmatch(rf"{handle}-[a-z]{{3}}", new_h), new_h
        # new handle reachable, old handle 404s on bg locale
        assert s.get(f"{BASE}/products/{new_h}", params={"locale": "bg"}, timeout=30).status_code == 200
        assert s.get(f"{BASE}/products/{handle}", params={"locale": "bg"}, timeout=30).status_code == 404
    finally:
        for lid in link_ids:
            s.delete(f"{BASE}/admin/delisted-links/{lid}", timeout=30)
        # restore product doc
        products.replace_one({"handle": original["handle"]}, original)
        cli.close()
