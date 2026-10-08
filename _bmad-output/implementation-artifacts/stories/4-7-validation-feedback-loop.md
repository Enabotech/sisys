# Story 4.7: Validation Feedback 闭环（增强重试与不可行标记）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 质量保障工程师,
**I want** 系统执行 Validation Feedback 闭环——工具执行基础重试耗尽后，自动捕获 STDERR、检索错误案例库辅助 LLM 生成修复代码并增强重试（最大 3 次），3 次均失败则标记任务"不可行"并记录演进日志,
**So that** 工具执行失败可自动恢复或明确标记，保证战略分析任务可靠完成、失败历史可追溯。

### 业务价值

- 覆盖 **FR-ST-07 (P1)**（prd.md:1822，公理依据 or.md 三.3.(3)「支持 Validation Feedback 闭环：自动捕获代码执行 STDERR，检索错误案例库辅助 LLM 生成修复版本；设定最大重试次数（默认 3 次），失败则标记不可行并记录至演进日志」）。
- Epic 4「战略工具箱」V1 P1 扩展（执行优先级 P1-7）：Epic 4 收官故事。4.1a~4.6 已交付五阶段执行引擎、Schema 验证装饰器（含基础重试）、Docker 沙箱、红蓝辩论与工具版本管理——当前失败路径在基础重试耗尽后**直接终结**（`ToolResultValidationError`/`ToolExecutionFailedError` 上抛），既无 STDERR 数据链（适配器捕获后丢弃），也无修复闭环与失败资产沉淀。
- **在 Epic 中的位置**：Epic 4 最后一个实现故事（4-1~4-6 全部 done）。前序故事在本 Story 处预置了大量契约（详见「已有资产复用清单」）：`EXCEPTION_399` 预留编码、`SandboxExecutionFailed.stderr` 预留字段、`ToolSchemaValidationFailed` reliable 通道"4.7 启用"注释、`ToolResultStatus.INVALID` 的"可重试"语义注释——本 Story 是这些预留债的集中清偿点。
- **依赖**：Story 4.1a（ToolExecutionEngine 五阶段 + 基础 3 次重试）✅ done + Story 4.3（ToolOutputValidator 装饰器 + `ToolSchemaValidationFailed` 事件 + violations 注入 prompt 自纠反馈）✅ done + Story 4.4（Docker 沙箱 + SandboxSecurityDecorator）✅ done + Story 4.6（工具版本管理，执行链透明路由）✅ done。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: STDERR 捕获数据链贯通

**Given** 沙箱内代码执行失败（非零退出码或 stderr 非空）
**When** `AioDockerSandboxAdapter.execute_code` 抛出 `ExecutionError`（EXCEPTION_313）
**Then** 异常 `context` 携带 `stderr`（截断 ≤2000 字符防 DoS）与 `exit_code`（向后兼容：构造器新增可选参数，既有调用零改动）
**And** `SandboxSecurityDecorator` 发布 `SandboxExecutionFailed` 事件时填充**已预留未用**的 `execution_id` 与 `stderr` 字段（`sandbox_events.py:96` 注释"用于 Story 4.7 Validation Feedback"的清偿）
**And** 反馈闭环沿异常因果链提取 STDERR（`_unwrap_sandbox_error` 先例，`sandbox_security_decorator.py:100-120`），stderr 进入修复 prompt 与演进日志。

**验证标准/Validation Criteria:**
- [ ] `ExecutionError` 构造器支持 `stderr`/`exit_code` 可选参数并写入 `context`（默认值不破坏既有 4.4 测试）
- [ ] `aiodocker_sandbox_adapter.py:511-518` 失败路径将 `stderr_str[:2000]` 与 `exit_code` 填入异常 context（当前仅 logger.debug 丢弃）
- [ ] `sandbox_security_decorator.py:132-137` 事件发布填充 `execution_id` + `stderr`
- [ ] Schema 校验失败路径（无 STDERR）以 `schema_violations` 提取错误签名（`ToolResultValidationError.context["schema_violations"]`，4.3 已携带）
- [ ] 单元测试覆盖：adapter 填充 / decorator 事件填充 / cause 链提取三段

### AC-2: Validation Feedback 闭环——增强重试与修复代码生成

**Given** 工具执行结果验证失败且基础重试已耗尽（内层 `ToolOutputValidator` 抛 `ToolResultValidationError` EXCEPTION_389），或执行失败（`ToolExecutionFailedError` EXCEPTION_382，含沙箱 STDERR）
**When** `ValidationFeedbackDecorator`（装饰链最外层）捕获触发异常
**Then** 触发增强反馈循环，每次增强尝试依次执行：提取 STDERR/签名 → 检索错误案例库 → LLM 生成修复代码 → 经 `context.extensions["validation_feedback_hints"]` 注入（P0-D 模式先例）重执行内层链
**And** 增强重试最大 **3 次**（`RetryPolicy.max_attempts=3` 语义复用，区别于基础重试的两层循环）
**And** 增强重试期间 Engine 内部重试临时降为 `max_attempts=1`（4.3 P0-1 教训：防 3×3×3×3=81x LLM 调用放大触发 `max_total_duration_sec` 超时），完成后恢复原值（try/finally 防御）
**And** 修复成功则返回 `ToolResult(status=SUCCESS, retry_count=增强尝试次数)`。

**验证标准/Validation Criteria:**
- [ ] 触发条件判定：仅 389（OUTPUT 校验耗尽）与 382（执行失败）两类进入闭环；`ToolExecutionTimeoutError`（385）与数据采集异常组（207/201/410-413 直传语义）**不进入**闭环（超时/策略违规不可修复，直接上抛）
- [ ] 修复 prompt 组装：原 Code 产物 + STDERR + 案例库检索结果（Top-N 相似案例的 fix_summary）+ schema violations（若有）
- [ ] `tool_execution_engine.py` `_think_stage`/`_code_stage` prompt 构建读取 `validation_feedback_hints` 扩展键（引擎 `__init__` 签名不变——4.4 AC-7.4 BDD 断言保护）
- [ ] 防放大：增强重试期间内层 Engine `_retry.max_attempts=1`，finally 恢复
- [ ] 单元测试：触发判定矩阵 / hint 注入透传 / 防放大恢复 / 成功恢复路径

### AC-3: 不可行标记与领域事件

**Given** 3 次增强重试均失败
**When** 反馈循环耗尽
**Then** 标记任务不可行：返回 `ToolResult(status=INFEASIBLE)`（`ToolResultStatus` 新增枚举值，additive 向后兼容），`output` 携带失败摘要（error_signature/最终 STDERR 摘要/尝试次数）
**And** 发布 `ToolExecutionMarkedInfeasible` 领域事件（双通道 reliable），写入演进日志 `final_status=MARKED_INFEASIBLE`
**And** 闭环内部以 `ValidationFeedbackRetryExhaustedError`（EXCEPTION_399，**4.1b/4.3 两度预留的编码**）作为耗尽信号，由装饰器捕获并转换为 INFEASIBLE 结果（对外不抛异常——ToolChain DAG 编排按 `status` 分支感知，避免中断后续节点）
**And** 修复成功路径发布 `ToolExecutionRecovered` 领域事件（双通道 reliable）。

**验证标准/Validation Criteria:**
- [ ] `ToolResultStatus.INFEASIBLE = "infeasible"` 新增；既有不变量不受影响（INVALID 语义不变——`value_objects/tool_execution.py:247-249` 注释契约保持）
- [ ] `ValidationFeedbackRetryExhaustedError`：code=`EXCEPTION_399`、继承 `BusinessException`、构造器携带 `execution_id`/`tool_id`/`enhanced_retry_count`/`error_signature` context
- [ ] `ToolExecutionState` 6 状态机**不动**（FAILED 终态语义不变，增强重试按"终态反向迁移禁止（重试创建新 attempt）"既有注释语义创建新执行）
- [ ] 两事件 13 字段对齐 `DomainEvent` 基类 + tenant_id baseline（4-5 R1-F01 教训：metadata 字段一律 `str()` 化防 json 序列化失败）
- [ ] INFEASIBLE 结果不抛异常、不发布 ToolExecuted 成功事件

### AC-4: 演进日志与持久化可靠性

**Given** 反馈闭环结束（无论恢复或标记不可行）
**When** 写入演进日志
**Then** `EvolutionLogEntry` 聚合根落库（PG migration 017），记录 execution_id / tool_id / error_signature / enhanced_retry_count / fix_attempts 摘要 / final_status（RECOVERED | MARKED_INFEASIBLE）
**And** 失败历史可追溯：按 `tool_id` 查询该工具全部反馈历史（`EvolutionLogQuery` Query Object，多字段+分页），按 `execution_id` 精确定位单次记录
**And** 清偿 defer 债：**outbox 独立 session 结构性修复**（`tool_execution_engine.py:283-285` 与 `data_source_resolver.py:352` 注释显式 defer 本 Story）——reliable 通道 outbox 写入使用独立 session/事务，不复用请求 ContextVar session；后台/CLI 路径异常回滚后 reliable 事件不丢失。

**验证标准/Validation Criteria:**
- [ ] `EvolutionLogEntry` 不变量：`enhanced_retry_count ∈ [1,3]`、`final_status` 为枚举、UUID 有效、timezone-aware
- [ ] 按 execution_id 幂等 upsert（同 execution 重复写入不产生重复行）
- [ ] `EvolutionLogQuery`（frozen dataclass：tool_id/tenant_id/execution_id 可选 + limit/offset）走 Query Object 决策规则（多字段组合+分页）
- [ ] outbox 修复回归断言：模拟请求 session 异常回滚场景，reliable 事件仍成功投递（正常 HTTP 路径行为零变化）
- [ ] 集成测试覆盖双查询面（list_by_tool / get_by_execution）

### AC-5: 错误案例库（检索辅助 + 案例回填 + 幂等）

**Given** 反馈循环执行中
**When** 每次增强尝试前
**Then** 按 `(tenant_id, tool_id, error_signature)` 检索错误案例库，命中案例的 `fix_summary` 注入修复 prompt（or.md error_db.search 蓝图落地）
**And** 闭环结束时回填案例：恢复成功记 `RECOVERED` 案例（错误→修复成功对，最高价值）；标记不可行记 `MARKED_INFEASIBLE` 案例
**And** 案例写入幂等：同 `(tenant_id, tool_id, error_signature)` 重复记录 `occurrence_count += 1` 并刷新 `last_seen_at`，不产生重复行。

