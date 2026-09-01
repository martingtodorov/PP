"""Align our URLs with the live purepeptide.bg URLs.

- collection `all-peptides` -> `2all-the-peptides-1`
- page slugs renamed to the live ones (contact-1, about-1, become-a-distributor, …)
- the imported Shopify 301 redirects are removed (the owner does not want them)
- the missing live collection `retatrutide-price` is created from the live page
"""
import logging
import os
import re
import sys
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

log = logging.getLogger("align_urls")

OLD_ALL = "all-peptides"
NEW_ALL = "2all-the-peptides-1"
SLUG_MAP = {
    "contacts": "contact-1",
    "partners": "become-a-distributor",
    "about": "about-1",
    "terms-of-service": "terms-conditions",
    "shipping-policy": "delivery-and-payment",
    "what-are-peptides": "какво-са-пептиди",
}
UA = {"User-Agent": "Mozilla/5.0 (compatible; PurePeptideMigrator/1.0)"}


def fetch_live_collection(handle: str) -> dict:
    r = requests.get(f"https://purepeptide.bg/collections/{handle}", headers=UA, timeout=30)
    r.raise_for_status()
    html = r.text
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
    body = re.search(r'<div class="[^"]*collection__description[^"]*"[^>]*>(.*?)</div>', html, re.S)
    clean = lambda s: re.sub(r"\s+", " ", (s or "")).replace("&ndash;", "–").strip()
    return {
        "seo_title": clean(title.group(1) if title else "").replace(" – PurePeptide", ""),
        "seo_description": clean(desc.group(1) if desc else ""),
        "body_html": (body.group(1).strip() if body else ""),
    }


def run() -> dict:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    out = {}

    # 1. all-peptides -> 2all-the-peptides-1
    out["collection_renamed"] = db.collections_cat.update_one(
        {"handle": OLD_ALL}, {"$set": {"handle": NEW_ALL}}
    ).modified_count
    moved = 0
    for p in db.products.find({"collections": OLD_ALL}, {"id": 1, "collections": 1}):
        cols = [NEW_ALL if c == OLD_ALL else c for c in p.get("collections", [])]
        db.products.update_one({"id": p["id"]}, {"$set": {"collections": cols}})
        moved += 1
    out["products_recollected"] = moved

    # 2. page slugs -> live slugs
    renamed = {}
    for old, new in SLUG_MAP.items():
        n = db.pages.update_many({"slug": old}, {"$set": {"slug": new}}).modified_count
        if n:
            renamed[f"{old}->{new}"] = n
    out["pages_renamed"] = renamed

    # 3. drop the imported Shopify redirects
    out["redirects_removed"] = db.delisted_links.delete_many({"created_by": "matrixify-import"}).deleted_count

    # 4. missing live collection: retatrutide-price
    if not db.collections_cat.find_one({"handle": "retatrutide-price"}):
        meta = fetch_live_collection("retatrutide-price")
        prods = list(db.products.find(
            {"$or": [{"handle": {"$regex": "retatrutide", "$options": "i"}},
                     {"title": {"$regex": "retatrutide|ретатрутид", "$options": "i"}}]},
            {"id": 1, "handle": 1, "image": 1},
        ))
        db.collections_cat.insert_one({
            "id": str(uuid.uuid4()),
            "handle": "retatrutide-price",
            "title": "Retatrutide (Ретатрутид)",
            "description": meta["body_html"] or meta["seo_description"],
            "image": (prods[0].get("image") if prods else ""),
            "sort_order": 99,
            "nav_hidden": True,
            "seo_title": meta["seo_title"],
            "seo_description": meta["seo_description"],
            "translations": {},
        })
        for p in prods:
            db.products.update_one({"id": p["id"]}, {"$addToSet": {"collections": "retatrutide-price"}})
        out["retatrutide_price"] = {"created": True, "products": [p["handle"] for p in prods], **meta}
    else:
        out["retatrutide_price"] = {"created": False}

    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=1))
