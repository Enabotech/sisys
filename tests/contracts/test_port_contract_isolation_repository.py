"""Story 5.4: IsolationRepository 端口契约测试（11 维度）

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
    poetry run pytest tests/contracts/test_port_contract_isolation_repository.py -v
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.isolation_repository import IsolationRepository
from src.domain.ports.registry import Lifetime


class _DummyResolver:
    """测试用最小 Resolver 占位符。

    isolation_repository 工厂注入依赖 redis_adapter——以零 IO 的
    RedisAdapter(fakeredis 客户端) 替身提供（契约维度仅验证实例化与方法面，
    不触真实连接）。
    """

    def resolve(self, name: str) -> Any:
        if name == "redis_adapter":
            import fakeredis.aioredis

            from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

            return RedisAdapter(redis_client=fakeredis.aioredis.FakeRedis(decode_responses=True))
        raise KeyError(f"未注册的端口: {name}")


class TestIsolationRepositoryPortContract:
    """isolation_repository 端口契约（11 维度——agent_repository 样板同款）。"""

    PORT_NAME = "isolation_repository"
    IMPL_CLS_NAME = "RedisIsolationRepository"
    MODULE_PATH = "src.infrastructure.storage.redis.redis_isolation_repository"
    EXPECTED_TAGS = ("redis", "agent", "isolation")
    EXPECTED_OWNER = "platform"
    REQUIRED_METHODS = ["save", "get_by_agent_id", "delete", "exists"]

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
        assert self._spec().interface is IsolationRepository

    # --- 维度 5: 生命周期（DC-7: SINGLETON——D7 评估落地）---

    def test_dimension_5_port_lifetime(self) -> None:
        assert self._spec().lifetime == Lifetime.SINGLETON, (
            "isolation_repository 必须 SINGLETON（Story 5.4 DC-7：无状态仓储构造零 IO，"
            "被 SINGLETON 服务捕获无 captive 实害——D7 从源头避免）"
        )

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
        assert isinstance(instance, IsolationRepository)
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
        assert isinstance(instance, IsolationRepository)
