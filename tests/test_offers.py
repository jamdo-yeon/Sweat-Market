import uuid

from sqlmodel import Session as SQLSession, select
from datetime import datetime, timedelta, timezone

from app.db import engine
from app.models import User, Tx, WorkoutOffer, WorkoutParticipant
from tests.test_auth import signup, login
from app.qr import create_checkin_token


def _unique_user():
    token = uuid.uuid4().hex[:8]
    return f"user_{token}", f"{token}@test.com"


def _create_offer(
        client, 
        max_participants=3,
        scheduled_at="2026-09-25T18:00",
    ):
    r = client.post(
        "/offers",
        data={
            "sport": "running",
            "location": "Simon Fraser University — Burnaby, BC",
            "latitude": "49.2781",
            "longitude": "-122.9199",
            "scheduled_at": scheduled_at,
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
            "location": "Simon Fraser University — Burnaby, BC",
            "latitude": "49.2781",
            "longitude": "-122.9199",
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

def test_create_offer_requires_valid_location(client):
    username, email = _unique_user()
    signup(client, username=username, email=email)

    r = client.post(
        "/offers",
        data={
            "sport": "running",
            "location": "Random typed text",
            "scheduled_at": "2026-09-25T18:00",
            "max_participants": "3",
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == "/offers?error=location"

    with SQLSession(engine) as session:
        offer = session.exec(select(WorkoutOffer)).first()
        assert offer is None

def test_location_verification_succeeds_near_workout_time(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    r = client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?location_status=verified&offer_id={offer_id}"
    )

    with SQLSession(engine) as session:
        participant = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id,
                WorkoutParticipant.user_id != 1,
            )
        ).first()

        assert participant is not None
        assert participant.location_verified_at is not None

def test_location_verification_rejected_outside_time_window(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(hours=2)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    r = client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?location_status=wrong_time&offer_id={offer_id}"
    )

def test_verified_participant_can_check_in(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )
    token = create_checkin_token(offer_id)

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    r = client.get(
        f"/offers/{offer_id}/checkin?token={token}",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=success&offer_id={offer_id}"
    )

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        checked_in_participant = next(
            p for p in participants
            if p.checked_in
        )

        assert checked_in_participant.checked_in is True
        assert checked_in_participant.checked_in_at is not None

def test_unverified_participant_cannot_check_in(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )
    token = create_checkin_token(offer_id)

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    r = client.get(
        f"/offers/{offer_id}/checkin?token={token}",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=location_required&offer_id={offer_id}"
    )

    with SQLSession(engine) as session:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id
            )
        ).all()

        assert all(
            participant.checked_in is False
            for participant in participants
        )

