# Story 6-4: JSON 思维链输出（BLM 面五段规范化组装 + EVIDENCE_PACKAGE 战略档案归档 + 决策追溯查询面）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统在 BLM 前两阶段每个步骤完成时输出 JSON 思维链（Input→`<Reflection>`→`<Tools_Used>`→`<Constraints_Check>`→JSON 五段），经确定性组装复用 5-3 交付的 `ChainOfThought` VO，并以 `ArchiveType.EVIDENCE_PACKAGE` 归档至战略档案库（L2 强制+L3 向量+L4 WORM），配套按 plan_id 的决策追溯查询面,
**So that** Agent 决策过程可追溯和可解释——每个 BLM 步骤的工具使用、反思推理、约束核对与最终结构化结论形成审计级证据链（7 年 WORM 保留），支撑后续 6-7 溯源树展示与高管审计。

### 业务价值

- 覆盖 **FR-SP-04 (P0)**：系统可以输出 JSON 思维链（Input→`<Reflection>`→`<Tools_Used>`→`<Constraints_Check>`→JSON）[or.md 五.5 L480 / prd.md L1871]
- **兑现三方钦定的持久化契约**：① 6-1 边界表（6-1 故事文件 L37）钦定「JSON 思维链输出规范化 → Story 6-4（BLM 面输出规范化）」——6-1 复用 5-3 内建思维链不规范化；② `src/domain/value_objects/chain_of_thought.py:4-5` docstring 明言「供 **6-4 持久化**与 5.7 Phoenix 追踪消费的结构化真源」；③ `ArchiveType.EVIDENCE_PACKAGE`（`src/domain/entities/strategic_archive.py:32,38`，3-10 定义）**全 src 零使用**——本 Story 是其钦定激活方（禁重复造轮 checklist 红线第一条：新增领域概念前全仓 grep 已确认零既有归档通道）
- **补齐 5-3 思维链的最后一公里**：5-3 交付了任务级思维链（SingleAgentWorkflow 六阶段 package_evidence 终局合成→`AgentWorkflowResult.chain`），但其生命周期止于 state→CLI 打印→AgentDecided 200 字截断投影→span 属性（四 Agent 调研实证：`grep -rni "chain.*archive|persist.*chain" src/` 零命中）——「存储至战略档案库」在 5-3 与 BLM 面均不存在，本 Story 落地归档接线
- **Epic 6 内部依赖兑现**：epics L2013 钦定 6.4 依赖 6.1（done）——BLM 流程宿主（SpBlmGraph 8 节点）在位，本 Story 是其可观测面增强；下游 6-7 溯源树展示消费思维链证据链
- **审计合规价值**：思维链落 L4 WORM（retention_days=2555/7 年，`strategic_archive_service.py:193-198` 既有）——「可追溯决策」架构原则（architecture.md L132：所有决策可追溯至原始数据和假设，7 年审计追踪）在 Agent 推理维度的落位

### 与 5-3/6-1/6-2/6-3 的范围边界（出处逐行声明）

| 面（出处） | 已交付（禁重复造轮） | 6-4 增量（本 Story） |
|---|---|---|
| 思维链 VO（5-3） | `ChainOfThought` 五字段 frozen dataclass（input_summary/reflection/tools_used:tuple/constraints_check/final_answer）+ `to_display()` 五段 XML 展示 + `__post_init__` 242 校验（`src/domain/value_objects/chain_of_thought.py:33-103`） | **零改动复用**（组装产物的目标类型——5-3 已为 6-4 预留持久化语义） |
| 思维链 Schema（5-3） | `ChainOfThoughtSchema` + `to_domain()`（`src/application/services/agent_workflow_schemas.py:73-103`）——LLM 终局合成专用 | **零使用**（6-4 确定性组装不经 LLM——OD-2；deferred L192 R1-DF3 的 Schema 演进触发条件不满足，注记零触发） |
| 任务级思维链组装（5-3） | `agent_workflow_service.package_evidence` LLM 终局合成 + 组装覆写 DC-2（`src/application/services/agent_workflow_service.py:334-408`） | **零触碰**（SingleAgentWorkflow 路径不归档——任务级思维链归档归 5.7 Phoenix/后续 Story，OD-1；deferred 登记） |
| 思维链异常（5-3） | `ChainOfThoughtValidationError`（EXCEPTION_445，agent 域，`src/domain/exceptions/agent_exceptions.py:251-270`，context.missing_fields） | **复用**（组装终态门禁——242 捕获改写 445 的 5-3 先例同款；零新增异常，OD-6） |
| BLM 流程宿主（6-1/6-2） | `SpBlmGraph` 8 节点 + `BlmPlanningService` 八依赖 + 三执行方法（performance_gap/insight_step/synthesize）+ per-step/latest 快照 + BlmStageCompleted | **尾参可选注入挂接+回传三件套**（第九依赖可选——本类 base_config+LangGraphEngine 双尾参先例；三方法末尾组装+归档→`_PlanRunState` 累积→`project_chain_records` 投影→sp_blm_graph 节点适配器直写——R1-F1；快照/事件链零改动——OD-8） |
| 战略档案库（3-10/6-3 接线） | `StrategicArchiveService.archive_plan`（L2 强制→L3 降级→L4 WORM 强制→L5 降级→引用回写→ArchiveCreated，`src/application/services/strategic_archive_service.py:71-296`）+ `ArchiveType.EVIDENCE_PACKAGE` 枚举（零使用）+ `ArchiveQuery` 查询面 | **复用零改动 + EVIDENCE_PACKAGE 首激活**（载荷映射冻结——OD-4；追溯读侧走既有 `query_archive`） |
| 归档参数映射先例（6-3 ③步） | checkpoint_service.py:225-239 冻结形态（plan_type="SP"/decision_basis 携 checkpoint_no——R8-F3 语境锚先例） | 载荷映射新冻结（decision_basis 携 kind+stage 锚——R8-F3 同构） |
| Checkpoint 机制（6-3） | 完整形态快照 13 键/五步编排/恢复数据面 | **零触碰**（思维链与 Checkpoint 正交——Checkpoint 归档的是压缩笔记+上下文，思维链归档的是推理过程；两者经 plan_id 各自关联） |
| 快照面（6-2/6-3） | per-step 七键契约 + latest 七键 + 完整形态 13 键 | **零改动**（思维链不进 Redis state_data——持久化归宿是战略档案库，OD-8；6-2「structured_output 键恒在」契约零破坏） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: BLM 每步五段思维链产出（确定性组装）

**Given** BLM 前两阶段流程执行中（SpBlmGraph 8 步任一步：performance_gap / 六子步骤 / synthesis），该步领域产物已就绪（结构化输出或降级信封、工具执行轨迹、检索证据引用）
**When** 该步执行完成（三执行方法末尾挂接点触发——`run_performance_gap_analysis`/`run_insight_step`/`synthesize_insights`）
**Then** 以**确定性组装**（零新增 LLM 调用——OD-2）构造 `ChainOfThought` VO，五字段素材源映射（Task 0.2 冻结，唯一真源见「数据模型」节）：
- `input_summary` ← 步骤语义 + task 截断 + 证据计数（**按步骤型分列素材**——六子步骤：`StepSemanticConfig.display_name`+`role_prefix`（blm_planning_prompts.py:172-221 六配置行）+ `len(evidence_texts)`；performance_gap：`PERFORMANCE_GAP_CONFIG`（:162-169）+ `len(evidence_texts)`；**synthesis：无 StepSemanticConfig（语义配置只有 gap+六子七行——R1-F3 实测），display_name/role_prefix 钦定为组装服务模块级常量（"市场洞察综合"/"CMO"，不新增 prompts.py 配置行不动 6-1 资产）**，证据计数恒 0（synthesize_insights 无检索调用——:391-449））
- `tools_used` ← 该步**实际执行的工具 slug**（`_execute_candidate_tools` 返回三元组的第三位 tool_slug——`tool.slug or tool.name` :600，**首个成功候选即返回 :601 故每步至多 1 项；slug 为 kebab-case 无版本后缀，缺失时回落中文显示名**；包装为 `(tool_slug,) if tool_slug else ()`；无工具步/工具降级步合法空元组——「清单+版本后缀」是 5-3 任务级 tool_trace 语义（agent_workflow_service.py:273 `f"{name}:{version}"`），BLM 面不存在该形态，R1-F2 口径差钦定）
- `reflection` ← 规则模板合成（**按步骤型分列素材**——六子步骤：summary + findings 计数；performance_gap：summary（=financial_gap）+ root_causes 计数；synthesis：conclusions 计数 + degraded_inputs；三者均拼降级信息）
- `constraints_check` ← 规则模板合成（**按步骤型分列素材**——六子步骤：structured_output 值域守卫结果（InsightStepResult :247-267 既有校验）+ 证据充分性；performance_gap：四字段产物完整性（成功支）或降级信封标注（降级支）+ 证据充分性；synthesis：结论产出判定（conclusions 非空）+ degraded_inputs 标注（无检索面故无证据充分性段）；三者均拼降级标记）
- `final_answer` ← 该步结构化产物的 JSON 序列化（六子步骤=structured_output dict 原样 / performance_gap=`dataclasses.asdict(PerformanceGapArtifacts)` **六键 dict**（financial_gap/operational_gap/root_causes/portfolio_health/degraded/degrade_reason——blm_phases.py:195-200，R1-F4 口径）/ synthesis=`dataclasses.asdict(InsightSynthesis)` **两键 dict**（conclusions/degraded_inputs）/ **降级信封 dict {degraded, degrade_reason} 仅适用于结构化产物缺席形态**（R2-F2 钦定——六子=structured_output None（LLM 失败支）；**部分降级形态**（degraded=True 且产物在位——检索/工具降级而 LLM 成功，:348-351 常态路径）**payload=产物原样**（丢弃真实产物恰违背审计初衷），降级事实经 reflection 降级后缀+constraints_check 降级标记+decision_basis.degraded 三处承载；gap/synthesis 两型 asdict 自含 degraded 字段一种形态通吃无此分叉——降级也是决策过程，可追溯性恰恰要求记录降级原因）
**And** 一次完整 run 产出 **8 条思维链**（每步一条——OD-3 粒度钦定：or.md 五.5「SP/BP 各个阶段」的步骤级落位，stage 锚对齐 STAGE_VALUE_DOMAIN 八值），VO 构造经 `__post_init__` 242 校验（既有），组装层捕获 242 改写 **445** `ChainOfThoughtValidationError`（context.missing_fields——5-3 package_evidence :386-393 同款先例）

**验证标准/Validation Criteria:**
- [ ] 8 条思维链**四文本字段非空白**（input_summary/reflection/constraints_check/final_answer）+ **tools_used 形态合法**（空元组合法——synthesis 步恒空；非空时元素级非空白）（R2-F7 口径订正——「五字段非空」与空元组合法矛盾；Fake LLM 确定性产出下 100% 完整率——epic「完整率≥98%」MVP 口径）
- [ ] **组装映射判别力**：tools_used 断言=独立构造的期望轨迹（该步实际执行的工具 slug 单元组或空元组——**非 Fake LLM 回声**，组装面素材来自执行轨迹与既有产物，Fake 回声值泄漏即红——5-3 `test_chain_assembly_overwrite` :680-695 判别力先例）；final_answer 经 `json.loads` round-trip 解回等于该步 structured_output（六子步骤）/ asdict 六键等值（gap——list 归一口径：root_causes 解回为 list，与 asdict tuple 比较前显式 `tuple()` 归一——R1-F9 钦定）/ 两键等值（synthesis，同款 list 归一）
- [ ] 降级步（Fake LLM 注入失败形态——**验收 S3**（fail_schemas **限六子 Schema 子集**（R3-F10——全覆盖 8 Schema 触发全降级 481 :177-182 场景不可达））+单测双层）思维链仍产出：final_answer 为降级信封 JSON 且 degrade_reason 在位、constraints_check 含降级标注；**部分降级形态**（R2-F2）**归单测层 Task 1A 专属**（素材构造 degraded=True+payload 在位——R3-F2 分层裁定：检索降级唯一注入先例在单测 mock 层（test_blm_planning_service.py:252-254 AsyncMock spec=HybridSearchPort），验收层 no-mock 红线下无构造通道（真实 Qdrant 空结果=正常空证据不降级 :641-654））payload=structured_output 原样（非信封）+降级事实三处承载（reflection 后缀/constraints_check 标记/decision_basis.degraded）
- [ ] 组装素材缺陷时（构造性红测——单测层）：445 触发且 missing_fields 携缺失字段名——**构造配方钦定**（R2-F3）：冻结公式四文本字段恒非空白/final_answer 恒非空，**唯一可达 242 通道是 tools_used 元素级守卫**（`StepChainMaterial(tool_slug=" ")` 纯空白串——truthy 进元组后被 VO `not item.strip()` 拒绝，chain_of_thought.py:76-81）；空 payload 不可达（`json.dumps({})`="{}" 非空白）；payload 含不可 JSON 序列化对象抛 TypeError 非 242——生产素材源受控（model_dump/asdict/信封三态）注记不设防
- [ ] `to_display()` 展示形态正确（五段顺序 + 三个 XML 标签闭合对 + JSON 尾段——5-3 既有 VO 方法零改动复用，验收仅断言组装产物经展示面输出）

### AC-2: 输出包含完整思维链（Result 携带 + 事件投影真实化）

**Given** BLM 流程全链完成（8 步均执行）
**When** 组装执行结果（`RunBlmPlanningUseCase._assemble_result`）
**Then** `BlmPlanningResult` 携带 **`chain_records`** 新字段（默认尾字段 `()` 零破坏——6-3 R3-2 先例）：`tuple[ChainRecord, ...]` 每步一条（`ChainRecord` dataclass 定义在端口文件——`stage: str` / `chain: ChainOfThought` / `archive_id: str`（归档成功非空）/ `archived: bool`）
**And** 图 state 新增 `chain_records` 键（`SpBlmState` TypedDict `total=False` 加键零破坏）累积承载——**回传通道三件套**（R1-F1 钦定，`degraded_steps`/`timeline` 完全同构先例）：① `_PlanRunState` 加 `chain_records` 累积列表（服务侧 per-run 键控隔离——`_ensure_run_state` 通道 :732；三方法返回 VO 非 dict，累积**不经**方法返回值；**残留语义注记**（R2-F10）：`_runs` 无清理是既有模式（timeline/degraded_steps 同款 SINGLETON 进程级驻留，482 重跑防线恰依赖其残留 :240-246）——6-4 不新增清理机制，后续如引入 run_state 回收须三键同收）；② `BlmPlanningServicePort` 协议追加 `project_chain_records(plan_id)` **第七方法**（`project_timeline`/`project_degraded_steps` :193/:197 同构第三投影；既有六方法零改动）；③ `sp_blm_graph.py` 三类节点适配器（:44-48/:61-65/:77-81）返回 dict 各加 `"chain_records": service.project_chain_records(state["plan_id"])` 直写全量行（schemas.py:96-99 SpBlmState docstring「服务投影直写全量」钦定——纯 TypedDict 无 reducer 键覆盖（:43-45 为 5-3 AgentWorkflowState 同语义泛化注）、适配器直写全量勿二次合并，八节点对称）——**不进快照 state_data**（OD-8）、**不进事件 payload**（投影白名单钦定）
**And** AgentDecided 事件投影 **chain_summary 真实化**：SpBlmGraph 投影分支（`langgraph_engine.py:270` 现取 `first_conclusion`——synthesis 首结论）改为末条思维链 `final_answer[:200]` 截断（SingleAgentWorkflow :254 同款取值语义；**空回退分支钦定**（R1-F12）：chain_records 为空时（尾参 None 未注入/组装全失败）回退 `(first_conclusion or "")[:200]` 现值——synthesis 结论信息不因观测面缺席而丢失；五键白名单结构零变化——DC-11 投影纪律维持，VO 实例仍禁入 payload）

**验证标准/Validation Criteria:**
- [ ] `result.chain_records` 恰 8 条，stage 锚与 STAGE_VALUE_DOMAIN 八值一一对应（执行序排列；**读侧 tuple 归一**（R2-F5）：state 承载 list（投影返回 list——project_timeline 同构），`_assemble_result` 构造 Result 时显式 `tuple(final_state.get("chain_records") or ())` 归一防 list/注解漂移）
- [ ] 既有 `BlmPlanningResult` 消费面（CLI `_print_blm_progress` :655-680 / 6-1 单元引擎测试图身份锚 `test_blm_planning_service.py:976-984` + 验收/集成 DTO 面断言）**零适配通过**（默认尾字段向后兼容——Task 4.3 实证，6-3「零适配假设验证闭环」同款）
- [ ] AgentDecided 投影断言：chain_summary == 末条思维链 final_answer 前 200 字符（纯标量断言——值级非仅类型级）；**空回退分支断言**：chain_records 空时 == `(first_conclusion or "")[:200]` 现值（R1-F12）
- [ ] 图身份锚不受影响（终态 state 含 BLM 专属键 insight_step_results/synthesis——6-1 既有断言零修改通过）

