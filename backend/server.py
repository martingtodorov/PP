"""PurePeptide backend - FastAPI + Motor + JWT auth + bank-transfer commerce."""

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import csv
import html as html_lib
import io
import re
import secrets
import sys
import tempfile
import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from seed_data import COLLECTIONS, PRODUCTS, ARTICLES, DEFAULT_SETTINGS, SEED_VERSION
from translations_seed import COLLECTION_TR, PRODUCT_TR, ARTICLE_TR
from i18n import (
    LOCALES, DEFAULT_LOCALE, LOCALE_META, SITE_ORIGINS,
    normalize_locale, localize_doc, localize_list, ai_translate, ai_translate_page,
)
from pages_seed import PAGE_SLUGS, PAGE_LABELS, DEFAULT_PAGES
import storage
import email_service
import push_service

# ---------- App + DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="PurePeptide API")
api = APIRouter(prefix="/api")

JWT_ALG = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@purepeptide.bg")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@PurePeptide2026")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("purepeptide")


# ---------- Helpers ----------
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: str, email: str, role: str, ttl_minutes: int = 60 * 24 * 7) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="pp_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie("pp_token", path="/")


async def get_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get("pp_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    return user


async def require_user(request: Request) -> Dict[str, Any]:
    u = await get_user_from_request(request)
    if not u:
        raise HTTPException(status_code=401, detail="Не сте удостоверени")
    return u


async def require_admin(request: Request) -> Dict[str, Any]:
    u = await require_user(request)
    if u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Нямате администраторски достъп")
    return u


def public_user(u: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "phone": u.get("phone", ""),
        "role": u.get("role", "customer"),
    }


# ---------- Models ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = ""
    phone: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class Address(BaseModel):
    full_name: str
    phone: str
    email: Optional[EmailStr] = None
    line1: str
    city: str
    postal_code: str
    country: str = "BG"
    note: Optional[str] = ""


class CartLine(BaseModel):
    product_id: str
    variant_sku: str
    quantity: int = Field(gt=0)


class CheckoutIn(BaseModel):
    items: List[CartLine]
    shipping: Address
    customer_email: EmailStr
    customer_name: str
    customer_phone: str
    shipping_method: str = "econt_office"  # econt_office | econt_address | speedy
    notes: Optional[str] = ""
    discount_code: Optional[str] = ""
    terms_accepted: bool = False


class ProductIn(BaseModel):
    handle: str
    title: str
    subtitle: Optional[str] = ""
    description: str = ""
    image: str = ""
    images: List[str] = []
    variants: List[Dict[str, Any]] = []
    collections: List[str] = []
    tags: List[str] = []
    featured: bool = False
    specs: Dict[str, Any] = {}
    seo_title: Optional[str] = ""
    seo_description: Optional[str] = ""
    translations: Dict[str, Dict[str, Any]] = {}


class CollectionIn(BaseModel):
    handle: str
    title: str
    description: str = ""
    image: str = ""
    sort_order: int = 0
    seo_title: Optional[str] = ""
    seo_description: Optional[str] = ""
    translations: Dict[str, Dict[str, Any]] = {}


class TranslateIn(BaseModel):
    resource: str  # product | collection
    id: str
    locales: List[str] = []
    overwrite: bool = False


# ---------- Seeders ----------
async def seed_admin():
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": ADMIN_EMAIL,
            "password_hash": hash_password(ADMIN_PASSWORD),
            "name": "Администратор",
            "phone": "",
            "role": "admin",
            "created_at": now_utc(),
        })
        log.info("Seeded admin: %s", ADMIN_EMAIL)
    elif not verify_password(ADMIN_PASSWORD, existing["password_hash"]):
        await db.users.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"password_hash": hash_password(ADMIN_PASSWORD)}},
        )

    test_email = "customer@example.com"
    if not await db.users.find_one({"email": test_email}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": test_email,
            "password_hash": hash_password("Customer123!"),
            "name": "Иван Петров",
            "phone": "+359888000111",
            "role": "customer",
            "created_at": now_utc(),
        })


async def seed_catalog():
    """Seed / re-seed the catalog. A change of SEED_VERSION rebuilds the mirrored Shopify catalog."""
    current = await db.settings.find_one({"key": "site"})
    if ((current or {}).get("value") or {}).get("catalog_imported"):
        return
    seeded_version = (current or {}).get("value", {}).get("seed_version")
    stale = seeded_version != SEED_VERSION

    if stale:
        await db.collections_cat.delete_many({})
        await db.products.delete_many({})
        await db.articles.delete_many({})
        log.info("Re-seeding catalog for version %s", SEED_VERSION)

    if await db.collections_cat.count_documents({}) == 0:
        for c in COLLECTIONS:
            base_tr = {**(c.get("translations") or {})}
            for loc, fields in (COLLECTION_TR.get(c["handle"]) or {}).items():
                base_tr[loc] = {**(base_tr.get(loc) or {}), **fields}
            await db.collections_cat.insert_one({
                "id": str(uuid.uuid4()),
                "created_at": now_utc(),
                **c,
                "translations": base_tr,
            })
        log.info("Seeded %d collections", len(COLLECTIONS))

    if await db.products.count_documents({}) == 0:
        for p in PRODUCTS:
            base_tr = {**(p.get("translations") or {})}
            for loc, fields in (PRODUCT_TR.get(p["handle"]) or {}).items():
                base_tr[loc] = {**(base_tr.get(loc) or {}), **fields}
            doc = {
                "id": str(uuid.uuid4()),
                "created_at": now_utc(),
                "featured": False,
                "specs": {},
                "images": p.get("images", [p["image"]]),
                **p,
                "translations": base_tr,
            }
            await db.products.insert_one(doc)
        log.info("Seeded %d products", len(PRODUCTS))

    if await db.articles.count_documents({}) == 0:
        for a in ARTICLES:
            await db.articles.insert_one({
                "id": str(uuid.uuid4()),
                "published_at": now_utc(),
                **a,
                "translations": ARTICLE_TR.get(a["handle"], {}),
            })

    if not current or stale:
        merged = {**DEFAULT_SETTINGS, **(current or {}).get("value", {}), "seed_version": SEED_VERSION}
        if stale:
            merged = {**DEFAULT_SETTINGS}
        await db.settings.update_one(
            {"key": "site"}, {"$set": {"value": merged, "updated_at": now_utc()}}, upsert=True
        )
    else:
        # backfill any newly introduced settings keys without touching existing values
        existing_value = current.get("value", {})
        missing = {k: v for k, v in DEFAULT_SETTINGS.items() if k not in existing_value}
        if missing:
            await db.settings.update_one(
                {"key": "site"}, {"$set": {**{f"value.{k}": v for k, v in missing.items()}, "updated_at": now_utc()}}
            )


