"""
Verification tests for Cloudflare Bot Fight Mode finding.
Read-only GET requests from this datacenter IP to production hosts + preview regressions.
"""
import os
import requests
import pytest

PROD_HOSTS = [
    "https://purepeptide.bg",
    "https://purepeptide.eu",
    "https://purepeptide.ro",
    "https://purepeptide.gr",
]
PATHS = ["/", "/robots.txt", "/sitemap.xml", "/llms.txt", "/agents.md", "/api/settings"]

USER_AGENTS = {
    "curl-default": "curl/7.88.1",
    "python-requests": None,  # requests default
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "AhrefsBot": "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
    "ScreamingFrog": "Screaming Frog SEO Spider/19.0",
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.0; +https://openai.com/gptbot",
    "Chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

PREVIEW = os.environ.get("REACT_APP_BACKEND_URL", "https://peptide-checkout-32.preview.emergentagent.com").rstrip("/")


def _get(url, ua=None, timeout=15):
    headers = {}
    if ua:
        headers["User-Agent"] = ua
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        return r
    except Exception as e:
        return e


# --- Production host status matrix ---
@pytest.mark.parametrize("host", PROD_HOSTS)
@pytest.mark.parametrize("path", PATHS)
def test_production_no_403(host, path):
    url = f"{host}{path}"
    r = _get(url)
    if isinstance(r, Exception):
        pytest.fail(f"NETWORK ERROR {url}: {r}")
    # Report evidence, do not hard-fail on non-200 (redirects OK); but a 403 with cf-mitigated is critical
    cf_ray = r.headers.get("cf-ray", "")
    cf_mit = r.headers.get("cf-mitigated", "")
    server = r.headers.get("server", "")
    print(f"[{r.status_code}] {url} server={server} cf-ray={cf_ray} cf-mitigated={cf_mit}")
    if r.status_code == 403:
        pytest.fail(
            f"403 seen at {url}. UA=python-requests default. "
            f"server={server} cf-ray={cf_ray} cf-mitigated={cf_mit} "
            f"body[:200]={r.text[:200]!r}"
        )


# --- User-Agent matrix on purepeptide.bg ---
@pytest.mark.parametrize("ua_name,ua_val", list(USER_AGENTS.items()))
@pytest.mark.parametrize("path", ["/", "/api/settings"])
def test_bg_user_agents(ua_name, ua_val, path):
    url = f"https://purepeptide.bg{path}"
    r = _get(url, ua=ua_val)
    if isinstance(r, Exception):
        pytest.fail(f"NETWORK ERROR {url} UA={ua_name}: {r}")
    cf_ray = r.headers.get("cf-ray", "")
    cf_mit = r.headers.get("cf-mitigated", "")
    server = r.headers.get("server", "")
    ctype = r.headers.get("content-type", "")
    # Detect Cloudflare challenge page
    body_snip = r.text[:400]
    is_challenge = ("Just a moment" in body_snip or "cf-chl" in body_snip or "challenge-platform" in body_snip)
    print(
        f"[{r.status_code}] UA={ua_name} {url} server={server} cf-ray={cf_ray} "
        f"cf-mitigated={cf_mit} ctype={ctype} challenge={is_challenge}"
    )
    if r.status_code == 403 or is_challenge:
        pytest.fail(
            f"BLOCK at {url} UA={ua_name}: status={r.status_code} challenge={is_challenge} "
            f"server={server} cf-ray={cf_ray} cf-mitigated={cf_mit}"
        )


# --- SEO robots content on production purepeptide.bg (report but don't fail hard on stale build) ---
def test_prod_bg_robots_content():
    r = _get("https://purepeptide.bg/robots.txt")
    if isinstance(r, Exception):
        pytest.fail(f"NETWORK ERROR: {r}")
    body = r.text
    print(f"[status={r.status_code}] robots.txt length={len(body)}")
    print(f"BODY:\n{body}")
    assert r.status_code == 200, f"robots.txt not 200: {r.status_code}"
    assert "Disallow: /admin" in body, "Missing Disallow: /admin"
    # These should NOT be present (they were removed)
    for bad in ["/cart", "/checkout", "/account"]:
        # explicit "Disallow: /cart" style
        assert f"Disallow: {bad}" not in body, f"Stale build: still has Disallow: {bad}"


# --- Preview regression: robots.txt ---
def test_preview_robots_no_cart_checkout_account():
    r = _get(f"{PREVIEW}/api/robots.txt")
    assert not isinstance(r, Exception), f"network err {r}"
    assert r.status_code == 200, f"preview robots.txt {r.status_code}"
    body = r.text
    print(f"PREVIEW ROBOTS:\n{body}")
    for bad in ["/cart", "/checkout", "/account"]:
        assert f"Disallow: {bad}" not in body, f"Preview still disallows {bad}"
    assert "Disallow: /admin" in body


# --- Preview regression: /api/seo/prerender?path=/cart returns noindex,follow ---
def test_preview_prerender_cart_noindex():
    r = _get(f"{PREVIEW}/api/seo/prerender?path=/cart")
    assert not isinstance(r, Exception), f"network err {r}"
    assert r.status_code == 200, f"prerender cart {r.status_code}"
    html = r.text
    # Look for robots meta with noindex, follow
    import re
    m = re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']robots["\']', html, re.I)
    assert m, f"no robots meta tag in prerender output. head={html[:500]!r}"
    content = m.group(1).lower()
    print(f"PRERENDER /cart robots meta = {content!r}")
    assert "noindex" in content, f"missing noindex: {content}"
    assert "follow" in content, f"missing follow: {content}"