### AC-3: 思维链归档战略档案库（EVIDENCE_PACKAGE 激活）

**Given** 某步思维链组装完成（五字段校验通过）
**When** 归档步骤执行（挂接点内经 `ChainOfThoughtArchiveService` 调用 `StrategicArchiveService.archive_plan`——零改动复用）
**Then** 落一条 `StrategicArchive`：`archive_type=ArchiveType.EVIDENCE_PACKAGE`（**枚举首激活**——3-10 定义后零使用，本 Story 唯一构造位）、`plan_id` 同 BLM run、`plan_type="SP"`（6-3 R6-1 同款钦定——思维链是 SP 编制过程的推理快照）、归档载荷映射（**Task 0.3 冻结——唯一真源**）：
- `decision_basis = {"kind": "blm_chain_of_thought", "stage": stage_id, "chain": {五字段 dict}, "degraded": bool}`（**kind+stage 语境锚**——R8-F3「decision_basis 是 dict 自由字段，携带语境锚使读侧可精确过滤」同构先例）
- `assumptions = {"tools_used": [...], "evidence_refs": [...]}`（过程素材溯源——evidence_refs 源自 material.evidence_refs（R3-F1 补字段）：六子=result.evidence_refs / gap=检索三元组第三位 / synthesis=()）
- `evidence_blob = json.dumps({"stage": stage_id, "chain": {五字段 dict}}, ensure_ascii=False, sort_keys=True).encode("utf-8")`（**L4 WORM 存结构化 JSON——DC-2「存储用结构化、展示用标签」钦定**；to_display() 是展示面不落 blob）
**And** 存储落位：L2 PostgreSQL `strategic_archives` 行（强制）+ L3 Qdrant `strategic_archive` collection 点（可降级）+ L4 MinIO `archive-evidence` bucket WORM 对象（强制，retention_days=2555）+ L5 图谱（可降级）——`archive_plan` 既有编排零改动（:122-294 五步序）；归档内 `ArchiveCreated` 事件随 outbox 发布（既有——**零新事件**，OD-6）；**L4 落对象双前提注记**（R1-F16）：写入条件 `evidence_blob and self._object_storage is not None`（:191）——组合根 `resolve_optional("l4_object")`（:2217）未注册时 blob 静默跳过（blob_ref=None 无 284 无告警）；测试环境经 6-3 装配形态（真实 MinIO + bucket 自愈）覆盖，生产部署 L4 注册是 WORM 落位前提

**验证标准/Validation Criteria:**
- [ ] 真实链集成：一次 run 后 PG 恰 8 行 EVIDENCE_PACKAGE 档案（按 plan_id + archive_type 过滤——ArchiveQuery 既有查询面）+ Qdrant 点可搜（`search_vectors` 读回 payload.archive_id 匹配）+ MinIO 对象可取（blob_ref 解引用 → JSON 反序列化 → 五字段 round-trip 等值）
- [ ] 归档载荷断言：decision_basis.kind/stage 锚在位；blob 解引用 JSON == 独立构造的期望五字段 dict（判别力——非自证）
- [ ] L3/L5 失败优雅降级不阻断归档（3-10 既有降级语义零改动——Fake Embedding 豁免面下正常路径全绿）；L2/L4 失败触发面见 AC-4
- [ ] WORM 保留：`retention_days=2555` 经 blob 对象 retention 属性验证（6-3 集成① L4 断言先例）

### AC-4: 归档失败降级语义（可观测面非流程面）

**Given** 某步思维链组装成功、归档调用执行
**When** 归档强制环节失败（L2/L4 存储失败或归档内 ArchiveCreated 发布失败——`ArchiveStorageError` 284 透传面）
**Then** **降级不阻断 BLM 流程**：捕获 284 → 该步 `ChainRecord(archived=False, archive_id="")` → warning 日志（含 stage/plan_id/失败原因）→ 流程继续（后续步骤正常执行；该步领域产物/快照/事件不受影响——思维链是可观测面，因观测面失败丢弃已产出的领域结果是错误的权衡，OD-5）；**L2 半行语义注记**（R3-F5）：archive_plan 内 L2 save 先于 L4/回写/发布（:122-127 在前三者之前）——284 于后三者时 L2 行已在 session，session_context 末尾 commit 使 archived=False 台账与 L2 EVIDENCE_PACKAGE 行并存；**钦定半行提交为可接受形态**（L2 行在即证据在，archived 台账反映调用终态，读侧追溯以 L2 为准——行在即读得到，与台账 False 并存不矛盾）
**And** **挂接段 UUID 守卫钦定**（R3-F4）：`context.plan_id` 是 str（:218-225），归档是首个 UUID 硬消费方——挂接段 `uuid.UUID(plan_id)` 转换失败（畸形 plan_id——CLI `--plan-id` 无 UUID 守卫透传）时该步 chain 缺席+warning 日志降级续行（OD-5 同语义；裸 ValueError 逃逸违红线——6-3 checkpoint_service :249-252 宽捕注记同款防御）；6-1 既有链路对非 UUID plan_id 全程 str 兼容，本守卫使其不因 6-4 挂接而中断
**And** **零静默吞错**：失败可见可数——chain_records 中 archived=False 条目即失败台账；CLI blm-plan 汇总行输出归档计数（**三段式口径**（R2-F8）：「思维链归档 成功 N/失败 M/预期 8」——分母 8 使组装缺席 K=8-N-M 可推算，Task 3 断言同步）
**And** 组装失败（445）同降级语义（该步 chain 缺席于 chain_records——`chain_records` 条目数在 445 降级下 <8，计数断言可见；**不抛出中断 run**——同 OD-5 权衡）；**边界注记**（R1-F15）：`synthesize_insights` 早退分支（:410-412 `effective_context is None`——无步骤先行调用）不写快照不发事件亦**不触发挂接段**，该路径 synthesis chain 缺席合法（<8 台账口径覆盖）；AC-2 空回退分支（R1-F12）承接投影面

**验证标准/Validation Criteria:**
- [ ] 单测层 L4 失败注入（`AsyncMock(spec=L4ObjectPort)` archive 抛 284——**mock 仅限单元测试**红线合规）：run 完成 8 步、失败步 archived=False、其余步归档不受影响、快照写与 BlmStageCompleted 发布零调用次数变化
- [ ] 单测层组装失败注入（素材缺陷构造 445）：该步 chain 缺席、流程完成、chain_records 条目数 <8 断言
- [ ] 验收/集成层**不含**失败注入场景（no-mock 红线——6-3 0.8⑧「无法构造的真实服务失败归单测层 AsyncMock 承载」同款裁定，验收 Edge Cases 不含归档写失败容错）
- [ ] epic「思维链存储成功率 100%」口径重读（OD-5）：正常路径（真实服务全绿）N 次归档 N 次可读回 + 失败零静默（archived 台账可见）——非「失败即中断」字面

### AC-5: 决策追溯查询面

**Given** 某 plan_id 的 BLM run 已完成且思维链已归档（≥1 条 EVIDENCE_PACKAGE 档案）
**When** 执行决策追溯查询（`GetBlmChainTraceUseCase`（新用例）或 CLI `chain-query --plan-id`）
**Then** 经 `StrategicArchiveService.query_archive(ArchiveQuery(plan_id=..., archive_type=ArchiveType.EVIDENCE_PACKAGE))`（既有查询面零改动）读回档案清单，组装 `ChainOfThoughtTraceView`（视图 DTO 定义在端口文件——6-3 `CheckpointRecoveryView` 先例）：`plan_id` / `records`（每条：stage 锚 + 五字段 + archive_id + degraded + **`blob_content: dict | None = None`**（R2-F4——include_blob=True 且解引用成功时填充 JSON dict，否则 None））/ `total` / `archived_count`
**And** 追溯语义：按执行序（archived_at 升序）排列；五字段从 decision_basis.chain 反序列化重构 `ChainOfThought` VO（**round-trip 等值**——重构 VO 经既有 242 校验，归档载荷完整性自证；**tuple 归一钦定**（R1-F9）：PG JSONB 读回 `tools_used` 为 list，VO `__post_init__` tuple 类型守卫（chain_of_thought.py:71-75）必拒 list——`query_chain_trace` 重构前显式 `tools_used=tuple(chain["tools_used"])` 归一，断言侧同口径）；WORM blob 深度解引用为**可选**参数（`include_blob: bool = False`——默认读 L2 决策依据足够，深度审计时解 L4；**解引用通道**（R1-F6）：经本服务第二注入 `object_storage: L4ObjectPort` 直调 `retrieve(bucket_type="archive-evidence", object_key=blob_ref)`（l4_object.py:53 流式下载，累积后 json.loads）——StrategicArchiveService 无读 blob 公开方法且被验证器 C 钉死零 diff，不经其转发；**None 行为钦定**（R2-F4）：`object_storage=None` 且 `include_blob=True` → warning 日志 + records 槽位 blob_content=None + 不抛异常——与查询面幂等读语义对齐）
**And** 不存在（无档案的合法 UUID）plan_id 查询 → 空清单 + total=0（**查询面空结果不抛异常**——与恢复面 480 语义分立：查询是幂等读，无结果也是合法答案；**边界裁定**（R1-F14）：空串/畸形 plan_id 属非法形态走 242 守卫（AC-5 验证标准第 5 条），与「空清单」语义分立——「空 plan_id」措辞统一为「无档案的合法 plan_id」）；**ArchiveQuery limit 注记**（R1-F17）：默认 limit=20（archive_repository.py:74-75），8 条/run 无碍，追溯构造钦定显式 `limit=50`（单 run 满量+余量）

**验证标准/Validation Criteria:**
- [ ] 追溯 round-trip：查回 8 条、stage 锚齐备、每条五字段与组装期期望值等值（独立构造期望——非读回值自比）
- [ ] CLI `chain-query` 输出每条 to_display() 五段形态（展示面消费——DC-2 展示用标签）
- [ ] include_blob=True 时 `records[i].blob_content` 与独立构造的期望五字段 dict 等值（R2-F4 落位断言——非「retrieve 被 call 过」交互回声；WORM 真源一致性；None 注入分支 blob_content=None + 不抛异常）
- [ ] 不存在 plan_id 查询 → 空清单 + total=0（负向：禁 480——查询/恢复语义分立声明）
- [ ] 非法 plan_id 形态（非 UUID）→ 242 `EntityValidationError`（CLI 守卫构造真实异常——6-3 R1-F18 统一形态先例）

### AC-6: 契约零破坏（事件/异常/回归面）

**Given** 本 Story 全部代码交付
**When** 运行 6-1/6-2/6-3 既有测试资产与契约守护
**Then** **零新事件**（epic 未钦定思维链事件；归档事实经既有 `ArchiveCreated` 承载——event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 零 diff）；**零新异常**（445/284/242 全复用——`_code_ranges.py` 零 diff、`EXCEPTION_HTTP_MAP` 零 diff）
**And** 6-1/6-2/6-3 回归面**零适配通过**：6-2 per-step 七键契约与 latest 七键（快照 state_data 零新键——OD-8）/ 6-3 完整形态 13 键与 TTL / **负向契约断言面零修改**（`test_event_channel_mapping_blm_planning.py:88-104,126-134` 四文件零 CheckpointReached 引用断言——6-4 改动 blm_planning_service.py 不引入该引用即零适配通过）/ 5-3 任务级思维链测试（agent_workflow_service 零触碰）
**And** 组合根 diff = 纯新增 + **恰 1 行版本号变更**（新注册块 + blm_planning_service lambda 增量注入实参 + version 行 v1.0.0→v1.1.0 修改——agent_engine v1.0.0→v1.1.0 先例 :1555-1574 同款单行变更；R1-F11 口径：version 升级必然修改既有 version 行，「零删改」按字面不可满足，精确口径=纯新增行+恰 1 行版本变更）；**端口协议面声明**（R1-F1）：`BlmPlanningServicePort` 追加 `project_chain_records` 第七方法（既有六方法零改动——增量方法追加非语义变更，契约测试断言面同步核验）

**验证标准/Validation Criteria:**
- [ ] 6-1 验收/集成 + 6-2 验收/集成 + 6-3 验收/集成 + 5-3 agent_workflow 测试面全量零修改通过（Task 4.3 回归实证——「零适配假设」验证闭环）
- [ ] event_channels.yaml / channel_router.py / _code_ranges.py / exception_handlers.py 四文件 git diff 为空
- [ ] 既有契约测试（test_port_contract_blm_planning / test_event_channel_mapping_blm_planning / test_port_contract_checkpoint）零修改通过
- [ ] 三条红线自查零输出（raise ValueError / 手动 HTTPException / 继承内置 Exception——提交前 grep）

### AC-7: 性能与持久化成功率

**Given** 思维链组装与归档在测试管线中执行（Fake LLM 管线开销口径——OD-10）
**When** 采样计时
**Then** **组装窗口 P95<50ms**：口径 = 步骤素材就绪 → `ChainOfThought` VO 构造完成（五字段映射+校验）窗口（纯内存组装——确定性组装零 LLM 调用使 epic 指标物理可达；归档 I/O 与 LLM 延迟显式出栈独立计量——6-1 DC-7/6-2 OD-3/6-3 OD-6 口径差声明三先例，口径差落测试 docstring）
**And** **存储成功率**（OD-5 口径）：正常路径 N 次归档 N 次可读回（强制环节零吞错语义测试承载——8 条/run 全量 archived=True 且追溯查回全量）
**And** **并发写入 10 个思维链**：`asyncio.gather` 并发 10 条组装+归档（10 独立 stage 素材——6-1 集成「并发 5 市场洞察」先例同款），全部成功且档案库可查回 10 条；**会话模型钦定**（R1-F7）：每协程 `async with session_context(session_factory)` 独立 scope（session_context.py 模块头 R3「后台任务使用 session_context() 创建独立 scope」——PostgreSQLAdapter session 来自 ContextVar，gather 共享单 AsyncSession 并发使用不被 SQLAlchemy 支持）；**plan_id 口径消歧**（R1-F7）：并发场景 10 素材**共享一个场景专属 plan_id**（count==10 按 plan_id+archive_type 过滤成立），与隔离表「资源唯一性」行一致

**验证标准/Validation Criteria:**
- [ ] 组装窗口采样 ≥20 轮，P95 = `sorted(durations)[ceil(0.95*n)-1]` < 50ms（6-1/6-2/6-3 同款数学口径；升序排序前提显式声明）
- [ ] 成功率：一次 run 8/8 归档可读回 + 追溯 total==8（正常路径）
- [ ] 并发 10：gather 全部返回 archived=True + 档案库 count==10（按 plan_id + archive_type 过滤）
- [ ] 性能采样场景挂 `pytest.mark.xdist_group("blm-planning-perf")`（跨 Story 同 worker 串行——6-2/6-3 组复用先例；BDD 30s 硬超时预算内）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] **零新增事件**（OD-6）：归档事实经既有 `ArchiveCreated`（`src/domain/events/archive_events.py:17-49`，3-10 交付，event_channels.yaml/ChannelRouter 双登记在位——6-3 集成②已断言落行）承载；epic 6.4 文本未钦定思维链专属事件，YAGNI
- [ ] 既有事件零字段变更：`BlmStageCompleted`/`PlanningStarted`/`AgentDecided` 投影五键白名单结构零变化（仅 chain_summary 取值源真实化——AC-2）

#### 数据模型 (Data Models)
- [ ] **零新建领域 VO**（复用 `ChainOfThought`——5-3 交付，全仓 grep 实证无同语义重复类型；6-3 Lessons「新增领域类型前必须全仓 grep」纪律执行完毕）
- [ ] **组装素材映射冻结**（Task 0.2——本 Story 最核心规范，唯一真源）：

