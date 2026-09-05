"""WooCommerce-compatible REST façade for the NextLevel Fulfillment "WooCommerce shop" integration.

NextLevel's shop of type WooCommerce reads/writes orders through the WooCommerce REST API
(consumer key + secret, Basic auth) and receives `order.created` webhooks. We speak exactly that dialect:
  GET  /wp-json/wc/v3/orders[?status=processing&after=…]      GET /orders/{id}
  PUT  /wp-json/wc/v3/orders/{id}   (status / meta_data with the waybill)   POST /orders/{id}/notes
  GET  /wp-json/wc/v3/products[/{id}[/variations[/{vid}]]]     PUT stock_quantity → our inventory
Mounted at /wp-json/wc/v3 (production nginx) and /api/wc/wp-json/wc/v3 (preview ingress).
Every call is logged into `wc_api_log` so the admin can see what the warehouse does.
"""
import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import uuid
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

import email_templates

log = logging.getLogger("purepeptide.wc_api")
_db = None
_client = httpx.AsyncClient(timeout=30)
AWB_RE = re.compile(r"\b(\d{10,16})\b")
TRACKING_KEYS = ("awb", "tracking", "waybill", "nextlevel", "shipment", "товарителница")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def wc_int(value: str) -> int:
    return zlib.crc32(str(value).encode()) & 0x7FFFFFFF


def gen_keys() -> Dict[str, str]:
    return {"wc_consumer_key": "ck_" + secrets.token_hex(20), "wc_consumer_secret": "cs_" + secrets.token_hex(20)}


