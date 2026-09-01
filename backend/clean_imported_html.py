"""Strip the duplicate H1 headings out of already-imported Shopify HTML (products, collections, pages, articles)."""

import os
from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient

load_dotenv(Path(__file__).parent / ".env")
from matrixify_import import clean_body  # noqa: E402

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

TARGETS = [
    ("products", "description", "title"),
    ("collections_cat", "description", "title"),
    ("pages", "html", "title"),
    ("articles", "body", "title"),
]

for coll, field, title_field in TARGETS:
    changed = 0
    for doc in db[coll].find({field: {"$regex": "<h1", "$options": "i"}}):
        cleaned = clean_body(doc.get(field) or "", doc.get(title_field) or "")
        if cleaned != doc.get(field):
            db[coll].update_one({"_id": doc["_id"]}, {"$set": {field: cleaned}})
            changed += 1
    print(f"{coll}.{field}: {changed} cleaned")
