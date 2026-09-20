"""The country block still works when a country is listed, but the list is EMPTY by default.

20.06.2026: the owner switched the US/CA block off — `blocked_countries: []`. The tests below still
render the template WITH ["US", "CA"] to prove the mechanism works if it is ever turned back on;
`test_nobody_is_blocked_by_default` guards the default.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import jinja2
import pytest
import requests

ANSIBLE = Path("/app/deploy/hetzner/ansible")
TEMPLATE = ANSIBLE / "templates/nginx-purepeptide.conf.j2"
ERROR_PAGE = ANSIBLE / "files/error-pages/_not-live.html"
ROOT = Path("/tmp/pp_geoblock_test")
PORT = 8477
pytestmark = pytest.mark.skipif(not shutil.which("nginx"), reason="nginx is not installed")


def _free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


@pytest.fixture(scope="module")
def site():
    for sub in ("build", "error-pages", "ssl", "body", "proxy", "f", "u", "s"):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)
    (ROOT / "build/index.html").write_text("<h1>PurePeptide store</h1>")
    shutil.copy(ERROR_PAGE, ROOT / "error-pages/_not-live.html")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(ROOT / "ssl/key.pem"), "-out", str(ROOT / "ssl/cert.pem"),
                    "-days", "2", "-subj", "/CN=purepeptide.bg"], check=True, capture_output=True)

    rendered = jinja2.Template(TEMPLATE.read_text(), undefined=jinja2.StrictUndefined).render(
        app_name="purepeptide", web_root=str(ROOT), backend_private_ip="127.0.0.1",
        frontend_private_ip="127.0.0.1", nginx_http2_directive="listen",
        site_domains=["purepeptide.bg"], site_tls_certs={}, blocked_countries=["US", "CA"],
        ssl_cert_path=str(ROOT / "ssl/cert.pem"), ssl_key_path=str(ROOT / "ssl/key.pem"),
        groups={f"{ROOT}/ssl/cert.pem|{ROOT}/ssl/key.pem": ["purepeptide.bg"]})
    body = (rendered.replace("listen 443 ssl http2;", f"listen {PORT} ssl;")
            .replace("listen [::]:443 ssl http2;", "").replace("listen 80;", f"listen {PORT + 1};")
            .replace("listen [::]:80;", "").replace("listen 127.0.0.1:8080;", "listen 127.0.0.1:8479;"))
    conf = ROOT / "nginx.conf"
    conf.write_text(f"""worker_processes 1;
error_log {ROOT}/err.log warn;
pid {ROOT}/nginx.pid;
events {{ worker_connections 64; }}
http {{
  access_log off;
  client_body_temp_path {ROOT}/body; proxy_temp_path {ROOT}/proxy;
  fastcgi_temp_path {ROOT}/f; uwsgi_temp_path {ROOT}/u; scgi_temp_path {ROOT}/s;
  proxy_cache_path {ROOT}/cache keys_zone=pp_media:5m;
{body}
}}
""")
    check = subprocess.run(["nginx", "-t", "-c", str(conf), "-p", str(ROOT)], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert _free(PORT), f"port {PORT} is busy"
    subprocess.run(["nginx", "-c", str(conf), "-p", str(ROOT)], check=True)
    time.sleep(1)
    yield f"https://127.0.0.1:{PORT}"
    subprocess.run(["nginx", "-s", "stop", "-c", str(conf), "-p", str(ROOT)], capture_output=True)
    shutil.rmtree(ROOT, ignore_errors=True)


def fetch(site, path="/", country="BG", ua="Mozilla/5.0"):
    return requests.get(f"{site}{path}", verify=False, timeout=15, headers={
        "Host": "purepeptide.bg", "CF-IPCountry": country, "User-Agent": ua})


@pytest.mark.parametrize("country", ["US", "CA"])
@pytest.mark.parametrize("path", ["/", "/products/ghk-cu", "/api/nextcart/config"])
def test_a_blocked_country_sees_an_unconfigured_domain(site, country, path):
    r = fetch(site, path, country)
    assert r.status_code == 403
    assert "This domain is not configured" in r.text
    assert "PurePeptide" not in r.text          # not a hint that a shop lives here
    assert r.headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize("country", ["BG", "GR", "DE", "RO", "GB", ""])
def test_the_markets_we_serve_are_untouched(site, country):
    assert fetch(site, "/", country).status_code == 200


@pytest.mark.parametrize("ua", [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.1; +https://openai.com/gptbot)",
    "facebookexternalhit/1.1",
])
def test_the_crawlers_are_never_blocked(site, ua):
    """They all crawl from US addresses — blocking them would end the indexing."""
    r = fetch(site, "/", "US", ua)
    assert r.status_code == 200
    assert "PurePeptide" in r.text


def test_the_nextlevel_integration_endpoint_is_not_geoblocked():
    conf = TEMPLATE.read_text()
    wp = conf[conf.index("location ^~ /wp-json/"):]
    assert "$pp_block" not in wp[:wp.index("}")]


def test_the_blocked_list_is_a_deploy_variable():
    example = (ANSIBLE / "group_vars/all.yml.example").read_text()
    assert "blocked_countries: []" in example
    assert "blocked_countries | default([])" in TEMPLATE.read_text()


def test_nobody_is_blocked_by_default():
    """The US/CA block is off (20.06.2026) — an empty list must render a map without countries."""
    rendered = jinja2.Template(TEMPLATE.read_text(), undefined=jinja2.StrictUndefined).render(
        app_name="purepeptide", web_root="/tmp/x", backend_private_ip="127.0.0.1",
        frontend_private_ip="127.0.0.1", nginx_http2_directive="listen",
        site_domains=["purepeptide.bg"], site_tls_certs={},
        ssl_cert_path="/tmp/c.pem", ssl_key_path="/tmp/k.pem")
    geo = rendered[rendered.index("map $http_cf_ipcountry"):]
    geo = geo[:geo.index("}")]
    assert "default   0;" in geo
    for country in ("US", "CA"):
        assert f"    {country} " not in geo


def test_the_error_page_gives_nothing_away():
    html = ERROR_PAGE.read_text()
    for word in ("PurePeptide", "peptide", "blocked", "country", "США", "US"):
        assert word not in html
    assert "noindex" in html
