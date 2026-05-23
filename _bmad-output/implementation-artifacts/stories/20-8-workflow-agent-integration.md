# Story 20.8: 双核引擎集成验证

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现双核引擎（Prefect + LangGraph）端到端集成验证，补全 PrefectEngine 事件发布、统一验收测试，对齐设计文档 v2.6,
**So that** 工作流引擎与 Agent 编排引擎通过统一端口集成，六边形架构合规，生产化路径清晰。

### 业务价值

本 Story 是 Epic 20（重大重构）的收尾 Story。前序 Story（20-1~20-7）完成了测试框架、事件总线、异步重构、统一存储、端口契约、事务子系统。本 Story 在此基础上对双核引擎进行端到端集成验证，对齐设计文档 `docs/architecture/sisys-workflow-agent-integration-design.md` v2.6。

| 差距 | 严重度 | 说明 |
|------|--------|------|
| PrefectEngine 事件发布缺失 | P1 | `event_publisher` 已注入但未使用（LangGraphEngine 已实现 AgentDecided） |
| WorkflowSubmitted 事件类未定义 | P1 | `workflow_events.py` 仅有 RAGIndexed/ReportGenerated |
| 事件总线通道注册缺失 | P1 | `channel_router.py` 未注册 WorkflowSubmitted |
| Gherkin 统一验收测试缺失 | P0 | 1-18a/1-18b 各有验收测试，但无双引擎统一集成验收 |
| 设计文档与代码对齐未验证 | P1 | 需端到端验证端口签名、路由逻辑、DI注册、状态映射 |

| 指标 | 现状 | 目标 |
|------|------|------|
| PrefectEngine 事件发布 | 0 | WorkflowSubmitted 事件发布完成 |
| 统一验收测试 | 0 | Gherkin 双引擎集成验收测试 |
| 设计文档对齐 | 未验证 | 全部端口/适配器/DI/状态映射对齐确认 |

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) — ADR-002 双核引擎架构
**设计文档:** [`sisys-workflow-agent-integration-design.md`](../../docs/architecture/sisys-workflow-agent-integration-design.md) v2.6

**前置依赖:** Story 1.18a（Prefect 工作流集成）、Story 1.18b（LangGraph Agent 编排）、Story 20-1~20-7（重大重构系列）

---

## 🔗 前置依赖与现有代码继承

### 依赖故事

| 故事 | 组件 | 用途 |
|------|------|------|
| Story 1.1 | 六边形架构骨架 | 架构分层、端口/适配器模式 |
| Story 1.3 | DualChannelEventBus + ChannelRouter | 事件发布/路由基础设施 |
| Story 1.18a | WorkflowEnginePort + PrefectEngine + OrchestrationService | 双核引擎数据管道部分 |
| Story 1.18b | AgentEnginePort + LangGraphEngine + BasicAgentGraph | 双核引擎认知推理部分 |
| Story 20-6 | 端口契约测试重构 | 端口注册/解析/契约测试基础设施 |
| Story 20-7 | 事务子系统重构 | Saga/Outbox 事件发布基础设施 |

### 现有代码继承（必须复用，禁止重复定义）

| 现有组件 | 文件路径 | 复用方式 |
|---------|---------|---------|
| `WorkflowEnginePort` | `src/domain/ports/workflow_engine.py` (21-49) | 直接复用，本 Story 不修改端口定义 |
| `AgentEnginePort` | `src/domain/ports/agent_engine.py` (21-49) | 直接复用，本 Story 不修改端口定义 |
| `EventPublisher` | `src/domain/ports/event_publisher.py` | PrefectEngine 注入，发布 WorkflowSubmitted 事件 |
| `PublishResult` | `src/domain/events/publish_result.py` | 事件发布结果检查（`is_full_failure` 属性） |
| `DomainEvent` | `src/domain/events/base.py` | WorkflowSubmitted 事件基类 |
| `FlowStatus` | `src/domain/value_objects/flow_status.py` (18-35) | 统一状态枚举（PENDING/RUNNING/COMPLETED/FAILED/RETRYING） |
| `OrchestrationService` | `src/application/services/orchestration_service.py` (44-96) | 双引擎路由逻辑，直接复用 |
| `PrefectEngine` | `src/infrastructure/workflow/prefect_engine.py` (31-129) | 修改：添加事件发布方法 |
| `LangGraphEngine` | `src/infrastructure/agent_orch/langgraph_engine.py` (31-162) | 参考：事件发布模式复用 |
| `AgentDecided` | `src/domain/events/agent_events.py` (23-44) | 参考：事件类定义模板 |
| `RAGIndexed` | `src/domain/events/workflow_events.py` (21-37) | 参考：已有工作流事件类 |
| `ChannelRouter` | `src/infrastructure/messaging/channel_router.py` | 修改：注册 WorkflowSubmitted 通道映射 |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: PrefectEngine 事件发布补全