async def seed_pages():
    """Insert the default Bulgarian/English static page content once."""
    for slug, per_locale in DEFAULT_PAGES.items():
        for locale, content in per_locale.items():
            existing = await db.pages.find_one({"slug": slug, "locale": locale})
            if existing:
                continue
            await db.pages.insert_one({
                "id": str(uuid.uuid4()),
                "slug": slug,
                "locale": locale,
                "title": content.get("title", ""),
                "html": content.get("html", ""),
                "faq_items": content.get("faq_items", []),
                "updated_at": now_utc(),
            })


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("handle", unique=True)
    await db.products.create_index("id", unique=True)
    await db.collections_cat.create_index("handle", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index("order_number", unique=True)
    await db.pages.create_index([("slug", 1), ("locale", 1)], unique=True)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    await seed_admin()
    await seed_catalog()
    await seed_pages()
    try:
        storage.init_storage()
        log.info("Object storage initialized")
    except Exception as ex:
        log.error("Storage init failed: %s", ex)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ---------- Auth routes ----------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    """Self-registration is disabled — accounts are created by the shop owner only."""
    raise HTTPException(status_code=403, detail="Създаването на профил не е достъпно")


@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Невалидни данни за вход")
    token = create_token(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return {"user": public_user(user), "token": token}


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request):
    u = await get_user_from_request(request)
    if not u:
        return {"user": None}
    return {"user": public_user(u)}


# ---------- Public catalog ----------
def clean_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    d.pop("_id", None)
    return d


@api.get("/collections")
async def list_collections(locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    docs = await db.collections_cat.find({}, {"_id": 0}).sort("sort_order", 1).to_list(100)
    return {"collections": localize_list(docs, loc)}


def _apply_manual_order(prods: List[Dict[str, Any]], order: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Sort products by the manual order saved in the admin; unknown handles keep their position at the end."""
    if not order:
        return prods
    index = {h: i for i, h in enumerate(order)}
    return sorted(prods, key=lambda p: (index.get(p.get("handle"), len(index)), p.get("title", "")))


@api.get("/collections/{handle}")
async def get_collection(handle: str, locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    col = await db.collections_cat.find_one(
        {"$or": [{"handle": handle}, {f"translations.{loc}.handle": handle}]}, {"_id": 0}
    )
    if not col:
        raise HTTPException(404, "Колекцията не е намерена")
    base_handle = col["handle"]
    if base_handle == "all-peptides":
        prods = await db.products.find({"active": {"$ne": False}}, {"_id": 0}).to_list(500)
    else:
        prods = await db.products.find({"collections": base_handle, "active": {"$ne": False}}, {"_id": 0}).to_list(500)
    siblings = await db.collections_cat.find(
        {"handle": {"$nin": [base_handle, "all-peptides"]}}, {"_id": 0}
    ).sort("sort_order", 1).to_list(50)
    prods = _apply_manual_order(prods, col.get("product_order"))
    return {
        "collection": localize_doc(col, loc),
        "products": localize_list(prods, loc),
        "siblings": localize_list(siblings, loc),
    }


@api.get("/products")
async def list_products(
    featured: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    locale: str = Query(DEFAULT_LOCALE),
):
    loc = normalize_locale(locale)
    q: Dict[str, Any] = {"active": {"$ne": False}}
    if featured is not None:
        q["featured"] = featured
    if search:
        q["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {f"translations.{loc}.title": {"$regex": search, "$options": "i"}},
        ]
    docs = await db.products.find(q, {"_id": 0}).limit(500).to_list(500)
    if not search:
        all_col = await db.collections_cat.find_one({"handle": "all-peptides"}, {"_id": 0, "product_order": 1})
        docs = _apply_manual_order(docs, (all_col or {}).get("product_order"))
    return {"products": localize_list(docs[:limit], loc)}


@api.get("/products/{handle}")
async def get_product(handle: str, locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    p = await db.products.find_one(
        {"$or": [{"handle": handle}, {f"translations.{loc}.handle": handle}]}, {"_id": 0}
    )
    if not p:
        raise HTTPException(404, "Продуктът не е намерен")
    related = await db.products.find(
        {"handle": {"$ne": p["handle"]}, "collections": {"$in": p.get("collections", [])}},
        {"_id": 0},
    ).limit(8).to_list(8)
    cols = await db.collections_cat.find(
        {"handle": {"$in": p.get("collections", [])}}, {"_id": 0}
    ).to_list(20)
    articles = await db.articles.find({"product_handle": p["handle"]}, {"_id": 0}).to_list(5)
    return {
        "product": localize_doc(p, loc),
        "related": localize_list(related, loc),
        "collections": localize_list(cols, loc),
        "articles": localize_list(articles, loc),
    }


@api.get("/articles")
async def list_articles(locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    docs = await db.articles.find({}, {"_id": 0}).to_list(50)
    return {"articles": localize_list(docs, loc)}


@api.get("/locales")
async def get_locales():
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    return {"locales": LOCALES, "meta": LOCALE_META, "routes": routes}


# ---------- Delisted / retired URLs (content rotation board) ----------
class DelistedLinkIn(BaseModel):
    url: str
    locale: str = "bg"
    reason: str = ""
    status: str = "pending"  # pending | rotated | redirected | ignored
    replacement_url: str = ""
    notes: str = ""


@api.get("/admin/delisted-links")
async def list_delisted_links(user=Depends(require_admin)):
    docs = await db.delisted_links.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"links": docs}


@api.post("/admin/delisted-links")
async def create_delisted_link(payload: DelistedLinkIn, user=Depends(require_admin)):
    doc = {
        "id": str(uuid.uuid4()),
        **payload.model_dump(),
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "created_by": user["email"],
    }
    await db.delisted_links.insert_one(doc)
    return {"link": {k: v for k, v in doc.items() if k != "_id"}}


@api.put("/admin/delisted-links/{link_id}")
async def update_delisted_link(link_id: str, payload: DelistedLinkIn, user=Depends(require_admin)):
    res = await db.delisted_links.update_one(
        {"id": link_id}, {"$set": {**payload.model_dump(), "updated_at": now_utc()}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Линкът не е намерен")
    return {"ok": True}


@api.delete("/admin/delisted-links/{link_id}")
async def delete_delisted_link(link_id: str, user=Depends(require_admin)):
    res = await db.delisted_links.delete_one({"id": link_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Линкът не е намерен")
    return {"ok": True}


@api.get("/settings")
async def get_settings():
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    value = dict(s["value"]) if s else dict(DEFAULT_SETTINGS)
    for secret in ("resend_api_key", "discount_codes"):
        value.pop(secret, None)
    return value


# ---------- Checkout / Orders ----------
ORDER_CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
ORDER_CODE_DIGITS = "0123456789"


async def _next_order_number() -> str:
    """Random 5-character order code: 3 letters + 2 digits (e.g. KTX48)."""
    for _ in range(50):
        code = "".join(secrets.choice(ORDER_CODE_LETTERS) for _ in range(3)) + \
               "".join(secrets.choice(ORDER_CODE_DIGITS) for _ in range(2))
        if not await db.orders.find_one({"order_number": code}):
            return code
    return "".join(secrets.choice(ORDER_CODE_LETTERS + ORDER_CODE_DIGITS) for _ in range(5))


async def _resolve_discount(code: str, subtotal: float) -> Dict[str, Any]:
    """Returns {code, type, value, discount_eur} or raises HTTPException."""
    if not code:
        return {"code": "", "discount_eur": 0.0}
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    codes = ((s or {}).get("value") or {}).get("discount_codes", [])
    found = next((c for c in codes if c.get("code", "").upper() == code.strip().upper() and c.get("active")), None)
    if not found:
        raise HTTPException(400, "Невалиден код за отстъпка")
    if subtotal < float(found.get("min_subtotal", 0)):
        raise HTTPException(400, f"Кодът е валиден при сума над {found['min_subtotal']} EUR")
    if found["type"] == "percent":
        amount = subtotal * float(found["value"]) / 100.0
    else:
        amount = float(found["value"])
    amount = round(min(amount, subtotal), 2)
    return {"code": found["code"].upper(), "type": found["type"], "value": found["value"], "discount_eur": amount}


class DiscountIn(BaseModel):
    code: str
    subtotal_eur: float = 0.0


@api.post("/discount/validate")
async def validate_discount(payload: DiscountIn):
    return await _resolve_discount(payload.code, payload.subtotal_eur)


def _calc_totals(line_items: List[Dict[str, Any]], shipping_method: str, discount_eur: float = 0.0) -> Dict[str, float]:
    subtotal = sum(li["price_eur"] * li["quantity"] for li in line_items)
    shipping_cost = 0.0 if subtotal >= 100 else (5.99 if shipping_method != "speedy" else 7.49)
    total = subtotal - discount_eur + shipping_cost
    return {
        "subtotal_eur": round(subtotal, 2),
        "discount_eur": round(discount_eur, 2),
        "shipping_eur": shipping_cost,
        "total_eur": round(max(total, 0), 2),
    }


@api.post("/checkout")
async def checkout(payload: CheckoutIn, request: Request):
    if not payload.items:
        raise HTTPException(400, "Количката е празна")
    if not payload.terms_accepted:
        raise HTTPException(400, "Трябва да приемете общите условия")

    line_items = []
    for li in payload.items:
        prod = await db.products.find_one({"id": li.product_id}, {"_id": 0})
        if not prod:
            raise HTTPException(400, f"Продукт не е намерен: {li.product_id}")
        variant = next((v for v in prod.get("variants", []) if v.get("sku") == li.variant_sku), None)
        if not variant:
            raise HTTPException(400, f"Вариант не е намерен: {li.variant_sku}")
        if variant.get("stock", 0) < li.quantity:
            raise HTTPException(400, f"Недостатъчна наличност за {prod['title']} {variant['name']}")
        line_items.append({
            "product_id": prod["id"],
            "product_handle": prod["handle"],
            "title": prod["title"],
            "image": prod.get("image", ""),
            "variant_sku": variant["sku"],
            "variant_name": variant["name"],
            "price_eur": float(variant["price_eur"]),
            "quantity": li.quantity,
        })

    subtotal_raw = sum(li["price_eur"] * li["quantity"] for li in line_items)
    discount = await _resolve_discount(payload.discount_code or "", subtotal_raw)
    totals = _calc_totals(line_items, payload.shipping_method, discount.get("discount_eur", 0.0))
    user = await get_user_from_request(request)

    order = {
        "id": str(uuid.uuid4()),
        "order_number": await _next_order_number(),
        "customer_id": user["id"] if user else None,
        "customer_email": payload.customer_email.lower(),
        "customer_name": payload.customer_name,
        "customer_phone": payload.customer_phone,
        "items": line_items,
        "shipping": payload.shipping.model_dump(),
        "shipping_method": payload.shipping_method,
        "notes": payload.notes,
        "discount": discount,
        "terms_accepted": payload.terms_accepted,
        **totals,
        "currency": "EUR",
        "payment_status": "awaiting_payment",
        "fulfillment_status": "unfulfilled",
        "payment_method": "bank_transfer",
        "tracking": None,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    await db.orders.insert_one(order.copy())

    # decrement stock + inventory log
    for li in line_items:
        await db.products.update_one(
            {"id": li["product_id"], "variants.sku": li["variant_sku"]},
            {"$inc": {"variants.$.stock": -li["quantity"]}},
        )
        product = await db.products.find_one({"id": li["product_id"]}, {"_id": 0})
        if product:
            variant = next((v for v in product.get("variants", []) if v.get("sku") == li["variant_sku"]), {})
            await log_inventory(product, variant.get("name", li.get("variant_name", "")),
                                -li["quantity"], int(variant.get("stock") or 0),
                                f"Поръчка {order['order_number']}", "checkout")

    # bank instructions
    bank = {
        "name": os.environ.get("BANK_NAME", "UniCredit Bulbank"),
        "iban": os.environ.get("BANK_IBAN", "BG18UNCR70001523456789"),
        "bic": os.environ.get("BANK_BIC", "UNCRBGSF"),
        "holder": os.environ.get("BANK_HOLDER", "PurePeptide EOOD"),
        "reference": order["order_number"],
        "amount_eur": totals["total_eur"],
    }
    order_clean = {k: v for k, v in order.items() if k != "_id"}
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    site_settings = (s or {}).get("value", {})
    try:
        await email_service.send_order_confirmation(order_clean, bank, site_settings)
    except Exception:
        log.exception("Order confirmation email failed")
    items_summary = ", ".join(
        "{}{} ×{}".format(
            li.get("title", ""),
            " ({})".format(li["variant_name"]) if li.get("variant_name") else "",
            li.get("quantity", 1),
        )
        for li in line_items
    )[:180]
    try:
        await notify_admin_push_bg(
            "Нова поръчка {} · {:.2f} €".format(order["order_number"], totals["total_eur"]),
            "{} · {}".format(order.get("customer_name") or "", items_summary),
            "/admin/orders/{}".format(order["id"]),
            "order-{}".format(order["id"]),
        )
    except Exception:
        log.exception("Order push notification failed")
    try:
        admin_to = os.environ.get("CONTACT_EMAIL") or os.environ["ADMIN_EMAIL"]
        await email_service.send_email(
            admin_to,
            f"Нова поръчка {order['order_number']} — {totals['total_eur']:.2f} €",
            f"<h2 style='font-family:system-ui'>Нова поръчка {order['order_number']}</h2>"
            f"<p style='font-family:system-ui'>{order.get('customer_name') or ''} · {order.get('customer_email') or ''} · "
            f"{order.get('customer_phone') or ''}</p>"
            f"<p style='font-family:system-ui'>Сума: <strong>{totals['total_eur']:.2f} €</strong><br>"
            f"Артикули: {items_summary}</p>",
            site_settings,
        )
    except Exception:
        log.exception("Admin order email failed")
    return {"order": order_clean, "bank_transfer": bank}


@api.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Поръчката не е намерена")
    user = await get_user_from_request(request)
    is_owner = user and (user.get("role") == "admin" or o.get("customer_id") == user.get("id"))
    if not is_owner:
        # allow guest lookup by id (acts as token) for confirmation page
        return {"order": o, "guest_view": True}
    return {"order": o}


@api.get("/me/orders")
async def my_orders(user=Depends(require_user)):
    docs = await db.orders.find({"customer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"orders": docs}


# ---------- Admin ----------
@api.get("/admin/stats")
async def admin_stats(user=Depends(require_admin)):
    total_orders = await db.orders.count_documents({})
    awaiting = await db.orders.count_documents({"payment_status": "awaiting_payment"})
    paid = await db.orders.count_documents({"payment_status": "paid"})
    pending_ship = await db.orders.count_documents({"payment_status": "paid", "fulfillment_status": "unfulfilled"})
    customers = await db.users.count_documents({"role": "customer"})
    products = await db.products.count_documents({})
    pipeline = [
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$total_eur"}}},
    ]
    rev = await db.orders.aggregate(pipeline).to_list(1)
    revenue = rev[0]["total"] if rev else 0
    return {
        "total_orders": total_orders,
        "awaiting_payment": awaiting,
        "paid": paid,
        "pending_shipments": pending_ship,
        "customers": customers,
        "products": products,
        "revenue_eur": round(revenue, 2),
    }


def _order_view(o: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise native checkout orders and Shopify-imported orders into one shape."""
    info = o.get("customer_info") or {}
    ship = o.get("shipping") or {}
    raw_items = o.get("items") or o.get("line_items") or []
    items = [{
        "title": it.get("title", ""),
        "variant": it.get("variant_name") or it.get("variant") or "",
        "sku": it.get("variant_sku") or it.get("sku") or "",
        "quantity": int(it.get("quantity") or 1),
        "price_eur": float(it.get("price_eur") or 0),
        "product_handle": it.get("product_handle") or "",
    } for it in raw_items]
    fulfillment = o.get("fulfillment_status")
    if not fulfillment:
        fulfillment = "fulfilled" if o.get("status") == "shipped" else (
            "cancelled" if o.get("status") == "cancelled" else "unfulfilled")
    tracking = o.get("tracking")
    if not tracking and o.get("tracking_number"):
        tracking = {"tracking_number": o["tracking_number"], "tracking_url": "", "carrier": ""}
    return {
        "id": o.get("id"),
        "order_number": o.get("order_number"),
        "created_at": o.get("created_at"),
        "customer": {
            "name": o.get("customer_name") or info.get("name") or "",
            "email": o.get("customer_email") or info.get("email") or "",
            "phone": o.get("customer_phone") or info.get("phone") or "",
            "address": {
                "line1": ship.get("line1") or info.get("address") or "",
                "city": ship.get("city") or info.get("city") or "",
                "zip": ship.get("postal_code") or info.get("zip") or "",
                "country": ship.get("country") or info.get("country") or "",
            },
        },
        "items": items,
        "items_count": sum(i["quantity"] for i in items),
        "subtotal_eur": round(float(o.get("subtotal_eur") or 0), 2),
        "discount_eur": round(float(o.get("discount_eur") or 0), 2),
        "shipping_eur": round(float(o.get("shipping_eur") or 0), 2),
        "total_eur": round(float(o.get("total_eur") or 0), 2),
        "payment_status": o.get("payment_status") or "awaiting_payment",
        "fulfillment_status": fulfillment,
        "shipping_method": o.get("shipping_method") or (tracking or {}).get("carrier") or "",
        "payment_method": o.get("payment_method") or "",
        "tracking": tracking,
        "note": o.get("notes") or o.get("note") or "",
        "source": o.get("source") or "storefront",
        "currency": o.get("currency") or "EUR",
    }


ORDER_FILTERS = {
    "unfulfilled": {"fulfillment_status": {"$nin": ["fulfilled", "shipped"]}, "status": {"$ne": "cancelled"}},
    "unpaid": {"payment_status": {"$ne": "paid"}, "status": {"$ne": "cancelled"}},
    "paid": {"payment_status": "paid"},
    "awaiting_payment": {"payment_status": {"$in": ["awaiting_payment", "pending"]}},
    "shipped": {"$or": [{"fulfillment_status": {"$in": ["shipped", "fulfilled"]}}, {"status": "shipped"}]},
    "archived": {"$or": [{"status": "cancelled"}, {"payment_status": "paid", "fulfillment_status": {"$in": ["fulfilled", "shipped"]}}]},
}


@api.get("/admin/orders")
async def admin_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    user=Depends(require_admin),
):
    q: Dict[str, Any] = dict(ORDER_FILTERS.get(status or "", {}))
    if status == "open":
        q = {"status": {"$ne": "cancelled"}}
    if search:
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        clauses = [{"$or": [
            {"order_number": rx}, {"customer_email": rx}, {"customer_name": rx},
            {"customer_info.email": rx}, {"customer_info.name": rx}, {"customer_info.phone": rx},
        ]}]
        if "$or" in q:
            clauses.append({"$or": q.pop("$or")})
        q["$and"] = clauses
    total = await db.orders.count_documents(q)
    docs = await db.orders.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(min(limit, 200)).to_list(200)
    return {"orders": [_order_view(d) for d in docs], "total": total, "skip": skip}


@api.get("/admin/orders/{order_id}")
async def admin_order_detail(order_id: str, user=Depends(require_admin)):
    o = await db.orders.find_one({"$or": [{"id": order_id}, {"order_number": order_id}]}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Поръчката не е намерена")
    view = _order_view(o)
    handles = [i["product_handle"] for i in view["items"] if i["product_handle"]]
    skus = [i["sku"] for i in view["items"] if i["sku"]]
    prods = await db.products.find(
        {"$or": [{"handle": {"$in": handles}}, {"variants.sku": {"$in": skus}}]}, {"_id": 0}
    ).to_list(50)
    by_handle = {p["handle"]: p for p in prods}
    by_sku = {v.get("sku"): p for p in prods for v in p.get("variants", []) if v.get("sku")}
    for item in view["items"]:
        p = by_handle.get(item["product_handle"]) or by_sku.get(item["sku"])
        item["image"] = (p or {}).get("image", "")
        item["handle"] = (p or {}).get("handle", item["product_handle"])
    email = view["customer"]["email"]
    if email:
        others = await db.orders.count_documents({"$or": [{"customer_email": email}, {"customer_info.email": email}]})
        spent = await db.orders.aggregate([
            {"$match": {"$or": [{"customer_email": email}, {"customer_info.email": email}], "status": {"$ne": "cancelled"}}},
            {"$group": {"_id": None, "sum": {"$sum": "$total_eur"}}},
        ]).to_list(1)
        view["customer"]["orders_count"] = others
        view["customer"]["total_spent"] = round((spent[0]["sum"] if spent else 0) or 0, 2)
    return {"order": view}


@api.post("/admin/orders/{order_id}/fulfill")
async def admin_fulfill_order(order_id: str, user=Depends(require_admin)):
    res = await db.orders.update_one(
        {"id": order_id},
        {"$set": {"fulfillment_status": "fulfilled", "status": "shipped",
                  "fulfilled_at": now_utc(), "updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Поръчката не е намерена")
    await db.audit.insert_one({"id": str(uuid.uuid4()), "actor": user["email"], "action": "fulfill",
                               "order_id": order_id, "at": now_utc()})
    return {"ok": True}


@api.post("/admin/orders/{order_id}/send-invoice")
async def admin_send_invoice(order_id: str, user=Depends(require_admin)):
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Поръчката не е намерена")
    view = _order_view(o)
    if not view["customer"]["email"]:
        raise HTTPException(400, "Поръчката няма имейл адрес")
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    bank = {
        "name": os.environ.get("BANK_NAME", "UniCredit Bulbank"),
        "iban": os.environ.get("BANK_IBAN", "BG18UNCR70001523456789"),
        "bic": os.environ.get("BANK_BIC", "UNCRBGSF"),
        "holder": os.environ.get("BANK_HOLDER", "PurePeptide EOOD"),
        "reference": view["order_number"],
        "amount_eur": view["total_eur"],
    }
    payload = {**o, "customer_email": view["customer"]["email"], "customer_name": view["customer"]["name"],
               "items": [{"title": i["title"], "variant_name": i["variant"], "quantity": i["quantity"],
                          "price_eur": i["price_eur"], "variant_sku": i["sku"]} for i in view["items"]],
               "order_number": view["order_number"], "total_eur": view["total_eur"]}
    try:
        await email_service.send_order_confirmation(payload, bank, (s or {}).get("value", {}))
    except Exception as ex:
        log.exception("Invoice email failed")
        raise HTTPException(502, f"Имейлът не беше изпратен: {ex}")
    return {"ok": True, "sent_to": view["customer"]["email"]}


@api.post("/admin/orders/{order_id}/mark-paid")
async def mark_paid(order_id: str, user=Depends(require_admin)):
    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404)
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"payment_status": "paid", "paid_at": now_utc(), "updated_at": now_utc()}},
    )
    await db.audit.insert_one({
        "id": str(uuid.uuid4()), "actor": user["email"], "action": "mark_paid",
        "order_id": order_id, "at": now_utc(),
    })
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    try:
        await email_service.send_payment_received({k: v for k, v in o.items() if k != "_id"}, (s or {}).get("value", {}))
    except Exception:
        log.exception("Payment email failed")
    return {"ok": True}


class ShipmentIn(BaseModel):
    carrier: str = "speedy"  # speedy | econt
    service: str = "standard"
    parcel_weight_kg: float = 0.5


@api.post("/admin/orders/{order_id}/create-shipment")
async def create_shipment(order_id: str, payload: ShipmentIn, user=Depends(require_admin)):
    """MOCKED Speedy/Econt adapter - generates a fake tracking number until real API keys provided."""
    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404)
    if o.get("payment_status") != "paid":
        raise HTTPException(400, "Поръчката не е платена")
    tracking_id = f"{payload.carrier.upper()}-{uuid.uuid4().hex[:10].upper()}"
    tracking = {
        "carrier": payload.carrier,
        "service": payload.service,
        "tracking_number": tracking_id,
        "tracking_url": (
            f"https://www.speedy.bg/en/track-shipment/{tracking_id}"
            if payload.carrier == "speedy"
            else f"https://www.econt.com/services/track-shipment/{tracking_id}"
        ),
        "weight_kg": payload.parcel_weight_kg,
        "created_at": now_utc(),
        "mocked": True,
    }
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "tracking": tracking,
            "fulfillment_status": "shipped",
            "shipped_at": now_utc(),
            "updated_at": now_utc(),
        }},
    )
    await db.shipments.insert_one({"id": str(uuid.uuid4()), "order_id": order_id, **tracking})
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    try:
        await email_service.send_shipped({k: v for k, v in o.items() if k != "_id"}, tracking, (s or {}).get("value", {}))
    except Exception:
        log.exception("Shipping email failed")
    return {"ok": True, "tracking": tracking}


