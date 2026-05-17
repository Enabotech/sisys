"""基础设施层权限模型模块

定义权限的 SQLAlchemy ORM 模型，对应 permissions 表

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class PermissionModel(Base):
    """权限 SQLAlchemy 模型，对应 permissions 表

    Attributes:
        id: 主键 UUID
        name: 权限名称（唯一）
        resource: 资源标识
        action: 操作类型
        created_at: 创建时间
    """

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    resource: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
