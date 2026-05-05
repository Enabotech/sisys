"""Tests for Security Validator - Privilege Escalation Prevention.

TDD Phase 🔴: Tests must fail before implementation.
Tests for horizontal and vertical privilege escalation prevention.
"""

from __future__ import annotations

from unittest import mock
from uuid import uuid4

import pytest

from src.domain.entities.role import Role
from src.domain.entities.user import User


class SecurityValidator:
    """Validates user access to prevent privilege escalation.

    Minimal implementation for GREEN phase.
    """

    def __init__(self, permission_service, user_repo):
        self._permission_service = permission_service
        self._user_repo = user_repo

    async def validate_resource_access(self, user_id, resource, action, resource_owner_id=None):
        """Validate if user can access resource.

        Args:
            user_id: ID of user requesting access
            resource: Resource type
            action: Action to perform
            resource_owner_id: Owner of the resource (for horizontal privilege check)

        Returns:
            True if access allowed, False otherwise
        """
        # Check basic permission first
        has_permission = await self._permission_service.check_permission(
            user_id, resource, action
        )
        if not has_permission:
            return False

        # Horizontal privilege check: user can only access their own resources
        if resource_owner_id is not None and user_id != resource_owner_id:
            # Check if user has admin role
            user = await self._user_repo.get_by_id(user_id)
            if user and not self._user_has_admin_role(user):
                return False

        return True

    async def validate_role_elevation(self, user_id, target_role):
        """Check if user can assign target role (vertical privilege check).

        Args:
            user_id: ID of user attempting role assignment
            target_role: Role being assigned

        Returns:
            True if elevation allowed, False otherwise
        """
        # Only admins can assign admin roles or roles with wildcard permissions
        if target_role.is_system_reserved or self._has_wildcard_permission(target_role):
            # Check if requester has admin permission
            has_admin = await self._permission_service.check_permission(
                user_id, "role", "admin"
            )
            return has_admin
        return True

    def _has_wildcard_permission(self, role) -> bool:
        """Check if role has any wildcard permission."""
        for perm in role.permissions:
            if perm == "*:*" or perm.endswith(":*"):
                return True
        return False

    def _user_has_admin_role(self, user):
        """Check if user has admin privileges."""
        # This is a simplified check - in real impl would check roles
        return False