**验证标准/Validation Criteria:**
- [ ] `ErrorCase` 聚合根 + `ErrorCaseRepositoryPort`（search_by_signature / record_case upsert / get_by_natural_key——单字段检索与命令型操作直接参数，CLAUDE.md 端口参数决策规则）
- [ ] `ErrorSignatureExtractor` 领域服务（纯函数）：STDERR 归一化（剥离路径/行号/时间戳/内存地址）→ sha256 前 16 hex；schema violations 路径归一化签名——同根因不同表层输出收敛为同一签名（幂等前提）
- [ ] V1 检索语义：精确签名匹配（确定性可测）；向量相似检索（L3 Qdrant）为非目标
- [ ] 并发 upsert 冲突容错（4-6 CR1-4 教训：UNIQUE 冲突后 PendingRollback 需 `begin_nested()` SAVEPOINT 包裹重读）
- [ ] 案例检索结果为空时闭环仍可运行（纯 LLM 修复，`fix_strategy=PURE_LLM`）

### AC-6: 幂等性与事件通道补全

**Given** 同一执行重复触发反馈闭环（装饰器重复调用或事件重放）
**When** 闭环各副作用执行
**Then** 演进日志按 execution_id 幂等（AC-4）、案例库按自然键幂等（AC-5）、`ToolExecutionMarkedInfeasible`/`ToolExecutionRecovered` 事件不重复发布（同 execution 终态判定）
**And** 清偿 4.3 通道预留债：`ToolSchemaValidationFailed` 补 reliable 通道（`event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` **两处同步**，YAML > DEFAULT_MAPPINGS 优先级注释 `channel_router.py:50-53`）。

**验证标准/Validation Criteria:**
- [ ] 幂等集成测试：同 execution 重复闭环 → 日志 1 行 / 案例计数递增 / 事件 1 次
- [ ] `ToolSchemaValidationFailed` 通道从 realtime-only 升级为双通道 reliable（两处配置 + 契约测试逐字段断言）
- [ ] 新事件双通道两处登记（`configs/event_channels.yaml`——注意实际目录为 `configs/` 非 `config/`——+ `channel_router.py` DEFAULT_MAPPINGS）
- [ ] 事件通道映射契约测试：YAML 与 DEFAULT_MAPPINGS 逐字段一致（4-6 先例 `test_event_channel_mapping_tool_version.py`）

### AC-7: 装配升级与性能基准

**Given** 全部组件实现完成
**When** 组合根装配与性能基准执行
**Then** `tool_execution_service` 升级 **v1.3.0 → v1.4.0**，装饰链层叠为 `ValidationFeedbackDecorator > SandboxSecurityDecorator > ToolOutputValidator > Engine`（4.7 最外层），`compatibility=("v1.3.0", "v1.2.0")`，tags += `("feedback",)`
**And** 性能达标（epics 硬指标可测化口径）：闭环自身开销（错误签名提取 + 案例检索 + 演进日志写入，**不含** LLM 修复生成与沙箱执行时长——二者受 `LLMConfig.timeout`/沙箱 timeout 支配）单次 **P95 < 5s**；增强重试恢复成功率 **≥80%**（20 次可修复故障注入 ≥16 恢复）；不可行标记准确率 **≥95%**（20 次不可修复故障 100% 标记 + 可修复故障 0 误标）。

**验证标准/Validation Criteria:**
- [ ] 3 个新端口注册（`error_case_repository` / `evolution_log_repository` / `validation_feedback_service`）+ `tool_execution_service` 升级，PortSpec 10 字段齐备，lambda 工厂注入
- [ ] 端口契约测试 11 维度 ×3（`test_port_contract_tool.py` 样板：注册/名称/版本/接口类型/生命周期/owner/module/tags/impl callable/方法存在/Protocol runtime_checkable）
- [ ] 性能基准位于 `tests/integration/test_validation_feedback_integration.py`（epics 硬路径）：P95 开销 / 成功率 / 准确率三组
- [ ] 全量回归：`poetry run pytest tests/ -n 8` 通过、`ruff check` + `mypy` 通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] 使用标准库实现领域事件校验（frozen dataclass / Enum / 自定义验证），禁止在领域层依赖 Pydantic
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `UserCreated`）
- [ ] 新增 2 事件（`src/domain/events/validation_feedback_events.py`）：
  - `ToolExecutionMarkedInfeasible`：`execution_id`/`tool_id`/`tenant_id`/`tool_version`/`error_signature`/`enhanced_retry_count`/`failure_summary`/`occurred_at`；`aggregate_type="ToolExecution"`；双通道 reliable
  - `ToolExecutionRecovered`：`execution_id`/`tool_id`/`tenant_id`/`tool_version`/`error_signature`/`enhanced_retry_count`/`occurred_at`；`aggregate_type="ToolExecution"`；双通道 reliable
- [ ] `ToolSchemaValidationFailed` 由 realtime-only 升级双通道 reliable（4.3 留项"reliable 4.7 启用"清偿，事件类本身零改动）

#### 数据模型 (Data Models)
- [ ] 模型定义位于 `src/domain/entities/` 或对应层
- [ ] `ErrorCase` 聚合根（`src/domain/entities/error_case.py`）：`case_id`/`tenant_id`/`tool_id`/`error_signature`(64 hex)/`error_category`/`stderr_excerpt`(≤2000)/`fix_summary`(≤1000)/`outcome`(RECOVERED|MARKED_INFEASIBLE)/`occurrence_count`(≥1)/`last_seen_at`/`created_at`；自然键 `(tenant_id, tool_id, error_signature)`
- [ ] `EvolutionLogEntry` 聚合根（`src/domain/entities/evolution_log_entry.py`）：`log_id`/`tenant_id`/`tool_id`/`execution_id`/`tool_version`/`error_signature`/`enhanced_retry_count`(1-3)/`fix_attempts: tuple[FixAttempt, ...]`/`final_status`(RECOVERED|MARKED_INFEASIBLE)/`created_at`
- [ ] `FixAttempt` 值对象（`src/domain/value_objects/validation_feedback.py`）：`attempt_no`(1-based)/`error_signature`/`fix_strategy`(CASE_GUIDED|PURE_LLM)/`stderr_excerpt`/`succeeded`/`detail`
- [ ] `ToolResultStatus.INFEASIBLE` 新增枚举值（additive；`INVALID`"可重试"语义契约不变）
- [ ] `ErrorSignatureExtractor` 领域服务（`src/domain/services/error_signature_extractor.py`）：纯函数，STDERR 归一化签名 + violations 归一化签名
- [ ] `EvolutionLogQuery` Query 值对象（定义在端口文件，多字段+分页决策规则）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports` 与 `src/application/ports`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_validation_feedback*.py` 等 3 个新契约文件）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 端口变更配套契约测试与兼容性检查
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

**端口契约 SSOT 清单（本 Story 唯一事实源）：**

| 端口名 | 层 | interface | impl 注册实现 | version | lifetime | owner | tags |
|--------|----|-----------|--------------|---------|----------|-------|------|
| `error_case_repository` | domain | `ErrorCaseRepositoryPort`（`src/domain/ports/error_case_repository.py`） | lambda → `PostgreSQLErrorCaseRepository`（InMemory 实现供单测） | v1.0.0 | SCOPED | tool-team | (tool, repository, feedback) |
| `evolution_log_repository` | domain | `EvolutionLogRepositoryPort`（`src/domain/ports/evolution_log_repository.py`） | lambda → `PostgreSQLEvolutionLogRepository` | v1.0.0 | SCOPED | tool-team | (tool, repository, feedback) |
| `validation_feedback_service` | application | `ValidationFeedbackServicePort`（`src/application/ports/validation_feedback_service.py`，方法 `recover(...)`） | lambda 工厂注入 llm_client + error_case_repository + evolution_log_repository + event_publisher + RetryPolicy | v1.0.0 | SCOPED | tool-team | (tool, feedback, service) |
| `tool_execution_service` | application | `ToolExecutionServicePort` | **升级 v1.3.0 → v1.4.0**：装饰链最外层加 `ValidationFeedbackDecorator`；`compatibility=("v1.3.0", "v1.2.0")`；tags += ("feedback",) | v1.4.0 | SCOPED | tool-team | (tool, execution, service, decorated, versioned, feedback) |

**端口方法契约：**
- `ErrorCaseRepositoryPort`：`search_by_signature(tenant_id, tool_id, error_signature, limit=5) -> tuple[ErrorCase, ...]`；`record_case(case: ErrorCase) -> ErrorCase`（自然键 upsert 幂等计数）；`get_by_natural_key(tenant_id, tool_id, error_signature) -> ErrorCase | None`
- `EvolutionLogRepositoryPort`：`save(entry: EvolutionLogEntry) -> None`（execution_id upsert 幂等）；`list_by_query(query: EvolutionLogQuery) -> tuple[EvolutionLogEntry, ...]`；`get_by_execution(execution_id, tenant_id) -> EvolutionLogEntry | None`
- `ValidationFeedbackServicePort`：`async recover(tool_id, tool, tool_call, context, trigger_error) -> ToolResult`（编排完整闭环：签名提取→案例检索→LLM 修复→增强重试→演进日志→不可行标记/恢复事件）

