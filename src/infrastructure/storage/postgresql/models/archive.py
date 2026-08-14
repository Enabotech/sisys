"""基础设施层战略档案 SQLAlchemy 模型模块

定义战略档案表 ORM 模型，存储档案元数据及六层存储引用。
对应 strategic_archives 表，支持软删除。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class ArchiveModel(Base):
    """战略档案 SQLAlchemy 模型，对应 strategic_archives 表

    Attributes:
        archive_id: 档案 UUID 主键
        plan_id: 关联的 SP/BP 规划标识
        plan_type: 规划类型（"SP"/"BP"）
        archive_type: 档案类型（assumption/decision/deviation/evidence_package）
        assumptions: 关键假设变量（JSONB）
        decision_basis: 决策依据（JSONB）
        execution_deviation: 实际执行偏差（JSONB）
        metadata_ref: L2 元数据引用
        embedding_ref: L3 向量引用（可为空）
        blob_ref: L4 对象存储引用（可为空）
        graph_ref: L5 图存储引用（可为空）
        created_by: 创建者用户 ID
        version: 版本号（乐观锁）
        metadata: 扩展元数据（JSONB，预留 Story 3.11/3.12 扩展点）
        deleted_at: 软删除标记
        created_at: 创建时间
        archived_at: 归档时间
    """

    __tablename__ = "strategic_archives"

    archive_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    plan_id: Mapped[UUID | None] = mapped_column(SA_UUID, nullable=True)
    plan_type: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    archive_type: Mapped[str] = mapped_column(String(50), nullable=False)
    assumptions: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    decision_basis: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    execution_deviation: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    metadata_ref: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    embedding_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    blob_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    graph_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(SA_UUID, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "ArchiveModel",
]
