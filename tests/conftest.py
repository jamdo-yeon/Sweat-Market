# tests/conftest.py
import os

# Configure the isolated database before importing app.db, which creates the
# engine at import time. This prevents tests from touching the local/dev DB.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["TESTING"] = "1"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import engine

from app.main import app  # noqa: E402

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with TestClient(app) as c:
        yield c 
