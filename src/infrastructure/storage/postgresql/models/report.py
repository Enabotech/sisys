"""报告元数据 ORM 模型（Story 6-5a——strategic_reports 表）。

ArchiveModel 同款形态（Mapped/mapped_column/SA_UUID/JSONB/Base 继承
outbox.py）；列结构与 alembic 017 migration 镜像。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base

__all__ = ["ReportModel"]


class ReportModel(Base):
    """战略报告元数据行（L2——报告持久化真相源之一）。

    幂等锚 = report_id 主键（同 plan_id 重复生成产生新行——OD-10）。
    """

    __tablename__ = "strategic_reports"

    report_id: Mapped[uuid.UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(SA_UUID, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    degraded_section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
