# Story 1.18a: Prefect 工作流引擎集成

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 集成 Prefect 3.6+ 作为确定性数据管道引擎（端口抽象 + MVP 流程）,
**So that** 系统支持文档处理、RAG 索引、报告生成等工作流任务的可靠执行与状态追踪。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第三个故事。在 Story 1.1（六边形骨架）和 Story 1.3（事件总线）完成后，集成 Prefect 3.6+ 工作流引擎，建立双核引擎架构（ADR-002）的数据管道基础。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **WorkflowEnginePort 端口抽象** | 引擎可替换，支持未来 LangGraph 集成（1.18b） | Protocol 定义于 domain 层，零外部依赖 |
| **PrefectEngine 实现** | 确定性数据管道执行，内置重试/状态追踪 | 所有 Prefect 导入限定于 infrastructure/workflow/ |
| **DocumentProcessingFlow** | 端到端验证工作流架构：解析→嵌入→索引 | Flow 完成后发布 DocumentProcessed 事件 |
| **OrchestrationService** | 应用层统一编排入口，解耦引擎与业务 | 仅依赖 WorkflowEnginePort 端口 |
| **新事件定义** | 为下游故事（RAG/报告）预留事件契约 | RAGIndexed/ReportGenerated 注册到 ChannelRouter |

> ⚠️ **MVP 范围澄清**：本 Story 仅实现 **WorkflowEnginePort 端口 + PrefectEngine + DocumentProcessingFlow**。
> - RAGPipelineFlow → Epic 2/3 故事
> - ReportGenerationFlow → Epic 6 故事
> - BatchAnalysisFlow → Epic 3 故事
> - QualityControlFlow → Epic 3 故事
> - LangGraph Agent 编排 → Story 1.18b

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1, 价值组 6, Story 1.18a

**架构决策追溯:** ADR-002 双核引擎架构（architecture.md §3.2）

**前置依赖:** Story 1.1（六边形架构骨架）、Story 1.3（事件总线实现）

**后续依赖:** Story 1.18b（LangGraph Agent 编排，依赖本 Story 的 WorkflowEnginePort 和 OrchestrationService）

---

## 🔗 前置依赖与现有代码继承

### 依赖故事

| 故事 | 组件 | 用途 |
|------|------|------|
| Story 1.1 | 六边形架构骨架 | 架构分层、端口/适配器模式 |
| Story 1.3 | DualChannelEventBus + ChannelRouter | 事件发布/路由基础设施 |

### 现有代码继承（必须复用，禁止重复定义）

| 现有组件 | 文件路径 | 复用方式 |
|---------|---------|---------|
| `EventPublisher` 端口 | `src/domain/ports/event_publisher.py` | PrefectEngine 注入，Flow 完成后发布事件（`async def publish(event: DomainEvent) -> PublishResult`，导入路径为 `src.domain.ports.event_publisher`，不在 `__init__.py` 的 `__all__` 中） |
| `PublishResult` | `src/domain/events/publish_result.py` | 事件发布结果（含 `is_success`/`is_full_failure`/`partial_error` 属性），PrefectEngine 需检查并记录失败 |
| `DomainEvent` 基类 | `src/domain/events/base.py` | RAGIndexed/ReportGenerated 继承 |
| `ChannelRouter` | `src/infrastructure/messaging/channel_router.py` | 新增 RAGIndexed/ReportGenerated 映射（通过 `config/event_channels.yaml`） |
| `PortRegistry` + `register_port` | `src/domain/ports/registry.py` | 注册 WorkflowEnginePort |
| `Composition Root` | `src/composition_root.py` | DI 注册 workflow 端口 |
| `DocumentProcessed` 事件 | `src/domain/events/document_events.py` | DocumentProcessingFlow 完成后发布 |
| `PrefectConfig` 模式参考 | `src/infrastructure/config/auto_execute.py` | from_env() + frozen dataclass 模式 |
| `AutoExecuteService` 模式 | `src/domain/services/auto_execute_service.py` | 事件驱动执行模式参考 |
| `SagaOrchestrator` 模式 | `src/infrastructure/saga/saga_orchestrator.py` | 多步骤编排模式参考 |

### 架构位置

```
用户操作/事件触发
       ↓
OrchestrationService (1.18a) → 路由 task_type
       ↓ data_pipeline
PrefectEngine (1.18a) → 包装 Prefect SDK
       ↓ submit_flow
DocumentProcessingFlow (1.18a)
  ├── parse_document (@task)
  ├── generate_embedding (@task)
  └── index_document (@task)
       ↓ 完成
EventPublisher.publish(DocumentProcessed) → DualChannelEventBus → Outbox/RabbitMQ

未来扩展:
  OrchestrationService (1.18b) → task_type == "agent_reasoning"
       ↓
  LangGraphEngine (1.18b) → 包装 LangGraph SDK
```

---

## ✅ Acceptance Criteria 验收标准

### AC-1: WorkflowEnginePort 端口定义

**Given** 六边形架构骨架已实现（Story 1.1）
**When** 开发者需要执行工作流任务
**Then** `WorkflowEnginePort` Protocol 位于 `src/domain/ports/workflow_engine.py`，使用 `@runtime_checkable`
**And** 定义 `async def submit_flow(self, flow_name: str, parameters: dict[str, Any]) -> str`
**And** 定义 `async def get_flow_status(self, flow_run_id: str) -> FlowStatus`
**And** `FlowStatus` 值对象位于 `src/domain/value_objects/flow_status.py`（stdlib-only，枚举：PENDING/RUNNING/COMPLETED/FAILED/RETRYING）
**And** 零外部依赖（无 prefect/pydantic/langgraph 等导入）

**验证标准/Validation Criteria:**
- [x] WorkflowEnginePort Protocol（`src/domain/ports/workflow_engine.py`）
- [x] FlowStatus 值对象（`src/domain/value_objects/flow_status.py`）
- [x] `@runtime_checkable` 装饰器
- [x] 仅使用 Python 标准库类型

### AC-2: PrefectEngine 实现 WorkflowEnginePort

**Given** WorkflowEnginePort Protocol 已定义
**When** PrefectEngine 使用 PrefectConfig 实例化
**Then** PrefectEngine 位于 `src/infrastructure/workflow/prefect_engine.py`，满足 WorkflowEnginePort
**And** 所有 `import prefect` / `from prefect` 仅存在于 `src/infrastructure/workflow/`
**And** 架构约束测试确认 domain/application/interfaces 层零 Prefect 导入
**And** PrefectEngine 通过注入的 EventPublisher 发布领域事件

**验证标准/Validation Criteria:**
- [x] PrefectEngine 类（`src/infrastructure/workflow/prefect_engine.py`）
- [x] isinstance(PrefectEngine(...), WorkflowEnginePort) 返回 True
- [x] 架构测试验证零越界导入
- [x] EventPublisher 通过构造函数注入

### AC-3: DocumentProcessingFlow 执行

**Given** PrefectEngine 已初始化
**When** 通过 `submit_flow("DocumentProcessing", {"document_id": ..., "file_path": ...})` 提交文档处理请求
**Then** Prefect Flow 执行：parse_document → generate_embedding → index_document 作为顺序 Prefect tasks
**And** 成功完成后通过 EventPublisher 发布 `DocumentProcessed` 事件（构造时传入 `document_id`、`parse_result`、`embedding` 等字段；EventPublisher.publish() 返回 `PublishResult`，需检查 `is_full_failure` 并记录警告日志）
**And** 任务失败时 Prefect 内置重试机制激活（可配置重试次数）
**And** 工作流执行延迟 P95 < 500ms（mock 任务，测量编排开销）

