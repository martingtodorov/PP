"""Server-side prerender for every public route.

A React SPA answers crawlers with an empty shell: same <title>, no canonical, no H1, no product
data. This module renders the finished HTML on the server — head tags (unique title/description,
self-referencing canonical, hreflang, Open Graph, Twitter), JSON-LD (Product/Offer/BreadcrumbList/
Organization/WebSite/Article) and real body content (one H1, copy, price, images with alt, internal
links) — and injects it into the built index.html. React then takes over on the client.
"""
import html
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from i18n import DEFAULT_LOCALE, LOCALES, LOCALE_META, SITE_ORIGINS, localize_doc, normalize_locale
from nextcart import shipping_summary

log = logging.getLogger("purepeptide.prerender")

SHELL_TTL = 300
PAGE_TTL = 300
PRIVATE_PREFIXES = ("/cart", "/checkout", "/track", "/account", "/admin")
# the prerendered copy stays in the DOM for crawlers but is invisible to a human; without
# JavaScript it becomes a normal, readable page again
HIDE_STYLE = (
    "<style>#pp-prerender{position:absolute;width:1px;height:1px;margin:-1px;padding:0;"
    "overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}</style>"
    "<noscript><style>#pp-prerender{position:static;width:auto;height:auto;margin:0;"
    "overflow:visible;clip:auto;white-space:normal;padding:24px;max-width:900px}</style></noscript>"
)

_db = None
_shell_cache: Dict[str, Any] = {"html": "", "at": 0.0}
_pages: Dict[Tuple[str, str], Tuple[float, str]] = {}
_stamp = 0.0


def init(db) -> None:
    global _db
    _db = db


def bump() -> None:
    """Any admin write invalidates the prerendered HTML (called from the middleware)."""
    global _stamp
    _stamp = time.time()
    _pages.clear()


def _front_origin() -> str:
    for env in ("FRONTEND_ORIGIN", "PUBLIC_SITE_URL"):
        value = (os.environ.get(env) or "").strip().rstrip("/")
        if value:
            return value
    return "http://localhost:3000"


async def _shell() -> str:
    """The built index.html — fetched from the web root, so the hashed asset names stay correct."""
    if _shell_cache["html"] and time.time() - _shell_cache["at"] < SHELL_TTL:
        return _shell_cache["html"]
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            r = await c.get(f"{_front_origin()}/index.html", headers={"x-prerender-shell": "1"})
        if r.status_code == 200 and "<div id=\"root\"" in r.text:
            _shell_cache.update(html=r.text, at=time.time())
    except Exception as ex:
        log.warning("shell fetch failed: %s", ex)
    return _shell_cache["html"]


# ---------- locale / url helpers ----------

def locale_of(host: str, path: str) -> str:
    seg = path.strip("/").split("/")[0].lower()
    if seg in LOCALES and seg != DEFAULT_LOCALE:
        return seg
    hostname = (host or "").lower().split(":")[0]
    if hostname.endswith("purepeptide.gr"):
        return "gr"
    if hostname.endswith("purepeptide.ro"):
        return "ro"
    if hostname.endswith("purepeptide.eu"):
        return "en"
    return DEFAULT_LOCALE


def strip_prefix(path: str) -> str:
    seg = path.strip("/").split("/")[0].lower()
    if seg in LOCALES and seg != DEFAULT_LOCALE:
        rest = path.strip("/")[len(seg):]
        return "/" + rest.strip("/")
    return "/" + path.strip("/")


def url_for(locale: str, route: str) -> str:
    site = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])
    clean = route.strip("/")
    if not clean:
        return f"{site['origin']}{site['prefix']}/" if site["prefix"] else f"{site['origin']}/"
    return f"{site['origin']}{site['prefix']}/{clean}"


def _abs(url: str, origin: str) -> str:
    if not url:
        return f"{origin}/og-image.jpg"
    return url if url.startswith("http") else f"{origin}{url}"


def _text(value: Any, limit: int = 300) -> str:
    plain = re.sub(r"<[^>]+>", " ", str(value or ""))
    plain = html.unescape(re.sub(r"\s+", " ", plain)).strip()
    return plain[:limit].rstrip()


def demote(markup: str) -> str:
    """Imported copy sometimes starts with its own <h1> — one H1 per page, the rest become H2."""
    out = re.sub(r"<h1(\s[^>]*)?>", "<h2>", str(markup or ""), flags=re.I)
    return re.sub(r"</h1>", "</h2>", out, flags=re.I)


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


# ---------- head + body building ----------

def _og_locale(locale: str) -> str:
    """og:locale wants language_TERRITORY — plain `en` is invalid, so English declares en_GB."""
    meta = LOCALE_META[locale]
    return meta.get("og_locale") or meta["hreflang"].replace("-", "_")


