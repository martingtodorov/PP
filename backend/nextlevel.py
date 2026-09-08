"""NextLevel Delivery (api.nextlevel.delivery) — waybills for every order.

Everything here follows what the account actually accepts (see memory/nextlevel_mapping.md):
* office/locker deliveries go by `receiver.office_id` (the NextCart office id "econt:4434" → 4434),
* address deliveries need country + place + post_code (mandatory) + street,
* no `courier` is sent — the office or NextLevel's routing decides, which avoids couriers the
  account has no setup for (Speedy RO, DPD RO, Speedy PL/CZ, GLS IT by name…),
* COD only for cash-on-delivery orders: CASH, included_shipping_price=false, in the receiver
  country's currency (NextLevel silently accepts a wrong currency, so we refuse to guess).
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

log = logging.getLogger("purepeptide.nextlevel")

BASE = "https://api.nextlevel.delivery/v1"
SETTINGS_KEY = "integrations.nextlevel"
COUNTRY_CURRENCY = {"RO": "RON", "HU": "HUF", "PL": "PLN", "CZ": "CZK", "UK": "GBP", "GB": "GBP"}
OPEN_STATUSES_DONE = {"Delivered", "Returned", "Cancelled", "Canceled", "Return delivered"}
SYNC_SEC = 600

_db = None
_client = httpx.AsyncClient(timeout=40)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- settings
DEFAULTS = {"enabled": False, "auto_create": True, "app_id": "", "app_secret": "", "sender_id": 0,
            "sender_office_id": 1, "default_weight": 0.1, "cod_processing": "CASH", "package": "PACK",
            # what the waybill declares as contents (owner's decision: never the SKU list)
            "contents_text": "аминокиселини",
            # owner's decision: every parcel may be opened before it is paid for, return on us
            "open_before_pay": True, "obpd_option": "OPEN", "obpd_return_payer": "SENDER"}


def obpd_of(cfg: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """NextLevel `services.obpd` — OPEN = the receiver may open the parcel before paying."""
    if not cfg.get("open_before_pay", True):
        return None
    return {"option": (cfg.get("obpd_option") or "OPEN").upper(),
            "return_shipment_payer": (cfg.get("obpd_return_payer") or "SENDER").upper()}


async def get_config() -> Dict[str, Any]:
    doc = await _db.settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    cfg = {**DEFAULTS, **((doc or {}).get("value") or {})}
    cfg["app_id"] = cfg["app_id"] or os.environ.get("NEXTLEVEL_APP_ID", "")
    cfg["app_secret"] = cfg["app_secret"] or os.environ.get("NEXTLEVEL_APP_SECRET", "")
    return cfg


def _headers(cfg: Dict[str, Any]) -> Dict[str, str]:
    if not cfg.get("app_id") or not cfg.get("app_secret"):
        raise HTTPException(400, "Липсват app-id / app-secret за NextLevel")
    return {"app-id": cfg["app_id"], "app-secret": cfg["app_secret"], "accept": "application/json"}


async def _call(cfg: Dict[str, Any], method: str, path: str, **kw) -> Any:
    r = await _client.request(method, f"{BASE}{path}", headers=_headers(cfg), **kw)
    if "application/pdf" in r.headers.get("content-type", ""):
        return r.content
    try:
        data = r.json()
    except ValueError:
        data = {"error": {"code": r.status_code, "message": r.text[:300]}}
    if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
        msg = (data.get("error") or {}).get("message") if isinstance(data, dict) else str(data)
        raise NextLevelError(f"NextLevel {r.status_code}: {msg or 'грешка'}", r.status_code, data)
    return data


class NextLevelError(Exception):
    def __init__(self, message: str, status: int = 0, data: Any = None):
        super().__init__(message)
        self.status, self.data = status, data


# ---------------------------------------------------------------- payload
def office_id_of(delivery: Dict[str, Any]) -> Optional[int]:
    """NextCart offices are NextLevel offices: "econt:4434" → 4434."""
    office = (delivery or {}).get("office") or {}
    raw = str(office.get("id") or "")
    if ":" in raw and raw.split(":")[-1].isdigit():
        return int(raw.split(":")[-1])
    if office.get("nl_id"):
        return int(office["nl_id"])
    return None


def cod_of(order: Dict[str, Any], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if order.get("payment_method") != "cod":
        return None
    country = ((order.get("shipping") or {}).get("country") or "").upper()
    need = COUNTRY_CURRENCY.get(country, "EUR")
    have = (order.get("currency") or "EUR").upper()
    if need == "EUR":
        amount = float(order.get("total_eur") or 0)
    elif have == need and order.get("total_orig") is not None:
        amount = float(order["total_orig"])
    else:
        raise ValueError(f"Наложеният платеж за {country} трябва да е в {need}, а поръчката е в {have}")
    return {"amount": round(amount, 2), "currency": need, "processing_type": cfg.get("cod_processing", "CASH"),
            "included_shipping_price": False}


def build_payload(order: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Raise ValueError with a human reason when the order cannot be shipped as-is."""
    ship = order.get("shipping") or {}
    delivery = order.get("delivery") or {}
    receiver: Dict[str, Any] = {
        "name": (ship.get("full_name") or order.get("customer_name") or "").strip()[:100],
        "phone": (ship.get("phone") or order.get("customer_phone") or "").strip(),
        "email": (ship.get("email") or order.get("customer_email") or "").strip(),
    }
    if not receiver["name"] or not receiver["phone"]:
        raise ValueError("Липсва име или телефон на получателя")
    office_id = office_id_of(delivery)
    if delivery.get("destination_type") in ("office", "locker") and office_id is None:
        raise ValueError("Офисът/автоматът от чекаута няма NextLevel идентификатор")
    if office_id is not None:
        receiver["office_id"] = office_id
    else:
        country = (ship.get("country") or "").upper()
        if not country or not ship.get("city") or not ship.get("postal_code"):
            raise ValueError("За доставка до адрес NextLevel изисква държава, град и пощенски код")
        receiver.update({"country": country, "place": ship["city"].strip(), "post_code": str(ship["postal_code"]).strip(),
                         "street": (ship.get("line1") or "").strip()[:200] or "-"})
        if ship.get("line2"):
            receiver["other"] = str(ship["line2"])[:200]
    if ship.get("note"):
        receiver["other"] = ((receiver.get("other") or "") + " " + str(ship["note"])).strip()[:200]

    items = order.get("items") or []
    # the waybill declares a neutral content, never the SKU list (owner's decision)
    contents = (cfg.get("contents_text") or DEFAULTS["contents_text"])[:200]
    payload: Dict[str, Any] = {
        "sender": {"id": int(cfg["sender_id"]), "office_id": int(cfg.get("sender_office_id") or 1)},
        "receiver": receiver,
        "content": {"parcels_count": 1, "weight": float(cfg.get("default_weight") or 0.1),
                    "package": cfg.get("package") or "PACK", "contents": contents},
        "payment": {"payer": "sender"},
        "ref": str(order.get("order_number") or ""),
        "ref2": str(order.get("id") or "")[:60],
    }
    cod = cod_of(order, cfg)
    services: Dict[str, Any] = {}
    if cod:
        services["cod"] = cod
    obpd = obpd_of(cfg)
    if obpd and cod:  # opening before payment only makes sense when the receiver still has to pay
        services["obpd"] = obpd
    if services:
        payload["services"] = services
    return payload