**验证标准/Validation Criteria:**
- [x] DocumentProcessingFlow（`src/infrastructure/workflow/flows/document_processing_flow.py`）
- [x] document_tasks（`src/infrastructure/workflow/tasks/document_tasks.py`）
- [x] EventPublisher.publish() 调用验证（mock）
- [x] 重试行为验证（模拟任务失败）
- [x] 流程状态可查询

### AC-4: OrchestrationService 路由

**Given** OrchestrationService 在应用层
**When** 提交 `WorkflowTask`（task_type="data_pipeline"）
**Then** OrchestrationService 委托给 `WorkflowEnginePort`（通过注入）
**And** 返回 `WorkflowResult`（包含 flow_run_id、status、submitted_at）
**And** MVP 仅支持 data_pipeline 路由，agent_reasoning 由 Story 1.18b 补充

**验证标准/Validation Criteria:**
- [x] OrchestrationService（`src/application/services/orchestration_service.py`）
- [x] WorkflowTask 值对象（flow_name, parameters, task_type）
- [x] WorkflowResult 值对象（flow_run_id, status, submitted_at）
- [x] 仅依赖 WorkflowEnginePort 端口（不导入 infrastructure 层）

### AC-5: 新领域事件定义

**Given** 领域事件模式（Story 1.3）
**When** RAG 索引或报告生成在未来故事中完成
**Then** `RAGIndexed` 事件存在于 `src/domain/events/workflow_events.py`（字段：document_id, index_name, chunk_count）
**And** `ReportGenerated` 事件存在于同文件（字段：report_id, report_type, file_path）
**And** 两者注册到 `config/event_channels.yaml`，DeliveryMode.RELIABLE（通过 EventBusConfigLoader 加载到 ChannelRouter）

> **⚠️ 注册方式说明**：ChannelRouter 采用双轨注册机制 — 构造时加载 `DEFAULT_MAPPINGS`（19 个内置映射）作为基线，再通过 `EventBusConfigLoader.load()` 从 `config/event_channels.yaml` 追加/覆盖映射。新事件（RAGIndexed/ReportGenerated）需在 YAML 文件中添加映射条目，YAML 配置优先于默认映射。

**验证标准/Validation Criteria:**
- [x] RAGIndexed 事件（`src/domain/events/workflow_events.py`）
- [x] ReportGenerated 事件（同文件）
- [x] `config/event_channels.yaml` 新增 RAGIndexed/ReportGenerated 映射（DeliveryMode.RELIABLE）
- [x] `src/domain/events/__init__.py` 导出更新
- [x] 事件序列化/反序列化 roundtrip 测试通过

### AC-6: PrefectConfig 配置

**Given** 现有配置模式（AutoExecuteConfig.from_env()）
**When** PrefectConfig 加载
**Then** 从环境变量读取，提供合理默认值
**And** `PREFECT_API_URL` 默认 `"http://localhost:4200/api"`
**And** `PREFECT_WORK_POOL_NAME` 默认 `"sisys-worker-pool"`
**And** `PREFECT_RETRY_MAX_ATTEMPTS` 默认 `3`
**And** `PREFECT_RETRY_DELAY_SECONDS` 默认 `30`
**And** `PREFECT_TASK_TIMEOUT_SECONDS` 默认 `300`
**And** `PREFECT_FLOW_TIMEOUT_SECONDS` 默认 `3600`
**And** `@dataclass(frozen=True)` 不可变配置

**验证标准/Validation Criteria:**
- [x] PrefectConfig（`src/infrastructure/config/prefect.py`）
- [x] from_env() 类方法
- [x] frozen=True dataclass
- [x] 默认值与环境变量覆盖测试

### AC-7: Composition Root 注册

**Given** 现有 bootstrap() 模式（src/composition_root.py）
**When** 应用引导启动
**Then** `WorkflowEnginePort` 注册到 `PrefectEngine` 实现
**And** `OrchestrationService` 注册为应用层服务
**And** 端口契约测试验证注册/解析/兼容性

**验证标准/Validation Criteria:**
- [x] composition_root.py 新增 workflow 注册段
- [x] WorkflowEnginePort → PrefectEngine（SINGLETON，lambda 工厂模式）
- [x] OrchestrationService 注册（SINGLETON）
- [x] 契约测试（`tests/contracts/test_port_contract_workflow_engine.py`）

> **DI 注册模式说明**：PrefectConfig **不注册为端口**，而是在 lambda 工厂中通过 `PrefectConfig.from_env()` 创建。注册格式参考 `RedisManager`/`PostgreSQLManager`：
> ```python
> register_port(
>     name="workflow_engine",
>     version="v1.0.0",
>     interface=WorkflowEnginePort,
>     impl=lambda resolver: PrefectEngine(
>         PrefectConfig.from_env(),
>         resolver.resolve("event_publisher")
>     ),
>     module="src.infrastructure.workflow.prefect_engine",
>     lifetime=Lifetime.SINGLETON,
> )
> ```

### AC-8: 架构约束验证

**Given** 现有六边形架构测试套件
**When** 架构测试运行
**Then** domain/application/interfaces 层零 `import prefect`
**And** WorkflowEnginePort 仅使用 stdlib 类型
**And** OrchestrationService 不导入 infrastructure 层
**And** PrefectEngine 满足 WorkflowEnginePort Protocol（结构化子类型检查）

**验证标准/Validation Criteria:**
- [x] `tests/unit/architecture/test_prefect_architecture.py`
- [x] 零越界 Prefect 导入验证
- [x] 端口类型纯度验证
- [x] Protocol 一致性验证

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域端口 Schema (Domain Ports)
- [ ] WorkflowEnginePort 端口（`src/domain/ports/workflow_engine.py`）
  - `async def submit_flow(self, flow_name: str, parameters: dict[str, Any]) -> str` — 提交工作流执行，返回 flow_run_id
  - `async def get_flow_status(self, flow_run_id: str) -> FlowStatus` — 查询工作流状态
  - Protocol + `@runtime_checkable`
  - > **六边形架构约束**：WorkflowEnginePort 仅使用 Python 标准库类型，不导入 prefect/langgraph
  - > **编码约定**：文件首行 `from __future__ import annotations`，Protocol 方法体统一用 `...`（非空方法体），与 EventPublisher/SagaStep 等端口一致

#### 值对象 Schema (Value Objects)
- [ ] FlowStatus 值对象（`src/domain/value_objects/flow_status.py`）
  - 枚举：PENDING, RUNNING, COMPLETED, FAILED, RETRYING
  - str 枚举（继承 str, Enum），可序列化
  - > **位置决策说明**：SagaStatus 放在 `ports/saga_status.py`（仅服务 Saga 端口体系），FlowStatus 放在 `value_objects/` 是因为它被 WorkflowEnginePort 和 OrchestrationService 跨层共享，属于独立领域枚举而非端口附属
- [ ] WorkflowTask 值对象（`src/application/services/orchestration_service.py` 内联定义）
  - flow_name: str, parameters: dict[str, Any], task_type: Literal["data_pipeline", "agent_reasoning"]
  - frozen dataclass
- [ ] WorkflowResult 值对象（`src/application/services/orchestration_service.py` 内联定义）
  - flow_run_id: str, status: FlowStatus, submitted_at: datetime
  - frozen dataclass

#### 领域事件 Schema (Domain Events)
- [ ] RAGIndexed 事件（`src/domain/events/workflow_events.py`）
  - 继承 DomainEvent，`event_type: str = field(default="RAGIndexed", init=False)` — `__init_subclass__` 自动注册
  - 特有字段：document_id: uuid.UUID, index_name: str, chunk_count: int
  - aggregate_type="RAGIndex"
