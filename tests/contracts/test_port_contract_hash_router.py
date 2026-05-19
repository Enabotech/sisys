"""Port contract tests for HashRouter port.

Tests that HashRouter implementation satisfies the HashRouterProtocol.

重构说明: 使用 tests/contracts/conftest.py 的公共 fixture (registry, resolver)
"""

from __future__ import annotations

from src.domain.ports.hash_router_protocol import HashRouterProtocol


class TestHashRouterContract:
    """Contract tests for HashRouter port."""

    PORT_NAME = "hash_router"
    INTERFACE = HashRouterProtocol
    REQUIRED_METHODS = ["add_node", "remove_node", "route"]

    def test_port_is_registered(self, registry) -> None:
        """Port must be registered in global registry."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """Implementation must have all required methods from protocol.

        使用 spec.impl 类级别检查方法存在性，避免 resolver.resolve() 实例化
        （需要外部服务连接）
        """
        spec = registry.get(self.PORT_NAME)
        impl_cls = spec.impl if isinstance(spec.impl, type) else None
        if impl_cls is None:
            from src.domain.ports.resolver import Resolver

            impl = Resolver().resolve(self.PORT_NAME)
        else:
            impl = impl_cls
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version, "Port version is empty"
        assert spec.owner, "Port owner is empty"
        assert spec.module, "Port module is empty"
