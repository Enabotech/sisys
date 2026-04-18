"""Security models — Role and Permission value objects.

These are domain value objects that represent security concepts
in the infrastructure layer, not SQLAlchemy models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    pass


@dataclass
class Permission:
    """Permission value object.

    Represents a permission in the format "resource:action".
    Examples: "document:read", "document:write", "tool:execute", "*:*"

    Attributes:
        id: Unique permission identifier.
        resource: Resource name (e.g., "document", "tool", "agent").
        action: Action name (e.g., "read", "write", "delete", "execute").
        description: Human-readable description.
    """

    id: UUID
    resource: str
    action: str
    description: str | None = None

    @property
    def permission_string(self) -> str:
        """Return permission string in resource:action format."""
        return f"{self.resource}:{self.action}"

    @classmethod
    def from_string(cls, permission_str: str, permission_id: UUID | None = None) -> Permission:
        """Create Permission from string format (e.g., "document:read").

        Args:
            permission_str: Permission string in resource:action format.
            permission_id: Optional UUID for the permission.

        Returns:
            Permission: New Permission instance.

        Raises:
            ValueError: If permission string format is invalid.
        """
        parts = permission_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format: {permission_str}. Expected 'resource:action'")
        resource, action = parts
        return cls(id=permission_id or uuid4(), resource=resource, action=action)


@dataclass
class Role:
    """Role value object.

    Represents a role with associated permissions.
    A role is a collection of permissions that can be assigned to users.

    Attributes:
        id: Unique role identifier.
        name: Role name (e.g., "admin", "analyst", "viewer").
        description: Human-readable description.
        permissions: List of permissions granted by this role.
        is_active: Whether the role is active (soft delete support).
        created_at: Role creation timestamp.
        updated_at: Role last update timestamp.
    """

    id: UUID
    name: str
    description: str | None = None
    permissions: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if this role has a specific permission.

        Supports wildcard matching:
        - "*:*" matches all permissions
        - "document:*" matches all document permissions
        - "*:read" matches all read permissions

        Args:
            resource: Resource name.
            action: Action name.

        Returns:
            bool: True if role has the permission.
        """
        # Check for wildcard permission
        if "*:*" in self.permissions:
            return True

        # Check for resource wildcard
        if f"{resource}:*" in self.permissions:
            return True

        # Check for action wildcard
        if f"*:{action}" in self.permissions:
            return True

        # Check for exact match
        if f"{resource}:{action}" in self.permissions:
            return True

        return False

    def add_permission(self, permission: str) -> None:
        """Add a permission to this role.

        Args:
            permission: Permission string in resource:action format.
        """
        if permission not in self.permissions:
            self.permissions.append(permission)

    def remove_permission(self, permission: str) -> None:
        """Remove a permission from this role.

        Args:
            permission: Permission string in resource:action format.
        """
        if permission in self.permissions:
            self.permissions.remove(permission)


@dataclass
class User:
    """User value object for authentication.

    Represents a user with their authentication information and roles.

    Attributes:
        id: Unique user identifier.
        username: User's username (unique).
        email: User's email (unique).
        hashed_password: Bcrypt hashed password.
        is_active: Whether the user account is active.
        roles: List of role names assigned to this user.
        failed_login_attempts: Number of consecutive failed login attempts.
        locked_until: Timestamp when account lock expires (None if not locked).
        created_at: User creation timestamp.
        updated_at: User last update timestamp.
    """

    id: UUID
    username: str
    email: str
    hashed_password: str | None = None
    is_active: bool = True
    roles: list[str] = field(default_factory=list)
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_locked(self) -> bool:
        """Check if the account is currently locked.

        Returns:
            bool: True if account is locked.
        """
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def increment_failed_login(self) -> None:
        """Increment failed login attempt counter."""
        self.failed_login_attempts += 1

    def reset_failed_login(self) -> None:
        """Reset failed login attempt counter."""
        self.failed_login_attempts = 0

    def lock_account(self, duration_minutes: int) -> None:
        """Lock the account for a specified duration.

        Args:
            duration_minutes: Lockout duration in minutes.
        """
        from datetime import timedelta

        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
