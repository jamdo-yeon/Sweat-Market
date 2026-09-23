# app/chat.py
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
import os, json, time

from .db import get_session
from .models import (
    ChatRoom,
    Message,
    User,
    WorkoutOffer,
    WorkoutParticipant,
)
from .auth import current_user
from .uploads import UPLOAD_URL_PREFIX, upload_directory

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class RoomManager:
    def __init__(self):
        self.rooms: dict[int, set[WebSocket]] = {}

    async def connect(self, room_id: int, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, set()).add(ws)

    def disconnect(self, room_id: int, ws: WebSocket):
        self.rooms.get(room_id, set()).discard(ws)
        if not self.rooms.get(room_id):
            self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: int, payload: dict):
        dead = []
        for ws in self.rooms.get(room_id, set()):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)


manager = RoomManager()


def is_workout_participant(
    session: Session,
    offer_id: int,
    user_id: int,
) -> bool:
    participant = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer_id,
            WorkoutParticipant.user_id == user_id,
        )
    ).first()

    return participant is not None


def get_or_create_room(
    session: Session,
    offer_id: int,
) -> ChatRoom:
    room = session.exec(
        select(ChatRoom).where(
            ChatRoom.offer_id == offer_id
        )
    ).first()

    if not room:
        room = ChatRoom(offer_id=offer_id)
        session.add(room)
        session.commit()
        session.refresh(room)

    return room

def get_user_conversations(
    session: Session,
    user_id: int,
):
    participations = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.user_id == user_id
        )
    ).all()

    conversations = []

    for participation in participations:
        offer = session.get(
            WorkoutOffer,
            participation.offer_id,
        )

        if not offer:
            continue

        room = get_or_create_room(
            session,
            offer.id,
        )

        last_message = session.exec(
            select(Message)
            .where(Message.room_id == room.id)
            .order_by(Message.created_at.desc())
        ).first()

        last_sender = None

        if last_message:
            last_sender = session.get(
                User,
                last_message.sender_id,
            )

        conversations.append(
            {
                "room": room,
                "offer": offer,
                "last_message": last_message,
                "last_sender": last_sender,
            }
        )

    conversations.sort(
        key=lambda conversation:
            conversation["last_message"].created_at
            if conversation["last_message"]
            else conversation["room"].created_at,
        reverse=True,
    )

    return conversations


@router.get("/chat")
def chat_list(
    request: Request,
    session: Session = Depends(get_session),
):
    me = current_user(request, session)

    if not me:
        return RedirectResponse("/login", status_code=303)

    conversations = get_user_conversations(
        session,
        me.id,
    )

    return templates.TemplateResponse(
        request,
        "chat_list.html",
        {
            "user": me,
            "conversations": conversations,
        },
    )

@router.get("/offers/{offer_id}/chat")
def open_workout_chat(
    offer_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    me = current_user(request, session)

    if not me:
        return RedirectResponse(
            f"/login?next=/offers/{offer_id}/chat",
            status_code=303,
        )

    offer = session.get(WorkoutOffer, offer_id)

    if not offer:
        return RedirectResponse("/offers", status_code=303)

    if not is_workout_participant(
        session,
        offer_id,
        me.id,
    ):
        return RedirectResponse("/offers", status_code=303)

    room = get_or_create_room(
        session,
        offer_id,
    )

    return RedirectResponse(
        f"/chat/{room.id}",
        status_code=303,
    )

@router.get("/chat/{room_id}")
def chat_room(
    room_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    me = current_user(request, session)

    if not me:
        return RedirectResponse("/login", status_code=303)

    room = session.get(ChatRoom, room_id)

    if not room:
        return RedirectResponse("/chat", status_code=303)

    if not is_workout_participant(
        session,
        room.offer_id,
        me.id,
    ):
        return RedirectResponse("/chat", status_code=303)

    offer = session.get(
        WorkoutOffer,
        room.offer_id,
    )

    # All workout chats this user belongs to
    conversations = get_user_conversations(
        session,
        me.id,
    )

    # Participants in the currently selected workout
    participants = session.exec(
        select(WorkoutParticipant).where(
            WorkoutParticipant.offer_id == offer.id
        )
    ).all()

    creator = session.get(
        User,
        offer.creator_id,
    )

    messages = session.exec(
        select(Message)
        .where(Message.room_id == room_id)
        .order_by(Message.created_at)
    ).all()

    sender_ids = {
        message.sender_id
        for message in messages
    }

    senders = {
        sender_id: session.get(User, sender_id)
        for sender_id in sender_ids
    }

    return templates.TemplateResponse(
        request,
        "chat_room.html",
        {
            "user": me,
            "room": room,
            "offer": offer,
            "messages": messages,
            "senders": senders,
            "conversations": conversations,
            "participants": participants,
            "creator": creator,
            "is_host": offer.creator_id == me.id,
        },
    )


@router.websocket("/ws/chat/{room_id}")
async def ws_chat(room_id: int, websocket: WebSocket, session: Session = Depends(get_session)):
    uid = websocket.session.get("uid")
    if not uid:
        await websocket.close(code=4401)
        return

    room = session.get(ChatRoom, room_id)

    if not room:
        await websocket.close(code=4403)
        return

    if not is_workout_participant(
        session,
        room.offer_id,
        int(uid),
    ):
        await websocket.close(code=4403)
        return

    await manager.connect(room_id, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            content = (data.get("content") or "").strip()
            sender_id = int(uid)

            msg = Message(room_id=room_id, sender_id=sender_id, content=content)
            session.add(msg)
            session.commit()
            session.refresh(msg)

            await manager.broadcast(
                room_id,
                {
                    "type": "text",
                    "id": msg.id,
                    "sender_id": sender_id,
                    "content": content,
                    "created_at": msg.created_at.isoformat(),
                },
            )
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)


@router.post("/chat/{room_id}/image")
async def upload_image(
    room_id: int,
    request: Request,
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    me = current_user(request, session)
    if not me:
        return RedirectResponse("/login", status_code=303)

    room = session.get(ChatRoom, room_id)

    if not room:
        return RedirectResponse("/chat", status_code=303)

    if not is_workout_participant(
        session,
        room.offer_id,
        me.id,
    ):
        return RedirectResponse("/chat", status_code=303)

    ext = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    filename = f"{room_id}_{me.id}_{int(time.time())}{ext}"
    path = upload_directory("chat_images") / filename

    data = await image.read()
    with path.open("wb") as f:
        f.write(data)

    url = f"{UPLOAD_URL_PREFIX}/chat_images/{filename}"

    msg = Message(room_id=room_id, sender_id=me.id, image_url=url, content="")
    session.add(msg)
    session.commit()
    session.refresh(msg)

    await manager.broadcast(
        room_id,
        {
            "type": "image",
            "id": msg.id,
            "sender_id": me.id,
            "image_url": url,
            "created_at": msg.created_at.isoformat(),
        },
    )

    return RedirectResponse(f"/chat/{room_id}", status_code=303)
