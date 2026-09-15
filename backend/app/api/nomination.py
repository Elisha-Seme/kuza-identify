"""Nomination Service API (Section 4)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.api import NominationRequest, NominationResponse
from app.services.nomination import service as nomination
from app.services.nomination.form import form_definition

router = APIRouter(prefix="/nomination", tags=["nomination"])


@router.get("/form", response_model=list[dict])
def get_form():
    """The structured nomination checklist (incl. 2e amber-flag items)."""
    return form_definition()


@router.post("", response_model=NominationResponse)
def submit(body: NominationRequest, db: Session = Depends(get_db)):
    result = nomination.submit_nomination(
        db,
        school_id=body.school_id,
        nominator_role=body.nominator_role,
        checklist_responses=body.checklist_responses,
        learner_id=body.learner_id,
        gender=body.gender,
        cohort_id=body.cohort_id,
        guardian_identifier=body.guardian_identifier,
    )
    db.commit()
    return NominationResponse(
        learner_id=result.learner_id,
        nomination_id=result.nomination_id,
        amber_flag_count=result.amber_flag_count,
    )
