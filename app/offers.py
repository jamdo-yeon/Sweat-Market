from datetime import datetime, timezone

import os
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from math import radians, sin, cos, sqrt, atan2
from urllib.parse import quote

from .auth import current_user
from .db import get_session
from .models import User, WorkoutOffer, WorkoutParticipant, Tx
from itsdangerous import BadSignature, SignatureExpired

from .qr import (
    create_checkin_token,
    qr_png_bytes,
    verify_checkin_token,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def distance_meters(lat1, lon1, lat2, lon2):
    earth_radius_m = 6_371_000

    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = (
        sin(delta_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius_m * c

def recently_verified(participant: WorkoutParticipant) -> bool:
    if participant.location_verified_at is None:
        return False

    verified_at = participant.location_verified_at

    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)

    age_seconds = (
        datetime.now(timezone.utc) - verified_at
    ).total_seconds()

    return 0 <= age_seconds <= 10 * 60

def participants_near_each_other(
    participants: list[WorkoutParticipant],
    host_user_id: int,
    max_distance_meters: float = 150,
) -> bool:
    verified = [
        participant
        for participant in participants
        if recently_verified(participant)
        and participant.verified_latitude is not None
        and participant.verified_longitude is not None
    ]

    host = next(
        (
            participant
            for participant in verified
            if participant.user_id == host_user_id
        ),
        None,
    )

    if host is None:
        return False

    for participant in verified:
        if participant.user_id == host_user_id:
            continue

        distance = distance_meters(
            host.verified_latitude,
            host.verified_longitude,
            participant.verified_latitude,
            participant.verified_longitude,
        )

        if distance <= max_distance_meters:
            return True

    return False


@router.get("/offers")
def offers_page(
    request: Request,
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    offers = session.exec(
        select(WorkoutOffer).order_by(WorkoutOffer.scheduled_at)
    ).all()

    participant_counts = {}
    joined_offer_ids = set()
    qr_ready_offer_ids = set()

    for offer in offers:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer.id
            )
        ).all()

        participant_counts[offer.id] = len(participants)

        if user and any(p.user_id == user.id for p in participants):
            joined_offer_ids.add(offer.id)

        if participants_near_each_other(
            participants,
            host_user_id=offer.creator_id,
        ):
            qr_ready_offer_ids.add(offer.id)

    creators = {
        offer.creator_id: session.get(User, offer.creator_id)
        for offer in offers
    }

    return templates.TemplateResponse(
        request,
        "offers.html",
        {
            "user": user,
            "offers": offers,
            "participant_counts": participant_counts,
            "joined_offer_ids": joined_offer_ids,
            "creators": creators,
            "google_maps_api_key": os.getenv("GOOGLE_MAPS_API_KEY"),
            "location_error": request.query_params.get("error") == "location",
            "location_status": request.query_params.get("location_status"),
            "status_offer_id": request.query_params.get("offer_id"),
            "qr_ready_offer_ids": qr_ready_offer_ids,
            "checkin_status": request.query_params.get("checkin_status"),
        },
    )


@router.post("/offers")
def create_offer(
    request: Request,
    title: str = Form(...),
    sport: str = Form(...),
    location: str = Form(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    scheduled_at: str = Form(...),
    description: str | None = Form(None),
    max_participants: int = Form(2),
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        return RedirectResponse("/login", status_code=303)

    if latitude is None or longitude is None:
        return RedirectResponse("/offers?error=location", status_code=303)

    offer = WorkoutOffer(
        creator_id=user.id,
        title=title.strip(),
        sport=sport.strip(),
        location=location.strip(),
        latitude=latitude,
        longitude=longitude,
        scheduled_at=datetime.fromisoformat(
            scheduled_at.replace("Z", "+00:00")
        ),
        description=(description or "").strip() or None,
        max_participants=max_participants,
    )

    session.add(offer)
    session.commit()
    session.refresh(offer)

    # Creator automatically joins their own workout
    participant = WorkoutParticipant(
        offer_id=offer.id,
        user_id=user.id,
    )

    session.add(participant)
    session.commit()

    return RedirectResponse("/offers", status_code=303)

@router.post("/offers/{offer_id}/join")
def join_offer(
    offer_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        return RedirectResponse("/login", status_code=303)

    offer = session.get(WorkoutOffer, offer_id)
    if not offer:
        return RedirectResponse("/offers", status_code=303)

    existing = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id,
            WorkoutParticipant.user_id == user.id,
        )
    ).first()

    if existing:
        return RedirectResponse("/offers", status_code=303)

    participants = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id
        )
    ).all()

    if len(participants) >= offer.max_participants:
        return RedirectResponse("/offers", status_code=303)

    session.add(
        WorkoutParticipant(
            offer_id=offer_id,
            user_id=user.id,
        )
    )
    session.commit()

    return RedirectResponse("/offers", status_code=303)


