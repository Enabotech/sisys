"""Tests for Role Service.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.infrastructure.security.role_service import (
    RoleAlreadyExistsError,
    RoleNotFoundError,
    RoleService,
)


class TestRoleService:
    """Role Service tests."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.get = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def role_service(self, mock_session):
        """Create RoleService instance with mock session."""
        return RoleService(mock_session)

    @pytest.mark.asyncio
    async def test_create_role_success(self, role_service, mock_session):
        """Should create role successfully."""

        # Mock no existing role
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        role = await role_service.create_role(
            name="analyst",
            description="Analyst role",
            permissions=["document:read", "tool:execute"],
        )

        assert role.name == "analyst"
        assert role.description == "Analyst role"
        mock_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_create_role_already_exists(self, role_service, mock_session):
        """Should raise error when role already exists."""
        existing_role = MagicMock()
        existing_role.name = "analyst"

        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_role)))

        with pytest.raises(RoleAlreadyExistsError):
            await role_service.create_role(name="analyst")

    @pytest.mark.asyncio
    async def test_get_role_by_id(self, role_service, mock_session):
        """Should return role when found."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.name = "admin"
        mock_role.description = "Admin role"
        mock_role.is_active = True
        mock_role.created_at = None
        mock_role.updated_at = None

        mock_session.get = AsyncMock(return_value=mock_role)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )

        role = await role_service.get_role_by_id(role_id)

        assert role is not None
        assert role.name == "admin"

    @pytest.mark.asyncio
    async def test_get_role_by_id_not_found(self, role_service, mock_session):
        """Should return None when role not found."""
        mock_session.get = AsyncMock(return_value=None)

        role = await role_service.get_role_by_id(uuid4())

        assert role is None

    @pytest.mark.asyncio
    async def test_get_all_roles(self, role_service, mock_session):
        """Should return all roles."""

        mock_roles = [
            MagicMock(id=uuid4(), name="admin", description="Admin", is_active=True, created_at=None, updated_at=None),
            MagicMock(id=uuid4(), name="viewer", description="Viewer", is_active=True, created_at=None, updated_at=None),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_roles
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock each role's permissions query
        with patch.object(role_service, "get_role_permissions", return_value=[]):
            roles = await role_service.get_all_roles()

        assert len(roles) == 2

    @pytest.mark.asyncio
    async def test_update_role(self, role_service, mock_session):
        """Should update role successfully."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.name = "admin"
        mock_role.description = "Old description"
        mock_role.is_active = True

        mock_session.get = AsyncMock(return_value=mock_role)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )

        await role_service.update_role(
            role_id=role_id,
            description="New description",
        )

        assert mock_role.description == "New description"

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, role_service, mock_session):
        """Should raise error when role not found."""
        mock_session.get = AsyncMock(return_value=None)

        with pytest.raises(RoleNotFoundError):
            await role_service.update_role(uuid4(), description="New desc")

    @pytest.mark.asyncio
    async def test_delete_role_soft_delete(self, role_service, mock_session):
        """Should soft delete role (set is_active=False)."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.is_active = True

        mock_session.get = AsyncMock(return_value=mock_role)

        result = await role_service.delete_role(role_id)

        assert result is True
        assert mock_role.is_active is False

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, role_service, mock_session):
        """Should raise error when deleting non-existent role."""
        mock_session.get = AsyncMock(return_value=None)

        with pytest.raises(RoleNotFoundError):
            await role_service.delete_role(uuid4())

    @pytest.mark.asyncio
    async def test_assign_permission_to_role(self, role_service, mock_session):
        """Should assign permission to role."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.name = "admin"

        mock_session.get = AsyncMock(return_value=mock_role)

        # Mock permission query - permission doesn't exist yet
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await role_service.assign_permission_to_role(role_id, "document:read")

        assert result is True
        mock_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_assign_role_to_user(self, role_service, mock_session):
        """Should assign role to user."""
        user_id = uuid4()
        role_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_role = MagicMock()
        mock_role.id = role_id

        # Mock get for user and role
        mock_session.get = AsyncMock(side_effect=[mock_user, mock_role])

        # Mock check for existing assignment
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await role_service.assign_role_to_user(user_id, role_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_role_from_user(self, role_service, mock_session):
        """Should revoke role from user."""
        user_id = uuid4()
        role_id = uuid4()

        mock_session.execute = AsyncMock(return_value=MagicMock())

        result = await role_service.revoke_role_from_user(user_id, role_id)

        assert result is True
        mock_session.execute.assert_called()
