"""RevOrder (NextCart) server-to-server integration — separate credentials per storefront domain.

Each domain (purepeptide.bg, purepeptide.eu, purepeptide.ro, …) has its own api_key, secret_key and
webhook. Orders are pushed to RevOrder signed with HMAC-SHA256; RevOrder calls us back on
/api/webhooks/revorder/{domain} with the same signature scheme.

NOTE: the exact RevOrder endpoint/payload contract is not published — endpoint path and field names are
configurable per domain so they can be aligned once the merchant receives their API credentials.
"""
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request

log = logging.getLogger("purepeptide.revorder")

router = APIRouter(tags=["revorder"])
SETTINGS_KEY = "integrations.revorder"
DEFAULT_BASE = os.environ["NEXTCART_BASE_URL"]
DEFAULT_ORDERS_PATH = "/api/orders"
# one backend serves every storefront domain, so the callback always lands on the live API host
WEBHOOK_BASE = (os.environ.get("PUBLIC_SITE_URL") or "").strip().strip('"').rstrip("/")

_db = None
_admin_dep = None
_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=4.0, read=12.0, write=12.0, pool=4.0))


async def _admin_guard(request: Request):
    return await _admin_dep(request)


def init(db, admin_dependency) -> APIRouter:
    """Wire the router to the app's Mongo handle and admin auth dependency."""
    global _db, _admin_dep
    _db = db
    _admin_dep = admin_dependency
    return router


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _all_domains() -> Dict[str, Dict[str, Any]]:
    doc = await _db.settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    return ((doc or {}).get("value") or {}).get("domains") or {}


DOMAIN_ALIASES = {"purepeptide-labs.bg": "purepeptide.bg"}


def webhook_url(domain: str) -> str:
    """The address the merchant pastes into RevOrder so it can call us back.

    In production PUBLIC_SITE_URL is empty (each locale lives on its own domain), so the callback
    goes to the domain itself; the preview/staging host sets it and wins.
    """
    base = WEBHOOK_BASE or f"https://{domain}"
    return f"{base}/api/webhooks/revorder/{domain}"


def aliases_of(domain: str) -> List[str]:
    return [a for a, target in DOMAIN_ALIASES.items() if target == domain]


def _new_credentials() -> Dict[str, str]:
    """We issue the pair ourselves — the merchant copies it into the RevOrder dashboard."""
    return {"api_key": f"pp_live_{secrets.token_hex(16)}", "secret_key": secrets.token_hex(32)}


async def domain_config(domain: str) -> Optional[Dict[str, Any]]:
    domain = DOMAIN_ALIASES.get(domain, domain)
    cfg = (await _all_domains()).get(domain)
    if cfg and cfg.get("enabled") and cfg.get("api_key") and cfg.get("secret_key"):
        return cfg
    return None


async def push_order(order: Dict[str, Any], domain: str) -> Dict[str, Any]:
    """Send an order to RevOrder for the given storefront domain. Never raises."""
    cfg = await domain_config(domain)
    if not cfg:
        return {"sent": False, "reason": "not_configured"}
    payload = {
        "order_number": order.get("order_number"),
        "external_id": order.get("id"),
        "domain": domain,
        "currency": order.get("currency") or "EUR",
        "total": order.get("total_eur"),
        "shipping_total": order.get("shipping_eur"),
        "discount_total": order.get("discount_eur"),
        "customer": {
            "name": order.get("customer_name"),
            "email": order.get("customer_email"),
            "phone": order.get("customer_phone"),
        },
        "delivery": order.get("delivery"),
        "shipping_address": order.get("shipping"),
        "line_items": [
            {"sku": li.get("variant_sku"), "title": li.get("title"), "quantity": li.get("quantity"),
             "price": li.get("price_eur")}
            for li in (order.get("line_items") or order.get("items") or [])
        ],
        "payment_method": order.get("payment_method"),
        "created_at": order.get("created_at"),
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    url = (cfg.get("api_base") or DEFAULT_BASE).rstrip("/") + (cfg.get("orders_path") or "/api/orders")
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": cfg["api_key"],
        "X-Signature": f"sha256={sign(cfg['secret_key'], body)}",
        "X-Shop-Domain": domain,
    }
    event = {"domain": domain, "direction": "outbound", "order_id": order.get("id"),
             "order_number": order.get("order_number"), "url": url, "created_at": _now()}
    try:
        r = await _client.post(url, content=body, headers=headers)
        event.update({"status_code": r.status_code, "ok": r.is_success, "response": r.text[:600]})
        result = {"sent": r.is_success, "status": r.status_code, "response": r.text[:400]}
    except Exception as ex:
        event.update({"status_code": 0, "ok": False, "response": str(ex)[:600]})
        result = {"sent": False, "reason": str(ex)[:200]}
    await _db.integration_events.insert_one(event)
    return result


