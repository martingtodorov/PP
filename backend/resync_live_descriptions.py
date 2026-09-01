"""Pull the newest product descriptions from the live purepeptide.bg (Shopify /products/{handle}.js).

Some products were edited on the live store after the Matrixify export, so the export is shorter.
Keeps the heading but demotes <h1> to <h2> (the page renders its own H1).
"""
import logging
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

log = logging.getLogger("resync_desc")
UA = {"User-Agent": "Mozilla/5.0 (compatible; PurePeptideMigrator/1.0)"}


def demote_h1(html: str) -> str:
    html = re.sub(r"<h1(\s[^>]*)?>", lambda m: f"<h2{m.group(1) or ''}>", html, flags=re.I)
    return re.sub(r"</h1>", "</h2>", html, flags=re.I)


def run() -> dict:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    out = {"updated": [], "unchanged": [], "no_live": []}
    for p in db.products.find({}, {"_id": 0, "handle": 1, "description": 1}):
        try:
            r = requests.get(f"https://purepeptide.bg/products/{p['handle']}.js", headers=UA, timeout=25)
        except Exception as ex:
            out["no_live"].append(f"{p['handle']}: {ex}")
            continue
        if not r.ok:
            out["no_live"].append(f"{p['handle']}: HTTP {r.status_code}")
            continue
        live = demote_h1((r.json().get("description") or "").strip())
        ours = p.get("description") or ""
        if live and len(live) > len(ours):
            db.products.update_one({"handle": p["handle"]}, {"$set": {"description": live}})
            out["updated"].append({p["handle"]: f"{len(ours)} -> {len(live)}"})
        else:
            out["unchanged"].append(p["handle"])
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=1))
