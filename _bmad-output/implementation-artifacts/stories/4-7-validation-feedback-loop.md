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

- 覆盖 **FR-ST-07 (P1)**（`_bmad-output/planning-artifacts/prd.md:1822`，公理依据 `or.md:233` 三.3.(3)「支持 Validation Feedback 闭环：自动捕获代码执行 STDERR，检索错误案例库辅助 LLM 生成修复版本；设定最大重试次数（默认 3 次），失败则标记不可行并记录至演进日志」）。
- Epic 4「战略工具箱」V1 P1 扩展（执行优先级 P1-7）：Epic 4 收官故事。4.1a~4.6 已交付五阶段执行引擎、Schema 验证装饰器（含基础重试）、Docker 沙箱、红蓝辩论与工具版本管理——当前失败路径在基础重试耗尽后**直接终结**（`ToolResultValidationError`/`ToolExecutionFailedError` 上抛），既无 STDERR 数据链（适配器捕获后丢弃），也无修复闭环与失败资产沉淀。
- **在 Epic 中的位置**：Epic 4 最后一个实现故事（4-1~4-6 全部 done）。前序故事在本 Story 处预置了大量契约（详见「已有资产复用清单」）：`EXCEPTION_399` 预留编码、`SandboxExecutionFailed.stderr` 预留字段、`ToolSchemaValidationFailed` reliable 通道"4.7 启用"注释、`ToolResultStatus.INVALID` 的"可重试"语义注释——本 Story 是这些预留债的集中清偿点。
- **依赖**：Story 4.1a（ToolExecutionEngine 五阶段 + 基础 3 次重试）✅ done + Story 4.3（ToolOutputValidator 装饰器 + `ToolSchemaValidationFailed` 事件 + violations 注入 prompt 自纠反馈）✅ done + Story 4.4（Docker 沙箱 + SandboxSecurityDecorator）✅ done + Story 4.6（工具版本管理，执行链透明路由）✅ done。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: STDERR 捕获数据链贯通

**Given** 沙箱内代码执行失败（非零退出码或 stderr 非空）
**When** `AioDockerSandboxAdapter.execute_code` 抛出 `ExecutionError`（EXCEPTION_313）
**Then** 异常 `context` 携带 `stderr`（截断 ≤2000 字符防 DoS）与 `exit_code`（向后兼容：构造器新增可选参数且**透传合并 `context`**——两个既有子类 `SandboxTimeoutError`/`SandboxResourceLimitExceededError` 的 `super().__init__(reason, context=...)` 调用零改动，含子类构造回归）
**And** `SandboxSecurityDecorator` 发布 `SandboxExecutionFailed` 事件时填充**已预留未用**的 `execution_id` 与 `stderr` 字段（`sandbox_events.py:96` 注释"用于 Story 4.7 Validation Feedback"的清偿）——`execution_id` 从**外层异常 context** 提取（except 块中的 `exc` 即外层 `ToolExecutionFailedError`，其 `context["execution_id"]` 由引擎 `tool_execution_engine.py:261-263` 构造时写入；`stderr` 从解包所得内层 `ExecutionError.context` 提取；`execute_code_with_protection` 直连路径无聚合根，`execution_id` 保持空串）
**And** 反馈闭环沿异常因果链提取 STDERR（`_unwrap_sandbox_error` 先例，`sandbox_security_decorator.py:100-120`——**同时遍历自定义 `cause` 属性与 `__cause__`**，`base_exceptions.py:62,72` 语义），stderr 进入修复 prompt 与演进日志。

**验证标准/Validation Criteria:**
- [ ] `ExecutionError` 构造器支持 `stderr`/`exit_code` 可选参数并合并写入 `context`，**且签名含 `context`/`cause` 透传**（子类 `SandboxTimeoutError`/`SandboxResourceLimitExceededError` 构造回归 + 既有 4.4 测试零破坏）
- [ ] `aiodocker_sandbox_adapter.py:511-518` 失败路径将 `stderr_str[:2000]` 与 `exit_code` 填入异常 context（当前仅 logger.debug 丢弃）
- [ ] `sandbox_security_decorator.py:132-137` 事件发布填充 `execution_id`（外层异常 context）+ `stderr`（内层 313 context；helper 签名需能拿到外层异常或其 context）
- [ ] Schema 校验失败路径（无 STDERR）以 `schema_violations` 提取错误签名（`ToolResultValidationError.context["schema_violations"]`，4.3 已携带）
- [ ] 单元测试覆盖：adapter 填充 / decorator 事件填充（含直连路径空 execution_id 分支）/ cause 链提取三段

### AC-2: Validation Feedback 闭环——增强重试与修复代码生成

**Given** 工具执行结果验证失败且基础重试已耗尽（内层 `ToolOutputValidator` 抛 `ToolResultValidationError` EXCEPTION_389），或执行失败（`ToolExecutionFailedError` EXCEPTION_382 且 `stage="EXECUTION"`，cause 链携带沙箱 STDERR——生产装配下 STDERR 的主浮现形态，见 Dev Notes「STDERR 实际浮现路径」）
**When** `ValidationFeedbackDecorator`（装饰链最外层）捕获触发异常
**Then** 触发增强反馈循环，每次增强尝试依次执行：提取 STDERR/签名 → 查询错误案例库 → LLM 生成**修复建议（suggested_fix 策略/代码草案）** → 经 `context.extensions["validation_feedback_hints"]` 注入（P0-D 模式先例）重执行内层链——**引擎 Code stage 是唯一代码作者**（prompt 指令「优先采纳 hints.suggested_fix，仅做必要适配」），避免 fix-gen 与引擎双作者导致失败不可归因
**And** 修复 prompt **必须携带跨尝试失败反馈**（Reflexion/Self-Debugging 共识——attempt k 的 prompt 含 attempt 1..k-1 的 stderr_excerpt/detail 与「以下方案已失败，禁止重复」指令；`FixAttempt` 数据结构已备），否则 attempt 2/3 与 attempt 1 独立同分布，确定性采样下重复生成相同失败修复
**And** 增强尝试总数 **3 次**（attempt 1..3，`RetryPolicy.max_attempts=3` 总尝试语义——非"3 次重试+1 次首试"）
**And** 防重试放大：增强期间内层重试全部封顶——引擎 `_retry` **与** `ToolOutputValidator` 的校验重试（`retry_policy_for_validation` 动态读 `engine._retry.max_attempts`，`tool_output_validator.py:105`——**前置条件**：TOV 构造未显式注入 `retry_policy`（`or` 短路才走动态读；生产装配 `composition_root.py:2360-2365` 成立，防放大测试须同时断言该构造形态））同为 `max_attempts=1`；实现上 `ValidationFeedbackDecorator` 保存引擎原 `RetryPolicy` 引用 → 整体替换为 `max_attempts=1` 且**保留原 `retryable_exceptions`**（frozen dataclass 禁属性赋值；恢复必须按引用、禁止重建默认对象——默认 `RetryPolicy` 含 `ExecutionError`(313) 会静默偏离生产白名单——生产装配已收窄排除 313）→ try/finally 按引用恢复
**And** 修复成功则返回 `ToolResult(status=SUCCESS, retry_count=增强尝试次数)`。

**验证标准/Validation Criteria:**
- [ ] 触发条件判定：仅 389（OUTPUT 校验耗尽，含 Schema 违规与 LLM 瞬时故障两子路径）与 382 且 `stage="EXECUTION"`（执行失败，含 316/317 经兜底包装的子类）进入闭环；382 且 `stage="SANDBOX_START"`（312/315 沙箱启动失败——基础设施故障非代码缺陷，修复不可归因）、`ToolExecutionTimeoutError`（385）、策略违规（207）、标记语法错误（201）、数据源族（410-413）、required schema 缺失（398——4.3 定义 4.7 消费）**不进入**闭环直接上抛
- [ ] 修复 prompt 组装：STDERR + 案例查询结果（命中 RECOVERED 案例时注入 fix_summary）+ schema violations（若有）+ **前次增强尝试失败反馈（attempt 1..k-1）** + 禁止重复失败方案指令；不含"原 Code 产物"依赖（引擎按 hints 重新生成，见 Then）
- [ ] hints payload 契约（Task 0 定稿 schema）：`{stderr_excerpt, schema_violations, case_summaries, prior_attempts, suggested_fix}`；`tool_execution_engine.py` `_think_stage`/`_code_stage` prompt 构建读取 `validation_feedback_hints` 扩展键（引擎 `__init__` 签名不变——4.4 AC-7.4 BDD 断言保护）
- [ ] 防放大：增强期间引擎与 validator 两层重试均封顶 1，finally 按引用恢复（含 retryable_exceptions 保持断言）
- [ ] 修复生成自身失败：fix-gen 调用包 `_call_with_retry(max_attempts=1)`，LLMAPIError/LLMResponseError 经重试语义耗尽**计为该次增强尝试失败**（`FixAttempt.detail="llm_generation_failed"`）；**fix-gen 调用点以 `except Exception` 收敛**（非白名单异常如响应构造缺陷同样计为该次 attempt 失败，detail 区分类型——防裸穿打破 INFEASIBLE 不抛契约）；增强尝试中内层浮出非触发类领域异常（385/207/410-413/398）时中止闭环直传（语义优先级高于闭环）。**中止路径观测面立法（R3-3）**：中止 = 零观测副作用（不写演进日志——AC-4 Given「闭环结束」不含中止且 final_status 无第三值；不回填案例；不发事件；已耗 attempt 遥测随无日志丢弃）；**连锁语义**：中止后同 trigger_error 重放**不命中幂等短路**（短路依赖已有终态日志）→ 重放全量重跑（LLM 配额放大为已知代价，完整中止遥测需 final_status 第三值 ABORTED——登记 deferred-work）；abort 场景 BDD 构造法 = attempt-k 的 LLM code mock 返回含裸 `$`（201 浮出）或注入 resolver（207）——385 同 RetryPolicy 下需单调钟竞速（首执行 <cap 触发 382、重执行 >cap 浮出 385）CI 必抖动，**385 仅用于直传场景构造**（引擎 `RetryPolicy(max_total_duration_sec≈0)`）
- [ ] 单元测试：触发判定矩阵（含 SANDBOX_START 排除行）/ hint 注入透传 / 防放大恢复 / 跨尝试反馈注入 / 修复生成失败处置 / 成功恢复路径

### AC-3: 不可行标记与领域事件

**Given** 3 次增强重试均失败
**When** 反馈循环耗尽
**Then** 标记任务不可行：返回 `ToolResult(status=INFEASIBLE)`（`ToolResultStatus` 新增枚举值，additive 向后兼容），`output` 携带失败摘要（error_signature/最终 STDERR 摘要/尝试次数）
**And** 发布 `ToolExecutionMarkedInfeasible` 领域事件（配置双登记 reliable——运行时仅 outbox 路径，见 AC-6 语义注记），写入演进日志 `final_status=MARKED_INFEASIBLE`
**And** 闭环内部以 `ValidationFeedbackRetryExhaustedError`（EXCEPTION_399，**4.1b/4.3 两度预留的编码**）作为耗尽信号，由装饰器捕获并转换为 INFEASIBLE 结果（对外不抛异常——ToolChain DAG 编排按 `status` 分支感知，避免中断后续节点；**DAG 策略交互注记（R2 发现，R6 业界对标勘误与定稿）**：INFEASIBLE 经结果路径计入 `failed_nodes`（`tool_chain_orchestrator.py:643-644`，`!= "success"` 判定）后，**FAIL_FAST 链仍会中断**——波次间检查 `:208-225`（`FAIL_FAST and failed_nodes` → raise）兜底，与业界主流一致（永久性失败 × 显式 fail-fast = 中断：K8s PodFailurePolicy FailJob / Temporal non-retryable / Step Functions 未捕获即 fail）；SKIP_DOWNSTREAM 沿 failed_nodes 自动兼容（下游 SKIPPED）、CONTINUE_ON_ERROR 落 COMPLETED_WITH_ERRORS——三策略语义均正确。真实 delta 为三件工程事（随本 Story 修复，见 Task 8 Subtask 8.6）：①**类型丢失**——`:637` node state 二值 `"FAILED"` 抹掉「不可行」与「故障」区分（Temporal「catch 后 re-wrap 丢失 non-retryable 元数据」同型反模式），修复 = `NodeRunStatus.state` 支持 `"INFEASIBLE"`；②**cause=None**——`:218-224` FAIL_FAST 异常构造无法恢复原始异常，修复 = 从 `ToolResult.output` 取 `error_signature`/尝试次数填充异常 context（K8s JobFailed condition 带 reason 同型，KEP-4443）；③**同波兄弟跑完**（旧异常路径会取消同波）——FAIL_FAST 策略下首个结果失败主动 cancel 同波剩余任务为**可选优化**（纯算力节约，deferred 登记；CONTINUE/SKIP 场景本就不该取消，禁做成无条件）
**And** 修复成功路径发布 `ToolExecutionRecovered` 领域事件（配置双登记 reliable——运行时仅 outbox 路径，见 AC-6 语义注记）。**两事件 execution_id 定稿 = 主 id**（`trigger_error.context["execution_id"]`——与演进日志幂等键同源；attempt 级引擎事件回链仅经 `fix_attempts.attempt_execution_id`）。**389 子路径 id 同源修复（R2 发现悬空，R7 定稿方案）**：389 的 execution_id 原为 TOV 内 `extract_schema_execution_id(context) or uuid4()` 铸造（`tool_output_validator.py:111`）——生产链无人设置该键时与 ToolExecution 聚合行无对应（「两套 id 空间」，4.1b DataSourceFetchFailed 断链同构）。**修复设计（决策 #16，Task 6 循环 D 实施）**：链入口 `ToolExecutionService.execute`（`tool_execution_service.py:64`，装饰链之外）注入 `context.with_extension("schema_execution_id", uuid.uuid4())`（1 行，沿用 TOV 已读的键名——`schema_event_helpers.py:141-146` 第一优先级）+ 引擎 `:137-138` 聚合 id 改为优先读该键（3 行，无则新铸）+ TOV 零改动自动命中——**聚合 id = 382/389 context id = 演进日志幂等键 = 两事件 id 全链同源**；引擎 `_persist_execution` 用 save（upsert 语义），校验重试多次 execute 同 id 重入无乐观锁冲突（聚合行覆盖为最新次，与 execution_id 幂等语义一致）

**验证标准/Validation Criteria:**
- [ ] `ToolResultStatus.INFEASIBLE = "infeasible"` 新增（`(str, Enum)` 加值 additive）；既有语义注释保持（INVALID 语义不变——`value_objects/tool_execution.py:247-249` 注释契约保持）；**既有 4 值边界断言联动**：`tests/unit/domain/value_objects/test_tool_execution_values.py:114-120` 的 `len(statuses)==4`/全值 set 断言与 `tool_execution.py:30` 枚举 docstring「4 值边界」须同步更新为 5 值（Task 1 循环 C 显式包含）
- [ ] `ValidationFeedbackRetryExhaustedError`：code=`EXCEPTION_399`、继承 `BusinessException`、构造器携带 `execution_id`/`tool_id`/`enhanced_retry_count`/`error_signature` context（execution_id 取自 trigger_error.context——见 AC-1/AC-6 提取机制）
- [ ] `ToolExecutionState` 6 状态机**不动**（FAILED 终态语义不变，增强重试按"终态反向迁移禁止（重试创建新 attempt）"既有注释语义创建新执行）
- [ ] 两事件字段与 `DomainEvent` 基类 12 核心字段（`base.py:20-35` `_CORE_FIELD_NAMES`）对齐 + 各自自有字段（MarkedInfeasible 8 个 / Recovered 7 个）+ tenant_id baseline（4-5 R1-F01 教训：metadata 字段一律 `str()` 化防 json 序列化失败）
- [ ] INFEASIBLE 结果不抛异常、不发布 ToolExecuted 成功事件

### AC-4: 演进日志与持久化可靠性

