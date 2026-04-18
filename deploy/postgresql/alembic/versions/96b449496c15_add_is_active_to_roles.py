"""Add is_active and updated_at to roles table.

Revision ID: 96b449496c15
Revises: 001
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "96b449496c15"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("roles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("roles", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Allow hashed_password to be nullable for OAuth users
    op.alter_column("users", "hashed_password", existing_type=sa.VARCHAR(length=255), nullable=True)

    # Allow created_at/updated_at to be nullable
    op.alter_column(
        "users", "created_at", existing_type=postgresql.TIMESTAMP(), nullable=True, existing_server_default=sa.text("now()")
    )
    op.alter_column(
        "users", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=True, existing_server_default=sa.text("now()")
    )

    # Allow permissions.resource and action to be nullable
    op.alter_column("permissions", "resource", existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column("permissions", "action", existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column(
        "permissions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "permissions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column("permissions", "action", existing_type=sa.VARCHAR(length=50), nullable=False)
    op.alter_column("permissions", "resource", existing_type=sa.VARCHAR(length=50), nullable=False)

    op.alter_column(
        "users", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=False, existing_server_default=sa.text("now()")
    )
    op.alter_column(
        "users", "created_at", existing_type=postgresql.TIMESTAMP(), nullable=False, existing_server_default=sa.text("now()")
    )
    op.alter_column("users", "hashed_password", existing_type=sa.VARCHAR(length=255), nullable=False)

    op.drop_column("roles", "updated_at")
    op.drop_column("roles", "is_active")
