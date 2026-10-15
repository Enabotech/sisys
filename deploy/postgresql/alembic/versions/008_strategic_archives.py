"""Add strategic_archives table for Strategic Archive permanent storage.

Revision ID: 008
Revises: 007
Create Date: 2026-08-13

This migration creates:
- strategic_archives table: stores strategic archive metadata with six-layer storage references
- validity period columns (valid_from/valid_until) + 7 indexes

合并注记（2026-10-16 重构）：吸收原 009（查询索引）与原 010（有效期列+索引）两个补丁
migration——同一表的建表/索引/加列合并为完整版一次交付。

Migration chain:
001_initial (base)
└── 002_audit_tables
    └── 003_rbac_extensions
        └── 004_saga_tables
            └── 005_documents
                └── 006_document_version_snapshots
                    └── 007_dictionary_tables
                        └── 008_strategic_archives (this file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    pass

# revision identifiers
revision = "008"
down_revision = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade: create strategic_archives table."""
    op.create_table(
        "strategic_archives",
        sa.Column("archive_id", sa.Uuid(), primary_key=True, comment="档案 UUID 主键"),
        sa.Column("plan_id", sa.Uuid(), nullable=True, comment="关联的 SP/BP 规划标识"),
        sa.Column("plan_type", sa.String(10), nullable=False, server_default="", comment="规划类型（SP/BP）"),
        sa.Column(
            "archive_type", sa.String(50), nullable=False, comment="档案类型（assumption/decision/deviation/evidence_package）"
        ),
        sa.Column("assumptions", sa.dialects.postgresql.JSONB(), nullable=True, comment="关键假设变量"),
        sa.Column("decision_basis", sa.dialects.postgresql.JSONB(), nullable=True, comment="决策依据"),
        sa.Column("execution_deviation", sa.dialects.postgresql.JSONB(), nullable=True, comment="实际执行偏差"),
        sa.Column("metadata_ref", sa.String(500), nullable=False, server_default="", comment="L2 元数据引用"),
        sa.Column("embedding_ref", sa.String(500), nullable=True, comment="L3 向量引用"),
        sa.Column("blob_ref", sa.String(500), nullable=True, comment="L4 对象存储引用"),
        sa.Column("graph_ref", sa.String(500), nullable=True, comment="L5 图存储引用"),
        sa.Column("created_by", sa.Uuid(), nullable=True, comment="创建者用户 ID"),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1"), comment="版本号（乐观锁）"),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=True, comment="扩展元数据"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="软删除标记"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, comment="创建时间"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True, comment="归档时间"),
        # 有效期列（原 010 补丁并入——Story 3.11 事实有效期管理）
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True, comment="生效时间"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True, comment="失效时间"),
    )

    # 7 索引（原 009 补丁 3 个 + 原 010 补丁 4 个并入——一次交付完整索引集）
    op.create_index("ix_strategic_archives_plan_id", "strategic_archives", ["plan_id"])
    op.create_index("ix_strategic_archives_archive_type", "strategic_archives", ["archive_type"])
    op.create_index("ix_strategic_archives_archived_at", "strategic_archives", ["archived_at"])
    op.create_index("ix_strategic_archives_valid_until", "strategic_archives", ["valid_until"])
    op.create_index("ix_strategic_archives_valid_from", "strategic_archives", ["valid_from"])
    # 部分索引：仅覆盖设置了有效期的记录子集
    op.create_index(
        "ix_strategic_archives_validity_active",
        "strategic_archives",
        ["valid_from", "valid_until"],
        postgresql_where=sa.text("valid_from IS NOT NULL OR valid_until IS NOT NULL"),
    )
    # 表达式索引：加速陈旧标记批量查询中的 metadata 过滤
    op.create_index(
        "ix_strategic_archives_staleness",
        "strategic_archives",
        [sa.text("(metadata->>'staleness')")],
        postgresql_where=sa.text("metadata->>'staleness' IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade: drop strategic_archives table."""
    op.drop_table("strategic_archives")