**Given** 反馈闭环结束（无论恢复或标记不可行）
**When** 写入演进日志
**Then** `EvolutionLogEntry` 聚合根落库（PG migration 017），记录 execution_id / tool_id / **trigger_code（389|382——失败模式第一维分类，AIOps failure history 基线字段）** / error_signature / enhanced_retry_count / fix_attempts 摘要（含每次 attempt_execution_id 回链） / **duration_sec（闭环时长，MTTR 等价物）** / final_status（RECOVERED | MARKED_INFEASIBLE）
**And** 失败历史可追溯：按 `tool_id` 查询该工具全部反馈历史（`EvolutionLogQuery` Query Object，多字段+分页），按 `execution_id` 精确定位单次记录
**And** 清偿 defer 债：**outbox 后台路径独立 session 修复**（`tool_execution_engine.py:282-284` 与 `data_source_resolver.py:352` 注释显式 defer 本 Story）——设计采用 **fallback 独立 session**：`PostgreSQLOutboxRepository.save` 优先 `get_session()`（HTTP 路径复用请求 session，保持事务性 outbox 原子性——业务状态与事件发布同事务 commit/rollback），捕获 `RuntimeError`（后台/CLI 路径无请求 session——现状事件静默丢失的根因）时经注入的 `session_factory` 走 `session_context` 独立写入（`outbox_processor.py:148-150` 先例同款）。

**验证标准/Validation Criteria:**
- [ ] `EvolutionLogEntry` 不变量：`enhanced_retry_count ∈ [1,3]`、`final_status` 为枚举、`trigger_code ∈ {"EXCEPTION_389","EXCEPTION_382"}`、UUID 有效、timezone-aware
- [ ] 按 execution_id 幂等 upsert（同 execution 重复写入不产生重复行）
- [ ] `EvolutionLogQuery`（frozen dataclass：tool_id/tenant_id/execution_id 可选 + limit/offset）走 Query Object 决策规则（多字段组合+分页）
- [ ] outbox 修复回归断言：**后台/CLI 路径**（无请求 session——`get_session()` 抛 RuntimeError 场景）reliable 事件经 fallback 独立 session 成功落库（现状该场景事件 100% 静默丢失）；**正常 HTTP 路径行为零变化**（仍走请求 session 同事务，事务性原子性保持）
- [ ] 后台路径中「业务 session 异常回滚连带丢失已 flush 事件」形态（session_context rollback 连带）为**遗留债**：完整修复需后台路径会话策略重构，超出本 Story 范围——defer 注释清偿时显式登记 `deferred-work.md`
- [ ] 集成测试覆盖双查询面（list_by_tool / get_by_execution）

### AC-5: 错误案例库（查询辅助 + 案例回填 + 幂等）

**Given** 反馈循环执行中
**When** 每次增强尝试前
**Then** 按 `(tenant_id, tool_id, error_signature)` **精确查询**错误案例库（V1 语义诚实化：自然键 UNIQUE 下精确匹配至多命中 1 行，即"精确查表"而非多案例检索——`get_by_natural_key` 即查询面），命中且 `outcome=RECOVERED` 且 `fix_summary` 非空时注入修复 prompt（or.md error_db.search 蓝图的 V1 落地形态）；命中 `MARKED_INFEASIBLE` 案例时注入**负样本提示**（"此签名历史 N 次修复均失败"——ExpeL 失败经验模式，infeasible_count 支撑）
**And** 闭环结束时回填案例：恢复成功回填 `recovered_count += 1` 并**覆写 fix_summary**（仅 RECOVERED 路径覆写——保留最佳已知修复，防不可行写回冲掉修复配方）；标记不可行回填 `infeasible_count += 1`（fix_summary 不动）
**And** 案例写入幂等：同 `(tenant_id, tool_id, error_signature)` 重复记录 `occurrence_count += 1`（= recovered_count + infeasible_count 合计）并刷新 `last_seen_at`，不产生重复行。

**验证标准/Validation Criteria:**
- [ ] `ErrorCase` 聚合根 + `ErrorCaseRepositoryPort`（get_by_natural_key 精确查询 / record_case upsert——单字段检索与命令型操作直接参数，CLAUDE.md 端口参数决策规则；**不设 search_by_signature**——V1 精确匹配下与 get_by_natural_key 语义重复，多案例加权检索登记 deferred-work）
- [ ] `ErrorSignatureExtractor` 领域服务（纯函数）：STDERR 归一化（剥离路径/行号/时间戳/内存地址 + **数值→`<N>`、引号串→`<S>` 模板化**——Sentry message templating 对标，防 `KeyError: 'x'` 类消息内插值分裂签名）→ **完整 sha256 hexdigest（64 hex）**；签名计算取**尾部锚定摘录 `stderr[-2000:]`**（traceback 根因行在末尾，头部截断会切掉根因致错误合并；事件/prompt 展示仍可头部截断）；schema violations 路径归一化签名（排序去序）——同根因不同表层输出收敛为同一签名（幂等前提）
- [ ] V1 查询语义：精确签名匹配（确定性可测）；向量相似检索（L3 Qdrant）与多案例加权检索（签名前缀粗化分组 + occurrence_count DESC——依赖完整摘要保留的前缀派生能力）为非目标并登记 deferred-work
- [ ] 并发 upsert 冲突容错（4-6 CR1-4 教训：UNIQUE 冲突后 PendingRollback 需 `begin_nested()` SAVEPOINT 包裹重读）
- [ ] 案例查询无命中时闭环仍可运行（纯 LLM 修复，`fix_strategy=PURE_LLM`）；命中不可行案例时 `fix_strategy=NEGATIVE_CASE_GUIDED`（决策 #15 三分支——二值会把负样本命中虚标为 PURE_LLM，演进日志失败史不可区分）

### AC-6: 幂等性与事件通道补全

**Given** 同一触发异常重复进入反馈闭环（**可达场景界定**：`recover()` 被以同一 `trigger_error`（同 execution_id）重复调用——事件消费侧重放/上游补偿重试形态；注意装饰器层重复调用会因引擎每次 `execute()` 新铸 execution_id（`tool_execution_engine.py:137-138`）而不命中幂等键，此为架构边界非缺陷）
**When** 闭环各副作用执行
**Then** **副作用去重语义**：演进日志按 execution_id 幂等 upsert（AC-4）、案例库按自然键幂等计数（AC-5）、`ToolExecutionMarkedInfeasible`/`ToolExecutionRecovered` 事件不重复发布（同 execution 终态判定短路）；短路路径返回合成结论——INFEASIBLE 语义完整（output 即失败摘要，日志行可支撑）；RECOVERED 重放返回合成 SUCCESS 摘要（**边界注记**：原成功 ToolResult 的完整 output/evidence_package 不在演进日志中，重放结果不含证据包——下游需证据时应重新执行而非依赖重放）
**And** 清偿 4.3 通道预留债：`ToolSchemaValidationFailed` 补 reliable 通道（`event_channels.yaml`（顶层键 `event_channels:`）与 `ChannelRouter.DEFAULT_MAPPINGS` **两处同步**，YAML > DEFAULT_MAPPINGS 优先级注释 `channel_router.py:50-53`）。

**验证标准/Validation Criteria:**
- [ ] 幂等集成测试：同 trigger_error 重复调用 `recover()` → 日志 1 行 / 事件 1 次 / 返回合成结论；案例以已记录终态调 `record_case`（分类计数与 occurrence **同步递增**——「该失败的观测计数」语义，不变量 occurrence=recovered+infeasible 自动守恒；**禁止只加 occurrence 不加分类计数**——破坏合计不变量、构造期 242 崩溃，R3-2 定谳）；短路路径零副作用限定 = 不新建行 / 不写日志 / 不发事件 / 不覆写 fix_summary；RECOVERED 重放同理递增 recovered_count
- [ ] `ToolSchemaValidationFailed` 通道从 realtime-only 升级为 reliable（两处配置 + 契约测试逐字段断言）
- [ ] 新事件双通道两处登记（`configs/event_channels.yaml`——注意实际目录为 `configs/` 非 `config/`——+ `channel_router.py` DEFAULT_MAPPINGS）。**「双通道」语义注记**：指配置面双登记（`redis_channel` + `rabbitmq_routing_key` 两键、`delivery_mode: reliable`，与既有 ToolExecuted/Sandbox 三事件同形态）；运行时 `DualChannelEventBus.publish` 对 reliable 事件**仅走 outbox/RabbitMQ 路径不发布 Redis**（`dual_channel_event_bus.py:58-65`，单测 :77 锁死）——契约测试断言对象为两处配置逐字段一致，非双通道投递行为
- [ ] 事件通道映射契约测试：YAML 与 DEFAULT_MAPPINGS 逐字段一致（4-6 先例 `test_event_channel_mapping_tool_version.py`）

### AC-7: 装配升级与性能基准

**Given** 全部组件实现完成
**When** 组合根装配与性能基准执行
**Then** `tool_execution_service` 升级 **v1.3.0 → v1.4.0**，装饰链层叠为 `ValidationFeedbackDecorator > SandboxSecurityDecorator > ToolOutputValidator > Engine`（4.7 最外层），`compatibility=("v1.3.0", "v1.2.0")`，tags += `("feedback",)`
**And** 性能达标（epics 硬指标可测化口径，Task 0 与业务方确认留痕）：闭环自身开销（错误签名提取 + 案例查询 + 演进日志写入，**不含** LLM 修复生成与沙箱执行时长——二者受 `LLMConfig.timeout`/沙箱 timeout 支配）单次 **P95 < 5s**（`statistics.quantiles(n=20)[18]` 分位 + 分级断言：达标 assert / 环境不达标 skip 留测量证据——4-6 `test_tool_version_integration.py:398-415` 先例；计时手法 = 端口级计时代理包裹仓储 + LLM/Sandbox AsyncMock `await asyncio.sleep(0)` 真实挂起点）；**闭环机制有效性**（mock LLM 可编程修复序列前提——指标语义注记：mock 化下度量的是编排机制正确性而非真实修复能力，真实修复能力观察基准不进 CI 门禁并登记 deferred-work）：增强重试恢复机制成功率 **≥80%**（20 次可修复故障注入 ≥16 恢复，主断言为内容性断言：修复 prompt 含 stderr/案例 fix_summary/历史反馈、hints 注入透传）；不可行标记机制准确率 **20 次不可修复故障全部标记 + 可修复故障 0 误标**（样本规模下等效 100%；epics 字面 ≥95% 为下限口径，20 样本粒度无法区分 95%/100%）。

**验证标准/Validation Criteria:**
- [ ] 3 个新端口注册（`error_case_repository` / `evolution_log_repository` / `validation_feedback_service`）+ `tool_execution_service` 升级，PortSpec 10 字段齐备，lambda 工厂注入（`validation_feedback_service` 注入清单以端口 SSOT 表行为准——含 engine 引用、不注入 RetryPolicy）
- [ ] 端口契约测试 11 维度 ×3（`test_port_contract_tool.py` 样板：注册/名称/版本/接口类型/生命周期/owner/module/tags/impl callable/方法存在/Protocol runtime_checkable）
- [ ] 性能基准位于 `tests/integration/test_validation_feedback_integration.py`（epics 硬路径）：P95 开销 / 机制成功率 / 机制准确率三组
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
  - `ToolExecutionMarkedInfeasible`：`execution_id`/`tool_id`/`tenant_id`/`tool_version`/`error_signature`/`enhanced_retry_count`/`failure_summary`/`occurred_at`（自有字段 8 个）；`aggregate_type="ToolExecution"`；配置双登记 reliable（运行时仅 outbox 路径，见 AC-6 语义注记）
  - `ToolExecutionRecovered`：`execution_id`/`tool_id`/`tenant_id`/`tool_version`/`error_signature`/`enhanced_retry_count`/`occurred_at`（自有字段 7 个）；`aggregate_type="ToolExecution"`；配置双登记 reliable；两事件均与 `DomainEvent` 基类 12 核心字段对齐
- [ ] `ToolSchemaValidationFailed` 由 realtime-only 升级 reliable（4.3 留项"reliable 4.7 启用"清偿，事件类本身零改动）

