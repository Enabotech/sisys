# Story 5.3: 单 Agent 标准工作流

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** Agent 工程师,
**I want** 系统执行单 Agent 任务（感知→规划→执行→验证→反思→证据打包）,
**So that** Agent 自主完成任务并输出可验证结果。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组的第三环：5-1 交付 Agent 实例化、5-2 交付身份档案加载，本 Story 交付**任务执行闭环**——CEO Agent 按标准六阶段工作流自主完成任务，产出 JSON 思维链（可审计推理过程）与证据包（可验证结果）。这是 Epic 5 的核心交付物：下游 5.7 Phoenix 追踪、5.11 SAP 实现、Epic 6.1 BLM 战略规划流程全部以本 Story 的执行循环为底座。附带交付 FR-IF-03 SAP 消息 Schema（P0/MVP，5.11 是 P1/V1，Schema 必须提前）。

**范围权威**：epics_v1.0.md L1549-1589（AC + 测试要求）；or.md §四.4（L290-303 九步设计，六阶段为必选步）；architecture.md §17.4（L2895-2906）。

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.2 | `LoadAgentProfileUseCase`（注册名 `agent_profile_use_case`）+ `AgentProfileLoadResult`（六档案 + tools_l1 + 计量）+ `SkillSelectorPort` + agent 异常段 440-443（444-449 预留「5.3 工作流异常」——`_code_ranges.py` L119 注释显式预留） | 本 Story 的上下文装配材料源与异常段继承 | ✅ done |
| Story 1.18b | `AgentEnginePort`（`src/domain/ports/agent_engine.py` L13-42）+ `LangGraphEngine`（`src/infrastructure/agent_orch/langgraph_engine.py`）+ `OrchestrationService`（agent_reasoning 路由已通）+ `FlowStatus` 状态模型 | 六阶段图的承载引擎底座 | ✅ done |
| Story 3.2a | `LLMClientPort`（`src/domain/ports/llm_client.py` L130-199：`generate`/`structured_generate`）+ `LitellmLLMClient`（注册名 `llm_client` SINGLETON，组合根 L2004-2013） | 六阶段每阶段的 LLM 调用 | ✅ done |
| Story 4.1a~4.4 | `tool_execution_service` 端口（装饰链完整：ValidationFeedback→SandboxSecurity→OutputValidator→Engine，组合根 L2394-2426）+ `EvidencePackage` VO（`src/domain/value_objects/tool_execution.py` L127-166） | 「执行」阶段工具调用通道（禁直调 engine/sandbox）+ 工具级证据先例 | ✅ done |
| Story 4-5 | prompt 构造与 Schema 分层先例（`debate_prompts.py`/`debate_schemas.py` + `to_domain()` 桥接）+ Fake LLM 分派锚纪律（system_prompt 前缀稳定） | 上下文装配与思维链 Schema 的结构模板 | ✅ done |
| Story 1.2 | `IsolationLevel` 枚举（`src/domain/events/enums.py` L39-45：L1_FUSED/L2_COLLAB/L3_SOFT/L4_HARD） | SAPMessage.isolation_level 字段类型（复用，不新建） | ✅ done |

**5-2 移交的六条下游风险**（5-2 Story「已知下游风险」L796-804，本 Story 必须处置）：

| # | 风险 | 本 Story 处置 |
|---|------|--------------|
| 1 | 启动上下文 LLM 注入契约未定（拼装方式/口径/标签） | **Task 3 交付装配契约**（DC-3 定稿） |
| 2 | LangGraph 引擎 agent_id 双轨道（langgraph_engine.py L71-72 自铸） | **Task 5 收敛**：parameters 传入实体 agent_id（DC-5） |
| 3 | skill_loader SCOPED 被 SINGLETON 捕获（captive dependency） | 知悉并沿用（归 5-1 D7/5.4 评估，本 Story 不扩捕获面——见 DC-9） |
| 4 | MEMORY.md 系统级合并缺失 | MVP 静态种子直载（5-2 交付形态已足够） |
| 5 | event_id 幂等去重对重复调用无效 | 知悉（事件消费语义归 5.7/5.9） |
| 6 | 档案单角色覆盖（仅 CEO） | 沿用（本 Story 仍仅 CEO） |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| `LLMClientPort.structured_generate(prompt, response_schema, config, system_prompt)` | `src/domain/ports/llm_client.py` L162-191 | **直接复用**——思维链/规划等阶段的结构化输出（Pydantic Schema 驱动，含三策略解析容错）；schema 类放 application 层（端口参数 `type[Any]` 正为 domain 禁 pydantic 留口） |
| `LLMConfig` 派生纪律（`dataclasses.replace(base, temperature=…, timeout=…)` 完整派生） | `src/application/services/red_blue_debate_service.py` L490-516（`_build_call_config`） | **参考照抄**——阶段温度分档必须基于 base 完整派生（裸 `LLMConfig()` 丢 endpoint/api_key 连接字段）；per-call timeout 显式小值（辩论 12s 先例 L83） |
| prompt 模块独立文件模式（常量 + TypedDict map + 构造函数） | `src/application/services/debate_prompts.py`、`summary_prompts.py`、`validation_feedback_prompts.py` | **参考照抄**——新建 `agent_workflow_prompts.py` 同款形态；system_prompt 前缀稳定 = Fake LLM 分派契约（validation_feedback_prompts.py L21 注释先例） |
| Pydantic Schema + `to_domain()` 桥接（应用层） | `src/application/services/debate_schemas.py` L7（「定义在应用层，允许依赖 Pydantic」） | **参考照抄**——思维链阶段 Schema 同款（`NonEmptyStr = Annotated[str, StringConstraints(...)]` 条目级校验，禁 deprecated 的 `Field(strip_whitespace=True)`） |
| `AgentProfileLoadResult` / `AgentProfile` VO / `ToolMetadata` 16 字段 | `src/application/use_cases/agent_profile_loading.py` L42-59、`src/domain/value_objects/agent_profile.py`、`src/application/ports/skill_loader.py` L28-72 | **直接复用**——装配材料（六档案 str + `tools_l1` 含 `description`/`when_to_use`/`when_not_to_use`） |
| `SkillLoaderPort.load_sop(tool_name) → SkillDocument`（L2 SOP ≤500 行，LRU-100） | `src/application/ports/skill_loader.py` L134-147、`src/application/skills/loader.py` L191-244 | **直接复用**——执行阶段按需加载 SOP（Step 6 渐进式加载） |
| `tool_execution_service` 端口（execute(tool_id, tool_call, context)→ToolResult） | `src/application/services/tool_execution_service.py` L64（注册组合根 L2394-2426） | **直接复用**——执行阶段工具调用**唯一通道**（直调 engine/sandbox 会绕过 4-3 校验/4-7 反馈闭环/4-4 沙箱安全装饰） |
| `EvidencePackage` VO（9 字段 + data_sources）与 `_build_evidence` 组装先例 | `src/domain/value_objects/tool_execution.py` L127-166、`src/application/services/tool_execution_engine.py` L511-533 | **参考照抄**——任务级 `TaskEvidencePackage` 的结构模板（字段语义见 Task 0 数据模型） |
| `AgentEnginePort` + `LangGraphEngine` 骨架（submit_graph/get_graph_status/`_SUPPORTED_GRAPHS`/`_publish_agent_decided`） | `src/domain/ports/agent_engine.py`、`src/infrastructure/agent_orch/langgraph_engine.py` L48-163 | **扩展**——新图注册 + 构造注入工作流服务（agent_id 收敛位 L71-72） |
| `AgentDecided` 事件（agent_id/decision_result/confidence）+ reliable 单通道双登记 | `src/domain/events/agent_events.py` L15-36、`configs/event_channels.yaml` L177-180、`channel_router.py` L231-235 | **直接复用**——工作流完成事件（**不新建事件**，confidence 由硬编码 0.9 真实化为验证阶段置信度——DC-6） |
| agent 异常子域段（440-443 已用，444-449 预留本 Story） | `src/domain/exceptions/agent_exceptions.py`、`_code_ranges.py` L112-119 | **追加**——本 Story 在同文件新增 444/445 |
| `IsolationLevel` 枚举（str, Enum——pydantic v2 原生兼容） | `src/domain/events/enums.py` L39-45 | **直接复用**——SAPMessage.isolation_level 字段类型（interfaces→domain 方向合法） |
| CLI 子命令骨架（argparse + 守卫先于 bootstrap + 退出码 + `_close_connection_pools`） | `src/entrypoints/agent_cli.py`（R1-F7 后双池对称清理形态） | **扩展**——追加 `run-task` 子命令 |
| Fake LLM 测试模式（`AsyncMock(spec=LLMClientPort)` + `response_schema is X` 身份分派 + 六元组记录） | `tests/unit/application/services/test_red_blue_debate_service.py` `_make_fake_llm` L112-157 | **参考照抄**——六阶段单测的 LLM 替身 |
| 验收测试骨架（FEATURE 常量 + @scenario 显式绑定 + context dict + `_run_async` + Redis 门控动态 skip + 精确清理） | `tests/acceptance/test_acceptance_agent_profile_loading.py`（5-2 最新形态 785 行） | **参考照抄**——R6 主体基准；AST 静态扫描写法参照 `test_acceptance_postgresql_relational_layer.py`（**禁复制其 then-pass 占位与场景悬空**——PG 模板 17/30 绑定 + 大量 pass 是历史缺陷，5-2 已有「每 then 真实断言」纪律 L909） |
| 测试基建：`get_test_env()`/`SISYS_USE_TEST_PORTS=1`/xdist_group | `tests/environments.py`、`tests/isolation.py` | **直接复用** |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`src/` 下 `perceive|reflect|evidence_packag|ChainOfThought|SAPMessage|SingleAgentWorkflow|run-task` 零命中；LangGraph 现图仅 `analyze→synthesize→END` 占位节点——`src/infrastructure/agent_orch/graphs/basic_agent_graph.py` L16-34，零 LLM 零工具零六阶段）：

