# Story 20-7: 事务子系统重构

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现事务子系统重构（Session 生命周期治理、UoW DI 注册、Outbox 完善、Saga 基础设施）,
**So that** 事务边界显式化、跨存储操作可靠执行、六边形架构合规。

### 业务价值

Epic 20 前序 Story（20-1 ~ 20-6）完成了测试框架、事件总线、异步重构、统一存储架构、端口契约测试等重大改造。当前事务子系统存在 8 个关键问题（P1-P8）：

| # | 问题 | 严重程度 | 现状 |
|---|------|---------|------|
| P1 | Session 生命周期双重管理冲突 | **中** | UoW.__aexit__ close() + Middleware close() 双重关闭（潜在风险，生产未使用 UoW） |
| P2 | UnitOfWork 未在 DI 容器注册 | **高** | composition_root.py 无 uow 注册；EventHandler 无法获取 UoW |
| P3 | Saga 仅停留在设计文档 | **中** | arch-appendix.md 附录J 的 10 个场景无代码实现 |
| P4 | 事务隔离级别未配置 | **中** | 全部使用默认 READ COMMITTED |
| P5 | 设计文档示例与实际代码不一致 | **中** | 已在 v1.0.5 修正 |
| P6 | OutboxEntity archived 状态与 DB 约束冲突 | **高** | CheckConstraint 缺 archived |
| P7 | InMemoryOutboxRepository 绕过状态机 | **中** | 直接赋值字段，无状态校验 |
| P8 | Saga 设计代码使用废弃 datetime.utcnow() | **低** | 实现时修正 |

| 指标 | 现状 | 目标 |
|------|------|------|
| UoW DI 注册 | 0 | UnitOfWorkFactory 注册完成 |
| Saga 基础设施 | 0 | Orchestrator + Repository + 3 个场景 |
| Outbox archived 状态 | 约束冲突 | 修复 CheckConstraint |
| 事务隔离级别 | 仅默认 | 支持 SERIALIZABLE/REPEATABLE READ |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Session 生命周期职责分离

**Given** PostgreSQLUnitOfWork 和 SessionMiddleware 存在双重 close() 调用风险
**When** 重构 UoW 移除 close() 调用 + Middleware 条件化 commit/rollback
**Then** UoW 只管理事务边界（begin/commit/rollback），Middleware 负责 session 生命周期（create/close）

**验证标准:**
- [ ] PostgreSQLUnitOfWork.__aexit__ 不调用 close()
- [ ] SessionMiddleware 检查 is_uow_managed() 标记决定是否 commit/rollback
- [ ] 所有现有测试通过

### AC-2: UnitOfWorkFactory Protocol + DI 注册

**Given** UnitOfWork 未在 DI 容器注册
**When** 定义 UnitOfWorkFactory Protocol 并注册为 TRANSIENT 端口
**Then** EventHandler 可通过 DI 获取 UoW 工厂

**验证标准:**
- [ ] `src/domain/ports/unit_of_work.py` 新增 UnitOfWorkFactory(Protocol)
- [ ] composition_root.py 注册 uow_factory 端口
- [ ] 契约测试验证 UnitOfWorkFactory 接口方法

### AC-3: UoW 实例级标志位（修复类级别共享 bug）

**Given** PostgreSQLUnitOfWork._committed/_rolled_back 是类属性（多实例共享状态）
**When** 改为实例属性
**Then** 每个实例独立管理事务状态

**验证标准:**
- [ ] _committed 和 _rolled_back 改为实例属性（在 __init__ 中初始化）
- [ ] 新增 __init__ 方法
- [ ] 测试验证多实例状态隔离

### AC-4: Outbox archived 状态修复 + 状态机修复

**Given** OutboxEntity.archived 与 DB CheckConstraint 冲突，InMemoryOutboxRepository 绕过状态机
**When** 修复 CheckConstraint + 重构状态机调用
**Then** archived 状态可持久化，状态转换通过 entity 方法

**验证标准:**
- [ ] CheckConstraint 添加 'archived' 状态
- [ ] InMemoryOutboxRepository.mark_published() 调用 entity.mark_published()
- [ ] InMemoryOutboxRepository.mark_failed() 调用 entity.mark_failed()
- [ ] PostgreSQLOutboxRepository.mark_published() 添加前置状态校验
- [ ] PostgreSQLOutboxRepository.mark_failed() 添加前置状态校验

### AC-5: Outbox 清理策略 + RetryPolicy 集成

