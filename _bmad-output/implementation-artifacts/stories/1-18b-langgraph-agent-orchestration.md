# Story 1.18b: LangGraph Agent 编排集成

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 集成 LangGraph 1.0+ 作为 Agent 编排引擎（端口抽象 + MVP 状态图）,
**So that** 系统支持认知密集型推理，包括 Agent 协作、Checkpoint 机制、与 Prefect 通过编排服务协调。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第四个故事。在 Story 1.18a（Prefect 工作流集成）完成后，集成 LangGraph 1.0+ Agent 编排引擎，完成双核引擎架构（ADR-002）的认知推理部分。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **AgentEnginePort 端口抽象** | 引擎可替换，支持未来其他 Agent 框架 | Protocol 定义于 domain 层，零外部依赖 |
| **LangGraphEngine 实现** | 认知密集型推理执行，状态图驱动 | 所有 langgraph 导入限定于 infrastructure/agent_orch/ |
| **BasicAgentGraph MVP** | 端到端验证编排架构：analyze→synthesize | Graph 完成后发布 AgentDecided 事件 |
| **OrchestrationService 扩展** | 应用层统一编排入口，支持双引擎路由 | 同时依赖 WorkflowEnginePort + AgentEnginePort |
| **Checkpoint 基础机制** | Agent 状态持久化，支持中断恢复 | LangGraph InMemorySaver 集成 |

> ⚠️ **MVP 范围澄清**：本 Story 仅实现 **AgentEnginePort 端口 + LangGraphEngine + BasicAgentGraph**。
> - BLM 六阶段状态图 → Epic 5/6 故事
> - BEM 六阶段状态图 → Epic 15 故事
> - 完整 Checkpoint 双模式恢复（Replay/Override）→ Story 6.6
> - SYS Agent 裁决 → Story 9.6
> - 多 Agent 协作图（collaboration_graph）→ Epic 9 故事

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1, 价值组 6, Story 1.18b

**架构决策追溯:** ADR-002 双核引擎架构（architecture.md §3.2）

**前置依赖:** Story 1.1（六边形架构骨架）、Story 1.3（事件总线实现）、Story 1.18a（Prefect 工作流集成）
**后续依赖:** Epic 4（工具箱）、Epic 5（Agent 协作）、Epic 6（战略规划）—— 均依赖本 Story 的 AgentEnginePort 和 LangGraphEngine

---

## 🔗 前置依赖与现有代码继承

### 依赖故事

| 故事 | 组件 | 用途 |
|------|------|------|
| Story 1.1 | 六边形架构骨架 | 架构分层、端口/适配器模式 |
| Story 1.3 | DualChannelEventBus + ChannelRouter | 事件发布/路由基础设施 |
| Story 1.18a | WorkflowEnginePort + PrefectEngine + OrchestrationService | 双核引擎数据管道部分 + 编排服务 |

### 现有代码继承（必须复用，禁止重复定义）

| 现有组件 | 文件路径 | 复用方式 |
|---------|---------|---------|
| `EventPublisher` 端口 | `src/domain/ports/event_publisher.py` | LangGraphEngine 注入，Graph 完成后发布事件（`async def publish(event: DomainEvent) -> PublishResult`，导入路径为 `src.domain.ports.event_publisher`） |
| `PublishResult` | `src/domain/events/publish_result.py` | 事件发布结果（frozen dataclass，含 `event_id`/`redis_success`/`outbox_saved`/`redis_error`/`outbox_error` 字段 + `is_success`/`is_full_failure`/`partial_error` 计算属性），LangGraphEngine 需检查 `is_full_failure` 并记录警告日志 |
| `DomainEvent` 基类 | `src/domain/events/base.py` | AgentDecided/CheckpointReached 继承 |
| `AgentDecided` 事件 | `src/domain/events/agent_events.py` | Graph 完成后发布（已有 agent_id, decision_result, confidence 字段） |
| `CheckpointReached` 事件 | `src/domain/events/checkpoint_events.py` | Checkpoint 节点发布（已有 checkpoint_id, phase_identifier, user_feedback_request 字段） |
| `FlowStatus` 值对象 | `src/domain/value_objects/flow_status.py` | AgentEnginePort 复用此枚举（PENDING/RUNNING/COMPLETED/FAILED/RETRYING） |
| `ChannelRouter` | `src/infrastructure/messaging/channel_router.py` | AgentDecided/CheckpointReached 已在 DEFAULT_MAPPINGS 注册（RELIABLE 通道） |
| `PortRegistry` + `register_port` | `src/domain/ports/registry.py` | 注册 AgentEnginePort |
| `OrchestrationService` | `src/application/services/orchestration_service.py` | 扩展 agent_reasoning 路由（第 82 行 `NotImplementedError` → 实际委托） |
| `WorkflowTask` / `WorkflowResult` | `src/application/services/orchestration_service.py` | 复用值对象（task_type 已包含 `"agent_reasoning"` Literal） |
| `Composition Root` | `src/composition_root.py` | DI 注册 agent 端口 + 更新编排服务注册 |
| `Agent` 实体 | `src/domain/entities/agent.py` | AgentRole/AgentStatus 枚举和状态机 |
| `PrefectConfig` 模式参考 | `src/infrastructure/config/prefect.py` | frozen dataclass + from_env() 模式参考 |

### 架构位置

```
用户操作/事件触发
       ↓
OrchestrationService (1.18a 创建, 1.18b 扩展) → 路由 task_type
       ↓ data_pipeline                    ↓ agent_reasoning
PrefectEngine (1.18a) → 包装 Prefect SDK  LangGraphEngine (1.18b) → 包装 LangGraph SDK
       ↓ submit_flow                      ↓ submit_graph
DocumentProcessingFlow (1.18a)            BasicAgentGraph (1.18b)
  ├── parse_document (@task)                ├── analyze (node)
  ├── generate_embedding (@task)            └── synthesize (node)
  └── index_document (@task)                      ↓ 完成
       ↓ 完成                              EventPublisher.publish(AgentDecided)
EventPublisher.publish(DocumentProcessed)        ↓
       ↓                                DualChannelEventBus → ChannelRouter(RELIABLE) → Outbox → RabbitMQ
DualChannelEventBus → Outbox/RabbitMQ
```

---

## ✅ Acceptance Criteria 验收标准

### AC-1: AgentEnginePort 端口定义

