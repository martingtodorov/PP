"""The admin session lasts 90 days, and a password change kills every old session."""
import os
from datetime import datetime, timezone

import jwt
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
API = "http://localhost:8001/api"
CREDS = {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}


def test_the_login_lasts_ninety_days():
    r = requests.post(f"{API}/auth/login", json=CREDS, timeout=20)
    assert r.status_code == 200
    claims = jwt.decode(r.json()["token"], options={"verify_signature": False})
    days = (datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(timezone.utc)).days
    assert 88 <= days <= 90, days
    cookie = r.headers.get("set-cookie", "")
    assert "pp_token=" in cookie and "Max-Age=7776000" in cookie and "HttpOnly" in cookie


def test_a_token_from_another_password_is_refused():
    """The `pv` claim pins the token to the password hash it was issued with."""
    import server

    token = server.create_token("whoever", CREDS["email"], "admin", password_hash="old-hash")
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert me.json()["user"] is None                     # /auth/me is soft: no user, no session
    protected = requests.get(f"{API}/admin/orders", params={"limit": 1},
                             headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert protected.status_code in (401, 403)


def test_the_current_token_still_opens_the_admin():
    token = requests.post(f"{API}/auth/login", json=CREDS, timeout=20).json()["token"]
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert me.status_code == 200 and me.json()["user"]["role"] == "admin"
    orders = requests.get(f"{API}/admin/orders", params={"limit": 1},
                          headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert orders.status_code == 200
