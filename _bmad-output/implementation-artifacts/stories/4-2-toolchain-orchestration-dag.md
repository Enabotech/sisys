# Story 4.2: 工具链编排（DAG）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统编排工具链（DAG 有向无环图），按拓扑顺序调度子任务，支持复杂分析任务的自动化执行,
**So that** Agent 可以定义工具组合（如 `PESTEL → Porter's Five Forces → SWOT-TOWS`）并自动按依赖关系并行调度，支撑复杂战略分析任务。

### 业务价值

Story 4.2 在 Story 4.1a 已实现的 `ToolExecutionEngine` 单工具五阶段工作流基础上，引入 **DAG 工具链编排** 能力：

1. **多工具组合**：单次工具调用升级为工具链编排（多个工具 + 依赖关系），支撑 PESTEL→Porter→SWOT 等组合分析
2. **拓扑调度**：按 DAG 拓扑顺序自动调度，无依赖节点并行执行（提升执行效率 3-10 倍）
3. **DAG 校验**：合法性校验（无环、无重复边、节点存在性），失败即拒绝执行
4. **失败语义**：节点失败时支持 3 种策略（FAIL_FAST 全链终止 / CONTINUE_ON_ERROR 继续后续 / SKIP_DOWNSTREAM 跳过下游）
5. **复用 R1 端口**：`ToolChainDag` 复用 `ToolExecutionServicePort`（Story 4.1a），不破坏既有契约

**业务定位：** Epic 4 战略工具箱的 **工具链层能力**，位于单工具执行（4.1a）之上、Validation Feedback（4.7）之下。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，FR-ST-02
**前置依赖:** Story 4.1a（ToolExecutionEngine 五阶段工作流）/ Story 1.18a（Prefect 工作流引擎 / DAG 概念基础）
**后续依赖:** Story 4.7（Validation Feedback 闭环增强 — 工具链级别失败恢复）/ Story 5.x（多 Agent 协作中复用工具链）

### ⚠️ Story 范围澄清（重要）

**本 Story 范围（4.2）：**

1. `ToolChainDag` 聚合根 + DAG 校验器（DAGValidator，无环 / 无重复边 / 节点存在性 / 拓扑有效性）
2. `ToolChainNode` 实体（节点 + 依赖边 + 输入参数模板 + 节点失败策略）
3. `ToolChainRepositoryPort` 领域层仓储端口（继承 `L2RdbPort[ToolChainDag]`）
4. `ToolChainServicePort` 应用层服务（编排入口） + `ToolChainOrchestrator`（拓扑排序 + 并行调度 + 失败策略实施）
5. `ToolChainRun` 聚合根（运行时实例，追踪每个节点执行状态）
6. `ToolChainExecuted` 领域事件（双通道：realtime + reliable）
7. DAG 编排用例 `RunToolChainUseCase` + Skill 加载 + 事件发布
8. 端口注册 + Alembic migration 012 + 6 端口契约测试 + 架构验证测试

**不在本 Story 范围（拆分到其他 Story）：**

- **动态 DAG 改写**（运行时增删节点）→ **Story 4.7**（Validation Feedback 闭环增强）
- **跨工具链 DAG**（DAG 节点本身是子 DAG）→ 后续 Story 待定
- **DAG 可视化**（前端 Mermaid 渲染）→ 后续 Story 待定（仅提供 JSON Schema）
- **工具链版本管理**（DAG 灰度发布与回滚）→ **Story 4.6**（工具版本管理 V1 扩展）
- **故障补偿 Saga**（DAG 节点失败自动回滚前序）→ 与 Epic 5 SagaOrchestrator 集成时评估

**复用决策（依据 R2 规则）：**

- **R1 复用**：`ToolExecutionServicePort`（Story 4.1a）/ `EventBusPort`（Story 1.3）/ `L2RdbPort[ToolChainDag]`（仓储基座）
- **R2 新建**：`ToolChainServicePort`（应用层组合端口，组合 ToolExecutionService + EventBusPort + ToolChainRepository）
- **R3 实现**：`InMemoryToolChainRepository`（领域仓储）/ `ToolChainOrchestrator`（应用层编排器）

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

1. **定义文件**：在 `src/domain/exceptions/tool_chain_exceptions.py` 创建异常类（**新增** 子域模块，独立于 tool_exceptions.py）
2. **`_code_ranges.py` 子域映射**：在 `_CLASS_TO_SUBDOMAIN` 注册 class → 子域对应（**本 Story 新增 `toolchain` 子域 390-399**）
3. **`__init__.py` 暴露**：在 `src/domain/exceptions/__init__.py` 导入并加入 `__all__`
4. **子域码段校验**：异常 `code` 在 `toolchain` 子域（390-399）范围内

### 抑制告警禁止

- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释
- **禁止** mypy 配置 `ignore_missing_imports=true` 豁免
- 第三方库缺类型注解时**必须**创建 PEP 561 stubs（`stubs/<package>/__init__.pyi`）

### Commit & Push 规范

- **禁止** commit 信息含 AI 辅助署名（`Co-Authored-By: Claude` / `anthropic.com` 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 已合入的架构依赖规则
- **禁止** 修改已合入的 alembic migration（只允许新增，本期新增 migration 012）

---

## 🎯 领域异常契约（CLAUDE.md §5 强制）

> 本 Story 涉及的所有异常必须在 Task 0 完成前完成 4 项 Checklist。

### 已存在异常复用（来自 Story 4.1a）

| 异常类 | code | parent | 触发场景 | 复用方式 |
|--------|------|--------|----------|---------|
| `ToolNotFoundError` | EXCEPTION_380 | `NotFoundError` (EXCEPTION_202) | DAG 节点引用的 tool_id 在 Tool 仓储中查不到 | Task 0 评估 → 复用（不新增） |
| `ToolExecutionFailedError` | EXCEPTION_382 | `BusinessException` | DAG 节点执行五阶段任一阶段失败（不可重试） | 复用 |
| `ToolExecutionRetryExhaustedError` | EXCEPTION_383 | `BusinessException` | DAG 节点重试 3 次后仍失败 | 复用 |
| `EntityValidationError` | EXCEPTION_242 | entity 子域 | DAG 节点字段不变量校验（参数模板 / 失败策略枚举值） | 复用 |
| `EntityBusinessRuleError` | EXCEPTION_244 | entity 子域 | DAG 业务规则违反（如 DAG 节点数 > 上限 / 深度 > 上限） | 复用 |

### 候选新增异常（本 Story Task 0 评估）

**⚠️ 关键决策（Round 1 调研结论）：** **新增 `toolchain` 子域（390-399）**，独立于 tool 子域（380-389）。

**理由**：
1. **职责清晰**：tool 子域聚焦"单工具执行"，toolchain 子域聚焦"DAG 编排"，是不同抽象层级
2. **避免码位耗尽**：tool 子域 380-389 仅 10 个码位，已使用 9 个（含 1 保留 EXCEPTION_384），未来扩展空间有限
3. **项目惯例**：与已有子域划分一致（如 `dictionary` 270-279 与 `archive` 282-289 独立成域）

**子域嵌套声明**（重要，Task 0 必须执行）：
- `toolchain: (390, 399)` ⊂ `external: (301, 399)`（与 `tool: (380, 389)` 同处理方式）
- 物理上 `toolchain` 码位处于 `external` 父范围之内，但语义上独立
- 必须在 `_code_ranges.py` 的 `nested_subdomains` 注册：`"toolchain": "external"`
- 必须在 `sisys-uni-exception-design.md §3.3.2` 表标注"嵌套于 external（语义独立）"

**新增 4 个异常（4 项 Checklist 强制）：**

| 候选异常 | 触发场景 | parent class | code | 子域 | HTTP 映射 |
|----------|----------|--------------|------|------|-----------|
| `ToolChainCycleDetectedError` | DAG 包含循环依赖（A→B→C→A，含自依赖 A→A 作为长度为 1 的环） | `BusinessException` | EXCEPTION_390 | toolchain (390-399) | 422（语义错误） |
| `ToolChainDuplicateNodeError` | DAG 节点重复（同一 node_id 出现两次） | `BusinessException` | EXCEPTION_391 | toolchain (390-399) | 422 |
| `ToolChainNodeNotFoundError` | DAG 边引用的上游节点不存在（如 `B 依赖 X`，但 X 未在 nodes 列表中） | `BusinessException` | EXCEPTION_392 | toolchain (390-399) | 404 |
| `ToolChainExecutionFailedError` | 工具链执行整体失败（FAIL_FAST 策略下首个节点失败后整链终止） | `BusinessException` | EXCEPTION_393 | toolchain (390-399) | 500 |

**HTTP 状态码映射登记**（CLAUDE.md §5 红线延伸）：Task 0 必须在 `ExceptionHandler._http_status_map` 表追加上述 4 个异常的映射（422/422/404/500）。

**toolchain 子域（390-399）剩余码位**：EXCEPTION_394-399 共 6 个码位预留，供后续 Story（4.7 Validation Feedback / 5.x 多 Agent 协作）扩展。

**复用现有异常（非新增）：**
- `EntityValidationError` (EXCEPTION_242) 复用：DAG 节点字段不变量校验（node_id 非空、depends_on 非空、failure_strategy ∈ {FAIL_FAST, CONTINUE_ON_ERROR, SKIP_DOWNSTREAM}）
- `EntityBusinessRuleError` (EXCEPTION_244) 复用：业务规则违反（如 DAG 节点数 > 100 / DAG 深度 > 10 层）
- `EntityStateTransitionError` (EXCEPTION_243) 复用：**ToolChainRunState 非法迁移**（如 PENDING→COMPLETED 跳过 RUNNING）

### 异常登记确认（Task 0 必做项）

**Task 0 必须完成的 3 项异常登记动作：**

1. **`_code_ranges.py` 新增 `toolchain` 子域**（`src/domain/exceptions/_code_ranges.py`）
   - 在 `CODE_RANGES` dict 中追加 `"toolchain": (390, 399)`
   - 在 `_CLASS_TO_SUBDOMAIN` 注册 4 个新异常类

2. **`sisys-uni-exception-design.md §3.3.2` 表补登记 toolchain 子域**
   - 在 `tool` 行（380-389）后追加 toolchain 行：
     ```markdown
     | `toolchain` | 390–399 | ToolChainCycleDetectedError, ToolChainDuplicateNodeError, ToolChainNodeNotFoundError, ToolChainExecutionFailedError 等（DAG 工具链编排异常，独立于 tool） |
     ```

