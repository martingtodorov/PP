"""Create one real shipment per courier/country through nextlevel.py, print/track it, then cancel it."""
import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

import nextlevel  # noqa: E402

RECEIVER = {"full_name": "TEST PurePeptide Тест", "phone": "+359878279269", "email": "contact@purepeptide.bg"}
ITEMS = [{"title": "Sermorelin 5mg", "quantity": 1, "price_eur": 59.0}]


def order(tag, country, delivery, shipping, payment="cod", currency="EUR", total_eur=62.89, total_orig=None):
    return {"id": f"nltest-{tag}-{uuid.uuid4().hex[:6]}", "order_number": f"TEST-{tag.upper()}",
            "customer_name": RECEIVER["full_name"], "customer_email": RECEIVER["email"], "customer_phone": RECEIVER["phone"],
            "items": ITEMS, "payment_method": payment, "currency": currency, "total_eur": total_eur, "total_orig": total_orig,
            "shipping": {**RECEIVER, "country": country, **shipping}, "delivery": delivery, "status": "test",
            "source": "nextlevel-selftest"}


async def office(cfg, country, courier, machine=None, search=None):
    params = {"country": country, "courier": courier}
    if search:
        params["search"] = search
    offs = await nextlevel._call(cfg, "GET", "/offices", params=params)
    if machine is not None:
        offs = [o for o in offs if bool(o.get("is_machine")) == machine]
    o = offs[0]
    return {"provider_key": courier.lower(), "destination_type": "locker" if o.get("is_machine") else "office",
            "office": {"id": f"{courier.lower()}:{o['id']}", "code": o.get("office_code"), "name": o["name"], "city": o["place"],
                       "postal_code": o.get("post_code")}}, o


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    nextlevel._db = db
    cfg = await nextlevel.get_config()
    cases = []
    d, o = await office(cfg, "BG", "Econt", machine=False, search="София")
    cases.append(("econt-office", order("econt-office", "BG", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    d, o = await office(cfg, "BG", "Econt", machine=True)
    cases.append(("econt-locker", order("econt-locker", "BG", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    cases.append(("econt-address", order("econt-address", "BG", {"provider_key": "econt", "destination_type": "address"},
                                         {"city": "София", "postal_code": "1000", "line1": "бул. Витоша 1", "note": "тест — не доставяй"})))
    d, o = await office(cfg, "BG", "Speedy", machine=False, search="София")
    cases.append(("speedy-office", order("speedy-office", "BG", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    d, o = await office(cfg, "BG", "BoxNow", machine=True, search="София")
    cases.append(("boxnow-locker", order("boxnow-locker", "BG", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    d, o = await office(cfg, "BG", "Sameday", machine=True, search="София")
    cases.append(("sameday-locker", order("sameday-locker", "BG", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    cases.append(("bank-transfer-no-cod", order("bank", "BG", {"provider_key": "econt", "destination_type": "address"},
                                                {"city": "София", "postal_code": "1000", "line1": "бул. Витоша 1"}, payment="bank_transfer")))
    d, o = await office(cfg, "RO", "FAN", machine=False)
    cases.append(("fan-ro-office", order("fan-office", "RO", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]},
                                         currency="RON", total_orig=319.0)))
    cases.append(("fan-ro-address", order("fan-address", "RO", {"provider_key": "fan", "destination_type": "address"},
                                          {"city": "București", "postal_code": "010101", "line1": "Calea Victoriei 1"}, currency="RON", total_orig=319.0)))
    cases.append(("ro-wrong-currency", order("ro-eur", "RO", {"provider_key": "fan", "destination_type": "address"},
                                             {"city": "București", "postal_code": "010101", "line1": "Calea Victoriei 1"}, currency="EUR")))
    d, o = await office(cfg, "HU", "GLS", machine=False)
    cases.append(("gls-hu-office", order("gls-hu", "HU", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]},
                                         currency="HUF", total_orig=25990.0)))
    cases.append(("gls-de-address", order("gls-de", "DE", {"provider_key": "gls", "destination_type": "address"},
                                          {"city": "Berlin", "postal_code": "10115", "line1": "Unter den Linden 1"}, payment="bank_transfer")))
    d, o = await office(cfg, "GR", "ACS", machine=False)
    cases.append(("acs-gr-office", order("acs-gr", "GR", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    d, o = await office(cfg, "GR", "BoxNow", machine=True)
    cases.append(("boxnow-gr-locker", order("boxnow-gr", "GR", d, {"city": o["place"], "postal_code": o["post_code"], "line1": o["address"]})))
    cases.append(("no-postcode", order("nopc", "BG", {"provider_key": "econt", "destination_type": "address"},
                                       {"city": "Бистрица", "postal_code": "", "line1": "Главна 5"})))

    results = []
    for tag, o in cases:
        await db.orders.insert_one(dict(o))
        row = {"case": tag}
        try:
            sh = await nextlevel.create_shipment(o["id"])
            row.update(awb=sh["awb"], courier=sh.get("courier"), status=sh.get("status"), price=sh.get("price"),
                       tracking=bool(sh.get("tracking_link")), cod=(sh["payload"].get("services") or {}).get("cod"))
            try:
                pdf = await nextlevel.label_pdf(o["id"])
                row["label_pdf_kb"] = round(len(pdf) / 1024, 1)
            except Exception as ex:
                row["label_error"] = str(ex)[:120]
            try:
                tr = await nextlevel.track([sh["awb"]])
                row["track"] = (tr[0].get("status") if tr else "empty")
            except Exception as ex:
                row["track_error"] = str(ex)[:120]
            try:
                c = await nextlevel.cancel_shipment(o["id"])
                row["cancel"] = c["response"]
            except Exception as ex:
                row["cancel_error"] = str(getattr(ex, "detail", ex))[:160]
        except Exception as ex:
            row["error"] = str(getattr(ex, "detail", ex))[:200]
        await db.orders.delete_one({"id": o["id"]})
        results.append(row)
        print(json.dumps(row, ensure_ascii=False))
    json.dump(results, open("/app/memory/nextlevel_live_test.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
