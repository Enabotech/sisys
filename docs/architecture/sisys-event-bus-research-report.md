# SISYS事件总线子系统全面调研报告与完善建议

**版本**: v2.0
**日期**: 2026-05-17
**范围**: 仅事件总线子系统（不含Saga/UoW/事务协调）
**对标基准**: NServiceBus、Axon Framework、Eventuate、MassTransit

---

## 1. 系统概述

### 1.1 设计定位

SISYS事件总线子系统采用**双通道模式（Dual-Channel Event Bus）**，是整个系统的"血液"：

- **REALTIME通道**: Redis Pub/Sub，低延迟（P95 < 50ms），用于心跳、自动触发等实时通知
- **RELIABLE通道**: PostgreSQL Outbox + RabbitMQ，100%可靠传输，用于审计、合规、业务状态变更事件

### 1.2 架构约束

遵循严格的六边形架构：

| 层级 | 位置 | 外部依赖约束 |
|------|------|--------------|
| Domain | `src/domain/events/`, `src/domain/ports/` | 仅Python标准库 |
| Application | `src/application/ports/` | 仅依赖Domain层 |
| Infrastructure | `src/infrastructure/messaging/` | 可依赖外部库（Redis、RabbitMQ、SQLAlchemy） |

### 1.3 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Application Layer                                   │
│                                                                              │
│   UseCase / EventHandler —— inject EventPublisher Port                      │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ EventSubscriber (Protocol)   — "当X发生时我要做什么" (应用层关注点)    │   │
│  │ async subscribe(event_type, handler)                                 │   │
│  │ async subscribe_async(event_type, handler)                           │   │
│  │ async start() / async close()                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ publish(event) / subscribe()
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Domain Layer (零外部依赖)                             │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ DomainEvent   │  │ EventPublisher  │  │ OutboxRepository            │  │
│  │ (frozen       │  │ (Protocol)      │  │ (Protocol)                  │  │
│  │  dataclass)   │  │                 │  │                              │  │
│  │ + _registry   │  │ async publish() │  │ async save()                │  │
│  │ + to/from_dict│  │ → PublishResult │  │ async get_unpublished()     │  │
│  └───────────────┘  └─────────────────┘  └──────────────────────────────┘  │
│  ┌───────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │ PublishResult │  │ EventStore (Protocol)                           │   │
│  │ (frozen       │  │ async save_events() / get_events()              │   │
│  │  dataclass)   │  │ async get_events_by_version()                   │   │
│  │ redis_success │  └─────────────────────────────────────────────────┘   │
│  │ outbox_saved  │                                                          │
│  └───────────────┘                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Infrastructure Layer                                   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                  DualChannelEventBus (Facade)                        │   │
│  │           implements EventPublisher (Domain) + EventSubscriber (App) │   │
│  └───────────┬────────────────────────────────────┬─────────────────────┘   │
│              │ ChannelRouter                       │                         │
│              │ get_delivery_mode(event_type)       │                         │
│              │ ┌─ overrides (runtime)              │                         │
│              │ ├─ DEFAULT_MAPPINGS (6 events)      │                         │
│              │ └─ YAML config (event_channels.yaml)│                         │
│              ▼                                     ▼                         │
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
│                                       │  │ ├── RetryPolicy          │ │   │
│                                       │  │ │   (指数退避+抖动)       │ │   │
│                                       │  │ ├── RedisRetryQueue      │ │   │
│                                       │  │ │   (ZSET延迟队列)        │ │   │
│                                       │  │ └── DeadLetterQueue      │ │   │
│                                       │  │     (可重试/人工/忽略)    │ │   │
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
│  │  append() / get_events() / get_events_by_version() (乐观锁)          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 事件分类

系统定义了**15+领域事件**，按传输需求分类：