# ---------------------------------------------------------------- order mapping
def wc_status(order: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    if order.get("status") == "cancelled":
        return "cancelled"
    # everything before the integration went live (incl. the Shopify history) is closed for the warehouse
    if order.get("source") == "shopify_import" or str(order.get("created_at") or "") < str(cfg.get("wc_since") or ""):
        return "completed"
    if order.get("payment_status") == "refunded":
        return "refunded"
    if (order.get("fulfillment_status") or "") in ("shipped", "fulfilled"):
        return "completed"
    if order.get("payment_method") == "cod" or order.get("payment_status") == "paid":
        return "processing"
    return "processing" if cfg.get("bank_transfer_when") == "immediately" else "on-hold"


def _split_name(full: str):
    parts = (full or "").strip().split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _money(v: Any) -> str:
    return f"{float(v or 0):.2f}"


def _local(order: Dict[str, Any], key: str) -> float:
    v = order.get(f"{key}_orig")
    return float(v if v is not None else (order.get(f"{key}_eur") or 0))


def _date(v: Any) -> str:
    s = str(v or _now_iso())[:19]
    return s.replace(" ", "T")


def to_wc_order(order: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    ship = order.get("shipping") or {}
    delivery = order.get("delivery") or {}
    office = delivery.get("office") or {}
    first, last = _split_name(ship.get("full_name") or order.get("customer_name") or "")
    base = email_templates.base_url(order.get("locale") or "bg")
    address = {
        "first_name": first, "last_name": last, "company": "",
        "address_1": (ship.get("line1") or "").strip() if not office else f"{office.get('name', '')}".strip(),
        "address_2": (ship.get("line2") or "").strip() if not office else (office.get("address") or ""),
        "city": (ship.get("city") or office.get("city") or "").strip(), "state": "",
        "postcode": str(ship.get("postal_code") or office.get("post_code") or "").strip(),
        "country": (ship.get("country") or cfg.get("wc_country") or "BG").upper(),
        "phone": (ship.get("phone") or order.get("customer_phone") or "").strip(),
    }
    billing = {**address, "email": (ship.get("email") or order.get("customer_email") or "").strip()}
    items = []
    for i, it in enumerate(order.get("items") or []):
        qty = int(it.get("quantity") or 1)
        price = float(it.get("price_orig") if it.get("price_orig") is not None else (it.get("price_eur") or 0))
        img = it.get("image") or ""
        items.append({
            "id": i + 1, "name": it.get("title") or it.get("variant_sku") or "", "product_id": wc_int(it.get("product_id") or it.get("product_handle") or ""),
            "variation_id": wc_int(it.get("variant_sku") or ""), "quantity": qty, "tax_class": "",
            "subtotal": _money(price * qty), "subtotal_tax": "0.00", "total": _money(price * qty), "total_tax": "0.00",
            "taxes": [], "meta_data": [{"id": 1, "key": "pa_variant", "value": it.get("variant_name") or "", "display_key": "Опаковка", "display_value": it.get("variant_name") or ""}],
            "sku": it.get("variant_sku") or "", "price": round(price, 2),
            "image": {"id": 0, "src": (img if img.startswith("http") else f"{base}{img}") if img else ""},
            "parent_name": it.get("title") or "",
        })
    is_cod = order.get("payment_method") == "cod"
    # a bank transfer already covers the shipping — NextLevel must see it as free, not charge it again
    shipping_total = _local(order, "shipping") if is_cod else 0.0
    method_title = {"office": "Доставка до офис", "locker": "Доставка до автомат", "address": "Доставка до адрес"}.get(delivery.get("destination_type") or "", "Доставка")
    courier = (delivery.get("provider_key") or "").lower()
    office_nl = str(office.get("id") or "").split(":")[-1] if office else ""
    meta = [
        {"id": 1, "key": "_pp_order_id", "value": order.get("id")},
        {"id": 2, "key": "_pp_locale", "value": order.get("locale") or "bg"},
        {"id": 3, "key": "_delivery_provider", "value": courier},
        {"id": 4, "key": "_delivery_type", "value": delivery.get("destination_type") or "address"},
    ]
    if office:
        meta += [{"id": 5, "key": "_nextlevel_office_id", "value": office_nl}, {"id": 6, "key": "office_id", "value": office_nl},
                 {"id": 7, "key": "_office_code", "value": office.get("code") or ""}, {"id": 8, "key": "_office_name", "value": office.get("name") or ""},
                 {"id": 9, "key": f"_{courier}_office_code", "value": office.get("code") or ""}]
    sh = order.get("shipment") or {}
    if sh.get("awb"):
        meta.append({"id": 10, "key": "_awb", "value": sh["awb"]})
    if is_cod and cfg.get("open_before_pay", True):
        # NextLevel services.obpd — the receiver may open/inspect the parcel before paying
        meta += [{"id": 11, "key": "_obpd_option", "value": (cfg.get("obpd_option") or "OPEN").upper()},
                 {"id": 12, "key": "_obpd_return_shipment_payer", "value": (cfg.get("obpd_return_payer") or "SENDER").upper()},
                 {"id": 13, "key": "_open_before_pay", "value": "yes"}]
    status = wc_status(order, cfg)
    wc_id = order.get("wc_id") or wc_int(order.get("id") or "")
    return {
        "id": wc_id, "parent_id": 0, "status": status, "currency": (order.get("currency") or "EUR").upper(), "version": "8.9.3",
        "prices_include_tax": True, "date_created": _date(order.get("created_at")), "date_modified": _date(order.get("updated_at")),
        "discount_total": _money(_local(order, "discount")), "discount_tax": "0.00", "shipping_total": _money(shipping_total), "shipping_tax": "0.00",
        "cart_tax": "0.00", "total": _money(_local(order, "total")), "total_tax": "0.00", "customer_id": 0, "order_key": f"wc_order_{wc_id}",
        "billing": billing, "shipping": address,
        "payment_method": "cod" if is_cod else "bacs", "payment_method_title": "Наложен платеж" if is_cod else "Банков превод",
        "transaction_id": "", "customer_ip_address": "", "customer_user_agent": "", "created_via": "checkout",
        "customer_note": " ".join(str(x) for x in [order.get("notes"), ship.get("note")] if x).strip(),
        "date_completed": None, "date_paid": _date(order.get("paid_at")) if order.get("payment_status") == "paid" else None,
        "cart_hash": "", "number": str(order.get("order_number") or wc_id), "meta_data": meta, "line_items": items,
        "tax_lines": [], "shipping_lines": [{"id": 1, "method_title": f"{method_title}{' — ' + office.get('name', '') if office else ''}".strip(),
                                            "method_id": f"{courier or 'flat_rate'}_{delivery.get('destination_type') or 'address'}", "instance_id": "1",
                                            "total": _money(shipping_total), "total_tax": "0.00", "taxes": [], "meta_data": []}],
        "fee_lines": [], "coupon_lines": ([{"id": 1, "code": order["discount"]["code"], "discount": _money(_local(order, "discount")), "discount_tax": "0.00"}]
                                          if (order.get("discount") or {}).get("code") else []),
        "refunds": [], "payment_url": "", "is_editable": status in ("pending", "on-hold"), "needs_payment": status in ("pending", "on-hold") and not is_cod,
        "needs_processing": True, "date_created_gmt": _date(order.get("created_at")), "date_modified_gmt": _date(order.get("updated_at")),
        "date_completed_gmt": None, "date_paid_gmt": None, "currency_symbol": {"EUR": "€", "RON": "lei", "HUF": "Ft", "PLN": "zł", "CZK": "Kč"}.get((order.get("currency") or "EUR").upper(), ""),
        "_links": {},
    }


def to_wc_product(p: Dict[str, Any], locale: str = "bg") -> Dict[str, Any]:
    base = email_templates.base_url(locale)
    variants = p.get("variants") or []
    pid = wc_int(p.get("id") or p.get("handle") or "")
    stock = sum(int(v.get("stock") or 0) for v in variants)
    return {
        "id": pid, "name": p.get("title") or "", "slug": p.get("handle") or "", "permalink": f"{base}/products/{p.get('handle', '')}",
        "type": "variable" if len(variants) > 1 else "simple", "status": "publish" if p.get("active", True) else "private",
        "sku": variants[0].get("sku", "") if len(variants) == 1 else "", "price": str(variants[0].get("price_eur", "")) if variants else "",
        "manage_stock": True, "stock_quantity": stock, "stock_status": "instock" if stock > 0 else "outofstock",
        "images": [{"id": i + 1, "src": (u if str(u).startswith("http") else f"{base}{u}")} for i, u in enumerate(p.get("images") or [])][:5],
        "variations": [wc_int(v.get("sku") or "") for v in variants] if len(variants) > 1 else [],
        "meta_data": [], "date_created": _date(p.get("created_at")), "date_modified": _date(p.get("updated_at")),
    }


def to_wc_variation(p: Dict[str, Any], v: Dict[str, Any], locale: str = "bg") -> Dict[str, Any]:
    stock = int(v.get("stock") or 0)
    return {
        "id": wc_int(v.get("sku") or ""), "parent_id": wc_int(p.get("id") or ""), "sku": v.get("sku") or "", "price": str(v.get("price_eur", "")),
        "regular_price": str(v.get("compare_at_eur") or v.get("price_eur", "")), "status": "publish", "manage_stock": True,
        "stock_quantity": stock, "stock_status": "instock" if stock > 0 else "outofstock", "weight": "0.1",
        "attributes": [{"id": 0, "name": "Опаковка", "option": v.get("name") or ""}], "meta_data": [],
        "description": f"{p.get('title', '')} {v.get('name', '')}".strip(),
    }


# ---------------------------------------------------------------- outbound webhook (order.created / order.updated)
async def push_webhook(order: Dict[str, Any], cfg: Dict[str, Any], topic: str = "order.created") -> Dict[str, Any]:
    body = json.dumps(to_wc_order(order, cfg), ensure_ascii=False).encode()
    secret = (cfg.get("wc_consumer_secret") or "").encode()
    sig = base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode() if secret else ""
    resource, event = topic.split(".")
    headers = {"content-type": "application/json", "accept": "application/json",
               "X-WC-Webhook-Source": email_templates.base_url(order.get("locale") or "bg") + "/", "X-WC-Webhook-Topic": topic,
               "X-WC-Webhook-Resource": resource, "X-WC-Webhook-Event": event, "X-WC-Webhook-Signature": sig,
               "X-WC-Webhook-ID": "1", "X-WC-Webhook-Delivery-ID": str(uuid.uuid4()), "User-Agent": "WooCommerce/8.9.3 Hookshot (WordPress/6.5)"}
    r = await _client.post(cfg["webhook_url"], content=body, headers=headers)
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:300]}
    await _log("outbound", f"webhook {topic}", cfg["webhook_url"], r.status_code, {"order": order.get("order_number")}, data)
    return {"status_code": r.status_code, "response": data}


