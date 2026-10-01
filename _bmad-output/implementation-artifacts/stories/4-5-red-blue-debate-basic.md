# Story 4.5: 红蓝辩论机制基础（单 Agent 多视角）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 产品专家,
**I want** 系统执行红蓝辩论机制基础（单 Agent 多视角，MVP 替代方案）,
**So that** MVP 阶段针对高不确定性争议议题，通过同一 LLM 以激进派（红）/ 保守派（蓝）双视角独立分析并对抗合成，输出包含共识与分歧区域的风险全景视图，替代 V1 完整多 Agent 辩论（Epic 10 Story 10.6）提前交付多视角决策价值。

### 业务价值

架构文档 GAP-CRITICAL-09（辩论质量评估器未实现）与 FR-AC-11（红蓝对抗辩论 → `src/application/services/debate_evaluator.py`，规划值未落地）长期挂账。Story 4.1a~4.4 已交付战略工具注册/执行/编排/校验/沙箱五层能力，但所有分析仍是**单视角输出**——战略规划的本质是"多视角共识构建，而非单点分析优化"（prd.md:157）。Story 4.5 在既有 LLM 基础设施（Story 3.2a `LLMClientPort`）之上补齐多视角能力：

1. **双视角独立生成**：同一 LLM 通过差异化 system prompt + 温度阶梯（红 T=0.8 发散 / 蓝 T=0.5 收敛 / 合成 T=0.2 裁决，与 FR-SP-10 V1 三阶段温度完全一致）扮演激进派与保守派，两视角**互相不可见**（独立生成，避免锚定偏差），`asyncio.gather` 并发调用压缩延迟
2. **风险全景视图**：合成阶段对比红蓝论点，输出共识区域（consensus_areas）+ 分歧区域（disagreement_areas）+ 整体风险等级 + 分化度
3. **辩论质量评估器落地**：`DebateEvaluator` 领域服务实现增益率/重复率/分化度三算法（architecture.md §7.3 终止条件的算法基础），MVP 调用分化度门控，增益率/重复率为 V1 多轮辩论（Story 10.6）预留——**GAP-CRITICAL-09 就此清偿**
4. **演进路径锁定**：DebateSession 状态机 / DebateQuality 字段（gain_rate、repetition_rate）/ 温度阶梯常量均按 V1 多轮结构设计，Epic 5（Agent 协作）与 Epic 10（完整辩论）在零破坏性变更下升级

**业务定位：** Epic 4 战略工具箱的**多视角分析层**，位于工具执行链（4.1a→4.4）之上，是 Epic 9-10 多 Agent 辩论的 MVP 前置。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md:1277-1316)（Story 4.5 + FR-ST-05）/ [`prd.md:1817`](../../_bmad-output/planning-artifacts/prd.md)（FR-ST-05 P0）/ [`or.md:241`](../../_bmad-output/planning-artifacts/or.md)（三.5.[3]）/ [`architecture.md §7`](../../../docs/architecture/architecture.md)（SYS AGENT 裁决与辩论机制）
**前置依赖:** Story 4.1a（✅ done，`LLMClientPort` 注入模式与 `RetryPolicy` 复用源）/ Story 3.2a（✅ done，`LLMClientPort` + `LitelLLMClient`，含 `LLMConfig.temperature` 分档传参）
**后续依赖:** Story 10.6（红蓝辩论完整实现，复用本 Story 的 DebateSession/DebateEvaluator/温度阶梯）/ Story 5-x（Agent 协作辩论，复用 RiskView 结构）/ Story 5.8（Agent 输出质量评估，承接视角/共识语义准确率量化）

### ⚠️ Story 范围澄清（重要）

**本 Story 范围（4.5）：**

1. **领域层值对象与枚举**：`DebatePerspective`（RED_AGGRESSIVE/BLUE_CONSERVATIVE）、`DebateTopic`（争议议题）、`PerspectiveAnalysis`（单视角分析）、`ConsensusArea`/`DisagreementArea`/`RiskView`（风险全景视图）、`DebateQuality`（质量评估结果，gain_rate/repetition_rate 字段为 V1 预留、MVP 置 None）
2. **`DebateSession` 聚合根**：状态机 IDLE→GENERATING→SYNTHESIZING→COMPLETED/FAILED + `state_version` 迁移计数（V1 乐观锁 CAS 预留——MVP InMemory 仓储幂等覆盖无冲突检测，`ToolExecution.save_with_state_version` CAS 为 V1 演进先例；复用 EXCEPTION_243 状态迁移守卫）
3. **3 个新领域异常**（EXCEPTION_420~422，新开 `debate` 子域 420-429，遵循 `data_source` 410-419 独立物理段先例）：`DebateGenerationError`(420) / `DebateSynthesisError`(421) / `DebateLowDivergenceError`(422)
4. **`DebateEvaluator` 领域服务**（纯算法、零外部依赖）：`compute_gain_rate` / `compute_repetition_rate`（字符 bigram Jaccard，V1 终止条件算法）/ `evaluate_overlap`（红蓝重叠率，MVP 门控）
5. **`DebateSessionRepositoryPort` 端口 + `InMemoryDebateSessionRepository`**（asyncio.Lock 类变量）——**不建 Alembic migration**（MVP 无历史辩论查询需求，PG 持久化随 Epic 10 审计需求落地，见"不在范围"）
6. **`DebateCompleted` 领域事件**：reliable 双通道（对齐 `ToolExecuted` 模式），同步登记 `configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS`（文件头声明"本文件 > DEFAULT_MAPPINGS，新增事件应同时更新两处"）
7. **应用层 `RedBlueDebateService`**：温度阶梯编排（红 T=0.8 + 蓝 T=0.5 并发 `asyncio.gather` → 分化度门控 → 合成 T=0.2 → 事件发布）+ `debate_prompts.py`（视角→prompt 映射，`summary_prompts.py` 的 `PERSPECTIVE_PROMPT_MAP` 同构模式）+ `debate_schemas.py`（Pydantic 结构化输出 Schema → 领域 VO 转换）
8. **`composition_root.py` 注册 3 个端口**：`debate_session_repository`（SCOPED）/ `debate_evaluator`（SINGLETON，无状态领域服务，对齐 `context_compressor` 先例）/ `red_blue_debate_service`（SCOPED，lambda 工厂注入）
9. **测试落地**（epics_v1.0.md:1306-1308 硬路径）：`tests/unit/architecture/test_red_blue_debate.py`（**无 `_arch_` 前缀，epics 硬要求，与 4-4 `test_docker_sandbox.py` 先例一致**）+ `tests/integration/test_red_blue_debate_integration.py` + BDD 验收 `tests/acceptance/test_acceptance_red_blue_debate.feature/.py`

**不在本 Story 范围（拆分到其他 Story）：**

- **多 Agent 实例化辩论**（激进/保守子智能体各自独立 Agent 实例 + SAP DEBATE 消息 + 公共黑板）→ Epic 5 Story 5.11（SAP 协议）与 Epic 9-10；MVP 为单 Agent 双视角（prd.md:456 明示"MVP 用单 Agent 多视角分析替代"）
- **多轮结构化辩论**（最多 5~7 轮、三阶段温度随轮次推进、JSON 补丁强制提交）→ Epic 10 Story 10.6（FR-SP-10）；MVP 单轮（红蓝各 1 次 + 合成 1 次 = 3 次 LLM 调用），`DebateQuality.gain_rate/repetition_rate` 字段与 `DebateEvaluator` 双算法为其预留
- **SYS AGENT 裁决五维评分与三套方案生成**（Plan A/B/C、置信度 0.4/0.6 分档、人工介入）→ Epic 10；MVP 合成阶段直接输出共识/分歧，不做裁决仲裁
- **辩论会话 PG 持久化与历史查询** → Epic 10（辩论审计需要时新增 migration）；MVP InMemory 仓储
- **"高不确定性议题自动启动辩论"**（or.md 三.5.[3] 自动触发）→ Epic 5/6 工作流集成；MVP 由调用方显式调用 `run_debate()`
- **辩论过热保护/成本熔断联动**（or.md 四.8.[4] 第五层熔断）→ Epic 11 成本熔断体系；MVP 仅 per-call timeout 上限保护
- **视角/共识语义准确率量化评估体系**（≥90%/≥85% 的数据集回溯验证）→ Story 5.8（Agent 输出质量评估）；本 Story 交付 CI 可验证代理指标（详见 AC-9 性能验收策略）

**复用决策（依据 R1~R3 规则）：**

- **R1 复用**（既有，不修改）：
  - `LLMClientPort`（`src/domain/ports/llm_client.py`）——`structured_generate(prompt, response_schema, config, system_prompt)` 完整覆盖辩论需求（temperature 经 `LLMConfig.temperature` 分档传参、system_prompt 承载视角角色、Pydantic schema 驱动结构化输出），**不扩展端口**（多轮历史拼入 prompt 字符串，`ToolExecutionEngine` 同款做法）
  - `LitelLLMClient`（基础设施层唯一实现，含熔断器 + 指数退避重试 + 多策略 JSON 解析）
  - `ExecutionContext`（`src/domain/value_objects/tool_execution.py`，会话/追踪上下文）
  - `EntityValidationError`(EXCEPTION_242) / `EntityStateTransitionError`(EXCEPTION_243)——VO 不变量与状态机守卫，**不新增编码**
  - `DomainEvent` 基类（`src/domain/events/base.py`，`event_type` 自动注册 + `object.__setattr__` 填 aggregate 惯例）
  - `register_port` / `PortSpec` 10 字段 / `Resolver`（注入链全程复用）
- **R2 组合注入**（应用层端口组合 R1 基础端口）：
  - `RedBlueDebateService.__init__(llm_client: LLMClientPort, evaluator: DebateEvaluator, session_repository: DebateSessionRepositoryPort, event_publisher: EventPublisher, per_call_timeout_sec: float = 12.0)`——四端口组合注入，对齐 `ToolExecutionEngine.__init__(llm_client, sandbox, ...)` 签名风格
- **R3 新建**（4.5 从零创建）：
  - 领域层：`debate.py` 值对象集 / `debate_session.py` 聚合根 / `debate_evaluator.py` 领域服务 / `debate_session_repository.py` 端口 / `debate_exceptions.py` 异常 / `debate_events.py` 事件
  - 应用层：`red_blue_debate_service.py` + `debate_prompts.py` + `debate_schemas.py` + `src/application/ports/red_blue_debate_service.py`
  - 基础设施层：`inmemory/debate_session_repository.py`
  - 测试：epics 硬路径 2 个 + 单测/契约/验收全套（见文件清单）

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

> 本 Story 实施过程中**严格遵守**以下硬约束，违反任何一项需返回 `draft` 状态重新设计。

### 领域零依赖（FR-AR-01）

- `src/domain/` 禁止 import 任何第三方包——**`pydantic` / `litellm` 均禁止**（LLM 结构化输出的 Pydantic Schema 只能放应用层 `debate_schemas.py`，领域 VO 用标准库 dataclass；领域层引用 schema 类型只能写 `type[Any]`，`LLMClientPort` 先例）
- 禁止 import `src.application` / `src.interfaces` / `src.infrastructure`
- `.importlinter` 强制校验：`poetry run lint-imports`

### 异常体系强制（sisys-uni-exception-design.md）

- **禁止** `raise ValueError(...)` / 手动 `raise HTTPException(...)` / 继承内置 `Exception`（除 `DomainError` 基类）
- **必须** 走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前**三条 grep 自查**零输出（**Story 4.5 范围声明**，对齐 4-4 口径）：新增代码范围内零输出；本 Story 精确 grep 路径：`src/domain/exceptions/debate_exceptions.py src/domain/value_objects/debate.py src/domain/entities/debate_session.py src/domain/services/debate_evaluator.py src/domain/ports/debate_session_repository.py src/domain/events/debate_events.py src/application/ports/red_blue_debate_service.py src/application/services/red_blue_debate_service.py src/application/services/debate_prompts.py src/application/services/debate_schemas.py src/infrastructure/storage/inmemory/debate_session_repository.py`

### 新增异常完整性 Checklist（**5 项强制**，含 HTTP 映射注册与设计文档同步）

1. **定义文件**：新建 `src/domain/exceptions/debate_exceptions.py`（3 个异常类，文件头 docstring 列出编码分配与继承链选择理由——`relevance_exceptions.py` 文件头同款格式）
2. **`_code_ranges.py` 子域映射**：`CODE_RANGES` 新增 `"debate": (420, 429)` 条目（含注释列举编码归属）+ `_CLASS_TO_SUBDOMAIN` 增加 3 行类名映射
3. **`__init__.py` 暴露**：`src/domain/exceptions/__init__.py` 导入并加入 `__all__`
4. **子域码段校验**：3 个异常 `code` 均在 debate 子域（420-429）范围内；420-422 占用，423-429 预留 V1（轮次超限/裁决置信度不足/辩论过热等）
5. **`EXCEPTION_HTTP_MAP` 注册**：`src/interfaces/api/exception_handlers.py` 增加 3 条映射，**注释编码与 code 严格一致**（`# 420` 对应 EXCEPTION_420，杜绝 4.1a 历史注释偏差重演）；同步更新 `docs/architecture/sisys-uni-exception-design.md §3.3.2` 编码分配表（**注意：`test_code_ranges.py` 的"文档同步"维度实际仅校验 `_CLASS_TO_SUBDOMAIN` 覆盖全部 `__all__` 导出类，不读取该 md 文档——文档同步无 CI 强制，人工更新 + 审查时 grep 核验**）

### 抑制告警禁止

- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释
- **禁止** mypy 配置 `ignore_missing_imports=true` 豁免——本 Story **零新第三方依赖**（复用 litellm 既有链路），无 PEP 561 stubs 需求

### Commit & Push 规范

- **禁止** commit 信息含 AI 辅助署名（`Co-Authored-By: Claude` / `anthropic.com` 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 已合入的架构依赖规则
- **禁止** 修改已合入的 alembic migration（本 Story 不新增 migration，无涉）

### API 路由约束（CLAUDE.md §5 第 10 项）

- **本 Story 不新增任何 HTTP API 路由**：对齐 4.1a~4.4 全纯服务层模式（`docs/api/openapi.yaml` 无 tool/sandbox/skill 端点先例，`create_app()` 仅挂 6 个既有 router）；辩论经服务端口调用，HTTP 暴露随 Epic 7 接口层 Story 落地

### LLM 调用安全约束（本 Story 特有）

- **禁止** 绕过 `LLMClientPort` 直接 import litellm（应用层只依赖端口抽象）
- **禁止** 辩论 prompt 拼接泄露 system prompt 模板全文以外的内部实现细节（消息安全性：错误消息与 prompt 面向调用方可理解）
- **温度阶梯三值硬编码为模块常量** `TEMPERATURE_PROFILE = {"red": 0.8, "blue": 0.5, "synthesis": 0.2}`（`red_blue_debate_service.py` 模块级），值与 FR-SP-10 / epics_v1.0.md:165 严格一致，架构验证测试断言对齐——禁止调用方随意传参覆盖（V1 演进时随轮次推进由编排内部计算，不开放外部配置）
- **per-call timeout 必设**：每次 `structured_generate` 显式传 `LLMConfig(temperature=t, timeout=self._per_call_timeout_sec)`（默认 12.0s）；**禁止**依赖 `LLMConfig.from_env()` 默认 timeout=600.0s（否则单次挂起即冲垮延迟目标）。**延迟预算三段式（诚实声明）**：① 无重试路径上界 = max(红,蓝) 12s + 合成 12s + 编排 <1s ≈ 25s < 30s ✓；② `LitelLLMClient` 内置 tenacity 重试（默认 3 次尝试 + 指数退避 1~4s，构造级参数不可按调用调节且 llm_client 为共享端口零修改），含重试最坏 ≈ 3×12s + 退避 ≈ 39s/调用——超 30s 时表现为 BDD 30s 硬超时（conftest `_BDD_HARD_TIMEOUT`）先行截断而非业务异常，属**已声明的接受风险**（熔断器 failure_threshold=5 / recovery 30s 兜底防雪崩）；③ P95<30s 为分布统计目标，本 Story 以「真实 LLM 单点计时 + 无重试上界论证」交付证据，批量 P95 基准随 Story 5.7 落地
- **红蓝视角互相不可见**：生成阶段双方 prompt 仅含议题与背景，**不含对方输出**（独立立场方法论，防锚定偏差）；对抗发生在合成阶段——禁止把蓝视角生成改为"看到红方再反驳"（那是 V1 多轮对抗的形态）

