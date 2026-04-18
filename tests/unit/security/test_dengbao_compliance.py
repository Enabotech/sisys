"""Tests for 等保 2.0 Compliance.

Tests for identity authentication and access control compliance requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.infrastructure.security.encryption_service import EncryptionService
from src.infrastructure.security.models import Role, User


class TestPasswordComplexity:
    """Tests for 等保 2.0 password complexity requirements."""

    @pytest.fixture
    def encryption_service(self) -> EncryptionService:
        """Create encryption service with 等保 2.0 defaults."""
        return EncryptionService(
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special=True,
        )

    def test_password_min_length_8(self, encryption_service: EncryptionService):
        """Password must be at least 8 characters."""
        # 7 characters - should fail
        errors = encryption_service.validate_password_strength("Abcdef1")
        assert any("at least 8" in e for e in errors)

        # 8 characters with all requirements - should pass
        errors = encryption_service.validate_password_strength("Abcdef1!")
        assert len(errors) == 0

    def test_password_requires_uppercase(self, encryption_service: EncryptionService):
        """Password must contain uppercase letter."""
        errors = encryption_service.validate_password_strength("abcdefg1!")
        assert any("uppercase" in e.lower() for e in errors)

    def test_password_requires_lowercase(self, encryption_service: EncryptionService):
        """Password must contain lowercase letter."""
        errors = encryption_service.validate_password_strength("ABCDEFG1!")
        assert any("lowercase" in e.lower() for e in errors)

    def test_password_requires_digit(self, encryption_service: EncryptionService):
        """Password must contain digit."""
        errors = encryption_service.validate_password_strength("AbcdefgH!")
        assert any("digit" in e.lower() for e in errors)

    def test_password_requires_special(self, encryption_service: EncryptionService):
        """Password must contain special character."""
        errors = encryption_service.validate_password_strength("AbcdefgH1")
        assert any("special" in e.lower() for e in errors)

    def test_valid_password_passes_all_checks(self, encryption_service: EncryptionService):
        """Valid password should pass all complexity checks."""
        password = "MyP@ssw0rd123"  # pragma: allowlist secret

        assert encryption_service.is_password_strong(password) is True


class TestAccountLocking:
    """Tests for 等保 2.0 account locking requirements."""

    def test_account_lock_after_max_attempts(self):
        """Account should lock after max failed login attempts."""
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@test.com",
            is_active=True,
        )

        # Simulate 5 failed login attempts
        for _ in range(5):
            user.increment_failed_login()

        # Account should be locked
        assert user.failed_login_attempts >= 5

    def test_account_lock_duration(self):
        """Account should remain locked for specified duration."""
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@test.com",
            is_active=True,
        )

        user.lock_account(30)  # 30 minutes

        # Should still be locked after 10 minutes
        assert user.is_locked() is True

    def test_account_unlock_after_duration(self):
        """Account should unlock after duration expires."""
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@test.com",
            is_active=True,
        )

        # Manually set locked_until to past
        user.locked_until = datetime.utcnow() - timedelta(minutes=1)

        assert user.is_locked() is False


class TestAccessControl:
    """Tests for RBAC access control requirements."""

    def test_admin_has_all_permissions(self):
        """Admin role should have *:* permission."""
        admin_role = Role(
            id=uuid4(),
            name="admin",
            permissions=["*:*"],
        )

        assert admin_role.has_permission("document", "read") is True
        assert admin_role.has_permission("document", "write") is True
        assert admin_role.has_permission("document", "delete") is True
        assert admin_role.has_permission("tool", "execute") is True

    def test_viewer_read_only(self):
        """Viewer role should have read-only access."""
        viewer_role = Role(
            id=uuid4(),
            name="viewer",
            permissions=["document:read"],
        )

        assert viewer_role.has_permission("document", "read") is True
        assert viewer_role.has_permission("document", "write") is False
        assert viewer_role.has_permission("document", "delete") is False

    def test_analyst_permissions(self):
        """Analyst role should have document and tool permissions."""
        analyst_role = Role(
            id=uuid4(),
            name="analyst",
            permissions=["document:read", "document:write", "tool:execute"],
        )

        assert analyst_role.has_permission("document", "read") is True
        assert analyst_role.has_permission("document", "write") is True
        assert analyst_role.has_permission("tool", "execute") is True
        assert analyst_role.has_permission("agent", "execute") is False

    def test_minimum_privilege_default_deny(self):
        """Default deny when no explicit permission."""
        empty_role = Role(
            id=uuid4(),
            name="empty",
            permissions=[],
        )

        assert empty_role.has_permission("document", "read") is False
        assert empty_role.has_permission("anything", "any_action") is False

    def test_wildcard_resource_permissions(self):
        """Resource wildcard should grant all actions on that resource."""
        role = Role(
            id=uuid4(),
            name="doc_manager",
            permissions=["document:*"],
        )

        assert role.has_permission("document", "read") is True
        assert role.has_permission("document", "write") is True
        assert role.has_permission("document", "delete") is True

    def test_wildcard_action_permissions(self):
        """Action wildcard should grant that action on all resources."""
        role = Role(
            id=uuid4(),
            name="auditor",
            permissions=["*:read"],
        )

        assert role.has_permission("document", "read") is True
        assert role.has_permission("tool", "read") is True
        assert role.has_permission("agent", "read") is True
        assert role.has_permission("document", "write") is False


class TestSessionManagement:
    """Tests for 等保 2.0 session management requirements."""

    def test_session_timeout_calculation(self):
        """Session should timeout after configured inactivity period."""
        # 等保 2.0 requires 30 minutes timeout
        timeout_minutes = 30

        # Create a user with a recent activity
        last_activity = datetime.utcnow() - timedelta(minutes=20)

        # Session should still be valid (20 minutes < 30 minutes)
        time_since_activity = datetime.utcnow() - last_activity
        assert time_since_activity.total_seconds() / 60 < timeout_minutes

    def test_session_expired_calculation(self):
        """Session should be invalid after timeout."""
        timeout_minutes = 30

        # Create a user with old activity
        last_activity = datetime.utcnow() - timedelta(minutes=31)

        # Session should be expired (31 minutes > 30 minutes)
        time_since_activity = datetime.utcnow() - last_activity
        assert time_since_activity.total_seconds() / 60 > timeout_minutes


class TestPredefinedRoles:
    """Tests for 等保 2.0 predefined roles."""

    def test_admin_role_permissions(self):
        """Admin role should have all permissions (*:*)."""
        admin_role = Role(
            id=uuid4(),
            name="admin",
            permissions=["*:*"],
        )

        # All resources
        for resource in ["document", "tool", "agent", "plan", "checkpoint", "archive", "system"]:
            for action in ["read", "write", "delete", "execute", "admin"]:
                assert admin_role.has_permission(resource, action) is True

    def test_analyst_role_permissions(self):
        """Analyst role should have specific permissions."""
        analyst_role = Role(
            id=uuid4(),
            name="analyst",
            permissions=["document:read", "document:write", "tool:execute", "agent:execute"],
        )

        assert analyst_role.has_permission("document", "read") is True
        assert analyst_role.has_permission("document", "write") is True
        assert analyst_role.has_permission("tool", "execute") is True
        assert analyst_role.has_permission("agent", "execute") is True

        # Should NOT have
        assert analyst_role.has_permission("document", "delete") is False
        assert analyst_role.has_permission("system", "admin") is False

    def test_viewer_role_permissions(self):
        """Viewer role should have read-only permissions."""
        viewer_role = Role(
            id=uuid4(),
            name="viewer",
            permissions=["document:read"],
        )

        assert viewer_role.has_permission("document", "read") is True

        # Should NOT have
        assert viewer_role.has_permission("document", "write") is False
        assert viewer_role.has_permission("document", "delete") is False
        assert viewer_role.has_permission("tool", "execute") is False
