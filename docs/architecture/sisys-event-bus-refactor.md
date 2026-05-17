# 事件总线子系统重构详细设计与执行方案

> 版本: 1.1 | 状态: 审查修订中
> 基于: `sisys-event-bus-research-report.md` v2.0
> 第1轮审查：修正AuditEvent注册描述、PostgresDeadLetterQueue架构缺陷、channel调用者清理、DualIdempotencyChecker严重BUG标注、save()同步实现细节

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
- [ ] **修改** `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py`：当前未继承任何Protocol/ABC接口（架构缺陷），改为实现Domain层 `DeadLetterQueue` Protocol，import from `src.domain.events.listener`
- [ ] **修改** `src/infrastructure/messaging/outbox/dead_letter_queue.py`：删除 `DeadLetterQueue` ABC 和 `InMemoryDeadLetterQueue`，改为 re-export from Domain层
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_listener.py`：更新 import 路径
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_consumer.py`：更新 import 路径
- [ ] **验证**：所有引用DeadLetterQueue的文件使用统一import，`grep -r "DeadLetterQueue" src/` 无重复定义

**关键文件**：
- `src/domain/events/listener.py` (L119-169, 保留)
- `src/infrastructure/messaging/outbox/dead_letter_queue.py` (全文, 清理)
- `src/infrastructure/messaging/outbox/postgres_dead_letter_queue.py` (import路径)
- `tests/unit/infrastructure/messaging/outbox/test_dead_letter_queue.py` (import更新)

#### 任务 1.2: 移除EventRegistry，统一到DomainEvent._registry
- [ ] **修改** `src/infrastructure/messaging/adapters/event_outbox_adapter.py`：移除 `EventRegistry` 类，`get()` 改为调用 `DomainEvent._registry.get()`
- [ ] **修改** `src/infrastructure/messaging/adapters/event_outbox_adapter.py`：`EventOutboxAdapter.to_domain_event()` 使用 `DomainEvent._registry` 查找事件类
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_consumer.py`：更新事件查找逻辑
- [ ] **验证**：`grep -r "EventRegistry" src/` 仅在注释或删除标记中出现

**关键文件**：
- `src/infrastructure/messaging/adapters/event_outbox_adapter.py` (EventRegistry类, 删除)
- `src/infrastructure/messaging/rabbitmq_consumer.py` (EventRegistry引用)
- `tests/unit/infrastructure/messaging/test_event_outbox_adapter.py` (更新)

#### 任务 1.3: 统一事件注册方式为__init_subclass__自动注册
- [ ] **修改** 4个使用 `__post_init__` + `object.__setattr__` 的事件类（AutoTriggered, AutoRouted, MemoryChanged, AutoExecuted），改为 `event_type: str = field(default="X", init=False)` 模式
- [ ] **修改** AuditEvent：当前通过 `event_type: str = "AuditEvent"` 字段默认值（init=True）设定类型，改为 `event_type: str = field(default="AuditEvent", init=False)` 模式
- [ ] **删除** 5个事件文件底部的手动注册行（`DomainEvent._registry["X"] = X` 或 `DomainEvent.register("X", X)`）
- [ ] **删除** 4个事件类 `__post_init__` 中的 `object.__setattr__(self, "event_type", "X")` 行（AuditEvent除外，其`__post_init__`仅做验证）
- [ ] **验证**：所有事件类 `from_dict` 反序列化测试通过，`DomainEvent._registry` 包含所有事件类型

**关键文件**：
- `src/domain/events/auto_trigger_events.py` (L49 __post_init__ + L57 手动注册)
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
- [ ] **修改** `src/infrastructure/messaging/outbox/outbox_repository.py`：移除 `get_unpublished`, `mark_published`, `mark_failed` 的同步stub（抛NotImplementedError），公共async方法成为Protocol实现；`save()` 当前有sync实现（session.add是同步操作），需改为async版本
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_event_bus.py`：`publish()` 中 `outbox_repo.save()` 加 `await`
- [ ] **验证**：`mypy src/domain/ports/outbox.py` 通过，所有使用OutboxRepository的代码适配async

**关键文件**：
- `src/domain/ports/outbox.py` (L30,37,47,54 签名改为async)
- `src/infrastructure/messaging/outbox/inmemory_outbox.py` (方法加async)
- `src/infrastructure/messaging/outbox/outbox_repository.py` (移除sync stub)
- `src/infrastructure/messaging/rabbitmq_event_bus.py` (save加await)

#### 任务 2.2: InMemoryEventBus兼容EventPublisher Protocol
- [ ] **修改** `src/infrastructure/messaging/inmemory_event_bus.py`：新增 `async publish(event, channel=None) -> PublishResult` 方法，兼容 `EventPublisher` Protocol
- [ ] **保留** 同步 `publish` 方法供 `InMemoryEventPublisher` Protocol 使用（向后兼容测试）
- [ ] **验证**：`isinstance(InMemoryEventBus(), EventPublisher)` 返回 True

