"""Move any remaining remote assets (hero background, marquee brand logos) onto our own server."""

import os
import json
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

import storage  # noqa: E402
from matrixify_import import store_image  # noqa: E402

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
storage.init_storage()

HERO_SRC = "https://cdn.shopify.com/s/files/1/0941/8965/0294/files/brand-3_b5f4565b-7bec-41db-9d3b-7bbd1c49e2ac.png?v=1767112972"
HERO_DEST = ROOT.parent / "frontend" / "public" / "hero-home.png"

if not HERO_DEST.exists():
    resp = requests.get(HERO_SRC, timeout=90)
    resp.raise_for_status()
    HERO_DEST.write_bytes(resp.content)
    print(f"hero saved: {HERO_DEST} ({len(resp.content) // 1024} kB)")
else:
    print("hero already local")


def migrate(value):
    if isinstance(value, str) and value.startswith("http") and "cdn.shopify.com" in value:
        return store_image(value)
    if isinstance(value, list):
        return [migrate(v) for v in value]
    if isinstance(value, dict):
        return {k: migrate(v) for k, v in value.items()}
    return value


doc = db.settings.find_one({"key": "site"})
new_value = migrate(doc.get("value") or {})
if json.dumps(new_value, sort_keys=True) != json.dumps(doc.get("value") or {}, sort_keys=True):
    db.settings.update_one({"key": "site"}, {"$set": {"value": new_value}})
    print("settings assets migrated")
else:
    print("settings already local")

# final audit
pat = re.compile(r"https?://cdn\.shopify\.com[^\"'\s\\)]+", re.I)
for coll in db.list_collection_names():
    if coll == "image_map":
        continue
    hits = 0
    for d in db[coll].find():
        hits += len(pat.findall(json.dumps(d, default=str)))
    if hits:
        print(f"REMAINING in {coll}: {hits}")
print("audit done")