1. 六阶段 LangGraph 图（`SingleAgentWorkflow`）+ 新 State Schema（现 `BasicAgentState` 仅 4 键——`schemas.py` L11-26）
2. `AgentWorkflowService`（六阶段逻辑服务）+ 其端口
3. `RunAgentWorkflowUseCase`（执行用例）+ CLI `run-task` 子命令
4. 上下文装配器 + prompt 模块（`agent_workflow_prompts.py`）+ 思维链阶段 Schema
5. `ChainOfThought` 思维链 VO + `TaskEvidencePackage` 任务级证据 VO（domain）
6. 工作流异常（EXCEPTION_444/445）
7. `src/interfaces/sap/`（types.py + message.py——**架构文档 §13.5 目录树钦定位，实际目录不存在需新建**；epics L1942「接口层骨架已存在」表述失实，勘误处置见 D-4）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 六阶段标准工作流执行

**Given** Agent 已实例化并加载身份档案（5-2 链路产出 `AgentProfileLoadResult`）
**When** 执行任务（`run-task --agent-id <uuid> --task "<描述>"`）
**Then** 按标准工作流执行：感知（任务上下文摘要）→ 规划（任务分解与工具匹配）→ 执行（工具调用，Think→Code→Execute→Observe→Validate 原子循环）→ 验证（结构化检查）→ 反思（失败时错误分析与修正重试）→ 证据打包（全量元数据封装）
**And** 验证未通过时进入反思，反思产出修正计划后重试规划（上限 2 次重试；耗尽后带失败标记完成证据打包）
**And** 实体 agent_id 贯通全链（LangGraphEngine 不再自铸——AgentDecided 事件的 aggregate_id 与 AgentProfileLoaded 可关联，5-2 风险 #2 核销）

**验证标准/Validation Criteria:**
- [ ] 六阶段顺序执行且每阶段有产出（阶段名序列断言）
- [ ] 验证失败→反思→重试的条件边路径可达且有断言
- [ ] 重试上限耗尽路径（带 `status=failed` 的完成态）可达
- [ ] agent_id 从 CLI 传入 → parameters → 事件全程一致（无 uuid4 新铸）

### AC-2: JSON 思维链输出

**Given** 工作流执行完成
**When** 输出结果
**Then** 产出五段式思维链：Input → `<Reflection>...</Reflection>` → `<Tools_Used>...</Tools_Used>` → `<Constraints_Check>...</Constraints_Check>` → JSON（最终结构化答案）
**And** 结构化形态为 `ChainOfThought` VO（input_summary/reflection/tools_used/constraints_check/final_answer 五字段）；展示形态 `to_display()` 生成 XML 标签文本（存储用结构化、展示用标签——DC-2 双形态）

**验证标准/Validation Criteria:**
- [ ] 五字段完备且非空（完整率断言）
- [ ] `to_display()` 输出含三个 XML 标签段与 JSON 尾段
- [ ] tools_used 与实际工具调用轨迹一致（Fake LLM 下可精确断言）

### AC-3: 证据打包

**Given** 任务执行完成（成功或重试耗尽）
**When** 打包证据
**Then** `TaskEvidencePackage` 包含：输入摘要哈希、任务分解图（规划产物）、工具调用轨迹（含版本）、关键中间产物快照、置信度评分及依据、引用源列表
**And** 证据包成功率 100%（成功/失败终态均产包）

**验证标准/Validation Criteria:**
- [ ] 六类字段齐备（or.md §四.11.[1] L343 结构化证据包标准）
- [ ] 失败终态同样产包（含失败原因与已执行轨迹）

### AC-4: SAP 消息 Schema 定义（FR-IF-03）

**Given** MVP 阶段 CEO 单 Agent（无 Agent 间通信消费方）
**When** 定义 SAP 消息契约
**Then** `src/interfaces/sap/message.py` 的 `SAPMessage` Pydantic 模型包含全部 15 字段（epics 验收点名的 10 必需字段：message_id/conversation_id/sender_id/receiver_id/message_type/priority/content/correlation_id/isolation_level/blackboard_visible + 设计文档补充的 timestamp/subject/context/requires_response/timeout_seconds）
**And** `types.py` 定义 `MessageType`（request/response/notification/broadcast/debate 五值）与 `MessagePriority`（low/normal/high/urgent 四值）枚举；`isolation_level` 复用 domain `IsolationLevel` 枚举

**验证标准/Validation Criteria:**
- [ ] 15 字段存在性与类型断言（10 必需字段逐一点名）
- [ ] 枚举值集合断言（5 类型/4 优先级）
- [ ] 默认值断言（priority=NORMAL/isolation_level=L4_HARD/blackboard_visible=False/timeout_seconds=300）
- [ ] conversation_id 必填（无默认）+ correlation_id 可空（`UUID | None = None`——修正设计文档 `UUID = None` 缺陷）+ 非法枚举值构造被拒（ValidationError）
- [ ] **不含**：bus/传输/序列化性能/黑板交互（全部归 5.11）

### AC-5: 性能指标

**Given** 端口级 Fake LLM 替身（含每调用延迟模拟——外部 SaaS 不可真实调用是既有豁免面）
**When** 测量工作流全链（六阶段 + 思维链 + 证据打包）
**Then** 工作流执行延迟 P95<10s；思维链输出完整率≥98%；证据打包成功率 100%；并发 Agent 会话≥10（NFR-PERF-04 MVP 档 / epics PERF-02）

**验证标准/Validation Criteria:**
- [ ] P95 计时含六阶段全链（warmup 剔除 + ≥20 采样 + `statistics.quantiles(n=20)[18]`——5-2 先例）
- [ ] 完整率 = 五字段完备的思维链条数 / 总条数（≥98% 断言，Fake LLM 确定性产出下为 100%）
- [ ] 并发 10 会话 `asyncio.gather` 全部成功（单进程并发先例）
- [ ] 真实 LLM 冒烟场景（`LLM_*` env 可用时执行 1 次全链，不可用动态 skip——口径差声明见 DC-7）

### AC-6: 端口接线、架构合规与 CLI 全链

**Given** 六阶段图、服务、用例、Schema 全部交付
**When** 验证接线
**Then** 新端口（`agent_workflow_service` / `agent_workflow_use_case`）经组合根 `register_port` 注册且 resolve 可达；`SingleAgentWorkflow` 图名在 `_SUPPORTED_GRAPHS` 注册；CLI `run-task` 子命令全链贯通（instantiate→load→run 可连续执行）；SAPMessage 落位 `src/interfaces/sap/`（interfaces 层 Pydantic 合规，不污染 domain）

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve + isinstance 合规断言（5-2 AC-6.1 同款）
- [ ] `AgentDecided` 复用决策落地：decision_result 含思维链摘要与证据引用、confidence 真实化（非硬编码 0.9）
- [ ] CLI 全链：`run-task` 成功输出摘要（退出码 0）+ 守卫路径（443/441/444 退出码 1）
- [ ] 架构验证器：domain 零外部依赖（新增 VO/异常 AST 扫描）+ 图工厂依赖方向（infrastructure→application 端口合法）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **不新增领域事件**——工作流完成复用既有 `AgentDecided`（`src/domain/events/agent_events.py` L15-36，reliable 单通道已双登记）。语义依据：「Agent 做出决策时触发」== 工作流产出最终决策；`decision_result: dict` 携带 `{workflow_status, task_summary, chain_summary, evidence_ref, retry_count}`，`confidence` 由验证阶段真实置信度填充（引擎 L153 硬编码 0.9 移除——DC-6）。新语义字段经 `decision_result` dict 扩展，零 Schema 变更
- [ ] `src/domain/events/__init__.py` 无需改动（AgentDecided 已导出）

#### 数据模型 (Data Models)

