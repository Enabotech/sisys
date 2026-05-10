# SISYS EDA + UnitOfWork 宗师级设计方案

> **文档版本：** 1.0.0
> **创建日期：** 2026-05-10
> **状态：** 已批准
> **维护者：** Agimtech

---

## 1. 背景与问题陈述

### 1.1 当前架构状态

Story 20.2（事件消息体系重构）已完成 AC-1 至 AC-10 的全部验收，但**AC-6（UnitOfWork 统一事务边界）存在重大设计缺失**：

| 组件 | 实现状态 | 问题 |
|------|---------|------|
| `PostgreSQLUnitOfWork` | 存在但无引用 | 生产代码从未使用，沦为废弃抽象 |
| `OutboxRepository` | 直接接收 `AsyncSession` | 事务边界依赖调用者"碰巧共享同一 session" |
| `PostgreSQLEventStore` | 直接接收 `AsyncSession` | 同上 |
| Event Handlers | 通过依赖注入获取 session | 无任何机制强制"业务操作与 outbox 写入共用同一事务" |

### 1.2 根本问题

**事务边界隐式共享，而非显式强制。**

```
当前架构（危险）
─────────────────────────────────────────────────────
UseCase / EventHandler
    ├── RepositoryA(session)   ← 你传的
    ├── RepositoryB(session)   ← 你传的（是同一个吗？）
    └── RepositoryC(session)   ← 你传的（是同一个吗？）
                                      ↑
                            没人强制验证
                            只能靠"约定"和 code review
```

### 1.3 风险量化

| 风险场景 | 概率 | 影响 | 后果 |
|---------|------|------|------|
| 新增 Repository 忘记传入同一 session | 中 | 高 | 业务成功 + outbox 失败 = 数据不一致 |
| 重构时切错 session 导致跨事务写入 | 中 | 极高 | 幽灵事件（outbox 有记录但业务未提交） |
| 测试/mock 时行为与生产不一致 | 高 | 中 | 测试通过但生产故障 |
| 未来新增事件处理器违反事务约定 | 中 | 高 | 幂等性双重检查失效 |

---

## 2. 业界最佳实践对标

### 2.1 四大框架对比

