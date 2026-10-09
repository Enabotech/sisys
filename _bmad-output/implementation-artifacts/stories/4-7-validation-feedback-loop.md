# Story 4.7: Validation Feedback 闭环（增强重试与不可行标记）

**Status:** `review`

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
**Then** 触发增强反馈循环，每次增强尝试依次执行：提取 STDERR/签名 → 查询错误案例库 → LLM 生成**修复建议（suggested_fix 策略/代码草案）** → 经 `context.extensions["validation_feedback_hints"]` 注入（P0-D 模式先例）重执行内层链——**引擎 Code stage 是唯一代码产出作者**（R8-5 精确化：fix-gen 产出建议草案而非最终代码；prompt 指令「优先采纳 hints.suggested_fix，仅做必要适配」）——「建议者+作者」两级结构的归因局限（attempt 失败无法区分 fix-gen 方案错误与引擎适配偏差）显式接受并写入决策 #9 依据
**And** 修复 prompt **必须携带跨尝试失败反馈**（Reflexion/Self-Debugging 共识——**动作+结果成对反馈**（R8-1）：attempt k 的 prompt 含 attempt 1..k-1 的 stderr_excerpt/detail/**suggested_fix_excerpt（前次采纳的修复方案摘要——「禁止重复失败方案」指令必须有指涉对象，仅传失败现象不传失败动作则防重复在信息上不成立）**与「以下方案已失败，禁止重复」指令；`FixAttempt.suggested_fix_excerpt` 字段承载），否则 attempt 2/3 与 attempt 1 独立同分布，确定性采样下重复生成相同失败修复
**And** 增强尝试总数 **3 次**（attempt 1..3，`RetryPolicy.max_attempts=3` 总尝试语义——非"3 次重试+1 次首试"）
**And** 防重试放大：增强期间内层重试全部封顶——引擎 `_retry` **与** `ToolOutputValidator` 的校验重试（`retry_policy_for_validation` 经 `effective_retry_policy` 动态读引擎策略，`tool_output_validator.py:105`——**前置条件**：TOV 构造未显式注入 `retry_policy`（`or` 短路才走动态读；生产装配 `composition_root.py` 装配成立，防放大测试须同时断言该构造形态））同为 `max_attempts=1`；实现上（**CR-R1-3 定稿：ContextVar per-task 覆盖形态**——旧「保存引擎原引用→整体替换→finally 按引用恢复」在进程级共享引擎上存在交错恢复致 `max_attempts` 永久=1 的竞态（`clear_scoped` 生产未接线），且封顶构造丢失 backoff/duration 配置）`ValidationFeedbackService` 以 `dataclasses.replace(engine._retry, max_attempts=1)` 派生封顶策略（**保留全部字段**——retryable_exceptions/backoff/duration；派生必须 replace 自引擎原策略、禁默认对象/禁硬编码白名单——默认 `RetryPolicy` 含 `ExecutionError`(313) 会静默偏离生产白名单）经 `retry_policy_override` 上下文管理器按 task 覆盖——共享引擎状态零写入、并发 recover 互不污染，with 退出自动还原
**And** 修复成功则返回 `ToolResult(status=SUCCESS, retry_count=增强尝试次数)`。

**验证标准/Validation Criteria:**
- [ ] 触发条件判定（九行矩阵，R8-4 升级）：仅 389（OUTPUT 校验耗尽，含 Schema 违规与 LLM 瞬时故障两子路径）与 382 且 `stage="EXECUTION"` **且 cause ∈ ExecutionError 族（313/316/317——沙箱执行内代码缺陷，修复可归因；**族成员=ExecutionError 子类（R12-F1 校正：318 SandboxQuotaExceededError 继承 SandboxError 非族成员，归 SSD 守卫直传——见 mid-attempt 立法 312/318/319）**）**进入闭环；**382 且 `stage="EXECUTION"` 且 cause ∉ ExecutionError 族**（引擎兜底 `except Exception` 宽捕获的混入形态：`LLMConfigError`(332)/`NetworkError`(102)/`StorageError`(103)/引擎自身解析 bug 等裸异常——**基础设施/配置类故障非代码缺陷**，与 SANDBOX_START 排除同理，修复不可归因且误标 INFEASIBLE）、382 且 `stage="SANDBOX_START"`（312/315 沙箱启动失败）、`ToolExecutionTimeoutError`（385）、策略违规（207）、标记语法错误（201）、数据源族（410-413）、required schema 缺失（398——4.3 定义 4.7 消费）**不进入**闭环直接上抛。**机理注记（R8-4）**：引擎兜底 `tool_execution_engine.py:253-266` 是宽捕获——除五族直传组（207/201/410-413/101/302）外的一切异常（含 332 配置类）都被无差别包为 `382(stage="EXECUTION")`，分类边界由 cause 链根因而非 stage 字段决定，故触发判定必须做 cause 族过滤（实测实证：`LLMConfigError(ExternalException)` 不在直传组 `ConfigurationError(SystemException)` 分支）
- [ ] 修复 prompt 组装：STDERR + 案例查询结果（命中 RECOVERED 案例时注入 fix_summary）+ schema violations（若有）+ **前次增强尝试失败反馈（attempt 1..k-1 的 stderr_excerpt/detail/suggested_fix_excerpt——动作+结果成对，R8-1）** + 禁止重复失败方案指令；不含"原 Code 产物"依赖（引擎按 hints 重新生成，见 Then）
- [ ] hints payload 契约（Task 0 定稿 schema）：`{stderr_excerpt, schema_violations, case_summaries, prior_attempts, suggested_fix}`；`tool_execution_engine.py` `_think_stage`/`_code_stage` prompt 构建读取 `validation_feedback_hints` 扩展键（引擎 `__init__` 签名不变——4.4 AC-7.4 BDD 断言保护）
- [ ] 防放大（CR-R1-3 ContextVar 形态）：增强期间引擎与 validator 两层重试均封顶 1（窗口内 `effective_retry_policy` 读到 max_attempts=1，含 retryable_exceptions 保持断言）；`engine._retry` 全程零写入（并发 recover 结束后 `engine._retry is 原对象`——并发回归断言）
- [ ] 修复生成自身失败：fix-gen 调用包 `_call_with_retry(max_attempts=1)`，LLMAPIError/LLMResponseError 经重试语义耗尽**计为该次增强尝试失败**（`FixAttempt.detail="llm_generation_failed"`）；**fix-gen 调用点以 `except Exception` 收敛**（非白名单异常如响应构造缺陷同样计为该次 attempt 失败，detail 区分类型——防裸穿打破 INFEASIBLE 不抛契约）；增强尝试中内层浮出异常应用**与触发面同构的入环谓词（R9-13 对称立法）**——mid-attempt 异常分类定稿：①浮出 389 / 382-EXECUTION 且 cause∈ExecutionError 族 = **计为该次 attempt 失败**（`FixAttempt.detail="retry_failed"`——提取该次 stderr/violations 填 FixAttempt，进入下一 attempt）；②浮出**任何不满足入环谓词的异常**（385/207/**201**/410-413/398/**382-EXECUTION 且 cause∉族（mid-attempt infra/配置故障——触发前被 cause 过滤直传、闭环内同样不可标 INFEASIBLE）/382-SANDBOX_START/SSD 守卫异常（312/318/319）/101/302）= **中止闭环直传**（语义优先级高于闭环——与触发面九行判定完全对称，防 infra 故障经 attempt 侧门误标不可行）；**LLM 持续故障直传规则（R8-6/决策 #17，R9-15 根因导向修订，R10-2 谓词定稿）**：3 次 attempt 全部失败**且各次失败根因均为 LLM 瞬时**（fix-gen `detail="llm_generation_failed"`，或重执行 `detail="retry_failed"` 且失败异常链 389←383←`last_exc` 中 `last_exc ∈ {LLMAPIError, LLMResponseError, TimeoutError}`——**谓词类型集 = 引擎生产可重试白名单同集（R10-2 定稿：LLM 网络超时属「LLM 瞬时」语义域，排除 TimeoutError 会使 LLM 超时持续故障耗尽误标 INFEASIBLE——#17 要防的污染原样发生）；BDD 直传场景 LLMAPIError/TimeoutError 两类型各构造一种**——LLM API 持续不可用期间两种失败形态同源同频，仅锚定 fix-gen 失败会漏掉约半数目标形态）时**直传原触发异常不标 INFEASIBLE 不写演进日志终态**（外部瞬时故障不可归因为任务不可行，误标 INFEASIBLE 会永久污染负样本库）；**零终态路径重放语义（R9-17 显式化）**：中止与 #17② 直传两条零终态路径重放均不命中幂等短路 → 全量重跑——对 LLM 瞬时故障这是**期望行为而非代价**（LLM 恢复后重放应重试而非返回缓存结论）；成功恢复且 `error_category=LLM_TRANSIENT` 时**不覆写 fix_summary**（恢复归因于退避自愈而非修复方案，防伪配方污染案例库，决策 #17）。**中止路径观测面立法（R3-3）**：中止 = 零观测副作用（不写演进日志——AC-4 Given「闭环结束」不含中止且 final_status 无第三值；不回填案例；不发事件；已耗 attempt 遥测随无日志丢弃）；**连锁语义**：中止后同 trigger_error 重放**不命中幂等短路**（短路依赖已有终态日志）→ 重放全量重跑（LLM 配额放大为已知代价，完整中止遥测需 final_status 第三值 ABORTED——登记 deferred-work）；abort 场景 BDD 构造法 = attempt-k 的 LLM code mock 返回含裸 `$`（201 浮出）或注入 resolver（207）——385 同 RetryPolicy 下需单调钟竞速（首执行 <cap 触发 382、重执行 >cap 浮出 385）CI 必抖动，**385 仅用于直传场景构造**（引擎 `RetryPolicy(max_total_duration_sec≈0)`）
- [ ] 单元测试：触发判定矩阵（含 SANDBOX_START 排除行）/ hint 注入透传 / 防放大恢复 / 跨尝试反馈注入 / 修复生成失败处置 / 成功恢复路径

### AC-3: 不可行标记与领域事件

**Given** 3 次增强重试均失败
**When** 反馈循环耗尽
**Then** 标记任务不可行：返回 `ToolResult(status=INFEASIBLE)`（`ToolResultStatus` 新增枚举值，additive 向后兼容），`output` 携带失败摘要（error_signature/最终 STDERR 摘要/尝试次数）
**And** 发布 `ToolExecutionMarkedInfeasible` 领域事件（配置双登记 reliable——运行时仅 outbox 路径，见 AC-6 语义注记），写入演进日志 `final_status=MARKED_INFEASIBLE`
**And** 闭环内部以 `ValidationFeedbackRetryExhaustedError`（EXCEPTION_399，**4.1b/4.3 两度预留的编码**）作为耗尽信号，由装饰器捕获并转换为 INFEASIBLE 结果（对外不抛异常——ToolChain DAG 编排按 `status` 分支感知，避免中断后续节点（**策略限定（R8-11）**：CONTINUE_ON_ERROR/SKIP_DOWNSTREAM 不中断，FAIL_FAST 仍中断——见下注记与决策 #14）；**DAG 策略交互注记（R2 发现，R6 业界对标勘误与定稿）**：INFEASIBLE 经结果路径计入 `failed_nodes`（`tool_chain_orchestrator.py:643-644`，`!= "success"` 判定）后，**FAIL_FAST 链仍会中断**——波次间检查 `:208-225`（`FAIL_FAST and failed_nodes` → raise）兜底，与业界主流一致（永久性失败 × 显式 fail-fast = 中断：K8s PodFailurePolicy FailJob / Temporal non-retryable / Step Functions 未捕获即 fail）；SKIP_DOWNSTREAM 沿 failed_nodes 自动兼容（下游 SKIPPED）、CONTINUE_ON_ERROR 落 COMPLETED_WITH_ERRORS——三策略语义均正确。真实 delta 为三件工程事（随本 Story 修复，**落点 = Task 6 TDD 循环 E（红绿一体实施，R8-8 迁移）+ Task 8.6 纯守护断言（验证而非实施）**）：①**类型丢失**——`:637` node state 二值 `"FAILED"` 抹掉「不可行」与「故障」区分（Temporal「catch 后 re-wrap 丢失 non-retryable 元数据」同型反模式），修复 = `NodeRunStatus.state`（**定义于 `src/domain/entities/tool_chain_run.py:86` 的 str Literal 非 Enum**，R8-7 补登记——Literal 加 `"INFEASIBLE"` + docstring 同步，additive）支持三值；②**cause=None**——`:218-224` FAIL_FAST 异常构造无法恢复原始异常，修复 = 从 `completed_node_results[failed_node_id].output` 取 `error_signature`/尝试次数填充异常 context（K8s JobFailed condition 带 reason 同型，KEP-4443；**修改面 R8-7 补登记：`ToolChainExecutionFailedError` 构造器（`tool_chain_exceptions.py:120-129`）现有 7 参数无 error_signature/尝试次数据位，需扩可选参数并同步 context 构建——异常契约面变更，`sisys-uni-exception-design.md` 两表联动核对**）；③**同波兄弟跑完**（旧异常路径会取消同波）——FAIL_FAST 策略下首个结果失败主动 cancel 同波剩余任务为**可选优化**（纯算力节约，deferred 登记；CONTINUE/SKIP 场景本就不该取消，禁做成无条件）。**策略判定边界注记（R8-15）**：波次间检查 `:209` 仅判定 **DAG 级** `dag.failure_strategy`——节点级 `failure_strategy=FAIL_FAST` 覆盖而 DAG 级为 CONTINUE/SKIP 时，结果化失败（无异常）不触发波次间 raise 也不触发异常路径（`_execute_wave` per-node 检查仅在异常抛出时到达），链继续执行（编排器既有语义，非本 Story 修改面，登记为已知行为）
**And** 修复成功路径发布 `ToolExecutionRecovered` 领域事件（配置双登记 reliable——运行时仅 outbox 路径，见 AC-6 语义注记）。**两事件 execution_id 定稿 = 主 id**（`trigger_error.context["execution_id"]`——与演进日志幂等键同源；attempt 级引擎事件回链仅经 `fix_attempts.attempt_execution_id`）。**389 子路径 id 同源修复（R2 发现悬空，R7 定稿方案）**：389 的 execution_id 原为 TOV 内 `extract_schema_execution_id(context) or uuid4()` 铸造（`tool_output_validator.py:111`）——生产链无人设置该键时与 ToolExecution 聚合行无对应（「两套 id 空间」，4.1b DataSourceFetchFailed 断链同构）。**修复设计（决策 #16，Task 6 循环 D 实施）**：链入口 `ToolExecutionService.execute`（`tool_execution_service.py:64`，装饰链之外）注入 `context.with_extension("schema_execution_id", uuid.uuid4())`（**条件注入形态（R8-16）**：`if "schema_execution_id" not in context.extensions:` 才注入——无条件覆盖会在未来 `ToolInputValidator` 入链时（TIV 同键 extract→注入先例）使 INPUT 事件 id 与 OUTPUT/聚合 id 分裂，倒退 4.3 P0-F 一致性；当前生产 TIV 未装配无实冲突，条件形态零成本防患）（1 行，沿用 TOV 已读的键名——`schema_event_helpers.py:141-146` 第一优先级）+ 引擎 `:137-138` 聚合 id 改为优先读该键（3 行，无则新铸）+ TOV 零改动自动命中——**聚合 id = 382/389 context id = 演进日志幂等键 = 两事件 id 全链同源**；引擎 `_persist_execution` 用 save（upsert 语义），校验重试多次 execute 同 id 重入无乐观锁冲突（聚合行覆盖为最新次，与 execution_id 幂等语义一致）

**验证标准/Validation Criteria:**
- [ ] `ToolResultStatus.INFEASIBLE = "infeasible"` 新增（`(str, Enum)` 加值 additive）；既有语义注释保持（INVALID 语义不变——`value_objects/tool_execution.py:247-249` 注释契约保持）；**既有 4 值边界断言联动**：`tests/unit/domain/value_objects/test_tool_execution_values.py:114-121` 的 `len(statuses)==4`/全值 set 断言与 `tool_execution.py:30` 枚举 docstring「4 值边界」须同步更新为 5 值（Task 1 循环 C 显式包含）
- [ ] `ValidationFeedbackRetryExhaustedError`：code=`EXCEPTION_399`、继承 `BusinessException`、构造器携带 `execution_id`/`tool_id`/`enhanced_retry_count`/`error_signature` context（execution_id 取自 trigger_error.context——见 AC-1/AC-6 提取机制）
- [ ] `ToolExecutionState` 6 状态机**不动**（FAILED 终态语义不变，增强重试按"终态反向迁移禁止（重试创建新 attempt）"既有注释语义创建新执行）
- [ ] 两事件字段与 `DomainEvent` 基类 12 核心字段（`base.py:20-35` `_CORE_FIELD_NAMES`）对齐 + 各自自有字段（MarkedInfeasible 8 个 / Recovered 7 个）+ tenant_id baseline（4-5 R1-F01 教训：metadata 字段一律 `str()` 化防 json 序列化失败）
- [ ] INFEASIBLE 结果不抛异常、不发布 ToolExecuted 成功事件
- [ ] **LLM 持续故障例外（决策 #17，R8-6；R12-F2 谓词对齐 R9-15 根因导向）**：3 attempt 全部失败**且各次失败根因均为 LLM 瞬时**（fix-gen `llm_generation_failed` 或重执行 `retry_failed` 且 389←383←last_exc∈{LLMAPIError, LLMResponseError, TimeoutError}——AC-2 VC 谓词同款）→ 直传原 389/382 触发异常，**不**返回 INFEASIBLE、**不**写 MARKED_INFEASIBLE 演进日志、**不**回填 infeasible_count（外部瞬时故障≠任务不可行）
- [ ] **INFEASIBLE×FAIL_FAST 守护断言面（Task 8.6 验证项，R8-13）**：Task 6 循环 E 交付物（node state 三值判定 / FAIL_FAST 异常 context 含 error_signature 与尝试次数 / SKIP_DOWNSTREAM 下游 SKIPPED）经架构测试守护——见 Task 8 Subtask 8.6 三断言

### AC-4: 演进日志与持久化可靠性

**Given** 反馈闭环结束（无论恢复或标记不可行）
**When** 写入演进日志
**Then** `EvolutionLogEntry` 聚合根落库（PG migration 017），记录 execution_id / tool_id / **trigger_code（389|382——失败模式第一维分类，AIOps failure history 基线字段）** / error_signature / enhanced_retry_count / fix_attempts 摘要（含每次 attempt_execution_id 回链） / **duration_sec（闭环时长——口径定稿 R8-21：从 `recover()` 进入到终态返回的墙钟时间，含 fix-gen 与重执行时长；不含基础重试阶段耗时，严格 MTTR 需叠加基础层 3×3 次重试耗时；与 AC-7 P95「闭环自身开销」为**两个口径**——P95 排除 LLM/沙箱用于开销门禁，duration_sec 全含用于恢复时长观测）** / final_status（RECOVERED | MARKED_INFEASIBLE）
**And** 失败历史可追溯：按 `tool_id` 查询该工具全部反馈历史（`EvolutionLogQuery` Query Object，多字段+分页），按 `execution_id` 精确定位单次记录
**And** 清偿 defer 债：**outbox 后台路径独立 session 修复**（`tool_execution_engine.py:282-284` 与 `data_source_resolver.py:352` 注释显式 defer 本 Story）——设计采用 **fallback 独立 session**：`PostgreSQLOutboxRepository.save` 优先 `get_session()`（HTTP 路径复用请求 session，保持事务性 outbox 原子性——业务状态与事件发布同事务 commit/rollback），捕获 `RuntimeError`（后台/CLI 路径无请求 session——现状事件静默丢失的根因）时经注入的 `session_factory` 走 `session_context` 独立写入（`outbox_processor.py:146-155` 先例同款）。

**验证标准/Validation Criteria:**
- [ ] `EvolutionLogEntry` 不变量：`enhanced_retry_count ∈ [1,3]`、`final_status` 为枚举、`trigger_code ∈ {"EXCEPTION_389","EXCEPTION_382"}`、UUID 有效、timezone-aware
- [ ] 按 execution_id 幂等 upsert（同 execution 重复写入不产生重复行）
- [ ] `EvolutionLogQuery`（frozen dataclass：tool_id/tenant_id/execution_id 可选 + limit/offset）走 Query Object 决策规则（多字段组合+分页）
- [ ] outbox 修复回归断言：**后台/CLI 路径**（无请求 session——`get_session()` 抛 RuntimeError 场景）reliable 事件经 fallback 独立 session 成功落库（现状该场景事件 100% 静默丢失）；**正常 HTTP 路径行为零变化**（仍走请求 session 同事务，事务性原子性保持）
- [ ] 后台路径中「业务 session 异常回滚连带丢失已 flush 事件」形态（session_context rollback 连带）为**遗留债**：完整修复需后台路径会话策略重构，超出本 Story 范围——defer 注释清偿时显式登记 `deferred-work.md`（R8-28 口径对齐：R7 探针若结论为「具备」——fallback 机制可复用扩展至 `_persist_execution`——则按探针结论升级处置，见 Task 6 循环 C 重构行）
- [ ] 集成测试覆盖双查询面（list_by_tool / get_by_execution）

### AC-5: 错误案例库（查询辅助 + 案例回填 + 幂等）

**Given** 反馈循环执行中
**When** 每次增强尝试前
**Then** 按 `(tenant_id, tool_id, error_signature)` **精确查询**错误案例库（V1 语义诚实化：自然键 UNIQUE 下精确匹配至多命中 1 行，即"精确查表"而非多案例检索——`get_by_natural_key` 即查询面），命中且 `outcome=RECOVERED` 且 `fix_summary` 非空时注入修复 prompt（or.md error_db.search 蓝图的 V1 落地形态）；命中 `MARKED_INFEASIBLE` 案例时注入**负样本提示**（"此签名已观测到 N 次不可行"——ExpeL 失败经验模式，infeasible_count 支撑；N 为观测计数语义（含重放递增，R9-18 口径校准）；**V1 不缩减尝试（R8-2 定稿）**——命中不可行案例仍全量 3 次 attempt：保证 infeasible 统计口径一致 + 避免 attempt 上限参数 K 的调参成本，缩减优化登记 deferred-work）。**fix_strategy 判定规则正文定稿（R9-16 补格——含原三分支 + 两个边界格全枚举）**：①命中 ∧ `outcome=RECOVERED` ∧ `fix_summary` 非空 → CASE_GUIDED（注入 fix_summary）；②命中 ∧ `outcome=MARKED_INFEASIBLE` ∧ **`error_category` 与本次触发分类匹配（R8-18 二次过滤升为判定前置——over-merging 签名碰撞时防跨根因误伤）** → NEGATIVE_CASE_GUIDED（注入负样本提示）；③无命中 → PURE_LLM；④**命中 ∧ RECOVERED ∧ `fix_summary` 为空**（LLM_TRANSIENT 首例——#17① 不覆写 + 构造默认空串，R9-16 格 1）→ **PURE_LLM + 注记「命中但无可注入配方」**（跳过注入；fix_strategy 语义 = 本次修复的指导来源，无可注入配方即纯 LLM——禁虚标 CASE_GUIDED）；⑤**命中 ∧ MARKED_INFEASIBLE ∧ category 不匹配**（签名碰撞形态，R9-16 格 2）→ **PURE_LLM + 注记「碰撞命中已抑制」**（负样本提示不注入——不同根因不共享失败经验）。`error_category` 列为**首写定格**（自然键行首次创建时确定，后续触发不改写——category 二次过滤的成立前提；碰撞共享行的 category 以首写为准）
**And** 闭环结束时回填案例：恢复成功回填 `recovered_count += 1` 并**覆写 fix_summary**（仅 RECOVERED 路径覆写且**仅 error_category ∈ {SCHEMA_VIOLATION, 沙箱 error_code} 时**——保留**最近一次成功**修复（R8-20 措辞诚实化：recency ≠ best，V1 无成功率比较机制，「最佳」为虚称；进阶聚合登记 deferred），防不可行写回冲掉修复配方；**LLM_TRANSIENT 类成功不覆写（决策 #17，R8-6）**——恢复归因于退避自愈而非修复方案，覆写会沉淀伪配方污染 CASE_GUIDED 注入面）；标记不可行回填 `infeasible_count += 1`（fix_summary 不动）
**And** 案例写入幂等：同 `(tenant_id, tool_id, error_signature)` 重复记录 `occurrence_count += 1`（= recovered_count + infeasible_count 合计）并刷新 `last_seen_at`，不产生重复行。

**验证标准/Validation Criteria:**
- [ ] `ErrorCase` 聚合根 + `ErrorCaseRepositoryPort`（get_by_natural_key 精确查询 / record_case upsert——单字段检索与命令型操作直接参数，CLAUDE.md 端口参数决策规则；**不设 search_by_signature**——V1 精确匹配下与 get_by_natural_key 语义重复，多案例加权检索登记 deferred-work）
- [ ] `ErrorSignatureExtractor` 领域服务（纯函数）：STDERR 归一化（剥离路径/行号/时间戳/内存地址 + **数值→`<N>`、引号串→`<S>` 模板化**——Sentry message templating 对标，防 `KeyError: 'x'` 类消息内插值分裂签名）→ **完整 sha256 hexdigest（64 hex）**；签名计算取**尾部锚定摘录 `stderr[-2000:]`**（traceback 根因行在末尾，头部截断会切掉根因致错误合并；事件/prompt 展示仍可头部截断）；schema violations 路径归一化签名（**规则完备化 R8-19**：排序去序 + **path 数组索引→`<I>` 模板化**（`$.output[3].value` 与 `$.output[5].value` 同根因——jsonschema violation 的 path 索引随 LLM 输出结构漂移，不模板化则同根因分裂多行破坏幂等前提）+ message 应用同套 `<N>/<S>` 模板化）——同根因不同表层输出收敛为同一签名（幂等前提）。**已知边界登记（R8-18/R8-30）**：①over-merging——`<S>` 抹平引号内类型名/键名，`TypeError: ... 'int' and 'str'` 与 `'int' and 'list'` 收敛同签名（Sentry grouping 官方承认的同款风险；缓解 = 案例命中按 `error_category` 二次过滤——ErrorCase 表 category 与 signature 并存，查询侧先签名后 category 核对）；②stderr 含 dict/set repr 时键序不稳定、异常链（PEP 3134）中间包装层数漂移可致签名分裂——低频形态，V1 不处理登记为已知边界（deferred 随真实语料评估）
- [ ] V1 查询语义：精确签名匹配（确定性可测）；向量相似检索（L3 Qdrant）与多案例加权检索（签名前缀粗化分组 + occurrence_count DESC——依赖完整摘要保留的前缀派生能力）为非目标并登记 deferred-work
- [ ] 并发 upsert 冲突容错（4-6 CR1-4 教训：UNIQUE 冲突后 PendingRollback 需 `begin_nested()` SAVEPOINT 包裹重读）
- [ ] 案例查询无命中时闭环仍可运行（纯 LLM 修复，`fix_strategy=PURE_LLM`）；命中不可行案例时 `fix_strategy=NEGATIVE_CASE_GUIDED`（决策 #15 三分支——二值会把负样本命中虚标为 PURE_LLM，演进日志失败史不可区分）

### AC-6: 幂等性与事件通道补全

**Given** 同一触发异常重复进入反馈闭环（**可达场景界定**：`recover()` 被以同一 `trigger_error`（同 execution_id）重复调用——事件消费侧重放/上游补偿重试形态；注意装饰器层重复调用不命中幂等键——**机制锚点 R8-12 更新（决策 #16 后）**：id 铸造主责移至链入口 `ToolExecutionService.execute` 每次调用注入新 `schema_execution_id`（引擎 `:137-138` 无注入时兜底新铸），装饰器层每次重执行都是新 id，此为架构边界非缺陷）
**When** 闭环各副作用执行
**Then** **副作用去重语义**：演进日志按 execution_id 幂等 upsert（AC-4）、案例库按自然键幂等计数（AC-5）、`ToolExecutionMarkedInfeasible`/`ToolExecutionRecovered` 事件不重复发布（同 execution 终态判定短路）；短路路径返回合成结论——INFEASIBLE 语义完整（output 即失败摘要，日志行可支撑；**不对称登记（R9-18）**：INFEASIBLE 重放不加 `replayed` 标记为刻意设计——INFEASIBLE 无 `validate_complete()` 证据包契约（386 仅约束 SUCCESS）、DAG 按 status 分支不消费 output 细节、重放摘要与原次 output 字段同形语义等价，可辨识性无消费方；RECOVERED 加标记因 SUCCESS 有证据包契约与下游校验交互，可辨识性有真实消费方）；RECOVERED 重放返回合成 SUCCESS 摘要（**可辨识标记（R8-3）**：合成结果 output 携带 `"replayed": true` 元数据键——与真实成功下游可区分（Temporal replay 逐字节等价 / HTTP Idempotency-Key Replayed 标识的共识：重放结果要么等价要么可辨识）；**双重边界注记**：①原成功 ToolResult 的完整 output/evidence_package 不在演进日志中，重放结果不含证据包——下游需证据时应重新执行而非依赖重放；②合成 SUCCESS 无 evidence_package，下游调用 `ToolResult.validate_complete()`（`tool_execution.py:261-274`——SUCCESS 必含证据包契约，4.3 立法（R12-F3 锚点校准））将抛 `EvidenceValidationFailedError`(386)——重放语义为**摘要性结论**，不承诺通过完整性校验，消费方按 `replayed` 标记先行分支）
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
**And** 性能达标（epics 硬指标可测化口径，Task 0 与业务方确认留痕）：闭环自身开销（错误签名提取 + 案例查询 + 演进日志写入，**不含** LLM 修复生成与沙箱执行时长——二者受 `LLMConfig.timeout`/沙箱 timeout 支配）单次 **P95 < 5s**（`statistics.quantiles(n=20)[18]` 分位 + 分级断言：达标 assert / 环境不达标 skip 留测量证据——4-6 `test_tool_version_integration.py:398-415` 先例；计时手法 = 端口级计时代理包裹仓储 + LLM/Sandbox AsyncMock `await asyncio.sleep(0)` 真实挂起点）；**闭环机制有效性**（mock LLM 可编程修复序列前提——指标语义注记：mock 化下度量的是编排机制正确性而非真实修复能力，真实修复能力观察基准不进 CI 门禁并登记 deferred-work）：增强重试恢复机制成功率 **≥80%**（20 次可修复故障注入 ≥16 恢复，主断言为内容性断言：修复 prompt 含 stderr/案例 fix_summary/历史反馈、hints 注入透传）；不可行标记机制准确率 **20 次不可修复故障全部标记 + 可修复故障 0 误标**（样本规模下等效 100%；epics 字面 ≥95% 为下限口径，20 样本粒度无法区分 95%/100%）。**统计口径注记（R8-31/R8-32）**：mock 可编程序列下成功率/准确率由测试脚本设定（≥80% 阈值实为编排覆盖计数非随机样本统计）；真实观测时 n=20、p̂=0.8 的 Wilson 95% CI ≈ [0.58, 0.94]——真实修复能力观测（deferred）需更大样本或序贯设计，且**按 fix_strategy 分组统计恢复率**作 NEGATIVE_CASE_GUIDED 负样本提示效用的对照基线（提示对 LLM 行为的实际影响——合理吓阻 vs 反向暗示——无对照则机制有效性不可评估）。

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
- [ ] `ErrorCase` 聚合根（`src/domain/entities/error_case.py`）：`case_id`/`tenant_id`/`tool_id`/`error_signature`(**64 hex 完整 sha256 hexdigest**——与签名提取器/列宽三者同一口径)/`error_category`（**赋值规则定稿（R3-9）**：389-Schema 路径=「SCHEMA_VIOLATION」/389-LLM 瞬时=「LLM_TRANSIENT」/382-EXECUTION=沙箱 error_code（cause 链首个 ExecutionError 族 code，如 EXCEPTION_313/316/317）——取自 trigger_code + cause 链推导）/`stderr_excerpt`(≤2000)/`fix_summary`(≤2000，**仅 RECOVERED 路径覆写且仅非 LLM_TRANSIENT 类**（决策 #17，R8-6）；**覆写内容来源定稿（R3-9）**：成功 attempt 的 suggested_fix（fix-gen 产出原文截断 ≤2000）+ 该次错误摘要一句——由服务层派生；V1 语义为「最近一次成功修复」（R8-20，非「最佳」——无成功率比较机制）；构造器默认空串与 migration DEFAULT '' 对齐)/`outcome`(最近一次：RECOVERED|MARKED_INFEASIBLE)/`recovered_count`(≥0)/`infeasible_count`(≥0)/`occurrence_count`(=recovered+infeasible 合计，≥1)/`last_seen_at`/`created_at`；自然键 `(tenant_id, tool_id, error_signature)`——计数拆分防不可行写回冲掉修复配方；**并发 outcome 次序（R3-11）**：同签名 RECOVERED×INFEASIBLE 并发回填时 outcome 终值取决于提交次序（有界竞态，分类计数守恒不受影响）——登记为已知行为
- [ ] `EvolutionLogEntry` 聚合根（`src/domain/entities/evolution_log_entry.py`）：`log_id`/`tenant_id`/`tool_id`/`execution_id`/`tool_version`/`trigger_code`(EXCEPTION_389|EXCEPTION_382)/`error_signature`/`enhanced_retry_count`(1-3)/`fix_attempts: tuple[FixAttempt, ...]`/`duration_sec`/`final_status`(RECOVERED|MARKED_INFEASIBLE)/`created_at`
- [ ] `FixAttempt` 值对象（`src/domain/value_objects/validation_feedback.py`）：`attempt_no`(1-based)/`attempt_execution_id: str = ""`（该次重执行的 execution id——入口注入或引擎兜底新铸（R8-26 措辞对齐决策 #16），回链增强期间事件；**空串=未发生重执行的合法形态**（如 fix-gen 失败计 attempt 的 `llm_generation_failed` 形态），Task 1 不变量禁立「UUID 有效」于该字段——R2 组合发现）/`error_signature`/`fix_strategy`(CASE_GUIDED|NEGATIVE_CASE_GUIDED|PURE_LLM 三分——决策 #15)/`stderr_excerpt: str = ""`/**`suggested_fix_excerpt: str = ""`（R8-1 新增：该次采纳的修复方案摘要，截断 ≤2000——跨尝试反馈通道的动作半边，「禁止重复失败方案」指令的指涉对象；空串=fix-gen 未产出（llm_generation_failed 形态）合法）**/`succeeded`/`detail`
- [ ] `ToolResultStatus.INFEASIBLE` 新增枚举值（`(str, Enum)` 加值 additive；`INVALID`"可重试"语义契约不变；既有 4 值边界断言与 docstring 同步 5 值——AC-3 VC）
- [ ] `ErrorSignatureExtractor` 领域服务（`src/domain/services/error_signature_extractor.py`）：纯函数，STDERR 归一化签名（剥路径/行号/时间戳/内存地址 + 数值→`<N>`/引号串→`<S>` 模板化 + 尾部锚定 `stderr[-2000:]` 参与哈希）+ violations 归一化签名（**排序去序 + path 数组索引→`<I>` + message 同套 `<N>/<S>` 模板化——R8-19**）——均输出 64 hex
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
| `validation_feedback_service` | application | `ValidationFeedbackServicePort`（`src/application/ports/validation_feedback_service.py`，方法 `recover(...)`） | lambda 工厂注入 llm_client + error_case_repository + evolution_log_repository + event_publisher + **双句柄（R9-14 定稿；CR-R1-3 修订 engine 句柄用途）**：①**engine 引用**（`resolver.resolve("tool_execution_engine")`——防放大封顶策略的 **replace 派生基线来源（只读**，SCOPED 同上下文与链内引擎同实例；CR-R1-3 后封顶经 ContextVar 覆盖传递，不再写入 `engine._retry`），决策 #8/AC-2）②**inner_chain 引用**（重执行用＝`SSD>TOV>Engine` 完整内层链——组合根需将链构造**上提共享（R10-3 落点定稿：工厂函数落 application 域模块、组合根一行委托——「组合根零私有函数」纪律，`build_tool_execution_engine` 先例同款 `tool_execution_engine.py:553-557`）**：现有装配中链内联于 `tool_execution_service` lambda（`:2347-2380`）且 `tool_execution_engine` 端口解析裸引擎，service 按单句柄字面实现会绕过 SSD 安全防护（session_id 注入/并发配额/SandboxExecutionFailed 事件）与 TOV 出参校验——**389-Schema 触发的闭环以「引擎未抛异常」判成功会把违规 output 标 RECOVERED，出参校验闭环被静默架空**）；attempt 重执行必须经 inner_chain（Task 6 循环 B 装配断言——R10-3 落位：装配级录制断言 + engine 句柄与 inner_chain 内引擎同一性断言；**CR-R1-21 回写：实际以「同一性断言 + 重执行固定走 `inner_chain.execute`」交付（结构等价守护）**）；fix-gen 重试封顶 `max_attempts=1` 由服务内自建，**不注入 RetryPolicy**（注入新建 RetryPolicy 会诱导封顶值绕过 replace 派生——派生必须自 engine 原策略保全部字段，陷阱 8） | v1.0.0 | SCOPED | tool-team | (tool, feedback, service) |
| `tool_execution_service` | application | `ToolExecutionServicePort` | **升级 v1.3.0 → v1.4.0**：装饰链最外层加 `ValidationFeedbackDecorator` + execute 入口条件注入 `schema_execution_id`（决策 #16/Task 6 循环 D，R8-23 补登记）；`compatibility=("v1.3.0", "v1.2.0")`；tags += ("feedback",) | v1.4.0 | SCOPED | tool-team | (tool, execution, service, decorated, versioned, feedback) |