| ChainOfThought 字段 | 素材源（采集点） | 组装规则 |
|---|---|---|
| `input_summary: str` | **按步骤型分列**（R1-F3）：六子步骤=`StepSemanticConfig.display_name`+`role_prefix`（blm_planning_prompts.py:172-221 六配置行）+`len(evidence_texts)`；performance_gap=`PERFORMANCE_GAP_CONFIG`（:162-169）+`len(evidence_texts)`；**synthesis=组装服务模块级常量（display_name="市场洞察综合"/role_prefix="CMO"——语义配置只有 gap+六子七行，synthesis 无 StepSemanticConfig，不新增 prompts.py 配置行不动 6-1 资产）+ 证据计数恒 0**（synthesize_insights :391-449 无检索调用）；`task` 三型均可达（`BlmPlanningContext.task` :85） | 六子/gap：`f"{display_name}｜{role_prefix}｜任务: {task[:80]}｜检索证据 {n} 条"`；synthesis：`f"市场洞察综合｜CMO｜任务: {task[:80]}｜综合结论 {len(conclusions)} 项"`（非空保证：配置常量/模块常量恒非空；n 上限 5——`_MAX_EVIDENCE_TEXTS` :88） |
| `tools_used: tuple[str, ...]` | `_execute_candidate_tools`（blm_planning_service.py:559-608）返回三元组 `(输出摘要, 工具面降级原因, tool_slug)` 的**第三位单数 slug**——`tool.slug or tool.name` :600（slug 可选 kebab-case 无版本后缀，缺失回落中文显示名）；**首个成功候选即返回 :601，每步至多 1 项**（R1-F2 实测定谳——「清单+版本后缀」是 5-3 任务级 tool_trace 语义，BLM 面不存在） | `(tool_slug,) if tool_slug else ()`；空元组合法（无工具步/工具降级步/工具候选全部失败步——`(none)` 展示占位由 to_display 既有处理） |
| `reflection: str` | **按步骤型分列**（R1-F3）：六子步骤=`result.summary`+`len(result.findings)`；performance_gap=`summary`（=financial_gap :284）+`len(artifacts.root_causes)`；synthesis=`len(synthesis.conclusions)`+`len(synthesis.degraded_inputs)`（**无 summary 字段**——InsightSynthesis 仅两字段 blm_phases.py:271-286） | 六子：`f"步骤产出: {summary[:120]}；要点 {len(findings)} 项{'；降级: ' + degrade_reason if degraded else '；流程正常'}"`；gap：`f"步骤产出: {summary[:120]}；根因 {len(root_causes)} 项{...}"`；synthesis：`f"综合结论 {len(conclusions)} 项；降级输入 {len(degraded_inputs)} 项{...}"`（降级信息入反思——降级是决策过程的一部分） |
| `constraints_check: str` | **按步骤型分列**（R1-F3）：六子步骤=structured_output 值域守卫（InsightStepResult :247-267 既有校验）+证据充分性 `n>=3`（n=`len(evidence_texts)`）；performance_gap=四字段产物完整性（成功支 financial_gap 非空）+证据充分性（n 同源）；synthesis=结论产出判定（conclusions 非空）+degraded_inputs 标注（**无检索面无证据充分性段**——:391-449 无 _retrieve_evidence 调用） | 六子：`f"结构化输出值域校验: {'通过' if ok else '缺失'}；证据充分性: {'充足' if n>=3 else '不足'}；降级标记: {degraded}"`；gap/synthesis 同构按型替换首段 |
| `final_answer: str` | 六子步骤=`structured_output` dict 原样；performance_gap=`dataclasses.asdict(PerformanceGapArtifacts)` **六键**（blm_phases.py:195-200 含 degraded/degrade_reason——R1-F4）；synthesis=`dataclasses.asdict(InsightSynthesis)` **两键**（conclusions/degraded_inputs）；**降级信封 `{"degraded": True, "degrade_reason": ...}` 仅适用于产物缺席形态**（六子=structured_output None；部分降级=产物原样——R2-F2） | `json.dumps(payload, ensure_ascii=False)`（排序不强制——round-trip 判别经 json.loads 等值；**list 归一口径**：asdict 的 tuple 字段经 json 回解为 list，断言比较前显式 `tuple()` 归一——R1-F9） |

- [ ] **归档载荷映射冻结**（Task 0.3——AC-3 唯一真源）：见 AC-3 Then 载荷三键（decision_basis kind+stage 锚 / assumptions 过程素材 / evidence_blob 结构化 JSON——DC-2 存储用结构化；**tools_used tuple 经 json.dumps 转 JSON array，读回 list 需 `tuple()` 归一——R1-F9 AC-5 钦定**）
- [ ] **ChainRecord / StepChainMaterial / ChainOfThoughtTraceView** 三 dataclass 定义在端口文件（application 层——多字段组合载体放端口文件先例，5-3 七 dataclass 同款；Task 0.4 终稿）。**StepChainMaterial 字段表冻结**（R1-F10——AC 未逐字段钦定，此处直接落档）：

| 字段 | 类型 | 三型差异说明 |
|---|---|---|
| `stage` | `str` | STAGE_VALUE_DOMAIN 八值之一——**构造公式钦定**（R3-F7）：六子=`f"market_insight_{step.value}"`（:384 同源——方法内裸变量 `step.value` 是 "trend" 短值不在八值集，必须前缀拼装）；gap="performance_gap"；synthesis="market_insight_synthesis" |
| `display_name` / `role_prefix` | `str` | 六子/gap=语义配置取值；synthesis=调用方（服务挂接段）传模块常量 |
| `task` | `str` | 三型同源（context.task） |
| `evidence_count` | `int` | gap/六子=len(evidence_texts)；synthesis 恒 0 |
| `tool_slug` | `str` | `_execute_candidate_tools` 第三返回值（可空串——空即空元组）；synthesis 恒 ""；**实值注记**（R3-F6）：TOOL_CATALOG 23 工具全零 `slug=`（strategic_tool_catalog.py 实测）——`tool.slug or tool.name` :600 回落分支恒触发，**实值恒为工具中文显示名**，判别力期望按 name 构造 |
| `evidence_refs` | `tuple[str, ...]` | **R3-F1 补**：六子=`result.evidence_refs`（blm_phases.py:240）；gap=检索三元组第三位（:252）；synthesis=()（无检索）——AC-3 assumptions.evidence_refs 的源字段 |
| `summary` | `str` | 六子=result.summary；gap=summary（=financial_gap）；synthesis=""（无该字段，reflection 用 conclusions 计数替代） |
| `findings_count` | `int` | 六子=len(findings)；gap=len(root_causes)；synthesis=len(conclusions)（**统一命名承载三型计数——组装服务按 stage 型选用素材**） |
| `degraded_inputs_count` | `int` | synthesis 型专用（其余 0） |
| `degraded` / `degrade_reason` | `bool` / `str` | 三型同构（信封/产物字段直取） |
| `payload` | `dict` | 六子=structured_output；gap=asdict 六键；synthesis=asdict 两键；降级步=降级信封 dict |
| `structured_ok` | `bool` | constraints_check 素材（六子=值域守卫结果；gap=financial_gap 非空；synthesis=conclusions 非空） |

**纯组装函数钦定**（R1-F13）：`compose_step_chain(material: StepChainMaterial) -> ChainOfThought` 为**模块级纯函数**（定义在 chain_of_thought_archive_service.py，零 I/O 零 LLM——AC-7 P95 采样直调对象；`compose_and_archive_step_chain` 内部复用之再接归档 I/O）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 新端口 `ChainOfThoughtArchiveServicePort`（`src/application/ports/chain_of_thought_archive.py`，`@runtime_checkable Protocol`）两方法：`compose_and_archive_step_chain(plan_id: uuid.UUID, stage: str, material: StepChainMaterial) -> ChainRecord | None`（组装+归档单步——**返回可空**（R1-F5）：组装失败 445 捕获降级时返回 None（该步 chain 缺席——AC-4 台账语义；ChainRecord.chain 非可选无法构造缺席记录，端口签名与降级语义对齐）；归档失败 284 时返回 `ChainRecord(archived=False, archive_id="", ...)` 非 None）/ `query_chain_trace(plan_id: uuid.UUID, include_blob: bool = False) -> ChainOfThoughtTraceView`（追溯——重构前 `tools_used=tuple(...)` 归一 R1-F9）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_chain_of_thought.py`（注册/spec 元数据/resolve/注入链）
- [ ] 组合根注册：`chain_of_thought_archive_service`（SINGLETON——**双注入**（R1-F6）：`strategic_archive_service` + `object_storage=resolve_optional("l4_object")`（include_blob 解引用通道——与 strategic_archive_service 组合根 :2217 同源可选解析））+ `blm_chain_trace_use_case`；`blm_planning_service` lambda 增量注入第九依赖 + version v1.0.0→v1.1.0（恰 1 行版本变更——R1-F11）
- [ ] 端口注册带 PortSpec（name/version/interface/impl/module/lifetime/owner/tags）；跨模块调用仅依赖抽象接口
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

#### 端口契约清单执行约束（强制）
- [ ] 本 Story 端口清单是唯一事实源：新增 1 个端口（chain_of_thought_archive_service）+ 1 个用例端口（blm_chain_trace_use_case）；既有端口零语义变更——`blm_planning_service` 构造器增量注入第九可选尾参 + **协议追加 `project_chain_records` 第七方法**（R1-F1：`project_timeline`/`project_degraded_steps` :193/:197 同构第三投影，增量方法追加非语义变更，既有六方法零改动；`sp_blm_graph.py` 节点适配器消费该方法直写 state——见 AC-2 三件套）
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **本 Story 零新增异常**（OD-6——全部复用既有，`_code_ranges.py`/`__init__.py`/`EXCEPTION_HTTP_MAP` 三文件零 diff）：

| 异常（既有） | code | 触发场景（本 Story 增量触发面） | 处置语义 |
|---|---|---|---|
| `ChainOfThoughtValidationError` | EXCEPTION_445（agent 域，5-3 交付） | 组装产物五字段缺失/空值（素材缺陷构造性场景——单测层红测） | 组装层捕获 242 改写（5-3 :386-393 同款）→ **降级不阻断**（AC-4——该步 chain 缺席台账可见）；**注记**（R1-F17）：242→445 路径 missing_fields 最多单元素（VO `__post_init__` 逐字段短路一次只抛一个 field），断言勿假设多字段清单 |
| `ArchiveStorageError` | EXCEPTION_284（archive 域，3-10 交付） | 归档 L2/L4 强制层失败/归档内 ArchiveCreated 发布失败（单测层注入） | 捕获 → archived=False 台账 + warning 日志 → **降级不阻断**（AC-4） |
| `EntityValidationError` | EXCEPTION_242（entity 域） | ChainOfThought VO `__post_init__` 既有校验（组装层捕获面）/ CLI plan_id 非 UUID 守卫（AC-5） | 透传或改写（上述两通道） |

- [ ] 编码分配：**零新编码**（planning 段 485-489 预留维持——6-6 恢复执行面既有预留声明不侵占）
- [ ] 消息安全性：复用异常既有 message（445 message 组合 missing_fields——6-3 R1-F3 组合 reason 先例知悉，5-3 既有形态零改动）

#### API 契约 (API Contract)
- [ ] **零 HTTP API 变更**（本 Story 无新 REST 路由——BLM 消费面是 CLI，与 6-1/6-2/6-3 一致；REST 面归后续 Story）；`docs/api/openapi.yaml` 零 diff

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖（本 Story 零改动——VO 复用） |
| application | `src/application/` | 组装+归档编排+追溯用例（本 Story 主改动层） |
| interfaces | `src/interfaces/` | 零改动（无新 REST 面） |
| infrastructure | `src/infrastructure/` | 零改动（归档经既有 StrategicArchiveService→PG/Qdrant/MinIO 适配器；LangGraph state 加键零改动） |

**领域层零依赖原则**：本 Story domain 层预期零改动（Task 0.8 复核终裁——若组装纯函数需下沉 domain 则素材类型必须标准库形态；当前设计组装逻辑依赖应用层配置类型 StepSemanticConfig，归应用层）

**依赖方向矩阵**（R1~R4 设计规则落位）：
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application**（本 Story 全部新增代码所在层） | ✓ 允许（ChainOfThought VO） | — | ✗ 禁止 | ✗ 禁止 |
| **infrastructure**（state 键扩展+图适配器直写行） | ✓ | ✓ | ✗ 禁止 | — |

- **R1 落位**：领域层基础端口（ChainOfThought VO / ArchiveRepositoryPort / L3VectorPort / L4ObjectPort / SnapshotRepositoryProtocol——全部既有复用，零新建）
- **R2 落位**：应用层端口 `ChainOfThoughtArchiveServicePort` **组合注入**既有应用服务 `StrategicArchiveService` + `L4ObjectPort`（R1-F6 双注入——include_blob 解引用）+ `BlmPlanningService` 尾参可选注入本服务（R2 组合注入双向体现）；`BlmPlanningServicePort` 协议追加 `project_chain_records` 投影方法（R1-F1——应用层端口增量）
- **R3 落位**：基础设施层零新增**实现类**（归档五步编排经既有 StrategicArchiveService 消费既有 PG/Qdrant/MinIO 适配器——支持扩展其他同类技术实现的能力由既有端口族承载）；infrastructure 层两处**增量修改**（R1-F1）：`schemas.py` SpBlmState 加键 + `graphs/sp_blm_graph.py` 三类节点适配器各加一行 chain_records 直写（`degraded_steps`/`timeline` 同构既有模式，非新实现）
- **R4 落位**：接口层零改动；入口层 CLI `chain-query` 子命令（`src/entrypoints/agent_cli.py`——6-3 checkpoint-create 先例）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_json_chain_of_thought.feature`（13 场景，AC 横幅分组+中文 Gherkin）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_json_chain_of_thought.py`（BDD 三件套+分档表 docstring+门控动态 skip+Fake LLM/Embedding 双豁免——6-3 演进形态为准，R6 模板旧欠账不承袭）
- [ ] 所有场景覆盖（Happy Path + Edge Cases——降级步形态/空查询/非法 plan_id；归档失败注入归单测层 no-mock 红线）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（`_run_async` 包装）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——本 Story 异常路径落位：降级步思维链（S3）/ 空清单查询（S7 负向）/ 非法 plan_id 242（S7 负向）；归档写失败归单测层（AC-4 裁定）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（组装映射/归档载荷/端口契约/异常复用清单四冻结）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态：ModuleNotFoundError（chain_of_thought_archive 端口/服务缺失）+ AttributeError（chain_records 缺失）+ 收尾清单 AssertionError）
- [ ] **链路接线断言清单**已定义（Task 0.9）：① 组合根 resolve 可达（chain_of_thought_archive_service / blm_chain_trace_use_case / blm_planning_service 九依赖注入链非 None——契约测试承载）；② 归档真实调用验证（挂接点代码位三方法 + L2 行/L4 blob 实证 + ArchiveCreated 落行——集成②+验收 S5 承载）；③ CLI chain-query 入口接线（tests/unit/interfaces/cli/test_agent_cli.py 新子命令用例）；④ EVIDENCE_PACKAGE 激活唯一性（构造位唯一——架构验证器 C 承载）；⑤「已实现未接线」检查：本 Story 交付件零休眠（任务级思维链归档归 5.7 属既有 5-3 资产的既有状态，非本 Story 交付件——deferred 注记）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿（证明断言活着） |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | ChainOfThoughtArchiveService | 组装映射五字段/降级信封/445 改写/284 降级台账/追溯视图组装 | `tests/unit/application/test_chain_of_thought_archive_service.py` | Task 1 |
| **TDD 单元测试** | BlmPlanningService 挂接 | 三方法挂接/chain_records 累积/尾参可选（None 时零挂接）/快照事件零影响 | `tests/unit/application/test_blm_planning_service.py`（扩展） | Task 2 |
| **TDD 单元测试** | 用例与 CLI | 追溯用例透传/空清单/242 守卫/chain-query 输出 | `tests/unit/application/use_cases/test_blm_chain_trace_use_case.py` + `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 3 |
| **TDD 单元测试** | AgentDecided 投影 | SpBlmGraph chain_summary 真实化值级断言 | `tests/unit/application/test_blm_planning_service.py`（TestSpBlmGraphTopology 扩展——投影纯标量断言先例 :1005-1027；R1-P3 目标订正：agent_orch/ 目录零 SpBlmGraph 用例） | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_json_chain_of_thought.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_json_chain_of_thought.py` | Task 0/7 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约 / registry / resolver / contract gate | 端口注册、版本、兼容性、实现解析、注入链 | `tests/contracts/test_port_contract_chain_of_thought.py` | Task 1/4 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、EVIDENCE_PACKAGE 唯一构造位、归档服务零触碰、BLM 挂接点、负向断言面 | `tests/unit/architecture/test_json_chain_of_thought.py`（epics L2218 钦定名） | Task 6 |
| **集成测试** | 真实链五场景 | 全链归档 round-trip/追溯/并发/性能/回归面 | `tests/integration/test_integration_chain_of_thought.py`（OD-7：对 epics L2219 钦定名 `test_json_chain_of_thought_integration.py` 的显式偏离——仓规 tests/integration/ 全目录 `test_integration_*` 前缀惯例，6-3 OD-8 同款拆分声明） | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**（本 Story 主改动层——epics L2209 钦定）
- [ ] **domain 层 ≥90% 维持**（本 Story domain 预期零改动——既有门禁不降）
- [ ] **集成测试覆盖率 ≥75%**（epics L2210 钦定）
- [ ] **关键路径覆盖率 100%**（组装映射五分支/降级两通道/归档载荷三键）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **PG 档案行清理** | **集成=真实归档提交+按 plan_id 删除清理**（R1-F7 口径订正：挂接点内归档经 archive_plan 真实提交，savepoint 回滚模式不适用于服务内归档链路；6-3 集成实证形态 :190-268 真实四服务+清理链同构——仅 commit 失败时 session 级 rollback 兜底 :292-296）；验收=真实提交后按 plan_id 删除 EVIDENCE_PACKAGE 行（6-3 `_cleanup_archive_residues` :346-430 先例——登记-清理闭环，R1-F1 教训） | 档案行泄漏累积 |
| **outbox 行清理**（R3-F3） | ArchiveCreated 8 行/run——`event_type='ArchiveCreated'` + `payload->'payload'->>'plan_id'` 双通道精确 DELETE（6-3 teardown 第②步 :287-291 先例）；集成② S9 断言场景后对称清理 | outbox 行泄漏累积 |
| **Qdrant 点清理** | 点 ID 为 MD5 哈希 int——断言/清理按 `payload.archive_id` 匹配（6-3 环境事实沉淀） | 点泄漏 |
| **MinIO WORM 清理** | WORM 对象经 `remove_objects(bypass_governance_mode=True)` 清理；bucket 必须 object-lock 形态（无锁 bucket 上 GOVERNANCE 设置使 L4 阻断——探测自愈 bypass 清版本重建，6-3 环境事实） | 对象泄漏/L4 阻断 |
| **Redis 零新键** | 本 Story 快照面零改动（OD-8）——无新 Redis 键族；验收沿用 6-1/6-2 blm-planning- 键清理链 | 无新增面 |
| **资源唯一性** | plan_id 独立 UUID（全链场景单 run 单 plan 8 步；**并发 10 场景 10 素材共享一个场景专属 plan_id**——R1-F7 消歧：count==10 按 plan_id+archive_type 过滤成立，与 AC-7 一致；各场景间 plan_id 互异） | 档案混淆 |
| **并行隔离** | xdist_group("blm-planning-perf") 同 worker 串行（跨 Story 组复用——6-2/6-3 先例）；性能/归档密集场景全入组 | 资源竞争随机失败 |
| **asyncio 上下文** | BDD 步骤 `event_loop.run_until_complete()`（`_run_async` 包装）；模块级 event_loop fixture（scope="module"）；场景级 context dict | context 数据丢失 |
| **pytest-asyncio** | BDD 步骤函数禁 `@pytest.mark.asyncio`；`asyncio_mode="auto"` 下 BDD 同步步骤经 `_run_async` 调度 | 步骤间状态丢失 |
| **延迟 import 纪律** | 新交付模块一律在步骤函数体内 import（否则收集期整文件炸——6-1 先例） | 收集期崩溃 |
| **并发测试方法** | 真正并发在 async 函数内 `asyncio.gather()`（10 归档并发——6-1 并发 5 先例） | 假并发 |
| **清理粒度/依赖声明** | teardown 链各步独立 try/except（断言失败也执行——6-3 六步链先例）；fixture 显式声明依赖 | 残留/顺序不确定 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（6-3 同构：归档面按 plan_id 定向清理——R1-F7 口径；测试范围外的表禁止触碰）
- ❌ 验收/集成层 mock 归档失败（`AsyncMock` 注入仅限单元测试——no-mock 红线；Fake LLM/Fake Embedding 为外部 SaaS 双豁免唯一例外）
- ❌ autouse fixture 删除全局匹配资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 性能场景缺 xdist_group（跨 worker 资源竞争）

**验证要求：**
- [ ] 并行测试 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance` 四目录全量通过（**显式四目录——裸 `tests/` 会挂起**）
- [ ] 连续 3 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 每步五段组装+8 条/run | Task 1 | 组装映射五分支+降级信封 | test_chain_of_thought_archive_service.py + 验收 S3（R3-F2 补行） |
| AC-1 | 组装映射判别力 | Task 1 | 期望轨迹独立构造+round-trip | 同上 + 验收 S2 |
| AC-1 | to_display 展示形态 | Task 1 | 五段展示 VO 方法复用断言 | 同上 + 验收 S10（R1-F8 归位） |
| AC-1 | 挂接点触发 | Task 2 | 三方法末尾挂接 | test_blm_planning_service.py（扩展） |
| AC-2 | Result/图 state 携带 | Task 2 | 三件套回传（run_state 累积+投影+适配器直写——R1-F1）+默认尾字段 | 同上 + 验收 S4 |
| AC-2 | 投影 chain_summary 真实化 | Task 2 | SpBlmGraph 投影分支取值源 | test_blm_planning_service.py::TestSpBlmGraphTopology（扩展——投影纯标量断言先例 :1005-1027，R1-P3 目标订正） |
| AC-3 | EVIDENCE_PACKAGE 归档+载荷 | Task 1 | 归档调用+载荷映射冻结 | test_chain_of_thought_archive_service.py + 集成① + 验收 S5 |
| AC-3 | L2/L3/L4 真实落位 | Task 5 | 集成真实链 | test_integration_chain_of_thought.py |
| AC-4 | 归档失败降级台账 | Task 1 | 284 捕获+archived=False+计数 | 单测 AsyncMock 注入（no-mock 红线合规） |
| AC-4 | 组装失败降级 | Task 1 | 445 捕获+chain 缺席 | 同上 |
| AC-5 | 追溯查询面 | Task 1/3 | query_chain_trace+用例+CLI | test_blm_chain_trace_use_case.py + 验收 S6/S7 |
| AC-5 | blob 深度解引用可选 | Task 1/3 | include_blob 参数 | 同上 + 集成② |
| AC-6 | 事件/异常零新增 | Task 4 | 四文件零 diff 验证 | 契约守护 + 验收 S9（R5 回指补） |
| AC-6 | 6-1/6-2/6-3 回归面零适配 | Task 4 | 既有测试全量复跑 | 回归实证记录 + 验收 S8/S13 |
| AC-6 | 负向断言面零修改 | Task 4/6 | 四文件零 CheckpointReached 复跑 | test_event_channel_mapping_blm_planning.py |
| AC-7 | 组装 P95<50ms | Task 5 | 20 轮采样窗口（纯函数直调——R1-F13） | 集成④（xdist_group）+ 验收 S11 |
| AC-7 | 成功率+并发 10 | Task 5 | 8/8 读回+gather 10 | 集成①③ + 验收 S1/S12（R1-P3 订正：成功率读回是场景①面非⑤） |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-7（规范冻结）；重点 AC-1/AC-3

