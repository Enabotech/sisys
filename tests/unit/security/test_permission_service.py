"""Tests for Permission Service.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.infrastructure.security.models import Role
from src.infrastructure.security.permission_service import PermissionServiceImpl


class TestPermissionService:
    """Permission Service tests."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def permission_service(self, mock_session):
        """Create PermissionService instance with mock session."""
        return PermissionServiceImpl(mock_session)

    @pytest.mark.asyncio
    async def test_check_permission_admin_role(self, permission_service, mock_session):
        """Should return True when user has admin role (all permissions)."""
        user_id = uuid4()

        # Create admin role with *:* permission
        admin_role = Role(
            id=uuid4(),
            name="admin",
            permissions=["*:*"],
        )

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[admin_role])

        permission_service._role_service = mock_role_service

        result = await permission_service.check_permission(user_id, "any_resource", "any_action")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_specific(self, permission_service, mock_session):
        """Should return True when user has specific permission."""
        user_id = uuid4()

        analyst_role = Role(
            id=uuid4(),
            name="analyst",
            permissions=["document:read", "document:write"],
        )

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[analyst_role])

        permission_service._role_service = mock_role_service

        result = await permission_service.check_permission(user_id, "document", "read")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_denied(self, permission_service, mock_session):
        """Should return False when user lacks permission."""
        user_id = uuid4()

        viewer_role = Role(
            id=uuid4(),
            name="viewer",
            permissions=["document:read"],
        )

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[viewer_role])

        permission_service._role_service = mock_role_service

        result = await permission_service.check_permission(user_id, "document", "delete")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, permission_service, mock_session):
        """Should return all permissions from all user roles."""
        user_id = uuid4()

        analyst_role = Role(
            id=uuid4(),
            name="analyst",
            permissions=["document:read", "tool:execute"],
        )
        custom_role = Role(
            id=uuid4(),
            name="custom",
            permissions=["report:generate"],
        )

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[analyst_role, custom_role])

        permission_service._role_service = mock_role_service

        permissions = await permission_service.get_user_permissions(user_id)

        assert "document:read" in permissions
        assert "tool:execute" in permissions
        assert "report:generate" in permissions

    @pytest.mark.asyncio
    async def test_get_user_permissions_no_duplicates(self, permission_service, mock_session):
        """Should not return duplicate permissions."""
        user_id = uuid4()

        role1 = Role(id=uuid4(), name="role1", permissions=["document:read"])
        role2 = Role(id=uuid4(), name="role2", permissions=["document:read"])

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[role1, role2])

        permission_service._role_service = mock_role_service

        permissions = await permission_service.get_user_permissions(user_id)

        # Count occurrences of document:read
        assert permissions.count("document:read") == 1

    @pytest.mark.asyncio
    async def test_assign_role(self, permission_service, mock_session):
        """Should delegate role assignment to role service."""
        user_id = uuid4()
        role_id = uuid4()

        mock_role_service = AsyncMock()
        mock_role_service.assign_role_to_user = AsyncMock(return_value=True)

        permission_service._role_service = mock_role_service

        result = await permission_service.assign_role(user_id, role_id)

        assert result is True
        mock_role_service.assign_role_to_user.assert_called_once_with(user_id, role_id)

    @pytest.mark.asyncio
    async def test_revoke_role(self, permission_service, mock_session):
        """Should delegate role revocation to role service."""
        user_id = uuid4()
        role_id = uuid4()

        mock_role_service = AsyncMock()
        mock_role_service.revoke_role_from_user = AsyncMock(return_value=True)

        permission_service._role_service = mock_role_service

        result = await permission_service.revoke_role(user_id, role_id)

        assert result is True
        mock_role_service.revoke_role_from_user.assert_called_once_with(user_id, role_id)

    @pytest.mark.asyncio
    async def test_has_role_true(self, permission_service, mock_session):
        """Should return True when user has the role."""
        user_id = uuid4()

        analyst_role = Role(id=uuid4(), name="analyst", permissions=["document:read"])

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[analyst_role])

        permission_service._role_service = mock_role_service

        result = await permission_service.has_role(user_id, "analyst")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_role_false(self, permission_service, mock_session):
        """Should return False when user doesn't have the role."""
        user_id = uuid4()

        viewer_role = Role(id=uuid4(), name="viewer", permissions=["document:read"])

        mock_role_service = AsyncMock()
        mock_role_service.get_user_roles = AsyncMock(return_value=[viewer_role])

        permission_service._role_service = mock_role_service

        result = await permission_service.has_role(user_id, "admin")

        assert result is False
