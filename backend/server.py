"""PurePeptide backend - FastAPI + Motor + JWT auth + bank-transfer commerce."""

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import csv
import html as html_lib
import io
import json
import re
import secrets
import sys
import tempfile
import time
import asyncio
import hashlib
import logging
import uuid
import random
from urllib.parse import quote, urlparse, unquote
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from seed_data import COLLECTIONS, PRODUCTS, ARTICLES, DEFAULT_SETTINGS, SEED_VERSION
from translations_seed import COLLECTION_TR, PRODUCT_TR, ARTICLE_TR
from i18n import (
    LOCALES, DEFAULT_LOCALE, LOCALE_META, SITE_ORIGINS,
    normalize_locale, localize_doc, localize_list, ai_translate, ai_translate_chunked, ai_translate_page,
    ai_rewrite_html,
)
from pages_seed import PAGE_SLUGS, PAGE_LABELS, DEFAULT_PAGES, LEGACY_PAGE_ALIASES
import storage
import email_service
from starlette.concurrency import run_in_threadpool

import currency
from links_map import LINK_TARGETS
import email_templates
import push_service
import bank as bank_details

# ---------- App + DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="PurePeptide API")
api = APIRouter(prefix="/api")

JWT_ALG = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes")

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


class DeliverySelection(BaseModel):
    """Pre-checkout selection coming from the NextCart modal (courier, office/locker or address)."""
    provider_key: str = ""
    provider_name: str = ""
    method_key: str = ""
    destination_type: str = ""
    label: str = ""
    price_amount: float = 0.0
    currency: str = "EUR"
    office: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None


class CheckoutIn(BaseModel):
    items: List[CartLine]
    shipping: Address
    customer_email: EmailStr
    customer_name: str
    customer_phone: str
    shipping_method: str = "econt_office"  # econt_office | econt_address | speedy
    payment_method: str = "bank_transfer"  # bank_transfer | cod
    delivery: Optional[DeliverySelection] = None
    notes: Optional[str] = ""
    discount_code: Optional[str] = ""
    terms_accepted: bool = False
    locale: str = "bg"


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
    nav_hidden: bool = False
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
    elif _env_flag("ADMIN_PASSWORD_RESET") and not verify_password(ADMIN_PASSWORD, existing["password_hash"]):
        # opt-in only: a normal deploy/restart must never reset a password changed in the admin panel
        await db.users.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"password_hash": hash_password(ADMIN_PASSWORD)}},
        )
        log.warning("Admin password re-synced from ADMIN_PASSWORD (ADMIN_PASSWORD_RESET=1)")

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


async def backfill_settings():
    """New DEFAULT_SETTINGS keys must reach an existing shop too — seed_catalog stops early once the
    real catalog is imported, so the backfill inside it never ran on production."""
    current = await db.settings.find_one({"key": "site"})
    if not current:
        return
    missing = {k: v for k, v in DEFAULT_SETTINGS.items() if k not in (current.get("value") or {})}
    if missing:
        await db.settings.update_one(
            {"key": "site"}, {"$set": {**{f"value.{k}": v for k, v in missing.items()}, "updated_at": now_utc()}}
        )
        log.info("Settings backfilled: %s", ", ".join(sorted(missing)))


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
    # the imported Shopify slug aliases answered 200 in every locale with Bulgarian copy and
    # duplicated the real page — they are gone for good (owner's decision: hard 404)
    dropped = await db.pages.delete_many({"$or": [{"canonical_slug": {"$nin": [None, ""]}},
                                                  {"slug": {"$in": LEGACY_PAGE_ALIASES}}]})
    if dropped.deleted_count:
        log.info("removed %s duplicate page aliases", dropped.deleted_count)
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
    await db.rotation_log.create_index("handle", unique=True)


async def backfill_rotation_log():
    """Every handle a rotation has ever produced is remembered, so a catalog re-import (which wipes
    `rotations`) cannot hand the same combination out twice."""
    ops = []
    for name, kind in (("products", "products"), ("collections_cat", "collections"),
                       ("articles", "articles"), ("pages", "pages")):
        async for d in db[name].find({"rotations.0": {"$exists": True}}, {"_id": 0, "rotations": 1}):
            for r in d.get("rotations") or []:
                for handle in (r.get("to"), r.get("from")):
                    if handle:
                        ops.append((handle, kind, r.get("locale") or DEFAULT_LOCALE))
    for handle, kind, loc in ops:
        await db.rotation_log.update_one(
            {"handle": handle},
            {"$setOnInsert": {"handle": handle, "kind": kind, "locale": loc, "at": now_utc()}},
            upsert=True)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    await seed_admin()
    await seed_catalog()
    await backfill_settings()
    await seed_pages()
    await backfill_rotation_log()
    try:
        storage.init_storage()
        log.info("Object storage initialized")
    except Exception as ex:
        log.error("Storage init failed: %s", ex)
    import abandoned as _abandoned
    asyncio.create_task(_abandoned.sweeper_loop())
    asyncio.create_task(nextlevel.sync_loop())
    asyncio.create_task(fulfillment.sync_loop())
    asyncio.create_task(wc_api.backfill_wc_ids())
    from restore_headings import restore_headings
    try:
        await restore_headings(db, storage)
    except Exception as ex:
        log.error("Heading restore failed: %s", ex)
    await resume_translate_jobs()
    asyncio.create_task(auto_translate_watch())


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
ALL_COLLECTION = "2all-the-peptides-1"   # live purepeptide.bg handle for "Всички пептиди"
LEGACY_ALL = "all-peptides"


def clean_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    d.pop("_id", None)
    return d


def slim(docs: List[Dict[str, Any]], *fields: str) -> List[Dict[str, Any]]:
    """Drop heavy fields (long HTML, raw translations) from list payloads."""
    drop = set(fields) | {"translations"}
    return [{k: v for k, v in d.items() if k not in drop} for d in docs]


