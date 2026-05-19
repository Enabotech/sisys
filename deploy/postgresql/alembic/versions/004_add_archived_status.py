"""Add archived status to event_outbox CheckConstraint.

Revision ID: 004
Revises: 003
Create Date: 2026-05-19

This migration adds 'archived' status to event_outbox.status CheckConstraint,
allowing failed events to be archived after max retries exceeded.

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_add_archived_status (this file)
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 'archived' to event_outbox status CheckConstraint."""
    # Drop old constraint
    op.drop_constraint("ck_outbox_status_values", "event_outbox", type_="check")

    # Create new constraint with archived status
    op.create_check_constraint(
        "ck_outbox_status_values",
        "event_outbox",
        "status IN ('pending', 'published', 'failed', 'archived')",
    )


def downgrade() -> None:
    """Remove 'archived' from event_outbox status CheckConstraint."""
    # Drop new constraint
    op.drop_constraint("ck_outbox_status_values", "event_outbox", type_="check")

    # Recreate old constraint without archived
    op.create_check_constraint(
        "ck_outbox_status_values",
        "event_outbox",
        "status IN ('pending', 'published', 'failed')",
    )
