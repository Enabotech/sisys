"""evaluation_model_resolver 端口契约测试（Story 5.8 — Task 1 TDD 循环 C）

11 维度契约（对齐 test_port_contract_agent_tracing 同款结构）:
注册可达 / 名称 / 版本 / 接口类型 / 生命周期（SINGLETON）/ owner（platform）/
module / tags / impl 可调用 / impl 产出端口实例 / Protocol runtime_checkable。

_DummyResolver: 零 IO 分发替身（分发 udmr_service 一端口名——生产 lambda 的
resolver 消费面；cloud_configs/local_model/llm_timeout 经 UDMRConfig.from_env()
原始值注入——构造器注入原始值纪律，UDMRService 注册先例 L1627-1647 同款）。

注意：维度 9b 经 DummyResolver 构造（udmr_service 分发 Fake + from_env 原始值）
——依赖 UDMR_* 环境变量清洁态（半配置态 from_env 抛 101 属环境问题非契约问题，
CI 裸 env 全默认值合法）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_evaluation_model_resolver.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAME = "evaluation_model_resolver"
IMPL_CLS_NAME = "UdmrEvaluationModelResolver"
MODULE_PATH = "src.infrastructure.routing.udmr_evaluation_model_resolver"
EXPECTED_TAGS = ("agent", "evaluation", "udmr")
EXPECTED_OWNER = "platform"
REQUIRED_METHODS = ["resolve_config"]


class _FakeUdmrService:
    """最小 UDMR 服务替身（维度 9b 构造注入面——不触发真实路由）."""

    async def decide(self, task: Any, causation_id: Any = None) -> Any:
        return None


class _DummyResolver:
    """零 IO 依赖分发替身（分发 evaluation_model_resolver lambda 消费的端口名）."""

    def resolve(self, name: str) -> Any:
        if name == "udmr_service":
            return _FakeUdmrService()
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestEvaluationModelResolverPortContract:
    """evaluation_model_resolver 端口 11 维度契约."""

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
        """维度 4: 接口类型 = EvaluationModelResolverPort（application 层端口——
        R3 落点：UDMR 路由技术实现面由 infrastructure 实现可替换）."""
        from src.application.ports.agent_evaluation import EvaluationModelResolverPort

        assert self._spec().interface is EvaluationModelResolverPort

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5: SINGLETON（Epic 5 全家政策——resolver 持 UDMRService 单例引用
        + UDMRConfig 原始值，构造期定格无请求级状态）."""
        assert self._spec().lifetime == Lifetime.SINGLETON, f"lifetime 应为 SINGLETON，实际 {self._spec().lifetime}"

    def test_dimension_6_port_owner(self) -> None:
        """维度 6: owner = platform."""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7: module 路径精确（延迟导入锚）."""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8: tags 三元组（agent/evaluation/udmr——评估×路由交叉标签）."""
        assert self._spec().tags == EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9a: impl 为可调用（lambda 工厂）."""
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        """维度 9b: impl(DummyResolver) 产出端口实例 + 实现类名精确."""
        from src.application.ports.agent_evaluation import EvaluationModelResolverPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, EvaluationModelResolverPort)
        assert type(instance).__name__ == IMPL_CLS_NAME

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10: 实现类方法齐备（resolve_config——端口面单方法）."""
        instance = self._spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺方法 {method}"
            assert callable(getattr(instance, method))

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11: Protocol runtime_checkable（isinstance 判定可用——判别力由
        test_udmr_evaluation_model_resolver.py 行为断言承载）."""
        from src.application.ports.agent_evaluation import EvaluationModelResolverPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, EvaluationModelResolverPort)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
