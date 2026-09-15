"""0007 school_record_imports + candidate_signals

Revision ID: 0007_imports_signals
Revises: 0006_context_flags_reviews
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.core import enums

revision = "0007_imports_signals"
down_revision = "0006_context_flags_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_record_imports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "record_type",
            sa.Enum(enums.RecordType, name="record_type", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column(
            "source_system",
            sa.Enum(enums.SourceSystem, name="source_system", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("raw_reference", sa.String(512), nullable=False),
    )

    # CandidateSignal: separate table from DomainScore, confidence fixed 'low'.
    op.create_table(
        "candidate_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=True),
        sa.Column("source_import_id", UUID(as_uuid=True), sa.ForeignKey("school_record_imports.id"), nullable=False),
        sa.Column(
            "signal_type",
            sa.Enum(enums.SignalType, name="signal_type", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("evidence_text", sa.Text, nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="low"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confidence = 'low'", name="ck_candidate_signal_low"),
    )
    op.create_index("ix_candidate_signals_learner_id", "candidate_signals", ["learner_id"])


def downgrade() -> None:
    op.drop_table("candidate_signals")
    op.drop_table("school_record_imports")
