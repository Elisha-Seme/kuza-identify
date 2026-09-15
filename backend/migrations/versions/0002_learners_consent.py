"""0002 learners + consent_records

Revision ID: 0002_learners_consent
Revises: 0001_schools
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from app.core import enums

revision = "0002_learners_consent"
down_revision = "0001_schools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learners",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("cohort_id", sa.String(64), nullable=True),
        sa.Column("gender", sa.String(32), nullable=True),
        sa.Column(
            "source",
            sa.Enum(enums.LearnerSource, name="learner_source", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_learners_school_id", "learners", ["school_id"])

    op.create_table(
        "consent_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("guardian_identifier", sa.String(128), nullable=False),
        sa.Column(
            "scope",
            sa.Enum(enums.ConsentScope, name="consent_scope", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_consent_records_learner_id", "consent_records", ["learner_id"])


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_table("learners")