@router.post("/offers/{offer_id}/leave")
def leave_offer(
    offer_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        return RedirectResponse("/login", status_code=303)

    offer = session.get(WorkoutOffer, offer_id)
    if not offer:
        return RedirectResponse("/offers", status_code=303)

    # Creator stays in their own workout
    if offer.creator_id == user.id:
        return RedirectResponse("/offers", status_code=303)

    participant = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id,
            WorkoutParticipant.user_id == user.id,
        )
    ).first()

    if participant:
        session.delete(participant)
        session.commit()

    return RedirectResponse("/offers", status_code=303)

@router.post("/offers/{offer_id}/verify-location")
def verify_location(
    offer_id: int,
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        return RedirectResponse("/login", status_code=303)

    offer = session.get(WorkoutOffer, offer_id)
    if not offer:
        return RedirectResponse("/offers", status_code=303)

    participant = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id,
            WorkoutParticipant.user_id == user.id,
        )
    ).first()

    if not participant:
        return RedirectResponse("/offers", status_code=303)

    now = datetime.now(timezone.utc)

    scheduled_at = offer.scheduled_at

    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    seconds_from_workout = abs(
        (now - scheduled_at).total_seconds()
    )

    if seconds_from_workout > 30 * 60:
        return RedirectResponse(
            f"/offers?location_status=wrong_time&offer_id={offer_id}",
            status_code=303,
        )

    if offer.latitude is None or offer.longitude is None:
        return RedirectResponse(
            f"/offers?location_status=unavailable&offer_id={offer_id}",
            status_code=303,
        )

    distance = distance_meters(
        latitude,
        longitude,
        offer.latitude,
        offer.longitude,
    )

    if distance <= 150:
        participant.verified_latitude = latitude
        participant.verified_longitude = longitude
        participant.location_verified_at = datetime.now(timezone.utc)

        session.add(participant)
        session.commit()
        return RedirectResponse(
            f"/offers?location_status=verified&offer_id={offer_id}",
            status_code=303,
        )

    return RedirectResponse(
        f"/offers?location_status=too_far&offer_id={offer_id}",
        status_code=303,
    )

@router.get("/offers/{offer_id}/qr")
def workout_qr(
    offer_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        return RedirectResponse("/login", status_code=303)

    offer = session.get(WorkoutOffer, offer_id)

    if not offer or offer.creator_id != user.id:
        return RedirectResponse("/offers", status_code=303)

    participants = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id
        )
    ).all()

    if not participants_near_each_other(
        participants,
        host_user_id=offer.creator_id,
    ):
        return RedirectResponse("/offers", status_code=303)

    token = create_checkin_token(offer_id)

    payload = str(
        request.url_for(
            "checkin",
            offer_id=offer_id,
        )
    ) + f"?token={token}"

    return Response(
        content=qr_png_bytes(payload),
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
        },
    )

@router.get("/offers/{offer_id}/checkin")
def checkin(
    offer_id: int,
    request: Request,
    token: str | None = None,
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        next_url = f"/offers/{offer_id}/checkin"

        if token:
            next_url += f"?token={token}"

        return RedirectResponse(
            f"/login?next={quote(next_url, safe='')}",
            status_code=303,
        )

    if not token:
        return RedirectResponse(
            f"/offers?checkin_status=invalid_qr&offer_id={offer_id}",
            status_code=303,
        )

    try:
        token_data = verify_checkin_token(token)
    except SignatureExpired:
        return RedirectResponse(
            f"/offers?checkin_status=expired_qr&offer_id={offer_id}",
            status_code=303,
        )
    except BadSignature:
        return RedirectResponse(
            f"/offers?checkin_status=invalid_qr&offer_id={offer_id}",
            status_code=303,
        )

    if token_data.get("offer_id") != offer_id:
        return RedirectResponse(
            f"/offers?checkin_status=invalid_qr&offer_id={offer_id}",
            status_code=303,
        )

    offer = session.get(WorkoutOffer, offer_id)

    if not offer:
        return RedirectResponse("/offers", status_code=303)

    participant = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id,
            WorkoutParticipant.user_id == user.id,
        )
    ).first()

    if not participant:
        return RedirectResponse(
            f"/offers?checkin_status=not_participant&offer_id={offer_id}",
            status_code=303,
        )

    if offer.creator_id == user.id:
        return RedirectResponse(
            f"/offers?checkin_status=host&offer_id={offer_id}",
            status_code=303,
        )

    if not recently_verified(participant):
        return RedirectResponse(
            f"/offers?checkin_status=location_required&offer_id={offer_id}",
            status_code=303,
        )

    if participant.checked_in:
        return RedirectResponse(
            f"/offers?checkin_status=already_checked_in&offer_id={offer_id}",
            status_code=303,
        )

    reward_coins = 10

    participant.checked_in = True
    participant.checked_in_at = datetime.now(timezone.utc)

    user.coins += reward_coins

    transaction = Tx(
        user_id=user.id,
        amount=reward_coins,
        kind="workout_reward",
        note=f"Verified workout check-in #{offer_id}",
    )

    session.add(participant)
    session.add(user)
    session.add(transaction)
    session.commit()

    return RedirectResponse(
        f"/offers?checkin_status=success&offer_id={offer_id}",
        status_code=303,
    )