@api.get("/collections")
async def list_collections(locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    docs = await db.collections_cat.find({}, {"_id": 0}).sort("sort_order", 1).to_list(100)
    return {"collections": slim(localize_list(docs, loc), "product_order")}


def _apply_manual_order(prods: List[Dict[str, Any]], order: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Sort products by the manual order saved in the admin; unknown handles keep their position at the end."""
    if not order:
        return prods
    index = {h: i for i, h in enumerate(order)}
    return sorted(prods, key=lambda p: (index.get(p.get("handle"), len(index)), p.get("title", "")))


def published_handle(doc: Dict[str, Any], loc: str) -> str:
    """The handle this document is published under right now for that locale."""
    return ((doc.get("translations") or {}).get(loc) or {}).get("handle") or doc.get("handle") or ""


def retired_handle(doc: Dict[str, Any], loc: str, requested: str) -> bool:
    """A handle that was rotated away must 404 for that locale (delisted URL).

    Once a document has been rotated in a locale it serves exactly ONE url there: the published
    handle. Every earlier code in the chain 404s — otherwise an intermediate rotation
    (…-lrp next to the live …-brk) stays online as a duplicate of the same product.
    """
    rotations = doc.get("rotations") or []
    if any(r.get("locale") == loc and r.get("from") == requested for r in rotations):
        return True
    if any(r.get("locale") == loc for r in rotations):
        return requested != published_handle(doc, loc)
    return False


async def catalog_handle(loc: str = DEFAULT_LOCALE) -> str:
    """The "all peptides" collection handle as it is published right now for this locale."""
    doc = await db.collections_cat.find_one({"$or": [{"link_key": "catalog"}, {"handle": ALL_COLLECTION}]},
                                            {"_id": 0, "handle": 1, "translations": 1})
    if not doc:
        return ALL_COLLECTION
    return ((doc.get("translations") or {}).get(loc) or {}).get("handle") or doc["handle"]


@api.get("/collections/{handle}")
async def get_collection(handle: str, locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    if handle == LEGACY_ALL:
        handle = ALL_COLLECTION
    query = ({"handle": {"$in": [ALL_COLLECTION, LEGACY_ALL]}} if handle == ALL_COLLECTION
             else {"$or": [{"handle": handle}, {f"translations.{loc}.handle": handle}]})
    col = await db.collections_cat.find_one(query, {"_id": 0})
    if not col or retired_handle(col, loc, handle):
        raise HTTPException(404, "Колекцията не е намерена")
    base_handle = col["handle"]
    if base_handle in (ALL_COLLECTION, LEGACY_ALL):
        prods = await db.products.find({"active": {"$ne": False}}, {"_id": 0}).to_list(500)
    else:
        prods = await db.products.find({"collections": base_handle, "active": {"$ne": False}}, {"_id": 0}).to_list(500)
    siblings = await db.collections_cat.find(
        {"handle": {"$nin": [base_handle, ALL_COLLECTION, LEGACY_ALL]}, "nav_hidden": {"$ne": True}}, {"_id": 0}
    ).sort("sort_order", 1).to_list(50)
    prods = _apply_manual_order(prods, col.get("product_order"))
    return {
        "collection": slim([localize_doc(col, loc)], "product_order")[0],
        "products": slim(localize_list(prods, loc), "description"),
        "siblings": slim(localize_list(siblings, loc), "description", "product_order"),
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
        all_col = await db.collections_cat.find_one({"handle": ALL_COLLECTION}, {"_id": 0, "product_order": 1})
        docs = _apply_manual_order(docs, (all_col or {}).get("product_order"))
    return {"products": slim(localize_list(docs[:limit], loc), "description")}


@api.get("/products/{handle}")
async def get_product(handle: str, locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    p = await db.products.find_one(
        {"$or": [{"handle": handle}, {f"translations.{loc}.handle": handle}]}, {"_id": 0}
    )
    if not p or retired_handle(p, loc, handle):
        raise HTTPException(404, "Продуктът не е намерен")
    related = await db.products.find(
        {"handle": {"$ne": p["handle"]}, "collections": {"$in": p.get("collections", [])}},
        {"_id": 0},
    ).limit(8).to_list(8)
    cols = await db.collections_cat.find(
        {"handle": {"$in": p.get("collections", [])}}, {"_id": 0}
    ).to_list(20)
    articles = await db.articles.find(
        {"product_handle": p["handle"], "published": {"$ne": False}}, {"_id": 0}).to_list(5)
    if not articles:
        # internal linking fallback: match the peptide name (e.g. "BPC-157") in article titles
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}(?:-[0-9]{2,4})?", p.get("title", ""))
        tokens = [t for t in tokens if t.lower() not in ("mg", "the", "and")]
        if tokens:
            rx = "|".join(re.escape(t) for t in tokens[:3])
            articles = await db.articles.find(
                {"published": True, "$or": [
                    {"title": {"$regex": rx, "$options": "i"}},
                    {"handle": {"$regex": rx, "$options": "i"}},
                ]},
                {"_id": 0},
            ).to_list(4)
    return {
        "product": localize_doc(p, loc),
        "related": localize_list(related, loc),
        "collections": localize_list(cols, loc),
        "articles": localize_list(articles, loc),
    }


@api.get("/articles")
async def list_articles(locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    # drafts (Published = False in Shopify) stay out of the storefront
    docs = await db.articles.find({"published": {"$ne": False}}, {"_id": 0}).to_list(50)
    return {"articles": slim(localize_list(docs, loc), "body")}


@api.get("/articles/{handle}")
async def get_article(handle: str, locale: str = Query(DEFAULT_LOCALE)):
    """Full article including the body — the list endpoint strips it to stay small."""
    loc = normalize_locale(locale)
    doc = await db.articles.find_one({"handle": handle, "published": {"$ne": False}}, {"_id": 0}) \
        or await db.articles.find_one({f"translations.{loc}.handle": handle}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Статията не е намерена")
    return {"article": localize_doc(doc, loc)}


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


# ---------- Content rotation ----------
ROTATABLE = {"collections": ("collections_cat", "handle"), "products": ("products", "handle"),
             "articles": ("articles", "handle"), "pages": ("pages", "slug")}
URL_RE = re.compile(r"https?://[^\s<>\"'`,;)\]}]+|(?<![\w/])/[a-z0-9\-_%/\u0400-\u04FF]{3,}")


def parse_link_list(text: str) -> List[str]:
    """Split a pasted blob into URLs — newlines, spaces, commas or glued 'https://a...https://b...'."""
    spaced = re.sub(r"(?<!^)(?=https?://)", "\n", text or "")
    out, seen = [], set()
    for raw in URL_RE.findall(spaced):
        url = raw.strip().rstrip(".,;")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def split_url(url: str) -> tuple:
    """(kind, handle) for a storefront URL or path; ('', '') when it is not rotatable."""
    path = urlparse(url).path if "://" in url else url
    parts = [p for p in unquote(path).split("/") if p]
    if len(parts) >= 2 and parts[0] in LOCALES:      # /en/collections/foo
        parts = parts[1:]
    if len(parts) >= 2 and parts[0] in ROTATABLE:
        return parts[0], parts[1]
    return "", ""


def rotation_code(taken: set) -> str:
    while True:
        code = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=3))
        if code not in taken:
            return code


async def _handle_ever_used(kind: str, handle: str) -> bool:
    """True when this exact URL has ever been published anywhere — a rotation must never reuse one."""
    if await db.rotation_log.find_one({"handle": handle}, {"_id": 1}):
        return True
    if kind == "pages":
        return bool(await db.pages.find_one(
            {"$or": [{"slug": handle}, {"pub_slug": handle}, {"rotations.to": handle},
                     {"rotations.from": handle}]}, {"_id": 1}))
    for name in ("products", "collections_cat", "articles"):
        clauses = [{"handle": handle}, {"rotations.to": handle}, {"rotations.from": handle}]
        clauses += [{f"translations.{loc}.handle": handle} for loc in LOCALES]
        if await db[name].find_one({"$or": clauses}, {"_id": 1}):
            return True
    return False


async def next_rotation_handle(kind: str, base: str, doc: Dict[str, Any], loc: str) -> str:
    """A fresh 3-letter code that was never used for ANY url of the shop, logged so a later
    re-import (which wipes `rotations`) cannot hand out the same combination again."""
    taken = {r.get("code") for r in (doc.get("rotations") or [])}
    for _ in range(200):
        candidate = f"{base}-{rotation_code(taken)}"
        taken.add(candidate.rsplit("-", 1)[-1])
        if not await _handle_ever_used(kind, candidate):
            await db.rotation_log.update_one(
                {"handle": candidate},
                {"$setOnInsert": {"handle": candidate, "kind": kind, "locale": loc, "at": now_utc()}},
                upsert=True)
            return candidate
    raise HTTPException(500, f"Няма свободна комбинация за „{base}“")


async def rotate_page(link: Dict[str, Any], handle: str, loc: str, user_email: str) -> Dict[str, Any]:
    """Rotate a static page URL for one locale: /pages/faq -> /pages/faq-xyz.

    The document keeps its `slug` (the admin editor and the page family key stay untouched); the
    published URL lives in `pub_slug`, so a second rotation replaces the 3-letter code instead of
    stacking suffixes."""
    doc = await db.pages.find_one({"locale": loc, "$or": [{"slug": handle}, {"pub_slug": handle}]}, {"_id": 0})
    if not doc:
        doc = await db.pages.find_one({"locale": loc, "rotations.from": handle}, {"_id": 0})
    if not _has_content(doc):
        raise HTTPException(404, f"Няма съдържание за страница „{handle}“ на език {loc}")

    rotations = list(doc.get("rotations") or [])
    base = rotations[0]["from"] if rotations else (doc.get("pub_slug") or doc["slug"])
    new_slug = await next_rotation_handle("pages", base, doc, loc)

    rewritten = False
    html = doc.get("html") or ""
    if len(html) > 40:
        try:
            html = await ai_rewrite_html(html, loc, context=f"страница „{doc.get('title') or base}“ — ротация на съдържание")
            rewritten = True
        except Exception as exc:
            log.warning("rotation rewrite failed for page %s: %s", handle, exc)

    rotations.append({"locale": loc, "from": doc.get("pub_slug") or doc["slug"], "to": new_slug,
                      "code": new_slug.split("-")[-1], "rewritten": rewritten, "at": now_utc(), "by": user_email})
    update = {"pub_slug": new_slug, "rotations": rotations, "updated_at": now_utc()}
    if rewritten:
        update["html"] = html
    await db.pages.update_one({"slug": doc["slug"], "locale": loc}, {"$set": update})
    _links_cache.clear()
    return {"kind": "pages", "handle": new_slug, "path": f"/pages/{new_slug}", "rewritten": rewritten}


async def rotate_content(kind: str, handle: str, loc: str, user_email: str, to: str = "") -> Dict[str, Any]:
    """`to` republishes an exact handle (restoring a rotation a catalog re-import wiped) and then
    leaves the copy alone — the AI rewrite is only for a genuinely new rotation."""
    coll = db[ROTATABLE[kind][0]]
    doc = await coll.find_one({"$or": [{"handle": handle}, {f"translations.{loc}.handle": handle}]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Няма съдържание с handle „{handle}“")

    tr = dict(doc.get("translations") or {})
    entry = dict(tr.get(loc) or {})
    history = [r for r in (doc.get("rotations") or []) if r.get("locale") == loc]
    base = history[0]["from"] if history else (entry.get("handle") or doc["handle"])
    new_handle = to.strip() or await next_rotation_handle(kind, base, doc, loc)
    if new_handle == handle:
        raise HTTPException(400, "Новият handle е същият като стария")
    entry["handle"] = new_handle

    rewritten = False
    source_html = entry.get("description") or (doc.get("description") if loc == DEFAULT_LOCALE else "")
    if not to and source_html and len(source_html) > 40:
        try:
            entry["description"] = await ai_rewrite_html(
                source_html, loc, context=f"{kind} „{entry.get('title') or doc.get('title')}“ — ротация на съдържание")
            rewritten = True
        except Exception as exc:            # a failed rewrite must not block the URL rotation
            log.warning("rotation rewrite failed for %s: %s", handle, exc)
    tr[loc] = entry

    # the entry retires the handle that WAS published (not the delisted url the board still shows),
    # so a second rotation cannot leave the previous code online
    previous = published_handle(doc, loc) or handle
    rotations = [r for r in (doc.get("rotations") or [])
                 if not (r.get("locale") == loc and r.get("from") == previous)]
    rotations.append({"locale": loc, "from": previous, "to": new_handle, "code": new_handle.split("-")[-1],
                      "rewritten": rewritten, "at": now_utc(), "by": user_email})
    await coll.update_one({"handle": doc["handle"]}, {"$set": {"translations": tr, "rotations": rotations,
                                                              "updated_at": now_utc()}})
    _links_cache.clear()
    return {"kind": kind, "handle": new_handle, "path": f"/{kind}/{new_handle}", "rewritten": rewritten}


async def rotate_one(link: Dict[str, Any], user_email: str, to: str = "") -> Dict[str, Any]:
    kind, handle = split_url(link["url"])
    if not kind:
        raise HTTPException(400, f"Не мога да ротирам този URL: {link['url']}")
    loc = normalize_locale(link.get("locale") or DEFAULT_LOCALE)
    res = (await rotate_page(link, handle, loc, user_email) if kind == "pages"
           else await rotate_content(kind, handle, loc, user_email, to=to))

    site = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((site or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    new_url = _loc_url(loc, res["path"], routes)
    await db.delisted_links.update_one({"id": link["id"]}, {"$set": {
        "status": "rotated", "replacement_url": new_url, "rotated_at": now_utc(),
        "rewritten": res["rewritten"], "notes": (link.get("notes") or "").strip(),
    }})
    return {"id": link["id"], "url": link["url"], "new_url": new_url, "handle": res["handle"],
            "locale": loc, "kind": kind, "rewritten": res["rewritten"]}


class BulkLinksIn(BaseModel):
    text: str
    locale: str = "bg"
    reason: str = ""


@api.post("/admin/delisted-links/bulk")
async def create_delisted_links_bulk(payload: BulkLinksIn, user=Depends(require_admin)):
    """Paste as many links as you want — one per line, comma separated or glued together."""
    urls = parse_link_list(payload.text)
    if not urls:
        raise HTTPException(400, "Не разпознах нито един линк в текста")
    existing = {d["url"] for d in await db.delisted_links.find({"url": {"$in": urls}}, {"_id": 0, "url": 1}).to_list(1000)}
    docs = [{"id": str(uuid.uuid4()), "url": u, "locale": normalize_locale(payload.locale),
             "reason": payload.reason, "status": "pending", "replacement_url": "", "notes": "",
             "created_at": now_utc(), "updated_at": now_utc(), "created_by": user["email"]}
            for u in urls if u not in existing]
    if docs:
        await db.delisted_links.insert_many(docs)
    return {"added": len(docs), "skipped": len(urls) - len(docs),
            "links": [{k: v for k, v in d.items() if k != "_id"} for d in docs]}


@api.post("/admin/delisted-links/{link_id}/rotate")
async def rotate_delisted_link(link_id: str, to: str = "", user=Depends(require_admin)):
    """`?to=` republishes an exact handle — used to restore a rotation a re-import overwrote."""
    link = await db.delisted_links.find_one({"id": link_id}, {"_id": 0})
    if not link:
        raise HTTPException(404, "Линкът не е намерен")
    return {"rotated": await rotate_one(link, user["email"], to=to)}


@api.post("/admin/delisted-links/rotate-pending")
async def rotate_pending_links(user=Depends(require_admin)):
    links = await db.delisted_links.find({"status": "pending"}, {"_id": 0}).to_list(200)
    done, failed = [], []
    gate = asyncio.Semaphore(3)   # the AI rewrites are the slow part — run a few in parallel

    async def run(link):
        async with gate:
            try:
                done.append(await rotate_one(link, user["email"]))
            except HTTPException as exc:
                failed.append({"url": link["url"], "error": exc.detail})
            except Exception as exc:
                failed.append({"url": link["url"], "error": str(exc)})

    await asyncio.gather(*(run(l) for l in links))
    return {"rotated": done, "failed": failed}


@api.get("/settings")
async def get_settings(locale: str = Query(DEFAULT_LOCALE)):
    from nextcart import shipping_summary
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    value = dict(s["value"]) if s else dict(DEFAULT_SETTINGS)
    for secret in ("resend_api_key", "discount_codes"):
        value.pop(secret, None)
    # Google's merchant listings want the delivery and return terms inside the product offer
    value["shipping"] = await shipping_summary(normalize_locale(locale))
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


@api.get("/currency")
async def currency_for(locale: str = DEFAULT_LOCALE):
    """Which currency (and daily ECB rate) the given storefront is priced in."""
    return await currency.rate_for_locale(db, normalize_locale(locale))


def _calc_totals(line_items: List[Dict[str, Any]], shipping_method: str, discount_eur: float = 0.0,
                 shipping_override: Optional[float] = None) -> Dict[str, float]:
    subtotal = sum(li["price_eur"] * li["quantity"] for li in line_items)
    if shipping_override is not None:
        shipping_cost = round(float(shipping_override), 2)  # courier price chosen at checkout wins
    else:
        shipping_cost = 5.99 if shipping_method != "speedy" else 7.49  # no free-shipping threshold
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
        # the SKU is the stable key — a re-import gives products new ids, so a cart saved in the
        # browser before the import must still check out
        prod = (await db.products.find_one({"id": li.product_id}, {"_id": 0})
                or await db.products.find_one({"variants.sku": li.variant_sku}, {"_id": 0}))
        if not prod:
            raise HTTPException(400, f"Продуктът вече не се предлага (SKU {li.variant_sku}) — премахнете го от количката")
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
    shipping_override = None
    if payload.delivery:
        from nextcart import resolve_delivery
        iso = (payload.shipping.country or "").upper()
        check = await resolve_delivery(iso, payload.delivery.provider_key,
                                       payload.delivery.method_key, payload.delivery.destination_type)
        if not check["ok"]:
            log.warning("checkout rejected: %s %s is not offered for %s",
                        payload.delivery.provider_key, payload.delivery.method_key, iso)
            raise HTTPException(400, "Изберете отново начина на доставка за тази държава")
        fixed = check.get("method")
        if fixed:
            # a courier left over from another country — swap it for the one that serves this one
            log.warning("checkout: %s -> %s for %s (order rewritten)",
                        payload.delivery.method_key, fixed.get("key"), iso)
            payload.delivery.provider_key = fixed.get("provider_key") or ""
            payload.delivery.provider_name = fixed.get("provider_name") or payload.delivery.provider_name
            payload.delivery.method_key = fixed.get("key") or payload.delivery.method_key
            payload.delivery.label = fixed.get("label") or payload.delivery.label
            payload.shipping_method = payload.delivery.method_key
            if fixed.get("destination_type"):
                payload.delivery.destination_type = fixed["destination_type"]
            if payload.delivery.destination_type == "address":
                payload.delivery.office = None      # an office of the old courier means nothing now
        shipping_override = check["price"]
        if shipping_override is None:
            shipping_override = payload.delivery.price_amount
        payload.delivery.price_amount = shipping_override
    user = await get_user_from_request(request)
    # some markets are prepaid only (Spain) — the client must not be able to send COD
    from nextcart import cod_allowed
    pay_method = payload.payment_method if payload.payment_method in ("bank_transfer", "cod") else "bank_transfer"
    if pay_method == "cod" and not cod_allowed((payload.shipping.country or "").upper()):
        pay_method = "bank_transfer"
    totals = _calc_totals(line_items, payload.shipping_method, discount.get("discount_eur", 0.0), shipping_override)
    loc = (payload.locale or "bg").lower()
    fx = await currency.rate_for_locale(db, loc)
    local = currency.order_amounts(line_items, totals, discount, fx["currency"], fx["rate"])
    for li, price in zip(line_items, local.pop("item_prices", [])):
        li["price_orig"] = price

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
        "delivery": payload.delivery.model_dump() if payload.delivery else None,
        "notes": payload.notes,
        "discount": discount,
        "terms_accepted": payload.terms_accepted,
        "locale": loc,
        **totals,
        **local,
        "payment_status": "awaiting_payment",
        "fulfillment_status": "unfulfilled",
        "payment_method": pay_method,
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
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    site_settings = (s or {}).get("value", {})
    bank = bank_details.from_settings(site_settings, order["order_number"], totals["total_eur"])
    order_clean = {k: v for k, v in order.items() if k != "_id"}
    await db.orders.update_one({"id": order["id"]}, {"$set": {"wc_id": wc_api.wc_int(order["id"])}})
    asyncio.create_task(fulfillment.dispatch_new_order(order["id"]))
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
            "Нова поръчка {} · {}".format(order["order_number"], email_templates._money(
                local.get("total_orig", totals["total_eur"]), order["currency"])),
            "{} · {}".format(order.get("customer_name") or "", items_summary),
            "/admin/orders/{}".format(order["id"]),
            "order-{}".format(order["id"]),
        )
    except Exception:
        log.exception("Order push notification failed")
    try:
        admin_to = os.environ.get("CONTACT_EMAIL") or os.environ["ADMIN_EMAIL"]
        if email_service.is_test_address(order["customer_email"]):
            log.info("test order %s — admin notification skipped", order["order_number"])
        else:
            admin_subject, admin_html = email_templates.render_admin_order(order_clean)
            await email_service.send_email(admin_to, admin_subject, admin_html, site_settings)
    except Exception:
        log.exception("Admin order email failed")
    try:
        await abandoned.mark_recovered(order["customer_email"])
    except Exception:
        log.exception("Abandoned cart cleanup failed")

    return {"order": order_clean, "bank_transfer": bank}


async def _bank_block(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bank details belong to the confirmation only — the checkout no longer shows them."""
    if (order.get("payment_method") or "bank_transfer") != "bank_transfer":
        return None
    if order.get("status") == "cancelled" or order.get("payment_status") == "paid":
        return None
    return await bank_details.details(db, order.get("order_number", ""), order.get("total_eur", 0.0))


@api.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Поръчката не е намерена")
    user = await get_user_from_request(request)
    blocker = cancel_blocker(o)
    o["cancellable"] = not blocker
    o["cancel_blocker"] = blocker
    bank = await _bank_block(o)
    is_owner = user and (user.get("role") == "admin" or o.get("customer_id") == user.get("id"))
    if not is_owner:
        # allow guest lookup by id (acts as token) for confirmation page
        if o.get("shipment"):
            o["shipment"] = {k: v for k, v in o["shipment"].items() if k != "payload"}
        return {"order": o, "bank_transfer": bank, "guest_view": True}
    return {"order": o, "bank_transfer": bank}


@api.get("/me/orders")
async def my_orders(user=Depends(require_user)):
    docs = await db.orders.find({"customer_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for d in docs:
        d["cancellable"] = not cancel_blocker(d)
    return {"orders": docs}


class TrackIn(BaseModel):
    order_number: str = Field(min_length=3, max_length=32)
    phone: str = Field(min_length=5, max_length=32)


_track_hits: Dict[str, List[float]] = {}


def _only_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _track_view(o: Dict[str, Any]) -> Dict[str, Any]:
    """What a guest may see: status, courier, waybill, items — no e-mail, no full address of others."""
    delivery = o.get("delivery") or {}
    office = delivery.get("office") or {}
    ship = o.get("shipping") or {}
    info = o.get("customer_info") or {}
    shipment = o.get("shipment") or {}
    cancelled = o.get("status") == "cancelled" or o.get("fulfillment_status") == "cancelled"
    ff_status = str((o.get("fulfillment") or {}).get("status") or "").lower()
    delivered = ff_status == "delivered" or str(shipment.get("status") or "").lower() == "delivered"
    return {
        "order_number": o.get("order_number"),
        "created_at": o.get("created_at"),
        "currency": str(o.get("currency") or "EUR").upper(),
        "total_eur": round(float(o.get("total_eur") or 0), 2),
        "total_display": float(o.get("total_orig") if o.get("total_orig") is not None else (o.get("total_eur") or 0)),
        "payment_method": o.get("payment_method") or "bank_transfer",
        "payment_status": o.get("payment_status") or "awaiting_payment",
        "fulfillment_status": "cancelled" if cancelled else (o.get("fulfillment_status") or "unfulfilled"),
        "steps": {
            "placed": True,
            "paid": o.get("payment_status") == "paid" or (o.get("payment_method") == "cod" and bool(shipment.get("awb"))),
            "shipped": bool(shipment.get("awb")) or o.get("fulfillment_status") in ("shipped", "fulfilled"),
            "delivered": delivered,
        },
        "cancelled": cancelled,
        "items": [{"title": i.get("title", ""), "variant": i.get("variant_name") or "",
                   "quantity": int(i.get("quantity") or 1),
                   "price_display": float(i.get("price_orig") if i.get("price_orig") is not None else (i.get("price_eur") or 0))}
                  for i in (o.get("items") or o.get("line_items") or [])],
        "delivery": {
            "label": delivery.get("label") or o.get("shipping_method") or "",
            "courier": delivery.get("provider_name") or "",
            "office_name": office.get("name") or "",
            "office_address": office.get("address") or "",
            "line1": ship.get("line1") or info.get("address") or "",
            "city": ship.get("city") or info.get("city") or "",
            "postal_code": ship.get("postal_code") or info.get("postcode") or "",
            "country": ship.get("country") or info.get("country") or "",
        },
        "shipment": {
            "awb": shipment.get("awb") or "",
            "courier": shipment.get("courier") or "",
            "status": shipment.get("status") or "",
            "tracking_link": shipment.get("tracking_link") or (o.get("tracking") or {}).get("tracking_url") or "",
        } if shipment.get("awb") else None,
    }


@api.post("/orders/track")
async def track_order(payload: TrackIn, request: Request):
    """Public order tracking: order number + the phone the order was placed with."""
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    hits = [t for t in _track_hits.get(ip, []) if time.time() - t < 600]
    if len(hits) >= 15:
        raise HTTPException(429, "Твърде много опити. Опитайте пак след няколко минути.")
    _track_hits[ip] = hits + [time.time()]

    number = payload.order_number.strip().upper().lstrip("#")
    given = _only_digits(payload.phone)[-8:]
    o = await db.orders.find_one({"order_number": number}, {"_id": 0})
    stored = [_only_digits(o.get("customer_phone")),
              _only_digits((o.get("shipping") or {}).get("phone")),
              _only_digits((o.get("customer_info") or {}).get("phone"))] if o else []
    if not o or len(given) < 6 or not any(s.endswith(given) for s in stored if s):
        raise HTTPException(404, "Не намерихме поръчка с този номер и телефон")

    if (o.get("fulfillment") or {}).get("payload") and not (o.get("shipment") or {}).get("status") == "Delivered":
        try:
            await fulfillment.refresh_order(o["id"])
            o = await db.orders.find_one({"id": o["id"]}, {"_id": 0}) or o
        except Exception as exc:  # live status is a bonus, never a blocker
            log.info("tracking refresh for %s skipped: %s", number, exc)
    return {"order": _track_view(o)}



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
    cur = str(o.get("currency") or "EUR").upper()
    fx = float(o.get("currency_rate") or (1.0 if cur == "EUR" else 1.0))
    items = [{
        "title": it.get("title", ""),
        "variant": it.get("variant_name") or it.get("variant") or "",
        "sku": it.get("variant_sku") or it.get("sku") or "",
        "quantity": int(it.get("quantity") or 1),
        "price_eur": float(it.get("price_eur") or 0),
        "price_display": float(it.get("price_orig") if it.get("price_orig") is not None else (it.get("price_eur") or 0)),
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
        "subtotal_display": round(float(o.get("subtotal_orig") if o.get("subtotal_orig") is not None else (o.get("subtotal_eur") or 0)), 2),
        "discount_display": round(float(o.get("discount_orig") if o.get("discount_orig") is not None else (o.get("discount_eur") or 0)), 2),
        "shipping_display": round(float(o.get("shipping_orig") if o.get("shipping_orig") is not None else (o.get("shipping_eur") or 0)), 2),
        "total_display": round(float(o.get("total_orig") if o.get("total_orig") is not None else (o.get("total_eur") or 0)), 2),
        "currency_rate": fx,
        "payment_status": o.get("payment_status") or "awaiting_payment",
        "fulfillment_status": fulfillment,
        "shipping_method": o.get("shipping_method") or (tracking or {}).get("carrier") or "",
        "payment_method": o.get("payment_method") or "",
        "tracking": tracking,
        "shipment": o.get("shipment"),
        "shipment_error": o.get("shipment_error"),
        "fulfillment": o.get("fulfillment"),
        "fulfillment_error": o.get("fulfillment_error"),
        "wc_id": o.get("wc_id"),
        "note": o.get("notes") or o.get("note") or "",
        "source": o.get("source") or "storefront",
        "currency": cur,
        "delivery": o.get("delivery"),
        "discount_code": o.get("discount_code") or "",
        "cancellable": not cancel_blocker(o),
        "cancel_blocker": cancel_blocker(o),
        "cancelled_at": o.get("cancelled_at"),
        "cancelled_by": o.get("cancelled_by"),
        "cancel_reason": o.get("cancel_reason") or "",
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
    bank = bank_details.from_settings((s or {}).get("value"), view["order_number"], view["total_eur"])
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
    asyncio.create_task(fulfillment.on_paid(order_id))
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
        email_templates.render_admin_note(
            "ТЕСТ", "Resend работи коректно",
            "Това е тестов имейл от вашия PurePeptide магазин. Ако го виждате, транзакционните "
            "имейли (потвърждение на поръчка, изоставена количка и известия към администратора) "
            "ще се доставят коректно."),
        site_settings,
    )
    if not res.get("sent"):
        raise HTTPException(400, f"Имейлът не беше изпратен: {res.get('reason')}")
    return res


CANCEL_LOCKED = ("fulfilled", "shipped", "delivered")


def cancel_blocker(o: Dict[str, Any]) -> str:
    """Empty string when the order may still be cancelled, otherwise the reason it may not."""
    if o.get("status") == "cancelled" or o.get("payment_status") == "cancelled":
        return "Поръчката вече е отказана"
    if (o.get("fulfillment_status") or "") in CANCEL_LOCKED or o.get("status") in CANCEL_LOCKED:
        return "Поръчката вече е изпратена — свържете се с нас за връщане"
    return ""


async def perform_cancel(o: Dict[str, Any], by: str, reason: str = "",
                         notify_courier: bool = True, force: bool = False) -> Dict[str, Any]:
    """Cancel at the courier, put the stock back, mark the order cancelled and notify both sides.

    The warehouse comes first: if NextLevel does not confirm the cancellation, nothing is changed
    here (owner's rule — an order must never be "cancelled" in the shop while the warehouse still
    ships it). `force=True` is the admin's escape hatch, `notify_courier=False` is used when the
    cancellation came FROM the warehouse.
    """
    blocker = cancel_blocker(o)
    if blocker:
        raise HTTPException(400, blocker)

    courier: Dict[str, Any] = {}
    if notify_courier and (o.get("fulfillment") or {}).get("number"):
        try:
            courier["fulfillment"] = await fulfillment.cancel_order(o["id"])
        except HTTPException as exc:
            log.warning("fulfillment cancel failed for %s: %s", o.get("order_number"), exc.detail)
            if not force:
                raise HTTPException(exc.status_code, f"Складът на NextLevel не потвърди отказа: {exc.detail}. "
                                                     "Поръчката НЕ е отказана, за да не остане активна в склада — "
                                                     "опитайте пак или я откажете от панела на NextLevel.")
            courier["fulfillment_error"] = str(exc.detail)
        except Exception as exc:
            log.warning("fulfillment cancel crashed for %s: %s", o.get("order_number"), exc)
            if not force:
                raise HTTPException(502, f"Складът на NextLevel не потвърди отказа: {exc}. Поръчката НЕ е отказана.")
            courier["fulfillment_error"] = str(exc)
    if notify_courier and (o.get("shipment") or {}).get("awb"):
        try:
            courier["shipment"] = await nextlevel.cancel_shipment(o["id"])
        except Exception as exc:
            courier["shipment_error"] = str(exc)
            log.warning("shipment cancel failed for %s: %s", o.get("order_number"), exc)
            if not force:
                raise HTTPException(502, f"Товарителницата не беше анулирана: {exc}. Поръчката НЕ е отказана.")

    for li in o.get("items") or []:
        await db.products.update_one(
            {"id": li["product_id"], "variants.sku": li["variant_sku"]},
            {"$inc": {"variants.$.stock": li["quantity"]}},
        )
        product = await db.products.find_one({"id": li["product_id"]}, {"_id": 0})
        if product:
            variant = next((v for v in product.get("variants", []) if v.get("sku") == li["variant_sku"]), {})
            await log_inventory(product, variant.get("name", li.get("variant_name", "")),
                                li["quantity"], int(variant.get("stock") or 0),
                                f"Отказана поръчка {o['order_number']}", by)

    await db.orders.update_one({"id": o["id"]}, {"$set": {
        "status": "cancelled", "payment_status": "cancelled", "fulfillment_status": "cancelled",
        "cancelled_at": now_utc(), "cancelled_by": by, "cancel_reason": reason, "updated_at": now_utc(),
    }})

    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    site_settings = (s or {}).get("value", {})
    if o.get("customer_email"):
        try:
            await email_service.send_order_cancelled(o, site_settings, reason)
        except Exception:
            log.exception("cancellation email failed")
    try:
        await email_service.send_email(
            os.environ.get("CONTACT_EMAIL") or ADMIN_EMAIL,
            f"Отказана поръчка {o['order_number']} — PurePeptide",
            email_templates.render_admin_note(
                "ОТКАЗАНА", f"Поръчка {o['order_number']} е отказана",
                f"Отказана от: {by}<br>Причина: {reason or '—'}<br>"
                f"Сума: {o.get('total_display') or o.get('total_eur')} {o.get('currency') or 'EUR'}<br>"
                f"Наличностите са върнати автоматично."),
            site_settings,
        )
    except Exception:
        log.exception("admin cancellation email failed")

    return {"ok": True, "courier": courier}


class CancelIn(BaseModel):
    reason: str = ""


@api.post("/orders/{order_id}/cancel")
async def cancel_own_order(order_id: str, payload: CancelIn, request: Request):
    """A customer may cancel while the parcel has not been shipped yet."""
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Поръчката не е намерена")
    user = await get_user_from_request(request)
    if user and user.get("role") == "admin":
        by = f"админ {user['email']}"
    elif user and o.get("customer_id") == user.get("id"):
        by = f"клиент {user.get('email')}"
    else:
        by = "клиент (без профил)"
    return await perform_cancel(o, by, payload.reason.strip()[:300])


@api.post("/admin/orders/{order_id}/cancel")
async def cancel_order(order_id: str, payload: CancelIn = CancelIn(), force: bool = False,
                       user=Depends(require_admin)):
    """`force=true` cancels in the shop even if NextLevel refused — only the admin may do that."""
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(404, "Поръчката не е намерена")
    return await perform_cancel(o, f"админ {user['email']}", payload.reason.strip()[:300], force=force)


async def _cancel_from_warehouse(order_id: str, by: str) -> None:
    """NextLevel cancelled the order in their panel → mirror it here (stock back + e-mails)."""
    o = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not o or o.get("status") == "cancelled":
        return
    await perform_cancel(o, by, "Отказана от склада на NextLevel", notify_courier=False)


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
    # an image pasted as a link is downloaded into our storage, never hot-linked
    fields = await adopt_external_images(payload.model_dump())
    doc = {"id": str(uuid.uuid4()), "created_at": now_utc(), **fields}
    if not doc.get("images"):
        doc["images"] = [doc["image"]] if doc.get("image") else []
    await db.products.insert_one(doc.copy())
    doc.pop("_id", None)
    return {"product": doc}


@api.put("/admin/products/{product_id}")
async def admin_update_product(product_id: str, payload: ProductIn, user=Depends(require_admin)):
    fields = await adopt_external_images(payload.model_dump())
    res = await db.products.update_one({"id": product_id}, {"$set": fields})
    if res.matched_count == 0:
        raise HTTPException(404)
    return {"ok": True}


@api.delete("/admin/products/{product_id}")
async def admin_delete_product(product_id: str, user=Depends(require_admin)):
    await db.products.delete_one({"id": product_id})
    return {"ok": True}


class ArticlePatch(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    image: Optional[str] = None
    body: Optional[str] = None
    author: Optional[str] = None
    product_handle: Optional[str] = None
    published: Optional[bool] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


@api.get("/admin/articles")
async def admin_articles(user=Depends(require_admin)):
    docs = await db.articles.find({}, {"_id": 0, "translations": 0}).sort("published_at", -1).to_list(200)
    return {"articles": docs}


@api.patch("/admin/articles/{handle}")
async def admin_update_article(handle: str, payload: ArticlePatch, user=Depends(require_admin)):
    """Only the fields actually sent are written — the Bulgarian source stays untouched otherwise."""
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "Няма промени")
    changes = await adopt_external_images(changes)
    changes["updated_at"] = now_utc()
    res = await db.articles.update_one({"handle": handle}, {"$set": changes})
    if res.matched_count == 0:
        raise HTTPException(404, "Статията не е намерена")
    doc = await db.articles.find_one({"handle": handle}, {"_id": 0, "translations": 0})
    return {"article": doc}


@api.post("/admin/collections")
async def admin_create_collection(payload: CollectionIn, user=Depends(require_admin)):
    if await db.collections_cat.find_one({"handle": payload.handle}):
        raise HTTPException(400, "Handle вече съществува")
    doc = {"id": str(uuid.uuid4()), "created_at": now_utc(), **await adopt_external_images(payload.model_dump())}
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
        {"$set": {"value": await adopt_external_images(payload.value), "updated_at": now_utc()}},
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
    res = await db.collections_cat.update_one({"id": collection_id},
                                              {"$set": await adopt_external_images(payload.model_dump())})
    if res.matched_count == 0:
        raise HTTPException(404, "Колекцията не е намерена")
    _links_cache.clear()
    return {"ok": True}


@api.get("/admin/collections/{handle}/products")
async def admin_collection_products(handle: str, user=Depends(require_admin)):
    col = await db.collections_cat.find_one({"handle": handle}, {"_id": 0})
    if not col:
        raise HTTPException(404, "Колекцията не е намерена")
    q = {} if handle == ALL_COLLECTION else {"collections": handle}
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

    q = {} if handle == ALL_COLLECTION else {"collections": handle}
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


ALLOWED_WIDTHS = {160, 300, 480, 600, 900, 1200}


def _image_variant(data: bytes, width: int, fmt: str, cache_file: Path) -> bytes:
    """Resize + convert to WebP/JPEG once, then serve from disk cache."""
    if cache_file.exists():
        return cache_file.read_bytes()
    from io import BytesIO

    from PIL import Image

    im = Image.open(BytesIO(data))
    if fmt == "WEBP":
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
    else:
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
    if width and im.width > width:
        im.thumbnail((width, width * 4), Image.LANCZOS)
    buf = BytesIO()
    if fmt == "WEBP":
        im.save(buf, "WEBP", quality=82, method=5)
    else:
        im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    out = buf.getvalue()
    cache_file.write_bytes(out)
    return out


_NO_CACHE = {"Cache-Control": "no-store"}


def _guess_type(path: str) -> str:
    return storage.MIME_TYPES.get(path.rsplit(".", 1)[-1].lower(), "application/octet-stream")


async def _ensure_file_record(path: str, uploaded_by: str) -> None:
    await db.files.update_one(
        {"storage_path": path},
        {"$set": {"storage_path": path, "is_deleted": False},
         "$setOnInsert": {"id": str(uuid.uuid4()), "original_filename": path.split("/")[-1],
                          "content_type": _guess_type(path), "created_at": now_utc(),
                          "uploaded_by": uploaded_by}},
        upsert=True,
    )


@api.get("/files/{path:path}")
async def serve_file(path: str, request: Request, w: int = 0):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        # the bytes are on disk but the bookkeeping row is gone (restored DB, failed mirror…): serve
        # the file and recreate the row instead of 404-ing on a picture we actually have
        if not storage.local_exists(path):
            raise HTTPException(404, "Файлът не е намерен", headers=_NO_CACHE)
        await _ensure_file_record(path, "self-heal")
        record = {"content_type": _guess_type(path)}
    content_type = record.get("content_type", "application/octet-stream")
    cache_file = IMAGE_CACHE / hashlib.sha1(path.encode()).hexdigest()
    if cache_file.exists():
        data = cache_file.read_bytes()
    else:
        try:
            data, storage_type = await run_in_threadpool(storage.get_object, path)
        except Exception as ex:
            log.warning("File %s unreadable: %s", path, ex)
            raise HTTPException(404, "Файлът не е намерен", headers=_NO_CACHE)
        content_type = record.get("content_type") or storage_type
        try:
            cache_file.write_bytes(data)
        except OSError as ex:
            log.warning("Image cache not writable (%s): %s", IMAGE_CACHE, ex)

    # every raster image is served as WebP (or JPEG for older clients), resized on demand
    convertible = content_type.startswith("image/") and not any(
        x in content_type for x in ("svg", "gif"))
    if convertible:
        accept = request.headers.get("accept", "")
        fmt = "WEBP" if "image/webp" in accept or not accept else "JPEG"
        width = w if w in ALLOWED_WIDTHS else 0
        try:
            suffix = "webp" if fmt == "WEBP" else "jpg"
            variant = IMAGE_CACHE / f"{cache_file.name}-w{width}.{suffix}"
            data = await run_in_threadpool(_image_variant, data, width, fmt, variant)
            content_type = f"image/{suffix if fmt == 'WEBP' else 'jpeg'}"
        except Exception as ex:
            log.warning("Image variant failed for %s: %s", path, ex)

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "Vary": "Accept"},
    )


# ---------- Media repair ----------
# Shopify CDN links carry a ?v=<version> query and the stored path is a hash of the whole URL, so a
# re-import after Shopify bumped that version produced brand-new paths while the bytes of the old
# ones were never re-uploaded. The result: a product pointing at a path that 404s even though the
# very same picture is on disk under a different hash. This walks every document, checks whether the
# referenced object can actually be read and re-points it to a readable copy of the same file (or
# downloads it again from the original source).
_FILE_REF = re.compile(r"/api/files/([A-Za-z0-9][A-Za-z0-9/._-]*\.(?:png|jpe?g|webp|gif|svg))")


def _readable(path: str) -> bool:
    try:
        storage.get_object(path)
        return True
    except Exception:
        return False


def _base_name(path: str) -> str:
    tail = path.split("/")[-1]
    return tail.split("-", 1)[1] if "-" in tail else tail


def _refetch_image(src: str) -> Optional[Dict[str, Any]]:
    """Download the original source again and store it under a query-independent path."""
    import requests

    try:
        resp = requests.get(src, timeout=60)
        resp.raise_for_status()
    except Exception as ex:
        log.warning("Media repair could not fetch %s: %s", src[:90], ex)
        return None
    base = re.sub(r"[^A-Za-z0-9._-]", "-", src.split("?")[0].rsplit("/", 1)[-1] or "image")
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else "png"
    content_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp", "gif": "image/gif"}.get(
                        ext, resp.headers.get("Content-Type", "image/png").split(";")[0])
    path = f"import/{hashlib.sha1(src.split('?')[0].encode()).hexdigest()[:12]}-{base}"
    stored = storage.put_object(path, resp.content, content_type).get("path", path)
    return {"path": stored, "base": base, "content_type": content_type, "size": len(resp.content)}


# ---------- off-site images ----------
# The lab reports (Janoshik certificates) were still served from the old Shopify store: the day that
# store lapses, 14 products lose their proof images and their JSON-LD `image` entries at once.
# Every picture we reference must live in our own storage.
_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>)]+", re.I)
_IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg", ".bmp")
OWN_HOSTS = ("purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr",
             "purepeptide-labs.bg")


