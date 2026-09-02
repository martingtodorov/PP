"""Locale registry, document localisation and AI translation for PurePeptide."""

import asyncio
import json
import os
from typing import Any, Dict, List

LOCALES = ["bg", "en", "fr", "de", "cz", "hu", "pl", "sk", "si", "gr", "ro"]
DEFAULT_LOCALE = "bg"

# locale -> (language name for the translator, html lang / hreflang code)
LOCALE_META = {
    "bg": {"name": "Bulgarian", "hreflang": "bg-BG", "label": "Български"},
    "en": {"name": "English", "hreflang": "en", "label": "English"},
    "fr": {"name": "French", "hreflang": "fr-FR", "label": "Français"},
    "de": {"name": "German", "hreflang": "de-DE", "label": "Deutsch"},
    "cz": {"name": "Czech", "hreflang": "cs-CZ", "label": "Čeština"},
    "hu": {"name": "Hungarian", "hreflang": "hu-HU", "label": "Magyar"},
    "pl": {"name": "Polish", "hreflang": "pl-PL", "label": "Polski"},
    "sk": {"name": "Slovak", "hreflang": "sk-SK", "label": "Slovenčina"},
    "si": {"name": "Slovenian", "hreflang": "sl-SI", "label": "Slovenščina"},
    "gr": {"name": "Greek", "hreflang": "el-GR", "label": "Ελληνικά"},
    "ro": {"name": "Romanian", "hreflang": "ro-RO", "label": "Română"},
}

# Production domain / path mapping per locale (used for hreflang + cross-domain links)
SITE_ORIGINS = {
    "bg": {"origin": "https://purepeptide.bg", "prefix": ""},
    "en": {"origin": "https://purepeptide.eu", "prefix": "/en"},
    "fr": {"origin": "https://purepeptide.eu", "prefix": "/fr"},
    "de": {"origin": "https://purepeptide.eu", "prefix": "/de"},
    "cz": {"origin": "https://purepeptide.eu", "prefix": "/cz"},
    "hu": {"origin": "https://purepeptide.eu", "prefix": "/hu"},
    "pl": {"origin": "https://purepeptide.eu", "prefix": "/pl"},
    "sk": {"origin": "https://purepeptide.eu", "prefix": "/sk"},
    "si": {"origin": "https://purepeptide.eu", "prefix": "/si"},
    "gr": {"origin": "https://purepeptide.gr", "prefix": ""},
    "ro": {"origin": "https://purepeptide.ro", "prefix": ""},
}

TRANSLATABLE = ["title", "subtitle", "description", "handle", "menu_title", "excerpt", "body", "seo_title", "seo_description"]


def normalize_locale(locale: str | None) -> str:
    loc = (locale or DEFAULT_LOCALE).lower()
    return loc if loc in LOCALES else DEFAULT_LOCALE


def localize_doc(doc: Dict[str, Any], locale: str) -> Dict[str, Any]:
    """Overlay translations[locale] onto the base document.

    Fallback chain: requested locale -> English pivot -> Bulgarian source, so a
    non-Bulgarian storefront never falls back to Cyrillic when English copy exists.
    """
    if not doc:
        return doc
    out = dict(doc)
    translations = out.get("translations") or {}
    out["base_handle"] = out.get("handle")
    out["handles"] = {
        loc: (translations.get(loc) or {}).get("handle") or out.get("handle") for loc in LOCALES
    }
    chain = [translations.get(locale) or {}]
    if locale not in ("bg", "en"):
        chain.append(translations.get("en") or {})
    for field in TRANSLATABLE:
        for source in chain:
            val = source.get(field)
            if val:
                out[field] = val
                break
    out.pop("translations", None)
    return out


def localize_list(docs: List[Dict[str, Any]], locale: str) -> List[Dict[str, Any]]:
    return [localize_doc(d, locale) for d in docs]


