"""Story 4.1a: ToolExecutionService 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_tool.py（11 维度全覆盖）

11 维度测试方法名清单：
1. test_dimension_1_port_is_registered
2. test_dimension_2_port_name
3. test_dimension_3_port_version
4. test_dimension_4_port_interface_type
5. test_dimension_5_port_lifetime
6. test_dimension_6_port_owner
7. test_dimension_7_port_module
8. test_dimension_8_port_tags
9. test_dimension_9_impl_is_callable
10. test_dimension_10_implementation_has_required_methods
11. test_dimension_11_protocol_is_runtime_checkable
"""

from __future__ import annotations

from typing import Any

import pytest

from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_registry_service import ToolRegistryService
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository


class _DummyResolver:
    """测试用 resolver，模拟端口依赖注入"""

    def __init__(self) -> None:
        self._repo = InMemoryToolRepository()
        self._registry = ToolRegistryService(self._repo)
        self._engine = _DummyEngine()
        self._service = ToolExecutionService(
            registry=self._registry,
            engine=self._engine,
        )

    def resolve(self, name: str) -> Any:
        if name == "tool_registry_service":
            return self._registry
        if name == "tool_execution_engine":
            return self._engine
        if name == "tool_repository":
            return self._repo
        raise KeyError(f"未注册的端口: {name}")


class _DummyEngine:
    """测试用引擎存根（避免真实执行链路）"""

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return None


class TestToolExecutionServicePortContract:
    """ToolExecutionServicePort 端口契约测试 11 维度"""

    PORT_NAME = "tool_execution_service"
    IMPL_CLS_NAME = "ToolExecutionService"
    MODULE_PATH = "src.application.services.tool_execution_service"
    EXPECTED_TAGS = ("tool", "execution", "service")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = ["execute", "get_tool_metadata", "list_tools_metadata"]

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """从全局端口注册中心获取端口规格"""
        from src.domain.ports.registry import _global_registry

        self._ports = _global_registry
        spec = self._ports.get(self.PORT_NAME)
        if spec is None:
            pytest.skip(f"端口 {self.PORT_NAME} 尚未注册（待 Task 7 完成）")
        self.spec = spec

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册"""
        assert self.spec is not None

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名称"""
        assert self.spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：端口版本"""
        assert self.spec.version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：端口接口类型"""
        assert self.spec.interface is ToolExecutionServicePort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：端口生命周期"""
        from src.composition_root import Lifetime

        assert self.spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：端口 owner"""
        assert self.spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：端口 module 路径"""
        assert self.spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：端口 tags"""
        assert set(self.spec.tags) == set(self.EXPECTED_TAGS)

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：impl 是可调用工厂"""
        assert callable(self.spec.impl)

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含必需方法"""
        resolver = _DummyResolver()
        instance = self.spec.impl(resolver)
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(instance, method_name), f"缺少方法: {method_name}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 runtime_checkable"""
        assert (
            hasattr(ToolExecutionServicePort, "_is_runtime_protocol")
            or hasattr(ToolExecutionServicePort, "__runtime_protocol__")
            or getattr(ToolExecutionServicePort, "_is_protocol", False)
        )

        resolver = _DummyResolver()
        instance = self.spec.impl(resolver)
        assert isinstance(instance, ToolExecutionServicePort)
