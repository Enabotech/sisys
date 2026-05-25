"""Tests for PermissionService (application layer)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.application.use_cases.permission_management import PermissionService


class TestPermissionService:
    """Test PermissionService application layer implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_user_role_repo = AsyncMock()
        self.mock_role_repo = AsyncMock()

        self.service = PermissionService(
            user_role_repo=self.mock_user_role_repo,
            role_repo=self.mock_role_repo,
        )

    async def test_check_permission_has_permission(self):
        """User with matching role returns True."""
        role = MagicMock()
        role.permissions = ["document:read", "document:write"]

        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(
            user_id=uuid4(),
            resource="document",
            action="read",
        )

        assert result is True

    async def test_check_permission_no_permission(self):
        """User without matching role returns False."""
        role = MagicMock()
        role.permissions = ["document:read"]

        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(
            user_id=uuid4(),
            resource="document",
            action="delete",
        )

        assert result is False

    async def test_check_permission_wildcard_resource(self):
        """Role with *:* permission grants all access."""
        role = MagicMock()
        role.permissions = ["*:*"]

        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(
            user_id=uuid4(),
            resource="anything",
            action="any_action",
        )

        assert result is True

    async def test_check_permission_wildcard_action(self):
        """Role with resource:* permission grants all actions on resource."""
        role = MagicMock()
        role.permissions = ["document:*"]

        self.mock_user_role_repo.get_user_roles.return_value = [role]

        result = await self.service.check_permission(
            user_id=uuid4(),
            resource="document",
            action="delete",
        )

        assert result is True

    async def test_check_permission_no_roles(self):
        """User with no roles returns False."""
        self.mock_user_role_repo.get_user_roles.return_value = []

        result = await self.service.check_permission(
            user_id=uuid4(),
            resource="document",
            action="read",
        )

        assert result is False

    async def test_check_permission_multiple_roles_one_matches(self):
        """If any role has permission, returns True."""
        role1 = MagicMock()
        role1.permissions = ["document:read"]

        role2 = MagicMock()
        role2.permissions = ["agent:execute"]

        self.mock_user_role_repo.get_user_roles.return_value = [role1, role2]

        result = await self.service.check_permission(
            user_id=uuid4(),
            resource="agent",
            action="execute",
        )

        assert result is True

    async def test_get_user_permissions_returns_all_permissions(self):
        """get_user_permissions returns combined permissions from all roles."""
        role1 = MagicMock()
        role1.permissions = ["document:read", "document:write"]

        role2 = MagicMock()
        role2.permissions = ["agent:execute", "document:read"]

        self.mock_user_role_repo.get_user_roles.return_value = [role1, role2]

        result = await self.service.get_user_permissions(uuid4())

        assert "document:read" in result
        assert "document:write" in result
        assert "agent:execute" in result
        assert len(result) == 3  # document:read only appears once (set)

    async def test_get_user_permissions_no_roles(self):
        """get_user_permissions returns empty list when user has no roles."""
        self.mock_user_role_repo.get_user_roles.return_value = []

        result = await self.service.get_user_permissions(uuid4())

        assert result == []

    def test_matches_permission_exact_match(self):
        """Exact resource:action match returns True."""
        assert self.service._matches_permission("document:read", "document", "read") is True

    def test_matches_permission_wildcard_both(self):
        """*:* matches everything."""
        assert self.service._matches_permission("*:*", "anything", "any_action") is True

    def test_matches_permission_wildcard_action(self):
        """resource:* matches any action on resource."""
        assert self.service._matches_permission("document:*", "document", "delete") is True

    def test_matches_permission_no_match(self):
        """Non-matching resource returns False."""
        assert self.service._matches_permission("document:read", "document", "delete") is False

    def test_matches_permission_different_resource(self):
        """Different resource returns False."""
        assert self.service._matches_permission("document:read", "agent", "read") is False

    def test_role_has_permission_with_permission(self):
        """Role with matching permission returns True."""
        role = MagicMock()
        role.permissions = ["document:read"]

        assert self.service._role_has_permission(role, "document", "read") is True

    def test_role_has_permission_without_permission(self):
        """Role without matching permission returns False."""
        role = MagicMock()
        role.permissions = ["document:read"]

        assert self.service._role_has_permission(role, "document", "write") is False
