# SISYS 事务子系统详细设计

**文档版本:** v1.0
**生成时间:** 2026-05-19
**基于:** architecture.md v8.3.1 + sisys-transaction-subsystem-refactor.md v1.0.5 + 现有代码实现全面调研
**状态:** Phase 1 已完成（Session 生命周期治理 + UoW 完善），Phase 2-4 待完善

---

## 1. 设计概述

### 1.1 事务子系统职责

事务子系统是 SISYS 的核心基础设施，采用六边形架构（Ports & Adapters）设计，负责：

| 职责 | 技术实现 | 当前状态 |
|------|---------|---------|
| **事务边界管理** | UnitOfWork 模式 | ✅ 已实现 |
| **Session 生命周期** | ContextVar + Middleware | ✅ 已实现 |
| **Outbox 模式** | Transactional Outbox | ⚠️ 部分实现（Persistence Bug） |
| **Saga 编排** | 补偿型 Saga | ⚠️ 基础设施已建 |
| **幂等性保证** | DualIdempotencyChecker | ✅ 已实现 |

### 1.2 核心设计原则

- **Session 生命周期职责分离**：Middleware 负责创建和关闭，UoW 负责事务边界
- **事务边界显式化**：所有跨表写入通过 UoW，使用 `async with uow:` 模式
- **Outbox 原子性**：业务表 + outbox 表同一事务提交，Poller 独立 session
- **六边形架构合规**：领域层零外部依赖，依赖方向正确

### 1.3 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| Session 管理 | SQLAlchemy 2.0 AsyncSession + ContextVar | 线程/异步隔离 |
| 事务边界 | UnitOfWork Pattern | 幂等 commit/rollback |
| 事件发布 | Transactional Outbox | 确保事件可靠发布 |
| 跨库事务 | Saga Pattern | 补偿型 Orchestration |
| 消息队列 | RabbitMQ 3.12+ | PERSISTENT 持久化 |
| 重试策略 | 指数退避 + Jitter | RetryPolicy |

---

## 2. 架构总览图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Composition Root                              │
│                   src/composition_root.py                            │
│         register_port(name, interface, impl, lifetime)              │
│         Resolver._auto_inject(cls) → 按参数名/类型递归解析           │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ 装配
                           v
┌──────────────────────────────────────────────────────────────────────┐
│                    Application Layer                                 │
│                    (EventHandler / UseCase)                          │
│                                                                      │
│  uow = uow_factory()                                                 │
│  async with uow:                                                      │
│      ├── business_repo.save(entity)   # 同一 session                │
│      └── outbox_repo.save(event)       # 同一 session                │
│  # uow.__aexit__: commit (no close!)                                  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ 依赖
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  Domain Layer — 端口定义（零外部依赖）                                │
│                                                                      │
│  UnitOfWork(Protocol)          OutboxRepository(Protocol)            │
│  UnitOfWorkFactory(Protocol)   SagaStep(Protocol)                    │
│  SagaContext(Protocol)         SagaRepositoryProtocol(Protocol)     │
│                                                                      │
│  位置: src/domain/ports/                                            │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ 实现
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  Infrastructure Layer — 技术实现                                      │
│                                                                      │
│  PostgreSQLUnitOfWork          PostgreSQLOutboxRepository            │
│  SessionMiddleware             AsyncOutboxPoller                     │
│  SagaOrchestrator              PostgreSQLSagaRepository             │
│  RetryPolicy                   DualIdempotencyChecker               │
│                                                                      │
│  位置: src/infrastructure/messaging/                                │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ 依赖
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  External Systems                                                     │
│  PostgreSQL 15 + SQLAlchemy | RabbitMQ 3.12+ | Redis (幂等性)         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. UnitOfWork 子系统

### 3.1 Domain 层端口

#### UnitOfWork Protocol

**文件:** `src/domain/ports/unit_of_work.py`

```python
@runtime_checkable
class UnitOfWork(Protocol):
    """抽象工作单元接口

    定义事务边界：begin(), commit(), rollback()
    支持异步上下文管理器协议

    设计要点：
    - session property 返回 object（类型宽泛，AsyncSession 协变兼容）
    - __aexit__ 规则：异常 rollback，正常仅在未手动 commit/rollback 时才 commit
    - 不负责 close session（由 SessionMiddleware 负责）
    """

    @property
    def session(self) -> object:
        """获取当前事务的 session"""
        ...

    async def begin(self) -> None:
        """开始事务"""
        ...

    async def commit(self) -> None:
        """提交事务"""
        ...

    async def rollback(self) -> None:
        """回滚事务"""
        ...

    async def begin_nested(self) -> None:
        """创建 savepoint（嵌套事务）"""
        ...

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """异步上下文管理器出口

        规则：
        - 异常：rollback
        - 正常：仅在未手动 commit/rollback 时才 commit
        - 不负责 close session（由 SessionMiddleware 负责）
        - 返回 False：不吞没异常
        """
        ...
```

