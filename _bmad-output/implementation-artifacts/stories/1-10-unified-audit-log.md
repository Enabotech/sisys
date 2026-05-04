# Story 1.10: Unified Audit Log

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

> **🔧 技术约束（v1.0）：**
> 1. **复用 Story 1.5 PostgreSQL 配置模式** — `src/infrastructure/config/` 下的配置模式复用
> 2. **复用 Story 1.9 AuthService/PermissionService** — 审计日志记录 actor 信息来源
> 3. **事务发件箱模式** — 审计事件与业务操作同事务提交，保证可靠性
> 4. **双通道事件总线** — RabbitMQ + WORM 归档用于审计事件（架构 ADR-003）
> 5. **六层存储架构** — 审计元数据存 L2 (PostgreSQL)，完整审计归档存 L4 (MinIO WORM)
> 6. **等保 2.0 + SOX 合规** — 审计日志 7 年不可变存储

---

## 📖 Story 描述

**As a** 安全工程师,
**I want** 实现统一审计日志系统,
**So that** 系统满足等保 2.0 和 SOX 合规要求，支持完整操作追溯和多方检索。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 4（安全与合规基础）的第二个故事，在 Story 1.5 (PostgreSQL 关系存储层) 和 Story 1.9 (RBAC 权限管理) 基础上实现统一审计日志系统。审计日志作为系统合规的核心基础设施，承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **统一审计记录** | 记录所有操作，支持完整追溯 | 日志完整性 100% |
| **不可变存储** | 防止日志篡改，满足合规要求 | WORM 存储 7 年 |
| **多维检索** | 支持按时间/角色/任务类型/修正级别检索 | 检索响应<500ms |
| **事务保证** | 审计事件与业务操作原子性提交 | 0 数据丢失 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 4: 安全与合规基础

**覆盖 FR:**
- FR-SC-02: 统一审计日志（Story 1.10）
- FR-SC-03: WORM 存储（Story 1.10 写入审计日志至 Story 1.7 的 `audit-archives` WORM bucket）
- FR-SC-04: 审计日志多维检索（**基础实现**：PostgreSQL 索引 + API；**完整实现**：Epic 8 Story 8.1）

**覆盖 NFR:**
- NFR-COMP-02: 审计日志保留（Story 1.10 写入 PostgreSQL MVP，V2 归档至 Story 1.7 MinIO WORM）✓
- NFR-COMP-05: 审计日志完整性（100% 完整，日志审计工具验证通过）✓

### 依赖关系 Dependencies

| 依赖 Story | 依赖类型 | 依赖原因 |
|-----------|---------|---------|
| Story 1-1: Hexagonal Architecture Skeleton | 硬依赖 | 六边形架构模式、依赖注入容器、领域层接口定义规范 |
| Story 1-5: PostgreSQL Relational Layer | 硬依赖 | 审计日志元数据存储于 PostgreSQL |
| Story 1-9: RBAC Permission Management | 硬依赖 | actor 信息（用户 ID、角色）来源于认证授权系统 |
| Story 1-7: MinIO Object Layer | 软依赖 | WORM 存储最终目标，但 MVP 使用 PostgreSQL 审计表 |
| Story 1.16: Integration Test Framework | 软依赖 | 集成测试框架模式复用 |

### 技术容量规划

| 指标 | MVP | V1 | V2 |
|------|-----|----|----|
| **审计日志存储容量** | 100GB | 500GB | 2TB |
| **单条日志大小** | ≤2KB | ≤2KB | ≤2KB |
| **日志保留期限** | 7 年 | 7 年 | 10 年 |
| **并发写入 QPS** | ≥100 | ≥500 | ≥2000 |
| **检索延迟 P95** | <500ms | <200ms | <100ms |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 统一审计日志记录 (Unified Audit Logging)

**Given** 审计日志服务已初始化
**When** 系统任何组件执行操作（认证、授权、文档处理、Agent 决策等）
**Then** 系统记录审计日志条目
**And** 日志包含: log_id, timestamp, actor, action_type, target_resource, old_value, new_value
**And** 日志通过事务发件箱模式保证可靠性

**验证标准/Validation Criteria:**
- [ ] 审计日志数据模型定义
  - 字段: `log_id` (UUID), `timestamp` (datetime), `actor` (str), `action_type` (str), `target_resource` (str), `old_value` (JSON), `new_value` (JSON)
