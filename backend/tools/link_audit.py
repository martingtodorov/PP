"""Crawl the storefront the way Googlebot sees it and report every internal link that is not 200."""
import re
import sys
from collections import deque
from urllib.parse import quote, urljoin, urlsplit

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 200
PRERENDER = "/api/seo/prerender?path="
UA = ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
HREF = re.compile(r'href="([^"#?]+)', re.I)
SKIP = ("/api/", "/admin", "/cart", "/checkout", "/account", ".xml", ".pdf", ".png", ".jpg", ".svg",
        ".webp", ".ico", ".json", ".txt")


def internal(url: str) -> bool:
    parts = urlsplit(url)
    # the prerendered copy links absolutely (https://purepeptide.bg/...) — same site, different host
    if parts.netloc and parts.netloc not in (urlsplit(BASE).netloc, "purepeptide.bg", "www.purepeptide.bg"):
        return False
    return not any(s in parts.path for s in SKIP)


def main() -> None:
    seen, queue, bad = set(), deque(["/"]), []
    client = httpx.Client(timeout=30, headers={"User-Agent": UA}, follow_redirects=False)
    while queue and len(seen) < LIMIT:
        path = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        try:
            r = client.get(f"{BASE}{PRERENDER}{quote(path)}")
        except Exception as ex:
            bad.append((path, f"error {ex}"))
            continue
        if r.status_code >= 400:
            bad.append((path, r.status_code))
            continue
        if r.status_code in (301, 302, 307, 308):
            bad.append((path, f"{r.status_code} -> {r.headers.get('location')}"))
            continue
        for href in HREF.findall(r.text):
            if not internal(href):
                continue
            nxt = urlsplit(urljoin(path, href)).path or "/"
            if nxt not in seen:
                queue.append(nxt)
    print(f"crawled={len(seen)} broken={len(bad)}")
    for path, status in bad:
        print(status, path)


if __name__ == "__main__":
    main()
