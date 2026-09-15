"""Add sandbox_sessions table for Story 4.4 Docker sandbox execution persistence.

Revision ID: 014
Revises: 013
Create Date: 2026-09-11

Story 4.4: Docker 沙箱执行（AC-4 SandboxSession 聚合根持久化 + 配额统计 + 空闲清理)

CLAUDE.md §5 硬约束:已合入 migration 禁止修改,本期只允许新增。

设计决策:
- 主键 session_id VARCHAR(64)（字符串主键,业务标识符,匹配 ^[A-Za-z0-9_-]{1,64}$)
  - **注意**:不继承 L2RdbPort(UUID 主键约束),故独立定义 SandboxSessionRepositoryPort
- container_id VARCHAR(64) UNIQUE 约束 — 防止同一容器被多个 SandboxSession 引用
- state CHECK 约束 IN ('RUNNING', 'TERMINATED', 'FAILED')
- 4 索引（与 4.1a/4.3 复合索引模式一致,优化后）:
  1. tenant_id 单列索引 — 用于按租户过滤 session(虽然复合索引可前缀覆盖,
     但单列索引对小数据集性能更优;此处为简洁性保留)
  2. (tenant_id, state) — 复合索引,按租户 + 状态过滤
  3. (state, last_activity_at) — 空闲 TTL 清理(SandboxSessionReaper.reap_idle_sessions)
  4. container_id UNIQUE — 容器 ID 唯一性约束(放在 create_table 内)
- resource_limits JSONB — 来自 ContainerSpec.to_dict()
- L2/L4 双轨存储边界:结构化字段 → L2_rdb / 大文本 → L4_object
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "014"
down_revision = "013"


def upgrade() -> None:
    """创建 sandbox_sessions 表 + 4 索引"""
    op.create_table(
        "sandbox_sessions",
        sa.Column(
            "session_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column(
            "container_id",
            sa.String(64),
            nullable=True,
        ),
        sa.Column("image_digest", sa.String(255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "terminated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resource_limits",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default="RUNNING",
        ),
        sa.Column(
            "state_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.CheckConstraint(
            "state IN ('RUNNING', 'TERMINATED', 'FAILED')",
            name="ck_sandbox_sessions_state",
        ),
        sa.CheckConstraint("state_version >= 1", name="ck_sandbox_sessions_state_version"),
        sa.UniqueConstraint("container_id", name="uq_sandbox_sessions_container_id"),
    )

    # 4 索引（按 Story 4.4 AC-4 验收清单）
    # 1. tenant_id 单列索引 — 按租户过滤高频场景
    op.create_index(
        "ix_sandbox_sessions_tenant_id",
        "sandbox_sessions",
        ["tenant_id"],
    )
    # 2. (tenant_id, state) 复合索引 — 按租户 + 状态过滤(配额统计 count_active)
    op.create_index(
        "ix_sandbox_sessions_tenant_state",
        "sandbox_sessions",
        ["tenant_id", "state"],
    )
    # 3. (state, last_activity_at) — 空闲 TTL 清理核心索引
    op.create_index(
        "ix_sandbox_sessions_state_last_activity",
        "sandbox_sessions",
        ["state", "last_activity_at"],
    )
    # 4. container_id UNIQUE — 已在 create_table 内通过 UniqueConstraint 创建
    # (此处不需要额外 op.create_index,UNIQUE 约束已自动创建索引)


def downgrade() -> None:
    """回滚"""
    # 索引按创建顺序逆序删除
    op.drop_index(
        "ix_sandbox_sessions_state_last_activity",
        table_name="sandbox_sessions",
    )
    op.drop_index(
        "ix_sandbox_sessions_tenant_state",
        table_name="sandbox_sessions",
    )
    op.drop_index(
        "ix_sandbox_sessions_tenant_id",
        table_name="sandbox_sessions",
    )
    op.drop_table("sandbox_sessions")