class TestEmailIn(BaseModel):
    to: EmailStr


@api.post("/admin/email/test")
async def admin_test_email(payload: TestEmailIn, user=Depends(require_admin)):
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    site_settings = (s or {}).get("value", {})
    res = await email_service.send_email(
        payload.to,
        "PurePeptide — тестов имейл",
        "<p>Това е тестов имейл от вашия PurePeptide магазин. Resend работи коректно.</p>",
        site_settings,
    )
    if not res.get("sent"):
        raise HTTPException(400, f"Имейлът не беше изпратен: {res.get('reason')}")
    return res


@api.post("/admin/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user=Depends(require_admin)):
    o = await db.orders.find_one({"id": order_id})
    if not o:
        raise HTTPException(404)
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"payment_status": "cancelled", "fulfillment_status": "cancelled", "updated_at": now_utc()}},
    )
    return {"ok": True}


@api.get("/admin/customers")
async def admin_customers(user=Depends(require_admin)):
    imported = await db.customers.count_documents({})
    if imported:
        docs = await db.customers.find({}, {"_id": 0}).sort("total_spent", -1).to_list(5000)
        return {"customers": docs, "total": imported}
    docs = await db.users.find({"role": "customer"}, {"_id": 0, "password_hash": 0}).to_list(500)
    # attach order counts
    for d in docs:
        d["orders_count"] = await db.orders.count_documents({"customer_id": d["id"]})
    return {"customers": docs, "total": len(docs)}