3. **新增模块文件**：`src/domain/exceptions/tool_chain_exceptions.py`
   - 4 个新异常类
   - `__all__` 导出

**4 项 Checklist 自查（CLAUDE.md §5）→ 5 项 Checklist（Round 1 修订扩展）：**
- [ ] Task 0 完成时 `grep -rn "EXCEPTION_390\|EXCEPTION_391\|EXCEPTION_392\|EXCEPTION_393" src/domain/exceptions/` 全部有定义
- [ ] `_CLASS_TO_SUBDOMAIN` 表覆盖 4 个新异常类（`toolchain` 子域 + `nested_subdomains` 注册 `"toolchain": "external"`）
- [ ] `src/domain/exceptions/__init__.py` 导入并 `__all__` 暴露 4 个新异常
- [ ] `tests/unit/domain/exceptions/test_code_ranges.py` 子域码段校验通过（`toolchain` ∈ [390, 399] 且 nested_subdomains 注册）
- [ ] `tests/unit/domain/exceptions/test_error_code_uniqueness.py` 编码唯一性校验通过
- [ ] `sisys-uni-exception-design.md §3.3.2` 表补登记 toolchain 子域（含嵌套关系说明）
- [ ] **第 5 项（Round 1 新增）**：`ExceptionHandler._http_status_map` 表追加 4 个新异常的 HTTP 映射（422/422/404/500）
- [ ] **第 5 项补充**：测试覆盖在 `tests/unit/domain/exceptions/test_tool_exceptions.py` 或新增 `tests/unit/domain/exceptions/test_tool_chain_exceptions.py`（按项目按异常模块命名惯例），断言 4 个新异常的 parent class（MRO chain 含 `BusinessException`）

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

- **`asyncio.Lock` 必须声明为类变量**而非实例变量（CLAUDE.md §6 Gotchas）
- **BDD 步骤函数禁止 `@pytest.mark.asyncio`**（会导致 context data 丢失），统一使用 `event_loop.run_until_complete()`
- pytest-asyncio 当前配置 `asyncio_mode = "auto"`（`pyproject.toml:274`）；本期新增的 BDD 步骤函数统一使用 `event_loop.run_until_complete()`，与 auto mode 不冲突；单元测试可继续使用 `@pytest.mark.asyncio` 装饰器
- **并行 DAG 执行测试**：使用 `asyncio.gather()` 在 async 函数内触发（**禁止** `asyncio.run()` 在 BDD 步骤函数内调用）

### 集成测试两种子模式（CLAUDE.md §5）

本 Story 集成测试使用以下两种子模式之一：

1. **真实服务 Schema 隔离模式**（推荐）：独立 PG schema + savepoint rollback + 租户隔离 bucket
   - 适用：ToolChainOrchestrator 端到端链路、RunToolChainUseCase 端到端
2. **Mock 工厂模式**（例外）：`AsyncMock(spec=ProtocolClass)` + `_make_*()` 工厂函数
   - 适用：ToolExecutionService 真实调用涉及沙箱执行成本场景

### 测试数据清理

- **禁止** 手动 `delete` / `truncate` 任何数据库表
- 使用 savepoint rollback 自动清理（推荐）或 TestTenant UUID 前缀隔离（自清理）

### 验证测试禁止 Mock

- **验收测试禁止 mock**（CLAUDE.md §5）
- 强制使用 `scenarios() + context dict + 真实服务实例 + pytest.skip()` 动态跳过
- 集成测试 mock 仅在"无安全清理的纯基础设施"场景例外

---

## 🌐 API 契约（template.md §4.1.6 强制）

> 本 Story 主要交付应用层用例 + 编排器实现，**不直接暴露 HTTP 端点**。但 ToolChainExecuted 事件订阅契约影响下游订阅者，需在 API 契约小节明确。

### 事件契约（ToolChainExecuted）

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_type` | `str` | 固定为 `"ToolChainExecuted"`（**新增**，区别于 4.1a 的 `ToolExecuted`） |
| `chain_run_id` | `UUID` | **新增字段**，ToolChainRun 聚合根主键 |
| `chain_id` | `UUID` | 关联 ToolChainDag 聚合根 ID |
| `tenant_id` | `UUID` | 多租户隔离 |
| `aggregate_id` | `UUID` | = `chain_run_id` |
| `aggregate_type` | `str` | `"ToolChainRun"` |
| `execution_result` | `dict` | ToolChainRunResult 序列化（node_results + failed_nodes + total_duration_sec） |
| `cost_audit` | `dict` | 成本审计（LLM token 总和、沙箱时长总和、并行加速比） |
| `failure_strategy` | `str` | `"FAIL_FAST"` / `"CONTINUE_ON_ERROR"` / `"SKIP_DOWNSTREAM"` |

### 内部端口契约（非 HTTP）

- `ToolChainServicePort.execute_chain(chain_id, parameters, context) -> ToolChainRunResult`（应用层端口）
- `ToolChainRepositoryPort.save(dag) / list_by_query(query) / save_with_state_version(...)`（领域层仓储端口，继承 `L2RdbPort[ToolChainDag]`）
- `ToolChainDagValidator.validate(dag) -> None`（领域层校验器，**纯函数**，无副作用）

### 契约测试文件

- `tests/contracts/test_event_contract_tool_chain_executed.py`（事件契约：字段必填 + 序列化 + 通道双投递）
- `tests/contracts/test_port_contract_tool_chain_service.py`（端口契约 11 维度）
- `tests/contracts/test_port_contract_tool_chain_repository.py`（端口契约 11 维度）
- `tests/contracts/test_port_contract_tool_chain_dag_validator.py`（领域校验器契约）

---

## 📊 Story Details（template.md §4.6 强制）

| 字段 | 值 |
|------|-----|
| Story ID | `4.2` |
| Story Key | `4-2-toolchain-orchestration-dag` |
| File | `_bmad-output/implementation-artifacts/stories/4-2-toolchain-orchestration-dag.md` |
| Status | `ready-for-dev` |
| Epic | Epic 4: 战略工具箱 |
| 价值组 | 战略决策智能（Executive Decision Intelligence） |
| 优先级 | P0（Epic 4 战略工具箱核心 Story） |
| 估算工作量 | **20-30 人天**（含 5 项 Checklist 异常体系 + Kahn 算法（stdlib `graphlib.TopologicalSorter`）+ 变量插值（`string.Template`）+ 3 种失败策略（含 SKIP_DOWNSTREAM reverse_adj 预计算）+ 4 端口契约测试 + 1 个领域校验器 + Alembic migration 012 + 集成测试 + TDD 完整循环 +30% 缓冲） |
| 覆盖 FR | FR-ST-02（工具链编排，DAG 有向无环图） |
| 前置 Story | 4-1a-strategic-tool-impl（已 ready-for-dev）/ 1-18a-prefect-workflow-integration（已 done） |
| 后续 Story | 4-3-tool-io-schema-validation / 4-7-tool-execution-auto-invocation / 5.x-multi-agent-collaboration |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: ToolChainDag 聚合根 + DAG 拓扑模型

**Given** 复杂分析任务需要多个工具按依赖关系组合执行（如 PESTEL→Porter's→SWOT）
**When** 定义 `ToolChainDag` 聚合根 + `ToolChainNode` 实体
**Then**

- **路径**：`src/domain/entities/tool_chain.py`
- **`ToolChainDag` 字段**（9 项）：
  - `chain_id: UUID`（聚合根主键）
  - `tenant_id: UUID`（多租户隔离）
  - `name: str`（DAG 名称，如 `pestel-to-swot-analysis`）
  - `description: str`（DAG 业务说明）
  - `nodes: tuple[ToolChainNode, ...]`（有序节点列表，不可变）
  - `failure_strategy: FailureStrategy`（DAG 级别失败策略）
  - `max_concurrency: int`（最大并发节点数，默认 5）
  - `created_at: datetime`
  - `updated_at: datetime`
- **`ToolChainNode` 字段**（7 项）：
  - `node_id: str`（DAG 内唯一标识，如 `pestel`）
  - `tool_slug: str`（kebab-case 工具标识，引用 Tool.slug）
  - `depends_on: tuple[str, ...]`（依赖的上游节点 node_id 列表）
  - `arguments_template: dict[str, Any]`（参数模板，支持 `${upstream_node.output.field}` 变量插值）
  - `failure_strategy: FailureStrategy | None`（节点级覆盖策略；None 时使用 DAG 级别策略）
  - `retry_override: RetryPolicy | None`（节点级重试策略覆盖）
  - `skip_on_upstream_failure: bool`（上游失败时是否跳过本节点，默认 `True`）
- **`FailureStrategy` 枚举 3 值**：
  - `FAIL_FAST`：首个节点失败立即终止整链
  - `CONTINUE_ON_ERROR`：节点失败标记后继续执行后续节点
  - `SKIP_DOWNSTREAM`：节点失败时跳过所有下游依赖节点（**推荐默认**）
- **`__post_init__` 职责**：类型校验 + 跨字段不变量（chain_id 非空 UUID、name 非空、nodes 非空、max_concurrency ≥ 1、failure_strategy ∈ 枚举）+ **预计算 `_reverse_adj: dict[str, tuple[str, ...]]`**（反向邻接表，O(V+E) 一次性构建，供 SKIP_DOWNSTREAM BFS 标记下游节点使用，使用 `object.__setattr__` 突破 frozen 限制）
- **不可变设计**：`nodes: tuple`（非 list）+ `@dataclass(frozen=True)`，避免运行时修改破坏 DAG 一致性

**验证标准/Validation Criteria:**
- [ ] `ToolChainDag` 聚合根位于 `src/domain/entities/tool_chain.py`
- [ ] 9 字段完整（chain_id/tenant_id/name/description/nodes/failure_strategy/max_concurrency/created_at/updated_at）
- [ ] `ToolChainNode` 7 字段完整（node_id/tool_slug/depends_on/arguments_template/failure_strategy/retry_override/skip_on_upstream_failure）
- [ ] `FailureStrategy` 枚举 3 值（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）
- [ ] `__post_init__` 触发不变量校验（失败抛 `EntityValidationError` EXCEPTION_242）
- [ ] `nodes: tuple` 不可变设计（无 append/remove 接口）
- [ ] domain 层零依赖验证通过（`poetry run lint-imports`）
- [ ] 单元测试覆盖：`_make_tool_chain_dag()` 工厂函数 + `FailureStrategy` 枚举值验证 + 不变量失败测试

### AC-2: DAG 校验器（拓扑有效性 + 循环检测 + 节点存在性）

**Given** DAG 必须无环 + 节点依赖必须合法
**When** 实现 `ToolChainDagValidator` 领域服务
**Then**

- **路径**：`src/domain/services/tool_chain_dag_validator.py`（领域服务，**纯函数**，无副作用）
- **核心方法**：`validate(dag: ToolChainDag) -> None`
- **3 项校验规则**（**顺序敏感**，前项失败立即抛错）：
  1. **节点唯一性**：所有 `node_id` 不重复（重复抛 `ToolChainDuplicateNodeError` EXCEPTION_391）
  2. **依赖节点存在性**：所有 `depends_on` 引用的 `node_id` 必须在 `nodes` 列表中存在（缺失抛 `ToolChainNodeNotFoundError` EXCEPTION_392）
  3. **无环检测（含自依赖）**：使用 **stdlib `graphlib.TopologicalSorter`**（Kahn 算法 BFS 实现）做拓扑排序 + 环检测；自依赖作为长度为 1 的环被统一捕获；如发现环，使用 DFS 单点调用提取环路径（发现环抛 `ToolChainCycleDetectedError` EXCEPTION_390）
- **算法复杂度**：O(V + E)（V = 节点数，E = 边数）
- **业界参考**：Apache Airflow 用 Kahn + 单独 `nx.find_cycle()` 报路径；Python `graphlib.TopologicalSorter`（3.9+）提供零依赖 Kahn 实现
- **异常上下文**：携带失败详情
  - `ToolChainDuplicateNodeError`：context 含 `duplicate_node_id` / `chain_id`
  - `ToolChainNodeNotFoundError`：context 含 `missing_node_id` / `referenced_by_node_ids: list[str]` / `chain_id`
  - `ToolChainCycleDetectedError`：context 含 `cycle_path: list[str]`（环路径节点列表）/ `chain_id`

**验证标准/Validation Criteria:**
- [ ] `ToolChainDagValidator` 位于 `src/domain/services/`（**纯函数**，无外部依赖）
- [ ] 4 项校验规则顺序正确（前项失败立即抛错）
- [ ] stdlib `graphlib.TopologicalSorter`（Kahn 算法）实现环检测
- [ ] 算法复杂度 O(V + E) 验证（基准测试：100 节点 200 边 < 10ms）
- [ ] 异常上下文携带失败详情（duplicate_node_id / missing_node_id / cycle_path）
- [ ] 单元测试覆盖：正常 DAG / 重复节点 / 缺失依赖 / 自依赖 / 简单环（A→B→A）/ 复杂环（A→B→C→D→B）/ 多环（A→B→A, C→D→E→C）

### AC-3: ToolChainRepository 端口（六边形仓储模式）

**Given** `ToolChainDag` 需要持久化定义 + 历史
**When** 创建 `ToolChainRepositoryPort`（领域层仓储端口）
**Then**

- **路径**：`src/domain/ports/tool_chain_repository.py`（**领域层**，非应用层）
- **基类**：**继承** `L2RdbPort[ToolChainDag]`（`src/domain/ports/l2_rdb.py:20` 泛型 async CRUD 基座）+ 领域扩展方法
- **同步/异步一致性**：L2RdbPort 是 async 基类，所有方法必须 `async def`
- **查询方法使用 Query Object 模式**（CLAUDE.md §4 端口查询参数决策规则）：
  ```python
  @dataclass(frozen=True)
  class ToolChainDagQuery:
      """ToolChainDag 查询值对象"""
      tenant_id: UUID | None = None
      name: str | None = None
      min_nodes: int | None = None  # 至少包含 N 个节点
      max_nodes: int | None = None  # 最多包含 N 个节点
      offset: int = 0
      limit: int = 100

  @runtime_checkable
  class ToolChainRepositoryPort(L2RdbPort[ToolChainDag], Protocol):
      """工具链仓储端口协议（领域层）

      继承 L2RdbPort[ToolChainDag] 泛型 async CRUD 基座：
      - async def get_by_id(id) -> ToolChainDag | None
      - async def save(entity) -> ToolChainDag
      - async def delete(id) -> None
      - async def list_all() -> list[ToolChainDag]

      领域扩展：
      - async def list_by_query(query) -> list[ToolChainDag]
      - async def count(query) -> int
      """
  ```
- **InMemory 实现**：`src/infrastructure/storage/inmemory/tool_chain_repository.py`
  - 复用 Story 4.1a 的 `InMemoryToolExecutionRepository` 模式（dict[UUID, ToolChainDag] + asyncio.Lock 类变量 + frozen dataclass 节点）
- **Alembic migration 012**：`deploy/postgresql/alembic/versions/012_tool_chains.py`
  - `tool_chains` 表（chain_id PK, tenant_id, name, description, nodes JSONB, failure_strategy, max_concurrency, created_at, updated_at）
  - 4 索引：tenant_id / (tenant_id, name) / (tenant_id, failure_strategy) / GIN(nodes JSONB)

**验证标准/Validation Criteria:**
- [ ] `ToolChainRepositoryPort` 定义在 `src/domain/ports/`（非应用层）
- [ ] 查询方法使用 `ToolChainDagQuery` frozen dataclass（CLAUDE.md §4 决策规则）
- [ ] InMemoryToolChainRepository 实现完整（dict + asyncio.Lock 类变量 + 节点 frozen）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_tool_chain_repository.py` 11 维度覆盖
- [ ] `composition_root.py` 注册 `tool_chain_repository` 端口（lifetime=SCOPED）
- [ ] Alembic migration `012_tool_chains.py` 创建（含 4 索引）
- [ ] L2/L4 双轨存储边界（nodes JSONB → L2_rdb；DAG 元数据全在 L2_rdb，无 L4 依赖）

