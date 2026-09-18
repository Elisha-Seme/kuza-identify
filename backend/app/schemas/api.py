"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.core.enums import Channel, Language, NominatorRole, PanelDecision


# --- Screening ----------------------------------------------------------------
class StartSessionRequest(BaseModel):
    learner_id: uuid.UUID
    channel: Channel = Channel.whatsapp
    language: Language = Language.en


class SessionStateResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    next_prompt: str | None = None


class SubmitResponseRequest(BaseModel):
    session_id: uuid.UUID
    raw_response: str
    response_time_ms: int | None = None


# --- Mock WhatsApp webhook ----------------------------------------------------
class WhatsAppWebhookPayload(BaseModel):
    # Shape the mock provider POSTs; a real vendor webhook is normalised by the
    # provider's parse_webhook() before reaching the gateway.
    from_: str = Field(alias="from")
    text: str

    model_config = {"populate_by_name": True}


# --- Nomination ---------------------------------------------------------------
class NominationRequest(BaseModel):
    school_id: uuid.UUID
    nominator_role: NominatorRole
    checklist_responses: dict
    learner_id: uuid.UUID | None = None
    gender: str | None = None
    cohort_id: str | None = None
    guardian_identifier: str | None = None


class NominationResponse(BaseModel):
    learner_id: uuid.UUID
    nomination_id: uuid.UUID
    amber_flag_count: int


# --- Portfolio / work-sample evidence -----------------------------------------
class PortfolioRequest(BaseModel):
    school_id: uuid.UUID
    submitted_by_role: NominatorRole
    title: str
    description: str
    external_reference: str | None = None
    learner_id: uuid.UUID | None = None
    gender: str | None = None
    cohort_id: str | None = None


class PortfolioResponse(BaseModel):
    learner_id: uuid.UUID
    submission_id: uuid.UUID


# --- Panel review -------------------------------------------------------------
class DecisionRequest(BaseModel):
    reviewer_id: str
    decision: PanelDecision
    notes: str | None = None
