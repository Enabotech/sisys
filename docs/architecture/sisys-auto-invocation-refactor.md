# SISYS 自主调用子系统重构设计

**文档版本:** v1.2
**生成时间:** 2026-05-21
**修订:** R1 修正 10 项（行号/路径/步骤编号）；R2 修正 10 项（DI lambda 语法/测试清单/语义变更/矛盾统一）
**基于:** sisys-auto-invocation-design.md v1.0 + Story 1.14a/b/c 代码全面调研 + 25 项问题分析
**状态:** 重构设计

---

## 1. 重构概述

### 1.1 背景

SISYS Story 1.14a（Trigger）/ 1.14b（Route）/ 1.14c（Execute）已完成自主调用三阶段管线的 MVP 实现。经多 Agent 并行调研（domain 层、application/infrastructure 层、测试层三个视角），共发现 **25 项** 设计问题，涵盖关键 Bug、架构违规、代码质量和风格优化四个等级。

### 1.2 目标

1. **修复关键 Bug**：DI 路径错误、双重发布、cosine_similarity 计算错误
2. **纯化领域层**：消除 domain 层对 Redis/Outbox 的知识依赖，迁移端口至正确位置
3. **完善 DI 注册**：使自主调用管线可通过 composition_root 完整启动
4. **增强类型安全**：消除 getattr 链和泛型 DomainEvent 参数
5. **统一配置体系**：消除死配置，统一 frozen 约束

### 1.3 范围

**包含：**
- 自主调用三阶段管线的 domain/application/infrastructure 层重构
- DI 注册完善
- 死代码清理
- 线程安全加固

**不包含：**
- UDMR 三层决策逻辑（Story 1.17）
- Prefect/LangGraph 引擎内部实现（Story 1.18a/b）
- 外部化记忆子系统（Story 1.15a/b）
- 沙箱从 Docker → gVisor 的迁移（V2+）

### 1.4 约束

| 约束 | 规则 |
|------|------|
| 六边形架构 | Domain 层零外部依赖（仅 Python 标准库） |
| Protocol 优先 | 接口用 `typing.Protocol` + `@runtime_checkable` |
| async 一致性 | 异步操作 Protocol 签名必须为 async |
| 事件不可变 | 所有 DomainEvent 均为 `frozen=True` dataclass |
| 单向依赖 | domain ← application ← interfaces ← infrastructure |
| 向后兼容 | 重构不得破坏 4190+ 现有测试 |
| 渐进重构 | 按 P0→P1→P2→P3 优先级分阶段执行 |

### 1.5 当前代码基线

| 指标 | 值 |
|------|-----|
| 总测试数 | 4190 passed, 38 skipped |
| Domain 层文件 | 16 个（events 3 + services 3 + ports 6 + entities 2 + value_objects 2） |
| Application 层文件 | 4 个（handlers 3 + services 1） |
| Infrastructure 层文件 | 10 个（routing 2 + sandbox 2 + storage 1 + scheduler 1 + config 3 + messaging 1） |

---

## 2. 问题清单

### 2.1 P0 关键 Bug（4 项）

#### P0-1：DI 注册路径与实际文件路径不匹配

**问题：** `composition_root.py` 中两个端口的 impl 路径指向不存在的目录。

| 端口名 | 注册路径 | 实际路径 |
|--------|---------|---------|
| `sandbox_executor` | `src.infrastructure.sandbox.docker_sandbox_adapter.DockerSandboxAdapter` | `src.infrastructure.external_services.sandbox.docker_sandbox_adapter.DockerSandboxAdapter` |
| `snapshot_repository` | `src.infrastructure.storage.redis_snapshot_store.RedisSnapshotStore` | `src.infrastructure.storage.redis.redis_snapshot_store.RedisSnapshotStore` |

**影响：** 运行时 DI 解析失败，端口无法实例化。

**修复方案：** 修正 composition_root.py 中的 impl 和 module 路径（两个参数均指向错误目录）。

**验证：** `Resolver().resolve("sandbox_executor")` 和 `Resolver().resolve("snapshot_repository")` 成功返回实例。

---

#### P0-2：AutoRouteHandler 双重发布 AutoRouted 事件

**问题：** `AutoRouteHandler.on_triggered()` 调用 `AutoRouteService.on_triggered_event()`，后者内部调用 `self._publish(routed)` 发布 `AutoRouted`。但 handler 随后又调用 `self._publish(routed)` 再次发布同一事件。

```
AutoRouteHandler.on_triggered(event)
  ├── service.on_triggered_event(event)  → 内部 _publish(routed)  ← 第 1 次发布
  └── self._publish(routed)              ← 第 2 次发布（重复！）
```

**涉及文件：**
- `src/application/event_handlers/auto_route_handler.py` 第 81-91 行（handler 发布）
- `src/domain/services/auto_route_service.py` 第 83 行（service 内部发布）

**影响：** 下游消费者收到重复路由事件，可能触发双重执行。注意：仅当 handler 被注入 publisher 时才发生实际双重发布（publisher=None 时 handler 侧为空操作），但代码结构上存在双重发布路径是设计缺陷。

**修复方案：** 从 `AutoRouteHandler` 中移除 `_publish` 方法及其调用。Service 层是唯一发布者。

**验证：** 发布 `AutoTriggered` 后，事件总线上仅出现 1 条 `AutoRouted`。

---

#### P0-3：自主调用管线组件未注册 DI

**问题：** 以下 8 个核心组件在 `composition_root.py` 中无注册：

| 组件 | 类型 | 位置 |
|------|------|------|
| `AutoTriggerService` | Domain Service | `src/domain/services/auto_trigger_service.py` |
| `AutoRouteService` | Domain Service | `src/domain/services/auto_route_service.py` |
| `AutoExecuteService` | Domain Service | `src/domain/services/auto_execute_service.py` |
| `AutoTriggerHandler` | Application Handler | `src/application/event_handlers/auto_trigger_handler.py` |
| `AutoRouteHandler` | Application Handler | `src/application/event_handlers/auto_route_handler.py` |
| `AutoExecuteCompletedHandler` | Application Handler | `src/application/event_handlers/auto_execute_completed_handler.py` |
| `HeartbeatScheduler` | Infrastructure Scheduler | `src/infrastructure/scheduler/heartbeat_scheduler.py` |
| `SessionNamespaceManager` | Infrastructure Service | `src/infrastructure/external_services/sandbox/session_namespace_manager.py` |

