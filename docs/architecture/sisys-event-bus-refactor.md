# 事件总线子系统重构详细设计与执行方案

> 版本: 2.3 | 状态: 审查修订中
> 基于: `sisys-event-bus-research-report.md` v2.0
> 第1-5轮（第一批）：v1.0→v2.0，24处P0修正
> 第8轮（第二批）：message_serializer重命名遗漏4处import+测试文件重命名、Phase1受影响测试补2个、DualIdempotencyChecker测试断言适配、fallback路由键改mark_failed、EventRegistry.get() KeyError行为保持

## Context

基于 `sisys-event-bus-research-report.md` (v2.0) 的全面调研，事件总线子系统综合评分 7.5/10。核心问题：
- 3处重复定义（DeadLetterQueue、EventRegistry、事件注册方式）
- 1处Protocol契约违背（OutboxRepository同步/异步不匹配）
- 1处封装违背（AsyncOutboxPoller访问私有方法）
- Composition Root与EventBusFactory双轨创建、依赖注入缺陷
- 可靠性机制自身不可靠（非原子dequeue、PostgreSQL幂等回退）

**目标**：消除代码质量问题，使EventBus子系统为后续EPICS/STORY开发提供可靠EDA基础设施。

**约束**：严格六边形架构，Domain层零外部依赖。

---

## 设计规则

1. **六边形架构**：Domain层仅Python标准库，Port在Domain/Application层定义，Infrastructure层仅提供实现
2. **Protocol优先**：接口用 `typing.Protocol` + `@runtime_checkable`，不用ABC
3. **async一致性**：所有异步操作的Protocol签名必须为async，消除sync/async混用
4. **显式依赖**：构造函数注入，消除ContextVar隐式依赖（本阶段先标注，Phase 2处理）
5. **单一真实来源**：消除重复定义，每个概念只存在一处
6. **向后兼容**：重构不破坏现有EventHandler/UseCase的调用方式

---

## 执行步骤

### Phase 1: 消除重复定义（P0）

#### 任务 1.1: 统一DeadLetterQueue
- [ ] **设计**：Domain层 `listener.py` 保留 `DeadLetterQueue` Protocol + `InMemoryDeadLetterQueue`，删除Infrastructure层 `outbox/dead_letter_queue.py` 中的重复定义
- [ ] **前置决策**：当前 Domain 层 `DeadLetterQueue` Protocol 是同步签名，但 `PostgresDeadLetterQueue` 的 `enqueue`/`dequeue` 是 async 方法且返回值不同（4元素 vs 3元素 tuple）。必须在统一前决定 Protocol 签名方向：
  - **方案A（推荐）**：Protocol 改为 async 签名，`dequeue` 返回 `tuple[DomainEvent, str, int] | None`，PostgresDeadLetterQueue 调整返回值对齐（去掉 `DeadLetterQueueEntry`）
  - **方案B**：保持 Protocol 同步，PostgresDeadLetterQueue 仅作为独立实现不实现 Protocol（维持现状但补上类型注解）
- [ ] **修改** `src/domain/events/listener.py`：如果采用方案A，`enqueue`/`dequeue` 改为 async
- [ ] **修改** `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py`：改为实现Domain层 `DeadLetterQueue` Protocol，对齐返回值
- [ ] **修改** `src/infrastructure/messaging/outbox/dead_letter_queue.py`：删除 `DeadLetterQueue` ABC 和 `InMemoryDeadLetterQueue`，改为 re-export from Domain层
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_listener.py`：更新 import 路径
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_consumer.py`：更新 import 路径，`set_dead_letter_queue` 参数类型从 `Any` 改为 `DeadLetterQueue`
- [ ] **验证**：所有引用DeadLetterQueue的文件使用统一import，`grep -r "DeadLetterQueue" src/` 无重复定义

**关键文件**：
- `src/domain/events/listener.py` (L119-170, 保留)
- `src/infrastructure/messaging/outbox/dead_letter_queue.py` (全文, 清理)
- `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py` (import路径)
- `tests/unit/infrastructure/messaging/test_postgres_dead_letter_queue.py` (import更新)

