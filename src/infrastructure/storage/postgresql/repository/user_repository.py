"""UserRepository — 用户仓储实现。

重构说明（Phase 3）：
- 继承 PostgreSQLAdapter[UserModel, UserModel]（恒等转换）
- 实现 _to_entity/_to_model 恒等转换
- 自动获得父类 get_by_id/save/delete/list_all
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import UserModel
from src.infrastructure.storage.postgresql.repository.base_repository import PostgreSQLAdapter


class UserRepository(PostgreSQLAdapter[UserModel, UserModel]):
    """用户仓储实现。

    继承 PostgreSQLAdapter[UserModel, UserModel]，
    添加用户特定查询方法。
    """

    def __init__(self, session: AsyncSession):
        """初始化 UserRepository。

        Args:
            session: 异步数据库会话
        """
        super().__init__(UserModel, session)

    def _to_entity(self, model: UserModel) -> UserModel:
        """ORM 模型 → 领域实体（恒等转换）。"""
        return model

    def _to_model(self, entity: UserModel) -> UserModel:
        """领域实体 → ORM 模型（恒等转换）。"""
        return entity

    async def get_by_username(self, username: str) -> UserModel | None:
        """根据用户名获取用户。

        Args:
            username: 用户名

        Returns:
            用户实例，如果不存在则返回 None
        """
        result = await self._session.execute(select(UserModel).where(UserModel.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserModel | None:
        """根据邮箱获取用户。

        Args:
            email: 邮箱地址

        Returns:
            用户实例，如果不存在则返回 None
        """
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        return result.scalar_one_or_none()