#### 数据模型 (Data Models)
- [ ] 模型定义位于 `src/domain/entities/` 或对应层
- [ ] `ErrorCase` 聚合根（`src/domain/entities/error_case.py`）：`case_id`/`tenant_id`/`tool_id`/`error_signature`(**64 hex 完整 sha256 hexdigest**——与签名提取器/列宽三者同一口径)/`error_category`（**赋值规则定稿（R3-9）**：389-Schema 路径=「SCHEMA_VIOLATION」/389-LLM 瞬时=「LLM_TRANSIENT」/382-EXECUTION=沙箱 error_code（cause 链首个 ExecutionError 族 code，如 EXCEPTION_313/316/317）——取自 trigger_code + cause 链推导）/`stderr_excerpt`(≤2000)/`fix_summary`(≤2000，**仅 RECOVERED 路径覆写**；**覆写内容来源定稿（R3-9）**：成功 attempt 的 suggested_fix（fix-gen 产出原文截断 ≤2000）+ 该次错误摘要一句——由服务层派生；构造器默认空串与 migration DEFAULT '' 对齐)/`outcome`(最近一次：RECOVERED|MARKED_INFEASIBLE)/`recovered_count`(≥0)/`infeasible_count`(≥0)/`occurrence_count`(=recovered+infeasible 合计，≥1)/`last_seen_at`/`created_at`；自然键 `(tenant_id, tool_id, error_signature)`——计数拆分防不可行写回冲掉修复配方；**并发 outcome 次序（R3-11）**：同签名 RECOVERED×INFEASIBLE 并发回填时 outcome 终值取决于提交次序（有界竞态，分类计数守恒不受影响）——登记为已知行为
- [ ] `EvolutionLogEntry` 聚合根（`src/domain/entities/evolution_log_entry.py`）：`log_id`/`tenant_id`/`tool_id`/`execution_id`/`tool_version`/`trigger_code`(EXCEPTION_389|EXCEPTION_382)/`error_signature`/`enhanced_retry_count`(1-3)/`fix_attempts: tuple[FixAttempt, ...]`/`duration_sec`/`final_status`(RECOVERED|MARKED_INFEASIBLE)/`created_at`
- [ ] `FixAttempt` 值对象（`src/domain/value_objects/validation_feedback.py`）：`attempt_no`(1-based)/`attempt_execution_id: str = ""`（该次重执行引擎新铸 id——回链增强期间事件；**空串=未发生重执行的合法形态**（如 fix-gen 失败计 attempt 的 `llm_generation_failed` 形态），Task 1 不变量禁立「UUID 有效」于该字段——R2 组合发现）/`error_signature`/`fix_strategy`(CASE_GUIDED|NEGATIVE_CASE_GUIDED|PURE_LLM 三分——决策 #15)/`stderr_excerpt: str = ""`/`succeeded`/`detail`
- [ ] `ToolResultStatus.INFEASIBLE` 新增枚举值（`(str, Enum)` 加值 additive；`INVALID`"可重试"语义契约不变；既有 4 值边界断言与 docstring 同步 5 值——AC-3 VC）
- [ ] `ErrorSignatureExtractor` 领域服务（`src/domain/services/error_signature_extractor.py`）：纯函数，STDERR 归一化签名（剥路径/行号/时间戳/内存地址 + 数值→`<N>`/引号串→`<S>` 模板化 + 尾部锚定 `stderr[-2000:]` 参与哈希）+ violations 归一化签名（排序去序）——均输出 64 hex
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
| `validation_feedback_service` | application | `ValidationFeedbackServicePort`（`src/application/ports/validation_feedback_service.py`，方法 `recover(...)`） | lambda 工厂注入 llm_client + error_case_repository + evolution_log_repository + event_publisher + **engine 引用**（`resolver.resolve("tool_execution_engine")`——防放大封顶/恢复 `engine._retry` **原引用**用，决策 #8/AC-2；wrapped 链首是 SSD 无 `_retry`，禁经装饰链推导）；fix-gen 重试封顶 `max_attempts=1` 由服务内自建，**不注入 RetryPolicy**（注入新建 RetryPolicy 会诱导「按值恢复」——恢复必须按 engine 原引用，陷阱 8） | v1.0.0 | SCOPED | tool-team | (tool, feedback, service) |
| `tool_execution_service` | application | `ToolExecutionServicePort` | **升级 v1.3.0 → v1.4.0**：装饰链最外层加 `ValidationFeedbackDecorator`；`compatibility=("v1.3.0", "v1.2.0")`；tags += ("feedback",) | v1.4.0 | SCOPED | tool-team | (tool, execution, service, decorated, versioned, feedback) |

**端口方法契约：**
- `ErrorCaseRepositoryPort`：`get_by_natural_key(tenant_id, tool_id, error_signature) -> ErrorCase | None`（V1 精确查询面——自然键 UNIQUE 下精确匹配即全部语义，多案例加权检索登记 deferred-work）；`record_case(case: ErrorCase) -> ErrorCase`（自然键 upsert 幂等计数 + outcome 分类计数）
- `EvolutionLogRepositoryPort`：`save(entry: EvolutionLogEntry) -> None`（execution_id upsert 幂等）；`list_by_query(query: EvolutionLogQuery) -> tuple[EvolutionLogEntry, ...]`；`get_by_execution(execution_id, tenant_id) -> EvolutionLogEntry | None`
- `ValidationFeedbackServicePort`：`async recover(tool_id, tool, tool_call, context, trigger_error) -> ToolResult`（编排完整闭环：签名提取→案例查询→LLM 修复建议生成→增强重试→演进日志→不可行标记/恢复事件；execution_id 幂等键取自 `trigger_error.context["execution_id"]`）

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
| EXCEPTION_399 | `ValidationFeedbackRetryExhaustedError` | `BusinessException`（EXCEPTION_2XX 业务规则基类——注意 103 是 StorageError，勿混标） | **422** | 3 次增强重试均失败，任务被判定不可行（内部耗尽信号，装饰器捕获转 `ToolResult(INFEASIBLE)`；422 与 396 出参校验失败语义对齐——"语义上不可处理"而非 502"可重试下游故障"，不可行标记恰是"重试无意义"的终态结论） |

#### 修改的既有异常（Task 0 契约——遵守本 Story 自设规则"新增/修改的领域异常必须在 Task 0 完成设计"）

- `ExecutionError`（EXCEPTION_313，`sandbox_exceptions.py:33-37` 现无自定义构造器）构造器增强：`__init__(self, message=None, *, stderr=None, exit_code=None, cause=None, context=None)`——`context` 参数**透传合并**（`merged = {**(context or {}), **new_fields}` 后传 `super().__init__(message, cause=cause, context=merged)`）。**兼容性硬约束**：两个既有子类 `SandboxTimeoutError`/`SandboxResourceLimitExceededError` 的 `super().__init__(reason, context={...})` 调用必须零改动通过（Task 3 测试含子类构造回归）——不透传 `context` 会立即使子类 TypeError 并炸 `test_sandbox_exceptions.py:168-196`

- [ ] **不扩域 400-409（方案 A 触发条件未满足）**：4.3 预测的 `ValidationFeedbackFallbackFailedError`/`HumanReviewTimeoutError`/`CanaryConflictError` 均属降级/人工审核/灰度联动扩展（非本 epic 范围，见非目标），400-409 保持未分配——Story 文件与 `sisys-uni-exception-design.md` 中"扩域至 400-409（方案 A）"的预留注释更新为"按需扩域，触发条件：反馈闭环降级链路立项"
- [ ] 归属模块：新建 `src/domain/exceptions/validation_feedback_exceptions.py`（4.5 debate 新文件先例）；`_CLASS_TO_SUBDOMAIN` 子域映射注册为 `"toolchain"`（399 物理归属 toolchain 段，语义为反馈闭环——沿用 4.2/4.3 子域嵌套声明惯例）
- [ ] 构造器参数设计：`execution_id`/`tool_id`/`enhanced_retry_count`/`error_signature` 经 `context` 字典暴露
- [ ] 消息安全性审查：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] **5 处登记 Checklist**（4-6 教训全量执行）：
  1. **定义文件**：`validation_feedback_exceptions.py`（类 + `__all__`）
  2. **`_code_ranges.py`**：`CODE_RANGES` 注释行 EXCEPTION_399 由"预留"改"已分配" + `_CLASS_TO_SUBDOMAIN` 注册
  3. **`exceptions/__init__.py`**：导入 + `__all__`（按子域分组注释节）
  4. **`EXCEPTION_HTTP_MAP`**：`exception_handlers.py` 精确注册 399→422（注释格式与 4.6 先例一致，注释行内 code 与实际 code 严格对齐——4.1a 偏移 bug 先例）
  5. **`sisys-uni-exception-design.md §3.3.2` 两表同步**（注意：该文档存在两个同号 §3.3.2 小节（`:649` 编码分配表与 `:786` 子域范围表），**都必须更新**——4-6 踩坑记录；`:786` 子域范围表当前无独立 toolchain 行，需补行或确认 tool 行覆盖口径）+ 同文档 `:805`/`:807` 两行既有「399 预留/预占」表述连带更新 + `tests/unit/interfaces/api/test_exception_handlers.py` 期望集合同步（4-5 教训）
- [ ] 编码碰撞自查：`grep -rn "EXCEPTION_399" src/` 仅新定义文件与登记处命中
- [ ] 测试覆盖：构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过（`tests/unit/domain/exceptions/` 全目录既有测试回归（25 个既有文件，不硬编码计数）+ 新增 `test_validation_feedback_exceptions.py`——断言继承关系而非父类具体码号）
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
- **Edge Cases 必须包含异常路径** — 覆盖触发矩阵八行全覆盖（389 入两子路径 / 382-EXECUTION 入 / 382-SANDBOX_START 出直传 / 385 出 / 207 出 / 201 出 / 410-413 出 / 398 出）+ 399 耗尽标记场景、案例库空命中纯 LLM 修复、**CASE_GUIDED 正样本命中**（RECOVERED 案例注入 fix_summary）、负样本命中（MARKED_INFEASIBLE 案例）提示注入、fix-gen 失败（detail=llm_generation_failed）、abort 中止（attempt-k 浮出 201/207 直传 + 零观测副作用断言）、幂等重复触发（同 trigger_error 重复 recover()，双终态各一）、RECOVERED 重放合成摘要；防放大/跨尝试反馈/hints 透传为单测口径（`test_validation_feedback_service.py`/`test_tool_execution_engine_hints.py`），BDD 不重复覆盖
- **Edge Case 构造注入点清单（防走错路径）**：385 超时仅可经引擎 `RetryPolicy(max_total_duration_sec≈0)` 构造（五阶段全部完成后判定 `tool_execution_engine.py:198-204`；靠 sandbox 慢会得 316→382 **进闭环**走错路径；abort 场景**禁用 385**——同 RetryPolicy 下需单调钟竞速 CI 必抖动，用 201/207 构造，见 AC-2 VC 中止路径立法）；207/413 需**同时**注入 resolver（`set_data_source_resolver`）且缺 tool_metadata（无 resolver 时含标记代码先触发 101 而非 207）；201 用 LLM code mock 返回含裸 `$` 代码最易构造；389-LLM 瞬时子路径 fixture 必须显式**零退避**（RetryPolicy initial/max_delay_sec=0——默认 1s/2s 指数退避下 3+3 次重试 CI 时长爆炸）
- **服务级 BDD 模式（4-6 形态）**：`scenarios()` 批量注册 + `context: dict[str, Any]` fixture + 模块级 `event_loop` fixture + `_run(coro)` helper + `_make_*` 工厂 + `_capture_error`；真实服务链（InMemory 仓储 + 真实 ErrorSignatureExtractor + 真实引擎 + 真实装饰链），仅 LLM/Sandbox 适配器 AsyncMock（可编程失败/修复序列）；fixture 需暴露上述注入点（引擎 retry_policy 参数 / resolver 注入）；**场景级独立重建服务链**（每场景重建仓储/引擎/装饰链——模块级共享会跨场景泄漏 ErrorCase 行，负样本/重放场景依赖场景内先跑一次耗尽再跑第二次）；**事件次数断言前 drain 后台任务**（`asyncio.create_task` fire-and-forget 位于 recover() 尾部，无 drain 则断言竞态随机红——`gather(*pending)` 或 sleep(0) 循环至无 pending task；4-6 `_RecordingEventPublisher` 先例可捕获）
- Fake LLM 分派纪律（4-5 R1-F06 教训）：Mock LLM 按 prompt 中的**结构化角色标记**（如 system_prompt 或修复 prompt 固定前缀）分派响应，禁止按易混淆子串分派——引擎 Think/Code/Validate 与修复生成走同一 mock 时必须按 prompt 结构分派而非纯调用序号

**模块依赖窗口提交策略（4-6 :1128 先例，强制）：**
- Task 0.9 红窗口确认后**暂缓入库**，随对应模块落地**批提交**：feature（无 import，Task 0 即可入库）→ 事件契约/通道映射测试随 Task 2 → 双仓储契约 + PG 仓储集成（不含 outbox fallback 用例——R3-1）随 Task 4 → 验收 .py + 服务契约 + 装饰器测试 + outbox fallback 用例（追加至 repositories 集成文件）随 Task 6 → Task 7/8/9 各自红绿同批入库（Task 8 架构测试 import 服务/装饰器/仓储实现，按 8.2-8.5 断言对象**不得早于 Task 6**）
- **对既有文件的"先红"修改**（`test_exception_handlers.py` 期望集合、`test_port_contract_tool_execution_service.py` 版本期望 + EXPECTED_TAGS）：红不单独落库（本地观察），与对应实现同 commit 入库——防止单独提交打挂现有绿套件与 mypy pre-commit hook

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态：acceptance .py 与契约测试 collection ERROR / ImportError，属预期中间态）
- [ ] P95 口径重定义（epics「单次重试延迟」→「闭环自身开销」，决策 #11）与业务方确认留痕（Subtask 0.11）
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
| **TDD 单元测试** | ToolResultStatus.INFEASIBLE | additive 枚举/INVALID 语义不回归/5 值全集 | `tests/unit/domain/value_objects/test_tool_result_status.py` | Task 1 |
| **TDD 单元测试** | ToolResultStatus 4→5 值边界（**修改既有**） | 既有边界断言更新（len==4→5）+ docstring 同步 | `tests/unit/domain/value_objects/test_tool_execution_values.py`（修改） | Task 1 |
| **TDD 单元测试** | 领域事件 ×2 | 字段/序列化 str 化/aggregate 关联 | `tests/unit/domain/events/test_validation_feedback_events.py` | Task 2 |
| **TDD 领域异常测试** | 399 异常 | 构造/context/继承链/编码 | `tests/unit/domain/exceptions/test_validation_feedback_exceptions.py` | Task 2 |
| **TDD 单元测试** | ExecutionError 增强 | stderr/exit_code 可选参数向后兼容 | `tests/unit/domain/exceptions/test_sandbox_exceptions.py`（扩展） | Task 3 |
| **TDD 单元测试** | adapter/装饰器 STDERR 链 | 异常 context 填充/事件字段填充/cause 链提取 | `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_adapter_stderr.py` + `tests/unit/application/services/test_sandbox_security_decorator_events.py` | Task 3 |
| **TDD 单元测试** | InMemory 双仓储 | upsert 幂等/分类计数/get_by_natural_key 语义 | `tests/unit/infrastructure/storage/inmemory/test_error_case_repository.py`、`test_evolution_log_repository.py` | Task 4 |
| **TDD 单元测试** | ValidationFeedbackService | 触发判定矩阵/闭环编排/防放大/案例回填 | `tests/unit/application/services/test_validation_feedback_service.py` | Task 5 |
| **TDD 单元测试** | ValidationFeedbackDecorator | 装饰链集成/hints 注入/INFEASIBLE 转换/事件发布 | `tests/unit/application/services/test_validation_feedback_decorator.py` | Task 6 |
| **TDD 单元测试** | 引擎 hints prompt | `validation_feedback_hints` 扩展键读取 | `tests/unit/application/services/test_tool_execution_engine_hints.py` | Task 6 |
| **TDD 契约测试** | 3 新端口 + 1 升级 | 11 维度（注册/名称/版本/接口/生命周期/owner/module/tags/impl callable/方法/Protocol） | `tests/contracts/test_port_contract_error_case_repository.py`、`test_port_contract_evolution_log_repository.py`、`test_port_contract_validation_feedback_service.py` | Task 4/6 |
| **TDD 契约测试** | 事件契约 + 通道映射 | 事件字段/双通道两处一致 | `tests/contracts/test_event_contract_validation_feedback_events.py`、`test_event_channel_mapping_validation_feedback.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_validation_feedback_loop.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_validation_feedback_loop.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | 同 feature/.py | Task 9 |
| **SDD 架构验证** | 反馈闭环架构测试（epics 硬路径） | 重试增强/失败标记/幂等性/演进日志四项 | `tests/unit/architecture/test_validation_feedback.py` | Task 8 |
| **集成测试** | PG 双仓储 + outbox fallback + migration 017 | repo_session 事务 rollback + xdist_group（4-6 样板） | `tests/integration/test_validation_feedback_repositories.py` | Task 4 |
| **集成测试** | 全链闭环 + 幂等 + outbox 回归 + 性能基准（epics 硬路径） | 真实 PG + 机制成功率/机制准确率/P95 | `tests/integration/test_validation_feedback_integration.py` | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**（epics 硬指标：本 Story 核心交付在应用层闭环编排）
- [ ] **领域层覆盖率 ≥90%**（关键业务逻辑，不变量验证）
- [ ] **基础设施层覆盖率 ≥75%**（外部依赖适配，连接测试）
- [ ] **集成测试覆盖率 ≥75%**（epics 硬指标）
- [ ] **关键路径覆盖率 100%**：闭环触发判定矩阵全八行（389 入两子路径/382 且 EXECUTION 入/382 且 SANDBOX_START 出/385 出/207 出/201 出/410-413 出/398 出）、增强重试 attempt 1→3、耗尽标记、恢复成功、案例回填（recovered/infeasible 分类）、幂等 upsert 全分支

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
| **外部服务隔离** | PG 集成测试走 repo_session 事务 rollback + xdist_group 串行 + PG 探活 skip（4-6 `test_tool_version_integration` 样板）；Redis 场景级独立客户端 | 真实数据被污染 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；BDD 步骤用 `event_loop.run_until_complete()` | 锁失效或 context 丢失 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **BDD async 配合** | BDD 步骤函数不使用 `@pytest.mark.asyncio` | context 数据丢失 |
| **Fake LLM 分派** | Mock LLM 按结构化角色标记分派响应，禁止易混淆子串分派（4-5 R1-F06） | 误路由致断言循环论证 |
| **并发 upsert** | 集成测试覆盖 UNIQUE 冲突 + PendingRollback 容错（begin_nested SAVEPOINT，4-6 CR1-4） | 并发记录案例崩溃 |
| **时间敏感断言** | P95 阈值断言与计时口径成对出现：`statistics.quantiles(n=20)[18]` 分位 + 分级断言（达标 assert / 环境不达标 skip 留测量证据，4-6 AC-7 先例）；mock 替身注入真实挂起点（`await asyncio.sleep(0)`，4-5 R2-F02 原语义） | CI 随机红 |

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
| AC-1 | STDERR 捕获数据链贯通（adapter→异常→事件） | Task 3 | ExecutionError 增强 + adapter 填充 + 装饰器事件填充 + cause 链提取 | `test_aiodocker_adapter_stderr.py` + `test_sandbox_exceptions.py`（扩展）+ `test_sandbox_security_decorator_events.py` |
| AC-1 | 签名提取（violations 路径） | Task 1 | ErrorSignatureExtractor | `test_error_signature_extractor.py` |
| AC-2 | 触发判定（矩阵八行） | Task 5 | recover 触发判定矩阵 | `test_validation_feedback_service.py` |
| AC-2 | 案例查询注入修复 prompt | Task 5 | 修复 prompt 组装（CASE_GUIDED/PURE_LLM/负样本） | 同上 |
| AC-2 | hints 注入 + 引擎 prompt 读取 | Task 6 | `validation_feedback_hints` 扩展键 | `test_tool_execution_engine_hints.py` |
| AC-2 | 防放大（两层封顶 + 按引用恢复） | Task 5 | 增强循环内临时降级 | 同上 |
| AC-3 | INFEASIBLE 标记 + ToolResult 契约 | Task 1 / Task 5 / Task 6 | 枚举新增（含 4→5 值边界联动）/ 耗尽转换 | `test_tool_result_status.py` + `test_tool_execution_values.py`（修改）+ `test_validation_feedback_decorator.py` |
| AC-3 | 399 异常全链路登记 + execution_id 全链同源（决策 #16） | Task 2 / Task 6 | 5 处登记 Checklist / 链入口注入 + 引擎复用（循环 D） | `test_validation_feedback_exceptions.py` + `test_validation_feedback_decorator.py`（id 同源四断言并入装饰器测试批） |
| AC-3 | 两领域事件 + 配置双登记 reliable | Task 2 | 事件定义 + 两处配置 | `test_validation_feedback_events.py` + 契约 |
| AC-4 | 演进日志实体 + 双查询面 | Task 1 / Task 4 | 实体 + EvolutionLogQuery + 仓储 | `test_evolution_log_entry.py` + `test_validation_feedback_repositories.py`（集成） |
| AC-4 | outbox 后台路径 fallback 修复 | Task 6 | outbox_repository fallback 独立 session | `test_validation_feedback_repositories.py` + `test_validation_feedback_integration.py` |
| AC-5 | 案例库实体 + 端口 + 存储 | Task 1 / Task 4 | ErrorCase + 仓储双实现 + migration 017 | `test_error_case.py` + `test_validation_feedback_repositories.py`（集成） |
| AC-5 | 幂等 upsert + 分类计数 | Task 4 | 自然键 upsert + SAVEPOINT 容错 | 同上 |
| AC-6 | 闭环幂等（日志/案例/事件） | Task 5 | 同 trigger_error 终态判定短路 | `test_validation_feedback_service.py`（循环 C）+ 集成 |
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
- [ ] Subtask 0.9: 红窗口确认——验收 .py 与契约测试运行失败且失败形态符合预期（collection ERROR / ImportError 属预期中间态；Gherkin 场景因步骤未实现跳过不计红）；按「模块依赖窗口提交策略」确定各批次入库时点
- [ ] Subtask 0.10: 前置依赖实地验证——4.3 装饰器链/4.4 沙箱适配器/`configs/event_channels.yaml` 现状冒烟（确认预留注释与实际一致）
- [ ] Subtask 0.11: P95 口径重定义（epics「单次重试延迟 P95<5s」→「闭环自身开销 P95<5s，不含 LLM/沙箱时长」，决策 #11）与业务方确认留痕
- [ ] Subtask 0.12: hints payload 契约定稿（`{stderr_excerpt, schema_violations, case_summaries, prior_attempts, suggested_fix}`）+ **per-stage 消费映射定稿**（Code stage 必消费 `suggested_fix` + `prior_attempts` + `stderr_excerpt` + 禁止重复指令——唯一代码作者必须看到失败历史，否则 Reflexion 反馈在作者层断链；Think stage 消费 `case_summaries`（含负样本提示——使引擎对已知不可行签名可感知）+ stderr 摘要；schema_violations → Code/Validate 两 stage）+ 修复建议生成（fix-gen）与引擎 Code stage 的单一作者分工确认（fix-gen 产出 suggested_fix 策略/代码草案，引擎按 hints 重新生成完整代码）；Task 6 测试按「各 stage 消费键集」断言（非笼统「读取并拼入」）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域模型与领域服务

**关联 AC:** AC-3（INFEASIBLE）、AC-4（EvolutionLogEntry）、AC-5（ErrorCase/签名）

#### TDD 循环 A：ErrorCase 聚合根 + EvolutionLogEntry 聚合根 + FixAttempt 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_case.py` + `test_evolution_log_entry.py`（构造不变量：UUID 有效/签名 64 hex/occurrence_count=recovered+infeasible 合计≥1/enhanced_retry_count∈[1,3]/trigger_code 枚举/final_status 终态语义/非法构造抛 242；**FixAttempt 边界形态**：`attempt_execution_id=""`+`stderr_excerpt=""`+`detail="llm_generation_failed"` 可构造合法——禁立 UUID 不变量于该字段） |
| 🟢 绿 | 实现 `src/domain/entities/error_case.py`、`evolution_log_entry.py`、`src/domain/value_objects/validation_feedback.py` 最小代码 |
| 🔄 重构 | 类型注解、中文 docstring（Google 风格）、`__all__` |