**关键文件**：
- `src/infrastructure/messaging/inmemory_event_bus.py`
- `src/domain/ports/event_publisher.py` (InMemoryEventPublisher Protocol 保留)

#### 任务 2.3: AsyncOutboxPoller改用公共接口
- [ ] **前置**：依赖任务2.1完成（OutboxRepository Protocol已async）
- [ ] **修改** `src/infrastructure/messaging/outbox/outbox_processor.py`：
  - `poll_once()` 调用 `self._repo.get_unpublished(limit)` 替代 `_get_unpublished_entities()`
  - 调用 `self._repo.mark_published(event_id)` 替代 `_mark_published_entity()`
  - 调用 `self._repo.mark_failed(event_id, error)` 替代 `_mark_failed_entity()`
- [ ] **修改** OutboxEntity/DomainEvent 转换逻辑：Poller内部处理OutboxEntity→DomainEvent转换（当前已在做，只是通过私有方法绕过）
- [ ] **修改** `outbox_repository.py` 和 `inmemory_outbox.py`：公共async方法返回DomainEvent（而非OutboxEntity），Poller不再需要知道OutboxEntity
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
- [ ] **同步修改** 所有实现 `EventPublisher` 的类：`RedisEventBus.publish()`（L49，直接覆盖channel参数）、`RabbitMQEventBus.publish()`
- [ ] **清理** 传入channel值的调用者：
  - `src/domain/services/auto_trigger_service.py:159` — `channel="rt:AutoTriggered"`
  - `src/domain/services/auto_route_service.py:148` — `channel="rt:AutoRouted"`
  - `src/application/event_handlers/auto_execute_completed_handler.py:124` — `channel=channel`
  - `src/application/event_handlers/auto_route_handler.py:113` — `channel=channel or "rt:AutoRouted"`
- [ ] **验证**：所有调用改为 `publish(event)`，`grep "channel=" src/ --include="*.py" | grep publish` 无channel传参

**关键文件**：
- `src/domain/ports/event_publisher.py` (L33)
- `src/infrastructure/messaging/dual_channel_event_bus.py` (L53)
- `src/infrastructure/messaging/redis_event_bus.py` (publish签名)
- `src/infrastructure/messaging/rabbitmq_event_bus.py` (publish签名)

#### 任务 3.2: AsyncOutboxPoller注入ChannelRouter替代硬编码路由键
- [ ] **修改** `src/infrastructure/messaging/outbox/outbox_processor.py`：
  - `__init__` 新增 `router: ChannelRouter` 参数
  - `poll_once()` 中 `routing_key` 改为 `self._router.get_rabbitmq_routing_key(entity.event_type)`
  - 默认值 `f"sisys.events.reliable.{entity.event_type}"` 作为 router 返回 None 时的 fallback
- [ ] **修改** `src/infrastructure/messaging/event_bus_factory.py`：`create_dual_channel_bus()` 传递共享 router 给 Poller
- [ ] **验证**：Poller使用ChannelRouter解析路由键，`grep "sisys.events.reliable" outbox_processor.py` 仅出现在fallback中

**关键文件**：
- `src/infrastructure/messaging/outbox/outbox_processor.py` (硬编码路由键)
- `src/infrastructure/messaging/event_bus_factory.py` (工厂传参)

#### 任务 3.3: EventBusFactory去除类级别可变状态
- [ ] **修改** `src/infrastructure/messaging/event_bus_factory.py`：
  - 移除 `_instance: ClassVar` 和 `_poller: ClassVar` 类属性
  - `configure_event_bus()`, `get_event_bus()`, `get_poller()` 改为模块级函数，使用模块级变量
  - 或改为由Composition Root管理生命周期，Factory仅提供 `create_*` 方法
- [ ] **修改** 测试中直接修改 `EventBusFactory._instance = None` 的代码：改用 `reset_event_bus()` 或 fixture
- [ ] **验证**：`EventBusFactory` 无类级别可变状态，测试间无共享状态污染

**关键文件**：
- `src/infrastructure/messaging/event_bus_factory.py` (L68-69 类属性)
- `tests/unit/infrastructure/messaging/test_event_bus_factory.py` (清理类属性操作)

#### 任务 3.4: 统一Composition Root与Factory
- [ ] **修改** `src/composition_root.py` L446-511：
  - 使用 `EventBusFactory` 创建组件（而非手动lambda创建独立实例）
  - `router` → `EventBusFactory` 共享实例
  - `event_publisher` → 工厂 `create_dual_channel_bus()` 返回的bus
  - 注册 `AsyncOutboxPoller` 到DI容器
  - 修复 `outbox_repo` 生命周期：从SCOPED改为SINGLETON（或由UoW管理scope）
- [ ] **修改** `DualChannelEventBus` 字符串路径注册改为lambda工厂
- [ ] **注册** `EventSubscriber` 端口 → `DualChannelEventBus` 实现
- [ ] **验证**：`bootstrap()` 后 `resolve("event_publisher")` 返回 `DualChannelEventBus` 实例，所有子组件共享router和连接

