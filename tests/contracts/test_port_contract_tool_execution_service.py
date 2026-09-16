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

from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.ports.llm_client import LLMConfig, LLMResponse
from src.domain.ports.registry import Lifetime, PortSpec
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository


class _DummyLLM:
    """LLM 客户端存根（满足 LLMClientPort 接口）"""

    async def generate(
        self,
        prompt: str,
        config: LLMConfig | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="")

    async def structured_generate(
        self,
        prompt: str,
        response_schema: Any,
        config: LLMConfig | None = None,
        system_prompt: str | None = None,
    ) -> Any:
        return ""

    async def close(self) -> None:
        pass


class _DummySandbox:
    """沙箱执行器存根（满足 SandboxExecutor 接口）"""

    async def start_container(self, session_id: str) -> None:
        pass

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        return {"status": "ok", "output": ""}

    async def stop_container(self, session_id: str) -> None:
        pass

    async def is_container_running(self, session_id: str) -> bool:
        return True


class _DummyResolver:
    """测试用 resolver，模拟端口依赖注入"""

    def __init__(self) -> None:
        self._repo = InMemoryToolRepository()
        self._registry = ToolRegistryService(self._repo)
        self._engine = ToolExecutionEngine(
            llm_client=_DummyLLM(),
            sandbox=_DummySandbox(),
        )

    def resolve(self, name: str) -> Any:
        if name == "tool_registry_service":
            return self._registry
        if name == "tool_execution_engine":
            return self._engine
        if name == "tool_repository":
            return self._repo
        raise KeyError(f"未注册的端口: {name}")


class TestToolExecutionServicePortContract:
    """ToolExecutionServicePort 端口契约测试 11 维度"""

    PORT_NAME = "tool_execution_service"
    IMPL_CLS_NAME = "ToolExecutionService"
    MODULE_PATH = "src.application.services.tool_execution_service"
    EXPECTED_TAGS = ("tool", "execution", "service")
    EXPECTED_OWNER = "tool-team"
    REQUIRED_METHODS = ["execute", "get_tool_metadata", "list_tools_metadata"]

    def _spec(self) -> PortSpec | None:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：端口已注册"""
        spec = self._spec()
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2：端口名称"""
        spec = self._spec()
        assert spec is not None
        assert spec.name == self.PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：端口版本"""
        spec = self._spec()
        assert spec is not None
        assert spec.version == "v1.1.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4：端口接口类型"""
        spec = self._spec()
        assert spec is not None
        assert spec.interface is ToolExecutionServicePort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5：端口生命周期"""
        spec = self._spec()
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_dimension_6_port_owner(self) -> None:
        """维度 6：端口 owner"""
        spec = self._spec()
        assert spec is not None
        assert spec.owner == self.EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7：端口 module 路径"""
        spec = self._spec()
        assert spec is not None
        assert spec.module == self.MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8：端口 tags"""
        spec = self._spec()
        assert spec is not None
        assert set(spec.tags) == set(self.EXPECTED_TAGS)

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9：impl 是可调用工厂"""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10：实现类包含必需方法"""
        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)
        resolver = _DummyResolver()
        instance = spec.impl(resolver)
        for method_name in self.REQUIRED_METHODS:
            assert hasattr(instance, method_name), f"缺少方法: {method_name}"

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11：Protocol 是 runtime_checkable"""
        assert (
            hasattr(ToolExecutionServicePort, "_is_runtime_protocol")
            or hasattr(ToolExecutionServicePort, "__runtime_protocol__")
            or getattr(ToolExecutionServicePort, "_is_protocol", False)
        )

        spec = self._spec()
        assert spec is not None
        assert callable(spec.impl)
        resolver = _DummyResolver()
        instance = spec.impl(resolver)
        assert isinstance(instance, ToolExecutionServicePort)