#### 任务 1.2: 移除EventRegistry，统一到DomainEvent._registry
- [ ] **修改** `src/infrastructure/messaging/adapters/event_outbox_adapter.py`：移除 `EventRegistry` 类，`get()` 改为调用 `DomainEvent._registry.get()`
- [ ] **修改** `src/infrastructure/messaging/adapters/event_outbox_adapter.py`：`EventOutboxAdapter.to_domain_event()` L143 使用 `DomainEvent._registry` 查找事件类，替换 `EventRegistry.get(entity.event_type)`
- [ ] **修改** `src/infrastructure/messaging/adapters/sqlalchemy_event_outbox_adapter.py` L59：同步修改 `to_domain_event()` 中的事件查找逻辑
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_consumer.py`：更新事件查找逻辑，`EventRegistry.get(event_type)` 改为 `DomainEvent._registry[event_type]`（用 `[]` 访问保持 KeyError 行为，与原 `EventRegistry.get()` 抛异常一致）
- [ ] **验证**：`grep -r "EventRegistry" src/` 仅在注释或删除标记中出现

**关键文件**：
- `src/infrastructure/messaging/adapters/event_outbox_adapter.py` (EventRegistry类, 删除; L143 to_domain_event)
- `src/infrastructure/messaging/adapters/sqlalchemy_event_outbox_adapter.py` (L59 to_domain_event同步修改)
- `src/infrastructure/messaging/rabbitmq_consumer.py` (EventRegistry引用)
- `tests/unit/infrastructure/messaging/test_event_outbox_adapter.py` (更新)

#### 任务 1.3: 统一事件注册方式为__init_subclass__自动注册
- [ ] **修改** `src/domain/events/base.py` `from_dict` 方法（L228-243）：当前 L230 硬编码传入 `event_type=event_type`，对 `init=False` 字段会触发 TypeError。**必须同步修改**：
  ```python
  # 修复逻辑：仅当 event_type 字段的 init=True 时才传入
  event_type_field = next((f for f in fields(target_class) if f.name == "event_type"), None)
  init_kwargs = {"event_id": eid, "timestamp": ts, ...}  # 不含 event_type
  if event_type_field is None or event_type_field.init:
      init_kwargs["event_type"] = event_type
  return target_class(**init_kwargs, **extra_kwargs)
  ```
- [ ] **修改** 4个使用 `__post_init__` + `object.__setattr__` 的事件类（AutoTriggered, AutoRouted, MemoryChanged, AutoExecuted），改为 `event_type: str = field(default="X", init=False)` 模式
- [ ] **修改** AuditEvent：当前通过 `event_type: str = "AuditEvent"` 字段默认值（init=True）设定类型，改为 `event_type: str = field(default="AuditEvent", init=False)` 模式
- [ ] **删除** 5个事件文件底部的手动注册行（`DomainEvent._registry["X"] = X` 或 `DomainEvent.register("X", X)`）
- [ ] **删除** 4个事件类 `__post_init__` 中的 `object.__setattr__(self, "event_type", "X")` 行（AuditEvent除外，其`__post_init__`仅做验证）
- [ ] **验证**：所有事件类 `from_dict` 反序列化测试通过，`DomainEvent._registry` 包含所有事件类型（预期22个）
- [ ] **建议**：为 `DomainEvent._registry` 添加 `@classmethod reset_registry(cls)` 方法（仅用于测试），在 `tests/fixtures.py` 的 `reset_test_environment` 中调用

**关键文件**：
- `src/domain/events/base.py` (L228-243 from_dict, L230 event_type传参阻断点)
- `src/domain/events/auto_trigger_events.py` (L45 __post_init__ + L57 手动注册)
- `src/domain/events/auto_route_events.py` (L48 __post_init__ + L56 手动注册)
- `src/domain/events/memory_events.py` (L55 __post_init__ + L63 手动注册)
- `src/domain/events/auto_execute_events.py` (L51 __post_init__ + L60 手动注册)
- `src/domain/events/audit_events.py` (L142 手动register，event_type通过字段默认值设定)
- 参考正确实现：`src/domain/events/document_events.py` (自动注册模式)

---

### Phase 2: 修复Protocol契约（P1）

#### 任务 2.1: OutboxRepository Protocol改为async
- [ ] **修改** `src/domain/ports/outbox.py`：所有方法改为 `async`
  ```python
  # Before (sync)
  def save(self, event: DomainEvent) -> None: ...
  def get_unpublished(self, limit: int) -> list[DomainEvent]: ...
  def mark_published(self, event_id: UUID) -> None: ...
  def mark_failed(self, event_id: UUID, error: str) -> None: ...

  # After (async)
  async def save(self, event: DomainEvent) -> None: ...
  async def get_unpublished(self, limit: int) -> list[DomainEvent]: ...
  async def mark_published(self, event_id: UUID) -> None: ...
  async def mark_failed(self, event_id: UUID, error: str) -> None: ...
  ```
- [ ] **修改** `src/infrastructure/messaging/outbox/inmemory_outbox.py`：同步方法改为async，加 `asyncio.Lock` 保护
- [ ] **修改** `src/infrastructure/messaging/outbox/outbox_repository.py`：
  - 删除 `get_unpublished`(L59), `mark_published`(L85), `mark_failed`(L105) 的同步stub（抛NotImplementedError）
  - 将 `async_get_unpublished`/`async_mark_published`/`async_mark_failed` 重命名为对应Protocol方法名
  - `save()`(L50) 当前有sync实现（session.add是同步操作），改为async并加入 `await self._session.flush()` 确保写入
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_event_bus.py`：`publish()` 中 `outbox_repo.save()` 加 `await`
- [ ] **修改** `src/application/use_cases/document_processing.py` L63：`outbox_repo.save()` 在同步方法 `process_document` 中调用，改为async后该方法也必须改为 `async def`，所有调用者需同步适配
- [ ] **验证**：`mypy src/domain/ports/outbox.py` 通过，所有使用OutboxRepository的代码适配async

