"""Add tool_chains table for ToolChainDag aggregate persistence.

Revision ID: 012
Revises: 011
Create Date: 2026-09-10

Story 4.2: 工具链编排（DAG 工具链持久化）

CLAUDE.md §5 硬约束：已合入 migration 禁止修改，本期只允许新增。

设计决策：
- nodes 字段使用 JSONB 存储 DAG 节点数组（含 node_id / tool_slug / depends_on / arguments_template 等）
- 4 索引：tenant_id / (tenant_id, name) / (tenant_id, failure_strategy) / GIN(nodes JSONB)
- L2/L4 双轨存储边界：结构化字段 → L2_rdb / 大文本 → L4_object
  （本期无 L4 依赖，DAG 元数据全在 L2_rdb）
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "012"
down_revision = "011"


def upgrade() -> None:
    """创建 tool_chains 表 + 4 索引"""
    op.create_table(
        "tool_chains",
        sa.Column("chain_id", UUID(), primary_key=True),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        # DAG 节点数组（含 node_id / tool_slug / depends_on / arguments_template / failure_strategy 等）
        sa.Column("nodes", JSONB(), nullable=False),
        sa.Column(
            "failure_strategy",
            sa.String(30),
            nullable=False,
            server_default="SKIP_DOWNSTREAM",
        ),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="5"),
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
            "failure_strategy IN ('FAIL_FAST', 'CONTINUE_ON_ERROR', 'SKIP_DOWNSTREAM')",
            name="ck_tool_chains_failure_strategy",
        ),
        sa.CheckConstraint("max_concurrency >= 1", name="ck_tool_chains_max_concurrency"),
    )
    # 4 索引
    op.create_index("ix_tool_chains_tenant_id", "tool_chains", ["tenant_id"])
    op.create_index(
        "ix_tool_chains_tenant_name",
        "tool_chains",
        ["tenant_id", "name"],
    )
    op.create_index(
        "ix_tool_chains_tenant_failure_strategy",
        "tool_chains",
        ["tenant_id", "failure_strategy"],
    )
    # GIN 索引：nodes JSONB 字段（支持按 node_id / tool_slug 查询）
    op.execute("CREATE INDEX ix_tool_chains_nodes_gin ON tool_chains USING gin (nodes jsonb_path_ops)")


def downgrade() -> None:
    """回滚"""
    op.execute("DROP INDEX IF EXISTS ix_tool_chains_nodes_gin")
    op.drop_index("ix_tool_chains_tenant_failure_strategy", table_name="tool_chains")
    op.drop_index("ix_tool_chains_tenant_name", table_name="tool_chains")
    op.drop_index("ix_tool_chains_tenant_id", table_name="tool_chains")
    op.drop_table("tool_chains")
