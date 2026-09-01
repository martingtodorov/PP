"""Iteration 14: Test URL alignment with live purepeptide.bg, sitemap, agents.md, link-index."""
import os
import urllib.parse
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Collections URL alignment ----------
class TestCollectionsAlignment:
    def test_collections_list_contains_new_handles(self):
        r = requests.get(f"{API}/collections", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # data may be list or dict
        items = data if isinstance(data, list) else data.get("items", data.get("collections", []))
        handles = [c.get("handle") for c in items]
        assert "2all-the-peptides-1" in handles, f"missing new all-peptides handle. got={handles}"
        assert "all-peptides" not in handles, f"legacy handle should not be in list. got={handles}"
        assert "retatrutide-price" in handles, f"missing retatrutide-price. got={handles}"

    def test_get_new_all_peptides_collection(self):
        r = requests.get(f"{API}/collections/2all-the-peptides-1", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        products = body.get("products") or body.get("items") or []
        assert len(products) > 0, f"expected products in 2all-the-peptides-1: {body}"

    def test_legacy_all_peptides_alias(self):
        r = requests.get(f"{API}/collections/all-peptides", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        products = body.get("products") or body.get("items") or []
        assert len(products) > 0

    def test_retatrutide_collection(self):
        r = requests.get(f"{API}/collections/retatrutide-price", timeout=30)
        assert r.status_code == 200, r.text


# ---------- Pages with new slugs ----------
NEW_PAGE_SLUGS = [
    "contact-1",
    "about-1",
    "become-a-distributor",
    "terms-conditions",
    "delivery-and-payment",
    "какво-са-пептиди",
]
OLD_PAGE_SLUGS = ["contacts", "about", "partners", "terms-of-service", "shipping-policy", "what-are-peptides"]


class TestPageSlugs:
    @pytest.mark.parametrize("slug", NEW_PAGE_SLUGS)
    def test_new_slug_returns_200(self, slug):
        encoded = urllib.parse.quote(slug, safe="-")
        r = requests.get(f"{API}/pages/{encoded}", timeout=30)
        assert r.status_code == 200, f"{slug} -> {r.status_code} {r.text[:200]}"
        data = r.json()
        page = data.get("page") or data
        body_field = page.get("html") or page.get("body_html") or page.get("content") or page.get("body") or ""
        assert len(body_field) > 0, f"empty body for {slug}"

    @pytest.mark.parametrize("slug", OLD_PAGE_SLUGS)
    def test_old_slug_404(self, slug):
        r = requests.get(f"{API}/pages/{slug}", timeout=30)
        assert r.status_code == 404, f"old slug {slug} still resolves: {r.status_code}"


# ---------- link-index ----------
class TestLinkIndex:
    def test_link_index_structure(self):
        r = requests.get(f"{API}/link-index", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("collections", "products", "articles", "pages"):
            assert key in data, f"missing {key} in link-index"
            assert isinstance(data[key], list)
            assert len(data[key]) > 0
            first = data[key][0]
            handle_key = "handle" if "handle" in first else "slug"
            assert "title" in first and handle_key in first, f"{key} item missing title/handle: {first}"
        # counts (approximate expected)
        print(
            "link-index counts:",
            {k: len(data[k]) for k in ("collections", "products", "articles", "pages")},
        )


# ---------- SEO endpoints ----------
class TestSEO:
    def test_sitemap_xml(self):
        r = requests.get(f"{API}/sitemap.xml", timeout=30)
        assert r.status_code == 200, r.text
        body = r.text
        assert "/collections/2all-the-peptides-1" in body
        assert "/pages/contact-1" in body
        assert "/pages/html-sitemap" in body
        # xml validity - starts with <?xml
        assert body.lstrip().startswith("<?xml")

    def test_agentic_sitemap(self):
        r = requests.get(f"{API}/sitemap_agentic_discovery.xml", timeout=30)
        assert r.status_code == 200, r.text
        assert r.text.lstrip().startswith("<?xml")

    def test_agents_md(self):
        r = requests.get(f"{API}/agents.md", timeout=30)
        assert r.status_code == 200, r.text
        # Should be markdown listing entry points and products
        assert len(r.text) > 100

    def test_robots_txt(self):
        r = requests.get(f"{API}/robots.txt", timeout=30)
        assert r.status_code == 200, r.text
        body = r.text
        assert "sitemap.xml" in body.lower()
        assert "sitemap_agentic_discovery.xml" in body.lower()
        assert "agents.md" in body.lower()


# ---------- Delisted / redirects cleanup ----------
class TestDelistedLinks:
    def test_no_matrixify_redirects(self):
        # try admin token first
        s = requests.Session()
        login = s.post(
            f"{API}/auth/login",
            json={"email": "admin@purepeptide.bg", "password": "Admin@PurePeptide2026"},
            timeout=30,
        )
        headers = {}
        if login.status_code == 200:
            try:
                token = login.json().get("access_token") or login.json().get("token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
            except Exception:
                pass
        r = s.get(f"{API}/admin/delisted-links", headers=headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        matrixify = [i for i in items if (i.get("created_by") == "matrixify-import")]
        assert len(matrixify) == 0, f"still have {len(matrixify)} matrixify redirects"