**端口方法契约：**
- `ErrorCaseRepositoryPort`：`get_by_natural_key(tenant_id, tool_id, error_signature) -> ErrorCase | None`（V1 精确查询面——自然键 UNIQUE 下精确匹配即全部语义，多案例加权检索登记 deferred-work）；`record_case(case: ErrorCase) -> ErrorCase`（自然键 upsert 幂等计数 + outcome 分类计数）
- `EvolutionLogRepositoryPort`：`save(entity: EvolutionLogEntry) -> EvolutionLogEntry`（execution_id upsert 幂等；返回保存后实体——CR-R1-20 签名回写，深拷贝隔离语义受益）；`list_by_query(query: EvolutionLogQuery) -> tuple[EvolutionLogEntry, ...]`；`get_by_execution(execution_id, tenant_id) -> EvolutionLogEntry | None`
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

- `ToolChainExecutionFailedError`（EXCEPTION_393，`tool_chain_exceptions.py:120-129`）构造器扩展（R8-7 补登记——Task 8.6② / Task 6 循环 E 交付物）：现有 7 参数（message/chain_run_id/chain_id/failed_node_id/original_error_code/original_stage/cause）无错误摘要数据位，新增**可选参数** `error_signature: str | None = None` 与 `enhanced_retry_count: int | None = None`，非 None 时写入 context（与既有「仅非 None 字段进 context」约定一致，`:130-140`）——INFEASIBLE 触发 FAIL_FAST 中断时异常 context 携带失败签名与尝试次数（决策 #14② / K8s JobFailed condition reason 同型）。**可选参数 additive 向后兼容**（既有调用点零改动）；code 不变（393 复用非新开），`sisys-uni-exception-design.md` 编码分配表无需新行——但异常契约语义变更（context 可选键扩展）在设计文档 §3.3.2 编码分配表 393 行注记「context 扩展键（error_signature/enhanced_retry_count，4.7）」留痕

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
- **Edge Cases 必须包含异常路径** — 覆盖触发矩阵九行全覆盖（R8-4：389 入两子路径 / 382-EXECUTION 且 cause∈ExecutionError 族入 / **382-EXECUTION 且 cause∉ExecutionError 族出直传（兜底宽捕获混入形态——cause=LLMConfigError(332) 构造）** / 382-SANDBOX_START 出直传 / 385 出 / 207 出 / 201 出 / 410-413 出 / 398 出）+ 399 耗尽标记场景、案例库空命中纯 LLM 修复、**CASE_GUIDED 正样本命中**（RECOVERED 案例注入 fix_summary）、负样本命中（MARKED_INFEASIBLE 案例）提示注入（全量 3 次不缩减——R8-2）、fix-gen 失败（detail=llm_generation_failed）、**LLM 持续故障全耗尽直传**（3 attempt 全 llm_generation_failed → 直传原 389 不标 INFEASIBLE 零观测副作用——决策 #17/R8-6）、abort 中止（attempt-k 浮出 201/207 直传 + 零观测副作用断言）、幂等重复触发（同 trigger_error 重复 recover()，双终态各一）、RECOVERED 重放合成摘要（含 `"replayed": true` 标记断言——R8-3）；防放大/跨尝试反馈（含 suggested_fix_excerpt 注入断言——R8-1）/hints 透传为单测口径（`test_validation_feedback_service.py`/`test_tool_execution_engine_hints.py`），BDD 不重复覆盖
- **Edge Case 构造注入点清单（防走错路径）**：**BDD fixture 引擎 RetryPolicy 统一形态条款（R10-1/R10-4 立法）**——所有含真实引擎的场景 fixture 引擎 `retry_policy` 必须为**生产白名单形态 + 零退避**：`RetryPolicy(retryable_exceptions=(LLMAPIError, LLMResponseError, TimeoutError), initial_delay_sec=0, max_delay_sec=0)`（`build_tool_execution_engine` 白名单同款 + `:558-560` 注释语义）。**机理（R10-1）**：默认白名单含 `ExecutionError`（`retry_helpers.py:54-59`）时 313 被引擎内层重试 3 次耗尽转 383 → TOV 白名单含 383 再耗尽转 **389**——「382 且 cause∈族入闭环」场景实际以 389 形态入环且 cause 链可提取同一 stderr，**场景完全虚过**（仅 trigger_code/category 与意图不符）；382 主路径触发场景（含负样本首跑/399 耗尽场景的触发段）必须显式构造白名单形态方可达该行。**机理（R10-4）**：389-Schema 子路径 TOV 3 轮校验重试默认退避 1s+2s（`tool_output_validator.py:195-205` 继承 delay 参数），7-8 个场景累计 ~20s 纯 sleep——零退避统一适用于**全部子路径**而非仅 LLM 瞬时子路径；385 超时仅可经引擎 `RetryPolicy(max_total_duration_sec≈0)` 构造（五阶段全部完成后判定 `tool_execution_engine.py:198-204`；靠 sandbox 慢会得 316→382 **进闭环**走错路径；abort 场景**禁用 385**——同 RetryPolicy 下需单调钟竞速 CI 必抖动，用 201/207 构造，见 AC-2 VC 中止路径立法）；207/413 需**同时**注入 resolver（`set_data_source_resolver`）且缺 tool_metadata（无 resolver 时含标记代码先触发 101 而非 207）；201 用 LLM code mock 返回含裸 `$` 代码最易构造；382-cause∉族直传用 mock LLM `side_effect=LLMConfigError` 走真实链（引擎 Think 失败→不在白名单→兜底包 382(cause=LLMConfigError)）或直构 382（VFD 只看异常对象）
- **服务级 BDD 模式（4-6 形态）**：`scenarios()` 批量注册 + `context: dict[str, Any]` fixture + 模块级 `event_loop` fixture + `_run(coro)` helper + `_make_*` 工厂 + `_capture_error`；真实服务链（InMemory 仓储 + 真实 ErrorSignatureExtractor + 真实引擎 + 真实装饰链），仅 LLM/Sandbox 适配器 AsyncMock（可编程失败/修复序列）；fixture 需暴露上述注入点（引擎 retry_policy 参数 / resolver 注入）；**场景级独立重建服务链**（每场景重建仓储/引擎/装饰链——模块级共享会跨场景泄漏 ErrorCase 行，负样本/重放场景依赖场景内先跑一次耗尽再跑第二次）；**事件次数断言前 drain 后台任务**（`asyncio.create_task` fire-and-forget 位于 recover() 尾部，无 drain 则断言竞态随机红——`gather(*pending)` 或 sleep(0) 循环至无 pending task；4-6 `_RecordingEventPublisher` 先例可捕获）
- Fake LLM 分派纪律（4-5 R1-F06 教训）：Mock LLM 按 prompt 中的**结构化角色标记**（如 system_prompt 或修复 prompt 固定前缀）分派响应，禁止按易混淆子串分派——引擎 Think/Code/Validate 与修复生成走同一 mock 时必须按 prompt 结构分派而非纯调用序号

