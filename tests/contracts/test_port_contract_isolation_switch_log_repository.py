"""isolation_switch_log_repository 端口契约测试（Story 5.6 — Task 2 TDD 循环 C）

11 维度契约（对齐 test_port_contract_isolation_management_service 同款结构）:
注册可达 / 名称 / 版本 / 接口类型 / 生命周期（SINGLETON——DC-11，5-4 DC-7 新增面
政策）/ owner（platform）/ module / tags / impl 可调用 / impl 产出端口实例 /
Protocol runtime_checkable。

_DummyResolver: 零 IO 替身分发（session_factory → None——仓储构造器合法默认，
fallback 缺失时显式失败是设计语义；debate_session L31 先例形态）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_isolation_switch_log_repository.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.registry import Lifetime, _global_registry

PORT_NAME = "isolation_switch_log_repository"
IMPL_CLS_NAME = "PostgreSQLIsolationSwitchLogRepository"
MODULE_PATH = "src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository"
EXPECTED_TAGS = ("agent", "isolation", "audit")
EXPECTED_OWNER = "platform"
REQUIRED_METHODS = ["save", "search"]


class _DummyResolver:
    """零 IO 依赖分发替身（session_factory → None——构造器合法默认形态）."""

    def resolve(self, name: str) -> Any:
        if name == "session_factory":
            return None  # 仓储构造器默认（fallback 缺失显式失败是设计语义）
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        return None


class TestIsolationSwitchLogRepositoryPortContract:
    """isolation_switch_log_repository 端口 11 维度契约."""

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
        """维度 4: 接口类型 = IsolationSwitchLogRepository（domain 端口）."""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository

        assert self._spec().interface is IsolationSwitchLogRepository

    def test_dimension_5_port_lifetime(self) -> None:
        """维度 5: SINGLETON（DC-11——5-4 DC-7 新增面政策：新端口从源头避免被
        SINGLETON isolation_management_service 捕获形成 captive；同域先例
        isolation_repository L2874 亦 SINGLETON）。"""
        assert self._spec().lifetime == Lifetime.SINGLETON, f"lifetime 应为 SINGLETON，实际 {self._spec().lifetime}"

    def test_dimension_6_port_owner(self) -> None:
        """维度 6: owner = platform."""
        assert self._spec().owner == EXPECTED_OWNER

    def test_dimension_7_port_module(self) -> None:
        """维度 7: module 路径精确（延迟导入锚）."""
        assert self._spec().module == MODULE_PATH

    def test_dimension_8_port_tags(self) -> None:
        """维度 8: tags 三元组（agent/isolation/audit——审计域交叉标签）."""
        assert self._spec().tags == EXPECTED_TAGS

    def test_dimension_9_impl_is_callable(self) -> None:
        """维度 9a: impl 为可调用（lambda 工厂）."""
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        """维度 9b: impl(DummyResolver) 产出端口实例 + 实现类名精确."""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, IsolationSwitchLogRepository)
        assert type(instance).__name__ == IMPL_CLS_NAME

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        """维度 10: 实现类方法齐备（save/search——端口面最小两方法）."""
        instance = self._spec().impl(_DummyResolver())
        for method in REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺方法 {method}"
            assert callable(getattr(instance, method))

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        """维度 11: Protocol runtime_checkable（isinstance 判定可用）."""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository

        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, IsolationSwitchLogRepository)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