| 类别 | 事件示例 | 通道 | 持久化要求 |
|------|----------|------|-----------|
| 实时通知 | HeartbeatTriggered, AutoTriggered, AutoRouted | Redis Pub/Sub | 无 |
| 业务状态 | DocumentProcessed, ToolExecuted, AgentDecided | RabbitMQ + Outbox | WORM 7年归档 |
| 审计合规 | AuditEvent, CheckpointReached | RabbitMQ + Outbox | SOX合规 |

---

## 2. 现有实现分析

### 2.1 核心组件清单

```
src/domain/
├── events/                          # 领域事件定义
│   ├── base.py                      # DomainEvent基类，多态反序列化注册表
│   ├── publish_result.py            # PublishResult复合结果
│   ├── listener.py                  # EventListener/EventListenerAsync Protocol
│   │                                # + DeadLetterQueue Protocol (重复定义①)
│   ├── event_store.py               # EventStore Protocol
│   ├── enums.py                     # 共享枚举
│   └── *_events.py                  # 15+具体事件类
├── ports/
    ├── event_publisher.py           # EventPublisher Protocol + InMemoryEventPublisher Protocol
    └── outbox.py                    # OutboxRepository Protocol（同步签名，契约违背）

src/application/ports/
└── event_subscriber.py              # EventSubscriber Protocol

src/infrastructure/messaging/
├── dual_channel_event_bus.py        # 双通道门面（Facade）
├── redis_event_bus.py               # Redis Pub/Sub实现（Publisher+Subscriber）
├── rabbitmq_event_bus.py            # RabbitMQ+Outbox实现（仅Publisher）
├── inmemory_event_bus.py            # 内存实现（同步，不兼容EventPublisher Protocol）
├── channel_router.py                # 事件类型→通道映射（DeliveryMode枚举）
├── event_bus_factory.py             # 工厂+全局单例（类级别可变状态）
├── event_bus_config_loader.py       # YAML配置加载器
├── redis_publisher.py               # RedisEventPublisher（连接池未保护）
├── redis_subscriber.py              # RedisEventSubscriber（error_handler覆盖bug）
├── rabbitmq_publisher.py            # RabbitMQPublisher（aio_pika）
├── rabbitmq_consumer.py             # RabbitMQConsumer（ACK/NACK/重试/DLQ）
├── rabbitmq_listener.py             # RabbitMQEventListener（不完整：无自动消费）
├── error_mapper.py                  # 外部错误→领域异常映射
├── message_serializer.py            # InMemoryEventStore（命名误导）
├── event_store.py                   # PostgreSQLEventStore（乐观锁）
├── outbox/
│   ├── outbox.py                    # OutboxEntity状态机
│   ├── outbox_processor.py          # AsyncOutboxPoller（访问私有方法，路由键硬编码）
│   ├── outbox_repository.py         # PostgreSQLOutboxRepository（同步方法抛NotImplementedError）
│   ├── inmemory_outbox.py           # InMemoryOutboxRepository
│   ├── dead_letter_queue.py         # DeadLetterQueue ABC (重复定义②)
│   └── postgres_dead_letter_queue.py # PostgreSQL DLQ实现
├── retry/
│   ├── retry_policy.py              # 指数退避+抖动
│   ├── redis_retry_queue.py         # ZSET延迟队列（dequeue非原子）
│   ├── checker.py                   # IdempotencyChecker（Redis SET NX，故障时fail-open）
│   └── dual_idempotency_checker.py  # 双写幂等（Redis+PostgreSQL，PostgreSQL回退不可靠）
└── adapters/
    ├── event_outbox_adapter.py      # EventRegistry (重复定义③) + DomainEvent↔OutboxEntity
    └── sqlalchemy_event_outbox_adapter.py  # DomainEvent↔OutboxModel

src/composition_root.py              # DI注册（EventBus相关）
config/event_channels.yaml           # 6个事件通道映射配置
```

### 2.2 设计模式应用