- [ ] Subtask 1.1: 🔴 红 — 编写两聚合根 + 值对象失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现三模型最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 B：ErrorSignatureExtractor 领域服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_signature_extractor.py`（STDERR 归一化：路径/行号/时间戳/内存地址剥离 + 数值→`<N>`/引号串→`<S>` 模板化后同根因收敛同签名——含 `KeyError: 'x'` 不同键名收敛用例；尾部锚定 `stderr[-2000:]`——超长 traceback 末尾根因行保留用例；violations 排序归一化；空输入处理；输出恒 64 hex） |
| 🟢 绿 | 实现 `src/domain/services/error_signature_extractor.py`（纯函数，完整 sha256 hexdigest 64 hex） |
| 🔄 重构 | 确认零外部依赖（仅标准库 hashlib/re） |

- [ ] Subtask 1.4: 🔴 红 — 编写签名提取失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现签名提取最小代码
- [ ] Subtask 1.6: 🔄 重构 — 优化代码

#### TDD 循环 C：ToolResultStatus.INFEASIBLE 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_result_status.py`（INFEASIBLE 存在/INVALID 既有语义不回归/SUCCESS 不变量不回归/**5 值全集断言**）+ **修改既有** `tests/unit/domain/value_objects/test_tool_execution_values.py:114-120` 4 值边界断言 → 5 值（先红——既有断言在加值后必红，证明边界断言活着） |
| 🟢 绿 | `src/domain/value_objects/tool_execution.py` 枚举追加 `INFEASIBLE = "infeasible"`（`(str, Enum)` 加值 additive） |
| 🔄 重构 | docstring 更新（`:30`「4 值边界」→ 5 值 + 终态不可行语义 + 与 INVALID"可重试"的区分——同步消解 `:34` INVALID「不进入重试」旧注释与 `:247-249`「可重试」的表述张力） |

- [ ] Subtask 1.7: 🔴 红 — 编写枚举扩展失败测试 + 更新既有 4 值边界断言
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
| 🔴 红 | 编写 `test_validation_feedback_events.py`（字段默认值/自有字段数边界（8/7）/`to_dict()` 序列化 str 化/aggregate_id 关联 execution_id/**execution_id = 主 id（trigger_error.context 同源，R2-11）**/event_type 经 `__init_subclass__` 自动注册——`base.py:74-85`） |
| 🟢 绿 | 实现 `src/domain/events/validation_feedback_events.py` + `events/__init__.py` 导出 |
| 🔄 重构 | 4-5 R1-F01 教训核查：metadata/字段全 str 化 |

- [ ] Subtask 2.1: 🔴 红 — 编写事件失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现两事件
- [ ] Subtask 2.3: 🔄 重构 — 序列化安全核查

#### TDD 循环 B：异常 399 全链路登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_exceptions.py`（code=EXCEPTION_399/继承 BusinessException（断言继承关系非父类码号）/context 四字段/子域=toolchain）+ `test_exception_handlers.py` 期望集合更新（先红，按提交策略与实现同 commit） |
| 🟢 绿 | 新建 `validation_feedback_exceptions.py` → `_code_ranges.py` 两处 → `__init__.py` → `EXCEPTION_HTTP_MAP`（399→422）→ 设计文档两表 → 预留注释改已分配 |
| 🔄 重构 | `grep -rn "EXCEPTION_399" src/` 碰撞自查 + `tests/unit/domain/exceptions/` 全目录既有测试回归（25 文件，不硬编码计数） |

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
| 🔴 红 | 扩展 `test_sandbox_exceptions.py`（stderr/exit_code 可选参数写入 context/默认 None 不破坏 4.4 既有断言/**子类 `SandboxTimeoutError`/`SandboxResourceLimitExceededError` 构造回归**——`super().__init__(reason, context=...)` 透传兼容）+ 新建 `test_aiodocker_adapter_stderr.py`（失败路径异常 context 含 stderr[:2000] 与 exit_code） |
| 🟢 绿 | `sandbox_exceptions.py` ExecutionError 构造器增强（签名含 `context`/`cause` 透传合并，Task 0「修改的既有异常」契约）+ `aiodocker_sandbox_adapter.py:511-518` 填充 |
| 🔄 重构 | 截断常量提取（≤2000） |

- [ ] Subtask 3.1: 🔴 红 — 编写异常增强与适配器填充失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现两处最小改动
- [ ] Subtask 3.3: 🔄 重构 — 优化代码

#### TDD 循环 B：SandboxSecurityDecorator 事件填充 + cause 链提取 helper

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `test_sandbox_security_decorator_events.py`（SandboxExecutionFailed 事件 execution_id/stderr 填充断言——execution_id 取自**外层** 382 异常 context（helper 签名需能拿到外层异常或其 context）；**直连路径**（execute_code_with_protection）execution_id 空串分支）+ cause 链提取 helper 测试（**双分支**：主分支=生产链 382 自定义 `cause` 属性单跳到 313；次分支=389 `__cause__` 链经 383 到 LLM 错误——见 Dev Notes「STDERR 实际浮现路径」） |
| 🟢 绿 | `sandbox_security_decorator.py:132-137` 事件填充（except 块读外层 `exc.context["execution_id"]`）+ 新增 cause 链 stderr 提取函数（同时遍历自定义 `cause` 属性与 `__cause__`/`__context__`，供 4.7 装饰器复用，放置于该模块导出） |
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
| 🔴 红 | 编写 `test_error_case_repository.py` + `test_evolution_log_repository.py`（InMemory：get_by_natural_key 精确查询/record_case 自然键 upsert 分类计数（recovered_count/infeasible_count）/save 幂等/list_by_query 分页过滤/get_by_*） |
| 🟢 绿 | 实现 `src/domain/ports/error_case_repository.py`（含 EvolutionLogQuery 于 evolution_log_repository.py）+ `src/infrastructure/storage/inmemory/` 双实现 |
| 🔄 重构 | InMemory 深拷贝防共享引用污染（4-6 CR1-2 教训） |

- [ ] Subtask 4.1: 🔴 红 — 编写双仓储 InMemory 失败测试
- [ ] Subtask 4.2: 🟢 绿 — 实现端口 + InMemory
- [ ] Subtask 4.3: 🔄 重构 — 深拷贝防护

#### TDD 循环 B：PG 模型 + migration 017 + PG 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | PG 仓储测试（新建 `tests/integration/test_validation_feedback_repositories.py` 为本循环红/绿载体——repo_session 事务 rollback + `xdist_group` 串行 + PG 探活 skip（4-6 `test_tool_version_integration.py:50,158-183` 样板，**非**独立 schema/TestTenant 模式）：upsert 幂等/UNIQUE 冲突 begin_nested 容错重读/JSONB fix_attempts 读写。**R3-1 注记**：outbox fallback 用例**不在本批**——落 Task 6 循环 C 向本文件追加（fallback 修复在 Task 6，本批入库时含 fallback 用例必红破坏批次全绿） |
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
| 🔴 红 | 编写 `test_validation_feedback_service.py` 循环 A 组（触发判定矩阵八行：389 入（Schema/LLM 瞬时两子路径）/382 且 stage=EXECUTION 入（含 316/317）/382 且 stage=SANDBOX_START 出直传/385 出直传/207、201 出直传/410-413 出直传/398 出直传；增强循环 attempt 1→3 计数（总数 3 非重试 3）；耗尽抛 399） |
| 🟢 绿 | 实现 `src/application/ports/validation_feedback_service.py` + `src/application/services/validation_feedback_service.py`（recover 编排：提取→查询→修复→重执行→记录）+ `validation_feedback_prompts.py` |
| 🔄 重构 | 383/399 语义区分注释显式化 |

- [ ] Subtask 5.1: 🔴 红 — 编写触发判定失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现服务骨架与触发判定
- [ ] Subtask 5.3: 🔄 重构 — 优化判定逻辑

#### TDD 循环 B：修复生成 + 防放大 + 案例回填

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 循环 B 组（LLM 修复 prompt 组装含案例 fix_summary（命中 RECOVERED 且非空）/命中 MARKED_INFEASIBLE 注入负样本提示且 `fix_strategy=NEGATIVE_CASE_GUIDED`/空案例 PURE_LLM 降级/**attempt k prompt 含 attempt 1..k-1 失败反馈与禁止重复指令**/fix-gen 自身失败（含非白名单异常）计为该次 attempt 失败/增强期间引擎与 validator 两层重试封顶 1 且按引用恢复（retryable_exceptions 保持 + TOV 无显式 retry_policy 前置断言）/恢复成功回填 recovered_count + 覆写 fix_summary + ToolExecutionRecovered 事件/耗尽回填 infeasible_count + ToolExecutionMarkedInfeasible 事件 + 演进日志） |
| 🟢 绿 | 实现修复循环（fix-gen 产出 suggested_fix + 跨尝试反馈）+ 案例回填 + 演进日志写入 + 事件发布（fire-and-forget，P0-I 模式） |
| 🔄 重构 | Fake LLM 按 system_prompt 角色标记分派（4-5 教训）核查测试自身 |

- [ ] Subtask 5.4: 🔴 红 — 编写修复与回填失败测试
- [ ] Subtask 5.5: 🟢 绿 — 实现完整闭环
- [ ] Subtask 5.6: 🔄 重构 — 优化代码

#### TDD 循环 C：幂等与 evolution log

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 循环 C 组（同 trigger_error 重复 recover：演进日志单行/事件单次/案例以终态调 record_case 同步递增计数（R3-2 定谳——禁只加 occurrence 破坏合计不变量）/短路返回合成结论——INFEASIBLE 语义完整、RECOVERED 为不含证据包的摘要（AC-6 边界注记）） |
| 🟢 绿 | 终态判定短路（execution_id 取自 trigger_error.context；已有终态记录→副作用去重 + 合成结论 + record_case 观测计数） |
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
| 🔴 红 | 编写 `test_validation_feedback_decorator.py`（捕获 389/382 且 stage=EXECUTION 委托 service/382 且 stage=SANDBOX_START 透传/其他异常透传/INFEASIBLE 结果转换不抛异常）+ `test_tool_execution_engine_hints.py`（`validation_feedback_hints` 扩展键读取并拼入 Think/Code prompt（含「优先采纳 suggested_fix」指令）/无 hints 零行为变化） |
| 🟢 绿 | 实现 `src/application/services/validation_feedback_decorator.py` + `tool_execution_engine.py` prompt 构建扩展（`__init__` 签名不变） |
| 🔄 重构 | 引擎改动面最小化核查（4.4 AC-7.4 BDD 断言保护） |

- [ ] Subtask 6.1: 🔴 红 — 编写装饰器与 hints 失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现装饰器 + 引擎扩展
- [ ] Subtask 6.3: 🔄 重构 — 优化代码

