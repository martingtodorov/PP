"""Extra live coverage for iter52: brand-suffix titles, rotation 404s, product JSON-LD, sitemap image ns."""
import re
import requests

API = "http://localhost:8001/api"
HOST = {"Host": "purepeptide.bg"}


def _title(html: str) -> str:
    m = re.search(r"<title>([^<]*)</title>", html)
    return m.group(1) if m else ""


def _prerender(path: str) -> requests.Response:
    return requests.get(f"{API}/seo/prerender", params={"path": path}, headers=HOST, timeout=30)


# ---- title suffix across page types ----
def test_title_suffix_home_no_double_brand():
    r = _prerender("/")
    assert r.status_code == 200
    t = _title(r.text)
    assert "PurePeptide" in t
    # No double brand suffix
    assert t.count("PurePeptide") == 1, t


def test_title_suffix_product():
    r = _prerender("/products/21-retatrutide-5-lrp")
    assert r.status_code == 200
    t = _title(r.text)
    assert t.endswith("- PurePeptide"), t


def test_title_suffix_cart_and_track():
    for path in ("/cart", "/track"):
        r = _prerender(path)
        assert r.status_code == 200, path
        t = _title(r.text)
        assert "PurePeptide" in t, (path, t)


def test_title_suffix_static_pages():
    for path in ("/pages/faq", "/pages/chemical-analysis"):
        r = _prerender(path)
        assert r.status_code == 200, path
        t = _title(r.text)
        assert "PurePeptide" in t, (path, t)


# ---- rotation 404s at prerender level ----
def test_rotation_404_prerender_retatrutide():
    assert _prerender("/products/21-retatrutide-5-lrp").status_code == 200
    assert _prerender("/products/21-retatrutide-5").status_code == 404


def test_rotation_404_prerender_ghkcu():
    r_live = requests.get(f"{API}/products/1-ghk-cu-dbo", params={"locale": "bg"}, timeout=30)
    r_dead = requests.get(f"{API}/products/1-ghk-cu", params={"locale": "bg"}, timeout=30)
    assert r_live.status_code == 200
    assert r_dead.status_code == 404
    assert _prerender("/products/1-ghk-cu-dbo").status_code == 200
    assert _prerender("/products/1-ghk-cu").status_code == 404


def test_non_rotated_products_still_serve():
    for h in ("bpc-157-5", "mots-c", "pt-141"):
        r = requests.get(f"{API}/products/{h}", params={"locale": "bg"}, timeout=30)
        assert r.status_code == 200, (h, r.status_code)
        assert _prerender(f"/products/{h}").status_code == 200, h


# ---- product structured data completeness ----
def test_product_json_ld_completeness():
    html = _prerender("/products/21-retatrutide-5-lrp").text
    required_bits = [
        '"@type": "Product"',
        '"image"',
        '"availability": "https://schema.org/InStock"',
        '"priceValidUntil"',
        '"hasMerchantReturnPolicy"',
        '"returnShippingFeesAmount"',
        '"shippingDetails"',
        '"brand"',
    ]
    missing = [b for b in required_bits if b not in html]
    assert not missing, f"Missing JSON-LD fields: {missing}"
    # image URLs absolute
    imgs = re.findall(r'"image":\s*(\[[^\]]+\]|"[^"]+")', html)
    assert imgs
    assert "http" in imgs[0]
    # productID / sku / mpn present
    assert '"sku"' in html or '"productID"' in html or '"mpn"' in html


# ---- sitemap ----
def child_sitemaps(kind: str = "") -> str:
    """The parent /sitemap.xml is an index (Shopify shape) — glue the children together."""
    index = requests.get(f"{API}/sitemap.xml", headers=HOST, timeout=60)
    assert index.status_code == 200 and "<sitemapindex" in index.text
    out = ""
    for child in re.findall(r"<loc>([^<]+)</loc>", index.text):
        name = child.rsplit("/", 1)[-1]
        if "agentic" in name or (kind and f"_{kind}_" not in name):
            continue
        out += requests.get(f"{API}/{name}", headers=HOST, timeout=60).text
    return out


def test_sitemap_image_namespace_and_no_retired():
    xml = child_sitemaps()
    assert 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"' in xml
    # No retired handles
    assert "/products/21-retatrutide-5<" not in xml
    assert "/products/21-retatrutide-5/" not in xml
    assert "21-retatrutide-5-lrp" in xml
    # every product url has an image:loc
    urls = re.findall(r"<url>.*?</url>", xml, re.DOTALL)
    prod_urls = [u for u in urls if "/products/" in u]
    assert prod_urls
    assert all("<image:loc>" in u for u in prod_urls[:10])
    # hreflang alternates still there
    assert "hreflang" in xml
