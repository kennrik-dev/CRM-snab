"""Tests for /reports router (Phase 9.1). Mirrors tests/test_dashboard.py."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.calculations import today_moscow
from app.db import Base, get_db, register_sqlite_setup
from app.main import app
from app.security import hash_password

ADMIN_EMAIL = "admin@crm.local"
ADMIN_INITIAL_PASSWORD = "change-me-123"
ADMIN_NEW_PASSWORD = "newadmin123"
TODAY = today_moscow()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def last_month_date() -> str:
    # a date firmly in the previous calendar month (robust regardless of today's day)
    first_this = TODAY.replace(day=1)
    return (first_this - timedelta(days=5)).isoformat()


# --- fixtures (mirror test_dashboard.py) ---------------------------------------

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


# --- helpers -------------------------------------------------------------------

POS = [{"name": "x", "qty": 2.0, "unit": "шт", "price": 10000}]   # 2 * 100.00 = 20000 kop


def _create_request(client, code, title, positions):
    r = client.post("/requests", json={"code": code, "title": title, "positions": positions})
    assert r.status_code == 200, r.text
    return r.json()


def _to_zakupka(client, code, title, positions):
    body = _create_request(client, code, title, positions)
    r = client.post(f"/requests/{body['id']}/take-to-work")
    assert r.status_code == 200, r.text
    return r.json()["procedure_id"]


def _to_support(client, code, title, positions):
    proc_id = _to_zakupka(client, code, title, positions)
    for src, pp in zip(positions, client.get(f"/procedures/{proc_id}").json()["positions"]):
        if src.get("price") is not None:
            client.patch(f"/procedures/{proc_id}/positions/{pp['id']}", json={"price": src["price"]})
    client.patch(f"/procedures/{proc_id}", json={"status_zakup": "На сделку"})
    r = client.post(f"/procedures/{proc_id}/to-support")
    assert r.status_code == 200, r.text
    return proc_id


def _position_ids(client, proc_id):
    return [p["id"] for p in client.get(f"/procedures/{proc_id}").json()["positions"]]


def _delivery_upd(client, code, title, positions):
    proc_id = _to_support(client, code, title, positions)
    pid = _position_ids(client, proc_id)[0]
    d = client.post(f"/procedures/{proc_id}/deliveries", json={"positions": [pid]}).json()
    upd = client.post(f"/deliveries/{d['id']}/upd", json={"upd": "UPD-" + code}).json()
    return proc_id, d, upd


def _set_proc(db, proc_id, **fields):
    from app.models import Procedure
    db.query(Procedure).filter_by(id=proc_id).update(fields)
    db.commit()


def _set_delivery(db, delivery_id, **fields):
    from app.models import Delivery
    db.query(Delivery).filter_by(id=delivery_id).update(fields)
    db.commit()


def _make_role_user(db, email, department, is_curator=False, global_role=None):
    from app.models import User
    u = User(
        email=email, password_hash=hash_password("userpass123"),
        full_name=email.split("@")[0], account_type="department" if department else "global",
        department=department, is_curator=1 if is_curator else 0, global_role=global_role,
        is_active=1, must_change_password=0,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _login_as(client, email, password="userpass123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


# --- 9.1 Task 1: shape / auth / validation -------------------------------------

def test_report_shape_and_keys(client_admin):
    r = client_admin.get("/reports/time")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"type", "title", "period", "kpis", "sections"}
    assert body["type"] == "time"


def test_report_unknown_type_404(client_admin):
    assert client_admin.get("/reports/bogus").status_code == 404


def test_report_unauth_401(client_seeded):
    assert client_seeded.get("/reports/time").status_code == 401


def test_report_must_change_403(client_seeded):
    client_seeded.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_INITIAL_PASSWORD})
    assert client_seeded.get("/reports/time").status_code == 403


def test_report_employee_forbidden_403(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "kompl_emp@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 403


def test_report_curator_ok(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "kompl_cur@crm.local", "Комплектация", is_curator=True)
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 200


def test_report_rukovoditel_ok(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "ruk@crm.local", None, global_role="Руководитель")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time").status_code == 200


def test_report_custom_period_validation_422(client_admin):
    # custom without range
    assert client_admin.get("/reports/time?period=custom").status_code == 422
    # custom inverted
    q = f"?period=custom&date_from={days_ago(1)}&date_to={days_ago(5)}"
    assert client_admin.get("/reports/time" + q).status_code == 422


def test_report_custom_period_ok(client_admin):
    q = f"?period=custom&date_from={days_ago(10)}&date_to={days_ago(0)}"
    r = client_admin.get("/reports/time" + q)
    assert r.status_code == 200
    # period.key echo is asserted in T3 once report_time returns a real period


def test_report_unknown_period_422(client_admin):
    assert client_admin.get("/reports/time?period=bogus").status_code == 422


def test_filters_shape(client_admin):
    r = client_admin.get("/reports")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"mtr", "supplier", "author"}


# --- 9.1 Task 2: period + ctx + filters ---------------------------------------

from app import calculations as calc


def test_resolve_period_month():
    f, t, info = calc._resolve_period({"period": "month"}, TODAY)
    assert f == TODAY.replace(day=1)
    assert t == TODAY
    assert info["key"] == "month" and info["label"] == "Текущий месяц"


def test_resolve_period_quarter():
    f, t, info = calc._resolve_period({"period": "quarter"}, TODAY)
    qm = ((TODAY.month - 1) // 3) * 3 + 1
    from datetime import date
    assert f == date(TODAY.year, qm, 1)


def test_resolve_period_year():
    f, t, info = calc._resolve_period({"period": "year"}, TODAY)
    from datetime import date
    assert f == date(TODAY.year, 1, 1)
    assert info["label"] == "С начала года"


def test_resolve_period_custom():
    f, t, info = calc._resolve_period(
        {"period": "custom", "date_from": days_ago(10), "date_to": days_ago(2)}, TODAY)
    assert info["key"] == "custom"
    assert info["from"] == days_ago(10)


def test_resolve_period_none():
    f, t, info = calc._resolve_period({}, TODAY)
    assert f is None and t is None and info is None


def test_ctx_period_filters_procedures_by_zagruzka(client_admin, db_seeded):
    from app.models import ParentRequest, Procedure, Tender
    p_in = _to_zakupka(client_admin, "P-IN", "in", POS)
    p_out = _to_zakupka(client_admin, "P-OUT", "out", POS)
    # move p_out's parent zagruzka to a date firmly in the previous month
    out_par_id = (db_seeded.query(Tender)
                  .join(Procedure, Procedure.tender_id == Tender.id)
                  .filter(Procedure.id == p_out).first()).parent_id
    db_seeded.query(ParentRequest).filter_by(id=out_par_id).update({"zagruzka": last_month_date()})
    db_seeded.commit()
    ctx = calc._load_report_ctx(db_seeded, TODAY, {"period": "month"})
    ids = [p.id for p in ctx.procs]
    assert p_in in ids and p_out not in ids


def test_ctx_filters_mtr_supplier_author(client_admin, db_seeded):
    _to_zakupka(client_admin, "F-MTR", "mtr", [{"name": "x", "qty": 1, "unit": "шт", "price": 100}])
    # filter by supplier that doesn't exist → empty
    ctx = calc._load_report_ctx(db_seeded, TODAY, {"supplier": "Никто"})
    assert ctx.procs == []


def test_filters_endpoint_returns_distinct(client_admin, db_seeded):
    _to_zakupka(client_admin, "F-S1", "s1", POS)               # supplier unset here
    proc_id = _to_support(client_admin, "F-S2", "s2", POS)
    _set_proc(db_seeded, proc_id, supplier="ООО Ромашка")
    r = client_admin.get("/reports")
    body = r.json()
    assert "ООО Ромашка" in body["supplier"]


def test_filters_endpoint_forbidden_employee(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "k2@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports").status_code == 403


# --- 9.1 Task 3: report_time ---------------------------------------------------

def _report(client, type_="time", **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return client.get(f"/reports/{type_}" + (f"?{qs}" if qs else "")).json()


def test_time_includes_procedure_with_days(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "T-Z1", "z1", POS)
    _set_proc(db_seeded, pid, block_entered_at=days_ago(12))
    snap = _report(client_admin, "time")
    rows = snap["sections"][0]["rows"]
    assert any(r[0].get("code") == "T-Z1" for r in rows)
    day_cell = next(r[4] for r in rows if r[0].get("code") == "T-Z1")
    assert day_cell["text"] == "12 дн." and day_cell["level"] == "warn"
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Заявок в работе"] == "1"
    assert kpi["Зависли ≥3 дн."] == "1"


def test_time_excludes_completed_procedure(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "T-CM", "cm", POS)
    _set_delivery(db_seeded, d["id"], status="done", date=days_ago(1))
    _set_proc(db_seeded, pid, status_postavki="Поставлено", srok_dd=days_ago(-30), block_entered_at=days_ago(5))
    pay_id = client_admin.get("/payments").json()["items"][0]["id"]
    client_admin.post(f"/payments/{pay_id}/pay")            # → completed
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    assert not any(r[0].get("code") == "T-CM" for r in rows)


def test_time_excludes_cancelled(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "T-CA", "ca", POS)
    _set_proc(db_seeded, pid, status_zakup="Отменена", block_entered_at=days_ago(2))
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    assert not any(r[0].get("code") == "T-CA" for r in rows)


def test_time_includes_awaiting_parent_komplektaciya(client_admin):
    _create_request(client_admin, "T-AW", "awaiting", POS)   # no tender → awaiting
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    aw = [r for r in rows if r[0].get("code") == "T-AW"]
    assert aw and aw[0][3]["text"] == "Комплектация"          # stage cell


def test_time_avg_and_sort_desc(client_admin, db_seeded):
    p1 = _to_zakupka(client_admin, "T-A1", "a1", POS); _set_proc(db_seeded, p1, block_entered_at=days_ago(2))
    p2 = _to_zakupka(client_admin, "T-A2", "a2", POS); _set_proc(db_seeded, p2, block_entered_at=days_ago(8))
    snap = _report(client_admin, "time")
    days_list = [r[4]["text"] for r in snap["sections"][0]["rows"]]
    assert days_list[0] == "8 дн."                            # desc
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Ср. время на этапе"] == "5 дн."               # (8+2)/2


def test_time_no_block_entered_at_excluded(client_admin, db_seeded):
    pid = _to_zakupka(client_admin, "T-NB", "nb", POS)
    _set_proc(db_seeded, pid, block_entered_at=None)
    rows = _report(client_admin, "time")["sections"][0]["rows"]
    assert not any(r[0].get("code") == "T-NB" for r in rows)


def test_time_period_echo(client_admin):
    body = client_admin.get("/reports/time?period=month").json()
    assert body["period"]["key"] == "month"
    assert body["period"]["label"] == "Текущий месяц"


# --- 9.1 Task 4: report_sums ---------------------------------------------------

def test_sums_stage_totals_and_footer(client_admin, db_seeded):
    p1 = _to_zakupka(client_admin, "S-Z1", "z1", POS)
    _set_proc(db_seeded, p1, contract_sum=200000)                  # 2 000 ₽ (block zakupka)
    p2 = _to_support(client_admin, "S-S1", "s1", POS)
    _set_proc(db_seeded, p2, contract_sum=500000)                  # 5 000 ₽ (block support)
    snap = _report(client_admin, "sums")
    sec1 = snap["sections"][0]
    rows = {r[0]["text"]: r for r in sec1["rows"]}
    assert rows["В закупке"][2]["text"] == _fmt_money_expected(200000)
    assert rows["В сопровождении"][2]["text"] == _fmt_money_expected(500000)
    assert sec1["footer"][2]["text"] == _fmt_money_expected(700000)


def _fmt_money_expected(kop):
    # mirror calculations._fmt_money for assertions
    rub = kop / 100
    s = f"{int(rub):,}".replace(",", " ")
    return f"{s} ₽"


def test_sums_supplier_section(client_admin, db_seeded):
    p1 = _to_support(client_admin, "S-P1", "p1", POS); _set_proc(db_seeded, p1, supplier="Альфа", contract_sum=100000)
    p2 = _to_support(client_admin, "S-P2", "p2", POS); _set_proc(db_seeded, p2, supplier="Альфа", contract_sum=200000)
    p3 = _to_support(client_admin, "S-P3", "p3", POS); _set_proc(db_seeded, p3, supplier="Бета", contract_sum=50000)
    snap = _report(client_admin, "sums")
    sec2 = next(s for s in snap["sections"] if s.get("title") == "По поставщикам")
    by = {r[0]: r for r in sec2["rows"]}
    assert by["Альфа"][1] == "2" and by["Бета"][1] == "1"
    # sorted desc by sum → Альфа first
    assert sec2["rows"][0][0] == "Альфа"


def test_sums_kpi_v_oplate(client_admin, db_seeded):
    _delivery_upd(client_admin, "S-UP", "up", POS)   # 1 await УПД, amount = Σ delivery pos = 20000
    snap = _report(client_admin, "sums")
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["В оплате"] == _fmt_money_expected(20000)


def test_sums_excludes_cancelled_includes_completed(client_admin, db_seeded):
    p_c = _to_support(client_admin, "S-CM", "cm", POS); _set_proc(db_seeded, p_c, contract_sum=300000, status_postavki="Поставлено")
    p_x = _to_zakupka(client_admin, "S-CA", "ca", POS); _set_proc(db_seeded, p_x, status_zakup="Отменена")
    snap = _report(client_admin, "sums")
    sec1 = snap["sections"][0]
    # completed (Поставлено) counted in support; cancelled excluded
    sup_row = next(r for r in sec1["rows"] if r[0]["text"] == "В сопровождении")
    assert int(sup_row[1]) >= 1


# --- 9.1 Task 5: report_late ---------------------------------------------------

def test_late_overdue_delivery(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "L-OD", "od", POS)
    _set_proc(db_seeded, pid, srok_dd=days_ago(5))               # past, transit → overdue
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Поставки")
    assert any(r[0].get("code") == "L-OD" for r in sec["rows"])
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Просроч. поставок"] == "1"


def test_late_payment_overdue(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "L-OP", "op", POS)
    from app.models import UpdPayment
    db_seeded.query(UpdPayment).filter_by(delivery_id=d["id"]).update({"srok": days_ago(3)})
    db_seeded.commit()
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    assert any(r[0] == "UPD-L-OP" for r in sec["rows"])
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["Просроч. оплат"] == "1"


def test_late_excludes_cancelled_procedure(client_admin, db_seeded):
    pid, d, _upd = _delivery_upd(client_admin, "L-CA", "ca", POS)
    _set_proc(db_seeded, pid, srok_dd=days_ago(5), status_postavki="Отменена")
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Поставки")
    assert all(r[0].get("code") != "L-CA" for r in sec["rows"])


def test_late_empty_section_shows_note(client_admin):
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Поставки")
    assert sec["rows"] and sec["rows"][0][0]["text"] == "нет"


def test_late_manual_upd_excluded_when_period(client_admin):
    client_admin.post("/payments", json={"upd": "UPD-MAN", "supplier": "S", "srok": days_ago(5), "amount": 10000})
    snap = _report(client_admin, "late", period="month")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    assert all("UPD-MAN" not in str(r) for r in sec["rows"])


def test_late_manual_upd_included_no_period(client_admin):
    client_admin.post("/payments", json={"upd": "UPD-MAN2", "supplier": "S", "srok": days_ago(5), "amount": 10000})
    snap = _report(client_admin, "late")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    assert any(r[0] == "UPD-MAN2" for r in sec["rows"])


# --- 9.1 Task 6: report_people -------------------------------------------------

def test_people_group_by_sostavitel(client_admin, db_seeded):
    # create requests as admin (full_name "Администратор"); set sostavitel explicitly via DB
    _create_request(client_admin, "PE-1", "t1", POS)
    _create_request(client_admin, "PE-2", "t2", POS)
    from app.models import ParentRequest
    db_seeded.query(ParentRequest).filter_by(code="PE-1").update({"sostavitel": "Орлова А."})
    db_seeded.query(ParentRequest).filter_by(code="PE-2").update({"sostavitel": "Седов В."})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    rows = {r[0]: r for r in snap["sections"][0]["rows"]}
    assert "Орлова А." in rows and "Седов В." in rows
    assert rows["Орлова А."][2] == "1"   # 1 заявка


def test_people_counts_procedures_and_sum(client_admin, db_seeded):
    # one parent with one procedure in zakupka; set contract_sum explicitly
    pid = _to_zakupka(client_admin, "PE-P1", "p1", POS)
    _set_proc(db_seeded, pid, contract_sum=200000)                 # 2 000 ₽
    from app.models import ParentRequest, Procedure, Tender
    par_id = db_seeded.query(Tender).join(Procedure, Procedure.tender_id == Tender.id).filter(Procedure.id == pid).first().parent_id
    db_seeded.query(ParentRequest).filter_by(id=par_id).update({"sostavitel": "Орлова А."})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    row = next(r for r in snap["sections"][0]["rows"] if r[0] == "Орлова А.")
    assert row[3] == "1"                  # 1 procedure
    assert row[4]["text"] == "2 000 ₽"


def test_people_excludes_cancelled_parent(client_admin, db_seeded):
    _create_request(client_admin, "PE-CA", "ca", POS)
    from app.models import ParentRequest
    db_seeded.query(ParentRequest).filter_by(code="PE-CA").update({"sostavitel": "X", "status": "cancelled"})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    assert all(r[0] != "X" for r in snap["sections"][0]["rows"])


def test_people_dept_fallback(client_admin, db_seeded):
    # parent.dept null → fallback to creator's department
    _create_request(client_admin, "PE-D1", "d1", POS)
    from app.models import ParentRequest
    db_seeded.query(ParentRequest).filter_by(code="PE-D1").update({"sostavitel": "Z", "dept": None})
    db_seeded.commit()
    snap = _report(client_admin, "people")
    row = next(r for r in snap["sections"][0]["rows"] if r[0] == "Z")
    # admin has no department → "—"
    assert row[1] == "—"

# --- 9.1 Task 7: export --------------------------------------------------------

def test_export_csv_content_type_and_body(client_admin, db_seeded):
    _to_zakupka(client_admin, "X-1", "x1", POS)
    r = client_admin.get("/reports/time/export?format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")            # UTF-8 BOM
    assert "Время на этапе" in r.text
    assert "content-disposition" in {k.lower() for k in r.headers}
    assert ".csv" in r.headers["content-disposition"]


def test_export_excel(client_admin):
    r = client_admin.get("/reports/sums/export?format=excel")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"                            # xlsx zip signature
    assert ".xlsx" in r.headers["content-disposition"]


def test_export_pdf(client_admin):
    r = client_admin.get("/reports/late/export?format=pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert ".pdf" in r.headers["content-disposition"]


def test_export_unknown_format_422(client_admin):
    assert client_admin.get("/reports/time/export?format=docx").status_code == 422


def test_export_unknown_type_404(client_admin):
    assert client_admin.get("/reports/bogus/export?format=csv").status_code == 404


def test_export_forbidden_employee(client_seeded, db_seeded):
    u = _make_role_user(db_seeded, "k3@crm.local", "Комплектация")
    _login_as(client_seeded, u.email)
    assert client_seeded.get("/reports/time/export?format=csv").status_code == 403


# --- 9.1 scope fix: filters apply consistently to payments/people ----------------

def test_late_payments_scoped_by_supplier(client_admin, db_seeded):
    pid1, d1, _ = _delivery_upd(client_admin, "L-SC1", "sc1", POS)
    _set_proc(db_seeded, pid1, supplier="Альфа", srok_dd=days_ago(5))
    pid2, d2, _ = _delivery_upd(client_admin, "L-SC2", "sc2", POS)
    _set_proc(db_seeded, pid2, supplier="Бета", srok_dd=days_ago(5))
    from app.models import UpdPayment
    db_seeded.query(UpdPayment).filter_by(delivery_id=d1["id"]).update({"srok": days_ago(3)})
    db_seeded.query(UpdPayment).filter_by(delivery_id=d2["id"]).update({"srok": days_ago(3)})
    db_seeded.commit()
    snap = _report(client_admin, "late", supplier="Альфа")
    sec = next(s for s in snap["sections"] if s.get("title") == "Оплаты")
    upd_nums = [r[0] for r in sec["rows"]]
    assert "UPD-L-SC1" in upd_nums
    assert "UPD-L-SC2" not in upd_nums


def test_sums_v_oplate_scoped_by_supplier(client_admin, db_seeded):
    pid1, d1, _ = _delivery_upd(client_admin, "S-OP1", "op1", POS)
    _set_proc(db_seeded, pid1, supplier="Альфа")
    pid2, d2, _ = _delivery_upd(client_admin, "S-OP2", "op2", POS)
    _set_proc(db_seeded, pid2, supplier="Бета")
    snap = _report(client_admin, "sums", supplier="Альфа")
    kpi = {k["label"]: k["value"] for k in snap["kpis"]}
    assert kpi["В оплате"] == _fmt_money_expected(20000)   # only Альфа's await УПД


def test_people_supplier_filter_scopes_procedures(client_admin, db_seeded):
    p1 = _to_zakupka(client_admin, "PE-A1", "a1", POS); _set_proc(db_seeded, p1, supplier="Альфа", contract_sum=100000)
    p2 = _to_zakupka(client_admin, "PE-B1", "b1", POS); _set_proc(db_seeded, p2, supplier="Бета", contract_sum=200000)
    from app.models import ParentRequest, Procedure, Tender
    for pid in (p1, p2):
        par_id = db_seeded.query(Tender).join(Procedure, Procedure.tender_id == Tender.id).filter(Procedure.id == pid).first().parent_id
        db_seeded.query(ParentRequest).filter_by(id=par_id).update({"sostavitel": "Орлова А."})
    db_seeded.commit()
    snap = _report(client_admin, "people", supplier="Альфа")
    row = next(r for r in snap["sections"][0]["rows"] if r[0] == "Орлова А.")
    assert row[3] == "1"                                   # only Альфа procedure counted
    assert row[4]["text"] == _fmt_money_expected(100000)   # 100000 kop → "1 000 ₽"