**影响：** 自主调用管线无法通过 DI 容器启动，必须手动装配。

**修复方案：** 在 composition_root.py 中添加完整注册（详见第 3.1 节）。注意：`auto_trigger_handler` 依赖 `event_listener` 端口，需确认该端口已注册或补充注册。

**注意：** domain service 和 handler 不是 Protocol 端口，使用 `register_port()` 注册它们是临时方案（与 P3-7 同一反模式）。理想方案是引入 `register_service()` 机制，但当前优先保证管线可启动。

**验证：** 通过 DI 容器可解析完整的管线组件链。

---

#### P0-4：SemanticRouter._cosine_similarity 计算错误

**问题：** `magnitude_a` 计算使用 `zip(a, b)` 截断到较短向量长度，当 `len(a) != len(b)` 时得到错误的模值。

```python
magnitude_a = math.sqrt(sum(x * x for x, _ in zip(a, b)))  # ← zip 截断！
magnitude_b = math.sqrt(sum(y * y for _, y in zip(a, b)))  # ← 同样截断
```

**涉及文件：** `src/infrastructure/routing/semantic_router.py` 第 203-204 行

**影响：** 不同长度的嵌入向量产生错误的相似度分数。注意：正常运行时所有向量来自同一嵌入模型（bge-m3, 1024 维），长度一致，bug 不触发。仅当候选项注册了不同维度的嵌入时才显现。

**修复方案：** 分别计算各向量的模值，不使用 zip：
```python
magnitude_a = math.sqrt(sum(x * x for x in a))
magnitude_b = math.sqrt(sum(y * y for y in b))
```

**验证：** 长度不同的向量返回正确相似度；现有 4190 测试不回归。

---

### 2.2 P1 架构违规（6 项）

#### P1-1：CheckpointSnapshot 含 Redis 特定序列化方法

**问题：** `CheckpointSnapshot.to_redis_hash()` 和 `from_redis_hash()` 是 Redis Hash 序列化逻辑，定义在 domain 实体上违反六边形架构。

**涉及文件：** `src/domain/entities/checkpoint_snapshot.py`

**修复方案：**
- 从 `CheckpointSnapshot` 移除 `to_redis_hash()` 和 `from_redis_hash()` 方法
- 在 `RedisSnapshotStore` 中创建 `_snapshot_to_hash()` / `_hash_to_snapshot()` 私有方法
- 更新 `RedisSnapshotStore.save()` 和 `load()` 使用新方法

**验证：** `CheckpointSnapshot` 不含任何 Redis 引用；RedisSnapshotStore 测试通过。

---

#### P1-2：PublishResult 含基础设施特定字段

**问题：** `PublishResult`（定义在 domain 层）包含 `redis_success`、`redis_error`、`outbox_saved`、`outbox_error` 字段。Domain 层不应知道 Redis 和 Outbox 的存在。

**涉及文件：** `src/domain/events/publish_result.py`

**修复方案：**
- 将 `PublishResult` 重构为通用通道结果：
  ```python
  @dataclass(frozen=True)
  class ChannelResult:
      channel_name: str       # "realtime" / "reliable"
      success: bool
      error: str | None = None

  @dataclass(frozen=True)
  class PublishResult:
      event_id: str
      results: tuple[ChannelResult, ...]
      @property is_success -> bool
      @property is_full_failure -> bool
      @property partial_error -> bool
  ```
- 在基础设施层各子总线中构造 `ChannelResult` 实例。实际构造站点有 2 个子总线（非 DualChannelEventBus 直接构造）：
  - `src/infrastructure/messaging/redis_event_bus.py` — RedisEventBus.publish() 构造 `ChannelResult("realtime", ...)`
  - `src/infrastructure/messaging/rabbitmq_event_bus.py` — RabbitMQEventBus.publish() 构造 `ChannelResult("reliable", ...)`
  - `src/infrastructure/messaging/inmemory_event_bus.py` — InMemoryEventBus.publish() 构造 `ChannelResult("inmemory", ...)`
  - `DualChannelEventBus` 不直接构造 PublishResult，透传子总线返回值

**语义变更注意：** 当前 `is_success` 语义为"任一通道成功即为成功"（`redis_success or outbox_saved`），新方案改为"全部通道成功才算成功"（`all(r.success for r in self.results)`）。需评估是否有消费者依赖旧语义。

**验证：** `PublishResult` 无 Redis/Outbox 引用；EventPublisher Protocol 测试通过。

---

#### P1-3：EventListener/DeadLetterQueue 定义在 events/ 而非 ports/

**问题：** `EventListener`、`EventListenerAsync`、`DeadLetterQueue` 三个 Protocol 定义在 `src/domain/events/listener.py` 而非 `src/domain/ports/`。所有其他端口（EventPublisher、HashRouterProtocol 等）均在 `domain/ports/`。

**涉及文件：** `src/domain/events/listener.py`

**修复方案：**
- 创建 `src/domain/ports/event_listener.py` — 包含 `EventListener` 和 `EventListenerAsync`
- 创建 `src/domain/ports/dead_letter_queue.py` — 包含 `DeadLetterQueue`
- `src/domain/events/listener.py` 保留 `InMemoryEventListener` 和 `InMemoryDeadLetterQueue` 具体实现（迁移至 infrastructure 层，见 P1-4）
- 更新所有导入引用

**验证：** `from src.domain.ports.event_listener import EventListener` 可用；架构测试通过。

---

#### P1-4：InMemoryEventListener/InMemoryDeadLetterQueue 在 domain 层

**问题：** `InMemoryEventListener` 和 `InMemoryDeadLetterQueue` 是具体实现类（非 Protocol），不应在 domain 层。

**涉及文件：** `src/domain/events/listener.py`

**修复方案：**
- 迁移至 `src/infrastructure/messaging/in_memory_event_listener.py`
- 迁移至 `src/infrastructure/messaging/in_memory_dead_letter_queue.py`
- 测试文件中的导入路径更新

**验证：** Domain 层仅包含 Protocol 接口，无具体实现类。

---

#### P1-5：AutoExecuteService.on_routed_event 接收泛型 DomainEvent

**问题：** `AutoExecuteService.on_routed_event(event: DomainEvent)` 接收泛型 `DomainEvent`，然后通过 6 次 `getattr` 提取 `session_id`、`task_context` 等字段（包括 logger 调用中的第 6 次）。对比 `AutoRouteService.on_triggered_event(event: AutoTriggered)` 使用具体类型。此外，`AutoRouted` 的 `trigger_event_type` 和 `trigger_event_id` 字段在 `on_routed_event` 中完全丢失（从未提取）。

