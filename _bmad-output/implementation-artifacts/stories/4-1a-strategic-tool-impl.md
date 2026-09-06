# Story 4.1a: 战略工具实现

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** 将已注册的 23 种战略工具从"目录条目"转化为"可执行工具"——实现领域模型、执行引擎、Skills SOP 和完整调用链路,
**So that** Agent 可以按照 Think→Code→Execute→Observe→Validate 标准工作流调用工具完成战略分析。

### 业务价值

**业务价值：** Story 4.1 仅注册工具元数据，本 Story 补齐 ToolExecution 聚合根、ToolExecutionService（应用层）、ToolExecutionEngine、StrategicAnalysisUseCase 和 Skills 静态资源骨架（TOOLS.md + SKILL.md ×23 + skill_manifest）。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱

### ⚠️ Story 范围澄清（重要）

**本 Story 范围（4.1a）：**
1. Tool 聚合根元数据字段增强（rule_version, reliability_score, execution_count）
2. **新建 ToolExecution 聚合根**（含 ToolExecutionState 5 状态机），与 Tool 生命周期字段解耦
3. ToolExecutionService（应用层）+ Port 抽象（避免与 ToolRegistryService 命名冲突）
4. ToolCall / ToolResult / ExecutionContext 值对象
5. ToolExecutionEngine 五阶段工作流（Think→Code→Execute→Observe→Validate）
6. StrategicAnalysisUseCase 编排
7. Skills 静态资产骨架（TOOLS.md + 23 份 SKILL.md + skill_manifest.py）+ SkillsLoader Port

**不在本 Story 范围（拆分到其他 Story）：**
- **SkillSelector**（基于 L1 元数据推荐 Top-K）→ **Story 5.2**（epics_v1.0.md:1287）
- **ToolExecutorAutoInvocation**（Auto-Invoke Pipeline 集成）→ **Story 4.7**（epics_v1.0.md:774）
- **Skills 准确性 ≥85% / 误触发 ≤5% 验收** → **Story 5.9**（epics_v1.0.md:2358）
- **Tool Execution Engine 的生产级沙箱集成**（Jupyter Kernel 持久化）→ **Story 4.8**（architecture.md §17.2.4）

**架构文档依据：** `docs/architecture/architecture.md:2286-2296` 明确"Skills 系统实现路径详见 Epic 5 蓝图（Story 5-2 ~ 5-9）"——本 Story 仅完成 Skills 系统骨架，避免与 Story 5.2 SkillSelector 职责冲突。

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

> 本 Story 实施过程中**严格遵守**以下硬约束，违反任何一项需返回 `draft` 状态重新设计。

### 领域零依赖（FR-AR-01）

- `src/domain/` 禁止 import 任何第三方包（langgraph/prefect/fastapi/pydantic/sqlalchemy/typer/redis/qdrant/minio/neo4j/aio_pika/litellm/instructor 等）
- 禁止 import `src.application` / `src.interfaces` / `src.infrastructure`
- `.importlinter` 强制校验：`poetry run lint-imports`

### 异常体系强制（sisys-uni-exception-design.md）

- **禁止** `raise ValueError(...)`
- **禁止** 手动 `raise HTTPException(...)`
- **禁止** 继承内置 `Exception`（除 `DomainError` 基类）
- **必须** 走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前**三条 grep 自查**必须零输出：`grep -rn "raise ValueError\|raise HTTPException\|class.*Exception\b" src/`

### 新增异常完整性 Checklist（4 项强制）

1. **定义文件**：在 `src/domain/exceptions/tool_exceptions.py`（或其他子域文件）创建异常类
2. **`_code_ranges.py` 子域映射**：在 `_CLASS_TO_SUBDOMAIN` 注册 class → 子域对应
4. **`__init__.py` 暴露**：在 `src/domain/exceptions/__init__.py` 导入并加入 `__all__`
4. **子域码段校验**：异常 `code` 在子域分配范围内（如 tool 子域 380-389）

### 抑制告警禁止

- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释
- **禁止** mypy 配置 `ignore_missing_imports=true` 豁免
- 第三方库缺类型注解时**必须**创建 PEP 561 stubs（`stubs/<package>/__init__.pyi`）

### Commit & Push 规范

- **禁止** commit 信息含 AI 辅助署名（`Co-Authored-By: Claude` / `anthropic.com` 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 已合入的架构依赖规则
- **禁止** 修改已合入的 alembic migration（只允许新增）

---

## 🎯 领域异常契约（CLAUDE.md §5 强制）

> 本 Story 涉及的所有异常必须在 Task 0 完成前完成 4 项 Checklist。

### 已使用异常（Story 4.1 已实现）

| 异常类 | code | parent | 触发场景 | 4项 Checklist |
|--------|------|--------|----------|--------------|
| `ToolNotFoundError` | EXCEPTION_380 | `NotFoundError` (EXCEPTION_202) | 通过 tool_id/name 查不到 Tool | ✅ 定义文件 / ✅ _code_ranges.py / ✅ __init__.py / ✅ 380 子域 |
| `ToolAlreadyExistsError` | EXCEPTION_381 | `ConflictError` (EXCEPTION_203) | 注册 Tool 时重复 | ✅ 定义文件 / ✅ _code_ranges.py / ✅ __init__.py / ✅ 381 子域 |

### 候选新增异常（本 Story Task 0 评估）

| 候选异常 | 触发场景 | 建议 code | 子域 | 4项 Checklist 计划 |
|----------|----------|-----------|------|--------------------|
| `ToolExecutionFailedError` | ToolExecutionEngine 五阶段任一阶段失败（不可重试） | EXCEPTION_382 | tool (380-389) | Task 0 实现 |
| `ToolExecutionRetryExhaustedError` | 重试 3 次后仍失败 | EXCEPTION_383 | tool (380-389) | Task 0 实现 |
| `ToolExecutionStateTransitionError` | ToolExecutionState 非法迁移（如 IDLE→COMPLETED 跳过中间态） | EXCEPTION_384 | tool (380-389) | Task 0 实现 |
| `ToolExecutionTimeoutError` | Tool 执行超过 `RetryPolicy.max_total_duration_sec` | EXCEPTION_385 | tool (380-389) | Task 0 实现 |
| `EvidenceValidationFailedError` | EvidencePackage 完整性校验失败（缺 plan/code/confidence 等必填字段） | EXCEPTION_386 | tool (380-389) | Task 0 实现 |
| `SkillNotFoundError` | 通过 tool_name 查不到对应 SKILL.md（skill_manifest.py 缺失映射） | EXCEPTION_387 | tool (380-389) | Task 0 实现 |
| `SkillLoadError` | SKILL.md 文件读取/解析失败（IO 错误、YAML frontmatter 格式错误） | EXCEPTION_388 | tool (380-389) | Task 0 实现 |
| `ToolResultValidationError` | ToolResult.status=invalid 需附加上下文（与 `EntityBusinessRuleError` 区分） | EXCEPTION_389 | tool (380-389) | Task 0 实现 |

**tool 子域（380-389）剩余码位**：8 个码位全部使用，新增异常不应超出此范围。

**复用现有异常（非新增）：**
- `ToolNotFoundError` (EXCEPTION_380) 复用：Skill slug 查不到对应 Tool 元数据
- `EntityValidationError` (EXCEPTION_242) 复用：ToolExecutionState 不变量校验
- `LLMAPIError` (EXCEPTION_330) 复用：Think/Code 阶段 LLM 调用失败（可重试异常）
- `LLMResponseError` (EXCEPTION_331) 复用：LLM 响应格式错误（可重试异常）
- `SandboxExecutionError` (EXCEPTION_311) 复用：Execute 阶段沙箱执行失败（可重试异常）

---

## 🎯 测试隔离约束（CLAUDE.md §5 + template.md §4.4）