> **目的：** 在进入代码实现前，冻结组装映射、归档载荷、端口契约、异常复用清单与 Gherkin 验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 范围边界与复用面核验（四源声明：5-3 VO 零改动 / EVIDENCE_PACKAGE 零使用实证复跑 / 6-1 边界表 L37 钦定 / 6-2 快照契约不破坏）——全仓 grep 三条实证命令留档（`grep -rn "EVIDENCE_PACKAGE" src/` 仅枚举定义两行 / `grep -rni "chain.*archive|persist.*chain" src/` 零命中 / `grep -rn "ChainOfThought" src/application/services/blm_*` 零命中）
- [ ] Subtask 0.2: 组装映射冻结（五字段素材源表——本文件「数据模型」节为唯一真源；`_execute_candidate_tools` 返回形态亲验定谳工具轨迹提取规则）
- [ ] Subtask 0.3: 归档载荷映射冻结（decision_basis kind+stage 锚 / assumptions 过程素材 / evidence_blob 结构化 JSON——AC-3 唯一真源；embedding_text 构造亲验——`strategic_archive_service.py:148` 上游确认）
- [ ] Subtask 0.4: 端口契约定稿（ChainOfThoughtArchiveServicePort 两方法 + StepChainMaterial/ChainRecord/ChainOfThoughtTraceView 三 dataclass 字段表）
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_json_chain_of_thought.feature`（**13 场景编号连续钉死**（R1-F8 重排——AC-5 拆正向/负向两场景消除 S11 空洞与 S6 二义，to_display 场景归 AC-1）：S1 全链 8 条（AC-1，含 AC-7 成功率断言并入）/S2 组装映射判别力（AC-1）/S3 降级步形态（AC-1）/S4 Result 携带+投影真实化（AC-2）/S5 归档真实落位（AC-3）/S6 追溯查询正向（AC-5）/S7 追溯负向两形态（AC-5——**单 Scenario 含两段 Given-When-Then**（R2-F9）：无档案合法 plan_id 空清单段+非法 plan_id 242 段串联，@scenario 绑单场景名，拆两 Scenario 则计数 14≠13 失配）/S8 零回归守护（AC-6）/S9 事件零新增+ArchiveCreated 落行（AC-6）/S10 to_display 展示形态（AC-1 验证标准 5——原 S12 归位）/S11 P95 组装窗口（AC-7）/S12 并发 10（AC-7——原 S10+S11 并入）/S13 收尾清单）
- [ ] Subtask 0.6: 编写 BDD 步骤实现（**含延迟 import 的完整步骤体**——非占位骨架，0.7 全红失败形态依赖完整实现；R1-P3 措辞订正）`tests/acceptance/test_acceptance_json_chain_of_thought.py`（docstring 五段+场景三属性分档表/pytestmark 全套+xdist_group blm-planning-perf/13 场景全绑定 @scenario/模块级 event_loop+context dict+_run_async 三件套/teardown 链含**四清理步**（R3-F3：PG 档案行+Qdrant 点+MinIO WORM 对象+**outbox 行**（`event_type='ArchiveCreated'` + `payload->'payload'->>'plan_id'` 双通道 DELETE——6-3 六步链第②步 :287-291 移植，S9 断言落行后必须对称清理，8 行/run×全链场景）/（6-3 `_cleanup_archive_residues` :346-430 形态移植））/**验收装配归档服务 publisher 形态钦定**（R3-F8：默认 None+发布场景（S9）重建真实 publisher——6-3 先例 :636 同款，避免全场景 8 行/run outbox 残留放大清理面）/Fake LLM 双 Schema 族分派工厂（复用 6-2 `_make_fake_llm` 按 response_schema 身份分派形态——test_acceptance_market_insight.py:365 先例；6-4 组装零新增 LLM 调用故 Fake 面不扩）/Fake Embedding 豁免工厂/延迟 import 纪律）
- [ ] Subtask 0.7: 运行验收测试，确认 13 场景全红零 skip（四真实服务门控全过；失败形态钦定：ModuleNotFoundError×N（端口/服务缺失）+AttributeError（chain_records 缺失）+AssertionError（收尾清单）——收集期零错误）
- [ ] Subtask 0.8: 既有资产复核（八项亲验——**①② 已于文档审查 R1 实测定谳**（R1-F2/F3，正文冻结表已按实测形态书写，本 Subtask 复跑确认而非重新定谳）：① `_execute_candidate_tools`（blm_planning_service.py:559-608）返回三元组 `(输出摘要, 降级原因, tool_slug)`——**单数 slug 至多 1 项无版本后缀**（:600-601 首个成功即返回）；② **双单数形态断裂**：`InsightStepResult.tool_used` 是单数 str（blm_phases.py:239）**且执行轨迹第三返回值同为单数 str**——ChainOfThought.tools_used 是 tuple[str,...]，包装 `(tool_slug,)`（6-1 属性形态断裂族教训直接应用：素材采集从执行轨迹取而非信封字段，且**不得假设清单形态**）；③ `archive_plan` embedding_text 构造（:144-148 上游）；④ `PerformanceGapArtifacts` asdict **六键**/`InsightSynthesis` asdict **两键**（frozen dataclass 标准库形态亲验——R1-F4 口径）；⑤ AgentDecided SpBlmGraph 投影分支（langgraph_engine.py:258-279）chain_summary 现值形态；⑥ 组合根 blm_planning_service lambda（:1580-1598）注入实参断言面（test_port_contract_blm_planning.py:89-98 inspect.getsource——增量注入不破坏既有断言亲验）；⑦ 三方法挂接点素材可见性（六子步骤：result 信封+裸变量全可见；**performance_gap：无 findings/structured_output——素材=artifacts 六属性+summary+evidence_texts+`_tool_slug`/`_evidence_refs`（下划线命名作用域可见可采集——R3-F9 补）（:249-297 作用域）；synthesis：conclusions/degraded_inputs，无工具无检索（:391-449）——R1-F3 三型分列依据**）；⑧ SpBlmState TypedDict（schemas.py:84-110）加键零破坏亲验（total=False——**写侧经 sp_blm_graph 节点适配器（R1-F1 三件套③），加键本身不产生写入**）
- [ ] Subtask 0.9: 链路接线断言清单五项定义（见 Task 0 完成标志⑤）+ deferred-work 处置注记落档（L192 R1-DF3 零触发注记——6-4 确定性组装不经 ChainOfThoughtSchema；新登记：5-3 任务级思维链归档归 5.7 Phoenix/后续 Story）

**完成标准/Definition of Done:**
- [ ] 规范项全部冻结（四冻结：组装映射/归档载荷/端口契约/异常复用）
- [ ] 验收测试运行失败（预期行为，红阶段确认——13 场景全红）

---

### Task 1: 应用层——ChainOfThoughtArchiveService（组装+归档+追溯）+ 端口 + 异常复用

**关联 AC:** AC-1 / AC-3 / AC-4 / AC-5

#### TDD 循环 A：组装与归档服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_chain_of_thought_archive_service.py`（组装映射**三型×五字段**参数化（R1-F3——gap/六子/synthesis 素材分列）/降级信封+**部分降级产物原样**（R2-F2 两形态各一用例）/445 改写（**构造配方 `tool_slug=" "`**（R2-F3）→**返回 None** R1-F5）/284 捕获降级台账（AsyncMock spec=StrategicArchiveService 抛 ArchiveStorageError→ChainRecord(archived=False)）/归档载荷三键映射断言（期望值独立构造）/8 条 run 形态/纯组装函数 compose_step_chain 独立单测（R1-F13——P95 采样对象）） |
| 🟢 绿 | 实现 `src/application/ports/chain_of_thought_archive.py`（Protocol + 三 dataclass + CHAIN_ARCHIVE_KIND 常量）+ `src/application/services/chain_of_thought_archive_service.py`（**模块级纯函数 compose_step_chain(material)→ChainOfThought**（R1-F13）+ compose_and_archive_step_chain：素材→纯函数组装→VO 构造 242 捕获改写 445 **返回 None**（R1-F5）→archive_plan 载荷映射→284 捕获 archived=False→ChainRecord 返回）最小代码 |
| 🟡 变异 | 组装映射改坏（tools_used 置空/final_answer 换回声）→红；归档调用删除→archived 断言红；还原→绿 |
| 🔄 重构 | 类型注解/docstring（Google 风格全中文）/ruff+mypy |

- [ ] Subtask 1.1: 🔴 红 — 组装与归档服务失败测试（Mock 工厂 `AsyncMock(spec=StrategicArchiveService)` + `_make_material()` 工厂函数——集成 Mock 工厂子模式形态）
- [ ] Subtask 1.2: 🟢 绿 — 端口文件 + 服务实现最小代码
- [ ] Subtask 1.3: 🟡 变异 — 映射/归档/降级三锚突变实证
- [ ] Subtask 1.4: 🔄 重构 — 注解与文档

