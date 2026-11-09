"""brand_templates 品牌模板配置表（Story 6-11——白标报告基础 L2 持久化）。

只增 migration（已合入 migration 禁改红线）；与 BrandTemplateModel ORM 镜像。

server_default now() 仅 INSERT 初值——UPDATE 分支 updated_at 由服务侧构造
实体显式定值（OD-12 应用侧定时戳：report_repository :126-139 先例——两机制
不混用，DDL 不承载修订前进语义）。

Revision ID: 018
Revises: 017
Create Date: 2026-11-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """建 brand_templates 表（template_id 主键 + name 业务键 UNIQUE + 双时间戳）。

    UNIQUE(name) 是 UPSERT 修订语义的并发防御锚（007 snapshots version unique
    先例援引——017 无 UNIQUE 约束仅 PK，本表业务键语义需要）；name UNIQUE 下
    并发双 INSERT 的 IntegrityError 由仓储捕获包装 495（防御义务归仓储——
    CLI 单进程常态低概率）。
    """
    op.create_table(
        "brand_templates",
        sa.Column("template_id", UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color_scheme", sa.String(length=30), nullable=False),
        sa.Column("font_preset", sa.String(length=30), nullable=False),
        sa.Column("logo_object_key", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("template_id"),
        sa.UniqueConstraint("name", name="uq_brand_templates_name"),
    )


def downgrade() -> None:
    """回滚：删表（对称回滚——downgrade 链验证）。"""
    op.drop_table("brand_templates")