def _is_external_image(url: str) -> bool:
    bare = url.split("?")[0].lower()
    host = _bare_host(url)
    if not host or host in OWN_HOSTS or host.endswith(".emergentagent.com"):
        return False
    return bare.endswith(_IMG_EXT) or "shopify" in host or "/cdn/shop/" in bare


async def _adopt_image(src: str) -> str:
    """`/api/files/...` URL for an off-site picture, downloading it once and reusing it after."""
    key = src.split("?")[0]
    entry = await db.image_map.find_one({"$or": [{"key": key}, {"src": src}]}, {"_id": 0, "path": 1, "url": 1})
    if entry and entry.get("url") and await run_in_threadpool(_readable, entry.get("path") or ""):
        return entry["url"]
    got = await run_in_threadpool(_refetch_image, src)
    if not got:
        return ""
    url = f"/api/files/{got['path']}"
    await _ensure_file_record(got["path"], "image-rehost")
    await db.image_map.update_one(
        {"key": key},
        {"$set": {"key": key, "src": src, "path": got["path"], "url": url},
         "$setOnInsert": {"created_at": now_utc()}}, upsert=True)
    return url


async def adopt_external_images(node: Any, report: Dict[str, List] = None) -> Any:
    """Copy every off-site image the value references into our storage and rewrite the reference."""
    if isinstance(node, str):
        out = node
        for url in dict.fromkeys(_URL_IN_TEXT.findall(node)):
            if not _is_external_image(url):
                continue
            local = await _adopt_image(url)
            if local:
                out = out.replace(url, local)
                if report is not None:
                    report.setdefault("replaced", []).append({"from": url, "to": local})
            elif report is not None:
                report.setdefault("failed", []).append(url)
        return out
    if isinstance(node, list):
        return [await adopt_external_images(x, report) for x in node]
    if isinstance(node, dict):
        return {k: await adopt_external_images(v, report) for k, v in node.items()}
    return node


