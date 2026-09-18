"""Story 4.4: Sandbox sessions table

Revision ID: 015
Revises: 014
Create Date: 2026-09-16

记录沙箱会话（便于审计 + 配额统计）。
- VARCHAR(64) 主键 session_id（业务标识符,匹配 ^[A-Za-z0-9_-]{1,64}$）
- tenant_id UUID 多租户隔离
- container_id Docker container ID（启动后填充）
- image_digest 实际启动的镜像 digest
- started_at / last_activity_at / terminated_at 时间戳
- resource_limits JSONB 容器资源限制字典
- state VARCHAR(16) 状态（RUNNING / TERMINATED / FAILED）
- state_version INT 乐观锁版本号

索引（3 个）:
- (tenant_id, state) 复合索引：按租户 + 状态过滤
- (state, last_activity_at) 复合索引：空闲 TTL 扫描
- container_id UNIQUE 索引：防止容器 ID 冲突

CLAUDE.md §5 硬约束：禁止修改已合入的 alembic migration。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 sandbox_sessions 表 + 3 索引."""
    op.create_table(
        "sandbox_sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("image_digest", sa.String(length=512), nullable=False, server_default=""),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resource_limits", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="RUNNING"),
        sa.Column("state_version", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint(
            "state IN ('RUNNING', 'TERMINATED', 'FAILED')",
            name="ck_sandbox_sessions_state",
        ),
    )

    # 索引 1: (tenant_id, state) 复合索引（按租户 + 状态过滤）
    op.create_index(
        "ix_sandbox_sessions_tenant_state",
        "sandbox_sessions",
        ["tenant_id", "state"],
    )

    # 索引 2: (state, last_activity_at) 复合索引（空闲 TTL 扫描）
    op.create_index(
        "ix_sandbox_sessions_state_last_activity",
        "sandbox_sessions",
        ["state", "last_activity_at"],
    )

    # 索引 3: container_id UNIQUE 索引（防止容器 ID 冲突）
    op.create_index(
        "ix_sandbox_sessions_container_id_unique",
        "sandbox_sessions",
        ["container_id"],
        unique=True,
        postgresql_where=sa.text("container_id IS NOT NULL"),
    )


def downgrade() -> None:
    """回滚 sandbox_sessions 表 + 3 索引."""
    op.drop_index("ix_sandbox_sessions_container_id_unique", table_name="sandbox_sessions")
    op.drop_index("ix_sandbox_sessions_state_last_activity", table_name="sandbox_sessions")
    op.drop_index("ix_sandbox_sessions_tenant_state", table_name="sandbox_sessions")
    op.drop_table("sandbox_sessions")
