"""Generate the per-domain RevOrder credentials (api_key + secret_key) and print them once.

Usage: python gen_revorder_keys.py [--force]
Existing keys are kept unless --force is passed.
"""
import asyncio
import os
import secrets
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DOMAINS = ["purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr"]
SETTINGS_KEY = "integrations.revorder"
DEFAULT_BASE = os.environ["NEXTCART_BASE_URL"]


async def main(force: bool) -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    doc = await db.settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    domains = ((doc or {}).get("value") or {}).get("domains") or {}
    for d in DOMAINS:
        cur = domains.get(d, {})
        if force or not cur.get("api_key"):
            cur["api_key"] = f"pp_live_{secrets.token_hex(20)}"
        if force or not cur.get("secret_key"):
            cur["secret_key"] = f"pps_{secrets.token_hex(32)}"
        cur.setdefault("api_base", DEFAULT_BASE)
        cur.setdefault("orders_path", "/api/orders")
        if not cur.get("webhook_url"):
            cur["webhook_url"] = f"https://{d}/api/webhooks/revorder/{d}"
        cur.setdefault("enabled", False)
        domains[d] = cur
    await db.settings.update_one(
        {"key": SETTINGS_KEY},
        {"$set": {"value": {"domains": domains}, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    for d in DOMAINS:
        c = domains[d]
        print(f"\n=== {d} ===")
        print(f"API key    : {c['api_key']}")
        print(f"Secret key : {c['secret_key']}")
        print(f"Webhook URL: {c['webhook_url']}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main("--force" in sys.argv))
