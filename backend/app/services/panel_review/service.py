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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import PanelDecision
from app.models import (
    CandidateSignal,
    FlagEvent,
    ItemResponse,
    Learner,
    NominationRecord,
    PanelReview,
    School,
    ScreeningSession,
)
from app.services.aggregation_flag.engine import DomainProfileEntry, build_profile
from app.services.decision_audit_log.service import log_event
from app.services.nomination.form import count_amber_flags

# Items in the current screener — used only to express completeness (answers/total).
_EXPECTED_ITEMS = 5


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
    # --- read-only workflow/quality fields (no schema change) ----------------
    language: str = "en"
    channel: str = "whatsapp"
    responses_count: int = 0
    expected_items: int = _EXPECTED_ITEMS
    scored_live: bool = False
    received_at: str | None = None
    review_history: list[dict] = field(default_factory=list)


def _clean(text: str | None) -> str:
    """Sanitise text on read so the UI never shows legacy placeholder wording or
    em dashes, even for rows written by an earlier build. Belt-and-braces with the
    seed rewrite: guarantees a clean display without needing a database reset."""
    if not text:
        return text or ""
    if (
        "MOCK SCORER" in text
        or "Deterministic placeholder" in text
        or "seed fixture" in text.lower()
    ):
        return "Automated demo estimate. Connect a scoring model for a real assessment."
    # Normalise em/en dashes to commas for legacy rows (avoid a space before the comma).
    return (
        text.replace(" — ", ", ").replace(" – ", ", ")
        .replace("—", ",").replace("–", ",")
    )


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
            "rule_description": _clean(f.rule_description),
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
            "evidence_text": _clean(s.evidence_text),
            "confidence": s.confidence,
        }
        for s in db.scalars(
            select(CandidateSignal).where(CandidateSignal.learner_id == learner.id)
        )
    ]

    reviews = list(
        db.scalars(
            select(PanelReview)
            .where(PanelReview.session_id == session_id)
            .order_by(PanelReview.decided_at.desc())
        )
    )
    review_history = [
        {
            "decision": r.decision.value,
            "reviewer_id": r.reviewer_id,
            "notes": r.notes,
            "decided_at": r.decided_at.isoformat(),
        }
        for r in reviews
    ]

    prof = build_profile(db, session_id)
    for e in prof:  # sanitise legacy evidence text on read
        e.evidence_text = _clean(e.evidence_text)
    responses_count = db.scalar(
        select(func.count())
        .select_from(ItemResponse)
        .where(ItemResponse.session_id == session_id)
    ) or 0
    # "Live" only if a real Claude model produced the score (ids start with
    # "claude-"); demo/seed versions read as demo data.
    scored_live = any(e.scoring_model_version.startswith("claude") for e in prof)

    return FlaggedProfile(
        session_id=session_id,
        learner_id=learner.id,
        learner_source=learner.source.value,
        school_id=learner.school_id,
        profile=prof,
        flags=flags,
        nomination_amber_flags=amber,
        candidate_signals=signals,
        existing_decision=reviews[0].decision.value if reviews else None,
        language=session.language.value,
        channel=session.channel.value,
        responses_count=responses_count,
        scored_live=scored_live,
        received_at=session.started_at.isoformat() if session.started_at else None,
        review_history=review_history,
    )


def metrics(db: Session) -> dict:
    """Read-only pilot funnel + fairness slices, derived from existing data.

    Honest by construction: only counts things the system actually records. Deeper
    fairness measures (reviewer agreement, false pos/neg) need labelled ground
    truth and are intentionally NOT invented here.
    """
    total_sessions = db.scalar(select(func.count()).select_from(ScreeningSession)) or 0
    flagged_ids = set(db.scalars(select(FlagEvent.session_id).distinct()))
    reviewed_ids = set(db.scalars(select(PanelReview.session_id).distinct()))

    def _decided(kind: PanelDecision) -> int:
        return len(set(db.scalars(
            select(PanelReview.session_id).where(PanelReview.decision == kind)
        )))

    funnel = {
        "screened": total_sessions,
        "flagged": len(flagged_ids),
        "reviewed": len(reviewed_ids),
        "advanced": _decided(PanelDecision.advance),
        "held": _decided(PanelDecision.hold),
        "declined": _decided(PanelDecision.decline),
        "awaiting_review": len(flagged_ids - reviewed_ids),
    }

    advanced_ids = set(db.scalars(
        select(PanelReview.session_id).where(PanelReview.decision == PanelDecision.advance)
    ))

    # Fairness slices: flag rate by pathway / school tier / language / gender.
    slices: dict[str, dict] = {"pathway": {}, "school_tier": {}, "language": {}, "gender": {}}
    for session in db.scalars(select(ScreeningSession)):
        learner = db.get(Learner, session.learner_id)
        school = db.get(School, learner.school_id) if learner else None
        buckets = {
            "pathway": learner.source.value if learner else "unknown",
            "school_tier": school.tier if school else "unknown",
            "language": session.language.value,
            "gender": (learner.gender if learner and learner.gender else "unreported"),
        }
        for dim, key in buckets.items():
            b = slices[dim].setdefault(key, {"sessions": 0, "flagged": 0, "advanced": 0})
            b["sessions"] += 1
            if session.id in flagged_ids:
                b["flagged"] += 1
            if session.id in advanced_ids:
                b["advanced"] += 1
    return {"funnel": funnel, "slices": slices}


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
