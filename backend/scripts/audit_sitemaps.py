"""Audit: every URL in every sitemap must be live, canonical and its own host's."""
import os
import re
import sys
import urllib.parse
from collections import defaultdict

import requests

BASE = "http://localhost:8001"
HOSTS = ["purepeptide.bg", "purepeptide.gr", "purepeptide.eu", "purepeptide.ro"]
LOC = re.compile(r"<loc>([^<]+)</loc>")
ALT = re.compile(r'hreflang="([^"]+)"\s+href="([^"]+)"')


def get(path, host, **kw):
    return requests.get(f"{BASE}{path}", headers={"Host": host}, timeout=60, **kw)


def audit(host):
    print(f"\n===== {host}")
    idx = get("/api/sitemap.xml", host)
    print("sitemap.xml:", idx.status_code, "| children:", len(LOC.findall(idx.text)))
    if idx.status_code != 200:
        print("  (no sitemap for this host — switched-off market)")
        return {}, {}
    children = LOC.findall(idx.text)
    problems = defaultdict(list)
    seen = {}
    total = 0
    for child in children:
        p = urllib.parse.urlparse(child)
        if p.netloc != host:
            problems["child sitemap on a foreign host"].append(child)
        r = get("/api" + p.path, host)
        if r.status_code != 200:
            problems[f"child sitemap {r.status_code}"].append(child)
            continue
        urls = LOC.findall(r.text)
        total += len(urls)
        print(f"  {p.path}: {len(urls)} urls")
        for u in urls:
            up = urllib.parse.urlparse(u)
            if up.netloc != host:
                problems["url on a foreign host"].append(u)
            if u in seen:
                problems["duplicate url"].append(u)
            seen[u] = child
            if not u.startswith("https://"):
                problems["not https"].append(u)
            if u.rstrip("/") != u and up.path != "/":
                problems["trailing slash"].append(u)
    print("  total urls:", total)
    return seen, problems


def check_live(seen, host, limit=None):
    problems = defaultdict(list)
    items = list(seen)[:limit] if limit else list(seen)
    for u in items:
        path = urllib.parse.urlparse(u).path
        if path.endswith((".md", ".txt", ".xml")):
            # served straight from the backend by nginx (never the SPA shell), not prerendered
            r = get("/api" + path, host, allow_redirects=False)
            if r.status_code != 200:
                problems[f"dead in sitemap ({r.status_code})"].append(u)
            continue
        r = get("/api/seo/prerender", host, params={"path": path}, allow_redirects=False)
        if r.status_code != 200:
            problems[f"dead in sitemap ({r.status_code})"].append(u)
            continue
        html = r.text
        can = re.findall(r'rel="canonical" href="([^"]+)"', html)
        if not can:
            problems["no canonical"].append(u)
        elif can[0] != u:
            problems["canonical points elsewhere"].append(f"{u} -> {can[0]}")
        if re.search(r'name="robots"[^>]*noindex', html):
            problems["noindex page in sitemap"].append(u)
    return problems


if __name__ == "__main__":
    all_problems = defaultdict(list)
    for host in HOSTS:
        seen, probs = audit(host)
        for k, v in probs.items():
            all_problems[f"{host}: {k}"] += v
        live = check_live(seen, host, limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
        for k, v in live.items():
            all_problems[f"{host}: {k}"] += v
    print("\n===== PROBLEMS")
    if not all_problems:
        print("none")
    for k, v in all_problems.items():
        print(f"{k}: {len(v)}")
        for item in v[:8]:
            print("   ", item)
