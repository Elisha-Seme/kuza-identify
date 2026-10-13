"""Screening Gateway API (Section 4).

Exposes session start/submit plus a mock-provider webhook so a full WhatsApp-style
conversation can be driven locally without any real provider credentials.
"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.auth import SCREENING_OPERATE, Staff, require_roles
from app.core.config import get_settings
from app.core.db import get_db
from app.core.enums import Channel
from app.models import ChannelBinding, Learner, ScreeningSession
from app.core.webhook_security import shared_secret_valid, twilio_signature_valid
from app.providers.sms import get_provider as get_sms_provider
from app.providers.sms.base import OutboundSms
from app.providers.ussd import get_provider as get_ussd_provider
from app.providers.whatsapp import get_provider
from app.providers.whatsapp.base import OutboundMessage
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
    """Public, read-only view of the core session items (the 5 questions a
    child answers automatically). No answer keys, no scorer guidance."""
    return [items.public_view(i) for i in items.all_items()]


@router.get("/items/bonus", response_model=list[dict])
def list_bonus_items():
    """Off-level and creativity items (public view)."""
    return [items.public_view(i) for i in items.bonus_items()]


@router.get("/items/all", response_model=dict)
def list_all_items():
    """The whole multimedia bank for Kuza Play and facilitator mode: intro,
    control words and every item (public view: no answers, no scorer notes).
    Image paths are relative to MEDIA_BASE_URL / the dashboard's /items."""
    raw = items._load_raw()
    return {
        "session_intro": raw.get("session_intro"),
        "control_words": raw.get("control_words"),
        "domains": raw.get("domains"),
        "items": [items.public_view(i) for i in items.every_item()],
    }


# ---------------------------------------------------------------------------
# Phone -> session routing, persisted in channel_bindings (it used to be an
# in-memory dict, which serverless hosts wipe on every cold start, silently
# dropping live WhatsApp/SMS/USSD sessions). Numbers are stored hashed.
# ---------------------------------------------------------------------------
def _phone_hash(number: str) -> str:
    normalised = "".join(ch for ch in number if ch.isdigit())
    return hashlib.sha256(normalised.encode()).hexdigest()


def _bind(db: Session, channel: Channel, number: str, session_id: uuid.UUID, staff: Staff | None = None) -> None:
    key = (_phone_hash(number), channel)
    row = db.get(ChannelBinding, key)
    if row is not None and staff is not None and staff.school_id is not None and row.session_id != session_id:
        # Don't let one school's staff redirect a phone that is mid-session
        # for a learner at another school.
        current = db.get(ScreeningSession, row.session_id)
        if current is not None and current.status.value == "in_progress":
            learner = db.get(Learner, current.learner_id)
            if learner is None or learner.school_id != staff.school_id:
                raise HTTPException(409, "That phone is in an active session for another school.")
    if row is None:
        db.add(ChannelBinding(phone_hash=key[0], channel=channel, session_id=session_id))
    else:
        row.session_id = session_id
    db.commit()


def _bound_session(db: Session, channel: Channel, number: str) -> str | None:
    row = db.get(ChannelBinding, (_phone_hash(number), channel))
    return str(row.session_id) if row else None


def _unbind(db: Session, channel: Channel, number: str) -> None:
    row = db.get(ChannelBinding, (_phone_hash(number), channel))
    if row is not None:
        db.delete(row)
        db.commit()


