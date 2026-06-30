"""Tests for app.backup.run_backup (Phase 10 B5). Spec: docs/33 §3/§9."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from app.backup import run_backup


def _make_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (x INTEGER)")
    con.execute("INSERT INTO t VALUES (42)")
    con.commit()
    con.close()


def test_run_backup_creates_valid_snapshot(tmp_path):
    src = tmp_path / "crm.db"
    _make_db(src)
    bdir = tmp_path / "backups"
    out = run_backup(str(src), str(bdir), keep=14)
    assert out.exists()
    assert out.suffix == ".db"
    # snapshot is a valid sqlite db with the data (online backup consistency)
    con = sqlite3.connect(str(out))
    rows = con.execute("SELECT x FROM t").fetchall()
    con.close()
    assert rows == [(42,)]


def test_run_backup_rotates_to_keep(tmp_path):
    src = tmp_path / "crm.db"
    _make_db(src)
    bdir = tmp_path / "backups"
    bdir.mkdir()
    # Pre-seed keep+6 snapshots, all OLDER than the real backup will be.
    base = time.time() - 1000.0
    for i in range(20):
        f = bdir / f"crm_seed_{i:02d}.db"   # matches run_backup's glob("crm_*.db")
        f.write_bytes(b"")
        os.utime(f, (base + i, base + i))
    out = run_backup(str(src), str(bdir), keep=14)   # adds 1 current → 21 total
    files = sorted(bdir.glob("*.db"))
    assert len(files) == 14                            # pruned to newest 14
    assert out.exists()                                # the real backup survives


def test_run_backup_preserves_source(tmp_path):
    src = tmp_path / "crm.db"
    _make_db(src)
    run_backup(str(src), str(tmp_path / "b"), keep=14)
    # source still readable and intact
    con = sqlite3.connect(str(src))
    assert con.execute("SELECT x FROM t").fetchall() == [(42,)]
    con.close()