**Given** PrefectEngine 已注入 `event_publisher` 但未使用，LangGraphEngine 已实现 AgentDecided 事件发布
**When** PrefectEngine.submit_flow 成功提交工作流后
**Then** 发布 `WorkflowSubmitted` 领域事件
**And** 事件发布失败不回写 FAILED 状态（与 LangGraphEngine 行为一致）

**验证标准:**
- [x] `src/domain/events/workflow_events.py` 新增 `WorkflowSubmitted` 事件类（继承 DomainEvent）
- [x] `PrefectEngine.submit_flow` 成功后调用 `_publish_workflow_submitted()`
- [x] `_publish_workflow_submitted()` 检查 `PublishResult.is_full_failure` 并记录 warning 日志
- [x] 事件发布异常捕获后仅 `logger.exception`，不影响 `submit_flow` 返回值（flow_run_id 正常返回）

### AC-2: 双引擎事件发布对称性

**Given** PrefectEngine 和 LangGraphEngine 均注入 EventPublisher
**When** 比较两者的事件发布逻辑
**Then** 两者遵循相同模式：publish → 检查 None/is_full_failure → logger.warning

**验证标准:**
- [x] PrefectEngine._publish_workflow_submitted 与 LangGraphEngine._publish_agent_decided 模式一致
- [x] 两者均使用 `try/except Exception` 包裹事件发布
- [x] 两者均检查 `publish_result is None`（防御性检查，Protocol 声明非 None）和 `publish_result.is_full_failure`
- [x] 测试覆盖双引擎事件发布异常路径

### AC-3: 事件总线通道注册

**Given** WorkflowSubmitted 是新定义的领域事件
**When** ChannelRouter 初始化事件通道映射
**Then** WorkflowSubmitted 注册到 RELIABLE 通道（RabbitMQ + Outbox）

**验证标准:**
- [x] `channel_router.py` 注册 WorkflowSubmitted 通道映射
- [x] 事件类型名称为 `"WorkflowSubmitted"`
- [x] 通道策略与 AgentDecided 一致

### AC-4: Gherkin 统一验收测试

**Given** Story 1-18a/1-18b 各有独立验收测试
**When** 创建统一集成验收测试
**Then** 覆盖双引擎提交、状态查询、事件发布的完整流程

**验证标准:**
- [x] `tests/acceptance/test_acceptance_workflow-agent-integration.feature` 包含双引擎集成场景（6 个场景）
- [x] `tests/acceptance/test_acceptance_workflow-agent-integration.py` 实现步骤函数
- [x] 场景覆盖：data_pipeline 提交（AC-1）、agent_reasoning 提交、状态查询、事件发布（AC-1）、双引擎对称性（AC-2）、通道注册（AC-3）
- [x] 使用测试专用 DI 容器（mock Prefect/LangGraph SDK，不依赖真实 server）

### AC-5: 设计文档与代码对齐验证

**Given** 设计文档 v2.6 描述了完整的双引擎集成架构
**When** 逐一验证设计文档中的声明
**Then** 代码实现与文档描述完全一致

**验证标准:**
- [x] WorkflowEnginePort 方法签名与文档 Section 2.2 一致
- [x] AgentEnginePort 方法签名与文档 Section 2.3 一致
- [x] OrchestrationService 双引擎路由与文档 Section 2.4 时序图一致
- [x] PrefectEngine 状态映射（9→5）与文档 Section 3.1 映射表一致
- [x] LangGraphEngine 状态（COMPLETED/FAILED）与文档 Section 3.1 一致
- [x] DI 注册模式与文档 Section 6.1 一致
- [x] 六边形架构约束测试通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] `WorkflowSubmitted` 事件定义位于 `src/domain/events/workflow_events.py`
- [x] 使用 dataclass(frozen=True) 继承 `DomainEvent`
- [x] 事件字段：`flow_run_id: uuid.UUID`、`flow_name: str`、`parameters: dict[str, Any]`
- [x] `event_type` 字段：`event_type: str = field(default="WorkflowSubmitted", init=False)`（放在所有业务字段之后，与 workflow_events.py 现有 RAGIndexed/ReportGenerated 风格一致）
- [x] `__post_init__` 方法：设置 `aggregate_id = flow_run_id`、`aggregate_type = "Workflow"`（参考 AgentDecided/RAGIndexed 模式）
- [x] 事件命名符合规范：`[Aggregate][Action]` → `WorkflowSubmitted`

