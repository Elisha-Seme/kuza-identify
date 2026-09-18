"""Screening Gateway (Section 4).

Owns screening session state and interruption/resume (Section 3.4). Session
progress is derived from persisted ItemResponses, so a dropped WhatsApp/USSD
session resumes exactly where it left off after any restart — nothing lives only
in memory here.

Consent is enforced before a session can start (Section 7 / DPA 2019).

On completion the gateway runs the LLM Scoring Service over each response to
produce DomainScores, then hands off to the Aggregation & Flag Engine. It never
writes a decision.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Channel, ConsentScope, Language, SessionStatus
from app.models import (
    ConsentRecord,
    DomainScore,
    ItemResponse,
    Learner,
    ScreeningSession,
)
from app.services.adaptive_item_engine import engine as items
from app.services.aggregation_flag.engine import evaluate_and_flag
from app.services.llm_scoring.service import score_response


class ConsentMissingError(Exception):
    """Raised when a screening session is started without recorded consent."""


def _seen_item_ids(db: Session, session_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(ItemResponse.item_id)
            .where(ItemResponse.session_id == session_id)
            .order_by(ItemResponse.created_at)
        )
    )


def _has_screening_consent(db: Session, learner_id: uuid.UUID) -> bool:
    return (
        db.scalars(
            select(ConsentRecord.id)
            .where(ConsentRecord.learner_id == learner_id)
            .where(ConsentRecord.scope == ConsentScope.screening)
        ).first()
        is not None
    )


def start_session(
    db: Session,
    *,
    learner_id: uuid.UUID,
    channel: Channel,
    language: Language,
) -> tuple[ScreeningSession, str | None]:
    """Create a session and return it plus the first item prompt text."""
    if not _has_screening_consent(db, learner_id):
        raise ConsentMissingError(
            "No screening-scope ConsentRecord for this learner (DPA 2019)."
        )
    session = ScreeningSession(
        learner_id=learner_id, channel=channel, language=language,
        status=SessionStatus.in_progress,
    )
    db.add(session)
    db.flush()
    first = items.select_next([])
    if first is None:
        return session, None
    # State the untimed / no-penalty accommodation explicitly, once, before the
    # first item (UDL practice) rather than leaving it unenforced-but-unstated.
    intro = items.session_intro(language)
    prompt = f"{intro}\n\n{first.text(language)}" if intro else first.text(language)
    return session, prompt


def next_prompt(db: Session, session_id: uuid.UUID) -> str | None:
    """The prompt text for the item the learner should answer next (resume-safe)."""
    session = db.get(ScreeningSession, session_id)
    if session is None or session.status != SessionStatus.in_progress:
        return None
    item = items.select_next(_seen_item_ids(db, session_id))
    return item.text(session.language) if item else None


def submit_response(
    db: Session,
    *,
    session_id: uuid.UUID,
    raw_response: str,
    response_time_ms: int | None = None,
) -> str | None:
    """Record a response to the currently-pending item and return the next prompt,
    or None when the session is complete (which triggers scoring + flagging)."""
    session = db.get(ScreeningSession, session_id)
    if session is None or session.status != SessionStatus.in_progress:
        return None

    pending = items.select_next(_seen_item_ids(db, session_id))
    if pending is None:
        _complete(db, session)
        return None

    db.add(
        ItemResponse(
            session_id=session_id,
            item_id=pending.id,
            raw_response=raw_response,
            response_time_ms=response_time_ms,
        )
    )
    session.current_item_index = session.current_item_index + 1
    db.flush()

    nxt = items.select_next(_seen_item_ids(db, session_id))
    if nxt is None:
        _complete(db, session)
        return None
    return nxt.text(session.language)


def _complete(db: Session, session: ScreeningSession) -> None:
    """Score every response into a DomainScore, then run the flag engine."""
    from datetime import datetime, timezone

    responses = list(
        db.scalars(
            select(ItemResponse).where(ItemResponse.session_id == session.id)
        )
    )
    for r in responses:
        item = items.get_item(r.item_id)
        if item is None:
            continue
        result = score_response(
            domain=item.domain,
            item_prompt=item.text(session.language),
            expected_reasoning=item.expected_reasoning,
            raw_response=r.raw_response,
            language=session.language,
        )
        db.add(
            DomainScore(
                session_id=session.id,
                domain=item.domain,
                score=result.score,
                evidence_text=result.evidence_text,
                scoring_model_version=result.scoring_model_version,
            )
        )
    db.flush()

    # Aggregation & Flag Engine: writes flags + evidence only, never a decision.
    evaluate_and_flag(db, session.id)

    session.status = SessionStatus.completed
    session.completed_at = datetime.now(timezone.utc)
    db.flush()
