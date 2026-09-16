"""Screening Gateway API (Section 4).

Exposes session start/submit plus a mock-provider webhook so a full WhatsApp-style
conversation can be driven locally without any real provider credentials.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
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

    import uuid

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
