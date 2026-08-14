"""Add query indexes for strategic_archives table.

Revision ID: 009
Revises: 008
Create Date: 2026-08-14

This migration adds indexes to support ArchiveQuery filter conditions:
- ix_strategic_archives_plan_id on plan_id
- ix_strategic_archives_archive_type on archive_type
- ix_strategic_archives_archived_at on archived_at (used for ORDER BY + range filter)

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_saga_tables
            └── 005_documents
                └── 006_document_version_snapshots
                    └── 007_dictionary_tables
                        └── 008_strategic_archives
                            └── 009_strategic_archives_indexes (this file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    pass

# revision identifiers
revision = "009"
down_revision = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade: create indexes for strategic_archives query columns."""
    op.create_index("ix_strategic_archives_plan_id", "strategic_archives", ["plan_id"])
    op.create_index("ix_strategic_archives_archive_type", "strategic_archives", ["archive_type"])
    op.create_index("ix_strategic_archives_archived_at", "strategic_archives", ["archived_at"])


def downgrade() -> None:
    """Downgrade: drop indexes from strategic_archives table."""
    op.drop_index("ix_strategic_archives_archived_at", table_name="strategic_archives")
    op.drop_index("ix_strategic_archives_archive_type", table_name="strategic_archives")
    op.drop_index("ix_strategic_archives_plan_id", table_name="strategic_archives")
