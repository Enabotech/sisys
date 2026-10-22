"""Story 5.1: agent_instantiation_use_case 端口契约测试（11 维度）

参考样板：tests/contracts/test_port_contract_tool_execution_repository.py

11 维度测试方法名清单：
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
"""

from __future__ import annotations

from typing import Any

from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
from src.domain.ports.registry import Lifetime


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    agent_instantiation_use_case 工厂注入四依赖（Story 5-4 追加
    isolation_management_service）：agent_config_loader / agent_repository /
    event_publisher / isolation_management_service——全部以零 IO 替身提供
    （契约维度仅验证实例化与方法面，不触真实连接）。
    """

    def resolve(self, name: str) -> Any:
        if name == "agent_config_loader":
            from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

            return YamlAgentConfigLoader()
        if name == "agent_repository":
            import fakeredis.aioredis

            from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
            from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

            return RedisAgentRepository(adapter=RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True)))
        if name == "event_publisher":
            from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

            return InMemoryEventBus()
        if name == "isolation_management_service":
            import fakeredis.aioredis

            from src.application.services.isolation_management_service import IsolationManagementService
            from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
            from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

            fake_adapter = RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True))
            return IsolationManagementService(
                isolation_repository=RedisIsolationRepository(adapter=fake_adapter),
                agent_repository=self.resolve("agent_repository"),
                event_publisher=self.resolve("event_publisher"),
                agent_config_loader=self.resolve("agent_config_loader"),
            )
        raise KeyError(f"未注册的端口: {name}")


class TestAgentInstantiationUseCasePortContract:
    """agent_instantiation_use_case 端口契约测试 11 维度"""

    PORT_NAME = "agent_instantiation_use_case"
    IMPL_CLS_NAME = "InstantiateAgentUseCase"
    MODULE_PATH = "src.application.use_cases.agent_instantiation"
    EXPECTED_TAGS = ("agent",)
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["execute"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # 维度 1: 端口已注册
    def test_dimension_1_port_is_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未注册"

    # 维度 2: 端口名称
    def test_dimension_2_port_name(self) -> None:
        assert self._spec().name == self.PORT_NAME

    # 维度 3: 端口版本
    def test_dimension_3_port_version(self) -> None:
        assert self._spec().version == "v1.0.0"

    # 维度 4: interface 绑定自身类型（对齐 orchestration_service 先例）
    def test_dimension_4_port_interface_type(self) -> None:
        assert self._spec().interface is InstantiateAgentUseCase

    # 维度 5: 生命周期
    def test_dimension_5_port_lifetime(self) -> None:
        assert self._spec().lifetime == Lifetime.SINGLETON

    # 维度 6: 端口 owner
    def test_dimension_6_port_owner(self) -> None:
        assert self._spec().owner == self.EXPECTED_OWNER

    # 维度 7: 实现模块路径
    def test_dimension_7_port_module(self) -> None:
        assert self._spec().module == self.MODULE_PATH

    # 维度 8: 端口 tags
    def test_dimension_8_port_tags(self) -> None:
        assert self._spec().tags == self.EXPECTED_TAGS

    # 维度 9a: impl 工厂可调用
    def test_dimension_9_impl_is_callable(self) -> None:
        assert callable(self._spec().impl)

    # 维度 9b: impl 工厂产出 isinstance 声明接口
    def test_dimension_9b_impl_produces_port_instance(self) -> None:
        spec = self._spec()
        instance = spec.impl(_DummyResolver())
        assert isinstance(instance, InstantiateAgentUseCase)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # 维度 10: 实现类具备 REQUIRED_METHODS
    def test_dimension_10_implementation_has_required_methods(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        for method in self.REQUIRED_METHODS:
            assert hasattr(instance, method), f"实现缺少方法: {method}"
            assert callable(getattr(instance, method)), f"方法不可调用: {method}"

    # 维度 11: 接口可 runtime 校验（interface 为具体类，isinstance 天然可用）
    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, InstantiateAgentUseCase)


__all__ = ["TestAgentInstantiationUseCasePortContract"]