#### 端口契约清单执行约束（强制）
- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> **适用范围：** 本清单仅针对定义在 `src/domain/exceptions/` 下、继承自 `DomainError`（别名 `BaseException`）的**领域异常**。
> **不在本清单范围：** FastAPI/Pydantic 框架原生异常、第三方 SDK 原始异常（由 `ErrorMapper` 映射）。
> **禁止 `raise ValueError`：** 所有验证失败均使用领域异常体系。
> 完整检查清单与全量异常分类详见 [`sisys-uni-exception-design.md §3.12`](../../../docs/architecture/sisys-uni-exception-design.md#312-异常注册检查清单)。
> 编码分配策略（人工编码 + CI 自动校验）详见 [`sisys-uni-exception-design.md §3.3`](../../../docs/architecture/sisys-uni-exception-design.md#33-编码分配策略人工编码--ci-自动校验)。

- [ ] **仅新增 1 个异常，占用既定预留码位 `EXCEPTION_399`**（`sisys-uni-exception-design.md:718` 与 `_code_ranges.py:85` 两处预留"Story 4.7 ValidationFeedbackRetryExhaustedError"的兑现；`toolchain` 子域 390-399 第 10 个也是最后一个码位）：

| code | 异常类 | parent class | HTTP | 触发场景 |
|------|--------|--------------|------|----------|
| EXCEPTION_399 | `ValidationFeedbackRetryExhaustedError` | `BusinessException`（EXCEPTION_103） | **422** | 3 次增强重试均失败，任务被判定不可行（内部耗尽信号，装饰器捕获转 `ToolResult(INFEASIBLE)`；422 与 396 出参校验失败语义对齐——"语义上不可处理"而非 502"可重试下游故障"，不可行标记恰是"重试无意义"的终态结论） |

- [ ] **不扩域 400-409（方案 A 触发条件未满足）**：4.3 预测的 `ValidationFeedbackFallbackFailedError`/`HumanReviewTimeoutError`/`CanaryConflictError` 均属降级/人工审核/灰度联动扩展（非本 epic 范围，见非目标），400-409 保持未分配——Story 文件与 `sisys-uni-exception-design.md` 中"扩域至 400-409（方案 A）"的预留注释更新为"按需扩域，触发条件：反馈闭环降级链路立项"
- [ ] 归属模块：新建 `src/domain/exceptions/validation_feedback_exceptions.py`（4.5 debate 新文件先例）；`_CLASS_TO_SUBDOMAIN` 子域映射注册为 `"toolchain"`（399 物理归属 toolchain 段，语义为反馈闭环——沿用 4.2/4.3 子域嵌套声明惯例）
- [ ] 构造器参数设计：`execution_id`/`tool_id`/`enhanced_retry_count`/`error_signature` 经 `context` 字典暴露
- [ ] 消息安全性审查：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] **5 处登记 Checklist**（4-6 教训全量执行）：
  1. **定义文件**：`validation_feedback_exceptions.py`（类 + `__all__`）
  2. **`_code_ranges.py`**：`CODE_RANGES` 注释行 EXCEPTION_399 由"预留"改"已分配" + `_CLASS_TO_SUBDOMAIN` 注册
  3. **`exceptions/__init__.py`**：导入 + `__all__`（按子域分组注释节）
  4. **`EXCEPTION_HTTP_MAP`**：`exception_handlers.py` 精确注册 399→422（注释格式与 4.6 先例一致，注释行内 code 与实际 code 严格对齐——4.1a 偏移 bug 先例）
  5. **`sisys-uni-exception-design.md §3.3.2` 两表同步**（注意：该文档存在两个同号 §3.3.2 小节，编码分配表与子域范围表**都必须更新**——4-6 踩坑记录）+ `tests/unit/interfaces/api/test_exception_handlers.py` 期望集合同步（4-5 教训）
- [ ] 编码碰撞自查：`grep -rn "EXCEPTION_399" src/` 仅新定义文件与登记处命中
- [ ] 测试覆盖：构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过（`tests/unit/domain/exceptions/` 8 项既有测试 + 新增 `test_validation_feedback_exceptions.py`）
- [ ] BDD 验收场景：异常路径（399 内部转换、385/207 不入闭环直传）纳入 Gherkin Edge Cases

**复用现有异常（禁止同义新增）：**
- `ToolResultValidationError`（EXCEPTION_389）— OUTPUT 校验耗尽触发信号（`tool_output_validator.py:220-222` 注释"4.7 订阅契约按此类型处理"）
- `ToolExecutionFailedError`（EXCEPTION_382）— 执行失败触发信号（cause 链携带沙箱异常）
- `ToolExecutionTimeoutError`（EXCEPTION_385）— 不入闭环直传（超时不可修复）
- `ToolSchemaMissingError`（EXCEPTION_398）— required_schema 集成点：闭环中 Tool schema 缺失时 fail-fast 直传（4.3 定义、4.7 消费，测试注释 `test_tool_schema_exceptions.py:144` 契约兑现）
- `EntityValidationError`（242）/`EntityStateTransitionError`（243）— 新实体不变量与状态守卫复用
- `ToolExecutionRetryExhaustedError`（EXCEPTION_383）— 与 399 的语义区分：383=**基础**重试（stage 级 RetryPolicy）耗尽（仍可进入增强闭环）；399=**增强**重试（反馈闭环级）耗尽（终态不可行）——Story 与异常 docstring 中必须显式写明此区分，防同义混淆

#### API 契约 (API Contract)
- [ ] 本 Story **无新增 REST 端点**（演进日志查询面为非目标；`docs/api/openapi.yaml` 零改动——4.1b"无新 REST 端点"先例）
- [ ] `EXCEPTION_HTTP_MAP` 新增 399→422 映射（AC-3 登记 Checklist 第 4 项）
- [ ] 既有 `tools` 路由行为零变化回归

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

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
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止（`.importlinter` application-no-infrastructure 契约——应用服务注入标量/端口，禁止 import infrastructure；outbox session 修复必须落在 infrastructure/messaging 内） |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_validation_feedback_loop.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_validation_feedback_loop.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases），场景命名 `AC-x.y - 中文描述`（4.3/4.6 工具系先例）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 覆盖：399 耗尽标记、385 超时不入闭环、207/413 数据源异常直传、案例库空命中纯 LLM 修复、幂等重复触发
- **服务级 BDD 模式（4-6 形态）**：`scenarios()` 批量注册 + `context: dict[str, Any]` fixture + 模块级 `event_loop` fixture + `_run(coro)` helper + `_make_*` 工厂 + `_capture_error`；真实服务链（InMemory 仓储 + 真实 ErrorSignatureExtractor + 真实引擎 + 真实装饰链），仅 LLM/Sandbox 适配器 AsyncMock（可编程失败/修复序列）
- Fake LLM 分派纪律（4-5 R1-F06 教训）：Mock LLM 按 prompt 中的**结构化角色标记**（如 system_prompt 或修复 prompt 固定前缀）分派响应，禁止按易混淆子串分派

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态：acceptance .py 与契约测试 collection ERROR / ImportError，属预期中间态）
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
| **TDD 单元测试** | ErrorCase 聚合根 | 构造不变量/自然键/occurrence_count | `tests/unit/domain/entities/test_error_case.py` | Task 1 |
| **TDD 单元测试** | EvolutionLogEntry 聚合根 | 构造不变量/fix_attempts/终态语义 | `tests/unit/domain/entities/test_evolution_log_entry.py` | Task 1 |
| **TDD 单元测试** | ErrorSignatureExtractor | STDERR 归一化/violations 签名/同根因收敛 | `tests/unit/domain/services/test_error_signature_extractor.py` | Task 1 |
| **TDD 单元测试** | ToolResultStatus.INFEASIBLE | additive 枚举/INVALID 语义不回归 | `tests/unit/domain/value_objects/test_tool_result_status.py` | Task 1 |
| **TDD 单元测试** | 领域事件 ×2 | 字段/序列化 str 化/aggregate 关联 | `tests/unit/domain/events/test_validation_feedback_events.py` | Task 2 |
| **TDD 领域异常测试** | 399 异常 | 构造/context/继承链/编码 | `tests/unit/domain/exceptions/test_validation_feedback_exceptions.py` | Task 2 |
| **TDD 单元测试** | ExecutionError 增强 | stderr/exit_code 可选参数向后兼容 | `tests/unit/domain/exceptions/test_sandbox_exceptions.py`（扩展） | Task 3 |
| **TDD 单元测试** | adapter/装饰器 STDERR 链 | 异常 context 填充/事件字段填充/cause 链提取 | `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_adapter_stderr.py` + `tests/unit/application/services/test_sandbox_security_decorator_events.py` | Task 3 |
| **TDD 单元测试** | InMemory 双仓储 | upsert 幂等/查询语义 | `tests/unit/infrastructure/storage/inmemory/test_error_case_repository.py`、`test_evolution_log_repository.py` | Task 4 |
| **TDD 单元测试** | ValidationFeedbackService | 触发判定矩阵/闭环编排/防放大/案例回填 | `tests/unit/application/services/test_validation_feedback_service.py` | Task 5 |
| **TDD 单元测试** | ValidationFeedbackDecorator | 装饰链集成/hints 注入/INFEASIBLE 转换/事件发布 | `tests/unit/application/services/test_validation_feedback_decorator.py` | Task 6 |
| **TDD 单元测试** | 引擎 hints prompt | `validation_feedback_hints` 扩展键读取 | `tests/unit/application/services/test_tool_execution_engine_hints.py` | Task 6 |
| **TDD 契约测试** | 3 新端口 + 1 升级 | 11 维度（注册/名称/版本/接口/生命周期/owner/module/tags/impl callable/方法/Protocol） | `tests/contracts/test_port_contract_error_case_repository.py`、`test_port_contract_evolution_log_repository.py`、`test_port_contract_validation_feedback_service.py` | Task 4/6 |
| **TDD 契约测试** | 事件契约 + 通道映射 | 事件字段/双通道两处一致 | `tests/contracts/test_event_contract_validation_feedback_events.py`、`test_event_channel_mapping_validation_feedback.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_validation_feedback_loop.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_validation_feedback_loop.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | 同 feature/.py | Task 9 |
| **SDD 架构验证** | 反馈闭环架构测试（epics 硬路径） | 重试增强/失败标记/幂等性/演进日志四项 | `tests/unit/architecture/test_validation_feedback.py` | Task 8 |
| **集成测试** | 全链闭环 + PG 双仓储 + outbox 修复 + 性能基准（epics 硬路径） | 真实 PG/Redis + 成功率/准确率/P95 | `tests/integration/test_validation_feedback_integration.py` | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**（epics 硬指标：本 Story 核心交付在应用层闭环编排）
- [ ] **领域层覆盖率 ≥90%**（关键业务逻辑，不变量验证）
- [ ] **基础设施层覆盖率 ≥75%**（外部依赖适配，连接测试）
- [ ] **集成测试覆盖率 ≥75%**（epics 硬指标）
- [ ] **关键路径覆盖率 100%**：闭环触发判定矩阵（389 入/382 入/385 出/207 出/413 出）、增强重试 1→3 次、耗尽标记、恢复成功、案例回填、幂等 upsert 全分支

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [ ] **三条异常红线 grep 自查零输出**：`grep -rn "raise ValueError" src/` / `grep -rn "HTTPException" src/ --include="*.py" | grep -v exception_handlers` / `grep -rn "# noqa\|# type: ignore\|# pylint: disable" src/`

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback（savepoint） | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 前缀隔离（`TestTenant`） | ID 冲突或状态污染 |
| **外部服务隔离** | PG/Redis 集成测试走独立 schema + 租户隔离 | 真实数据被污染 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；BDD 步骤用 `event_loop.run_until_complete()` | 锁失效或 context 丢失 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **BDD async 配合** | BDD 步骤函数不使用 `@pytest.mark.asyncio` | context 数据丢失 |
| **Fake LLM 分派** | Mock LLM 按结构化角色标记分派响应，禁止易混淆子串分派（4-5 R1-F06） | 误路由致断言循环论证 |
| **并发 upsert** | 集成测试覆盖 UNIQUE 冲突 + PendingRollback 容错（begin_nested SAVEPOINT，4-6 CR1-4） | 并发记录案例崩溃 |
| **时间敏感断言** | 性能基准 P95 阈值断言与计时口径成对出现；CI 慢机器容差（如 1.8× 阈值，4-5 R2-F02 先例） | CI 随机红 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源
- ❌ asyncio.Lock 使用实例变量
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 验收测试 mock 领域服务（仅 LLM/Sandbox 外部适配器可 AsyncMock）

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | STDERR 捕获数据链贯通（adapter→异常→事件） | Task 3 | ExecutionError 增强 + adapter 填充 + 装饰器事件填充 + cause 链提取 | `test_aiodocker_adapter_stderr.py` 等 |
| AC-1 | 签名提取（violations 路径） | Task 1 | ErrorSignatureExtractor | `test_error_signature_extractor.py` |
| AC-2 | 触发判定（389/382 入，385/207 出） | Task 5 | recover 触发判定矩阵 | `test_validation_feedback_service.py` |
| AC-2 | 案例检索注入修复 prompt | Task 5 | 修复 prompt 组装（CASE_GUIDED/PURE_LLM） | 同上 |
| AC-2 | hints 注入 + 引擎 prompt 读取 | Task 6 | `validation_feedback_hints` 扩展键 | `test_tool_execution_engine_hints.py` |
| AC-2 | 防放大（max_attempts=1 + finally 恢复） | Task 5 | 增强循环内临时降级 | 同上 |
| AC-3 | INFEASIBLE 标记 + ToolResult 契约 | Task 1 / Task 5 | 枚举新增 / 耗尽转换 | `test_tool_result_status.py` |
| AC-3 | 399 异常全链路登记 | Task 2 | 5 处登记 Checklist | `test_validation_feedback_exceptions.py` |
| AC-3 | 两领域事件 + 双通道 | Task 2 | 事件定义 + 两处配置 | `test_validation_feedback_events.py` + 契约 |
| AC-4 | 演进日志实体 + 双查询面 | Task 1 / Task 4 | 实体 + EvolutionLogQuery + 仓储 | `test_evolution_log_entry.py` + 集成 |
| AC-4 | outbox 独立 session 修复 | Task 6 | infrastructure/messaging outbox session 独立化 | `test_validation_feedback_integration.py` |
| AC-5 | 案例库实体 + 端口 + 存储 | Task 1 / Task 4 | ErrorCase + 仓储双实现 + migration 017 | `test_error_case.py` + 集成 |
| AC-5 | 幂等 upsert + occurrence_count | Task 4 | 自然键 upsert + SAVEPOINT 容错 | 集成测试 |
| AC-6 | 闭环幂等（日志/案例/事件） | Task 5 | 同 execution 终态判定 | 集成测试 |
| AC-6 | ToolSchemaValidationFailed reliable 启用 | Task 2 | 两处配置 + 契约测试 | `test_event_channel_mapping_validation_feedback.py` |
| AC-7 | 装配 v1.4.0 + 3 新端口 | Task 6 | 组合根 + 契约测试 ×3 | 契约测试 |
| AC-7 | 性能基准（P95/成功率/准确率） | Task 7 | 三组基准 | `test_validation_feedback_integration.py` |
| 全部 | 架构约束验证（epics 硬路径） | Task 8 | 四项架构测试 | `tests/unit/architecture/test_validation_feedback.py` |
| 全部 | 开发结束验收 | Task 9 | 收尾场景 ×2 | feature/.py 收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7（规范源头）

> **目的：** 在进入代码实现前，明确 Schema、端口契约、领域异常契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 领域事件 Schema 定稿（2 新事件字段表 + `ToolSchemaValidationFailed` reliable 启用决策）
- [ ] Subtask 0.2: 数据模型定稿（ErrorCase / EvolutionLogEntry / FixAttempt / INFEASIBLE / ErrorSignatureExtractor 签名算法规范）
- [ ] Subtask 0.3: 端口契约清单定稿（SSOT 表 4 行 + 方法签名）
- [ ] Subtask 0.4: 领域异常契约定稿（399 五处登记 Checklist + 383/399 语义区分声明）
- [ ] Subtask 0.5: API 契约确认（无新端点 + HTTP_MAP 422）
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_validation_feedback_loop.feature`（AC-x.y 场景集全枚举 + 收尾场景）
- [ ] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_validation_feedback_loop.py`
- [ ] Subtask 0.8: 编写 3 个端口契约测试 + 事件契约/通道映射契约测试（红）
- [ ] Subtask 0.9: 红窗口确认——验收 .py 与契约测试运行失败且失败形态符合预期（collection ERROR / ImportError 属预期中间态；Gherkin 场景因步骤未实现跳过不计红）
- [ ] Subtask 0.10: 前置依赖实地验证——4.3 装饰器链/4.4 沙箱适配器/`configs/event_channels.yaml` 现状冒烟（确认预留注释与实际一致）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域模型与领域服务

**关联 AC:** AC-3（INFEASIBLE）、AC-4（EvolutionLogEntry）、AC-5（ErrorCase/签名）

#### TDD 循环 A：ErrorCase 聚合根 + EvolutionLogEntry 聚合根 + FixAttempt 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_case.py` + `test_evolution_log_entry.py`（构造不变量：UUID 有效/签名 64 hex/occurrence_count≥1/enhanced_retry_count∈[1,3]/终态语义/非法构造抛 242） |
| 🟢 绿 | 实现 `src/domain/entities/error_case.py`、`evolution_log_entry.py`、`src/domain/value_objects/validation_feedback.py` 最小代码 |
| 🔄 重构 | 类型注解、中文 docstring（Google 风格）、`__all__` |

- [ ] Subtask 1.1: 🔴 红 — 编写两聚合根 + 值对象失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现三模型最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 B：ErrorSignatureExtractor 领域服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_signature_extractor.py`（STDERR 归一化：路径/行号/时间戳/内存地址剥离后同根因收敛同签名；violations 排序归一化；空输入处理） |
| 🟢 绿 | 实现 `src/domain/services/error_signature_extractor.py`（纯函数，sha256 前 16 hex） |
| 🔄 重构 | 确认零外部依赖（仅标准库 hashlib/re） |

- [ ] Subtask 1.4: 🔴 红 — 编写签名提取失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现签名提取最小代码
- [ ] Subtask 1.6: 🔄 重构 — 优化代码

#### TDD 循环 C：ToolResultStatus.INFEASIBLE 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_result_status.py`（INFEASIBLE 存在/INVALID 既有语义不回归/SUCCESS 不变量不回归） |
| 🟢 绿 | `src/domain/value_objects/tool_execution.py` 枚举追加 `INFEASIBLE = "infeasible"`（additive，frozen dataclass 加值零风险） |
| 🔄 重构 | docstring 更新（终态不可行语义 + 与 INVALID"可重试"的区分） |

- [ ] Subtask 1.7: 🔴 红 — 编写枚举扩展失败测试
- [ ] Subtask 1.8: 🟢 绿 — 追加枚举值
- [ ] Subtask 1.9: 🔄 重构 — 更新语义注释

**完成标准/Definition of Done:**
- [ ] 两聚合根 + 值对象 + 领域服务 + 枚举扩展全部实现
- [ ] TDD 循环全部通过
- [ ] 领域层覆盖率 ≥90%

---

### Task 2: 领域事件与异常体系

**关联 AC:** AC-3（399 + 两事件）、AC-6（reliable 通道补全）

#### TDD 循环 A：领域事件 ×2

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_events.py`（字段默认值/`to_dict()` 序列化 str 化/aggregate_id 关联 execution_id/event_type 注册） |
| 🟢 绿 | 实现 `src/domain/events/validation_feedback_events.py` + `events/__init__.py` 导出 |
| 🔄 重构 | 4-5 R1-F01 教训核查：metadata/字段全 str 化 |

- [ ] Subtask 2.1: 🔴 红 — 编写事件失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现两事件
- [ ] Subtask 2.3: 🔄 重构 — 序列化安全核查

#### TDD 循环 B：异常 399 全链路登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_exceptions.py`（code=EXCEPTION_399/继承 BusinessException/context 四字段/子域=toolchain）+ `test_exception_handlers.py` 期望集合更新（先红） |
| 🟢 绿 | 新建 `validation_feedback_exceptions.py` → `_code_ranges.py` 两处 → `__init__.py` → `EXCEPTION_HTTP_MAP`（399→422）→ 设计文档两表 → 预留注释改已分配 |
| 🔄 重构 | `grep -rn "EXCEPTION_399" src/` 碰撞自查 + 8 项既有异常测试全绿 |

- [ ] Subtask 2.4: 🔴 红 — 编写异常失败测试
- [ ] Subtask 2.5: 🟢 绿 — 五处登记实现
- [ ] Subtask 2.6: 🔄 重构 — 碰撞自查 + 全量异常测试

#### TDD 循环 C：事件通道双登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_channel_mapping_validation_feedback.py`（两新事件双通道两处逐字段一致 + ToolSchemaValidationFailed 升级双通道后两处一致） |
| 🟢 绿 | `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py` DEFAULT_MAPPINGS 同步更新（含 4.3 注释"reliable 4.7 启用"改"已启用"） |
| 🔄 重构 | YAML > DEFAULT_MAPPINGS 优先级注释保持 |

- [ ] Subtask 2.7: 🔴 红 — 编写通道映射失败测试
- [ ] Subtask 2.8: 🟢 绿 — 两处配置同步
- [ ] Subtask 2.9: 🔄 重构 — 契约测试转绿确认

**完成标准/Definition of Done:**
- [ ] 399 异常五处登记完成且既有异常测试全绿
- [ ] 两事件 + 通道双登记完成
- [ ] 契约测试通过

---

### Task 3: STDERR 捕获数据链贯通

**关联 AC:** AC-1

#### TDD 循环 A：ExecutionError 增强 + 适配器填充

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_sandbox_exceptions.py`（stderr/exit_code 可选参数写入 context/默认 None 不破坏 4.4 既有断言）+ 新建 `test_aiodocker_adapter_stderr.py`（失败路径异常 context 含 stderr[:2000] 与 exit_code） |
| 🟢 绿 | `sandbox_exceptions.py` ExecutionError 构造器增强 + `aiodocker_sandbox_adapter.py:511-518` 填充 |
| 🔄 重构 | 截断常量提取（≤2000） |

- [ ] Subtask 3.1: 🔴 红 — 编写异常增强与适配器填充失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现两处最小改动
- [ ] Subtask 3.3: 🔄 重构 — 优化代码

#### TDD 循环 B：SandboxSecurityDecorator 事件填充 + cause 链提取 helper

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `test_sandbox_security_decorator_events.py`（SandboxExecutionFailed 事件 execution_id/stderr 填充断言——字段已预留未填）+ cause 链提取 helper 测试（嵌套异常链中定位 ExecutionError 并提取 stderr） |
| 🟢 绿 | `sandbox_security_decorator.py:132-137` 事件填充 + 新增 cause 链 stderr 提取函数（供 4.7 装饰器复用，放置于该模块导出） |
| 🔄 重构 | 4.4 既有测试全量回归（事件字段新增不破坏旧断言） |

- [ ] Subtask 3.4: 🔴 红 — 编写事件填充失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现填充与提取
- [ ] Subtask 3.6: 🔄 重构 — 4.4 回归确认

**完成标准/Definition of Done:**
- [ ] STDERR 三段链贯通（adapter → 异常 context → 事件 + cause 链提取）
- [ ] 4.4 既有测试零回归
- [ ] TDD 循环全部通过

---

### Task 4: 仓储端口与存储双实现

**关联 AC:** AC-4、AC-5

#### TDD 循环 A：端口 + InMemory 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_case_repository.py` + `test_evolution_log_repository.py`（InMemory：search_by_signature 语义/record_case 自然键 upsert 计数/save 幂等/list_by_query 分页过滤/get_by_*） |
| 🟢 绿 | 实现 `src/domain/ports/error_case_repository.py`（含 EvolutionLogQuery 于 evolution_log_repository.py）+ `src/infrastructure/storage/inmemory/` 双实现 |
| 🔄 重构 | InMemory 深拷贝防共享引用污染（4-6 CR1-2 教训） |

- [ ] Subtask 4.1: 🔴 红 — 编写双仓储 InMemory 失败测试
- [ ] Subtask 4.2: 🟢 绿 — 实现端口 + InMemory
- [ ] Subtask 4.3: 🔄 重构 — 深拷贝防护

#### TDD 循环 B：PG 模型 + migration 017 + PG 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | PG 仓储测试（独立 schema + savepoint rollback 模式：upsert 幂等/UNIQUE 冲突 begin_nested 容错重读/JSONB fix_attempts 读写） |
| 🟢 绿 | `models/error_case.py` + `models/evolution_log_entry.py` + `repository/` 双实现 + `deploy/postgresql/alembic/versions/017_validation_feedback.py`（表设计见 Dev Notes） |
| 🔄 重构 | migration 仅新增不修改既有（红线） |

- [ ] Subtask 4.4: 🔴 红 — 编写 PG 仓储失败测试
- [ ] Subtask 4.5: 🟢 绿 — 实现 PG 双仓储 + migration 017
- [ ] Subtask 4.6: 🔄 重构 — 事务边界优化

#### TDD 循环 C：组合根注册 + 契约测试转绿

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 编写的 `test_port_contract_error_case_repository.py`、`test_port_contract_evolution_log_repository.py` 保持红 |
| 🟢 绿 | `composition_root.py` 注册 2 端口（lambda 工厂 + PortSpec 10 字段） |
| 🔄 重构 | 契约测试 11 维度全绿 |

- [ ] Subtask 4.7: 🔴 红 — 契约测试红状态确认
- [ ] Subtask 4.8: 🟢 绿 — 组合根注册转绿
- [ ] Subtask 4.9: 🔄 重构 — 11 维度全绿

**完成标准/Definition of Done:**
- [ ] 双仓储 InMemory + PG 实现 + migration 017
- [ ] 契约测试 ×2 通过
- [ ] 基础设施层覆盖率 ≥75%

---

### Task 5: Validation Feedback 应用服务（闭环编排）

**关联 AC:** AC-2、AC-3、AC-5、AC-6

#### TDD 循环 A：触发判定与闭环编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_service.py` 循环 A 组（触发判定矩阵：389 入/382 入/385 出直传/207/413 出直传；增强循环 1→3 次计数；耗尽抛 399） |
| 🟢 绿 | 实现 `src/application/ports/validation_feedback_service.py` + `src/application/services/validation_feedback_service.py`（recover 编排：提取→检索→修复→重执行→记录）+ `validation_feedback_prompts.py` |
| 🔄 重构 | 383/399 语义区分注释显式化 |

- [ ] Subtask 5.1: 🔴 红 — 编写触发判定失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现服务骨架与触发判定
- [ ] Subtask 5.3: 🔄 重构 — 优化判定逻辑

#### TDD 循环 B：修复生成 + 防放大 + 案例回填

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 循环 B 组（LLM 修复 prompt 组装含案例 fix_summary/空案例 PURE_LLM 降级/增强期间 Engine max_attempts=1 且 finally 恢复/恢复成功记 RECOVERED 案例 + ToolExecutionRecovered 事件/耗尽记 MARKED_INFEASIBLE 案例 + ToolExecutionMarkedInfeasible 事件 + 演进日志） |
| 🟢 绿 | 实现修复循环 + 案例回填 + 演进日志写入 + 事件发布（fire-and-forget，P0-I 模式） |
| 🔄 重构 | Fake LLM 按 system_prompt 角色标记分派（4-5 教训）核查测试自身 |

- [ ] Subtask 5.4: 🔴 红 — 编写修复与回填失败测试
- [ ] Subtask 5.5: 🟢 绿 — 实现完整闭环
- [ ] Subtask 5.6: 🔄 重构 — 优化代码

#### TDD 循环 C：幂等与 evolution log

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 循环 C 组（同 execution 重复 recover：演进日志单行/事件单次/案例计数递增） |
| 🟢 绿 | 终态判定短路（已有终态记录直接返回） |
| 🔄 重构 | 幂等键统一为 execution_id |

- [ ] Subtask 5.7: 🔴 红 — 编写幂等失败测试
- [ ] Subtask 5.8: 🟢 绿 — 实现幂等短路
- [ ] Subtask 5.9: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] 闭环编排完整（触发/检索/修复/重试/回填/标记/日志）
- [ ] 应用层覆盖率 ≥85%
- [ ] TDD 循环全部通过

