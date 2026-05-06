"""UserRepository — 用户仓储实现。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import UserModel
from src.infrastructure.storage.postgresql.repository.base_repository import BaseRepository


class UserRepository(BaseRepository[UserModel]):
    """用户仓储实现。

    继承 BaseRepository[UserModel]，添加用户特定查询方法。
    """

    def __init__(self, session: AsyncSession):
        """初始化 UserRepository。

        Args:
            session: 异步数据库会话
        """
        super().__init__(UserModel, session)

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
