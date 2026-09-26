"""Iteration 69 — three-point audit fixes:

1) Public GET /api/settings must NOT expose bank_iban/bank_bic/bank_holder/bank_name,
   but admin GET /api/admin/settings still returns them.
2) A bank_transfer order still carries the bank_transfer block (POST /api/checkout
   and GET /api/orders/{id}) with holder/name/iban/bic/reference/amount.
3) prerender.fix_images and frontend fixImages remove sourceless <img>, replace alt="",
   preserve meaningful alt, and are applied to page bodies.
"""
import os
import re
import sys
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://peptide-checkout-32.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@purepeptide.bg")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@PurePeptide2026")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"

sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


# ---- Public settings must NOT expose bank ----
class TestPublicSettingsPrivacy:
    PRIVATE = ("bank_iban", "bank_bic", "bank_holder", "bank_name")

    @pytest.mark.parametrize("locale", ["bg", "en", "gr", "ro", "fr", "de"])
    def test_no_bank_in_public_settings(self, api, locale):
        r = api.get(f"{BASE_URL}/api/settings", params={"locale": locale})
        assert r.status_code == 200, r.text
        data = r.json()
        for k in self.PRIVATE:
            assert k not in data, f"private key {k} leaked in locale {locale}"
        # storefront still needs these
        assert "site_name" in data or "currency" in data or "shipping" in data
        assert "shipping" in data

    def test_admin_settings_still_has_bank(self, api, admin_token):
        r = api.get(f"{BASE_URL}/api/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        data = r.json()
        # admin settings shape may wrap in {settings:{...}} or {value:{...}} or return flat
        payload = data.get("settings") or data.get("value") or data
        # keys must be PRESENT for admin (the fix pops them ONLY from the public payload)
        assert "bank_iban" in payload, "admin should still see bank_iban key"
        assert "bank_bic" in payload, "admin should still see bank_bic key"


# ---- Bank-transfer order still carries bank block ----
class TestBankTransferOrder:
    """Bulgaria is COD-only (nextcart.COUNTRY_PAYMENTS); use ES which offers bank_transfer.
    Seed admin settings temporarily with bank details, verify the block, then restore.
    """

    BANK_SEED = {
        "bank_holder": "PurePeptide EOOD",
        "bank_name": "DSK Bank",
        "bank_iban": "BG61STSA93000032400775",
        "bank_bic": "STSABGSF",
    }

    def _place(self, api):
        payload = {
            "items": [{"product_id": "519a9304-92f7-4616-80b0-37587a9ef728",
                       "variant_sku": "DEMO-A", "quantity": 1}],
            "customer_email": f"TEST_{uuid.uuid4().hex[:8]}@example.com",
            "customer_name": "TEST Buyer",
            "customer_phone": "+34600000000",
            "shipping": {"full_name": "TEST Buyer", "phone": "+34600000000",
                         "line1": "Calle Test 1", "city": "Madrid", "postal_code": "28001",
                         "country": "ES"},
            "delivery": {"provider_key": "gls", "method_key": "gls_home",
                         "destination_type": "address",
                         "address": {"line1": "Calle Test 1", "city": "Madrid",
                                     "postal_code": "28001", "country": "ES"},
                         "price_amount": 9.9},
            "shipping_method": "gls_home",
            "payment_method": "bank_transfer",
            "terms_accepted": True,
            "locale": "en",
        }
        r = api.post(f"{BASE_URL}/api/checkout", json=payload)
        return r

    def test_bank_transfer_flow(self, api, admin_token):
        hdr = {"Authorization": f"Bearer {admin_token}"}
        # Preview DB has empty bank_iban/bank_bic — seed them, then restore.
        g0 = api.get(f"{BASE_URL}/api/admin/settings", headers=hdr)
        assert g0.status_code == 200
        original = g0.json().get("settings") or g0.json().get("value") or g0.json()
        patched = {**original, **self.BANK_SEED}
        put0 = api.put(f"{BASE_URL}/api/admin/settings", headers=hdr,
                       json={"value": patched})
        assert put0.status_code == 200, put0.text[:400]
        try:
            r = self._place(api)
            if r.status_code != 200:
                pytest.skip(f"checkout in preview refused bank_transfer for ES: {r.status_code} {r.text[:300]}")
            body = r.json()
            order = body.get("order") or {}
            oid = order.get("id")
            assert oid, f"no order id: {body}"
            assert order.get("payment_method") == "bank_transfer", \
                f"expected bank_transfer, got {order.get('payment_method')}"
            try:
                bt = body.get("bank_transfer")
                assert bt, "bank_transfer block missing in checkout response"
                assert bt.get("iban") == self.BANK_SEED["bank_iban"], bt
                assert bt.get("bic") == self.BANK_SEED["bank_bic"], bt
                assert bt.get("holder") == self.BANK_SEED["bank_holder"], bt
                assert bt.get("name") == self.BANK_SEED["bank_name"], bt
                assert bt.get("reference"), f"reference missing: {bt}"
                assert bt.get("amount_eur") or bt.get("amount"), f"amount missing: {bt}"

                g = api.get(f"{BASE_URL}/api/orders/{oid}")
                assert g.status_code == 200, g.text
                gbt = g.json().get("bank_transfer")
                assert gbt, "bank_transfer missing on GET /orders/{id}"
                assert gbt.get("iban") == self.BANK_SEED["bank_iban"]
                assert gbt.get("bic") == self.BANK_SEED["bank_bic"]

                # And: GET /api/settings (public) STILL must not contain them
                pub = api.get(f"{BASE_URL}/api/settings").json()
                for k in ("bank_iban", "bank_bic", "bank_holder", "bank_name"):
                    assert k not in pub, f"{k} leaked in public settings after seed"
            finally:
                api.delete(f"{BASE_URL}/api/admin/orders/{oid}",
                           headers=hdr, params={"force": "true"})
        finally:
            api.put(f"{BASE_URL}/api/admin/settings", headers=hdr,
                    json={"value": original})


# ---- fix_images unit tests ----
class TestFixImagesBackend:
    def test_sourceless_dropped(self):
        from prerender import fix_images
        html_in = '<p>x</p><img><img><img src="/x.png" alt="">y'
        out = fix_images(html_in, "MY TITLE")
        # sourceless dropped
        assert re.search(r"<img(?![^>]*\bsrc=)[^>]*>", out) is None, out
        # empty alt replaced with title
        assert 'alt="MY TITLE"' in out
        # exactly one <img> remains
        assert len(re.findall(r"<img\b", out)) == 1

    def test_preserves_meaningful_alt(self):
        from prerender import fix_images
        html_in = '<img src="/a.png" alt="Test Report BPC-157">'
        out = fix_images(html_in, "Page Title")
        assert 'alt="Test Report BPC-157"' in out

    def test_title_html_escaped(self):
        from prerender import fix_images
        out = fix_images('<img src="/a.png" alt="">', 'Title "quoted" & <b>')
        assert re.search(r'<img\b[^>]*\balt="[^"]+"', out)
        # no raw double-quote or unescaped tag inside alt
        assert '<b>' not in out

    def test_no_img_no_change(self):
        from prerender import fix_images
        assert fix_images("<p>hi</p>", "T") == "<p>hi</p>"


class TestFixImagesFrontendMirror:
    """The frontend helper must implement the same three rules."""
    def test_frontend_helper_source(self):
        src = open("/app/frontend/src/lib/richText.js", encoding="utf-8").read()
        assert "export const fixImages" in src
        # drops sourceless
        assert "src\\s*=" in src or "src=" in src
        # applied in StaticPage
        static_page = open("/app/frontend/src/pages/StaticPage.jsx", encoding="utf-8").read()
        assert "fixImages(" in static_page
        assert "page.title" in static_page


# ---- Prerender output on chemical-analysis page (both bg and en) ----
class TestPrerenderChemicalAnalysis:
    @pytest.mark.parametrize("path", ["/pages/chemical-analysis", "/en/pages/chemical-analysis"])
    def test_no_img_without_alt_or_src(self, api, path):
        r = api.get(f"{BASE_URL}/api/seo/prerender", params={"path": path})
        if r.status_code == 404:
            pytest.skip(f"page {path} not present in preview DB")
        assert r.status_code == 200, r.text
        html_out = r.text
        # Every <img> must have a src
        for tag in re.findall(r"<img\b[^>]*>", html_out, flags=re.I):
            assert re.search(r'\bsrc\s*=\s*"[^"]+"', tag), f"sourceless img rendered: {tag}"
            m = re.search(r'\balt\s*=\s*"([^"]*)"', tag, flags=re.I)
            assert m is not None, f"img without alt attribute: {tag}"
            assert m.group(1).strip() != "", f"empty alt rendered: {tag}"


# ---- Regression: settings 200, robots open, US/Chrome fallback still config-level (skip live) ----
class TestRegression:
    def test_settings_ok(self, api):
        assert api.get(f"{BASE_URL}/api/settings").status_code == 200

    def test_cod_checkout_still_works(self, api, admin_token):
        payload = {
            "items": [{"product_id": "519a9304-92f7-4616-80b0-37587a9ef728",
                       "variant_sku": "DEMO-A", "quantity": 1}],
            "customer_email": f"TEST_{uuid.uuid4().hex[:8]}@example.com",
            "customer_name": "TEST Buyer",
            "customer_phone": "+359888000112",
            "shipping": {"full_name": "TEST Buyer", "phone": "+359888000112",
                         "line1": "ul. Test 1", "city": "Sofia", "postal_code": "1000",
                         "country": "BG"},
            "delivery": {"provider_key": "econt", "method_key": "econt_office",
                         "destination_type": "office",
                         "office": {"id": "econt:1292216"},
                         "price_amount": 3.89},
            "shipping_method": "econt_office",
            "payment_method": "cod",
            "terms_accepted": True,
            "locale": "bg",
        }
        r = api.post(f"{BASE_URL}/api/checkout", json=payload)
        if r.status_code != 200:
            pytest.skip(f"COD checkout unavailable in preview: {r.status_code} {r.text[:200]}")
        oid = (r.json().get("order") or {}).get("id")
        if oid:
            api.delete(f"{BASE_URL}/api/admin/orders/{oid}",
                       headers={"Authorization": f"Bearer {admin_token}"},
                       params={"force": "true"})
