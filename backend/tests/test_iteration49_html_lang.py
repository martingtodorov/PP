"""Iteration 49: `<html lang>` must reflect the storefront on every prerendered route.

Owner's SEO scan reported that every crawled page (EN, RO, CZ) shipped `lang="bg"`.
prerender.py now calls _set_lang() on the shell BEFORE any early return (private route,
looks-like-a-file, missing-content 404) so every branch stamps the right subtag.

These tests hit the live preview /api/seo/prerender endpoint with explicit X-Forwarded-Host
per storefront and assert (a) exactly one <html lang> attribute is present and (b) it carries
the plain language subtag (bg / en / cs / sl / de / ro / el), never a region-tagged code.
"""
import os
import re

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
UA = {"User-Agent": "Googlebot/2.1"}


def _prerender(host: str, path: str):
    r = requests.get(f"{BASE}/api/seo/prerender", params={"path": path},
                     headers={**UA, "X-Forwarded-Host": host}, timeout=30)
    return r.status_code, r.text


def _lang(html: str) -> str:
    matches = re.findall(r'<html[^>]*\slang="([^"]+)"', html)
    assert len(matches) == 1, f"expected exactly one <html lang=..>, got {len(matches)}"
    return matches[0]


# host -> expected html lang subtag
# NOTE: the Kubernetes preview ingress overwrites X-Forwarded-Host, so host-based storefronts
# (.bg / .ro / .gr) cannot be tested through /api/seo/prerender here — the local-nginx suite in
# test_nginx_redirects.py covers those. Path-prefix locales (/en, /cz, /si, /de) work regardless
# of Host because locale_of() checks the URL path first.
STOREFRONTS = [
    ("purepeptide.eu", "/en/", "en"),
    ("purepeptide.eu", "/cz/", "cs"),
    ("purepeptide.eu", "/si/", "sl"),
    ("purepeptide.eu", "/de/", "de"),
]


@pytest.mark.parametrize("host,root,lang", STOREFRONTS)
def test_home_page_lang(host, root, lang):
    status, body = _prerender(host, root)
    assert status == 200, (host, root, status)
    assert _lang(body) == lang


@pytest.mark.parametrize("host,root,lang", STOREFRONTS)
def test_catalog_lang(host, root, lang):
    status, body = _prerender(host, root.rstrip("/") + "/collections")
    assert status == 200
    assert _lang(body) == lang


@pytest.mark.parametrize("host,root,lang", STOREFRONTS)
def test_missing_product_still_gets_locale_lang(host, root, lang):
    """A 404 (no such product) must still stamp the storefront's lang, not fall back to bg."""
    status, body = _prerender(host, root.rstrip("/") + "/products/definitely-does-not-exist-xyz")
    assert status == 404
    assert _lang(body) == lang


@pytest.mark.parametrize("host,root,lang", STOREFRONTS)
def test_private_route_lang(host, root, lang):
    """Cart is a private route: prerender serves the untouched shell but lang must still be set."""
    status, body = _prerender(host, root.rstrip("/") + "/cart")
    assert status == 200
    assert _lang(body) == lang


@pytest.mark.parametrize("host,root,lang", STOREFRONTS)
def test_looks_like_a_file_lang(host, root, lang):
    """A stray .ext under a storefront path (e.g. old cached asset) still answers with locale lang."""
    status, body = _prerender(host, root.rstrip("/") + "/whatever.txt")
    # served as shell + 404
    assert status == 404
    assert _lang(body) == lang


def test_lang_is_never_bg_for_english_root():
    """Regression: owner reported /en/ carrying lang=bg — must be lang=en now."""
    _, body = _prerender("purepeptide.eu", "/en/")
    assert 'lang="bg"' not in body.split("</head>")[0][:600]


def test_lang_is_never_region_tagged():
    """html lang must be a plain subtag ("cs" not "cs-CZ", "sl" not "sl-SI", "el" not "el-GR")."""
    for host, root, lang in STOREFRONTS:
        _, body = _prerender(host, root)
        assert "-" not in _lang(body), (host, root)


def test_hreflang_set_stays_intact():
    """Every rendered page must still carry the 11 hreflang alternates + x-default."""
    _, body = _prerender("purepeptide.eu", "/en/")
    alternates = re.findall(r'<link rel="alternate" hreflang="([^"]+)"', body)
    # 11 locales + x-default
    assert len(alternates) == 12, alternates
    assert "x-default" in alternates
    assert "bg-BG" in alternates and "cs-CZ" in alternates and "sl-SI" in alternates


def test_canonical_of_en_root():
    _, body = _prerender("purepeptide.eu", "/en/")
    assert '<link rel="canonical" href="https://purepeptide.eu/en/"' in body


def test_canonical_of_cz_root():
    _, body = _prerender("purepeptide.eu", "/cz/")
    assert '<link rel="canonical" href="https://purepeptide.eu/cz/"' in body


def test_canonical_of_bg_root():
    _, body = _prerender("purepeptide.bg", "/")
    assert '<link rel="canonical" href="https://purepeptide.bg/"' in body


def test_hidden_prerender_wrapper_present():
    _, body = _prerender("purepeptide.eu", "/en/")
    assert '<div id="pp-prerender">' in body
    assert "#pp-prerender{position:absolute" in body  # HIDE_STYLE