| 框架 | 事务管理模式 | Outbox 实现 | 评价 |
|------|-------------|-------------|------|
| **Axon Framework (Java)** | `UnitOfWork` + `TransactionManager` | `JpaEventStorageEngine` 同一 transaction 写入 | ✅ 事务边界显式，UnitOfWork 是一等公民 |
| **Eventuate Local (Java)** | `AggregateRepository` 管理事务 | `EventuateTramOutbox` 同一 JDBC transaction | ✅ 教科书级 Outbox + UoW 集成 |
| **NServiceBus (C#)** | `IUnitOfWork` 接口 | DB Outbox 表，同一 transaction | ✅ 生产级验证，业界标准 |
| **Spring Cloud Stream** | `@Transactional` AOP 代理 | 同一 transaction 写 outbox | ⚠️ 依赖 AOP，污染侵入性较强 |

**核心共识**：Outbox Pattern 的关键是**业务表 + outbox 表必须在同一数据库事务中写入**。

### 2.2 SQLAlchemy 官方推荐模式

SQLAlchemy 文档推荐的 `AsyncSession` 作为"ambient transaction context"模式：

```python
# 官方推荐：session 作为 ambient transaction carrier
async with async_session() as session:
    await session.execute(...)
    # 在同一 transaction 内多个 repository 共享 session
```

**问题**：Session 通过构造器注入，无法在**编译期/类型系统**强制验证"多个 Repository 使用同一个 session"。

### 2.3 Microsoft eShop 参考实现

```csharp
// eShop 采用 IUnitOfWork 统一事务边界
public class OrderService
{
    public async Task PlaceOrder(IUnitOfWork unitOfWork, OrderCommand command)
    {
        // 所有 Repository 通过 unitOfWork 获取 session
        var orderRepo = unitOfWork.OrderRepository;
        var outboxRepo = unitOfWork.OutboxRepository;

        // 事务边界显式：commit/rollback 在 unitOfWork 层面
        await unitOfWork.BeginAsync();
        await orderRepo.Add(order);
        await outboxRepo.Save(order.ChangedEvent);
        await unitOfWork.CommitAsync();
    }
}
```

---

## 3. 宗师级解决方案

### 3.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **事务边界显式化** | 所有事务操作必须通过 `PostgreSQLUnitOfWork`，禁止绕过 |
| **类型系统强制** | Repository 构造器接收 `PostgreSQLUnitOfWork` 而非直接接收 `AsyncSession` |
| **向后兼容** | 现有不涉及 outbox 的 Repository 保持直接 session 注入模式 |
| **渐进式迁移** | 新增代码优先使用 UoW，不强制要求重构现有代码 |

### 3.2 架构重构

```
重构后：显式事务协调（安全）
─────────────────────────────────────────────────────
UseCase / EventHandler
    └── async with uow:          ← 事务边界显式声明
            ├── repo_a(uow.session)  ← 同一 session（类型系统强制）
            ├── repo_b(uow.session)  ← 同一 session
            └── repo_c(uow.session)  ← 同一 session
                                      ↑
                                类型系统强制保证
```

### 3.3 PostgreSQLUnitOfWork 增强设计

```python
# src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py

class PostgreSQLUnitOfWork:
    """事务作用域 + session 管理（增强版）

    职责：
    1. 管理 AsyncSession 生命周期
    2. 提供 session 属性访问器（所有 Repository 必须通过这里获取 session）
    3. 防止重复 commit（guard）
    4. 支持嵌套事务（savepoint）
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._committed = False
        self._rolled_back = False

    @property
    def session(self) -> AsyncSession:
        """所有 Repository 必须通过这里获取 session"""
        return self._session

    async def commit(self) -> None:
        """显式提交 + 幂等标记"""
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚 + 标记"""
        await self._session.rollback()
        self._rolled_back = True

    async def begin_nested(self) -> None:
        """创建 savepoint，支持嵌套事务"""
        await self._session.begin_nested()

    async def release_nested(self) -> None:
        """释放 savepoint"""
        await self._session.commit()  # savepoint commit

    # async with 协议支持
    async def __aenter__(self) -> "PostgreSQLUnitOfWork":
        await self._session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "TracebackType | None",
    ) -> bool:
        """异步上下文管理器出口

        规则：
        - 异常：rollback（即使已部分 commit）
        - 正常：commit
        - 始终 close session
        """
        if exc_type is not None:
            await self.rollback()
        elif not self._committed and not self._rolled_back:
            await self.commit()
        await self.close()
        return False  # 不吞没异常
```

### 3.4 Repository 改造

```python
# 旧模式（危险）- 直接接收 session
class SomeRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

# 新模式（安全）- 通过 UoW 获取 session
class SomeRepository:
    def __init__(self, uow: PostgreSQLUnitOfWork):
        self._session = uow.session  # 只能通过 uow 获取

# 向后兼容模式 - 接收 session 或 uow 均可
from typing import Union
class SomeRepository:
    def __init__(self, session_or_uow: Union[AsyncSession, PostgreSQLUnitOfWork]):
        if isinstance(session_or_uow, PostgreSQLUnitOfWork):
            self._session = session_or_uow.session
        else:
            self._session = session_or_uow  # 保持旧接口兼容
```

### 3.5 事务边界强制点

**以下场景必须使用 PostgreSQLUnitOfWork**：

| 场景 | 原因 |
|------|------|
| Event Handler 处理 `DocumentProcessed` | 需要同时写业务表 + outbox 表 |
| `AsyncOutboxPoller` 发布事件 | 需要事务性读取 + 更新状态 |
| Checkpoint 创建 | 需要同时更新业务状态 + 写 CheckpointEvent + 更新 Outbox |
| 任何涉及"业务表 + outbox 表双写"的场景 | 必须保证原子性 |

**以下场景可保持直接 session 注入**：

| 场景 | 原因 |
|------|------|
| 纯查询 Repository | 不涉及事务写入 |
| 单表 CRUD（无 outbox 依赖） | 无双写需求 |
| 只读 Event Handler | 不写业务表 |

---

## 4. 与 Story 20.2 的集成

### 4.1 AC-6 重定义

**原文**：
> AC-6: UnitOfWork 统一事务边界
> 业务操作与 Outbox 写入应该在同一事务中

**补充明确**：
> 验收标准补充：
> - [ ] `PostgreSQLUnitOfWork.session` 属性强制所有 Repository 通过其获取 session
> - [ ] 涉及 outbox 写入的 Event Handler 必须使用 UoW
> - [ ] 事务边界在 `async with uow:` 块级别显式声明

### 4.2 依赖关系

```
AC-1 PostgreSQL DLQ ──┐
AC-2 Redis Retry ────┼── AC-8 RabbitMQEventListener ── AC-6 UoW（事务边界）
AC-3 DualIdempotency ─┘         │
                                 ▼
                    Event Handler（使用 UoW 保证原子性）
                                 │
                                 ▼
                    PostgreSQLOutboxRepository（通过 uow.session 写入）
                    BusinessRepository（通过 uow.session 写入）
```

### 4.3 架构验证测试

```python
# tests/unit/infrastructure/test_uow_transaction_boundary.py

class TestUoWTransactionBoundary:
    """验证事务边界强制：涉及 outbox 的路径必须使用 UoW"""

    def test_outbox_repository_receives_uow(self):
        """OutboxRepository 必须通过 PostgreSQLUnitOfWork 获取 session"""
        uow = PostgreSQLUnitOfWork(session=mock_session)
        repo = PostgreSQLOutboxRepository(uow)  # 传入 uow
        assert repo._session is uow.session

    def test_event_handler_uses_uow_for_atomic_write(self):
        """EventHandler 必须使用 UoW 保证业务+outbox 原子性"""
        uow = PostgreSQLUnitOfWork(session=session)
        handler = DocumentProcessedHandler(
            business_repo=SomeBusinessRepo(uow),
            outbox_repo=PostgreSQLOutboxRepository(uow),
        )
        # 在 uow 上下文中执行
        async with uow:
            await handler.handle(event)
        # commit/rollback 由 uow 管理

    def test_no_direct_session_injection_for_outbox_paths(self):
        """架构验证：outbox 路径禁止直接注入 session"""
        # 检测所有接收 AsyncSession 的 Repository
        # 筛选涉及 outbox 写入的类
        # 验证它们都通过 uow 获取 session
```

---

## 5. 迁移路径

### Phase 1：清理 + 基础设施完善（1-2 天）

**任务**：
1. 删除废弃测试代码（`test_story_20_2.feature` 中 AC-6 的空测试场景）
2. 完善 `PostgreSQLUnitOfWork`：`session` 属性、guard 逻辑
3. 创建 `tests/unit/infrastructure/test_uow_transaction_boundary.py`

**完成标准**：
- [ ] `PostgreSQLUnitOfWork` 拥有 `session` 属性访问器
- [ ] 重复 commit/rollback 会抛出 `InvalidStateError`
- [ ] 架构验证测试通过

### Phase 2：新增代码使用 UoW（持续）

**规则**：
- 新增 EventHandler 涉及 outbox 写入时，优先使用 `PostgreSQLUnitOfWork`
- 新增 Repository 涉及双写场景时，通过 `uow.session` 获取 session

**模板**：
```python
# 新增 EventHandler 模板
class SomeEventHandler:
    def __init__(self, uow: PostgreSQLUnitOfWork):
        self._business_repo = SomeBusinessRepo(uow)
        self._outbox_repo = PostgreSQLOutboxRepository(uow)

    async def handle(self, event: DomainEvent) -> None:
        async with self._uow:  # 事务边界
            await self._business_repo.update(event)
            self._outbox_repo.save(SomeEvent.from_event(event))
        # commit on exit, rollback on exception
```

### Phase 3：核心路径迁移（当业务需要时）

**优先级**：
1. `DocumentProcessedHandler`（最关键，涉及 WORM 归档）
2. `AsyncOutboxPoller`（事件发布的事务性保证）
3. `CheckpointReachedHandler`（战略规划核心路径）

**迁移检查清单**：
- [ ] 所有涉及 outbox 写入的 Repository 已改造为接收 `PostgreSQLUnitOfWork`
- [ ] Event Handler 在 `async with uow:` 块内执行
- [ ] 集成测试验证"业务表 + outbox 表原子性"
- [ ] 故障注入测试（session 共享失败场景）

---

## 6. 决策权衡

### 6.1 为什么不用 Spring `@Transactional` 注解？

| 维度 | AOP 注解模式 | UoW 显式模式 |
|------|-------------|-------------|
| 侵入性 | 高（需要代理/AOP） | 低（纯 Python，无代理） |
| 可测试性 | 差（需要特殊测试夹具） | 好（mock uow 即可） |
| 事务边界可见性 | 隐式（需要查看注解） | 显式（代码中可见） |
| 与六边形架构契合度 | 低（框架强耦合） | 高（接口隔离） |
| SQLAlchemy 兼容性 | 一般 | 极佳（session 即 transaction） |

**结论**：Python 无Spring 式AOP代理，UoW 模式是最契合六边形架构的选择。

### 6.2 为什么不用"保持现状 + code review"？

| 维度 | code review 约束 | UoW 类型系统强制 |
|------|-----------------|-----------------|
| 人为纪律性依赖 | 高 | 无 |
| 新人上手难度 | 高（需要理解约定） | 低（类型系统引导） |
| 重构安全性 | 低（容易遗漏） | 高（编译器报错） |
| 可追溯性 | 低（约定散落各处） | 高（代码即文档） |

**结论**：code review 无法捕获所有边界情况。类型系统强制是工业级最佳实践。

---

## 7. 结论

### 7.1 推荐方案

| 决策 | 选择 |
|------|------|
| **方案** | PostgreSQLUnitOfWork 作为核心事务协调器 |
| **架构模式** | Repository 通过 uow.session 获取 session，EventHandler 在 async with uow 块内执行 |
| **迁移策略** | 渐进式（Phase 1 清理 + 完善基础设施，Phase 2-3 按需迁移） |

### 7.2 关键收益

| 收益 | 说明 |
|------|------|
| **编译期事务边界保证** | 违反事务约定的代码无法通过类型检查 |
| **可测试性提升** | mock 一个 uow vs mock 多个 session |
| **架构合规性** | 符合 Axon/Eventuate/Microsoft 业界最佳实践 |
| **零成本复用** | 废弃的 `PostgreSQLUnitOfWork` 正好用于此目的 |

### 7.3 风险缓解

| 风险 | 缓解措施 |
|------|---------|
| 迁移成本高 | 渐进式迁移，不要求一次性全部重构 |
| 向后兼容破坏 | Repository 支持"session 或 uow"双模式构造 |
| 测试改造成本大 | Phase 1 同步完善架构验证测试 |

---

## 8. 参考资料

| 来源 | 引用 |
|------|------|
| Axon Framework | `UnitOfWork` + `TransactionManager` pattern |
| Eventuate Local | `EventuateTramOutbox` + JDBC transaction |
| NServiceBus | `IUnitOfWork` + Outbox pattern |
| Microsoft eShop | `IUnitOfWork` + Repository pattern |
| SQLAlchemy Docs | AsyncSession as ambient transaction context |
| Story 20.2 | AC-6 UnitOfWork 统一事务边界 |
| Architecture.md | 第 10 章 事件驱动架构设计 |
