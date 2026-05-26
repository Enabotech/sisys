"""基础设施层权限仓储模块

继承 PostgreSQLAdapter[Permission, PermissionModel]，实现实体与模型转换
通过 _to_entity/_to_model 隔离领域层与 ORM 层
"""

from __future__ import annotations

from sqlalchemy import select

from src.domain.entities.permission import Permission
from src.domain.ports.permission_repository import PermissionRepositoryPort
from src.infrastructure.storage.postgresql.models import PermissionModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter


class PermissionRepository(
    PostgreSQLAdapter[Permission, PermissionModel],
    PermissionRepositoryPort,
):
    """权限仓储实现

    通过 _to_entity/_to_model 隔离领域层与 ORM 层
    """

    def __init__(self) -> None:
        super().__init__(PermissionModel)

    def _to_entity(self, model: PermissionModel) -> Permission:
        """将 ORM 模型转换为领域实体。"""
        return Permission(
            id=model.id,
            name=model.name,
            resource=model.resource,
            action=model.action,
            created_at=model.created_at,
        )

    def _to_model(self, entity: Permission) -> PermissionModel:
        """将领域实体转换为 ORM 模型。"""
        return PermissionModel(
            id=entity.id,
            name=entity.name,
            resource=entity.resource,
            action=entity.action,
        )

    async def get_by_name(self, name: str) -> Permission | None:
        """根据名称获取权限

        Args:
            name: 权限名称

        Returns:
            权限领域实体，如果不存在则返回 None
        """
        result = await self._session.execute(select(PermissionModel).where(PermissionModel.name == name))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