- [ ] `ChainOfThought` VO（`src/domain/value_objects/chain_of_thought.py`，frozen dataclass）：`input_summary: str` / `reflection: str` / `tools_used: tuple[str, ...]`（工具调用轨迹，含版本后缀如 `"pestel:v1.2.0"`）/ `constraints_check: str` / `final_answer: str`——五字段 `__post_init__` strip 非空校验（AgentProfile VO 先例）；`to_display() -> str` 生成五段展示形态（`Input → <Reflection>…</Reflection> → <Tools_Used>…</Tools_Used> → <Constraints_Check>…</Constraints_Check> → JSON 尾段`，JSON 尾段为 final_answer 原样——or.md §五.5 L480 格式）
- [ ] `TaskEvidencePackage` VO（`src/domain/value_objects/task_evidence.py`，frozen dataclass）：`input_hash: str`（任务输入摘要哈希，sha256 hex）/ `task_breakdown: tuple[str, ...]`（规划阶段任务分解）/ `tool_trace: tuple[str, ...]`（工具调用轨迹——复用工具级 `EvidencePackage.citations` 语义聚合）/ `artifacts_snapshot: dict[str, str]`（关键中间产物快照）/ `confidence: float` + `confidence_rationale: str`（置信度评分及依据）/ `citations: tuple[str, ...]`（引用源切片 ID 列表）/ `status: str`（"completed"/"failed"）/ `failure_reason: str = ""`（失败终态时非空）——or.md §四.11.[1] L343 字段级标准
- [ ] SAPMessage（**interfaces 层 Pydantic，非 domain VO**）见下方「API/接口契约」

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `AgentWorkflowServicePort`（`src/application/ports/agent_workflow.py`，`@runtime_checkable Protocol`）：六阶段每阶段一方法（`perceive(state) → PerceptionResult` / `plan(state) → PlanResult` / `execute_step(state, step) → ToolResult` / `verify(state) → VerificationResult`（含 passed/confidence）/ `reflect(state) → ReflectionResult`（含 revised_plan）/ `package_evidence(state) → TaskEvidencePackage`）+ `build_context(agent_id, task) → WorkflowContext`（装配入口）。阶段结果用 application 层 dataclass（非 pydantic——服务间流转不需要 LLM Schema；PerceptionResult/PlanResult/VerificationResult/ReflectionResult/WorkflowContext 五个 dataclass 定义在端口文件 `agent_workflow.py` 内——多字段组合载体放端口文件先例）
- [ ] `RunAgentWorkflowUseCase` 用例端口：`execute(agent_id: UUID, task: str) -> AgentWorkflowResult`（结果 DTO：chain/ evidence/ workflow_status/ retry_count——对齐 `AgentProfileLoadResult` 形态）
- [ ] 端口注册中心/解析器/契约门禁纪律照旧（`src/domain/ports/registry.py` 体系）；组合根注册名：`agent_workflow_service`（SINGLETON）/ `agent_workflow_use_case`（SINGLETON）
- [ ] 端口契约测试两份（`tests/contracts/test_port_contract_agent_workflow_service.py` / `test_port_contract_agent_workflow_use_case.py`，11 维度 + DummyResolver——5-2 三份同款）
- [ ] **禁止**在服务文件本地定义 Protocol；**禁止**新建语义重复端口（工具执行/LLM/SOP 加载全部复用既有端口）

#### 端口契约清单执行约束（强制）

- [ ] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`agent_workflow_service` + `agent_workflow_use_case` 两新端口；其余全部复用）
- [ ] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线（`sisys-uni-exception-design.md §3.12`）。本 Story 使用 agent 子域预留段 444-449（`_code_ranges.py` L119 注释「预留 5.3 工作流异常」）。

- [ ] `AgentWorkflowError`（EXCEPTION_444，SystemException）——工作流阶段执行失败（LLM 阶段调用失败包装/图执行异常收敛）。context：`{agent_id, phase, reason}`（phase = perceive/plan/execute/verify/reflect/package 之一——同码多因区分锚点）；HTTP 500
- [ ] `ChainOfThoughtValidationError`（EXCEPTION_445，SystemException）——思维链完整性校验失败（五字段缺一/空值/结构非法；LLM 输出缺陷属系统性问题非调用方输入错误）。context：`{agent_id, missing_fields}`；HTTP 500
- [ ] 强制 4 项 checklist：定义文件（agent_exceptions.py 追加）/ `_code_ranges.py` `_CLASS_TO_SUBDOMAIN` 两映射 / `__init__.py` 暴露 / 子域码段校验测试；`EXCEPTION_HTTP_MAP` 444→500、445→500；`sisys-uni-exception-design.md §3.3.2` 编码分配表同步
- [ ] LLM 族异常（331 等）传播策略：阶段内包装为 444（携带 phase），`LLMConfigError`/`CancelledError` 透传（4-5 辩论纪律先例）
- [ ] BDD 异常路径：444（阶段失败）/445（思维链残缺）/443/441 复用场景纳入 Edge Cases

#### API 契约 (API Contract)

