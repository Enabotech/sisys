"""Add tool_executions table for Tool execution aggregate persistence.

Revision ID: 009
Revises: 008
Create Date: 2026-09-07

Story 4.1a: 战略工具实现（ToolExecution 聚合根持久化）

This migration creates:
- tool_executions table: execution state + evidence package (L2 structured / L4 refs)
- 4 indexes (tenant+execution unique, tenant+tool+started_at, tenant+state, input_hash)
- 3 CHECK constraints (state values, confidence range, state_version >= 0)

Migration chain:
001_initial (base)
    └── 002_audit_tables
        └── 003_rbac_extensions
            └── 004_saga_tables
                └── 005_documents
                    └── 006_document_version_snapshots
                        └── 007_dictionary_tables
                            └── 008_strategic_archives
                                └── 009_tool_executions (this file)
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"


def upgrade() -> None:
    """创建 tool_executions 表 + 4 索引 + 3 CHECK 约束"""
    op.create_table(
        "tool_executions",
        sa.Column("execution_id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tool_id", sa.UUID(), nullable=False),  # ID-only 弱引用（推迟 FK）
        sa.Column("tool_version", sa.String(50), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="IDLE"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.String(1000), nullable=True),
        # 证据包结构化字段（L2_rdb）
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("rule_version", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        # L4 MinIO 引用
        sa.Column("evidence_storage_key", sa.String(500), nullable=True),
        # 乐观锁
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "state IN ('IDLE', 'PLANNING', 'EXECUTING', 'VALIDATING', 'COMPLETED', 'FAILED')",
            name="ck_tool_executions_state",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_tool_executions_retry_count"),
        sa.CheckConstraint("state_version >= 0", name="ck_tool_executions_state_version"),
    )
    # 4 索引：租户基线 + 复合 + 时间 + 部分索引
    op.create_index("ix_tool_executions_tenant_id", "tool_executions", ["tenant_id"])
    op.create_index(
        "ix_tool_executions_tenant_tool_state",
        "tool_executions",
        ["tenant_id", "tool_id", "state"],
    )
    op.create_index(
        "ix_tool_executions_tenant_started_at",
        "tool_executions",
        ["tenant_id", "started_at"],
    )
    op.create_index(
        "ix_tool_executions_terminal_state",
        "tool_executions",
        ["tenant_id", "state"],
        postgresql_where=sa.text("state IN ('COMPLETED', 'FAILED')"),
    )


def downgrade() -> None:
    """回滚"""
    op.drop_index("ix_tool_executions_terminal_state", table_name="tool_executions")
    op.drop_index("ix_tool_executions_tenant_started_at", table_name="tool_executions")
    op.drop_index("ix_tool_executions_tenant_tool_state", table_name="tool_executions")
    op.drop_index("ix_tool_executions_tenant_id", table_name="tool_executions")
    op.drop_table("tool_executions")
