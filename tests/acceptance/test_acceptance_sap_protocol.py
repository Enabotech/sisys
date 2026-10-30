"""验收测试：Story 5.11 SAP 协议支持（内部 Agent 通信）。

模板基准: test_acceptance_postgresql_relational_layer.py（PG 模板 R6——多行 @scenario
字面量路径 + 场景绑定与步骤实现交替排列 + AC 横幅分组）；R6 改造（5-3/5-5/5-10 先例）:
真实断言（禁 then-pass 占位）+ context dict fixture + 模块级 event_loop + _run_async
同循环三件套（禁 @pytest.mark.asyncio——context 数据丢失红线）。

14 场景三属性分档表（外部服务依赖 / 前置状态 / 断言面）:
| 场景 | 外部服务依赖 | 前置状态（Given 装配） | 断言面（Then） |
| AC-1.1 四类型单播+BROADCAST 全员送达 | 无 | 手工 bus + 替身黑板/守卫 + 三接收方 | 15 字段全等 + epics 十键 |
| AC-1.2 优先级出队 | 无 | 手工 bus + 单接收方 | URGENT>HIGH>NORMAL×3>LOW 插队+同级 FIFO |
| AC-1.3 校验面+关闭态 | 无 | 手工 bus + 单接收方 | 461 reason 闭集 + close 动作清单 |
| AC-2.1 关联送达 | 无 | 两方装配（响应方回发） | correlation 匹配 + 双重送达 |
| AC-2.2 超时+迟到+双响应 | 无 | 请求方+静默响应方 | 460 三段式 + 索引清理 + 幂等 |
| AC-2.3 无等待+并发 | 无 | 两对装配 | 直达 + 超时路径 + 键控隔离 |
| AC-3.1 MVCC 真实 Redis | Redis（场景级 redis marker） | 真实 RedisPublicBlackboard | v2==v1+1 + get 读回 + 自清理 |
| AC-3.2 L4 真实链 449 | Redis（场景级 redis marker） | 实例化 CEO + 真实 guard | 449 透传 + 零写入 |
| AC-3.3 零写入+写失败 | 无（替身面不挂 redis） | 手工 bus + 两接收方 | 零 post + 投影锚 + 正交性 + 462 |
| AC-4.1 序列化往返 | 无 | 15 字段满载实例 | 逐字段相等 + ValidationError 透传 |
| AC-4.2 组合根接线 | 无（bootstrap 注册表） | bootstrap | resolve 四件 + 注入链 + fail-fast |
| AC-5.1 P95 双锚 | 无（进程内委托计时） | _PERF_CACHE 委托 | <0.2s/<0.05s + 正向锚 21 |
| AC-5.2 并发 50 | 无 | 手工 bus + 单接收方 | 50/50 零丢失 + 队列清空 |
| 收尾 完成清单 | 无 | 交付完成 | src 七件 + tests 八件 + 注册联动 |

redis marker 分档（AC-5 钦定）: 文件名 sap_protocol 不命中 conftest 服务关键词映射（仅
自动挂 acceptance）；文件级 pytestmark = [acceptance, xdist_group] 不挂 redis——AC-3.1/
AC-3.2 两真实 Redis 场景函数级 @pytest.mark.redis（-m "not redis" 仅排除两场景，AC-3.3
替身面与其余 12 场景仍跑——462 fail-loud/BROADCAST+False/不投递验收面不丢）；xdist_group
与集成计时逐字同组 sap-protocol-perf（loadgroup 同 worker 串行是 _PERF_CACHE 命中前提）。

延迟 import 纪律: 模块顶部仅 stdlib+pytest+pytest_bdd+既有基建（build_key）；本 Story 新
交付模块（bus/sap_exceptions/集成常量与 helper）一律步骤函数体内 import——Task 0-5 窗口期
为运行期 ModuleNotFoundError 逐场景 failed 非 collection error（5-10 延迟 import 先例）。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_sap_protocol.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine, Generator
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

# redis marker 显式分档（AC-5 钦定）：文件级不挂 redis（进程内替身/委托计时面零 Redis
# 依赖——挂了会让 -m "not redis" 环境连 12 场景一并排除）；AC-3.1/AC-3.2 场景函数级叠加
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.xdist_group("sap-protocol-perf"),
]


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（BDD 步骤 run_until_complete 专用，禁 @pytest.mark.asyncio）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """场景级共享上下文（dict 形态）+ 惰性真实 Redis 客户端登记（场景级独立——跨循环记忆锚）。"""
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_env_config": acceptance_env_config,
        "_cleanup_keys": [],
        "_agent_ids": [],
        "_buses": [],
    }
    yield ctx
    # 先关闭场景内创建的全部总线（消费任务 cancel+gather 于模块 loop 存活期——孤儿协程
    # GC 于 loop 关闭后会触发 Queue.get 清理路径的 unraisable RuntimeError 噪声）
    for bus_instance in ctx.get("_buses", []):
        _run_async(event_loop, bus_instance.close())
    client = ctx.pop("_real_redis_client", None)
    if client is not None:
        # teardown：先删登记的自产键（黑板双键 + agent/isolation 双 namespace），再关客户端
        for key in ctx.get("_cleanup_keys", []):
            _run_async(event_loop, client.delete(key))
        for agent_id in ctx.get("_agent_ids", []):
            for namespace in ("agent", "isolation"):
                _run_async(event_loop, client.delete(build_key(namespace, str(agent_id))))
        _run_async(event_loop, client.close())


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """同循环调度（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失）。"""
    return event_loop.run_until_complete(coro)


class _StubBlackboard:
    """手写零 IO 黑板替身（duck-typing 实现 PublicBlackboard 端口契约——捕获 post 调用）。"""

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
        """捕获 post 调用（返回递增版本号——非 0 成功语义）。"""
        self.post_calls.append(
            {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "content": content,
                "confidence": confidence,
                "citations": citations,
            }
        )
        return len(self.post_calls)

    async def get(self, conversation_id: str) -> list[dict[str, Any]]:
        """读回桩（替身面不消费）。"""
        return []

    async def get_by_agent(self, conversation_id: str, agent_id: str) -> dict[str, Any] | None:
        """读回桩。"""
        return None

    async def get_latest(self, conversation_id: str) -> dict[str, Any] | None:
        """读回桩。"""
        return None


class _FailingBlackboard(_StubBlackboard):
    """post 返 0 失败替身（OD-7 fail-loud 检测点——RedisPublicBlackboard 吞异常返 0 形态）。"""

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict[str, Any],
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """捕获调用但返回 0（写失败语义）。"""
        await super().post(conversation_id, agent_id, content, confidence=confidence, citations=citations)
        return 0


class _RecordingIsolationGuard:
    """手写零 IO 守卫替身（duck-typing 实现 IsolationGuardPort——放行/拒绝可控）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.reject_with: Exception | None = None

    async def ensure_agent_access(
        self,
        actor_agent_id: uuid.UUID,
        target_agent_id: uuid.UUID,
        resource: Any,
        operation: Any,
    ) -> None:
        """捕获守卫调用（reject_with 置位时抛出该异常——拒绝形态可控）。"""
        self.calls.append(
            {
                "actor": actor_agent_id,
                "target": target_agent_id,
                "resource": resource,
                "operation": operation,
            }
        )
        if self.reject_with is not None:
            raise self.reject_with

    async def ensure_agent_executable(self, agent_id: uuid.UUID) -> Any:
        """协议面补全桩（duck-typing 结构匹配——bus 仅消费 ensure_agent_access）。"""
        return None

    async def ensure_tool_access(self, agent_id: uuid.UUID, tool_name: str) -> None:
        """协议面补全桩。"""


class _RecordingEventPublisher:
    """手写 duck-typing 事件捕获类（publish 追加事件并返回真实 PublishResult——全仓 15+ 文件同款先例）。"""

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
    """手写零 IO 切换日志仓储替身（5-5 _StubIsolationSwitchLogRepository 先例——save/search 双方法）。"""

    async def save(self, log: Any) -> Any:
        """捕获保存（替身面零 IO）。"""
        return log

    async def search(self, query: Any) -> Any:
        """空结果查询（IsolationSwitchLogSearchResult 真实形态——5-5 替身先例）。"""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


def _make_message(**overrides: Any) -> Any:
    """构造 SAPMessage（默认最小必填 + 覆盖——5-3 test_message 模块级工厂先例；延迟 import 防收集期炸）。"""
    from src.interfaces.sap.message import SAPMessage

    kwargs: dict[str, Any] = {
        "message_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "sender_id": str(uuid.uuid4()),
        "receiver_id": str(uuid.uuid4()),
        "message_type": "notification",
        "content": "SAP 协议验收消息",
    }
    kwargs.update(overrides)
    return SAPMessage(**kwargs)


async def _wait_for_delivery(
    received_lists: list[list[Any]],
    expected_total: int,
    timeout_seconds: float = 5.0,
) -> None:
    """等待送达计数达标（条件轮询上限 5s——禁 sleep 死等）。"""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        actual = sum(len(received) for received in received_lists)
        if actual >= expected_total:
            return
        await asyncio.sleep(0.01)
    actual = sum(len(received) for received in received_lists)
    pytest.fail(f"等待消息送达超时：期望 {expected_total} 条，实际 {actual} 条")


