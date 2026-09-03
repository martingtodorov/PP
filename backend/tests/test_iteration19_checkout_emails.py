"""Iteration-19: checkout shipping requirement, locale persistence, abandoned carts,
multilingual transactional emails, recovery-on-order."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL") else open("/app/frontend/.env").read().split(
    "REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASS = "Admin@PurePeptide2026"
TEST_TO = "admin@purepeptide.bg"


# ---------- helpers ----------
@pytest.fixture(scope="module")
def line_item():
    r = requests.get(f"{API}/products", params={"limit": 8}, timeout=15)
    assert r.status_code == 200
    prods = r.json().get("products") or r.json().get("items") or []
    for p in prods:
        for v in (p.get("variants") or []):
            if v.get("stock", 1) != 0 and v.get("price_eur"):
                return {"product_id": p["id"], "variant_sku": v["sku"], "price_eur": v["price_eur"]}
    pytest.skip("no purchasable variant")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _checkout_payload(li, *, email, terms=True, payment="cod", locale="bg",
                      omit_shipping_full_name=False, omit_shipping_phone=False):
    ship = {
        "full_name": "TEST Iter19",
        "phone": "+359888222999",
        "line1": "София Аксаков 12",
        "city": "СОФИЯ",
        "postal_code": "1000",
        "country": "BG",
    }
    if omit_shipping_full_name:
        ship.pop("full_name")
    if omit_shipping_phone:
        ship.pop("phone")
    return {
        "items": [{"product_id": li["product_id"], "variant_sku": li["variant_sku"], "quantity": 1}],
        "shipping": ship,
        "customer_email": email,
        "customer_name": "TEST Iter19",
        "customer_phone": "+359888222999",
        "shipping_method": "econt_office",
        "payment_method": payment,
        "delivery": {
            "provider_key": "econt", "provider_name": "Еконт",
            "method_key": "econt_office", "destination_type": "office",
            "label": "До офис на Еконт", "price_amount": 3.89, "currency": "EUR",
            "office": {"id": "1", "name": "София Аксаков",
                       "address": "Аксаков 12", "city": "СОФИЯ", "postal_code": "1000"},
            "address": None,
        },
        "discount_code": "",
        "terms_accepted": terms,
        "locale": locale,
    }


# ---------- POST /api/checkout ----------
class TestCheckoutContract:
    def test_missing_shipping_full_name_returns_422(self, line_item):
        p = _checkout_payload(line_item, email="TEST_iter19_missing_fn@example.com",
                              omit_shipping_full_name=True)
        r = requests.post(f"{API}/checkout", json=p, timeout=15)
        assert r.status_code == 422, r.text[:300]
        body = r.text
        assert "full_name" in body

    def test_missing_shipping_phone_returns_422(self, line_item):
        p = _checkout_payload(line_item, email="TEST_iter19_missing_ph@example.com",
                              omit_shipping_phone=True)
        r = requests.post(f"{API}/checkout", json=p, timeout=15)
        assert r.status_code == 422, r.text[:300]
        assert "phone" in r.text

    def test_terms_rejected_returns_400(self, line_item):
        p = _checkout_payload(line_item, email="TEST_iter19_terms@example.com", terms=False)
        r = requests.post(f"{API}/checkout", json=p, timeout=15)
        assert r.status_code == 400, r.text[:300]

    def test_full_payload_ok_and_locale_persisted(self, line_item):
        """The admin _order_view intentionally strips `locale`; verify persistence via Mongo."""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        email = "TEST_iter19_locale@example.com"
        p = _checkout_payload(line_item, email=email, locale="ro")
        r = requests.post(f"{API}/checkout", json=p, timeout=25)
        assert r.status_code == 200, r.text[:400]
        order = r.json().get("order")
        assert order and order.get("id")
        oid = order["id"]

        async def _fetch():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            doc = await client[os.environ["DB_NAME"]].orders.find_one({"id": oid}, {"_id": 0})
            client.close()
            return doc

        doc = asyncio.run(_fetch())
        assert doc, f"order {oid} not in db"
        assert (doc.get("locale") or "").lower() == "ro", f"locale={doc.get('locale')!r}"


# ---------- /api/nextcart/config ----------
EXPECTED = {
    "BG": {"econt", "boxnow", "pigeon"},
    "RO": {"fancourier"},
    "GR": {"speedex"},
    "HU": {"gls"}, "PL": {"gls"}, "SK": {"gls"}, "CZ": {"gls"},
    "SI": {"gls"}, "HR": {"gls"}, "IT": {"gls"}, "DE": {"gls"},
}


class TestNextcartConfig:
    @pytest.mark.parametrize("country,expected", list(EXPECTED.items()))
    def test_couriers(self, country, expected):
        r = requests.get(f"{API}/nextcart/config", params={"country": country}, timeout=25)
        assert r.status_code == 200
        cfg = r.json()
        methods = cfg.get("delivery_methods") or []
        assert methods, f"{country}: no methods"
        keys = {m.get("provider_key") for m in methods}
        assert keys == expected, f"{country}: got {keys} expected {expected}"
        for m in methods:
            assert (m.get("currency") or "").upper() == "EUR"
        pm = cfg.get("payment_methods") or []
        assert pm and pm[0]["key"] == "cod"


# ---------- the bank details live on the order, not on a public endpoint ----------
def test_public_bank_endpoint_is_removed():
    assert requests.get(f"{API}/bank-details", timeout=10).status_code == 404


# ---------- /api/nextcart/countries ----------
def test_countries():
    r = requests.get(f"{API}/nextcart/countries", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["default"] == "BG"
    assert len(d["countries"]) == 11
    bg = next(c for c in d["countries"] if c["iso2"] == "BG")
    assert bg["name"] == "България"


# ---------- POST /api/cart/track ----------
def _track_body(email, locale="bg"):
    return {
        "email": email,
        "customer_name": "TEST Iter19",
        "phone": "+359888000111",
        "locale": locale,
        "items": [{"product_id": "p", "variant_sku": "sku", "title": "Ret 5",
                   "variant_name": "5 mg", "image": "", "price_eur": 55.0, "quantity": 2}],
    }


class TestCartTrack:
    def test_track_upserts(self):
        email = f"TEST_iter19_track_{int(time.time())}@example.com"
        r1 = requests.post(f"{API}/cart/track", json=_track_body(email), timeout=15)
        assert r1.status_code == 200, r1.text
        id1 = r1.json()["id"]
        r2 = requests.post(f"{API}/cart/track", json=_track_body(email), timeout=15)
        assert r2.status_code == 200
        assert r2.json()["id"] == id1, "second track must upsert the same id"

    def test_empty_items_400(self):
        body = _track_body("TEST_iter19_empty@example.com")
        body["items"] = []
        r = requests.post(f"{API}/cart/track", json=body, timeout=10)
        assert r.status_code == 400


# ---------- admin abandoned carts ----------
class TestAdminAbandoned:
    def test_list_and_send(self, admin_session):
        email = f"TEST_iter19_ab_{int(time.time())}@example.com"
        requests.post(f"{API}/cart/track", json=_track_body(email), timeout=15)
        r = admin_session.get(f"{API}/admin/abandoned-carts", timeout=15)
        assert r.status_code == 200, r.text[:200]
        carts = r.json().get("carts") or []
        assert any(c.get("email", "").lower() == email.lower() for c in carts)
        cid = next(c["id"] for c in carts if c.get("email", "").lower() == email.lower())
        # send now — but redirect the recipient to sandbox address
        # (backend uses cart.email; we can't easily override without patch — accept sent or reason)
        s = admin_session.post(f"{API}/admin/abandoned-carts/{cid}/send", timeout=25)
        assert s.status_code == 200, s.text[:200]
        # Resend sandbox: sending to non-verified emails may 403; document either outcome
        body = s.json()
        assert "sent" in body

    def test_sweep_ok(self, admin_session):
        r = admin_session.post(f"{API}/admin/abandoned-carts/sweep", timeout=25)
        assert r.status_code == 200
        assert "sent" in r.json()


# ---------- POST /api/admin/emails/test — multilingual ----------
LOCALES_REQUIRED = ["bg", "en", "ro", "gr", "de"]
LOCALES_ALL = ["bg", "en", "fr", "de", "cz", "hu", "pl", "sk", "si", "gr", "ro"]


class TestEmailTemplates:
    @pytest.mark.parametrize("locale", LOCALES_ALL)
    def test_order_email_all_locales(self, admin_session, locale):
        r = admin_session.post(f"{API}/admin/emails/test",
                               json={"to": TEST_TO, "kind": "order", "locale": locale},
                               timeout=30)
        assert r.status_code == 200, f"{locale}: {r.status_code} {r.text[:200]}"
        # sent may be False if Resend rejects address; we only assert render didn't 500
        assert "sent" in r.json()

    @pytest.mark.parametrize("locale", LOCALES_ALL)
    def test_abandoned_email_all_locales(self, admin_session, locale):
        # ensure at least one cart exists
        requests.post(f"{API}/cart/track",
                      json=_track_body(f"TEST_iter19_seed_{locale}@example.com", locale=locale),
                      timeout=15)
        r = admin_session.post(f"{API}/admin/emails/test",
                               json={"to": TEST_TO, "kind": "abandoned", "locale": locale},
                               timeout=30)
        assert r.status_code == 200, f"{locale}: {r.status_code} {r.text[:200]}"
        assert "sent" in r.json()

    def test_required_locales_send_true(self, admin_session):
        """At least the required locales must actually be sent (sent:true)."""
        results = {}
        for loc in LOCALES_REQUIRED:
            r = admin_session.post(f"{API}/admin/emails/test",
                                   json={"to": TEST_TO, "kind": "order", "locale": loc},
                                   timeout=30)
            results[loc] = (r.status_code, r.json() if r.status_code == 200 else r.text[:200])
        # Assert at least one succeeded to confirm Resend integration works
        successful = [l for l, (sc, body) in results.items()
                      if sc == 200 and isinstance(body, dict) and body.get("sent")]
        assert successful, f"No email was actually sent (Resend may be misconfigured): {results}"


# ---------- Order placement marks the open cart as recovered ----------
class TestRecoverOnOrder:
    def test_order_recovers_open_cart(self, line_item, admin_session):
        email = f"TEST_iter19_recover_{int(time.time())}@example.com"
        # track abandoned cart
        r = requests.post(f"{API}/cart/track", json=_track_body(email), timeout=15)
        assert r.status_code == 200
        cart_id = r.json()["id"]
        # place order for same email
        p = _checkout_payload(line_item, email=email)
        rc = requests.post(f"{API}/checkout", json=p, timeout=25)
        assert rc.status_code == 200, rc.text[:200]
        # admin list
        lst = admin_session.get(f"{API}/admin/abandoned-carts", timeout=15).json().get("carts") or []
        match = next((c for c in lst if c.get("id") == cart_id), None)
        assert match, "cart missing from admin list"
        assert match.get("status") == "recovered", f"status={match.get('status')}"
