"""agent_workflow_use_case 端口契约测试（Story 5-3 — 单 Agent 标准工作流）

11 维度契约断言（维度清单同 agent_profile_use_case 契约测试先例）。

DummyResolver 提供四依赖名（agent_repository / agent_profile_use_case /
agent_engine / agent_workflow_service）——仓储用 fakeredis 零 IO 替身；
档案用例与工作流服务用组合根同款真实工厂链（DummyResolver 递归 resolve）；
agent_engine 用组合根 LangGraphEngine 工厂（无连接构造）。
"""

from __future__ import annotations

from typing import Any


class _DummyResolver:
    """测试用最小 Resolver 占位符（用例工厂注入四依赖）。

    依赖链按组合根注册语义供给（agent_workflow_use_case 的四依赖经组合根
    lambda 全部 resolve 可达——本 DummyResolver 以真实 resolver 委托实现，
    避免重复手搓四依赖替身）。
    """

    def resolve(self, name: str) -> Any:
        if name == "agent_workflow_use_case":
            from src.domain.ports.resolver import get_resolver

            return get_resolver().resolve("agent_workflow_use_case")
        raise KeyError(f"未注册的端口: {name}")


class TestAgentWorkflowUseCasePortContract:
    """agent_workflow_use_case 端口契约测试 11 维度。"""

    PORT_NAME = "agent_workflow_use_case"
    IMPL_CLS_NAME = "RunAgentWorkflowUseCase"
    MODULE_PATH = "src.application.use_cases.run_agent_workflow"
    EXPECTED_TAGS = ("agent", "workflow")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["execute"]

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

    # 维度 4: interface 绑定用例自身类型（对齐 5-1/5-2 用例端口先例）
    def test_dimension_4_interface_is_use_case(self) -> None:
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase

        assert self._spec().interface is RunAgentWorkflowUseCase

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

    # 维度 9b: impl 工厂产出用例实例（四依赖注入完整）
    def test_dimension_9b_impl_produces_use_case_instance(self) -> None:
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
        from src.domain.ports.resolver import get_resolver

        instance = self._spec().impl(get_resolver())
        assert isinstance(instance, RunAgentWorkflowUseCase)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # 维度 10: 实现具备必需方法
    def test_dimension_10_implementation_has_required_methods(self) -> None:
        from src.domain.ports.resolver import get_resolver

        instance = self._spec().impl(get_resolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # 维度 11: isinstance 校验（用例自身类型）
    def test_dimension_11_instance_type(self) -> None:
        from src.application.use_cases.run_agent_workflow import RunAgentWorkflowUseCase
        from src.domain.ports.resolver import get_resolver

        instance = self._spec().impl(get_resolver())
        assert isinstance(instance, RunAgentWorkflowUseCase)


__all__ = ["TestAgentWorkflowUseCasePortContract"]