TRACKING_URLS = {
    "Econt": "https://www.econt.com/services/track-shipment/{awb}",
    "Speedy": "https://www.speedy.bg/bg/track-shipment?shipmentNumber={awb}",
    "BoxNow": "https://boxnow.bg/tracking?parcelId={awb}",
    "Sameday": "https://sameday.bg/#awb={awb}",
    "FAN": "https://www.fancourier.ro/awb-tracking/?xawb={awb}",
    "GLS": "https://gls-group.eu/track/{awb}",
    "ACS": "https://www.acscourier.net/el/track-and-trace/?generalCode={awb}",
    "Speedex": "https://www.speedex.gr/isapohi.asp?voucher_code={awb}",
    "Geniki": "https://www.taxydromiki.com/track/{awb}",
}


def tracking_url_for(courier: Optional[str], courier_awb: Optional[str], awb: str) -> str:
    """NextLevel has no public tracking page; the courier's one works with the courier's own number."""
    tpl = TRACKING_URLS.get(courier or "")
    if tpl and courier_awb:
        return tpl.format(awb=courier_awb)
    return ""


# per-courier sanity checks: a NextLevel internal awb starts with 1 and gets rejected by the
# courier's own site, so a number in that shape is not a tracking number we may show
COURIER_NUMBER_RULES = {
    "BoxNow": lambda n: not n.startswith("1"),        # BoxNow parcel ids never start with 1
}


