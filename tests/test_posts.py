# tests/test_posts.py
from pathlib import Path

def signup_and_login(client, username="user02", email="u2@test.com", password="Passw0rd!"):
    client.post("/signup", data={"username": username, "email": email, "password": password}, follow_redirects=False)
    r = client.post("/login", data={"email": email, "password": password}, follow_redirects=False)
    if r.status_code == 422:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    return client

def test_create_post_text(client):
    signup_and_login(client)
    r = client.post("/posts/new", data={"caption": "hello"}, follow_redirects=False)
    assert r.status_code in (200, 302, 303)

def test_create_post_with_image(client, tmp_path: Path):
    signup_and_login(client)
    img_path = tmp_path / "x.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    with img_path.open("rb") as f:
        r = client.post(
            "/posts/new",
            data={"caption": "with image"},
            files={"image": ("x.png", f, "image/png")},
            follow_redirects=False,
        )
    assert r.status_code in (200, 302, 303)
