"""Manual, fail-closed cleanup of a verified LOCAL privacy-preview. Never called by startup/deploy.

Dry run: python scripts/purge_preview_data.py --expected-db <local DB_NAME>
Execute: add --execute --confirm-preview-cleanup after reviewing the counts.
No production targets, network storage, remote MongoDB, or whole-database drops are supported.
"""
import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values, load_dotenv
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri

BACKEND = Path(__file__).resolve().parents[1]
WIPE = (
    "products", "collections_cat", "pages", "articles", "product_orders", "redirects",
    "delisted_links", "rotation_log", "files", "image_map", "import_jobs", "imports",
    "customers", "orders", "abandoned_carts", "inventory_log", "shipments", "contact_messages",
    "translate_jobs", "integration_events", "wc_api_log", "daily_reports", "visits", "audit",
    "migrations", "push_subscriptions", "fx_rates", "sessions", "refresh_tokens",
)


def validate_target(env, expected_db, preview_url, backend=BACKEND):
    if env.get("APP_ENV") != "privacy-preview" or env.get("PREVIEW_ONLY") != "true":
        raise ValueError("Refusing cleanup outside explicitly enabled privacy-preview")
    if env.get("ALLOW_MANAGED_STORAGE") != "false":
        raise ValueError("Managed storage must be disabled before cleanup")
    if not expected_db or expected_db != env.get("DB_NAME"):
        raise ValueError("The explicitly confirmed database does not match DB_NAME")
    host = urlsplit(preview_url).hostname or ""
    if not host.endswith(".preview.emergentagent.com"):
        raise ValueError("Refusing cleanup without the configured preview origin")
    uri = env["MONGO_URL"]
    if not uri.startswith("mongodb://"):
        raise ValueError("Only standalone loopback MongoDB is supported")
    parsed = parse_uri(uri)
    if len(parsed["nodelist"]) != 1:
        raise ValueError("Refusing multi-host MongoDB target; exactly one loopback host is required")
    if any(host not in ("localhost", "127.0.0.1", "::1") for host, _ in parsed["nodelist"]):
        raise ValueError("Refusing a non-loopback MongoDB target")
    if parsed.get("database") and parsed["database"] != expected_db:
        raise ValueError("URI database differs from the confirmed database")
    if any(str(k).lower() in ("replicaset", "loadbalanced", "proxyhost") for k in parsed["options"]):
        raise ValueError("Replica/proxy connections are not allowed for this cleanup")
    media = Path(env["MEDIA_ROOT"])
    if media.is_symlink() or media.resolve() != (backend / ".media").resolve():
        raise ValueError("MEDIA_ROOT must be this checkout's local .media directory")
    for relative in (".media", ".image_cache", "data"):
        candidate = backend / relative
        if candidate.is_symlink() or candidate.resolve().parent != backend.resolve():
            raise ValueError("Refusing a linked or external runtime data directory")
    return uri


def clean_database(db, admin_email, settings):
    """Explicit allowlist; retain the configured technical admin's complete credential record."""
    admin = db.users.find_one({"email": admin_email, "role": "admin"})
    if not admin or not admin.get("id"):
        raise ValueError("Configured preview administrator not found; no data was deleted")
    unknown = set(db.list_collection_names()) - set(WIPE) - {"users", "settings"}
    if any(db[name].count_documents({}) for name in unknown):
        raise ValueError("Unreviewed collections present; no data was deleted")
    counts = {name: db[name].delete_many({}).deleted_count for name in WIPE}
    counts["users"] = db.users.delete_many({"id": {"$ne": admin["id"]}}).deleted_count
    counts["settings"] = db.settings.delete_many({}).deleted_count
    db.settings.insert_one({"key": "site", "value": settings.copy()})
    if db.users.find_one({"id": admin["id"]}) != admin:
        raise RuntimeError("Preview admin preservation check failed")
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-db", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-preview-cleanup", action="store_true")
    parser.add_argument("--seed-demo", action="store_true", help="Reinitialize only fictional fixtures after cleanup")
    args = parser.parse_args()
    load_dotenv(BACKEND / ".env")
    frontend = dotenv_values(BACKEND.parent / "frontend/.env")
    uri = validate_target(os.environ, args.expected_db, frontend["REACT_APP_BACKEND_URL"])
    with MongoClient(uri, serverSelectionTimeoutMS=3000) as client:
        hello = client.admin.command("hello")
        if hello.get("setName") or hello.get("msg") == "isdbgrid":
            raise ValueError("Refusing a replica set or cluster even when the seed address is local")
        db = client[args.expected_db]
        if not args.execute:
            print("DRY RUN: standalone loopback preview confirmed; no writes")
            for name in WIPE:
                print(name, db[name].count_documents({}))
            return
        if not args.confirm_preview_cleanup:
            raise ValueError("Execution requires explicit --confirm-preview-cleanup")
        sys.path.insert(0, str(BACKEND))
        from seed_data import DEFAULT_SETTINGS
        preview_settings = {**DEFAULT_SETTINGS, "media": {"hero": "/demo-fixture.svg", "og": "/demo-fixture.svg"}}
        counts = clean_database(db, os.environ["ADMIN_EMAIL"], preview_settings)
        for relative in (".media", ".image_cache", "data"):
            root = BACKEND / relative
            if root.exists():
                shutil.rmtree(root)
        if args.seed_demo:
            if os.environ.get("ENABLE_DEMO_DATA") != "true":
                raise ValueError("Fictional fixtures require explicit ENABLE_DEMO_DATA=true")
            from server import seed_catalog, seed_pages

            async def seed():
                await seed_catalog()
                await seed_pages()

            asyncio.run(seed())
        print("Preview cleanup complete; preserved the configured admin; record counts only:", counts)


if __name__ == "__main__":
    main()