- [ ] ReportGenerated 事件（`src/domain/events/workflow_events.py`）
  - 继承 DomainEvent，`event_type: str = field(default="ReportGenerated", init=False)` — `__init_subclass__` 自动注册
  - 特有字段：report_id: uuid.UUID, report_type: str, file_path: str
  - aggregate_type="Report"

#### 配置模型 (Configuration Models)
- [ ] PrefectConfig 配置（`src/infrastructure/config/prefect.py`）
  - `@dataclass(frozen=True)` — 不可变配置
  - api_url: str（PREFECT_API_URL，默认 "http://localhost:4200/api"）
  - work_pool_name: str（PREFECT_WORK_POOL_NAME，默认 "sisys-worker-pool"）
  - retry_max_attempts: int（PREFECT_RETRY_MAX_ATTEMPTS，默认 3）
  - retry_delay_seconds: int（PREFECT_RETRY_DELAY_SECONDS，默认 30）
  - task_timeout_seconds: int（PREFECT_TASK_TIMEOUT_SECONDS，默认 300）
  - flow_timeout_seconds: int（PREFECT_FLOW_TIMEOUT_SECONDS，默认 3600）
  - from_env() 类方法

#### 基础设施适配器 Schema (Infrastructure Adapters)
- [ ] PrefectEngine（`src/infrastructure/workflow/prefect_engine.py`）
  - 实现 WorkflowEnginePort Protocol
  - 构造函数注入：PrefectConfig, EventPublisher
  - submit_flow(): 使用 Prefect SDK 提交 flow 运行
  - get_flow_status(): 映射 Prefect 状态到 FlowStatus 枚举
- [ ] DocumentProcessingFlow（`src/infrastructure/workflow/flows/document_processing_flow.py`）
  - Prefect @flow 装饰器
  - 顺序执行：parse_document → generate_embedding → index_document
  - 完成回调：通过 EventPublisher 发布 DocumentProcessed 事件
- [ ] document_tasks（`src/infrastructure/workflow/tasks/document_tasks.py`）
  - parse_document (@task, retries=2)
  - generate_embedding (@task, retries=2)
  - index_document (@task, retries=2)

#### 应用层 Schema (Application Services)
- [ ] OrchestrationService（`src/application/services/orchestration_service.py`）
  - 构造函数注入：WorkflowEnginePort
  - `async def execute(self, task: WorkflowTask) -> WorkflowResult`
  - MVP：仅路由 data_pipeline → WorkflowEnginePort

#### 统一端口注册与接口治理
- [ ] 端口注册：composition_root.py 注册 workflow_engine + orchestration_service
- [ ] 契约测试：tests/contracts/test_port_contract_workflow_engine.py
- [ ] 端口版本：v1.0.0，owner=platform-team

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1_18a.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_story_1_18a_steps.py`
- [ ] 覆盖场景：
  - PrefectEngine 创建与配置
  - DocumentProcessingFlow 提交与执行
  - 工作流完成 → DocumentProcessed 事件发布
  - 工作流失败 → 重试机制触发
  - OrchestrationService 路由 data_pipeline 任务
  - RAGIndexed/ReportGenerated 事件定义完整性
  - PrefectConfig 环境变量覆盖

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
| **TDD 单元测试** | FlowStatus | 枚举值完整性 | `test_flow_status.py` | Task 1 |
| **TDD 单元测试** | WorkflowEnginePort | Protocol 签名 | `test_workflow_engine.py` | Task 1 |
| **TDD 单元测试** | PrefectConfig | from_env() + 默认值 | `test_prefect_config.py` | Task 2 |
| **TDD 单元测试** | PrefectEngine | submit_flow/get_flow_status | `test_prefect_engine.py` | Task 2 |
| **TDD 单元测试** | DocumentProcessingFlow | 流程执行 + 事件发布 | `test_document_processing_flow.py` | Task 3 |
| **TDD 单元测试** | OrchestrationService | 路由逻辑 | `test_orchestration_service.py` | Task 3 |
| **TDD 单元测试** | RAGIndexed/ReportGenerated | 事件 roundtrip | `test_workflow_events.py` | Task 3 |
| **TDD 单元测试** | Composition Root | workflow 注册链路 | `test_composition_root_workflow.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1_18a.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_story_1_18a_steps.py` | Task 0 |
| **TDD 契约测试** | WorkflowEnginePort | 端口注册/解析/兼容性 | `test_port_contract_workflow_engine.py` | Task 3 |
| **SDD 架构验证** | 六边形约束 | 零越界 Prefect 导入 | `test_prefect_architecture.py` | Task 4 |
| **集成测试** | 端到端流程 | OrchestrationService → PrefectEngine → 事件发布 | `test_story_1_18a_integration.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [x] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [x] **架构层覆盖率 ≥85%**（架构层 Story，含工作流核心机制）
- [x] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [x] **Ruff 检查通过**（`ruff check src/`）
- [x] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：** 测试必须自包含（Self-contained），不依赖真实 Prefect server。

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **Prefect 隔离** | 所有 Prefect SDK 调用使用 mock（unittest.mock.AsyncMock） | 测试依赖真实 server，CI 失败 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **BDD async 配合** | BDD 步骤函数使用 `event_loop.run_until_complete()`，不使用 `@pytest.mark.asyncio` | context 数据丢失 |
| **EventPublisher mock** | 事件发布使用 AsyncMock，验证调用参数 | 测试耦合真实事件总线 |

**验证要求：**
- [x] 并行测试 `pytest tests/ -n 8` 通过
- [x] 连续5次运行无随机失败
- [x] `poetry run ruff check` 通过
- [x] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| 全部 | SDD 规范定义 + Gherkin 验收 | Task 0 | 0.1-0.10（规范定义+红阶段验证） | `test_story_1_18a.feature`, `test_story_1_18a_steps.py` |
| AC-1 | FlowStatus 值对象 | Task 1 | 1.1-1.3（FlowStatus 红→绿→重构） | `test_flow_status.py` |
| AC-1 | WorkflowEnginePort Protocol | Task 1 | 1.4-1.6（Protocol 红→绿→重构） | `test_workflow_engine.py` |
| AC-2 | PrefectEngine 实现 | Task 2 | 2.4-2.6（PrefectEngine 红→绿→重构） | `test_prefect_engine.py` |
| AC-3 | DocumentProcessingFlow | Task 3 | 3.1-3.3（Flow 红→绿→重构，含事件发布验证） | `test_document_processing_flow.py` |
| AC-3 | 事件发布验证 | Task 3 | 3.1-3.3（Flow 测试内验证 EventPublisher.publish 调用） | `test_document_processing_flow.py` |
| AC-4 | OrchestrationService | Task 3 | 3.4-3.6（路由逻辑 红→绿→重构） | `test_orchestration_service.py` |
| AC-5 | RAGIndexed/ReportGenerated | Task 3 | 3.7-3.9（事件定义+路由注册） | `test_workflow_events.py` |
| AC-6 | PrefectConfig | Task 2 | 2.1-2.3（Config 红→绿→重构） | `test_prefect_config.py` |
| AC-7 | Composition Root 注册 | Task 3 | 3.10-3.12（端口注册+契约测试） | `test_port_contract_workflow_engine.py` |
| AC-7 | 端口契约测试 | Task 3 | 3.11（契约测试） | `test_port_contract_workflow_engine.py` |
| AC-7 | Composition Root 注册验证 | Task 3 | 3.12（注册链路验证） | `test_composition_root_workflow.py` |
| AC-8 | 架构约束验证 | Task 4 | 4.1-4.6 | `test_prefect_architecture.py` |
| 全部 | 集成测试 | Task 4 | 4.7-4.9（端到端流程） | `test_story_1_18a_integration.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **目的：** 在进入代码实现前，明确端口、事件、配置、验收标准。

- [x] Subtask 0.1: 定义 FlowStatus 值对象 Schema（`src/domain/value_objects/flow_status.py`）
- [x] Subtask 0.2: 定义 WorkflowEnginePort Protocol（`src/domain/ports/workflow_engine.py`）
- [x] Subtask 0.3: 定义 PrefectConfig 配置 Schema（`src/infrastructure/config/prefect.py`）
- [x] Subtask 0.4: 定义 PrefectEngine 适配器 Schema
- [x] Subtask 0.5: 定义 DocumentProcessingFlow + document_tasks Schema
- [x] Subtask 0.6: 定义 OrchestrationService Schema
- [x] Subtask 0.7: 定义 RAGIndexed + ReportGenerated 事件 Schema
- [x] Subtask 0.8: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1_18a.feature`
- [x] Subtask 0.9: 编写 BDD 步骤实现 `tests/acceptance/test_story_1_18a_steps.py`
- [x] Subtask 0.10: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] Gherkin 验收测试运行失败（红阶段确认）
- [x] 端口契约清单完整（registry/composition_root/contract test）

