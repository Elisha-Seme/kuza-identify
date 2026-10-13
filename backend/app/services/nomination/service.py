"""Nomination Service (Section 4).

A teacher or parent submits the structured checklist (form.py). This produces a
Learner (source=nomination) if one doesn't already exist and a NominationRecord.

Nomination is a MEDIUM-confidence review signal (Section 2). Its 2e amber-flag
count is surfaced to the panel as evidence on the learner's profile — it is NOT a
score and NOT a decision. A nominated learner is expected to complete the same
active screener before the panel records a decision (decisions attach to
ScreeningSessions per Section 5).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.enums import ConsentScope, LearnerSource, NominatorRole
from app.models import ConsentRecord, Learner, NominationRecord
from app.services.nomination.form import count_amber_flags


@dataclass
class NominationResult:
    learner_id: uuid.UUID
    nomination_id: uuid.UUID
    amber_flag_count: int


def submit_nomination(
    db: Session,
    *,
    school_id: uuid.UUID,
    nominator_role: NominatorRole,
    checklist_responses: dict,
    learner_id: uuid.UUID | None = None,
    gender: str | None = None,
    cohort_id: str | None = None,
    guardian_identifier: str | None = None,
) -> NominationResult:
    if learner_id is None:
        learner = Learner(
            school_id=school_id,
            cohort_id=cohort_id,
            gender=gender,
            source=LearnerSource.nomination,
        )
        db.add(learner)
        db.flush()
        learner_id = learner.id

    record = NominationRecord(
        learner_id=learner_id,
        nominator_role=nominator_role,
        checklist_responses=checklist_responses,
    )
    db.add(record)

    # Only a PARENT/guardian nomination is an expression of guardian consent
    # (Section 7). A teacher or peer ticking a box is not the guardian's
    # consent, so no ConsentRecord is written for them; consent is collected
    # from the guardian before screening, as the consent gate requires.
    if guardian_identifier and nominator_role == NominatorRole.parent:
        db.add(
            ConsentRecord(
                learner_id=learner_id,
                guardian_identifier=guardian_identifier,
                scope=ConsentScope.nomination,
            )
        )

    db.flush()
    return NominationResult(
        learner_id=learner_id,
        nomination_id=record.id,
        amber_flag_count=count_amber_flags(checklist_responses),
    )
