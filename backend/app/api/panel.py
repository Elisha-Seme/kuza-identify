"""Panel Review Dashboard API (Section 4).

Serves the flagged-profile list, a per-session profile with evidence, and the
decision-recording endpoint. Decisions are written here (via the service) and
nowhere else.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.api import DecisionRequest
from app.services.panel_review import service as panel

router = APIRouter(prefix="/panel", tags=["panel"])


def _profile_to_dict(p) -> dict:
    d = asdict(p)
    d["session_id"] = str(p.session_id)
    d["learner_id"] = str(p.learner_id)
    d["school_id"] = str(p.school_id)
    d["profile"] = [asdict(e) for e in p.profile]
    return d


@router.get("/flagged", response_model=list[dict])
def list_flagged(db: Session = Depends(get_db)):
    return [_profile_to_dict(p) for p in panel.list_flagged_sessions(db)]


@router.get("/metrics", response_model=dict)
def metrics(db: Session = Depends(get_db)):
    """Read-only pilot funnel + fairness slices (no schema change, honest counts)."""
    return panel.metrics(db)


@router.get("/sessions/{session_id}", response_model=dict)
def get_profile(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return _profile_to_dict(panel.get_flagged_profile(db, session_id))


@router.post("/sessions/{session_id}/decision", response_model=dict)
def record_decision(
    session_id: uuid.UUID, body: DecisionRequest, db: Session = Depends(get_db)
):
    review = panel.record_decision(
        db,
        session_id=session_id,
        reviewer_id=body.reviewer_id,
        decision=body.decision,
        notes=body.notes,
    )
    db.commit()
    return {
        "review_id": str(review.id),
        "session_id": str(session_id),
        "decision": review.decision.value,
        "decided_at": review.decided_at.isoformat(),
    }
