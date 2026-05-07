# Story 1.18a: Prefect 工作流引擎集成

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 集成 Prefect 3.6+ 工作流引擎（数据管道）,
**So that** 系统支持确定性数据流，包括文档处理、RAG 索引、报告生成。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第一个故事，在 Story 1.1（六边形架构骨架）和 Story 1.3（事件总线）完成后实现 Prefect 工作流引擎集成。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **数据管道引擎** | 支持文档处理、RAG 索引、报告生成的确定性数据流 | 三种流程可用 |
| **任务重试与失败恢复** | 确保长时间运行任务的可观测性和可恢复性 | 重试成功率≥95% |
| **流程状态追踪** | 流程状态持久化至 Redis，支持断点恢复 | TTL 24h-30d |
| **领域事件发布** | DocProcessed/RAGIndexed/ReportGenerated 事件驱动后续处理 | 事件发布成功 |

> ⚠️ **MVP 范围澄清**：本 Story 实现 **Prefect 工作流引擎基础集成**，支持三种核心数据管道流程。
> - **编排服务协调** → Story 1.18b 范围（Prefect + LangGraph 协调）
> - **LangGraph Agent 编排** → Story 1.18b 范围

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 6: MVP 关键机制增强，Story 1.18a

**架构公理追溯:** ADR-002 双核引擎架构（Prefect + LangGraph），Prefect 负责确定性数据流

**前置依赖:** Story 1.1（六边形架构骨架）、Story 1.3（事件总线）

**后续依赖:** Story 1.18b（LangGraph Agent 编排集成，Prefect + LangGraph 协调）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Prefect 工作流引擎基础架构

**Given** 架构骨架已实现（Story 1.1）
**When** 实现 Prefect 3.6+ 工作流引擎基础架构
**Then** Prefect 引擎包装器正确初始化
**And** 工作流流程定义符合六边形架构约束

**验证标准/Validation Criteria:**
- [ ] PrefectEngine 引擎包装器实现（`src/infrastructure/workflow/prefect_engine.py`）
- [ ] 流程状态持久化至 Redis（TTL 24h-30d）
- [ ] 领域层零 Prefect 依赖验证（Workflow 定义在基础设施层）
- [ ] 架构层覆盖率≥85%

### AC-2: 文档处理流程 (Document Processing Flow)

**Given** Prefect 引擎已初始化
**When** 执行文档处理任务
**Then** DocumentProcessingFlow 正确执行文档处理步骤
**And** 支持任务重试（失败重试成功率≥95%）
**And** 流程状态持久化至 Redis
**And** 发布 DocProcessed 领域事件

**验证标准/Validation Criteria:**
- [ ] DocumentProcessingFlow 流程定义（`src/infrastructure/workflow/flows/document_processing_flow.py`）
- [ ] 任务重试配置（指数退避 + 最大重试次数）
- [ ] 流程状态追踪（running/completed/failed）
- [ ] DocProcessed 事件发布（集成 Story 1.3 事件总线）
- [ ] 工作流执行延迟 P95<500ms（**仅指 Prefect 流程编排开销，不含 LLM 调用时间**）
- [ ] LLM 调用时间由 UDMR 路由的 100ms 约束（project-context.md §7.1）单独考核

### AC-3: RAG 索引流程 (RAG Pipeline Flow)

**Given** Prefect 引擎已初始化
**When** 执行 RAG 索引任务
**Then** RAGPipelineFlow 正确执行 RAG 索引步骤
**And** 支持任务重试（失败重试成功率≥95%）
**And** 流程状态持久化至 Redis
**And** 发布 RAGIndexed 领域事件

**验证标准/Validation Criteria:**
- [ ] RAGPipelineFlow 流程定义（`src/infrastructure/workflow/flows/rag_pipeline_flow.py`）
- [ ] 任务重试配置（指数退避 + 最大重试次数）
- [ ] 流程状态追踪（running/completed/failed）
- [ ] RAGIndexed 事件发布（集成 Story 1.3 事件总线）
- [ ] 工作流执行延迟 P95<500ms（**仅指 Prefect 流程编排开销，不含 LLM 调用时间**）

### AC-4: 报告生成流程 (Report Generation Flow)