def _tidy(title: str) -> str:
    """One space around the pipe — a missing one ("… на GH| цена") was visible in the SERP."""
    return re.sub(r"\s*\|\s*", " | ", title).strip()


def _head(locale: str, route: str, title: str, description: str, image: str,
          og_type: str = "website", extra: str = "", robots: str = "") -> str:
    title = _tidy(title)
    origin = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])["origin"]
    canonical = url_for(locale, route)
    alternates = "".join(
        f'<link rel="alternate" hreflang="{LOCALE_META[loc]["hreflang"]}" href="{url_for(loc, route)}">'
        for loc in LOCALES
    ) + f'<link rel="alternate" hreflang="x-default" href="{url_for("en", route)}">'
    return (
        f"<title>{esc(title)}</title>"
        f'<meta name="description" content="{esc(description)}">'
        f'<link rel="canonical" href="{canonical}">'
        f'<meta name="robots" content="{robots or "index, follow, max-image-preview:large, max-snippet:-1"}">'
        f'<meta property="og:type" content="{og_type}">'
        f'<meta property="og:title" content="{esc(title)}">'
        f'<meta property="og:description" content="{esc(description)}">'
        f'<meta property="og:url" content="{canonical}">'
        f'<meta property="og:image" content="{_abs(image, origin)}">'
        f'<meta property="og:locale" content="{_og_locale(locale)}">'
        f'<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{esc(title)}">'
        f'<meta name="twitter:description" content="{esc(description)}">'
        f'<meta name="twitter:image" content="{_abs(image, origin)}">'
        + alternates + extra
    )


def _ld(*blocks: Dict[str, Any]) -> str:
    import json
    graph = [b for b in blocks if b]
    # data-pp-jsonld lets React drop this block on mount (lib/seo.js) — two Product nodes with the
    # same @id would otherwise merge in Google's eyes and report "duplicate field brand"
    return ('<script type="application/ld+json" data-pp-jsonld="prerender">'
            + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
            + "</script>")


async def _merchant_terms(locale: str) -> Dict[str, Any]:
    """Google merchant listings want the return window and the delivery terms inside every offer —
    the same block the storefront JSON-LD builds (frontend/src/lib/schema.js)."""
    try:
        s = await shipping_summary(locale) or {}
    except Exception:
        return {}
    country = s.get("country") or "BG"
    handling = s.get("handling_days") or [1, 3]
    transit = s.get("transit_days") or [1, 3]
    out: Dict[str, Any] = {"hasMerchantReturnPolicy": {
        "@type": "MerchantReturnPolicy", "applicableCountry": country, "returnPolicyCountry": country,
        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
        "merchantReturnDays": s.get("return_days") or 14,
        "returnMethod": "https://schema.org/ReturnByMail",
        "returnFees": "https://schema.org/ReturnShippingFees"}}
    if isinstance(s.get("price"), (int, float)):
        out["shippingDetails"] = {
            "@type": "OfferShippingDetails",
            "shippingRate": {"@type": "MonetaryAmount", "value": s["price"],
                             "currency": s.get("currency") or "EUR"},
            "shippingDestination": {"@type": "DefinedRegion", "addressCountry": country},
            "deliveryTime": {"@type": "ShippingDeliveryTime",
                             "handlingTime": {"@type": "QuantitativeValue", "unitCode": "DAY",
                                              "minValue": handling[0], "maxValue": handling[1]},
                             "transitTime": {"@type": "QuantitativeValue", "unitCode": "DAY",
                                             "minValue": transit[0], "maxValue": transit[1]}}}
    return out


# site settings, refreshed by _route() — _organization() needs them but stays sync, because it is
# embedded in every page's JSON-LD graph
_SITE: Dict[str, Any] = {}


def _organization(locale: str) -> Dict[str, Any]:
    """Same shape as the old Shopify store: logo as an ImageObject plus a contact point."""
    origin = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])["origin"]
    email = _SITE.get("contact_email") or "contact@purepeptide.bg"
    phone = _SITE.get("contact_phone") or ""
    contact = {"@type": "ContactPoint", "contactType": "customer service", "email": email,
               "areaServed": "EU",
               "availableLanguage": [LOCALE_META[loc]["name"] for loc in LOCALES]}
    if phone:
        contact["telephone"] = phone
    return {"@type": "Organization", "@id": f"{origin}/#organization",
            "name": _SITE.get("site_name") or "PurePeptide", "url": origin,
            "logo": {"@type": "ImageObject", "url": f"{origin}/favicon-512.png",
                     "width": 512, "height": 512},
            "image": f"{origin}/og-image.jpg", "email": email, "contactPoint": contact}


