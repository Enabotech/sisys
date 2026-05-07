"""Unit tests for Role domain entity."""

from __future__ import annotations

import uuid

from src.domain.entities.role import Role


class TestRoleHasPermission:
    """Test Role.has_permission method."""

    def test_exact_permission_match(self) -> None:
        """Should return True when permission exactly matches."""
        role = Role(
            id=uuid.uuid4(),
            name="editor",
            permissions=("document:read", "document:write"),
        )
        assert role.has_permission("document:read") is True
        assert role.has_permission("document:write") is True

    def test_exact_permission_no_match(self) -> None:
        """Should return False when permission doesn't match."""
        role = Role(
            id=uuid.uuid4(),
            name="viewer",
            permissions=("document:read",),
        )
        assert role.has_permission("document:write") is False

    def test_wildcard_all_permissions(self) -> None:
        """Should return True for any permission when *:* is granted."""
        role = Role(
            id=uuid.uuid4(),
            name="admin",
            permissions=("*:*",),
        )
        assert role.has_permission("document:read") is True
        assert role.has_permission("system:admin") is True
        assert role.has_permission("anything:at:all") is True

    def test_wildcard_resource_match(self) -> None:
        """Should match wildcard resource with specific action."""
        role = Role(
            id=uuid.uuid4(),
            name="doc-admin",
            permissions=("document:*",),
        )
        assert role.has_permission("document:read") is True
        assert role.has_permission("document:write") is True
        assert role.has_permission("document:delete") is True
        assert role.has_permission("other:read") is False

    def test_wildcard_action_match(self) -> None:
        """Should match wildcard action with specific resource."""
        role = Role(
            id=uuid.uuid4(),
            name="reader",
            permissions=("*:read",),
        )
        assert role.has_permission("document:read") is True
        assert role.has_permission("system:read") is True
        assert role.has_permission("document:write") is False

    def test_permission_without_colon(self) -> None:
        """Should handle permission without colon."""
        role = Role(
            id=uuid.uuid4(),
            name="simple",
            permissions=("read",),
        )
        # When no colon in permission, splits on empty string
        assert role.has_permission("read") is True

    def test_empty_permissions(self) -> None:
        """Should return False when role has no permissions."""
        role = Role(
            id=uuid.uuid4(),
            name="empty",
            permissions=(),
        )
        assert role.has_permission("document:read") is False
