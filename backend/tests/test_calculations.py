"""Unit tests for app.calculations (Phase 6.1). Pure functions, no HTTP/DB."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.calculations import (
    docs_aggregate,
    is_delivery_late,
    is_delivery_overdue,
    is_procedure_overdue,
    is_upd_overdue,
    overdue_pct,
    position_sum,
    procedure_sum,
    progress,
    today_moscow,
)

TODAY = date(2026, 6, 21)  # зафиксированное «сегодня» (Москва)


def _pos(qty, price=None, delivery_id=None):
    return SimpleNamespace(qty=qty, price=price, delivery_id=delivery_id)


def _delivery(status="transit", date_str=None, ttn=0, m15=0, upd=0, sert=0, did=1):
    return SimpleNamespace(id=did, status=status, date=date_str,
                           doc_ttn=ttn, doc_m15=m15, doc_upd=upd, doc_sert=sert)


# --- position_sum / procedure_sum -------------------------------------------------

def test_position_sum_qty_times_price_kopecks():
    assert position_sum(_pos(10.0, 15000)) == 150000  # 10 * 150.00 ₽

def test_position_sum_no_price_is_zero():
    assert position_sum(_pos(10.0, None)) == 0

def test_position_sum_fractional_qty_rounded():
    assert position_sum(_pos(1.5, 10000)) == 15000  # 1.5 * 100.00

def test_procedure_sum_sums_positions():
    assert procedure_sum([_pos(2.0, 10000), _pos(1.0, 5000)]) == 25000

def test_procedure_sum_empty_is_zero():
    assert procedure_sum([]) == 0


# --- progress --------------------------------------------------------------------

def test_progress_zero_positions():
    assert progress([], []) == (0, 0, 0.0)

def test_progress_none_done():
    # 3 positions, none in a done delivery
    d = _delivery(status="transit", did=7)
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=None), _pos(1, 100, delivery_id=7)]
    assert progress(positions, [d]) == (0, 3, 0.0)

def test_progress_partial_done():
    d_done = _delivery(status="done", did=7)
    d_transit = _delivery(status="transit", did=8)
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=8), _pos(1, 100, delivery_id=None)]
    delivered, total, pct = progress(positions, [d_done, d_transit])
    assert (delivered, total) == (1, 3)
    assert round(pct, 2) == round(100 / 3, 2)

def test_progress_all_done():
    d = _delivery(status="done", did=7)
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=7)]
    assert progress(positions, [d]) == (2, 2, 100.0)


# --- is_delivery_overdue / late --------------------------------------------------

def test_delivery_overdue_transit_past_srok():
    d = _delivery(status="transit")
    assert is_delivery_overdue(d, "2026-06-01", TODAY) is True

def test_delivery_overdone_not_overdue():
    d = _delivery(status="done", date_str="2026-06-10")
    assert is_delivery_overdue(d, "2026-06-01", TODAY) is False

def test_delivery_overdue_future_srok_false():
    d = _delivery(status="transit")
    assert is_delivery_overdue(d, "2026-07-01", TODAY) is False

def test_delivery_overdue_no_srok_false():
    d = _delivery(status="transit")
    assert is_delivery_overdue(d, None, TODAY) is False

def test_delivery_late_done_after_srok():
    d = _delivery(status="done", date_str="2026-06-10")
    assert is_delivery_late(d, "2026-06-01", TODAY) is True

def test_delivery_late_done_before_srok_false():
    d = _delivery(status="done", date_str="2026-05-01")
    assert is_delivery_late(d, "2026-06-01", TODAY) is False

def test_delivery_late_transit_false():
    d = _delivery(status="transit")
    assert is_delivery_late(d, "2026-06-01", TODAY) is False


# --- is_procedure_overdue --------------------------------------------------------

def test_procedure_overdue_past_srok_not_delivered():
    assert is_procedure_overdue("2026-06-01", "В поставке", TODAY) is True

def test_procedure_overdue_past_srok_delivered_false():
    assert is_procedure_overdue("2026-06-01", "Поставлено", TODAY) is False

def test_procedure_overdue_future_srok_false():
    assert is_procedure_overdue("2026-07-01", "В поставке", TODAY) is False

def test_procedure_overdue_no_srok_false():
    assert is_procedure_overdue(None, "В поставке", TODAY) is False


# --- overdue_pct -----------------------------------------------------------------

def test_overdue_pct_no_positions_zero():
    assert overdue_pct([], [], "2026-06-01", TODAY) == 0.0

def test_overdue_pct_all_late_hundred():
    d = _delivery(status="transit", did=7)  # transit past srok → overdue
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=7)]
    assert overdue_pct(positions, [d], "2026-06-01", TODAY) == 100.0

def test_overdue_pct_partial():
    d_over = _delivery(status="transit", did=7)
    d_ok = _delivery(status="done", date_str="2026-05-01", did=8)  # done before srok → not late
    positions = [_pos(1, 100, delivery_id=7), _pos(1, 100, delivery_id=8), _pos(1, 100, delivery_id=None)]
    assert round(overdue_pct(positions, [d_over, d_ok], "2026-06-01", TODAY), 2) == round(100 / 3, 2)

def test_overdue_pct_none_late_zero():
    d = _delivery(status="done", date_str="2026-05-01", did=7)
    positions = [_pos(1, 100, delivery_id=7)]
    assert overdue_pct(positions, [d], "2026-06-01", TODAY) == 0.0


# --- docs_aggregate --------------------------------------------------------------

def test_docs_aggregate_no_deliveries_all_false():
    assert docs_aggregate([]) == {"ttn": False, "m15": False, "upd": False, "sert": False}

def test_docs_aggregate_single_all_set():
    d = _delivery(ttn=1, m15=1, upd=1, sert=1)
    assert docs_aggregate([d]) == {"ttn": True, "m15": True, "upd": True, "sert": True}

def test_docs_aggregate_two_one_missing_flag():
    d1 = _delivery(ttn=1, m15=1, upd=1, sert=1, did=1)
    d2 = _delivery(ttn=0, m15=1, upd=1, sert=1, did=2)  # missing ttn in d2
    agg = docs_aggregate([d1, d2])
    assert agg["ttn"] is False   # not in ALL
    assert agg["m15"] is True
    assert agg["upd"] is True
    assert agg["sert"] is True


# --- is_upd_overdue --------------------------------------------------------------

def test_upd_overdue_await_past_srok():
    u = SimpleNamespace(pay_status="await", srok="2026-06-01")
    assert is_upd_overdue(u, TODAY) is True

def test_upd_overdue_paid_false():
    u = SimpleNamespace(pay_status="paid", srok="2026-06-01")
    assert is_upd_overdue(u, TODAY) is False

def test_upd_overdue_await_future_false():
    u = SimpleNamespace(pay_status="await", srok="2026-07-01")
    assert is_upd_overdue(u, TODAY) is False

def test_upd_overdue_no_srok_false():
    u = SimpleNamespace(pay_status="await", srok=None)
    assert is_upd_overdue(u, TODAY) is False


# --- today_moscow ----------------------------------------------------------------

def test_today_moscow_returns_date():
    assert isinstance(today_moscow(), date)
