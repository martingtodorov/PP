"""Scan the live storefronts for anything that identifies the owner or the company.

Fetches every public page of every production domain (sitemap + API pages/products/articles +
the static files) and reports hits for the company name, the ЕИК/CUI, the registered address and
the owner's phone numbers.

Run: python backend/scripts/scan_public_exposure.py
"""
import re
import sys
import xml.etree.ElementTree as ET

import httpx

DOMAINS = ["https://purepeptide.bg", "https://purepeptide.gr", "https://purepeptide.ro",
           "https://purepeptide.eu"]
LOCALES = ["bg", "en", "fr", "de", "cz", "hu", "pl", "sk", "si", "gr", "ro"]

PATTERNS = {
    "ЕИК/CUI 208640029": re.compile(r"208\s?640\s?029"),
    "думата ЕИК/EIK/CUI": re.compile(r"\b(?:ЕИК|EIK|CUI|УИК)\b"),
    "ЕООД / EOOD / LTD": re.compile(r"\b(?:ЕООД|EOOD|OOD|ООД|Ltd\.?|LTD)\b"),
    "Пюр Пептид": re.compile(r"Пюр\s*Пептид"),
    "седалище „Бяла река“": re.compile(r"Бяла\s*река"),
    "личен телефон": re.compile(r"(?:\+359|0)\s?8[0-9][0-9]\s?[0-9]{3}\s?[0-9]{3}"),
}
IGNORE_URL = re.compile(r"\.(?:png|jpe?g|webp|svg|ico|woff2?|css|js|map)$", re.I)


def urls_of(domain: str) -> list:
    out = [f"{domain}/", f"{domain}/robots.txt", f"{domain}/llms.txt", f"{domain}/agents.md",
           f"{domain}/sitemap.xml"]
    try:
        r = httpx.get(f"{domain}/sitemap.xml", timeout=40, follow_redirects=True)
        root = ET.fromstring(r.content)
        for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            if loc.text and loc.text.startswith(domain) and not IGNORE_URL.search(loc.text):
                out.append(loc.text)
    except Exception as exc:
        print(f"  ! sitemap {domain}: {exc}")
    return sorted(set(out))


def api_texts(domain: str) -> list:
    """Page / product / article copy for every locale, as the storefront receives it."""
    out = []
    with httpx.Client(base_url=f"{domain}/api", timeout=40) as c:
        for loc in LOCALES:
            try:
                slugs = [p["slug"] for p in c.get("/pages", params={"locale": loc}).json().get("pages", [])]
            except Exception:
                slugs = []
            for slug in slugs:
                r = c.get(f"/pages/{slug}", params={"locale": loc})
                if r.status_code == 200:
                    out.append((f"api /pages/{slug}?locale={loc}", r.text))
            for path, key in (("/products", "products"), ("/collections", "collections"),
                              ("/articles", "articles")):
                r = c.get(path, params={"locale": loc})
                if r.status_code == 200:
                    out.append((f"api {path}?locale={loc}", r.text))
            for path in ("/settings", "/links", "/bank-details"):
                r = c.get(path, params={"locale": loc})
                if r.status_code == 200:
                    out.append((f"api {path}?locale={loc}", r.text))
    return out


def scan(label: str, text: str, hits: dict):
    for name, rx in PATTERNS.items():
        for m in rx.finditer(text):
            snippet = text[max(0, m.start() - 70):m.end() + 70].replace("\n", " ")
            hits.setdefault(name, []).append((label, m.group(0), snippet))


def main():
    hits = {}
    for domain in DOMAINS:
        print(f"== {domain}")
        try:
            httpx.get(domain, timeout=20, follow_redirects=True)
        except Exception as exc:
            print(f"  ! unreachable: {exc}")
            continue
        pages = urls_of(domain)
        print(f"  {len(pages)} URLs from the sitemap")
        for url in pages:
            try:
                r = httpx.get(url, timeout=40, follow_redirects=True)
            except Exception:
                continue
            if r.status_code == 200:
                scan(url, r.text, hits)
        for label, text in api_texts(domain):
            scan(f"{domain} {label}", text, hits)

    print("\n================ РЕЗУЛТАТ ================")
    if not hits:
        print("Чисто: нито едно съвпадение по фирма, ЕИК, седалище или личен телефон.")
        return 0
    for name, found in hits.items():
        seen = {}
        for label, match, snippet in found:
            seen.setdefault((match, snippet[:120]), []).append(label)
        print(f"\n### {name} — {len(found)} съвпадения в {len({l for _, _, l in [(a, b, c) for a, b, c in found]})} места")
        for (match, snippet), labels in list(seen.items())[:12]:
            print(f"  • {match!r} …{snippet}…")
            for label in labels[:4]:
                print(f"      {label}")
            if len(labels) > 4:
                print(f"      … и още {len(labels) - 4} адреса")
    return 1


if __name__ == "__main__":
    sys.exit(main())
