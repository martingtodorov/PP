"""Contextual internal links: a peptide named in an article links to its live product page.

Applied while the copy is served (API + prerendered HTML) and never stored, so the link always
points at the handle that is published right now — a rotation can never leave a dead link behind.
"""
import re
import time
from typing import Callable, Dict, List, Optional, Tuple

from i18n import published_handle

MAX_LINKS = 6          # per article, so the copy stays readable
MIN_ALIAS = 4
TTL = 300
SKIP_TAGS = ("a", "h1", "h2", "h3", "script", "style", "button")
_cache: Dict[str, Tuple[float, List[Tuple[str, str]]]] = {}
_db = None


def init(db) -> None:
    global _db
    _db = db


def clear() -> None:
    _cache.clear()


def aliases_of(title: str) -> List[str]:
    """„Ретатрутид (Retatrutide) 5mg" -> ["Ретатрутид", "Retatrutide"] — the names people write."""
    out: List[str] = []
    inside = re.findall(r"\(([^)]+)\)", title or "")
    stem = re.split(r"[|,–—]| \d", re.sub(r"\([^)]*\)", " ", title or ""))[0]
    for candidate in [stem] + inside:
        name = candidate.strip(" .,:;")
        if len(name) >= MIN_ALIAS and not name.isdigit():
            out.append(name)
    return out


async def targets(locale: str) -> List[Tuple[str, str]]:
    """(alias, path) for every active product, longest alias first."""
    hit = _cache.get(locale)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    pairs: List[Tuple[str, str]] = []
    async for p in _db.products.find({"active": {"$ne": False}},
                                     {"_id": 0, "handle": 1, "title": 1, "translations": 1}):
        handle = published_handle(p, locale) or p.get("handle")
        if not handle:
            continue
        title = ((p.get("translations") or {}).get(locale) or {}).get("title") or p.get("title") or ""
        for alias in aliases_of(title):
            pairs.append((alias, f"/products/{handle}"))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    _cache[locale] = (time.time(), pairs)
    return pairs


def apply(html: str, pairs: List[Tuple[str, str]], href_of: Optional[Callable[[str], str]] = None,
          limit: int = MAX_LINKS, skip_path: str = "") -> str:
    """Link the first mention of each product, in running text only (never inside a link or heading)."""
    if not html or not pairs:
        return html
    build = href_of or (lambda path: path)
    parts = re.split(r"(<[^>]+>)", html)
    depth, used, added = 0, set(), 0
    for i, part in enumerate(parts):
        if part.startswith("<"):
            tag = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            if tag and tag.group(1).lower() in SKIP_TAGS:
                depth = max(depth - 1, 0) if part.startswith("</") else depth + 1
            continue
        if depth or added >= limit or not part.strip():
            continue
        hits = []
        for alias, path in pairs:
            key = alias.lower()
            if key in used or path == skip_path or any(h[3] == key for h in hits):
                continue
            match = re.search(rf"(?<![\w\-]){re.escape(alias)}(?![\w\-])", part, re.IGNORECASE)
            if match:
                hits.append((match.start(), match.end(), path, key))
        # earliest mention first, the longer name wins when two overlap
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        chosen, last_end = [], -1
        for start, end, path, key in hits:
            if start < last_end or added + len(chosen) >= limit:
                continue
            chosen.append((start, end, path, key))
            last_end = end
        text = part
        for start, end, path, key in reversed(chosen):
            text = f'{text[:start]}<a href="{build(path)}">{text[start:end]}</a>{text[end:]}'
            used.add(key)
        added += len(chosen)
        parts[i] = text
    return "".join(parts)


async def link_article(article: Dict, locale: str,
                       href_of: Optional[Callable[[str], str]] = None) -> Dict:
    """The article as it is served, with its body cross-linked to the live product pages."""
    body = article.get("body") or ""
    if not body:
        return article
    own = f"/products/{article.get('product_handle')}" if article.get("product_handle") else ""
    article["body"] = apply(body, await targets(locale), href_of=href_of, skip_path=own)
    return article
