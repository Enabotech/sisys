"""集成测试：Story 5.11 SAP 协议——真实 Redis 黑板桥 + 性能三锚。

redis marker 分档（AC-5 钦定）: 文件级 [integration, xdist_group]——TestRealRedisBlackboardBridge
类级叠加 redis（真实 Redis 依赖归此类）；TestSAPPerformance 类级不挂 redis（进程内性能
与 Redis 无关——挂了会让 -m "not redis" 环境连性能三锚一并排除）；xdist_group
"sap-protocol-perf" 与验收文件逐字同组（loadgroup 同 worker 串行是 _PERF_CACHE 命中前提）。

性能口径声明（5-8 DC-8④ 形态四注记）:
1. 进程内口径——send→handler 收到全程（校验+入队+异步出队+handler 调用），本地进程
   µs 级；200ms 门是回归绊线非容量预算（网络传输是 V2+ 面——OD-4 部署形态知悉注记）。
2. 绊线定位——门限取 epics L1923/L1924 钦定值，两数量级裕量（本地实测 µs 级）。
3. 20 样本方差知悉——quantiles(latencies, n=20)[18] exclusive 口径（5-8/5-9/5-10 同款），
   小样本方差在两个数量级裕量下不构成判定风险。
4. 序列化满载口径——15 字段全显式实例（最大体积形态）dump+validate 往返。

正向锚口径: 采样轮 handler 收到计数 == warmup 1 + 采样 20 == 21（防静默跳过假绿）；
并发轮 50/50 零丢失 + 处理完成后队列清空（积压归零——NFR-IF-03 积压口径的行为面承载）。

Run with:
    poetry run pytest tests/integration/test_integration_sap_protocol.py -v
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.events.enums import IsolationLevel
from src.interfaces.sap.bus import InProcessSAPBus, deserialize, serialize
from src.interfaces.sap.message import SAPMessage
from src.interfaces.sap.types import MessagePriority, MessageType

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group("sap-protocol-perf"),
]

# P95 三锚阈值常量（单源定义——验收侧 import 本常量断言，禁双真源；epics L1923
# 消息传递 P95<200ms / L1924 序列化 P95<50ms / L1925 并发≥50——本地进程内 µs 级，
# 两门均有数量级裕量）
SAP_DELIVERY_P95_LIMIT_SECONDS = 0.2
SAP_SERIALIZATION_P95_LIMIT_SECONDS = 0.05
SAP_CONCURRENCY_FLOOR = 50

#: 采样规模（P95 = quantiles(latencies, n=20)[18] exclusive——5-8/5-9/5-10 同款口径）
SAP_SAMPLE_ROUNDS = 20

#: 委托缓存（集成/验收逐字同组 loadgroup 同 worker 串行——命中或首次采样形态）
_PERF_CACHE: dict[str, dict[str, Any]] = {}


class _StubBlackboard:
    """手写零 IO 黑板替身（duck-typing PublicBlackboard——进程内性能面零 Redis 依赖）。"""

    def __init__(self) -> None:
        self.post_calls: list[dict[str, Any]] = []

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict[str, Any],
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """捕获 post 调用（返回递增版本号）。"""
        self.post_calls.append(
            {"conversation_id": conversation_id, "agent_id": agent_id, "content": content, "confidence": confidence}
        )
        return len(self.post_calls)

    async def get(self, conversation_id: str) -> list[dict[str, Any]]:
        """读回桩。"""
        return []

    async def get_by_agent(self, conversation_id: str, agent_id: str) -> dict[str, Any] | None:
        """读回桩。"""
        return None

    async def get_latest(self, conversation_id: str) -> dict[str, Any] | None:
        """读回桩。"""
        return None


class _RecordingIsolationGuard:
    """手写零 IO 守卫替身（duck-typing IsolationGuardPort——放行形态）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def ensure_agent_access(
        self, actor_agent_id: uuid.UUID, target_agent_id: uuid.UUID, resource: Any, operation: Any
    ) -> None:
        """捕获守卫调用（放行）。"""
        self.calls.append({"actor": actor_agent_id, "target": target_agent_id, "resource": resource, "operation": operation})

    async def ensure_agent_executable(self, agent_id: uuid.UUID) -> Any:
        """协议面补全桩（duck-typing 结构匹配——bus 仅消费 ensure_agent_access）。"""
        return None

    async def ensure_tool_access(self, agent_id: uuid.UUID, tool_name: str) -> None:
        """协议面补全桩。"""