---

### Task 1: FlowStatus 值对象 + WorkflowEnginePort Protocol

**关联 AC:** AC-1

#### TDD 循环 [A]：FlowStatus 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_flow_status.py`（验证枚举值、字符串转换、stdlib-only） |
| 🟢 绿 | 实现 `src/domain/value_objects/flow_status.py` — str 枚举 |
| 🔄 重构 | 优化类型注解，运行 `ruff` + `mypy` |

- [x] Subtask 1.1: 🔴 红 — 编写 FlowStatus 失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现 FlowStatus（PENDING/RUNNING/COMPLETED/FAILED/RETRYING）
- [x] Subtask 1.3: 🔄 重构 — 验证零外部依赖

#### TDD 循环 [B]：WorkflowEnginePort Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_workflow_engine.py`（验证 runtime_checkable、方法签名、FlowStatus 返回类型） |
| 🟢 绿 | 实现 `src/domain/ports/workflow_engine.py` — WorkflowEnginePort Protocol |
| 🔄 重构 | 注册到 `src/domain/ports/__init__.py` |

- [x] Subtask 1.4: 🔴 红 — 编写 WorkflowEnginePort 失败测试
- [x] Subtask 1.5: 🟢 绿 — 实现 WorkflowEnginePort Protocol
- [x] Subtask 1.6: 🔄 重构 — 更新 `__init__.py` 导出

**完成标准/Definition of Done:**
- [x] FlowStatus + WorkflowEnginePort 实现完成
- [x] 零外部依赖（stdlib-only）
- [x] TDD 循环全部通过

---

### Task 2: PrefectConfig + PrefectEngine

**关联 AC:** AC-2, AC-6

#### TDD 循环 [A]：PrefectConfig

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/config/test_prefect_config.py`（验证 from_env()、默认值、环境变量覆盖） |
| 🟢 绿 | 实现 `src/infrastructure/config/prefect.py` — PrefectConfig |
| 🔄 重构 | 对齐 RedisConfig from_env() 模式 |

- [x] Subtask 2.1: 🔴 红 — 编写 PrefectConfig 失败测试
- [x] Subtask 2.2: 🟢 绿 — 实现 PrefectConfig（frozen=True, from_env()）
- [x] Subtask 2.3: 🔄 重构 — 对齐配置模式

#### TDD 循环 [B]：PrefectEngine

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/test_prefect_engine.py`（mock Prefect SDK，验证 submit_flow/get_flow_status，WorkflowEnginePort 一致性） |
| 🟢 绿 | 实现 `src/infrastructure/workflow/prefect_engine.py` — PrefectEngine |
| 🔄 重构 | 优化错误处理和日志 |

- [x] Subtask 2.4: 🔴 红 — 编写 PrefectEngine 失败测试
- [x] Subtask 2.5: 🟢 绿 — 实现 PrefectEngine（mock Prefect SDK 调用）
- [x] Subtask 2.6: 🔄 重构 — 优化状态映射和错误处理

> **关键约束**：PrefectEngine 测试全量 mock Prefect SDK，不启动真实 Prefect server。使用 `unittest.mock.patch` 替换 `prefect` 模块调用。

**完成标准/Definition of Done:**
- [x] PrefectConfig from_env() 正确解析
- [x] PrefectEngine 满足 WorkflowEnginePort
- [x] 所有 Prefect 导入限定于 infrastructure/workflow/
- [x] TDD 循环全部通过

---

### Task 3: DocumentProcessingFlow + OrchestrationService + 事件 + DI 注册

**关联 AC:** AC-3, AC-4, AC-5, AC-7

#### TDD 循环 [A]：DocumentProcessingFlow

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/test_document_processing_flow.py`（验证流程定义、任务执行顺序、事件发布） |
| 🟢 绿 | 实现 `src/infrastructure/workflow/flows/document_processing_flow.py` + `tasks/document_tasks.py` |
| 🔄 重构 | 提取可复用任务模式 |

- [x] Subtask 3.1: 🔴 红 — 编写 DocumentProcessingFlow 失败测试
- [x] Subtask 3.2: 🟢 绿 — 实现 Flow（@flow + @task 装饰器）
- [x] Subtask 3.3: 🔄 重构 — 优化任务模块

#### TDD 循环 [B]：OrchestrationService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_orchestration_service.py`（验证路由到 WorkflowEnginePort、WorkflowResult 创建） |
| 🟢 绿 | 实现 `src/application/services/orchestration_service.py` |
| 🔄 重构 | 添加类型注解 |

- [x] Subtask 3.4: 🔴 红 — 编写 OrchestrationService 失败测试
- [x] Subtask 3.5: 🟢 绿 — 实现 OrchestrationService（注入 WorkflowEnginePort）
- [x] Subtask 3.6: 🔄 重构 — 优化路由逻辑

#### TDD 循环 [C]：工作流事件定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_workflow_events.py`（验证事件创建、序列化、注册表） |
| 🟢 绿 | 实现 `src/domain/events/workflow_events.py` + 更新 ChannelRouter |
| 🔄 重构 | 更新 `__init__.py` 导出 |

- [x] Subtask 3.7: 🔴 红 — 编写 RAGIndexed + ReportGenerated 事件测试
- [x] Subtask 3.8: 🟢 绿 — 实现工作流事件 + 更新 `config/event_channels.yaml` 映射
- [x] Subtask 3.9: 🔄 重构 — 更新 events `__init__.py`

#### DI 注册 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_workflow_engine.py`（端口注册/解析/兼容性测试失败） |
| 🟢 绿 | 更新 `src/composition_root.py`（注册 workflow_engine + orchestration_service） |
| 🔄 重构 | 验证完整注册链路 + 运行全量测试 |

- [x] Subtask 3.10: 🔴 红 — 编写 WorkflowEnginePort 契约失败测试
- [x] Subtask 3.11: 🟢 绿 — 更新 composition_root.py 注册 workflow 端口
- [x] Subtask 3.12: 🔄 重构 — 验证注册链路 + `test_composition_root_workflow.py`

**完成标准/Definition of Done:**
- [x] DocumentProcessingFlow 执行通过（mock 任务）
- [x] DocumentProcessed 事件发布验证
- [x] OrchestrationService 路由逻辑正确
- [x] RAGIndexed/ReportGenerated 事件定义 + `config/event_channels.yaml` 映射
- [x] Composition Root 注册完成
- [x] 契约测试通过
- [x] TDD 循环全部通过

---

### Task 4: SDD 架构约束验证测试 + 集成测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-8

#### SDD 架构约束验证测试