### AC-4: ToolChainRun 聚合根 + 5 状态机

**Given** 工具链运行时需要追踪执行状态、失败节点、并行进度
**When** 新建 `ToolChainRun` 聚合根 + `ToolChainRunState` 状态机
**Then**

- **路径**：`src/domain/entities/tool_chain_run.py`
- **`ToolChainRunState` 枚举 5 值**（删除原 CANCELLED 状态，因本期不实现取消逻辑且无业务触发器，CLAUDE.md §2 简化原则）：
  - `PENDING`：待执行（创建后初始状态）
  - `RUNNING`：正在执行（至少一个节点处于 RUNNING）
  - `COMPLETED`：全部节点成功
  - `COMPLETED_WITH_ERRORS`：部分节点失败但策略允许继续
  - `FAILED`：DAG 级别失败（FAIL_FAST 触发或全部节点失败）
- **状态机迁移矩阵**（沿用 Story 4.1a ToolExecution 模式）：
  ```python
  VALID_TRANSITIONS: dict[ToolChainRunState, set[ToolChainRunState]] = {
      ToolChainRunState.PENDING: {ToolChainRunState.RUNNING},
      ToolChainRunState.RUNNING: {
          ToolChainRunState.COMPLETED,
          ToolChainRunState.COMPLETED_WITH_ERRORS,
          ToolChainRunState.FAILED,
      },
      ToolChainRunState.COMPLETED: set(),  # 终态
      ToolChainRunState.COMPLETED_WITH_ERRORS: set(),  # 终态
      ToolChainRunState.FAILED: set(),  # 终态
  }
  ```
- **CANCELLED 状态延后说明**：如后续 Story（4.7 Validation Feedback / 5.x 多 Agent 协作）需要取消能力，单独 Story 引入 `RequestCancelToolChainUseCase` + `asyncio.CancelledError` 处理器 + HTTP 端点；本期不预留死代码。
- **`ToolChainRun` 字段**（13 项）：
  - `chain_run_id: UUID`（聚合根主键）
  - `chain_id: UUID`（关联 ToolChainDag）
  - `tenant_id: UUID`
  - `state: ToolChainRunState`
  - `started_at: datetime`
  - `completed_at: datetime | None`（终态时必填）
  - `node_runs: dict[str, NodeRunStatus]`（节点运行状态字典：node_id → NodeRunStatus）
  - `failed_nodes: tuple[str, ...]`（失败的节点 node_id 列表）
  - `total_duration_sec: float | None`（实际 wall-clock 耗时，started_at → completed_at）
  - `critical_path_sec: float | None`（关键路径长度，最长路径上各节点耗时求和，理论最大加速比上限）
  - `parallel_speedup_ratio: float | None`（Amdahl 加速比 = `total_work_sec / total_duration_sec`，"相比完全串行加速多少倍"）
  - `failure_strategy: FailureStrategy`（运行时使用的策略快照）
  - `cost_audit: CostAudit`（强类型成本审计，见下方）
  - `state_version: int`（乐观锁版本号）
- **`NodeRunStatus` 值对象**：
  ```python
  @dataclass(frozen=True)
  class NodeRunStatus:
      node_id: str
      state: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"]
      started_at: datetime | None = None
      completed_at: datetime | None = None
      error: str | None = None
      tool_result: dict | None = None  # ToolResult.output 序列化
  ```
- **状态机迁移实现**：`transition_to(new_state)` 方法 + `can_transition_to(new_state)` 校验（复用 4.1a 模式）
- **非法迁移异常**：复用 `EntityStateTransitionError` (EXCEPTION_243)
- **`CostAudit` 强类型值对象**（替换原 `dict[str, Any]`）：
  ```python
  @dataclass(frozen=True)
  class CostAudit:
      llm_prompt_tokens: int = 0
      llm_completion_tokens: int = 0
      llm_total_tokens: int = 0
      sandbox_duration_sec: float = 0.0
      api_calls: int = 0
      parallel_speedup_ratio: float | None = None
      critical_path_sec: float | None = None
      wall_clock_sec: float | None = None
  ```

**验证标准/Validation Criteria:**
- [ ] `ToolChainRun` 聚合根 + `ToolChainRunState` 5 值（PENDING/RUNNING/COMPLETED/COMPLETED_WITH_ERRORS/FAILED；CANCELLED 已删除）
- [ ] 状态机迁移矩阵正确（4 条主链边，无 CANCELLED 兜底）
- [ ] `NodeRunStatus` 值对象 6 字段完整
- [ ] `CostAudit` 强类型值对象 8 字段（避免 `dict[str, Any]` 类型不安全）
- [ ] 非法迁移抛 `EntityStateTransitionError` (EXCEPTION_243)（复用业务异常）
- [ ] 终态必有 completed_at、非终态 completed_at 为 None
- [ ] 单元测试覆盖：状态机迁移矩阵 5 状态所有合法 + 非法迁移