```python
# AutoExecuteService — 不安全
async def on_routed_event(self, event: DomainEvent) -> AutoExecuted | None:
    session_id = getattr(event, "session_id", "")      # 无类型检查

# AutoRouteService — 安全
async def on_triggered_event(self, event: AutoTriggered) -> AutoRouted:
    session_id = event.session_id                       # 类型安全
```

**涉及文件：** `src/domain/services/auto_execute_service.py`

**修复方案：**
- 方法签名改为 `async def on_routed_event(self, event: AutoRouted) -> AutoExecuted | None`
- 将 `getattr(event, "field", "")` 替换为直接属性访问 `event.field`

**验证：** MyPy 类型检查通过；重构后测试通过。

---

#### P1-6：AutoTriggerContext.from_domain_event 脆弱的嵌套回退链

**问题：** `from_domain_event` 通过多层嵌套 `payload.get("session_id", payload.get("payload", {}).get("session_id", ...))` 提取 `session_id`，且硬编码 13 个允许的 context key（文档之前误记为 12）。此外存在 3 个附加问题：
1. 第 98 行的 `and k not in ("aggregate_id", "event_id", "event_type")` 过滤条件是死代码（这些 key 不在允许列表中）
2. `__post_init__` 也有 session_id 空值兜底逻辑，与 `from_domain_event` 的兜底重复
3. 嵌套 `payload.get("payload", {})` 回退需验证是否有调用者传入此结构

**涉及文件：** `src/domain/value_objects/auto_trigger_context.py`

**修复方案：**
- 简化 session_id 提取为最多 2 层回退
- 将允许的 context key 列表提取为类常量 `ALLOWED_CONTEXT_KEYS`
- 添加明确的 fallback 日志记录

**验证：** 现有 AutoTriggerContext 测试全部通过。

---

### 2.3 P2 代码质量（8 项）

#### P2-1：AutoExecuteConfig 未导出 + frozen 不一致

**问题：** `AutoExecuteConfig` 是 `frozen=True` dataclass，但 `AutoTriggerConfig` 和 `AutoRouteConfig` 不是。`AutoExecuteConfig` 未从 `src/infrastructure/config/__init__.py` 导出。

**修复方案：** 统一所有 config 为 `frozen=True`；在 `__init__.py` 中添加 `AutoExecuteConfig` 导出。

---

#### P2-2：AutoRouteConfig 死配置字段

**问题：** `AutoRouteConfig.semantic_threshold` 从环境变量加载但从未传递给任何服务或路由器。

**修复方案：** 将 `semantic_threshold` 传递给 `AutoRouteService` 或在 DI 注册中消费。`cache_ttl_seconds` 见 P2-8（移除）。

---

#### P2-3：RoutingDecisionLog 从未实例化

**问题：** `RoutingDecisionLog` 实体定义完整但 `AutoRouteService` 从不创建实例。路由审计追踪缺失。

**修复方案：** 在 `AutoRouteService._make_routing_decision()` 中创建 `RoutingDecisionLog` 实例，并通过新的 `RoutingDecisionLogRepository` 端口持久化。此为 Story 1.14b AC-3 的遗漏实现。

---

#### P2-4：InMemoryEventPublisher 废弃 Protocol

**问题：** `src/domain/ports/event_publisher.py` 中 `InMemoryEventPublisher` 标记废弃但未删除，且使用 sync 签名与 async `EventPublisher` 不一致。

**修复方案：** 删除 `InMemoryEventPublisher` Protocol 定义。

---

#### P2-5：AutoExecuteService 未从 `__init__.py` 导出

**问题：** `src/domain/services/__init__.py` 导出 `AutoTriggerService` 和 `AutoRouteService`，但未导出 `AutoExecuteService`。

**修复方案：** 在 `__init__.py` 中添加 `AutoExecuteService` 导出。

---

#### P2-6：AutoTriggerHandler 无界队列

**问题：** `AutoTriggerHandler._event_queue` 是无大小限制的 `queue.Queue`。在高负载下可能导致内存无限增长。

**修复方案：** 设置 `queue.Queue(maxsize=1000)` 作为背压机制。当队列满时，新事件记录警告并丢弃（fail-fast）。

---

#### P2-7：DockerSandboxAdapter 类级别可变状态

**问题：** `_running_containers: dict[str, bool] = {}` 是类变量，所有实例共享且非线程安全。

**修复方案：** 改为实例变量 `self._running_containers: dict[str, bool] = {}`。同步移除 `reset_all_containers` 类方法（测试改用实例级清理），或将其改为按测试 fixture 管理。

---

#### P2-8：SemanticRouter.cache_ttl_seconds 参数接受但从未使用

**问题：** 构造函数接受 `cache_ttl_seconds` 参数但实际仅使用 `MAX_CACHE_SIZE` 控制 LRU 淘汰，TTL 从未生效。

**修复方案：** 移除 `cache_ttl_seconds` 参数（当前 LRU 策略已足够），或实现基于 TTL 的过期清理。推荐前者（KISS）。

---

### 2.4 P3 风格优化（7 项）

#### P3-1：import time 在方法体内

**涉及文件：** `src/domain/services/auto_execute_service.py` 第 85 行

**修复：** 将 `import time` 移至模块顶部。

---

#### P3-2：惰性导入在 AutoExecuteCompletedHandler

**涉及文件：** `src/application/event_handlers/auto_execute_completed_handler.py`

**修复：** 将 `DocumentProcessed`、`ToolExecuted`、`AgentDecided` 移至模块顶部导入。若有循环依赖，用 `TYPE_CHECKING` 保护。

---

#### P3-3：f-string 在 logger 调用中

**涉及文件：** `src/application/event_handlers/auto_trigger_handler.py`

**修复：** 将 `logger.debug(f"Registered handler for {event_type}")` 改为 `logger.debug("Registered handler for event type: %s", event_type)`。

---

#### P3-4：SessionNamespaceManager 占位符 "now"

**涉及文件：** `src/infrastructure/external_services/sandbox/session_namespace_manager.py` 第 60 行

**修复：** 将 `"created_at": "now"` 改为 `"created_at": datetime.now(timezone.utc).isoformat()`。

---

#### P3-5：HashNode dataclass 从未使用

