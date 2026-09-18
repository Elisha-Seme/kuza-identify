"""0009 portfolio_submissions

Revision ID: 0009_portfolio_submissions
Revises: 0008_decision_audit_log
Create Date: 2026-09-18

Added beyond the original Section 5 entity list, at the project owner's
request: a 4th evidence type (work samples / portfolios) alongside screening,
nomination, and passive signals. Purely additive — no existing table or
column changes. See app/models/entities.py::PortfolioSubmission for the
design rationale (pointer-not-inline, evidence-only, never a decision).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0009_portfolio_submissions"
down_revision = "0008_decision_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("submitted_by_role", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("external_reference", sa.String(512), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_portfolio_submissions_learner_id", "portfolio_submissions", ["learner_id"])


def downgrade() -> None:
    op.drop_table("portfolio_submissions")