def _check_bind_scope(db: Session, staff: Staff, session_id: str) -> uuid.UUID:
    """School staff may only bind sessions for learners at their own school."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(422, "session_id must be a UUID.")
    session = db.get(ScreeningSession, sid)
    if session is None:
        raise HTTPException(404, "No such screening session.")
    if session.status.value != "in_progress":
        raise HTTPException(409, "That session is already finished.")
    if staff.school_id is not None:
        learner = db.get(Learner, session.learner_id)
        if learner is None or learner.school_id != staff.school_id:
            raise HTTPException(403, "This learner is not at your school.")
    return sid


def _mock_only(provider_setting: str) -> None:
    """The JSON demo webhooks accept unsigned input, so they only exist while
    the matching provider is the mock. Once real Twilio is on, only the signed
    /twilio routes accept traffic."""
    if provider_setting != "mock":
        raise HTTPException(404, "Not found.")


def _media_for(db: Session, session_id: uuid.UUID) -> str | None:
    item = gateway.pending_item(db, session_id)
    if item is None:
        return None
    path = item.image_for(Channel.whatsapp, gateway.pending_stage(db, session_id))
    return get_settings().media_base_url.rstrip("/") + "/" + path if path else None


@router.post("/sessions", response_model=SessionStateResponse)
def start_session(body: StartSessionRequest, db: Session = Depends(get_db),
                  staff: Staff = Depends(require_roles(*SCREENING_OPERATE))):
    """Staff start a session for a consented learner (school staff: own school only)."""
    if staff.school_id is not None:
        learner = db.get(Learner, body.learner_id)
        if learner is None or learner.school_id != staff.school_id:
            raise HTTPException(403, "This learner is not at your school.")
    try:
        session, first_prompt = gateway.start_session(
            db, learner_id=body.learner_id, channel=body.channel, language=body.language
        )
    except gateway.ConsentMissingError as e:
        raise HTTPException(status_code=403, detail=str(e))
    db.commit()
    item = gateway.pending_item(db, session.id)
    return SessionStateResponse(
        session_id=session.id, status=session.status.value, next_prompt=first_prompt,
        item_id=item.id if item else None,
    )


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
def session_state(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Resume point for Kuza Play: which item is waiting. The session id is the
    capability (an unguessable UUID handed out by staff); nothing about the
    learner is returned."""
    session = db.get(ScreeningSession, session_id)
    if session is None:
        raise HTTPException(404, "No such screening session.")
    item = gateway.pending_item(db, session_id)
    return SessionStateResponse(
        session_id=session_id, status=session.status.value,
        next_prompt=gateway.next_prompt(db, session_id), item_id=item.id if item else None,
        channel=session.channel.value,
    )


@router.post("/responses", response_model=SessionStateResponse)
def submit_response(body: SubmitResponseRequest, db: Session = Depends(get_db)):
    try:
        next_prompt = gateway.submit_response(
            db,
            session_id=body.session_id,
            raw_response=body.raw_response,
            response_time_ms=body.response_time_ms,
            expected_item_id=body.item_id,
        )
    except gateway.WrongItemError as e:
        raise HTTPException(409, str(e))
    db.commit()
    status = "completed" if next_prompt is None else "in_progress"
    item = gateway.pending_item(db, body.session_id) if next_prompt is not None else None
    return SessionStateResponse(
        session_id=body.session_id, status=status, next_prompt=next_prompt,
        item_id=item.id if item else None,
    )


_COMPLETION_TEXT = "Asante! Umemaliza uchunguzi. / Thank you! You've finished the screener."


def _route_whatsapp_inbound(db: Session, from_number: str, text: str) -> str:
    """Shared by the mock JSON webhook and the real Twilio webhook: look up the
    session bound to this number, submit the response, send the next prompt
    (or the completion message) back, and return what was sent. Raises
    HTTPException(404) if no session is bound — callers decide how to
    present that (the mock route surfaces it directly; the Twilio route
    replies gracefully instead, see below)."""
    provider = get_provider()
    session_id = _bound_session(db, Channel.whatsapp, from_number)
    if session_id is None:
        raise HTTPException(
            status_code=404,
            detail="No active session for this number. Start one via POST /screening/sessions "
            "and register it with POST /screening/webhook/bind.",
        )
    sid = uuid.UUID(session_id)
    before = gateway.pending_item(db, sid)
    before_stage = gateway.pending_stage(db, sid)
    next_prompt = gateway.submit_response(db, session_id=sid, raw_response=text)
    db.commit()
    reply = next_prompt if next_prompt is not None else _COMPLETION_TEXT
    # Attach a picture only when there's a NEW one to show: a new question, or
    # step 2 of a memory item (not on a hint / repeat / pause reply).
    after = gateway.pending_item(db, sid) if next_prompt is not None else None
    moved = after is not None and (before is None or after.id != before.id
                                   or gateway.pending_stage(db, sid) != before_stage)
    media = _media_for(db, sid) if moved else None
    provider.send(OutboundMessage(to_number=from_number, text=reply, media_url=media))
    if next_prompt is None:
        _unbind(db, Channel.whatsapp, from_number)
    return reply