#### TDD 循环 B：装配升级 v1.4.0 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_port_contract_validation_feedback_service.py` 红 + `test_port_contract_tool_execution_service.py` 版本期望升级 v1.4.0 **及 EXPECTED_TAGS 增补 feedback**（`:150,:205` set 全等断言——tags += ("feedback",) 不同步必红，R3-6） |
| 🟢 绿 | `composition_root.py`：注册 `validation_feedback_service` + 装饰链最外层加 ValidationFeedbackDecorator + version/compatibility/tags 更新 |
| 🔄 重构 | 契约测试 11 维度 ×2 全绿 + 既有 tool_execution_service 契约回归 |
- [ ] Subtask 6.4: 🔴 红 — 契约测试红确认
- [ ] Subtask 6.5: 🟢 绿 — 装配升级转绿
- [ ] Subtask 6.6: 🔄 重构 — 全绿确认

#### TDD 循环 C：outbox 独立 session 结构性修复（defer 债清偿）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写失败场景测试：**后台/CLI 路径**（无请求 session——`get_session()` 抛 RuntimeError 场景，`PostgreSQLAdapter._session` property `repository/postgresql_adapter.py:46-64`）断言 reliable 事件 outbox 写入经 fallback 独立 session 成功落库（现状该场景静默丢失，当前行为下红）；HTTP 路径（有请求 session）行为不变断言。**fallback 测试清理策略（R2 发现，强制）**：fallback 走 `session_context` 独立写入即 **commit**（`session_context.py:117-127`），repo_session 的 rollback 够不着——测试必须**不挂 repo_session**（否则 ContextVar 有值触发不了 RuntimeError 分支），并在 try/finally 中按**本测试自建 event_id 集合**删除自建行（「只清理自己创建的资源」的本意形态；隔离表「禁手动 delete/truncate」禁令针对 truncate 全表/误删他行，定向删除自建行是该规则的合规例外并在此显式声明） |
| 🟢 绿 | `src/infrastructure/messaging/outbox/outbox_repository.py`：`save` **直接调用 `get_session()` 捕 `RuntimeError`**（实现精度注记 R3-11：经 `PostgreSQLAdapter._session` property 调用时无 session 抛的是 `InvalidStateError`，catch RuntimeError 不命中——必须绕过 property 直调 `get_session()`），RuntimeError 时经注入的 `session_factory` 走 `session_context` 独立写入（`outbox_processor.py:148-150` 先例同款；**修复必须落在 infrastructure 层**——application 禁 import infrastructure；HTTP 路径保持请求 session 同事务，事务性原子性不变） |
| 🔄 重构 | 正常 HTTP 路径行为零变化回归断言 + fallback 行 teardown 验证（自建行清理后零残留）+ `tool_execution_engine.py:282-284` 与 `data_source_resolver.py:352` 两处 defer 注释更新（形态① 无 session 场景已修复；形态② session_context 异常回滚连带丢失登记 `deferred-work.md`——AC-4 遗留债）。**形态② 探针动作（R7）**：实施本循环时顺带核查后台 worker 的 `session_context` 事务边界——R7 调查已确认 HTTP 路径事务语义正确（领域失败经 ExceptionHandlers 转响应走 commit，`session_middleware.py:60-68` 仅未捕获异常才 rollback），真缺陷仅在后台路径的 FAILED 持久化连带丢失；fallback 机制（session_factory 注入 + session_context 独立写入）可直接复用扩展至 `_persist_execution`——探针结论写入 deferred-work 登记行（具备则升级，不具备则留语义推演记录） |

- [ ] Subtask 6.7: 🔴 红 — 编写 outbox 独立 session 失败测试
- [ ] Subtask 6.8: 🟢 绿 — 实现独立 session 修复
- [ ] Subtask 6.9: 🔄 重构 — 双路径回归 + 注释清偿

#### TDD 循环 D：execution_id 全链同源（决策 #16 / R7——关闭 R2-5 deferred）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写失败测试：①链入口注入断言——`ToolExecutionService.execute` 后 `context.extensions["schema_execution_id"]` 存在且为 UUID；②引擎复用断言——注入预置 id 后 `ToolExecution` 聚合 `execution_id` 与之相等（含 382 异常 context 同 id 断言）；③TOV 透传断言——389 的 `context["execution_id"]` 与预置 id 相等（`extract_schema_execution_id` 命中 extensions 通道）；④未注入时引擎新铸（向后兼容——既有单测直构引擎不注入仍绿） |
| 🟢 绿 | `tool_execution_service.py:64` 入口注入（1 行）+ `tool_execution_engine.py:137-138` 聚合 id 优先读 extensions（3 行，`uuid.uuid4()` 兜底） |
| 🔄 重构 | 4.3/4.5 既有 schema 事件测试回归（execution_id 语义从「TOV 随机铸造」变「链入口统一」——断言 instanceof UUID 者不受影响，断言特定值者核对） |

- [ ] Subtask 6.10: 🔴 红 — 编写 id 同源四断言失败测试
- [ ] Subtask 6.11: 🟢 绿 — 入口注入 + 引擎复用两处最小实现
- [ ] Subtask 6.12: 🔄 重构 — 既有 schema 事件测试回归

**完成标准/Definition of Done:**
- [ ] 装饰链四层装配 + v1.4.0
- [ ] outbox 修复落地 + defer 注释清偿
- [ ] execution_id 全链同源（聚合/异常 context/演进日志/事件四点一 id）
- [ ] 既有契约测试零回归

---

### Task 7: 集成测试与性能基准

**关联 AC:** AC-4、AC-5、AC-6、AC-7

> 无独立 TDD 循环表——本 Task 为真实服务全链验证（epics 硬路径 `tests/integration/test_validation_feedback_integration.py`）。

- [ ] Subtask 7.1: 全链闭环集成测试（真实 PG repo_session 事务 rollback + xdist_group 串行 + PG 探活 skip——4-6 `test_tool_version_integration` 样板：模拟沙箱失败→闭环→恢复/耗尽两路径；InMemory→PG 仓储替换真实实现）
- [ ] Subtask 7.2: 幂等集成测试（同 trigger_error 重复 recover() 三副作用断言 + 合成结论）
- [ ] Subtask 7.3: 性能基准一——闭环开销 P95<5s（签名提取+查询+日志写入计时，20 次采样，端口级计时代理 + `statistics.quantiles` 分位断言 + 分级 skip 留证）
- [ ] Subtask 7.4: 性能基准二——闭环机制成功率 ≥80%（20 次可修复故障注入，AsyncMock LLM 可编程修复序列按 prompt 结构分派；主断言为内容性断言——修复 prompt 含 stderr/案例/历史反馈、hints 注入透传）
- [ ] Subtask 7.5: 性能基准三——不可行标记机制准确率（20 次不可修复全部标记 + 可修复 0 误标，等效 100%）
- [ ] Subtask 7.6: outbox 修复集成回归（后台路径 fallback 独立 session 投递 + HTTP 路径零变化）

**完成标准/Definition of Done:**
- [ ] 集成测试全绿（真实服务）
- [ ] 三组性能基准达标
- [ ] 集成覆盖率 ≥75%

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** 全部（epics 硬路径四项架构测试）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 8.1: 创建 `tests/unit/architecture/test_validation_feedback.py`（epics 指定硬路径——与目录内既有 `test_arch_*.py` 命名惯例（28 个文件）不同，按 epics_v1.0.md:1395 指定名创建，文件头 docstring 注明）
- [ ] Subtask 8.2: 重试增强验证器——STDERR 捕获与修复建议生成链路断言（触发→prompt 含 STDERR/案例→重执行）
- [ ] Subtask 8.3: 失败标记验证器——3 次增强失败后 INFEASIBLE + 399 + 事件三联断言
- [ ] Subtask 8.4: 幂等性验证器——同 trigger_error 重复 recover：日志单行 / 事件单次 / 案例分类计数与 occurrence 同步递增（record_case 幂等路径，AC-6 R3-2 定谳口径）/ 不新建行 / fix_summary 不覆写
- [ ] Subtask 8.5: 演进日志验证器——失败历史可追溯（双查询面）
- [ ] Subtask 8.6: INFEASIBLE×FAIL_FAST 语义守护验证器（决策 #14 / R6 业界对标）——①`NodeRunStatus.state` 类型不抹除断言：INFEASIBLE 结果的节点 state 为 `"INFEASIBLE"`（非二值 `"FAILED"`——`tool_chain_orchestrator.py:637` 扩展三值判定）且 `tool_result` 含失败摘要；②FAIL_FAST 中断因果断言：INFEASIBLE 触发 `ToolChainExecutionFailedError` 时异常 context 含 `error_signature` 与尝试次数（`:218-224` cause=None 修复后）；③SKIP_DOWNSTREAM 兼容断言：INFEASIBLE 节点的下游 SKIPPED、独立分支正常执行
- [ ] Subtask 8.7: 循环依赖检测使用 ruff/isort（不引入 pylint）+ 运行完整测试套件生成报告

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
| 5 | 错误签名算法 | 领域服务纯函数归一化（剥路径/行号/时间戳/内存地址 + 数值/引号串模板化 + 尾部锚定 `stderr[-2000:]`）→ **完整 sha256 hexdigest（64 hex）** | 确定性可测；同根因不同表层输出收敛（幂等前提）——Sentry message templating 对标防插值分裂、尾部锚定防切根因；完整摘要保留前缀粗化分组派生能力（多案例检索前置）；V1 精确匹配，向量检索留 L3 扩展 |
| 6 | 案例回填时机 | 恢复成功回填 `recovered_count += 1` 并覆写 fix_summary（仅 RECOVERED 覆写）+ 耗尽回填 `infeasible_count += 1` | 成功案例对后续修复价值最高（Few-Shot 素材）；分类计数防不可行写回冲掉修复配方；失败计数支撑负样本提示与准确率统计 |
| 7 | STDERR 链修复方式 | `ExecutionError` 构造器可选参数（stderr/exit_code 入 context，**含 context/cause 透传合并**——子类零改动）+ adapter 填充 + 装饰器事件填充（execution_id 取外层 382 context） | 向后兼容（默认值 + 透传保证子类 `super().__init__(reason, context=...)` 零改动）；事件字段已预留（sandbox_events.py:96/101/104）只欠填充 |
| 8 | 防重试放大 | 增强循环期间内层重试全部封顶：引擎 `_retry` 与 validator 校验重试（动态读 engine._retry，前置条件=TOV 无显式 retry_policy）整体替换 `max_attempts=1`（保留原 retryable_exceptions）+ try/finally 按引用恢复 | 4.3 P0-1 教训复用；修正数学：TOV 已无条件封顶 engine 内层（:114-129），防放大的真实对象是增强期间的 TOV 校验重试（未防 3×3×1=9x）；按引用恢复防默认 RetryPolicy（含 313）静默偏离生产白名单（生产已收窄排除）；嵌套恢复链经推演成立（TOV :119-127 复制白名单不硬编码） |
| 9 | hints 注入通道 | `context.extensions["validation_feedback_hints"]`（ExecutionContext frozen + with_extension 工厂），payload 契约 `{stderr_excerpt, schema_violations, case_summaries, prior_attempts, suggested_fix}` | P0-D 模式先例（schema_last_violations 同款）；引擎 `__init__` 签名不变；引擎 Code stage 唯一代码作者（指令「优先采纳 suggested_fix」）避免双作者不可归因 |
| 10 | outbox 修复落点 | `messaging/outbox/outbox_repository.py` fallback 独立 session（优先 get_session()，RuntimeError 时经 session_factory 走 session_context） | 两处 defer 注释显式指派本 Story；outbox_processor.py:148-150 独立 session 先例；application 层禁 import infrastructure 约束；HTTP 路径事务性原子性保持（无条件独立 session 会破坏原子性并污染 rollback 隔离测试） |
| 11 | 性能指标口径 | P95<5s 限闭环自身开销（签名/查询/日志），LLM 与沙箱时长除外；比率指标命名为「闭环机制有效性」（mock LLM 度量编排正确性非修复能力） | epic 字面指标可测化——LLM 生成受 LLMConfig.timeout=600s 支配物理上不可能 <5s；Task 0 与业务确认留痕（Subtask 0.11） |
| 12 | 修复循环反馈记忆 | attempt k 的修复 prompt 携带 attempt 1..k-1 失败反馈（FixAttempt.stderr_excerpt/detail + 禁止重复指令） | Reflexion/Self-Debugging/ChatRepair 共识——无跨尝试反馈时 attempt 2/3 与 attempt 1 独立同分布，确定性采样下重复生成相同失败修复，3 次尝试退化为同一次的重复采样 |
| 13 | 幂等语义 | 副作用去重（execution_id 取自 trigger_error.context）+ INFEASIBLE 结论可重放；RECOVERED 重放返回合成摘要（不含证据包） | 引擎每次 execute 新铸 execution_id，「装饰器重复调用」不命中幂等键（架构边界）；日志无 result 载荷故不承诺 RECOVERED 完整重放 |
| 14 | INFEASIBLE×FAIL_FAST 语义定稿（R6 业界对标勘误） | 耗尽结果化后 FAIL_FAST 链**仍中断**（波次检查 `:208-225` 兜底，R2「变为继续执行」结论系漏看该检查点）；真实 delta = 类型丢失（node state 二值判定）+ cause=None（异常可观测性降级）+ 同波兄弟跑完（算力浪费）——前两者随本 Story 修复（Task 8.6），同波取消为可选优化 deferred | 业界主流一致：永久性失败 × 显式 fail-fast = 中断（K8s PodFailurePolicy FailJob 短路重试立即终止 / Temporal non-retryable 跳过重试 / SF 未捕获即 fail）；「结果化继续」须显式声明而非默认副作用；类型元数据在传播链不可抹除（Temporal re-wrap 反模式）；「业务方确认」阻碍经对标消解——中断语义维持现状即正确立场 |
| 15 | fix_strategy 三分支 | `FixStrategy` 三值：CASE_GUIDED（命中 RECOVERED 且 fix_summary 非空）/ NEGATIVE_CASE_GUIDED（命中 MARKED_INFEASIBLE——负样本提示形态）/ PURE_LLM（无命中） | 二值枚举会把「负样本命中」虚标为 PURE_LLM（反向虚标，R1-9 同轴）；演进日志失败史需区分「已知不可行签名仍尝试」（AIOps 最有价值信号）与「无案例可查」；新建值对象加值零成本 |
| 16 | execution_id 全链同源（R7 定稿） | 链入口 `ToolExecutionService.execute` 注入 `schema_execution_id`（沿用 4.3 预留的 extensions 透传键——`schema_event_helpers.py:141-146` 第一优先级）+ 引擎聚合 id 优先读该键（Task 6 循环 D）——聚合/382/389/演进日志/两事件四点一 id | 关闭 R2-5「两套 id 空间」deferred；改动 ~4 行生产代码（入口 1 + 引擎 3）+ TOV 零改动自动命中；R7 调查勘误了 R6 前的「ToolResult 加字段」设想（389 抛异常不构造 ToolResult，加字段无效）；引擎 save 为 upsert，校验重试同 id 重入无乐观锁冲突；dev 前是窗口（dev 后事件链消费面固化，再改过 ContractGate） |

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
        except ToolResultValidationError as trigger:
            # 389 = OUTPUT 校验基础重试耗尽（Schema 违规 / LLM 瞬时故障两子路径）
            return await self._feedback.recover(
                tool_id=tool_id, tool=tool, tool_call=tool_call,
                context=context, trigger_error=trigger,
            )
        except ToolExecutionFailedError as trigger:
            # 382 且 stage=EXECUTION = 执行失败（cause 链可提取沙箱 STDERR——生产主浮现形态）
            # 382 且 stage=SANDBOX_START = 沙箱启动失败（infra 故障，代码修复不可归因）→ 直传
            if trigger.context.get("stage") == "EXECUTION":
                return await self._feedback.recover(
                    tool_id=tool_id, tool=tool, tool_call=tool_call,
                    context=context, trigger_error=trigger,
                )
            raise
        # ToolExecutionTimeoutError(385) / 207 / 201 / 410-413 / 398 → 不捕获自然上抛
        # 增强尝试中内层浮出上述非触发类异常 → recover() 内中止闭环直传（AC-2 VC）