| 模式 | 实现位置 | 评价 |
|------|----------|------|
| 六边形架构 | Domain Ports + Infrastructure Adapters | ✅ 严格遵循，Domain层零外部依赖 |
| Transactional Outbox | `RabbitMQEventBus` → Outbox → Poller → RabbitMQ | ✅ 正确实现 |
| Facade | `DualChannelEventBus` 统一入口 | ✅ 符合NServiceBus Scheme B |
| Strategy | `ChannelRouter` 动态路由 | ✅ 配置驱动+运行时覆盖 |
| Factory | `EventBusFactory` | ⚠️ 全局可变类状态，与Composition Root双轨创建 |
| Event Sourcing | `PostgreSQLEventStore` | ✅ 乐观锁+追加存储 |

### 2.3 测试覆盖现状

- **单元测试**: 35+测试文件，覆盖Domain事件、Infrastructure组件、Architecture约束
- **集成测试**: `test_event_bus_integration.py`（使用mock，非真实Redis/RabbitMQ）
- **契约测试**: `test_event_publisher_contract.py`验证Protocol契约
- **架构约束测试**: AST解析验证Domain层零外部依赖

**覆盖率**: EventBus层 ≥85%，集成测试 ≥75%（符合Story 1.3验收标准）

**测试缺口**:
- 无真实Redis/RabbitMQ集成测试
- InMemoryEventBus无专属测试文件
- ErrorMapper/OpenTelemetryTracer无测试
- PostgreSQLEventStore无测试
- Composition Root EventBus注册无测试
- 并发场景测试不足（仅IdempotencyChecker有并发测试）

---

## 3. 业界最佳实践对标

### 3.1 NServiceBus对标分析

| 特性 | NServiceBus | SISYS现状 | 评估 |
|------|-------------|----------|------|
| 统一入口 | `IEndpointInstance` 统一发送/发布 | `DualChannelEventBus` 统一发布 | ✅ 符合 |
| Outbox模式 | Transactional Outbox + Deduplication | Outbox + DualIdempotencyChecker | ✅ 符合 |
| 幂等处理 | Distributed Deduplication | Redis SET NX + PostgreSQL fallback | ⚠️ PostgreSQL回退不可靠 |
| 重试策略 | First-level retry + SLR | RetryPolicy + RedisRetryQueue | ⚠️ 缺少Second-Level Retry |
| 消息审计 | Audit Queue + Forwarding | AuditEvent + WORM归档 | ✅ 符合 |
| 消息头传播 | 消息头自动传播（CorrelationId/CausationId） | DomainEvent含correlation_id/causation_id | ✅ 符合 |
| 消息体序列化 | 内置Serializer + 自定义 | JSON序列化 + DomainEvent.to_dict/from_dict | ✅ 符合 |

### 3.2 Axon Framework对标分析

| 特性 | Axon Framework | SISYS现状 | 评估 |
|------|----------------|----------|------|
| Event Bus | `EventBus` + `EventGateway` | `DualChannelEventBus` | ✅ 基础实现 |
| Event Store | `EventStore` + Snapshotting | `PostgreSQLEventStore` | ⚠️ 无快照机制 |
| Event Processing | `EventProcessor` + `TrackingToken` | `RabbitMQConsumer` + `RedisEventSubscriber` | ⚠️ 无处理进度追踪 |
| 分区处理 | `SequencingPolicy` | 无 | ❌ 缺失 |
| 事件Upcaster | Schema版本迁移 | 无 | ❌ 缺失 |

### 3.3 Eventuate对标分析

| 特性 | Eventuate | SISYS现状 | 评估 |
|------|-----------|----------|------|
| 事件发布 | `AggregateCrud` + `EventPublisher` | `DualChannelEventBus` + Outbox | ✅ 符合 |
| 订阅处理 | `EventHandler` + `TrackingProcessor` | `EventListener` Protocol | ⚠️ 基础实现，无进度追踪 |
| 幂等处理 | 参与者合约 + 幂等键 | `IdempotencyChecker` + `DualIdempotencyChecker` | ⚠️ PostgreSQL回退不可靠 |
| 消息顺序 | 因果关系+聚合级顺序保证 | 无顺序保证 | ❌ 缺失 |

