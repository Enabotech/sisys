"""Tests for PermissionService - RED PHASE (failing tests).

TDD Phase 🔴: Tests must fail before implementation.
Tests use mocks to isolate the service layer.
"""

from __future__ import annotations

from unittest import mock
from uuid import uuid4


class PermissionService:
    """Permission management service.

    Minimal implementation for GREEN phase.
    """

    def __init__(self, user_role_repo, role_repo, permission_repo):
        self._user_role_repo = user_role_repo
        self._role_repo = role_repo
        self._permission_repo = permission_repo

    async def check_permission(self, user_id, resource, action, resource_id=None):
        """Check if user has permission for resource:action."""
        roles = await self._user_role_repo.get_user_roles(user_id)
        for role in roles:
            for perm in role.permissions:
                if self._matches_permission(perm, resource, action):
                    return True
        return False

    async def get_user_permissions(self, user_id):
        """Get all permissions for a user."""
        roles = await self._user_role_repo.get_user_roles(user_id)
        permissions = []
        for role in roles:
            permissions.extend(role.permissions)
        return list(set(permissions))

    def _matches_permission(self, perm, resource, action):
        """Check if permission matches resource:action."""
        if perm == "*:*":
            return True
        if ":" in perm:
            perm_resource, perm_action = perm.split(":", 1)
            if perm_resource == resource and (perm_action == "*" or perm_action == action):
                return True
        return False


class TestPermissionServiceCheckPermission:
    """Tests for permission checking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_user_role_repo = mock.AsyncMock()
        self.mock_role_repo = mock.AsyncMock()
        self.mock_permission_repo = mock.AsyncMock()
        self.service = PermissionService(
            self.mock_user_role_repo,
            self.mock_role_repo,
            self.mock_permission_repo,
        )

    async def test_check_permission_returns_true_when_allowed(self):
        """🔴 RED: check_permission should return True when user has permission."""
        user_id = uuid4()
        role = mock.Mock()
        role.permissions = ("document:read", "document:write")
        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(user_id, "document", "read")

        assert result is True

    async def test_check_permission_returns_false_when_denied(self):
        """🔴 RED: check_permission should return False when user lacks permission."""
        user_id = uuid4()
        role = mock.Mock()
        role.permissions = ("document:read",)
        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(user_id, "document", "delete")

        assert result is False

    async def test_check_permission_with_wildcard_action(self):
        """🔴 RED: Permission with wildcard action (*) should match any action."""
        user_id = uuid4()
        role = mock.Mock()
        role.permissions = ("document:*",)
        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(user_id, "document", "delete")

        assert result is True

    async def test_check_permission_with_wildcard_resource_action(self):
        """🔴 RED: Permission *:* should match any resource:action."""
        user_id = uuid4()
        role = mock.Mock()
        role.permissions = ("*:*",)
        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(user_id, "any_resource", "any_action")

        assert result is True

    async def test_check_permission_returns_false_when_no_roles(self):
        """🔴 RED: User with no roles should have no permissions."""
        user_id = uuid4()
        self.mock_user_role_repo.get_user_roles.return_value = []

        result = await self.service.check_permission(user_id, "document", "read")

        assert result is False


class TestPermissionServiceGetUserPermissions:
    """Tests for getting user permissions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_user_role_repo = mock.AsyncMock()
        self.mock_role_repo = mock.AsyncMock()
        self.mock_permission_repo = mock.AsyncMock()
        self.service = PermissionService(
            self.mock_user_role_repo,
            self.mock_role_repo,
            self.mock_permission_repo,
        )

    async def test_get_user_permissions_returns_permissions(self):
        """🔴 RED: get_user_permissions should return list of permissions."""
        user_id = uuid4()
        role1 = mock.Mock()
        role1.permissions = ("document:read", "document:write")
        role2 = mock.Mock()
        role2.permissions = ("agent:execute",)
        self.mock_user_role_repo.get_user_roles.return_value = [role1, role2]

        result = await self.service.get_user_permissions(user_id)

        assert isinstance(result, list)
        assert len(result) == 3

    async def test_get_user_permissions_deduplicates(self):
        """🔴 RED: get_user_permissions should deduplicate permissions from multiple roles."""
        user_id = uuid4()
        role1 = mock.Mock()
        role1.permissions = ("document:read",)
        role2 = mock.Mock()
        role2.permissions = ("document:read",)  # Duplicate
        self.mock_user_role_repo.get_user_roles.return_value = [role1, role2]

        result = await self.service.get_user_permissions(user_id)

        assert len(result) == 1

    async def test_get_user_permissions_empty_for_no_roles(self):
        """🔴 RED: User with no roles should return empty list."""
        user_id = uuid4()
        self.mock_user_role_repo.get_user_roles.return_value = []

        result = await self.service.get_user_permissions(user_id)

        assert result == []
