import uuid

from sqlmodel import Session as SQLSession, select

from app.db import engine
from app.models import WorkoutOffer, WorkoutParticipant
from tests.test_auth import signup


def _unique_user():
    token = uuid.uuid4().hex[:8]
    return f"user_{token}", f"{token}@test.com"


def _create_offer(client, max_participants=3):
    r = client.post(
        "/offers",
        data={
            "sport": "running",
            "location": "SFU Burnaby",
            "scheduled_at": "2026-09-25T18:00",
            "description": "Evening run",
            "max_participants": str(max_participants),
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    with SQLSession(engine) as session:
        offer = session.exec(
            select(WorkoutOffer).order_by(WorkoutOffer.id.desc())
        ).first()
        assert offer is not None
        return int(offer.id)


def test_create_offer_requires_login(client):
    r = client.post(
        "/offers",
        data={
            "sport": "running",
            "location": "SFU Burnaby",
            "scheduled_at": "2026-09-25T18:00",
            "max_participants": "3",
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_creator_is_added_as_participant(client):
    username, email = _unique_user()
    signup(client, username=username, email=email)

    offer_id = _create_offer(client)

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        assert len(participants) == 1


def test_user_can_join_and_leave_offer(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    offer_id = _create_offer(client)

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)

    r = client.post(
        f"/offers/{offer_id}/join",
        follow_redirects=False,
    )

    assert r.status_code == 303

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        assert len(participants) == 2

    r = client.post(
        f"/offers/{offer_id}/leave",
        follow_redirects=False,
    )

    assert r.status_code == 303

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        assert len(participants) == 1


def test_duplicate_join_does_not_add_second_participant(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    offer_id = _create_offer(client)

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)

    client.post(f"/offers/{offer_id}/join")
    client.post(f"/offers/{offer_id}/join")

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        assert len(participants) == 2


def test_full_offer_rejects_additional_user(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    offer_id = _create_offer(client, max_participants=2)

    client.get("/logout")

    user1_name, user1_email = _unique_user()
    signup(client, username=user1_name, email=user1_email)
    client.post(f"/offers/{offer_id}/join")

    client.get("/logout")

    user2_name, user2_email = _unique_user()
    signup(client, username=user2_name, email=user2_email)
    client.post(f"/offers/{offer_id}/join")

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        assert len(participants) == 2