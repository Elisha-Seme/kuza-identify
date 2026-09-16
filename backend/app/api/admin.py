"""One-shot bootstrap endpoint for hosted deployments.

Because raw Postgres isn't reachable from the build environment, the schema and
seed are created by the running app itself, once, via this token-guarded route.
It is idempotent: it creates tables if missing, (re)installs the append-only
trigger on decision_audit_log, and seeds demo data only when the DB is empty.

Locally you'd use `alembic upgrade head` + `python -m app.cli.seed` instead; this
route exists so a serverless host with no shell can reach the same state.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine
from app.models import School

router = APIRouter(prefix="/admin", tags=["admin"])

# Mirrors migration 0008 — enforces the immutable Decision & Audit Log at the DB.
_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION kuza_reject_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'decision_audit_log is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_decision_audit_log_immutable ON decision_audit_log;
CREATE TRIGGER trg_decision_audit_log_immutable
BEFORE UPDATE OR DELETE ON decision_audit_log
FOR EACH ROW EXECUTE FUNCTION kuza_reject_mutation();
"""


@router.post("/init")
def init(x_admin_token: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="bad or missing X-Admin-Token")

    # 1. Schema (models are the source of truth; matches the Alembic migrations).
    Base.metadata.create_all(engine)

    # 2. Immutability trigger.
    with engine.begin() as conn:
        conn.execute(text(_TRIGGER_SQL))

    # 3. Seed only if empty.
    seeded = False
    db = SessionLocal()
    try:
        existing = db.scalar(select(func.count()).select_from(School))
        if not existing:
            from app.cli.seed import main as seed_main

            seed_main()
            seeded = True
    finally:
        db.close()

    return {
        "schema": "ready",
        "trigger": "installed",
        "seeded": seeded,
        "llm_scoring": "live" if settings.llm_enabled else "mock",
    }