- [ ] 本 Story 无 REST API（CLI 入口；`POST /api/v1/agents/{agent_id}/execute` 规划位归 7-2——architecture.md L2433，不做）
- [ ] SAP 接口契约：`src/interfaces/sap/types.py`（`MessageType: str, Enum` 五值 / `MessagePriority: str, Enum` 四值）+ `message.py`（`SAPMessage(BaseModel)` 15 字段——字段表见 AC-4；`correlation_id: UUID | None = None` 修正设计缺陷；`isolation_level: IsolationLevel = IsolationLevel.L4_HARD` 复用 domain 枚举；`receiver_id: str` 广播时约定值 `"broadcast"`（docstring 注明）；`timestamp: datetime` 用 `datetime.now(UTC)`——禁裸 utcnow（architecture v8.4.0 红线））。设计源：interface-design.md §7.4 L1302-1335 + sisys-core-domain-design.md §17.3.7 L1558-1585（两份一致）
- [ ] SAPMessage **不进** `event_channels.yaml`/`ChannelRouter`（接口层通信协议非领域事件——职责矩阵 interface-design §2.2）；Pydantic ValidationError 属接口层框架契约（shared_models.py 先例），**不占**异常体系新条目

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [ ] 思维链阶段 Schema（Pydantic）放 `src/application/services/agent_workflow_schemas.py`（debate_schemas.py 先例）；domain 只收 VO（`to_domain()` 桥接）
- [ ] LangGraph 图/节点在 `src/infrastructure/agent_orch/`（graph 与 nodes 子目录），图工厂依赖 `AgentWorkflowServicePort`（infrastructure→application **端口** 合法；禁直接 import 服务实现类）
- [ ] SAPMessage 在 `src/interfaces/sap/`（interfaces→domain 枚举合法；interfaces 层 Pydantic 合规）
- [ ] `agent_workflow_prompts.py` 纯常量与纯函数（application/services/），零 IO

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_agent_workflow.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_agent_workflow.py`
- [ ] 场景组织：AC 注释横幅分组（PG 模板形态）+ 全场景逐一 @scenario 显式绑定（5-2 形态，**禁 scenarios() 批量绑定与 then-pass 占位**）
- [ ] 覆盖：AC-1×4（六阶段顺序/反思重试/重试耗尽/agent_id 贯通）+ AC-2×2（五段完备/展示形态）+ AC-3×2（字段完备/失败终态产包）+ AC-4×3（字段/枚举默认值/非法拒绝）+ AC-5×3（P95/完整率/并发）+ AC-6×3（接线/事件/CLI 全链）= **17 场景**（Task 9 追加收尾场景后全量 18——收尾场景按模板钦定归 Task 9）
- [ ] BDD 步骤约束：`event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`）；Fake LLM 经 context dict 注入（LLM 是外部 SaaS——端口级 Fake 是既有豁免面，验收其余组件全真实：真实图执行/真实 Redis 仓储/真实档案加载）

**Task 0 完成标志：**

- [ ] 规范项全部定义；Gherkin 已编写且运行确认失败（红阶段验证）
- [ ] **链路接线断言清单**（Epic 4 行动项 7.1-1）：`agent_workflow_service`/`agent_workflow_use_case` 组合根 resolve 可达 / `SingleAgentWorkflow` 图名注册可达 / AgentDecided 发布点（引擎 L86 → 新图执行后发布，decision_result 结构化）真实触发验证 / CLI run-task 全链
- [ ] deferred-work 交叉登记：本 Story 核销 5-2 移交项（agent_id 双轨/装配契约）；续期项（session_storage——触发移 5.4 多轮会话，DC-9）注明

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（7.1-2 强制）。禁止行为四条同模板基线（先码后测/测试后置/跳红/跳变异）。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | ChainOfThought/TaskEvidencePackage VO | 五字段校验/to_display/证据字段/失败终态 | `tests/unit/domain/value_objects/test_chain_of_thought.py`、`test_task_evidence.py` | Task 1 |
| TDD 领域异常测试 | 444/445 | 构造/context/HTTP 映射/码唯一 | `tests/unit/domain/exceptions/test_agent_exceptions.py`（追加）+ `test_exception_handlers.py`（追加） | Task 1 |
| TDD 单元测试 | SAPMessage Schema | 15 字段/枚举/默认值/必填/非法拒绝 | `tests/unit/interfaces/sap/test_message.py` | Task 2 |
| TDD 单元测试 | prompt 模块 + 装配器 + 思维链 Schema | 分节顺序/L1 行格式/to_domain/CJK 计量 | `tests/unit/application/services/test_agent_workflow_prompts.py`、`test_agent_workflow_context.py`、`test_agent_workflow_schemas.py` | Task 3 |
| TDD 单元测试 | AgentWorkflowService 六阶段 | 每阶段 prompt 构造/LLM 调用/解析/证据组装（Fake LLM 身份分派） | `tests/unit/application/services/test_agent_workflow_service.py` | Task 4 |
| TDD 单元测试 | LangGraph 图与引擎扩展 | 六节点顺序/条件边（fail→reflect→重试→耗尽）/agent_id 贯通 | `tests/unit/infrastructure/agent_orch/test_single_agent_workflow_graph.py`、`test_langgraph_engine.py`（追加） | Task 5 |
| TDD 单元测试 | 用例 + CLI | 守卫序/装配调用/事件发布/run-task 退出码 | `tests/unit/application/use_cases/test_run_agent_workflow.py`、`tests/unit/interfaces/cli/test_agent_cli.py`（追加） | Task 6 |
| TDD 契约测试 | 两新端口 | 11 维度 + DummyResolver | `tests/contracts/test_port_contract_agent_workflow_{service,use_case}.py` | Task 4/6 |
| TDD 验收测试 | Gherkin + BDD | 18 场景（Task 0 编写，各 Task 转绿） | `test_acceptance_agent_workflow.feature/.py` | Task 0-7 |
| SDD 架构验证 | 六边形约束 | VO 零外部依赖/图工厂依赖方向/SAP 落位/组合根外零实例化 | `tests/unit/architecture/test_arch_agent_workflow.py` | Task 8 |
| 集成测试 | 全链（真实图+Redis+档案+Fake LLM） | 六阶段贯通/性能 P95/并发 10 | `tests/integration/test_integration_agent_workflow.py` | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；**应用层 ≥85%**（本 Story 主战场）；domain ≥90%；infrastructure ≥75%；interfaces ≥85%（SAP 面）
- [ ] 集成测试覆盖率 ≥75%（epics L1580 TDD 要求口径——沿 5-2 L431 先例对齐，非模板通用 70%）；关键路径（六阶段条件边三分支）100% 分支覆盖

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（pre-commit mypy 覆盖 tests/——测试代码同样类型干净）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/`HTTPException`/继承内置 Exception）+ 零抑制注释

#### 测试隔离约束

> 基线同模板（事务隔离/UUID 唯一/并行隔离/清理粒度/asyncio 纪律全表）。本 Story 特别注意：

- [ ] Fake LLM 分派锚 = `response_schema is X` 身份（**禁与断言锚同源**——4-5 循环论证教训：分派键与断言锚必须独立信号）；`system_prompt` 前缀作辅助分派键时前缀稳定性入注释
- [ ] 计时场景 xdist_group 串行 + benchmark 场景级标记（5-2 R1-F8 形态——不打文件级）
- [ ] Redis 场景级独立客户端 + teardown 逐键精确删除（**禁全库 scan_iter 复核**——5-2 R1-F1 教训：与并行组共享键空间耦合假红）
- [ ] 验收/集成测试零真实 LLM 调用（Fake LLM 端口替身豁免面；真实 LLM 仅冒烟场景 env 门控动态 skip）

**验证要求：** `pytest tests/ -n 8` 通过；连续 5 次无随机失败；ruff/mypy 通过。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 六阶段顺序执行 | Task 4/5 | 六阶段服务方法 + 图节点 | test_agent_workflow_service/test_single_agent_workflow_graph |
| AC-1 | 反思重试与耗尽路径 | Task 5 | 条件边（verify→reflect→plan 循环） | test_single_agent_workflow_graph |
| AC-1 | agent_id 贯通 | Task 5/6 | 引擎收敛 + 用例透传 | test_langgraph_engine（追加） |
| AC-2 | 思维链五段完备 | Task 1/4 | VO + 解析组装 | test_chain_of_thought/test_agent_workflow_service |
| AC-2 | to_display 展示形态 | Task 1 | VO 方法 | test_chain_of_thought |
| AC-3 | 证据包六类字段 | Task 1/4 | VO + 打包组装 | test_task_evidence/test_agent_workflow_service |
| AC-3 | 失败终态产包 | Task 4/5 | 打包阶段失败分支 | test_agent_workflow_service |
| AC-4 | SAPMessage 15 字段/枚举/默认值/非法拒绝 | Task 2 | Schema 定义 | test_message |
| AC-5 | P95/完整率/并发 | Task 7 | 集成性能 | test_integration_agent_workflow |
| AC-6 | 端口接线/图注册 | Task 6 | 组合根 + SUPPORTED_GRAPHS | 契约测试 + 验收 AC-6.1 |
| AC-6 | AgentDecided 真实化 | Task 5/6 | confidence 移除硬编码 | test_langgraph_engine（追加） |
| AC-6 | CLI run-task 全链 | Task 6 | 子命令 | test_agent_cli（追加） |
| AC-6 | 架构合规 | Task 8 | 验证器 A-E | test_arch_agent_workflow |
| 全 AC | 收尾清单 | Task 9 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ TDD 循环内化原则同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [ ] Subtask 0.1: 定义数据模型规范——ChainOfThought VO（五字段 + to_display）+ TaskEvidencePackage VO（九字段）字段表定稿（本文件「数据模型」节为唯一真源）
- [ ] Subtask 0.2: 定义端口契约——AgentWorkflowServicePort 六阶段方法签名 + RunAgentWorkflowUseCase.execute 签名（「统一端口定义注册与管理」节代码块落盘）
- [ ] Subtask 0.3: 定义异常契约——444/445（code/parent/context 触发场景表）
- [ ] Subtask 0.4: 定义 SAPMessage 契约——15 字段表 + 枚举 + 修正项（correlation_id 联合类型）
- [ ] Subtask 0.5: 定义装配契约——system_prompt 分节顺序/温度分档/超时/CJK 计量（DC-3 定稿入 Dev Notes）
- [ ] Subtask 0.6: 编写 Gherkin `test_acceptance_agent_workflow.feature`（17 场景——收尾场景按模板归 Task 9 追加）+ BDD 步骤实现骨架 `test_acceptance_agent_workflow.py`
- [ ] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError/断言红为合法红）
- [ ] Subtask 0.8: deferred-work 交叉登记（核销项与续期项）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义；验收测试红阶段确认；链路接线断言清单定义

---

### Task 1: 领域层——思维链/证据 VO + 工作流异常 444/445

**关联 AC:** AC-2、AC-3

#### TDD 循环 A：ChainOfThought VO

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_chain_of_thought.py`（五字段构造/strip 非空校验/类型守卫先于判空——5-1 R2-F2 教训/tools_used 元组形态/to_display 五段文本含三个 XML 标签 + JSON 尾） |
| 🟢 绿 | 实现 `src/domain/value_objects/chain_of_thought.py`（frozen + `__post_init__` 校验——AgentProfile VO 模板） |
| 🟡 变异 | 移除某字段校验 → 红 → 还原绿 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：TaskEvidencePackage VO

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_task_evidence.py`（九字段/失败终态 failure_reason 非空守卫：status=="failed" 时 failure_reason.strip() 非空/confidence 0.0-1.0 范围/input_hash 64 位 hex 形态） |
| 🟢 绿 | 实现 `src/domain/value_objects/task_evidence.py` |
| 🟡 变异 | 失败守卫突变 → 红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 C：异常 444/445

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_agent_exceptions.py` 追加（code/继承 SystemException/context 三键或 missing_fields/444 phase 参数）+ `test_exception_handlers.py` 追加 444→500/445→500 + `test_code_ranges.py` 子域校验自然覆盖 |
| 🟢 绿 | `agent_exceptions.py` 追加两类 + `_code_ranges.py` 两映射 + `__init__.py` + `EXCEPTION_HTTP_MAP` + 设计文档 §3.3.2 两行 |
| 🟡 变异 | 码值突变 → 唯一性测试红 → 还原 |
| 🔄 重构 | 全套异常测试（`tests/unit/domain/exceptions/`）绿 |

- [ ] Subtask 1.1-1.3: 三循环各红绿变异重构
- [ ] Subtask 1.4: 领域事件无变更确认（AgentDecided 复用——零 diff）

**完成标准/Definition of Done:** VO + 异常全绿；domain 覆盖率 ≥90% 维持

---

### Task 2: SAP 消息 Schema（interfaces/sap/）

**关联 AC:** AC-4

