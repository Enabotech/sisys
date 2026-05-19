# SISYS 事件总线子系统详细设计

**文档版本:** v1.0
**生成时间:** 2026-05-19
**基于:** architecture.md v8.3.1 + sisys-event-bus-refactor-design.md v2.10 + sisys-event-bus-research-report.md v2.0 + 现有代码实现全面调研
**状态:** 重构已完成

---

## 1. 设计概述

### 1.1 双通道事件总线

SISYS 采用双通道事件总线架构，是整个系统的"血液"：

| 通道 | 技术 | 语义 | 延迟 | 可靠性 | 用途 |
|------|------|------|------|--------|------|
| **REALTIME** | Redis Pub/Sub | 尽力而为，允许丢失 | P95 < 50ms | 不持久化 | 心跳、自动触发等实时通知 |
| **RELIABLE** | PostgreSQL Outbox + RabbitMQ | 100%可靠传输，最终一致 | 秒级（Poller 间隔） | WORM 7年归档 | 审计、合规、业务状态变更 |

### 1.2 架构约束

- **六边形架构**: Domain 层仅 Python 标准库，Port 在 Domain/Application 层定义，Infrastructure 层仅提供实现
- **Protocol 优先**: 接口用 `typing.Protocol` + `@runtime_checkable`
- **async 一致性**: 所有异步操作的 Protocol 签名必须为 async
- **单一真实来源**: 每个概念只存在一处定义

### 1.3 核心设计原则

- **Domain 层零外部依赖**: `src/domain/events/` 和 `src/domain/ports/` 仅使用 Python 标准库
- **Outbox 模式**: RELIABLE 通道不直接发送到 RabbitMQ，先持久化到 Outbox（与业务同事务），再由 Poller 异步拉取发送
- **事件不可变**: 所有 DomainEvent 均为 `frozen=True` dataclass
- **多态反序列化**: 通过 `__init_subclass__` + `_registry` 实现事件类型到子类的自动映射

---

## 2. 架构总览图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Application Layer                                   │
│                                                                              │
│   UseCase / EventHandler ← inject EventPublisher Port                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ EventSubscriber (Protocol)   — "当X发生时我要做什么"                   │   │
│  │ async subscribe(event_type, handler)                                 │   │
│  │ async subscribe_async(event_type, handler)                           │   │
│  │ async start() / async close()                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ publish(event) / subscribe()
                                 v
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Domain Layer (零外部依赖)                             │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ DomainEvent   │  │ EventPublisher  │  │ OutboxRepository            │  │
│  │ (frozen       │  │ (Protocol)      │  │ (Protocol)                  │  │
│  │  dataclass)   │  │                 │  │                              │  │
│  │ + _registry   │  │ async publish() │  │ async save()                │  │
│  │ + to/from_dict│  │ → PublishResult │  │ async get_unpublished()     │  │
│  └───────────────┘  └─────────────────┘  │ async mark_published()      │  │
│  ┌───────────────┐  ┌─────────────────┐  │ async mark_failed()         │  │
│  │ PublishResult │  │ EventStore      │  │ async cleanup_old()         │  │
│  │ redis_success │  │ (Protocol)      │  └──────────────────────────────┘  │
│  │ outbox_saved  │  │ save/get_events │  ┌──────────────────────────────┐  │
│  └───────────────┘  └─────────────────┘  │ DeadLetterQueue (Protocol)  │  │
│  ┌───────────────┐  ┌─────────────────┐  │ async enqueue/dequeue       │  │
│  │ EventListener │  │ EventListener-  │  └──────────────────────────────┘  │
│  │ (sync Port)   │  │ Async (Port)    │                                    │
│  └───────────────┘  └─────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 v
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Infrastructure Layer                                   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              DualChannelEventBus (Facade)                            │   │
│  │       implements EventPublisher (Domain) + EventSubscriber (App)     │   │
│  └───────────┬────────────────────────────────────┬─────────────────────┘   │
│              │ ChannelRouter                       │                         │
│              │ get_delivery_mode(event_type)       │                         │
│              │ DEFAULT_MAPPINGS (19+ events)       │                         │
│              │ YAML config (event_channels.yaml)   │                         │
│              v                                     v                         │
│  ┌─────────────────────┐              ┌─────────────────────────────────┐   │
│  │   REALTIME 通道      │              │        RELIABLE 通道              │   │
│  │                     │              │                                 │   │
│  │  RedisEventBus      │              │  RabbitMQEventBus               │   │
│  │  ├── RedisPublisher │              │  └── OutboxRepository.save()    │   │
│  │  │   (连接池)        │              │       ↓ 同一PostgreSQL事务       │   │
│  │  └── RedisSubscriber│              │  ┌──────────────────────────┐  │   │
│  │      ├── subscribe  │              │  │ event_outbox 表           │  │   │
│  │      └── _listen_   │              │  │ status: pending →         │  │   │
│  │          loop       │              │  │   published / failed       │  │   │
│  │         ↓ handler   │              │  └────────────┬──────────────┘  │   │
│  │                     │              │               ↓                 │   │
│  └─────────────────────┘              │  AsyncOutboxPoller (1s 间隔)    │   │
│                                       │  ├── get_unpublished()          │   │
│                                       │  ├── RabbitMQPublisher          │   │
│                                       │  │   (aio_pika, durable topic) │   │
│                                       │  └── mark_published/failed()   │   │
│                                       └────────────┬────────────────────┘   │
│                                                    ↓                        │
│                                       ┌────────────────────────────────┐   │
│                                       │       RabbitMQ Broker          │   │
│                                       │  ┌──────────────────────────┐ │   │
│                                       │  │ RabbitMQConsumer         │ │   │
│                                       │  │ ├── IdempotencyChecker   │ │   │
│                                       │  │ │   (Redis SET NX)       │ │   │
│                                       │  │ ├── DualIdempotency-     │ │   │
│                                       │  │ │   Checker (Redis+PG)   │ │   │
│                                       │  │ ├── RedisRetryQueue      │ │   │
│                                       │  │ │   (ZSET Lua原子dequeue)│ │   │
│                                       │  │ └── DeadLetterQueue      │ │   │
│                                       │  └──────────────────────────┘ │   │
│                                       └────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  EventMetricsCollector          │  ErrorMapper                        │   │
│  │  (processed/failed/retried/     │  (Redis/RabbitMQ/S3错误             │   │
│  │   dlq/cache命中)                │   → 领域异常映射)                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  PostgreSQLEventStore (事件溯源)                                      │   │
│  │  append() / get_events() / get_events_by_type() (乐观锁)             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Domain 层

