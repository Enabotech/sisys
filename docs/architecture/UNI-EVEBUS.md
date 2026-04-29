# 统一双通道事件总线架构设计

## 1. 背景与目标

### 1.1 现状分析

| 通道 | 实现 | 完整度 | 问题 |
|------|------|--------|------|
| Redis Pub/Sub | `RedisEventPublisher` + `RedisEventSubscriber` | 8.5/10 | 仅单通道，无统一抽象 |
| RabbitMQ + Outbox | `RabbitMQPublisher` + `InMemoryOutboxRepository` | 7.0/10 | Outbox 未集成到 EventBus；PostgreSQL Outbox 有接口-实现不匹配 |

**核心问题：**
- EventBus 接口未定义，InMemoryEventBus 无法作为统一抽象
- 缺乏 DeliveryMode 机制，事件无法声明其传输通道
- RabbitMQ 路径未通过 Outbox，Story 1.3 AC-1 未满足
- 订阅端仅支持 Redis，未实现 Story 20.2 的死信队列

### 1.2 设计目标

1. **统一抽象**：EventBus 接口定义发布/订阅语义，屏蔽底层传输差异
2. **双通道路由**：基于事件类型自动路由到 Redis（实时）/ RabbitMQ（可靠）
3. **Outbox 集成**：可靠通道通过 Outbox 保证，最终一致性
4. **Scheme B**：EventBus 作为门面，内部协调 Outbox 和 Publisher（对标 NServiceBus/Axon Framework）
5. **Story 1.3 约束满足**：Redis 仅用于实时通知，可靠传输必须经 Outbox → RabbitMQ

---

## 2. 目标架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Application Layer                            │
│                    (Domain Services / Use Cases)                     │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ DomainEvent
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Interfaces Layer                             │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                      EventBus (Port)                             │ │
│  │  + publish(event, delivery_mode?) -> PublishResult              │ │
│  │  + subscribe(event_type, handler) -> None                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ RedisEventBus   │    │  RabbitMQEventBus   │    │  DualChannelEventBus │
│ (REALTIME_ONLY) │    │   (RELIABLE_ONLY)   │    │      (BOTH)          │
└────────┬────────┘    └──────────┬──────────┘    └─────────────────────┘
         │                         │
         │                         │ Outbox.save(event)
         │                         ▼
         │              ┌─────────────────────┐
         │              │  OutboxRepository   │
         │              │  (InMemory/Postgres)│
         │              └──────────┬──────────┘
         │                         │ Poller reads
         │                         ▼
         │              ┌─────────────────────┐
         │              │ AsyncOutboxPoller   │
         │              │ (Background Task)    │
         │              └──────────┬──────────┘
         │                         │ publish
         │                         ▼
         │              ┌─────────────────────┐
         └─────────────►│  RabbitMQPublisher  │◄──────┐
                        └─────────────────────┘       │
                         Infrastructure Layer        │
                         (External Systems)           │
                                                       │
                                                       ▼
                                            ┌─────────────────────┐
                                            │  RabbitMQ Broker    │
                                            └─────────────────────┘
```

---

## 3. 核心类型设计

### 3.1 DeliveryMode 枚举

```python
# src/infrastructure/messaging/delivery_mode.py

from enum import Enum


class DeliveryMode(Enum):
    """事件投递模式。"""

    REALTIME_ONLY = "realtime"  # 仅发 Redis Pub/Sub（尽力而为）
    RELIABLE_ONLY = "reliable"  # 仅发 RabbitMQ + Outbox（可靠传输）
    BOTH = "both"  # 双通道都发
```

### 3.2 PublishResult 数据类

```python
# src/infrastructure/messaging/publish_result.py

from dataclasses import dataclass
from typing import Self

from .delivery_mode import DeliveryMode


@dataclass(frozen=True)
class PublishResult:
    """发布结果。"""

    event_id: str
    redis_success: bool = False
    redis_error: str | None = None
    rabbitmq_success: bool = False
    rabbitmq_error: str | None = None
    outbox_saved: bool = False  # RabbitMQ 路径是否成功写入 Outbox

    @property
    def is_full_success(self) -> bool:
        """所有尝试的通道都成功。"""
        # RELIABLE_ONLY: outbox_saved 为成功标志
        if not self.redis_success and not self.rabbitmq_success:
            return self.outbox_saved
        return self.redis_success and self.outbox_saved

    @property
    def is_partial_success(self) -> bool:
        """部分成功。"""
        if self.redis_success and self.outbox_saved:
            return False
        if self.redis_success or self.outbox_saved:
            return True
        return False

    @property
    def is_full_failure(self) -> bool:
        """全部失败。"""
        return not self.redis_success and not self.outbox_saved