---

### Task 6: 装饰器集成、装配升级与 outbox 可靠性修复

**关联 AC:** AC-2、AC-3、AC-4、AC-7

#### TDD 循环 A：ValidationFeedbackDecorator + 引擎 hints

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_decorator.py`（捕获 389/382 委托 service/其他异常透传/INFEASIBLE 结果转换不抛异常）+ `test_tool_execution_engine_hints.py`（`validation_feedback_hints` 扩展键读取并拼入 Think/Code prompt/无 hints 零行为变化） |
| 🟢 绿 | 实现 `src/application/services/validation_feedback_decorator.py` + `tool_execution_engine.py` prompt 构建扩展（`__init__` 签名不变） |
| 🔄 重构 | 引擎改动面最小化核查（4.4 AC-7.4 BDD 断言保护） |

- [ ] Subtask 6.1: 🔴 红 — 编写装饰器与 hints 失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现装饰器 + 引擎扩展
- [ ] Subtask 6.3: 🔄 重构 — 优化代码

#### TDD 循环 B：装配升级 v1.4.0 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_port_contract_validation_feedback_service.py` 红 + `test_port_contract_tool_execution_service.py` 版本期望升级 v1.4.0（先红） |
| 🟢 绿 | `composition_root.py`：注册 `validation_feedback_service` + 装饰链最外层加 ValidationFeedbackDecorator + version/compatibility/tags 更新 |
| 🔄 重构 | 契约测试 11 维度 ×2 全绿 + 既有 tool_execution_service 契约回归 |