**模块依赖窗口提交策略（4-6 :1128 先例，强制）：**
- Task 0.9 红窗口确认后**暂缓入库**，随对应模块落地**批提交**：feature（无 import，Task 0 即可入库）→ 事件契约/通道映射测试随 Task 2 → 双仓储契约 + PG 仓储集成（不含 outbox fallback 用例——R3-1）随 Task 4 → 验收 .py + 服务契约 + 装饰器测试 + outbox fallback 用例（追加至 repositories 集成文件）**+ 编排器修复（循环 E：orchestrator/Literal/异常构造器三文件与循环 E 测试同批——R8-8）**随 Task 6 → Task 7/8/9 各自红绿同批入库（Task 8 架构测试 import 服务/装饰器/仓储实现，按 8.2-8.6 断言对象**不得早于 Task 6**——R8-27：8.6 断言对象含编排器三文件修改，落 Task 6 循环 E 批）
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
| **TDD 单元测试** | 编排器 INFEASIBLE 三断言（循环 E——R9-21 补登） | node state 三值 / FAIL_FAST context 填充 / SKIP_DOWNSTREAM 兼容 | `tests/unit/application/services/test_tool_chain_orchestrator_infeasible.py` | Task 6 |
| **TDD 契约测试** | 3 新端口 + 1 升级 | 11 维度（注册/名称/版本/接口/生命周期/owner/module/tags/impl callable/方法/Protocol） | `tests/contracts/test_port_contract_error_case_repository.py`、`test_port_contract_evolution_log_repository.py`、`test_port_contract_validation_feedback_service.py` | Task 4/6 |
| **TDD 契约测试** | 事件契约 + 通道映射 | 事件字段/双通道两处一致 | `tests/contracts/test_event_contract_validation_feedback_events.py`、`test_event_channel_mapping_validation_feedback.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_validation_feedback_loop.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_validation_feedback_loop.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | 同 feature/.py | Task 9 |
| **SDD 架构验证** | 反馈闭环架构测试（epics 硬路径） | 重试增强/失败标记/幂等性/演进日志四项 + 8.6 INFEASIBLE×FAIL_FAST 守护（R8-13，第五项） | `tests/unit/architecture/test_validation_feedback.py` | Task 8 |
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
- [ ] **关键路径覆盖率 100%**：闭环触发判定矩阵全九行（R8-4：389 入两子路径/382 且 EXECUTION 且 cause∈ExecutionError 族入/382 且 EXECUTION 且 cause∉族出/382 且 SANDBOX_START 出/385 出/207 出/201 出/410-413 出/398 出）、增强重试 attempt 1→3、耗尽标记、恢复成功、案例回填（recovered/infeasible 分类）、幂等 upsert 全分支

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
| AC-2 | 触发判定（矩阵九行——R8-4） | Task 5 | recover 触发判定矩阵 | `test_validation_feedback_service.py` |
| AC-2 | 案例查询注入修复 prompt | Task 5 | 修复 prompt 组装（CASE_GUIDED/PURE_LLM/负样本） | 同上 |
| AC-2 | hints 注入 + 引擎 prompt 读取 | Task 6 | `validation_feedback_hints` 扩展键 | `test_tool_execution_engine_hints.py` |
| AC-2 | 防放大（两层封顶——CR-R1-3 ContextVar 形态：replace 派生 + per-task 覆盖 + 引擎零写入） | Task 5 | 增强循环内临时降级 | 同上 |
| AC-3 | INFEASIBLE 标记 + ToolResult 契约 | Task 1 / Task 5 / Task 6 | 枚举新增（含 4→5 值边界联动）/ 耗尽转换 | `test_tool_result_status.py` + `test_tool_execution_values.py`（修改）+ `test_validation_feedback_decorator.py` |
| AC-3 | 399 异常全链路登记 + execution_id 全链同源（决策 #16） | Task 2 / Task 6 | 5 处登记 Checklist / 链入口注入 + 引擎复用（循环 D——**CR-R1-4 补交守护**：六断言实际落 `test_execution_id_same_source.py`） | `test_validation_feedback_exceptions.py` + `test_execution_id_same_source.py`（CR-R1-4 补交） |
| AC-3 | INFEASIBLE×FAIL_FAST 语义修复 + 守护（决策 #14，R8-8 落点） | Task 6 / Task 8 | 循环 E 红绿实施（编排器三文件）/ 8.6 纯守护断言 | 循环 E 单测 + `tests/unit/architecture/test_validation_feedback.py`（8.6 三断言） |
| AC-3 | 两领域事件 + 配置双登记 reliable | Task 2 | 事件定义 + 两处配置 | `test_validation_feedback_events.py` + 契约 |
| AC-4 | 演进日志实体 + 双查询面 | Task 1 / Task 4 | 实体 + EvolutionLogQuery + 仓储 | `test_evolution_log_entry.py` + `test_validation_feedback_repositories.py`（集成） |
| AC-4 | outbox 后台路径 fallback 修复 | Task 6 | outbox_repository fallback 独立 session | `test_validation_feedback_repositories.py` + `test_validation_feedback_integration.py` |
| AC-5 | 案例库实体 + 端口 + 存储 | Task 1 / Task 4 | ErrorCase + 仓储双实现 + migration 017 | `test_error_case.py` + `test_validation_feedback_repositories.py`（集成） |
| AC-5 | 幂等 upsert + 分类计数 | Task 4 | 自然键 upsert + SAVEPOINT 容错 | 同上 |
| AC-6 | 闭环幂等（日志/案例/事件） | Task 5 | 同 trigger_error 终态判定短路 | `test_validation_feedback_service.py`（循环 C）+ 集成 |
| AC-6 | ToolSchemaValidationFailed reliable 启用 | Task 2 | 两处配置 + 契约测试 | `test_event_channel_mapping_validation_feedback.py` |
| AC-7 | 装配 v1.4.0 + 3 新端口 | Task 6 | 组合根 + 契约测试 ×3 | 契约测试 |
| AC-7 | 性能基准（P95/成功率/准确率） | Task 7 | 三组基准 | `test_validation_feedback_integration.py` |
| 全部 | 架构约束验证（epics 硬路径） | Task 8 | 四项架构测试（epics 枚举）+ 8.6 守护验证器（R8-13） | `tests/unit/architecture/test_validation_feedback.py` |
| 全部 | 开发结束验收 | Task 9 | 收尾场景 ×2 | feature/.py 收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7（规范源头）

> **目的：** 在进入代码实现前，明确 Schema、端口契约、领域异常契约、验收标准与六边形架构边界。

- [x] Subtask 0.1: 领域事件 Schema 定稿（2 新事件字段表 + `ToolSchemaValidationFailed` reliable 启用决策）
- [x] Subtask 0.2: 数据模型定稿（ErrorCase / EvolutionLogEntry / FixAttempt / INFEASIBLE / ErrorSignatureExtractor 签名算法规范）
- [x] Subtask 0.3: 端口契约清单定稿（SSOT 表 4 行 + 方法签名）
- [x] Subtask 0.4: 领域异常契约定稿（399 五处登记 Checklist + 383/399 语义区分声明）
- [x] Subtask 0.5: API 契约确认（无新端点 + HTTP_MAP 422）
- [x] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_validation_feedback_loop.feature`（AC-x.y 场景集全枚举 + 收尾场景）
- [x] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_validation_feedback_loop.py`
- [x] Subtask 0.8: 编写 3 个端口契约测试 + 事件契约/通道映射契约测试（红）
- [x] Subtask 0.9: 红窗口确认——验收 .py 与契约测试运行失败且失败形态符合预期（collection ERROR / ImportError 属预期中间态；Gherkin 场景因步骤未实现跳过不计红）；按「模块依赖窗口提交策略」确定各批次入库时点
- [x] Subtask 0.10: 前置依赖实地验证——4.3 装饰器链/4.4 沙箱适配器/`configs/event_channels.yaml` 现状冒烟（确认预留注释与实际一致）
- [x] Subtask 0.11: P95 口径重定义（epics「单次重试延迟 P95<5s」→「闭环自身开销 P95<5s，不含 LLM/沙箱时长」，决策 #11）与业务方确认留痕
- [x] Subtask 0.12: hints payload 契约定稿（`{stderr_excerpt, schema_violations, case_summaries, prior_attempts, suggested_fix}`；**prior_attempts 携带各次 FixAttempt 摘要含 `suggested_fix_excerpt`——动作+结果成对（R8-1），「禁止重复失败方案」指令的指涉对象**）+ **per-stage 消费映射定稿**（Code stage 必消费 `suggested_fix` + `prior_attempts`（含前次方案摘要）+ `stderr_excerpt` + 禁止重复指令——唯一代码产出作者必须看到失败历史与失败方案，否则 Reflexion 反馈在作者层断链；Think stage 消费 `case_summaries`（含负样本提示——使引擎对已知不可行签名可感知）+ stderr 摘要；schema_violations → Code/Validate 两 stage）+ 修复建议生成（fix-gen）与引擎 Code stage 的作者分工确认（fix-gen 产出 suggested_fix 策略/代码草案，引擎按 hints 重新生成完整代码——**「建议者+作者」两级结构的归因局限显式接受，见决策 #9 依据（R8-5）**）；**prior_attempts 空方案条目渲染规则（R9-20 定稿）**：`suggested_fix_excerpt=""` 的条目（llm_generation_failed 形态）渲染为「未产出方案（生成失败）」标注，**不进入**「禁止重复失败方案」清单（无指涉对象——空串渲染为已试方案会误导 fix-gen）；Task 6 测试按「各 stage 消费键集」断言（非笼统「读取并拼入」）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域模型与领域服务

**关联 AC:** AC-3（INFEASIBLE）、AC-4（EvolutionLogEntry）、AC-5（ErrorCase/签名）

#### TDD 循环 A：ErrorCase 聚合根 + EvolutionLogEntry 聚合根 + FixAttempt 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_case.py` + `test_evolution_log_entry.py`（构造不变量：UUID 有效/签名 64 hex/occurrence_count=recovered+infeasible 合计≥1/enhanced_retry_count∈[1,3]/trigger_code 枚举/final_status 终态语义/非法构造抛 242；**FixAttempt 边界形态**：`attempt_execution_id=""`+`stderr_excerpt=""`+`suggested_fix_excerpt=""`+`detail="llm_generation_failed"` 可构造合法——禁立 UUID 不变量于该字段；**`suggested_fix_excerpt` 截断 ≤2000 边界**（R8-1）） |
| 🟢 绿 | 实现 `src/domain/entities/error_case.py`、`evolution_log_entry.py`、`src/domain/value_objects/validation_feedback.py` 最小代码 |
| 🔄 重构 | 类型注解、中文 docstring（Google 风格）、`__all__` |

- [x] Subtask 1.1: 🔴 红 — 编写两聚合根 + 值对象失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现三模型最小代码
- [x] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 B：ErrorSignatureExtractor 领域服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_signature_extractor.py`（STDERR 归一化：路径/行号/时间戳/内存地址剥离 + 数值→`<N>`/引号串→`<S>` 模板化后同根因收敛同签名——含 `KeyError: 'x'` 不同键名收敛用例；尾部锚定 `stderr[-2000:]`——超长 traceback 末尾根因行保留用例；violations 归一化——排序去序 + **path 数组索引模板化（`$.output[3].value` 与 `$.output[5].value` 同签名——R8-19 索引漂移收敛用例）** + message 模板化；空输入处理；输出恒 64 hex） |
| 🟢 绿 | 实现 `src/domain/services/error_signature_extractor.py`（纯函数，完整 sha256 hexdigest 64 hex） |
| 🔄 重构 | 确认零外部依赖（仅标准库 hashlib/re） |

- [x] Subtask 1.4: 🔴 红 — 编写签名提取失败测试
- [x] Subtask 1.5: 🟢 绿 — 实现签名提取最小代码
- [x] Subtask 1.6: 🔄 重构 — 优化代码

#### TDD 循环 C：ToolResultStatus.INFEASIBLE 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_result_status.py`（INFEASIBLE 存在/INVALID 既有语义不回归/SUCCESS 不变量不回归/**5 值全集断言**）+ **修改既有** `tests/unit/domain/value_objects/test_tool_execution_values.py:114-121` 4 值边界断言（`len==4` 在 :116 与全值 set 相等断言在 :121）→ 5 值（先红——既有断言在加值后必红，证明边界断言活着；锚点修正 R8-35：实际断言块为 114-121） |
| 🟢 绿 | `src/domain/value_objects/tool_execution.py` 枚举追加 `INFEASIBLE = "infeasible"`（`(str, Enum)` 加值 additive） |
| 🔄 重构 | docstring 更新（`:30`「4 值边界」→ 5 值 + 终态不可行语义 + 与 INVALID"可重试"的区分——同步消解 `:34` INVALID「不进入重试」旧注释与 `:247-249`「可重试」的表述张力） |

- [x] Subtask 1.7: 🔴 红 — 编写枚举扩展失败测试 + 更新既有 4 值边界断言
- [x] Subtask 1.8: 🟢 绿 — 追加枚举值
- [x] Subtask 1.9: 🔄 重构 — 更新语义注释

**完成标准/Definition of Done:**
- [x] 两聚合根 + 值对象 + 领域服务 + 枚举扩展全部实现
- [x] TDD 循环全部通过
- [x] 领域层覆盖率 ≥90%

---

### Task 2: 领域事件与异常体系

**关联 AC:** AC-3（399 + 两事件）、AC-6（reliable 通道补全）

#### TDD 循环 A：领域事件 ×2

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_events.py`（字段默认值/自有字段数边界（8/7）/`to_dict()` 序列化 str 化/aggregate_id 关联 execution_id/**execution_id = 主 id（trigger_error.context 同源，R2-11）**/event_type 经 `__init_subclass__` 自动注册——`base.py:74-85`） |
| 🟢 绿 | 实现 `src/domain/events/validation_feedback_events.py` + `events/__init__.py` 导出 |
| 🔄 重构 | 4-5 R1-F01 教训核查：metadata/字段全 str 化 |

- [x] Subtask 2.1: 🔴 红 — 编写事件失败测试
- [x] Subtask 2.2: 🟢 绿 — 实现两事件
- [x] Subtask 2.3: 🔄 重构 — 序列化安全核查

#### TDD 循环 B：异常 399 全链路登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_exceptions.py`（code=EXCEPTION_399/继承 BusinessException（断言继承关系非父类码号）/context 四字段/子域=toolchain）+ `test_exception_handlers.py` 期望集合更新（先红，按提交策略与实现同 commit） |
| 🟢 绿 | 新建 `validation_feedback_exceptions.py` → `_code_ranges.py` 两处 → `__init__.py` → `EXCEPTION_HTTP_MAP`（399→422）→ 设计文档两表 → 预留注释改已分配 |
| 🔄 重构 | `grep -rn "EXCEPTION_399" src/` 碰撞自查 + `tests/unit/domain/exceptions/` 全目录既有测试回归（25 文件，不硬编码计数） |

- [x] Subtask 2.4: 🔴 红 — 编写异常失败测试
- [x] Subtask 2.5: 🟢 绿 — 五处登记实现
- [x] Subtask 2.6: 🔄 重构 — 碰撞自查 + 全量异常测试

#### TDD 循环 C：事件通道双登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_channel_mapping_validation_feedback.py`（两新事件双通道两处逐字段一致 + ToolSchemaValidationFailed 升级双通道后两处一致） |
| 🟢 绿 | `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py` DEFAULT_MAPPINGS 同步更新（含 4.3 注释"reliable 4.7 启用"改"已启用"） |
| 🔄 重构 | YAML > DEFAULT_MAPPINGS 优先级注释保持 |

- [x] Subtask 2.7: 🔴 红 — 编写通道映射失败测试
- [x] Subtask 2.8: 🟢 绿 — 两处配置同步
- [x] Subtask 2.9: 🔄 重构 — 契约测试转绿确认

**完成标准/Definition of Done:**
- [x] 399 异常五处登记完成且既有异常测试全绿
- [x] 两事件 + 通道双登记完成
- [x] 契约测试通过

---

### Task 3: STDERR 捕获数据链贯通

**关联 AC:** AC-1

#### TDD 循环 A：ExecutionError 增强 + 适配器填充

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_sandbox_exceptions.py`（stderr/exit_code 可选参数写入 context/默认 None 不破坏 4.4 既有断言/**子类 `SandboxTimeoutError`/`SandboxResourceLimitExceededError` 构造回归**——`super().__init__(reason, context=...)` 透传兼容）+ 新建 `test_aiodocker_adapter_stderr.py`（失败路径异常 context 含 stderr[:2000] 与 exit_code） |
| 🟢 绿 | `sandbox_exceptions.py` ExecutionError 构造器增强（签名含 `context`/`cause` 透传合并，Task 0「修改的既有异常」契约）+ `aiodocker_sandbox_adapter.py:511-518` 填充 |
| 🔄 重构 | 截断常量提取（≤2000） |

- [x] Subtask 3.1: 🔴 红 — 编写异常增强与适配器填充失败测试
- [x] Subtask 3.2: 🟢 绿 — 实现两处最小改动
- [x] Subtask 3.3: 🔄 重构 — 优化代码

#### TDD 循环 B：SandboxSecurityDecorator 事件填充 + cause 链提取 helper

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `test_sandbox_security_decorator_events.py`（SandboxExecutionFailed 事件 execution_id/stderr 填充断言——execution_id 取自**外层** 382 异常 context（helper 签名需能拿到外层异常或其 context）；**直连路径**（execute_code_with_protection）execution_id 空串分支）+ cause 链提取 helper 测试（**双分支**：主分支=生产链 382 自定义 `cause` 属性单跳到 313；次分支=389 `__cause__` 链经 383 到 LLM 错误——见 Dev Notes「STDERR 实际浮现路径」） |
| 🟢 绿 | `sandbox_security_decorator.py:132-137` 事件填充（except 块读外层 `exc.context["execution_id"]`）+ 新增 cause 链 stderr 提取函数（同时遍历自定义 `cause` 属性与 `__cause__`/`__context__`，供 4.7 装饰器复用，放置于该模块导出） |
| 🔄 重构 | 4.4 既有测试全量回归（事件字段新增不破坏旧断言） |

- [x] Subtask 3.4: 🔴 红 — 编写事件填充失败测试
- [x] Subtask 3.5: 🟢 绿 — 实现填充与提取
- [x] Subtask 3.6: 🔄 重构 — 4.4 回归确认

**完成标准/Definition of Done:**
- [x] STDERR 三段链贯通（adapter → 异常 context → 事件 + cause 链提取）
- [x] 4.4 既有测试零回归
- [x] TDD 循环全部通过

---

### Task 4: 仓储端口与存储双实现

**关联 AC:** AC-4、AC-5

#### TDD 循环 A：端口 + InMemory 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_error_case_repository.py` + `test_evolution_log_repository.py`（InMemory：get_by_natural_key 精确查询/record_case 自然键 upsert 分类计数（recovered_count/infeasible_count）/save 幂等/list_by_query 分页过滤/get_by_*） |
| 🟢 绿 | 实现 `src/domain/ports/error_case_repository.py`（含 EvolutionLogQuery 于 evolution_log_repository.py）+ `src/infrastructure/storage/inmemory/` 双实现 |
| 🔄 重构 | InMemory 深拷贝防共享引用污染（4-6 CR1-2 教训） |

- [x] Subtask 4.1: 🔴 红 — 编写双仓储 InMemory 失败测试
- [x] Subtask 4.2: 🟢 绿 — 实现端口 + InMemory
- [x] Subtask 4.3: 🔄 重构 — 深拷贝防护

#### TDD 循环 B：PG 模型 + migration 017 + PG 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | PG 仓储测试（新建 `tests/integration/test_validation_feedback_repositories.py` 为本循环红/绿载体——repo_session 事务 rollback + `xdist_group` 串行 + PG 探活 skip（4-6 `test_tool_version_integration.py:50,158-183` 样板，**非**独立 schema/TestTenant 模式）：upsert 幂等/UNIQUE 冲突 begin_nested 容错重读/JSONB fix_attempts 读写。**R3-1 注记**：outbox fallback 用例**不在本批**——落 Task 6 循环 C 向本文件追加（fallback 修复在 Task 6，本批入库时含 fallback 用例必红破坏批次全绿） |
| 🟢 绿 | `models/error_case.py` + `models/evolution_log_entry.py` + `repository/` 双实现 + `deploy/postgresql/alembic/versions/017_validation_feedback.py`（表设计见 Dev Notes） |
| 🔄 重构 | migration 仅新增不修改既有（红线） |

- [x] Subtask 4.4: 🔴 红 — 编写 PG 仓储失败测试
- [x] Subtask 4.5: 🟢 绿 — 实现 PG 双仓储 + migration 017
- [x] Subtask 4.6: 🔄 重构 — 事务边界优化

#### TDD 循环 C：组合根注册 + 契约测试转绿

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 编写的 `test_port_contract_error_case_repository.py`、`test_port_contract_evolution_log_repository.py` 保持红 |
| 🟢 绿 | `composition_root.py` 注册 2 端口（lambda 工厂 + PortSpec 10 字段） |
| 🔄 重构 | 契约测试 11 维度全绿 |

- [x] Subtask 4.7: 🔴 红 — 契约测试红状态确认
- [x] Subtask 4.8: 🟢 绿 — 组合根注册转绿
- [x] Subtask 4.9: 🔄 重构 — 11 维度全绿

**完成标准/Definition of Done:**
- [x] 双仓储 InMemory + PG 实现 + migration 017
- [x] 契约测试 ×2 通过
- [x] 基础设施层覆盖率 ≥75%

---

### Task 5: Validation Feedback 应用服务（闭环编排）

**关联 AC:** AC-2、AC-3、AC-5、AC-6

#### TDD 循环 A：触发判定与闭环编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_validation_feedback_service.py` 循环 A 组（触发判定矩阵九行：389 入（Schema/LLM 瞬时两子路径）/382 且 stage=EXECUTION 且 cause∈ExecutionError 族入（含 316/317）/382 且 stage=EXECUTION 且 cause∉族出直传（R8-4——cause=LLMConfigError(332) 构造用例）/382 且 stage=SANDBOX_START 出直传/385 出直传/207、201 出直传/410-413 出直传/398 出直传；增强循环 attempt 1→3 计数（总数 3 非重试 3）；耗尽抛 399） |
| 🟢 绿 | 实现 `src/application/ports/validation_feedback_service.py` + `src/application/services/validation_feedback_service.py`（recover 编排：提取→查询→修复→重执行→记录）+ `validation_feedback_prompts.py` |
| 🔄 重构 | 383/399 语义区分注释显式化 |

- [x] Subtask 5.1: 🔴 红 — 编写触发判定失败测试
- [x] Subtask 5.2: 🟢 绿 — 实现服务骨架与触发判定
- [x] Subtask 5.3: 🔄 重构 — 优化判定逻辑

#### TDD 循环 B：修复生成 + 防放大 + 案例回填

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 循环 B 组（LLM 修复 prompt 组装含案例 fix_summary（命中 RECOVERED 且非空）/命中 MARKED_INFEASIBLE 且 category 匹配注入负样本提示且 `fix_strategy=NEGATIVE_CASE_GUIDED`（全量 3 次不缩减——R8-2；category 不匹配落 PURE_LLM 碰撞抑制——R9-16 格⑤）/空案例 PURE_LLM 降级/**命中 RECOVERED 但 fix_summary 空（LLM_TRANSIENT 首例）落 PURE_LLM「命中但无可注入配方」注记（R9-16 格④）**/**attempt k prompt 含 attempt 1..k-1 失败反馈（stderr_excerpt/detail/suggested_fix_excerpt 动作+结果成对——R8-1；空 excerpt 条目渲染为「未产出方案（生成失败）」不进禁止重复清单——R9-20）与禁止重复指令**/fix-gen 自身失败（含非白名单异常）计为该次 attempt 失败/**mid-attempt 异常分类（R9-13）：389/382-cause∈族 mid-attempt 计为该次 attempt 失败（detail=retry_failed）；382-cause∉族（StorageError）mid-attempt 中止直传零观测副作用**/**3 attempt 全失败且根因均为 LLM 瞬时（llm_generation_failed 或 retry_failed 且 389←383←LLM 链）直传原触发不标 INFEASIBLE 零观测副作用（决策 #17②/R9-15 根因导向）**/**LLM_TRANSIENT 成功不覆写 fix_summary（决策 #17/R8-6）**/增强期间引擎与 validator 两层重试封顶 1 且按引用恢复（retryable_exceptions 保持 + TOV 无显式 retry_policy 前置断言——**CR-R1-3 机制演进**：封顶形态已迁移 ContextVar per-task 覆盖，断言面改为 effective 观测 + 引擎零触碰 + 并发回归，决策 #8/陷阱 8/14 同步改写）/恢复成功回填 recovered_count + 覆写 fix_summary（非 LLM_TRANSIENT 类）+ ToolExecutionRecovered 事件/耗尽回填 infeasible_count + ToolExecutionMarkedInfeasible 事件 + 演进日志） |
| 🟢 绿 | 实现修复循环（fix-gen 产出 suggested_fix + 跨尝试反馈）+ 案例回填 + 演进日志写入 + 事件发布（fire-and-forget，P0-I 模式） |
| 🔄 重构 | Fake LLM 按 system_prompt 角色标记分派（4-5 教训）核查测试自身 |

- [x] Subtask 5.4: 🔴 红 — 编写修复与回填失败测试
- [x] Subtask 5.5: 🟢 绿 — 实现完整闭环
- [x] Subtask 5.6: 🔄 重构 — 优化代码

#### TDD 循环 C：幂等与 evolution log

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 循环 C 组（同 trigger_error 重复 recover：演进日志单行/事件单次/案例以终态调 record_case 同步递增计数（R3-2 定谳——禁只加 occurrence 破坏合计不变量）/短路返回合成结论——INFEASIBLE 语义完整、RECOVERED 为不含证据包的摘要（AC-6 边界注记）） |
| 🟢 绿 | 终态判定短路（execution_id 取自 trigger_error.context；已有终态记录→副作用去重 + 合成结论 + record_case 观测计数） |
| 🔄 重构 | 幂等键统一为 execution_id |

- [x] Subtask 5.7: 🔴 红 — 编写幂等失败测试
- [x] Subtask 5.8: 🟢 绿 — 实现幂等短路
- [x] Subtask 5.9: 🔄 重构 — 优化代码

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
| 🔴 红 | 编写 `test_validation_feedback_decorator.py`（触发判定对齐九行矩阵（R9-1 口径补齐）：捕获 389 委托 service/382-EXECUTION 且 cause∈ExecutionError 族 委托/382-EXECUTION 且 cause∉族 直传（cause=LLMConfigError(332) 构造——R8-4 核心新增行为在装饰器层的测试位）/382-SANDBOX_START 透传/其他异常透传/INFEASIBLE 结果转换不抛异常）+ `test_tool_execution_engine_hints.py`（`validation_feedback_hints` 扩展键读取并拼入 Think/Code prompt（含「优先采纳 suggested_fix」指令）/无 hints 零行为变化） |
| 🟢 绿 | 实现 `src/application/services/validation_feedback_decorator.py` + `tool_execution_engine.py` prompt 构建扩展（`__init__` 签名不变） |
| 🔄 重构 | 引擎改动面最小化核查（4.4 AC-7.4 BDD 断言保护） |

- [x] Subtask 6.1: 🔴 红 — 编写装饰器与 hints 失败测试
- [x] Subtask 6.2: 🟢 绿 — 实现装饰器 + 引擎扩展
- [x] Subtask 6.3: 🔄 重构 — 优化代码

