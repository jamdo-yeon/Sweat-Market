from __future__ import annotations

import os
import secrets
import threading
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlmodel import Session, select

from .auth import pwd
from .models import (
    ChatRoom,
    Message,
    Order,
    Tx,
    User,
    WorkoutOffer,
    WorkoutParticipant,
)


ENGINEERING_USERNAME = "engineering_student"
CS_USERNAME = "cs_student"
VANCOUVER = ZoneInfo("America/Vancouver")
_SEED_LOCK = threading.Lock()
_POSTGRES_SEED_LOCK_ID = 743_286_051


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _password_hash() -> str:
    password = os.getenv("DEMO_USER_PASSWORD") or secrets.token_urlsafe(32)
    return pwd.hash(password)


def _ensure_user(session: Session, **values) -> User:
    user = session.exec(
        select(User).where(User.username == values["username"])
    ).first()
    if user:
        return user

    user = User(password_hash=_password_hash(), **values)
    session.add(user)
    session.flush()
    return user


def _future_workout_time(
    now: datetime,
    *,
    days_ahead: int,
    hour: int,
    minute: int,
) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    local_date = now.astimezone(VANCOUVER).date() + timedelta(days=days_ahead)
    local_datetime = datetime.combine(
        local_date,
        time(hour=hour, minute=minute),
        tzinfo=VANCOUVER,
    )
    return local_datetime.astimezone(timezone.utc)


def _ensure_offer(
    session: Session,
    *,
    creator: User,
    now: datetime,
    scheduled_at: datetime,
    **values,
) -> WorkoutOffer:
    offer = session.exec(
        select(WorkoutOffer).where(
            WorkoutOffer.creator_id == creator.id,
            WorkoutOffer.title == values["title"],
        )
    ).first()

    if not offer:
        offer = WorkoutOffer(
            creator_id=int(creator.id),
            scheduled_at=scheduled_at,
            **values,
        )
        session.add(offer)
        session.flush()
    else:
        existing_time = offer.scheduled_at
        if existing_time.tzinfo is None:
            existing_time = existing_time.replace(tzinfo=timezone.utc)
        if existing_time <= now:
            offer.scheduled_at = scheduled_at
            session.add(offer)
            session.flush()

    return offer


def _ensure_participant(
    session: Session,
    *,
    offer: WorkoutOffer,
    user: User,
) -> None:
    participant = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer.id,
            WorkoutParticipant.user_id == user.id,
        )
    ).first()
    if not participant:
        session.add(
            WorkoutParticipant(
                offer_id=int(offer.id),
                user_id=int(user.id),
            )
        )
        session.flush()


def _ensure_chat_room(session: Session, offer: WorkoutOffer) -> None:
    room = session.exec(
        select(ChatRoom).where(ChatRoom.offer_id == offer.id)
    ).first()
    if not room:
        session.add(ChatRoom(offer_id=int(offer.id)))
        session.flush()


def cleanup_obsolete_test_data(session: Session) -> dict[str, int]:
    deleted = {
        "offers": 0,
        "participants": 0,
        "rooms": 0,
        "messages": 0,
        "users": 0,
    }
    candidate_user_ids: set[int] = set()

    possible_offers = session.exec(
        select(WorkoutOffer).where(WorkoutOffer.title == "Test Workout")
    ).all()

    for offer in possible_offers:
        creator = session.get(User, offer.creator_id)
        is_obsolete_test_offer = (
            creator is not None
            and creator.username.startswith("user_")
            and "Simon Fraser University" in offer.location
            and offer.description == "Evening run"
        )
        if not is_obsolete_test_offer:
            continue

        candidate_user_ids.add(int(creator.id))

        room = session.exec(
            select(ChatRoom).where(ChatRoom.offer_id == offer.id)
        ).first()
        if room:
            messages = session.exec(
                select(Message).where(Message.room_id == room.id)
            ).all()
            for message in messages:
                candidate_user_ids.add(message.sender_id)
                session.delete(message)
                deleted["messages"] += 1
            session.delete(room)
            deleted["rooms"] += 1

        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer.id
            )
        ).all()
        for participant in participants:
            candidate_user_ids.add(participant.user_id)
            session.delete(participant)
            deleted["participants"] += 1

        session.delete(offer)
        deleted["offers"] += 1

    session.flush()

    for user_id in candidate_user_ids:
        user = session.get(User, user_id)
        if not user or not user.username.startswith("user_"):
            continue

        has_references = any(
            (
                session.exec(
                    select(WorkoutOffer).where(
                        WorkoutOffer.creator_id == user_id
                    )
                ).first(),
                session.exec(
                    select(WorkoutParticipant).where(
                        WorkoutParticipant.user_id == user_id
                    )
                ).first(),
                session.exec(
                    select(Message).where(Message.sender_id == user_id)
                ).first(),
                session.exec(select(Tx).where(Tx.user_id == user_id)).first(),
                session.exec(
                    select(Order).where(Order.user_id == user_id)
                ).first(),
            )
        )
        if not has_references:
            session.delete(user)
            deleted["users"] += 1

    session.flush()
    return deleted