### 代码质量门禁（CLAUDE.md §4 第 3 项扩展）

- **行宽 128 字符**（`ruff` 配置 `line-length = 128`）
- **ruff 规则集 E/F/I/N/W**（`ruff` 配置 `select = ["E", "F", "I", "N", "W"]`）
- **Google 风格全中文注释**（详见项目 memory `~/.claude/projects/-home-agimtech-sisys/memory/sisys_code_comment_style.md`）：文件头 docstring（设计依据 + 编码分配/不变量清单）+ 类 docstring + 函数/方法 docstring（Args/Returns/Raises/Example）

---

## 🎯 领域异常契约（CLAUDE.md §5 强制）

> 本 Story 涉及的所有异常必须在 Task 0 完成 **5 项 Checklist**（详见硬约束章节）。

### 已存在异常复用（不新增编码）

| 异常类 | code | parent | 触发场景 | 复用方式 |
|--------|------|--------|----------|----------|
| `EntityValidationError` | EXCEPTION_242 | entity 子域 | 领域 VO/实体不变量校验（title 非空 / confidence ∈ [0,1] / overlap_rate ∈ [0,1] / 状态机字段类型） | 复用 |
| `EntityStateTransitionError` | EXCEPTION_243 | entity 子域 | `DebateSession` 状态机非法迁移（如 COMPLETED → GENERATING） | 复用（`ToolExecution` 同款，迁移成功 `state_version += 1`） |
| `LLMAPIError` / `LLMResponseError` / `LLMConfigError` | EXCEPTION_330/331/332 | llm 子域 | LLM 底层失败（作为 `cause` 链入 debate 异常 context，**不直接向调用方透传**——`RelevanceEvaluationService` 包装先例） | 复用为 cause |

### 新增异常（本 Story Task 0 登记，3 个）

**关键决策：新开 `debate` 子域 (420, 429)**——420 起完全未使用（2026-10-01 四视角调研 grep 确认零占用），遵循 `data_source` 410-419 独立物理段先例（`_code_ranges.py` 注释"external 已满"后新开段；debate 同理：business 2XX 与 external 3XX 均无整段空位）。

**继承链选择（对齐 `relevance_exceptions.py` 文件头"设计理由"格式，逐类说明）：**

| 异常类 | code | parent | 触发场景 | HTTP 映射 | 上下文字段 |
|--------|------|--------|----------|-----------|-----------|
| `DebateGenerationError` | EXCEPTION_420 | `ExternalException` | 红/蓝视角 LLM 生成调用失败（LLMAPIError/超时/结构化解析失败的不可恢复包装） | 500（精确注册，避免 isinstance 回退 ExternalException 基类 502） | `debate_id` / `perspective` / `topic_title`（截断 100） / `cause` |
| `DebateSynthesisError` | EXCEPTION_421 | `ExternalException` | 风险视图合成 LLM 调用失败（同上，独立成类区分"视角生成"与"合成"监控面） | 500（同上） | `debate_id` / `topic_title` / `cause` |
| `DebateLowDivergenceError` | EXCEPTION_422 | `BusinessException` | 红蓝视角重叠率 ≥ 0.95（两视角实质相同，辩论失去意义，属业务规则违反） | 422（与 `RelevanceEvaluationBlockedError`(361)→422 先例一致，精确注册避免回退 400） | `debate_id` / `overlap_rate` / `red_summary`（截断）/ `blue_summary`（截断） |

**继承层次设计说明：**

- `DebateGenerationError` 继承 `ExternalException`（非 BusinessException）：视角生成的根因是外部 LLM 服务调用失败，与 `RelevanceEvaluationError`(360) 继承链先例完全一致；HTTP 500 而非 502——精确注册避免 isinstance 回退到 `ExternalException` 基类 502（`relevance_exceptions.py` 文件头注释原话："精确注册避免 isinstance 回退到 ExternalException 基类 502"）
- `DebateGenerationError` 与 `DebateSynthesisError` 分立两类（不合并为一个"DebateLLMError"）：监控面需精确区分"视角生成失败"（可定位到红/蓝哪一方）与"合成失败"——对齐 4-4 反模式审查经验"无法精确区分则监控无法精确告警"
- `DebateLowDivergenceError` 继承 `BusinessException`：分化不足是辩论流程的业务结果违反（LLM 调用本身成功），非外部故障；阈值 0.95 语义 = 两视角论点几乎完全相同
- **不设 `DebateError` 子域基类**：420/421 继承 ExternalException、422 继承 BusinessException，无法共享同一基类（项目规范必须继承三大抽象分层之一）；`relevance` 子域（360/361）平铺无基类先例支持此设计
- **结构化输出校验失败的异常包装链（2026-10-01 实测定谳）**：小模型违反 minItems/maxItems 等 json_schema 约束时，`response_schema(**parsed)` 抛 pydantic `ValidationError`（继承 `ValueError`）→ 被 `LitelLLMClient` 外层 `except (…, ValueError, …)` 捕获（litellm_llm_client.py:722）→ 重试耗尽统一抛 `LLMResponseError(cause=…)`（:730-735）→ 服务包装为 420/421——**裸 ValidationError 不会逃逸**，服务 except 面无需（也不应）额外覆盖 ValidationError（会造死代码分支）

**禁止设计反模式（异常 5 轮审查经验 + 4-4 先例）：**

- ❌ 复用 `LLMAPIError` 直接向调用方透传（丢失 debate_id/perspective 领域上下文，违反"异常携带领域上下文"原则）→ 包装为 `DebateGenerationError(cause=...)`
- ❌ 新建 `DebateSessionStateTransitionError`（复用 EXCEPTION_243，`ToolExecution` 先例）
- ❌ 把"分化度警告"（0.80 ≤ 重叠率 < 0.95）做成异常——警告是 RiskView.warnings 字段的正常输出，仅 ≥ 0.95 硬阈值抛 `DebateLowDivergenceError`（避免质量问题硬失败损害可用性；重试机制属 Story 4.7 Validation Feedback 体系）
- ❌ 分化度不足自动重试红视角（MVP 无重试预算，P95<30s 延迟目标约束——见 LLM 调用安全约束节延迟预算三段式；重试体系 4.7 统一治理）

### 登记确认动作（Task 0 必做）

- [ ] 新建 `src/domain/exceptions/debate_exceptions.py`（3 个异常类 + 文件头编码分配/继承理由 docstring）
- [ ] `src/domain/exceptions/_code_ranges.py`：`CODE_RANGES` 增加 `"debate": (420, 429)`（含注释列举 420-422 归属 + 423-429 预留说明）+ `_CLASS_TO_SUBDOMAIN` 增加 3 行
- [ ] `src/domain/exceptions/__init__.py` 导入并加入 `__all__`
- [ ] `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 注册 3 条（`# 420`/`# 421`/`# 422` 注释与 code 严格一致）
- [ ] `docs/architecture/sisys-uni-exception-design.md §3.3.2` 编码分配表增加 debate 子域 3 行
- [ ] 运行 `poetry run pytest tests/unit/domain/exceptions/test_code_ranges.py -v`（校验子域范围/继承链一致性/注册覆盖三维度；§3.3.2 文档表更新为人工维护，无 CI 强制）
- [ ] 运行 `poetry run pytest tests/unit/domain/exceptions/test_error_code_uniqueness.py -v`（无碰撞）

---

## 🎯 测试隔离约束（CLAUDE.md §4 + §5 强制）

> 辩论测试无外部共享资源（InMemory 仓储 + Fake LLM），隔离要求低于 4-4 真实 Docker，但 LLM 真实场景与 BDD 异步纪律仍须严格遵守。

### Fake LLM 工厂（单元/集成/验收共用模式）

- 单元测试：`AsyncMock(spec=LLMClientPort)` + `structured_generate.side_effect` 按 **response_schema 身份分派**（`response_schema is PerspectiveAnalysisSchema` 时按 `config.temperature` 区分红（0.8）/蓝（0.5），`is RiskViewSchema` 时返回合成结果——`test_summary_generation_service.py:40-50` 按 schema 身份分派先例）。**禁止**按 system_prompt 子串分派：裁判 system_prompt 必然同时描述红蓝双方（同时含"激进派""保守派"标记），子串判定顺序会使合成调用误路由到视角 Schema、Happy path 对正确实现误红（`test_skill_framework.py`（integration 目录）按 user prompt 内容分派的先例不适用于本三角色场景）。system_prompt 角色标记短语保留为**断言物**（断言每次调用的 system_prompt 含对应角色标记），不作为分派依据
- **温度断言（强制按分派身份记录）**：分派闭包内联按 `(response_schema, temperature)` 联合记录——断言 **PerspectiveAnalysisSchema 调用中 temperature==0.8（红）与 ==0.5（蓝）各至少一次**（红蓝温度互换 0.8↔0.5 时 sorted/集合断言不红、按身份断言必红——判别力更强）、RiskViewSchema 调用 temperature==0.2；`sorted == [0.2, 0.5, 0.8]` 仅作补充全量断言——**CI 可验证的温度阶梯证据**
- 返回值构造：`MagicMock(spec=response_schema)` 按字段填充（`test_summary_generation_service.py:29-59` 工厂同款）

### 真实 LLM 场景（集成 + 验收的 llm 分组）

- 复用 `tests/acceptance/conftest.py` 的 `probe_llm_endpoint_reachable(endpoint)`（TCP 3s 探测，防内网端点卡死）+ `run_with_bdd_timeout(event_loop, coro, cfg_timeout)`（BDD 调用层硬超时保护）
- LLM 端点不可达 / 无 api_key → `pytest.skip(f"LLM not available: ...")` **动态跳过**（**禁止**写死 `@pytest.mark.skip`）
- 场景标记 `@pytest.mark.llm`（pyproject markers 已注册），CI 可 `-m "not llm"` 排除
- 真实 LLM 计时场景断言单次 `run_debate` 端到端 < 30s（P95 代理单点验证；批量 P95 基准见 AC-9）

### asyncio 纪律（CLAUDE.md §6 Gotcha + §5）

- `asyncio.Lock` 必须为**类变量**：`InMemoryDebateSessionRepository._lock: asyncio.Lock = asyncio.Lock()`（4.1a/4.4 一致模式）
- **BDD 步骤函数禁止 `@pytest.mark.asyncio`**（context 数据丢失红线）：步骤函数用**同步 `def`** + `event_loop.run_until_complete(coro)` 驱动（pytest-bdd 8.x 限制，acceptance 全部 59 个 .py 文件遵循）；模块级 event_loop fixture 先例：`test_acceptance_domain_dictionary.py` / `test_acceptance_layered_retrieval.py`；`test_acceptance_strategic_tool_impl.py:424-430` 为 `_run_async` helper 变体（每次新建 event loop 后 run_until_complete，同样合法）
- 单元测试可直接 `async def test_*`（`asyncio_mode = "auto"`）
- 红蓝并发场景（gather）在 async 函数内 `asyncio.gather()`（CLAUDE.md §5 真正并发测试约定）

### 其余隔离规则

- 测试数据议题/租户用 `TestTenant` UUID 前缀或 `uuid.uuid4()` 现场生成（资源唯一性）
- 本 Story **无 delete/truncate 需求**（InMemory 仓储场景级新建实例，天然隔离；禁止为 InMemory 写全局清理 autouse fixture）
- 并行验证：`pytest tests/ -n 8` 通过（辩论测试无共享面，无需 xdist_group 串行化）

---

## 🌐 端口契约（CLAUDE.md §4 端口契约 + 内/外部接口契约）

### 外部端口契约：LLMClientPort（R1 复用，零修改）

`src/domain/ports/llm_client.py` 既有 Protocol，本 Story 调用面（**禁止扩展**）：

```python
async def structured_generate(
    self,
    prompt: str,
    response_schema: type[Any],      # 应用层 Pydantic Schema 类（debate_schemas.py）
    config: LLMConfig | None = None, # LLMConfig(temperature=0.8/0.5/0.2, timeout=per_call)
    system_prompt: str | None = None,# 视角角色 prompt（红/蓝/裁判）
) -> Any: ...                        # 返回 Schema 实例，应用层转领域 VO
```

多轮对抗历史（V1）拼入 prompt 字符串——`ToolExecutionEngine` 同款，不新增 `messages` 入参（触碰 `test_port_contract_llm_client.py` 三方法契约 + `test_arch_llm_client.py`，超范围）。

### 内部端口契约：RedBlueDebateServicePort（新增，应用层）

`src/application/ports/red_blue_debate_service.py`（对齐 `ToolChainServicePort`/`SummaryGenerationServicePort` 先例）：

```python
@runtime_checkable
class RedBlueDebateServicePort(Protocol):
    """红蓝辩论服务端口协议（单 Agent 多视角 MVP）"""

    async def run_debate(self, topic: DebateTopic, context: ExecutionContext) -> DebateResult: ...
    async def get_debate_result(self, debate_id: uuid.UUID) -> DebateResult | None: ...
```

### 内部端口契约：DebateSessionRepositoryPort（新增，领域层）

`src/domain/ports/debate_session_repository.py`（单字段标识查找用直接参数，CLAUDE.md §4 决策规则；不继承 L2RdbPort——主键 UUID 但无 PG 实现，4.4 `SandboxSessionRepositoryPort` 同款独立 Protocol 先例）：

```python
@runtime_checkable
class DebateSessionRepositoryPort(Protocol):
    """辩论会话仓储端口协议"""

    async def save(self, session: DebateSession) -> DebateSession: ...  # 返回实体对齐既有 5 个 InMemory 仓储先例
    async def get_by_id(self, debate_id: uuid.UUID) -> DebateSession | None: ...
```

### 核心值对象与实体签名（Task 0 规范，领域层标准库实现）

```python
# src/domain/value_objects/debate.py
class DebatePerspective(str, Enum):
    """辩论视角枚举：红=激进派（发散），蓝=保守派（收敛）"""
    RED_AGGRESSIVE = "red_aggressive"
    BLUE_CONSERVATIVE = "blue_conservative"

@dataclass(frozen=True)
class DebateTopic:
    """争议议题值对象（辩论输入）"""
    tenant_id: uuid.UUID
    title: str                        # 非空、≤200 字符
    background: str = ""              # 议题背景与证据上下文（供双视角引用），≤8000 字符
    debate_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # __post_init__: title 非空/长度、background 长度 → EntityValidationError(242)

@dataclass(frozen=True)
class PerspectiveAnalysis:
    """单视角分析值对象"""
    perspective: DebatePerspective
    stance: str                       # 一句话立场，非空
    arguments: tuple[str, ...]        # 核心论点 1~8 条，每条非空
    risks: tuple[str, ...]            # 该视角识别的主要风险
    recommendations: tuple[str, ...]  # 该视角建议
    confidence: float                 # ∈ [0.0, 1.0]
    # __post_init__: 枚举合法/stance 非空/arguments 1~8 条非空/confidence 范围 → 242

@dataclass(frozen=True)
class ConsensusArea:
    """共识区域条目：双视角共同认可的判断"""
    area: str                         # 共识主题，非空
    description: str                  # 共识内容
    confidence: float                 # ∈ [0.0, 1.0]

@dataclass(frozen=True)
class DisagreementArea:
    """分歧区域条目：双视角立场对立点"""
    area: str                         # 分歧主题，非空
    red_position: str                 # 红方立场
    blue_position: str                # 蓝方立场
    risk_note: str                    # 分歧带来的决策风险提示

@dataclass(frozen=True)
class RiskView:
    """风险全景视图（辩论核心输出）"""
    consensus_areas: tuple[ConsensusArea, ...]     # ≥ 1 条
    disagreement_areas: tuple[DisagreementArea, ...] # ≥ 1 条
    overall_risk_level: str           # "LOW" | "MEDIUM" | "HIGH"（Literal 校验）
    overlap_rate: float            # 红蓝重叠率 ∈ [0.0, 1.0]
    warnings: tuple[str, ...] = ()    # 质量警告（如重叠率 ≥ 0.80 分化偏弱）
    # __post_init__: 两组区域非空/risk_level 枚举/divergence 范围 → 242

@dataclass(frozen=True)
class DebateQuality:
    """辩论质量评估结果（V1 多轮字段预留）"""
    overlap_rate: float            # 红蓝重叠率（MVP 必填）
    gain_rate: float | None = None    # 增益率（多轮概念，MVP 单轮恒 None）
    repetition_rate: float | None = None  # 重复率（多轮概念，MVP 单轮恒 None）

@dataclass(frozen=True)
class DebateResult:
    """辩论结果值对象（服务返回聚合）"""
    debate_id: uuid.UUID
    topic_title: str
    red_analysis: PerspectiveAnalysis
    blue_analysis: PerspectiveAnalysis
    risk_view: RiskView
    quality: DebateQuality
    duration_ms: int                  # ≥ 0
```