**Given** 六边形架构骨架已实现（Story 1.1），WorkflowEnginePort 已建立模式（Story 1.18a）
**When** 开发者需要执行 Agent 编排任务
**Then** `AgentEnginePort` Protocol 位于 `src/domain/ports/agent_engine.py`，使用 `@runtime_checkable`
**And** 定义 `async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str`
**And** 定义 `async def get_graph_status(self, graph_run_id: str) -> FlowStatus`
**And** 复用 `FlowStatus` 值对象（`src/domain/value_objects/flow_status.py`）
**And** 零外部依赖（无 langgraph/langchain/prefect 等导入）

**验证标准/Validation Criteria:**
- [ ] AgentEnginePort Protocol（`src/domain/ports/agent_engine.py`）
- [ ] `@runtime_checkable` 装饰器
- [ ] 仅使用 Python 标准库类型 + FlowStatus
- [ ] 文件首行 `from __future__ import annotations`

### AC-2: LangGraphConfig 配置

**Given** 现有配置模式（PrefectConfig.from_env()）
**When** LangGraphConfig 加载
**Then** 从环境变量读取，提供合理默认值
**And** `LANGGRAPH_API_URL` 默认 `"http://localhost:8000"`（LangGraph Studio/Cloud，MVP 不使用但预留）
**And** `LANGGRAPH_CHECKPOINT_TABLE` 默认 `"langgraph_checkpoints"`（MVP 未使用，为 Story 6.6 PostgreSQL Checkpointer 预留）
**And** `LANGGRAPH_RETRY_MAX_ATTEMPTS` 默认 `3`
**And** `LANGGRAPH_RETRY_DELAY_SECONDS` 默认 `30`（重试间隔，与 PrefectConfig 对称）
**And** `LANGGRAPH_TASK_TIMEOUT_SECONDS` 默认 `300`（节点级超时）
**And** `LANGGRAPH_GRAPH_TIMEOUT_SECONDS` 默认 `1800`（整体图超时，与 PrefectConfig.flow_timeout_seconds 对称）
**And** `@dataclass(frozen=True)` 不可变配置

**验证标准/Validation Criteria:**
- [ ] LangGraphConfig（`src/infrastructure/config/langgraph.py`）
- [ ] from_env() 类方法
- [ ] frozen=True dataclass
- [ ] 默认值与环境变量覆盖测试

### AC-3: LangGraphEngine 实现 AgentEnginePort

**Given** AgentEnginePort Protocol 已定义
**When** LangGraphEngine 使用 LangGraphConfig 实例化
**Then** LangGraphEngine 位于 `src/infrastructure/agent_orch/langgraph_engine.py`，满足 AgentEnginePort
**And** 所有 `import langgraph` / `from langgraph` 仅存在于 `src/infrastructure/agent_orch/`
**And** 架构约束测试确认 domain/application/interfaces 层零 langgraph 导入
**And** LangGraphEngine 通过注入的 EventPublisher 发布领域事件
**And** 构造函数注入 LangGraphConfig + EventPublisher（不注入 LangGraph SDK 对象）

**验证标准/Validation Criteria:**
- [ ] LangGraphEngine 类（`src/infrastructure/agent_orch/langgraph_engine.py`）
- [ ] isinstance(LangGraphEngine(...), AgentEnginePort) 返回 True
- [ ] 架构测试验证零越界导入
- [ ] EventPublisher 通过构造函数注入

### AC-4: BasicAgentGraph 执行

**Given** LangGraphEngine 已初始化
**When** 通过 `submit_graph("BasicAgent", {"agent_role": "CEO", "task_description": "..."})` 提交 Agent 任务
**Then** LangGraph StateGraph 执行：analyze → synthesize 作为顺序节点
**And** 成功完成后通过 EventPublisher 发布 `AgentDecided` 事件（构造时传入 `agent_id`、`decision_result`、`confidence` 字段）
**And** Agent 状态图执行延迟 P95 < 500ms（mock 节点，测量编排开销）
**And** 支持基础 Checkpoint（LangGraph InMemorySaver，`from langgraph.checkpoint.memory import InMemorySaver`，MVP 用内存实现）

**验证标准/Validation Criteria:**
- [ ] BasicAgentGraph（`src/infrastructure/agent_orch/graphs/basic_agent_graph.py`）
- [ ] agent_nodes（`src/infrastructure/agent_orch/nodes/agent_nodes.py`）
- [ ] EventPublisher.publish() 调用验证（mock）
- [ ] Checkpoint 保存/恢复验证
- [ ] 图执行状态可查询

> **⚠️ MVP 说明**: BasicAgentGraph 内节点为 MVP 占位实现（返回 mock 分析结果），真实 Agent 推理由 Epic 5/6 故事补充。本 Story 验证的是**编排架构**而非业务逻辑。

### AC-5: OrchestrationService 扩展

**Given** OrchestrationService 在应用层（Story 1.18a 创建）
**When** 提交 `WorkflowTask`（task_type="agent_reasoning"）
**Then** OrchestrationService 委托给 `AgentEnginePort`（通过构造函数注入）
**And** 返回 `WorkflowResult`（包含 flow_run_id、status、submitted_at）
**And** 构造函数从 `__init__(self, workflow_engine)` 扩展为 `__init__(self, workflow_engine, agent_engine)`
**And** 第 82 行 `NotImplementedError` 替换为实际 agent_reasoning 路由逻辑
**And** agent_reasoning 分支应包含参数校验：`graph_name` 不能为空（与 data_pipeline 的 `flow_name` 校验对称）

**验证标准/Validation Criteria:**
- [ ] OrchestrationService 构造函数新增 `agent_engine: AgentEnginePort` 参数
- [ ] `execute()` 方法 `agent_reasoning` 分支替换 `NotImplementedError`
- [ ] 仅依赖 AgentEnginePort 端口（不导入 infrastructure 层）
- [ ] `data_pipeline` 路由逻辑不变（回归测试）

### AC-6: Composition Root 注册

**Given** 现有 bootstrap() 模式（src/composition_root.py）
**When** 应用引导启动
**Then** `AgentEnginePort` 注册到 `LangGraphEngine` 实现
**And** `OrchestrationService` 注册更新为注入双引擎（workflow_engine + agent_engine）
**And** 端口契约测试验证注册/解析/兼容性

**验证标准/Validation Criteria:**
- [ ] composition_root.py 新增 agent_orch 注册段
- [ ] AgentEnginePort → LangGraphEngine（SINGLETON，lambda 工厂模式）
- [ ] OrchestrationService 注册更新为注入双引擎
- [ ] 契约测试（`tests/contracts/test_port_contract_agent_engine.py`）

