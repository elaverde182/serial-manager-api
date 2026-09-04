"""Fixtures de pruebas: BD SQLite temporal por sesión + cliente autenticado."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_serial.db")
os.environ.setdefault("AUTH_PROVIDER", "local")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-bytes-minimum-1234")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("LOGIN_MAX_ATTEMPTS", "100000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seeds.run import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def admin_headers(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