#### 端口契约（已存在，本 Story 不新增端口）
- [x] `WorkflowEnginePort` — 已在 `src/composition_root.py` bootstrap() 函数中注册（第983-995行）
- [x] `AgentEnginePort` — 已在 `src/composition_root.py` bootstrap() 函数中注册（第1002-1014行）
- [x] 端口契约测试已通过（Story 20-6 补全）

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
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_workflow-agent-integration.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_workflow-agent-integration.py`
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | WorkflowSubmitted 事件 | 事件创建、字段验证 | `tests/unit/domain/events/test_workflow_events.py` | Task 1 |
| **TDD 单元测试** | ChannelRouter 通道注册 | WorkflowSubmitted 映射注册 | `tests/unit/infrastructure/messaging/test_channel_router.py` | Task 1 |
| **TDD 单元测试** | PrefectEngine 事件发布 | 事件发布成功/失败路径 | `tests/unit/infrastructure/workflow/test_prefect_engine.py` | Task 2 |
| **集成测试** | 双引擎路由 + DI | OrchestrationService 端到端 | `tests/integration/test_integration_workflow_agent_integration.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_workflow-agent-integration.feature` | Task 0/4 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_workflow-agent-integration.py` | Task 0/4 |
| **SDD 架构验证** | 六边形约束 | 导入边界、依赖方向 | `tests/unit/architecture/test_hexagonal_architecture_constraints.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 |
|---------|------|
| **外部服务隔离** | Prefect/LangGraph 测试使用 mock（不依赖真实 server） |
| **资源唯一性** | 测试数据使用 UUID |
| **并行隔离** | 并行测试 `pytest tests/ -n 8` 通过 |

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | WorkflowSubmitted 事件类定义 | Task 1 | 事件类创建 | `test_workflow_events.py` |
| AC-1 | PrefectEngine 事件发布 | Task 2 | _publish_workflow_submitted | `test_prefect_engine.py` |
| AC-2 | 双引擎发布模式对称 | Task 2 | 异常处理对齐 | `test_prefect_engine.py` |
| AC-2 | 双引擎对称性验收测试 | Task 4 | Subtask 4.6 场景5 | `.feature` + `.py` |
| AC-3 | 事件总线通道注册 | Task 1 | channel_router 注册 | `test_channel_router.py` |
| AC-3 | 通道注册验收测试 | Task 4 | Subtask 4.7 场景6 | `.feature` + `.py` |
| AC-4 | Gherkin 验收测试 | Task 0/4 | 场景 + 步骤实现 | `.feature` + `.py` |
| AC-5 | 设计文档对齐 | Task 3 | 端到端验证 | `test_integration_*.py` |
| AC-5 | 架构约束验证 | Task 5 | 导入边界 | `test_hexagonal_*.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-3, AC-4

> **目的：** 定义 WorkflowSubmitted 事件 Schema、Gherkin 验收场景。

- [x] Subtask 0.1: 定义 WorkflowSubmitted 事件 Schema
  - 事件类名：`WorkflowSubmitted`
  - 基类：`DomainEvent`（`src/domain/events/base.py`）
  - 字段：`flow_run_id: uuid.UUID`、`flow_name: str`、`parameters: dict[str, Any]`、`event_type: str`（event_type 放在最后，与 RAGIndexed/ReportGenerated 一致）
  - `__post_init__`：设置 `aggregate_id = flow_run_id`、`aggregate_type = "Workflow"`
  - `event_type` 声明：`event_type: str = field(default="WorkflowSubmitted", init=False)`
- [x] Subtask 0.2: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_workflow-agent-integration.feature`
  - 场景1: 数据管道工作流提交（覆盖 AC-1/AC-5）
  - 场景2: Agent 推理任务提交（覆盖 AC-5）
  - 场景3: 双引擎状态查询（覆盖 AC-5）
  - 场景4: PrefectEngine 事件发布（覆盖 AC-1）
  - 场景5: 双引擎事件发布对称性验证（覆盖 AC-2）
  - 场景6: WorkflowSubmitted 事件总线通道注册（覆盖 AC-3）
- [x] Subtask 0.3: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_workflow-agent-integration.py`
- [x] Subtask 0.4: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准:**
- [x] 事件 Schema 定义完毕
- [x] Gherkin 验收测试运行失败（预期行为）