> **DI 注册模式**：LangGraphConfig **不注册为端口**，在 lambda 工厂中通过 `LangGraphConfig.from_env()` 创建。注册格式参考 PrefectEngine：
> ```python
> register_port(
>     name="agent_engine",
>     version="v1.0.0",
>     interface=AgentEnginePort,
>     impl=lambda resolver: LangGraphEngine(
>         LangGraphConfig.from_env(),
>         resolver.resolve("event_publisher")
>     ),
>     module="src.infrastructure.agent_orch.langgraph_engine",
>     lifetime=Lifetime.SINGLETON,
> )
> ```

### AC-7: 架构约束验证

**Given** 现有六边形架构测试套件
**When** 架构测试运行
**Then** domain/application/interfaces 层零 `import langgraph`
**And** AgentEnginePort 仅使用 stdlib 类型
**And** OrchestrationService 不导入 infrastructure 层
**And** LangGraphEngine 满足 AgentEnginePort Protocol（结构化子类型检查）

**验证标准/Validation Criteria:**
- [ ] `tests/unit/architecture/test_langgraph_architecture.py`
- [ ] 零越界 LangGraph 导入验证
- [ ] 端口类型纯度验证
- [ ] Protocol 一致性验证

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 `docs/developer/sdd-tdd-checklist.md` 和 `docs/developer/sdd-tdd-fusion-guide.md`（项目全局文档）。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域端口 Schema (Domain Ports)
- [ ] AgentEnginePort 端口（`src/domain/ports/agent_engine.py`）
  - `async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str` — 提交 Agent 状态图执行，返回 graph_run_id
  - `async def get_graph_status(self, graph_run_id: str) -> FlowStatus` — 查询状态图执行状态
  - Protocol + `@runtime_checkable`
  - > **六边形架构约束**：AgentEnginePort 仅使用 Python 标准库类型，不导入 langgraph/langchain
  - > **编码约定**：文件首行 `from __future__ import annotations`，Protocol 方法体统一用 `...`
  - > **设计决策说明**：AgentEnginePort 不复用 WorkflowEnginePort，因为（1）LangGraph 执行模型与 Prefect 不同（StateGraph vs Flow）；（2）未来可能需要 interrupt/resume graph 等额外方法；（3）架构文档 ADR-002 明确展示两个独立引擎

#### 配置模型 (Configuration Models)
- [ ] LangGraphConfig 配置（`src/infrastructure/config/langgraph.py`）
  - `@dataclass(frozen=True)` — 不可变配置
  - api_url: str（LANGGRAPH_API_URL，默认 `"http://localhost:8000"`）
  - checkpoint_table: str（LANGGRAPH_CHECKPOINT_TABLE，默认 `"langgraph_checkpoints"`，MVP 未使用，Story 6.6 预留）
  - retry_max_attempts: int（LANGGRAPH_RETRY_MAX_ATTEMPTS，默认 3）
  - retry_delay_seconds: int（LANGGRAPH_RETRY_DELAY_SECONDS，默认 30）
  - task_timeout_seconds: int（LANGGRAPH_TASK_TIMEOUT_SECONDS，默认 300）
  - graph_timeout_seconds: int（LANGGRAPH_GRAPH_TIMEOUT_SECONDS，默认 1800）
  - from_env() 类方法

#### 基础设施适配器 Schema (Infrastructure Adapters)
- [ ] LangGraphEngine（`src/infrastructure/agent_orch/langgraph_engine.py`）
  - 实现 AgentEnginePort Protocol
  - 构造函数注入：LangGraphConfig, EventPublisher
  - submit_graph(): 执行编译后的 LangGraph StateGraph，返回 graph_run_id
  - get_graph_status(): 查询图执行状态，映射为 FlowStatus
  - **InMemorySaver 生命周期**：作为 LangGraphEngine 实例属性（构造函数创建一次，跨 submit_graph 调用共享）
  - **Graph 编译缓存**：维护 `graph_name -> CompiledGraph` 映射 + `graph_run_id -> graph_name` 映射（支持 get_graph_status 反查）
  - **MVP 阻塞语义**：submit_graph() 内部 await compiled.ainvoke()，阻塞直到完成；因此 get_graph_status() 在 MVP 中仅返回 COMPLETED 或 FAILED，RUNNING/PENDING 在本地模式下不可观察
- [ ] BasicAgentGraph（`src/infrastructure/agent_orch/graphs/basic_agent_graph.py`）
  - LangGraph StateGraph 定义
  - 状态 Schema: `BasicAgentState` TypedDict（定义于 `agent_orch/schemas.py`，含 task_description, agent_role, analysis_result, synthesis_result）
  - 顺序执行：analyze → synthesize
  - 完成回调：通过 EventPublisher 发布 AgentDecided 事件
- [ ] agent_nodes（`src/infrastructure/agent_orch/nodes/agent_nodes.py`）
  - analyze(state) — 分析节点（MVP 占位，返回 mock 分析结果）
  - synthesize(state) — 综合节点（MVP 占位，返回 mock 综合结果）
- [ ] schemas（`src/infrastructure/agent_orch/schemas.py`）
  - BasicAgentState TypedDict — task_description: str, agent_role: str, analysis_result: str, synthesis_result: str
  - 无外部依赖（仅 typing.TypedDict）

#### 应用层 Schema (Application Services)
- [ ] OrchestrationService 扩展（`src/application/services/orchestration_service.py`）
  - 构造函数新增：`agent_engine: AgentEnginePort` 参数
  - `execute()` 中 `agent_reasoning` 分支替换 `NotImplementedError`
  - 仅依赖端口接口（不导入 infrastructure 层）
  - 新增 `TYPE_CHECKING` 块导入 `AgentEnginePort`（参考现有 WorkflowEnginePort 导入模式，第21-22行）
  - 更新 `composition_root.py` 第861-872行 `orchestration_service` 注册（当前 interface=OrchestrationService 类本身，lambda 工厂需新增 `resolver.resolve("agent_engine")` 参数）