@api.post("/admin/media/rehost")
async def rehost_media(dry_run: bool = False, user=Depends(require_admin)):
    """Bring every image we still serve from someone else's domain into our own storage."""
    report: Dict[str, List] = {}
    scanned = changed = 0
    for name in ("products", "collections_cat", "articles", "pages", "settings"):
        async for doc in db[name].find({}):
            scanned += 1
            payload = {k: v for k, v in doc.items() if k != "_id"}
            adopted = await adopt_external_images(payload, report)
            if adopted != payload:
                changed += 1
                if not dry_run:
                    await db[name].update_one({"_id": doc["_id"]}, {"$set": adopted})
    if changed and not dry_run:
        prerender.bump()
    return {"scanned": scanned, "documents_changed": changed,
            "replaced": report.get("replaced", []), "failed": sorted(set(report.get("failed", []))),
            "dry_run": dry_run}


@api.post("/admin/media/repair")
async def repair_media(dry_run: bool = False, user=Depends(require_admin)):
    """Re-point (or re-download) every image reference whose object cannot be read."""
    by_base: Dict[str, List[str]] = {}
    async for rec in db.files.find({"is_deleted": False}, {"_id": 0, "storage_path": 1}):
        path = rec.get("storage_path") or ""
        if path.startswith("import/"):
            by_base.setdefault(_base_name(path), []).append(path)

    checked: Dict[str, bool] = {}

    async def ok(path: str) -> bool:
        if path not in checked:
            checked[path] = await run_in_threadpool(_readable, path)
        return checked[path]

    async def resolve(path: str) -> Optional[str]:
        """A readable path for the same picture, or None when the bytes are gone for good."""
        for candidate in by_base.get(_base_name(path), []):
            if candidate != path and await ok(candidate):
                return candidate
        entry = await db.image_map.find_one({"path": path}, {"_id": 0, "src": 1})
        src = (entry or {}).get("src")
        if src:
            got = await run_in_threadpool(_refetch_image, src)
            if got and await ok(got["path"]):
                await db.files.update_one(
                    {"storage_path": got["path"]},
                    {"$set": {"storage_path": got["path"], "original_filename": got["base"],
                              "content_type": got["content_type"], "size": got["size"],
                              "is_deleted": False, "uploaded_by": "media-repair"},
                     "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now_utc()}},
                    upsert=True,
                )
                await db.image_map.update_one(
                    {"src": src},
                    {"$set": {"src": src, "path": got["path"], "url": f"/api/files/{got['path']}"},
                     "$setOnInsert": {"created_at": now_utc()}},
                    upsert=True,
                )
                by_base.setdefault(_base_name(got["path"]), []).append(got["path"])
                return got["path"]
        return None

    fixed: List[Dict[str, str]] = []
    unresolved: List[str] = []

    async def fix_value(value: str) -> str:
        """Replace every unreadable reference inside a string (plain path or HTML)."""
        out = value
        for ref in set(_FILE_REF.findall(value)):
            if await ok(ref):
                if not dry_run:
                    await _ensure_file_record(ref, "media-repair")
                continue
            replacement = await resolve(ref)
            if replacement:
                out = out.replace(ref, replacement)
                fixed.append({"from": ref, "to": replacement})
            else:
                unresolved.append(ref)
        if value.startswith("import/") and not await ok(value):
            replacement = await resolve(value)
            if replacement:
                fixed.append({"from": value, "to": replacement})
                return replacement
            unresolved.append(value)
        return out

    async def walk(node):
        if isinstance(node, str):
            return await fix_value(node) if "/api/files/" in node or node.startswith("import/") else node
        if isinstance(node, list):
            return [await walk(x) for x in node]
        if isinstance(node, dict):
            return {k: await walk(v) for k, v in node.items()}
        return node

    scanned = 0
    for name in ("products", "collections", "articles", "pages", "site_settings"):
        async for doc in db[name].find({}):
            scanned += 1
            payload = {k: v for k, v in doc.items() if k != "_id"}
            repaired = await walk(payload)
            if repaired != payload and not dry_run:
                await db[name].update_one({"_id": doc["_id"]}, {"$set": repaired})

    return {"scanned": scanned, "fixed": len(fixed), "unresolved": sorted(set(unresolved)),
            "changes": fixed[:50], "dry_run": dry_run}


@api.get("/admin/media/status")
async def media_status(user=Depends(require_admin)):
    """Where the pictures live on THIS server and which referenced ones cannot be served."""
    info = await run_in_threadpool(storage.diagnose)
    refs: set = set()
    for name in ("products", "collections", "articles", "pages", "site_settings"):
        async for doc in db[name].find({}, {"_id": 0}):
            refs.update(_FILE_REF.findall(json.dumps(doc, ensure_ascii=False, default=str)))
    broken: List[Dict[str, Any]] = []
    for ref in sorted(refs):
        rec = await db.files.find_one({"storage_path": ref, "is_deleted": False}, {"_id": 0, "storage_path": 1})
        on_disk = storage.local_exists(ref)
        if rec and on_disk:
            continue
        broken.append({"path": ref, "record": bool(rec), "on_disk": on_disk})
    info.update({
        "files_in_db": await db.files.count_documents({"is_deleted": False}),
        "referenced": len(refs),
        "broken": broken,
        "image_cache": str(IMAGE_CACHE),
        "image_cache_writable": os.access(IMAGE_CACHE, os.W_OK),
    })
    return info


@api.post("/admin/import/coa-images")
async def import_coa_images(dry_run: bool = False, user=Depends(require_admin)):
    """Attach the Shopify chemical-analysis (COA) file of every product to its gallery.

    The report is appended LAST, so the main product photo never changes, and the run is
    idempotent — a product that already carries its COA image is reported as skipped.
    """
    import coa_import

    rows = await run_in_threadpool(coa_import.pairs)
    added: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []
    for row in rows:
        handle, filename, src = row["handle"], row["filename"], row["url"]
        product = await db.products.find_one({"handle": handle}, {"_id": 0, "handle": 1,
                                                                  "title": 1, "images": 1})
        if not product:
            failed.append({"handle": handle, "file": filename, "reason": "няма такъв продукт"})
            continue
        if not src:
            failed.append({"handle": handle, "file": filename, "reason": "липсва линк в експорта"})
            continue
        entry = await db.image_map.find_one({"$or": [{"key": src.split("?")[0]}, {"src": src}]},
                                           {"_id": 0, "path": 1, "url": 1})
        url = (entry or {}).get("url") or ""
        if not (url and await run_in_threadpool(_readable, entry.get("path", ""))):
            got = await run_in_threadpool(_refetch_image, src)
            if not got:
                failed.append({"handle": handle, "file": filename, "reason": "неуспешно сваляне"})
                continue
            url = f"/api/files/{got['path']}"
            if not dry_run:
                await _ensure_file_record(got["path"], "coa-import")
                await db.image_map.update_one(
                    {"key": src.split("?")[0]},
                    {"$set": {"key": src.split("?")[0], "src": src, "path": got["path"], "url": url},
                     "$setOnInsert": {"created_at": now_utc()}},
                    upsert=True,
                )
        images = product.get("images") or []
        if url in images:
            skipped.append({"handle": handle, "title": product.get("title", ""), "url": url})
            continue
        if not dry_run:
            await db.products.update_one(
                {"handle": handle},
                {"$set": {"images": images + [url], "coa_image": url,
                          "updated_at": now_utc()}},
            )
        added.append({"handle": handle, "title": product.get("title", ""), "url": url})
    if added and not dry_run:
        prerender.bump()
    return {"scanned": len(rows), "added": added, "skipped": skipped, "failed": failed,
            "dry_run": dry_run}



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


async def _page_slugs(base_slug: str) -> Dict[str, str]:
    """The slug this page is published under per locale — a page rotated in one language keeps the
    base slug in the others, so the hreflang targets differ (they used to all 404)."""
    published: Dict[str, str] = {}
    async for d in db.pages.find({"slug": base_slug}, {"_id": 0, "locale": 1, "pub_slug": 1}):
        published[d["locale"]] = d.get("pub_slug") or base_slug
    return {loc: published.get(loc, base_slug) for loc in LOCALES}


@api.get("/pages/{slug}")
async def public_page(slug: str, locale: str = Query(DEFAULT_LOCALE)):
    loc = normalize_locale(locale)
    if slug in LEGACY_PAGE_ALIASES:          # imported Shopify duplicate — removed for good
        raise HTTPException(404, "Страницата не е намерена")
    # a rotated page is published under its new slug only; the old one must 404 for that locale
    moved = await db.pages.find_one({"locale": loc, "pub_slug": slug}, {"_id": 0})
    if moved:
        out = _page_out(moved)
        out["locale"] = loc
        out["source_locale"] = loc
        out["slugs"] = await _page_slugs(moved["slug"])
        return {"page": out}
    if await db.pages.find_one({"locale": loc, "rotations.from": slug}, {"_id": 0, "slug": 1}):
        raise HTTPException(404, "Страницата не е намерена")
    chain = [loc] + [l for l in ("en", "bg") if l != loc]
    for candidate in chain:
        doc = await db.pages.find_one({"slug": slug, "locale": candidate}, {"_id": 0})
        if _has_content(doc) and not doc.get("canonical_slug"):
            if candidate == loc and doc.get("pub_slug"):
                raise HTTPException(404, "Страницата не е намерена")
            out = _page_out(doc)
            out["locale"] = loc
            out["source_locale"] = candidate
            out["slugs"] = await _page_slugs(doc["slug"])
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
                "html": await adopt_external_images(payload.html),
                "faq_items": items,
                "updated_at": now_utc(),
            },
            "$setOnInsert": {"id": str(uuid.uuid4()), "slug": slug, "locale": loc},
        },
        upsert=True,
    )
    doc = await db.pages.find_one({"slug": slug, "locale": loc}, {"_id": 0})
    _links_cache.clear()
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
    for f in ("seo_title", "seo_description"):
        if source_doc.get(f):
            source[f] = source_doc[f]
    if source_doc.get("faq_items"):
        source["faq_items"] = source_doc["faq_items"]

    translated: List[str] = []
    failed: List[str] = []
    for chunk_start in range(0, len(targets), 2):
        chunk = targets[chunk_start:chunk_start + 2]
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
                        "seo_title": fields.get("seo_title", ""),
                        "seo_description": fields.get("seo_description", ""),
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
import analytics_bots  # noqa: E402

