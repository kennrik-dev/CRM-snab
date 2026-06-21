from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import User, Dict
from app.security import hash_password, verify_password


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed(db):
    from app.seed import seed_initial
    seed_initial(db)


def test_admin_created_with_correct_fields(db):
    _seed(db)
    admin = db.query(User).filter_by(email="admin@crm.local").one()
    assert admin.global_role == "Админ"
    assert admin.must_change_password == 1
    assert admin.is_active == 1
    assert admin.account_type == "global"


def test_password_hash_is_not_plain_and_is_bcrypt(db):
    _seed(db)
    admin = db.query(User).filter_by(email="admin@crm.local").one()
    assert admin.password_hash != "change-me-123"
    assert admin.password_hash.startswith("$2")


def test_verify_default_password(db):
    _seed(db)
    admin = db.query(User).filter_by(email="admin@crm.local").one()
    assert verify_password("change-me-123", admin.password_hash) is True


def test_seed_idempotent_for_admin(db):
    _seed(db)
    _seed(db)
    assert db.query(User).filter_by(email="admin@crm.local").count() == 1


def test_status_zakup_dict_has_six_values(db):
    _seed(db)
    values = {d.value for d in db.query(Dict).filter_by(kind="status_zakup").all()}
    assert values == {
        "Приём заявок",
        "Торги",
        "Тех. экспертиза",
        "Дозапросы",
        "Согласование",
        "На сделку",
    }
    assert len(values) == 6


def test_status_sdelki_dict_has_three_values(db):
    _seed(db)
    values = {d.value for d in db.query(Dict).filter_by(kind="status_sdelki").all()}
    assert values == {"Согласование", "Подготовка ДД", "Подписано"}
    assert len(values) == 3


def test_seed_idempotent_for_dicts(db):
    _seed(db)
    _seed(db)
    zakup = db.query(Dict).filter_by(kind="status_zakup").count()
    sdelki = db.query(Dict).filter_by(kind="status_sdelki").count()
    assert zakup == 6
    assert sdelki == 3


def test_dict_unique_kind_value(db):
    _seed(db)
    db.add(Dict(kind="status_zakup", value="Приём заявок", sort_order=99))
    with pytest.raises(IntegrityError):
        db.commit()