#### TDD 循环 A：types + message

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/sap/test_message.py`（15 字段存在性逐一点名/MessageType 五值集合/MessagePriority 四值集合/默认值四断言（NORMAL/L4_HARD/False/300）/conversation_id 必填（缺省构造 ValidationError）/correlation_id 可空默认 None/非法 message_type 构造 ValidationError/timestamp tz-aware（UTC）） |
| 🟢 绿 | 新建 `src/interfaces/sap/__init__.py` + `types.py` + `message.py`（isolation_level 用 `from src.domain.events.enums import IsolationLevel`） |
| 🟡 变异 | 删 message_type 枚举一值 → 集合断言红 → 还原 |
| 🔄 重构 | ruff + mypy（pydantic v2 类型干净） |

- [ ] Subtask 2.1: 🔴 红 — Schema 测试
- [ ] Subtask 2.2: 🟢 绿 — 两文件实现（含「广播 receiver_id="broadcast"」与「5.11 实现传输」docstring 边界声明）
- [ ] Subtask 2.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:** SAPMessage 全字段测试绿；interfaces 层 Pydantic 合规

---

### Task 3: 上下文装配契约 + prompt 模块 + 思维链 Schema

**关联 AC:** AC-1、AC-2（5-2 风险 #1 核销）

#### TDD 循环 A：prompt 模块

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_agent_workflow_prompts.py`（system_prompt 分节顺序断言：IDENTITY→SOUL→CODE→核心约束→TOOLS L1 视图；L1 行格式 `"{tool_name}: {description}（用: {when_to_use}）"`；核心约束文本含思维链五段输出要求；task user prompt 模板占位符） |
| 🟢 绿 | 实现 `src/application/services/agent_workflow_prompts.py`（模块常量 + 构造函数——debate_prompts 四连先例；**system_prompt 前缀稳定性注释 = Fake 分派契约**） |
| 🟡 变异 | 分节顺序突变 → 红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：思维链 Schema + 装配器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `agent_workflow_schemas.py` 测试（ChainOfThoughtSchema 五字段 NonEmptyStr 条目级/to_domain() → VO list→tuple）+ `test_agent_workflow_context.py`（build_system_prompt(profile, tools_l1) 分节/cjk_estimate_tokens 中文感知计量（context_compressor L376-405 同款——中文 1.5 字/token 其他 4 字/token）/装配总计量断言） |
| 🟢 绿 | 实现 Schema 模块 + `AgentContextBuilder`（application/services/agent_workflow_context.py——纯函数或轻类，注入零 IO） |
| 🟡 变异 | 计量函数中文系数突变 → 红 → 还原 |
| 🔄 重构 | ruff + mypy |

- [ ] Subtask 3.1-3.2: 两循环红绿变异重构
- [ ] Subtask 3.3: 装配契约决策落盘核验（DC-3 的口径重定义——**新计量含全部六档案 + L1 视图 + 核心约束文本**，弃用 5-2 `startup_context_tokens` 的三件套口径；5-2 字段保留不动，本 Story 产出 `assembled_context_tokens` 新字段语义）

**完成标准/Definition of Done:** 装配器测试绿；Fake LLM 分派锚就绪（prompt 前缀）

---

### Task 4: AgentWorkflowService 六阶段逻辑

**关联 AC:** AC-1、AC-2、AC-3

#### TDD 循环 A：六阶段方法（每阶段一小循环，Fake LLM 身份分派）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_agent_workflow_service.py`（perceive：任务摘要 prompt + PerceptionSchema 解析/plan：任务分解 + 工具匹配（L1 description 驱动——规划阶段 LLM 从 tools_l1 自主选择，`selected_tools` 字段）/execute_step：经 `tool_execution_service.execute(tool_id, tool_call, context)` 调用（**断言经端口而非直调**）+ ToolResult 轨迹追加/verify：VerificationSchema（passed/confidence/rationale）/reflect：ReflectionSchema（error_analysis/revised_plan）/package_evidence：九字段组装（input_hash sha256/工具轨迹聚合/artifacts 快照/失败终态分支）。Fake LLM：`AsyncMock(spec=LLMClientPort)` + `structured_generate.side_effect` 按 `response_schema is X` 分派——**分派键（Schema 身份）与断言锚（产出内容）独立**） |
| 🟢 绿 | 实现 `src/application/services/agent_workflow_service.py`（构造注入 llm_client/tool_execution_service/skill_loader（L2 SOP 按需）——R2 组合端口；温度分档 TEMPERATURE_PROFILE + `_build_call_config` 完整派生（辩论纪律）；per-call timeout 显式 ≤8s（全链 10s 预算约束——DC-7）；LLM 异常包装 444 携带 phase） |
| 🟡 变异 | 阶段温度突变 → Fake 记录断言红；工具调用绕过端口直调 → mock 断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/contracts/test_port_contract_agent_workflow_service.py`（11 维度 + DummyResolver——5-2 三份同款） |
| 🟢 绿 | 组合根注册 `agent_workflow_service`（v1.0.0 SINGLETON tags=("agent","workflow")） |
| 🟡 变异 | impl 路径突变 → resolve 失败红 → 还原 |
| 🔄 重构 | 契约 12 项绿 |

- [ ] Subtask 4.1-4.2: 两循环
- [ ] Subtask 4.3: 思维链组装（ChainOfThoughtSchema 解析 → VO；445 校验失败路径测试）

**完成标准/Definition of Done:** 六阶段单测绿；契约绿；application 覆盖率 ≥85%

---

### Task 5: LangGraph SingleAgentWorkflow 图 + 引擎扩展（agent_id 收敛）

**关联 AC:** AC-1、AC-6（5-2 风险 #2 核销）

#### TDD 循环 A：图与条件边

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/agent_orch/test_single_agent_workflow_graph.py`（六节点顺序（正常路径：perceive→plan→execute→verify→[pass]→package）/验证失败→reflect→plan 重试路径/重试上限 2 耗尽→package（status=failed）/State Schema 字段（agent_id/task/context/phase 产物/retry_count/evidence/chain）；图工厂 `build_single_agent_workflow_graph(service: AgentWorkflowServicePort)` 编译产物 nodes/edges 断言） |
| 🟢 绿 | 实现 `src/infrastructure/agent_orch/graphs/single_agent_workflow_graph.py`（`StateGraph(WorkflowAgentState)` 六节点 + 条件边：verify 后按 `verification_passed` 分流；reflect 后按 `retry_count < MAX_RETRIES and revised` 分流——节点函数薄封装调服务阶段方法（闭包持 service））+ `schemas.py` 追加 `WorkflowAgentState(TypedDict, total=False)` |
| 🟡 变异 | 条件边谓词反转 → 路径断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：引擎扩展 + agent_id 收敛

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_langgraph_engine.py` 追加（`_SUPPORTED_GRAPHS` 含 "SingleAgentWorkflow"/parameters["agent_id"] 透传——**AgentDecided.agent_id == parameters 传入值**（自铸收敛断言——uuid4 新铸必红）/decision_result 含 {workflow_status, retry_count, evidence_ref 摘要}/confidence 来自 state（非 0.9 硬编码——突变断言：state.confidence=0.72 → 事件 confidence=0.72）/构造注入 workflow_service 端口） |
| 🟢 绿 | 改造 `langgraph_engine.py`（构造签名扩展 `workflow_service: AgentWorkflowServicePort | None = None`——默认 None 保持 BasicAgent 向后兼容；`_build_graph` 按图名分派到新图工厂；L71-72 agent_id 收敛：`parameters.get("agent_id")` 存在时复用，否则回退自铸（BasicAgent 兼容）；`_publish_agent_decided` 从 state 取 confidence） |
| 🟡 变异 | 移除 parameters agent_id 读取 → 贯通断言红 → 还原 |
| 🔄 重构 | 全部引擎测试绿（存量 BasicAgent 测试零回归） |

- [ ] Subtask 5.1-5.2: 两循环
- [ ] Subtask 5.3: 存量回归（BasicAgent 图测试全绿确认——扩展不破坏 1.18b 契约）

**完成标准/Definition of Done:** 六阶段图三路径绿；agent_id 贯通断言绿；存量零回归

---

### Task 6: RunAgentWorkflowUseCase + 组合根 + CLI run-task

**关联 AC:** AC-1、AC-6

#### TDD 循环 A：用例

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_run_agent_workflow.py`（守卫序：443（get_by_id None）→441（非 CEO）→ 装配（agent_profile_use_case.execute 调用断言）→ submit_graph("SingleAgentWorkflow", parameters 含 agent_id/task/context) → get_graph_status 轮询至终态 → 结果组装（AgentWorkflowResult 四字段）→ AgentDecided 发布由引擎承担（用例不重复发布——**断言用例零 publish 调用**，防双发）；守卫序 calls 断言（5-2 先例）；失败传播 444） |
| 🟢 绿 | 实现 `src/application/use_cases/run_agent_workflow.py`（构造注入 agent_repository/agent_profile_use_case/agent_engine/——R2 组合；编排模板对齐 5-2 六步形态） |
| 🟡 变异 | 守卫顺序交换 → calls 断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：组合根 + 契约 + CLI

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_port_contract_agent_workflow_use_case.py`（11 维度）+ `test_agent_cli.py` 追加（run-task 参数必填（--agent-id/-a + --task/-t）/成功输出摘要（六阶段状态行 + 思维链五段预览 + 证据引用 + 置信度）/443/441/444 退出码 1 + stderr 编码断言/UUID 守卫 201） |
| 🟢 绿 | 组合根注册 `agent_workflow_use_case`（四依赖工厂）+ LangGraphEngine 注册改造（注入 resolve("agent_workflow_service")）+ CLI `run-task` 子命令（骨架模板：守卫先于 bootstrap/退出码/_close_connection_pools） |
| 🟡 变异 | 注册名突变 → resolve 红 → 还原 |
| 🔄 重构 | 契约 + CLI 测试绿 |

- [ ] Subtask 6.1-6.2: 两循环
- [ ] Subtask 6.3: 集成冒烟——`resolve("agent_workflow_use_case")` 可达 + isinstance（链路接线断言清单 L1）

**完成标准/Definition of Done:** 用例/契约/CLI 绿；组合根接线可达

---

### Task 7: 集成测试 + 性能验收

**关联 AC:** AC-5

#### TDD 循环 A：全链集成 + 性能

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_agent_workflow.py`（场景①全链：真实 Redis 仓储（instantiate→run-task 同 agent_id）+ 真实档案加载 + 真实图执行 + Fake LLM（延迟模拟 200ms/调用）→ 六阶段贯通 + 思维链 + 证据 + AgentDecided 事件捕获（recording publisher——真实类子类先例）；场景②P95：warmup 1 + 20 采样 `quantiles(n=20)[18] < 10s`（Fake 延迟下设 6 档延迟确保有意义的计时下界）；场景③并发 10：`asyncio.gather` 10 agent_id 同时执行全成功；场景④真实 LLM 冒烟：`LLM_*` env 探测（`LLMConfig.from_env()` 有 model 时执行 1 次真实全链，否则 pytest.skip——动态跳过禁写死） |
| 🟢 绿 | 全场景转绿（验证型——被测链路已由 Task 1-6 交付） |
| 🟡 变异 | 阈值突变（10s→0.01s）→ P95 红 → 还原；Fake 延迟突变 → 计时下界红 → 还原 |
| 🔄 重构 | xdist_group + benchmark 场景级标记 + pytestmark（integration/redis） |