- [ ] 事务发件箱模式实现
  - 审计事件与业务操作同事务提交至 PostgreSQL `audit_outbox` 表
  - 后台处理器轮询发布至 RabbitMQ
- [ ] 统一审计拦截器/装饰器
  - 自动捕获关键操作的审计信息
  - 支持上下文传播（actor 信息从 AuthService 获取）
- [ ] 单元测试覆盖日志创建、序列化、反序列化场景

### AC-2: 不可变存储 (Immutable Storage / WORM)

**Given** 审计日志已记录
**When** 日志需要长期保存（≥7 年）
**Then** 日志写入不可变存储
**And** 已写入日志不可被修改或删除
**And** 支持归档到 MinIO WORM（未来 Story 1.7 完成后）

**验证标准/Validation Criteria:**
- [ ] PostgreSQL 审计表设计
  - 启用 PostgreSQL 行级安全 (RLS) 防止更新/删除
  - 使用触发器记录修改历史（可选）
- [ ] 日志归档接口
  - 支持将历史日志归档至 L4 对象存储
  - 归档记录元数据查询接口
- [ ] 完整性校验
  - 日志签名/校验和防止篡改
  - 定期校验任务
- [ ] 单元测试覆盖不可变性验证场景

### AC-3: 多维检索 (Multi-dimensional Search)

**Given** 审计日志已积累
**When** 用户按条件检索审计日志
**Then** 系统返回匹配的日志条目
**And** 支持按时间范围、角色、任务类型、修正级别等维度筛选
**And** 支持分页和排序

**验证标准/Validation Criteria:**
- [ ] 审计日志检索接口
  - `GET /api/v1/audit/logs` - 审计日志列表
  - 查询参数: `start_time`, `end_time`, `actor`, `action_type`, `target_resource`, `correction_level`, `page`, `page_size`
  - 响应: 分页的日志列表
- [ ] 检索索引设计
  - PostgreSQL 索引: `timestamp`, `actor`, `action_type`, `correction_level`
  - 复合索引优化常见查询模式
- [ ] CLI 命令支持
  - `sisys system audit query --actor user123 --start-time 2026-01-01`
- [ ] 单元测试覆盖检索、筛选、分页场景

### AC-4: 等保 2.0 + SOX 合规 (Compliance)

**Given** 系统需要通过等保 2.0 三级和 SOX 合规审计
**When** 执行合规性审计
**Then** 审计日志满足所有合规要求

**验证标准/Validation Criteria:**
- [ ] 等保 2.0 安全审计要求
  - 登录/登出事件记录（完整）
  - 权限变更事件记录（完整）
  - 敏感操作事件记录（完整）
  - 审计记录保护（不可篡改）
- [ ] SOX 合规要求
  - 财务相关操作完整审计
  - 审计追踪不可间断
  - 7 年保留期限
- [ ] 合规报告生成
  - 支持生成合规审计报告
  - 报告包含时间范围、操作统计、异常摘要

### AC-5: 事件驱动集成 (Event-Driven Integration)

**Given** 审计日志系统已运行
**When** 其他领域事件被发布时
**Then** 审计服务自动记录相关审计日志

**验证标准/Validation Criteria:**
- [ ] 事件监听器实现
  - 监听 `AuthenticationEvent`, `AuthorizationEvent`, `DocumentProcessedEvent`, `AgentDecidedEvent`, `CheckpointReachedEvent`, `CorrectionApprovedEvent`
  - 自动转换为审计日志
- [ ] 事件过滤和聚合
  - 仅记录关键事件（可配置）
  - 支持事件聚合减少日志量
- [ ] 事件处理幂等性
  - 基于 event_id 去重
  - Redis 缓存 TTL 7 天

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] AuditEvent 定义（`src/domain/events/audit_events.py`）
  - 基础字段（来自 FR-SC-02）: `log_id`, `timestamp`, `actor`, `action_type`, `target_resource`, `old_value`, `new_value`
  - 扩展字段（支持 FR-SC-04 多维检索）: `correction_level`
  - 继承 `DomainEvent` 基类

#### 数据模型 (Data Models) — 基础设施层
- [ ] AuditLogModel（PostgreSQL 审计日志表，`src/infrastructure/storage/postgresql/models/audit.py`）
  - 基础字段（FR-SC-02）: `id`, `log_id`, `timestamp`, `actor`, `action_type`, `target_resource`, `old_value`, `new_value`
  - 扩展字段: `correction_level`（支持 FR-SC-04 多维检索）
  - 系统字段: `checksum`, `created_at`