**关键文件**：
- `src/domain/ports/outbox.py` (L30,37,47,54 签名改为async)
- `src/infrastructure/messaging/outbox/inmemory_outbox.py` (方法加async)
- `src/infrastructure/messaging/outbox/outbox_repository.py` (移除sync stub)
- `src/infrastructure/messaging/rabbitmq_event_bus.py` (save加await)
- `src/application/use_cases/document_processing.py` (process_document同步→async)
- `tests/unit/application/use_cases/test_document_processing.py` (适配async)

#### 任务 2.2: InMemoryEventBus兼容EventPublisher Protocol
- [ ] **注意**：Python不支持同名方法sync/async区分（`def publish()` 和 `async def publish()` 是同一个方法名，后者覆盖前者），因此无法同时保留两个同名方法
- [ ] **方案**：将 `InMemoryEventBus` 继承关系从 `InMemoryEventPublisher` 改为 `EventPublisher`，`publish()` 改为 `async def publish(event) -> PublishResult`
- [ ] **废弃** `InMemoryEventPublisher` Protocol（同步版本），现有测试改用 `await bus.publish(event)`
- [ ] **前置**：此任务应在任务3.1（移除channel参数）之后执行，避免先加channel再删除
- [ ] **验证**：`isinstance(InMemoryEventBus(), EventPublisher)` 返回 True

**关键文件**：
- `src/infrastructure/messaging/inmemory_event_bus.py`
- `src/domain/ports/event_publisher.py` (废弃InMemoryEventPublisher Protocol)

#### 任务 2.3: AsyncOutboxPoller改用公共接口
- [ ] **前置**：依赖任务2.1完成（OutboxRepository Protocol已async）
- [ ] **修改** `src/infrastructure/messaging/outbox/outbox_processor.py`：
  - `poll_once()` 调用 `self._repo.get_unpublished(limit)` 替代 `_get_unpublished_entities()`
  - 调用 `self._repo.mark_published(event_id)` 替代 `_mark_published_entity()`
  - 调用 `self._repo.mark_failed(event_id, error)` 替代 `_mark_failed_entity()`
- [ ] **修改** OutboxEntity/DomainEvent 转换逻辑：Poller内部处理OutboxEntity→DomainEvent转换（当前已在做，只是通过私有方法绕过）
- [ ] **修改** `outbox_repository.py` 和 `inmemory_outbox.py`：公共async方法返回DomainEvent（而非OutboxEntity），Poller不再需要知道OutboxEntity
- [ ] **注意**：Poller运行时必须有活跃的session context（通过 `session_context()` 或等效机制包裹），因为公共方法通过 `self._session` property（ContextVar）获取session
- [ ] **验证**：Poller不包含任何 `_` 前缀方法调用，`grep "_repo\._" outbox_processor.py` 无结果