# ---------------------------------------------------------------- inbound API
async def _log(direction: str, method: str, path: str, status: int, req: Any = None, res: Any = None) -> None:
    try:
        await _db.wc_api_log.insert_one({"id": str(uuid.uuid4()), "at": datetime.now(timezone.utc).isoformat(), "direction": direction,
                                         "method": method, "path": path, "status": status,
                                         "request": json.loads(json.dumps(req, default=str)) if req is not None else None,
                                         "response": str(res)[:600] if res is not None else None})
    except Exception as ex:  # logging must never break the API
        log.warning("wc_api log failed: %s", ex)


class WCError(HTTPException):
    """WooCommerce clients expect {code, message, data:{status}} at the top level, not FastAPI's {detail}."""


def _wc_error(status: int, code: str, message: str) -> WCError:
    return WCError(status, {"code": code, "message": message, "data": {"status": status}})


async def wc_error_handler(request: Request, exc: WCError) -> JSONResponse:
    return JSONResponse(exc.detail, status_code=exc.status_code)


async def _auth(request: Request, cfg: Dict[str, Any]) -> None:
    key, secret = cfg.get("wc_consumer_key") or "", cfg.get("wc_consumer_secret") or ""
    if not key or not secret:
        raise _wc_error(401, "woocommerce_rest_cannot_view", "WooCommerce keys are not configured on this shop.")
    got_key, got_secret = request.query_params.get("consumer_key"), request.query_params.get("consumer_secret")
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            got_key, got_secret = base64.b64decode(auth[6:]).decode().split(":", 1)
        except Exception:
            got_key = got_secret = None
    if not (got_key and got_secret and hmac.compare_digest(got_key, key) and hmac.compare_digest(got_secret, secret)):
        raise _wc_error(401, "woocommerce_rest_cannot_view", "Sorry, you cannot list resources.")