async def ai_translate(source: Dict[str, str], locales: List[str], context: str = "") -> Dict[str, Dict[str, str]]:
    """Translate the given fields into the requested locales with Claude Sonnet 5.

    Uses the shop owner's own Anthropic key (ANTHROPIC_API_KEY). Returns
    {locale: {field: translated}}; raises so the caller can surface the error.
    """
    from anthropic import AsyncAnthropic

    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    targets = [normalize_locale(l) for l in locales]
    lang_list = ", ".join(f"{l} = {LOCALE_META[l]['name']}" for l in targets)

    system = (
        "You are a professional e-commerce translator for a peptide research supplier. "
        "Translate the given fields faithfully, keeping scientific terminology, peptide names, "
        "dosages (mg/mcg), CAS numbers and all HTML markup exactly intact. "
        "Never add or remove HTML tags. Keep a neutral, research-oriented tone. "
        "For the field `handle`, output a lowercase URL slug (ASCII letters, digits and hyphens only) "
        "that is SEO friendly in the target language. "
        "Return ONLY valid minified JSON shaped as {\"<locale>\": {\"<field>\": \"<translated>\"}}, "
        "no markdown fences and no commentary."
    )
    payload = {
        "source_language": "Bulgarian",
        "target_locales": {l: LOCALE_META[l]["name"] for l in targets},
        "fields": source,
        "context": context,
    }

    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{
                "role": "user",
                "content": f"Target locales: {lang_list}\n\n{json.dumps(payload, ensure_ascii=False)}",
            }],
        )
    finally:
        await client.close()

    if getattr(response, "stop_reason", None) == "max_tokens":
        raise RuntimeError("Отговорът беше отрязан (max_tokens) — намалете броя езици на заявка")

    block = next((b for b in response.content if getattr(b, "type", None) == "text"), None)
    if block is None:
        raise RuntimeError("Claude returned no text block")
    text = block.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    data = json.loads(text)
    # keep the known fields plus whatever the caller asked for (settings copy uses its own keys)
    allowed = set(TRANSLATABLE) | set(source.keys())
    return {loc: {k: v for k, v in vals.items() if k in allowed} for loc, vals in data.items() if loc in LOCALES}


async def ai_translate_chunked(source: Dict[str, str], locales: List[str], context: str = "",
                               chunk: int = 2) -> Dict[str, Dict[str, str]]:
    """Translate in small locale batches (run in parallel) so long texts never hit the token limit."""
    parts = [locales[i:i + chunk] for i in range(0, len(locales), chunk)]

    async def one(part: List[str]):
        try:
            return await ai_translate(source, part, context=context)
        except Exception:
            merged: Dict[str, Dict[str, str]] = {}
            for loc in part:  # retry one locale at a time
                merged.update(await ai_translate(source, [loc], context=context))
            return merged

    out: Dict[str, Dict[str, str]] = {}
    for res in await asyncio.gather(*(one(p) for p in parts), return_exceptions=True):
        if isinstance(res, dict):
            out.update(res)
    return out


async def ai_translate_page(source: Dict[str, Any], locales: List[str]) -> Dict[str, Dict[str, Any]]:
    """Translate a static page (title, html body, FAQ items) into the requested locales."""
    from anthropic import AsyncAnthropic

    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    targets = [normalize_locale(l) for l in locales]
    lang_list = ", ".join(f"{l} = {LOCALE_META[l]['name']}" for l in targets)

    system = (
        "You are a professional translator for a peptide research supplier's website. "
        "Translate the static page content faithfully. Keep scientific terminology, peptide names, "
        "dosages, laboratory names, email addresses, URLs and ALL HTML markup exactly intact — never "
        "add, remove or reorder HTML tags. Keep the same number of faq_items in the same order. "
        "Also translate `seo_title` (max 60 chars) and `seo_description` (max 155 chars) when present, "
        "keeping them natural and click-worthy in the target language. "
        "Return ONLY valid minified JSON shaped as "
        "{\"<locale>\": {\"title\": \"...\", \"html\": \"...\", \"seo_title\": \"...\", "
        "\"seo_description\": \"...\", \"faq_items\": [{\"q\": \"...\", \"a\": \"...\"}]}}, "
        "omitting faq_items when the source has none. No markdown fences, no commentary."
    )
    payload = {
        "source_language": "Bulgarian",
        "target_locales": {l: LOCALE_META[l]["name"] for l in targets},
        "page": source,
    }

    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            messages=[{
                "role": "user",
                "content": f"Target locales: {lang_list}\n\n{json.dumps(payload, ensure_ascii=False)}",
            }],
        )
    finally:
        await client.close()

    if getattr(response, "stop_reason", None) == "max_tokens":
        raise RuntimeError("Отговорът беше отрязан (max_tokens) — намалете броя езици на заявка")

    block = next((b for b in response.content if getattr(b, "type", None) == "text"), None)
    if block is None:
        raise RuntimeError("Claude returned no text block")
    text = block.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    data = json.loads(text)
    out: Dict[str, Dict[str, Any]] = {}
    for loc, vals in data.items():
        if loc not in LOCALES or not isinstance(vals, dict):
            continue
        entry: Dict[str, Any] = {}
        if vals.get("title"):
            entry["title"] = vals["title"]
        if isinstance(vals.get("html"), str):
            entry["html"] = vals["html"]
        for f in ("seo_title", "seo_description"):
            if vals.get(f):
                entry[f] = str(vals[f])
        items = vals.get("faq_items")
        if isinstance(items, list):
            entry["faq_items"] = [
                {"q": str(i.get("q", "")), "a": str(i.get("a", ""))}
                for i in items if isinstance(i, dict)
            ]
        if entry:
            out[loc] = entry
    return out
