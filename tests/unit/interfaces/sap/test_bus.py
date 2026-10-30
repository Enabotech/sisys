"""InProcessSAPBus 单元测试——Story 5.11 SAP 协议运行时。

四批：Task 2 循环 A 总线核心（分发/优先级/校验面/关闭态/异步 handler/订阅面）+
循环 B 序列化（JSON wire format 往返）+ Task 3 请求-响应关联 + Task 4 黑板桥。

替身：_StubBlackboard/_RecordingIsolationGuard/_FailingBlackboard（手写零 IO
duck-typing 端口契约——验收文件同款形态独立定义；Mock/Fake/Real 三层策略单元面）。

Run with:
    poetry run pytest tests/unit/interfaces/sap/test_bus.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.domain.exceptions import SAPBusStateError
from src.interfaces.sap.bus import InProcessSAPBus
from src.interfaces.sap.message import SAPMessage
from src.interfaces.sap.types import MessagePriority, MessageType


def _make_message(**overrides: Any) -> SAPMessage:
    """构造 SAPMessage（默认最小必填 + 覆盖——OD-5 UUID 测试标识）。"""
    kwargs: dict[str, Any] = {
        "message_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "sender_id": str(uuid.uuid4()),
        "receiver_id": str(uuid.uuid4()),
        "message_type": MessageType.NOTIFICATION,
        "content": "SAP 单测消息",
    }
    kwargs.update(overrides)
    return SAPMessage(**kwargs)


class _StubBlackboard:
    """手写零 IO 黑板替身（duck-typing 实现 PublicBlackboard——捕获 post 调用，版本递增）。"""

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


class _FailingBlackboard(_StubBlackboard):
    """post 返 0 失败替身（OD-7 fail-loud 检测点）。"""

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict[str, Any],
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """捕获调用但返回 0。"""
        await super().post(conversation_id, agent_id, content, confidence=confidence, citations=citations)
        return 0


class _SlowBlackboard(_StubBlackboard):
    """post 慢速替身（黑板桥 await 挂起载体——send/close 竞态窗口构造，R1-F1）。"""

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict[str, Any],
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """延迟后落账（让渡点——主协程在此窗口内 close 构造竞态）。"""
        await asyncio.sleep(0.2)
        return await super().post(conversation_id, agent_id, content, confidence=confidence, citations=citations)


class _RecordingIsolationGuard:
    """手写零 IO 守卫替身（duck-typing 实现 IsolationGuardPort——放行/拒绝可控）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.reject_with: Exception | None = None

    async def ensure_agent_access(
        self, actor_agent_id: uuid.UUID, target_agent_id: uuid.UUID, resource: Any, operation: Any
    ) -> None:
        """捕获守卫调用（reject_with 置位时抛出）。"""
        self.calls.append({"actor": actor_agent_id, "target": target_agent_id, "resource": resource, "operation": operation})
        if self.reject_with is not None:
            raise self.reject_with

    async def ensure_agent_executable(self, agent_id: uuid.UUID) -> Any:
        """协议面补全桩（duck-typing 结构匹配——bus 仅消费 ensure_agent_access）。"""
        return None

    async def ensure_tool_access(self, agent_id: uuid.UUID, tool_name: str) -> None:
        """协议面补全桩。"""


def _noop_handler(message: SAPMessage) -> None:
    """静默 handler（订阅注册/校验载体——mypy 具名函数优于 lambda 推断）。"""


#: 当前用例活跃总线注册表（autouse fixture 统一 close——消费任务 cancel+gather 必须在
#: loop 存活期完成；孤儿协程于 loop 关闭后被 GC 会触发 Queue.get 清理路径的
#: call_soon→RuntimeError('Event loop is closed') unraisable 噪声——归因错位到无关测试）
_ACTIVE_BUSES: list[InProcessSAPBus] = []


def _make_bus() -> tuple[InProcessSAPBus, _StubBlackboard, _RecordingIsolationGuard]:
    """构造总线三件套（bus + 替身黑板 + 替身守卫；bus 登记注册表供用例后统一收尾）。"""
    blackboard = _StubBlackboard()
    guard = _RecordingIsolationGuard()
    bus = InProcessSAPBus(blackboard=blackboard, guard=guard)
    _ACTIVE_BUSES.append(bus)
    return bus, blackboard, guard


@pytest.fixture(autouse=True)
async def _close_active_buses() -> AsyncGenerator[None, None]:
    """用例后关闭本用例创建的全部总线（close 幂等——用例内已 close 的零副作用）。"""
    yield
    for active_bus in _ACTIVE_BUSES:
        await active_bus.close()
    _ACTIVE_BUSES.clear()


async def _wait_delivery(received_lists: list[list[Any]], expected: int, timeout: float = 5.0) -> None:
    """等待送达计数达标（接收列表的列表——sum 口径；条件轮询上限禁 sleep 死等）。"""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if sum(len(one) for one in received_lists) >= expected:
            return
        await asyncio.sleep(0.01)
    actual = sum(len(one) for one in received_lists)
    pytest.fail(f"等待送达超时：期望 {expected} 条，实际 {actual} 条")


# ==== 循环 A：单播分发（AC-1） ====


class TestUnicastDelivery:
    """四种单播类型逐一送达（15 字段全等 + epics 十键 + 行为输入键）。"""

    @pytest.mark.parametrize(
        "message_type",
        [MessageType.REQUEST, MessageType.RESPONSE, MessageType.NOTIFICATION, MessageType.DEBATE],
    )
    async def test_unicast_type_delivered_equal(self, message_type: MessageType) -> None:
        """每种类型：handler 收到实例与发送实例 15 字段全等 + 十键逐键。"""
        bus, _, _ = _make_bus()
        received: list[SAPMessage] = []

        async def handler(message: SAPMessage) -> None:
            received.append(message)

        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, handler)
        message = _make_message(
            receiver_id=receiver_id,
            message_type=message_type,
            requires_response=message_type is MessageType.REQUEST,
            subject="单测单播",
            context={"round": 1},
        )
        await bus.send(message)
        await _wait_delivery([received], 1)
        got = received[0]
        assert got == message, "15 字段 Pydantic 实例应全等"
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
        for key in ten_keys:
            assert getattr(got, key) == getattr(message, key), f"十键断言失败: {key}"
        assert got.requires_response == message.requires_response
        assert got.timeout_seconds == message.timeout_seconds

    async def test_self_delivery(self) -> None:
        """sender 订阅自身 id 时收到自己的消息（自收合法——AC-1 And 订阅语义钦定）。"""
        bus, _, _ = _make_bus()
        agent_id = str(uuid.uuid4())
        received: list[SAPMessage] = []

        async def handler(message: SAPMessage) -> None:
            received.append(message)

        bus.subscribe(agent_id, handler)
        await bus.send(_make_message(sender_id=agent_id, receiver_id=agent_id))
        await _wait_delivery([received], 1)
        assert received[0].sender_id == agent_id


