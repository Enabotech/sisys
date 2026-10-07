"""Story 4-6: ToolVersionServicePort 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_tool.py（11 维度全覆盖）。
Task 0 阶段红（端口未注册）；Task 4 循环 C 组合根注册后转绿。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.application.ports.tool_version_service import ToolVersionServicePort
from src.application.services.tool_registry_service import ToolRegistryService
from src.application.services.tool_version_service import ToolVersionService
from src.domain.ports.registry import Lifetime, PortSpec
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
from src.infrastructure.storage.inmemory.tool_version_repository import (
    InMemoryToolVersionRepository,
)
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl


class _DummyResolver:
    """测试用 resolver，模拟端口依赖注入（lambda 工厂的求值环境）。"""

    def __init__(self) -> None:
        self._tool_repo = InMemoryToolRepository()
        self._version_repo = InMemoryToolVersionRepository()
        self._registry = ToolRegistryService(repository=self._tool_repo)

    def resolve(self, name: str) -> Any:
        if name == "tool_version_repository":
            return self._version_repo
        if name == "tool_registry_service":
            return self._registry
        if name == "schema_validator":
            return JsonSchemaValidatorImpl()
        if name == "tool_repository":
            return self._tool_repo
        if name == "event_publisher":
            return MagicMock()
        raise KeyError(f"未注册的端口: {name}")


class TestToolVersionServicePortContract:
    """ToolVersionServicePort 端口契约测试 11 维度。"""

    PORT_NAME = "tool_version_service"
    IMPL_CLS_NAME = "ToolVersionService"
    MODULE_PATH = "src.application.services.tool_version_service"
    EXPECTED_TAGS = ("tool", "version", "service")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = [
        "register_version",
        "publish_version",
        "abort_canary",
        "rollback",
        "resolve_version",
        "list_versions",
        "get_version_traffic",
    ]

    def _spec(self) -> PortSpec | None:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册。"""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名称。"""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：端口版本。"""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：端口接口类型。"""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is ToolVersionServicePort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：端口生命周期 SCOPED。"""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：端口 owner。"""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：端口 module 路径。"""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：端口 tags。"""
        spec = self._spec()
        assert spec is not None
        assert set(spec.tags) == set(self.EXPECTED_TAGS)

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：impl 是可调用工厂（lambda 工厂）。"""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含必需方法集（7 方法）。"""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)
        instance = spec.impl(_DummyResolver())
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(instance, method_name), f"缺少方法: {method_name}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 runtime_checkable 且工厂产出真实实例。"""
        assert (
            hasattr(ToolVersionServicePort, "_is_runtime_protocol")
            or hasattr(ToolVersionServicePort, "__runtime_protocol__")
            or getattr(ToolVersionServicePort, "_is_protocol", False)
        )
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, ToolVersionServicePort)

    def test_service_constructor_scalar_injection(self) -> None:
        """附加维度：构造注入为 max_retained_versions 标量（非 Config 对象）。

        应用层服务禁止 import src.infrastructure（.importlinter 契约
        application-no-infrastructure）——配置类仅在组合根解析后传标量。
        """
        import inspect

        sig = inspect.signature(ToolVersionService.__init__)
        assert "max_retained_versions" in sig.parameters
        assert "config" not in sig.parameters, "禁止注入 Config 对象（分层红线）"
        default = sig.parameters["max_retained_versions"].default
        assert default == 10
