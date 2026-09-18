"""Изчиства импортираните данни (каталог, съдържание, клиенти, поръчки) от ТАЗИ база.

Ползва се само в preview/споделена среда — продукцията не се пипа. След пускането рестартирай
бекенда: seed-ът на кода попълва демо каталога отново.

    python scripts/purge_preview_data.py --yes
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

WIPE = [
    "products", "collections_cat", "pages", "articles", "product_orders",
    "redirects", "delisted_links", "rotation_log",
    "files", "image_map", "import_jobs", "imports",
    "customers", "orders", "abandoned_carts", "inventory_log", "shipments",
    "contact_messages", "translate_jobs", "integration_events", "wc_api_log",
    "daily_reports", "visits", "audit",
]

if "--yes" not in sys.argv:
    sys.exit("добави --yes, за да потвърдиш изтриването")

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
for name in WIPE:
    print(f"{name}: {db[name].delete_many({}).deleted_count} изтрити")

db.settings.update_one({"key": "site"}, {"$unset": {"value.catalog_imported": "",
                                                    "value.catalog_imported_at": ""}})
db.migrations.delete_many({"key": {"$in": ["restore_body_headings", "adopt_imported_redirects"]}})
print("готово — рестартирай бекенда")
