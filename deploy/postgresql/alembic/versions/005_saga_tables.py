"""Add saga_instance table for Saga persistence.

Revision ID: 005
Revises: 004
Create Date: 2026-05-19

This migration creates saga_instance table for persisting Saga execution state.

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_add_archived_status
            └── 005_saga_tables (this file)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create saga_instance table."""
    op.create_table(
        "saga_instance",
        sa.Column("saga_id", sa.String(36), primary_key=True),
        sa.Column("saga_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("context_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saga_instance_saga_type", "saga_instance", ["saga_type"])
    op.create_index("ix_saga_instance_status", "saga_instance", ["status"])


def downgrade() -> None:
    """Drop saga_instance table."""
    op.drop_index("ix_saga_instance_status", table_name="saga_instance")
    op.drop_index("ix_saga_instance_saga_type", table_name="saga_instance")
    op.drop_table("saga_instance")
