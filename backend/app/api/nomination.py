"""Nomination Service API (Section 4)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.core.auth import client_ip, rate_limit
from app.core.db import get_db
from app.models import School
from app.schemas.api import NominationRequest, NominationResponse
from app.services.nomination import service as nomination
from app.services.nomination.form import form_definition

router = APIRouter(prefix="/nomination", tags=["nomination"])


@router.get("/form", response_model=list[dict])
def get_form():
    """The structured nomination checklist (incl. 2e amber-flag items)."""
    return form_definition()


@router.get("/schools", response_model=list[dict])
def list_schools(db: Session = Depends(get_db)):
    """Schools available to nominate into (id, name, tier)."""
    return [
        {"id": str(s.id), "name": s.name, "tier": s.tier}
        for s in db.scalars(select(School).order_by(School.name))
    ]


@router.post("", response_model=NominationResponse)
def submit(body: NominationRequest, request: Request, db: Session = Depends(get_db)):
    """Open to parents and teachers without an account (a referral only
    invites a screening; it can never reach a decision), so it is rate-limited
    and size-capped instead."""
    rate_limit(f"nominate:{client_ip(request)}", limit=20, window_s=3600)
    if len(str(body.checklist_responses)) > 4000:
        raise HTTPException(413, "That nomination is too long.")
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