```python
# src/domain/entities/debate_session.py（ToolExecution 状态机同构）
class DebateSessionState(str, Enum):
    IDLE = "idle"
    GENERATING = "generating"        # 红蓝视角生成中
    SYNTHESIZING = "synthesizing"    # 风险视图合成中
    COMPLETED = "completed"
    FAILED = "failed"

VALID_TRANSITIONS: dict[DebateSessionState, set[DebateSessionState]] = {
    DebateSessionState.IDLE: {DebateSessionState.GENERATING},
    DebateSessionState.GENERATING: {DebateSessionState.SYNTHESIZING, DebateSessionState.FAILED},
    DebateSessionState.SYNTHESIZING: {DebateSessionState.COMPLETED, DebateSessionState.FAILED},
    DebateSessionState.COMPLETED: set(),
    DebateSessionState.FAILED: set(),
}
TERMINAL_STATES: frozenset[DebateSessionState] = frozenset(
    {DebateSessionState.COMPLETED, DebateSessionState.FAILED}
)

@dataclass
class DebateSession:
    """辩论会话聚合根（状态机 + 迁移计数，V1 乐观锁预留）"""
    debate_id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    state: DebateSessionState = DebateSessionState.IDLE
    red_analysis: PerspectiveAnalysis | None = None
    blue_analysis: PerspectiveAnalysis | None = None
    risk_view: RiskView | None = None
    failure_reason: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    state_version: int = 0
    # validate() / can_transition_to() / transition_to()（非法迁移抛 243，成功 state_version += 1）
    # 终态不变量：COMPLETED 必有 risk_view；FAILED 必有 failure_reason
```

### 领域事件：DebateCompleted（继承 DomainEvent 基类）

`src/domain/events/debate_events.py`（`sandbox_events.py` 惯例：`event_type` init=False 自动注册 + `__post_init__` 用 `object.__setattr__` 填 aggregate）：

```python
@dataclass(frozen=True)
class DebateCompleted(DomainEvent):
    debate_id: uuid.UUID
    tenant_id: uuid.UUID
    topic_title: str                       # 截断 100 字符
    red_stance: str                        # 红方立场摘要
    blue_stance: str                       # 蓝方立场摘要
    consensus_count: int
    disagreement_count: int
    overlap_rate: float
    overall_risk_level: str
    duration_ms: int
    temperature_profile: dict[str, float]  # {"red": 0.8, "blue": 0.5, "synthesis": 0.2}
    event_type: str = field(default="DebateCompleted", init=False)
    # __post_init__: aggregate_type="DebateSession"，aggregate_id=debate_id，metadata 透传 tenant_id
```

**双通道登记（新增事件必须同步两处 + CLAUDE.md §4 约定）：**

- `configs/event_channels.yaml`：`redis_channel: "sisys:rt:debate_completed"` + `rabbitmq_routing_key: "sisys.events.reliable.debate_completed"` + `delivery_mode: "reliable"` + description（对齐 ToolExecuted 双通道模式）
- `src/infrastructure/messaging/channel_router.py` 的 `DEFAULT_MAPPINGS` 增加 `ChannelMapping(...)` 同参数条目（YAML 与 DEFAULT_MAPPINGS 参数逐字段一致）

### 端口注册（composition_root.py，3 个新端口）

| 端口名 | version | interface | impl | lifetime | owner | tags |
|--------|---------|-----------|------|----------|-------|------|
| `debate_session_repository` | v1.0.0 | `DebateSessionRepositoryPort` | `InMemoryDebateSessionRepository()`（惰性 `__import__` lambda） | SCOPED | tool-team | ("debate", "repository", "inmemory") |
| `debate_evaluator` | v1.0.0 | `DebateEvaluator`（领域服务类即接口，`context_compressor` 先例） | `"src.domain.services.debate_evaluator.DebateEvaluator"`（字符串延迟加载） | SINGLETON | tool-team | ("debate", "domain", "service") |
| `red_blue_debate_service` | v1.0.0 | `RedBlueDebateServicePort` | lambda 工厂注入 `llm_client` + `debate_evaluator` + `debate_session_repository` + `event_publisher`（`tool_chain_service` 注册范式） | SCOPED | tool-team | ("debate", "service") |

### 契约测试文件清单

- `tests/contracts/test_port_contract_red_blue_debate_service.py`（11 维度：PORT_NAME/INTERFACE/REQUIRED_METHODS + name/version/lifetime/owner/module/tags/impl callable/runtime_checkable）
- `tests/contracts/test_port_contract_debate_session_repository.py`（11 维度同上）
- `tests/contracts/test_event_contract_debate_events.py`（`test_event_contract_tool_executed.py` 模式：event_type/aggregate 归属/继承 DomainEvent/子类字段/to_dict-from_dict roundtrip）
- `tests/contracts/test_event_channel_mapping_debate.py`（YAML 与 `DEFAULT_MAPPINGS` 两处参数逐字段一致断言——新增事件双处同步的门禁）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 领域值对象与枚举 + 不变量校验

**Given** 辩论输入/输出需要不可变的多视角结构描述，且需阻止空议题/越界置信度等非法构造
**When** 在领域层定义 `debate.py` 值对象集与 `DebatePerspective` 枚举
**Then**

- **路径**：`src/domain/value_objects/debate.py`（**领域层**，标准库实现）
- **构成**：`DebatePerspective`（RED_AGGRESSIVE/BLUE_CONSERVATIVE）+ `DebateTopic` + `PerspectiveAnalysis` + `ConsensusArea` + `DisagreementArea` + `RiskView` + `DebateQuality` + `DebateResult`（完整签名见上文端口契约节）
- **`__post_init__` 不变量**（违反抛 `EntityValidationError` EXCEPTION_242，context 携带 entity/field/value/constraint）：
  1. `DebateTopic.title` 非空且 ≤ 200 字符；`background` ≤ 8000 字符
  2. `PerspectiveAnalysis.stance` 非空；`arguments` 1~8 条且每条非空；`confidence ∈ [0.0, 1.0]`；`perspective` 枚举合法
  3. `ConsensusArea.area` / `DisagreementArea.area` 非空；两者 `confidence ∈ [0.0, 1.0]`（ConsensusArea）
  4. `RiskView.consensus_areas ≥ 1` 且 `disagreement_areas ≥ 1`；`overall_risk_level ∈ {"LOW","MEDIUM","HIGH"}`；`overlap_rate ∈ [0.0, 1.0]`
  5. `DebateQuality.overlap_rate ∈ [0.0, 1.0]`；`DebateResult.duration_ms ≥ 0`
- **不可变设计**：全部 `@dataclass(frozen=True)`，tuple 替代 list 字段
- **零依赖**：仅标准库（dataclasses/enum/uuid/datetime）+ 领域异常
- `src/domain/value_objects/__init__.py` re-export 全部新类型

**验证标准/Validation Criteria:**

- [ ] 全部 8 个类型（7 个 frozen dataclass VO + 1 个枚举 `DebatePerspective`，枚举天然不可变）位于 `src/domain/value_objects/debate.py`
- [ ] 5 组不变量失败测试逐项触发 EXCEPTION_242（每项独立用例）
- [ ] 默认值/合法构造通过（`_make_debate_topic(**overrides)` 等 `_make_*` 工厂函数）
- [ ] `poetry run lint-imports` 通过（域层零依赖）
- [ ] `tests/unit/domain/value_objects/test_debate.py` 通过

### AC-2: DebateSession 聚合根 + 状态机

**Given** 辩论流程需要状态追踪与可观测性，且状态迁移必须受控（V1 多轮辩论在此实体上扩展）
**When** 定义 `DebateSession` 聚合根（`ToolExecution` 状态机同构）
**Then**

- **路径**：`src/domain/entities/debate_session.py`
- **状态机**：`IDLE → GENERATING → SYNTHESIZING → COMPLETED`，`GENERATING/SYNTHESIZING → FAILED` 可达，`COMPLETED/FAILED` 为终态（`VALID_TRANSITIONS` 迁移矩阵 + `TERMINAL_STATES` frozenset）
- **非法迁移抛 `EntityStateTransitionError`**（EXCEPTION_243，复用不新增）；迁移成功 `state_version += 1`（迁移计数，V1 乐观锁 CAS 预留）
- **终态不变量**：`COMPLETED` 必有 `risk_view` 与 `completed_at`；`FAILED` 必有 `failure_reason`；非终态不得有 `completed_at`（违反抛 242）
- `validate()` 校验 UUID/非空/枚举/timezone-aware/`state_version ≥ 0`
- **实体不发领域事件**（项目惯例：事件由应用服务在流程完成后发布——grep 确认 `src/domain/entities/` 无 DomainEvent 引用）

**验证标准/Validation Criteria:**

- [ ] 合法全路径迁移（IDLE→…→COMPLETED）`state_version` 递增断言
- [ ] 非法迁移（COMPLETED→GENERATING、IDLE→SYNTHESIZING 跳态）抛 243 + code 断言
- [ ] 终态不变量违反抛 242
- [ ] `tests/unit/domain/entities/test_debate_session.py` 通过

### AC-3: 3 个新辩论领域异常（EXCEPTION_420~422）

**Given** 视角生成/合成失败需包装 LLM 底层异常携带领域上下文，视角分化不足属业务规则违反
**When** 新建 `debate_exceptions.py` + 登记 debate 子域 (420, 429)
**Then**

- **路径**：`src/domain/exceptions/debate_exceptions.py`（新建子域模块，文件头 docstring 含编码分配 + 继承链选择理由，`relevance_exceptions.py` 同款格式）
- **3 个异常类**（继承链/HTTP 映射/上下文字段见"领域异常契约"节表格）：
  | 类名 | code | parent | HTTP |
  |------|------|--------|------|
  | `DebateGenerationError` | EXCEPTION_420 | `ExternalException` | 500 |
  | `DebateSynthesisError` | EXCEPTION_421 | `ExternalException` | 500 |
  | `DebateLowDivergenceError` | EXCEPTION_422 | `BusinessException` | 422 |
- **构造器契约**：`__init__` 接收领域上下文字段 → 组装 `context` dict → `super().__init__(message=message, cause=cause, context=context)`；LLM 底层异常经 `cause` 参数链入（**不吞异常**）
- **5 项 Checklist 全项完成**（定义文件 / `_code_ranges.py` 两表 / `__init__.py` / `EXCEPTION_HTTP_MAP` 3 条精确注册 / `sisys-uni-exception-design.md §3.3.2` 同步）

**验证标准/Validation Criteria:**

- [ ] 3 个异常类 code 无碰撞（`test_error_code_uniqueness.py` 通过）
- [ ] 子域范围校验通过（`test_code_ranges.py` 通过——子域范围/继承链/注册覆盖维度；debate 3 异常直接继承抽象基类 ExternalException/BusinessException，被 Rule 2 的 abstract_names 跳过，无需扩 `allowed_child_parent_subdomains` 白名单）
- [ ] `to_dict()` 序列化含全部 context 字段 + cause 链解析
- [ ] HTTP 映射：3 个异常经 `exception_handler()` 映射 500/500/422（反向验证 `pytest.raises → exception_handler() → assert status`）
- [ ] 三条 grep 自查零输出（本 Story 范围路径）
- [ ] `tests/unit/domain/exceptions/test_debate_exceptions.py` 通过

### AC-4: DebateEvaluator 领域服务（GAP-CRITICAL-09 清偿）

**Given** architecture.md §7.3 定义辩论终止条件（增益率 <10% / 重复率 >50%）且 GAP-CRITICAL-09 挂账"辩论质量评估器未实现"
**When** 实现纯算法领域服务 `DebateEvaluator`
**Then**

- **路径**：`src/domain/services/debate_evaluator.py`（领域层，零外部依赖，纯函数式）
- **三个公开算法**（字符 bigram 集合 Jaccard 相似度族，中文无需分词，标准库实现）：
  - `compute_repetition_rate(current_text: str, previous_text: str) -> float`——相邻轮次重复内容占比（V1 终止条件：>0.50 强制终止）；完全相同文本返回 1.0，无交集返回 0.0；**空文本边界**：两者皆空返回 0.0，一空一非空返回 0.0（空参数列表重复率 bug 是架构 8.0.0 版修正项，此处必须测试覆盖）
  - `compute_gain_rate(current_text: str, previous_text: str) -> float`——新信息量/上轮信息量 = |current_bigrams − previous_bigrams| / max(|previous_bigrams|, 1)（V1 终止条件：<0.10 强制终止）；previous 为空时返回 1.0（全新信息）
  - `evaluate_overlap(red_analysis: PerspectiveAnalysis, blue_analysis: PerspectiveAnalysis) -> float`——红蓝重叠率 = bigram Jaccard(红论点拼接, 蓝论点拼接)，返回浮点重叠率（`DebateQuality(overlap_rate=...)` 由服务层用返回值组装——评估器不构造质量对象，纯函数单一职责；MVP 编排门控：≥0.95 抛 `DebateLowDivergenceError`；≥0.80 输出 RiskView.warnings 警告）
- **`evaluate_round(rounds: ...)` 不实现**——V1 多轮接口随 Story 10.6 演进（MVP 无轮次序列，禁止过度设计）
- **确定性**：纯函数无状态，同输入同输出（SINGLETON 注册前提）

**验证标准/Validation Criteria:**

- [ ] 三算法已知输入精确断言（如 `compute_repetition_rate("ABC", "ABC") == 1.0`、`compute_gain_rate("ABCD", "ABC") == 0.5`——bigram("ABCD")={AB,BC,CD} 与 bigram("ABC")={AB,BC} 差集 {CD}，1 / max(2, 1) = 0.5 精确断言）
- [ ] 空文本/单字符/Unicode 中文三类边界用例
- [ ] `evaluate_overlap` 红蓝相同 → 1.0；完全无关 → 0.0；中文论点对可用
- [ ] 零依赖验证（`lint-imports` + 架构测试 AST 扫描）
- [ ] `tests/unit/domain/services/test_debate_evaluator.py` 通过

### AC-5: DebateSessionRepositoryPort + InMemory 实现

**Given** 辩论会话需要仓储抽象支撑编排可观测与测试（PG 持久化延后 Epic 10）
**When** 定义仓储端口与 InMemory 实现
**Then**

- **端口**：`src/domain/ports/debate_session_repository.py`（`save` / `get_by_id` 两方法，`@runtime_checkable`，docstring 声明无专属异常）
- **实现**：`src/infrastructure/storage/inmemory/debate_session_repository.py`——`InMemoryDebateSessionRepository`，`asyncio.Lock` **类变量**（4.1a/4.4 一致模式），内部 `dict[uuid.UUID, DebateSession]`，save 先 `validate()` 再幂等覆盖（按 debate_id，无版本冲突检测——V1 CAS 预留），返回保存后的实体（对齐既有 5 个 InMemory 仓储 `save -> Entity` 先例）
- **注册**：`composition_root.py` 注册 `debate_session_repository`（SCOPED，见端口契约节 PortSpec）