#### TDD 循环 B：装配升级 v1.4.0 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_port_contract_validation_feedback_service.py` 红 + `test_port_contract_tool_execution_service.py` 版本期望升级 v1.4.0 **及 EXPECTED_TAGS 增补 feedback**（`:150,:205` set 全等断言——tags += ("feedback",) 不同步必红，R3-6）+ **双句柄装配断言（R10-3 落位）**：①装配级——经组合根装配的 service 触发一次 recover 后，录制式替身断言 attempt 重执行调用到达 SSD 与 TOV（非裸引擎——R9-14 双句柄的运行面守护。**CR-R1-21 回写**：实际以「同一性断言 + 重执行固定走 `inner_chain.execute`（`validation_feedback_service.py` 编排单点）」交付——结构等价守护）；②同一性——service 的 engine 句柄与 inner_chain 最内层引擎为**同一对象**（id 相等——否则封顶封的是另一台引擎，防放大失效；生产 SCOPED 缓存 `resolver.py:186-189` 可保但契约测试 `_DummyResolver` 每次新实例，须显式断言。**CR-R1-3 后封顶改 replace 派生基线——同一性保证派生自真实引擎配置**） |
| 🟢 绿 | `composition_root.py`：注册 `validation_feedback_service` + 装饰链最外层加 ValidationFeedbackDecorator + version/compatibility/tags 更新 + **链构造上提共享双句柄注入（R9-14/R10-3 落点：工厂函数落 application 域模块——`build_tool_execution_engine` 先例同款「组合根零私有函数」纪律（`tool_execution_engine.py:553-557`），组合根一行委托）** |
| 🔄 重构 | 契约测试 11 维度 ×2 全绿 + 既有 tool_execution_service 契约回归 |
- [x] Subtask 6.4: 🔴 红 — 契约测试红确认
- [x] Subtask 6.5: 🟢 绿 — 装配升级转绿
- [x] Subtask 6.6: 🔄 重构 — 全绿确认

#### TDD 循环 C：outbox 独立 session 结构性修复（defer 债清偿）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写失败场景测试：**后台/CLI 路径**（无请求 session——`get_session()` 抛 RuntimeError 场景，`PostgreSQLAdapter._session` property `repository/postgresql_adapter.py:46-64`）断言 reliable 事件 outbox 写入经 fallback 独立 session 成功落库（现状该场景静默丢失，当前行为下红）；HTTP 路径（有请求 session）行为不变断言。**fallback 测试清理策略（R2 发现，强制）**：fallback 走 `session_context` 独立写入即 **commit**（`session_context.py:117-127`），repo_session 的 rollback 够不着——测试必须**不挂 repo_session**（否则 ContextVar 有值触发不了 RuntimeError 分支），并在 try/finally 中按**本测试自建 event_id 集合**删除自建行（「只清理自己创建的资源」的本意形态；隔离表「禁手动 delete/truncate」禁令针对 truncate 全表/误删他行，定向删除自建行是该规则的合规例外并在此显式声明） |
| 🟢 绿 | `src/infrastructure/messaging/outbox/outbox_repository.py`：`save` **直接调用 `get_session()` 捕 `RuntimeError`**（实现精度注记 R3-11，R8-34 勘误细化：`PostgreSQLOutboxRepository._session` property（`:40-42`）现状即直调 `get_session()` **无包装**——无 session 时抛的就是裸 `RuntimeError`，修复形态 = 现有调用外包 try/except 即可；`InvalidStateError` 分叉仅存在于 `PostgreSQLAdapter._session`（`postgresql_adapter.py:60-64` 捕 RuntimeError 重包）——若 fallback 机制复用扩展至 `PostgreSQLAdapter` 系仓储（`_persist_execution` 探针），那里才需「绕过 property 直调 `get_session()`」），RuntimeError 时经注入的 `session_factory` 走 `session_context` 独立写入（`outbox_processor.py:146-155` 先例同款，R8-36 行号校准；**修复必须落在 infrastructure 层**——application 禁 import infrastructure；HTTP 路径保持请求 session 同事务，事务性原子性不变——接线形态见 R8-9 注记） |
| 🔄 重构 | 正常 HTTP 路径行为零变化回归断言 + fallback 行 teardown 验证（自建行清理后零残留）+ `tool_execution_engine.py:282-284` 与 `data_source_resolver.py:352` 两处 defer 注释更新（形态① 无 session 场景已修复；形态② session_context 异常回滚连带丢失登记 `deferred-work.md`——AC-4 遗留债）。**形态② 探针动作（R7，R8-9 勘误）**：实施本循环时顺带核查后台 worker 的 `session_context` 事务边界——**勘误**：R7 原文「HTTP 路径事务语义正确（领域失败经 ExceptionHandlers 转响应走 commit，`session_middleware.py:60-68`）」有两处失准：①实际路径为 `src/infrastructure/middleware/session_middleware.py:58-71`（`interfaces/api/middleware/` 目录不存在）；②**该中间件当前未在 `create_app()` 接线**（实测：`app.py:55` 仅注册 ExceptionContextMiddleware，SessionMiddleware 全 src 零生产引用）——「领域失败转响应走 commit」为**设计语义而非运行事实**，现状生产**全部路径**（含 HTTP 请求触发的 fire-and-forget）outbox save 均触发 RuntimeError fallback，本循环的 fallback 修复因此覆盖当前全部生产路径（修复必要性上调）；SessionMiddleware 生产接线为独立技术债（登记 deferred-work）；fallback 机制（session_factory 注入 + session_context 独立写入）可直接复用扩展至 `_persist_execution`——探针结论写入 deferred-work 登记行（具备则升级，不具备则留语义推演记录）。**HTTP 路径回归断言构造注记（R8-9 联动）**：「有请求 session」形态测试需显式 `set_session()` fixture 模拟已接线中间件（接线前该形态在生产不可达，测试验证的是 fallback 分支语义而非生产路径） |

- [x] Subtask 6.7: 🔴 红 — 编写 outbox 独立 session 失败测试
- [x] Subtask 6.8: 🟢 绿 — 实现独立 session 修复
- [x] Subtask 6.9: 🔄 重构 — 双路径回归 + 注释清偿

#### TDD 循环 D：execution_id 全链同源（决策 #16 / R7——关闭 R2-5 deferred）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写失败测试：①链入口注入断言——**spy 口径（R9-19）**：`ExecutionContext` frozen + `with_extension` 返回新实例——调用方 context 在 execute 后不含新键，断言对象为**内层收到的 context**（录制式 wrapped/装饰器替身捕获）；②引擎复用断言——注入预置 id（UUID 对象）后 `ToolExecution` 聚合 `execution_id` 与之相等（含 382 异常 context 同 id 断言；**str 化比较口径（R9-19）**——预置 UUID 对象 vs 引擎/异常 context 中 str 形态，断言用 `str(预置)==context 值`）；③TOV 透传断言——389 的 `context["execution_id"]` 与预置 id 相等（`extract_schema_execution_id` 命中 extensions 通道，str 化同②）；④未注入时引擎新铸（向后兼容——既有单测直构引擎不注入仍绿）；⑤**条件注入负分支（R9-10/R9-19）**——context 预置合法 id 后入口**不覆写**（注入点与引擎读取点对既有键单点保持）；**第三态定义（R9-19）**：extensions 键为非法 UUID 值时行为 = 读点统一经 `extract_schema_execution_id` 单点归一（非法值静默新铸——引擎与 TOV 共用该 helper 则同 id；**禁直读裸值**——裸 UUID 构造在引擎 try 块外抛 242） |
| 🟢 绿 | `tool_execution_service.py:64` 入口条件注入（~2 行：`if "schema_execution_id" not in context.extensions:` + `with_extension`）+ `tool_execution_engine.py:137-138` 聚合 id 优先经 `extract_schema_execution_id(context)` 读取（兜底新铸，读点单点归一） |
| 🔄 重构 | 4.3/4.5 既有 schema 事件测试回归（execution_id 语义从「TOV 随机铸造/session_id fallback」变「链入口统一」——断言 instanceof UUID 者不受影响，断言特定值者核对（含 session_id 为合法 UUID 时 4.3 事件 id 取 session_id 血统的旧形态用例）） |

- [x] Subtask 6.10: 🔴 红 — 编写 id 同源四断言失败测试（**CR-R1-4 勘误：本批测试 dev 周期实际缺位**——突变实验证明 revert 决策 #16 两处生产代码零红；代码审查周期补交 `test_execution_id_same_source.py` 六断言（含断言④优先级链形态与⑥双未注入独立新铸），见 Review Findings CR-R1-4）
- [x] Subtask 6.11: 🟢 绿 — 入口注入 + 引擎复用两处最小实现
- [x] Subtask 6.12: 🔄 重构 — 既有 schema 事件测试回归

#### TDD 循环 E：编排器 INFEASIBLE 语义修复（决策 #14 / R8-8 落点迁移——自 Task 8.6 迁入，红绿一体）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写编排器三断言失败测试（新增 `tests/unit/application/services/test_tool_chain_orchestrator_infeasible.py`）：①node state 三值——INFEASIBLE 结果的节点 `state=="INFEASIBLE"`（非 `"FAILED"` 二值折叠，`:637` 现状必红）；②FAIL_FAST 中断异常 context 含 `error_signature` 与 `enhanced_retry_count`（`:218-224` cause=None 现状下 context 无此二键，必红——ToolResult 从 `completed_node_results[failed_node_id]` 可达）；③SKIP_DOWNSTREAM 下游 SKIPPED + 独立分支正常执行（既有行为回归位，不预期红） |
| 🟢 绿 | 三文件最小实现：`tool_chain_orchestrator.py:637` 三值判定（`result.status == ToolResultStatus.INFEASIBLE` → `"INFEASIBLE"`，`:643` 的 `!= "success"` 计入 failed_nodes **不动**——INFEASIBLE 继续驱动 FAIL_FAST 中断与 SKIP_DOWNSTREAM 跳过）+ `:218-224` 从 `completed_node_results` 取 output 填充异常 context；`src/domain/entities/tool_chain_run.py:86` Literal 加 `"INFEASIBLE"` + `:78` docstring 同步（R8-7）；`tool_chain_exceptions.py` 构造器扩可选参数 `error_signature`/`enhanced_retry_count`（Task 0「修改的既有异常」契约） |
| 🔄 重构 | 既有编排器测试全量回归（`test_tool_chain_orchestrator*.py`——node state 断言均为 COMPLETED/FAILED/SKIPPED 形态，不受 Literal 加值影响） |

- [x] Subtask 6.13: 🔴 红 — 编写编排器三断言失败测试
- [x] Subtask 6.14: 🟢 绿 — 编排器/Literal/异常构造器三文件最小实现
- [x] Subtask 6.15: 🔄 重构 — 既有编排器测试回归

**完成标准/Definition of Done:*
- [x] 装饰链四层装配 + v1.4.0
- [x] outbox 修复落地 + defer 注释清偿
- [x] execution_id 全链同源（聚合/异常 context/演进日志/事件四点一 id）
- [x] 编排器 INFEASIBLE 语义修复（循环 E 三文件——决策 #14 前两件 delta）
- [x] 既有契约测试零回归

---

### Task 7: 集成测试与性能基准

**关联 AC:** AC-4、AC-5、AC-6、AC-7

> 无独立 TDD 循环表——本 Task 为真实服务全链验证（epics 硬路径 `tests/integration/test_validation_feedback_integration.py`）。

- [x] Subtask 7.1: 全链闭环集成测试（真实 PG repo_session 事务 rollback + xdist_group 串行 + PG 探活 skip——4-6 `test_tool_version_integration` 样板：模拟沙箱失败→闭环→恢复/耗尽两路径；InMemory→PG 仓储替换真实实现）
- [x] Subtask 7.2: 幂等集成测试（同 trigger_error 重复 recover() 三副作用断言 + 合成结论）
- [x] Subtask 7.3: 性能基准一——闭环开销 P95<5s（签名提取+查询+日志写入计时，20 次采样，端口级计时代理 + `statistics.quantiles` 分位断言 + 分级 skip 留证）
- [x] Subtask 7.4: 性能基准二——闭环机制成功率 ≥80%（20 次可修复故障注入，AsyncMock LLM 可编程修复序列按 prompt 结构分派；主断言为内容性断言——修复 prompt 含 stderr/案例/历史反馈、hints 注入透传）
- [x] Subtask 7.5: 性能基准三——不可行标记机制准确率（20 次不可修复全部标记 + 可修复 0 误标，等效 100%）
- [x] Subtask 7.6: outbox 修复集成回归（后台路径 fallback 独立 session 投递 + HTTP 路径零变化）

**完成标准/Definition of Done:*
- [x] 集成测试全绿（真实服务）
- [x] 三组性能基准达标
- [x] 集成覆盖率 ≥75%

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** 全部（epics 硬路径四项架构测试 + 8.6 INFEASIBLE×FAIL_FAST 守护——R8-13 第五项）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 8.1: 创建 `tests/unit/architecture/test_validation_feedback.py`（epics 指定硬路径——与目录内既有 `test_arch_*.py` 命名惯例（28 个文件）不同，按 epics_v1.0.md:1395 指定名创建，文件头 docstring 注明）
- [x] Subtask 8.2: 重试增强验证器——STDERR 捕获与修复建议生成链路断言（触发→prompt 含 STDERR/案例→重执行）
- [x] Subtask 8.3: 失败标记验证器——3 次增强失败后 INFEASIBLE + 399 + 事件三联断言
- [x] Subtask 8.4: 幂等性验证器——同 trigger_error 重复 recover：日志单行 / 事件单次 / 案例分类计数与 occurrence 同步递增（record_case 幂等路径，AC-6 R3-2 定谳口径）/ 不新建行 / fix_summary 不覆写
- [x] Subtask 8.5: 演进日志验证器——失败历史可追溯（双查询面）
- [x] Subtask 8.6: INFEASIBLE×FAIL_FAST 语义守护验证器（决策 #14 / R6 业界对标；**R8-8 性质定稿：纯守护断言**——验证 Task 6 循环 E 已落地的修复，本 Subtask 不含生产代码修改）——①`NodeRunStatus.state` 类型不抹除断言：INFEASIBLE 结果的节点 state 为 `"INFEASIBLE"`（非二值 `"FAILED"`——Task 6 循环 E 已扩展 `tool_chain_orchestrator.py:637` 三值判定 + `tool_chain_run.py:86` Literal）且 `tool_result` 含失败摘要；②FAIL_FAST 中断因果断言：INFEASIBLE 触发 `ToolChainExecutionFailedError` 时异常 context 含 `error_signature` 与 `enhanced_retry_count`（`:218-224` 修复已落循环 E——异常构造器扩参 `tool_chain_exceptions.py`）；③SKIP_DOWNSTREAM 兼容断言：INFEASIBLE 节点的下游 SKIPPED、独立分支正常执行
- [x] Subtask 8.7: 循环依赖检测使用 ruff/isort（不引入 pylint）+ 运行完整测试套件生成报告

**完成标准/Definition of Done:*
- [x] 四项架构测试（epics 枚举）+ 8.6 守护验证器（R8-13）全部通过
- [x] 测试输出清晰的合规报告
- [x] 任何违规都会导致测试失败

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

- [x] Subtask 9.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [x] Subtask 9.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [x] Subtask 9.3: 运行开发结束验收测试并确认通过
- [x] Subtask 9.4: 运行 `poetry run pytest tests/ -n 8`、`ruff check`、`mypy` + 三条异常红线 grep 自查收尾

