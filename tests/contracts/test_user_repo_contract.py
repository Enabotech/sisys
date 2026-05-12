"""Port contract tests for UserRepository port.

Tests that user repository implementation satisfies the UserRepositoryPort.
"""

from __future__ import annotations

from src.composition_root import bootstrap
from src.domain.ports.registry import _global_registry
from src.domain.ports.user_repository import UserRepositoryPort

bootstrap()


class TestUserRepositoryContract:
    """Contract tests for UserRepository port."""

    @classmethod
    def get_port_name(cls) -> str:
        return "user_repo"

    def test_port_is_registered(self) -> None:
        """Port must be registered in global registry."""
        spec = _global_registry.get(self.get_port_name())
        assert spec is not None, f"Port {self.get_port_name()} not registered"
        assert spec.interface is UserRepositoryPort

    def test_interface_has_required_methods(self) -> None:
        """Interface must have core query methods."""
        # Core query methods that the interface requires
        required_methods = ["get_by_id", "get_by_username"]
        for method in required_methods:
            assert hasattr(UserRepositoryPort, method), f"Interface missing method: {method}"
