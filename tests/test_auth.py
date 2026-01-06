# tests/test_auth.py

def signup(client, username="user01", email="u1@test.com", password="Passw0rd!"):
    r = client.post(
        "/signup",
        data={"username": username, "email": email, "password": password},
        follow_redirects=False,
    )
    assert r.status_code in (200, 302, 303)
    return r

def login(client, username="user01", email="u1@test.com", password="Passw0rd!"):
    r = client.post("/login", data={"email": email, "password": password}, follow_redirects=False)
    if r.status_code == 422:
        r = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert r.status_code in (200, 302, 303)
    return r

def test_health_or_home(client):
    r = client.get("/")
    assert r.status_code in (200, 302)

def test_signup_login_sets_cookie(client):
    signup(client)
    r = login(client)

    cookie_header = (r.headers.get("set-cookie", "") or "").lower()
    # SessionMiddleware에서 session_cookie="sweatmarket_session" 이라면 이게 가장 정확
    assert "sweatmarket_session" in cookie_header or "session" in cookie_header

def test_protected_requires_auth(client):
    r = client.get("/profile", follow_redirects=False)
    assert r.status_code in (302, 401, 403)