#### 统一端口注册与接口治理
- [ ] 端口注册：composition_root.py 新增 agent_engine 注册
- [ ] 端口更新：composition_root.py 更新 orchestration_service 注册（注入双引擎）
- [ ] 契约测试：tests/contracts/test_port_contract_agent_engine.py
- [ ] 端口版本：v1.0.0，owner=platform

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1_18b.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_story_1_18b_steps.py`
- [ ] 覆盖场景：
  - LangGraphEngine 创建与配置
  - BasicAgentGraph 提交与执行
  - Agent 图完成 → AgentDecided 事件发布
  - OrchestrationService 路由 agent_reasoning 任务
  - OrchestrationService 路由 data_pipeline 任务（回归验证）
  - 双引擎协调（data_pipeline + agent_reasoning 分别路由）
  - LangGraphConfig 环境变量覆盖

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
| **TDD 单元测试** | AgentEnginePort | Protocol 签名 | `test_agent_engine.py` | Task 1 |
| **TDD 单元测试** | LangGraphConfig | from_env() + 默认值 | `test_langgraph_config.py` | Task 2 |
| **TDD 单元测试** | LangGraphEngine | submit_graph/get_graph_status | `test_langgraph_engine.py` | Task 2 |
| **TDD 单元测试** | BasicAgentGraph | 图执行 + 事件发布 | `test_basic_agent_graph.py` | Task 3 |
| **TDD 单元测试** | OrchestrationService | 双引擎路由 | `test_orchestration_service.py` | Task 3（更新现有测试） |
| **TDD 单元测试** | Composition Root | agent 注册链路 | `test_composition_root_agent.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1_18b.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_story_1_18b_steps.py` | Task 0 |
| **TDD 契约测试** | AgentEnginePort | 端口注册/解析/兼容性 | `test_port_contract_agent_engine.py` | Task 3 |
| **SDD 架构验证** | 六边形约束 | 零越界 LangGraph 导入 | `test_langgraph_architecture.py` | Task 4 |
| **集成测试** | 端到端流程 | OrchestrationService → LangGraphEngine → 事件发布 | `test_story_1_18b_integration.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **架构层覆盖率 ≥85%**（架构层 Story，含 Agent 编排核心机制）
- [ ] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：** 测试必须自包含（Self-contained），不依赖真实 LangGraph server。

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **LangGraph 隔离** | 所有 LangGraph SDK 调用使用 mock（unittest.mock.AsyncMock） | 测试依赖真实 server，CI 失败 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **BDD async 配合** | BDD 步骤函数使用 `event_loop.run_until_complete()`，不使用 `@pytest.mark.asyncio` | context 数据丢失 |
| **EventPublisher mock** | 事件发布使用 AsyncMock，验证调用参数 | 测试耦合真实事件总线 |

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| 全部 | SDD 规范定义 + Gherkin 验收 | Task 0 | 0.1-0.8（规范定义+红阶段验证） | `test_story_1_18b.feature`, `test_story_1_18b_steps.py` |
| AC-1 | AgentEnginePort Protocol | Task 1 | 1.1-1.3（Protocol 红→绿→重构） | `test_agent_engine.py` |
| AC-2 | LangGraphConfig | Task 2 | 2.1-2.3（Config 红→绿→重构） | `test_langgraph_config.py` |
| AC-3 | LangGraphEngine 实现 | Task 2 | 2.4-2.6（Engine 红→绿→重构） | `test_langgraph_engine.py` |
| AC-4 | BasicAgentGraph | Task 3 | 3.1-3.3（Graph 红→绿→重构，含事件发布验证） | `test_basic_agent_graph.py` |
| AC-4 | 事件发布验证 | Task 3 | 3.1-3.3（Graph 测试内验证 EventPublisher.publish 调用） | `test_basic_agent_graph.py` |
| AC-5 | OrchestrationService 扩展 | Task 3 | 3.4-3.6（双引擎路由 红→绿→重构） | `test_orchestration_service.py` |
| AC-6 | Composition Root 注册 | Task 3 | 3.7-3.9（端口注册+契约测试） | `test_port_contract_agent_engine.py` |
| AC-6 | 端口契约测试 | Task 3 | 3.8（契约测试） | `test_port_contract_agent_engine.py` |
| AC-6 | Composition Root 注册验证 | Task 3 | 3.9（注册链路验证） | `test_composition_root_agent.py` |
| AC-7 | 架构约束验证 | Task 4 | 4.1-4.6 | `test_langgraph_architecture.py` |
| 全部 | 集成测试 | Task 4 | 4.7-4.9（端到端流程） | `test_story_1_18b_integration.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确端口、配置、验收标准。

- [ ] Subtask 0.1: 定义 AgentEnginePort Protocol Schema（`src/domain/ports/agent_engine.py`）
- [ ] Subtask 0.2: 定义 LangGraphConfig 配置 Schema（`src/infrastructure/config/langgraph.py`）
- [ ] Subtask 0.3: 定义 LangGraphEngine 适配器 Schema
- [ ] Subtask 0.4: 定义 BasicAgentGraph + agent_nodes Schema
- [ ] Subtask 0.5: 定义 OrchestrationService 扩展 Schema
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1_18b.feature`
- [ ] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_story_1_18b_steps.py`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] Gherkin 验收测试运行失败（红阶段确认）
- [ ] 端口契约清单完整（registry/composition_root/contract test）

---

### Task 1: AgentEnginePort Protocol

**关联 AC:** AC-1

#### TDD 循环 [A]：AgentEnginePort Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_agent_engine.py`（验证 runtime_checkable、方法签名、FlowStatus 返回类型、零外部依赖） |
| 🟢 绿 | 实现 `src/domain/ports/agent_engine.py` — AgentEnginePort Protocol |
| 🔄 重构 | 注册到 `src/domain/ports/__init__.py` |

- [ ] Subtask 1.1: 🔴 红 — 编写 AgentEnginePort 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 AgentEnginePort Protocol
- [ ] Subtask 1.3: 🔄 重构 — 更新 `__init__.py` 导出

**完成标准/Definition of Done:**
- [ ] AgentEnginePort 实现完成
- [ ] 零外部依赖（stdlib-only + FlowStatus）
- [ ] TDD 循环全部通过

---

### Task 2: LangGraphConfig + LangGraphEngine

**关联 AC:** AC-2, AC-3

#### TDD 循环 [A]：LangGraphConfig

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/config/test_langgraph_config.py`（验证 from_env()、默认值、环境变量覆盖） |
| 🟢 绿 | 实现 `src/infrastructure/config/langgraph.py` — LangGraphConfig |
| 🔄 重构 | 对齐 PrefectConfig from_env() 模式 |

- [ ] Subtask 2.1: 🔴 红 — 编写 LangGraphConfig 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 LangGraphConfig（frozen=True, from_env()）
- [ ] Subtask 2.3: 🔄 重构 — 对齐配置模式

#### TDD 循环 [B]：LangGraphEngine

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/agent_orch/test_langgraph_engine.py`（mock LangGraph SDK，验证 submit_graph/get_graph_status，AgentEnginePort 一致性） |
| 🟢 绿 | 实现 `src/infrastructure/agent_orch/langgraph_engine.py` — LangGraphEngine |
| 🔄 重构 | 优化错误处理和日志 |

