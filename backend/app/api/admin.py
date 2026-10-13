"""One-shot bootstrap endpoint for hosted deployments.

Because raw Postgres isn't reachable from the build environment, the schema and
seed are created by the running app itself, once, via this token-guarded route.
It is idempotent: it creates tables if missing, (re)installs the append-only
trigger on decision_audit_log, and seeds demo data only when the DB is empty.

Locally you'd use `alembic upgrade head` + `python -m app.cli.seed` instead; this
route exists so a serverless host with no shell can reach the same state.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.auth import ADMIN, Staff, current_staff, hash_password, require_roles
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine, get_db
from app.core.enums import StaffRole
from app.models import School, StaffUser

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


# create_all() creates missing TABLES but never adds new COLUMNS to tables that
# already exist, so columns added after first deploy are added here, idempotently
# (mirrors migration 0010). Without this, an older hosted DB breaks on insert.
_COLUMN_PATCHES_SQL = """
ALTER TABLE item_responses ADD COLUMN IF NOT EXISTS hints_used INTEGER NOT NULL DEFAULT 0;
ALTER TABLE item_responses ADD COLUMN IF NOT EXISTS skipped BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE screening_sessions ADD COLUMN IF NOT EXISTS pending_hints INTEGER NOT NULL DEFAULT 0;
ALTER TABLE screening_sessions ADD COLUMN IF NOT EXISTS pending_stage INTEGER NOT NULL DEFAULT 0;
ALTER TABLE screening_sessions ADD COLUMN IF NOT EXISTS paused BOOLEAN NOT NULL DEFAULT false;
"""


def _run_init(settings) -> dict:
    # 1. Schema (models are the source of truth; matches the Alembic migrations).
    #    Also creates tables added after the first deploy (e.g. portfolio
    #    submissions, staff users), which is what a "500 on /panel/flagged" on
    #    an older hosted database usually means.
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(_COLUMN_PATCHES_SQL))

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


def _check_token(settings, token: str | None) -> None:
    import hmac

    if not settings.admin_token or not token or not hmac.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=403, detail="bad or missing admin token")


@router.post("/init")
def init_post(x_admin_token: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    _check_token(settings, x_admin_token)
    return _run_init(settings)




_ALL_TABLES = (
    "candidate_signals, consent_records, context_adjustments, decision_audit_log, "
    "domain_scores, flag_events, item_responses, learners, nomination_records, "
    "panel_reviews, portfolio_submissions, school_record_imports, schools, screening_sessions, "
    "channel_bindings"
)


def _run_reset(settings) -> dict:
    if not settings.allow_data_reset:
        raise HTTPException(
            403,
            "Reset is disabled. It truncates every table including the append-only "
            "audit log, so it only runs where ALLOW_DATA_RESET=true (demo hosts).",
        )
    """Wipe all learner data and reload the clean demo profiles. For demo hosts
    that were first seeded before a real key was configured, this removes any
    stale placeholder rows. TRUNCATE is not blocked by the audit-log trigger
    (which guards UPDATE/DELETE only)."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(_TRIGGER_SQL))
        conn.execute(text(f"TRUNCATE TABLE {_ALL_TABLES} RESTART IDENTITY CASCADE"))
    from app.cli.seed import main as seed_main

    seed_main()
    return {"reset": True, "reseeded": True, "llm_scoring": "live" if settings.llm_enabled else "mock"}




