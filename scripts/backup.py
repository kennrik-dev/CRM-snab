"""CLI: daily SQLite backup of crm.db (Phase 10 B5). Run via cron/Task Scheduler.

Usage: python scripts/backup.py [--db crm.db] [--backup-dir backups] [--keep 14]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.backup import run_backup  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Backup CRM SQLite DB.")
    ap.add_argument("--db", default=settings.DB_PATH)
    default_dir = str(Path(settings.DB_PATH).resolve().parent / "backups")
    ap.add_argument("--backup-dir", default=default_dir)
    ap.add_argument("--keep", type=int, default=14)
    args = ap.parse_args()
    out = run_backup(args.db, args.backup_dir, keep=args.keep)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