@router.post("/webhook/whatsapp", response_model=dict)
def whatsapp_webhook(payload: WhatsAppWebhookPayload, db: Session = Depends(get_db)):
    """Mock WhatsApp inbound (JSON {from, text}) for demos/tests. Disabled once
    WHATSAPP_PROVIDER is a real vendor (see _mock_only)."""
    _mock_only(get_settings().whatsapp_provider)
    provider = get_provider()
    inbound = provider.parse_webhook({"from": payload.from_, "text": payload.text})
    reply = _route_whatsapp_inbound(db, inbound.from_number, inbound.text)
    return {"delivered": reply}


@router.post("/webhook/whatsapp/twilio", response_class=PlainTextResponse)
async def whatsapp_webhook_twilio(request: Request, db: Session = Depends(get_db)) -> str:
    """Real Twilio WhatsApp inbound. Twilio POSTs form-encoded fields and signs
    the request with X-Twilio-Signature over the exact configured callback
    URL — verified here before anything is processed."""
    settings = get_settings()
    if not settings.twilio_auth_token or not settings.public_base_url:
        raise HTTPException(503, "Twilio webhook is not configured (TWILIO_AUTH_TOKEN / PUBLIC_BASE_URL).")
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    url = settings.public_base_url.rstrip("/") + str(request.url.path)
    if not twilio_signature_valid(
        url=url, params=params, signature=request.headers.get("X-Twilio-Signature"),
        auth_token=settings.twilio_auth_token,
    ):
        raise HTTPException(403, "Invalid Twilio signature.")

    provider = get_provider()
    inbound = provider.parse_webhook(params)
    try:
        _route_whatsapp_inbound(db, inbound.from_number, inbound.text)
    except HTTPException:
        # Unknown number: still 200 to Twilio (it isn't at fault), just no reply sent.
        pass
    return ""  # empty TwiML body: the reply already went out via the REST API send() above


@router.post("/webhook/bind", response_model=dict)
def bind_phone(from_: str, session_id: str, db: Session = Depends(get_db),
               staff: Staff = Depends(require_roles(*SCREENING_OPERATE))):
    """Staff: route a learner's WhatsApp number to a screening session."""
    sid = _check_bind_scope(db, staff, session_id)
    _bind(db, Channel.whatsapp, from_, sid, staff)
    return {"bound": True, "channel": "whatsapp", "session_id": str(sid)}


# ---------------------------------------------------------------------------
# SMS — the no-smartphone, no-data-plan channel. Works on any phone with
# airtime/signal, no app or internet needed. Async, sequential text, same
# shape as WhatsApp, so it reuses the gateway identically. Real delivery is
# Twilio (Section 6), same as WhatsApp; SMS_PROVIDER selects mock or twilio.
# ---------------------------------------------------------------------------
def _route_sms_inbound(db: Session, from_number: str, text: str) -> str:
    """Mirrors _route_whatsapp_inbound for the SMS provider/session map."""
    provider = get_sms_provider()
    session_id = _bound_session(db, Channel.sms, from_number)
    if session_id is None:
        raise HTTPException(
            status_code=404,
            detail="No active session for this number. Start one via POST /screening/sessions "
            "and register it with POST /screening/webhook/sms/bind.",
        )
    next_prompt = gateway.submit_response(db, session_id=uuid.UUID(session_id), raw_response=text)
    db.commit()
    reply = next_prompt if next_prompt is not None else _COMPLETION_TEXT
    provider.send(OutboundSms(to_number=from_number, text=reply))
    if next_prompt is None:
        _unbind(db, Channel.sms, from_number)
    return reply


