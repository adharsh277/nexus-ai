"""Test setup.

Uses TEST_DATABASE_URL. Supports both PostgreSQL (with Alembic migrations)
and SQLite in-memory/file testing for flexible local execution.
"""
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import User
from app.security import get_current_user
from app.services.embeddings import MockEmbeddingProvider, override_embedding_provider
from app.services.llm import MockProvider, override_llm_provider



TEST_URL = os.environ.get("TEST_DATABASE_URL", settings.test_database_url)
BACKEND_DIR = Path(__file__).resolve().parents[1]

is_sqlite = TEST_URL.startswith("sqlite")


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ensure_database(url: str) -> None:
    if is_sqlite:
        return
    db_name = make_url(url).database
    admin = create_engine(make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    if not is_sqlite:
        _ensure_database(TEST_URL)
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.attributes["url"] = TEST_URL
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        eng = create_engine(TEST_URL)
    else:
        eng = create_engine(TEST_URL, connect_args={"check_same_thread": False})
        Base.metadata.create_all(eng)

    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()

    with engine.begin() as conn:
        tables = (
            "document_chunks",
            "documents",
            "notifications",
            "reminders",
            "messages",
            "conversations",
            "tasks",
            "users",
        )
        if is_sqlite:
            for table in tables:
                conn.execute(text(f"DELETE FROM {table}"))
        else:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))


@pytest.fixture(autouse=True)
def default_mock_llm():
    """Ensure all tests run offline using MockProvider without consuming Gemini API quota."""
    provider = MockProvider()
    override_llm_provider(provider)
    yield provider
    override_llm_provider(None)


@pytest.fixture(autouse=True)
def default_mock_embeddings():
    """Ensure all tests run offline using MockEmbeddingProvider."""
    provider = MockEmbeddingProvider()
    override_embedding_provider(provider)
    yield provider
    override_embedding_provider(None)



@pytest.fixture
def user(db):
    u = User(email="alice@example.com", display_name="Alice")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def other_user(db):
    u = User(email="bob@example.com", display_name="Bob")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, user):
    """Client acting as `user`. Use `act_as(client, other)` to switch identity."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def act_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