- [ ] Subtask 6.4: 🔴 红 — 契约测试红确认
- [ ] Subtask 6.5: 🟢 绿 — 装配升级转绿
- [ ] Subtask 6.6: 🔄 重构 — 全绿确认

#### TDD 循环 C：outbox 独立 session 结构性修复（defer 债清偿）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写失败场景测试：模拟请求 session 回滚（后台/CLI 路径），断言 reliable 事件 outbox 写入不随回滚丢失（当前行为下红） |
| 🟢 绿 | `src/infrastructure/messaging/`（outbox 写入路径/dual_channel_event_bus）reliable 写入包裹独立 `session_context`（`outbox_processor.py:148-149` 先例；**修复必须落在 infrastructure 层**——application 禁 import infrastructure） |
| 🔄 重构 | 正常 HTTP 路径行为零变化回归断言 + `tool_execution_engine.py:283-285` 与 `data_source_resolver.py:352` 两处 defer 注释更新为"已修复" |

- [ ] Subtask 6.7: 🔴 红 — 编写 outbox 独立 session 失败测试
- [ ] Subtask 6.8: 🟢 绿 — 实现独立 session 修复
- [ ] Subtask 6.9: 🔄 重构 — 双路径回归 + 注释清偿

**完成标准/Definition of Done:**
- [ ] 装饰链四层装配 + v1.4.0
- [ ] outbox 修复落地 + defer 注释清偿
- [ ] 既有契约测试零回归

---

### Task 7: 集成测试与性能基准

**关联 AC:** AC-4、AC-5、AC-6、AC-7

> 无独立 TDD 循环表——本 Task 为真实服务全链验证（epics 硬路径 `tests/integration/test_validation_feedback_integration.py`）。