**关键文件**：
- `src/infrastructure/messaging/outbox/outbox_processor.py` (L59,73,76 私有→公共)
- `src/infrastructure/messaging/outbox/outbox_repository.py` (公共方法签名)
- `src/infrastructure/messaging/outbox/inmemory_outbox.py` (公共方法签名)

---

### Phase 3: 修复设计缺陷（P1）

#### 任务 3.1: DualChannelEventBus移除channel死参数
- [ ] **修改** `src/infrastructure/messaging/dual_channel_event_bus.py` L53：移除 `channel: str | None = None` 参数（方法体内完全未使用，路由由ChannelRouter决定）
- [ ] **同步修改** `src/domain/ports/event_publisher.py` L33：移除 `channel` 参数
- [ ] **同步修改** 所有实现 `EventPublisher` 的类：
  - `src/infrastructure/messaging/redis_event_bus.py` L49（移除channel参数，但方法体内仍需 `self._router.get_redis_channel(event.event_type)` 获取channel传给底层publisher——"移除channel"指公共接口，内部路由逻辑保留）
  - `src/infrastructure/messaging/redis_publisher.py` L66（底层publisher的channel参数保留，Redis Pub/Sub需要channel名）
  - `src/infrastructure/messaging/rabbitmq_event_bus.py` publish签名
- [ ] **清理** 内部方法签名：
  - `src/application/event_handlers/auto_execute_completed_handler.py` L112 `_publish(self, event, channel)` 方法签名
  - `src/application/event_handlers/auto_route_handler.py` L113 `_publish` 方法签名
- [ ] **清理** 传入channel值的调用者：
  - `src/domain/services/auto_trigger_service.py:159` — `channel="rt:AutoTriggered"`
  - `src/domain/services/auto_route_service.py:148` — `channel="rt:AutoRouted"`
  - `src/application/event_handlers/auto_execute_completed_handler.py:124` — `channel=channel`
  - `src/application/event_handlers/auto_route_handler.py:113` — `channel=channel or "rt:AutoRouted"`
- [ ] **验证**：所有调用改为 `publish(event)`，`grep "channel=" src/ --include="*.py" | grep publish` 无channel传参

**关键文件**：
- `src/domain/ports/event_publisher.py` (L33)
- `src/infrastructure/messaging/dual_channel_event_bus.py` (L53)
- `src/infrastructure/messaging/redis_event_bus.py` (L49 publish签名)
- `src/infrastructure/messaging/redis_publisher.py` (L66 publish签名)
- `src/infrastructure/messaging/rabbitmq_event_bus.py` (publish签名)
- `src/application/event_handlers/auto_execute_completed_handler.py` (L112 _publish签名)
- `src/application/event_handlers/auto_route_handler.py` (L101 _publish签名)

#### 任务 3.2: AsyncOutboxPoller注入ChannelRouter替代硬编码路由键
- [ ] **修改** `src/infrastructure/messaging/outbox/outbox_processor.py`：
  - `__init__` 新增 `router: ChannelRouter` 参数
  - `poll_once()` 中 `routing_key` 改为 `self._router.get_rabbitmq_routing_key(entity.event_type)`
  - 默认值 `f"sisys.events.reliable.{entity.event_type}"` 作为 router 返回 None 时的 fallback
  - **注意**：当 router 返回 None 时，Poller 应调用 `mark_failed(event_id, "No routing key mapping")` 并记录 warning，而非静默发布到可能无消费者的 fallback routing key
- [ ] **修改** `src/infrastructure/messaging/event_bus_factory.py`：`create_dual_channel_bus()` 传递共享 router 给 Poller
- [ ] **验证**：Poller使用ChannelRouter解析路由键，`grep "sisys.events.reliable" outbox_processor.py` 仅出现在fallback中

**关键文件**：
- `src/infrastructure/messaging/outbox/outbox_processor.py` (硬编码路由键)
- `src/infrastructure/messaging/event_bus_factory.py` (工厂传参)

