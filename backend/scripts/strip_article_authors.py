"""Clear the by-line on every article — the owner wants no author names on the site.

Idempotent: run it again after any import.
"""
import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    res = await db.articles.update_many({"author": {"$nin": [None, ""]}}, {"$set": {"author": ""}})
    left = await db.articles.count_documents({"author": {"$nin": [None, ""]}})
    print(f"cleared {res.modified_count} by-lines, {left} left")


if __name__ == "__main__":
    asyncio.run(main())