@api.get("/admin/customers/{email}/orders")
async def admin_customer_orders(email: str, user=Depends(require_admin)):
    docs = await db.orders.find(
        {"$or": [{"customer_email": email.lower()}, {"customer_info.email": email.lower()}]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    spent = sum(d.get("total_eur", 0) for d in docs if d.get("status") != "cancelled")
    return {"orders": docs, "orders_count": len(docs), "total_spent": round(spent, 2)}


@api.patch("/admin/products/{product_id}/active")
async def admin_toggle_product(product_id: str, payload: Dict[str, bool], user=Depends(require_admin)):
    active = bool(payload.get("active", True))
    res = await db.products.update_one({"id": product_id}, {"$set": {"active": active}})
    if res.matched_count == 0:
        raise HTTPException(404, "Продуктът не е намерен")
    return {"ok": True, "active": active}


@api.get("/admin/products")
async def admin_products(user=Depends(require_admin)):
    docs = await db.products.find({}, {"_id": 0}).to_list(500)
    return {"products": docs}


@api.post("/admin/products")
async def admin_create_product(payload: ProductIn, user=Depends(require_admin)):
    if await db.products.find_one({"handle": payload.handle}):
        raise HTTPException(400, "Handle вече съществува")
    doc = {"id": str(uuid.uuid4()), "created_at": now_utc(), **payload.model_dump()}
    if not doc.get("images"):
        doc["images"] = [doc["image"]] if doc.get("image") else []
    await db.products.insert_one(doc.copy())
    doc.pop("_id", None)
    return {"product": doc}


@api.put("/admin/products/{product_id}")
async def admin_update_product(product_id: str, payload: ProductIn, user=Depends(require_admin)):
    res = await db.products.update_one({"id": product_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404)
    return {"ok": True}


@api.delete("/admin/products/{product_id}")
async def admin_delete_product(product_id: str, user=Depends(require_admin)):
    await db.products.delete_one({"id": product_id})
    return {"ok": True}


@api.post("/admin/collections")
async def admin_create_collection(payload: CollectionIn, user=Depends(require_admin)):
    if await db.collections_cat.find_one({"handle": payload.handle}):
        raise HTTPException(400, "Handle вече съществува")
    doc = {"id": str(uuid.uuid4()), "created_at": now_utc(), **payload.model_dump()}
    await db.collections_cat.insert_one(doc.copy())
    doc.pop("_id", None)
    return {"collection": doc}


class SettingsIn(BaseModel):
    value: Dict[str, Any]


@api.get("/admin/settings")
async def admin_get_settings(user=Depends(require_admin)):
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    return {"settings": (s or {}).get("value", DEFAULT_SETTINGS)}


@api.put("/admin/settings")
async def admin_update_settings(payload: SettingsIn, user=Depends(require_admin)):
    await db.settings.update_one(
        {"key": "site"},
        {"$set": {"value": payload.value, "updated_at": now_utc()}},
        upsert=True,
    )
    return {"ok": True}


@api.post("/admin/import/products")
async def admin_import_products(file: UploadFile = File(...), user=Depends(require_admin)):
    """Matrixify-compatible CSV product import. Expected columns:
    Handle, Title, Body HTML, Image Src, Variant SKU, Variant Price, Variant Inventory Qty, Tags, Collection
    """
    raw = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    inserted = 0
    updated = 0
    errors: List[str] = []
    grouped: Dict[str, Dict[str, Any]] = {}
    for i, row in enumerate(reader, start=2):
        try:
            handle = (row.get("Handle") or "").strip()
            if not handle:
                continue
            if handle not in grouped:
                grouped[handle] = {
                    "handle": handle,
                    "title": (row.get("Title") or handle).strip(),
                    "subtitle": "",
                    "description": (row.get("Body HTML") or row.get("Body (HTML)") or "").strip(),
                    "image": (row.get("Image Src") or "").strip(),
                    "images": [],
                    "variants": [],
                    "collections": [c.strip() for c in (row.get("Collection") or "").split(",") if c.strip()],
                    "tags": [t.strip() for t in (row.get("Tags") or "").split(",") if t.strip()],
                    "featured": False,
                }
            img = (row.get("Image Src") or "").strip()
            if img and img not in grouped[handle]["images"]:
                grouped[handle]["images"].append(img)
            sku = (row.get("Variant SKU") or "").strip()
            if sku:
                price = float((row.get("Variant Price") or "0").strip() or 0)
                qty = int(float((row.get("Variant Inventory Qty") or "0").strip() or 0))
                vname = (row.get("Option1 Value") or row.get("Variant Name") or sku).strip()
                grouped[handle]["variants"].append({
                    "name": vname, "price_eur": price, "stock": qty, "sku": sku,
                })
        except Exception as ex:
            errors.append(f"Row {i}: {ex}")

    for handle, doc in grouped.items():
        if not doc["images"] and doc["image"]:
            doc["images"] = [doc["image"]]
        existing = await db.products.find_one({"handle": handle})
        if existing:
            await db.products.update_one({"handle": handle}, {"$set": doc})
            updated += 1
        else:
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = now_utc()
            await db.products.insert_one(doc.copy())
            inserted += 1

    log_doc = {
        "id": str(uuid.uuid4()),
        "type": "products",
        "filename": file.filename,
        "inserted": inserted,
        "updated": updated,
        "errors": errors[:50],
        "at": now_utc(),
        "actor": user["email"],
    }
    await db.imports.insert_one(log_doc.copy())
    log_doc.pop("_id", None)
    return log_doc


MATRIXIFY_STEPS = ["products", "collections", "pages", "articles", "redirects", "discounts", "customers", "orders", "spend"]


async def _run_matrixify(job_id: str, storage_path: str, steps: List[str], skip_images: bool):
    blob, _ = storage.get_object(storage_path)
    work_dir = Path(tempfile.mkdtemp(prefix="matrixify-"))
    xlsx = work_dir / "import.xlsx"
    xlsx.write_bytes(blob)
    cmd = [sys.executable, str(Path(__file__).parent / "matrixify_import.py"),
           "--file", str(xlsx), "--only", ",".join(steps)]
    if skip_images:
        cmd.append("--skip-images")
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(Path(__file__).parent),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    lines: List[str] = []
    assert proc.stdout
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="ignore").rstrip()
        if not line:
            continue
        lines.append(line)
        if len(lines) % 5 == 0:
            await db.import_jobs.update_one({"id": job_id}, {"$set": {"log": lines[-400:]}})
    code = await proc.wait()
    await db.import_jobs.update_one({"id": job_id}, {"$set": {
        "log": lines[-400:],
        "status": "completed" if code == 0 else "failed",
        "exit_code": code,
        "summary": [l.split("INFO ")[-1] for l in lines if "imported:" in l or "backfilled" in l],
        "finished_at": now_utc(),
    }})


@api.post("/admin/import/matrixify")
async def admin_import_matrixify(
    file: UploadFile = File(...),
    steps: str = Form("products,collections"),
    skip_images: bool = Form(False),
    user=Depends(require_admin),
):
    """Full Matrixify .xlsx import — runs in the background and streams progress into an import job."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".xlsx", ".xlsm"):
        raise HTTPException(400, "Качете .xlsx файл (Matrixify Excel експорт)")
    chosen = [s.strip() for s in steps.split(",") if s.strip() in MATRIXIFY_STEPS]
    if not chosen:
        raise HTTPException(400, "Изберете поне един тип данни за импорт")
    if "orders" in chosen and "spend" not in chosen:
        chosen.append("spend")

    data = await file.read()
    if not data:
        raise HTTPException(400, "Файлът е празен")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    result = storage.put_object(
        f"imports/matrixify-{stamp}.xlsx", data,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    storage_path = result.get("path", f"imports/matrixify-{stamp}.xlsx")
    await db.files.insert_one({
        "id": str(uuid.uuid4()),
        "storage_path": storage_path,
        "original_filename": file.filename,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size": len(data),
        "is_deleted": False,
        "created_at": now_utc(),
        "uploaded_by": user["email"],
    })

    job = {
        "id": str(uuid.uuid4()),
        "type": "matrixify",
        "filename": file.filename,
        "storage_path": storage_path,
        "steps": chosen,
        "skip_images": skip_images,
        "status": "running",
        "log": [],
        "summary": [],
        "actor": user["email"],
        "at": now_utc(),
    }
    await db.import_jobs.insert_one(job.copy())
    asyncio.create_task(_run_matrixify(job["id"], storage_path, chosen, skip_images))
    return {"job_id": job["id"], "status": "running", "steps": chosen}


@api.get("/admin/import/jobs")
async def admin_import_jobs(user=Depends(require_admin)):
    docs = await db.import_jobs.find({}, {"_id": 0, "log": 0}).sort("at", -1).to_list(20)
    return {"jobs": docs}


@api.get("/admin/import/jobs/{job_id}")
async def admin_import_job(job_id: str, user=Depends(require_admin)):
    doc = await db.import_jobs.find_one({"id": job_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Задачата не е намерена")
    return {"job": doc}


@api.get("/admin/imports")
async def admin_imports_log(user=Depends(require_admin)):
    docs = await db.imports.find({}, {"_id": 0}).sort("at", -1).limit(50).to_list(50)
    return {"imports": docs}


@api.get("/admin/products/{product_id}")
async def admin_get_product(product_id: str, user=Depends(require_admin)):
    doc = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Продуктът не е намерен")
    return {"product": doc}


@api.put("/admin/collections/{collection_id}")
async def admin_update_collection(collection_id: str, payload: CollectionIn, user=Depends(require_admin)):
    res = await db.collections_cat.update_one({"id": collection_id}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Колекцията не е намерена")
    return {"ok": True}


@api.get("/admin/collections/{handle}/products")
async def admin_collection_products(handle: str, user=Depends(require_admin)):
    col = await db.collections_cat.find_one({"handle": handle}, {"_id": 0})
    if not col:
        raise HTTPException(404, "Колекцията не е намерена")
    q = {} if handle == "all-peptides" else {"collections": handle}
    prods = await db.products.find(q, {"_id": 0}).to_list(500)
    prods = _apply_manual_order(prods, col.get("product_order"))
    return {
        "collection": {"handle": handle, "title": col.get("title", handle)},
        "products": [{
            "handle": p["handle"],
            "title": p["title"],
            "image": p.get("image", ""),
            "active": p.get("active", True),
            "price_eur": min([v.get("price_eur", 0) for v in p.get("variants", [])] or [0]),
        } for p in prods],
    }


@api.put("/admin/collections/{handle}/order")
async def admin_set_collection_order(handle: str, payload: Dict[str, List[str]], user=Depends(require_admin)):
    handles = payload.get("handles") or []
    res = await db.collections_cat.update_one(
        {"handle": handle},
        {"$set": {"product_order": handles, "order_updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Колекцията не е намерена")
    return {"ok": True, "count": len(handles)}


@api.post("/admin/collections/{handle}/order/by-sales")
async def admin_order_by_sales(handle: str, user=Depends(require_admin)):
    """Sort a collection by units sold (best seller first), using order history."""
    col = await db.collections_cat.find_one({"handle": handle}, {"_id": 0})
    if not col:
        raise HTTPException(404, "Колекцията не е намерена")

    sold: Dict[str, int] = {}
    async for o in db.orders.find({"status": {"$ne": "cancelled"}},
                                  {"_id": 0, "items": 1, "line_items": 1}):
        for it in (o.get("items") or []) + (o.get("line_items") or []):
            h = it.get("product_handle")
            if h:
                sold[h] = sold.get(h, 0) + int(it.get("quantity") or 1)

    q = {} if handle == "all-peptides" else {"collections": handle}
    prods = await db.products.find(q, {"_id": 0, "handle": 1, "title": 1}).to_list(500)
    ordered = sorted(prods, key=lambda p: (-sold.get(p["handle"], 0), p.get("title", "")))
    handles = [p["handle"] for p in ordered]
    await db.collections_cat.update_one(
        {"handle": handle},
        {"$set": {"product_order": handles, "order_updated_at": now_utc()}},
    )
    return {
        "ok": True,
        "handles": handles,
        "sold": {p["handle"]: sold.get(p["handle"], 0) for p in ordered},
    }


@api.get("/admin/collections")
async def admin_collections(user=Depends(require_admin)):
    docs = await db.collections_cat.find({}, {"_id": 0}).sort("sort_order", 1).to_list(100)
    return {"collections": docs}


# ---------- Image uploads (Emergent object storage) ----------
@api.post("/admin/upload")
async def admin_upload(file: UploadFile = File(...), user=Depends(require_admin)):
    ext = (file.filename or "img.png").rsplit(".", 1)[-1].lower()
    if ext not in storage.MIME_TYPES:
        raise HTTPException(400, "Неподдържан формат. Позволени: jpg, png, webp, gif, svg")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Файлът е по-голям от 8MB")
    path = f"{storage.APP_NAME}/products/{uuid.uuid4()}.{ext}"
    content_type = storage.MIME_TYPES[ext]
    try:
        result = storage.put_object(path, data, content_type)
    except Exception as ex:
        log.exception("Upload failed")
        raise HTTPException(502, f"Качването се провали: {ex}")
    await db.files.insert_one({
        "id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": now_utc(),
        "uploaded_by": user["email"],
    })
    return {"url": f"/api/files/{result['path']}", "path": result["path"]}


IMAGE_CACHE = Path(__file__).parent / ".image_cache"
IMAGE_CACHE.mkdir(exist_ok=True)


@api.get("/files/{path:path}")
async def serve_file(path: str):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(404, "Файлът не е намерен")
    content_type = record.get("content_type", "application/octet-stream")
    cache_file = IMAGE_CACHE / hashlib.sha1(path.encode()).hexdigest()
    if cache_file.exists():
        data = cache_file.read_bytes()
    else:
        try:
            data, storage_type = storage.get_object(path)
            content_type = record.get("content_type") or storage_type
            cache_file.write_bytes(data)
        except Exception:
            raise HTTPException(404, "Файлът не е намерен")
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ---------- Static pages (editable per locale) ----------
class PageIn(BaseModel):
    title: str = ""
    html: str = ""
    faq_items: List[Dict[str, str]] = []


class PageTranslateIn(BaseModel):
    locales: List[str] = []
    overwrite: bool = False


def _page_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "slug": doc.get("slug"),
        "locale": doc.get("locale"),
        "title": doc.get("title", ""),
        "html": doc.get("html", ""),
        "faq_items": doc.get("faq_items", []),
        "seo_title": doc.get("seo_title", ""),
        "seo_description": doc.get("seo_description", ""),
        "updated_at": doc.get("updated_at"),
    }


def _has_content(doc: Optional[Dict[str, Any]]) -> bool:
    if not doc:
        return False
    return bool(doc.get("title") or doc.get("html") or doc.get("faq_items"))


@api.get("/pages/{slug}")
async def public_page(slug: str, locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    chain = [loc] + [l for l in ("en", "bg") if l != loc]
    for candidate in chain:
        doc = await db.pages.find_one({"slug": slug, "locale": candidate}, {"_id": 0})
        if _has_content(doc):
            out = _page_out(doc)
            out["locale"] = loc
            out["source_locale"] = candidate
            return {"page": out}
    raise HTTPException(404, "Страницата не е намерена")


@api.get("/admin/pages")
async def admin_pages(user=Depends(require_admin)):
    docs = await db.pages.find({}, {"_id": 0}).to_list(500)
    by_slug: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        by_slug.setdefault(d["slug"], {})[d["locale"]] = _has_content(d)
    return {
        "slugs": [
            {"slug": s, "label": PAGE_LABELS.get(s, s), "filled": by_slug.get(s, {})}
            for s in PAGE_SLUGS
        ],
        "locales": LOCALES,
    }


@api.get("/admin/pages/{slug}/{locale}")
async def admin_get_page(slug: str, locale: str, user=Depends(require_admin)):
    if slug not in PAGE_SLUGS:
        raise HTTPException(404, "Непозната страница")
    loc = normalize_locale(locale)
    doc = await db.pages.find_one({"slug": slug, "locale": loc}, {"_id": 0})
    if not doc:
        return {"page": {"slug": slug, "locale": loc, "title": "", "html": "", "faq_items": [], "updated_at": None}}
    return {"page": _page_out(doc)}


@api.put("/admin/pages/{slug}/{locale}")
async def admin_update_page(slug: str, locale: str, payload: PageIn, user=Depends(require_admin)):
    if slug not in PAGE_SLUGS:
        raise HTTPException(404, "Непозната страница")
    loc = normalize_locale(locale)
    items = [{"q": (i.get("q") or ""), "a": (i.get("a") or "")} for i in payload.faq_items]
    await db.pages.update_one(
        {"slug": slug, "locale": loc},
        {
            "$set": {
                "title": payload.title,
                "html": payload.html,
                "faq_items": items,
                "updated_at": now_utc(),
            },
            "$setOnInsert": {"id": str(uuid.uuid4()), "slug": slug, "locale": loc},
        },
        upsert=True,
    )
    doc = await db.pages.find_one({"slug": slug, "locale": loc}, {"_id": 0})
    return {"ok": True, "page": _page_out(doc)}


@api.post("/admin/pages/{slug}/translate")
async def admin_translate_page(slug: str, payload: PageTranslateIn, user=Depends(require_admin)):
    if slug not in PAGE_SLUGS:
        raise HTTPException(404, "Непозната страница")
    source_doc = await db.pages.find_one({"slug": slug, "locale": "bg"}, {"_id": 0})
    if not _has_content(source_doc):
        raise HTTPException(400, "Първо въведете съдържание на български")

    targets = [normalize_locale(l) for l in (payload.locales or LOCALES)]
    targets = [l for l in targets if l != "bg"]
    if not payload.overwrite:
        kept = []
        for loc in targets:
            existing = await db.pages.find_one({"slug": slug, "locale": loc})
            if not _has_content(existing):
                kept.append(loc)
        targets = kept
    if not targets:
        return {"ok": True, "translated": [], "message": "Няма нови езици за превод"}

    source = {"title": source_doc.get("title", ""), "html": source_doc.get("html", "")}
    if source_doc.get("faq_items"):
        source["faq_items"] = source_doc["faq_items"]

    translated: List[str] = []
    failed: List[str] = []
    for chunk_start in range(0, len(targets), 3):
        chunk = targets[chunk_start:chunk_start + 3]
        try:
            result = await ai_translate_page(source, chunk)
        except Exception as ex:
            log.exception("Page translation failed for %s", chunk)
            failed.extend(chunk)
            continue
        for loc, fields in result.items():
            await db.pages.update_one(
                {"slug": slug, "locale": loc},
                {
                    "$set": {
                        "title": fields.get("title", ""),
                        "html": fields.get("html", ""),
                        "faq_items": fields.get("faq_items", []),
                        "updated_at": now_utc(),
                    },
                    "$setOnInsert": {"id": str(uuid.uuid4()), "slug": slug, "locale": loc},
                },
                upsert=True,
            )
            translated.append(loc)
    if not translated and failed:
        raise HTTPException(502, "Преводът се провали")
    return {"ok": True, "translated": translated, "failed": failed}


# ---------- Traffic tracking + analytics ----------
class TrackIn(BaseModel):
    session_id: str
    path: str = "/"
    referrer: str = ""
    locale: str = "bg"


@api.post("/track")
async def track_visit(payload: TrackIn, request: Request):
    if not payload.session_id:
        raise HTTPException(400, "Липсва сесия")
    await db.visits.insert_one({
        "session_id": payload.session_id[:64],
        "path": payload.path[:300],
        "referrer": payload.referrer[:300],
        "locale": normalize_locale(payload.locale),
        "ua": (request.headers.get("user-agent") or "")[:300],
        "ts": now_utc(),
    })
    return {"ok": True}


def _range_bounds(range_key: str, date_from: Optional[str], date_to: Optional[str]):
    """Returns (start, end, prev_start, prev_end, bucket) as tz-aware datetimes."""
    now = datetime.now(timezone.utc)
    if range_key == "custom" and date_from and date_to:
        start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
        bucket = "hour" if (end - start) <= timedelta(days=2) else "day"
    elif range_key == "7d":
        end = now
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        bucket = "day"
    elif range_key == "30d":
        end = now
        start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        bucket = "day"
    else:  # today
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
        bucket = "hour"
    span = end - start
    return start, end, start - span, start, bucket


def _bucket_key(iso: str, bucket: str) -> str:
    return iso[:13] if bucket == "hour" else iso[:10]


async def _period_stats(start: datetime, end: datetime, bucket: str) -> Dict[str, Any]:
    s_iso, e_iso = start.isoformat(), end.isoformat()
    visits = await db.visits.find(
        {"ts": {"$gte": s_iso, "$lt": e_iso}}, {"_id": 0, "session_id": 1, "ts": 1}
    ).to_list(200000)
    orders = await db.orders.find(
        {"created_at": {"$gte": s_iso, "$lt": e_iso}, "status": {"$ne": "cancelled"}},
        {"_id": 0, "created_at": 1, "subtotal_eur": 1, "discount_eur": 1},
    ).to_list(50000)

    sessions = {v["session_id"] for v in visits}
    sales = sum(max((o.get("subtotal_eur") or 0) - (o.get("discount_eur") or 0), 0) for o in orders)

    buckets: Dict[str, Dict[str, float]] = {}
    first_seen: Dict[str, str] = {}
    for v in visits:
        sid = v["session_id"]
        if sid not in first_seen or v["ts"] < first_seen[sid]:
            first_seen[sid] = v["ts"]
    for sid, ts in first_seen.items():
        b = buckets.setdefault(_bucket_key(ts, bucket), {"sessions": 0, "orders": 0, "sales": 0.0})
        b["sessions"] += 1
    for o in orders:
        b = buckets.setdefault(_bucket_key(o["created_at"], bucket), {"sessions": 0, "orders": 0, "sales": 0.0})
        b["orders"] += 1
        b["sales"] += max((o.get("subtotal_eur") or 0) - (o.get("discount_eur") or 0), 0)

    keys: List[str] = []
    cursor = start
    step = timedelta(hours=1) if bucket == "hour" else timedelta(days=1)
    while cursor < end + step:
        keys.append(_bucket_key(cursor.isoformat(), bucket))
        cursor += step
    series = [
        {"t": k, **{m: round(buckets.get(k, {}).get(m, 0), 2) for m in ("sessions", "orders", "sales")}}
        for k in keys
    ]
    return {
        "sessions": len(sessions),
        "orders": len(orders),
        "sales": round(sales, 2),
        "conversion": round(len(orders) / len(sessions) * 100, 2) if sessions else 0.0,
        "series": series,
    }


@api.get("/admin/analytics")
async def admin_analytics(
    range: str = Query("today"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(require_admin),
):
    start, end, prev_start, prev_end, bucket = _range_bounds(range, date_from, date_to)
    current = await _period_stats(start, end, bucket)
    previous = await _period_stats(prev_start, prev_end, bucket)

    live_since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    live = await db.visits.distinct("session_id", {"ts": {"$gte": live_since}})

    def delta(now_v: float, prev_v: float) -> Optional[float]:
        if not prev_v:
            return None
        return round((now_v - prev_v) / prev_v * 100, 1)

    return {
        "range": range,
        "bucket": bucket,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "live": len(live),
        "current": current,
        "previous": previous,
        "deltas": {
            "sessions": delta(current["sessions"], previous["sessions"]),
            "orders": delta(current["orders"], previous["orders"]),
            "sales": delta(current["sales"], previous["sales"]),
            "conversion": delta(current["conversion"], previous["conversion"]),
        },
    }


# ---------- Inventory tracking ----------
class InventoryIn(BaseModel):
    product_id: str
    variant_name: str
    stock: int
    note: str = ""


async def log_inventory(product: Dict[str, Any], variant_name: str, change: int, after: int, reason: str, actor: str = "system"):
    await db.inventory_log.insert_one({
        "id": str(uuid.uuid4()),
        "product_id": product.get("id"),
        "product_title": product.get("title"),
        "handle": product.get("handle"),
        "variant_name": variant_name,
        "change": change,
        "stock_after": after,
        "reason": reason,
        "actor": actor,
        "created_at": now_utc(),
    })


@api.get("/admin/inventory")
async def admin_inventory(user=Depends(require_admin)):
    settings = await db.settings.find_one({"key": "site"}, {"_id": 0})
    threshold = int(((settings or {}).get("value") or {}).get("low_stock_threshold", 5))
    docs = await db.products.find({}, {"_id": 0}).to_list(500)
    items = []
    for p in docs:
        for v in p.get("variants", []):
            stock = int(v.get("stock") or 0)
            items.append({
                "product_id": p["id"],
                "handle": p["handle"],
                "title": p["title"],
                "image": p.get("image", ""),
                "variant_name": v.get("name", ""),
                "sku": v.get("sku", ""),
                "price_eur": v.get("price_eur", 0),
                "stock": stock,
                "active": p.get("active", True),
                "state": "out" if stock <= 0 else ("low" if stock <= threshold else "ok"),
            })
    items.sort(key=lambda x: x["stock"])
    return {
        "items": items,
        "threshold": threshold,
        "out_of_stock": sum(1 for i in items if i["state"] == "out"),
        "low_stock": sum(1 for i in items if i["state"] == "low"),
        "total_units": sum(i["stock"] for i in items),
    }


@api.put("/admin/inventory")
async def admin_set_inventory(payload: InventoryIn, user=Depends(require_admin)):
    product = await db.products.find_one({"id": payload.product_id})
    if not product:
        raise HTTPException(404, "Продуктът не е намерен")
    variant = next((v for v in product.get("variants", []) if v.get("name") == payload.variant_name), None)
    if variant is None:
        raise HTTPException(404, "Вариантът не е намерен")
    before = int(variant.get("stock") or 0)
    new_stock = max(payload.stock, 0)
    await db.products.update_one(
        {"id": payload.product_id, "variants.name": payload.variant_name},
        {"$set": {"variants.$.stock": new_stock}},
    )
    await log_inventory(product, payload.variant_name, new_stock - before, new_stock,
                        payload.note or "Ръчна корекция", user["email"])
    return {"ok": True, "stock": new_stock}


@api.get("/admin/inventory/log")
async def admin_inventory_log(limit: int = 100, user=Depends(require_admin)):
    docs = await db.inventory_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"log": docs}


@api.put("/admin/inventory/threshold")
async def admin_set_threshold(payload: Dict[str, int], user=Depends(require_admin)):
    value = max(int(payload.get("threshold", 5)), 0)
    await db.settings.update_one({"key": "site"}, {"$set": {"value.low_stock_threshold": value}})
    return {"ok": True, "threshold": value}


# ---------- Contact form + Web Push notifications ----------
class ContactIn(BaseModel):
    name: str
    email: str
    phone: str = ""
    message: str
    locale: str = DEFAULT_LOCALE


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushKeys
    expirationTime: Optional[int] = None


async def _admin_subscriptions() -> List[Dict[str, Any]]:
    return await db.push_subscriptions.find({}, {"_id": 0}).to_list(100)


async def notify_admin_push(title: str, body: str, url: str = "/admin/orders", tag: str = "pp"):
    subs = await _admin_subscriptions()
    if not subs:
        return {"sent": [], "gone": [], "failed": []}
    result = await push_service.send_to_subscriptions(subs, {
        "title": title, "body": body, "url": url, "tag": tag,
    })
    for endpoint in result["gone"]:
        await db.push_subscriptions.delete_one({"endpoint": endpoint})
    await db.push_log.insert_one({
        "id": str(uuid.uuid4()), "title": title, "body": body, "url": url,
        "sent": len(result["sent"]), "failed": len(result["failed"]), "gone": len(result["gone"]),
        "at": now_utc(),
    })
    return result


async def notify_admin_push_bg(title: str, body: str, url: str = "/admin/orders", tag: str = "pp"):
    """Fire-and-forget push so a slow push service never delays the API response."""
    async def runner():
        try:
            await asyncio.wait_for(notify_admin_push(title, body, url, tag), timeout=20)
        except Exception:
            log.exception("Background push failed")

    asyncio.create_task(runner())


@api.post("/contact")
async def contact_form(payload: ContactIn, request: Request):
    if not payload.name.strip() or "@" not in payload.email or not payload.message.strip():
        raise HTTPException(400, "Моля попълнете име, валиден имейл и съобщение")

    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip()[:120],
        "email": payload.email.strip().lower()[:160],
        "phone": payload.phone.strip()[:40],
        "message": payload.message.strip()[:4000],
        "locale": normalize_locale(payload.locale),
        "status": "new",
        "ip": (request.headers.get("x-forwarded-for") or "").split(",")[0][:60],
        "created_at": now_utc(),
    }
    await db.contact_messages.insert_one(doc.copy())

    settings = await db.settings.find_one({"key": "site"}, {"_id": 0})
    to = os.environ.get("CONTACT_EMAIL") or os.environ["ADMIN_EMAIL"]
    safe = {k: html_lib.escape(str(v)) for k, v in doc.items()}
    body_html = (
        f"<h2 style='font-family:system-ui'>Ново запитване от сайта</h2>"
        f"<p style='font-family:system-ui'><strong>Име:</strong> {safe['name']}<br>"
        f"<strong>Имейл:</strong> {safe['email']}<br>"
        f"<strong>Телефон:</strong> {safe['phone'] or '—'}<br>"
        f"<strong>Език:</strong> {safe['locale']}</p>"
        f"<p style='font-family:system-ui;white-space:pre-line;background:#f8fafc;padding:14px;border-radius:8px'>{safe['message']}</p>"
    )
    email_ok = True
    try:
        await email_service.send_email(to, f"Ново запитване от {safe['name']}", body_html,
                                       (settings or {}).get("value", {}))
    except Exception as ex:
        email_ok = False
        log.exception("Contact email failed: %s", ex)

    await notify_admin_push_bg(
        "Ново запитване",
        f"{doc['name']} · {doc['phone'] or doc['email']}",
        "/admin/messages",
        f"contact-{doc['id']}",
    )
    return {"ok": True, "email_sent": email_ok}


@api.get("/admin/messages")
async def admin_messages(status: Optional[str] = None, user=Depends(require_admin)):
    q = {"status": status} if status else {}
    docs = await db.contact_messages.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    new_count = await db.contact_messages.count_documents({"status": "new"})
    return {"messages": docs, "new_count": new_count}


@api.patch("/admin/messages/{message_id}")
async def admin_update_message(message_id: str, payload: Dict[str, str], user=Depends(require_admin)):
    status = payload.get("status", "handled")
    res = await db.contact_messages.update_one(
        {"id": message_id}, {"$set": {"status": status, "updated_at": now_utc()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Запитването не е намерено")
    return {"ok": True, "status": status}


@api.get("/push/public-key")
async def push_public_key():
    return {"public_key": os.environ["VAPID_PUBLIC_KEY"]}


@api.post("/push/subscriptions")
async def push_subscribe(payload: PushSubscriptionIn, user=Depends(require_admin)):
    await db.push_subscriptions.update_one(
        {"endpoint": payload.endpoint},
        {
            "$set": {
                "endpoint": payload.endpoint,
                "keys": payload.keys.model_dump(),
                "expiration_time": payload.expirationTime,
                "admin_email": user["email"],
                "updated_at": now_utc(),
            },
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now_utc()},
        },
        upsert=True,
    )
    total = await db.push_subscriptions.count_documents({})
    return {"ok": True, "subscriptions": total}


@api.delete("/push/subscriptions")
async def push_unsubscribe(payload: Dict[str, str], user=Depends(require_admin)):
    await db.push_subscriptions.delete_one({"endpoint": payload.get("endpoint", "")})
    return {"ok": True}


@api.get("/admin/push/status")
async def push_status(user=Depends(require_admin)):
    subs = await db.push_subscriptions.find({}, {"_id": 0, "keys": 0}).to_list(100)
    last = await db.push_log.find({}, {"_id": 0}).sort("at", -1).to_list(10)
    return {"subscriptions": subs, "log": last, "public_key": os.environ["VAPID_PUBLIC_KEY"]}


@api.post("/admin/push/test")
async def push_test(user=Depends(require_admin)):
    result = await notify_admin_push(
        "Тестова нотификация",
        "Push нотификациите за PurePeptide работят.",
        "/admin/orders",
        "pp-test",
    )
    if not result["sent"]:
        raise HTTPException(400, "Няма активни абонаменти за нотификации на това устройство")
    return {"ok": True, "sent": len(result["sent"])}


# ---------- AI translation ----------
@api.post("/admin/translate")
async def admin_translate(payload: TranslateIn, user=Depends(require_admin)):
    coll = db.products if payload.resource == "product" else db.collections_cat
    doc = await coll.find_one({"id": payload.id})
    if not doc:
        raise HTTPException(404, "Ресурсът не е намерен")

    targets = [normalize_locale(l) for l in (payload.locales or LOCALES) if normalize_locale(l) != "bg"]
    existing = doc.get("translations") or {}
    if not payload.overwrite:
        targets = [l for l in targets if not (existing.get(l) or {}).get("title")]
    if not targets:
        return {"ok": True, "translated": [], "message": "Няма нови езици за превод"}

    source = {
        "title": doc.get("title", ""),
        "handle": doc.get("handle", ""),
        "description": doc.get("description", ""),
    }
    if doc.get("subtitle"):
        source["subtitle"] = doc["subtitle"]

    try:
        result = await ai_translate(source, targets, context="PurePeptide research peptides e-commerce")
    except Exception as ex:
        log.exception("Translation failed")
        raise HTTPException(502, f"Преводът се провали: {ex}")

    updates = {}
    for loc, fields in result.items():
        merged = {**(existing.get(loc) or {}), **fields}
        updates[f"translations.{loc}"] = merged
    await coll.update_one({"id": payload.id}, {"$set": updates})
    fresh = await coll.find_one({"id": payload.id}, {"_id": 0})
    return {"ok": True, "translated": list(result.keys()), "resource": fresh}


class BulkTranslateIn(BaseModel):
    resource: str = "product"  # product | collection | all
    locales: List[str] = []
    overwrite: bool = False


async def _translate_one(coll, doc, targets: List[str], overwrite: bool) -> List[str]:
    existing = doc.get("translations") or {}
    todo = [l for l in targets if overwrite or not (existing.get(l) or {}).get("title")]
    if not todo:
        return []
    source = {
        "title": doc.get("title", ""),
        "handle": doc.get("handle", ""),
        "description": doc.get("description", ""),
    }
    if doc.get("subtitle"):
        source["subtitle"] = doc["subtitle"]
    if doc.get("menu_title"):
        source["menu_title"] = doc["menu_title"]
    result = await ai_translate(source, todo, context="PurePeptide research peptides e-commerce")
    updates = {f"translations.{loc}": {**(existing.get(loc) or {}), **fields} for loc, fields in result.items()}
    if updates:
        await coll.update_one({"id": doc["id"]}, {"$set": updates})
    return list(result.keys())


async def _run_bulk_translate(job_id: str, resource: str, targets: List[str], overwrite: bool):
    collections_to_do = []
    if resource in ("product", "all"):
        collections_to_do.append(("product", db.products))
    if resource in ("collection", "all"):
        collections_to_do.append(("collection", db.collections_cat))

    total = 0
    for _, coll in collections_to_do:
        total += await coll.count_documents({})
    await db.translate_jobs.update_one(
        {"id": job_id},
        {"$set": {"status": "running", "total": total, "done": 0, "failed": [], "updated_at": now_utc()}},
    )

    done = 0
    failed: List[str] = []
    for kind, coll in collections_to_do:
        docs = await coll.find({}, {"_id": 0}).to_list(1000)
        for doc in docs:
            try:
                await _translate_one(coll, doc, targets, overwrite)
            except Exception as ex:
                log.error("Bulk translate failed for %s %s: %s", kind, doc.get("handle"), ex)
                failed.append(f"{kind}:{doc.get('handle')}")
            done += 1
            await db.translate_jobs.update_one(
                {"id": job_id},
                {"$set": {"done": done, "failed": failed, "current": doc.get("handle"), "updated_at": now_utc()}},
            )
    await db.translate_jobs.update_one(
        {"id": job_id}, {"$set": {"status": "finished", "current": "", "updated_at": now_utc()}}
    )


@api.post("/admin/translate/bulk")
async def admin_bulk_translate(payload: BulkTranslateIn, user=Depends(require_admin)):
    targets = [normalize_locale(l) for l in (payload.locales or LOCALES) if normalize_locale(l) != "bg"]
    running = await db.translate_jobs.find_one({"status": {"$in": ["queued", "running"]}}, {"_id": 0})
    if running:
        return {"job": running, "message": "Вече има активен превод"}
    job_id = str(uuid.uuid4())
    await db.translate_jobs.insert_one({
        "id": job_id, "status": "queued", "resource": payload.resource, "locales": targets,
        "total": 0, "done": 0, "failed": [], "current": "", "created_at": now_utc(), "updated_at": now_utc(),
        "actor": user["email"],
    })
    asyncio.create_task(_run_bulk_translate(job_id, payload.resource, targets, payload.overwrite))
    return {"job_id": job_id, "status": "queued", "locales": targets}


@api.get("/admin/translate/bulk")
async def admin_bulk_translate_status(user=Depends(require_admin)):
    job = await db.translate_jobs.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    return {"job": job}


# ---------- SEO: sitemap + robots ----------
def _loc_url(locale: str, path: str, routes: Dict[str, Any] = None) -> str:
    cfg = (routes or {}).get(locale) or SITE_ORIGINS[locale]
    return f"{cfg['origin']}{cfg.get('prefix', '')}{path}"


@api.get("/sitemap.xml")
async def sitemap():
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    active = [l for l in LOCALES if (routes.get(l) or {}).get("enabled", True)]
    cols = await db.collections_cat.find({}, {"_id": 0}).to_list(200)
    prods = await db.products.find({}, {"_id": 0}).to_list(500)
    arts = await db.articles.find({}, {"_id": 0}).to_list(200)
    static_pages = ["", "/collections/all-peptides", "/pages/what-are-peptides",
                    "/pages/chemical-analysis", "/pages/faq", "/pages/contacts", "/pages/partners"]

    def handle_for(doc, loc):
        return ((doc.get("translations") or {}).get(loc) or {}).get("handle") or doc.get("handle")

    entries: List[tuple] = []  # (path_per_locale dict, priority)
    for path in static_pages:
        entries.append(({loc: path for loc in active}, "0.9" if path == "" else "0.7"))
    for c in cols:
        entries.append(({loc: f"/collections/{handle_for(c, loc)}" for loc in active}, "0.8"))
    for p in prods:
        entries.append(({loc: f"/products/{handle_for(p, loc)}" for loc in active}, "0.9"))
    for a in arts:
        entries.append(({loc: f"/articles/{handle_for(a, loc)}" for loc in active}, "0.6"))

    today = datetime.now(timezone.utc).date().isoformat()
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for paths, prio in entries:
        alternates = "".join(
            f'<xhtml:link rel="alternate" hreflang="{LOCALE_META[l]["hreflang"]}" href="{_loc_url(l, paths[l], routes)}"/>'
            for l in active
        )
        if "en" in paths:
            alternates += f'<xhtml:link rel="alternate" hreflang="x-default" href="{_loc_url("en", paths["en"], routes)}"/>'
        for loc in active:
            parts.append(
                f"<url><loc>{_loc_url(loc, paths[loc], routes)}</loc><lastmod>{today}</lastmod>"
                f"<changefreq>weekly</changefreq><priority>{prio}</priority>{alternates}</url>"
            )
    parts.append("</urlset>")
    return Response(content="".join(parts), media_type="application/xml")


@api.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin",
        "Disallow: /checkout",
        "Disallow: /cart",
        "Disallow: /account",
        "",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
    ]
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    for origin in dict.fromkeys((routes.get(loc) or SITE_ORIGINS[loc])["origin"] for loc in LOCALES):
        lines.append(f"Sitemap: {origin}/sitemap.xml")
    return "\n".join(lines)


# ---------- Mount + CORS ----------
app.include_router(api)

_origins_env = os.environ.get("CORS_ORIGINS", "*")
if _origins_env.strip() == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins_env.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@api.get("/")
async def root():
    return {"service": "PurePeptide API", "status": "ok"}