#### 任务 3.3: EventBusFactory清理（死代码处理）
- [ ] **现状**：`EventBusFactory` 仅在测试中调用，生产代码（composition_root.py）直接通过 `register_port` 创建组件，Factory 为死代码
- [ ] **决策**：保留 Factory 作为测试辅助工具（提供 `create_*` 方法），但移除全局单例职责
- [ ] **修改** `src/infrastructure/messaging/event_bus_factory.py`：
  - 移除 `_instance: ClassVar` 和 `_poller: ClassVar` 类属性
  - 移除 `configure_event_bus()`, `get_event_bus()`, `get_poller()` 全局单例方法
  - 保留 `create_dual_channel_bus()` 等工厂方法供测试使用
- [ ] **修改** 测试中直接修改 `EventBusFactory._instance = None` 的代码：改用直接实例化或 fixture
- [ ] **验证**：`EventBusFactory` 无类级别可变状态，测试间无共享状态污染

**关键文件**：
- `src/infrastructure/messaging/event_bus_factory.py` (L68-69 类属性)
- `tests/unit/infrastructure/messaging/test_event_bus_factory.py` (清理类属性操作)

#### 任务 3.4: 修复Composition Root EventBus注册
- [ ] **现状**：Composition Root 当前直接通过 `register_port` 创建EventBus组件（不使用 EventBusFactory），字符串路径注册 DualChannelEventBus 已可行（`_auto_inject` 通过参数名 `redis_bus`/`rabbitmq_bus`/`router` 自动匹配注册名）
- [ ] **修改** `src/composition_root.py` L446-511：
  - 保持字符串路径注册 DualChannelEventBus（`_auto_inject` 参数名匹配已验证可行）
  - 修复 `outbox_repo` 生命周期：从SCOPED改为SINGLETON。此修改是安全的，因为 `PostgreSQLOutboxRepository._session` 是property，每次调用 `get_session()` 从ContextVar获取当前上下文的session，session隔离由UoW（middleware的 `session_context()`）管理
  - 确保 `redis_bus` 和 `rabbitmq_bus` 共享 `router` 实例（当前已通过 `resolver.resolve("router")` 共享）
- [ ] **注册** `EventSubscriber` 端口 → `DualChannelEventBus` 实现
- [ ] **注册** `AsyncOutboxPoller` 到DI容器
- [ ] **验证**：`bootstrap()` 后 `resolve("event_publisher")` 返回 `DualChannelEventBus` 实例，所有子组件共享router和连接

**关键文件**：
- `src/composition_root.py` (L446-511)
- `src/infrastructure/messaging/event_bus_factory.py`

---

### Phase 4: 可靠性修复（P2）

#### 任务 4.1: RedisRetryQueue原子dequeue
- [ ] **修改** `src/infrastructure/messaging/retry/redis_retry_queue.py` (L178-194)：
  - `dequeue()` 改用 Lua 脚本实现原子 ZRANGEBYSCORE + ZREM
  - **注意**：ZPOPMIN不适合此场景——ZPOPMIN按score最小值弹出，无法按 `score <= now` 做时间过滤，需要额外逻辑处理未到期事件重新入队
  - Lua 脚本思路：`ZRANGEBYSCORE key -inf now LIMIT 0 count` → `ZREM key members` 原子执行
- [ ] **新增** 并发dequeue测试：两个consumer同时dequeue不重复
- [ ] **验证**：并发测试通过

**关键文件**：
- `src/infrastructure/messaging/retry/redis_retry_queue.py` (dequeue方法)

#### 任务 4.2: DualIdempotencyChecker PostgreSQL回退修复（严重BUG）
- [ ] **修改** `src/infrastructure/messaging/retry/dual_idempotency_checker.py`：
  - **当前BUG**：`_try_acquire_postgresql()` 执行 `INSERT ... ON CONFLICT DO NOTHING` 后用 `fetchone()` 检查结果，但 `fetchone()` 对 `DO NOTHING` 总返回 `None`，导致PG回退路径始终返回 `False`（所有事件被错误标记为"已处理"）
  - **修复**：改用 `INSERT ... ON CONFLICT DO NOTHING RETURNING event_id`，根据返回值判断是否插入成功
- [ ] **验证**：PostgreSQL回退路径正确检测重复（首次返回True，重复返回False）