### 3.4 核心差距汇总

| 差距项 | 业界标准 | SISYS影响 | 优先级 |
|--------|----------|----------|--------|
| Second-Level Retry | NServiceBus SLR | 失败事件缺乏分级重试 | **P2** |
| 事件Schema版本迁移 | Axon Upcaster | Schema变更无法向后兼容 | **P2** |
| 处理进度追踪 | Axon TrackingToken / Eventuate | 消费者重启后无法断点续传 | **P2** |
| 消息顺序保证 | Eventuate聚合级顺序 | 同一聚合事件可能乱序消费 | **P3** |
| Event Snapshotting | Axon快照策略 | 长事件流重建效率低 | **P3** |

---

## 4. 代码质量问题分析

### 4.1 重复定义（P0）

#### 问题1: DeadLetterQueue三处定义

```python
# ① src/domain/events/listener.py — Protocol + InMemoryDeadLetterQueue
class DeadLetterQueue(Protocol):
    async def enqueue(self, event, error, retry_count): ...
    async def dequeue(self) -> tuple[DomainEvent, str, int] | None: ...

# ② src/infrastructure/messaging/outbox/dead_letter_queue.py — ABC + InMemoryDeadLetterQueue
class DeadLetterQueue(ABC):
    async def enqueue(self, entry: DeadLetterQueueEntry): ...
    async def dequeue(self) -> DeadLetterQueueEntry | None: ...

# ③ src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py
class PostgresDeadLetterQueue(DeadLetterQueue):  # 继承②
```

**影响**: 类型签名不一致（Protocol用`tuple`返回，ABC用`Entry`对象），维护混乱。

**建议**: 统一到Domain层单一Protocol，Infrastructure层仅提供实现。

#### 问题2: EventRegistry与DomainEvent._registry重复

```python
# src/domain/events/base.py — 自动注册
class DomainEvent:
    _registry: ClassVar[dict[str, type[DomainEvent]]] = {}
    def __init_subclass__(cls) -> None:
        DomainEvent._registry[cls.event_type] = cls

# src/infrastructure/messaging/adapters/event_outbox_adapter.py — 手动扫描
class EventRegistry:
    _build_registry()  # 扫描DomainEvent.__subclasses__()
    register(), get(), reset()
```

**影响**: 两套注册表需同步维护。`EventRegistry`依赖`__subclasses__()`仅返回已导入的子类，新增事件类必须在此模块显式import。

**建议**: 移除`EventRegistry`，统一使用`DomainEvent._registry`。

#### 问题3: 事件类型注册方式不一致

部分事件自动注册（`__init_subclass__`），部分手动注册：

```python
# 自动注册 — event_type有default且init=False
class DocumentProcessed(DomainEvent):
    event_type: str = field(default="DocumentProcessed", init=False)

# 手动注册 — __post_init__设置 + 模块底部手动注册
class AutoTriggered(DomainEvent):
    def __post_init__(self):
        object.__setattr__(self, "event_type", "AutoTriggered")
DomainEvent._registry["AutoTriggered"] = AutoTriggered  # 模块底部
```

**影响**: 遗忘手动注册将导致`from_dict`反序列化失败，且无编译期或运行时告警。

**建议**: 统一为`__init_subclass__`自动注册，移除所有手动注册。

### 4.2 契约违背（P1）

#### 问题4: OutboxRepository Protocol同步/异步不匹配

```python
# src/domain/ports/outbox.py — Protocol定义同步方法
class OutboxRepository(Protocol):
    def save(self, event: DomainEvent) -> OutboxEntity: ...
    def get_unpublished(self, limit: int) -> list[DomainEvent]: ...
    def mark_published(self, event_id: str) -> None: ...

# src/infrastructure/messaging/outbox/outbox_repository.py — 同步方法抛异常
class PostgreSQLOutboxRepository(OutboxRepository):
    def get_unpublished(self, limit: int) -> list[DomainEvent]:
        raise NotImplementedError("Use async_get_unpublished instead")
    async def async_get_unpublished(self, limit: int) -> list[DomainEvent]:
        # 实际实现
```