- [ ] Subtask 2.4: 🔴 红 — 编写 LangGraphEngine 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 LangGraphEngine（mock LangGraph SDK 调用）
- [ ] Subtask 2.6: 🔄 重构 — 优化状态映射和错误处理

> **关键约束**：LangGraphEngine 测试全量 mock LangGraph SDK，不启动真实 LangGraph server。使用 `unittest.mock.patch` 替换 `langgraph` 模块调用。

**完成标准/Definition of Done:**
- [ ] LangGraphConfig from_env() 正确解析
- [ ] LangGraphEngine 满足 AgentEnginePort
- [ ] 所有 LangGraph 导入限定于 infrastructure/agent_orch/
- [ ] TDD 循环全部通过

---

### Task 3: BasicAgentGraph + OrchestrationService 扩展 + DI 注册

**关联 AC:** AC-4, AC-5, AC-6

#### TDD 循环 [A]：BasicAgentGraph

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/agent_orch/test_basic_agent_graph.py`（验证图定义、节点执行顺序、事件发布） |
| 🟢 绿 | 实现 `src/infrastructure/agent_orch/graphs/basic_agent_graph.py` + `nodes/agent_nodes.py` |
| 🔄 重构 | 提取可复用节点模式 |

- [ ] Subtask 3.1: 🔴 红 — 编写 BasicAgentGraph 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 Graph（StateGraph + nodes）
- [ ] Subtask 3.3: 🔄 重构 — 优化节点模块

#### TDD 循环 [B]：OrchestrationService 扩展

> **⚠️ 现有测试影响分析**：`tests/unit/application/services/test_orchestration_service.py` 当前包含 9 个测试方法，添加 `agent_engine` 参数后以下测试需更新：
> - `TestOrchestrationServiceProtocolCompliance.test_only_depends_on_workflow_engine_port` — AST 检查需扩展
> - `TestOrchestrationServiceExecute` 全部 4 个测试 — 构造函数调用需添加 `mock_agent_engine` 参数
> - `TestOrchestrationServiceValidation` 全部 2 个测试 — 同上
> - `test_execute_agent_reasoning_raises_not_implemented` — 替换为 agent_reasoning 路由测试
>
> 另需更新 `tests/integration/test_story_1_18a_integration.py` 中 `test_data_pipeline_full_chain` 的构造调用。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_orchestration_service.py` 新增测试（验证 agent_reasoning 路由到 AgentEnginePort、双引擎协调、data_pipeline 回归） |
| 🟢 绿 | 修改 `src/application/services/orchestration_service.py`（新增 agent_engine 参数，替换 NotImplementedError） |
| 🔄 重构 | 优化路由逻辑和类型注解 |

- [ ] Subtask 3.4: 🔴 红 — 编写 OrchestrationService 扩展失败测试
- [ ] Subtask 3.5: 🟢 绿 — 扩展 OrchestrationService（注入 AgentEnginePort）
- [ ] Subtask 3.6: 🔄 重构 — 优化双引擎路由逻辑

#### DI 注册 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_agent_engine.py`（端口注册/解析/兼容性测试失败） |
| 🟢 绿 | 更新 `src/composition_root.py`（注册 agent_engine + 更新 orchestration_service） |
| 🔄 重构 | 验证完整注册链路 + 运行全量测试 |

- [ ] Subtask 3.7: 🔴 红 — 编写 AgentEnginePort 契约失败测试
- [ ] Subtask 3.8: 🟢 绿 — 更新 composition_root.py 注册 agent 端口
- [ ] Subtask 3.9: 🔄 重构 — 验证注册链路 + `test_composition_root_agent.py`

**完成标准/Definition of Done:**
- [ ] BasicAgentGraph 执行通过（mock 节点）
- [ ] AgentDecided 事件发布验证
- [ ] OrchestrationService 双引擎路由正确
- [ ] data_pipeline 路由回归测试通过
- [ ] Composition Root 注册完成
- [ ] 契约测试通过
- [ ] TDD 循环全部通过

---

### Task 4: SDD 架构约束验证测试 + 集成测试

**关联 AC:** AC-1, AC-3, AC-4, AC-5, AC-7

#### SDD 架构约束验证测试

> **已有覆盖**：`test_hexagonal_architecture_constraints.py` 已将 `langgraph` 列入 `FORBIDDEN_DOMAIN_IMPORTS`，`.importlinter` 已禁止 domain 层导入 langgraph。本 Story 需新增的验证项如下。

- [ ] Subtask 4.1: 创建 `tests/unit/architecture/test_langgraph_architecture.py`
- [ ] Subtask 4.2: 验证 infrastructure/agent_orch/ 以外零 LangGraph 导入（复用 `_scan_file_imports()` 模式）
- [ ] Subtask 4.3: 验证 AgentEnginePort 仅使用 stdlib 类型
- [ ] Subtask 4.4: 验证 LangGraphEngine 满足 AgentEnginePort Protocol（结构化子类型检查）
- [ ] Subtask 4.5: 验证 OrchestrationService 不导入 infrastructure 层
- [ ] Subtask 4.6: 验证 BasicAgentGraph 使用 AgentDecided 事件（已注册于 ChannelRouter DEFAULT_MAPPINGS）

#### 集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_story_1_18b_integration.py`（OrchestrationService → LangGraphEngine → 事件发布端到端） |
| 🟢 绿 | 实现集成测试（mock LangGraph SDK，真实 EventPublisher mock） |
| 🔄 重构 | 优化测试覆盖 |

- [ ] Subtask 4.7: 🔴 红 — 编写集成测试失败测试
- [ ] Subtask 4.8: 🟢 绿 — 实现端到端 Agent 编排流程测试
- [ ] Subtask 4.9: 🔄 重构 — 优化测试覆盖

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] `pytest tests/ -n 8` 并行测试通过
- [ ] `ruff check src/` + `mypy src/` 通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md) §3.2 ADR-002

- **架构模式:** 六边形架构 + 双核引擎架构（ADR-002）
- **ADR-002 核心设计:** Prefect 处理确定性数据管道，LangGraph 处理 Agent 认知推理。OrchestrationService 协调两者，通过领域事件通信（无直接耦合）
- **技术栈:** LangGraph 1.0+（已在 pyproject.toml 声明 `langgraph = "^1.0.0"`）
- **已有架构约束测试:** `test_hexagonal_architecture_constraints.py` 已将 `langgraph` 列入 `FORBIDDEN_DOMAIN_IMPORTS`

### 关键架构决策

