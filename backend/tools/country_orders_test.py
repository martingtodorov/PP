"""Fire one real COD order per shipping country through the public checkout, report what the
NextLevel fulfillment integration did with it, then clean everything up.

    python backend/tools/country_orders_test.py            # place + report (orders stay)
    python backend/tools/country_orders_test.py --cleanup   # cancel + delete every test order
"""
import argparse
import asyncio
import json
import os
import sys

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(os.path.dirname(ROOT), "frontend", ".env"))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}
MARK = "country-selftest"

# owner's choice: office/locker where the account supports it, address for CZ/DE/IT
PLAN = {
    "RO": ("office", "ro"), "GR": ("office", "gr"), "HU": ("office", "hu"), "PL": ("office", "pl"),
    "SK": ("office", "sk"), "SI": ("office", "si"), "HR": ("office", "en"),
    "CZ": ("address", "cz"), "DE": ("address", "en"), "IT": ("address", "en"),
}
ADDRESSES = {  # fallback address per country (NextLevel needs city + postal code)
    "CZ": ("Praha", "11000", "Václavské náměstí 1"),
    "DE": ("Berlin", "10115", "Invalidenstraße 1"),
    "IT": ("Milano", "20121", "Via Dante 1"),
    "RO": ("Bucuresti", "010011", "Calea Victoriei 1"),
    "GR": ("Athina", "10431", "Stadiou 1"),
    "HU": ("Budapest", "1051", "Bajcsy-Zsilinszky út 1"),
    "PL": ("Warszawa", "00-001", "Marszałkowska 1"),
    "SK": ("Bratislava", "81101", "Hlavná 1"),
    "SI": ("Ljubljana", "1000", "Slovenska cesta 1"),
    "HR": ("Zagreb", "10000", "Ilica 1"),
}
CONTACT = {"full_name": "TEST QA Country", "phone": "+359878279269", "email": "qa-country@example.com"}


async def pick_item(c: httpx.AsyncClient):
    prods = (await c.get(f"{BASE}/api/products?locale=bg")).json()
    for p in prods.get("products", prods if isinstance(prods, list) else []):
        for v in p.get("variants") or []:
            if (v.get("stock") or 0) > 1:
                return {"product_id": p["id"], "variant_sku": v["sku"], "quantity": 1}, f"{p['title']} {v['name']}"
    raise SystemExit("no product in stock")


async def method_for(c: httpx.AsyncClient, country: str, want: str):
    cfg = (await c.get(f"{BASE}/api/nextcart/config", params={"country": country})).json()
    methods = cfg.get("delivery_methods") or []
    order = {"office": ["office", "locker", "address"], "address": ["address", "office", "locker"]}[want]
    for dest in order:
        m = next((x for x in methods if x.get("destination_type") == dest), None)
        if m:
            return m, [f"{x.get('provider_key')}/{x.get('destination_type')}" for x in methods]
    return None, []


async def pickup_for(c: httpx.AsyncClient, country: str, m: dict):
    r = await c.get(f"{BASE}/api/nextcart/pickups", params={
        "provider_key": m["provider_key"], "destination_type": m["destination_type"], "country": country})
    for o in (r.json().get("pickups") or []):
        if o.get("postal_code") and o.get("city"):
            return o
    return None


