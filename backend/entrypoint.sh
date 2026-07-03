#!/usr/bin/env sh
set -e

# 1. On first boot crm.db does not exist yet, but migrations/env.py runs a
#    pre-migration backup that raises FileNotFoundError on a missing DB.
#    Guarantee a (valid, empty) file first.
python - <<'PY'
from pathlib import Path
import sqlite3
from app.config import settings
p = Path(settings.DB_PATH)
p.parent.mkdir(parents=True, exist_ok=True)
if not p.exists():
    sqlite3.connect(str(p)).close()
    print(f"[entrypoint] created empty DB at {p}", flush=True)
PY

# 2. Apply migrations (env.py auto-backs-up into /data/backups first)
echo "[entrypoint] alembic upgrade head..."
alembic upgrade head

# 3. Seed admin + status dicts (idempotent)
echo "[entrypoint] seed_initial..."
python -c "from app.db import SessionLocal; from app.seed import seed_initial; seed_initial(SessionLocal())"

# 4. Hand off to CMD (uvicorn)
exec "$@"
