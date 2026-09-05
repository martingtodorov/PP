"""SEO tags: metadata only — never a word of them on the page, never in the public API."""
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
TAGS = ["ретатрутид", "отслабване пептид", "retatrutide bulgaria"]


def _admin():
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": os.environ["ADMIN_EMAIL"],
                                      "password": os.environ["ADMIN_PASSWORD"]},
           timeout=20).raise_for_status()
    return s


def test_tags_reach_the_metadata_but_not_the_page():
    s = _admin()
    prod = next(p for p in s.get(f"{API}/admin/products", timeout=20).json()["products"]
                if p.get("active", True))
    full = s.get(f"{API}/admin/products/{prod['id']}", timeout=20).json()["product"]
    payload = {k: v for k, v in full.items() if k not in ("id", "created_at", "base_handle", "handles")}
    original = full.get("admin_tags") or []
    try:
        payload["admin_tags"] = TAGS
        assert s.put(f"{API}/admin/products/{prod['id']}", json=payload, timeout=30).status_code == 200

        listed = requests.get(f"{API}/products", timeout=20).json()["products"]
        handle = next(p["handle"] for p in listed if p.get("base_handle") == full["handle"])
        page = requests.get(f"{API}/seo/prerender", params={"path": f"/products/{handle}"},
                            headers={"Host": "purepeptide.bg"}, timeout=30).text
        head, body = page.split("</head>", 1)

        assert f'<meta name="keywords" content="{", ".join(TAGS)}">' in head
        assert f'"keywords": "{", ".join(TAGS)}"' in head          # inside the Product JSON-LD
        for tag in TAGS:
            assert tag not in body                                 # nothing visible to a human

        llms = requests.get(f"{API}/llms.txt", headers={"Host": "purepeptide.bg"}, timeout=30).text
        assert f"(keywords: {', '.join(TAGS)})" in llms            # AI crawlers get them too
        assert all("admin_tags" not in p for p in listed)
    finally:
        payload["admin_tags"] = original
        s.put(f"{API}/admin/products/{prod['id']}", json=payload, timeout=30)


def test_renaming_a_collection_handle_moves_the_live_url():
    """The bug: a rotated collection is published under translations[bg].handle, so editing the
    handle in the admin changed nothing on the site."""
    s = _admin()
    col = next(c for c in s.get(f"{API}/admin/collections", timeout=20).json()["collections"]
               if (c.get("rotations") or []) and c.get("link_key") != "catalog")
    old_base = col["handle"]
    live_before = ((col.get("translations") or {}).get("bg") or {}).get("handle") or old_base
    new_handle = f"{old_base}-qa1"
    payload = {k: v for k, v in col.items() if k not in ("id", "rotations")}
    try:
        payload["handle"] = new_handle
        assert s.put(f"{API}/admin/collections/{col['id']}", json=payload, timeout=30).status_code == 200
        assert requests.get(f"{API}/collections/{new_handle}", timeout=20).status_code == 200
        assert requests.get(f"{API}/collections/{live_before}", timeout=20).status_code == 404
        assert requests.get(f"{API}/seo/prerender", params={"path": f"/collections/{new_handle}"},
                            headers={"Host": "purepeptide.bg"}, timeout=30).status_code == 200
    finally:
        payload["handle"] = old_base
        s.put(f"{API}/admin/collections/{col['id']}", json=payload, timeout=30)


def test_a_missing_url_is_a_hard_404_that_still_points_home_to_the_catalogue():
    r = requests.get(f"{API}/seo/prerender", params={"path": "/collections/nope-nope"},
                     headers={"Host": "purepeptide.bg"}, timeout=30)
    assert r.status_code == 404
    assert 'http-equiv="refresh"' in r.text and "/collections/" in r.text
    assert "noindex" in r.text


def test_the_catalogue_survives_a_handle_change():
    """The catch-all collection is found by link_key, so it still lists every product."""
    s = _admin()
    col = next(c for c in s.get(f"{API}/admin/collections", timeout=20).json()["collections"]
               if c.get("link_key") == "catalog")
    live = ((col.get("translations") or {}).get("bg") or {}).get("handle") or col["handle"]
    data = requests.get(f"{API}/collections/{live}", timeout=20).json()
    total = len(requests.get(f"{API}/products", params={"limit": 500}, timeout=20).json()["products"])
    assert len(data["products"]) == total and total > 0
    assert requests.get(f"{API}/links", timeout=20).json()["catalog"] == f"/collections/{live}"