### AC-5: ToolChainOrchestrator 拓扑排序 + 并行调度

**Given** DAG 编排器需按拓扑顺序调度节点，无依赖节点并行执行
**When** 实现 `ToolChainOrchestrator`（应用层服务）
**Then**

- **路径**：`src/application/services/tool_chain_orchestrator.py`（应用层编排器）
- **核心方法**：`async execute_chain(dag: ToolChainDag, parameters: dict, context: ExecutionContext) -> ToolChainRun`
- **算法步骤**（**6 步流程**）：

  1. **DAG 校验**：`ToolChainDagValidator.validate(dag)` → 失败抛相应异常
  2. **拓扑排序**：使用 **Kahn 算法**（BFS + 入度表）生成拓扑序列
     - 返回 `list[str]` 节点 node_id 列表（按执行顺序）
     - 算法复杂度 O(V + E)
  3. **构建执行波次（waves）**：将拓扑序列切分为多个波次
     - wave[0]：所有无依赖节点（入度 = 0）
     - wave[1]：依赖全部在 wave[0] 的节点
     - wave[n]：依赖全部在 wave[0..n-1] 的节点
     - 数据结构：`list[list[str]]`（外层顺序，内层同波可并行）
  4. **波次内并行执行**：使用 `asyncio.gather()` 并发执行同波节点
     - 节点执行调用 `ToolExecutionService.execute(tool_id, tool_call, context)`
     - 异常处理：根据 `failure_strategy` 决定后续行为
  5. **变量插值**：节点 `arguments_template` 中的 `${upstream_node.output.field}` 引用上游节点结果
     - 实现：**stdlib `string.Template` 自定义 delimiter**（`delimiter="${"` + `idpattern=r"[a-zA-Z_][a-zA-Z0-9_.]*"` 限制合法变量名）
     - **禁止** `re.sub(r'\$\{([^}]+)\}', ...)` 正则方案（无法处理嵌套、转义、字符串字面量误匹配）
     - 上游节点未完成 → 引用失败抛 `EntityBusinessRuleError` (EXCEPTION_244)
     - 语法规范：
       - ✅ 支持：`${upstream.output.field}`、`${upstream.output.nested.field}`（最多 3 层嵌套属性）
       - ✅ 支持：`safe_substitute()` 模式（未知变量保留原文本，不抛错）
       - ❌ 禁止：`${upstream.output + other.output}`（禁止表达式计算，安全风险）
       - ❌ 禁止：`${upstream.output.items[index]}`（禁止数组索引）
       - ❌ 禁止：`${condition ? A : B}`（禁止三元表达式）
  6. **ToolChainRun 状态更新**：
     - 启动：PENDING → RUNNING
     - 完成：RUNNING → COMPLETED / COMPLETED_WITH_ERRORS / FAILED
     - 终态：设置 completed_at + 计算 total_duration_sec + parallel_speedup_ratio

- **失败策略实施**：
  - **FAIL_FAST**：节点失败立即抛 `ToolChainExecutionFailedError` (EXCEPTION_393)，终止剩余 wave（**关键**：使用 `raise ... from original` 保留 `ToolExecutionFailedError` 的 `__cause__` 异常链，context 同时保留 `original_error_code`）
  - **CONTINUE_ON_ERROR**：节点失败标记 `NodeRunStatus.FAILED`，继续后续 wave
  - **SKIP_DOWNSTREAM**：节点失败时 BFS 遍历 `_reverse_adj`（**DAG 构建时 O(V+E) 预计算**，见 AC-1）查找所有下游节点，标记为 `NodeRunStatus.SKIPPED`，跳过执行
  - **复杂度实测**：反向邻接表预计算 O(V+E) 一次性；运行时 BFS 下游标记 O(downstream_size)（非 O(F·(V+E))）

- **并发控制**：`max_concurrency` 限制（默认 5）
  - 使用 `asyncio.Semaphore(max_concurrency)` 包裹 `asyncio.gather()`
  - 同波节点数 > max_concurrency 时，分批并发

**验证标准/Validation Criteria:**
- [ ] `ToolChainOrchestrator` 实现位于 `src/application/services/`
- [ ] Kahn 算法实现（BFS + 入度表）
- [ ] 执行波次划分正确（wave[0] 无依赖 → wave[n] 依赖前序波）
- [ ] `asyncio.gather()` 并行执行同波节点
- [ ] `asyncio.Semaphore` 并发控制（max_concurrency）
- [ ] 变量插值（`${upstream_node.output.field}`）正确解析
- [ ] 3 种失败策略（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）正确实施
- [ ] `ToolChainExecutionFailedError` (EXCEPTION_393) 在 FAIL_FAST 时抛出
- [ ] 单元测试覆盖：线性链 / 钻石依赖 / 简单并行 / 复杂并行 / 失败传播 / 变量插值

### AC-6: ToolChainService 应用层服务接口

**Given** 工具链编排入口需要 Protocol 抽象（六边形约束）
**When** 创建 `ToolChainServicePort`（应用层端口）+ `ToolChainService` 实现
**Then**

- **路径**：
  - 实现：`src/application/services/tool_chain_service.py`
  - Port：`src/application/ports/tool_chain_service.py`
- **Protocol 方法签名**：
  ```python
  @runtime_checkable
  class ToolChainServicePort(Protocol):
      """工具链服务端口协议（应用层）"""

      async def execute_chain(
          self,
          chain_id: UUID,
          parameters: dict[str, Any],
          context: ExecutionContext,
      ) -> ToolChainRun:
          """执行工具链（顶层入口）

          Args:
              chain_id: 工具链定义 ID
              parameters: 工具链执行参数
              context: 执行上下文

          Returns:
              ToolChainRun: 运行时实例

          Raises:
              ToolNotFoundError: chain_id 不存在
              ToolChainCycleDetectedError: DAG 包含循环依赖
              ToolChainDuplicateNodeError: DAG 节点重复
              ToolChainNodeNotFoundError: DAG 边引用不存在的节点
              ToolChainExecutionFailedError: FAIL_FAST 触发
          """
          ...

      async def get_chain_definition(self, chain_id: UUID) -> ToolChainDag:
          """获取工具链定义（委托 Repository）"""
          ...

      async def list_chain_definitions(
          self, query: ToolChainDagQuery,
      ) -> list[ToolChainDag]:
          """列出工具链定义（Query Object 模式）"""
          ...
  ```
- **依赖注入**：`ToolChainService.__init__(repository: ToolChainRepositoryPort, orchestrator: ToolChainOrchestrator)`
- **`composition_root.py` 注册**：
  - `tool_chain_service`：name=`tool_chain_service`, version=`v1.0.0`, interface=`ToolChainServicePort`, impl=`ToolChainService`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "chain", "service")`

**验证标准/Validation Criteria:**
- [ ] `ToolChainServicePort` Protocol 定义完整（3 方法）
- [ ] `ToolChainService` 实现完整
- [ ] 依赖通过端口注入（不导入 infrastructure 具体实现）
- [ ] `execute_chain()` 委托 `ToolChainOrchestrator`
- [ ] `get_chain_definition()` / `list_chain_definitions()` 委托 Repository
- [ ] 端口契约测试 `tests/contracts/test_port_contract_tool_chain_service.py` 11 维度覆盖

### AC-7: RunToolChainUseCase + Skill 加载 + ToolChainExecuted 事件

**Given** Agent 调用工具链需要应用层用例编排
**When** 实现 `RunToolChainUseCase`
**Then**

- **路径**：`src/application/use_cases/run_tool_chain.py`
- **编排流程**：
  1. `chain_name` 查询 → 通过 ToolChainRepository 获取 ToolChainDag
  2. 加载 Skill（复用 4.1a `SkillLoaderPort` 7 方法：`load_metadata` / `load_sop` / `load_references` / `load_script` / `match_by_capability` / `match_by_tag` / `match_by_trigger`；本期采用**节点级**加载：每个节点执行前按 `tool_slug` 调用 `load_metadata(tool_name)` 获取 L1 元数据，按需 `load_sop(tool_name)` 懒加载 L2 SOP；多节点元数据使用 `asyncio.gather()` 并发预加载）
  3. `ToolChainService.execute_chain(chain_id, parameters, context)`
  4. `ToolChainRun` 完成 → 发布 `ToolChainExecuted` 事件（**新增**，双通道配置）
- **依赖注入**：通过 `composition_root.py` 注入 `ToolChainRepository` + `ToolChainService` + `SkillLoaderPort` + `EventBusPort`
- **事件双通道配置**：
  - 更新 `configs/event_channels.yaml` 添加 `ToolChainExecuted` 映射（redis_channel + rabbitmq_exchange）
  - 更新 `ChannelRouter.DEFAULT_MAPPINGS` (`src/infrastructure/messaging/channel_router.py:132-137`) 添加 realtime 通道
- **事件载荷**（10 字段，参考 AC-6 节）
- **可靠性评分异步更新**：ToolChainDag 整体 `reliability_score` 和节点级 `execution_count` 由 `ToolChainExecuted` 事件异步更新（最终一致投影）

**验证标准/Validation Criteria:**
- [ ] `RunToolChainUseCase` 实现位于 `src/application/use_cases/`
- [ ] 编排流程完整：chain 查询 → Skill 加载 → execute_chain → 事件发布
- [ ] `ToolChainExecuted` 事件**双通道**配置（realtime + reliable）
- [ ] `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 同步更新
- [ ] 依赖通过端口注入
- [ ] 异常链路通过 `EventBusPort` 发布

### AC-8: 端口注册与架构约束

**Given** 所有组件需要注册到 composition_root
**When** 注册 4 个新端口（tool_chain_repository / tool_chain_dag_validator / tool_chain_orchestrator / tool_chain_service）+ 1 个 ToolChainExecuted 事件通道（非 Port，独立维度）+ 验证架构约束
**Then**

