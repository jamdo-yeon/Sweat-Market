from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .auth import current_user
from .db import get_session
from .models import User, WorkoutOffer, WorkoutParticipant

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
        },
    )


@router.post("/offers")
def create_offer(
    request: Request,
    sport: str = Form(...),
    location: str = Form(...),
    scheduled_at: str = Form(...),
    description: str | None = Form(None),
    max_participants: int = Form(2),
    session: Session = Depends(get_session),
):
    user = current_user(request, session)

    if not user:
        return RedirectResponse("/login", status_code=303)

    offer = WorkoutOffer(
        creator_id=user.id,
        sport=sport.strip(),
        location=location.strip(),
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