---

### Task 1: WorkflowSubmitted 事件类 + 通道注册

**关联 AC:** AC-1, AC-3

#### TDD 循环 A：WorkflowSubmitted 事件类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 修改 `tests/unit/domain/events/test_workflow_events.py`，新增 TestWorkflowSubmittedEvent 测试类（WorkflowSubmitted 创建、字段验证、aggregate_type 自动填充） |
| 🟢 绿 | 在 `src/domain/events/workflow_events.py` 添加 WorkflowSubmitted 事件类 |
| 🔄 重构 | 对齐 RAGIndexed 事件类模式，运行 `ruff` + `mypy` |

- [x] Subtask 1.1: 🔴 红 — 修改 test_workflow_events.py，新增 WorkflowSubmitted 失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现 WorkflowSubmitted 事件类
- [x] Subtask 1.3: 🔄 重构 — 对齐代码风格

#### TDD 循环 B：事件总线通道注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 在 `tests/unit/infrastructure/messaging/test_channel_router.py` 编写通道注册验证测试（WorkflowSubmitted 在 ChannelRouter 映射中存在） |
| 🟢 绿 | 在 `src/infrastructure/messaging/channel_router.py` 注册 WorkflowSubmitted |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [x] Subtask 1.4: 🔴 红 — 编写通道注册验证测试
- [x] Subtask 1.5: 🟢 绿 — 注册 WorkflowSubmitted 通道映射
- [x] Subtask 1.6: 🔄 重构 — 验证

**完成标准:**
- [x] WorkflowSubmitted 事件类创建并注册
- [x] 通道映射注册完成
- [x] 所有测试通过

---

### Task 2: PrefectEngine 事件发布

**关联 AC:** AC-1, AC-2

> **参考模式：** 复用 `LangGraphEngine._publish_agent_decided()` (langgraph_engine.py:139-162) 的模式。

#### TDD 循环 A：事件发布成功路径

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 PrefectEngine 事件发布测试（mock EventPublisher，验证 WorkflowSubmitted 被发布） |
| 🟢 绿 | 在 PrefectEngine 添加 `_publish_workflow_submitted()` 方法 |
| 🔄 重构 | 对齐 LangGraphEngine 模式 |

- [x] Subtask 2.1: 🔴 红 — 编写事件发布成功测试
- [x] Subtask 2.2: 🟢 绿 — 实现 _publish_workflow_submitted()
- [x] Subtask 2.3: 🔄 重构 — 对齐模式

#### TDD 循环 B：事件发布异常路径

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写异常路径测试（publish 返回 None、is_full_failure、抛出异常） |
| 🟢 绿 | 实现异常处理（logger.warning/logger.exception） |
| 🔄 重构 | 验证状态不被覆写 |

- [x] Subtask 2.4: 🔴 红 — 编写事件发布异常测试
- [x] Subtask 2.5: 🟢 绿 — 实现异常处理
- [x] Subtask 2.6: 🔄 重构 — 验证 COMPLETED 状态不被覆写

**完成标准:**
- [x] PrefectEngine.submit_flow 成功后发布 WorkflowSubmitted 事件
- [x] 事件发布异常不影响引擎状态
- [x] 与 LangGraphEngine 模式对称

---

### Task 3: 集成验证测试

**关联 AC:** AC-5

#### TDD 循环 A：双引擎端到端集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写集成测试（OrchestrationService 双引擎路由、DI resolve） |
| 🟢 绿 | 验证现有代码通过集成测试 |
| 🔄 重构 | 优化测试结构 |

- [x] Subtask 3.1: 🔴 红 — 编写 OrchestrationService 双引擎路由测试
- [x] Subtask 3.2: 🔴 红 — 编写 DI 注册 resolve 验证测试
- [x] Subtask 3.3: 🔴 红 — 编写 PrefectEngine 状态映射验证测试（9→5）
- [x] Subtask 3.4: 🟢 绿 — 验证现有代码通过
- [x] Subtask 3.5: 🔄 重构 — 优化

**完成标准:**
- [x] OrchestrationService 双引擎路由正确
- [x] DI 注册 resolve 正确
- [x] Prefect 状态映射（9→5）正确
- [x] LangGraph 状态（COMPLETED/FAILED）正确

---

### Task 4: Gherkin 验收测试实现