**验证标准/Validation Criteria:**

- [ ] save → get_by_id roundtrip；未知名返回 None
- [ ] 并发 save 安全（`asyncio.gather` 50 并发无丢失，`test_sandbox_session_repository` 同款场景）
- [ ] 契约测试 `tests/contracts/test_port_contract_debate_session_repository.py` 11 维度通过
- [ ] `tests/unit/infrastructure/storage/test_debate_session_repository.py` 通过

### AC-6: DebateCompleted 领域事件 + 双通道注册

**Given** 辩论完成需可靠通知下游（审计/工作流/后续 Agent 协作消费），CLAUDE.md §4 约定新事件双通道同步登记
**When** 定义 `DebateCompleted` 事件并注册双通道
**Then**

- **事件类**：`src/domain/events/debate_events.py`（完整签名见端口契约节；`event_type` init=False 自动注册、`__post_init__` 填 aggregate_id/aggregate_type="DebateSession"、metadata 透传 tenant_id）
- **四处同步**：`events/__init__.py` 导出 + `configs/event_channels.yaml`（realtime+reliable 双通道键值见端口契约节）+ `ChannelRouter.DEFAULT_MAPPINGS` 同参数条目 + 事件契约测试
- **payload 可序列化**：`to_dict()` 全字段 JSON 可序列化（含 `temperature_profile` dict），`from_dict()` roundtrip 重建（`DomainEvent._registry` 多态注册生效）

**验证标准/Validation Criteria:**

- [ ] `to_dict()` / `from_dict()` roundtrip 字段一致
- [ ] `test_event_contract_debate_events.py` 通过（event_type/aggregate 归属/继承链/子类字段）
- [ ] `test_event_channel_mapping_debate.py` 通过：YAML 与 `DEFAULT_MAPPINGS` 两处 `redis_channel` / `rabbitmq_routing_key` / `delivery_mode` 逐字段一致 + `delivery_mode == RELIABLE`
- [ ] 服务发布事件后 `ChannelRouter.get_delivery_mode("DebateCompleted") == DeliveryMode.RELIABLE`

### AC-7: RedBlueDebateService 应用服务（温度阶梯编排核心）

**Given** 单 Agent 多视角辩论需要应用层编排：双视角并发生成 → 分化度门控 → 风险视图合成 → 事件发布
**When** 实现 `RedBlueDebateService` + prompts + schemas
**Then**

- **服务**：`src/application/services/red_blue_debate_service.py`
  - `__init__(llm_client: LLMClientPort, evaluator: DebateEvaluator, session_repository: DebateSessionRepositoryPort, event_publisher: EventPublisher, per_call_timeout_sec: float = 12.0)`
  - `async run_debate(topic: DebateTopic, context: ExecutionContext) -> DebateResult`——编排流程：
    1. 创建 `DebateSession`（IDLE→GENERATING）并 `repository.save`——**编排全程每次状态迁移后均 save**（终态/中间态可观测与测试断言依赖仓储快照）
    2. **红蓝并发**：`asyncio.gather(红视角任务, 蓝视角任务)`，各自 `structured_generate(prompt=视角 user prompt, response_schema=PerspectiveAnalysisSchema, config=LLMConfig(temperature=0.8/0.5, timeout=self._per_call_timeout_sec), system_prompt=红/蓝角色 prompt)`；任一失败 → session 转 FAILED（failure_reason）+ save → 包装 `DebateGenerationError(debate_id, perspective, cause=...)` 抛出；**gather 异常语义**：gather 默认首异常即传播且不取消兄弟任务——服务异常分支须显式取消未完成一方（`task.cancel()` + suppress `CancelledError`），防孤儿任务与 "exception was never retrieved" 警告
    3. Schema → 领域 VO 转换（`PerspectiveAnalysisSchema.to_domain()`，应用层职责）
    4. **分化度门控**：`evaluator.evaluate_overlap(red, blue)` → 重叠率 ≥ 0.95：session FAILED + save + 抛 `DebateLowDivergenceError`；0.80 ≤ 重叠率 < 0.95：记入 warnings 继续
    5. session GENERATING→SYNTHESIZING + save；合成调用（T=0.2，`RiskViewSchema`）；失败 → FAILED + save + `DebateSynthesisError(cause=...)`
    6. Schema → `RiskView` VO（合成阶段将 overlap_rate/warnings 服务端注入——**不信任 LLM 输出分化度**，`relevance_schemas.py` computed_field 服务端裁决先例）；VO 构造抛 `EntityValidationError`(242) 的理论缝隙（Pydantic 过但领域不变量败，如嵌套 area 字段约束缺位时）→ session FAILED + save + **透传 242**（属数据契约违反而非 LLM 调用失败，不包装为 421）
    7. session SYNTHESIZING→COMPLETED + save；组装 `DebateResult(duration_ms)`
    8. 发布 `DebateCompleted`，**双形态失败处理**（EventPublisher 契约是返回 `PublishResult` 而非抛异常）：① `result.is_success == False`（全失败/部分失败标志）→ logger.warning；② publish 调用本身抛异常（契约外防御）→ try/except 捕获 logger.warning——两形态均**不覆写辩论结果**（`PrefectEngine._publish_workflow_submitted` 对称先例：PublishResult 为 None/全失败时仅 WARNING）；返回 `DebateResult`
  - `async get_debate_result(debate_id) -> DebateResult | None`——从仓储重建，**仅 COMPLETED 会话可重建**（重建公式：`topic_title = session.title`；`quality = DebateQuality(overlap_rate=session.risk_view.overlap_rate, gain_rate=None, repetition_rate=None)`；`duration_ms = round((session.completed_at - session.started_at).total_seconds() * 1000)`——与 `run_debate` 返回值可能有毫秒级时钟差，测试断言重建语义而非与原值全等）；FAILED 及一切非 COMPLETED 会话（含未知名）返回 None——FAILED 虽为终态但无 risk_view，数学上不可重建
  - **模块常量**：`TEMPERATURE_PROFILE: dict[str, float] = {"red": 0.8, "blue": 0.5, "synthesis": 0.2}`（架构测试断言对齐 FR-SP-10）+ `OVERLAP_HARD_THRESHOLD = 0.95` + `OVERLAP_WARNING_THRESHOLD = 0.80`
- **prompts**：`src/application/services/debate_prompts.py`——`PERSPECTIVE_PROMPT_MAP: dict[DebatePerspective, PerspectivePrompt]`，`PerspectivePrompt` 为 TypedDict（`system_prompt: str` + `user_prompt_template: str`，与 `summary_prompts.PerspectivePrompts` 同构、键类型升级为枚举）；红/蓝各含 system_prompt（角色人设+立场纪律+输出要求）+ user_prompt_template（`{title}`/`{background}` 占位）+ `SYNTHESIS_SYSTEM_PROMPT` / `SYNTHESIS_USER_TEMPLATE`（裁判人设：给定红蓝双方论点 JSON，输出共识/分歧/风险等级）；prompt 全中文、含可识别角色标记短语（红"激进派"/蓝"保守派"/裁判"裁判"——供调用断言与立场遵循断言，**不作 Fake 分派依据**）
- **schemas**：`src/application/services/debate_schemas.py`——`PerspectiveAnalysisSchema(BaseModel)`（stance/arguments: list[str] min_length=1 max_length=8/risks/recommendations/confidence: float ge=0 le=1）+ `RiskViewSchema(BaseModel)`（consensus_areas: list[ConsensusAreaSchema] min_length=1 / disagreement_areas: list[DisagreementAreaSchema] min_length=1 / overall_risk_level: Literal["LOW","MEDIUM","HIGH"]）+ 各 `to_domain()` 转换方法（Pydantic 校验 + 领域 VO 双重不变量）

**验证标准/Validation Criteria:**

- [ ] Happy path：Fake LLM 三次分派 → `DebateResult` 三段结构完整（red/blue/risk_view）
- [ ] **温度阶梯断言**：按分派身份强制记录——PerspectiveAnalysisSchema 调用中 temperature==0.8（红）与 ==0.5（蓝）各至少一次（互换即红），RiskViewSchema 调用 temperature==0.2；补充断言三次温度 sorted == [0.2, 0.5, 0.8]
- [ ] 红蓝并发验证：Fake LLM 记录每次调用 start/end 时间戳，断言红蓝生成窗口重叠（`blue.start < red.end` 且 `red.start < blue.end`——串行实现必不满足该断言）；辅以 sleep 注入 Fake 的单边计时断言 `elapsed < 1.5 × sleep`（串行两次 ≈ 2×sleep 必超标，单边阈值避免 CI 调度抖动假红）
- [ ] 视角独立性（断言范围限定）：仅施加于两次 `PerspectiveAnalysisSchema` 调用——红/蓝的 prompt 与 system_prompt 互不含对方 stance/论点标记（独立立场方法论，防锚定偏差）；**合成调用（RiskViewSchema）豁免**——其 user prompt 按设计必然同时含红蓝双方论点 JSON（对抗发生在合成阶段）
- [ ] LLM 失败路径：红视角 side_effect 抛 `LLMAPIError` → 断言 `DebateGenerationError` + `context.perspective == "red_aggressive"` + `cause` 链保留；session 终态 FAILED + failure_reason（**蓝视角对称用例**：`context.perspective == "blue_conservative"`）；失败路径经 `repository.get_by_id` 断言终态落库（依赖"每次状态迁移后 save"纪律）
- [ ] 合成失败路径 → `DebateSynthesisError`；分化度 ≥0.95 → `DebateLowDivergenceError`（Fake 返回红蓝几乎相同的 arguments）
- [ ] 0.80 ≤ 重叠率 < 0.95 → 不抛异常，`risk_view.warnings` 非空
- [ ] 事件发布：`AsyncMock(spec=EventPublisher)` 断言 publish(DebateCompleted) 一次 + 字段值；**双形态失败**：Fake publish 返回 `PublishResult(is_success=False)` 时 `run_debate` 仍返回结果（契约内形态，EventPublisher 契约返回 PublishResult 而非抛异常）；Fake publish 直接 raise 时仍返回结果（契约外防御形态）
- [ ] per-call timeout 传递断言：捕获 `config.timeout == 12.0`（默认构造）
- [ ] `tests/unit/application/services/test_red_blue_debate_service.py` 通过

### AC-8: composition_root 端口注册 + 契约测试

**Given** 新增 3 个端口必须经组合根统一注册（禁止业务代码直接实例化实现）
**When** 注册 `debate_session_repository` / `debate_evaluator` / `red_blue_debate_service`
**Then**

- 注册参数严格对齐"端口契约"节表格（PortSpec 10 字段：name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated，compatibility 默认空元组、deprecated 默认 False）
- `red_blue_debate_service` lambda 工厂内 `resolver.resolve("llm_client")` / `resolve("debate_evaluator")` / `resolve("debate_session_repository")` / `resolve("event_publisher")` 四依赖注入（惰性 `__import__` 引用实现类，`tool_chain_service` 注册范式）
- 注册后 `bootstrap()` 可正常完成（无循环依赖/无 ImportError）

**验证标准/Validation Criteria:**

- [ ] `Resolver().resolve("red_blue_debate_service")` 返回真实 `RedBlueDebateService` 实例且 isinstance `RedBlueDebateServicePort`
- [ ] `resolve("debate_evaluator")` 两次 resolve 返回同一实例（SINGLETON 生效）
- [ ] 契约测试 `tests/contracts/test_port_contract_red_blue_debate_service.py` 11 维度通过（含 `REQUIRED_METHODS = ["run_debate", "get_debate_result"]`）
- [ ] 契约测试 `tests/contracts/test_port_contract_debate_session_repository.py` 11 维度通过
- [ ] `poetry run pytest tests/contracts/ -q` 全量通过（既有契约测试零回归——tests/contracts/ 现 76 个测试文件、覆盖 157 个注册端口）

### AC-9: 集成测试 + 架构验证测试 + 性能验收（epics 硬路径）

**Given** epics_v1.0.md:1293-1295 性能指标（P95<30s / 视角准确率≥90% / 共识识别准确率≥85%）与 :1307-1308 硬性要求的测试文件路径
**When** 落地集成测试、架构验证测试与性能基准
**Then**

- **集成测试**（`tests/integration/test_red_blue_debate_integration.py`，真实服务优先）：
  - **真实服务组装场景**（CI 常跑）：真实 `RedBlueDebateService` + 真实 `DebateEvaluator` + 真实 `InMemoryDebateSessionRepository` + `AsyncMock(spec=LLMClientPort)` Fake 分派 + `AsyncMock(spec=EventPublisher)`（端口适配器 mock 例外，CLAUDE.md §5 允许面）——端到端 Happy path + 异常路径 + 事件发布 + 仓储状态追踪
  - **真实 LLM 场景**（`@pytest.mark.llm` + 动态 skip）：`LLMConfig.from_env()` 或 UDMR cloud config 探测（`test_acceptance_entity_extraction.py` 三重门模式）→ 真实议题（如"公司是否应在下一财年进入东南亚市场"）→ 断言双视角非空、立场声明遵循（stance 含立场关键词）、共识/分歧区域非空、**端到端耗时 < 30s**
  - **编排开销基准**（Fake LLM 零耗时注入）：断言纯编排开销 < 1s（smoke 级证据：纯内存编排为微秒~毫秒量级，判别力边界 = 检出编排内意外混入真实 IO/网络客户端，不承担 LLM 侧延迟证明——LLM 侧见"LLM 调用安全约束"节延迟预算三段式声明）
- **架构验证测试**（`tests/unit/architecture/test_red_blue_debate.py`，**epics 硬路径无 `_arch_` 前缀**，4-4 `test_docker_sandbox.py` 先例）：
  - **epics:1288-1290 架构测试三项 → 本 Story 测试面映射**（traceability，防验收漏项）：①「红蓝辩论测试-验证单 Agent 多视角」→ 本架构测试（整体约束组）+ `test_red_blue_debate_integration.py`（端到端单 Agent 双视角）+ AC-7 组服务单测；②「视角生成测试-验证激进派和保守派分析」→ `test_red_blue_debate_service.py`（红/蓝 schema 身份分派断言 + 立场遵循）+ `test_debate.py`（PerspectiveAnalysis 不变量）；③「风险视图测试-验证共识与分歧区域」→ `test_debate.py`（RiskView/ConsensusArea/DisagreementArea 不变量）+ AC-7 合成场景（共识/分歧非空断言）
  - 领域零依赖 AST 扫描（debate 相关 domain 文件 FORBIDDEN_IMPORTS 黑名单：pydantic/sqlalchemy/redis/fastapi/litellm 等）
  - `TEMPERATURE_PROFILE` 常量值断言 == {"red": 0.8, "blue": 0.5, "synthesis": 0.2}（FR-SP-10 对齐门禁）
  - 3 端口 PortSpec 10 字段元数据完整性 + 依赖方向（domain ← application ← infrastructure）
  - 禁止在服务文件本地定义 Protocol/Port 抽象（架构约束）
- **性能验收策略（诚实工程声明，防"完成度造假"）**：
  - **CI 可验证代理指标**：结构完整率 100%（`structured_generate` Pydantic 校验 + VO 不变量通过率）+ 立场遵循断言（Fake 与真实 LLM 双场景）+ 编排开销 <1s + 无重试路径上界论证（含重试最坏 ≈39s/调用为已声明的接受风险，见延迟预算三段式）
  - **语义准确率（视角≥90%/共识识别≥85%）无法在 CI 硬验收**（依赖评估数据集与真实 LLM 行为）——本 Story 以"结构完整率 + 立场声明遵循 + 共识/分歧非空"为代理指标交付；量化语义评估纳入 Story 5.8（Agent 输出质量评估）评估数据集体系，**本 Story 不伪造该两项指标的通过证据**
  - P95<30s：真实 LLM 单点计时（<30s 断言，P95 的单点代理）+ 无重试路径上界论证交付（含重试最坏 ≈39s/调用为已声明的接受风险）；批量 P95 分布统计随 Story 5.7（Phoenix 评估）落地

