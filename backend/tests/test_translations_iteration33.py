"""
Iteration 33: Test bulk translation queue admin endpoints,
product H1/H2 heading rules on public API, collection titles.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://shopify-migrate-3.preview.emergentagent.com').rstrip('/')

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    }, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"no token in login response: {data}"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


class TestBulkTranslateAdmin:
    def test_bulk_status_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/admin/translate/bulk", timeout=15)
        assert r.status_code == 401, f"expected 401 got {r.status_code}"

    def test_bulk_history_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/admin/translate/bulk/history", timeout=15)
        assert r.status_code == 401

    def test_bulk_status_authenticated(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/translate/bulk", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should have a job field or job-like fields
        job = data.get("job") if isinstance(data, dict) and "job" in data else data
        assert job is not None, f"no job in response: {data}"
        # Job may be null if none ever ran, but request says one is running
        if job:
            for key in ("status", "done", "total"):
                assert key in job, f"missing key {key} in job: {job}"
            assert "completed" not in job, "'completed' array must NOT be in response"
            # status should be running or finished
            assert job["status"] in ("running", "finished", "queued", "stopped", "failed"), \
                f"unexpected status: {job['status']}"

    def test_bulk_history_authenticated(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/translate/bulk/history", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "jobs" in data, f"missing 'jobs': {data}"
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) <= 10


class TestProductHeadings:
    def test_retatrutide_description_starts_with_h1(self):
        r = requests.get(f"{BASE_URL}/api/products/21-retatrutide-5", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        prod = data.get("product", data)
        desc = prod.get("description") or prod.get("body_html") or ""
        assert desc.lstrip().startswith("<h1>Какво е Ретатрутид?</h1>"), \
            f"description does not start with expected H1. First 200 chars: {desc[:200]!r}"

    def test_bpc157_description_has_h1(self):
        r = requests.get(f"{BASE_URL}/api/products/bpc-157-5", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        prod = data.get("product", data)
        desc = prod.get("description") or prod.get("body_html") or ""
        stripped = desc.lstrip()
        assert stripped.startswith("<h1>"), f"description does not start with <h1>. First 200: {stripped[:200]!r}"
        # BPC-157 uses 'Какво представлява' instead of 'Какво е'
        assert ("Какво е" in stripped[:200]) or ("Какво представлява" in stripped[:200]), \
            f"H1 does not contain expected phrase. First 200: {stripped[:200]!r}"


class TestCollectionsPublic:
    def test_all_peptides_collection(self):
        r = requests.get(f"{BASE_URL}/api/collections/2all-the-peptides-1", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Just check exists — the visible title is a frontend concern
        assert data is not None

    def test_metabolic_studies_collection(self):
        r = requests.get(f"{BASE_URL}/api/collections/metabolic-studies", timeout=15)
        assert r.status_code == 200, r.text

    def test_collections_list_count_and_h1(self):
        r = requests.get(f"{BASE_URL}/api/collections", timeout=20)
        assert r.status_code == 200
        data = r.json()
        cols = data.get("collections", data) if isinstance(data, dict) else data
        assert isinstance(cols, list)
        assert len(cols) == 8, f"expected 8 collections, got {len(cols)}"
        for c in cols:
            desc = (c.get("description") or c.get("body_html") or "").lstrip()
            assert desc.startswith("<h1>"), f"collection {c.get('handle')} desc does not start with <h1>: {desc[:120]!r}"


class TestProductsList:
    def test_products_count_and_h1_backfill(self):
        r = requests.get(f"{BASE_URL}/api/products?limit=100", timeout=30)
        assert r.status_code == 200
        data = r.json()
        prods = data.get("products", data) if isinstance(data, dict) else data
        assert isinstance(prods, list)
        assert len(prods) == 23, f"expected 23 products, got {len(prods)}"
        # List endpoint doesn't include description; hit detail for each handle
        h1_count = 0
        missing = []
        for p in prods:
            handle = p.get("handle")
            if not handle:
                continue
            dr = requests.get(f"{BASE_URL}/api/products/{handle}", timeout=15)
            if dr.status_code != 200:
                missing.append((handle, dr.status_code))
                continue
            pd = dr.json()
            pd = pd.get("product", pd)
            desc = (pd.get("description") or pd.get("body_html") or "").lstrip()
            if desc.startswith("<h1>"):
                h1_count += 1
            else:
                missing.append((handle, desc[:80]))
        assert h1_count >= 22, f"expected >=22 products with <h1>, got {h1_count}. Missing: {missing[:5]}"


class TestBulkTranslateStop:
    def test_stop_unauthenticated(self):
        r = requests.post(f"{BASE_URL}/api/admin/translate/bulk/stop", timeout=15)
        assert r.status_code == 401

    def test_stop_when_idle(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/translate/bulk/stop", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "stopped" in data, f"missing 'stopped' key: {data}"
        # When nothing running, stopped should be 0
        assert data["stopped"] == 0, f"expected stopped=0 when idle, got {data}"


class TestBulkTranslateFinishedShape:
    def test_bulk_finished_no_completed_field(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/translate/bulk", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        job = data.get("job") if isinstance(data, dict) and "job" in data else data
        if job and job.get("status") == "finished":
            assert job.get("done") == 64, f"expected done=64, got {job.get('done')}"
            assert job.get("total") == 64, f"expected total=64, got {job.get('total')}"
            assert job.get("failed") == [] or job.get("failed") is None
            assert "completed" not in job
            assert "completed" not in data

    def test_history_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/translate/bulk/history", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        jobs = data["jobs"]
        for j in jobs:
            assert "completed" not in j, f"job history item must not contain 'completed': {j}"
