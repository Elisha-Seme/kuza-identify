"""Screening Gateway API (Section 4).

Exposes session start/submit plus a mock-provider webhook so a full WhatsApp-style
conversation can be driven locally without any real provider credentials.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.providers.sms.base import OutboundSms
from app.providers.sms.mock import get_provider as get_sms_provider
from app.providers.ussd.mock import get_provider as get_ussd_provider
from app.providers.whatsapp.base import OutboundMessage
from app.providers.whatsapp.mock import get_provider
from app.schemas.api import (
    SessionStateResponse,
    StartSessionRequest,
    SubmitResponseRequest,
    WhatsAppWebhookPayload,
)
from app.services.adaptive_item_engine import engine as items
from app.services.screening_gateway import service as gateway

router = APIRouter(prefix="/screening", tags=["screening"])


@router.get("/intro", response_model=dict)
def get_intro():
    """The bilingual, untimed/no-penalty framing shown once before the first
    item (see item_bank.json `session_intro`). Public and read-only."""
    from app.core.enums import Language

    return {
        "en": items.session_intro(Language.en) or "",
        "sw": items.session_intro(Language.sw) or "",
    }


@router.get("/items", response_model=list[dict])
def list_items():
    """Public, read-only view of the screening item set (the 5 questions a child
    answers). Excludes the internal scoring guidance (`expected_reasoning`)."""
    return [
        {
            "id": i.id,
            "domain": i.domain,
            "difficulty": i.difficulty,
            "prompt": i.prompt,
        }
        for i in items.all_items()
    ]


@router.get("/items/bonus", response_model=list[dict])
def list_bonus_items():
    """Off-level and creativity items — additional evidence content, not yet
    part of the automatic 5-question session (see engine.py docstring)."""
    return [
        {
            "id": i.id,
            "domain": i.domain,
            "difficulty": i.difficulty,
            "tier": i.tier,
            "prompt": i.prompt,
        }
        for i in items.bonus_items()
    ]

# In-memory phone -> session routing for the MOCK provider only. This is ephemeral
# transport routing, not learner data; a real vendor carries its own conversation
# id. Session *progress* is always persisted (resume-safe) — only this routing map
# is in memory.
_phone_sessions: dict[str, str] = {}


@router.post("/sessions", response_model=SessionStateResponse)
def start_session(body: StartSessionRequest, db: Session = Depends(get_db)):
    try:
        session, first_prompt = gateway.start_session(
            db, learner_id=body.learner_id, channel=body.channel, language=body.language
        )
    except gateway.ConsentMissingError as e:
        raise HTTPException(status_code=403, detail=str(e))
    db.commit()
    return SessionStateResponse(
        session_id=session.id, status=session.status.value, next_prompt=first_prompt
    )


@router.post("/responses", response_model=SessionStateResponse)
def submit_response(body: SubmitResponseRequest, db: Session = Depends(get_db)):
    next_prompt = gateway.submit_response(
        db,
        session_id=body.session_id,
        raw_response=body.raw_response,
        response_time_ms=body.response_time_ms,
    )
    db.commit()
    status = "completed" if next_prompt is None else "in_progress"
    return SessionStateResponse(
        session_id=body.session_id, status=status, next_prompt=next_prompt
    )


@router.post("/webhook/whatsapp", response_model=dict)
def whatsapp_webhook(payload: WhatsAppWebhookPayload, db: Session = Depends(get_db)):
    """Mock WhatsApp inbound. Routes the message to the caller's active session,
    records it, and pushes the next item back through the (mock) provider."""
    provider = get_provider()
    inbound = provider.parse_webhook({"from": payload.from_, "text": payload.text})

    session_id = _phone_sessions.get(inbound.from_number)
    if session_id is None:
        raise HTTPException(
            status_code=404,
            detail="No active session for this number. Start one via POST /screening/sessions "
            "and register it with POST /screening/webhook/bind.",
        )

    next_prompt = gateway.submit_response(
        db, session_id=uuid.UUID(session_id), raw_response=inbound.text
    )
    db.commit()

    if next_prompt is not None:
        provider.send(OutboundMessage(to_number=inbound.from_number, text=next_prompt))
    else:
        provider.send(
            OutboundMessage(
                to_number=inbound.from_number,
                text="Asante! Umemaliza uchunguzi. / Thank you! You've finished the screener.",
            )
        )
        _phone_sessions.pop(inbound.from_number, None)
    return {"delivered": provider.last_message_to(inbound.from_number)}


@router.post("/webhook/bind", response_model=dict)
def bind_phone(from_: str, session_id: str):
    """Demo helper: associate a phone number with a session for the mock webhook."""
    _phone_sessions[from_] = session_id
    return {"bound": {from_: session_id}}


# ---------------------------------------------------------------------------
# SMS — the no-smartphone, no-data-plan channel. Works on any phone with
# airtime/signal, no app or internet needed. Async, sequential text, same
# shape as WhatsApp, so it reuses the gateway identically. No real Africa's
# Talking credentials yet — this is the mock provider (Section 6).
# ---------------------------------------------------------------------------
_sms_phone_sessions: dict[str, str] = {}


@router.post("/webhook/sms", response_model=dict)
def sms_webhook(payload: WhatsAppWebhookPayload, db: Session = Depends(get_db)):
    """Mock SMS inbound. Same routing pattern as the WhatsApp webhook."""
    provider = get_sms_provider()
    inbound = provider.parse_webhook({"from": payload.from_, "text": payload.text})

    session_id = _sms_phone_sessions.get(inbound.from_number)
    if session_id is None:
        raise HTTPException(
            status_code=404,
            detail="No active session for this number. Start one via POST /screening/sessions "
            "and register it with POST /screening/webhook/sms/bind.",
        )

    next_prompt = gateway.submit_response(
        db, session_id=uuid.UUID(session_id), raw_response=inbound.text
    )
    db.commit()

    if next_prompt is not None:
        provider.send(OutboundSms(to_number=inbound.from_number, text=next_prompt))
    else:
        provider.send(
            OutboundSms(
                to_number=inbound.from_number,
                text="Asante! Umemaliza uchunguzi. / Thank you! You've finished the screener.",
            )
        )
        _sms_phone_sessions.pop(inbound.from_number, None)
    return {"delivered": provider.last_message_to(inbound.from_number)}


@router.post("/webhook/sms/bind", response_model=dict)
def bind_sms_phone(from_: str, session_id: str):
    """Demo helper: associate a phone number with a session for the mock SMS webhook."""
    _sms_phone_sessions[from_] = session_id
    return {"bound": {from_: session_id}}


# ---------------------------------------------------------------------------
# USSD — dial a shortcode, no airtime or data needed at all. Synchronous,
# menu-based, one request/response per screen (see providers/ussd/base.py for
# why this can't share the WhatsApp/SMS shape). Best suited to the
# forced-choice item; a long written answer is a poor fit for a numeric
# keypad and a session clock outside our control, which is stated here rather
# than hidden.
# ---------------------------------------------------------------------------
_ussd_phone_sessions: dict[str, str] = {}


@router.post("/webhook/ussd", response_class=PlainTextResponse)
async def ussd_webhook(request: Request, db: Session = Depends(get_db)) -> str:
    provider = get_ussd_provider()
    form = await request.form()
    turn = provider.parse_request(dict(form))

    session_id = _ussd_phone_sessions.get(turn.phone_number)
    if session_id is None:
        return "END No active screening for this number. Ask a reviewer to register you first."

    # Africa's Talking sends the full input chain ("1*2*hello"); only the
    # latest keypress is this turn's answer. Empty text means first dial —
    # nothing to record yet, just show where the learner is.
    latest = turn.text.split("*")[-1] if turn.text else ""

    if turn.text == "":
        prompt = gateway.next_prompt(db, uuid.UUID(session_id))
        if prompt is None:
            return "END This screening is already complete. Thank you."
        return f"CON {prompt}"

    next_prompt = gateway.submit_response(
        db, session_id=uuid.UUID(session_id), raw_response=latest
    )
    db.commit()

    if next_prompt is None:
        _ussd_phone_sessions.pop(turn.phone_number, None)
        return "END Thank you. The screening is complete."
    return f"CON {next_prompt}"


@router.post("/webhook/ussd/bind", response_model=dict)
def bind_ussd_phone(from_: str, session_id: str):
    """Demo helper: associate a phone number with a session for the mock USSD webhook."""
    _ussd_phone_sessions[from_] = session_id
    return {"bound": {from_: session_id}}
