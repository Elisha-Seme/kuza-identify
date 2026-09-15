"""0008 decision_audit_log — append-only, immutable (Section 4 / Section 7)

Revision ID: 0008_decision_audit_log
Revises: 0007_imports_signals
Create Date: 2026-09-15

Immutability is enforced at the database level: a trigger raises on any UPDATE
or DELETE, so even a bug or a direct SQL session cannot rewrite the flag ->
decision history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008_decision_audit_log"
down_revision = "0007_imports_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("screening_sessions.id"), nullable=False),
        sa.Column("flag_event_id", UUID(as_uuid=True), sa.ForeignKey("flag_events.id"), nullable=True),
        sa.Column("panel_review_id", UUID(as_uuid=True), sa.ForeignKey("panel_reviews.id"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_decision_audit_log_session_id", "decision_audit_log", ["session_id"])

    # --- Immutability: reject UPDATE and DELETE at the DB level ---------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION kuza_reject_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'decision_audit_log is append-only; % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_audit_log_immutable
        BEFORE UPDATE OR DELETE ON decision_audit_log
        FOR EACH ROW EXECUTE FUNCTION kuza_reject_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_decision_audit_log_immutable ON decision_audit_log;")
    op.execute("DROP FUNCTION IF EXISTS kuza_reject_mutation();")
    op.drop_table("decision_audit_log")