def _make_handler(received: list[Any]) -> Any:
    """handler 工厂（闭包绑定接收列表——规避循环变量闭包陷阱）。"""

    async def handler(message: Any) -> None:
        received.append(message)

    return handler


# ==== AC-1: SAPBus 端口与进程内总线核心（分发面/优先级/校验面/关闭态） ====


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-1.1 - 四种单播类型逐一送达与 BROADCAST 全员送达",
)
def test_ac_1_1_unicast_and_broadcast(context: dict[str, Any]) -> None:
    """AC-1.1: 四种单播类型 15 字段全等 + BROADCAST 全员送达（分发面合一）。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-1.2 - 四级优先级乱序插队与同级 FIFO 出队",
)
def test_ac_1_2_priority_order(context: dict[str, Any]) -> None:
    """AC-1.2: 乱序注入六级消息——插队语义 + 同级 FIFO 双观测。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-1.3 - 协议校验面 fail-loud 与关闭态 461",
)
def test_ac_1_3_validation_and_close(context: dict[str, Any]) -> None:
    """AC-1.3: 校验面 reason 闭集 + close 动作清单 + 关闭态三方法。"""


@given("手工构造 InProcessSAPBus 实例（注入替身黑板与放行守卫）")
def given_bus_with_stubs(context: dict[str, Any]) -> None:
    """替身装配（每场景新实例——SINGLETON 组件验收手工新实例惯例）。"""
    from src.interfaces.sap.bus import InProcessSAPBus

    blackboard = _StubBlackboard()
    guard = _RecordingIsolationGuard()
    context["bus"] = InProcessSAPBus(blackboard=blackboard, guard=guard)
    context["_buses"].append(context["bus"])
    context["stub_blackboard"] = blackboard
    context["stub_guard"] = guard


@given("三个接收方以 UUID 标识订阅消息")
def given_three_receivers(context: dict[str, Any]) -> None:
    """三接收方订阅（BROADCAST 全员送达载体——OD-5 UUID 标识）。"""
    bus = context["bus"]
    receiver_ids = [str(uuid.uuid4()) for _ in range(3)]
    received: dict[str, list[Any]] = {rid: [] for rid in receiver_ids}
    for receiver_id in receiver_ids:
        bus.subscribe(receiver_id, _make_handler(received[receiver_id]))
    context["receiver_ids"] = receiver_ids
    context["received"] = received


@when("依次发送 REQUEST RESPONSE NOTIFICATION DEBATE 四种单播消息")
def when_send_four_unicast_types(context: dict[str, Any]) -> None:
    """四类型单播逐一发送（REQUEST 置 requires_response——行为输入键点名载体）。"""
    from src.interfaces.sap.types import MessageType

    sender_id = str(uuid.uuid4())
    receiver_id = context["receiver_ids"][0]
    messages = []
    for message_type in (
        MessageType.REQUEST,
        MessageType.RESPONSE,
        MessageType.NOTIFICATION,
        MessageType.DEBATE,
    ):
        message = _make_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=f"单播消息-{message_type.value}",
            requires_response=message_type is MessageType.REQUEST,
            subject="验收单播",
            context={"round": 1},
        )
        messages.append(message)
        _run_async(context["_loop"], context["bus"].send(message))
    context["sent_unicast_messages"] = messages


@when("三个接收方场景下发送 BROADCAST 消息")
def when_send_broadcast(context: dict[str, Any]) -> None:
    """BROADCAST 全员送达（receiver_id="broadcast" 约定值——OD-8 组合锁定）。"""
    from src.interfaces.sap.types import MessageType

    message = _make_message(
        sender_id=str(uuid.uuid4()),
        receiver_id="broadcast",
        message_type=MessageType.BROADCAST,
        content="广播消息",
    )
    _run_async(context["_loop"], context["bus"].send(message))
    context["sent_broadcast_message"] = message


@then("每种类型消息 15 字段与发送实例全等且 epics 十键逐键一致")
def then_unicast_delivered_fields(context: dict[str, Any]) -> None:
    """投递保真面：15 字段 Pydantic 实例全等 + epics 十键逐键 + 行为输入键点名
    （按 message_id 过滤——BDD 全 when 先于 then，BROADCAST 已同队到达，总数断言
    时序脆弱）。"""
    receiver_id = context["receiver_ids"][0]
    received = context["received"][receiver_id]
    sent_messages = context["sent_unicast_messages"]
    _run_async(context["_loop"], _wait_for_delivery([received], len(sent_messages)))
    got_by_id = {m.message_id: m for m in received}
    for sent in sent_messages:
        assert sent.message_id in got_by_id, f"单播消息 {sent.message_id} 未送达"
        got = got_by_id[sent.message_id]
        assert got == sent, "15 字段 Pydantic 实例应全等（投递保真面）"
    ten_keys = (
        "message_id",
        "conversation_id",
        "sender_id",
        "receiver_id",
        "message_type",
        "priority",
        "content",
        "correlation_id",
        "isolation_level",
        "blackboard_visible",
    )
    for sent in sent_messages:
        got = got_by_id[sent.message_id]
        for key in ten_keys:
            assert getattr(got, key) == getattr(sent, key), f"epics 十键逐键断言失败: {key}"
        assert got.requires_response == sent.requires_response, "requires_response 应保真"
        assert got.timeout_seconds == sent.timeout_seconds, "timeout_seconds 应保真"


@then("BROADCAST 全员送达同一 message_id")
def then_broadcast_all_received(context: dict[str, Any]) -> None:
    """三接收方各收到同一 message_id（接收方集合快照定格——零遗漏）。"""
    received_lists = list(context["received"].values())
    _run_async(context["_loop"], _wait_for_delivery(received_lists, 4 + 3))
    broadcast_id = context["sent_broadcast_message"].message_id
    for receiver_id, received in context["received"].items():
        matches = [m for m in received if m.message_id == broadcast_id]
        assert len(matches) == 1, f"接收方 {receiver_id} 应恰收到一条 BROADCAST，实际 {len(matches)} 条"


@given("单接收方订阅消息并记录出队顺序")
def given_single_receiver_recording(context: dict[str, Any]) -> None:
    """单接收方订阅（优先级出队顺序/并发送达计数双载体）。"""
    bus = context["bus"]
    receiver_id = str(uuid.uuid4())
    delivery_order: list[Any] = []
    bus.subscribe(receiver_id, _make_handler(delivery_order))
    context["receiver_id"] = receiver_id
    context["delivery_order"] = delivery_order


@when("乱序注入六级消息（LOW NORMAL HIGH URGENT 各一加两条 NORMAL）")
def when_inject_six_out_of_order(context: dict[str, Any]) -> None:
    """乱序注入六级（单协程一次性灌入——风险 2 钦定：逐条独立 run_until_complete 窗口会让
    消费任务即时消化当条消息致队列零积压，优先级无处施展；单协程内 send 零让渡全部入队
    后消费任务才首次调度——插队语义可观测）。"""
    from src.interfaces.sap.types import MessagePriority, MessageType

    priorities = (
        MessagePriority.LOW,
        MessagePriority.NORMAL,
        MessagePriority.HIGH,
        MessagePriority.URGENT,
        MessagePriority.NORMAL,
        MessagePriority.NORMAL,
    )
    bus = context["bus"]
    receiver_id = context["receiver_id"]
    messages = [
        _make_message(
            receiver_id=receiver_id,
            message_type=MessageType.NOTIFICATION,
            priority=priority,
            content=f"优先级消息-{index}",
        )
        for index, priority in enumerate(priorities)
    ]

    async def _inject_messages() -> None:
        """单协程连续 send（六条全部入队后消费任务才调度——队列积压使优先级生效）。"""
        for message in messages:
            await bus.send(message)

    _run_async(context["_loop"], _inject_messages())
    context["priority_sent_ids"] = [m.message_id for m in messages]


@then("出队顺序为 URGENT HIGH NORMAL×3（入队序）LOW")
def then_priority_order(context: dict[str, Any]) -> None:
    """乱序注入下插队语义 + 同级 FIFO（等待队列清空后断言序）。"""
    from src.interfaces.sap.types import MessagePriority

    _run_async(context["_loop"], _wait_for_delivery([context["delivery_order"]], 6))
    assert context["delivery_order"] and [m.priority for m in context["delivery_order"]] == [
        MessagePriority.URGENT,
        MessagePriority.HIGH,
        MessagePriority.NORMAL,
        MessagePriority.NORMAL,
        MessagePriority.NORMAL,
        MessagePriority.LOW,
    ], f"优先级出队顺序错误: {[m.priority for m in context['delivery_order']]}"
    # 同级 FIFO 内序（R1-F4 双观测）：三条 NORMAL 按入队序 msg-1/4/5——seq 破平局
    # 计数器被破坏时 priority 序仍 [NORMAL,NORMAL,NORMAL] 不可见，content 序必红
    content_order = [m.content for m in context["delivery_order"]]
    assert content_order == [
        "优先级消息-3",
        "优先级消息-2",
        "优先级消息-1",
        "优先级消息-4",
        "优先级消息-5",
        "优先级消息-0",
    ], f"同级 FIFO 内序破坏（三条 NORMAL 应按入队序）: {content_order}"
    # 六条 message_id 零丢失（插队不改集合）
    received_ids = {m.message_id for m in context["delivery_order"]}
    assert received_ids == set(context["priority_sent_ids"]), "优先级场景六条消息应零丢失"