**验证标准/Validation Criteria:**

- [ ] `tests/integration/test_red_blue_debate_integration.py` 真实服务组装场景全过（`-m "not llm"` 亦全过）
- [ ] 真实 LLM 场景在有 LLM 环境通过 / 无环境动态 skip（不红）
- [ ] `tests/unit/architecture/test_red_blue_debate.py` 覆盖零依赖/温度常量/PortSpec/依赖方向四组断言
- [ ] `poetry run ruff check src/ tests/` + `poetry run mypy src/` 通过
- [ ] `pytest tests/ -n 8` 并行通过

### AC-10: BDD 验收测试（Gherkin 中文，R6 模板）

**Given** Story 需通过 Gherkin 验收（CLAUDE.md §5 强制 + R6 模板规范）
**When** 创建中文 Gherkin feature 文件 + BDD step 实现
**Then**

- **Feature 文件**：`tests/acceptance/test_acceptance_red_blue_debate.feature`
  - **头部组织（双先例组合）**：第 1 行 `# language: zh-CN` + 第 2 行 Story 注释（`# Story 4.5 — 红蓝辩论机制基础(BDD 验收场景,完整覆盖 10 条 AC)`——此形态先例为 4.1b `test_acceptance_data_source.feature` 与 4.4 `test_acceptance_docker_sandbox.feature`；R6 模板 `test_acceptance_postgresql_relational_layer.feature` 第 2 行直接是 `功能:`，其贡献的是三段式+背景块+`# ====` 横幅形态）+ `功能:` 三段式（角色+需求+目的）+ `背景:` 块（共用前置：辩论服务已初始化）+ 按 AC 编号 `# ====` 注释横幅分组
  - **场景命名**：`场景: AC-N.M - 中文细分描述`（对齐 4.3 编号式样板）
  - **异常断言双行**：`那么 抛出 XXX异常` + `并且 错误码为 EXCEPTION_xxx`
  - **场景清单**（完整覆盖 10 个 AC 分组，每组 ≥ 1 子场景）：
    - **AC-1 组**（值对象）：AC-1.1 合法构造全字段 / AC-1.2~1.5 四组不变量失败（title 空 / confidence 越界 / RiskView 区域空 / risk_level 非法）
    - **AC-2 组**（状态机）：AC-2.1 合法全路径迁移 + state_version 递增 / AC-2.2 非法迁移抛 243 / AC-2.3 终态不变量
    - **AC-3 组**（异常）：AC-3.1~3.3 三个异常构造 + code 断言 / AC-3.4 HTTP 映射（500/500/422）反向验证
    - **AC-4 组**（评估器）：AC-4.1 重复率已知值 / AC-4.2 增益率已知值 / AC-4.3 分化度两极值 + 中文用例 / AC-4.4 空文本边界
    - **AC-5 组**（仓储）：AC-5.1 save→get roundtrip / AC-5.2 未知名 None / AC-5.3 并发安全
    - **AC-6 组**（事件）：AC-6.1 事件构造 + to_dict/from_dict roundtrip / AC-6.2 双通道映射一致（YAML == DEFAULT_MAPPINGS + RELIABLE）
    - **AC-7 组**（服务编排，核心）：AC-7.1 Happy path 三段结构 / AC-7.2 温度阶梯（按分派身份断言红 0.8 蓝 0.5 合成 0.2）/ AC-7.3 红蓝生成时间窗口重叠（Fake 记录 start/end 时间戳断言 `blue.start < red.end` 且 `red.start < blue.end`——串行实现必红）/ AC-7.4 视角互相不可见（限定视角生成两次调用，合成豁免）/ AC-7.5 生成失败→420 / AC-7.6 合成失败→421 / AC-7.7 分化不足→422 / AC-7.8 分化警告不抛异常 / AC-7.9 事件发布字段断言
    - **AC-8 组**（端口注册）：AC-8.1 三端口注册 + PortSpec 元数据 / AC-8.2 resolver 解析真实实例
    - **AC-9 组**（集成/架构/性能）：AC-9.1 架构零依赖 + 温度常量 / AC-9.2 编排开销 <1s
    - **收尾验收组**（4.3 固定套路）：`收尾 - 覆盖率门禁达标`（src/tests 完成清单逐项确认）
- **BDD step 文件**：`tests/acceptance/test_acceptance_red_blue_debate.py`
  - **绑定方式**：`@scenario` 显式逐场景绑定（R6 模板模式）+ `context: dict[str, Any]` fixture 跨步骤传递（4.1a 模式）——两种既有主流模式的组合
  - 文件头 docstring：Story 号 + 真实服务要求 + 运行命令 + **6 项关键约定**（对齐 4.1a 样板：@given/@when/@then 装饰器 + context dict；真实服务实例（真实 `RedBlueDebateService` + `DebateEvaluator` + `InMemoryDebateSessionRepository`，**仅 LLM/EventPublisher 端口适配器 Fake**）；步骤严格按 AC 顺序 `# ====` 分隔；异常 try/except 捕获到 `context["query_error"]` 后 isinstance + code 断言；禁止 mock 核心域服务；LLM 不可用 `pytest.skip()` 动态跳过）
  - **步骤函数形态**：同步 `def` + `event_loop.run_until_complete(coro)`（模块级 event_loop fixture）；**禁止 `@pytest.mark.asyncio`**
  - **Fake LLM 工厂**：`_make_fake_llm(red: PerspectiveAnalysisSchema, blue: ..., risk: ...) -> AsyncMock`——`structured_generate.side_effect` 按 **response_schema 身份分派**（PerspectiveAnalysisSchema + temperature 0.8→红 / 0.5→蓝；RiskViewSchema→合成；禁止按 system_prompt 子串分派——裁判 prompt 同时含红蓝标记必误路由），闭包内联按分派记录 `(prompt, system_prompt, response_schema, temperature, start_ts, end_ts)` 序列供温度/独立性/并发窗口断言，并断言各调用 system_prompt 含对应角色标记（红"激进派"/蓝"保守派"/裁判"裁判"）
  - 共享 fixtures：`context()` / `debate_session_repository()`（真实 InMemory）/ `event_loop`（module 级）

**验证标准/Validation Criteria:**

- [ ] feature 文件 `# language: zh-CN` 首行 + Story 注释次行 + 功能三段式 + 背景: 块
- [ ] 完整覆盖 10 个 AC 分组 + 收尾验收（每组 ≥ 1 子场景，场景命名 `AC-N.M - 描述`）
- [ ] 异常场景双断言（抛出 XXX异常 + 错误码为 EXCEPTION_xxx）
- [ ] step 文件 `@scenario` 显式绑定全部场景 + 6 项关键约定 docstring
- [ ] 步骤函数同步 def + event_loop.run_until_complete；零 `@pytest.mark.asyncio`
- [ ] 真实服务链（仅 LLM/publisher 端口 Fake）；LLM 场景动态 skip
- [ ] 全部场景通过（`poetry run pytest tests/acceptance/test_acceptance_red_blue_debate.py -v`）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/debate_events.py`
- [ ] 使用标准库 dataclass 实现领域事件（`@dataclass(frozen=True)` 继承 `DomainEvent`），禁止在领域层依赖 Pydantic
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `DebateCompleted`）
- [ ] `event_type` init=False 自动注册 + `__post_init__` 填 aggregate（`sandbox_events.py` 惯例）

#### 数据模型 (Data Models)
- [ ] 值对象/实体定义位于 `src/domain/value_objects/debate.py` + `src/domain/entities/debate_session.py`
- [ ] 7 个 frozen VO + 1 个枚举（共 8 类型）+ 1 个状态机聚合根（签名见端口契约节）
- [ ] Pydantic LLM 输出 Schema 位于应用层 `debate_schemas.py`（领域零依赖红线）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports/debate_session_repository.py` 与 `src/application/ports/red_blue_debate_service.py`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，3 个新端口登记为 `PortSpec`（10 字段）
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约测试：`test_port_contract_red_blue_debate_service.py` + `test_port_contract_debate_session_repository.py`（11 维度）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义（`RedBlueDebateServicePort` 唯一编排入口）
- [ ] 端口具备唯一名称、版本（v1.0.0）、owner（tool-team）、compatibility
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

#### 端口契约清单执行约束（强制）
- [ ] 本 Story 端口清单（debate_session_repository / debate_evaluator / red_blue_debate_service）是唯一事实源
- [ ] 禁止新增未登记端口（如 DebateLlmPort——LLMClientPort 复用即可，禁止语义重复端口），禁止未同步更新 registry/resolver/contract test
- [ ] 每个端口同时具备 contract（Protocol 文件）、registry（composition_root）、resolver 验证、contract test（11 维度）、owner、version
- [ ] 未通过 Contract Gate 检查的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)
- [ ] **新增 3 异常**（EXCEPTION_420/421/422，debate 子域 420-429）——继承链/HTTP 映射/上下文/反模式禁止详见"领域异常契约"节
- [ ] **复用 3 异常**（242 实体验证 / 243 状态迁移 / 330-332 作为 cause 链入）——不重复建类
- [ ] 5 项 Checklist（定义文件 / `_code_ranges.py` 两表 / `__init__.py` / `EXCEPTION_HTTP_MAP` / 设计文档 §3.3.2 同步）Task 0 完成
- [ ] 异常路径 Gherkin 场景纳入 AC-3 组（420/421/422 三条 + HTTP 映射反向验证）

#### API 契约 (API Contract)
- [ ] 本 Story **不涉及 HTTP API**（对齐 4.1a~4.4 纯服务层先例；`docs/api/openapi.yaml` 不变更）——接口层暴露随 Epic 7 落地

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 辩论 VO/聚合根/评估器算法/端口/异常/事件，零外部依赖 |
| application | `src/application/` | `RedBlueDebateService` 编排 + prompts/schemas + 服务端口 |
| interfaces | `src/interfaces/` | 本 Story 无变更 |
| infrastructure | `src/infrastructure/` | `InMemoryDebateSessionRepository`（LLM 实现复用不动） |

**领域层零依赖原则**：`src/domain/` 仅用 Python 标准库；禁止导入 pydantic/litellm/langgraph/prefect/fastapi/sqlalchemy/redis 等（`.importlinter` + 架构测试双重校验）

**依赖方向矩阵**（本 Story 新增文件的合法依赖）：
| 新增文件 | 允许依赖 |
|----------|----------|
| `domain/value_objects/debate.py` | 标准库 + `domain/exceptions` |
| `domain/entities/debate_session.py` | 标准库 + `domain/exceptions` + `domain/value_objects` |
| `domain/services/debate_evaluator.py` | 标准库 + `domain/value_objects` |
| `domain/ports/debate_session_repository.py` | 标准库 + `domain/entities` |
| `domain/events/debate_events.py` | 标准库 + `domain/events/base` |
| `application/services/red_blue_debate_service.py` | `domain/**`（LLMClientPort/ExecutionContext/EventPublisher）+ `application/services/debate_schemas` + `application/services/debate_prompts` |
| `application/ports/red_blue_debate_service.py` | `domain/**` |
| `infrastructure/storage/inmemory/debate_session_repository.py` | `domain/ports` + `domain/entities` + 标准库 |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_red_blue_debate.feature`（R6 模板组织）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_red_blue_debate.py`（@scenario 显式绑定 + context dict）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases + 收尾验收）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试；同步 `def` 形态
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 三新异常（420/421/422）各 ≥ 1 场景 + 状态机非法迁移（243）+ VO 不变量（242）场景

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 3 新异常 5 项 Checklist 登记完成（含 HTTP 映射 + 设计文档同步）
- [ ] `DebateCompleted` 双通道四处登记完成

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
| **TDD 单元测试** | 辩论值对象 | 8 个 VO 构造 + 5 组不变量 | `tests/unit/domain/value_objects/test_debate.py` | Task 1 |
| **TDD 单元测试** | DebateSession | 状态机迁移/终态不变量/迁移计数 | `tests/unit/domain/entities/test_debate_session.py` | Task 2 |
| **TDD 单元测试** | 辩论异常 | 构造/to_dict/HTTP 映射/code 唯一性 | `tests/unit/domain/exceptions/test_debate_exceptions.py` | Task 3 |
| **TDD 单元测试** | DebateEvaluator | 三算法已知值/边界/中文 | `tests/unit/domain/services/test_debate_evaluator.py` | Task 4 |
| **TDD 单元测试** | InMemory 仓储 | roundtrip/None/并发 50 | `tests/unit/infrastructure/storage/test_debate_session_repository.py` | Task 2 |
| **TDD 单元测试** | 事件 | roundtrip/aggregate 归属 | `tests/unit/domain/events/test_debate_events.py` | Task 5 |
| **TDD 单元测试** | debate_schemas | Schema 字段约束/to_domain 转换 | `tests/unit/application/services/test_debate_schemas.py` | Task 6 |
| **TDD 单元测试** | debate_prompts | 视角映射/模板占位符/角色标记 | `tests/unit/application/services/test_debate_prompts.py` | Task 6 |
| **TDD 单元测试** | RedBlueDebateService | 温度阶梯/并发/独立性/异常路径/事件 | `tests/unit/application/services/test_red_blue_debate_service.py` | Task 7 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（10 AC 组 + 收尾） | `tests/acceptance/test_acceptance_red_blue_debate.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | @scenario 绑定 + 步骤函数 | `tests/acceptance/test_acceptance_red_blue_debate.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上 feature/py | Task 10 |
| **TDD 契约测试** | 服务端口/仓储端口 | PortSpec 11 维度 | `tests/contracts/test_port_contract_red_blue_debate_service.py` + `test_port_contract_debate_session_repository.py` | Task 8 |
| **TDD 契约测试** | 事件契约 + 双通道 | 事件 Schema + YAML/DEFAULT_MAPPINGS 一致 | `tests/contracts/test_event_contract_debate_events.py` + `test_event_channel_mapping_debate.py` | Task 5 |
| **SDD 架构验证** | 六边形架构约束 | 零依赖/温度常量/PortSpec/依赖方向 | `tests/unit/architecture/test_red_blue_debate.py`（epics 硬路径） | Task 9 |
| **集成测试** | 真实服务组装 + 真实 LLM | 端到端编排/事件/性能/真实议题 | `tests/integration/test_red_blue_debate_integration.py` | Task 9 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md:1297-1299（Story 4.5 AC）与项目 CI 门禁：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（epics AC 硬要求，`pytest --cov=src/application`）
- [ ] **领域层覆盖率 ≥90%**（新增辩论领域代码全部为有逻辑实现，不适用骨架豁免）
- [ ] **集成测试覆盖率 ≥75%**（epics_v1.0.md:1299 AC 硬要求；执行口径：`pytest tests/integration/test_red_blue_debate_integration.py --cov=src/application/services/red_blue_debate_service --cov=src/application/services/debate_schemas --cov=src/application/services/debate_prompts --cov=src/domain/services/debate_evaluator --cov-fail-under=75`——辩论新增核心模块的集成场景行覆盖率）
- [ ] **关键路径覆盖率 100%**（`run_debate` 编排全分支：Happy/生成失败/合成失败/低分化/警告/事件失败不覆写）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`，E/F/I/N/W，行宽 128）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **lint-imports 通过**（`poetry run lint-imports`，六边形依赖方向）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

（完整规则见"🎯 测试隔离约束"节，此处摘要执行清单）

- [ ] Fake LLM 按 response_schema 身份分派（+temperature 区分红蓝）+ 按身份温度断言
- [ ] 真实 LLM 场景 `@pytest.mark.llm` + `probe_llm_endpoint_reachable` + `pytest.skip()` 动态跳过
- [ ] `asyncio.Lock` 类变量（InMemory 仓储）
- [ ] BDD 步骤同步 def + `event_loop.run_until_complete()`，零 `@pytest.mark.asyncio`
- [ ] `pytest tests/ -n 8` 并行通过；连续 5 次运行无随机失败

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 值对象 + 不变量 | Task 1 | TDD 循环 A（VO/枚举） | `test_debate.py` |
| AC-2 | DebateSession 状态机 | Task 2 | TDD 循环 A（聚合根） | `test_debate_session.py` |
| AC-5 | Repository 端口 + InMemory | Task 2 | TDD 循环 B（端口/实现） | `test_debate_session_repository.py` |
| AC-3 | 3 新异常 + 5 项 Checklist | Task 3 | TDD 循环 A（异常登记） | `test_debate_exceptions.py` |
| AC-4 | DebateEvaluator 三算法 | Task 4 | TDD 循环 A（评估器） | `test_debate_evaluator.py` |
| AC-6 | DebateCompleted + 双通道 | Task 5 | TDD 循环 A（事件 + 契约） | `test_debate_events.py` + 契约 2 件 |
| AC-7 | 服务编排 + prompts/schemas | Task 6/7 | Task 6 双循环 + Task 7 双循环 | `test_red_blue_debate_service.py` |
| AC-8 | 端口注册 + 契约测试 | Task 8 | TDD 循环 A（注册/契约） | 契约测试 2 件 |
| AC-9 | 集成/架构/性能 | Task 9 | 双循环（集成 + 架构） | 硬路径 2 件 |
| AC-10 | BDD 验收（R6 模板） | Task 0/10 | Task 0 场景编写 + Task 10 收尾 | acceptance 2 件 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-10（全部规范输入）

> **目的：** 在进入代码实现前，明确异常登记、事件登记、Gherkin 验收标准与六边形架构边界。

- [ ] Subtask 0.1: 完成异常 5 项 Checklist（`debate_exceptions.py` 3 类 + `_code_ranges.py` 两表 + `__init__.py` + `EXCEPTION_HTTP_MAP` 3 条 + `sisys-uni-exception-design.md §3.3.2` 同步；运行 `test_code_ranges.py` + `test_error_code_uniqueness.py` 确认通过——**登记本身即实现，TDD 红绿在 Task 3 展开单测**）
- [ ] Subtask 0.2: 创建 `src/domain/events/debate_events.py` 空规范骨架（仅 docstring 编码事件字段清单）+ 四处登记中的两处配置（`event_channels.yaml` + `DEFAULT_MAPPINGS` 条目；事件类实现随 Task 5 TDD 落地）
- [ ] Subtask 0.3: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_red_blue_debate.feature`（R6 模板组织：背景块 + 10 AC 分组 + 收尾场景，场景清单见 AC-10）
- [ ] Subtask 0.4: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_red_blue_debate.py`（@scenario 显式绑定 + context dict + Fake LLM 工厂 + event_loop fixture；实现步骤对尚不存在的类型将 ImportError——预期红）
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证：失败原因为 `ModuleNotFoundError`/`ImportError`，非语法错误）

**完成标准/Definition of Done:**
- [ ] 异常与事件登记完成且既有异常测试套件通过
- [ ] Gherkin + BDD 步骤文件就绪，运行确认红
- [ ] 已声明中间态窗口：Task 1~6 期间本验收 .py 因顶部 import 未落地类型呈 collection error（预期中间态，与 4.1a~4.4 先例的"运行失败即红"口径一致）；任务级验证以目标测试文件为准，全量 `pytest tests/` 到 Task 7 后恢复无噪
- [ ] 规范文档（本 Story 端口契约/异常契约/依赖矩阵）经 dev 人工复核

---

### Task 1: 领域值对象与枚举（领域层）

**关联 AC:** AC-1

#### TDD 循环 [A]：辩论值对象集

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_debate.py`（`_make_debate_topic/_make_perspective/_make_risk_view` 工厂 + 合法构造 + 5 组不变量失败用例） |
| 🟢 绿 | 实现 `src/domain/value_objects/debate.py`（8 类型 + `__post_init__` 校验，签名见端口契约节） |
| 🔄 重构 | 类型注解补全 + Google 全中文 docstring + `value_objects/__init__.py` re-export |

