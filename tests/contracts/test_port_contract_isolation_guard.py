"""isolation_guard_service 端口契约测试（Story 5.5 — Agent 三重硬隔离保证）

11 维度契约验证（与 isolation_management_service 契约同款结构）:
1. test_dimension_1_port_is_registered — 组合根注册非 None
2. test_dimension_2_port_name — 端口名 isolation_guard_service
3. test_dimension_3_port_version — 版本 v1.0.0
4. test_dimension_4_port_interface_type — 接口 IsolationGuardPort
5. test_dimension_5_port_lifetime — SINGLETON（无状态纯判定服务）
6. test_dimension_6_port_owner — platform
7. test_dimension_7_port_module — 实现模块路径
8. test_dimension_8_port_tags — ("agent", "isolation", "security")
9. test_dimension_9_impl_is_callable — 工厂可调用（9a）+ DummyResolver 实例化
   isinstance（9b——三依赖零 IO 替身）
10. test_dimension_10_implementation_has_required_methods — 三方法面
11. test_dimension_11_protocol_is_runtime_checkable — 端口运行时可检查

Run with:
    poetry run pytest tests/contracts/test_port_contract_isolation_guard.py -v
"""

from __future__ import annotations

from typing import Any

from src.application.ports.isolation_guard import IsolationGuardPort


class _DummyResolver:
    """测试用最小 Resolver 占位符（isolation_guard_service 工厂三依赖零 IO 替身）。

    isolation_management_service 经组合根 resolve（Agent 系区段依赖序——
    guard 注册晚于 isolation_management_service）；agent_repository /
    agent_config_loader 以 fakeredis/真实无状态实例提供（契约维度仅验证
    实例化与方法面，不触真实连接）。
    """

    def resolve(self, name: str) -> Any:
        from src.domain.ports.resolver import resolve as real_resolve

        if name == "isolation_management_service":
            return real_resolve(name)
        if name == "agent_repository":
            import fakeredis.aioredis

            from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
            from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

            return RedisAgentRepository(adapter=RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True)))
        if name == "agent_config_loader":
            from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

            return YamlAgentConfigLoader()
        raise KeyError(f"未注册的端口: {name}")


class TestIsolationGuardPortContract:
    """isolation_guard_service 端口契约 11 维度。"""

    PORT_NAME = "isolation_guard_service"
    IMPL_CLS_NAME = "IsolationGuardService"
    MODULE_PATH = "src.application.services.isolation_guard_service"
    EXPECTED_TAGS = ("agent", "isolation", "security")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["ensure_agent_executable", "ensure_agent_access", "ensure_tool_access"]

    def _spec(self) -> Any:
        from src.domain.ports.registry import _global_registry

        return _global_registry.get(self.PORT_NAME)

    # ===== 维度 1: 注册 =====

    def test_dimension_1_port_is_registered(self) -> None:
        assert self._spec() is not None, f"端口 {self.PORT_NAME} 未在组合根注册"

    # ===== 维度 2: 端口名 =====

    def test_dimension_2_port_name(self) -> None:
        assert self._spec().name == self.PORT_NAME

    # ===== 维度 3: 版本 =====

    def test_dimension_3_port_version(self) -> None:
        assert self._spec().version == "v1.0.0"

    # ===== 维度 4: 接口类型 =====

    def test_dimension_4_port_interface_type(self) -> None:
        assert self._spec().interface is IsolationGuardPort

    # ===== 维度 5: 生命周期 =====

    def test_dimension_5_port_lifetime(self) -> None:
        from src.domain.ports.registry import Lifetime

        assert self._spec().lifetime == Lifetime.SINGLETON

    # ===== 维度 6: 所有者 =====

    def test_dimension_6_port_owner(self) -> None:
        assert self._spec().owner == self.EXPECTED_OWNER

    # ===== 维度 7: 模块路径 =====

    def test_dimension_7_port_module(self) -> None:
        assert self._spec().module == self.MODULE_PATH

    # ===== 维度 8: 标签 =====

    def test_dimension_8_port_tags(self) -> None:
        assert self._spec().tags == self.EXPECTED_TAGS

    # ===== 维度 9: 工厂可调用（9a）+ DummyResolver 实例化（9b） =====

    def test_dimension_9a_impl_is_callable(self) -> None:
        assert callable(self._spec().impl)

    def test_dimension_9b_impl_instantiates_via_dummy_resolver(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, IsolationGuardPort)
        assert type(instance).__name__ == self.IMPL_CLS_NAME

    # ===== 维度 10: 实现方法面 =====

    def test_dimension_10_implementation_has_required_methods(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        for method_name in self.REQUIRED_METHODS:
            method = getattr(instance, method_name, None)
            assert callable(method), f"实现缺少方法: {method_name}"

    # ===== 维度 11: 端口运行时可检查 =====

    def test_dimension_11_protocol_is_runtime_checkable(self) -> None:
        instance = self._spec().impl(_DummyResolver())
        assert isinstance(instance, IsolationGuardPort)