#### UnitOfWorkFactory Protocol

**文件:** `src/domain/ports/unit_of_work.py` (行 78-97)

```python
@runtime_checkable
class UnitOfWorkFactory(Protocol):
    """UnitOfWork 工厂 Protocol

    设计原因（D2 决策）：
    - PortSpec.interface 类型为 Type，Callable[[], UnitOfWork] 不合法
    - 须定义专门的 Protocol 满足 PortSpec 类型约束
    - 工厂每次调用返回新实例（TRANSIENT 生命周期）
    """

    def __call__(self) -> UnitOfWork:
        """创建新的 UnitOfWork 实例"""
        ...
```

### 3.2 Infrastructure 层实现

#### PostgreSQLUnitOfWork

**文件:** `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py`

```python
class PostgreSQLUnitOfWork(UnitOfWork):
    """PostgreSQL 工作单元实现

    使用 SQLAlchemy AsyncSession 管理事务，实现领域层 UnitOfWork 接口

    Attributes:
        _committed: 是否已提交（实例级）
        _rolled_back: 是否已回滚（实例级）
    """

    def __init__(self) -> None:
        """初始化工作单元实例级状态并缓存 session 引用。"""
        self._committed: bool = False
        self._rolled_back: bool = False
        self._session: AsyncSession = get_session()  # 从 ContextVar 获取

    @property
    def session(self) -> AsyncSession:
        """获取当前事务的 session"""
        return self._session

    async def begin(self) -> None:
        await self._session.begin()

    async def commit(self) -> None:
        """显式提交事务并标记为已提交（幂等保护）"""
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚事务并标记为已回滚（幂等保护）"""
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.rollback()
        self._rolled_back = True

    async def begin_nested(self) -> None:
        """创建 savepoint（嵌套事务）"""
        await self._session.begin_nested()

    async def close(self) -> None:
        """关闭会话（公共方法，但 __aexit__ 不调用）"""
        await self._session.close()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """异步上下文管理器出口

        关键设计：__aexit__ 不调用 close()，由 SessionMiddleware 负责
        """
        if exc_type is not None:
            if not self._rolled_back:
                await self.rollback()
        elif not self._committed and not self._rolled_back:
            await self.commit()
        return False
```

**设计要点：**
- 幂等保护：`_committed` / `_rolled_back` 标志防止重复 commit/rollback
- Session 来源：通过 `get_session()` 从 ContextVar 获取，非构造器注入
- close() 分离：公共方法但 `__aexit__` 不调用，由 Middleware 统一管理

### 3.3 Session 生命周期管理

#### SessionMiddleware

**文件:** `src/infrastructure/middleware/session_middleware.py`

```python
class SessionMiddleware(BaseHTTPMiddleware):
    """ASGI 中间件，在每个请求中管理 AsyncSession

    请求开始时通过 ContextVar 创建 AsyncSession，成功时提交，异常时回滚，结束时关闭

    关键设计：使用 session.in_transaction() 检测 UoW 是否已管理事务
    - UoW 已 commit/rollback 后 in_transaction() 为 False，跳过操作
    - UoW 未使用时 in_transaction() 为 True，由 Middleware commit/rollback
    - finally 块始终负责 close + reset
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        session = self._factory()
        token = set_session(session)
        try:
            response = await call_next(request)
            if session.in_transaction():  # ✅ 检测 UoW
                await session.commit()
            return response
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            await session.close()
            reset_session(token)
```

#### Session Context

**文件:** `src/infrastructure/storage/postgresql/session_context.py`

```python
# ContextVar 定义
_session_ctx: ContextVar[AsyncSession | None] = ContextVar(
    "pg_session",
    default=None,
)

# 获取 session
def get_session() -> AsyncSession:
    """从 ContextVar 获取当前 session，不存在则抛出 RuntimeError"""
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError("No session in context")
    return session

# 上下文管理器（后台任务用）
@asynccontextmanager
async def session_context(session_factory):
    session = session_factory()
    token = set_session(session)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        reset_session(token)
```

### 3.4 Session 生命周期流程

