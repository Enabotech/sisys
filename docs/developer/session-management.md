# Session 管理开发指南

> **版本**: v1.0.0
> **创建日期**: 2026-05-20
> **维护者**: Platform Team

---

## 概述

SISYS 系统使用 **ContextVar** 作为 PostgreSQL AsyncSession 的主要传递机制。本文档说明 ContextVar 工作原理、生命周期管理、测试模式和最佳实践。

---

## Session 传递判定标准

| 场景 | 传递方式 | 说明 |
|------|---------|------|
| 标准 CRUD 仓储 | ContextVar (`get_session()`) | 默认方式，无需构造函数参数 |
| PostgreSQLUnitOfWork | ContextVar (`get_session()`) | 在 `__init__` 中缓存 session 引用 |
| 后台任务（Poller/Saga） | `session_context()` 显式 scope | 独立 session 生命周期管理 |
| 审计场景（SERIALIZABLE） | 构造函数注入 `PostgreSQLManager` | 唯一例外，见 `AuditUnitOfWork` |

---

## ContextVar 工作原理

### 核心定义

```python
# src/infrastructure/storage/postgresql/session_context.py
_session_ctx: ContextVar[AsyncSession | None] = ContextVar("pg_session", default=None)
```

### 关键函数

| 函数 | 用途 | 调用者 |
|------|------|--------|
| `get_session()` | 获取当前 ContextVar 中的 session | Repository/UoW |
| `get_session_optional()` | 可选获取，返回 None 而非抛异常 | 容错场景 |
| `set_session(session)` | 设置 session 到 ContextVar | Middleware/Test |
| `reset_session(token)` | 通过 Token 重置 ContextVar | Middleware/Test |
| `session_context(factory)` | 后台任务 session 上下文管理器 | Poller/Saga |
| `with_session(session)` | 测试辅助上下文管理器 | Test Fixture |

---

## HTTP 请求生命周期

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HTTP Request                                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SessionMiddleware.dispatch()                     │
│                                                                     │
│  1. session = self._factory()          # 创建 AsyncSession          │
│  2. token = set_session(session)       # 设置 ContextVar            │
│  3. try:                                                            │
│       response = await call_next(request)                           │
│       if session.in_transaction():     # 检查 UoW 是否已管理事务    │
│           await session.commit()        # 未管理则 Middleware 提交  │
│       return response                                              │
│     except Exception:                                               │
│       if session.in_transaction():                                  │
│           await session.rollback()      # 异常时回滚                │
│       raise                                                         │
│     finally:                                                        │
│       await session.close()            # 始终关闭 session           │
│       reset_session(token)             # 重置 ContextVar            │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Application Layer (EventHandler/UseCase)          │
│                                                                     │
│  uow = uow_factory()                   # 从 DI 获取工厂             │
│  async with uow:                       # begin() 自动调用           │
│      repo = SomeRepository()           # 无参构造                   │
│      await repo.save(entity)           # 内部 get_session() 获取    │
│      await outbox_repo.save(event)     # 同一 session               │
│  # uow.__aexit__: commit (不调用 close!)                            │
│  # Middleware.finally: close + reset                                │
└─────────────────────────────────────────────────────────────────────┘
```

**关键点**：
- `session.in_transaction()` 检测 UoW 是否已管理事务（commit/rollback 后返回 False）
- UoW 只负责事务边界（begin/commit/rollback），不负责 session 关闭
- Middleware 始终负责 session.close() 和 ContextVar 重置

---

## 后台任务生命周期

```python
# 使用 session_context() 创建独立 scope
async def background_task():
    factory = resolver.resolve("session_factory")
    async with session_context(factory):    # 创建 session + set_context
        uow = PostgreSQLUnitOfWork()
        async with uow:
            await repo.save(entity)
        # session_context.__aexit__: commit + close + reset
```

**流程图**：

```
┌─────────────────────────────────────────────────────────────────────┐
│                      session_context(factory)                        │
│                                                                     │
│  1. session = factory()                # 创建 AsyncSession          │
│  2. token = set_session(session)       # 设置 ContextVar            │
│  3. try:                                                            │
│       yield session                                                │
│       await session.commit()           # 正常退出时提交             │
│     except Exception:                                               │
│       await session.rollback()         # 异常时回滚                 │
│       raise                                                         │
│     finally:                                                        │
│       await session.close()            # 始终关闭                   │
│       reset_session(token)             # 重置 ContextVar            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 测试模式

### 模式 1: `with_session()` 上下文管理器

```python
@pytest.mark.asyncio
async def test_repository_save():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()

    async with with_session(mock_session):
        repo = UserRepository()
        await repo.save(entity)

    mock_session.execute.assert_called_once()
```

### 模式 2: `set_session()` / `reset_session()` 手动管理