- **`composition_root.py` 注册清单**（**4 个新端口**）：
  - `tool_chain_repository`：name=`tool_chain_repository`, version=`v1.0.0`, interface=`ToolChainRepositoryPort`, impl=`InMemoryToolChainRepository`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "chain", "repository")`
  - `tool_chain_dag_validator`：name=`tool_chain_dag_validator`, version=`v1.0.0`, interface=`ToolChainDagValidatorProtocol`, impl=`ToolChainDagValidator`, lifetime=`SINGLETON`（**纯函数无状态**）, owner=`tool-team`, tags=`("tool", "chain", "validator")`
  - `tool_chain_orchestrator`：name=`tool_chain_orchestrator`, version=`v1.0.0`, interface=`ToolChainOrchestratorProtocol`, impl=`ToolChainOrchestrator`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "chain", "orchestrator")`
  - `tool_chain_service`：name=`tool_chain_service`, version=`v1.0.0`, interface=`ToolChainServicePort`, impl=`ToolChainService`, lifetime=`SCOPED`, owner=`tool-team`, tags=`("tool", "chain", "service")`
- **`ToolChainDagValidatorProtocol`**（领域层校验器协议）：
  ```python
  @runtime_checkable
  class ToolChainDagValidatorProtocol(Protocol):
      """DAG 校验器协议（领域层）"""

      def validate(self, dag: ToolChainDag) -> None:
          """校验 DAG 合法性（无环 + 节点唯一 + 依赖存在）

          Raises:
              ToolChainCycleDetectedError: 循环依赖
              ToolChainDuplicateNodeError: 节点重复
              ToolChainNodeNotFoundError: 依赖节点不存在
          """
          ...
  ```
- **impl 路径用字符串实现延迟加载**（CLAUDE.md §6 Gotchas）
- **六边形架构约束**：`poetry run lint-imports` 通过
- **依赖方向矩阵合规**：domain 零依赖 → application → infrastructure → interfaces

