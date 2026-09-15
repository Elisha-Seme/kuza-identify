#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres, apply migrations, then start the API.
echo "Waiting for database…"
python - <<'PY'
import os, time
import sqlalchemy as sa
url = os.environ["DATABASE_URL"]
for attempt in range(30):
    try:
        sa.create_engine(url).connect().close()
        print("Database is up.")
        break
    except Exception as e:
        print(f"  db not ready ({attempt+1}/30): {e.__class__.__name__}")
        time.sleep(2)
else:
    raise SystemExit("Database never became available")
PY

echo "Running migrations…"
alembic upgrade head

echo "Starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
