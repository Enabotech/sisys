"""Add dictionary_entries and dictionary_snapshots tables for domain dictionary management.

Revision ID: 007
Revises: 006
Create Date: 2026-08-11

This migration creates:
- dictionary_entries table: stores domain dictionary terms with optimistic locking
- dictionary_snapshots table: stores versioned snapshots for rollback capability

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_saga_tables
            └── 005_documents
                └── 006_document_version_snapshots
                    └── 007_dictionary_tables (this file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    pass

# revision identifiers
revision = "007"
down_revision = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade: create dictionary_entries and dictionary_snapshots tables."""
    # dictionary_entries table
    op.create_table(
        "dictionary_entries",
        sa.Column("term", sa.String(200), primary_key=True, comment="词条文本（业务主键）"),
        sa.Column("entity_type", sa.String(50), nullable=False, default="", comment="实体类型"),
        sa.Column("category", sa.String(50), nullable=False, server_default="general", comment="词条类别"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="是否启用"),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1"), comment="词条版本（乐观锁）"),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="", comment="创建者"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, comment="更新时间"),
    )

    # dictionary_snapshots table
    op.create_table(
        "dictionary_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), primary_key=True, comment="快照 UUID 主键"),
        sa.Column("version", sa.Integer(), nullable=False, unique=True, comment="词典版本号（唯一）"),
        sa.Column("entries", sa.dialects.postgresql.JSONB(), nullable=True, comment="完整词条快照"),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="", comment="创建者"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, comment="创建时间"),
        sa.Column("change_summary", sa.dialects.postgresql.JSONB(), nullable=True, comment="变更摘要"),
    )


def downgrade() -> None:
    """Downgrade: drop dictionary_entries and dictionary_snapshots tables."""
    op.drop_table("dictionary_snapshots")
    op.drop_table("dictionary_entries")
