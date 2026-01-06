# app/models.py — merged Part A (User, Post/Comment, Chat) + Part D (Tx, Order)

from typing import Optional
from datetime import datetime, date, timezone
from sqlmodel import SQLModel, Field, UniqueConstraint


def utcnow():
    return datetime.now(timezone.utc)


# ---------- Part A: User ----------
class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_username"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: Optional[str] = Field(default=None, index=True)
    password_hash: str

    coins: int = 0

    nickname: Optional[str] = Field(default=None, index=True)
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    avatar_url: Optional[str] = None
    sport: Optional[str] = None
    time_window: Optional[str] = None
    region: Optional[str] = None
    goal: Optional[str] = None

    is_active: bool = Field(default=False)
    email_confirmed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utcnow)


# ---------- Part A: Community ----------
class Post(SQLModel, table=True):
    __tablename__ = "posts"
    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="users.id", index=True)
    image_url: Optional[str] = None
    caption: str
    created_at: datetime = Field(default_factory=utcnow)


class Comment(SQLModel, table=True):
    __tablename__ = "comments"
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="posts.id", index=True)
    author_id: int = Field(foreign_key="users.id", index=True)
    content: str
    created_at: datetime = Field(default_factory=utcnow)


# ---------- Part A: DM ----------
class ChatRoom(SQLModel, table=True):
    __tablename__ = "chat_rooms"
    id: Optional[int] = Field(default=None, primary_key=True)
    user1_id: int = Field(foreign_key="users.id")
    user2_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=utcnow)


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="chat_rooms.id")
    sender_id: int = Field(foreign_key="users.id")
    content: str = ""
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


# ---------- Part D: Wallet & DEX ----------
class Tx(SQLModel, table=True):
    __tablename__ = "txs"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    amount: int
    kind: str
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    side: str
    price: int
    amount: int
    created_at: datetime = Field(default_factory=utcnow)