- [ ] Subtask 7.1: 全链闭环集成测试（真实 PG 独立 schema + savepoint rollback + 租户隔离：模拟沙箱失败→闭环→恢复/耗尽两路径；InMemory→PG 仓储替换真实实现）
- [ ] Subtask 7.2: 幂等集成测试（重复触发三副作用断言）
- [ ] Subtask 7.3: 性能基准一——闭环开销 P95<5s（签名提取+检索+日志写入计时，20 次采样，CI 容差 1.8×）
- [ ] Subtask 7.4: 性能基准二——恢复成功率 ≥80%（20 次可修复故障注入，AsyncMock LLM 可编程修复序列）
- [ ] Subtask 7.5: 性能基准三——不可行标记准确率 ≥95%（20 次不可修复 100% 标记 + 可修复 0 误标）
- [ ] Subtask 7.6: outbox 修复集成回归（后台路径事件投递 + HTTP 路径零变化）

**完成标准/Definition of Done:**
- [ ] 集成测试全绿（真实服务）
- [ ] 三组性能基准达标
- [ ] 集成覆盖率 ≥75%

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** 全部（epics 硬路径四项架构测试）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 8.1: 创建 `tests/unit/architecture/test_validation_feedback.py`（epics 指定硬路径）
- [ ] Subtask 8.2: 重试增强验证器——STDERR 捕获与修复建议生成链路断言（触发→prompt 含 STDERR/案例→重执行）
- [ ] Subtask 8.3: 失败标记验证器——3 次增强失败后 INFEASIBLE + 399 + 事件三联断言
- [ ] Subtask 8.4: 幂等性验证器——重复执行零副作用（日志/案例/事件）
- [ ] Subtask 8.5: 演进日志验证器——失败历史可追溯（双查询面）
- [ ] Subtask 8.6: 循环依赖检测使用 ruff/isort（不引入 pylint）+ 运行完整测试套件生成报告

**完成标准/Definition of Done:**
- [ ] 四项架构测试（epics 枚举）全部通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

### Task 9: 开发结束验收测试

**关联 AC:** 全部

> **性质说明：** 本 Task 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 feature 中的收尾验收场景（src 清成清单 + tests 四目录完成清单——存在性+可导入性断言） |
| 🟢 绿 | 编写 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 9.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 9.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 9.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 9.4: 运行 `poetry run pytest tests/ -n 8`、`ruff check`、`mypy` + 三条异常红线 grep 自查收尾

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] 四测试目录完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md §17.3`](../../../docs/architecture/architecture.md) + [`sisys-core-domain-design.md §17.2.3/§17.2.4`](../../../docs/architecture/sisys-core-domain-design.md)

- **架构模式:** 六边形架构 + Decorator 装饰链（4.3 ToolOutputValidator / 4.4 SandboxSecurityDecorator 先例）+ DDD Query Object + 事件双通道（realtime Redis pub/sub + reliable RabbitMQ/Outbox）
- **设计约束:** 领域层零依赖；application 禁 import infrastructure（outbox 修复必须落 infrastructure/messaging）；端口组合根统一注册（lambda 工厂 + PortSpec 10 字段）；既有引擎 `__init__` 签名不可变（4.4 AC-7.4 BDD 断言）
- **接口治理:** 统一端口注册、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配、契约优先、版本化兼容（v1.4.0 compatibility 双版本）、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+ / SQLAlchemy 2.0 async / jsonschema Draft7 / aiodocker / litellm（经 LLMClientPort 抽象）
- **原始蓝图:** `sisys-core-domain-design.md:740-746`（引擎 except 分支 code_fixer.fix 重试草案）与 `:810-816`（PersistentSandbox STDERR 捕获 + error_db.search 草案）——本 Story 将蓝图落为装饰器 + ErrorCaseRepositoryPort 实现

### 关键架构决策

| # | 决策点 | 选中方案 | 依据 |
|---|--------|---------|------|
| 1 | **闭环挂载方式** | **装饰器同步闭环**（`ValidationFeedbackDecorator` 装饰链最外层，捕获 389/382 触发） | 与 4.3/4.4 装饰器先例一致；同步 in-path 可测性好（TDD 友好）；4.3 蓝图的"事件订阅 + 60s 终止确认超时"复杂度高且异步重执行需任务重新调度基础设施；订阅契约（execution_id 去重/is_final）在装饰器 catch 点天然成立——事件仍发布供外部消费者（审计/监控），闭环本身不依赖事件回环 |
| 2 | 不可行标记载体 | `ToolResultStatus.INFEASIBLE` 新枚举值 + 领域事件 + 演进日志（**不改** ToolExecutionState 6 状态机） | 状态机改动破坏面大（VALID_TRANSITIONS/既有 4.1a 测试）；ToolResult 是调用方契约面（DAG 按 status 分支）；"终态反向迁移禁止（重试创建新 attempt）"注释语义保持 |
| 3 | 耗尽对外契约 | 返回 `ToolResult(INFEASIBLE)` 不抛异常；399 为内部信号 | ToolChain DAG 后续节点按 status 感知不中断；4.3 蓝图"降级到人工审核"非本 epic 范围 |
| 4 | 异常编码 | 仅 1 个新异常占 399；**不扩 400-409** | 方案 A 触发条件（≥2 异常）未满足；Fallback/HumanReview/Canary 三预测异常均属非本 epic 的扩展链路（见非目标） |
| 5 | 错误签名算法 | 领域服务纯函数归一化（剥路径/行号/时间戳/内存地址）→ sha256 前 16 hex | 确定性可测；同根因不同表层输出收敛（幂等前提）；V1 精确匹配，向量检索留 L3 扩展 |
| 6 | 案例回填时机 | 恢复成功回填 RECOVERED 案例（错误→修复对）+ 耗尽回填 MARKED_INFEASIBLE | 成功案例对后续修复价值最高（Few-Shot 素材）；失败案例支撑准确率统计 |
| 7 | STDERR 链修复方式 | `ExecutionError` 构造器可选参数（stderr/exit_code 入 context）+ adapter 填充 + 装饰器事件填充 | 向后兼容（默认值零改动既有调用）；事件字段已预留（sandbox_events.py:96/101/104）只欠填充 |
| 8 | 防重试放大 | 增强循环期间内层 Engine `_retry.max_attempts=1` 临时降级 + try/finally 恢复 | 4.3 P0-1 教训直接复用（3×3×3×3=81x LLM 调用触发超时）；ToolOutputValidator 同款模式先例 |
| 9 | hints 注入通道 | `context.extensions["validation_feedback_hints"]`（ExecutionContext frozen + with_extension 工厂） | P0-D 模式先例（schema_last_violations 同款）；引擎 `__init__` 签名不变 |
| 10 | outbox 修复落点 | infrastructure/messaging outbox 写入独立 session_context | 两处 defer 注释显式指派本 Story；outbox_processor.py:148-149 独立 session 先例；application 层禁 import infrastructure 约束 |
| 11 | 性能指标口径 | P95<5s 限闭环自身开销（签名/检索/日志），LLM 与沙箱时长除外 | epic 字面指标可测化——LLM 生成受 LLMConfig.timeout=600s 支配物理上不可能 <5s；Task 0 与业务确认留痕 |

### 核心编排流程（ValidationFeedbackDecorator 实现蓝图）

```python
class ValidationFeedbackDecorator:
    """装饰链最外层：SandboxSecurityDecorator > ToolOutputValidator > Engine 之外再包一层"""

    def __init__(self, wrapped, feedback_service: ValidationFeedbackServicePort):
        self._wrapped = wrapped            # SandboxSecurityDecorator(ToolOutputValidator(Engine))
        self._feedback = feedback_service

    async def execute(self, tool_id, tool, tool_call, context) -> ToolResult:
        try:
            return await self._wrapped.execute(tool_id, tool, tool_call, context)
        except (ToolResultValidationError, ToolExecutionFailedError) as trigger:
            # 389 = OUTPUT 校验基础重试耗尽（violations 可修复语义）
            # 382 = 执行失败（cause 链可提取沙箱 STDERR）
            # 385/207/413 等不在此捕获——超时/策略违规不可修复，直接上抛
            return await self._feedback.recover(
                tool_id=tool_id, tool=tool, tool_call=tool_call,
                context=context, trigger_error=trigger,
            )
        # ToolExecutionTimeoutError / 领域异常组 / DataSourceError → 不捕获自然上抛


class ValidationFeedbackService:
    async def recover(self, tool_id, tool, tool_call, context, trigger_error) -> ToolResult:
        # 幂等短路：已有该 execution 终态演进日志 → 直接返回既有结论
        # 1. 提取错误上下文：cause 链提取 stderr（ExecutionError.context）或 violations（389.context）
        # 2. signature = ErrorSignatureExtractor.extract(stderr) / extract_from_violations(...)
        # 3. 增强循环 attempt 1..3（RetryPolicy.max_attempts=3 语义）：
        #    a. cases = error_case_repo.search_by_signature(tenant, tool, signature)
        #    b. fix_prompt = 组装(原 code + stderr + cases.fix_summary + violations)
        #       fix_strategy = CASE_GUIDED if cases else PURE_LLM
        #    c. hints_context = context.with_extension("validation_feedback_hints", {...})
        #    d. 临时 wrapped._retry.max_attempts=1 → try: 重执行内层链 → finally 恢复
        #    e. 成功 → 回填 RECOVERED 案例 + 演进日志(RECOVERED) + ToolExecutionRecovered 事件
        #            → return ToolResult(SUCCESS, retry_count=attempt)
        # 4. 耗尽 → 抛/捕获 ValidationFeedbackRetryExhaustedError(399) 内部信号
        #    → 回填 MARKED_INFEASIBLE 案例 + 演进日志(MARKED_INFEASIBLE)
        #       + ToolExecutionMarkedInfeasible 事件
        #    → return ToolResult(INFEASIBLE, output={error_signature, stderr_excerpt, attempts}, retry_count=3)
