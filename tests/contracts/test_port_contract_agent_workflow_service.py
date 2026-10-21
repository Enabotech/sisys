"""agent_workflow_service 端口契约测试（Story 5-3 — 单 Agent 标准工作流）

11 维度契约断言（维度清单同 agent_profile_use_case 契约测试先例）。

DummyResolver 提供四依赖名（llm_client / tool_execution_service / skill_loader /
tool_registry_service）——llm_client 与工具面两端口用 Mock/AsyncMock 零 IO 替身
（契约测试只验证工厂组装形态，不发命令）；skill_loader 用真实 InMemorySkillLoader
（本地静态文件只读、零连接构造）。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock


class _DummyResolver:
    """测试用最小 Resolver 占位符（服务工厂注入四依赖）。"""

    def resolve(self, name: str) -> Any:
        if name == "llm_client":
            from src.domain.ports.llm_client import LLMClientPort

            return AsyncMock(spec=LLMClientPort)
        if name == "tool_execution_service":
            from src.application.ports.tool_execution_service import ToolExecutionServicePort

            return AsyncMock(spec=ToolExecutionServicePort)
        if name == "skill_loader":
            from src.application.skills.loader import InMemorySkillLoader

            return InMemorySkillLoader()
        if name == "tool_registry_service":
            from src.application.ports.tool_registry_service import ToolRegistryServicePort

            return Mock(spec=ToolRegistryServicePort)
        raise KeyError(f"未注册的端口: {name}")


class TestAgentWorkflowServicePortContract:
    """agent_workflow_service 端口契约测试 11 维度。"""

    PORT_NAME = "agent_workflow_service"
    IMPL_CLS_NAME = "AgentWorkflowService"
    MODULE_PATH = "src.application.services.agent_workflow_service"
    EXPECTED_TAGS = ("agent", "workflow")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = [
        "build_context",
        "perceive",
        "plan",
        "execute",
        "verify",
        "reflect",
        "package_evidence",
    ]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # 维度 1: 端口已注册
    def test_dimension_1_port_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未注册"

    # 维度 2: 端口名称
    def test_dimension_2_port_name(self) -> None:
        assert self._spec().name == self.PORT_NAME

    # 维度 3: 版本
    def test_dimension_3_version(self) -> None:
        assert self._spec().version == "v1.0.0"

    # 维度 4: interface 绑定端口 Protocol（对齐 agent_engine 端口先例）
    def test_dimension_4_interface_is_protocol(self) -> None:
        from src.application.ports.agent_workflow import AgentWorkflowServicePort

        assert self._spec().interface is AgentWorkflowServicePort

    # 维度 5: 生命周期
    def test_dimension_5_lifetime(self) -> None:
        from src.domain.ports.registry import Lifetime

        assert self._spec().lifetime == Lifetime.SINGLETON

    # 维度 6: owner
    def test_dimension_6_owner(self) -> None:
        assert self._spec().owner == self.EXPECTED_OWNER

    # 维度 7: 实现模块路径
    def test_dimension_7_module_path(self) -> None:
        assert self._spec().module == self.MODULE_PATH

    # 维度 8: tags
    def test_dimension_8_tags(self) -> None:
        assert self._spec().tags == self.EXPECTED_TAGS

    # 维度 9a: impl 是可调用工厂
    def test_dimension_9a_impl_callable(self) -> None:
        assert callable(self._spec().impl)

    # 维度 9b: impl 工厂产出服务实例（四依赖注入完整）
    def test_dimension_9b_impl_produces_service_instance(self) -> None:
        from src.application.services.agent_workflow_service import AgentWorkflowService

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentWorkflowService)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # 维度 10: 实现具备必需方法（build_context + 六阶段）
    def test_dimension_10_implementation_has_required_methods(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # 维度 11: isinstance 校验（端口 Protocol——runtime_checkable）
    def test_dimension_11_instance_satisfies_protocol(self) -> None:
        from src.application.ports.agent_workflow import AgentWorkflowServicePort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentWorkflowServicePort)


__all__ = ["TestAgentWorkflowServicePortContract"]
