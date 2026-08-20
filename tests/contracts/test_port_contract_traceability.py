"""Story 3.8 高保真溯源端口契约测试

验证 traceability_service 端口的注册、解析和实现。
遵循项目四方法模式: test_port_is_registered + test_implementation_has_required_methods
+ test_metadata_complete + test_lifetime_is_scoped
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类，避免触发 DI 实例化"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestTraceabilityPortContract:
    """traceability_service 端口契约"""

    PORT_NAME = "traceability_service"
    IMPL_CLS_NAME = "TraceabilityService"
    REQUIRED_METHODS = ["trace", "get_citation_detail", "get_citation_by_document"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.domain.ports.traceability import TraceabilityPort

        assert spec.interface is TraceabilityPort

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
        """溯源服务必须是 SCOPED 生命周期"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED


class TestTraceabilityPortInterface:
    """TraceabilityPort 领域端口接口契约"""

    def test_port_protocol_exists(self) -> None:
        """TraceabilityPort 协议应存在于 domain/ports"""
        from src.domain.ports.traceability import TraceabilityPort

        assert TraceabilityPort is not None
        assert hasattr(TraceabilityPort, "trace")
        assert hasattr(TraceabilityPort, "get_citation_detail")
        assert hasattr(TraceabilityPort, "get_citation_by_document")


class TestTraceabilityPortResolver:
    """TraceabilityService 端口解析验证"""

    def test_resolve_traceability_service(self, resolver) -> None:
        """验证 Resolver 可解析 traceability_service"""
        resolved = resolver.resolve("traceability_service")
        assert hasattr(resolved, "trace")
        assert hasattr(resolved, "get_citation_detail")
        assert hasattr(resolved, "get_citation_by_document")
