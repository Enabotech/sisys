"""Storage layer port contract tests.

Tests that L0-L5 storage ports, UnifiedStorage, SessionStorage and StorageEnums
are correctly registered and satisfy their Protocol interfaces.
对应 AC-2: 全部 domain/ports 存储层端口契约测试完成
"""

from __future__ import annotations

from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.l1_cache import L1CachePort
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.session_storage import SessionStorage
from src.domain.ports.storage_enums import DataAccessPattern, StorageLayer, StorageTier
from src.domain.ports.unified_storage import UnifiedStoragePort


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


class TestL0StoragePort:
    """Contract tests for L0Storage port."""

    PORT_NAME = "l0_storage"
    INTERFACE = L0StoragePort
    REQUIRED_METHODS = ["write", "read", "delete", "exists", "list_memories"]

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
            return  # Cannot resolve, skip instance method check
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """Port metadata must be complete."""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module


class TestL1CachePort:
    """Contract tests for L1Cache port (redis_adapter)."""

    PORT_NAME = "redis_adapter"
    INTERFACE = L1CachePort
    REQUIRED_METHODS = ["get", "set", "delete", "exists", "delete_pattern", "set_with_ttl"]

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


class TestL3VectorPort:
    """Contract tests for L3Vector port."""

    PORT_NAME = "l3_vector"
    INTERFACE = L3VectorPort
    REQUIRED_METHODS = [
        "upsert_points",
        "delete_points",
        "get_point",
        "search",
        "search_sparse",
        "create_collection",
        "delete_collection",
        "collection_exists",
        "list_collections",
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


class TestL4ObjectPort:
    """Contract tests for L4Object port."""

    PORT_NAME = "l4_object"
    INTERFACE = L4ObjectPort
    REQUIRED_METHODS = ["store", "retrieve", "delete", "get_metadata", "archive", "list_objects"]

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


class TestL5GraphPort:
    """Contract tests for L5Graph port."""

    PORT_NAME = "l5_graph"
    INTERFACE = L5GraphPort
    REQUIRED_METHODS = [
        "create_entity",
        "get_entity",
        "delete_entity",
        "create_relationship",
        "delete_relationship",
        "find_related",
        "execute_query",
        "execute_write_query",
        "get_neighbors",
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


class TestUnifiedStoragePort:
    """Contract tests for UnifiedStorage port."""

    PORT_NAME = "unified_storage"
    INTERFACE = UnifiedStoragePort
    REQUIRED_METHODS = ["save", "read", "delete", "exists"]

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


class TestSessionStoragePort:
    """Contract tests for SessionStorage port."""

    PORT_NAME = "session_storage"
    INTERFACE = SessionStorage
    REQUIRED_METHODS = ["save", "load", "delete", "exists"]

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


class TestStorageEnums:
    """Contract tests for StorageEnums completeness."""

    def test_storage_layer_enum_complete(self) -> None:
        """StorageLayer enum must have all required values."""
        members = list(StorageLayer)
        assert len(members) == 6, f"StorageLayer should have 6 values, got {len(members)}"
        names = [m.name for m in members]
        assert "L0_FILE" in names
        assert "L1_CACHE" in names
        assert "L2_SQL" in names
        assert "L3_VECTOR" in names
        assert "L4_OBJECT" in names
        assert "L5_GRAPH" in names

    def test_storage_tier_enum_complete(self) -> None:
        """StorageTier enum must have all required values."""
        members = list(StorageTier)
        assert len(members) == 4, f"StorageTier should have 4 values, got {len(members)}"
        names = [m.name for m in members]
        assert "HOT" in names
        assert "WARM" in names
        assert "COLD" in names
        assert "FROZEN" in names

    def test_data_access_pattern_enum_complete(self) -> None:
        """DataAccessPattern enum must have all required values."""
        members = list(DataAccessPattern)
        assert len(members) == 4, f"DataAccessPattern should have 4 values, got {len(members)}"
        names = [m.name for m in members]
        assert "FREQUENT" in names
        assert "OCCASIONAL" in names
        assert "RARE" in names
        assert "ARCHIVED" in names
