# Story 4.1a: 战略工具实现

**Status:** `ready-for-dev`

> **注意:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**作为** 工具工程师,
**我希望** 将已注册的 23 种战略工具从"目录条目"转化为"可执行工具"——实现领域模型、执行引擎、Skills SOP 和完整调用链路,
**以便** Agent 可以按照 Think→Code→Execute→Observe→Validate 标准工作流调用工具完成战略分析。

### 业务价值

本 Story 是 Epic 4（战略工具箱）的第二个故事（P0-2），对应 FR-ST-02（战略工具可执行化）。它将 Story 4.1 注册的 23 种工具元数据转化为可执行工具——补齐 Tool 聚合根增强、ToolService、ToolExecutionEngine、StrategicAnalysisUseCase 和 Skills 三级系统。

**现有资产（已就绪，本 Story 直接利用）：**
- `Tool` 实体（`src/domain/entities/tool.py`）— 基础属性 + `ToolCategory` 枚举（10 个分类）+ 不变量校验
- `ToolRepositoryPort`（`src/domain/ports/tool_repository.py`）— 增删查存能力
- `InMemoryToolRepository`（`src/infrastructure/storage/inmemory/tool_repository.py`）— MVP 内存仓储
- `ToolRegistryServicePort` + `ToolRegistryService`（应用层）— 工具注册与查询
- `StrategicToolCatalog`（`src/domain/entities/strategic_tool_catalog.py`）— 23 种工具元数据常量
- `ToolNotFoundError` / `ToolAlreadyExistsError` 异常（`src/domain/exceptions/tool_exceptions.py`）
- `ToolExecuted` 领域事件（`src/domain/events/tool_events.py`）
- `LLMClientPort`（`src/domain/ports/llm_client.py`）— Think/Code 阶段依赖
- `SandboxExecutor`（`src/domain/ports/sandbox_executor.py`）— Execute 阶段依赖
- 组合根已注册 `tool_repository` 和 `tool_registry_service` 端口

**本 Story 的核心任务：**
- **增强 Tool 实体**：新增 `rule_version`、`reliability_score`、`execution_count`、`execution_state` 字段 + 状态机枚举 `ToolExecutionState`
- **定义 ToolService 领域服务**（`src/domain/services/tool_service.py`）— Protocol 定义 `execute`、`get_tool`、`list_all_tools`、`get_tools_by_category`
- **定义 ToolCall / ToolResult 值对象**（`src/domain/value_objects/tool_execution.py`）— frozen dataclass
- **实现 ToolExecutionEngine**（`src/application/services/tool_execution_engine.py`）— Think→Code→Execute→Observe→Validate 五阶段循环
- **实现 StrategicAnalysisUseCase**（`src/application/use_cases/strategic_analysis.py`）— 用例编排
- **实现 Skills 三级加载系统**（`src/application/skills/`）— SkillLoaderPort + skill_manifest + L1/L2/L3 MVP
- **在 `composition_root.py` 中注册新端口（`tool_service` + `skill_loader`）**，完成依赖注入

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1a

**前置依赖:**
- Story 4.1（战略工具注册 ✅ 已实现）— 提供 Tool 实体、ToolCategory、ToolRepositoryPort、ToolRegistryService、23 种工具元数据

**后续依赖:**
- Story 4.2（工具链编排 DAG）— 依赖本 Story 实现的 ToolService 和 ToolExecutionEngine
- Story 4.3（工具 Schema 验证）— 依赖本 Story 的 ToolCall/ToolResult 值对象
- Story 4.4（Docker 沙箱执行）— 依赖本 Story 的 ToolExecutionEngine 五阶段循环
- Story 5.1（CEO Agent 实例化）— Agent 调用工具需本 Story 的 StrategicAnalysisUseCase

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Tool 聚合根与状态机

**Given** Tool 实体已存在
**When** 增强 Tool 实体
**Then** 新增 `rule_version`（str）、`reliability_score`（float 0-1）、`execution_count`（int）、`execution_state`（ToolExecutionState）字段
**And** ToolExecutionState 状态机枚举包含：idle → planning → executing → validating → completed/failed
**And** `transition_to()` 方法执行状态转换并校验不变量

**验证标准/Validation Criteria:**
- [ ] Tool 实体包含 `rule_version`、`reliability_score`、`execution_count`、`execution_state` 字段
- [ ] `ToolExecutionState` 枚举包含 6 个值：idle、planning、executing、validating、completed、failed
- [ ] `transition_to()` 方法校验合法转换路径，非法转换抛出 `EntityStateTransitionError`（EXCEPTION_243）
- [ ] `reliability_score` 范围校验：0.0 <= score <= 1.0
- [ ] `validate()` 不变量校验覆盖新增字段
- [ ] 状态机转换路径：idle→planning、planning→executing、executing→validating、validating→completed、executing→failed、validating→failed

