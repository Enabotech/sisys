"""RBAC Extensions - All role-based access control schema extensions.

Revision ID: 003
Revises: 002
Create Date: 2026-05-05

This migration consolidates all RBAC-related schema changes:
- Add is_active to roles (from 96b449496c15)
- Add is_locked to users (from add_is_locked_to_users)
- Add is_system_reserved to roles (from add_is_system_reserved_to_roles)
- Add login_attempts table (new)
- Add updated_at to roles (from 96b449496c15)
- Allow nullable fields for OAuth users

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions (this file)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema with RBAC extensions."""
    # =======================================================================
    # Add fields to roles table
    # =======================================================================
    op.add_column("roles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("roles", sa.Column("is_system_reserved", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("roles", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # =======================================================================
    # Add fields to users table
    # =======================================================================
    op.add_column("users", sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="false"))

    # Allow hashed_password to be nullable for OAuth users
    op.alter_column("users", "hashed_password", existing_type=sa.VARCHAR(length=255), nullable=True)

    # Allow created_at/updated_at to be nullable
    op.alter_column(
        "users", "created_at", existing_type=postgresql.TIMESTAMP(), nullable=True, existing_server_default=sa.text("now()")
    )
    op.alter_column(
        "users", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=True, existing_server_default=sa.text("now()")
    )

    # =======================================================================
    # Allow permissions fields to be nullable (for OAuth/scoped permissions)
    # =======================================================================
    op.alter_column("permissions", "resource", existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column("permissions", "action", existing_type=sa.VARCHAR(length=50), nullable=True)
    op.alter_column(
        "permissions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )

    # =======================================================================
    # Create login_attempts table (for Deng Bao 2.0 compliance)
    # =======================================================================
    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),  # IPv6 max length
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("failure_reason", sa.String(100), nullable=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Indexes for login attempt queries
    op.create_index("ix_login_attempts_username_attempted_at", "login_attempts", ["username", "attempted_at"])
    op.create_index("ix_login_attempts_user_id_attempted_at", "login_attempts", ["user_id", "attempted_at"])

    # Unique constraint to prevent duplicate rapid attempts
    op.create_unique_constraint("uq_login_attempt_user_time", "login_attempts", ["user_id", "attempted_at"])


def downgrade() -> None:
    """Downgrade schema - remove RBAC extensions."""
    # Drop login_attempts table
    op.drop_constraint("uq_login_attempt_user_time", "login_attempts", type_="unique")
    op.drop_index("ix_login_attempts_user_id_attempted_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_username_attempted_at", table_name="login_attempts")
    op.drop_table("login_attempts")

    # Restore permissions fields
    op.alter_column(
        "permissions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column("permissions", "action", existing_type=sa.VARCHAR(length=50), nullable=False)
    op.alter_column("permissions", "resource", existing_type=sa.VARCHAR(length=50), nullable=False)

    # Restore users fields
    op.alter_column(
        "users", "updated_at", existing_type=postgresql.TIMESTAMP(), nullable=False, existing_server_default=sa.text("now()")
    )
    op.alter_column(
        "users", "created_at", existing_type=postgresql.TIMESTAMP(), nullable=False, existing_server_default=sa.text("now()")
    )
    op.alter_column("users", "hashed_password", existing_type=sa.VARCHAR(length=255), nullable=False)

    # Drop users is_locked column
    op.drop_column("users", "is_locked")

    # Drop roles fields
    op.drop_column("roles", "updated_at")
    op.drop_column("roles", "is_system_reserved")
    op.drop_column("roles", "is_active")
