"""PermissionRepository — 权限仓储实现。

重构说明（Phase 3）：
- 继承 PostgreSQLAdapter[PermissionModel, PermissionModel]（恒等转换）
- 实现 _to_entity/_to_model 恒等转换
- 自动获得父类 get_by_id/save/delete/list_all

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
"""

from __future__ import annotations

from sqlalchemy import select

from src.infrastructure.storage.postgresql.models import PermissionModel
from src.infrastructure.storage.postgresql.repository.base_repository import PostgreSQLAdapter


class PermissionRepository(PostgreSQLAdapter[PermissionModel, PermissionModel]):
    """权限仓储实现。

    继承 PostgreSQLAdapter[PermissionModel, PermissionModel]，
    添加权限特定查询方法。
    """

    def __init__(self) -> None:
        super().__init__(PermissionModel)

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