**涉及文件：** `src/infrastructure/routing/hash_router.py` 第 20-29 行

**修复：** 删除未使用的 `HashNode` dataclass。

---

#### P3-6：HeartbeatScheduler 绕过 DI 创建 Redis 连接池

**涉及文件：** `src/infrastructure/scheduler/heartbeat_scheduler.py`

**修复：** 接受注入的 Redis 连接配置或连接池，而非在内部自行创建。

---

#### P3-7：OrchestrationService 注册为 Port

**涉及文件：** `src/composition_root.py`

**修复：** 将 `OrchestrationService` 从 port 注册改为 service 注册（或移除 registration，改为在需要时直接构造）。

---

## 3. 重构方案详细设计

### 3.1 DI 管线装配

#### 3.1.1 完整注册清单

在 `src/composition_root.py` 中添加以下注册：

```python
# === Auto-Invocation Pipeline ===

# Domain Services
register_port(
    name="auto_trigger_service",
    version="v1.0.0",
    interface=AutoTriggerService,
    impl=lambda resolver: AutoTriggerService(
        publisher=resolver.resolve("event_publisher"),
    ),
    module="src.domain.services.auto_trigger_service",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

register_port(
    name="auto_route_service",
    version="v1.0.0",
    interface=AutoRouteService,
    impl=lambda resolver: AutoRouteService(
        publisher=resolver.resolve("event_publisher"),
        hash_router=resolver.resolve("hash_router"),
        semantic_router=resolver.resolve("semantic_router"),
    ),
    module="src.domain.services.auto_route_service",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

register_port(
    name="auto_execute_service",
    version="v1.0.0",
    interface=AutoExecuteService,
    impl=lambda resolver: AutoExecuteService(
        sandbox=resolver.resolve("sandbox_executor"),
        snapshot_repo=resolver.resolve("snapshot_repository"),
    ),
    module="src.domain.services.auto_execute_service",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

# Application Handlers
register_port(
    name="auto_trigger_handler",
    version="v1.0.0",
    interface=AutoTriggerHandler,
    impl=lambda resolver: AutoTriggerHandler(
        auto_trigger_service=resolver.resolve("auto_trigger_service"),
        event_listener=resolver.resolve("event_listener"),
    ),
    module="src.application.event_handlers.auto_trigger_handler",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

register_port(
    name="auto_route_handler",
    version="v1.0.0",
    interface=AutoRouteHandler,
    impl=lambda resolver: AutoRouteHandler(
        auto_route_service=resolver.resolve("auto_route_service"),
    ),
    module="src.application.event_handlers.auto_route_handler",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

register_port(
    name="auto_execute_completed_handler",
    version="v1.0.0",
    interface=AutoExecuteCompletedHandler,
    impl=lambda resolver: AutoExecuteCompletedHandler(
        publisher=resolver.resolve("event_publisher"),
    ),
    module="src.application.event_handlers.auto_execute_completed_handler",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

# Infrastructure Services
register_port(
    name="heartbeat_scheduler",
    version="v1.0.0",
    interface=HeartbeatScheduler,
    impl=lambda resolver: HeartbeatScheduler(
        redis_config=resolver.resolve("redis_connection_manager"),
    ),
    module="src.infrastructure.scheduler.heartbeat_scheduler",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)

register_port(
    name="session_namespace_manager",
    version="v1.0.0",
    interface=SessionNamespaceManager,
    impl=lambda resolver: SessionNamespaceManager(
        sandbox=resolver.resolve("sandbox_executor"),
    ),
    module="src.infrastructure.external_services.sandbox.session_namespace_manager",
    lifetime=Lifetime.SINGLETON,
    owner="auto-invocation-team",
)
```

> **前置依赖：** `auto_trigger_handler` 需要 `event_listener` 端口，当前该端口未在 composition_root.py 中注册。需先确认 `EventListener` Protocol（P1-3 迁移至 `domain/ports/` 后）的注册条目。若 P1-3 迁移时创建了 `src/domain/ports/event_listener.py`，则需同步添加：
> ```python
> register_port(
>     name="event_listener",
>     version="v1.0.0",
>     interface=EventListener,
>     impl=lambda resolver: InMemoryEventListener(),
>     module="src.infrastructure.messaging.in_memory_event_listener",
>     lifetime=Lifetime.SINGLETON,
>     owner="auto-invocation-team",
> )
> ```

#### 3.1.2 路径修正

```python
# 修正前（impl 和 module 均错误）
impl="src.infrastructure.sandbox.docker_sandbox_adapter.DockerSandboxAdapter"
module="src.infrastructure.sandbox.docker_sandbox_adapter"
impl="src.infrastructure.storage.redis_snapshot_store.RedisSnapshotStore"
module="src.infrastructure.storage.redis_snapshot_store"

# 修正后（impl 和 module 均指向实际路径）
impl="src.infrastructure.external_services.sandbox.docker_sandbox_adapter.DockerSandboxAdapter"
module="src.infrastructure.external_services.sandbox.docker_sandbox_adapter"
impl="src.infrastructure.storage.redis.redis_snapshot_store.RedisSnapshotStore"
module="src.infrastructure.storage.redis.redis_snapshot_store"
```

#### 3.1.3 启动序列

```
lifespan event
  └── resolve("auto_trigger_handler") → AutoTriggerHandler.__init__
        └── .register_handlers() → 启动后台线程 + 注册 12 种事件
  └── resolve("heartbeat_scheduler") → HeartbeatScheduler.start()
        └── asyncio.create_task(_heartbeat_loop)
```

---

### 3.2 事件发布链修复

#### 3.2.1 双重发布修复

**当前调用链（错误）：**
```
AutoRouteHandler.on_triggered(event)
  ├── routed = self._auto_route_service.on_triggered_event(event)
  │     └── service._publish(routed)    ← 发布 #1
  └── self._publish(routed)             ← 发布 #2（重复）
```

**修复后调用链：**
```
AutoRouteHandler.on_triggered(event)
  └── routed = self._auto_route_service.on_triggered_event(event)
        └── service._publish(routed)    ← 唯一发布点
```

**修改内容：**
- `AutoRouteHandler`：删除 `_publish` 方法；删除 `publisher` 构造参数；`on_triggered` 仅调用 service
- `AutoExecuteCompletedHandler`：保持不变（该 handler 无对应 domain service 承担发布职责）
- `AutoTriggerHandler`：保持不变（该 handler 通过 `_process_event` 调用 service，service 内部发布）