def seed_demo_data(
    session: Session,
    *,
    now: datetime | None = None,
) -> None:
    with _SEED_LOCK:
        if session.get_bind().dialect.name == "postgresql":
            session.connection().execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": _POSTGRES_SEED_LOCK_ID},
            )

        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        cleanup_obsolete_test_data(session)

        engineering_student = _ensure_user(
            session,
            username=ENGINEERING_USERNAME,
            nickname="Engineering Student",
            email="engineering.demo@example.com",
            sport="gym",
            region="Surrey, BC",
            goal="Find workout partners and stay consistent",
            coins=30,
            is_active=True,
            email_confirmed_at=now,
        )
        cs_student = _ensure_user(
            session,
            username=CS_USERNAME,
            nickname="CS Student",
            email="cs.demo@example.com",
            sport="running",
            region="Surrey, BC",
            goal="Morning runs and fitness accountability",
            coins=20,
            is_active=True,
            email_confirmed_at=now,
        )

        gym_buddy = _ensure_offer(
            session,
            creator=engineering_student,
            now=now,
            title="Gym Buddy",
            sport="gym",
            location="Surrey Sport & Leisure Complex — Surrey, BC, Canada",
            latitude=49.1535,
            longitude=-122.7631,
            scheduled_at=_future_workout_time(
                now,
                days_ahead=1,
                hour=18,
                minute=0,
            ),
            description="Looking for a gym buddy for a strength workout.",
            max_participants=2,
        )
        morning_run = _ensure_offer(
            session,
            creator=cs_student,
            now=now,
            title="Morning Run",
            sport="running",
            location="Holland Park — Surrey, BC, Canada",
            latitude=49.1838,
            longitude=-122.8484,
            scheduled_at=_future_workout_time(
                now,
                days_ahead=2,
                hour=7,
                minute=30,
            ),
            description="Easy morning run before classes. All levels welcome.",
            max_participants=4,
        )

        _ensure_participant(
            session,
            offer=gym_buddy,
            user=engineering_student,
        )
        _ensure_participant(
            session,
            offer=morning_run,
            user=cs_student,
        )
        _ensure_participant(
            session,
            offer=morning_run,
            user=engineering_student,
        )
        _ensure_chat_room(session, gym_buddy)
        _ensure_chat_room(session, morning_run)
        session.commit()


class DemoAutoLoginMiddleware:
    def __init__(self, app, *, engine):
        self.app = app
        self.engine = engine

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and demo_mode_enabled():
            browser_session = scope.get("session")
            if browser_session is not None:
                with Session(self.engine) as session:
                    uid = browser_session.get("uid")
                    current = session.get(User, uid) if uid else None
                    if current is None:
                        demo_user = session.exec(
                            select(User).where(
                                User.username == ENGINEERING_USERNAME
                            )
                        ).first()
                        if demo_user:
                            browser_session["uid"] = int(demo_user.id)

        await self.app(scope, receive, send)
