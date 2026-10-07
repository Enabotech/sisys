"""Story 4.6: tool_versions table（工具版本管理——灰度发布与回滚）

Revision ID: 016
Revises: 015
Create Date: 2026-10-07

- (tool_id, version) 复合唯一；平台级资源无 tenant_id（TOOL_CATALOG 语义一致）
- 2 个 partial unique index 硬守护单 STABLE / 单活跃 CANARY（并发不变量——
  逐语句即时校验，多行状态变更须"先降级/清场、后提升"）
- 2 查询索引（状态过滤 + 回滚候选 last_stable_at DESC）
- CHECK 值域与 ToolVersionStatus 小写枚举一一对应
- tool_id 无外键（011 先例：tools 表落地后补强，文件头注释说明）

CLAUDE.md §5 硬约束：禁止修改已合入的 alembic migration，本期只允许新增。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "016"
down_revision = "015"


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
