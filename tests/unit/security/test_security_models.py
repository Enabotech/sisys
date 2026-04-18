"""Tests for Security Models (Role, Permission, User value objects).

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.infrastructure.security.models import Permission, Role, User


class TestPermission:
    """Permission value object tests."""

    def test_permission_string_format(self):
        """Should create permission with correct string format."""
        permission_id = uuid4()
        permission = Permission(
            id=permission_id,
            resource="document",
            action="read",
        )

        assert permission.permission_string == "document:read"

    def test_permission_from_string(self):
        """Should create permission from string format."""
        permission = Permission.from_string("document:write")

        assert permission.resource == "document"
        assert permission.action == "write"

    def test_permission_from_string_invalid(self):
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError):
            Permission.from_string("invalid_format")

    def test_permission_equality(self):
        """Should be equal when resource and action match."""
        perm1 = Permission.from_string("document:read", uuid4())
        perm2 = Permission.from_string("document:read", uuid4())

        assert perm1.resource == perm2.resource
        assert perm1.action == perm2.action


class TestRole:
    """Role value object tests."""

    @pytest.fixture
    def admin_role(self) -> Role:
        """Create admin role with all permissions."""
        return Role(
            id=uuid4(),
            name="admin",
            permissions=["*:*"],
        )

    @pytest.fixture
    def analyst_role(self) -> Role:
        """Create analyst role with specific permissions."""
        return Role(
            id=uuid4(),
            name="analyst",
            permissions=["document:read", "document:write", "tool:execute"],
        )

    def test_role_has_permission_wildcard_all(self, admin_role: Role):
        """Admin role should have all permissions via wildcard."""
        assert admin_role.has_permission("document", "read") is True
        assert admin_role.has_permission("tool", "execute") is True
        assert admin_role.has_permission("any_resource", "any_action") is True

    def test_role_has_permission_exact_match(self, analyst_role: Role):
        """Should match exact permission."""
        assert analyst_role.has_permission("document", "read") is True
        assert analyst_role.has_permission("document", "write") is True

    def test_role_has_permission_no_match(self, analyst_role: Role):
        """Should return False when permission not granted."""
        assert analyst_role.has_permission("document", "delete") is False
        assert analyst_role.has_permission("tool", "read") is False

    def test_role_has_permission_resource_wildcard(self):
        """Should match resource wildcard permission."""
        role = Role(
            id=uuid4(),
            name="document_admin",
            permissions=["document:*"],
        )

        assert role.has_permission("document", "read") is True
        assert role.has_permission("document", "write") is True
        assert role.has_permission("document", "delete") is True
        assert role.has_permission("tool", "read") is False

    def test_role_has_permission_action_wildcard(self):
        """Should match action wildcard permission."""
        role = Role(
            id=uuid4(),
            name="all_readers",
            permissions=["*:read"],
        )

        assert role.has_permission("document", "read") is True
        assert role.has_permission("tool", "read") is True
        assert role.has_permission("document", "write") is False

    def test_role_add_permission(self, analyst_role: Role):
        """Should add permission to role."""
        analyst_role.add_permission("agent:execute")

        assert "agent:execute" in analyst_role.permissions

    def test_role_add_permission_duplicate(self, analyst_role: Role):
        """Should not add duplicate permission."""
        initial_count = len(analyst_role.permissions)
        analyst_role.add_permission("document:read")

        assert len(analyst_role.permissions) == initial_count

    def test_role_remove_permission(self, analyst_role: Role):
        """Should remove permission from role."""
        analyst_role.remove_permission("document:read")

        assert "document:read" not in analyst_role.permissions

    def test_role_remove_permission_not_found(self, analyst_role: Role):
        """Should not error when removing non-existent permission."""
        initial_count = len(analyst_role.permissions)
        analyst_role.remove_permission("nonexistent:permission")

        assert len(analyst_role.permissions) == initial_count


class TestUser:
    """User value object tests."""

    @pytest.fixture
    def user(self) -> User:
        """Create test user."""
        return User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_secret",  # pragma: allowlist secret
            is_active=True,
            roles=["analyst"],
        )

    def test_user_is_locked_false_when_not_locked(self, user: User):
        """Should return False when locked_until is None."""
        assert user.is_locked() is False

    def test_user_is_locked_true_when_future(self, user: User):
        """Should return True when locked_until is in future."""
        user.locked_until = datetime.utcnow() + timedelta(minutes=30)

        assert user.is_locked() is True

    def test_user_is_locked_false_when_past(self, user: User):
        """Should return False when locked_until is in past."""
        user.locked_until = datetime.utcnow() - timedelta(minutes=1)

        assert user.is_locked() is False

    def test_user_increment_failed_login(self, user: User):
        """Should increment failed login counter."""
        initial = user.failed_login_attempts
        user.increment_failed_login()

        assert user.failed_login_attempts == initial + 1

    def test_user_reset_failed_login(self, user: User):
        """Should reset failed login counter."""
        user.failed_login_attempts = 5
        user.reset_failed_login()

        assert user.failed_login_attempts == 0

    def test_user_lock_account(self, user: User):
        """Should lock account for specified duration."""
        user.lock_account(30)

        assert user.locked_until is not None
        assert user.is_locked() is True
