"""Abandoned cart capture + recovery emails.

The checkout modal posts a cart snapshot as soon as a valid email is typed. A background
sweeper sends one recovery email per cart after ABANDONED_DELAY_MIN minutes, unless the
customer has meanwhile placed an order.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

import currency
import email_service
import email_templates
import bank as bank_details

log = logging.getLogger("purepeptide.abandoned")

router = APIRouter(tags=["abandoned-carts"])
DELAY_MIN = int(os.environ.get("ABANDONED_DELAY_MIN", "60"))
SWEEP_SEC = int(os.environ.get("ABANDONED_SWEEP_SEC", "600"))

_db = None
_admin_dep = None


class CartLineIn(BaseModel):
    product_id: str = ""
    variant_sku: str = ""
    title: str = ""
    variant_name: str = ""
    image: str = ""
    price_eur: float = 0.0
    quantity: int = Field(default=1, ge=1)


class CartTrackIn(BaseModel):
    email: EmailStr
    customer_name: str = ""
    phone: str = ""
    locale: str = "bg"
    items: List[CartLineIn]


async def _admin_guard(request: Request):
    return await _admin_dep(request)


def init(db, admin_dependency) -> APIRouter:
    global _db, _admin_dep
    _db = db
    _admin_dep = admin_dependency
    return router


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _site_settings() -> Dict[str, Any]:
    doc = await _db.settings.find_one({"key": "site"}, {"_id": 0})
    return (doc or {}).get("value") or {}


@router.post("/cart/track")
async def track_cart(payload: CartTrackIn):
    """Upsert the visitor's cart snapshot — one open record per email."""
    if not payload.items:
        raise HTTPException(400, "Количката е празна")
    items = [i.model_dump() for i in payload.items]
    subtotal = round(sum(i["price_eur"] * i["quantity"] for i in items), 2)
    email = payload.email.lower()
    now = _now()
    existing = await _db.abandoned_carts.find_one({"email": email, "status": "open"}, {"_id": 0})
    doc = {
        "email": email,
        "customer_name": payload.customer_name,
        "phone": payload.phone,
        "locale": (payload.locale or "bg").lower(),
        "items": items,
        "subtotal_eur": subtotal,
        "status": "open",
        "updated_at": now,
    }
    if existing:
        await _db.abandoned_carts.update_one({"id": existing["id"]}, {"$set": doc})
        return {"ok": True, "id": existing["id"]}
    doc.update({"id": str(uuid.uuid4()), "created_at": now, "reminded_at": None})
    await _db.abandoned_carts.insert_one(doc.copy())
    return {"ok": True, "id": doc["id"]}


async def mark_recovered(email: str) -> None:
    """Called after a successful checkout so no reminder is sent."""
    if not email:
        return
    await _db.abandoned_carts.update_many(
        {"email": email.lower(), "status": "open"},
        {"$set": {"status": "recovered", "updated_at": _now()}},
    )


async def send_reminder(cart: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    settings = settings if settings is not None else await _site_settings()
    code = (settings.get("abandoned_discount_code") or "").strip()
    fx = await currency.rate_for_locale(_db, cart.get("locale"))
    res = await email_service.send_abandoned_cart(cart, settings, code, fx)
    await _db.abandoned_carts.update_one(
        {"id": cart["id"]},
        {"$set": {"status": "reminded" if res.get("sent") else "open",
                  "reminded_at": _now() if res.get("sent") else None,
                  "last_error": None if res.get("sent") else res.get("reason", "")}},
    )
    return res


async def sweep() -> int:
    """Send reminders for carts idle longer than the delay. Returns the number sent."""
    cutoff = _now() - timedelta(minutes=DELAY_MIN)
    carts = await _db.abandoned_carts.find(
        {"status": "open", "updated_at": {"$lte": cutoff}}, {"_id": 0}
    ).to_list(50)
    if not carts:
        return 0
    settings = await _site_settings()
    sent = 0
    for cart in carts:
        if await _db.orders.find_one({"customer_email": cart["email"],
                                      "created_at": {"$gte": cart["created_at"].isoformat()
                                                     if hasattr(cart["created_at"], "isoformat")
                                                     else cart["created_at"]}}):
            await _db.abandoned_carts.update_one({"id": cart["id"]}, {"$set": {"status": "recovered"}})
            continue
        res = await send_reminder(cart, settings)
        sent += 1 if res.get("sent") else 0
    return sent


async def sweeper_loop() -> None:
    while True:
        try:
            await asyncio.sleep(SWEEP_SEC)
            count = await sweep()
            if count:
                log.info("Abandoned cart reminders sent: %s", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Abandoned cart sweep failed")


# ---------- admin ----------
@router.get("/admin/abandoned-carts")
async def list_carts(admin=Depends(_admin_guard)):
    carts = await _db.abandoned_carts.find({}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return {"carts": carts, "delay_minutes": DELAY_MIN}


@router.post("/admin/abandoned-carts/{cart_id}/send")
async def send_now(cart_id: str, admin=Depends(_admin_guard)):
    cart = await _db.abandoned_carts.find_one({"id": cart_id}, {"_id": 0})
    if not cart:
        raise HTTPException(404, "Количката не е намерена")
    return await send_reminder(cart)


@router.post("/admin/abandoned-carts/sweep")
async def sweep_now(admin=Depends(_admin_guard)):
    return {"sent": await sweep()}


@router.post("/admin/emails/test")
async def send_test_email(payload: Dict[str, Any] = Body(...), admin=Depends(_admin_guard)):
    """Send either template to any address so the shop owner can review the design."""
    to = (payload.get("to") or "").strip()
    kind = payload.get("kind") or "order"
    locale = (payload.get("locale") or "bg").lower()
    if not to:
        raise HTTPException(400, "Липсва имейл получател")
    settings = await _site_settings()
    fx = await currency.rate_for_locale(_db, locale)
    if kind == "abandoned":
        cart = await _db.abandoned_carts.find_one({}, {"_id": 0}, sort=[("updated_at", -1)])
        if not cart:
            order = await _db.orders.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
            if not order:
                raise HTTPException(400, "Няма данни за примерен имейл")
            cart = {"id": "preview", "email": to, "customer_name": order.get("customer_name", ""),
                    "items": order.get("items", []), "locale": locale}
        cart = {**cart, "email": to, "locale": locale}
        return await email_service.send_abandoned_cart(
            cart, settings, (settings.get("abandoned_discount_code") or "").strip(), fx)
    order = await _db.orders.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if not order:
        raise HTTPException(400, "Няма поръчки за примерен имейл")
    # the preview speaks the chosen storefront's currency, whatever the sample order was placed in
    order = email_templates.localize_order({**order, "customer_email": to, "locale": locale}, fx)
    bank = bank_details.from_settings(settings, order.get("order_number", ""))
    return await email_service.send_order_confirmation(order, bank, settings)
