"""Port contract tests for UserRepository port.

Tests that user repository implementation satisfies the UserRepositoryPort.
重构说明: 使用 tests/contracts/conftest.py 的公共 fixture (registry, resolver)
"""

from __future__ import annotations

from src.domain.ports.user_repository import UserRepositoryPort


class TestUserRepositoryContract:
    """Contract tests for UserRepository port."""

    PORT_NAME = "user_repo"
    INTERFACE = UserRepositoryPort
    REQUIRED_METHODS = ["get_by_id", "get_by_username"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_interface_has_required_methods(self) -> None:
        """Interface must have core query methods."""
        for method in self.REQUIRED_METHODS:
            assert hasattr(self.INTERFACE, method), f"Interface missing method: {method}"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version, "Port version is empty"
        assert spec.owner, "Port owner is empty"
        assert spec.module, "Port module is empty"
