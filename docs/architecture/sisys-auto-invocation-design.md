# SISYS 自主调用子系统详细设计

**文档版本:** v1.0
**生成时间:** 2026-05-21
**基于:** architecture.md v8.3.1 + sisys-event-bus-design.md v1.0 + Story 1.14a/b/c 已完成实现 + 现有代码全面调研
**状态:** 初始设计

---

## 1. 设计概述

### 1.1 系统公理一

SISYS 基于 `trigger(event) → route(routing) → execute(execution)` 自主调用循环构建，这是系统的核心运行逻辑：

> CLI 是"点火开关"（外部触发器），领域事件是"引擎血液"（内部触发器），auto-trigger → auto-route → auto-execute 是"引擎运转逻辑"。

| 阶段 | 触发源 | 路由机制 | 执行环境 | 状态管理 |
|------|--------|---------|---------|---------|
| **trigger** | 领域事件 / 周期性心跳事件 | — | — | — |
| **route** | — | session_id 哈希 / 语义路由 | — | 路由决策日志（WORM 归档） |
| **execute** | — | — | 会话命名空间（Docker/gVisor 沙箱） | 状态快照 → Redis（TTL 24h-30d） |

### 1.2 目标与范围

本文档覆盖自主调用子系统的完整详细设计，包括：

- 三阶段管线（trigger → route → execute）的领域模型、事件链、端口协议
- 与事件总线（双通道）、UDMR（Story 1.17）、引擎（Story 1.18a/b）的集成方案
- 错误处理、性能保障、组合根装配
- 后续 Story 和 Epic 的扩展指南

**不覆盖：** 外部化记忆子系统（Story 1.15a/b）、UDMR 三层决策逻辑（Story 1.17）、Prefect/LangGraph 引擎内部实现（Story 1.18a/b）。

### 1.3 架构约束

| 约束 | 规则 | 验证方式 |
|------|------|---------|
| **六边形架构** | Domain 层零外部依赖（仅 Python 标准库） | 架构测试（import 检查） |
| **Protocol 优先** | 接口用 `typing.Protocol` + `@runtime_checkable` | 代码审查 |
| **async 一致性** | 所有异步操作的 Protocol 签名必须为 async | 代码审查 |
| **事件不可变** | 所有 DomainEvent 均为 `frozen=True` dataclass | 类型检查 |
| **单向依赖** | domain → application → interfaces → infrastructure | 架构测试 |
| **端口归属** | 端口定义在 domain/ports/ 或 application/ports/ | 目录结构检查 |

**依赖方向矩阵：**

| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|-------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止 |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

### 1.4 核心设计原则

1. **事件驱动解耦**：三阶段通过事件总线连接，每阶段仅发布自己的输出事件
2. **端口/适配器分离**：领域逻辑通过 Protocol 定义端口，基础设施提供实现
3. **技术事件桥接**：AutoExecuted 是技术事件，通过 `business_event_type` 桥接到业务领域事件
4. **会话一致性**：同一 session_id 的任务路由到同一节点（哈希路由保证）
5. **状态可恢复**：执行状态通过 CheckpointSnapshot 快照化，支持中断恢复

### 1.5 性能目标总表

| 阶段 | 指标 | MVP 目标 | V1 目标 | V2 目标 |
|------|------|---------|--------|--------|
| trigger | 触发延迟 P95 | < 10ms | < 5ms | < 3ms |
| trigger | 吞吐量 | 1000 events/s | 5000 events/s | 10000 events/s |
| route | 路由决策延迟 P95 | < 50ms | < 30ms | < 20ms |
| route | 路由吞吐量 | 1000 decisions/s | 5000 decisions/s | 10000 decisions/s |
| route | 语义匹配率 | ≥ 90% | ≥ 95% | ≥ 98% |
| execute | 沙箱启动延迟 P95 | < 100ms | < 50ms | < 30ms |
| execute | 快照延迟 P95 | < 50ms | < 30ms | < 20ms |
| execute | 执行吞吐量 | 100 executions/s | 500 executions/s | 1000 executions/s |

---

## 2. 架构总览图

### 2.1 完整拓扑

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              External Triggers                                    │
│  CLI ("点火开关")  │  REST API  │  周期性心跳 (HeartbeatScheduler)                 │
└──────────┬─────────┴──────┬─────┴────────────┬──────────────────────────────────┘
           │                │                  │
           v                v                  v
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           Domain Event Layer                                      │
│  DocumentProcessed │ ToolExecuted │ AgentDecided │ CheckpointReached │ ... (12种) │
└──────────┬───────────────────────────────────────────────────────────────────────┘
           │ DualChannelEventBus (REALTIME: Redis Pub/Sub)
           v
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        Phase 1: TRIGGER                                           │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Application Layer                                                        │  │
│  │  AutoTriggerHandler                                                       │  │
│  │  ├── 后台线程 + 独立 asyncio 事件循环                                      │  │
│  │  ├── 注册 12 种领域事件 + HeartbeatTriggered                                │  │
│  │  ├── MAX_CONCURRENT_TASKS=100, TASK_TIMEOUT=300s                          │  │
│  │  └── 桥接事件总线 → AutoTriggerService                                     │  │
│  └────────────────────────────┬───────────────────────────────────────────────┘  │
│                               │                                                   │
│  ┌────────────────────────────v───────────────────────────────────────────────┐  │
│  │  Domain Layer                                                             │  │
│  │  AutoTriggerService                                                       │  │
│  │  ├── on_domain_event(event) → AutoTriggered                                │  │
│  │  ├── on_heartbeat_event(event) → AutoTriggered                             │  │
│  │  └── extract_context(event) → AutoTriggerContext                           │  │
│  └────────────────────────────┬───────────────────────────────────────────────┘  │
│                               │                                                   │
│                    AutoTriggered (REALTIME)                                        │
│                    {trigger_type, session_id, agent_id, task_context,             │
│                     source_event_type, source_event_id}                           │
└──────────┬────────────────────┬──────────────────────────────────────────────────┘
           │ DualChannelEventBus (REALTIME: Redis Pub/Sub)
           v
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        Phase 2: ROUTE                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Application Layer                                                        │  │
│  │  AutoRouteHandler                                                         │  │
│  │  ├── 监听 AutoTriggered 事件                                               │  │
│  │  ├── 调用 AutoRouteService.on_triggered_event()                            │  │
│  │  └── 发布 AutoRouted 事件                                                  │  │
│  └────────────────────────────┬───────────────────────────────────────────────┘  │
│                               │                                                   │
│  ┌────────────────────────────v───────────────────────────────────────────────┐  │
│  │  Domain Layer                                                             │  │
│  │  AutoRouteService                                                         │  │
│  │  ├── _make_routing_decision(event)                                        │  │
│  │  │   ├── HashRouterProtocol.route(session_id) → hash_target                │  │
│  │  │   └── SemanticRouterProtocol.route(task_context) → (target, score)      │  │
│  │  └── 混合路由决策: hash + semantic → "mixed"/"hash"/"semantic"             │  │
│  └────────────────────────────┬───────────────────────────────────────────────┘  │
│                               │                                                   │
│                    AutoRouted (REALTIME)                                           │
│                    {route_type, session_id, task_context,                         │
│                     route_target, route_score, trigger_event_id}                  │
└──────────┬────────────────────┬──────────────────────────────────────────────────┘
           │
           │ ┌─── 未来: UDMR (Story 1.17) ────────────────────────────────┐
           │ │  AutoRouted → UDMRService                                  │
           │ │  L1 ComplianceGateway → L2 ComplexityAssessor → L3 RouterExecutor │
           │ │  输出: selected_model + cost_estimate → AutoExecuted        │
           │ └───────────────────────────────────────────────────────────────┘
           │
           │ DualChannelEventBus (RELIABLE: Outbox + RabbitMQ)
           v
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        Phase 3: EXECUTE                                           │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Domain Layer                                                             │  │
│  │  AutoExecuteService                                                       │  │
│  │  ├── on_routed_event(event)                                               │  │
│  │  │   ├── SandboxExecutorProtocol.start_container(session_id)               │  │
│  │  │   ├── SandboxExecutorProtocol.execute_code(session_id, code)            │  │
│  │  │   ├── SnapshotRepositoryProtocol.save(snapshot)                         │  │
│  │  │   └── 发布 AutoExecuted (技术事件)                                      │  │
│  │  ├── create_snapshot(session_id, state) → CheckpointSnapshot               │  │
│  │  └── restore_snapshot(session_id) → CheckpointSnapshot                     │  │
│  └────────────────────────────┬───────────────────────────────────────────────┘  │
│                               │                                                   │
│                    AutoExecuted (REALTIME)                                         │
│                    {session_id, task_context, execution_result,                   │
│                     cost_estimate, latency_ms, business_event_type}               │
│                               │                                                   │
│  ┌────────────────────────────v───────────────────────────────────────────────┐  │
│  │  Application Layer                                                        │  │
│  │  AutoExecuteCompletedHandler                                              │  │
│  │  ├── on_executed(event) → 根据 business_event_type 分发:                   │  │
│  │  │   ├── "DocumentProcessed" → DocumentProcessed 事件                       │  │
│  │  │   ├── "ToolExecuted" → ToolExecuted 事件                                 │  │
│  │  │   └── "AgentDecided" → AgentDecided 事件                                │  │
│  │  └── 发布业务领域事件到事件总线                                              │  │
│  └────────────────────────────┬───────────────────────────────────────────────┘  │
│                               │                                                   │
│                    业务领域事件 (RELIABLE)                                          │
│                    DocumentProcessed / ToolExecuted / AgentDecided                 │
│                               │                                                   │
│                    ┌──────────v──────────┐                                        │
│                    │  回到 Phase 1        │ ← 自主调用循环                         │
│                    │  触发下一轮 trigger   │                                        │
│                    └─────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 基础设施层组件拓扑

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       Infrastructure Layer                                        │
│                                                                                   │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐  │
│  │  HashRouter          │  │  SemanticRouter       │  │  DockerSandboxAdapter   │  │
│  │  FNV-1a + 虚拟节点   │  │  bge-m3 + 余弦相似度  │  │  Docker 容器隔离        │  │
│  │  加权一致性哈希      │  │  内存嵌入缓存         │  │  CPU/Memory/Network 限制│  │
│  │  src/infrastructure/ │  │  MAX_CACHE=10000      │  │  src/infrastructure/   │  │
│  │  routing/            │  │  src/infrastructure/  │  │  external_services/    │  │
│  └──────────┬──────────┘  └──────────┬───────────┘  └──────────┬─────────────┘  │
│             │ implements               │ implements               │ implements     │
│             v                          v                          v               │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐  │
│  │  HashRouterProtocol  │  │  SemanticRouter-      │  │  SandboxExecutor-       │  │
│  │  (domain/ports/)     │  │  Protocol             │  │  Protocol               │  │
│  │  route(session_id)   │  │  (domain/ports/)      │  │  (domain/ports/)        │  │
│  │  → str               │  │  route(context)        │  │  start/execute/stop     │  │
│  │                       │  │  → (str, float)       │  │  (application/ports/)   │  │
│  └─────────────────────┘  └──────────────────────┘  └────────────────────────┘  │
│                                                                                   │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐  │
│  │  RedisSnapshotStore  │  │  HeartbeatScheduler   │  │  SessionNamespace-      │  │
│  │  Redis Hash + TTL    │  │  asyncio + Redis ZADD  │  │  Manager               │  │
│  │  主从复制支持        │  │  可配置间隔 (默认60s)  │  │  会话-命名空间映射       │  │
│  │  src/infrastructure/ │  │  src/infrastructure/  │  │  src/infrastructure/    │  │
│  │  storage/redis/      │  │  scheduler/           │  │  external_services/     │  │
│  └──────────┬──────────┘  └──────────────────────┘  └────────────────────────┘  │
│             │ implements                                                              │
│             v                                                                        │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐  │
│  │  SnapshotRepo-       │  │  AutoTriggerConfig    │  │  AutoRouteConfig        │  │
│  │  Protocol            │  │  (from_env())         │  │  (from_env())           │  │
│  │  (domain/ports/)     │  │  src/infrastructure/  │  │  src/infrastructure/    │  │
│  │  save/load/delete    │  │  config/              │  │  config/               │  │
│  └─────────────────────┘  └──────────────────────┘  └────────────────────────┘  │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────────┐│
│  │  AutoExecuteConfig (from_env())  │  sandbox_type / snapshot_ttl / resources ││
│  │  src/infrastructure/config/      │                                          ││
│  └──────────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Domain 层设计