# ==== 循环 A：BROADCAST 全员送达（AC-1） ====


class TestBroadcastDelivery:
    """BROADCAST（receiver_id="broadcast"）全员送达语义。"""

    async def test_broadcast_reaches_all_subscribers(self) -> None:
        """三接收方全员收到同一 message_id（零遗漏）。"""
        bus, _, _ = _make_bus()
        receiver_ids = [str(uuid.uuid4()) for _ in range(3)]
        received: dict[str, list[SAPMessage]] = {rid: [] for rid in receiver_ids}
        for rid in receiver_ids:

            async def handler(message: SAPMessage, target: list[SAPMessage] = received[rid]) -> None:
                target.append(message)

            bus.subscribe(rid, handler)
        message = _make_message(receiver_id="broadcast", message_type=MessageType.BROADCAST)
        await bus.send(message)
        await _wait_delivery([r for r in received.values()], 3)
        for rid in receiver_ids:
            assert [m.message_id for m in received[rid]] == [message.message_id]

    async def test_broadcast_snapshot_freezes_at_send_time(self) -> None:
        """接收方集合快照在 send 时刻定格——send 后 subscribe 者不收到。"""
        bus, _, _ = _make_bus()
        early_id = str(uuid.uuid4())
        early_received: list[SAPMessage] = []

        async def early_handler(message: SAPMessage) -> None:
            early_received.append(message)

        bus.subscribe(early_id, early_handler)
        await bus.send(_make_message(receiver_id="broadcast", message_type=MessageType.BROADCAST))
        await _wait_delivery([early_received], 1)
        late_received: list[SAPMessage] = []

        async def late_handler(message: SAPMessage) -> None:
            late_received.append(message)

        bus.subscribe(str(uuid.uuid4()), late_handler)
        await asyncio.sleep(0.05)
        assert late_received == [], "send 后订阅者不应收到先前的 BROADCAST"

    async def test_broadcast_zero_subscribers_silent_success(self) -> None:
        """零订阅者 BROADCAST 静默成功零投递（全员=当前空集）。"""
        bus, _, _ = _make_bus()
        message = _make_message(receiver_id="broadcast", message_type=MessageType.BROADCAST)
        await bus.send(message)  # 零异常零投递


# ==== 循环 A：优先级出队（AC-1） ====


class TestPriorityOrder:
    """四级优先级 per-receiver 出队（乱序插队 + 同级 FIFO 双观测）。"""

    async def test_priority_insertion_and_fifo(self) -> None:
        """六级乱序（LOW/NORMAL/HIGH/URGENT 各一 + 2×NORMAL）→ URGENT>HIGH>NORMAL×3（入队序）>LOW。

        双观测（R1-F4）：priority 序断插队语义 + content 序断同级 FIFO 内序——
        seq 破平局计数器被破坏（非单调/常量变异）时三条 NORMAL 乱序出队，
        content 序断言必红（priority 序仍 [NORMAL,NORMAL,NORMAL] 不可见）。
        """
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        delivery_order: list[str] = []

        async def handler(message: SAPMessage) -> None:
            delivery_order.append(message.content)

        bus.subscribe(receiver_id, handler)
        priorities = (
            MessagePriority.LOW,
            MessagePriority.NORMAL,
            MessagePriority.HIGH,
            MessagePriority.URGENT,
            MessagePriority.NORMAL,
            MessagePriority.NORMAL,
        )
        for index, priority in enumerate(priorities):
            await bus.send(_make_message(receiver_id=receiver_id, priority=priority, content=f"msg-{index}"))
        await _wait_delivery([delivery_order], 6)
        # 出队 content 期望：URGENT(msg-3) > HIGH(msg-2) > NORMAL×3 按入队序(msg-1/4/5) > LOW(msg-0)
        assert delivery_order == ["msg-3", "msg-2", "msg-1", "msg-4", "msg-5", "msg-0"], (
            f"优先级出队顺序错误（含同级 FIFO 内序）: {delivery_order}"
        )


# ==== 循环 A：校验面 fail-loud（AC-1/OD-5/OD-8） ====


