"""Story 3-1b 搜索服务端口契约测试

验证 sparse_search_service 和 hybrid_search_service 端口的注册、契约和元数据。
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类，避免触发 DI 实例化"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestSparseSearchServicePortContract:
    """Bm25SparseSearchService 端口契约"""

    PORT_NAME = "sparse_search_service"
    IMPL_CLS_NAME = "Bm25SparseSearchService"
    REQUIRED_METHODS = ["search"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        from src.application.services.sparse_search_service import Bm25SparseSearchService

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        assert spec.interface is Bm25SparseSearchService

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法（通过模块导入检查，不实例化）"""
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
        """搜索服务必须是 SCOPED 生命周期"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_owner_is_search_team(self, registry: PortRegistry) -> None:
        """所有者为 search-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "search-team"


class TestHybridSearchServicePortContract:
    """HybridSearchService 端口契约"""

    PORT_NAME = "hybrid_search_service"
    IMPL_CLS_NAME = "HybridSearchService"
    REQUIRED_METHODS = ["search"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        from src.application.services.hybrid_search_service import HybridSearchService

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        assert spec.interface is HybridSearchService

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法（通过模块导入检查，不实例化）"""
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
        """搜索服务必须是 SCOPED 生命周期"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_owner_is_search_team(self, registry: PortRegistry) -> None:
        """所有者为 search-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "search-team"

    def test_version_upgraded_to_1_1_0(self, registry: PortRegistry) -> None:
        """版本升级到 v1.1.0（含 compatibility）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version == "v1.1.0", f"版本={spec.version}，应为 v1.1.0"
        assert spec.compatibility == ("v1.0.0",), f"compatibility={spec.compatibility}"


class TestGraphSearchServicePortContract:
    """GraphSearchService 端口契约"""

    PORT_NAME = "graph_search_service"
    IMPL_CLS_NAME = "GraphSearchService"
    REQUIRED_METHODS = ["search"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        from src.application.services.graph_search_service import GraphSearchService

        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        assert spec.interface is GraphSearchService

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
        """Graph 检索服务必须是 SCOPED 生命周期"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_owner_is_search_team(self, registry: PortRegistry) -> None:
        """所有者为 search-team"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.owner == "search-team"


class TestDenseSearchServiceRegression:
    """已有 dense_search_service 端口回归验证（无变更，确保不退化）"""

    PORT_NAME = "dense_search_service"

    def test_port_still_registered(self, registry: PortRegistry) -> None:
        """dense_search_service 端口仍应注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 已丢失"

    def test_version_unchanged(self, registry: PortRegistry) -> None:
        """dense_search_service 版本号不变（v1.0.0）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version == "v1.0.0", f"dense_search_service 版本号意外变更: {spec.version}"
