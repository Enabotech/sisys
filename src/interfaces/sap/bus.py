"""接口层 SAP 协议总线（Story 5.11 — SAP 协议支持/内部 Agent 通信）

SAPBus 端口（Protocol：send/subscribe/wait_for_response/close）+ InProcessSAPBus
进程内 asyncio 实现 + JSON wire format 序列化契约（serialize/deserialize——Pydantic
v2 model_dump_json/model_validate_json 薄封装，跨进程演进[V2+]格式零漂移——NFR-INT-05
版本兼容基线）。

传输形态（OD-4）：进程内 asyncio 总线（MVP/V1 单进程前提）；跨进程通道（Redis
pub/sub / RabbitMQ）与水平扩展是 V2+ 面——本实现的端口契约与 wire format 在演进时
保持稳定。SAP 非领域事件（5-3 职责边界钉死）：不进 event_channels.yaml/ChannelRouter。

依赖方向（R2 组合注入）：bus（interfaces）← PublicBlackboard + IsolationGuardPort
两应用层基础端口——interfaces→application 合法面。

wire format 注记：序列化是跨进程演进的格式契约；坏 JSON/缺字段反序列化由
pydantic ValidationError 原样透传（Schema 层契约——bus 不吞不包装）。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from src.application.ports.isolation_guard import IsolationGuardPort
from src.application.ports.public_blackboard import PublicBlackboard
from src.domain.exceptions import SAPBlackboardWriteError, SAPBusStateError, SAPTimeoutError
from src.domain.value_objects.isolation_access import AccessOperation, IsolationResource
from src.interfaces.sap.message import SAPMessage
from src.interfaces.sap.types import MessagePriority, MessageType

logger = logging.getLogger(__name__)

#: BROADCAST 消息的 receiver_id 约定值（OD-8 组合双向锁定）
BROADCAST_RECEIVER_ID = "broadcast"

#: wait_for_response 无挂起条目且未显式传参时的兜底超时秒数
#: （与 SAPMessage.timeout_seconds 默认 300 对齐——v1.1.0 钦定）
SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS = 300.0

#: 优先级出队序（数值小者先出——URGENT 插队语义）
_PRIORITY_RANK: dict[MessagePriority, int] = {
    MessagePriority.URGENT: 0,
    MessagePriority.HIGH: 1,
    MessagePriority.NORMAL: 2,
    MessagePriority.LOW: 3,
}


@runtime_checkable
class SAPBus(Protocol):
    """SAP 总线端口（接口层横向协议——architecture.md 规划钦定位）

    四方法契约（Task 0.1 签名级钦定：send/wait_for_response/close 必须 async——
    await 守卫与黑板 post；subscribe 同步注册）。

    积压口径注记：per-receiver 队列长度可观测（NFR-IF-03「积压<100 条」是部署
    容量面——由并发场景队列最终清空行为承载，不设阈值门）。
    """

    async def send(self, message: SAPMessage) -> None:
        """发送消息（校验面 → 黑板桥 → 入队分发）

        close 竞态放弃语义：blackboard_visible=True 的消息在黑板桥 await 挂起期间
        总线被 close 时，本调用静默放弃（不投递不登记不报错——返回 None）——
        已写入黑板的内容保留（持久面诚实）；调用方对「消息被放弃」零显式感知
        通道（V1 契约知悉——需确定性投递语义的调用方应避免 close 并发窗口）。

        Args:
            message: SAP 消息（15 字段 Pydantic 载体）

        Raises:
            SAPBusStateError: 461——未注册接收方/非 UUID 标识/BROADCAST 组合违规/总线已关闭
            IsolationOperationForbiddenError: 449——黑板写守卫拒绝（原样透传）
            SAPBlackboardWriteError: 462——黑板 post 返 0（fail-loud，OD-7）
        """
        ...

    def subscribe(self, receiver_id: str, handler: Callable[[SAPMessage], Awaitable[None] | None]) -> None:
        """订阅消息（同步注册；同 receiver_id 重复 subscribe 覆盖——后注册 handler 生效）

        Args:
            receiver_id: 接收方 Agent 标识（str(agent_id) UUID 形态——OD-5）
            handler: 消息处理器（协程 await 后再出队下一条——串行保序；同步形态同受支持）

        Raises:
            SAPBusStateError: 461——非 UUID 标识（防死订阅）/总线已关闭
        """
        ...

    async def wait_for_response(self, correlation_id: uuid.UUID, timeout_seconds: float | None = None) -> SAPMessage:
        """等待关联响应（correlation_id 锚 = REQUEST.message_id——OD-9 锚约定）

        计时锚点：timeout 从本方法调用时刻起算（asyncio.wait_for duration 语义——
        非 send 时刻 deadline 语义）。

        Args:
            correlation_id: 关联锚（所等待 REQUEST 的 message_id）
            timeout_seconds: 超时秒数（None 时取登记条目承载的请求消息 timeout_seconds；
                无条目时取 SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS 兜底）

        Returns:
            关联的 RESPONSE 消息

        Raises:
            SAPTimeoutError: 460——等满超时无 resolve（超时后条目清理，迟到响应零崩溃）
            SAPBusStateError: 461——总线已关闭
        """
        ...

    async def close(self) -> None:
        """关闭总线（幂等）：取消全部消费任务 + 清空队列 + 挂起等待者收 461 + 清空登记表

        消息丢弃语义：close 丢弃在途（已出队未完成）与滞留（未出队）消息，无
        redelivery——V1 总线非持久语义（优雅排空归 V2+ 知悉注记）。
        """
        ...


def serialize(message: SAPMessage) -> str:
    """序列化 SAPMessage 为 JSON 字符串（wire format）

    Args:
        message: SAP 消息实例

    Returns:
        JSON 字符串（15 字段——UUID/datetime ISO 感知/枚举 str 值/dict 嵌套）
    """
    return message.model_dump_json()


def deserialize(payload: str) -> SAPMessage:
    """反序列化 JSON 字符串为 SAPMessage

    Args:
        payload: JSON 字符串（wire format）

    Returns:
        SAPMessage 实例

    Raises:
        pydantic.ValidationError: 坏 JSON/缺字段（Schema 层契约——原样透传不包装）
    """
    return SAPMessage.model_validate_json(payload)


class InProcessSAPBus:
    """进程内 asyncio 总线实现（OD-4——MVP/V1 单进程前提）

    组件五件（Task 0.1 职责图）：校验面（_validate——开闭态首位/UUID 双侧/组合
    双向/注册检查）/ 黑板桥（_bridge_to_blackboard——Task 4 兑现）/ per-receiver
    优先级队列（heapq 元组 rank+seq 破平局保同级 FIFO）/ correlation 索引
    （_pending——Task 3 兑现）/ 消费任务（_consume——deliver-continue）。

    Attributes:
        _blackboard: 公共黑板端口（R2 组合注入——黑板桥消费）
        _guard: 隔离守卫端口（R2 组合注入——黑板写入前守卫）
        _handlers: 订阅表（receiver_id → handler——重复订阅覆盖）
        _queues: per-receiver 优先级队列表
        _seq_counters: per-receiver 序计数器（同级 FIFO 破平局）
        _consumer_tasks: per-receiver 消费任务表（串行消费循环）
        _pending: correlation 登记表（message_id → (Future, timeout_seconds)——Task 3 兑现）
        _closed: 关闭标志（校验次序首位）
        _closed_event: 关闭唤醒事件（无挂起条目等待者收 461 的唤醒通道——close 时 set）
    """

    def __init__(self, blackboard: PublicBlackboard, guard: IsolationGuardPort) -> None:
        """初始化进程内总线

        Args:
            blackboard: 公共黑板端口（经组合根 resolve 注入——不直连 Redis）
            guard: 隔离守卫端口（经组合根 resolve 注入）
        """
        self._blackboard = blackboard
        self._guard = guard
        self._closed = False
        # 关闭唤醒事件（无挂起条目的等待者收 461 的唤醒通道——Python 3.10+ Event
        # 构造零 loop 绑定，BDD 同步 given 手工构造安全）
        self._closed_event = asyncio.Event()
        self._handlers: dict[str, Callable[[SAPMessage], Awaitable[None] | None]] = {}
        self._queues: dict[str, asyncio.PriorityQueue[tuple[int, int, SAPMessage]]] = {}
        self._seq_counters: dict[str, int] = {}
        self._consumer_tasks: dict[str, asyncio.Task[None]] = {}
        self._pending: dict[uuid.UUID, tuple[asyncio.Future[SAPMessage], float]] = {}

    async def send(self, message: SAPMessage) -> None:
        """发送消息（校验 → 黑板桥 → 入队——先黑板后入队次序钦定）

        零挂起确定性前提：blackboard_visible=False 时校验+入队同步完成（put_nowait
        无让渡）——优先级序断言成立的确定性基础（v1.3.0 注记）。

        close 竞态放弃语义（R1-F1）：blackboard_visible=True 的消息在黑板桥 await
        挂起期间总线被 close 时，本调用静默放弃（不投递不登记不报错）；已写入
        黑板的内容保留（持久面诚实）。调用方对「消息被放弃」零显式感知通道——
        需确定性投递语义的调用方应避免 close 并发窗口（V1 契约知悉）。

        Args:
            message: SAP 消息

        Raises:
            SAPBusStateError: 461（校验面——reason 闭集五成员）
            IsolationOperationForbiddenError: 449 透传（黑板桥守卫拒绝——Task 4）
            SAPBlackboardWriteError: 462（黑板 post 返 0——Task 4）
        """
        self._validate(message)
        if message.blackboard_visible:
            await self._bridge_to_blackboard(message)
            # 跨 await 点状态复查（close 竞态窗口——R1-F1）：黑板桥挂起期间并发
            # close 完成时，本消息属 close「丢弃在途」语义面——放弃登记与投递
            # （非上抛早退路径：黑板若已写入则保留——持久面与进程内投递面在此
            # 分离，抛 461 反失真）；「close 后新 send」仍走 _validate 首位抛 461。
            if self._closed:
                return
        if message.requires_response:
            self._register_pending(message)
        if message.message_type is MessageType.RESPONSE and message.correlation_id is not None:
            # None 守卫（v1.3.0 钦定）：correlation_id=None 的裸 RESPONSE 直接跳过
            # resolve 查找（非 warning 路径——无关联回复不是迟到响应）
            self._resolve_pending(message)
        if message.message_type is MessageType.BROADCAST:
            # 接收方集合快照在入队分发时刻定格——send 完成后 subscribe 者不收到
            # （blackboard_visible=True 时快照实取黑板桥 await 完成后——时序上
            # 桥期间新订阅者会收到本广播，措辞以入队分发为准）
            for receiver_id in list(self._handlers):
                self._ensure_consumer(receiver_id)
                self._enqueue(receiver_id, message)
        else:
            self._ensure_consumer(message.receiver_id)
            self._enqueue(message.receiver_id, message)

    def subscribe(self, receiver_id: str, handler: Callable[[SAPMessage], Awaitable[None] | None]) -> None:
        """订阅消息（同步注册；重复 subscribe 覆盖——dict 语义一致；自收合法）

        Args:
            receiver_id: 接收方标识（str(agent_id) UUID 形态——OD-5；"broadcast" 约定值不可订阅）
            handler: 消息处理器（async 形态协程 await 后再出队下一条——串行保序）

        Raises:
            SAPBusStateError: 461——非 UUID 标识（防「永远无法合法收到消息」的死订阅）/总线已关闭
        """
        if self._closed:
            raise SAPBusStateError(reason="bus_closed", message="SAP 总线已关闭")
        try:
            uuid.UUID(receiver_id)
        except ValueError:
            raise SAPBusStateError(
                reason="invalid_receiver_id",
                message=f"订阅标识非 UUID 形态: {receiver_id!r}",
                context_extra={"receiver_id": receiver_id},
            ) from None
        self._handlers[receiver_id] = handler
        if receiver_id not in self._queues:
            self._queues[receiver_id] = asyncio.PriorityQueue()
            self._seq_counters[receiver_id] = 0
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop is not None:
                self._consumer_tasks[receiver_id] = running_loop.create_task(self._consume(receiver_id))
            # 无 running loop（同步注册场景——如 BDD given 步骤/应用启动期）：
            # 消费任务惰性启动，首次 send（async 上下文）时经 _ensure_consumer 补建

    def _ensure_consumer(self, receiver_id: str) -> None:
        """确保接收方消费任务已启动（subscribe 无 running loop 时的惰性启动补建）

        Args:
            receiver_id: 接收方标识
        """
        if receiver_id in self._queues and receiver_id not in self._consumer_tasks:
            self._consumer_tasks[receiver_id] = asyncio.get_running_loop().create_task(self._consume(receiver_id))

    async def wait_for_response(self, correlation_id: uuid.UUID, timeout_seconds: float | None = None) -> SAPMessage:
        """等待关联响应（correlation_id 锚 = REQUEST.message_id——OD-9 锚约定）

        计时锚点：timeout 从本方法调用时刻起算（asyncio.wait_for duration 语义——
        非 send 时刻 deadline 语义）；超时抛出前取消底层等待任务（shield 保护登记
        Future 不被 wait_for 取消——条目生命周期钦定「保留至超时/close」）。

        默认值口径：timeout_seconds=None 时取登记条目承载的请求消息 timeout_seconds
        （send 时登记——300 默认经 SAPMessage 字段语义承载）；无登记条目时取
        SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS 兜底。无条目路径与有条目超时同路径
        （等满 timeout 抛 460——不 special-case）；期间 close 发生则经 _closed_event
        唤醒收 461（与有条目在途等待者结局统一——R1-F3）。

        Args:
            correlation_id: 关联锚（OD-9——REQUEST.message_id）
            timeout_seconds: 超时秒数（None 取登记条目/兜底常量）

        Returns:
            关联的 RESPONSE 消息

        Raises:
            SAPTimeoutError: 460——等满超时无 resolve（超时后条目清理；迟到响应零崩溃零 resolve）
            SAPBusStateError: 461——总线已关闭
        """
        if self._closed:
            raise SAPBusStateError(reason="bus_closed", message="SAP 总线已关闭")
        entry = self._pending.get(correlation_id)
        if timeout_seconds is None:
            timeout_seconds = entry[1] if entry is not None else SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS
        timeout_occurred = False
        response: SAPMessage | None = None
        if entry is not None:
            try:
                response = await asyncio.wait_for(asyncio.shield(entry[0]), timeout_seconds)
            except TimeoutError:
                timeout_occurred = True
        else:
            # 无挂起条目：等满超时（460）或 close 唤醒（461）——两路径结局统一
            # （R1-F3：裸 sleep 无法被 close 唤醒，同一次 close 下无条目等待者
            # 与有条目等待者结局分裂；显式 raise 禁落穿下方生产 assert——
            # python -O 剥离 assert 后落穿将静默返回 None 破坏类型契约）
            try:
                await asyncio.wait_for(self._closed_event.wait(), timeout_seconds)
            except TimeoutError:
                timeout_occurred = True
            else:
                raise SAPBusStateError(reason="bus_closed", message="SAP 总线已关闭——在途等待者收 461") from None
        if timeout_occurred:
            # 等待路径条目清理：迟到响应不再 resolve（已清理 Future 防御面——log warning）
            self._pending.pop(correlation_id, None)
            raise SAPTimeoutError(
                correlation_id=str(correlation_id),
                timeout_seconds=timeout_seconds,
            ) from None
        assert response is not None
        return response

    async def close(self) -> None:
        """关闭总线（幂等）——动作清单五件

        ① 取消全部消费任务（CancelledError 属 BaseException——消费循环的
        except Exception 不吞取消信号，放行传播）② 清空 per-receiver 队列
        ③ 挂起 correlation Future → 461 bus_closed（仅未 done 条目——future.done()
        守卫防 InvalidStateError；set_exception 后同步消化 retrieved 标记——无等待者
        条目不产 never-retrieved 噪音）④ 清空登记表（二次 close 空表幂等）⑤ 登记
        表内条目的在途等待者收 461 非 CancelledError + 无挂起条目的等待者经
        _closed_event 唤醒收 461（R1-F3 两路径结局统一），与「close 后新调用 →
        461」结局统一（边界知悉：同 correlation 多等待者中先超时者已清理条目时，
        其余等待者不被本清单触达——各自等满收 460，单请求单等待者惯例下不可达）。

        消息丢弃语义：在途与滞留消息丢弃，无 redelivery（V1 非持久）；黑板桥
        await 挂起期间 close 的在途 send 恢复后同样放弃投递（send 侧复查——已写
        入黑板的内容保留，持久面诚实）。
        """
        if self._closed:
            return
        self._closed = True
        self._closed_event.set()
        for task in self._consumer_tasks.values():
            task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks.values(), return_exceptions=True)
        for queue in self._queues.values():
            while not queue.empty():
                queue.get_nowait()
        for future, _timeout in self._pending.values():
            if not future.done():
                future.set_exception(SAPBusStateError(reason="bus_closed", message="SAP 总线已关闭——在途等待者收 461"))
                # 消化 retrieved 标记（R1-F2）：无等待者条目的 461 不产 asyncio
                # ERROR 级 "Future exception was never retrieved" 噪音（exception()
                # 仅置已读标记不清结果——有等待者的 await 仍拿到异常，零语义变化）
                future.exception()
        self._pending.clear()

    def _validate(self, message: SAPMessage) -> None:
        """协议校验面（次序钦定：开闭态首位 → UUID 双侧 → BROADCAST 组合 → 注册检查）

        Args:
            message: 待发送消息

        Raises:
            SAPBusStateError: 461——reason 闭集 {receiver_not_registered, invalid_sender_id,
                invalid_receiver_id, broadcast_convention_violation, bus_closed}
        """
        if self._closed:
            raise SAPBusStateError(reason="bus_closed", message="SAP 总线已关闭")
        try:
            uuid.UUID(message.sender_id)
        except ValueError:
            raise SAPBusStateError(
                reason="invalid_sender_id",
                message=f"SAP 消息 sender_id 非 UUID 形态: {message.sender_id!r}",
                context_extra={"sender_id": message.sender_id},
            ) from None
        is_broadcast_receiver = message.receiver_id == BROADCAST_RECEIVER_ID
        if not is_broadcast_receiver:
            try:
                uuid.UUID(message.receiver_id)
            except ValueError:
                raise SAPBusStateError(
                    reason="invalid_receiver_id",
                    message=f"SAP 消息 receiver_id 非 UUID 且非 broadcast 约定值: {message.receiver_id!r}",
                    context_extra={"receiver_id": message.receiver_id},
                ) from None
        if is_broadcast_receiver is not (message.message_type is MessageType.BROADCAST):
            raise SAPBusStateError(
                reason="broadcast_convention_violation",
                message="BROADCAST 类型与 receiver_id='broadcast' 约定值必须双向锁定（OD-8）",
                context_extra={"message_type": message.message_type.value},
            )
        if not is_broadcast_receiver and message.receiver_id not in self._handlers:
            raise SAPBusStateError(
                reason="receiver_not_registered",
                message=f"单播目标接收方未注册: {message.receiver_id!r}",
                context_extra={"receiver_id": message.receiver_id},
            )

    def _enqueue(self, receiver_id: str, message: SAPMessage) -> None:
        """入队（heapq 元组 rank+seq——同级 FIFO 破平局；put_nowait 零让渡）

        Args:
            receiver_id: 目标接收方标识
            message: SAP 消息
        """
        self._seq_counters[receiver_id] += 1
        self._queues[receiver_id].put_nowait((_PRIORITY_RANK[message.priority], self._seq_counters[receiver_id], message))

    async def _consume(self, receiver_id: str) -> None:
        """per-receiver 串行消费循环（deliver-continue 钦定——DC-11）

        单条 handler 崩溃不冻结该接收方队列（Actor supervision 隔离惯例）：
        捕获 handler 异常（同步 raise 与异步异常等效）→ log warning（含 message_id
        与异常摘要）→ 继续出队下一条。捕获边界 except Exception——CancelledError
        属 BaseException 放行传播（close 的 task.cancel() 落在 await handler 处时不被吞）。

        Args:
            receiver_id: 接收方标识
        """
        queue = self._queues[receiver_id]
        while True:
            _, _, message = await queue.get()
            handler = self._handlers.get(receiver_id)
            if handler is None:
                continue
            try:
                result = handler(message)
                if inspect.isawaitable(result):
                    await result
            except Exception as error:
                logger.warning(
                    "SAP 消息 handler 处理异常（deliver-continue）: receiver_id=%s message_id=%s error=%s",
                    receiver_id,
                    message.message_id,
                    error,
                )

    async def _bridge_to_blackboard(self, message: SAPMessage) -> None:
        """黑板桥（守卫 → post → fail-loud 检测——次序钦定：先黑板后入队由 send 调用位置承载）

        守卫参数锚：actor=uuid(sender_id)、target=uuid(receiver_id)（BROADCAST 形态
        target=actor 自身——广播无特定目标）；判定语义单边取 actor 侧隔离状态——消息的
        isolation_level 字段是显示性标识（发送时快照）不是判定输入。守卫拒绝
        （449/448/443/447）原样上抛（透传不包装——黑板桥无异常翻译职责，5-5 分码
        语义完整保留）+ 消息不投递（发送原子性）。

        content 四键最小投影（枚举显式 .value 字符串化——断言确定性：读回比较是纯
        str 域）；post 返回 version==0 → SAPBlackboardWriteError（fail-loud OD-7：
        RedisPublicBlackboard 吞 ConnectionError/TimeoutError 返 0 的既有语义检测点）。

        Args:
            message: blackboard_visible=True 的消息

        Raises:
            IsolationOperationForbiddenError: 449 等守卫拒绝族（原样透传）
            SAPBlackboardWriteError: 462（post 返 0）
        """
        actor = uuid.UUID(message.sender_id)
        target = actor if message.receiver_id == BROADCAST_RECEIVER_ID else uuid.UUID(message.receiver_id)
        await self._guard.ensure_agent_access(
            actor_agent_id=actor,
            target_agent_id=target,
            resource=IsolationResource.BLACKBOARD,
            operation=AccessOperation.WRITE,
        )
        version = await self._blackboard.post(
            conversation_id=str(message.conversation_id),
            agent_id=message.sender_id,
            content={
                "message_id": str(message.message_id),
                "message_type": message.message_type.value,
                "content": message.content,
                "priority": message.priority.value,
            },
            confidence=1.0,
        )
        if version == 0:
            raise SAPBlackboardWriteError(
                conversation_id=str(message.conversation_id),
                message="SAP 黑板桥 post 返回 0（公共黑板写失败——fail-loud，OD-7）",
            )

    def _register_pending(self, message: SAPMessage) -> None:
        """correlation 登记表写入（requires_response=True 消息 send 时预建 Future + 元数据）

        登记表与挂起 Future 表同构复用（send 预建 Future + timeout 元数据，wait 只
        await）；条目生命周期钦定（DC-11）：保留至超时清理或 close——resolve 不移除
        条目（「resolve 即移除」会使 resolve 之后才调 wait 的等待者落入无条目路径
        等满伪超时）。

        Args:
            message: 待登记的请求消息（message_id 作 correlation 键）
        """
        if message.message_id in self._pending:
            return
        future: asyncio.Future[SAPMessage] = asyncio.get_running_loop().create_future()
        self._pending[message.message_id] = (future, float(message.timeout_seconds))

    def _resolve_pending(self, message: SAPMessage) -> None:
        """RESPONSE 到达时的关联 resolve（DC-10 双动作：入队送达 + resolve 正交）

        幂等 resolve 守卫（future.done 检查——JMS 重复投递幂等惯例）：正常双响应
        第二条 log-ignore 零 InvalidStateError；条目不存在（未挂起或已超时清理）
        时静默跳过——迟到响应不是错误（Future 已清理防御面）。

        Args:
            message: RESPONSE 消息（correlation_id 非空——调用点 None 守卫已过）
        """
        assert message.correlation_id is not None
        entry = self._pending.get(message.correlation_id)
        if entry is None:
            return
        future = entry[0]
        if future.done():
            logger.warning(
                "SAP 重复 RESPONSE 幂等忽略（log-ignore）: correlation_id=%s message_id=%s",
                message.correlation_id,
                message.message_id,
            )
            return
        future.set_result(message)


__all__ = [
    "BROADCAST_RECEIVER_ID",
    "InProcessSAPBus",
    "SAP_DEFAULT_RESPONSE_TIMEOUT_SECONDS",
    "SAPBus",
    "deserialize",
    "serialize",
]
