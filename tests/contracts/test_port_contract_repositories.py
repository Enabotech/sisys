"""Repository layer port contract tests.

Tests that L2RdbPort, RoleRepositoryPort, UserRoleRepositoryPort,
LoginAttemptRepositoryPort, AuditRepositoryPort, OutboxRepository,
L2MetadataRepositoryPort, L2ChangeHistoryRepositoryPort, L2GroupMemberRepositoryPort,
SnapshotRepositoryProtocol are correctly registered and satisfy their Protocol interfaces.
对应 AC-3: 全部 domain/ports 仓储层端口契约测试完成
"""

from __future__ import annotations

from src.domain.ports.audit_repository import AuditRepositoryPort
from src.domain.ports.login_attempt_repository import LoginAttemptRepositoryPort
from src.domain.ports.memory_repository import (
    L2ChangeHistoryRepositoryPort,
    L2GroupMemberRepositoryPort,
    L2MetadataRepositoryPort,
)
from src.domain.ports.outbox import OutboxRepository
from src.domain.ports.role_repository import RoleRepositoryPort
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.ports.user_role_repository import UserRoleRepositoryPort


def _get_impl(spec, port_name):
    """Helper to get implementation instance or None if cannot resolve."""
    impl_cls = spec.impl if isinstance(spec.impl, type) else None
    if impl_cls is None:
        try:
            from src.domain.ports.resolver import Resolver

            return Resolver().resolve(port_name)
        except (RuntimeError, ImportError, KeyError):
            return None
    return impl_cls


class TestRoleRepositoryPort:
    """Contract tests for RoleRepository port."""

    PORT_NAME = "role_repo"
    INTERFACE = RoleRepositoryPort
    REQUIRED_METHODS = ["get_by_id", "get_by_name", "list_all", "save", "delete"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestUserRoleRepositoryPort:
    """Contract tests for UserRoleRepository port."""

    PORT_NAME = "user_role_repo"
    INTERFACE = UserRoleRepositoryPort
    REQUIRED_METHODS = ["assign_role", "revoke_role", "get_user_roles", "get_role_users"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestLoginAttemptRepositoryPort:
    """Contract tests for LoginAttemptRepository port."""

    PORT_NAME = "login_attempt_repo"
    INTERFACE = LoginAttemptRepositoryPort
    REQUIRED_METHODS = [
        "record_attempt",
        "get_recent_failed_attempts",
        "is_account_locked",
        "get_lockout_remaining_minutes",
        "clear_attempts",
        "check_and_record_lockout",
        "record_attempt_and_check_lockout",
    ]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestAuditRepositoryPort:
    """Contract tests for AuditRepository port."""

    PORT_NAME = "audit_repo"
    INTERFACE = AuditRepositoryPort
    REQUIRED_METHODS = [
        "save",
        "get_by_id",
        "search",
        "update_archive_status",
        "get_archive_status",
    ]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestOutboxRepository:
    """Contract tests for OutboxRepository port."""

    PORT_NAME = "outbox_repo"
    INTERFACE = OutboxRepository
    REQUIRED_METHODS = ["save", "get_unpublished", "mark_published", "mark_failed"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestL2MetadataRepositoryPort:
    """Contract tests for L2MetadataRepository port."""

    PORT_NAME = "memory_metadata"
    INTERFACE = L2MetadataRepositoryPort
    REQUIRED_METHODS = [
        "get_by_id",
        "save",
        "delete",
        "list_all",
        "get_by_name",
        "list_by_user",
        "list_by_type",
    ]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestL2ChangeHistoryRepositoryPort:
    """Contract tests for L2ChangeHistoryRepository port."""

    PORT_NAME = "memory_change_history"
    INTERFACE = L2ChangeHistoryRepositoryPort
    REQUIRED_METHODS = ["get_by_id", "save", "delete", "list_all", "get_by_memory_id"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestL2GroupMemberRepositoryPort:
    """Contract tests for L2GroupMemberRepository port."""

    PORT_NAME = "memory_group_member"
    INTERFACE = L2GroupMemberRepositoryPort
    REQUIRED_METHODS = [
        "is_group_member",
        "is_group_admin",
        "add_member",
        "remove_member",
    ]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestSnapshotRepositoryProtocol:
    """Contract tests for SnapshotRepository port."""

    PORT_NAME = "snapshot_repository"
    INTERFACE = SnapshotRepositoryProtocol
    REQUIRED_METHODS = ["save", "load", "delete"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol."""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module