class TestValidationFace:
    """send/subscribe 校验面（461 reason 闭集——fail-loud）。"""

    async def test_unregistered_receiver_raises_461(self) -> None:
        """未注册接收方单播 → 461 receiver_not_registered（三段式：raises+code+context）。"""
        bus, _, _ = _make_bus()
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.send(_make_message(receiver_id=str(uuid.uuid4())))
        error = exc_info.value
        assert error.code == "EXCEPTION_461"
        assert error.context["reason"] == "receiver_not_registered"

    async def test_invalid_sender_id_raises_461(self) -> None:
        """非 UUID sender → 461 invalid_sender_id。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, _noop_handler)
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.send(_make_message(sender_id="ceo-not-uuid", receiver_id=receiver_id))
        error = exc_info.value
        assert error.code == "EXCEPTION_461"
        assert error.context["reason"] == "invalid_sender_id"

    async def test_invalid_receiver_id_send_raises_461(self) -> None:
        """非 UUID 非 broadcast 的 receiver（send 侧）→ 461 invalid_receiver_id。"""
        bus, _, _ = _make_bus()
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.send(_make_message(receiver_id="cfo-not-uuid"))
        error = exc_info.value
        assert error.code == "EXCEPTION_461"
        assert error.context["reason"] == "invalid_receiver_id"

    def test_invalid_receiver_id_subscribe_raises_461(self) -> None:
        """subscribe 侧同样校验 UUID（防死订阅）→ 461 invalid_receiver_id。"""
        bus, _, _ = _make_bus()
        with pytest.raises(SAPBusStateError) as exc_info:
            bus.subscribe("cto-not-uuid", lambda message: None)
        error = exc_info.value
        assert error.code == "EXCEPTION_461"
        assert error.context["reason"] == "invalid_receiver_id"

    def test_subscribe_broadcast_convention_value_rejected(self) -> None:
        """ "broadcast" 约定值不可作订阅标识（广播约定值非实体）→ invalid_receiver_id。"""
        bus, _, _ = _make_bus()
        with pytest.raises(SAPBusStateError) as exc_info:
            bus.subscribe("broadcast", lambda message: None)
        assert exc_info.value.context["reason"] == "invalid_receiver_id"

    @pytest.mark.parametrize(
        ("message_type", "receiver_id"),
        [
            (MessageType.BROADCAST, None),  # BROADCAST 类型 + 合法 UUID receiver（方向一）
            (MessageType.NOTIFICATION, "broadcast"),  # 非 BROADCAST 类型 + "broadcast"（方向二）
        ],
        ids=["bcast-type-with-uuid-receiver", "unicast-type-with-broadcast-receiver"],
    )
    async def test_broadcast_convention_violation_both_directions(
        self, message_type: MessageType, receiver_id: str | None
    ) -> None:
        """组合双向违规 → 461 broadcast_convention_violation（OD-8——方向一 receiver 取合法 UUID）。"""
        bus, _, _ = _make_bus()
        receiver = receiver_id if receiver_id is not None else str(uuid.uuid4())
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.send(_make_message(receiver_id=receiver, message_type=message_type))
        error = exc_info.value
        assert error.code == "EXCEPTION_461"
        assert error.context["reason"] == "broadcast_convention_violation"

    async def test_broadcast_valid_convention_accepted(self) -> None:
        """合法组合（BROADCAST + "broadcast"）放行——约定值豁免仅此组合。"""
        bus, _, _ = _make_bus()
        received: list[SAPMessage] = []
        receiver_id = str(uuid.uuid4())

        async def handler(message: SAPMessage) -> None:
            received.append(message)

        bus.subscribe(receiver_id, handler)
        await bus.send(_make_message(receiver_id="broadcast", message_type=MessageType.BROADCAST))
        await _wait_delivery([received], 1)
        assert received[0].message_type is MessageType.BROADCAST


# ==== 循环 A：关闭态（AC-1 close 动作清单） ====


class TestCloseSemantics:
    """close 动作清单（幂等/取消任务/清空队列/Future→461/清空登记表）+ 关闭态三方法。"""

    async def test_closed_send_raises_461(self) -> None:
        """close 后 send → 461 bus_closed。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, _noop_handler)
        await bus.close()
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.send(_make_message(receiver_id=receiver_id))
        assert exc_info.value.context["reason"] == "bus_closed"

    async def test_closed_subscribe_raises_461(self) -> None:
        """close 后 subscribe → 461 bus_closed。"""
        bus, _, _ = _make_bus()
        await bus.close()
        with pytest.raises(SAPBusStateError) as exc_info:
            bus.subscribe(str(uuid.uuid4()), lambda message: None)
        assert exc_info.value.context["reason"] == "bus_closed"

    async def test_closed_wait_for_response_raises_461(self) -> None:
        """close 后 wait_for_response → 461 bus_closed（关闭态检查先行——stub 开路径不触达）。"""
        bus, _, _ = _make_bus()
        await bus.close()
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.wait_for_response(uuid.uuid4(), timeout_seconds=1.0)
        assert exc_info.value.context["reason"] == "bus_closed"

    async def test_close_idempotent(self) -> None:
        """二次 close 幂等（空表不炸 InvalidStateError）。"""
        bus, _, _ = _make_bus()
        await bus.close()
        await bus.close()  # 二次关闭零异常

    async def test_validation_order_closed_first(self) -> None:
        """校验次序钦定：开闭态首位（closed bus 上载荷违规报 bus_closed 非 invalid_sender_id）。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, _noop_handler)
        await bus.close()
        with pytest.raises(SAPBusStateError) as exc_info:
            await bus.send(_make_message(sender_id="not-uuid", receiver_id=receiver_id))
        assert exc_info.value.context["reason"] == "bus_closed", "开闭态检查应先于载荷校验"

    async def test_close_cancels_tasks_and_clears_queues(self) -> None:
        """close 取消全部消费任务 + 清空 per-receiver 队列（白盒——内部状态可观测）。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, _noop_handler)
        await bus.send(_make_message(receiver_id=receiver_id))
        await bus.close()
        tasks = getattr(bus, "_consumer_tasks", {})
        queues = getattr(bus, "_queues", {})
        assert all(task.cancelled() or task.done() for task in tasks.values()), "消费任务应被取消/完成"
        assert all(queue.empty() for queue in queues.values()), "队列应清空"

    async def test_close_no_waiter_future_retrieved_cleanly(self) -> None:
        """send 后无人 wait 即 close：无等待者 Future 消化 retrieved 标记（R1-F2）。

        消化行覆盖载体：close 内 set_exception 后同步调 exception()——不产 asyncio
        ERROR 级 never-retrieved 噪音；exception() 不清结果，取回的 461 语义完整
        （等待者若有仍能拿到异常）。
        """
        bus, _, _ = _make_bus()
        responder_id = str(uuid.uuid4())
        bus.subscribe(responder_id, _noop_handler)
        request = _make_message(
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )
        await bus.send(request)
        pending = getattr(bus, "_pending", {})
        assert request.message_id in pending, "send 后条目应已登记"
        future_ref = pending[request.message_id][0]
        await bus.close()
        retrieved = future_ref.exception()  # 取回不炸（InvalidStateError 零）——已消化标记
        assert isinstance(retrieved, SAPBusStateError)
        assert retrieved.context["reason"] == "bus_closed"

    async def test_close_after_resolve_skips_done_future_and_clears_pending(self) -> None:
        """已 resolve 保留条目的 close：future.done() 守卫不炸 InvalidStateError + 登记表清空（R1-F5）。

        变异锚：close 第四动作去掉 done 守卫改全量 set_exception → 本用例 close 处
        InvalidStateError 必红（真实生命周期路径：REQUEST 已 resolve、条目保留、
        对话结束后 close）；去掉 `_pending.clear()` → 白盒空表断言红。
        """
        bus, _, _ = _make_bus()
        requester_id = str(uuid.uuid4())
        responder_id = str(uuid.uuid4())
        bus.subscribe(requester_id, _noop_handler)
        bus.subscribe(responder_id, _noop_handler)
        request = _make_message(
            sender_id=requester_id,
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )
        await bus.send(request)
        reply = _make_message(
            sender_id=responder_id,
            receiver_id=requester_id,
            message_type=MessageType.RESPONSE,
            correlation_id=request.message_id,
            content="已响应",
        )
        await bus.send(reply)  # resolve（DC-11：条目保留不移除）
        pending = getattr(bus, "_pending", {})
        assert request.message_id in pending, "resolve 后条目应保留（DC-11 钦定）"
        assert pending[request.message_id][0].done(), "resolve 后 Future 应已 done"
        await bus.close()  # 全量 set_exception 无守卫的实现在此必炸 InvalidStateError
        assert getattr(bus, "_pending", {}) == {}, "close 第五动作应清空登记表"
        await bus.close()  # 二次 close 幂等

    async def test_close_during_handler_await_returns_promptly(self) -> None:
        """close 取消落在 await handler 挂起点：CancelledError 放行（except Exception 不吞）——R1-F6。

        变异锚：捕获边界改 except BaseException → CancelledError 被吞 → 消费循环回
        queue.get 永候 → close 的 gather 永挂 → 外层 wait_for 超时红。
        """
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        handler_started = asyncio.Event()

        async def slow_handler(message: SAPMessage) -> None:
            handler_started.set()
            await asyncio.sleep(30.0)  # 挂起点——cancel 落在此处（_consume 的 try 块内）

        bus.subscribe(receiver_id, slow_handler)
        await bus.send(_make_message(receiver_id=receiver_id))
        await asyncio.wait_for(handler_started.wait(), timeout=2.0)
        await asyncio.wait_for(bus.close(), timeout=2.0)  # 宽捕获变异下永挂 → 此处超时红
        tasks = getattr(bus, "_consumer_tasks", {})
        assert all(task.cancelled() or task.done() for task in tasks.values()), "消费任务应被取消/完成"


