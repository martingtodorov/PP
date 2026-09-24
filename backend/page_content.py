"""Read-only content resolution shared by the page API and prerender; never overwrites owner copy."""
import copy
import re
from html import escape, unescape
from urllib.parse import urlsplit

from i18n import localize_doc, published_handle
from literature_copy import LITERATURE_COPY
from pages_seed import DEFAULT_PAGES


def plain_text(value):
    markup = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", value or "", flags=re.I | re.S)
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", markup)).replace("\u200b", "").split())


def valid_faq_items(items):
    return [{"q": str(item["q"]).strip(), "a": str(item["a"]).strip()}
            for item in (items or []) if isinstance(item, dict)
            and str(item.get("q") or "").strip() and str(item.get("a") or "").strip()]


def has_page_body(doc):
    text = plain_text(doc.get("html"))
    return bool(text and text.casefold() != plain_text(doc.get("title")).casefold())


async def resolve_page_content(db, doc, locale, source_locale):
    from prerender import url_for

    out = copy.deepcopy(doc)
    slug = out.get("slug")
    if slug == "faq":
        out["faq_items"] = valid_faq_items(out.get("faq_items"))
        if locale == "en" and (source_locale != "en" or
                                not (has_page_body(out) or out["faq_items"])):
            # The existing English FAQ is the approved fallback, not a fabricated translation.
            defaults = copy.deepcopy(DEFAULT_PAGES["faq"]["en"])
            out["faq_items"], out["html"] = defaults["faq_items"], defaults["html"]
            out["title"] = out.get("title") if source_locale == "en" and out.get("title") else defaults["title"]
            if source_locale != "en":
                out["seo_title"], out["seo_description"] = "", ""
            source_locale = "en"
        if not has_page_body(out):
            out["html"] = ""
        if locale == "en" and not (out.get("seo_description") or "").strip():
            out["seo_description"] = "Answers to frequently asked questions about PurePeptide, laboratory analysis, certificates, peptide storage and delivery."
    elif slug == "scientific-literature" and (source_locale != locale or not has_page_body(out)):
        content = LITERATURE_COPY[locale]
        out["title"] = out.get("title") if source_locale == locale and out.get("title") else content["title"]
        blocks = [f'<p data-testid="scientific-literature-{key}">{escape(content[key])}</p>'
                  for key in ("intro", "reading", "notice")]
        articles = await db.articles.find({"published": {"$ne": False}}, {"_id": 0}).sort("published_at", -1).to_list(200)
        blocks.append('<ul data-testid="scientific-literature-articles">')
        for doc in articles:
            article = localize_doc(doc, locale)
            handle = published_handle(doc, locale)
            if not handle or not article.get("title"):
                continue
            excerpt = plain_text(article.get("excerpt")) or plain_text(article.get("body"))
            if len(excerpt) > 600:
                excerpt = excerpt[:600].rsplit(" ", 1)[0] + "…"
            # Same-origin links keep both preview and each production storefront in their own
            # environment. Retain the canonical locale prefix and published article handle.
            href = urlsplit(url_for(locale, f"/articles/{handle}")).path
            blocks.append(f'<li><h2><a data-testid="scientific-article-{escape(handle, quote=True)}" '
                          f'href="{escape(href, quote=True)}">{escape(article["title"])}</a></h2>'
                          f'<p>{escape(excerpt)}</p></li>')
        blocks.append("</ul>")
        out["html"] = "".join(blocks)
        if source_locale != locale or not (out.get("seo_description") or "").strip():
            out["seo_description"] = content["intro"]
        if source_locale != locale:
            out["seo_title"] = ""
        source_locale = locale
    return out, source_locale