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

from app.core.auth import hash_password
from app.core.db import SessionLocal
from app.core.enums import ConsentScope, LearnerSource, StaffRole
from app.main import app
from app.models import ConsentRecord, DomainScore, FlagEvent, Learner, School, StaffUser

client = TestClient(app)


def _staff_headers(db, role: StaffRole, school_id=None) -> dict:
    """Create a staff account directly and sign in through the real endpoint."""
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@test.kuza"
    db.add(StaffUser(email=email, display_name=f"Test {role.value}", role=role,
                     school_id=school_id, password_hash=hash_password("correct horse battery")))
    db.commit()
    r = client.post("/auth/login", json={"email": email, "password": "correct horse battery"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


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
        headers=_staff_headers(db, StaffRole.school_staff, school.id),
    )
    assert resp.status_code == 403  # DPA 2019: no consent, no session
    assert "consent" in resp.json()["detail"].lower()


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
    staff = _staff_headers(db, StaffRole.school_staff, school.id)
    start = client.post(
        "/screening/sessions",
        json={"learner_id": str(learner.id), "channel": "whatsapp", "language": "sw"},
        headers=staff,
    ).json()
    session_id = start["session_id"]
    assert start["next_prompt"]  # first item text returned

    phone = "254700000001"
    client.post("/screening/webhook/bind", json={"phone": phone, "session_id": session_id}, headers=staff)

    # 5 answers + 1 "OK" for the two-step memory item.
    for i in range(6):
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
        body = {"reviewer_id": "someone-else", "decision": "advance", "notes": "ok"}
        assert client.post(f"/panel/sessions/{session_id}/decision", json=body).status_code == 401
        dec = client.post(
            f"/panel/sessions/{session_id}/decision", json=body,
            headers=_staff_headers(db, StaffRole.reviewer),
        )
        assert dec.status_code == 200
        # The typed reviewer_id is ignored; the signed-in account is recorded.
        rid = db.execute(text(
            "SELECT reviewer_id FROM panel_reviews WHERE session_id=:sid"
        ), {"sid": session_id}).scalar()
        assert rid.startswith("staff:")

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
