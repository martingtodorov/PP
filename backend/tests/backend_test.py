"""PurePeptide backend e2e tests - covers public catalog, auth, checkout, admin flows."""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"
CUSTOMER_EMAIL = "customer@example.com"
CUSTOMER_PASSWORD = "Customer123!"


# ---------- Shared fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def customer_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    assert r.status_code == 200, f"Customer login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def sample_product(session):
    r = session.get(f"{API}/products?limit=5")
    assert r.status_code == 200
    products = r.json()["products"]
    assert len(products) > 0
    # pick one with stock
    for p in products:
        for v in p.get("variants", []):
            if v.get("stock", 0) > 2:
                return p, v
    return products[0], products[0]["variants"][0]


# ---------- Public catalog ----------
class TestCatalog:
    def test_root(self, session):
        # ingress may strip trailing slash; try both
        r = session.get(f"{API}/")
        if r.status_code != 200:
            r = session.get(f"{API}/settings")  # any public api proves backend is up
        assert r.status_code == 200

    def test_collections_seeded(self, session):
        r = session.get(f"{API}/collections")
        assert r.status_code == 200
        cols = r.json()["collections"]
        assert isinstance(cols, list)
        assert len(cols) >= 7, f"Expected >=7 collections, got {len(cols)}"
        # validate fields
        for c in cols:
            assert "handle" in c and "title" in c

    def test_collection_by_handle(self, session):
        col_handle = session.get(f"{API}/collections").json()["collections"][0]["handle"]
        r = session.get(f"{API}/collections/{col_handle}")
        assert r.status_code == 200
        body = r.json()
        assert body["collection"]["handle"] == col_handle
        assert isinstance(body["products"], list)

    def test_collection_404(self, session):
        r = session.get(f"{API}/collections/does-not-exist")
        assert r.status_code == 404

    def test_products_seeded(self, session):
        r = session.get(f"{API}/products?limit=100")
        assert r.status_code == 200
        prods = r.json()["products"]
        assert len(prods) >= 20, f"Expected >=20 products, got {len(prods)}"
        # ensure no _id leaked
        for p in prods:
            assert "_id" not in p
            assert "variants" in p

    def test_product_by_handle(self, session):
        prods = session.get(f"{API}/products?limit=1").json()["products"]
        handle = prods[0]["handle"]
        r = session.get(f"{API}/products/{handle}")
        assert r.status_code == 200
        body = r.json()
        assert body["product"]["handle"] == handle
        assert "related" in body

    def test_articles(self, session):
        r = session.get(f"{API}/articles")
        assert r.status_code == 200
        assert isinstance(r.json()["articles"], list)

    def test_settings(self, session):
        r = session.get(f"{API}/settings")
        assert r.status_code == 200


# ---------- Auth ----------
class TestAuth:
    def test_register_login_logout(self, session):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Pass1234!", "name": "Tester"})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == email
        assert "pp_token" in s.cookies

        # me endpoint with cookie
        rm = s.get(f"{API}/auth/me")
        assert rm.status_code == 200
        assert rm.json()["user"]["email"] == email

        # logout clears cookie
        rl = s.post(f"{API}/auth/logout")
        assert rl.status_code == 200

        # login again
        rli = s.post(f"{API}/auth/login", json={"email": email, "password": "Pass1234!"})
        assert rli.status_code == 200

    def test_register_duplicate(self, session):
        r = session.post(f"{API}/auth/register", json={"email": ADMIN_EMAIL, "password": "whatever", "name": "x"})
        assert r.status_code == 400

    def test_login_invalid(self, session):
        r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_admin_login_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"
        assert "pp_token" in s.cookies

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["user"] is None


