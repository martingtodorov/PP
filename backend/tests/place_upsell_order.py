"""Create a COD order via /api/checkout and print the returned order_id."""
import os, sys, requests
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE = os.environ["PUBLIC_SITE_URL"].rstrip("/")

payload = {
    "items": [{"product_id": "519a9304-92f7-4616-80b0-37587a9ef728",
               "variant_sku": "DEMO-A", "quantity": 1}],
    "customer_email": "iter67upsell@example.com",
    "customer_name": "Iter67 Buyer",
    "customer_phone": "+359888111222",
    "shipping": {"full_name": "Iter67 Buyer", "phone": "+359888111222",
                 "line1": "Test 1", "city": "София", "postal_code": "1000",
                 "country": "BG"},
    "payment_method": "cod",
    "shipping_method": "econt_office",
    "delivery": {"provider_key": "econt", "method_key": "econt_office",
                 "destination_type": "office",
                 "office": {"id": "econt:1292216", "name": "Econt Test",
                            "address": "тест", "city": "София"},
                 "price_amount": 3.89},
    "terms_accepted": True,
    "locale": "bg",
}
r = requests.post(f"{BASE}/api/checkout", json=payload,
                  headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                  timeout=60)
print("STATUS", r.status_code)
if r.status_code >= 400:
    print(r.text[:500]); sys.exit(1)
d = r.json()
oid = d.get("order_id") or (d.get("order") or {}).get("id") or d.get("id")
print("ORDER_ID", oid)
