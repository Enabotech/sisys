"""PermissionService — Permission control service implementation.

Implements the PermissionService protocol for authorization checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.security.role_service import RoleService

if TYPE_CHECKING:
    pass


class PermissionServiceImpl:
    """Permission service implementation.

    Implements the PermissionService protocol for checking user permissions.
    Uses RoleService to fetch user roles and their permissions.
    """

    def __init__(
        self,
        session: AsyncSession,
        role_service: RoleService | None = None,
    ) -> None:
        """Initialize PermissionService.

        Args:
            session: Async database session.
            role_service: Role service instance. If None, creates new one.
        """
        self._session = session
        self._role_service = role_service or RoleService(session)

    async def check_permission(self, user_id: UUID, resource: str, action: str) -> bool:
        """Check if user has permission for a specific resource and action.

        Supports wildcard matching:
        - "*:*" matches all permissions
        - "document:*" matches all document permissions
        - "*:read" matches all read permissions

        Args:
            user_id: User's UUID.
            resource: Resource name (e.g., "document", "tool", "agent").
            action: Action name (e.g., "read", "write", "delete", "execute").

        Returns:
            bool: True if user has permission, False otherwise.
        """
        # Get all roles for user
        roles = await self._role_service.get_user_roles(user_id)

        # Check if any role has the permission
        for role in roles:
            if role.has_permission(resource, action):
                return True

        return False

    async def get_user_permissions(self, user_id: UUID) -> list[str]:
        """Get all permissions for a user (computed from all roles).

        Args:
            user_id: User's UUID.

        Returns:
            list[str]: List of permission strings (format: "resource:action").
            Duplicates are removed.
        """
        roles = await self._role_service.get_user_roles(user_id)

        permissions_set = set()
        for role in roles:
            permissions_set.update(role.permissions)

        return list(permissions_set)

    async def assign_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User's UUID.
            role_id: Role's UUID.

        Returns:
            bool: True if assignment succeeded, False otherwise.
        """
        return await self._role_service.assign_role_to_user(user_id, role_id)

    async def revoke_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Revoke a role from a user.

        Args:
            user_id: User's UUID.
            role_id: Role's UUID.

        Returns:
            bool: True if revocation succeeded, False otherwise.
        """
        return await self._role_service.revoke_role_from_user(user_id, role_id)

    async def get_role_permissions(self, role_id: UUID) -> list[str]:
        """Get all permissions for a specific role.

        Args:
            role_id: Role's UUID.

        Returns:
            list[str]: List of permission strings.
        """
        return await self._role_service.get_role_permissions(role_id)

    async def assign_permission_to_role(self, role_id: UUID, permission: str) -> bool:
        """Assign a permission to a role.

        Args:
            role_id: Role's UUID.
            permission: Permission string (format: "resource:action").

        Returns:
            bool: True if assignment succeeded, False otherwise.
        """
        return await self._role_service.assign_permission_to_role(role_id, permission)

    async def revoke_permission_from_role(self, role_id: UUID, permission: str) -> bool:
        """Revoke a permission from a role.

        Args:
            role_id: Role's UUID.
            permission: Permission string (format: "resource:action").

        Returns:
            bool: True if revocation succeeded, False otherwise.
        """
        return await self._role_service.revoke_permission_from_role(role_id, permission)

    async def has_role(self, user_id: UUID, role_name: str) -> bool:
        """Check if user has a specific role.

        Args:
            user_id: User's UUID.
            role_name: Role name to check.

        Returns:
            bool: True if user has the role, False otherwise.
        """
        roles = await self._role_service.get_user_roles(user_id)
        return any(role.name == role_name for role in roles)