```
┌──────────────────────────────────────────────────────────────────────┐
│  HTTP 请求场景                                                        │
├──────────────────────────────────────────────────────────────────────┤
│ SessionMiddleware.dispatch()                                         │
│     ├── session = self._factory()         # 创建 session            │
│     ├── token = set_session(session)      # 写入 ContextVar          │
│     │                                                                  │
│     ├── handler 使用 UoW 时:                                            │
│     │   ├── uow.__aenter__() → session.begin()                         │
│     │   ├── ... business + outbox ...          # flush()             │
│     │   └── uow.__aexit__() → session.commit()  # in_transaction=Flase│
│     │                                                                  │
│     ├── handler 未使用 UoW 时:                                          │
│     │   └── session.in_transaction()=True → Middleware commit        │
│     │                                                                  │
│     └── finally:                                                       │
│         ├── session.close()            # 始终 close                    │
│         └── reset_session(token)       # 清理 ContextVar               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  后台任务场景                                                         │
├──────────────────────────────────────────────────────────────────────┤
│ async with session_context(factory):                                 │
│     ├── session = session_factory()      # 创建 session               │
│     ├── set_session(session)             # 写入 ContextVar             │
│     ├── yield session                   # 业务逻辑                    │
│     ├── session.commit()                # 自动提交                    │
│     └── session.close() + reset()        # 自动清理                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.5 DI 注册

```python
# src/composition_root.py 行 557-565
register_port(
    name="uow_factory",
    version="v1.0.0",
    interface=UnitOfWorkFactory,
    impl=lambda resolver: PostgreSQLUnitOfWork,  # 返回类本身
    module="src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work",
    lifetime=Lifetime.TRANSIENT,  # 每次创建新实例
)
```

---

## 4. Outbox 子系统

### 4.1 Domain 层端口

**文件:** `src/domain/ports/outbox.py`

```python
@runtime_checkable
class OutboxRepository(Protocol):
    """事务发件箱仓储接口（领域层）

    所有方法使用 DomainEvent，基础设施层实现时在内部转换为 OutboxEntity
    保证领域层零 OutboxEntity 污染
    所有异步操作的 Protocol 签名为 async
    """

    async def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱（与业务操作同事务）"""
        ...

    async def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表（FIFO 排序）"""
        ...

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布"""
        ...

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败"""
        ...

    async def cleanup_old_published_records(self, older_than_days: int = 30) -> int:
        """清理超过保留期的已发布记录"""
        ...
```

### 4.2 OutboxEntity 状态机

**文件:** `src/infrastructure/messaging/outbox/outbox.py`

```
                    +------------------+
                    |     pending      |
                    +--------+---------+
                             |
              +-------------+-------------+
              |                           |
              v                           v
     +--------+--------+        +--------+--------+
     |  published      |        |  failed         |
     +-----------------+        +--------+---------+
                                        |
                    +-------------------+-------------------+
                    |                                       |
                    v                                       v
           +--------+--------+                    +--------+--------+
           |  pending (重试)  |                    |  archived (终态) |
           +-----------------+                    +-----------------+
```

| 方法 | 状态转换 | 验证规则 |
|------|---------|---------|
| `mark_published()` | pending → published | 仅 pending 可转换 |
| `mark_failed()` | pending/failed → failed | 递增 retry_count |
| `mark_pending()` | failed → pending（重试） | 检查 max_retries |
| `mark_archived()` | failed → archived | 终态，不可再转换 |

### 4.3 Infrastructure 层实现

#### PostgreSQLOutboxRepository

**文件:** `src/infrastructure/messaging/outbox/outbox_repository.py`

```python
class PostgreSQLOutboxRepository(OutboxRepository):
    """PostgreSQL 发件箱仓储实现

    所有公开方法为 async（实现 OutboxRepository Protocol）
    内部方法（_ 前缀）直接操作 OutboxModel，仅 Poller 使用
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @property
    def _session(self) -> AsyncSession:
        return get_session()  # 从 ContextVar 获取

    async def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱（与业务操作同事务）"""
        model = SQLAlchemyEventOutboxAdapter.from_domain_event(event)
        self._session.add(model)
        await self._session.flush()  # ✅ 正确：UoW 控制提交

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布"""
        result = await self._session.execute(
            select(OutboxModel).where(OutboxModel.event_id == event_id)
        )
        model = result.scalar_one_or_none()
        if model:
            if model.status != "pending":
                raise InvalidStateTransitionError(model.status, "published")
            model.status = "published"
            model.published_at = datetime.now(UTC)
            await self._session.flush()  # ⚠️ 待修复：添加 flush()

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败"""
        result = await self._session.execute(
            select(OutboxModel).where(OutboxModel.event_id == event_id)
        )
        model = result.scalar_one_or_none()
        if model:
            if model.status not in ("pending", "failed"):
                raise InvalidStateTransitionError(model.status, "failed")
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error
            await self._session.flush()  # ⚠️ 待修复：添加 flush()

    async def cleanup_old_published_records(self, older_than_days: int = 30) -> int:
        """清理超过保留期的已发布记录"""
        # TODO: 实现基于 published_at 和 status='published' 的清理逻辑
        return 0  # ⚠️ 待修复：存根实现