### 3.1 DomainEvent 基类

**文件:** `src/domain/events/base.py`

```python
@dataclass(frozen=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    schema_version: str = "1.0.0"          # DEFAULT_SCHEMA_VERSION
    aggregate_id: uuid.UUID | None = None
    aggregate_type: str = ""
    version: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: uuid.UUID | None = None  # AC-4 分布式链路追踪
    causation_id: uuid.UUID | None = None     # AC-4
    metadata: dict[str, Any] = field(default_factory=dict)
    _registry: ClassVar[dict[str, type[DomainEvent]]] = {}
```

**关键方法:**

| 方法 | 签名 | 职责 |
|------|------|------|
| `__init_subclass__` | `(cls, **kwargs)` | 自动注册子类到 `_registry`（绕过 `@dataclass` 时序问题） |
| `register` | `(cls, event_type, event_class)` | 手动注册（测试用） |
| `reset_registry` | `(cls)` | 清空注册表（测试隔离） |
| `to_dict` | `(self) -> dict` | 序列化：核心字段顶层 + 子类字段合并进 payload |
| `from_dict` | `(cls, data) -> DomainEvent` | 通过 `_registry` 多态反序列化 |
| `_serialize_value` | `(value) -> Any` | 递归处理 Enum/UUID/datetime/list/dict |
| `_deserialize_value` | `(cls, value, target_type) -> Any` | 处理 Optional/Union/UUID/datetime/Enum |

**设计要点:**
- `frozen=True` 保证事件不可变
- 子类须声明 `event_type: str = field(default="...", init=False)` 才能被自动注册
- `_CORE_FIELD_NAMES` 明确区分"顶层字段"与"payload 字段"
- `from_dict` 支持向后兼容字段名 `occurred_on`

### 3.2 PublishResult

**文件:** `src/domain/events/publish_result.py`

```python
@dataclass(frozen=True)
class PublishResult:
    event_id: str
    redis_success: bool = False
    redis_error: str | None = None
    outbox_saved: bool = False
    outbox_error: str | None = None

    @property
    def is_success -> bool        # 任一通道成功
    @property
    def is_full_failure -> bool   # 所有通道失败
    @property
    def partial_error -> str | None  # 第一个错误
```

**设计要点:**
- 双通道结果模型：`redis_success`（尽力而为）+ `outbox_saved`（可靠路径）
- `outbox_saved=True` 表示 RELIABLE 投递最终会成功（Poller 保证）

### 3.3 Domain Ports

#### 3.3.1 EventPublisher

**文件:** `src/domain/ports/event_publisher.py`

```python
@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> PublishResult: ...
```

#### 3.3.2 OutboxRepository

**文件:** `src/domain/ports/outbox.py`

```python
@runtime_checkable
class OutboxRepository(Protocol):
    async def save(self, event: DomainEvent) -> None: ...
    async def get_unpublished(self, limit: int) -> list[DomainEvent]: ...
    async def mark_published(self, event_id: UUID) -> None: ...
    async def mark_failed(self, event_id: UUID, error: str) -> None: ...
    async def cleanup_old_published_records(self, older_than_days: int = 30) -> int: ...
```

**设计要点:**
- "方案 A 彻底隔离"：接口完全使用 `DomainEvent`，不暴露 `OutboxEntity`
- 基础设施层负责 `DomainEvent` 与 `OutboxEntity` 的转换

### 3.4 Domain Event Protocols

#### 3.4.1 EventListener / EventListenerAsync

**文件:** `src/domain/events/listener.py`

```python
@runtime_checkable
class EventListener(Protocol):          # 同步
    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None: ...
    def dispatch(self, event: DomainEvent) -> None: ...

@runtime_checkable
class EventListenerAsync(Protocol):     # 异步
    async def async_handle(self, event: DomainEvent) -> None: ...
```

#### 3.4.2 DeadLetterQueue

**文件:** `src/domain/events/listener.py`

```python
@runtime_checkable
class DeadLetterQueue(Protocol):
    async def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None: ...
    async def dequeue(self) -> tuple[DomainEvent, str, int] | None: ...
```

#### 3.4.3 EventStore

**文件:** `src/domain/events/event_store.py`

```python
@runtime_checkable
class EventStore(Protocol):
    def save_events(self, events: list[DomainEvent]) -> None: ...
    def get_events(self, aggregate_id: UUID) -> list[DomainEvent]: ...
    def get_events_by_version(self, aggregate_id: UUID, from_version: int, to_version: int) -> list[DomainEvent]: ...
```

### 3.5 Application Ports

#### 3.5.1 EventSubscriber

**文件:** `src/application/ports/event_subscriber.py`

```python
@runtime_checkable
class EventSubscriber(Protocol):
    async def subscribe(self, event_type: str, handler: Callable[[DomainEvent], Any]) -> None: ...
    async def subscribe_async(self, event_type: str, handler: Callable[[DomainEvent], Awaitable[Any]]) -> None: ...
    async def start(self) -> None: ...
    async def close(self) -> None: ...
```

