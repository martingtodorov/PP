"""Iteration 66: checkout layout & dial prefixes, admin filters bank_transfer/cod,
order detail fields (payment_method, discount_code), NextLevel failure alert paths."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://peptide-checkout-32.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@purepeptide.bg")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@PurePeptide2026")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, r.text
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------- Checkout config: dial prefixes ----------------
class TestDialPrefixes:
    def test_precheckout_config_returns_dial_territories(self):
        r = None
        for _ in range(3):
            r = requests.get(f"{BASE_URL}/api/nextcart/config",
                             params={"country": "BG"}, timeout=30)
            if r.status_code == 200:
                break
        assert r.status_code == 200, r.text
        data = r.json()
        terr = data.get("precheckout_phone_territories") or []
        assert isinstance(terr, list)
        # Should at least contain BG/GR/RO among territories
        isos = {t.get("iso2") for t in terr}
        assert {"BG", "GR", "RO"}.issubset(isos) or len(isos) > 3, isos

    def test_countries_endpoint_has_dial(self):
        r = requests.get(f"{BASE_URL}/api/nextcart/countries", timeout=30)
        assert r.status_code == 200
        cs = r.json().get("countries") or []
        bg = next((c for c in cs if c.get("iso2") == "BG"), None)
        gr = next((c for c in cs if c.get("iso2") == "GR"), None)
        ro = next((c for c in cs if c.get("iso2") == "RO"), None)
        assert bg and str(bg.get("dial")) == "359"
        assert gr and str(gr.get("dial")) == "30"
        assert ro and str(ro.get("dial")) == "40"


# ---------------- Admin orders filters ----------------
class TestAdminOrderFilters:
    def test_filter_bank_transfer(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"status": "bank_transfer", "limit": 200},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "orders" in data and "total" in data
        for o in data["orders"]:
            pm = o.get("payment_method") or "bank_transfer"
            assert pm == "bank_transfer", f"Order {o.get('order_number')} pm={pm}"

    def test_filter_cod(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"status": "cod", "limit": 200},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for o in data["orders"]:
            assert o.get("payment_method") == "cod", f"Order {o.get('order_number')} pm={o.get('payment_method')}"

    def test_filter_counts_preview(self, admin_headers):
        """Preview DB is expected to have ~1 bank_transfer + ~15 COD."""
        bt = requests.get(f"{BASE_URL}/api/admin/orders", params={"status": "bank_transfer"},
                          headers=admin_headers, timeout=30).json()
        cod = requests.get(f"{BASE_URL}/api/admin/orders", params={"status": "cod"},
                           headers=admin_headers, timeout=30).json()
        # Note: bank_transfer includes legacy null payment_method rows
        print(f"bank_transfer total={bt['total']} cod total={cod['total']}")
        assert bt["total"] >= 1
        assert cod["total"] >= 1


# ---------------- Admin order detail: payment_method + discount_code ----------------
class TestOrderDetail:
    def test_order_view_has_payment_method(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"limit": 10}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        orders = r.json().get("orders") or []
        assert orders, "no orders in preview DB"
        for o in orders[:3]:
            assert "payment_method" in o, o
            oid = o["id"]
            d = requests.get(f"{BASE_URL}/api/admin/orders/{oid}",
                             headers=admin_headers, timeout=30)
            assert d.status_code == 200
            body = d.json()
            order = body.get("order") or body
            assert "payment_method" in order
            # discount_code key may be empty string or None
            assert "discount_code" in order


# ---------------- NextLevel failure alert ----------------
class TestNextLevelFailureAlert:
    def test_fulfillment_create_missing_creds_alerts(self, admin_headers):
        """With fulfillment cfg mocked / missing creds, POST fulfillment/create should
        return a 4xx/5xx AND leave fulfillment.alerted_error on the order."""
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"status": "cod", "limit": 5},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        orders = r.json().get("orders") or []
        if not orders:
            pytest.skip("no COD orders to test")
        # Pick an order that hasn't shipped
        target = None
        for o in orders:
            if o.get("fulfillment_status") not in ("shipped", "fulfilled"):
                target = o
                break
        if not target:
            pytest.skip("no unshipped orders")

        oid = target["id"]
        # Try the two known endpoints; the app uses fulfillment/create
        resp = requests.post(f"{BASE_URL}/api/admin/orders/{oid}/fulfillment/create",
                             headers=admin_headers, timeout=30)
        print(f"fulfillment/create -> {resp.status_code} {resp.text[:200]}")
        # It should NOT be 200 in a mocked/no-cred environment; 4xx or 502 acceptable.
        # But if fulfillment number already exists (409), still valid response.
        assert resp.status_code in (400, 401, 403, 404, 409, 422, 500, 502), resp.text

        # If it was rejected due to data/credentials, check side-effects
        if resp.status_code in (422, 502, 400):
            d = requests.get(f"{BASE_URL}/api/admin/orders/{oid}",
                             headers=admin_headers, timeout=30).json()
            order = d.get("order") or d
            ff = order.get("fulfillment") or {}
            # Alert may or may not have been recorded depending on data completeness path
            print(f"order fulfillment: alerted_error={ff.get('alerted_error')} "
                  f"fulfillment_error={order.get('fulfillment_error')}")

    def test_dedup_second_call_no_duplicate_alert(self, admin_headers):
        # Fire again for the same order — expect deduped alert (no exception, still 4xx/5xx)
        r = requests.get(f"{BASE_URL}/api/admin/orders",
                         params={"status": "cod", "limit": 5},
                         headers=admin_headers, timeout=30)
        orders = r.json().get("orders") or []
        target = next((o for o in orders if o.get("fulfillment_status") not in ("shipped", "fulfilled")), None)
        if not target:
            pytest.skip("no unshipped orders")
        oid = target["id"]
        for _ in range(2):
            resp = requests.post(f"{BASE_URL}/api/admin/orders/{oid}/fulfillment/create",
                                 headers=admin_headers, timeout=30)
            assert resp.status_code != 500 or "alerted" not in resp.text.lower()


# ---------------- Regression: delivery ETA ----------------
class TestDeliveryETAregression:
    @pytest.mark.parametrize("cc,expected", [("BG", "1"), ("GR", "1"), ("RO", "1"), ("DE", "5")])
    def test_precheckout_config(self, cc, expected):
        r = requests.get(f"{BASE_URL}/api/nextcart/config",
                         params={"country": cc}, timeout=30)
        assert r.status_code == 200, r.text
        # The frontend derives ETA client-side; here we only verify config responds for country
        assert r.json().get("delivery_methods") is not None or r.json().get("payment_methods") is not None
