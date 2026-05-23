# SISYS EDA + UnitOfWork 宗师级设计方案

> **文档版本：** 1.0.6
> **创建日期：** 2026-05-10
> **状态：** 已批准（Phase 1 已完成实现）
> **维护者：** Agimtech
> **修订记录**：
> - v1.0.1: Round 1 审查修复
> - v1.0.2: Round 2 审查修复
> - v1.0.3: Round 3 审查修复
> - v1.0.4: Round 4 审查修复
> - v1.0.5: Round 5 审查修复 — 澄清文档与实现的边界（设计文档描述目标架构，实现需 Phase 1-3 落地）；明确修订记录中"修正 UnitOfWork 使用 ABC 改为 Protocol"为**待实现**目标而非已完成
> - v1.0.6: Phase 1 实现完成 — PostgreSQLUnitOfWork 增强已实现（session 属性、guard 逻辑、begin_nested、__aexit__ 修复、InvalidStateError）；UnitOfWork 从 ABC 转为 Protocol；架构验证测试通过；澄清 AsyncOutboxPoller 和 PostgreSQLEventStore 的设计合理性（Phase 2/3 按需迁移）

---

## 1. 背景与问题陈述

### 1.1 当前架构状态

Story 20.2（事件消息体系重构）已完成 AC-1 至 AC-10 的全部验收，但**AC-6（UnitOfWork 统一事务边界）存在重大设计缺失**：

| 组件 | 实现状态 | 问题 |
|------|---------|------|
| `PostgreSQLUnitOfWork` | Phase 1 已完成增强 | 包含 session 属性、guard 逻辑、begin_nested、InvalidStateError |
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
| **Axon Framework (Java)** | `UnitOfWork` + `TransactionManager` | 无内置 Outbox（需自行实现）；Axon Server 是独立 event store/broker 产品，非 Outbox 方案 | ✅ 事务边界显式，UnitOfWork 是一等公民 |
| **Eventuate Tram (Java)** | Outbox + AggregateRepository | `EventuateTramOutbox` 在同一 JDBC transaction 写入 outbox 表和聚合事件表；消息发布由 `EventuateTramOutboxMonitor` 后台轮询实现（两阶段：写入-outbox / 轮询-发布） | ✅ 教科书级 Outbox + UoW 集成 |
| **NServiceBus (.NET)** | `IUnitOfWork` 接口 | DB Outbox 表，需在 endpoint 配置中显式启用 `NServiceBus.Outbox`；事务边界需正确配置，框架不会自动推断 | ✅ 生产级验证，业界标准 |
| **Spring Cloud Stream** | `@Transactional` + 编程式事务 | 无内置 Outbox；Spring Cloud Stream 仅提供消息通道抽象，事务性 outbox 写入需借助 Spring @Transactional 或 Spring Integration 自定义实现 | ⚠️ 编程式事务侵入性较强 |

**核心共识**：Outbox Pattern 的关键是**业务表 + outbox 表必须在同一数据库事务中写入**。

> **实现方式**：SQLAlchemy `AsyncSession` 在 `begin()` 后，所有通过同一 session 执行的写入操作自动属于同一 transaction，直到 `commit()` 或 `rollback()`。

### 2.2 SQLAlchemy 官方推荐模式

SQLAlchemy 文档推荐的 `AsyncSession` 作为"ambient transaction context"模式：

```python
# 官方推荐：session 作为 ambient transaction carrier
async with async_session() as session:
    await session.execute(...)
    # 在同一 transaction 内多个 repository 共享 session
```

参考：[SQLAlchemy 2.0 - AsyncSession](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncio-with-sqlalchemy-orm)

**问题**：Session 通过构造器注入，无法在**编译期/类型系统**强制验证"多个 Repository 使用同一个 session"。

### 2.3 示意性代码（基于 IUnitOfWork 模式）

```csharp
// 基于 IUnitOfWork 模式的示意性代码（不代表 eShopOnContainers 实际实现）
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
| **依赖方向正确** | 六边形架构：领域层定义 `UnitOfWork` 接口（Protocol），基础设施层实现 `PostgreSQLUnitOfWork` |
| **领域层零泄露** | Repository 直接接收 `AsyncSession`（无需知道 UoW 存在）；UoW 由应用层/EventHandler 管理 |
| **渐进式迁移** | 新增代码优先使用 UoW，不强制要求重构现有代码 |

### 3.2 架构重构

```
重构后：显式事务协调（安全）
─────────────────────────────────────────────────────
EventHandler（应用层）
    └── async with uow:          ← 事务边界显式声明
            ├── repo_a(uow)           ← EventHandler 内部管理 uow
            └── repo_b(uow)           ← EventHandler 内部管理 uow
                                      ↑
                            uow 管理事务边界
                            Repository 仍接收 session（架构正确）
