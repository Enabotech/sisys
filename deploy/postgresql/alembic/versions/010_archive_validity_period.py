"""new migration: add valid_from/valid_until columns to strategic_archives

Revision ID: 010
Revises: 009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"


def upgrade() -> None:
    """新增 valid_from/valid_until 列 + 索引"""
    op.add_column(
        "strategic_archives",
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "strategic_archives",
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
    )
    # 索引1：valid_until 单列索引，加速 validity_status="expired" 查询
    op.create_index(
        "ix_strategic_archives_valid_until",
        "strategic_archives",
        ["valid_until"],
    )
    # 索引2：valid_from 单列索引，加速 OR 查询中的 valid_from 条件过滤
    op.create_index(
        "ix_strategic_archives_valid_from",
        "strategic_archives",
        ["valid_from"],
    )
    # 索引3：部分索引，仅覆盖设置了有效期的记录子集
    op.create_index(
        "ix_strategic_archives_validity_active",
        "strategic_archives",
        ["valid_from", "valid_until"],
        postgresql_where=sa.text("valid_from IS NOT NULL OR valid_until IS NOT NULL"),
    )
    # 索引4：表达式索引，加速陈旧标记批量查询中的 metadata 过滤
    op.create_index(
        "ix_strategic_archives_staleness",
        "strategic_archives",
        [sa.text("(metadata->>'staleness')")],
        postgresql_where=sa.text("metadata->>'staleness' IS NOT NULL"),
    )


def downgrade() -> None:
    """回滚迁移"""
    op.drop_index("ix_strategic_archives_staleness", table_name="strategic_archives")
    op.drop_index("ix_strategic_archives_validity_active", table_name="strategic_archives")
    op.drop_index("ix_strategic_archives_valid_from", table_name="strategic_archives")
    op.drop_index("ix_strategic_archives_valid_until", table_name="strategic_archives")
    op.drop_column("strategic_archives", "valid_until")
    op.drop_column("strategic_archives", "valid_from")
