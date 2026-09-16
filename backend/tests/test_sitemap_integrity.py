"""Sitemaps and robots.txt: only live URLs, only this host, one file per language.

Everything is asserted against the running backend with the production Host header, because the
bugs were all host-dependent: purepeptide.ro served 652 Bulgarian URLs and then crashed with
KeyError('ro'), and purepeptide.eu put 176 URLs of eight languages into one unreadable file.
"""
import re
import xml.etree.ElementTree as ET

import requests
from conftest import run  # noqa: F401

API = "http://localhost:8001/api"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SINGLE = {"purepeptide.bg": "bg", "purepeptide.gr": "gr", "purepeptide.ro": "ro"}
EU_LOCALES = ["en", "fr", "de", "cz", "hu", "pl", "sk", "si"]


def get(path, host):
    return requests.get(f"{API}{path}", headers={"Host": host}, timeout=60)


def locs(xml_text):
    root = ET.fromstring(xml_text)
    return [e.text.strip() for e in root.findall(".//s:loc", NS)]


def test_every_sitemap_is_valid_xml_and_lists_only_its_own_host():
    for host in list(SINGLE) + ["purepeptide.eu"]:
        idx = get("/sitemap.xml", host)
        assert idx.status_code == 200, host
        children = locs(idx.text)
        assert children, host
        for child in children:
            assert child.startswith(f"https://{host}/"), f"{host} -> {child}"
            r = get("/" + child.split("/")[-1], host)
            assert r.status_code == 200, f"{child} -> {r.status_code}"
            urls = locs(r.text)
            assert urls, f"{child} is empty"
            for u in urls:
                assert u.startswith(f"https://{host}/"), f"{child} -> {u}"


def test_a_single_language_domain_keeps_the_plain_child_names():
    for host in SINGLE:
        children = [c.rsplit("/", 1)[-1] for c in locs(get("/sitemap.xml", host).text)]
        assert children == ["sitemap_agentic_discovery.xml", "sitemap_products_1.xml",
                            "sitemap_collections_1.xml", "sitemap_pages_1.xml",
                            "sitemap_blogs_1.xml"], host


def test_the_eight_language_domain_gets_one_file_per_language():
    children = [c.rsplit("/", 1)[-1] for c in locs(get("/sitemap.xml", "purepeptide.eu").text)]
    assert len(children) == 1 + 4 * len(EU_LOCALES)
    for kind in ("products", "collections", "pages", "blogs"):
        for loc in EU_LOCALES:
            assert f"sitemap_{kind}_{loc}_1.xml" in children
    for loc in EU_LOCALES:
        urls = locs(get(f"/sitemap_products_{loc}_1.xml", "purepeptide.eu").text)
        assert urls
        for u in urls:
            assert u.startswith(f"https://purepeptide.eu/{loc}/"), u


def test_the_romanian_domain_serves_its_own_pages():
    """It answered 200 on production while the market is switched off for selling: the sitemap used
    to fall back to every locale (652 Bulgarian URLs) and the children crashed with KeyError."""
    urls = locs(get("/sitemap_products_1.xml", "purepeptide.ro").text)
    assert len(urls) > 5
    assert all(u.startswith("https://purepeptide.ro/") for u in urls)
    assert not any("/en/" in u or "/pages/%D0" in u for u in urls)


def test_robots_advertises_only_this_hosts_sitemaps():
    for host in list(SINGLE) + ["purepeptide.eu"]:
        body = requests.get(f"{API}/robots.txt", headers={"Host": host}, timeout=30).text
        sitemaps = re.findall(r"^Sitemap: (.+)$", body, re.M)
        assert sitemaps, host
        for sm in sitemaps:
            assert sm.startswith(f"https://{host}/"), f"{host} -> {sm}"
            assert "/api/" not in sm, sm
        assert f"{host}/agents.md" in body and f"{host}/llms.txt" in body


def test_the_stale_static_robots_file_is_gone():
    """The file in the bundle won the `try_files` and advertised all four domains' /api/sitemap.xml —
    Search Console then reported a cross-host sitemap it could not read on every domain."""
    from pathlib import Path

    assert not (Path("/app/frontend/public/robots.txt")).exists()
    conf = Path("/app/deploy/hetzner/ansible/templates/nginx-purepeptide.conf.j2").read_text()
    assert "proxy_pass http://{{ backend_private_ip }}:8001/api/robots.txt;" in conf
    assert "location = /robots.txt   { try_files $uri @backend; }" not in conf