**来源:** [`architecture.md`](../../docs/architecture/architecture.md) §3.2 ADR-002

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **新建 AgentEnginePort** | 引擎独立演化，支持 LangGraph 特有方法 | 多一个端口需维护 | ✅ 9/10 |
| 复用 WorkflowEnginePort | 减少代码量 | LangGraph 执行模型不同，接口牵强 | 5/10 |
| 直接使用 LangGraph 无端口抽象 | 最快实现 | 耦合 SDK，无法替换 | 3/10 |

### LangGraph 1.0 API 注意事项

**来源:** LangGraph 官方文档 https://docs.langchain.com/oss/python/langgraph/graph-api 和 https://docs.langchain.com/oss/python/langgraph/functional-api

#### Graph API（StateGraph 模式）

- **核心概念**：`StateGraph(state_schema)` 创建状态图，`add_node()` 添加节点，`add_edge()` 添加边
- **入口/出口**：`graph.add_edge(START, "first_node")` + `graph.add_edge("last_node", END)`（`START`/`END` 从 `langgraph.graph` 导入）
- **编译执行**：`compiled = graph.compile(checkpointer=InMemorySaver())` → `result = await compiled.ainvoke(state, config)`
- **状态 Schema**：使用 `TypedDict` 定义，节点返回 `dict` 更新状态
- **Checkpoint**：`from langgraph.checkpoint.memory import InMemorySaver`（注意：不是 `MemorySaver`）
- **线程隔离**：通过 `config={"configurable": {"thread_id": "unique_id"}}` 实现并发隔离
- **状态查询**：`compiled.get_state(config)` 获取当前状态

#### Functional API（@entrypoint/@task 模式）

- **装饰器模式**：`@entrypoint` 定义入口函数，`@task` 定义子任务
- **适用场景**：简单 DAG 流程，无需复杂状态图
- **状态管理**：通过函数参数/返回值传递，不使用 StateGraph

#### Node 函数签名

```python
def node_function(state: StateSchema, config: RunnableConfig) -> dict | Command:
    """节点函数接受两个参数：
    - state: 当前状态（TypedDict）
    - config: RunnableConfig，含 configurable 参数（如 thread_id）
    返回：状态更新 dict 或 Command 对象（组合状态更新+路由）
    """
    return {"analysis_result": "..."}  # 或 Command(update={"result": "...}, goto="next_node")
```

#### Command 原语（v1.0+）

- **用途**：组合状态更新 + 路由决策，替代简单的 dict 返回
- **语法**：`Command(update={"field": "value"}, goto="target_node")`
- **场景**：条件路由（如 if/else 分支）或同时更新状态并指定下一节点

#### 其他重要参数

- **递归限制**：默认 1000 步（v1.0.6+），防止无限循环
- **Runtime 对象**（Functional API）：提供 `context`、`store`、`execution_info`

#### 状态映射策略（LangGraph → FlowStatus）

LangGraph 没有与 Prefect 等价的复杂状态枚举（9种 StateType），执行结果只有成功/失败：

| LangGraph 状态 | FlowStatus 映射 |
|----------------|-----------------|
| 图正在执行中 | `FlowStatus.RUNNING` |
| 图正常完成 | `FlowStatus.COMPLETED` |
| 图执行异常 | `FlowStatus.FAILED` |
| 未开始 | `FlowStatus.PENDING` |
| 需重试（超时等） | `FlowStatus.RETRYING` |

#### MVP 实现策略

- **本地执行模式**：使用 `graph.compile().ainvoke()`，不使用 LangGraph Platform/Cloud API
- **graph_run_id 生成**：使用 `uuid.uuid4()` 生成，通过 `config.thread_id` 传入 LangGraph 用于状态追踪

### AgentEnginePort vs WorkflowEnginePort 设计说明

**来源:** architecture.md §3.2, Story 1.18a Dev Notes

```
# 当前 (Story 1.18a):
OrchestrationService.__init__(workflow_engine)
  execute(task):
    if data_pipeline → workflow_engine.submit_flow(...)

# 本 Story 扩展后 (Story 1.18b):
OrchestrationService.__init__(workflow_engine, agent_engine)
  execute(task):
    if data_pipeline    → workflow_engine.submit_flow(...)
    if agent_reasoning  → agent_engine.submit_graph(...)
```

### LangGraphEngine 架构设计依据

**1. 适配器模式（Adapter Pattern）**
- LangGraphEngine 是 AgentEnginePort 的基础设施适配器，所有 LangGraph SDK 导入限定于 `infrastructure/agent_orch/` 包内
- 替换为 AutoGen/CrewAI 等引擎时，仅需新建适配器并修改 composition_root 注册

**2. 构造函数注入策略**
- 注入 `LangGraphConfig`（配置值）+ `EventPublisher`（端口），不注入 LangGraph SDK 对象
- domain 层不接受 infrastructure 配置对象（参考 PrefectEngine 模式）

**3. SINGLETON 注册**
- LangGraphEngine 无状态，所有状态由 LangGraph 内部 InMemorySaver 管理
- 与 PrefectEngine 一致

**4. 本地执行模式**
- MVP 使用 `graph.compile().ainvoke()` 本地执行，不依赖外部 LangGraph Server
- 未来可切换到 LangGraph Platform API（仅修改 LangGraphEngine 内部实现）

**5. LangGraphConfig 独立配置类**
- LangGraphConfig 定义于 `infrastructure/config/` 而非 LangGraphEngine 内部，参考 PrefectConfig 模式
- 配置对象在 lambda 工厂中通过 `LangGraphConfig.from_env()` 创建，不注册为端口

**6. 测试隔离策略**
- 所有 LangGraph SDK 调用使用 `unittest.mock.AsyncMock`，不启动真实 LangGraph server
- BasicAgentGraph 测试不依赖 InMemorySaver 的真实行为（mock `graph.compile()` 返回值）

**7. Graph 与 Engine 职责分离**
- LangGraphEngine 负责：生命周期管理（submit/get_status）、事件发布、状态映射
- BasicAgentGraph 负责：图结构定义（StateGraph + nodes + edges）
- schemas.py 负责：状态 TypedDict 定义（供 Engine 和 Graph 共享）
- agent_nodes.py 负责：纯函数节点实现（不持有状态，不发布事件）

**8. EventPublisher 使用差异（LangGraphEngine vs PrefectEngine）**
- PrefectEngine 注入 EventPublisher 但当前未调用（Deployment 远程模式，Flow 内部由 DocumentProcessingFlow 发布事件）
- LangGraphEngine 必须在 `submit_graph()` 完成后主动调用 `EventPublisher.publish(AgentDecided(...))`（本地 `ainvoke()` 模式，引擎可直接发布）
- 发布后需检查 `result.is_full_failure` 并记录警告日志（参考 `document_processing_flow.py` 第62行模式）

