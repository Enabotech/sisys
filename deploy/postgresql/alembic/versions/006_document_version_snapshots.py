"""Add document_version_snapshots table for version snapshot persistence.

Revision ID: 006
Revises: 005
Create Date: 2026-08-01

This migration creates the document_version_snapshots table with
document_id foreign key to documents table and unique constraint
on (document_id, version).

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_saga_tables
            └── 005_documents
                └── 006_document_version_snapshots (this file)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create document_version_snapshots table."""
    op.create_table(
        "document_version_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False, server_default=""),
        sa.Column("change_description", sa.String(500), nullable=False, server_default=""),
        sa.Column("diff_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("diff_json", sa.JSON(), nullable=True),
        sa.Column("storage_object_key", sa.String(500), nullable=False, server_default=""),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(64), nullable=False, server_default=""),
        sa.UniqueConstraint("document_id", "version", name="uq_document_version"),
    )
    op.create_index(
        "idx_doc_ver_snapshots_doc_id",
        "document_version_snapshots",
        ["document_id"],
    )


def downgrade() -> None:
    """Drop document_version_snapshots table and indexes."""
    op.drop_index("idx_doc_ver_snapshots_doc_id", table_name="document_version_snapshots")
    op.drop_table("document_version_snapshots")