def _website(locale: str) -> Dict[str, Any]:
    origin = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])["origin"]
    return {"@type": "WebSite", "@id": f"{origin}/#website", "name": "PurePeptide", "url": origin,
            "inLanguage": LOCALE_META[locale]["hreflang"],
            "publisher": {"@id": f"{origin}/#organization"}}


def _breadcrumbs(locale: str, trail: List[Tuple[str, str]]) -> Dict[str, Any]:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": url_for(locale, route)}
        for i, (name, route) in enumerate(trail)]}


def _crumb_html(locale: str, trail: List[Tuple[str, str]]) -> str:
    links = " › ".join(f'<a href="{url_for(locale, route)}">{esc(name)}</a>' for name, route in trail)
    return f'<nav aria-label="Breadcrumb">{links}</nav>'


# ---------- routes ----------

def _link_li(locale: str, prefix: str, handle: str, label: str) -> str:
    return f'<li><a href="{url_for(locale, prefix + str(handle))}">{esc(label)}</a></li>'


def _product_li(locale: str, product: Dict[str, Any]) -> str:
    variants = product.get("variants") or []
    price = float((variants[0] if variants else {}).get("price_eur") or 0)
    tail = f" — {price:.2f} EUR" if price else ""
    href = url_for(locale, f'/products/{product.get("handle")}')
    return f'<li><a href="{href}">{esc(product.get("title"))}</a>{tail}</li>'


def _retired(doc: Dict[str, Any], locale: str, requested: str) -> bool:
    """A handle rotated away in the admin must 404 for crawlers too, not only in the JSON API."""
    return any(r.get("locale") == locale and r.get("from") == requested
               for r in (doc.get("rotations") or []))


async def _product(locale: str, handle: str) -> Optional[Dict[str, str]]:
    doc = await _db.products.find_one({"handle": handle, "active": True}, {"_id": 0}) \
        or await _db.products.find_one({f"translations.{locale}.handle": handle}, {"_id": 0})
    if not doc or _retired(doc, locale, handle):
        return None
    p = localize_doc(doc, locale)
    route = f"/products/{p.get('handle') or handle}"
    origin = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])["origin"]
    variants = p.get("variants") or []
    in_stock = any((v.get("stock") or 0) > 0 for v in variants)
    prices = [float(v.get("price_eur") or 0) for v in variants if v.get("price_eur")]
    images = [_abs(i, origin) for i in (p.get("images") or ([p["image"]] if p.get("image") else []))][:13]
    title = p.get("seo_title") or f'{p.get("title")} | PurePeptide'
    description = p.get("seo_description") or _text(p.get("description"))
    terms = await _merchant_terms(locale)
    offers = [{"@type": "Offer", "name": v.get("name") or "", "url": url_for(locale, route),
               "priceCurrency": "EUR", "price": f'{float(v.get("price_eur") or 0):.2f}',
               "sku": v.get("sku") or "",
               "availability": ("https://schema.org/InStock" if (v.get("stock") or 0) > 0
                                else "https://schema.org/OutOfStock"),
               "itemCondition": "https://schema.org/NewCondition",
               "seller": {"@id": f"{origin}/#organization"}, **terms} for v in variants]
    # one Offer for a single variant, an AggregateOffer with the range for several — exactly what
    # the storefront renders, so both versions of the page describe the same product
    offer_node: Any = offers[0] if len(offers) == 1 else {
        "@type": "AggregateOffer", "priceCurrency": "EUR",
        "lowPrice": f"{min(prices):.2f}" if prices else "0.00",
        "highPrice": f"{max(prices):.2f}" if prices else "0.00",
        "offerCount": len(offers), "url": url_for(locale, route),
        "availability": ("https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock"),
        **terms, "offers": offers}
    trail = [(_t(locale, "home"), "/"), (_t(locale, "catalog"), "/collections"), (p.get("title"), route)]
    body = [
        _crumb_html(locale, trail),
        f'<h1>{esc(p.get("title"))}</h1>',
        f'<p>{esc(description)}</p>',
        (f'<p><strong>{min(prices):.2f} EUR</strong> · '
         f'{"В наличност" if in_stock else "Изчерпан"}</p>' if prices else ""),
        "".join(f'<img src="{src}" alt="{esc(p.get("title"))}" width="600" height="600">' for src in images),
        demote(p.get("description")),
        "".join(f'<a href="{url_for(locale, f"/collections/{c}")}">{esc(c)}</a> '
                for c in (p.get("collections") or [])[:6]),
    ]
    ld = _ld(
        {"@type": "Product", "@id": f'{url_for(locale, route)}#product', "name": p.get("title"),
         "description": _text(description, 500), "image": images,
         "sku": (variants[0].get("sku") if variants else ""),
         "mpn": (variants[0].get("sku") if variants else ""),
         "brand": {"@type": "Brand", "name": "PurePeptide"}, "category": "Research peptides",
         "url": url_for(locale, route), "offers": offer_node},
        _breadcrumbs(locale, trail), _organization(locale), _website(locale))
    return {"head": _head(locale, route, title, description, images[0] if images else "",
                          og_type="product", extra=ld),
            "body": "".join(x for x in body if x)}