# ==== 循环 A：异步 handler 串行保序 + deliver-continue（AC-1 And） ====


class TestAsyncHandlerSemantics:
    """异步 handler 串行保序 + handler 异常 deliver-continue（DC-11）。"""

    async def test_async_handler_serial_order(self) -> None:
        """同接收方两条消息按入队序处理完成（协程 await 后再出队下一条）。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        events: list[str] = []

        async def handler(message: SAPMessage) -> None:
            events.append(f"start-{message.content}")
            await asyncio.sleep(0.02 if message.content == "first" else 0.0)
            events.append(f"end-{message.content}")

        bus.subscribe(receiver_id, handler)
        await bus.send(_make_message(receiver_id=receiver_id, content="first"))
        await bus.send(_make_message(receiver_id=receiver_id, content="second"))
        deadline = asyncio.get_running_loop().time() + 5.0
        while asyncio.get_running_loop().time() < deadline and len(events) < 4:
            await asyncio.sleep(0.01)
        assert events == ["start-first", "end-first", "start-second", "end-second"], (
            f"串行保序破坏（第二条应等第一条完成）: {events}"
        )

    async def test_handler_exception_deliver_continue(self, caplog: pytest.LogCaptureFixture) -> None:
        """首条 handler 异常 → log warning（含 message_id）→ 继续出队下一条（队列不冻结）。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        received: list[SAPMessage] = []

        async def handler(message: SAPMessage) -> None:
            if message.content == "poison":
                raise RuntimeError("handler 业务异常")
            received.append(message)

        bus.subscribe(receiver_id, handler)
        poison = _make_message(receiver_id=receiver_id, content="poison")
        await bus.send(poison)
        await bus.send(_make_message(receiver_id=receiver_id, content="healthy"))
        await _wait_delivery([received], 1)
        assert [m.content for m in received] == ["healthy"], "毒消息后应继续投递"
        poison2 = _make_message(receiver_id=receiver_id, content="poison")
        await bus.send(poison2)
        await _wait_delivery([received], 1)
        deadline = asyncio.get_running_loop().time() + 2.0
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
            if any(
                str(poison.message_id) in record.getMessage() or str(poison2.message_id) in record.getMessage()
                for record in caplog.records
            ):
                break
        assert any(
            str(poison.message_id) in record.getMessage() or str(poison2.message_id) in record.getMessage()
            for record in caplog.records
        ), "log warning 应含 message_id"
        assert received, "healthy 消息应已送达"

    async def test_sync_handler_supported(self) -> None:
        """同步 handler（返回 None）同受支持（Callable[[SAPMessage], Awaitable[None] | None]）。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        received: list[SAPMessage] = []

        def sync_handler(message: SAPMessage) -> None:
            received.append(message)

        bus.subscribe(receiver_id, sync_handler)
        await bus.send(_make_message(receiver_id=receiver_id))
        await _wait_delivery([received], 1)
        assert received[0].receiver_id == receiver_id


# ==== 循环 A：订阅面语义（AC-1 And 订阅语义钦定） ====


class TestSubscribeFace:
    """订阅面（重复订阅覆盖——dict 语义一致）。"""

    async def test_duplicate_subscribe_overrides(self) -> None:
        """同 receiver_id 重复 subscribe 覆盖（后注册 handler 生效）。"""
        bus, _, _ = _make_bus()
        receiver_id = str(uuid.uuid4())
        first: list[SAPMessage] = []
        second: list[SAPMessage] = []

        async def handler_one(message: SAPMessage) -> None:
            first.append(message)

        async def handler_two(message: SAPMessage) -> None:
            second.append(message)

        bus.subscribe(receiver_id, handler_one)
        bus.subscribe(receiver_id, handler_two)
        await bus.send(_make_message(receiver_id=receiver_id))
        await _wait_delivery([second], 1)
        assert first == [], "旧 handler 应被覆盖不再收"
        assert len(second) == 1


# ==== 循环 B：序列化契约（AC-4） ====


class TestSerialization:
    """JSON wire format 往返保真（NFR-INT-05 格式基线——Pydantic v2 薄封装）。"""

    def test_roundtrip_full_message(self) -> None:
        """15 字段满载实例往返逐字段相等（UUID/datetime tz-aware/枚举 str/dict 嵌套）。"""
        from datetime import UTC, datetime

        from src.domain.events.enums import IsolationLevel

        original = SAPMessage(
            message_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            sender_id=str(uuid.uuid4()),
            receiver_id=str(uuid.uuid4()),
            message_type=MessageType.DEBATE,
            priority=MessagePriority.URGENT,
            content="满载内容",
            correlation_id=uuid.uuid4(),
            isolation_level=IsolationLevel.L2_COLLAB,
            blackboard_visible=True,
            timestamp=datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC),
            subject="序列化单测",
            context={"嵌套": {"层级": 1}, "tags": ["a", "b"]},
            requires_response=True,
            timeout_seconds=120,
        )
        from src.interfaces.sap.bus import deserialize, serialize

        payload = serialize(original)
        assert isinstance(payload, str)
        roundtrip = deserialize(payload)
        assert roundtrip == original
        for field_name in SAPMessage.model_fields:
            assert getattr(roundtrip, field_name) == getattr(original, field_name), f"字段 {field_name} 往返失真"

    def test_bad_json_raises_pydantic_validation_error(self) -> None:
        """坏 JSON → pydantic ValidationError 原样透传（bus 不吞不包装）。"""
        from pydantic import ValidationError

        from src.interfaces.sap.bus import deserialize

        with pytest.raises(ValidationError) as exc_info:
            deserialize('{"message_id": "not-a-json"')
        assert type(exc_info.value) is ValidationError

    def test_missing_field_json_raises_validation_error(self) -> None:
        """缺字段 JSON → pydantic ValidationError（Schema 层契约）。"""
        from pydantic import ValidationError

        from src.interfaces.sap.bus import deserialize

        with pytest.raises(ValidationError):
            deserialize('{"sender_id": "x"}')

    def test_wire_format_stability_basics(self) -> None:
        """wire format 基线（枚举 str 值——IsolationLevel "L2" 形态落 JSON）。"""
        from src.domain.events.enums import IsolationLevel
        from src.interfaces.sap.bus import deserialize, serialize

        message = _make_message(isolation_level=IsolationLevel.L2_COLLAB, priority=MessagePriority.URGENT)
        payload = serialize(message)
        assert '"L2"' in payload, "IsolationLevel 应序列化为 str 值 L2"
        assert '"urgent"' in payload, "priority 应序列化为 str 值 urgent"
        assert deserialize(payload).isolation_level is IsolationLevel.L2_COLLAB


# ==== 循环 B：模块常量（AC-2 无条目兜底——Task 3 消费） ====


class TestModuleConstants:
    """模块级常量基线（SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS 与 SAPMessage 默认对齐）。"""

    def test_default_response_timeout_constant(self) -> None:
        """兜底常量 300.0（与 SAPMessage.timeout_seconds 默认 300 对齐——v1.1.0 钦定）。"""
        from src.interfaces.sap.bus import SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS

        assert SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS == 300.0
        assert SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS == float(_make_message().timeout_seconds)


# ==== Task 3：请求-响应关联（AC-2——wait_for_response + Future 索引 + 超时 460） ====


def _make_pair_bus() -> tuple[InProcessSAPBus, str, str, list[SAPMessage], list[SAPMessage]]:
    """构造请求方/响应方两方装配（响应方 handler 回发指向请求的 RESPONSE——OD-9 锚）。"""
    bus, _, _ = _make_bus()
    requester_id = str(uuid.uuid4())
    responder_id = str(uuid.uuid4())
    requester_received: list[SAPMessage] = []
    responder_received: list[SAPMessage] = []

    async def on_requester(message: SAPMessage) -> None:
        requester_received.append(message)

    async def on_responder(message: SAPMessage) -> None:
        responder_received.append(message)
        if message.message_type is MessageType.REQUEST:
            await bus.send(
                _make_message(
                    sender_id=responder_id,
                    receiver_id=message.sender_id,
                    message_type=MessageType.RESPONSE,
                    content="单测响应",
                    correlation_id=message.message_id,
                )
            )

    bus.subscribe(requester_id, on_requester)
    bus.subscribe(responder_id, on_responder)
    return bus, requester_id, responder_id, requester_received, responder_received


class TestRequestResponse:
    """关联送达（OD-9 锚 = REQUEST.message_id + DC-10 双动作）。"""

    async def test_wait_returns_correlated_response(self) -> None:
        """wait 返回的 RESPONSE correlation_id == 请求 message_id（关联链闭合）。"""
        bus, requester_id, responder_id, _, _ = _make_pair_bus()
        request = _make_message(
            sender_id=requester_id,
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
            timeout_seconds=5,
        )

        async def _flow() -> SAPMessage:
            await bus.send(request)
            return await bus.wait_for_response(request.message_id, timeout_seconds=5.0)

        response = await _flow()
        assert response.correlation_id == request.message_id, "OD-9 锚：correlation_id 应等于 REQUEST.message_id"
        assert response.sender_id == responder_id

    async def test_requester_handler_dual_delivery(self) -> None:
        """DC-10 双动作：resolve 与入队送达正交——请求方 handler 也收到 RESPONSE。"""
        bus, requester_id, responder_id, requester_received, _ = _make_pair_bus()
        request = _make_message(
            sender_id=requester_id,
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )

        async def _flow() -> SAPMessage:
            await bus.send(request)
            return await bus.wait_for_response(request.message_id, timeout_seconds=5.0)

        await _flow()
        await _wait_delivery([requester_received], 1)
        matches = [m for m in requester_received if m.correlation_id == request.message_id]
        assert len(matches) == 1, "请求方 handler 应恰收到一条关联 RESPONSE"

    async def test_timing_anchor_from_wait_call(self) -> None:
        """计时锚点 = wait 调用时刻（duration 语义）——延迟回发判别形态（R1-F7 重构）。

        时序：t=0 send（响应方延迟 1.6s 回发）→ t=0.8 wait(1.2)。
        wait 锚（正确实现）：预算窗口 [0.8, 2.0] ∋ 1.6 → 成功 resolve；
        send 锚（变异——预算从 send 起算）：deadline = 0+1.2 < 1.6 → 超时 460 必红。
        双侧判别余量 0.4s（参数较 1.0/0.5/0.75 加大——xdist 满载假红防护）。
        响应方 handler 自建（不可改共享 _make_pair_bus——1.6s 延迟会传染关联用例）。
        """
        bus, _, _ = _make_bus()
        requester_id = str(uuid.uuid4())
        responder_id = str(uuid.uuid4())

        async def delayed_responder(message: SAPMessage) -> None:
            if message.message_type is MessageType.REQUEST:
                await asyncio.sleep(1.6)
                await bus.send(
                    _make_message(
                        sender_id=responder_id,
                        receiver_id=message.sender_id,
                        message_type=MessageType.RESPONSE,
                        content="延迟响应",
                        correlation_id=message.message_id,
                    )
                )

        bus.subscribe(requester_id, _noop_handler)
        bus.subscribe(responder_id, delayed_responder)
        request = _make_message(
            sender_id=requester_id,
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )

        async def _flow() -> SAPMessage:
            await bus.send(request)
            await asyncio.sleep(0.8)  # send→wait 间隔——send 锚变异下预算已被耗 0.8s
            return await bus.wait_for_response(request.message_id, timeout_seconds=1.2)

        response = await _flow()
        assert response.correlation_id == request.message_id, "wait 锚语义下响应应在预算窗口内到达"


class TestTimeout:
    """超时 460（三段式 + 索引清理 + 迟到防御 + 默认值口径）。"""

    async def test_timeout_raises_460_three_part(self) -> None:
        """短超时 → 460 三段式（code + context 双键——correlation_id str 换算）。"""
        from src.domain.exceptions import SAPTimeoutError

        bus, _, _ = _make_bus()
        responder_id = str(uuid.uuid4())
        bus.subscribe(responder_id, _noop_handler)
        request = _make_message(
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )
        await bus.send(request)
        with pytest.raises(SAPTimeoutError) as exc_info:
            await bus.wait_for_response(request.message_id, timeout_seconds=0.1)
        error = exc_info.value
        assert error.code == "EXCEPTION_460"
        assert error.context["correlation_id"] == str(request.message_id)
        assert error.context["timeout_seconds"] == 0.1

    async def test_timeout_clears_entry_late_response_no_crash(self) -> None:
        """超时后条目清理：迟到 RESPONSE 回发零崩溃零 resolve（正常单播送达承载）。"""
        from src.domain.exceptions import SAPTimeoutError

        bus, _, _ = _make_bus()
        requester_id = str(uuid.uuid4())
        silent_responder_id = str(uuid.uuid4())
        requester_received: list[SAPMessage] = []
        bus.subscribe(requester_id, lambda message: requester_received.append(message))
        bus.subscribe(silent_responder_id, lambda message: None)
        request = _make_message(
            sender_id=requester_id,
            receiver_id=silent_responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )
        await bus.send(request)
        with pytest.raises(SAPTimeoutError):
            await bus.wait_for_response(request.message_id, timeout_seconds=0.05)
        late_reply = _make_message(
            receiver_id=requester_id,
            message_type=MessageType.RESPONSE,
            correlation_id=request.message_id,
            content="迟到响应",
        )
        await bus.send(late_reply)  # 零崩溃（Future 已清理——不抛 InvalidStateError）
        await _wait_delivery([requester_received], 1)
        assert requester_received[0].message_id == late_reply.message_id
        # 索引零残留行为断言：超时后再 wait 同一 correlation 走无条目路径（460——
        # 若超时未清理条目，迟到 resolve 会污染第二次等待使其立即返回非 460）
        with pytest.raises(SAPTimeoutError):
            await bus.wait_for_response(request.message_id, timeout_seconds=0.05)

    async def test_timeout_default_from_request_message(self) -> None:
        """不传 timeout → 取登记条目承载的请求消息 timeout_seconds（300 默认口径）。"""
        from src.domain.exceptions import SAPTimeoutError

        bus, _, _ = _make_bus()
        responder_id = str(uuid.uuid4())
        bus.subscribe(responder_id, _noop_handler)
        request = _make_message(
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
            timeout_seconds=1,
        )
        await bus.send(request)
        with pytest.raises(SAPTimeoutError) as exc_info:
            await bus.wait_for_response(request.message_id, timeout_seconds=None)
        assert exc_info.value.context["timeout_seconds"] == 1

    async def test_no_entry_wait_none_falls_back_to_constant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无条目 + None → SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS 兜底（monkeypatch 短值技法——v1.2.0 钦定）。"""
        from src.domain.exceptions import SAPTimeoutError
        from src.interfaces.sap import bus as sap_bus_module

        monkeypatch.setattr(sap_bus_module, "SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS", 0.05)
        bus, _, _ = _make_bus()
        with pytest.raises(SAPTimeoutError) as exc_info:
            await bus.wait_for_response(uuid.uuid4(), timeout_seconds=None)
        assert exc_info.value.code == "EXCEPTION_460"
        assert exc_info.value.context["timeout_seconds"] == 0.05

    async def test_no_entry_waiter_closed_during_wait_gets_461(self) -> None:
        """无条目等待者挂起中 close → _closed_event 唤醒收 461（R1-F3 事件赢分支）。

        与 close 后入口检查用例（test_closed_wait_for_response_raises_461）的区别：
        等待者先挂起（ensure_future）、close 后到——裸 sleep 形态下该等待者将等满
        收 460（结局分裂）；事件唤醒形态收 461 与有条目在途等待者统一。
        等待者结局必须被 await（禁 fire-and-forget——防 461 换形复活噪音）。
        """
        bus, _, _ = _make_bus()
        waiter = asyncio.ensure_future(bus.wait_for_response(uuid.uuid4(), timeout_seconds=5.0))
        await asyncio.sleep(0.05)  # 让等待者先挂起
        await bus.close()
        with pytest.raises(SAPBusStateError) as exc_info:
            await waiter  # 结局必须被取回
        assert exc_info.value.context["reason"] == "bus_closed"

    async def test_no_entry_waiter_timeout_wins_gets_460(self) -> None:
        """无条目等待者等满超时赢 → 460（R1-F3 超时赢分支——事件未触发）。"""
        from src.domain.exceptions import SAPTimeoutError

        bus, _, _ = _make_bus()
        with pytest.raises(SAPTimeoutError) as exc_info:
            await bus.wait_for_response(uuid.uuid4(), timeout_seconds=0.05)
        assert exc_info.value.code == "EXCEPTION_460"
        assert exc_info.value.context["timeout_seconds"] == 0.05