#### TDD 循环 B：追溯查询

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展同文件（query_chain_trace：档案清单→视图组装/五字段 round-trip 重构 VO（**tools_used=tuple(...) 归一断言**——R1-F9）/include_blob 解引用（L4ObjectPort.retrieve mock 注入——单测层；**blob_content 落位断言 + object_storage=None 分支**（R2-F4——warning+槽位 None 不抛异常）/空清单/排序 archived_at 升序） |
| 🟢 绿 | 实现 query_chain_trace 最小代码（query_archive 既有面（**ArchiveQuery 显式 limit=50**——R1-F17）+ decision_basis.chain 反序列化（tools_used tuple 归一）+ include_blob 经 object_storage.retrieve 解引用） |
| 🟡 变异 | stage 锚丢失→排序断言红；blob 跳过→深度断言红；还原→绿 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 1.5: 🔴 红 — 追溯查询失败测试
- [ ] Subtask 1.6: 🟢 绿 — 追溯实现
- [ ] Subtask 1.7: 🟡 变异 — 两锚实证
- [ ] Subtask 1.8: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] 服务两方法实现完成（组装+归档/追溯）
- [ ] TDD 循环 A/B 全部通过
- [ ] 445/284 复用异常触发面测试在位（零新增异常实证）
- [ ] 覆盖率≥85%（application 主改动层）

---

### Task 2: BLM 挂接——三方法组装归档挂接 + state/Result/投影扩展

**关联 AC:** AC-1 / AC-2

> ⚠️ **本 Task 是既有回归风险集中面**（blm_planning_service.py 是 6-1/6-2 核心资产）——尾参可选注入（None 时行为与现状逐字节等价）+ 三方法末尾追加挂接段（既有语句零改动）+ 默认尾字段零破坏三重护栏。

#### TDD 循环 A：服务挂接

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/test_blm_planning_service.py`（挂接用例族：三方法挂接后 `run_state.chain_records` 累积（`project_chain_records` 投影断言——R1-F1①②）/尾参 None 时零挂接（call_order 断言归档服务零调用——与现状等价性守护）/素材采集点正确（tools_used=执行轨迹第三返回值单数 slug 包装元组——0.8② 双单数形态断裂应用；**三型素材构造正确**——R1-F3）/compose 返回 None（445 降级）时跳过追加/快照写与 BlmStageCompleted 调用次数零变化） |
| 🟢 绿 | `BlmPlanningService.__init__` 尾部追加 `chain_archive_service: ChainOfThoughtArchiveServicePort \| None = None`（本类 base_config :145 + LangGraphEngine :52-53 双尾参先例——R1-P3 行号订正）+ `_PlanRunState` 加 `chain_records: list[ChainRecord]` 字段 + `project_chain_records(plan_id)` 投影方法（degraded_steps/timeline 同构）+ 三方法末尾（快照写之后、return 之前）挂接段（素材采集→compose_and_archive_step_chain→**None 判断跳过/ChainRecord 追加 run_state.chain_records**——R1-F1①：累积进 per-run 状态非返回值，三方法返回 VO 零改动）最小代码 |
| 🟡 变异 | 挂接段删除→chain_records 断言红；尾参默认改非 None→等价性守护红；project 方法删除→投影断言红；还原→绿 |
| 🔄 重构 | 挂接段提参（若三方法重复——组装素材构造器私有方法化） |

- [ ] Subtask 2.1: 🔴 红 — 挂接用例族失败测试
- [ ] Subtask 2.2: 🟢 绿 — 尾参+三挂接段最小代码
- [ ] Subtask 2.3: 🟡 变异 — 两锚实证
- [ ] Subtask 2.4: 🔄 重构 — 素材构造收敛

#### TDD 循环 B：state/Result/投影扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `TestSpBlmGraphTopology`（R1-P3 目标订正：sp_blm_graph 图链路用例在本文件——节点适配器直写断言：六子步骤后中间 state chain_records 递增/终态恰 8 条；投影 chain_summary == 末条 final_answer[:200] 值级断言+**空回退分支断言**（R1-F12））+ 用例测试扩展（_assemble_result 读 chain_records 默认 () 零破坏） |
| 🟢 绿 | `SpBlmState` 加 chain_records 键（total=False）+ **`sp_blm_graph.py` 三类节点适配器返回 dict 各加 `"chain_records": service.project_chain_records(state["plan_id"])` 直写行**（R1-F1③——degraded_steps/timeline 同构、八节点对称、`BlmPlanningServicePort` 协议同步追加第七方法）+ `BlmPlanningResult` 加默认尾字段 `chain_records: tuple[ChainRecord, ...] = ()` + `_assemble_result` 读 `final_state.get("chain_records")` + 投影分支 chain_summary 取值源改末条思维链（空回退 `(first_conclusion or "")[:200]`） |
| 🟡 变异 | 投影改回 first_conclusion→值级断言红；Result 字段删除→类型断言红；**适配器直写行删除→终态 8 条断言红（回传通道活着）**；还原→绿 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 2.5: 🔴 红 — 投影/Result 失败测试
- [ ] Subtask 2.6: 🟢 绿 — 三扩展点最小代码
- [ ] Subtask 2.7: 🟡 变异 — 两锚实证
- [ ] Subtask 2.8: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] 三方法挂接（run_state 累积+投影方法）+ 适配器直写 + state/Result/投影扩展完成（R1-F1 四位面）
- [ ] 尾参 None 等价性守护测试在位（现状回归护栏）
- [ ] 既有 blm_planning 测试零适配通过
- [ ] 覆盖率≥85%

---

### Task 3: 追溯用例 + 组合根 + CLI

**关联 AC:** AC-2 / AC-5 / AC-6

#### TDD 循环 A：用例与组合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_blm_chain_trace_use_case.py`（透传/空清单/242 守卫（plan_id 非 UUID 构造真实 EntityValidationError——6-3 R1-F18 统一形态））+ 契约测试 `tests/contracts/test_port_contract_chain_of_thought.py`（注册/spec 元数据/resolve/注入链/版本 v 前缀） |
| 🟢 绿 | `src/application/use_cases/get_blm_chain_trace.py`（GetBlmChainTraceUseCase——薄透传+UUID 守卫）+ 组合根三注册块（chain_of_thought_archive_service SINGLETON **双注入** strategic_archive_service+object_storage（R1-F6）/ blm_chain_trace_use_case / blm_planning_service lambda 增量注入+version v1.1.0——**纯新增行+恰 1 行版本变更**（R1-F11 口径）） |
| 🟡 变异 | 注册名漂移→resolve 红；注入实参删除→getsource 断言红；还原→绿 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 3.1: 🔴 红 — 用例+契约失败测试
- [ ] Subtask 3.2: 🟢 绿 — 用例+注册最小代码
- [ ] Subtask 3.3: 🟡 变异 — 两锚实证
- [ ] Subtask 3.4: 🔄 重构 — 优化代码

#### TDD 循环 B：CLI 子命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（chain-query：正常输出 to_display 每条五段+归档计数/空清单 exit 0/非法 plan_id → stderr `[EXCEPTION_242]` 形态/blm-plan 汇总行**三段式**「成功 N/失败 M/预期 8」（R2-F8）） |
| 🟢 绿 | `src/entrypoints/agent_cli.py` 增 chain-query 子命令（argparse 扁平——6-3 checkpoint-create 先例；`--plan-id`/`--include-blob` 两参数）+ blm-plan `_print_blm_progress` 尾部思维链计数行 |
| 🟡 变异 | 输出漂移→断言红；还原→绿 |
| 🔄 重构 | 优化代码 |

- [ ] Subtask 3.5: 🔴 红 — CLI 失败测试
- [ ] Subtask 3.6: 🟢 绿 — 子命令+汇总行最小代码
- [ ] Subtask 3.7: 🟡 变异 — 输出锚实证
- [ ] Subtask 3.8: 🔄 重构 — 优化代码

**完成标准/Definition of Done:**
- [ ] 用例+组合根+CLI 全部接线
- [ ] 组合根 diff = 纯新增+恰 1 行版本变更（实证）
- [ ] 覆盖率≥85%

---

### Task 4: 契约守护与 6-1/6-2/6-3/5-3 回归面

**关联 AC:** AC-6

- [ ] Subtask 4.1: 契约测试扩展守护（test_event_channel_mapping_blm_planning.py 零修改复跑——四文件零 CheckpointReached 引用断言天然通过实证；EVIDENCE_PACKAGE 构造位唯一性断言——架构验证器 C 的前置红测归 Task 6，此处登记接口）
- [ ] Subtask 4.2: 四文件零 diff 验证（event_channels.yaml / channel_router.py / _code_ranges.py / exception_handlers.py——git diff 空输出留档）
- [ ] Subtask 4.3: 回归面全量复跑（6-1 验收/集成 + 6-2 验收/集成 + 6-3 验收/集成 + 5-3 agent_workflow 测试面——零适配假设实证：默认尾字段/尾参可选/快照零新键三护栏；**若失配即证明零适配假设破产，回对应 Task 修护栏（而非适配测试——6-2 R1-2 教训）**）
- [ ] Subtask 4.4: 三条红线 grep 自查（提交前零输出留档）

**完成标准/Definition of Done:**
- [ ] 既有测试资产全量零修改通过
- [ ] 四文件零 diff 实证
- [ ] 红线自查零输出

---

### Task 5: 集成测试——真实链五场景

**关联 AC:** AC-3 / AC-5 / AC-7

- [ ] Subtask 5.1: 场景① 真实链全流程（Redis/PG/Qdrant/MinIO 四真实 + Fake LLM/Fake Embedding 双豁免——6-3 装配形态移植）：一次 run 8 条思维链全量归档 round-trip（PG 恰 8 行/Qdrant 点可搜/L4 blob 解引用 JSON==期望五字段/WORM retention 验证/chain_records 8 条 archived=True）
- [ ] Subtask 5.2: 场景② 追溯+blob 深度解引用（query 面查回 8 条排序正确/include_blob=True L4 等值/ArchiveCreated outbox 落行断言——6-3 集成② 真实 publisher 装配先例；event_type 过滤防自捕）
- [ ] Subtask 5.3: 场景③ 并发 10（asyncio.gather 10 独立素材归档——**每协程 session_context() 独立 scope**（R1-F7——gather 共享单 AsyncSession 并发使用不被 SQLAlchemy 支持）；**10 素材共享一个场景专属 plan_id**（count==10 按该 plan_id+archive_type 过滤——R1-F7 消歧）；全 archived=True）
- [ ] Subtask 5.4: 场景④ 性能采样（组装窗口 20 轮 P95<50ms——素材固定**直调纯函数 `compose_step_chain`**（R1-F13——零 I/O 零 LLM；**采样素材型=六子步骤型**钦定）；采样 task 文本固定；口径差声明落 docstring）
- [ ] Subtask 5.5: 场景⑤ 6-1/6-2/6-3 回归面（集成层既有用例复跑）
- [ ] Subtask 5.6: 清理闭环（PG 档案行按 plan_id 删除+Qdrant payload.archive_id 匹配清点+MinIO bypass_governance 清对象+**outbox 行**（ArchiveCreated 按 event_type+plan_id 双通道 DELETE——R3-F3）——teardown 链四步独立 try/except；四键族跑前跑后净增 0 断言——6-3 R1-F1 教训直接继承）

