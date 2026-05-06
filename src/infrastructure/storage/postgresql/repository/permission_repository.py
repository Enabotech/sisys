"""PermissionRepository — 权限仓储实现。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import PermissionModel
from src.infrastructure.storage.postgresql.repository.base_repository import BaseRepository


class PermissionRepository(BaseRepository[PermissionModel]):
    """权限仓储实现。

    继承 BaseRepository[PermissionModel]，添加权限特定查询方法。
    """

    def __init__(self, session: AsyncSession):
        """初始化 PermissionRepository。

        Args:
            session: 异步数据库会话
        """
        super().__init__(PermissionModel, session)

    async def get_by_name(self, name: str) -> PermissionModel | None:
        """根据名称获取权限。

        Args:
            name: 权限名称

        Returns:
            权限实例，如果不存在则返回 None
        """
        result = await self._session.execute(select(PermissionModel).where(PermissionModel.name == name))
        return result.scalar_one_or_none()
