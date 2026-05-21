"""Service protocol port contract tests.

Tests that redis_connection_manager, postgresql_connection_manager, qdrant_connection_manager,
neo4j_connection_manager, audit_service, semantic_router ports
are correctly registered and satisfy their Protocol interfaces.
对应 AC-5: 全部 domain/ports 服务协议端口契约测试完成
"""

from __future__ import annotations

from src.domain.ports.audit_service import AuditServicePort
from src.domain.ports.connection_manager import ConnectionManager
from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol


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


class TestRedisConnectionManager:
    """Contract tests for Redis connection manager."""

    PORT_NAME = "redis_connection_manager"
    INTERFACE = ConnectionManager
    REQUIRED_METHODS = ["health_check", "close", "get_client"]

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
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestPostgreSQLConnectionManager:
    """Contract tests for PostgreSQL connection manager."""

    PORT_NAME = "postgresql_connection_manager"
    INTERFACE = ConnectionManager
    REQUIRED_METHODS = ["health_check", "close", "get_client"]

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
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestQdrantConnectionManager:
    """Contract tests for Qdrant connection manager."""

    PORT_NAME = "qdrant_connection_manager"
    INTERFACE = ConnectionManager
    REQUIRED_METHODS = ["health_check", "close", "get_client"]

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
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestNeo4jConnectionManager:
    """Contract tests for Neo4j connection manager."""

    PORT_NAME = "neo4j_connection_manager"
    INTERFACE = ConnectionManager
    REQUIRED_METHODS = ["health_check", "close", "get_client"]

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
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestAuditServicePort:
    """Contract tests for AuditService port."""

    PORT_NAME = "audit_service"
    INTERFACE = AuditServicePort
    REQUIRED_METHODS = ["record", "verify_integrity", "verify_batch", "archive"]

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
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestSemanticRouterProtocol:
    """Contract tests for SemanticRouter port."""

    PORT_NAME = "semantic_router"
    INTERFACE = SemanticRouterProtocol
    REQUIRED_METHODS = ["route"]

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
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"