**完成标准/Definition of Done:**
- [ ] 五场景全绿
- [ ] 清理闭环实证（净增 0）
- [ ] 环境事实沉淀（如有新发现——6-3 先例）

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-1 / AC-3 / AC-6

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_json_chain_of_thought.py`（**epics L2218 钦定名**——注意与既有文件同名冲突检查：tests/unit/architecture/ 现无同名（四 Agent 调研实证零命中）；若冲突补 __init__.py 包链唯一化——6-3 先例）
- [ ] Subtask 6.2: 验证器 A——EVIDENCE_PACKAGE 唯一构造位（全 src 构造点扫描：`ArchiveType.EVIDENCE_PACKAGE` 仅出现于 chain_of_thought_archive_service.py 一处构造 + 枚举定义处——激活唯一性守护）
- [ ] Subtask 6.3: 验证器 B——服务落位（ChainOfThoughtArchiveService 定义唯一/端口落位 application/ports/实现落位 application/services/组合根注册/禁本地 Protocol——`grep Protocol src/application/services/chain_of_thought_archive_service.py` 零输出）
- [ ] Subtask 6.4: 验证器 C——归档服务零触碰（strategic_archive_service.py 本 Story 零 diff——AST 级或 git diff 断言）+ strategic_archive.py 实体零 diff
- [ ] Subtask 6.5: 验证器 D——BLM 挂接点（三方法挂接段存在性+尾参可选注入+**回传通道三件套存在性**（R1-F1：_PlanRunState.chain_records 字段+project_chain_records 协议方法+sp_blm_graph 三类节点适配器 chain_records 直写行——`grep "chain_records" src/infrastructure/agent_orch/graphs/sp_blm_graph.py` ≥3 处）+chain_records 不进快照 state_data 键（to_state_data 键清单断言——七键恒定）+不进事件 payload（投影白名单五键恒定））
- [ ] Subtask 6.6: 验证器 E——负向契约断言面零修改复跑（四文件零 CheckpointReached——test_event_channel_mapping_blm_planning.py 既有两用例）
- [ ] Subtask 6.7: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 五验证器（A~E）全部通过
- [ ] 任何违规都会导致测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1~AC-7（收尾全量）

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 完善 `test_acceptance_json_chain_of_thought.feature` 中的收尾验收场景（S13——src 与四测试目录完成清单逐项确认） |
| 🟢 绿 | 编写 `test_acceptance_json_chain_of_thought.py` 的 S13 BDD 步骤实现（交付件存在性断言——文件级+关键符号级） |
| 🟡 变异 | 交付件清单删条目→红；还原→绿 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 7.1: 13 场景全绿实证（装配回灌——6-3 验收装配形态：SessionContext/Qdrant collection 确保/MinIO bucket 自愈/Fake 双豁免/双装配防泄漏 dispose 前置）
- [ ] Subtask 7.2: pytestmark/xdist_group 完整性复核（组串行真正生效——6-3 pytestmark 丢失修复教训）
- [ ] Subtask 7.3: 四目录全量回归（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`）+ ruff + mypy
- [ ] Subtask 7.4: 专项覆盖率（chain_of_thought_archive_service ≥85%（application 门禁）/整体 ≥80%）+ 三红线 grep + 组合根 diff（纯新增+恰 1 行版本变更——R1-F11 口径）终验
- [ ] Subtask 7.5: 台账终态（deferred-work 注记落档/sprint-status.yaml 状态流转 review）

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过（13/13）
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（reliable 单通道——ArchiveCreated 既有登记复用）+ 可追溯决策原则（architecture.md L132：所有决策可追溯至原始数据和假设，7 年审计追踪）
- **设计约束:** 领域层零依赖（import-linter 强制；本 Story domain 预期零改动）；`@dataclass(frozen=True)` 不可变 VO 复用；服务经端口组合注入（R2——ChainOfThoughtArchiveService 注入 StrategicArchiveService）
- **接口治理:** 统一端口注册（PortSpec：name/version/interface/impl/module/lifetime/owner/compatibility/tags）、Registry/Resolver/ContractGate、组合根唯一装配、契约优先
- **技术栈:** Python 3.11+ / LangGraph（SpBlmState 加键）/ PostgreSQL（L2）/ Qdrant（L3）/ MinIO WORM（L4，GOVERNANCE 模式 retention 2555 天）/ pytest-bdd
- **关键架构条款:** §17.4 AGENT 架构注记 L2992-2994（思维链 ChainOfThought 五字段 VO + to_display 五段展示随 5-3 交付——6-4 持久化消费）/ or.md 五.5 L480（五段格式钦定）/ prd FR-SP-04 L1871

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | 范围边界：6-4 落 **BLM 面**思维链规范化（6-1 边界表 L37 钦定「Story 6-4（BLM 面输出规范化）」）+ 战略档案库归档 + 决策追溯查询面（用例+CLI）。**不含**：5-3 任务级思维链（SingleAgentWorkflow chain state 键）归档——归 5.7 Phoenix 追踪消费立项时的后续 Story（deferred 登记）；深度思考多路径推演（FR-AC-14 P1——并行多条思维链）；REST 查询面（归后续 Story）；6-7 溯源树展示（消费方） | epics L2013 依赖钦定（6.4 依赖 6.1）+ 6-1 边界表 L37 + chain_of_thought.py:4-5「供 6-4 持久化」+ prd FR-SP-04(P0) vs FR-AC-14(P1) 优先级 |
| **OD-2** | **确定性组装（零新增 LLM 调用）**：五字段从既有步骤执行素材（工具轨迹/检索证据/结构化输出/降级信息/语义配置）规则组装——不经 ChainOfThoughtSchema、不调 LLM。与 5-3 任务级终局合成（LLM 单次调用 :373-375）形态差异声明：5-3 是任务级一次合成；BLM 面 8 步若各加一次 LLM 调用则 token 成本翻倍且 epic「生成延迟 P95<50ms」物理不可达（含 LLM 调用秒级延迟）。**测试红利**：组装面零 Fake 依赖（素材确定性），Fake LLM 仅服务既有 8 步结构化调用 | epic 性能行 P95<50ms 物理可达性 + 6-1 DC-7/6-2 OD-3/6-3 OD-6 口径差三先例 + 成本（8×额外调用/run）+ deferred L192（ChainOfThoughtSchema 演进触发条件不满足——零触发注记） |
| **OD-3** | **每步粒度（8 条/run）**：or.md 五.5「SP/BP 各个阶段，输出 JSON 思维链」（:480——R1-P3 订正原文拼写）的「阶段」在 6-1/6-2 实现形态下落位为**步骤粒度**（STAGE_VALUE_DOMAIN 八值各一条——performance_gap/六子步骤/synthesis）。归档时机=步骤方法内（快照写之后）——**崩溃一致性**：run 中断时已完成步骤的思维链已归档（失败 run 的决策过程恰是审计最需要的）；run 末批量归档会丢中断 run 的推理证据 | or.md 阶段语义 + 6-2 步骤化实现形态 + 崩溃一致性权衡 + 6-3 ③步内同步归档先例 |
| **OD-4** | 归档通道**零改动复用** `StrategicArchiveService.archive_plan`：`archive_type=ArchiveType.EVIDENCE_PACKAGE`（3-10 枚举**首激活**——全 src 零使用实证）、`plan_type="SP"`（6-3 R6-1 同款：推理快照属 SP 编制过程语境——"chain" 值会被 archive_plan 入口双道校验拒绝且扩枚举=契约面爆炸）、载荷映射冻结（decision_basis kind+stage 锚——R8-F3 同构；evidence_blob 结构化 JSON——DC-2「存储用结构化、展示用标签」，to_display 不落 blob）。L3 embedding 经 Fake Embedding 豁免（验收/集成）与真实链（生产） | archive_plan 现状（:71-296 七参数+双道校验）+ 6-3 ③步载荷先例 + DC-2 钦定 + 最小契约变更原则 |
| **OD-5** | **归档失败降级不阻断**：思维链是可观测面非流程面——284/445 捕获后该步 archived=False（或 chain 缺席）台账 + warning 日志 + 流程继续（领域产物/快照/事件不受影响）。epic「思维链存储成功率 100%」口径重读：正常路径 N 归档 N 可读回 + 失败零静默（台账可见）——非「失败即中断」字面（中断会因观测面失败丢弃已产出的领域结果——错误权衡）。验收/集成不含归档失败注入（no-mock 红线——6-3 0.8⑧ 同款裁定，单测层 AsyncMock 承载） | 可观测面/流程面职责分离 + 6-1 快照写容错同语义（:701-702）+ 6-3 0.8⑧ 先例 |
| **OD-6** | **零新事件 + 零新异常**：归档事实经既有 `ArchiveCreated`（archive_plan 内部发布 :270-294，双登记在位——6-3 集成②断言先例）承载；异常复用 445（组装终态门禁——5-3 :386-393 捕获改写同款）/284（归档层透传）/242（VO 校验+CLI 守卫）。epic 6.4 文本未钦定思维链事件/异常；planning 段 485-489 预留（6-6）不侵占 | YAGNI + 既有资产复用优先（checklist 红线）+ `_code_ranges.py:189` 预留声明 + 事件双登记纪律（新事件须 yaml+router 双更新——本 Story 零新增即零 diff） |
| **OD-7** | 测试文件命名（禁故事编号后缀）：unit/architecture 用 epics 钦定 `test_json_chain_of_thought.py`（**epics L2218 一致**；同名冲突检查+包链预案）；integration `test_integration_chain_of_thought.py`（**对 epics L2219 钦定名 `test_json_chain_of_thought_integration.py` 的显式偏离**——仓规 tests/integration/ 全目录 test_integration_* 惯例，6-3 OD-8 同款拆分声明）；acceptance `test_acceptance_json_chain_of_thought.feature/.py`；服务单测 `test_chain_of_thought_archive_service.py`；用例单测 `test_blm_chain_trace_use_case.py` | epics L2218-2219 钦定名（半采半离）+ 记忆「禁止故事编号命名文件」+ 6-3 OD-7/OD-8 双先例 |
| **OD-8** | **快照面零改动**：思维链不进 Redis state_data（6-2 per-step 七键契约/latest 七键/6-3 完整形态 13 键全部零触碰）——思维链的持久化归宿是战略档案库（AC 钦定「存储至战略档案库」），Redis 快照是流程状态面非推理证据面；图 state `chain_records` 键仅内存流转（LangGraph 内存图无序列化需求——快照写不读该键）。**6-2「structured_output 键恒在」契约零破坏**；读侧判别不受影响 | AC「存储至战略档案库」单一归宿 + 6-2 端口契约冻结面 + 双轨制先例（6-3 OD-3 键族职责分离——流程状态面 vs 审批恢复面 vs 推理证据面三分） |
| **OD-9** | 扩展形态**四**钦定（R1-F1 扩展）：① `SpBlmState` 加 chain_records 键（TypedDict `total=False` 加键零破坏——6-1 交付形态；**写侧经三件套，加键本身不产生写入**）；①′ **回传通道三件套**：`_PlanRunState.chain_records` 累积（degraded_steps/timeline 同构第三累积位）+ `BlmPlanningServicePort` 追加 `project_chain_records` 第七方法（既有六方法零改动）+ `sp_blm_graph.py` 三类节点适配器返回 dict 各加直写行（八节点对称——schemas.py:43-45 键覆盖语义）；② `BlmPlanningResult` 加默认尾字段 `chain_records: tuple[ChainRecord, ...] = ()`（零破坏——6-3 R3-2 先例）；③ AgentDecided 投影 chain_summary 取值源真实化（SpBlmGraph 分支 `first_conclusion` → 末条思维链 final_answer[:200]——SingleAgentWorkflow :254 同款取值语义；**空回退** `(first_conclusion or "")[:200]`（R1-F12）；五键白名单结构零变化，VO 仍禁入 payload——DC-11 纪律维持） | 6-1 state/投影形态 + degraded_steps/timeline 投影同构先例（sp_blm_graph.py:46-47/63-64/79-80）+ 6-3 R3-2 默认尾字段先例 + DC-11 投影纪律 + 「输出包含思维链」的事件面体现（最小改动大语义） |
| **OD-10** | 性能口径差声明：**组装窗口 P95<50ms** = 素材就绪→VO 构造完成（纯内存——OD-2 确定性组装使指标物理可达）；归档 I/O（L2/L3/L4）与 LLM 延迟显式出栈独立计量（不进 P95 口径——epic 未预见组装/归档/LLM 三段分离）；成功率口径见 OD-5；并发 10=asyncio.gather 独立素材归档。口径差落测试 docstring | 6-1 DC-7/6-2 OD-3/6-3 OD-6 三先例 + epic 指标物理可达性论证 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/                                    = 预期零改动（Task 0.8 终裁——VO 复用；异常零新增）
├── application/
│   ├── ports/chain_of_thought_archive.py      ★ 新建（Protocol+三 dataclass+CHAIN_ARCHIVE_KIND——Task 1）
│   ├── services/chain_of_thought_archive_service.py ★ 新建（组装+归档+追溯+纯函数 compose_step_chain——Task 1）
│   ├── ports/blm_planning.py                  ▲ BlmPlanningResult 加默认尾字段+协议追加 project_chain_records 第七方法（Task 2——R1-F1）
│   ├── services/blm_planning_service.py       ▲ 尾参可选注入+_PlanRunState 加累积位+project_chain_records 投影+三方法挂接段（Task 2——既有语句零改动）
│   └── use_cases/get_blm_chain_trace.py       ★ 新建（追溯用例——Task 3）
├── infrastructure/
│   └── agent_orch/
│       ├── graphs/sp_blm_graph.py             ▲ 三类节点适配器返回 dict 各加 chain_records 直写行（Task 2——R1-F1③，degraded_steps/timeline 同构）
│       ├── schemas.py                         ▲ SpBlmState 加 chain_records 键（Task 2）
│       └── langgraph_engine.py                ▲ SpBlmGraph 投影 chain_summary 取值源+空回退（Task 2——五键白名单结构零变化）
├── entrypoints/agent_cli.py                   ▲ chain-query 子命令+blm-plan 汇总行（Task 3）
└── composition_root.py                        ▲ 三注册块+blm_planning_service 增量注入+version v1.1.0（Task 3——纯新增+恰 1 行版本变更）

tests/
├── unit/
│   ├── application/test_chain_of_thought_archive_service.py ★ 新建（Task 1）
│   ├── application/test_blm_planning_service.py          ▲ 挂接用例族+投影值级断言+节点适配器直写扩展（Task 2——TestSpBlmGraphTopology :1005-1027 先例，R1-P3 目标订正）
│   ├── application/use_cases/test_blm_chain_trace_use_case.py ★ 新建（Task 3）
│   ├── architecture/test_json_chain_of_thought.py        ★ 新建（Task 6，epics 钦定名）
│   └── interfaces/cli/test_agent_cli.py                  ▲ chain-query 用例扩展（Task 3）
├── integration/test_integration_chain_of_thought.py      ★ 新建（Task 5，OD-7）
├── contracts/test_port_contract_chain_of_thought.py      ★ 新建（Task 1/4）
└── acceptance/
    ├── test_acceptance_json_chain_of_thought.feature/.py ★ 新建（Task 0/7，13 场景）
    └── （6-1/6-2/6-3/5-3 既有验收文件零修改——Task 4 回归验证）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 处置注记（Task 0/7——L192 零触发+任务级归档新登记）