```

**触发判定矩阵（必须完整测试）：**

| 触发异常 | 编码 | 入闭环 | 理由 |
|---------|------|--------|------|
| `ToolResultValidationError` | 389 | ✅ | OUTPUT 校验基础重试耗尽，violations 可指导修复 |
| `ToolExecutionFailedError` | 382 | ✅ | 执行失败（含沙箱启动失败 `stage="SANDBOX_START"` 直抛路径），cause 链可提取 STDERR |
| `ToolExecutionTimeoutError` | 385 | ❌ 直传 | 超时不可修复（重试同样超时） |
| `BusinessRuleViolationError` | 207 | ❌ 直传 | 白名单策略违规，非代码缺陷 |
| `DataSourceError` 族 | 410-413 | ❌ 直传 | 外部数据不可用，4.1b 语义"策略违规 vs 数据不可用"区分 |
| `ValidationError` | 201 | ❌ 直传 | 标记语法错误，非运行时可修复 |

> **STDERR 实际浮现路径（防困惑，重要）**：沙箱代码执行失败（`ExecutionError` 313 在引擎 retryable 白名单内）→ 引擎内部重试 3 次耗尽抛 `ToolExecutionRetryExhaustedError`（383）→ `ToolOutputValidator` 的 `retry_policy_for_validation` 含 383（`tool_output_validator.py:201-204`）再重试 3 次耗尽后**转换为 389 抛出**（`:223-229`，`from retry_exc` 保留因果链）。即 STDERR 场景在最外层以 **389 形态浮现**，其 `__cause__` 链为 `389 → 383 → ExecutionError(context.stderr)`；沙箱**启动**失败则经引擎 `SANDBOX_START` 分支以 382 直浮（`tool_execution_engine.py:162-167`）。因此 STDERR 提取 helper 必须同时走 `__cause__` 链**和** 383 的自定义 `cause` 属性（`retry_helpers.py:112-117`）——Task 3 的嵌套链测试必须覆盖这两个分支。

### 数据库表设计（migration 017: `017_validation_feedback.py`）

```sql
-- error_cases：错误案例库（自然键 UNIQUE）
CREATE TABLE error_cases (
    id                UUID PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    tool_id           UUID NOT NULL,
    error_signature   VARCHAR(64) NOT NULL,
    error_category    VARCHAR(64) NOT NULL,          -- 沙箱 error_code（EXCEPTION_313 等）或 'SCHEMA_VIOLATION'
    stderr_excerpt    VARCHAR(2000) NOT NULL DEFAULT '',
    fix_summary       VARCHAR(1000) NOT NULL DEFAULT '',
    outcome           VARCHAR(32) NOT NULL,          -- RECOVERED / MARKED_INFEASIBLE
    occurrence_count  INTEGER NOT NULL DEFAULT 1,
    last_seen_at      TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_error_cases_natural_key UNIQUE (tenant_id, tool_id, error_signature)
);
CREATE INDEX ix_error_cases_tool ON error_cases (tenant_id, tool_id, error_signature);

-- tool_evolution_logs：演进日志（execution_id 幂等）
CREATE TABLE tool_evolution_logs (
    id                    UUID PRIMARY KEY,
    tenant_id             UUID NOT NULL,
    tool_id               UUID NOT NULL,
    execution_id          UUID NOT NULL,
    tool_version          VARCHAR(64) NOT NULL DEFAULT '',
    error_signature       VARCHAR(64) NOT NULL,
    enhanced_retry_count  INTEGER NOT NULL,           -- 1-3
    fix_attempts          JSONB NOT NULL DEFAULT '[]', -- FixAttempt 摘要数组
    final_status          VARCHAR(32) NOT NULL,       -- RECOVERED / MARKED_INFEASIBLE
    created_at            TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_tool_evolution_logs_execution UNIQUE (tenant_id, execution_id)
);
CREATE INDEX ix_tool_evolution_logs_tool ON tool_evolution_logs (tenant_id, tool_id, created_at DESC);
```

### ⚠️ 实现陷阱提示（Pitfalls）

1. **事件 metadata 序列化**：新事件字段一律 `str()` 化入 metadata/payload（4-5 R1-F01：UUID 对象 → json.dumps TypeError → reliable 通道 100% 静默失败）。
2. **HTTP_MAP 注释对齐**：`exception_handlers.py` 注释行内 `# 399 — ...` 与实际 code 严格一致（4.1a 偏移 bug 先例）。
3. **InMemory 仓储深拷贝**：save/search 返回 deepcopy 副本（4-6 CR1-2：共享引用致测试间状态污染）。
4. **PG upsert 并发**：UNIQUE 冲突 flush 后 session 进 PendingRollback，必须 `begin_nested()` SAVEPOINT 包裹重读（4-6 CR1-4）。
5. **frozen dataclass 加字段**：新字段必须带默认值且置于既有字段之后（4-6 教训）。
6. **`configs/event_channels.yaml`**：实际路径是 `configs/`（复数）不是 `config/`；YAML 与 DEFAULT_MAPPINGS 两处必须同步（YAML 优先）。
7. **设计文档两个 §3.3.2**：`sisys-uni-exception-design.md` 存在同号小节，编码分配表与子域范围表都要更新（4-6 踩坑）。
8. **装饰器恢复 Engine `_retry`**：临时降级必须 try/finally 防御性恢复（ToolOutputValidator:216-233 同款双保险）。
9. **禁止 `# noqa`/`# type: ignore`**：三条 grep 自查零输出后才可提交。
10. **性能计时口径**：P95 基准的计时窗口排除 LLM/沙箱调用（mock 替身注入切换点 `await asyncio.sleep(0)`——4-5 R2-F02）；CI 慢机容差 1.8×。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── error_case.py                    # [新] 错误案例聚合根
│   │   └── evolution_log_entry.py           # [新] 演进日志聚合根
│   ├── events/
│   │   └── validation_feedback_events.py    # [新] 2 领域事件
│   ├── exceptions/
│   │   ├── validation_feedback_exceptions.py # [新] EXCEPTION_399
│   │   ├── sandbox_exceptions.py            # [改] ExecutionError stderr/exit_code 参数
│   │   ├── _code_ranges.py                  # [改] 399 登记 + 子域映射
│   │   └── __init__.py                      # [改] 导出
│   ├── ports/
│   │   ├── error_case_repository.py         # [新] 案例库端口
│   │   └── evolution_log_repository.py      # [新] 演进日志端口（含 EvolutionLogQuery）
│   ├── services/
│   │   └── error_signature_extractor.py     # [新] 签名提取纯函数
│   └── value_objects/
│       ├── validation_feedback.py           # [新] FixAttempt 值对象
│       └── tool_execution.py                # [改] ToolResultStatus.INFEASIBLE
├── application/
│   ├── ports/
│   │   └── validation_feedback_service.py   # [新] 服务端口
│   └── services/
│       ├── validation_feedback_service.py   # [新] 闭环编排
│       ├── validation_feedback_decorator.py # [新] 装饰链最外层
│       ├── validation_feedback_prompts.py   # [新] 修复 prompt 模板
│       ├── tool_execution_engine.py         # [改] hints prompt 读取 + defer 注释清偿
│       └── sandbox_security_decorator.py    # [改] 事件 execution_id/stderr 填充
├── infrastructure/
│   ├── external_services/sandbox/
│   │   └── aiodocker_sandbox_adapter.py     # [改] stderr 填入异常 context
│   ├── messaging/
│   │   ├── channel_router.py                # [改] 新事件 + reliable 升级
│   │   └── (outbox 写入路径)                 # [改] 独立 session 修复
│   └── storage/
│       ├── inmemory/
│       │   ├── error_case_repository.py     # [新]
│       │   └── evolution_log_repository.py  # [新]
│       └── postgresql/
│           ├── models/
│           │   ├── error_case.py            # [新]
│           │   └── evolution_log_entry.py   # [新]
│           └── repository/
│               ├── error_case_repository.py     # [新]
│               └── evolution_log_repository.py  # [新]
├── interfaces/api/
│   └── exception_handlers.py                # [改] 399→422
└── composition_root.py                      # [改] 3 新端口 + v1.4.0 装配

deploy/postgresql/alembic/versions/
└── 017_validation_feedback.py               # [新] 双表

configs/
└── event_channels.yaml                      # [改] 2 新事件 + reliable 升级