**Given** Outbox 表无清理策略，AsyncOutboxPoller 未使用 RetryPolicy
**When** 实现定期清理 + 集成现有 RetryPolicy
**Then** 已发布记录可清理，失败重试有指数退避

**验证标准:**
- [ ] 新增 cleanup_old_published_records() 方法
- [ ] AsyncOutboxPoller 使用 RetryPolicy 计算退避时间
- [ ] 测试验证清理不影响 pending 事件

### AC-6: 事务隔离级别配置 + 审计专用 UoW

**Given** 全部使用默认 READ COMMITTED 隔离级别
**When** 实现隔离级别配置 + 审计专用 UoW
**Then** 支持 SERIALIZABLE/REPEATABLE READ 隔离级别

**验证标准:**
- [ ] PostgreSQLManager.get_async_session() 支持 isolation_level 参数（当前代码完全无 isolation 支持，需新增）
- [ ] AuditUnitOfWork 使用 SERIALIZABLE 隔离级别
- [ ] 测试验证隔离级别生效

### AC-7: Saga 基础设施（Orchestrator + Context + Repository + 领域端口）

**Given** Saga 仅存在于设计文档
**When** 实现 saga 模块 + 领域端口 + DI 注册
**Then** SagaOrchestrator 可执行多步骤流程并持久化状态

**验证标准:**
- [ ] `src/infrastructure/saga/` 模块创建（5 个文件）
- [ ] `src/domain/ports/saga.py` 定义 SagaStep Protocol
- [ ] `src/domain/events/saga_events.py` 定义 SagaStatusChanged
- [ ] saga_instance 表迁移脚本
- [ ] composition_root.py 注册 saga_repository

### AC-8: Saga 场景落地（S01-S03 混合式）

**Given** Saga 基础设施已完成
**When** 实现 S01-S03 具体场景
**Then** 文档处理、战略规划创建、Checkpoint 保存 Saga 可运行

**验证标准:**
- [ ] S01 文档处理 Saga（混合式：事件触发 + Orchestrator）
- [ ] S02 战略规划创建 Saga（编排式 + SERIALIZABLE）
- [ ] S03 Checkpoint 保存 Saga（编排式 + REPEATABLE READ）
- [ ] 集成测试验证正向流程 + 补偿流程

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

#### 领域事件 Schema (Domain Events)
- [ ] SagaStatusChanged 定义于 `src/domain/events/saga_events.py`
- [ ] 继承 DomainEvent，含 saga_id / saga_type / old_status / new_status 属性

#### 数据模型 (Data Models)
- [ ] SagaContext 定义于 `src/infrastructure/saga/saga_context.py`
- [ ] 含 saga_id / status / steps_data / errors / to_dict() 序列化方法
- [ ] OutboxEntity archived 状态支持

#### API 契约 (API Contract)
- [ ] SagaRepository 接口定义于 `src/domain/ports/saga.py`
- [ ] UnitOfWorkFactory 接口定义于 `src/domain/ports/unit_of_work.py`

#### 统一端口注册与接口治理
- [ ] 新增端口：uow_factory（UnitOfWorkFactory → PostgreSQLUnitOfWork，TRANSIENT）
- [ ] 新增端口：saga_repository（SagaRepositoryProtocol → PostgreSQLSagaRepository，SCOPED）
- [ ] 修改端口：UnitOfWork Protocol 移除 close() 方法
- [ ] 端口契约测试更新

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

#### 验收标准 Gherkin (Acceptance Tests)

**功能测试文件：** `tests/acceptance/test_story_20_7.feature`

```gherkin
Feature: 事务子系统重构
  作为系统架构师
  我要实现事务子系统的完整重构
  以确保事务边界显式化、跨存储操作可靠执行

  Background:
    Given 端口注册中心已初始化

  Scenario: UoW 不调用 close，由 Middleware 负责
    Given PostgreSQLUnitOfWork 实例
    When 执行 async with uow: 代码块
    Then uow.__aexit__ 不调用 session.close()
    And Middleware 负责关闭 session

  Scenario: UnitOfWorkFactory 可通过 DI 获取
    Given 端口注册中心已初始化
    When 调用 resolver.resolve("uow_factory")
    Then 返回 UnitOfWorkFactory 实例
    And 调用 factory() 返回新 UnitOfWork 实例

  Scenario: Saga 正向执行成功
    Given SagaOrchestrator 和 2 个 SagaStep
    When 执行 orchestrator.execute(steps)
    Then 两个 Step 按顺序执行
    And SagaContext 状态为 COMPLETED

  Scenario: Saga Step 失败触发补偿
    Given SagaOrchestrator 和 3 个 SagaStep（第 2 个失败）
    When 执行 orchestrator.execute(steps)
    Then Step 1 的 compensate() 被调用
    And SagaContext 状态为 COMPENSATED
```