def is_courier_number(courier: Optional[str], number: str, internal_awb: str = "") -> bool:
    """Is this really the courier's own number, or NextLevel's internal id in disguise?"""
    num = (number or "").strip()
    if not num or num == (internal_awb or "").strip():
        return False
    rule = COURIER_NUMBER_RULES.get(courier or "")
    return rule(num) if rule else True


def customer_tracking(shipment: Dict[str, Any]) -> Dict[str, Any]:
    """What the customer is given: the courier's own number and the courier's tracking page.

    `awb` is NextLevel's internal id — useless to a customer and unsearchable on any courier site,
    so it never leaves the admin. Until the courier number arrives the tracking block stays empty.
    """
    courier_awb = str(shipment.get("courier_awb") or "").strip()
    courier = shipment.get("courier") or ""
    if not is_courier_number(courier, courier_awb, str(shipment.get("awb") or "")):
        courier_awb = ""                              # nothing to show yet
    return {"tracking_number": courier_awb,
            "tracking_url": tracking_url_for(courier, courier_awb, shipment.get("awb", "")),
            "carrier": courier or "NextLevel",
            "ready": bool(courier_awb)}


def _summary(res: Dict[str, Any]) -> Dict[str, Any]:
    price = res.get("price") if isinstance(res.get("price"), dict) else {}
    courier = res.get("subcontractor") or res.get("courier")
    awb = str(res.get("awb") or res.get("id") or "")
    return {
        "awb": awb,
        "courier_awb": res.get("courier_awb"),
        "courier": courier,
        "status": res.get("status"),
        "status_id": res.get("status_id"),
        "cod_status": res.get("cod_status"),
        "tracking_link": tracking_url_for(courier, res.get("courier_awb"), awb),
        "total_price": res.get("total_price") or price.get("total_price"),
        "base_price": res.get("base_price") or price.get("base_price"),
        "cod_native": price.get("native_cod"),
        "currency": res.get("currency"),
        "created_at": _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------------- operations
async def create_shipment(order_id: str, force: bool = False) -> Dict[str, Any]:
    cfg = await get_config()
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Поръчката не е намерена")
    if order.get("shipment", {}).get("awb") and not force:
        raise HTTPException(409, f"Вече има товарителница {order['shipment']['awb']}")
    try:
        payload = build_payload(order, cfg)
    except ValueError as ex:
        await _db.orders.update_one({"id": order_id}, {"$set": {"shipment_error": str(ex), "shipment_error_at": _now()}})
        raise HTTPException(422, str(ex))
    try:
        res = await _call(cfg, "POST", "/shipments", json=payload)
    except NextLevelError as ex:
        await _db.orders.update_one({"id": order_id}, {"$set": {"shipment_error": str(ex), "shipment_error_at": _now()}})
        raise HTTPException(502, str(ex))
    shipment = {**_summary(res), "payload": payload}
    tracking = customer_tracking(shipment)
    await _db.orders.update_one({"id": order_id}, {
        "$set": {"shipment": shipment, "tracking": tracking,
                 "tracking_number": tracking["tracking_number"]},
        "$unset": {"shipment_error": "", "shipment_error_at": ""}})
    log.info("NextLevel shipment %s for order %s (%s)", shipment["awb"], order.get("order_number"), shipment.get("courier"))
    # the courier number often lands a few minutes later; the sync loop mails the customer as soon
    # as it does, so nobody receives a number no courier can find
    if order.get("customer_email") and order.get("source") != "nextlevel-selftest" and tracking["ready"]:
        asyncio.create_task(_notify_customer({**order, "shipment": shipment}))
    return shipment


async def _notify_once(order_id: str) -> None:
    """Send the shipment mail the first time the courier number exists, and only then."""
    order = await _db.orders.find_one(
        {"id": order_id, "shipment.customer_notified_at": {"$exists": False},
         "customer_email": {"$nin": ["", None]}, "source": {"$ne": "nextlevel-selftest"}},
        {"_id": 0})
    if order:
        await _notify_customer(order)


async def _notify_customer(order: Dict[str, Any]) -> None:
    """The customer gets the waybill the moment we have it: email + the tracking block on the order page."""
    import email_service

    try:
        s = await _db.settings.find_one({"key": "site"}, {"_id": 0})
        res = await email_service.send_shipment_created(order, (s or {}).get("value") or {})
        await _db.orders.update_one({"id": order["id"]}, {"$set": {"shipment.customer_notified_at": _now(),
                                                                    "shipment.customer_email_id": (res or {}).get("id")}})
    except Exception as ex:
        log.warning("Shipment email for %s failed: %s", order.get("order_number"), ex)


async def cancel_shipment(order_id: str) -> Dict[str, Any]:
    cfg = await get_config()
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0, "shipment": 1})
    awb = (order or {}).get("shipment", {}).get("awb")
    if not awb:
        raise HTTPException(404, "Няма товарителница")
    try:
        res = await _call(cfg, "POST", f"/shipments/{awb}/cancel")
    except NextLevelError as ex:
        raise HTTPException(502, str(ex))
    await _db.orders.update_one({"id": order_id}, {
        "$set": {"shipment.status": "Cancelled", "shipment.cancelled_at": _now(), "shipment.updated_at": _now()},
        "$unset": {"tracking": "", "tracking_number": ""}})
    return {"cancelled": True, "awb": awb, "response": res}


