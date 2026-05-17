"""RoleRepository — 角色仓储实现。

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.permission import Permission
from src.domain.entities.role import Role
from src.domain.ports.role_repository import RoleRepositoryPort
from src.infrastructure.storage.postgresql.models import PermissionModel, RoleModel
from src.infrastructure.storage.postgresql.session_context import get_session


class RoleRepository(RoleRepositoryPort):
    """角色仓储实现。

    实现领域实体与 SQLAlchemy 模型之间的转换。
    继承 RoleRepositoryPort 端口接口。
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    def _to_domain(self, model: RoleModel) -> "Role":
        """将 SQLAlchemy 模型转换为领域实体。

        Args:
            model: SQLAlchemy 模型实例

        Returns:
            Role 领域实体
        """
        from src.domain.entities.role import Role

        return Role(
            id=model.id,
            name=model.name,
            description=model.description or "",
            permissions=(),  # Permissions loaded separately via async method
            is_system_reserved=model.is_system_reserved,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _get_permissions_for_model(self, role_id: UUID) -> tuple[str, ...]:
        """从关联表获取角色的权限字符串列表。

        Args:
            role_id: 角色 UUID

        Returns:
            权限字符串元组
        """
        from src.infrastructure.storage.postgresql.models import PermissionModel
        from src.infrastructure.storage.postgresql.models.rbac_association import (
            role_permissions_table as role_permissions,
        )

        result = await self._session.execute(
            select(PermissionModel.name)
            .join(role_permissions, PermissionModel.id == role_permissions.c.permission_id)
            .where(role_permissions.c.role_id == role_id)
        )
        return tuple(r[0] for r in result.fetchall())

    async def delete(self, id: UUID) -> bool:
        """删除角色。

        Args:
            id: 角色 UUID

        Returns:
            True 删除成功

        Raises:
            RoleNotFoundError: 角色不存在
        """
        model = await self._session.get(RoleModel, id)
        if not model:
            from src.domain.exceptions.role_exceptions import RoleNotFoundError

            raise RoleNotFoundError(id)
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def _load_permissions_for_model(self, model: RoleModel) -> "Role":
        """为模型加载权限并返回完整的领域实体。

        Args:
            model: SQLAlchemy 模型实例

        Returns:
            包含权限的 Role 领域实体
        """
        from src.domain.entities.role import Role

        permissions = await self._get_permissions_for_model(model.id)
        return Role(
            id=model.id,
            name=model.name,
            description=model.description or "",
            permissions=permissions,
            is_system_reserved=model.is_system_reserved,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, role: "Role") -> RoleModel:
        """将领域实体转换为 SQLAlchemy 模型。

        Args:
            role: Role 领域实体

        Returns:
            RoleModel SQLAlchemy 模型实例
        """
        created_at = role.created_at
        if created_at is not None and created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)

        updated_at = role.updated_at
        if updated_at is not None and updated_at.tzinfo is not None:
            updated_at = updated_at.replace(tzinfo=None)

        return RoleModel(
            id=role.id or uuid4(),
            name=role.name,
            description=role.description,
            is_system_reserved=role.is_system_reserved,
            is_active=role.is_active,
            created_at=created_at or datetime.now(UTC).replace(tzinfo=None),
            updated_at=updated_at,
        )

    async def _get_or_create_permission(self, perm_name: str) -> UUID:
        """获取或创建权限记录。

        Args:
            perm_name: 权限名称

        Returns:
            权限 UUID
        """
        from src.infrastructure.storage.postgresql.models import PermissionModel

        result = await self._session.execute(select(PermissionModel).where(PermissionModel.name == perm_name))
        perm_model = result.scalar_one_or_none()
        if perm_model:
            return perm_model.id

        # 创建新权限
        new_perm = PermissionModel(name=perm_name)
        self._session.add(new_perm)
        await self._session.flush()
        return new_perm.id

    async def _save_permissions(self, role_id: UUID, permissions: tuple[str, ...]) -> None:
        """保存角色权限到关联表。

        Args:
            role_id: 角色 UUID
            permissions: 权限字符串元组
        """
        from src.infrastructure.storage.postgresql.models.rbac_association import (
            role_permissions_table as role_permissions,
        )

        # 先删除现有权限
        await self._session.execute(role_permissions.delete().where(role_permissions.c.role_id == role_id))

        # 插入新权限（获取或创建权限记录）
        for perm_name in permissions:
            perm_id = await self._get_or_create_permission(perm_name)
            await self._session.execute(role_permissions.insert().values(role_id=role_id, permission_id=perm_id))

    async def get_by_name(self, name: str) -> "Role | None":
        """根据名称获取角色。

        Args:
            name: 角色名称

        Returns:
            Role 领域实体，如果不存在则返回 None
        """
        result = await self._session.execute(select(RoleModel).where(RoleModel.name == name))
        model = result.scalar_one_or_none()
        return await self._load_permissions_for_model(model) if model else None

    async def save(self, role: "Role") -> "Role":
        """保存角色（插入或更新）。

        Args:
            role: Role 领域实体

        Returns:
            保存后的 Role 领域实体

        Raises:
            RoleAlreadyExistsError: 角色名已存在（数据库唯一约束违反）
        """
        model = self._to_model(role)
        if role.id is None:
            self._session.add(model)
        else:
            model = await self._session.merge(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError:
            await self._session.rollback()
            from src.domain.exceptions.role_exceptions import RoleAlreadyExistsError

            raise RoleAlreadyExistsError(role.name)

        # 保存权限关联
        if role.permissions:
            await self._save_permissions(model.id, role.permissions)
            await self._session.flush()

        return await self._load_permissions_for_model(model)

    async def get_by_id(self, id: UUID) -> "Role | None":
        """根据 ID 获取角色。

        Args:
            id: 角色 UUID

        Returns:
            Role 领域实体，如果不存在则返回 None
        """
        result = await self._session.execute(select(RoleModel).where(RoleModel.id == id))
        model = result.scalar_one_or_none()
        return await self._load_permissions_for_model(model) if model else None

    async def list_all(self, skip: int = 0, limit: int = 100) -> list["Role"]:
        """获取所有角色.

        Args:
            skip: 跳过数量
            limit: 返回数量上限

        Returns:
            Role 领域实体列表
        """
        result = await self._session.execute(select(RoleModel).offset(skip).limit(limit))
        models = result.scalars().all()
        roles = []
        for m in models:
            roles.append(await self._load_permissions_for_model(m))
        return roles

    async def get_permissions_for_role(self, role_id: str) -> list[Permission]:
        """获取角色的权限列表。

        Args:
            role_id: 角色 ID

        Returns:
            Permission 领域实体列表
        """
        from src.infrastructure.storage.postgresql.models.rbac_association import (
            role_permissions_table as role_permissions,
        )

        result = await self._session.execute(
            select(PermissionModel)
            .join(role_permissions, PermissionModel.id == role_permissions.c.permission_id)
            .where(role_permissions.c.role_id == role_id)
        )
        return [self._to_permission_entity(m) for m in result.scalars().all()]

    def _to_permission_entity(self, model: PermissionModel) -> Permission:
        """PermissionModel -> Permission domain entity."""
        return Permission(
            id=model.id,
            name=model.name,
            resource=model.resource,
            action=model.action,
            created_at=model.created_at,
        )