@given("一个接收方以 UUID 标识订阅消息")
def given_one_receiver(context: dict[str, Any]) -> None:
    """单接收方订阅（关闭态挂起等待者载体）。"""
    bus = context["bus"]
    receiver_id = str(uuid.uuid4())
    received: list[Any] = []
    bus.subscribe(receiver_id, _make_handler(received))
    context["receiver_id"] = receiver_id
    context["received_list"] = received


@when("进行未注册接收方与非 UUID 双侧及组合双向校验违规操作")
def when_validation_violations(context: dict[str, Any]) -> None:
    """校验面六操作（四 reason 闭集——组合双向两操作同 reason；BROADCAST 方向 receiver 取合法 UUID）。"""
    from src.domain.exceptions import SAPBusStateError
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    violations: dict[str, Any] = {}

    # ① 未注册接收方单播（发送方拿到明确错误——比静默入队后无人消费更诚实）
    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(
            context["_loop"],
            bus.send(_make_message(receiver_id=str(uuid.uuid4()), message_type=MessageType.NOTIFICATION)),
        )
    violations["receiver_not_registered"] = exc_info.value

    # ② 非 UUID sender（receiver 用已注册合法值——隔离单因）
    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(
            context["_loop"],
            bus.send(
                _make_message(
                    sender_id="ceo-not-uuid",
                    receiver_id=context["receiver_id"],
                    message_type=MessageType.NOTIFICATION,
                )
            ),
        )
    violations["invalid_sender_id"] = exc_info.value

    # ③ 非 UUID 且非 "broadcast" 的 receiver（send 侧——闭集成员创建期无触发用例，v1.1.0 补）
    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(
            context["_loop"],
            bus.send(_make_message(receiver_id="cfo-not-uuid", message_type=MessageType.NOTIFICATION)),
        )
    violations["invalid_receiver_id_send"] = exc_info.value

    # ③b subscribe 侧同样校验（防「永远无法合法收到消息」的死订阅）
    with pytest.raises(SAPBusStateError) as exc_info:
        bus.subscribe("cto-not-uuid", lambda message: None)
    violations["invalid_receiver_id_subscribe"] = exc_info.value

    # ④ BROADCAST 类型 + 合法 UUID receiver（组合方向一——v1.3.0：非 UUID 形态先撞 invalid_receiver_id 防 reason 错位）
    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(
            context["_loop"],
            bus.send(_make_message(receiver_id=str(uuid.uuid4()), message_type=MessageType.BROADCAST)),
        )
    violations["broadcast_convention_violation_bcast"] = exc_info.value

    # ⑤ 非 BROADCAST 类型 + receiver=="broadcast"（组合方向二——双向锁定）
    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(
            context["_loop"],
            bus.send(_make_message(receiver_id="broadcast", message_type=MessageType.NOTIFICATION)),
        )
    violations["broadcast_convention_violation_unicast"] = exc_info.value

    context["violations"] = violations


@when("发送 requires_response 的 REQUEST 并后台挂起等待者")
def when_pending_waiter(context: dict[str, Any]) -> None:
    """挂起等待者（close 第五动作 set_exception 的真实载体——先驱动至挂起点）。"""
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    request = _make_message(
        sender_id=str(uuid.uuid4()),
        receiver_id=context["receiver_id"],
        message_type=MessageType.REQUEST,
        requires_response=True,
        timeout_seconds=5,
    )

    async def _flow() -> Any:
        await bus.send(request)
        return await bus.wait_for_response(request.message_id, timeout_seconds=5.0)

    context["pending_wait_task"] = context["_loop"].create_task(_flow())
    # 驱动至挂起点（等待者挂在登记 Future 上——0.05s 让渡消费任务与等待任务）
    _run_async(context["_loop"], asyncio.sleep(0.05))


@when("关闭总线后二次关闭并调用 send subscribe wait_for_response")
def when_close_and_closed_calls(context: dict[str, Any]) -> None:
    """close 动作清单（幂等/取消任务/清空队列/Future set_exception/清空登记表）+ 关闭态三方法。"""
    from src.domain.exceptions import SAPBusStateError
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    loop = context["_loop"]

    _run_async(loop, bus.close())

    # 在途等待者结局（461 非 CancelledError——结局统一钦定）
    try:
        _run_async(loop, context["pending_wait_task"])
        context["pending_wait_outcome"] = "unexpected-return"
    except SAPBusStateError as error:
        context["pending_wait_outcome"] = error

    # 二次关闭（空表幂等——done 守卫 + 登记表清空，DC-11/v1.2.0 第五动作）
    _run_async(loop, bus.close())
    context["second_close_raised"] = False

    # 关闭态三方法（校验次序钦定：开闭态首位）
    closed_calls: dict[str, Any] = {}
    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(
            loop,
            bus.send(_make_message(receiver_id=context["receiver_id"], message_type=MessageType.NOTIFICATION)),
        )
    closed_calls["send"] = exc_info.value

    def _silent_handler(message: Any) -> None:
        """静默 handler（关闭态订阅拒绝载体）。"""

    with pytest.raises(SAPBusStateError) as exc_info:
        bus.subscribe(str(uuid.uuid4()), _silent_handler)
    closed_calls["subscribe"] = exc_info.value

    with pytest.raises(SAPBusStateError) as exc_info:
        _run_async(loop, bus.wait_for_response(uuid.uuid4(), timeout_seconds=1.0))
    closed_calls["wait_for_response"] = exc_info.value
    context["closed_calls"] = closed_calls


@then("四类校验违规各抛 461 且 reason 逐项匹配闭集")
def then_validation_reasons(context: dict[str, Any]) -> None:
    """reason 闭集逐项（receiver_not_registered/invalid_sender_id/invalid_receiver_id/broadcast_convention_violation）。"""
    violations = context["violations"]
    expected_reasons = {
        "receiver_not_registered": "receiver_not_registered",
        "invalid_sender_id": "invalid_sender_id",
        "invalid_receiver_id_send": "invalid_receiver_id",
        "invalid_receiver_id_subscribe": "invalid_receiver_id",
        "broadcast_convention_violation_bcast": "broadcast_convention_violation",
        "broadcast_convention_violation_unicast": "broadcast_convention_violation",
    }
    assert set(violations) == set(expected_reasons)
    for key, reason in expected_reasons.items():
        error = violations[key]
        assert error.code == "EXCEPTION_461", f"{key}: code 应为 EXCEPTION_461"
        assert error.context["reason"] == reason, f"{key}: reason 应为 {reason}，实际 {error.context.get('reason')}"


@then("挂起等待者收到 461 总线关闭异常")
def then_pending_waiter_461(context: dict[str, Any]) -> None:
    """在途等待者结局 = 461 bus_closed（非 CancelledError——与「close 后新调用 → 461」结局统一）。"""
    from src.domain.exceptions import SAPBusStateError

    outcome = context["pending_wait_outcome"]
    assert isinstance(outcome, SAPBusStateError), f"在途等待者应收 SAPBusStateError，实际 {outcome!r}"
    assert outcome.code == "EXCEPTION_461"
    assert outcome.context["reason"] == "bus_closed"


@then("二次关闭幂等零异常")
def then_second_close_idempotent(context: dict[str, Any]) -> None:
    """二次 close 空表幂等（已 resolve 保留条目不炸 InvalidStateError——future.done 守卫）。"""
    assert context["second_close_raised"] is False


@then("关闭态三方法均抛 461 且 reason 为 bus_closed")
def then_closed_three_methods(context: dict[str, Any]) -> None:
    """close 后三方法统一 461 bus_closed（消息丢弃语义：无 redelivery——V1 非持久知悉注记）。"""
    expected = {"send", "subscribe", "wait_for_response"}
    assert set(context["closed_calls"]) == expected
    for name, error in context["closed_calls"].items():
        assert error.code == "EXCEPTION_461", f"{name}: code 应为 EXCEPTION_461"
        assert error.context["reason"] == "bus_closed", f"{name}: reason 应为 bus_closed"


# ==== AC-2: 请求-响应关联（correlation Future + 超时 460） ====


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-2.1 - REQUEST 等待与 RESPONSE correlation 关联送达",
)
def test_ac_2_1_correlation_delivery(context: dict[str, Any]) -> None:
    """AC-2.1: REQUEST→RESPONSE 关联链闭合（OD-9 锚=REQUEST.message_id）+ 双动作送达。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-2.2 - 超时 460 与索引清理及迟到双响应防御",
)
def test_ac_2_2_timeout_and_defense(context: dict[str, Any]) -> None:
    """AC-2.2: 超时三段式 + 索引清理 + 迟到防御 + 双响应幂等两 Edge 子用例。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-2.3 - 默认无等待语义与并发请求键控隔离",
)
def test_ac_2_3_no_wait_and_concurrent(context: dict[str, Any]) -> None:
    """AC-2.3: 默认无等待 + 未挂起超时路径 + 两对并发键控隔离。"""