# same visitor id in three windows: presence of the cookie means "seen in the last 24h / 7d / 30d"
VISITOR_COOKIES = (("pp_v24", 60 * 60 * 24), ("pp_v7", 60 * 60 * 24 * 7), ("pp_v30", 60 * 60 * 24 * 30))
SESSION_COOKIE = "pp_ses"
SESSION_IDLE = 30 * 60          # Shopify's rule: 30 minutes without a page view ends the session
SESSION_MAX = 24 * 60 * 60      # ...and a session never lives longer than 24 hours


def _session_id(request: Request) -> str:
    """Sliding 30-minute session, capped at 24 hours — a new browser tab is the SAME session.

    The value is `<id>.<started epoch>`: the cookie's own 30-minute expiry ends an idle session,
    the timestamp inside it ends a session that has been going on for a day.
    """
    raw = request.cookies.get(SESSION_COOKIE) or ""
    sid, _, started = raw.partition(".")
    if sid and started.isdigit() and time.time() - int(started) < SESSION_MAX:
        return raw
    return f"{uuid.uuid4().hex}.{int(time.time())}"


def _cookieless_ids(request: Request, ua: str) -> tuple:
    """Session/visitor ids for a visitor who has not accepted analytics cookies.

    A daily-salted hash of IP + user agent: it groups the page views of one person into 30-minute
    windows (so the session count stays honest) without storing anything on their device and
    without being traceable from one day to the next.
    """
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() \
        or (request.client.host if request.client else "?")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{ip}|{ua}|{day}".encode()).hexdigest()
    return f"{digest[:24]}-{int(time.time() // SESSION_IDLE)}", digest[:32]


class TrackIn(BaseModel):
    session_id: str = ""
    path: str = "/"
    referrer: str = ""
    locale: str = "bg"


