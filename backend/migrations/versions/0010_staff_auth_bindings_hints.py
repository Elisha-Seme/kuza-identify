"""0010 staff users, channel bindings, hint/skip evidence

Revision ID: 0010_staff_auth_bindings_hints
Revises: 0009_portfolio_submissions
Create Date: 2026-10-13

* staff_users: sign-in for reviewers / admins / auditors / school staff, so the
  panel and admin routes are no longer open to anyone with the API URL.
* channel_bindings: phone -> session routing for WhatsApp/SMS/USSD, persisted
  (it was an in-memory dict, lost on every serverless cold start). Phone numbers
  are stored hashed.
* item_responses.hints_used / skipped and screening_sessions.pending_hints /
  pending_stage (two-step memory items on phone channels):
  learning-velocity evidence and an honest "skip" (never scored as zero).

Purely additive; no existing column changes meaning.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010_staff_auth_bindings_hints"
down_revision = "0009_portfolio_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "channel_bindings",
        sa.Column("phone_hash", sa.String(64), primary_key=True),
        sa.Column("channel", sa.String(64), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column("item_responses", sa.Column("hints_used", sa.Integer, nullable=False, server_default="0"))
    op.add_column("item_responses", sa.Column("skipped", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("screening_sessions", sa.Column("pending_hints", sa.Integer, nullable=False, server_default="0"))
    op.add_column("screening_sessions", sa.Column("pending_stage", sa.Integer, nullable=False, server_default="0"))
    op.add_column("screening_sessions", sa.Column("paused", sa.Boolean, nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("screening_sessions", "paused")
    op.drop_column("screening_sessions", "pending_stage")
    op.drop_column("screening_sessions", "pending_hints")
    op.drop_column("item_responses", "skipped")
    op.drop_column("item_responses", "hints_used")
    op.drop_table("channel_bindings")
    op.drop_table("staff_users")