async def label_pdf(order_id: str) -> bytes:
    cfg = await get_config()
    order = await _db.orders.find_one({"id": order_id}, {"_id": 0, "shipment": 1})
    awb = (order or {}).get("shipment", {}).get("awb")
    if not awb:
        raise HTTPException(404, "Няма товарителница")
    try:
        data = await _call(cfg, "POST", f"/shipments/{awb}/print")
    except NextLevelError as ex:
        raise HTTPException(502, str(ex))
    if not isinstance(data, (bytes, bytearray)):
        raise HTTPException(502, "NextLevel не върна PDF")
    return bytes(data)


async def track(awbs: List[str]) -> List[Dict[str, Any]]:
    cfg = await get_config()
    if not awbs:
        return []
    data = await _call(cfg, "POST", "/shipments/track", json={"ids": awbs})
    return data if isinstance(data, list) else data.get("shipments", data.get("data", []))


async def sync_open_shipments() -> Dict[str, Any]:
    cursor = _db.orders.find({"shipment.awb": {"$exists": True},
                              "shipment.status": {"$nin": list(OPEN_STATUSES_DONE)}}, {"_id": 0, "id": 1, "shipment.awb": 1})
    orders = await cursor.to_list(500)
    by_awb = {o["shipment"]["awb"]: o["id"] for o in orders}
    updated = 0
    for i in range(0, len(by_awb), 50):
        chunk = list(by_awb)[i:i + 50]
        try:
            rows = await track(chunk)
        except Exception as ex:
            log.warning("NextLevel track failed: %s", ex)
            continue
        for row in rows:
            awb = str(row.get("awb") or "")
            if awb not in by_awb:
                continue
            courier = row.get("subcontractor") or None
            shipment = {"awb": awb, "courier": courier, "courier_awb": row.get("courier_awb")}
            tracking = customer_tracking(shipment)
            await _db.orders.update_one({"id": by_awb[awb]}, {"$set": {
                "shipment.status": row.get("status"), "shipment.status_id": row.get("status_id"),
                "shipment.courier": courier, "shipment.courier_awb": row.get("courier_awb"),
                "shipment.tracking_link": tracking["tracking_url"],
                "shipment.last_movement": row.get("last_movement"), "shipment.updated_at": _now(),
                "tracking": tracking, "tracking_number": tracking["tracking_number"]}})
            updated += 1
            if tracking["ready"]:
                await _notify_once(by_awb[awb])
            if str(row.get("status") or "").lower() == "delivered":
                await notify_delivered(by_awb[awb])
    return {"open": len(by_awb), "updated": updated}


