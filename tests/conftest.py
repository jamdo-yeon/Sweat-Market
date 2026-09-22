# tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import engine


# IMPORTANT: app import 전에 env 세팅 (engine이 import-time에 잡힐 수 있음)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["TESTING"] = "1"
os.environ["SECRET_KEY"] = "test-secret"

# 혹시 남아있으면 삭제

from app.main import app  # noqa: E402

@pytest.fixture
def client():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with TestClient(app) as c:
        yield c 
