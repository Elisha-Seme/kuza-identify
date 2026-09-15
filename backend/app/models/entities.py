"""ORM models — one class per entity in Section 5, in spec order.

Design rules baked into this schema (non-negotiable, from Section 3 & 5):
  * NO name field on any person, NO diagnosis field, NO health field anywhere.
    (School.name is a *school's* name and is part of Section 5 — retained.)
  * NO composite / average / aggregate score column anywhere. Domains stay
    independent; the Aggregation Engine flags on max per-domain deviation.
  * CandidateSignal is a SEPARATE table from DomainScore, on purpose, so a
    low-confidence passive inference can never be read as direct evidence.
  * DomainScore / FlagEvent carry evidence and flags only. The decision lives
    solely on PanelReview. The flag -> decision path is logged immutably in
    DecisionAuditLog.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import enums
from app.core.db import Base


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _enum(py_enum, name: str):
    # native_enum=False -> stored as VARCHAR + CHECK, avoiding pg-enum migration pain.
    return Enum(py_enum, name=name, native_enum=False, length=64, validate_strings=True)


class School(Base):
    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = _pk()
    # School name (an organisation, not a person) — part of Section 5.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Resource context tier, used for score adjustment — NOT a value judgement.
    tier: Mapped[str] = mapped_column(String(64), nullable=False)
    network: Mapped[str | None] = mapped_column(String(255), nullable=True)

    learners: Mapped[list["Learner"]] = relationship(back_populates="school")


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[uuid.UUID] = _pk()  # pseudonymous, system-generated
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id"), nullable=False
    )
    # cohort_id is a bare identifier — Section 5 defines no Cohort entity.
    cohort_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)  # optional
    source: Mapped[enums.LearnerSource] = mapped_column(
        _enum(enums.LearnerSource, "learner_source"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    school: Mapped[School] = relationship(back_populates="learners")


class NominationRecord(Base):
    __tablename__ = "nomination_records"

    id: Mapped[uuid.UUID] = _pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learners.id"), nullable=False
    )
    nominator_role: Mapped[enums.NominatorRole] = mapped_column(
        _enum(enums.NominatorRole, "nominator_role"), nullable=False
    )
    # Structured checklist, includes 2e amber-flag items. JSONB, never free names.
    checklist_responses: Mapped[dict] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScreeningSession(Base):
    __tablename__ = "screening_sessions"

    id: Mapped[uuid.UUID] = _pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learners.id"), nullable=False
    )
    channel: Mapped[enums.Channel] = mapped_column(
        _enum(enums.Channel, "channel"), nullable=False
    )
    language: Mapped[enums.Language] = mapped_column(
        _enum(enums.Language, "language"), nullable=False
    )
    status: Mapped[enums.SessionStatus] = mapped_column(
        _enum(enums.SessionStatus, "session_status"),
        default=enums.SessionStatus.in_progress,
        nullable=False,
    )
    # Cursor into the item bank so a dropped session can resume (Section 3.4).
    current_item_index: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    responses: Mapped[list["ItemResponse"]] = relationship(back_populates="session")


class ItemResponse(Base):
    """Response Store — append-only (Section 4). No updates in application code."""

    __tablename__ = "item_responses"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screening_sessions.id"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ScreeningSession] = relationship(back_populates="responses")


class DomainScore(Base):
    """Per-domain score + evidence. NO composite score exists in this system."""

    __tablename__ = "domain_scores"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screening_sessions.id"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_domain_score_range"),
    )


class ContextAdjustment(Base):
    """Section 5 gives this NO id — keyed by (school_id, domain, effective_from).

    Phase 0: populated from a simple school-tier lookup table, not a trained model.
    """

    __tablename__ = "context_adjustments"

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id"), primary_key=True
    )
    domain: Mapped[str] = mapped_column(String(64), primary_key=True)
    adjustment_factor: Mapped[float] = mapped_column(Float, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )


class FlagEvent(Base):
    """A flag raised by the Aggregation & Flag Engine. Evidence, never a decision."""

    __tablename__ = "flag_events"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screening_sessions.id"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_description: Mapped[str] = mapped_column(Text, nullable=False)
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PanelReview(Base):
    """The ONLY entity that carries a decision. Written by a human reviewer."""

    __tablename__ = "panel_reviews"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screening_sessions.id"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[enums.PanelDecision] = mapped_column(
        _enum(enums.PanelDecision, "panel_decision"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SchoolRecordImport(Base):
    __tablename__ = "school_record_imports"

    id: Mapped[uuid.UUID] = _pk()
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id"), nullable=False
    )
    record_type: Mapped[enums.RecordType] = mapped_column(
        _enum(enums.RecordType, "record_type"), nullable=False
    )
    source_system: Mapped[enums.SourceSystem] = mapped_column(
        _enum(enums.SourceSystem, "source_system"), nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Pointer to stored file/table — never embedded inline (Section 5).
    raw_reference: Mapped[str] = mapped_column(String(512), nullable=False)


class CandidateSignal(Base):
    """Passive-mining output. SEPARATE from DomainScore by design. Advisory only:
    invites a child to screen, never advances them (Section 2 / 7)."""

    __tablename__ = "candidate_signals"

    id: Mapped[uuid.UUID] = _pk()
    # nullable — a Learner stub may not exist until a signal fires (Section 5).
    learner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learners.id"), nullable=True
    )
    source_import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("school_record_imports.id"), nullable=False
    )
    signal_type: Mapped[enums.SignalType] = mapped_column(
        _enum(enums.SignalType, "signal_type"), nullable=False
    )
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Fixed low — structurally cannot outrank an active DomainScore (Section 5).
    confidence: Mapped[str] = mapped_column(
        String(16), default="low", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence = 'low'", name="ck_candidate_signal_low"),
    )


class ConsentRecord(Base):
    """DPA 2019 — consent captured before any screening session starts (Section 7)."""

    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = _pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learners.id"), nullable=False
    )
    guardian_identifier: Mapped[str] = mapped_column(
        String(128), nullable=False
    )  # pseudonymous
    scope: Mapped[enums.ConsentScope] = mapped_column(
        _enum(enums.ConsentScope, "consent_scope"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DecisionAuditLog(Base):
    """Decision & Audit Log (Section 4). Append-only, immutable record of every
    flag -> decision path. Not named as an entity in Section 5's list, but required
    by Section 4 and the constraints; added as the minimal realisation of it.

    Immutability is enforced two ways: application code only ever inserts, and a
    DB trigger (see migration) rejects UPDATE and DELETE.
    """

    __tablename__ = "decision_audit_log"

    id: Mapped[uuid.UUID] = _pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screening_sessions.id"), nullable=False
    )
    # The flag(s) and the review this path connects. Either may be null at the
    # moment of logging (a flag fires before any decision exists).
    flag_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("flag_events.id"), nullable=True
    )
    panel_review_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("panel_reviews.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