> 本 Story 所有测试**严格遵守**以下隔离约束，违反任何一项 CI 阻断。

### 测试租户隔离（TestTenant UUID 前缀）

- 所有集成测试 / 验收测试**必须**使用 `TestTenant` 生成 UUID 前缀
- UUID 前缀覆盖五层存储资源：
  - **L1 Redis key**：`test:<uuid>:<key>`
  - **L2 PG schema**：`test_<uuid>` 独立 schema
  - **L3 Qdrant collection**：`test_<uuid>_<collection>`
  - **L4 MinIO bucket**：`test-<uuid>-bucket`
  - **L5 RabbitMQ queue**：`test.<uuid>.<queue>`

### 异步测试约束

- **`asyncio.Lock` 必须声明为类变量**而非实例变量（否则协程间不共享）
- **BDD 步骤函数禁止 `@pytest.mark.asyncio`**（会导致 context data 丢失），统一使用 `event_loop.run_until_complete()`
- pytest-asyncio 使用 **strict mode**，禁止 auto mode 误用

### 集成测试两种子模式（CLAUDE.md §5）

本 Story 集成测试使用以下两种子模式之一：

1. **真实服务 Schema 隔离模式**（推荐）：独立 PG schema + savepoint rollback + 租户隔离 bucket
   - 适用：ToolExecutionEngine 端到端链路、StrategicAnalysisUseCase 端到端
2. **Mock 工厂模式**（例外）：`AsyncMock(spec=ProtocolClass)` + `_make_*()` 工厂函数
   - 适用：LLMClientPort 真实调用涉及 API Key 成本场景

### 测试数据清理

- **禁止** 手动 `delete` / `truncate` 任何数据库表
- 使用 savepoint rollback 自动清理（推荐）或 TestTenant UUID 前缀隔离（自清理）

### 验证测试禁止 Mock

- **验收测试禁止 mock**（CLAUDE.md §5）
- 强制使用 `scenarios() + context dict + 真实服务实例 + pytest.skip()` 动态跳过
- 集成测试 mock 仅在"无安全清理的纯基础设施"场景例外

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Tool 聚合根元数据字段增强 + ToolExecution 聚合根与状态机

**Given** Tool 实体（生命周期）和 Tool 执行（运行时）是两个不同维度的概念
**When** 增强 Tool 元数据字段并新建 ToolExecution 聚合根
**Then**

**Part A - Tool 元数据字段增强**：
- Tool 实体新增 `rule_version: str`（业务规则版本，如 "BLM-v3.2"）
- Tool 实体新增 `reliability_score: float`（取值 [0.0, 1.0]，基于历史执行成功率）
- Tool 实体新增 `execution_count: int`（单调递增计数，初始 0）
- 新增字段均有不变量校验（`__post_init__` → `validate()`）
- 不变量校验失败抛 `EntityValidationError`（EXCEPTION_242）
- **保持现有 `ToolStatus` 3 值不变**（ACTIVE/DEPRECATED/MAINTENANCE 表示工具生命周期）
- 新增字段以 `Optional` / `default_factory` 形式添加，**不破坏** Story 4.1 已注册的 23 个 TOOL_CATALOG 实例

**Part B - 新建 ToolExecution 聚合根与状态机**：
- 新建 `src/domain/entities/tool_execution.py`
- 新建 `ToolExecutionState` 枚举：`IDLE → PLANNING → EXECUTING → VALIDATING → COMPLETED|FAILED`
- ToolExecution 聚合根字段：`execution_id`、`tool_id`、`state`、`started_at`、`completed_at`、`plan`、`code`、`result`、`evidence_package`、`retry_count`
- 状态机迁移矩阵：仅允许正向迁移（IDLE→PLANNING→EXECUTING→VALIDATING→COMPLETED|FAILED），反向迁移抛 `ToolExecutionStateTransitionError` (EXCEPTION_384)
- 状态机迁移在 `__post_init__` + 显式 `transition_to(new_state)` 方法中校验

**验证标准/Validation Criteria:**
- [ ] Tool 实体 3 个新字段定义完整（rule_version, reliability_score, execution_count）
- [ ] Tool 实体 23 个 TOOL_CATALOG 实例不破坏（向后兼容）
- [ ] ToolExecution 聚合根新建，字段完整
- [ ] ToolExecutionState 枚举 6 个值（IDLE/PLANNING/EXECUTING/VALIDATING/COMPLETED/FAILED）
- [ ] 状态机迁移矩阵正确（仅正向）
- [ ] 非法迁移抛 `ToolExecutionStateTransitionError` (EXCEPTION_384)
- [ ] 使用已有领域异常 + 候选新增异常 4 项 Checklist 通过
- [ ] domain 层零依赖验证通过（`poetry run lint-imports`）

### AC-2: ToolExecutionService 应用层服务接口

**Given** 领域服务编排涉及多端口（LLM/Sandbox/Event）应属应用层
**When** 创建 ToolExecutionService（应用层）+ Port 抽象
**Then**

- **命名空间澄清**：使用 `ToolExecutionService`（非 `ToolService`），与 `ToolRegistryService` 职责明确分工：
  - `ToolRegistryService`（应用层，已存在）：**注册 + 元数据查询**（register_all/get_tool/list_tools/count）
  - `ToolExecutionService`（应用层，本 Story 新建）：**执行编排 + 结果封装**（execute + 委托元数据查询给 RegistryService）
- **路径规范**：
  - 实现：`src/application/services/tool_execution_service.py`
  - Port：`src/application/ports/tool_execution_service.py`
- **Protocol 方法签名**：
  - `async execute(tool_id: UUID, tool_call: ToolCall, context: ExecutionContext) -> ToolResult`
  - `get_tool_metadata(tool_id: UUID) -> Tool`（委托 ToolRegistryService.get_tool）
  - `list_tools_metadata(query: ToolListQuery) -> list[Tool]`（Query Object 模式）
- **依赖注入**：通过 `composition_root.py` 注入 `ToolRegistryServicePort` + `ToolExecutionEngine` + `LLMClientPort` + `SandboxExecutorPort` + `EventBusPort`

**验证标准/Validation Criteria:**
- [ ] ToolExecutionService 实现位于 `src/application/services/`
- [ ] ToolExecutionServicePort Protocol 位于 `src/application/ports/`
- [ ] execute() 签名使用 ExecutionContext（frozen dataclass）非 `context: dict`
- [ ] list_tools_metadata(query: ToolListQuery) 使用 Query Object 模式（CLAUDE.md §4 端口查询参数决策规则）
- [ ] 协议方法签名完整，与 ToolRegistryServicePort 职责无重叠
- [ ] 依赖通过端口注入，不导入 infrastructure 具体实现

### AC-3: ToolCall / ToolResult / ExecutionContext 值对象

**Given** 工具执行需要结构化输入/输出/上下文
**When** 创建值对象
**Then**

- **路径**：`src/domain/value_objects/tool_execution.py`（frozen dataclass）
- **ToolCall**：`tool_id: UUID`、`arguments: dict[str, Any]`（符合 Tool.input_schema）、`tenant_id: UUID`
- **ExecutionContext**（Query Object 模式）：`tenant_id: UUID`、`user_id: UUID`、`session_id: str`、`trace_id: str`、`timeout_sec: float = 60.0`
- **ToolResult**：`tool_id: UUID`、`status: ToolResultStatus`、`output: dict`、`evidence_package: EvidencePackage`、`started_at: datetime`、`completed_at: datetime`
- **ToolResultStatus 枚举 4 值**：`success` / `failed` / `invalid` / `insufficient_data`
  - `success`：执行成功且产出完整
  - `failed`：执行失败（沙箱/LLM/校验失败，已重试 3 次）
  - `invalid`：输入参数不符合 Tool.input_schema（DDL 校验失败，**不进入**重试）
  - `insufficient_data`：输入数据不充分（如 LLM 反馈缺关键信息，可重试）