### 3.1 事件体系

自主调用子系统定义三个技术事件，均继承自 `DomainEvent`（`src/domain/events/base.py`）：

```
DomainEvent (frozen dataclass, _registry 多态反序列化)
├── AutoTriggered     # Phase 1 输出：触发上下文提取完成
├── AutoRouted        # Phase 2 输出：路由决策完成
└── AutoExecuted      # Phase 3 输出：任务执行完成
```

#### 3.1.1 AutoTriggered

**文件:** `src/domain/events/auto_trigger_events.py`

```
@dataclass(frozen=True)
class AutoTriggered(DomainEvent):
    event_type: str = "AutoTriggered"        # init=False, 自动注册到 _registry
    trigger_type: str                         # "domain_event" | "heartbeat"
    session_id: str                           # 会话标识（提取自 payload 或 heartbeat_id）
    agent_id: str | None                      # Agent 标识（可选）
    task_context: dict[str, Any]              # 任务上下文（键值对）
    source_event_type: str                    # 原始事件类型（如 "DocumentProcessed"）
    source_event_id: str | None               # 原始事件 ID

    # 自动设置:
    aggregate_type = "AutoTrigger"
    aggregate_id = event_id (如未指定)
```

**通道映射:** REALTIME（Redis Pub/Sub）

#### 3.1.2 AutoRouted

**文件:** `src/domain/events/auto_route_events.py`

```
@dataclass(frozen=True)
class AutoRouted(DomainEvent):
    event_type: str = "AutoRouted"            # init=False
    route_type: str                           # "hash" | "semantic" | "mixed"
    session_id: str                           # 会话标识
    task_context: dict[str, Any]              # 任务上下文（透传自 AutoTriggered）
    route_target: str                         # 目标 Agent/工具 ID
    route_score: float                        # 路由置信度（0.0-1.0）
    trigger_event_type: str                   # 原始触发事件类型
    trigger_event_id: str | None              # 原始触发事件 ID

    # 自动设置:
    aggregate_type = "AutoRoute"
    aggregate_id = event_id (如未指定)
```

**通道映射:** REALTIME（Redis Pub/Sub）

#### 3.1.3 AutoExecuted

**文件:** `src/domain/events/auto_execute_events.py`

```
@dataclass(frozen=True)
class AutoExecuted(DomainEvent):
    event_type: str = "AutoExecuted"          # init=False
    session_id: str                           # 会话标识
    task_context: dict[str, Any]              # 任务上下文（透传自 AutoRouted）
    execution_result: dict[str, Any]          # 执行结果（status/output/error）
    cost_estimate: float                      # 成本估算（美元）
    latency_ms: float                         # 执行延迟（毫秒）
    business_event_type: str                  # 业务事件类型分发键
                                              #   "DocumentProcessed" | "ToolExecuted" | "AgentDecided"
    route_target: str                         # 路由目标（透传自 AutoRouted）
    route_score: float                        # 路由置信度（透传自 AutoRouted）

    # 自动设置:
    aggregate_type = "AutoExecute"
    aggregate_id = event_id (如未指定)
```

**通道映射:** RELIABLE（PostgreSQL Outbox + RabbitMQ）

**设计要点:** AutoExecuted 是技术事件而非业务事件。通过 `business_event_type` 字段，下游 `AutoExecuteCompletedHandler` 将其桥接到对应的业务领域事件。这不是继承关系，而是策略模式分发。

### 3.2 领域服务

三个领域服务分别对应自主调用的三个阶段，均位于 `src/domain/services/`。

#### 3.2.1 AutoTriggerService

**文件:** `src/domain/services/auto_trigger_service.py`

**职责：** 监听领域事件和心跳事件，提取会话上下文，发布 AutoTriggered 事件。

```
class AutoTriggerService:
    __init__(publisher: EventPublisher | None = None)

    async on_domain_event(event: DomainEvent) → AutoTriggered | None
        # 1. 构建 payload（event.payload + event_type）
        # 2. AutoTriggerContext.from_domain_event() 提取上下文
        # 3. 构造 AutoTriggered 事件
        # 4. 通过 publisher 发布

    async on_heartbeat_event(event: DomainEvent) → AutoTriggered | None
        # 1. 提取 heartbeat_id, wake_reason, todo_items, cost_budget
        # 2. AutoTriggerContext.from_heartbeat() 提取上下文
        # 3. 构造 AutoTriggered 事件
        # 4. 通过 publisher 发布

    extract_context(event: DomainEvent) → AutoTriggerContext
        # 不发布事件，仅提取上下文（测试/调试用）
```

**依赖端口:** `EventPublisher`（domain/ports/event_publisher.py）

#### 3.2.2 AutoRouteService

**文件:** `src/domain/services/auto_route_service.py`

**职责：** 监听 AutoTriggered 事件，执行路由决策（哈希 + 语义），发布 AutoRouted 事件。

```
class AutoRouteService:
    __init__(
        publisher: EventPublisher | None = None,
        hash_router: HashRouterProtocol | None = None,
        semantic_router: SemanticRouterProtocol | None = None,
    )

    async on_triggered_event(event: AutoTriggered) → AutoRouted
        # 1. _make_routing_decision(event) → (route_type, route_target, route_score)
        # 2. 构造 AutoRouted 事件
        # 3. 通过 publisher 发布

    async _make_routing_decision(event) → tuple[str, str, float]
        # 路由策略（优先级从高到低）:
        # 1. mixed: hash + semantic 均可用 → 优先 semantic（更智能匹配）
        # 2. semantic: 仅 semantic 可用
        # 3. hash: 仅 hash 可用
        # 4. hash(default): 均不可用，目标="default", score=0.0
```

**依赖端口:**
- `EventPublisher`
- `HashRouterProtocol`（domain/ports/hash_router_protocol.py）
- `SemanticRouterProtocol`（domain/ports/semantic_router_protocol.py）

**路由决策逻辑：**

```
┌──────────────────┐    ┌──────────────────┐
│  HashRouter      │    │  SemanticRouter   │
│  session_id      │    │  task_context     │
│  → hash_target   │    │  → (sem_target,   │
│  score = 1.0     │    │      sem_score)   │
└────────┬─────────┘    └────────┬──────────┘
         │                       │
         v                       v
    ┌──────────────────────────────────────┐
    │  混合路由决策                         │
    │                                      │
    │  if hash_target AND semantic_target: │
    │    → "mixed", semantic_target, score │
    │  elif semantic_target:               │
    │    → "semantic", target, score       │
    │  elif hash_target:                   │
    │    → "hash", target, 1.0             │
    │  else:                               │
    │    → "hash", "default", 0.0          │
    └──────────────────────────────────────┘
```

#### 3.2.3 AutoExecuteService

**文件:** `src/domain/services/auto_execute_service.py`

**职责：** 监听 AutoRouted 事件，在沙箱中执行任务，创建状态快照，发布 AutoExecuted 事件。