### AC-2: ToolService 领域服务接口

**Given** Tool 聚合根已增强
**When** 定义 ToolService 领域服务
**Then** `src/domain/services/tool_service.py` 定义 ToolService Protocol
**And** 方法：`execute(tool_id, tool_call, context) -> ToolResult`
**And** 方法：`get_tool(tool_id)`、`list_all_tools()`、`get_tools_by_category(category)`

**验证标准/Validation Criteria:**
- [ ] `ToolService` 是 `@runtime_checkable Protocol`
- [ ] `execute()` 方法接受 `tool_id: uuid.UUID`、`tool_call: ToolCall`、`context: dict` 参数，返回 `ToolResult`
- [ ] `get_tool()` 方法接受 `tool_id: uuid.UUID`，返回 `Tool`
- [ ] `list_all_tools()` 方法返回 `list[Tool]`
- [ ] `get_tools_by_category()` 方法接受 `category: ToolCategory`，返回 `list[Tool]`
- [ ] 领域层零外部依赖

### AC-3: ToolCall / ToolResult 值对象

**Given** ToolService 接口已定义
**When** 定义 ToolCall / ToolResult 值对象
**Then** `src/domain/value_objects/tool_execution.py` 定义 frozen dataclass
**And** ToolResult.status 枚举：success/failed/invalid/insufficient_data
**And** 证据包：input_hash、rule_version、citations、confidence

**验证标准/Validation Criteria:**
- [ ] `ToolCall` 是 frozen dataclass，包含 `tool_id`、`parameters: dict`、`context: dict` 字段
- [ ] `ToolResult` 是 frozen dataclass，包含 `status`、`output: dict`、`evidence: ToolEvidence` 字段
- [ ] `ToolExecutionStatus` 枚举包含 4 个值：success、failed、invalid、insufficient_data
- [ ] `ToolEvidence` 包含 `input_hash: str`、`rule_version: str`、`citations: list[str]`、`confidence: float` 字段
- [ ] 值对象不可变（frozen=True）

### AC-4: ToolExecutionEngine 标准工作流

**Given** ToolService 和值对象已定义
**When** 实现 ToolExecutionEngine
**Then** Think→Code→Execute→Observe→Validate 五阶段循环
**And** Think/Code 依赖 LLMClientPort（已实现）
**And** Execute 依赖 SandboxExecutor（已实现端口，MVP mock）
**And** 失败重试最多 3 次，超出返回 failed
**And** 证据打包：plan + code + result + observation + validation + confidence + citations

**验证标准/Validation Criteria:**
- [ ] `ToolExecutionEngine` 实现 `ToolService` Protocol
- [ ] 五阶段循环：think() → code() → execute() → observe() → validate()
- [ ] Think 阶段调用 `LLMClientPort.generate()` 生成执行计划
- [ ] Code 阶段调用 `LLMClientPort.generate()` 生成 Python 代码
- [ ] Execute 阶段调用 `SandboxExecutor.execute_code()` 执行代码
- [ ] Observe 阶段产出 `observed_output: dict`（标准化执行结果）
- [ ] Validate 阶段产出 `validation_result: {match: bool, issues: list[str]}`，并可据此决定 completed/failed
- [ ] 失败重试最多 3 次，超出返回 `ToolResult(status=failed)`
- [ ] 证据打包包含 plan、code、result、observation、validation、confidence、citations
- [ ] 工具状态机转换：idle→planning→executing→validating→completed/failed

### AC-5: StrategicAnalysisUseCase 用例编排

**Given** ToolExecutionEngine 已实现
**When** 实现 StrategicAnalysisUseCase
**Then** `src/application/use_cases/strategic_analysis.py` 定义用例
**And** tool_name 查询 → Skill 加载 → ToolService.execute → ToolExecuted 事件发布
**And** 依赖通过端口注入，不导入 infrastructure 具体实现

**验证标准/Validation Criteria:**
- [ ] `StrategicAnalysisUseCase` 接受 `tool_name: str`、`parameters: dict`、`context: dict` 参数
- [ ] 通过 `ToolRegistryServicePort.get_tool(tool_name)` 查询工具
- [ ] 通过 `SkillLoaderPort.load_skill_summary(tool_name)` 加载 Skill 摘要并注入 context
- [ ] 通过 `ToolService.execute()` 执行工具并获得 `ToolResult`
- [ ] 若 `ToolResult.status != success`，不发布 `ToolExecuted`，改为记录失败证据并向上抛出领域异常
- [ ] 若 `ToolResult.status == success`，发布 `ToolExecuted` 领域事件，事件至少包含 `tool_id` 与 `execution_result`
- [ ] 依赖通过构造器注入（`tool_registry`、`tool_service`、`skill_loader`、`event_publisher`）
- [ ] 不导入 infrastructure 具体实现类

