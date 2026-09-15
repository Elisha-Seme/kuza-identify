"""0003 nomination_records

Revision ID: 0003_nomination_records
Revises: 0002_learners_consent
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core import enums

revision = "0003_nomination_records"
down_revision = "0002_learners_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nomination_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column(
            "nominator_role",
            sa.Enum(enums.NominatorRole, name="nominator_role", native_enum=False, length=64),
            nullable=False,
        ),
        sa.Column("checklist_responses", JSONB, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_nomination_records_learner_id", "nomination_records", ["learner_id"])


def downgrade() -> None:
    op.drop_table("nomination_records")
