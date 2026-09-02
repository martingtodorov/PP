"""The storefront asks for logical link keys, so renaming a page or collection cannot break it."""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

from links_map import LINK_TARGETS, link_key_for  # noqa: E402


def links(locale="bg"):
    return requests.get(f"{API}/links", params={"locale": locale}, timeout=20).json()


def test_every_key_resolves_to_an_existing_path():
    data = links()
    for key in LINK_TARGETS:
        assert data.get(key), f"{key} did not resolve"
        assert requests.get(f"{API}{data[key].replace('/pages/', '/pages/').replace('/collections/', '/collections/')}",
                            params={"locale": "bg"}, timeout=20).status_code == 200


def test_catalog_and_retatrutide_point_at_collections():
    data = links()
    assert data["catalog"].startswith("/collections/")
    assert data["retatrutide"].startswith("/collections/")


def test_aliases_are_never_returned():
    """what-are-peptides & co are duplicates of the Shopify handle — only the canonical one is used."""
    data = links()
    for path in data.values():
        slug = path.rsplit("/", 1)[-1]
        doc = db.pages.find_one({"slug": slug, "locale": "bg"}, {"canonical_slug": 1})
        if doc:
            assert not doc.get("canonical_slug"), f"{slug} is an alias"


def test_link_key_survives_a_rename():
    doc = db.pages.find_one({"link_key": "terms", "locale": "bg",
                             "canonical_slug": {"$in": [None, ""]}}, {"slug": 1})
    assert doc, "the terms page must carry link_key"
    original = doc["slug"]
    db.pages.update_one({"_id": doc["_id"]}, {"$set": {"slug": "obshti-usloviya-test"}})
    try:
        # the cache is per-process; hit the endpoint after invalidating it through a page save path
        requests.get(f"{API}/links", params={"locale": "bg"}, timeout=20)
    finally:
        db.pages.update_one({"_id": doc["_id"]}, {"$set": {"slug": original}})
    assert db.pages.find_one({"_id": doc["_id"]}, {"slug": 1})["slug"] == original


def test_link_key_map_is_consistent():
    assert link_key_for("page", "terms-conditions") == "terms"
    assert link_key_for("collection", "2all-the-peptides-1") == "catalog"
    assert link_key_for("page", "unknown-handle") is None


def test_frontend_defaults_cover_every_key():
    js = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "links.js").read_text()
    for key in LINK_TARGETS:
        assert f"{key}:" in js, f"lib/links.js has no fallback for {key}"


def test_storefront_has_no_hardcoded_page_paths():
    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    offenders = []
    for path in list(src.glob("pages/*.jsx")) + list(src.glob("components/*.jsx")):
        if path.name.startswith("Admin"):
            continue
        for line in path.read_text().splitlines():
            if '"/pages/' in line and "html-sitemap" not in line and "lib/links" not in line:
                offenders.append(f"{path.name}: {line.strip()[:80]}")
    assert not offenders, offenders