async def _order_by_wc_id(wc_id: int) -> Optional[Dict[str, Any]]:
    o = await _db.orders.find_one({"wc_id": wc_id}, {"_id": 0})
    if o:
        return o
    async for row in _db.orders.find({"wc_id": {"$exists": False}}, {"_id": 0, "id": 1}):
        if wc_int(row["id"]) == wc_id:
            await _db.orders.update_one({"id": row["id"]}, {"$set": {"wc_id": wc_id}})
            return await _db.orders.find_one({"id": row["id"]}, {"_id": 0})
    return None


async def backfill_wc_ids() -> int:
    n = 0
    async for row in _db.orders.find({"wc_id": {"$exists": False}}, {"_id": 0, "id": 1}):
        await _db.orders.update_one({"id": row["id"]}, {"$set": {"wc_id": wc_int(row["id"])}})
        n += 1
    return n


def _find_awb(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Waybill from meta_data / tracking fields / note text — whatever the warehouse sends."""
    courier, awb = None, None
    for m in payload.get("meta_data") or []:
        k = str(m.get("key") or "").lower()
        v = str(m.get("value") or "")
        if ("courier" in k or "carrier" in k) and v:
            courier = v
        elif awb is None and any(t in k for t in TRACKING_KEYS) and AWB_RE.search(v):
            awb = AWB_RE.search(v).group(1)
    if awb:
        return {"awb": awb, "courier": courier or payload.get("courier") or payload.get("carrier")}
    for k in ("tracking_number", "awb", "waybill", "shipment_number"):
        if payload.get(k) and AWB_RE.search(str(payload[k])):
            return {"awb": AWB_RE.search(str(payload[k])).group(1), "courier": payload.get("courier") or payload.get("carrier") or courier}
    note = str(payload.get("note") or payload.get("customer_note") or "")
    if note and any(t in note.lower() for t in TRACKING_KEYS) and AWB_RE.search(note):
        return {"awb": AWB_RE.search(note).group(1), "courier": courier}
    return None


async def _apply_update(order: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    import fulfillment

    patch: Dict[str, Any] = {"fulfillment.updated_at": datetime.now(timezone.utc).isoformat(), "fulfillment.transport": "woocommerce",
                             "fulfillment.number": str(order.get("order_number") or "")}
    status = str(payload.get("status") or "").lower()
    if status:
        patch["fulfillment.status"] = {"completed": "shipped", "cancelled": "cancelled", "processing": "processing", "on-hold": "waiting", "refunded": "returned"}.get(status, status)
        patch["fulfillment.wc_status"] = status
        if status == "completed" and (order.get("fulfillment_status") or "unfulfilled") == "unfulfilled":
            patch["fulfillment_status"] = "shipped"
        if status == "cancelled" and order.get("status") != "cancelled":
            patch["fulfillment.warehouse_cancelled"] = True
    found = _find_awb(payload)
    if found:
        patch["fulfillment.awb"] = found["awb"]
        if found.get("courier"):
            patch["fulfillment.courier"] = found["courier"]
    await _db.orders.update_one({"id": order["id"]}, {"$set": patch})
    if found:
        await fulfillment._apply_awb(order, {"awb": found["awb"], "courier": found.get("courier") or (order.get("fulfillment") or {}).get("courier"),
                                             "shipment_status": "Shipped"})
    fresh = await _db.orders.find_one({"id": order["id"]}, {"_id": 0})
    if patch.get("fulfillment.warehouse_cancelled"):
        # the warehouse cancelled on its side → cancel in the shop too (stock back + e-mail)
        await fulfillment.warehouse_cancelled(order["id"], "NextLevel (WooCommerce API)")
        fresh = await _db.orders.find_one({"id": order["id"]}, {"_id": 0})
    return fresh


def init(db_, get_cfg) -> APIRouter:
    """`get_cfg` is fulfillment.get_config (the WooCommerce keys live in the same settings document)."""
    global _db
    _db = db_
    router = APIRouter()

    async def guard(request: Request) -> Dict[str, Any]:
        cfg = await get_cfg()
        try:
            await _auth(request, cfg)
        except WCError:
            await _log("inbound", request.method, request.url.path.split("/wc/v3", 1)[-1] or "/", 401,
                       {"query": dict(request.query_params), "auth": request.headers.get("authorization", "")[:6], "ua": request.headers.get("user-agent", "")[:80]})
            raise
        return cfg

    @router.get("")
    @router.get("/")
    async def index(request: Request):
        cfg = await guard(request)
        return {"namespace": "wc/v3", "routes": {"/wc/v3/orders": {}, "/wc/v3/orders/(?P<id>[\\d]+)": {}, "/wc/v3/products": {}, "/wc/v3/system_status": {}},
                "store": {"country": cfg.get("wc_country") or "BG"}}

    @router.get("/system_status")
    async def system_status(request: Request):
        cfg = await guard(request)
        base = email_templates.base_url("bg")
        return {"environment": {"home_url": base, "site_url": base, "version": "8.9.3", "wp_version": "6.5.4", "wp_multisite": False},
                "settings": {"currency": "EUR", "currency_symbol": "€", "thousand_separator": " ", "decimal_separator": ",", "number_of_decimals": 2},
                "database": {}, "active_plugins": [], "theme": {}, "security": {"secure_connection": True}, "pages": [],
                "store": {"country": cfg.get("wc_country") or "BG"}}

    @router.get("/orders")
    async def list_orders(request: Request, response: Response, status: str = "any", after: str = "", before: str = "", page: int = 1,
                          per_page: int = 10, search: str = "", include: str = "", order: str = "desc", orderby: str = "date"):
        cfg = await guard(request)
        q: Dict[str, Any] = {"source": {"$ne": "nextlevel-selftest"}}
        if after:
            q["created_at"] = {"$gte": after[:19]}
        if before:
            q.setdefault("created_at", {})["$lte"] = before[:19] + "\uffff"
        if search:
            q["$or"] = [{"order_number": {"$regex": re.escape(search), "$options": "i"}}, {"customer_email": {"$regex": re.escape(search), "$options": "i"}}]
        if include:
            ids = [int(x) for x in include.split(",") if x.strip().isdigit()]
            q["wc_id"] = {"$in": ids}
        rows = await _db.orders.find(q, {"_id": 0}).sort("created_at", -1 if order == "desc" else 1).to_list(3000)
        wanted = None if status in ("", "any") else set(s.strip() for s in status.split(","))
        out = [to_wc_order(o, cfg) for o in rows]
        if wanted:
            out = [o for o in out if o["status"] in wanted]
        total = len(out)
        per_page = max(1, min(per_page, 100))
        page_rows = out[(page - 1) * per_page: page * per_page]
        response.headers["X-WP-Total"] = str(total)
        response.headers["X-WP-TotalPages"] = str(max(1, -(-total // per_page)))
        await _log("inbound", "GET", "/orders", 200, dict(request.query_params), f"{len(page_rows)} orders")
        return page_rows

    @router.get("/orders/{wc_id}")
    async def get_order(wc_id: int, request: Request):
        cfg = await guard(request)
        o = await _order_by_wc_id(wc_id)
        if not o:
            await _log("inbound", "GET", f"/orders/{wc_id}", 404)
            raise _wc_error(404, "woocommerce_rest_shop_order_invalid_id", "Invalid ID.")
        await _log("inbound", "GET", f"/orders/{wc_id}", 200, None, o.get("order_number"))
        return to_wc_order(o, cfg)

    @router.put("/orders/{wc_id}")
    @router.post("/orders/{wc_id}")
    @router.patch("/orders/{wc_id}")
    async def update_order(wc_id: int, request: Request):
        cfg = await guard(request)
        o = await _order_by_wc_id(wc_id)
        if not o:
            raise _wc_error(404, "woocommerce_rest_shop_order_invalid_id", "Invalid ID.")
        try:
            payload = await request.json()
        except Exception:
            payload = dict(await request.form()) if request.headers.get("content-type", "").startswith("application/x-www-form") else {}
        fresh = await _apply_update(o, payload if isinstance(payload, dict) else {})
        await _log("inbound", request.method, f"/orders/{wc_id}", 200, payload, f"{o.get('order_number')} → {payload.get('status') if isinstance(payload, dict) else ''}")
        return to_wc_order(fresh, cfg)

    @router.get("/orders/{wc_id}/notes")
    async def list_notes(wc_id: int, request: Request):
        await guard(request)
        o = await _order_by_wc_id(wc_id)
        if not o:
            raise _wc_error(404, "woocommerce_rest_shop_order_invalid_id", "Invalid ID.")
        return o.get("wc_notes") or []

    @router.post("/orders/{wc_id}/notes")
    async def add_note(wc_id: int, request: Request):
        await guard(request)
        o = await _order_by_wc_id(wc_id)
        if not o:
            raise _wc_error(404, "woocommerce_rest_shop_order_invalid_id", "Invalid ID.")
        payload = await request.json()
        note = {"id": len(o.get("wc_notes") or []) + 1, "author": "NextLevel", "date_created": _now_iso(), "note": str(payload.get("note") or ""),
                "customer_note": bool(payload.get("customer_note"))}
        await _db.orders.update_one({"id": o["id"]}, {"$push": {"wc_notes": note}})
        await _apply_update(o, {"note": note["note"]})
        await _log("inbound", "POST", f"/orders/{wc_id}/notes", 201, payload, o.get("order_number"))
        return note

    @router.get("/products")
    async def list_products(request: Request, response: Response, page: int = 1, per_page: int = 10, sku: str = "", search: str = "", status: str = "any"):
        await guard(request)
        q: Dict[str, Any] = {}
        if sku:
            q["variants.sku"] = {"$in": [s.strip() for s in sku.split(",")]}
        if search:
            q["title"] = {"$regex": re.escape(search), "$options": "i"}
        rows = await _db.products.find(q, {"_id": 0}).to_list(1000)
        out = [to_wc_product(p) for p in rows]
        if sku:  # WooCommerce returns the matching variation as a product when the sku belongs to a variation
            wanted = {s.strip() for s in sku.split(",")}
            out = [to_wc_variation(p, v) | {"name": f"{p.get('title', '')} {v.get('name', '')}".strip(), "type": "variation"}
                   for p in rows for v in p.get("variants") or [] if v.get("sku") in wanted]
        per_page = max(1, min(per_page, 100))
        response.headers["X-WP-Total"] = str(len(out))
        response.headers["X-WP-TotalPages"] = str(max(1, -(-len(out) // per_page)))
        await _log("inbound", "GET", "/products", 200, dict(request.query_params), f"{len(out)} products")
        return out[(page - 1) * per_page: page * per_page]

    async def _product(pid: int) -> Dict[str, Any]:
        async for p in _db.products.find({}, {"_id": 0}):
            if wc_int(p.get("id") or "") == pid:
                return p
        raise _wc_error(404, "woocommerce_rest_product_invalid_id", "Invalid ID.")

    async def _set_stock(p: Dict[str, Any], v: Dict[str, Any], qty: int) -> None:
        before = int(v.get("stock") or 0)
        await _db.products.update_one({"id": p["id"], "variants.sku": v.get("sku")}, {"$set": {"variants.$.stock": qty}})
        await _db.inventory_log.insert_one({"id": str(uuid.uuid4()), "product_id": p.get("id"), "product_title": p.get("title"), "handle": p.get("handle"),
                                            "variant_name": v.get("name"), "change": qty - before, "stock_after": qty, "reason": "nextlevel_sync",
                                            "actor": "nextlevel", "created_at": datetime.now(timezone.utc).isoformat()})

    @router.get("/products/{pid}")
    async def get_product(pid: int, request: Request):
        await guard(request)
        return to_wc_product(await _product(pid))

    @router.put("/products/{pid}")
    @router.post("/products/{pid}")
    async def update_product(pid: int, request: Request):
        await guard(request)
        p = await _product(pid)
        payload = await request.json()
        if payload.get("stock_quantity") is not None and len(p.get("variants") or []) == 1:
            await _set_stock(p, p["variants"][0], int(payload["stock_quantity"]))
            p = await _product(pid)
        await _log("inbound", request.method, f"/products/{pid}", 200, payload, p.get("title"))
        return to_wc_product(p)

    @router.get("/products/{pid}/variations")
    async def list_variations(pid: int, request: Request):
        await guard(request)
        p = await _product(pid)
        return [to_wc_variation(p, v) for v in p.get("variants") or []]

    @router.get("/products/{pid}/variations/{vid}")
    async def get_variation(pid: int, vid: int, request: Request):
        await guard(request)
        p = await _product(pid)
        v = next((v for v in p.get("variants") or [] if wc_int(v.get("sku") or "") == vid), None)
        if not v:
            raise _wc_error(404, "woocommerce_rest_product_variation_invalid_id", "Invalid ID.")
        return to_wc_variation(p, v)

    @router.put("/products/{pid}/variations/{vid}")
    @router.post("/products/{pid}/variations/{vid}")
    async def update_variation(pid: int, vid: int, request: Request):
        await guard(request)
        p = await _product(pid)
        v = next((v for v in p.get("variants") or [] if wc_int(v.get("sku") or "") == vid), None)
        if not v:
            raise _wc_error(404, "woocommerce_rest_product_variation_invalid_id", "Invalid ID.")
        payload = await request.json()
        if payload.get("stock_quantity") is not None:
            await _set_stock(p, v, int(payload["stock_quantity"]))
            v = {**v, "stock": int(payload["stock_quantity"])}
        await _log("inbound", request.method, f"/products/{pid}/variations/{vid}", 200, payload, v.get("sku"))
        return to_wc_variation(p, v)

    @router.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def unknown(rest: str, request: Request):
        cfg = await get_cfg()
        try:
            await _auth(request, cfg)
            status = 404
        except HTTPException:
            status = 401
        body = None
        try:
            body = await request.json()
        except Exception:
            pass
        await _log("inbound", request.method, f"/{rest}", status, {"query": dict(request.query_params), "body": body})
        raise _wc_error(status, "rest_no_route" if status == 404 else "woocommerce_rest_cannot_view",
                        "No route was found matching the URL and request method" if status == 404 else "Sorry, you cannot list resources.")

    return router


async def recent_log(limit: int = 40) -> List[Dict[str, Any]]:
    return await _db.wc_api_log.find({}, {"_id": 0}).sort("at", -1).to_list(limit)
