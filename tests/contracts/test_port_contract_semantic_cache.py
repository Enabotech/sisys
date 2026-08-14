"""Story 3-9 语义缓存端口契约测试

验证 semantic_cache、semantic_cache_middleware、cache_invalidation_handler 端口的注册、契约和元数据。
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import Lifetime, PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类，避免触发 DI 实例化"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestSemanticCachePortContract:
    """RedisSemanticCache 端口契约"""

    PORT_NAME = "semantic_cache"
    IMPL_CLS_NAME = "RedisSemanticCache"
    REQUIRED_METHODS = ["get", "set", "invalidate", "invalidate_pattern", "invalidate_all", "invalidate_by_document_id"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        from src.application.ports.semantic_cache import SemanticCache

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        assert spec.interface is SemanticCache

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.module, f"端口 {self.PORT_NAME} 缺少 module 元数据"

        impl_cls = _load_impl_cls(spec.module, self.IMPL_CLS_NAME)
        assert impl_cls is not None, f"无法从 {spec.module} 导入 {self.IMPL_CLS_NAME}"

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method))

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_singleton(self, registry: PortRegistry) -> None:
        """语义缓存必须是 SINGLETON 生命周期"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON, f"生命周期={spec.lifetime}，应为 SINGLETON"

    def test_owner_is_cache_team(self, registry: PortRegistry) -> None:
        """所有者为 cache-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "cache-team", f"owner={spec.owner}"

    def test_version_upgraded_to_1_1_0(self, registry: PortRegistry) -> None:
        """版本升级到 v1.1.0（含 compatibility）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version == "v1.1.0", f"版本={spec.version}，应为 v1.1.0"
        assert spec.compatibility == ("v1.0.0",), f"compatibility={spec.compatibility}"


class TestSemanticCacheMiddlewarePortContract:
    """SemanticCacheMiddleware 端口契约"""

    PORT_NAME = "semantic_cache_middleware"
    IMPL_CLS_NAME = "SemanticCacheMiddleware"
    REQUIRED_METHODS = ["search"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        from src.application.services.semantic_cache_middleware import SemanticCacheMiddleware

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        assert spec.interface is SemanticCacheMiddleware

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.module, f"端口 {self.PORT_NAME} 缺少 module 元数据"

        impl_cls = _load_impl_cls(spec.module, self.IMPL_CLS_NAME)
        assert impl_cls is not None, f"无法从 {spec.module} 导入 {self.IMPL_CLS_NAME}"

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method))

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_scoped(self, registry: PortRegistry) -> None:
        """中间件必须是 SCOPED 生命周期"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED, f"生命周期={spec.lifetime}，应为 SCOPED"

    def test_owner_is_cache_team(self, registry: PortRegistry) -> None:
        """所有者为 cache-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "cache-team"


class TestCacheInvalidationHandlerPortContract:
    """CacheInvalidationHandler 端口契约"""

    PORT_NAME = "cache_invalidation_handler"
    IMPL_CLS_NAME = "CacheInvalidationHandler"
    REQUIRED_METHODS = ["handle"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        from src.infrastructure.messaging.event_handlers.cache_invalidation_handler import (
            CacheInvalidationHandler,
        )

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        assert spec.interface is CacheInvalidationHandler

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.module, f"端口 {self.PORT_NAME} 缺少 module 元数据"

        impl_cls = _load_impl_cls(spec.module, self.IMPL_CLS_NAME)
        assert impl_cls is not None, f"无法从 {spec.module} 导入 {self.IMPL_CLS_NAME}"

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method))

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_singleton(self, registry: PortRegistry) -> None:
        """处理器必须是 SINGLETON 生命周期（确保事件注册仅执行一次）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON, f"生命周期={spec.lifetime}，应为 SINGLETON"

    def test_owner_is_cache_team(self, registry: PortRegistry) -> None:
        """所有者为 cache-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "cache-team"


class TestCacheMetricsPortContract:
    """CacheMetricsPort 端口契约"""

    PORT_NAME = "cache_metrics"

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_singleton(self, registry: PortRegistry) -> None:
        """指标端口必须是 SINGLETON 生命周期"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON, f"生命周期={spec.lifetime}，应为 SINGLETON"

    def test_owner_is_cache_team(self, registry: PortRegistry) -> None:
        """所有者为 cache-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "cache-team"


class TestHybridSearchServiceRegression:
    """已有 hybrid_search_service 端口回归验证（无变更，确保不退化）"""

    PORT_NAME = "hybrid_search_service"

    def test_port_still_registered(self, registry: PortRegistry) -> None:
        """hybrid_search_service 端口仍应注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 已丢失"

    def test_version_unchanged(self, registry: PortRegistry) -> None:
        """hybrid_search_service 版本号不变（v1.1.0）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version == "v1.1.0", f"版本号意外变更: {spec.version}"