class ValidationFeedbackService:
    async def recover(self, tool_id, tool, tool_call, context, trigger_error) -> ToolResult:
        # 幂等短路：execution_id = trigger_error.context["execution_id"]
        #   已有该 execution 终态演进日志 → 副作用去重 + 返回合成结论
        #   （INFEASIBLE 语义完整；RECOVERED 为不含证据包的摘要——AC-6 边界注记）
        # 1. 提取错误上下文：cause 链提取 stderr（382.cause=ExecutionError.context——生产主路径
        #    自定义 cause 属性单跳；或 389.__cause__ 经 383 到 LLM 错误——次路径）或 violations（389.context）
        # 2. signature = ErrorSignatureExtractor.extract(stderr) / extract_from_violations(...)
        # 3. 增强循环 attempt 1..3（RetryPolicy.max_attempts=3 总尝试语义）：
        #    a. case = error_case_repo.get_by_natural_key(tenant, tool, signature)
        #       命中且 outcome=RECOVERED 且 fix_summary 非空 → case_summaries=[fix_summary]
        #       命中 MARKED_INFEASIBLE → 负样本提示（"此签名历史 N 次修复均失败"）
        #    b. fix_prompt = 组装(stderr + case_summaries + violations
        #                       + attempt 1..k-1 失败反馈（stderr_excerpt/detail）
        #                       + "以下方案已失败，禁止重复" 指令)
        #       fix_strategy = CASE_GUIDED（命中 RECOVERED 且 fix_summary 非空）
        #                    / NEGATIVE_CASE_GUIDED（命中 MARKED_INFEASIBLE——负样本提示形态）
        #                    / PURE_LLM（无命中）                          # 三分支，决策 #15
        #    c. suggested_fix = fix_gen(fix_prompt)  # 包 _call_with_retry(max_attempts=1)，
        #       # 失败计为该次 attempt 失败（detail="llm_generation_failed"），不裸穿
        #    d. hints = {stderr_excerpt, schema_violations, case_summaries,
        #               prior_attempts, suggested_fix}   # payload 契约（Task 0.12）
        #       hints_context = context.with_extension("validation_feedback_hints", hints)
        #    e. 防放大：保存 engine 原 RetryPolicy 引用 → 整体替换
        #       RetryPolicy(max_attempts=1, retryable_exceptions=原白名单)
        #       （validator 校验重试动态读 engine._retry.max_attempts，同被封顶）
        #       → try: 重执行内层链 → finally: 按引用恢复
        #       注意：wrapped 是 SSD（无 _retry），需经组合根注入 engine 引用穿透
        #    f. 成功 → recovered_count += 1 + 覆写 fix_summary + 演进日志(RECOVERED, trigger_code,
        #       duration_sec, fix_attempts[含 attempt_execution_id]) + ToolExecutionRecovered 事件
        #            → return ToolResult(SUCCESS, retry_count=attempt)
        # 4. 耗尽 → 抛/捕获 ValidationFeedbackRetryExhaustedError(399) 内部信号
        #    → infeasible_count += 1（fix_summary 不动）+ 演进日志(MARKED_INFEASIBLE)
        #       + ToolExecutionMarkedInfeasible 事件
        #    → return ToolResult(INFEASIBLE, output={error_signature, stderr_excerpt, attempts}, retry_count=3)
```

**触发判定矩阵（必须完整测试）：**

| 触发异常 | 编码 | 入闭环 | 理由 |
|---------|------|--------|------|
| `ToolResultValidationError` | 389 | ✅ | OUTPUT 校验基础重试耗尽——两子路径：Schema 违规（violations 直接在 context）/ LLM 瞬时故障（cause 链 389→383→LLM 错误，**violations 为空**，签名走 LLM 错误消息归一化） |
| `ToolExecutionFailedError` 且 `stage="EXECUTION"` | 382 | ✅ | 执行失败（**生产装配下 STDERR 的主浮现形态**——cause 单跳到 313，见下方浮现路径）；含 316/317（ExecutionError 子类经兜底包装） |
| `ToolExecutionFailedError` 且 `stage="SANDBOX_START"` | 382 | ❌ 直传 | 沙箱启动失败（312/315 容器/镜像）——基础设施故障非代码缺陷，LLM 修复不可归因（3 次注定失败的修复尝试纯耗 LLM 配额且误标 INFEASIBLE） |
| `ToolExecutionTimeoutError` | 385 | ❌ 直传 | 超时不可修复（重试同样超时） |
| `BusinessRuleViolationError` | 207 | ❌ 直传 | 白名单策略违规，非代码缺陷 |
| `ValidationError` | 201 | ❌ 直传 | 标记语法错误，非运行时可修复 |
| `DataSourceError` 族 | 410-413 | ❌ 直传 | 外部数据不可用，4.1b 语义"策略违规 vs 数据不可用"区分 |
| `ToolSchemaMissingError` | 398 | ❌ 直传 | required_schema 缺失，配置问题非代码缺陷（4.3 定义、4.7 消费契约） |

> **STDERR 实际浮现路径（防困惑，重要——生产装配语义）**：生产装配经 `build_tool_execution_engine`（`tool_execution_engine.py:569-578`，组合根 `:2330-2333`）把引擎重试白名单收窄为 `(LLMAPIError, LLMResponseError, TimeoutError)`——**`ExecutionError`(313) 不在白名单**（`:558-560` 注释：沙箱确定性失败重试无意义）。因此：
> - **主路径（STDERR 场景）**：313 → 引擎兜底 `except Exception`（`:253-266`）包成 `ToolExecutionFailedError(382, stage="EXECUTION", cause=313)`（自定义 `cause` 属性，非 `raise from`）→ 382 不在 validator 白名单（`tool_output_validator.py:201-204`）直浮 → SandboxSecurityDecorator 解包发事件后原样上浮（`sandbox_security_decorator.py:190-195`）→ VFD 捕获入闭环。STDERR 提取 = `382.cause`（自定义属性单跳）→ `ExecutionError.context["stderr"]`（AC-1 修复后携带）。
> - **次路径（LLM 瞬时故障）**：LLMAPIError/LLMResponseError/TimeoutError 可重试 → 引擎 3 次耗尽抛 383（`retry_helpers.py:112-117`，`cause=last_exc` 自定义属性）→ validator 白名单含 383 再重试 3 次耗尽 → **转 389 抛出**（`tool_output_validator.py:223-229`，`from retry_exc` 设 `__cause__`）。链形态 `389.__cause__ → 383.cause → LLM 错误`——**无 STDERR 无 violations**，签名走 LLM 错误消息。
> - **单测直构形态注意**：裸构造 `ToolExecutionEngine()` 用默认 `RetryPolicy`（**含** ExecutionError，`retry_helpers.py:54-59`）时 313 会被引擎重试——单测构造主路径 382 场景须用生产白名单形态或直接构造 382。
> - 提取 helper 必须**同时遍历自定义 `cause` 属性与 `__cause__`/`__context__`**（`base_exceptions.py:62,72`；`_unwrap_sandbox_error` 的判级顺序 `:113-120`）——Task 3 嵌套链测试覆盖两分支，主分支为 382 形态。

### 数据库表设计（migration 017: `017_validation_feedback.py`）

```sql
-- error_cases：错误案例库（自然键 UNIQUE）
CREATE TABLE error_cases (
    id                UUID PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    tool_id           UUID NOT NULL,
    error_signature   VARCHAR(64) NOT NULL,           -- 完整 sha256 hexdigest（64 hex，三处口径同一）
    error_category    VARCHAR(64) NOT NULL,           -- 沙箱 error_code（EXCEPTION_313 等）或 'SCHEMA_VIOLATION' 或 'LLM_TRANSIENT'
    stderr_excerpt    VARCHAR(2000) NOT NULL DEFAULT '',
    fix_summary       VARCHAR(2000) NOT NULL DEFAULT '',  -- 仅 RECOVERED 路径覆写
    outcome           VARCHAR(32) NOT NULL,           -- 最近一次：RECOVERED / MARKED_INFEASIBLE
    recovered_count   INTEGER NOT NULL DEFAULT 0,
    infeasible_count  INTEGER NOT NULL DEFAULT 0,
    occurrence_count  INTEGER NOT NULL DEFAULT 1,     -- = recovered_count + infeasible_count
    last_seen_at      TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_error_cases_natural_key UNIQUE (tenant_id, tool_id, error_signature)
);
CREATE INDEX ix_error_cases_tool ON error_cases (tenant_id, tool_id, last_seen_at DESC);
-- 注：不建 (tenant_id, tool_id, error_signature) 普通索引——与 UNIQUE 约束完全同列属冗余写放大；
-- 本索引支撑"按工具查最近案例"排序

-- tool_evolution_logs：演进日志（execution_id 幂等）
CREATE TABLE tool_evolution_logs (
    id                    UUID PRIMARY KEY,
    tenant_id             UUID NOT NULL,
    tool_id               UUID NOT NULL,
    execution_id          UUID NOT NULL,
    tool_version          VARCHAR(64) NOT NULL DEFAULT '',
    trigger_code          VARCHAR(16) NOT NULL,       -- EXCEPTION_389 / EXCEPTION_382（失败模式第一维分类）
    error_signature       VARCHAR(64) NOT NULL,
    enhanced_retry_count  INTEGER NOT NULL,           -- 1-3
    fix_attempts          JSONB NOT NULL DEFAULT '[]', -- FixAttempt 摘要数组（含 attempt_execution_id 回链）
    duration_sec          NUMERIC(10,3) NOT NULL DEFAULT 0,  -- 闭环时长（MTTR 等价物）
    final_status          VARCHAR(32) NOT NULL,       -- RECOVERED / MARKED_INFEASIBLE
    created_at            TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_tool_evolution_logs_execution UNIQUE (tenant_id, execution_id)
);
CREATE INDEX ix_tool_evolution_logs_tool ON tool_evolution_logs (tenant_id, tool_id, created_at DESC);
```

### ⚠️ 实现陷阱提示（Pitfalls）

1. **事件 metadata 序列化**：新事件字段一律 `str()` 化入 metadata/payload（4-5 R1-F01：UUID 对象 → json.dumps TypeError → reliable 通道 100% 静默失败）。
2. **HTTP_MAP 注释对齐**：`exception_handlers.py` 注释行内 `# 399 — ...` 与实际 code 严格一致（4.1a 偏移 bug 先例）。
3. **InMemory 仓储深拷贝**：save/get 返回 deepcopy 副本（4-6 CR1-2：共享引用致测试间状态污染；`inmemory/tool_version_repository.py:32-39` `_detached()` 唯一先例）。
4. **PG upsert 并发**：UNIQUE 冲突 flush 后 session 进 PendingRollback，必须 `begin_nested()` SAVEPOINT 包裹重读（4-6 CR1-4）。
5. **frozen dataclass 加字段**：新字段必须带默认值且置于既有字段之后（4-6 教训；`ToolResultStatus` 是 `(str, Enum)` 加枚举值无此约束）。
6. **`configs/event_channels.yaml`**：实际路径是 `configs/`（复数）不是 `config/`，顶层键是 `event_channels:`；YAML 与 DEFAULT_MAPPINGS 两处必须同步（YAML 优先）。
7. **设计文档两个 §3.3.2**：`sisys-uni-exception-design.md` 存在同号小节（`:649`/`:786`），编码分配表与子域范围表都要更新；`:805`/`:807` 两行既有 399 表述连带核对（4-6 踩坑）。
8. **装饰器恢复 Engine `_retry`**：必须按**保存的引用**整体替换/恢复（frozen dataclass 禁属性赋值；恢复时重建默认 `RetryPolicy()` 会把白名单静默改回含 313，闭环后浮现形态漂移）；try/finally 防御性恢复（ToolOutputValidator:114-129 降级 + :230-233 恢复完整模式）。
9. **禁止 `# noqa`/`# type: ignore`**：三条 grep 自查零输出后才可提交。
10. **性能计时口径**：P95 基准的计时窗口排除 LLM/沙箱调用（端口级计时代理包裹仓储 + mock 替身注入真实挂起点 `await asyncio.sleep(0)`——4-5 R2-F02 原语义为制造挂起点）；P95 分位断言用 `statistics.quantiles` + 分级断言（达标 assert / 不达标 skip 留证据，4-6 `test_tool_version_integration.py:398-415` 先例）。
11. **ExecutionError 子类兼容**：新构造器必须透传合并 `context`——`SandboxTimeoutError`/`SandboxResourceLimitExceededError` 的 `super().__init__(reason, context={...})` 不改即炸（Task 0「修改的既有异常」契约）。
12. **既有 4 值边界断言**：`test_tool_execution_values.py:114-120` 在加 INFEASIBLE 后必红——属预期红（证明边界断言活着），与枚举加值同 commit 更新为 5 值。
13. **单测构造 382 主路径**：裸构造引擎（默认 RetryPolicy 含 313）时 313 被引擎重试不走主路径——单测直接构造 382(stage=EXECUTION, cause=313) 或用生产白名单形态（Dev Notes 浮现路径节）。
14. **封顶窗口的并发边界**：VFD 封顶窗口（含 fix-gen LLM 时长）内同 scope 并发共享引擎的内层重试被连带封顶——SCOPED per-request 隔离下无实害；后台单 scope 并发为已知边界（TOV 先例同款已接受风险，窗口更长）。
15. **fallback 测试清理纪律**：outbox fallback 测试不挂 repo_session（否则触发不了 RuntimeError 分支），独立 session 写入即 commit——try/finally 按自建 event_id 集合删除自建行（Task 6 循环 C 强制项）。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── error_case.py                    # [新] 错误案例聚合根
│   │   └── evolution_log_entry.py           # [新] 演进日志聚合根
│   ├── events/
│   │   ├── validation_feedback_events.py    # [新] 2 领域事件
│   │   └── __init__.py                      # [改] 导出
│   ├── exceptions/
│   │   ├── validation_feedback_exceptions.py # [新] EXCEPTION_399
│   │   ├── sandbox_exceptions.py            # [改] ExecutionError stderr/exit_code 参数（context 透传合并）
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
│       ├── tool_execution_engine.py         # [改] hints prompt 读取 + defer 注释清偿 + 聚合 id 优先读 schema_execution_id（Task 6D/决策 #16）
│       ├── tool_execution_service.py        # [改] 链入口注入 schema_execution_id（决策 #16，1 行）
│       ├── tool_chain_orchestrator.py       # [改] node state 三值判定（INFEASIBLE）+ FAIL_FAST cause 填充（Task 8.6/决策 #14）
│       └── sandbox_security_decorator.py    # [改] 事件 execution_id/stderr 填充
├── infrastructure/
│   ├── external_services/sandbox/
│   │   └── aiodocker_sandbox_adapter.py     # [改] stderr 填入异常 context
│   ├── messaging/
│   │   ├── channel_router.py                # [改] 新事件 + reliable 升级
│   │   └── outbox/
│   │       └── outbox_repository.py         # [改] fallback 独立 session（get_session RuntimeError → session_context）
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
| `SandboxExecutionFailed` 事件 `stderr`/`execution_id` 字段 | `src/domain/events/sandbox_events.py:96,101,104` | **已预留无需新建**，仅由发布方填充（Task 3——execution_id 取外层 382 context，stderr 取内层 313 context） |
| `ToolSchemaValidationFailed` 事件（自有业务字段 10 个：execution_id/tool_id/tenant_id/event_type/validation_phase/schema_violations/retry_attempt/failed_at/schema_version/is_final——源 docstring 自称「13 字段」为 4.3 原文，以字段定义为准） | `src/domain/events/tool_schema_events.py:25` | reliable 通道升级（Task 2），外部消费者面 |
| `ToolOutputValidator` 耗尽契约 | `src/application/services/tool_output_validator.py:220-229` | 抛 389 即本 Story 触发信号（Schema 违规 / LLM 瞬时两子路径——Dev Notes 浮现路径），**禁止改动其语义** |
| `_call_with_retry` / `RetryPolicy` | `src/application/services/retry_helpers.py:36,62` | 增强循环复用（max_attempts=3 总尝试语义 + on_failure_callback **已实现**（`:65,95-99`），纯复用无需增强） |
| cause 链解包先例 `_unwrap_sandbox_error` | `src/application/services/sandbox_security_decorator.py:100-120` | stderr 提取 helper 参照实现（判级 `cause→__cause__→__context__`；注意其"首中 ExecutionError 即停"——新 helper 需同时取外层异常 context 的 execution_id） |
| `context.extensions` 注入模式（P0-D） | `tool_output_validator.py:135-141` + `tool_execution_engine.py:446-447` | `validation_feedback_hints` 同款通道 |
| `with_extension` frozen 工厂 | `src/domain/value_objects/tool_execution.py:95` | hints 上下文透传 |
| `LLMClientPort.generate` | `src/domain/ports/llm_client.py:137` | 修复代码生成（无需新端口） |
| `EXCEPTION_399` 预留 | `_code_ranges.py:85` + `sisys-uni-exception-design.md:718` | 直接占用（勿新开码位） |
| `session_context` 独立会话 | `src/infrastructure/storage/postgresql/session_context.py:97-132` + `messaging/outbox/outbox_processor.py:148-150` 先例 | outbox fallback 修复复用（注意实际路径在 `messaging/outbox/` 子目录） |
| `ToolExecutionQuery` Query Object 先例 | `src/domain/ports/tool_execution_repository.py:24` | EvolutionLogQuery 同款模式 |
| 4.3 订阅契约设计 | `stories/4-3-tool-io-schema-validation.md:1600-1669`「4.6/4.7 架构演进路径」 | 事件字段消费方式参照（去重键/is_final/schema_version 防漂移） |
| 端口契约测试 11 维度样板 | `tests/contracts/test_port_contract_tool.py` | 新契约测试同款结构 |
| 事件通道映射契约样板 | `tests/contracts/test_event_channel_mapping_tool_version.py` | 同款逐字段断言 |
| fire-and-forget 事件发布 + violations 截断 helper | `src/application/services/schema_event_helpers.py`（`publish_schema_event_async`/`truncate_violations_for_event`，P0-H/P0-I） | 新事件发布复用同款模式（不阻塞主流程 + 截断防 DoS） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-6](./4-6-tool-version-management.md)（done）+ [Story 4-5](./4-5-red-blue-debate-basic.md)（done）+ [Story 4-3](./4-3-tool-io-schema-validation.md)（done）