### AC-6: Skills 三级渐进式加载（MVP）

**Given** StrategicAnalysisUseCase 已实现
**When** 实现 Skills 加载系统
**Then** L1 TOOLS.md：23 个工具元数据摘要，总 token < 200
**And** L2 SKILL.md：至少 3 份完整 SOP（PESTEL/SWOT/波特五力），其余可用结构化模板占位，每份 < 500 行
**And** L3 scripts/ + references/：目录存在，允许空文件或最小 stub，按需扩展
**And** skill_manifest.py：tool_id ↔ slug 双向映射完整覆盖 23 种工具

**验证标准/Validation Criteria:**
- [ ] `src/application/skills/` 目录结构包含 L1/L2/L3 三级
- [ ] L1 TOOLS.md 文件包含 23 种工具元数据摘要，总 token < 200
- [ ] L2 SKILL.md 至少 3 份完整 SOP（PESTEL/SWOT/波特五力），其余为结构化模板（必须包含五阶段占位）
- [ ] L3 scripts/ 和 references/ 目录存在；MVP 允许空文件或最小 stub
- [ ] `skill_manifest.py` 实现 `tool_id` ↔ `slug` 双向映射（23 项全覆盖）
- [ ] `SkillLoader` 类实现三级加载逻辑，并通过 `SkillLoaderPort` 暴露接口

### AC-7: 端口注册与架构约束

**Given** 所有组件已实现
**When** 在 composition_root.py 中注册新端口
**Then** tool_service、skill_loader 端口正确注册
**And** 六边形架构：domain 零外部依赖、依赖方向矩阵合规

**验证标准/Validation Criteria:**
- [ ] `tool_service` 端口已注册（SCOPED 生命周期，tool-team 负责）
- [ ] `skill_loader` 端口已注册（SCOPED 生命周期，tool-team 负责）
- [ ] `PortRegistry.get("tool_service")` 返回非空 `PortSpec`
- [ ] `PortRegistry.get("skill_loader")` 返回非空 `PortSpec`
- [ ] domain 层零外部依赖（无 pydantic/sqlalchemy/redis 等导入）
- [ ] 依赖方向矩阵合规（application→domain 允许，infrastructure→domain 允许）

---

## 🏗️ SDD+TDD 融合开发

> **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] `ToolExecuted` 已定义（`src/domain/events/tool_events.py`），本 Story 复用
- [ ] 本 Story 不修改事件 schema；工具执行证据（evidence）仅承载于 `ToolResult` 值对象内，不扩散至领域事件

#### 数据模型 (Data Models)
- [ ] `Tool` 实体增强（`src/domain/entities/tool.py`）：新增 `rule_version`、`reliability_score`、`execution_count`、`execution_state`
- [ ] `ToolExecutionState` 状态机枚举定义
- [ ] `ToolCall` / `ToolResult` / `ToolEvidence` 值对象定义

#### 端口契约清单执行约束（强制）
- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task
- [ ] Skills 加载必须抽象为 application 层端口（`SkillLoaderPort`），禁止 use case 直接操作文件系统

#### 统一端口定义注册与管理 (Port Contract)

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner | 状态 |
|---------|------|------|---------|---------|-------|------|
| `tool_service` | v1.0.0 | `ToolService` | `src.application.services.tool_execution_engine.ToolExecutionEngine` | SCOPED | tool-team | 新建 |
| `skill_loader` | v1.0.0 | `SkillLoaderPort` | `src.application.skills.skill_loader.SkillLoader` | SCOPED | tool-team | 新建 |

> **实现说明：** 采用单端口注册策略（`tool_service`），避免“禁止语义重复端口”违规；`ToolExecutionEngine` 作为实现类注入 `tool_service` 端口，后续可按需升级接口。

