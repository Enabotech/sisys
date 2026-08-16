"""Story 3.6 契约化摘要生成端口契约测试

验证 summary_generation_service 端口的注册、解析和实现。
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类，避免触发 DI 实例化"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestSummaryGenerationPortContract:
    """summary_generation_service 端口契约"""

    PORT_NAME = "summary_generation_service"
    IMPL_CLS_NAME = "SummaryGenerationService"
    REQUIRED_METHODS = ["generate_summary"]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.domain.ports.summary_generation import SummaryGenerationPort

        assert spec.interface is SummaryGenerationPort

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
        """摘要生成服务必须是 SCOPED 生命周期（轻量编排）"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED


class TestSummaryGenerationPortInterface:
    """SummaryGenerationPort 领域端口接口契约"""

    def test_port_protocol_exists(self) -> None:
        """SummaryGenerationPort 协议应存在于 domain/ports"""
        from src.domain.ports.summary_generation import SummaryGenerationPort

        assert SummaryGenerationPort is not None
        assert hasattr(SummaryGenerationPort, "generate_summary")


class TestSummaryGenerationPortResolver:
    """SummaryGenerationService 端口解析验证"""

    def test_resolve_summary_generation_service(self, resolver) -> None:
        """验证 Resolver 可解析 summary_generation_service"""
        resolved = resolver.resolve("summary_generation_service")
        assert hasattr(resolved, "generate_summary")