```
class AutoExecuteService:
    __init__(
        sandbox: SandboxExecutorProtocol | None = None,
        snapshot_repo: SnapshotRepositoryProtocol | None = None,
    )

    async on_routed_event(event: DomainEvent) → AutoExecuted | None
        # 1. 提取 session_id, task_context, route_target, route_score
        # 2. sandbox.start_container(session_id)
        # 3. sandbox.execute_code(session_id, code) 或标记 completed
        # 4. snapshot_repo.save(CheckpointSnapshot)
        # 5. 构造 AutoExecuted 事件（含 business_event_type）
        # 注意：异常时仍返回 AutoExecuted（status="failed"）

    async create_snapshot(session_id, state, stage_id) → CheckpointSnapshot | None
        # 独立快照创建，版本号自动递增

    async restore_snapshot(session_id) → CheckpointSnapshot | None
        # 恢复最新快照
```

**依赖端口:**
- `SandboxExecutorProtocol`（domain/ports/sandbox_executor_protocol.py）
- `SnapshotRepositoryProtocol`（domain/ports/snapshot_repository_protocol.py）

**异常处理设计：** 执行失败时不抛异常，而是返回 `AutoExecuted(execution_result={"status": "failed", "error": str(e)})`，确保事件链不中断。

### 3.3 实体

#### 3.3.1 CheckpointSnapshot

**文件:** `src/domain/entities/checkpoint_snapshot.py`

```
@dataclass(frozen=True)
class CheckpointSnapshot:
    snapshot_id: UUID                          # 唯一标识
    session_id: str                            # 所属会话
    stage_id: str                              # 执行阶段（planning/execution/completed）
    state_version: int                         # 乐观锁版本号
    state_data: dict[str, Any]                 # 状态数据
    timestamp: datetime                        # 创建时间（UTC）
    ttl_seconds: int = 86400                   # TTL（60s ~ 2592000s = 30d）

    # 序列化方法:
    to_redis_hash() → dict[str, str]           # Redis Hash 格式
    from_redis_hash(data) → CheckpointSnapshot  # 反序列化

    # 不可变更新:
    with_updated_state(state_data, version?) → CheckpointSnapshot  # 创建新快照
```

**存储格式（Redis Hash）：**

```
Key: snapshot:{session_id}
Field: latest → JSON({
    snapshot_id, session_id, stage_id,
    state_version, state_data, timestamp, ttl_seconds
})
TTL: ttl_seconds（默认 86400 = 24h）
```

#### 3.3.2 RoutingDecisionLog

**文件:** `src/domain/entities/routing_decision_log.py`

```
@dataclass(frozen=True)
class RoutingDecisionLog:
    log_id: UUID                               # 日志唯一标识
    task_id: str                               # 任务标识
    session_id: str                            # 会话标识
    route_type: str                            # "hash" | "semantic" | "mixed" | "local" | "cloud"
    route_target: str                          # 目标 Agent/工具/模型
    route_score: float                         # 置信度（0.0-1.0）
    cost_estimate: float = 0.0                 # 预估成本（美元）
    latency_ms: float = 0.0                    # 决策延迟（ms）
    timestamp: datetime                        # 决策时间（UTC）
    worm_storage_ref: str = ""                 # WORM 存储引用（7年归档）
    # UDMR 扩展字段:
    selected_model: str = ""                   # UDMR 选定模型
    cost_actual: float = 0.0                   # 实际成本
    fallback_reason: str | None = None         # 回退原因

    validate() → None                          # 不变量校验
```

**WORM 归档要求:** 路由决策日志需保留 7 年（SOX/ISO27001 合规）。

### 3.4 值对象

#### 3.4.1 AutoTriggerContext

**文件:** `src/domain/value_objects/auto_trigger_context.py`

```
@dataclass(frozen=True)
class AutoTriggerContext:
    session_id: str                            # 会话标识
    trigger_type: str                          # "domain_event" | "heartbeat"
    agent_id: str | None = None                # Agent 标识
    task_context: dict[str, Any] = {}          # 任务上下文
    timestamp: datetime                        # 触发时间
    source_event_type: str = ""                # 源事件类型
    source_event_id: str | None = None         # 源事件 ID

    # 工厂方法:
    from_domain_event(event_type, payload, event_id?) → AutoTriggerContext
    from_heartbeat(heartbeat_id, wake_reason, todo_items, cost_budget) → AutoTriggerContext
```

**session_id 提取优先级：** `payload.session_id` → `payload.payload.session_id` → `payload.aggregate_id` → `"default"`

### 3.5 端口协议

自主调用子系统定义以下端口协议：

| 端口 | 文件路径 | 层次 | 签名 |
|------|---------|------|------|
| `EventPublisher` | `src/domain/ports/event_publisher.py` | Domain | `async publish(event) → PublishResult` |
| `HashRouterProtocol` | `src/domain/ports/hash_router_protocol.py` | Domain | `route(session_id) → str` |
| `SemanticRouterProtocol` | `src/domain/ports/semantic_router_protocol.py` | Domain | `async route(context) → (str, float)` |
| `SandboxExecutorProtocol` | `src/domain/ports/sandbox_executor_protocol.py` | Domain | `start/execute/stop` |
| `SnapshotRepositoryProtocol` | `src/domain/ports/snapshot_repository_protocol.py` | Domain | `save/load/delete` |
| `SandboxExecutor` | `src/application/ports/sandbox_port.py` | Application | `start/execute/stop/is_running` |

**设计规则：**
- 所有端口使用 `typing.Protocol` + `@runtime_checkable`（`SandboxExecutor` 除外，位于 application/ports/ 未加装饰器，通过结构化类型兼容）
- async 操作的 Protocol 签名必须为 async
- 端口定义在 domain/ports/ 或 application/ports/（取决于依赖方向）
- 基础设施层提供 Protocol 的具体实现

---

## 4. Application 层设计

### 4.1 事件处理器

自主调用子系统定义三个应用层事件处理器，负责桥接事件总线与领域服务。

#### 4.1.1 AutoTriggerHandler

**文件:** `src/application/event_handlers/auto_trigger_handler.py`

**职责：** 桥接事件总线与 AutoTriggerService，注册 12 种领域事件处理器。

```
class AutoTriggerHandler:
    __init__(auto_trigger_service, event_listener)

    # 并发控制:
    MAX_CONCURRENT_TASKS = 100
    TASK_TIMEOUT = 300.0  # 秒

    # 注册的事件类型（12 种）:
    _registered_event_types = [
        "DocumentProcessed", "ToolExecuted", "AgentDecided",
        "CheckpointReached", "CheckpointRecovered",
        "CorrectionClassified", "CorrectionApproved",
        "RoutingDecided", "IsolationLevelSwitched",
        "HeartbeatTriggered", "StrategicDeviationWarning",
        "AuditEvent",
    ]

    register_handlers() → None
        # 1. 启动后台工作线程
        # 2. 为每种事件类型注册 handler

    # 内部机制:
    # - 同步 handler 将事件放入 queue.Queue
    # - 后台线程运行独立 asyncio 事件循环
    # - asyncio.wait_for() 控制超时
    # - asyncio.wait(FIRST_COMPLETED) 控制并发
```

**架构选择：** 使用后台线程 + 独立 asyncio 事件循环，而非纯 async，原因是事件总线的 `EventListener.dispatch()` 是同步调用，需要桥接到 async 领域服务。

#### 4.1.2 AutoRouteHandler

**文件:** `src/application/event_handlers/auto_route_handler.py`

**职责：** 监听 AutoTriggered 事件，调用 AutoRouteService，发布 AutoRouted 事件。

```
class AutoRouteHandler:
    __init__(auto_route_service, publisher)

    async on_triggered(event: DomainEvent) → AutoRouted | None
        # 1. 类型检查：isinstance(event, AutoTriggered)
        # 2. 调用 auto_route_service.on_triggered_event(event)
        # 3. 通过 publisher 发布 AutoRouted
```

**与 UDMR 的区别（重要）：**

| 维度 | AutoRouteHandler（本 Story） | UDMR（Story 1.17） |
|------|------------------------------|-------------------|
| 输入事件 | AutoTriggered | AutoRouted |
| 输出事件 | AutoRouted | RoutingDecided |
| 路由对象 | Agent/工具（目标选择） | 本地/云模型（模型选择） |
| 路由策略 | hash + semantic | L1 合规 → L2 评估 → L3 决策 |

#### 4.1.3 AutoExecuteCompletedHandler

**文件:** `src/application/event_handlers/auto_execute_completed_handler.py`

**职责：** 监听 AutoExecuted 事件，根据 `business_event_type` 分发到业务领域事件。

```
class AutoExecuteCompletedHandler:
    __init__(publisher)

    async on_executed(event: AutoExecuted) → None
        # 根据 business_event_type 分发:
        # "DocumentProcessed" → _publish_document_processed(event)
        # "ToolExecuted"      → _publish_tool_executed(event)
        # "AgentDecided"      → _publish_agent_decided(event)
        # 其他                 → 默认 _publish_tool_executed(event)
```

**技术事件 → 业务事件桥接：**

```
AutoExecuted                          业务领域事件
┌─────────────────┐                  ┌───────────────────┐
│ business_event_  │                  │                   │
│ type =           │──"DocumentProc."─▶ DocumentProcessed  │
│                  │──"ToolExecuted"──▶ ToolExecuted       │
│                  │──"AgentDecided"──▶ AgentDecided       │
│ execution_result │                  │ decision_result   │
│ cost_estimate    │                  │ cost_audit        │
│ route_score      │                  │ confidence        │
└─────────────────┘                  └───────────────────┘
```

### 4.2 编排流程

完整的事件编排链如下：