@api.post("/track")
async def track_visit(payload: TrackIn, request: Request, response: Response):
    """One page view. Bots are flagged (and never counted), humans get the tracking cookies.

    With analytics consent the session lives in a cookie with a sliding 30-minute window (Shopify's
    rule), so a second tab is no longer a second session, and three more cookies carry the same
    visitor id for 24h / 7d / 30d. Without consent nothing is stored on the device — the same
    windows are derived from a daily-salted IP+UA hash instead.
    """
    ua = (request.headers.get("user-agent") or "")[:300]
    bot = analytics_bots.is_bot(ua)
    # analytics cookies only after the visitor accepted them (pp_consent = "<analytics><marketing>")
    consented = (request.cookies.get("pp_consent") or "")[:1] == "1"
    if consented:
        session = _session_id(request)
        visitor_id = request.cookies.get(VISITOR_COOKIES[-1][0]) or uuid.uuid4().hex
        fresh = {name: not request.cookies.get(name) for name, _ in VISITOR_COOKIES}
    else:
        session, visitor_id = _cookieless_ids(request, ua)
        fresh = {name: False for name, _ in VISITOR_COOKIES}
    await db.visits.insert_one({
        "session_id": session.split(".")[0],
        "visitor_id": visitor_id,
        "path": payload.path[:300],
        "referrer": payload.referrer[:300],
        "locale": normalize_locale(payload.locale),
        "ua": ua,
        "bot": bot,
        "cookieless": not consented,
        "new_24h": fresh["pp_v24"],
        "new_7d": fresh["pp_v7"],
        "new_30d": fresh["pp_v30"],
        "ts": now_utc(),
    })
    if not bot and consented:
        response.set_cookie(SESSION_COOKIE, session, max_age=SESSION_IDLE, httponly=True,
                            samesite="lax", secure=True, path="/")
        for name, max_age in VISITOR_COOKIES:
            response.set_cookie(name, visitor_id, max_age=max_age, httponly=True,
                                samesite="lax", secure=True, path="/")
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
        {"ts": {"$gte": s_iso, "$lt": e_iso}, **analytics_bots.NOT_BOT},
        {"_id": 0, "session_id": 1, "visitor_id": 1, "ts": 1},
    ).to_list(200000)
    orders = await db.orders.find(
        {"created_at": {"$gte": s_iso, "$lt": e_iso}, "status": {"$ne": "cancelled"}},
        {"_id": 0, "created_at": 1, "subtotal_eur": 1, "discount_eur": 1, "source": 1},
    ).to_list(50000)

    sessions = {v["session_id"] for v in visits}
    visitors = {v.get("visitor_id") or v["session_id"] for v in visits}
    own_orders = sum(1 for o in orders if (o.get("source") or "storefront") != "shopify_import")
    sales = sum(max((o.get("subtotal_eur") or 0) - (o.get("discount_eur") or 0), 0) for o in orders)

    buckets: Dict[str, Dict[str, float]] = {}
    first_seen: Dict[str, str] = {}
    for v in visits:
        sid = v["session_id"]
        if sid not in first_seen or v["ts"] < first_seen[sid]:
            first_seen[sid] = v["ts"]
        b = buckets.setdefault(_bucket_key(v["ts"], bucket),
                               {"sessions": 0, "views": 0, "orders": 0, "sales": 0.0})
        b["views"] += 1
    for sid, ts in first_seen.items():
        b = buckets.setdefault(_bucket_key(ts, bucket),
                               {"sessions": 0, "views": 0, "orders": 0, "sales": 0.0})
        b["sessions"] += 1
    for o in orders:
        b = buckets.setdefault(_bucket_key(o["created_at"], bucket),
                               {"sessions": 0, "views": 0, "orders": 0, "sales": 0.0})
        b["orders"] += 1
        b["sales"] += max((o.get("subtotal_eur") or 0) - (o.get("discount_eur") or 0), 0)

    keys: List[str] = []
    cursor = start
    step = timedelta(hours=1) if bucket == "hour" else timedelta(days=1)
    while cursor < end + step:
        keys.append(_bucket_key(cursor.isoformat(), bucket))
        cursor += step
    series = [
        {"t": k, **{m: round(buckets.get(k, {}).get(m, 0), 2)
                    for m in ("sessions", "views", "orders", "sales")}}
        for k in keys
    ]
    return {
        "sessions": len(sessions),
        "visitors": len(visitors),
        "views": len(visits),
        "orders": len(orders),
        "sales": round(sales, 2),
        # only orders placed in THIS shop can be related to the sessions we track — the imported
        # Shopify history has no sessions here and would push the conversion above 100%
        "conversion": (min(round(own_orders / len(sessions) * 100, 2), 100.0)
                       if sessions and own_orders else 0.0),
        "series": series,
    }