**关键文件**：
- `src/infrastructure/messaging/retry/dual_idempotency_checker.py` (L167-168 _try_acquire_postgresql, fetchone() BUG)
- `tests/unit/infrastructure/messaging/test_dual_idempotency_checker.py` (PG fallback断言需修改)
- `tests/acceptance/test_story_20_2_steps.py` (mock session返回值需适配RETURNING)

#### 任务 4.3: RabbitMQConsumer重试改用RedisRetryQueue
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_consumer.py` (L174-227 `_handle_failure`)：
  - **当前BUG**：`nack(requeue=True)` 不保留客户端对 `message.headers` 的修改——requeue后RabbitMQ重新投递原始消息，L204的 `message.headers["x-retry-count"] = ...` 修改无效，导致重试计数永远不递增、无限重试
  - **参考实现**：`RabbitMQEventListener` (`rabbitmq_listener.py`) 已使用 `RedisRetryQueue` 处理重试，可作为改造参考
  - **修改方案**：构造函数注入 `RedisRetryQueue`；`_handle_failure()` 改为 NACK（不requeue），将事件enroll到 `RedisRetryQueue`，由延迟重试机制处理
  - 超过最大重试次数 → DLQ
- [ ] **验证**：消费者重试通过RedisRetryQueue而非RabbitMQ requeue

**关键文件**：
- `src/infrastructure/messaging/rabbitmq_consumer.py` (L174-227 _handle_failure)
- `src/infrastructure/messaging/rabbitmq_listener.py` (参考实现)

#### 任务 4.4: 线程安全修复
- [ ] **修改** `src/infrastructure/messaging/channel_router.py`：`_mappings` 和 `_overrides` 的 `register()`/`set_override()` 改为不可变dict + copy-on-write（原子替换引用，无需Lock）
- [ ] **修改** `src/infrastructure/messaging/redis_publisher.py` (L52-64)：`_get_pool()` 当前是同步方法，但 `_pool_lock` (L50) 是 `asyncio.Lock`（需要 `async with`），导致锁是死代码。修改方案：将 `_get_pool()` 改为 `async` 方法，使用 `async with self._pool_lock`，所有调用处加 `await`
- [ ] **修改** `src/infrastructure/monitoring/event_metrics.py`：计数器 `+= 1` 操作加 `asyncio.Lock`（当前注释标注"线程安全计数器"但实际未实现）
- [ ] **验证**：并发测试通过

**关键文件**：
- `src/infrastructure/messaging/channel_router.py` (_mappings/_overrides)
- `src/infrastructure/messaging/redis_publisher.py` (_get_pool, _pool_lock)
- `src/infrastructure/monitoring/event_metrics.py` (计数器)

---

### Phase 5: 补全与清理（P2-P3）

#### 任务 5.1: 补全22个事件的DEFAULT_MAPPINGS
- [ ] **修改** `src/infrastructure/messaging/channel_router.py` DEFAULT_MAPPINGS：当前仅6个映射（AutoTriggered, AutoRouted, DocumentProcessed, MemoryChanged, CheckpointReached, AuditEvent），需补全16个缺失事件
- [ ] **缺失事件清单**（按领域分组，`delivery_mode` 分配规则：控制信号/瞬时/可丢失 → REALTIME；业务状态变更/合规审计 → RELIABLE）：
  - REALTIME（3个）：AutoExecuted（控制流完成）、HeartbeatTriggered（心跳信号）、RoutingDecided（路由决策）
  - RELIABLE（13个）：ToolExecuted、AgentDecided、CheckpointRecovered、IsolationLevelSwitched、CorrectionApproved、StrategicDeviationWarning、MFAChallengeIssuedEvent、IntrusionDetectedEvent、DataIntegrityViolationEvent、SensitiveDataDetected、CrossBorderTransferRequested、DataSovereigntyViolation、PIPLDataAccessRequested
- [ ] **同步修改** `config/event_channels.yaml`
- [ ] **验证**：所有22个DomainEvent子类均有通道映射

**关键文件**：
- `src/infrastructure/messaging/channel_router.py` (DEFAULT_MAPPINGS)
- `config/event_channels.yaml`

#### 任务 5.2: YAML配置集成
- [ ] **修改** `src/composition_root.py`：在EventBus相关注册中调用 `EventBusConfigLoader.load()`，YAML配置覆盖DEFAULT_MAPPINGS
- [ ] **验证**：修改 `event_channels.yaml` 后重启，ChannelRouter使用YAML中的配置

**关键文件**：
- `src/composition_root.py`
- `src/infrastructure/messaging/event_bus_config_loader.py`

#### 任务 5.3: 清理遗留文件和命名
- [ ] **删除** 遗留测试文件：`test_redis_event_bus.py`（旧版，`test_redis_event_bus_new.py` 为当前版本）
- [ ] **删除** 遗留测试文件：`test_rabbitmq_event_bus.py`（旧版，`test_rabbitmq_event_bus_new.py` 为当前版本）
- [ ] **重命名** `_new.py` 测试文件去掉 `_new` 后缀
- [ ] **修改** `src/infrastructure/messaging/message_serializer.py`：重命名为 `inmemory_event_store.py`（当前名称误导）
- [ ] **同步修改** 4处import路径：
  - `tests/unit/infrastructure/messaging/test_message_serializer.py` → 重命名为 `test_inmemory_event_store.py`
  - `tests/unit/domain/events/test_event_store.py`
  - `tests/integration/conftest.py`
  - `tests/integration/test_test_utils.py`
- [ ] **修改** `EventBusConfigLoader.from_default_path()`：方法名改为 `create()`，更准确表达语义
- [ ] **验证**：无遗留 `_new.py` 文件，无误导命名

**关键文件**：
- `tests/unit/infrastructure/messaging/test_redis_event_bus.py` (删除)
- `tests/unit/infrastructure/messaging/test_redis_event_bus_new.py` (重命名)
- `tests/unit/infrastructure/messaging/test_rabbitmq_event_bus.py` (删除)
- `tests/unit/infrastructure/messaging/test_rabbitmq_event_bus_new.py` (重命名)
- `src/infrastructure/messaging/message_serializer.py` → `inmemory_event_store.py` (重命名)
- `tests/unit/infrastructure/messaging/test_message_serializer.py` → `test_inmemory_event_store.py` (重命名)
- `src/infrastructure/messaging/event_bus_config_loader.py` (方法重命名)

#### 任务 5.4: Protocol统一添加@runtime_checkable
- [ ] **修改** `src/application/ports/event_subscriber.py` L21：添加 `@runtime_checkable` 装饰器
- [ ] **修改** `src/domain/events/listener.py`：为 `EventListener`(L21)、`EventListenerAsync`(L99)、`DeadLetterQueue`(L119) 添加 `@runtime_checkable`
- [ ] **修改** `src/domain/events/event_store.py` L22：为 `EventStore` 添加 `@runtime_checkable`
- [ ] **验证**：所有Port Protocol均有 `@runtime_checkable` 装饰器

**关键文件**：
- `src/application/ports/event_subscriber.py` (L21)
- `src/domain/events/listener.py` (L21, L99, L119)
- `src/domain/events/event_store.py` (L22)

---

## 依赖关系图

```
Phase 1 (P0 重复定义) ← 无依赖，可并行
  1.1 DeadLetterQueue
  1.2 EventRegistry
  1.3 事件注册方式

