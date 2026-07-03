from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    DB_PATH: str = os.environ.get("DB_PATH", "crm.db")
    TZ: str = os.environ.get("TZ", "Europe/Moscow")
    SESSION_SECRET: str = os.environ.get("SESSION_SECRET", "change-me-in-prod")
    IDLE_TIMEOUT_MIN: int = int(os.environ.get("IDLE_TIMEOUT_MIN", "120"))


settings = Settings()
