"""/search router — global search skeleton (Phase 3.4).

GET /search?q=<string>&limit=<int>
- q: required (may be empty/whitespace => all groups empty, no DB queries)
- limit: default 20, max 50
- Requires require_password_changed

Returns JSON grouped by entity type:
{
  "parents":    [{"id": int, "code": str, "title": str}],
  "procedures": [{"id": int, "proc": str|null, "supplier": str|null, "tender_id": int}],
  "suppliers":  [{"id": int, "name": str, "proc_count": int}]
}

Matching is case-insensitive (Unicode-aware) — uses the `py_casefold` SQL
function registered in `app.db` (Python's str.casefold handles Cyrillic,
which SQLite's built-in LOWER() does not).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_password_changed
from app.models import ParentRequest, Procedure, User

router = APIRouter(tags=["search"])


@router.get("/search")
def global_search(
    q: str = Query("", description="Search query (case-insensitive substring)"),
    limit: int = Query(20, ge=1, le=50, description="Per-group cap (default 20, max 50)"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_password_changed),
):
    empty = {"parents": [], "procedures": [], "suppliers": []}

    q_stripped = q.strip()
    if not q_stripped:
        return empty

    # Casefold once in Python; py_casefold is applied to the column in SQL.
    # Both sides end up in the same canonical form, so instr() can do a
    # plain substring search. (LIKE would also work but requires escaping
    # % and _ in q; instr() sidesteps that.)
    q_cf = q_stripped.casefold()

    # ------------------------------------------------------------------
    # parents — match code OR title (case-insensitive Unicode)
    # ------------------------------------------------------------------
    code_match = func.instr(func.py_casefold(ParentRequest.code), q_cf) > 0
    title_match = func.instr(func.py_casefold(ParentRequest.title), q_cf) > 0
    parents = (
        db.query(ParentRequest.id, ParentRequest.code, ParentRequest.title)
        .filter(code_match | title_match)
        .order_by(ParentRequest.created_at.desc())
        .limit(limit)
        .all()
    )

    # ------------------------------------------------------------------
    # procedures — proc IS NOT NULL AND proc matches (case-insensitive Unicode)
    # ------------------------------------------------------------------
    procedures = (
        db.query(
            Procedure.id,
            Procedure.proc,
            Procedure.supplier,
            Procedure.tender_id,
        )
        .filter(Procedure.proc.isnot(None))
        .filter(func.instr(func.py_casefold(Procedure.proc), q_cf) > 0)
        .order_by(Procedure.created_at.desc())
        .limit(limit)
        .all()
    )

    # ------------------------------------------------------------------
    # suppliers — distinct suppliers whose name matches (case-insensitive Unicode)
    # Excludes NULL suppliers. Ordered by proc_count DESC, name ASC.
    # `id` is the min(procedure.id) for the group — a stable representative.
    # ------------------------------------------------------------------
    supplier_rows = (
        db.query(
            func.min(Procedure.id).label("id"),
            Procedure.supplier.label("name"),
            func.count(Procedure.id).label("proc_count"),
        )
        .filter(Procedure.supplier.isnot(None))
        .filter(func.instr(func.py_casefold(Procedure.supplier), q_cf) > 0)
        .group_by(Procedure.supplier)
        .order_by(func.count(Procedure.id).desc(), Procedure.supplier.asc())
        .limit(limit)
        .all()
    )

    return {
        "parents": [
            {"id": p.id, "code": p.code, "title": p.title} for p in parents
        ],
        "procedures": [
            {
                "id": pr.id,
                "proc": pr.proc,
                "supplier": pr.supplier,
                "tender_id": pr.tender_id,
            }
            for pr in procedures
        ],
        "suppliers": [
            {"id": s.id, "name": s.name, "proc_count": s.proc_count}
            for s in supplier_rows
        ],
    }