---

### 3.3 领域层纯化

#### 3.3.1 CheckpointSnapshot 序列化迁移

**修改前** (`checkpoint_snapshot.py`):
```python
class CheckpointSnapshot:
    def to_redis_hash(self) -> dict[str, str]: ...
    @classmethod
    def from_redis_hash(cls, data: dict[str, str]) -> CheckpointSnapshot: ...
```

**修改后** (`checkpoint_snapshot.py`):
```python
class CheckpointSnapshot:
    # 仅保留领域方法
    def with_updated_state(self, state_data: dict, new_version: int) -> CheckpointSnapshot: ...
```

**新增** (`redis_snapshot_store.py`):
```python
class RedisSnapshotStore:
    @staticmethod
    def _snapshot_to_hash(snapshot: CheckpointSnapshot) -> dict[str, str]:
        """将 CheckpointSnapshot 序列化为 Redis Hash 字段"""
        ...

    @staticmethod
    def _hash_to_snapshot(data: dict[str, str]) -> CheckpointSnapshot:
        """从 Redis Hash 字段反序列化为 CheckpointSnapshot"""
        ...
```

---

#### 3.3.2 PublishResult 抽象化

**修改前** (`publish_result.py`):
```python
@dataclass(frozen=True)
class PublishResult:
    event_id: str
    redis_success: bool
    redis_error: str | None
    outbox_saved: bool
    outbox_error: str | None
```

**修改后**:
```python
@dataclass(frozen=True)
class ChannelResult:
    """单个通道的发布结果"""
    channel_name: str       # "realtime" / "reliable"
    success: bool
    error: str | None = None

@dataclass(frozen=True)
class PublishResult:
    """事件发布结果（通道无关）"""
    event_id: str
    results: tuple[ChannelResult, ...] = ()

    @property
    def is_success(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def is_full_failure(self) -> bool:
        return len(self.results) > 0 and not any(r.success for r in self.results)

    @property
    def partial_error(self) -> bool:
        return not self.is_success and not self.is_full_failure
```

**子总线适配**（DualChannelEventBus 透传子总线返回值，不直接构造 PublishResult）：
```python
# RedisEventBus.publish() — 构造单通道结果
async def publish(self, event: DomainEvent) -> PublishResult:
    try:
        await self._publish_to_redis(event)
        return PublishResult(
            event_id=str(event.event_id),
            results=(ChannelResult("realtime", True),),
        )
    except Exception as e:
        return PublishResult(
            event_id=str(event.event_id),
            results=(ChannelResult("realtime", False, str(e)),),
        )

# RabbitMQEventBus.publish() — 构造单通道结果
async def publish(self, event: DomainEvent) -> PublishResult:
    try:
        await self._save_to_outbox(event)
        return PublishResult(
            event_id=str(event.event_id),
            results=(ChannelResult("reliable", True),),
        )
    except Exception as e:
        return PublishResult(
            event_id=str(event.event_id),
            results=(ChannelResult("reliable", False, str(e)),),
        )

# DualChannelEventBus.publish() — 透传子总线结果
async def publish(self, event: DomainEvent) -> PublishResult:
    mode = self._router.get_delivery_mode(event.event_type)
    if mode == DeliveryMode.REALTIME:
        return await self._redis_bus.publish(event)  # 透传
    else:
        return await self._rabbitmq_bus.publish(event)  # 透传
```

---

#### 3.3.3 端口位置迁移

| 组件 | 迁移前 | 迁移后 |
|------|--------|--------|
| `EventListener` Protocol | `src/domain/events/listener.py` | `src/domain/ports/event_listener.py` |
| `EventListenerAsync` Protocol | `src/domain/events/listener.py` | `src/domain/ports/event_listener.py` |
| `DeadLetterQueue` Protocol | `src/domain/events/listener.py` | `src/domain/ports/dead_letter_queue.py` |
| `InMemoryEventListener` | `src/domain/events/listener.py` | `src/infrastructure/messaging/in_memory_event_listener.py` |
| `InMemoryDeadLetterQueue` | `src/domain/events/listener.py` | `src/infrastructure/messaging/in_memory_dead_letter_queue.py` |

`src/domain/events/listener.py` 保留为向后兼容的 re-export 文件（标记 deprecated）。

---

### 3.4 类型安全增强

#### 3.4.1 AutoExecuteService 参数类型

```python
# 修改前
async def on_routed_event(self, event: DomainEvent) -> AutoExecuted | None:
    session_id = getattr(event, "session_id", "")
    task_context = getattr(event, "task_context", {})

# 修改后
from src.domain.events.auto_route_events import AutoRouted

async def on_routed_event(self, event: AutoRouted) -> AutoExecuted | None:
    session_id = event.session_id
    task_context = event.task_context
    route_target = event.route_target
    route_score = event.route_score
    route_type = event.route_type
```

**影响范围：** `AutoExecuteService` 及其所有测试的调用方式需更新。

---

#### 3.4.2 AutoTriggerContext 提取逻辑简化

```python
# 修改前：4 层嵌套回退
session_id = (
    payload.get("session_id")
    or payload.get("payload", {}).get("session_id")
    or payload.get("aggregate_id")
    or "default"
)

# 修改后：2 层回退 + 显式日志
session_id = payload.get("session_id") or payload.get("aggregate_id") or "default"
if session_id == "default":
    logger.warning("No session_id found in event payload, using 'default'")

ALLOWED_CONTEXT_KEYS: ClassVar[tuple[str, ...]] = (
    "task_type", "priority", "tool_name", "checkpoint_id",
    "correction_type", "routing_decision", "isolation_level",
    "document_id", "strategy_id", "agent_id", "session_id",
    "error_message", "retry_count",
)
```

---

### 3.5 配置体系统一

#### 3.5.1 Frozen 统一

所有 auto-invocation 配置类统一为 `@dataclass(frozen=True)`：

- `AutoTriggerConfig` → 添加 `frozen=True`
- `AutoRouteConfig` → 添加 `frozen=True`
- `AutoExecuteConfig` → 已是 `frozen=True`（无需修改）

#### 3.5.2 导出统一

在 `src/infrastructure/config/__init__.py` 中添加：
```python
from src.infrastructure.config.auto_execute import AutoExecuteConfig
```

#### 3.5.3 死配置激活

将 `AutoRouteConfig.semantic_threshold` 连接到实际消费者：