**影响**: Protocol契约在运行时被违背，静态类型检查无法捕获。

**建议**: 将`OutboxRepository` Protocol改为async方法签名。

#### 问题5: InMemoryEventBus不兼容EventPublisher Protocol

```python
# src/domain/ports/event_publisher.py — async Protocol
class EventPublisher(Protocol):
    async publish(event, channel=None) -> PublishResult: ...

# src/infrastructure/messaging/inmemory_event_bus.py — 同步实现
class InMemoryEventBus(InMemoryEventPublisher):  # 实现的是同步Protocol
    def publish(self, event) -> None: ...        # 同步，不返回PublishResult
```

**影响**: InMemoryEventBus无法在需要`EventPublisher`的场景中使用，测试需额外适配器。

**建议**: InMemoryEventBus同时实现`EventPublisher` Protocol（async版）。

### 4.3 封装违背（P1）

#### 问题6: AsyncOutboxPoller访问私有方法

```python
# src/infrastructure/messaging/outbox/outbox_processor.py
class AsyncOutboxPoller:
    async def poll_once(self) -> None:
        entities = await self._repo._get_unpublished_entities(self._batch_size)  # 私有方法
        for entity in entities:
            await self._rabbitmq_publisher.async_publish(...)
            await self._repo._mark_published_entity(entity.event_id)  # 私有方法
```

**影响**: Poller与具体Repository实现强耦合，替换Repository需同时修改Poller。

**建议**: 在`OutboxRepository` Protocol中定义async公共方法，Poller仅通过公共接口交互。

### 4.4 设计缺陷（P1-P2）

#### 问题7: EventBusFactory全局可变状态

```python
class EventBusFactory:
    _instance: ClassVar[EventBusFactory | None] = None  # 类级别可变
    _poller: ClassVar[AsyncOutboxPoller | None] = None
```

**影响**: 线程不安全，测试间共享状态污染，与Composition Root双轨创建实例。

**建议**: 移除类级别可变状态，统一由Composition Root管理生命周期。

#### 问题8: Composition Root与Factory双轨创建

Composition Root直接创建`RedisEventPublisher`/`RedisEventSubscriber`，而`EventBusFactory`也创建独立实例。两者不共享连接池。

**建议**: 统一由Composition Root管理，Factory仅提供创建逻辑不做单例管理。

#### 问题9: AsyncOutboxPoller路由键硬编码

```python
# outbox_processor.py
routing_key = f"sisys.events.reliable.{entity.event_type}"  # 硬编码
```

**影响**: 忽略`ChannelRouter`配置，新增事件类型需修改Poller代码。

**建议**: Poller注入`ChannelRouter`，通过`get_rabbitmq_routing_key()`获取路由键。

#### 问题10: DualChannelEventBus.publish()的channel参数是死参数

```python
async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult:
    # channel参数被接受但从未使用，路由完全由ChannelRouter决定
```

**影响**: 接口契约误导，调用者以为可以指定通道。

**建议**: 移除`channel`参数，或文档明确标记为忽略。

### 4.5 可靠性风险（P2）

#### 问题11: RedisRetryQueue.dequeue()非原子

```python
async def dequeue(self, limit: int) -> list[RetryQueueEntry]:
    entries = await self._client.zrangebyscore(...)  # 读
    for entry in entries:
        await self._client.zrem(...)                  # 删（非原子）
```

**影响**: 并发消费者可能重复取出同一条目。

**建议**: 使用Lua脚本保证原子读删，或使用`ZPOPMIN`（Redis 5.0+）。

#### 问题12: DualIdempotencyChecker PostgreSQL回退不可靠

