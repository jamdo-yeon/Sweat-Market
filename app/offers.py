from datetime import datetime

import os
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from math import radians, sin, cos, sqrt, atan2

from .auth import current_user
from .db import get_session
from .models import User, WorkoutOffer, WorkoutParticipant

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

    for offer in offers:
        participants = session.exec(
            select(WorkoutParticipant).where(
                WorkoutParticipant.offer_id == offer.id
            )
        ).all()

        participant_counts[offer.id] = len(participants)

        if user and any(p.user_id == user.id for p in participants):
            joined_offer_ids.add(offer.id)

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
        },
    )


@router.post("/offers")
def create_offer(
    request: Request,
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
        sport=sport.strip(),
        location=location.strip(),
        latitude=latitude,
        longitude=longitude,
        scheduled_at=datetime.fromisoformat(scheduled_at),
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
        return RedirectResponse(
            f"/offers?location_status=verified&offer_id={offer_id}",
            status_code=303,
        )

    return RedirectResponse(
        f"/offers?location_status=too_far&offer_id={offer_id}",
        status_code=303,
    )