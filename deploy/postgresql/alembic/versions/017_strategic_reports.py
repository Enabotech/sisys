"""strategic_reports 报告元数据表（Story 6-5a——L2 报告持久化）。

只增 migration（已合入 migration 禁改红线）；与 ReportModel ORM 镜像。

Revision ID: 017
Revises: 016
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """建 strategic_reports 表（report_id 主键 + plan_id 索引 + metadata JSONB）。"""
    op.create_table(
        "strategic_reports",
        sa.Column("report_id", UUID(), nullable=False),
        sa.Column("plan_id", UUID(), nullable=False),
        sa.Column("report_type", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("section_count", sa.Integer(), nullable=False),
        sa.Column("degraded_section_count", sa.Integer(), nullable=False),
        sa.Column("generation_ms", sa.Integer(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index("ix_strategic_reports_plan_id", "strategic_reports", ["plan_id"])


def downgrade() -> None:
    """回滚：删索引与表（对称回滚——downgrade 链验证）。"""
    op.drop_index("ix_strategic_reports_plan_id", table_name="strategic_reports")
    op.drop_table("strategic_reports")