**Given** Prefect 引擎已初始化
**When** 执行报告生成任务
**Then** ReportGenerationFlow 正确执行报告生成步骤
**And** 支持任务重试（失败重试成功率≥95%）
**And** 流程状态持久化至 Redis
**And** 发布 ReportGenerated 领域事件

**验证标准/Validation Criteria:**
- [ ] ReportGenerationFlow 流程定义（`src/infrastructure/workflow/flows/report_generation_flow.py`）
- [ ] 任务重试配置（指数退避 + 最大重试次数）
- [ ] 流程状态追踪（running/completed/failed）
- [ ] ReportGenerated 事件发布（集成 Story 1.3 事件总线）
- [ ] 工作流执行延迟 P95<500ms（**仅指 Prefect 流程编排开销，不含 LLM 调用时间**）

### AC-5: 编排服务接口定义

> ⚠️ **范围说明**：本 AC 仅定义 OrchestrationService 接口，不涉及完整实现。完整编排服务协调实现在 Story 1.18b。

**Given** Prefect 工作流引擎已集成
**When** 定义编排服务接口
**Then** OrchestrationService 接口方法签名正确
**And** 接口方法与 Prefect/LangGraph 解耦（通过领域事件通信）

**验证标准/Validation Criteria:**
- [ ] OrchestrationService 接口类定义（`src/application/services/orchestration_service.py`）
- [ ] 工作流执行方法签名（execute_data_pipeline/task_type）
- [ ] 状态查询方法签名（get_workflow_status）
- [ ] 事件驱动协调接口（与 LangGraph 解耦）

> **注意**：OrchestrationService 完整实现（包括 Prefect + LangGraph 协调逻辑）属于 Story 1.18b 范围。

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考故事 1.17 的 SDD+TDD 融合开发模式。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域服务 Schema (Domain Services)
- [ ] OrchestrationService 接口类（`src/application/services/orchestration_service.py`）
  - 方法: `execute_data_pipeline(task_type, context) -> WorkflowResult`, `get_workflow_status(flow_id) -> WorkflowStatus`
  - 职责: 协调 Prefect 执行数据管道，通过领域事件与 LangGraph 解耦

#### 工作流引擎接口 (Workflow Engine Interface)
- [ ] PrefectEngine 协议接口（`src/domain/services/workflow_engine.py`）**领域层定义接口**
  - 方法: `submit_flow(flow_name, parameters) -> FlowRunId`, `get_flow_run_status(run_id) -> FlowRunStatus`, `cancel_flow_run(run_id) -> None`
  - 职责: 定义工作流引擎抽象接口，基础设施层实现具体引擎

#### 配置模型 (Configuration Models)
- [ ] PrefectConfig 配置（`src/infrastructure/config/prefect.py`）
  - 环境变量: `PREFECT_API_URL`, `PREFECT_WORK_QUEUE`, `PREFECT_STORAGE Redis TTL`
  - 从环境变量读取（`from_env()` 方法，复用 OtelConfig 模式）

#### 数据模型 (Data Models)
- [ ] WorkflowResult 值对象（`src/domain/value_objects/workflow_result.py`）
  - 字段: run_id, status, started_at, completed_at, error, retry_count
- [ ] WorkflowStatus 枚举（`src/domain/value_objects/workflow_status.py`）
  - 值: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
