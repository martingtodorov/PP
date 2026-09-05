"""A sitemap may only list URLs of its own domain.

purepeptide.bg/sitemap.xml used to list all 726 URLs of all four storefronts, so Search Console
reported hundreds of foreign pages for the Bulgarian property.
"""
import os
import re

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE = "http://localhost:8001"
HOSTS = {
    "purepeptide.bg": ["purepeptide.bg"],
    "purepeptide.eu": ["purepeptide.eu"],
    "purepeptide.ro": ["purepeptide.ro"],
    "purepeptide.gr": ["purepeptide.gr"],
    "purepeptide-labs.bg": ["purepeptide.bg"],          # the Bulgarian alias lists the .bg URLs
}


def sitemap(host: str) -> str:
    """The parent sitemap is an index (like Shopify's) — return the children glued together."""
    r = requests.get(f"{BASE}/api/sitemap.xml", headers={"Host": host}, timeout=30)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert "<sitemapindex" in r.text
    out = ""
    for child in re.findall(r"<loc>([^<]+)</loc>", r.text):
        path = "/" + child.split("/", 3)[3]
        if "agentic" in path:                      # the AI entry-point file is checked separately
            continue
        c = requests.get(f"{BASE}/api{path}", headers={"Host": host}, timeout=30)
        assert c.status_code == 200, path
        out += c.text
    return out


def test_the_index_links_one_file_per_kind():
    xml = requests.get(f"{BASE}/api/sitemap.xml", headers={"Host": "purepeptide.bg"}, timeout=30).text
    files = [u.rsplit("/", 1)[-1] for u in re.findall(r"<loc>([^<]+)</loc>", xml)]
    assert files == ["sitemap_agentic_discovery.xml", "sitemap_products_1.xml",
                     "sitemap_collections_1.xml", "sitemap_pages_1.xml", "sitemap_blogs_1.xml"]
    assert all(u.startswith("https://purepeptide.bg/")
               for u in re.findall(r"<loc>([^<]+)</loc>", xml))


def locs(xml: str):
    return re.findall(r"<loc>([^<]+)</loc>", xml)


@pytest.mark.parametrize("host,domains", HOSTS.items())
def test_a_sitemap_lists_only_its_own_domain(host, domains):
    found = {u.split("/")[2] for u in locs(sitemap(host))}
    assert found == set(domains), f"{host} listed foreign domains: {found}"


def test_the_bulgarian_sitemap_is_one_page_per_url():
    urls = locs(sitemap("purepeptide.bg"))
    assert len(urls) == len(set(urls))
    assert all("/en/" not in u and "/cz/" not in u for u in urls)
    assert "https://purepeptide.bg/" in urls                # the home page is there


def test_the_shared_domain_keeps_all_eight_prefixed_languages():
    urls = locs(sitemap("purepeptide.eu"))
    prefixes = {u.split("/")[3] for u in urls}
    assert prefixes == {"en", "fr", "de", "cz", "hu", "pl", "sk", "si"}
    # every language holds the same number of pages
    counts = {p: sum(1 for u in urls if u.split("/")[3] == p) for p in prefixes}
    assert len(set(counts.values())) == 1, counts


def test_hreflang_alternates_still_point_at_every_language():
    xml = sitemap("purepeptide.bg")
    first = xml.split("</url>")[0]
    for host in ("purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr"):
        assert host in first
    assert 'hreflang="x-default"' in first


@pytest.mark.parametrize("host", ["purepeptide.bg", "purepeptide.eu"])
def test_robots_and_the_agent_sitemap_stay_on_their_own_domain(host):
    robots = requests.get(f"{BASE}/api/robots.txt", headers={"Host": host}, timeout=20).text
    sitemaps = [l.split(": ", 1)[1] for l in robots.splitlines() if l.startswith("Sitemap:")]
    assert sitemaps and all(s.split("/")[2] == host for s in sitemaps), sitemaps
    agentic = requests.get(f"{BASE}/api/sitemap_agentic_discovery.xml",
                           headers={"Host": host}, timeout=20).text
    assert all(u.split("/")[2] == host for u in locs(agentic))


def child(host: str, kind: str) -> str:
    return requests.get(f"{BASE}/api/sitemap_{kind}_1.xml", headers={"Host": host}, timeout=60).text


def test_product_entries_match_the_shopify_shape():
    xml = child("purepeptide.bg", "products")
    assert "<priority>" not in xml                       # Shopify does not emit priority
    home, first = (re.sub(r"<xhtml:link[^>]*>", "", u)
                   for u in re.findall(r"<url>.*?</url>", xml)[:2])
    assert home == "<url><loc>https://purepeptide.bg/</loc><changefreq>daily</changefreq></url>"
    assert "<changefreq>daily</changefreq>" in first
    assert re.search(r"<lastmod>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+\-]\d\d:\d\d</lastmod>", first), first
    assert first.count("<image:image>") == 1             # the featured image only
    assert "<image:title>" in first and "- PurePeptide</image:caption>" in first


def test_collection_and_page_entries_match_the_shopify_shape():
    cols = child("purepeptide.bg", "collections")
    assert "<changefreq>daily</changefreq>" in cols and "<image:title>" in cols
    pages = child("purepeptide.bg", "pages")
    assert "<changefreq>weekly</changefreq>" in pages and "<image:image>" not in pages
    # the Cyrillic slug is percent-encoded, exactly like the Shopify export
    assert "/pages/%D0%BA%D0%B0%D0%BA%D0%B2%D0%BE" in pages


def test_agentic_sitemap_is_only_the_agent_guide():
    xml = requests.get(f"{BASE}/api/sitemap_agentic_discovery.xml",
                       headers={"Host": "purepeptide.bg"}, timeout=20).text
    assert locs(xml) == ["https://purepeptide.bg/agents.md", "https://purepeptide.bg/llms.txt"]
    assert "<changefreq>weekly</changefreq>" in xml


def test_agents_md_and_llms_txt_are_served():
    for path in ("/agents.md", "/llms.txt"):
        r = requests.get(f"{BASE}/api{path}", headers={"Host": "purepeptide.bg"}, timeout=30)
        assert r.status_code == 200 and len(r.text) > 200, path


@pytest.mark.parametrize("path", [
    "/sitemap.xml", "/sitemap_products_1.xml", "/sitemap_collections_1.xml",
    "/sitemap_pages_1.xml", "/sitemap_blogs_1.xml", "/sitemap_agentic_discovery.xml",
    "/robots.txt", "/llms.txt", "/agents.md",
])
def test_head_is_answered(path):
    """FastAPI routes are GET-only, so every validator probing with HEAD got a 405 first."""
    r = requests.head(f"{BASE}/api{path}", headers={"Host": "purepeptide.bg"}, timeout=30)
    assert r.status_code == 200, (path, r.status_code)


def test_sitemaps_are_not_cached_for_an_hour():
    """A stale CDN copy outlived a deploy and looked like the fix had not shipped."""
    for path in ("/sitemap.xml", "/sitemap_products_1.xml", "/robots.txt"):
        r = requests.get(f"{BASE}/api{path}", headers={"Host": "purepeptide.bg"}, timeout=30)
        assert "max-age=300" in r.headers.get("cache-control", ""), path


def test_the_shared_domain_stays_well_inside_the_sitemap_limits():
    xml = child("purepeptide.eu", "products")
    assert len(xml.encode()) < 50 * 1024 * 1024
    assert xml.count("<url>") < 50000
