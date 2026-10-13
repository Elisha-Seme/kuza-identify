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
    body = first.text_for(channel, language)
    prompt = f"{intro}\n\n{body}" if intro else body
    return session, prompt


def pending_stage(db: Session, session_id: uuid.UUID) -> int:
    session = db.get(ScreeningSession, session_id)
    return session.pending_stage if session else 0


def pending_item(db: Session, session_id: uuid.UUID) -> items.Item | None:
    """The item currently waiting for an answer (used to attach its picture)."""
    session = db.get(ScreeningSession, session_id)
    if session is None or session.status != SessionStatus.in_progress:
        return None
    return items.select_next(_seen_item_ids(db, session_id))


def next_prompt(db: Session, session_id: uuid.UUID) -> str | None:
    """The prompt text for the item the learner should answer next (resume-safe)."""
    session = db.get(ScreeningSession, session_id)
    if session is None or session.status != SessionStatus.in_progress:
        return None
    item = items.select_next(_seen_item_ids(db, session_id))
    return item.text_for(session.channel, session.language, session.pending_stage) if item else None


_CONTROL_REPLIES = {
    "pause": {
        "en": "No problem, your answers are saved. Send any message when you want to carry on.",
        "sw": "Sawa, majibu yako yamehifadhiwa. Tuma ujumbe wowote ukitaka kuendelea.",
    },
    "no_hint": {
        "en": "There are no more hints for this one. Have a go, or say 'skip'.",
        "sw": "Hakuna dokezo zaidi kwa swali hili. Jaribu, au sema 'ruka'.",
    },
}


class WrongItemError(Exception):
    """The client answered a different item than the one waiting (e.g. a
    double-tap that would otherwise land on the NEXT item)."""


def submit_response(
    db: Session,
    *,
    session_id: uuid.UUID,
    raw_response: str,
    response_time_ms: int | None = None,
    expected_item_id: str | None = None,
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

    if expected_item_id is not None and expected_item_id != pending.id:
        raise WrongItemError(f"Item {expected_item_id} is not the one waiting ({pending.id}).")

    lang = session.language
    action = items.control_word(raw_response)
    # Coming back after "pause": this message only resumes. Re-send the
    # current question; never record it as an answer.
    if session.paused:
        session.paused = False
        db.flush()
        if action != "skip":
            return pending.text_for(session.channel, lang, session.pending_stage)
    if action == "pause":
        session.paused = True
        db.flush()
        return _CONTROL_REPLIES["pause"].get(lang.value) or _CONTROL_REPLIES["pause"]["en"]
    # Step 1 of a two-step memory item: "repeat"/"hint" show the things to
    # remember again; any other reply ("OK") moves on to the question and is
    # not an answer. Skip still skips.
    if pending.staged(session.channel) and session.pending_stage == 0 and action != "skip":
        if action in ("repeat", "hint"):
            return pending.text_for(session.channel, lang, 0)
        session.pending_stage = 1
        db.flush()
        return pending.text_for(session.channel, lang, 1)
    # Control words never count as an answer and never advance the session.
    if action == "repeat":
        return pending.text_for(session.channel, lang, session.pending_stage)
    if action == "hint":
        h = pending.hint(session.pending_hints, lang)
        if h is None:
            return _CONTROL_REPLIES["no_hint"].get(lang.value) or _CONTROL_REPLIES["no_hint"]["en"]
        session.pending_hints += 1
        db.flush()
        return h

    db.add(
        ItemResponse(
            session_id=session_id,
            item_id=pending.id,
            raw_response="" if action == "skip" else raw_response,
            response_time_ms=response_time_ms,
            hints_used=session.pending_hints,
            skipped=action == "skip",
        )
    )
    session.pending_hints = 0
    session.pending_stage = 0
    session.current_item_index = session.current_item_index + 1
    db.flush()

    nxt = items.select_next(_seen_item_ids(db, session_id))
    if nxt is None:
        _complete(db, session)
        return None
    return nxt.text_for(session.channel, lang, 0)


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
        # A skipped item is NOT scored: no DomainScore rather than a zero, so
        # skipping (as the intro promises) carries no penalty and can't create
        # a false "uneven profile" flag.
        if item is None or r.skipped:
            continue
        result = score_response(
            domain=item.domain,
            item_prompt=item.scoring_prompt(session.language),
            expected_reasoning=item.expected_reasoning,
            raw_response=item.describe_response(r.raw_response, session.language),
            language=session.language,
        )
        evidence = result.evidence_text
        if r.hints_used:
            evidence += f" (Answered after {r.hints_used} hint{'s' if r.hints_used > 1 else ''}: learning-velocity evidence.)"
        db.add(
            DomainScore(
                session_id=session.id,
                domain=item.domain,
                score=result.score,
                evidence_text=evidence,
                scoring_model_version=result.scoring_model_version,
            )
        )
    db.flush()

    # Aggregation & Flag Engine: writes flags + evidence only, never a decision.
    evaluate_and_flag(db, session.id)

    session.status = SessionStatus.completed
    session.completed_at = datetime.now(timezone.utc)
    db.flush()
