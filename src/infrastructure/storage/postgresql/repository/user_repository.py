"""UserRepository — 用户仓储实现

继承 PostgreSQLAdapter[User, UserModel]，实现实体↔模型转换
UserRepositoryPort 声明返回 User 领域实体，本仓储通过 TEntity 泛型匹配
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
        """ORM model -> domain entity."""
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
        """Domain entity -> ORM model."""
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
        """根据用户名获取用户"""
        result = await self._session.execute(select(UserModel).where(UserModel.username == username))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        """根据邮箱获取用户"""
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
