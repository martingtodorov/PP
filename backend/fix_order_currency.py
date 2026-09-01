"""One-off migration: imported orders in non-EUR currencies (RON etc.) were stored with the
foreign amount inside the *_eur fields. Keep the original amounts in *_orig and convert to real EUR."""
import logging
import os

from dotenv import load_dotenv
from pymongo import MongoClient

from currency import rate_for

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
log = logging.getLogger("fix_currency")

MONEY = ("subtotal_eur", "discount_eur", "shipping_eur", "total_eur")


def run() -> dict:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    fixed = 0
    for o in db.orders.find({"currency": {"$nin": [None, "", "EUR", "eur"]}, "currency_normalized": {"$ne": True}}):
        cur = (o.get("currency") or "EUR").upper()
        rate = rate_for(cur)
        if rate == 1.0:
            db.orders.update_one({"id": o["id"]}, {"$set": {"currency_normalized": True, "currency_rate": 1.0}})
            continue
        upd = {"currency": cur, "currency_rate": rate, "currency_normalized": True}
        for f in MONEY:
            orig = round(float(o.get(f) or 0), 2)
            upd[f.replace("_eur", "_orig")] = orig
            upd[f] = round(orig / rate, 2)
        items = o.get("line_items") or o.get("items") or []
        for it in items:
            price = round(float(it.get("price_eur") or 0), 2)
            it["price_orig"] = price
            it["price_eur"] = round(price / rate, 2)
        upd["line_items" if o.get("line_items") is not None else "items"] = items
        db.orders.update_one({"id": o["id"]}, {"$set": upd})
        fixed += 1

    # recompute customer spend from the normalised EUR totals
    pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": "$customer_info.email", "orders": {"$sum": 1}, "spent": {"$sum": "$total_eur"},
                    "last": {"$max": "$created_at"}, "first": {"$min": "$created_at"}}},
    ]
    touched = 0
    for row in db.orders.aggregate(pipeline):
        if not row["_id"]:
            continue
        res = db.customers.update_one({"email": row["_id"]}, {"$set": {
            "total_orders": row["orders"], "total_spent": round(row["spent"], 2),
            "first_order_at": row["first"], "last_order_at": row["last"]}})
        touched += res.matched_count
    return {"orders_fixed": fixed, "customers_updated": touched}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
