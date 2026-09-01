"""Iteration-10 backend tests: contact form, push, best-seller ordering,
NAD+/Bacteriostatic water hidden, manual ordering, pages, checkout notify."""
import os
import re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://shopify-migrate-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASS = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"admin login failed {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# ---------- Regression: storefront alive ----------
class TestStorefrontAlive:
    def test_products_returns_21_active(self, anon_session):
        r = anon_session.get(f"{API}/products", timeout=15)
        assert r.status_code == 200
        data = r.json()
        prods = data.get("products", data) if isinstance(data, dict) else data
        assert isinstance(prods, list)
        assert len(prods) == 21, f"expected 21 active products, got {len(prods)}"

    def test_collections_returns_7(self, anon_session):
        r = anon_session.get(f"{API}/collections", timeout=15)
        assert r.status_code == 200
        data = r.json()
        cols = data.get("collections", data) if isinstance(data, dict) else data
        assert len(cols) == 7

    def test_product_page_bpc157(self, anon_session):
        r = anon_session.get(f"{API}/products/bpc-157-5", timeout=15)
        assert r.status_code == 200
        p = r.json().get("product", r.json())
        assert p.get("handle") == "bpc-157-5"


# ---------- NAD+ and bacteriostatic water hidden ----------
class TestHiddenProducts:
    HIDDEN_HANDLES_CANDIDATES = ["nad-100", "nad-plus-100", "nad-100mg", "bacteriostatic-water", "bakteriostaticna-voda"]

    def test_hidden_products_not_in_public_list(self, anon_session):
        r = anon_session.get(f"{API}/products", timeout=15)
        prods = r.json().get("products", r.json()) if isinstance(r.json(), dict) else r.json()
        titles = " ".join([(p.get("title") or "") + " " + (p.get("handle") or "") for p in prods]).lower()
        assert "nad" not in titles, f"NAD product still visible: {titles}"
        assert "бактериостатична" not in titles and "bacteriostatic" not in titles

    def test_hidden_product_direct_get_still_works(self, anon_session):
        # find a hidden product handle via admin
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
        r = s.get(f"{API}/admin/products", timeout=15)
        assert r.status_code == 200
        data = r.json()
        allp = data.get("products", data) if isinstance(data, dict) else data
        hidden = [p for p in allp if p.get("active") is False]
        assert len(hidden) >= 2, f"expected >=2 hidden products, got {len(hidden)}"
        # verify at least one has NAD or bacterio in title/handle
        h_titles = " ".join([(p.get("title", "") + " " + p.get("handle", "")).lower() for p in hidden])
        assert ("nad" in h_titles) and ("бактериостатичн" in h_titles or "bacterio" in h_titles), h_titles
        # direct GET works
        for p in hidden[:2]:
            handle = p.get("handle")
            rr = anon_session.get(f"{API}/products/{handle}", timeout=15)
            assert rr.status_code == 200, f"hidden {handle} direct GET failed"


# ---------- Best-seller ordering ----------
class TestBestSellerOrder:
    EXPECTED_PREFIX = ["ghk-cu", "bpc-157", "tb-500", "hgh"]  # loose prefixes

    def _verify_order(self, prods):
        # Check both title AND handle since handles have manual-sort prefixes (1-, fg, axc)
        titles = [(p.get("title") or "").lower() for p in prods[:4]]
        handles = [(p.get("handle") or "").lower() for p in prods[:4]]
        combined = [t + " " + h for t, h in zip(titles, handles)]
        assert "ghk-cu" in combined[0], f"first should be GHK-Cu, got {combined}"
        assert "bpc-157" in combined[1] or "bpc157" in combined[1], f"2nd should be BPC-157, got {combined}"
        assert "tb-500" in combined[2] or "tb500" in combined[2], f"3rd should be TB-500, got {combined}"
        assert "hgh" in combined[3] or "176-191" in combined[3] or "frag" in combined[3], \
            f"4th should be hGH frag, got {combined}"

    def test_products_order(self, anon_session):
        r = anon_session.get(f"{API}/products", timeout=15)
        prods = r.json().get("products", r.json()) if isinstance(r.json(), dict) else r.json()
        self._verify_order(prods)

    def test_all_peptides_collection_order(self, anon_session):
        r = anon_session.get(f"{API}/collections/all-peptides", timeout=15)
        assert r.status_code == 200
        data = r.json()
        prods = data.get("products", [])
        self._verify_order(prods)


