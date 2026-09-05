"""Internal product tags stay in the admin, and a delisted collection disappears from the site."""
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"


def _admin():
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"],
                                      "password": os.environ["ADMIN_PASSWORD"]},
           timeout=20).raise_for_status()
    return s


def test_the_owner_can_tag_a_product_and_the_customer_never_sees_it():
    s = _admin()
    # an active product, so the storefront checks below have something to look at
    prod = next(p for p in s.get(f"{API}/admin/products", timeout=20).json()["products"]
                if p.get("active", True))
    full = s.get(f"{API}/admin/products/{prod['id']}", timeout=20).json()["product"]
    original = full.get("admin_tags") or []
    payload = {k: v for k, v in full.items()
               if k not in ("id", "created_at", "base_handle", "handles")}
    try:
        payload["admin_tags"] = ["топ маржин", "поръчай пак"]
        assert s.put(f"{API}/admin/products/{prod['id']}", json=payload, timeout=30).status_code == 200

        back = s.get(f"{API}/admin/products/{prod['id']}", timeout=20).json()["product"]
        assert back["admin_tags"] == ["топ маржин", "поръчай пак"]

        listed = requests.get(f"{API}/products", timeout=20).json()["products"]
        assert all("admin_tags" not in p for p in listed)
        # the storefront URL can be a rotated handle, so take it from the public listing
        handle = next(p["handle"] for p in listed if p.get("base_handle") == back["handle"])
        public = requests.get(f"{API}/products/{handle}", timeout=20).json()["product"]
        assert "admin_tags" not in public
        page = requests.get(f"{API}/seo/prerender", params={"path": f"/products/{handle}"},
                            headers={"Host": "purepeptide.bg"}, timeout=30)
        assert "топ маржин" not in page.text
    finally:
        payload["admin_tags"] = original
        s.put(f"{API}/admin/products/{prod['id']}", json=payload, timeout=30)


def test_a_delisted_collection_is_off_the_storefront():
    s = _admin()
    col = next(c for c in s.get(f"{API}/admin/collections", timeout=20).json()["collections"]
               if c["handle"] not in ("2all-the-peptides-1", "all-peptides"))
    try:
        r = s.patch(f"{API}/admin/collections/{col['id']}/delisted", json={"delisted": True}, timeout=20)
        assert r.status_code == 200 and r.json()["delisted"] is True

        assert requests.get(f"{API}/collections/{col['handle']}", timeout=20).status_code == 404
        listed = requests.get(f"{API}/collections", timeout=20).json()["collections"]
        assert col["handle"] not in [c.get("base_handle") for c in listed]
        sitemap = requests.get(f"{API}/sitemap_collections_1.xml", headers={"Host": "purepeptide.bg"},
                               timeout=30).text
        assert f"/collections/{col['handle']}" not in sitemap
        # the admin still sees it, so it can be brought back
        assert any(c["handle"] == col["handle"]
                   for c in s.get(f"{API}/admin/collections", timeout=20).json()["collections"])
    finally:
        s.patch(f"{API}/admin/collections/{col['id']}/delisted", json={"delisted": False}, timeout=20)
    listed = requests.get(f"{API}/collections", timeout=20).json()["collections"]
    assert col["handle"] in [c.get("base_handle") for c in listed]     # brought back with one click


def test_the_daily_report_renders_with_the_numbers_and_the_traffic_sources():
    import asyncio

    import email_templates as et
    import server

    day = __import__("datetime").datetime.now(server.SHOP_TZ).date() - __import__("datetime").timedelta(days=1)
    data = asyncio.get_event_loop().run_until_complete(server._report_payload(day)) \
        if False else asyncio.run(server._report_payload(day))
    subject, html = et.render_admin_daily_report(data)
    assert day.strftime("%d.%m.%Y") in subject or "поръчки" in subject
    for label in ("Продажби", "Поръчки", "Сесии", "Посетители", "ДНЕВЕН ОТЧЕТ"):
        assert label in html
    assert "ЕООД" not in html and "ЕИК" not in html