```

### 3.3 EventChannelRegistry

```python
# src/infrastructure/messaging/event_channel_registry.py

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .delivery_mode import DeliveryMode


class EventChannel(Enum):
    """预定义事件通道。"""

    RT = "rt"  # Redis 实时通道 prefix
    DOMAIN = "domain"  # Redis 领域事件通道
    RELIABLE = "sisys.events.reliable"  # RabbitMQ 可靠交换器
    AUDIT = "audit"  # RabbitMQ 审计交换器


@dataclass
class EventChannelMapping:
    """事件通道映射配置。"""

    event_type: str
    redis_channel: str | None = None  # e.g., "rt:DocumentProcessed"
    rabbitmq_routing_key: str | None = None  # e.g., "sisys.events.reliable.document_processed"
    default_delivery_mode: DeliveryMode = DeliveryMode.BOTH
    description: str = ""


class EventChannelRegistry:
    """事件通道注册表。

    管理事件类型到通道的映射配置。
    支持 YAML 配置加载和运行时覆盖。
    """

    def __init__(self) -> None:
        self._mappings: dict[str, EventChannelMapping] = {}
        self._overrides: dict[str, DeliveryMode] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """初始化默认通道映射（来自 Story 1.3 约束）。"""

        # 实时通知型：仅 Redis
        for event_type in ["AutoTriggered", "AutoRouted"]:
            self.register(EventChannelMapping(
                event_type=event_type,
                redis_channel=f"rt:{event_type}",
                default_delivery_mode=DeliveryMode.REALTIME_ONLY,
                description=f"{event_type} - 实时通知"
            ))

        # 可靠传输型：仅 RabbitMQ + Outbox
        for event_type in ["MemoryChanged", "CheckpointReached"]:
            self.register(EventChannelMapping(
                event_type=event_type,
                rabbitmq_routing_key=f"sisys.events.reliable.{self._to_snake_case(event_type)}",
                default_delivery_mode=DeliveryMode.RELIABLE_ONLY,
                description=f"{event_type} - 可靠持久化"
            ))

        # 双通道型：Redis + RabbitMQ
        for event_type in ["DocumentProcessed", "ToolExecuted", "AgentDecided"]:
            self.register(EventChannelMapping(
                event_type=event_type,
                redis_channel=f"rt:{event_type}",
                rabbitmq_routing_key=f"sisys.events.reliable.{self._to_snake_case(event_type)}",
                default_delivery_mode=DeliveryMode.BOTH,
                description=f"{event_type} - 双通道"
            ))

        # 审计型：仅 RabbitMQ（WORM）
        self.register(EventChannelMapping(
            event_type="AuditEvent",
            rabbitmq_routing_key="audit.audit_event",
            default_delivery_mode=DeliveryMode.RELIABLE_ONLY,
            description="审计事件 - 7年 WORM 存储"
        ))

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """驼峰转蛇形。"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()

    def register(self, mapping: EventChannelMapping) -> None:
        """注册事件通道映射。"""
        self._mappings[mapping.event_type] = mapping

    def get(self, event_type: str) -> EventChannelMapping | None:
        """获取事件通道映射。"""
        return self._mappings.get(event_type)

    def get_delivery_mode(self, event_type: str) -> DeliveryMode:
        """获取事件投递模式（支持运行时覆盖）。"""
        if event_type in self._overrides:
            return self._overrides[event_type]
        mapping = self._mappings.get(event_type)
        return mapping.default_delivery_mode if mapping else DeliveryMode.BOTH

    def set_delivery_mode_override(self, event_type: str, mode: DeliveryMode) -> None:
        """运行时覆盖投递模式。"""
        self._overrides[event_type] = mode

    def get_redis_channel(self, event_type: str) -> str | None:
        """获取 Redis 通道名。"""
        mapping = self._mappings.get(event_type)
        if mapping:
            if mapping.default_delivery_mode == DeliveryMode.RELIABLE_ONLY:
                return None  # RELIABLE_ONLY 不使用 Redis
            return mapping.redis_channel
        return f"rt:{event_type}"  # 默认回退

    def get_rabbitmq_routing_key(self, event_type: str) -> str | None:
        """获取 RabbitMQ 路由键。"""
        mapping = self._mappings.get(event_type)
        if mapping:
            return mapping.rabbitmq_routing_key
        return f"sisys.events.reliable.{self._to_snake_case(event_type)}"

    @classmethod
    def create_for_testing(cls) -> EventChannelRegistry:
        """创建测试用注册表（空映射）。"""
        instance = object.__new__(cls)
        instance._mappings = {}
        instance._overrides = {}
        return instance
```

---

## 4. 接口设计

### 4.1 EventBus 端口接口

```python
class EventBus(ABC):
    """事件总线端口（六边形架构适配端口）。

    应用层仅依赖此接口，不关心底层传输实现。
    """

    @abstractmethod
    async def publish(self, event: DomainEvent, delivery_mode: DeliveryMode | None = None) -> PublishResult:
        """发布领域事件。

        Args:
            event: 领域事件实例
            delivery_mode: 传输模式，默认按事件类型推断

        Returns:
            PublishResult: 包含各通道发布状态的不可变结果
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅领域事件。

        Args:
            event_type: 事件类型（支持 glob 模式如 "user.*"）
            handler: 同步事件处理器
        """
        pass

    @abstractmethod
    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[Any]],
    ) -> None:
        """异步订阅领域事件。

        Args:
            event_type: 事件类型
            handler: 异步事件处理器
        """
        pass
```

---

## 5. 通道实现

### 5.1 RedisEventBus（REALTIME_ONLY 路径）

```python
class RedisEventBus(EventBus):
    """Redis Pub/Sub 事件总线（实时通道）。

    发布时直接推送到 Redis 通道，允许消息丢失。
    订阅时通过 RedisEventSubscriber 接收。
    """

    def __init__(self, publisher: RedisEventPublisher, subscriber: RedisEventSubscriber) -> None:
        self._publisher = publisher
        self._subscriber = subscriber
        self._handlers: dict[str, list[Callable[[DomainEvent], Any]]] = {}

    async def publish(self, event: DomainEvent, delivery_mode: DeliveryMode | None = None) -> PublishResult:
        # 强制 REALTIME_ONLY
        try:
            await self._publisher.publish(event)
            return PublishResult(event_id=str(event.event_id), redis_success=True)
        except Exception as e:
            return PublishResult(event_id=str(event.event_id), redis_error=str(e))

    async def subscribe(self, event_type: str, handler: Callable[[DomainEvent], Any]) -> None:
        channel = f"rt:{event_type}"

        def wrapped_handler(data: dict) -> None:
            domain_event = self._deserialize(data)
            handler(domain_event)

        self._subscriber.subscribe(channel, wrapped_handler)
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def subscribe_async(self, event_type: str, handler: Callable[[DomainEvent], Awaitable[Any]]) -> None:
        # ... 异步版本实现
```

### 5.2 RabbitMQEventBus（RELIABLE_ONLY 路径）

```python
class RabbitMQEventBus(EventBus):
    """RabbitMQ + Outbox 事件总线（可靠通道）。

    发布时写入 Outbox，由后台 Poller 消费并发布到 RabbitMQ。
    对标 NServiceBus 的 "可靠发送" 模式。
    """

    def __init__(
        self,
        outbox_repository: OutboxRepository,
        publisher: RabbitMQPublisher,
        outbox_poller: AsyncOutboxPoller,
    ) -> None:
        self._outbox = outbox_repository
        self._publisher = publisher
        self._poller = outbox_poller

    async def publish(self, event: DomainEvent, delivery_mode: DeliveryMode | None = None) -> PublishResult:
        # 强制 RELIABLE_ONLY：写入 Outbox
        try:
            self._outbox.save(event)
            return PublishResult(
                event_id=str(event.event_id),
                outbox_saved=True,
                rabbitmq_success=False,  # Poller 异步发布
            )
        except Exception as e:
            return PublishResult(event_id=str(event.event_id), rabbitmq_error=str(e))

    async def subscribe(self, event_type: str, handler: Callable[[DomainEvent], Any]) -> None:
        # 订阅 RabbitMQ 队列
        await self._consumer.subscribe(event_type, handler)

    async def subscribe_async(self, event_type: str, handler: Callable[[DomainEvent], Awaitable[Any]]) -> None:
        # 异步订阅实现
```

### 5.3 DualChannelEventBus（主统一门面）

```python
class DualChannelEventBus(EventBus):
    """双通道统一事件总线门面（主入口）。

    对标 NServiceBus 的 Bus.Send/Publish 语义：
    - 根据 DeliveryMode 路由到对应通道
    - BOTH 模式：先 Redis（异步），再 Outbox（可靠）
    - 内部协调 RedisEventBus 和 RabbitMQEventBus
    """

    def __init__(
        self,
        redis_bus: RedisEventBus,
        rabbitmq_bus: RabbitMQEventBus,
        registry: EventChannelRegistry,
    ) -> None:
        self._redis_bus = redis_bus
        self._rabbitmq_bus = rabbitmq_bus
        self._registry = registry

    async def publish(self, event: DomainEvent, delivery_mode: DeliveryMode | None = None) -> PublishResult:
        # 推断 DeliveryMode
        mode = delivery_mode or self._registry.get_delivery_mode(event.event_type)

        if mode == DeliveryMode.REALTIME_ONLY:
            return await self._redis_bus.publish(event)

        if mode == DeliveryMode.RELIABLE_ONLY:
            return await self._rabbitmq_bus.publish(event)

        # BOTH: 并发双通道
        redis_result, rabbitmq_result = await asyncio.gather(
            self._redis_bus.publish(event),
            self._rabbitmq_bus.publish(event),
            return_exceptions=True,
        )

        # 合并结果
        redis_ok = not isinstance(redis_result, Exception)
        rabbitmq_ok = not isinstance(rabbitmq_result, Exception)

        return PublishResult(
            event_id=str(event.event_id),
            redis_success=redis_ok,
            redis_error=str(redis_result) if not redis_ok else None,
            rabbitmq_success=rabbitmq_ok,
            rabbitmq_error=str(rabbitmq_result) if not rabbitmq_ok else None,
            outbox_saved=rabbitmq_ok,
        )

    async def subscribe(self, event_type: str, handler: Callable[[DomainEvent], Any]) -> None:
        mode = self._registry.get_delivery_mode(event_type)
        if mode == DeliveryMode.REALTIME_ONLY:
            await self._redis_bus.subscribe(event_type, handler)
        elif mode == DeliveryMode.RELIABLE_ONLY:
            await self._rabbitmq_bus.subscribe(event_type, handler)
        else:  # BOTH: 双通道都订阅
            await asyncio.gather(
                self._redis_bus.subscribe(event_type, handler),
                self._rabbitmq_bus.subscribe(event_type, handler),
            )
```

---

## 6. 消费端设计

### 6.1 订阅端架构（Story 20.2）

```
RabbitMQ Broker ──► RabbitMQEventListener
                           │
                           ├──► DualIdempotencyChecker
                           │           │
                           │           ├──► RedisRetryQueue ──► Handler
                           │           │
                           │           └──► PostgresDeadLetterQueue
                           │
                           └──► EventHandler
```

### 6.2 RabbitMQEventListener

```python
class RabbitMQEventListener:
    """RabbitMQ 事件监听器（Story 20.2 实现）。

    特性：
    - 幂等性检查（DualIdempotencyChecker）
    - 重试队列（RedisRetryQueue）
    - 死信队列（PostgresDeadLetterQueue）
    - 优雅关闭
    """

    def __init__(
        self,
        connection: aio_pika.Connection,
        queue_name: str,
        idempotency_checker: DualIdempotencyChecker,
        retry_queue: RedisRetryQueue,
        dead_letter_queue: PostgresDeadLetterQueue,
        prefetch_count: int = 10,
    ) -> None:
        self._connection = connection
        self._queue_name = queue_name
        self._idempotency = idempotency_checker
        self._retry_queue = retry_queue
        self._dlq = dead_letter_queue
        self._prefetch_count = prefetch_count
        self._handlers: dict[str, Callable[[DomainEvent], Any]] = {}
        self._running = False

    async def start(self) -> None:
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=self._prefetch_count)
        queue = await channel.declare_queue(self._queue_name, durable=True)

        self._running = True
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._running:
                    break
                await self._process_message(message)

    async def _process_message(self, message: aio_pika.IncomingMessage) -> None:
        try:
            event_data = json_loads(message.body)
            event_id = event_data.get("event_id")
            event_type = event_data.get("event_type")

            # 幂等性检查
            if await self._idempotency.is_duplicate(event_id):
                await message.ack()
                return

            # 查找处理器
            handler = self._handlers.get(event_type)
            if not handler:
                logger.warning("No handler for event type: %s", event_type)
                await message.ack()
                return

            # 执行处理
            domain_event = self._deserialize(event_data)
            await handler(domain_event)

            await self._idempotency.mark_processed(event_id)
            await message.ack()

        except RetryableError as e:
            # 可重试错误：进入重试队列
            await self._retry_queue.enqueue(message, delay=30)
            await message.ack()

        except Exception as e:
            # 不可重试错误：进入死信队列
            logger.error("Non-retryable error processing message: %s", e)
            await self._dlq.enqueue(message, error=str(e))
            await message.ack()
```

---

## 7. 事件类注解扩展

### 7.1 DeliveryMode 注解

```python
# 在 src/domain/events/base.py 中扩展

class DeliveryMode(Enum):
    REALTIME_ONLY = "realtime"
    RELIABLE_ONLY = "reliable"
    BOTH = "both"

# 模块级注册表
_EVENT_DELIVERY_MODES: dict[str, DeliveryMode] = {}

def delivery_mode(mode: DeliveryMode) -> Callable:
    """事件类装饰器，声明默认传输模式。"""
    def decorator(cls: type[DomainEvent]) -> type[DomainEvent]:
        _EVENT_DELIVERY_MODES[cls.__name__] = mode
        return cls
    return decorator

# 使用示例
@delivery_mode(DeliveryMode.RELIABLE_ONLY)
class OrderCreatedEvent(DomainEvent):
    event_type = "order.created"
    # ...
```

---

## 8. 重构实现计划

### Phase 1：基础设施层（Week 1-2）

**目标**：完成 DeliveryMode、PublishResult、EventChannelRegistry 及各通道实现

| 文件 | 操作 | 依赖 |
|------|------|------|
| `src/domain/events/delivery_mode.py` | 新增 | 无 |
| `src/domain/events/publish_result.py` | 新增 | 无 |
| `src/domain/events/registry.py` | 新增 | DeliveryMode |
| `src/interfaces/eventbus.py` | 新增（接口） | DomainEvent, PublishResult |
| `src/infrastructure/messaging/redis_event_bus.py` | 新增 | RedisEventPublisher, EventBus |
| `src/infrastructure/messaging/rabbitmq_event_bus.py` | 新增 | OutboxRepository, RabbitMQPublisher, EventBus |
| `src/infrastructure/messaging/dual_channel_event_bus.py` | 新增 | RedisEventBus, RabbitMQEventBus, EventChannelRegistry |

**验收标准**：
- `DeliveryMode` 枚举覆盖三种模式
- `EventChannelRegistry` 支持按类型注册和查询
- `RedisEventBus.publish()` 返回 `PublishResult`
- `RabbitMQEventBus.publish()` 将事件写入 Outbox
- `DualChannelEventBus.publish()` 根据 mode 路由

### Phase 2：消费端完善（Week 2-3）

**目标**：完成 Story 20.2 消费端实现

| 文件 | 操作 | 依赖 |
|------|------|------|
| `src/infrastructure/messaging/rabbitmq_event_listener.py` | 新增 | aio_pika, DualIdempotencyChecker |
| `src/infrastructure/messaging/idempotency_checker.py` | 新增 | Redis |
| `src/infrastructure/messaging/dead_letter_queue.py` | 新增 | PostgreSQL |
| `src/infrastructure/messaging/retry_queue.py` | 新增 | Redis |

**验收标准**：
- `RabbitMQEventListener` 支持幂等检查
- 失败消息进入重试队列或死信队列
- 优雅关闭（处理中消息完成）

### Phase 3：应用层集成（Week 3-4）

**目标**：应用层切换到 EventBus 接口

| 文件 | 操作 | 依赖 |
|------|------|------|
| `src/application/services/*_service.py` | 修改 | EventBus |
| `src/infrastructure/di.py` | 修改 | EventBus 实现注入 |
| `tests/unit/test_*_service.py` | 新增 | EventBus mock |

**验收标准**：
- 所有 `DomainEvent` 通过 `EventBus.publish()` 发布
- 事件处理器通过 `EventBus.subscribe()` 注册
- 单元测试 100% 覆盖

### Phase 4：Story 1.5 PostgreSQL Outbox（Week 4-6）

**目标**：完成 PostgreSQL 持久化 Outbox

| 文件 | 操作 | 依赖 |
|------|------|------|
| `src/infrastructure/messaging/outbox/postgres_outbox.py` | 重写 | PostgreSQL |
| `tests/integration/test_outbox_persistence.py` | 新增 | PostgreSQL |

**验收标准**：
- `PostgreSQLOutboxRepository` 实现 `OutboxRepository` 接口
- 事务性写入（与业务操作同一事务）
- Poller 高可用（多实例竞争）

---

## 9. 文件变更清单

```
src/domain/events/
  + delivery_mode.py        # DeliveryMode 枚举
  + publish_result.py       # PublishResult 数据类
  + registry.py             # EventChannelRegistry

src/interfaces/
  + eventbus.py             # EventBus 抽象端口

src/infrastructure/messaging/
  + redis_event_bus.py      # RedisEventBus 实现
  + rabbitmq_event_bus.py   # RabbitMQEventBus 实现
  + dual_channel_event_bus.py  # DualChannelEventBus 主入口
  + rabbitmq_event_listener.py # Story 20.2 消费端
  + idempotency_checker.py  # 幂等性检查
  + dead_letter_queue.py    # 死信队列
  + retry_queue.py          # 重试队列
  ~ event_bus.py            # 重命名 InMemoryEventBus（保留开发用）
  ~ outbox/inmemory_outbox.py  # 确认实现

src/application/services/
  ~ *service.py             # 切换到 EventBus 接口

tests/unit/
  + test_delivery_mode.py
  + test_publish_result.py
  + test_event_channel_registry.py
  + test_redis_event_bus.py
  + test_rabbitmq_event_bus.py
  + test_dual_channel_event_bus.py

tests/integration/
  + test_event_bus_integration.py
  + test_outbox_persistence.py  # Story 1.5
```

---

## 10. 测试策略

### 10.1 单元测试

| 测试类 | 覆盖目标 |
|--------|----------|
| `test_delivery_mode` | 枚举值完整性 |
| `test_publish_result` | 结果合并逻辑、属性计算 |
| `test_event_channel_registry` | 注册/查询/默认推断 |
| `test_redis_event_bus` | REALTIME_ONLY 路径 |
| `test_rabbitmq_event_bus` | RELIABLE_ONLY 路径（mock Outbox） |
| `test_dual_channel_event_bus` | BOTH 路径、三种模式路由 |

### 10.2 集成测试

```python
# tests/integration/test_event_bus_integration.py

@pytest.fixture
def outbox_repo():
    # 使用真实 InMemoryOutboxRepository
    return InMemoryOutboxRepository()

@pytest.fixture
def dual_bus(outbox_repo):
    redis_pub = RedisEventPublisher(test_config)
    rabbitmq_pub = RabbitMQPublisher(test_config)
    poller = AsyncOutboxPoller(outbox_repo, rabbitmq_pub)

    redis_bus = RedisEventBus(redis_pub, RedisEventSubscriber(test_config))
    rabbitmq_bus = RabbitMQEventBus(outbox_repo, rabbitmq_pub, poller)
    registry = EventChannelRegistry()

    return DualChannelEventBus(redis_bus, rabbitmq_bus, registry)

async def test_reliable_only_saves_to_outbox(dual_bus):
    event = OrderCreatedEvent(order_id="123")
    result = await dual_bus.publish(event, DeliveryMode.RELIABLE_ONLY)

    assert result.outbox_saved
    assert not result.rabbitmq_success  # Poller 异步发布
```

---

## 11. Story 1.3 约束满足矩阵

| AC | 要求 | 实现方式 | 状态 |
|----|------|----------|------|
| AC-1 | Redis 仅用于实时通知，可靠传输必须走 Outbox → RabbitMQ | `RabbitMQEventBus.publish()` 调用 `Outbox.save()` | 待实现 |
| AC-2 | Redis 通道命名规范 `sisys:rt:{event_type}` | `EventChannelRegistry` 默认实现 | 待修改 |
| AC-3 | 双通道可独立使用 | `RedisEventBus` / `RabbitMQEventBus` 独立注入 | 待实现 |
| AC-4 | 事件可声明传输模式 | `DeliveryMode` 注解 + `EventChannelRegistry` | 待实现 |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Outbox Poller 延迟 | 可靠事件延迟增加 | 配置合理的轮询间隔（默认 1s） |
| 双通道一致性 | Redis 成功但 Outbox 失败 | BOTH 模式返回 partial_error，应用层决定 |
| Story 1.5 PostgreSQL 性能 | 高并发写入 Outbox | 批量读取 + 批量发布；连接池优化 |
| 幂等性检查性能 | Redis 延迟影响吞吐 | 使用 Redis SETNX 原子操作 + TTL |
