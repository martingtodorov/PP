"""The nginx template must produce exactly one crawlable URL per page.

Renders the real Ansible template, starts nginx with it (TLS stripped, so no Cloudflare Origin
certificates are needed) and checks the redirects the owner asked for:
  purepeptide.eu/            -> 301 /en/
  purepeptide.eu/products/x  -> 301 /en/products/x
  purepeptide.eu/cz          -> 301 /cz/
and nothing else moves: /en/... , /api/... , assets, robots.txt, and the single-language domains.
"""
import http.client
import os
import pathlib
import re
import shutil
import signal
import subprocess
import tempfile
import time

import pytest
from jinja2 import Template

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO / "deploy/hetzner/ansible/templates/nginx-purepeptide.conf.j2"
PORT = 8099
VARS = {
    "app_name": "purepeptide",
    "site_domains": ["purepeptide.bg", "purepeptide-labs.bg", "purepeptide.eu",
                     "purepeptide.ro", "purepeptide.gr"],
    "web_root": "",                      # filled in with the temp root
    "backend_private_ip": "127.0.0.1",   # the real local FastAPI, so proxied routes answer
    "frontend_private_ip": "127.0.0.1",
    "ssl_cert_path": "/dev/null",
    "ssl_key_path": "/dev/null",
    "nginx_http2_directive": "listen",
    "site_tls_certs": {},
}


def _plain_http(conf: str) -> str:
    """Same server blocks, served over plain HTTP on a test port instead of TLS."""
    conf = conf.replace("listen 443 ssl http2;", f"listen 127.0.0.1:{PORT};")
    conf = re.sub(r"^\s*listen \[::\]:443 ssl http2;\n", "", conf, flags=re.M)
    conf = re.sub(r"^\s*(ssl_certificate|ssl_certificate_key|ssl_protocols|"
                  r"ssl_prefer_server_ciphers|ssl_session_cache|ssl_session_timeout).*\n", "",
                  conf, flags=re.M)
    conf = re.sub(r"^\s*listen 80;\n\s*listen \[::\]:80;\n", "", conf, flags=re.M)
    # the port-80 redirect block would clash with the test port, and the private shell block binds
    # an address that does not exist here
    conf = conf.replace("listen 127.0.0.1:8080;", "listen 127.0.0.1:8098;")
    return conf


@pytest.fixture(scope="module")
def nginx():
    if not shutil.which("nginx"):
        pytest.skip("nginx is not installed in this environment")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pp-nginx-"))
    (tmp / "build/static").mkdir(parents=True)
    (tmp / "build/index.html").write_text("<html lang=\"bg\"><body><div id=\"root\"></div></body></html>")
    (tmp / "build/robots.txt").write_text("User-agent: *\n")
    (tmp / "logs").mkdir()
    body = Template(TEMPLATE.read_text(encoding="utf-8")).render(**{**VARS, "web_root": str(tmp)})
    conf = ("worker_processes 1;\nerror_log %s/logs/error.log;\npid %s/nginx.pid;\n"
            "events { worker_connections 64; }\nhttp {\n"
            "  access_log off;\n  client_body_temp_path %s/logs;\n  proxy_temp_path %s/logs/proxy;\n"
            "  fastcgi_temp_path %s/logs/fcgi;\n  uwsgi_temp_path %s/logs/uwsgi;\n"
            "  scgi_temp_path %s/logs/scgi;\n  include /etc/nginx/mime.types;\n%s\n}\n"
            % (tmp, tmp, tmp, tmp, tmp, tmp, tmp, _plain_http(body)))
    (tmp / "nginx.conf").write_text(conf)
    check = subprocess.run(["nginx", "-t", "-c", str(tmp / "nginx.conf"), "-p", str(tmp)],
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    proc = subprocess.Popen(["nginx", "-c", str(tmp / "nginx.conf"), "-p", str(tmp),
                             "-g", "daemon off;"])
    time.sleep(1.5)
    yield
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)
    shutil.rmtree(tmp, ignore_errors=True)


def get(host: str, path: str):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15)
    conn.request("GET", path, headers={"Host": host})
    r = conn.getresponse()
    body = r.read().decode("utf-8", "replace")
    conn.close()
    return r.status, r.getheader("Location"), body


@pytest.mark.parametrize("path,expected", [
    ("/", "https://purepeptide.eu/en/"),
    ("/products/sermorelin", "https://purepeptide.eu/en/products/sermorelin"),
    ("/collections/immunity", "https://purepeptide.eu/en/collections/immunity"),
    ("/cart", "https://purepeptide.eu/en/cart"),
])
def test_the_shared_domain_sends_unprefixed_pages_to_english(nginx, path, expected):
    status, location, _ = get("purepeptide.eu", path)
    assert (status, location) == (301, expected)


@pytest.mark.parametrize("prefix", ["en", "fr", "de", "cz", "hu", "pl", "sk", "si"])
def test_a_locale_root_gets_its_trailing_slash(nginx, prefix):
    status, location, _ = get("purepeptide.eu", f"/{prefix}")
    assert (status, location) == (301, f"https://purepeptide.eu/{prefix}/")


@pytest.mark.parametrize("path", ["/en/", "/en/products/sermorelin", "/cz/", "/api/products",
                                  "/robots.txt", "/static/js/main.js", "/admin/login"])