@given("请求方与响应方两方装配（响应方回发指向请求的 RESPONSE）")
def given_pair_with_reply(context: dict[str, Any]) -> None:
    """两方装配（双方各订阅自身 UUID 标识；响应方 handler 回发 RESPONSE——correlation_id=请求 message_id）。"""
    from src.interfaces.sap.bus import InProcessSAPBus
    from src.interfaces.sap.types import MessageType

    blackboard = _StubBlackboard()
    guard = _RecordingIsolationGuard()
    bus = InProcessSAPBus(blackboard=blackboard, guard=guard)
    context["_buses"].append(bus)
    requester_id = str(uuid.uuid4())
    responder_id = str(uuid.uuid4())
    requester_received: list[Any] = []
    responder_received: list[Any] = []

    def _make_responder_handler(responder: str, received: list[Any]) -> Any:
        async def on_responder(message: Any) -> None:
            received.append(message)
            if message.message_type is MessageType.REQUEST:
                await bus.send(
                    _make_message(
                        sender_id=responder,
                        receiver_id=message.sender_id,
                        message_type=MessageType.RESPONSE,
                        content="响应内容",
                        correlation_id=message.message_id,
                    )
                )

        return on_responder

    bus.subscribe(requester_id, _make_handler(requester_received))
    bus.subscribe(responder_id, _make_responder_handler(responder_id, responder_received))
    context.update(
        bus=bus,
        requester_id=requester_id,
        responder_id=responder_id,
        requester_received=requester_received,
        responder_received=responder_received,
    )


@when("请求方发送 requires_response 的 REQUEST 并等待其 message_id 锚")
def when_request_wait(context: dict[str, Any]) -> None:
    """send → wait(message_id)（OD-9 锚约定——不支持「REQUEST 预设自 correlation_id」形态）。"""
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    request = _make_message(
        sender_id=context["requester_id"],
        receiver_id=context["responder_id"],
        message_type=MessageType.REQUEST,
        content="请求内容",
        requires_response=True,
        timeout_seconds=5,
    )

    async def _flow() -> Any:
        await bus.send(request)
        return await bus.wait_for_response(request.message_id, timeout_seconds=5.0)

    context["request_message"] = request
    context["response_message"] = _run_async(context["_loop"], _flow())


@then("wait_for_response 返回消息的 correlation_id 与请求 message_id 相等")
def then_correlation_matches(context: dict[str, Any]) -> None:
    """关联链闭合（OD-9：correlation_id == REQUEST.message_id——JMS 同款惯例）。"""
    assert context["response_message"].correlation_id == context["request_message"].message_id, (
        "correlation 锚应等于 REQUEST.message_id"
    )


@then("请求方 handler 同时收到该 RESPONSE（双动作送达）")
def then_requester_dual_delivery(context: dict[str, Any]) -> None:
    """DC-10 双动作：resolve 与入队送达正交——请求方 handler 也收到 RESPONSE。"""
    from src.interfaces.sap.types import MessageType

    requester_received = context["requester_received"]
    _run_async(context["_loop"], _wait_for_delivery([requester_received], 1))
    request_id = context["request_message"].message_id
    matches = [m for m in requester_received if m.message_type is MessageType.RESPONSE and m.correlation_id == request_id]
    assert len(matches) == 1, f"请求方 handler 应恰收到一条关联 RESPONSE，实际 {len(matches)} 条"


@given("请求方与静默响应方装配（订阅自身且无人回发）")
def given_silent_pair(context: dict[str, Any]) -> None:
    """超时载体装配（静默响应方——handler 记录但不回发）。"""
    from src.interfaces.sap.bus import InProcessSAPBus

    blackboard = _StubBlackboard()
    guard = _RecordingIsolationGuard()
    bus = InProcessSAPBus(blackboard=blackboard, guard=guard)
    context["_buses"].append(bus)
    requester_id = str(uuid.uuid4())
    silent_responder_id = str(uuid.uuid4())
    requester_received: list[Any] = []
    silent_received: list[Any] = []
    bus.subscribe(requester_id, _make_handler(requester_received))
    bus.subscribe(silent_responder_id, _make_handler(silent_received))
    context.update(
        bus=bus,
        requester_id=requester_id,
        silent_responder_id=silent_responder_id,
        requester_received=requester_received,
        silent_received=silent_received,
    )


@when("发送 REQUEST 后无人回发并以 0.1 秒短超时等待")
def when_timeout_wait(context: dict[str, Any]) -> None:
    """短超时快速验证（计时锚=wait_for_response 调用时刻——duration 语义）。"""
    from src.domain.exceptions import SAPTimeoutError
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    request = _make_message(
        sender_id=context["requester_id"],
        receiver_id=context["silent_responder_id"],
        message_type=MessageType.REQUEST,
        requires_response=True,
        timeout_seconds=5,
    )
    _run_async(context["_loop"], bus.send(request))
    with pytest.raises(SAPTimeoutError) as exc_info:
        _run_async(context["_loop"], bus.wait_for_response(request.message_id, timeout_seconds=0.1))
    context["timeout_error"] = exc_info.value
    context["timed_out_request"] = request


@then("抛出 460 且 context 携带 correlation_id 与 timeout_seconds")
def then_460_context(context: dict[str, Any]) -> None:
    """460 三段式（code + context 双键——correlation_id 统一 str() 换算口径）。"""
    error = context["timeout_error"]
    assert error.code == "EXCEPTION_460"
    assert error.context["correlation_id"] == str(context["timed_out_request"].message_id)
    assert error.context["timeout_seconds"] == 0.1


@then("超时后索引零残留（迟到 RESPONSE 零崩溃零 resolve）")
def then_late_response_no_crash(context: dict[str, Any]) -> None:
    """迟到防御：超时后回发 RESPONSE——零崩溃零 resolve（Future 已清理），正常单播送达承载。"""
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    request = context["timed_out_request"]
    late_reply = _make_message(
        sender_id=context["silent_responder_id"],
        receiver_id=context["requester_id"],
        message_type=MessageType.RESPONSE,
        content="迟到响应",
        correlation_id=request.message_id,
    )
    # 零崩溃：send 正常完成（不抛 InvalidStateError——Future 已清理防御面 log warning）
    _run_async(context["_loop"], bus.send(late_reply))
    requester_received = context["requester_received"]
    _run_async(context["_loop"], _wait_for_delivery([requester_received], 1))
    assert any(m.message_id == late_reply.message_id for m in requester_received), "迟到 RESPONSE 应正常单播送达"


@then("正常双响应幂等（第二条 RESPONSE 零 InvalidStateError）")
def then_duplicate_response_idempotent(context: dict[str, Any]) -> None:
    """幂等 resolve 守卫（future.done 检查——JMS 重复投递幂等惯例；wait 挂起中第二条到达）。"""
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    requester_id = context["requester_id"]

    async def _double_response_flow() -> Any:
        request = _make_message(
            sender_id=requester_id,
            receiver_id=context["silent_responder_id"],
            message_type=MessageType.REQUEST,
            requires_response=True,
            timeout_seconds=5,
        )
        await bus.send(request)
        wait_task = asyncio.ensure_future(bus.wait_for_response(request.message_id, timeout_seconds=5.0))
        first_reply = _make_message(
            sender_id=context["silent_responder_id"],
            receiver_id=requester_id,
            message_type=MessageType.RESPONSE,
            content="第一条响应",
            correlation_id=request.message_id,
        )
        second_reply = _make_message(
            sender_id=context["silent_responder_id"],
            receiver_id=requester_id,
            message_type=MessageType.RESPONSE,
            content="第二条响应",
            correlation_id=request.message_id,
        )
        await bus.send(first_reply)  # resolve 生效
        await bus.send(second_reply)  # 幂等守卫：零 InvalidStateError 零二次 resolve
        return await wait_task

    response = _run_async(context["_loop"], _double_response_flow())
    assert response is not None
    assert response.content == "第一条响应", "幂等 resolve 应保留第一条响应（log-ignore 第二条）"


@given("两对请求响应装配（响应方各自回发）")
def given_two_pairs(context: dict[str, Any]) -> None:
    """并发键控隔离载体（两对独立 UUID——响应方 handler 记录并回发指向请求）。"""
    from src.interfaces.sap.bus import InProcessSAPBus
    from src.interfaces.sap.types import MessageType

    blackboard = _StubBlackboard()
    guard = _RecordingIsolationGuard()
    bus = InProcessSAPBus(blackboard=blackboard, guard=guard)
    context["_buses"].append(bus)
    pairs: list[dict[str, Any]] = []
    for pair_index in range(2):
        requester_id = str(uuid.uuid4())
        responder_id = str(uuid.uuid4())
        requester_received: list[Any] = []
        responder_received: list[Any] = []

        def _make_responder_handler(responder: str, received: list[Any], index: int) -> Any:
            async def on_responder(message: Any) -> None:
                received.append(message)
                if message.message_type is MessageType.REQUEST:
                    await bus.send(
                        _make_message(
                            sender_id=responder,
                            receiver_id=message.sender_id,
                            message_type=MessageType.RESPONSE,
                            content=f"响应-{index}",
                            correlation_id=message.message_id,
                        )
                    )

            return on_responder

        bus.subscribe(requester_id, _make_handler(requester_received))
        bus.subscribe(responder_id, _make_responder_handler(responder_id, responder_received, pair_index))
        pairs.append(
            {
                "requester_id": requester_id,
                "responder_id": responder_id,
                "requester_received": requester_received,
                "responder_received": responder_received,
            }
        )
    context["bus"] = bus
    context["pairs"] = pairs