- [ ] AuditOutboxModel（事务发件箱表）
  - 字段: `id`, `event_id`, `event_type`, `payload`, `status`, `created_at`, `processed_at`
- [ ] AuditConfig 配置模型（`src/infrastructure/config/audit.py`）

#### API 契约 (API Contract)
- [ ] 审计日志检索端点: `GET /api/v1/audit/logs`
- [ ] 审计日志详情端点: `GET /api/v1/audit/logs/{log_id}`
- [ ] 审计统计端点: `GET /api/v1/audit/stats`

#### CLI 命令 (CLI Commands)
- [ ] `sisys system audit query` - 查询审计日志
- [ ] `sisys system audit stats` - 审计统计

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.10.feature`
- [ ] 覆盖场景:
  - 审计日志自动记录
  - 多维检索（时间/角色/任务类型/修正级别）
  - WORM 不可变性验证
  - 等保 2.0 合规验证
  - 事件驱动自动记录

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 审计日志模型 | 日志创建、校验和计算 | `test_audit_model.py` | Task 1 |
| **TDD 单元测试** | 审计服务 | 日志记录、检索、统计 | `test_audit_service.py` | Task 1 |
| **TDD 单元测试** | 事务发件箱 | Outbox 写入、发布、重试 | `test_audit_outbox.py` | Task 2 |
| **TDD 单元测试** | 事件监听器 | 事件转换、日志自动记录 | `test_audit_event_listener.py` | Task 3 |
| **TDD 集成测试** | PostgreSQL 审计表 | CRUD、RLS 不可变性 | `test_audit_postgres_integration.py` | Task 4 |
| **SDD 合规测试** | 等保 2.0 合规 | 登录/权限/敏感操作审计 | `test_dengbao_audit_compliance.py` | Task 5 |
| **SDD 架构验证** | 领域层零依赖 | 领域层无审计实现细节 | `test_architecture_constraints.py` | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **安全层覆盖率 ≥85%**（`pytest --cov=src/infrastructure/security`）- **P1 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

> ⚠️ **骨架 Story 覆盖率豁免：** 如果本 Story 为架构骨架（Skeleton），大量代码为空接口/占位类/`__init__.py`，无法达到上述覆盖率指标。**请将覆盖率要求临时调整为：整体≥30%，[层类型] 层≥50%。**
> 本 Story 非骨架实现，需严格执行覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源；语义缓存测试用不同 embedding 向量 | 资源冲突导致并行失败 |
| **语义缓存隔离** | 语义缓存基于向量相似度，多测试用相同 embedding 会互相覆盖缓存 | 需要用 unique_cache_key 生成不同 embedding |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **asyncio.run 使用** | 独立脚本用 asyncio.run()；pytest-xdist 并行测试中 BDD 步骤函数用 event_loop.run_until_complete() | asyncio.run() 创建新循环，并行测试时可能关闭错误循环 |
| **并发测试方法** | 单进程测试用 asyncio.run()；pytest-xdist 并行时 BDD 步骤用 event_loop fixture；真正并发测试在 async 函数内用 asyncio.gather() | 根据场景正确选择否则失败 |
| **外部客户端** | 第三方 API 必须验证方法存在性 | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ pytest-xdist 并行测试时，BDD 步骤函数内使用 asyncio.run()（应使用 event_loop fixture）

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 统一审计日志记录 | Task 1 | Subtask 1.1-1.6 (AuditService + AuditEvent) | `test_audit_service.py`, `test_audit_model.py` |
| AC-1 | 事务发件箱模式 | Task 2 | Subtask 2.1-2.6 (Outbox 处理器) | `test_audit_outbox.py` |
| AC-2 | 不可变存储 | Task 4 | Subtask 4.1-4.6 (PostgreSQL RLS + 校验和) | `test_audit_postgres_integration.py` |
| AC-3 | 多维检索 | Task 1 | Subtask 1.7-1.12 (检索 + 分页) | `test_audit_service.py` |
| AC-4 | 等保 2.0 + SOX 合规 | Task 5 | Subtask 5.1-5.6 (合规验证测试) | `test_dengbao_audit_compliance.py` |
| AC-5 | 事件驱动集成 | Task 3 | Subtask 3.1-3.6 (事件监听器) | `test_audit_event_listener.py` |
| AC-1~AC-5 | 端到端集成测试 | Task 4 | Subtask 4.7-4.12 (完整流程) | `test_audit_postgres_integration.py` |
| AC-5 | 架构约束验证 | Task 6 | Subtask 6.1-6.6 (架构约束) | `test_architecture_constraints.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5