### 3.6 MVP 内存实现（Domain 层内）

| 类 | 文件 | 说明 |
|----|------|------|
| `InMemoryEventListener` | `listener.py` | `defaultdict(list)` + ExceptionGroup |
| `InMemoryDeadLetterQueue` | `listener.py` | `asyncio.Queue`，FIFO 出队 |

---

## 4. 领域事件清单

### 4.1 事件分类

| 类别 | 事件 | 通道 | 归档 |
|------|------|------|------|
| **实时通知** | HeartbeatTriggered, AutoTriggered, AutoRouted, AutoExecuted, RoutingDecided | Redis Pub/Sub | 不持久化 |
| **业务状态** | DocumentProcessed, ToolExecuted, AgentDecided, CheckpointReached, CheckpointRecovered, CorrectionApproved, IsolationLevelSwitched, StrategicDeviationWarning, MemoryChanged, SagaStatusChanged | RabbitMQ + Outbox | 7年存储 |
| **审计合规** | AuditEvent, MFAChallengeIssuedEvent, IntrusionDetectedEvent, DataIntegrityViolationEvent, SensitiveDataDetected, CrossBorderTransferRequested, DataSovereigntyViolation, PIPLDataAccessRequested | RabbitMQ + Outbox | WORM 7年 |

### 4.2 具体事件定义

| 事件 | 文件 | aggregate_type | 特有字段 |
|------|------|---------------|---------|
| DocumentProcessed | `document_events.py` | Document | document_id, parse_result, embedding |
| ToolExecuted | `tool_events.py` | Tool | tool_id, execution_result, cost_audit |
| AgentDecided | `agent_events.py` | Agent | agent_id, decision_result, confidence |
| CheckpointReached | `checkpoint_events.py` | Checkpoint | checkpoint_id, phase_identifier |
| CheckpointRecovered | `checkpoint_events.py` | Checkpoint | recovery_mode, modification_content, consistency_risk_level |
| CorrectionApproved | `correction_events.py` | Correction | correction_type, approval_chain |
| StrategicDeviationWarning | `planning_events.py` | StrategicPlan | deviation_type, deviation_level, threshold |
| HeartbeatTriggered | `heartbeat_events.py` | Heartbeat | wake_reason, todo_items, cost_budget |
| IsolationLevelSwitched | `isolation_events.py` | Agent | previous_level, target_level, switch_timestamp |
| RoutingDecided | `routing_events.py` | RoutingTask | l1_compliance_result, l2_factor_scores, route_type |
| AutoTriggered | `auto_trigger_events.py` | AutoTrigger | trigger_type, source_event_type |
| AutoRouted | `auto_route_events.py` | AutoRoute | route_type, route_target, route_score |
| AutoExecuted | `auto_execute_events.py` | AutoExecute | business_event_type, latency_ms |
| AuditEvent | `audit_events.py` | Audit | actor, action_type, target_resource, correction_level |
| MemoryChanged | `memory_events.py` | Memory | memory_id, change_type, is_automatic |
| SagaStatusChanged | `saga_events.py` | Saga | saga_type, old_status, new_status |
| MFAChallengeIssuedEvent | `compliance_events.py` | MFAChallenge | challenge_type, status |
| IntrusionDetectedEvent | `compliance_events.py` | IntrusionDetection | severity, action, attack_type |
| DataIntegrityViolationEvent | `compliance_events.py` | DataIntegrity | violation_type, affected_table |
| SensitiveDataDetected | `compliance_events.py` | DataSovereignty | sensitive_type, data_category |
| CrossBorderTransferRequested | `compliance_events.py` | CrossBorderTransfer | source_region, target_region |
| DataSovereigntyViolation | `compliance_events.py` | DataSovereignty | violation_type, data_origin |
| PIPLDataAccessRequested | `compliance_events.py` | PIPLCompliance | request_purpose, data_subject |

### 4.3 共享枚举

**文件:** `src/domain/events/enums.py`

