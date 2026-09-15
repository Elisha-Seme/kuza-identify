"""0004 screening_sessions

Revision ID: 0004_screening_sessions
Revises: 0003_nomination_records
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.core import enums

revision = "0004_screening_sessions"
down_revision = "0003_nomination_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(enums.Channel, name="channel", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.Enum(enums.Language, name="language", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(enums.SessionStatus, name="session_status", native_enum=False, length=64),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("current_item_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_screening_sessions_learner_id", "screening_sessions", ["learner_id"])


def downgrade() -> None:
    op.drop_table("screening_sessions")
