"""Panel Review Dashboard API (Section 4).

Serves the flagged-profile list, a per-session profile with evidence, and the
decision-recording endpoint. Decisions are written here (via the service) and
nowhere else.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AUDIT_READ, INSIGHTS_READ, PANEL_DECIDE, PANEL_READ, Staff, require_roles
from app.core.db import get_db
from app.models import DecisionAuditLog, StaffUser
from app.schemas.api import DecisionRequest
from app.services.panel_review import service as panel

router = APIRouter(prefix="/panel", tags=["panel"])


def _names(db: Session) -> dict[str, str]:
    return {f"staff:{u.id}": u.display_name for u in db.scalars(select(StaffUser))}


def _profile_to_dict(p, names: dict[str, str] | None = None) -> dict:
    d = asdict(p)
    for r in d.get("review_history", []):
        r["reviewer_name"] = (names or {}).get(r.get("reviewer_id"), r.get("reviewer_id"))
    d["session_id"] = str(p.session_id)
    d["learner_id"] = str(p.learner_id)
    d["school_id"] = str(p.school_id)
    d["profile"] = [asdict(e) for e in p.profile]
    return d


@router.get("/flagged", response_model=list[dict])
def list_flagged(db: Session = Depends(get_db), _: Staff = Depends(require_roles(*PANEL_READ))):
    names = _names(db)
    return [_profile_to_dict(p, names) for p in panel.list_flagged_sessions(db)]


@router.get("/metrics", response_model=dict)
def metrics(db: Session = Depends(get_db), _: Staff = Depends(require_roles(*INSIGHTS_READ))):
    """Read-only pilot funnel + fairness slices. Counts below 5 are shown as
    "<5" so a small slice (e.g. one school, one gender) can't single a child out."""
    return _suppress_small(panel.metrics(db))


def _suppress_small(m: dict, k: int = 5) -> dict:
    def fix(v):
        if isinstance(v, dict):
            return {kk: fix(vv) for kk, vv in v.items()}
        if isinstance(v, int) and 0 < v < k:
            return f"<{k}"
        return v

    return {"funnel": m.get("funnel", {}), "slices": fix(m.get("slices", {})), "small_cell_threshold": k}


@router.get("/audit-log", response_model=list[dict])
def audit_log(limit: int = 200, db: Session = Depends(get_db), _: Staff = Depends(require_roles(*AUDIT_READ))):
    """Read-only view of the append-only flag -> decision log (auditors, leads)."""
    rows = db.scalars(select(DecisionAuditLog).order_by(DecisionAuditLog.logged_at.desc()).limit(min(limit, 1000)))
    return [
        {"id": str(r.id), "session_id": str(r.session_id), "event_type": r.event_type,
         "detail": r.detail, "logged_at": r.logged_at.isoformat()}
        for r in rows
    ]


@router.get("/sessions/{session_id}", response_model=dict)
def get_profile(session_id: uuid.UUID, db: Session = Depends(get_db), _: Staff = Depends(require_roles(*PANEL_READ))):
    return _profile_to_dict(panel.get_flagged_profile(db, session_id), _names(db))


@router.post("/sessions/{session_id}/decision", response_model=dict)
def record_decision(
    session_id: uuid.UUID, body: DecisionRequest, db: Session = Depends(get_db),
    staff: Staff = Depends(require_roles(*PANEL_DECIDE)),
):
    # The reviewer is whoever is signed in. Any reviewer_id in the body is
    # ignored, so a decision can't be recorded under someone else's name.
    review = panel.record_decision(
        db,
        session_id=session_id,
        reviewer_id=staff.reviewer_id,
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
