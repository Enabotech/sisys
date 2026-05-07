# SISYS 系统同步代码实现现状

**生成日期**: 2026-05-01
**分析范围**: `src/` 目录下所有同步相关代码
**目的**: 全面调研系统同步实现架构

---

## 1. 同步架构概述

SISYS 系统采用**双通道事件总线架构**，通过 `DualChannelEventBus` 实现实时(REALTIME)和可靠(RELIABLE)两种传输模式。

### 1.1 核心架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           应用层 (Application)                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │              SixLayerStorageCoordinator (六层存储协同)               │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         领域层 (Domain)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────────┐ │
│  │  DomainEvent │  │ OutboxRepo   │  │  EventListener / EventPublisher  │ │
│  └──────────────┘  └──────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      接口层 (Interfaces)                                 │
│  ┌───────────────────────┐    ┌───────────────────────────────────────┐ │
│  │    EventPublisher     │    │          EventSubscriber               │ │
│  │   (发布抽象端口)       │    │          (订阅抽象端口)                │ │
│  └───────────────────────┘    └───────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      基础设施层 (Infrastructure)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │              DualChannelEventBus (双通道事件总线入口)                 │ │
│  │   ├── RedisEventBus (REALTIME 实时通道)                              │ │
│  │   └── RabbitMQEventBus (RELIABLE 可靠通道 + Outbox 模式)             │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │
│  │ ChannelRouter  │  │OutboxProcessor│  │     RedisRetryQueue        │ │
│  │   (通道路由)    │  │  (发件箱轮询)  │  │     (延迟重试队列)          │ │
│  └────────────────┘  └────────────────┘  └────────────────────────────┘ │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────┐ │
│  │IdempotencyChecker│ │DeadLetterQueue│  │  EventStore (PostgreSQL)   │ │
│  │   (幂等性检查)   │  │  (死信队列)   │  │     (事件溯源存储)         │ │
│  └────────────────┘  └────────────────┘  └────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 双通道模式

| 通道类型 | 实现 | 用途 |
|----------|------|------|
| **REALTIME** | Redis Pub/Sub | 触发事件、路由决策完成等需要即时通知的场景 |
| **RELIABLE** | RabbitMQ + Outbox | 文档处理完成、记忆变更、审计事件等需要可靠传输的场景 |

---

## 2. 核心组件详解

### 2.1 领域层 (Domain Layer)

#### 2.1.1 DomainEvent 基类
**文件路径**: `src/domain/events/base.py`

核心标准化字段:
- `event_id`: UUID - 事件唯一标识
- `event_type`: str - 事件类型 discriminator
- `timestamp`: datetime - 事件发生时间
- `aggregate_id`: UUID - 聚合 ID
- `aggregate_type`: str - 聚合类型
- `version`: int - 版本号（乐观锁）
- `payload`: dict - 事件负载
- `correlation_id` / `causation_id`: 可追溯性字段

#### 2.1.2 OutboxRepository 接口
**文件路径**: `src/domain/repositories/outbox.py`

```python
class OutboxRepository(ABC):
    def save(self, event: DomainEvent) -> None: ...
    def get_unpublished(self, limit: int) -> list[DomainEvent]: ...
    def mark_published(self, event_id: UUID) -> None: ...
    def mark_failed(self, event_id: UUID, error: str) -> None: ...
```

#### 2.1.3 EventListener 接口
**文件路径**: `src/domain/events/listener.py`

提供两种事件监听器:
- `EventListener`: 同步事件监听器
- `EventListenerAsync`: 异步事件监听器

#### 2.1.4 PublishResult
**文件路径**: `src/domain/events/publish_result.py`

发布结果数据类，包含:
- `redis_success`: Redis 通道是否成功
- `outbox_saved`: 消息是否已存入 Outbox
- `redis_error` / `outbox_error`: 错误信息

---

### 2.2 基础设施层 (Infrastructure Layer)

#### 2.2.1 DualChannelEventBus
**文件路径**: `src/infrastructure/messaging/dual_channel_event_bus.py`

统一双通道事件总线入口，根据 `ChannelRouter` 推断 `DeliveryMode`:
- `REALTIME`: 路由到 `RedisEventBus` (Redis Pub/Sub)
- `RELIABLE`: 路由到 `RabbitMQEventBus` (Outbox 模式)

#### 2.2.2 ChannelRouter
**文件路径**: `src/infrastructure/messaging/channel_router.py`

通道路由器，管理事件类型到通道的映射。