- [ ] Subtask 1.1: 🔴 红 — 编写值对象失败测试（含每项不变量的 context 字段断言）
- [ ] Subtask 1.2: 🟢 绿 — 实现 8 个 frozen dataclass + 枚举最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化校验提取（`_validate_non_empty` 等私有助手）、运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] 8 类型实现 + `__init__.py` 导出
- [ ] 不变量 5 组用例全绿
- [ ] `lint-imports` 零依赖通过

---

### Task 2: DebateSession 聚合根 + Repository 端口（领域层 + 基础设施层）

**关联 AC:** AC-2, AC-5

#### TDD 循环 [A]：`DebateSession` 聚合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_debate_session.py`（合法全路径迁移 + state_version 递增 / 非法迁移抛 243 / 终态不变量抛 242 / validate 边界） |
| 🟢 绿 | 实现 `src/domain/entities/debate_session.py`（状态枚举 + 迁移矩阵 + `can_transition_to`/`transition_to` + `validate`，`ToolExecution` 同构） |
| 🔄 重构 | docstring 不变量清单 + `__all__` 导出 |

#### TDD 循环 [B]：`DebateSessionRepositoryPort` + InMemory 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_debate_session_repository.py`（roundtrip / get_by_id None / `asyncio.gather` 50 并发 save 无丢失） |
| 🟢 绿 | 实现 `src/domain/ports/debate_session_repository.py` + `src/infrastructure/storage/inmemory/debate_session_repository.py`（asyncio.Lock 类变量） |
| 🔄 重构 | 端口 docstring 异常声明 + `ports`/`storage` `__init__` 导出 |

- [ ] Subtask 2.1: 🔴 红 — 实体状态机失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `DebateSession`
- [ ] Subtask 2.3: 🔄 重构 — 优化实体代码
- [ ] Subtask 2.4: 🔴 红 — 仓储端口/实现失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现端口 Protocol + InMemory 仓储
- [ ] Subtask 2.6: 🔄 重构 — 优化仓储代码

**完成标准/Definition of Done:**
- [ ] 状态机全分支覆盖 + 并发安全验证
- [ ] 两 TDD 循环全绿

---

### Task 3: 3 个新辩论异常（领域层）

**关联 AC:** AC-3

> Task 0 已完成登记（5 项 Checklist）；本 Task 补齐 TDD 单测闭环。

#### TDD 循环 [A]：辩论异常类单测

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_debate_exceptions.py`（3 类构造/context 字段/to_dict 序列化/cause 链/HTTP 映射反向验证 500/500/422） |
| 🟢 绿 | 补齐 `debate_exceptions.py` 3 类完整实现（Task 0 骨架 → 完整构造器与 docstring） |
| 🔄 重构 | 文件头"继承链选择理由" docstring 终稿 + 与 `relevance_exceptions.py` 格式对齐校对 |

- [ ] Subtask 3.1: 🔴 红 — 编写 3 类异常失败测试
- [ ] Subtask 3.2: 🟢 绿 — 完整实现 3 类异常
- [ ] Subtask 3.3: 🔄 重构 — 优化 docstring 与 context 组装

**完成标准/Definition of Done:**
- [ ] 异常单测 + 既有 `test_code_ranges.py`/`test_error_code_uniqueness.py` 全绿
- [ ] 三条 grep 自查零输出（本 Story 路径）

---

### Task 4: DebateEvaluator 领域服务（领域层）

**关联 AC:** AC-4

#### TDD 循环 [A]：三算法

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_debate_evaluator.py`（`compute_repetition_rate`/`compute_gain_rate`/`evaluate_overlap` 已知值精确断言 + 空文本/单字符/中文边界 + 纯函数确定性） |
| 🟢 绿 | 实现 `src/domain/services/debate_evaluator.py`（字符 bigram 提取 + Jaccard 集合运算，标准库） |
| 🔄 重构 | 算法 docstring（公式 + architecture.md §7.3 阈值对应关系）+ 常量提取 |

- [ ] Subtask 4.1: 🔴 红 — 编写三算法失败测试
- [ ] Subtask 4.2: 🟢 绿 — 实现评估器最小代码
- [ ] Subtask 4.3: 🔄 重构 — 优化算法与文档

**完成标准/Definition of Done:**
- [ ] 三算法全边界用例绿
- [ ] GAP-CRITICAL-09 清偿（评估器算法落地）

---

### Task 5: DebateCompleted 事件 + 双通道契约（领域层 + 基础设施配置）

**关联 AC:** AC-6

#### TDD 循环 [A]：事件类 + 双通道一致性契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_debate_events.py`（构造/aggregate 归属/roundtrip）+ `tests/contracts/test_event_contract_debate_events.py`（Schema 契约）+ `tests/contracts/test_event_channel_mapping_debate.py`（YAML == DEFAULT_MAPPINGS 逐字段 + RELIABLE） |
| 🟢 绿 | 实现 `src/domain/events/debate_events.py` 完整事件类 + `events/__init__.py` 导出（Task 0 已登记 yaml/router 两处配置，此处验证一致性测试转绿） |
| 🔄 重构 | `__post_init__` metadata 透传校对（`sandbox_events.py` 对齐） |

- [ ] Subtask 5.1: 🔴 红 — 编写事件 + 双通道契约失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现事件类与四处登记收口
- [ ] Subtask 5.3: 🔄 重构 — 优化事件代码

**完成标准/Definition of Done:**
- [ ] roundtrip + 双通道一致性契约全绿
- [ ] `ChannelRouter.get_delivery_mode("DebateCompleted") == RELIABLE`

---

### Task 6: 应用层 prompts 与 schemas

**关联 AC:** AC-7（前置半场）

#### TDD 循环 [A]：`debate_schemas.py`（Pydantic 结构化输出 Schema）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_debate_schemas.py`（Schema 字段约束：arguments 1~8/confidence 0~1/risk_level Literal/`to_domain()` 转换 + 越界拒绝） |
| 🟢 绿 | 实现 `src/application/services/debate_schemas.py`（`PerspectiveAnalysisSchema`/`RiskViewSchema`/嵌套 Area Schema + `to_domain()`） |
| 🔄 重构 | Field 描述中文化 + `model_config` 对齐既有 Schema 风格 |

#### TDD 循环 [B]：`debate_prompts.py`（视角 prompt 映射）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_debate_prompts.py`（PERSPECTIVE_PROMPT_MAP 覆盖红蓝两键/模板占位符 format 可用/角色标记短语存在——供调用断言与立场遵循断言（分派按 response_schema 身份，见测试隔离约束节）/SYNTHESIS 模板含红蓝注入占位） |
| 🟢 绿 | 实现 `src/application/services/debate_prompts.py`（红/蓝/裁判三组 system + user 模板，全中文，含角色标记） |
| 🔄 重构 | prompt 文案评审（立场纪律清晰、无内部实现泄露） |

- [ ] Subtask 6.1: 🔴 红 — Schema 失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现 Schema
- [ ] Subtask 6.3: 🔄 重构 — 优化 Schema
- [ ] Subtask 6.4: 🔴 红 — prompts 失败测试
- [ ] Subtask 6.5: 🟢 绿 — 实现 prompts
- [ ] Subtask 6.6: 🔄 重构 — 优化 prompts

**完成标准/Definition of Done:**
- [ ] Schema 约束 + 转换全绿；prompt 映射与占位符全绿
- [ ] 领域零依赖不受影响（pydantic 仅应用层）

---

### Task 7: RedBlueDebateService 编排（应用层核心）

**关联 AC:** AC-7

#### TDD 循环 [A]：Happy path（温度阶梯 + 并发 + 独立性 + 事件）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_red_blue_debate_service.py` Happy 组（三段结构 / 温度集合 {0.8,0.5,0.2} / gather 并发性（sleep 注入计时）/ 视角 prompt 互相不可见 / 事件 publish 字段 / per-call timeout 传递 / 仓储状态 IDLE→GENERATING→SYNTHESIZING→COMPLETED） |
| 🟢 绿 | 实现 `src/application/services/red_blue_debate_service.py` + `src/application/ports/red_blue_debate_service.py`（编排八步流程，见 AC-7） |
| 🔄 重构 | 编排步骤方法化（`_generate_perspectives`/`_check_divergence`/`_synthesize_risk_view`/`_publish_completion`）+ TEMPERATURE_PROFILE 等常量模块化 |

#### TDD 循环 [B]：异常路径与分化度门控

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 补充异常组测试（红视角 LLMAPIError→420 + context.perspective / 蓝视角对称用例 / 合成失败→421 / 重叠率 ≥0.95→422 + session FAILED 落库 / 0.80~0.95 警告不抛 / 事件 publish 双形态失败（PublishResult is_success=False 与 raise）不覆写结果 / get_debate_result：COMPLETED 重建（quality/duration_ms 推导公式）与非 COMPLETED（含 FAILED）返回 None） |
| 🟢 绿 | 实现异常包装与门控分支 |
| 🔄 重构 | 异常 context 组装统一助手 |

- [ ] Subtask 7.1: 🔴 红 — Happy path 失败测试
- [ ] Subtask 7.2: 🟢 绿 — 实现服务编排主体
- [ ] Subtask 7.3: 🔄 重构 — 方法化与常量提取
- [ ] Subtask 7.4: 🔴 红 — 异常路径失败测试
- [ ] Subtask 7.5: 🟢 绿 — 实现门控与包装
- [ ] Subtask 7.6: 🔄 重构 — 优化异常处理

**完成标准/Definition of Done:**
- [ ] 编排全分支覆盖（关键路径 100%）
- [ ] 应用层覆盖率 ≥85% 贡献达成
- [ ] BDD AC-7 组场景转绿

---

### Task 8: composition_root 注册 + 端口契约测试

**关联 AC:** AC-8

#### TDD 循环 [A]：三端口注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_red_blue_debate_service.py` + `test_port_contract_debate_session_repository.py`（11 维度，PORT_NAME/INTERFACE/REQUIRED_METHODS 类常量 + `_global_registry.get()` 断言） |
| 🟢 绿 | `src/composition_root.py` 注册 3 端口（参数见端口契约节表格；lambda 工厂四依赖 resolve） |
| 🔄 重构 | 注册块注释（Story 4.5 标注 + 端口用途）与既有 tool 域注册块风格对齐 |

- [ ] Subtask 8.1: 🔴 红 — 编写两件契约失败测试
- [ ] Subtask 8.2: 🟢 绿 — 组合根注册 3 端口
- [ ] Subtask 8.3: 🔄 重构 — 注释与风格对齐
- [ ] Subtask 8.4: 验证 `bootstrap()` 全量注册无回归（`pytest tests/contracts/ -q` + resolver SINGLETON 断言）

**完成标准/Definition of Done:**
- [ ] 11 维度契约测试 × 2 全绿
- [ ] 既有契约套件零回归

---

### Task 9: 集成测试 + 架构验证测试 + 性能基准（epics 硬路径）

**关联 AC:** AC-9

#### TDD 循环 [A]：集成测试（真实服务组装 + 真实 LLM + 编排开销）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_red_blue_debate_integration.py`（真实组装场景：真实 Service/Evaluator/Repository + Fake LLM/publisher 端到端；真实 LLM 场景：三重门探测 + 动态 skip + 端到端 <30s；编排开销基准 <1s） |
| 🟢 绿 | 修复集成链路问题至全绿（`-m "not llm"` 常跑面） |
| 🔄 重构 | 场景函数命名与 marker 规范化（`@pytest.mark.llm`/`@pytest.mark.integration`） |

#### TDD 循环 [B]：架构验证测试（epics 硬路径）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_red_blue_debate.py`（**无 `_arch_` 前缀**：AST 零依赖扫描 / TEMPERATURE_PROFILE 值断言 / PortSpec 10 字段 / 依赖方向 / 禁止服务文件本地 Protocol） |
| 🟢 绿 | 修复架构违规（若有）至全绿 |
| 🔄 重构 | AST 零依赖扫描沿用既有各文件**私有 `_extract_imports` 复制先例**（`test_docker_sandbox.py:54-71` / `test_arch_strategic_tool_impl.py:74-90`——架构测试目录无共享助手模块，勿寻找不存在的公共件） |