- **EvidencePackage 字段**（8 字段统一）：`input_hash`、`rule_version`、`plan`、`code`、`result`、`observation`、`validation`、`confidence`、`citations`
  - 与 AC-1 字段对齐（plan/code/observation/validation 来自 ToolExecutionEngine 五阶段）

**验证标准/Validation Criteria:**
- [ ] ToolCall / ExecutionContext / ToolResult 三个值对象定义完整（frozen dataclass）
- [ ] ToolResultStatus 枚举 4 值边界文档化
- [ ] EvidencePackage 8 字段统一（与 AC-1 + AC-4 一致）
- [ ] ToolResult 完整性校验（必填字段缺失抛 `EvidenceValidationFailedError` EXCEPTION_386）
- [ ] `test_tool_execution_values.py` 单元测试完整覆盖 3 个值对象

### AC-4: ToolExecutionEngine 标准工作流

**Given** 工具需要按标准流程执行
**When** 实现 ToolExecutionEngine
**Then**

- **路径**：`src/application/services/tool_execution_engine.py`
- **五阶段工作流**：Think → Code → Execute → Observe → Validate
- **五阶段端口映射**：

| 阶段 | 端口方法 | 输入 | 输出 | 失败可重试 |
|------|----------|------|------|------------|
| **Think** | `LLMClientPort.structured_generate(prompt, response_schema=PlanSchema)` | SKILL.md + ToolCall.arguments | `plan: str` | ✅（LLMAPIError/LLMResponseError） |
| **Code** | `LLMClientPort.structured_generate(prompt, response_schema=CodeSchema)` | plan + input_schema | `code: str` | ✅（LLMAPIError/LLMResponseError） |
| **Execute** | `SandboxExecutorPort.execute_code(session_id, code)` | session_id + code | `result: str` | ✅（SandboxExecutionError/TimeoutError） |
| **Observe** | `SandboxExecutorPort.execute_code(session_id, observation_code)` | session_id | `observation: str` | ✅（SandboxExecutionError） |
| **Validate** | `LLMClientPort.structured_generate(prompt, response_schema=ValidationSchema)` | result + observation + output_schema | `validation: ValidationResult` | ✅（LLMAPIError） |

- **RetryPolicy**（frozen dataclass）：
  - `max_attempts: int = 3`
  - `backoff_strategy: Literal["exponential", "linear", "constant"] = "exponential"`
  - `initial_delay_sec: float = 1.0`
  - `max_delay_sec: float = 30.0`
  - `max_total_duration_sec: float = 120.0`
  - `retryable_exceptions: tuple[type[Exception], ...] = (LLMAPIError, LLMResponseError, SandboxExecutionError, TimeoutError)`
- **Session 管理**：通过 `SandboxExecutorPort.start_container(session_id)` / `stop_container(session_id)` 生命周期管理
- **证据包双轨存储**：
  - 结构化字段（input_hash, rule_version, confidence, citations）→ L2_rdb PostgreSQL
  - 大文本字段（plan, code, result, observation, validation）→ L4_object MinIO
- **失败处理**：3 次重试耗尽抛 `ToolExecutionRetryExhaustedError` (EXCEPTION_383)，超过 `max_total_duration_sec` 抛 `ToolExecutionTimeoutError` (EXCEPTION_385)

**验证标准/Validation Criteria:**
- [ ] ToolExecutionEngine 实现位于 `src/application/services/`
- [ ] 五阶段端口映射表覆盖完整（Think/Code/Execute/Observe/Validate）
- [ ] RetryPolicy frozen dataclass 实现完整
- [ ] 沙箱 session 生命周期管理（start_container → execute_code → stop_container）
- [ ] 重试机制实现（最多 3 次，指数退避）
- [ ] 证据包双轨存储（L2_rdb + L4_object）
- [ ] LLMClientPort / SandboxExecutorPort 集成正确

### AC-5: StrategicAnalysisUseCase 用例编排

**Given** 应用层需要编排工具执行流程
**When** 实现 StrategicAnalysisUseCase
**Then**

- **路径**：`src/application/use_cases/strategic_analysis.py`
- **编排流程**：`tool_name 查询 → Skill 加载 → ToolExecutionService.execute → ToolExecuted 事件发布`
- **依赖注入**：通过 `composition_root.py` 注入 `ToolRegistryServicePort`、`SkillLoaderPort`、`ToolExecutionService`、`EventBusPort`
- **SkillLoaderPort 抽象**（六边形约束）：`src/application/ports/skill_loader.py`
  - `async load_metadata(tool_name: str) -> ToolMetadata`（L1）
  - `async load_sop(tool_name: str) -> SkillDocument`（L2）
  - `async load_references(tool_name: str, ref_name: str) -> bytes`（L3）
- **Skill 加载失败异常路径**：复用 `ToolNotFoundError` (EXCEPTION_380) 携带 slug 上下文 / 新增 `SkillNotFoundError` (EXCEPTION_387)
- **事件双通道配置**：ToolExecuted 事件**已存在**（`src/domain/events/tool_events.py:15-37`），当前仅 reliable 单通道（`configs/event_channels.yaml:84-87`）。本 Story 同步更新为**双通道**（realtime Redis pub/sub + reliable RabbitMQ）：
  - 更新 `configs/event_channels.yaml:84-87` 添加 `redis_channel: sisys.events.realtime.tool_executed`
  - 更新 `ChannelRouter.DEFAULT_MAPPINGS` (`src/infrastructure/messaging/channel_router.py:132-137`) 添加 realtime 通道

**验证标准/Validation Criteria:**
- [ ] StrategicAnalysisUseCase 实现位于 `src/application/use_cases/`
- [ ] SkillLoaderPort Protocol 抽象（六边形约束）
- [ ] Skill 加载失败异常路径完整（复用 ToolNotFoundError 或新增 SkillNotFoundError）
- [ ] ToolExecuted 事件**升级为双通道**（realtime + reliable），同步更新 event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS
- [ ] 依赖通过端口注入，不导入 infrastructure 具体实现
- [ ] 异常链路通过 `EventBusPort` 发布（不直接 import Redis/RabbitMQ 客户端）

### AC-6: Skills 三级渐进式加载（仅骨架）

**Given** Skills 系统需要三级加载机制，但 SkillSelector 归属 Story 5.2
**When** 实现 Skills 静态资源骨架 + 加载器
**Then**

**Story 范围声明（本 Story 仅骨架，SkillSelector 留 Story 5.2）：**
- ✅ L1 `TOOLS.md`：23 个工具元数据，<200 tokens
- ✅ L2 `SKILL.md × 23`：每份 <500 行，含适用场景、负向触发、输入/输出字段、步骤、input_examples
- ✅ L3 `scripts/` + `references/`：按需加载（具体内容可后续填充）
- ✅ `skill_manifest.py`：tool_id ↔ slug 双向映射
- ❌ SkillSelector 推荐算法（→ Story 5.2）
- ❌ Skills 准确性 ≥85% 验收（→ Story 5.9）

**23 份 SKILL.md 内容生成策略**：
1. **阶段 1（前置任务）**：建立 SKILL.md 模板（适用场景、负向触发、输入/输出字段、步骤、input_examples 五段式）
2. **阶段 2（代表性 3-5 个）**：挑选代表性工具（不同 category）人工编写 SOP，验证模板有效性
3. **阶段 3（其余 18 份）**：用模板 + LLM 辅助生成，人工 review
4. **阶段 4（验证）**：所有 SKILL.md 通过 `token_count_validator`（<200 tokens 校验）+ `frontmatter_validator`（YAML 格式校验）

