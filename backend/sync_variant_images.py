"""Pull the real variant → image mapping from the live purepeptide.bg Shopify JSON.

Shopify exposes `/products/{handle}.js` with `variants[].featured_image`. Our imported images keep the
original Shopify filename as a suffix, so we can match them and store `variants[i].image`.
"""
import logging
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

log = logging.getLogger("variant_images")
UA = {"User-Agent": "Mozilla/5.0 (compatible; PurePeptideMigrator/1.0)"}


def run() -> dict:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    report = {"updated": [], "skipped": [], "missing_live": []}
    for p in db.products.find({}, {"_id": 0, "handle": 1, "variants": 1, "images": 1, "image": 1}):
        variants = p.get("variants") or []
        if len(variants) < 2:
            continue
        try:
            r = requests.get(f"https://purepeptide.bg/products/{p['handle']}.js", headers=UA, timeout=25)
        except Exception as ex:
            report["missing_live"].append(f"{p['handle']}: {ex}")
            continue
        if not r.ok:
            report["missing_live"].append(f"{p['handle']}: HTTP {r.status_code}")
            continue
        live = r.json()
        by_title = {}
        for v in live.get("variants", []):
            src = ((v.get("featured_image") or {}).get("src") or "").split("?")[0].split("/")[-1]
            if src:
                by_title[str(v.get("title", "")).strip().lower()] = src

        ours = p.get("images") or ([p["image"]] if p.get("image") else [])
        changed = False
        for i, v in enumerate(variants):
            name = str(v.get("name", "")).strip().lower()
            fname = by_title.get(name)
            if not fname:
                continue
            stem = fname.rsplit(".", 1)[0]
            match = next((u for u in ours if stem in u), None)
            if match and v.get("image") != match:
                variants[i]["image"] = match
                changed = True
        if changed:
            db.products.update_one({"handle": p["handle"]}, {"$set": {"variants": variants}})
            report["updated"].append({p["handle"]: [{v.get("name"): (v.get("image") or "")[-30:]} for v in variants]})
        else:
            report["skipped"].append(p["handle"])
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=1))
