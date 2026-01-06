# tests/test_websocket.py
import json
import re
import uuid

from sqlmodel import Session as SQLSession, select

from app.db import engine
from app.models import User
from tests.test_auth import signup, login

def get_user_id_by_email(email: str) -> int:
    with SQLSession(engine) as s:
        u = s.exec(select(User).where(User.email == email)).first()
        assert u is not None, f"User not found in DB for email={email}"
        return int(u.id)

def test_websocket_connect(client):
    pw = "Passw0rd!"

    u1 = uuid.uuid4().hex[:8]
    u2 = uuid.uuid4().hex[:8]
    email1 = f"{u1}@test.com"
    email2 = f"{u2}@test.com"

    # create 2 users
    r = signup(client, username=u1, email=email1, password=pw)
    assert r.status_code in (200, 302, 303, 409)
    r = signup(client, username=u2, email=email2, password=pw)
    assert r.status_code in (200, 302, 303, 409)

    me_id = get_user_id_by_email(email1)
    other_id = get_user_id_by_email(email2)

    # login as user1 (sets session cookie)
    r = login(client, username=u1, email=email1, password=pw)
    assert r.status_code in (200, 302, 303)

    # create/get room: /chat/start requires user_id Form(...)
    r = client.post("/chat/start", data={"user_id": other_id}, follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    assert re.match(r"^/chat/\d+$", loc), f"Unexpected redirect location: {loc}"
    room_id = int(loc.split("/")[-1])

    # websocket expects JSON text with sender_id + content
    with client.websocket_connect(f"/ws/chat/{room_id}") as ws:
        ws.send_text(json.dumps({"sender_id": me_id, "content": "hello"}))
        ws.close()
