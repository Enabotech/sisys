# SISYS 事务子系统重构详细设计与执行方案

> **文档版本：** 1.0.0
> **创建日期：** 2026-05-18
> **状态：** 待审批
> **维护者：** Agimtech
> **前置文档：** `sisys-eda-unitofwork-design.md` (v1.0.6, Phase 1 已完成)
> **关联文档：** `architecture.md` (v8.3.1), `arch-appendix.md` (附录J Saga 设计)

---

## 1. 背景与目标

### 1.1 问题陈述

SISYS 系统事务子系统已完成 Phase 1 基础设施建设（UnitOfWork Protocol + PostgreSQLUnitOfWork），但存在以下关键问题：

| # | 问题 | 严重程度 | 影响 |
|---|------|---------|------|
| P1 | Session 生命周期双重管理冲突 | **高** | SessionMiddleware 和 UoW 同时管理 commit/close，生产环境可能抛异常 |
| P2 | UnitOfWork 未在 DI 容器注册 | **高** | EventHandler 无法通过依赖注入获取 UoW |
| P3 | Saga 仅停留在设计文档 | **中** | arch-appendix.md 附录J 的 10 个跨库事务场景无代码实现 |
| P4 | 事务隔离级别未配置 | **中** | 全部使用默认 READ COMMITTED，关键审计场景无法保证强一致性 |
| P5 | OutboxRepository 构造器不一致 | **低** | 实际无参构造（依赖 ContextVar），设计文档描述有参构造 |

### 1.2 设计目标

| 目标 | 度量标准 |
|------|---------|
| 事务边界显式化 | 所有跨表写入操作必须通过 UoW |
| Session 生命周期无冲突 | Middleware 和 UoW 职责分离，无双重 commit/close |
| 六边形架构合规 | 领域层零依赖，依赖方向正确 |
| 满足后续 EPICS/STORY 需求 | 支持 Saga 场景 S01-S10 |
| 渐进式迁移 | 不破坏现有功能，分阶段落地 |

---

## 2. 现有代码深度分析

### 2.1 当前架构全景

```
                    ┌─────────────────────────────────┐
                    │      HTTP Request / Background   │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │     SessionMiddleware            │
                    │  create session → set ContextVar │
                    │  dispatch → commit/rollback/close│
                    │  reset ContextVar                │
                    └────────────┬────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼──────┐  ┌───────▼───────┐  ┌───────▼────────┐
    │  Repository    │  │  OutboxRepo   │  │  EventStore    │
    │ (PostgreSQL    │  │ (PostgreSQL   │  │ (PostgreSQL    │
    │  Adapter)      │  │  OutboxRepo)  │  │  EventStore)   │
    │  get_session() │  │  get_session()│  │  get_session() │
    └────────────────┘  └───────────────┘  └────────────────┘
              │                  │                   │
              └──────────────────┼──────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │     ContextVar (session_context) │
                    │     _session_ctx: ContextVar     │
                    └─────────────────────────────────┘
```

**问题可视化**：当 UseCase 使用 `async with uow:` 时：

```
SessionMiddleware.dispatch()
    └── handler uses: async with uow:
            ├── uow.__aenter__() → session.begin()
            ├── ... business + outbox ...
            └── uow.__aexit__()  → session.commit() + session.close()  ← UoW 关闭
    └── middleware finally → session.close() + reset_session()           ← 重复关闭!
```

### 2.2 Session 生命周期冲突分析

**当前 PostgreSQLUnitOfWork.__aexit__**（`postgresql_unit_of_work.py:109-141`）:

```python
async def __aexit__(self, ...):
    if exc_type is not None:
        await self.rollback()
    elif not self._committed and not self._rolled_back:
        await self.commit()
    await self.close()      # ← 问题根源：UoW 关闭了 session
    return False
```

**当前 SessionMiddleware.dispatch**（`session_middleware.py:46-67`）:

```python
async def dispatch(self, request, call_next):
    session = self._factory()
    token = set_session(session)
    try:
        response = await call_next(request)  # handler 在此执行
        await session.commit()               # ← 可能已被 UoW commit
        return response
    except Exception:
        await session.rollback()             # ← 可能已被 UoW rollback
        raise
    finally:
        await session.close()                # ← 可能已被 UoW close
        reset_session(token)
```

**冲突矩阵**：

