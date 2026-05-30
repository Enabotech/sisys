"""Add documents table for document metadata persistence.

Revision ID: 005
Revises: 004
Create Date: 2026-05-30

This migration creates the documents table with Row-Level Isolation
via tenant_id column and supporting indexes.

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_saga_tables
            └── 005_documents (this file)
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
    """Create documents table with tenant isolation indexes."""
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column(
            "parse_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("uploaded_by", sa.String(100), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("idx_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index(
        "idx_documents_tenant_created_at",
        "documents",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    """Drop documents table and indexes."""
    op.drop_index("idx_documents_tenant_created_at", table_name="documents")
    op.drop_index("idx_documents_tenant_id", table_name="documents")
    op.drop_table("documents")