- [ ] 端口契约定义位于 `src/domain/services/tool_service.py`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口登记为 `PortSpec`
- [ ] 端口实现仅在 `src/composition_root.py` 统一注册
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_tool_service.py`）
- [ ] 接口命名符合单一职责
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象接口

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计。

**复用已有异常：**
- `EntityStateTransitionError`（EXCEPTION_243）— 状态机非法转换
- `EntityValidationError`（EXCEPTION_242）— 不变量校验失败
- `ToolNotFoundError`（EXCEPTION_380）— 工具不存在

**本 Story 无需新增异常**，全部复用现有异常体系。

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|-------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止 |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | Tool 实体增强 | 状态机、不变量、新增字段 | `tests/unit/domain/entities/test_tool.py` | Task 1 |
| **TDD 单元测试** | ToolCall/ToolResult 值对象 | frozen dataclass、枚举、证据包 | `tests/unit/domain/value_objects/test_tool_execution_values.py` | Task 2 |
| **TDD 单元测试** | ToolService Protocol | 端口契约、方法签名 | `tests/contracts/test_port_contract_tool_service.py` | Task 3 |
| **TDD 单元测试** | ToolExecutionEngine | 五阶段循环、重试、证据打包 | `tests/unit/application/services/test_tool_execution_engine.py` | Task 4 |
| **TDD 单元测试** | StrategicAnalysisUseCase | 用例编排、事件发布 | `tests/unit/application/use_cases/test_strategic_analysis_usecase.py` | Task 5 |
| **TDD 单元测试** | Skills 加载系统 | 三级加载、manifest 映射 | `tests/unit/application/skills/test_skills_loader.py` | Task 6 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `tests/unit/architecture/test_arch_strategic_tool_impl.py` | Task 7 |
| **集成测试** | 工具执行全链路 | 端口→引擎→仓储→实体 | `tests/integration/test_integration_strategic_tool_impl.py` | Task 7 |
| **TDD 验收测试** | Gherkin 场景 | AC-1~AC-7 业务价值验收 | `tests/acceptance/test_acceptance_strategic_tool_impl.feature` | Task 0/8 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_acceptance_strategic_tool_impl.py` | Task 0/8 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- **P1 阻断门禁**
- [ ] **集成测试覆盖率 ≥70%**
- [ ] **分层门禁判定源**：以 `scripts/check_coverage_gates.py` 为准，CI 同时执行 `--fail-under=80` 作为整体兜底

> ⚠️ **骨架 Story 覆盖率豁免：** 如果本 Story 为架构骨架（Skeleton），大量代码为空接口/占位类/`__init__.py`，
> 无法达到上述覆盖率指标。**请将覆盖率要求临时调整为：整体≥30%，对应层≥50%。**
> 从下一个非骨架 Story 开始恢复标准覆盖率要求。**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [ ] **架构约束门禁通过**（`poetry run lint-imports`，必须为零违规）

#### 测试隔离约束

> **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

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
| AC-1 | Tool 聚合根与状态机 | Task 1 | Subtask 1.1-1.5 | `test_tool.py` |
| AC-2 | ToolService 领域服务接口 | Task 3 | Subtask 3.1-3.3 | `test_port_contract_tool_service.py` |
| AC-3 | ToolCall / ToolResult 值对象 | Task 2 | Subtask 2.1-2.4 | `test_tool_execution_values.py` |
| AC-4 | ToolExecutionEngine 标准工作流 | Task 4 | Subtask 4.1-4.5 | `test_tool_execution_engine.py` |
| AC-5 | StrategicAnalysisUseCase 用例编排 | Task 5 | Subtask 5.1-5.3 | `test_strategic_analysis_usecase.py` |
| AC-6 | Skills 三级渐进式加载 | Task 6 | Subtask 6.1-6.4 | `test_skills_loader.py` |
| AC-7 | 端口注册与架构约束 | Task 7 | Subtask 7.1-7.4 | `test_port_contract_tool_service.py` |
| AC-1~AC-7 | 开发结束验收 | Task 8 | Subtask 8.1-8.4 | `test_acceptance_strategic_tool_impl.feature` |

---

## 📋 Tasks / Subtasks 任务分解

> **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **目的：** 在进入代码实现前，明确 Schema、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `ToolExecutionState` 状态机枚举（6 个值 + 合法转换路径表）
- [ ] Subtask 0.2: 定义 `ToolCall` / `ToolResult` / `ToolEvidence` 值对象 Schema
- [ ] Subtask 0.3: 定义 `ToolService` Protocol 签名（`execute`、`get_tool`、`list_tools`、`list_tools_by_category`）
- [ ] Subtask 0.4: 定义 ToolExecutionEngine 五阶段循环接口
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_strategic_tool_impl.feature`
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_strategic_tool_impl.py`
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Tool 实体增强与状态机

**关联 AC:** AC-1

> **目的：** 增强 Tool 实体，新增状态机和执行相关字段。

#### TDD 循环 A：ToolExecutionState 状态机枚举

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool.py` 中 ToolExecutionState 测试（6 个值存在、合法转换路径） |
| 🟢 绿 | 在 `tool.py` 中添加 `ToolExecutionState` 枚举和 `TOOL_EXECUTION_TRANSITIONS` 转换表 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 ToolExecutionState 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 `ToolExecutionState` 枚举（idle/planning/executing/validating/completed/failed）
- [ ] Subtask 1.3: 🔄 重构 — 定义 `TOOL_EXECUTION_TRANSITIONS` 合法转换路径表

#### TDD 循环 B：Tool 实体字段增强

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool.py` 中新增字段测试（rule_version/reliability_score/execution_count/execution_state） |
| 🟢 绿 | 在 `Tool` dataclass 中添加 4 个新字段 |
| 🔄 重构 | 优化 validate() 方法覆盖新增字段 |

