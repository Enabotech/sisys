"""品牌模板 ORM 模型（Story 6-11——brand_templates 表）。

ReportModel 同款形态（Mapped/mapped_column/SA_UUID/Base 继承 outbox.py）；
列结构与 alembic 018 migration 镜像（含 UNIQUE(name) 业务键约束）。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base

__all__ = ["BrandTemplateModel"]


class BrandTemplateModel(Base):
    """品牌模板配置行（L2——白标配置持久化真相源）。

    幂等锚 = template_id 主键；name UNIQUE 是业务键（并发双 INSERT 的
    IntegrityError 防御锚——仓储捕获包装 495）。server_default now() 仅
    INSERT 初值，UPDATE 分支 updated_at 由服务侧显式定值（OD-12）。
    """

    __tablename__ = "brand_templates"
    __table_args__ = (UniqueConstraint("name", name="uq_brand_templates_name"),)

    template_id: Mapped[uuid.UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_scheme: Mapped[str] = mapped_column(String(30), nullable=False)
    font_preset: Mapped[str] = mapped_column(String(30), nullable=False)
    logo_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