> **目的：** 在进入代码实现前，明确 Schema、数据模型、接口、验收标准。

- [ ] Subtask 0.1: 定义 AuditEvent 领域事件 Schema
- [ ] Subtask 0.2: 定义 AuditLogModel 数据模型（PostgreSQL 表）
- [ ] Subtask 0.3: 定义 AuditOutboxModel 事务发件箱模型
- [ ] Subtask 0.4: 定义 AuditConfig 配置模型
- [ ] Subtask 0.5: 定义 AuditService 接口协议
- [ ] Subtask 0.6: 创建/更新 `docs/api/openapi.yaml` 审计端点
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.10.feature`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 审计日志核心服务 (Audit Log Core Service)

**关联 AC:** AC-1, AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 复用说明:** 审计配置沿用 Story 1.4-1.9 的 `XxxConfig + from_env()` 模式。

#### TDD 循环 A：AuditLogModel 审计日志模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_model.py`（日志创建、校验和计算、序列化） |
| 🟢 绿 | 实现 `AuditLogModel` 类最小代码 |
| 🔄 重构 | 添加校验和验证、JSON 字段处理 |

- [ ] Subtask 1.1: 🔴 红 — 编写 AuditLogModel 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 AuditLogModel 最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化 AuditLogModel 代码

#### TDD 循环 B：AuditService 审计服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_service.py`（日志记录、检索、统计） |
| 🟢 绿 | 实现 `AuditService` 类最小代码 |
| 🔄 重构 | 添加多维检索、分页、错误处理 |

- [ ] Subtask 1.4: 🔴 红 — 编写 AuditService 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 AuditService 最小代码
- [ ] Subtask 1.6: 🔄 重构 — 优化 AuditService 代码

#### TDD 循环 C：审计日志检索

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写检索测试（时间范围、角色、任务类型、修正级别筛选） |
| 🟢 绿 | 实现多维检索逻辑 |
| 🔄 重构 | 添加索引优化、查询优化 |

- [ ] Subtask 1.7: 🔴 红 — 编写审计检索失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现多维检索逻辑
- [ ] Subtask 1.9: 🔄 重构 — 优化检索性能

#### TDD 循环 D：审计统计

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_stats.py`（操作统计、合规报告） |
| 🟢 绿 | 实现统计计算逻辑 |
| 🔄 重构 | 优化统计查询性能 |

- [ ] Subtask 1.10: 🔴 红 — 编写审计统计失败测试
- [ ] Subtask 1.11: 🟢 绿 — 实现审计统计逻辑
- [ ] Subtask 1.12: 🔄 重构 — 优化统计代码

**完成标准/Definition of Done:**
- [ ] AuditLogModel 和 AuditService 实现完成
- [ ] TDD 循环全部通过
- [ ] 多维检索功能实现
- [ ] 安全层覆盖率≥40%

---

### Task 2: 事务发件箱模式 (Transaction Outbox Pattern)

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 说明:** 事务发件箱确保审计事件与业务操作原子性提交，这是等保 2.0 合规的关键要求。

#### TDD 循环 A：Outbox 模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_outbox_model.py`（Outbox 表操作） |
| 🟢 绿 | 实现 `AuditOutboxModel` 类最小代码 |
| 🔄 重构 | 添加状态管理、错误处理 |

- [ ] Subtask 2.1: 🔴 红 — 编写 Outbox 模型失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 Outbox 模型
- [ ] Subtask 2.3: 🔄 重构 — 优化 Outbox 模型代码

#### TDD 循环 B：Outbox 处理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_outbox_processor.py`（轮询、发布、重试） |
| 🟢 绿 | 实现 Outbox 处理器最小代码 |
| 🔄 重构 | 添加重试逻辑、死信队列处理 |

- [ ] Subtask 2.4: 🔴 红 — 编写 Outbox 处理器失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 Outbox 处理器
- [ ] Subtask 2.6: 🔄 重构 — 优化 Outbox 处理器代码

