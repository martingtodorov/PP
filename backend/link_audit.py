"""Dead-link report: crawl the storefront the way Google sees it (the prerendered HTML) and list
every internal URL that does not answer 200. Read-only — it never changes content."""
import logging
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import unquote, urljoin, urlsplit

import prerender
from i18n import SITE_ORIGINS

log = logging.getLogger("purepeptide.linkaudit")
HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)
SKIP_PREFIX = ("/api/", "/admin", "/cart", "/checkout", "/account")
FILE_RE = re.compile(r"\.(xml|json|txt|pdf|png|jpe?g|svg|webp|ico|css|js|woff2?)$", re.IGNORECASE)
MAX_PAGES = 400
_db = None


def init(db) -> None:
    global _db
    _db = db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _own_hosts() -> set:
    return {urlsplit(route["origin"]).netloc for route in SITE_ORIGINS.values()}


def _internal_path(href: str, base: str, hosts: set) -> str:
    """The site-relative path of an internal link, or "" when the link leaves the shop."""
    if href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return ""
    parts = urlsplit(urljoin(base, href))
    if parts.netloc and parts.netloc not in hosts:
        return ""
    path = unquote(parts.path or "/")
    if not path.startswith("/") or path.startswith(SKIP_PREFIX) or FILE_RE.search(path):
        return ""
    return path


async def run(job_id: str, locale: str, limit: int) -> Dict[str, Any]:
    host = urlsplit(SITE_ORIGINS.get(locale, SITE_ORIGINS["bg"])["origin"]).netloc
    hosts = _own_hosts()
    limit = max(1, min(limit, MAX_PAGES))
    seen: set = set()
    parents: Dict[str, str] = {"/": ""}
    queue: deque = deque(["/"])
    broken: List[Dict[str, Any]] = []
    try:
        while queue and len(seen) < limit:
            path = queue.popleft()
            if path in seen:
                continue
            seen.add(path)
            rendered = await prerender.render(path, host)
            if not rendered:
                continue                      # the shell answers this route (private page, asset)
            html, status = rendered
            if status != 200:
                broken.append({"path": path, "status": status, "found_on": parents.get(path, "")})
                continue
            for href in HREF.findall(html):
                nxt = _internal_path(href, f"https://{host}{path}", hosts)
                if nxt and nxt not in seen and nxt not in parents:
                    parents[nxt] = path
                    queue.append(nxt)
            if len(seen) % 20 == 0:
                await _db.link_audits.update_one({"id": job_id}, {"$set": {
                    "crawled": len(seen), "broken": broken, "updated_at": _now()}})
        result = {"status": "done", "crawled": len(seen), "queued_left": len(queue),
                  "broken": broken, "finished_at": _now(), "updated_at": _now()}
    except Exception as ex:
        log.exception("link audit %s crashed", job_id)
        result = {"status": "failed", "error": str(ex), "crawled": len(seen), "broken": broken,
                  "finished_at": _now(), "updated_at": _now()}
    await _db.link_audits.update_one({"id": job_id}, {"$set": result})
    return result
