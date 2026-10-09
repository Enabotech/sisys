"""Story 4.7: Validation Feedback 双表（错误案例库 + 演进日志）

Revision ID: 017
Revises: 016
Create Date: 2026-10-09

- error_cases：自然键 (tenant_id, tool_id, error_signature) UNIQUE——精确查表；
  分类计数拆分（recovered/infeasible）+ occurrence 守恒 CHECK；
  error_signature VARCHAR(64) 与签名提取器/实体不变量三处口径同一
- tool_evolution_logs：(tenant_id, execution_id) UNIQUE——execution_id 幂等 upsert；
  fix_attempts JSONB（含 attempt_execution_id 回链）；trigger_code/final_status
  CHECK 值域与枚举一一对应
- 不建 (tenant_id, tool_id, error_signature) 普通索引——与 UNIQUE 约束完全同列
  属冗余写放大（ix_error_cases_tool 支撑按工具查最近案例排序）

CLAUDE.md §5 硬约束：禁止修改已合入的 alembic migration，本期只允许新增。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "017"
down_revision = "016"


def upgrade() -> None:
    """创建 error_cases 与 tool_evolution_logs 双表。"""
    op.create_table(
        "error_cases",
        sa.Column("case_id", UUID(), primary_key=True),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column("tool_id", UUID(), nullable=False),
        sa.Column("error_signature", sa.String(64), nullable=False),
        sa.Column("error_category", sa.String(64), nullable=False),
        sa.Column("stderr_excerpt", sa.String(2000), nullable=False, server_default=""),
        sa.Column("fix_summary", sa.String(2000), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("recovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("infeasible_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "outcome IN ('RECOVERED', 'MARKED_INFEASIBLE')",
            name="ck_error_cases_outcome",
        ),
        sa.CheckConstraint("recovered_count >= 0", name="ck_error_cases_recovered_nonneg"),
        sa.CheckConstraint("infeasible_count >= 0", name="ck_error_cases_infeasible_nonneg"),
        sa.CheckConstraint(
            "occurrence_count = recovered_count + infeasible_count",
            name="ck_error_cases_occurrence_conservation",
        ),
        sa.CheckConstraint("occurrence_count >= 1", name="ck_error_cases_occurrence_min"),
        sa.UniqueConstraint(
            "tenant_id",
            "tool_id",
            "error_signature",
            name="uq_error_cases_natural_key",
        ),
    )
    op.create_index(
        "ix_error_cases_tool",
        "error_cases",
        ["tenant_id", "tool_id", sa.text("last_seen_at DESC")],
    )

    op.create_table(
        "tool_evolution_logs",
        sa.Column("log_id", UUID(), primary_key=True),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column("tool_id", UUID(), nullable=False),
        sa.Column("execution_id", UUID(), nullable=False),
        sa.Column("tool_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("trigger_code", sa.String(16), nullable=False),
        sa.Column("error_signature", sa.String(64), nullable=False),
        sa.Column("enhanced_retry_count", sa.Integer(), nullable=False),
        sa.Column("fix_attempts", JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("duration_sec", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("final_status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "trigger_code IN ('EXCEPTION_389', 'EXCEPTION_382')",
            name="ck_tool_evolution_logs_trigger_code",
        ),
        sa.CheckConstraint(
            "final_status IN ('RECOVERED', 'MARKED_INFEASIBLE')",
            name="ck_tool_evolution_logs_final_status",
        ),
        sa.CheckConstraint(
            "enhanced_retry_count BETWEEN 1 AND 3",
            name="ck_tool_evolution_logs_retry_count_range",
        ),
        sa.CheckConstraint("duration_sec >= 0", name="ck_tool_evolution_logs_duration_nonneg"),
        sa.UniqueConstraint(
            "tenant_id",
            "execution_id",
            name="uq_tool_evolution_logs_execution",
        ),
    )
    op.create_index(
        "ix_tool_evolution_logs_tool",
        "tool_evolution_logs",
        ["tenant_id", "tool_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """逆序删除双表（索引随表级联，显式删除保持与 upgrade 严格对称）。"""
    op.drop_index("ix_tool_evolution_logs_tool", table_name="tool_evolution_logs")
    op.drop_table("tool_evolution_logs")
    op.drop_index("ix_error_cases_tool", table_name="error_cases")
    op.drop_table("error_cases")