- [ ] Subtask 1.4: 🔴 红 — 编写新增字段失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 `Tool` 实体字段增强 + `transition_to()` 方法
- [ ] Subtask 1.6: 🔄 重构 — 运行 `ruff check` + `mypy` + 确认测试通过

**完成标准/Definition of Done:**
- [ ] `ToolExecutionState` 包含 6 个枚举值
- [ ] `Tool` 实体包含 `rule_version`、`reliability_score`、`execution_count`、`execution_state`
- [ ] `transition_to()` 方法校验合法转换，非法转换抛 `EntityStateTransitionError`
- [ ] TDD 循环全部通过
- [ ] 覆盖率 >= 90%

---

### Task 2: ToolCall / ToolResult 值对象

**关联 AC:** AC-3

> **目的：** 定义工具执行的输入/输出值对象。

#### TDD 循环 A：ToolExecutionStatus 枚举

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_execution_values.py`（4 个值存在） |
| 🟢 绿 | 创建 `src/domain/value_objects/tool_execution.py`，定义枚举 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 ToolExecutionStatus 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 创建 `ToolExecutionStatus` 枚举（success/failed/invalid/insufficient_data）

#### TDD 循环 B：ToolCall / ToolResult / ToolEvidence

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_execution_values.py`（frozen dataclass、字段完整性） |
| 🟢 绿 | 创建 `ToolCall`、`ToolEvidence`、`ToolResult` frozen dataclass |
| 🔄 重构 | 添加类型注解、docstring |

- [ ] Subtask 2.3: 🔴 红 — 编写值对象失败测试
- [ ] Subtask 2.4: 🟢 绿 — 实现 `ToolCall`、`ToolEvidence`、`ToolResult`
- [ ] Subtask 2.5: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] `ToolExecutionStatus` 包含 4 个枚举值
- [ ] `ToolCall`、`ToolEvidence`、`ToolResult` 为 frozen dataclass
- [ ] TDD 循环全部通过
- [ ] 覆盖率 >= 90%

---

### Task 3: ToolService 领域服务 Protocol

**关联 AC:** AC-2, AC-7

> **目的：** 定义 ToolService 领域服务端口，并确保端口对齐实现层已有方法。

#### TDD 循环 A：ToolService Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_port_contract_tool_service.py`（Protocol 方法签名、@runtime_checkable） |
| 🟢 绿 | 创建 `src/domain/services/tool_service.py`，定义 `ToolService` Protocol |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 `ToolService` 契约测试
- [ ] Subtask 3.2: 🟢 绿 — 创建 `ToolService` Protocol（execute、get_tool、list_all_tools、get_tools_by_category）
- [ ] Subtask 3.3: 🔄 重构 — 优化方法签名、添加 docstring

**完成标准/Definition of Done:**
- [ ] `ToolService` 是 `@runtime_checkable Protocol`
- [ ] 所有方法签名符合 AC-2 定义
- [ ] 领域层零外部依赖
- [ ] 覆盖率 >= 90%

---

### Task 4: ToolExecutionEngine 五阶段执行引擎

**关联 AC:** AC-4

> **目的：** 实现 Think→Code→Execute→Observe→Validate 五阶段循环，并输出标准化执行结果与质量判定。

#### TDD 循环 A：ToolExecutionEngine 基础结构

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_execution_engine.py`（构造、五阶段方法存在性） |
| 🟢 绿 | 创建 `src/application/services/tool_execution_engine.py`，实现基本结构 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 编写引擎基础结构失败测试
- [ ] Subtask 4.2: 🟢 绿 — 实现 `ToolExecutionEngine` 基础结构（依赖注入 LLMClientPort + SandboxExecutor）

#### TDD 循环 B：五阶段循环实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写五阶段循环测试（think/code/execute/observe/validate） |
| 🟢 绿 | 实现 think() → code() → execute() → observe() → validate() 方法 |
| 🔄 重构 | 优化重试逻辑（最多 3 次） |

- [ ] Subtask 4.3: 🔴 红 — 编写五阶段循环失败测试
- [ ] Subtask 4.4: 🟢 绿 — 实现 `think()` 调用 LLMClientPort.generate()
- [ ] Subtask 4.5: 🟢 绿 — 实现 `code()` 调用 LLMClientPort.generate()
- [ ] Subtask 4.6: 🟢 绿 — 实现 `execute()` 调用 SandboxExecutor.execute_code()
- [ ] Subtask 4.7: 🟢 绿 — 实现 `observe()`，产出 `observed_output`、`anomalies`、`trends`
- [ ] Subtask 4.8: 🟢 绿 — 实现 `validate()`，产出 `validation_result`、`issues`、`confidence`
- [ ] Subtask 4.9: 🔄 重构 — 实现重试逻辑（最多 3 次）+ 证据打包

**完成标准/Definition of Done:**
- [ ] `ToolExecutionEngine` 实现 `ToolService` Protocol
- [ ] 五阶段循环完整实现
- [ ] observe 输出标准化结果（`observed_output/anomalies/trends`）
- [ ] validate 输出标准化判定（`validation_result/issues/confidence`）
- [ ] 失败重试最多 3 次，质量不达标（issues 非空或 confidence 低于阈值）可触发 failed
- [ ] 证据打包完整
- [ ] 覆盖率 >= 85%

---

### Task 5: StrategicAnalysisUseCase 用例编排

**关联 AC:** AC-5, AC-7

> **目的：** 实现战略分析用例编排，明确成功/失败路径判定与依赖注入契约。

#### TDD 循环 A：StrategicAnalysisUseCase

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_strategic_analysis_usecase.py`（用例执行、事件发布） |
| 🟢 绿 | 创建 `src/application/use_cases/strategic_analysis.py` |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 5.1: 🔴 红 — 编写用例失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 `StrategicAnalysisUseCase`（tool_name 查询 → Skill 加载 → execute → 事件发布）
- [ ] Subtask 5.3: 🔄 重构 — 优化依赖注入、添加日志