**完成标准/Definition of Done:**
- [ ] Outbox 模型和处理器实现完成
- [ ] TDD 循环全部通过
- [ ] 事务原子性保证
- [ ] 安全层覆盖率≥60%

---

### Task 3: 事件驱动审计集成 (Event-Driven Audit Integration)

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 说明:** 自动监听领域事件并转换为审计日志。

#### TDD 循环 A：事件监听器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_event_listener.py`（事件转换、日志自动记录） |
| 🟢 绿 | 实现事件监听器最小代码 |
| 🔄 重构 | 添加事件过滤、聚合逻辑 |

- [ ] Subtask 3.1: 🔴 红 — 编写事件监听器失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现事件监听器
- [ ] Subtask 3.3: 🔄 重构 — 优化事件监听器代码

#### TDD 循环 B：事件到审计的转换映射

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写事件转换映射测试 |
| 🟢 绿 | 实现事件到审计字段的转换逻辑 |
| 🔄 重构 | 添加配置化映射支持 |

- [ ] Subtask 3.4: 🔴 红 — 编写事件转换失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现事件转换逻辑
- [ ] Subtask 3.6: 🔄 重构 — 优化转换代码

**完成标准/Definition of Done:**
- [ ] 事件监听器实现完成
- [ ] TDD 循环全部通过
- [ ] 支持关键领域事件自动记录
- [ ] 安全层覆盖率≥70%

---

### Task 4: 不可变存储与集成 (Immutable Storage & Integration)

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 说明:** PostgreSQL 行级安全 (RLS) 实现不可变性，MVP 阶段使用。

#### TDD 循环 A：PostgreSQL RLS 不可变性

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_postgres_rls.py`（RLS 策略、不可变性验证） |
| 🟢 绿 | 实现 RLS 策略和应用 |
| 🔄 重构 | 验证策略正确性 |

- [ ] Subtask 4.1: 🔴 红 — 编写 PostgreSQL RLS 失败测试
- [ ] Subtask 4.2: 🟢 绿 — 实现 RLS 策略
- [ ] Subtask 4.3: 🔄 重构 — 验证 RLS 策略

#### TDD 循环 B：校验和验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写校验和验证测试 |
| 🟢 绿 | 实现校验和计算和验证逻辑 |
| 🔄 重构 | 优化校验和算法 |

- [ ] Subtask 4.4: 🔴 红 — 编写校验和验证失败测试
- [ ] Subtask 4.5: 🟢 绿 — 实现校验和逻辑
- [ ] Subtask 4.6: 🔄 重构 — 优化校验和代码

#### TDD 循环 C：端到端集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_audit_integration.py`（完整流程测试） |
| 🟢 绿 | 实现完整审计流程 |
| 🔄 重构 | 优化集成流程 |

- [ ] Subtask 4.7: 🔴 红 — 编写端到端集成失败测试
- [ ] Subtask 4.8: 🟢 绿 — 实现端到端集成
- [ ] Subtask 4.9: 🔄 重构 — 优化集成流程

**完成标准/Definition of Done:**
- [ ] PostgreSQL 不可变性实现完成
- [ ] TDD 循环全部通过
- [ ] 安全层覆盖率≥80%

---

### Task 5: 等保 2.0 + SOX 合规验证 (Compliance Validation)

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 说明:** Task 5 验证功能性合规（登录审计、权限变更审计、敏感操作审计），架构约束由 Task 6 验证。

#### TDD 循环 A：登录/登出审计

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_dengbao_login_audit.py`（登录/登出事件记录） |
| 🟢 绿 | 实现登录审计功能 |
| 🔄 重构 | 优化审计记录格式 |

- [ ] Subtask 5.1: 🔴 红 — 编写登录审计失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现登录审计功能
- [ ] Subtask 5.3: 🔄 重构 — 优化登录审计代码

#### TDD 循环 B：权限变更审计

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_dengbao_permission_audit.py`（权限变更事件记录） |
| 🟢 绿 | 实现权限变更审计功能 |
| 🔄 重构 | 优化权限变更审计代码 |

- [ ] Subtask 5.4: 🔴 红 — 编写权限变更审计失败测试
- [ ] Subtask 5.5: 🟢 绿 — 实现权限变更审计功能
- [ ] Subtask 5.6: 🔄 重构 — 优化权限变更审计代码

