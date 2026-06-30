"""Tests for /comments router (Phase 10 B2). Spec: docs/31 §7, docs/01 §2.7."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password
from app.models import Comment, AuditLog, ParentRequest, User

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


def _login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def client_admin(client_seeded):
    """Admin with must_change_password=0 (change then re-login)."""
    _login(client_seeded, ADMIN_EMAIL, ADMIN_INITIAL_PASSWORD)
    r = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD},
    )
    assert r.status_code == 200, r.text
    client_seeded.post("/auth/logout")
    _login(client_seeded, ADMIN_EMAIL, ADMIN_NEW_PASSWORD)
    return client_seeded


def _make_dept_user(db, email, department, curator=False, password="pass12345"):
    u = User(
        email=email,
        password_hash=hash_password(password),
        full_name=email.split("@")[0].title(),
        account_type="department",
        department=department,
        is_curator=1 if curator else 0,
        global_role=None,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_parent(db, code="Т-1"):
    p = ParentRequest(code=code, title="T", sostavitel="S")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# POST /comments
# ---------------------------------------------------------------------------

def test_create_comment_fills_author_and_role_snapshot(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments",
        json={"target_kind": "parent", "target_id": parent.id, "text": "Привет!"},
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["text"] == "Привет!"
    assert c["target_kind"] == "parent"
    assert c["target_id"] == parent.id
    # author/role filled server-side from the session user (admin)
    assert c["author"] and c["author"] == "Админ" or c["role"] in ("Админ",)
    assert c["author_id"] is not None
    assert "created_at" in c


def test_create_comment_writes_audit(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "x"}
    )
    rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="parent", entity_id=parent.id)
        .all()
    )
    assert any("комментар" in (row.action or "").lower() for row in rows)


def test_create_comment_rejects_bad_target_kind(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments",
        json={"target_kind": "delivery", "target_id": parent.id, "text": "x"},
    )
    assert r.status_code == 422, r.text


def test_create_comment_rejects_empty_text(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments",
        json={"target_kind": "parent", "target_id": parent.id, "text": "   "},
    )
    assert r.status_code == 422, r.text


def test_create_comment_404_when_target_missing(client_admin, db_seeded):
    r = client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": 999999, "text": "x"}
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# GET /comments
# ---------------------------------------------------------------------------

def test_list_comments_filtered_and_ascending(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    for txt in ("первый", "второй", "третий"):
        client_admin.post(
            "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": txt}
        )
    other = _make_parent(db_seeded, code="Т-2")
    client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": other.id, "text": "чужей"}
    )
    r = client_admin.get(f"/comments?target_kind=parent&target_id={parent.id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert [c["text"] for c in body["items"]] == ["первый", "второй", "третий"]


# ---------------------------------------------------------------------------
# DELETE /comments/{id}
# ---------------------------------------------------------------------------

def test_delete_own_comment_as_author(client_admin, db_seeded):
    parent = _make_parent(db_seeded)
    r = client_admin.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "x"}
    )
    cid = r.json()["id"]
    d = client_admin.delete(f"/comments/{cid}")
    assert d.status_code == 204, d.text
    assert db_seeded.query(Comment).filter_by(id=cid).first() is None


def test_delete_others_comment_as_non_author_forbidden(client_seeded, db_seeded):
    author = _make_dept_user(db_seeded, "a@x.local", "Закупки")
    other = _make_dept_user(db_seeded, "b@x.local", "Закупки")
    parent = _make_parent(db_seeded)
    _login(client_seeded, author.email, "pass12345")
    r = client_seeded.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "мной"}
    )
    cid = r.json()["id"]
    client_seeded.post("/auth/logout")
    _login(client_seeded, other.email, "pass12345")
    d = client_seeded.delete(f"/comments/{cid}")
    assert d.status_code == 403, d.text


def test_delete_others_comment_as_admin_ok(client_seeded, db_seeded):
    author = _make_dept_user(db_seeded, "a@x.local", "Закупки")
    parent = _make_parent(db_seeded)
    _login(client_seeded, author.email, "pass12345")
    r = client_seeded.post(
        "/comments", json={"target_kind": "parent", "target_id": parent.id, "text": "мной"}
    )
    cid = r.json()["id"]
    client_seeded.post("/auth/logout")
    # Change admin password in THIS session (seed leaves change-me-123 + must_change=1).
    _login(client_seeded, ADMIN_EMAIL, ADMIN_INITIAL_PASSWORD)
    client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD},
    )
    client_seeded.post("/auth/logout")
    _login(client_seeded, ADMIN_EMAIL, ADMIN_NEW_PASSWORD)
    d = client_seeded.delete(f"/comments/{cid}")
    assert d.status_code == 204, d.text


def test_delete_missing_comment_404(client_admin):
    assert client_admin.delete("/comments/999999").status_code == 404


# ---------------------------------------------------------------------------
# auth gating
# ---------------------------------------------------------------------------

def test_comments_unauthenticated_401(client_seeded):
    assert client_seeded.get("/comments?target_kind=parent&target_id=1").status_code == 401
