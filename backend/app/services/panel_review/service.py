"""Panel Review Service (Section 4).

Builds the reviewer's view of a flagged screening session (per-domain evidence,
flags, and any nomination / candidate-signal context) and records the reviewer's
decision.

This is the ONLY place a decision is written (Section 3.6). Recording a decision
also appends to the immutable Decision & Audit Log, completing the flag ->
decision path for every flag on the session.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import PanelDecision
from app.models import (
    CandidateSignal,
    FlagEvent,
    Learner,
    NominationRecord,
    PanelReview,
    ScreeningSession,
)
from app.services.aggregation_flag.engine import DomainProfileEntry, build_profile
from app.services.decision_audit_log.service import log_event
from app.services.nomination.form import count_amber_flags


@dataclass
class FlaggedProfile:
    session_id: uuid.UUID
    learner_id: uuid.UUID
    learner_source: str
    school_id: uuid.UUID
    profile: list[DomainProfileEntry]
    flags: list[dict]
    nomination_amber_flags: int
    candidate_signals: list[dict]
    existing_decision: str | None = field(default=None)


def list_flagged_sessions(db: Session) -> list[FlaggedProfile]:
    """Every screening session that has at least one FlagEvent."""
    session_ids = list(
        db.scalars(select(FlagEvent.session_id).distinct())
    )
    return [get_flagged_profile(db, sid) for sid in session_ids]


def get_flagged_profile(db: Session, session_id: uuid.UUID) -> FlaggedProfile:
    session = db.get(ScreeningSession, session_id)
    learner = db.get(Learner, session.learner_id)

    flags = [
        {
            "id": str(f.id),
            "rule_id": f.rule_id,
            "rule_description": f.rule_description,
            "fired_at": f.fired_at.isoformat(),
        }
        for f in db.scalars(
            select(FlagEvent).where(FlagEvent.session_id == session_id)
        )
    ]

    # Nomination context for this learner (evidence, never a score).
    amber = 0
    for nom in db.scalars(
        select(NominationRecord).where(NominationRecord.learner_id == learner.id)
    ):
        amber += count_amber_flags(nom.checklist_responses)

    # Passive candidate signals for this learner (advisory only, fixed-low).
    signals = [
        {
            "id": str(s.id),
            "signal_type": s.signal_type.value,
            "evidence_text": s.evidence_text,
            "confidence": s.confidence,
        }
        for s in db.scalars(
            select(CandidateSignal).where(CandidateSignal.learner_id == learner.id)
        )
    ]

    existing = db.scalars(
        select(PanelReview)
        .where(PanelReview.session_id == session_id)
        .order_by(PanelReview.decided_at.desc())
    ).first()

    return FlaggedProfile(
        session_id=session_id,
        learner_id=learner.id,
        learner_source=learner.source.value,
        school_id=learner.school_id,
        profile=build_profile(db, session_id),
        flags=flags,
        nomination_amber_flags=amber,
        candidate_signals=signals,
        existing_decision=existing.decision.value if existing else None,
    )


def record_decision(
    db: Session,
    *,
    session_id: uuid.UUID,
    reviewer_id: str,
    decision: PanelDecision,
    notes: str | None = None,
) -> PanelReview:
    """Write the panel's decision and close the audit trail for this session."""
    review = PanelReview(
        session_id=session_id,
        reviewer_id=reviewer_id,
        decision=decision,
        notes=notes,
    )
    db.add(review)
    db.flush()

    # Log the flag -> decision path immutably: one entry per flag on the session.
    flags = list(
        db.scalars(select(FlagEvent).where(FlagEvent.session_id == session_id))
    )
    if flags:
        for f in flags:
            log_event(
                db,
                session_id=session_id,
                flag_event_id=f.id,
                panel_review_id=review.id,
                event_type="decision_recorded",
                detail={
                    "decision": decision.value,
                    "reviewer_id": reviewer_id,
                    "rule_id": f.rule_id,
                },
            )
    else:
        log_event(
            db,
            session_id=session_id,
            panel_review_id=review.id,
            event_type="decision_recorded",
            detail={"decision": decision.value, "reviewer_id": reviewer_id},
        )
    return review
