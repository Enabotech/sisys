"""Port contract tests for HashRouter port.

Tests that HashRouter implementation satisfies the HashRouterProtocol.
"""

from __future__ import annotations

from src.composition_root import bootstrap
from src.domain.ports.hash_router_protocol import HashRouterProtocol
from src.domain.ports.registry import _global_registry

bootstrap()


class TestHashRouterContract:
    """Contract tests for HashRouter port."""

    @classmethod
    def get_port_name(cls) -> str:
        return "hash_router"

    @classmethod
    def get_implementation(cls) -> type:
        """Get the registered implementation class."""
        from src.domain.ports.resolver import Resolver

        resolver = Resolver()
        return resolver.resolve("hash_router")  # type: ignore[no-any-return]

    def test_port_is_registered(self) -> None:
        """Port must be registered in global registry."""
        spec = _global_registry.get(self.get_port_name())
        assert spec is not None, f"Port {self.get_port_name()} not registered"
        assert spec.interface is HashRouterProtocol

    def test_implementation_has_required_methods(self) -> None:
        """Implementation must have all required methods from protocol."""
        impl = self.get_implementation()
        required_methods = ["add_node", "remove_node", "route"]
        for method in required_methods:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"