class TestDuplicateResponse:
    """正常双响应幂等（future.done 守卫）+ 条目生命周期（resolve 不移除条目）。"""

    async def test_double_response_idempotent(self) -> None:
        """wait 挂起中第二条同 correlation RESPONSE → 幂等守卫零 InvalidStateError（log-ignore）。"""
        bus, _, _ = _make_bus()
        requester_id = str(uuid.uuid4())
        responder_id = str(uuid.uuid4())
        bus.subscribe(requester_id, lambda message: None)
        bus.subscribe(responder_id, _noop_handler)
        request = _make_message(
            sender_id=requester_id,
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
        )

        async def _double_flow() -> SAPMessage:
            await bus.send(request)
            wait_task = asyncio.ensure_future(bus.wait_for_response(request.message_id, timeout_seconds=5.0))
            first_reply = _make_message(
                sender_id=responder_id,
                receiver_id=requester_id,
                message_type=MessageType.RESPONSE,
                content="第一条响应",
                correlation_id=request.message_id,
            )
            second_reply = _make_message(
                sender_id=responder_id,
                receiver_id=requester_id,
                message_type=MessageType.RESPONSE,
                content="第二条响应",
                correlation_id=request.message_id,
            )
            await bus.send(first_reply)
            await bus.send(second_reply)  # 幂等守卫：零 InvalidStateError 零二次 resolve
            return await wait_task

        response = await _double_flow()
        assert response.content == "第一条响应", "幂等 resolve 应保留第一条（log-ignore 第二条）"

    async def test_entry_survives_resolve_for_later_wait(self) -> None:
        """条目生命周期：resolve 不移除条目——resolve 之后再 wait 立即复用结果（非伪超时）。"""
        bus, requester_id, responder_id, _, _ = _make_pair_bus()
        request = _make_message(
            sender_id=requester_id,
            receiver_id=responder_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
            timeout_seconds=5,
        )

        async def _flow() -> tuple[SAPMessage, SAPMessage]:
            await bus.send(request)
            first = await bus.wait_for_response(request.message_id, timeout_seconds=5.0)
            # resolve 已发生但条目保留——后置 wait 应立即复用（若 resolve 即移除则落入
            # 无条目路径：等满兜底 300s 伪超时，本用例 5s 上限内必失败）
            second = await bus.wait_for_response(request.message_id, timeout_seconds=None)
            return first, second

        first, second = await asyncio.wait_for(_flow(), timeout=5.0)
        assert first.message_id == second.message_id, "后置 wait 应复用已 resolve 结果"