```python
async def _try_acquire_postgresql(self, event_id: str) -> bool:
    result = await session.execute(insert(...).on_conflict_do_nothing())
    return result.fetchone() is not None  # INSERT ON CONFLICT后fetchone不可靠
```

**影响**: 可能误判事件已处理（false negative），导致事件被跳过。

**建议**: 使用`INSERT ... ON CONFLICT DO NOTHING RETURNING event_id`，或改为先查后插。

#### 问题13: RabbitMQConsumer修改消息Header

```python
message.headers["x-retry-count"] = str(retry_count + 1)  # Header可能不可变
await message.nack(requeue=True)                          # 修改后的Header可能不持久
```

**影响**: aio_pika某些版本下Header不可变导致运行时错误；requeue后Header修改可能不保留。

**建议**: 使用`RedisRetryQueue`做显式延迟重试，而非依赖Nack requeue。

#### 问题14: IdempotencyChecker故障时fail-open

```python
async def try_acquire(self, event_id: str) -> bool:
    try:
        return await self._client.set(key, "1", nx=True, ex=self._ttl)
    except Exception:
        return True  # fail-open：Redis故障时允许重复处理
```

**影响**: Redis宕机期间事件会被重复处理。

**建议**: 这是可用性vs一致性的设计权衡，当前选择合理。但应在文档中明确标注此行为，并依赖下游消费者自身幂等。

### 4.6 线程安全（P2）

| 组件 | 问题 | 建议 |
|------|------|------|
| `ChannelRouter._mappings` | 无锁保护，`register()`和`get_delivery_mode()`并发不安全 | 加`asyncio.Lock`或改为不可变映射 |
| `EventMetricsCollector` | 计数器使用非原子`+=` | 改用`threading.Lock`或`asyncio.Lock` |
| `RedisEventPublisher._get_pool()` | 声明了`_pool_lock`但未使用 | 在`_get_pool()`中使用锁保护 |
| `InMemoryOutboxRepository` | 公共同步方法无锁保护 | 文档标注或加锁 |

### 4.7 中低优先级问题

| 问题 | 优先级 | 说明 |
|------|--------|------|
| `message_serializer.py`命名误导 | P3 | 包含`InMemoryEventStore`而非序列化器 |
| `EventBusConfigLoader.from_default_path()`命名误导 | P3 | 返回loader但不加载，调用者仍需`load()` |
| YAML配置未集成 | P3 | composition_root未调用`EventBusConfigLoader.load()` |
| PostgreSQL类级别asyncio.Lock | P3 | 事件循环启动前实例化可能失败 |
| RedisEventBus无Redis通道时静默丢弃事件 | P2 | `get_redis_channel()`返回None时无日志 |
| RedisEventSubscriber覆盖error_handler | P2 | 同通道第二次subscribe的error_handler被忽略 |
| PostgreSQLEventStore的CREATE TABLE SQL语法错误 | P2 | 多语句无分号分隔 |

---

## 5. 设计文档vs代码实现差距

| 设计文档要求 | 代码实现现状 | 差距 |
|-------------|-------------|------|
| 6个DEFAULT_MAPPINGS事件 | ✅ 一致 | 无 |
| RELIABLE事件走Outbox→Poller→RabbitMQ | ✅ 一致 | 无 |
| EventPublisher/EventSubscriber分离 | ✅ 一致 | 无 |
| YAML配置驱动 | ⚠️ 代码存在但未集成 | composition_root未调用ConfigLoader |
| event_id类型: UUID vs str(ULID) | ⚠️ 代码使用str | architecture.md两处定义不一致 |
| event_type命名: PascalCase vs snake_case | ⚠️ 代码使用PascalCase | architecture.md第17章用snake_case |
| 12个领域事件的通道映射 | ❌ 仅6个有DEFAULT_MAPPINGS | 6个事件缺通道配置 |
| RabbitMQConsumer独立设计 | ⚠️ 代码存在但订阅模式未集成 | RELIABLE订阅无法通过DualChannelEventBus |
| EventMetricsCollector | ✅ 代码存在 | 无 |
| IdempotencyChecker | ✅ 代码存在 | 无 |
| DLQ处理和告警 | ⚠️ 代码存在但无告警 | 无DLQ堆积告警 |
| 事件Schema版本迁移 | ❌ 不存在 | or.md要求但未实现 |
| 事件处理顺序保证 | ❌ 不存在 | 同聚合事件可能乱序 |

