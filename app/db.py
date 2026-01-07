# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sweatmarket.db")
TESTING = os.getenv("TESTING") == "1"

if TESTING or DATABASE_URL == "sqlite://" or ":memory:" in DATABASE_URL:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # <-- in-memory DB를 테스트 동안 유지
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