@when("发送 requires_response 为 False 的 NOTIFICATION")
def when_send_notification_no_wait(context: dict[str, Any]) -> None:
    """默认无等待语义（correlation 索引零挂起条目——requires_response=False 不登记）。"""
    from src.domain.exceptions import SAPTimeoutError
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    pair = context["pairs"][0]
    notification = _make_message(
        sender_id=pair["requester_id"],
        receiver_id=pair["responder_id"],
        message_type=MessageType.NOTIFICATION,
        content="通知直达",
    )
    _run_async(context["_loop"], bus.send(notification))
    context["notification_message"] = notification

    # 未挂起 correlation 的 wait 按超时路径处理（等满 timeout 抛 460——不 special-case）
    with pytest.raises(SAPTimeoutError) as exc_info:
        _run_async(context["_loop"], bus.wait_for_response(notification.message_id, timeout_seconds=0.05))
    context["no_wait_timeout_error"] = exc_info.value


@then("消息直达 handler 且未挂起 correlation 的等待按超时路径抛 460")
def then_no_wait_semantics(context: dict[str, Any]) -> None:
    """直送保真 + 无条目超时路径（460 三段式——correlation_id/timeout_seconds context 键）。"""
    notification = context["notification_message"]
    responder_received = context["pairs"][0]["responder_received"]
    _run_async(context["_loop"], _wait_for_delivery([responder_received], 1))
    assert any(m.message_id == notification.message_id for m in responder_received), "NOTIFICATION 应直达 handler"
    error = context["no_wait_timeout_error"]
    assert error.code == "EXCEPTION_460"
    assert error.context["correlation_id"] == str(notification.message_id)
    assert error.context["timeout_seconds"] == 0.05


@then("两对并发请求各自关联 resolve 互不干扰")
def then_concurrent_isolation(context: dict[str, Any]) -> None:
    """correlation 键控隔离（两对并发 wait 各自 resolve——content 标识交叉验证）。"""
    from src.interfaces.sap.types import MessageType

    bus = context["bus"]
    pairs = context["pairs"]

    async def _concurrent_flow() -> tuple[list[Any], list[Any]]:
        requests = []
        for pair in pairs:
            request = _make_message(
                sender_id=pair["requester_id"],
                receiver_id=pair["responder_id"],
                message_type=MessageType.REQUEST,
                requires_response=True,
                timeout_seconds=5,
            )
            await bus.send(request)
            requests.append(request)
        responses = await asyncio.gather(
            *(bus.wait_for_response(request.message_id, timeout_seconds=5.0) for request in requests)
        )
        return requests, responses

    requests, responses = _run_async(context["_loop"], _concurrent_flow())
    for pair_index, (request, response) in enumerate(zip(requests, responses, strict=True)):
        assert response.correlation_id == request.message_id, f"第 {pair_index} 对关联错乱"
        assert response.content == f"响应-{pair_index}", f"第 {pair_index} 对响应串扰（键控隔离破坏）"


# ==== AC-3: 公共黑板交互（守卫集成 + MVCC 写入 + fail-loud 462） ====


@pytest.mark.redis  # 场景函数级 redis marker（AC-5 分档钦定——文件级不挂 redis）
@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-3.1 - 公共黑板 MVCC 写入（真实 Redis）",
)
def test_ac_3_1_mvcc_real_redis(context: dict[str, Any]) -> None:
    """AC-3.1: 真实 Redis MVCC 版本精确递增 + get 读回 + 自清理。"""