```
1. 用户操作 → DomainEvent（如 DocumentProcessed）
2. DomainEvent → DualChannelEventBus.dispatch() → AutoTriggerHandler._create_handler()
3. AutoTriggerHandler 将事件入队 → 后台线程处理
4. AutoTriggerService.on_domain_event() → AutoTriggered
5. AutoTriggered → DualChannelEventBus.publish() → REALTIME 通道
6. AutoRouteHandler.on_triggered() → AutoRouteService.on_triggered_event()
7. AutoRouteService._make_routing_decision() → AutoRouted
8. AutoRouted → DualChannelEventBus.publish() → REALTIME 通道
9. AutoExecuteService.on_routed_event() → 沙箱执行 + 快照保存
10. AutoExecuted → DualChannelEventBus.publish() → REALTIME 通道
11. AutoExecuteCompletedHandler.on_executed() → 分发业务事件
12. 业务事件 → DualChannelEventBus → 回到步骤 2（自主调用循环）
```

---

## 5. Infrastructure 层设计

### 5.1 路由器

#### 5.1.1 HashRouter（一致性哈希路由器）

**文件:** `src/infrastructure/routing/hash_router.py`
**实现端口:** `HashRouterProtocol`（`src/domain/ports/hash_router_protocol.py`）

**算法:** FNV-1a 32-bit 哈希 + 加权虚拟节点一致性哈希环

```
┌─────────────────────────────────────────────────────┐
│              HashRouter 架构                         │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  一致性哈希环（Sorted Array + 顺序查找）          │  │
│  │                                                  │  │
│  │  V0 ── V1 ── V2 ── ... ── Vn ── V0 (环绕)     │  │
│  │  │      │      │              │                  │  │
│  │  NodeA  NodeA  NodeB  ...    NodeN              │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  配置:                                               │
│  - VIRTUAL_NODES_PER_NODE = 150（每个物理节点）      │
│  - 支持加权（weight > 1 → 更多虚拟节点）             │
│  - route(session_id): O(n) 顺序查找（V2 优化为 bisect 二分查找）              │
└─────────────────────────────────────────────────────┘
```

**关键特性：**
- **会话一致性：** 相同 session_id 始终路由到同一节点（100% 保证）
- **最小重分配：** 节点增删时仅影响 K/N 个映射（K=虚拟节点数，N=环空间）
- **加权支持：** 高性能节点可分配更多虚拟节点
- **零依赖：** FNV-1a 纯 Python 实现，不依赖 mmh3 等外部库

**接口签名：**

```
class HashRouter:
    __init__(nodes: Sequence[str] | None, virtual_nodes: int | None)
    add_node(node_id: str, weight: int = 1) → None
    remove_node(node_id: str) → None
    route(session_id: str) → str
    node_count → int
    virtual_node_count → int
```

#### 5.1.2 SemanticRouter（语义路由器）

**文件:** `src/infrastructure/routing/semantic_router.py`
**实现端口:** `SemanticRouterProtocol`（`src/domain/ports/semantic_router_protocol.py`）

**算法:** bge-m3 向量嵌入 + 余弦相似度匹配

```
┌─────────────────────────────────────────────────────┐
│              SemanticRouter 架构                     │
│                                                      │
│  输入: task_context dict                             │
│    ↓                                                 │
│  _extract_task_description() → "描述字符串"          │
│    ↓                                                 │
│  _get_task_embedding() → [float] × 1024             │
│    ├── 内存缓存命中 → 直接返回                       │
│    └── EmbeddingModelProtocol.embed() → 计算+缓存   │
│    ↓                                                 │
│  余弦相似度计算 (task × each candidate)              │
│    ↓                                                 │
│  输出: (best_candidate_id, best_score)              │
└─────────────────────────────────────────────────────┘
```

**关键特性：**
- **bge-m3 嵌入：** 1024 维向量，支持中英双语，本地部署
- **内存缓存：** MAX_CACHE_SIZE=10000，LRU 风格淘汰
- **候选注册：** 动态添加/移除 Agent/工具候选
- **优雅降级：** 无嵌入模型时返回零向量（score=0.0）

**数据模型：**

```
@dataclass
class Candidate:
    candidate_id: str          # 候选项唯一标识
    name: str                  # 候选项名称
    description: str           # 候选项描述（用于嵌入）
    embedding: list[float]     # 预计算的嵌入向量（1024维）

class EmbeddingModelProtocol(Protocol):
    async embed(texts: list[str]) → list[list[float]]
```

### 5.2 沙箱

#### 5.2.1 DockerSandboxAdapter

**文件:** `src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py`
**实现端口:** `SandboxExecutor`（`src/application/ports/sandbox_port.py`）

```
┌─────────────────────────────────────────────────────┐
│              DockerSandboxAdapter                    │
│                                                      │
│  资源限制:                                           │
│  - CPU: 1 核                                         │
│  - Memory: 512MB                                     │
│  - Network: 禁用 (network_mode="none")              │
│  - Filesystem: 隔离临时目录                          │
│                                                      │
│  生命周期:                                           │
│  start_container(session_id)                         │
│    ├── 检查是否已运行 → 幂等                          │
│    └── docker_client.containers.run(...)             │
│                                                      │
│  execute_code(session_id, code)                      │
│    ├── 检查容器状态                                   │
│    └── docker_client.exec_create/exec_start          │
│                                                      │
│  stop_container(session_id)                          │
│    ├── docker_client.get(name).remove(force=True)    │
│    └── 清理资源                                       │
│                                                      │
│  MVP 状态: mock 实现（生产环境接入 Docker SDK）      │
└─────────────────────────────────────────────────────┘
```

**演进路线：**
- **MVP:** Docker 容器级隔离（当前实现）
- **V2+:** gVisor 用户态内核（SandboxExecutor 新实现，端口不变）

#### 5.2.2 SessionNamespaceManager

**文件:** `src/infrastructure/external_services/sandbox/session_namespace_manager.py`

```
class SessionNamespaceManager:
    __init__(sandbox: SandboxExecutor | None)

    async get_or_create_namespace(session_id) → str
        # 相同 session_id 复用同一命名空间
        # 新会话创建命名空间（调用 sandbox.start_container）

    async release_namespace(session_id) → None
        # 释放命名空间（调用 sandbox.stop_container）
        # 清理 _active_sessions 记录

    get_active_sessions() → list[str]
    is_session_active(session_id) → bool
    async update_resource_usage(session_id, cpu_delta, memory_delta) → None
```

**设计约束：** 同一 session_id 的任务共享同一命名空间（会话隔离保证）。

### 5.3 快照存储

#### 5.3.1 RedisSnapshotStore

**文件:** `src/infrastructure/storage/redis/redis_snapshot_store.py`
**实现端口:** `SnapshotRepositoryProtocol`（`src/domain/ports/snapshot_repository_protocol.py`）

```
┌─────────────────────────────────────────────────────┐
│              RedisSnapshotStore                      │
│                                                      │
│  Key 格式: snapshot:{session_id}                     │
│  Field:   "latest" → JSON(to_redis_hash())          │
│  TTL:     ttl_seconds（默认 86400 = 24h）            │
│                                                      │
│  操作:                                               │
│  save(snapshot)                                      │
│    ├── HSET snapshot:{sid} latest {json}             │
│    └── EXPIRE snapshot:{sid} {ttl}                   │
│                                                      │
│  load(session_id)                                    │
│    ├── HGET snapshot:{sid} latest                    │
│    └── from_redis_hash(json.loads(data))             │
│                                                      │
│  delete(session_id)                                  │
│    └── DEL snapshot:{sid}                            │
│                                                      │
│  exists(session_id)                                  │
│    └── EXISTS snapshot:{sid}                         │
│                                                      │
│  高可用: Redis Sentinel/Cluster 主从复制             │
│  TTL 范围: 60s ~ 2592000s (30d)                      │
└─────────────────────────────────────────────────────┘
```

### 5.4 心跳调度器

#### 5.4.1 HeartbeatScheduler

**文件:** `src/infrastructure/scheduler/heartbeat_scheduler.py`

```
┌─────────────────────────────────────────────────────┐
│              HeartbeatScheduler                      │
│                                                      │
│  实现: 纯 asyncio (asyncio.create_task)              │
│  间隔: 可配置（默认 60s）                             │
│                                                      │
│  启动:                                               │
│  start()                                             │
│    └── _heartbeat_loop() [asyncio.Task]              │
│        ├── asyncio.sleep(interval)                   │
│        ├── _fire_heartbeat()                         │
│        │   ├── 生成 HeartbeatTriggered 事件          │
│        │   ├── _store_heartbeat() → Redis ZADD       │
│        │   └── publisher(event) → 事件总线           │
│        └── 循环                                      │
│                                                      │
│  Redis 跟踪:                                         │
│  Key: heartbeat:pending                              │
│  Type: Sorted Set (score=timestamp)                  │
│  TTL: 3 × interval（自动清理）                       │
│                                                      │
│  一次性调度:                                          │
│  schedule_heartbeat(id, delay, reason)               │
│    └── ZADD heartbeat:pending {id: fire_time}       │
│                                                      │
│  优雅停止:                                           │
│  stop()                                              │
│    ├── _running = False                              │
│    ├── cancel _heartbeat_task                        │
│    └── disconnect Redis pool                         │
└─────────────────────────────────────────────────────┘
```

### 5.5 配置

三个配置类均使用 `from_env()` 类方法从环境变量加载，位于 `src/infrastructure/config/`：

| 配置类 | 文件 | 关键参数 |
|--------|------|---------|
| `AutoTriggerConfig` | `auto_trigger.py` | trigger_enabled, heartbeat_interval_seconds (60s), trigger_max_retries (3) |
| `AutoRouteConfig` | `auto_route.py` | route_enabled, route_type ("mixed"), semantic_threshold (0.7), hash_ring_size (150), cache_ttl_seconds (86400) |
| `AutoExecuteConfig` | `auto_execute.py` | enabled, sandbox_type ("docker"), snapshot_ttl_seconds (86400), resource_limits |

---

## 6. 事件编排链

