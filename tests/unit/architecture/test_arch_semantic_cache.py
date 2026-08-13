"""Story 3-9: SDD 架构约束验证测试

验证语义缓存的架构合规性：
- domain 层零外部依赖
- 依赖方向：application → domain ✓，application → infrastructure ✗
- SemanticCacheMiddleware 在 application/services 中定义
- CacheInvalidationHandler 在 infrastructure/messaging 中定义
- SemanticCache 端口在 application/ports 中定义
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestServicePlacement:
    """验证服务在正确的架构层中"""

    def test_semantic_cache_middleware_in_application(self) -> None:
        """SemanticCacheMiddleware 在 application/services 中定义"""
        from src.application.services.semantic_cache_middleware import SemanticCacheMiddleware

        assert hasattr(SemanticCacheMiddleware, "search")
        assert hasattr(SemanticCacheMiddleware, "metrics")

    def test_cache_invalidation_handler_in_infrastructure(self) -> None:
        """CacheInvalidationHandler 在 infrastructure/messaging 中定义"""
        from src.infrastructure.messaging.event_handlers.cache_invalidation_handler import (
            CacheInvalidationHandler,
        )

        assert hasattr(CacheInvalidationHandler, "handle")

    def test_semantic_cache_port_in_application(self) -> None:
        """SemanticCache 端口在 application/ports 中定义"""
        from src.application.ports.semantic_cache import SemanticCache

        assert hasattr(SemanticCache, "get")
        assert hasattr(SemanticCache, "set")
        assert hasattr(SemanticCache, "invalidate")
        assert hasattr(SemanticCache, "invalidate_pattern")
        assert hasattr(SemanticCache, "invalidate_all")
        assert hasattr(SemanticCache, "invalidate_by_document_id")

    def test_cache_metrics_port_in_application(self) -> None:
        """CacheMetricsPort 在 application/ports 中定义"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        assert hasattr(CacheMetricsPort, "record_cache_hit")
        assert hasattr(CacheMetricsPort, "record_cache_miss")
        assert hasattr(CacheMetricsPort, "cache_hits_total")
        assert hasattr(CacheMetricsPort, "cache_misses_total")


class TestDependencyDirection:
    """验证依赖方向：application → domain ✓，application → infrastructure ✗"""

    def test_middleware_imports_application_and_domain_only(self) -> None:
        """SemanticCacheMiddleware 仅导入 domain + application，不导入 infrastructure"""
        src_path = Path("src/application/services/semantic_cache_middleware.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.infrastructure",
            "redis",
            "qdrant_client",
            "fastapi",
            "sqlalchemy",
            "prefect",
            "neo4j",
            "minio",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"semantic_cache_middleware.py 禁止导入 infrastructure: {node.module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(blocked_prefixes), (
                        f"semantic_cache_middleware.py 禁止导入 infrastructure: {alias.name}"
                    )

    def test_invalidation_handler_imports_domain_and_application_ports(self) -> None:
        """CacheInvalidationHandler 仅导入 domain + application ports，不导入 infrastructure"""
        src_path = Path("src/infrastructure/messaging/event_handlers/cache_invalidation_handler.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.application.services",
            "src.application.event_handlers",
            "src.interfaces",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"cache_invalidation_handler.py 禁止导入 application services/interfaces: {node.module}"
                    )

    def test_cache_metrics_port_no_implementation_deps(self) -> None:
        """CacheMetricsPort 仅使用 typing 标准库"""
        src_path = Path("src/application/ports/cache_metrics_port.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.infrastructure",
            "redis",
            "pydantic",
            "fastapi",
            "sqlalchemy",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"cache_metrics_port.py 禁止导入 infrastructure: {node.module}"
                    )


class TestSemanticCachePortDefinition:
    """端口定义完整性验证"""

    def test_semantic_cache_port_has_all_methods(self) -> None:
        """SemanticCache 端口有所有必需方法"""
        from src.application.ports.semantic_cache import SemanticCache

        assert hasattr(SemanticCache, "get")
        assert hasattr(SemanticCache, "set")
        assert hasattr(SemanticCache, "invalidate")
        assert hasattr(SemanticCache, "invalidate_pattern")
        assert hasattr(SemanticCache, "invalidate_all")
        assert hasattr(SemanticCache, "invalidate_by_document_id")

    def test_set_has_doc_ids_param(self) -> None:
        """SemanticCache.set() 有 doc_ids 可选参数"""
        import inspect

        from src.application.ports.semantic_cache import SemanticCache

        sig = inspect.signature(SemanticCache.set)
        params = list(sig.parameters.keys())
        assert "doc_ids" in params, f"set() 缺少 doc_ids 参数: {params}"

    def test_cache_metrics_port_has_required_methods(self) -> None:
        """CacheMetricsPort 有必需方法和属性"""
        from src.application.ports.cache_metrics_port import CacheMetricsPort

        assert hasattr(CacheMetricsPort, "record_cache_hit")
        assert hasattr(CacheMetricsPort, "record_cache_miss")
        assert hasattr(CacheMetricsPort, "hit_rate")
