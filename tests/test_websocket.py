import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLSession, select
from starlette.websockets import WebSocketDisconnect

from app.db import engine
from app.models import ChatRoom, Message
from tests.test_auth import signup
from tests.test_offers import _create_offer


def _unique_user():
    token = uuid.uuid4().hex[:8]
    return f"user_{token}", f"{token}@test.com"


def test_workout_chat_websocket(client):
    # Create workout host
    creator_name, creator_email = _unique_user()

    signup(
        client,
        username=creator_name,
        email=creator_email,
    )

    offer_id = _create_offer(client)

    with SQLSession(engine) as session:
        room = session.exec(
            select(ChatRoom).where(
                ChatRoom.offer_id == offer_id
            )
        ).first()

        assert room is not None
        room_id = room.id

    response = client.get(f"/chat/{room_id}", follow_redirects=False)
    assert response.status_code == 200

    client.get("/logout")

    participant_name, participant_email = _unique_user()

    signup(
        client,
        username=participant_name,
        email=participant_email,
    )

    client.post(
        f"/offers/{offer_id}/join",
        follow_redirects=False,
    )

    with client.websocket_connect(
        f"/ws/chat/{room_id}"
    ) as websocket:
        websocket.send_json(
            {
                "content": "Ready for the workout!"
            }
        )

        data = websocket.receive_json()

        assert data["type"] == "text"
        assert data["content"] == "Ready for the workout!"
        assert data["sender_name"] == participant_name

    with SQLSession(engine) as session:
        message = session.exec(
            select(Message).where(
                Message.room_id == room_id
            )
        ).first()

        assert message is not None
        assert message.content == "Ready for the workout!"

def test_non_participant_cannot_access_workout_chat(client):
    # Create workout host
    creator_name, creator_email = _unique_user()

    signup(
        client,
        username=creator_name,
        email=creator_email,
    )

    offer_id = _create_offer(client)

    with SQLSession(engine) as session:
        room = session.exec(
            select(ChatRoom).where(
                ChatRoom.offer_id == offer_id
            )
        ).first()

        assert room is not None
        room_id = room.id

    # Log out the host
    client.get("/logout")

    # Create a new user who has NOT joined the workout
    outsider_name, outsider_email = _unique_user()

    signup(
        client,
        username=outsider_name,
        email=outsider_email,
    )

    # Outsider should not be allowed into the chat
    response = client.get(
        f"/chat/{room_id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/chat"

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/chat/{room_id}"):
            pass


def test_ws_payload_includes_server_sender_name(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)
    offer_id = _create_offer(client)

    client.get("/logout")
    participant_name, participant_email = _unique_user()
    signup(client, username=participant_name, email=participant_email)
    client.post(f"/offers/{offer_id}/join", follow_redirects=False)

    with SQLSession(engine) as session:
        room = session.exec(select(ChatRoom).where(ChatRoom.offer_id == offer_id)).first()
        assert room is not None
        room_id = room.id

    with client.websocket_connect(f"/ws/chat/{room_id}") as websocket:
        websocket.send_json({"content": "hello from websocket"})
        payload = websocket.receive_json()

    assert payload["type"] == "text"
    assert payload["sender_name"] == participant_name
    assert payload["sender_id"] is not None


def test_chat_redirects_to_most_recent_conversation(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    first_offer_id = _create_offer(client, scheduled_at="2026-09-25T18:00")
    with SQLSession(engine) as session:
        first_room = session.exec(select(ChatRoom).where(ChatRoom.offer_id == first_offer_id)).first()
        assert first_room is not None

    client.post(f"/offers/{first_offer_id}/join", follow_redirects=False)
    client.get("/logout")

    second_user_name, second_user_email = _unique_user()
    signup(client, username=second_user_name, email=second_user_email)
    second_offer_id = _create_offer(client, scheduled_at="2026-09-26T18:00")
    with SQLSession(engine) as session:
        second_room = session.exec(select(ChatRoom).where(ChatRoom.offer_id == second_offer_id)).first()
        assert second_room is not None

    client.post(f"/offers/{second_offer_id}/join", follow_redirects=False)

    with SQLSession(engine) as session:
        room = session.exec(select(ChatRoom).where(ChatRoom.offer_id == second_offer_id)).first()
        assert room is not None
        session.add(
            Message(
                room_id=room.id,
                sender_id=client.session_context.get("uid") if hasattr(client, "session_context") else 1,
                content="Latest update",
            )
        )
        session.commit()

    r = client.get("/chat", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/chat/{second_room.id}"


def test_chat_empty_state_renders_find_workouts_link(client):
    username, email = _unique_user()
    signup(client, username=username, email=email)

    response = client.get("/chat")
    assert response.status_code == 200
    text = response.text
    assert "Find workouts" in text or "Find a workout" in text


def test_image_upload_requires_participant_and_rejects_invalid_types(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)
    offer_id = _create_offer(client)

    with SQLSession(engine) as session:
        room = session.exec(select(ChatRoom).where(ChatRoom.offer_id == offer_id)).first()
        assert room is not None
        room_id = room.id

    client.get("/logout")

    participant_name, participant_email = _unique_user()
    signup(client, username=participant_name, email=participant_email)
    client.post(f"/offers/{offer_id}/join", follow_redirects=False)

    valid = client.post(
        f"/chat/{room_id}/image",
        files={"image": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        follow_redirects=False,
    )
    assert valid.status_code == 303

    invalid = client.post(
        f"/chat/{room_id}/image",
        files={"image": ("note.txt", b"hello world", "text/plain")},
        follow_redirects=False,
    )
    assert invalid.status_code == 400

    with SQLSession(engine) as session:
        msgs = session.exec(select(Message).where(Message.room_id == room_id)).all()
        assert len(msgs) == 1
        assert msgs[0].image_url is not None
    creator_name, creator_email = _unique_user()

    signup(
        client,
        username=creator_name,
        email=creator_email,
    )

    offer_id = _create_offer(client)

    response = client.get(
        f"/offers/{offer_id}/chat",
        follow_redirects=False,
    )

    assert response.status_code == 303

    with SQLSession(engine) as session:
        room = session.exec(
            select(ChatRoom).where(
                ChatRoom.offer_id == offer_id
            )
        ).first()

        assert room is not None
        assert response.headers["location"] == f"/chat/{room.id}"