### 6.1 完整数据流

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         自主调用循环（事件编排链）                         │
│                                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │ 外部触发  │───▶│ Phase 1      │───▶│ Phase 2      │───▶│ Phase 3   │  │
│  │          │    │ TRIGGER      │    │ ROUTE        │    │ EXECUTE   │  │
│  └──────────┘    └──────┬───────┘    └──────┬───────┘    └─────┬─────┘  │
│       │                 │                   │                  │        │
│       │         AutoTriggered        AutoRouted          AutoExecuted  │
│       │         (REALTIME)           (REALTIME)          (RELIABLE)    │
│       │                 │                   │                  │        │
│       │                 │                   │         ┌────────▼────┐  │
│       │                 │                   │         │ Completed   │  │
│       │                 │                   │         │ Handler     │  │
│       │                 │                   │         └────────┬────┘  │
│       │                 │                   │                  │        │
│       │                 │                   │         ┌────────▼────┐  │
│       │                 │                   │         │ 业务事件分发  │  │
│       │                 │                   │         │ DocumentProc │  │
│       │                 │                   │         │ ToolExecuted │  │
│       │                 │                   │         │ AgentDecided │  │
│       │                 │                   │         └────────┬────┘  │
│       │                 │                   │                  │        │
│       │                 │                   │         ┌────────▼────┐  │
│       │◀───────────────────────────────────────────────回到 Phase 1 │  │
│       │                 │                   │         └─────────────┘  │
│  ┌────┴─────┐                                                           │
│  │ 触发源   │                                                           │
│  │ · CLI    │                                                           │
│  │ · API    │                                                           │
│  │ · 心跳   │                                                           │
│  │ · 事件   │◀── 自主调用循环的核心：业务事件回流触发下一轮              │
│  └──────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.2 链路追踪

每个事件携带 `correlation_id` 和 `causation_id`，支持全链路追踪：

```
DomainEvent (correlation_id=C1, causation_id=null)
  ↓ AutoTriggerService
AutoTriggered (correlation_id=C1, causation_id=DomainEvent.event_id)
  ↓ AutoRouteService
AutoRouted (correlation_id=C1, causation_id=AutoTriggered.event_id)
  ↓ AutoExecuteService
AutoExecuted (correlation_id=C1, causation_id=AutoRouted.event_id)
  ↓ AutoExecuteCompletedHandler
BusinessEvent (correlation_id=C1, causation_id=AutoExecuted.event_id)
```

| 字段 | 含义 | 用途 |
|------|------|------|
| `correlation_id` | 整条链路的唯一标识（首次触发时生成） | 链路聚合查询 |
| `causation_id` | 直接前驱事件 ID | 因果链重建 |
| `source_event_type` | 链路起点的原始事件类型 | 根因分析 |
| `source_event_id` | 链路起点的事件 ID | 审计追踪 |

### 6.3 事件通道映射

| 事件类型 | 通道 | 技术栈 | 语义 |
|---------|------|--------|------|
| AutoTriggered | REALTIME | Redis Pub/Sub | 尽力而为，允许丢失 |
| AutoRouted | REALTIME | Redis Pub/Sub | 尽力而为，允许丢失 |
| HeartbeatTriggered | REALTIME | Redis Pub/Sub | 尽力而为，允许丢失 |
| AutoExecuted | REALTIME | Redis Pub/Sub | 尽力而为，允许丢失 |
| DocumentProcessed | RELIABLE | PostgreSQL Outbox + RabbitMQ | 100% 可靠传输 |
| ToolExecuted | RELIABLE | PostgreSQL Outbox + RabbitMQ | 100% 可靠传输 |
| AgentDecided | RELIABLE | PostgreSQL Outbox + RabbitMQ | 100% 可靠传输 |
| RoutingDecided | REALTIME | Redis Pub/Sub | 尽力而为，允许丢失 |

### 6.4 AutoExecuted 分发机制

AutoExecuted 是技术事件与业务事件的桥接点。其 `business_event_type` 字段决定下游业务事件类型：

```
AutoExecuted.business_event_type:
│
├── "DocumentProcessed"
│   → DocumentProcessed(document_id, parse_result)
│   → 触发下一轮自主调用（文档处理 → 索引 → 检索）
│
├── "ToolExecuted"
│   → ToolExecuted(tool_id, execution_result, cost_audit)
│   → 触发下一轮自主调用（工具结果 → 分析 → 决策）
│
├── "AgentDecided"
│   → AgentDecided(agent_id, decision_result, confidence)
│   → 触发下一轮自主调用（决策 → 下一步规划）
│
└── 其他 / 空
    → 默认 ToolExecuted（容错设计）
```

**设计理由：** 使用 `business_event_type` 字段而非子类继承，因为：
1. 保持事件类型注册表（`_registry`）的扁平性
2. 避免深度继承导致的序列化/反序列化复杂性
3. 运行时可灵活添加新的业务事件类型（无需修改 AutoExecuted 类）

---

## 7. 业界对标分析

### 7.1 工作流引擎对比

| 维度 | Temporal | Cadence | Argo Workflows | Prefect | LangGraph |
|------|----------|---------|----------------|---------|-----------|
| **定位** | 分布式工作流编排 | 微服务编排（Temporal前身） | Kubernetes 原生工作流 | 数据管道编排 | Agent 推理编排 |
| **任务类型** | 长运行、可重试、有状态 | 同 Temporal | 批处理、CI/CD | 数据处理、ETL | LLM Agent、思维链 |
| **状态存储** | Cassandra/MySQL/PostgreSQL | Cassandra | Kubernetes CRD | PostgreSQL/SQLite | 内存/Redis |
| **重试策略** | 指数退避、最大次数、超时 | 同 Temporal | 策略模板 | 可配置 | 节点级配置 |
| **可视化** | Web UI | Web UI | Argo UI | Prefect Cloud | LangGraph Studio |
| **SDK** | Go/Java/Python/TS | Java/Go | YAML | Python | Python |
| **适用场景** | 企业级复杂工作流 | 遗留系统 | K8s 环境 | 数据科学团队 | LLM 应用 |

**SISYS 选型决策：Prefect + LangGraph 双引擎方案**

| 引擎 | 职责 | 原因 |
|------|------|------|
| **Prefect** | 数据管道（文档处理/RAG 索引/报告生成） | 确定性任务编排、强状态持久化、Python 原生 |
| **LangGraph** | Agent 推理（BLM 规划/Agent 协作） | 认知推理灵活性、思维链可视化、LLM 原生支持 |

**与 Temporal 的对比：**
- **选择 Prefect 而非 Temporal 的原因：**
  1. SISYS 以 Python 为主语言，Prefect 的 Python 原生支持更优
  2. 数据管道任务确定性高，无需 Temporal 的复杂分布式事务语义
  3. MVP 阶段 Prefect 部署成本更低

- **未来考虑 Temporal 的场景：**
  1. 需要跨天/跨周的长运行工作流
  2. 需要跨服务的分布式事务（Saga 补偿）
  3. 需要 Web UI 运维监控（V2+）

### 7.2 事件驱动架构对比

| 维度 | NServiceBus | Apache Kafka | RabbitMQ | Redis Pub/Sub |
|------|-------------|--------------|----------|---------------|
| **模式** | 智能总线 | 分布式日志 | 消息代理 | 发布/订阅 |
| **持久化** | 可配置 | 磁盘日志 | 可配置 | 可选（AOF） |
| **顺序保证** | 分区有序 | 分区有序 | 单队列有序 | 无 |
| **延迟** | ~ms 级 | ~ms 级 | ~ms 级 | ~μs 级 |
| **吞吐量** | 中等 | 极高（百万/s） | 高（万/s） | 高（万/s） |
| **消息回溯** | 有限 | 支持（Offset） | 不支持 | 不支持 |
| **可靠性** | 高（Outbox） | 高（复制） | 高（持久化） | 低（尽力而为） |
| **复杂度** | 高 | 高 | 中 | 低 |

**SISYS 选型决策：Redis Pub/Sub + RabbitMQ/Outbox 双通道**

| 通道 | 技术 | 用途 | 原因 |
|------|------|------|------|
| **REALTIME** | Redis Pub/Sub | 心跳、AutoTriggered、AutoRouted | 延迟最低（μs 级）、允许丢失、MVP 成本低 |
| **RELIABLE** | RabbitMQ + PostgreSQL Outbox | 业务事件、审计日志 | 100% 可靠传输、WORM 7 年归档、支持事务 |

**与 NServiceBus 的对比：**
- NServiceBus 是 .NET 生态的智能总线，SISYS 选择 Python 原生方案
- SISYS 的 Outbox 模式借鉴了 NServiceBus 的事务消息设计
- 未来可考虑引入 Kafka 替代 RabbitMQ（如需更高吞吐量）

### 7.3 沙箱隔离对比

| 维度 | Docker | gVisor | Firecracker | Kata Containers |
|------|--------|--------|-------------|-----------------|
| **隔离级别** | 容器级（共享内核） | 用户态内核 | 微 VM | 轻量 VM |
| **启动时间** | ~100ms | ~200ms | ~125ms | ~500ms |
| **内存开销** | 低（MB 级） | 低 | 中（MB 级） | 高（GB 级） |
| **安全性** | 中（内核漏洞风险） | 高 | 高 | 最高 |
| **兼容性** | 完全兼容 | 大部分兼容 | Linux only | 完全兼容 |
| **部署复杂度** | 低 | 中 | 中 | 高 |
| **适用场景** | 开发/测试/生产 | 多租户生产 | 无服务器 | 高安全需求 |

**SISYS 选型决策：Docker → gVisor 渐进式演进**

| 阶段 | 技术 | 原因 |
|------|------|------|
| **MVP** | Docker | 部署成本低、社区成熟、开发效率高 |
| **V2+** | gVisor | 安全需求提升、多租户隔离增强、无需更换端口协议 |