**关联 AC:** AC-2, AC-3, AC-4

> **基于 Task 0 创建的 Gherkin 场景，实现 BDD 步骤函数。**

#### TDD 循环 A：步骤函数实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 确认 Gherkin 场景运行失败（步骤未实现） |
| 🟢 绿 | 实现 BDD 步骤函数 |
| 🔄 重构 | 统一断言表达 |

- [x] Subtask 4.0: 🔴 红 — 运行 Gherkin 场景，确认步骤未实现导致测试失败
- [x] Subtask 4.1: 🟢 绿 — 实现 DI 容器初始化步骤（使用测试专用 DI 容器，mock Prefect/LangGraph SDK 客户端）
- [x] Subtask 4.2: 🟢 绿 — 实现 data_pipeline 提交步骤（场景1）
- [x] Subtask 4.3: 🟢 绿 — 实现 agent_reasoning 提交步骤（场景2）
- [x] Subtask 4.4: 🟢 绿 — 实现状态查询验证步骤（场景3）
- [x] Subtask 4.5: 🟢 绿 — 实现事件发布验证步骤（场景4）
- [x] Subtask 4.6: 🟢 绿 — 实现双引擎事件发布对称性验证步骤（场景5，覆盖 AC-2）
- [x] Subtask 4.7: 🟢 绿 — 实现通道注册验证步骤（场景6，覆盖 AC-3）
- [x] Subtask 4.8: 🔄 重构 — 运行全部验收测试

**完成标准:**
- [x] 所有 Gherkin 场景（1-6）通过
- [x] 使用测试专用 DI 容器（mock Prefect/LangGraph SDK）

---

### Task 5: 架构约束验证

**关联 AC:** AC-5

> **性质说明：** SDD 规范验证测试，验证代码符合六边形架构约束。

#### 架构验证测试

- [x] Subtask 5.1: 运行 `tests/unit/architecture/test_hexagonal_architecture_constraints.py`
- [x] Subtask 5.2: 验证 Domain 层不导入 prefect/langgraph（已有测试覆盖）
- [x] Subtask 5.3: 验证 Application 层不导入 Infrastructure 层（已有测试覆盖）
- [x] Subtask 5.4: 补充 WorkflowSubmitted 事件类的零依赖验证（如有必要）

**完成标准:**
- [x] 所有架构约束测试通过
- [x] Domain 层零外部依赖

---

### Task 6: 开发结束验收

**关联 AC:** All

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

- [x] Subtask 6.1: 场景 — 验证 `src` 完成清单
  - [x] `workflow_events.py` 新增 WorkflowSubmitted
  - [x] `__init__.py` 更新 WorkflowSubmitted 导出
  - [x] `prefect_engine.py` 新增 _publish_workflow_submitted
  - [x] `channel_router.py` 注册 WorkflowSubmitted
  - [x] `event_channels.yaml` 同步添加通道配置
- [x] Subtask 6.2: 场景 — 验证 `tests` 完成清单
  - [x] `test_workflow_events.py` 单元测试
  - [x] `test_prefect_engine.py` 事件发布测试补充
  - [x] `test_integration_workflow_agent_integration.py` 集成测试
  - [x] `test_acceptance_workflow-agent-integration.*` 验收测试
- [x] Subtask 6.3: 运行 `pytest`、`ruff check`、`mypy` 收尾校验
- [x] Subtask 6.4: 更新 sprint-status.yaml 为 `done`
- [x] Subtask 6.5: 更新设计文档 `docs/architecture/sisys-workflow-agent-integration-design.md`
  - [x] Section 4.2 事件发布责任：改为 "Engine 层发布 WorkflowSubmitted 事件"
  - [x] Section 5.1 策略差异表：更新 Prefect 列的发布位置
  - [x] Section 5.3 添加 PrefectEngine 的 PublishResult 检查模式说明

**完成标准:**
- [x] 完成清单已逐项验证
- [x] Story 可进入 `done`

---

## 🔍 Review Findings（代码审查发现）

> **审查日期:** 2026-05-23
> **审查范围:** commit 8b285311 (Story 20.8 实现)

### Decision Needed

- [x] ~~[Review][Decision] 验收测试使用 MagicMock 违反约束~~ — 已修复：改用 `prefect.states.State(type=st)` 真实 Prefect SDK 对象替代 MagicMock。

### Patch

- [x] ~~[Review][Patch] AST 检查不精确~~ — 已修复：`has_return_after_try` 改为 `has_return_after_event_publish_try`，精确验证 return 语句位于最后一个 try/except 块之后。`tests/acceptance/test_acceptance_workflow-agent-integration.py:259-283`