@router.post("/reset")
def reset_post(x_admin_token: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    _check_token(settings, x_admin_token)
    return _run_reset(settings)


def _run_demo_screening() -> dict:
    """Create a consented demo learner, run the full 5-item screener with sample
    answers, score each response (real Claude if configured, else the mock), apply
    the flag rules, and return the new session so it appears in the dashboard.

    Token-guarded because each run costs real LLM calls when Claude is live.
    """
    from app.core.enums import Channel, ConsentScope, Language, LearnerSource
    from app.models import ConsentRecord, FlagEvent, Learner, School
    from app.services.screening_gateway import service as gateway

    db = SessionLocal()
    try:
        school = db.scalar(select(School).limit(1))
        if school is None:
            school = School(name="Demo School", tier="low_resource", network="demo")
            db.add(school)
            db.flush()

        learner = Learner(
            school_id=school.id, cohort_id="demo", gender=None,
            source=LearnerSource.active_screening,
        )
        db.add(learner)
        db.flush()
        db.add(ConsentRecord(
            learner_id=learner.id, guardian_identifier="demo-guardian",
            scope=ConsentScope.screening,
        ))
        db.flush()

        session, _ = gateway.start_session(
            db, learner_id=learner.id, channel=Channel.whatsapp, language=Language.en
        )
        # Articulate sample answers to the v2 core items (keyed by domain, so
        # they follow whatever order the engine presents).
        from app.cli.seed import _DEMO_ANSWERS

        while (item := gateway.pending_item(db, session.id)) is not None:
            gateway.submit_response(
                db, session_id=session.id,
                raw_response=_DEMO_ANSWERS.get(item.domain, "I am not sure."),
                response_time_ms=11000,
            )
        db.commit()

        flags = list(db.scalars(select(FlagEvent).where(FlagEvent.session_id == session.id)))
        return {
            "created_session_id": str(session.id),
            "learner_id": str(learner.id),
            "flags": [f.rule_id for f in flags],
            "scored_by": get_settings().scoring_model if get_settings().llm_enabled else "mock",
            "note": "Open the dashboard and Refresh to see this new profile.",
        }
    finally:
        db.close()




@router.post("/demo-screening")
def demo_screening_post(_: Staff = Depends(require_roles(*ADMIN))) -> dict:
    """Programme admins only: each run costs real LLM calls when Claude is live."""
    return _run_demo_screening()


# ---------------------------------------------------------------- staff accounts
class NewStaffUser(BaseModel):
    email: str
    display_name: str
    role: StaffRole
    password: str
    school_id: uuid.UUID | None = None


def _create_user(db: Session, body: NewStaffUser) -> dict:
    if len(body.password) < 10:
        raise HTTPException(422, "Password must be at least 10 characters.")
    if body.role == StaffRole.school_staff and body.school_id is None:
        raise HTTPException(422, "School staff accounts must be linked to a school.")
    email = body.email.strip().lower()
    if db.scalar(select(StaffUser).where(func.lower(StaffUser.email) == email)):
        raise HTTPException(409, "An account with this email already exists.")
    u = StaffUser(
        email=email, display_name=body.display_name.strip(), role=body.role,
        school_id=body.school_id, password_hash=hash_password(body.password),
    )
    db.add(u)
    db.commit()
    return {"id": str(u.id), "email": u.email, "role": u.role.value}


@router.post("/bootstrap-admin")
def bootstrap_admin(body: NewStaffUser, x_admin_token: str | None = Header(default=None),
                    db: Session = Depends(get_db)) -> dict:
    """Create the FIRST programme admin, using the ADMIN_TOKEN header. Refuses
    once any programme admin exists, after that admins create accounts in the
    dashboard (Admin > Staff accounts)."""
    _check_token(get_settings(), x_admin_token)
    if body.role != StaffRole.programme_admin:
        raise HTTPException(422, "Bootstrap only creates a programme_admin.")
    if db.scalar(select(func.count()).select_from(StaffUser).where(StaffUser.role == StaffRole.programme_admin)):
        raise HTTPException(409, "A programme admin already exists; sign in and use Admin > Staff accounts.")
    return _create_user(db, body)


@router.get("/users")
def list_users(_: Staff = Depends(require_roles(*ADMIN)), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": str(u.id), "email": u.email, "display_name": u.display_name, "role": u.role.value,
         "school_id": str(u.school_id) if u.school_id else None, "active": u.active}
        for u in db.scalars(select(StaffUser).order_by(StaffUser.created_at))
    ]


@router.post("/users")
def create_user(body: NewStaffUser, _: Staff = Depends(require_roles(*ADMIN)),
                db: Session = Depends(get_db)) -> dict:
    return _create_user(db, body)


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: uuid.UUID, me: Staff = Depends(require_roles(*ADMIN)),
                    db: Session = Depends(get_db)) -> dict:
    if user_id == me.id:
        raise HTTPException(422, "You cannot deactivate your own account.")
    u = db.get(StaffUser, user_id)
    if u is None:
        raise HTTPException(404, "No such account.")
    u.active = False
    db.commit()
    return {"id": str(u.id), "active": False}
