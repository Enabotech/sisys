"""agent_drift 端口契约测试——Story 5.9 组合根注册 11 维度门禁。

对齐 test_port_contract_agent_evaluation.py 同款结构（11 维度 + _DummyResolver
分发替身）。差异：_DummyResolver 扩 event_publisher 分发分支（agent_drift 注册
lambda 消费 event_publisher 单依赖——llm_client 双分发先例可循；分支返回最小
Fake publisher，构造仅注入不校验、契约测试不触发发布）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_agent_drift.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAME = "agent_drift"
IMPL_CLS_NAME = "CUSUMDriftDetector"
MODULE_PATH = "src.infrastructure.monitoring.cusum_detector"
EXPECTED_TAGS = ("agent", "drift", "observability")
EXPECTED_OWNER = "platform"
REQUIRED_METHODS = ["update", "trigger_recalibration"]


class _FakeEventPublisher:
    """最小 Fake 事件发布替身（duck-typing——对齐 5-8 _FakeLLMClient 形态）。"""

    async def publish(self, event: Any) -> Any:
        return None


class _DummyResolver:
    """零 IO 依赖分发替身（分发 agent_drift lambda 消费的 event_publisher 端口名）."""

    def resolve(self, name: str) -> Any:
        if name == "event_publisher":
            return _FakeEventPublisher()
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestAgentDriftPortContract:
    """11 维度契约（注册可达/元数据/impl 可构造/方法齐备/runtime_checkable）。"""

    def _spec(self) -> Any:
        spec = _global_registry.get(PORT_NAME)
        assert spec is not None, f"端口 {PORT_NAME} 未注册（bootstrap 后应可达）"
        return spec

    def test_dimension_1_port_is_registered(self) -> None:
        """维度 1：注册可达。"""
        assert self._spec() is not None

    def test_dimension_2_port_name(self) -> None:
        """维度 2：名称。"""
        assert self._spec().name == PORT_NAME

    def test_dimension_3_port_version(self) -> None:
        """维度 3：版本。"""
        assert self._spec().version == "v1.0.0"

    def test_dimension_4_interface_is_drift_detection_port(self) -> None:
        """维度 4：接口类型（application 端口——延迟 import 消费注册面）。"""
        from src.application.ports.agent_drift import DriftDetectionPort

        assert self._spec().interface is DriftDetectionPort

    def test_dimension_5_lifetime_singleton(self) -> None:
        """维度 5：生命周期 SINGLETON（有状态检测器——状态即功能 DC-6：跨 run
        序列累积必须跨 execute 调用存活，SCOPED/TRANSIENT 使序列归零检测失效）。"""
        assert self._spec().lifetime == Lifetime.SINGLETON

    def test_dimension_6_owner(self) -> None:
        """维度 6：owner。"""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_module_path(self) -> None:
        """维度 7：实现模块路径（architecture.md L2594 钦定位置）。"""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_tags(self) -> None:
        """维度 8：tags。"""
        assert self._spec().tags == EXPECTED_TAGS

    def test_dimension_9a_impl_is_callable(self) -> None:
        """维度 9a：impl 可调用（lambda 工厂）。"""
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_yields_port_instance(self) -> None:
        """维度 9b：impl 产出端口实例 + 类名（_DummyResolver 真实构造 impl——
        构造仅注入 event_publisher 不校验、契约测试不触发发布）。"""
        from src.application.ports.agent_drift import DriftDetectionPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, DriftDetectionPort), f"应实现 DriftDetectionPort: {type(instance)}"
        assert type(instance).__name__ == IMPL_CLS_NAME

    def test_dimension_10_methods_present(self) -> None:
        """维度 10：方法齐备（hasattr + callable——OD-7 双方法契约）。"""
        instance = self._spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"{IMPL_CLS_NAME} 应有 {method}"
            assert callable(getattr(instance, method)), f"{method} 应 callable"

    def test_dimension_11_runtime_checkable(self) -> None:
        """维度 11：runtime_checkable isinstance 判别（行为判别力归单测/验收承载）。"""
        from src.application.ports.agent_drift import DriftDetectionPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, DriftDetectionPort)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