```python
# 在 DI 注册中传递配置
auto_route_config = AutoRouteConfig.from_env()

register_port(
    name="auto_route_service",
    ...
    impl=lambda resolver: AutoRouteService(
        publisher=resolver.resolve("event_publisher"),
        hash_router=resolver.resolve("hash_router"),
        semantic_router=resolver.resolve("semantic_router"),
        semantic_threshold=auto_route_config.semantic_threshold,
    ),
)
```

在 `AutoRouteService._make_routing_decision()` 中使用 `semantic_threshold`：
```python
if semantic_score >= self._semantic_threshold:
    return "semantic", semantic_target, semantic_score
```

> **注意：** `cache_ttl_seconds` 见 P2-8（移除），不在此处激活。当前 LRU 策略已足够。

---

### 3.6 死代码清理

| 项目 | 操作 | 文件 |
|------|------|------|
| `InMemoryEventPublisher` | 删除 | `src/domain/ports/event_publisher.py` |
| `HashNode` dataclass | 删除 | `src/infrastructure/routing/hash_router.py` |
| `cache_ttl_seconds` 参数 | 移除（从 AutoRouteConfig 和 SemanticRouter） | `src/infrastructure/routing/semantic_router.py`, `src/infrastructure/config/auto_route.py` |
| `AutoExecuteService` 导出 | 添加 | `src/domain/services/__init__.py` |

---

### 3.7 线程安全与背压

#### 3.7.1 AutoTriggerHandler 队列背压

```python
# 修改前
self._event_queue: queue.Queue[tuple[str, DomainEvent]] = queue.Queue()

# 修改后
MAX_QUEUE_SIZE: int = 1000
self._event_queue: queue.Queue[tuple[str, DomainEvent]] = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)
```

在 `_create_handler` 中添加背压处理：
```python
def _create_handler(self, event_type: str) -> Callable[[DomainEvent], None]:
    def handler(event: DomainEvent) -> None:
        try:
            self._event_queue.put_nowait((event_type, event))
        except queue.Full:
            logger.warning("Event queue full (%d), dropping event: %s",
                          self.MAX_QUEUE_SIZE, event_type)
    return handler
```

#### 3.7.2 DockerSandboxAdapter 状态隔离

```python
# 修改前（类级别共享）
_running_containers: dict[str, bool] = {}

# 修改后（实例级别）
def __init__(self) -> None:
    self._running_containers: dict[str, bool] = {}
```

如需跨实例状态共享，由调用者（如 `SessionNamespaceManager`）管理，而非在 adapter 类上。

---

## 4. 修改文件清单与影响矩阵

### 4.1 Domain 层

| 文件 | 修改类型 | 涉及问题 |
|------|---------|---------|
| `src/domain/entities/checkpoint_snapshot.py` | 删除 to_redis_hash/from_redis_hash | P1-1 |
| `src/domain/events/publish_result.py` | 重构为 ChannelResult + PublishResult | P1-2 |
| `src/domain/events/listener.py` | 精简为 re-export | P1-3, P1-4 |
| `src/domain/ports/event_listener.py` | 新建（EventListener + EventListenerAsync） | P1-3 |
| `src/domain/ports/dead_letter_queue.py` | 新建（DeadLetterQueue） | P1-3 |
| `src/domain/ports/event_publisher.py` | 删除 InMemoryEventPublisher | P2-4 |
| `src/domain/ports/__init__.py` | 添加新端口导出 | P1-3 |
| `src/domain/services/auto_execute_service.py` | 参数类型 AutoRouted + import time 顶部 | P1-5, P3-1 |
| `src/domain/services/auto_route_service.py` | 添加 semantic_threshold 参数 + RoutingDecisionLog | P2-2, P2-3 |
| `src/domain/ports/routing_decision_log_repository.py` | 新建（RoutingDecisionLogRepository Protocol） | P2-3 |
| `src/domain/services/__init__.py` | 添加 AutoExecuteService 导出 | P2-5 |
| `src/domain/value_objects/auto_trigger_context.py` | 简化提取逻辑 + 提取常量 | P1-6 |

### 4.2 Application 层

| 文件 | 修改类型 | 涉及问题 |
|------|---------|---------|
| `src/application/event_handlers/auto_route_handler.py` | 删除 _publish + publisher 参数 | P0-2 |
| `src/application/event_handlers/auto_trigger_handler.py` | 队列背压 + logger f-string | P2-6, P3-3 |
| `src/application/event_handlers/auto_execute_completed_handler.py` | 顶部导入 | P3-2 |

### 4.3 Infrastructure 层

| 文件 | 修改类型 | 涉及问题 |
|------|---------|---------|
| `src/infrastructure/routing/semantic_router.py` | cosine_similarity 修复 + 移除 cache_ttl | P0-4, P2-8 |
| `src/infrastructure/routing/hash_router.py` | 删除 HashNode | P3-5 |
| `src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py` | 实例级别状态 | P2-7 |
| `src/infrastructure/external_services/sandbox/session_namespace_manager.py` | datetime 替换占位符 | P3-4 |
| `src/infrastructure/storage/redis/redis_snapshot_store.py` | 新增 mapper 方法 | P1-1 |
| `src/infrastructure/scheduler/heartbeat_scheduler.py` | 注入 Redis 连接 | P3-6 |
| `src/infrastructure/config/auto_trigger.py` | frozen=True | P2-1 |
| `src/infrastructure/config/auto_route.py` | frozen=True | P2-1 |
| `src/infrastructure/config/__init__.py` | 添加 AutoExecuteConfig | P2-1 |
| `src/infrastructure/messaging/in_memory_event_listener.py` | 新建（从 domain 迁移） | P1-4 |
| `src/infrastructure/messaging/in_memory_dead_letter_queue.py` | 新建（从 domain 迁移） | P1-4 |
| `src/infrastructure/messaging/dual_channel_event_bus.py` | 适配 ChannelResult | P1-2 |

### 4.4 Composition Root

| 文件 | 修改类型 | 涉及问题 |
|------|---------|---------|
| `src/composition_root.py` | 修正路径 + 添加 8 个注册 + 移除 OrchestrationService port | P0-1, P0-3, P3-7 |

### 4.5 测试文件（需更新导入和断言）

> 以下列出直接受影响的测试文件（约 25 个），按修改类型分组。完整的测试影响范围约 68 个文件，此处仅列出需要修改导入路径或断言逻辑的文件。

**P0 修复相关：**