docs/architecture/
└── sisys-uni-exception-design.md            # [改] 两表 + 预留注释更新
```

### 已有资产复用清单（防重复造轮子 —— 实现前必读）

| 资产 | 位置 | 复用方式 |
|------|------|----------|
| `SandboxExecutionFailed` 事件 `stderr`/`execution_id` 字段 | `src/domain/events/sandbox_events.py:96,101,104` | **已预留无需新建**，仅由发布方填充（Task 3） |
| `ToolSchemaValidationFailed` 事件 13 字段（is_final/retry_attempt/schema_version） | `src/domain/events/tool_schema_events.py:25` | reliable 通道升级（Task 2），外部消费者面 |
| `ToolOutputValidator` 耗尽契约 | `src/application/services/tool_output_validator.py:220-229` | 抛 389 即本 Story 触发信号，**禁止改动其语义** |
| `_call_with_retry` / `RetryPolicy` | `src/application/services/retry_helpers.py:36,62` | 增强循环复用（max_attempts=3 + on_failure_callback） |
| cause 链解包先例 `_unwrap_sandbox_error` | `src/application/services/sandbox_security_decorator.py:100-120` | stderr 提取 helper 参照实现 |
| `context.extensions` 注入模式（P0-D） | `tool_output_validator.py:135-141` + `tool_execution_engine.py:446-447` | `validation_feedback_hints` 同款通道 |
| `with_extension` frozen 工厂 | `src/domain/value_objects/tool_execution.py:95` | hints 上下文透传 |
| `LLMClientPort.generate` | `src/domain/ports/llm_client.py:137` | 修复代码生成（无需新端口） |
| `EXCEPTION_399` 预留 | `_code_ranges.py:85` + `sisys-uni-exception-design.md:718` | 直接占用（勿新开码位） |
| `session_context` 独立会话 | `src/infrastructure/storage/postgresql/session_context.py:100` + outbox_processor.py:148-149 先例 | outbox 修复复用 |
| `ToolExecutionQuery` Query Object 先例 | `src/domain/ports/tool_execution_repository.py:24` | EvolutionLogQuery 同款模式 |
| 4.3 订阅契约设计 | `stories/4-3-tool-io-schema-validation.md:1600-1669`「4.6/4.7 架构演进路径」 | 事件字段消费方式参照（去重键/is_final/schema_version 防漂移） |
| 端口契约测试 11 维度样板 | `tests/contracts/test_port_contract_tool.py` | 新契约测试同款结构 |
| 事件通道映射契约样板 | `tests/contracts/test_event_channel_mapping_tool_version.py` | 同款逐字段断言 |
| fire-and-forget 事件发布 + violations 截断 helper | `src/application/services/schema_event_helpers.py`（`publish_schema_event_async`/`truncate_violations_for_event`，P0-H/P0-I） | 新事件发布复用同款模式（不阻塞主流程 + 截断防 DoS） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-6](./4-6-tool-version-management.md)（done）+ [Story 4-5](./4-5-red-blue-debate-basic.md)（done）+ [Story 4-3](./4-3-tool-io-schema-validation.md)（done）

**关键学习/Key Learnings:**
- 4-3 P0-1：装饰器重试与 Engine 内部重试叠加 → 81x LLM 调用放大触发超时——增强循环必须临时降级内层 max_attempts=1
- 4-5 R1-F01：事件 metadata 携带 UUID 对象 → json 序列化 TypeError → reliable 通道 100% 静默失败——字段一律 str 化
- 4-6 CR1-4：PG UNIQUE 冲突后 PendingRollback → begin_nested SAVEPOINT 包裹容错重读
- 4-6 R3-1：应用层禁止 import infrastructure（import-linter 契约）——注入端口/标量，outbox 修复落 infrastructure
- 4-5 R1-F06/R2-F01：Fake LLM 禁按易混淆子串分派（按 response_schema/system_prompt 角色标记）；mock 需真实挂起点（asyncio.sleep）
- 4-6 文档审查 R1 系列：规范内部矛盾/死锁/不可达是 P0 高发区——Task 0 触发判定矩阵必须完整无死角
- 4-6 留项登记纪律：defer 项显式登记留痕（本 Story 兑现 399/事件字段/reliable 通道/outbox session 四笔预留债）

**应用到本故事/Applied to This Story:**
- [ ] 增强循环防放大（AC-2 硬性验证项）
- [ ] 事件字段 str 化 + InMemory deepcopy + SAVEPOINT 容错（实现陷阱清单）
- [ ] 触发判定矩阵六行全覆盖测试（回归网先行）
- [ ] 四笔预留债逐项清偿并在原注释处更新状态

### 非目标（Out of Scope）

- ❌ **工具熔断**（or.md 七.7.(3)"连续 3 次校验失败自动熔断"）——不在本 epic AC 清单，与反馈闭环正交；**登记 `deferred-work.md`**（建议挂 Story 5.x Agent 弹性隔离或独立运维 Story）
- ❌ 向量相似案例检索（L3 Qdrant embedding）——V1 精确签名匹配；签名泛化不足以支撑时再立项
- ❌ 自动灰度推进（按成功率自动 promote）——4-6 非目标登记"属 4.7/后续"；评估：自动 promote 需 per-version 成功率统计与安全护栏，超出本 Story 反馈闭环边界，**继续 defer 并登记**（演进日志已提供失败历史数据面，未来自动闭环的数据输入已就绪）
- ❌ per-version 执行统计视图（4-6 登记"4.7 输入"）——演进日志 `tool_evolution_logs` 表 + `list_by_tool` 查询面已覆盖失败侧历史；成功率聚合视图 defer（有真实运维诉求时基于本表实现）
- ❌ 人工审核降级通道（`ValidationFeedbackHumanReviewTimeoutError`）、备选 Tool 回退（`ValidationFeedbackFallbackFailedError`）、灰度 canary 联动（`ValidationFeedbackCanaryConflictError`）——4.3 预测的三个扩展异常均不立项，400-409 保持未分配
- ❌ 演进日志/案例库 REST 查询 API 与 CLI——本 Story 无新端点；查询面经仓储端口供内部消费
- ❌ `ToolInputValidator` 组合根注册补齐——4.3 遗留独立事项，与本 Story 装饰链无冲突（4.7 装饰器加在最外层不依赖它）
- ❌ 4-6 遗留项（ToolExecuted 事件 tool_version/tenant_id 回填、tools 表 PG 持久化等）——维持 4-6 非目标登记不动

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM-5.3) |
| **Version** | create-story workflow v6.3.0 / template v2.9.0 |
| **Execution Date** | 2026-10-08 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1362-1410 Story 4.7 / L145,L518,L779 FR-ST-07） |
| **架构文档** | `docs/architecture/architecture.md` §17.3 / `docs/architecture/sisys-core-domain-design.md` §17.2.3-17.2.4 |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-6-tool-version-management.md`（+4-5/4-3/4-4 学习经验） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 4.7 定义 + FR-ST-07 + 性能/覆盖率硬指标）
- [x] 架构约束从 `architecture.md`/`sisys-core-domain-design.md` 提取（§17.3 工具箱 + 蓝图伪代码）
- [x] 前一个故事学习经验整合（4-6/4-5/4-3 三故事 Review Findings 全量消化）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 代码实地调研（3 并行调研 Agent：引擎/沙箱/重试链 + 异常/端口/事件 + 前序经验/测试风格——全部 file:line 实证）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-7-validation-feedback-loop.md`

**待创建的文件/To Be Created (Dev Story 实施):**

*src 生产代码（16 新 + 14 改）：*
- `src/domain/entities/error_case.py` - 错误案例聚合根
- `src/domain/entities/evolution_log_entry.py` - 演进日志聚合根
- `src/domain/events/validation_feedback_events.py` - 2 领域事件
- `src/domain/exceptions/validation_feedback_exceptions.py` - EXCEPTION_399
- `src/domain/ports/error_case_repository.py` - 案例库端口
- `src/domain/ports/evolution_log_repository.py` - 演进日志端口 + EvolutionLogQuery
- `src/domain/services/error_signature_extractor.py` - 签名提取纯函数
- `src/domain/value_objects/validation_feedback.py` - FixAttempt 值对象
- `src/application/ports/validation_feedback_service.py` - 服务端口
- `src/application/services/validation_feedback_service.py` - 闭环编排
- `src/application/services/validation_feedback_decorator.py` - 装饰链最外层
- `src/application/services/validation_feedback_prompts.py` - 修复 prompt 模板
- `src/infrastructure/storage/inmemory/error_case_repository.py` - InMemory 实现
- `src/infrastructure/storage/inmemory/evolution_log_repository.py` - InMemory 实现
- `src/infrastructure/storage/postgresql/models/error_case.py` - PG 模型
- `src/infrastructure/storage/postgresql/models/evolution_log_entry.py` - PG 模型
- `src/infrastructure/storage/postgresql/repository/error_case_repository.py` - PG 实现
- `src/infrastructure/storage/postgresql/repository/evolution_log_repository.py` - PG 实现
- `deploy/postgresql/alembic/versions/017_validation_feedback.py` - migration 017
- 修改：`value_objects/tool_execution.py`（INFEASIBLE）、`sandbox_exceptions.py`（ExecutionError 增强）、`_code_ranges.py`、`exceptions/__init__.py`、`exception_handlers.py`（399→422）、`events/__init__.py`、`aiodocker_sandbox_adapter.py`（stderr 填充）、`sandbox_security_decorator.py`（事件填充）、`tool_execution_engine.py`（hints + defer 注释清偿）、`channel_router.py`、`composition_root.py`（3 端口 + v1.4.0）、`configs/event_channels.yaml`、`sisys-uni-exception-design.md`、outbox 写入路径（独立 session）

*测试（21 新 + 1 改）：*
- `tests/acceptance/test_acceptance_validation_feedback_loop.feature` + `.py` - 验收 Gherkin + BDD
- `tests/unit/architecture/test_validation_feedback.py` - 架构测试四项（epics 硬路径）
- `tests/integration/test_validation_feedback_integration.py` - 集成 + 性能基准（epics 硬路径）
- `tests/unit/domain/entities/test_error_case.py`、`test_evolution_log_entry.py`
- `tests/unit/domain/services/test_error_signature_extractor.py`
- `tests/unit/domain/value_objects/test_tool_result_status.py`
- `tests/unit/domain/events/test_validation_feedback_events.py`
- `tests/unit/domain/exceptions/test_validation_feedback_exceptions.py`
- `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_adapter_stderr.py`
- `tests/unit/application/services/test_sandbox_security_decorator_events.py`、`test_validation_feedback_service.py`、`test_validation_feedback_decorator.py`、`test_tool_execution_engine_hints.py`
- `tests/unit/infrastructure/storage/inmemory/test_error_case_repository.py`、`test_evolution_log_repository.py`
- `tests/contracts/test_port_contract_error_case_repository.py`、`test_port_contract_evolution_log_repository.py`、`test_port_contract_validation_feedback_service.py`、`test_event_contract_validation_feedback_events.py`、`test_event_channel_mapping_validation_feedback.py`
- 修改：`tests/unit/domain/exceptions/test_sandbox_exceptions.py`（扩展）、`tests/unit/interfaces/api/test_exception_handlers.py`（期望集合）、`tests/contracts/test_port_contract_tool_execution_service.py`（版本 v1.4.0）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.7 |
| **Story Key** | 4-7-validation-feedback-loop |
| **File** | `_bmad-output/implementation-artifacts/stories/4-7-validation-feedback-loop.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱（收官故事） |
| **价值组** | 战略工具执行能力（V1 P1 扩展） |
| **优先级** | P1-7（V1） |
| **覆盖 FR** | FR-ST-07 |
| **依赖** | 4.1a ✅ / 4.3 ✅ / 4.4 ✅ / 4.6 ✅ |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-9，10 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-7）
3. [x] Architecture constraints extracted 架构约束已提取（含 11 项关键架构决策）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4-6/4-5/4-3）
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | （待审查后填写） | | |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** [待 dev-story 完成后填写]
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] [{故事编号4-7}-{优先级P0~2}-{问题编号}][Review][Patch | Defer] **[问题精准描述]** — 决策：[决策精准描述] [blind | edge | audit] `[相对路径]:[行号范围]`

#### 已修复 Patch

- [ ] [{故事编号4-7}-{优先级P0~2}-{问题编号}][Review][Patch] [问题精准描述] [相对路径:行号] — [解决方案精准描述]

#### 已推迟 Defer

- [ ] [{故事编号4-7}-{优先级P0~2}-{问题编号}][Review][Defer] [问题精准描述] — deferred，[原因精准描述]

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-08
**最后更新/Last Updated:** 2026-10-08
**更新说明/Description:**
- v1.0.0: 创建故事文件（3 并行调研 Agent 代码实证 + 4 前序故事经验整合 + 4 笔预留债清偿方案）
