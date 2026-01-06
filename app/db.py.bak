# Database engine and initialization.
# TODO (A or C):
# - Create SQLModel engine (sqlite+aiosqlite:///./fitcoin.db by default)
# - init_db(): SQLModel.metadata.create_all(bind=engine)
# - Consider reading DATABASE_URL from env with default SQLite file.

# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sweatmarket.db")
# aiosqlite 쓰지 않음 (동기 엔진)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
