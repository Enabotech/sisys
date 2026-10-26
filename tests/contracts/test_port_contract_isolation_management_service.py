"""Story 5.4: IsolationManagementServicePort 端口契约测试（11 维度）

参考样板: tests/contracts/test_port_contract_agent_repository.py

11 维度测试方法名清单:
1. test_dimension_1_port_is_registered
2. test_dimension_2_port_name
3. test_dimension_3_port_version
4. test_dimension_4_port_interface_type
5. test_dimension_5_port_lifetime
6. test_dimension_6_port_owner
7. test_dimension_7_port_module
8. test_dimension_8_port_tags
9. test_dimension_9_impl_is_callable（9a 可调用 + 9b DummyResolver 实例化 isinstance）
10. test_dimension_10_implementation_has_required_methods
11. test_dimension_11_protocol_is_runtime_checkable

Run with:
    poetry run pytest tests/contracts/test_port_contract_isolation_management_service.py -v
"""

from __future__ import annotations

from typing import Any

from src.application.ports.isolation_management import IsolationManagementServicePort
from src.domain.ports.registry import Lifetime


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    isolation_management_service 工厂注入六依赖（isolation_repository/
    agent_repository/event_publisher/agent_config_loader[R1-F01 TTL 真源通道]/
    isolation_switch_log_repository[Story 5.6 第五依赖——PG 仓储构造器
    session_factory=None 合法默认] + audit_service[第六依赖可选——
    resolve_optional 通道，debate_session L31 先例]）——全部以零 IO 替身提供
    （契约维度仅验证实例化与方法面，不触真实连接）。
    """

    def resolve(self, name: str) -> Any:
        import fakeredis.aioredis

        from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
        from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
            PostgreSQLIsolationSwitchLogRepository,
        )
        from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
        from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
        from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

        if name == "isolation_repository":
            return RedisIsolationRepository(
                adapter=RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True))
            )
        if name == "agent_repository":
            return RedisAgentRepository(adapter=RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True)))
        if name == "event_publisher":
            return InMemoryEventBus()
        if name == "agent_config_loader":
            return YamlAgentConfigLoader()
        if name == "isolation_switch_log_repository":
            return PostgreSQLIsolationSwitchLogRepository(session_factory=None)
        raise KeyError(f"未注册的端口: {name}")

    def resolve_optional(self, name: str) -> Any:
        """可选依赖通道（Story 5.6 第六依赖 audit_service——lambda 消费形态）。"""
        return None


class TestIsolationManagementServicePortContract:
    """isolation_management_service 端口契约（11 维度）。"""

    PORT_NAME = "isolation_management_service"
    IMPL_CLS_NAME = "IsolationManagementService"
    MODULE_PATH = "src.application.services.isolation_management_service"
    EXPECTED_TAGS = ("agent", "isolation")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["initialize_agent_isolation", "get_isolation_state", "switch_isolation_level"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # --- 维度 1: 端口已注册 ---

    def test_dimension_1_port_is_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未注册"

    # --- 维度 2: 端口名 ---

    def test_dimension_2_port_name(self) -> None:
        assert self._spec().name == self.PORT_NAME

    # --- 维度 3: 版本 ---

    def test_dimension_3_port_version(self) -> None:
        assert self._spec().version == "v1.0.0"

    # --- 维度 4: 接口类型（Protocol 同一性）---

    def test_dimension_4_port_interface_type(self) -> None:
        assert self._spec().interface is IsolationManagementServicePort

    # --- 维度 5: 生命周期（SINGLETON——被 CLI/用例捕获无实害）---

    def test_dimension_5_port_lifetime(self) -> None:
        assert self._spec().lifetime == Lifetime.SINGLETON

    # --- 维度 6: 归属 ---

    def test_dimension_6_port_owner(self) -> None:
        assert self._spec().owner == self.EXPECTED_OWNER

    # --- 维度 7: 模块路径 ---

    def test_dimension_7_port_module(self) -> None:
        assert self._spec().module == self.MODULE_PATH

    # --- 维度 8: 标签 ---

    def test_dimension_8_port_tags(self) -> None:
        assert self._spec().tags == self.EXPECTED_TAGS

    # --- 维度 9: impl 可调用 + 产出端口实例 ---

    def test_dimension_9_impl_is_callable(self) -> None:
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, IsolationManagementServicePort)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # --- 维度 10: 实现具备必需方法 ---

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少必需方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # --- 维度 11: Protocol 可运行时检查 ---

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, IsolationManagementServicePort)
