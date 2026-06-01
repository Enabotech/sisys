"""EmbeddingServicePort 端口契约测试

验证 embedding_service 和 dense_search_service 端口的注册、实现和元数据
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import pytest

from src.domain.ports.registry import PortRegistry


class TestEmbeddingServicePortContract:
    """EmbeddingServicePort 端口契约"""

    PORT_NAME = "embedding_service"
    REQUIRED_METHODS = ["encode_text", "encode_texts"]
    REQUIRED_PROPERTIES = ["dimension"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.domain.ports.embedding_service import EmbeddingServicePort

        assert spec.interface is EmbeddingServicePort

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法"""
        from src.domain.ports.resolver import Resolver

        spec = registry.get(self.PORT_NAME)
        assert spec is not None

        try:
            resolver = Resolver()
            impl = resolver.resolve(self.PORT_NAME)
        except Exception as e:
            pytest.skip(f"实现类实例化失败（可能缺少模型）: {e}")

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"缺少方法: {method}"
            assert callable(getattr(impl, method))

        for prop in self.REQUIRED_PROPERTIES:
            assert hasattr(impl, prop), f"缺少属性: {prop}"

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_singleton(self, registry: PortRegistry) -> None:
        """嵌入服务必须是 SINGLETON 生命周期（模型加载昂贵）"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON


class TestDenseSearchServicePortContract:
    """DenseSemanticSearchService 端口契约"""

    PORT_NAME = "dense_search_service"
    REQUIRED_METHODS = ["search"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含 search 方法"""
        from src.domain.ports.resolver import Resolver

        spec = registry.get(self.PORT_NAME)
        assert spec is not None

        try:
            resolver = Resolver()
            impl = resolver.resolve(self.PORT_NAME)
        except Exception as e:
            pytest.skip(f"实现类实例化失败（可能缺少模型）: {e}")

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"缺少方法: {method}"
            assert callable(getattr(impl, method))

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_scoped(self, registry: PortRegistry) -> None:
        """检索服务应为 SCOPED 生命周期（轻量编排）"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED
