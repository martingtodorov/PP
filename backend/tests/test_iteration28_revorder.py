"""Iteration 28 — RevOrder admin integrations backend contract."""
import hmac
import hashlib
import json
import os
import re
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"
DOMAINS = ["purepeptide.bg", "purepeptide.eu", "purepeptide.ro", "purepeptide.gr"]
TEST_DOMAIN = "purepeptide.eu"  # use .eu for round-trip; leave .bg untouched per request


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# ---------- security ----------
class TestAuthGuards:
    def test_list_requires_admin(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/admin/integrations/revorder")
        assert r.status_code in (401, 403)

    def test_generate_requires_admin(self, anon_session):
        r = anon_session.post(f"{BASE_URL}/api/admin/integrations/revorder/generate",
                              json={"domain": "purepeptide.eu"})
        assert r.status_code in (401, 403)

    def test_reveal_requires_admin(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/admin/integrations/revorder/reveal",
                             params={"domain": "purepeptide.eu"})
        assert r.status_code in (401, 403)

    def test_put_requires_admin(self, anon_session):
        r = anon_session.put(f"{BASE_URL}/api/admin/integrations/revorder",
                             json={"domain": "purepeptide.eu"})
        assert r.status_code in (401, 403)

    def test_test_requires_admin(self, anon_session):
        r = anon_session.post(f"{BASE_URL}/api/admin/integrations/revorder/test",
                              json={"domain": "purepeptide.eu"})
        assert r.status_code in (401, 403)


# ---------- list / defaults / masking ----------
class TestListAndDefaults:
    def test_list_returns_all_four_domains_with_defaults(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder")
        assert r.status_code == 200
        data = r.json()
        assert set(DOMAINS).issubset(set(data["domains"].keys()))
        for d in DOMAINS:
            cfg = data["domains"][d]
            # Default fields
            assert cfg["api_base"] == "https://api.nextcartmanager.com"
            assert cfg["orders_path"] == "/api/orders"
            assert cfg["webhook_url"].endswith(f"/api/webhooks/revorder/{d}")
            assert "has_keys" in cfg
            # keys must be masked or empty
            if cfg["has_keys"]:
                assert "•" in cfg["api_key"], f"api_key not masked for {d}: {cfg['api_key']}"
                assert "•" in cfg["secret_key"], f"secret_key not masked for {d}"
        assert isinstance(data.get("events"), list)


# ---------- generate + reveal + regenerate ----------
class TestGenerateAndReveal:
    def test_generate_returns_unmasked_pair(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/integrations/revorder/generate",
                               json={"domain": TEST_DOMAIN})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["api_key"].startswith("pp_live_")
        assert re.fullmatch(r"[0-9a-f]{64}", data["secret_key"]), data["secret_key"]
        assert data["webhook_url"].endswith(f"/api/webhooks/revorder/{TEST_DOMAIN}")

    def test_regenerate_produces_different_values(self, admin_session):
        r1 = admin_session.post(f"{BASE_URL}/api/admin/integrations/revorder/generate",
                                json={"domain": TEST_DOMAIN}).json()
        r2 = admin_session.post(f"{BASE_URL}/api/admin/integrations/revorder/generate",
                                json={"domain": TEST_DOMAIN}).json()
        assert r1["api_key"] != r2["api_key"]
        assert r1["secret_key"] != r2["secret_key"]

    def test_list_never_returns_unmasked_after_generate(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder").json()
        cfg = r["domains"][TEST_DOMAIN]
        assert cfg["has_keys"] is True
        assert "•" in cfg["api_key"]
        assert "•" in cfg["secret_key"]
        # must not accidentally leak
        assert "pp_live_" not in cfg["api_key"] or cfg["api_key"].count("•") > 0

    def test_reveal_returns_full_keys(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder/reveal",
                              params={"domain": TEST_DOMAIN})
        assert r.status_code == 200
        data = r.json()
        assert data["api_key"].startswith("pp_live_")
        assert re.fullmatch(r"[0-9a-f]{64}", data["secret_key"])

    def test_reveal_404_for_unknown_domain(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder/reveal",
                              params={"domain": "not-a-real-domain.xyz"})
        assert r.status_code == 404


# ---------- PUT persistence ----------
class TestPutPersistence:
    def test_edit_api_base_and_orders_path_persists(self, admin_session):
        # Save custom values (keeping disabled)
        r = admin_session.put(f"{BASE_URL}/api/admin/integrations/revorder", json={
            "domain": TEST_DOMAIN,
            "api_base": "https://api.nextcartmanager.com",
            "orders_path": "/api/orders/custom-test",
            "enabled": False,
        })
        assert r.status_code == 200
        # Verify via list
        listing = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder").json()
        cfg = listing["domains"][TEST_DOMAIN]
        assert cfg["orders_path"] == "/api/orders/custom-test"
        assert cfg["enabled"] is False
        # restore
        admin_session.put(f"{BASE_URL}/api/admin/integrations/revorder", json={
            "domain": TEST_DOMAIN, "api_base": "https://api.nextcartmanager.com",
            "orders_path": "/api/orders", "enabled": False,
        })

    def test_put_masked_key_does_not_overwrite(self, admin_session):
        before = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder/reveal",
                                   params={"domain": TEST_DOMAIN}).json()
        # Send the masked value back — must NOT overwrite
        listing = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder").json()
        masked = listing["domains"][TEST_DOMAIN]["api_key"]
        assert "•" in masked
        admin_session.put(f"{BASE_URL}/api/admin/integrations/revorder", json={
            "domain": TEST_DOMAIN, "api_key": masked, "secret_key": "",
            "api_base": "https://api.nextcartmanager.com", "orders_path": "/api/orders",
            "enabled": False,
        })
        after = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder/reveal",
                                  params={"domain": TEST_DOMAIN}).json()
        assert after["api_key"] == before["api_key"]
        assert after["secret_key"] == before["secret_key"]


# ---------- inbound webhook ----------
def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestInboundWebhook:
    @pytest.fixture(scope="class")
    def enabled_domain_creds(self, admin_session):
        # Enable TEST_DOMAIN, capture the current secret, then always disable at teardown.
        creds = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder/reveal",
                                  params={"domain": TEST_DOMAIN}).json()
        admin_session.put(f"{BASE_URL}/api/admin/integrations/revorder", json={
            "domain": TEST_DOMAIN, "api_base": "https://api.nextcartmanager.com",
            "orders_path": "/api/orders", "enabled": True,
        })
        yield creds
        # Teardown — MUST disable so no real order push happens
        admin_session.put(f"{BASE_URL}/api/admin/integrations/revorder", json={
            "domain": TEST_DOMAIN, "api_base": "https://api.nextcartmanager.com",
            "orders_path": "/api/orders", "enabled": False,
        })

    def test_bad_signature_401(self, enabled_domain_creds):
        body = json.dumps({"id": "x", "status": "shipped"}).encode()
        r = requests.post(f"{BASE_URL}/api/webhooks/revorder/{TEST_DOMAIN}", data=body,
                          headers={"Content-Type": "application/json",
                                   "X-Signature": "sha256=deadbeef"})
        assert r.status_code == 401

    def test_unknown_domain_404(self, enabled_domain_creds):
        body = b"{}"
        sig = _sign(enabled_domain_creds["secret_key"], body)
        r = requests.post(f"{BASE_URL}/api/webhooks/revorder/nope.example",
                          data=body,
                          headers={"Content-Type": "application/json",
                                   "X-Signature": f"sha256={sig}"})
        assert r.status_code == 404

    def test_valid_signature_updates_order_and_dedupes(self, enabled_domain_creds, admin_session):
        # Find a real order to reference
        orders = admin_session.get(f"{BASE_URL}/api/admin/orders").json()
        order_list = orders.get("orders") or orders.get("items") or orders if isinstance(orders, list) else orders
        # Try common shapes
        candidate = None
        if isinstance(orders, dict):
            for key in ("orders", "items", "results", "data"):
                if isinstance(orders.get(key), list) and orders[key]:
                    candidate = orders[key][0]
                    break
        elif isinstance(orders, list) and orders:
            candidate = orders[0]
        if not candidate:
            pytest.skip("No existing orders to attach webhook to")

        order_ref = candidate.get("order_number") or candidate.get("id")
        assert order_ref
        event_id = f"evt_test_{uuid.uuid4().hex[:12]}"
        payload = {
            "id": event_id,
            "event": "shipment.updated",
            "external_id": candidate.get("id"),
            "order_number": candidate.get("order_number"),
            "status": "shipped",
            "tracking_number": "TESTTRK123",
            "courier": "Speedy",
        }
        body = json.dumps(payload).encode()
        sig = _sign(enabled_domain_creds["secret_key"], body)
        r = requests.post(f"{BASE_URL}/api/webhooks/revorder/{TEST_DOMAIN}",
                          data=body,
                          headers={"Content-Type": "application/json",
                                   "X-Signature": f"sha256={sig}"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data.get("matched", 0) >= 1

        # Duplicate — same event_id
        r2 = requests.post(f"{BASE_URL}/api/webhooks/revorder/{TEST_DOMAIN}",
                           data=body,
                           headers={"Content-Type": "application/json",
                                    "X-Signature": f"sha256={sig}"})
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True

        # Verify event landed in listing
        listing = admin_session.get(f"{BASE_URL}/api/admin/integrations/revorder").json()
        events = listing["events"]
        assert any(e.get("event_id") == event_id for e in events)


# ---------- regressions from iter 27 ----------
class TestRegressions:
    def test_geo_country_returns_empty_city(self):
        r = requests.get(f"{BASE_URL}/api/geo/country")
        assert r.status_code == 200
        assert r.json().get("city", "") == ""

    def test_retatrutide_compare_at(self):
        r = requests.get(f"{BASE_URL}/api/products/21-retatrutide-5")
        assert r.status_code == 200
        variants = (r.json().get("product") or {}).get("variants", []) or r.json().get("variants", [])
        assert variants
        # Look for the 5mg compare-at of 59
        found_59 = any(abs((v.get("compare_at_eur") or 0) - 59.0) < 0.01 for v in variants)
        assert found_59, [v.get("compare_at_eur") for v in variants]