**演进路径：** `SandboxExecutor` 端口定义在 `application/ports/`，基础设施层提供 `DockerSandboxAdapter` 和未来的 `GvisorSandboxAdapter`，实现零代码改动切换。

### 7.4 状态管理对比

| 维度 | Redis | ZooKeeper | etcd | Consul |
|------|-------|-----------|------|--------|
| **数据模型** | Key-Value | 树形节点 | Key-Value | Key-Value |
| **一致性** | 最终一致（默认） | 强一致（ZAB） | 强一致（Raft） | 强/弱可选 |
| **延迟** | ~μs 级 | ~ms 级 | ~ms 级 | ~ms 级 |
| **TTL 支持** | 原生 | 需要实现 | 原生 | 原生 |
| **数据结构** | Hash/Set/ZSet 等 | 无 | 无 | 无 |
| **主从复制** | 支持 | 支持 | 支持 | 支持 |
| **适用场景** | 缓存/会话/队列 | 协调服务 | K8s 配置 | 服务发现 |

**SISYS 选型决策：Redis Hash**

| 需求 | 选择 Redis Hash 的原因 |
|------|----------------------|
| **低延迟** | 快照读写 P95 < 50ms 要求 |
| **TTL** | 会话状态 24h-30d 自动过期 |
| **数据结构** | Hash 字段支持部分更新（HSET） |
| **已有基础设施** | 项目已部署 Redis（语义缓存、会话状态） |
| **主从复制** | 支持 Redis Sentinel/Cluster 高可用 |

### 7.5 路由算法对比

| 算法 | 复杂度 | 一致性 | 负载均衡 | 适用场景 |
|------|--------|--------|----------|---------|
| **一致性哈希** | O(log n) | 高（节点变化影响小） | 中 | 分布式缓存、会话路由 |
| **轮询** | O(1) | 低（节点变化全重分配） | 高 | 无状态服务 |
| **加权随机** | O(1) | 低 | 高（可调权重） | 负载均衡器 |
| **语义路由** | O(n) | N/A | 取决于嵌入质量 | 智能匹配、Agent 选择 |
| **最小连接数** | O(n) | 低 | 最高 | 长连接服务 |

**SISYS 选型决策：混合路由（一致性哈希 + 语义路由）**

| 路由类型 | 场景 | 优先级 |
|---------|------|--------|
| **语义路由** | 智能匹配任务到最合适的 Agent/工具 | 高（语义匹配率 ≥ 95%） |
| **哈希路由** | 保证同一 session_id 的任务路由到同一节点 | 基础（会话一致性 100%） |
| **混合策略** | semantic 有结果时优先 semantic，否则 fallback 到 hash | 默认 |

**混合路由决策逻辑：**

```
if semantic_target and semantic_score >= threshold:
    return "semantic", semantic_target, semantic_score
elif hash_target:
    return "hash", hash_target, 1.0
else:
    return "hash", "default", 0.0
```

---

## 8. 与 UDMR/引擎集成设计

### 8.1 自主路由 vs UDMR 路由

SISYS 系统中存在两种不同层次的路由机制：

| 维度 | 自主路由（Story 1.14b） | UDMR 路由（Story 1.17） |
|------|-------------------------|------------------------|
| **路由对象** | Agent / 工具（目标选择） | 本地/云模型（模型选择） |
| **输入事件** | AutoTriggered | AutoRouted |
| **输出事件** | AutoRouted | RoutingDecided |
| **决策算法** | hash + semantic | L1 合规 → L2 评估 → L3 决策 |
| **决策字段** | route_target, route_score | selected_model, cost_estimate |
| **触发时机** | Phase 2（路由阶段） | Phase 2.5（模型选择阶段） |

**集成数据流：**

```
AutoTriggered
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│  Phase 2: 自主路由（Story 1.14b）                                   │
│  AutoRouteService._make_routing_decision()                        │
│  输出: route_type, route_target, route_score                       │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
                     AutoRouted
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
    ▼                       ▼                       ▼
┌─────────────┐    ┌─────────────────┐    ┌─────────────┐
│ Phase 2.5:  │    │ 直接执行         │    │ 未来扩展    │
│ UDMR 路由    │    │ (无需模型选择)   │    │ (其他引擎)  │
│ (Story 1.17)│    └────────┬────────┘    └─────────────┘
└──────┬──────┘             │
       │                    │
       ▼                    │
RoutingDecided              │
       │                    │
       ▼                    │
selected_model              │
       │                    │
       └────────────────────┴───────────────────────┐
                                                    │
                                                    ▼
                                            AutoExecuted
                                            (含 selected_model)
```

### 8.2 RoutingDecisionLog UDMR 扩展

`RoutingDecisionLog` 实体已预留 UDMR 扩展字段：

```
@dataclass(frozen=True)
class RoutingDecisionLog:
    # 自主路由字段（Story 1.14b）
    log_id: UUID
    task_id: str
    session_id: str
    route_type: str          # "hash" | "semantic" | "mixed"
    route_target: str        # Agent/工具 ID
    route_score: float       # 路由置信度

    # UDMR 扩展字段（Story 1.17）
    selected_model: str = ""           # UDMR 选定模型（local/cloud/具体模型名）
    cost_actual: float = 0.0           # 实际成本
    fallback_reason: str | None = None # 回退原因（timeout/unavailable/health_check_failed）
```

### 8.3 与 Prefect 集成

**职责：** 数据管道任务编排（文档处理/RAG 索引/报告生成）

**端口定义：** `WorkflowEnginePort`（Story 1.18a）

```
class WorkflowEnginePort(Protocol):
    async submit_flow(flow_name: str, parameters: dict) → str
        # 提交 Prefect flow 执行，返回 flow_run_id

    async get_flow_status(flow_run_id: str) → FlowStatus
        # 查询 flow 执行状态
```

**集成点：** `OrchestrationService`（`src/application/services/orchestration_service.py`）

```
class OrchestrationService:
    __init__(workflow_engine: WorkflowEnginePort, agent_engine: AgentEnginePort)

    async execute(task: WorkflowTask) → WorkflowResult:
        if task.task_type == "data_pipeline":
            # 路由到 Prefect
            flow_run_id = await self._workflow_engine.submit_flow(
                task.flow_name, task.parameters
            )
            return WorkflowResult(flow_run_id, status, submitted_at)
```

**自主调用与 Prefect 的协作：**

```
AutoRouted (route_target = "data_pipeline_agent")
    │
    ▼
AutoExecuteService → SandboxExecutor.execute_code()
    │
    ├── task_context["task_type"] = "data_pipeline"
    │
    └── 触发 OrchestrationService.execute(WorkflowTask)
            │
            ▼
        Prefect flow 执行
```

### 8.4 与 LangGraph 集成

**职责：** Agent 推理任务编排（BLM 规划/Agent 协作）

**端口定义：** `AgentEnginePort`（Story 1.18b）

```
class AgentEnginePort(Protocol):
    async submit_graph(graph_name: str, parameters: dict) → str
        # 提交 LangGraph graph 执行，返回 graph_run_id

    async get_graph_status(graph_run_id: str) → GraphStatus
        # 查询 graph 执行状态
```

**集成点：** 同 `OrchestrationService`

```
async execute(task: WorkflowTask) → WorkflowResult:
    if task.task_type == "agent_reasoning":
        # 路由到 LangGraph
        graph_run_id = await self._agent_engine.submit_graph(
            task.parameters["graph_name"], task.parameters
        )
        return WorkflowResult(graph_run_id, status, submitted_at)
```

### 8.5 完整集成数据流

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    自主调用 + UDMR + 引擎 完整数据流                         │
│                                                                            │
│  用户操作/CLI/API/心跳                                                      │
│       │                                                                    │
│       ▼                                                                    │
│  DomainEvent ────────────────────────────────────────────────────────────  │
│       │                     DualChannelEventBus (REALTIME)                 │
│       ▼                                                                    │
│  ┌─────────────┐                                                          │
│  │ Phase 1     │ AutoTriggerService                                       │
│  │ TRIGGER     │ → AutoTriggered {session_id, task_context}               │
│  └──────┬──────┘                                                          │
│         │                                                                  │
│         ▼                                                                  │
│  ┌─────────────┐                                                          │
│  │ Phase 2     │ AutoRouteService                                         │
│  │ ROUTE       │ → AutoRouted {route_target, route_score}                 │
│  └──────┬──────┘                                                          │
│         │                                                                  │
│         ├─────────────────────────────────────────┐                        │
│         │                                         │                        │
│         ▼                                         ▼                        │
│  ┌─────────────┐                         ┌─────────────┐                   │
│  │ Phase 2.5   │ UDMRService            │ 直接执行     │                   │
│  │ UDMR        │ L1→L2→L3 决策           │ (无UDMR)    │                   │
│  │ (Story 1.17)│                         │             │                   │
│  └──────┬──────┘                         └──────┬──────┘                   │
│         │                                       │                          │
│         ▼                                       │                          │
│  selected_model                                 │                          │
│         │                                       │                          │
│         └───────────────────┬───────────────────┘                          │
│                             │                                              │
│                             ▼                                              │
│                    ┌─────────────────┐                                     │
│                    │ Phase 3         │ AutoExecuteService                  │
│                    │ EXECUTE         │ → SandboxExecutor / Orchestration   │
│                    └────────┬────────┘                                     │
│                             │                                              │
│         ┌───────────────────┼───────────────────┐                          │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │ Prefect     │    │ LangGraph   │    │ Sandbox     │                     │
│  │ (data_pipe) │    │ (agent_reas)│    │ (code_exec) │                     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                     │
│         │                  │                  │                            │
│         └──────────────────┼──────────────────┘                            │
│                            │                                               │
│                            ▼                                               │
│                    AutoExecuted                                            │
│                    {business_event_type, execution_result}                 │
│                            │                                               │
│                            ▼                                               │
│                    AutoExecuteCompletedHandler                             │
│                    → DocumentProcessed / ToolExecuted / AgentDecided       │
│                            │                                               │
│                            ▼                                               │
│                    回到 Phase 1（自主调用循环）                              │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 错误处理与恢复

