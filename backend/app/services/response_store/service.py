"""Response Store (Section 4) — append-only access to raw ItemResponses.

The Store is the ItemResponse table plus these read helpers. Writes happen only
through the Screening Gateway; nothing here updates or deletes a response.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ItemResponse


def responses_for_session(db: Session, session_id: uuid.UUID) -> list[ItemResponse]:
    return list(
        db.scalars(
            select(ItemResponse)
            .where(ItemResponse.session_id == session_id)
            .order_by(ItemResponse.created_at)
        )
    )
