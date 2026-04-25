"""Memory PostgreSQL Models.

DDL 来源: architecture.md §11.2.5
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .outbox import Base


class MemoryMetadataModel(Base):
    """记忆元数据模型。

    对应表: memory_metadata
    用途: 追踪 L0 文件系统记忆的状态快照
    """

    __tablename__ = "memory_metadata"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mtime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )  # 软删除标记


class MemoryChangeHistoryModel(Base):
    """记忆变更历史模型（append-only）。

    对应表: memory_change_history
    用途: 追溯记忆的变更过程，不存储当前状态
    """

    __tablename__ = "memory_change_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_metadata.memory_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 关系
    memory: Mapped[MemoryMetadataModel] = relationship(
        "MemoryMetadataModel",
        backref="histories",
        foreign_keys=[memory_id],
    )
