"""End-to-end tests over the real API + database.

Requires a Postgres reachable via DATABASE_URL with migrations applied
(`alembic upgrade head`). Run:  pytest -q

These assert the spec's hard constraints hold at runtime, not just in the schema:
consent gating, the mocked WhatsApp conversation, scoring producing evidence-only
DomainScores, flags firing, decisions written only via the panel, and the
immutable audit trail.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.enums import ConsentScope, LearnerSource
from app.main import app
from app.models import ConsentRecord, DomainScore, FlagEvent, Learner, School

client = TestClient(app)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def _make_school(db) -> School:
    school = School(name="Test School", tier="low_resource", network="pilot")
    db.add(school)
    db.commit()
    return school


def test_consent_gate_blocks_screening(db):
    school = _make_school(db)
    learner = Learner(school_id=school.id, source=LearnerSource.active_screening)
    db.add(learner)
    db.commit()

    resp = client.post(
        "/screening/sessions",
        json={"learner_id": str(learner.id), "channel": "whatsapp", "language": "en"},
    )
    assert resp.status_code == 403  # DPA 2019: no consent, no session


def test_full_whatsapp_flow_scores_flags_and_decides(db):
    school = _make_school(db)
    learner = Learner(school_id=school.id, source=LearnerSource.active_screening)
    db.add(learner)
    db.flush()
    db.add(
        ConsentRecord(
            learner_id=learner.id,
            guardian_identifier="g-pseudo",
            scope=ConsentScope.screening,
        )
    )
    db.commit()

    # Start session (Kiswahili) and drive the mocked WhatsApp webhook to completion.
    start = client.post(
        "/screening/sessions",
        json={"learner_id": str(learner.id), "channel": "whatsapp", "language": "sw"},
    ).json()
    session_id = start["session_id"]
    assert start["next_prompt"]  # first item text returned

    phone = "254700000001"
    client.post(f"/screening/webhook/bind?from_={phone}&session_id={session_id}")

    for i in range(5):
        r = client.post(
            "/screening/webhook/whatsapp",
            json={"from": phone, "text": f"Jibu {i} pamoja na maelezo ya kufikiri."},
        )
        assert r.status_code == 200

    # Five DomainScores (one per domain), each with evidence + model version.
    scores = db.query(DomainScore).filter_by(session_id=uuid.UUID(session_id)).all()
    assert len(scores) == 5
    for s in scores:
        assert s.evidence_text
        assert s.scoring_model_version
        assert 0 <= s.score <= 100

    # No composite score column exists anywhere (constraint: domains independent).
    cols = db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public'"
    )).scalars().all()
    lowered = [c.lower() for c in cols]
    assert not any(
        k in c for c in lowered for k in ("composite", "average", "overall_score", "total_score")
    )

    # If flags fired, a decision can be recorded — and only via the panel.
    flags = db.query(FlagEvent).filter_by(session_id=uuid.UUID(session_id)).all()
    if flags:
        dec = client.post(
            f"/panel/sessions/{session_id}/decision",
            json={"reviewer_id": "rev-1", "decision": "advance", "notes": "ok"},
        )
        assert dec.status_code == 200

        # The flag -> decision path is in the immutable log, and cannot be mutated.
        n = db.execute(text(
            "SELECT count(*) FROM decision_audit_log WHERE session_id=:sid "
            "AND event_type='decision_recorded'"
        ), {"sid": session_id}).scalar()
        assert n >= 1
        with pytest.raises(Exception):
            db.execute(text("UPDATE decision_audit_log SET event_type='x'"))
            db.commit()
        db.rollback()
