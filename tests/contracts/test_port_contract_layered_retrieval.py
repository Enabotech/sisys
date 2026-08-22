"""Story 3.5 分层检索端口契约测试

验证 layered_retrieval_service 端口的注册、解析和实现。
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类，避免触发 DI 实例化"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestLayeredRetrievalPortContract:
    """layered_retrieval_service 端口契约"""

    PORT_NAME = "layered_retrieval_service"
    IMPL_CLS_NAME = "LayeredRetrievalService"
    REQUIRED_METHODS = ["retrieve", "search_top_down", "search_bottom_up"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.domain.ports.layered_retrieval import LayeredRetrievalPort

        assert spec.interface is LayeredRetrievalPort

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
        """分层检索服务必须是 SCOPED 生命周期（轻量编排）"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED


class TestLayeredRetrievalPortInterface:
    """LayeredRetrievalPort 领域端口接口契约"""

    def test_port_protocol_exists(self) -> None:
        """LayeredRetrievalPort 协议应存在于 domain/ports"""
        from src.domain.ports.layered_retrieval import LayeredRetrievalPort

        assert LayeredRetrievalPort is not None
        assert hasattr(LayeredRetrievalPort, "search_top_down")
        assert hasattr(LayeredRetrievalPort, "search_bottom_up")


class TestLayeredRetrievalPortResolver:
    """LayeredRetrievalService 端口解析验证（通过模块导入检查，避免触发 DI 完整链路）"""

    IMPL_CLS_NAME = "LayeredRetrievalService"
    REQUIRED_METHODS = ["retrieve", "search_top_down", "search_bottom_up"]

    def test_resolve_layered_retrieval_service(self, registry: PortRegistry) -> None:
        """验证实现类包含所有必需方法（通过模块导入，不触发 DI 实例化）"""
        spec = registry.get("layered_retrieval_service")
        assert spec is not None, "layered_retrieval_service 端口未注册"
        assert spec.module, "端口缺少 module 元数据"

        impl_cls = _load_impl_cls(spec.module, self.IMPL_CLS_NAME)
        assert impl_cls is not None, f"无法从 {spec.module} 导入 {self.IMPL_CLS_NAME}"

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method))