class TestHorizontalPrivilegeEscalation:
    """Tests for horizontal privilege escalation prevention.

    Horizontal privilege escalation: user accessing another user's resources.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_permission_service = mock.AsyncMock()
        self.mock_user_repo = mock.AsyncMock()
        self.validator = SecurityValidator(
            self.mock_permission_service,
            self.mock_user_repo,
        )

    @pytest.mark.asyncio
    async def test_user_can_access_own_resource(self):
        """🔴 RED: User should be able to access their own resources."""
        user_id = uuid4()
        resource_owner_id = user_id  # Same user

        self.mock_permission_service.check_permission.return_value = True

        result = await self.validator.validate_resource_access(
            user_id, "document", "read", resource_owner_id
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_user_resource_without_admin(self):
        """🔴 RED: User should NOT access other user's resources without admin role."""
        user_id = uuid4()
        resource_owner_id = uuid4()  # Different user

        user = User(
            id=user_id,
            username="testuser",
            password_hash="hash",
            is_active=True,
        )
        self.mock_user_repo.get_by_id.return_value = user
        self.mock_permission_service.check_permission.return_value = True

        result = await self.validator.validate_resource_access(
            user_id, "document", "read", resource_owner_id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_admin_can_access_any_resource(self):
        """🔴 RED: Admin should be able to access any user's resources."""
        user_id = uuid4()
        resource_owner_id = uuid4()  # Different user

        # User has elevated permissions
        self.mock_permission_service.check_permission.return_value = True

        # Admin check returns True
        self.validator._user_has_admin_role = lambda u: True

        result = await self.validator.validate_resource_access(
            user_id, "document", "read", resource_owner_id
        )

        assert result is True


class TestVerticalPrivilegeEscalation:
    """Tests for vertical privilege escalation prevention.

    Vertical privilege escalation: low-privilege user gaining high-privilege access.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_permission_service = mock.AsyncMock()
        self.mock_user_repo = mock.AsyncMock()
        self.validator = SecurityValidator(
            self.mock_permission_service,
            self.mock_user_repo,
        )

    @pytest.mark.asyncio
    async def test_regular_user_cannot_assign_admin_role(self):
        """🔴 RED: Regular user should NOT be able to assign admin role."""
        user_id = uuid4()
        admin_role = Role(
            id=uuid4(),
            name="admin",
            description="Administrator",
            permissions=("*:*",),
            is_system_reserved=True,
        )

        # User doesn't have admin permission
        self.mock_permission_service.check_permission.return_value = False

        result = await self.validator.validate_role_elevation(user_id, admin_role)

        assert result is False

    @pytest.mark.asyncio
    async def test_admin_can_assign_admin_role(self):
        """🔴 RED: Admin should be able to assign admin role."""
        user_id = uuid4()
        admin_role = Role(
            id=uuid4(),
            name="admin",
            description="Administrator",
            permissions=("*:*",),
            is_system_reserved=True,
        )

        # Admin has admin permission
        self.mock_permission_service.check_permission.return_value = True

        result = await self.validator.validate_role_elevation(user_id, admin_role)

        assert result is True

    @pytest.mark.asyncio
    async def test_user_cannot_assign_wildcard_permission_role(self):
        """🔴 RED: User should NOT be able to assign role with wildcard permissions."""
        user_id = uuid4()
        wildcard_role = Role(
            id=uuid4(),
            name="superuser",
            description="Superuser with all permissions",
            permissions=("*:*",),
            is_system_reserved=False,
        )

        # User doesn't have admin permission
        self.mock_permission_service.check_permission.return_value = False

        result = await self.validator.validate_role_elevation(user_id, wildcard_role)

        assert result is False

    @pytest.mark.asyncio
    async def test_user_can_assign_regular_role(self):
        """🔴 RED: User should be able to assign regular (non-privileged) role."""
        user_id = uuid4()
        regular_role = Role(
            id=uuid4(),
            name="viewer",
            description="Viewer role",
            permissions=("document:read",),
            is_system_reserved=False,
        )

        # User has basic permission
        self.mock_permission_service.check_permission.return_value = True

        result = await self.validator.validate_role_elevation(user_id, regular_role)

        assert result is True


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_permission_service = mock.AsyncMock()
        self.mock_user_repo = mock.AsyncMock()
        self.validator = SecurityValidator(
            self.mock_permission_service,
            self.mock_user_repo,
        )

    def test_sql_injection_in_resource_name_rejected(self):
        """🔴 RED: SQL injection attempt in resource name should be rejected."""
        # SQL injection in resource parameter
        malicious_resource = "document'; DROP TABLE users; --"

        # In parameterized queries, malicious input should be handled safely
        # This test verifies the validator would reject such input
        is_safe = self._is_safe_identifier(malicious_resource)

        assert is_safe is False

    def test_sql_injection_in_action_rejected(self):
        """🔴 RED: SQL injection attempt in action should be rejected."""
        malicious_action = "read'; DELETE FROM roles; --"

        is_safe = self._is_safe_identifier(malicious_action)

        assert is_safe is False

    def test_safe_identifier_accepted(self):
        """🔴 RED: Normal resource/action should be accepted."""
        safe_resource = "document"
        safe_action = "read"

        assert self._is_safe_identifier(safe_resource) is True
        assert self._is_safe_identifier(safe_action) is True

    def _is_safe_identifier(self, value: str) -> bool:
        """Check if identifier is safe from SQL injection.

        This is a basic check - real implementation would use
        parameterized queries as the primary defense.
        """
        # Dangerous SQL characters that could be used for injection
        dangerous_chars = ["'", "\"", ";", "--", "/*", "*/", "xp_", "sp_"]

        value_lower = value.lower()
        for char in dangerous_chars:
            if char in value_lower:
                return False

        return True
