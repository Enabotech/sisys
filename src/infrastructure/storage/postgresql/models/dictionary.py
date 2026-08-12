"""基础设施层词典管理 SQLAlchemy 模型模块

定义词典词条表和快照表的 ORM 模型。
词条表使用 term 作为业务主键，支持乐观锁版本控制。
快照表使用 UUID 主键，存储完整词条 JSON 快照。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class DictionaryEntryModel(Base):
    """词典词条 SQLAlchemy 模型，对应 dictionary_entries 表

    Attributes:
        term: 词条文本（业务主键）
        entity_type: 实体类型
        category: 词条类别
        active: 是否启用
        version: 词条版本（乐观锁）
        created_by: 创建者
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "dictionary_entries"

    term: Mapped[str] = mapped_column(String(200), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(
        self,
        term: str = "",
        entity_type: str = "",
        category: str = "general",
        active: bool = True,
        version: int = 1,
        created_by: str = "",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """初始化词典词条模型"""
        self.term = term
        self.entity_type = entity_type
        self.category = category
        self.active = active
        self.version = version
        self.created_by = created_by
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at


class DictionarySnapshotModel(Base):
    """词典快照 SQLAlchemy 模型，对应 dictionary_snapshots 表

    Attributes:
        snapshot_id: 快照 UUID 主键
        version: 词典版本号（唯一）
        entries: 完整词条快照（JSONB）
        created_by: 创建者
        created_at: 创建时间
        change_summary: 变更摘要（JSONB）
    """

    __tablename__ = "dictionary_snapshots"

    snapshot_id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    entries: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    def __init__(
        self,
        snapshot_id: UUID | None = None,
        version: int = 0,
        entries: dict | None = None,
        created_by: str = "",
        created_at: datetime | None = None,
        change_summary: dict | None = None,
    ) -> None:
        """初始化词典快照模型"""
        self.snapshot_id = snapshot_id or uuid4()
        self.version = version
        self.entries = entries or {}
        self.created_by = created_by
        self.created_at = created_at or datetime.now(timezone.utc)
        self.change_summary = change_summary or {}
