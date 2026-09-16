"""One-shot bootstrap endpoint for hosted deployments.

Because raw Postgres isn't reachable from the build environment, the schema and
seed are created by the running app itself, once, via this token-guarded route.
It is idempotent: it creates tables if missing, (re)installs the append-only
trigger on decision_audit_log, and seeds demo data only when the DB is empty.

Locally you'd use `alembic upgrade head` + `python -m app.cli.seed` instead; this
route exists so a serverless host with no shell can reach the same state.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
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


def _run_init(settings) -> dict:
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


def _check_token(settings, token: str | None) -> None:
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(status_code=403, detail="bad or missing admin token")


@router.post("/init")
def init_post(x_admin_token: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    _check_token(settings, x_admin_token)
    return _run_init(settings)


@router.get("/init")
def init_get(token: str = Query(...)) -> dict:
    """Browser-clickable one-shot bootstrap. Same as POST /admin/init but the
    token is passed as ?token= so it can be triggered from a URL bar once."""
    settings = get_settings()
    _check_token(settings, token)
    return _run_init(settings)


_ALL_TABLES = (
    "candidate_signals, consent_records, context_adjustments, decision_audit_log, "
    "domain_scores, flag_events, item_responses, learners, nomination_records, "
    "panel_reviews, school_record_imports, schools, screening_sessions"
)


def _run_reset(settings) -> dict:
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


@router.get("/reset")
def reset_get(token: str = Query(...)) -> dict:
    settings = get_settings()
    _check_token(settings, token)
    return _run_reset(settings)


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
        # Deliberately uneven, articulate answers so the 2e spike pattern shows.
        answers = [
            "Cost is 60 and she sells for 96 so profit is 36. I did 12 times 8 first, then subtracted 60.",
            "Net, because a net is what a fisherman depends on just like a farmer depends on rain.",
            "42. The gaps are 4, 6, 8, 10, so the next gap is 12 and 30+12=42.",
            "Yes, because the rule says everyone who passed had studied, so not studying means not passing.",
            "blue, seven, river, chair, mango. I made a short story linking each word to remember the order.",
        ]
        for a in answers:
            gateway.submit_response(
                db, session_id=session.id, raw_response=a, response_time_ms=11000
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


@router.get("/demo-screening")
def demo_screening_get(token: str = Query(...)) -> dict:
    settings = get_settings()
    _check_token(settings, token)
    return _run_demo_screening()


@router.post("/demo-screening")
def demo_screening_post(x_admin_token: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    _check_token(settings, x_admin_token)
    return _run_demo_screening()
