from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    DB_PATH: str = "crm.db"
    TZ: str = "Europe/Moscow"
    SESSION_SECRET: str = "change-me-in-prod"
    IDLE_TIMEOUT_MIN: int = 120


settings = Settings()