**关键文件**：
- `src/composition_root.py` (L446-511)
- `src/infrastructure/messaging/event_bus_factory.py`

---

### Phase 4: 可靠性修复（P2）

#### 任务 4.1: RedisRetryQueue原子dequeue
- [ ] **修改** `src/infrastructure/messaging/retry/redis_retry_queue.py`：
  - `dequeue()` 改用 Lua 脚本实现原子 ZRANGEBYSCORE + ZREM
  - 或使用 Redis 5.0+ `ZPOPMIN` 命令
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

#### 任务 4.3: RabbitMQConsumer重试改用RedisRetryQueue
- [ ] **修改** `src/infrastructure/messaging/rabbitmq_consumer.py`：
  - `_handle_failure()` 不再修改 `message.headers["x-retry-count"]`
  - 不再使用 `nack(requeue=True)` 做重试
  - 改为：NACK（不requeue），将事件enroll到 `RedisRetryQueue`，由延迟重试机制处理
  - 超过最大重试次数 → DLQ
- [ ] **验证**：消费者重试通过RedisRetryQueue而非RabbitMQ requeue

**关键文件**：
- `src/infrastructure/messaging/rabbitmq_consumer.py` (L200+ _handle_failure)

#### 任务 4.4: 线程安全修复
- [ ] **修改** `src/infrastructure/messaging/channel_router.py`：`_mappings` 和 `_overrides` 操作加 `asyncio.Lock`（或改为不可变dict + copy-on-write）
- [ ] **修改** `src/infrastructure/messaging/redis_publisher.py`：`_get_pool()` 使用已有的 `_pool_lock`
- [ ] **修改** `src/infrastructure/monitoring/event_metrics.py`：计数器加 `threading.Lock` 或 `asyncio.Lock`
- [ ] **验证**：并发测试通过

**关键文件**：
- `src/infrastructure/messaging/channel_router.py` (_mappings/_overrides)
- `src/infrastructure/messaging/redis_publisher.py` (_get_pool, _pool_lock)
- `src/infrastructure/monitoring/event_metrics.py` (计数器)

---

### Phase 5: 补全与清理（P2-P3）

#### 任务 5.1: 补全12个事件的DEFAULT_MAPPINGS
- [ ] **修改** `src/infrastructure/messaging/channel_router.py` DEFAULT_MAPPINGS：补全缺失的6个事件（ToolExecuted, AgentDecided, CheckpointRecovered, CorrectionApproved, StrategicDeviationWarning, RoutingDecided）
- [ ] **同步修改** `config/event_channels.yaml`
- [ ] **验证**：所有DomainEvent子类均有通道映射

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
- [ ] **修改** `EventBusConfigLoader.from_default_path()`：方法名改为 `create()`，更准确表达语义
- [ ] **验证**：无遗留 `_new.py` 文件，无误导命名

**关键文件**：
- `tests/unit/infrastructure/messaging/test_redis_event_bus.py` (删除)
- `tests/unit/infrastructure/messaging/test_redis_event_bus_new.py` (重命名)
- `tests/unit/infrastructure/messaging/test_rabbitmq_event_bus.py` (删除)
- `tests/unit/infrastructure/messaging/test_rabbitmq_event_bus_new.py` (重命名)
- `src/infrastructure/messaging/message_serializer.py` (重命名)
- `src/infrastructure/messaging/event_bus_config_loader.py` (方法重命名)

#### 任务 5.4: EventSubscriber添加@runtime_checkable
- [ ] **修改** `src/application/ports/event_subscriber.py` L21：添加 `@runtime_checkable` 装饰器，与其他Port Protocol保持一致
- [ ] **验证**：`isinstance(RedisEventBus(), EventSubscriber)` 返回 True

**关键文件**：
- `src/application/ports/event_subscriber.py` (L21)

---

## 依赖关系图

```
Phase 1 (P0 重复定义) ← 无依赖，可并行
  1.1 DeadLetterQueue
  1.2 EventRegistry
  1.3 事件注册方式

Phase 2 (P1 契约修复) ← 依赖 Phase 1
  2.1 OutboxRepository async    ← 先做，2.3依赖它
  2.2 InMemoryEventBus兼容
  2.3 Poller公共接口           ← 依赖 2.1

Phase 3 (P1 设计缺陷) ← 依赖 Phase 2
  3.1 channel死参数
  3.2 Poller注入ChannelRouter
  3.3 Factory去类级别状态
  3.4 Composition Root统一    ← 依赖 3.2, 3.3

Phase 4 (P2 可靠性) ← 依赖 Phase 2
  4.1 RedisRetryQueue原子
  4.2 DualIdempotency修复
  4.3 Consumer重试改用Redis
  4.4 线程安全

Phase 5 (P2-P3 补全清理) ← 依赖 Phase 3
  5.1 补全事件映射
  5.2 YAML集成
  5.3 遗留清理
  5.4 runtime_checkable
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