> **已有覆盖**：`test_hexagonal_architecture_constraints.py` 已将 `prefect` 列入 `FORBIDDEN_DOMAIN_IMPORTS`，`.importlinter` 已禁止 domain 层导入 prefect。本 Story 需新增的验证项如下。

- [x] Subtask 4.1: 创建 `tests/unit/architecture/test_prefect_architecture.py`
- [x] Subtask 4.2: 验证 infrastructure/workflow/ 以外零 Prefect 导入（复用 `_scan_file_imports()` 模式）
- [x] Subtask 4.3: 验证 WorkflowEnginePort 仅使用 stdlib 类型
- [x] Subtask 4.4: 验证 PrefectEngine 满足 WorkflowEnginePort Protocol（结构化子类型检查）
- [x] Subtask 4.5: 验证 OrchestrationService 不导入 infrastructure 层
- [x] Subtask 4.6: 验证 RAGIndexed/ReportGenerated 注册于 ChannelRouter（通过 `config/event_channels.yaml`）

#### 集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_story_1_18a_integration.py`（OrchestrationService → PrefectEngine → 事件发布端到端） |
| 🟢 绿 | 实现集成测试（mock Prefect SDK，真实 EventPublisher mock） |
| 🔄 重构 | 优化测试覆盖 |

- [x] Subtask 4.7: 🔴 红 — 编写集成测试失败测试
- [x] Subtask 4.8: 🟢 绿 — 实现端到端工作流流程测试
- [x] Subtask 4.9: 🔄 重构 — 优化测试覆盖

**完成标准/Definition of Done:**
- [x] 所有架构约束测试通过
- [x] 集成测试通过
- [x] `pytest tests/ -n 8` 并行测试通过
- [x] `ruff check src/` + `mypy src/` 通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) §3.2 ADR-002