- [ ] DocProcessed/RAGIndexed/ReportGenerated 领域事件（已在 Story 1.2 定义）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.18a.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - 文档处理流程执行（正常/重试/失败）
  - RAG 索引流程执行（正常/重试/失败）
  - 报告生成流程执行（正常/重试/失败）
  - 编排服务协调
  - 流程状态持久化

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | PrefectEngine | 工作流引擎基础 | `test_prefect_engine.py` | Task 1 |
| **TDD 单元测试** | DocumentProcessingFlow | 文档处理流程 | `test_document_processing_flow.py` | Task 2 |
| **TDD 单元测试** | RAGPipelineFlow | RAG 索引流程 | `test_rag_pipeline_flow.py` | Task 2 |
| **TDD 单元测试** | ReportGenerationFlow | 报告生成流程 | `test_report_generation_flow.py` | Task 2 |
| **TDD 单元测试** | OrchestrationService | 编排服务协调 | `test_orchestration_service.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.18a.feature` | Task 0 |
| **SDD 架构验证** | 架构约束 | 六边形架构约束 | `test_prefect_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端工作流 | `test_prefect_integration.py` | Task 3 |

---

#### 测试隔离约束（必须遵守）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**
> 参考 CLAUDE.md 测试隔离约束。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **asyncio 上下文** | asyncio.Lock 使用类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture

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
| AC-1 | Prefect 工作流引擎基础架构 | Task 1 | Subtask 1.1-1.3（PrefectEngine 红→绿→重构） | `test_prefect_engine.py` |
| AC-2 | 文档处理流程 | Task 2 | Subtask 2.1-2.3（DocumentProcessingFlow 红→绿→重构） | `test_document_processing_flow.py` |
| AC-3 | RAG 索引流程 | Task 2 | Subtask 2.4-2.6（RAGPipelineFlow 红→绿→重构） | `test_rag_pipeline_flow.py` |
| AC-4 | 报告生成流程 | Task 2 | Subtask 2.7-2.9（ReportGenerationFlow 红→绿→重构） | `test_report_generation_flow.py` |
| AC-5 | 编排服务接口 | Task 3 | Subtask 3.1-3.3（OrchestrationService 红→绿→重构） | `test_orchestration_service.py` |
| AC-1 | 架构验证 | Task 3 | Subtask 3.4-3.6（架构约束验证 红→绿→重构） | `test_prefect_architecture.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 WorkflowEngine 协议接口（`src/domain/services/workflow_engine.py`）
- [ ] Subtask 0.2: 定义 WorkflowResult 值对象（`src/domain/value_objects/workflow_result.py`）
- [ ] Subtask 0.3: 定义 WorkflowStatus 枚举（`src/domain/value_objects/workflow_status.py`）
- [ ] Subtask 0.4: 定义 PrefectConfig 配置模型（`src/infrastructure/config/prefect.py`）
- [ ] Subtask 0.5: 定义 OrchestrationService 接口（`src/application/services/orchestration_service.py`）
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.18a.feature`（Dev agent 创建）
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Prefect 工作流引擎基础架构

**关联 AC:** AC-1

> **职责边界:** Task 1 负责 PrefectEngine 引擎包装器和基础设施层流程定义

#### TDD 循环：PrefectEngine 引擎包装器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/test_prefect_engine.py`（验证工作流引擎基础） |
| 🟢 绿 | 实现 `src/infrastructure/workflow/prefect_engine.py` - PrefectEngine 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.1: 🔴 红 — 编写 PrefectEngine 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 PrefectEngine（Prefect 3.6+ 引擎包装）
- [ ] Subtask 1.3: 🔄 重构 — 优化引擎包装器实现

**完成标准/Definition of Done:**
- [ ] PrefectEngine 实现完成
- [ ] 流程状态持久化至 Redis（TTL 24h-30d）
- [ ] 领域层零 Prefect 依赖验证
- [ ] TDD 循环全部通过

---

### Task 2: 三种数据管道流程实现

**关联 AC:** AC-2, AC-3, AC-4

> **职责边界:** Task 2 负责三种数据管道流程实现

#### TDD 循环 [A]：DocumentProcessingFlow 文档处理流程

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/flows/test_document_processing_flow.py` |
| 🟢 绿 | 实现 `src/infrastructure/workflow/flows/document_processing_flow.py` |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 2.1: 🔴 红 — 编写 DocumentProcessingFlow 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 DocumentProcessingFlow
- [ ] Subtask 2.3: 🔄 重构 — 优化流程定义

#### TDD 循环 [B]：RAGPipelineFlow RAG 索引流程

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/flows/test_rag_pipeline_flow.py` |
| 🟢 绿 | 实现 `src/infrastructure/workflow/flows/rag_pipeline_flow.py` |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 2.4: 🔴 红 — 编写 RAGPipelineFlow 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 RAGPipelineFlow
- [ ] Subtask 2.6: 🔄 重构 — 优化流程定义