class TestNoWait:
    """默认无等待语义（requires_response=False 零登记）。"""

    async def test_notification_no_pending_entry(self) -> None:
        """NOTIFICATION 直达 + 该 message_id 的 wait 走无条目超时路径（等满 timeout 抛 460）。"""
        from src.domain.exceptions import SAPTimeoutError

        bus, _, _ = _make_bus()
        responder_id = str(uuid.uuid4())
        received: list[SAPMessage] = []
        bus.subscribe(responder_id, lambda message: received.append(message))
        notification = _make_message(receiver_id=responder_id, message_type=MessageType.NOTIFICATION)
        await bus.send(notification)
        await _wait_delivery([received], 1)
        with pytest.raises(SAPTimeoutError) as exc_info:
            await bus.wait_for_response(notification.message_id, timeout_seconds=0.05)
        assert exc_info.value.context["correlation_id"] == str(notification.message_id)

    async def test_bare_response_none_correlation_skips_resolve(self) -> None:
        """correlation_id=None 的裸 RESPONSE 直接跳过 resolve 查找（非 warning 路径）。"""
        bus, _, _ = _make_bus()
        requester_id = str(uuid.uuid4())
        received: list[SAPMessage] = []
        bus.subscribe(requester_id, lambda message: received.append(message))
        bare_reply = _make_message(receiver_id=requester_id, message_type=MessageType.RESPONSE)
        assert bare_reply.correlation_id is None
        await bus.send(bare_reply)  # 零崩溃零 resolve 查找
        await _wait_delivery([received], 1)
        assert received[0].message_id == bare_reply.message_id