```python
@pytest.mark.asyncio
async def test_uow_commit():
    mock_session = AsyncMock(spec=AsyncSession)

    token = set_session(mock_session)
    try:
        uow = PostgreSQLUnitOfWork()
        async with uow:
            pass  # 业务操作
        mock_session.commit.assert_called_once()
    finally:
        reset_session(token)
```

### 模式 3: 统一 Fixture（推荐）

```python
# tests/conftest.py
@pytest.fixture
async def pg_session():
    """标准 PostgreSQL session fixture"""
    mock_session = AsyncMock(spec=AsyncSession)
    async with with_session(mock_session):
        yield mock_session


# 使用
@pytest.mark.asyncio
async def test_with_fixture(pg_session):
    repo = UserRepository()
    await repo.get_by_id(uuid4())
    pg_session.execute.assert_called()
```

---

## 当前 ContextVar 消费者清单

以下文件通过 `get_session()` 从 ContextVar 获取 session：

| 文件 | 组件 |
|------|------|
| `postgresql_unit_of_work.py` | PostgreSQLUnitOfWork |
| `outbox_repository.py` | PostgreSQLOutboxRepository |
| `postgres_dead_letter_queue.py` | PostgresDeadLetterQueue |
| `saga_repository.py` | PostgreSQLSagaRepository |
| `postgresql_adapter.py` | PostgreSQLAdapter（泛型基类） |
| `event_store.py` | EventStore |
| `dual_idempotency_checker.py` | DualIdempotencyChecker |
| `audit_repository_impl.py` | AuditRepositoryImpl |
| `memory_metadata_repository.py` | PostgreSQLMemoryMetadataRepository |
| `memory_change_history_repository.py` | PostgreSQLMemoryChangeHistoryRepository |
| `memory_group_member_repository.py` | PostgreSQLMemoryGroupMemberRepository |
| `login_attempt_repository.py` | LoginAttemptRepository |
| `role_repository.py` | RoleRepository |
| `user_role_repository.py` | UserRoleRepository |

---

## 构造函数注入例外

### AuditUnitOfWork（SERIALIZABLE 隔离级别）

```python
# src/infrastructure/messaging/unit_of_work/audit_unit_of_work.py
class AuditUnitOfWork(UnitOfWork):
    def __init__(self, manager: PostgreSQLManager) -> None:
        """注入 PostgreSQLManager 以创建 SERIALIZABLE 隔离级别的 session"""
        self._manager = manager
        # ...

    async def begin(self) -> None:
        self._session_ctx = self._manager.get_session_with_isolation("SERIALIZABLE")
        self._session = await self._session_ctx.__aenter__()
        await self._session.begin()
```

**何时使用构造函数注入**：
1. 需要非默认隔离级别（SERIALIZABLE / REPEATABLE_READ）
2. 需要独立于请求 scope 的 session 生命周期
3. 需要自定义 session 配置（只读 session、特定 schema 搜索路径）

---

## 常见错误与调试

### 错误 1: RuntimeError: No AsyncSession in context

**原因**：在 ContextVar 未设置时调用 `get_session()`

**解决方案**：
- HTTP 请求：确保 `SessionMiddleware` 已正确配置
- 后台任务：使用 `session_context()` 包装
- 测试：使用 `with_session()` 或 `set_session()` fixture

### 错误 2: 双重 commit/close

**原因**：UoW 和 Middleware 都尝试提交/关闭 session

**解决方案**：
- 确保 PostgreSQLUnitOfWork `__aexit__` 不调用 `close()`（当前已修复）
- Middleware 使用 `session.in_transaction()` 检测 UoW 状态

### 错误 3: 测试中 ContextVar 泄漏

**原因**：`set_session()` 后未调用 `reset_session()`

**解决方案**：
- 使用 `with_session()` 上下文管理器（自动重置）
- 或确保 `try/finally` 中调用 `reset_session(token)`

---

## 最佳实践

1. **新建仓储**：无参构造 + `_session` 属性通过 `get_session()` 获取
2. **EventHandler 使用 UoW**：从 DI 获取 `uow_factory`，`async with uow:` 管理事务
3. **后台任务**：使用 `session_context()` 显式管理 session 生命周期
4. **测试**：优先使用 `with_session()` 或统一 `pg_session` fixture
5. **特殊隔离级别**：参考 `AuditUnitOfWork` 模式，注入 `PostgreSQLManager`

---

## 参考文件

- `src/infrastructure/storage/postgresql/session_context.py` — ContextVar 核心模块
- `src/infrastructure/middleware/session_middleware.py` — HTTP 请求 session 生命周期
- `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` — UoW 实现
- `src/infrastructure/messaging/unit_of_work/audit_unit_of_work.py` — 构造函数注入先例
- `src/composition_root.py` — DI 注册（`uow_factory`, `session_factory`）