- [ ] Subtask 7.1: 🔴 红 — 四场景编写
- [ ] Subtask 7.2: 🟢 绿 — 转绿 + 计时校准
- [ ] Subtask 7.3: 🟡 变异 + 🔄 重构（隔离纪律：Redis 键逐键删除 + LLM env 探测封装 fixture）

**完成标准/Definition of Done:** 集成 4 场景绿（真实 LLM 缺席时 3 绿 1 skip）；性能三指标断言活

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** AC-6

#### 架构验证测试实现（验证器 A-E）

- [ ] Subtask 8.1: 创建 `tests/unit/architecture/test_arch_agent_workflow.py`
- [ ] Subtask 8.2: 验证器 A——domain 零外部依赖（chain_of_thought.py/task_evidence.py/agent_exceptions.py AST 扫描禁 pydantic/langgraph）
- [ ] Subtask 8.3: 验证器 B——图工厂依赖方向（infrastructure 图文件 import 白名单：application.ports.agent_workflow 合法 / application.services 实现类非法）
- [ ] Subtask 8.4: 验证器 C——SAP 落位（`src/interfaces/sap/` 存在 + message.py pydantic 可用 + domain 无 SAP 引用反向）
- [ ] Subtask 8.5: 验证器 D——组合根外零实例化（LangGraphEngine/AgentWorkflowService 全仓 AST 扫描禁业务代码直接实例化）
- [ ] Subtask 8.6: 验证器 E——prompt 模块零 IO（agent_workflow_prompts/context 纯函数断言）
- [ ] Subtask 8.7: 循环依赖检测用 ruff/isort（不引入 pylint）+ 全套报告

**完成标准/Definition of Done:** 验证器 A-E 全绿；违规即红

---

### Task 9: 开发结束验收测试

**关联 AC:** 全部

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 验收 feature 追加收尾场景（src 完成清单/tests 四目录完成清单逐项确认——AC-6.3 形态） |
| 🟢 绿 | BDD 步骤实现（文件存在性 + 关键符号 grep 断言——5-2 AC-6.3 同款） |
| 🔄 重构 | 场景命名收敛 |

- [ ] Subtask 9.1: 收尾场景红绿
- [ ] Subtask 9.2: 全量回归（`pytest tests/ -n 8` + 连续 5 次稳定）+ ruff/mypy 收尾校验
- [ ] Subtask 9.3: 文档同步（architecture.md §17.4 实现状态注记 + interface-design.md §5.6 装配契约落地注记 + §7 SAP Schema 已定义注记）

**完成标准/Definition of Done:** 全量 18 场景（17 + 收尾 1）全绿；Story 可进入 review

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §17.4（L2895-2906 九步循环/EIP/SAP）、§3.2 ADR-002（双核引擎）、§11.2.4（配置集加载→任务执行接线位）；[`sisys-workflow-agent-integration-design.md`](../../../docs/architecture/sisys-workflow-agent-integration-design.md)（AgentEnginePort/FlowStatus/引擎适配设计）

- **架构模式：** 六边形（Ports & Adapters）+ 双核引擎（Prefect 数据流 / LangGraph 认知推理——`OrchestrationService.coordinate()` 按 task_type 路由）
- **设计约束：** domain 零外部依赖（AST 门禁）；infrastructure 图工厂只依赖 application **端口**；SAP 属接口层横向协议（非领域事件）
- **接口治理：** 新端口两枚（`agent_workflow_service`/`agent_workflow_use_case`）走 PortSpec 全套（registry/resolver/contract gate/契约测试）；其余全部复用既有端口
- **技术栈：** Python 3.11+ / LangGraph StateGraph（`langgraph.graph.StateGraph` + 条件边 `add_conditional_edges`）/ litellm（structured_generate JSON Schema mode）/ pydantic v2（interfaces+application 层）

### 关键架构决策