**关键学习/Key Learnings:**
- 4-3 P0-1：装饰器重试与 Engine 内部重试叠加 → 81x LLM 调用放大触发超时（4.3 时代威胁模型）——增强循环必须封顶内层全部重试（引擎 + validator 两层 max_attempts=1，按引用恢复）
- 4-5 R1-F01：事件 metadata 携带 UUID 对象 → json 序列化 TypeError → reliable 通道 100% 静默失败——字段一律 str 化
- 4-6 CR1-4：PG UNIQUE 冲突后 PendingRollback → begin_nested SAVEPOINT 包裹容错重读
- 4-6 R3-1：应用层禁止 import infrastructure（import-linter 契约）——注入端口/标量，outbox 修复落 infrastructure
- 4-5 R1-F06/R2-F01：Fake LLM 禁按易混淆子串分派（按 response_schema/system_prompt 角色标记）；mock 需真实挂起点（asyncio.sleep）
- 4-6 文档审查 R1 系列：规范内部矛盾/死锁/不可达是 P0 高发区——Task 0 触发判定矩阵必须完整无死角
- 4-6 留项登记纪律：defer 项显式登记留痕（本 Story 兑现 399/事件字段/reliable 通道/outbox session 四笔预留债）

**应用到本故事/Applied to This Story:**
- [ ] 增强循环防放大（两层封顶 + 按引用恢复，AC-2 硬性验证项）
- [ ] 事件字段 str 化 + InMemory deepcopy + SAVEPOINT 容错（实现陷阱清单）
- [ ] 触发判定矩阵八行全覆盖测试（回归网先行）
- [ ] 四笔预留债逐项清偿并在原注释处更新状态（outbox defer 注释按形态①已修复/形态②登记 deferred-work 更新）
- [ ] 既有 4 值边界断言 4→5 联动（证明边界断言活着）
- [ ] 修复 prompt 跨尝试反馈（决策 #12——防同分布重复失败修复）

### 非目标（Out of Scope）

- ❌ **工具熔断**（or.md 四.7.(3)"连续 3 次校验失败自动熔断"——:315，属「四、AGENT」章第 7 节）——不在本 epic AC 清单，与反馈闭环正交；**登记 `deferred-work.md`**（建议挂 Story 5.x Agent 弹性隔离或独立运维 Story）。注：签名级 fast-fail（同签名 infeasible_count 高时注入负样本提示并缩减尝试）**属本 Story AC-5 已含**，与工具级熔断正交、不连带 defer
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

*src 生产代码（18 新 + 14 改）+ deploy/configs/docs（1 新 + 2 改）：*
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
- 修改：`value_objects/tool_execution.py`（INFEASIBLE + docstring 5 值）、`sandbox_exceptions.py`（ExecutionError 增强）、`_code_ranges.py`、`exceptions/__init__.py`、`exception_handlers.py`（399→422）、`events/__init__.py`、`aiodocker_sandbox_adapter.py`（stderr 填充）、`sandbox_security_decorator.py`（事件填充 + cause 链提取导出）、`tool_execution_engine.py`（hints + defer 注释清偿 + **聚合 id 优先读 schema_execution_id**——决策 #16/Task 6 循环 D）、`tool_execution_service.py`（**链入口注入 schema_execution_id**——决策 #16，1 行）、`tool_chain_orchestrator.py`（R6/Task 8.6：`:637` node state 三值判定支持 "INFEASIBLE" + `:218-224` FAIL_FAST 异常 context 填 error_signature——决策 #14 两缺口修复）、`channel_router.py`、`composition_root.py`（3 端口 + v1.4.0）；configs 改 `configs/event_channels.yaml`；docs 改 `sisys-uni-exception-design.md`（两表 + :805/:807 连带）；infra 改 `messaging/outbox/outbox_repository.py`（fallback 独立 session）

