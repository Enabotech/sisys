"""Agent 档案加载集成与性能测试（Story 5-2 — 真实 Redis + 真实文件全链路）

验证型集成/性能测试：被测链路已由 Task 2-4 交付，编写后直接转绿为合法
预期；断言活性由变异阶段（阈值突变）背书。

场景：
① instantiate→load-profile 全链路：六档案内容非空 + 23 工具 + 计量断言 →
  teardown 按 context 记录的 agent_id 逐键精确 delete + 收尾 scan_iter
  复核残留 0（禁 delete_pattern/flush——多 worker 共享 Redis 实例）
② P95 计时：perf_counter + warmup 剔除 1 次 + 20 采样 +
  statistics.quantiles(n=20)[18] < 500ms（AC-5.1；先例
  tests/acceptance/test_acceptance_docker_sandbox.py L1001-1012）
③ 20 次重复加载成功率 100%（同一 agent_id 复用——幂等只读设计行为，AC-5.2）

组装纪律（5-1 test_integration_agent_instantiation.py 同款）：仓储用
real_redis 场景级客户端手动组装；agent_profile_loader / skill_selector 经
组合根 resolve（本地静态文件只读、无连接构造，跨循环安全）；事件总线用
真实 InMemoryEventBus；用例手动实例化（禁 resolve 用例端口——SINGLETON
redis_client 跨循环死连接）。

xdist_group("agent-profile-loading")：与验收侧同组——同 worker 串行化计时
场景（仅保同组串行不保独占 CPU；-n auto 下抖动超标时以 -n 0 结果为准）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_agent_profile_loading.py -v
"""

from __future__ import annotations

import statistics
import time
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
    pytest.mark.xdist_group("agent-profile-loading"),
]


@pytest.fixture
async def assembled(real_redis: Any) -> AsyncGenerator[tuple[Any, Any, Any], None]:
    """手动组装 instantiate + load-profile 双用例链路（real_redis ping 失败已动态 skip）。

    Yields:
        (实例化用例, 档案加载用例, real_redis 客户端)
    """
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
    from src.domain.ports.resolver import resolve

    repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=real_redis))
    instantiate_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=repository,
        event_publisher=InMemoryEventBus(),
    )
    load_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=repository,
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    yield instantiate_case, load_case, real_redis


# ===================================================================
# 场景 ①: instantiate → load-profile 全链路
# ===================================================================


class TestFullChainProfileLoading:
    """真实 Redis + 真实文件全链路：实例化→档案加载→内容断言→精确清理。"""

    async def test_instantiate_then_load_profile_full_chain(self, assembled: tuple[Any, Any, Any]) -> None:
        """全链路：六档案非空 + 23 工具 + 计量一致性 + 收尾 scan 复核零残留。"""
        instantiate_case, load_case, client = assembled
        instantiation = await instantiate_case.execute(role=AgentRole.CEO)
        agent_id = instantiation.agent_id
        key = build_key("agent", str(agent_id))
        try:
            result = await load_case.execute(agent_id=agent_id)

            # 六档案内容非空（真实文件读取）
            profile = result.profile
            for field_name in ("identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"):
                content = getattr(profile, field_name)
                assert isinstance(content, str) and content.strip(), f"{field_name} 应非空"

            # 23 个 ACTIVE 工具（真实 L1 元数据）
            assert len(result.tools_l1) == 23
            assert all(meta.status == "active" for meta in result.tools_l1)

            # 计量一致性（同款口径复算）
            l1_view = "\n".join(f"{meta.tool_name}: {meta.description}" for meta in result.tools_l1)
            expected = (len(profile.identity) + len(profile.soul) + len(l1_view)) // 4
            assert result.startup_context_tokens == expected
            assert result.startup_context_tokens <= 1700, "总量预算 ≤1700"
        finally:
            # teardown: 仅精确删除本测试创建的键（禁通配/flush）
            await client.delete(key)
            # 收尾复核：sisys:agent:* 残留为 0（本测试不产生跨键副作用）
            remaining = [k async for k in client.scan_iter(match="sisys:agent:*", count=100)]
            assert remaining == [], f"残留键未清理: {remaining}"


# ===================================================================
# 场景 ②: P95 性能门禁（AC-5.1）
# ===================================================================


class TestP95Latency:
    """档案加载全链路 P95 < 500ms（warmup 剔除 1 次 + 20 采样，同一 agent_id 复用）。"""

    async def test_p95_under_500ms(self, assembled: tuple[Any, Any, Any]) -> None:
        """P95 经 quantiles(n=20)[18] 计算（对典型 <20ms 链路约 25 倍余量）。"""
        instantiate_case, load_case, client = assembled
        instantiation = await instantiate_case.execute(role=AgentRole.CEO)
        agent_id = instantiation.agent_id
        try:
            # warmup: 1 次不计入样本（消除首样本文件系统页缓存/L1 缓存冷启动污染）
            await load_case.execute(agent_id=agent_id)

            latencies: list[float] = []
            for _ in range(20):
                started = time.perf_counter()
                await load_case.execute(agent_id=agent_id)
                latencies.append((time.perf_counter() - started) * 1000)  # ms

            # N=20 样本 P95: quantiles(n=20)[18] 恰为第 19/20 分位
            p95 = statistics.quantiles(latencies, n=20)[18]
            assert p95 < 500, f"档案加载全链路 P95={p95:.1f}ms 超阈值 500ms (样本: {[f'{x:.1f}' for x in sorted(latencies)]})"
        finally:
            await client.delete(build_key("agent", str(agent_id)))


# ===================================================================
# 场景 ③: 20 次重复加载成功率（AC-5.2——幂等只读）
# ===================================================================


class TestTwentyRepeatedLoads:
    """同一 agent_id 20 次重复加载全部成功（确定性文件 IO + L1 内存缓存命中）。"""

    async def test_20_repeated_loads_all_succeed(self, assembled: tuple[Any, Any, Any]) -> None:
        """计数 == 20 全成功 + agent_id 一致 + 事件计数 20（重复发布语义）。"""
        from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
        from src.domain.events.agent_events import AgentProfileLoaded
        from src.domain.ports.resolver import resolve

        instantiate_case, _, client = assembled
        instantiation = await instantiate_case.execute(role=AgentRole.CEO)
        agent_id = instantiation.agent_id
        try:
            # 独立总线计数（assembled 的 load_case 总线也捕获，此处显式组装验证事件面）
            event_bus = InMemoryEventBus()
            load_case = LoadAgentProfileUseCase(
                profile_loader=resolve("agent_profile_loader"),
                repository=RedisAgentRepository(adapter=RedisAdapter(redis_client=client)),
                skill_selector=resolve("skill_selector"),
                event_publisher=event_bus,
            )

            results = []
            for _ in range(20):
                results.append(await load_case.execute(agent_id=agent_id))

            assert len(results) == 20
            assert all(result is not None and result.agent_id == agent_id for result in results)
            # 每次加载发布一个事件（幂等只读指不改变被读状态，事件重复发布由 event_id 去重）
            profile_events = [e for e in event_bus.published_events if isinstance(e, AgentProfileLoaded)]
            assert len(profile_events) == 20
        finally:
            await client.delete(build_key("agent", str(agent_id)))