| # | 决策点 | 选定方案 | 备选方案（弃用理由） | 依据 |
|---|--------|---------|---------------------|------|
| DC-1 | 六阶段承载形态 | **LangGraph `SingleAgentWorkflow` 图承载编排**（六节点 + 条件边：verify→[pass→package / fail→reflect]；reflect→[revised 且 retry<2→plan / 耗尽→package(failed)]）+ **节点薄封装调用 `AgentWorkflowService` 阶段方法**（图工厂构造注入端口；阶段逻辑/prompt/LLM 全在应用层服务） | a) 应用层纯 Python 顺序编排（弃用：验证失败→反思→重试的条件循环与未来 checkpoint 中断恢复正是 StateGraph 价值——手写循环重复造轮且 or.md §四.4.[1] L291 明确「StateGraph 机制」）；b) 全部逻辑写进图节点（弃用：infrastructure 层膨胀，prompt/LLM 逻辑应在 application；节点难单测） | or.md L291-301；architecture.md §17.4 L2900；LangGraphEngine 现骨架（`_build_graph` 分派位） |
| DC-2 | 思维链双形态 | **结构化存储 + 标签展示**：`ChainOfThought` VO 五字段（结构化真源，供 6-4 持久化/5.7 追踪消费）+ `to_display()` 生成 `Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON` 五段文本（or.md §五.5 的展示契约）；单次 `structured_generate` 返回完整思维链 JSON（一次解析全链——继承 litellm 三策略容错） | a) 五段独立 LLM 调用逐段拼（弃用：5 倍延迟/成本，P95<10s 不可达；段间无强依赖）；b) 让 LLM 输出原始 XML 标签文本再正则解析（弃用：解析脆弱，结构化 Schema 优先——项目零 json_repair 依赖） | or.md L480；epics L1560；4-5 structured_generate 先例 |
| DC-3 | 上下文装配契约（5-2 风险#1 核销） | **system_prompt 五分节定序**：IDENTITY→SOUL→CODE（行为约束）→核心约束文本（思维链五段输出格式 + 安全红线——模块常量化，项目首个「核心约束」载体）→TOOLS L1 视图（`"{tool_name}: {description}（用: {when_to_use}）"` 行格式）；USER/MEMORY 追加 system 尾节；task_description 进 user prompt；**计量口径重定义**：`assembled_context_tokens` = 全部分节 CJK 感知估算（中文 1.5 字/token 其他 4 字——context_compressor L376-405 同款），弃 5-2 三件套口径（字段保留不动作历史） | a) USER/MEMORY 进 user 消息（弃用：MVP 简单优先，分节可控）；b) 逐档案按需加载（弃用：六档案合计 ~3.2KB 无需分级）；c) 沿用 chars//4（弃用：中文低估数倍——5-2 风险#1 明示） | interface-design §5.6 八步（Step1 AGENT.md 见 D-2）；5-2 风险 #1 三重警示 |
| DC-4 | SAPMessage 落位与类型 | **`src/interfaces/sap/`**（architecture.md §13.5 L2125-2131 钦定：message.py/types.py/bus.py[5.11]/middleware.py[V2]）；15 字段全量；`isolation_level: IsolationLevel`（复用 domain `events/enums.py` L39-45——str,Enum 与 pydantic v2 原生兼容，与 IsolationLevelSwitched 事件同源）；修正设计缺陷 `correlation_id: UUID \| None = None` | a) application 层（debate_schemas 先例——弃用：架构文档钦定 interfaces/sap/，SAP 是外部通信协议归接口层 R4）；b) isolation_level 用裸 str（弃用：domain 枚举已存在，重复定义违反 SSOT）；c) 自定义独立枚举（弃用：与 domain IsolationLevel 语义重复） | architecture.md §13.5；interface-design §7.4 L1302-1335；两份设计文档一致 |
| DC-5 | agent_id 双轨收敛（5-2 风险#2 核销） | **parameters 透传实体 agent_id**：用例在 parameters 携带 agent_id/task/context → 引擎优先 `parameters["agent_id"]`（存在即复用，缺失回退自铸保 BasicAgent 兼容）→ AgentDecided(实体 id) 与 AgentProfileLoaded(实体 id) 可按 aggregate_id 关联 | a) 引擎内查仓储反查（弃用：引擎依赖仓储端口越界——编排引擎不该有持久化职责）；b) 桥接映射表（弃用：单 Agent 直传即可，映射是过度设计） | 5-2 风险 #2；langgraph_engine.py L71-72 收敛位 |
| DC-6 | 工作流完成事件 | **复用 `AgentDecided`**（不新建事件）：`decision_result` 携带 `{workflow_status, task_summary, chain_summary, evidence_ref, retry_count}`；`confidence` 真实化（state 里的验证置信度——引擎 L153 硬编码 0.9 移除）；发布点保持引擎内（用例零发布防双发） | a) 新建 AgentWorkflowCompleted 事件（弃用：与 AgentDecided「Agent 做出决策」语义重叠——禁止同义事件；下游 5.7/5.9 以 AgentDecided 为锚的设计不变）；b) 用例发布（弃用：双发风险，引擎发布是 1.18b 既有接线） | epics 零新事件要求；agent_events.py L15-36；模板「禁止同义接口重复定义」 |
| DC-7 | P95<10s 验收口径 | **Fake LLM 延迟模拟为主口径**（每调用注入 200ms 级模拟延迟——计时有真实下界；六阶段 ≈8-10 次 LLM 调用 + 工具执行）+ **真实 LLM 冒烟场景**（env 门控动态 skip，跑通即证链路兼容不设硬阈值——外部 SaaS 延迟不可控） | a) 仅 Fake 零延迟计时（弃用：计时无下界，恒真风险）；b) CI 硬性真实 LLM（弃用：外部依赖+费用+不稳定，项目豁免面惯例） | epics L1571；4-5/3-2b Fake LLM 先例；5-2 性能验收形态 |
| DC-8 | LLM 调用配置 | **TEMPERATURE_PROFILE 分档**（perceive 0.3/plan 0.2/execute 辅助 0.1/verify 0.1/reflect 0.4/package 0.1——规划反思略高发散、验证执行低温确定）+ `_build_call_config` 完整派生 + **per-call timeout ≤8s**（全链 10s 预算内单阶段上限；禁依赖 from_env 默认 600s——辩论 12s 先例的紧缩版） | 统一温度（弃用：阶段语义分化是 4-5 验证过的模式）；裸 LLMConfig()（弃用：丢连接字段——B 视角调研实证契约） | red_blue L75/L490-516/L83 先例 |
| DC-9 | session_storage 与九步可选步处置 | **续期 defer**：`session_storage`（deferred-work L130 原触发=5.3）续期至多轮会话需求 Story（5-4+）——MVP 单次 CLI 调用内会话闭合，无跨调用状态需求；**九步中的可选步不实现**：深度思考（L297 并行多路径——9-8 域）/演化（L301——V1）；初始化（L293）内化为用例前置（档案加载+装配即初始化） | 激活 session_storage（弃用：YAGNI——无消费方）；实现深度思考（弃用：epics AC 未要求，属 9-8 深度推演域） | epics AC 六阶段口径；Simplicity First |
| DC-10 | 工具选择机制 | **规划阶段 LLM 自主选择**（PlanSchema 含 `selected_tools: list[NonEmptyStr]`——从 system_prompt 的 L1 视图自判，interface-design §5.6 Step5「description 即触发器」）；执行阶段按规划顺序逐工具 `tool_execution_service.execute`；**不建** SkillSelector 排序/Top-K（5-2 DC-4 已废弃该口径） | 关键词预筛 + LLM 复核（弃用：双阶段复杂度，L1 全量 23 条注入后 LLM 自判足够——P5 Less scaffolding） | interface-design §5.5/§5.6；GAP-CRITICAL-08b 哲学 |

### 已知下游风险（本 Story 不处置，消费方 Story 决策）

1. **思维链持久化归 6-4**：本 Story 交付 VO（内存态），存储至战略档案库与决策追溯查询是 Epic 6.4（测试含存储/追溯，依赖 6.1）——5-3 不落库。
2. **AgentDecided 无活跃订阅者**：AutoTriggerHandler 已订阅但组合根 handler_names 未激活（L2800-2809）——5.7 Phoenix 追踪立项时决定是否接线。
3. **SAPMessage 零消费方**：5.11 实现传输（bus/序列化/黑板交互）；`conversation_id: UUID` 与 PublicBlackboard 端口 str 键的换算（`str(conv_id)`）5.11 处理。
4. **图工厂服务注入与 SINGLETON 捕获**：LangGraphEngine（SINGLETON）注入 agent_workflow_service（SINGLETON）无捕获问题；但服务内 skill_loader（SCOPED）捕获沿 5-1 D7 留项形态（不扩新捕获面——工具执行走 tool_execution_service 端口，其 SCOPED 归属同评估）。
5. **多角色扩展**：本 Story 仅 CEO（5-2 风险 #6 延续）；V1 扩角色时图/服务零改动（role 从档案链透传）。

### 设计文档偏离声明

> 90-8 先例机制：实施与设计文档冲突时显式声明，实施后同步更新文档。

| # | 冲突点 | 偏离内容 | 实施后同步动作 |
|---|--------|---------|---------------|
| D-1 | prd.md FR-AC-03（L1839）引用 `[or.md 四.4.(1)]` | 六阶段工作流实际在 or.md **四.4.(2)-(7)**（四.4.(1) 是初始化步骤）——宽松引用 | 无需动作（注记性声明，5-2 D-5 同款） |
| D-2 | interface-design §5.6 Step1 要求 AGENT.md（<150 行） | **不纳入本 Story**（AGENT.md 无 FR 认领——FR-AC-02 七档案枚举不含；其「项目上下文+约束」语义由 DC-3 核心约束文本常量承载） | 5-2 D-6 评估结论落地；不修改 interface-design（§5.6 是规划）；Task 9 在 §5.6 补「AGENT.md 未实施，约束由核心约束文本承载」注记 |
| D-3 | or.md §四.4 九步（含初始化/深度思考/演化共 9 步） | 交付六阶段（初始化内化为用例前置；深度思考/演化可选步不实现——DC-9） | Task 9 在 architecture.md §17.4 补「MVP 交付六阶段，可选步待 9-8/V1」注记 |
| D-4 | epics L1942「接口层骨架已存在（src/interfaces/sap/）」 | 实际目录不存在（架构 §13.5 是愿景树）——本 Story 新建 | 勘误性声明；无需改 epics（历史规划文档） |
| D-5 | epics L1585-1586 建议测试路径 `tests/unit/architecture/test_agent_workflow.py` 等 | 按项目实际目录结构（unit 按层分目录/integration 无后缀/arch 测试命名 test_arch_*）——5-2 D-7 同款 | 不修改 epics；dev 以本 Story 测试分类表为准 |
| D-6 | or.md §四.4.(4) 执行阶段「写入持久化沙箱内存变量」 | MVP 工具执行经 tool_execution_service（Docker 沙箱装饰链内）——「持久化沙箱内存变量」的会话级状态归 session_storage 续期 defer（DC-9） | deferred-work 续期登记 |
| D-7 | sisys-core-domain-design §17.3.7 SAPMessage `correlation_id: UUID = None` | pydantic v2 非法默认（不可空类型配 None 默认）——修正为 `UUID \| None = None` | Task 9 在两份设计文档该行补勘误注记 |

### 关键代码模式参考

**图工厂 + 服务注入模式（新建 `single_agent_workflow_graph.py`）：**