**skill_manifest.py 数据源**：
- Tool 实体新增 `slug: str` 字段（kebab-case 命名，如 `pestel-analysis`）
- `src/domain/entities/strategic_tool_catalog.py` 同步更新 23 个 TOOL_CATALOG 实例
- `skill_manifest.py` 通过 `tool_id ↔ slug` 双向映射（`dict[UUID, str]` + `dict[str, UUID]`）

**三级加载触发逻辑**：
- L1（TOOLS.md）：启动时全量缓存（单例 `InMemorySkillLoader`）
- L2（SKILL.md × 23）：按需（tool_name 查询时加载，LRU 缓存 100 项）
- L3（scripts/references）：按需（references 名称查询时加载，无缓存）

**多租户隔离**：L1/L2/L3 **不按 tenant_id 隔离**（Skills 是跨租户共享的业务知识）

**验证标准/Validation Criteria:**
- [ ] TOOLS.md 格式正确（<200 tokens，验证用 tiktoken）
- [ ] SKILL.md × 23 创建完整（每份 <500 行）
- [ ] scripts/references 目录结构正确（占位即可）
- [ ] skill_manifest.py 双向映射完整（23 项）
- [ ] Tool 实体新增 slug 字段 + 23 个 TOOL_CATALOG 同步更新
- [ ] SkillsLoader 实现位于 `src/application/skills/loader.py`
- [ ] SkillLoaderPort Protocol 抽象（六边形约束）

### AC-7: 端口注册与架构约束

**Given** 所有组件需要注册到 composition_root
**When** 注册 tool_execution_service、tool_execution_engine、skill_loader 端口
**Then**

- **`composition_root.py` 注册清单**：
  - `tool_execution_service`：name=`tool_execution_service`, version=`v1.0.0`, interface=`ToolExecutionServicePort`, impl=`ToolExecutionService`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "execution", "service")`
  - `tool_execution_engine`：name=`tool_execution_engine`, version=`v1.0.0`, interface=`ToolExecutionEnginePort`, impl=`ToolExecutionEngine`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "execution", "engine")`
  - `skill_loader`：name=`skill_loader`, version=`v1.0.0`, interface=`SkillLoaderPort`, impl=`InMemorySkillLoader`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("skills", "loader", "inmemory")`
- **impl 路径用字符串实现延迟加载**（CLAUDE.md §6 Gotchas）
- **六边形架构约束**：`poetry run lint-imports` 通过
- **依赖方向矩阵合规**：domain 零依赖 → application → infrastructure → interfaces

**验证标准/Validation Criteria:**
- [ ] 三个新端口注册完整（tool_execution_service / tool_execution_engine / skill_loader）
- [ ] PortSpec 元数据完整（name/version/interface/impl/lifetime/owner/tags 七字段）
- [ ] lifetime 决策合理（三个端口均为 SCOPED，与 ToolRegistryService 对齐）
- [ ] 端口命名空间与现有 tool_repository / tool_registry_service 无冲突
- [ ] 依赖注入正确（impl 字符串延迟加载）
- [ ] 架构约束验证通过（`poetry run lint-imports`）
- [ ] 架构测试 `tests/unit/architecture/test_arch_strategic_tool_impl.py` 覆盖完整

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期（如 `ImportError`、`NameError`） |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**TDD 禁止行为**：
- 禁止先写代码后写测试
- 禁止将测试编写推迟到后续 Task
- 禁止跳过红阶段验证（必须有失败的 pytest 输出作为证据）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Tool 字段增强 + ToolExecution 聚合根与状态机 | Task 1 | Tool 字段 + ToolExecution 实体 + ToolExecutionState 状态机 | `tests/unit/domain/entities/test_tool_41a.py` |
| AC-2 | ToolExecutionService 应用层服务接口 | Task 2 | ToolExecutionService + Port 抽象 | `tests/contracts/test_port_contract_tool_execution_service.py` |
| AC-3 | ToolCall / ToolResult / ExecutionContext 值对象 | Task 3 | 值对象创建 + 4 项 Checklist | `tests/unit/domain/value_objects/test_tool_execution_values.py` |
| AC-4 | ToolExecutionEngine 标准工作流 | Task 4 | 五阶段工作流 + RetryPolicy + 证据包 | `tests/unit/application/services/test_tool_execution_engine.py` |
| AC-5 | StrategicAnalysisUseCase 用例编排 | Task 5 | 用例编排 + SkillLoaderPort + 事件双通道 | `tests/unit/application/use_cases/test_strategic_analysis_usecase.py` |
| AC-6 | Skills 三级渐进式加载（仅骨架） | Task 6 | TOOLS.md + SKILL.md ×23 + skill_manifest.py + Loader | `tests/unit/application/skills/test_skills_loader.py` |
| AC-7 | 端口注册与架构约束 | Task 7 | 端口注册 + PortSpec 元数据 + lint-imports | `tests/unit/architecture/test_arch_strategic_tool_impl.py` |
| **AC-1~AC-7 收尾** | **开发结束验收测试** | **Task 8** | **src + tests 完成清单断言 + 收尾校验** | `tests/acceptance/test_acceptance_strategic_tool_impl.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7

> **目的：** 在进入代码实现前，明确 Schema、接口契约、验收标准、异常契约。这是 SDD 规范驱动的基础。

- [ ] Subtask: 定义 Tool 聚合根新字段 Schema（rule_version, reliability_score, execution_count）
- [ ] Subtask: 定义 ToolExecution 聚合根 + ToolExecutionState 5 状态机 Schema
- [ ] Subtask: 定义 ToolExecutionServicePort Protocol 接口
- [ ] Subtask: 定义 ToolCall / ExecutionContext / ToolResult / ToolResultStatus / EvidencePackage 值对象
- [ ] Subtask: 定义 ToolExecutionEngine 五阶段工作流 + RetryPolicy
- [ ] Subtask: 定义 StrategicAnalysisUseCase + SkillLoaderPort
- [ ] Subtask: 定义 Skills 三级加载 Schema（TOOLS.md / SKILL.md / skill_manifest.py）
- [ ] Subtask: 定义 PortSpec 元数据清单（tool_execution_service / tool_execution_engine / skill_loader）
- [ ] Subtask: **新增异常 8 项 Checklist 实施**（ToolExecutionFailedError / ToolExecutionRetryExhaustedError / ToolExecutionStateTransitionError / ToolExecutionTimeoutError / EvidenceValidationFailedError / SkillNotFoundError / SkillLoadError / ToolResultValidationError）
- [ ] Subtask: **复用异常确认**（ToolNotFoundError / EntityValidationError / LLMAPIError / LLMResponseError / SandboxExecutionError）
- [ ] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_strategic_tool_impl.feature`
- [ ] Subtask: 编写 Gherkin 验收测试 `.py` 步骤实现 `tests/acceptance/test_acceptance_strategic_tool_impl.py`
- [ ] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 8 个新增异常 4 项 Checklist 通过（grep 自查零输出）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Tool 聚合根元数据增强 + ToolExecution 聚合根与状态机

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：Tool 实体元数据字段增强

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_41a.py`（验证 rule_version, reliability_score, execution_count 字段） | `pytest tests/unit/domain/entities/test_tool_41a.py` 失败 |
| 🟢 绿 | 增强 `src/domain/entities/tool.py` 添加新字段（Optional/default_factory） | `pytest tests/unit/domain/entities/test_tool_41a.py` 通过 |
| 🔄 重构 | 添加类型注解、docstring、不变量验证 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Tool 字段增强失败测试
- [ ] Subtask: 🟢 绿 — 实现 Tool 字段增强（不破坏 Story 4.1 的 23 个 TOOL_CATALOG 实例）
- [ ] Subtask: 🔄 重构 — 添加不变量验证（reliability_score ∈ [0.0, 1.0], execution_count ≥ 0）