| 测试文件 | 涉及问题 | 修改内容 |
|----------|---------|---------|
| `tests/unit/domain/services/test_route_service.py` | P0-2 | 验证仅发布 1 次 AutoRouted |
| `tests/unit/application/event_handlers/test_auto_route_handler.py` | P0-2 | 移除 handler 发布相关断言 |
| `tests/unit/infrastructure/routing/test_semantic_router.py` | P0-4 | cosine_similarity 不同长度向量测试 |
| `tests/unit/infrastructure/routing/test_semantic_router_coverage.py` | P0-4 | 覆盖率测试适配 |
| `tests/unit/infrastructure/routing/test_semantic_router_cache.py` | P2-8 | 移除 cache_ttl 相关测试 |

**P1 架构修复相关：**

| 测试文件 | 涉及问题 | 修改内容 |
|----------|---------|---------|
| `tests/unit/domain/entities/test_checkpoint_snapshot.py` | P1-1 | 移除 to_redis_hash/from_redis_hash 测试 |
| `tests/unit/infrastructure/storage/test_redis_snapshot_store.py` | P1-1 | 添加 mapper 方法测试 |
| `tests/unit/domain/events/test_publish_result.py` | P1-2 | 适配 ChannelResult + is_success 语义变更 |
| `tests/unit/infrastructure/messaging/test_dual_channel_event_bus.py` | P1-2 | 适配子总线返回值 |
| `tests/unit/infrastructure/messaging/test_redis_eventbus.py` | P1-2 | 适配 ChannelResult 构造 |
| `tests/unit/infrastructure/messaging/test_rabbitmq_event_bus.py` | P1-2 | 适配 ChannelResult 构造 |
| `tests/unit/domain/ports/test_protocols.py` | P1-3 | 添加 EventListener/DeadLetterQueue 端口验证 |
| `tests/unit/domain/services/test_execute_service.py` | P1-5 | 参数类型改为 AutoRouted |
| `tests/unit/domain/value_objects/test_auto_trigger_context.py` | P1-6 | 简化提取逻辑断言 |
| `tests/unit/architecture/test_event_messaging_architecture.py` | P1-3, P1-4 | 架构约束更新 |
| `tests/unit/architecture/test_event_architecture.py` | P1-3 | 导入路径验证 |

**P2 质量改进相关：**

| 测试文件 | 涉及问题 | 修改内容 |
|----------|---------|---------|
| `tests/unit/infrastructure/config/test_auto_trigger_config.py` | P2-1 | frozen=True 验证 |
| `tests/unit/infrastructure/config/test_route_config.py` | P2-1, P2-2 | frozen=True + 死配置移除 |
| `tests/unit/infrastructure/config/test_auto_execute_config.py` | P2-1 | frozen 一致性 |
| `tests/unit/domain/ports/test_event_publisher.py` | P2-4 | 移除 InMemoryEventPublisher 测试 |
| `tests/unit/application/event_handlers/test_auto_trigger_handler_branches.py` | P2-6 | 背压/队列满测试 |
| `tests/unit/infrastructure/external_services/sandbox/test_docker_sandbox_adapter.py` | P2-7 | 实例级别状态测试 |

**集成/验收测试：**

| 测试文件 | 涉及问题 | 修改内容 |
|----------|---------|---------|
| `tests/integration/test_integration_route.py` | P0-2 | 双重发布修复验证 |
| `tests/integration/test_integration_execute.py` | P1-5 | 参数类型变更 |
| `tests/acceptance/test_acceptance_autonomous-invocation-route.py` | P0-2 | 发布唯一性验证 |
| `tests/acceptance/test_acceptance_autonomous-invocation-execute.py` | P1-5 | 参数类型变更 |

---

## 5. 执行步骤

### Phase 1：P0 关键 Bug 修复

- [ ] **1.1** 修正 composition_root.py 中 DockerSandboxAdapter 的 impl 和 module 路径（P0-1）
- [ ] **1.2** 修正 composition_root.py 中 RedisSnapshotStore 的 impl 和 module 路径（P0-1）
- [ ] **1.3** 从 AutoRouteHandler 移除 `_publish` 方法和 `publisher` 构造参数（P0-2）
- [ ] **1.4** 修复 SemanticRouter._cosine_similarity：分别计算各向量模值（P0-4）
- [ ] **1.5** 确认 event_listener 端口已注册，在 composition_root 中添加 8 个自主调用组件注册（P0-3）
- [ ] **1.6** 运行 `poetry run pytest tests/unit/infrastructure/routing/ tests/unit/domain/services/ -v` 验证
- [ ] **1.7** 运行 `poetry run pytest --tb=short -q` 全量回归

### Phase 2：P1 架构违规修复

- [ ] **2.1** 从 CheckpointSnapshot 移除 to_redis_hash/from_redis_hash，在 RedisSnapshotStore 中创建 mapper（P1-1）
- [ ] **2.2** 重构 PublishResult 为 ChannelResult + PublishResult，适配 2 个子总线构造站点（RedisEventBus/RabbitMQEventBus）+ InMemoryEventBus + DualChannelEventBus 透传（P1-2）
- [ ] **2.3** 创建 `src/domain/ports/event_listener.py`（EventListener + EventListenerAsync Protocol）（P1-3）
- [ ] **2.4** 创建 `src/domain/ports/dead_letter_queue.py`（DeadLetterQueue Protocol）（P1-3）
- [ ] **2.5** 迁移 InMemoryEventListener 至 `src/infrastructure/messaging/`（P1-4）
- [ ] **2.6** 迁移 InMemoryDeadLetterQueue 至 `src/infrastructure/messaging/`（P1-4）
- [ ] **2.7** AutoExecuteService.on_routed_event 参数改为 AutoRouted（P1-5）
- [ ] **2.8** 简化 AutoTriggerContext.from_domain_event 提取逻辑（P1-6）
- [ ] **2.9** 更新所有导入引用和测试
- [ ] **2.10** 运行 `poetry run pytest --tb=short -q` 全量回归

### Phase 3：P2 代码质量改进

