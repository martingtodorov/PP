"""Every URL we publish in a sitemap must answer 200 — checked at deploy time.

A dead link can reach a published sitemap in many ways (a de-activated product, a rotated handle, a
deleted page, a bad import), so instead of chasing each cause the deploy verifies the whole file.
Runs against the local backend, so it works before DNS/Cloudflare ever see the release.

    python scripts/check_sitemap.py [--base http://127.0.0.1:8001] [--host purepeptide.bg ...]

Exit code 1 (and a list) when anything in a sitemap is not 200.
"""
import argparse
import asyncio
import re
import sys
from urllib.parse import urlsplit

import httpx

HOSTS = ("purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr")


async def check_host(client: httpx.AsyncClient, base: str, host: str) -> list:
    headers = {"Host": host, "X-Forwarded-Host": host}
    r = await client.get(f"{base}/api/sitemap.xml", headers=headers, timeout=60)
    if r.status_code != 200:
        return [(host, "/sitemap.xml", r.status_code)]
    bad, urls = [], []
    if "<sitemapindex" in r.text:                     # parent sitemap -> fetch every child file
        for child in re.findall(r"<loc>([^<]+)</loc>", r.text):
            path = urlsplit(child).path
            c = await client.get(f"{base}/api{path}", headers=headers, timeout=60)
            if c.status_code != 200:
                bad.append((host, path, c.status_code))
                continue
            urls += re.findall(r"<loc>([^<]+)</loc>", c.text)
    else:
        urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    for url in urls:
        parts = urlsplit(url)
        if parts.netloc != host:
            bad.append((host, url, "foreign domain"))
            continue
        path = parts.path or "/"
        if path.endswith((".md", ".txt", ".xml")):     # served by the backend, not prerendered HTML
            res = await client.get(f"{base}/api{path}", headers=headers, timeout=60)
            if res.status_code != 200:
                bad.append((host, path, res.status_code))
            continue
        page = await client.get(f"{base}/api/seo/prerender", params={"path": path},
                                headers=headers, timeout=60)
        if page.status_code != 200:
            bad.append((host, path, page.status_code))
    print(f"{host}: {len(urls)} URLs, {len(bad)} broken")
    return bad


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--host", action="append", dest="hosts")
    args = ap.parse_args()
    async with httpx.AsyncClient(follow_redirects=False) as client:
        results = [await check_host(client, args.base, h) for h in (args.hosts or HOSTS)]
    bad = [row for rows in results for row in rows]
    if bad:
        print("\nBROKEN SITEMAP ENTRIES:", file=sys.stderr)
        for host, path, status in bad:
            print(f"  {host}{path} -> {status}", file=sys.stderr)
        return 1
    print("every sitemap URL answers 200")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
