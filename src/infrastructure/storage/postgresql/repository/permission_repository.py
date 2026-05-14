"""PermissionRepository — 权限仓储实现。

重构说明（Phase 3）：
- 继承 PostgreSQLAdapter[PermissionModel, PermissionModel]（恒等转换）
- 实现 _to_entity/_to_model 恒等转换
- 自动获得父类 get_by_id/save/delete/list_all
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import PermissionModel
from src.infrastructure.storage.postgresql.repository.base_repository import PostgreSQLAdapter


class PermissionRepository(PostgreSQLAdapter[PermissionModel, PermissionModel]):
    """权限仓储实现。

    继承 PostgreSQLAdapter[PermissionModel, PermissionModel]，
    添加权限特定查询方法。
    """

    def __init__(self, session: AsyncSession):
        """初始化 PermissionRepository。

        Args:
            session: 异步数据库会话
        """
        super().__init__(PermissionModel, session)

    def _to_entity(self, model: PermissionModel) -> PermissionModel:
        """ORM 模型 → 领域实体（恒等转换）。"""
        return model

    def _to_model(self, entity: PermissionModel) -> PermissionModel:
        """领域实体 → ORM 模型（恒等转换）。"""
        return entity

    async def get_by_name(self, name: str) -> PermissionModel | None:
        """根据名称获取权限。

        Args:
            name: 权限名称

        Returns:
            权限实例，如果不存在则返回 None
        """
        result = await self._session.execute(select(PermissionModel).where(PermissionModel.name == name))
        return result.scalar_one_or_none()
