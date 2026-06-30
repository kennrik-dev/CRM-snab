"""SQLite backup helper (Phase 10 B5). Spec: docs/33 §3/§9.

daily file backup of crm.db, retain last N (14). Uses sqlite3 online-backup
(conn.backup) for a consistent snapshot under concurrent writers — NOT a raw
file copy. Importable from migrations/env.py and scripts/backup.py.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def run_backup(db_path: str, backup_dir: str, keep: int = 14) -> Path:
    """Copy `db_path` to `backup_dir/crm_YYYYMMDD_HHMMSS.db` via online backup,
    then prune the directory to the newest `keep` files. Returns the new path.
    Raises on failure (§3: backup before migration is mandatory)."""
    src_path = Path(db_path)
    if not src_path.exists():
        raise FileNotFoundError(f"DB not found: {src_path}")

    bdir = Path(backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = bdir / f"crm_{stamp}.db"

    src = sqlite3.connect(str(src_path))
    dest = sqlite3.connect(str(dest_path))
    try:
        src.backup(dest)  # online, consistent snapshot
    finally:
        dest.close()
        src.close()

    # prune: keep newest `keep` by modification time
    files = sorted(bdir.glob("crm_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in files[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass

    return dest_path


__all__ = ["run_backup"]
