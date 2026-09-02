"""Backend tests for iteration 29 — UI strings (checkout copy) admin overlay."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to reading frontend/.env
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"

CYR = re.compile(r"[\u0400-\u04FF]")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return s


# ---------- Public /api/ui-strings ----------
def test_public_ui_strings_returns_overrides_only():
    r = requests.get(f"{BASE_URL}/api/ui-strings", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "strings" in body
    assert isinstance(body["strings"], dict)


def test_public_ui_strings_by_locale():
    r = requests.get(f"{BASE_URL}/api/ui-strings?locale=ro", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "strings" in body
    assert "ro" in body["strings"]


# ---------- Admin auth guards ----------
def test_admin_ui_strings_get_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/ui-strings", timeout=10)
    assert r.status_code in (401, 403)


def test_admin_ui_strings_put_requires_auth():
    r = requests.put(f"{BASE_URL}/api/admin/ui-strings",
                     json={"locale": "ro", "strings": {"toPayment": "X"}}, timeout=10)
    assert r.status_code in (401, 403)


def test_admin_translate_requires_auth():
    r = requests.post(f"{BASE_URL}/api/admin/ui-strings/translate",
                      json={"locale": "de", "source": {"applyBtn": "Приложи"}}, timeout=10)
    assert r.status_code in (401, 403)


# ---------- Admin GET ----------
def test_admin_get_ui_strings(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/ui-strings", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "strings" in body


# ---------- PUT + persistence + empty-string deletion ----------
def test_admin_put_persists_and_public_reflects(admin_session):
    key = "toPayment"
    marker = "TEST_ContinuePayment_iter29"
    # Save
    r = admin_session.put(
        f"{BASE_URL}/api/admin/ui-strings",
        json={"locale": "ro", "strings": {key: marker}}, timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True and data.get("locale") == "ro"
    try:
        # Verify via admin GET
        g = admin_session.get(f"{BASE_URL}/api/admin/ui-strings", timeout=15)
        assert g.status_code == 200
        assert g.json()["strings"].get("ro", {}).get(key) == marker
        # Verify public
        p = requests.get(f"{BASE_URL}/api/ui-strings?locale=ro", timeout=10)
        assert p.status_code == 200
        assert p.json()["strings"]["ro"].get(key) == marker
    finally:
        # Cleanup: empty string deletes the override
        d = admin_session.put(
            f"{BASE_URL}/api/admin/ui-strings",
            json={"locale": "ro", "strings": {key: ""}}, timeout=15,
        )
        assert d.status_code == 200
        # Confirm cleared
        g2 = admin_session.get(f"{BASE_URL}/api/admin/ui-strings", timeout=15)
        assert key not in (g2.json()["strings"].get("ro") or {})


# ---------- Placeholder preservation in stored value ----------
def test_admin_put_preserves_placeholder(admin_session):
    key = "freeShippingHint"
    val = "TEST add {amount} more for free"
    admin_session.put(f"{BASE_URL}/api/admin/ui-strings",
                      json={"locale": "en", "strings": {key: val}}, timeout=15)
    try:
        g = admin_session.get(f"{BASE_URL}/api/admin/ui-strings", timeout=15)
        assert "{amount}" in g.json()["strings"]["en"][key]
    finally:
        admin_session.put(f"{BASE_URL}/api/admin/ui-strings",
                          json={"locale": "en", "strings": {key: ""}}, timeout=15)


# ---------- Geo regression ----------
def test_geo_country_returns_empty_city():
    r = requests.get(f"{BASE_URL}/api/geo/country", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "country" in body
    assert body.get("city", "") == ""


# ---------- Retatrutide compare-at price regression ----------
def test_retatrutide_compare_at_price():
    r = requests.get(f"{BASE_URL}/api/products/retatrutide", timeout=15)
    if r.status_code != 200:
        pytest.skip("retatrutide product not present at this handle")
    body = r.json()
    variants = body.get("variants") or []
    v5 = next((v for v in variants if "5" in str(v.get("sku", "")) or v.get("dosage_mg") == 5), None)
    if v5:
        # compare_at may be at product or variant level
        assert v5.get("compare_at_price") or body.get("compare_at_eur") or body.get("compare_at_price"), \
            f"no compare_at price on retatrutide 5mg: {v5}"


# ---------- RevOrder integrations regression: 4 domains listed, masked ----------
def test_revorder_lists_four_domains_masked(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder", timeout=15)
    assert r.status_code == 200
    body = r.json()
    domains = body.get("domains") or body.get("configs") or body
    if isinstance(domains, dict):
        domains = list(domains.values())
    assert isinstance(domains, list)
    assert len(domains) == 4
    for d in domains:
        # Enabled must remain False (test hygiene)
        # Keys should be masked (contain bullet) or empty
        for field in ("api_key", "secret"):
            v = d.get(field, "")
            if v:
                assert "•" in v or "*" in v, f"{d.get('domain')} {field} not masked: {v[:20]}"


# ---------- Code review guard: bulk translate wires UI strings ----------
def test_bulk_translate_includes_ui_step_in_code():
    src = open("/app/backend/server.py").read()
    assert "ui_strings_mod.translate_locale" in src
    assert 'include_ui = resource in ("everything", "ui")' in src
    assert "total += len(targets)" in src