**完成标准/Definition of Done:**
- [ ] `StrategicAnalysisUseCase` 用例编排完成
- [ ] 成功路径仅发布 `ToolExecuted` 事件；失败路径抛出领域异常并记录证据
- [ ] 依赖通过构造器注入
- [ ] 不导入 infrastructure 具体实现
- [ ] 覆盖率 >= 85%

---

### Task 6: Skills 三级加载系统

**关联 AC:** AC-6

> **目的：** 实现 Skills 三级渐进式加载。

#### TDD 循环 A：skill_manifest.py

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_skills_loader.py`（双向映射测试） |
| 🟢 绿 | 创建 `src/application/skills/skill_manifest.py` |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 6.1: 🔴 红 — 编写 manifest 双向映射失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现 `skill_manifest.py`（tool_id ↔ slug 双向映射）

#### TDD 循环 B：SkillLoader 三级加载

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_skills_loader.py`（L1/L2/L3 加载测试） |
| 🟢 绿 | 创建 `src/application/skills/skill_loader.py` |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 6.3: 🔴 红 — 编写 SkillLoader 失败测试
- [ ] Subtask 6.4: 🟢 绿 — 实现 `SkillLoader`（L1 TOOLS.md / L2 SKILL.md / L3 scripts+references）
- [ ] Subtask 6.5: 创建 L1 `TOOLS.md`（23 种工具元数据摘要，<200 tokens）
- [ ] Subtask 6.6: 创建 L2 `skills/` 目录（至少 3 份完整 SOP，其余结构化模板占位）
- [ ] Subtask 6.7: 创建 L3 `scripts/` + `references/` 目录结构（MVP 允许 stub）

**完成标准/Definition of Done:**
- [ ] `skill_manifest.py` 双向映射完成（23 项全覆盖）
- [ ] `SkillLoader` 三级加载完成，并通过 `SkillLoaderPort` 暴露接口
- [ ] L1/L2/L3 目录结构完整
- [ ] L2 至少 3 份完整 SOP，其余模板符合五阶段占位规范
- [ ] 覆盖率 >= 85%

---

### Task 7: 端口注册与架构约束验证

**关联 AC:** AC-7

> **目的：** 在 composition_root.py 中注册新端口，验证架构约束。

#### TDD 循环 A：端口注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口注册测试 |
| 🟢 绿 | 在 `composition_root.py` 中添加端口注册代码 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 7.1: 🔴 红 — 编写端口注册失败测试
- [ ] Subtask 7.2: 🟢 绿 — 在 `composition_root.py` 中注册 `tool_service` 与 `skill_loader`
- [ ] Subtask 7.3: 🔄 重构 — 优化注册顺序、添加注释

#### SDD 架构验证测试

- [ ] Subtask 7.4: 创建 `tests/unit/architecture/test_arch_strategic_tool_impl.py`
- [ ] Subtask 7.5: 实现依赖方向验证（domain 层无外部依赖）
- [ ] Subtask 7.6: 实现端口注册验证（所有端口在 composition_root.py 中注册）
- [ ] Subtask 7.7: 实现 `poetry run lint-imports` 零违规验证（架构契约强制校验）

**完成标准/Definition of Done:**
- [ ] `tool_service` 端口已注册
- [ ] `skill_loader` 端口已注册
- [ ] 所有架构约束测试通过
- [ ] 覆盖率 >= 85%

---

### Task 8: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **目的：** 收尾阶段最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写收尾验收场景 |
| 🟢 绿 | 实现 BDD 步骤 |
| 🔄 重构 | 收敛场景命名、统一断言 |