async def _collection(locale: str, handle: str) -> Optional[Dict[str, str]]:
    doc = await _db.collections_cat.find_one({"handle": handle}, {"_id": 0}) \
        or await _db.collections_cat.find_one({f"translations.{locale}.handle": handle}, {"_id": 0})
    if not doc or _retired(doc, locale, handle):
        return None
    c = localize_doc(doc, locale)
    route = f"/collections/{c.get('handle') or handle}"
    base_handle = doc.get("handle")
    products = await _db.products.find({"collections": base_handle, "active": True}, {"_id": 0}).to_list(60)
    items = [localize_doc(p, locale) for p in products]
    title = c.get("seo_title") or f'{c.get("title")} | PurePeptide'
    description = c.get("seo_description") or _text(c.get("description"))
    trail = [(_t(locale, "home"), "/"), (c.get("title"), route)]
    body = [
        _crumb_html(locale, trail),
        f'<h1>{esc(c.get("title"))}</h1>',
        f'<p>{esc(description)}</p>',
        "<ul>" + "".join(_product_li(locale, p) for p in items) + "</ul>",
    ]
    ld = _ld({"@type": "CollectionPage", "@id": f'{url_for(locale, route)}#page', "name": c.get("title"),
              "description": _text(description, 500), "url": url_for(locale, route),
              "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
                  {"@type": "ListItem", "position": i + 1, "name": p.get("title"),
                   "url": url_for(locale, f'/products/{p.get("handle")}')} for i, p in enumerate(items)]}},
             _breadcrumbs(locale, trail), _organization(locale), _website(locale))
    return {"head": _head(locale, route, title, description, c.get("image") or "", extra=ld),
            "body": "".join(body)}


async def _catalog(locale: str) -> Dict[str, str]:
    """/collections — the shop index: every collection and every product, one link each."""
    collections = await _db.collections_cat.find({}, {"_id": 0}).to_list(50)
    products = await _db.products.find({"active": True}, {"_id": 0}).to_list(200)
    items = [localize_doc(p, locale) for p in products]
    title = f'{_t(locale, "catalog")} | PurePeptide'
    description = _HOME.get(locale, _HOME["en"])[1]
    trail = [(_t(locale, "home"), "/"), (_t(locale, "catalog"), "/collections")]
    ld = _ld({"@type": "CollectionPage", "@id": f'{url_for(locale, "/collections")}#page',
              "name": _t(locale, "catalog"), "url": url_for(locale, "/collections"),
              "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
                  {"@type": "ListItem", "position": i + 1, "name": p.get("title"),
                   "url": url_for(locale, f'/products/{p.get("handle")}')} for i, p in enumerate(items)]}},
             _breadcrumbs(locale, trail), _organization(locale), _website(locale))
    body = [_crumb_html(locale, trail), f'<h1>{esc(_t(locale, "catalog"))}</h1>',
            "<ul>" + "".join(_link_li(locale, "/collections/", c.get("handle"),
                                      localize_doc(c, locale).get("title")) for c in collections) + "</ul>",
            "<ul>" + "".join(_product_li(locale, p) for p in items) + "</ul>"]
    return {"head": _head(locale, "/collections", title, description, "", extra=ld), "body": "".join(body)}