| 场景 | Middleware | UoW | 结果 |
|------|-----------|-----|------|
| 不使用 UoW | commit + close | - | ✅ 正常 |
| 使用 UoW | commit + close | commit + close | ❌ 双重 commit + 双重 close |
| 使用 UoW + 异常 | rollback + close | rollback + close | ❌ 双重 rollback + 双重 close |

### 2.3 UnitOfWork DI 注册缺失

`composition_root.py` 中注册了 `session_factory`、`outbox_repo`、`outbox_poller` 等组件，但**未注册**：
- `PostgreSQLUnitOfWork` 或其工厂
- `UnitOfWork` Protocol 的实现绑定

EventHandler 无法通过 DI 获取 UoW，只能手动 `PostgreSQLUnitOfWork()`，违反"依赖接口而非实现"原则。

### 2.4 Saga 设计 vs 实现差距

`arch-appendix.md` 附录J 定义了：
- `SagaStatus` / `SagaStep` / `SagaContext` / `SagaOrchestrator` 类设计
- 10 个跨库事务场景 S01-S10
- 混合式 Saga 模式（编排式 + 编舞式）
- 补偿事务设计原则

但 `src/infrastructure/saga/` 目录**不存在**，所有代码未实现。

---

## 3. 业界最佳实践对标

### 3.1 四大框架事务管理模式

| 框架 | UoW 模式 | Outbox 集成 | Saga 支持 | 适用评估 |
|------|---------|-------------|-----------|---------|
| **Eventuate Tram** | AggregateRepository + Transaction | 同 JDBC transaction 写 outbox | SagaOrchestrator 自动编排 | ⭐⭐⭐ 最契合 |
| **Axon Framework** | UnitOfWork 一等公民 | 无内置 Outbox（Axon Server 替代） | SagaManager + AssociationResolver | ⭐⭐ 架构参考 |
| **NServiceBus** | IUnitOfWork + Outbox pipeline | 自动管理事务边界 | NServiceBus.Saga 基类 | ⭐⭐ 生产验证 |
| **Spring Cloud Stream** | @Transactional 注解 | 无内置 Outbox | Spring Cloud Saga（社区） | ⭐ 侵入性强 |

### 3.2 SQLAlchemy 2.0 AsyncSession 最佳实践

**官方推荐**（[SQLAlchemy 2.0 Async Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)）：

```python
# 模式 1: session.begin() 管理事务
async with async_session() as session:
    async with session.begin():
        # 所有操作在同一事务
        await session.execute(...)
    # session.begin() 块退出时自动 commit/rollback
# session 退出时自动 close

# 模式 2: autoflush + 显式 commit
async with async_session() as session:
    await session.execute(...)
    await session.commit()  # 显式提交
# session 退出时自动 close
```

**关键配置**：
- `expire_on_commit=False` — 避免延迟加载问题（已配置 ✅）
- `async_sessionmaker` 工厂模式（已配置 ✅）
- 避免嵌套 session.begin() — 使用 begin_nested() 创建 savepoint

### 3.3 Transactional Outbox 模式最佳实践

| 实践 | 说明 | SISYS 现状 |
|------|------|-----------|
| 业务表 + outbox 同事务写入 | 避免 dual-write 问题 | ✅ 同一 session |
| 后台 Poller 独立事务轮询 | 与业务事务解耦 | ✅ session_context() |
| 幂等消费 | 消费者处理重复消息 | ✅ DualIdempotencyChecker |
| Outbox 表清理 | 防止无限增长 | ❌ 未实现 |
| 指数退避重试 | 失败后渐进重试 | ⚠️ AsyncOutboxPoller 无退避 |

### 3.4 本系统最优方案选择

**核心决策**：采用 Eventuate Tram 模式为核心参考，结合 SQLAlchemy 2.0 异步特性：

```
业务操作 + Outbox 写入 → 同一 AsyncSession → 同一事务 → 原子提交
                                    ↓
AsyncOutboxPoller → 独立 session_context() → 轮询 → RabbitMQ 发布
                                    ↓
幂等性保证 → DualIdempotencyChecker → Redis + PostgreSQL 双写
```

---

## 4. 目标架构设计

### 4.1 核心设计决策

#### 决策 D1: Session 生命周期职责分离

**规则**：Session 生命周期由外层 scope（Middleware 或 session_context）管理，UoW 只管理事务边界。

