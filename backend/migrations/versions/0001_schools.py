"""0001 schools

Revision ID: 0001_schools
Revises:
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_schools"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(64), nullable=False),
        sa.Column("network", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("schools")
