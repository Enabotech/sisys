"""Tests for RoleService - RED PHASE (failing tests).

TDD Phase 🔴: Tests must fail before implementation.
Tests use mocks to isolate the service layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest

from src.application.use_cases.role_management import (
    CannotDeleteSystemRoleError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    RoleService,
)
from src.domain.entities.role import Role
from src.domain.ports.role_repository import RoleRepositoryPort


class TestRoleServiceCreation:
    """Tests for Role creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repo = mock.AsyncMock(spec=RoleRepositoryPort)
        self.service = RoleService(self.mock_repo)

    @pytest.mark.asyncio
    async def test_create_role_returns_role(self):
        """🔴 RED: create_role should return a Role instance."""
        self.mock_repo.get_by_name.return_value = None
        saved_role = Role(
            id=uuid4(),
            name="test_role",
            description="",
            permissions=("document:read", "document:write"),
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.mock_repo.save.return_value = saved_role

        result = await self.service.create_role(
            name="test_role",
            permissions=["document:read", "document:write"],
        )

        assert result is not None
        assert isinstance(result, Role)
        assert result.name == "test_role"

    @pytest.mark.asyncio
    async def test_create_role_with_duplicate_name_raises_error(self):
        """🔴 RED: Creating a role with existing name should raise RoleAlreadyExistsError."""
        existing_role = Role(
            id=uuid4(),
            name="test_role",
            description="",
            permissions=(),
            is_system_reserved=False,
            is_active=True,
        )
        self.mock_repo.get_by_name.return_value = existing_role

        with pytest.raises(RoleAlreadyExistsError):
            await self.service.create_role(name="test_role", permissions=[])

    @pytest.mark.asyncio
    async def test_create_role_saves_to_repository(self):
        """🔴 RED: create_role should save the role to repository."""
        self.mock_repo.get_by_name.return_value = None
        saved_role = Role(
            id=uuid4(),
            name="test_role",
            description="Test description",
            permissions=("document:read",),
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.mock_repo.save.return_value = saved_role

        result = await self.service.create_role(
            name="test_role",
            permissions=["document:read"],
            description="Test description",
        )

        self.mock_repo.save.assert_called_once()
        assert result.name == "test_role"


class TestRoleServiceRetrieval:
    """Tests for Role retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repo = mock.AsyncMock(spec=RoleRepositoryPort)
        self.service = RoleService(self.mock_repo)

    @pytest.mark.asyncio
    async def test_get_role_returns_role(self):
        """🔴 RED: get_role should return a Role instance."""
        role_id = uuid4()
        expected_role = Role(
            id=role_id,
            name="admin",
            description="Administrator",
            permissions=("*:*",),
            is_system_reserved=True,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.mock_repo.get_by_id.return_value = expected_role

        result = await self.service.get_role(role_id)

        assert result is not None
        assert result.name == "admin"
        assert result.is_system_reserved is True

    @pytest.mark.asyncio
    async def test_get_role_returns_none_when_not_found(self):
        """🔴 RED: get_role should return None when role doesn't exist."""
        role_id = uuid4()
        self.mock_repo.get_by_id.return_value = None

        result = await self.service.get_role(role_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_roles_returns_list(self):
        """🔴 RED: list_roles should return a list of roles."""
        roles = [
            Role(id=uuid4(), name="admin", description="", permissions=(), is_active=True, created_at=datetime.now(UTC)),
            Role(id=uuid4(), name="viewer", description="", permissions=(), is_active=True, created_at=datetime.now(UTC)),
        ]
        self.mock_repo.list_all.return_value = roles

        result = await self.service.list_roles()

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_roles_filters_inactive(self):
        """🔴 RED: list_roles with active_only=True should filter inactive roles."""
        roles = [
            Role(
                id=uuid4(),
                name="admin",
                description="",
                permissions=(),
                is_active=True,
                created_at=datetime.now(UTC),
            ),
            Role(
                id=uuid4(),
                name="inactive_role",
                description="",
                permissions=(),
                is_active=False,
                created_at=datetime.now(UTC),
            ),
        ]
        self.mock_repo.list_all.return_value = roles

        result = await self.service.list_roles(active_only=True)

        assert len(result) == 1
        assert result[0].name == "admin"


class TestRoleServiceDeletion:
    """Tests for Role deletion."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repo = mock.AsyncMock(spec=RoleRepositoryPort)
        self.service = RoleService(self.mock_repo)

    @pytest.mark.asyncio
    async def test_delete_role_returns_true(self):
        """🔴 RED: delete_role should return True on success."""
        role_id = uuid4()
        role = Role(
            id=role_id,
            name="test_role",
            description="",
            permissions=(),
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.mock_repo.get_by_id.return_value = role
        self.mock_repo.delete.return_value = True

        result = await self.service.delete_role(role_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_role_raises_error(self):
        """🔴 RED: Deleting non-existent role should raise RoleNotFoundError."""
        role_id = uuid4()
        self.mock_repo.get_by_id.return_value = None

        with pytest.raises(RoleNotFoundError):
            await self.service.delete_role(role_id)

    @pytest.mark.asyncio
    async def test_delete_system_role_raises_error(self):
        """🔴 RED: Deleting system-reserved role should raise CannotDeleteSystemRoleError."""
        role_id = uuid4()
        role = Role(
            id=role_id,
            name="admin",
            description="System admin",
            permissions=("*:*",),
            is_system_reserved=True,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.mock_repo.get_by_id.return_value = role

        with pytest.raises(CannotDeleteSystemRoleError):
            await self.service.delete_role(role_id)


class TestRoleServiceUpdate:
    """Tests for Role update."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repo = mock.AsyncMock(spec=RoleRepositoryPort)
        self.service = RoleService(self.mock_repo)

    @pytest.mark.asyncio
    async def test_update_role_permissions(self):
        """🔴 RED: update_role should update permissions."""
        role_id = uuid4()
        existing_role = Role(
            id=role_id,
            name="test_role",
            description="",
            permissions=("document:read",),
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        updated_role = Role(
            id=role_id,
            name="test_role",
            description="",
            permissions=("document:read", "document:write"),
            is_system_reserved=False,
            is_active=True,
            created_at=existing_role.created_at,
            updated_at=datetime.now(UTC),
        )
        self.mock_repo.get_by_id.return_value = existing_role
        self.mock_repo.save.return_value = updated_role

        result = await self.service.update_role(
            role_id,
            permissions=["document:read", "document:write"],
        )

        assert result.permissions == ("document:read", "document:write")

    @pytest.mark.asyncio
    async def test_update_nonexistent_role_raises_error(self):
        """🔴 RED: Updating non-existent role should raise RoleNotFoundError."""
        role_id = uuid4()
        self.mock_repo.get_by_id.return_value = None

        with pytest.raises(RoleNotFoundError):
            await self.service.update_role(role_id, name="new_name")

    @pytest.mark.asyncio
    async def test_add_permission_to_role(self):
        """🔴 RED: add_permission should add a single permission to existing permissions."""
        role_id = uuid4()
        existing_role = Role(
            id=role_id,
            name="test_role",
            description="",
            permissions=("document:read",),
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        updated_role = Role(
            id=role_id,
            name="test_role",
            description="",
            permissions=("document:read", "document:write"),
            is_system_reserved=False,
            is_active=True,
            created_at=existing_role.created_at,
            updated_at=datetime.now(UTC),
        )
        self.mock_repo.get_by_id.return_value = existing_role
        self.mock_repo.save.return_value = updated_role

        result = await self.service.add_permission(role_id, "document:write")

        assert "document:write" in result.permissions
