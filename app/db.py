# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

default_sqlite_path = "sqlite:////tmp/sweatmarket.db" if os.getenv("VERCEL") else "sqlite:///./sweatmarket.db"
DATABASE_URL = os.getenv("DATABASE_URL", default_sqlite_path)
TESTING = os.getenv("TESTING") == "1"

if TESTING or DATABASE_URL == "sqlite://" or ":memory:" in DATABASE_URL:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # <-- in-memory DB를 테스트 동안 유지
    )
elif DATABASE_URL.startswith("sqlite:"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