| 职责 | SessionMiddleware | session_context() | UoW |
|------|------------------|-------------------|-----|
| 创建 session | ✅ | ✅ | ❌ |
| 设置 ContextVar | ✅ | ✅ | ❌ |
| begin() | ❌ | ❌ | ✅ |
| commit() | ✅（兜底） | ✅ | ✅ |
| rollback() | ✅（兜底） | ✅ | ✅ |
| close() | ✅ | ✅ | ❌ |
| 重置 ContextVar | ✅ | ✅ | ❌ |

**Why**: UoW 不应拥有 session 生命周期，否则与外层管理器冲突。UoW 是事务边界的协调器，不是 session 的所有者。

**How**: 修改 PostgreSQLUnitOfWork.__aexit__ 移除 close() 调用。

#### 决策 D2: UoW 工厂模式 + DI 注册

**规则**：通过 DI 容器注册 `UnitOfWorkFactory`，每次创建新 UoW 实例。

```python
# composition_root.py
register_port(
    name="uow_factory",
    interface=Callable[[], UnitOfWork],
    impl=lambda resolver: PostgreSQLUnitOfWork,
    lifetime=Lifetime.TRANSIENT,
)

# EventHandler 使用
class SomeHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self._uow_factory = uow_factory

    async def handle(self, event):
        uow = self._uow_factory()
        async with uow:
            ...
```

**Why**: UoW 是短生命周期（每次请求/操作），不适合 SINGLETON。工厂模式允许 EventHandler 延迟创建。

#### 决策 D3: Middleware 适配 UoW 模式

**规则**：Middleware 不再主动 commit/rollback。改为：
- 如果 handler 内使用了 UoW → session 已 commit/rollback，Middleware 只做 close + reset
- 如果 handler 未使用 UoW → Middleware 保持原有 commit/rollback 逻辑

```python
# 通过标记位检测 UoW 是否已管理事务
async def dispatch(self, request, call_next):
    session = self._factory()
    token = set_session(session)
    uow_managed = False
    set_uow_flag(False)  # ContextVar 标记
    try:
        response = await call_next(request)
        if not get_uow_flag():
            await session.commit()
        return response
    except Exception:
        if not get_uow_flag():
            await session.rollback()
        raise
    finally:
        await session.close()
        reset_session(token)
```

**Why**: 向后兼容。未使用 UoW 的 handler 保持原有行为，使用 UoW 的 handler 由 UoW 管理事务。

#### 决策 D4: Saga 基础设施实现

**规则**：实现 `src/infrastructure/saga/` 模块，包含：
- `SagaStep` (ABC) — 步骤抽象
- `SagaContext` — 执行上下文
- `SagaOrchestrator` — 编排器
- `SagaRepository` — 状态持久化

SagaStep 与 UoW 集成：每个 Step 在独立 UoW 内执行，Step 失败触发补偿。

#### 决策 D5: 事务隔离级别配置

**规则**：在 PostgreSQLManager 中支持按场景配置隔离级别：

| 场景 | 隔离级别 | 理由 |
|------|---------|------|
| 一般 CRUD | READ COMMITTED（默认） | 性能与一致性平衡 |
| 审计写入（S02-S05） | SERIALIZABLE | 防止审计日志并发写入冲突 |
| Checkpoint 保存（S03） | REPEATABLE READ | 防止快照读写冲突 |
| Outbox 轮询 | READ COMMITTED | 无特殊要求 |

### 4.2 目标架构全景

```
┌──────────────────────────────────────────────────────────────────────┐
│                       HTTP Request                                   │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  SessionMiddleware                                            │  │
│  │  职责: create session → set ContextVar → close → reset       │  │
│  │  不负责: commit/rollback（由 UoW 或 Middleware 兜底处理）     │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  Application Layer (EventHandler / UseCase)                    │  │
│  │                                                                │  │
│  │  uow = uow_factory()                                           │  │
│  │  async with uow:                                               │  │
│  │      ├── business_repo.save(entity)    # 同一 session          │  │
│  │      ├── outbox_repo.save(event)       # 同一 session          │  │
│  │      └── event_store.append(event)     # 同一 session          │  │
│  │  # uow.__aexit__: commit or rollback (no close)                │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  Infrastructure Layer                                          │  │
│  │                                                                │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐   │  │
│  │  │ PostgreSQL   │ │ Outbox       │ │ EventStore           │   │  │
│  │  │ Adapter      │ │ Repository   │ │ (原始 SQL)           │   │  │
│  │  │ get_session()│ │ get_session()│ │ get_session()        │   │  │
│  │  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘   │  │
│  │         │                │                     │               │  │
│  │         └────────────────┼─────────────────────┘               │  │
│  │                          │                                     │  │
│  │         ┌────────────────▼────────────────┐                    │  │
│  │         │  ContextVar (session_context)   │                    │  │
│  │         │  session 由 Middleware 创建      │                    │  │
│  │         └─────────────────────────────────┘                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Background Tasks                                              │  │
│  │                                                                │  │
│  │  AsyncOutboxPoller:                                            │  │
│  │    session_context(factory) → poll_once → publish → commit     │  │
│  │                                                                │  │
│  │  SagaOrchestrator:                                             │  │
│  │    step_1 (uow_1) → step_2 (uow_2) → ... → compensate         │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 UnitOfWork 使用模式（重构后）

```python
# === HTTP 请求场景 ===
# SessionMiddleware 创建 session → handler 使用 UoW → Middleware close session

class DocumentProcessedHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self._uow_factory = uow_factory

    async def handle(self, event: DocumentProcessed) -> None:
        uow = self._uow_factory()
        async with uow:                                    # begin()
            business_repo = SomeRepository(uow.session)    # 同一 session
            outbox_repo = PostgreSQLOutboxRepository(uow.session)

            await business_repo.update(entity)
            await outbox_repo.save(domain_event)
        # uow.__aexit__: commit (no close!)
        # SessionMiddleware.finally: close() + reset()

# === 后台任务场景 ===
# 使用 session_context() 创建独立 session

async def background_task():
    factory = resolver.resolve("session_factory")
    async with session_context(factory):
        uow = PostgreSQLUnitOfWork()
        async with uow:
            await some_repo.save(entity)
            await outbox_repo.save(event)
    # session_context().__aexit__: commit + close + reset
```

### 4.4 Saga 执行器与 UoW 集成

```
SagaOrchestrator.execute()
    ├── Step 1: UploadDocument
    │   └── async with uow_1:  (独立事务)
    │       ├── minio.put_object(file)
    │       └── postgres.save_metadata()
    │
    ├── Step 2: GenerateEmbedding
    │   └── async with uow_2:  (独立事务)
    │       ├── qdrant.upsert(vector)
    │       └── postgres.update_index_status()
    │
    └── [失败] → compensate:
        ├── Step 2.compensate: async with uow_c2:
        │   └── qdrant.delete(vector_id)
        └── Step 1.compensate: async with uow_c1:
            ├── postgres.delete_metadata()
            └── minio.remove_object(file_id)