#### TDD 循环 [C]：ReportGenerationFlow 报告生成流程

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/flows/test_report_generation_flow.py` |
| 🟢 绿 | 实现 `src/infrastructure/workflow/flows/report_generation_flow.py` |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 2.7: 🔴 红 — 编写 ReportGenerationFlow 失败测试
- [ ] Subtask 2.8: 🟢 绿 — 实现 ReportGenerationFlow
- [ ] Subtask 2.9: 🔄 重构 — 优化流程定义

**完成标准/Definition of Done:**
- [ ] 三种流程全部实现完成
- [ ] 任务重试配置（指数退避 + 最大重试次数）
- [ ] 流程状态追踪（running/completed/failed）
- [ ] 领域事件发布（DocProcessed/RAGIndexed/ReportGenerated）
- [ ] TDD 循环全部通过

---

### Task 3: 编排服务与架构验证

**关联 AC:** AC-5, AC-1

> **职责边界:** Task 3 负责 OrchestrationService 编排服务和架构验证

#### TDD 循环 [A]：OrchestrationService 编排服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_orchestration_service.py` |
| 🟢 绿 | 实现 `src/application/services/orchestration_service.py` |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 3.1: 🔴 红 — 编写 OrchestrationService 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 OrchestrationService
- [ ] Subtask 3.3: 🔄 重构 — 优化编排服务实现

#### TDD 循环 [B]：架构约束验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_prefect_architecture.py`（验证六边形架构约束） |
| 🟢 绿 | 实现架构验证逻辑（领域层零 Prefect 依赖、依赖方向） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.4: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.6: 🔄 重构 — 验证器优化

#### 集成测试

- [ ] Subtask 3.7: 创建 `tests/integration/test_prefect_integration.py`（端到端工作流）