async def _article(locale: str, handle: str) -> Optional[Dict[str, str]]:
    doc = await _db.articles.find_one({"handle": handle}, {"_id": 0}) \
        or await _db.articles.find_one({f"translations.{locale}.handle": handle}, {"_id": 0})
    if not doc or _retired(doc, locale, handle):
        return None
    a = localize_doc(doc, locale)
    route = f"/articles/{a.get('handle') or handle}"
    title = a.get("seo_title") or f'{a.get("title")} | PurePeptide'
    description = a.get("seo_description") or _text(a.get("excerpt") or a.get("body"))
    trail = [(_t(locale, "home"), "/"), (_t(locale, "articles"), "/pages/articles"), (a.get("title"), route)]
    origin = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])["origin"]
    ld = _ld({"@type": "Article", "@id": f'{url_for(locale, route)}#article', "headline": a.get("title"),
              "description": _text(description, 500), "image": _abs(a.get("image") or "", origin),
              "datePublished": a.get("published_at"), "dateModified": a.get("updated_at") or a.get("published_at"),
              "author": {"@type": "Organization", "name": a.get("author") or "PurePeptide"},
              "publisher": {"@id": f"{origin}/#organization"}, "mainEntityOfPage": url_for(locale, route)},
             _breadcrumbs(locale, trail), _organization(locale), _website(locale))
    body = [_crumb_html(locale, trail), f'<h1>{esc(a.get("title"))}</h1>', demote(a.get("body")) or f'<p>{esc(description)}</p>']
    return {"head": _head(locale, route, title, description, a.get("image") or "",
                          og_type="article", extra=ld),
            "body": "".join(body)}


async def _page(locale: str, slug: str) -> Optional[Dict[str, str]]:
    # mirrors GET /api/pages/{slug}: a rotated page lives under `pub_slug` only, the old slug 404s
    doc = await _db.pages.find_one({"slug": slug, "locale": locale, "pub_slug": slug}, {"_id": 0}) \
        or await _db.pages.find_one({"locale": locale, "pub_slug": slug}, {"_id": 0})
    if not doc:
        if await _db.pages.find_one({"locale": locale, "rotations.from": slug}, {"_id": 0, "slug": 1}):
            return None
        doc = await _db.pages.find_one({"slug": slug, "locale": locale}, {"_id": 0})
        if doc and doc.get("pub_slug"):
            return None
        doc = doc or await _db.pages.find_one({"slug": slug, "locale": DEFAULT_LOCALE}, {"_id": 0})
    if not doc:
        return None
    route = f"/pages/{slug}"
    title = doc.get("seo_title") or f'{doc.get("title")} | PurePeptide'
    description = doc.get("seo_description") or _text(doc.get("html"))
    trail = [(_t(locale, "home"), "/"), (doc.get("title"), route)]
    ld = _ld({"@type": "WebPage", "@id": f'{url_for(locale, route)}#page', "name": doc.get("title"),
              "description": _text(description, 500), "url": url_for(locale, route)},
             _breadcrumbs(locale, trail), _organization(locale), _website(locale))
    body = [_crumb_html(locale, trail), f'<h1>{esc(doc.get("title"))}</h1>', demote(doc.get("html"))]
    return {"head": _head(locale, route, title, description, "", extra=ld), "body": "".join(body)}


_SITEMAP_SECTIONS = {
    "": ("products", "collections", "articles", "pages"),
    "-products": ("products",),
    "-collections": ("collections",),
    "-blogs": ("articles",),
    "-articles": ("articles",),
    "-pages": ("pages",),
}


async def _html_sitemap(locale: str, slug: str) -> Optional[Dict[str, str]]:
    """The HTML sitemap pages the app renders (same URLs as the old Shopify theme).

    They live in the router, not in the `pages` collection, so the prerender used to answer 404 for
    them — a soft 404 on pages that are linked from the footer and were indexed on Shopify.
    """
    section = slug[len("html-sitemap"):]
    kinds = _SITEMAP_SECTIONS.get(section)
    if kinds is None:
        return None
    route = f"/pages/{slug}"
    label = {"products": _t(locale, "catalog"), "collections": _t(locale, "collections"),
             "articles": _t(locale, "articles"), "pages": _t(locale, "pages")}
    heading = "HTML sitemap" if not section else f"HTML sitemap — {label[kinds[0]]}"
    sources = {"products": (_db.products, "/products/", {"active": True}),
               "collections": (_db.collections_cat, "/collections/", {}),
               "articles": (_db.articles, "/articles/", {}),
               "pages": (_db.pages, "/pages/", {"locale": DEFAULT_LOCALE})}
    blocks = []
    for kind in kinds:
        coll, prefix, query = sources[kind]
        field = "slug" if kind == "pages" else "handle"
        docs = await coll.find(query, {"_id": 0, field: 1, "title": 1, "translations": 1,
                                       "pub_slug": 1}).to_list(500)
        items = []
        for doc in docs:
            local = localize_doc(doc, locale)
            handle = local.get("pub_slug") or local.get(field)
            if handle:
                items.append(_link_li(locale, prefix, handle, local.get("title") or handle))
        if items:
            blocks.append(f"<h2>{esc(label[kind])}</h2><ul>{''.join(items)}</ul>")
    trail = [(_t(locale, "home"), "/"), (heading, route)]
    ld = _ld({"@type": "WebPage", "@id": f"{url_for(locale, route)}#page", "name": heading,
              "url": url_for(locale, route)},
             _breadcrumbs(locale, trail), _organization(locale), _website(locale))
    body = [_crumb_html(locale, trail), f"<h1>{esc(heading)}</h1>"] + blocks
    return {"head": _head(locale, route, f"{heading} | PurePeptide", _t(locale, "sitemapDesc"),
                          "", extra=ld),
            "body": "".join(body)}


