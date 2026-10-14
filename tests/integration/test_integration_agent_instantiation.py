"""Agent 实例化集成与性能测试（Story 5-1 — 真实 Redis 全链路）

验证型集成/性能测试：被测链路已由 Task 2-4 交付，编写后直接转绿为合法
预期；断言活性由变异阶段（阈值突变）背书。

场景：
① 实例化→键存在→读回一致→teardown 按 context 记录的 agent_id 逐键精确
  delete（禁 delete_pattern/flush——多 worker 共享 Redis 实例）
② P95 计时：perf_counter + warmup 剔除 1 次 + 20 采样 +
  statistics.quantiles(n=20)[18] < 200ms（AC-5.1；先例
  tests/acceptance/test_acceptance_docker_sandbox.py L1001-1012）
③ asyncio.gather 10 并发全成功 + 10 agent_id 逐一 exists() 互异
  （AC-5.2/NFR-PERF-04 MVP 档；禁 scan 模式计数——多 worker 共享同一
  Redis 实例会误计并行场景键）

组装纪律（integration 无共享 resolve() fixture 基建——inline resolve 用法
见 test_integration_traceability.py L171-174）：config_loader 经组合根
resolve（零 IO）；仓储用 real_redis 场景级客户端手动组装（先例
test_integration_storage.py L79 RedisAdapter(real_redis)）；事件总线用真实
InMemoryEventBus；用例手动实例化。

xdist_group("agent-instantiation")：与验收侧同组——同 worker 串行化计时
场景（仅保同组串行不保独占 CPU；-n auto 下抖动超标时以 -n 0 结果为准）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_agent_instantiation.py -v
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
from src.domain.entities.agent import AgentRole
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.benchmark,
    pytest.mark.xdist_group("agent-instantiation"),
]


@pytest.fixture
async def assembled(
    real_redis: Any,
) -> AsyncGenerator[tuple[InstantiateAgentUseCase, RedisAgentRepository, Any], None]:
    """手动组装实例化链路（real_redis ping 失败时 conftest 已动态 skip）。

    Yields:
        (用例, 仓储, real_redis 客户端)——仓储供读回契约断言，客户端供键
        断言与 teardown 精确清理
    """
    from src.domain.ports.resolver import resolve

    repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=real_redis))
    case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=repository,
        event_publisher=InMemoryEventBus(),
    )
    yield case, repository, real_redis


# ===================================================================
# 场景 ①: 全链路实例化 → 持久化 → 读回一致
# ===================================================================


class TestFullChainInstantiation:
    """真实 Redis 全链路：实例化→键存在→读回一致→精确清理。"""

    async def test_instantiate_persist_restore(
        self, assembled: tuple[InstantiateAgentUseCase, RedisAgentRepository, Any]
    ) -> None:
        case, repository, client = assembled
        result = await case.execute(role=AgentRole.CEO)
        key = build_key("agent", str(result.agent_id))
        try:
            # 键存在 + TTL 在合理区间（86400 附近，扣除执行耗时）
            assert await client.exists(key) == 1, f"键不存在: {key}"
            ttl = await client.ttl(key)
            assert 86300 < ttl <= 86400, f"TTL 异常: {ttl}"

            # 读回一致（经仓储显式重建）
            restored = await repository.get_by_id(result.agent_id)
            assert restored is not None
            assert restored.agent_id == result.agent_id
            assert restored.role == AgentRole.CEO
            assert restored.name == result.agent.name
            assert restored.responsibilities == result.agent.responsibilities
            assert restored.domain_knowledge == result.agent.domain_knowledge
        finally:
            # teardown: 仅精确删除本测试创建的键（禁通配/flush）
            await client.delete(key)

    async def test_repository_exists_and_delete_roundtrip(
        self, assembled: tuple[InstantiateAgentUseCase, RedisAgentRepository, Any]
    ) -> None:
        """仓储 exists/delete 在真实 Redis 上的幂等行为。"""
        case, repository, client = assembled
        result = await case.execute(role=AgentRole.CEO)
        agent_id = result.agent_id
        try:
            assert await repository.exists(agent_id) is True
            await repository.delete(agent_id)
            assert await repository.exists(agent_id) is False
            assert await repository.get_by_id(agent_id) is None
            await repository.delete(agent_id)  # 幂等
        finally:
            await client.delete(build_key("agent", str(agent_id)))


# ===================================================================
# 场景 ②: P95 性能门禁（AC-5.1）
# ===================================================================


class TestP95Latency:
    """实例化全链路 P95 < 200ms（warmup 剔除 1 次 + 20 采样）。"""

    async def test_p95_under_200ms(self, assembled: tuple[InstantiateAgentUseCase, RedisAgentRepository, Any]) -> None:
        case, _, client = assembled
        created_keys: list[str] = []
        try:
            # warmup: 1 次不计入样本（消除首样本连接池/配置加载冷启动污染）
            warmup = await case.execute(role=AgentRole.CEO)
            created_keys.append(build_key("agent", str(warmup.agent_id)))

            latencies: list[float] = []
            for _ in range(20):
                started = time.perf_counter()
                result = await case.execute(role=AgentRole.CEO)
                latencies.append((time.perf_counter() - started) * 1000)  # ms
                created_keys.append(build_key("agent", str(result.agent_id)))

            # N=20 样本 P95: quantiles(n=20)[18] 恰为第 19/20 分位
            p95 = statistics.quantiles(latencies, n=20)[18]
            assert p95 < 200, f"实例化全链路 P95={p95:.1f}ms 超阈值 200ms (样本: {[f'{x:.1f}' for x in sorted(latencies)]})"
        finally:
            for key in created_keys:
                await client.delete(key)


# ===================================================================
# 场景 ③: 10 并发实例化（AC-5.2 / NFR-PERF-04 MVP 档）
# ===================================================================


class TestTenConcurrentInstantiations:
    """asyncio.gather 10 并发全成功 + agent_id 互异 + 逐一 exists()。"""

    async def test_10_concurrent_all_success_distinct_keys_exist(
        self, assembled: tuple[InstantiateAgentUseCase, RedisAgentRepository, Any]
    ) -> None:
        case, _, client = assembled
        results = await asyncio.gather(*(case.execute(role=AgentRole.CEO) for _ in range(10)))
        agent_ids = [result.agent_id for result in results]
        try:
            assert len(results) == 10
            assert all(isinstance(agent_id, uuid.UUID) for agent_id in agent_ids)
            assert len(set(agent_ids)) == 10, "10 个 agent_id 必须全部互异"

            # 逐一 exists() 断言（禁 scan 模式计数——多 worker 共享实例会误计）
            for agent_id in agent_ids:
                key = build_key("agent", str(agent_id))
                assert await client.exists(key) == 1, f"并发实例化键缺失: {key}"
        finally:
            for agent_id in agent_ids:
                await client.delete(build_key("agent", str(agent_id)))
