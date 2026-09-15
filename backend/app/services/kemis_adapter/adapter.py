"""KEMIS Integration Adapter — INTERFACE AND TYPES ONLY (Section 6 / Section 8).

Phase 0 explicitly does NOT implement this against a real KEMIS endpoint. No
public KEMIS API is documented and access is a pending Ministry-of-Education
data-sharing question (Section 9). The adapter's job is to isolate every
KEMIS-specific auth/schema/access-model detail behind one interface so that the
rest of the system only ever sees a NormalizedSchoolRecord — identical to a
spreadsheet a partner school emailed over (SchoolRecordImport, Section 5).

When (and only when) a real data-sharing arrangement exists, add a concrete
implementation of KemisAdapter here. Nothing downstream changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.enums import RecordType


@dataclass(frozen=True)
class NormalizedSchoolRecord:
    """The single shape the rest of the system consumes, regardless of source.

    Deliberately carries NO learner name, diagnosis, or health field. The learner
    is referenced by a pseudonymous per-school key the adapter is responsible for
    mapping (never a national ID exposed downstream).
    """

    school_ref: str
    learner_ref: str  # pseudonymous, school-scoped
    record_type: RecordType
    payload: dict  # normalized grade/attendance/remark data — never raw portal HTML
    observed_at: datetime


class KemisAdapter(Protocol):
    """The contract a real KEMIS implementation must satisfy. Not implemented in
    Phase 0 — any call raises NotImplementedError via the stub below."""

    def fetch_records(
        self, *, school_ref: str, since: datetime | None = None
    ) -> list[NormalizedSchoolRecord]:
        """Return normalized records for one school. Real impl handles KEMIS auth,
        paging, and schema quirks internally."""


class NotConnectedKemisAdapter:
    """Phase 0 stub. Present so wiring/types compile and tests can assert the
    'not connected' contract, but it never talks to a real endpoint."""

    def fetch_records(
        self, *, school_ref: str, since: datetime | None = None
    ) -> list[NormalizedSchoolRecord]:
        raise NotImplementedError(
            "KEMIS integration is not connected in Phase 0. Build a concrete "
            "KemisAdapter only once a Ministry-of-Education data-sharing "
            "arrangement exists (spec Section 6 / 8 / 9)."
        )