_bmad-output/implementation-artifacts/sprint-status.yaml ▲ 状态流转（Task 7）
```

（▲ 修改 / ★ 新建 / = 零改动 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——四 Agent 并行调研+主会话亲验双重核验；行号基准 HEAD@d27cdc6e，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| `ChainOfThought` VO | `src/domain/value_objects/chain_of_thought.py:33-49` | 五字段 frozen dataclass（input_summary: str/reflection: str/tools_used: **tuple[str, ...]**（空元组合法）/constraints_check: str/final_answer: str）；`__post_init__` :51-81 校验抛 242（`_TEXT_FIELDS` :30）；`to_display()` :83-103 五段 XML（空轨迹"(none)" :96）；docstring :4-5「供 6-4 持久化」钦定；**零改动复用**；不在 value_objects/__init__.py 导出（消费方全路径 import 先例） |
| `ChainOfThoughtValidationError` | `src/domain/exceptions/agent_exceptions.py:251-270` | EXCEPTION_445（agent 域）；context 携 missing_fields；5-3 捕获改写先例 agent_workflow_service.py:386-393——**复用零改动** |
| `ArchiveType.EVIDENCE_PACKAGE` | `src/domain/entities/strategic_archive.py:32,38` | `"evidence_package"`——3-10 定义后**全 src 零使用**（本 Story 首激活）；实体不变量 :124-129：EVIDENCE_PACKAGE 不要求 plan_id（BLM 场景携带 plan_id 合法） |
| `StrategicArchiveService.archive_plan` | `src/application/services/strategic_archive_service.py:71-296` | 七参数（plan_id/plan_type/archive_type/assumptions/decision_basis/execution_deviation/evidence_blob: bytes）；五步序 L2 强制 :122-127→L3 降级 :139-187（embedding :148+upsert collection="strategic_archive"）→L4 强制 :189-210（bucket_type="archive-evidence" retention 2555）→L5 降级 :214-241→引用回写 :243-268→ArchiveCreated :270-294（发布失败抛 284）；**零改动复用** |
| 6-3 归档调用先例 | `src/application/services/checkpoint_service.py:222-257` | archive_plan 参数映射冻结形态（plan_type="SP" **:227**/载荷映射 **:233-238**/284 包装 :240-257——R1-P3 行号订正）——6-4 载荷映射的形态模板（**6-3 未传 archive_type 落库为默认 ASSUMPTION——6-4 必须显式传 `archive_type=ArchiveType.EVIDENCE_PACKAGE` 枚举成员**（R1-P3 补注：裸 str 被实体 validate :90-94 拒绝）；异常处置按 OD-5 改降级非包装阻断） |
| `ArchiveQuery` 查询面 | `src/domain/ports/archive_repository.py:38-103` | frozen Query Object（plan_id/archive_type/...组合+分页）——追溯读侧零改动复用（`query_archive` strategic_archive_service.py:315） |
| `BlmPlanningService` 三执行方法 | `src/application/services/blm_planning_service.py` | `run_performance_gap_analysis` :231-298（重跑 482 :241-246/成功四字段 :275-284/降级信封 :286-294/record_step+快照 :296-297）；`run_insight_step` :304-385（Schema 分派 :341/structured_output :364/per-step→latest :383-384）；`synthesize_insights` :391-449（**早退分支 :410-412** effective_context None 不触发挂接——R1-F15）——**挂接点=各方法末尾快照写之后、return 之前**（三方法返回 VO——累积进 `_PlanRunState` :94-129 非返回值，`_ensure_run_state` :732 键控隔离）；构造器八必填+base_config 可选尾参 :135-146（第九尾参注入位——本类可选尾参先例）；`project_timeline`/`project_degraded_steps` :455-465 投影先例 |
| 工具执行轨迹源 | `src/application/services/blm_planning_service.py:559-608` | `_execute_candidate_tools`（449/380 步级捕获→直接推理续行）——**返回三元组 `(输出摘要, 工具面降级原因, tool_slug)`**（:560-572 docstring 钦定；`tool_slug = tool.slug or tool.name` :600 首个成功即返回 :601 **每步至多 1 项无版本后缀**——R1-F2 定谳；白名单空/全失败 `("", "", "")` :608） |
| `InsightStepResult.tool_used` | `src/domain/value_objects/blm_phases.py:239` | **单数 str**（"实际执行的工具 slug（缺失回落显示名）"）——与 ChainOfThought.tools_used（tuple）**双单数形态断裂登记**（0.8②：执行轨迹第三返回值同为单数——素材从执行轨迹取包装 `(tool_slug,)`，非信封单值字段，**不得假设清单形态**） |
| 六类型化 Schema | `src/application/services/blm_planning_prompts.py:53-128` | 六 Schema+GapAnalysisSchema :31-37+InsightSynthesisSchema :125-128——final_answer 素材源（structured_output=model_dump :364）；StepSemanticConfig :136-157（display_name/role_prefix——input_summary 素材） |
| `SpBlmState` | `src/infrastructure/agent_orch/schemas.py:84-110` | TypedDict total=False 现九键（:102-110）——加 chain_records 键零破坏（0.8⑧；**写侧经三件套，:43-45 注释钦定纯 TypedDict 无 reducer 键覆盖语义**） |
| **`sp_blm_graph` 图工厂**（R1-F1 新增锚点） | `src/infrastructure/agent_orch/graphs/sp_blm_graph.py:29-91` | `build_sp_blm_graph(service: BlmPlanningServicePort)` :29；三类节点适配器返回 dict——`_performance_gap_node` :44-48 / `_insight_node` :61-65 / `_synthesize_node` :77-81（`degraded_steps`/`timeline` 经 `service.project_*` 直写全量先例 :46-47/:63-64/:79-80；`prior_outputs` 组装 :55-58）；**chain_records 直写行挂接位=三返回 dict 各加一行**（八节点对称） |
| **`BlmPlanningServicePort` 协议**（R1-F1 新增锚点） | `src/application/ports/blm_planning.py:117-199` | 现六方法（build_planning_context :126/run_performance_gap_analysis :146/run_insight_step :157/synthesize_insights :179/project_timeline :193/project_degraded_steps :197）——**追加 `project_chain_records` 第七方法**（增量追加非语义变更）；`BlmPlanningContext` :69-90（task :85 三方法可达） |
| `BlmPlanningResult` | `src/application/ports/blm_planning.py:93-114` | **七**字段 DTO（:108-114——R1-P3 计数订正）——加默认尾字段 chain_records（OD-9②）；`_assemble_result` 组装点 run_blm_planning.py:185-193（终态直读——final_state.get("chain_records") 扩展） |
| AgentDecided 投影 | `src/infrastructure/agent_orch/langgraph_engine.py:258-279` | SpBlmGraph 分支五键纯标量白名单——chain_summary 现值 `(first_conclusion or "")[:200]` :270（synthesis 首结论）→ 改末条思维链 final_answer[:200]（OD-9③；SingleAgentWorkflow :254 取值语义同款）；confidence 显式 0.0 维持（DC-11） |
| 负向契约断言面 | `tests/contracts/test_event_channel_mapping_blm_planning.py:88-104,126-134` | 四文件零 CheckpointReached 引用断言——6-4 改 blm_planning_service.py 不引入该引用即**零修改通过**（OD-4/AC-6 守护依据） |
| `ArchiveCreated` 双登记 | `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py`（3-10 登记；6-3 集成②已断言落行） | 归档事件既有通道——**零 diff 复用**（OD-6）；outbox 断言键 `payload->'payload'->>'archive_id'`（6-3 集成②先例） |
| 组合根注册 | `src/composition_root.py` | blm_planning_service :1580-1598（SINGLETON 八依赖——增量注入+version v1.0.0→v1.1.0，agent_engine :1555-1574 先例）；strategic_archive_service :2209-2227（注入源）；新注册块相邻位（checkpoint_service :2287-2302 形态模板）；契约测试 getsource 断言面 :89-98（test_port_contract_blm_planning.py——增量注入不破坏既有断言，0.8⑥ 亲验） |
| CLI 先例 | `src/entrypoints/agent_cli.py` | blm-plan :288-315/:683-722（汇总打印 _print_blm_progress :655-681——尾部计数行扩展位）；checkpoint-create :320-371（argparse 扁平+守卫形态——chain-query 模板；242 统一形态 R1-F18 先例） |
| 验收装配先例 | `tests/acceptance/test_acceptance_checkpoint_snapshot.py` | 三件套+teardown 六步链+_cleanup_archive_residues :346-427（PG 行/Qdrant 点/MinIO WORM 清理——**6-4 直接移植**）+Fake LLM/Embedding 双豁免+SessionContext+bucket 自愈——6-4 装配参照（Fake LLM 复用 6-2 `_make_fake_llm` 六 Schema 身份分派形态——6-4 零新增 Schema 面） |
| 集成真实链先例 | `tests/integration/test_integration_checkpoint.py` | 四真实+双豁免+记录壳键清理（R1-F1）+性能采样数学口径——场景①④⑤ 形态模板 |

### 锚定义务清单（deferred-work 台账——Task 0.9 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-4 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L192（R1-DF3） | ChainOfThoughtSchema.input_summary 必填与「系统覆写」语义冗余——核销触发「下次 Schema 演进」 | **零触发注记**：6-4 确定性组装不经 ChainOfThoughtSchema（OD-2——Schema 是 LLM 终局合成专用，5-3 资产）；Schema 零触碰，留项维持 |
| 2 | 新登记 | 5-3 任务级思维链（SingleAgentWorkflow chain state 键→AgentWorkflowResult.chain）无归档通道 | **新留项登记**：归 5.7 Phoenix 追踪消费立项时的后续 Story（OD-1 边界声明；6-4 只落 BLM 面） |
| 3 | L170 | 事件消费基建四件（归档事件消费方） | 预判**顺延**：6-4 是 ArchiveCreated 生产路径叠加非消费方（5-3/6-3 同款裁定）——注记落档 |
| 4 | L132 | 检索-压缩循环（6-3 已核销主链三组件） | 无关（本 Story 不触碰 note/compress 链）——零处置 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-3 Checkpoint 快照创建](./6-3-checkpoint-snapshot-creation.md)（五轮文档审查+五轮代码审查收敛 done）+ Story 6-1/6-2（同款双五轮）

**关键学习/Key Learnings:**
- **Epic 1/3 骨架资产复用（6-3 头号教训）**：立 Story 时钦定「新建」前必须全仓 grep 同语义类型——本 Story 已执行：ChainOfThought（5-3）/ArchiveType.EVIDENCE_PACKAGE（3-10 定义零使用）/ArchiveQuery（3-10）全部复用激活，**唯一新建面=组装+归档编排服务**（应用层新服务是合理增量——既有资产无此职责）
- **属性形态断裂族**（6-1 两犯+6-3 R1 再证——本 Story 高危点已前置登记）：`InsightStepResult.tool_used` 是**单数 str**（blm_phases.py:239）**且执行轨迹第三返回值同为单数**（R1-F2 实测）而 `ChainOfThought.tools_used` 是 **tuple[str, ...]**——素材采集从执行轨迹取包装 `(tool_slug,)`（0.8②——**双单数形态，不得假设清单**）；`structured_output` 是 dict（非 str）；**JSON round-trip tuple↔list 断裂**（R1-F9——读回重构 VO 必须 `tuple()` 归一否则 242）；`CompressedContext.persistent_note_ref` str vs UUID 形态先例知悉（本 Story 无涉）；`ArchiveType.EVIDENCE_PACKAGE` 枚举成员（非裸 str——archive_plan 入参传枚举，实体 validate :90-94 拒绝裸 str）
- **断言判别力**（6-3 R1-F6/R8 值级断言教训）：组装映射断言=独立构造期望轨迹（非 Fake 回声/非读回值自比）；投影 chain_summary 值级断言（非仅类型级）；归档载荷 blob 解引用与期望 dict 等值（非自证）
- **no-mock 红线互斥裁定**（6-2 R3-4/6-3 0.8⑧）：归档失败注入（284）与组装失败（445）归单测层 AsyncMock 承载——验收/集成 Edge Cases 不含归档写失败容错
- **键清理闭环**（6-3 R1-F1 实测泄漏 1117+ 键教训）：PG 档案行/Qdrant 点/MinIO WORM 对象三面清理链（teardown 各步独立 try/except）+ 跑前跑后净增 0 断言——集成/验收双侧（记录壳形态视 6-4 归档调用面而定：挂接点内归档无独立键族，清理按 plan_id 过滤档案行即可）
- **TDD Task 边界**（6-2 R1-2）：挂接扩展（Task 2）与回归验证（Task 4.3）分离依据=三护栏（尾参可选 None/默认尾字段/快照零新键）向后兼容假设——失配即回 Task 2 修护栏（而非适配测试）
- **BDD 三件套+性能口径**（6-1/6-2/6-3 三连先例）：模块级 event_loop+context dict+`_run_async`；teardown 链断言失败也执行；P95 口径差声明落 docstring（OD-10）；采样 xdist_group blm-planning-perf 组复用；pytestmark 完整性复核（6-3 丢失修复教训——Task 7.2 专项）
- **红线三处漏网教训**（6-1 R5）：全程零抑制注释+提交信息禁 AI 署名+三条 grep 自查

**应用到本故事/Applied to This Story:**
- [ ] ChainOfThought/EVIDENCE_PACKAGE/ArchiveQuery/445/284/242 全复用激活（Task 0.1 实证复跑+Task 1 实现）
- [ ] tool_used 单数 vs tools_used tuple 形态断裂在 0.8② 亲验登记+素材采集点钦定
- [ ] 组装映射/投影/载荷三类断言值级独立构造（S2/S4/S5+单测）
- [ ] 归档/组装失败注入落位单测层（0.8/AC-4 钦定）
- [ ] 三面清理链+净增 0 断言（Task 5.6）
- [ ] 三护栏+失配回修闭环（Task 4.3）
- [ ] 性能口径 OD-10+xdist_group 复用+pytestmark 复核（Task 7.2）
- [ ] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep（Task 4.4/7.4）

### 其他约束速查

- **风险集中登记**：①最大回归风险 = blm_planning_service.py 挂接（6-1/6-2 核心资产——三护栏+既有测试零适配实证）；②契约风险 = 组合根增量注入破坏既有 getsource 断言（0.8⑥ 亲验）；③投影风险 = chain_summary 取值源变更（值级断言+五键白名单恒定双锚）；④清理风险 = 档案三面残留（6-3 R1-F1 同族——teardown 链+净增 0）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type:ignore；提交信息禁 AI 署名
- **覆盖率**：整体≥80% / application≥85%（主改动层）/ domain≥90% 维持 / 集成≥75%
- **验收/集成禁 mock**（真实服务优先+`pytest.skip()` 动态跳过；Fake LLM+Fake Embedding 双豁免——外部 SaaS）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-03 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Instructions** | `.claude/skills/bmad-create-story/discover-inputs.md` + `checklist.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L2183-2222 Story 6.4 定义） |
| **架构文档** | `docs/architecture/architecture.md`（§17.4 L2992-2994 思维链注记） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-3-checkpoint-snapshot-creation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **调研底座** | 四 Agent 并行调研（A=ChainOfThought VO 与 5-3 工作流 / B=BLM 流程 6-1~6-3 现状 / C=战略档案库体系 / D=测试模板与工程规范）+ 主会话亲验（5-3 边界 L37/or.md 五.5/prd FR-SP-04/deferred-work/6-3 全文/投影与 tool_used 形态）——行号基准 HEAD@d27cdc6e |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` L2183-2222 提取
- [x] 架构约束从 `architecture.md` 提取（§17.4 注记/可追溯决策原则）
- [x] 前一个故事学习经验整合（6-1/6-2/6-3 双五轮审查教训）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（四冻结：组装映射/归档载荷/端口契约/异常复用）
- [x] 项目结构对齐统一规范
- [x] 四 Agent 并行调研+主会话亲验双重核验（R1~R6 设计规则落位：R1 零新建基础端口全复用/R2 组合注入/R3 零 infra 新增/R4 CLI 入口）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-4-json-chain-of-thought-output.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/chain_of_thought_archive.py` - 端口+三 dataclass+常量（Task 1）
- `src/application/services/chain_of_thought_archive_service.py` - 组装+归档+追溯服务（Task 1）
- `src/application/use_cases/get_blm_chain_trace.py` - 追溯用例（Task 3）
- `tests/unit/application/test_chain_of_thought_archive_service.py` - 服务单测（Task 1）
- `tests/unit/application/use_cases/test_blm_chain_trace_use_case.py` - 用例单测（Task 3）
- `tests/unit/architecture/test_json_chain_of_thought.py` - 架构五验证器（Task 6，epics 钦定名）
- `tests/integration/test_integration_chain_of_thought.py` - 集成五场景（Task 5，OD-7）
- `tests/contracts/test_port_contract_chain_of_thought.py` - 端口契约（Task 1/4）
- `tests/acceptance/test_acceptance_json_chain_of_thought.feature` - Gherkin 13 场景（Task 0）
- `tests/acceptance/test_acceptance_json_chain_of_thought.py` - BDD 步骤实现（Task 0/7）

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/application/ports/blm_planning.py` - BlmPlanningResult 默认尾字段+协议追加 project_chain_records 第七方法（Task 2——R1-F1）
- `src/application/services/blm_planning_service.py` - 尾参可选注入+_PlanRunState 累积位+投影方法+三方法挂接段（Task 2）
- `src/infrastructure/agent_orch/graphs/sp_blm_graph.py` - 三类节点适配器 chain_records 直写行（Task 2——R1-F1③）
- `src/infrastructure/agent_orch/schemas.py` - SpBlmState 加键（Task 2）
- `src/infrastructure/agent_orch/langgraph_engine.py` - 投影 chain_summary 取值源+空回退（Task 2）
- `src/composition_root.py` - 三注册块+增量注入+version（Task 3——纯新增+恰 1 行版本变更）
- `src/entrypoints/agent_cli.py` - chain-query 子命令+汇总行（Task 3）
- `tests/unit/application/test_blm_planning_service.py` - 挂接用例族+投影值级断言+节点适配器直写扩展（Task 2）
- `tests/unit/interfaces/cli/test_agent_cli.py` - chain-query 用例扩展（Task 3）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 处置注记（Task 0/7）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 状态流转（Task 7）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.4 |
| **Story Key** | 6-4-json-chain-of-thought-output |
| **File** | `_bmad-output/implementation-artifacts/stories/6-4-json-chain-of-thought-output.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力 |
| **优先级** | P0-4 |
| **覆盖 FR** | FR-SP-04（P0）——决策追溯预铺 6-7 溯源树 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/零新事件零新异常/快照面零改动/EVIDENCE_PACKAGE 首激活）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-1/6-2/6-3 双五轮审查教训）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则**（R<n>-F<m>）：R=审查轮次，F=修复项——与既有 Story 的 R<n>-F/P/D 先例编号空间一致。

**Round 1（2026-11-03，四视角调研 A/B/C/D + 双评审员 + 主会话亲验，v1.0.0→v1.1.0）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-F1 | chain_records 回传通道断裂：三方法返回 VO 非 dict「累积进返回 dict」无处落；SpBlmState 加键不产生写入（TypedDict 无 reducer 键覆盖——schemas.py:43-45 注释钦定）；`sp_blm_graph.py` 缺席修改清单→`final_state.get("chain_records")` 恒 `()`，AC-2「恰 8 条」物理不可达（三源确认：调研 B+评审 1+评审 2） | **P0** | 钦定回传通道三件套（degraded_steps/timeline 完全同构）：①`_PlanRunState` 加 chain_records 累积位+②`BlmPlanningServicePort` 追加 project_chain_records 第七方法（增量追加非语义变更——端口契约清单/AC-6 同步改口）+③sp_blm_graph 三类节点适配器直写全量（八节点对称）；sp_blm_graph.py 入项目结构/锚点表/文件清单；Task 2 红/绿/变异、验证器 D、OD-9①′ 四位面同步 |
| R1-F2 | tools_used 素材口径失实：「成功工具清单，含版本后缀」——实测返回三元组第三位单数 slug（:600-601 首个成功即返回，每步至多 1 项；slug 无版本后缀） | P1 | AC-1/冻结表/锚点表/0.8①② 五处统一改口：`(tool_slug,) if tool_slug else ()`；「清单+版本后缀」标注为 5-3 任务级语义 BLM 面不适用；判别力断言口径同步 |
| R1-F3 | 素材映射表一行通吃三型：synthesis 无 StepSemanticConfig（语义配置仅 gap+六子七行）/无检索（n 无来源）；gap 无 findings/structured_output——「唯一真源」两型不可编译（假冻结） | P1 | 冻结表三型分列（input_summary/reflection/constraints_check 各三行）；synthesis 语义常量钦定服务模块级（不动 prompts.py 6-1 资产）；gap 用 root_causes 计数；AC-1 素材源映射同步 |
| R1-F4 | PerformanceGapArtifacts asdict 是六键非「四字段」（blm_phases.py:195-200 含 degraded/degrade_reason）；InsightSynthesis 两键 | P1 | AC-1/冻结表改口六键/两键（round-trip 断言口径） |
| R1-F5 | 端口签名 `-> ChainRecord` 与 445 降级「chain 缺席」矛盾（ChainRecord.chain 非可选无法构造缺席记录——契约测试会先锁死错误形态） | P1 | 端口改 `-> ChainRecord | None`：组装失败 445→None（缺席）；归档失败 284→ChainRecord(archived=False)；挂接段 None 判断跳过追加（Task 1/2 同步） |
| R1-F6 | include_blob 无生产通道：StrategicArchiveService 无读 blob 公开方法且被验证器 C 钉死零 diff | P1 | 端口契约补第二注入 `object_storage: L4ObjectPort`（组合根 resolve_optional 同源 :2217）；解引用经 `retrieve(bucket_type, object_key)`（l4_object.py:53） |
| R1-F7 | 并发 10 双缺口：gather 共享单 AsyncSession 并发使用不被 SQLAlchemy 支持（session 来自 ContextVar）；plan_id 口径两处矛盾（「独立 plan_id」vs「count==10 按 plan_id 过滤」） | P1 | 每协程 `session_context()` 独立 scope（session_context.py 模块头 R3）；plan_id 消歧=10 素材共享一个场景专属 plan_id（AC-7/隔离表/Task 5.3 三处同步）；集成隔离口径订正为真实提交+按 plan_id 清理（6-3 实证同构，savepoint 不适用服务内归档链路） |
| R1-F8 | 13 场景计数对不上：枚举仅 12 个 ID（S11 空洞+AC-5×2 仅 S6 一个编号）——0.7「全红」与 Task 7「13/13」按字面不可满足 | P1 | 场景编号连续重排：AC-5 拆 S6 正向+S7 负向，S8 零回归/S9 事件/S10 to_display（归 AC-1）/S11 P95/S12 并发/S13 收尾；0.5/0.6/边缘注记/矩阵五处同步 |
| R1-F9 | AC-5 round-trip 必炸 242：PG JSONB 读回 tools_used 为 list，VO tuple 类型守卫（chain_of_thought.py:71-75）必拒——归一责任无人钦定 | P1 | query_chain_trace 重构前 `tools_used=tuple(chain["tools_used"])` 归一；AC-1 round-trip 断言 list 归一口径；冻结表/AC-5/Task 1B 三处钦定 |
| R1-F10 | StepChainMaterial 字段清单未钦定（「字段清单 AC-2/AC-5 已钦定」引用失实——AC 只钦定另两 dataclass） | P2 | 数据模型节直接落 字段表（含三型差异说明） |
| R1-F11 | 组合根「零删改」与 version 升 v1.1.0 自相矛盾（version 行必是修改） | P2 | 四处统一「纯新增+恰 1 行版本号变更」精确口径 |
| R1-F12 | 投影「末条思维链」缺空回退语义（chain_records 空时末条不存在——无条件替换丢 synthesis 现值信息） | P2 | 钦定空回退 `(first_conclusion or "")[:200]`；AC-2 验证标准补空回退断言 |
| R1-F13 | P95 采样对象（纯组装函数）未在规范位定义——直调 async 复合函数必含 I/O 超预算 | P2 | 钦定模块级纯函数 `compose_step_chain(material) -> ChainOfThought`（Task 1 绿+端口节+Task 5.4 采样素材型=六子步骤型） |
| R1-F14 | 「空 plan_id→空清单」与「非法 plan_id→242」边界互斥（空串也是非 UUID） | P2 | 措辞改「无档案的合法 plan_id→空清单」；空串/畸形走 242 守卫（两语义分立声明） |
| R1-F15 | synthesize_insights 早退分支（:410-412）不触发挂接未声明 | P2 | AC-4 边界注记（该路径 chain 缺席合法，<8 台账口径覆盖） |
| R1-F16 | L4 隐性静默位：`evidence_blob and _object_storage is not None` 双条件——组合根 resolve_optional 未注册时 blob 静默丢弃无 284 无告警 | P2 | AC-3 落对象双前提注记（测试环境 6-3 装配覆盖；生产部署 L4 注册是 WORM 前提） |
| R1-F17 | 杂项：ArchiveQuery limit 默认 20 未注记；missing_fields 单字段短路语义（VO 逐字段短路——断言勿假设多字段） | P2 | AC-5 显式 limit=50 钦定；异常契约表 445 行注记 |
| R1-P3 | 行号/口径订正批：checkpoint plan_type :229→:227、载荷 :230-238→:233-238；LangGraphEngine 尾参 :51→:52-53；BlmPlanningResult 八字段→七字段；投影断言目标 agent_orch/→test_blm_planning_service.py::TestSpBlmGraphTopology（:1005-1027）；SP/BBP→SP/BP（or.md:480 原文）；6-1 断言位置口径（单元 :976-984+验收集成 DTO 面）；矩阵 AC-7 行集成③⑤→①③；`_cleanup_archive_residues` :346-427→:346-430；0.6「骨架」→「含延迟 import 的完整步骤体」；6-3 先例落库类型为默认 ASSUMPTION 非 EVIDENCE_PACKAGE（6-4 必须显式传枚举成员——锚点表补注） | P3 | 逐处订正（本表为索引——各落点位见正文 R1-P3 标记） |
| R1-改判 | 评审 1 报「6-1 边界表 L36」——实测 L37 即思维链行（L36 是阶段位点行），文档原文正确不修（误报登记） | — | 不落修改；留痕防后续轮重查 |

