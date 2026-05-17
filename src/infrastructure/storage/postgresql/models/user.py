"""基础设施层用户模型模块

定义用户的 SQLAlchemy ORM 模型，对应 users 表

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class UserModel(Base):
    """用户 SQLAlchemy 模型，对应 users 表

    Attributes:
        id: 主键 UUID
        username: 用户名（唯一）
        email: 邮箱（唯一）
        hashed_password: 哈希密码
        is_active: 是否激活
        is_locked: 是否锁定
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __init__(
        self,
        username: str,
        email: str,
        id: UUID | None = None,
        hashed_password: str | None = None,
        is_active: bool = True,
        is_locked: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """初始化用户模型

        Args:
            username: 用户名
            email: 邮箱
            id: 主键 UUID，为 None 时自动生成
            hashed_password: 哈希密码，可选
            is_active: 是否激活，默认 True
            is_locked: 是否锁定，默认 False
            created_at: 创建时间，可选
            updated_at: 更新时间，可选
        """
        self.id = id or uuid4()
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.is_active = is_active
        self.is_locked = is_locked
        self.created_at = created_at
        self.updated_at = updated_at