#### TDD 循环 B：ToolExecution 聚合根 + ToolExecutionState 状态机

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_41a.py`（验证 ToolExecution 聚合根 + 5 状态机转换：IDLE→PLANNING→EXECUTING→VALIDATING→COMPLETED/FAILED） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/tool_execution.py` 实现 ToolExecution + ToolExecutionState | `pytest` 通过 |
| 🔄 重构 | 添加状态迁移矩阵、不变量验证、`transition_to()` 方法 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolExecution 失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolExecution + ToolExecutionState
- [ ] Subtask: 🔄 重构 — 添加状态迁移矩阵验证

**完成标准/Definition of Done:**
- [ ] Tool 实体 3 个新字段完整（不破坏 23 个 TOOL_CATALOG 实例）
- [ ] ToolExecution 聚合根 + ToolExecutionState 6 值（IDLE/PLANNING/EXECUTING/VALIDATING/COMPLETED/FAILED）
- [ ] 状态机迁移矩阵正确（仅正向）
- [ ] 非法迁移抛 `ToolExecutionStateTransitionError` (EXCEPTION_384)
- [ ] domain 层零依赖验证通过
- [ ] 所有测试通过
- [ ] 覆盖率 ≥90%（domain 层）

---

### Task 2: ToolExecutionService 应用层服务接口定义

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环：ToolExecutionService Protocol + 实现

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_port_contract_tool_execution_service.py`（验证 Protocol 方法签名 + Query Object 模式） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/ports/tool_execution_service.py` 定义 Protocol + `src/application/services/tool_execution_service.py` 实现 | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、Protocol 约束、依赖注入 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Protocol 失败测试
- [ ] Subtask: 🟢 绿 — 实现 Protocol + Service
- [ ] Subtask: 🔄 重构 — 委托元数据查询给 ToolRegistryService，避免职责重叠

**完成标准/Definition of Done:**
- [ ] ToolExecutionServicePort Protocol 定义完整
- [ ] ToolExecutionService 实现完整
- [ ] execute() 签名使用 ExecutionContext（frozen dataclass）
- [ ] list_tools_metadata(query: ToolListQuery) 使用 Query Object 模式
- [ ] 与 ToolRegistryServicePort 职责无重叠
- [ ] 所有测试通过
- [ ] 覆盖率 ≥90%（应用层）

---

### Task 3: ToolCall / ToolResult / ExecutionContext 值对象创建

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：ToolCall / ExecutionContext 值对象

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_execution_values.py`（验证 ToolCall / ExecutionContext frozen dataclass） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/value_objects/tool_execution.py` 定义 ToolCall + ExecutionContext | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、不变量验证 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolCall / ExecutionContext 失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolCall / ExecutionContext
- [ ] Subtask: 🔄 重构 — 添加不变量验证

#### TDD 循环 B：ToolResult / ToolResultStatus / EvidencePackage 值对象

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_execution_values.py`（验证 ToolResult + EvidencePackage + ToolResultStatus 4 值） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/value_objects/tool_execution.py` 定义 ToolResult + EvidencePackage + ToolResultStatus | `pytest` 通过 |
| 🔄 重构 | 添加 8 字段统一、完整性校验、文档化 ToolResultStatus 4 值边界 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolResult 失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolResult + EvidencePackage + ToolResultStatus
- [ ] Subtask: 🔄 重构 — 添加完整性校验（缺字段抛 `EvidenceValidationFailedError`）

**完成标准/Definition of Done:**
- [ ] ToolCall / ExecutionContext / ToolResult 三个值对象定义完整
- [ ] ToolResultStatus 枚举 4 值边界文档化
- [ ] EvidencePackage 8 字段统一（与 AC-1 + AC-4 一致）
- [ ] 所有测试通过

---

### Task 4: ToolExecutionEngine 标准工作流实现

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：五阶段工作流 + 五阶段端口映射

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_execution_engine.py`（验证 Think→Code→Execute→Observe→Validate 端口映射） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_execution_engine.py` 实现五阶段工作流 | `pytest` 通过 |
| 🔄 重构 | 添加日志、错误处理、Session 生命周期管理 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写五阶段端口映射失败测试
- [ ] Subtask: 🟢 绿 — 实现五阶段工作流
- [ ] Subtask: 🔄 重构 — 添加 RetryPolicy 实施（指数退避，最多 3 次）

#### TDD 循环 B：证据包双轨存储

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_execution_engine.py`（验证证据包双轨存储：结构化字段→L2_rdb, 大文本→L4_object） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_execution_engine.py` 实现证据打包 | `pytest` 通过 |
| 🔄 重构 | 添加证据验证、序列化、双轨存储协调 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写证据包存储失败测试
- [ ] Subtask: 🟢 绿 — 实现证据包双轨存储
- [ ] Subtask: 🔄 重构 — 添加证据验证

**完成标准/Definition of Done:**
- [ ] 五阶段工作流实现完整（端口映射表覆盖）
- [ ] RetryPolicy frozen dataclass 实施
- [ ] SandboxExecutor Session 生命周期管理
- [ ] 重试机制实现（最多 3 次，指数退避）
- [ ] 证据包双轨存储完整
- [ ] 所有测试通过

---

### Task 5: StrategicAnalysisUseCase 用例编排

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：用例编排

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_strategic_analysis_usecase.py`（验证完整流程：tool_name 查询→Skill 加载→ToolExecutionService.execute→ToolExecuted 事件） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/use_cases/strategic_analysis.py` 实现用例 | `pytest` 通过 |
| 🔄 重func | 添加错误处理、日志、事件发布 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写用例失败测试
- [ ] Subtask: 🟢 绿 — 实现用例
- [ ] Subtask: 🔄 重构 — 添加错误处理 + SkillLoaderPort 抽象

#### TDD 循环 B：ToolExecuted 事件双通道配置升级

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_event_channel_config.py`（验证 ToolExecuted 双通道配置） | `pytest` 失败 |
| 🟢 绿 | 更新 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` | `pytest` 通过 |
| 🔄 重构 | 添加双通道投递验证测试 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写双通道配置失败测试
- [ ] Subtask: 🟢 绿 — 升级 ToolExecuted 为双通道（realtime + reliable）
- [ ] Subtask: 🔄 重构 — 添加双通道投递验证

**完成标准/Definition of Done:**
- [ ] StrategicAnalysisUseCase 实现完整
- [ ] SkillLoaderPort Protocol 抽象（六边形约束）
- [ ] Skill 加载失败异常路径完整
- [ ] ToolExecuted 事件**升级为双通道**（realtime + reliable）
- [ ] 依赖通过端口注入
- [ ] 所有测试通过

---

### Task 6: Skills 三级渐进式加载实现（仅骨架）

**关联 AC:** AC-6

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：L1 TOOLS.md

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_skills_loader.py`（验证 TOOLS.md 格式正确，<200 tokens，tiktoken 计数） | `pytest` 失败 |
| 🟢 绿 | 创建 `src/application/skills/TOOLS.md`（23 个工具元数据） | `pytest` 通过 |
| 🔄 重构 | 验证 token 数量 + `token_count_validator` | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 TOOLS.md 格式失败测试
- [ ] Subtask: 🟢 绿 — 创建 TOOLS.md
- [ ] Subtask: 🔄 重构 — 验证 token 数量

#### TDD 循环 B：L2 SKILL.md × 23

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_skills_loader.py`（验证 SKILL.md 格式正确，<500 行/个，含 5 段式：适用场景/负向触发/输入输出/步骤/input_examples） | `pytest` 失败 |
| 🟢 绿 | 创建 `src/application/skills/<slug>/SKILL.md`（23 个，按模板生成策略 4 阶段实施） | `pytest` 通过 |
| 🔄 重构 | 验证行数、内容结构、`frontmatter_validator` | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 SKILL.md 格式失败测试
- [ ] Subtask: 🟢 绿 — 创建 23 个 SKILL.md
- [ ] Subtask: 🔄 重构 — 验证行数 + frontmatter