Phase 2 (P1 契约修复) ← 依赖 Phase 1
  2.1 OutboxRepository async    ← 先做，2.3依赖它
  2.2 InMemoryEventBus兼容      ← 依赖 3.1（先移除channel再加async publish）
  2.3 Poller公共接口           ← 依赖 2.1

Phase 3 (P1 设计缺陷) ← 依赖 Phase 2.1（不依赖2.2/2.3，可与Phase 2后半段并行）
  3.1 channel死参数             ← 先做，2.2依赖此任务
  3.2 Poller注入ChannelRouter
  3.3 Factory去类级别状态       ← Factory为死代码（无生产调用者），低优先级
  3.4 Composition Root统一    ← 依赖 3.2, 3.3

Phase 4 (P2 可靠性) ← 仅依赖 Phase 2.1，可与 Phase 3 并行
  4.1 RedisRetryQueue原子
  4.2 DualIdempotency修复
  4.3 Consumer重试改用Redis
  4.4 线程安全

Phase 5 (P2-P3 补全清理) ← 仅 5.1 依赖 Phase 3.2
  5.1 补全事件映射             ← 依赖 3.2
  5.2 YAML集成               ← 无依赖，可提前
  5.3 遗留清理               ← 无依赖，可提前
  5.4 runtime_checkable       ← 无依赖，可提前到 Phase 1 并行
