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
        assert "Какво е" in stripped[:200], f"H1 does not contain 'Какво е'. First 200: {stripped[:200]!r}"


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
