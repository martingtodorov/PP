"""Iteration 30 — media/repair endpoint, admin blog editor, draft hiding, variant images.

Covers:
* POST /api/admin/media/repair (dry_run + real, idempotency, auth)
* GET /api/admin/articles + PATCH /api/admin/articles/{handle} (auth, partial, 404)
* Drafts hidden from public /api/articles, /api/link-index, /api/sitemap.xml
* Publish toggle round-trip
* Retatrutide compare_at regression (49/59)
* Variant image + compare_at persistence via PUT /api/admin/products/{id}
* matrixify_import.store_image ?v= normalization (unit-level assertion via importing the module)
"""
import os
import re
import sys
import time
from pathlib import Path

import pytest
import requests

# ---------- config ----------
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"
RETA_PRODUCT = "21-retatrutide-5"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return s


# =========================================================================
# 1. Auth guards on new endpoints
# =========================================================================
class TestAuthGuards:
    def test_admin_articles_get_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/articles", timeout=10)
        assert r.status_code in (401, 403)

    def test_admin_article_patch_requires_auth(self):
        r = requests.patch(f"{BASE_URL}/api/admin/articles/some-handle",
                           json={"title": "x"}, timeout=10)
        assert r.status_code in (401, 403)

    def test_media_repair_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/admin/media/repair", timeout=15)
        assert r.status_code in (401, 403)


# =========================================================================
# 2. Public articles: drafts hidden
# =========================================================================
class TestDraftsHidden:
    def test_public_articles_excludes_drafts(self, admin_session):
        pub = requests.get(f"{BASE_URL}/api/articles", timeout=15).json()
        pub_arts = pub.get("articles", pub)
        adm = admin_session.get(f"{BASE_URL}/api/admin/articles", timeout=15).json()
        adm_arts = adm["articles"]
        assert len(adm_arts) > len(pub_arts), (
            f"admin={len(adm_arts)} public={len(pub_arts)} — drafts should be hidden"
        )
        # Every public article must be published (not published=false)
        for a in pub_arts:
            assert a.get("published") is not False, f"{a['handle']} is a draft in /api/articles"
        # And at least one admin article is a draft (published=false)
        drafts = [a for a in adm_arts if a.get("published") is False]
        assert drafts, "expected at least one draft in admin list"

    def test_sitemap_excludes_drafts(self, admin_session):
        xml = requests.get(f"{BASE_URL}/api/sitemap.xml", timeout=15).text
        adm = admin_session.get(f"{BASE_URL}/api/admin/articles", timeout=15).json()
        drafts = [a["handle"] for a in adm["articles"] if a.get("published") is False]
        for h in drafts:
            assert f"/articles/{h}" not in xml, f"draft {h} leaked into sitemap"

    def test_link_index_excludes_drafts(self, admin_session):
        idx = requests.get(f"{BASE_URL}/api/link-index", timeout=15).json()
        adm = admin_session.get(f"{BASE_URL}/api/admin/articles", timeout=15).json()
        drafts = {a["handle"] for a in adm["articles"] if a.get("published") is False}
        # link-index shape: articles list containing urls/handles
        blob = str(idx)
        for h in drafts:
            assert f"/articles/{h}" not in blob, f"draft {h} leaked into link-index"


# =========================================================================
# 3. Admin articles PATCH: partial write + 404
# =========================================================================
class TestAdminArticlePatch:
    def test_patch_404_for_unknown_handle(self, admin_session):
        r = admin_session.patch(
            f"{BASE_URL}/api/admin/articles/definitely-not-a-real-handle-xyz",
            json={"excerpt": "x"}, timeout=15,
        )
        assert r.status_code == 404

    def test_partial_patch_only_writes_sent_fields(self, admin_session):
        adm = admin_session.get(f"{BASE_URL}/api/admin/articles", timeout=15).json()
        art = adm["articles"][0]
        handle = art["handle"]
        original_title = art.get("title", "")
        original_image = art.get("image", "")
        original_excerpt = art.get("excerpt", "")
        marker = f"TEST_EDIT_{int(time.time())}"
        try:
            r = admin_session.patch(
                f"{BASE_URL}/api/admin/articles/{handle}",
                json={"excerpt": marker}, timeout=15,
            )
            assert r.status_code == 200, r.text
            updated = r.json()["article"]
            assert updated["excerpt"] == marker
            # title/image untouched
            assert updated.get("title", "") == original_title
            assert updated.get("image", "") == original_image
        finally:
            # restore
            admin_session.patch(
                f"{BASE_URL}/api/admin/articles/{handle}",
                json={"excerpt": original_excerpt}, timeout=15,
            )

    def test_publish_toggle_round_trip(self, admin_session):
        adm = admin_session.get(f"{BASE_URL}/api/admin/articles", timeout=15).json()
        drafts = [a for a in adm["articles"] if a.get("published") is False]
        if not drafts:
            pytest.skip("no drafts in DB to toggle")
        handle = drafts[0]["handle"]
        try:
            # publish
            r = admin_session.patch(
                f"{BASE_URL}/api/admin/articles/{handle}",
                json={"published": True}, timeout=15,
            )
            assert r.status_code == 200
            # appears immediately on public /api/articles
            pub = requests.get(f"{BASE_URL}/api/articles", timeout=15).json()
            handles = {a["handle"] for a in pub.get("articles", pub)}
            assert handle in handles, "published article did not surface on public API"
        finally:
            # restore draft state
            admin_session.patch(
                f"{BASE_URL}/api/admin/articles/{handle}",
                json={"published": False}, timeout=15,
            )
            # confirm hidden again
            pub = requests.get(f"{BASE_URL}/api/articles", timeout=15).json()
            handles = {a["handle"] for a in pub.get("articles", pub)}
            assert handle not in handles


