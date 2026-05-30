"""基础设施层角色模型模块

定义角色的 SQLAlchemy ORM 模型，对应 roles 表
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


def _utc_now() -> datetime:
    """返回当前 UTC 时间（无时区，用于数据库兼容）"""
    return datetime.now(UTC).replace(tzinfo=None)


class RoleModel(Base):
    """角色 SQLAlchemy 模型，对应 roles 表

    Attributes:
        id: 主键 UUID
        name: 角色名称（唯一）
        description: 角色描述
        is_active: 是否激活
        is_system_reserved: 是否系统保留角色
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_system_reserved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