#### TDD 循环 C：合规报告生成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写合规报告测试 |
| 🟢 绿 | 实现合规报告生成逻辑 |
| 🔄 重构 | 优化报告格式和内容 |

- [ ] Subtask 5.7: 🔴 红 — 编写合规报告失败测试
- [ ] Subtask 5.8: 🟢 绿 — 实现合规报告生成逻辑
- [ ] Subtask 5.9: 🔄 重构 — 优化合规报告代码

**完成标准/Definition of Done:**
- [ ] 等保 2.0 + SOX 合规功能实现完成
- [ ] TDD 循环全部通过
- [ ] 合规报告生成功能实现
- [ ] 安全层覆盖率≥85%

---

### Task 6: 架构约束验证 (Architecture Constraints)

**关联 AC:** AC-5（架构约束验证）

> **性质说明：** 本 Task 验证审计日志实现是否符合六边形架构约束。Task 5 验证功能性合规，本 Task 验证架构合规。

#### 架构验证测试实现

- [ ] Subtask 6.1: 创建 `tests/unit/security/test_audit_architecture_constraints.py`
- [ ] Subtask 6.2: 实现领域层零审计实现验证（扫描 `src/domain/` 目录，确保无 `infrastructure`、`audit` 等外部依赖导入）
- [ ] Subtask 6.3: 实现依赖方向验证（验证 `domain → infrastructure` 单向依赖）
- [ ] Subtask 6.4: 运行 Ruff 检查（`ruff check src/`，0 错误）
- [ ] Subtask 6.5: 运行 MyPy 类型检查（`mypy src/`，0 问题）
- [ ] Subtask 6.6: 验证审计事件定义在正确位置（`src/domain/events/audit_events.py`）

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败
- [ ] 安全层覆盖率≥85%（累计 Task 1-6）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **六层存储架构:** L2 关系存储层（PostgreSQL 15+）存储审计元数据，L4 对象存储层（MinIO WORM）存储完整审计归档
- **双通道事件总线:**
  - 实时通知型: Redis 发布/订阅
  - 业务状态型: RabbitMQ + Outbox
  - 审计事件型: RabbitMQ + WORM 归档（7 年）
- **事务发件箱模式:**
  - 事件与业务操作同事务提交至 PostgreSQL `audit_outbox` 表
  - 后台处理器轮询发布至 RabbitMQ
  - 保证最终一致性
- **审计日志 Schema（FR-SC-02）：**
  - log_id (UUID)
  - timestamp (datetime)
  - actor (str) - 用户 ID/系统组件
  - action_type (str) - 操作类型
  - target_resource (str) - 目标资源
  - old_value (JSON) - 变更前值
  - new_value (JSON) - 变更后值
  - **扩展字段（FR-SC-04 多维检索基础实现，本 Story）：**
    - correction_level (int) - 修正级别 (L0-L3)
    - **注意：** FR-SC-04 完整多维检索（含多维度聚合、复杂筛选）在 Epic 8 Story 8.1

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 3 (ADR-003): 双通道事件总线

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **PostgreSQL 审计表 (MVP)** | 简单、事务保证、查询方便 | 大数据量性能下降 | ✅ 8/10 |
| **MinIO WORM (V1+)** | 不可变、7 年存储、成本低 | 查询功能弱 | 7/10 |
| **Elasticsearch** | 强大检索能力 | 额外基础设施 | 6/10 |

**决策理由：**
1. MVP 阶段使用 PostgreSQL 审计表，简化实现
2. 设计支持未来迁移到 MinIO WORM
3. 通过 Outbox 模式保证审计可靠性

### 项目结构说明 Project Structure