async def place(c: httpx.AsyncClient, country: str, item: dict):
    want, locale = PLAN[country]
    m, available = await method_for(c, country, want)
    if not m:
        return {"country": country, "ok": False, "error": "няма нито един метод на доставка"}
    pickup = await pickup_for(c, country, m) if m["destination_type"] in ("office", "locker") else None
    city, postal, street = ADDRESSES[country]
    ship = {**CONTACT, "country": country,
            "line1": f"{pickup['name']}, {pickup.get('address', '')}" if pickup else street,
            "city": pickup["city"] if pickup else city,
            "postal_code": pickup["postal_code"] if pickup else postal,
            "note": "ТЕСТ — не изпращай"}
    payload = {
        "items": [item], "shipping": ship, "customer_email": CONTACT["email"],
        "customer_name": CONTACT["full_name"], "customer_phone": CONTACT["phone"],
        "shipping_method": m["key"], "payment_method": "cod",
        "delivery": {"provider_key": m["provider_key"], "provider_name": m.get("provider_name") or "",
                     "method_key": m["key"], "destination_type": m["destination_type"],
                     "label": m.get("label") or "", "price_amount": float(m.get("price_amount") or 0),
                     "currency": "EUR",
                     "office": {"id": pickup["id"], "name": pickup["name"], "address": pickup.get("address", ""),
                                "city": pickup["city"], "postal_code": pickup["postal_code"]} if pickup else None,
                     "address": None if pickup else {"city": city, "postal_code": postal, "street": street}},
        "notes": MARK, "terms_accepted": True, "locale": locale,
    }
    r = await c.post(f"{BASE}/api/checkout", json=payload)
    if r.status_code >= 400:
        return {"country": country, "ok": False, "method": m["key"], "available": available,
                "error": f"checkout {r.status_code}: {r.text[:200]}"}
    o = r.json()["order"]
    return {"country": country, "ok": True, "id": o["id"], "order_number": o["order_number"],
            "method": m["key"], "dest": m["destination_type"], "office": (pickup or {}).get("name"),
            "currency": o.get("currency"), "total": o.get("total_orig", o.get("total_eur")),
            "locale": locale, "available": available}


async def report(db, rows):
    print("\n=== Резултат ===")
    for r in rows:
        if not r.get("ok"):
            print(f"{r['country']}: ❌ {r.get('error')}  (методи: {r.get('available')})")
            continue
        o = await db.orders.find_one({"id": r["id"]}, {"_id": 0, "fulfillment": 1, "fulfillment_error": 1, "wc_id": 1})
        ff = (o or {}).get("fulfillment") or {}
        state = (f"✅ webhook → nl_id {ff.get('nl_id')} ({ff.get('transport')}, wc {ff.get('wc_status')})"
                 if ff.get("number") else f"❌ {(o or {}).get('fulfillment_error') or 'няма фулфилмент запис'}")
        print(f"{r['country']}: {r['order_number']} {r['total']} {r['currency']} · {r['method']}"
              f"{' · ' + r['office'] if r.get('office') else ''} → {state}")


async def cleanup(db, c: httpx.AsyncClient):
    orders = await db.orders.find({"notes": MARK}, {"_id": 0}).to_list(50)
    print(f"Изтривам {len(orders)} тестови поръчки…")
    for o in orders:
        if (o.get("fulfillment") or {}).get("number"):
            r = await c.delete(f"{BASE}/api/admin/orders/{o['id']}/fulfillment")
            print(f"  {o['order_number']}: cancel {r.status_code}")
        for li in o.get("items") or []:
            await db.products.update_one({"id": li["product_id"], "variants.sku": li["variant_sku"]},
                                         {"$inc": {"variants.$.stock": li["quantity"]}})
        await db.inventory_log.delete_many({"reason": f"Поръчка {o['order_number']}"})
        await db.orders.delete_one({"id": o["id"]})
    await db.customers.delete_many({"email": CONTACT["email"]})
    await db.abandoned_carts.delete_many({"email": CONTACT["email"]})


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as c:
        r = await c.post(f"{BASE}/api/auth/login", json=ADMIN)
        r.raise_for_status()
        if args.cleanup:
            await cleanup(db, c)
            return
        item, name = await pick_item(c)
        print(f"Артикул: {name}\n")
        countries = [x.strip().upper() for x in args.only.split(",") if x.strip()] or list(PLAN)
        rows = []
        for country in countries:
            res = await place(c, country, item)
            rows.append(res)
            print(json.dumps(res, ensure_ascii=False))
            await asyncio.sleep(2)
        await asyncio.sleep(6)
        await report(db, rows)


if __name__ == "__main__":
    asyncio.run(main())