### Deferred（预存问题）

- [x] [Review][Defer] 可变字典引用 — frozen dataclass 的 `parameters`/`decision_result` 字段存储可变引用，调用方可在构造后修改。AgentDecided 同样有此问题。预存，非本 Story 引入。
- [x] [Review][Defer] flow_run_id 默认工厂误导 — 默认 `uuid.uuid4()` 从未被使用，可能掩盖调用方遗漏。RAGIndexed/ReportGenerated 同样有此模式。预存。
- [x] [Review][Defer] aggregate_type 可被覆盖 — `if not self.aggregate_type:` 条件允许调用方传入自定义值，而非强制设置。所有事件都有此模式。预存。
- [x] [Review][Defer] DomainEvent 注册表无隔离 — 测试检查 `_registry["WorkflowSubmitted"]` 但未确保清洁状态。预存模式。
- [x] [Review][Defer] 不可序列化参数延迟失败 — parameters 包含 Prefect 对象时仅在 `to_dict()` 时报错。预存问题。

### Dismissed（误报/合规）

- 重复字段声明：误报，实际代码无重复
- 静默异常吞掉：符合 AC-1 设计要求（日志记录不影响返回值）
- 缺少参数校验：类型签名 + OrchestrationService 校验已覆盖

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Hexagonal Architecture），端口-适配器模式
- **设计约束:** 领域层零依赖、依赖方向严格（domain ← application ← infrastructure）
- **ADR-002:** 双核引擎架构 — Prefect（确定性数据管道）+ LangGraph（认知推理）
- **技术栈:** Python 3.11+、Prefect 3.6.25、LangGraph 1.1.6

### 关键架构决策

**来源:** ADR-002 双核引擎架构

| 决策 | 选择 | 理由 |
|------|------|------|
| 工作流引擎 | Prefect | DAG 预定义、Deployment 远程提交 |
| Agent 引擎 | LangGraph | 状态图驱动、动态决策 |
| 状态模型 | FlowStatus 统一 | 5 状态枚举（PENDING/RUNNING/COMPLETED/FAILED/RETRYING） |
| 编排层 | OrchestrationService | 应用层统一路由 |
| 事件发布 | Engine 层发布 | LangGraphEngine 发布 AgentDecided，PrefectEngine 发布 WorkflowSubmitted |

### 设计文档偏离声明

> **偏离项：** 设计文档 `sisys-workflow-agent-integration-design.md` v2.6 Section 4.2 声明 "PrefectEngine 本身不发布领域事件"。
>
> **偏离原因：** 双引擎事件发布对称性（AC-2）要求两者遵循相同模式。`event_publisher` 已注入到 PrefectEngine 但未使用（设计预留），本 Story 激活该能力。
>
> **实施后动作：** 需同步更新设计文档 Section 4.2（事件发布责任）、Section 5.1（策略差异表）、Section 5.3（PublishResult 检查模式），将 PrefectEngine 的事件发布策略从 "Flow 内部发布" 更新为 "Engine 层发布 WorkflowSubmitted 事件"。

### 关键代码模式参考

#### 事件类定义（复用 AgentDecided）
```python
# src/domain/events/agent_events.py:23-44
@dataclass(frozen=True)
class AgentDecided(DomainEvent):
    agent_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="AgentDecided", init=False)
    decision_result: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
```

> **字段顺序说明：** WorkflowSubmitted 的 `event_type` 放在所有业务字段之后（与 RAGIndexed/ReportGenerated 一致），而非参照 AgentDecided 放在 `flow_run_id` 之后。这是为了保持同一文件 `workflow_events.py` 内部的代码风格统一。

#### 事件发布模式（复用 LangGraphEngine）
```python
# src/infrastructure/agent_orch/langgraph_engine.py:139-162
async def _publish_agent_decided(self, agent_id, result, run_id):
    event = AgentDecided(agent_id=agent_id, decision_result=result, confidence=0.9)
    publish_result = await self._event_publisher.publish(event)
    if publish_result is None:
        logger.warning("AgentDecided 事件发布返回 None [run_id=%s]", run_id)
    elif publish_result.is_full_failure:
        logger.warning("AgentDecided 事件发布全部失败 [run_id=%s]: %s", run_id, publish_result)
```