```

---

## 验证方案

### 每个任务完成后
1. `poetry run pytest tests/unit/domain/events/ -x` — Domain层事件测试
2. `poetry run pytest tests/unit/infrastructure/messaging/ -x` — Infrastructure层测试
3. `poetry run pytest tests/unit/architecture/ -x` — 六边形架构约束测试
4. `poetry run pytest tests/contracts/ -x` — Protocol契约测试

### Phase全部完成后
1. `poetry run pytest` — 全量测试套件通过
2. `poetry run mypy src/domain/ports/ src/domain/events/` — Domain层类型检查通过
3. `grep -r "_repo\._" src/infrastructure/messaging/` — 无私有方法跨类访问
4. `grep -r "DeadLetterQueue" src/` — 仅Domain层定义，Infrastructure层引用
5. `grep -r "EventRegistry" src/` — 仅在删除或注释中
6. `grep -r "NotImplementedError" src/infrastructure/messaging/outbox/` — 无NotImplementedError
7. 六边形架构约束验证：Domain层零外部依赖（现有AST测试覆盖）

### 集成验证
1. `poetry run pytest tests/integration/test_event_bus_integration.py -x` — 集成测试
2. `poetry run pytest tests/contracts/test_event_publisher_contract.py -x` — 契约测试
3. `poetry run python -c "from src.domain.events.base import DomainEvent; from src.domain.events import *; print(f'Registry: {len(DomainEvent._registry)} events'); assert len(DomainEvent._registry) >= 22"` — 事件注册完整性验证

---

## 测试影响面分析

### Phase 1 受影响测试
| 测试文件 | 影响原因 |
|----------|----------|
| `tests/unit/infrastructure/messaging/test_event_outbox_adapter.py` | EventRegistry移除，改为测试DomainEvent._registry |
| `tests/unit/infrastructure/messaging/test_outbox_entity.py` | registry_manual_register/reset测试需适配 |
| `tests/unit/domain/events/test_events_base.py` | from_dict修改影响反序列化测试 |
| `tests/unit/domain/events/test_event_serialization.py` | 事件注册方式变更影响roundtrip测试 |
| `tests/unit/infrastructure/messaging/test_idempotency_retry.py` | DLQ import路径从infrastructure改为domain |
| `tests/acceptance/test_story_1_3_steps.py` | InMemoryDeadLetterQueue import路径变更 |

### Phase 2 受影响测试
| 测试文件 | 影响原因 |
|----------|----------|
| `tests/unit/domain/ports/test_outbox_interface.py` | Protocol方法签名sync→async |
| `tests/unit/domain/ports/test_outbox_repository.py` | Protocol接口定义测试 |
| `tests/unit/infrastructure/messaging/outbox/test_inmemory_outbox.py` | 同步方法→async |
| `tests/unit/infrastructure/messaging/test_postgresql_outbox_repository.py` | 适配async签名 |
| `tests/unit/infrastructure/messaging/test_outbox_pattern.py` | 私有方法→公共async方法 |
| `tests/unit/infrastructure/messaging/test_async_outbox_poller.py` | 私有方法调用→公共接口 |
| `tests/unit/infrastructure/messaging/test_rabbitmq_event_bus_new.py` | outbox_repo.save()加await |
| `tests/unit/application/use_cases/test_document_processing.py` | process_document同步→async |
| `tests/integration/test_layer_collaboration.py` | process_document调用链适配async |

### Phase 3 受影响测试
| 测试文件 | 影响原因 |
|----------|----------|
| `tests/contracts/test_event_publisher_contract.py` (L58) | channel参数移除 |
| `tests/unit/application/event_handlers/test_auto_route_handler.py` | _publish方法签名变更 |
| `tests/unit/application/event_handlers/test_auto_execute_completed_listener.py` | _publish方法签名变更 |
| `tests/unit/infrastructure/messaging/test_redis_event_bus.py` | publish签名channel参数移除 |
| `tests/acceptance/test_story_1_3_steps.py` | redis_publisher.publish(event, channel)调用 |
| `tests/unit/infrastructure/messaging/test_event_bus_factory.py` | Factory类属性清理 |