async def refresh_all_tracking() -> Dict[str, Any]:
    """Re-read every NextLevel shipment and rewrite the customer's number and link.

    For orders created before the customer number was split from NextLevel's internal awb: it asks
    NextLevel for the courier's own waybill and stores that instead.
    """
    cursor = _db.orders.find({"shipment.awb": {"$nin": ["", None]}},
                             {"_id": 0, "id": 1, "shipment": 1, "tracking_number": 1})
    orders = await cursor.to_list(5000)
    by_awb = {str(o["shipment"]["awb"]): o for o in orders if o.get("shipment", {}).get("awb")}
    fixed, still_missing, failed = 0, 0, 0

    # warehouse (fulfillment) shipments already carry the courier's own waybill — no API call needed
    for o in [x for x in orders if (x.get("shipment") or {}).get("source") == "fulfillment"]:
        sh = o["shipment"]
        tracking = customer_tracking({"awb": sh["awb"], "courier": sh.get("courier"),
                                      "courier_awb": sh.get("courier_awb") or sh["awb"]})
        tracking["tracking_url"] = tracking["tracking_url"] or (sh.get("tracking_link") or "")
        await _db.orders.update_one({"id": o["id"]}, {"$set": {
            "shipment.courier_awb": sh.get("courier_awb") or sh["awb"],
            "shipment.tracking_link": tracking["tracking_url"],
            "tracking": tracking, "tracking_number": tracking["tracking_number"]}})
        by_awb.pop(str(sh["awb"]), None)
        fixed, still_missing = (fixed + 1, still_missing) if tracking["ready"] else (fixed, still_missing + 1)

    awbs = list(by_awb)
    for i in range(0, len(awbs), 50):
        try:
            rows = await track(awbs[i:i + 50])
        except Exception as ex:
            log.warning("NextLevel track failed while refreshing: %s", ex)
            failed += len(awbs[i:i + 50])
            continue
        for row in rows:
            awb = str(row.get("awb") or "")
            order = by_awb.get(awb)
            if not order:
                continue
            courier = row.get("subcontractor") or row.get("courier") or order["shipment"].get("courier")
            shipment = {"awb": awb, "courier": courier, "courier_awb": row.get("courier_awb")}
            tracking = customer_tracking(shipment)
            await _db.orders.update_one({"id": order["id"]}, {"$set": {
                "shipment.courier": courier, "shipment.courier_awb": row.get("courier_awb"),
                "shipment.tracking_link": tracking["tracking_url"],
                "shipment.updated_at": _now(),
                "tracking": tracking, "tracking_number": tracking["tracking_number"]}})
            if tracking["ready"]:
                fixed += 1
            else:
                still_missing += 1
    return {"orders": len(by_awb), "with_courier_number": fixed,
            "waiting_for_courier_number": still_missing, "unreachable": failed}


async def notify_delivered(order_id: str) -> None:
    """One thank-you email per order when the courier confirms delivery."""
    import email_service

    order = await _db.orders.find_one({"id": order_id, "shipment.delivered_notified_at": {"$exists": False}}, {"_id": 0})
    if not order or not order.get("customer_email") or order.get("source") == "nextlevel-selftest":
        return
    await _db.orders.update_one({"id": order_id}, {"$set": {"shipment.delivered_notified_at": _now(), "fulfillment_status": "fulfilled",
                                                            "shipment.delivered_at": _now()}})
    try:
        s = await _db.settings.find_one({"key": "site"}, {"_id": 0})
        await email_service.send_delivered(order, (s or {}).get("value") or {})
    except Exception as ex:
        log.warning("Delivered email for %s failed: %s", order.get("order_number"), ex)


async def sync_loop():
    while True:
        try:
            cfg = await get_config()
            if cfg.get("enabled"):
                await sync_open_shipments()
        except Exception as ex:
            log.warning("NextLevel sync loop: %s", ex)
        await asyncio.sleep(SYNC_SEC)


async def auto_create(order_id: str):
    """Fire-and-forget after checkout; failures land on the order for the admin to see."""
    try:
        cfg = await get_config()
        if not cfg.get("enabled") or not cfg.get("auto_create"):
            return
        await create_shipment(order_id)
    except HTTPException as ex:
        log.warning("NextLevel auto-create for %s failed: %s", order_id, ex.detail)
    except Exception:
        log.exception("NextLevel auto-create for %s crashed", order_id)