- [ ] Subtask 9.1: 🔴 红 — 集成测试编写
- [ ] Subtask 9.2: 🟢 绿 — 集成链路全绿
- [ ] Subtask 9.3: 🔄 重构 — marker 规范化
- [ ] Subtask 9.4: 🔴 红 — 架构验证测试编写
- [ ] Subtask 9.5: 🟢 绿 — 架构面全绿
- [ ] Subtask 9.6: 🔄 重构 — AST 扫描形态对齐先例（私有 `_extract_imports` 复制式，无共享助手可复用）
- [ ] Subtask 9.7: 性能验收策略核验（AC-9 三段：CI 代理指标 / timeout 上界论证 / 真实 LLM 单点计时——诚实工程声明留痕）

**完成标准/Definition of Done:**
- [ ] epics 硬路径两文件落地且全绿
- [ ] `-m "not llm"` 全绿；真实 LLM 环境通过或动态 skip
- [ ] `ruff` + `mypy` + `lint-imports` 通过

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-10（收尾）+ 全 AC 复核

> **性质说明：** 本 Task 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 完善 feature 收尾验收场景（`收尾 - 覆盖率门禁达标` 等）与 BDD 步骤实现 |
| 🟢 绿 | 全量场景运行通过（10 AC 组 + 收尾） |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 10.1: 场景 1 — 验证 `src` 完成清单逐项确认（8 类型/聚合根/3 异常/评估器/端口 3/事件 1/服务 1/prompts/schemas/仓储实现）
- [ ] Subtask 10.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单逐项确认（测试分类表全量文件）
- [ ] Subtask 10.3: 运行开发结束验收测试并确认通过（`poetry run pytest tests/acceptance/test_acceptance_red_blue_debate.py -v`）
- [ ] Subtask 10.4: 运行 `pytest tests/ -n 8`、`ruff check`、`mypy`、`lint-imports` 收尾校验 + 三条 grep 自查零输出