**预定义映射**:
```python
DEFAULT_MAPPINGS = {
    "AutoTriggered": DeliveryMode.REALTIME,      # 触发事件，实时通知
    "AutoRouted": DeliveryMode.REALTIME,          # 路由决策完成
    "DocumentProcessed": DeliveryMode.RELIABLE,  # 文档处理完成
    "MemoryChanged": DeliveryMode.RELIABLE,       # 记忆变更
    "CheckpointReached": DeliveryMode.RELIABLE,  # 检查点到达
    "AuditEvent": DeliveryMode.RELIABLE,          # 审计事件
}
```

#### 2.2.3 Outbox 模式实现

**AsyncOutboxPoller**: `src/infrastructure/messaging/outbox/outbox_processor.py`

异步轮询 OutboxEntity，发布至 RabbitMQ:
- `poll_once()`: 轮询一次并发布待处理事件
- `run()`: 启动轮询循环
- 使用 `asyncio.Semaphore` 控制并发

**InMemoryOutboxRepository**: `src/infrastructure/messaging/outbox/inmemory_outbox.py`

内存发件箱仓储实现（MVP 阶段使用），非线程安全。

**PostgreSQLOutboxRepository**: `src/infrastructure/messaging/outbox/outbox_repository.py`

PostgreSQL 持久化发件箱仓储实现。

#### 2.2.4 EventStore (事件溯源)
**文件路径**: `src/infrastructure/messaging/event_store.py`

PostgreSQL 事件存储实现，支持:
- `append()`: 追加事件（带乐观锁版本检查）
- `get_events()`: 获取聚合的所有事件
- `get_events_by_type()`: 按事件类型和时间范围查询

#### 2.2.5 重试机制

**RedisRetryQueue**: `src/infrastructure/messaging/retry/redis_retry_queue.py`

使用 Redis ZSET 实现延迟重试调度:
- 失败事件进入 ZSET，score 为重试时间戳
- 轮询器检查到期事件进行重试
- 避免 nack(requeue=True) 造成的消息饥饿问题

**RetryPolicy**: `src/infrastructure/messaging/retry/retry_policy.py`

完整指数退避 + jitter 防止惊群效应:
```python
delay = min(base * 2^retry_count * jitter, max)
# jitter 范围: [0.5, 1.5]
```

#### 2.2.6 幂等性检查

**IdempotencyChecker**: `src/infrastructure/messaging/retry/checker.py`

基于 Redis SET NX 原子操作实现事件处理幂等性保证，TTL 默认 7 天。

**DualIdempotencyChecker**: `src/infrastructure/messaging/retry/dual_idempotency_checker.py`

Redis + PostgreSQL 双写幂等性检查器:
- Redis SET NX 提供高性能检查
- PostgreSQL 记录提供持久化保证
- Redis 故障时降级至 PostgreSQL

#### 2.2.7 死信队列

**PostgresDeadLetterQueue**: `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py`

基于 PostgreSQL 的持久化死信队列:
- 入队/出队（FIFO）
- 状态管理（pending/processed）
- 人工干预支持

---

### 2.3 接口层 (Interfaces Layer)

#### 2.3.1 EventPublisher
**文件路径**: `src/interfaces/event_publisher.py`

事件发布抽象端口，定义 `publish()` 方法。

#### 2.3.2 EventSubscriber
**文件路径**: `src/interfaces/event_subscriber.py`

事件订阅抽象端口，定义:
- `subscribe()`: 同步事件处理器
- `subscribe_async()`: 异步事件处理器
- `start()` / `close()`: 生命周期管理

---

### 2.4 应用层 (Application Layer)

#### 2.4.1 SixLayerStorageCoordinator
**文件路径**: `src/application/services/six_layer_storage_coordinator.py`

六层存储协同服务，协调 L0-L5 各层存储的读写:
- L0: FileMemoryAdapter
- L1: RedisMemoryCache
- L2: MemoryMetadataRepository + MemoryChangeHistoryRepository
- L3: QdrantVectorStorage
- L4: MinIORepository
- L5: Neo4jGraphStorage

---

## 3. 同步流程分析

### 3.1 事件发布流程 (RELIABLE 模式)

```
应用层调用 EventPublisher.publish(event)
         │
         ▼
DualChannelEventBus.publish(event)
         │
         ▼
ChannelRouter.get_delivery_mode(event_type)
         │
         ▼ (RELIABLE 模式)
RabbitMQEventBus.publish(event)
         │
         ▼
OutboxRepository.save(event)  ← 与业务操作同事务
         │
         ▼
AsyncOutboxPoller.run()  ← 后台轮询
         │
         ├── 读取 pending 事件
         │
         ├── 发布到 RabbitMQ
         │
         └── 标记为 published/failed
```

### 3.2 事件订阅/消费流程