- [ ] **3.1** 统一 AutoTriggerConfig/AutoRouteConfig 为 frozen=True（P2-1）
- [ ] **3.2** 在 config `__init__.py` 中添加 AutoExecuteConfig 导出（P2-1）
- [ ] **3.3** 连接 AutoRouteConfig.semantic_threshold 到 AutoRouteService（P2-2）
- [ ] **3.4** 移除 AutoRouteConfig.cache_ttl_seconds 死配置字段（P2-2/P2-8）
- [ ] **3.5** 在 AutoRouteService 中创建 RoutingDecisionLog 实例（P2-3）
- [ ] **3.6** 删除 InMemoryEventPublisher Protocol（P2-4）
- [ ] **3.7** 在 `__init__.py` 中添加 AutoExecuteService 导出（P2-5）
- [ ] **3.8** AutoTriggerHandler 队列添加 maxsize=1000 背压（P2-6）
- [ ] **3.9** DockerSandboxAdapter._running_containers 改为实例变量，同步移除/重构 reset_all_containers（P2-7）
- [ ] **3.10** 移除 SemanticRouter.cache_ttl_seconds 参数（P2-8）
- [ ] **3.11** 运行 `poetry run pytest --tb=short -q` 全量回归

### Phase 4：P3 风格优化

- [ ] **4.1** 将 `import time` 移至 auto_execute_service.py 模块顶部（P3-1）
- [ ] **4.2** 将 AutoExecuteCompletedHandler 的惰性导入移至顶部（P3-2）
- [ ] **4.3** 修复 AutoTriggerHandler 中的 logger f-string（P3-3）
- [ ] **4.4** SessionNamespaceManager 中 `"now"` 改为 datetime（P3-4）
- [ ] **4.5** 删除未使用的 HashNode dataclass（P3-5）
- [ ] **4.6** HeartbeatScheduler 接受注入的 Redis 连接配置（P3-6）
- [ ] **4.7** OrchestrationService 改为 service 注册而非 port（P3-7）
- [ ] **4.8** 运行 `poetry run pytest --tb=short -q` 全量回归

---

## 6. 测试策略

### 6.1 回归基线

| 指标 | 基线值 |
|------|--------|
| 总测试数 | 4190 passed, 38 skipped |
| 失败数 | 0 |
| 覆盖率 | 92% |

每个 Phase 完成后必须达到同等基线。

### 6.2 新增测试需求

| 测试类型 | 新增测试 | 描述 |
|----------|---------|------|
| DI 解析 | `test_auto_invocation_pipeline_resolvable` | 验证所有 8 个组件可通过 DI 容器解析 |
| 发布唯一性 | `test_auto_routed_published_once` | 验证 AutoTriggered → 仅 1 条 AutoRouted |
| 序列化 | `test_redis_snapshot_mapper` | 验证 mapper 正确序列化/反序列化 |
| PublishResult | `test_channel_result_abstraction` | 验证 PublishResult 无 Redis/Outbox 引用 |
| 背压 | `test_trigger_handler_queue_full_drops` | 验证队列满时丢弃事件并记录警告 |
| 架构合规 | `test_domain_no_redis_references` | 验证 domain 层无 Redis 导入 |

### 6.3 架构合规验证

```bash
# Domain 层零外部依赖
poetry run pytest tests/unit/architecture/ -v

# 端口契约测试
poetry run pytest tests/contracts/ -v

# 协议类型检查
poetry run pytest tests/unit/domain/ports/test_protocols.py -v
```

---

## 7. 与后续 Story 的兼容性

### 7.1 Story 1.15a/b（外部化记忆）

**扩展点：**
- `CheckpointSnapshot` 纯化后，记忆快照可通过独立的 `MemorySnapshot` 实体实现，不依赖 Redis 序列化
- `PublishResult` 抽象化后，MemoryChanged 事件可复用通用通道发布

**影响：** 无破坏性变更。重构为记忆子系统提供了更干净的扩展接口。

---

### 7.2 Story 1.17（UDMR 路由）

**扩展点：**
- `RoutingDecisionLog` 实例化（P2-3）是 UDMR 集成的前提
- `AutoRouteService` 添加 `semantic_threshold` 参数后，UDMR 可在 L3 层利用该阈值做模型选择
- DI 注册完善后，UDMR 组件可直接注入管线

**影响：** P2-3（RoutingDecisionLog 实例化）是 Story 1.17 的前置依赖。

---

### 7.3 Story 1.18a/b（引擎集成）

**扩展点：**
- `OrchestrationService` 从 port 改为 service 注册后（P3-7），引擎适配器注册更清晰
- DI 管线完善后，`WorkflowEnginePort` 和 `AgentEnginePort` 可通过 DI 注入 `OrchestrationService`

**影响：** 无破坏性变更。重构使引擎集成更顺畅。

---

### 7.4 Epic 4（战略工具箱）

**扩展点：**
- `SemanticRouter` 的 `Candidate` 注册机制直接支持 23 个战略工具注册
- `cosine_similarity` 修复（P0-4）确保工具匹配准确度
- DI 注册完善后，工具注册可在启动时自动完成

---

### 7.5 Epic 5（Agent 协作）

**扩展点：**
- `SessionNamespaceManager` 占位符修复（P3-4）为多 Agent 会话管理提供基础
- `DockerSandboxAdapter` 实例隔离（P2-7）支持 Agent 级别的容器隔离
- `CheckpointSnapshot` 纯化后，Agent 状态恢复通过 `SnapshotRepositoryProtocol` 统一管理

---

## 关键设计决策汇总

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | CheckpointSnapshot 序列化 | 迁移至 RedisSnapshotStore mapper | domain 实体不应知道 Redis |
| 2 | PublishResult 字段 | 抽象为 ChannelResult | domain 不应知道 Redis/Outbox |
| 3 | EventListener 位置 | 迁移至 domain/ports/ | 保持端口约定一致性 |
| 4 | AutoExecuteService 参数 | 改为接收 AutoRouted | 与 AutoRouteService 模式一致 |
| 5 | DI 注册 | 完整注册 8 个组件 | 当前管线无法通过 DI 启动 |
| 6 | 双重发布修复 | 从 handler 移除 _publish | service 是唯一发布者 |
| 7 | 配置 frozen | 统一为 frozen=True | 不可变配置更安全 |
| 8 | 队列背压 | maxsize=1000 + 丢弃 | 防止 OOM，fail-fast 优于 fail-slow |
| 9 | DockerSandboxAdapter 状态 | 改为实例变量 | 实例隔离，消除共享状态风险 |
| 10 | RoutingDecisionLog | 在 service 中实例化 | 完成 Story 1.14b AC-3 遗漏 |
| 11 | PublishResult.is_success 语义 | 从"任一成功"改为"全部成功" | 通道无关抽象后的自然语义；需评估现有消费者是否依赖旧语义 |
