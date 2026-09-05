"""Brand suffix in every title, one live URL per rotated product, images in the sitemap."""
import os
import re
import sys

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prerender  # noqa: E402
import server  # noqa: E402

API = "http://localhost:8001/api"
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


# ---------- brand suffix ----------

@pytest.mark.parametrize("raw,expected", [
    ("Ретатрутид (Retatrutide) 5/10/30mg | цена", "Ретатрутид (Retatrutide) 5/10/30mg | цена - PurePeptide"),
    ("Сермарелин", "Сермарелин - PurePeptide"),
    ("PurePeptide – Nº1 пептиди", "PurePeptide – Nº1 пептиди"),   # already names the brand
    ("", "PurePeptide"),
    ("Цена на GH| пептид", "Цена на GH | пептид - PurePeptide"),  # pipe spacing kept
])
def test_brand_title(raw, expected):
    assert prerender.brand_title(raw) == expected


def test_frontend_mirrors_the_suffix():
    seo = open(os.path.join(ROOT, "frontend", "src", "lib", "seo.js")).read()
    assert 'const BRAND = "PurePeptide"' in seo
    assert "${text} - ${BRAND}" in seo
    assert "brandTitle(title)" in seo
    pages = os.path.join(ROOT, "frontend", "src", "pages")
    for name in os.listdir(pages):
        if name.endswith(".jsx"):
            assert " | PurePeptide" not in open(os.path.join(pages, name)).read(), name


# ---------- one live URL per rotated document ----------

ROTATED = {"handle": "prod", "translations": {"bg": {"handle": "prod-brk"}},
           "rotations": [{"locale": "bg", "from": "prod", "to": "prod-lrp"},
                         {"locale": "bg", "from": "prod-lrp", "to": "prod-brk"}]}


@pytest.mark.parametrize("requested,retired", [
    ("prod-brk", False),   # published
    ("prod-lrp", True),    # intermediate rotation — was a live duplicate before the fix
    ("prod", True),        # the delisted url
])
def test_only_the_published_handle_serves(requested, retired):
    assert server.retired_handle(ROTATED, "bg", requested) is retired
    assert prerender._retired(ROTATED, "bg", requested) is retired


def test_untouched_locales_are_not_retired():
    assert server.retired_handle(ROTATED, "ro", "prod") is False
    assert server.retired_handle({"handle": "x"}, "bg", "x") is False


def test_rotation_entry_retires_the_previously_published_handle():
    src = open(os.path.join(ROOT, "backend", "server.py")).read()
    body = src.split("async def rotate_content", 1)[1].split("async def rotate_one", 1)[0]
    assert "previous = published_handle(doc, loc) or handle" in body
    assert '"from": previous' in body


# ---------- live checks ----------

def test_live_product_title_and_404s():
    assert requests.get(f"{API}/products/21-retatrutide-5-lrp", params={"locale": "bg"}, timeout=30).status_code == 200
    assert requests.get(f"{API}/products/21-retatrutide-5", params={"locale": "bg"}, timeout=30).status_code == 404
    html = requests.get(f"{API}/seo/prerender", params={"path": "/products/21-retatrutide-5-lrp"},
                        headers={"Host": "purepeptide.bg"}, timeout=30).text
    assert re.search(r"<title>[^<]*- PurePeptide</title>", html)
    assert '"availability": "https://schema.org/InStock"' in html
    assert '"returnShippingFeesAmount"' in html
    assert '"priceValidUntil"' in html


def test_sitemap_declares_product_images():
    xml = requests.get(f"{API}/sitemap.xml", headers={"Host": "purepeptide.bg"}, timeout=60).text
    assert 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"' in xml
    product = [u for u in re.findall(r"<url>.*?</url>", xml) if "/products/" in u]
    assert product and all("<image:loc>" in u for u in product[:5])


def test_html_is_stable_between_requests():
    """No rolling dates: the same URL must render byte-identical HTML on every deploy/day."""
    url = f"{API}/seo/prerender"
    a = requests.get(url, params={"path": "/products/21-retatrutide-5-lrp"}, timeout=30).text
    b = requests.get(url, params={"path": "/products/21-retatrutide-5-lrp"}, timeout=30).text
    assert a == b
    assert f'"priceValidUntil": "{prerender.datetime.now(prerender.timezone.utc).year + 1}-12-31"' in a
    js = open(os.path.join(ROOT, "frontend", "src", "lib", "schema.js")).read()
    assert "getUTCFullYear() + 1}-12-31" in js          # the React build must agree with the server


def test_sitemap_lastmod_is_the_record_date():
    xml = requests.get(f"{API}/sitemap.xml", headers={"Host": "purepeptide.bg"}, timeout=60).text
    days = set(re.findall(r"<lastmod>([\d-]+)</lastmod>", xml))
    assert days and len(days) > 1, "every url carrying today's date is a worthless lastmod signal"


def test_retired_url_is_a_dead_end_not_a_redirect():
    block = open(os.path.join(ROOT, "frontend", "src", "components", "NotFoundBlock.jsx")).read()
    assert "useNavigate" not in block and "navigate(" not in block
    assert 'data-testid="not-found-catalog-link"' in block


# ---------- imported Shopify slug aliases are gone (owner: hard 404) ----------

ALIASES = ["about", "contacts", "what-are-peptides", "terms-of-service", "shipping-policy",
           "partners"]


@pytest.mark.parametrize("slug", ALIASES)
def test_page_aliases_404_in_every_locale(slug):
    for loc in ("bg", "en", "de", "ro"):
        r = requests.get(f"{API}/pages/{slug}", params={"locale": loc}, timeout=30)
        assert r.status_code == 404, (slug, loc, r.status_code)


@pytest.mark.parametrize("slug", ["chemical-analysis", "privacy-policy", "refund-policy"])
def test_the_real_pages_still_serve(slug):
    assert requests.get(f"{API}/pages/{slug}", params={"locale": "bg"}, timeout=30).status_code == 200


def test_importer_no_longer_publishes_aliases():
    src = open(os.path.join(ROOT, "backend", "matrixify_import.py")).read()
    body = src.split("def import_pages", 1)[1].split("def import_articles", 1)[0]
    assert "PAGE_MAP.get(handle)" not in body
    assert 'delete_many({"canonical_slug"' in body


# ---------- a rotation code is never reused ----------

def test_rotation_handles_are_globally_unique():
    src = open(os.path.join(ROOT, "backend", "server.py")).read()
    assert "async def next_rotation_handle" in src
    assert "db.rotation_log" in src
    assert "await next_rotation_handle(kind, base, doc, loc)" in src
    assert 'await next_rotation_handle("pages", base, doc, loc)' in src
    assert "await db.rotation_log.create_index(\"handle\", unique=True)" in src
