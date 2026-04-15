"""RoleRepository — 角色仓储实现。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.base_repository import BaseRepository
from src.infrastructure.storage.postgresql.models import PermissionModel, RoleModel


class RoleRepository(BaseRepository[RoleModel]):
    """角色仓储实现。

    继承 BaseRepository[RoleModel]，添加角色特定查询方法。
    """

    def __init__(self, session: AsyncSession):
        """初始化 RoleRepository。

        Args:
            session: 异步数据库会话
        """
        super().__init__(RoleModel, session)

    async def get_by_name(self, name: str) -> RoleModel | None:
        """根据名称获取角色。

        Args:
            name: 角色名称

        Returns:
            角色实例，如果不存在则返回 None
        """
        result = await self._session.execute(select(RoleModel).where(RoleModel.name == name))
        return result.scalar_one_or_none()

    async def get_permissions_for_role(self, role_id: str) -> list[PermissionModel]:
        """获取角色的权限列表。

        Args:
            role_id: 角色 ID

        Returns:
            权限列表
        """
        from src.infrastructure.storage.postgresql.models.association import (
            role_permissions_table as role_permissions,
        )

        result = await self._session.execute(
            select(PermissionModel)
            .join(role_permissions, PermissionModel.id == role_permissions.c.permission_id)
            .where(role_permissions.c.role_id == role_id)
        )
        return list(result.scalars().all())
