"""Put the Shopify body heading ("Какво е Ретатрутид?") back at the top of every product description.

Earlier imports dropped the body's own <h1> because the page already had a title. The live
purepeptide.bg shows that heading as the H1 and the product name as an H2, and the owner wants the
same, so the heading is restored from the Matrixify export without touching anything else on the
product (uploaded pictures, prices, translations). Idempotent — runs at every startup.
"""
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

from starlette.concurrency import run_in_threadpool

log = logging.getLogger("purepeptide.headings")
BUNDLED_XLSX = Path(__file__).parent / "data" / "matrixify-export.xlsx"
_H1 = re.compile(r"^\s*<h1[^>]*>(.*?)</h1>", re.I | re.S)


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", re.sub(r"<[^>]+>", "", text or "").lower())


def body_headings(source) -> Dict[str, str]:
    """Product handle -> raw leading <h1> text of its Shopify body."""
    import openpyxl

    wb = openpyxl.load_workbook(source, read_only=True)
    ws = wb["Products"]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    ih, ib = header.index("Handle"), header.index("Body HTML")
    out: Dict[str, str] = {}
    for row in rows:
        handle, body = row[ih], row[ib]
        if not handle or not body or str(handle) in out:
            continue
        m = _H1.match(str(body))
        if m:
            heading = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if heading:
                out[str(handle).strip()] = heading
    return out


async def _latest_export(db, storage) -> Optional[bytes]:
    job = await db.import_jobs.find_one({"type": "matrixify", "status": "completed"},
                                        {"_id": 0, "storage_path": 1}, sort=[("at", -1)])
    if not job or not job.get("storage_path"):
        return None
    try:
        blob, _ = await run_in_threadpool(storage.get_object, job["storage_path"])
        return blob
    except Exception:
        return None


async def restore_product_headings(db, storage) -> int:
    blob = await _latest_export(db, storage)
    source = BytesIO(blob) if blob else BUNDLED_XLSX
    if not blob and not BUNDLED_XLSX.exists():
        return 0
    headings = await run_in_threadpool(body_headings, source)
    fixed = 0
    for handle, heading in headings.items():
        doc = await db.products.find_one({"handle": handle}, {"_id": 1, "description": 1})
        if not doc:
            continue
        desc = doc.get("description") or ""
        if _H1.match(desc) or _norm(heading) in _norm(desc[:400]):
            continue
        await db.products.update_one(
            {"_id": doc["_id"]}, {"$set": {"description": f"<h1>{heading}</h1>\n{desc}"}})
        fixed += 1
    if fixed:
        log.info("Restored the body heading on %s products", fixed)
    return fixed
