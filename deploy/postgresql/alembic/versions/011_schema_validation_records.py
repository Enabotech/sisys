"""Add schema_validation_records table for Schema validation history persistence.

Revision ID: 011
Revises: 010
Create Date: 2026-09-10

Story 4.3: 工具输入/输出 Schema 验证（AC-5 SchemaValidationRecord 聚合根持久化）

This migration creates:
- schema_validation_records table: validation history with violations JSONB
- 5 indexes（含 violations GIN jsonb_path_ops——原 014 补丁并入）

合并注记（2026-10-16 重构）：吸收原 014（violations GIN 索引）。

Migration chain:
001_initial (base)
    └── 002_audit_tables
        └── 003_rbac_extensions
            └── 004_saga_tables
                └── 005_documents
                    └── 006_document_version_snapshots
                        └── 007_dictionary_tables
                            └── 008_strategic_archives
                                └── 009_tool_executions
                                    └── 010_tool_chains
                                        └── 011_schema_validation_records (this file)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "011"
down_revision = "010"


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
    # GIN 索引（原 014 补丁并入——jsonb_path_ops 支持 @@ jsonpath match 加速
    # violations JSONB 查询；不支持 ?/?? 存在性操作符，本 Story 不需要）
    op.create_index(
        "ix_schema_validation_records_violations_gin",
        "schema_validation_records",
        ["violations"],
        postgresql_using="gin",
        postgresql_ops={"violations": "jsonb_path_ops"},
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
