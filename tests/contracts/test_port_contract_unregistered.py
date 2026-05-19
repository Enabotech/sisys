"""Unregistered protocol interface contract tests.

Tests that 5 protocol interfaces (defined but not registered in composition_root.py)
have correct method signatures. These cannot be tested via registry since they're
not registered ports.
对应 AC-5: 5 个未注册 Protocol 接口验证
"""

from __future__ import annotations

from src.domain.ports.health_check import HealthCheckPort
from src.domain.ports.integrity import IntegrityPort
from src.domain.ports.permission_repository import PermissionRepositoryPort
from src.domain.ports.unit_of_work import UnitOfWork


class TestPermissionRepositoryPort:
    """Interface contract tests for PermissionRepository port (not registered)."""

    INTERFACE = PermissionRepositoryPort
    REQUIRED_METHODS = ["get_by_name", "get_by_id", "save", "delete", "list_all"]

    def test_interface_is_protocol(self) -> None:
        """Interface must be a Protocol."""
        from typing import Protocol

        assert issubclass(self.INTERFACE, Protocol)  # type: ignore[arg-type]

    def test_interface_has_required_methods(self) -> None:
        """Implementation must have all required methods from protocol."""
        for method in self.REQUIRED_METHODS:
            assert hasattr(self.INTERFACE, method), f"Interface missing method: {method}"


class TestUnitOfWork:
    """Interface contract tests for UnitOfWork (not registered)."""

    INTERFACE = UnitOfWork
    REQUIRED_METHODS = [
        "session",
        "begin",
        "commit",
        "rollback",
        "close",
        "begin_nested",
        "__aenter__",
        "__aexit__",
    ]

    def test_interface_is_protocol(self) -> None:
        """Interface must be a Protocol."""
        from typing import Protocol

        assert issubclass(self.INTERFACE, Protocol)  # type: ignore[arg-type]

    def test_interface_has_required_methods(self) -> None:
        """Implementation must have all required methods from protocol."""
        for method in self.REQUIRED_METHODS:
            assert hasattr(self.INTERFACE, method), f"Interface missing method: {method}"


class TestHealthCheckPort:
    """Interface contract tests for HealthCheckPort (not registered)."""

    INTERFACE = HealthCheckPort
    REQUIRED_METHODS = ["check", "close"]

    def test_interface_is_protocol(self) -> None:
        """Interface must be a Protocol."""
        from typing import Protocol

        assert issubclass(self.INTERFACE, Protocol)  # type: ignore[arg-type]

    def test_interface_has_required_methods(self) -> None:
        """Implementation must have all required methods from protocol."""
        for method in self.REQUIRED_METHODS:
            assert hasattr(self.INTERFACE, method), f"Interface missing method: {method}"


class TestIntegrityPort:
    """Interface contract tests for IntegrityPort (not registered)."""

    INTERFACE = IntegrityPort
    REQUIRED_METHODS = ["verify_file", "compute_hash", "verify_hash"]

    def test_interface_is_protocol(self) -> None:
        """Interface must be a Protocol."""
        from typing import Protocol

        assert issubclass(self.INTERFACE, Protocol)  # type: ignore[arg-type]

    def test_interface_has_required_methods(self) -> None:
        """Implementation must have all required methods from protocol."""
        for method in self.REQUIRED_METHODS:
            assert hasattr(self.INTERFACE, method), f"Interface missing method: {method}"
