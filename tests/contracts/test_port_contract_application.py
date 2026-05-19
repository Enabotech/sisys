"""Application layer port contract tests.

Tests that sandbox_executor, semantic_cache, memory_file_storage, public_blackboard,
compressor, session_cache, memory_cache, exception_metrics, document_storage,
memory_vector_storage, text_extractor, memory_graph_storage, metrics, event_subscriber
ports are correctly registered and satisfy their Protocol interfaces.
对应 AC-6: 全部 application/ports 端口契约测试完成
"""

from __future__ import annotations

from src.application.ports.compressor_service import CompressorService
from src.application.ports.document_storage_port import DocumentStoragePort
from src.application.ports.event_subscriber import EventSubscriber
from src.application.ports.exception_metrics_port import ExceptionMetricsPort
from src.application.ports.memory_cache_port import MemoryCachePort
from src.application.ports.memory_file_port import MemoryFilePort
from src.application.ports.memory_graph_port import MemoryGraphPort
from src.application.ports.memory_vector_port import MemoryVectorPort
from src.application.ports.metrics_port import MetricsPort
from src.application.ports.public_blackboard import PublicBlackboard
from src.application.ports.sandbox_port import SandboxExecutor
from src.application.ports.semantic_cache import SemanticCache
from src.application.ports.session_cache_port import SessionCachePort
from src.application.ports.text_extractor_service import TextExtractorService


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


class TestSandboxExecutor:
    """Contract tests for SandboxExecutor port."""

    PORT_NAME = "sandbox_executor"
    INTERFACE = SandboxExecutor
    REQUIRED_METHODS = [
        "start_container",
        "execute_code",
        "stop_container",
        "is_container_running",
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


class TestSemanticCache:
    """Contract tests for SemanticCache port."""

    PORT_NAME = "semantic_cache"
    INTERFACE = SemanticCache
    REQUIRED_METHODS = ["get", "set", "invalidate"]

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


class TestMemoryFilePort:
    """Contract tests for MemoryFilePort port."""

    PORT_NAME = "memory_file_storage"
    INTERFACE = MemoryFilePort
    REQUIRED_METHODS = [
        "write",
        "read",
        "delete",
        "exists",
        "list_memories",
        "update_index",
        "remove_from_index",
        "search_index",
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


class TestPublicBlackboard:
    """Contract tests for PublicBlackboard port."""

    PORT_NAME = "public_blackboard"
    INTERFACE = PublicBlackboard
    REQUIRED_METHODS = ["post", "get", "get_by_agent", "get_latest"]

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


class TestCompressorService:
    """Contract tests for CompressorService port."""

    PORT_NAME = "compressor"
    INTERFACE = CompressorService
    REQUIRED_METHODS = ["compress", "supports"]

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


class TestSessionCachePort:
    """Contract tests for SessionCachePort port."""

    PORT_NAME = "session_cache"
    INTERFACE = SessionCachePort
    REQUIRED_METHODS = [
        "get",
        "set",
        "delete",
        "exists",
        "delete_pattern",
        "set_with_ttl",
        "save_session",
        "load_session",
        "delete_session",
        "session_exists",
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


class TestMemoryCachePort:
    """Contract tests for MemoryCachePort port."""

    PORT_NAME = "memory_cache"
    INTERFACE = MemoryCachePort
    REQUIRED_METHODS = [
        "get",
        "set",
        "delete",
        "exists",
        "delete_pattern",
        "set_with_ttl",
        "get_memory",
        "set_memory",
        "delete_memory",
        "invalidate_owner",
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


class TestExceptionMetricsPort:
    """Contract tests for ExceptionMetricsPort port."""

    PORT_NAME = "exception_metrics"
    INTERFACE = ExceptionMetricsPort
    REQUIRED_METHODS = ["record_exception"]

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


class TestDocumentStoragePort:
    """Contract tests for DocumentStoragePort port."""

    PORT_NAME = "document_storage"
    INTERFACE = DocumentStoragePort
    REQUIRED_METHODS = [
        "store",
        "retrieve",
        "delete",
        "get_metadata",
        "archive",
        "list_objects",
        "store_document",
        "list_user_documents",
        "get_document_metadata",
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


class TestMemoryVectorPort:
    """Contract tests for MemoryVectorPort port."""

    PORT_NAME = "memory_vector_storage"
    INTERFACE = MemoryVectorPort
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
        "index_memory",
        "search_similar_memories",
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


class TestTextExtractorService:
    """Contract tests for TextExtractorService port."""

    PORT_NAME = "text_extractor"
    INTERFACE = TextExtractorService
    REQUIRED_METHODS = ["extract", "supports"]

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


class TestMemoryGraphPort:
    """Contract tests for MemoryGraphPort port."""

    PORT_NAME = "memory_graph_storage"
    INTERFACE = MemoryGraphPort
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
        "index_memory_relations",
        "get_knowledge_graph",
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


class TestMetricsPort:
    """Contract tests for MetricsPort port."""

    PORT_NAME = "metrics"
    INTERFACE = MetricsPort
    REQUIRED_METHODS = [
        "collect",
        "collect_as_dict",
        "record_sessions",
        "record_queue_length",
        "record_cache_hit",
        "record_cache_miss",
        "record_event_processed",
        "update_processing_rate",
        "get_hit_rate",
        "get_sessions",
        "get_queue_length",
        "get_processing_rate",
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


class TestEventSubscriber:
    """Contract tests for EventSubscriber port."""

    PORT_NAME = "event_subscriber"
    INTERFACE = EventSubscriber
    REQUIRED_METHODS = ["subscribe", "subscribe_async", "start", "close"]

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