**完成标准/Definition of Done:**
- [ ] OrchestrationService 实现完成
- [ ] 六边形架构验证通过（领域层零 Prefect 依赖）
- [ ] 工作流执行延迟 P95<500ms
- [ ] 任务调度准确率 100%
- [ ] 失败重试成功率≥95%
- [ ] 集成测试通过

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **架构层覆盖率 ≥85%**（`pytest --cov=src/infrastructure/workflow --cov-fail-under=85`）- **P1 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application --cov-fail-under=85`）- **P1 阻断门禁**
- [ ] **集成测试覆盖率 ≥75%**（`pytest --cov=tests/integration`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **ADR-002 双核引擎架构:** Prefect 负责确定性数据流，LangGraph 负责 Agent 认知推理
  - Prefect: 文档处理、RAG 索引、报告生成
  - LangGraph: BLM 规划、Agent 协作
  - 协调机制: 编排服务通过领域事件协调，无直接耦合
- **设计约束:**
  - 领域层零依赖外部框架（Prefect 仅在基础设施层）
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 工作流引擎位于 `src/infrastructure/workflow/`
- **技术栈:**
  - Prefect 3.6.16+
  - Redis（流程状态持久化，TTL 24h-30d）
  - RabbitMQ（事件发布，集成 Story 1.3 事件总线）

### Prefect 与 LangGraph 边界

| 职责 | Prefect | LangGraph |
|------|---------|-----------|
| **数据管道** | ✅ 文档处理、RAG 索引、报告生成 | ❌ 不涉及 |
| **Agent 编排** | ❌ 不涉及 | ✅ BLM 规划、Agent 协作 |
| **状态持久化** | Redis（TTL 24h-30d） | Redis（TTL 24h-30d） |
| **事件发布** | DocProcessed/RAGIndexed/ReportGenerated | AgentDecided/CheckpointReached |
| **协调方式** | 编排服务通过领域事件协调 | 编排服务通过领域事件协调 |

> ⚠️ **RAGIndexed/ReportGenerated 事件说明**：这两个事件属于**基础设施层内部事件**，仅触发下游 Saga，不进入领域事件总线的 WORM 归档。与 project-context.md §12 定义的 11 个领域事件（DocProcessed/ToolExecuted/AgentDecided 等）性质不同。

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── services/
│   │   │   └── workflow_engine.py      # WorkflowEngine 协议接口（领域层定义）
│   │   ├── value_objects/
│   │   │   ├── workflow_result.py      # WorkflowResult 值对象
│   │   │   └── workflow_status.py      # WorkflowStatus 枚举
│   │   └── events/
│   │       └── __init__.py            # DocProcessed（Story 1.2）；RAGIndexed/ReportGenerated 为基础设施层内部事件
│   ├── application/
│   │   └── services/
│   │       └── orchestration_service.py # OrchestrationService（应用层）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── prefect.py             # PrefectConfig 配置
│   │   └── workflow/
│   │       ├── prefect_engine.py      # PrefectEngine 实现
│   │       └── flows/
│   │           ├── __init__.py
│   │           ├── document_processing_flow.py
│   │           ├── rag_pipeline_flow.py
│   │           └── report_generation_flow.py
│   └── interfaces/
│       └── event_listeners/
│           └── workflow_listener.py    # 工作流事件监听（复用 Story 1.3 模式）
├── tests/
│   ├── unit/
│   │   ├── architecture/
│   │   │   └── test_prefect_architecture.py
│   │   ├── application/services/
│   │   │   └── test_orchestration_service.py
│   │   └── infrastructure/workflow/
│   │       ├── test_prefect_engine.py
│   │       └── flows/
│   │           ├── test_document_processing_flow.py
│   │           ├── test_rag_pipeline_flow.py
│   │           └── test_report_generation_flow.py
│   ├── integration/
│   │   └── test_prefect_integration.py
│   └── acceptance/
│       ├── test_story_1.18a.feature
│       └── test_story_1.18a_steps.py
└── docs/
    └── developer/
        └── prefect_guide.md           # Prefect 实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.17: UDMR 基础路由](./1-17-udmr-basic-routing.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，PrefectConfig 采用相同 `from_env()` 类方法
2. **六边形架构严格分层** — WorkflowEngine 协议定义在领域层，PrefectEngine 实现在基础设施层
3. **事件驱动解耦** — 编排服务仅负责触发和协调，不处理具体业务逻辑
4. **性能基准测试** — 工作流性能要求 P95<500ms，需独立基准测试

**应用到本故事/Applied to This Story:**
- [ ] PrefectConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [ ] WorkflowEngine 协议定义在领域层，PrefectEngine 基础设施层实现
- [ ] Task 3 包含架构验证测试（六边形架构约束检测）
- [ ] 性能基准测试验证 P95<500ms（仅指编排开销，不含 LLM）
- [ ] RAGIndexed/ReportGenerated 为基础设施层内部事件，不进入 WORM 归档
- [ ] AC-5 仅定义 OrchestrationService 接口，完整实现在 Story 1.18b

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `5929817` | fix: 修复 Group 记忆 Redis key 格式和 mypy 类型错误 | 修复 Redis key 格式 |
| `ff63d49` | fix(test): 修复验收测试和集成测试的测试隔离约束 | 测试隔离修复 |
| `dc7c9e7` | docs: 更新 Story 1.15b 状态为 review | 文档更新 |
| `1f779ed` | test: 添加六层存储集成测试 test_storage_integration.py | 集成测试 |
| `a16c9ab` | docs: 完善 Story 1.15b 完成状态说明 | 文档完善 |

**可应用模式:**
1. **测试隔离严格遵守** — Redis key 使用 UUID 前缀隔离
2. **六边形架构严格分层** — domain/infrastructure/application 层严格分离
3. **配置与实现分离** — Config 类与实现类分离

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-27 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] ADR-002 双核引擎架构分析完成（Prefect vs LangGraph 边界）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 前一个故事学习经验已整合

### 文件清单 File List

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/services/workflow_engine.py` - WorkflowEngine 协议接口
- `src/domain/value_objects/workflow_result.py` - WorkflowResult 值对象
- `src/domain/value_objects/workflow_status.py` - WorkflowStatus 枚举
- `src/infrastructure/config/prefect.py` - PrefectConfig 配置模型
- `src/infrastructure/workflow/prefect_engine.py` - PrefectEngine 实现
- `src/infrastructure/workflow/flows/document_processing_flow.py` - 文档处理流程
- `src/infrastructure/workflow/flows/rag_pipeline_flow.py` - RAG 索引流程
- `src/infrastructure/workflow/flows/report_generation_flow.py` - 报告生成流程
- `src/application/services/orchestration_service.py` - OrchestrationService
- `tests/unit/infrastructure/workflow/test_prefect_engine.py` - PrefectEngine 单元测试
- `tests/unit/infrastructure/workflow/flows/test_document_processing_flow.py` - 文档处理流程测试
- `tests/unit/infrastructure/workflow/flows/test_rag_pipeline_flow.py` - RAG 索引流程测试
- `tests/unit/infrastructure/workflow/flows/test_report_generation_flow.py` - 报告生成流程测试
- `tests/unit/application/services/test_orchestration_service.py` - OrchestrationService 测试
- `tests/unit/architecture/test_prefect_architecture.py` - 架构验证测试
- `tests/integration/test_prefect_integration.py` - 集成测试
- `tests/acceptance/test_story_1.18a.feature` - Gherkin 验收测试
- `tests/acceptance/test_story_1.18a_steps.py` - 验收测试步骤实现
- `docs/developer/prefect_guide.md` - Prefect 实施指南