class TestConcurrentWait:
    """并发多请求挂起互不干扰（correlation 键控隔离）。"""

    async def test_two_pairs_concurrent_isolation(self) -> None:
        """两对并发 REQUEST 各自关联 resolve（correlation 键控——响应 content 交叉验证）。"""
        bus, _, _ = _make_bus()
        pairs = []
        for index in range(2):
            requester_id = str(uuid.uuid4())
            responder_id = str(uuid.uuid4())

            async def on_responder(message: SAPMessage, responder: str = responder_id, idx: int = index) -> None:
                if message.message_type is MessageType.REQUEST:
                    await bus.send(
                        _make_message(
                            sender_id=responder,
                            receiver_id=message.sender_id,
                            message_type=MessageType.RESPONSE,
                            content=f"响应-{idx}",
                            correlation_id=message.message_id,
                        )
                    )

            bus.subscribe(requester_id, lambda message: None)
            bus.subscribe(responder_id, on_responder)
            pairs.append((requester_id, responder_id))

        async def _concurrent_flow() -> tuple[list[SAPMessage], list[SAPMessage]]:
            requests = []
            for requester_id, responder_id in pairs:
                request = _make_message(
                    sender_id=requester_id,
                    receiver_id=responder_id,
                    message_type=MessageType.REQUEST,
                    requires_response=True,
                )
                await bus.send(request)
                requests.append(request)
            responses = await asyncio.gather(
                *(bus.wait_for_response(request.message_id, timeout_seconds=5.0) for request in requests)
            )
            return requests, responses

        requests, responses = await asyncio.wait_for(_concurrent_flow(), timeout=5.0)
        for pair_index, (request, response) in enumerate(zip(requests, responses, strict=True)):
            assert response.correlation_id == request.message_id, f"第 {pair_index} 对关联错乱"
            assert response.content == f"响应-{pair_index}", f"第 {pair_index} 对响应串扰"


# ==== Task 4：黑板桥（AC-3——守卫集成 + MVCC 写入 + fail-loud 462，替身面） ====