```
RabbitMQConsumer 接收消息
         │
         ├── 反序列化 JSON → DomainEvent
         │
         ├── 幂等性检查 (IdempotencyChecker)
         │
         ├── 执行处理器 (handler)
         │
         ├── 成功 → ACK
         │
         └── 失败 → 重试或死信
                  │
                  ├── RetryPolicy.should_retry()
                  │
                  ├── 重试次数 < max → NACK requeue=True
                  │
                  └── 超过 max → DeadLetterQueue
```

### 3.3 MemoryChanged 事件处理流程

**文件路径**: `src/application/event_handlers/memory_changed_listener.py`

```
MemoryChanged 事件触发
         │
         ▼
1. L1 Redis 缓存失效（同步，立即）
   保证"上下文≠缓存"公理
         │
         ▼
2. L2 PostgreSQL 写入
   - metadata_repository.upsert()
   - history_repository.append()
         │
         ▼
3. L3 Qdrant 向量（按需，内容>500 tokens）
         │
         ▼
4. L5 Neo4j 图谱（按需，EntityExtractor）
```

---

## 4. 状态管理

### 4.1 OutboxEntity 状态机

```
pending → published  (发布成功)
pending → failed     (发布失败，可重试)
failed  → pending    (重试)
failed  → archived   (终态，超过最大重试次数)
```

### 4.2 DeadLetterQueue 条目状态

```
pending → processed
```

---

## 5. 错误处理机制

### 5.1 多层重试策略

1. **指数退避 + Jitter**: `delay = min(base * 2^retry_count * jitter, max)`
2. **RedisRetryQueue**: ZSET 延迟重试调度
3. **RabbitMQ NACK requeue**: 消息重新入队

### 5.2 幂等性保证

- `IdempotencyChecker`: Redis SET NX 原子操作
- `DualIdempotencyChecker`: Redis + PostgreSQL 双写

### 5.3 死信处理

- `PostgresDeadLetterQueue`: 持久化存储
- 支持人工干预和状态查询

---

## 6. 关键文件清单

| 层级 | 文件路径 | 职责 |
|------|----------|------|
| **Domain** | `src/domain/events/base.py` | 领域事件基类 |
| | `src/domain/events/publish_result.py` | 发布结果数据类 |
| | `src/domain/events/listener.py` | 事件监听器接口 |
| | `src/domain/repositories/outbox.py` | Outbox 仓储接口 |
| | `src/domain/events/memory_events.py` | MemoryChanged 事件定义 |
| **Application** | `src/application/services/six_layer_storage_coordinator.py` | 六层存储协同 |
| **Infrastructure** | `src/infrastructure/messaging/dual_channel_event_bus.py` | 双通道事件总线 |
| | `src/infrastructure/messaging/channel_router.py` | 通道路由器 |
| | `src/infrastructure/messaging/rabbitmq_event_bus.py` | RabbitMQ 事件总线 |
| | `src/infrastructure/messaging/redis_event_bus.py` | Redis 事件总线 |
| | `src/infrastructure/messaging/outbox/outbox_processor.py` | Outbox 轮询处理器 |
| | `src/infrastructure/messaging/outbox/inmemory_outbox.py` | 内存 Outbox 实现 |
| | `src/infrastructure/messaging/outbox/outbox_repository.py` | PostgreSQL Outbox 实现 |
| | `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py` | 死信队列 |
| | `src/infrastructure/messaging/event_store.py` | 事件溯源存储 |
| | `src/infrastructure/messaging/retry/redis_retry_queue.py` | 延迟重试队列 |
| | `src/infrastructure/messaging/retry/retry_policy.py` | 重试策略 |
| | `src/infrastructure/messaging/retry/checker.py` | 幂等性检查器 |
| | `src/infrastructure/messaging/retry/dual_idempotency_checker.py` | 双写幂等性检查器 |
| | `src/infrastructure/messaging/rabbitmq_consumer.py` | RabbitMQ 消费者 |
| | `src/infrastructure/messaging/adapters/event_outbox_adapter.py` | 事件转换器 |
| **Interfaces** | `src/interfaces/event_publisher.py` | 发布端口 |
| | `src/interfaces/event_subscriber.py` | 订阅端口 |
| | `src/application/event_handlers/memory_changed_listener.py` | MemoryChanged 监听器 |

---

## 7. 配置说明

通道映射在 `ChannelRouter.DEFAULT_MAPPINGS` 中定义，可通过 `ChannelRouter.set_override()` 运行时覆盖传输模式。

---

## 8. 相关文档

- [EventBus Unified Dual Channel Design](eventbus-unified-dual-channel-design.md)
- [Infrastructure Refactoring Plan](infrastructure-refactoring-plan.md)
