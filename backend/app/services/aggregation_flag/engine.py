"""Aggregation & Flag Engine (Section 3.1 / Section 4).

Applies context adjustment, builds the per-domain profile, and applies flag rules.

HARD CONSTRAINTS enforced here:
  * NO composite / average score is ever computed for a decision. Domains stay
    independent and flags fire on the MAXIMUM per-domain deviation and on the
    spread between domains (spike shape) — never on a mean.
  * This engine writes FlagEvent (a flag) and starts the immutable Decision &
    Audit Log trail. It NEVER writes a decision — only PanelReview does.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ContextAdjustment,
    DomainScore,
    FlagEvent,
    Learner,
    ScreeningSession,
)
from app.services.aggregation_flag.context import factor_for_tier
from app.services.decision_audit_log.service import log_event

# --- Flag rules. Each operates on independent domains; none averages. ----------
SPIKE_HIGH_THRESHOLD = 80  # a single adjusted domain at/above this is a spike
WIDE_VARIANCE_THRESHOLD = 40  # max-min spread at/above this = uneven (2e-shaped)


@dataclass
class DomainProfileEntry:
    domain: str
    raw_score: int
    adjustment_factor: float
    adjusted_score: int
    evidence_text: str
    scoring_model_version: str


def _adjusted(raw: int, factor: float) -> int:
    return max(0, min(100, round(raw * factor)))


def build_profile(db: Session, session_id: uuid.UUID) -> list[DomainProfileEntry]:
    """Return the per-domain profile for a session. No composite is produced."""
    session = db.get(ScreeningSession, session_id)
    if session is None:
        return []
    learner = db.get(Learner, session.learner_id)

    scores = list(
        db.scalars(
            select(DomainScore).where(DomainScore.session_id == session_id)
        )
    )

    profile: list[DomainProfileEntry] = []
    for s in scores:
        factor = _factor_for(db, learner, s.domain)
        profile.append(
            DomainProfileEntry(
                domain=s.domain,
                raw_score=s.score,
                adjustment_factor=factor,
                adjusted_score=_adjusted(s.score, factor),
                evidence_text=s.evidence_text,
                scoring_model_version=s.scoring_model_version,
            )
        )
    return profile


def _factor_for(db: Session, learner: Learner | None, domain: str) -> float:
    """Prefer an explicit per-school ContextAdjustment row; fall back to tier."""
    if learner is not None:
        row = db.scalars(
            select(ContextAdjustment)
            .where(ContextAdjustment.school_id == learner.school_id)
            .where(ContextAdjustment.domain == domain)
            .order_by(ContextAdjustment.effective_from.desc())
        ).first()
        if row is not None:
            return row.adjustment_factor
        school = learner.school
        if school is not None:
            return factor_for_tier(school.tier)
    return 1.0


def evaluate_and_flag(db: Session, session_id: uuid.UUID) -> list[FlagEvent]:
    """Apply flag rules to a session's profile and persist any FlagEvents.

    Returns the FlagEvents created. Also opens the audit trail for each flag.
    """
    profile = build_profile(db, session_id)
    if not profile:
        return []

    adjusted = [e.adjusted_score for e in profile]
    peak = max(adjusted)
    spread = max(adjusted) - min(adjusted)
    peak_domain = max(profile, key=lambda e: e.adjusted_score).domain

    created: list[FlagEvent] = []

    if peak >= SPIKE_HIGH_THRESHOLD:
        created.append(
            _fire(
                db,
                session_id,
                rule_id="R1_domain_spike_high",
                description=(
                    f"Spike in '{peak_domain}': adjusted score {peak} >= "
                    f"{SPIKE_HIGH_THRESHOLD}. Flagged on the single-domain maximum, "
                    "not any composite."
                ),
            )
        )

    if spread >= WIDE_VARIANCE_THRESHOLD:
        created.append(
            _fire(
                db,
                session_id,
                rule_id="R2_wide_domain_variance",
                description=(
                    f"Uneven profile: max-min spread {spread} >= "
                    f"{WIDE_VARIANCE_THRESHOLD} across independent domains — the "
                    "spike shape 2e screening looks for."
                ),
            )
        )

    db.flush()
    return created


def _fire(
    db: Session, session_id: uuid.UUID, *, rule_id: str, description: str
) -> FlagEvent:
    flag = FlagEvent(
        session_id=session_id, rule_id=rule_id, rule_description=description
    )
    db.add(flag)
    db.flush()  # get flag.id for the audit trail
    log_event(
        db,
        session_id=session_id,
        flag_event_id=flag.id,
        event_type="flag_fired",
        detail={"rule_id": rule_id, "rule_description": description},
    )
    return flag