**Task 0 完成标志：**
- [ ] Gherkin 验收测试已编写
- [ ] 规范项全部定义完毕

---

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | PostgreSQLUnitOfWork | 实例级标志位、不调用 close | `test_postgresql_unit_of_work.py` | Task 1 |
| **TDD 单元测试** | SessionMiddleware | UoW 感知 commit/rollback | `test_session_middleware.py` | Task 2 |
| **TDD 契约测试** | UnitOfWorkFactory | Protocol 方法存在性 | `test_port_contract_uow_factory.py` | Task 3 |
| **TDD 单元测试** | Outbox 状态机 | archived 持久化、状态转换 | `test_outbox_state_machine.py` | Task 4 |
| **TDD 单元测试** | Outbox 清理 | 清理策略、RetryPolicy | `test_outbox_cleanup.py` | Task 5 |
| **TDD 单元测试** | AuditUnitOfWork | SERIALIZABLE 隔离级别 | `test_audit_unit_of_work.py` | Task 6 |
| **TDD 单元测试** | SagaOrchestrator | 正向执行、补偿 | `test_saga_orchestrator.py` | Task 7 |
| **TDD 单元测试** | SagaContext | 状态管理、序列化 | `test_saga_context.py` | Task 7 |
| **TDD 集成测试** | SagaRepository | PostgreSQL 持久化 | `test_saga_repository.py` | Task 8 |
| **TDD 集成测试** | Saga 场景 | S01-S03 端到端 | `test_saga_scenarios.py` | Task 9 |
| **SDD 架构验证** | 六边形架构 | 依赖方向、零依赖 | `test_uow_transaction_boundary.py` | Task 10 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（SagaStep Protocol 验证）
- [ ] **基础设施层覆盖率 ≥75%**（Saga 实现、UoW 实现）

> **Saga 新增模块覆盖率豁免：** Phase 3-4 新增的 saga 模块首次实现时，覆盖率要求可临时降低至整体≥30%。后续优化时恢复标准。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）

#### 测试隔离约束