# =========================================================================
# 4. Media repair: break a product image, repair, verify + idempotent
# =========================================================================
class TestMediaRepair:
    """Reproduces the bogus-hash 404 pattern and verifies the repair heals it."""

    _BOGUS_PREFIX = "aaaabbbbcccc"  # deliberately invalid 12-hex prefix

    def _get_prod(self, s, handle):
        r = s.get(f"{BASE_URL}/api/admin/products", timeout=15)
        for p in r.json().get("products", []):
            if p["handle"] == handle:
                return p
        pytest.skip(f"product {handle} not found")

    def _put_prod(self, s, prod):
        # PUT expects the ProductIn shape — strip non-writable fields
        payload = {k: v for k, v in prod.items()
                   if k not in ("id", "created_at", "updated_at", "base_handle", "handles")}
        r = s.put(f"{BASE_URL}/api/admin/products/{prod['id']}",
                  json=payload, timeout=20)
        assert r.status_code == 200, r.text

    def test_repair_heals_broken_product_and_article_images(self, admin_session):
        s = admin_session

        # --- STEP 1: pick a product with real /api/files/import/... image and break it ---
        prod = self._get_prod(s, RETA_PRODUCT)
        orig_prod = {"image": prod.get("image", ""), "images": list(prod.get("images", []))}
        m = re.search(r"/api/files/import/([0-9a-f]+)-", orig_prod["image"])
        if not m:
            pytest.skip(f"product {RETA_PRODUCT} has no import/<hash>-... image; got {orig_prod['image']!r}")

        def break_ref(url):
            return re.sub(r"/api/files/import/[0-9a-f]+-",
                          f"/api/files/import/{self._BOGUS_PREFIX}-", url) if url else url

        broken_main = break_ref(orig_prod["image"])
        broken_gallery = [break_ref(u) for u in orig_prod["images"]]
        # sanity: the broken URL should actually 404
        broken_check = requests.get(f"{BASE_URL}{broken_main}", timeout=15, allow_redirects=False)
        assert broken_check.status_code in (404, 500), (
            f"broken URL {broken_main} unexpectedly returned {broken_check.status_code}"
        )

        # apply the breakage
        prod["image"] = broken_main
        prod["images"] = broken_gallery
        self._put_prod(s, prod)

        # --- STEP 2: also break an article image if we have a public one ---
        adm = s.get(f"{BASE_URL}/api/admin/articles", timeout=15).json()
        art_target = None
        for a in adm["articles"]:
            if (a.get("image") or "").startswith("/api/files/import/"):
                art_target = a
                break
        orig_art_image = art_target.get("image", "") if art_target else ""
        if art_target:
            broken_art = break_ref(orig_art_image)
            r = s.patch(f"{BASE_URL}/api/admin/articles/{art_target['handle']}",
                        json={"image": broken_art}, timeout=15)
            assert r.status_code == 200

        try:
            # --- STEP 3: dry_run — verify report says fixes but DB unchanged ---
            r = s.post(f"{BASE_URL}/api/admin/media/repair?dry_run=true", timeout=120)
            assert r.status_code == 200, r.text
            dry = r.json()
            assert dry["dry_run"] is True
            assert dry["fixed"] >= 1, f"dry_run should report >=1 fix, got {dry}"
            # DB still broken — re-fetch product
            still = self._get_prod(s, RETA_PRODUCT)
            assert still["image"] == broken_main, "dry_run must not persist changes"

            # --- STEP 4: real run — heals ---
            r = s.post(f"{BASE_URL}/api/admin/media/repair", timeout=180)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["fixed"] >= 1, f"expected fixed>0, got {body}"
            assert body["unresolved"] == [], f"unresolved refs remain: {body['unresolved']}"

            # --- STEP 5: fetched product now points at a readable image ---
            healed = self._get_prod(s, RETA_PRODUCT)
            assert healed["image"] != broken_main, "product image was not repaired"
            img_resp = requests.get(f"{BASE_URL}{healed['image']}", timeout=20)
            assert img_resp.status_code == 200, f"repaired image not readable: {img_resp.status_code}"
            assert img_resp.headers.get("Content-Type", "").startswith("image/"), img_resp.headers

            # --- STEP 6: second run is a no-op ---
            r = s.post(f"{BASE_URL}/api/admin/media/repair", timeout=120)
            assert r.status_code == 200
            body2 = r.json()
            assert body2["fixed"] == 0, f"second run should be no-op, got fixed={body2['fixed']}"
            assert body2["unresolved"] == []
        finally:
            # restore article if we edited it (image may now be healed — write orig back)
            if art_target:
                s.patch(f"{BASE_URL}/api/admin/articles/{art_target['handle']}",
                        json={"image": orig_art_image}, timeout=15)