# ---------- admin management ----------
def _mask(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "•" * max(len(value) - 8, 4) + value[-4:]


@router.get("/admin/integrations/revorder")
async def get_revorder_settings(admin=Depends(_admin_guard)):
    """Every storefront domain, keys masked — the full values come from /reveal or /generate."""
    domains = await _all_domains()
    out = {}
    for d in list(dict.fromkeys(ALL_DOMAINS_HINT + list(domains))):
        c = domains.get(d) or {}
        out[d] = {
            "enabled": bool(c.get("enabled")),
            "api_base": c.get("api_base") or DEFAULT_BASE,
            "orders_path": c.get("orders_path") or DEFAULT_ORDERS_PATH,
            "webhook_url": webhook_url(d),
            "aliases": {a: webhook_url(a) for a in aliases_of(d)},
            "api_key": _mask(c.get("api_key", "")),
            "secret_key": _mask(c.get("secret_key", "")),
            "has_keys": bool(c.get("api_key") and c.get("secret_key")),
            "updated_at": c.get("updated_at") or "",
        }
    events = await _db.integration_events.find({}, {"_id": 0}).sort("created_at", -1).to_list(30)
    return {"domains": out, "events": events}


async def _store(domain: str, cfg: Dict[str, Any]) -> None:
    domains = await _all_domains()
    domains[domain] = cfg
    await _db.settings.update_one(
        {"key": SETTINGS_KEY},
        {"$set": {"value": {"domains": domains}, "updated_at": _now()}},
        upsert=True,
    )


@router.post("/admin/integrations/revorder/generate")
async def generate_revorder_keys(payload: Dict[str, Any] = Body(...), admin=Depends(_admin_guard)):
    """Issue a fresh api_key + secret_key for one domain and return them in full, once."""
    domain = (payload.get("domain") or "").strip().lower()
    if not domain:
        raise HTTPException(400, "Липсва домейн")
    cfg = (await _all_domains()).get(domain) or {}
    cfg.update(_new_credentials())
    cfg["api_base"] = cfg.get("api_base") or DEFAULT_BASE
    cfg["orders_path"] = cfg.get("orders_path") or DEFAULT_ORDERS_PATH
    cfg["webhook_url"] = webhook_url(domain)
    cfg["updated_at"] = _now()
    await _store(domain, cfg)
    return {"domain": domain, "api_key": cfg["api_key"], "secret_key": cfg["secret_key"],
            "webhook_url": cfg["webhook_url"], "enabled": bool(cfg.get("enabled"))}


@router.get("/admin/integrations/revorder/reveal")
async def reveal_revorder_keys(domain: str, admin=Depends(_admin_guard)):
    """Unmasked keys for copy-paste into RevOrder — admin session only."""
    cfg = (await _all_domains()).get((domain or "").strip().lower())
    if not cfg or not cfg.get("api_key"):
        raise HTTPException(404, "Няма генерирани ключове за този домейн")
    return {"domain": domain, "api_key": cfg["api_key"], "secret_key": cfg.get("secret_key", ""),
            "webhook_url": webhook_url(domain)}


@router.put("/admin/integrations/revorder")
async def save_revorder_settings(payload: Dict[str, Any] = Body(...), admin=Depends(_admin_guard)):
    """Save credentials for one domain. Empty key fields keep the stored value."""
    domain = (payload.get("domain") or "").strip().lower()
    if not domain:
        raise HTTPException(400, "Липсва домейн")
    domains = await _all_domains()
    current = domains.get(domain, {})
    for field in ("api_key", "secret_key"):
        value = (payload.get(field) or "").strip()
        if value and "•" not in value:
            current[field] = value
    current["api_base"] = (payload.get("api_base") or current.get("api_base") or DEFAULT_BASE).strip()
    current["orders_path"] = (payload.get("orders_path") or current.get("orders_path")
                              or DEFAULT_ORDERS_PATH).strip()
    current["webhook_url"] = webhook_url(domain)
    current["enabled"] = bool(payload.get("enabled"))
    current["updated_at"] = _now()
    await _store(domain, current)
    return {"ok": True, "domain": domain, "webhook_url": current["webhook_url"],
            "has_keys": bool(current.get("api_key") and current.get("secret_key"))}


@router.post("/admin/integrations/revorder/test")
async def test_revorder(payload: Dict[str, Any] = Body(...), admin=Depends(_admin_guard)):
    domain = (payload.get("domain") or "").strip().lower()
    cfg = await domain_config(domain)
    if not cfg:
        raise HTTPException(400, "Домейнът не е конфигуриран или е изключен")
    probe = {"id": "test", "order_number": "TEST-0000", "total_eur": 0, "shipping_eur": 0,
             "customer_name": "Test", "customer_email": "test@example.com", "line_items": [],
             "created_at": _now()}
    return await push_order(probe, domain)


# ---------- inbound webhook ----------
@router.post("/webhooks/revorder/{domain}")
async def revorder_webhook(domain: str, request: Request):
    """Shipment/status callbacks from RevOrder — HMAC verified, idempotent per event id."""
    cfg = await domain_config(domain)
    if not cfg:
        raise HTTPException(404, "Unknown domain")
    raw = await request.body()
    provided = (request.headers.get("x-signature") or "").replace("sha256=", "")
    expected = sign(cfg["secret_key"], raw)
    if not provided or not hmac.compare_digest(provided, expected):
        log.warning("RevOrder webhook signature mismatch for %s", domain)
        raise HTTPException(401, "Invalid signature")
    try:
        event = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Invalid JSON")

    event_id = str(event.get("id") or event.get("event_id") or "")
    if event_id and await _db.integration_events.find_one({"event_id": event_id, "direction": "inbound"}):
        return {"ok": True, "duplicate": True}

    updates: Dict[str, Any] = {}
    if event.get("tracking_number"):
        updates["tracking_number"] = event["tracking_number"]
    if event.get("courier"):
        updates["tracking_courier"] = event["courier"]
    status = event.get("status") or event.get("fulfillment_status")
    if status:
        updates["fulfillment_status"] = status
    if event.get("payment_status"):
        updates["payment_status"] = event["payment_status"]

    matched = 0
    ref = event.get("external_id") or event.get("order_number")
    if ref and updates:
        updates["updated_at"] = _now()
        res = await _db.orders.update_one({"$or": [{"id": ref}, {"order_number": ref}]}, {"$set": updates})
        matched = res.matched_count

    await _db.integration_events.insert_one({
        "domain": domain, "direction": "inbound", "event_id": event_id,
        "event_name": event.get("event") or event.get("type") or "update",
        "order_ref": ref, "applied": updates, "matched": matched,
        "payload": json.dumps(event, ensure_ascii=False)[:1500], "created_at": _now(),
    })
    return {"ok": True, "matched": matched}


ALL_DOMAINS_HINT: List[str] = [
    "purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr",
]
