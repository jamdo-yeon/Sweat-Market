# tests/conftest.py
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

DB_PATH = Path("/tmp/sweatmarket_test.db")

# IMPORTANT: app import 전에 env 세팅 (engine이 import-time에 잡힐 수 있음)
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret"

# 혹시 남아있으면 삭제
try:
    DB_PATH.unlink()
except FileNotFoundError:
    pass

from app.main import app  # noqa: E402

@pytest.fixture
def client():
    # 매 테스트마다 DB fresh start
    try:
        DB_PATH.unlink()
    except FileNotFoundError:
        pass

    with TestClient(app) as c:
        yield c
