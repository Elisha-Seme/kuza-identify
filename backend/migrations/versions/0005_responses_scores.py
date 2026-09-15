"""0005 item_responses + domain_scores

Revision ID: 0005_responses_scores
Revises: 0004_screening_sessions
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_responses_scores"
down_revision = "0004_screening_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("raw_response", sa.Text, nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_item_responses_session_id", "item_responses", ["session_id"])

    op.create_table(
        "domain_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("evidence_text", sa.Text, nullable=False),
        sa.Column("scoring_model_version", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_domain_score_range"),
    )
    op.create_index("ix_domain_scores_session_id", "domain_scores", ["session_id"])


def downgrade() -> None:
    op.drop_table("domain_scores")
    op.drop_table("item_responses")