#### TDD 循环 C：L3 scripts/references

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_skills_loader.py`（验证 scripts/references 目录结构占位） | `pytest` 失败 |
| 🟢 绿 | 创建 `src/application/skills/<slug>/scripts/` 和 `references/` 目录结构 | `pytest` 通过 |
| 🔄 重构 | 验证目录结构 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写目录结构失败测试
- [ ] Subtask: 🟢 绿 — 创建 scripts/references 目录
- [ ] Subtask: 🔄 重构 — 验证目录结构

#### TDD 循环 D：skill_manifest.py + Tool 实体 slug 字段

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_skills_loader.py`（验证 tool_id ↔ slug 双向映射 + Tool.slug 字段） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/tool.py` 添加 slug 字段 + 同步 23 个 TOOL_CATALOG + 创建 `src/application/skills/skill_manifest.py` | `pytest` 通过 |
| 🔄 重构 | 验证映射完整性 + slug 命名规范（kebab-case） | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 skill_manifest 失败测试
- [ ] Subtask: 🟢 绿 — 实现 skill_manifest.py + Tool.slug 字段
- [ ] Subtask: 🔄 重构 — 验证映射完整性

#### TDD 循环 E：SkillsLoader 实现

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_skills_loader.py`（验证 SkillLoaderPort 三方法：load_metadata / load_sop / load_references） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/skills/loader.py` 实现 `InMemorySkillLoader`（L1 启动缓存 / L2 LRU 100 / L3 无缓存） | `pytest` 通过 |
| 🔄 重构 | 验证三级加载触发逻辑 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Loader 失败测试
- [ ] Subtask: 🟢 绿 — 实现 InMemorySkillLoader
- [ ] Subtask: 🔄 重构 — 验证三级加载

**完成标准/Definition of Done:**
- [ ] TOOLS.md 格式正确（<200 tokens）
- [ ] SKILL.md × 23 完整（每份 <500 行，5 段式结构）
- [ ] scripts/references 目录结构正确
- [ ] skill_manifest.py 双向映射完整
- [ ] Tool.slug 字段 + 23 个 TOOL_CATALOG 同步更新
- [ ] InMemorySkillLoader 实现 + SkillLoaderPort Protocol
- [ ] 所有测试通过

---

### Task 7: 端口注册与架构约束验证

**关联 AC:** AC-7

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：端口注册 + PortSpec 元数据

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_arch_strategic_tool_impl.py`（验证 3 个新端口注册元数据：name/version/interface/impl/lifetime/owner/tags 七字段） | `pytest` 失败 |
| 🟢 绿 | 在 `src/composition_root.py` 注册 tool_execution_service / tool_execution_engine / skill_loader | `pytest` 通过 |
| 🔄 重构 | 验证端口注册元数据完整性 + impl 字符串延迟加载 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写端口注册失败测试
- [ ] Subtask: 🟢 绿 — 实现端口注册
- [ ] Subtask: 🔄 重构 — 验证 PortSpec 元数据完整性

#### TDD 循环 B：架构约束验证（lint-imports + 循环依赖检测）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_arch_strategic_tool_impl.py`（验证 domain 层零外部依赖 + 依赖方向矩阵合规 + 循环依赖检测） | `pytest` 失败 |
| 🟢 绿 | 运行 `poetry run lint-imports` 验证通过 + `ruff check --select E` 检测循环依赖 | 全部通过 |
| 🔄 重构 | 添加架构约束文档 + 端口命名空间澄清 | `ruff check + mypy + pytest + lint-imports` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写架构约束失败测试
- [ ] Subtask: 🟢 绿 — 验证架构约束通过
- [ ] Subtask: 🔄 重构 — 添加架构约束文档

**完成标准/Definition of Done:**
- [ ] 三个新端口注册完整（tool_execution_service / tool_execution_engine / skill_loader）
- [ ] PortSpec 元数据七字段完整
- [ ] 依赖注入正确
- [ ] 架构约束验证通过（`lint-imports` + `ruff --select E`）
- [ ] 所有测试通过

---

### Task 8: 开发结束验收测试（CLAUDE.md §5 + template.md §4.5）

**关联 AC:** AC-1 ~ AC-7

> ⚠️ **收尾验证 Task：** 全部实现 Task 完成后，进行最终验收。