def test_already_canonical_urls_are_not_redirected(nginx, path):
    status, location, _ = get("purepeptide.eu", path)
    assert status != 301, f"{path} unexpectedly redirected to {location}"


@pytest.mark.parametrize("host", ["purepeptide.bg", "purepeptide.ro", "purepeptide.gr",
                                  "purepeptide-labs.bg"])
def test_single_language_domains_keep_their_root(nginx, host):
    status, location, _ = get(host, "/")
    assert status != 301, f"{host}/ unexpectedly redirected to {location}"
    status, _, _ = get(host, "/products/sermorelin")
    assert status != 301


@pytest.mark.parametrize("host,path,expected", [
    ("purepeptide.bg", "/pages/homepage", "https://purepeptide.bg/"),
    ("purepeptide.eu", "/pages/homepage", "https://purepeptide.eu/en/"),
    ("purepeptide.eu", "/cz/pages/homepage", "https://purepeptide.eu/cz/"),
])
def test_the_page_only_the_old_shopify_theme_had_is_redirected(nginx, host, path, expected):
    status, location, _ = get(host, path)
    assert (status, location) == (301, expected)


@pytest.mark.parametrize("path", ["/pages/html-sitemap", "/pages/html-sitemap-products",
                                  "/pages/html-sitemap-collections", "/pages/html-sitemap-blogs",
                                  "/pages/html-sitemap-pages"])
def test_the_html_sitemap_pages_are_served_not_redirected(nginx, path):
    """They live in the router, so the prerender has to answer them itself."""
    status, location, body = get("purepeptide.bg", path)
    assert status == 200, location
    assert "HTML sitemap" in body and "<li><a" in body


@pytest.mark.parametrize("host,path,lang", [
    ("purepeptide.bg", "/", "bg"),
    ("purepeptide.eu", "/en/", "en"),
    ("purepeptide.eu", "/cz/", "cs"),
    ("purepeptide.eu", "/si/", "sl"),
    ("purepeptide.eu", "/de/", "de"),
    ("purepeptide.ro", "/", "ro"),
    ("purepeptide.gr", "/", "el"),
])
def test_every_storefront_states_its_own_language(nginx, host, path, lang):
    """Through the real nginx + prerender chain, not just the module in isolation."""
    status, _, body = get(host, path)
    assert status == 200, (host, path, status)
    assert f'<html lang="{lang}"' in body, body[:200]
    # exactly one lang attribute on <html>
    assert len(re.findall(r'<html[^>]*\slang="', body)) == 1


# ---------------- iteration 49 extensions ----------------

# extra redirects on the shared .eu domain (owner's SEO report)
@pytest.mark.parametrize("path,expected", [
    ("/articles/what-is-sermorelin", "https://purepeptide.eu/en/articles/what-is-sermorelin"),
    ("/pages/faq", "https://purepeptide.eu/en/pages/faq"),
    ("/checkout", "https://purepeptide.eu/en/checkout"),
    ("/track", "https://purepeptide.eu/en/track"),
])
def test_more_unprefixed_pages_go_to_english(nginx, path, expected):
    status, location, _ = get("purepeptide.eu", path)
    assert (status, location) == (301, expected)


# these paths must NEVER redirect on the shared .eu domain (assets/API/admin/single-file routes)
@pytest.mark.parametrize("path", [
    "/wp-json/wc/v3/products",
    "/sitemap.xml",
    "/llms.txt",
    "/logo.png",
    "/hero.jpg",
    "/admin",
    "/admin/",
])
def test_reserved_paths_on_shared_domain_never_redirect(nginx, path):
    status, location, _ = get("purepeptide.eu", path)
    assert status != 301, f"{path} unexpectedly redirected to {location}"


# no redirect chains: the .eu -> /en/... target must land on 200 or 404 in ONE hop
@pytest.mark.parametrize("start,expected", [
    ("/", "/en/"),
    ("/products/sermorelin", "/en/products/sermorelin"),
    ("/cz", "/cz/"),
])
def test_no_redirect_loops_or_chains(nginx, start, expected):
    status, location, _ = get("purepeptide.eu", start)
    assert status == 301
    assert location.endswith(expected)
    # second hop must not be a redirect
    target_path = location.split("purepeptide.eu", 1)[1]
    status2, location2, _ = get("purepeptide.eu", target_path)
    assert status2 in (200, 404), (target_path, status2, location2)
    assert location2 is None or not location2.startswith("http")


# canonical regression: prerender's canonical of a locale root equals its own URL
@pytest.mark.parametrize("host,path,canonical", [
    ("purepeptide.eu", "/en/", "https://purepeptide.eu/en/"),
    ("purepeptide.eu", "/cz/", "https://purepeptide.eu/cz/"),
    ("purepeptide.bg", "/", "https://purepeptide.bg/"),
    ("purepeptide.ro", "/", "https://purepeptide.ro/"),
])
def test_canonical_matches_destination(nginx, host, path, canonical):
    status, _, body = get(host, path)
    assert status == 200, (host, path, status)
    assert f'<link rel="canonical" href="{canonical}"' in body, body[:400]


# a private route (/en/cart) is served with the shell but lang must still match locale
def test_private_route_lang_is_locale(nginx):
    status, _, body = get("purepeptide.eu", "/en/cart")
    assert status == 200
    assert '<html lang="en"' in body
