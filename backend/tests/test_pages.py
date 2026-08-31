"""Static editable pages (per locale) - public + admin CRUD + AI translate.

Covers the review_request for iteration_8:
- GET /api/pages/{slug}?locale=... (locale returned + source_locale fallback)
- Unknown slug -> 404
- Admin auth guards on /api/admin/pages*
- GET /api/admin/pages returns 9 slugs with filled map
- GET /api/admin/pages/{slug}/{locale} returns empty scaffold when missing
- PUT upserts, public GET reflects immediately
- PUT unknown slug -> 404
- POST /api/admin/pages/{slug}/translate (paid Anthropic call) — runs EXACTLY ONCE
  for slug=contacts, locales=[de], overwrite=True, then cleans up so the storefront
  keeps its EN fallback for the other locales.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"
CUSTOMER_EMAIL = "customer@example.com"
CUSTOMER_PASSWORD = "Customer123!"

SLUGS = [
    "what-are-peptides", "faq", "contacts", "chemical-analysis", "partners",
    "privacy-policy", "refund-policy", "terms-of-service", "shipping-policy",
]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def customer_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    if r.status_code != 200:
        pytest.skip("customer login not available")
    return s


# ---------------- Public ----------------
class TestPublicPages:
    def test_bg_faq(self):
        r = requests.get(f"{API}/pages/faq", params={"locale": "bg"})
        assert r.status_code == 200, r.text
        p = r.json()["page"]
        assert p["slug"] == "faq"
        assert p["locale"] == "bg"
        assert p["source_locale"] == "bg"
        # Bulgarian FAQ has 4 seeded items with Cyrillic q
        assert len(p["faq_items"]) >= 3
        assert any(re.search(r"[А-Яа-я]", it["q"]) for it in p["faq_items"])

    def test_bg_what_are_peptides(self):
        r = requests.get(f"{API}/pages/what-are-peptides", params={"locale": "bg"})
        assert r.status_code == 200
        p = r.json()["page"]
        assert p["title"]
        assert p["source_locale"] == "bg"
        assert re.search(r"[А-Яа-я]", p["html"])

    @pytest.mark.parametrize("slug", SLUGS)
    def test_all_slugs_return_content(self, slug):
        r = requests.get(f"{API}/pages/{slug}", params={"locale": "bg"})
        assert r.status_code == 200, f"{slug} -> {r.status_code} {r.text}"
        p = r.json()["page"]
        # Every seeded slug should have title in BG
        assert p["title"], f"{slug} has empty title"

    def test_de_falls_back_to_en(self):
        # No German content seeded for what-are-peptides -> should fall back to EN
        r = requests.get(f"{API}/pages/what-are-peptides", params={"locale": "de"})
        assert r.status_code == 200
        p = r.json()["page"]
        assert p["locale"] == "de"
        assert p["source_locale"] == "en", f"expected en fallback, got {p['source_locale']!r}"
        assert p["title"].lower().startswith("what")

    def test_unknown_slug_404(self):
        r = requests.get(f"{API}/pages/does-not-exist-xyz", params={"locale": "bg"})
        assert r.status_code == 404


# ---------------- Admin auth guards ----------------
class TestAdminGuards:
    def test_list_unauth(self):
        assert requests.get(f"{API}/admin/pages").status_code == 401

    def test_get_unauth(self):
        assert requests.get(f"{API}/admin/pages/contacts/en").status_code == 401

    def test_put_unauth(self):
        assert requests.put(f"{API}/admin/pages/contacts/en", json={"title": "x", "html": "y", "faq_items": []}).status_code == 401

    def test_translate_unauth(self):
        assert requests.post(f"{API}/admin/pages/contacts/translate", json={"locales": ["de"]}).status_code == 401

    def test_customer_forbidden(self, customer_session):
        assert customer_session.get(f"{API}/admin/pages").status_code == 403


# ---------------- Admin list ----------------
class TestAdminList:
    def test_slug_list_has_nine(self, admin_session):
        r = admin_session.get(f"{API}/admin/pages")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["slugs"]) == 9
        got = {s["slug"] for s in body["slugs"]}
        assert set(SLUGS) == got
        # labels + filled map present
        for entry in body["slugs"]:
            assert entry["label"]
            assert isinstance(entry["filled"], dict)
            # bg should be filled for every seeded slug
            assert entry["filled"].get("bg") is True, f"{entry['slug']} bg not filled"
        # locales list
        assert "locales" in body
        assert "bg" in body["locales"] and "en" in body["locales"]


# ---------------- Admin get scaffold ----------------
class TestAdminGet:
    def test_empty_scaffold_for_missing_locale(self, admin_session):
        # what-are-peptides has no fr seed -> empty scaffold
        r = admin_session.get(f"{API}/admin/pages/what-are-peptides/fr")
        assert r.status_code == 200
        p = r.json()["page"]
        assert p["slug"] == "what-are-peptides"
        assert p["locale"] == "fr"
        assert p["title"] == "" and p["html"] == "" and p["faq_items"] == []

    def test_unknown_slug_get_404(self, admin_session):
        r = admin_session.get(f"{API}/admin/pages/nope-slug/en")
        assert r.status_code == 404

    def test_bg_seeded(self, admin_session):
        r = admin_session.get(f"{API}/admin/pages/contacts/bg")
        assert r.status_code == 200
        assert r.json()["page"]["title"]


# ---------------- Admin PUT + public reflects ----------------
class TestAdminPut:
    def test_put_unknown_slug_404(self, admin_session):
        r = admin_session.put(f"{API}/admin/pages/nope-slug/en", json={"title": "x", "html": "y", "faq_items": []})
        assert r.status_code == 404

    def test_upsert_and_public_reflects_then_reset(self, admin_session):
        slug, loc = "contacts", "pl"
        marker_title = "TEST Kontakt PL"
        marker_html = "<p>TEST PL content 12345</p>"
        # baseline: fetch current (to restore later)
        cur = admin_session.get(f"{API}/admin/pages/{slug}/{loc}").json()["page"]

        # Upsert
        r = admin_session.put(f"{API}/admin/pages/{slug}/{loc}", json={
            "title": marker_title, "html": marker_html, "faq_items": [],
        })
        assert r.status_code == 200, r.text
        p = r.json()["page"]
        assert p["title"] == marker_title
        assert p["html"] == marker_html

        # Public immediately reflects
        pub = requests.get(f"{API}/pages/{slug}", params={"locale": loc}).json()["page"]
        assert pub["title"] == marker_title
        assert pub["source_locale"] == loc
        assert marker_html in pub["html"]

        # Reset: since baseline was empty scaffold, delete via mongo cli — but we can't.
        # Best-effort: put empty content back so public falls back to en.
        admin_session.put(f"{API}/admin/pages/{slug}/{loc}", json={
            "title": cur.get("title", ""), "html": cur.get("html", ""), "faq_items": cur.get("faq_items", []),
        })
        # Verify fallback works again if baseline was empty
        if not (cur.get("title") or cur.get("html") or cur.get("faq_items")):
            pub2 = requests.get(f"{API}/pages/{slug}", params={"locale": loc}).json()["page"]
            assert pub2["source_locale"] in ("en", "bg"), f"expected fallback, got {pub2['source_locale']}"

    def test_faq_upsert_reorder(self, admin_session):
        slug, loc = "faq", "sk"
        cur = admin_session.get(f"{API}/admin/pages/{slug}/{loc}").json()["page"]
        items = [
            {"q": "TEST Q1", "a": "A1"},
            {"q": "TEST Q2", "a": "A2"},
            {"q": "TEST Q3", "a": "A3"},
        ]
        r = admin_session.put(f"{API}/admin/pages/{slug}/{loc}", json={
            "title": "TEST FAQ SK", "html": "", "faq_items": items,
        })
        assert r.status_code == 200
        pub = requests.get(f"{API}/pages/{slug}", params={"locale": loc}).json()["page"]
        assert [i["q"] for i in pub["faq_items"]] == ["TEST Q1", "TEST Q2", "TEST Q3"]

        # Reorder (swap 1&3)
        reordered = [items[2], items[1], items[0]]
        admin_session.put(f"{API}/admin/pages/{slug}/{loc}", json={
            "title": "TEST FAQ SK", "html": "", "faq_items": reordered,
        })
        pub2 = requests.get(f"{API}/pages/{slug}", params={"locale": loc}).json()["page"]
        assert [i["q"] for i in pub2["faq_items"]] == ["TEST Q3", "TEST Q2", "TEST Q1"]

        # Reset to baseline (empty scaffold likely) so storefront falls back to en/bg
        admin_session.put(f"{API}/admin/pages/{slug}/{loc}", json={
            "title": cur.get("title", ""), "html": cur.get("html", ""), "faq_items": cur.get("faq_items", []),
        })


# ---------------- AI translate (RUNS ONCE) ----------------
class TestAITranslateOnce:
    """Calls the paid Anthropic endpoint EXACTLY ONCE for slug=contacts, locales=[de]."""

    def test_translate_contacts_de(self, admin_session):
        slug = "contacts"
        # Snapshot the current de content so we can restore afterwards
        cur_de = admin_session.get(f"{API}/admin/pages/{slug}/de").json()["page"]

        r = admin_session.post(f"{API}/admin/pages/{slug}/translate", json={
            "locales": ["de"], "overwrite": True,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "de" in body.get("translated", []), body

        pub = requests.get(f"{API}/pages/{slug}", params={"locale": "de"}).json()["page"]
        assert pub["source_locale"] == "de", f"expected source_locale de, got {pub['source_locale']}"
        assert pub["title"], "empty title after translation"
        # No Cyrillic leakage
        assert not re.search(r"[А-Яа-я]", pub["title"] + pub["html"])
        # Must look German-ish: contains at least one common German letter/word or non-empty html
        assert pub["html"].strip(), "html body should not be empty"

        # Restore prior de content (whether empty scaffold or real content) so
        # storefront returns to EN/BG fallback per the reviewer's clean-up ask.
        admin_session.put(f"{API}/admin/pages/{slug}/de", json={
            "title": cur_de.get("title", ""),
            "html": cur_de.get("html", ""),
            "faq_items": cur_de.get("faq_items", []),
        })