class _RecordingEventPublisher:
    """手写 duck-typing 事件捕获类（真实链装配消费——全仓 15+ 文件同款先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _StubIsolationSwitchLogRepository:
    """手写零 IO 切换日志仓储替身（真实链装配消费——5-5 先例）。"""

    async def save(self, log: Any) -> Any:
        """捕获保存。"""
        return log

    async def search(self, query: Any) -> Any:
        """空结果查询（IsolationSwitchLogSearchResult 真实形态——5-5 替身先例）。"""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


#: 活跃总线注册表（autouse fixture 统一 close——消费任务于 loop 存活期收尾；
#: 孤儿协程 GC 于 loop 关闭后会触发 Queue.get 清理路径的 unraisable RuntimeError 噪声）
_ACTIVE_BUSES: list[InProcessSAPBus] = []


@pytest.fixture(autouse=True)
async def _close_active_buses() -> AsyncGenerator[None, None]:
    """用例后关闭本用例创建的全部总线（close 幂等）。"""
    yield
    for active_bus in _ACTIVE_BUSES:
        await active_bus.close()
    _ACTIVE_BUSES.clear()


def _make_sap_message(**overrides: Any) -> SAPMessage:
    """构造 SAPMessage（默认最小必填 + 覆盖——OD-5 UUID 测试标识）。"""
    kwargs: dict[str, Any] = {
        "message_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "sender_id": str(uuid.uuid4()),
        "receiver_id": str(uuid.uuid4()),
        "message_type": MessageType.NOTIFICATION,
        "content": "SAP 集成消息",
    }
    kwargs.update(overrides)
    return SAPMessage(**kwargs)


def _make_full_message() -> SAPMessage:
    """构造 15 字段满载实例（序列化最大体积形态——性能口径）。"""
    return SAPMessage(
        message_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        sender_id=str(uuid.uuid4()),
        receiver_id=str(uuid.uuid4()),
        message_type=MessageType.DEBATE,
        priority=MessagePriority.URGENT,
        content="满载序列化性能消息内容",
        correlation_id=uuid.uuid4(),
        isolation_level=IsolationLevel.L2_COLLAB,
        blackboard_visible=True,
        timestamp=datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC),
        subject="序列化性能",
        context={"嵌套": {"层级": 1}, "tags": ["a", "b"], "meta": {"deep": {"value": 42}}},
        requires_response=True,
        timeout_seconds=120,
    )


async def _probe_real_redis() -> Any:
    """真实 Redis 探测（ping 失败动态 skip——禁写死 skip marker）。"""
    import redis.asyncio as aioredis

    from tests.environments import get_test_env

    cfg = get_test_env()
    client = aioredis.Redis(
        host=cfg.redis.host,
        port=cfg.redis.port,
        password=cfg.redis.password,
        decode_responses=True,
    )
    try:
        await client.ping()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Redis not available: {exc}")
    return client


async def sample_sap_perf() -> dict[str, Any]:
    """性能三锚委托采样（cache-or-compute——_PERF_CACHE 单 key sap_perf 载三指标 summary）。

    传递口径：构造消息 → send → handler 收到事件（asyncio.Event）全程 perf_counter 计时；
    序列化口径：满载实例 dump+validate 往返同批 20 采样；正向锚：收到计数 == warmup 1 + 20。
    """
    cached = _PERF_CACHE.get("sap_perf")
    if cached is not None:
        return cached

    bus = InProcessSAPBus(blackboard=_StubBlackboard(), guard=_RecordingIsolationGuard())
    _ACTIVE_BUSES.append(bus)
    receiver_id = str(uuid.uuid4())
    delivery_received: list[SAPMessage] = []
    delivered_event = asyncio.Event()

    async def handler(message: SAPMessage) -> None:
        delivery_received.append(message)
        delivered_event.set()

    bus.subscribe(receiver_id, handler)

    delivery_latencies: list[float] = []
    for round_index in range(1 + SAP_SAMPLE_ROUNDS):  # warmup 1 + 采样 20（首轮不计时）
        delivered_event.clear()
        start = time.perf_counter()
        await bus.send(_make_sap_message(receiver_id=receiver_id, content=f"性能消息-{round_index}"))
        await asyncio.wait_for(delivered_event.wait(), timeout=5.0)
        if round_index > 0:  # warmup 轮不计时
            delivery_latencies.append(time.perf_counter() - start)

    full_message = _make_full_message()
    serialization_latencies: list[float] = []
    for _ in range(SAP_SAMPLE_ROUNDS):
        start = time.perf_counter()
        payload = serialize(full_message)
        deserialize(payload)
        serialization_latencies.append(time.perf_counter() - start)

    summary = {
        "delivery_p95_seconds": statistics.quantiles(delivery_latencies, n=SAP_SAMPLE_ROUNDS)[18],
        "serialization_p95_seconds": statistics.quantiles(serialization_latencies, n=SAP_SAMPLE_ROUNDS)[18],
        "delivery_received_count": len(delivery_received),
        "delivery_sample_count": len(delivery_latencies),
    }
    _PERF_CACHE["sap_perf"] = summary
    return summary


# ==== 真实 Redis 黑板桥（类级 redis marker——AC-3.1/AC-3.2 集成承载） ====


class TestRealRedisBlackboardBridge:
    """真实 Redis 场景（MVCC 写入 + L4 真实链 449 + 自清理——5-5 AC-3.3 装配形态延续）。"""

    pytestmark = [pytest.mark.redis]

    async def test_mvcc_versions_increment_and_readback(self) -> None:
        """两次可见 send → get 读回版本 [v1, v1+1] 精确递增 + content message_id 匹配 + 自清理。"""
        from src.infrastructure.storage.redis.key_builder import build_key
        from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard

        client = await _probe_real_redis()
        try:
            blackboard = RedisPublicBlackboard(redis_client=client)
            bus = InProcessSAPBus(blackboard=blackboard, guard=_RecordingIsolationGuard())
            _ACTIVE_BUSES.append(bus)
            receiver_id = str(uuid.uuid4())
            bus.subscribe(receiver_id, lambda message: None)
            conversation_id = uuid.uuid4()
            messages = [
                _make_sap_message(
                    receiver_id=receiver_id,
                    blackboard_visible=True,
                    conversation_id=conversation_id,
                    content=f"黑板可见消息-{index}",
                )
                for index in range(2)
            ]
            for message in messages:
                await bus.send(message)

            entries = await blackboard.get(str(conversation_id))
            versions = [entry["version"] for entry in entries]
            assert len(versions) == 2, f"应有两条黑板条目，实际 {len(versions)}"
            assert versions[0] >= 1
            assert versions[1] == versions[0] + 1, f"MVCC 版本应精确递增（v2==v1+1），实际 {versions}"
            for entry, message in zip(entries, messages, strict=True):
                assert entry["content"]["message_id"] == str(message.message_id)
                assert entry["agent_id"] == message.sender_id

            # 自清理：只清自己创建的黑板双键 + exists 复核
            blackboard_key = build_key("blackboard", str(conversation_id))
            version_key = build_key("blackboard", str(conversation_id), "version")
            await client.delete(blackboard_key, version_key)
            assert not await client.exists(blackboard_key)
            assert not await client.exists(version_key)
        finally:
            await client.close()

    async def test_l4_real_chain_449_passthrough_zero_write(self) -> None:
        """真实隔离链（实例化 L4 CEO Agent + 真实 guard）→ 黑板写 449 透传 + 零写入。"""
        from src.application.services.isolation_guard_service import IsolationGuardService
        from src.application.services.isolation_management_service import IsolationManagementService
        from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
        from src.domain.entities.agent import AgentRole
        from src.domain.exceptions import IsolationOperationForbiddenError
        from src.domain.ports.resolver import resolve
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
        from src.infrastructure.storage.redis.key_builder import build_key
        from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
        from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
        from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
        from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

        client = await _probe_real_redis()
        try:
            agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=client))
            isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=client))
            isolation_service = IsolationManagementService(
                isolation_repository=isolation_repository,
                agent_repository=agent_repository,
                event_publisher=_RecordingEventPublisher(),
                agent_config_loader=resolve("agent_config_loader"),
                isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
                audit_service=None,
            )
            guard = IsolationGuardService(
                isolation_management_service=isolation_service,
                agent_repository=agent_repository,
                agent_config_loader=resolve("agent_config_loader"),
            )
            blackboard = RedisPublicBlackboard(redis_client=client)
            bus = InProcessSAPBus(blackboard=blackboard, guard=guard)
            _ACTIVE_BUSES.append(bus)
            instantiate_use_case = InstantiateAgentUseCase(
                config_loader=resolve("agent_config_loader"),
                repository=agent_repository,
                event_publisher=InMemoryEventBus(),
                isolation_service=isolation_service,
            )
            result = await instantiate_use_case.execute(role=AgentRole.CEO)
            conversation_id = uuid.uuid4()
            target_receiver_id = str(uuid.uuid4())
            bus.subscribe(
                target_receiver_id, lambda message: None
            )  # 哑接收方（守卫判定单边取 actor 侧——target 仅参与 cross_agent 布尔）
            message = _make_sap_message(
                sender_id=str(result.agent_id),
                receiver_id=target_receiver_id,
                blackboard_visible=True,
                conversation_id=conversation_id,
            )
            with pytest.raises(IsolationOperationForbiddenError) as exc_info:
                await bus.send(message)
            error = exc_info.value
            assert error.code == "EXCEPTION_449"
            assert error.context["reason"] == "data_isolation:read_only"
            entries = await blackboard.get(str(conversation_id))
            assert entries == [], "守卫拒绝后黑板应零写入"

            # 自清理：agent/isolation 双 namespace 键 + exists 复核（黑板零写入无键可清）
            for namespace in ("agent", "isolation"):
                key = build_key(namespace, str(result.agent_id))
                await client.delete(key)
                assert not await client.exists(key), f"自产键未清理: {key}"
        finally:
            await client.close()


# ==== 性能三锚（类级不挂 redis——进程内性能零 Redis 依赖） ====


class TestSAPPerformance:
    """性能三锚（epics L1923/L1924/L1925——委托计时 + 常量单源 + 正向锚）。"""

    async def test_delivery_p95_under_limit(self) -> None:
        """传递 P95 < 200ms（epics L1923——等值断言是常量改错值变异锚的充分条件）。"""
        assert SAP_DELIVERY_P95_LIMIT_SECONDS == 0.2, "SAP_DELIVERY_P95_LIMIT_SECONDS 应为 0.2（常量单源）"
        summary = await sample_sap_perf()
        assert summary["delivery_p95_seconds"] < SAP_DELIVERY_P95_LIMIT_SECONDS, (
            f"消息传递 P95 应 < {SAP_DELIVERY_P95_LIMIT_SECONDS}s，实际 {summary['delivery_p95_seconds']}s"
        )

    async def test_serialization_p95_under_limit(self) -> None:
        """序列化 P95 < 50ms（epics L1924——满载实例 dump+validate 往返口径）。"""
        assert SAP_SERIALIZATION_P95_LIMIT_SECONDS == 0.05, "SAP_SERIALIZATION_P95_LIMIT_SECONDS 应为 0.05（常量单源）"
        summary = await sample_sap_perf()
        assert summary["serialization_p95_seconds"] < SAP_SERIALIZATION_P95_LIMIT_SECONDS, (
            f"序列化 P95 应 < {SAP_SERIALIZATION_P95_LIMIT_SECONDS}s，实际 {summary['serialization_p95_seconds']}s"
        )

    async def test_positive_anchor_received_count_21(self) -> None:
        """正向锚：采样轮收到计数 == warmup 1 + 20 采样 == 21（防静默跳过假绿）。"""
        summary = await sample_sap_perf()
        assert summary["delivery_received_count"] == 21, (
            f"正向锚应为 21（warmup 1 + 20 采样），实际 {summary['delivery_received_count']}"
        )
        assert summary["delivery_sample_count"] == 20

    async def test_concurrency_50_all_delivered_queue_drained(self) -> None:
        """50 并发 send 全送达零丢失 + 处理完成后队列清空（积压归零——epics L1925 ≥50）。"""
        assert SAP_CONCURRENCY_FLOOR == 50, "SAP_CONCURRENCY_FLOOR 应为 50（常量单源）"
        bus = InProcessSAPBus(blackboard=_StubBlackboard(), guard=_RecordingIsolationGuard())
        _ACTIVE_BUSES.append(bus)
        receiver_id = str(uuid.uuid4())
        delivery_order: list[SAPMessage] = []

        async def handler(message: SAPMessage) -> None:
            delivery_order.append(message)

        bus.subscribe(receiver_id, handler)
        messages = [
            _make_sap_message(receiver_id=receiver_id, content=f"并发消息-{index}") for index in range(SAP_CONCURRENCY_FLOOR)
        ]
        await asyncio.gather(*(bus.send(message) for message in messages))

        deadline = asyncio.get_running_loop().time() + 5.0
        while asyncio.get_running_loop().time() < deadline and len(delivery_order) < SAP_CONCURRENCY_FLOOR:
            await asyncio.sleep(0.01)
        assert len(delivery_order) == SAP_CONCURRENCY_FLOOR, f"50 条应全送达零丢失，实际 {len(delivery_order)}"
        received_ids = {message.message_id for message in delivery_order}
        for message in messages:
            assert message.message_id in received_ids, f"消息 {message.message_id} 丢失"
        # 串行消费全部完成后队列必空（handler 完成计数承载积压归零）
        assert len(delivery_order) == len(messages)

    async def test_xdist_group_unique(self) -> None:
        """xdist 组互异：sap-protocol-perf 与既有 15 组不冲突（全仓扫描）。"""
        import re
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        existing_groups: set[str] = set()
        for py_file in (repo_root / "tests").rglob("*.py"):
            existing_groups.update(re.findall(r'xdist_group\("([^"]+)"\)', py_file.read_text(encoding="utf-8")))
        expected_existing = {
            "agent-workflow-perf",
            "agent-isolation-perf",
            "agent-triple-isolation-perf",
            "isolation-switch-log-perf",
            "phoenix-tracer-perf",
            "agent-evaluation-perf",
            "drift-detection-perf",
            "agent-instantiation",
            "agent-profile-loading",
            "data-source-cache",
            "sandbox-daemon",
            "tool-executions-pg",
            "tool-versions-pg",
            "validation-feedback-pg",
            "checkpoint-evaluation-perf",
        }
        assert expected_existing <= existing_groups, f"既有 15 组应全在位（缺失 {expected_existing - existing_groups}）"
        assert "sap-protocol-perf" in existing_groups, "新组 sap-protocol-perf 应已声明"
        assert len(existing_groups) >= 16, "含新组应至少 16 组"
