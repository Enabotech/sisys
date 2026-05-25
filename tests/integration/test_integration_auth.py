"""Tests for Auth Service Integration - End-to-End Flow.

Integration tests verifying complete authentication and authorization flow.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.application.use_cases.permission_management import PermissionService
from src.application.use_cases.role_management import RoleService
from src.domain.entities.role import Role
from src.domain.ports.role_repository import RoleRepositoryPort
from src.domain.ports.user_role_repository import UserRoleRepositoryPort


class MockRoleRepository(RoleRepositoryPort):
    """Mock implementation of RoleRepositoryPort for testing."""

    def __init__(self) -> None:
        self._roles: dict[str, Role] = {}

    async def get_by_id(self, role_id):
        for role in self._roles.values():
            if role.id == role_id:
                return role
        return None

    async def get_by_name(self, name: str) -> Role | None:
        return self._roles.get(name)

    async def list_all(self) -> list[Role]:
        return list(self._roles.values())

    async def save(self, role: Role) -> Role:
        from dataclasses import replace

        if role.id is None:
            new_role = replace(role, id=uuid4())
            self._roles[new_role.name] = new_role
            return new_role
        self._roles[role.name] = role
        return role

    async def delete(self, role_id) -> bool:
        for name, role in self._roles.items():
            if role.id == role_id:
                del self._roles[name]
                return True
        return False


class MockUserRoleRepository(UserRoleRepositoryPort):
    """Mock implementation of UserRoleRepositoryPort for testing."""

    def __init__(self) -> None:
        self._user_roles: dict[UUID, list[Role]] = {}
        self._role_repo = None

    def set_role_repo(self, role_repo):
        self._role_repo = role_repo

    async def assign_role(self, user_id, role_id) -> bool:
        if user_id not in self._user_roles:
            self._user_roles[user_id] = []
        # Find the role by ID and add it
        if self._role_repo:
            for role in await self._role_repo.list_all():
                if role.id == role_id:
                    self._user_roles[user_id].append(role)
                    break
        return True

    async def revoke_role(self, user_id, role_id) -> bool:
        if user_id in self._user_roles:
            self._user_roles[user_id] = [r for r in self._user_roles[user_id] if r.id != role_id]
        return True

    async def get_user_roles(self, user_id) -> list[Role]:
        return self._user_roles.get(user_id, [])

    async def get_role_users(self, role_id) -> list[UUID]:
        result = []
        for uid, roles in self._user_roles.items():
            if any(r.id == role_id for r in roles):
                result.append(uid)
        return result


class TestAuthIntegrationFlow:
    """Integration tests for complete auth flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.role_repo = MockRoleRepository()
        self.user_role_repo = MockUserRoleRepository()
        self.user_role_repo.set_role_repo(self.role_repo)
        self.role_service = RoleService(self.role_repo)
        self.permission_service = PermissionService(
            self.user_role_repo,
            self.role_repo,
        )

    async def test_complete_auth_flow(self):
        """🔴 Integration: Complete auth flow from login to resource access."""
        # Step 1: Create roles
        admin_role = await self.role_service.create_role(
            name="admin",
            permissions=["*:*"],
            description="Administrator",
            is_system_reserved=True,
        )

        viewer_role = await self.role_service.create_role(
            name="viewer",
            permissions=["document:read"],
            description="Viewer role",
        )

        # Step 2: Verify roles created
        roles = await self.role_service.list_roles()
        assert len(roles) == 2

        # Step 3: Assign role to user
        user_id = uuid4()
        await self.user_role_repo.assign_role(user_id, admin_role.id)
        await self.user_role_repo.assign_role(user_id, viewer_role.id)

        # Step 4: Verify user permissions
        perms = await self.permission_service.get_user_permissions(user_id)
        assert len(perms) >= 2

        # Step 5: Check permission
        has_access = await self.permission_service.check_permission(user_id, "document", "read")
        assert has_access is True

    async def test_role_management_flow(self):
        """🔴 Integration: Role CRUD flow."""
        # Create role
        role = await self.role_service.create_role(
            name="editor",
            permissions=["document:read", "document:write"],
            description="Editor role",
        )
        assert role.name == "editor"

        # Get role
        retrieved = await self.role_service.get_role(role.id)
        assert retrieved is not None
        assert retrieved.name == "editor"

        # Update role
        updated = await self.role_service.update_role(
            role.id,
            permissions=["document:read", "document:write", "document:delete"],
        )
        assert "document:delete" in updated.permissions

        # Delete role
        deleted = await self.role_service.delete_role(role.id)
        assert deleted is True

        # Verify deleted - should raise RoleNotFoundError
        from src.application.use_cases.role_management import RoleNotFoundError

        with pytest.raises(RoleNotFoundError):
            await self.role_service.get_role(role.id)

    async def test_privilege_escalation_blocked(self):
        """🔴 Integration: Privilege escalation attempt blocked."""
        # Create regular user role (no wildcard permissions)
        user_role = await self.role_service.create_role(
            name="user",
            permissions=["document:read"],
            description="Regular user",
        )

        # Create privileged role (not assigned to any user, just for testing)
        await self.role_service.create_role(
            name="admin",
            permissions=["*:*"],
            description="Admin",
            is_system_reserved=True,
        )

        # Assign regular role to user
        user_id = uuid4()
        await self.user_role_repo.assign_role(user_id, user_role.id)

        # User should NOT have admin permission
        has_admin = await self.permission_service.check_permission(user_id, "role", "admin")
        assert has_admin is False

        # User should have basic read permission
        has_read = await self.permission_service.check_permission(user_id, "document", "read")
        assert has_read is True


class TestPermissionFlow:
    """Integration tests for permission checking flow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.role_repo = MockRoleRepository()
        self.user_role_repo = MockUserRoleRepository()
        self.user_role_repo.set_role_repo(self.role_repo)
        self.role_service = RoleService(self.role_repo)
        self.permission_service = PermissionService(
            self.user_role_repo,
            self.role_repo,
        )

    async def test_permission_check_with_wildcard(self):
        """🔴 Integration: Wildcard permission grants access to matching actions."""
        # Create role with wildcard
        wildcard_role = await self.role_service.create_role(
            name="superuser",
            permissions=["document:*"],
            description="Can do anything with documents",
        )

        user_id = uuid4()
        await self.user_role_repo.assign_role(user_id, wildcard_role.id)

        # Should have access to any document action
        for action in ["read", "write", "delete", "execute"]:
            has_perm = await self.permission_service.check_permission(user_id, "document", action)
            assert has_perm is True

    async def test_permission_denied_without_role(self):
        """🔴 Integration: User without role has no permissions."""
        user_id = uuid4()
        # No roles assigned

        has_perm = await self.permission_service.check_permission(user_id, "document", "read")
        assert has_perm is False

    async def test_multiple_roles_combined(self):
        """🔴 Integration: Permissions from multiple roles are combined."""
        role1 = await self.role_service.create_role(
            name="reader",
            permissions=["document:read"],
            description="Can read documents",
        )

        role2 = await self.role_service.create_role(
            name="writer",
            permissions=["document:write"],
            description="Can write documents",
        )

        user_id = uuid4()
        await self.user_role_repo.assign_role(user_id, role1.id)
        await self.user_role_repo.assign_role(user_id, role2.id)

        # User should have both read and write
        has_read = await self.permission_service.check_permission(user_id, "document", "read")
        has_write = await self.permission_service.check_permission(user_id, "document", "write")
        assert has_read is True
        assert has_write is True