> **Protocol 契约说明：** `EventPublisher.publish()` 声明返回 `PublishResult`（非 Optional），所有已知实现均保证返回非 None。None 检查属于防御性编程，与 LangGraphEngine 现有模式保持对称。

#### Prefect 状态映射（9→5）
```python
# src/infrastructure/workflow/prefect_engine.py:105-129
# SCHEDULED/PENDING → PENDING
# RUNNING → RUNNING
# COMPLETED → COMPLETED
# FAILED(run_count < max_retries) → RETRYING
# FAILED(run_count >= max_retries)/CANCELLED/CRASHED/CANCELLING/PAUSED → FAILED
```

### 前一个故事学习经验

**来源:** [Story 20-7](./20-7-transaction-subsystem-refactor.md) + [Story 1-18b](./1-18b-langgraph-agent-orchestration.md)

**关键学习/Key Learnings:**
- 事件发布异常**必须**独立于引擎执行状态（LangGraphEngine 在 catch 中不覆写 COMPLETED）
- `PublishResult` 返回值理论上非 None（Protocol 声明 `-> PublishResult`），但 LangGraphEngine 使用防御性 None 检查，PrefectEngine 保持对称
- `_env_int` 配置异常包装：LangGraphConfig 已实现（含键名上下文），PrefectConfig 尚未统一（可选优化项）
- Gherkin 步骤函数不使用 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()`
- BDD 步骤中同一中文文本可能需要同时支持 given/when 装饰器

**应用到本故事:**
- [ ] PrefectEngine 事件发布严格遵循"异常不覆写状态"模式
- [ ] 测试使用 `event_loop.run_until_complete()` 运行 async 函数
- [ ] 事件类使用 frozen dataclass + field(default_factory=uuid.uuid4)

### 项目结构说明

```
src/
├── domain/
│   ├── events/
│   │   ├── base.py                        # DomainEvent 基类
│   │   ├── agent_events.py                # AgentDecided 事件
│   │   ├── workflow_events.py             # RAGIndexed + ReportGenerated + [WorkflowSubmitted]
│   │   └── publish_result.py              # PublishResult 值对象
│   ├── ports/
│   │   ├── workflow_engine.py             # WorkflowEnginePort Protocol
│   │   ├── agent_engine.py               # AgentEnginePort Protocol
│   │   └── event_publisher.py             # EventPublisher Protocol
│   └── value_objects/
│       └── flow_status.py                 # FlowStatus 枚举
├── application/
│   └── services/
│       └── orchestration_service.py        # OrchestrationService 双引擎路由
├── infrastructure/
│   ├── workflow/
│   │   └── prefect_engine.py              # PrefectEngine [修改: 添加事件发布]
│   ├── agent_orch/
│   │   └── langgraph_engine.py            # LangGraphEngine [参考: 事件发布模式]
│   ├── messaging/
│   │   └── channel_router.py              # ChannelRouter [修改: 注册 WorkflowSubmitted]
│   └── config/
│       ├── prefect.py                     # PrefectConfig
│       └── langgraph.py                   # LangGraphConfig
└── composition_root.py                    # DI 组合根
```

---

## 🤖 开发代理记录

### 使用模型

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.7 |
| **Execution Date** | 2026-05-23 |

### 调试日志引用

| 配置项 | 路径 |
|--------|------|
| **设计文档** | `docs/architecture/sisys-workflow-agent-integration-design.md` v2.6 |
| **前置 Story** | `_bmad-output/implementation-artifacts/stories/1-18a-*.md`, `1-18b-*.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单

- [x] 故事需求从设计文档 v2.6 + 前置 Story 分析提取
- [x] 架构约束从 architecture.md 提取
- [x] 前置故事学习经验整合（1-18a/1-18b）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单

**待创建的文件:**
- `tests/integration/test_integration_workflow_agent_integration.py` — 双引擎集成测试
- `tests/acceptance/test_acceptance_workflow-agent-integration.feature` — Gherkin 场景
- `tests/acceptance/test_acceptance_workflow-agent-integration.py` — BDD 步骤实现

**待修改的文件:**
- `tests/unit/domain/events/test_workflow_events.py` — 新增 WorkflowSubmitted 测试类（文件已存在）
- `src/domain/events/workflow_events.py` — 添加 WorkflowSubmitted 事件类
- `src/domain/events/__init__.py` — 导出 WorkflowSubmitted（更新 `__all__`）
- `src/infrastructure/workflow/prefect_engine.py` — 添加事件发布方法
- `src/infrastructure/messaging/channel_router.py` — 注册 WorkflowSubmitted 通道
- `config/event_channels.yaml` — 同步添加 WorkflowSubmitted 通道配置
- `tests/unit/infrastructure/workflow/test_prefect_engine.py` — 补充事件发布测试
- `docs/architecture/sisys-workflow-agent-integration-design.md` — 更新 Section 4.2/5.1/5.3 事件发布策略描述

