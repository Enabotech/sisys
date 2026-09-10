"""Add schema_validation_records table for Story 4.3 Schema validation history persistence.

Revision ID: 013
Revises: 012
Create Date: 2026-09-10

Story 4.3: 工具输入/输出 Schema 验证（AC-5 SchemaValidationRecord 聚合根持久化）

CLAUDE.md §5 硬约束：已合入 migration 禁止修改，本期只允许新增。

设计决策：
- violations 字段使用 JSONB 存储 SchemaViolation 列表（含 datetime/UUID 等已脱敏）
- 4 索引（优化后）：
  1. (tenant_id, execution_id) — 4.7 Validation Feedback 按 execution_id 查 violations 高频
  2. (tenant_id, tool_id, validated_at DESC) — 替换原 (tenant_id, tool_id)，增加时间序列优化
  3. (tenant_id, validation_phase, is_valid) — 替换原 (tenant_id, validation_phase)，增加 is_valid 过滤
  4. (tenant_id, is_valid, validated_at DESC) — 替换原 (tenant_id, is_valid, validated_at)，按时间倒序
- 移除冗余：tenant_id 单列索引在 (tenant_id, *) 复合索引已覆盖
  （PostgreSQL 复合索引可前缀使用）
- CHECK 约束：validation_phase IN ('INPUT', 'OUTPUT', 'COMPATIBILITY')
- L2/L4 双轨存储边界：结构化字段 → L2_rdb / 大文本 → L4_object
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013"
down_revision = "012"


def upgrade() -> None:
    """创建 schema_validation_records 表 + 4 索引"""
    op.create_table(
        "schema_validation_records",
        sa.Column("record_id", UUID(), primary_key=True),
        sa.Column("execution_id", UUID(), nullable=False),
        sa.Column("tool_id", UUID(), nullable=False),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column(
            "validation_phase",
            sa.String(20),
            nullable=False,
        ),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("violations", JSONB(), nullable=False, server_default="[]"),
        sa.Column("retry_attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "schema_version",
            sa.String(20),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "validation_phase IN ('INPUT', 'OUTPUT', 'COMPATIBILITY')",
            name="ck_schema_validation_records_phase",
        ),
        sa.CheckConstraint("retry_attempt >= 1", name="ck_schema_validation_records_retry_attempt"),
    )
    # 4 索引（按 Story 4.3 AC-5 验收清单）
    op.create_index(
        "ix_schema_validation_records_tenant_execution",
        "schema_validation_records",
        ["tenant_id", "execution_id"],
    )
    op.create_index(
        "ix_schema_validation_records_tenant_tool_time",
        "schema_validation_records",
        ["tenant_id", "tool_id", sa.text("validated_at DESC")],
    )
    op.create_index(
        "ix_schema_validation_records_tenant_phase_valid",
        "schema_validation_records",
        ["tenant_id", "validation_phase", "is_valid"],
    )
    op.create_index(
        "ix_schema_validation_records_tenant_valid_time",
        "schema_validation_records",
        ["tenant_id", "is_valid", sa.text("validated_at DESC")],
    )


def downgrade() -> None:
    """回滚"""
    op.drop_index(
        "ix_schema_validation_records_tenant_valid_time",
        table_name="schema_validation_records",
    )
    op.drop_index(
        "ix_schema_validation_records_tenant_phase_valid",
        table_name="schema_validation_records",
    )
    op.drop_index(
        "ix_schema_validation_records_tenant_tool_time",
        table_name="schema_validation_records",
    )
    op.drop_index(
        "ix_schema_validation_records_tenant_execution",
        table_name="schema_validation_records",
    )
    op.drop_table("schema_validation_records")