**验证标准/Validation Criteria:**
- [ ] **4 个**新端口注册完整（tool_chain_repository / tool_chain_dag_validator / tool_chain_orchestrator / tool_chain_service）
- [ ] PortSpec 元数据十字段完整（name/version/interface/impl/module/lifetime/owner/**compatibility/tags/deprecated**）；其中 `compatibility=()` 表示向后兼容版本元组、`deprecated=False` 表示未废弃（参考 `src/domain/ports/registry.py:27-53`）
- [ ] lifetime 决策合理（validator = SINGLETON，其余 = SCOPED）
- [ ] 端口命名空间与现有 tool_repository / tool_execution_repository 无冲突
- [ ] 依赖注入正确（impl 字符串延迟加载）
- [ ] 架构约束验证通过（`poetry run lint-imports`）
- [ ] 架构测试 `tests/unit/architecture/test_arch_tool_chain_orchestration_dag.py` 覆盖完整

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离。

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
| AC-1 | ToolChainDag 聚合根 + DAG 拓扑模型 | Task 1 | ToolChainDag + ToolChainNode + FailureStrategy 枚举 | `tests/unit/domain/entities/test_tool_chain_dag_42.py` |
| AC-2 | DAG 校验器（拓扑有效性 + 循环检测） | Task 2 | ToolChainDagValidator + stdlib `graphlib.TopologicalSorter`（Kahn 算法）+ 环路径提取 | `tests/unit/domain/services/test_tool_chain_dag_validator.py` |
| AC-3 | ToolChainRepository 端口（六边形仓储模式）| Task 5 | 仓储端口 + InMemory 实现 + PostgreSQL migration 012 | `tests/contracts/test_port_contract_tool_chain_repository.py` |
| AC-4 | ToolChainRun 聚合根 + 5 状态机 | Task 3 | ToolChainRun + ToolChainRunState + NodeRunStatus | `tests/unit/domain/entities/test_tool_chain_run_42.py` |
| AC-5 | ToolChainOrchestrator 拓扑排序 + 并行调度 | Task 4 | Kahn 算法 + asyncio.gather + 失败策略 | `tests/unit/application/services/test_tool_chain_orchestrator.py` |
| AC-6 | ToolChainService 应用层服务接口 | Task 6 | ToolChainServicePort + ToolChainService 实现 | `tests/contracts/test_port_contract_tool_chain_service.py` |
| AC-7 | RunToolChainUseCase + Skill 加载 + 事件双通道 | Task 7 | 用例编排 + ToolChainExecuted 事件 | `tests/unit/application/use_cases/test_run_tool_chain_usecase.py` |
| AC-8 | 端口注册与架构约束 | Task 8 | 4 端口注册 + PortSpec 元数据 + lint-imports | `tests/unit/architecture/test_arch_tool_chain_orchestration_dag.py` |
| **AC-1~AC-8 收尾** | **开发结束验收测试** | **Task 9** | **src + tests 完成清单断言 + 收尾校验** | `tests/acceptance/test_acceptance_tool_chain_orchestration_dag.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-8

> **目的：** 在进入代码实现前，明确 Schema、接口契约、验收标准、异常契约。这是 SDD 规范驱动的基础。

- [ ] Subtask: 定义 `ToolChainDag` 聚合根 Schema（9 字段）+ `ToolChainNode` 7 字段
- [ ] Subtask: 定义 `FailureStrategy` 枚举（3 值：FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）
- [ ] Subtask: 定义 `ToolChainRun` 聚合根 Schema（13 字段）+ `ToolChainRunState` 5 值状态机 + `NodeRunStatus` 值对象
- [ ] Subtask: 定义 `ToolChainDagValidator` 领域服务接口（4 项校验规则：节点唯一 / 依赖存在 / 无自依赖 / 无环）
- [ ] Subtask: 定义 `ToolChainRepositoryPort` Protocol 接口（继承 `L2RdbPort[ToolChainDag]`）
- [ ] Subtask: 定义 `ToolChainServicePort` Protocol 接口（3 方法：execute_chain / get_chain_definition / list_chain_definitions）
- [ ] Subtask: 定义 `ToolChainDagValidatorProtocol` Protocol 接口（领域层纯函数校验器）
- [ ] Subtask: 定义 `ToolChainOrchestratorProtocol` Protocol 接口（6 步流程：校验 → 拓扑排序 → 波次构建 → 并行执行 → 变量插值 → 状态更新）
- [ ] Subtask: 定义 `ToolChainExecuted` 领域事件 Schema（10 字段，含 chain_run_id / chain_id / failure_strategy）
- [ ] Subtask: 定义 PortSpec 元数据清单（4 个新端口：tool_chain_repository / tool_chain_dag_validator / tool_chain_orchestrator / tool_chain_service）
- [ ] Subtask: **新增异常 4 项 Checklist 实施**（ToolChainCycleDetectedError EXCEPTION_390 / ToolChainDuplicateNodeError EXCEPTION_391 / ToolChainNodeNotFoundError EXCEPTION_392 / ToolChainExecutionFailedError EXCEPTION_393）
- [ ] Subtask: **新增 toolchain 子域 390-399**（更新 `_code_ranges.py` + `sisys-uni-exception-design.md §3.3.2`）
- [ ] Subtask: **复用异常确认**（ToolNotFoundError / ToolExecutionFailedError / ToolExecutionRetryExhaustedError / EntityValidationError / EntityBusinessRuleError / EntityStateTransitionError）
- [ ] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_tool_chain_orchestration_dag.feature`
- [ ] Subtask: 编写 Gherkin 步骤实现 `tests/acceptance/test_acceptance_tool_chain_orchestration_dag.py`
- [ ] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 4 个新增异常 4 项 Checklist 通过（grep 自查零输出）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: ToolChainDag 聚合根 + ToolChainNode + FailureStrategy

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：ToolChainDag 聚合根 + ToolChainNode 实体

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_dag_42.py`（验证 9 字段 + ToolChainNode 7 字段 + 不变量校验） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/tool_chain.py` 实现 `ToolChainDag` + `ToolChainNode` + `FailureStrategy` | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、节点不可变 tuple 设计 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolChainDag 字段增强失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolChainDag + ToolChainNode + FailureStrategy
- [ ] Subtask: 🔄 重构 — 添加不变量验证（chain_id 非空、nodes 非空、max_concurrency ≥ 1、failure_strategy ∈ 枚举）

#### TDD 循环 B：FailureStrategy 枚举 3 值

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_dag_42.py`（验证 FailureStrategy 3 值边界 + 默认值） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/tool_chain.py` 定义 `FailureStrategy(Enum)` | `pytest` 通过 |
| 🔄 重构 | 文档化 3 值语义边界（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM） | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 FailureStrategy 失败测试
- [ ] Subtask: 🟢 绿 — 实现 FailureStrategy 枚举
- [ ] Subtask: 🔄 重构 — 文档化 3 值语义边界

**完成标准/Definition of Done:**
- [ ] ToolChainDag 聚合根 9 字段完整（chain_id/tenant_id/name/description/nodes/failure_strategy/max_concurrency/created_at/updated_at）
- [ ] ToolChainNode 实体 7 字段完整（node_id/tool_slug/depends_on/arguments_template/failure_strategy/retry_override/skip_on_upstream_failure）
- [ ] FailureStrategy 枚举 3 值（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）
- [ ] 不变量校验通过 `__post_init__` 触发（失败抛 `EntityValidationError`）
- [ ] nodes: tuple 不可变设计
- [ ] domain 层零依赖验证通过
- [ ] 所有测试通过
- [ ] 覆盖率 ≥90%（domain 层）

---

### Task 2: ToolChainDagValidator 领域服务（拓扑校验）

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：节点唯一性 + 依赖节点存在性校验（O(V) + O(V·deps)）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_dag_validator.py`（验证节点重复 → EXCEPTION_391 / 缺失依赖 → EXCEPTION_392） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/services/tool_chain_dag_validator.py` 实现节点唯一性 + 依赖存在性校验 | `pytest` 通过 |
| 🔄 重构 | 添加异常上下文（duplicate_node_id / missing_node_id / referenced_by_node_ids / chain_id） | `ruff check + mypy + pytest` 全部通过 |

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_dag_validator.py`（验证节点重复 → EXCEPTION_391 / 缺失依赖 → EXCEPTION_392） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/services/tool_chain_dag_validator.py` 实现节点唯一性 + 依赖存在性校验 | `pytest` 通过 |
| 🔄 重构 | 添加异常上下文（duplicate_node_id / missing_node_id / referenced_by / chain_id） | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写节点唯一性失败测试
- [ ] Subtask: 🟢 绿 — 实现节点唯一性校验
- [ ] Subtask: 🔄 重构 — 添加异常上下文

#### TDD 循环 B：无环检测（stdlib `graphlib.TopologicalSorter` Kahn 算法 + 环路径提取）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_dag_validator.py`（验证自依赖 A→A + 简单环 A→B→A + 复杂环 A→B→C→D→B + 多环） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/services/tool_chain_dag_validator.py` 使用 stdlib `graphlib.TopologicalSorter`（Kahn 算法 BFS 实现）+ 捕获 `CycleError` 提取环路径；自依赖作为长度为 1 的环被统一捕获 | `pytest` 通过 |
| 🔄 重构 | 添加 cycle_path 异常上下文（环路径节点列表）+ 算法复杂度 O(V + E) 验证 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写无环检测失败测试
- [ ] Subtask: 🟢 绿 — 实现 Kahn 算法（stdlib `graphlib.TopologicalSorter`）+ 环路径提取
- [ ] Subtask: 🔄 重构 — 添加 cycle_path 上下文

**完成标准/Definition of Done:**
- [ ] ToolChainDagValidator 实现位于 `src/domain/services/`（**纯函数**，无外部依赖）
- [ ] 3 项校验规则顺序正确（前项失败立即抛错；自依赖已合并入无环检测）
- [ ] stdlib `graphlib.TopologicalSorter`（Kahn 算法）实现环检测
- [ ] 算法复杂度 O(V + E)（基准测试：100 节点 200 边 < 10ms）
- [ ] 异常上下文完整（duplicate_node_id / missing_node_id / referenced_by_node_ids / cycle_path / chain_id）
- [ ] 单元测试覆盖：正常 DAG / 重复节点 / 缺失依赖 / 自依赖 / 简单环 / 复杂环 / 多环

---

### Task 3: ToolChainRun 聚合根 + 5 状态机

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：ToolChainRun 聚合根 + NodeRunStatus

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_run_42.py`（验证 ToolChainRun 13 字段 + NodeRunStatus 6 字段 + 不变量校验） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/tool_chain_run.py` 实现 `ToolChainRun` + `NodeRunStatus` + `ToolChainRunState` | `pytest` 通过 |
| 🔄 重构 | 添加状态迁移矩阵、不变量验证、`transition_to()` 方法 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 ToolChainRun 失败测试
- [ ] Subtask: 🟢 绿 — 实现 ToolChainRun + ToolChainRunState + NodeRunStatus
- [ ] Subtask: 🔄 重构 — 添加状态迁移矩阵验证

#### TDD 循环 B：ToolChainRunState 5 值状态机迁移

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_run_42.py`（验证状态机迁移矩阵 5 状态所有合法 + 非法迁移） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/entities/tool_chain_run.py` 实现 `VALID_TRANSITIONS` dict + `transition_to()` 方法 | `pytest` 通过 |
| 🔄 重构 | 终态反向迁移禁止 + 复用 `EntityStateTransitionError` (EXCEPTION_243) | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写状态机迁移失败测试
- [ ] Subtask: 🟢 绿 — 实现状态机迁移矩阵
- [ ] Subtask: 🔄 重构 — 终态反向迁移禁止

**完成标准/Definition of Done:**
- [ ] ToolChainRun 聚合根 13 字段完整（chain_run_id/chain_id/tenant_id/state/started_at/completed_at/node_runs/failed_nodes/total_duration_sec/critical_path_sec/parallel_speedup_ratio/failure_strategy/cost_audit/state_version）
- [ ] ToolChainRunState 枚举 5 值（PENDING/RUNNING/COMPLETED/COMPLETED_WITH_ERRORS/FAILED；CANCELLED 已删除）
- [ ] NodeRunStatus 值对象 6 字段完整（node_id/state/started_at/completed_at/error/tool_result）
- [ ] CostAudit 强类型值对象 8 字段完整
- [ ] 状态机迁移矩阵正确（4 条主链边，无 CANCELLED 兜底）
- [ ] 非法迁移抛 `EntityStateTransitionError` (EXCEPTION_243)（复用业务异常）
- [ ] 终态必有 completed_at、非终态 completed_at 为 None
- [ ] domain 层零依赖验证通过
- [ ] 所有测试通过
- [ ] 覆盖率 ≥90%（domain 层）

---

### Task 4: ToolChainOrchestrator 拓扑排序 + 并行调度

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：Kahn 算法拓扑排序 + 执行波次构建

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_orchestrator.py`（验证 Kahn 算法 + 波次划分：线性链 / 钻石依赖 / 简单并行 / 复杂并行） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_chain_orchestrator.py` 实现 `_topological_sort()` + `_build_execution_waves()` | `pytest` 通过 |
| 🔄 重构 | 添加算法复杂度 O(V + E) 验证 + 波次顺序保证 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Kahn 算法失败测试
- [ ] Subtask: 🟢 绿 — 实现拓扑排序 + 波次构建
- [ ] Subtask: 🔄 重构 — 算法复杂度验证

#### TDD 循环 B：asyncio.gather 并行执行 + 变量插值

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_orchestrator.py`（验证 asyncio.gather 并行 + `${upstream.output.field}` 变量插值） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_chain_orchestrator.py` 实现 `_execute_wave()` + `_interpolate_arguments()` | `pytest` 通过 |
| 🔄 重构 | asyncio.Semaphore 并发控制（max_concurrency）+ 上游节点未完成引用失败抛 `EntityBusinessRuleError` | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写并行执行失败测试
- [ ] Subtask: 🟢 绿 — 实现 asyncio.gather 并行 + 变量插值
- [ ] Subtask: 🔄 重构 — 并发控制 + 引用失败异常

#### TDD 循环 C：3 种失败策略实施

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_orchestrator.py`（验证 FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM 三策略） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_chain_orchestrator.py` 实现 `_handle_node_failure()` + 下游节点查找（DFS 反向） | `pytest` 通过 |
| 🔄 重构 | FAIL_FAST 抛 `ToolChainExecutionFailedError` (EXCEPTION_393) + SKIP_DOWNSTREAM 标记 `NodeRunStatus.SKIPPED` | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写失败策略失败测试
- [ ] Subtask: 🟢 绿 — 实现 3 种失败策略
- [ ] Subtask: 🔄 重构 — FAIL_FAST 异常 + SKIP_DOWNSTREAM 节点状态

#### TDD 循环 D：ToolChainRun 状态更新 + 性能指标计算

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_tool_chain_orchestrator.py`（验证 ToolChainRun 状态机迁移 + total_duration_sec + parallel_speedup_ratio 计算） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/services/tool_chain_orchestrator.py` 实现 `_update_run_state()` + `_compute_metrics()` | `pytest` 通过 |
| 🔄 重构 | PENDING → RUNNING → 终态迁移 + 串行总时长计算（各节点耗时求和） | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写状态更新失败测试
- [ ] Subtask: 🟢 绿 — 实现状态更新 + 性能指标
- [ ] Subtask: 🔄 重构 — 串行总时长计算

**完成标准/Definition of Done:**
- [ ] ToolChainOrchestrator 实现位于 `src/application/services/`
- [ ] Kahn 算法实现（BFS + 入度表）
- [ ] 执行波次划分正确（wave[0] 无依赖 → wave[n] 依赖前序波）
- [ ] `asyncio.gather()` 并行执行同波节点
- [ ] `asyncio.Semaphore` 并发控制（max_concurrency）
- [ ] 变量插值（`${upstream_node.output.field}`）正确解析
- [ ] 3 种失败策略（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）正确实施
- [ ] ToolChainExecutionFailedError (EXCEPTION_393) 在 FAIL_FAST 时抛出
- [ ] ToolChainRun 状态机迁移 + 性能指标计算
- [ ] 单元测试覆盖：线性链 / 钻石依赖 / 简单并行 / 复杂并行 / 失败传播 / 变量插值

---

### Task 5: ToolChainRepository 端口契约 + PostgreSQL migration 012

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
>
> **重要依赖关系**：本 Task 必须在 Task 6 之前完成。ToolChainService 依赖 ToolChainRepository 接口与 InMemory 实现（Task 6 `ToolChainService.__init__` 接收 `ToolChainRepositoryPort`，需要 InMemory 实现才能完成端口注入并通过 TDD 绿阶段）。

#### TDD 循环 A：ToolChainRepositoryPort + InMemory 实现

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_port_contract_tool_chain_repository.py`（11 维度覆盖 + ToolChainDagQuery frozen dataclass） | `pytest` 失败 |
| 🟢 绿 | 在 `src/domain/ports/tool_chain_repository.py` 定义 Protocol + `src/infrastructure/storage/inmemory/tool_chain_repository.py` 实现 | `pytest` 通过 |
| 🔄 重构 | asyncio.Lock 类变量测试 + Query Object 模式验证 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Repository 端口契约失败测试
- [ ] Subtask: 🟢 绿 — 实现 Protocol + InMemory Repository
- [ ] Subtask: 🔄 重构 — asyncio.Lock 类变量测试

#### TDD 循环 B：Alembic migration 012_tool_chains.py

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 migration 012 测试（验证 tool_chains 表结构 + 4 索引 + nodes JSONB 字段） | `pytest` 失败 |
| 🟢 绿 | 创建 `deploy/postgresql/alembic/versions/012_tool_chains.py` | `pytest` 通过 |
| 🔄 重构 | 验证 migration downgrade 可回滚 + GIN(nodes JSONB) 索引正确 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 migration 失败测试
- [ ] Subtask: 🟢 绿 — 创建 migration 012
- [ ] Subtask: 🔄 重构 — 验证 migration 回滚

**完成标准/Definition of Done:**
- [ ] ToolChainRepositoryPort 定义在 `src/domain/ports/`（非应用层）
- [ ] 查询方法使用 `ToolChainDagQuery` frozen dataclass（CLAUDE.md §4 决策规则）
- [ ] InMemoryToolChainRepository 实现完整（dict + asyncio.Lock 类变量 + 节点 frozen）
- [ ] 端口契约测试 11 维度覆盖
- [ ] Alembic migration 012 创建（含 4 索引：tenant_id / (tenant_id, name) / (tenant_id, failure_strategy) / GIN(nodes JSONB)）
- [ ] 所有测试通过

---

### Task 6: ToolChainService 应用层服务接口定义

**关联 AC:** AC-6

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
>
> **依赖关系**：本 Task 依赖 Task 5（ToolChainRepositoryPort + InMemoryToolChainRepository）已完成。`ToolChainService.__init__` 接收 `ToolChainRepositoryPort` 抽象，必须先有 Repository 实现才能完成端口注入并通过 TDD 绿阶段。

#### TDD 循环：ToolChainService Protocol + 实现

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_port_contract_tool_chain_service.py`（验证 Protocol 方法签名 3 方法 + Query Object 模式） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/ports/tool_chain_service.py` 定义 Protocol + `src/application/services/tool_chain_service.py` 实现 | `pytest` 通过 |
| 🔄 重构 | 添加类型注解、docstring、Protocol 约束、依赖注入 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写 Protocol 失败测试
- [ ] Subtask: 🟢 绿 — 实现 Protocol + Service
- [ ] Subtask: 🔄 重构 — 委托 Orchestrator 执行 + Repository 查询

**完成标准/Definition of Done:**
- [ ] ToolChainServicePort Protocol 定义完整（3 方法：execute_chain / get_chain_definition / list_chain_definitions）
- [ ] ToolChainService 实现完整
- [ ] `execute_chain()` 委托 `ToolChainOrchestrator`
- [ ] `get_chain_definition()` / `list_chain_definitions()` 委托 Repository
- [ ] 依赖通过端口注入（不导入 infrastructure 具体实现）
- [ ] 端口契约测试 11 维度覆盖
- [ ] 所有测试通过
- [ ] 覆盖率 ≥85%（应用层）

---

### Task 7: RunToolChainUseCase + Skill 加载 + ToolChainExecuted 事件双通道

**关联 AC:** AC-7

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：用例编排

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_run_tool_chain_usecase.py`（验证完整流程：chain 查询 → Skill 加载 → execute_chain → 事件发布） | `pytest` 失败 |
| 🟢 绿 | 在 `src/application/use_cases/run_tool_chain.py` 实现用例 | `pytest` 通过 |
| 🔄 重构 | 添加错误处理、日志、事件发布 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写用例失败测试
- [ ] Subtask: 🟢 绿 — 实现用例
- [ ] Subtask: 🔄 重构 — 添加错误处理 + SkillLoaderPort 抽象

#### TDD 循环 B：ToolChainExecuted 事件双通道配置升级

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_event_channel_config.py`（验证 ToolChainExecuted 双通道配置） | `pytest` 失败 |
| 🟢 绿 | 更新 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` | `pytest` 通过 |
| 🔄 重构 | 添加双通道投递验证测试 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写双通道配置失败测试
- [ ] Subtask: 🟢 绿 — 升级 ToolChainExecuted 为双通道（realtime + reliable）
- [ ] Subtask: 🔄 重构 — 添加双通道投递验证

**完成标准/Definition of Done:**
- [ ] RunToolChainUseCase 实现完整
- [ ] 编排流程：chain 查询 → Skill 加载 → execute_chain → 事件发布
- [ ] SkillLoaderPort Protocol 抽象（六边形约束，复用 4.1a）
- [ ] ToolChainExecuted 事件**双通道**配置（realtime + reliable）
- [ ] `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 同步更新
- [ ] 依赖通过端口注入
- [ ] 所有测试通过

---

### Task 8: 端口注册与架构约束验证

**关联 AC:** AC-8

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：端口注册 + PortSpec 元数据

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_arch_tool_chain_orchestration_dag.py`（验证 4 个新端口注册元数据：name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated 十字段） | `pytest` 失败 |
| 🟢 绿 | 在 `src/composition_root.py` 注册 tool_chain_repository / tool_chain_dag_validator / tool_chain_orchestrator / tool_chain_service | `pytest` 通过 |
| 🔄 重构 | 验证端口注册元数据完整性 + impl 字符串延迟加载 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写端口注册失败测试
- [ ] Subtask: 🟢 绿 — 实现端口注册
- [ ] Subtask: 🔄 重构 — 验证 PortSpec 元数据完整性

#### TDD 循环 B：架构约束验证（lint-imports + 循环依赖检测）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_arch_tool_chain_orchestration_dag.py`（验证 domain 层零外部依赖 + 依赖方向矩阵合规 + 循环依赖检测） | `pytest` 失败 |
| 🟢 绿 | 运行 `poetry run lint-imports` 验证通过 + `ruff check --select E` 检测循环依赖 | 全部通过 |
| 🔄 重构 | 添加架构约束文档 + 端口命名空间澄清 | `ruff check + mypy + pytest + lint-imports` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写架构约束失败测试
- [ ] Subtask: 🟢 绿 — 验证架构约束通过
- [ ] Subtask: 🔄 重构 — 添加架构约束文档

#### TDD 循环 C：6 端口契约测试集成验证

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_port_contract_*.py` 集成验证（tool_chain_service / tool_chain_repository / tool_chain_dag_validator 全部 11 维度） | `pytest` 失败 |
| 🟢 绿 | 确认所有实现满足所有维度 | `pytest` 通过 |
| 🔄 重构 | 补充 asyncio.Lock 类变量测试 + Validator 纯函数性测试 | `ruff check + mypy + pytest` 全部通过 |

- [ ] Subtask: 🔴 红 — 编写端口契约集成失败测试
- [ ] Subtask: 🟢 绿 — 验证 6 端口契约完整
- [ ] Subtask: 🔄 重构 — 补充类变量测试 + 纯函数测试

**完成标准/Definition of Done:**
- [ ] **4 个**新端口注册完整（tool_chain_repository / tool_chain_dag_validator / tool_chain_orchestrator / tool_chain_service）
- [ ] PortSpec 元数据十字段完整（含 compatibility + deprecated）
- [ ] 依赖注入正确
- [ ] 架构约束验证通过（`lint-imports` + `ruff --select E`）
- [ ] 4 端口契约测试通过（含 tool_chain_dag_validator 纯函数验证）
- [ ] InMemoryToolChainRepository asyncio.Lock 类变量验证通过
- [ ] Alembic migration 012 创建（含 4 索引）
- [ ] 所有测试通过

---

### Task 9: 开发结束验收测试（CLAUDE.md §5 + template.md §4.5）

**关联 AC:** AC-1 ~ AC-8

> ⚠️ **收尾验证 Task：** 全部实现 Task 完成后，进行最终验收。

#### TDD 循环：src + tests 完成清单断言 + 收尾校验

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| 🔴 红 | 编写 `test_acceptance_tool_chain_orchestration_dag.py` 收尾场景（验证 src + tests 完成清单断言） | `pytest` 失败 |
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
- [ ] **覆盖率门禁达标 + CI 强制阻断**（Task 0 已配置 `pyproject.toml [tool.coverage.report] fail_under = 80` + `--cov-fail-under=80`）：domain ≥90% / application ≥85% / 整体 ≥80%

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** Hexagonal Architecture（六边形架构）
- **设计约束:**
  - 领域层零依赖（FR-AR-01）- 领域层不得依赖任何外部框架，仅依赖 Python 标准库与领域模型
  - 依赖方向：基础设施层→应用层→基础设施层（禁止反向依赖）
  - 仓储模式（FR-AR-04）- 各存储层通过仓储模式向领域层提供统一接口
- **技术栈:** Python 3.11+
- **DAG 概念基础:** Story 1.18a 的 Prefect 工作流引擎采用"确定性 DAG"模式（`sisys-workflow-agent-integration-design.md §1.3 ADR-002 对齐矩阵：高确定性 — DAG 预定义；低确定性 — Agent 动态决策），本 Story 复用此概念但应用于工具组合而非文档管道。

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR-002 双核引擎架构扩展

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **应用层 ToolChainOrchestrator（选中）** | 与 Story 4.1a ToolExecutionEngine 同层，端口语义统一；纯 Python asyncio.gather 实现，无外部依赖 | 复杂并行调度需手动实现（Kahn 算法 + 波次构建） | ✅ 9/10 |
| Prefect Flow（备选 A） | 内置 DAG 调度、状态追踪、可视化 | 引入 Prefect 重量级依赖到工具组合场景，违背"应用层不依赖基础设施"原则 | 6/10 |
| LangGraph StateGraph（备选 B） | 灵活的状态机编排、可视化 | 主要面向 Agent 认知推理（非确定性），与工具组合（确定性 DAG）语义错配；引入 LangGraph 依赖到应用层 | 5/10 |

**R1-R4 规则应用：**
- **R1 复用**：`ToolExecutionServicePort`（4.1a）/ `EventBusPort`（1.3）/ `L2RdbPort[ToolChainDag]`（仓储基座）
- **R2 新建**：`ToolChainServicePort`（组合端口：ToolExecutionService + EventBusPort + ToolChainRepository）
- **R3 实现**：`InMemoryToolChainRepository`（领域仓储）/ `ToolChainOrchestrator`（应用编排器）
- **R4 适配**（本期不实现）：HTTP API 端点 + CLI 命令（提交 `toolchain execute <chain_id>`）

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── tool.py                  # 既有 Tool 聚合根（4.1a 增强）
│   │   ├── tool_execution.py        # 既有 ToolExecution 聚合根（4.1a）
│   │   ├── tool_chain.py            # 新建 ToolChainDag + ToolChainNode + FailureStrategy（4.2）
│   │   └── tool_chain_run.py        # 新建 ToolChainRun + ToolChainRunState + NodeRunStatus（4.2）
│   ├── exceptions/
│   │   ├── tool_exceptions.py       # 既有 9 个 tool 子域异常（4.1a）
│   │   └── tool_chain_exceptions.py # 新建 4 个 toolchain 子域异常（4.2）
│   ├── ports/
│   │   ├── tool_execution_repository.py  # 既有（4.1a）
│   │   ├── tool_chain_repository.py      # 新建 ToolChainRepositoryPort（4.2）
│   │   ├── registry.py                   # 既有 PortRegistry
│   │   └── resolver.py                   # 既有 PortResolver
│   └── services/
│       └── tool_chain_dag_validator.py  # 新建 DAG 校验器（4.2，领域层纯函数）
│
├── application/
│   ├── ports/
│   │   ├── tool_execution_engine.py  # 既有（4.1a）
│   │   ├── tool_execution_service.py  # 既有（4.1a）
│   │   ├── tool_chain_service.py     # 新建 ToolChainServicePort（4.2）
│   │   └── tool_chain_orchestrator.py # 新建 ToolChainOrchestratorProtocol（4.2）
│   ├── services/
│   │   ├── tool_execution_engine.py   # 既有（4.1a）
│   │   ├── tool_execution_service.py  # 既有（4.1a）
│   │   ├── tool_chain_service.py      # 新建 ToolChainService（4.2）
│   │   └── tool_chain_orchestrator.py # 新建 ToolChainOrchestrator（4.2，Kahn 算法 + asyncio.gather）
│   └── use_cases/
│       ├── strategic_analysis.py      # 既有（4.1a）
│       └── run_tool_chain.py          # 新建 RunToolChainUseCase（4.2）
│
├── infrastructure/
│   ├── storage/
│   │   └── inmemory/
│   │       ├── tool_execution_repository.py  # 既有（4.1a）
│   │       └── tool_chain_repository.py      # 新建 InMemoryToolChainRepository（4.2）
│   ├── messaging/
│   │   └── channel_router.py          # 既有 ChannelRouter（新增 ToolChainExecuted 映射）
│   └── workflow/                       # 既有 Prefect 引擎（1.18a，本 Story 不直接复用）
│
├── interfaces/                         # 本期不直接修改
└── composition_root.py                # 新增 4 个端口注册（4.2）
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源：** [`4-1a-strategic-tool-impl.md`](4-1a-strategic-tool-impl.md)（Story 4.1a，已 ready-for-dev）

**关键学习点：**

1. **聚合根不可变 + 状态机迁移模式**：Story 4.1a 创建的 `ToolExecution` 聚合根采用"frozen dataclass + `transition_to()` 方法 + `VALID_TRANSITIONS` dict"模式（`src/domain/entities/tool_execution.py:44-61`），本 Story AC-4 的 `ToolChainRun` 严格沿用此模式，避免重写状态机逻辑。

2. **复用项目统一 `EntityStateTransitionError` (EXCEPTION_243)**：Story 4.1a R2 决策"不新增 `ToolExecutionStateTransitionError`，复用项目统一迁移守卫异常"（`4-1a-strategic-tool-impl.md:112-119`）。本 Story AC-4 `ToolChainRunState` 迁移守卫**同样复用** `EntityStateTransitionError`，不新增 toolchain 子域异常。

3. **`L2RdbPort[T]` 继承 + async 接口约束**：Story 4.1a AC-1.5 确定 `ToolExecutionRepositoryPort` 继承 `L2RdbPort[ToolExecution]`（async 基座），所有方法必须 `async def`。本 Story AC-3 `ToolChainRepositoryPort` 严格对齐。

4. **ToolExecutionService ↔ ToolRegistryService 职责分离**：Story 4.1a AC-2 决策"使用 `ToolExecutionService`（非 `ToolService`），与 `ToolRegistryService` 职责明确分工"（`4-1a-strategic-tool-impl.md:574-585`）。本 Story AC-6 的 `ToolChainService` 同样**严格区分** `ToolChainService`（执行编排）与 `ToolChainRepository`（持久化），避免职责重叠。

5. **asyncio.Lock 类变量规则**：Story 4.1a AC-1.5 + CLAUDE.md §6 Gotchas 明确"asyncio.Lock 必须声明为**类变量**而非实例变量"（`4-1a-strategic-tool-impl.md:397`）。本 Story AC-3 的 `InMemoryToolChainRepository` 严格遵循此规则。

6. **Tool 实体新字段不破坏现有 23 个 TOOL_CATALOG**：Story 4.1a AC-1 新增字段（rule_version/reliability_score/execution_count/slug）均以 Optional/default_factory 形式添加（`tool.py:91-94`）。本 Story AC-1 的 ToolChainNode 不修改 Tool 实体，仅通过 `tool_slug` 引用，避免破坏既有契约。

7. **Skill 加载复用**：Story 4.1a AC-5 + AC-6 实现 `SkillLoaderPort` 7 方法（`load_metadata` / `load_sop` / `load_references` / `load_script` / `match_by_capability` / `match_by_tag` / `match_by_trigger`，`src/application/ports/skill_loader.py:103-207`）+ `skill_manifest.py` 双向映射。本 Story AC-7 `RunToolChainUseCase` 复用 `SkillLoaderPort`（按节点 tool_slug 调用 `load_metadata(tool_name)` 获取元数据，`load_sop(tool_name)` 懒加载 SOP），不重复实现。

8. **事件双通道配置模式**：Story 4.1a AC-5 B 决策"当前仅 reliable 单通道，本 Story 升级为 realtime + reliable"（`4-1a-strategic-tool-impl.md:703-707`）。本 Story AC-7 沿用此模式：**新增事件默认为双通道**，同步更新 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS`。

9. **端口契约测试 11 维度样板**：Story 4.1a 提供完整 11 维度样板（`_DummyResolver` + 11 维度测试方法名 + runtime_checkable Protocol 校验模式，`4-1a-strategic-tool-impl.md:1274-1303`）。本 Story 4 个新端口契约测试直接复用此样板。

10. **Alembic migration 严格增量**：Story 4.1a 创建 migration 011，本 Story AC-3 创建 migration 012（`tool_chains` 表 + 4 索引）。**禁止**修改 011 及之前已合入 migration。

**避免重蹈覆辙：**

- Story 4.1a Task 7 同时实现 4 端口注册 + migration + InMemoryToolRepository 修复，导致 Task 8 验收测试发现遗留 P0 项。本 Story Task 8 严格聚焦 4 端口注册 + 架构约束，**不混入** InMemoryToolChainRepository 并发安全（已在 Task 6 的 InMemory 实现中预先处理 asyncio.Lock）。

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | claude-sonnet-4-5（建议） |
| **Version** | create-story workflow v1.0.0 |
| **Execution Date** | 2026-09-09 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` / `docs/architecture/sisys-workflow-agent-integration-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-1a-strategic-tool-impl.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（FR-ST-02 / Story 4.2）
- [x] 架构约束从 `architecture.md` + `sisys-workflow-agent-integration-design.md` 提取
- [x] 前一个故事（4.1a）学习经验整合（10 项关键学习 + 避免重蹈覆辙）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] toolchain 子域（390-399）4 个新异常 4 项 Checklist 定义完毕
- [x] 4 个新端口契约定义（tool_chain_repository / tool_chain_dag_validator / tool_chain_orchestrator / tool_chain_service）+ ToolChainExecuted 事件通道定义
- [x] Kahn 算法（stdlib `graphlib.TopologicalSorter`）+ 环路径提取设计完整
- [x] 3 种失败策略（FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM）边界明确

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-2-toolchain-orchestration-dag.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**

| 路径 | 描述 |
|------|------|
| `src/domain/entities/tool_chain.py` | ToolChainDag + ToolChainNode + FailureStrategy |
| `src/domain/entities/tool_chain_run.py` | ToolChainRun + ToolChainRunState + NodeRunStatus |
| `src/domain/services/tool_chain_dag_validator.py` | DAG 校验器（stdlib `graphlib.TopologicalSorter` + 环路径提取） |
| `src/domain/ports/tool_chain_repository.py` | ToolChainRepositoryPort Protocol + ToolChainDagQuery |
| `src/domain/exceptions/tool_chain_exceptions.py` | 4 个新异常（EXCEPTION_390/391/392/393） |
| `src/application/ports/tool_chain_service.py` | ToolChainServicePort Protocol |
| `src/application/ports/tool_chain_orchestrator.py` | ToolChainOrchestratorProtocol Protocol |
| `src/application/services/tool_chain_service.py` | ToolChainService 实现 |
| `src/application/services/tool_chain_orchestrator.py` | ToolChainOrchestrator 实现（Kahn + asyncio.gather） |
| `src/application/use_cases/run_tool_chain.py` | RunToolChainUseCase |
| `src/infrastructure/storage/inmemory/tool_chain_repository.py` | InMemoryToolChainRepository |
| `deploy/postgresql/alembic/versions/012_tool_chains.py` | migration 012 |
| `tests/unit/domain/entities/test_tool_chain_dag_42.py` | ToolChainDag 单元测试 |
| `tests/unit/domain/entities/test_tool_chain_run_42.py` | ToolChainRun 单元测试 |
| `tests/unit/domain/services/test_tool_chain_dag_validator.py` | DAG 校验器单元测试 |
| `tests/unit/application/services/test_tool_chain_orchestrator.py` | Orchestrator 单元测试 |
| `tests/unit/application/use_cases/test_run_tool_chain_usecase.py` | UseCase 单元测试 |
| `tests/unit/architecture/test_arch_tool_chain_orchestration_dag.py` | 架构验证测试 |
| `tests/contracts/test_port_contract_tool_chain_service.py` | Service 端口契约 |
| `tests/contracts/test_port_contract_tool_chain_repository.py` | Repository 端口契约 |
| `tests/contracts/test_port_contract_tool_chain_dag_validator.py` | Validator 端口契约 |
| `tests/contracts/test_event_contract_tool_chain_executed.py` | 事件契约 |
| `tests/integration/test_integration_tool_chain_orchestration_dag.py` | 集成测试 |
| `tests/acceptance/test_acceptance_tool_chain_orchestration_dag.feature` | Gherkin 验收场景 |
| `tests/acceptance/test_acceptance_tool_chain_orchestration_dag.py` | BDD 步骤实现 |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | `4.2` |
| **Story Key** | `4-2-toolchain-orchestration-dag` |
| **File** | `_bmad-output/implementation-artifacts/stories/4-2-toolchain-orchestration-dag.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具链编排（Toolchain Orchestration） |
| **优先级** | P0（Epic 4 战略工具箱核心 Story，FR-ST-02） |
| **覆盖 FR** | FR-ST-02（工具链编排，DAG 有向无环图） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-9，共 10 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-8 共 8 个 AC）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 + 端口契约 + 异常体系）
4. [x] Previous story learnings integrated 前一个故事（4.1a）学习经验已整合（10 项关键学习）
5. [x] Sprint status synced to `ready-for-dev`

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** TBD（dev-story 完成时填写）
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] TBD（dev-story 完成后填写）

#### 已修复 Patch

- [ ] TBD（dev-story 完成后填写）

#### 已推迟 Defer

- [ ] TBD（dev-story 完成后填写）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-09-09
**最后更新/Last Updated:** 2026-09-09
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 Story 4.1a 设计模式 + 4 项 Checklist 异常体系 + 6 端口契约 + Kahn/DFS 算法）