---

## 📊 故事详情

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 20.8 |
| **Story Key** | 20-8-workflow-agent-integration |
| **File** | `_bmad-output/implementation-artifacts/stories/20-8-workflow-agent-integration.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 20: 重大重构 |
| **优先级** | P1 |
| **覆盖 FR** | FR-1.18a, FR-1.18b, ADR-002 |

### 完成总结

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前置故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | AC-1 验证标准错误引用 `self._runs`（PrefectEngine 无此属性） | P0 | 修正为 "不影响 `submit_flow` 返回值" |
| 2 | EventPublisher Protocol 声明返回 `PublishResult` 非 Optional，文档要求检查 None | P0 | 标注为防御性检查，添加 Protocol 契约说明段落 |
| 3 | 设计文档 v2.6 Section 4.2 声明 "PrefectEngine 不发布事件"，与本 Story 目标冲突 | P0 | 添加设计偏离声明，添加设计文档同步更新检查项 |
| 4 | `event_type` 字段位置与 workflow_events.py 现有风格不一致 | P1 | 统一到最后位置，与 RAGIndexed/ReportGenerated 一致 |
| 5 | Task 4 缺失红阶段验证 Subtask | P1 | 新增 Subtask 4.0 红阶段验证 |
| 6 | `test_workflow_events.py` 标注为"待创建"但已存在 | P1 | 修正为"待修改" |
| 7 | 缺失模板必需章节：文档审查修复、代码审查发现 | P0 | 新增两个章节 |
| 8 | AC-2/AC-3 完全缺乏 Gherkin 场景覆盖 | P0 | 新增场景5（双引擎对称性）和场景6（通道注册），补充 Subtask 4.6/4.7 |
| 9 | DI 容器在测试环境可行性未明确 | P0 | Subtask 4.1 添加 mock 策略说明，AC-4 修改为"测试专用 DI 容器" |
| 10 | `_env_int` 学习经验描述不够精确 | P2 | 标注 PrefectConfig 尚未统一（可选优化项） |
| 11 | 追溯矩阵 AC-3 测试文件路径错误 + 缺少 AC-2/AC-3 验收覆盖行 | P1 | 修正为 test_channel_router.py，新增 AC-2/AC-3 验收测试行 |
| 12 | Task 4 头部 AC 关联不完整 | P1 | 修正为 AC-2, AC-3, AC-4 |
| 13 | 测试分类表缺少通道注册测试行 | P2 | 新增 test_channel_router.py 归属 Task 1 |

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

**故事版本:** v1.5.0
**创建日期:** 2026-05-23
**最后更新:** 2026-05-23
**更新说明:**
- v1.5.0: R5 追溯矩阵与对齐审查 — 修正 AC-3 测试文件路径（P1）、新增 AC-2/AC-3 验收测试覆盖行（P1）、修正 Task 4 AC 关联（P1）、补充测试分类表通道注册行（P2）
- v1.4.0: R4 Gherkin 覆盖审查 — 补充 AC-2/AC-3 Gherkin 场景5/6（P0）、补充 Subtask 4.6/4.7 步骤函数（P0）、明确 DI 容器 mock 策略（P0）、更新 _env_int 学习经验描述（P2）
- v1.3.0: R3 模板合规性审查 — 新增文档审查修复章节（P0）、新增代码审查发现章节（P0）、Task 4 补充红阶段 Subtask 4.0（P1）、修正 test_workflow_events.py 文件状态为"待修改"（P1）、修正 Subtask 1.1 描述为"修改"（P1）
- v1.2.0: R2 正确性审查 — 修正 AC-1 验证标准错误引用 self._runs（P0-1）、标注 Protocol 契约与防御性 None 检查（P0-2）、新增设计文档偏离声明与更新提醒（P0-3）、修正 event_type 字段位置到 workflow_events.py 风格（P1-4）、新增 Subtask 6.5 设计文档同步检查项
- v1.1.0: R1 正确性审查 — 补充 __init__.py/event_channels.yaml 到文件清单，修正端口注册位置，补充 __post_init__ 模式，修正 AgentDecided 代码片段字段顺序
- v1.0.0: 创建故事文件