async def _visitor_windows() -> Dict[str, int]:
    """Different people (visitor cookie) in the last 24h / 7 days / 30 days, bots excluded.

    Visits recorded before the cookies existed only have a session id — they fall back to it, so
    the windows and the period figures always tell the same story.
    """
    now = datetime.now(timezone.utc)
    out: Dict[str, int] = {}
    for key, days in (("24h", 1), ("7d", 7), ("30d", 30)):
        since = (now - timedelta(days=days)).isoformat()
        rows = await db.visits.aggregate([
            {"$match": {"ts": {"$gte": since}, **analytics_bots.NOT_BOT}},
            {"$group": {"_id": {"$ifNull": ["$visitor_id", "$session_id"]}}},
            {"$count": "n"},
        ]).to_list(1)
        out[key] = rows[0]["n"] if rows else 0
    return out


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
    live = await db.visits.distinct("session_id", {"ts": {"$gte": live_since}, **analytics_bots.NOT_BOT})
    bots = await db.visits.count_documents({"ts": {"$gte": start.isoformat(), "$lt": end.isoformat()},
                                            "$nor": [analytics_bots.NOT_BOT]})

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
        "bots_excluded": bots,
        "visitors": await _visitor_windows(),
        "current": current,
        "previous": previous,
        "deltas": {
            "sessions": delta(current["sessions"], previous["sessions"]),
            "visitors": delta(current["visitors"], previous["visitors"]),
            "views": delta(current["views"], previous["views"]),
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
    contact_subject, contact_html = email_templates.render_admin_contact(safe)
    email_ok = True
    try:
        await email_service.send_email(to, contact_subject, contact_html,
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
    for f in ("seo_title", "seo_description"):
        if doc.get(f):
            source[f] = doc[f]

    try:
        result = await ai_translate_chunked(source, targets, context="PurePeptide research peptides e-commerce")
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
    resource: str = "everything"  # product | collection | article | page | all | everything
    locales: List[str] = []
    overwrite: bool = False


async def _translate_one(coll, doc, targets: List[str], overwrite: bool) -> List[str]:
    existing = doc.get("translations") or {}

    def stale(loc: str) -> bool:
        tr = existing.get(loc) or {}
        if not tr.get("title"):
            return True
        # the Bulgarian text gained its "<h1>" heading after this translation was made
        src_h1 = bool(re.match(r"\s*<h1[\s>]", doc.get("description") or "", re.I))
        return src_h1 and not re.match(r"\s*<h1[\s>]", tr.get("description") or "", re.I)

    todo = [l for l in targets if overwrite or stale(l)]
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
    for f in ("seo_title", "seo_description"):
        if doc.get(f):
            source[f] = doc[f]
    result = await ai_translate_chunked(source, todo, context="PurePeptide research peptides e-commerce")
    updates = {f"translations.{loc}": {**(existing.get(loc) or {}), **fields} for loc, fields in result.items()}
    if updates:
        await coll.update_one({"id": doc["id"]}, {"$set": updates})
    return list(result.keys())


async def _translate_article(doc, targets: List[str], overwrite: bool) -> List[str]:
    """Articles are translated one locale per call — the body HTML is long."""
    existing = doc.get("translations") or {}
    todo = [l for l in targets if overwrite or not (existing.get(l) or {}).get("title")]
    done: List[str] = []
    for loc in todo:
        source = {k: doc.get(k) for k in ("title", "handle", "excerpt", "body", "seo_title", "seo_description") if doc.get(k)}
        result = await ai_translate(source, [loc], context="PurePeptide scientific article about research peptides")
        fields = result.get(loc)
        if not fields:
            continue
        await db.articles.update_one(
            {"id": doc["id"]},
            {"$set": {f"translations.{loc}": {**(existing.get(loc) or {}), **fields}}},
        )
        done.append(loc)
    return done


async def _translate_page_slug(slug: str, targets: List[str], overwrite: bool) -> List[str]:
    source_doc = await db.pages.find_one({"slug": slug, "locale": "bg"}, {"_id": 0})
    if not _has_content(source_doc):
        return []
    todo = list(targets)
    if not overwrite:
        kept = []
        for loc in todo:
            existing = await db.pages.find_one({"slug": slug, "locale": loc})
            if not _has_content(existing):
                kept.append(loc)
        todo = kept
    if not todo:
        return []
    source = {"title": source_doc.get("title", ""), "html": source_doc.get("html", "")}
    for f in ("seo_title", "seo_description"):
        if source_doc.get(f):
            source[f] = source_doc[f]
    if source_doc.get("faq_items"):
        source["faq_items"] = source_doc["faq_items"]
    done: List[str] = []
    for start in range(0, len(todo), 2):
        chunk = todo[start:start + 2]
        result = await ai_translate_page(source, chunk)
        for loc, fields in result.items():
            await db.pages.update_one(
                {"slug": slug, "locale": loc},
                {"$set": {
                    "title": fields.get("title", ""),
                    "html": fields.get("html", ""),
                    "faq_items": fields.get("faq_items", []),
                    "seo_title": fields.get("seo_title", ""),
                    "seo_description": fields.get("seo_description", ""),
                    "updated_at": now_utc(),
                }, "$setOnInsert": {"id": str(uuid.uuid4()), "slug": slug, "locale": loc}},
                upsert=True,
            )
            done.append(loc)
    return done


SETTINGS_TR_FIELDS = ("tagline", "footer_text", "announcements")


async def _translate_settings(targets: List[str], overwrite: bool) -> List[str]:
    """Site-wide copy from the settings (announcement bar, tagline, footer) → *_i18n[locale]."""
    doc = await db.settings.find_one({"key": "site"}, {"_id": 0})
    value = (doc or {}).get("value") or {}
    source = {f: value[f] for f in ("tagline", "footer_text") if value.get(f)}
    ann = [a for a in (value.get("announcements") or []) if a]
    for i, a in enumerate(ann):
        source[f"announcement_{i}"] = a
    if not source:
        return []
    todo = [l for l in targets if overwrite or not (value.get("tagline_i18n") or {}).get(l)
            or not (value.get("announcements_i18n") or {}).get(l)]
    if not todo:
        return []
    result = await ai_translate_chunked(source, todo, context="PurePeptide storefront: announcement bar, tagline, footer")
    updates: Dict[str, Any] = {}
    for loc, fields in result.items():
        for f in ("tagline", "footer_text"):
            if fields.get(f):
                updates[f"value.{f}_i18n.{loc}"] = fields[f]
        anns = [fields.get(f"announcement_{i}") for i in range(len(ann))]
        if all(anns):
            updates[f"value.announcements_i18n.{loc}"] = anns
    if updates:
        await db.settings.update_one({"key": "site"}, {"$set": updates})
    return list(result.keys())


async def _job_stopped(job_id: str) -> bool:
    job = await db.translate_jobs.find_one({"id": job_id}, {"_id": 0, "status": 1})
    return not job or job.get("status") == "stopped"


async def _run_bulk_translate(job_id: str, resource: str, targets: List[str], overwrite: bool):
    """Works through every translatable thing; progress is persisted per item so a restart resumes."""
    do_all = resource in ("all", "everything")
    steps: List[tuple] = []
    if do_all or resource == "product":
        steps.append(("product", db.products))
    if do_all or resource == "collection":
        steps.append(("collection", db.collections_cat))
    if resource in ("everything", "article"):
        steps.append(("article", db.articles))
    include_pages = resource in ("everything", "page")
    include_ui = resource in ("everything", "ui")
    include_settings = resource in ("everything", "settings")

    job = await db.translate_jobs.find_one({"id": job_id}, {"_id": 0}) or {}
    completed = set(job.get("completed") or [])
    failed: List[str] = list(job.get("failed") or [])

    total = 0
    for _, coll in steps:
        total += await coll.count_documents({})
    if include_pages:
        total += len(PAGE_SLUGS)
    if include_ui:
        total += len(targets)
    if include_settings:
        total += 1
    done = len(completed)
    await db.translate_jobs.update_one(
        {"id": job_id},
        {"$set": {"status": "running", "total": total, "done": done, "failed": failed, "updated_at": now_utc()}},
    )

    async def tick(key: str, label: str, ok: bool):
        nonlocal done
        done += 1
        if ok:
            completed.add(key)
        elif key not in failed:
            failed.append(key)
        await db.translate_jobs.update_one(
            {"id": job_id},
            {"$set": {"done": done, "failed": failed, "current": label, "updated_at": now_utc()},
             "$addToSet": {"completed": key}},
        )

    for kind, coll in steps:
        docs = await coll.find({}, {"_id": 0}).to_list(1000)
        for doc in docs:
            key = f"{kind}:{doc.get('handle')}"
            if key in completed:
                continue
            if await _job_stopped(job_id):
                return
            ok = True
            try:
                if kind == "article":
                    await _translate_article(doc, targets, overwrite)
                else:
                    await _translate_one(coll, doc, targets, overwrite)
            except Exception as ex:
                log.error("Bulk translate failed for %s %s: %s", kind, doc.get("handle"), ex)
                ok = False
            await tick(key, f"{kind}: {doc.get('handle')}", ok)
    if include_pages:
        for slug in PAGE_SLUGS:
            key = f"page:{slug}"
            if key in completed:
                continue
            if await _job_stopped(job_id):
                return
            ok = True
            try:
                await _translate_page_slug(slug, targets, overwrite)
            except Exception as ex:
                log.error("Bulk translate failed for page %s: %s", slug, ex)
                ok = False
            await tick(key, f"page: {slug}", ok)
    if include_settings and "settings:site" not in completed:
        if await _job_stopped(job_id):
            return
        ok = True
        try:
            await _translate_settings(targets, overwrite)
        except Exception as ex:
            log.error("Bulk translate failed for settings: %s", ex)
            ok = False
        await tick("settings:site", "настройки: лента, слоган, футър", ok)
    if include_ui:
        import ui_strings as ui_strings_mod
        for loc in targets:
            key = f"checkout:{loc}"
            if key in completed:
                continue
            if await _job_stopped(job_id):
                return
            ok = True
            try:
                await ui_strings_mod.translate_locale(loc)
            except Exception as ex:
                log.error("Bulk translate failed for checkout copy %s: %s", loc, ex)
                ok = False
            await tick(key, f"чекаут и текстове на сайта: {loc}", ok)
    await db.translate_jobs.update_one(
        {"id": job_id}, {"$set": {"status": "finished", "current": "", "updated_at": now_utc()}}
    )


async def resume_translate_jobs():
    """A deploy or restart must not lose a queued translation — pick it up where it stopped."""
    job = await db.translate_jobs.find_one({"status": {"$in": ["queued", "running"]}}, {"_id": 0},
                                           sort=[("created_at", -1)])
    if job:
        log.info("Resuming translation job %s (%s/%s)", job["id"], job.get("done"), job.get("total"))
        asyncio.create_task(_run_bulk_translate(job["id"], job.get("resource", "everything"),
                                                job.get("locales") or [], bool(job.get("overwrite"))))


async def _missing_translations(targets: List[str]) -> int:
    """How many catalogue items still lack a translation in one of the target languages."""
    missing = 0
    for coll in (db.products, db.collections_cat, db.articles):
        for loc in targets:
            missing += await coll.count_documents({f"translations.{loc}.title": {"$in": [None, ""]}})
    return missing


async def auto_translate_watch():
    """Production translates itself: new products, collections and articles are picked up without
    anyone opening the admin panel. Off by default (AUTO_TRANSLATE), never overwrites existing copy."""
    if (os.environ.get("AUTO_TRANSLATE") or "").strip().lower() not in ("1", "true", "yes"):
        return
    targets = [loc for loc in LOCALES if loc != DEFAULT_LOCALE]
    await asyncio.sleep(90)                       # let the app finish booting first
    while True:
        try:
            active = await db.translate_jobs.find_one({"status": {"$in": ["queued", "running"]}}, {"_id": 0})
            if not active and await _missing_translations(targets):
                job_id = str(uuid.uuid4())
                await db.translate_jobs.insert_one({
                    "id": job_id, "status": "queued", "resource": "everything", "locales": targets,
                    "overwrite": False, "completed": [], "total": 0, "done": 0, "failed": [],
                    "current": "", "created_at": now_utc(), "updated_at": now_utc(), "actor": "auto",
                })
                log.info("Auto-translate job %s started for %s", job_id, ", ".join(targets))
                asyncio.create_task(_run_bulk_translate(job_id, "everything", targets, False))
        except Exception:
            log.exception("auto-translate watch failed")
        await asyncio.sleep(6 * 3600)


@api.post("/admin/translate/bulk")
async def admin_bulk_translate(payload: BulkTranslateIn, user=Depends(require_admin)):
    targets = [normalize_locale(l) for l in (payload.locales or LOCALES) if normalize_locale(l) != "bg"]
    running = await db.translate_jobs.find_one({"status": {"$in": ["queued", "running"]}}, {"_id": 0})
    if running:
        stale = (datetime.now(timezone.utc) - datetime.fromisoformat(running["updated_at"])).total_seconds() > 180
        if stale:
            await db.translate_jobs.update_one({"id": running["id"]}, {"$set": {"status": "stopped"}})
        else:
            return {"job": running, "message": "Вече има активен превод"}
    job_id = str(uuid.uuid4())
    await db.translate_jobs.insert_one({
        "id": job_id, "status": "queued", "resource": payload.resource, "locales": targets,
        "overwrite": payload.overwrite, "completed": [],
        "total": 0, "done": 0, "failed": [], "current": "", "created_at": now_utc(), "updated_at": now_utc(),
        "actor": user["email"],
    })
    asyncio.create_task(_run_bulk_translate(job_id, payload.resource, targets, payload.overwrite))
    return {"job_id": job_id, "status": "queued", "locales": targets}


@api.post("/admin/translate/bulk/stop")
async def admin_bulk_translate_stop(user=Depends(require_admin)):
    res = await db.translate_jobs.update_many(
        {"status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "stopped", "current": "", "updated_at": now_utc()}})
    return {"stopped": res.modified_count}


@api.get("/admin/translate/bulk/history")
async def admin_bulk_translate_history(user=Depends(require_admin)):
    jobs = await db.translate_jobs.find({}, {"_id": 0, "completed": 0}).sort("created_at", -1).to_list(10)
    return {"jobs": jobs}


@api.get("/admin/translate/bulk")
async def admin_bulk_translate_status(user=Depends(require_admin)):
    job = await db.translate_jobs.find_one({}, {"_id": 0, "completed": 0}, sort=[("created_at", -1)])
    return {"job": job}


# resolved navigation paths per locale, invalidated whenever a page/collection is saved
_links_cache: Dict[str, tuple] = {}


@api.get("/links")
async def resolve_links(locale: str = Query(DEFAULT_LOCALE)):
    """Resolve every logical navigation key to a path that exists right now (see links_map.py)."""
    loc = normalize_locale(locale)
    cached = _links_cache.get(loc)
    if cached and time.time() - cached[0] < 300:
        return cached[1]

    out: Dict[str, str] = {}
    for key, (kind, candidates) in LINK_TARGETS.items():
        if kind == "collection":
            doc = (await db.collections_cat.find_one({"link_key": key}, {"_id": 0})
                   or await db.collections_cat.find_one({"handle": {"$in": candidates}}, {"_id": 0}))
            if doc:
                handle = ((doc.get("translations") or {}).get(loc) or {}).get("handle") or doc["handle"]
                out[key] = f"/collections/{handle}"
        else:
            doc = await db.pages.find_one({"link_key": key, "locale": "bg",
                                          "canonical_slug": {"$in": [None, ""]}}, {"_id": 0})
            if not doc:
                for candidate in candidates:
                    found = await db.pages.find_one({"slug": candidate, "locale": "bg"}, {"_id": 0})
                    if found and not found.get("canonical_slug"):
                        doc = found
                        break
            if doc:
                slug = doc["slug"]
                if loc != DEFAULT_LOCALE:
                    local = await db.pages.find_one({"slug": slug, "locale": loc}, {"_id": 0, "pub_slug": 1})
                    slug = (local or {}).get("pub_slug") or slug
                else:
                    slug = doc.get("pub_slug") or slug
                out[key] = f"/pages/{slug}"
    _links_cache[loc] = (time.time(), out)
    return out


@api.get("/link-index")
async def link_index(locale: str = Query(DEFAULT_LOCALE)):
    """Everything that has a URL — powers the HTML sitemap pages."""
    loc = normalize_locale(locale)
    cols = await db.collections_cat.find({"nav_hidden": {"$ne": True}}, {"_id": 0}).sort("sort_order", 1).to_list(200)
    prods = await db.products.find({"active": {"$ne": False}}, {"_id": 0}).to_list(500)
    arts = await db.articles.find({"published": {"$ne": False}}, {"_id": 0}).to_list(200)
    pages = await db.pages.find({"locale": {"$in": [loc, "bg"]}}, {"_id": 0}).to_list(200)
    by_slug: Dict[str, Dict[str, Any]] = {}
    for p in pages:
        if p["slug"] not in by_slug or p["locale"] == loc:
            by_slug[p["slug"]] = p
    slim = lambda d: {"handle": d.get("handle"), "title": d.get("title", "")}
    return {
        "collections": [slim(c) for c in localize_list(cols, loc)],
        "products": [slim(p) for p in localize_list(prods, loc)],
        "articles": [slim(a) for a in localize_list(arts, loc)],
        "pages": [{"slug": (d.get("pub_slug") if d.get("locale") == loc and d.get("pub_slug") else s),
                   "title": (d.get("title") or PAGE_LABELS.get(s, s))}
                  for s, d in by_slug.items() if s in PAGE_SLUGS and not d.get("canonical_slug")],
    }


# ---------- SEO: sitemap + robots ----------
def _loc_url(locale: str, path: str, routes: Dict[str, Any] = None) -> str:
    cfg = (routes or {}).get(locale) or SITE_ORIGINS[locale]
    return f"{cfg['origin']}{cfg.get('prefix', '')}{path}"


def _bare_host(value: str) -> str:
    return value.replace("https://", "").replace("http://", "").split("/")[0] \
        .split(":")[0].lower().removeprefix("www.")


def _host_locales(request: Request, routes: Dict[str, Any], active: List[str]) -> List[str]:
    """The locales that actually live on the requested domain.

    A sitemap may only list URLs of its own host — purepeptide.bg/sitemap.xml listing the .eu and
    .ro pages made Search Console report hundreds of foreign URLs. purepeptide.eu keeps its eight
    prefixed languages, .bg / .ro / .gr keep one each.
    """
    host = _bare_host(request.headers.get("x-forwarded-host") or request.headers.get("host") or "")
    own = [l for l in active if _bare_host((routes.get(l) or SITE_ORIGINS[l])["origin"]) == host]
    if not own and host == "purepeptide-labs.bg":       # the Bulgarian alias domain
        own = [l for l in active if l == DEFAULT_LOCALE]
    return own or active


SITEMAP_KINDS = ("products", "collections", "pages", "blogs")
# a stale CDN copy of robots.txt/sitemap outlived a deploy by an hour and looked like a bug
SEO_CACHE = {"Cache-Control": "public, max-age=300, s-maxage=300"}
SITEMAP_CHUNK = 5000          # Shopify splits at 5 000 URLs per file; same limit here


async def _sitemap_groups(request: Request):
    """Every URL of the requested domain, grouped like Shopify's child sitemaps.

    Returns (routes, active, listed, groups) where each entry is
    (path per locale, priority, image srcs, lastmod).
    """
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    active = [l for l in LOCALES if (routes.get(l) or {}).get("enabled", True)]
    listed = _host_locales(request, routes, active)
    cols = await db.collections_cat.find({}, {"_id": 0}).to_list(200)
    # a de-activated product 404s on the storefront — listing it in a sitemap is a dead link
    prods = await db.products.find({"active": {"$ne": False}}, {"_id": 0}).to_list(500)
    arts = await db.articles.find({"published": {"$ne": False}}, {"_id": 0}).to_list(200)
    static_pages = [""] + [f"/pages/{s}" for s in PAGE_SLUGS] + [
        "/pages/articles", "/pages/html-sitemap", "/pages/html-sitemap-products",
        "/pages/html-sitemap-collections", "/pages/html-sitemap-blogs",
        "/pages/html-sitemap-articles", "/pages/html-sitemap-pages",
    ]
    # rotated pages are published per locale under a new slug
    rotated_pages: Dict[str, Dict[str, str]] = {}
    page_days: Dict[str, str] = {}
    async for d in db.pages.find({}, {"_id": 0, "slug": 1, "locale": 1, "pub_slug": 1, "updated_at": 1}):
        if d.get("pub_slug"):
            rotated_pages.setdefault(d["locale"], {})[d["slug"]] = d["pub_slug"]
        day = _stamp(d.get("updated_at"))
        if day and day > page_days.get(d["slug"], ""):
            page_days[d["slug"]] = day

    def page_path(path: str, loc: str) -> str:
        slug = path.rsplit("/", 1)[-1]
        return f"/pages/{rotated_pages.get(loc, {}).get(slug, slug)}"

    def handle_for(doc, loc):
        return ((doc.get("translations") or {}).get(loc) or {}).get("handle") or doc.get("handle")

    def entry(doc, prefix: str, brand_sep: str) -> Dict[str, Dict[str, str]]:
        """Per-locale path, image title and caption — every domain must read in its own language,
        not in Bulgarian (the cached translations already hold the localised titles)."""
        out = {}
        for loc in active:
            local = localize_doc(doc, loc)
            title = local.get("title") or ""
            src = (local.get("images") or [None])[0] or local.get("image")
            out[loc] = {"path": f"{prefix}{handle_for(doc, loc)}", "src": src or "",
                        "title": title, "caption": f"{title}{brand_sep}PurePeptide" if title else ""}
        return out

    doc_days = [d for d in (_stamp(x.get("updated_at")) for x in cols + prods + arts) if d]
    newest = max(doc_days) if doc_days else datetime.now(timezone.utc).date().isoformat()

    groups: Dict[str, List[tuple]] = {k: [] for k in SITEMAP_KINDS}
    for path in static_pages:
        slug = path.rsplit("/", 1)[-1]
        meta = {loc: {"path": (page_path(path, loc) if path else path), "src": ""} for loc in active}
        if path == "":                       # Shopify lists the home page in the product sitemap
            groups["products"].append((meta, "daily", ""))
            continue
        target = "blogs" if path == "/pages/articles" else "pages"
        groups[target].append((meta, "daily", page_days.get(slug) or newest))
    for c in cols:
        groups["collections"].append((entry(c, "/collections/", " - "), "daily",
                                      _stamp(c.get("updated_at")) or newest))
    for p in prods:
        groups["products"].append((entry(p, "/products/", " - "), "daily",
                                   _stamp(p.get("updated_at")) or newest))
    for a in arts:
        groups["blogs"].append((entry(a, "/articles/", " "), "daily",
                                _stamp(a.get("updated_at")) or _stamp(a.get("published_at")) or newest))
    return routes, active, listed, groups


def _host_origin(request: Request, routes: Dict[str, Any], listed: List[str]) -> str:
    """The origin the sitemap itself is served from — a sitemap may only list its own host."""
    return ((routes.get(listed[0]) or SITE_ORIGINS[listed[0]])["origin"]).rstrip("/")


def _sitemap_pages(entries: List[tuple], listed: List[str]) -> int:
    urls = max(len(entries) * max(len(listed), 1), 1)
    return (urls + SITEMAP_CHUNK - 1) // SITEMAP_CHUNK


def _stamp(value: Any) -> str:
    """Full ISO timestamp of a stored value, like Shopify's lastmod (2026-09-05T22:18:39+00:00)."""
    if isinstance(value, datetime):
        return value.replace(microsecond=0).astimezone(timezone.utc).isoformat()
    if isinstance(value, str) and len(value) >= 10:
        return re.sub(r"\.\d+", "", value)          # stored ISO strings carry microseconds
    return ""


def _q(path: str) -> str:
    """Sitemap URLs must be percent-encoded (the Cyrillic page slug, like Shopify's export)."""
    return quote(path, safe="/-_.~") or "/"


# HEAD must answer too: FastAPI routes are GET-only, so validators and crawlers that probe with
# HEAD got a 405 on every sitemap ("couldn't fetch")
@api.api_route("/sitemap.xml", methods=["GET", "HEAD"])
async def sitemap_index(request: Request):
    """Parent sitemap, same shape as the Shopify one: one child file per resource kind."""
    routes, _active, listed, groups = await _sitemap_groups(request)
    origin = _host_origin(request, routes, listed)
    locs = [f"{origin}/sitemap_agentic_discovery.xml"]
    for kind in SITEMAP_KINDS:
        for page in range(1, _sitemap_pages(groups[kind], listed) + 1):
            locs.append(f"{origin}/sitemap_{kind}_{page}.xml")
    body = "".join(f"  <sitemap>\n    <loc>{loc}</loc>\n  </sitemap>\n" for loc in locs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + body + "</sitemapindex>\n")
    return Response(content=xml, media_type="application/xml", headers=SEO_CACHE)


@api.api_route("/sitemap_{kind}_{page:int}.xml", methods=["GET", "HEAD"])
async def sitemap_child(kind: str, page: int, request: Request):
    if kind not in SITEMAP_KINDS or page < 1:
        raise HTTPException(404, "Sitemap не съществува")
    routes, active, listed, groups = await _sitemap_groups(request)
    entries = groups[kind]
    if page > _sitemap_pages(entries, listed):
        raise HTTPException(404, "Sitemap не съществува")

    def img_tag(loc: str, meta: Dict[str, str]) -> str:
        """Same shape as the Shopify product sitemap (loc + title + caption), in the locale's own
        language — every domain used to repeat the Bulgarian title."""
        src = meta.get("src") or ""
        if not src:
            return ""
        origin = ((routes.get(loc) or SITE_ORIGINS[loc])["origin"]).rstrip("/")
        return ("    <image:image>\n"
                f"      <image:loc>{html_lib.escape(src if src.startswith('http') else origin + src, quote=True)}</image:loc>\n"
                f"      <image:title>{html_lib.escape(meta.get('title') or '', quote=True)}</image:title>\n"
                f"      <image:caption>{html_lib.escape(meta.get('caption') or '', quote=True)}</image:caption>\n"
                "    </image:image>\n")

    # lastmod is the real change date of the record — a rolling "today" told Google every URL had
    # changed on every request and devalued the signal
    urls: List[str] = []
    for meta, changefreq, lastmod in entries:
        for loc in listed:
            urls.append(
                f'  <url>\n    <loc>{_loc_url(loc, _q(meta[loc]["path"]), routes)}</loc>\n'
                + (f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else "")
                + f"    <changefreq>{changefreq}</changefreq>\n"
                f"{img_tag(loc, meta[loc])}  </url>\n"
            )
    window = urls[(page - 1) * SITEMAP_CHUNK: page * SITEMAP_CHUNK]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
           'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
           + "".join(window) + "</urlset>\n")
    return Response(content=xml, media_type="application/xml", headers=SEO_CACHE)


@api.api_route("/sitemap_agentic_discovery.xml", methods=["GET", "HEAD"])
async def agentic_sitemap(request: Request):
    """AI entry point, same as Shopify's: the agent guide, nothing else. The full URL inventory
    lives in the regular sitemap children, so there is nothing to duplicate here."""
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    active = [l for l in LOCALES if (routes.get(l) or {}).get("enabled", True)]
    locale = _host_locales(request, routes, active)[0]
    cfg = routes.get(locale) or SITE_ORIGINS[locale]
    origin = cfg["origin"].rstrip("/")
    body = "".join(f"  <url>\n    <loc>{origin}{p}</loc>\n    <changefreq>daily</changefreq>\n  </url>\n"
                   for p in ("/agents.md", "/llms.txt"))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")
    return Response(content=xml, media_type="application/xml", headers=SEO_CACHE)


@api.api_route("/agents.md", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def agents_md():
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    origin = (routes.get("bg") or SITE_ORIGINS["bg"])["origin"]
    cols = await db.collections_cat.find({}, {"_id": 0, "handle": 1, "title": 1}).sort("sort_order", 1).to_list(50)
    prods = await db.products.find({"active": {"$ne": False}}, {"_id": 0, "handle": 1, "title": 1, "variants": 1}).to_list(500)
    lines = [
        "# PurePeptide — AI agent guide",
        "",
        "PurePeptide е български доставчик на лиофилизирани изследователски пептиди с чистота >99%,",
        "потвърдена с HPLC и LC-MS от независимата лаборатория Janoshik Analytical.",
        "Продуктите са само за лабораторни и научноизследователски цели (Research Use Only).",
        "",
        "## Entry points",
        f"- Home: {origin}/",
        f"- All peptides: {origin}/collections/{await catalog_handle()}",
        f"- HTML sitemap: {origin}/pages/html-sitemap",
        f"- XML sitemap: {origin}/sitemap.xml",
        f"- Scientific articles: {origin}/pages/articles",
        f"- Lab analysis & COA: {origin}/pages/chemical-analysis",
        f"- FAQ: {origin}/pages/faq",
        f"- Contact: {origin}/pages/contact-1",
        "",
        "## Categories",
    ]
    lines += [f"- {c.get('title')}: {origin}/collections/{c['handle']}" for c in cols]
    lines += ["", "## Products (price in EUR)"]
    for p in prods:
        prices = [v.get("price_eur") for v in (p.get("variants") or []) if v.get("price_eur")]
        price = f" — from €{min(prices):.2f}" if prices else ""
        lines.append(f"- {p.get('title')}{price}: {origin}/products/{p['handle']}")
    lines += [
        "",
        "## Notes for agents",
        "- Currency: EUR (BGN shown in parallel on purepeptide.bg).",
        "- Localised storefronts: purepeptide.eu/en|fr|de|cz|hu|pl|sk|si, purepeptide.gr, purepeptide.ro.",
        "- Payment: bank transfer. Shipping: Speedy/Econt in Bulgaria, couriers across the EU.",
        "- Products are not medicinal products and are not for human or veterinary use.",
        "",
    ]
    return "\n".join(lines)


@api.api_route("/llms.txt", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def llms_txt():
    """llms.txt per llmstxt.org: one H1, a blockquote summary, then link sections (Markdown)."""
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    origin = (routes.get("bg") or SITE_ORIGINS["bg"])["origin"]
    cols = await db.collections_cat.find({"nav_hidden": {"$ne": True}}, {"_id": 0, "handle": 1, "title": 1}).sort("sort_order", 1).to_list(50)
    prods = await db.products.find({"active": {"$ne": False}},
                                   {"_id": 0, "handle": 1, "title": 1, "variants": 1, "seo_description": 1}).to_list(500)
    lines = [
        "# PurePeptide",
        "",
        "> Bulgarian supplier of lyophilised research peptides with >99% purity, verified by HPLC and",
        "> LC-MS at the independent laboratory Janoshik Analytical. All products are sold strictly for",
        "> laboratory and scientific research purposes (Research Use Only) and are not medicinal products.",
        "",
        "Prices below are in EUR (BGN in parallel on purepeptide.bg; RON, CZK, HUF and PLN on the local",
        "storefronts). Payment: cash on delivery or bank transfer. Shipping across the EU.",
        "",
        "## Store",
        f"- [Home]({origin}/): storefront entry point",
        f"- [All peptides]({origin}/collections/{await catalog_handle()}): the full catalogue with prices and stock",
        f"- [Lab analysis & COA]({origin}/pages/chemical-analysis): HPLC / LC-MS certificates per batch",
        f"- [Scientific articles]({origin}/pages/articles): research summaries per peptide",
        f"- [FAQ]({origin}/pages/faq): storage, reconstitution, delivery and payment questions",
        f"- [Contact]({origin}/pages/contact-1): e-mail, phone and contact form",
        "",
        "## Collections",
    ]
    lines += [f"- [{c.get('title')}]({origin}/collections/{c['handle']})" for c in cols]
    lines += ["", "## Products"]
    for p in prods:
        prices = [v.get("price_eur") for v in (p.get("variants") or []) if v.get("price_eur")]
        price = f" — from €{min(prices):.2f}" if prices else ""
        desc = re.sub(r"\s+", " ", (p.get("seo_description") or "")).strip()[:140]
        lines.append(f"- [{p.get('title')}{price}]({origin}/products/{p['handle']})" + (f": {desc}" if desc else ""))
    lines += [
        "",
        "## Optional",
        f"- [AI agent guide]({origin}/agents.md): longer machine-readable guide",
        f"- [XML sitemap]({origin}/sitemap.xml)",
        f"- [Agentic discovery sitemap]({origin}/sitemap_agentic_discovery.xml)",
        f"- [HTML sitemap]({origin}/pages/html-sitemap)",
        "",
    ]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8")


@api.api_route("/robots.txt", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def robots(request: Request):
    # ONE group for every crawler: separate per-bot groups replace the "*" group for that bot, so
    # the AI crawlers used to lose the /admin, /cart, /checkout and /account exclusions. The content
    # signals state the owner's policy — everything is allowed, training included.
    lines = [
        "User-agent: *",
        "Content-Signal: search=yes, ai-input=yes, ai-train=yes, use=full",
        "Allow: /",
        "Disallow: /admin",
        "Disallow: /checkout",
        "Disallow: /cart",
        "Disallow: /account",
        "",
    ]
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    routes = ((s or {}).get("value") or {}).get("locale_routes") or SITE_ORIGINS
    # a domain advertises its OWN sitemaps only — the other storefronts have their own robots.txt
    for origin in dict.fromkeys((routes.get(loc) or SITE_ORIGINS[loc])["origin"]
                                for loc in _host_locales(request, routes, LOCALES)):
        lines.append(f"Sitemap: {origin}/sitemap.xml")
        lines.append(f"Sitemap: {origin}/sitemap_agentic_discovery.xml")
    origin_bg = (routes.get("bg") or SITE_ORIGINS["bg"])["origin"]
    lines.append("")
    lines.append(f"# AI agent guide: {origin_bg}/agents.md")
    lines.append(f"# llms.txt: {origin_bg}/llms.txt")
    return PlainTextResponse("\n".join(lines), headers=SEO_CACHE)


# ---------- Mount + CORS ----------
from nextcart import router as nextcart_router  # noqa: E402
from geo import router as geo_router  # noqa: E402
import abandoned  # noqa: E402
import ui_strings  # noqa: E402

api.include_router(nextcart_router)
api.include_router(geo_router)
import nextlevel  # noqa: E402
import fulfillment  # noqa: E402
import wc_api  # noqa: E402
api.include_router(nextlevel.init(db, require_admin))
api.include_router(fulfillment.init(db, require_admin))
fulfillment.set_cancel_hook(_cancel_from_warehouse)
_wc_router = wc_api.init(db, fulfillment.get_config)
app.add_exception_handler(wc_api.WCError, wc_api.wc_error_handler)


@app.get("/wp-json")
@app.get("/wp-json/")
async def wp_json_index():
    """WordPress discovery document — WooCommerce clients probe it before calling wc/v3."""
    return {"name": "PurePeptide", "description": "PurePeptide store", "url": email_templates.base_url("bg"),
            "namespaces": ["wc/v3", "wc/v2", "wc/v1"], "authentication": {}, "routes": {"/wc/v3": {"namespace": "wc/v3"}}}
app.include_router(_wc_router, prefix="/wp-json/wc/v3")
app.include_router(_wc_router, prefix="/api/wc/wp-json/wc/v3")
api.include_router(abandoned.init(db, require_admin))
api.include_router(ui_strings.init(db, require_admin))

import prerender  # noqa: E402

prerender.init(db)


@api.get("/seo/prerender", include_in_schema=False)
async def seo_prerender(request: Request, path: str = "/"):
    """Finished HTML for a page request. 404 keeps its status (no soft 404); only a failure here
    (5xx) makes nginx fall back to the static shell."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    # sitemaps publish percent-encoded URLs (Cyrillic page slugs), so a crawler can ask for either
    result = await prerender.render(unquote(path), host)
    if not result:
        raise HTTPException(503, "prerender unavailable")
    body, status = result
    headers = {"X-Prerender": "1"}
    headers["Cache-Control"] = ("public, max-age=60, s-maxage=300" if status == 200
                                else "no-cache")
    return HTMLResponse(body, status_code=status, headers=headers)


@app.middleware("http")
async def _drop_prerender_cache(request: Request, call_next):
    """Any successful admin write makes the prerendered HTML stale."""
    response = await call_next(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400 \
            and "/admin/" in request.url.path:
        prerender.bump()
    return response


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
