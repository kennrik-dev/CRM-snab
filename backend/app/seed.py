from __future__ import annotations

from sqlalchemy.orm import Session

from .models import User, Dict
from .security import hash_password

DEFAULT_ADMIN_EMAIL = "admin@crm.local"
DEFAULT_ADMIN_PASSWORD = "change-me-123"
DEFAULT_ADMIN_NAME = "Администратор"

ZAKUP_VALUES = [
    ("Приём заявок", 1),
    ("Торги", 2),
    ("Тех. экспертиза", 3),
    ("Дозапросы", 4),
    ("Согласование", 5),
    ("На сделку", 6),
]
SDELKI_VALUES = [
    ("Согласование", 1),
    ("Подготовка ДД", 2),
    ("Подписано", 3),
]


def seed_initial(db: Session) -> None:
    # Admin (idempotent on email)
    if not db.query(User).filter_by(email=DEFAULT_ADMIN_EMAIL).first():
        db.add(
            User(
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                full_name=DEFAULT_ADMIN_NAME,
                account_type="global",
                global_role="Админ",
                is_active=1,
                must_change_password=1,
            )
        )
    # Dicts
    for value, order in ZAKUP_VALUES:
        if not db.query(Dict).filter_by(kind="status_zakup", value=value).first():
            db.add(Dict(kind="status_zakup", value=value, sort_order=order))
    for value, order in SDELKI_VALUES:
        if not db.query(Dict).filter_by(kind="status_sdelki", value=value).first():
            db.add(Dict(kind="status_sdelki", value=value, sort_order=order))
    db.commit()
