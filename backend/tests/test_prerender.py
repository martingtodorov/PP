"""Server-side prerender: every public route must answer with finished, crawlable HTML."""
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"


def get(path, host="purepeptide.bg"):
    return requests.get(f"{API}/seo/prerender", params={"path": path}, headers={"Host": host}, timeout=30)


def head_of(html, pattern):
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else ""


def _a_product():
    p = requests.get(f"{API}/products", params={"locale": "bg"}, timeout=30).json()["products"][0]
    return p["handle"], p["title"]


def test_a_product_page_is_fully_rendered():
    handle, title = _a_product()
    r = get(f"/products/{handle}")
    assert r.status_code == 200 and r.headers["X-Prerender"] == "1"
    html = r.text
    assert head_of(html, r"<title>(.*?)</title>")
    assert head_of(html, r'rel="canonical" href="([^"]+)"') == f"https://purepeptide.bg/products/{handle}"
    assert head_of(html, r'og:type" content="([^"]+)"') == "product"
    assert html.count("<h1") == 1, "exactly one H1 per page"
    assert title[:12] in head_of(html, r"<h1>(.*?)</h1>")
    assert '"@type": "Product"' in html and '"Offer"' in html and "BreadcrumbList" in html
    assert '"priceCurrency": "EUR"' in html and "schema.org/InStock" in html or "OutOfStock" in html
    assert "<img " in html
    assert html.count("hreflang=") >= 12       # 11 locales + x-default
    assert len(html) > 12000


def test_the_home_page_carries_its_own_title_and_content():
    html = get("/").text
    assert "PurePeptide" in head_of(html, r"<title>(.*?)</title>")
    assert head_of(html, r'rel="canonical" href="([^"]+)"') == "https://purepeptide.bg/"
    assert html.count("<h1") == 1
    assert '"@type": "Organization"' in html and '"@type": "WebSite"' in html
    assert "/products/" in html, "the home page must link to products"


def test_collections_articles_and_pages_are_rendered():
    coll = requests.get(f"{API}/collections", params={"locale": "bg"}, timeout=30).json()["collections"][0]
    html = get(f"/collections/{coll['handle']}").text
    assert html.count("<h1") == 1 and "ItemList" in html and "/products/" in html

    art = requests.get(f"{API}/articles", params={"locale": "bg"}, timeout=30).json()["articles"][0]
    html = get(f"/articles/{art['handle']}").text
    assert html.count("<h1") == 1 and '"@type": "Article"' in html

    html = get("/pages/faq").text
    assert html.count("<h1") == 1 and '"@type": "WebPage"' in html


def test_each_domain_gets_its_own_canonical_and_language():
    for host, canonical, lang in [("purepeptide.ro", "https://purepeptide.ro/", "ro_RO"),
                                  ("purepeptide.gr", "https://purepeptide.gr/", "el_GR"),
                                  ("purepeptide.eu", "https://purepeptide.eu/en/", "en")]:
        html = get("/en/" if host == "purepeptide.eu" else "/", host=host).text
        assert head_of(html, r'rel="canonical" href="([^"]+)"') == canonical, host
        assert head_of(html, r'og:locale" content="([^"]+)"') == lang, host


def test_private_and_unknown_routes_fall_back_to_the_spa():
    for path in ["/cart", "/checkout", "/track", "/account/orders", "/admin/settings",
                 "/products/does-not-exist", "/favicon.ico"]:
        assert get(path).status_code == 404, path


def test_imported_copy_never_adds_a_second_h1():
    import prerender
    assert prerender.demote("<h1>Какво е DSIP?</h1><p>x</p>") == "<h2>Какво е DSIP?</h2><p>x</p>"
    assert prerender.demote('<H1 class="a">T</H1>') == "<h2>T</h2>"


def test_an_admin_write_drops_the_cached_html():
    import prerender
    prerender._pages[("x", "/")] = (9e9, "stale")
    prerender.bump()
    assert prerender._pages == {}