# ---------- Admin manual ordering ----------
class TestAdminManualOrdering:
    def test_admin_collection_products_ordered(self, admin_session):
        r = admin_session.get(f"{API}/admin/collections/all-peptides/products", timeout=15)
        assert r.status_code == 200
        data = r.json()
        prods = data.get("products", data) if isinstance(data, dict) else data
        assert isinstance(prods, list) and len(prods) > 0
        assert all(p.get("handle") for p in prods)

    def test_reorder_and_restore(self, admin_session, anon_session):
        r = admin_session.get(f"{API}/admin/collections/all-peptides/products", timeout=15)
        prods = r.json().get("products", r.json())
        original_handles = [p["handle"] for p in prods]

        # swap first two
        new_order = [original_handles[1], original_handles[0]] + original_handles[2:]
        rr = admin_session.put(
            f"{API}/admin/collections/all-peptides/order",
            json={"handles": new_order},
            timeout=15,
        )
        assert rr.status_code == 200, f"set order failed {rr.status_code} {rr.text}"

        # storefront reflects change
        pub = anon_session.get(f"{API}/collections/all-peptides", timeout=15).json()
        pub_prods = pub.get("products", [])
        pub_handles = [p["handle"] for p in pub_prods]
        assert pub_handles[0] == new_order[0] and pub_handles[1] == new_order[1], \
            f"storefront order not applied: {pub_handles[:3]}"

        # Restore by "order by sales" — leaves shop best-seller-first
        rs = admin_session.post(f"{API}/admin/collections/all-peptides/order/by-sales", timeout=15)
        assert rs.status_code == 200

        # verify GHK-Cu is first again (by title/handle contains ghk-cu)
        pub2 = anon_session.get(f"{API}/collections/all-peptides", timeout=15).json()
        first = pub2["products"][0]
        assert "ghk-cu" in (first.get("handle", "") + first.get("title", "")).lower(), \
            f"after by-sales first is {first.get('handle')}"


# ---------- Contact form ----------
class TestContactForm:
    _msg_id = None

    def test_reject_empty_name(self, anon_session):
        r = anon_session.post(f"{API}/contact",
                              json={"name": "", "email": "x@y.com", "phone": "", "message": "hi"}, timeout=15)
        assert r.status_code == 400

    def test_reject_invalid_email(self, anon_session):
        r = anon_session.post(f"{API}/contact",
                              json={"name": "Test", "email": "notanemail", "phone": "", "message": "hi"}, timeout=15)
        assert r.status_code == 400

    def test_submit_valid(self, anon_session):
        r = anon_session.post(f"{API}/contact", json={
            "name": "TEST_Iter10",
            "email": "test@example.com",
            "phone": "+359888000000",
            "message": "Автоматичен тест — iteration 10.",
            "locale": "bg",
        }, timeout=25)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        assert r.json().get("ok") is True

    def test_message_in_admin(self, admin_session):
        r = admin_session.get(f"{API}/admin/messages", timeout=15)
        assert r.status_code == 200
        msgs = r.json().get("messages", [])
        m = next((x for x in msgs if x.get("name") == "TEST_Iter10"), None)
        assert m is not None, "test message not found in admin"
        TestContactForm._msg_id = m["id"]

    def test_handle_message(self, admin_session):
        assert TestContactForm._msg_id, "no message id"
        r = admin_session.patch(f"{API}/admin/messages/{TestContactForm._msg_id}",
                                json={"status": "handled"}, timeout=15)
        assert r.status_code == 200
        # verify it moved
        r2 = admin_session.get(f"{API}/admin/messages?status=handled", timeout=15)
        ids = [m["id"] for m in r2.json().get("messages", [])]
        assert TestContactForm._msg_id in ids


