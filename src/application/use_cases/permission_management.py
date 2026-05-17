"""SISYS 应用层权限服务模块。

遵循六边形架构：应用层服务，实现 PermissionServicePort 接口

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from uuid import UUID

from src.domain.ports.permission_service import PermissionServicePort
from src.domain.ports.role_repository import RoleRepositoryPort
from src.domain.ports.user_role_repository import UserRoleRepositoryPort


class PermissionService(PermissionServicePort):
    """权限服务实现.

    负责权限检查和用户权限查询
    遵循六边形架构：通过仓储端口访问数据，不直接依赖基础设施
    """

    def __init__(
        self,
        user_role_repo: UserRoleRepositoryPort,
        role_repo: RoleRepositoryPort,
    ):
        """初始化 PermissionService.

        Args:
            user_role_repo: 用户-角色关联仓储端口
            role_repo: 角色仓储端口
        """
        self._user_role_repo = user_role_repo
        self._role_repo = role_repo

    async def check_permission(
        self,
        user_id: UUID,
        resource: str,
        action: str,
        resource_id: UUID | None = None,
    ) -> bool:
        """检查用户是否拥有指定资源的操作权限.

        Args:
            user_id: 用户 ID
            resource: 资源类型（如 "document", "agent"）
            action: 操作类型（如 "read", "write", "execute"）
            resource_id: 资源实例 ID（可选，用于实例级权限控制）

        Returns:
            True 如果有权限，False 否则
        """
        roles = await self._user_role_repo.get_user_roles(user_id)
        for role in roles:
            if self._role_has_permission(role, resource, action):
                return True
        return False

    async def get_user_permissions(self, user_id: UUID) -> list[str]:
        """获取用户所有权限列表.

        Args:
            user_id: 用户 ID

        Returns:
            权限字符串列表（如 ["document:read", "document:write", "agent:execute"]）
        """
        roles = await self._user_role_repo.get_user_roles(user_id)
        permissions: set[str] = set()
        for role in roles:
            permissions.update(role.permissions)
        return list(permissions)

    def _role_has_permission(self, role, resource: str, action: str) -> bool:
        """检查角色是否拥有指定权限.

        Args:
            role: Role 领域实体
            resource: 资源类型
            action: 操作类型

        Returns:
            True 如果拥有权限，False 否则
        """
        for perm in role.permissions:
            if self._matches_permission(perm, resource, action):
                return True
        return False

    def _matches_permission(self, perm: str, resource: str, action: str) -> bool:
        """检查权限字符串是否匹配 resource:action.

        Args:
            perm: 权限字符串（如 "document:read", "*:*"）
            resource: 资源类型
            action: 操作类型

        Returns:
            True 如果匹配，False 否则
        """
        if perm == "*:*":
            return True
        if ":" in perm:
            perm_resource, perm_action = perm.split(":", 1)
            if perm_resource == resource and (perm_action == "*" or perm_action == action):
                return True
        return False