# ---------- Checkout ----------
class TestCheckout:
    def _make_payload(self, product, variant, qty=1, method="econt_office"):
        return {
            "items": [{"product_id": product["id"], "variant_sku": variant["sku"], "quantity": qty}],
            "shipping": {
                "full_name": "Test User", "phone": "+359888000111", "email": "guest@example.com",
                "line1": "ул. Тест 1", "city": "София", "postal_code": "1000", "country": "BG",
            },
            "customer_email": "guest@example.com",
            "customer_name": "Test User",
            "customer_phone": "+359888000111",
            "shipping_method": method,
        }

    def test_guest_checkout_creates_order(self, sample_product):
        product, variant = sample_product
        payload = self._make_payload(product, variant, 1)
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["order"]["payment_status"] == "awaiting_payment"
        assert data["order"]["fulfillment_status"] == "unfulfilled"
        assert data["order"]["customer_id"] is None
        bank = data["bank_transfer"]
        assert bank["iban"] and bank["bic"] and bank["reference"].startswith("PP-")
        assert bank["amount_eur"] == data["order"]["total_eur"]

    def test_shipping_econt_under_100(self, sample_product):
        product, variant = sample_product
        payload = self._make_payload(product, variant, 1, "econt_office")
        if variant["price_eur"] >= 100:
            pytest.skip("variant too expensive for under-100 test")
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 200
        assert r.json()["order"]["shipping_eur"] == 5.99

    def test_shipping_speedy(self, sample_product):
        product, variant = sample_product
        payload = self._make_payload(product, variant, 1, "speedy")
        if variant["price_eur"] >= 100:
            pytest.skip("variant too expensive")
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 200
        assert r.json()["order"]["shipping_eur"] == 7.49

    def test_shipping_free_over_100(self, sample_product):
        product, variant = sample_product
        # buy enough to exceed 100 eur
        qty = max(1, int(120 / max(variant["price_eur"], 1)) + 1)
        if variant.get("stock", 0) < qty:
            pytest.skip("insufficient stock for free shipping test")
        payload = self._make_payload(product, variant, qty)
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 200
        assert r.json()["order"]["shipping_eur"] == 0.0

    def test_insufficient_stock_rejected(self, sample_product):
        product, variant = sample_product
        payload = self._make_payload(product, variant, 999999)
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 400

    def test_invalid_product_rejected(self):
        payload = {
            "items": [{"product_id": "bogus-id", "variant_sku": "X", "quantity": 1}],
            "shipping": {"full_name": "x", "phone": "1", "line1": "x", "city": "x", "postal_code": "1000"},
            "customer_email": "x@x.com", "customer_name": "x", "customer_phone": "1",
        }
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 400

    def test_authenticated_checkout_links_to_user(self, customer_session, sample_product):
        product, variant = sample_product
        payload = {
            "items": [{"product_id": product["id"], "variant_sku": variant["sku"], "quantity": 1}],
            "shipping": {"full_name": "Иван", "phone": "+359888000111", "line1": "ул. Тест 1",
                         "city": "София", "postal_code": "1000", "country": "BG"},
            "customer_email": CUSTOMER_EMAIL, "customer_name": "Иван", "customer_phone": "+359888000111",
            "shipping_method": "econt_office",
        }
        r = customer_session.post(f"{API}/checkout", json=payload)
        assert r.status_code == 200
        order = r.json()["order"]
        assert order["customer_id"] is not None

    def test_my_orders_requires_auth(self):
        r = requests.get(f"{API}/me/orders")
        assert r.status_code == 401

    def test_my_orders_returns_for_customer(self, customer_session):
        r = customer_session.get(f"{API}/me/orders")
        assert r.status_code == 200
        orders = r.json()["orders"]
        assert isinstance(orders, list)
        assert len(orders) >= 1


# ---------- Admin guards ----------
class TestAdminGuards:
    @pytest.mark.parametrize("path", [
        "/admin/stats", "/admin/orders", "/admin/products", "/admin/customers", "/admin/imports"
    ])
    def test_unauthenticated_blocked(self, path):
        r = requests.get(f"{API}{path}")
        assert r.status_code == 401

    @pytest.mark.parametrize("path", [
        "/admin/stats", "/admin/orders", "/admin/products", "/admin/customers"
    ])
    def test_customer_forbidden(self, customer_session, path):
        r = customer_session.get(f"{API}{path}")
        assert r.status_code == 403

    def test_admin_stats(self, admin_session):
        r = admin_session.get(f"{API}/admin/stats")
        assert r.status_code == 200
        s = r.json()
        for key in ("total_orders", "awaiting_payment", "paid", "customers", "products", "revenue_eur"):
            assert key in s

    def test_admin_orders_list(self, admin_session):
        r = admin_session.get(f"{API}/admin/orders")
        assert r.status_code == 200
        assert isinstance(r.json()["orders"], list)

    def test_admin_products_list(self, admin_session):
        r = admin_session.get(f"{API}/admin/products")
        assert r.status_code == 200
        assert len(r.json()["products"]) >= 20

    def test_admin_customers_list(self, admin_session):
        r = admin_session.get(f"{API}/admin/customers")
        assert r.status_code == 200
        custs = r.json()["customers"]
        assert any(c["email"] == CUSTOMER_EMAIL for c in custs)