| 约束类型 | 规则 |
|---------|------|
| **事务隔离** | 集成测试使用 transaction rollback |
| **Schema 自创建** | fixture 内完成 Schema 初始化 |
| **资源唯一性** | 测试数据使用 UUID |
| **ContextVar 隔离** | 每个 UoW 实例独立 session scope |

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Session 生命周期职责分离 | Task 1, Task 2 | UoW 不 close + Middleware 适配 | `test_postgresql_unit_of_work.py`, `test_session_middleware.py` |
| AC-2 | UnitOfWorkFactory Protocol + DI 注册 | Task 3 | Protocol 定义 + 注册 | `test_port_contract_uow_factory.py` |
| AC-3 | UoW 实例级标志位 | Task 1 | __init__ + 实例属性 | `test_postgresql_unit_of_work.py` |
| AC-4 | Outbox archived + 状态机 | Task 4 | CheckConstraint + entity 方法调用 | `test_outbox_state_machine.py` |
| AC-5 | Outbox 清理 + RetryPolicy | Task 5 | cleanup + 退避策略 | `test_outbox_cleanup.py` |
| AC-6 | 隔离级别 + 审计 UoW | Task 6 | isolation_level + AuditUoW | `test_audit_unit_of_work.py` |
| AC-7 | Saga 基础设施 | Task 7, Task 8 | 模块 + 端口 + 注册 | `test_saga_orchestrator.py`, `test_saga_repository.py` |
| AC-8 | Saga 场景 S01-S03 | Task 9 | 混合式 + 编排式场景 | `test_saga_scenarios.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部 AC

- [ ] Subtask 0.1: 定义 SagaStatusChanged 领域事件（`src/domain/events/saga_events.py`）
- [ ] Subtask 0.2: 定义 SagaContext 数据模型（`src/infrastructure/saga/saga_context.py`）
- [ ] Subtask 0.3: 定义 SagaRepositoryProtocol 接口（`src/domain/ports/saga.py`）
- [ ] Subtask 0.4: 定义 UnitOfWorkFactory Protocol（`src/domain/ports/unit_of_work.py`）
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_story_20_7.feature`
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_story_20_7_steps.py`

**完成标准:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试可运行

---

### Task 1: PostgreSQLUnitOfWork 重构

**关联 AC:** AC-1, AC-3

#### TDD 循环 A：实例级标志位修复

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证多实例状态隔离 |
| 🟢 绿 | 添加 __init__ 方法，将 _committed/_rolled_back 改为实例属性 |
| 🔄 重构 | 优化代码结构 |

- [ ] Subtask 1.1: 🔴 红 — 编写多实例状态隔离测试
- [ ] Subtask 1.2: 🟢 绿 — 新增 __init__ 方法：`self._committed = False` + `self._rolled_back = False`（覆盖行 39-40 的类属性）
- [ ] Subtask 1.3: 🔄 重构 — 优化属性命名和初始化

#### TDD 循环 B：移除 close() 调用 + 添加标记位

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 重写现有测试：原 5 个测试验证 close() 被调用，须改为验证 close() **不被**调用 |
| 🟢 绿 | 移除行 136 和行 140 的 await self.close() 调用，添加 mark_uow_managed() |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 1.4: 🔴 红 — 重写 test_aexit_commits_on_no_exception（不验证 close）
- [ ] Subtask 1.5: 🔴 红 — 重写 test_aexit_rollback_on_exception（不验证 close）
- [ ] Subtask 1.6: 🔴 红 — 编写 __aexit__ 不调用 close 的新测试
- [ ] Subtask 1.7: 🟢 绿 — 移除行 136（rollback 失败时 close）和行 140（始终 close）的 close() 调用
- [ ] Subtask 1.8: 🟢 绿 — 添加 _uow_managed_ctx ContextVar 和 mark_uow_managed()/is_uow_managed() 辅助函数
- [ ] Subtask 1.9: 🟢 绿 — __aexit__ 调用 mark_uow_managed(True)
- [ ] Subtask 1.10: 🔄 重构 — 优化代码

**完成标准:**
- [ ] `pytest tests/unit/infrastructure/messaging/unit_of_work/test_postgresql_unit_of_work.py -v` 通过
- [ ] 多实例状态隔离测试通过
- [ ] __aexit__ 不调用 close 测试通过
- [ ] 原有 5 个测试全部重写为不验证 close

---

### Task 2: SessionMiddleware UoW 适配

**关联 AC:** AC-1

#### TDD 循环：Middleware UoW 感知

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证 Middleware 条件化 commit/rollback |
| 🟢 绿 | 实现 is_uow_managed() 检查逻辑 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 2.1: 🔴 红 — 编写 UoW 已管理时跳过 commit 测试
- [ ] Subtask 2.2: 🔴 红 — 编写 UoW 未使用时正常 commit 测试
- [ ] Subtask 2.3: 🟢 绿 — dispatch() 检查 is_uow_managed() 决定 commit/rollback
- [ ] Subtask 2.4: 🟢 绿 — finally 块始终 close + reset
- [ ] Subtask 2.5: 🔄 重构 — 优化代码

**完成标准:**
- [ ] `pytest tests/unit/infrastructure/middleware/test_session_middleware.py -v` 通过
- [ ] UoW 管理和未管理两种路径测试通过

---

### Task 3: UnitOfWork Protocol 重构 + UnitOfWorkFactory DI 注册

**关联 AC:** AC-2

#### TDD 循环 A：UnitOfWork Protocol 修改

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 更新契约测试验证 UnitOfWork 移除 close() |
| 🟢 绿 | 从 Protocol 移除 close() 方法 |
| 🔄 重构 | 更新文档注释 |

- [ ] Subtask 3.1: 🔴 红 — 更新 test_port_contract_unregistered.py：从 REQUIRED_METHODS 移除 "close"（当前含 8 方法含 close，改为 7 方法）
- [ ] Subtask 3.2: 🟢 绿 — 移除 close() 方法定义
- [ ] Subtask 3.3: 🟢 绿 — 新增 UnitOfWorkFactory(Protocol)

#### TDD 循环 B：DI 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写契约测试验证 uow_factory 端口 |
| 🟢 绿 | 注册 uow_factory 端口 |
| 🔄 重构 | 优化注册配置 |

- [ ] Subtask 3.4: 🔴 红 — 编写 test_port_contract_uow_factory.py
- [ ] Subtask 3.5: 🟢 绿 — composition_root.py 注册 uow_factory（TRANSIENT）
- [ ] Subtask 3.6: 🔄 重构 — 优化代码

**完成标准:**
- [ ] UnitOfWork Protocol 移除 close()
- [ ] UnitOfWorkFactory Protocol 定义完成
- [ ] uow_factory 端口注册完成
- [ ] 契约测试通过

---

### Task 4: Outbox 状态修复

**关联 AC:** AC-4

#### TDD 循环 A：CheckConstraint 修复

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证 archived 状态持久化 |
| 🟢 绿 | 修改 CheckConstraint 添加 'archived' |
| 🔄 重构 | 更新 ORM 模型 |

- [ ] Subtask 4.1: 🔴 红 — 编写 archived 状态持久化测试
- [ ] Subtask 4.2: 🟢 绿 — 修改 outbox.py ORM CheckConstraint（添加 'archived'）
- [ ] Subtask 4.3: 🟢 绿 — 创建新 Alembic 迁移脚本（不直接修改 001_initial.py）

#### TDD 循环 B：OutboxRepository 状态机修复

> **⚠️ 两个实现均须修复**：InMemoryOutboxRepository（行 56-75）和 PostgreSQLOutboxRepository（行 66-81）都直接赋值 `status` 字段绕过状态机。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证状态机方法调用 |
| 🟢 绿 | 重构两个实现为调用 entity/model 状态方法 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 4.4: 🔴 红 — 编写 InMemoryOutboxRepository 状态机调用测试
- [ ] Subtask 4.5: 🟢 绿 — InMemory: mark_published() 调用 entity.mark_published()
- [ ] Subtask 4.6: 🟢 绿 — InMemory: mark_failed() 调用 entity.mark_failed()
- [ ] Subtask 4.7: 🔴 红 — 编写 PostgreSQLOutboxRepository 状态转换校验测试
- [ ] Subtask 4.8: 🟢 绿 — PostgreSQL: mark_published() 添加前置状态校验（仅 pending 可转换）
- [ ] Subtask 4.9: 🟢 绿 — PostgreSQL: mark_failed() 添加前置状态校验
- [ ] Subtask 4.10: 🔄 重构 — 优化代码

**完成标准:**
- [ ] archived 状态持久化测试通过
- [ ] InMemoryOutboxRepository 状态机调用测试通过
- [ ] PostgreSQLOutboxRepository 状态转换校验测试通过
- [ ] `pytest tests/unit/infrastructure/messaging/outbox/test_outbox_state_machine.py -v` 通过

---

### Task 5: Outbox 增强

**关联 AC:** AC-5

#### TDD 循环 A：清理策略

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写清理策略测试 |
| 🟢 绿 | 实现 cleanup_old_published_records() |
| 🔄 重构 | 优化配置参数 |

- [ ] Subtask 5.1: 🔴 红 — 编写清理已发布记录测试
- [ ] Subtask 5.2: 🔴 红 — 编写清理不影响 pending 测试
- [ ] Subtask 5.3: 🟢 绿 — 实现清理方法
- [ ] Subtask 5.4: 🔄 重构 — 添加配置参数

#### TDD 循环 B：RetryPolicy 集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写指数退避重试测试 |
| 🟢 绿 | 集成现有 RetryPolicy |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 5.5: 🔴 红 — 编写 RetryPolicy 退避时间测试
- [ ] Subtask 5.6: 🟢 绿 — AsyncOutboxPoller 使用 RetryPolicy.get_delay()
- [ ] Subtask 5.7: 🔄 重构 — 优化代码

**完成标准:**
- [ ] 清理策略测试通过
- [ ] RetryPolicy 集成测试通过
- [ ] `pytest tests/unit/infrastructure/messaging/outbox/test_outbox_cleanup.py -v` 通过

---

### Task 6: 事务隔离级别 + 审计 UoW

**关联 AC:** AC-6

#### TDD 循环 A：隔离级别配置

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写隔离级别测试 |
| 🟢 绿 | 实现 get_session_with_isolation() |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 6.1: 🔴 红 — 编写 SERIALIZABLE 隔离级别测试
- [ ] Subtask 6.2: 🔴 红 — 编写 REPEATABLE READ 隔离级别测试
- [ ] Subtask 6.3: 🟢 绿 — PostgreSQLManager 支持 isolation_level 参数
- [ ] Subtask 6.4: 🔄 重构 — 优化代码

#### TDD 循环 B：审计专用 UoW

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写审计 UoW 测试 |
| 🟢 绿 | 实现 AuditUnitOfWork |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 6.5: 🔴 红 — 编写 AuditUnitOfWork 使用 SERIALIZABLE 测试
- [ ] Subtask 6.6: 🟢 绿 — 实现 AuditUnitOfWork 类
- [ ] Subtask 6.7: 🔄 重构 — 优化代码

**完成标准:**
- [ ] 隔离级别配置测试通过
- [ ] AuditUnitOfWork 测试通过
- [ ] `pytest tests/unit/infrastructure/messaging/unit_of_work/test_audit_unit_of_work.py -v` 通过

---

### Task 7: Saga 基础设施（模块 + Orchestrator + Context + 事件）

**关联 AC:** AC-7

#### TDD 循环 A：SagaContext

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SagaContext 状态管理测试 |
| 🟢 绿 | 实现 SagaContext 类 |
| 🔄 重构 | 优化序列化方法 |

- [ ] Subtask 7.1: 🔴 红 — 编写 SagaContext 状态管理测试
- [ ] Subtask 7.2: 🔴 红 — 编写 SagaContext to_dict/序列化测试
- [ ] Subtask 7.3: 🟢 绿 — 实现 SagaContext 类
- [ ] Subtask 7.4: 🔄 重构 — 优化代码

#### TDD 循环 B：SagaStep ABC

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SagaStep 抽象方法测试 |
| 🟢 绿 | 实现 SagaStep ABC |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 7.5: 🔴 红 — 编写 SagaStep execute/compensate 抽象方法测试
- [ ] Subtask 7.6: 🟢 绿 — 实现 SagaStep ABC
- [ ] Subtask 7.7: 🔄 重构 — 优化代码

#### TDD 循环 C：SagaOrchestrator

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SagaOrchestrator 正向执行测试 |
| 🔴 红 | 编写 SagaOrchestrator 补偿流程测试 |
| 🟢 绿 | 实现 SagaOrchestrator 类 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 7.8: 🔴 红 — 编写正向执行测试
- [ ] Subtask 7.9: 🔴 红 — 编写中间步骤失败补偿测试
- [ ] Subtask 7.10: 🟢 绿 — 实现 SagaOrchestrator 类
- [ ] Subtask 7.11: 🔄 重构 — 优化代码

#### TDD 循环 D：SagaStatus + 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SagaStatus 枚举测试 |
| 🔴 红 | 编写 SagaStatusChanged 事件测试 |
| 🟢 绿 | 实现 SagaStatus 枚举和事件类 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 7.12: 🔴 红 — 编写 SagaStatus 枚举测试
- [ ] Subtask 7.13: 🔴 红 — 编写 SagaStatusChanged 事件测试
- [ ] Subtask 7.14: 🟢 绿 — 实现 SagaStatus 枚举
- [ ] Subtask 7.15: 🟢 绿 — 实现 SagaStatusChanged 事件（datetime.now(UTC) 修正）
- [ ] Subtask 7.16: 🔄 重构 — 优化代码

**完成标准:**
- [ ] `pytest tests/unit/infrastructure/saga/ -v` 通过
- [ ] SagaOrchestrator 正向执行和补偿测试通过

---

### Task 8: Saga Repository + 领域端口 + DI 注册

**关联 AC:** AC-7

#### TDD 循环 A：SagaRepository

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SagaRepository 持久化测试 |
| 🟢 绿 | 实现 PostgreSQLSagaRepository |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 8.1: 🔴 红 — 编写 save/load/update_status 测试
- [ ] Subtask 8.2: 🟢 绿 — 实现 PostgreSQLSagaRepository
- [ ] Subtask 8.3: 🟢 绿 — 创建 saga_instance 表迁移脚本
- [ ] Subtask 8.4: 🔄 重构 — 优化代码

#### TDD 循环 B：领域端口 + DI 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 SagaStep Protocol 契约测试 |
| 🟢 绿 | 定义 SagaRepositoryProtocol |
| 🟢 绿 | 注册 saga_repository 端口 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 8.5: 🔴 红 — 编写 SagaStep Protocol 契约测试
- [ ] Subtask 8.6: 🟢 绿 — 定义 SagaRepositoryProtocol
- [ ] Subtask 8.7: 🟢 绿 — composition_root.py 注册 saga_repository
- [ ] Subtask 8.8: 🔄 重构 — 优化代码

**完成标准:**
- [ ] `pytest tests/integration/test_saga_repository.py -v` 通过
- [ ] 契约测试通过
- [ ] DI 注册完成

---

### Task 9: Saga 场景 S01-S03 + 集成测试

**关联 AC:** AC-8

#### TDD 循环 A：S01 文档处理 Saga

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 S01 场景测试 |
| 🟢 绿 | 实现 S01 Steps 和 Orchestrator |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 9.1: 🔴 红 — 编写 S01 正向流程测试
- [ ] Subtask 9.2: 🔴 红 — 编写 S01 补偿流程测试
- [ ] Subtask 9.3: 🟢 绿 — 实现 S01 Steps（UploadDocument/SaveMetadata/GenerateEmbedding/ExtractEntities）
- [ ] Subtask 9.4: 🔄 重构 — 优化代码

#### TDD 循环 B：S02 战略规划创建 Saga

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 S02 场景测试（SERIALIZABLE） |
| 🟢 绿 | 实现 S02 Steps |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 9.5: 🔴 红 — 编写 S02 正向流程测试
- [ ] Subtask 9.6: 🟢 绿 — 实现 S02 Steps（SavePlan/ArchiveEvidence，SERIALIZABLE）
- [ ] Subtask 9.7: 🔄 重构 — 优化代码

#### TDD 循环 C：S03 Checkpoint 保存 Saga

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 S03 场景测试（REPEATABLE READ） |
| 🟢 绿 | 实现 S03 Steps |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 9.8: 🔴 红 — 编写 S03 正向流程测试
- [ ] Subtask 9.9: 🟢 绿 — 实现 S03 Steps（SaveCheckpoint/ArchiveSnapshot，REPEATABLE READ）
- [ ] Subtask 9.10: 🔄 重构 — 优化代码

**完成标准:**
- [ ] `pytest tests/integration/test_saga_scenarios.py -v` 通过
- [ ] S01-S03 场景可运行
- [ ] 补偿流程测试通过

---

### Task 10: SDD 架构约束验证测试

**关联 AC:** 全部 AC

#### 架构验证测试更新

- [ ] Subtask 10.1: 更新 `test_uow_transaction_boundary.py` 验证 UoW 不调用 close
- [ ] Subtask 10.2: 新增六边形架构依赖方向测试（domain 不导入 infrastructure.saga）
- [ ] Subtask 10.3: 新增 SagaStep 接口隔离测试
- [ ] Subtask 10.4: 运行完整测试套件确认无回归

**完成标准:**
- [ ] 所有架构验证测试通过
- [ ] `poetry run pytest --tb=short` 全部通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Hexagonal Architecture）+ 事件驱动架构
- **设计约束:** 领域层零依赖、依赖倒置、仓储模式、UnitOfWork 模式
- **接口治理:** 统一端口注册 PortSpec、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+、SQLAlchemy 2.0 AsyncSession、Protocol（typing）

### 关键架构决策

**来源:** [`sisys-transaction-subsystem-refactor.md`](../../docs/architecture/sisys-transaction-subsystem-refactor.md)

| 决策 | 内容 | 理由 |
|------|------|------|
| D1 | Session 生命周期职责分离 | UoW 管理 begin/commit/rollback，Middleware 管理 create/close |
| D2 | UnitOfWorkFactory Protocol | PortSpec.interface 需要 Type，Callable 不合法 |
| D3 | Middleware 适配 UoW 模式 | 向后兼容，通过标记位检测 |
| D4 | Saga 基础设施实现 | 每步独立 UoW，失败逆序补偿 |
| D5 | 事务隔离级别配置 | 审计场景 SERIALIZABLE |
| D6 | ContextVar 隐式依赖权衡 | 保持现状，Repository 无参构造 |

### 项目结构说明

```
src/
├── domain/
│   ├── ports/
│   │   ├── unit_of_work.py      # 修改：移除 close()，新增 UnitOfWorkFactory
│   │   └── saga.py              # 新增：SagaStep/SagaRepositoryProtocol
│   └── events/
│       └── saga_events.py       # 新增：SagaStatusChanged
├── infrastructure/
│   ├── messaging/
│   │   ├── unit_of_work/
│   │   │   ├── postgresql_unit_of_work.py  # 修改：实例属性、不调用 close
│   │   │   └── audit_unit_of_work.py       # 新增
│   │   └── outbox/
│   │       ├── outbox_repository.py        # 保持
│   │       └── inmemory_outbox.py          # 修改：调用状态机方法
│   ├── saga/                               # 新增目录
│   │   ├── __init__.py
│   │   ├── saga_step.py
│   │   ├── saga_context.py
│   │   ├── saga_status.py
│   │   ├── saga_orchestrator.py
│   │   └── saga_repository.py
│   └── storage/postgresql/
│       ├── session_context.py              # 修改：新增 UoW 标记位
│       └── postgresql_manager.py           # 修改：支持隔离级别
├── middleware/
│   └── session_middleware.py               # 修改：UoW 感知
└── composition_root.py                     # 修改：注册 uow_factory、saga_repository
```

### 前一个故事学习经验

**来源:** [Story 20-6 端口契约测试补全](./20-6-port-contracts-refactor.md)

**关键学习:**
1. resolver.resolve() 实施风险：对需要外部服务的端口，resolve() 会尝试实例化。契约测试应优先使用 `spec.impl` 类级别检查
2. 7 个 application/ports Protocol 缺少 @runtime_checkable：使用 hasattr/callable 而非 isinstance
3. L2RdbPort[T] 是泛型基类：继承端口的测试须验证基类方法
4. 所有 Port 使用 Protocol（非 ABC）：domain/ports 全部 @runtime_checkable

**应用到本故事:**
- [ ] SagaStep Protocol 契约测试使用 hasattr/callable
- [ ] UnitOfWorkFactory 契约测试验证 __call__ 方法
- [ ] 测试先调用 bootstrap() 注册

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | claude-opus-4-7 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-19 |

### 调试日志引用

| 配置项 | 路径 |
|--------|------|
| **设计文档** | `docs/architecture/sisys-transaction-subsystem-refactor.md` (v1.0.5) |
| **Story 模板** | `docs/developer/story-template.md` (v2.7.0) |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/20-6-port-contracts-refactor.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单

- [x] 设计文档 v1.0.5 完整读取（5 轮审查完成）
- [x] 代码调研完成（发现类级别标志位 bug）
- [x] Story 需求从设计文档提取
- [x] 架构约束从模板和前序 Story 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成

### 文件清单

**待修改的文件:**
- `src/domain/ports/unit_of_work.py` — 移除 close()，新增 UnitOfWorkFactory
- `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` — 实例属性、不调用 close
- `src/infrastructure/storage/postgresql/session_context.py` — 新增 UoW 标记位
- `src/infrastructure/middleware/session_middleware.py` — UoW 感知
- `src/infrastructure/messaging/outbox/inmemory_outbox.py` — 调用状态机方法
- `src/infrastructure/storage/postgresql/postgresql_manager.py` — 隔离级别
- `src/composition_root.py` — 注册 uow_factory、saga_repository
- `deploy/postgresql/alembic/versions/001_initial.py` — 不直接修改，通过新迁移脚本修复
- `src/infrastructure/storage/postgresql/models/outbox.py` — 修改 CheckConstraint 添加 'archived'
- `tests/contracts/test_port_contract_unregistered.py` — 更新 UnitOfWork 方法数

**待新增的文件:**
- `src/domain/ports/saga.py` — SagaStep/SagaRepositoryProtocol
- `src/domain/events/saga_events.py` — SagaStatusChanged
- `src/infrastructure/saga/__init__.py`
- `src/infrastructure/saga/saga_step.py`
- `src/infrastructure/saga/saga_context.py`
- `src/infrastructure/saga/saga_status.py`
- `src/infrastructure/saga/saga_orchestrator.py`
- `src/infrastructure/saga/saga_repository.py`
- `src/infrastructure/messaging/unit_of_work/audit_unit_of_work.py`
- `deploy/postgresql/alembic/versions/xxx_add_saga_instance.py`
- `tests/acceptance/test_story_20_7.feature`
- `tests/acceptance/test_story_20_7_steps.py`
- `tests/contracts/test_port_contract_uow_factory.py`
- `tests/unit/infrastructure/messaging/outbox/test_outbox_state_machine.py`
- `tests/unit/infrastructure/messaging/outbox/test_outbox_cleanup.py`
- `tests/unit/infrastructure/messaging/unit_of_work/test_audit_unit_of_work.py`
- `tests/unit/infrastructure/saga/test_saga_orchestrator.py`
- `tests/unit/infrastructure/saga/test_saga_context.py`
- `tests/integration/test_saga_repository.py`
- `tests/integration/test_saga_scenarios.py`

---

## 📊 故事详情

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 20.7 |
| **Story Key** | 20-7-transaction-subsystem-refactor |
| **File** | `_bmad-output/implementation-artifacts/stories/20-7-transaction-subsystem-refactor.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 20: 重大重构 |
| **优先级** | P0 |
| **覆盖范围** | 4 Phase / 10 Task / 8 AC |

### 完成总结

1. [x] All tasks defined 所有任务定义完成（10 Tasks + Task 0）
2. [x] All acceptance criteria specified 8 项验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] 代码调研额外发现已整合（类级别标志位 bug）
6. [x] 设计文档 v1.0.5 完整覆盖

### 下一步

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
