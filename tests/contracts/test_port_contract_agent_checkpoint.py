"""agent_checkpoint 端口契约测试——Story 5.10 组合根注册 11 维度门禁。

对齐 test_port_contract_agent_drift.py 同款结构（11 维度 + _DummyResolver
分发替身）。差异：_DummyResolver 分发 snapshot_repository 端口（agent_checkpoint
注册 lambda 消费 snapshot_repository 单依赖——R2 应用端口组合注入领域基础端口；
分支返回最小 Fake 快照仓储，构造仅注入不触发 IO、契约测试不执行 record/restore）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_agent_checkpoint.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAME = "agent_checkpoint"
IMPL_CLS_NAME = "EvaluationCheckpointRecorder"
MODULE_PATH = "src.application.services.evaluation_checkpoint_recorder"
EXPECTED_TAGS = ("agent", "checkpoint", "observability")
EXPECTED_OWNER = "platform"
REQUIRED_METHODS = ["record", "restore"]


class _FakeSnapshotRepo:
    """最小 Fake 快照仓储替身（duck-typing 实现 SnapshotRepositoryProtocol——零 IO）。"""

    async def save(self, snapshot: Any) -> None:
        return None

    async def load(self, session_id: str) -> Any:
        return None

    async def delete(self, session_id: str) -> None:
        return None


class _DummyResolver:
    """零 IO 依赖分发替身（分发 agent_checkpoint lambda 消费的 snapshot_repository 端口名）."""

    def resolve(self, name: str) -> Any:
        if name == "snapshot_repository":
            return _FakeSnapshotRepo()
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestAgentCheckpointPortContract:
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

    def test_dimension_4_interface_is_agent_checkpoint_port(self) -> None:
        """维度 4：接口类型（application 端口——延迟 import 消费注册面）。"""
        from src.application.ports.agent_checkpoint import AgentCheckpointPort

        assert self._spec().interface is AgentCheckpointPort

    def test_dimension_5_lifetime_singleton(self) -> None:
        """维度 5：生命周期 SINGLETON（跨 run 累积——状态即功能 DC-7：评估历史
        窗口必须跨 execute 调用存活，SCOPED/TRANSIENT 使累积归零历史失效）。"""
        assert self._spec().lifetime == Lifetime.SINGLETON

    def test_dimension_6_owner(self) -> None:
        """维度 6：owner。"""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_module_path(self) -> None:
        """维度 7：实现模块路径（application/services 落位——evaluation_harness 先例同层）。"""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_tags(self) -> None:
        """维度 8：tags。"""
        assert self._spec().tags == EXPECTED_TAGS

    def test_dimension_9a_impl_is_callable(self) -> None:
        """维度 9a：impl 可调用（lambda 工厂）。"""
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_yields_port_instance(self) -> None:
        """维度 9b：impl 产出端口实例 + 类名（_DummyResolver 真实构造 impl——
        构造仅注入 snapshot_repository 不触发 IO、契约测试不执行 record/restore）。"""
        from src.application.ports.agent_checkpoint import AgentCheckpointPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentCheckpointPort), f"应实现 AgentCheckpointPort: {type(instance)}"
        assert type(instance).__name__ == IMPL_CLS_NAME

    def test_dimension_10_methods_present(self) -> None:
        """维度 10：方法齐备（hasattr + callable——OD-7 双方法契约）。"""
        instance = self._spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"{IMPL_CLS_NAME} 应有 {method}"
            assert callable(getattr(instance, method)), f"{method} 应 callable"

    def test_dimension_11_runtime_checkable(self) -> None:
        """维度 11：runtime_checkable isinstance 判别（行为判别力归单测/验收承载）。"""
        from src.application.ports.agent_checkpoint import AgentCheckpointPort

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, AgentCheckpointPort)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