# ---------- Push endpoints ----------
class TestPush:
    def test_public_key(self, anon_session):
        r = anon_session.get(f"{API}/push/public-key", timeout=15)
        assert r.status_code == 200
        assert r.json().get("public_key")

    def test_status_requires_admin(self, anon_session):
        r = anon_session.get(f"{API}/admin/push/status", timeout=15)
        assert r.status_code in (401, 403)

    def test_status_admin(self, admin_session):
        r = admin_session.get(f"{API}/admin/push/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "subscriptions" in d and "log" in d and "public_key" in d

    def test_subscribe_requires_admin(self, anon_session):
        r = anon_session.post(f"{API}/push/subscriptions", json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/TEST_fake",
            "keys": {"p256dh": "x", "auth": "y"},
        }, timeout=15)
        assert r.status_code in (401, 403)

    def test_subscribe_and_unsubscribe(self, admin_session):
        endpoint = "https://fcm.googleapis.com/fcm/send/TEST_iter10_fake_endpoint"
        r = admin_session.post(f"{API}/push/subscriptions", json={
            "endpoint": endpoint, "keys": {"p256dh": "BFakeP256dh", "auth": "FakeAuth"},
        }, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        assert r.json().get("ok") is True
        # cleanup
        rd = admin_session.delete(f"{API}/push/subscriptions", json={"endpoint": endpoint}, timeout=15)
        assert rd.status_code == 200

    def test_push_test_no_subs_returns_400(self, admin_session):
        # remove any test sub first (best effort)
        r = admin_session.post(f"{API}/admin/push/test", timeout=15)
        # Real browser subs likely absent; expect 400 with BG msg. If there ARE real subs it may be 200.
        if r.status_code == 400:
            assert re.search(r"[А-я]", r.text), f"no bg text: {r.text}"
        else:
            assert r.status_code == 200


# ---------- Checkout with notifications ----------
class TestCheckout:
    _order_number = None

    def test_place_order(self, anon_session):
        # find bpc-157-5 product id
        r = anon_session.get(f"{API}/products/bpc-157-5", timeout=15)
        assert r.status_code == 200
        p = r.json().get("product", r.json())
        pid = p["id"]
        payload = {
            "items": [{"product_id": pid, "variant_sku": "PP-BPC157-5MG", "quantity": 1}],
            "customer_email": "test@example.com",
            "customer_name": "TEST Iter10",
            "customer_phone": "+359888111222",
            "shipping": {
                "full_name": "TEST Iter10",
                "phone": "+359888111222",
                "line1": "ul. Test 1",
                "city": "Sofia",
                "postal_code": "1000",
                "country": "BG",
            },
            "shipping_method": "econt",
            "terms_accepted": True,
        }
        r = anon_session.post(f"{API}/checkout", json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        order = r.json().get("order", r.json())
        onum = order.get("order_number")
        assert onum and re.match(r"^[A-Z]{3}[0-9]{2}$", onum), f"bad order_number: {onum}"
        TestCheckout._order_number = onum
        print(f"CREATED ORDER: {onum}")

    def test_inventory_log_has_entry(self, admin_session):
        assert TestCheckout._order_number
        r = admin_session.get(f"{API}/admin/inventory/log", timeout=15)
        assert r.status_code == 200
        entries = r.json().get("log", r.json())
        # last entry should reference BPC-157 or the order
        recent = entries[:5] if isinstance(entries, list) else []
        assert len(recent) > 0, "no inventory log entries"

    def test_order_in_admin(self, admin_session):
        r = admin_session.get(f"{API}/admin/orders?limit=50", timeout=15)
        assert r.status_code == 200
        orders = r.json().get("orders", [])
        found = any(o.get("order_number") == TestCheckout._order_number for o in orders)
        assert found, f"order {TestCheckout._order_number} not in admin"


# ---------- Static pages ----------
class TestPages:
    SLUGS = ["what-are-peptides", "faq", "contacts", "chemical-analysis", "partners",
             "about", "cookies", "privacy-policy", "terms-of-service", "shipping-policy",
             "scientific-literature"]

    @pytest.mark.parametrize("slug", SLUGS)
    def test_public_page(self, anon_session, slug):
        r = anon_session.get(f"{API}/pages/{slug}?locale=bg", timeout=15)
        assert r.status_code == 200, f"{slug} -> {r.status_code}"
        page = r.json().get("page", r.json())
        # Some pages use faq_items instead of html
        content = (page.get("html") or "") + str(page.get("faq_items") or "") + str(page.get("body") or "")
        assert len(content) > 20, f"{slug} content too small"

    def test_admin_pages_lists_all(self, admin_session):
        r = admin_session.get(f"{API}/admin/pages", timeout=15)
        assert r.status_code == 200
        slugs = [s["slug"] for s in r.json().get("slugs", [])]
        for expected in self.SLUGS:
            assert expected in slugs, f"missing slug in admin: {expected}"

    def test_contacts_page_has_bg_copy(self, anon_session):
        r = anon_session.get(f"{API}/pages/contacts?locale=bg", timeout=15)
        page = r.json().get("page", r.json())
        html = (page.get("html") or "") + str(page.get("body") or "")
        # Bulgarian keywords
        assert "contact@purepeptide.bg" in html
        assert "10:00" in html and "17:00" in html
        assert "24" in html


# ---------- Sort dropdown removed check (backend side: check that products don't need it) ----------
# UI check will be in playwright.


# ---------- Static assets ----------
class TestStaticAssets:
    def test_service_worker(self, anon_session):
        r = anon_session.get(f"{BASE}/service-worker.js", timeout=15)
        assert r.status_code == 200
        assert "self" in r.text or "addEventListener" in r.text

    def test_manifest(self, anon_session):
        r = anon_session.get(f"{BASE}/manifest.json", timeout=15)
        assert r.status_code == 200
        m = r.json()
        assert m.get("display") == "standalone"

    def test_logo192(self, anon_session):
        r = anon_session.get(f"{BASE}/logo192.png", timeout=15)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