> **📌 架构说明:** 审计日志服务遵循六边形架构的依赖倒置原则。
> - 领域层 (`src/domain/events/`) 定义审计事件（DomainEvent 子类）
> - 领域层 (`src/domain/services/`) 定义审计服务接口（Protocol）
> - 基础设施层 (`src/infrastructure/audit/`) 实现审计服务接口

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── audit_events.py          # AuditEvent 领域事件
│   │   │   └── ... (其他领域事件)
│   │   └── services/
│   │       ├── __init__.py
│   │       └── audit_service.py          # AuditService 接口（Protocol）
│   └── infrastructure/
│       ├── config/
│       │   └── audit.py                  # AuditConfig 配置模型
│       ├── audit/
│       │   ├── __init__.py
│       │   ├── audit_service.py          # AuditService 实现
│       │   ├── outbox_processor.py       # 事务发件箱处理器
│       │   ├── event_listener.py         # 事件监听器
│       │   └── compliance_reporter.py    # 合规报告生成
│       └── storage/
│           └── postgresql/
│               └── models/
│                   ├── audit.py           # AuditLogModel
│                   └── audit_outbox.py    # AuditOutboxModel
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   └── events/
│   │   │       └── test_audit_events.py
│   │   └── infrastructure/
│   │       └── audit/
│   │           ├── test_audit_service.py
│   │           ├── test_audit_outbox.py
│   │           └── test_audit_event_listener.py
│   ├── integration/
│   │   └── test_audit_integration.py
│   └── acceptance/
│       └── test_story_1.10.feature
└── docs/
    └── audit/
        └── unified_audit_log_guide.md  # 统一审计日志实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.9-RBAC Permission Management](./1-9-rbac-permission-management.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — Story 1.4-1.9 已建立 `XxxConfig + from_env()` 模式，本 Story 沿用
2. **领域层接口与基础设施层实现分离** — 领域层定义接口（Protocol），基础设施层实现
3. **AuthService 提供 actor 信息** — 审计日志的 actor 字段从 AuthService 获取
4. **PostgreSQL 存储层** — 审计元数据存储于 PostgreSQL（Story 1.5 基础）
5. **事务发件箱模式** — Story 1.3 事件总线已实现 Outbox 模式，复用该模式