#### TDD 循环：src + tests 完成清单断言 + 收尾校验

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_acceptance_strategic_tool_impl.py` 收尾场景（验证 src + tests 完成清单断言） | `pytest` 失败 |
| 🟢 绿 | 全部实现 Task 完成后运行 | `pytest` 通过 |
| 🔄 重构 | 收尾校验：`poetry run pytest` + `poetry run ruff check` + `poetry run mypy` + `poetry run lint-imports` | 全部通过 |

- [ ] Subtask: 🔴 红 — 编写完成清单断言失败测试
- [ ] Subtask: 🟢 绿 — 运行所有测试套件
- [ ] Subtask: 🔄 重构 — 收尾校验（pytest + ruff + mypy + lint-imports）

**完成标准/Definition of Done:**
- [ ] src/ 完成清单断言通过（所有新建文件存在）
- [ ] tests/ 完成清单断言通过（单元/集成/契约/验收/架构 5 类全覆盖）
- [ ] `pytest` 全部通过（单元 + 集成 + 契约 + 验收）
- [ ] `ruff check` 通过
- [ ] `mypy` 通过
- [ ] `lint-imports` 通过
- [ ] 覆盖率门禁达标（domain ≥90% / application ≥85% / 整体 ≥80%）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** Hexagonal Architecture（六边形架构）
- **设计约束:**
  - 领域层零依赖（FR-AR-01）- 领域层不得依赖任何外部框架，仅依赖 Python 标准库与领域模型
  - 依赖方向：基础设施层→应用层→领域层（禁止反向依赖）
  - 仓储模式（FR-AR-04）- 各存储层通过仓储模式向领域层提供统一接口
- **技术栈:** Python 3.11+

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 ADR-001

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Python dataclasses（选中）** | 标准库、零依赖、类型安全、序列化友好 | 需要手动编写验证逻辑 | ✅ 9/10 |
| Pydantic V2 | 验证强大、生态丰富 | 引入外部依赖，违反领域层零约束 | 6/10 |

### 前一个故事学习经验（template.md 强制）

**来源：** [`4-1-strategic-tool-registration-tools.md`](4-1-strategic-tool-registration-tools.md)（Story 4.1，已 done）

**关键学习点：**

1. **InMemoryToolRepository 模式可复用**：Story 4.1 创建的 `InMemoryToolRepository`（`src/infrastructure/storage/inmemory/tool_repository.py`）采用"进程内单例 + UUID 主键"模式，是存储层基础设施的标杆实现。Task 6 InMemorySkillLoader 应借鉴此模式（启动全量缓存 + LRU 淘汰 + 多租户隔离预留）

2. **ToolCategory 枚举双维度设计**：Story 4.1 已将 ToolCategory 拆为 5 个功能分类 + 5 个战略分类（10 值），证明业务复杂时枚举多维度划分的合理性。本 Story AC-6 的 SKILL.md 模板可借鉴"按 category 分组"组织 SOP

3. **Draft-07 Schema 校验机制**：Story 4.1 已为 Tool.input_schema / output_schema 引入 Draft-07 JSON Schema 校验（`tool_registry_service.py`）。本 Story AC-4 五阶段工作流的 Validate 阶段可复用 Draft-07 校验（`ValidationSchema.response_schema` 字段）

4. **PortSpec 元数据规范**：Story 4.1 的 `tool_repository` + `tool_registry_service` 注册（`composition_root.py:2171-2199`）展示了 PortSpec 七字段（name/version/interface/impl/lifetime/owner/tags）的最佳实践。本 Story Task 7 应严格对齐

5. **TOOL_CATALOG 常量数据源**：Story 4.1 的 23 个 TOOL_CATALOG 实例（`src/domain/entities/strategic_tool_catalog.py`）是元数据单一数据源。本 Story AC-6 的 skill_manifest.py 双向映射应与 TOOL_CATALOG 一一对应，避免数据漂移

6. **测试模式参考**：
   - 验收测试：`test_acceptance_strategic_tool_registration.py`（pytest-bdd + scenarios + 真实 InMemoryToolRepository + ToolRegistryService）
   - 单元测试：`test_tool.py`（`_make_tool(**kwargs)` 工厂函数 + TestToolCreation/TestToolCategory/TestToolValidation 三 class）
   - 集成测试：`test_integration_tool_registration.py`（端到端真实服务 Schema 隔离模式）

7. **避免重蹈覆辙**：
   - Story 4.1 已实现的 `tool_id | tool_name` 双查询入口（`get_tool(tool_id=None, tool_name=None)`），本 Story AC-2 的 ToolExecutionService.get_tool_metadata 应直接委托，避免重写查询逻辑
   - Story 4.1 的事件发布（`ToolExecuted`）当前**单通道配置**与 CLAUDE.md §4 双通道约束冲突，本 Story AC-5 Task 5 应升级为双通道

### 已有代码模式参考

**Tool 实体:** `src/domain/entities/tool.py`
- ToolCategory 枚举已定义 10 种（5 功能分类 + 5 战略分类）
- ToolStatus 枚举已定义 3 值（ACTIVE/DEPRECATED/MAINTENANCE，**生命周期状态**，本 Story 不修改）
- Tool 实体已存在，需要增强 3 个新字段（rule_version/reliability_score/execution_count）

**ToolRepositoryPort:** `src/domain/ports/tool_repository.py`
- Protocol 已定义，包含 7 个 CRUD 方法
- **本 Story 不扩展 execute 相关方法**，执行职责由 ToolExecutionService 承担

**ToolRegistryService:** `src/application/services/tool_registry_service.py`
- 已实现 register_all/get_tool/get_tools_by_category/list_all_tools/tool_count
- **本 Story 直接复用**，ToolExecutionService.get_tool_metadata 委托给此服务

**LLMClientPort:** `src/domain/ports/llm_client.py`
- Protocol 已定义，包含 generate, structured_generate, close 方法
- **AC-4 五阶段 Think/Code/Validate 阶段使用 structured_generate**（带 response_schema 参数）

**SandboxExecutorPort:** `src/domain/ports/sandbox_executor.py`
- Protocol 已定义，包含 start_container, execute_code, stop_container 方法（**session 维度**）
- 已有 `DockerSandboxAdapter` 实现（`src/infrastructure/external_services/sandbox/`）

**AgentEnginePort:** `src/domain/ports/agent_engine.py`
- Protocol 已定义（**本 Story 不直接使用**，由 Story 4.7 Auto-Invoke 集成）

### Skills 系统参考（部分骨架，源文件待重建）

**Skills 目录结构现状：** `src/application/skills/`
- 当前子树仅有 `__pycache__` 残留（曾存在 `loader.py` / `frontmatter_validator.py` / `token_count_validator.py`）
- **本 Story 需从零创建**：`__init__.py` + `TOOLS.md` + 23 份 `SKILL.md` + `scripts/` + `references/` + `skill_manifest.py` + `loader.py` + `validators/`

**skill_manifest.py 需求:**
- tool_id ↔ slug 双向映射（`dict[UUID, str]` + `dict[str, UUID]`）
- 23 个工具对应 23 个 slug（kebab-case，如 `pestel-analysis`、`porters-five-forces`、`ansoff-matrix`）
- Tool 实体同步新增 `slug: str` 字段

### ToolExecuted 事件参考

**已定义：** `src/domain/events/tool_events.py:15-37`
- 字段：`tool_id: UUID`、`event_type: str = "ToolExecuted"`、`execution_result: dict`、`cost_audit: dict`、`aggregate_id`、`aggregate_type="Tool"`
- **本 Story AC-5 Task 5 升级为双通道**（realtime + reliable）

---

## 🎯 测试要求与质量门禁

### 覆盖率要求（CLAUDE.md §4）

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain --cov-fail-under=90`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application --cov-fail-under=85`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

**注：** pyproject.toml 当前**未配置分层 `--cov-fail-under`**，Task 8 收尾前需补充：
- `[tool.pytest.ini_options]` addopts 添加 `--cov-fail-under=80`（整体门禁）
- CI workflow 增加分层 pytest-cov 检查（domain ≥90% / application ≥85%）

### 代码质量门禁

- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`poetry run pre-commit run --all-files`）
- [ ] **架构约束验证通过**（`poetry run lint-imports`）
- [ ] **禁止 `# noqa / # type: ignore / # pylint: disable`**（CLAUDE.md §5 红线）
- [ ] **禁止 mypy `ignore_missing_imports=true`**（CLAUDE.md §5 红线，缺类型包必须创建 PEP 561 stubs）

### 测试文件清单

| 测试类型 | 测试文件 | 对应 Task | 真实服务策略 |
|---------|---------|-----------|--------------|
| **单元测试** | `tests/unit/domain/entities/test_tool_41a.py` | Task 1 | Mock 端口 |
| **单元测试** | `tests/unit/domain/value_objects/test_tool_execution_values.py` | Task 3 | Mock 端口 |
| **单元测试** | `tests/unit/application/services/test_tool_execution_engine.py` | Task 4 | Mock LLMClient + SandboxExecutor |
| **单元测试** | `tests/unit/application/use_cases/test_strategic_analysis_usecase.py` | Task 5 | Mock Service + EventBus |
| **单元测试** | `tests/unit/application/skills/test_skills_loader.py` | Task 6 | Mock 文件 IO |
| **端口契约测试** | `tests/contracts/test_port_contract_tool_execution_service.py` | Task 2 | 真实服务（InMemorySkillLoader） |
| **架构约束测试** | `tests/unit/architecture/test_arch_strategic_tool_impl.py` | Task 7 | lint-imports + ruff --select E |
| **集成测试** | `tests/integration/test_integration_strategic_tool_impl.py` | Task 7 | **真实服务 Schema 隔离模式**（TestTenant + savepoint rollback） |
| **验收测试（BDD）** | `tests/acceptance/test_acceptance_strategic_tool_impl.feature` | Task 0 | Gherkin 7 scenario |
| **验收测试（BDD）** | `tests/acceptance/test_acceptance_strategic_tool_impl.py` | Task 8 | **禁止 mock** + 真实服务（InMemorySkillLoader + InMemoryToolRepository + ToolRegistryService + ToolExecutionService + TestTenant） |

---

## 🚀 交付物清单

