"""Portfolio / work-sample evidence API.

A 4th intake evidence type, alongside screening, nomination, and passive
signals. Evidence only — never a score, never a decision.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.api import PortfolioRequest, PortfolioResponse
from app.services.portfolio import service as portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("", response_model=PortfolioResponse)
def submit(body: PortfolioRequest, db: Session = Depends(get_db)):
    result = portfolio.submit_portfolio(
        db,
        school_id=body.school_id,
        submitted_by_role=body.submitted_by_role.value,
        title=body.title,
        description=body.description,
        external_reference=body.external_reference,
        learner_id=body.learner_id,
        gender=body.gender,
        cohort_id=body.cohort_id,
    )
    db.commit()
    return PortfolioResponse(
        learner_id=result.learner_id, submission_id=result.submission_id
    )