# ---------- Admin order workflow ----------
class TestAdminOrderWorkflow:
    @pytest.fixture(scope="class")
    def fresh_order_id(self, sample_product):
        product, variant = sample_product
        payload = {
            "items": [{"product_id": product["id"], "variant_sku": variant["sku"], "quantity": 1}],
            "shipping": {"full_name": "Wf User", "phone": "+359888000111",
                         "line1": "ул. Тест 1", "city": "София", "postal_code": "1000", "country": "BG"},
            "customer_email": "wf@example.com", "customer_name": "Wf User", "customer_phone": "+359888000111",
            "shipping_method": "speedy",
        }
        r = requests.post(f"{API}/checkout", json=payload)
        assert r.status_code == 200, r.text
        return r.json()["order"]["id"]

    def test_create_shipment_before_paid_rejected(self, admin_session, fresh_order_id):
        r = admin_session.post(f"{API}/admin/orders/{fresh_order_id}/create-shipment",
                               json={"carrier": "speedy"})
        assert r.status_code == 400

    def test_mark_paid(self, admin_session, fresh_order_id):
        r = admin_session.post(f"{API}/admin/orders/{fresh_order_id}/mark-paid")
        assert r.status_code == 200
        # verify
        orders = admin_session.get(f"{API}/admin/orders?status=paid").json()["orders"]
        assert any(o["id"] == fresh_order_id for o in orders)

    def test_create_shipment_after_paid(self, admin_session, fresh_order_id):
        r = admin_session.post(f"{API}/admin/orders/{fresh_order_id}/create-shipment",
                               json={"carrier": "speedy", "service": "standard", "parcel_weight_kg": 0.5})
        assert r.status_code == 200
        tracking = r.json()["tracking"]
        assert tracking["mocked"] is True
        assert tracking["tracking_number"].startswith("SPEEDY-")
        assert "speedy.bg" in tracking["tracking_url"]


# ---------- Admin import + settings ----------
class TestAdminImportAndSettings:
    def test_csv_import_inserts_and_updates(self, admin_session):
        csv_data = (
            "Handle,Title,Body HTML,Image Src,Variant SKU,Variant Price,Variant Inventory Qty,Tags,Collection,Option1 Value\n"
            "test-import-pep,Test Import Peptide,Описание,https://example.com/x.jpg,TIP-5MG,29.99,10,bpc,research-peptides,5mg\n"
            "test-import-pep,Test Import Peptide,Описание,https://example.com/x.jpg,TIP-10MG,49.99,5,bpc,research-peptides,10mg\n"
        )
        files = {"file": ("import.csv", io.BytesIO(csv_data.encode()), "text/csv")}
        # Use a separate session w/o JSON content-type for multipart
        s = requests.Session()
        s.cookies.update(admin_session.cookies)
        r = s.post(f"{API}/admin/import/products", files=files)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["inserted"] + body["updated"] >= 1

        # verify the product exists
        gp = requests.get(f"{API}/products/test-import-pep")
        assert gp.status_code == 200
        prod = gp.json()["product"]
        assert len(prod["variants"]) == 2

    def test_update_settings(self, admin_session):
        # fetch current settings
        cur = requests.get(f"{API}/settings").json()
        cur["test_marker"] = "qa-" + uuid.uuid4().hex[:6]
        r = admin_session.put(f"{API}/admin/settings", json={"value": cur})
        assert r.status_code == 200
        new = requests.get(f"{API}/settings").json()
        assert new.get("test_marker") == cur["test_marker"]

    def test_settings_unauthenticated(self):
        r = requests.put(f"{API}/admin/settings", json={"value": {}})
        assert r.status_code == 401