| 交付物 | 文件路径 | 状态 |
|-------|---------|------|
| **Tool 实体增强** | `src/domain/entities/tool.py` | 增强 3 字段 + slug 字段 |
| **ToolExecution 聚合根** | `src/domain/entities/tool_execution.py` | **待新建** |
| **ToolExecutionService 实现** | `src/application/services/tool_execution_service.py` | **待新建** |
| **ToolExecutionService Port** | `src/application/ports/tool_execution_service.py` | **待新建** |
| **ToolCall / ToolResult / ExecutionContext** | `src/domain/value_objects/tool_execution.py` | **待新建** |
| **ToolExecutionEngine** | `src/application/services/tool_execution_engine.py` | **待新建** |
| **StrategicAnalysisUseCase** | `src/application/use_cases/strategic_analysis.py` | **待新建** |
| **SkillLoaderPort** | `src/application/ports/skill_loader.py` | **待新建** |
| **InMemorySkillLoader** | `src/application/skills/loader.py` | **待新建** |
| **TOOLS.md** | `src/application/skills/TOOLS.md` | **待新建** |
| **SKILL.md × 23** | `src/application/skills/<slug>/SKILL.md` | **待新建** |
| **scripts/** | `src/application/skills/<slug>/scripts/` | **待新建**（占位） |
| **references/** | `src/application/skills/<slug>/references/` | **待新建**（占位） |
| **skill_manifest.py** | `src/application/skills/skill_manifest.py` | **待新建** |
| **token_count_validator** | `src/application/skills/validators/token_count_validator.py` | **待新建** |
| **frontmatter_validator** | `src/application/skills/validators/frontmatter_validator.py` | **待新建** |
| **8 个新增异常** | `src/domain/exceptions/tool_exceptions.py` | Task 0 新增 |
| **端口注册** | `src/composition_root.py` | 注册 tool_execution_service / tool_execution_engine / skill_loader |
| **事件双通道配置** | `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py` | 升级 ToolExecuted 为双通道 |

---

## 📚 参考文档

- [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) - 架构设计文档
- [epics_v1.0.md](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 和 Story 定义
- [sisys-core-domain-design.md](../../docs/architecture/sisys-core-domain-design.md) - 核心领域架构详细设计
- [sisys-implementation-patterns.md](../../docs/architecture/sisys-implementation-patterns.md) - 实现模式参考手册
- [sisys-port-management-design.md](../../docs/architecture/sisys-port-management-design.md) - 端口注册与依赖注入
- [sisys-uni-exception-design.md](../../docs/architecture/sisys-uni-exception-design.md) - **统一异常设计（CLAUDE.md §5 强制）**
- [sisys-test-system-design.md](../../docs/architecture/sisys-test-system-design.md) - 测试系统设计（TestTenant + 隔离约束）

---

## ✅ 完成标准/Definition of Done

- [ ] 所有 AC 验收标准通过（AC-1 ~ AC-7）
- [ ] 所有测试通过（单元测试、集成测试、契约测试、架构测试、验收测试）
- [ ] 覆盖率满足要求（整体≥80%，领域层≥90%，应用层≥85%）
- [ ] 代码质量门禁通过（Ruff、MyPy、import-linter、pre-commit）
- [ ] 端口注册完整（tool_execution_service / tool_execution_engine / skill_loader）
- [ ] 架构约束验证通过（`poetry run lint-imports`）
- [ ] 8 个新增异常 4 项 Checklist 通过（grep 自查零输出）
- [ ] ToolExecuted 事件升级为双通道（realtime + reliable）
- [ ] Commit 信息无 AI 辅助署名（Co-Authored-By: Claude / anthropic.com）
- [ ] 文档更新完成（CLAUDE.md / architecture.md 同步更新）

---

## 🤖 Dev Agent Record（template.md 强制）

### 使用模型

- Claude Code Sonnet 5（开发阶段）
- Claude Code Opus 5（code-review 阶段）

### 调试日志

待 `dev-story` 完成后填充

### 完成清单（标准格式）

待 `dev-story` 完成后填充：

```
[ ] AC-1 ~ AC-7 全部完成
[ ] 7 个 Task + 1 个收尾验收 Task 全部通过
[ ] 覆盖率门禁达标
[ ] 代码质量门禁通过
[ ] 端口注册完整
```

### 文件清单（To Be Created 标准模板）

待 `dev-story` 完成后填充：

```
src/
├── domain/
│   ├── entities/
│   │   ├── tool.py (增强 3 字段 + slug)
│   │   └── tool_execution.py (新建)
│   ├── exceptions/
│   │   └── tool_exceptions.py (新增 8 异常)
│   ├── ports/
│   │   └── (无新增)
│   ├── services/
│   │   └── (无新增，应用层服务)
│   └── value_objects/
│       └── tool_execution.py (新建)
├── application/
│   ├── ports/
│   │   ├── tool_execution_service.py (新建)
│   │   └── skill_loader.py (新建)
│   ├── services/
│   │   ├── tool_registry_service.py (复用)
│   │   ├── tool_execution_service.py (新建)
│   │   └── tool_execution_engine.py (新建)
│   ├── use_cases/
│   │   └── strategic_analysis.py (新建)
│   └── skills/
│       ├── __init__.py (新建)
│       ├── TOOLS.md (新建)
│       ├── loader.py (新建)
│       ├── manifest.py (新建)
│       ├── validators/
│       │   ├── token_count_validator.py (新建)
│       │   └── frontmatter_validator.py (新建)
│       └── <slug>/
│           ├── SKILL.md × 23 (新建)
│           ├── scripts/ (新建占位)
│           └── references/ (新建占位)
├── infrastructure/
│   └── messaging/
│       └── channel_router.py (升级 ToolExecuted 双通道)
└── composition_root.py (注册 3 个新端口)

configs/
└── event_channels.yaml (升级 ToolExecuted 双通道)

tests/
├── unit/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── test_tool_41a.py (新建)
│   │   └── value_objects/
│   │       └── test_tool_execution_values.py (新建)
│   ├── application/
│   │   ├── services/
│   │   │   └── test_tool_execution_engine.py (新建)
│   │   ├── use_cases/
│   │   │   └── test_strategic_analysis_usecase.py (新建)
│   │   └── skills/
│   │       └── test_skills_loader.py (新建)
│   └── architecture/
│       └── test_arch_strategic_tool_impl.py (新建)
├── contracts/
│   └── test_port_contract_tool_execution_service.py (新建)
├── integration/
│   └── test_integration_strategic_tool_impl.py (新建)
└── acceptance/
    ├── test_acceptance_strategic_tool_impl.feature (新建)
    └── test_acceptance_strategic_tool_impl.py (新建)
```

---

## 文档审查修复 / 代码审查发现（template.md 必选）

**Round 1 审查发现（17+ P0 问题）：**

1. ✅ AC-1 Tool 字段增强会破坏 23 个 TOOL_CATALOG 实例 → 修正为 Optional/default_factory
2. ✅ AC-1 状态机语义与 ToolStatus 冲突 → 修正为新建 ToolExecution 聚合根
3. ✅ AC-2 ToolService Protocol 路径违反分层惯例 → 修正为 ToolExecutionService（应用层）
4. ✅ AC-6 Skills 系统归属与 Epic 5 冲突 → 新增"Story 范围澄清"小节
5. ✅ 测试文件不存在 → 修正为 test_tool_41a.py 等命名 + 状态标注
6. ✅ Skills 子树源文件缺失 → 修正为交付物清单标注"待新建"
7. ✅ ToolExecuted 事件单通道违反双通道约束 → AC-5 升级为双通道
8. ✅ pre-commit 路径错误 → Task 5 Task 8 涵盖
9. ✅ 覆盖率门禁未配置 → 测试要求补充分层 --cov-fail-under
10. ✅ ToolService 与 ToolRegistryService 命名重叠 → 重命名为 ToolExecutionService
11. ✅ template.md v2.9.0 强制小节缺失 → 新增"硬约束声明/领域异常契约/测试隔离约束/前一个故事学习经验/Dev Agent Record/Story 范围澄清/任务 8 收尾验收"
12. ✅ CLAUDE.md 硬约束覆盖不足 → 新增"硬约束声明"小节
13. ✅ AC-3 ToolCall.context 类型弱 → 修正为 ExecutionContext frozen dataclass
14. ✅ AC-4 SandboxExecutor 维度错配 → 五阶段端口映射表 + Session 生命周期管理
15. ✅ AC-6 23 份 SKILL.md 内容来源缺失 → 内容生成策略 4 阶段
16. ✅ AC-6 skill_manifest.py 数据源未指定 → Tool 实体新增 slug 字段
17. ✅ AC-6 三级加载触发逻辑未定义 → L1 启动缓存 / L2 LRU / L3 无缓存
18. ✅ 缺 Task 8 开发结束验收测试 → 新增 Task 8

**下一步：** Round 2 - D1 二次调研遗漏点，启动新一轮审查。
