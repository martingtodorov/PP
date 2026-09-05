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
    r = requests.get(f"{BASE}/api/sitemap.xml", headers={"Host": host}, timeout=30)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    return r.text


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
    assert "https://purepeptide.bg" in urls                 # the home page is there


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
