"""Move every remaining image into our own object storage.

* uploads the site media that still lives in frontend/public (hero, logos, OG image)
* downloads and re-hosts any external image URL found in the CMS content (Shopify CDN etc.)
* records everything in `files` so /api/files/<path> can serve WebP/JPEG variants
* stores the site media map in settings.value.media

Usage: python migrate_media_to_storage.py
"""
import asyncio
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")
import storage  # noqa: E402

PUBLIC = Path(__file__).resolve().parent.parent / "frontend" / "public"
SITE_MEDIA = {
    "hero": "hero-home.webp",
    "logo": "logo-header.png",
    "logo_light": "logo-white.svg",
    "og": "og-image.jpg",
}
EXT_URL = re.compile(r'https?://[^\s"\'<>)]+?\.(?:png|jpe?g|webp|gif|avif)(?:\?[^\s"\'<>)]*)?', re.I)
CONTENT_COLLECTIONS = ["products", "collections", "articles", "pages", "settings"]


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower().split("?")[0]


async def _register(db, path: str, filename: str, content_type: str, size: int) -> None:
    await db.files.update_one(
        {"storage_path": path},
        {"$setOnInsert": {
            "id": str(uuid.uuid4()),
            "storage_path": path,
            "original_filename": filename,
            "content_type": content_type,
            "size": size,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by": "migration",
        }},
        upsert=True,
    )


async def upload_bytes(db, data: bytes, filename: str, prefix: str) -> str:
    ext = _ext(filename)
    content_type = storage.MIME_TYPES.get(ext, "application/octet-stream")
    digest = hashlib.sha1(data).hexdigest()[:12]
    path = f"{storage.APP_NAME}/{prefix}/{digest}-{re.sub(r'[^A-Za-z0-9._-]+', '-', filename)[:70]}"
    existing = await db.files.find_one({"storage_path": path})
    if not existing:
        result = storage.put_object(path, data, content_type)
        path = result.get("path", path)
        await _register(db, path, filename, content_type, result.get("size", len(data)))
    return f"/api/files/{path}"


async def migrate_site_media(db) -> dict:
    media = {}
    for key, name in SITE_MEDIA.items():
        src = PUBLIC / name
        if not src.exists():
            print(f"  skip {name} (missing)")
            continue
        media[key] = await upload_bytes(db, src.read_bytes(), name, "site")
        print(f"  {name} -> {media[key]}")
    return media


async def _replace_in(db, value, mapping: dict):
    if isinstance(value, str):
        out = value
        for old, new in mapping.items():
            out = out.replace(old, new)
        return out
    if isinstance(value, list):
        return [await _replace_in(db, v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: await _replace_in(db, v, mapping) for k, v in value.items()}
    return value


async def migrate_external(db) -> int:
    fixed = 0
    for coll in CONTENT_COLLECTIONS:
        async for doc in db[coll].find({}):
            doc_id = doc.pop("_id")
            raw = json.dumps(doc, ensure_ascii=False, default=str)
            urls = {u for u in EXT_URL.findall(raw) if "/api/files/" not in u}
            if not urls:
                continue
            mapping = {}
            for url in urls:
                try:
                    resp = requests.get(url, timeout=60)
                    resp.raise_for_status()
                except Exception as ex:
                    print(f"  ! download failed {url}: {ex}")
                    continue
                name = url.split("/")[-1].split("?")[0] or f"{uuid.uuid4()}.jpg"
                mapping[url] = await upload_bytes(db, resp.content, name, "content")
                fixed += 1
                print(f"  {coll}: {url[:60]}… -> {mapping[url]}")
            if not mapping:
                continue
            update = {}
            for key, value in doc.items():
                new_value = await _replace_in(db, value, mapping)
                if new_value != value:
                    update[key] = new_value
            if update:
                await db[coll].update_one({"_id": doc_id}, {"$set": update})
    return fixed


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    storage.init_storage()
    print("Site media:")
    media = await migrate_site_media(db)
    print("External content images:")
    count = await migrate_external(db)
    if media:
        await db.settings.update_one({"key": "site"}, {"$set": {"value.media": media}}, upsert=True)
    print(f"\nDone. Site media: {len(media)} · re-hosted external images: {count}")


if __name__ == "__main__":
    asyncio.run(main())