# home copy mirrors the storefront (i18n/locales.js) so the prerender and React agree
# (SERP title <= 60 chars with the purity claim up front, meta description, H1 value proposition)
_HOME = {
    "bg": ("PurePeptide – Nº1 пептиди с доказано качество в България",
           "Лиофилизирани пептиди за научно-изследователски цели, създадени с фокус върху стабилност, чистота и проследимост. Всеки продукт е придружен от независим анализ от Janoshik Labs.",
           "Пептиди с лабораторно доказано качество и >99% чистота"),
    "en": ("PurePeptide – Nº1 proven-quality peptides in Europe",
           "Lyophilised peptides for research use, made with a focus on stability, purity and traceability. Every product comes with an independent Janoshik Labs analysis.",
           "Peptides with laboratory-verified quality and >99% purity"),
    "fr": ("PurePeptide – Nº1 des peptides de qualité prouvée en France",
           "Peptides lyophilisés pour la recherche, conçus pour la stabilité, la pureté et la traçabilité. Chaque produit est accompagné d'une analyse indépendante de Janoshik Labs.",
           "Peptides de qualité vérifiée en laboratoire, pureté >99 %"),
    "de": ("PurePeptide – Nº1 Peptide geprüfter Qualität in Deutschland",
           "Lyophilisierte Peptide für Forschungszwecke, entwickelt mit Fokus auf Stabilität, Reinheit und Nachverfolgbarkeit. Jedes Produkt enthält eine unabhängige Analyse von Janoshik Labs.",
           "Peptide mit laborgeprüfter Qualität und >99 % Reinheit"),
    "cz": ("PurePeptide – Nº1 peptidy s prokázanou kvalitou v Česku",
           "Lyofilizované peptidy pro výzkumné účely, vyvinuté s důrazem na stabilitu, čistotu a dohledatelnost. Ke každému produktu patří nezávislá analýza od Janoshik Labs.",
           "Peptidy s laboratorně ověřenou kvalitou a čistotou >99 %"),
    "hu": ("PurePeptide – Nº1 igazolt minőségű peptidek Magyarországon",
           "Liofilizált peptidek kutatási célra, a stabilitásra, a tisztaságra és a nyomon követhetőségre fókuszálva. Minden termékhez független Janoshik Labs analízis tartozik.",
           "Laboratóriumban igazolt minőségű peptidek, >99% tisztaság"),
    "pl": ("PurePeptide – Nº1 peptydy o potwierdzonej jakości w Polsce",
           "Liofilizowane peptydy do celów badawczych, tworzone z naciskiem na stabilność, czystość i identyfikowalność. Do każdego produktu dołączona jest niezależna analiza Janoshik Labs.",
           "Peptydy o laboratoryjnie potwierdzonej jakości i czystości >99%"),
    "sk": ("PurePeptide – Nº1 peptidy s overenou kvalitou na Slovensku",
           "Lyofilizované peptidy na výskumné účely, vyvinuté s dôrazom na stabilitu, čistotu a sledovateľnosť. Ku každému produktu patrí nezávislá analýza od Janoshik Labs.",
           "Peptidy s laboratórne overenou kvalitou a čistotou >99 %"),
    "si": ("PurePeptide – Nº1 peptidi preverjene kakovosti v Sloveniji",
           "Liofilizirani peptidi za raziskovalne namene, zasnovani s poudarkom na stabilnosti, čistosti in sledljivosti. Vsak izdelek spremlja neodvisna analiza Janoshik Labs.",
           "Peptidi z laboratorijsko preverjeno kakovostjo in čistostjo >99 %"),
    "gr": ("PurePeptide – Nº1 πεπτίδια εγγυημένης ποιότητας στην Ελλάδα",
           "Λυοφιλιωμένα πεπτίδια για ερευνητική χρήση, με έμφαση στη σταθερότητα, την καθαρότητα και την ιχνηλασιμότητα. Κάθε προϊόν συνοδεύεται από ανεξάρτητη ανάλυση Janoshik Labs.",
           "Πεπτίδια με εργαστηριακά επιβεβαιωμένη ποιότητα και καθαρότητα >99%"),
    "ro": ("PurePeptide – Nº1 peptide de calitate dovedită în România",
           "Peptide liofilizate pentru cercetare, create cu accent pe stabilitate, puritate și trasabilitate. Fiecare produs este însoțit de o analiză independentă Janoshik Labs.",
           "Peptide cu calitate verificată în laborator și puritate >99%"),
}