def test_the_canonical_matches_the_sitemap_character_for_character():
    """The Cyrillic page slug was percent-encoded in the sitemap and raw in the canonical — the
    same page in two spellings."""
    urls = locs(get("/sitemap_pages_1.xml", "purepeptide.bg").text)
    cyrillic = [u for u in urls if "%D0" in u]
    assert cyrillic, "no percent-encoded page in the sitemap"
    for u in cyrillic[:3]:
        path = u.replace("https://purepeptide.bg", "")
        html = requests.get(f"{API}/seo/prerender", params={"path": path},
                            headers={"Host": "purepeptide.bg"}, timeout=40).text
        assert re.findall(r'rel="canonical" href="([^"]+)"', html)[0] == u


def test_a_rotated_or_delisted_url_is_in_no_sitemap():
    import matrixify_import as mi

    rotated = mi.db.collections_cat.find_one({"rotations.0": {"$exists": True}},
                                             {"_id": 0, "rotations": 1, "handle": 1})
    assert rotated, "no rotated collection in the database"
    dead = {r["from"] for r in rotated["rotations"]} - {rotated["handle"]}
    body = get("/sitemap_collections_1.xml", "purepeptide.bg").text
    for handle in dead:
        assert f"/collections/{handle}<" not in body, handle
    delisted = mi.db.collections_cat.find_one({"delisted": True}, {"_id": 0, "handle": 1})
    if delisted:
        assert f"/collections/{delisted['handle']}<" not in body


SHAPE = re.compile(
    r"<url>\n"
    r"    <loc>(?P<loc>[^<]+)</loc>\n"
    r"    <lastmod>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00</lastmod>\n"
    r"    <changefreq>daily</changefreq>\n"
    r"    <image:image>\n"
    r"      <image:loc>[^<]+</image:loc>\n"
    r"      <image:title>[^<]*</image:title>\n"
    r"      <image:caption>[^<]*</image:caption>\n"
    r"    </image:image>\n"
    r"  </url>")


def test_a_rotated_url_keeps_the_shopify_shape():
    """Rotating a link changes the <loc> and nothing else: same indentation, same lastmod /
    changefreq / image block — the file still reads like the Shopify export."""
    import server

    handle = "zz-sitemap-rotation"
    products = server.db.products

    async def rewrite(html, locale, context=""):
        return html.replace("Молекулата", "Пептидът")

    original = server.ai_rewrite_html
    server.ai_rewrite_html = rewrite
    try:
        run(products.delete_many({"handle": {"$regex": f"^{handle}"}}))
        run(products.insert_one({
            "id": "zz-sitemap-rotation-1", "handle": handle, "title": "ZZ Sitemap тест 5mg",
            "description": "<h1>Какво е ZZ?</h1><p>Молекулата е изследвана в лабораторни модели "
                           "за ефекти върху възстановяването и метаболизма.</p>",
            "images": ["/api/files/import/zz-test.png"], "active": True,
            "variants": [{"name": "5mg", "price_eur": 10.0, "stock": 1, "sku": "ZZ-SITEMAP"}]}))
        before = get("/sitemap_products_1.xml", "purepeptide.bg").text
        entry = [m.group(0) for m in SHAPE.finditer(before) if handle in m.group("loc")]
        assert entry, "the fresh product is not in the sitemap in the expected shape"

        res = run(server.rotate_content("products", handle, "bg", "t@t.bg"))
        new_handle = res["handle"]
        assert new_handle != handle

        after = get("/sitemap_products_1.xml", "purepeptide.bg").text
        rotated = [m.group(0) for m in SHAPE.finditer(after) if new_handle in m.group("loc")]
        assert rotated, "the rotated product lost the Shopify shape"
        assert rotated[0].replace(new_handle, handle) == entry[0].replace(
            re.search(r"<lastmod>[^<]+", entry[0]).group(0),
            re.search(r"<lastmod>[^<]+", rotated[0]).group(0))
        assert f"/products/{handle}<" not in after      # the retired handle is gone
    finally:
        server.ai_rewrite_html = original
        run(products.delete_many({"id": "zz-sitemap-rotation-1"}))
        run(server.db.delisted_links.delete_many({"url": {"$regex": handle}}))
        run(server.db.rotation_log.delete_many({"handle": {"$regex": f"^{handle}"}}))