---

## 6. 完善建议与路线图

### 6.1 Phase 1: 代码质量修复（Week 1-2，P0-P1）

| 任务 | 工作量 | 验收标准 |
|------|--------|----------|
| 统一DeadLetterQueue | 1天 | Domain层单一Protocol，Infrastructure层实现继承 |
| 移除EventRegistry | 0.5天 | 统一使用DomainEvent._registry |
| 统一事件注册方式 | 0.5天 | 所有事件类型通过`__init_subclass__`自动注册 |
| OutboxRepository async Protocol | 0.5天 | Protocol改为async方法签名 |
| InMemoryEventBus兼容EventPublisher | 0.5天 | 同时实现async Protocol |
| Poller公共接口重构 | 1天 | OutboxRepository新增async公共方法，Poller不再访问私有方法 |
| EventBusFactory去除类级别可变状态 | 0.5天 | 改为模块级单例或由Composition Root管理 |
| Poller路由键改用ChannelRouter | 0.5天 | 注入ChannelRouter，不再硬编码 |
| 移除publish()的channel死参数 | 0.5天 | 接口签名清理 |

**验收**: 所有35+现有测试通过，Architecture约束测试通过。

### 6.2 Phase 2: 可靠性增强（Week 3-4，P2）

| 任务 | 工作量 | 验收标准 |
|------|--------|----------|
| RedisRetryQueue原子dequeue | 1天 | Lua脚本或ZPOPMIN，并发测试通过 |
| DualIdempotencyChecker PostgreSQL回退修复 | 0.5天 | RETURNING子句或先查后插 |
| RabbitMQConsumer重试改用RedisRetryQueue | 1天 | 不再依赖Nack requeue传递Header |
| Composition Root与Factory统一 | 1天 | 消除双轨创建，共享连接池 |
| YAML配置集成 | 0.5天 | composition_root调用EventBusConfigLoader |
| 补全12个事件的通道映射 | 0.5天 | DEFAULT_MAPPINGS覆盖所有领域事件 |
| 事件Schema版本迁移框架 | 2天 | EventUpcaster机制+版本列 |
| Second-Level Retry | 2天 | 本地重试→远程延迟队列分级 |
| 处理进度追踪（Processing Token） | 2天 | 消费者重启后断点续传 |
| 线程安全修复 | 1天 | ChannelRouter/Metrics/Lock修复 |

### 6.3 Phase 3: 性能优化与运维（Week 5-6，P3）

| 任务 | 工作量 | 验收标准 |
|------|--------|----------|
| Event Snapshotting | 2天 | 长事件流快照压缩，重建效率提升10x |
| Batch Publishing | 1天 | Outbox批量发布优化 |
| 性能基准测试 | 2天 | P95延迟<30ms，吞吐>2000 events/sec |
| 健康检查端点 | 1天 | EventBus健康状态HTTP端点 |
| 监控仪表板 | 2天 | Grafana仪表板（延迟/吞吐/DLQ堆积） |
| 告警规则 | 1天 | Prometheus告警规则 |
| 真实Redis/RabbitMQ集成测试 | 2天 | 端到端验证 |
| 运维手册 | 1天 | DLQ处理、重放、故障恢复文档 |

---

## 7. 架构评估

