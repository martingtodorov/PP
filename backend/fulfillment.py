"""NextLevel Fulfillment — the warehouse receives the ORDER (SKUs, quantities, receiver) and packs +
issues the waybill itself. Owner's choice: when this is enabled we do NOT create shipments ourselves.

Docs: https://nextlevel-delivery.readme.io/reference/create-new-order
Two transports: the authenticated API (`app-id ff-…` + `app-secret`, gives back number/status/awb) or the
per-shop inbound webhook URL (`https://api.nextlevel.delivery/webhooks/orders/ff-…`, fire-and-forget).
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import nextlevel
from nextlevel import COUNTRY_CURRENCY, NextLevelError, office_id_of

log = logging.getLogger("purepeptide.fulfillment")

API = "https://api.nextlevel.delivery/v1/fulfillment/orders"
SETTINGS_KEY = "integrations.nextlevel_fulfillment"
SYNC_SEC = 600
DONE_STATUSES = {"delivered", "returned", "cancelled", "duplicated", "trash"}
# checkout provider_key → NextLevel courier name (address deliveries only; offices carry the courier)
COURIER_NAMES = {"econt": "Econt", "boxnow": "BoxNow", "speedy": "Speedy", "sameday": "Sameday", "fancourier": "FAN",
                 "speedex": "Speedex", "gls": "GLS", "acs": "ACS", "geniki": "Geniki"}
_db = None
_client = httpx.AsyncClient(timeout=40)

DEFAULTS = {"enabled": False, "auto_create": True, "app_id": "", "app_secret": "", "webhook_url": "",
            "weight": 0.1, "send_courier": True,
            # what the waybill declares as contents (owner's decision: never the SKU list)
            "contents_text": "аминокиселини",
            "open_before_pay": True, "obpd_option": "OPEN", "obpd_return_payer": "SENDER",
            "wc_consumer_key": "", "wc_consumer_secret": "", "wc_country": "BG"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_config() -> Dict[str, Any]:
    doc = await _db.settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    cfg = {**DEFAULTS, **((doc or {}).get("value") or {})}
    cfg["app_id"] = cfg["app_id"] or os.environ.get("NEXTLEVEL_FF_APP_ID", "")
    cfg["app_secret"] = cfg["app_secret"] or os.environ.get("NEXTLEVEL_FF_APP_SECRET", "")
    if cfg["app_id"] and not cfg["webhook_url"]:
        cfg["webhook_url"] = f"https://api.nextlevel.delivery/webhooks/orders/{cfg['app_id']}"
    cfg["has_api"] = bool(cfg["app_id"] and cfg["app_secret"])
    cfg["has_wc"] = bool(cfg["wc_consumer_key"] and cfg["wc_consumer_secret"])
    cfg["shop_type"] = "api" if cfg["has_api"] else ("woocommerce" if cfg["has_wc"] else "webhook")
    return cfg


def _headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    if not cfg.get("has_api"):
        raise HTTPException(400, "Липсват app-id / app-secret на фулфилмент магазина в NextLevel")
    return {"app-id": cfg["app_id"], "app-secret": cfg["app_secret"], "accept": "application/json"}


async def _call(cfg: Dict[str, Any], method: str, path: str = "", **kw) -> Any:
    r = await _client.request(method, f"{API}{path}", headers=_headers(cfg), **kw)
    try:
        data = r.json()
    except ValueError:
        data = {"error": {"code": r.status_code, "message": r.text[:300]}}
    if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
        msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else str(data)
        raise NextLevelError(f"NextLevel {r.status_code}: {msg or 'грешка'}", r.status_code, data)
    return data


# ---------------------------------------------------------------- payload
def _local(order: Dict[str, Any], key: str) -> float:
    v = order.get(f"{key}_orig")
    return round(float(v if v is not None else (order.get(f"{key}_eur") or 0)), 2)


def build_order(order: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Raise ValueError with a human reason when the order cannot be handed to the warehouse as-is."""
    ship = order.get("shipping") or {}
    delivery = order.get("delivery") or {}
    country = (ship.get("country") or "").upper()
    currency = COUNTRY_CURRENCY.get(country, "EUR")
    have = (order.get("currency") or "EUR").upper()
    if currency != "EUR" and have != currency:
        raise ValueError(f"Поръчката за {country} трябва да е в {currency}, а е в {have}")

    items = order.get("items") or []
    if not items:
        raise ValueError("Поръчката няма артикули")
    products = []
    for it in items:
        sku = (it.get("variant_sku") or it.get("sku") or "").strip()
        if not sku:
            raise ValueError(f"Артикул „{it.get('title', '')}“ няма SKU")
        price = it.get("price_orig") if it.get("price_orig") is not None else it.get("price_eur")
        title, variant = str(it.get("title") or ""), str(it.get("variant_name") or "")
        name = (title if not variant or variant.lower() in title.lower() else f"{title} {variant}").strip()[:150]
        products.append({"sku": sku, "name": name or sku, "quantity": int(it.get("quantity") or 1),
                         "unit_price": round(float(price or 0), 2), "weight": float(cfg.get("weight") or 0.1)})

    receiver: Dict[str, Any] = {
        "name": (ship.get("full_name") or order.get("customer_name") or "").strip()[:100],
        "phone": (ship.get("phone") or order.get("customer_phone") or "").strip(),
    }
    email = (ship.get("email") or order.get("customer_email") or "").strip()
    if email:
        receiver["email"] = email
    if not receiver["name"] or not receiver["phone"]:
        raise ValueError("Липсва име или телефон на получателя")
    office_id = office_id_of(delivery)
    if delivery.get("destination_type") in ("office", "locker") and office_id is None:
        raise ValueError("Офисът/автоматът от чекаута няма NextLevel идентификатор")
    # NextLevel requires receiver.country on EVERY shipment, office/locker deliveries included
    receiver["country"] = country or (cfg.get("wc_country") or "").upper()
    if not receiver["country"]:
        raise ValueError("Поръчката няма държава на получателя (receiver.country)")
    if office_id is not None:
        receiver["office_id"] = office_id
        if ship.get("city"):
            receiver["place"] = ship["city"].strip()
    else:
        if not ship.get("city") or not ship.get("postal_code"):
            raise ValueError("За доставка до адрес NextLevel изисква държава, град и пощенски код")
        receiver.update({"place": ship["city"].strip(), "post_code": str(ship["postal_code"]).strip(),
                         "street": (ship.get("line1") or "").strip()[:200] or "-"})
        if ship.get("line2"):
            receiver["other"] = str(ship["line2"])[:200]

    shipping = _local(order, "shipping")
    is_cod = order.get("payment_method") == "cod"
    # a bank transfer covers the shipping too, so the warehouse must not charge it again
    prepaid_shipping = not is_cod
    payload: Dict[str, Any] = {
        "order_id": str(order.get("order_number") or order.get("id")),
        "ref": str(order.get("order_number") or ""),
        "ref2": str(order.get("id") or "")[:60],
        "products": products,
        "price": round(_local(order, "subtotal") - _local(order, "discount"), 2),
        "currency": currency,
        "shipping_price": 0.0 if prepaid_shipping else shipping,
        "is_shipping_free": prepaid_shipping or shipping <= 0,
        "receiver": receiver,
        "payment_method": "cod" if is_cod else "bank_transfer",
        "is_paid": (not is_cod) or order.get("payment_status") == "paid",
        "contents": (cfg.get("contents_text") or DEFAULTS["contents_text"])[:200],
    }
    note = " ".join(str(x) for x in [order.get("notes"), ship.get("note")] if x).strip()
    if note:
        payload["note"] = note[:500]
    courier = COURIER_NAMES.get((delivery.get("provider_key") or "").lower())
    if office_id is None and courier and cfg.get("send_courier", True):
        payload["courier"] = courier
    if is_cod:
        payload["services"] = {"cod": {"amount": _local(order, "total"), "currency": currency,
                                       "processing_type": "CASH", "included_shipping_price": True}}
        obpd = nextlevel.obpd_of({**nextlevel.DEFAULTS, "open_before_pay": cfg.get("open_before_pay", True),
                                  "obpd_option": cfg.get("obpd_option"), "obpd_return_payer": cfg.get("obpd_return_payer")})
        if obpd:
            payload["services"]["obpd"] = obpd
    return payload


