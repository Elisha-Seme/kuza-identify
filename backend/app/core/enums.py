"""Enumerations mirrored exactly from the data model in Section 5 of the spec.

These are the single source of truth for the constrained string values used by
both the SQLAlchemy models and the Alembic migrations. Keeping them here means a
value can never drift between the schema and the application layer.
"""
from __future__ import annotations

import enum


class LearnerSource(str, enum.Enum):
    """Learner.source — how the learner entered Layer 1 (Section 2 pathways)."""

    active_screening = "active_screening"
    nomination = "nomination"
    passive_signal = "passive_signal"


class Channel(str, enum.Enum):
    """ScreeningSession.channel. USSD is modelled but out of scope for Phase 0."""

    whatsapp = "whatsapp"
    ussd = "ussd"


class Language(str, enum.Enum):
    """ScreeningSession.language — bilingual by default (Section 7)."""

    en = "en"
    sw = "sw"


class SessionStatus(str, enum.Enum):
    """ScreeningSession.status — supports interruption/resume (Section 3.4)."""

    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class NominatorRole(str, enum.Enum):
    """NominationRecord.nominator_role."""

    teacher = "teacher"
    parent = "parent"


class PanelDecision(str, enum.Enum):
    """PanelReview.decision — the ONLY place a decision is ever written."""

    advance = "advance"
    hold = "hold"
    decline = "decline"


class RecordType(str, enum.Enum):
    """SchoolRecordImport.record_type."""

    grades = "grades"
    attendance = "attendance"
    teacher_remarks = "teacher_remarks"
    assignment_scan = "assignment_scan"  # Phase 2 (OCR) — modelled, not ingested


class SourceSystem(str, enum.Enum):
    """SchoolRecordImport.source_system — a KEMIS record and a school spreadsheet
    look identical downstream; only the adapter knows the difference (Section 4)."""

    school_local = "school_local"
    kemis = "kemis"


class SignalType(str, enum.Enum):
    """CandidateSignal.signal_type — passive-mining spike signatures (Section 3.7)."""

    grade_variance = "grade_variance"
    remark_nlp_flag = "remark_nlp_flag"
    attendance_discrepancy = "attendance_discrepancy"


class ConsentScope(str, enum.Enum):
    """ConsentRecord.scope — DPA 2019 purpose limitation (Section 7)."""

    screening = "screening"
    nomination = "nomination"
    secondary_use_of_school_records = "secondary_use_of_school_records"
