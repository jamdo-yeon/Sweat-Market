# tests/test_wallet_dex.py
import uuid

from tests.test_auth import signup


def _unique_user():
    token = uuid.uuid4().hex[:8]
    return f"user_{token}", f"{token}@test.com"


def test_posts_new_requires_login(client):
    r = client.get("/posts/new", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert (r.headers.get("location") or "").startswith("/login")


def test_logout_clears_session(client):
    username, email = _unique_user()
    signup(client, username=username, email=email, password="Passw0rd!")

    r = client.get("/profile", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert (r.headers.get("location") or "").startswith("/profile/edit")

    r = client.post("/logout", follow_redirects=False)
    assert r.status_code in (302, 303)

    r = client.get("/profile", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert (r.headers.get("location") or "").startswith("/login")


def test_wallet_demo_mode(client):
    r = client.get("/wallet?demo=1")
    assert r.status_code == 200
    assert "Meetup demo" in r.text


def test_dex_demo_mode(client):
    r = client.get("/dex?demo=1")
    assert r.status_code == 200
    assert any(price in r.text for price in ["96", "98", "100", "101", "103", "104", "106", "108", "110"])


def test_dex_create_order_persists(client):
    username, email = _unique_user()
    signup(client, username=username, email=email, password="Passw0rd!")

    r = client.post(
        "/dex/new",
        data={"side": "buy", "price": "123", "amount": "7"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)

    r = client.get("/dex")
    assert r.status_code == 200
    assert "123" in r.text