**完成标准/Definition of Done:*
- [x] `src` 完成清单已逐项验证确认
- [x] 四测试目录完成清单已逐项验证确认
- [x] 开发结束验收测试通过
- [x] Story 可进入 `done`（提交后转 review）

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
| 3 | 耗尽对外契约 | 返回 `ToolResult(INFEASIBLE)` 不抛异常；399 为内部信号 | ToolChain DAG 编排按 status 结果化感知——**中断与否由 `failure_strategy` 决定（R8-11 校准）：CONTINUE_ON_ERROR / SKIP_DOWNSTREAM 不中断（下游 SKIPPED/落 COMPLETED_WITH_ERRORS），FAIL_FAST 仍中断（波次间检查 `:208-225` 兜底 raise，见决策 #14）**；4.3 蓝图"降级到人工审核"非本 epic 范围 |
| 4 | 异常编码 | 仅 1 个新异常占 399；**不扩 400-409** | 方案 A 触发条件（≥2 异常）未满足；Fallback/HumanReview/Canary 三预测异常均属非本 epic 的扩展链路（见非目标） |
| 5 | 错误签名算法 | 领域服务纯函数归一化（剥路径/行号/时间戳/内存地址 + 数值/引号串模板化 + 尾部锚定 `stderr[-2000:]`）→ **完整 sha256 hexdigest（64 hex）** | 确定性可测；同根因不同表层输出收敛（幂等前提）——Sentry message templating 对标防插值分裂、尾部锚定防切根因；完整摘要保留前缀粗化分组派生能力（多案例检索前置）；V1 精确匹配，向量检索留 L3 扩展 |
| 6 | 案例回填时机 | 恢复成功回填 `recovered_count += 1` 并覆写 fix_summary（仅 RECOVERED 覆写）+ 耗尽回填 `infeasible_count += 1` | 成功案例对后续修复价值最高（Few-Shot 素材）；分类计数防不可行写回冲掉修复配方；失败计数支撑负样本提示与准确率统计 |
| 7 | STDERR 链修复方式 | `ExecutionError` 构造器可选参数（stderr/exit_code 入 context，**含 context/cause 透传合并**——子类零改动）+ adapter 填充 + 装饰器事件填充（execution_id 取外层 382 context） | 向后兼容（默认值 + 透传保证子类 `super().__init__(reason, context=...)` 零改动）；事件字段已预留（sandbox_events.py:96/101/104）只欠填充 |
| 8 | 防重试放大 | 增强循环期间内层重试全部封顶：引擎 `_retry` 与 validator 校验重试（经 `effective_retry_policy` 动态读，前置条件=TOV 无显式 retry_policy）——**CR-R1-3 定稿：ContextVar per-task 覆盖形态**（封顶策略 `dataclasses.replace(engine._retry, max_attempts=1)` 全字段保真，经 `retry_policy_override` 按 task 覆盖，with 退出自动还原；VFD 与 TOV 双侧同源同修——TOV 自身校验循环期间的引擎封顶同迁 ContextVar） | 4.3 P0-1 教训复用；修正数学：TOV 已无条件封顶 engine 内层，防放大的真实对象是增强期间的 TOV 校验重试（未防 3×3×1=9x）；**旧「整体替换+按引用恢复」两缺陷（CR-R1-3 证伪）**：①`clear_scoped` 生产未接线→SCOPED 实为进程共享，交错恢复可使 `max_attempts` 永久=1（无锁竞态）②封顶构造只保留 retryable_exceptions 把 backoff/duration 重置默认值——replace 派生根治两缺陷且并发安全（per-task 隔离）；replace 派生防默认 RetryPolicy（含 313）静默偏离生产白名单（生产已收窄排除） |
| 9 | hints 注入通道 | `context.extensions["validation_feedback_hints"]`（ExecutionContext frozen + with_extension 工厂），payload 契约 `{stderr_excerpt, schema_violations, case_summaries, prior_attempts, suggested_fix}` | P0-D 模式先例（schema_last_violations 同款）；引擎 `__init__` 签名不变；引擎 Code stage 是**唯一代码产出作者**（指令「优先采纳 suggested_fix」）——**R8-5 论证精确化**：结构实为「fix-gen 建议者 + 引擎作者」两级，attempt 失败无法完全区分 fix-gen 方案错误与引擎适配偏差（归因局限显式接受——换取案例库注入/跨尝试反馈的工程收益与引擎 stage 复用）；成本注记：每次触发总 LLM 调用 ≈ 基础层 3×3 + 闭环 3×(1 fix-gen + 引擎五阶段)，修复增益依赖 mock 基准验证（AC-7） |
| 10 | outbox 修复落点 | `messaging/outbox/outbox_repository.py` fallback 独立 session（优先 get_session()，RuntimeError 时经 session_factory 走 session_context） | 两处 defer 注释显式指派本 Story；outbox_processor.py:146-155 独立 session 先例；application 层禁 import infrastructure 约束；HTTP 路径事务性原子性保持（无条件独立 session 会破坏原子性并污染 rollback 隔离测试） |
| 11 | 性能指标口径 | P95<5s 限闭环自身开销（签名/查询/日志），LLM 与沙箱时长除外；比率指标命名为「闭环机制有效性」（mock LLM 度量编排正确性非修复能力） | epic 字面指标可测化——LLM 生成受 LLMConfig.timeout=600s 支配物理上不可能 <5s；Task 0 与业务确认留痕（Subtask 0.11） |
| 12 | 修复循环反馈记忆 | attempt k 的修复 prompt 携带 attempt 1..k-1 失败反馈（FixAttempt.stderr_excerpt/detail/**suggested_fix_excerpt（R8-1）**+ 禁止重复指令） | Reflexion/Self-Debugging/ChatRepair 共识——**动作+结果成对反馈**（Reflexion 反思完整轨迹含动作 / Self-Debugging 反馈含生成代码+执行结果）：仅传失败现象不传失败动作则「禁止重复」无指涉对象，防重复机制信息上不成立；无跨尝试反馈时 attempt 2/3 与 attempt 1 独立同分布，确定性采样下重复生成相同失败修复，3 次尝试退化为同一次的重复采样 |
| 13 | 幂等语义 | 副作用去重（execution_id 取自 trigger_error.context）+ INFEASIBLE 结论可重放；RECOVERED 重放返回**可辨识**合成摘要（`replayed: true` 标记，不含证据包） | 链入口每次 execute 注入新 `schema_execution_id`（决策 #16，引擎无注入时兜底新铸——R8-12 锚点更新），「装饰器重复调用」不命中幂等键（架构边界）；日志无 result 载荷故不承诺 RECOVERED 完整重放——重放结果「要么等价要么可辨识」（Temporal replay / HTTP Idempotency-Key 共识，R8-3），合成 SUCCESS 不通过 `validate_complete()`（386）为已登记边界 |
| 14 | INFEASIBLE×FAIL_FAST 语义定稿（R6 业界对标勘误） | 耗尽结果化后 FAIL_FAST 链**仍中断**（波次检查 `:208-225` 兜底，R2「变为继续执行」结论系漏看该检查点）；真实 delta = 类型丢失（node state 二值判定）+ cause=None（异常可观测性降级）+ 同波兄弟跑完（算力浪费）——前两者随本 Story 修复（**落点 R8-8 定稿：Task 6 TDD 循环 E 红绿一体实施 + Task 8.6 纯守护断言**），同波取消为可选优化 deferred | 业界主流一致：永久性失败 × 显式 fail-fast = 中断（K8s PodFailurePolicy FailJob 短路重试立即终止 / Temporal non-retryable 跳过重试 / SF 未捕获即 fail）；「结果化继续」须显式声明而非默认副作用；类型元数据在传播链不可抹除（Temporal re-wrap 反模式）；「业务方确认」阻碍经对标消解——中断语义维持现状即正确立场 |
| 15 | fix_strategy 三分支 | `FixStrategy` 三值：CASE_GUIDED（命中 RECOVERED 且 fix_summary 非空）/ NEGATIVE_CASE_GUIDED（命中 MARKED_INFEASIBLE——负样本提示形态）/ PURE_LLM（无命中） | 二值枚举会把「负样本命中」虚标为 PURE_LLM（反向虚标，R1-9 同轴）；演进日志失败史需区分「已知不可行签名仍尝试」（AIOps 最有价值信号）与「无案例可查」；新建值对象加值零成本 |
| 16 | execution_id 全链同源（R7 定稿） | 链入口 `ToolExecutionService.execute` **条件**注入 `schema_execution_id`（R8-16：`if not in extensions` 才注入——防未来 ToolInputValidator 入链时无条件覆盖致 INPUT/OUTPUT id 分裂倒退 P0-F 一致性；沿用 4.3 预留的 extensions 透传键——`schema_event_helpers.py:139-173` 第一优先级）+ 引擎聚合 id 优先读该键（Task 6 循环 D）——聚合/382/389/演进日志/两事件四点一 id | 关闭 R2-5「两套 id 空间」deferred；改动 ~4 行生产代码（入口 1 + 引擎 3）+ TOV 零改动自动命中（R8 调研实证：全链 context 零重建——SSD 原样透传/TOV with_extension 保键/引擎只读，注入键必达 TOV:111 与引擎读取点）；R7 调查勘误了 R6 前的「ToolResult 加字段」设想（389 抛异常不构造 ToolResult，加字段无效）；引擎 save 为 upsert，校验重试同 id 重入无乐观锁冲突；dev 前是窗口（dev 后事件链消费面固化，再改过 ContractGate） |
| 17 | LLM_TRANSIENT 双保险（R8-6 新增） | ①`error_category=LLM_TRANSIENT` 的成功**不覆写 fix_summary**；②3 attempt 全部失败**且各次失败根因均为 LLM 瞬时**（R9-15 根因导向：fix-gen `llm_generation_failed` 或重执行 `retry_failed` 且 389←383←LLM 链——仅锚定 fix-gen 失败漏约半数形态）时**直传原触发异常**（不标 INFEASIBLE/不写终态日志/不回填计数——零观测副作用；重放不短路为期望行为：LLM 恢复后应重试，R9-17） | LLM 瞬时故障的修复手段依赖同一故障源（fix-gen 与引擎五阶段均调同一 LLM 客户端）——闭环实为拉长退避窗口而非修复代码：自愈成功时覆写会沉淀伪配方污染 CASE_GUIDED 注入面（恢复归因于时间非方案）；持续故障时误标 INFEASIBLE 会永久污染负样本库（外部瞬时故障≠任务不可行）；SRE 过载响应共识（退避+熔断而非放大调用）+「不可归因不标记」矩阵自洽原则（与 SANDBOX_START 排除同理） |

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
            # 382 且 stage=EXECUTION 且 cause∈ExecutionError 族 = 执行失败（cause 链可提取沙箱 STDERR——生产主浮现形态）
            #   cause 族过滤（R8-4）：引擎兜底 except Exception 宽捕获会把非代码缺陷异常
            #   （LLMConfigError 332 / NetworkError / StorageError / 裸异常）也包成 382-EXECUTION——
            #   infra/配置类修复不可归因（与 SANDBOX_START 同理），直传防误标 INFEASIBLE
            # 382 且 stage=SANDBOX_START = 沙箱启动失败（infra 故障，代码修复不可归因）→ 直传
            if trigger.context.get("stage") == "EXECUTION" and isinstance(trigger.cause, ExecutionError):
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
        #                       + attempt 1..k-1 失败反馈（stderr_excerpt/detail/suggested_fix_excerpt
        #                       ——动作+结果成对，R8-1：失败方案是指涉对象）
        #                       + "以下方案已失败，禁止重复" 指令)
        #       fix_strategy = CASE_GUIDED（命中 RECOVERED 且 fix_summary 非空）
        #                    / NEGATIVE_CASE_GUIDED（命中 MARKED_INFEASIBLE——负样本提示形态，
        #                      全量 3 次不缩减，R8-2）
        #                    / PURE_LLM（无命中）                          # 三分支，决策 #15
        #    c. suggested_fix = fix_gen(fix_prompt)  # 包 _call_with_retry(max_attempts=1)，
        #       # 失败计为该次 attempt 失败（detail="llm_generation_failed"），不裸穿；
        #       # 3 attempt 全失败且根因均为 LLM 瞬时（llm_generation_failed 或 retry_failed
        #       # 且 389←383←LLM 错误——R12-F2 对齐 R9-15 根因导向）→ 直传原触发异常
        #       # （决策 #17②，R8-6——LLM 持续故障≠任务不可行，零观测副作用同 abort 路径）
        #    d. hints = {stderr_excerpt, schema_violations, case_summaries,
        #               prior_attempts, suggested_fix}   # payload 契约（Task 0.12；
        #               格②命中时 case_summaries 附带负样本提示——CR-R1-6）
        #       hints_context = context.with_extension("validation_feedback_hints", hints)
        #    e. 防放大（CR-R1-3 ContextVar 形态）：capped = replace(engine._retry,
        #       max_attempts=1)（全字段保真）→ with retry_policy_override(capped):
        #       重执行 inner_chain（SSD>TOV>Engine 完整内层链——R9-14 双句柄：
        #       重执行禁走裸引擎，绕过 SSD 安全防护与 TOV 出参校验会把违规 output
        #       标 RECOVERED——389 闭环被静默架空）；with 退出自动还原——共享
        #       engine._retry 零写入（validator 校验重试经 effective 动态读同被封顶）
        #       注意：engine 句柄（封顶策略 replace 派生基线——只读）与 inner_chain
        #       句柄（重执行用）分开注入（组合根链构造上提共享，SSOT 表 R9-14 定稿）
        #    f. 成功 → recovered_count += 1 + 覆写 fix_summary（非 LLM_TRANSIENT 类——决策 #17①）
        #       + 演进日志(RECOVERED, trigger_code, duration_sec, fix_attempts[含
        #       attempt_execution_id/suggested_fix_excerpt]) + ToolExecutionRecovered 事件
        #            → return ToolResult(SUCCESS, retry_count=attempt)
        # 4. 耗尽 → 抛/捕获 ValidationFeedbackRetryExhaustedError(399) 内部信号
        #    → infeasible_count += 1（fix_summary 不动）+ 演进日志(MARKED_INFEASIBLE)
        #       + ToolExecutionMarkedInfeasible 事件
        #    → return ToolResult(INFEASIBLE, output={error_signature, stderr_excerpt, attempts}, retry_count=3)
```

**触发判定矩阵（必须完整测试，九行——R8-4 升级）：**

| 触发异常 | 编码 | 入闭环 | 理由 |
|---------|------|--------|------|
| `ToolResultValidationError` | 389 | ✅ | OUTPUT 校验基础重试耗尽——两子路径：Schema 违规（violations 直接在 context）/ LLM 瞬时故障（cause 链 389→383→LLM 错误，**violations 为空**，签名走 LLM 错误消息归一化；回填受决策 #17 双保险约束） |
| `ToolExecutionFailedError` 且 `stage="EXECUTION"` 且 **cause ∈ ExecutionError 族** | 382 | ✅ | 沙箱内代码执行失败（**生产装配下 STDERR 的主浮现形态**——cause 单跳到 313，见下方浮现路径）；含 316/317（ExecutionError 子类经兜底包装；318 非族成员——继承 SandboxError，R12-F1）；**316 可修复性论证（R8-22）**：沙箱超时（单次执行 wall-clock cap）经算法优化/资源调整可恢复，区别于 385（引擎总预算已含全部重试余量耗尽，重试无余量）——两者测量层不同（沙箱 cap vs 引擎总预算），处理差异成立 |
| `ToolExecutionFailedError` 且 `stage="EXECUTION"` 且 **cause ∉ ExecutionError 族** | 382 | ❌ 直传 | **兜底宽捕获混入形态（R8-4 新增行）**：引擎兜底 `except Exception`（`:253-266`）把五族直传组外的一切异常无差别包为 382-EXECUTION——`LLMConfigError`(332，配置类——实测 `ExternalException` 子类不落直传组 `ConfigurationError` 分支)/`NetworkError`(102)/`StorageError`(103)/引擎自身解析 bug 等裸异常。**基础设施/配置类故障非代码缺陷**（与 SANDBOX_START 排除同理：修复不可归因 + 误标 INFEASIBLE 污染负样本库），且存储类故障时演进日志/案例库同样不可写（闭环对存储故障的响应路径自身不可持久化）——分类边界由 cause 链根因而非 stage 字段决定 |
| `ToolExecutionFailedError` 且 `stage="SANDBOX_START"` | 382 | ❌ 直传 | 沙箱启动失败（312/315 容器/镜像）——基础设施故障非代码缺陷，LLM 修复不可归因（3 次注定失败的修复尝试纯耗 LLM 配额且误标 INFEASIBLE） |
| `ToolExecutionTimeoutError` | 385 | ❌ 直传 | 引擎总预算超时不可修复（重试同样超时——预算已含全部重试余量） |
| `BusinessRuleViolationError` | 207 | ❌ 直传 | 白名单策略违规，非代码缺陷 |
| `ValidationError` | 201 | ❌ 直传 | 标记语法错误，非运行时可修复 |
| `DataSourceError` 族 | 410-413 | ❌ 直传 | 外部数据不可用，4.1b 语义"策略违规 vs 数据不可用"区分 |
| `ToolSchemaMissingError` | 398 | ❌ 直传 | required_schema 缺失，配置问题非代码缺陷（4.3 定义、4.7 消费契约） |

> **矩阵外直传成员注记（R8-29）**：引擎直传组 `except (BusinessRuleViolationError, ValidationError, DataSourceError, ConfigurationError, TimeoutError)`（`:242`）实际另含 `ConfigurationError`(101，398 的父类) 与领域 `TimeoutError`(302) 两成员——VFD 不捕获自然上浮，行为与矩阵排除语义一致（101 含于 398 行/ConfigurationError 族语义、302 含于超时族语义），测试枚举按族覆盖即可，不单列行为差异行。

> **STDERR 实际浮现路径（防困惑，重要——生产装配语义）**：生产装配经 `build_tool_execution_engine`（`tool_execution_engine.py:569-578`，组合根 `:2330-2333`）把引擎重试白名单收窄为 `(LLMAPIError, LLMResponseError, TimeoutError)`——**`ExecutionError`(313) 不在白名单**（`:558-560` 注释：沙箱确定性失败重试无意义）。因此：
> - **主路径（STDERR 场景）**：313 → 引擎兜底 `except Exception`（`:253-266`）包成 `ToolExecutionFailedError(382, stage="EXECUTION", cause=313)`（自定义 `cause` 属性，非 `raise from`）→ 382 不在 validator 白名单（`tool_output_validator.py:201-204`）直浮 → SandboxSecurityDecorator 解包发事件后原样上浮（`sandbox_security_decorator.py:190-195`）→ VFD 捕获入闭环。STDERR 提取 = `382.cause`（自定义属性单跳）→ `ExecutionError.context["stderr"]`（AC-1 修复后携带）。
> - **次路径（LLM 瞬时故障）**：LLMAPIError/LLMResponseError/TimeoutError 可重试 → 引擎 3 次耗尽抛 383（`retry_helpers.py:112-117`，`cause=last_exc` 自定义属性）→ validator 白名单含 383 再重试 3 次耗尽 → **转 389 抛出**（`tool_output_validator.py:223-229`，`from retry_exc` 设 `__cause__`）。链形态 `389.__cause__ → 383.cause → LLM 错误`——**无 STDERR 无 violations**，签名走 LLM 错误消息。
> - **单测直构形态注意**：裸构造 `ToolExecutionEngine()` 用默认 `RetryPolicy`（**含** ExecutionError，`retry_helpers.py:54-59`）时 313 会被引擎重试——单测构造主路径 382 场景须用生产白名单形态或直接构造 382。
> - **兜底宽捕获边界（R8-4，触发判定 cause 族过滤的依据）**：兜底 `except Exception`（`:253-266`）的捕获范围 = 五族直传组（`:242`）之外的一切——不只 ExecutionError 族，还包括穿透 `_retry` 白名单的 `LLMConfigError`(332)/`NetworkError`(102)/`StorageError`(103) 及引擎自身代码 bug（裸 KeyError 等）。这些异常同样被包成 `382(stage="EXECUTION")`，但根因是 infra/配置类故障而非沙箱内代码缺陷——**stage 字段不区分根因，触发判定必须加 cause 族过滤**（矩阵第 2/3 行），否则矩阵排除 398/SANDBOX_START 的「配置/infra 不可归因」理由被兜底宽捕获系统性破坏。
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
    fix_summary       VARCHAR(2000) NOT NULL DEFAULT '',  -- 仅 RECOVERED 且非 LLM_TRANSIENT 路径覆写（决策 #17）
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
8. **封顶策略的派生纪律（CR-R1-3 机制演进）**：封顶必须由引擎**原策略 `dataclasses.replace` 派生**（保留 retryable_exceptions/backoff/duration 全部字段——重建默认 `RetryPolicy()` 或只传白名单会把 backoff/duration 静默重置默认值，且默认白名单含 313 偏离生产收窄形态）；经 `retry_policy_override`（ContextVar per-task）覆盖传递，**禁直接写入 `engine._retry` 共享属性**（`clear_scoped` 生产未接线→SCOPED 实为进程级共享，保存/恢复交错可致 `max_attempts` 永久=1——CR-R1-3 竞态机理）。
9. **禁止 `# noqa`/`# type: ignore`**：三条 grep 自查零输出后才可提交。
10. **性能计时口径**：P95 基准的计时窗口排除 LLM/沙箱调用（端口级计时代理包裹仓储 + mock 替身注入真实挂起点 `await asyncio.sleep(0)`——4-5 R2-F02 原语义为制造挂起点）；P95 分位断言用 `statistics.quantiles` + 分级断言（达标 assert / 不达标 skip 留证据，4-6 `test_tool_version_integration.py:398-415` 先例）。
11. **ExecutionError 子类兼容**：新构造器必须透传合并 `context`——`SandboxTimeoutError`/`SandboxResourceLimitExceededError` 的 `super().__init__(reason, context={...})` 不改即炸（Task 0「修改的既有异常」契约）。
12. **既有 4 值边界断言**：`test_tool_execution_values.py:114-121` 在加 INFEASIBLE 后必红——属预期红（证明边界断言活着），与枚举加值同 commit 更新为 5 值。
13. **单测构造 382 主路径**：裸构造引擎（默认 RetryPolicy 含 313）时 313 被引擎重试不走主路径——单测直接构造 382(stage=EXECUTION, cause=313) 或用生产白名单形态（Dev Notes 浮现路径节）。
14. **封顶窗口的并发边界（CR-R1-3 重写）**：旧前提「SCOPED per-request 隔离下无实害」失实——`clear_scoped()` 生产零调用，SCOPED 实例为**进程级共享**（resolver `_scoped_context` 全生命周期缓存），DAG 同波并发节点即单 scope 并发的现实形态；旧「保存→替换→恢复」形态存在交错恢复致引擎 `max_attempts` 永久=1 的竞态（并发保存到他人封顶值→finally 恢复封顶值）。**CR-R1-3 根治**：封顶经 ContextVar per-task 覆盖（VFD 重执行窗口 + TOV 校验循环双侧迁移），共享引擎状态零写入——并发连带与永久污染两个面同时消除（并发双 recover 回归测试守护 `engine._retry is 原对象`）。
15. **fallback 测试清理纪律**：outbox fallback 测试不挂 repo_session（否则触发不了 RuntimeError 分支），独立 session 写入即 commit——try/finally 按自建 event_id 集合删除自建行（Task 6 循环 C 强制项）。
16. **SessionMiddleware 未接线（R8-9 实测事实）**：`src/infrastructure/middleware/session_middleware.py`（注意实际路径在 infrastructure 非 interfaces/api）已实现但**未在 `create_app()` 注册**（`app.py:55` 仅 ExceptionContextMiddleware，全 src 零生产引用）——「HTTP 路径经 SessionMiddleware commit 存活」是设计语义而非运行事实，现状生产全部路径 outbox save 均触发 RuntimeError fallback；「有请求 session」形态的 fallback 测试需显式 `set_session()` fixture 模拟已接线形态；接线为独立技术债（deferred 登记）。
17. **兜底宽捕获的根因错配（R8-4）**：引擎兜底 `except Exception`（`tool_execution_engine.py:253-266`）把五族直传组外的一切异常（含 LLMConfigError 332/NetworkError/StorageError/裸异常）包成 `382(stage="EXECUTION")`——stage 字段不区分根因，VFD 触发判定必须加 cause 族过滤（`isinstance(trigger.cause, ExecutionError)`），否则 infra/配置故障混入闭环误标 INFEASIBLE；构造非族直传测试用例时用 `LLMConfigError` 或裸 `KeyError` 作 cause。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── error_case.py                    # [新] 错误案例聚合根
│   │   ├── evolution_log_entry.py           # [新] 演进日志聚合根
│   │   └── tool_chain_run.py                # [改] NodeRunStatus.state Literal 加 "INFEASIBLE" + docstring（R8-7/循环 E，additive）
│   ├── events/
│   │   ├── validation_feedback_events.py    # [新] 2 领域事件
│   │   └── __init__.py                      # [改] 导出
│   ├── exceptions/
│   │   ├── validation_feedback_exceptions.py # [新] EXCEPTION_399
│   │   ├── sandbox_exceptions.py            # [改] ExecutionError stderr/exit_code 参数（context 透传合并）
│   │   ├── tool_chain_exceptions.py         # [改] ToolChainExecutionFailedError 构造器扩可选参数 error_signature/enhanced_retry_count（R8-7/循环 E，additive）
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
│       ├── tool_chain_orchestrator.py       # [改] node state 三值判定（INFEASIBLE）+ FAIL_FAST cause 填充（Task 6 循环 E/决策 #14——R8-8 落点定稿）
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
| `session_context` 独立会话 | `src/infrastructure/storage/postgresql/session_context.py:99-132` + `messaging/outbox/outbox_processor.py:146-155` 先例 | outbox fallback 修复复用（注意实际路径在 `messaging/outbox/` 子目录） |
| `ToolExecutionQuery` Query Object 先例 | `src/domain/ports/tool_execution_repository.py:24` | EvolutionLogQuery 同款模式 |
| 4.3 订阅契约设计 | `stories/4-3-tool-io-schema-validation.md:1600-1669`「4.6/4.7 架构演进路径」 | 事件字段消费方式参照（去重键/is_final/schema_version 防漂移） |
| 端口契约测试 11 维度样板 | `tests/contracts/test_port_contract_tool.py` | 新契约测试同款结构 |
| 事件通道映射契约样板 | `tests/contracts/test_event_channel_mapping_tool_version.py` | 同款逐字段断言 |
| fire-and-forget 事件发布 + violations 截断 helper | `src/application/services/schema_event_helpers.py`（`publish_schema_event_async`/`truncate_violations_for_event`，P0-H/P0-I） | 新事件发布复用同款模式（不阻塞主流程 + 截断防 DoS） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-6](./4-6-tool-version-management.md)（done）+ [Story 4-5](./4-5-red-blue-debate-basic.md)（done）+ [Story 4-3](./4-3-tool-io-schema-validation.md)（done）

**关键学习/Key Learnings:**
- 4-3 P0-1：装饰器重试与 Engine 内部重试叠加 → 81x LLM 调用放大触发超时（4.3 时代威胁模型）——增强循环必须封顶内层全部重试（引擎 + validator 两层 max_attempts=1；**CR-R1-3 机制演进：ContextVar per-task 覆盖替代共享属性替换/恢复**——SCOPED 实为进程共享，写入式封顶有交错恢复竞态）
- 4-5 R1-F01：事件 metadata 携带 UUID 对象 → json 序列化 TypeError → reliable 通道 100% 静默失败——字段一律 str 化
- 4-6 CR1-4：PG UNIQUE 冲突后 PendingRollback → begin_nested SAVEPOINT 包裹容错重读
- 4-6 R3-1：应用层禁止 import infrastructure（import-linter 契约）——注入端口/标量，outbox 修复落 infrastructure
- 4-5 R1-F06/R2-F01：Fake LLM 禁按易混淆子串分派（按 response_schema/system_prompt 角色标记）；mock 需真实挂起点（asyncio.sleep）
- 4-6 文档审查 R1 系列：规范内部矛盾/死锁/不可达是 P0 高发区——Task 0 触发判定矩阵必须完整无死角
- 4-6 留项登记纪律：defer 项显式登记留痕（本 Story 兑现 399/事件字段/reliable 通道/outbox session 四笔预留债）

**应用到本故事/Applied to This Story:**
- [ ] 增强循环防放大（两层封顶 + ContextVar 覆盖 + 引擎零写入——CR-R1-3 机制演进，AC-2 硬性验证项）
- [ ] 事件字段 str 化 + InMemory deepcopy + SAVEPOINT 容错（实现陷阱清单）
- [ ] 触发判定矩阵九行全覆盖测试（回归网先行——R8-4 九行口径）
- [ ] 四笔预留债逐项清偿并在原注释处更新状态（outbox defer 注释按形态①已修复/形态②登记 deferred-work 更新）
- [ ] 既有 4 值边界断言 4→5 联动（证明边界断言活着）
- [ ] 修复 prompt 跨尝试反馈（决策 #12——防同分布重复失败修复）

### 非目标（Out of Scope）

- ❌ **工具熔断**（or.md 四.7.(3)"连续 3 次校验失败自动熔断"——:315，属「四、AGENT」章第 7 节）——不在本 epic AC 清单，与反馈闭环正交；**登记 `deferred-work.md`**（建议挂 Story 5.x Agent 弹性隔离或独立运维 Story）。注：签名级 fast-fail 的**信息注入半边**（同签名 infeasible_count 高时注入负样本提示）**属本 Story AC-5 已含**；**尝试缩减半边（命中高不可行签名时降低 attempt 上限）R8-2 定稿为 deferred**——V1 全量 3 次（AC-5 注记：保证 infeasible 统计口径一致 + 避免 attempt 上限参数 K 的调参成本；Temporal non-retryable 跳过重试的业界立场在真实负样本效用数据（R8-32 对照基线）落地后再采纳），与工具级熔断一并登记不连带 defer
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

### 开发实施记录 Dev Execution Notes（dev-story）

**Task 0 实施留痕（2026-10-09）：**

- **代码调研**：4 并行调研 Agent（引擎/重试/校验链 + 沙箱/装饰器/STDERR 链 + 异常/事件/通道体系 + 存储/编排器/组合根/测试风格），Story 全部关键锚点实证命中（少量 2-6 行偏移内容在位：build_tool_execution_engine def 在 :551、TOV 389 抛出体 :223-229、组合根装饰链 :2341-2378）。环境探活：PG postgres@localhost:5432/sisys 可连（public schema 22 表齐备）+ Redis 可用。
- **P95 口径留痕（Subtask 0.11，决策 #11）**：epics 字面「单次重试延迟 P95<5s」在 LLM 修复生成场景物理不可达（`LLMConfig.timeout` 默认 600s 支配生成时长）——可测化口径定为「**闭环自身开销 P95<5s**（错误签名提取 + 案例查询 + 演进日志写入，**不含** LLM 修复生成与沙箱执行时长）」。机制有效性指标（成功率 ≥80%/准确率）语义为 mock 可编程序列下的**编排机制正确性**度量而非真实修复能力（真实观察基准登记 deferred-work）。按 Task 0 与业务方确认流程：本留痕即实施口径基线，epics 硬指标的测试落点在 Task 7 `test_validation_feedback_integration.py` 三组基准。
- **BDD 契约要点（Task 1-6 实现须对齐）**：fix-gen 调用形态 `llm_client.generate(prompt=..., system_prompt="Validation Feedback 修复顾问...")`（system_prompt 角色标记为 Fake LLM 分派键——4-5 R1-F06）；引擎 Think/Code/Validate prompt 固定前缀（"为工具"/"基于以下计划"/"验证工具"）在 hints 拼接后必须保持稳定；`_run` 内联同循环 drain fire-and-forget 事件任务；`ErrorSignatureExtractor.extract(stderr)` / `extract_from_violations(violations: tuple[dict, ...])` 方法名契约；`extract_stderr_from_cause_chain` 从 `sandbox_security_decorator` 导出（Task 3）。
- **红窗口确认（Subtask 0.9）**：验收 .py 与 3 端口契约 + 事件契约 4 文件 collection ERROR（ModuleNotFoundError——Task 1-6 产物缺失，预期中间态）；通道映射契约 10 failed（断言红——新事件未登记，预期）；feature 无 import 即时入库（commit 1a51f164）。

**Task 1-9 实施总结（2026-10-09，dev-story 完成）：**

| Task | 提交 | 核心交付 | 测试 |
|------|------|----------|------|
| 0 SDD 规范 | 1a51f164 | feature 46 场景全枚举 + 契约测试红窗口确认 + P95 口径留痕 | 红窗口实证。**CR-R1-19 勘误：feature 实为 42 场景**（AC 枚举逐条合计 3+20+4+4+4+4+1+2=42，feature 文件与 pytest 实数一致——「46」无出处，提交信息历史不改） |
| 1 领域模型 | ead48778 | ErrorCase/EvolutionLogEntry/FixAttempt/签名提取器/INFEASIBLE 枚举（4→5 值联动） | 86 用例 |
| 2 事件与异常 | f4d6d433 | 两事件 + 399 五处登记 + ToolSchemaValidationFailed reliable 升级 + 双通道登记 | 161 用例 |
| 3 STDERR 数据链 | 94b903df | ExecutionError 构造器增强 + adapter 填充 + 装饰器事件填充 + cause 链提取 helper | 20 用例 |
| 4 仓储双实现 | bbbbe3c1 | 双端口 + InMemory/PG + migration 017（upgrade/downgrade 对称实证）+ 组合根注册 | 55 用例 |
| 5 闭环编排 | 59f16d0a | 触发九行/五格分类/跨尝试反馈/防放大/幂等/#17② 根因导向直传 | 37 用例 |
| 6 装配与修复 | dc953cbe | VFD 装饰器 + v1.4.0 装配 + outbox fallback + id 全链同源 + 编排器三值（循环 A-E） | 2074 回归 |
| 7 集成与基准 | c35c2c74 | 全链闭环（真实 PG）+ 幂等 + P95/成功率/准确率三组基准（epics 硬路径） | 6 用例 |
| 8 架构验证 | 5be77ec8 | 五项验证器 + 8.6 INFEASIBLE×FAIL_FAST 守护 + 循环依赖检测（epics 硬路径） | 17 用例 |
| 9 收尾验收 | （本提交） | 收尾场景 ×2 + 全量回归 + 红线自查 | 42 验收场景全绿 |

**DoD 最终核验：**
- 全量回归 `pytest tests/ -n 8`：**11873 passed / 21 failed（全部预存量或环境性——OCR 文件依赖/GPU CI 配置断言/Docker daemon/Qdrant 并发竞争，均不在 4.7 变更集，hybrid_search 单跑通过实证并行资源竞争）**
- 验收测试 42/42 全绿（含收尾 src/tests 清单场景——42 文件存在性+可导入性断言）
- `ruff check src/ tests/` 全过；`mypy src/` 653 文件零错误
- 三条异常红线 grep：4.7 变更集零命中（strategic_archive/ocr_cli/equilibrium_security/inmemory_event_listener 等命中项为预存量，git diff 8e41dc00..HEAD 实证不在变更集）
- 覆盖率：domain ≥90%/application ≥85% 由全量回归维持（--cov 门禁在 CI 全量跑）
- deferred-work.md 登记 13 项（Story 收敛声明清单全部落账。**CR-R1-19 勘误：实勘 12 项**——第 13 项「400-409 扩域触发条件注释更新」已在异常 docstring 与设计文档 :718 行内完成、未入 deferred 清单）

**实施中的关键调试发现（BDD 验收阶段）：**
- `_drain` 死锁：fire-and-forget drain 未排除 current_task → gather 等待自己（修复：自排除）
- Fake LLM 分派：system_prompt 判定须 `startswith`（FIX_SYSTEM_PROMPT 是完整句子而非裸标记）
- 签名口径漂移：BDD 预置案例签名须与真实 JsonSchemaValidator violations 同形态计算（否则案例虚不命中）
- `fail_remaining=3` 非 9：TOV 校验重试期间无条件封顶引擎（4.3 P0-1）→ 每轮 TOV 仅 1 次 think
- #17② 判定升级：except 块内 raise 的 `__context__` 回指外层触发异常，叶子判定走偏 → 改链上成员判定 `_chain_contains_llm_transient`（R10-2「链中 last_exc」谓词语义的忠实实现）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-7-validation-feedback-loop.md`

**待创建的文件/To Be Created (Dev Story 实施):**

*src 生产代码（18 新 + 17 改）+ deploy/configs/docs（1 新 + 2 改）：*
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
- 修改：`value_objects/tool_execution.py`（INFEASIBLE + docstring 5 值）、`sandbox_exceptions.py`（ExecutionError 增强）、**`entities/tool_chain_run.py`（NodeRunStatus.state Literal 加 "INFEASIBLE" + docstring——R8-7 补登记/Task 6 循环 E）**、**`tool_chain_exceptions.py`（ToolChainExecutionFailedError 构造器扩可选参数 error_signature/enhanced_retry_count + context 契约——R8-7 补登记/循环 E，Task 0「修改的既有异常」契约）**、`_code_ranges.py`、`exceptions/__init__.py`、`exception_handlers.py`（399→422）、`events/__init__.py`、`aiodocker_sandbox_adapter.py`（stderr 填充）、`sandbox_security_decorator.py`（事件填充 + cause 链提取导出）、`tool_execution_engine.py`（hints + defer 注释清偿 + **聚合 id 优先读 schema_execution_id**——决策 #16/Task 6 循环 D）、**`tool_output_validator.py`（类 docstring :58 历史漂移顺带修正——声称"重试耗尽构造 FAILED ToolResult"实际直接 raise 389，R8-33 独立登记）**、`tool_execution_service.py`（**链入口条件注入 schema_execution_id**——决策 #16/R8-16，~2 行）、`tool_chain_orchestrator.py`（R6/**Task 6 循环 E（R8-8 落点定稿）**：`:637` node state 三值判定支持 "INFEASIBLE" + `:218-224` FAIL_FAST 异常 context 填 error_signature——决策 #14 两缺口修复）、`channel_router.py`、`composition_root.py`（3 端口 + v1.4.0 + **链构造上提共享双句柄**——R9-14）；configs 改 `configs/event_channels.yaml`；docs 改 `sisys-uni-exception-design.md`（两表 + :805/:807 连带 + **393 行 context 扩展键注记**——R8-7）；infra 改 `messaging/outbox/outbox_repository.py`（fallback 独立 session）

*测试（24 新 + 4 改）：*
- `tests/acceptance/test_acceptance_validation_feedback_loop.feature` + `.py` - 验收 Gherkin + BDD
- `tests/unit/architecture/test_validation_feedback.py` - 架构测试四项（epics 枚举）+ 8.6 INFEASIBLE×FAIL_FAST 守护（第五项——R9-3 补）
- `tests/integration/test_validation_feedback_integration.py` - 集成 + 性能基准（epics 硬路径）
- `tests/unit/domain/entities/test_error_case.py`、`test_evolution_log_entry.py`
- `tests/unit/domain/services/test_error_signature_extractor.py`
- `tests/unit/domain/value_objects/test_tool_result_status.py`
- `tests/unit/domain/events/test_validation_feedback_events.py`
- `tests/unit/domain/exceptions/test_validation_feedback_exceptions.py`
- `tests/unit/infrastructure/external_services/sandbox/test_aiodocker_adapter_stderr.py`
- `tests/unit/application/services/test_sandbox_security_decorator_events.py`、`test_validation_feedback_service.py`、`test_validation_feedback_decorator.py`、`test_tool_execution_engine_hints.py`、`test_tool_chain_orchestrator_infeasible.py`（循环 E 三断言——R8-8）
- `tests/unit/application/services/test_execution_id_same_source.py` - execution_id 全链同源六断言（**代码审查周期 CR-R1-4 补交**——循环 D 承诺测试 dev 期缺位）
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
3. [x] Architecture constraints extracted 架构约束已提取（含 17 项关键架构决策——决策表 #1~#17，其中 #14/#15 为文档审查 R2/R3 增补、#16 为 R7 增补、#17 为 R8 增补）
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
| R1-6 | 防放大不完整且蓝图不可实现（validator 校验重试未封顶 9x；VFD._wrapped 是 SSD 无 _retry；frozen 整体替换/按引用恢复缺失） | P1 | 两层封顶 + 保留原 retryable_exceptions + 按引用恢复 + 组合根注入 engine 引用穿透（决策 #8 改写。**CR-R1-3 机制演进**：代码审查周期定稿 ContextVar per-task 覆盖形态——并发竞态根治，见决策 #8/陷阱 8/14） |
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
| R2-7 | INFEASIBLE 结果化使 FAIL_FAST 策略失效（异常路径→结果路径，兄弟节点照常执行）零登记 | P1 | AC-3 DAG 策略交互注记 + 决策 #14 + deferred-work 登记。**R6 勘误**：本行机理结论漏看波次间检查 `:208-225`——FAIL_FAST 链仍中断，真实 delta 为类型丢失/cause=None/同波跑完三件工程事，R6 业界对标已定稿修复方案（决策 #14 改写 + Task 8.6。**R8-8 落点勘误**：实施位已迁移 Task 6 循环 E，8.6 定稿纯守护断言） |
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
| R3-11 | 并发 outcome 次序竞态未登记 + fallback 须直调 get_session()（经 property 得 InvalidStateError，catch 不命中） | P3 | 已知行为登记 + 实现精度注记入 Task 6 循环 C 绿。**R8-34 勘误**：InvalidStateError 分叉仅存在于 `PostgreSQLAdapter._session`（catch RuntimeError 重包）；`PostgreSQLOutboxRepository._session` property 现状即直调 `get_session()` 无包装（抛裸 RuntimeError）——对 outbox repo「绕过 property」不适用，该注记仅在 fallback 复用扩展至 PostgreSQLAdapter 系时相关 |
| R6-1 | R2-7 机理结论漏看波次间检查 `tool_chain_orchestrator.py:208-225`（FAIL_FAST and failed_nodes → raise）——「FAIL_FAST 链变为继续执行」的决策 #14 前提部分失实，实际中断语义维持（INFEASIBLE 经 `:643-644` 已计入 failed_nodes） | P1 | 业界对标（K8s PodFailurePolicy FailJob / Temporal non-retryable / SF Catch）勘误定稿：中断语义维持即业界主流立场，「业务方确认」阻碍消解；AC-3 注记/决策 #14/R2-7 台账/收敛声明×2 五处勘误改写 |
| R6-2 | 真实 delta 三件工程事：node state 二值判定抹类型（Temporal re-wrap 反模式同型）/ FAIL_FAST 异常 cause=None 可观测性降级（K8s JobFailed reason 同型缺口）/ 同波兄弟跑完算力浪费 | P1 | 前两件升级纳入本 Story 实施（~~新增 Task 8 Subtask 8.6 守护验证器~~ **R8-8 落点定稿：Task 6 循环 E 红绿实施（编排器三文件——R8-7 补全 tool_chain_run.py/tool_chain_exceptions.py）+ 8.6 纯守护断言**）；同波取消为可选优化维持 deferred（禁无条件——CONTINUE/SKIP 场景本就不该取消） |
| R7-1 | R2-5 deferred 的两条设想路径均有误（ToolResult 加字段帮不到 389——抛异常不构造结果对象；ToolInputValidator 入链注入的 id 仍非聚合 id）；实地调查发现正确方案：链入口注入 `schema_execution_id`（4.3 预留 extensions 键，`schema_event_helpers.py:141-146` 第一优先级零改动命中）+ 引擎聚合 id 复用（save upsert 语义支撑校验重试同 id 重入） | P1 | 决策 #16 + Task 6 新增循环 D（Subtask 6.10-6.12 四断言）+ AC-3 注记改写 + R2-5 台账勘误 + 收敛声明移出 + 文件清单/结构树登记（`tool_execution_service.py` 1 行 + 引擎 3 行）——关闭 deferred |
| R7-2 | outbox 形态②的语义分界经实地调研厘清：HTTP 路径事务语义正确（`session_middleware.py:60-68`——领域失败经 ExceptionHandlers 转响应走 commit，仅未捕获异常 rollback）；真缺陷仅后台 session_context 路径的 FAILED 持久化连带丢失；fallback 机制可复用扩展至 `_persist_execution` | P2 | Task 6 循环 C 重构行附探针动作（实施时核查后台 worker 事务边界，结论登记 deferred-work——具备则升级）；熔断项核验 ToolExecutionQuery.state 材料齐备（纯范围决策）记入 deferred 注记。**R8-9 勘误**：路径应为 `src/infrastructure/middleware/session_middleware.py:58-71`（`interfaces/api/middleware/` 不存在）且该中间件未在 create_app 接线——「HTTP 路径事务语义正确」为设计语义非运行事实，fallback 实际覆盖当前全部生产路径（见 R8-9） |
| R8-1 | 跨尝试反馈通道不含前次修复方案内容——`FixAttempt` 无 suggested_fix 摘要字段，prior_attempts 只传失败现象（stderr）不传失败动作，「禁止重复失败方案」指令无指涉对象，防重复机制信息上不成立（Reflexion/Self-Debugging/ChatRepair 共识为动作+结果成对反馈） | P1 | `FixAttempt` 新增 `suggested_fix_excerpt: str = ""`（截断 ≤2000）；AC-2 Then/VC、Task 0.12 payload、蓝图 b/f、Task 1 循环 A 红、Task 5 循环 B 红、决策 #12 六处联动 |
| R8-2 | 非目标注记声称「签名级 fast-fail 缩减尝试属 AC-5 已含」但正文 grep「缩减」零机制——声明失实且与矩阵排除 SANDBOX_START 的「注定失败不重试」逻辑自相矛盾 | P1 | 诚实化定稿：AC-5 负样本命中处显式「V1 全量 3 次不缩减（统计口径一致 + 免调参）+ 缩减登记 deferred」；非目标注记拆「信息注入半边已含/尝试缩减半边 deferred」两半表述 |
| R8-3 | RECOVERED 重放合成 SUCCESS 违反 `ToolResult.validate_complete()` 契约（SUCCESS 必含 evidence_package 否则 386，`tool_execution.py:271-281` 实测）且与真实成功对下游不可区分（Temporal replay / HTTP Idempotency-Key 共识：重放结果要么等价要么可辨识） | P1 | 合成结果 output 携带 `"replayed": true` 可辨识标记；AC-6 决策 #13 双重边界注记（386 交互 + 摘要性结论不承诺完整性校验） |
| R8-4 | 触发矩阵「382-EXECUTION=代码缺陷」判别式实为引擎兜底 `except Exception` 宽捕获（`:253-266`）——LLMConfigError(332，实测 ExternalException 子类不落直传组)/NetworkError/StorageError/裸异常均被包成 382-EXECUTION 混入闭环：与排除 398/SANDBOX_START 的「配置/infra 不可归因」理由自相矛盾 + 存储故障时闭环副作用自身不可持久化 | P1 | 矩阵升级九行：382-EXECUTION 按 cause ∈/∉ ExecutionError 族细分入环/直传；AC-2 VC/覆盖率门禁/Task 5 循环 A/BDD Edge Cases/蓝图/浮现路径注记/陷阱 17 七处联动；构造用例 cause=LLMConfigError |
| R8-5 | 「引擎 Code stage 是唯一代码作者，避免双作者不可归因」论证名不副实——结构实为 fix-gen 建议者+引擎作者两级，attempt 失败仍无法区分方案错误与适配偏差；且未量化每次触发 LLM 调用成本 | P1 | 决策 #9 依据精确化：措辞改「唯一代码产出作者」+ 归因局限显式接受（换取案例库/跨尝试反馈工程收益）+ 成本注记（基础 3×3 + 闭环 3×(1+五阶段)）；AC-2 Then/Subtask 0.12 联动 |
| R8-6 | LLM_TRANSIENT 子路径入闭环自举矛盾——修复手段（fix-gen+引擎五阶段）依赖同一故障源：自愈成功时覆写 fix_summary 沉淀伪配方污染 CASE_GUIDED；持续故障时误标 INFEASIBLE 永久污染负样本库（SRE 过载响应共识：退避+熔断而非放大） | P1 | 决策 #17 双保险：①LLM_TRANSIENT 成功不覆写 fix_summary；②3 attempt 全 llm_generation_failed 直传原触发异常（零观测副作用同 abort）；AC-2 VC/AC-3 VC/AC-5/蓝图 c/f/Task 5 循环 B/表设计注释七处联动 |
| R8-7 | Task 8.6 修改面传导不彻底，漏列两文件：`tool_chain_run.py:86`（NodeRunStatus.state 为 str Literal 非 Enum，`"INFEASIBLE"` 字面量传入 mypy 必红）与 `tool_chain_exceptions.py:120-129`（构造器 7 参数无 error_signature/尝试次数据位，异常契约面变更）——文件清单/结构树/8.6 均未登记，dev 按清单执行必撞墙 | P1 | 两文件补入文件清单（16 改）/结构树/「修改的既有异常」契约节（393 构造器扩可选参数 + 设计文档 393 行注记）；8.6/循环 E/AC-3 注记同步实名 |
| R8-8 | 编排器两处生产代码修复落点（Task 8.6）与 Task 8「SDD 规范验证测试，非 TDD 单元测试」性质声明冲突——Story 顶线「每个 Task 独立完成 TDD 循环禁止测试与实现分离」下修复无处合法落地 | P1 | 落点迁移：Task 6 新增 TDD 循环 E（Subtask 6.13-6.15 红绿一体，三断言先红→三文件最小实现→既有编排器回归）；8.6 定稿纯守护断言；提交策略/追溯矩阵/AC-3 注记/决策 #14/R6-2 台账落点标注六处联动 |
| R8-9 | R7「HTTP 路径事务语义正确（经 SessionMiddleware commit）」为设计语义非运行事实——实测 `create_app()` 仅注册 ExceptionContextMiddleware（`app.py:55`），SessionMiddleware 全 src 零生产引用；且引用路径 `interfaces/api/middleware/` 不存在（实际 `infrastructure/middleware/session_middleware.py:58-71`）。现状生产全部路径 outbox save 均触发 RuntimeError fallback | P1 | Task 6 循环 C 探针行勘误改写（路径 + 未接线事实 + fallback 覆盖面上调说明 + HTTP 形态测试需 set_session fixture 注记）；R7-2 台账勘误标注；陷阱 16 新增；SessionMiddleware 接线登记 deferred |
| R8-10 | 完成总结「15 项关键架构决策」计数失实（决策表实际 16 行且本轮新增 #17 后为 17 行）——v1.3.1 曾修过同类（V4-1 决策计数 11→15），R7 增量未传播该位 | P2 | 改「17 项——决策表 #1~#17（#14/#15 R2/R3、#16 R7、#17 R8 增补）」 |
| R8-11 | AC-3 主句「避免中断后续节点」与决策 #3「不中断」绝对化表述未随 R6「FAIL_FAST 仍中断」定稿回校——同一文档新旧结论并存，dev 读 #3 得「永不中断」错误结论 | P2 | AC-3 主句与决策 #3 补策略限定（CONTINUE/SKIP 不中断、FAIL_FAST 中断——指向决策 #14） |
| R8-12 | AC-6/决策 #13 幂等机制锚点「引擎每次 execute() 新铸 execution_id（:137-138）」未随决策 #16 更新——同一行号两处被描述为相反行为（无条件新铸 vs 优先读注入键兜底新铸） | P2 | 两处更新为「链入口每次 execute 注入新 id（引擎兜底新铸，决策 #16）→ 装饰器重复调用不命中幂等键」 |
| R8-13 | 「四项架构测试」四处口径（测试分类表/追溯矩阵/Task 8 关联 AC/DoD/文件清单）未随 8.6 增补更新——按 DoD 验收漏检 R6 交付物；AC-3 VC 亦无 8.6 断言面验证项 | P2 | 四处改「四项（epics 枚举）+ 8.6 守护验证器」；AC-3 VC 补两条（8.6 断言面 + LLM 持续故障例外）；追溯矩阵补 AC-3 INFEASIBLE×FAIL_FAST 行 |
| R8-14 | 收敛声明「零 P0/P1/P2 残留」与「台账合计 46 行」未反映 R6/R7 追加的 4 行台账（含 P1×3）——文档自述矛盾（该节被 R6/R7 当活文档改写过则统计应对当前状态负责） | P2 | 统计行追加「+ R6×2 + R7×2（收敛后延迟项具备度复审增量）」；最终状态段补 R6/R7 性质说明；本轮 R8 起以「第二轮审查周期」续记（见收敛声明补记） |
| R8-15 | 波次间检查只认 DAG 级 `dag.failure_strategy`——节点级 FAIL_FAST 覆盖而 DAG 级 CONTINUE/SKIP 时结果化失败不中断（无异常则 `_execute_wave` per-node 检查不可达），Story 未登记该策略判定边界 | P2 | AC-3 注记补「策略判定边界（R8-15）」：编排器既有语义非本 Story 修改面，登记已知行为 |
| R8-16 | 决策 #16 无条件注入 `with_extension("schema_execution_id", uuid4())`——未来 ToolInputValidator 入链（TIV 同键先例）时无条件覆盖使 INPUT 事件 id 与 OUTPUT/聚合 id 分裂，倒退 4.3 P0-F 一致性 | P2 | 注入形态改条件注入（`if "schema_execution_id" not in context.extensions:`）；AC-3 修复设计/决策 #16/文件清单三处联动 |
| R8-17 | 「禁止重复失败方案」纯靠 prompt 指令无机制兜底——LLM 违背指令时 attempt 间产出等价输出（Reflexion 实现真实痛点；pass@k 依赖显式温度多样化；ChatRepair 显式去重） | P2 | 登记已知边界（V1 指令级强度 + R8-1 的 suggested_fix_excerpt 已提供指涉对象）；采样多样化/相似度去重登记 deferred（避免 V1 过度工程） |
| R8-18 | stderr 模板化存在 over-merging 未登记——`<S>` 抹平引号内类型名（`'int' and 'str'` vs `'int' and 'list'` 收敛同签名），不同根因错误合并致 CASE_GUIDED 注入错误配方/负样本误伤（Sentry grouping 官方承认同款风险并提供 fingerprint 纠错通道） | P2 | AC-5 VC 已知边界登记 + 案例命中按 error_category 二次过滤缓解注记 |
| R8-19 | violations 归一化规则不完整——仅「排序去序」，未规定 path 数组索引漂移（`$.output[3]` vs `$.output[5]` 随 LLM 输出结构漂移）与 message 模板化适用，同根因分裂多行破坏「幂等前提」自称 | P2 | 规则完备化：path 索引→`<I>` + message 同套 `<N>/<S>`；Task 0 数据模型/AC-5 VC/Task 1 循环 B 红（索引漂移收敛用例）三处联动 |
| R8-20 | fix_summary「保留最佳已知修复」为虚称——机制实为最近一次成功覆写，recency≠best（历史 10 次稳定配方被第 11 次侥幸新配方永久覆盖且不可回退；ExpeL 为跨轨迹归纳聚合） | P2 | 措辞诚实化「最近一次成功修复」+ 进阶聚合登记 deferred |
| R8-21 | duration_sec「MTTR 等价物」口径未定义（起止点/是否含 fix-gen/与 P95「闭环自身开销不含 LLM」的关系）——两口径并存无区分声明，运维解读矛盾；从 recover() 起算则 MTTR 系统性低估（不含基础重试） | P2 | AC-4 口径定稿：recover() 进入到终态返回墙钟（含 fix-gen 与重执行、不含基础重试阶段）+ 与 P95 口径的显式区分声明 |
| R8-22 | 316（沙箱超时）入闭环与 385（引擎总预算超时）排除——同义失败形态相反处理无论证（385 排除理由成立则 316 大体也成立，反之亦然） | P2 | 矩阵 316 行补可修复性论证：沙箱单次执行 cap 经算法优化可恢复 vs 引擎总预算已含全部重试余量耗尽——测量层不同处理差异成立 |
| R8-23 | SSOT 端口表 `tool_execution_service` 升级行为描述未含链入口注入（决策 #16 的行为变化）——同表 validation_feedback_service 行粒度含实现要点，对称缺位 | P3 | 升级描述补「+ execute 入口条件注入 schema_execution_id」 |
| R8-24 | R7-1 台账修复方案枚举漏列两个实际修订位（追溯矩阵 AC-3 行新增 / Task 6 DoD 同源条目）——留痕不全 | P3 | 本行登记补全（R7-1 实际修订位以正文为准：决策 #16/循环 D/AC-3 注记/R2-5 勘误/收敛声明/文件清单/结构树/追溯矩阵/DoD 九处） |
| R8-25 | v1.5.0 说明「#2（389 回链）」「#4（outbox 形态②）」编号指代无锚点——deferred 段无序号标记，读者需自行数序还原 | P3 | 改写为内容指代（「389 回链项」「outbox 形态②项」），随本轮收敛声明补记一并消除歧义 |
| R8-26 | `FixAttempt.attempt_execution_id` 注释「该次重执行引擎新铸 id」与决策 #16 后的 id 来源（入口注入或引擎兜底）未对齐——每 attempt 独立新 id 语义不变，仅注释精度 | P3 | 注释改「入口注入或引擎兜底新铸（决策 #16 语义下）」 |
| R8-27 | 提交策略「按 8.2-8.5 断言对象不得早于 Task 6」未覆盖 8.6（R6 增补时漏改） | P3 | 改 8.2-8.6 + 8.6 断言对象（编排器三文件）落循环 E 批注记 |
| R8-28 | AC-4 VC「完整修复超出本 Story 范围」绝对化与 R7 探针「具备则升级」口径张力——两份处置指令不一致 | P3 | AC-4 VC 补探针升级口径对齐注记 |
| R8-29 | 矩阵枚举不完备——引擎直传组实际含 101（398 父类）/302 两行未列（行为一致无风险，但「全覆盖测试」按枚举会漏测两条真实可达路径） | P3 | 矩阵后补「直传成员注记」（101 含于 398 族、302 含于超时族，测试按族覆盖） |
| R8-30 | 签名对非确定性输出形态稳定性边界未登记——stderr 含 dict/set repr 键序不稳定、异常链（PEP 3134）中间包装层数漂移可致同根因签名分裂 | P3 | AC-5 VC 已知边界登记（低频形态 V1 不处理，deferred 随真实语料评估） |
| R8-31 | 20 样本「成功率 ≥80%」未注明置信区间（n=20、p̂=0.8 的 Wilson 95% CI ≈ [0.58,0.94]）与 mock 序列下阈值的非统计性质 | P3 | AC-7 统计口径注记补齐（真实观测需更大样本或序贯设计） |
| R8-32 | 负样本提示效用假设零度量——NEGATIVE_CASE_GUIDED 恢复率与 PURE_LLM 无对照，机制有效性不可评估（deferred 观察基准落地会踩坑） | P3 | AC-7 注记补「按 fix_strategy 分组统计恢复率作对照基线」 |
| R8-33 | TOV 类 docstring :58 与实现不符（声称重试耗尽构造 FAILED ToolResult，实际直接 raise 389——4.3 遗留漂移），循环 D 触碰该文件相邻逻辑时易误读 | P3 | 文件清单 tool_execution_engine.py 修改项附「TOV docstring 历史漂移顺带修正」（实为 tool_output_validator.py :58——实施循环 D 时核正） |
| R8-34 | R3-11 实现精度注记张冠李戴——`PostgreSQLOutboxRepository._session` property（:40-42）现状即直调 get_session() 无包装（抛裸 RuntimeError），InvalidStateError 分叉仅存在于 `PostgreSQLAdapter._session`（:60-64 捕 RuntimeError 重包）；「必须绕过 property」对 outbox repo 自身不适用 | P3 | 循环 C 绿行注记勘误细化（outbox repo 现有形态即修复靶位；InvalidStateError 分叉仅在复用扩展至 PostgreSQLAdapter 系时相关） |
| R8-35 | 锚点微偏：`test_tool_execution_values.py` 断言块实际 114-121（所引 114-120 终点少 1 行，`assert actual == expected` 在 :121） | P3 | Task 1 循环 C 红行锚点改 114-121 并注明两断言行号 |
| R8-36 | 锚点微偏：`session_context` 实际 99-132（所引 97-132 起点偏 2 行）+ outbox_processor 先例实际 146-155（所引 148-150 为核心行） | P3 | 循环 C 绿行引用行号校准（146-155）。**R9 勘误**：AC-4/决策 #10/复用表三处同源残留本轮补校（R9-7） |
| R9-1 | R8-4 传播漏网：Task 6 循环 A 红行触发枚举仍为旧三分支口径（「382 且 stage=EXECUTION 委托」无 cause 族限定）——与蓝图 cause 过滤实现直接矛盾，装饰器层 cause∉族直传分支零测试位；另主会话 R8 后自查已补追溯矩阵 AC-2 行与应用清单行两处（R8-4 台账「七处联动」未含） | P2 | 循环 A 红行改九行口径（含 cause=LLMConfigError 构造用例）；R8-4 台账联动位补记（本轮勘误） |
| R9-2 | R8-8 声称「R6-2 台账落点标注」未执行 + 两处残留「8.6 实施修复」旧语义（R2-7 括注/收敛声明条目 7）——沿台账链追溯会得出「8.6 是实施位」的过期结论 | P2 | 三处按勘误先例补「R8-8 落点定稿」括注（R6-2/R2-7/条目 7，本轮已修） |
| R9-3 | R8-13 文件清单位漏改（仍「架构测试四项」）+ 台账行括号列 5 处却称四处 | P3 | 文件清单行补「+ 8.6 守护（第五项）」；台账计数以枚举为准（本轮勘误） |
| R9-4 | R8-25 修复零执行——v1.5.0 说明「#2/#4」编号指代原样存在 | P3 | 「#2（389 回链）」→「389 回链项」、「#4（outbox 形态②）」→「outbox 形态②项」（本轮已修） |
| R9-5 | R8-14 声称「最终状态段补 R6/R7 性质说明」实际落在统计段——最终状态段零改动 | P3 | 最终状态段补第一轮/R6R7 性质说明 + 第二轮周期续记（本轮已修） |
| R9-6 | R8-35 锚点 114-120 残留两处（AC-3 VC/陷阱 12）——只改了 Task 1 循环 C 红行 | P3 | 两处同步 114-121（本轮已修） |
| R9-7 | R8-36 锚点残留三处（AC-4 先例引用/决策 #10/复用表——复用表 97-132 恰为问题陈述点位却未修） | P3 | 三处分别校准 146-155/146-155/99-132+146-155（本轮已修） |
| R9-8 | R8-11 半执行——决策 #3 已补限定但 AC-3 主句「避免中断后续节点」绝对化未改 | P3 | 主句补策略限定括注（本轮已修） |
| R9-9 | R8-33 挂靠错位——TOV docstring 修正挂在 engine 文件名下（:58 属 tool_output_validator.py），且该文件未入修改清单（实际 17 改非 16 改） | P3 | `tool_output_validator.py` 独立登记为修改项（16→17 改，本轮已修） |
| R9-10 | R8-16 条件注入未传播循环 D——四断言无「预置 id 不覆写」负分支；行数口径（1 行→条件形态 ~2 行）漂移 | P3 | 循环 D 红补第⑤断言 + 行数口径校准（本轮已修，并入 R9-19 断言精度重写） |
| R9-11 | R3-11 台账行残留被 R8-34 推翻的机理表述（「经 property 得 InvalidStateError」对 outbox repo 不成立）无勘误标注 | P3 | R3-11 行尾补 R8-34 勘误括注（本轮已修） |
| R9-12 | 收敛声明·演进条目 1/4 残留 R8 前口径（「8 行化」阿拉伯数字逃过 grep/「单一代码作者」为 R8-5 判定名不副实的原措辞） | P3 | 条目 1 补「R8-4 后九行」、条目 4 对齐决策 #9 现行文本（本轮已修） |
| R9-13 | attempt 面异常分类与触发面九行判定不对称——mid-attempt 浮出 382(cause∉族)/382-SANDBOX_START/SSD 守卫异常/101/302 行为未定义：实现者自选「计为 attempt 失败」会把 infra 故障标不可行（同一 StorageError 触发前被 cause 过滤直传、闭环内却被标 INFEASIBLE——R8-4 排除理由被 attempt 侧门击穿）；中止清单缺 201；「389/382-cause∈族 mid-attempt=计为该次 attempt 失败」最自然语义全文未定稿 | P1 | AC-2 VC 对称立法：①入环谓词内异常计 attempt 失败（detail=retry_failed）；②任何不满足入环谓词的异常中止直传（含 382-cause∉族/SANDBOX_START/SSD 守卫/101/302/201）；Task 5 循环 B 红补 mid-attempt 两用例；蓝图同步 |
| R9-14 | recover() 重执行执行器未入 SSOT 注入清单——「重执行内层链」与「仅注入 engine 引用」互拆：组合根实测 engine 端口解析裸引擎、装饰链内联于 tool_execution_service lambda 无句柄——按字面单句柄实现重执行走裸引擎，绕过 SSD 安全防护（session_id 注入/并发配额/事件）与 TOV 出参校验，389-Schema 触发的闭环以「引擎未抛异常」判成功会把违规 output 标 RECOVERED（出参校验闭环被静默架空） | P1 | SSOT 双句柄定稿：engine 引用（_retry 封顶用）+ inner_chain 引用（重执行用，组合根链构造上提共享）；Task 6 循环 B 装配断言补「attempt 重执行经 SSD+TOV」；蓝图 e/AC-2 联动 |
| R9-15 | 决策 #17② 条件键于 detail=="llm_generation_failed" 三次全量合取——漏「fix-gen 成功 + 重执行 LLM 瞬时失败（389←383←LLM 链）」形态（限流抖动下 P≈0.47 与 fix-gen 失败同量级，保护面漏掉约半数目标人群），LLM_TRANSIENT 类 MARKED_INFEASIBLE 负样本照旧沉淀（#17 自己的设计依据原样发生） | P2 | 判定改根因导向：全 attempt 失败且各次根因均为 LLM 瞬时（llm_generation_failed 或 retry_failed 且 389←383←LLM 链）；依赖 R9-13 的 detail 值域定稿；AC-2 VC/决策 #17/蓝图 c 三处联动 |
| R9-16 | fix_strategy 三分支判定矩阵两个未覆盖格：①命中∧RECOVERED∧fix_summary 空（LLM_TRANSIENT 首例——#17① 不覆写+默认空串+R3-2 重放不写 → 永远空串，三分支皆不匹配实现者只能虚标，R8-32 对照基线口径歧义）；②命中∧MARKED_INFEASIBLE∧category 不匹配（签名碰撞）——R8-18 二次过滤仅为注记未升判定规则；error_category 自然键语义（首写定格/随写更新）未定稿 | P2 | 判定规则正文五格全枚举（原三分支 + 格④PURE_LLM「命中但无可注入配方」+ 格⑤PURE_LLM「碰撞命中已抑制」）；category 二次过滤升为 NEGATIVE 判定前置；error_category 定稿首写定格；AC-5 Then/Task 5 循环 B 联动 |
| R9-17 | #17② 直传路径「重放不短路」代价仅经「同款」二字间接继承——且该不短路对 LLM 瞬时故障是期望行为（LLM 恢复后重放应重试）而非纯代价 | P3 | 零终态路径重放语义显式化：两条零终态路径并列 + 「期望行为而非代价」改写（AC-2 VC，本轮已修） |
| R9-18 | INFEASIBLE 重放无 replayed 标记的不对称未登记理由（与 R8-3 自引「要么等价要么可辨识」共识名义冲突）；负样本提示文案「历史 N 次修复均失败」的 N 含重放观测计数（语义漂移） | P3 | 不对称理由登记（INFEASIBLE 无 386 契约交互/DAG 不消费 output 细节/语义等价——可辨识性无消费方）；文案改「已观测到 N 次不可行」（本轮已修） |
| R9-19 | 循环 D 断言①在 frozen context 下不可按字面实现（ExecutionContext frozen + with_extension 返回新实例——调用方 context 在 execute 后不含新键，按字面永红）+ ③ str/UUID 双轨比较未定稿 + 第三态（extensions 键非法 UUID）行为未定义（extract 静默新铸 vs 直读裸值 242，两种实现行为相反）+ 重构行漏 session_id fallback 旧形态 | P3 | 断言①改 spy 口径（录制内层收到 context）；②③ str 化比较定稿；第三态定义「读点统一经 extract 单点归一（禁直读裸值）」；重构行补 session_id fallback；绿行读点改经 extract（本轮已修） |
| R9-20 | prior_attempts 空方案条目（suggested_fix_excerpt=""——llm_generation_failed 形态）渲染规则未定义——按统一模板渲染为「方案 <空> 已失败」会误导 fix-gen | P3 | 渲染定稿：空 excerpt 条目标「未产出方案（生成失败）」不进禁止重复清单（Subtask 0.12/Task 5 循环 B 联动，本轮已修） |
| R9-21 | 测试分类表漏登 test_tool_chain_orchestrator_infeasible.py（追溯矩阵/文件清单有）——三处口径不一，按分类表核对交付会漏检 | P3 | 分类表补行（Task 6，本轮已修） |
| R10-1 | 382 主路径 BDD 场景 fixture 引擎 RetryPolicy 形态无约束——默认白名单含 313（retry_helpers.py:54-59）时 313 被引擎重试转 383→TOV→389 形态入环，场景虚过（cause 链可提取同一 stderr 连修复断言都绿，仅 trigger_code/category 与意图不符）；陷阱 13/浮现路径节均止步单测口径 | P2 | BDD 注入点清单立「fixture 引擎统一形态条款」：生产白名单 + 零退避（R10-4 并入），382 主路径触发场景必须显式构造 |
| R10-2 | 决策 #17② 根因判定谓词「LLM 错误形态」类型集合未定稿——链形态 383.cause 可能类型含 TimeoutError(引擎白名单成员)，谓词含否两写行为分叉：不含则 LLM 网络超时持续故障耗尽误标 INFEASIBLE（#17 要防的污染原样发生） | P2 | 谓词定稿 = 引擎生产可重试白名单同集 {LLMAPIError, LLMResponseError, TimeoutError}；BDD 直传场景两类型各构造一种（本轮已修） |
| R10-3 | R9-14 声称的「Task 6 循环 B 装配断言」未落入循环 B TDD 表——按表执行漏写，双句柄/防裸引擎保护架空；次生：①装配同一性（engine 句柄=inner_chain 内引擎）无断言——契约测试 _DummyResolver 每次新实例 11 维度全绿也不守护；②「链构造上提共享」落点未指明——组合根字面读法撞「组合根零私有函数」纪律（tool_execution_engine.py:553-557 注释） | P2 | 循环 B 红行补装配级断言（录制替身断言重执行到达 SSD/TOV）+ 同一性断言（id 相等）；SSOT 补工厂落点（application 域模块，组合根一行委托，本轮已修） |
| R10-4 | 零退避约束仅限定 389-LLM 瞬时子路径——389-Schema 子路径 TOV 3 轮校验重试默认退避 1s+2s（继承 delay 参数），7-8 场景累计 ~20s 纯 sleep | P3 | 并入 R10-1 统一 fixture 形态条款（零退避适用于全部子路径，本轮已修） |
| R12-F1 | ExecutionError 族成员展开错误（终审独立快扫发现）：:54 与 :942 将 318 列入族（「313/316/317/318」）——代码实证 `SandboxQuotaExceededError(SandboxError)`（sandbox_exceptions.py:140）非 ExecutionError 子类；文档内 :157/:642（正确展开 313/316/317）与 :58/:68（318 归 SSD 守卫中止直传）四处正确位与两处错误位自相矛盾——按错误位字面写测试期望将与 isinstance 谓词实现互斥（TDD 红绿冲突） | P2 | 两处删 318 对齐正确口径 + 族成员定义注记（R12 校正）；318 归位 SSD 守卫（312/318/319 直传）语义不变 |
| R12-F2 | 决策 #17② R8-6 原始谓词（detail 全量合取）残留两处：:76 AC-3 VC 与 :914 蓝图 c——R9-15 根因导向修订声称「蓝图 c 联动」未执行完整；按 :76 字面写断言会漏 retry_failed 形态（约半数保护面，R9-15 要修的漏法原样复发） | P2 | 两处补根因导向谓词对齐 AC-2 VC/决策 #17 定稿口径（本轮已修） |
| R12-F3 | validate_complete 锚点微偏：:114 引 271-281，实际函数 261-274（raise 块 268-272）——R9 轮锚点校准未覆盖此位 | P3 | 锚点改 261-274（本轮已修） |
| R12-F4 | 收敛声明统计行/最终状态段未同步 R10/R12 增量（止于 R8×36/R9 21 项）——该节经 R9-5 改写即应对当前状态负责（R8-14 判例） | P3 | 统计行续记 R8~R12 全量 + 最终状态段补全五轮计数与收敛结论（本轮已修） |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-10-09（代码审查周期 Round 1——四视角并行调研（闭环编排正确性 / 契约一致性 / 测试判别力 / 架构合规回归）+ 主会话独立探针实证 + 双评审员方案评审 + 复评「优秀」后落码）
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- 无（全部 P1/P2 项已 Patch；P3 按「成本趋零应做」随轮清偿或 Defer 登记）

#### 已修复 Patch

- [x] [4-7-P1-CR-R1-1][Review][Patch] RECOVERED 幂等重放清空修复配方：`_replay_synthetic` 以 `fix_summary=""+outcome=RECOVERED` 调 `record_case`，两仓储 merge 规则「RECOVERED 取传入值」把既有配方覆写为空串（AC-6「短路路径不覆写 fix_summary」显式违约；三方探针实证：重放后 `fix_summary=''`、`recovered_count=2`）`src/application/services/validation_feedback_service.py:594` — 重放分支先 `get_by_natural_key` 透传既有配方（镜像 #17① 分支形态）+ unit/AC-6.2 双侧补「配方存续+计数递增」断言（突变回退实证红）
- [x] [4-7-P1-CR-R1-2][Review][Patch] #17② 谓词 `__context__` 隐式链假阳性：`_chain_contains_llm_transient` 遍历 `__context__`——生产形态（recover 在 VFD except 块内被 await）下任何内层异常经 `__context__` 回指触发链，389-LLM 触发时非 LLM 根因失败被误判（该标 INFEASIBLE 的代码缺陷被直传放走；fix-gen TypeError 误标 `llm_generation_failed`）`validation_feedback_service.py:115` — 弃用 `__context__` 通道仅走显式因果（自定义 cause 属性+`__cause__`——生产链全程显式实证：引擎 382 `cause=`/TOV `raise from`/383 `cause=last_exc`）；删死代码 `_root_cause`；补生产动态上下文回归单测 4 形态（突变注入实证红）[blind]
- [x] [4-7-P1-CR-R1-3][Review][Patch] `engine._retry` 无锁竞态致进程级永久污染：`clear_scoped()` 生产零调用→SCOPED 实为进程共享，并发 recover 交错「保存→封顶→恢复」可使 max_attempts 永久=1；且封顶构造丢失 backoff/duration 配置（重置默认值）`validation_feedback_service.py:285` — 迁移为 ContextVar per-task 覆盖（`retry_helpers` 新增 `effective_retry_policy`/`retry_policy_override`；service 封顶 = `replace(engine._retry, max_attempts=1)` 全字段保真 + `with` 包裹重执行——engine 句柄转只读）；**TOV 同源同修**（4.3 遗留同款竞态：`:119-129` 写+`:217-233` 恢复改 `with retry_policy_override` 包裹校验循环）；引擎 `:500/:511` 读取改 effective、`:204` 刻意读 base 注记；防放大单测×2 改写为 effective 观测 + 新增并发双 recover 回归（gather 后 `engine._retry is 原对象`）[blind]
- [x] [4-7-P1-CR-R1-4][Review][Patch] 循环 D「execution_id 全链同源」五断言未交付（C 视角突变实验：revert 决策 #16 两处生产代码→156+ 测试全绿——Subtask 6.10 勾选与产物缺位）— 补交 `tests/unit/application/services/test_execution_id_same_source.py` 六断言（①入口注入 spy ②聚合 id 复用 ③TOV 透传 ④未注入兜底新铸（按优先级链「注入>session_id>新铸」钉死——D-P3a）⑤条件注入负分支 ⑥双未注入独立新铸），真实 ToolExecutionService/Engine/TOV + 可编程替身 [audit]
- [x] [4-7-P1-CR-R1-5][Review][Patch] `_current_trigger_code` 实例属性竞态：DAG 同波节点并发穿过同一 SCOPED service 实例（TaskGroup 实证），`:212` 写与 `_finish_*` 读跨 await 交错→演进日志 trigger_code 382/389 串扰（AC-4 基线字段失真）`validation_feedback_service.py:212` — trigger_code 显式传参至 `_finish_recovered`/`_finish_infeasible`，删实例属性与 `_trigger_code_of` [blind]
- [x] [4-7-P2-CR-R1-6][Review][Patch] 负样本提示未达引擎：Subtask 0.12「Think stage 消费 case_summaries（含负样本提示）」生产者侧未兑现——`_classify_case` 格② 返回 `([], hint)`，引擎 Think prompt 永远收不到（引擎测试手工构造恰证明消费端契约在位）`validation_feedback_service.py:433` — hints 组装处并入（`strategy==NEGATIVE_CASE_GUIDED` 时 case_summaries 追加负样本提示）；fix-gen prompt 的 case_summaries 仍传原值（防「历史成功修复案例」标题语义错标）+ 服务层断言 [edge]
- [x] [4-7-P2-CR-R1-7][Review][Patch] `_drain_safe_publish` 无强引用：asyncio 未持引用 task 可被 GC 中途回收（两事件静默丢失）`validation_feedback_service.py:75` — 模块级 `_background_tasks` set 持引 + done 回调 discard（schema_event_helpers:206-207 先例同款）[blind]
- [x] [4-7-P2-CR-R1-8][Review][Patch] `# type: ignore[attr-defined]` ×2（红线）：AsyncMock 裸挂 `calls` 属性所致 `tests/acceptance/test_acceptance_validation_feedback_loop.py:235,:442` — 根因消除：`_ScriptedLLM` 真实包装类（类型化 calls + `_LLMResponse` 轻量响应），26 调用点全量回归绿 [audit]
- [x] [4-7-P2-CR-R1-9][Review][Patch] BDD 恒真/空壳断言四则：AC-2.2（双层恒真——`EvolutionLogEntry` 无 error_category 字段且 #17② 直传零观测使 `if logs:` 不可达）；AC-5.4（then 体只断 status，「不覆写」空壳）；AC-7.1（`callable(spec.impl)` 与层叠零关系）；P95 基准（`except Exception→None`+恒真 status 断言——闭环整体崩溃仍 20 条样本全绿）`tests/acceptance/...:701,:1519,:1666` + `tests/integration/...:475` — AC-2.2 改断 #17② 直传形态（原 389+零观测副作用三断言，feature 文本与绑定串同步改）；AC-5.4 given 预置旧配方+then 断配方原样/计数递增；AC-7.1 改 `spec.impl(替身 resolver)` 解包 VFD>SSD>TOV>Engine 四层 isinstance 链；P95 改 INFEASIBLE 定向断言（脚本确定性）+删恒真；AC-2.14 补「不渲染案例注入段」内容断言 [audit]
- [x] [4-7-P2-CR-R1-10][Review][Patch] error_category 首写定格无定向断言（格② 判定前置不变量仅靠实现自律；突变改 merge 取传入值全测试面零红）— InMemory+PG 各补「异 category 二次回填后 category 不变」用例 [audit]
- [x] [4-7-P2-CR-R1-11][Review][Patch] execution_id UUID 防御不一致：`:204` 短路查询有 ValueError 守卫而 `:499/:557` 落库裸 `UUID(execution_id)`——无效串 id 在案例行已写后抛裸 ValueError（红线+INFEASIBLE 不抛双破）`validation_feedback_service.py:197` — 入口一次性归一（try UUID 失败按无 id），删死 except；补「无效串 id 不崩+日志新铸」用例 [edge]
- [x] [4-7-P2-CR-R1-12][Review][Patch] 陷阱 14 前提失实：「SCOPED per-request 隔离下无实害」被 `clear_scoped` 生产零调用证伪（SCOPED=进程共享，DAG 波次即单 scope 并发）`4-7-validation-feedback-loop.md:1019` — 陷阱 14 重写（R1-F3 机制覆盖 VFD+TOV 双侧后并发连带消除；AC-2 Then/VC/决策 #8/SSOT 表/陷阱 8/蓝图/composition_root 注释/追溯矩阵联动改写，历史台账加「机制经 CR-R1-3 演进」标注）[audit]
- [x] [4-7-P2-CR-R1-13][Review][Patch] 设计文档 393 行 context 扩展键注记漏落（File List 已承诺「声称已改实际未改」）`docs/architecture/sisys-uni-exception-design.md:712` — 编码分配表 393 行括注「context 扩展键（error_signature/enhanced_retry_count，4.7）」补齐 [audit]

#### P3 随轮清偿（成本趋零应做）

- [x] [4-7-P3-CR-R1-14][Review][Patch] B8 冗余局部 import（`tool_execution_service.py:102` `import uuid as _uuid`）— 删，用模块级 `uuid`
- [x] [4-7-P3-CR-R1-15][Review][Patch] A10 生产裸 assert（`validation_feedback_service.py:199`）— 删（ExecutionContext.tenant_id 类型契约已保证；AssertionError 绕过统一异常体系且 `python -O` 剥离）
- [x] [4-7-P3-CR-R1-16][Review][Patch] B9 签名 hex 字符集校验三处对齐（FixAttempt/EvolutionLogEntry 补 `int(,16)` 校验，与 ErrorCase 既有形态一致——报错文案自称「64 hex」而实现只查长度）
- [x] [4-7-P3-CR-R1-17][Review][Patch] B4 引擎 defer 注释残留失准口径（「HTTP 路径经 SessionMiddleware commit 存活」——R8-9 已勘误该中间件未接线）`tool_execution_engine.py:288` — 改「接线（deferred）后经请求 session 存活；当前生产全部路径无请求 session」
- [x] [4-7-P3-CR-R1-18][Review][Patch] B2 TOV 类 docstring 漂移（:58「重试耗尽构造 FAILED ToolResult」实际 raise 389——R8-33 登记 dev 未执行）— 两处 docstring 改实（类头 + execute Returns）
- [x] [4-7-P3-CR-R1-19][Review][Patch] B3/C 计数勘误（deferred-work 登记 13→12 实勘；「46 场景」→42 实勘——AC 枚举合计与 feature/pytest 实数）
- [x] [4-7-P3-CR-R1-20][Review][Patch] B5 SSOT `EvolutionLogRepositoryPort.save` 签名回写（`save(entity) -> EvolutionLogEntry`——返回保存后实体，深拷贝隔离语义受益）
- [x] [4-7-P3-CR-R1-21][Review][Patch] B6 R10-3① 断言形态回写（「装配级录制断言」以「同一性断言 + 重执行固定走 `inner_chain.execute`（结构等价）」交付——Story 描述按实改）

#### 已推迟 Defer

- [x] [4-7-P3-CR-R1-22][Review][Defer] A5 mid-attempt 389-Schema 新 violations 未进跨尝试反馈（仅 reason 字符串兜底，FixAttempt 无 violations 字段承载）— deferred，值对象扩字段涉及演进日志 schema 联动，随真实反馈质量需求评估
- [x] [4-7-P3-CR-R1-23][Review][Defer] A6 duration_sec 口径微偏（终态墙钟在副作用前计量，系统性小幅低估）— deferred，口径立法为「recover 进入到终态返回」，重构计量点需改 `_finish_*` 签名族，观测影响微小
- [x] [4-7-P3-CR-R1-24][Review][Defer] A7 格④⑤「注记」无运行时可观测载体（演进日志中与 PURE_LLM 不可区分）— deferred，fix_strategy 枚举加值涉及 PG enum 迁移
- [x] [4-7-P3-CR-R1-25][Review][Defer] A8 389-LLM 子路径签名输入为外层 389 消息（口径粗——同工具全部 389-LLM 失败收敛一个签名桶；仅影响 occurrence 聚合粒度）— deferred，随真实语料评估
- [x] [4-7-P3-CR-R1-26][Review][Defer] D-P3a 引擎聚合 id 继承 session_id 回退（`extract_schema_execution_id` 三级优先——直连+UUID session_id 时聚合 id=session_id 非「兜底新铸」字面）— 生产全路径经链入口注入不受影响；已在 CR-R1-4 断言④按优先级链钉死并注记
- [x] [4-7-P3-CR-R1-27][Review][Defer] D-P3b VFD 触发谓词绑定具体类（静态方法 import 而非端口方法——端口实现替换时判定不跟随）— deferred，提端口方法涉及接口契约与契约测试联动
- [x] [4-7-P3-CR-R1-28][Review][Defer] M4 `validation_feedback_service` 端口与 `tool_execution_service` 双链构造（同 scope 两套 TOV/SSD 实例——「上提共享」原意为共享工厂代码；端口生产零消费方，SSD 并发配额翻倍窗口仅在双链同时执行时存在）— 登记已知形态
- [x] [4-7-P3-CR-R1-29][Review][Defer] `_finish_recovered` 读-后-记 TOCTOU（fix_summary 快照与 record_case 间并发写窗口极小；计数由 repo 合并保护）— 注记登记
- [x] [4-7-P3-CR-R1-30][Review][Defer] D-P3c lint-imports 既有 BROKEN（interfaces→composition_root 两处 import，先于 4-7 存在于基线 74fe77c2——非本 Story 变更集）— 独立工程项单独立项，不属本审查周期范围（已向用户报告）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施（Task 0-9 全交付，2026-10-09）
- [x] 运行 `code-review` 进行代码审查（进行中——代码审查周期 Round 1 已清偿 P1×5 + P2×8 + 红线×1 + P3×8，见 Review Findings；R2~R5 后续轮次执行中）
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.8.0
**创建日期/Created:** 2026-10-08
**最后更新/Last Updated:** 2026-10-09（代码审查周期 Round 1）
**更新说明/Description:**
- v1.0.0: 创建故事文件（3 并行调研 Agent 代码实证 + 4 前序故事经验整合 + 4 笔预留债清偿方案）
- v1.1.0: 文档审查 Round 1——4 调研 Agent + 3 审查 Agent（正确性/一致性 + 可行性/可达性 + 科学性/方法论对标业界）收敛 42 项（P0×5 + P1×10 + P2/P3×27）：重写 STDERR 浮现路径为生产真实形态（382 主路径）、execution_id 全链提取机制定稿、签名统一 64 hex + Sentry 对标归一化、修复循环跨尝试反馈（Reflexion 共识）、outbox fallback 独立 session 重设计、触发矩阵 8 行化、防放大两层封顶、幂等副作用去重语义等
- v1.2.0: 文档审查 Round 2 回归核查——双 Agent（传播完备性 + 修复组合交互面）收敛 16 项（P1×4 + P2×8 + P3×4）+ 2 项 R1 台账勘误：389 两套 id 空间注记、outbox fallback 测试清理策略定稿、INFEASIBLE×FAIL_FAST 行为变更登记（决策 #14）、fix_strategy 三分支（决策 #15）、FixAttempt 边界形态定约、fix-gen 异常收敛、hints per-stage 消费映射、触发矩阵衍生位补齐（八行三处）
- v1.3.0: 文档审查 Round 3 单深度推演——三轮全推演（Gherkin 场景三轴 + Task 0→9 依赖干跑/提交批次 + 六条长状态时间线）收敛 11 项（P1×3 + P2×3 + P3×5）：幂等短路 record_case 定谳（R2-4 自拆修复）、Task 4/6 批次矛盾化解、abort 观测面立法与构造法、事件断言 drain 纪律、场景全枚举补齐、EXPECTED_TAGS 联动、error_category/fix_summary 来源定稿、提交策略 7/8/9 批次补全
- v1.3.1: Round 5 独立终审——五节核验全过，周期正式收敛（零 P0/P1/P2 残留）；清偿 V4-1（决策计数 11→15 锚定）/V4-2（SSOT 表补 engine 引用 + RetryPolicy 语义消歧，AC-7 联动）+ F5-1/F5-2 两项 P3 微瑕；追加文档审查周期收敛声明
- v1.4.0: R6 业界对标修订（INFEASIBLE×FAIL_FAST）——精读编排器勘误 R2-7 机理（漏看波次检查 :208-225，中断语义本就维持且为业界主流立场：K8s PodFailurePolicy FailJob / Temporal non-retryable / Step Functions 未捕获即 fail）；真实 delta 三件中前两件（node state 类型丢失 / FAIL_FAST cause=None）升级纳入实施（新增 Task 8.6 守护验证器 + `tool_chain_orchestrator.py` 两处修改登记），同波取消优化维持 deferred；「业务方确认」阻碍经对标消解
- v1.5.0: R7 延迟项具备度复审落地——389 回链项勘误 R6 前设想路径后定稿「链入口注入 schema_execution_id + 引擎聚合 id 复用」方案（发现 4.3 预留 extensions 通道 `schema_event_helpers.py:141-146` 零改动命中，~4 行改动），升级纳入实施关闭 R2-5 deferred（决策 #16 + Task 6 循环 D 四断言）；outbox 形态②项实地厘清事务语义分界（HTTP 路径经 middleware 核实正确，真缺陷仅后台路径），Task 6 循环 C 附探针动作；熔断项核验查询材料齐备记入 deferred 注记
- v1.6.0: 第二轮文档审查周期 Round 1（R8）——4 调研 Agent（编排器 R6 面/execution_id 链 R7 面/outbox·session 面/锚点存续 50 点）+ 2 审查 Agent（R6R7 增量一致性/科学性方法论）+ 主会话实测裁定，收敛 36 项（P1×9 + P2×13 + P3×14）：触发矩阵九行化（cause 族过滤防兜底宽捕获混入）、LLM_TRANSIENT 双保险（决策 #17）、跨尝试反馈补动作半边（suggested_fix_excerpt）、RECOVERED 重放可辨识标记（386 契约边界）、编排器修复落点迁移 Task 6 循环 E + 修改面补全两文件（tool_chain_run.py/tool_chain_exceptions.py）、SessionMiddleware 未接线勘误（fallback 覆盖面上调）、决策 #16 条件注入、签名归一化规则完备化（violations 索引模板化）等
- v1.6.1: 第二轮审查 Round 2（R9）回归核查——双 Agent（R8 修复传播完备性 + 修复组合交互面）+ 主会话裁定，收敛 21 项（P1×2 + P2×4 + P3×15）：attempt 面对称立法（mid-attempt 异常分类定稿——389/382-cause∈族计 attempt 失败，其余中止直传防 infra 侧门误标）、SSOT 双句柄定稿（engine+inner_chain——防重执行绕过 SSD/TOV 架空出参校验）、决策 #17② 根因导向修订（漏半数形态）、fix_strategy 判定五格全枚举（两缺格定稿）、R8 台账执行缺位 12 项勘误补齐（传播漏网/锚点残留/计数）等
- v1.6.2: 第二轮审查 Round 3（R10）单深度推演——三部分推演（BDD 场景三轴逐场景 + Task 0→9 依赖干跑/提交批次 + 六条长状态时间线逐字段终态）+ 20 余处源码实证，收敛 4 项（P2×3 + P3×1）+ 11 项「推演后不成立」裁定（VFD 递归捕获被 Python except 语义+inner_chain 结构双重排除；382-代码缺陷×LLM-持续故障交叉直传被裁定为唯一正确语义）：BDD fixture 引擎统一形态条款（白名单+零退避——默认白名单含 313 致 382 主路径场景虚过）、#17② 谓词类型集定稿（生产白名单同集——TimeoutError 排除则超时持续故障误标）、循环 B 双句柄装配断言落位（运行面守护+同一性）、SSOT 工厂落点（组合根零私有函数纪律）
- v1.6.3: 第二轮审查 Round 4/5（R11 纯验证 + R12 独立终审）——R11 零修改零提交（锚点存续 9 组实证 + 结构终验全过）；R12 五节终审（周期闭合/12 项双向取证/独立快扫/门禁/状态流转）发现并清偿 4 项（P2×2 + P3×2）：ExecutionError 族成员经代码继承树校正（318 继承 SandboxError 非族成员——两处误列删除）、#17② 旧谓词残留两处对齐根因导向、validate_complete 锚点校准、统计续记。**第二轮周期正式收敛（零 P0/P1/P2 残留），收敛声明入 Story**
- v1.7.0: **dev-story 实施**——Task 0-9 全部完成（SDD+TDD 十任务批提交：1a51f164/ead48778/f4d6d433/94b903df/bbbbe3c1/59f16d0a/dc953cbe/c35c2c74/5be77ec8 + 收尾提交）；验收 42/42 全绿 + 全量回归 11873 passed（21 失败全部预存量/环境性实证）+ ruff/mypy 全过 + 4.7 变更集红线零命中；Status → review
- v1.8.0: **代码审查周期 Round 1**——四视角并行调研（闭环编排正确性/契约一致性/测试判别力/架构合规回归）+ 主会话探针实证 + 双评审员方案评审 + 复评「优秀」后落码：清偿 P1×5（RECOVERED 重放清空配方/#17② `__context__` 假阳性/engine._retry 竞态→ContextVar 根治（VFD+TOV 双侧）/循环 D 五断言补交/trigger_code 竞态）+ P2×8（含 `# type: ignore` 红线×2 根因消除、负样本提示达引擎、BDD 恒真断言四则修正、首写定格定向断言、UUID 归一、陷阱 14 前提修正、393 注记）+ P3×8 随轮清偿 + Defer×9 登记；防放大机制演进为 ContextVar per-task 覆盖（决策 #8/陷阱 8/14/蓝图/SSOT 联动改写）

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

- 台账合计 46 行：R1×20 + R2×15 + R3×11，编号连续无缺（**R8-14 补记**：另有收敛后延迟项具备度复审增量 R6×2 + R7×2 共 4 行，性质为「收敛后复审的增量修订轮，不重开周期，其 P1/P2 发现已随当轮清偿」；**R8 起进入第二轮审查周期，新增 R8×36 + R9×21 + R10×4 + R12 终审 F×4 行见修复表——R12-F4 续记**）
- 修复点计数：R1 42（P0×5 + P1×10 + P2/P3×27）/ R2 16（P1×4 + P2×8 + P3×4，落 15 台账行——R2-15 为复合行）/ R3 11（P1×3 + P2×3 + P3×5，行点一致）
- R4 零修复（验证轮）；R5 零新增缺陷，清偿 4 项 P3（V4-1 决策计数 11→15、V4-2 SSOT 表补 engine 引用并消歧 RetryPolicy 语义、F5-1 Last Updated 日期、F5-2 epics 行号 :1398→:1395）
- 累计：69 个修复点 + 4 项收敛清偿；R5 双向抽验 12 项全部与仓库代码实证吻合

**关键设计决策演进（审查驱动）**

1. STDERR 浮现路径从错误断言修正为生产真实形态——382(stage=EXECUTION) 主路径 / 389→383 次路径双分支，触发矩阵 8 行化（SANDBOX_START 等 infra 故障排除出闭环；**R8-4 后升级九行——382-EXECUTION 按 cause 族细分**）（R1-1/R1-17）
2. execution_id 从全链悬空到提取机制定稿：外层 382 context 主 id 与演进日志幂等键同源；389 半边「两套 id 空间」显式登记为已知边界（R1-2/R2-5）
3. 错误签名统一 64 hex 完整 sha256 + Sentry 对标归一化（数值/引号串模板化 + 尾部锚定 stderr[-2000:]），三处口径同一（R1-3）
4. 修复循环跨尝试失败反馈（Reflexion/Self-Debugging 共识）+ 引擎 Code stage 唯一代码产出作者（R1-4，决策 #9/#12；**R8-1/R8-5 精确化**：反馈为动作+结果成对（suggested_fix_excerpt）/「建议者+作者」两级结构归因局限显式接受）
5. outbox 修复重设计为 fallback 独立 session——HTTP 路径事务性原子性保持、后台 RuntimeError 分支经 session_factory 落地（R1-5，决策 #10）
6. 防放大两层封顶（引擎 + TOV 校验重试）+ RetryPolicy 按引用整体恢复 + engine 引用经组合根注入穿透（R1-6/R2-15，决策 #8；SSOT 表 v1.3.1 补登记）
7. INFEASIBLE 结果化与 ToolChain FAIL_FAST 策略交互显式登记（R2-7，决策 #14；**R6 勘误**：漏看波次检查 `:208-225`，中断语义本就维持——经业界对标 K8s PodFailurePolicy/Temporal non-retryable 定稿为正确立场，类型丢失/cause=None 两缺口随本 Story 实施（**R8-8 落点定稿：Task 6 循环 E 红绿实施 + 8.6 纯守护**），同波取消优化维持 deferred）
8. fix_strategy 三分支 CASE_GUIDED/NEGATIVE_CASE_GUIDED/PURE_LLM（R2-8，决策 #15）
9. 幂等短路 record_case 分类计数与 occurrence 同步递增定谳（R3-2，化解 R2-4 自拆）
10. abort 中止路径观测面立法：零观测副作用 + 重放不短路全量重跑 + BDD 构造法禁 385（R3-3）

**deferred 登记（dev 期落 deferred-work.md）**

编排层 INFEASIBLE×FAIL_FAST 显式联动（决策 #14。**R6 勘误与移出**：R2 机理结论漏看波次检查 `:208-225`——中断语义本就维持且符合业界主流；类型丢失/cause=None 两缺口经对标定稿后**升级纳入本 Story 实施**（**R8-8 落点定稿：Task 6 循环 E 红绿实施 + 8.6 纯守护**），本 deferred 项仅余同波取消可选优化）；389 半边 aggregate 完整回链（**R7 移出**：调查勘误 R6 前设想路径，定稿「链入口注入 schema_execution_id + 引擎复用」方案——决策 #16 / Task 6 循环 D 升级纳入本 Story 实施，deferred 关闭）；中止遥测 ABORTED 第三值；outbox 后台路径「业务 session 异常回滚连带丢失」形态②（**R7 探针，R8-9 勘误**：~~HTTP 路径事务语义已核实正确~~ SessionMiddleware 未接线——「HTTP commit 存活」为设计语义非运行事实，fallback 修复实际覆盖当前全部生产路径；真缺陷仅后台路径；Task 6 循环 C 附探针动作——fallback 机制可复用扩展至 _persist_execution，结论随实施登记）；**SessionMiddleware 生产接线（R8-9 新增——独立技术债：组件已实现未装配，接线后 HTTP 路径方有事务边界，非本 Story 范围）**；**fast-fail 尝试缩减半边（R8-2/R8 新增：负样本信息注入已含，attempt 上限缩减待真实效用对照数据落地后采纳——Temporal non-retryable 立场）**；多案例加权检索与向量相似检索（L3 Qdrant）；工具熔断（or.md 四.7.(3)，建议挂 5.x——R7 核验 ToolExecutionQuery.state 过滤材料齐备，纯范围决策）；自动灰度推进与 per-version 统计视图；真实修复能力观察基准（不进 CI 门禁；**R8-32 补：按 fix_strategy 分组统计恢复率作 NEGATIVE_CASE_GUIDED 效用对照 + R8-31 样本量约束：真实观测需更大样本或序贯设计**）；**修复循环采样多样化/生成相似度去重（R8-17 新增——V1 指令级强度 + suggested_fix_excerpt 指涉对象已就位，机制性兜底待真实失败率数据）**；**fix_summary 进阶聚合（R8-20 新增——V1 为最近一次成功覆写，跨轨迹归纳/多数次验证后覆写待案例库规模支撑）**；**签名分裂低频形态（R8-30 新增——dict/set repr 键序/异常链层数漂移，随真实语料评估）**；400-409 扩域触发条件注释更新（Task 2 既定动作）。

**最终状态**

- 周期状态：**收敛（CONVERGED）**——零 P0/P1/P2 残留，4 项 P3 随本提交清偿（第一轮周期截至 v1.3.1；R6/R7 为收敛后延迟项具备度复审的**增量修订轮，不重开周期**，其 P1/P2 发现已随当轮清偿）
- **第二轮审查周期（R8 起，2026-10-09）**：收敛后复审定位——R6/R7 增量修订质量 + 前周期修复终态存续 + 组合交互面；R8 收敛 36 项（P1×9）、R9 回归核查 21 项（P1×2）、R10 单深度推演 4 项（P1×0）、R11 纯验证零项、R12 独立终审 4 项（P2×2+P3×2，随收敛提交清偿）——**R12-F4 续记后周期正式收敛，零 P0/P1/P2 残留**
- Story 状态：`ready-for-dev` 保持不变（文档审查周期不改里程碑状态）
- 下一步：运行 `dev-story` 进入实施（10 Task / SDD+TDD 融合 / 预留债 4 笔集中清偿）

### 🏁 第二轮文档审查周期收敛声明（R12 独立终审，2026-10-09）

**周期概况**

Story 4-7 于第一轮周期收敛（v1.3.1）后，因 R6/R7 收敛后增量修订（v1.4.0/v1.5.0）触发第二轮审查周期（R8~R12，v1.5.0→v1.6.3），定位为「收敛后复审：R6/R7 增量修订质量 + 前周期修复终态存续 + 组合交互面」。R12 独立终审以「不轻信 Story 自身记录、仓库实地取证」纪律执行五节核验：周期闭合甄别（3 提交链均仅触碰本文档、R11 零提交、工作区干净、零代码触碰红线守住、提交无 AI 署名）、关键修复双向取证（12 项正文声明 vs HEAD 代码逐条对照全部吻合）、独立新鲜快扫（发现 P2×2+P3×2，随本轮清偿）、三项门禁核验（递减投入/严重度递减/台账连续性全过）、状态流转判定。**结论：四项终审发现随本提交清偿后，第二轮周期正式收敛，零 P0/P1/P2 残留。**

**五轮结构与投入**

- R8：4 并行调研 Agent（编排器 R6 面 / execution_id 链 R7 面 / outbox·session 面 / 锚点存续 50 点）+ 2 审查 Agent（R6R7 增量一致性 / 科学性方法论）+ 主会话实测裁定——36 项
- R9：双 Agent 回归核查（R8 修复传播完备性 + 修复组合交互面）+ 主会话裁定——21 项
- R10：单 Agent 单深度推演（BDD 场景三轴逐场景 + Task 0→9 依赖干跑/提交批次 + 六条长状态时间线逐字段终态，20 余处源码实证）——4 项 + 11 项「推演后不成立」裁定留痕
- R11：纯验证轮（零修改零提交——锚点存续实证 + 结构终验，第一轮 R4 先例）
- R12：独立终审（五节核验）——新发现 4 项（P2×2+P3×2）随终审轮清偿（第一轮 R5 先例）

**修复统计（终审核对口径）**

- 台账合计 115 行：第一轮 46（R1×20+R2×15+R3×11）+ 收敛后增量 R6×2+R7×2 + 第二轮 R8×36+R9×21+R10×4 + R12 终审 F×4，编号连续无缺
- 修复点：R8 36（P1×9+P2×13+P3×14）/ R9 21（P1×2+P2×4+P3×15）/ R10 4（P2×3+P3×1）/ R11 零 / R12 4（P2×2+P3×2）
- P1 递减 9→2→0→0；R12 双向抽验 12 项全部与仓库代码实证吻合；R11 锚点抽验 9 组全部命中 HEAD

**关键设计决策演进（R8-R12 审查驱动，8 条）**

1. 触发矩阵九行化（R8-4/R12-F1）：382-EXECUTION 按 cause ∈/∉ ExecutionError 族细分——判别式从 stage 字段升级为 cause 链根因，防引擎兜底宽捕获把 infra/配置故障混入闭环误标 INFEASIBLE；族成员经代码继承树校正（313/316/317）
2. 决策 #17 LLM_TRANSIENT 双保险（R8-6→R9-15→R10-2→R12-F2 四轮递进）：成功不覆写 fix_summary 防伪配方 + 全 attempt LLM 瞬时根因直传防负样本库污染，谓词类型集定稿为引擎生产白名单同集
3. 跨尝试反馈补动作半边（R8-1）：`suggested_fix_excerpt` 使「禁止重复失败方案」指令获得指涉对象（Reflexion 动作+结果成对反馈）+ 空方案条目渲染规则（R9-20）
4. 编排器修复落点迁移（R8-8）：Task 8.6 → Task 6 循环 E 红绿一体 + 8.6 定稿纯守护——化解「SDD 验证测试 Task 含生产代码修改」与 TDD 顶线的冲突；修改面传导补全（R8-7：tool_chain_run.py Literal + tool_chain_exceptions.py 构造器）
5. SessionMiddleware 未接线勘误（R8-9）：实测 create_app 零注册——「HTTP 路径事务语义正确」由设计语义降为待接线事实，fallback 覆盖面上调至当前全部生产路径，接线登记 deferred
6. attempt 面对称立法（R9-13）：mid-attempt 异常分类与触发面九行完全同构（入环谓词内计失败 retry_failed / 谓词外中止直传），堵死 infra 故障经 attempt 侧门误标不可行
7. SSOT 双句柄（R9-14/R10-3）：engine 引用（封顶用）与 inner_chain 引用（重执行用）分立 + 装配级/同一性断言 + 工厂落点 application 域模块——防重执行走裸引擎静默架空 SSD/TOV 双防护
8. fix_strategy 五格全枚举（R9-16）与 BDD fixture 引擎统一形态条款（R10-1/R10-4）：消灭判定矩阵缺格虚标与 382 主路径场景虚过（默认白名单含 313）+ 退避累计 ~20s；RECOVERED 重放可辨识标记（R8-3/R9-18）

**deferred 登记（相对第一轮的增量，dev 期落 deferred-work.md）**

SessionMiddleware 生产接线（R8-9，独立技术债）；fast-fail 尝试缩减半边（R8-2，待真实负样本效用对照数据）；修复循环采样多样化/相似度去重（R8-17）；fix_summary 进阶聚合（R8-20）；签名分裂低频形态（R8-30）；其余沿第一轮清单（ABORTED 第三值、outbox 形态②探针、多案例加权/向量检索、工具熔断、自动灰度、真实修复能力观察基准等）不变。

**最终状态**

- 第二轮周期状态：**收敛（CONVERGED）**——零 P0/P1/P2 残留（4 项终审发现随本提交清偿）
- Story 状态：`ready-for-dev` 保持不变（文档审查周期不改里程碑）
- 下一步：运行 `dev-story` 进入实施（10 Task / SDD+TDD 融合 / 预留债 4 笔集中清偿）