*测试（23 新 + 4 改）：*
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
- `tests/integration/test_validation_feedback_repositories.py` - PG 双仓储 + outbox fallback 集成（Task 4 载体）
- 修改：`tests/unit/domain/exceptions/test_sandbox_exceptions.py`（扩展）、`tests/unit/interfaces/api/test_exception_handlers.py`（期望集合）、`tests/contracts/test_port_contract_tool_execution_service.py`（版本 v1.4.0 + EXPECTED_TAGS 增补 feedback）、`tests/unit/domain/value_objects/test_tool_execution_values.py`（4→5 值边界断言）

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
3. [x] Architecture constraints extracted 架构约束已提取（含 15 项关键架构决策——决策表 #1~#15，其中 #14/#15 为文档审查 R2/R3 增补）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4-6/4-5/4-3）
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | STDERR 浮现路径断言与生产装配相反（声称 313 在引擎白名单→389 形态浮现；实际生产白名单已收窄，313 经兜底包 382(stage=EXECUTION) 直浮；389→383 链仅 LLM 瞬时场景） | P0 | 重写 Dev Notes 浮现路径节为双分支（382 主路径/389 次路径）+ 触发矩阵 8 行化（SANDBOX_START 排除）+ AC-1/2/Task 3/蓝图/资产表全传播（约 13 处）。**R2 勘误**：BDD Edge Cases/AC-2 VC/Task 5 循环 A 三处衍生位仍为 6-7 行口径，R2 已补齐（见 R2-1/R2-2/R2-3） |
| R1-2 | execution_id 全链悬空（ExecutionContext 无该字段；幂等键不可达；事件填充无来源） | P0 | 定义提取机制（外层 382 context / trigger_error.context）+ 幂等可达场景改写（同 trigger_error 重复 recover）+ 直连路径空串分支 |
| R1-3 | 签名位数自相矛盾（16 hex vs 64 hex，Task 1 两 TDD 循环不可能同时绿） | P0 | 统一 64 hex 完整 sha256 + 归一化补强（数值/引号串模板化、尾部锚定 stderr[-2000:]）——Sentry 对标 |
| R1-4 | 修复循环无跨尝试失败反馈（attempt 2/3 与 attempt 1 独立同分布，循环不收敛——违背 Reflexion/Self-Debugging 共识） | P0 | 修复 prompt 注入 attempt 1..k-1 失败反馈 + 禁止重复指令 + hints payload 契约定稿 + 引擎 Code stage 单一作者（决策 #12 新增） |
| R1-5 | outbox 修复自相矛盾（无条件独立 session 破坏 HTTP 事务原子性 + 污染 rollback 隔离测试；条件式修不了自设验证项） | P0 | 重设计为 fallback 独立 session（get_session RuntimeError 时）；HTTP 零变化；回滚连带形态登记 deferred-work |
| R1-6 | 防放大不完整且蓝图不可实现（validator 校验重试未封顶 9x；VFD._wrapped 是 SSD 无 _retry；frozen 整体替换/按引用恢复缺失） | P1 | 两层封顶 + 保留原 retryable_exceptions + 按引用恢复 + 组合根注入 engine 引用穿透（决策 #8 改写） |
| R1-7 | INFEASIBLE 必炸既有 4 值边界测试（test_tool_execution_values.py len==4 硬断言） | P1 | Task 1 循环 C 显式包含 4→5 值联动（先红证明断言活着）+ 文件清单/追溯矩阵登记 |
| R1-8 | ExecutionError 子类 super() 冲突（316/317 构造器调 super().__init__(reason, context=...)，新签名不透传即 TypeError） | P1 | 签名含 context/cause 透传合并 + Task 0「修改的既有异常」小节 + 子类构造回归 |
| R1-9 | 检索语义与唯一键矛盾（UNIQUE+精确匹配 ⇒ limit=5 死参数；MARKED_INFEASIBLE 空 fix_summary 注入且虚标 CASE_GUIDED） | P1 | 删 search_by_signature → get_by_natural_key；outcome 过滤；负样本提示；多案例加权 defer |
| R1-10 | ErrorCase 单值 outcome 覆盖冲掉修复配方 | P1 | recovered_count/infeasible_count 分类计数 + fix_summary 仅 RECOVERED 覆写 |
| R1-11 | 幂等结论重放不可实现（日志无 result 载荷；「装饰器重复调用」场景引擎新铸 id 不命中） | P1 | 副作用去重语义 + 可达场景界定 + RECOVERED 重放边界注记（决策 #13 新增） |
| R1-12 | 闭环内 fix-gen 失败/非触发类异常裸穿（破坏 INFEASIBLE 不抛契约） | P1 | fix-gen 失败计为该次 attempt 失败；非触发类异常中止直传 |
| R1-13 | 389 空 violations 子路径未定义（LLM 瞬时故障时 violations/stderr 双空，签名无输入） | P1 | 触发矩阵补两子路径 + 签名走 LLM 错误消息归一化 |
| R1-14 | BusinessException 误标 EXCEPTION_103（实为 2XX；103 是 StorageError） | P1 | 改 EXCEPTION_2XX + 测试断言继承关系非父类码号 |
| R1-15 | 红窗口无合入策略（Task 0→6 期间提交必挂 CI/mypy hook） | P1 | 增补「模块依赖窗口提交策略」小节（4-6 :1128 先例） |
| R1-16 | 演进日志字段集低于 failure history 基线（缺 trigger_code/duration_sec/attempt 回链） | P2 | migration 017 增列 + FixAttempt.attempt_execution_id（建表前零成本） |
| R1-17 | SANDBOX_START/infra 故障误入闭环（3 次注定失败修复 + 误标 INFEASIBLE） | P2 | 触发矩阵按 stage 维度排除 |
| R1-18 | 性能指标循环论证（mock 下"成功率"=编排正确性）+ 准确率 95%/100% 口径矛盾 | P2 | 更名「闭环机制有效性」+ 内容性断言为主 + 准确率口径统一 |
| R1-19 | 集成测试样板描述错位（4-6 实为 repo_session 事务 rollback 非 schema 隔离）+ 1.8× 容差误引 | P2 | 4 处改样板 + P95 分位断言先例改引 4-6 |
| R1-20 | 「双通道 reliable」语义误导（运行时 reliable 不发 Redis）+「8 项异常测试」失实 +「13 字段」无依据 + 文件计数错 + 决策 #11 留痕未落 Task 0 + or.md 节号错（七.7→四.7）+ 索引冗余 + 枚举术语 + B 类小项若干 | P2/P3 | 逐项修正（语义注记/全目录表述/12 核心字段口径/计数改实/Subtask 0.11/节号/索引改 last_seen_at/Enum 术语）。**R2 勘误**：复用表 ToolSchemaValidationFailed 行「13 字段」未同步（R2-13 已按源 docstring 原文口径改写）；文件计数二次修正（R2-14） |
| R2-1 | Task 0 BDD Edge Cases 触发矩阵口径六行（缺 SANDBOX_START/398 两行，且把非矩阵行 399 计入） | P1 | 改写为八行枚举 + 399 耗尽标记独立场景 + 补负样本命中场景 |
| R2-2 | AC-2 VC「不进入」枚举缺 398 行 | P2 | 补「required schema 缺失（398）」 |
| R2-3 | Task 5 循环 A 红测试矩阵枚举缺 398 行 | P2 | 补齐八行 |
| R2-4 | Subtask 8.4「重复执行零副作用」与 AC-6「案例计数递增」矛盾 | P2 | 改为 AC-6 口径（日志单行/事件单次/案例仅计数递增） |
| R2-5 | 389 路径两套 id 空间未注记（TOV 铸造 uuid4 无聚合对应；演进日志/事件 389 半边悬空回链） | P1 | AC-3 注记 + deferred-work 登记（完整回链需 ToolInputValidator 入链或 ToolResult 增 execution_id 字段）。**R7 勘误与移出**：两条设想路径均有误（ToolResult 加字段帮不到 389——抛异常不构造结果对象）；R7 实地调查定稿正确方案：链入口注入 `schema_execution_id`（4.3 预留键，TOV 零改动命中）+ 引擎聚合 id 复用——**升级纳入本 Story 实施**（决策 #16 / Task 6 循环 D，~4 行改动），deferred 关闭 |
| R2-6 | outbox fallback 测试与 rollback 隔离冲突（独立 session 写入即 commit，rollback 够不着；无清理策略） | P1 | Task 6 循环 C 定稿清理策略（不挂 repo_session + try/finally 按自建 event_id 删除）+ 隔离表例外显式声明 + 陷阱 15 |
| R2-7 | INFEASIBLE 结果化使 FAIL_FAST 策略失效（异常路径→结果路径，兄弟节点照常执行）零登记 | P1 | AC-3 DAG 策略交互注记 + 决策 #14 + deferred-work 登记。**R6 勘误**：本行机理结论漏看波次间检查 `:208-225`——FAIL_FAST 链仍中断，真实 delta 为类型丢失/cause=None/同波跑完三件工程事，R6 业界对标已定稿修复方案（决策 #14 改写 + Task 8.6） |
| R2-8 | fix_strategy 二值枚举把负样本命中虚标为 PURE_LLM（演进日志失败史不可区分） | P2 | FixStrategy 加第三值 NEGATIVE_CASE_GUIDED（决策 #15）+ 蓝图/AC-5 VC/Task 5 同步 |
| R2-9 | FixAttempt.attempt_execution_id 在 llm_generation_failed 形态（无重执行）无值可填，Task 1 不变量风险互拆 | P2 | 字段定约空串默认 + Task 1 红补边界形态用例 + 禁立 UUID 不变量 |
| R2-10 | fix-gen 非白名单异常裸穿（绕过「计为 attempt 失败」打破 INFEASIBLE 不抛契约） | P2 | fix-gen 调用点 except Exception 收敛计为该次 attempt 失败（detail 区分类型） |
| R2-11 | 两事件 execution_id 用主 id 还是 attempt id 未明示 | P2 | 定稿主 id（与演进日志幂等键同源）+ attempt 回链仅经 fix_attempts |
| R2-12 | hints 五键 per-stage 消费映射未定义（Code stage 不消费 prior_attempts 则 Reflexion 反馈在作者层断链） | P2 | Subtask 0.12 定稿映射表（Code stage 必消费 suggested_fix+prior_attempts+stderr+禁止重复指令）+ Task 6 按 stage 键集断言 |
| R2-13 | 复用表 ToolSchemaValidationFailed「13 字段」与 R1-20 台账不符 | P3 | 按源字段定义改写（自有 10 字段 + 源 docstring 自称 13 的注记） |
| R2-14 | 文件清单计数二次失实（src 12 改写成 11；deploy/configs/docs 3 改实为 2） | P3 | 计数改实 |
| R2-15 | 白名单方向性措辞（「改回生产白名单」方向反了）+ 防放大动态读前置条件未声明 + 封顶窗口并发边界 | P3 | AC-2/决策 #8 措辞统一 + 前置条件注记 + 陷阱 14 |
| R3-1 | Task 4 批集成载体含 outbox fallback 用例但修复落 Task 6——T4 入库即红破坏批次全绿 | P1 | fallback 用例明确为 Task 6 向 repositories 集成文件追加 + 提交策略节批次清单同步 |
| R3-2 | 幂等短路「仅 occurrence 递增」三方不可满足（构造期 242 崩溃/断言红/字面红——R2-4 修复自身引入） | P1 | 定谳：短路以已记录终态调 record_case（分类计数与 occurrence 同步递增），零副作用限定为不建行/不写日志/不发事件/不覆写 fix_summary；AC-6 VC/8.4/Task 5 循环 C 三处联动 |
| R3-3 | abort 中止场景构造未定义（385 单调钟竞速 CI 必抖动）+ 中止路径观测面全未定义（日志/案例/事件/重放短路） | P1 | 构造法定稿（abort 用 201/207，385 仅直传场景）+ 中止零观测副作用立法 + 重放不短路全量重跑为已知代价（ABORTED 第三值登记 deferred-work） |
| R3-4 | 事件次数断言与 fire-and-forget create_task 存在调度竞态（随机红） | P2 | BDD 约束补「断言前 drain 后台任务」（gather pending / sleep(0) 循环） |
| R3-5 | 场景全枚举缺口（fix-gen 失败/CASE_GUIDED 正样本/abort/RECOVERED 重放未列） | P2 | BDD Edge Cases 清单补列 + 单测-BDD 分工显式声明 |
| R3-6 | tool_execution_service 契约测试 EXPECTED_TAGS set 全等断言与 tags+=feedback 联动缺失 | P2 | Task 6 循环 B 红 + 文件清单同步「EXPECTED_TAGS 增补 feedback」 |
| R3-7 | 「17 个 test_arch_*」计数失实（实际 28） | P3 | 改实 |
| R3-8 | 场景级服务链重建与 RetryPolicy 零退避未显式要求（跨场景泄漏/CI 时长爆炸） | P3 | BDD 约束补两条显式要求 |
| R3-9 | fix_summary 覆写内容来源/error_category 赋值规则/构造默认值三处未定义 | P3 | Task 0 数据模型定稿（error_category 三分支映射 + fix_summary=suggested_fix 截断派生 + 默认空串） |
| R3-10 | 提交策略未覆盖 Task 7/8/9 批次 + Task 8 import 依赖未明示 | P3 | 补批次与「不得早于 Task 6」约束 |
| R3-11 | 并发 outcome 次序竞态未登记 + fallback 须直调 get_session()（经 property 得 InvalidStateError，catch 不命中） | P3 | 已知行为登记 + 实现精度注记入 Task 6 循环 C 绿 |
| R6-1 | R2-7 机理结论漏看波次间检查 `tool_chain_orchestrator.py:208-225`（FAIL_FAST and failed_nodes → raise）——「FAIL_FAST 链变为继续执行」的决策 #14 前提部分失实，实际中断语义维持（INFEASIBLE 经 `:643-644` 已计入 failed_nodes） | P1 | 业界对标（K8s PodFailurePolicy FailJob / Temporal non-retryable / SF Catch）勘误定稿：中断语义维持即业界主流立场，「业务方确认」阻碍消解；AC-3 注记/决策 #14/R2-7 台账/收敛声明×2 五处勘误改写 |
| R6-2 | 真实 delta 三件工程事：node state 二值判定抹类型（Temporal re-wrap 反模式同型）/ FAIL_FAST 异常 cause=None 可观测性降级（K8s JobFailed reason 同型缺口）/ 同波兄弟跑完算力浪费 | P1 | 前两件升级纳入本 Story 实施（新增 Task 8 Subtask 8.6 守护验证器 + 编排器两处修改入文件清单/结构树）；同波取消为可选优化维持 deferred（禁无条件——CONTINUE/SKIP 场景本就不该取消） |
| R7-1 | R2-5 deferred 的两条设想路径均有误（ToolResult 加字段帮不到 389——抛异常不构造结果对象；ToolInputValidator 入链注入的 id 仍非聚合 id）；实地调查发现正确方案：链入口注入 `schema_execution_id`（4.3 预留 extensions 键，`schema_event_helpers.py:141-146` 第一优先级零改动命中）+ 引擎聚合 id 复用（save upsert 语义支撑校验重试同 id 重入） | P1 | 决策 #16 + Task 6 新增循环 D（Subtask 6.10-6.12 四断言）+ AC-3 注记改写 + R2-5 台账勘误 + 收敛声明移出 + 文件清单/结构树登记（`tool_execution_service.py` 1 行 + 引擎 3 行）——关闭 deferred |
| R7-2 | outbox 形态②的语义分界经实地调研厘清：HTTP 路径事务语义正确（`session_middleware.py:60-68`——领域失败经 ExceptionHandlers 转响应走 commit，仅未捕获异常 rollback）；真缺陷仅后台 session_context 路径的 FAILED 持久化连带丢失；fallback 机制可复用扩展至 `_persist_execution` | P2 | Task 6 循环 C 重构行附探针动作（实施时核查后台 worker 事务边界，结论登记 deferred-work——具备则升级）；熔断项核验 ToolExecutionQuery.state 材料齐备（纯范围决策）记入 deferred 注记 |

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

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-10-08
**最后更新/Last Updated:** 2026-10-09
**更新说明/Description:**
- v1.0.0: 创建故事文件（3 并行调研 Agent 代码实证 + 4 前序故事经验整合 + 4 笔预留债清偿方案）
- v1.1.0: 文档审查 Round 1——4 调研 Agent + 3 审查 Agent（正确性/一致性 + 可行性/可达性 + 科学性/方法论对标业界）收敛 42 项（P0×5 + P1×10 + P2/P3×27）：重写 STDERR 浮现路径为生产真实形态（382 主路径）、execution_id 全链提取机制定稿、签名统一 64 hex + Sentry 对标归一化、修复循环跨尝试反馈（Reflexion 共识）、outbox fallback 独立 session 重设计、触发矩阵 8 行化、防放大两层封顶、幂等副作用去重语义等
- v1.2.0: 文档审查 Round 2 回归核查——双 Agent（传播完备性 + 修复组合交互面）收敛 16 项（P1×4 + P2×8 + P3×4）+ 2 项 R1 台账勘误：389 两套 id 空间注记、outbox fallback 测试清理策略定稿、INFEASIBLE×FAIL_FAST 行为变更登记（决策 #14）、fix_strategy 三分支（决策 #15）、FixAttempt 边界形态定约、fix-gen 异常收敛、hints per-stage 消费映射、触发矩阵衍生位补齐（八行三处）
- v1.3.0: 文档审查 Round 3 单深度推演——三轮全推演（Gherkin 场景三轴 + Task 0→9 依赖干跑/提交批次 + 六条长状态时间线）收敛 11 项（P1×3 + P2×3 + P3×5）：幂等短路 record_case 定谳（R2-4 自拆修复）、Task 4/6 批次矛盾化解、abort 观测面立法与构造法、事件断言 drain 纪律、场景全枚举补齐、EXPECTED_TAGS 联动、error_category/fix_summary 来源定稿、提交策略 7/8/9 批次补全
- v1.3.1: Round 5 独立终审——五节核验全过，周期正式收敛（零 P0/P1/P2 残留）；清偿 V4-1（决策计数 11→15 锚定）/V4-2（SSOT 表补 engine 引用 + RetryPolicy 语义消歧，AC-7 联动）+ F5-1/F5-2 两项 P3 微瑕；追加文档审查周期收敛声明
- v1.4.0: R6 业界对标修订（INFEASIBLE×FAIL_FAST）——精读编排器勘误 R2-7 机理（漏看波次检查 :208-225，中断语义本就维持且为业界主流立场：K8s PodFailurePolicy FailJob / Temporal non-retryable / Step Functions 未捕获即 fail）；真实 delta 三件中前两件（node state 类型丢失 / FAIL_FAST cause=None）升级纳入实施（新增 Task 8.6 守护验证器 + `tool_chain_orchestrator.py` 两处修改登记），同波取消优化维持 deferred；「业务方确认」阻碍经对标消解
- v1.5.0: R7 延迟项具备度复审落地——#2（389 回链）勘误 R6 前设想路径后定稿「链入口注入 schema_execution_id + 引擎聚合 id 复用」方案（发现 4.3 预留 extensions 通道 `schema_event_helpers.py:141-146` 零改动命中，~4 行改动），升级纳入实施关闭 R2-5 deferred（决策 #16 + Task 6 循环 D 四断言）；#4（outbox 形态②）实地厘清事务语义分界（HTTP 路径经 middleware 核实正确，真缺陷仅后台路径），Task 6 循环 C 附探针动作；熔断项核验查询材料齐备记入 deferred 注记

### 🏁 文档审查周期收敛声明（Round 5 独立终审，2026-10-09）

**周期概况**

Story 4-7（Validation Feedback 闭环——增强重试与不可行标记，Epic 4 收官故事）创建后进入文档审查周期，采用「多轮多视角审查 + 独立终审」结构。Round 5 独立终审以「不轻信 Story 自身记录、仓库实地取证」为纪律执行五节核验：周期闭合甄别（4 提交链 + 工作区干净 + 零游离变更 + 周期零代码触碰）、关键修复双向取证（12 项 Story 声明 vs 仓库代码逐条对照，含行号级核验）、独立新鲜快扫（零 P0/P1 新发现）、四项门禁核验（全过）、状态流转判定。**结论：周期正式收敛，零 P0/P1/P2 残留。**

**五轮结构与投入**

- R1：4 并行调研 Agent（引擎/沙箱/重试链 + 异常/端口/事件 + 前序经验/测试风格）+ 3 审查 Agent（正确性/一致性 + 可行性/可达性 + 科学性/方法论对标业界）
- R2：双 Agent 回归核查（传播完备性 + 修复组合交互面）+ 2 项 R1 台账勘误
- R3：单 Agent 深度推演（Gherkin 场景三轴 + Task 0→9 依赖干跑/提交批次 + 六条长状态时间线）
- R4：纯验证轮（零修改零提交，2 项 P3 留项交本轮）
- R5：独立终审（单终审员五节全取证）

**修复统计（终审核对口径）**

- 台账合计 46 行：R1×20 + R2×15 + R3×11，编号连续无缺
- 修复点计数：R1 42（P0×5 + P1×10 + P2/P3×27）/ R2 16（P1×4 + P2×8 + P3×4，落 15 台账行——R2-15 为复合行）/ R3 11（P1×3 + P2×3 + P3×5，行点一致）
- R4 零修复（验证轮）；R5 零新增缺陷，清偿 4 项 P3（V4-1 决策计数 11→15、V4-2 SSOT 表补 engine 引用并消歧 RetryPolicy 语义、F5-1 Last Updated 日期、F5-2 epics 行号 :1398→:1395）
- 累计：69 个修复点 + 4 项收敛清偿；R5 双向抽验 12 项全部与仓库代码实证吻合

**关键设计决策演进（审查驱动）**

1. STDERR 浮现路径从错误断言修正为生产真实形态——382(stage=EXECUTION) 主路径 / 389→383 次路径双分支，触发矩阵 8 行化（SANDBOX_START 等 infra 故障排除出闭环）（R1-1/R1-17）
2. execution_id 从全链悬空到提取机制定稿：外层 382 context 主 id 与演进日志幂等键同源；389 半边「两套 id 空间」显式登记为已知边界（R1-2/R2-5）
3. 错误签名统一 64 hex 完整 sha256 + Sentry 对标归一化（数值/引号串模板化 + 尾部锚定 stderr[-2000:]），三处口径同一（R1-3）
4. 修复循环跨尝试失败反馈（Reflexion/Self-Debugging 共识）+ 引擎 Code stage 单一代码作者（R1-4，决策 #9/#12）
5. outbox 修复重设计为 fallback 独立 session——HTTP 路径事务性原子性保持、后台 RuntimeError 分支经 session_factory 落地（R1-5，决策 #10）
6. 防放大两层封顶（引擎 + TOV 校验重试）+ RetryPolicy 按引用整体恢复 + engine 引用经组合根注入穿透（R1-6/R2-15，决策 #8；SSOT 表 v1.3.1 补登记）
7. INFEASIBLE 结果化与 ToolChain FAIL_FAST 策略交互显式登记（R2-7，决策 #14；**R6 勘误**：漏看波次检查 `:208-225`，中断语义本就维持——经业界对标 K8s PodFailurePolicy/Temporal non-retryable 定稿为正确立场，类型丢失/cause=None 两缺口升级为 Task 8.6 守护验证器随本 Story 实施，同波取消优化维持 deferred）
8. fix_strategy 三分支 CASE_GUIDED/NEGATIVE_CASE_GUIDED/PURE_LLM（R2-8，决策 #15）
9. 幂等短路 record_case 分类计数与 occurrence 同步递增定谳（R3-2，化解 R2-4 自拆）
10. abort 中止路径观测面立法：零观测副作用 + 重放不短路全量重跑 + BDD 构造法禁 385（R3-3）

**deferred 登记（dev 期落 deferred-work.md）**

编排层 INFEASIBLE×FAIL_FAST 显式联动（决策 #14。**R6 勘误与移出**：R2 机理结论漏看波次检查 `:208-225`——中断语义本就维持且符合业界主流；类型丢失/cause=None 两缺口经对标定稿后**升级纳入本 Story 实施**（Task 8.6），本 deferred 项仅余同波取消可选优化）；389 半边 aggregate 完整回链（**R7 移出**：调查勘误 R6 前设想路径，定稿「链入口注入 schema_execution_id + 引擎复用」方案——决策 #16 / Task 6 循环 D 升级纳入本 Story 实施，deferred 关闭）；中止遥测 ABORTED 第三值；outbox 后台路径「业务 session 异常回滚连带丢失」形态②（**R7 探针**：HTTP 路径事务语义已核实正确，真缺陷仅后台路径；Task 6 循环 C 附探针动作——fallback 机制可复用扩展至 _persist_execution，结论随实施登记）；多案例加权检索与向量相似检索（L3 Qdrant）；工具熔断（or.md 四.7.(3)，建议挂 5.x——R7 核验 ToolExecutionQuery.state 过滤材料齐备，纯范围决策）；自动灰度推进与 per-version 统计视图；真实修复能力观察基准（不进 CI 门禁）；400-409 扩域触发条件注释更新（Task 2 既定动作）。

**最终状态**

- 周期状态：**收敛（CONVERGED）**——零 P0/P1/P2 残留，4 项 P3 随本提交清偿
- Story 状态：`ready-for-dev` 保持不变（文档审查周期不改里程碑状态）
- 下一步：运行 `dev-story` 进入实施（10 Task / SDD+TDD 融合 / 预留债 4 笔集中清偿）