```python
from langgraph.graph import StateGraph, END
from src.application.ports.agent_workflow import AgentWorkflowServicePort

def build_single_agent_workflow_graph(service: AgentWorkflowServicePort):
    """六阶段图工厂（节点薄封装——阶段逻辑在应用层服务）。"""
    graph = StateGraph(WorkflowAgentState)
    graph.add_node("perceive", lambda state: service.perceive(state))
    graph.add_node("plan", lambda state: service.plan(state))
    # ... execute/verify/reflect/package_evidence
    graph.set_entry_point("perceive")
    graph.add_edge("perceive", "plan")
    graph.add_edge("plan", "execute")
    graph.add_conditional_edges(
        "verify",
        lambda state: "package" if state["verification_passed"] else "reflect",
        {"package": "package_evidence", "reflect": "reflect"},
    )
    graph.add_conditional_edges(
        "reflect",
        lambda state: "plan" if state["retry_count"] < MAX_RETRIES and state.get("revised") else "package",
        {"plan": "plan", "package": "package_evidence"},
    )
    graph.add_edge("package_evidence", END)
    return graph.compile()
```

**Fake LLM 身份分派模式（六阶段单测核心替身）：**

```python
def _make_fake_llm() -> AsyncMock:
    """Fake LLM：按 response_schema 身份分派（分派键与断言锚独立——4-5 纪律）。"""
    fake = AsyncMock(spec=LLMClientPort)
    async def _structured_generate(prompt, response_schema, config=None, system_prompt=None):
        if response_schema is PerceptionSchema:
            return PerceptionSchema(summary="任务摘要：...")
        if response_schema is PlanSchema:
            return PlanSchema(steps=["..."], selected_tools=["pestel"])
        # ... 每阶段 Schema 一分支
    fake.structured_generate.side_effect = _structured_generate
    return fake
```

**引擎 agent_id 收敛模式（langgraph_engine.py 改造位）：**

```python
# L71-72 现状（自铸——收敛目标）：
#   run_id = str(uuid.uuid4()); agent_id = uuid.uuid4()
# 收敛后：
agent_id_raw = parameters.get("agent_id")
agent_id = UUID(agent_id_raw) if agent_id_raw else uuid.uuid4()  # 缺失回退保 BasicAgent 兼容
```

**验收测试骨架（R6 模板基准 = 5-2 最新形态 + PG 模板三要素）：** FEATURE 常量 + @scenario 全量显式绑定 + context dict fixture + `_run_async(event_loop, coro)` 同循环纪律 + Redis 门控动态 skip + teardown 逐键精确删除（禁全库 scan——5-2 R1-F1）+ AC 注释横幅分组（PG 模板）+ AST 静态扫描（PG 模板 test_acceptance_postgresql_relational_layer.py 写法）；**禁** then-pass 占位与场景悬空（PG 模板历史缺陷）。

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.2](./5-2-agent-identity-profile-loading.md)（文档审查周期 46 项 + 代码审查周期 26 项收敛的完整教训链）

**关键学习/Key Learnings:**
- **场景层级是验收设计的第一分叉**：每场景定稿「层级（用例级/端口级）+ LLM 依赖（Fake/真实）+ Redis 依赖」三属性，BDD 约束节/隔离表同步分档
- **同码多因断言必须带 context 区分锚点**（444 按 phase、445 按 missing_fields）
- **计数断言同源派生**（== len(result.tools_l1) 形态）+ tripwire 注记
- **断言锚点与 Fake 分派键必须独立信号**（4-5 循环论证教训——本 Story DC-10/Task 4 直接应用）
- **`命令 | tail` 掩盖退出码**：全量验证看统计行；预存失败要隔离复跑 + git log 溯源定谳（gpu/docker/redis 三形态甄别先例）
- **每 then 真实断言（禁 pass 占位）+ 全场景显式绑定（禁悬空）**
- **pre-commit mypy 覆盖 tests/**：测试代码类型干净（Protocol 签名逐参对齐）

**应用到本故事/Applied to This Story:**
- [ ] 18 场景三属性分档表（Task 0 定稿）
- [ ] Fake LLM 分派键独立性纪律（Task 4）
- [ ] 性能断言变异实证 + 计时下界（Task 7——Fake 延迟注入）
- [ ] teardown 逐键删除 + 禁全库 scan（Task 7）

### deferred-work 处置（5-3 触发项分流）

| 项 | 处置 |
|----|------|
| `session_storage` + RedisSessionStorage（deferred-work L130，原触发=5.3） | **续期**（触发移至 5-4+/多轮会话——DC-9：MVP 单次调用内闭合） |
| agent_id 双轨（5-2 风险 #2） | **本 Story 核销**（Task 5） |
| 上下文装配契约（5-2 风险 #1 + R3-DF1 L1 失败语义） | **本 Story 核销**（Task 3 定契约；L1 失败语义在装配契约中一并定义——TOOLS.md 降级时 387 传播策略） |
| CLI bootstrap 10.4s（D13，核销=5.3 批量消费前） | **知悉不处置**（run-task 单次调用语义下非阻断；组合根瘦身属架构级决策，登记保持） |
| R1-DF2 事件观测面（锚=5.3 首个事件消费 Story） | **部分核销**：本 Story 是 AgentDecided 的语义消费方（真实化 confidence）但非首个 AgentProfileLoaded 消费方——登记保持（观测面归 5.7） |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── value_objects/
│   │   ├── chain_of_thought.py          # 新建：思维链 VO（五字段 + to_display）
│   │   └── task_evidence.py             # 新建：任务级证据包 VO（九字段）
│   └── exceptions/agent_exceptions.py   # 追加：444/445（预留段核销）
├── application/
│   ├── ports/
│   │   └── agent_workflow.py            # 新建：AgentWorkflowServicePort（六阶段）
│   ├── services/
│   │   ├── agent_workflow_prompts.py    # 新建：prompt 常量模块
│   │   ├── agent_workflow_schemas.py    # 新建：阶段 Pydantic Schema + to_domain
│   │   ├── agent_workflow_context.py    # 新建：装配器（build_system_prompt + CJK 计量）
│   │   └── agent_workflow_service.py    # 新建：六阶段逻辑服务
│   └── use_cases/
│       └── run_agent_workflow.py        # 新建：执行用例
├── infrastructure/
│   └── agent_orch/
│       ├── langgraph_engine.py          # 改造：图名分派 + agent_id 收敛 + confidence 真实化
│       ├── schemas.py                   # 追加：WorkflowAgentState
│       └── graphs/
│           └── single_agent_workflow_graph.py  # 新建：六节点 + 条件边图工厂
├── interfaces/
│   └── sap/                             # 新建目录（架构 §13.5 钦定位）
│       ├── __init__.py
│       ├── types.py                     # MessageType/MessagePriority 枚举
│       └── message.py                   # SAPMessage（15 字段）
├── entrypoints/
│   └── agent_cli.py                     # 扩展：run-task 子命令
└── composition_root.py                  # 追加：两端口注册 + 引擎注册改造

tests/
├── unit/{domain/value_objects,application/services,application/use_cases,infrastructure/agent_orch,interfaces/sap,interfaces/cli,architecture}/
├── contracts/test_port_contract_agent_workflow_{service,use_case}.py
├── integration/test_integration_agent_workflow.py
└── acceptance/test_acceptance_agent_workflow.{feature,py}
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-19 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1549-1589） |
| **架构文档** | `docs/architecture/architecture.md`（§17.4/§3.2/§11.2.4/§13.5）+ `sisys-workflow-agent-integration-design.md` |
| **接口设计** | `docs/architecture/interface-design.md`（§5.5/§5.6/§7） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.7 + L1112-1180 九步伪码） |
| **前一个 Story** | `5-2-agent-identity-profile-loading.md`（v1.5.1 收敛态） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（含 FR-IF-03 搭车交付界定）
- [x] 架构约束从 architecture.md/interface-design/core-domain-design/or.md 提取
- [x] 前一个故事学习经验整合（5-2 六条下游风险全处置 + 教训链应用）
- [x] 四视角并行代码调研（编排引擎/LLM 装配面/SAP 分层/六阶段设计与验收模板）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-3-single-agent-workflow.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- 见「项目结构说明」节逐项（src 新建 12 + 改造 4；tests 四目录全套——以结构节为准）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.3 |
| **Story Key** | 5-3-single-agent-workflow |
| **File** | `_bmad-output/implementation-artifacts/stories/5-3-single-agent-workflow.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力） |
| **优先级** | P0-3 |
| **覆盖 FR** | FR-AC-03（P0）、FR-IF-03（P0，Schema only） |
| **性能锚** | NFR-PERF-04（MVP≥10 并发）/ epics PERF-02 / L1571-1573 三指标 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-9）
2. [x] All acceptance criteria specified（AC-1~AC-6）
3. [x] Architecture constraints extracted
4. [x] Previous story learnings integrated
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> （实施前由文档审查工作流填写。）

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

> （实施后由 code-review 工作流填写。）

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施（从 Task 0 开始）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-19
**最后更新/Last Updated:** 2026-10-19
**更新说明/Description:**
- v1.0.0: 创建故事文件（四视角并行调研：编排引擎底座/LLM 客户端与装配面/SAP 消息分层/六阶段设计与验收模板；10 项关键架构决策 DC-1~DC-10 + 7 项偏离声明 D-1~D-7；5-2 六条下游风险全处置分流；SAPMessage 15 字段含 2 处设计缺陷修正）
