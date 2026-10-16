"""Story 4.6: tool_versions table（工具版本管理——灰度发布与回滚）

Revision ID: 013
Revises: 012
Create Date: 2026-10-07

This migration creates:
- tool_versions table: 版本灰度（traffic_weight/required_rollout_mode）+ last_stable_at 回滚锚点
- CHECK（traffic_weight 0-100）+ (tenant_id, tool_id, version) UNIQUE

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
                                        └── 011_schema_validation_records
                                            └── 012_sandbox_sessions
                                                └── 013_tool_versions (this file)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013"
down_revision = "012"


def upgrade() -> None:
    """创建 tool_versions 表 + 复合唯一 + 2 partial unique index + 2 查询索引。"""
    op.create_table(
        "tool_versions",
        sa.Column("version_id", UUID(), primary_key=True),
        sa.Column("tool_id", UUID(), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("input_schema", JSONB(), nullable=False, server_default="{}"),
        sa.Column("output_schema", JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("traffic_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "required_rollout_mode",
            sa.String(16),
            nullable=False,
            server_default="any",
        ),
        sa.Column("last_stable_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'canary', 'stable', 'deprecated')",
            name="ck_tool_versions_status",
        ),
        sa.CheckConstraint(
            "traffic_weight BETWEEN 0 AND 100",
            name="ck_tool_versions_traffic_weight",
        ),
        sa.CheckConstraint(
            "required_rollout_mode IN ('any', 'canary_only')",
            name="ck_tool_versions_rollout_mode",
        ),
        sa.UniqueConstraint("tool_id", "version", name="uq_tool_versions_tool_version"),
    )
    # 并发不变量硬守护（partial unique index ×2）
    op.create_index(
        "uq_tool_versions_single_stable",
        "tool_versions",
        ["tool_id"],
        unique=True,
        postgresql_where=sa.text("status = 'stable'"),
    )
    op.create_index(
        "uq_tool_versions_single_canary",
        "tool_versions",
        ["tool_id"],
        unique=True,
        postgresql_where=sa.text("status = 'canary'"),
    )
    # 查询索引
    op.create_index(
        "ix_tool_versions_tool_status",
        "tool_versions",
        ["tool_id", "status"],
    )
    op.create_index(
        "ix_tool_versions_tool_last_stable",
        "tool_versions",
        ["tool_id", sa.text("last_stable_at DESC")],
    )


def downgrade() -> None:
    """回滚：删除 tool_versions 表与索引。"""
    op.drop_index(
        "ix_tool_versions_tool_last_stable",
        table_name="tool_versions",
    )
    op.drop_index(
        "ix_tool_versions_tool_status",
        table_name="tool_versions",
    )
    op.drop_index(
        "uq_tool_versions_single_canary",
        table_name="tool_versions",
    )
    op.drop_index(
        "uq_tool_versions_single_stable",
        table_name="tool_versions",
    )
    op.drop_table("tool_versions")