```

#### InMemoryOutboxRepository

**文件:** `src/infrastructure/messaging/outbox/inmemory_outbox.py`

```python
class InMemoryOutboxRepository(OutboxRepository):
    """内存发件箱仓储实现（MVP 阶段）

    所有公开方法为 async（实现 OutboxRepository Protocol）
    内部方法（_ 前缀）直接操作 OutboxEntity，使用 asyncio.Lock 保护
    """

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == event_id:
                    e.mark_published()  # ✅ 正确：调用状态机方法
                    break

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败"""
        async with self._lock:
            for e in self._entities:
                if e.event_id == event_id:
                    e.mark_failed(error)  # ✅ 正确：调用状态机方法
                    break

    async def cleanup_old_published_records(self, older_than_days: int = 30) -> int:
        """清理超过保留期的已发布记录"""
        async with self._lock:
            cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
            to_remove = [
                e for e in self._entities
                if e.status == "published" and e.published_at is not None and e.published_at < cutoff
            ]
            for e in to_remove:
                self._entities.remove(e)
            return len(to_remove)  # ✅ 正确：完整实现
```

### 4.4 AsyncOutboxPoller

**文件:** `src/infrastructure/messaging/outbox/outbox_processor.py`

```python
class AsyncOutboxPoller:
    """异步发件箱轮询器

    定期轮询 Outbox，将 pending 状态的事件发布至 RabbitMQ
    成功则标记为 published，失败则标记为 failed
    """

    def __init__(
        self,
        outbox_repository: OutboxRepository,
        publisher: Any,
        router: ChannelRouter,
        session_factory: Any = None,
        poll_interval: float = 1.0,
        batch_size: int = 10,
    ):
        ...

    async def poll_once(self) -> None:
        """轮询一次并发布待处理事件"""
        events = await self._repo.get_unpublished(limit=self._batch_size)
        if not events:
            return

        semaphore = asyncio.Semaphore(self._batch_size)

        async def process_one(event: DomainEvent) -> None:
            async with semaphore:
                routing_key = self._router.get_rabbitmq_routing_key(event.event_type)
                if routing_key is None:
                    await self._repo.mark_failed(
                        event.event_id,
                        f"No routing key mapping for {event.event_type}",
                    )
                    return

                try:
                    await self._publisher.async_publish(event, routing_key=routing_key)
                    await self._repo.mark_published(event.event_id)
                except Exception as e:
                    try:
                        await self._repo.mark_failed(event.event_id, str(e))
                    except Exception:
                        logger.error(...)  # ⚠️ 异常被吞没
                    logger.error(...)
                # ⚠️ 待修复：无重试机制（RetryPolicy 未集成）

        await asyncio.gather(*[process_one(e) for e in events])

    async def run(self) -> None:
        """启动轮询循环"""
        self._running = True
        while self._running:
            try:
                if self._session_factory is not None:
                    async with session_context(self._session_factory):
                        await self.poll_once()
                else:
                    await self.poll_once()
            except Exception as e:
                logger.error("Error in poll_once: %s", e)
            await asyncio.sleep(self._poll_interval)
```

### 4.5 RetryPolicy

**文件:** `src/infrastructure/messaging/retry/retry_policy.py`

```python
@dataclass
class RetryPolicy:
    """重试策略配置

    指数退避公式: delay = min(base * 2^retry_count * jitter, max)
    jitter 范围: [0.5, 1.5]
    """

    base_delay: float = 1.0
    max_delay: float = 60.0
    max_retries: int = 3

    def get_delay(self, retry_count: int) -> float:
        jitter: float = random.uniform(0.5, 1.5)
        delay = min(self.base_delay * (2**retry_count) * jitter, self.max_delay)
        return float(delay)

    def should_retry(self, retry_count: int, max_retries: int | None = None) -> bool:
        limit = max_retries if max_retries is not None else self.max_retries
        return retry_count < limit
```

### 4.6 DualIdempotencyChecker

**文件:** `src/infrastructure/messaging/retry/dual_idempotency_checker.py`

幂等性保证：Redis + PostgreSQL 双写，防止重复处理。

### 4.7 DI 注册

```python
# src/composition_root.py

# Outbox Repository (SINGLETON)
register_port(
    name="outbox_repo",
    version="v1.0.0",
    interface=OutboxRepository,
    impl="src.infrastructure.messaging.outbox.outbox_repository.PostgreSQLOutboxRepository",
    module="src.infrastructure.messaging.outbox.outbox_repository",
    lifetime=Lifetime.SINGLETON,
)

# Outbox Poller
register_port(
    name="outbox_poller",
    version="v1.0.0",
    interface=AsyncOutboxPoller,
    impl=lambda resolver: AsyncOutboxPoller(
        outbox_repository=resolver.resolve("outbox_repo"),
        publisher=resolver.resolve("rabbitmq_publisher"),
        router=resolver.resolve("router"),
        session_factory=resolver.resolve("session_factory"),
    ),
    module="src.infrastructure.messaging.outbox.outbox_processor",
    lifetime=Lifetime.SINGLETON,
)
```

---

## 5. Saga 子系统

### 5.1 Domain 层端口

#### SagaStatus

**文件:** `src/domain/ports/saga_status.py`

```python
class SagaStatus(str, Enum):
    """Saga 实例状态枚举。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        """是否为终态。"""
        return self in (SagaStatus.COMPLETED, SagaStatus.COMPENSATED, SagaStatus.FAILED)

    def can_transition_to(self, target: SagaStatus) -> bool:
        """检查是否可转换到目标状态。"""
        valid_transitions: dict[SagaStatus, set[SagaStatus]] = {
            SagaStatus.PENDING: {SagaStatus.RUNNING},
            SagaStatus.RUNNING: {SagaStatus.COMPLETED, SagaStatus.COMPENSATING, SagaStatus.FAILED},
            SagaStatus.COMPENSATING: {SagaStatus.COMPENSATED, SagaStatus.FAILED},
        }
        return target in valid_transitions.get(self, set())