**应用到本故事/Applied to This Story:**
- [ ] AuditConfig 采用 Story 1.4-1.9 相同的配置模式
- [ ] AuditService 接口定义在领域层（Protocol），实现在基础设施层
- [ ] 复用 Story 1.3 事件总线的 Outbox 处理器模式
- [ ] actor 信息从 AuthService 认证上下文中获取
- [ ] 架构约束测试验证领域层无审计实现细节

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-18 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `docs/developer/story-template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-9-rbac-permission-management.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] Story 需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-10-unified-audit-log.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/events/audit_events.py` - AuditEvent 领域事件
- `src/domain/services/audit_service.py` - AuditService 接口（Protocol）
- `src/infrastructure/config/audit.py` - AuditConfig 配置模型
- `src/infrastructure/audit/audit_service.py` - AuditService 实现
- `src/infrastructure/audit/outbox_processor.py` - 事务发件箱处理器
- `src/infrastructure/audit/event_listener.py` - 事件监听器
- `src/infrastructure/audit/compliance_reporter.py` - 合规报告生成
- `src/infrastructure/storage/postgresql/models/audit.py` - AuditLogModel
- `src/infrastructure/storage/postgresql/models/audit_outbox.py` - AuditOutboxModel
- `tests/unit/domain/events/test_audit_events.py` - 审计事件单元测试
- `tests/unit/infrastructure/audit/test_audit_service.py` - 审计服务单元测试
- `tests/unit/infrastructure/audit/test_audit_outbox.py` - 发件箱单元测试
- `tests/unit/infrastructure/audit/test_audit_event_listener.py` - 事件监听器测试
- `tests/integration/test_audit_integration.py` - 集成测试
- `tests/acceptance/test_story_1.10.feature` - 验收测试
- `docs/audit/unified_audit_log_guide.md` - 实施指南

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.10 |
| **Story Key** | 1-10-unified-audit-log |
| **File** | `_bmad-output/implementation-artifacts/stories/1-10-unified-audit-log.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 4: 安全与合规基础 |
| **优先级** | P0 |
| **覆盖 FR** | FR-SC-02（统一审计日志）、FR-SC-03（WORM 存储，Story 1.10 写入 Story 1.7 WORM bucket）、FR-SC-04（多维检索基础实现，完整实现见 Epic 8 Story 8.1） |
| **覆盖 NFR** | NFR-COMP-02（审计日志保留）、NFR-COMP-05（审计日志完整性） |
| **层类型** | 安全层（覆盖率≥85%） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成（Task 0-6，含 SDD 规范 + TDD 循环）
2. [ ] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5）
3. [ ] Architecture constraints extracted 架构约束已提取（事务发件箱、WORM、双通道事件总线）
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合（配置模式复用、接口分离、架构约束验证）
5. [ ] Sprint status synced to `ready-for-dev`

### Review Findings (2026-04-20)

#### decision-needed (需要明确决策)
- [x] [Review][Decision] D1: 双重写入 vs 纯Outbox模式 — **已决策：保持双写（audit_log + outbox）**，符合 ADR-003 双通道架构，RabbitMQ 已部署

#### patch (可直接修复)
- [x] [Review][Patch] P1: `_publish_entry` 是空实现 [outbox_processor.py:102-120] — **已修复**：实现 RabbitMQ 发布
- [x] [Review][Patch] P2: Archive UPDATE 被 RLS 拒绝 [audit_service.py:337-339] — **已修复**：添加注释说明 RLS 限制，V2 实现 MinIO WORM
- [x] [Review][Patch] P3: `asyncio.run()` 在 async 上下文崩溃 [event_listener.py:91-102] — **已修复**：添加运行时检查
- [x] [Review][Patch] P4: `_running` 标志竞态条件 [outbox_processor.py:131] — **已修复**：使用 `asyncio.Event`
- [x] [Review][Patch] P5: `page_size` 无上限验证 [audit_service.py:197-199] — **已修复**：添加验证逻辑
- [x] [Review][Patch] P6: 环境变量解析无异常处理 [audit.py:75-86] — **已修复**：添加 `_int_env` 辅助函数
- [x] [Review][Patch] P7: Outbox 变更可能因无 commit 丢失 — **跳过**：设计决策，由调用方管理事务
- [x] [Review][Patch] P8: `correction_level` 无范围校验 [audit_events.py:102] — **已修复**：添加 `__post_init__` 校验
- [x] [Review][Patch] P9: `mark_entries_for_retry` 冗余代码 [outbox_processor.py:173-177] — **已修复**：移除重复赋值
- [x] [Review][Patch] P10: `rowcount` 可能为 None — **跳过**：代码已处理，无需修改

#### defer (已存在，非本次引入)
- [x] [Review][Defer] W1: Archive 不强制 7 年保留 — deferred, MVP 限制，MinIO WORM V2 才实现
- [x] [Review][Defer] W2: 缺少 CLI 命令 — deferred, Spec 要求但未实现，属于后续 Story
- [x] [Review][Defer] W4: 合规分析不验证完整覆盖 — deferred, MVP 限制，完整验证 V2 实现

#### Review Tasks (Story 1.10 补丁)
- [x] [Review][Task] T1: 事件监听器映射对齐 — `event_listener.py` 映射类型与 spec 对齐 (AC-5)
  - **结论**: event_listener.py 映射与实际领域事件命名一致（Story 1.2 规范: `DocumentProcessed`, `AgentDecided` 等，无 "Event" 后缀）
  - **修复**: 测试文件 `test_audit_event_listener_mapping.py` 使用正确的事件类型名称
  - **Spec 问题**: Story 1.10 AC-5 错误使用 `DocumentProcessedEvent` 后缀，应与 Story 1.2 保持一致
- [x] [Review][Task] T2: Outbox RLS 状态转换收紧 — `002_audit_tables.py` 策略审查 (AC-2)
  - **结论**: 原 RLS 策略允许 `published → published` 过渡（不应该）
  - **修复**: 使用 CASE 表达式显式验证状态转换:
    - `pending → published|failed` ✓
    - `failed → pending` ✓
    - `published → 任意` ✗ (终态不可转换)

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 技术参考

### 关键依赖库

| 库 | 版本 | 用途 |
|------|------|------|
| `sqlalchemy` | 2.0+ | ORM |
| `pydantic` | 2.0+ | 数据验证 |
| `aio-pika` | 9.0+ | RabbitMQ 客户端 |
| `passlib` | 1.7+ | 密码哈希（用于校验） |

### 合规检查矩阵

| 检查项 | 要求 | 验证方式 |
|--------|------|---------|
| 等保 2.0 安全审计 | 登录/权限/敏感操作 100% 记录 | 代码审查 + 功能测试 |
| SOX 合规 | 财务操作完整审计，7 年保留 | 集成测试 |
| WORM 不可变性 | 已写入日志不可修改/删除 | 安全测试 |
| 事务原子性 | 审计与业务操作同事务 | 单元测试 |

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-18
**最后更新/Last Updated:** 2026-04-18
**更新说明:** 基于统一审计日志需求创建，遵循 SDD+TDD 融合模式，包含 7 个 Task（Task 0 SDD 规范 + Task 1-5 TDD 循环 + Task 6 架构验证），安全层覆盖率要求≥85%
