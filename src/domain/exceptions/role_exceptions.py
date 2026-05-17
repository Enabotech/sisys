"""领域层角色管理异常模块

定义角色管理相关的领域异常，包括角色已存在、角色不存在、不能删除系统保留角色等

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions.business_exceptions import (
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)


class RoleAlreadyExistsError(ConflictError):
    """角色已存在异常（保留 name 属性）

    Attributes:
        name: 重复的角色名称
    """

    code = "EXCEPTION_203"

    def __init__(self, name: str) -> None:
        """初始化角色已存在异常

        Args:
            name: 重复的角色名称
        """
        self.name = name
        super().__init__(f"Role with name '{name}' already exists")


class RoleNotFoundError(NotFoundError):
    """角色不存在异常（保留 role_id 属性）

    Attributes:
        role_id: 不存在的角色 UUID
    """

    code = "EXCEPTION_202"

    def __init__(self, role_id: UUID) -> None:
        """初始化角色不存在异常

        Args:
            role_id: 不存在的角色 UUID
        """
        self.role_id = role_id
        super().__init__(f"Role with id '{role_id}' not found")


class CannotDeleteSystemRoleError(BusinessRuleViolationError):
    """不能删除系统保留角色异常（保留 role_id 属性）

    Attributes:
        role_id: 系统保留角色的 UUID
    """

    code = "EXCEPTION_207"

    def __init__(self, role_id: UUID) -> None:
        """初始化不能删除系统保留角色异常

        Args:
            role_id: 系统保留角色的 UUID
        """
        self.role_id = role_id
        super().__init__(f"Cannot delete system-reserved role '{role_id}'")


class CannotDeleteRoleWithUsersError(ConflictError):
    """不能删除有关联用户的角色异常（保留 role_id + user_count 属性）

    Attributes:
        role_id: 角色的 UUID
        user_count: 关联用户数量
    """

    code = "EXCEPTION_203"

    def __init__(self, role_id: UUID, user_count: int) -> None:
        """初始化不能删除有关联用户的角色异常

        Args:
            role_id: 角色的 UUID
            user_count: 关联用户数量
        """
        self.role_id = role_id
        self.user_count = user_count
        super().__init__(f"Cannot delete role '{role_id}' - {user_count} users are assigned to this role")


__all__ = [
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
]