# =========================================================================
# 5. Variant image + compare_at persistence
# =========================================================================
class TestVariantImageAndCompareAt:
    def test_retatrutide_compare_at_regression(self):
        r = requests.get(f"{BASE_URL}/api/products/{RETA_PRODUCT}", timeout=15)
        assert r.status_code == 200
        p = r.json().get("product", r.json())
        v0 = p["variants"][0]
        assert v0.get("price_eur") == 49.0, f"expected 49 EUR, got {v0.get('price_eur')}"
        assert v0.get("compare_at_eur") == 59.0, f"expected 59 EUR, got {v0.get('compare_at_eur')}"

    def test_put_persists_variant_image_and_compare_at(self, admin_session):
        s = admin_session
        r = s.get(f"{BASE_URL}/api/admin/products", timeout=15)
        prod = next((p for p in r.json()["products"] if p["handle"] == RETA_PRODUCT), None)
        assert prod, "retatrutide product missing"

        # snapshot originals
        original = {
            "variants": [dict(v) for v in prod["variants"]],
        }
        try:
            # pin variant[1].image to variant[0]'s or product image, set compare_at
            pin = prod["variants"][0].get("image") or prod.get("image") or (prod.get("images") or [None])[0]
            assert pin, "no image available to pin"
            new_variants = [dict(v) for v in prod["variants"]]
            new_variants[1]["image"] = pin
            new_variants[1]["compare_at_eur"] = 111.0
            payload = {k: v for k, v in prod.items()
                       if k not in ("id", "created_at", "updated_at", "base_handle", "handles")}
            payload["variants"] = new_variants
            r = s.put(f"{BASE_URL}/api/admin/products/{prod['id']}", json=payload, timeout=20)
            assert r.status_code == 200, r.text

            # GET public product — verify persistence
            pub = requests.get(f"{BASE_URL}/api/products/{RETA_PRODUCT}", timeout=15).json()
            p2 = pub.get("product", pub)
            assert p2["variants"][1].get("image") == pin, p2["variants"][1]
            assert p2["variants"][1].get("compare_at_eur") == 111.0, p2["variants"][1]
        finally:
            # restore
            payload = {k: v for k, v in prod.items()
                       if k not in ("id", "created_at", "updated_at", "base_handle", "handles")}
            payload["variants"] = original["variants"]
            s.put(f"{BASE_URL}/api/admin/products/{prod['id']}", json=payload, timeout=20)


# =========================================================================
# 6. matrixify_import.store_image ?v= normalization (code-level assertion)
# =========================================================================
class TestImageMapNormalization:
    def test_urls_with_and_without_v_query_yield_same_path(self):
        """Static assertion by reading the source: the hash input strips ?query."""
        import hashlib
        src = Path("/app/backend/matrixify_import.py").read_text()
        assert 'norm = url.split("?")[0]' in src
        assert 'hashlib.sha1(norm.encode())' in src, "hash should be over the query-stripped URL"
        assert 'db.image_map.update_one' in src and '"key": norm' in src, (
            "image_map should be keyed on the query-stripped URL"
        )
        # simulate: two URLs differing only in ?v= produce the same path suffix
        u1 = "https://cdn.shopify.com/s/files/1/x/foo.png?v=111"
        u2 = "https://cdn.shopify.com/s/files/1/x/foo.png?v=222"
        n1 = u1.split("?")[0]
        n2 = u2.split("?")[0]
        assert hashlib.sha1(n1.encode()).hexdigest()[:12] == hashlib.sha1(n2.encode()).hexdigest()[:12]