```

每个 SagaStep 在独立 UoW 中执行，失败时按逆序补偿。补偿操作也通过 UoW 保证原子性。

---

## 5. 分阶段执行计划

### Phase 1: Session 生命周期治理 + UoW 完善

**目标**：解决 P1（双重管理冲突）和 P2（DI 注册缺失）。

- [ ] **Task 1.1**: 修改 `PostgreSQLUnitOfWork.__aexit__` 移除 `await self.close()` 调用
  - 文件: `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py:140`
  - UoW 只管理 begin/commit/rollback，不管理 close
  - close 仍保留为公共方法，供需要显式关闭的场景调用

- [ ] **Task 1.2**: 添加 UoW 事务管理标记位
  - 文件: `src/infrastructure/storage/postgresql/session_context.py`
  - 新增 `_uow_managed_ctx: ContextVar[bool]`
  - 新增 `mark_uow_managed()` / `is_uow_managed()` 辅助函数
  - UoW.__aexit__ 调用 `mark_uow_managed(True)` 标记事务已管理

- [ ] **Task 1.3**: 重构 `SessionMiddleware` 适配 UoW 模式
  - 文件: `src/infrastructure/middleware/session_middleware.py`
  - 正常路径: 检查 `is_uow_managed()` → 已管理则跳过 commit/rollback
  - 异常路径: 检查标记 → 未管理则 rollback
  - finally: 始终 close + reset（不受 UoW 影响）

- [ ] **Task 1.4**: 修改 `UnitOfWork` Protocol 移除 `close()` 方法
  - 文件: `src/domain/ports/unit_of_work.py`
  - close() 不属于事务边界接口，从 Protocol 中移除
  - PostgreSQLUnitOfWork 保留 close() 作为实现细节

- [ ] **Task 1.5**: 注册 `UnitOfWorkFactory` 到 DI 容器
  - 文件: `src/composition_root.py`
  - 注册 `uow_factory` 端口，接口为 `Callable[[], UnitOfWork]`
  - 实现为 `PostgreSQLUnitOfWork` 类本身（每次调用创建新实例）

- [ ] **Task 1.6**: 修复 `PostgreSQLOutboxRepository` 构造器
  - 文件: `src/infrastructure/messaging/outbox/outbox_repository.py`
  - 保持无参构造（通过 get_session() 获取 session）
  - 与 PostgreSQLAdapter 保持一致模式

- [ ] **Task 1.7**: 更新 UoW 单元测试
  - 文件: `tests/unit/infrastructure/messaging/unit_of_work/test_postgresql_unit_of_work.py`
  - 验证 __aexit__ 不调用 close()
  - 验证 mark_uow_managed() 标记设置

- [ ] **Task 1.8**: 更新 SessionMiddleware 测试
  - 文件: `tests/unit/infrastructure/middleware/test_session_middleware.py`
  - 验证 UoW 管理后 Middleware 不重复 commit
  - 验证 UoW 未使用时 Middleware 正常 commit

- [ ] **Task 1.9**: 更新架构验证测试
  - 文件: `tests/unit/infrastructure/messaging/unit_of_work/test_uow_transaction_boundary.py`
  - 添加 UoW 不调用 close 的验证
  - 添加 Session 与 UoW 职责分离的验证

**完成标准**：
- [ ] 所有现有测试通过
- [ ] UoW 不调用 close()，Middleware 负责关闭
- [ ] UoW 通过 DI 工厂获取
- [ ] 使用 UoW 和不使用 UoW 两种路径均正常工作

---

### Phase 2: Outbox 完善 + 事务隔离配置

**目标**：解决 P4（隔离级别）和 Outbox 运维能力。

- [ ] **Task 2.1**: 实现 Outbox 表清理策略
  - 文件: `src/infrastructure/messaging/outbox/outbox_processor.py`（或新文件）
  - 定期清理已发布超过 N 天的 outbox 记录
  - 配置参数: `cleanup_threshold_days`、`cleanup_batch_size`

- [ ] **Task 2.2**: AsyncOutboxPoller 添加指数退避重试
  - 文件: `src/infrastructure/messaging/outbox/outbox_processor.py`
  - 发布失败后使用指数退避（base=1s, max=60s, factor=2）
  - 超过 max_retries 后标记为 archived（终态）

- [ ] **Task 2.3**: 配置 PostgreSQL 事务隔离级别
  - 文件: `src/infrastructure/storage/postgresql/postgresql_manager.py`
  - 新增 `get_session_with_isolation(level)` 方法
  - 支持 READ_COMMITTED / REPEATABLE_READ / SERIALIZABLE
  - UoW 工厂支持指定隔离级别

- [ ] **Task 2.4**: 实现审计场景专用 UoW
  - 文件: `src/infrastructure/messaging/unit_of_work/audit_unit_of_work.py`
  - 使用 SERIALIZABLE 隔离级别
  - 用于 S02-S05 强一致性场景

- [ ] **Task 2.5**: 编写 Outbox 清理和重试测试
  - 验证清理策略不影响 pending 事件
  - 验证指数退避重试逻辑

**完成标准**：
- [ ] Outbox 已发布记录可定期清理
- [ ] 发布失败有指数退避重试
- [ ] 支持 SERIALIZABLE 隔离级别

---

### Phase 3: Saga 基础设施实现

**目标**：解决 P3，实现 Saga 执行器基础框架。

- [ ] **Task 3.1**: 创建 `src/infrastructure/saga/` 模块
  - `__init__.py`
  - `saga_step.py` — SagaStep ABC（execute + compensate + get_description）
  - `saga_context.py` — SagaContext（saga_id, status, steps_data, errors）
  - `saga_status.py` — SagaStatus 枚举

- [ ] **Task 3.2**: 实现 SagaOrchestrator
  - `src/infrastructure/saga/saga_orchestrator.py`
  - 正向执行 + 带重试（execute_with_retry）
  - 补偿流程（逆序 _compensate）
  - 状态持久化（_persist_status）
  - 每个 Step 在独立 UoW 中执行

- [ ] **Task 3.3**: 实现 SagaRepository（PostgreSQL）
  - `src/infrastructure/saga/saga_repository.py`
  - saga_instance 表（saga_id, saga_type, status, context_data, created_at, updated_at）
  - save / load / update_status 方法
  - 新增 Alembic 迁移脚本

- [ ] **Task 3.4**: 定义 Saga 领域端口
  - `src/domain/ports/saga.py` — SagaStep Protocol（领域层零依赖）
  - SagaOrchestrator 是基础设施层实现

- [ ] **Task 3.5**: 注册 Saga 组件到 DI 容器
  - `src/composition_root.py`
  - 注册 `saga_repository` 端口

- [ ] **Task 3.6**: 编写 Saga 基础设施测试
  - 单元测试: SagaOrchestrator 正向执行 + 补偿
  - 单元测试: SagaContext 状态管理
  - 集成测试: SagaRepository PostgreSQL 持久化

**完成标准**：
- [ ] SagaOrchestrator 可执行多步骤流程
- [ ] 补偿事务正确逆序执行
- [ ] Saga 状态持久化到 PostgreSQL
- [ ] 六边形架构依赖方向正确

---

### Phase 4: Saga 场景落地（按业务优先级）

**目标**：按优先级实现具体 Saga 场景。

- [ ] **Task 4.1**: 实现 S01 文档处理与索引 Saga（编舞式）
  - Steps: UploadDocument → SaveMetadata → GenerateEmbedding → ExtractEntities
  - 最终一致性，事件驱动

- [ ] **Task 4.2**: 实现 S02 战略规划创建 Saga（编排式）
  - Steps: SavePlan → ArchiveEvidence
  - 强一致性，SERIALIZABLE 隔离级别

- [ ] **Task 4.3**: 实现 S03 Checkpoint 保存 Saga（编排式）
  - Steps: SaveCheckpoint → ArchiveSnapshot
  - 强一致性，REPEATABLE READ 隔离级别

- [ ] **Task 4.4**: 编写 Saga 场景集成测试
  - 验证正向流程成功
  - 验证中间步骤失败后补偿正确
  - 验证幂等性

- [ ] **Task 4.5**: 后续场景按需实现（S04-S10）
  - 根据业务需求排期

**完成标准**：
- [ ] S01-S03 Saga 场景可运行
- [ ] 补偿流程经过测试验证
- [ ] Saga 状态可查询和监控

---

## 6. 关键文件修改清单

### 6.1 修改文件

| 文件 | Phase | 修改内容 |
|------|-------|---------|
| `src/domain/ports/unit_of_work.py` | 1 | 移除 close() 方法 |
| `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` | 1 | __aexit__ 不调用 close，添加 mark_uow_managed |
| `src/infrastructure/storage/postgresql/session_context.py` | 1 | 添加 _uow_managed_ctx ContextVar |
| `src/infrastructure/middleware/session_middleware.py` | 1 | 适配 UoW 标记，条件化 commit/rollback |
| `src/composition_root.py` | 1,3 | 注册 uow_factory + saga 组件 |
| `src/infrastructure/messaging/outbox/outbox_processor.py` | 2 | 添加指数退避 + 清理策略 |
| `src/infrastructure/storage/postgresql/postgresql_manager.py` | 2 | 支持隔离级别配置 |
| `docs/architecture/sisys-eda-unitofwork-design.md` | 1 | 更新 Phase 2/3 状态 |

### 6.2 新增文件

| 文件 | Phase | 内容 |
|------|-------|------|
| `src/infrastructure/saga/__init__.py` | 3 | Saga 模块初始化 |
| `src/infrastructure/saga/saga_step.py` | 3 | SagaStep ABC |
| `src/infrastructure/saga/saga_context.py` | 3 | SagaContext |
| `src/infrastructure/saga/saga_status.py` | 3 | SagaStatus 枚举 |
| `src/infrastructure/saga/saga_orchestrator.py` | 3 | Saga 编排器 |
| `src/infrastructure/saga/saga_repository.py` | 3 | Saga 状态持久化 |
| `src/domain/ports/saga.py` | 3 | Saga 领域端口 |
| `src/infrastructure/messaging/unit_of_work/audit_unit_of_work.py` | 2 | 审计专用 UoW |
| `deploy/postgresql/alembic/versions/xxx_add_saga_instance.py` | 3 | Saga 表迁移 |

### 6.3 测试文件

| 文件 | Phase | 内容 |
|------|-------|------|
| `tests/unit/.../test_uow_no_close.py` | 1 | UoW 不调用 close 验证 |
| `tests/unit/.../test_session_middleware_uow_aware.py` | 1 | Middleware 适配测试 |
| `tests/unit/.../test_outbox_cleanup.py` | 2 | Outbox 清理测试 |
| `tests/unit/.../test_saga_orchestrator.py` | 3 | Saga 编排器单元测试 |
| `tests/unit/.../test_saga_context.py` | 3 | Saga 上下文测试 |
| `tests/integration/test_saga_repository.py` | 3 | Saga 持久化集成测试 |
| `tests/integration/test_saga_scenarios.py` | 4 | Saga 场景集成测试 |

---

## 7. 测试验证策略

### 7.1 单元测试

| 测试场景 | 验证点 |
|---------|--------|
| UoW 不调用 close | __aexit__ 后 session 未关闭 |
| UoW 标记位设置 | __aexit__ 后 is_uow_managed() 返回 True |
| Middleware UoW 感知 | UoW 已管理时 Middleware 跳过 commit |
| Middleware 兜底逻辑 | 未使用 UoW 时 Middleware 正常 commit |
| Saga 正向执行 | 多步骤顺序执行成功 |
| Saga 补偿 | 中间失败触发逆序补偿 |
| Saga 幂等性 | 重复执行补偿操作安全 |

### 7.2 集成测试

| 测试场景 | 验证点 |
|---------|--------|
| UoW + Outbox 原子性 | 业务表 + outbox 表同时提交/回滚 |
| UoW + EventStore 原子性 | 业务表 + event_store 表同时提交/回滚 |
| Saga 状态持久化 | SagaContext 正确保存到 PostgreSQL |
| 隔离级别 | SERIALIZABLE 防止并发写入冲突 |

### 7.3 故障注入测试

| 测试场景 | 验证点 |
|---------|--------|
| UoW commit 失败 | session 正确 rollback，标记位正确 |
| Outbox 发布失败 | 事件标记为 failed，Poller 后续重试 |
| Saga Step 失败 | 补偿流程正确执行 |
| Saga 补偿失败 | 状态标记为 HALTED，等待人工干预 |

### 7.4 架构验证测试

| 测试场景 | 验证点 |
|---------|--------|
| 六边形依赖方向 | 领域层不导入 infrastructure.saga |
| UoW 接口隔离 | 应用层依赖 UnitOfWork Protocol，非具体实现 |
| SagaStep 接口隔离 | 应用层依赖 SagaStep Protocol |

### 7.5 运行命令

```bash
# 运行全部事务相关测试
poetry run pytest tests/unit/infrastructure/messaging/unit_of_work/ -v
poetry run pytest tests/unit/infrastructure/middleware/ -v
poetry run pytest tests/unit/infrastructure/saga/ -v
poetry run pytest tests/integration/test_saga_repository.py -v

