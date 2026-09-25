"""Iteration 60 — contextual links, dead-link report, readable NextLevel errors.

Covers the acceptance criteria the main agent listed as "not yet verified":
- auth rejection of /api/admin/link-audit
- duplicate-job guard (POST while running returns the running job)
- article body / prerender contain live product links (both relative and absolute)
- article page returns 200 for the linked product handle
- readable NextLevel errors (400 on /nextlevel/test, 502 NextLevelError handler wiring,
  preview does not crash, fulfillment/refresh readable message)
- regression: /admin/delisted-links list works, page <title> has no ' - PurePeptide' suffix,
  /api/articles list + article page still render, rotation-301 toggle still flips.
"""
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (iteration60-tests)"}


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update(UA)
    email = os.environ.get("ADMIN_EMAIL")
    pwd = os.environ.get("ADMIN_PASSWORD")
    if not email or not pwd:
        # read from backend/.env directly
        try:
            for line in open("/app/backend/.env"):
                if line.startswith("ADMIN_EMAIL="):
                    email = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("ADMIN_PASSWORD="):
                    pwd = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
    if not email or not pwd:
        pytest.skip("admin credentials not available")
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    s = requests.Session()
    s.headers.update(UA)
    return s


# ---------------- Autolink / contextual links ----------------
class TestAutolink:
    def test_article_body_has_product_links(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/articles/demo-article?locale=bg")
        assert r.status_code == 200
        body = r.json()["article"]["body"]
        # relative hrefs in the API body
        assert '/products/demo-sample-a' in body
        assert '/products/demo-sample-b' in body

    def test_prerender_has_absolute_product_links(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/seo/prerender?path=/articles/demo-article")
        assert r.status_code == 200
        html = r.text
        assert 'https://purepeptide.bg/products/demo-sample-a' in html
        assert 'https://purepeptide.bg/products/demo-sample-b' in html

    def test_linked_product_page_returns_200(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/products/demo-sample-a?locale=bg")
        assert r.status_code == 200
        r2 = anon_session.get(f"{BASE_URL}/api/products/demo-sample-b?locale=bg")
        assert r2.status_code == 200

    def test_autolink_unit_no_break_of_hyphenated_word_and_skip_headings(self):
        """Direct autolink.apply() coverage of the hard constraints."""
        import sys
        sys.path.insert(0, "/app/backend")
        import autolink
        html = (
            "<h1>BPC-157 stays in the heading</h1>"
            "<p>Първо: BPC-157 се появява тук.</p>"
            "<p>Second BPC-157 mention should not link.</p>"
            '<p>Inside <a href="/x">BPC-157</a> already linked.</p>'
        )
        out = autolink.apply(html, [("BPC-157", "/products/bpc-157")])
        # heading must remain unchanged
        assert "<h1>BPC-157 stays in the heading</h1>" in out
        # existing anchor untouched (no nested <a>)
        assert '<a href="/x">BPC-157</a>' in out
        # BPC-157 was linked once in the first plain paragraph
        anchors = re.findall(r'<a href="/products/bpc-157">BPC-157</a>', out)
        assert len(anchors) == 1
        # never split the hyphenated word
        assert "BPC-157" in out
        assert not re.search(r'BPC(?!-)<', out)

    def test_autolink_respects_limit(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import autolink
        pairs = [(f"Product{i}", f"/products/p{i}") for i in range(10)]
        html = "<p>" + " ".join(f"Product{i}" for i in range(10)) + "</p>"
        out = autolink.apply(html, pairs, limit=6)
        anchors = re.findall(r'<a href="/products/', out)
        assert len(anchors) == 6


# ---------------- link-audit auth + duplicate-job guard ----------------
class TestLinkAudit:
    def test_get_requires_auth(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/admin/link-audit")
        assert r.status_code in (401, 403), f"expected auth reject, got {r.status_code}"

    def test_post_requires_auth(self, anon_session):
        r = anon_session.post(f"{BASE_URL}/api/admin/link-audit",
                              json={"locale": "bg", "limit": 5})
        assert r.status_code in (401, 403), f"expected auth reject, got {r.status_code}"

    def test_get_returns_latest_job(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/link-audit")
        assert r.status_code == 200
        data = r.json()
        assert "job" in data
        # if a job has ever run, verify shape
        job = data["job"]
        if job:
            assert "status" in job
            assert "crawled" in job
            assert "broken" in job
            assert isinstance(job["broken"], list)

    def test_duplicate_job_guard(self, admin_session):
        # start a small job
        r1 = admin_session.post(f"{BASE_URL}/api/admin/link-audit",
                                json={"locale": "bg", "limit": 20})
        assert r1.status_code == 200
        job1 = r1.json()["job"]
        assert job1["status"] == "running"
        job1_id = job1["id"]

        # immediately post again — must return running job with the message
        r2 = admin_session.post(f"{BASE_URL}/api/admin/link-audit",
                                json={"locale": "bg", "limit": 20})
        assert r2.status_code == 200
        body2 = r2.json()
        # either message is present or same running job id returned
        job2 = body2.get("job")
        assert job2 is not None
        if body2.get("message"):
            assert "Вече" in body2["message"] or "проверка" in body2["message"]
            assert job2["id"] == job1_id
        else:
            # even without message, must be the same running id, not a new one
            assert job2["id"] == job1_id

    def test_audit_job_eventually_finishes(self, admin_session):
        # poll up to 60s for a done/failed status
        deadline = time.time() + 90
        last = None
        while time.time() < deadline:
            r = admin_session.get(f"{BASE_URL}/api/admin/link-audit")
            job = r.json().get("job")
            if job:
                last = job
                if job["status"] in ("done", "failed", "stopped"):
                    break
            time.sleep(3)
        assert last is not None
        assert last["status"] in ("done", "failed", "stopped"), f"job status={last.get('status')}"
        # shape of broken[]
        for b in last.get("broken") or []:
            assert set(b.keys()) >= {"path", "status", "found_on"}


# ---------------- NextLevel readable errors ----------------
class TestNextLevelErrors:
    def test_nextlevel_test_returns_readable_400(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/integrations/nextlevel/test", json={})
        # with no keys configured, must be 400 with Bulgarian text — NOT 500
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "app-id" in detail or "app-secret" in detail or "липсват" in detail

    def test_nextlevel_error_handler_registered(self):
        """Code-level check: NextLevelError -> 502 handler is wired in server.py."""
        import sys
        sys.path.insert(0, "/app/backend")
        import nextlevel
        assert hasattr(nextlevel, "NextLevelError")
        # read server.py source to confirm registration
        src = open("/app/backend/server.py").read()
        assert "add_exception_handler(nextlevel.NextLevelError" in src
        # confirm the handler returns 502
        assert "status_code=502" in src

    def test_fulfillment_refresh_readable_error_on_missing_order(self, admin_session):
        bogus = str(uuid.uuid4())
        r = admin_session.post(f"{BASE_URL}/api/admin/orders/{bogus}/fulfillment/refresh")
        assert r.status_code in (400, 404), f"expected 400/404, got {r.status_code} {r.text[:200]}"
        assert r.status_code != 500

    def test_nextlevel_preview_does_not_crash(self, admin_session):
        # find any order id
        r = admin_session.get(f"{BASE_URL}/api/admin/orders?limit=1")
        if r.status_code != 200:
            pytest.skip(f"cannot list orders: {r.status_code}")
        orders = r.json().get("orders") or r.json().get("items") or []
        if not orders:
            pytest.skip("no orders available for preview test")
        oid = orders[0].get("id") or orders[0].get("_id")
        r2 = admin_session.get(f"{BASE_URL}/api/admin/integrations/nextlevel/preview/{oid}")
        # must NOT be 500 — either 200 with ok:false, or 4xx
        assert r2.status_code != 500, f"preview crashed 500: {r2.text[:200]}"
        if r2.status_code == 200:
            body = r2.json()
            assert "ok" in body
            if body["ok"] is False:
                assert "error" in body


# ---------------- Regression ----------------
class TestRegression:
    def test_delisted_links_list(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/delisted-links")
        assert r.status_code == 200
        data = r.json()
        assert "links" in data or isinstance(data, list)

    def test_articles_list(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/articles?locale=bg")
        assert r.status_code == 200
        assert "articles" in r.json() or isinstance(r.json(), list)

    def test_article_title_has_no_purepeptide_suffix(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/seo/prerender?path=/articles/demo-article")
        assert r.status_code == 200
        m = re.search(r"<title>([^<]+)</title>", r.text)
        assert m, "no <title> in prerender"
        title = m.group(1)
        assert " - PurePeptide" not in title, f"unexpected suffix in title: {title}"

    def test_rotation_policy_toggle(self, admin_session):
        # read current setting
        r = admin_session.get(f"{BASE_URL}/api/admin/rotation-policy")
        assert r.status_code == 200
        cur = r.json()
        enabled = bool(cur.get("enabled"))
        # flip
        r2 = admin_session.put(f"{BASE_URL}/api/admin/rotation-policy",
                               json={"enabled": not enabled})
        assert r2.status_code in (200, 204)
        assert r2.json().get("enabled") is (not enabled)
        # restore
        admin_session.put(f"{BASE_URL}/api/admin/rotation-policy", json={"enabled": enabled})
