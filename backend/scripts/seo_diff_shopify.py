"""Compare our SEO with the old Shopify store, page by page (read-only report).

Usage: python scripts/seo_diff_shopify.py
Writes /app/memory/seo_diff_shopify.md
"""
import asyncio
import pathlib
import re
import sys

import httpx

OLD = "https://etb7zb-gy.myshopify.com"
NEW = "http://localhost:8001/api/seo/prerender?path="
HOST = "purepeptide.bg"
TAG = re.compile(r"<[^>]+>")


def field(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.S | re.I)
    return re.sub(r"\s+", " ", TAG.sub("", m.group(1))).strip() if m else ""


def parse(html: str) -> dict:
    return {
        "title": field(html, r"<title[^>]*>(.*?)</title>"),
        "description": field(html, r'<meta name="description" content="(.*?)"'),
        "canonical": field(html, r'<link rel="canonical" href="(.*?)"'),
        "h1": field(html, r"<h1[^>]*>(.*?)</h1>"),
        "robots": field(html, r'<meta name="robots" content="(.*?)"'),
        "ld": ",".join(sorted(set(re.findall(r'"@type"\s*:\s*"(\w+)"', html)))),
    }


async def fetch(client: httpx.AsyncClient, url: str, headers=None) -> str:
    try:
        r = await client.get(url, headers=headers or {}, timeout=30, follow_redirects=True)
        return r.text if r.status_code == 200 else ""
    except Exception as exc:                      # noqa: BLE001 - report and continue
        print("fetch failed", url, exc, file=sys.stderr)
        return ""


async def main() -> None:
    async with httpx.AsyncClient() as client:
        index = await fetch(client, f"{OLD}/sitemap.xml")
        children = [u for u in re.findall(r"<loc>([^<]+)</loc>", index) if "agentic" not in u]
        urls: list[str] = []
        for child in children:
            urls += re.findall(r"<loc>([^<]+)</loc>", await fetch(client, child))
        urls = [u for u in dict.fromkeys(urls) if "/blogs/" not in u or "/blogs/" in u]
        rows = []
        for url in ["/"] + [u.replace(OLD, "") for u in urls]:
            old = parse(await fetch(client, f"{OLD}{url}"))
            if not old["title"]:
                continue
            new = parse(await fetch(client, f"{NEW}{url}", {"Host": HOST}))
            rows.append((url, old, new))
        out = ["# SEO: стар Shopify магазин vs. новият сайт (bg)", "",
               f"Сравнени {len(rows)} адреса. `=` еднакво, `≠` различно, `—` липсва при нас.", ""]
        for key in ("title", "description", "h1", "ld"):
            diff = [r for r in rows if r[1][key] != r[2][key]]
            out += [f"## {key} — различни: {len(diff)} / {len(rows)}", ""]
            for url, old, new in diff:
                out += [f"### {url}", f"- Shopify: `{old[key] or '—'}`", f"- Ние: `{new[key] or '—'}`", ""]
        path = pathlib.Path("/app/memory/seo_diff_shopify.md")
        path.write_text("\n".join(out), encoding="utf-8")
        print(f"{len(rows)} URLs compared -> {path}")


if __name__ == "__main__":
    asyncio.run(main())
