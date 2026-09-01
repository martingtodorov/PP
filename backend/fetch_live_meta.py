"""Fill any missing meta title / description by reading them from the live purepeptide.bg pages."""

import html as html_lib
import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent / ".env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

BASE = "https://purepeptide.bg"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PurePeptideMigration/1.0)"}

SHOPIFY_PAGE_HANDLE = {
    "what-are-peptides": "какво-са-пептиди",
    "chemical-analysis": "chemical-analysis",
    "faq": "faq",
    "contacts": "contact-1",
    "partners": "become-a-distributor",
    "about": "about-1",
    "cookies": "cookies",
    "privacy-policy": "data-sharing-opt-out",
    "terms-of-service": "terms-conditions",
    "shipping-policy": "delivery-and-payment",
    "scientific-literature": "scientific-literature",
}


def fetch_meta(url: str):
    try:
        r = requests.get(url, timeout=25, headers=HEADERS)
        if r.status_code != 200:
            return None, None
    except Exception:
        return None, None
    title = re.search(r"<title>(.*?)</title>", r.text, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', r.text, re.S)
    clean = lambda m: re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip() if m else None
    return clean(title), clean(desc)


def fill(collection: str, query: dict, url_builder, label_field: str):
    for doc in db[collection].find(query):
        url = url_builder(doc)
        if not url:
            continue
        title, desc = fetch_meta(url)
        update = {}
        if title and not doc.get("seo_title"):
            update["seo_title"] = title
        if desc and not doc.get("seo_description"):
            update["seo_description"] = desc
        if update:
            db[collection].update_one({"_id": doc["_id"]}, {"$set": update})
            print(f"{collection}: {doc.get(label_field)} → {list(update)}")
        else:
            print(f"{collection}: {doc.get(label_field)} → nothing found at {url}")


missing = {"$or": [{"seo_title": {"$in": ["", None]}}, {"seo_description": {"$in": ["", None]}}]}

fill("products", missing, lambda d: f"{BASE}/products/{d['handle']}", "handle")
fill("collections_cat", missing, lambda d: f"{BASE}/collections/{d['handle']}" if d["handle"] != "all-peptides" else f"{BASE}/collections/2all-the-peptides-1", "handle")
fill("pages", {"locale": "bg", **missing},
     lambda d: f"{BASE}/pages/{SHOPIFY_PAGE_HANDLE[d['slug']]}" if d["slug"] in SHOPIFY_PAGE_HANDLE else None, "slug")
fill("articles", missing, lambda d: f"{BASE}/blogs/news/{d['handle']}", "handle")

for coll, field in [("products", "handle"), ("collections_cat", "handle"), ("articles", "handle")]:
    left = db[coll].count_documents(missing)
    print(f"still missing in {coll}: {left}")
print("bg pages still missing:", db.pages.count_documents({"locale": "bg", **missing}))
