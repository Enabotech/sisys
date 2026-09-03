"""Story 4.1: 端口契约测试 — 工具仓储与工具注册服务

验证 tool_repository / tool_registry_service 端口的注册、版本、接口、
生命周期、owner/tags/module 元数据，以及 InMemoryToolRepository / ToolRegistryService
实现类的 required_methods 与 Protocol runtime_checkable 属性。

遵循项目标准 11 维度契约测试模式（与 test_port_contract_strategic_archive / document_parser / traceability 对齐）。
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.tool_repository import ToolRepositoryPort


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    tool_registry_service 的 impl 工厂需要 resolver.resolve('tool_repository')，
    本测试使用最小可工作实例。
    """

    def resolve(self, name: str) -> Any:
        from src.infrastructure.storage.inmemory.tool_repository import (
            InMemoryToolRepository,
        )

        if name == "tool_repository":
            return InMemoryToolRepository()
        raise KeyError(name)


class TestToolRepositoryPortContract:
    """tool_repository 端口契约（11 维度全覆盖）."""

    PORT_NAME = "tool_repository"
    IMPL_CLS_NAME = "InMemoryToolRepository"
    MODULE_PATH = "src.infrastructure.storage.inmemory.tool_repository"
    EXPECTED_TAGS = ("tool", "repository", "inmemory")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "save",
        "get_by_id",
        "get_by_name",
        "list_all",
        "count",
        "list_by_category",
        "delete",
    ]

    def _spec(self) -> Any:
        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册."""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：PortSpec.name 正确."""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：PortSpec.version 为 v1.0.0."""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：PortSpec.interface 是 ToolRepositoryPort Protocol."""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is ToolRepositoryPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：PortSpec.lifetime 为 SCOPED."""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：PortSpec.owner 为 tool-team."""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：PortSpec.module 指向正确实现模块."""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：PortSpec.tags 元数据完整."""
        spec = self._spec()
        assert spec is not None
        assert spec.tags == self.EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：spec.impl 是可调用工厂."""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_dimension_9_impl_factory_produces_port_instance(self) -> None:
        """维度 9（续）：工厂产出满足 Protocol（runtime_checkable isinstance 校验）."""
        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ToolRepositoryPort)

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含所有必需方法."""
        import importlib

        spec = self._spec()
        assert spec is not None
        assert spec.module
        mod = importlib.import_module(spec.module)
        impl_cls = getattr(mod, self.IMPL_CLS_NAME, None)
        assert impl_cls is not None
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method)), f"方法不可调用: {method}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 @runtime_checkable（isinstance 行为）."""
        from src.infrastructure.storage.inmemory.tool_repository import (
            InMemoryToolRepository,
        )

        # Protocol 实际应用：isinstance 校验通过
        repo = InMemoryToolRepository()
        assert isinstance(repo, ToolRepositoryPort)


class TestToolRegistryServicePortContract:
    """tool_registry_service 端口契约（11 维度全覆盖）."""

    PORT_NAME = "tool_registry_service"
    IMPL_CLS_NAME = "ToolRegistryService"
    MODULE_PATH = "src.application.services.tool_registry_service"
    EXPECTED_TAGS = ("tool", "registry", "service")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "register_all",
        "get_tool",
        "get_tools_by_category",
        "list_all_tools",
        "tool_count",
    ]

    def _spec(self) -> Any:
        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册."""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：PortSpec.name 正确."""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：PortSpec.version 为 v1.0.0."""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：PortSpec.interface 是 ToolRegistryServicePort Protocol."""
        from src.application.ports.tool_registry_service import (
            ToolRegistryServicePort,
        )

        spec = self._spec()
        assert spec is not None
        assert spec.interface is ToolRegistryServicePort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：PortSpec.lifetime 为 SCOPED."""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：PortSpec.owner 为 tool-team."""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：PortSpec.module 指向正确实现模块."""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：PortSpec.tags 元数据完整."""
        spec = self._spec()
        assert spec is not None
        assert spec.tags == self.EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：spec.impl 是可调用工厂."""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)

    def test_dimension_9_impl_factory_produces_port_instance(self) -> None:
        """维度 9（续）：工厂产出满足 Protocol."""
        from src.application.ports.tool_registry_service import (
            ToolRegistryServicePort,
        )

        spec = self._spec()
        assert spec is not None
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ToolRegistryServicePort)

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含所有必需方法."""
        import importlib

        spec = self._spec()
        assert spec is not None
        assert spec.module
        mod = importlib.import_module(spec.module)
        impl_cls = getattr(mod, self.IMPL_CLS_NAME, None)
        assert impl_cls is not None
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method)), f"方法不可调用: {method}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 @runtime_checkable（isinstance 行为）."""
        from src.application.services.tool_registry_service import (
            ToolRegistryService,
        )
        from src.infrastructure.storage.inmemory.tool_repository import (
            InMemoryToolRepository,
        )

        # Protocol 实际应用：isinstance 校验通过
        service = ToolRegistryService(repository=InMemoryToolRepository())
        from src.application.ports.tool_registry_service import (
            ToolRegistryServicePort,
        )

        assert isinstance(service, ToolRegistryServicePort)
