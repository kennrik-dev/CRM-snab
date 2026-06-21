"""SQLAlchemy engine + session factory.

Phase 1 — minimal engine bound to the SQLite file in `settings.DB_PATH`.
The `connect` listener enables foreign-key enforcement (off by default in SQLite)
and registers `py_casefold` (Phase 3.4 — Unicode-aware casefold for search).
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def register_sqlite_setup(dbapi_conn, _) -> None:
    """Per-connection SQLite setup. Called automatically for the prod engine
    (see the `connect` listener below) and from test fixtures.

    Idempotent actions:
    1. PRAGMA foreign_keys=ON  (so ON DELETE CASCADE works)
    2. Register `py_casefold(text) -> text` — Unicode-aware casefolding.
       SQLite's built-in `lower()` is ASCII-only, so `'Т'.lower() == 'Т'`
       which breaks case-insensitive search for Cyrillic. `py_casefold`
       delegates to Python's `str.casefold()` which handles Cyrillic
       (and `ё`→`е`, etc.) correctly.
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()

    def py_casefold(value):
        if value is None:
            return None
        return str(value).casefold()

    dbapi_conn.create_function("py_casefold", 1, py_casefold)


engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _setup_sqlite_on_connect(dbapi_conn, _):
    register_sqlite_setup(dbapi_conn, _)


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
