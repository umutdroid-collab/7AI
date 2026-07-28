"""Test ortamı. Her test kendi geçici veritabanı ve veri klasörleriyle
çalışır; ayarlar get_settings() içinde lru_cache'lendiği için ortam
değişkenleri uygulama import edilmeden ÖNCE ayarlanmalıdır."""

import os
import tempfile

import pytest

_TMP = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(_TMP, "test.db"))
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("INVOICE_FOLDER", os.path.join(_TMP, "invoices"))
os.environ.setdefault("CLINICAL_DOCS_FOLDER", os.path.join(_TMP, "clinical_docs"))
os.environ.setdefault("VECTOR_DB_DIR", os.path.join(_TMP, "vectorstore"))
os.environ.setdefault("CHECKIN_PHOTOS_FOLDER", os.path.join(_TMP, "checkins"))
os.environ.setdefault("BACKUP_DIR", os.path.join(_TMP, "backups"))
os.environ.setdefault("SEED_ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "testpass123")
os.environ.setdefault("PUBMED_EMAIL", "test@test.com")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = ("admin@test.com", "testpass123")


@pytest.fixture(autouse=True)
def clean_db():
    """Her testten önce şemayı sıfırla - testler birbirinin verisini görmesin."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.routers import auth as auth_router

    auth_router._failed_logins.clear()  # giriş kilidi sayaçları testler arasında sızmasın
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def auth_headers(client, email=ADMIN[0], password=ADMIN[1], ip="1.1.1.1"):
    r = client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"x-forwarded-for": ip},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return auth_headers(client)


@pytest.fixture
def employee(client, admin):
    client.post(
        "/auth/users",
        json={
            "full_name": "Test Çalışan",
            "email": "calisan@test.com",
            "password": "calisansifre1",
            "role": "employee",
        },
        headers=admin,
    )
    return auth_headers(client, "calisan@test.com", "calisansifre1", ip="2.2.2.2")