**完成标准/Definition of Done:**
- [ ] `src` 与四类测试目录完成清单逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §7 + [`sisys-core-domain-design.md §17.3`](../../../docs/architecture/sisys-core-domain-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ DDD（聚合根/值对象/领域服务/领域事件）；单 Agent 多视角为 V1 多 Agent 辩论（Epic 9-10）的 MVP 替代（prd.md:456）
- **设计约束:** 领域层零依赖；端口统一注册（PortSpec 10 字段）；事件双通道投递（realtime Redis pub/sub + reliable RabbitMQ + Outbox）；异常是领域契约（debate 子域 420-429）；温度阶梯 0.8/0.5/0.2 与 FR-SP-10 V1 三阶段对齐
- **接口治理:** `register_port()` 唯一注册入口 + `Resolver` 自动注入 + 契约测试 11 维度 + ContractGate 兼容性
- **技术栈:** Python 3.11+ / FastAPI 0.104+（本 Story 无涉）/ litellm（经 `LLMClientPort` 间接）/ pytest 7+ + pytest-bdd 8.x / **零新增第三方依赖**

### 关键架构决策

**来源:** [`architecture.md §7.3`](../../../docs/architecture/architecture.md)（终止条件）+ ADR-009（辩论质量评估器）+ 本 Story 调研

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **【选中】应用服务直编排（注入 LLMClientPort，Summary/Relevance 同构）** | 不引入编排引擎复杂度；MVP 三次调用顺序简单；测试直接；对齐既有 3 个 LLM 应用服务先例 | 多轮演进时需在服务内自管理轮次状态（Epic 10 届时再评估迁移 LangGraph） | ✅ 9/10 |
| LangGraph debate 子图（新增 graph + state TypedDict + `_SUPPORTED_GRAPHS` 注册） | 状态图原生多轮演进；checkpointer 持久化 | 现有 `LangGraphEngine` 仅 submit/status 两方法、**无结果取回端口**（结果只能经事件带出）；MVP 占位节点不调 LLM，改造面大；Simplicity First 违背 | 5/10 |
| **【选中】红蓝独立生成（互相不可见）+ 合成阶段对抗** | 方法论正确（独立立场防锚定偏差）；gather 并发压缩延迟（P95 达标关键） | 失去"针对对方论点反驳"的对抗深度（V1 多轮补齐） | ✅ 8/10 |
| 蓝视角看到红方输出再反驳（串行） | 对抗性更强 | 锚定偏差（LLM 倾向认同先入观点）；串行延迟翻倍冲垮 P95；偏离 or.md"实例化两派独立辩论"语义 | 4/10 |
| **【选中】字符 bigram Jaccard（DebateEvaluator 算法族）** | 标准库实现、中文免分词、确定性纯函数、领域层零依赖 | 语义级相似度弱于 embedding（但 MVP 门控阈值 0.95/0.80 为粗粒度，够用；语义级评估属 Story 5.8） | ✅ 8/10 |
| 词级 Jaccard（需分词）/ embedding 余弦相似度 | 语义更准 | 领域层引入 jieba/向量依赖违反零依赖红线；分词移入应用层则算法割裂 | 3/10 |
| **【选中】新开 debate 子域 420-429 平铺 3 异常（无共同基类）** | data_source 410-419 独立段先例；relevance 平铺无基类先例；External/Business 继承自由 | 无 `except DebateError` 统一捕获（调用方按具体类捕获，语义更精确） | ✅ 8/10 |
| 复用 entity(245-249) / tool 子域 / 设 DebateError 基类 | 少改 `_code_ranges.py` | 语义错位（辩论非实体校验）；跨 External/Business 无法共基类 | 4/10 |
| **【选中】InMemory 仓储（无 migration）** | MVP 零 DB 足迹；epics AC 无持久化要求；端口抽象保留 PG 升级路径 | 重启丢失会话（MVP 可接受；Epic 10 审计需求时新增 migration） | ✅ 8/10 |
| 本 Story 即建 PG migration 016 | 审计完整 | 无消费场景的表（YAGNI）；增加 Story 体量与测试面 | 5/10 |

### 项目结构说明 Project Structure

```
.
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── debate_session.py              # 新增（Task 2）
│   │   ├── value_objects/
│   │   │   └── debate.py                      # 新增（Task 1，8 类型）
│   │   ├── events/
│   │   │   └── debate_events.py               # 新增（Task 0 骨架 + Task 5 实现）
│   │   ├── ports/
│   │   │   └── debate_session_repository.py   # 新增（Task 2）
│   │   ├── services/
│   │   │   └── debate_evaluator.py            # 新增（Task 4）
│   │   └── exceptions/
│   │       └── debate_exceptions.py           # 新增（Task 0 登记 + Task 3 实现）
│   ├── application/
│   │   ├── ports/
│   │   │   └── red_blue_debate_service.py     # 新增（Task 7）
│   │   └── services/
│   │       ├── red_blue_debate_service.py     # 新增（Task 7）
│   │       ├── debate_prompts.py              # 新增（Task 6）
│   │       └── debate_schemas.py              # 新增（Task 6）
│   ├── infrastructure/
│   │   └── storage/inmemory/
│   │       └── debate_session_repository.py   # 新增（Task 2）
│   └── composition_root.py                    # 修改（Task 8，+3 端口注册）
├── configs/
│   └── event_channels.yaml                    # 修改（Task 0，+DebateCompleted 条目）
├── src/infrastructure/messaging/
│   └── channel_router.py                      # 修改（Task 0，+DEFAULT_MAPPINGS 条目）
├── docs/architecture/
│   └── sisys-uni-exception-design.md          # 修改（Task 0，§3.3.2 +debate 子域）
└── tests/
    ├── unit/
    │   ├── domain/
    │   │   ├── value_objects/test_debate.py               # 新增（Task 1）
    │   │   ├── entities/test_debate_session.py            # 新增（Task 2）
    │   │   ├── services/test_debate_evaluator.py          # 新增（Task 4）
    │   │   ├── events/test_debate_events.py               # 新增（Task 5）
    │   │   └── exceptions/test_debate_exceptions.py       # 新增（Task 3）
    │   ├── application/services/
    │   │   ├── test_red_blue_debate_service.py            # 新增（Task 7）
    │   │   ├── test_debate_prompts.py                     # 新增（Task 6）
    │   │   └── test_debate_schemas.py                     # 新增（Task 6）
    │   ├── infrastructure/storage/
    │   │   └── test_debate_session_repository.py          # 新增（Task 2）
    │   └── architecture/
    │       └── test_red_blue_debate.py                    # 新增（Task 9，epics 硬路径无 _arch_ 前缀）
    ├── integration/
    │   └── test_red_blue_debate_integration.py            # 新增（Task 9，epics 硬路径）
    ├── contracts/
    │   ├── test_port_contract_red_blue_debate_service.py  # 新增（Task 8）
    │   ├── test_port_contract_debate_session_repository.py # 新增（Task 8）
    │   ├── test_event_contract_debate_events.py           # 新增（Task 5）
    │   └── test_event_channel_mapping_debate.py           # 新增（Task 5）
    └── acceptance/
        ├── test_acceptance_red_blue_debate.feature        # 新增（Task 0 + 10）
        └── test_acceptance_red_blue_debate.py             # 新增（Task 0 + 10）
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-4-docker-sandbox-execution.md](./4-4-docker-sandbox-execution.md)（done）/ [4-1f-skills-datasource-enhancement.md](./4-1f-skills-datasource-enhancement.md)（done，五轮审查收敛）/ 4-1a / 4-2 / 4-3（一致模式）

**关键学习/Key Learnings:**

- **端口向后兼容优先**（4-4/4.3 装饰器模式）：本 Story 复用 `LLMClientPort` 零修改（多轮历史拼 prompt，`ToolExecutionEngine` 同款），不触碰 `test_port_contract_llm_client.py` 三方法契约
- **PortSpec 10 字段 + 契约测试 11 维度**（4-1a/4-2/4-3/4-4 一致模式）：name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated；契约测试 PORT_NAME/INTERFACE/REQUIRED_METHODS 类常量组织
- **`set_data_source_resolver` 教训**（4.1b）：新增协作对象避免修改既有服务 `__init__` 签名破坏 BDD 断言——本 Story 全新服务无此包袱，但 `_build_tool_execution_engine` 风格的 lambda 工厂注入是注册范式
- **asyncio.Lock 类变量**（4.1a/4.4）：`InMemoryDebateSessionRepository._lock` 严格沿用
- **共享文件跨 Task 中间态红窗口显式声明**（4-1d D8 先例 + 4-1f）：Task 0 登记（异常/事件配置）与 Task 3/5 实现（单测/事件类）之间存在登记先行窗口——Task 0 DoD 显式声明"登记即实现骨架，TDD 红绿随后续 Task 展开"，不追求虚假全时绿
- **断言绊线是设计意图**（4-1d R2-F12）：温度常量断言（TEMPERATURE_PROFILE 值 == FR-SP-10）与双通道一致性断言（YAML == DEFAULT_MAPPINGS）是绊线——重构时保活改写而非删除
- **变异演示判别力**（4-1c/4-1f 先例）：Fake LLM 温度捕获 + 视角独立性断言（红 prompt 不含蓝输出）即本 Story 判别力形态
- **`EXCEPTION_HTTP_MAP` 注释与 code 严格一致**（4-4 发现的 4.1a 历史 bug：注释 309~312 vs 实际 311~314 偏差）：新增 3 条映射注释必须 `# 420`/`# 421`/`# 422` 对应
- **三层 Mock/Fake/Real 策略**：单元 Fake LLM（spec 端口适配器例外面）；集成真实服务组装 + 可选真实 LLM；验收真实服务链 + 仅端口适配器 Fake + 动态 skip
- **行号引用先读代码再动手**（4-1f v1.1.0 教训）：本 Story 文档行号与代码事实来自 2026-10-01 四视角调研（①战略工具域 ②LLM/编排基础设施 ③验收测试基础设施 ④端口/异常/事件体系）——实施时凡引用 file:line 先实地核实
- **条件注册闭包陷阱**（composition_root 先例）：注册块 lambda 内 import + 延迟执行，import 放 lambda 体内

**应用到本故事/Applied to This Story:**

- [ ] `LLMClientPort` 零修改复用（prompt 拼接承载多轮历史）
- [ ] 3 端口注册沿用 lambda 工厂 + `__import__` 惰性加载范式（`tool_chain_service` 样例）
- [ ] `InMemoryDebateSessionRepository` asyncio.Lock 类变量
- [ ] Task 0/3/5 登记与实现的中间态红窗口显式声明
- [ ] 温度常量 + 双通道两处一致性 = 架构测试绊线
- [ ] `# 420` 注释与 code 严格一致
- [ ] 提交前三条 grep 自查零输出（本 Story 路径清单见硬约束节）
- [ ] 11 维度契约测试 × 2 端口 + 事件契约 × 2 件
- [ ] Fake LLM 按 response_schema 身份分派（+temperature 区分红蓝）+ 按身份温度/独立性捕获断言

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（GLM-5.3 驱动） |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-10-01 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md:1277-1316`（Story 4.5）+ `:777`（依赖）+ `:165`（FR-SP-10 温度阶梯） |
| **架构文档** | `docs/architecture/architecture.md`（§7 裁决与辩论 + §7.3 评估规则 + :3141 FR-AC-11 + :3311 GAP-CRITICAL-09）+ `docs/architecture/sisys-core-domain-design.md`（§17.3.4-17.3.5）+ `docs/architecture/sisys-uni-exception-design.md` |
| **PRD** | `_bmad-output/planning-artifacts/prd.md`（:1817 FR-ST-05 + :456 MVP 替代策略 + :1236 温度三阶段） |
| **OR 公理** | `_bmad-output/planning-artifacts/or.md`（三.5.[3]:241 + 三.2.[3]:60 + 四.3:318-320） |
| **前置 Story** | `4-1a-strategic-tool-impl.md`（done）/ `3-2a-llm-client-infrastructure.md`（done）/ `4-4-docker-sandbox-execution.md`（done）/ `4-1f-skills-datasource-enhancement.md`（done） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **四视角调研** | 2026-10-01：①战略工具域实现（Tool 聚合根/ToolExecutionEngine/组合根注册范式/debate 绿地确认）②LLM Client 与编排基础设施（LLMClientPort 签名/temperature 传参链/Fake 工厂样例/LangGraph MVP 占位事实）③验收测试与测试基础设施（R6 模板结构/4.1a BDD 样板/集成隔离 fixture/契约测试模式）④端口/异常/事件体系（PortSpec 原文/CODE_RANGES 全表+420 空段确认/事件四处同步清单/157 端口现状） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md:1277-1316` 提取（FR-ST-05 + 3 项 AC + BDD Given/When/Then）
- [x] 架构约束从 `architecture.md` §7 + `CLAUDE.md` §5 + `sisys-uni-exception-design.md` 提取
- [x] 前置故事学习经验整合（4-1a / 4-4 / 4-1f 模式 + GAP-CRITICAL-09 清偿定位）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0 + Task 1-10，每个含完整 TDD 循环）
- [x] 项目结构对齐统一规范（六边形 4 层 + R1/R2/R3 复用决策）
- [x] 3 个新辩论异常 EXCEPTION_420~422 5 项 Checklist 定义完成（debate 子域 420-429 新开段）
- [x] LLMClientPort 零修改复用决策明确（温度阶梯经 LLMConfig 分档传参）
- [x] 温度阶梯 0.8/0.5/0.2 与 FR-SP-10 V1 演进路径锁定（TEMPERATURE_PROFILE 常量 + 架构测试绊线）
- [x] 性能验收诚实工程策略明确（CI 代理指标 + timeout 上界论证 + 语义准确率移交 Story 5.8，防完成度造假）

### 文件清单 File List

**创建的文件/Created Files:**

- `_bmad-output/implementation-artifacts/stories/4-5-red-blue-debate-basic.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**

**领域层：**
- `src/domain/value_objects/debate.py` - 7 个辩论值对象 + 视角枚举（共 8 类型，Task 1）
- `src/domain/entities/debate_session.py` - DebateSession 聚合根 + 状态机（Task 2）
- `src/domain/services/debate_evaluator.py` - 辩论质量评估器三算法（Task 4）
- `src/domain/ports/debate_session_repository.py` - 仓储端口（Task 2）
- `src/domain/exceptions/debate_exceptions.py` - 3 个新异常（Task 0/3）
- `src/domain/events/debate_events.py` - DebateCompleted 事件（Task 0/5）

**应用层：**
- `src/application/services/red_blue_debate_service.py` - 辩论编排服务（Task 7）
- `src/application/services/debate_prompts.py` - 视角/裁判 prompt 映射（Task 6）
- `src/application/services/debate_schemas.py` - LLM 结构化输出 Schema（Task 6）
- `src/application/ports/red_blue_debate_service.py` - 服务端口（Task 7）

**基础设施层：**
- `src/infrastructure/storage/inmemory/debate_session_repository.py` - InMemory 仓储（Task 2）

**测试文件：**
- `tests/unit/domain/value_objects/test_debate.py`（Task 1）
- `tests/unit/domain/entities/test_debate_session.py`（Task 2）
- `tests/unit/domain/services/test_debate_evaluator.py`（Task 4）
- `tests/unit/domain/events/test_debate_events.py`（Task 5）
- `tests/unit/domain/exceptions/test_debate_exceptions.py`（Task 3）
- `tests/unit/application/services/test_red_blue_debate_service.py`（Task 7）
- `tests/unit/application/services/test_debate_prompts.py`（Task 6）
- `tests/unit/application/services/test_debate_schemas.py`（Task 6）
- `tests/unit/infrastructure/storage/test_debate_session_repository.py`（Task 2）
- `tests/unit/architecture/test_red_blue_debate.py`（Task 9，**epics 硬路径无 `_arch_` 前缀**）
- `tests/integration/test_red_blue_debate_integration.py`（Task 9，epics 硬路径）
- `tests/contracts/test_port_contract_red_blue_debate_service.py`（Task 8）
- `tests/contracts/test_port_contract_debate_session_repository.py`（Task 8）
- `tests/contracts/test_event_contract_debate_events.py`（Task 5）
- `tests/contracts/test_event_channel_mapping_debate.py`（Task 5）
- `tests/acceptance/test_acceptance_red_blue_debate.feature`（Task 0 + 10）
- `tests/acceptance/test_acceptance_red_blue_debate.py`（Task 0 + 10）

**配置更新：**
- `src/composition_root.py` 注册 3 个端口（debate_session_repository / debate_evaluator / red_blue_debate_service）
- `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py` 注册 DebateCompleted 双通道
- `src/domain/exceptions/_code_ranges.py`（CODE_RANGES + `_CLASS_TO_SUBDOMAIN` 3 行）
- `src/domain/exceptions/__init__.py` 扩展 `__all__`
- `src/interfaces/api/exception_handlers.py` 增加 3 条 `EXCEPTION_HTTP_MAP`
- `docs/architecture/sisys-uni-exception-design.md` §3.3.2 编码分配表 +debate 子域
- 各层 `__init__.py` 导出（value_objects/entities/events/ports/services）

**依赖更新：** 无（零新增第三方依赖）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.5 |
| **Story Key** | 4-5-red-blue-debate-basic |
| **File** | `_bmad-output/implementation-artifacts/stories/4-5-red-blue-debate-basic.md` |
| **Status** | `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略决策智能（Executive Decision Intelligence）— 可解释性与决策溯源（or.md 三.5） |
| **优先级** | P0-5（Epic 4 战略工具箱多视角分析核心能力，MVP P0） |
| **覆盖 FR** | FR-ST-05（红蓝辩论机制基础，P0） |
| **前置 Story** | 4-1a-strategic-tool-impl（✅ done）/ 3-2a-llm-client-infrastructure（✅ done） |
| **后续 Story** | 10-6-red-blue-debate-full-implementation（V1 多轮+裁决）/ 5-8-agent-output-quality-evaluation（语义准确率量化承接） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0 + Task 1-10，共 11 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-10，共 10 项 AC）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 4 层 + R1/R2/R3 复用决策 + LLM 调用安全约束）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4-1a/4-4/4-1f 一致模式 + GAP-CRITICAL-09 清偿）
5. [ ] Sprint status synced to `ready-for-dev`（create-story workflow 收尾自动更新）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 编号规则：`R<审查轮>-F<序号>`（R1 = Round 1 文档审查，2026-10-01；四视角代码调研 + 双评审员（正确性一致性 / 可行性可满足性）+ 主会话实测定谳）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-F01 | `divergence_rate` 命名与值语义自反（名为分化率、值是重叠率，高值=低分化）——已扩散至 RiskView/DebateQuality/事件/异常 context 四处，V1 消费方必误用 | P1 | 全局改名 `overlap_rate` / `evaluate_overlap` / `OVERLAP_HARD/WARNING_THRESHOLD`（`DebateLowDivergenceError` 类名保留——重叠高→分化低→异常，语义链正确）；改名前后数量守恒核验（9+1+5 处，零残留） |
| R1-F02 | 「`test_code_ranges.py` 含文档同步校验维度」三处失实——该测试 Rule 4 实际只校验 `_CLASS_TO_SUBDOMAIN` 覆盖 `__all__` 类，不读取 sisys-uni-exception-design.md，文档同步纯人工无 CI 强制 | P1 | 三处更正表述（硬约束 Checklist 第 5 项 / 登记确认动作 / AC-3 验证标准）；附主会话定谳：debate 3 异常直接继承抽象基类被 Rule 2 `abstract_names` 跳过，无需扩白名单 |
| R1-F03 | `compute_gain_rate("ABCD", "ABC") ≈ 0.25` 与公式矛盾——差集 {CD}=1，1/max(2,1)=0.5，照写即错误期望 | P1 | 改为 `== 0.5` 精确断言并附推导 |
| R1-F04 | 「复用既有 test_arch_* 的 AST 扫描助手」不可行——架构测试目录无共享助手模块，30 个文件均为私有 `_extract_imports` 复制形态 | P1 | Task 9 循环 B 重构阶段与 Subtask 9.6 改为「私有 `_extract_imports` 复制先例（附 file:line）」 |
| R1-F05 | per-call timeout 上界论证未计入 tenacity 重试放大（默认 3 次×12s+退避≈39s/调用 > 30s；构造级参数不可按调用调节；BDD 30s 硬超时会先截断）——「≤30s 预算论证」数学不成立 | P1 | 改为延迟预算三段式诚实声明：① 无重试上界 ≈25s<30s ✓ ② 含重试最坏 ≈39s 为已声明接受风险（熔断兜底）③ P95 分布统计随 5.7；4 处出现位同步改写 |
| R1-F06 | Fake LLM 按 system_prompt 子串分派存在合成误路由——裁判 prompt 必然同时含"激进派""保守派"标记，判定顺序使合成调用误路由到视角 Schema，Happy path 对正确实现误红 | P1 | 分派方案重构为 response_schema 身份分派（+temperature 区分红蓝），角色标记降为断言物；4 处出现位同步（测试隔离约束 / AC-10 Fake 工厂 / 两条测试要求清单 / Task 6 prompts 测试） |
| R1-F07 | `get_debate_result`「终态重建」对 FAILED 语义不可满足（FAILED 是终态但无 risk_view）且重建公式留白（quality/duration_ms 未写推导） | P1 | 明确仅 COMPLETED 可重建 + 三字段重建公式（title/DebateQuality 推导/completed_at−started_at 毫秒换算，注明测试断言重建语义非全等）；FAILED 及非 COMPLETED 返回 None；Task 7B 测试清单同步 |
| R1-F08 | `evaluate_overlap` 同一行内签名 `-> float` 与「返回 DebateQuality(...)」自相矛盾，Task 4 测试无从落笔 | P1 | 定谳返回 float（与门控用法/断言一致），DebateQuality 组装归服务层，纯函数单一职责 |
| R1-F09 | BDD AC-7.3「红蓝并发」Then 断言无观测物（(prompt, temperature) 序列串行实现产出相同，场景空转或无法落笔） | P1 | 观测物落地：Fake 记录每次调用 start/end 时间戳，断言红蓝窗口重叠（`blue.start < red.end` 且 `red.start < blue.end`，串行必红）；单测辅以单边计时阈值 `elapsed < 1.5×sleep`；AC-7.3 场景名与断言物同步 |
| R1-F10 | 事件发布失败只测契约外形态（AsyncMock raise）——EventPublisher 契约是返回 PublishResult（is_success 标志，不抛异常），契约内真实可达形态无处理规定无测试，真实全失败被静默吞 | P1 | 双形态处理规定（is_success==False → warning；raise → try/except warning；均不覆写结果）+ AC-7 验证标准与 Task 7B 测试清单双形态用例 |
| R1-F11 | epics:1288-1290 架构测试三项（红蓝辩论/视角生成/风险视图）无 traceability 映射，验收核对时漏项 | P1 | AC-9 架构验证测试节补三项→具体测试文件/场景映射清单 |
| R1-F12 | 「第 2 行 Story 注释」归属 R6 模板错误——R6 模板第 2 行直接 `功能:`，Story 注释次行形态属 4.1b/4.4 先例 | P2 | 头部组织改双先例组合表述（4.1b/4.4 贡献 Story 注释行；R6 贡献三段式/背景块/横幅；@scenario 绑定仍 R6 .py 先例不变） |
| R1-F13 | 4.1a 被引为「模块级 event_loop fixture」样板失实（4.1a 用 scenarios()+_run_async 每次新建 loop）+「52/52 acceptance 文件」过期 | P2 | 先例改指 domain_dictionary/layered_retrieval；4.1a:424-430 标注为 _run_async 变体（同样合法）；52/52→59 |
| R1-F14 | 仓储 `save -> None` 偏离全部 5 个 InMemory 先例（均返回实体）却自称同款；`state_version`「乐观锁」在全链路无执行点（save 幂等覆盖无 CAS） | P2 | `save -> DebateSession` 对齐先例 + AC-5 补「先 validate 再幂等覆盖（无版本冲突检测，V1 CAS 预留）」；「乐观锁」降格「迁移计数（V1 乐观锁 CAS 预留）」4 处同步 |
| R1-F15 | 依赖矩阵遗漏 `debate_prompts`（服务必 import PERSPECTIVE_PROMPT_MAP/SYNTHESIS_*，按原矩阵实施即 lint-imports/运行时 ImportError） | P2 | 矩阵行补 `application/services/debate_prompts` |
| R1-F16 | 测试分类表遗漏 Task 6 两文件（test_debate_schemas.py / test_debate_prompts.py，Task/Subtask/结构树/文件清单四处在唯分类表缺席，Subtask 10.2 按表收尾会漏核） | P2 | 分类表补两行（Task 6 归属） |
| R1-F17 | 温度断言 sorted/集合写法检不出红蓝温度互换（0.8↔0.5 互换仍过） | P2 | 升级为按分派身份强制记录断言（PerspectiveAnalysisSchema 调用中 0.8/0.5 各至少一次，互换必红），sorted 仅补充；2 处同步 |
| R1-F18 | 视角独立性断言未限定调用范围——合成 user prompt 按设计必然同含红蓝论点 JSON，断言若覆盖合成调用必误红 | P2 | 断言范围限定两次 PerspectiveAnalysisSchema 调用，合成调用显式豁免 |
| R1-F19 | gather 异常语义未规定（默认首异常传播不取消兄弟任务→孤儿任务+never retrieved 警告）；失败路径转 FAILED 后是否 save 未写明；缺蓝视角对称断言；schema→VO 抛 242 的归宿未规定 | P2 | 编排步骤补：异常分支显式取消兄弟任务；「每次状态迁移后均 save」纪律；蓝视角对称用例 + 终态落库断言；242 透传归宿（属数据契约违反不包装 421） |
| R1-F20 | Task 0 验收 .py 的 collection error 持续到 Task 7 才消失，Task 1~6 期间全量 pytest 带噪——中间态窗口未声明（Lessons Learned 只声明了登记先行窗口） | P2 | Task 0 DoD 补声明（collection error 为预期中间态，任务级验证以目标文件为准） |
| R1-F21 | 「集成测试覆盖率 ≥75%」无执行口径（cov 目标域/运行方式不明，epics 硬指标无法按字面执行） | P2 | 补执行口径命令（四辩论核心模块 --cov + --cov-fail-under=75） |
| R1-F22 | `PerspectivePrompt` 值类型未定义形态（先例 PerspectivePrompts 为 TypedDict；「同构」名不副实） | P2 | 补 TypedDict 定义（system_prompt + user_prompt_template，键类型升级为枚举） |
| R1-F23 | epics 行号引用错位：性能指标实在 :1293-1295，:1306-1308 仅硬路径两文件 | P2 | AC-9 Given 引用修正（1293-1295 性能 + 1307-1308 路径） |
| R1-F24 | 「既有 157 端口契约」数字混淆（157 是 register_port 数；tests/contracts/ 实为 76 文件） | P3 | 改「76 个测试文件、覆盖 157 个注册端口」 |
| R1-F25 | 类型计数三处不一（「8 类型且 frozen」vs「8 个 VO+枚举」=9；枚举非 frozen dataclass） | P3 | 统一「7 个 frozen dataclass VO + 1 个枚举 = 8 类型」3 处同步 |
| R1-F26 | 三条 grep 自查路径清单漏 `src/application/ports/red_blue_debate_service.py`（R3 新建文件之一） | P3 | 清单补入（10→11 路径） |
| R1-F27 | 评审员报「裸 pydantic ValidationError 可能逃逸」——主会话实测推翻：ValidationError 继承 ValueError，被 LitelLLMClient 外层 except 捕获→重试耗尽统一抛 LLMResponseError（:722/:730-735），不逃逸 | P3 | 改判不落码（服务 except 面不扩 ValidationError，避免死代码分支）；包装链事实登记入异常契约节，供 dev 免推演 |
| R1-F28 | 编排开销 <1s 断言判别力边界未注明（纯内存微秒~毫秒级，1s 阈值余量千倍，仅 smoke）；并发计时「≈max」双边近似断言 CI 抖动脆弱 | P3 | 判别力边界注明（检出编排内意外混入真实 IO）；计时断言改单边阈值 `elapsed < 1.5×sleep` |

**Round 1 统计：** 调研 Agent ×4 + 审查 Agent ×2 + 主会话实测定谳 ×8；发现 P0×0 + P1×11 + P2×12 + P3×5（R1-F27 为评审员建议被实测改判），修复簇 28 项；改名传播 15 处数量守恒核验、6 组残留 grep 零命中。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 待 dev-story 实施后填写
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] 待 dev-story 实施后填充

#### 已修复 Patch

- [ ] 待 dev-story 实施后填充

#### 已推迟 Defer

- [ ] 待 dev-story 实施后填充

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-10-01
**最后更新/Last Updated:** 2026-10-01
**更新说明/Description:**
- v1.0.0: 创建故事文件（四视角代码调研 + epics/PRD/OR/架构文档提取 + 4-1a/4-4/4-1f 经验整合；debate 子域 420-429 新开；GAP-CRITICAL-09 清偿定位）
- v1.1.0: Round 1 五维审查修订（科学性/合理性/正确性/一致性/可行性）——28 修复簇：P1×11（divergence→overlap 全局改名 / 文档同步 CI 校验失实×3 / gain_rate 示例值数学错误 / AST 助手复用不可行 / 延迟预算三段式重写 / Fake 分派误路由重构 / get_debate_result FAILED 语义 / evaluate_overlap 返回类型矛盾 / 并发观测物落地 / PublishResult 双形态 / epics 三项映射）+ P2×12 + P3×5；R1-F27 评审员建议经实测定谳改判不落码
