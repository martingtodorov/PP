"""PurePeptide backend - FastAPI + Motor + JWT auth + bank-transfer commerce."""

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import csv
import io
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from seed_data import COLLECTIONS, PRODUCTS, ARTICLES, DEFAULT_SETTINGS

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


class CollectionIn(BaseModel):
    handle: str
    title: str
    title_en: Optional[str] = ""
    description: str = ""
    image: str = ""
    sort_order: int = 0


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
    if await db.collections_cat.count_documents({}) == 0:
        for c in COLLECTIONS:
            await db.collections_cat.insert_one({
                "id": str(uuid.uuid4()),
                "created_at": now_utc(),
                **c,
            })
        log.info("Seeded %d collections", len(COLLECTIONS))

    if await db.products.count_documents({}) == 0:
        for p in PRODUCTS:
            doc = {
                "id": str(uuid.uuid4()),
                "created_at": now_utc(),
                "featured": False,
                "images": p.get("images", [p["image"]]),
                **p,
            }
            await db.products.insert_one(doc)
        log.info("Seeded %d products", len(PRODUCTS))

    if await db.articles.count_documents({}) == 0:
        for a in ARTICLES:
            await db.articles.insert_one({
                "id": str(uuid.uuid4()),
                "published_at": now_utc(),
                **a,
            })

    if not await db.settings.find_one({"key": "site"}):
        await db.settings.insert_one({"key": "site", "value": DEFAULT_SETTINGS, "updated_at": now_utc()})


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("handle", unique=True)
    await db.products.create_index("id", unique=True)
    await db.collections_cat.create_index("handle", unique=True)
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index("order_number", unique=True)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()
    await seed_admin()
    await seed_catalog()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ---------- Auth routes ----------
@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Имейлът вече е регистриран")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "phone": payload.phone,
        "role": "customer",
        "created_at": now_utc(),
    }
    await db.users.insert_one(user)
    token = create_token(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return {"user": public_user(user), "token": token}


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
async def list_collections():
    docs = await db.collections_cat.find({}, {"_id": 0}).sort("sort_order", 1).to_list(100)
    return {"collections": docs}


@api.get("/collections/{handle}")
async def get_collection(handle: str):
    col = await db.collections_cat.find_one({"handle": handle}, {"_id": 0})
    if not col:
        raise HTTPException(404, "Колекцията не е намерена")
    if handle == "all-peptides":
        prods = await db.products.find({}, {"_id": 0}).to_list(500)
    else:
        prods = await db.products.find({"collections": handle}, {"_id": 0}).to_list(500)
    return {"collection": col, "products": prods}


@api.get("/products")
async def list_products(featured: Optional[bool] = None, search: Optional[str] = None, limit: int = 100):
    q: Dict[str, Any] = {}
    if featured is not None:
        q["featured"] = featured
    if search:
        q["title"] = {"$regex": search, "$options": "i"}
    docs = await db.products.find(q, {"_id": 0}).limit(limit).to_list(limit)
    return {"products": docs}


@api.get("/products/{handle}")
async def get_product(handle: str):
    p = await db.products.find_one({"handle": handle}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Продуктът не е намерен")
    related = await db.products.find(
        {"handle": {"$ne": handle}, "collections": {"$in": p.get("collections", [])}},
        {"_id": 0},
    ).limit(4).to_list(4)
    return {"product": p, "related": related}


@api.get("/articles")
async def list_articles():
    docs = await db.articles.find({}, {"_id": 0}).to_list(50)
    return {"articles": docs}


@api.get("/settings")
async def get_settings():
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    return s["value"] if s else DEFAULT_SETTINGS


# ---------- Checkout / Orders ----------
async def _next_order_number() -> str:
    count = await db.orders.count_documents({})
    return f"PP-{1000 + count + 1}"


def _calc_totals(line_items: List[Dict[str, Any]], shipping_method: str) -> Dict[str, float]:
    subtotal = sum(li["price_eur"] * li["quantity"] for li in line_items)
    shipping_cost = 0.0 if subtotal >= 100 else (5.99 if shipping_method != "speedy" else 7.49)
    total = subtotal + shipping_cost
    return {"subtotal_eur": round(subtotal, 2), "shipping_eur": shipping_cost, "total_eur": round(total, 2)}


@api.post("/checkout")
async def checkout(payload: CheckoutIn, request: Request):
    if not payload.items:
        raise HTTPException(400, "Количката е празна")

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

    totals = _calc_totals(line_items, payload.shipping_method)
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

    # decrement stock
    for li in line_items:
        await db.products.update_one(
            {"id": li["product_id"], "variants.sku": li["variant_sku"]},
            {"$inc": {"variants.$.stock": -li["quantity"]}},
        )

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


@api.get("/admin/orders")
async def admin_orders(status: Optional[str] = None, user=Depends(require_admin)):
    q: Dict[str, Any] = {}
    if status == "awaiting_payment":
        q["payment_status"] = "awaiting_payment"
    elif status == "paid":
        q["payment_status"] = "paid"
    elif status == "shipped":
        q["fulfillment_status"] = "shipped"
    elif status == "fulfilled":
        q["fulfillment_status"] = {"$in": ["fulfilled", "shipped"]}
    docs = await db.orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"orders": docs}


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
    return {"ok": True, "tracking": tracking}


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
    docs = await db.users.find({"role": "customer"}, {"_id": 0, "password_hash": 0}).to_list(500)
    # attach order counts
    for d in docs:
        d["orders_count"] = await db.orders.count_documents({"customer_id": d["id"]})
    return {"customers": docs}


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


@api.get("/admin/imports")
async def admin_imports_log(user=Depends(require_admin)):
    docs = await db.imports.find({}, {"_id": 0}).sort("at", -1).limit(50).to_list(50)
    return {"imports": docs}


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