| 枚举 | 值 | 使用事件 |
|------|-----|---------|
| `DeviationType` | BUDGET_OVERUN, TIMELINE_DELAY, SCOPE_CREEP, QUALITY_DROP, RESOURCE_SHORTAGE, STRATEGY_MISALIGN | StrategicDeviationWarning |
| `DeviationLevel` | MINOR, MODERATE, SEVERE | StrategicDeviationWarning |
| `CorrectionType` | L0, L1, L2, L3 | CorrectionApproved |
| `IsolationLevel` | L4_HARD, L3_SOFT, L2_COLLAB, L1_FUSED | IsolationLevelSwitched |
| `RecoveryMode` | REPLAY, OVERRIDE | CheckpointRecovered |
| `AuditActionType` | authentication/*, authorization/*, document/*, agent/*, checkpoint/*, correction/*, system/* | AuditEvent |

### 4.4 事件编排链路

```
用户操作 → DomainEvent
  ↓ AutoTriggerHandler
AutoTriggered (trigger_type, source_event_type)
  ↓ AutoRouteHandler
AutoRouted (route_type, route_target, route_score)
  ↓ AutoExecuteCompletedHandler
AutoExecuted → BusinessEvent (DocumentProcessed / ToolExecuted / AgentDecided)
```

每一步通过 `source_event_type`/`trigger_event_type` 追踪来源，支持完整的事件链路追溯。

---

## 5. Infrastructure 层 — 核心组件

### 5.1 DualChannelEventBus (Facade)

**文件:** `src/infrastructure/messaging/dual_channel_event_bus.py`

```python
class DualChannelEventBus(EventPublisher):
    def __init__(self, redis_bus: RedisEventBus, rabbitmq_bus: RabbitMQEventBus,
                 router: ChannelRouter) -> None

    async def publish(self, event: DomainEvent) -> PublishResult
    async def subscribe(self, event_type: str, handler) -> None
    async def subscribe_async(self, event_type: str, handler) -> None
    async def start(self) -> None     # 仅启动 Redis
    async def close(self) -> None     # 依次关闭两通道
```

**路由逻辑:**
- `router.get_delivery_mode()` 返回 REALTIME → 调用 `redis_bus.publish()`
- 返回 RELIABLE → 调用 `rabbitmq_bus.publish()`
- 订阅仅支持 REALTIME 模式，RELIABLE 模式调用抛 `ValueError`

### 5.2 ChannelRouter

**文件:** `src/infrastructure/messaging/channel_router.py`

```python
class DeliveryMode(Enum):
    REALTIME = "realtime"
    RELIABLE = "reliable"

@dataclass
class ChannelMapping:
    event_type: str
    redis_channel: str | None = None
    rabbitmq_routing_key: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.RELIABLE
    description: str = ""

class ChannelRouter:
    DEFAULT_MAPPINGS: dict[str, ChannelMapping]  # 19+ 预定义映射
    def get_delivery_mode(self, event_type: str) -> DeliveryMode
    def get_redis_channel(self, event_type: str) -> str | None
    def get_rabbitmq_routing_key(self, event_type: str) -> str | None
    def register(self, mapping: ChannelMapping) -> None       # Copy-on-Write
    def set_override(self, event_type: str, mode: DeliveryMode) -> None  # Copy-on-Write
```

**DEFAULT_MAPPINGS 通道分配:**
- REALTIME (5+): AutoTriggered, AutoRouted, AutoExecuted, HeartbeatTriggered, RoutingDecided
- RELIABLE (14+): DocumentProcessed, MemoryChanged, AuditEvent, ToolExecuted, AgentDecided, CheckpointReached, CheckpointRecovered, CorrectionApproved, StrategicDeviationWarning, IsolationLevelSwitched, 合规事件系列, SagaStatusChanged

**Redis 通道命名:** `sisys:rt:{snake_case_event_type}`
**RabbitMQ 路由键命名:** `sisys.events.reliable.{snake_case_event_type}`（AuditEvent 使用 `audit.audit_event`）

### 5.3 EventBusConfigLoader

**文件:** `src/infrastructure/messaging/event_bus_config_loader.py`

```python
class EventBusConfigLoader:
    @classmethod
    def create(cls) -> EventBusConfigLoader
    def load(self, router: ChannelRouter, config_path: str | Path) -> None
```

- YAML 配置作为 merge overlay 覆盖 DEFAULT_MAPPINGS
- 文件不存在时静默返回
- 配置文件: `config/event_channels.yaml`

---

## 6. Infrastructure 层 — REALTIME 通道

### 6.1 RedisEventBus

**文件:** `src/infrastructure/messaging/redis_event_bus.py`

```python
class RedisEventBus(EventPublisher, EventSubscriber):
    def __init__(self, publisher, subscriber, router: ChannelRouter) -> None
```

- 同时实现 `EventPublisher` 和 `EventSubscriber`
- 通过 `router.get_redis_channel()` 获取通道名
- 无 Redis 通道映射时返回 `PublishResult(redis_success=False)`

### 6.2 RedisEventPublisher

**文件:** `src/infrastructure/messaging/redis_publisher.py`

```python
class RedisEventPublisher:
    _NAMESPACE = "rt"
    def __init__(self, config: RedisConfig) -> None
    async def _get_pool(self) -> aioredis.ConnectionPool  # 懒加载 + asyncio.Lock
    async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult
    async def close(self) -> None
```

- 默认通道名: `rt:{event.event_type}`
- 捕获 `ConnectionError`/`TimeoutError`，返回 `PublishResult(redis_success=False)`
- 支持异步上下文管理器

### 6.3 RedisEventSubscriber

**文件:** `src/infrastructure/messaging/redis_subscriber.py`

```python
class RedisEventSubscriber:
    def __init__(self, config: RedisConfig) -> None
    def subscribe(self, channel, handler, error_handler=None) -> None
    async def start(self) -> None         # 创建后台 asyncio.Task
    async def _listen_loop(self) -> None   # async for message in pubsub
    def _dispatch_message(self, channel, data) -> None  # 同步分发
    async def close(self) -> None          # cancel + 5s 超时 + 取消订阅
```

- 按频道注册多个处理器: `dict[str, list[EventHandler]]`
- 同步分发处理器（非 async）
- 单个处理器异常不影响其他处理器

---

## 7. Infrastructure 层 — RELIABLE 通道

### 7.1 RabbitMQEventBus

**文件:** `src/infrastructure/messaging/rabbitmq_event_bus.py`

```python
class RabbitMQEventBus(EventPublisher):
    def __init__(self, outbox_repository, router: ChannelRouter) -> None
    async def publish(self, event: DomainEvent) -> PublishResult
```

- **Outbox 模式**: `publish()` 保存到 Outbox 仓储（与业务同事务），不直接发 RabbitMQ
- 通过 `router.get_rabbitmq_routing_key()` 获取路由键
- 无映射时返回失败结果

### 7.2 RabbitMQPublisher

**文件:** `src/infrastructure/messaging/rabbitmq_publisher.py`

```python
class RabbitMQPublisher:
    def __init__(self, config: RabbitMQConfig) -> None
    async def connect(self) -> None          # connect_robust + 声明 Topic 交换机
    async def async_publish(self, event, routing_key, retry_count=0) -> None
    async def close(self) -> None
```

- `aio_pika.connect_robust` 自动重连
- Topic 交换机 `sisys.events.reliable`，durable=True
- 消息持久化 (`DeliveryMode.PERSISTENT`)
- `x-retry-count` 消息头传递重试次数

### 7.3 RabbitMQConsumer

**文件:** `src/infrastructure/messaging/rabbitmq_consumer.py`

```python
class RabbitMQConsumer:
    def __init__(self, config, idempotency_checker=None, metrics_collector=None,
                 dlq=None, retry_queue=None, max_retries=3, retry_delay_seconds=30) -> None
    async def connect(self) -> None
    def register_handler(self, queue_name, handler) -> None
    async def async_consume(self, queue_name) -> AbstractQueue
    async def bind_queue(self, queue_name, routing_key, exchange_name) -> None
```

**处理流程:**
1. 反序列化消息 → DomainEvent
2. 幂等性检查 (`idempotency_checker.try_acquire()`)
3. 执行处理器
4. 成功 → ACK
5. 失败 → 三级降级:
   - RedisRetryQueue 延迟重试（指数退避）
   - RedisRetryQueue 不可用 → `nack(requeue=True)`
   - 超过最大重试次数 → `nack(requeue=False)` 进死信

### 7.4 RabbitMQEventListener

**文件:** `src/infrastructure/messaging/rabbitmq_listener.py`

```python
class RabbitMQEventListener(EventListenerAsync):
    def __init__(self, config: RabbitMQConfig, redis_client: aioredis.Redis) -> None
    def set_dead_letter_queue(self, dlq: DeadLetterQueue) -> None
    async def async_handle(self, event: DomainEvent) -> None
```

- 集成 `DualIdempotencyChecker` + `RedisRetryQueue`
- `_process_event()` 为占位符，由子类/外部覆盖

---

## 8. Infrastructure 层 — Outbox 子系统

### 8.1 OutboxEntity 状态机

**文件:** `src/infrastructure/messaging/outbox/outbox.py`

```
pending ──→ published (终态)
    │
    └──→ failed ──→ pending (重试)
              └──→ archived (终态)
```

- `status`, `retry_count`, `max_retries`, `error_message`
- 非法状态转换抛 `InvalidStateTransitionError`

### 8.2 PostgreSQLOutboxRepository

**文件:** `src/infrastructure/messaging/outbox/outbox_repository.py`

```python
class PostgreSQLOutboxRepository(OutboxRepository):
    # 公共方法（满足 OutboxRepository Protocol）
    async def save(self, event: DomainEvent) -> None
    async def get_unpublished(self, limit: int) -> list[DomainEvent]
    async def mark_published(self, event_id: UUID) -> None
    async def mark_failed(self, event_id: UUID, error: str) -> None
    async def cleanup_old_published_records(self, older_than_days: int) -> int
```

- Session 通过 ContextVar (`session_context.get_session()`) 获取
- `save()` 使用 `session.add()` + `flush()` 触发 DB 约束校验
- 内部使用 `OutboxModel` ORM，公共接口返回 `DomainEvent`

### 8.3 AsyncOutboxPoller

**文件:** `src/infrastructure/messaging/outbox/outbox_processor.py`

```python
class AsyncOutboxPoller:
    def __init__(self, outbox_repository, publisher, router,
                 session_factory=None, poll_interval=1.0, batch_size=10) -> None
    async def poll_once(self) -> None
    async def run(self) -> None     # 无限循环轮询
    def stop(self) -> None
```

**poll_once 流程:**
1. `get_unpublished(batch_size)` 获取 pending 事件
2. 并发发布到 RabbitMQ (`asyncio.gather` + `Semaphore`)
3. 路由键从 `ChannelRouter.get_rabbitmq_routing_key()` 获取
4. 成功 → `mark_published()`，失败 → `mark_failed()`
5. `mark_failed()` 自身失败时仅记录 ERROR，事件保持 pending

**run 流程:**
- 每次轮询创建独立 session context
- `poll_interval` 间隔无限循环
- `stop()` 设置停止标志

### 8.4 InMemoryOutboxRepository

**文件:** `src/infrastructure/messaging/outbox/inmemory_outbox.py`

- MVP 实现，内存列表 + `asyncio.Lock` 保护

### 8.5 PostgreSQL 死信队列

**文件:** `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py`

```python
class PostgresDeadLetterQueue(DeadLetterQueue):
    async def enqueue(self, event, error, retry_count) -> None  # session.add + flush
    async def dequeue(self) -> tuple[DomainEvent, str, int] | None
```

- 实现 Domain 层 `DeadLetterQueue` Protocol
- 返回值对齐: `(DomainEvent, str, int)` 三元组

---

## 9. Infrastructure 层 — 可靠性组件

### 9.1 RetryPolicy

**文件:** `src/infrastructure/messaging/retry/retry_policy.py`

```python
@dataclass
class RetryPolicy:
    base_delay: float = 1.0
    max_delay: float = 60.0
    max_retries: int = 3

    def get_delay(self, retry_count: int) -> float   # 指数退避 + jitter [0.5, 1.5]
    def should_retry(self, retry_count, max_retries=None) -> bool
```

### 9.2 RedisRetryQueue

**文件:** `src/infrastructure/messaging/retry/redis_retry_queue.py`

```python
class RedisRetryQueue:
    _DEQUEUE_SCRIPT = """..."""  # Lua 原子 ZRANGEBYSCORE + ZREM
    def __init__(self, redis_client, queue_key="sisys:retry:queue") -> None
    async def enqueue(self, event_id, event_type, payload, retry_at, ...) -> None
    async def dequeue(self, limit=10) -> list[RetryQueueEntry]
    async def count(self) -> int
    async def peek(self, limit=10) -> list[RetryQueueEntry]
    async def remove(self, event_id) -> bool
    async def clear(self) -> None
```

- ZSET 延迟队列: score 为重试时间戳
- Lua 原子脚本保证并发 dequeue 安全
- Redis Cluster 兼容（单 key 操作）

### 9.3 IdempotencyChecker

**文件:** `src/infrastructure/messaging/retry/checker.py`

```python
class IdempotencyChecker:
    def __init__(self, redis_client=None, host="localhost", port=6379, ...) -> None
    async def try_acquire(self, event_id: UUID, ttl=7*24*3600) -> bool
```

- 单 Redis `SET NX` 原子操作
- Fail-Open: Redis 故障时返回 True（允许处理）
- 默认 TTL 7 天

### 9.4 DualIdempotencyChecker

**文件:** `src/infrastructure/messaging/retry/dual_idempotency_checker.py`

```python
class DualIdempotencyChecker:
    def __init__(self, redis_client, ttl=7*24*3600) -> None
    async def try_acquire(self, event_id: UUID) -> bool
    async def is_processed(self, event_id: UUID) -> bool
```

- 双写模式: Redis `SET NX`（高性能）+ PostgreSQL `INSERT ON CONFLICT DO NOTHING RETURNING event_id`
- 优先 Redis，Redis 失败降级至 PostgreSQL
- PostgreSQL Session 通过 ContextVar 获取
- 双重 Fail-Open: Redis 和 PostgreSQL 都失败时返回 True

---

## 10. Infrastructure 层 — 事件溯源 & 监控

### 10.1 PostgreSQLEventStore

**文件:** `src/infrastructure/messaging/event_store.py`

```python
class PostgreSQLEventStore:
    async def append(self, event: DomainEvent) -> None      # 乐观锁版本检查
    async def get_events(self, aggregate_id: UUID) -> list[DomainEvent]
    async def get_events_by_type(self, event_type, start_time, end_time) -> list[DomainEvent]
```

- 使用 raw SQL (`sqlalchemy.text`)，非 ORM
- Session 通过 ContextVar 获取
- `UNIQUE (aggregate_id, version)` 约束 + 版本冲突抛 `VersionError`

### 10.2 InMemoryEventStore

**文件:** `src/infrastructure/messaging/inmemory_event_store.py`

- MVP 实现 `EventStore` Protocol
- `defaultdict(list)` 按 `aggregate_id` 索引
- 同步方法（与 Protocol 一致）

### 10.3 EventMetricsCollector

**文件:** `src/infrastructure/monitoring/event_metrics.py`

```python
class EventMetricsCollector:
    def record_processed(self, event_type, duration) -> None
    def record_failed(self, event_type, error) -> None
    def record_retried(self, event_type) -> None
    def record_dlq(self, event_type) -> None
    def record_cache_hit(self, cache_type="semantic") -> None
    def record_cache_miss(self, cache_type="semantic") -> None
    @property
    def hit_rate(self) -> float
```

- `deque(maxlen=10_000)` 有界队列存储处理耗时
- asyncio 单线程模型中 `+=1` 天然原子
- 额外包含 OpenTelemetry Tracer (`@contextmanager` 模式)

### 10.4 ErrorMapper

**文件:** `src/infrastructure/messaging/error_mapper.py`

| 映射表 | 错误数 | 目标异常 |
|--------|--------|---------|
| S3 (MinIO) | 18 | NotFoundError, ConflictError, PermissionDeniedError, ThirdPartyError |
| RabbitMQ | 3 | NetworkError, MessageBusError, TimeoutError |
| Redis | 3 | NetworkError, TimeoutError, ServiceUnavailableError |

- `with_error_mapping` 装饰器: 捕获异常后按错误码映射
- 保留原始异常链 (`cause=`)

---

## 11. Infrastructure 层 — EventBusFactory

**文件:** `src/infrastructure/messaging/event_bus_factory.py`

```python
@dataclass
class EventBusConfig:
    redis_url: str | None = None
    rabbitmq_url: str | None = None
    outbox_repository: Any = None
    poll_interval: float = 1.0
    batch_size: int = 10

class EventBusFactory:
    def __init__(self, config=None) -> None
    def create_redis_bus(self) -> RedisEventBus
    def create_rabbitmq_bus(self) -> RabbitMQEventBus
    def create_dual_channel_bus(self) -> tuple[DualChannelEventBus, AsyncOutboxPoller]
```

- 延迟初始化组件，按需创建
- 单个 `ChannelRouter` 实例在所有总线间共享
- 延迟导入避免循环依赖
- **仅用于测试**，生产代码通过 Composition Root 直接注册

---

## 12. Application 层 — 事件处理器

### 12.1 AutoTriggerHandler

**文件:** `src/application/event_handlers/auto_trigger_handler.py`

- 桥接事件总线与 `AutoTriggerService` 领域服务
- 后台线程 + 独立 asyncio 事件循环桥接同步/异步
- 注册 12 种事件类型
- `MAX_CONCURRENT_TASKS=100`, `TASK_TIMEOUT=300s`

### 12.2 AutoRouteHandler

**文件:** `src/application/event_handlers/auto_route_handler.py`

- 监听 `AutoTriggered` → 调用 `AutoRouteService` → 发布 `AutoRouted`
- 遵循系统公理一: trigger → route → execute

### 12.3 AutoExecuteCompletedHandler

**文件:** `src/application/event_handlers/auto_execute_completed_handler.py`

- 监听 `AutoExecuted` → 根据 `business_event_type` 分发到下游领域事件
- 映射: DocumentProcessed → DocumentProcessed, ToolExecuted → ToolExecuted, AgentDecided → AgentDecided

### 12.4 MemoryChangedHandler

**文件:** `src/application/event_handlers/memory_changed_handler.py`

- 处理多层存储同步 (architecture.md §11.2.9):
  - L1 Redis 缓存失效（同步，立即）
  - L2 PostgreSQL 写入（metadata + history）
  - L2.5 MEMORY.md 索引更新
  - L3 Qdrant 向量 [TODO #Story6.3]
  - L5 Neo4j 图谱 [TODO #Story1.17]

---

## 13. Composition Root DI 注册

**文件:** `src/composition_root.py`

| 注册名 | 接口 | 实现 | 生命周期 |
|--------|------|------|---------|
| `router` | `ChannelRouter` | `_create_router()` | SINGLETON |
| `redis_bus` | `EventPublisher` | `RedisEventBus(publisher, subscriber, router)` | SINGLETON |
| `rabbitmq_bus` | `EventPublisher` | `RabbitMQEventBus(outbox_repo, router)` | SINGLETON |
| `event_publisher` | `EventPublisher` | `DualChannelEventBus` | SINGLETON |
| `outbox_repo` | `OutboxRepository` | `PostgreSQLOutboxRepository` | SINGLETON |
| `rabbitmq_publisher` | `RabbitMQPublisher` | `RabbitMQPublisher(config)` | SINGLETON |
| `outbox_poller` | `AsyncOutboxPoller` | `AsyncOutboxPoller(repo, publisher, router, session_factory)` | SINGLETON |
| `event_subscriber` | `EventSubscriber` | `resolve("event_publisher")` | SINGLETON |

**关键设计:**
- `event_subscriber` 解析为 `DualChannelEventBus`（同时实现两个 Protocol）
- `redis_bus` 和 `rabbitmq_bus` 共享 `router` 实例
- `outbox_poller` 需在应用启动时由 lifespan event 触发 `run()`
- YAML 配置在 `_create_router()` 中通过 `EventBusConfigLoader.load()` 集成

---

## 14. 配置

### 14.1 RedisConfig

**文件:** `src/infrastructure/config/redis.py`

```python
@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 10
    default_ttl: int = 86400
```

### 14.2 RabbitMQConfig

**文件:** `src/infrastructure/config/rabbitmq.py`

```python
@dataclass
class RabbitMQConfig:
    host: str = "localhost"        # RABBITMQ_HOST
    port: int = 5672               # RABBITMQ_PORT
    username: str = "guest"        # RABBITMQ_USERNAME
    password: str = "guest"        # RABBITMQ_PASSWORD
    vhost: str = "/"               # RABBITMQ_VHOST
```

### 14.3 YAML 配置

**文件:** `config/event_channels.yaml`

```yaml
event_channels:
  AutoTriggered:     delivery_mode: "realtime", redis_channel: "sisys:rt:auto_triggered"
  AutoRouted:        delivery_mode: "realtime", redis_channel: "sisys:rt:auto_routed"
  DocumentProcessed: delivery_mode: "reliable", rabbitmq_routing_key: "sisys.events.reliable.document_processed"
  MemoryChanged:     delivery_mode: "reliable", rabbitmq_routing_key: "sisys.events.reliable.memory_changed"
  CheckpointReached: delivery_mode: "reliable", rabbitmq_routing_key: "sisys.events.reliable.checkpoint_reached"
  AuditEvent:        delivery_mode: "reliable", rabbitmq_routing_key: "audit.audit_event"
```

### 14.4 Alembic 迁移

| 版本 | 文件 | 内容 |
|------|------|------|
| 001_initial | `001_initial.py` | `event_outbox` 表 |

---

## 15. 测试体系

### 15.1 测试分层

| 类型 | 位置 | 覆盖内容 |
|------|------|---------|
| **端口契约测试** | `tests/contracts/` | `test_port_contract_event_publisher.py` |
| **单元测试** | `tests/unit/` | 35+ 测试文件，覆盖 Domain 事件、Infrastructure 组件 |
| **集成测试** | `tests/integration/` | `test_event_bus_integration.py`, `test_event_messaging_integration.py` |
| **验收测试 (BDD)** | `tests/acceptance/` | Story 1.3, 1.4, 1.13, 1.14, 1.16, 20.2 |
| **架构约束测试** | `tests/unit/architecture/` | Domain 层零外部依赖、依赖方向 |

### 15.2 关键测试文件

| 文件 | 覆盖目标 |
|------|---------|
| `test_events_base.py` | DomainEvent 基类（序列化、反序列化、注册表） |
| `test_event_serialization.py` | 所有事件类型 roundtrip |
| `test_channel_router.py` | DEFAULT_MAPPINGS、register、override |
| `test_dual_channel_event_bus.py` | 双通道路由、订阅限制 |
| `test_redis_event_bus_new.py` | RedisEventBus 发布/订阅 |
| `test_rabbitmq_event_bus_new.py` | RabbitMQEventBus + Outbox |
| `test_async_outbox_poller.py` | Poller 轮询、并发发布 |
| `test_outbox_pattern.py` | Outbox 模式端到端 |
| `test_rabbitmq_consumer.py` | 消费者 ACK/NACK/重试/DLQ |
| `test_redis_retry_queue.py` | Lua 原子 dequeue、并发测试 |
| `test_dual_idempotency_checker.py` | Redis+PG 双写幂等 |
| `test_event_outbox_adapter.py` | DomainEvent ↔ OutboxEntity 转换 |
| `test_event_bus_factory.py` | 工厂创建 |
| `test_error_mapper.py` | 错误映射 |
| `test_event_metrics_extension.py` | 指标收集 |

---

## 16. 设计模式汇总

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **六边形架构** | 全部 | Domain Ports + Infrastructure Adapters，Domain 层零外部依赖 |
| **双通道 Facade** | `DualChannelEventBus` | 统一入口，内部路由到 Redis/RabbitMQ |
| **Protocol 结构化子类型** | 所有 Port | `@runtime_checkable` Protocol |
| **Transaction Outbox** | `RabbitMQEventBus` + Poller | 保证事件与业务同事务，最终一致投递 |
| **多态反序列化注册表** | `DomainEvent._registry` | `__init_subclass__` 自动注册 |
| **策略模式** | `ChannelRouter` | 事件类型到通道的动态路由 |
| **Copy-on-Write** | `ChannelRouter._mappings` | 不可变 dict 原子替换，并发读安全 |
| **懒初始化** | `RedisEventPublisher._get_pool()` | 连接池按需创建 + asyncio.Lock |
| **状态机** | `OutboxEntity` | pending → published/failed → archived |
| **幂等性双写** | `DualIdempotencyChecker` | Redis + PostgreSQL，Fail-Open |
| **延迟队列** | `RedisRetryQueue` | ZSET + Lua 原子 dequeue |
| **指数退避 + Jitter** | `RetryPolicy` | 防惊群效应 |
| **事件溯源** | `PostgreSQLEventStore` | 乐观锁 + 追加存储 |
| **错误标准化** | `ErrorMapper` | 外部 SDK 异常 → 领域异常 |
| **错误链保留** | `wrap_external_error` | `cause=` 保留原始异常 |

---

## 17. 已知限制与 TODO

| 项目 | 优先级 | 说明 |
|------|--------|------|
| 单 Poller 实例约束 | P2 | 多实例部署会重复发布，需 `SELECT ... FOR UPDATE SKIP LOCKED` |
| 事件 Schema 版本迁移 | P2 | 缺少 EventUpcaster 机制 |
| 处理进度追踪 | P2 | 消费者重启后无法断点续传 |
| 消息顺序保证 | P3 | 同聚合事件可能乱序消费 |
| Event Snapshotting | P3 | 长事件流重建效率低 |
| 真实 Redis/RabbitMQ 集成测试 | P3 | 当前集成测试使用 mock |
| L3 向量索引触发 | TODO | MemoryChangedHandler 中 L3 标记为 `#Story6.3` |
| L5 图谱索引触发 | TODO | MemoryChangedHandler 中 L5 标记为 `#Story1.17` |

---

## 18. 关键文件索引

### 18.1 Domain 层

| 文件 | 内容 |
|------|------|
| `src/domain/events/base.py` | DomainEvent 基类 + `_registry` |
| `src/domain/events/publish_result.py` | PublishResult |
| `src/domain/events/listener.py` | EventListener, EventListenerAsync, DeadLetterQueue + MVP 实现 |
| `src/domain/events/event_store.py` | EventStore Protocol |
| `src/domain/events/enums.py` | 共享枚举 |
| `src/domain/events/*_events.py` | 15+ 具体事件类 |
| `src/domain/ports/event_publisher.py` | EventPublisher Protocol |
| `src/domain/ports/outbox.py` | OutboxRepository Protocol |

### 18.2 Application 层

| 文件 | 内容 |
|------|------|
| `src/application/ports/event_subscriber.py` | EventSubscriber Protocol |
| `src/application/event_handlers/auto_trigger_handler.py` | AutoTriggerHandler |
| `src/application/event_handlers/auto_route_handler.py` | AutoRouteHandler |
| `src/application/event_handlers/auto_execute_completed_handler.py` | AutoExecuteCompletedHandler |
| `src/application/event_handlers/memory_changed_handler.py` | MemoryChangedHandler |

### 18.3 Infrastructure 层

| 文件 | 内容 |
|------|------|
| `src/infrastructure/messaging/dual_channel_event_bus.py` | 双通道 Facade |
| `src/infrastructure/messaging/channel_router.py` | ChannelRouter + DeliveryMode |
| `src/infrastructure/messaging/event_bus_config_loader.py` | YAML 配置加载 |
| `src/infrastructure/messaging/event_bus_factory.py` | EventBusFactory |
| `src/infrastructure/messaging/redis_event_bus.py` | RedisEventBus |
| `src/infrastructure/messaging/redis_publisher.py` | RedisEventPublisher |
| `src/infrastructure/messaging/redis_subscriber.py` | RedisEventSubscriber |
| `src/infrastructure/messaging/rabbitmq_event_bus.py` | RabbitMQEventBus |
| `src/infrastructure/messaging/rabbitmq_publisher.py` | RabbitMQPublisher |
| `src/infrastructure/messaging/rabbitmq_consumer.py` | RabbitMQConsumer |
| `src/infrastructure/messaging/rabbitmq_listener.py` | RabbitMQEventListener |
| `src/infrastructure/messaging/inmemory_event_bus.py` | InMemoryEventBus |
| `src/infrastructure/messaging/inmemory_event_store.py` | InMemoryEventStore |
| `src/infrastructure/messaging/event_store.py` | PostgreSQLEventStore |
| `src/infrastructure/messaging/error_mapper.py` | ErrorMapper |
| `src/infrastructure/messaging/outbox/outbox.py` | OutboxEntity 状态机 |
| `src/infrastructure/messaging/outbox/outbox_processor.py` | AsyncOutboxPoller |
| `src/infrastructure/messaging/outbox/outbox_repository.py` | PostgreSQLOutboxRepository |
| `src/infrastructure/messaging/outbox/inmemory_outbox.py` | InMemoryOutboxRepository |
| `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py` | PostgresDeadLetterQueue |
| `src/infrastructure/messaging/retry/retry_policy.py` | RetryPolicy |
| `src/infrastructure/messaging/retry/redis_retry_queue.py` | RedisRetryQueue |
| `src/infrastructure/messaging/retry/checker.py` | IdempotencyChecker |
| `src/infrastructure/messaging/retry/dual_idempotency_checker.py` | DualIdempotencyChecker |
| `src/infrastructure/messaging/adapters/event_outbox_adapter.py` | DomainEvent ↔ OutboxEntity |
| `src/infrastructure/messaging/adapters/sqlalchemy_event_outbox_adapter.py` | DomainEvent ↔ OutboxModel |
| `src/infrastructure/monitoring/event_metrics.py` | EventMetricsCollector + OpenTelemetryTracer |
| `src/infrastructure/config/redis.py` | RedisConfig |
| `src/infrastructure/config/rabbitmq.py` | RabbitMQConfig |
| `config/event_channels.yaml` | YAML 通道映射 |
