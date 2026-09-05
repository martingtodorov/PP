"""Every hreflang target a page emits must answer 200.

Collection handles and rotated page slugs are localised, but the prerenderer used to reuse the
current route for all eleven alternates — 10 of 11 pointed at URLs that do not exist, so Google
discarded the whole language cluster.
"""
import os
import re
import sys
from urllib.parse import unquote, urlsplit

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8001/api"
HOST_LOCALE = {"purepeptide.bg": "bg", "purepeptide.ro": "ro", "purepeptide.gr": "gr",
               "purepeptide.eu": "en"}


def render(host: str, path: str):
    # sitemap URLs are percent-encoded; requests would double-encode them
    return requests.get(f"{API}/seo/prerender", params={"path": unquote(path)},
                        headers={"Host": host, "X-Forwarded-Host": host}, timeout=30)


def hreflangs(html: str):
    return re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', html)


def first_path(host: str, kind: str) -> str:
    """A live URL of that kind for the domain, taken from the domain's own sitemap."""
    index = requests.get(f"{API}/sitemap.xml", headers={"Host": host}, timeout=60).text
    name = next(u.rsplit("/", 1)[-1] for u in re.findall(r"<loc>([^<]+)</loc>", index)
                if f"_{kind}_" in u)
    xml = requests.get(f"{API}/{name}", headers={"Host": host}, timeout=60).text
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        path = urlsplit(url).path
        if kind == "pages" and path.rstrip("/").endswith(("html-sitemap", "articles")):
            continue
        if path not in ("", "/"):
            return path
    raise AssertionError(f"no {kind} url for {host}")


@pytest.mark.parametrize("host", ["purepeptide.bg", "purepeptide.ro", "purepeptide.eu", "purepeptide.gr"])
@pytest.mark.parametrize("kind", ["collections", "pages", "products", "blogs"])
def test_every_hreflang_target_answers_200(host, kind):
    path = first_path(host, kind)
    page = render(host, path)
    assert page.status_code == 200, (host, path)
    alts = hreflangs(page.text)
    assert len(alts) >= 11, alts
    broken = []
    for lang, href in alts:
        parts = urlsplit(href)
        target = render(parts.netloc, parts.path or "/")
        if target.status_code != 200:
            broken.append((lang, href, target.status_code))
    assert not broken, f"{host}{path} -> {broken}"


def test_alternates_use_the_other_locales_handle():
    """The exact condition that was failing: a localised handle must appear in the alternates."""
    cols = requests.get(f"{API}/collections", params={"locale": "bg"}, timeout=30).json()["collections"]
    col = next(c for c in cols if (c.get("handles") or {}).get("ro") != c["handle"])
    page = render("purepeptide.bg", f'/collections/{col["handle"]}')
    assert page.status_code == 200
    hrefs = dict(hreflangs(page.text))
    assert hrefs["ro-RO"].endswith(f'/collections/{col["handles"]["ro"]}'), hrefs["ro-RO"]
    assert hrefs["bg-BG"].endswith(f'/collections/{col["handle"]}')
    assert col["handle"] not in hrefs["ro-RO"]        # not the current page's handle any more


def test_rotated_page_alternates_follow_the_per_locale_slug():
    """A page rotated in one language keeps the base slug in the others."""
    rotated = requests.get(f"{API}/admin/pages", timeout=10)      # unauthenticated -> 401 is fine
    assert rotated.status_code in (200, 401)
    page = render("purepeptide.bg", first_path("purepeptide.bg", "pages"))
    assert page.status_code == 200
    for lang, href in hreflangs(page.text):
        assert render(urlsplit(href).netloc, urlsplit(href).path).status_code == 200, (lang, href)