**更新的文件/Updated Files:**
- `src/domain/services/__init__.py` - 添加 WorkflowEngine 导出
- `src/domain/value_objects/__init__.py` - 添加 WorkflowResult, WorkflowStatus 导出
- `src/infrastructure/config/__init__.py` - 添加 PrefectConfig 导出
- `src/infrastructure/workflow/__init__.py` - 添加 PrefectEngine, flows 导出

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.18a |
| **Story Key** | 1-18a-prefect-workflow-integration |
| **File** | `_bmad-output/implementation-artifacts/stories/1-18a-prefect-workflow-integration.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-18a（MVP，ARCH Prefect） |
| **覆盖 FR** | ARCH Prefect（Prefect 3.6+ 数据管道：文档处理/RAG 索引/报告生成） |
| **依赖 Story** | Story 1.1（六边形架构骨架）、Story 1.3（事件总线） |
| **前置条件** | DomainEvent 基类已定义（Story 1.2），事件总线已实现（Story 1.3） |
| **后续 Story** | Story 1.18b（LangGraph Agent 编排集成） |
| **覆盖率要求** | 架构层≥85%，集成测试≥75% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-3）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-5）
3. [x] Architecture constraints extracted 架构约束已提取（ADR-002 双核引擎、Prefect vs LangGraph 边界）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 1.17 配置模式、事件驱动解耦）
5. [x] Sprint status synced to `ready-for-dev`
6. [x] Prefect vs LangGraph 边界已澄清
7. [x] P95 性能指标已澄清（仅指编排开销，不含 LLM 时间）
8. [x] RAGIndexed/ReportGenerated 事件性质已澄清（基础设施层内部事件）
9. [x] AC-5 范围已澄清（仅定义接口，完整实现在 Story 1.18b）

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [ADR-002 双核引擎架构](../../_bmad-output/planning-artifacts/architecture.md#32-决策-2-adr-002-双核引擎架构-prefect--langgraph) | Prefect + LangGraph 架构决策 |
| [Story 1.1: 六边形架构骨架](./1-1-hexagonal-architecture-skeleton.md) | 前置 Story（架构基础） |
| [Story 1.2: 领域事件定义](./1-2-domain-event-definition.md) | 前置 Story（事件定义） |
| [Story 1.3: 事件总线实现](./1-3-event-bus-implementation.md) | 前置 Story（事件总线） |
| [Story 1.18b: LangGraph Agent 编排集成](./1-18b-langgraph-agent-orchestration.md) | 后续 Story（Prefect + LangGraph 协调） |
| [Story 1.17: UDMR 基础路由](./1-17-udmr-basic-routing.md) | 前一个故事（配置模式参考） |

---

## 🔭 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施（遵循 SDD+TDD 融合模式）
- [ ] 运行 `code-review` 进行代码审查

- [ ] 可选：运行 `/bmad:tea:automate` 生成测试（如果 Test Architect 模块已安装）

---

**模板版本/Template Version:** 2.2.0
**创建日期/Created:** 2026-04-27
**最后更新/Last Updated:** 2026-04-27
**更新说明:** Story 1.18a 完整版本 - 实现 Prefect 工作流引擎集成：(1) PrefectEngine 引擎包装器; (2) DocumentProcessingFlow 文档处理流程; (3) RAGPipelineFlow RAG 索引流程; (4) ReportGenerationFlow 报告生成流程; (5) OrchestrationService 编排服务; (6) 六边形架构验证; (7) 性能基准测试 P95<500ms

**五性审查修复 (2026-04-27)**：
- P1 修复: P95<500ms 澄清为"仅指 Prefect 流程编排开销，不含 LLM 调用时间"
- P2 修复: RAGIndexed/ReportGenerated 澄清为"基础设施层内部事件，不进入 WORM 归档"
- P3 修复: AC-5 重命名为"编排服务接口定义"，明确仅定义接口不涉及实现
