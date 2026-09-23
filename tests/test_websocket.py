import uuid

from sqlmodel import Session as SQLSession, select

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

    # Opening /chat lazily creates the workout's chat room
    response = client.get("/chat")

    assert response.status_code == 200

    with SQLSession(engine) as session:
        room = session.exec(
            select(ChatRoom).where(
                ChatRoom.offer_id == offer_id
            )
        ).first()

        assert room is not None
        room_id = room.id

    # Create another user and join the workout
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

    # Joined participant can open the workout chat
    response = client.get(
        f"/chat/{room_id}",
        follow_redirects=False,
    )

    assert response.status_code == 200

    # Participant can connect to the workout WebSocket
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

    # Message should also be persisted in the database
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

    # Opening /chat creates the workout's chat room
    response = client.get("/chat")
    assert response.status_code == 200

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

def test_participant_can_open_chat_from_workout(client):
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