**Round 2（2026-11-03，回归核查双 Agent（传播完备性 R2-A + 增量面组合 R2-B）+ 主会话亲验定谳，v1.1.0→v1.2.0）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-F1 | 「第六方法/既有五方法」计数失实（R1-F1 修复自引入）：协议实有 6 方法（build_planning_context :126/run_performance_gap_analysis :146/run_insight_step :157/synthesize_insights :179/project_timeline :193/project_degraded_steps :197），追加 project_chain_records 是第七方法——9 处传播+锚点表行内自相矛盾（自列六名却称「现五方法」） | P1 | sed 批量「第六方法→第七方法/既有五方法→既有六方法/现五方法→现六方法」9 处；grep 验证零残留 |
| R2-F2 | 部分降级形态 payload 两读（R1-F3 同病根「降级轴」漏修）：degraded=True 且 structured_output 在位（检索/工具降级而 LLM 成功——:348-351 常态路径）时「六子=原样」与「降级步=信封」冲突——按信封读则丢弃真实产物（违背审计初衷） | P1 | 钦定：降级信封仅适用于产物缺席形态（structured_output None）；部分降级 payload=产物原样+降级事实三处承载（reflection 后缀/constraints_check 标记/decision_basis.degraded）；AC-1 验证标准补部分降级断言+Task 1A 红补两形态用例 |
| R2-F3 | 445 构造配方不可达：冻结公式四文本字段恒非空白/final_answer 恒非空——空 payload 红测写不出（json.dumps({})="{}"），唯一 242 通道是 tools_used 元素级守卫（tool_slug=" " 纯空白串 :76-81） | P2 | AC-1 验证标准钦定构造配方 `StepChainMaterial(tool_slug=" ")`；TypeError 面注记不设防理由（素材源受控三态） |
| R2-F4 | include_blob 双缺口：object_storage=None × include_blob=True 行为未钦定（读侧对称 R1-F16 缺注记）；TraceView 无 blob 承载字段——「解引用内容等值」断言只能退化为交互回声（违背值级断言纪律） | P2 | None 行为钦定（warning+槽位 None 不抛异常）；records 补 `blob_content: dict \| None = None` 字段；验证标准改 records[i].blob_content 等值断言；Task 1B 红/绿同步 |
| R2-F5 | project_chain_records 返回 list × Result 字段 tuple 归一未钦定（dict.get→Any 静默绕过 mypy——R1-F9 同款场景） | P2 | `_assemble_result` 读侧显式 `tuple(final_state.get("chain_records") or ())` 归一（AC-2 验证标准钦定） |
| R2-F6 | 早退分支行号 :411-413 偏 1 行（if 在 :410；:413 是正常路径语句被错误包入）——R1-F15 自引入偏差 | P3 | 3 处批量订正 :410-412（主会话实测定谳） |
| R2-F7 | AC-1「全量五字段非空」与空元组合法口径矛盾（synthesis 步 tool_slug 恒空→tools_used 恒空元组，字面断言假红） | P3 | 改「四文本字段非空白+tools_used 形态合法」 |
| R2-F8 | CLI 汇总行计数口径未钦定（二态 vs 三态——445 组装缺席在 CLI 面不可见） | P3 | 三段式「成功 N/失败 M/预期 8」（缺席 K=8-N-M 可推算）；Task 3 断言同步 |
| R2-F9 | S7「负向两形态」未声明单 Scenario 双段结构（拆两 Scenario 则计数 14≠13） | P3 | 0.5 补「单 Scenario 含两段 Given-When-Then」声明 |
| R2-F10 | 锚点借用：schemas.py:43-45 是 5-3 AgentWorkflowState docstring（SpBlmState 自身直写行在 :96-99）；run_state 残留语义未注记（`_runs` 无清理是既有模式） | P3 | 锚点改引 :96-99（:43-45 降为泛化注）；AC-2 补残留语义注记（482 防线依赖残留、三键同收） |

> R2-A 另证实：R1 十项修复传播完备性**全部落地**（含台账外超额传播位）；R2-B 证实「零适配」声称经全仓断言面实测成立（6-1 图身份锚为逐键成员断言非键全集；键全集断言仅在快照 state_data 面——OD-8 保护）+ R1-F7 并发会话模型验证最干净。

**Round 3（2026-11-03，单深度推演（13 场景三轴/8 步时间线/失败矩阵）+ 13 条证伪留痕，v1.2.0→v1.3.0）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-F1 | StepChainMaterial 缺 `evidence_refs` 字段：AC-3 assumptions.evidence_refs 引用无源字段（material 是唯一传参通道）——R1-F10 字段表「假冻结」同类病 | P1 | 字段表补一行（六子=result.evidence_refs/gap=检索三元组第三位/synthesis=()）；AC-3 assumptions 行标注素材源 |
| R3-F2 | 部分降级验收层不可构造（检索降级唯一注入先例在单测 mock 层 test_blm_planning_service.py:252-254；验收 no-mock 红线无通道——真实 Qdrant 空结果=正常空证据不降级 :641-654）+「6-1 既有注入先例」引用失实 | P2 | AC-1 VC3 分层裁定：全降级=验收 S3+单测；部分降级=单测层 Task 1A 专属；矩阵补 AC-1→S3 行 |
| R3-F3 | outbox 行清理缺位：S9/集成②断言 ArchiveCreated 落行（8 行/run）但 6-3 teardown 六步链移植时丢弃第②步——残留累积+「净增 0」口径失真 | P2 | 0.6 四清理步/Task 5.6 四步链+四键族/隔离表补 outbox 行（event_type+plan_id 双通道 DELETE） |
| R3-F4 | 挂接段 plan_id str→UUID 转换守卫未钦定：归档是首个 UUID 硬消费方（6-1 全程 str 兼容），畸形值下裸 ValueError 逃逸→图失败中断 run（违 OD-5+违红线） | P2 | AC-4 钦定挂接段守卫：转换失败该步 chain 缺席+warning 降级续行（6-3 :249-252 宽捕注记同款） |
| R3-F5 | 284 捕获后 L2 半行提交语义未钦定（L2 save 先于失败位——archived=False 台账与 L2 行并存，三层测试均不可达的生产空洞） | P2 | AC-4 注记钦定：半行提交为可接受形态（L2 行在即证据在，读侧以 L2 为准） |
| R3-F6 | tools_used 实值恒为中文显示名：TOOL_CATALOG 23 工具全零 slug=（实测零命中）——判别力期望按 kebab-case 假设必假红 | P3 | 字段表 tool_slug 行补实值注记（期望按 name 构造） |
| R3-F7 | 六子步骤 stage 锚构造公式未显式钦定（裸变量 step.value="trend" 不在八值集——必须前缀拼装） | P3 | 字段表 stage 行补公式 `f"market_insight_{step.value}"`（:384 同源） |
| R3-F8 | 验收装配归档服务 event_publisher 形态未钦定（6-3 先例默认 None；S9 需真实 publisher——若全程真实则全场景 outbox 残留放大） | P3 | 0.6 钦定：默认 None+S9 场景重建真实 publisher（6-3 :636 同款） |
| R3-F9 | 0.8⑦ gap 素材清单漏 tool_slug（冻结表每步采集——清单与冻结表不一致） | P3 | 0.8⑦ 补 `_tool_slug`/`_evidence_refs`（下划线命名作用域可见） |
| R3-F10 | S3 全红注入护栏未声明（fail_schemas 全覆盖 8 Schema→全降级 481 :177-182 场景不可达） | P3 | AC-1 VC3 补「限六子 Schema 子集」注记 |

> R3 证伪留痕（已推演排除，防下轮重推）：①SINGLETON×SCOPED 死 session（服务实为 SCOPED+PG 仓储零参构造调用时读 ContextVar+验收手工构造绕开组合根）②投影在 _assemble_result 后读 Result（实为先于——submit_graph :126-131 发布）③SpBlmState 加键破坏 6-1 图身份锚（逐键成员断言非全集）④lambda 第 9 参破坏 getsource 断言（membership 断言）⑤445 注入 archive_plan 零调用断言时序矛盾（组装先于归档）⑥尾字段破坏等值断言（尾参 None 投影恒 ()）⑦R2-F3 唯一 242 通道论断有漏（四文本恒非空白复核成立）⑧gather 共享 ContextVar 互窜（Task 级拷贝隔离）⑨S5 Qdrant 断言依赖相似命中（filter 面过滤检索）⑩epics 钦定名冲突（无同名+OD-7 已声明）⑪快照写在挂接前时序错位（每节点后 state 恰含该步）⑫行号锚点漂移（20+ 抽查全命中）⑬synthesis 无降级标记可判（R2-F2 三处承载通吃）。

**Round 5（2026-11-03，独立终审五节——周期闭合/双向取证/独立快扫/收敛判定/状态完整性，v1.3.0→v1.3.1）：**

> **收敛声明**：Story 6-4 v1.3.0 独立终审收敛——三轮文档审查（Round 1 四视角调研+双评审 P0×1+P1×8、Round 2 回归核查双 Agent P1×2+P2×3、Round 3 单深度推演 P1×1+P2×4 + 13 条证伪留痕）共 37 项修复台账登记完整，终审抽验 12/12（覆盖三轮、含 P0/P1 全档）经「台账声明 vs 正文现实 vs 代码现实」三方对照全部一致，R1-改判（6-1 边界表 L37 误报）经原文实地核实登记正当。25+ 代码锚点实地命中（协议六方法/三元组 :600-601/早退 :410-412/TOOL_CATALOG 零 slug/EVIDENCE_PACKAGE 全 src 零使用等），三张冻结表交叉一致、文件清单与项目结构三方对齐。零 P0/P1 残留，P3×6（changelog 残留字符/计数 off-by-one/条目顺序/:655-680 定谳/字段表描述/矩阵回指）随本轮收敛提交清偿。判定达到 ready-for-dev 质量门，Status 与 sprint-status.yaml 一致，可交付 dev-story 实施。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待代码审查）
**审查模式:** （待代码审查）

#### 需决策 Decision Needed

- [ ] （待代码审查）

#### 已修复 Patch

- [ ] （待代码审查）

#### 已推迟 Defer

- [ ] （待代码审查）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.1
**创建日期/Created:** 2026-11-03
**最后更新/Last Updated:** 2026-11-03（五轮审查收敛）
**更新说明/Description:**
- v1.0.0: 创建故事文件（四 Agent 并行调研+主会话亲验：5-3 ChainOfThought VO 复用定位/3-10 EVIDENCE_PACKAGE 零使用实证/6-1 边界表 L37 钦定 BLM 面/6-3 归档与清理先例；四冻结规范：确定性组装映射（OD-2）/归档载荷映射（OD-4）/端口契约/异常复用清单（OD-6 零新增）；AC-1~AC-7 + Task 0~7 + 13 验收场景规划；Status → ready-for-dev）
- v1.1.0: 文档审查 Round 1（四视角调研+双评审+主会话亲验，P0×1+P1×8+P2×8+P3 批）：**R1-F1 回传通道三件套**（chain_records 经 _PlanRunState 累积+协议第七投影方法+sp_blm_graph 节点适配器直写——原「累积进返回 dict」物理不可行）；R1-F2 tools_used 单数口径；R1-F3 素材映射三型分列；R1-F5 端口返回 ChainRecord \| None；R1-F6 include_blob 第二注入；R1-F7 并发会话模型+plan_id 消歧+集成清理口径；R1-F8 场景编号连续重排；R1-F9 tuple 归一；R1-F10~F17 与 R1-P3 行号订正批（详见文档审查修复表）
- v1.2.0: 文档审查 Round 2 回归核查（双 Agent：传播完备性+增量面组合；P1×2+P2×3+P3×5）：R2-F1 第七方法计数订正（R1 自引入 9 处）；R2-F2 部分降级 payload 钦定（降级信封仅产物缺席形态——R1-F3 降级轴漏修）；R2-F3 445 构造配方（tool_slug=" " 唯一通道）；R2-F4 include_blob None 行为+blob_content 落位字段；R2-F5 读侧 tuple 归一；R2-F6~F10 行号/口径/结构批（详见修复表）
- v1.3.0: 文档审查 Round 3 单深度推演（13 场景三轴/8 步时间线/失败矩阵+13 条证伪留痕；P1×1+P2×4+P3×5）：R3-F1 StepChainMaterial 补 evidence_refs 字段（assumptions 源字段）；R3-F2 部分降级分层裁定（归单测层——验收 no-mock 无通道）；R3-F3 outbox 行清理四步链（6-3 teardown 第②步移植）；R3-F4 挂接段 UUID 守卫（裸 ValueError 逃逸防御）；R3-F5 L2 半行语义钦定；R3-F6~F10 实值/公式/装配/清单/护栏批
- v1.3.1: Round 5 独立终审收敛（P3×6 随收敛清偿：changelog 残留字符/计数 off-by-one/条目调序/:655-680 定谳/字段表描述/矩阵回指）+ 收敛声明入档——零 P0/P1 残留，v1.3.1 维持 ready-for-dev
