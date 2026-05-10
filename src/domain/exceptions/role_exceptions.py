"""Role Management Exceptions — 角色管理相关异常.

异常来源：
- src/application/use_cases/role_management.py → RoleAlreadyExistsError, RoleNotFoundError, ...
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions.business_exceptions import (
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)


class RoleAlreadyExistsError(ConflictError):
    """角色已存在异常（保留 name 属性）."""

    code = "EXCEPTION_203"

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Role with name '{name}' already exists")


class RoleNotFoundError(NotFoundError):
    """角色不存在异常（保留 role_id 属性）."""

    code = "EXCEPTION_202"

    def __init__(self, role_id: UUID) -> None:
        self.role_id = role_id
        super().__init__(f"Role with id '{role_id}' not found")


class CannotDeleteSystemRoleError(BusinessRuleViolationError):
    """不能删除系统保留角色异常（保留 role_id 属性）."""

    code = "EXCEPTION_207"

    def __init__(self, role_id: UUID) -> None:
        self.role_id = role_id
        super().__init__(f"Cannot delete system-reserved role '{role_id}'")


class CannotDeleteRoleWithUsersError(ConflictError):
    """不能删除有关联用户的角色异常（保留 role_id + user_count 属性）."""

    code = "EXCEPTION_203"

    def __init__(self, role_id: UUID, user_count: int) -> None:
        self.role_id = role_id
        self.user_count = user_count
        super().__init__(f"Cannot delete role '{role_id}' - {user_count} users are assigned to this role")


__all__ = [
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
]
