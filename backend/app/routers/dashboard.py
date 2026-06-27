"""/dashboard router (Phase 8.1) — обзорный экран (одинаков для всех ролей).

Read-only: auth = require_password_changed (NO require_action). Data is global.
Spec: docs/14-page-dashboard.md, docs/32 §6. Decisions: docs/superpowers/specs/2026-06-27-phase8-dashboard-design.md.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import calculations as calc
from app.db import get_db
from app.dependencies import require_password_changed
from app.models import User
from app.schemas.dashboard import DashboardOut


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
) -> DashboardOut:
    data = calc.dashboard(db, calc.today_moscow())
    return DashboardOut(**data)