### BasicAgentGraph 数据流

```
submit_graph("BasicAgent", {"agent_role": "CEO", "task_description": "分析市场趋势"})
  ↓
LangGraphEngine.submit_graph()
  ↓ 生成 graph_run_id (UUID)
  ↓ 获取或创建 BasicAgentGraph compiled instance
  ↓ compiled.ainvoke({"task_description": "...", "agent_role": "CEO", ...}, config={"configurable": {"thread_id": graph_run_id}})
  ↓
BasicAgentGraph (StateGraph)
  ├── analyze(state)  → {"analysis_result": "..."}   (node, MVP mock)
  └── synthesize(state) → {"synthesis_result": "..."} (node, MVP mock)
  ↓ 完成回调
EventPublisher.publish(AgentDecided(agent_id=uuid.UUID(...), decision_result={...}, confidence=0.9))
  ↓
DualChannelEventBus → ChannelRouter(RELIABLE) → Outbox → RabbitMQ
```

> **注意**: Graph 内节点为 MVP 占位实现（返回 mock 分析/综合结果），真实 Agent 推理由 Epic 5/6 故事补充。

### MVP vs 完整版范围

| 组件 | MVP（本 Story） | 完整版 |
|------|----------------|--------|
| AgentEnginePort | ✅ 完整定义 | 同 |
| LangGraphEngine | ✅ 完整实现 | 同 |
| BasicAgentGraph | ✅ 2节点 mock 图 | Epic 5/6 补充真实推理 |
| BLM 六阶段状态图 | ❌ 不实现 | Epic 5/6 |
| BEM 六阶段状态图 | ❌ 不实现 | Epic 15 |
| 多 Agent 协作图 | ❌ 不实现 | Epic 9 |
| Checkpoint 双模式恢复 | ❌ 仅 InMemorySaver | Story 6.6（Replay/Override） |
| OrchestrationService | ✅ 双引擎路由 | 同 |
| SYS Agent 裁决 | ❌ 不实现 | Story 9.6 |
| CheckpointReached 事件 | ✅ 定义（Graph 可选发布） | Story 6.3 完整实现 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── workflow_engine.py           # WorkflowEnginePort（Story 1.18a，已存在）
│   │   │   └── agent_engine.py              # AgentEnginePort（新建）
│   │   └── events/
│   │       ├── agent_events.py              # AgentDecided（已存在，复用）
│   │       └── checkpoint_events.py         # CheckpointReached（已存在，复用）
│   ├── application/
│   │   └── services/
│   │       └── orchestration_service.py     # OrchestrationService（更新：双引擎）
│   └── infrastructure/
│       ├── config/
│       │   ├── prefect.py                   # PrefectConfig（Story 1.18a，已存在）
│       │   └── langgraph.py                 # LangGraphConfig（新建）
│       └── agent_orch/                      # Agent 编排引擎（新建目录）
│           ├── __init__.py
│           ├── schemas.py                   # BasicAgentState TypedDict（新建）
│           ├── langgraph_engine.py          # LangGraphEngine（新建）
│           ├── graphs/
│           │   ├── __init__.py
│           │   └── basic_agent_graph.py     # BasicAgentGraph（新建）
│           └── nodes/
│               ├── __init__.py
│               └── agent_nodes.py           # analyze/synthesize nodes（新建）
├── tests/
│   ├── unit/
│   │   ├── domain/ports/test_agent_engine.py
│   │   ├── infrastructure/
│   │   │   ├── config/test_langgraph_config.py
│   │   │   └── agent_orch/
│   │   │       ├── test_langgraph_engine.py
│   │   │       └── test_basic_agent_graph.py
│   │   ├── application/services/test_orchestration_service.py  # 更新
│   │   ├── architecture/test_langgraph_architecture.py
│   │   └── test_composition_root_agent.py
│   ├── contracts/test_port_contract_agent_engine.py
│   ├── integration/test_story_1_18b_integration.py
│   └── acceptance/
│       ├── test_story_1_18b.feature
│       └── test_story_1_18b_steps.py
```

### 六边形架构分层说明

| 层级 | 目录 | 组件 | 职责 |
|------|------|------|------|
| **Domain** | `domain/` | AgentEnginePort, FlowStatus, AgentDecided, CheckpointReached | 核心端口/值对象/事件，零外部依赖 |
| **Application** | `application/` | OrchestrationService, WorkflowTask, WorkflowResult | 业务编排，接受双端口注入 |
| **Infrastructure** | `infrastructure/` | LangGraphEngine, LangGraphConfig, BasicAgentGraph, agent_nodes | LangGraph SDK 封装 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.18a](./1-18a-prefect-workflow-integration.md)

1. **配置模式复用** — LangGraphConfig 采用与 PrefectConfig 相同的 `@dataclass(frozen=True)` + `from_env()` 模式
2. **事件驱动解耦** — LangGraphEngine 仅通过注入的 EventPublisher 发布事件，不直接调用 domain services
3. **构造函数原始值注入** — 参考 PrefectEngine 模式：domain 层不接受 infrastructure 配置对象，由 composition_root 传入
4. **SDK mock 策略** — LangGraph SDK 全量 mock，不依赖真实 LangGraph server
5. **端口契约三位一体** — 每个端口必须同时有 contract test + registry + composition_root
6. **FlowStatus 复用** — 两个引擎共用同一状态枚举，映射逻辑在各适配器内完成
7. **ChannelRouter 事件路由** — AgentDecided/CheckpointReached 已注册于 DEFAULT_MAPPINGS（RELIABLE 通道），无需新增映射
8. **PublishResult 检查** — EventPublisher.publish() 返回 PublishResult，需检查 `is_full_failure` 并记录警告日志
9. **Deployment vs 直接调用** — PrefectEngine 使用 Deployment 模式触发远程工作流，LangGraphEngine MVP 使用本地 `ainvoke()` 直接调用

**应用到本故事:**
- [ ] LangGraphConfig 遵循 frozen dataclass + from_env() 模式
- [ ] LangGraphEngine 通过构造函数注入 EventPublisher（不直接创建）
- [ ] OrchestrationService 注册更新为注入双引擎（SINGLETON）
- [ ] 测试使用 mock LangGraph SDK，不启动真实 server
- [ ] OrchestrationService 不导入 infrastructure 层任何类
- [ ] 契约测试覆盖端口注册/解析/兼容性
- [ ] 回归测试确保 data_pipeline 路由不受影响

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-20 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` §3.2 ADR-002 |
| **事件总线设计** | `docs/architecture/sisys-event-bus-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-18a-prefect-workflow-integration.md` |
| **Story 模板** | `docs/developer/story-template.md` v2.7.0 |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` §3.2 ADR-002 提取
- [x] 现有代码继承已确认（EventPublisher/DomainEvent/ChannelRouter/PortRegistry/AgentDecided/CheckpointReached）
- [x] 前一个故事学习经验已整合（Story 1.18a）
- [x] 状态将设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] ADR-002 双核引擎架构对齐
- [x] MVP 范围澄清（端口+引擎+1个Graph，非全部Graph）
- [x] LangGraph 导入边界明确（仅 infrastructure/agent_orch/）
- [x] LangGraph 1.0 API 注意事项文档化

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-18b-langgraph-agent-orchestration.md` — 本故事文件

