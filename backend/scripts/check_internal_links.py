"""Read-only crawl of sitemap pages AND every internal anchor in their prerendered HTML.

python scripts/check_internal_links.py --base "$REACT_APP_BACKEND_URL" --report audit.json
Add --in-process when preview ingress overwrites X-Forwarded-Host. This reads the same database
through the real FastAPI routes without starting services or changing any stored content.
Uses the chosen backend, never the production hosts linked in the HTML. No redirects are
followed: an internal link should point straight to its published, canonical 200 URL.
Also called by check_sitemap.py, so the existing release check covers internal links.
"""
import argparse
import asyncio
import json
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx


class PageLinks(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.canonical = ""
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")


def normalized(url):
    p = urlsplit(url)
    path = quote(unquote(p.path or "/"), safe="/-_.~")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))


async def audit(client, base):
    config = await client.get(f"{base}/api/locales")
    config.raise_for_status()
    routes = config.json()["routes"]
    origins = {r["origin"].rstrip("/") for r in routes.values()}
    hosts = {urlsplit(origin).hostname for origin in origins}
    hosts |= {f"www.{host}" for host in hosts if not host.startswith("www.")}
    references, pages, broken, noncanonical = defaultdict(set), {}, [], []
    sitemap_errors = []

    # Domain-aware sitemaps, not just the Bulgarian preview sitemap. Preserve ingress Host.
    for origin in sorted(origins):
        host = urlsplit(origin).netloc
        pending, visited = ["/sitemap.xml"], set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            try:
                response = await client.get(f"{base}/api{path}", headers={"X-Forwarded-Host": host})
                response.raise_for_status()
                root = ElementTree.fromstring(response.text)
                # Only page/sitemap locations: descendant image:loc entries are image metadata,
                # not HTML pages or internal <a href> targets.
                locations = [el.text for el in root.findall("./{*}*/{*}loc") if el.text]
                if root.tag.endswith("sitemapindex"):
                    pending.extend(urlsplit(url).path for url in locations)
                else:
                    for url in locations:
                        if urlsplit(url).netloc != host:
                            sitemap_errors.append({"url": origin + path, "error": f"Foreign sitemap URL: {url}; forwarded host may have been overwritten"})
                        references[normalized(url)].add(origin + path)
            except (httpx.HTTPError, ElementTree.ParseError) as exc:
                sitemap_errors.append({"url": origin + path, "error": str(exc)})
    # /collections is linked internally but does not need to be in the XML sitemap.
    for route in routes.values():
        references[normalized(f'{route["origin"]}{route.get("prefix", "")}/collections')].add("catalog index")

    async def fetch(url):
        p = urlsplit(url)
        route = unquote(p.path)
        headers = {"X-Forwarded-Host": p.netloc}
        # Public files/API links are not HTML routes; test their real endpoint instead.
        is_file = "." in route.rsplit("/", 1)[-1] or route.startswith("/api/")
        api_document = route in ("/agents.md", "/llms.txt", "/llms-full.txt", "/robots.txt") or route.startswith("/sitemap") and route.endswith(".xml")
        target = (f"{base}/api{p.path}" if api_document else f"{base}{p.path}") if is_file else f"{base}/api/seo/prerender"
        params = None if is_file else {"path": route + (f"?{p.query}" if p.query else "")}
        try:
            response = await client.get(target, params=params, headers=headers)
            parser = PageLinks(response.text) if not is_file and response.status_code == 200 else None
            return url, response.status_code, parser
        except httpx.HTTPError as exc:
            return url, str(exc), None

    while todo := sorted(set(references) - set(pages)):
        # Small batches: bounded load, with each distinct URL fetched only once.
        for offset in range(0, len(todo), 4):
            for url, status, parser in await asyncio.gather(*(fetch(u) for u in todo[offset:offset + 4])):
                pages[url] = status
                if status != 200:
                    continue
                if not parser:
                    continue
                if parser.canonical and normalized(parser.canonical).rstrip("/") != url.split("?")[0].rstrip("/"):
                    noncanonical.append({"url": url, "canonical": parser.canonical})
                for href in parser.links:
                    if href.startswith("#"):
                        continue
                    target = normalized(urljoin(url, href))
                    parts = urlsplit(target)
                    if parts.scheme in ("http", "https") and parts.hostname in hosts:
                        references[target].add(url)
        if len(pages) > 10000:
            sitemap_errors.append({"error": "Crawl safety limit exceeded; audit is incomplete"})
            break

    for url, status in pages.items():
        if status != 200:
            broken.append({"url": url, "status": status, "sources": sorted(references[url])})
    for item in noncanonical:
        item["sources"] = sorted(references[item["url"]])
    return {"checked": len(pages), "broken": broken, "noncanonical": noncanonical,
            "sitemap_errors": sitemap_errors}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--report")
    parser.add_argument("--in-process", action="store_true")
    args = parser.parse_args()
    transport = None
    if args.in_process:
        from dotenv import load_dotenv
        backend = Path(__file__).resolve().parents[1]
        load_dotenv(backend / ".env")
        sys.path.insert(0, str(backend))
        from server import app
        transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, timeout=60, follow_redirects=False) as client:
        report = await audit(client, args.base.rstrip("/"))
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report["broken"] or report["noncanonical"] or report["sitemap_errors"]))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))