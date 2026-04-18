"""PermissionService — Domain service interface for authorization.

This module defines the permission service interface (Protocol)
following hexagonal architecture: domain layer defines interface,
infrastructure layer implements it.

Reference: architecture.md - RBAC model (user-role-permission).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    pass


class PermissionService(Protocol):
    """Protocol defining permission service interface.

    The permission service is responsible for:
    - Permission checking (can user perform action on resource)
    - Role permission management
    - User-role assignment/revocation

    This is a domain layer interface (Protocol) that must be implemented
    by the infrastructure layer (src/infrastructure/security/permission_service.py).
    """

    def check_permission(self, user_id: UUID, resource: str, action: str) -> bool:
        """Check if user has permission for a specific resource and action.

        Args:
            user_id: User's UUID.
            resource: Resource name (e.g., "document", "tool", "agent").
            action: Action name (e.g., "read", "write", "delete", "execute").

        Returns:
            bool: True if user has permission, False otherwise.
        """
        ...

    def get_user_permissions(self, user_id: UUID) -> list[str]:
        """Get all permissions for a user (computed from all roles).

        Args:
            user_id: User's UUID.

        Returns:
            list[str]: List of permission strings (format: "resource:action").
        """
        ...

    def assign_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User's UUID.
            role_id: Role's UUID.

        Returns:
            bool: True if assignment succeeded, False otherwise.

        Raises:
            UserNotFoundError: If user doesn't exist.
            RoleNotFoundError: If role doesn't exist.
            RoleAssignmentError: If assignment fails.
        """
        ...

    def revoke_role(self, user_id: UUID, role_id: UUID) -> bool:
        """Revoke a role from a user.

        Args:
            user_id: User's UUID.
            role_id: Role's UUID.

        Returns:
            bool: True if revocation succeeded, False otherwise.

        Raises:
            UserNotFoundError: If user doesn't exist.
            RoleNotFoundError: If role doesn't exist.
            RoleRevocationError: If revocation fails.
        """
        ...

    def get_role_permissions(self, role_id: UUID) -> list[str]:
        """Get all permissions for a specific role.

        Args:
            role_id: Role's UUID.

        Returns:
            list[str]: List of permission strings.
        """
        ...

    def assign_permission_to_role(self, role_id: UUID, permission: str) -> bool:
        """Assign a permission to a role.

        Args:
            role_id: Role's UUID.
            permission: Permission string (format: "resource:action").

        Returns:
            bool: True if assignment succeeded, False otherwise.
        """
        ...

    def revoke_permission_from_role(self, role_id: UUID, permission: str) -> bool:
        """Revoke a permission from a role.

        Args:
            role_id: Role's UUID.
            permission: Permission string (format: "resource:action").

        Returns:
            bool: True if revocation succeeded, False otherwise.
        """
        ...

    def has_role(self, user_id: UUID, role_name: str) -> bool:
        """Check if user has a specific role.

        Args:
            user_id: User's UUID.
            role_name: Role name to check.

        Returns:
            bool: True if user has the role, False otherwise.
        """
        ...