**待创建的文件/To Be Created (Dev Story 实施):**

领域层（Domain）:
- `src/domain/ports/agent_engine.py` — AgentEnginePort Protocol

基础设施层（Infrastructure）:
- `src/infrastructure/config/langgraph.py` — LangGraphConfig
- `src/infrastructure/agent_orch/__init__.py` — 包声明
- `src/infrastructure/agent_orch/schemas.py` — BasicAgentState TypedDict
- `src/infrastructure/agent_orch/langgraph_engine.py` — LangGraphEngine
- `src/infrastructure/agent_orch/graphs/__init__.py` — Graphs 包
- `src/infrastructure/agent_orch/graphs/basic_agent_graph.py` — BasicAgentGraph
- `src/infrastructure/agent_orch/nodes/__init__.py` — Nodes 包
- `src/infrastructure/agent_orch/nodes/agent_nodes.py` — analyze/synthesize nodes

测试文件:
- `tests/unit/domain/ports/test_agent_engine.py`
- `tests/unit/infrastructure/config/test_langgraph_config.py`
- `tests/unit/infrastructure/agent_orch/test_langgraph_engine.py`
- `tests/unit/infrastructure/agent_orch/test_basic_agent_graph.py`
- `tests/unit/test_composition_root_agent.py`
- `tests/unit/architecture/test_langgraph_architecture.py`
- `tests/contracts/test_port_contract_agent_engine.py`
- `tests/integration/test_story_1_18b_integration.py`
- `tests/acceptance/test_story_1_18b.feature`
- `tests/acceptance/test_story_1_18b_steps.py`

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 AgentEnginePort
- `src/application/services/orchestration_service.py` — 新增 agent_engine 参数 + agent_reasoning 路由
- `src/infrastructure/agent_orch/__init__.py` — 导出 LangGraphEngine
- `src/composition_root.py` — 注册 agent_engine + 更新 orchestration_service 注册
- `tests/unit/application/services/test_orchestration_service.py` — 更新构造函数调用 + 新增 agent_reasoning 路由测试
- `tests/integration/test_story_1_18a_integration.py` — 更新 OrchestrationService 构造调用（添加 agent_engine 参数）

**已有文件（复用，禁止修改）:**
- `src/domain/ports/event_publisher.py` — EventPublisher 端口
- `src/domain/ports/workflow_engine.py` — WorkflowEnginePort 端口
- `src/domain/events/base.py` — DomainEvent 基类
- `src/domain/events/agent_events.py` — AgentDecided 事件
- `src/domain/events/checkpoint_events.py` — CheckpointReached 事件
- `src/domain/value_objects/flow_status.py` — FlowStatus 值对象
- `src/infrastructure/messaging/dual_channel_event_bus.py` — 双通道事件总线
- `src/infrastructure/messaging/channel_router.py` — ChannelRouter（AgentDecided/Checkpoint 已注册）
- `src/domain/entities/agent.py` — Agent 实体

---

## 📚 Project Context Reference

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **ADR-002** | 双核引擎：Prefect=数据管道，LangGraph=Agent推理 | architecture.md §3.2 |
| **LangGraph 导入边界** | 所有 `import langgraph` 限定于 `src/infrastructure/agent_orch/` | test_hexagonal_architecture_constraints.py |
| **测试覆盖率** | 架构层≥85%，集成测试≥70% | story-template.md |
| **LangGraph 版本** | 1.0+（pyproject.toml 声明） | pyproject.toml |
| **FlowStatus 复用** | 两个引擎共用 FlowStatus 枚举 | FlowStatus 文档注释 |

### 关键路径依赖

```
Story 1.1 (骨架) → Story 1.3 (事件总线) → Story 1.18a (Prefect 集成) → Story 1.18b (LangGraph 集成)
                                                                        ↓
                                                      Epic 4 (工具箱) + Epic 5 (Agent协作) + Epic 6 (战略规划)
```

### Prefect vs LangGraph 职责分离

| 引擎 | 职责 | 处理类型 | Story |
|------|------|---------|-------|
| **Prefect** | 确定性数据管道 | 文档处理/RAG索引/报告生成 | Story 1.18a ✅ |
| **LangGraph** | 认知推理 | BLM规划/Agent协作/多视角分析 | **本 Story** |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.18b |
| **Story Key** | 1-18b-langgraph-agent-orchestration |
| **File** | `_bmad-output/implementation-artifacts/stories/1-18b-langgraph-agent-orchestration.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-18b（ARCH LangGraph Agent 编排） |
| **覆盖 FR** | FR-AR-02（事件发布至事件总线） |
| **依赖 Story** | Story 1.1（架构骨架）、Story 1.3（事件总线）、Story 1.18a（Prefect 集成） |
| **前置条件** | 六边形架构骨架就绪、事件总线就绪、Prefect 集成完成、LangGraph 1.0+ 依赖已声明 |
| **后续 Story** | Story 1.19（成本度量）、Epic 4/5/6 故事 |
| **覆盖率要求** | 架构层≥85%，集成测试≥70% |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`
6. [x] ADR-002 双核引擎架构对齐
7. [x] MVP 范围澄清（端口+引擎+1 Graph，非全部 Graph）
8. [x] LangGraph 导入边界明确
9. [x] AgentDecided/CheckpointReached 事件复用确认
10. [x] 端口契约治理完整（registry/composition_root/contract test）
11. [x] 文件命名符合 story-template.md 规范

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

**模板版本/Template Version:** 2.7.0
**创建日期/Created:** 2026-05-20
**最后更新/Last Updated:** 2026-05-20
