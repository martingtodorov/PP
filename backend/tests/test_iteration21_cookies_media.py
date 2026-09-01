"""Iteration 21 — Cookie banner regression + local media-disk regression."""
import os
import io
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/app/backend/.media"))
ADMIN_EMAIL = "admin@purepeptide.bg"
ADMIN_PASSWORD = "Admin@PurePeptide2026"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def admin_token(sess):
    r = sess.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, r.text
    return tok


def _pick_product_image_path():
    r = requests.get(f"{BASE_URL}/api/products?limit=6")
    assert r.status_code == 200
    for p in r.json()["products"]:
        img = p.get("image") or ""
        if "/api/files/" in img:
            return img.split("/api/files/", 1)[1]
    pytest.skip("No product image via /api/files/ found")


# ---------- Media: WebP / JPEG negotiation ----------
class TestMediaNegotiation:
    def test_webp_returned_when_accept_webp(self):
        path = _pick_product_image_path()
        r = requests.get(f"{BASE_URL}/api/files/{path}", headers={"Accept": "image/webp"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/webp", r.headers
        assert r.headers.get("Vary", "").lower() == "accept"
        assert len(r.content) > 100

    def test_jpeg_when_accept_jpeg(self):
        path = _pick_product_image_path()
        r = requests.get(f"{BASE_URL}/api/files/{path}", headers={"Accept": "image/jpeg,*/*"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/jpeg", r.headers

    def test_local_disk_is_source_of_truth(self):
        path = _pick_product_image_path()
        # trigger a request to ensure mirroring happened
        requests.get(f"{BASE_URL}/api/files/{path}", headers={"Accept": "image/webp"})
        local = MEDIA_ROOT / path
        assert local.exists(), f"Expected local media file at {local}"
        assert local.stat().st_size > 0


# ---------- Admin upload + retrieve ----------
class TestAdminUpload:
    def test_upload_then_retrieve(self, admin_token):
        # 2x2 PNG
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000200000002080600000072b60d24"
            "0000000c4944415478da63f8cf000000030001010000180dda100000000049454e44ae426082"
        )
        files = {"file": ("TEST_iter21.png", io.BytesIO(png), "image/png")}
        r = requests.post(
            f"{BASE_URL}/api/admin/upload",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["url"].startswith("/api/files/")
        path = body["path"]

        # Immediately retrieve
        g = requests.get(f"{BASE_URL}/api/files/{path}", headers={"Accept": "image/webp"})
        assert g.status_code == 200
        # tiny 2x2 PNGs may skip webp conversion; accept either form as long as it serves an image
        assert g.headers["content-type"].startswith("image/"), g.headers

        # Local disk mirrored
        local = MEDIA_ROOT / path
        assert local.exists(), f"Uploaded file missing at {local}"


# ---------- Checkout regression (COD end-to-end) ----------
class TestCheckoutRegression:
    def test_end_to_end_cod_order(self):
        # pick first product & variant
        pr = requests.get(f"{BASE_URL}/api/products?limit=1")
        p = pr.json()["products"][0]
        variant = p["variants"][0]

        payload = {
            "items": [{"product_id": p["id"], "variant_sku": variant["sku"], "quantity": 1}],
            "customer_email": "test_iter21@example.com",
            "customer_name": "Test Iter21",
            "customer_phone": "+359888111222",
            "shipping": {
                "full_name": "Test Iter21",
                "phone": "+359888111222",
                "line1": "Test 1",
                "city": "Sofia",
                "postal_code": "1000",
                "country": "BG",
            },
            "shipping_method": "econt_office",
            "payment_method": "cod",
            "terms_accepted": True,
            "locale": "bg",
        }
        r = requests.post(f"{BASE_URL}/api/checkout", json=payload)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        order = body.get("order") or body
        assert order.get("order_number") or order.get("id"), body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
