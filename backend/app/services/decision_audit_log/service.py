"""Decision & Audit Log (Section 4 / Section 7).

The only entry point for writing the immutable flag -> decision trail. Callers
insert; nothing ever updates or deletes (the DB trigger from migration 0008
enforces this even against direct SQL).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import DecisionAuditLog


def log_event(
    db: Session,
    *,
    session_id: uuid.UUID,
    event_type: str,
    flag_event_id: uuid.UUID | None = None,
    panel_review_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> DecisionAuditLog:
    entry = DecisionAuditLog(
        session_id=session_id,
        flag_event_id=flag_event_id,
        panel_review_id=panel_review_id,
        event_type=event_type,
        detail=detail or {},
    )
    db.add(entry)
    db.flush()
    return entry