### 9.1 失败场景矩阵

| 阶段 | 失败场景 | 影响 | 处理策略 |
|------|---------|------|---------|
| Trigger | 事件发布失败 | AutoTriggered 未发出 | 日志记录，事件总线 Outbox 保证最终一致 |
| Trigger | 上下文提取失败 | session_id 为空 | 使用 "default" 兜底，触发继续 |
| Trigger | 心跳调度器 Redis 断连 | 心跳事件丢失 | Redis ZSET 自动重连，at-least-once |
| Route | 哈希路由无节点 | route_target 为空 | 返回 "default"，score=0.0 |
| Route | 语义路由无候选项 | semantic_score 为 0 | Fallback 到哈希路由 |
| Route | 语义嵌入计算失败 | 嵌入向量为零 | 余弦相似度为 0，fallback 到哈希 |
| Route | 事件发布失败 | AutoRouted 未发出 | Outbox 保证最终一致 |
| Execute | 沙箱启动失败 | 任务无法执行 | 返回 AutoExecuted(status="failed") |
| Execute | 代码执行异常 | 执行结果异常 | 返回 AutoExecuted(status="failed", error=str) |
| Execute | 快照保存失败 | 状态未持久化 | 日志警告，不影响事件发布 |
| Execute | 事件发布失败 | AutoExecuted 未发出 | Outbox 保证最终一致 |
| Completed | 业务事件发布失败 | 下游未收到 | Outbox 保证最终一致 |
| Completed | 未知 business_event_type | 事件类型不匹配 | 默认发布 ToolExecuted |

### 9.2 重试策略

**RELIABLE 通道（Outbox 模式）：**

```
事件发布失败 → OutboxEntity (status=pending)
    ↓ AsyncOutboxPoller (1s 间隔轮询)
    ↓ get_unpublished() → 重新发送
    ↓ 成功 → mark_published()
    ↓ 失败 → mark_failed() → 状态机: pending → failed → pending (重试)
    ↓ 持续失败 → failed → archived (终态)
```

**RedisRetryQueue（Redis ZSET + Lua 原子出队）：**

```
┌─────────────────────────────────────────────┐
│  RedisRetryQueue 重试流程                    │
│                                              │
│  1. 事件失败 → ZADD retry_queue {event: score=retry_time}
│  2. AsyncOutboxPoller → ZRANGEBYSCORE 0 now │
│  3. Lua 原子出队: ZPOPMIN + 检查 score ≤ now │
│  4. 重新发布                                 │
│  5. 成功 → 从 retry_queue 移除              │
│  6. 失败 → 指数退避 + 抖动:                  │
│     delay = min(base * 2^n + random_jitter, max_delay)
│     ZADD retry_queue {event: score=now+delay}
│  7. 超过最大重试次数 → DeadLetterQueue       │
└─────────────────────────────────────────────┘
```

### 9.3 死信队列

**MVP:** `InMemoryDeadLetterQueue`（进程重启后丢失，仅用于测试和开发）

**V1+:** `RedisDeadLetterQueue`（Redis ZSET + 持久化）

```
DeadLetterQueue Protocol:
    async enqueue(event, error, retry_count) → None
    async dequeue() → (event, error, retry_count) | None
```

### 9.4 状态恢复

**CheckpointSnapshot 恢复流程：**

```
┌─────────────────────────────────────────────────────┐
│              状态恢复流程                             │
│                                                      │
│  1. 任务执行前: CheckpointSnapshot 保存               │
│     state_data = {execution_result, route_target,    │
│                   route_score, route_type}            │
│     state_version 自动递增（乐观锁）                   │
│                                                      │
│  2. 中断发生:                                        │
│     ├── 沙箱崩溃                                     │
│     ├── 进程重启                                     │
│     └── 网络分区                                     │
│                                                      │
│  3. 恢复触发:                                        │
│     ├── HeartbeatTriggered (wake_reason="system_recovery")
│     └── 手动 CheckpointRecovery 命令                 │
│                                                      │
│  4. 恢复流程:                                        │
│     ├── snapshot_repo.load(session_id)               │
│     ├── CheckpointSnapshot.state_data 读取           │
│     ├── 从中断点继续执行                              │
│     └── 发布恢复事件（CheckpointRecovered）           │
│                                                      │
│  5. 双模式恢复:                                      │
│     ├── Replay: 从检查点重放所有后续步骤              │
│     └── Override: 仅恢复指定状态（需人工确认）        │
└─────────────────────────────────────────────────────┘
```

### 9.5 幂等性保证

**DualIdempotencyChecker（双通道幂等检查）：**

```
┌─────────────────────────────────────────────────────┐
│              幂等性保证                               │
│                                                      │
│  L1: Redis SET NX (高性能)                           │
│  Key: processed_event:{event_id}                     │
│  TTL: 7 天                                           │
│  成功 → 事件未处理过 → 继续                          │
│  失败 → 事件已处理 → 跳过                            │
│                                                      │
│  L2: PostgreSQL INSERT ON CONFLICT DO NOTHING         │
│  Table: processed_events                             │
│  UNIQUE(event_id)                                    │
│  双重保证：即使 Redis 不可用也能保证幂等              │
└─────────────────────────────────────────────────────┘
```

---

## 10. 性能与可靠性设计

### 10.1 延迟目标

```
┌──────────────────────────────────────────────────────────────┐
│                     延迟预算分解                               │
│                                                              │
│  触发阶段 (P95 < 10ms):                                      │
│  ├── 事件接收 + 入队         ~0.1ms  (queue.Queue.put)       │
│  ├── 上下文提取              ~0.5ms  (dict 操作)             │
│  ├── AutoTriggered 构造      ~0.1ms  (dataclass 实例化)      │
│  └── Redis Pub/Sub 发布      ~5ms    (网络 RTT)             │
│                                                              │
│  路由阶段 (P95 < 50ms):                                      │
│  ├── 事件反序列化            ~1ms    (from_dict)             │
│  ├── 哈希路由                ~0.1ms  (FNV-1a + 二分查找)     │
│  ├── 语义路由                ~20ms   (嵌入计算 + 相似度)      │
│  │   ├── 缓存命中           ~0.1ms                           │
│  │   └── 缓存未命中         ~20ms   (bge-m3 推理)           │
│  ├── AutoRouted 构造         ~0.1ms                           │
│  └── Redis Pub/Sub 发布      ~5ms                            │
│                                                              │
│  执行阶段 (P95 < 100ms):                                     │
│  ├── 沙箱启动                ~50ms   (Docker create/start)   │
│  │   └── 已运行:             ~0ms    (幂等跳过)              │
│  ├── 代码执行                ~30ms   (容器内执行)            │
│  ├── 快照保存                ~5ms    (Redis HSET + EXPIRE)   │
│  ├── AutoExecuted 构造       ~0.1ms                           │
│  └── Redis Pub/Sub 发布      ~5ms    (网络 RTT)              │
└──────────────────────────────────────────────────────────────┘
```

### 10.2 吞吐量设计

| 阶段 | 目标吞吐量 | 关键瓶颈 | 优化策略 |
|------|-----------|---------|---------|
| Trigger | 1000 events/s | Redis Pub/Sub 发布 | 并发处理（MAX_CONCURRENT_TASKS=100） |
| Route | 1000 decisions/s | 语义嵌入计算 | 嵌入缓存（MAX_CACHE_SIZE=10000） |
| Execute | 100 executions/s | 沙箱创建 | 会话复用（session_id 命名空间） |

### 10.3 缓存策略

```
┌──────────────────────────────────────────────────────────────┐
│                     缓存层级                                  │
│                                                              │
│  L1: 语义嵌入缓存（SemanticRouter._embedding_cache）          │
│  ├── Key: 描述字符串                                         │
│  ├── Value: [float] × 1024 嵌入向量                          │
│  ├── 容量: MAX_CACHE_SIZE = 10000                            │
│  └── 淘汰: LRU 风格（新增时检查容量）                         │
│                                                              │
│  L2: 沙箱容器缓存（DockerSandboxAdapter._running_containers）│
│  ├── Key: session_id                                         │
│  ├── Value: bool (running)                                   │
│  └── 策略: 幂等复用（start_container 检查状态）               │
│                                                              │
│  L3: Redis 快照缓存（RedisSnapshotStore）                     │
│  ├── Key: snapshot:{session_id}                              │
│  ├── Field: "latest" → JSON                                  │
│  ├── TTL: 86400s (24h) ~ 2592000s (30d)                      │
│  └── 高可用: Redis Sentinel/Cluster 主从复制                  │
└──────────────────────────────────────────────────────────────┘
```

### 10.4 并发控制

**AutoTriggerHandler 并发模型：**