- [ ] Subtask 8.1: 场景 1 — 验证 `src` 完成清单（Tool 实体增强、ToolService、ToolCall/ToolResult、ToolExecutionEngine、StrategicAnalysisUseCase、Skills 加载）
- [ ] Subtask 8.2: 场景 2 — 验证 `tests` 完成清单（unit/contracts/integration/acceptance）
- [ ] Subtask 8.3: 运行开发结束验收测试
- [ ] Subtask 8.4: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证
- [ ] `tests` 完成清单已逐项验证
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 领域驱动六边形架构（DDD + Hexagonal Architecture）
- **设计约束:** 领域层零外部依赖、依赖方向矩阵、端口注册与 DI 注入
- **接口治理:** 统一端口注册（PortSpec）、Registry/Resolver/ContractGate、Composition Root 装配、契约优先、版本化兼容
- **技术栈:** Python 3.11+、FastAPI 0.104+、dataclass（领域层）、LLMClientPort + SandboxExecutor（工具执行）

### 关键架构决策

**来源:** [`architecture.md`](../../docs/architecture/architecture.md) - §17.2 战略工具箱

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **五阶段循环（Think→Code→Execute→Observe→Validate）** | 标准化工作流、可审计、可重试 | 依赖 LLM 调用延迟 | 9/10 |
| Skills 三级加载 | 渐进式加载、Token 友好 | 需维护多级文件 | 8/10 |
| ToolExecutionState 状态机 | 可预测的状态转换、不变量保护 | 增加实体复杂度 | 9/10 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   └── tool.py                     # Tool 实体（增强：rule_version/reliability_score/execution_count/execution_state）
│   ├── services/
│   │   └── tool_service.py             # ToolService Protocol（本 Story 新建）
│   ├── value_objects/
│   │   └── tool_execution.py           # ToolCall/ToolResult/ToolEvidence（本 Story 新建）
│   └── events/
│       └── tool_events.py              # ToolExecuted 事件（复用）
├── application/
│   ├── ports/
│   │   └── skill_loader_port.py        # SkillLoaderPort（本 Story 新建）
│   ├── services/
│   │   └── tool_execution_engine.py    # ToolExecutionEngine（本 Story 新建）
│   ├── use_cases/
│   │   └── strategic_analysis.py       # StrategicAnalysisUseCase（本 Story 新建）
│   └── skills/                         # Skills 三级加载系统（本 Story 新建）
│       ├── __init__.py
│       ├── skill_manifest.py           # tool_id ↔ slug 双向映射
│       ├── skill_loader.py             # 三级加载器
│       ├── TOOLS.md                    # L1：23 种工具元数据摘要
│       └── skills/                     # L2：23 份 SKILL.md SOP
└── composition_root.py                 # 端口注册（本 Story 修改）
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-1-strategic-tool-registration-tools](./4-1-strategic-tool-registration-tools.md)

**关键学习:**
1. **端口升级机制** — `PortRegistry.register()` 对同名端口冲突则抛 `ConflictError`，必须先 `unregister()` 再重新注册
2. **异常体系设计** — 异常编码从 EXCEPTION_380 开始分配（tool 子域范围 380-389）
3. **Composition Root 注册模式** — `register_port()` 使用 lambda 工厂函数或字符串延迟加载
4. **InMemoryToolRepository 模式** — MVP 阶段使用内存仓储，后续可替换为 PostgreSQL
5. **StrategicToolCatalog 常量模式** — 23 种工具元数据定义为常量列表，启动时批量注册

**应用到本故事:**
- [ ] Tool 实体增强使用 object.__setattr__ 绕过 frozen dataclass 限制（如需）
- [ ] ToolExecutionEngine 使用 SCOPED 生命周期（每次请求独立实例）
- [ ] 新端口在 composition_root.py 中注册，遵循现有注册模式（单端口 `tool_service` + `skill_loader`）
- [ ] 领域层零外部依赖，ToolService Protocol 定义在 domain 层
- [ ] Skills 加载抽象为 application port（`SkillLoaderPort`），L3 脚本执行仍走 SandboxExecutor

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | kimi-k3 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-09-02 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-1-strategic-tool-registration-tools.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1a-strategic-tool-impl.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/entities/tool.py` - Tool 实体增强
- `src/domain/services/tool_service.py` - ToolService Protocol
- `src/domain/value_objects/tool_execution.py` - ToolCall/ToolResult/ToolEvidence
- `src/application/services/tool_execution_engine.py` - ToolExecutionEngine
- `src/application/use_cases/strategic_analysis.py` - StrategicAnalysisUseCase
- `src/application/skills/` - Skills 三级加载系统
- `tests/unit/domain/entities/test_tool.py` - Tool 实体测试
- `tests/unit/domain/value_objects/test_tool_execution_values.py` - 值对象测试
- `tests/contracts/test_port_contract_tool_service.py` - 端口契约测试
- `tests/unit/application/services/test_tool_execution_engine.py` - 引擎测试
- `tests/unit/application/use_cases/test_strategic_analysis_usecase.py` - 用例测试
- `tests/unit/application/skills/test_skills_loader.py` - Skills 加载测试
- `tests/unit/architecture/test_arch_strategic_tool_impl.py` - 架构验证测试
- `tests/integration/test_integration_strategic_tool_impl.py` - 集成测试
- `tests/acceptance/test_acceptance_strategic_tool_impl.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_strategic_tool_impl.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1a |
| **Story Key** | 4-1a-strategic-tool-impl |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1a-strategic-tool-impl.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具执行能力 |
| **优先级** | P0-2 |
| **覆盖 FR** | FR-ST-02 |

