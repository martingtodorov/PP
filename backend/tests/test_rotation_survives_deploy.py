"""A URL rotation must survive a deploy: the rotated handle stays live, the old one stays a 404.

The Shopify export still carries the original handle, so the re-import used to insert the document
under it — the retired URL came back online, the live one disappeared and every admin field
(translations, rotations, order, tags) was lost with it.
"""
import os

import requests
from conftest import run  # noqa: F401  (shared event loop for motor)

import matrixify_import as mi
import server

API = "http://localhost:8001/api"
DB = mi.db


def test_every_handle_a_document_ever_had_is_an_alias():
    doc = {"handle": "sermorelin-erx",
           "translations": {"bg": {"handle": "sermorelin-erx"}},
           "rotations": [{"from": "sermorelin", "to": "sermorelin-erx"},
                         {"from": "sermorelin-erx2", "to": "sermorelin-erx"}]}
    assert mi.handle_aliases(doc) == {"sermorelin", "sermorelin-erx", "sermorelin-erx2"}


def test_the_snapshot_finds_a_rotated_document_under_its_shopify_handle():
    rotated = DB.products.find_one({"rotations.0": {"$exists": True}},
                                   {"_id": 0, "handle": 1, "rotations": 1, "id": 1})
    assert rotated, "no rotated product in the database"
    original = rotated["rotations"][0]["from"]
    snapshot = mi.existing_by_handle("products", mi.KEEP_PRODUCT)
    assert original in snapshot, f"the export handle {original} must hit the live document"
    assert snapshot[original]["handle"] == rotated["handle"]
    assert snapshot[original]["id"] == rotated["id"]


def test_the_import_keeps_the_live_handle():
    for keep in (mi.KEEP_PRODUCT, mi.KEEP_COLLECTION, mi.KEEP_ARTICLE):
        assert "handle" in keep and "rotations" in keep


def test_whatever_is_published_is_never_a_404():
    """An interrupted rotation left its own handle on the retired list and the page vanished."""
    doc = {"handle": "metabolic-studies",
           "translations": {"bg": {"handle": "metabolic-studies-ghx"}},
           "rotations": [{"locale": "bg", "from": "metabolic-studies", "to": "metabolic-studies-ghx"},
                         {"locale": "bg", "from": "metabolic-studies-ghx", "to": "metabolic-studies-qa"}]}
    assert server.retired_handle(doc, "bg", "metabolic-studies-ghx") is False   # published
    assert server.retired_handle(doc, "bg", "metabolic-studies") is True        # retired
    assert server.retired_handle(doc, "bg", "metabolic-studies-qa") is True     # never published


def test_the_ssr_html_and_the_json_api_use_one_rule():
    import inspect

    import prerender

    assert "from server import retired_handle" in inspect.getsource(prerender._retired)


def test_a_rotated_collection_still_lists_its_products():
    """Products keep the collection handle they were imported with — the rotation must follow."""
    col = DB.collections_cat.find_one({"rotations.0": {"$exists": True}, "delisted": {"$ne": True},
                                       "link_key": {"$ne": "catalog"}}, {"_id": 0})
    assert col, "no rotated collection in the database"
    aliases = server.collection_handles(col)
    assert col["rotations"][0]["from"] in aliases
    expected = DB.products.count_documents({"collections": {"$in": aliases},
                                            "active": {"$ne": False}})
    live = server.published_handle(col, "bg")
    res = requests.get(f"{API}/collections/{live}", params={"locale": "bg"}, timeout=20)
    assert res.status_code == 200, res.text
    assert len(res.json()["products"]) == expected > 0


def test_the_retired_handles_of_that_collection_are_gone():
    col = DB.collections_cat.find_one({"rotations.0": {"$exists": True}, "delisted": {"$ne": True},
                                       "link_key": {"$ne": "catalog"}}, {"_id": 0})
    live = server.published_handle(col, "bg")
    for old in server.collection_handles(col):
        if old == live:
            continue
        assert requests.get(f"{API}/collections/{old}", params={"locale": "bg"},
                            timeout=20).status_code == 404, old
        assert requests.get(f"{API}/seo/prerender", params={"path": f"/collections/{old}"},
                            timeout=30).status_code == 404, old