async def _home(locale: str) -> Dict[str, str]:
    s = await _db.settings.find_one({"key": "site"}, {"_id": 0})
    settings = (s or {}).get("value", {})
    products = await _db.products.find({"active": True}, {"_id": 0}).to_list(24)
    items = [localize_doc(p, locale) for p in products]
    collections = await _db.collections_cat.find({}, {"_id": 0}).to_list(20)
    title, description, _ = _HOME.get(locale, _HOME["en"])
    origin = SITE_ORIGINS.get(locale, SITE_ORIGINS[DEFAULT_LOCALE])["origin"]
    ld = _ld(_organization(locale),
             {**_website(locale), "potentialAction": {
                 "@type": "SearchAction", "target": f"{origin}/collections?q={{search_term_string}}",
                 "query-input": "required name=search_term_string"}},
             {"@type": "ItemList", "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": p.get("title"),
                  "url": url_for(locale, f'/products/{p.get("handle")}')} for i, p in enumerate(items[:12])]})
    body = [
        # the hero shows the brand word, so the prerendered H1 must say exactly the same
        f'<h1>{esc(_SITE.get("hero_title") or "PurePeptide")}</h1>',
        f'<p>{esc(description)}</p>',
        "<ul>" + "".join(_link_li(locale, "/collections/", c.get("handle"),
                                   localize_doc(c, locale).get("title")) for c in collections) + "</ul>",
        "<ul>" + "".join(_link_li(locale, "/products/", p.get("handle"), p.get("title")) for p in items) + "</ul>",
    ]
    return {"head": _head(locale, "/", title, description, "", extra=ld), "body": "".join(body)}


_LABELS = {
    "home": {"bg": "Начало", "en": "Home", "fr": "Accueil", "de": "Startseite", "cz": "Domů",
             "hu": "Főoldal", "pl": "Strona główna", "sk": "Domov", "si": "Domov",
             "gr": "Αρχική", "ro": "Acasă"},
    "catalog": {"bg": "Всички пептиди", "en": "All peptides", "fr": "Tous les peptides",
                "de": "Alle Peptide", "cz": "Všechny peptidy", "hu": "Összes peptid",
                "pl": "Wszystkie peptydy", "sk": "Všetky peptidy", "si": "Vsi peptidi",
                "gr": "Όλα τα πεπτίδια", "ro": "Toate peptidele"},
    "notFound": {"bg": "Страницата не е намерена", "en": "Page not found", "fr": "Page introuvable",
                 "de": "Seite nicht gefunden", "cz": "Stránka nenalezena", "hu": "Az oldal nem található",
                 "pl": "Strona nie znaleziona", "sk": "Stránka sa nenašla", "si": "Stran ni najdena",
                 "gr": "Η σελίδα δεν βρέθηκε", "ro": "Pagina nu a fost găsită"},
    "articles": {"bg": "Научни статии", "en": "Articles", "fr": "Articles", "de": "Artikel",
                 "cz": "Články", "hu": "Cikkek", "pl": "Artykuły", "sk": "Články", "si": "Članki",
                 "gr": "Άρθρα", "ro": "Articole"},
    "collections": {"bg": "Категории", "en": "Collections", "fr": "Collections",
                    "de": "Kategorien", "cz": "Kategorie", "hu": "Kategóriák",
                    "pl": "Kategorie", "sk": "Kategórie", "si": "Kategorije",
                    "gr": "Κατηγορίες", "ro": "Categorii"},
    "pages": {"bg": "Страници", "en": "Pages", "fr": "Pages", "de": "Seiten", "cz": "Stránky",
              "hu": "Oldalak", "pl": "Strony", "sk": "Stránky", "si": "Strani",
              "gr": "Σελίδες", "ro": "Pagini"},
    "sitemapDesc": {"bg": "Пълен списък с всички страници, продукти, категории и статии в сайта.",
                    "en": "A full list of every page, product, collection and article on the site.",
                    "fr": "La liste complète des pages, produits, catégories et articles du site.",
                    "de": "Vollständige Liste aller Seiten, Produkte, Kategorien und Artikel.",
                    "cz": "Úplný seznam všech stránek, produktů, kategorií a článků na webu.",
                    "hu": "Az oldal összes lapjának, termékének, kategóriájának és cikkének listája.",
                    "pl": "Pełna lista wszystkich stron, produktów, kategorii i artykułów.",
                    "sk": "Úplný zoznam všetkých stránok, produktov, kategórií a článkov.",
                    "si": "Popoln seznam vseh strani, izdelkov, kategorij in člankov na spletu.",
                    "gr": "Πλήρης λίστα με όλες τις σελίδες, τα προϊόντα και τα άρθρα του site.",
                    "ro": "Lista completă a paginilor, produselor, categoriilor și articolelor."},
}


