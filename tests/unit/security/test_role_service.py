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

    @pytest.mark.asyncio
    async def test_revoke_permission_from_role(self, role_service, mock_session):
        """Should revoke permission from role."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.name = "admin"

        mock_session.get = AsyncMock(return_value=mock_role)

        # Mock permission exists
        mock_perm = MagicMock()
        mock_perm.id = uuid4()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_perm)))

        result = await role_service.revoke_permission_from_role(role_id, "document:read")

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_permission_from_role_not_found(self, role_service, mock_session):
        """Should raise error when role not found."""
        role_id = uuid4()
        mock_session.get = AsyncMock(return_value=None)

        with pytest.raises(RoleNotFoundError):
            await role_service.revoke_permission_from_role(role_id, "document:read")

    @pytest.mark.asyncio
    async def test_revoke_permission_permission_not_exists(self, role_service, mock_session):
        """Should return True when permission doesn't exist (idempotent)."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id

        mock_session.get = AsyncMock(return_value=mock_role)
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await role_service.revoke_permission_from_role(role_id, "nonexistent:action")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_role_permissions(self, role_service, mock_session):
        """Should get permissions for a role."""
        role_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["document:read", "document:write"]
        mock_session.execute = AsyncMock(return_value=mock_result)

        permissions = await role_service.get_role_permissions(role_id)

        assert len(permissions) == 2
        assert "document:read" in permissions

    @pytest.mark.asyncio
    async def test_get_user_roles(self, role_service, mock_session):
        """Should get roles for a user."""
        user_id = uuid4()
        mock_roles = [
            MagicMock(id=uuid4(), name="admin", description="Admin", is_active=True, created_at=None, updated_at=None),
            MagicMock(id=uuid4(), name="viewer", description="Viewer", is_active=True, created_at=None, updated_at=None),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_roles
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(role_service, "get_role_permissions", return_value=["doc:read"]):
            roles = await role_service.get_user_roles(user_id)

        assert len(roles) == 2

    @pytest.mark.asyncio
    async def test_get_user_roles_empty(self, role_service, mock_session):
        """Should return empty list when user has no roles."""
        user_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        roles = await role_service.get_user_roles(user_id)

        assert roles == []

    @pytest.mark.asyncio
    async def test_is_group_member_true(self, role_service, mock_session):
        """Should return True when user is a group member."""
        user_id = uuid4()
        group_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user_id
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await role_service.is_group_member(user_id, group_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_group_member_false(self, role_service, mock_session):
        """Should return False when user is not a group member."""
        user_id = uuid4()
        group_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await role_service.is_group_member(user_id, group_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_group_member_invalid_uuid(self, role_service, mock_session):
        """Should return False for invalid UUID."""
        result = await role_service.is_group_member("not-a-uuid", "also-not")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_group_admin(self, role_service, mock_session):
        """Should delegate to is_group_member."""
        user_id = uuid4()
        group_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user_id
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await role_service.is_group_admin(user_id, group_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_get_role_by_name(self, role_service, mock_session):
        """Should get role by name."""
        mock_role = MagicMock()
        mock_role.id = uuid4()
        mock_role.name = "admin"
        mock_role.description = "Admin role"
        mock_role.is_active = True
        mock_role.created_at = None
        mock_role.updated_at = None

        # First execute for _get_role_by_name, second for get_role_permissions in _build_role_object
        mock_session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_role)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            ]
        )

        role = await role_service.get_role_by_name("admin")

        assert role is not None
        assert role.name == "admin"

    @pytest.mark.asyncio
    async def test_get_role_by_name_not_found(self, role_service, mock_session):
        """Should return None when role name not found."""
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        role = await role_service.get_role_by_name("nonexistent")

        assert role is None

    @pytest.mark.asyncio
    async def test_create_role_invalid_permission_format(self, role_service, mock_session):
        """Should raise error for invalid permission format."""
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(ValueError, match="Invalid permission format"):
            await role_service.create_role(
                name="test_role",
                permissions=["invalid_format"],
            )

    @pytest.mark.asyncio
    async def test_create_role_permission_empty_string(self, role_service, mock_session):
        """Should raise error for empty permission string."""
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(ValueError, match="Invalid permission format"):
            await role_service.create_role(
                name="test_role",
                permissions=[""],
            )

    @pytest.mark.asyncio
    async def test_create_role_permission_starts_with_colon(self, role_service, mock_session):
        """Should raise error for permission starting with colon."""
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(ValueError, match="Invalid permission format"):
            await role_service.create_role(
                name="test_role",
                permissions=[":read"],
            )

    @pytest.mark.asyncio
    async def test_assign_permission_already_assigned(self, role_service, mock_session):
        """Should return True when permission already assigned."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.updated_at = None

        mock_perm = MagicMock()
        mock_perm.id = uuid4()

        # First execute: _get_permission_by_string returns existing permission
        # Second execute: check if already assigned returns existing record
        mock_session.get = AsyncMock(return_value=mock_role)
        mock_session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_perm)),  # _get_permission_by_string
                MagicMock(scalar_one_or_none=MagicMock(return_value=role_id)),  # already assigned check
            ]
        )

        result = await role_service.assign_permission_to_role(role_id, "document:read")

        assert result is True

    @pytest.mark.asyncio
    async def test_assign_role_to_user_max_roles_exceeded(self, role_service, mock_session):
        """Should raise error when user has max roles."""
        user_id = uuid4()
        role_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_role = MagicMock()
        mock_role.id = role_id

        # Mock existing role IDs for user
        existing_role_ids = [uuid4() for _ in range(10)]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = existing_role_ids
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value = mock_scalars

        mock_session.get = AsyncMock(side_effect=[mock_user, mock_role])
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_result,  # Check assignment - not assigned
                mock_result,  # Count roles - returns 10
            ]
        )

        with pytest.raises(ValueError, match="maximum number of roles"):
            await role_service.assign_role_to_user(user_id, role_id)

    @pytest.mark.asyncio
    async def test_assign_role_to_user_not_found(self, role_service, mock_session):
        """Should return False when user not found."""
        user_id = uuid4()
        role_id = uuid4()

        mock_session.get = AsyncMock(side_effect=[None, None])

        result = await role_service.assign_role_to_user(user_id, role_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_assign_role_to_user_already_assigned(self, role_service, mock_session):
        """Should return True when role already assigned to user."""
        user_id = uuid4()
        role_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_role = MagicMock()
        mock_role.id = role_id

        mock_session.get = AsyncMock(side_effect=[mock_user, mock_role])
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user_id)))

        result = await role_service.assign_role_to_user(user_id, role_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_role_name_conflict(self, role_service, mock_session):
        """Should raise error when updating to conflicting name."""
        role_id = uuid4()
        mock_role = MagicMock()
        mock_role.id = role_id
        mock_role.name = "admin"

        conflicting_role = MagicMock()
        conflicting_role.id = uuid4()
        conflicting_role.name = "new_name"

        mock_session.get = AsyncMock(return_value=mock_role)
        mock_session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=conflicting_role)),  # _get_role_by_name
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=[]))),  # get_role_permissions
            ]
        )

        with pytest.raises(RoleAlreadyExistsError):
            await role_service.update_role(role_id, name="new_name")
