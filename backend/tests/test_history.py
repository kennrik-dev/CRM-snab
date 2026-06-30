"""Tests for /history router (Phase 10 B3). Spec: docs/31 §7, docs/33 §2."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password
from app.models import AuditLog, User
from app.audit import write_audit

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"


@pytest.fixture()
def db_seeded():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _setup(dbapi_conn, _):
        register_sqlite_setup(dbapi_conn, _)

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    from app.seed import seed_initial
    seed_initial(s)
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client_seeded(db_seeded):
    def _override():
        try:
            yield db_seeded
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client_admin(client_seeded):
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    client_seeded.post("/auth/change-password", json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD})
    client_seeded.post("/auth/logout")
    r = client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD})
    assert r.status_code == 200
    return client_seeded


def _admin_user(db):
    return db.query(User).filter_by(email=ADMIN_EMAIL).one()


def test_history_filtered_descending(client_admin, db_seeded):
    u = _admin_user(db_seeded)
    for action in ("первое", "второе", "третье"):
        write_audit(db_seeded, "procedure", 5, u, action)
    # unrelated entity
    write_audit(db_seeded, "procedure", 6, u, "чужей")
    r = client_admin.get("/history?entity_kind=procedure&entity_id=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert [a["action"] for a in body["items"]] == ["третье", "второе", "первое"]


def test_history_actor_resolved_and_system_fallback(client_admin, db_seeded):
    u = _admin_user(db_seeded)
    write_audit(db_seeded, "procedure", 7, u, "с автором")
    write_audit(db_seeded, "procedure", 7, None, "без автора")  # user_id=None
    body = client_admin.get("/history?entity_kind=procedure&entity_id=7").json()
    actors = {a["action"]: a["actor"] for a in body["items"]}
    assert actors["с автором"] == u.full_name
    assert actors["без автора"] == "Система"


def test_history_accepts_arbitrary_entity_kind(client_admin, db_seeded):
    u = _admin_user(db_seeded)
    write_audit(db_seeded, "dict", 1, u, "dict event")
    r = client_admin.get("/history?entity_kind=dict&entity_id=1")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_history_unauthenticated_401(client_seeded):
    assert client_seeded.get("/history?entity_kind=procedure&entity_id=1").status_code == 401


def test_history_action_label_translated_and_fallback(client_admin, db_seeded):
    """Phase 10 F7 fix: /history returns action_label (Russian) from
    _AUDIT_PHRASES, falling back to the raw action when unmapped."""
    u = _admin_user(db_seeded)
    # (procedure, split) is a mapped snake_case action → Russian phrase
    write_audit(db_seeded, "procedure", 11, u, "split")
    # unknown action → fallback to raw
    write_audit(db_seeded, "procedure", 11, u, "some_unknown_action")
    # already-Russian action → fallback to itself
    write_audit(db_seeded, "procedure", 11, u, "Добавлен комментарий")
    body = client_admin.get("/history?entity_kind=procedure&entity_id=11").json()
    labels = {a["action"]: a["action_label"] for a in body["items"]}
    assert labels["split"] == "разбил(а) по поставщикам процедуру", labels
    assert labels["some_unknown_action"] == "some_unknown_action"
    assert labels["Добавлен комментарий"] == "Добавлен комментарий"
    # raw action still present (spec R8)
    assert all("action" in a and "action_label" in a for a in body["items"])