class TestBlackboardBridge:
    """黑板桥六场景（blackboard_visible 开关 + 守卫参数锚 + 正交性 + 透传 + fail-loud）。"""

    async def test_visible_message_posts_four_key_projection(self) -> None:
        """visible=True → post 四键最小投影（枚举显式 .value 字符串化）+ conversation_id str 换算 + 守卫四参数。"""
        from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource

        bus, blackboard, guard = _make_bus()
        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, _noop_handler)
        message = _make_message(receiver_id=receiver_id, blackboard_visible=True, content="可见消息")
        await bus.send(message)
        assert len(blackboard.post_calls) == 1
        call = blackboard.post_calls[0]
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
        guard_call = guard.calls[0]
        assert guard_call["actor"] == uuid.UUID(message.sender_id)
        assert guard_call["target"] == uuid.UUID(message.receiver_id)
        assert guard_call["resource"] is IsolationResource.BLACKBOARD
        assert guard_call["operation"] is AccessOperation.WRITE

    async def test_invisible_message_zero_post(self) -> None:
        """visible=False → 零 post 零守卫 + 送达不受影响（可见性唯一闸门——含 BROADCAST+False 全员送达）。"""
        from src.interfaces.sap.types import MessageType

        bus, blackboard, guard = _make_bus()
        receiver_a = str(uuid.uuid4())
        receiver_b = str(uuid.uuid4())
        received_a: list[SAPMessage] = []
        received_b: list[SAPMessage] = []
        bus.subscribe(receiver_a, lambda message: received_a.append(message))
        bus.subscribe(receiver_b, lambda message: received_b.append(message))
        unicast = _make_message(receiver_id=receiver_a, blackboard_visible=False)
        broadcast = _make_message(receiver_id="broadcast", message_type=MessageType.BROADCAST, blackboard_visible=False)
        await bus.send(unicast)
        await bus.send(broadcast)
        assert blackboard.post_calls == [], "blackboard_visible=False 应零 post 调用"
        assert guard.calls == [], "不可见消息不应触碰守卫"
        await _wait_delivery([received_a, received_b], 3)
        assert received_a == [unicast, broadcast], "接收方 a 应按序收到单播+广播（False 不影响投递）"
        assert received_b == [broadcast], "BROADCAST+False 应全员送达（零写入不等于零投递）"

    async def test_broadcast_orthogonality_post_once(self) -> None:
        """正交性计数锚：BROADCAST+True+两订阅方 → post 计数恰 1（一次黑板写 + N 投递——R3-F31）。"""
        from src.interfaces.sap.types import MessageType

        bus, blackboard, guard = _make_bus()
        receiver_ids = [str(uuid.uuid4()) for _ in range(2)]
        received: dict[str, list[SAPMessage]] = {rid: [] for rid in receiver_ids}
        for rid in receiver_ids:

            def capture_handler(message: SAPMessage, target: list[SAPMessage] = received[rid]) -> None:
                target.append(message)

            bus.subscribe(rid, capture_handler)
        message = _make_message(receiver_id="broadcast", message_type=MessageType.BROADCAST, blackboard_visible=True)
        pre_count = len(blackboard.post_calls)
        await bus.send(message)
        assert len(blackboard.post_calls) == pre_count + 1, (
            f"BROADCAST 可见消息应恰 post 一次（一次黑板写 + N 投递），实际新增 {len(blackboard.post_calls) - pre_count} 次"
        )
        # BROADCAST 形态守卫 target==actor（广播无特定目标）
        guard_call = guard.calls[-1]
        assert guard_call["actor"] == uuid.UUID(message.sender_id)
        assert guard_call["target"] == guard_call["actor"]
        # 全员送达（两接收方各收到同一 message_id——post 1 次 + 投递 2 次的正交性）
        await _wait_delivery(list(received.values()), 2)
        for rid in receiver_ids:
            assert [m.message_id for m in received[rid]] == [message.message_id]

    async def test_guard_rejection_passthrough_no_delivery(self) -> None:
        """守卫拒绝 → 449 原样透传（严格类型——不包装 SAP 异常）+ 消息不投递（先黑板后入队）。"""
        from src.domain.exceptions import IsolationOperationForbiddenError

        bus, blackboard, guard = _make_bus()
        receiver_id = str(uuid.uuid4())
        received: list[SAPMessage] = []
        bus.subscribe(receiver_id, lambda message: received.append(message))
        guard.reject_with = IsolationOperationForbiddenError(
            agent_id="stub-agent", operation="write", reason="data_isolation:read_only"
        )
        message = _make_message(receiver_id=receiver_id, blackboard_visible=True)
        with pytest.raises(IsolationOperationForbiddenError) as exc_info:
            await bus.send(message)
        assert type(exc_info.value) is IsolationOperationForbiddenError, "守卫拒绝应原样透传（不包装）"
        assert exc_info.value.code == "EXCEPTION_449"
        assert blackboard.post_calls == [], "守卫拒绝后黑板零写入"
        await asyncio.sleep(0.05)
        assert received == [], "被拒消息不应投递（发送原子性——先黑板后入队）"

    async def test_failing_blackboard_raises_462_no_delivery(self) -> None:
        """post 返 0 → SAPBlackboardWriteError 462（fail-loud OD-7）+ 消息不投递。"""
        from src.domain.exceptions import SAPBlackboardWriteError

        failing = _FailingBlackboard()
        guard = _RecordingIsolationGuard()
        bus = InProcessSAPBus(blackboard=failing, guard=guard)
        _ACTIVE_BUSES.append(bus)
        receiver_id = str(uuid.uuid4())
        received: list[SAPMessage] = []
        bus.subscribe(receiver_id, lambda message: received.append(message))
        message = _make_message(receiver_id=receiver_id, blackboard_visible=True)
        with pytest.raises(SAPBlackboardWriteError) as exc_info:
            await bus.send(message)
        error = exc_info.value
        assert error.code == "EXCEPTION_462"
        assert error.context["conversation_id"] == str(message.conversation_id)
        assert len(failing.post_calls) == 1, "post 应被调用且恰一次"
        await asyncio.sleep(0.05)
        assert received == [], "写失败消息不应投递（发送原子性）"

    @pytest.mark.parametrize(
        ("exception_name", "kwargs", "expected_code"),
        [
            (
                "IsolationOperationForbiddenError",
                {"agent_id": "a", "operation": "write", "reason": "data_isolation:read_only"},
                "EXCEPTION_449",
            ),
            (
                "IsolationAccessViolationError",
                {"actor_agent_id": "a", "target_agent_id": "b", "resource": "blackboard", "operation": "write"},
                "EXCEPTION_448",
            ),
            ("AgentNotFoundError", {"agent_id": "a"}, "EXCEPTION_443"),
            ("IsolationStateNotInitializedError", {"agent_id": "a"}, "EXCEPTION_447"),
        ],
        ids=["449-operation-forbidden", "448-access-violation", "443-agent-not-found", "447-state-not-initialized"],
    )
    async def test_guard_family_passthrough_parametrized(
        self, exception_name: str, kwargs: dict[str, str], expected_code: str
    ) -> None:
        """守卫四码（449/448/443/447）全族透传参数化（黑板桥无异常翻译职责）。"""
        import src.domain.exceptions as exceptions_module

        bus, _, guard = _make_bus()
        receiver_id = str(uuid.uuid4())
        bus.subscribe(receiver_id, _noop_handler)
        rejection = getattr(exceptions_module, exception_name)(**kwargs)
        guard.reject_with = rejection
        message = _make_message(receiver_id=receiver_id, blackboard_visible=True)
        with pytest.raises(type(rejection)) as exc_info:
            await bus.send(message)
        raised: Any = exc_info.value
        assert type(raised) is type(rejection), "守卫异常应原类型透传（不包装不上转译）"
        assert raised.code == expected_code

    async def test_send_abandoned_when_closed_during_bridge(self) -> None:
        """黑板桥挂起期间 close：send 恢复后放弃登记与投递（零幽灵条目/零幽灵消息——R1-F1）。

        变异锚：send 去掉 closed 复查 → 恢复后仍执行 register+enqueue——幽灵登记
        条目断言与队列空断言双红；黑板已写入的内容保留（持久面诚实——post_calls==1）。
        """
        from src.interfaces.sap.types import MessageType

        slow = _SlowBlackboard()
        guard = _RecordingIsolationGuard()
        bus = InProcessSAPBus(blackboard=slow, guard=guard)
        _ACTIVE_BUSES.append(bus)
        receiver_id = str(uuid.uuid4())
        received: list[SAPMessage] = []
        bus.subscribe(receiver_id, lambda message: received.append(message))
        message = _make_message(
            receiver_id=receiver_id,
            message_type=MessageType.REQUEST,
            requires_response=True,
            blackboard_visible=True,
        )
        send_task = asyncio.ensure_future(bus.send(message))
        await asyncio.sleep(0.05)  # send 已挂起在慢桥 post 的 await 上
        await bus.close()  # 竞态窗口内 close 完成五动作
        await send_task  # send 恢复——复查 _closed 后放弃（零异常返回）
        assert message.message_id not in getattr(bus, "_pending", {}), "close 后不应残留幽灵登记条目"
        queues = getattr(bus, "_queues", {})
        assert all(queue.empty() for queue in queues.values()), "close 后不应残留幽灵队列消息"
        assert len(slow.post_calls) == 1, "黑板桥已写入的内容保留（持久面与投递面分离）"
        await asyncio.sleep(0.1)
        assert received == [], "close 后消息不投递（在途丢弃语义）"
