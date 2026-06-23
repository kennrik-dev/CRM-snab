"""Tests for /procurement + /procedures routers (Phase 5.1).

Locked spec from `docs/superpowers/plans/2026-06-23-phase5-zakupka.md` §5.1.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password


ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"


# ---------------------------------------------------------------------------
# Fixtures (mirror test_requests.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_seeded():
    """In-memory DB with seed_initial applied."""
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
    """TestClient with get_db overridden to the seeded in-memory DB."""

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
    """TestClient logged in as admin with must_change_password=0."""
    r = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD},
    )
    assert r.status_code == 200, r.text

    r_ch = client_seeded.post(
        "/auth/change-password",
        json={"current": ADMIN_INITIAL_PASSWORD, "new": ADMIN_NEW_PASSWORD},
    )
    assert r_ch.status_code == 200, r.text

    r_lo = client_seeded.post("/auth/logout")
    assert r_lo.status_code == 200

    r_li = client_seeded.post(
        "/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_NEW_PASSWORD},
    )
    assert r_li.status_code == 200, r_li.text
    assert r_li.json()["must_change_password"] is False

    return client_seeded


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _make_zakup_emp(db, email="zakup_emp@crm.local", full_name="Закупщик Тестовый"):
    """Закупки employee — has zakupka edit rights."""
    from app.models import User
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name=full_name,
        account_type="department",
        department="Закупки",
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_kompl_emp(db, email="kompl_emp@crm.local", full_name="Комплектовщик Тестовый"):
    """Комплектация employee — has NO zakupka edit rights (RBAC negative)."""
    from app.models import User
    u = User(
        email=email,
        password_hash=hash_password("userpass123"),
        full_name=full_name,
        account_type="department",
        department="Комплектация",
        is_curator=0,
        global_role=None,
        is_active=1,
        must_change_password=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _login_as(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r


def _create_request_via_api(
    client,
    code="Т-001",
    title="Тестовая заявка",
    mtr=None,
    positions=None,
):
    """Create a parent_request + positions via the API. Returns response JSON."""
    payload = {
        "code": code,
        "title": title,
        "mtr": mtr,
        "positions": positions if positions is not None else [],
    }
    r = client.post("/requests", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _take_to_work(client, parent_id):
    """POST /requests/{id}/take-to-work → returns {tender_id, procedure_id}.

    Caller must be logged in as a user with zakupka edit rights.
    """
    r = client.post(f"/requests/{parent_id}/take-to-work")
    assert r.status_code == 200, r.text
    return r.json()


def _take_to_work_with_positions(client, code, title, mtr=None, positions=None):
    """Convenience: create a parent + positions (as admin) then take to work
    (as the same client) → returns the take-to-work JSON."""
    body = _create_request_via_api(
        client, code=code, title=title, mtr=mtr, positions=positions,
    )
    return _take_to_work(client, body["id"])


# ===========================================================================
# 1. GET /procurement empty
# ===========================================================================

def test_list_empty(client_admin):
    r = client_admin.get("/procurement")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


# ===========================================================================
# 2. After take-to-work → exactly 1 item with correct fields
# ===========================================================================

def test_list_after_take_to_work(client_admin):
    tw = _take_to_work_with_positions(
        client_admin,
        code="Z-002",
        title="Заявка в закупке",
        mtr="MTR-PARENT",
        positions=[
            {"name": "Болт", "qty": 10.0, "unit": "шт"},
            {"name": "Гайка", "qty": 5.0, "unit": "шт"},
        ],
    )
    proc_id = tw["procedure_id"]

    r = client_admin.get("/procurement")
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == proc_id
    assert item["proc"] is None
    assert item["tender_num"] is None
    assert item["code"] == "Z-002"
    assert item["title"] == "Заявка в закупке"
    # mtr falls back to parent.mtr when proc.mtr is NULL
    assert item["mtr"] == "MTR-PARENT"
    assert item["supplier"] is None
    assert item["status_zakup"] == "Новая"
    assert item["position_count"] == 2


# ===========================================================================
# 3. block='soprovozhdenie' procedure is NOT listed
# ===========================================================================

def test_list_excludes_soprovozhdenie_block(client_admin, db_seeded):
    from app.models import ParentRequest, Tender, Procedure
    # Create an awaiting parent directly (no API needed)
    pr = ParentRequest(
        code="SOPR-P", title="sopr", mtr=None, sostavitel="X", status="awaiting",
    )
    db_seeded.add(pr)
    db_seeded.commit()
    db_seeded.refresh(pr)
    t = Tender(parent_id=pr.id)
    db_seeded.add(t)
    db_seeded.commit()
    db_seeded.refresh(t)
    p = Procedure(tender_id=t.id, block="soprovozhdenie")
    db_seeded.add(p)
    db_seeded.commit()

    r = client_admin.get("/procurement")
    ids = {it["id"] for it in r.json()["items"]}
    assert p.id not in ids


# ===========================================================================
# 4. status_zakup='Отменена' hidden by default, present with include_archived=1
# ===========================================================================

def test_list_cancelled_hidden_by_default(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="CXL-L", title="cancelme", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]
    r_cancel = client_admin.post(f"/procedures/{proc_id}/cancel")
    assert r_cancel.status_code == 200

    # default: hidden
    r_def = client_admin.get("/procurement")
    ids_def = {it["id"] for it in r_def.json()["items"]}
    assert proc_id not in ids_def

    # archived: shown
    r_arch = client_admin.get("/procurement?include_archived=1")
    ids_arch = {it["id"] for it in r_arch.json()["items"]}
    assert proc_id in ids_arch


# ===========================================================================
# 5. status_zakup='Новая' IS in the active list
# ===========================================================================

def test_list_includes_novaya_status(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="NOV-L", title="novaya", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]

    r = client_admin.get("/procurement")
    items = r.json()["items"]
    target = next(it for it in items if it["id"] == proc_id)
    assert target["status_zakup"] == "Новая"


# ===========================================================================
# 6. Search matches code / tender.num / proc / supplier / title; non-match 0
# ===========================================================================

def test_search_matches_fields(client_admin):
    # A — code match only
    _take_to_work_with_positions(
        client_admin, code="SRCH-CODE", title="t1", positions=[{"name": "x", "qty": 1.0}],
    )
    # B — title match
    _take_to_work_with_positions(
        client_admin, code="SRCH-B", title="УникальныйТайтл", positions=[{"name": "x", "qty": 1.0}],
    )
    # C — proc match (set proc directly)
    tw_c = _take_to_work_with_positions(
        client_admin, code="SRCH-C", title="t3", positions=[{"name": "x", "qty": 1.0}],
    )
    client_admin.patch(f"/procedures/{tw_c['procedure_id']}", json={"proc": "PROC-XYZ"})
    # D — supplier match
    tw_d = _take_to_work_with_positions(
        client_admin, code="SRCH-D", title="t4", positions=[{"name": "x", "qty": 1.0}],
    )
    client_admin.patch(f"/procedures/{tw_d['procedure_id']}", json={"supplier": "ООО Ромашка"})
    # E — tender.num match
    tw_e = _take_to_work_with_positions(
        client_admin, code="SRCH-E", title="t5", positions=[{"name": "x", "qty": 1.0}],
    )
    client_admin.patch(f"/procedures/{tw_e['procedure_id']}", json={"tender_num": "TENDER-999"})

    def _ids(query):
        r = client_admin.get(f"/procurement?search={query}")
        return {it["id"] for it in r.json()["items"]}

    assert tw_c["procedure_id"] in _ids("proc-xyz")          # proc
    assert tw_d["procedure_id"] in _ids("ромашка")           # supplier (cyr case-insensitive)
    assert tw_e["procedure_id"] in _ids("tender-999")        # tender.num
    # code + title
    by_code = _ids("srch-code")
    assert any(c == "SRCH-CODE" for c in [it.get("code") for it in client_admin.get("/procurement?search=srch-code").json()["items"]])
    by_title = client_admin.get("/procurement?search=уникальныйтайтл").json()["items"]
    assert len(by_title) == 1

    # non-match
    r_no = client_admin.get("/procurement?search=НОЕТAKOГОСЛОВА123")
    assert r_no.json()["total"] == 0


# ===========================================================================
# 7. Each sort key orders rows; invalid sort falls back to default (no 500)
# ===========================================================================

def test_sort_keys_and_invalid_fallback(client_admin):
    # Build 3 procedures with distinct proc values for sorting
    tw1 = _take_to_work_with_positions(
        client_admin, code="SRT-A", title="a", positions=[{"name": "x", "qty": 1.0}],
    )
    tw2 = _take_to_work_with_positions(
        client_admin, code="SRT-B", title="b", positions=[{"name": "x", "qty": 1.0}],
    )
    tw3 = _take_to_work_with_positions(
        client_admin, code="SRT-C", title="c", positions=[{"name": "x", "qty": 1.0}],
    )
    client_admin.patch(f"/procedures/{tw1['procedure_id']}", json={"proc": "proc-zzz"})
    client_admin.patch(f"/procedures/{tw2['procedure_id']}", json={"proc": "proc-aaa"})
    client_admin.patch(f"/procedures/{tw3['procedure_id']}", json={"proc": "proc-mmm"})

    # valid sort by proc asc
    r = client_admin.get("/procurement?sort=proc")
    items = r.json()["items"]
    procs = [it["proc"] for it in items if it["proc"]]
    assert procs == sorted(procs)
    assert procs[0] == "proc-aaa"
    assert procs[-1] == "proc-zzz"

    # invalid sort → default (created_at desc) — no 500
    r_bad = client_admin.get("/procurement?sort=definitely-not-a-real-key")
    assert r_bad.status_code == 200
    items_bad = r_bad.json()["items"]
    # most-recently-created first: tw3 created last
    ids = [it["id"] for it in items_bad]
    assert ids.index(tw3["procedure_id"]) < ids.index(tw1["procedure_id"])


# ===========================================================================
# 8. total correct across pages; page=2 returns second slice
# ===========================================================================

def test_pagination_page2(client_admin):
    created = []
    for code in ["PG-1", "PG-2", "PG-3"]:
        tw = _take_to_work_with_positions(
            client_admin, code=code, title=code, positions=[{"name": "x", "qty": 1.0}],
        )
        created.append(tw["procedure_id"])

    r1 = client_admin.get("/procurement?page=1&page_size=2")
    assert r1.json()["total"] == 3
    assert len(r1.json()["items"]) == 2

    r2 = client_admin.get("/procurement?page=2&page_size=2")
    assert len(r2.json()["items"]) == 1
    # page2 item is distinct from page1 items
    page1_ids = {it["id"] for it in r1.json()["items"]}
    page2_ids = {it["id"] for it in r2.json()["items"]}
    assert page2_ids.isdisjoint(page1_ids)


# ===========================================================================
# 9. Null proc/tender_num/supplier do not crash (serialize as null)
# ===========================================================================

def test_list_null_fields_serialize(client_admin):
    _take_to_work_with_positions(
        client_admin, code="NULL-1", title="nulls", positions=[{"name": "x", "qty": 1.0}],
    )
    r = client_admin.get("/procurement")
    item = r.json()["items"][0]
    # proc, tender_num, supplier all NULL right after take-to-work
    assert item["proc"] is None
    assert item["tender_num"] is None
    assert item["supplier"] is None
    assert item["fio_zakupshchik"] is None
    assert item["pub_start"] is None
    assert item["pub_end"] is None


# ===========================================================================
# 10. GET /procedures/{id} 200 with detail + positions[*].price; 404 unknown
# ===========================================================================

def test_detail_with_positions_price(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="DET-1", title="detail", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]

    r = client_admin.get(f"/procedures/{proc_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == proc_id
    assert body["block"] == "zakupka"
    assert body["code"] == "DET-1"
    assert body["title"] == "detail"
    assert body["tender_id"] == tw["tender_id"]
    assert body["parent_id"] is not None
    assert isinstance(body["positions"], list)
    assert len(body["positions"]) == 1
    # price key present (nullable int)
    assert "price" in body["positions"][0]
    # block_entered_at OMITTED
    assert "block_entered_at" not in body


def test_detail_not_found_404(client_admin):
    r = client_admin.get("/procedures/99999")
    assert r.status_code == 404


# ===========================================================================
# 11. PATCH proc/supplier/mtr/pub_start/pub_end/fio_zakupshchik persist;
#     tender_num updates tender.num
# ===========================================================================

def test_patch_fields_persist(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="PAT-1", title="patch", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]

    r = client_admin.patch(
        f"/procedures/{proc_id}",
        json={
            "proc": "PROC-1",
            "supplier": "ООО Поставщик",
            "mtr": "MTR-NEW",
            "pub_start": "2026-01-01",
            "pub_end": "2026-02-01",
            "fio_zakupshchik": "Иванов И.И.",
        },
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["proc"] == "PROC-1"
    assert got["supplier"] == "ООО Поставщик"
    assert got["mtr"] == "MTR-NEW"
    assert got["pub_start"] == "2026-01-01"
    assert got["pub_end"] == "2026-02-01"
    assert got["fio_zakupshchik"] == "Иванов И.И."

    # GET it back
    r2 = client_admin.get(f"/procedures/{proc_id}")
    again = r2.json()
    assert again["proc"] == "PROC-1"
    assert again["supplier"] == "ООО Поставщик"


def test_patch_tender_num_updates_tender(client_admin, db_seeded):
    from app.models import Tender
    tw = _take_to_work_with_positions(
        client_admin, code="PAT-TN", title="patch num", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]
    tender_id = tw["tender_id"]

    r = client_admin.patch(f"/procedures/{proc_id}", json={"tender_num": "T-ABC"})
    assert r.status_code == 200, r.text
    assert r.json()["tender_num"] == "T-ABC"

    db_seeded.expire_all()
    tender = db_seeded.get(Tender, tender_id)
    assert tender.num == "T-ABC"


# ===========================================================================
# 12. PATCH status_zakup: each of 6 dict values → 200; garbage → 422;
#     Новая → 422; Отменена → 422
# ===========================================================================

VALID_ZAKUP_STATUSES = [
    "Приём заявок",
    "Торги",
    "Тех. экспертиза",
    "Дозапросы",
    "Согласование",
    "На сделку",
]


def test_patch_status_zakup_all_six_dict_values(client_admin):
    for value in VALID_ZAKUP_STATUSES:
        tw = _take_to_work_with_positions(
            client_admin,
            code=f"STZ-{value[:3]}",
            title=value,
            positions=[{"name": "x", "qty": 1.0}],
        )
        r = client_admin.patch(
            f"/procedures/{tw['procedure_id']}", json={"status_zakup": value},
        )
        assert r.status_code == 200, (value, r.text)
        assert r.json()["status_zakup"] == value


def test_patch_status_zakup_garbage_422(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="STZ-BAD", title="bad", positions=[{"name": "x", "qty": 1.0}],
    )
    r = client_admin.patch(
        f"/procedures/{tw['procedure_id']}", json={"status_zakup": "Несуществующий статус"},
    )
    assert r.status_code == 422


def test_patch_status_zakup_novaya_rejected_422(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="STZ-NOV", title="nov", positions=[{"name": "x", "qty": 1.0}],
    )
    r = client_admin.patch(
        f"/procedures/{tw['procedure_id']}", json={"status_zakup": "Новая"},
    )
    assert r.status_code == 422


def test_patch_status_zakup_otmenena_rejected_422(client_admin):
    tw = _take_to_work_with_positions(
        client_admin, code="STZ-OTM", title="otm", positions=[{"name": "x", "qty": 1.0}],
    )
    r = client_admin.patch(
        f"/procedures/{tw['procedure_id']}", json={"status_zakup": "Отменена"},
    )
    assert r.status_code == 422


# ===========================================================================
# 13. PATCH duplicate non-null proc → 409; duplicate non-null tender_num → 409;
#     NULL proc/tender_num on multiple rows → allowed
# ===========================================================================

def test_patch_duplicate_proc_409(client_admin):
    tw1 = _take_to_work_with_positions(
        client_admin, code="DUP-P1", title="p1", positions=[{"name": "x", "qty": 1.0}],
    )
    tw2 = _take_to_work_with_positions(
        client_admin, code="DUP-P2", title="p2", positions=[{"name": "x", "qty": 1.0}],
    )
    client_admin.patch(f"/procedures/{tw1['procedure_id']}", json={"proc": "UNIQ-PROC"})

    r = client_admin.patch(
        f"/procedures/{tw2['procedure_id']}", json={"proc": "UNIQ-PROC"},
    )
    assert r.status_code == 409
    assert "proc already exists" in r.json()["detail"]


def test_patch_duplicate_tender_num_409(client_admin):
    tw1 = _take_to_work_with_positions(
        client_admin, code="DUP-T1", title="t1", positions=[{"name": "x", "qty": 1.0}],
    )
    tw2 = _take_to_work_with_positions(
        client_admin, code="DUP-T2", title="t2", positions=[{"name": "x", "qty": 1.0}],
    )
    client_admin.patch(f"/procedures/{tw1['procedure_id']}", json={"tender_num": "UNIQ-NUM"})

    r = client_admin.patch(
        f"/procedures/{tw2['procedure_id']}", json={"tender_num": "UNIQ-NUM"},
    )
    assert r.status_code == 409
    assert "tender num already exists" in r.json()["detail"]


def test_patch_null_proc_and_tender_num_on_multiple_rows_allowed(client_admin):
    # Two procedures both with NULL proc — already the case after take-to-work.
    tw1 = _take_to_work_with_positions(
        client_admin, code="NULL-P1", title="n1", positions=[{"name": "x", "qty": 1.0}],
    )
    tw2 = _take_to_work_with_positions(
        client_admin, code="NULL-P2", title="n2", positions=[{"name": "x", "qty": 1.0}],
    )
    # Explicitly PATCH both to null — must NOT 409.
    r1 = client_admin.patch(f"/procedures/{tw1['procedure_id']}", json={"proc": None})
    assert r1.status_code == 200, r1.text
    r2 = client_admin.patch(f"/procedures/{tw2['procedure_id']}", json={"proc": None})
    assert r2.status_code == 200, r2.text
    rt1 = client_admin.patch(f"/procedures/{tw1['procedure_id']}", json={"tender_num": None})
    assert rt1.status_code == 200, rt1.text
    rt2 = client_admin.patch(f"/procedures/{tw2['procedure_id']}", json={"tender_num": None})
    assert rt2.status_code == 200, rt2.text


# ===========================================================================
# 14. PATCH 404 unknown id
# ===========================================================================

def test_patch_not_found_404(client_admin):
    r = client_admin.patch("/procedures/99999", json={"proc": "X"})
    assert r.status_code == 404


# ===========================================================================
# 15. cancel → status_zakup='Отменена' + audit; cancel again → 409;
#     uncancel → status_zakup='Новая' + audit; uncancel when not cancelled → 409;
#     block stays 'zakupka' throughout
# ===========================================================================

def test_cancel_then_uncancel_lifecycle(client_admin, db_seeded):
    from app.models import AuditLog, Procedure
    tw = _take_to_work_with_positions(
        client_admin, code="CUC-1", title="lifecycle", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]

    # cancel
    r_cancel = client_admin.post(f"/procedures/{proc_id}/cancel")
    assert r_cancel.status_code == 200, r_cancel.text
    assert r_cancel.json()["status_zakup"] == "Отменена"
    assert r_cancel.json()["block"] == "zakupka"

    # cancel again → 409
    r_cancel2 = client_admin.post(f"/procedures/{proc_id}/cancel")
    assert r_cancel2.status_code == 409

    # uncancel
    r_unc = client_admin.post(f"/procedures/{proc_id}/uncancel")
    assert r_unc.status_code == 200, r_unc.text
    assert r_unc.json()["status_zakup"] == "Новая"
    assert r_unc.json()["block"] == "zakupka"

    # uncancel when not cancelled → 409
    r_unc2 = client_admin.post(f"/procedures/{proc_id}/uncancel")
    assert r_unc2.status_code == 409

    # block stayed zakupka
    db_seeded.expire_all()
    proc = db_seeded.get(Procedure, proc_id)
    assert proc.block == "zakupka"

    # audit rows for both actions
    db_seeded.expire_all()
    cancel_rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="procedure", entity_id=proc_id, action="cancel")
        .all()
    )
    assert len(cancel_rows) == 1
    unc_rows = (
        db_seeded.query(AuditLog)
        .filter_by(entity_kind="procedure", entity_id=proc_id, action="uncancel")
        .all()
    )
    assert len(unc_rows) == 1


def test_cancel_not_found_404(client_admin):
    r = client_admin.post("/procedures/99999/cancel")
    assert r.status_code == 404


def test_uncancel_not_found_404(client_admin):
    r = client_admin.post("/procedures/99999/uncancel")
    assert r.status_code == 404


# ===========================================================================
# 16. RBAC: _make_kompl_emp PATCH/cancel/uncancel → 403; GET list + GET detail → 200
# ===========================================================================

@pytest.fixture()
def client_kompl_emp(client_seeded, db_seeded, client_admin):
    """Logged in as a Комплектация employee (no zakupka edit). A procedure
    is created first via admin, then we switch session to the kompl emp."""
    tw = _take_to_work_with_positions(
        client_admin, code="RBAC-1", title="rbac", positions=[{"name": "x", "qty": 1.0}],
    )
    proc_id = tw["procedure_id"]
    u = _make_kompl_emp(db_seeded)
    _login_as(client_seeded, u.email, "userpass123")
    return client_seeded, proc_id


def test_rbac_get_list_and_detail_ok_for_kompl(client_kompl_emp):
    client, proc_id = client_kompl_emp
    r_list = client.get("/procurement")
    assert r_list.status_code == 200
    r_det = client.get(f"/procedures/{proc_id}")
    assert r_det.status_code == 200


def test_rbac_patch_403_for_kompl(client_kompl_emp):
    client, proc_id = client_kompl_emp
    r = client.patch(f"/procedures/{proc_id}", json={"proc": "X"})
    assert r.status_code == 403


def test_rbac_cancel_403_for_kompl(client_kompl_emp):
    client, proc_id = client_kompl_emp
    r = client.post(f"/procedures/{proc_id}/cancel")
    assert r.status_code == 403


def test_rbac_uncancel_403_for_kompl(client_kompl_emp):
    client, proc_id = client_kompl_emp
    r = client.post(f"/procedures/{proc_id}/uncancel")
    assert r.status_code == 403
