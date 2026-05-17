"""基础设施层用户仓储模块

继承 PostgreSQLAdapter[User, UserModel]，实现实体与模型转换
通过 _to_entity/_to_model 隔离领域层与 ORM 层

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from sqlalchemy import select

from src.domain.entities.user import User
from src.infrastructure.storage.postgresql.models import UserModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter


class UserRepository(PostgreSQLAdapter[User, UserModel]):
    """用户仓储实现

    继承 PostgreSQLAdapter[User, UserModel]，
    通过 _to_entity/_to_model 隔离领域层与 ORM 层
    """

    def __init__(self) -> None:
        super().__init__(UserModel)

    def _to_entity(self, model: UserModel) -> User:
        """将 ORM 模型转换为领域实体

        Args:
            model: UserModel SQLAlchemy 模型实例

        Returns:
            User 领域实体
        """
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            password_hash=model.hashed_password or "",
            is_active=model.is_active,
            is_locked=model.is_locked,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        """将领域实体转换为 ORM 模型

        Args:
            entity: User 领域实体

        Returns:
            UserModel SQLAlchemy 模型实例
        """
        return UserModel(
            id=entity.id,
            username=entity.username,
            email=entity.email,
            hashed_password=entity.password_hash,
            is_active=entity.is_active,
            is_locked=entity.is_locked,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            User 领域实体，如果不存在则返回 None
        """
        result = await self._session.execute(select(UserModel).where(UserModel.username == username))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        """根据邮箱获取用户

        Args:
            email: 邮箱地址

        Returns:
            User 领域实体，如果不存在则返回 None
        """
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