- **架构模式:** 六边形架构 + 双核引擎架构（ADR-002）
- **ADR-002 核心设计:** Prefect 处理确定性数据管道，LangGraph 处理认知推理。OrchestrationService 协调两者，通过领域事件通信（无直接耦合）
- **技术栈:** Prefect 3.6.16+（已在 pyproject.toml 声明，锁定 3.6.25）
- **已有架构约束测试:** `test_hexagonal_architecture_constraints.py` 已将 `prefect` 列入 `FORBIDDEN_DOMAIN_IMPORTS`

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) §3.2 ADR-002

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **WorkflowEnginePort 位于 domain/ports/** | 引擎可替换，支持 LangGraph 并行 | 需依赖倒置 | ✅ 9/10 |
| WorkflowEnginePort 位于 application/ports/ | 实现简单 | 领域工作流概念泄漏到应用层 | 5/10 |
| 直接使用 Prefect 无端口抽象 | 最快实现 | 耦合 Prefect SDK，无法替换 | 3/10 |

### 双核引擎架构（ADR-002）说明

**来源:** architecture.md §3.2, lines 505-521

```python
# MVP (本 Story):
OrchestrationService.execute(task)
  if task.task_type == "data_pipeline":
      flow_run_id = await self.workflow_engine.submit_flow(task.flow_name, task.parameters)
      status = await self.workflow_engine.get_flow_status(flow_run_id)
      return WorkflowResult(flow_run_id=flow_run_id, status=status, submitted_at=datetime.now(timezone.utc))

# V1 (Story 1.18b 补充 — AgentEnginePort 尚不存在，此处仅为架构愿景):
OrchestrationService.execute(task)
  if task.task_type == "data_pipeline":
      flow_run_id = await self.workflow_engine.submit_flow(...)
      status = await self.workflow_engine.get_flow_status(flow_run_id)
      return WorkflowResult(flow_run_id=flow_run_id, status=status, submitted_at=datetime.now(timezone.utc))
  elif task.task_type == "agent_reasoning":
      return self.agent_engine.execute(...)
  else:
      data_result = self.workflow_engine.submit_flow(task.data_part)
      return self.agent_engine.execute(task.reasoning_part, context=data_result)
```

### Prefect 3.x API 注意事项

- Prefect 3.6.25 使用 `prefect.flow()` 和 `prefect.task()` 装饰器
- 状态查询通过 `prefect.client.orchestration.PrefectClient` 的 `read_flow_run()` 方法
- **Prefect 区分 state name（14+）和 state type（9）**：FlowStatus 映射到 state TYPE
- Prefect StateType 枚举（9个）：SCHEDULED, PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, CRASHED, PAUSED, CANCELLING
- State name → State type 映射（关键条目）：
  | State name | State type |
  |---|---|
  | Scheduled/Late/AwaitingConcurrencySlot/AwaitingRetry | SCHEDULED |
  | Pending | PENDING |
  | Running/Retrying | RUNNING |
  | Completed | COMPLETED |
  | Failed | FAILED |
  | Crashed | CRASHED |
  | Cancelled | CANCELLED |
  | Cancelling | CANCELLING |
  | Paused/Suspended | PAUSED |
- **`Retrying` 是 state NAME（type=RUNNING）**：task 级别 retry 期间状态为 Retrying，PrefectEngine 映射时 RUNNING → FlowStatus.RUNNING
- PrefectEngine 状态映射策略（基于 state TYPE）：
  - SCHEDULED/PENDING → FlowStatus.PENDING
  - RUNNING → FlowStatus.RUNNING
  - COMPLETED → FlowStatus.COMPLETED
  - FAILED（重试次数未耗尽）→ FlowStatus.RETRYING
  - FAILED（重试次数耗尽）→ FlowStatus.FAILED
  - **CANCELLED/CRASHED/CANCELLING/PAUSED → FlowStatus.FAILED**
- **映射设计依据**：
  - **业务抽象原则**：FlowStatus 是业务层状态抽象，不直接映射 Prefect 全部技术状态
  - **FAILED 包含"异常终止"语义**：CANCELLED（用户取消）、CRASHED（基础设施异常）、PAUSED（外部阻塞）均为"未正常完成"的异常终止场景
  - **PAUSED 特例**：如果业务需要区分"暂停等待审批"与"失败"，可扩展 FlowStatus 新增 PAUSED 状态，当前 Story 按 FAILED 处理
  - **CANCELLING 中间态**：短暂过渡态，映射为 FAILED 不影响业务判定
- `flow_run_id` 类型：Prefect 使用 `uuid.UUID`，WorkflowEnginePort 使用 `str`，PrefectEngine 负责 `str↔UUID` 转换
- **PrefectClient 是异步客户端**：通过 `async with get_client() as client:` 获取，不直接构造 `PrefectClient`
- **`create_flow_run()` 返回 `FlowRun` Pydantic 模型**（非 UUID），需通过 `.id` 获取 `flow_run_id`
- **外部触发使用 deployment 模式**：`read_deployment_by_name(name)` + `create_flow_run_from_deployment(deployment_id, parameters)`，`flow_name` 参数格式为 `<FLOW_NAME>/<DEPLOYMENT_NAME>`（如 `DocumentProcessing/default`）。直接使用 `create_flow_run()` 需要 `Flow` 运行时对象，仅适用于进程内调用
- **`DocumentProcessed.document_id` 类型为 `uuid.UUID`**（非 str），Flow 构造事件时需确保类型正确
- 测试中 mock `prefect` 模块：`@patch("src.infrastructure.workflow.prefect_engine.get_client")`

### PrefectEngine 架构设计依据

**1. 适配器模式（Adapter Pattern）**
- PrefectEngine 是 WorkflowEnginePort 的基础设施适配器，所有 Prefect SDK 导入限定于 `infrastructure/workflow/` 包内
- 替换为 LangGraph/Airflow 等引擎时，仅需新建适配器并修改 composition_root 注册，不触及 domain/application 层
- 参考：`src/infrastructure/messaging/` 下的 EventBus 适配器模式

**2. 构造函数注入策略**
- 注入 `PrefectConfig`（配置值）+ `EventPublisher`（端口），不注入 Prefect SDK 对象
- `EventPublisher` 注入使 PrefectEngine 在 Flow 完成后发布事件时解耦于具体 EventBus 实现
- domain 层不接受 infrastructure 配置对象（参考 UDMRouter 模式）

**3. SINGLETON 注册**
- PrefectEngine 无状态（无 request-scoped session），所有状态由 Prefect server 管理
- 与 UnifiedStorageGateway（SCOPED，持有 request-scoped AsyncSession）形成对比

**4. PrefectConfig 独立配置类**
- 遵循 AutoExecuteConfig 的 `@dataclass(frozen=True)` + `from_env()` 模式（注意：RedisConfig 使用 `@dataclass` 非 frozen）
- Prefect 连接参数（API URL、workspace 等）通过环境变量注入，支持多环境部署

**5. 测试隔离策略**
- Prefect SDK 全量 mock，不启动真实 Prefect server（参考 Story 1.14c 的 Mock SDK 策略）
- PrefectEngine 单元测试通过 `@patch` 替换 `prefect.client.orchestration.get_client`
- 集成测试验证 OrchestrationService → PrefectEngine → EventPublisher 完整链路（仍 mock Prefect SDK）

**6. Flow 与 Engine 职责分离**
- PrefectEngine 负责生命周期管理（提交、状态查询、事件发布）
- DocumentProcessingFlow（@flow）负责任务编排（解析→嵌入→索引的执行顺序和重试）
- Flow 内任务为 MVP 占位实现，真实业务逻辑由 Epic 2/3 故事补充

### DocumentProcessingFlow 数据流

```
submit_flow("DocumentProcessing", {"document_id": uuid, "file_path": "..."})
  ↓
DocumentProcessingFlow (@flow)
  ├── parse_document(document_id, file_path)  → ParseResult   (@task, retries=2)
  ├── generate_embedding(parse_result)         → EmbeddingResult (@task, retries=2)
  └── index_document(embedding_result)         → IndexResult    (@task, retries=2)
  ↓ 完成回调
EventPublisher.publish(DocumentProcessed)
  ↓
DualChannelEventBus → ChannelRouter(RELIABLE) → Outbox → RabbitMQ
```

> **注意**: Flow 内任务为 MVP 占位实现（返回 mock 数据），真实解析/嵌入/索引由 Epic 2/3 故事补充。本 Story 验证的是**编排架构**而非业务逻辑。

### MVP vs 完整版范围

| 组件 | MVP（本 Story） | 完整版 |
|------|----------------|--------|
| WorkflowEnginePort | ✅ 完整定义 | 同 |
| PrefectEngine | ✅ 完整实现 | 同 |
| DocumentProcessingFlow | ✅ 占位任务 | Epic 2/3 补充真实逻辑 |
| RAGPipelineFlow | ❌ 不实现 | Epic 2/3 |
| ReportGenerationFlow | ❌ 不实现 | Epic 6 |
| OrchestrationService | ✅ 仅 Prefect 路由 | Story 1.18b 补充 LangGraph |
| RAGIndexed 事件 | ✅ 定义（不实现 Flow） | Epic 2/3 实现生产者 |
| ReportGenerated 事件 | ✅ 定义（不实现 Flow） | Epic 6 实现生产者 |

### 项目结构说明

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   └── workflow_engine.py           # WorkflowEnginePort（新建）
│   │   ├── value_objects/
│   │   │   └── flow_status.py               # FlowStatus（新建）
│   │   └── events/
│   │       └── workflow_events.py           # RAGIndexed + ReportGenerated（新建）
│   ├── application/
│   │   └── services/
│   │       └── orchestration_service.py     # OrchestrationService（新建）
│   └── infrastructure/
│       ├── config/
│       │   └── prefect.py                   # PrefectConfig（新建）
│       └── workflow/
│           ├── __init__.py                  # 已有（更新导出）
│           ├── prefect_engine.py            # PrefectEngine（新建）
│           ├── flows/
│           │   ├── __init__.py              # 新建
│           │   └── document_processing_flow.py  # DocumentProcessingFlow（新建）
│           └── tasks/
│               ├── __init__.py              # 新建
│               └── document_tasks.py        # parse/embed/index tasks（新建）
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/test_workflow_engine.py
│   │   │   ├── value_objects/test_flow_status.py
│   │   │   └── events/test_workflow_events.py
│   │   ├── application/services/test_orchestration_service.py
│   │   ├── infrastructure/
│   │   │   ├── config/test_prefect_config.py
│   │   │   └── workflow/
│   │   │       ├── test_prefect_engine.py
│   │   │       └── test_document_processing_flow.py
│   │   ├── architecture/test_prefect_architecture.py
│   │   └── test_composition_root_workflow.py
│   ├── contracts/test_port_contract_workflow_engine.py
│   ├── integration/test_story_1_18a_integration.py
│   └── acceptance/
│       ├── test_story_1_18a.feature
│       └── test_story_1_18a_steps.py
```

### 六边形架构分层说明

| 层级 | 目录 | 组件 | 职责 |
|------|------|------|------|
| **Domain** | `domain/` | WorkflowEnginePort, FlowStatus, RAGIndexed, ReportGenerated | 核心端口/值对象/事件，零外部依赖 |
| **Application** | `application/` | OrchestrationService, WorkflowTask, WorkflowResult | 业务编排，接受端口注入 |
| **Infrastructure** | `infrastructure/` | PrefectEngine, PrefectConfig, DocumentProcessingFlow, document_tasks | Prefect SDK 封装 |

### 前一个故事学习经验

**来源:** [Story 1.17](./1-17-udmr-basic-routing.md) + [Story 1.14c](./1-14c-autonomous-invocation-execute.md)

1. **配置模式复用** — PrefectConfig 采用与 AutoExecuteConfig 相同的 `@dataclass(frozen=True)` + `from_env()` 模式（注意：RedisConfig 使用非 frozen `@dataclass`）
2. **事件驱动解耦** — PrefectEngine 仅通过注入的 EventPublisher 发布事件，不直接调用 domain services
3. **构造函数原始值注入** — 参考 UDMRouter 模式：domain 层不接受 infrastructure 配置对象，由 composition_root 传入
4. **Handler 桥接模式** — OrchestrationService 参考 AutoRouteHandler 的委托模式
5. **测试隔离** — BDD 步骤使用 `event_loop.run_until_complete()`，不用 `@pytest.mark.asyncio`
6. **Mock SDK 策略** — Prefect SDK 全量 mock，不依赖真实 Prefect server
7. **端口契约三位一体** — 每个端口必须同时有 contract test + registry + composition_root

**应用到本故事:**
- [ ] PrefectConfig 遵循 frozen dataclass + from_env() 模式
- [ ] PrefectEngine 通过构造函数注入 EventPublisher（不直接创建）
- [ ] OrchestrationService 注册为 SINGLETON（无状态路由服务，与 UnifiedStorageGateway SCOPED 不同：后者持有 request-scoped session，前者纯委托无状态）
- [ ] 测试使用 mock Prefect SDK，不启动真实 server
- [ ] OrchestrationService 不导入 infrastructure 层任何类
- [ ] 契约测试覆盖端口注册/解析/兼容性

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-19 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` §3.2 ADR-002 |
| **事件总线设计** | `docs/architecture/sisys-event-bus-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Story 模板** | `docs/developer/story-template.md` v2.7.0 |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` §3.2 ADR-002 提取
- [x] 现有代码继承已确认（EventPublisher/DomainEvent/ChannelRouter/PortRegistry）
- [x] 前一个故事学习经验已整合（Story 1.17 + 1.14c）
- [x] 状态将设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] ADR-002 双核引擎架构对齐
- [x] MVP 范围澄清（端口+引擎+1个Flow，非全部Flow）
- [x] Prefect 导入边界明确（仅 infrastructure/workflow/）
- [x] Prefect 3.x API 注意事项文档化

### 文件清单 File List

**待创建的文件/To Be Created (Dev Story 实施):**

领域层（Domain）:
- `src/domain/ports/workflow_engine.py` — WorkflowEnginePort Protocol
- `src/domain/value_objects/flow_status.py` — FlowStatus 值对象
- `src/domain/events/workflow_events.py` — RAGIndexed + ReportGenerated 事件

应用层（Application）:
- `src/application/services/orchestration_service.py` — OrchestrationService + WorkflowTask + WorkflowResult

基础设施层（Infrastructure）:
- `src/infrastructure/config/prefect.py` — PrefectConfig
- `src/infrastructure/workflow/prefect_engine.py` — PrefectEngine
- `src/infrastructure/workflow/flows/__init__.py` — Flows 包
- `src/infrastructure/workflow/flows/document_processing_flow.py` — DocumentProcessingFlow
- `src/infrastructure/workflow/tasks/__init__.py` — Tasks 包
- `src/infrastructure/workflow/tasks/document_tasks.py` — parse/embed/index tasks

测试文件:
- `tests/unit/domain/ports/test_workflow_engine.py`
- `tests/unit/domain/value_objects/test_flow_status.py`
- `tests/unit/domain/events/test_workflow_events.py`
- `tests/unit/infrastructure/config/test_prefect_config.py`
- `tests/unit/infrastructure/workflow/test_prefect_engine.py`
- `tests/unit/infrastructure/workflow/test_document_processing_flow.py`
- `tests/unit/application/services/test_orchestration_service.py`
- `tests/unit/test_composition_root_workflow.py`
- `tests/unit/architecture/test_prefect_architecture.py`
- `tests/contracts/test_port_contract_workflow_engine.py`
- `tests/integration/test_story_1_18a_integration.py`
- `tests/acceptance/test_story_1_18a.feature`
- `tests/acceptance/test_story_1_18a_steps.py`

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 WorkflowEnginePort
- `src/domain/value_objects/__init__.py` — 导出 FlowStatus
- `src/domain/events/__init__.py` — 导出 RAGIndexed, ReportGenerated
- `src/application/services/__init__.py` — 导出 OrchestrationService
- `src/infrastructure/workflow/__init__.py` — 导出 PrefectEngine
- `config/event_channels.yaml` — 新增 RAGIndexed/ReportGenerated 映射（DeliveryMode.RELIABLE）
- `src/composition_root.py` — 注册 workflow_engine + orchestration_service

**已有文件（复用，禁止修改）:**
- `src/domain/ports/event_publisher.py` — EventPublisher 端口
- `src/domain/events/base.py` — DomainEvent 基类
- `src/domain/events/document_events.py` — DocumentProcessed 事件
- `src/infrastructure/messaging/dual_channel_event_bus.py` — 双通道事件总线

---

## 📚 Project Context Reference

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **ADR-002** | 双核引擎：Prefect=数据管道，LangGraph=Agent推理 | architecture.md §3.2 |
| **Prefect 导入边界** | 所有 `import prefect` 限定于 `src/infrastructure/workflow/` | test_hexagonal_architecture_constraints.py |
| **测试覆盖率** | 架构层≥85%，集成测试≥70% | story-template.md |
| **Prefect 版本** | 3.6.16+（pyproject.toml 锁定 3.6.25） | pyproject.toml |

### 关键路径依赖

```
Story 1.1 (骨架) → Story 1.3 (事件总线) → Story 1.18a (Prefect 集成)
                                                  ↓
                                    Story 1.18b (LangGraph 集成)
                                                  ↓
                                    Epic 4 (工具箱) + Epic 6 (战略规划)
```

### Prefect vs LangGraph 职责分离

| 引擎 | 职责 | 处理类型 | Story |
|------|------|---------|-------|
| **Prefect** | 确定性数据管道 | 文档处理/RAG索引/报告生成 | **本 Story** |
| **LangGraph** | 认知推理 | BLM规划/Agent协作/多视角分析 | Story 1.18b |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.18a |
| **Story Key** | 1-18a-prefect-workflow-integration |
| **File** | `_bmad-output/implementation-artifacts/stories/1-18a-prefect-workflow-integration.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-18a（ARCH Prefect 数据管道） |
| **覆盖 FR** | FR-AR-02（事件发布至事件总线） |
| **依赖 Story** | Story 1.1（架构骨架）、Story 1.3（事件总线） |
| **前置条件** | 六边形架构骨架就绪、事件总线就绪、Prefect 3.6+ 依赖已声明 |
| **后续 Story** | Story 1.18b（LangGraph Agent 编排） |
| **覆盖率要求** | 架构层≥85%，集成测试≥70% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`
6. [x] ADR-002 双核引擎架构对齐
7. [x] MVP 范围澄清（端口+引擎+1 Flow，非全部 Flow）
8. [x] Prefect 导入边界明确
9. [x] 新事件定义（RAGIndexed/ReportGenerated）
10. [x] 端口契约治理完整（registry/composition_root/contract test）
11. [x] 文件命名符合 story-template.md 规范

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [ADR-002 双核引擎架构](../../_bmad-output/planning-artifacts/architecture.md) | architecture.md §3.2 |
| [事件总线设计文档](../../docs/architecture/sisys-event-bus-design.md) | 双通道事件总线详细设计 |
| [Story 1.17: UDMR 基础路由](./1-17-udmr-basic-routing.md) | 前一个 Story |
| [Story 1.18b: LangGraph Agent 编排](./1-18b-langgraph-agent-orchestration.md) | 后续 Story（依赖本 Story） |

---

**模板版本/Template Version:** 2.7.0
**创建日期/Created:** 2026-05-19
**最后更新/Last Updated:** 2026-05-20
**更新说明:** Round 5（最终轮）审查修正 — 补充 workflow __init__.py 导出、修正 Prefect Retrying 状态描述。5轮审查共修复 24 项问题（P0: 5项, P1: 12项, P2: 7项）。审查完成。

### 🔧 对抗性审查修复（Adversarial Review Fixes）

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| 1 | AC-5 ChannelRouter 事件注册方式错误（声称 DEFAULT_MAPPINGS 代码定义，实际为 event_channels.yaml YAML 配置） | P0 | AC-5 修正为 `config/event_channels.yaml` 注册，补充 EventBusConfigLoader 加载机制说明 | ✅ R1 |
| 2 | EventPublisher 不在 domain/ports/__init__.py __all__ 中，导入路径未明确 | P0 | 现有代码继承表补充导入路径 `src.domain.ports.event_publisher` 和 PublishResult 类型说明 | ✅ R1 |
| 3 | EventPublisher.publish() 返回 PublishResult（非 None），Story 未说明处理方式 | P0 | AC-3 补充 PublishResult 检查要求（is_full_failure 记录警告日志） | ✅ R1 |
| 4 | DocumentProcessed 事件已有完整定义（含 document_id/parse_result/embedding 字段），Story 未说明 Flow 完成后如何构造事件实例 | P0 | AC-3 补充事件构造时需传入的具体字段 | ✅ R1 |
| 5 | AC-5 验证标准残留 `ChannelRouter DEFAULT_MAPPINGS 更新` | P0 | 删除残留项，保留 `config/event_channels.yaml` 映射 | ✅ R2 |
| 6 | 现有代码继承表 PublishResult 重复出现（行60和66） | P1 | 删除重复条目，合并到 EventPublisher 行 | ✅ R2 |
| 7 | AC-4 Then 子句缺少 `submitted_at` 字段 | P1 | 补充 `submitted_at` 到 WorkflowResult 返回描述 | ✅ R2 |
| 8 | Dev Notes pseudocode 未构造 WorkflowResult | P1 | MVP/V1 pseudocode 补充 WorkflowResult 构造逻辑 | ✅ R2 |
| 9 | 集成测试覆盖率 70% vs 75% 矛盾（3处引用不一致） | P1 | 统一为 70%（对齐 story-template.md） | ✅ R2 |
| 10 | Subtask 3.8 描述错误（"ChannelRouter 映射"应为"event_channels.yaml 映射"） | P2 | 修正为"更新 `config/event_channels.yaml` 映射" | ✅ R2 |
| 11 | 文件清单错误列出 `channel_router.py`，缺少 `config/event_channels.yaml` | P0 | 替换为 `config/event_channels.yaml` | ✅ R2 |
| 12 | Task 0 AC 覆盖不完整（仅 AC-1, AC-5） | P1 | 扩展为 AC-1~AC-7 全覆盖 | ✅ R2 |
| 13 | 追溯矩阵缺少 `test_composition_root_workflow.py` 行 | P1 | 新增 AC-7 Composition Root 注册验证行，关联 Subtask 3.12 | ✅ R2 |
| 14 | Prefect StateType 有9个状态（含 SCHEDULED/CANCELLED/CRASHED/PAUSED/CANCELLING），Story 的 FlowStatus 仅5个且 RETRYING 不存在于 Prefect | P1 | Dev Notes 补充完整 9→5 状态映射策略，说明 RETRYING 由 PrefectEngine 综合判定、flow_run_id str↔UUID 转换 | ✅ R3 |
| 15 | Updated Files 缺少 `src/domain/value_objects/__init__.py`（FlowStatus 需导出） | P1 | 添加到 Updated Files 列表 | ✅ R3 |
| 16 | Updated Files 缺少 `src/application/services/__init__.py`（OrchestrationService 需导出） | P1 | 添加到 Updated Files 列表 | ✅ R3 |
| 17 | `test_composition_root_workflow.py` 在追溯矩阵和文件清单中但不在测试分类表中 | P1 | 测试分类表新增一行 | ✅ R3 |
| 18 | OrchestrationService 注册为 SINGLETON 缺少与 UnifiedStorageGateway(SCOPED) 的区别说明 | P2 | Dev Notes 补充 SINGLETON 理由（无状态路由服务 vs request-scoped session） | ✅ R3 |
| 19 | 应用到本故事条目中"测试使用 mock Prefect SDK"重复出现 | P2 | 删除重复行 | ✅ R3 |
| 20 | DI 注册子任务 3.10-3.12 缺少 TDD 循环表（仅有 checkbox） | P1 | 添加 TDD 循环表（红:契约测试→绿:composition_root→重构:链路验证），重新标注 subtask 阶段 | ✅ R4 |
| 21 | 追溯矩阵缺少 Task 0 行，验收测试文件无追溯 | P2 | 新增 Task 0 行，关联 `test_story_1_18a.feature` 和 `test_story_1_18a_steps.py` | ✅ R4 |
| 22 | Dev Notes 未说明 PrefectClient 异步获取模式（`get_client()` 而非直接构造）和 `create_flow_run()` 返回 `FlowRun` 模型 | P1 | 补充 PrefectClient 使用模式、`FlowRun.id` 获取方式、`DocumentProcessed.document_id` 为 UUID 类型 | ✅ R4 |
| 23 | Updated Files 缺少 `src/infrastructure/workflow/__init__.py`（需导出 PrefectEngine） | P1 | 添加到 Updated Files 列表 | ✅ R5 |
| 24 | "Prefect 无 RETRYING 状态"事实不准确（Prefect 有 Retrying 状态，主要用于 task 级别） | P2 | 修正为"Prefect Retrying 状态主要用于 task 级别，flow run 级别需综合判定" | ✅ R5 |
| 25 | Dev Notes 缺少 Prefect state name vs state type 区分说明（14+ state name → 9 state type），`Retrying` 是 name 而非 type | P1 | 新增 state name→state type 映射表，明确 FlowStatus 映射基于 state TYPE，`Retrying` 是 name（type=RUNNING） | ✅ R6 |
| 26 | PrefectEngine 状态映射策略缺少设计依据，CANCELLED/PAUSED 归为 FAILED 语义混淆 | P1 | 补充映射设计依据：业务抽象原则、FAILED 包含"异常终止"语义、PAUSED 特例说明、CANCELLING 中间态处理 | ✅ R6 |
| 27 | PrefectEngine 整体架构缺少设计依据章节（适配器模式、注入策略、SINGLETON 理由、Flow/Engine 职责分离等散落各处） | P1 | 新增"PrefectEngine 架构设计依据"章节，整合 6 项设计决策及其理由 | ✅ R6 |
| 28 | ChannelRouter "不是通过 DEFAULT_MAPPINGS 代码定义" 声明错误，实际代码中 DEFAULT_MAPPINGS 有 19 个硬编码条目，与 YAML 双轨并存 | P0 | 修正为"双轨注册机制：DEFAULT_MAPPINGS 为基线，YAML 追加/覆盖"，删除绝对否定表述 | ✅ R7 |
| 29 | PrefectConfig 模式参考引用 RedisConfig（非 frozen），但文档声称 frozen=True 模式，矛盾 | P1 | 修正参考为 AutoExecuteConfig（frozen=True），补充 RedisConfig 使用非 frozen 的说明 | ✅ R7 |
| 30 | PublishResult 缺少 `partial_error` 属性说明 | P2 | 补充 `partial_error` 属性到 PublishResult 描述 | ✅ R7 |
| 31 | PrefectConfig DI 注册模式未说明：Config 不注册为端口，需在 lambda 工厂中 `from_env()` 创建（参考 RedisManager/PostgreSQLManager 模式） | P0 | AC-7 补充 lambda 工厂注册格式示例，明确 PrefectConfig 不走 DI 容器 | ✅ R8 |
| 32 | FlowStatus 放在 value_objects/ 与 SagaStatus 放在 ports/ 不一致，缺少位置决策依据 | P1 | 值对象 Schema 补充位置决策说明（跨层共享 vs 端口附属） | ✅ R8 |
| 33 | WorkflowEnginePort Schema 缺少编码约定：`from __future__ import annotations` 和方法体用 `...` | P2 | 补充编码约定，与 EventPublisher/SagaStep 等端口一致 | ✅ R8 |
| 34 | 事件 Schema 中 event_type 声明方式不精确，缺少 `field(default=..., init=False)` 模式说明 | P1 | 修正为完整 `field(default="RAGIndexed", init=False)` 声明格式，与 DocumentProcessed 一致 | ✅ R8 |
| 35 | 架构测试未说明已有覆盖：test_hexagonal_architecture_constraints.py 已有 prefect 禁止导入，.importlinter 已配置 | P1 | Subtask 4.1 补充已有覆盖说明，明确需新增的验证项，引用 `_scan_file_imports()` 模式 | ✅ R9 |
| 36 | 伪代码 "V1 (Story 1.18b)" 引用 `self.agent_engine` 但 AgentEnginePort 不存在，易混淆 | P2 | 补充说明 "AgentEnginePort 尚不存在，此处仅为架构愿景" | ✅ R9 |
| 37 | AC-6 PrefectConfig 字段不完整（仅列 2 个，SDD Schema 定义 6 个），且引用 RedisConfig 而非 AutoExecuteConfig | P1 | 补充完整 6 个字段到 AC-6，修正引用为 AutoExecuteConfig | ✅ R10 |
