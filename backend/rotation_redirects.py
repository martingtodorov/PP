"""Future rotations resolve directly to the document's CURRENT locale handle, never via a chain.

Historical entries without the explicit policy marker retain their previous 404 behavior.
No startup migration, redirect backfill, private-data import or separate mutable target table.
"""
from urllib.parse import unquote, urlsplit

from i18n import published_handle
from pages_seed import LEGACY_PAGE_ALIASES

LATEST_ROTATION_301 = "latest_301"
KINDS = {"products": "products", "collections": "collections_cat", "articles": "articles", "pages": "pages"}


def content_path(path):
    """An exact content route only; a missing file or an arbitrary nested path is not an alias."""
    parts = unquote(urlsplit(path or "/").path).strip("/").split("/")
    if len(parts) != 2 or parts[0] not in KINDS or not parts[1]:
        return None
    return parts[0], parts[1]


async def latest_rotation_path(db, kind, locale, handle):
    if kind not in KINDS:
        return ""
    query = {"rotations": {"$elemMatch": {
        "locale": locale, "from": handle, "redirect_mode": LATEST_ROTATION_301,
    }}}
    if kind == "products":
        query["active"] = {"$ne": False}
    elif kind == "collections":
        query["delisted"] = {"$ne": True}
    elif kind == "articles":
        query["published"] = {"$ne": False}
    else:
        query["locale"] = locale
    doc = await db[KINDS[kind]].find_one(query, {"_id": 0})
    if not doc:
        return ""
    if kind == "pages":
        if (doc.get("canonical_slug") or doc.get("slug") in LEGACY_PAGE_ALIASES
                or not (doc.get("title") or doc.get("html") or doc.get("faq_items"))):
            return ""
        current = doc.get("pub_slug") or doc.get("slug")
    else:
        current = published_handle(doc, locale)
    # A manually restored current handle is a live page, never its own redirect.
    if not current or current == handle:
        return ""
    return f"/{kind}/{current}"