### 7.1 当前架构评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 六边形架构合规 | 9.5/10 | Domain层严格零依赖，Port分离清晰 |
| Outbox实现完整性 | 9/10 | 状态机+Poller+幂等完整 |
| 测试覆盖 | 8.5/10 | 单元+集成+契约+架构约束完整，缺真实集成测试 |
| 代码质量 | 7.5/10 | 存在3处重复定义、1处契约违背、2处封装违背 |
| 业界对标 | 7/10 | 缺SLR/Schema迁移/进度追踪/顺序保证 |
| 可靠性 | 7/10 | DLQ非原子dequeue、PostgreSQL幂等回退不可靠、Nack Header不可靠 |
| 线程安全 | 6/10 | 4个组件存在并发问题 |
| 运维支持 | 6/10 | 缺健康检查、监控仪表板、DLQ告警 |

**综合评分**: 7.5/10

### 7.2 核心优势

1. **双通道设计方向正确**: REALTIME/RELIABLE分离符合业务需求
2. **Outbox模式实现完整**: 状态机+Poller+幂等的组合是业界标准
3. **Domain层零污染**: 六边形架构严格遵守，这是后续扩展的基础
4. **测试文化良好**: 35+测试文件覆盖核心组件

### 7.3 核心风险

1. **重复定义导致维护隐患**: DLQ/EventRegistry/事件注册三处重复，改一处忘另一处
2. **契约违背隐藏运行时炸弹**: OutboxRepository同步方法抛异常，迟早有消费者调用到
3. **可靠性机制不可靠**: 非原子dequeue、PostgreSQL幂等回退、Nack Header三处可靠性缺陷叠加

---

## 8. 附录

### 8.1 参考业界框架

| 框架 | 版本 | 参考特性 |
|------|------|----------|
| NServiceBus | 8.x | Outbox + SLR + Audit + 幂等 |
| Axon Framework | 4.9 | EventStore + Upcaster + TrackingToken |
| Eventuate | 2.x | 幂等合约 + 处理进度 + 顺序保证 |

### 8.2 相关SISYS文档

| 文档 | 位置 | 说明 |
|------|------|------|
| architecture.md | `docs/architecture/` | 主架构文档（ADR-003、事件流、监听器映射） |
| or.md | `docs/architecture/` | 操作规则（事件驱动约束、Schema版本要求） |
| sisys-uni-dual-channel-eventbus-design.md | `docs/architecture/` | 双通道EventBus详细设计（v2.5） |
| epics_v1.0.md | `_bmad-output/planning-artifacts/` | Epic/Story定义 |
| sprint-status.yaml | `_bmad-output/implementation-artifacts/` | Sprint状态 |

### 8.3 验收测试清单

**Phase 1验收**:
- [ ] 所有35+现有测试通过
- [ ] Architecture约束测试通过（Domain零依赖）
- [ ] DeadLetterQueue单一Protocol定义
- [ ] EventRegistry已移除，仅DomainEvent._registry
- [ ] 所有事件类型通过`__init_subclass__`自动注册
- [ ] OutboxRepository Protocol为async签名
- [ ] Poller不访问任何Repository私有方法
- [ ] EventBusFactory无类级别可变状态

**Phase 2验收**:
- [ ] RedisRetryQueue并发dequeue测试通过
- [ ] DualIdempotencyChecker PostgreSQL回退可靠
- [ ] RabbitMQConsumer不再修改消息Header
- [ ] Composition Root与Factory共享连接池
- [ ] event_channels.yaml生效
- [ ] 12个领域事件全部有通道映射
- [ ] EventUpcaster机制测试覆盖≥85%
- [ ] Processing Token断点续传测试通过
- [ ] ChannelRouter/Metrics并发测试通过

**Phase 3验收**:
- [ ] P95延迟实测<30ms
- [ ] 吞吐实测>2000 events/sec
- [ ] 健康检查端点可用
- [ ] Grafana仪表板部署
- [ ] 真实Redis/RabbitMQ端到端测试通过

---

**报告撰写**: Claude Code
**审核状态**: 待用户审核确认