```
┌──────────────────────────────────────────────────────────────┐
│  同步事件处理器                   异步领域服务                 │
│  (Event Bus callback)            (AutoTriggerService)        │
│                                                              │
│  handler(event) ──queue.Queue──▶ _worker_loop()              │
│       │                          │                           │
│       │                          ├── asyncio event loop      │
│       │                          │   (独立线程)              │
│       │                          │                           │
│       │                          ├── create_task()           │
│       │                          │   per event               │
│       │                          │                           │
│       │                          ├── wait_for(timeout=300s)  │
│       │                          │   per task                │
│       │                          │                           │
│       │                          └── wait(FIRST_COMPLETED)  │
│       │                              when MAX_CONCURRENT     │
│       │                              tasks reached           │
│       │                                                       │
│       └── 非阻塞入队，立即返回                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. 组合根与 DI 注册

### 11.1 组件装配图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Composition Root                                  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Singleton 组件                                                    │  │
│  │                                                                    │  │
│  │  DualChannelEventBus (Facade)                                      │  │
│  │  ├── implements EventPublisher (Domain Port)                       │  │
│  │  ├── implements EventSubscriber (Application Port)                 │  │
│  │  ├── ChannelRouter (共享实例)                                      │  │
│  │  ├── RedisEventBus (REALTIME)                                      │  │
│  │  └── RabbitMQEventBus + OutboxRepository (RELIABLE)                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Domain Services                                                   │  │
│  │                                                                    │  │
│  │  AutoTriggerService                                                │  │
│  │  └── publisher = DualChannelEventBus (注入)                        │  │
│  │                                                                    │  │
│  │  AutoRouteService                                                  │  │
│  │  ├── publisher = DualChannelEventBus (注入)                        │  │
│  │  ├── hash_router = HashRouter (注入)                               │  │
│  │  └── semantic_router = SemanticRouter (注入)                       │  │
│  │                                                                    │  │
│  │  AutoExecuteService                                                │  │
│  │  ├── sandbox = DockerSandboxAdapter (注入)                         │  │
│  │  └── snapshot_repo = RedisSnapshotStore (注入)                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Application Handlers                                              │  │
│  │                                                                    │  │
│  │  AutoTriggerHandler                                                │  │
│  │  ├── auto_trigger_service = AutoTriggerService (注入)              │  │
│  │  └── event_listener = InMemoryEventListener (注入)                 │  │
│  │                                                                    │  │
│  │  AutoRouteHandler                                                  │  │
│  │  ├── auto_route_service = AutoRouteService (注入)                  │  │
│  │  └── publisher = DualChannelEventBus (注入)                        │  │
│  │                                                                    │  │
│  │  AutoExecuteCompletedHandler                                       │  │
│  │  └── publisher = DualChannelEventBus (注入)                        │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Infrastructure Adapters                                           │  │
│  │                                                                    │  │
│  │  HashRouter(nodes=[...], virtual_nodes=150)                        │  │
│  │  SemanticRouter(candidates=[...], embedding_model=bge_m3)         │  │
│  │  DockerSandboxAdapter()                                            │  │
│  │  SessionNamespaceManager(sandbox=DockerSandboxAdapter)             │  │
│  │  RedisSnapshotStore(redis_client=aioredis.Redis(...))              │  │
│  │  HeartbeatScheduler(redis_config=RedisConfig(...), interval=60)    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Configuration                                                     │  │
│  │                                                                    │  │
│  │  AutoTriggerConfig.from_env()                                      │  │
│  │  AutoRouteConfig.from_env()                                        │  │
│  │  AutoExecuteConfig.from_env()                                      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 11.2 启动序列

```
App Lifespan Event (FastAPI startup)
    │
    ├── 1. 加载配置
    │   ├── AutoTriggerConfig.from_env()
    │   ├── AutoRouteConfig.from_env()
    │   └── AutoExecuteConfig.from_env()
    │
    ├── 2. 初始化基础设施适配器
    │   ├── Redis 连接池 (aioredis.ConnectionPool)
    │   ├── RabbitMQ 连接 (aio_pika)
    │   ├── HashRouter(nodes=配置节点列表)
    │   ├── SemanticRouter(candidates=已注册Agent/工具)
    │   ├── DockerSandboxAdapter()
    │   └── RedisSnapshotStore(redis_client)
    │
    ├── 3. 组装领域服务
    │   ├── AutoTriggerService(publisher=event_bus)
    │   ├── AutoRouteService(publisher, hash_router, semantic_router)
    │   └── AutoExecuteService(sandbox, snapshot_repo)
    │
    ├── 4. 注册事件处理器
    │   ├── AutoTriggerHandler.register_handlers() → 注册 12 种事件
    │   └── （AutoRouteHandler/AutoExecuteCompletedHandler 通过事件总线订阅）
    │
    ├── 5. 启动后台任务
    │   ├── HeartbeatScheduler.start() → 心跳循环
    │   └── AsyncOutboxPoller.start() → Outbox 轮询
    │
    └── 6. 应用就绪
```

### 11.3 关闭序列

```
App Lifespan Event (FastAPI shutdown)
    │
    ├── 1. HeartbeatScheduler.stop()
    │   └── cancel _heartbeat_task + disconnect Redis pool
    │
    ├── 2. AutoTriggerHandler.stop()
    │   └── _running=False + join worker thread (timeout=5s)
    │
    ├── 3. AsyncOutboxPoller.stop()
    │   └── cancel polling task
    │
    └── 4. 清理资源
        ├── 关闭 RabbitMQ 连接
        ├── 关闭 Redis 连接池
        └── 停止 Docker 容器（如有）
```

---

## 12. 后续 Story 扩展指南

### 12.1 Story 1.15a/b：外部化记忆

**集成点：** MemoryChanged 事件 + CheckpointSnapshot

```
扩展路径:
├── Story 1.15a (L1 显式确认压缩)
│   ├── 新增: MemoryCompressed 事件
│   ├── 集成: AutoTriggerHandler 注册 MemoryChanged 事件
│   └── 使用: CheckpointSnapshot 保存压缩前原始状态
│
└── Story 1.15b (L0 入口 + 六层存储协同)
    ├── 新增: MemoryChangedHandler (Application Layer)
    ├── 集成: 事件总线 MemoryChanged → RELIABLE 通道
    └── 使用: 六层存储（L0 文件系统 → L1 Redis → L2 PostgreSQL → L3 Qdrant → L4 MinIO → L5 Neo4j）
```

### 12.2 Story 1.17：UDMR 基础路由

**集成点：** RoutingDecisionLog + UDMRTask + AutoRouted 事件

```
扩展路径:
├── 新增端口 (domain/ports/):
│   ├── ComplianceGateway (L1 合规检查)
│   ├── ComplexityAssessor (L2 复杂度评估)
│   └── RouterExecutor (L3 路由决策)
│
├── 新增服务 (domain/services/):
│   └── UDMRService (三层决策编排)
│
├── 扩展实体:
│   └── RoutingDecisionLog.selected_model (已预留字段)
│
├── 新增事件:
│   └── RoutingDecided (routing_events.py, 已存在)
│
└── 集成方式:
    AutoRouted → UDMRService.decide(UDMRTask)
                → RoutingDecided {selected_model, cost_estimate}
                → AutoExecuted (含 selected_model)
```

### 12.3 Story 1.18a/b：引擎集成

**集成点：** OrchestrationService + WorkflowEnginePort + AgentEnginePort

```
扩展路径:
├── Story 1.18a (Prefect 工作流引擎)
│   ├── 新增端口: WorkflowEnginePort (application/ports/)
│   ├── 新增适配器: PrefectAdapter (infrastructure/)
│   ├── 集成: OrchestrationService.execute(task_type="data_pipeline")
│   └── 触发: AutoExecuted 中 task_context["task_type"] 路由
│
└── Story 1.18b (LangGraph Agent 编排)
    ├── 新增端口: AgentEnginePort (domain/ports/)
    ├── 新增适配器: LangGraphAdapter (infrastructure/)
    ├── 集成: OrchestrationService.execute(task_type="agent_reasoning")
    └── 触发: AutoExecuted 中 task_context["task_type"] 路由
```

### 12.4 Epic 4：战略工具箱

**集成点：** SemanticRouter 候选注册 + SandboxExecutor

```
扩展路径:
├── 23 种工具注册
│   ├── SemanticRouter.add_candidate(Candidate)
│   │   candidate_id = "tool-pestel" / "tool-swot" / ...
│   │   description = 工具功能描述（用于语义匹配）
│   │   embedding = bge-m3(description) 预计算
│   │
│   └── 匹配: task_context → SemanticRouter.route() → tool_id
│
├── 工具链编排 (DAG)
│   ├── AutoRouted.route_target = tool_id
│   ├── AutoExecuteService → SandboxExecutor.execute_code(tool_code)
│   └── CheckpointSnapshot 保存中间状态
│
└── Schema 验证
    └── task_context["input_schema"] / task_context["output_schema"]
```

### 12.5 Epic 5：Agent 协作

**集成点：** session_id 隔离 + CheckpointSnapshot + 公共黑板

```
扩展路径:
├── 多 Agent 实例化
│   ├── SemanticRouter.add_candidate(Candidate)
│   │   candidate_id = "agent-ceo" / "agent-cfo" / ...
│   │
│   └── 路由: AutoTriggered → SemanticRouter.route() → agent_id
│
├── 会话隔离
│   ├── HashRouter.route(session_id) → 同一节点
│   ├── SessionNamespaceManager → 同一命名空间
│   └── CheckpointSnapshot → 会话状态恢复
│
├── 公共黑板
│   ├── L1 Redis: public_blackboard:{topic} (TTL 1h)
│   └── Agent 间中间结论交换
│
└── 弹性隔离 (EIP)
    └── IsolationLevelSwitched 事件触发隔离等级变更
```

### 12.6 扩展检查清单

开发后续 Story 时，应检查以下合规项：

| 检查项 | 验证方法 |
|--------|---------|
| Domain 层零外部依赖 | `grep -r "import langgraph\|import prefect\|import redis" src/domain/` |
| 端口协议定义正确 | Protocol + @runtime_checkable |
| 事件类型注册 | `event_type: str = field(default="...", init=False)` |
| 事件通道映射正确 | ChannelRouter.DEFAULT_MAPPINGS 更新 |
| 测试覆盖达标 | Domain ≥ 90%, Application ≥ 85%, Infrastructure ≥ 75% |
| 架构测试通过 | 依赖方向检查、循环依赖检查 |
| 现有测试回归 | 2146+ 并行回归测试全部通过 |
