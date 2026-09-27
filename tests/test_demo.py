from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from app.auth import pwd
from app.db import engine
from app.demo import cleanup_obsolete_test_data, seed_demo_data
from app.main import app
from app.models import ChatRoom, Message, User, WorkoutOffer, WorkoutParticipant
from tests.test_auth import signup


VANCOUVER = ZoneInfo("America/Vancouver")
FIXED_NOW = datetime(2026, 9, 26, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def demo_client(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with TestClient(app) as client:
        yield client


def _seed() -> None:
    with Session(engine) as session:
        seed_demo_data(session, now=FIXED_NOW)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_seed_creates_demo_users_and_workouts(client):
    _seed()

    with Session(engine) as session:
        engineering = session.exec(
            select(User).where(User.username == "engineering_student")
        ).one()
        cs_student = session.exec(
            select(User).where(User.username == "cs_student")
        ).one()
        gym_buddy = session.exec(
            select(WorkoutOffer).where(WorkoutOffer.title == "Gym Buddy")
        ).one()
        morning_run = session.exec(
            select(WorkoutOffer).where(WorkoutOffer.title == "Morning Run")
        ).one()

        assert engineering.nickname == "Engineering Student"
        assert engineering.coins == 30
        assert pwd.identify(engineering.password_hash) == "argon2"
        assert cs_student.nickname == "CS Student"
        assert cs_student.coins == 20
        assert pwd.identify(cs_student.password_hash) == "argon2"
        assert gym_buddy.creator_id == engineering.id
        assert morning_run.creator_id == cs_student.id


def test_seed_is_idempotent(client):
    _seed()
    _seed()

    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                User.username.in_(["engineering_student", "cs_student"])
            )
        ).all()
        offers = session.exec(
            select(WorkoutOffer).where(
                WorkoutOffer.title.in_(["Gym Buddy", "Morning Run"])
            )
        ).all()
        participants = session.exec(select(WorkoutParticipant)).all()
        rooms = session.exec(select(ChatRoom)).all()

        assert len(users) == 2
        assert len(offers) == 2
        assert len(participants) == 3
        assert len(rooms) == 2


def test_cleanup_removes_only_obsolete_test_workout_graph(client):
    _seed()

    with Session(engine) as session:
        old_user = User(
            username="user_oldfixture",
            email="oldfixture@test.com",
            password_hash=pwd.hash("Passw0rd!"),
            is_active=True,
        )
        session.add(old_user)
        session.flush()

        old_offer = WorkoutOffer(
            creator_id=int(old_user.id),
            title="Test Workout",
            sport="running",
            location="Simon Fraser University — Burnaby, BC",
            latitude=49.2781,
            longitude=-122.9199,
            scheduled_at=FIXED_NOW,
            description="Evening run",
            max_participants=3,
        )
        session.add(old_offer)
        session.flush()

        participant = WorkoutParticipant(
            offer_id=int(old_offer.id),
            user_id=int(old_user.id),
        )
        room = ChatRoom(offer_id=int(old_offer.id))
        session.add(participant)
        session.add(room)
        session.flush()
        session.add(
            Message(
                room_id=int(room.id),
                sender_id=int(old_user.id),
                content="obsolete test message",
            )
        )
        session.commit()

        deleted = cleanup_obsolete_test_data(session)
        session.commit()

        remaining_titles = {
            offer.title for offer in session.exec(select(WorkoutOffer)).all()
        }
        assert deleted == {
            "offers": 1,
            "participants": 1,
            "rooms": 1,
            "messages": 1,
            "users": 1,
        }
        assert "Test Workout" not in remaining_titles
        assert {"Gym Buddy", "Morning Run"}.issubset(remaining_titles)
        assert session.exec(
            select(User).where(User.username == "engineering_student")
        ).one()
        assert session.exec(
            select(User).where(User.username == "cs_student")
        ).one()


def test_demo_workouts_have_expected_owners(client):
    _seed()

    with Session(engine) as session:
        engineering = session.exec(
            select(User).where(User.username == "engineering_student")
        ).one()
        cs_student = session.exec(
            select(User).where(User.username == "cs_student")
        ).one()
        gym_buddy = session.exec(
            select(WorkoutOffer).where(WorkoutOffer.title == "Gym Buddy")
        ).one()
        morning_run = session.exec(
            select(WorkoutOffer).where(WorkoutOffer.title == "Morning Run")
        ).one()

        assert gym_buddy.creator_id == engineering.id
        assert morning_run.creator_id == cs_student.id


def test_morning_run_is_future_730_vancouver_time(client):
    _seed()

    with Session(engine) as session:
        morning_run = session.exec(
            select(WorkoutOffer).where(WorkoutOffer.title == "Morning Run")
        ).one()
        local_time = _as_utc(morning_run.scheduled_at).astimezone(VANCOUVER)

        assert local_time > FIXED_NOW.astimezone(VANCOUVER)
        assert (local_time.hour, local_time.minute) == (7, 30)


def test_demo_mode_disabled_does_not_seed_automatically(client):
    client.get("/")

    with Session(engine) as session:
        assert session.exec(select(User)).all() == []
        assert session.exec(select(WorkoutOffer)).all() == []


def test_demo_mode_auto_logs_in_unauthenticated_visitor(demo_client):
    response = demo_client.get("/")
    offers_response = demo_client.get("/offers")

    assert response.status_code == 200
    assert "Let’s start strong," in response.text
    assert "Engineering Student." in response.text
    assert offers_response.status_code == 200
    assert "Gym Buddy" in offers_response.text
    assert "Morning Run" in offers_response.text
    assert "Engineering Student" in offers_response.text
    assert "CS Student" in offers_response.text
    assert "1/2" in offers_response.text
    assert "2/4" in offers_response.text


def test_demo_mode_does_not_replace_authenticated_user(demo_client):
    signup(
        demo_client,
        username="existing_user",
        email="existing@example.com",
    )

    response = demo_client.get("/")

    assert response.status_code == 200
    assert "Let’s start strong," in response.text
    assert "existing_user." in response.text
    assert "Engineering Student." not in response.text
