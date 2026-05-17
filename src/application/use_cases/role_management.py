"""Role Management UseCases - 应用层角色管理用例.

遵循六边形架构：应用层用例，协调领域实体和仓储端口
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.domain.entities.role import Role
from src.domain.exceptions.role_exceptions import (
    CannotDeleteRoleWithUsersError,
    CannotDeleteSystemRoleError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
)
from src.domain.ports.role_repository import RoleRepositoryPort
from src.domain.ports.user_role_repository import UserRoleRepositoryPort

__all__ = [
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
]


class RoleService:
    """角色管理服务.

    应用层用例，负责角色创建、查询、更新、删除
    遵循六边形架构：通过 RoleRepositoryPort 端口访问数据，不直接依赖基础设施
    """

    def __init__(
        self,
        role_repo: RoleRepositoryPort,
        user_role_repo: UserRoleRepositoryPort | None = None,
    ):
        """初始化 RoleService.

        Args:
            role_repo: 角色仓储端口
            user_role_repo: 用户角色关联仓储端口（可选，用于删除前检查）
        """
        self._role_repo = role_repo
        self._user_role_repo = user_role_repo

    async def create_role(
        self,
        name: str,
        permissions: list[str],
        description: str = "",
        is_system_reserved: bool = False,
    ) -> Role:
        """创建新角色.

        Args:
            name: 角色名称（唯一）
            permissions: 权限列表（如 ["document:read", "document:write"]）
            description: 角色描述
            is_system_reserved: 是否为系统保留角色

        Returns:
            创建的角色（包含生成的 ID）

        Raises:
            RoleAlreadyExistsError: 角色名已存在
        """
        existing = await self._role_repo.get_by_name(name)
        if existing:
            raise RoleAlreadyExistsError(name)

        role = Role(
            id=None,  # Let repository generate
            name=name,
            description=description,
            permissions=tuple(permissions),
            is_system_reserved=is_system_reserved,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        return await self._role_repo.save(role)

    async def get_role(self, role_id: UUID) -> Role:
        """根据 ID 获取角色.

        Args:
            role_id: 角色 UUID

        Returns:
            Role 领域实体

        Raises:
            RoleNotFoundError: 角色不存在
        """
        role = await self._role_repo.get_by_id(role_id)
        if not role:
            raise RoleNotFoundError(role_id)
        return role

    async def get_role_by_name(self, name: str) -> Role | None:
        """根据名称获取角色.

        Args:
            name: 角色名称

        Returns:
            Role 领域实体，或 None（角色不存在）
        """
        return await self._role_repo.get_by_name(name)

    async def list_roles(self, active_only: bool = True) -> list[Role]:
        """获取所有角色.

        Args:
            active_only: 仅返回激活的角色

        Returns:
            角色列表
        """
        roles = await self._role_repo.list_all()
        if active_only:
            return [r for r in roles if r.is_active]
        return roles

    async def update_role(
        self,
        role_id: UUID,
        name: str | None = None,
        description: str | None = None,
        permissions: list[str] | None = None,
        is_active: bool | None = None,
    ) -> Role:
        """更新角色.

        Args:
            role_id: 角色 UUID
            name: 新名称（可选）
            description: 新描述（可选）
            permissions: 新权限列表（可选）
            is_active: 是否激活（可选）

        Returns:
            更新后的角色

        Raises:
            RoleNotFoundError: 角色不存在
            RoleAlreadyExistsError: 新名称已存在
        """
        role = await self._role_repo.get_by_id(role_id)
        if not role:
            raise RoleNotFoundError(role_id)

        # Check for duplicate name if name is being changed
        if name is not None and name != role.name:
            existing = await self._role_repo.get_by_name(name)
            if existing:
                raise RoleAlreadyExistsError(name)

        # Create updated role (immutable dataclass)
        updated_role = Role(
            id=role.id,
            name=name if name is not None else role.name,
            description=description if description is not None else role.description,
            permissions=tuple(permissions) if permissions is not None else role.permissions,
            is_system_reserved=role.is_system_reserved,
            is_active=is_active if is_active is not None else role.is_active,
            created_at=role.created_at,
            updated_at=datetime.now(UTC),
        )
        return await self._role_repo.save(updated_role)

    async def delete_role(self, role_id: UUID) -> bool:
        """删除角色.

        Args:
            role_id: 角色 UUID

        Returns:
            True 删除成功

        Raises:
            RoleNotFoundError: 角色不存在
            CannotDeleteSystemRoleError: 不能删除系统保留角色
            CannotDeleteRoleWithUsersError: 角色有关联用户
        """
        role = await self._role_repo.get_by_id(role_id)
        if not role:
            raise RoleNotFoundError(role_id)
        if role.is_system_reserved:
            raise CannotDeleteSystemRoleError(role_id)
        # 检查关联用户
        if self._user_role_repo:
            associated_users = await self._user_role_repo.get_role_users(role_id)
            if associated_users:
                raise CannotDeleteRoleWithUsersError(role_id, len(associated_users))
        # 删除前重新验证（防御 TOCTOU 竞态条件）
        # 在检查和删除之间，角色状态可能被其他事务修改
        role_for_delete = await self._role_repo.get_by_id(role_id)
        if not role_for_delete:
            raise RoleNotFoundError(role_id)
        if role_for_delete.is_system_reserved:
            raise CannotDeleteSystemRoleError(role_id)
        return await self._role_repo.delete(role_id)

    async def assign_permissions(self, role_id: UUID, permissions: list[str]) -> Role:
        """为角色分配权限（替换现有权限）

        Args:
            role_id: 角色 UUID
            permissions: 新的权限列表

        Returns:
            更新后的角色

        Raises:
            RoleNotFoundError: 角色不存在
        """
        return await self.update_role(role_id, permissions=permissions)

    async def add_permission(self, role_id: UUID, permission: str) -> Role:
        """为角色添加一个权限

        Args:
            role_id: 角色 UUID
            permission: 权限字符串（如 "document:read"）

        Returns:
            更新后的角色

        Raises:
            RoleNotFoundError: 角色不存在
        """
        role = await self._role_repo.get_by_id(role_id)
        if not role:
            raise RoleNotFoundError(role_id)
        new_permissions = list(role.permissions) + [permission]
        return await self.update_role(role_id, permissions=new_permissions)
