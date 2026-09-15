"""0006 context_adjustments + flag_events + panel_reviews

Revision ID: 0006_context_flags_reviews
Revises: 0005_responses_scores
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.core import enums

revision = "0006_context_flags_reviews"
down_revision = "0005_responses_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ContextAdjustment: Section 5 defines NO id — composite PK.
    op.create_table(
        "context_adjustments",
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id"), primary_key=True),
        sa.Column("domain", sa.String(64), primary_key=True),
        sa.Column("adjustment_factor", sa.Float, nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), server_default=sa.text("now()"), primary_key=True),
    )

    op.create_table(
        "flag_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("rule_description", sa.Text, nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_flag_events_session_id", "flag_events", ["session_id"])

    op.create_table(
        "panel_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column(
            "decision",
            sa.Enum(enums.PanelDecision, name="panel_decision", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_panel_reviews_session_id", "panel_reviews", ["session_id"])


def downgrade() -> None:
    op.drop_table("panel_reviews")
    op.drop_table("flag_events")
    op.drop_table("context_adjustments")