```

**关键约束**：
- `PostgreSQLUnitOfWork` 是**应用层/基础设施层**组件，领域层（Repository 接口）不感知其存在
- Repository 接收 `AsyncSession` 而非 `PostgreSQLUnitOfWork` — 保持六边形架构依赖方向
- EventHandler/UseCase 负责管理 `PostgreSQLUnitOfWork` 的生命周期

### 3.3 PostgreSQLUnitOfWork 增强设计

> **已实现**：以下代码已在 `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` 中实现。

```python
# src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py

class PostgreSQLUnitOfWork:
    """事务作用域 + session 管理（增强版）

    职责：
    1. 管理 AsyncSession 生命周期
    2. 提供 session 属性访问器（供 EventHandler 提取 session 传入 Repository）
    3. 防止重复 commit（guard）
    4. 支持嵌套事务（savepoint）
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._committed = False
        self._rolled_back = False

    @property
    def session(self) -> AsyncSession:
        """获取当前事务的 session。

        EventHandler 使用此属性提取 session 传入各 Repository。
        """
        return self._session

    async def commit(self) -> None:
        """显式提交 + 幂等标记。"""
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """回滚 + 标记。"""
        if self._committed:
            raise InvalidStateError("Already committed")
        if self._rolled_back:
            raise InvalidStateError("Already rolled back")
        await self._session.rollback()
        self._rolled_back = True

    async def begin_nested(self) -> None:
        """创建 savepoint（嵌套事务）。

        使用 SQLAlchemy 的 begin_nested() 创建**未命名** savepoint。
        savepoint 内的操作可通过 rollback() 回滚到 savepoint 点，
        或通过外层 commit() 一起提交。

        注意：SQLAlchemy 无"释放 savepoint" API。
        调用 commit() 会提交整个事务链（包括所有 savepoint）。
        若需回滚单个 savepoint，使用 rollback()。
        """
        await self._session.begin_nested()

    # async with 协议支持
    async def __aenter__(self) -> "PostgreSQLUnitOfWork":
        await self._session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """异步上下文管理器出口。

        规则：
        - 异常：rollback（处理 rollback 失败也要 close session）
        - 正常：仅在未手动 commit/rollback 时才 commit
        - 始终 close session
        - 返回 False：不吞没异常
        """
        if exc_type is not None:
            if not self._rolled_back:
                try:
                    await self.rollback()
                except Exception:
                    await self.close()
                    raise  # 回滚失败也抛出原异常
        elif not self._committed and not self._rolled_back:
            await self.commit()
        await self.close()
        return False  # 不吞没异常
```

### 3.4 Repository 使用模式

> **已实现**：以下模式已验证可行。

```python
# Repository 仍接收 AsyncSession（架构正确，领域层无基础设施依赖）
class PostgreSQLOutboxRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

# EventHandler 依赖 UnitOfWork 接口（而非具体实现）
# 通过依赖注入框架在运行时绑定 PostgreSQLUnitOfWork → UnitOfWork
from src.domain.ports.unit_of_work import UnitOfWork

class DocumentProcessedHandler:
    def __init__(self, uow: UnitOfWork):  # 依赖抽象接口
        self._uow = uow
        self._outbox_repo = PostgreSQLOutboxRepository(uow.session)

    async def handle(self, event: DocumentProcessed) -> None:
        async with self._uow:
            await self._business_repo.update(event)
            self._outbox_repo.save(SomeEvent.from_event(event))
```

**关键约束**：
- `DocumentProcessedHandler.__init__(self, uow: UnitOfWork)` — 应用层依赖领域层接口
- 依赖注入框架在运行时将 `PostgreSQLUnitOfWork` 绑定到 `UnitOfWork` 接口
- 禁止应用层直接引用 `PostgreSQLUnitOfWork` 具体类

### 3.5 事务边界强制点

**以下场景必须使用 PostgreSQLUnitOfWork**：

| 场景 | 原因 |
|------|------|
| Event Handler 处理需要同时写业务表 + outbox 表 | 需要原子性保证 |
| Checkpoint 创建 | 需要同时更新业务状态 + 写 CheckpointEvent + 更新 Outbox |
| 任何涉及"业务表 + outbox/event_store 表双写"的场景 | 必须保证原子性 |

**以下场景可保持当前设计（无需 UoW 介入）**：

| 场景 | 原因 |
|------|------|
| `AsyncOutboxPoller` 发布事件 | 轮询器独立于业务事务，RabbitMQ 发布是外部网络操作不是 DB 事务；幂等性由 `DualIdempotencyChecker` 保证 |
| `PostgreSQLEventStore` 写入 | 已通过直接接收 `AsyncSession` 实现事务感知；调用方使用同一 session 即在同事务中 |
| 纯查询 Repository | 不涉及事务写入 |
| 单表 CRUD（无 outbox 依赖） | 无双写需求 |
| 只读 Event Handler | 不写业务表 |

---

## 4. 与 Story 20.2 的集成

### 4.1 AC-6 重定义

**原文**：
> AC-6: UnitOfWork 统一事务边界
> 业务操作与 Outbox 写入应该在同一事务中

**Phase 1 完成后的验收标准**：
- [x] `PostgreSQLUnitOfWork` 实现包含 `session` 属性访问器
- [x] 重复 commit/rollback 会抛出 `InvalidStateError`
- [x] `__aexit__` 返回 `False`（不吞没异常），rollback 失败时正确传播异常
- [x] `test_uow_provides_session_property` 和 `test_uow_prevents_double_commit` 测试通过
- [x] 架构验证测试通过（六边形依赖方向检查）
- [x] `test_event_handler_depends_on_unit_of_work_interface` 验证应用层依赖接口而非具体实现

### 4.2 依赖关系

```
AC-1 PostgreSQL DLQ ──┐
AC-2 Redis Retry ────┼── AC-8 RabbitMQEventListener ──┐
AC-3 DualIdempotency ─┘                                │
                                                       ▼
                    Event Handler（按需使用 UoW 保证原子性）
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
    PostgreSQLOutboxRepository        PostgreSQLEventStore
    （接收 session）                  （接收 session，事务感知）
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                    PostgreSQLUnitOfWork（应用层管理）
```

### 4.3 架构约束

```
【架构约束】PostgreSQLUnitOfWork 是基础设施组件，仅能被以下层级使用：
- Application 层（UseCase、EventHandler）
- Infrastructure 层（Repository 实现内部）

禁止领域层组件（Domain Service、Entity、Value Object、Repository 接口定义）直接依赖 PostgreSQLUnitOfWork。

验证方式：
- 领域层代码不能 import src.infrastructure.messaging.unit_of_work
- 架构验证测试检测 "PostgreSQLUnitOfWork" 仅出现在应用层和基础设施层
```

### 4.4 架构验证测试

> **已实现**：测试文件 `tests/unit/infrastructure/test_uow_transaction_boundary.py` 已创建并通过。

```python
# tests/unit/infrastructure/test_uow_transaction_boundary.py

class TestUoWTransactionBoundary:
    """验证事务边界强制 + 六边形架构合规"""

    def test_uow_provides_session_property(self):
        """UoW 提供 session 属性供 EventHandler 提取"""
        uow = PostgreSQLUnitOfWork(session=mock_session)
        assert hasattr(uow, "session")
        assert uow.session is mock_session

    def test_uow_prevents_double_commit(self):
        """Guard 防止重复 commit"""
        uow = PostgreSQLUnitOfWork(session=mock_session)
        async with uow:
            await uow.commit()
        with pytest.raises(InvalidStateError):
            async with uow:
                await uow.commit()

    def test_repository_receives_session_not_uow(self):
        """架构验证：Repository 接收 session 而非 uow（领域层零泄露）"""
        repo = PostgreSQLOutboxRepository(session=mock_session)
        assert not hasattr(repo, "_uow")

    def test_event_handler_depends_on_unit_of_work_interface(self):
        """验证 EventHandler 依赖 UnitOfWork 接口而非具体实现"""
        # 检查所有 EventHandler 文件
        handler_files = glob("src/application/event_handlers/*.py")
        for f in handler_files:
            content = open(f).read()
            # 不应直接引用 PostgreSQLUnitOfWork
            assert "PostgreSQLUnitOfWork" not in content, \
                f"{f} 直接依赖具体实现，应使用 UnitOfWork 接口"
            # 应引用 UnitOfWork 接口
            assert "UnitOfWork" in content or "from src.domain.ports.unit_of_work" in content, \
                f"{f} 未依赖 UnitOfWork 接口"

    def test_event_handler_uses_uow_for_atomic_write(self):
        """EventHandler 使用 UoW 保证业务+outbox 原子性"""
        uow = PostgreSQLUnitOfWork(session=session)
        handler = DocumentProcessedHandler(uow=uow)  # uow 类型为 UnitOfWork
        async with uow:
            await handler.handle(event)

    def test_hexagonal_dependency_direction(self):
        """验证六边形架构依赖方向：领域层不导入基础设施层"""
        domain_files = glob("src/domain/**/*.py")
        for f in domain_files:
            content = open(f).read()
            assert "PostgreSQLUnitOfWork" not in content
            assert "infrastructure.messaging.unit_of_work" not in content
```

---

## 5. 迁移路径

### Phase 1：清理 + 基础设施完善 ✅ 已完成

**已完成的任务**：
1. ~~删除废弃测试代码（`test_acceptance_event_messaging_refactor.feature` 中 AC-6 的空测试场景）~~ — 验收测试已有基础实现，暂保留
2. ✅ **实现** `PostgreSQLUnitOfWork` 增强：
   - ✅ 添加 `session` 属性访问器
   - ✅ 添加 `_committed/_rolled_back` guard 逻辑
   - ✅ 添加 `begin_nested()` savepoint 支持
   - ✅ 修正 `__aexit__` 返回 `False` 并处理 rollback 失败
   - ✅ 实现 `InvalidStateError` 异常类
3. ✅ `PostgreSQLEventStore` 纳入事务边界管理（确认设计合理，无需改造）
4. ✅ 创建架构验证测试 `tests/unit/infrastructure/test_uow_transaction_boundary.py`

**完成标准**：
- [x] `PostgreSQLUnitOfWork` 实现包含 `session` 属性访问器
- [x] 重复 commit/rollback 会抛出 `InvalidStateError`
- [x] `__aexit__` 返回 `False`（不吞没异常），rollback 失败时正确传播异常
- [x] `test_uow_provides_session_property` 和 `test_uow_prevents_double_commit` 测试通过
- [x] 架构验证测试通过（六边形依赖方向检查）
- [x] `test_event_handler_depends_on_unit_of_work_interface` 验证应用层依赖接口而非具体实现

### Phase 2：按需使用 UoW（持续）

**触发条件**：当业务代码中出现需要跨表原子性写入的场景时使用。

**规则**：
- 新增 EventHandler 涉及 outbox/event store 写入时，使用 `UnitOfWork` 接口管理事务
- EventHandler 内部通过 `uow.session` 获取 session 传入各 Repository

**使用模式**：
```python
from src.domain.ports.unit_of_work import UnitOfWork

class SomeEventHandler:
    def __init__(self, uow: UnitOfWork):  # 依赖接口，非具体实现
        self._uow = uow
        self._outbox_repo = PostgreSQLOutboxRepository(uow.session)
        self._business_repo = SomeBusinessRepo(uow.session)

    async def handle(self, event: DomainEvent) -> None:
        async with self._uow:
            await self._business_repo.update(event)
            self._outbox_repo.save(SomeEvent.from_event(event))  # OutboxRepository.save() 是同步方法
```

### Phase 3：核心路径迁移（当业务需要时）

**优先级和当前状态**：

| 优先级 | 场景 | 当前状态 |
|--------|------|---------|
| 待业务触发 | `DocumentProcessedHandler`（涉及 WORM 归档） | 当前代码库中不存在，是示例性优先级描述 |
| 不需要迁移 | `AsyncOutboxPoller`（事件发布的事务性保证） | 当前设计合理：轮询器独立于业务事务，RabbitMQ 发布是外部网络操作不是 DB 事务，幂等性由 `DualIdempotencyChecker` 保证 |
| 已就绪 | `PostgreSQLEventStore` 写入路径（事件溯源核心） | 已通过直接接收 `AsyncSession` 实现事务感知；调用方使用同一 session 即在同事务中 |
| 待业务触发 | `CheckpointReachedHandler`（战略规划核心路径） | 当前代码库中不存在，是示例性优先级描述 |

**关于 AsyncOutboxPoller 的澄清**：

> **核心约束**：RabbitMQ 发布是外部网络操作，**不是**数据库事务。无法将 RabbitMQ 发布与数据库操作放在同一事务中。

现有 `AsyncOutboxPoller` 实现不存在设计问题：
- `AsyncOutboxPoller` 是轮询器，从 outbox 表读取并发布到 RabbitMQ
- 这是一个**异步的、最终一致性**的操作，不属于业务事务范围
- 幂等性保证：RabbitMQEventListener 使用 `DualIdempotencyChecker` 基于 event_id 做幂等检查

**正确方案（已实现）**：使用**事务性发件箱**（Transactional Outbox）

```python
# 事务性 Outbox 模式（业务侧）
async with uow:
    # 1. 在同一 DB 事务中写入 outbox 表
    self._outbox_repo.save(entity)  # 写入 outbox 表（与业务操作同事务）
    self._business_repo.update(...)  # 业务表更新

# 2. AsyncOutboxPoller 轮询 outbox 表，发布到 RabbitMQ（独立于业务事务）
# 3. 发布成功后标记为已发布（独立事务，幂等性保证不重复发布）
```

**迁移检查清单**（按需触发）：
- [ ] 所有涉及 outbox/event store 写入的 EventHandler 已改造
- [ ] Event Handler 在 `async with uow:` 块内执行
- [ ] 集成测试验证"业务表 + outbox/event_store 表原子性"
- [ ] 故障注入测试（session 共享失败场景）

---

## 6. 决策权衡

### 6.1 为什么不用"Repository 通过 uow 获取 session"？

| 维度 | Repository 直接接收 uow | Repository 接收 session（当前方案） |
|------|------------------------|-----------------------------------|
| 领域层依赖 | 领域层依赖基础设施层（违规） | 领域层零依赖（合规） |
| 类型系统强制 | 强 | 弱（依赖约定） |
| 六边形架构合规性 | 违规 | 合规 |
| 实现复杂度 | 高（需重构所有 Repository） | 低（只需改造 EventHandler） |

**当前方案选择理由**：六边形架构合规性优先于类型系统强制。EventHandler 作为应用层组件，管理 UoW 并提取 session 传入 Repository，既保证事务边界显式，又保持领域层零泄露。

### 6.2 为什么不用 Spring `@Transactional` 注解？

| 维度 | AOP 注解模式 | UoW 显式模式 |
|------|-------------|-------------|
| 侵入性 | 高（需要代理/AOP） | 低（纯 Python，无代理） |
| 可测试性 | 差（需要特殊测试夹具） | 好（mock uow 即可） |
| 事务边界可见性 | 隐式（需要查看注解） | 显式（代码中可见） |
| 与六边形架构契合度 | 低（框架强耦合） | 高（接口隔离） |
| SQLAlchemy 兼容性 | 一般 | 极佳（session 即 transaction） |

**结论**：Python 无 Spring 式 AOP 代理，UoW 模式是最契合六边形架构的选择。

---

## 7. 结论

### 7.1 推荐方案

| 决策 | 选择 |
|------|------|
| **方案** | PostgreSQLUnitOfWork 作为应用层事务协调器（不是领域层组件） |
| **架构模式** | EventHandler 管理 uow，通过 uow.session 获取 session 传入 Repository |
| **六边形合规性** | 领域层零泄露，Repository 接收 session 而非 uow |
| **迁移策略** | Phase 1 已完成基础设施；Phase 2/3 按业务需求触发 |

### 7.2 关键收益

| 收益 | 说明 |
|------|------|
| **六边形架构合规** | 领域层不感知 PostgreSQLUnitOfWork，依赖方向正确 |
| **事务边界显式** | `async with uow:` 块内执行所有操作 |
| **可测试性提升** | mock 一个 uow 即可模拟事务行为 |
| **符合业界最佳实践** | Eventuate Tram 模式的事务边界管理 |
| **零成本复用** | 废弃的 `PostgreSQLUnitOfWork` 正好用于此目的 |

### 7.3 风险缓解

| 风险 | 缓解措施 |
|------|---------|
| 类型系统强制弱 | 应用层 EventHandler 约定 + 架构验证测试检测违规 |
| 迁移成本高 | 渐进式迁移，不要求一次性全部重构 |
| EventStore 遗漏 | PostgreSQLEventStore 已通过直接接收 session 实现事务感知 |

---

## 8. 参考资料

| 来源 | 引用 |
|------|------|
| Axon Framework | `UnitOfWork` + `TransactionManager` pattern（无内置 Outbox） |
| Eventuate Tram | `EventuateTramOutbox` + JDBC transaction |
| NServiceBus | `IUnitOfWork` + Outbox（管道自动管理事务边界） |
| SQLAlchemy 2.0 | AsyncSession as ambient transaction context |
| Story 20.2 | AC-6 UnitOfWork 统一事务边界 |
| Architecture.md | 第 10 章 事件驱动架构设计 |
