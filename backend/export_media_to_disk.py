"""Pull every stored file onto the local media disk (MEDIA_ROOT).

Run once after a fresh deploy (or after switching servers) so the site serves all
images from its own disk and no longer depends on the managed object storage.

Usage: python export_media_to_disk.py [--force]
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")
import storage  # noqa: E402


async def main(force: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    storage.init_storage()
    total = ok = skipped = failed = 0
    async for rec in db.files.find({"is_deleted": False}, {"_id": 0, "storage_path": 1}):
        path = rec["storage_path"]
        total += 1
        target = storage.MEDIA_ROOT / path
        if target.exists() and not force:
            skipped += 1
            continue
        try:
            storage.get_object(path)  # writes through to MEDIA_ROOT
            ok += 1
        except Exception as ex:
            failed += 1
            print(f"  ! {path}: {ex}")
    size = sum(f.stat().st_size for f in storage.MEDIA_ROOT.rglob("*") if f.is_file())
    print(f"files: {total} · downloaded: {ok} · already on disk: {skipped} · failed: {failed}")
    print(f"{storage.MEDIA_ROOT} = {size / 1_048_576:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main("--force" in sys.argv))
