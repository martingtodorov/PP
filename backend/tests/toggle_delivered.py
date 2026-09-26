"""Toggle a preview COD order to delivered (or restore) for admin UI e2e.

Usage:
  python toggle_delivered.py set    -> print order_id it delivered
  python toggle_delivered.py reset  -> restore from /tmp/iter67_orig.json
"""
import asyncio, json, os, sys, pathlib
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
import nextlevel

BACKUP = pathlib.Path("/tmp/iter67_orig.json")

async def main():
    mode = sys.argv[1]
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    nextlevel._db = db

    if mode == "set":
        o = await db.orders.find_one(
            {"payment_method": "cod", "status": {"$ne": "cancelled"},
             "fulfillment_status": {"$ne": "delivered"},
             "customer_email": {"$nin": ["", None]}}, {"_id": 0})
        if not o:
            print("NONE"); return
        orig = {k: o.get(k) for k in ("payment_status","paid_at","paid_by","fulfillment_status","status")}
        orig["shipment"] = o.get("shipment") or {}
        orig["id"] = o["id"]
        BACKUP.write_text(json.dumps(orig, default=str))
        await nextlevel.mark_delivered(o["id"])
        print(o["id"])
    elif mode == "reset":
        orig = json.loads(BACKUP.read_text())
        oid = orig.pop("id")
        setops = {"fulfillment_status": orig["fulfillment_status"], "status": orig["status"], "shipment": orig["shipment"]}
        unset = {}
        for k in ("payment_status","paid_at","paid_by"):
            if orig[k] is None: unset[k] = ""
            else: setops[k] = orig[k]
        upd = {"$set": setops}
        if unset: upd["$unset"] = unset
        await db.orders.update_one({"id": oid}, upd)
        print("restored", oid)

asyncio.run(main())
