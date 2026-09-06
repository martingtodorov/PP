"""The owner's manual product order must survive a deploy, a re-seed and a re-import."""
import os

import pymongo
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _admin():
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"],
                                      "password": os.environ["ADMIN_PASSWORD"]},
           timeout=20).raise_for_status()
    return s


def test_the_order_is_saved_in_its_own_collection_too():
    s = _admin()
    col = next(c for c in s.get(f"{API}/admin/collections", timeout=20).json()["collections"]
               if c.get("link_key") == "catalog")
    handle = col["handle"]
    rows = s.get(f"{API}/admin/collections/{handle}/products", timeout=20).json()["products"]
    order = [p["handle"] for p in rows][::-1]
    assert s.put(f"{API}/admin/collections/{handle}/order", json={"handles": order},
                 timeout=20).status_code == 200

    saved = DB.product_orders.find_one({"key": handle}, {"_id": 0})
    assert saved and saved["handles"] == order
    # the storefront hides inactive products, so compare only what it returns
    shown = [p["base_handle"] for p in
             requests.get(f"{API}/collections/{handle}", timeout=20).json()["products"]]
    assert shown == [h for h in order if h in shown]


def test_a_wiped_order_is_restored():
    """A re-seed or a Matrixify re-import replaces the collection document and drops the field."""
    import asyncio

    import server

    col = next(c for c in _admin().get(f"{API}/admin/collections", timeout=20).json()["collections"]
               if c.get("link_key") == "catalog")
    handle = col["handle"]
    saved = DB.product_orders.find_one({"key": handle}, {"_id": 0})["handles"]

    DB.collections_cat.update_one({"handle": handle}, {"$unset": {"product_order": ""}})
    assert asyncio.run(server.restore_product_orders()) >= 1
    assert DB.collections_cat.find_one({"handle": handle}, {"_id": 0})["product_order"] == saved


def test_the_import_keeps_admin_fields_under_the_rotated_handle():
    """The snapshot must find a collection whose handle was moved to the rotated one."""
    import matrixify_import as mi

    snapshot = mi.existing_by_handle("collections_cat", mi.KEEP_COLLECTION)
    for col in DB.collections_cat.find({}, {"_id": 0, "handle": 1, "translations": 1}):
        live = ((col.get("translations") or {}).get("bg") or {}).get("handle")
        assert col["handle"] in snapshot
        if live:
            assert live in snapshot


def test_a_deploy_never_wipes_a_live_catalogue():
    """A new SEED_VERSION used to delete the collections and products (and with them the ordering).
    Now a catalogue with content is left alone unless ALLOW_RESEED=1 is set on purpose."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "server.py")).read()
    guard = src.split("async def seed_catalog")[1].split("async def ")[0]
    assert 'os.environ.get("ALLOW_RESEED") != "1"' in guard
    assert "not re-seeding" in guard
    assert "stale = False" in guard