@pytest.mark.redis
@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-3.2 - L4 真实隔离链写黑板 449 透传",
)
def test_ac_3_2_l4_real_chain_449(context: dict[str, Any]) -> None:
    """AC-3.2: 真实实例化 L4 CEO Agent + 真实 guard——黑板写 449 透传 + 零写入。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-3.3 - 零写入边界与写失败 fail-loud 462",
)
def test_ac_3_3_invisible_and_fail_loud(context: dict[str, Any]) -> None:
    """AC-3.3: 替身面——零 post + 四键投影 + 正交性计数锚 + 449 透传 + 462 不投递。"""


@given("真实 Redis 可用且装配真实 RedisPublicBlackboard 与放行守卫")
def given_real_redis_blackboard(context: dict[str, Any]) -> None:
    """真实 Redis 场景（场景级独立客户端——跨循环记忆锚；ping 探测动态 skip）。"""
    import redis.asyncio as aioredis

    from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
    from src.interfaces.sap.bus import InProcessSAPBus

    cfg = context["_env_config"]
    client = aioredis.Redis(
        host=cfg.redis.host,
        port=cfg.redis.port,
        password=cfg.redis.password,
        decode_responses=True,
    )
    try:
        _run_async(context["_loop"], client.ping())
    except Exception as exc:
        _run_async(context["_loop"], client.close())
        pytest.skip(f"Redis not available: {exc}")

    conversation_id = uuid.uuid4()
    blackboard = RedisPublicBlackboard(redis_client=client)
    bus = InProcessSAPBus(blackboard=blackboard, guard=_RecordingIsolationGuard())
    context["_buses"].append(bus)
    receiver_id = str(uuid.uuid4())
    received: list[Any] = []
    bus.subscribe(receiver_id, _make_handler(received))
    blackboard_key = build_key("blackboard", str(conversation_id))
    version_key = build_key("blackboard", str(conversation_id), "version")
    context["_real_redis_client"] = client
    context["_cleanup_keys"].extend([blackboard_key, version_key])
    context["real_bus"] = bus
    context["real_blackboard"] = blackboard
    context["real_receiver_id"] = receiver_id
    context["real_received"] = received
    context["blackboard_conversation_id"] = conversation_id
    context["blackboard_key"] = blackboard_key
    context["blackboard_version_key"] = version_key


@when("发送两条 blackboard_visible 为真的消息")
def when_send_two_visible(context: dict[str, Any]) -> None:
    """两次可见写入（MVCC incr 版本递增载体——同 conversation_id）。"""
    from src.interfaces.sap.types import MessageType

    bus = context["real_bus"]
    conversation_id = context["blackboard_conversation_id"]
    messages = []
    for index in range(2):
        message = _make_message(
            sender_id=str(uuid.uuid4()),
            receiver_id=context["real_receiver_id"],
            message_type=MessageType.NOTIFICATION,
            blackboard_visible=True,
            conversation_id=conversation_id,
            content=f"黑板可见消息-{index}",
        )
        _run_async(context["_loop"], bus.send(message))
        messages.append(message)
    context["visible_messages"] = messages


@then("get 读回版本号恰为 v1 与 v1+1 两级递增")
def then_mvcc_versions(context: dict[str, Any]) -> None:
    """v2==v1+1 精确递增（宽松形态对跳版错误实现不红——R3-F31 收紧）+ 版本断言走 get 读回。"""
    entries = _run_async(
        context["_loop"],
        context["real_blackboard"].get(str(context["blackboard_conversation_id"])),
    )
    versions = [entry["version"] for entry in entries]
    assert len(versions) == 2, f"应有两条黑板条目，实际 {len(versions)} 条"
    assert versions[0] >= 1, "首版本号应 >= 1"
    assert versions[1] == versions[0] + 1, f"MVCC 版本应精确递增（v2==v1+1），实际 {versions}"


@then("读回 content 的 message_id 与发送消息一致")
def then_blackboard_content(context: dict[str, Any]) -> None:
    """写入可读回（content 四键最小投影——枚举显式 .value 字符串化）。"""
    entries = _run_async(
        context["_loop"],
        context["real_blackboard"].get(str(context["blackboard_conversation_id"])),
    )
    messages = context["visible_messages"]
    for entry, message in zip(entries, messages, strict=True):
        assert entry["content"]["message_id"] == str(message.message_id)
        assert entry["content"]["message_type"] == message.message_type.value
        assert entry["content"]["content"] == message.content
        assert entry["content"]["priority"] == message.priority.value
        assert entry["agent_id"] == message.sender_id


@then("teardown 后黑板键与版本键均不存在")
def then_blackboard_keys_cleaned(context: dict[str, Any]) -> None:
    """自清理（只清自己创建的键——双键 delete 幂等 + exists 复核）。"""
    client = context["_real_redis_client"]
    blackboard_key = context["blackboard_key"]
    version_key = context["blackboard_version_key"]
    _run_async(context["_loop"], client.delete(blackboard_key, version_key))
    assert not _run_async(context["_loop"], client.exists(blackboard_key)), f"黑板键未清理: {blackboard_key}"
    assert not _run_async(context["_loop"], client.exists(version_key)), f"版本键未清理: {version_key}"


@given("真实 Redis 可用且真实实例化 L4 CEO Agent 并装配真实隔离链")
def given_real_isolation_chain(context: dict[str, Any]) -> None:
    """真实链装配（5-5 AC-3.3 装配形态延续——L4 出生即硬隔离；agent/isolation 键 teardown 清理）。"""
    import redis.asyncio as aioredis

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository
    from src.interfaces.sap.bus import InProcessSAPBus

    cfg = context["_env_config"]
    client = aioredis.Redis(
        host=cfg.redis.host,
        port=cfg.redis.port,
        password=cfg.redis.password,
        decode_responses=True,
    )
    try:
        _run_async(context["_loop"], client.ping())
    except Exception as exc:
        _run_async(context["_loop"], client.close())
        pytest.skip(f"Redis not available: {exc}")

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
    context["_buses"].append(bus)
    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    result = _run_async(context["_loop"], instantiate_use_case.execute(role=AgentRole.CEO))
    target_receiver_id = str(uuid.uuid4())
    bus.subscribe(target_receiver_id, lambda message: None)  # 哑接收方（注册检查在黑板桥之前——守卫判定单边取 actor 侧）
    context["_real_redis_client"] = client
    context["_agent_ids"].append(result.agent_id)
    context["real_bus"] = bus
    context["real_blackboard"] = blackboard
    context["l4_agent_id"] = result.agent_id
    context["l4_target_receiver_id"] = target_receiver_id
    context["l4_conversation_id"] = uuid.uuid4()


@when("L4 Agent 发送 blackboard_visible 为真的消息")
def when_l4_send_visible(context: dict[str, Any]) -> None:
    """真实链 L4 写黑板（READ_ONLY → 449 原样上抛——守卫判定单边取 actor 侧隔离状态）。"""
    from src.domain.exceptions import IsolationOperationForbiddenError
    from src.interfaces.sap.types import MessageType

    bus = context["real_bus"]
    message = _make_message(
        sender_id=str(context["l4_agent_id"]),
        receiver_id=context["l4_target_receiver_id"],
        message_type=MessageType.NOTIFICATION,
        blackboard_visible=True,
        conversation_id=context["l4_conversation_id"],
        content="L4 黑板可见消息",
    )
    with pytest.raises(IsolationOperationForbiddenError) as exc_info:
        _run_async(context["_loop"], bus.send(message))
    context["caught_449"] = exc_info.value


@then("抛出 449 且 context 的 reason 为 data_isolation:read_only")
def then_449_passthrough(context: dict[str, Any]) -> None:
    """449 透传三段式（零包装——5-5 分码语义完整保留：reason=data_isolation:read_only）。"""
    error = context["caught_449"]
    assert error.code == "EXCEPTION_449"
    assert error.context["reason"] == "data_isolation:read_only"


@then("真实黑板 get 读回为空（零写入）")
def then_zero_blackboard_write(context: dict[str, Any]) -> None:
    """守卫拒绝 → 黑板零写入（真实 get 空断言）。"""
    entries = _run_async(
        context["_loop"],
        context["real_blackboard"].get(str(context["l4_conversation_id"])),
    )
    assert entries == [], f"守卫拒绝后黑板应零写入，实际 {entries}"


@given("两个接收方以 UUID 标识订阅消息")
def given_two_receivers(context: dict[str, Any]) -> None:
    """两接收方订阅（正交性计数锚 N≥2 前提）。"""
    bus = context["bus"]
    receiver_ids = [str(uuid.uuid4()) for _ in range(2)]
    received: dict[str, list[Any]] = {rid: [] for rid in receiver_ids}
    for receiver_id in receiver_ids:
        bus.subscribe(receiver_id, _make_handler(received[receiver_id]))
    context["receiver_ids"] = receiver_ids
    context["received"] = received


@when("发送 blackboard_visible 为假的 NOTIFICATION 与 BROADCAST 消息")
def when_send_invisible(context: dict[str, Any]) -> None:
    """零写入边界（含 BROADCAST+False 组合——OD-7 正交开关行为锚；发送后即时快照）。"""
    from src.interfaces.sap.types import MessageType

    messages = [
        _make_message(
            receiver_id=context["receiver_ids"][0],
            message_type=MessageType.NOTIFICATION,
            blackboard_visible=False,
            content="不可见通知",
        ),
        _make_message(
            receiver_id="broadcast",
            message_type=MessageType.BROADCAST,
            blackboard_visible=False,
            content="不可见广播",
        ),
    ]
    for message in messages:
        _run_async(context["_loop"], context["bus"].send(message))
    context["invisible_post_snapshot"] = len(context["stub_blackboard"].post_calls)
    context["invisible_guard_snapshot"] = len(context["stub_guard"].calls)


@then("替身黑板零 post 调用（可见性开关是唯一闸门）")
def then_zero_post_when_invisible(context: dict[str, Any]) -> None:
    """False → 零 post 零守卫调用（发送后即时快照——后续可见消息不污染断言）。"""
    assert context["invisible_post_snapshot"] == 0, "blackboard_visible=False 应零 post 调用"
    assert context["invisible_guard_snapshot"] == 0, "不可见消息不应触碰守卫"


@when("发送 blackboard_visible 为真的 NOTIFICATION 消息")
def when_send_visible_notification(context: dict[str, Any]) -> None:
    """可见单播（守卫放行 → post 四键投影载体）。"""
    from src.interfaces.sap.types import MessageType

    message = _make_message(
        receiver_id=context["receiver_ids"][0],
        message_type=MessageType.NOTIFICATION,
        blackboard_visible=True,
        content="可见通知",
    )
    _run_async(context["_loop"], context["bus"].send(message))
    context["visible_notification"] = message
    # when 时快照 post/守卫调用对象（BDD 全部 when 先于 then 执行——[-1] 索引会被
    # 后续可见 BROADCAST/守卫拒绝操作污染）
    context["visible_notification_post_call"] = context["stub_blackboard"].post_calls[-1]
    context["visible_notification_guard_call"] = context["stub_guard"].calls[-1]


@then("post 四键投影与守卫四参数锚正确")
def then_post_projection_and_guard_params(context: dict[str, Any]) -> None:
    """content 四键最小投影（枚举显式 .value）+ 守卫 actor/target/resource/operation 四参数。"""
    from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

    message = context["visible_notification"]
    call = context["visible_notification_post_call"]
    assert call["conversation_id"] == str(message.conversation_id), (
        "conversation_id 应 str 换算（message.py L48-49 归 5.11 注记兑现）"
    )
    assert call["agent_id"] == message.sender_id
    assert call["content"] == {
        "message_id": str(message.message_id),
        "message_type": message.message_type.value,
        "content": message.content,
        "priority": message.priority.value,
    }
    assert call["confidence"] == 1.0
    guard_call = context["visible_notification_guard_call"]
    assert guard_call["actor"] == uuid.UUID(message.sender_id)
    assert guard_call["target"] == uuid.UUID(message.receiver_id)
    assert guard_call["resource"] is IsolationResource.BLACKBOARD
    assert guard_call["operation"] is AccessOperation.WRITE


@when("发送 blackboard_visible 为真的 BROADCAST 消息")
def when_send_visible_broadcast(context: dict[str, Any]) -> None:
    """正交性计数锚载体（一次黑板写 + N 投递——OD-7）。"""
    from src.interfaces.sap.types import MessageType

    message = _make_message(
        receiver_id="broadcast",
        message_type=MessageType.BROADCAST,
        blackboard_visible=True,
        content="可见广播",
    )
    context["pre_broadcast_post_count"] = len(context["stub_blackboard"].post_calls)
    _run_async(context["_loop"], context["bus"].send(message))
    context["visible_broadcast"] = message
    context["broadcast_guard_call"] = context["stub_guard"].calls[-1]


@then("BROADCAST 可见消息 post 计数恰为 1 且全员送达")
def then_broadcast_post_once(context: dict[str, Any]) -> None:
    """正交性唯一可写断言（per-receiver 各 post 一次的错误实现必红——R3-F31）+ BROADCAST 守卫 target==actor。"""
    message = context["visible_broadcast"]
    post_count_after = len(context["stub_blackboard"].post_calls)
    assert post_count_after == context["pre_broadcast_post_count"] + 1, (
        f"BROADCAST 可见消息应恰 post 一次（一次黑板写 + N 投递），实际新增 "
        f"{post_count_after - context['pre_broadcast_post_count']} 次"
    )
    # BROADCAST 形态守卫 target==actor（广播无特定目标——when 时快照对象）
    guard_call = context["broadcast_guard_call"]
    assert guard_call["actor"] == uuid.UUID(message.sender_id)
    assert guard_call["target"] == guard_call["actor"]
    # 全员送达（N=2 接收方各收到同一 message_id；累计送达 = 不可见1+不可见广播2+可见通知1+可见广播2 = 6）
    received_lists = list(context["received"].values())
    _run_async(context["_loop"], _wait_for_delivery(received_lists, 6))
    broadcast_id = message.message_id
    for receiver_id, received in context["received"].items():
        matches = [m for m in received if m.message_id == broadcast_id]
        assert len(matches) == 1, f"接收方 {receiver_id} 应恰收到一条可见 BROADCAST，实际 {len(matches)} 条"


@when("替身守卫拒绝后发送可见消息")
def when_guard_rejects(context: dict[str, Any]) -> None:
    """守卫拒绝形态（替身抛真实 IsolationOperationForbiddenError——透传零包装载体）。"""
    from src.domain.exceptions import IsolationOperationForbiddenError
    from src.interfaces.sap.types import MessageType

    guard = context["stub_guard"]
    guard.reject_with = IsolationOperationForbiddenError(
        agent_id="stub-agent",
        operation="write",
        reason="data_isolation:read_only",
    )
    message = _make_message(
        receiver_id=context["receiver_ids"][0],
        message_type=MessageType.NOTIFICATION,
        blackboard_visible=True,
        content="被拒消息",
    )
    context["pre_reject_delivery_snapshot"] = sum(len(v) for v in context["received"].values())
    with pytest.raises(IsolationOperationForbiddenError) as exc_info:
        _run_async(context["_loop"], context["bus"].send(message))
    context["guard_rejected_error"] = exc_info.value


@then("449 原样透传且消息不投递")
def then_449_passthrough_stub(context: dict[str, Any]) -> None:
    """透传不包装（严格类型断言）+ 发送原子性（黑板承诺面失败则整条 send 失败——先黑板后入队）。"""
    from src.domain.exceptions import IsolationOperationForbiddenError

    error = context["guard_rejected_error"]
    assert type(error) is IsolationOperationForbiddenError, "守卫拒绝应原样透传（不包装为 SAP 异常）"
    assert error.code == "EXCEPTION_449"
    delivery_total = sum(len(v) for v in context["received"].values())
    assert delivery_total == context["pre_reject_delivery_snapshot"], "被拒消息不应投递"


@when("替换黑板为 post 返 0 的失败替身后发送可见消息")
def when_failing_blackboard(context: dict[str, Any]) -> None:
    """fail-loud 462（post 返 0 检测——OD-7；新 bus 实例隔离原场景投递计数）。"""
    from src.domain.exceptions import SAPBlackboardWriteError
    from src.interfaces.sap.bus import InProcessSAPBus
    from src.interfaces.sap.types import MessageType

    failing_blackboard = _FailingBlackboard()
    failing_bus = InProcessSAPBus(blackboard=failing_blackboard, guard=_RecordingIsolationGuard())
    context["_buses"].append(failing_bus)
    failing_received: list[Any] = []
    failing_bus.subscribe(context["receiver_ids"][0], _make_handler(failing_received))
    message = _make_message(
        receiver_id=context["receiver_ids"][0],
        message_type=MessageType.NOTIFICATION,
        blackboard_visible=True,
        content="写失败消息",
    )
    with pytest.raises(SAPBlackboardWriteError) as exc_info:
        _run_async(context["_loop"], failing_bus.send(message))
    context["write_failure_error"] = exc_info.value
    context["failed_message"] = message
    context["failing_blackboard"] = failing_blackboard
    context["failing_received"] = failing_received


@then("抛出 462 且消息不投递")
def then_462_fail_loud(context: dict[str, Any]) -> None:
    """462 三段式（code + context conversation_id）+ post 确被调用且返 0 + 发送原子性。"""
    error = context["write_failure_error"]
    message = context["failed_message"]
    assert error.code == "EXCEPTION_462"
    assert error.context["conversation_id"] == str(message.conversation_id)
    assert len(context["failing_blackboard"].post_calls) == 1, "post 应被调用且恰一次"
    assert context["failing_received"] == [], "写失败消息不应投递"


# ==== AC-4: 序列化契约与端口接线 ====


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-4.1 - JSON 序列化往返保真",
)
def test_ac_4_1_serialization_roundtrip(context: dict[str, Any]) -> None:
    """AC-4.1: 15 字段满载实例 JSON 往返逐字段保真 + 坏 JSON ValidationError 透传。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-4.2 - 组合根 sap_bus 端口注册与注入链",
)
def test_ac_4_2_port_wiring(context: dict[str, Any]) -> None:
    """AC-4.2: resolve 四件 + 注入链 + fail-fast ConfigurationError。"""


