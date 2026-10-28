"""agent_evaluation 端口契约测试（Story 5.8 — Task 1 TDD 循环 C）

11 维度契约（对齐 test_port_contract_agent_tracing 同款结构）:
注册可达 / 名称 / 版本 / 接口类型 / 生命周期（SINGLETON——Epic 5 全家政策）/
owner（platform）/ module / tags / impl 可调用 / impl 产出端口实例 /
Protocol runtime_checkable。

_DummyResolver: 零 IO 分发替身（维度 9b 实参形态 impl(DummyResolver()) 与生产
lambda 双 resolve 对齐——分发 llm_client / evaluation_model_resolver 两端口名，
返回最小 Fake 实例——EvaluationHarness 构造仅注入不校验）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_agent_evaluation.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAME = "agent_evaluation"
IMPL_CLS_NAME = "EvaluationHarness"
MODULE_PATH = "src.application.services.evaluation_harness"
EXPECTED_TAGS = ("agent", "evaluation", "observability")
EXPECTED_OWNER = "platform"
REQUIRED_METHODS = ["evaluate"]


class _FakeLLMClient:
    """最小 LLM 客户端替身（维度 9b 构造注入面——不触发真实调用）."""

    async def structured_generate(
        self, prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        return None


class _FakeModelResolver:
    """最小模型解析替身（维度 9b 构造注入面）."""

    async def resolve_config(self, input_text: str) -> Any:
        return None


class _DummyResolver:
    """零 IO 依赖分发替身（分发 agent_evaluation lambda 消费的两端口名）."""

    def resolve(self, name: str) -> Any:
        if name == "llm_client":
            return _FakeLLMClient()
        if name == "evaluation_model_resolver":
            return _FakeModelResolver()
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestAgentEvaluationPortContract:
    """agent_evaluation 端口 11 维度契约."""

    def _spec(self) -> Any:
        return _global_registry.get(PORT_NAME)

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1: 端口已注册（resolve 可达）."""
        assert self._spec() is not None, f"端口 {PORT_NAME} 未注册"

    def test_dimension_2_port_name(self) -> None:
        """维度 2: 端口名精确."""
        assert self._spec().name == PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3: 版本 v1.0.0."""
        assert self._spec().version == "v1.0.0"

    def test_dimension_4_port_interface_type(self) -> None:
        """维度 4: 接口类型 = AgentEvaluationPort（application 层——R2 具体应用端口）."""
        from src.application.ports.agent_evaluation import AgentEvaluationPort

        assert self._spec().interface is AgentEvaluationPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5: SINGLETON（Epic 5 全家政策——EvaluationHarness 无状态纯函数式，
        无 eval_history 累积[5.9/5.10 范围]——SINGLETON 安全）."""
        assert self._spec().lifetime == Lifetime.SINGLETON, f"lifetime 应为 SINGLETON，实际 {self._spec().lifetime}"

    def test_dimension_6_port_owner(self) -> None:
        """维度 6: owner = platform."""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7: module 路径精确（延迟导入锚）."""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8: tags 三元组（agent/evaluation/observability——可观测域交叉标签）."""
        assert self._spec().tags == EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9a: impl 为可调用（lambda 工厂）."""
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        """维度 9b: impl(DummyResolver) 产出端口实例 + 实现类名精确."""
        from src.application.ports.agent_evaluation import AgentEvaluationPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentEvaluationPort)
        assert type(instance).__name__ == IMPL_CLS_NAME

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10: 实现类方法齐备（evaluate——端口面单方法）."""
        instance = self._spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺方法 {method}"
            assert callable(getattr(instance, method))

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11: Protocol runtime_checkable（isinstance 判定可用——判别力由
        test_evaluation_harness.py 行为断言承载）."""
        from src.application.ports.agent_evaluation import AgentEvaluationPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentEvaluationPort)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