# 运行架构验证
poetry run pytest tests/unit/infrastructure/messaging/unit_of_work/test_uow_transaction_boundary.py -v

# 运行全量测试确认无回归
poetry run pytest --tb=short
```

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Phase 1 改动影响现有功能 | 中 | 高 | 充分单元测试 + 集成测试覆盖；渐进式迁移 |
| Saga 实现复杂度超预期 | 中 | 中 | 先实现基础设施框架，场景按优先级逐个落地 |
| 隔离级别配置影响性能 | 低 | 中 | 仅审计场景使用 SERIALIZABLE，一般场景保持默认 |
| UoW 标记位 ContextVar 泄漏 | 低 | 高 | Middleware finally 块中重置标记位 |

---

## 9. 参考文档

| 文档 | 关联 |
|------|------|
| `sisys-eda-unitofwork-design.md` (v1.0.6) | Phase 1 完成的基础设计 |
| `architecture.md` (v8.3.1) | 六边形架构约束 + 事件驱动架构 |
| `arch-appendix.md` 附录J | Saga 事务一致性设计方案 |
| `story-template.md` (v2.7.0) | 六边形架构约束 + 测试隔离 |
| `sprint-status.yaml` | Sprint 状态追踪 |
| SQLAlchemy 2.0 AsyncSession | [官方文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) |
| Martin Fowler — Unit of Work | [模式定义](https://martinfowler.com/eaaCatalog/unitOfWork.html) |
| Eventuate Tram | Outbox + Saga 参考实现 |