def test_non_participant_cannot_check_in(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    offer_id = _create_offer(client)
    token = create_checkin_token(offer_id)

    client.get("/logout")

    outsider_name, outsider_email = _unique_user()
    signup(client, username=outsider_name, email=outsider_email)

    r = client.get(
        f"/offers/{offer_id}/checkin?token={token}",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=not_participant&offer_id={offer_id}"
    )

def test_invalid_qr_token_is_rejected(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    offer_id = _create_offer(client)

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    r = client.get(
        f"/offers/{offer_id}/checkin?token=invalid-token",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=invalid_qr&offer_id={offer_id}"
    )

def test_checkin_awards_coins_only_once(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    token = create_checkin_token(offer_id)

    # First scan should award the workout reward.
    r = client.get(
        f"/offers/{offer_id}/checkin?token={token}",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=success&offer_id={offer_id}"
    )

    with SQLSession(engine) as session:
        user = session.exec(
            select(User).where(User.username == user_name)
        ).first()

        assert user is not None
        assert user.coins == 10

        transactions = session.exec(
            select(Tx).where(
                Tx.user_id == user.id,
                Tx.kind == "workout_reward",
            )
        ).all()

        assert len(transactions) == 1
        assert transactions[0].amount == 10

    # Scanning the same QR again must not award coins again.
    r = client.get(
        f"/offers/{offer_id}/checkin?token={token}",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=already_checked_in&offer_id={offer_id}"
    )

    with SQLSession(engine) as session:
        user = session.exec(
            select(User).where(User.username == user_name)
        ).first()

        assert user is not None
        assert user.coins == 10

        transactions = session.exec(
            select(Tx).where(
                Tx.user_id == user.id,
                Tx.kind == "workout_reward",
            )
        ).all()

        assert len(transactions) == 1

def test_qr_available_when_verified_participants_are_near_each_other(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )

    # Host verifies at workout location
    client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    client.get("/logout")

    # Second participant joins and verifies nearby
    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2782",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    # QR is only accessible to the host
    client.get("/logout")

    login(
        client,
        username=creator_name,
        email=creator_email,
        password="Passw0rd!",
    )

    r = client.get(
        f"/offers/{offer_id}/qr",
        follow_redirects=False,
    )

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"

def test_qr_blocked_when_verified_participants_are_far_apart(client):
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )

    # Host verifies at workout location
    client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    client.get("/logout")

    user_name, user_email = _unique_user()
    signup(client, username=user_name, email=user_email)
    client.post(f"/offers/{offer_id}/join")

    # Directly simulate a recent verification far from the host.
    # We do this at the DB level because the normal verification endpoint
    # correctly rejects locations far from the workout.
    with SQLSession(engine) as session:
        user = session.exec(
            select(User).where(User.username == user_name)
        ).first()

        participant = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id,
                WorkoutParticipant.user_id == user.id,
            )
        ).first()

        participant.verified_latitude = 49.2800
        participant.verified_longitude = -122.9199
        participant.location_verified_at = datetime.now(timezone.utc)

        session.add(participant)
        session.commit()

    client.get("/logout")

    login(
        client,
        username=creator_name,
        email=creator_email,
        password="Passw0rd!",
    )

    r = client.get(
        f"/offers/{offer_id}/qr",
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == "/offers"

def test_logged_out_qr_scan_preserves_token_through_login(client):
    # Creator creates workout
    creator_name, creator_email = _unique_user()
    signup(client, username=creator_name, email=creator_email)

    scheduled_at = (
        datetime.now() + timedelta(minutes=5)
    ).isoformat(timespec="minutes")

    offer_id = _create_offer(
        client,
        scheduled_at=scheduled_at,
    )

    client.get("/logout")

    # Participant creates account and joins workout
    user_name, user_email = _unique_user()
    signup(
        client,
        username=user_name,
        email=user_email,
        password="Passw0rd!",
    )

    client.post(f"/offers/{offer_id}/join")

    # Participant verifies location while logged in
    client.post(
        f"/offers/{offer_id}/verify-location",
        data={
            "latitude": "49.2781",
            "longitude": "-122.9199",
        },
        follow_redirects=False,
    )

    token = create_checkin_token(offer_id)

    # Simulate scanning the QR while logged out
    client.get("/logout")

    r = client.get(
        f"/offers/{offer_id}/checkin?token={token}",
        follow_redirects=False,
    )

    assert r.status_code == 303

    login_url = r.headers["location"]

    assert login_url.startswith("/login?next=")
    assert token in login_url

    # Open login page so the hidden `next` value is rendered
    login_page = client.get(login_url)

    assert login_page.status_code == 200
    assert token in login_page.text

    # Submit login with the original check-in URL preserved
    next_url = f"/offers/{offer_id}/checkin?token={token}"

    r = client.post(
        "/login",
        data={
            "email": user_email,
            "password": "Passw0rd!",
            "next": next_url,
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == next_url

    # Browser follows the redirect back to the signed QR check-in
    r = client.get(
        r.headers["location"],
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == (
        f"/offers?checkin_status=success&offer_id={offer_id}"
    )

    # Check-in should actually be persisted
    with SQLSession(engine) as session:
        user = session.exec(
            select(User).where(User.username == user_name)
        ).first()

        participant = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer_id,
                WorkoutParticipant.user_id == user.id,
            )
        ).first()

        assert participant is not None
        assert participant.checked_in is True
        assert participant.checked_in_at is not None

        # Successful QR check-in should also award the reward
        assert user.coins == 10