@given("构造 15 字段全显式赋值的 SAPMessage 实例")
def given_full_message(context: dict[str, Any]) -> None:
    """满载实例（UUID/datetime tz-aware/枚举/dict 嵌套全显式——最大体积形态）。"""
    from datetime import UTC, datetime

    from src.domain.events.enums import IsolationLevel
    from src.interfaces.sap.message import SAPMessage
    from src.interfaces.sap.types import MessagePriority, MessageType

    context["full_message"] = SAPMessage(
        message_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        sender_id=str(uuid.uuid4()),
        receiver_id=str(uuid.uuid4()),
        message_type=MessageType.DEBATE,
        priority=MessagePriority.URGENT,
        content="满载消息内容",
        correlation_id=uuid.uuid4(),
        isolation_level=IsolationLevel.L2_COLLAB,
        blackboard_visible=True,
        timestamp=datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC),
        subject="序列化验收",
        context={"嵌套": {"层级": 1}, "tags": ["a", "b"]},
        requires_response=True,
        timeout_seconds=120,
    )


@when("serialize 后 deserialize 往返")
def when_roundtrip(context: dict[str, Any]) -> None:
    """JSON wire format 往返（Pydantic v2 model_dump_json/model_validate_json 薄封装）。"""
    from src.interfaces.sap.bus import deserialize, serialize

    payload = serialize(context["full_message"])
    assert isinstance(payload, str)
    context["serialized_payload"] = payload
    context["roundtrip_message"] = deserialize(payload)


@then("往返实例与原实例逐字段相等")
def then_roundtrip_equal(context: dict[str, Any]) -> None:
    """15 字段逐值保真（UUID/datetime ISO 感知/枚举 str 值/dict 嵌套——NFR-INT-05 格式基线）。"""
    original = context["full_message"]
    roundtrip = context["roundtrip_message"]
    assert roundtrip == original, "往返实例应 Pydantic 全等"
    for field_name in type(original).model_fields:
        assert getattr(roundtrip, field_name) == getattr(original, field_name), f"字段 {field_name} 往返失真"


@then("坏 JSON 反序列化抛 pydantic ValidationError 原样透传")
def then_bad_json_passthrough(context: dict[str, Any]) -> None:
    """Schema 层契约（bus 不吞不包装——严格类型断言防包装先例）。"""
    from pydantic import ValidationError

    from src.interfaces.sap.bus import deserialize

    with pytest.raises(ValidationError) as exc_info:
        deserialize('{"message_id": "not-a-json"')
    assert type(exc_info.value) is ValidationError, "坏 JSON 应 pydantic ValidationError 原样透传"


@given("组合根 bootstrap 完成")
def given_bootstrap(context: dict[str, Any]) -> None:
    """组合根注册中心就绪（bootstrap 由 tests/conftest _bootstrap_once 会话级自动调用——验收禁二次
    调用：同进程二次 bootstrap 因 lambda spec 对象不等炸 ConflictError，prefect/instantiation 先例）。"""
    from src.domain.ports.registry import _global_registry

    assert _global_registry.get("public_blackboard") is not None, "组合根未 bootstrap（conftest 应已执行）"


@when("resolve 解析 sap_bus 端口")
def when_resolve_sap_bus(context: dict[str, Any]) -> None:
    """首次 resolve（SINGLETON 惰性首解析——lambda 此时执行）。"""
    from src.domain.ports.resolver import resolve

    context["sap_bus_instance"] = resolve("sap_bus")


@then("返回 InProcessSAPBus 实例且 PortSpec 元数据四项正确")
def then_resolve_metadata(context: dict[str, Any]) -> None:
    """resolve 四件（可达/isinstance 双判别/PortSpec 元数据四项/SINGLETON）。"""
    from src.domain.ports.registry import Lifetime, _global_registry
    from src.interfaces.sap.bus import InProcessSAPBus, SAPBus

    instance = context["sap_bus_instance"]
    assert instance is not None, "resolve('sap_bus') 应可达"
    assert isinstance(instance, SAPBus), "@runtime_checkable Protocol 判别"
    assert isinstance(instance, InProcessSAPBus)
    spec = _global_registry.get("sap_bus")
    assert spec is not None, "端口 sap_bus 未注册"
    assert spec.version == "v1.0.0"
    assert spec.lifetime is Lifetime.SINGLETON, "有状态总线——订阅表+correlation 索引+优先级队列跨调用共享"
    assert spec.owner == "platform"
    assert spec.tags == ("agent", "sap", "collaboration")


@then("实例的黑板与守卫依赖注入链非空")
def then_injection_chain(context: dict[str, Any]) -> None:
    """两依赖接线可达（lambda 注入 public_blackboard + isolation_guard_service）。"""
    instance = context["sap_bus_instance"]
    assert getattr(instance, "_blackboard", None) is not None, "黑板依赖注入链断裂"
    assert getattr(instance, "_guard", None) is not None, "守卫依赖注入链断裂"


@then("依赖缺失时抛 ConfigurationError（fail-fast 非降级）")
def then_fail_fast_configuration(context: dict[str, Any]) -> None:
    """fail-fast 装配（lambda 显式翻译三元组——与可选依赖 resolve_optional→None 降级族相反裁定）。"""
    from src.domain.exceptions import ConfigurationError
    from src.domain.ports.registry import _global_registry

    class _MissingDepsResolver:
        """缺依赖分发替身（resolve 未注册名抛 KeyError——resolver 真实形态）。"""

        def resolve(self, name: str) -> Any:
            raise KeyError(f"Port not registered: {name}")

        def resolve_optional(self, name: str) -> Any:
            return None

    spec = _global_registry.get("sap_bus")
    assert spec is not None
    impl = spec.impl
    assert callable(impl), "sap_bus impl 应为可调用 lambda"
    with pytest.raises(ConfigurationError) as exc_info:
        impl(_MissingDepsResolver())
    assert exc_info.value.code == "EXCEPTION_101"


