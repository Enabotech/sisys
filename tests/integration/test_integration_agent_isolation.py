"""Story 5.4: EIP 弹性隔离协议基础 — 集成测试（真实 Redis 全链 + 性能三指标）

五场景（真实 Redis 6380 门控 ping 失败动态 skip + 手动组装全链）:
① 全链: 真实 InstantiateAgentUseCase（真实四依赖——隔离键必须真实写入）→
   instantiate → 隔离键 L4 断言 → 服务切换 L3 → 键 L3 + recording 恰一次事件 →
   双键 teardown + exists 复核
② P95: get_isolation_state 服务全链计时（443 守卫 + 隔离态读两次真实读，
   含协议解析与 VO 重建）；_PERF_CACHE 单槽缓存 helper（供验收 AC-5.1/5.2
   委托共享——同 xdist_group 同 worker 缓存命中，禁 20 采样双跑；helper 内
   sample_keys 双键登记即时清理）
③ 持久化成功率: 同批派生 20/20（helper 每轮 initialize+读回即成功率采样面）
④ 并发 10: 10 agent gather 并发 init+switch+get 全成功 + 目标等级互异
   （奇数 L3 偶数 L2——串扰在主断言即可红）
⑤ 事件真实发布链路: resolve 真实 event_publisher（DualChannelEventBus）+
   真实服务 switch → PG event_outbox 落行断言（精确查询禁全表计数；
   RabbitMQ 缺席不影响——reliable 通道 publish 只写 PG outbox，实际投递归
   AsyncOutboxPoller 异步侧）；发布面口径差声明（场景①recording 替身 vs
   场景⑤生产 outbox）随 docstring

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_agent_isolation.py -v
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

import pytest

from src.domain.entities.agent import AgentRole
from src.domain.events.enums import IsolationLevel
from src.infrastructure.storage.redis.key_builder import build_key

# 集成侧文件级 pytestmark（集成先例 profile_loading——与验收侧场景级各自对齐
# 本层先例，R1-F16 口径注记）；benchmark 文件级（全文件皆计时/性能语义）
pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.benchmark,
    pytest.mark.xdist_group("agent-isolation-perf"),
]

# P95 阈值同源派生常量（一处定义——验收侧 import 本常量断言，禁双真源）
ISOLATION_P95_LIMIT_SECONDS = 0.1

# 采样规格（warmup 1 + 20 采样——与 5-3 集成先例同款）
PERF_WARMUP_ROUNDS = 1
PERF_SAMPLE_ROUNDS = 20

#: P95/成功率采样缓存（模块级单槽——集成场景②③与验收 AC-5.1/5.2 共享同批
#: 结果，同 xdist_group 同 worker 串行保证缓存命中；禁 20 采样双跑拖慢套件）
_PERF_CACHE: dict[str, Any] = {}


class _RecordingEventPublisher:
    """手写 duck-typing 事件捕获类（直接实现 EventPublisher 端口契约——5-3 先例）。

    场景①/④ 的发布面替身（隔离键真实写入是主断言，事件发布经 recording 计数
    断言「恰一次」）；场景⑤换真实 DualChannelEventBus 验证生产 outbox 链路——
    两场景发布面口径差是设计分层非矛盾。
    """

    def __init__(self) -> None:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self._publish_result_cls = PublishResult
        self._channel_result_cls = ChannelResult
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        import uuid as uuid_module

        self.published_events.append(event)
        return self._publish_result_cls(
            event_id=str(uuid_module.uuid4()),
            results=(self._channel_result_cls(channel_name="inmemory", success=True),),
        )


def _assemble_real_chain(redis_client: Any, publisher: Any = None) -> dict[str, Any]:
    """手动组装真实四依赖链（场景级客户端——禁 resolve 发命令纪律）。

    Args:
        redis_client: 场景级真实 Redis 客户端（real_redis fixture）
        publisher: 事件发布器（默认 _RecordingEventPublisher；场景⑤传真实总线）

    Returns:
        组装字典（use_case/isolation_service/agent_repository/isolation_repository/
        recorder 四键）
    """
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    recorder = publisher if publisher is not None else _RecordingEventPublisher()
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=recorder,
        agent_config_loader=resolve("agent_config_loader"),
    )
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    return {
        "use_case": use_case,
        "isolation_service": isolation_service,
        "agent_repository": agent_repository,
        "isolation_repository": isolation_repository,
        "recorder": recorder,
    }


async def sample_isolation_perf(redis_client: Any) -> dict[str, Any]:
    """隔离检查 P95 + 持久化成功率采样（warmup 1 + 20 采样；双键登记清理）。

    计时面 = get_isolation_state 服务全链（443 存在性守卫 + 隔离态读共两次
    真实 Redis 读，含协议解析与 IsolationState VO 重建——DC-11 口径）；
    成功率采样面 = 每轮 initialize+读回（等级读回 == L4 记成功，warmup 不计
    入分母——分母 20 分子 20）。

    Args:
        redis_client: 场景级真实 Redis 客户端

    Returns:
        {"p95_seconds", "success_count", "total_count", "samples"}——验收侧
        AC-5.1/5.2 经缓存共享同批结果（_PERF_CACHE 命中即返）
    """
    if "result" in _PERF_CACHE:
        cached: dict[str, Any] = _PERF_CACHE["result"]
        return cached

    chain = _assemble_real_chain(redis_client)
    use_case = chain["use_case"]
    service = chain["isolation_service"]

    latencies: list[float] = []
    success_count = 0
    sample_keys: list[str] = []  # 双键登记（每轮 instantiate 产生 agent+isolation 键）

    async def _one_round(record: bool = True) -> float:
        nonlocal success_count
        instantiation = await use_case.execute(role=AgentRole.CEO)
        sample_keys.append(build_key("agent", str(instantiation.agent_id)))
        sample_keys.append(build_key("isolation", str(instantiation.agent_id)))
        started = time.perf_counter()
        state = await service.get_isolation_state(instantiation.agent_id)
        elapsed = time.perf_counter() - started
        if record:
            if state.current_level is IsolationLevel.L4_HARD:
                success_count += 1
        return elapsed

    for _ in range(PERF_WARMUP_ROUNDS):
        await _one_round(record=False)  # warmup: 计时与成功率分母均不含
    for _ in range(PERF_SAMPLE_ROUNDS):
        latencies.append(await _one_round(record=True))

    if sample_keys:  # teardown: 采样键精确清理（helper 内轮次不经场景 teardown）
        await redis_client.delete(*sample_keys)

    result: dict[str, Any] = {
        "p95_seconds": statistics.quantiles(latencies, n=PERF_SAMPLE_ROUNDS)[18],
        "success_count": success_count,
        "total_count": PERF_SAMPLE_ROUNDS,
        "samples": latencies,
    }
    _PERF_CACHE["result"] = result
    return result


# ===================================================================
# 场景①: 全链（instantiate → 隔离键 L4 → 切换 L3 → 事件恰一次）
# ===================================================================


class TestFullChainIsolation:
    """真实四依赖全链（隔离键真实性硬依赖——验收同款组装）。"""

    async def test_instantiate_switch_full_chain(self, real_redis: Any) -> None:
        """instantiate → 隔离键 L4 → 服务切 L3 → 键 L3 + 事件恰一次 → 双键清理。"""
        import json

        chain = _assemble_real_chain(real_redis)
        use_case = chain["use_case"]
        service = chain["isolation_service"]
        recorder = chain["recorder"]

        # 预绑定（异常路径 finally 守卫——写键后任意失败仍清理双键）
        agent_id: Any = None
        isolation_key: str | None = None
        try:
            # 1. 实例化即 L4（端到端锚——组合根 lambda 四依赖的运行时背书）
            instantiation = await use_case.execute(role=AgentRole.CEO)
            agent_id = instantiation.agent_id
            isolation_key = build_key("isolation", str(agent_id))
            raw = await real_redis.hget(isolation_key, "latest")
            assert raw is not None, "实例化后隔离键必须真实出现"
            assert json.loads(raw)["current_level"] == "L4"

            # 2. 服务切换 L3 → Redis 状态一致 + 事件恰一次
            result = await service.switch_isolation_level(agent_id, IsolationLevel.L3_SOFT, "集成全链切换")
            assert result.switched is True
            payload = json.loads(await real_redis.hget(isolation_key, "latest"))
            assert payload["current_level"] == "L3"
            events = [e for e in recorder.published_events if type(e).__name__ == "IsolationLevelSwitched"]
            assert len(events) == 1, f"事件应恰发布一次（实际 {len(events)}）"
            assert events[0].target_level is IsolationLevel.L3_SOFT
        finally:
            # 3. 双键 teardown（自包含纪律——写键后异常路径覆盖）
            if agent_id is not None:
                await real_redis.delete(build_key("agent", str(agent_id)), build_key("isolation", str(agent_id)))
        assert agent_id is not None  # 成功路径必达（Optional 收窄）
        assert isolation_key is not None
        assert not await real_redis.exists(build_key("agent", str(agent_id))), "agent 键未清理"
        assert not await real_redis.exists(isolation_key), "隔离键未清理"


# ===================================================================
# 场景②/③: P95 + 持久化成功率（_PERF_CACHE 计时 helper）
# ===================================================================


class TestIsolationPerformance:
    """性能三指标前两项（AC-5.1/5.2——验收侧经缓存委托共享本批结果）。"""

    async def test_get_isolation_state_p95_under_100ms(self, real_redis: Any) -> None:
        """P95: 服务全链 20 采样 quantiles[18] < 0.1s（warmup 剔除 1 次）。"""
        result = await sample_isolation_perf(real_redis)
        p95_ms = result["p95_seconds"] * 1000
        assert result["p95_seconds"] < ISOLATION_P95_LIMIT_SECONDS, (
            f"隔离检查 P95={p95_ms:.1f}ms 超阈值 {ISOLATION_P95_LIMIT_SECONDS * 1000:.0f}ms"
        )

    async def test_persistence_success_rate_100_percent(self, real_redis: Any) -> None:
        """持久化成功率: 20 次连续 initialize+读回全成功（分母 20 分子 20）。"""
        result = await sample_isolation_perf(real_redis)
        assert result["total_count"] == PERF_SAMPLE_ROUNDS
        assert result["success_count"] == PERF_SAMPLE_ROUNDS, (
            f"持久化成功率不足 100%: {result['success_count']}/{result['total_count']}"
        )


# ===================================================================
# 场景④: 并发 10（互异目标等级——键隔离判别力）
# ===================================================================


class TestConcurrentIsolation:
    """并发隔离 Agent≥10（NFR-PERF-04 MVP 档）。"""

    async def test_ten_agents_concurrent_init_switch_get(self, real_redis: Any) -> None:
        """10 agent gather 并发 init+switch+get 全成功 + 奇偶互异等级互不串扰。"""
        chain = _assemble_real_chain(real_redis)
        use_case = chain["use_case"]
        service = chain["isolation_service"]

        # key 即时登记（写键即入册——gather 部分失败时已完成写键仍可清理）
        keys: list[str] = []

        async def _one_agent(index: int) -> dict[str, Any]:
            instantiation = await use_case.execute(role=AgentRole.CEO)
            keys.append(build_key("agent", str(instantiation.agent_id)))
            keys.append(build_key("isolation", str(instantiation.agent_id)))
            target = IsolationLevel.L3_SOFT if index % 2 == 0 else IsolationLevel.L2_COLLAB
            switch = await service.switch_isolation_level(instantiation.agent_id, target, f"并发切换-{index}")
            state = await service.get_isolation_state(instantiation.agent_id)
            return {"agent_id": instantiation.agent_id, "target": target, "switch": switch, "state": state}

        try:
            results = list(await asyncio.gather(*(_one_agent(i) for i in range(10))))
            assert len(results) == 10
            for item in results:
                assert item["switch"].switched is True
                assert item["state"].current_level is item["target"], (
                    f"agent {item['agent_id']} 状态串扰: 期望 {item['target'].value}"
                )
            # 互异覆盖断言（奇偶两族均有代表）
            assert {item["target"] for item in results} == {IsolationLevel.L3_SOFT, IsolationLevel.L2_COLLAB}
        finally:
            # 双键 teardown（登记面清理——gather 中途失败时已完成 agent 的键仍覆盖）
            if keys:
                await real_redis.delete(*keys)
        for key in keys:
            assert not await real_redis.exists(key), f"并发场景键未清理: {key}"


# ===================================================================
# 场景⑤: 事件真实发布链路（生产 DualChannelEventBus → PG outbox 落行）
# ===================================================================


class TestRealEventPublishingOutbox:
    """切换事件经真实总线 reliable 通道落 PG outbox（生产发布面验证）。"""

    async def test_switch_event_lands_in_pg_outbox(self, real_redis: Any) -> None:
        """真实 event_publisher switch → event_outbox 落 IsolationLevelSwitched 行。

        RabbitMQ 缺席不影响本场景（reliable 通道 publish 只写 PG outbox，实际
        投递归 AsyncOutboxPoller 异步侧——R1-F31 注记）；PG 缺席动态 skip。
        """
        from src.domain.ports.resolver import resolve

        real_publisher = resolve("event_publisher")  # 生产 DualChannelEventBus
        chain = _assemble_real_chain(real_redis, publisher=real_publisher)
        instantiation = await chain["use_case"].execute(role=AgentRole.CEO)
        agent_id = instantiation.agent_id
        isolation_key = build_key("isolation", str(agent_id))

        from tests.environments import get_test_env

        env_pg = get_test_env().postgres
        try:
            from src.infrastructure.config.postgresql import PostgreSQLConfig
            from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
        except Exception as exc:  # PG 基建缺失（非连接失败——连接失败在测试体内暴露）
            pytest.skip(f"PostgreSQL 不可用: {exc}")

        try:
            result = await chain["isolation_service"].switch_isolation_level(
                agent_id, IsolationLevel.L2_COLLAB, "真实发布链路验证"
            )
            assert result.switched is True

            manager = PostgreSQLManager(
                PostgreSQLConfig(
                    host=env_pg.host,
                    port=env_pg.port,
                    database=env_pg.database,
                    username=env_pg.username,
                    password=env_pg.password,
                )
            )
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession

            # 连接级预检（PG 基建已装但服务未运行 → skip 而非红——对齐 Redis 侧
            # ping 门控形态；短超时防拖慢 PG 在位的常规运行，dispose 防绑循环引擎泄漏）
            try:
                async with AsyncSession(manager.get_async_engine()) as probe_session:
                    await probe_session.execute(text("SELECT 1"))
            except Exception as exc:
                await manager.get_async_engine().dispose()
                pytest.skip(f"PostgreSQL 连接不可达: {exc}")

            async with AsyncSession(manager.get_async_engine(), expire_on_commit=False) as session:
                query = text(
                    "SELECT event_id, event_type, status FROM event_outbox "
                    "WHERE event_type = 'IsolationLevelSwitched' AND payload->>'aggregate_id' = :agent_id "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                row = (await session.execute(query, {"agent_id": str(agent_id)})).fetchone()
            assert row is not None, f"event_outbox 未落 IsolationLevelSwitched 行（agent_id={agent_id}——真实发布链路断裂）"
            assert row[0] is not None  # event_id
            assert row[1] == "IsolationLevelSwitched"
        finally:
            # outbox 追加语义无清理面；仅清理本场景 Redis 双键
            await real_redis.delete(build_key("agent", str(agent_id)), isolation_key)