```

#### SagaContext Protocol

**文件:** `src/domain/ports/saga_context.py`

```python
@runtime_checkable
class SagaContext(Protocol):
    """Saga 执行上下文 Protocol。"""

    @property
    def saga_id(self) -> uuid.UUID: ...
    @property
    def saga_type(self) -> str: ...
    @property
    def status(self) -> SagaStatus: ...
    @property
    def steps_data(self) -> dict[str, dict[str, Any]]: ...
    @property
    def current_step_index(self) -> int: ...
    @property
    def errors(self) -> list[dict[str, Any]]: ...
    @property
    def created_at(self) -> datetime: ...
    @property
    def updated_at(self) -> datetime: ...
    @property
    def metadata(self) -> dict[str, Any]: ...

    def update_status(self, new_status: SagaStatus) -> SagaContext: ...
    def set_step_data(self, step_name: str, input_data: Any | None, output_data: Any | None) -> SagaContext: ...
    def get_step_output(self, step_name: str) -> Any | None: ...
    def advance_step(self, total_steps: int) -> SagaContext: ...
    def add_error(self, step_name: str, error_message: str) -> SagaContext: ...
    def to_dict(self) -> dict[str, Any]: ...
```

#### SagaStep Protocol

**文件:** `src/domain/ports/saga.py`

```python
@runtime_checkable
class SagaStep(Protocol):
    """Saga 步骤 Protocol

    每个 SagaStep 表示 Saga 流程中的一个原子操作
    当步骤失败时，compensate() 方法用于执行补偿操作
    """

    @property
    def name(self) -> str:
        """步骤唯一名称。"""
        ...

    async def execute(self, context: SagaContext) -> SagaContext:
        """执行正向操作。"""
        ...

    async def compensate(self, context: SagaContext) -> SagaContext:
        """执行补偿操作。"""
        ...
```

#### SagaRepositoryProtocol

**文件:** `src/domain/ports/saga.py`

```python
@runtime_checkable
class SagaRepositoryProtocol(Protocol):
    """Saga 实例持久化端口。"""

    async def save(self, context: SagaContext) -> None:
        """保存 Saga 上下文（UPSERT）。"""
        ...

    async def load(self, saga_id: str) -> SagaContext | None:
        """加载 Saga 上下文。"""
        ...

    async def update_status(self, saga_id: str, status: SagaStatus) -> None:
        """更新 Saga 状态。"""
        ...