# ---------------------------------------------------------------- admin API
class ConfigIn(BaseModel):
    enabled: Optional[bool] = None
    auto_create: Optional[bool] = None
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    sender_id: Optional[int] = None
    sender_office_id: Optional[int] = None
    default_weight: Optional[float] = None
    cod_processing: Optional[str] = None
    contents_text: Optional[str] = None


def _masked(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    out["app_secret"] = ("•" * 8 + cfg["app_secret"][-4:]) if cfg.get("app_secret") else ""
    out["has_keys"] = bool(cfg.get("app_id") and cfg.get("app_secret"))
    return out


def init(db_, admin_guard) -> APIRouter:
    global _db
    _db = db_
    router = APIRouter()

    @router.get("/admin/integrations/nextlevel")
    async def read(admin=Depends(admin_guard)):
        return _masked(await get_config())

    @router.put("/admin/integrations/nextlevel")
    async def update(payload: ConfigIn, admin=Depends(admin_guard)):
        patch = {k: v for k, v in payload.model_dump().items() if v is not None}
        if "app_secret" in patch and patch["app_secret"].startswith("•"):
            patch.pop("app_secret")
        if "contents_text" in patch:
            patch["contents_text"] = patch["contents_text"].strip()[:200] or DEFAULTS["contents_text"]
        await _db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {f"value.{k}": v for k, v in patch.items()}}, upsert=True)
        return _masked(await get_config())

    @router.post("/admin/integrations/nextlevel/test")
    async def test(admin=Depends(admin_guard)):
        cfg = await get_config()
        try:
            countries = await _call(cfg, "GET", "/countries")
            probe = {"sender": {"id": int(cfg["sender_id"]), "office_id": int(cfg.get("sender_office_id") or 1)},
                     "receiver": {"country": "BG", "place": "София", "post_code": "1000", "street": "бул. Витоша", "street_no": "1"},
                     "weight": float(cfg.get("default_weight") or 0.1)}
            price = await _call(cfg, "POST", "/shipments/calculate", json=probe)
            recent = await _call(cfg, "GET", "/shipments", params={"limit": 3})
        except NextLevelError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "countries": len(countries), "sample_price_bg": price.get("total"),
                "sender_seen": (recent[0].get("sender") or {}).get("name") if recent else None,
                "recent": [{"awb": (s.get("parcels") or [""])[0], "status": s.get("status"), "courier": s.get("subcontractor"),
                            "ref": s.get("ref")} for s in recent[:3]]}

    @router.get("/admin/integrations/nextlevel/preview/{order_id}")
    async def preview(order_id: str, admin=Depends(admin_guard)):
        cfg = await get_config()
        order = await _db.orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Поръчката не е намерена")
        try:
            payload = build_payload(order, cfg)
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}
        try:
            price = await _call(cfg, "POST", "/shipments/calculate", json={
                "sender": payload["sender"], "receiver": payload["receiver"], "weight": payload["content"]["weight"],
                **({"services": payload["services"]} if payload.get("services") else {})})
        except NextLevelError as ex:
            return {"ok": False, "error": str(ex), "payload": payload}
        return {"ok": True, "payload": payload, "price": price}

    @router.post("/admin/orders/{order_id}/shipment")
    async def create(order_id: str, force: bool = False, admin=Depends(admin_guard)):
        return await create_shipment(order_id, force=force)

    @router.delete("/admin/orders/{order_id}/shipment")
    async def cancel(order_id: str, admin=Depends(admin_guard)):
        return await cancel_shipment(order_id)

    @router.get("/admin/orders/{order_id}/shipment/label")
    async def label(order_id: str, admin=Depends(admin_guard)):
        pdf = await label_pdf(order_id)
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="label-{order_id[:8]}.pdf"'})

    @router.post("/admin/shipments/sync")
    async def sync(admin=Depends(admin_guard)):
        return await sync_open_shipments()

    @router.post("/admin/shipments/refresh-tracking")
    async def refresh_tracking(admin=Depends(admin_guard)):
        return await refresh_all_tracking()

    return router
