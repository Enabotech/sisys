"""Add tool_executions table for Tool execution aggregate persistence.

Revision ID: 011
Revises: 010
Create Date: 2026-09-07

Story 4.1a: 战略工具实现（ToolExecution 聚合根持久化）

CLAUDE.md §5 硬约束：已合入 migration 禁止修改，本期只允许新增。

设计决策：
- tool_id 使用 ID-only 弱引用（无 FOREIGN KEY 约束），等 Tool PostgreSQL
  持久化（Story 后续）后再补强 FK
- L2/L4 双轨存储边界：结构化字段 → L2_rdb / 大文本 → L4_object
  （evidence_storage_key 引用 L4 MinIO 对象键）

字段分类：
- 结构化字段（L2_rdb）：input_hash, rule_version, confidence
- 大文本字段（L4_object）：plan, code, result, observation, validation
- L4 引用（L2_rdb VARCHAR）：evidence_storage_key
"""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"


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