def _t(locale: str, key: str) -> str:
    return _LABELS[key].get(locale) or _LABELS[key]["en"]


async def _route(locale: str, route: str) -> Optional[Dict[str, str]]:
    doc = await _db.settings.find_one({"key": "site"}, {"_id": 0, "value": 1})
    _SITE.update((doc or {}).get("value") or {})
    parts = [p for p in route.strip("/").split("/") if p]
    if not parts:
        return await _home(locale)
    if parts[0] == "products" and len(parts) > 1:
        return await _product(locale, parts[1])
    if parts[0] == "collections":
        return await _collection(locale, parts[1]) if len(parts) > 1 else await _catalog(locale)
    if parts[0] == "articles" and len(parts) > 1:
        return await _article(locale, parts[1])
    if parts[0] == "pages" and len(parts) > 1:
        if parts[1].startswith("html-sitemap"):
            return await _html_sitemap(locale, parts[1])
        return await _page(locale, parts[1])
    return None


def _html_lang(locale: str) -> str:
    """`html lang` carries the plain language subtag: cz -> cs, si -> sl, gr -> el."""
    return LOCALE_META.get(locale, LOCALE_META[DEFAULT_LOCALE])["hreflang"].split("-")[0]


def _set_lang(html: str, locale: str) -> str:
    """The built shell ships `lang="bg"`; every localised page must state its own language."""
    lang = _html_lang(locale)
    if re.search(r"<html[^>]*\slang=", html):
        return re.sub(r'(<html[^>]*?)\slang="[^"]*"', lambda m: f'{m.group(1)} lang="{lang}"', html, count=1)
    return re.sub(r"<html\b", f'<html lang="{lang}"', html, count=1)


def _inject(shell: str, head: str, body: str, locale: str = DEFAULT_LOCALE) -> str:
    """Our tags win: drop the static title/description/OG of the shell, then add ours.

    The prerendered copy is wrapped in a visually-hidden container: crawlers (and anyone with
    JavaScript off, see the <noscript> rule) read it, while a normal visitor never sees a second of
    unstyled text before React mounts and replaces it.
    """
    out = re.sub(r"<title>.*?</title>", "", shell, flags=re.S)
    out = _set_lang(out, locale)
    out = re.sub(r'<meta\s+name="description"[^>]*>', "", out)
    out = re.sub(r'<meta\s+name="robots"[^>]*>', "", out)
    out = re.sub(r'<meta\s+(?:property|name)="(?:og|twitter):[^"]+"[^>]*>', "", out)
    out = out.replace("</head>", f"{head}{HIDE_STYLE}</head>", 1)
    wrapped = f'<div id="pp-prerender">{body}</div>'
    return re.sub(r'(<div id="root"[^>]*>)', lambda m: m.group(1) + wrapped, out, count=1)


async def render(path: str, host: str) -> Optional[Tuple[str, int]]:
    """(html, status) for a page request, or None when nginx should serve the static shell.

    Status matters: a URL whose content does not exist must answer 404, otherwise Google files it as
    a soft 404. Private routes (cart, checkout, account…) get the untouched shell with 200.
    """
    clean = (path or "/").split("?")[0].split("#")[0]
    route = strip_prefix(clean)
    looks_like_a_file = "." in route.rsplit("/", 1)[-1]
    key = (host or "", clean)
    hit = _pages.get(key)
    if hit and time.time() - hit[0] < PAGE_TTL:
        return hit[1]
    shell = await _shell()
    if not shell:
        return None
    locale = normalize_locale(locale_of(host, clean))
    if route.startswith(PRIVATE_PREFIXES):
        return _set_lang(shell, locale), 200
    if looks_like_a_file:
        return _set_lang(shell, locale), 404
    try:
        rendered = await _route(locale, route)
    except Exception:
        log.exception("prerender failed for %s", clean)
        return None
    if not rendered:
        # the route exists in the app but its content does not — a real 404, with the shell so the
        # visitor still sees the app's own not-found page
        head = _head(locale, route.lstrip("/"), _t(locale, "notFound"), "", "",
                     robots="noindex, follow")
        return _inject(shell, head, f'<h1>{esc(_t(locale, "notFound"))}</h1>', locale), 404
    out = (_inject(shell, rendered["head"], rendered["body"], locale), 200)
    _pages[key] = (time.time(), out)
    return out