# ==== AC-5: 性能三锚（委托计时 + 并发） ====


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-5.1 - 消息传递与序列化 P95 双锚（委托计时）",
)
def test_ac_5_1_p95_anchors(context: dict[str, Any]) -> None:
    """AC-5.1: 传递 P95<200ms + 序列化 P95<50ms（委托计时 + 常量单源等值断言）。"""


@scenario(
    "test_acceptance_sap_protocol.feature",
    "AC-5.2 - 50 并发消息全送达与队列清空",
)
def test_ac_5_2_concurrency_50(context: dict[str, Any]) -> None:
    """AC-5.2: 50 并发 send 全送达零丢失 + 队列清空（积压归零）。"""


@given("集成计时委托模块已加载（_PERF_CACHE 委托采样）")
def given_perf_delegate(context: dict[str, Any]) -> None:
    """委托采样（helper cache-or-compute——命中或首次采样，同 xdist_group 同 worker 串行）。"""
    from tests.integration.test_integration_sap_protocol import sample_sap_perf

    context["perf_summary"] = _run_async(context["_loop"], sample_sap_perf())


@when("读取委托采样的传递与序列化 P95 摘要")
def when_read_perf_summary(context: dict[str, Any]) -> None:
    """常量单源 import（验收侧禁双真源——集成模块定义/验收 import）。"""
    from tests.integration.test_integration_sap_protocol import (
        SAP_CONCURRENCY_FLOOR,
        SAP_DELIVERY_P95_LIMIT_SECONDS,
        SAP_SERIALIZATION_P95_LIMIT_SECONDS,
    )

    summary = context["perf_summary"]
    context["delivery_p95"] = summary["delivery_p95_seconds"]
    context["serialization_p95"] = summary["serialization_p95_seconds"]
    context["delivery_received_count"] = summary["delivery_received_count"]
    context["delivery_limit"] = SAP_DELIVERY_P95_LIMIT_SECONDS
    context["serialization_limit"] = SAP_SERIALIZATION_P95_LIMIT_SECONDS
    context["concurrency_floor"] = SAP_CONCURRENCY_FLOOR


@then("传递 P95 小于 200ms（常量单源 SAP_DELIVERY_P95_LIMIT_SECONDS 等值断言）")
def then_delivery_p95(context: dict[str, Any]) -> None:
    """epics L1923 钦定（等值断言是常量改错值变异锚的充分条件——v1.3.0）。"""
    assert context["delivery_limit"] == 0.2, "SAP_DELIVERY_P95_LIMIT_SECONDS 应为 0.2（常量单源）"
    assert context["delivery_p95"] < context["delivery_limit"], (
        f"消息传递 P95 应 < {context['delivery_limit']}s，实际 {context['delivery_p95']}s"
    )


@then("序列化 P95 小于 50ms（常量单源 SAP_SERIALIZATION_P95_LIMIT_SECONDS 等值断言）")
def then_serialization_p95(context: dict[str, Any]) -> None:
    """epics L1924 钦定（15 字段满载实例往返口径）。"""
    assert context["serialization_limit"] == 0.05, "SAP_SERIALIZATION_P95_LIMIT_SECONDS 应为 0.05（常量单源）"
    assert context["serialization_p95"] < context["serialization_limit"], (
        f"序列化 P95 应 < {context['serialization_limit']}s，实际 {context['serialization_p95']}s"
    )


@then("正向锚收到计数为 21")
def then_positive_anchor(context: dict[str, Any]) -> None:
    """warmup 1 + 20 采样全送达（防静默跳过假绿）+ 并发下限常量等值锚。"""
    assert context["delivery_received_count"] == 21, (
        f"正向锚应为 21（warmup 1 + 20 采样），实际 {context['delivery_received_count']}"
    )
    assert context["concurrency_floor"] == 50, "SAP_CONCURRENCY_FLOOR 应为 50（常量单源）"


@when("一次性并发发送 50 条消息")
def when_send_50_concurrent(context: dict[str, Any]) -> None:
    """gather 50 并发 send（red_blue_debate 50 并发先例同款）。"""
    bus = context["bus"]
    messages = [_make_message(receiver_id=context["receiver_id"], content=f"并发消息-{index}") for index in range(50)]

    async def _send_all() -> None:
        await asyncio.gather(*(bus.send(message) for message in messages))

    _run_async(context["_loop"], _send_all())
    context["concurrent_messages"] = messages


@then("50 条全部送达零丢失")
def then_all_50_delivered(context: dict[str, Any]) -> None:
    """50/50 逐条断言零丢失（red_blue_debate 先例同款）。"""
    _run_async(context["_loop"], _wait_for_delivery([context["delivery_order"]], 50))
    received_ids = {message.message_id for message in context["delivery_order"]}
    for message in context["concurrent_messages"]:
        assert message.message_id in received_ids, f"消息 {message.message_id} 丢失"


@then("接收方处理完成后队列清空（积压归零）")
def then_queue_drained(context: dict[str, Any]) -> None:
    """积压口径行为面承载（50/50 handler 完成计数——串行消费全部完成后 per-receiver 队列必空）。"""
    assert len(context["delivery_order"]) == 50, f"应 50 条全送达，实际 {len(context['delivery_order'])}"


# ==== 收尾: 开发结束验收（完成清单逐项确认） ====


@scenario(
    "test_acceptance_sap_protocol.feature",
    "开发结束 - 交付完成清单逐项确认",
)
def test_delivery_complete_checklist(context: dict[str, Any]) -> None:
    """收尾: src 七件 + tests 八件 + 注册联动全部就位。"""


@given("Story 5.11 交付完成")
def given_delivery_complete(context: dict[str, Any]) -> None:
    """收尾验收前置（开发结束状态——存在性与关键符号断言载体）。"""


@then("src 完成清单七件全部就位且关键符号可导入")
def then_src_checklist(context: dict[str, Any]) -> None:
    """2 新建 + 5 修改生产/注册面文件（口径注记 v1.1.0——两文档件不计入七件数）。"""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    src_files = [
        "src/interfaces/sap/bus.py",
        "src/domain/exceptions/sap_exceptions.py",
        "src/interfaces/sap/__init__.py",
        "src/domain/exceptions/__init__.py",
        "src/domain/exceptions/_code_ranges.py",
        "src/interfaces/api/exception_handlers.py",
        "src/composition_root.py",
    ]
    for relative in src_files:
        assert (repo_root / relative).exists(), f"src 完成清单缺件: {relative}"

    from src.domain.exceptions import SAPBlackboardWriteError, SAPBusStateError, SAPTimeoutError
    from src.interfaces.sap import InProcessSAPBus, SAPBus

    assert callable(SAPBus) and callable(InProcessSAPBus), "__init__ 导出面缺失"
    assert SAPTimeoutError.code == "EXCEPTION_460"
    assert SAPBusStateError.code == "EXCEPTION_461"
    assert SAPBlackboardWriteError.code == "EXCEPTION_462"


@then("tests 完成清单全部就位")
def then_tests_checklist(context: dict[str, Any]) -> None:
    """八件（unit 两件 + contracts 一件 + integration 一件 + architecture 一件 + acceptance 两件 + 追加一件）。"""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    test_files = [
        "tests/unit/interfaces/sap/test_bus.py",
        "tests/unit/domain/exceptions/test_sap_exceptions.py",
        "tests/contracts/test_port_contract_sap_bus.py",
        "tests/integration/test_integration_sap_protocol.py",
        "tests/unit/architecture/test_arch_sap_protocol.py",
        "tests/acceptance/test_acceptance_sap_protocol.feature",
        "tests/acceptance/test_acceptance_sap_protocol.py",
        "tests/unit/interfaces/api/test_exception_handlers.py",
    ]
    for relative in test_files:
        assert (repo_root / relative).exists(), f"tests 完成清单缺件: {relative}"


@then("组合根注册与导出及文档联动全部就位")
def then_wiring_checklist(context: dict[str, Any]) -> None:
    """注册三动作（CODE_RANGES sap 段/HTTP 映射三行/__init__ 导出）+ 组合根 sap_bus 注册。"""
    from fastapi import status

    from src.domain.exceptions import SAPBlackboardWriteError, SAPBusStateError, SAPTimeoutError
    from src.domain.exceptions._code_ranges import CODE_RANGES
    from src.domain.ports.registry import _global_registry
    from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

    assert CODE_RANGES.get("sap") == (460, 469), "CODE_RANGES sap 段未注册"
    assert EXCEPTION_HTTP_MAP[SAPTimeoutError] == status.HTTP_504_GATEWAY_TIMEOUT
    assert EXCEPTION_HTTP_MAP[SAPBusStateError] == status.HTTP_409_CONFLICT
    assert EXCEPTION_HTTP_MAP[SAPBlackboardWriteError] == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert _global_registry.get("sap_bus") is not None, "组合根 sap_bus 注册缺失"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