### 完成总结 Completion Summary

1. [x] 所有任务定义完成（9 个 Task，含 Task 0 SDD 规范）
2. [x] 所有验收标准已定义（AC-1 ~ AC-7）
3. [x] 架构约束已提取
4. [x] 前一个故事学习经验已整合
5. [x] 状态设置为 `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes

| # | 轮次 | 问题 | 严重度 | 修复方案 |
|---|------|------|--------|----------|
| 1 | Round 1 | AC-2/AC-5 方法名与现有 `ToolRegistryServicePort` 实现不一致 | P0 | 将 `list_tools()` → `list_all_tools()`，`list_tools_by_category()` → `get_tools_by_category()`，保持实现源一致性 |
| 2 | Round 1 | 端口表 `tool_execution_engine` 的 interface 与 impl 混同为同一个类 | P0 | 明确 interface 为 `ToolService` Protocol（domain），impl 为 `ToolExecutionEngine`（application） |
| 3 | Round 1 | 组合根注册说明缺少方法/接口对齐 | P0 | 在 Task 7 补充 `composition_root.py` 注册时必须对齐 `list_all_tools/get_tools_by_category` |
| 4 | Round 1 | 缺少 import-linter 与 CI 合规约束说明 | P0 | 新增“架构门禁”约束：实现 Task 7 后必须执行 `poetry run lint-imports` 并在文档 DoD 中登记 |
| 5 | Round 1 | coverage 门禁描述分散，易误导实现优先级 | P0 | 在 Test Requirements 中明确 `scripts/check_coverage_gates.py` 为分层门禁判定源，CI 同时执行 `--fail-under=80` |
| 6 | Round 2 | Skill 加载系统缺少可测端口定义 | P0 | 新增 `SkillLoaderPort`（application port）并补充 `load_skill_summary/load_skill_full` 接口 |
| 7 | Round 2 | ToolExecuted 事件字段扩展范围不清晰 | P0 | 明确“本 Story 不修改事件 schema”，ToolEvidence 仅用于 ToolResult 本地证据包 |
| 8 | Round 3 | observe/validate 输出未标准化 | P0 | 统一 observe 输出（observed_output/anomalies/trends），validate 输出（validation_result/issues/confidence） |
| 9 | Round 3 | AC-5 事件发布语义含糊 | P0 | 明确“仅 success 路径发布事件，失败路径抛异常；失败结果记录在证据包” |
| 10 | Round 3 | Task5 依赖清单不完整 | P0 | 构造器显式声明 tool_registry/tool_service/skill_loader/event_publisher 四端口 |
| 11 | Round 4 | AC-6 23 份完整 SOP 不符合 MVP 可执行性 | P0 | 改为“至少 3 份完整 SOP + 其余模板占位”，降低首版交付风险 |
| 12 | Round 4 | AC-7/Task7 端口名仍引用 tool_execution_engine | P0 | 统一为 tool_service + skill_loader 双端口注册 |
| 13 | Round 5 | 文档核心任务仍列出 list_tools/list_tools_by_category | P0 | 全文统一为 list_all_tools/get_tools_by_category，消除术语漂移 |
| 14 | Round 5 | AC-5 缺少 SkillLoaderPort 调用链路 | P0 | 补充 skill_loader 在 use case 中的调用与注入规则 |
| 15 | Round 5 | AC-7 THEN 描述未与端口表闭合 | P0 | 将 tool_execution_engine 替换为 skill_loader，保持一致性 |

---

### 🔍 代码审查发现 Review Findings

**审查日期:** -
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策

- [ ] - 待填写

#### 已修复

- [ ] - 待填写

#### 已推迟

- [ ] - 待填写

---

### 下一步

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-09-02
**最后更新/Last Updated:** 2026-09-02
**更新说明/Description:**
- v1.0.0: 创建故事文件 — 战略工具实现，Epic 4 第二个 P0 故事
