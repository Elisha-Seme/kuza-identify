"""Portfolio / work-sample evidence service.

A 4th evidence type, added at the project owner's request alongside screening,
nomination, and passive signals. A submission is advisory context for the
panel only — it never advances a learner on its own, and it never creates a
decision (same discipline as CandidateSignal / NominationRecord).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.enums import LearnerSource
from app.models import Learner, PortfolioSubmission


@dataclass
class PortfolioResult:
    learner_id: uuid.UUID
    submission_id: uuid.UUID


def submit_portfolio(
    db: Session,
    *,
    school_id: uuid.UUID,
    submitted_by_role: str,
    title: str,
    description: str,
    external_reference: str | None = None,
    learner_id: uuid.UUID | None = None,
    gender: str | None = None,
    cohort_id: str | None = None,
) -> PortfolioResult:
    if learner_id is None:
        learner = Learner(
            school_id=school_id, cohort_id=cohort_id, gender=gender,
            source=LearnerSource.nomination,
        )
        db.add(learner)
        db.flush()
        learner_id = learner.id

    submission = PortfolioSubmission(
        learner_id=learner_id,
        submitted_by_role=submitted_by_role,
        title=title,
        description=description,
        external_reference=external_reference,
    )
    db.add(submission)
    db.flush()
    return PortfolioResult(learner_id=learner_id, submission_id=submission.id)
