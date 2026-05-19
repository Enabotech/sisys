"""Add audit tables with RLS.

Revision ID: 002
Revises: 001
Create audit_log and audit_outbox tables with Row-Level Security for immutability.
Reference: Story 1.10 - AC-2 Immutable Storage
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_log and audit_outbox tables with RLS."""
    # =======================================================================
    # Audit Log Table
    # =======================================================================
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("log_id", sa.UUID(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("target_resource", sa.String(500), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("new_value", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("correction_level", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("log_id"),
        sa.CheckConstraint(
            "correction_level IS NULL OR (correction_level >= 0 AND correction_level <= 3)",
            name="ck_audit_correction_level_range",
        ),
    )

    # Indexes for multi-dimensional search (FR-SC-04)
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"])
    op.create_index("ix_audit_log_action_type", "audit_log", ["action_type"])
    op.create_index("ix_audit_log_correction_level", "audit_log", ["correction_level"])
    op.create_index("ix_audit_log_timestamp_actor", "audit_log", ["timestamp", "actor"])
    op.create_index("ix_audit_log_timestamp_action_type", "audit_log", ["timestamp", "action_type"])

    # =======================================================================
    # Audit Outbox Table (Transaction Outbox Pattern)
    # =======================================================================
    op.create_table(
        "audit_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'published', 'failed', 'archived')",
            name="ck_audit_outbox_status",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_audit_outbox_retry_count"),
        sa.CheckConstraint("max_retries >= 0", name="ck_audit_outbox_max_retries"),
    )

    op.create_index("ix_audit_outbox_status", "audit_outbox", ["status"])
    op.create_index("ix_audit_outbox_created_at", "audit_outbox", ["created_at"])

    # =======================================================================
    # Row-Level Security (RLS) for Immutability
    # Only the postgres system role can modify records after insert
    # Regular application users can only INSERT and SELECT
    # =======================================================================
    # Note: RLS requires the table to be owned by a superuser or
    # the session_user for non-owner scenarios. For production,
    # ensure the application runs with a restricted role.

    # Enable RLS on audit_log
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")

    # Create policy: Allow only INSERT and SELECT (no UPDATE, no DELETE)
    op.execute(
        """
        CREATE POLICY audit_log_immutable_insert_only ON audit_log
        FOR INSERT
        WITH CHECK (true)
    """
    )

    op.execute(
        """
        CREATE POLICY audit_log_immutable_select ON audit_log
        FOR SELECT
        USING (true)
    """
    )

    # Deny UPDATE operations explicitly
    op.execute(
        """
        CREATE POLICY audit_log_deny_update ON audit_log
        FOR UPDATE
        USING (false)
        WITH CHECK (false)
    """
    )

    # Deny DELETE operations explicitly
    op.execute(
        """
        CREATE POLICY audit_log_deny_delete ON audit_log
        FOR DELETE
        USING (false)
        WITH CHECK (false)
    """
    )

    # Enable RLS on audit_outbox (allows updates for retry logic)
    op.execute("ALTER TABLE audit_outbox ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY audit_outbox_insert_only ON audit_outbox
        FOR INSERT
        WITH CHECK (true)
    """
    )

    op.execute(
        """
        CREATE POLICY audit_outbox_select ON audit_outbox
        FOR SELECT
        USING (true)
    """
    )

    # Allow UPDATE only for status transitions (retry logic)
    # Valid transitions:
    #   pending  -> published (after successful processing)
    #   pending  -> failed    (after processing error)
    #   failed   -> pending   (retry after cooldown)
    # Terminal state 'published' cannot transition to any other state
    op.execute(
        """
        CREATE POLICY audit_outbox_update_status ON audit_outbox
        FOR UPDATE
        USING (
            -- Only rows in non-terminal state can be updated
            -- AND the transition must be valid
            CASE
                WHEN old.status = 'pending' THEN NEW.status IN ('published', 'failed')
                WHEN old.status = 'failed' THEN NEW.status = 'pending'
                ELSE FALSE
            END
        )
        WITH CHECK (
            -- The new status must be a valid transition from old status
            CASE
                WHEN old.status = 'pending' THEN NEW.status IN ('published', 'failed')
                WHEN old.status = 'failed' THEN NEW.status = 'pending'
                ELSE FALSE
            END
        )
    """
    )

    # Deny DELETE (outbox entries should be retained for audit)
    op.execute(
        """
        CREATE POLICY audit_outbox_deny_delete ON audit_outbox
        FOR DELETE
        USING (false)
        WITH CHECK (false)
    """
    )


def downgrade() -> None:
    """Drop audit tables and RLS policies."""
    op.execute("DROP POLICY IF EXISTS audit_log_immutable_insert_only ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_immutable_select ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_deny_update ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_deny_delete ON audit_log")
    op.execute("ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS audit_outbox_insert_only ON audit_outbox")
    op.execute("DROP POLICY IF EXISTS audit_outbox_select ON audit_outbox")
    op.execute("DROP POLICY IF EXISTS audit_outbox_update_status ON audit_outbox")
    op.execute("DROP POLICY IF EXISTS audit_outbox_deny_delete ON audit_outbox")
    op.execute("ALTER TABLE audit_outbox DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_audit_outbox_created_at", table_name="audit_outbox")
    op.drop_index("ix_audit_outbox_status", table_name="audit_outbox")
    op.drop_table("audit_outbox")

    op.drop_index("ix_audit_log_timestamp_action_type", table_name="audit_log")
    op.drop_index("ix_audit_log_timestamp_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_correction_level", table_name="audit_log")
    op.drop_index("ix_audit_log_action_type", table_name="audit_log")
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