def _summary(res: Dict[str, Any], transport: str) -> Dict[str, Any]:
    status = res.get("status")
    status_name = status.get("name") if isinstance(status, dict) else status
    status_id = status.get("id") if isinstance(status, dict) else res.get("status_id")
    return {
        "transport": transport,
        "number": str(res.get("number") or ""),
        "nl_id": res.get("id"),
        "status": status_name,
        "status_id": status_id,
        "awb": str(res.get("awb") or "") or None,
        "courier": res.get("courier"),
        "shipment_status": res.get("shipment_status_text") or res.get("shipment_status"),
        "tracking_link": res.get("tracking_link") if res.get("awb") else None,
        "total": res.get("total"),
        "created_at": _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------------- operations
async def _send(cfg: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if cfg.get("has_api"):
        try:
            res = await _call(cfg, "POST", "/", json=payload)
        except NextLevelError as ex:
            if "courier is invalid" in str(ex).lower() and payload.get("courier"):
                res = await _call(cfg, "POST", "/", json={k: v for k, v in payload.items() if k != "courier"})
            else:
                raise
        return _summary(res, "api")
    if not cfg.get("webhook_url"):
        raise NextLevelError("Няма нито API ключове, нито webhook адрес за фулфилмент", 400)
    r = await _client.post(cfg["webhook_url"], json=payload, headers={"accept": "application/json"})
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or not (data or {}).get("success", True):
        raise NextLevelError(f"NextLevel webhook {r.status_code}: {(data or {}).get('error') or r.text[:200]}", r.status_code, data)
    return {**_summary({"id": data.get("id"), "status": data.get("status") or "pending"}, "webhook"),
            "number": str(data.get("order_id") or payload["order_id"])}


async def create_order(order_id: str, force: bool = False) -> Dict[str, Any]:
    cfg = await get_config()
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Поръчката не е намерена")
    ff = order.get("fulfillment") or {}
    if ff.get("number") and (ff.get("status") or "") not in DONE_STATUSES and not force:
        raise HTTPException(409, f"Вече има фулфилмент поръчка {ff['number']}")
    if cfg.get("shop_type") == "woocommerce":
        return await _create_via_woocommerce(order, cfg)
    try:
        payload = build_order(order, cfg)
    except ValueError as ex:
        await _db.orders.update_one({"id": order_id}, {"$set": {"fulfillment_error": str(ex), "fulfillment_error_at": _now()}})
        raise HTTPException(422, str(ex))
    try:
        summary = await _send(cfg, payload)
    except NextLevelError as ex:
        await _db.orders.update_one({"id": order_id}, {"$set": {"fulfillment_error": str(ex), "fulfillment_error_at": _now()}})
        raise HTTPException(502, str(ex))
    record = {**summary, "payload": payload}
    await _db.orders.update_one({"id": order_id}, {
        "$set": {"fulfillment": record, "fulfillment_status": "processing" if order.get("fulfillment_status") == "unfulfilled" else order.get("fulfillment_status")},
        "$unset": {"fulfillment_error": "", "fulfillment_error_at": ""}})
    log.info("Fulfillment order %s for %s via %s (%s)", record.get("number"), order.get("order_number"), record["transport"], record.get("status"))
    if record.get("awb"):
        await _apply_awb(order, record)
    return record


async def _create_via_woocommerce(order: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """WooCommerce-type shop: NextLevel gets an order.created webhook and reads the rest over our WC façade."""
    import wc_api

    if not cfg.get("webhook_url"):
        raise HTTPException(400, "Няма webhook адрес на магазина (въведете app-id ff-…)")
    wc = wc_api.to_wc_order(order, cfg)
    try:
        res = await wc_api.push_webhook(order, cfg, "order.created")
    except Exception as ex:
        await _db.orders.update_one({"id": order["id"]}, {"$set": {"fulfillment_error": str(ex), "fulfillment_error_at": _now()}})
        raise HTTPException(502, f"NextLevel webhook: {ex}")
    if res["status_code"] >= 400:
        await _db.orders.update_one({"id": order["id"]}, {"$set": {"fulfillment_error": str(res["response"]), "fulfillment_error_at": _now()}})
        raise HTTPException(502, f"NextLevel webhook {res['status_code']}: {res['response']}")
    record = {"transport": "woocommerce", "number": wc["number"], "wc_id": wc["id"], "nl_id": (res["response"] or {}).get("id") if isinstance(res["response"], dict) else None,
              "status": (res["response"] or {}).get("status") if isinstance(res["response"], dict) else "pending", "wc_status": wc["status"],
              "awb": None, "courier": None, "created_at": _now(), "updated_at": _now(),
              "payload": {"order_id": wc["number"], "contents": (cfg.get("contents_text") or DEFAULTS["contents_text"])[:200]}}
    await _db.orders.update_one({"id": order["id"]}, {"$set": {"fulfillment": record, "wc_id": wc["id"]},
                                                      "$unset": {"fulfillment_error": "", "fulfillment_error_at": ""}})
    log.info("WooCommerce webhook order.created for %s → %s", order.get("order_number"), res["status_code"])
    return record


async def _apply_awb(order: Dict[str, Any], ff: Dict[str, Any]) -> None:
    """The warehouse issued the waybill → the customer sees/gets it exactly like our own shipments."""
    courier = ff.get("courier")
    awb = ff["awb"]
    shipment = {"awb": awb, "courier_awb": None, "courier": courier, "status": ff.get("shipment_status") or "Created",
                "tracking_link": ff.get("tracking_link") or nextlevel.tracking_url_for(courier, awb, awb) or f"https://nextlevel.delivery/track?awb={awb}",
                "source": "fulfillment", "created_at": _now(), "updated_at": _now()}
    tracking = {"tracking_number": awb, "tracking_url": shipment["tracking_link"], "carrier": courier or "NextLevel"}
    await _db.orders.update_one({"id": order["id"], "shipment.awb": {"$ne": awb}}, {
        "$set": {"shipment": shipment, "tracking": tracking, "tracking_number": awb, "fulfillment_status": "shipped"}})
    if order.get("customer_email") and not (order.get("shipment") or {}).get("awb") == awb:
        asyncio.create_task(nextlevel._notify_customer({**order, "shipment": shipment}))


async def cancel_order(order_id: str) -> Dict[str, Any]:
    cfg = await get_config()
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0, "fulfillment": 1})
    number = (order or {}).get("fulfillment", {}).get("number")
    if not number:
        raise HTTPException(404, "Няма фулфилмент поръчка")
    if order["fulfillment"].get("transport") == "woocommerce":
        import wc_api

        full = await _db.orders.find_one({"id": order_id}, {"_id": 0})
        try:
            res = await wc_api.push_webhook({**full, "status": "cancelled"}, cfg, "order.updated")
        except Exception as ex:
            raise HTTPException(502, f"NextLevel webhook: {ex}")
        await _db.orders.update_one({"id": order_id}, {"$set": {"fulfillment.status": "cancelled", "fulfillment.cancelled_at": _now(),
                                                                "fulfillment.updated_at": _now()}})
        return {"cancelled": True, "number": number, "response": res["response"],
                "note": "Изпратен е webhook order.updated със статус cancelled — проверете в панела на NextLevel"}
    if (order["fulfillment"].get("transport") == "webhook") and not cfg.get("has_api"):
        raise HTTPException(400, "Поръчката е подадена през webhook — откажете я в панела на NextLevel или добавете API ключове")
    try:
        res = await _call(cfg, "POST", f"/{number}/cancel")
    except NextLevelError as ex:
        raise HTTPException(502, str(ex))
    await _db.orders.update_one({"id": order_id}, {"$set": {"fulfillment.status": "cancelled", "fulfillment.status_id": 3,
                                                            "fulfillment.cancelled_at": _now(), "fulfillment.updated_at": _now()}})
    return {"cancelled": True, "number": number, "response": res}


async def refresh_order(order_id: str) -> Dict[str, Any]:
    cfg = await get_config()
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    ff = (order or {}).get("fulfillment") or {}
    if not order or not ff:
        raise HTTPException(404, "Няма фулфилмент поръчка")
    if not cfg.get("has_api"):
        raise HTTPException(400, "Статусът идва от NextLevel през WooCommerce API-то (PUT /orders) — няма какво да се дърпа без app-secret")
    try:
        res = await _call(cfg, "GET", f"/external/{ff['payload']['order_id']}")
    except NextLevelError as ex:
        raise HTTPException(502, str(ex))
    if isinstance(res, list):
        res = res[0] if res else {}
    fresh = _summary(res, ff.get("transport") or "api")
    patch = {f"fulfillment.{k}": v for k, v in fresh.items() if k not in ("created_at", "transport") and v is not None}
    await _db.orders.update_one({"id": order_id}, {"$set": patch})
    if fresh.get("awb"):
        await _apply_awb(order, fresh)
    if str(fresh.get("status") or "").lower() == "delivered" or str(fresh.get("shipment_status") or "").lower() == "delivered":
        await nextlevel.notify_delivered(order_id)
    return {**ff, **{k: v for k, v in fresh.items() if v is not None}}


async def sync_open_orders() -> Dict[str, Any]:
    cfg = await get_config()
    if not cfg.get("has_api"):
        return {"open": 0, "updated": 0, "skipped": "no api keys"}
    cursor = _db.orders.find({"fulfillment.number": {"$exists": True}, "fulfillment.status": {"$nin": list(DONE_STATUSES)}},
                             {"_id": 0, "id": 1})
    ids = [o["id"] for o in await cursor.to_list(300)]
    updated = 0
    for oid in ids:
        try:
            await refresh_order(oid)
            updated += 1
        except Exception as ex:
            log.warning("Fulfillment refresh %s failed: %s", oid, ex)
    return {"open": len(ids), "updated": updated}


async def sync_loop():
    while True:
        try:
            cfg = await get_config()
            if cfg.get("enabled"):
                await sync_open_orders()
        except Exception as ex:
            log.warning("Fulfillment sync loop: %s", ex)
        await asyncio.sleep(SYNC_SEC)


async def dispatch_new_order(order_id: str):
    """Called after checkout: warehouse order when fulfillment is on, otherwise our own waybill.

    Bank-transfer orders are NEVER submitted automatically (owner's decision) — the admin presses
    „Подай към склада“ himself, so nothing reaches the warehouse before the money does."""
    try:
        cfg = await get_config()
        order = await _db.orders.find_one({"id": order_id}, {"_id": 0, "payment_method": 1})
        if (order or {}).get("payment_method") != "cod":
            return
        if not cfg.get("enabled"):
            await nextlevel.auto_create(order_id)
            return
        if not cfg.get("auto_create"):
            return
        await create_order(order_id)
    except HTTPException as ex:
        log.warning("Fulfillment auto-create for %s failed: %s", order_id, ex.detail)
    except Exception:
        log.exception("Fulfillment auto-create for %s crashed", order_id)


async def on_paid(order_id: str):
    """Marking a bank transfer as paid does NOT submit it either — submission stays manual."""
    return


# ---------------------------------------------------------------- admin API
class ConfigIn(BaseModel):
    enabled: Optional[bool] = None
    auto_create: Optional[bool] = None
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    weight: Optional[float] = None
    contents_text: Optional[str] = None
    send_courier: Optional[bool] = None
    open_before_pay: Optional[bool] = None
    wc_consumer_key: Optional[str] = None
    wc_consumer_secret: Optional[str] = None
    wc_country: Optional[str] = None


def _masked(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    out["app_secret"] = ("•" * 8 + cfg["app_secret"][-4:]) if cfg.get("app_secret") else ""
    out["wc_consumer_secret"] = ("•" * 8 + cfg["wc_consumer_secret"][-4:]) if cfg.get("wc_consumer_secret") else ""
    return out


def init(db_, admin_guard) -> APIRouter:
    global _db
    _db = db_
    router = APIRouter()

    @router.get("/admin/integrations/nextlevel-fulfillment")
    async def read(admin=Depends(admin_guard)):
        return _masked(await get_config())

    @router.put("/admin/integrations/nextlevel-fulfillment")
    async def update(payload: ConfigIn, admin=Depends(admin_guard)):
        patch = {k: v for k, v in payload.model_dump().items() if v is not None}
        for secret_key in ("app_secret", "wc_consumer_secret"):
            if secret_key in patch and patch[secret_key].startswith("•"):
                patch.pop(secret_key)
        if "wc_country" in patch:
            patch["wc_country"] = patch["wc_country"].strip().upper()[:2]
        if "contents_text" in patch:
            patch["contents_text"] = patch["contents_text"].strip()[:200] or DEFAULTS["contents_text"]
        for k in ("app_id", "app_secret", "webhook_url", "wc_consumer_key", "wc_consumer_secret"):
            if k in patch:
                patch[k] = patch[k].strip()
        if patch.get("enabled") and not (await get_config()).get("wc_since"):
            patch["wc_since"] = _now()
        await _db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {f"value.{k}": v for k, v in patch.items()}}, upsert=True)
        return _masked(await get_config())

    @router.post("/admin/integrations/nextlevel-fulfillment/wc-keys")
    async def wc_keys(admin=Depends(admin_guard)):
        import wc_api

        keys = wc_api.gen_keys()
        cfg = await get_config()
        if not cfg.get("wc_since"):
            keys["wc_since"] = _now()  # older orders (and the Shopify history) are shown to the warehouse as completed
        await _db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {f"value.{k}": v for k, v in keys.items()}}, upsert=True)
        return {**_masked(await get_config()), "wc_consumer_secret_plain": keys["wc_consumer_secret"]}

    @router.get("/admin/integrations/nextlevel-fulfillment/wc-log")
    async def wc_log(limit: int = 40, admin=Depends(admin_guard)):
        import wc_api

        return {"events": await wc_api.recent_log(min(limit, 200))}

    @router.post("/admin/integrations/nextlevel-fulfillment/test")
    async def test(admin=Depends(admin_guard)):
        cfg = await get_config()
        if not cfg.get("has_api"):
            if cfg.get("shop_type") == "woocommerce":
                import wc_api

                events = await wc_api.recent_log(5)
                inbound = [e for e in events if e.get("direction") == "inbound"]
                return {"ok": True, "mode": "woocommerce", "webhook_url": cfg.get("webhook_url"),
                        "note": ("NextLevel вече чете магазина през WooCommerce API-то." if inbound else
                                 "WooCommerce ключовете са готови — въведете адреса на магазина и ключовете в панела на NextLevel; тук ще се появят заявките им."),
                        "recent": [{"number": e.get("method"), "order_id": e.get("path"), "status": e.get("status")} for e in events]}
            if cfg.get("webhook_url"):
                return {"ok": True, "mode": "webhook", "webhook_url": cfg["webhook_url"],
                        "note": "Само webhook: поръчките се изпращат, но статус/товарителница не могат да се четат без app-secret."}
            return {"ok": False, "error": "Няма app-id (ff-…) — въведете го, за да получите webhook адреса"}
        try:
            recent = await _call(cfg, "GET", "/", params={"per_page": 5})
        except NextLevelError as ex:
            return {"ok": False, "mode": "api", "error": str(ex)}
        rows = recent if isinstance(recent, list) else recent.get("data") or []
        return {"ok": True, "mode": "api", "count": len(rows),
                "recent": [{"number": r.get("number"), "order_id": r.get("order_id"),
                            "status": (r.get("status") or {}).get("name") if isinstance(r.get("status"), dict) else r.get("status"),
                            "awb": r.get("awb"), "courier": r.get("courier")} for r in rows[:5]]}

    @router.get("/admin/integrations/nextlevel-fulfillment/preview/{order_id}")
    async def preview(order_id: str, admin=Depends(admin_guard)):
        cfg = await get_config()
        order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Поръчката не е намерена")
        try:
            return {"ok": True, "payload": build_order(order, cfg)}
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}

    @router.post("/admin/orders/{order_id}/fulfillment")
    async def create(order_id: str, force: bool = False, admin=Depends(admin_guard)):
        return await create_order(order_id, force=force)

    @router.delete("/admin/orders/{order_id}/fulfillment")
    async def cancel(order_id: str, admin=Depends(admin_guard)):
        return await cancel_order(order_id)

    @router.post("/admin/orders/{order_id}/fulfillment/refresh")
    async def refresh(order_id: str, admin=Depends(admin_guard)):
        return await refresh_order(order_id)

    @router.post("/admin/fulfillment/sync")
    async def sync(admin=Depends(admin_guard)):
        return await sync_open_orders()

    return router
