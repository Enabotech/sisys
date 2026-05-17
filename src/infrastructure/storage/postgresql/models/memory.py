"""基础设施层记忆模型模块

定义记忆相关的 SQLAlchemy ORM 模型，对应 memory_metadata、memory_change_history
和 memory_group_members 表。DDL 来源: architecture.md 11.2.5

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .outbox import Base


class MemoryMetadataModel(Base):
    """记忆元数据 SQLAlchemy 模型，对应 memory_metadata 表

    追踪 L0 文件系统记忆的状态快照

    Attributes:
        memory_id: 记忆唯一标识（主键）
        user_id: 所属用户 ID
        name: 记忆名称（唯一）
        description: 记忆描述
        type: 记忆类型
        path: 记忆路径
        version: 版本号
        mtime: 修改时间
        owner: 所有者
        group_id: 群组 ID
        created_at: 创建时间
        updated_at: 更新时间
        deleted_at: 软删除标记时间
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
    """记忆变更历史 SQLAlchemy 模型，对应 memory_change_history 表

    追溯记忆的变更过程（append-only），不存储当前状态

    Attributes:
        id: 主键 UUID
        memory_id: 关联记忆 ID
        version: 版本号
        changed_at: 变更时间
        changed_by: 变更执行者
        change_type: 变更类型
        changed_fields: 变更的字段（JSON）
        diff_summary: 变更摘要
        archived_ref: 归档引用
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


class MemoryGroupMemberModel(Base):
    """群组成员关系 SQLAlchemy 模型，对应 memory_group_members 表

    验证 group 记忆的访问权限，存储 group_id 和 user_id 的多对多关系，带角色（member/admin）

    Attributes:
        group_id: 群组 ID（联合主键）
        user_id: 用户 ID（联合主键）
        role: 角色（member/admin）
    """

    __tablename__ = "memory_group_members"

    group_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")

    __table_args__ = (Index("ix_memory_group_members_group_user", "group_id", "user_id", unique=True),)
