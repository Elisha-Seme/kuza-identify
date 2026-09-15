"""Bias Audit Service (Section 4 / Section 7) — SKELETON.

Scheduled job comparing flag/advance rates across demographic, school-tier, AND
pathway (active / nomination / passive) slices. Section 7 makes this a stated
equity claim, not optional tooling, and Section 3.7 requires the passive-mining
pathway to be its own named slice — so pathway is a first-class dimension here.

Phase 0 scope: this computes the slice rates from what's in the DB so the metric
actually runs. It intentionally does not yet include significance testing or an
alerting threshold — that is follow-on work once pilot volumes exist (Section 9).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import PanelDecision
from app.models import FlagEvent, Learner, PanelReview, School, ScreeningSession


@dataclass
class SliceStat:
    slice_key: str
    sessions: int = 0
    flagged: int = 0
    advanced: int = 0

    @property
    def flag_rate(self) -> float:
        return round(self.flagged / self.sessions, 3) if self.sessions else 0.0

    @property
    def advance_rate(self) -> float:
        return round(self.advanced / self.sessions, 3) if self.sessions else 0.0


@dataclass
class BiasAuditReport:
    by_pathway: dict[str, SliceStat] = field(default_factory=dict)
    by_school_tier: dict[str, SliceStat] = field(default_factory=dict)
    by_gender: dict[str, SliceStat] = field(default_factory=dict)


def run_bias_audit(db: Session) -> BiasAuditReport:
    report = BiasAuditReport()

    flagged_session_ids = set(db.scalars(select(FlagEvent.session_id).distinct()))
    advanced_session_ids = set(
        db.scalars(
            select(PanelReview.session_id).where(
                PanelReview.decision == PanelDecision.advance
            )
        )
    )

    for session in db.scalars(select(ScreeningSession)):
        learner = db.get(Learner, session.learner_id)
        school = db.get(School, learner.school_id) if learner else None

        keys = {
            "pathway": (report.by_pathway, learner.source.value if learner else "unknown"),
            "tier": (report.by_school_tier, school.tier if school else "unknown"),
            "gender": (report.by_gender, learner.gender if learner and learner.gender else "unreported"),
        }
        for _, (bucket, key) in keys.items():
            stat = bucket.setdefault(key, SliceStat(slice_key=key))
            stat.sessions += 1
            if session.id in flagged_session_ids:
                stat.flagged += 1
            if session.id in advanced_session_ids:
                stat.advanced += 1

    return report