@router.post("/webhook/sms", response_model=dict)
def sms_webhook(payload: WhatsAppWebhookPayload, db: Session = Depends(get_db)):
    """Mock SMS inbound (JSON {from, text}) — demo/tests. Real Twilio SMS
    traffic uses the signed /webhook/sms/twilio route below."""
    _mock_only(get_settings().sms_provider)
    provider = get_sms_provider()
    inbound = provider.parse_webhook({"from": payload.from_, "text": payload.text})
    reply = _route_sms_inbound(db, inbound.from_number, inbound.text)
    return {"delivered": reply}


@router.post("/webhook/sms/twilio", response_class=PlainTextResponse)
async def sms_webhook_twilio(request: Request, db: Session = Depends(get_db)) -> str:
    """Real Twilio SMS inbound. Same signature verification as the WhatsApp
    Twilio route (see there for why the URL, not request.url, is used)."""
    settings = get_settings()
    if not settings.twilio_auth_token or not settings.public_base_url:
        raise HTTPException(503, "Twilio webhook is not configured (TWILIO_AUTH_TOKEN / PUBLIC_BASE_URL).")
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    url = settings.public_base_url.rstrip("/") + str(request.url.path)
    if not twilio_signature_valid(
        url=url, params=params, signature=request.headers.get("X-Twilio-Signature"),
        auth_token=settings.twilio_auth_token,
    ):
        raise HTTPException(403, "Invalid Twilio signature.")

    provider = get_sms_provider()
    inbound = provider.parse_webhook(params)
    try:
        _route_sms_inbound(db, inbound.from_number, inbound.text)
    except HTTPException:
        pass
    return ""


@router.post("/webhook/sms/bind", response_model=dict)
def bind_sms_phone(from_: str, session_id: str, db: Session = Depends(get_db),
                   staff: Staff = Depends(require_roles(*SCREENING_OPERATE))):
    """Staff: route a learner's SMS number to a screening session."""
    sid = _check_bind_scope(db, staff, session_id)
    _bind(db, Channel.sms, from_, sid, staff)
    return {"bound": True, "channel": "sms", "session_id": str(sid)}


# ---------------------------------------------------------------------------
# USSD — dial a shortcode, no airtime or data needed at all. Synchronous,
# menu-based, one request/response per screen (see providers/ussd/base.py for
# why this can't share the WhatsApp/SMS shape). Best suited to the
# forced-choice item; a long written answer is a poor fit for a numeric
# keypad and a session clock outside our control, which is stated here rather
# than hidden.
# ---------------------------------------------------------------------------
@router.post("/webhook/ussd", response_class=PlainTextResponse)
async def ussd_webhook(request: Request, db: Session = Depends(get_db)) -> str:
    settings = get_settings()
    if settings.ussd_provider != "mock" and not settings.ussd_webhook_secret:
        # Fail closed: a real shortcode with no shared secret would accept
        # anyone's forged callbacks.
        raise HTTPException(503, "USSD_WEBHOOK_SECRET must be set when USSD_PROVIDER is not 'mock'.")
    if not shared_secret_valid(provided=request.query_params.get("key"), expected=settings.ussd_webhook_secret):
        # Africa's Talking doesn't sign callbacks, so USSD_WEBHOOK_SECRET (checked
        # against ?key=... on the callback URL) is the substitute. Not set -> skipped.
        raise HTTPException(403, "Invalid or missing USSD webhook key.")
    provider = get_ussd_provider()
    form = await request.form()
    turn = provider.parse_request(dict(form))

    session_id = _bound_session(db, Channel.ussd, turn.phone_number)
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
        _unbind(db, Channel.ussd, turn.phone_number)
        return "END Thank you. The screening is complete."
    return f"CON {next_prompt}"


@router.post("/webhook/ussd/bind", response_model=dict)
def bind_ussd_phone(from_: str, session_id: str, db: Session = Depends(get_db),
                    staff: Staff = Depends(require_roles(*SCREENING_OPERATE))):
    """Staff: route a learner's phone to a screening session for USSD."""
    sid = _check_bind_scope(db, staff, session_id)
    _bind(db, Channel.ussd, from_, sid, staff)
    return {"bound": True, "channel": "ussd", "session_id": str(sid)}