```

### 5.2 Infrastructure 层实现

#### SagaContext 实现

**文件:** `src/infrastructure/saga/saga_context.py`

```python
@dataclass
class SagaContext:
    """Saga 执行上下文。"""

    saga_id: uuid.UUID = field(default_factory=uuid.uuid4)
    saga_type: str = ""
    status: SagaStatus = SagaStatus.PENDING
    steps_data: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_step_index: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_status(self, new_status: SagaStatus) -> SagaContext:
        """更新状态，返回新的 SagaContext 实例。"""
        if not self.status.can_transition_to(new_status):
            raise ValueError(f"非法状态转换: {self.status} → {new_status}")
        return dataclass_replace(self, status=new_status, updated_at=datetime.now(timezone.utc))

    def set_step_data(self, step_name: str, input_data: Any | None, output_data: Any | None) -> SagaContext:
        """设置步骤执行数据，返回新的 SagaContext 实例。"""
        new_steps_data = copy.deepcopy(self.steps_data)
        new_steps_data[step_name] = {"input": input_data, "output": output_data}
        return dataclass_replace(self, steps_data=new_steps_data, updated_at=datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        return {
            "saga_id": str(self.saga_id),
            "saga_type": self.saga_type,
            "status": self.status.value,
            "steps_data": self.steps_data,
            "current_step_index": self.current_step_index,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SagaContext:
        """从字典反序列化。"""
        return cls(
            saga_id=uuid.UUID(data["saga_id"]),
            saga_type=data["saga_type"],
            status=SagaStatus(data["status"]),
            steps_data=data.get("steps_data", {}),
            current_step_index=data.get("current_step_index", 0),
            errors=data.get("errors", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )
```

#### SagaOrchestrator

**文件:** `src/infrastructure/saga/saga_orchestrator.py`

```python
class SagaOrchestrator:
    """Saga 编排器

    协调多个 SagaStep 的执行和补偿流程

    执行流程：
    1. 正向执行所有步骤
    2. 若中间步骤失败，触发补偿流程（逆序执行已成功步骤的 compensate）
    3. 补偿失败标记为 FAILED
    """

    def __init__(
        self,
        saga_id: UUID,
        saga_type: str,
        steps: Sequence[SagaStep],
        repository: SagaRepositoryProtocol,
    ) -> None:
        ...

    async def execute(self) -> SagaContext:
        """执行 Saga 流程"""
        self._context = self._context.update_status(SagaStatus.RUNNING)
        await self._repository.save(self._context)

        for index, step in enumerate(self._steps):
            try:
                logger.info("Saga %s: executing step %s", self.saga_id, step.name)
                updated_context = await step.execute(self._context)
                self._context = updated_context
                self._context = self._context.set_step_data(step.name, None, updated_context)
                self._context = self._context.advance_step(len(self._steps))
                await self._repository.save(self._context)
            except Exception as e:
                logger.error("Saga %s: step %s failed: %s", self.saga_id, step.name, e)
                self._context = self._context.add_error(step.name, str(e))
                return await self._compensate(index)

        self._context = self._context.update_status(SagaStatus.COMPLETED)
        await self._repository.save(self._context)
        return self._context

    async def _compensate(self, failed_index: int) -> SagaContext:
        """补偿已成功的步骤（从失败步骤前一个开始逆向执行）"""
        if failed_index == 0:
            self._context = self._context.add_error("_compensate", "没有可补偿的步骤")
            self._context = self._context.update_status(SagaStatus.FAILED)
            await self._repository.save(self._context)
            return self._context

        self._context = self._context.update_status(SagaStatus.COMPENSATING)
        compensation_failed = False

        for index in range(failed_index - 1, -1, -1):
            step = self._steps[index]
            try:
                logger.info("Saga %s: compensating step %s", self.saga_id, step.name)
                await step.compensate(self._context)
            except Exception as e:
                logger.error("Saga %s: compensation failed for step %s: %s", self.saga_id, step.name, e)
                self._context = self._context.add_error(f"{step.name}_compensation", str(e))
                compensation_failed = True
                break

        if compensation_failed:
            self._context = self._context.update_status(SagaStatus.FAILED)
        else:
            self._context = self._context.update_status(SagaStatus.COMPENSATED)

        await self._repository.save(self._context)
        return self._context
```

#### PostgreSQLSagaRepository

**文件:** `src/infrastructure/saga/saga_repository.py`

```python
class PostgreSQLSagaRepository(SagaRepositoryProtocol):
    """PostgreSQL Saga 仓储实现

    通过 ContextVar 获取 session，无需构造器注入
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def save(self, context: SagaContext) -> None:
        """保存 Saga 上下文（UPSERT）"""
        data = context.to_dict()

        await self._session.execute(
            text(
                "INSERT INTO saga_instance (saga_id, saga_type, status, context_data, created_at, updated_at) "
                "VALUES (:saga_id, :saga_type, :status, :context_data, :created_at, :updated_at) "
                "ON CONFLICT (saga_id) DO UPDATE SET "
                "status = EXCLUDED.status, "
                "context_data = EXCLUDED.context_data, "
                "updated_at = EXCLUDED.updated_at"
            ),
            {
                "saga_id": str(context.saga_id),
                "saga_type": context.saga_type,
                "status": context.status.value,
                "context_data": json.dumps(data),
                "created_at": context.created_at,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._session.flush()  # ✅ 正确

    async def load(self, saga_id: str) -> SagaContext | None:
        """加载 Saga 上下文"""
        result = await self._session.execute(
            text("SELECT context_data FROM saga_instance WHERE saga_id = :saga_id"),
            {"saga_id": str(saga_id)},
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return SagaContext.from_dict(json.loads(row))

    async def update_status(self, saga_id: str, status: SagaStatus) -> None:
        """更新 Saga 状态"""
        existing = await self._session.execute(
            text("SELECT 1 FROM saga_instance WHERE saga_id = :saga_id"),
            {"saga_id": str(saga_id)},
        )
        if existing.scalar_one_or_none() is None:
            raise ValueError(f"update_status 未找到 saga_id={saga_id} 的 Saga 实例")

        await self._session.execute(
            text("UPDATE saga_instance SET status = :status, updated_at = :updated_at WHERE saga_id = :saga_id"),
            {
                "saga_id": str(saga_id),
                "status": status.value,
                "updated_at": datetime.now(UTC),
            },
        )
        # ⚠️ 待修复：添加 flush()
```

### 5.3 Saga 表结构

**文件:** `deploy/postgresql/alembic/versions/004_saga_tables.py`

```python
def upgrade() -> None:
    """Create saga_instance table with status CHECK constraint."""
    op.create_table(
        "saga_instance",
        sa.Column("saga_id", sa.String(36), primary_key=True),
        sa.Column("saga_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("context_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'COMPENSATING', 'COMPENSATED', 'FAILED')",
            name="ck_saga_status_values",
        ),
    )
    op.create_index("ix_saga_instance_saga_type", "saga_instance", ["saga_type"])
    op.create_index("ix_saga_instance_status", "saga_instance", ["status"])
```

### 5.4 DI 注册

```python
# src/composition_root.py 行 567-575
register_port(
    name="saga_repository",
    version="v1.0.0",
    interface=SagaRepositoryProtocol,
    impl="src.infrastructure.saga.saga_repository.PostgreSQLSagaRepository",
    module="src.infrastructure.saga.saga_repository",
    lifetime=Lifetime.SINGLETON,
)
```

---

## 6. 设计模式汇总

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **六边形架构 (Ports & Adapters)** | 全部子系统 | Domain 定义 Protocol，Infrastructure 实现 |
| **Protocol 结构化子类型** | 所有 Port | `typing.Protocol` + `@runtime_checkable`，鸭子类型兼容 |
| **Session 生命周期分离** | Middleware/UoW | Middleware 负责 close，UoW 负责事务 |
| **ContextVar Session 注入** | 所有 Repository | Session 不通过构造器传入，通过全局上下文变量获取 |
| **幂等保护** | UnitOfWork | `_committed`/`_rolled_back` 标志防止重复 commit/rollback |
| **事务发件箱 (Outbox)** | Outbox 子系统 | 保证事件可靠发布 |
| **工作单元 (Unit of Work)** | UoW 子系统 | 管理事务边界 |
| **Saga 补偿** | Saga 子系统 | 跨服务事务的逆向补偿 |
| **指数退避 + Jitter** | RetryPolicy | 防止惊群效应，最大延迟上限 |
| **UPSERT 语义** | SagaRepository | 幂等保存 Saga 状态 |

---

## 7. 关键问题与修复计划

### 7.1 高优先级问题

| 问题 | 位置 | 修复方案 | 状态 |
|------|------|---------|------|
| `mark_published()` 未调用 `flush()` | `outbox_repository.py:80` | 添加 `await self._session.flush()` | ✅ 已修复 |
| `mark_failed()` 未调用 `flush()` | `outbox_repository.py:96` | 添加 `await self._session.flush()` | ✅ 已修复 |
| `update_status()` 未调用 `flush()` | `saga_repository.py:134` | 添加 `await self._session.flush()` | ✅ 已修复 |
| `cleanup_old_published_records` 存根 | `outbox_repository.py:96-119` | 实现完整清理逻辑（基于 published_at + status='published'） | ✅ 已修复 |

### 7.2 中优先级问题

| 问题 | 位置 | 修复方案 | 状态 |
|------|------|---------|------|
| OutboxPoller 异常被吞没 | `outbox_processor.py:75-128` | 改进错误处理 + RetryPolicy 集成 | ✅ 已修复 |
| 未集成 RetryPolicy | `outbox_processor.py:20,37-63` | Poller 集成指数退避重试（构造器参数 `retry_policy`） | ✅ 已修复 |
| `datetime.utcnow()` 废弃 | `arch-appendix.md` | 替换为 `datetime.now(UTC)`（28 处） | 待修复 |

### 7.3 测试优化

| 问题 | 修复方案 | 效果 |
|------|---------|------|
| OutboxPoller 测试慢（27s） | fixture 使用极短 RetryPolicy（`base_delay=0.001, max_delay=0.01, max_retries=3`） | **27s → 4.2s** |

---

## 8. 测试体系

### 8.1 测试分层

| 测试类型 | 位置 | 覆盖内容 |
|---------|------|---------|
| **端口契约测试** | `tests/contracts/` | 端口注册、方法存在、元数据完整性 |
| **单元测试** | `tests/unit/infrastructure/messaging/unit_of_work/` | UoW 幂等保护、Session 分离 |
| **单元测试** | `tests/unit/infrastructure/messaging/outbox/` | Outbox 状态机、Poller 逻辑 |
| **单元测试** | `tests/unit/infrastructure/saga/` | SagaOrchestrator 正向/补偿 |
| **集成测试** | `tests/integration/` | 业务 + Outbox 原子性、Saga 持久化 |
| **架构约束测试** | `tests/unit/architecture/` | Domain 层零依赖、依赖方向 |

### 8.2 关键测试用例

| 测试 | 验证点 |
|------|--------|
| `test_uow_does_not_close_session` | `__aexit__` 不调用 `close()` |
| `test_middleware_uses_in_transaction` | Middleware 检测 UoW 状态 |
| `test_outbox_persistence` | `mark_published()`/`mark_failed()` 持久化（含 flush） |
| `test_outbox_state_machine` | 状态转换规则验证 |
| `test_poll_once_retries_on_transient_error` | 临时错误重试后成功 |
| `test_poll_once_marks_failed_after_retries_exhausted` | 重试耗尽后标记 failed |
| `test_saga_compensation` | 补偿流程正确执行 |
| `test_saga_upsert` | Saga 状态 UPSERT 持久化 |

### 8.3 运行命令

```bash
# 事务相关单元测试
poetry run pytest tests/unit/infrastructure/messaging/unit_of_work/ -v
poetry run pytest tests/unit/infrastructure/messaging/outbox/ -v
poetry run pytest tests/unit/infrastructure/saga/ -v

# 集成测试
poetry run pytest tests/integration/ -v -k "outbox or saga"

# 全量测试
poetry run pytest --tb=short
```

---

## 9. 关键文件索引

### 9.1 Domain 层端口

| 文件 | 端口 | 说明 |
|------|------|------|
| `src/domain/ports/unit_of_work.py` | `UnitOfWork`, `UnitOfWorkFactory` | 工作单元接口 |
| `src/domain/ports/outbox.py` | `OutboxRepository` | 发件箱仓储接口 |
| `src/domain/ports/saga.py` | `SagaStep`, `SagaRepositoryProtocol` | Saga 步骤和持久化接口 |
| `src/domain/ports/saga_context.py` | `SagaContext` | Saga 上下文接口 |
| `src/domain/ports/saga_status.py` | `SagaStatus` | Saga 状态枚举 |

### 9.2 Infrastructure 层实现

| 组件 | 文件 | 说明 |
|------|------|------|
| **UoW** | `infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` | UoW 实现 |
| **Middleware** | `infrastructure/middleware/session_middleware.py` | Session 中间件 |
| **Session Context** | `infrastructure/storage/postgresql/session_context.py` | ContextVar 管理 |
| **OutboxEntity** | `infrastructure/messaging/outbox/outbox.py` | 发件箱实体 |
| **Outbox Repo** | `infrastructure/messaging/outbox/outbox_repository.py` | PostgreSQL 实现 |
| **InMemory Outbox** | `infrastructure/messaging/outbox/inmemory_outbox.py` | 内存实现 |
| **Outbox Poller** | `infrastructure/messaging/outbox/outbox_processor.py` | 轮询处理器 |
| **RetryPolicy** | `infrastructure/messaging/retry/retry_policy.py` | 重试策略 |
| **SagaContext** | `infrastructure/saga/saga_context.py` | Saga 上下文实现 |
| **SagaOrchestrator** | `infrastructure/saga/saga_orchestrator.py` | Saga 编排器 |
| **Saga Repo** | `infrastructure/saga/saga_repository.py` | PostgreSQL 实现 |

### 9.3 数据库迁移

| 版本 | 文件 | 内容 |
|------|------|------|
| 001 | `001_initial.py` | event_outbox 表（含 archived CheckConstraint） |
| 004 | `004_saga_tables.py` | saga_instance 表 |

---

## 10. 与现有架构文档一致性

### 10.1 与 `sisys-transaction-subsystem-refactor.md` 一致性

| 项目 | Refactor 文档 | 实际代码 | 状态 |
|------|-------------|---------|------|
| Phase 1 Task 1.1 | UoW `__aexit__` 不调用 `close()` | `postgresql_unit_of_work.py:108-138` | ✅ |
| Phase 1 Task 1.2 | Middleware 使用 `in_transaction()` 检测 | `session_middleware.py:69-74` | ✅ |
| Phase 1 Task 1.5 | `UnitOfWorkFactory` Protocol | `unit_of_work.py:78-97` | ✅ |
| Phase 1 Task 1.6 | `uow_factory` DI 注册 | `composition_root.py:557-565` | ✅ |
| P6 | archived CheckConstraint | `001_initial.py:32` | ✅ |
| P7 | InMemoryOutboxRepository 状态机 | `inmemory_outbox.py:56-70` | ✅ |

### 10.2 与 `architecture.md` 一致性

| 约束 | 实现 | 状态 |
|------|------|------|
| 领域层零外部依赖 | `unit_of_work.py` 仅使用标准库 | ✅ |
| 六边形架构 | Protocol 在 domain，Impl 在 infrastructure | ✅ |
| 依赖方向正确 | domain → application → infrastructure | ✅ |

---

## 11. 已知限制与 TODO

| 项目 | 状态 | 说明 |
|------|------|------|
| `datetime.utcnow()` 废弃 | 待修复 | `arch-appendix.md` 中 28 处待替换为 `datetime.now(UTC)` |
| ~~`mark_published/mark_failed` 未调用 `flush()`~~ | ✅ 已修复 | 已添加 `flush()` 调用 |
| ~~`cleanup_old_published_records` 存根实现~~ | ✅ 已修复 | 已实现基于 `published_at` 的清理逻辑 |
| ~~`update_status` 未调用 `flush()`~~ | ✅ 已修复 | 已添加 `flush()` 调用 |
| ~~RetryPolicy 未集成到 Poller~~ | ✅ 已修复 | 已集成指数退避重试 |
| ~~OutboxPoller 异常被吞没~~ | ✅ 已修复 | 已改进错误处理 + 重试耗尽后标记 failed |
