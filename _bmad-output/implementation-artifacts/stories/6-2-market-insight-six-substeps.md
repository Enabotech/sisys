# Story 6-2: 市场洞察六子步骤（六步类型化结构化输出 + 每步 Checkpoint 触发）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统执行市场洞察六子步骤时，每个子步骤输出符合该步领域方法论的类型化结构化结果（PESTEL 六维度、波特五力、VRIO 等领域结构），且每个子步骤完成时触发 Checkpoint 快照骨架,
**So that** 全面分析市场环境和机会，并为后续阶段审批（Story 6-3 Checkpoint 完整机制）与报告生成（Story 6-5）提供结构化数据面。

### 业务价值

- 覆盖 **FR-SP-02 (P0)**：市场洞察六子步骤基础（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）
- Story 6-1 已交付六子步骤的**执行链骨架**（顺序执行、工具先行、检索注入、降级信封、快照 latest、`BlmStageCompleted` 事件），但每步产物止于**通用信封**（summary + findings 两个泛化字符串字段）。本 Story 将信封升级为**每步类型化 Schema**——下游 6-5 报告生成（Markdown/PDF 引文）与 6-7 溯源树需要结构化字段而非自由文本
- **每步 Checkpoint 快照骨架**为 Story 6-3（Checkpoint 完整机制：持久化笔记/压缩/Replay-Override 恢复）铺设可叠加的恢复点位（core-domain §17.4.1 钦定市场洞察阶段 = Checkpoint-2-7，每子步骤一个）
- Epic 6 内部顺序依赖：6-1（done）→ **6-2（本 Story）** → 6-3 → 6-5a/6-5b

### 与 6-1 的范围边界（出处逐行：6-1 边界表 / 6-1 代码审查 R2-3 / epics 6.2——R1 修订：节标题原笼统署名"6-1 边界表钦定"，实测仅"每步产物/快照"两行出自边界表，逐行出处已补列表内）

| 面（出处） | 6-1 已交付（禁重复造轮） | 6-2 增量（本 Story） |
|---|---|---|
| 六步执行链（6-1 交付记录） | `MarketInsightStep` 枚举/执行序/`SpBlmGraph` 六节点/工具候选先行/检索注入/步级降级 | 零改动复用 |
| 每步产物（6-1 边界表钦定） | `InsightStepResult` 通用信封（summary/findings）+ `InsightStepSchema`（两字段） | **六步各自类型化 Schema** + 信封扩展承载结构化产物 |
| 快照（6-1 边界表钦定） | latest 单值快照（`sisys:snapshot:blm-planning-{plan_id}`，读侧 `GetBlmPlanningStatusUseCase` 消费） | **每子步骤一份 Checkpoint 快照骨架**（per-step 键，latest 保持兼容） |
| 事件（本 Story 自钦定——沿 6-1 AC-4 先例） | `PlanningStarted`/`BlmStageCompleted`（stage 8 值域含每子步骤） | 零新增（`CheckpointReached` 继续不发布——6.3 语义分立） |
| 跨阶段传导（6-1 代码审查 R2-3 裁定） | gap 摘要仅传导 financial_gap 单字段（R2-3 成文裁定留给 6-2） | **gap 四字段全量传导** |
| 性能（epics 6.2 L2100-2102 钦定） | 全流程 P95<30s / 成功率≥95% | **市场洞察段 P95<25s** + **并发 5 任务**（新增性能面） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 六子步骤类型化结构化输出

**Given** 业绩差距分析完成且市场洞察六子步骤依次执行
**When** 某个子步骤的结构化 LLM 调用返回
**Then** 该步使用**该步专属的类型化 Schema**（非通用 `InsightStepSchema`）做结构化生成与校验，产出含该步领域方法论必含要素的结构化结果
**And** 结构化结果以 `structured_output` 字段挂载于 `InsightStepResult` 信封（键值均为 JSON 标量/标量列表——扁平化）
**And** 六步类型化分派由模块级 SSOT 映射驱动，服务层零 if-else 硬编码分派

**验证标准/Validation Criteria:**
- [ ] 看趋势产出含 PESTEL 六维度评估（OD-8 工具产物化）+ 技术演进路线图 + 情景规划方案集
- [ ] 看市场与客户产出含客户细分画像 + 需求优先级矩阵 + 价值主张地图
- [ ] 看竞争产出含波特五力五维评估（OD-8 工具产物化）+ 竞争对手能力雷达图评估 + 竞争策略建议
- [ ] 看自己产出含内部能力清单 + 核心能力 VRIO 评估 + 资源约束分析
- [ ] 看机会产出含机会清单 + 机会优先级排序 + 增长路径图
- [ ] 机会差距分析产出含机会差距量化报告 + 能力-机会匹配矩阵 + 差距弥合策略
- [ ] 产物命名以 or.md L386-415 原产物名为准（图/报告类产物以要点字段族承载——图本体生成归 6-5 报告面，OD-8 声明）
- [ ] 每个 Schema 字段类型仅限 `str` / `float` / `list[str]`（嵌套对象禁入——OD-5 扁平化强制）
- [ ] 每步 Schema 均含公共字段 `summary: str` + `findings: list[str]`（信封同源双公共字段——R3 修订，服务 L350-352 直读两字段）

### AC-2: 每子步骤触发 Checkpoint 快照骨架

**Given** 市场洞察某子步骤执行完成（含降级步）
**When** 步骤边界到达
**Then** 在既有 latest 快照之外，**为该子步骤创建一份独立 Checkpoint 快照骨架**（复用既有 `CheckpointSnapshot` 实体 + `SnapshotRepositoryProtocol` + `RedisSnapshotStore` 基建，零新端口）
**And** per-step 快照可按步骤独立读回，state_data 携带该步 stage 标识与类型化产物
**And** per-step 快照写入失败不阻断流程（与 latest 写入同语义——步级容错）

**验证标准/Validation Criteria:**
- [ ] 一次完整市场洞察运行后，6 个子步骤快照 + 1 个 latest 快照全部可独立读回
- [ ] per-step 快照键形态：`sisys:snapshot:blm-planning-{plan_id}:{step_value}`（session_id 后缀区分步骤——RedisSnapshotStore 键仅由 session_id 决定，见 Dev Notes）
- [ ] per-step 快照 stage_id = 该步 stage 值（`market_insight_{step}`，与 `STAGE_VALUE_DOMAIN` 同源）
- [ ] latest 快照（`stage_id="blm_planning"`）行为与 6-1 完全一致——读侧 `GetBlmPlanningStatusUseCase` 零回归
- [ ] 降级步同样触发快照（state_data 含降级标记；`structured_output` 键恒存在、降级步恒 `null`——见 state_data 七键契约）

### AC-3: CheckpointReached 事件语义分立（负向断言）

**Given** 市场洞察六子步骤依次完成并触发 per-step 快照
**When** 检查事件发布面
**Then** `CheckpointReached` 事件**零发布**（6.3 语义分立——6-1 AC-4/5-10 OD-6 先例沿袭：BLM 审批语义的 CheckpointReached 由 6-3 落地真实发布点）
**And** `BlmStageCompleted` stage 值域保持 8 值不变（`STAGE_VALUE_DOMAIN` frozenset 零扩展），每步发布行为与 6-1 一致
**And** 本 Story 零新增领域事件、零事件通道登记变更（`configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零 diff）

**验证标准/Validation Criteria:**
- [ ] outbox 中本 plan_id 相关行零 `CheckpointReached`（负向断言——验收/契约双承载；**非空锚前置（R3 补）**：先断言该 plan_id 行数 ≥9（PlanningStarted×1+BlmStageCompleted×8）再负向 CheckpointReached——防 recorder 装配空真；行筛选 SQL 路径 = `payload->'payload'->>'plan_id'`：outbox 行 payload 列存 `to_dict()` 全量、`plan_id` 位于 payload 子字典内——`event_outbox_adapter.from_domain_event` L30 + `base.to_dict` 子类字段并入语义，6-1 集成既有先例 `payload->'payload'->>'stage'` 同构；验收层该场景用 6-1 场景⑨ 真实发布装配先例）
- [ ] `test_event_channel_mapping_blm_planning.py` 既有负向源码 grep 断言继续通过
- [ ] `STAGE_VALUE_DOMAIN` 值域守卫测试零修改通过

### AC-4: 类型化校验失败降级与成功率

**Given** 某子步骤结构化 LLM 输出不符合该步类型化 Schema（校验失败/超时/异常）
**When** 服务层捕获
**Then** 按既有步级降级规则降级（完整信封：`degraded=True` + `degrade_reason` + `structured_output=None`），流程继续，后续步骤正常执行
**And** 降级步同样触发 per-step 快照与 `BlmStageCompleted`（信封完整性口径不变）
**And** 受控失败注入采样下，六子步骤成功率≥95%（口径：子步骤产出完整信封即计入成功——6-1 AC-5 先例）

**验证标准/Validation Criteria:**
- [ ] 单点类型化校验失败 → 仅该步降级，其余五步 + synthesis 正常
- [ ] 双杀注入（相邻两步 {k, k+1} 的**两个 Schema 同时恒败**——注意与 6-1 代码审查 R1-8 的"双杀"同词不同义：6-1 指单步首调+重试两序号皆败，本 Story 指相邻两步各自降级）→ 两步降级且互不传染
- [ ] **注入键钦定（R1 修订）**：一律按 `response_schema` 身份注入（`fail_schemas` 语义——schema 恒败，首调与重试皆败）——验收/集成 Fake 在既有 `fail_call_indices` 之外**扩展 schema 身份注入参数**；禁用调用序算术注入（重试同占调用序、20 轮采样下序号连续累计会漂移错位——6-1 验收 Fake L111 注记成文）；六 Schema 与六步一一对应，`fail_schemas={SchemaK, SchemaK+1}` 即精确双杀
- [ ] `structured_output` 仅在非降级且校验通过时填充
- [ ] 20 轮受控注入采样成功率 100%（Fake LLM 口径——降级信封完整即计入成功，6-1 先例；schema 身份注入与轮次无关，逐轮稳定复现双降级）

### AC-5: 市场洞察段性能 P95<25s

**Given** 市场洞察段（六子步骤 + 综合步骤，不含业绩差距分析阶段）在测试管线中执行
**When** 采样计时
**Then** 市场洞察段执行延迟 P95 < 25s（Fake LLM 管线开销口径——OD-3：真实 LLM 延迟显式出栈，口径差声明落测试 docstring，与 6-1 DC-7 先例一致；真实 LLM 计时归 6.1-DF1 部署验证）

**验证标准/Validation Criteria:**
- [ ] 采样 ≥20 轮（R1 修订：≥10 时 `ceil(0.95*10)-1=9` 即 P95≡最大值零容忍；20 轮取次大值档，对齐 6-1 先例），P95 = durations[ceil(0.95*n)-1] < 25.0s
- [ ] 计时窗口 = 六子步骤开始至 synthesis 完成（阶段 2 全段）；**观测点钦定（R1 修订）**：`timeline[market_insight_trend].started_at → timeline[market_insight_synthesis].completed_at`（经 `project_timeline(plan_id)` 或 latest 快照 state_data.timeline 读取——`InsightSynthesis` VO 本身无时间戳字段，`BlmTimelineEntry` 两端字段先由服务 `record_step` 写入）
- [ ] 性能场景复用 `_CachedEmbedding` 缓存代理模式（6-1 收敛优化先例：embedding API 往返占性能场景 >95%）

### AC-6: 并发执行 5 个市场洞察任务

**Given** 5 个规划任务（5 个**不同** plan_id——OD-4：同 plan_id 并发 482 竞态窗口归 7-2，6.1-DF6）
**When** 以 `asyncio.gather` 并发执行
**Then** 5 个任务全部完成，各自六子步骤类型化产物、per-step 快照、事件互不串扰
**And** 各 plan_id 的 per-step 快照键/事件 outbox 行按 plan_id 可分离断言

**验证标准/Validation Criteria:**
- [ ] 5 任务全部返回成功 DTO（或各自的降级终态正确归属）
- [ ] 每任务 6 个 per-step 快照独立可读回，无跨 plan_id 污染（state_data.plan_id 归属锚逐任务断言，R1-4）
- [ ] outbox 行按 `payload->'payload'->>'plan_id'` 逐任务计数正确（R1 修订：**禁用 `payload->>'aggregate_id'`**——`BlmStageCompleted.aggregate_id` 实测语义为 agent_id 非 plan_id（`planning_events.py` L132-133），5 任务共享 CEO agent 时该键全同值不可分离，且 context 无可解析 agent_id 时服务侧每次发布随机 uuid4（service L673）连单 plan 内都不稳定；`plan_id` 位于 to_dict 的 payload 子字典内，两级 JSONB 路径与 6-1 集成既有先例 `payload->'payload'->>'stage'` 同构）

### AC-7: 跨阶段传导与综合消费（gap 四字段全量）

**Given** 阶段 1 业绩差距分析产出四字段产物（financial_gap/operational_gap/root_causes/portfolio_health）
**When** 阶段 2 各子步骤构造 prompt
**Then** 注入的 gap 摘要为**四字段全量**（扩展 `summarize_gap_for_downstream`——6-1 **代码审查** R2-3 成文裁定的执行；R1 修订消歧：6-1 存在文档/代码两审查轮同号双表，代码审查 R2-3 才是 gap 收窄裁定），非 6-1 的 financial_gap 单字段
**And** 前序子步骤产物摘要注入后续步骤（`prior_outputs` 机制复用；**R3 消歧**：`summarize_step_for_downstream` 实测仅读 degraded/step/degrade_reason/summary 四字段、不读 structured_output——本条语义 = summary 经各类型化 Schema 的 `summary` 字段 description 约束与信封同源（AC-1 公共字段条款），**显式裁定不扩展 summarize_step_for_downstream 读结构化产物**——原文"类型化摘要含领域要素要点"双读法中读法 ii 无 Task 承载且验收面不可判别，予以收敛）
**And** synthesis 综合消费六步产物（含降级标注——⑥规则不变）

**验证标准/Validation Criteria:**
- [ ] 阶段 2 第一步 prompt 中可断言四字段全量摘要存在（Fake LLM calls 记录断言）
- [ ] gap 降级时摘要仍带 `[降级]` 标注（DEGRADATION_MARKER_PREFIX 单源不变）
- [ ] synthesis degraded_inputs 降级列举语义与 6-1 一致（零回归）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **零新增领域事件**（本 Story 钦定——事件面 6-1 已完备：`PlanningStarted`/`BlmStageCompleted` stage 8 值域含每子步骤）
- [x] `CheckpointReached` 保持不发布（6.3 语义分立——6-1 AC-4/5-10 OD-6 先例），负向断言沿袭
- [x] `configs/event_channels.yaml` 与 `src/infrastructure/messaging/channel_router.py` `DEFAULT_MAPPINGS` 零 diff（守护测试承载）
- [ ] 既有事件契约测试 `tests/contracts/test_event_channel_mapping_blm_planning.py` 回归通过

#### 数据模型 (Data Models)

**领域层 VO 扩展**（`src/domain/value_objects/blm_phases.py` 就地扩展，纯标准库）：

- [ ] `InsightStepResult` 新增字段 `structured_output: dict[str, Any] | None = None`
  - 值域守卫（`__post_init__`，抛 `EntityValidationError` EXCEPTION_242）：键为 str；值仅限 JSON 标量（str/int/float/bool）或 `list[str]`（防 pydantic 对象渗入领域层——domain 零依赖红线）
  - **白名单两层声明（R1 修订）**：守卫白名单（本条，str/int/float/bool + list[str]）**刻意比** Schema 声明白名单（AC-1/OD-5，str/float/list[str]）宽一格——纵深防御：守卫是应用层值域兜底而非生成面约束，两层集合不同且各自冻结；pydantic v2 下 float 字段对 int 输入强转 float（`model_dump()` 产 `1.0` 非 `1`），六 Schema 限声明白名单时 dump 结果恰好落在守卫白名单内
  - 带默认值 `None` 向后兼容（6-1 既有构造/断言零破坏）
  - 降级步恒为 `None`（AC-4）
- [ ] **六步类型化 Schema**（pydantic BaseModel，**应用层**——`src/application/services/blm_planning_prompts.py` 扩展，与 prompt 模板同文件，Task 0.1 钦定"结构化输出契约是 prompt 面的一部分"）：

| 步骤（枚举值） | Schema 类名 | 必含领域要素（or.md 五.2.(2) L386-415 输出产物 × OD-8 工具产物化映射） | 方法论锚 |
|---|---|---|---|
| `trend` | `TrendInsightSchema` | PESTEL 六维度评估（political/economic/social/technological/environmental/legal）〔OD-8：or.md 原产物"宏观趋势报告"工具产物化〕、技术演进路线图、情景规划方案集 | PESTEL/情景规划 |
| `market_customer` | `MarketCustomerInsightSchema` | 客户细分画像、需求优先级矩阵、价值主张地图 | $APPEALS/价值主张画布 |
| `competition` | `CompetitionInsightSchema` | 波特五力五维评估〔OD-8：or.md 原产物"行业竞争结构图"工具产物化〕、竞争对手能力雷达图评估、竞争策略建议 | 波特五力/竞争对手分析 |
| `self` | `SelfInsightSchema` | 内部能力清单、核心能力 VRIO 评估、资源约束分析 | 价值链分析/VRIO |
| `opportunity` | `OpportunityInsightSchema` | 机会清单、机会优先级排序、增长路径图 | SWOT-TOWS/安索夫矩阵 |
| `opportunity_gap` | `OpportunityGapInsightSchema` | 机会差距量化报告、能力-机会匹配矩阵、差距弥合策略 | GE-麦肯锡矩阵/SWOT-TOWS |

  - **公共字段（R3 修订——P1 修复）**：每 Schema 含 **`summary: str` + `findings: list[str]` 双公共字段**（信封同源：服务成功分支信封构造 L350-352 直读 `schema_result.summary`/`schema_result.findings` 填充 `InsightStepResult`——六 Schema 缺 findings 字段则切表即 AttributeError，Task 3 阻断；双公共字段使 6-1「findings/summary 语义未变」回归声明成立、降级分支空 summary/空 findings 对称保持）
  - **扁平化强制（OD-5）**：字段类型仅限 `str` / `float` / `list[str]`；禁嵌套 BaseModel / 禁 `list[dict]` / **禁 Optional[X] / None 默认值字段**（`model_dump()` 对 Optional 字段产 `None`——VO 守卫拒 None 且拒绝点在信封构造处、位于步级降级 try/except 之外，会炸整轮 run 而非降级该步）；GLM-5.3 anthropic 端点对嵌套 Schema 服务端栈溢出 500（`src/infrastructure/external_services/llm/litellm_llm_client.py` L631-637 注记成文）；字段命名 snake_case
  - 领域要素 → 字段的精确映射在 Task 0 定稿并冻结（后续 Task 不得擅自增删字段——契约面变更需过 Contract Gate 思路评审）
- [ ] `InsightStepSchema`（两字段通用信封 Schema）**移除**：六步全量切换类型化后生产调用点归零，保留即双源（YAGNI）；其 `summary` 语义并入各类型化 Schema 公共字段。引用面清理见"6-1 回归面"
- [ ] per-step 快照 state_data 键契约登记于端口文件序列化契约区（`src/application/ports/blm_planning.py` 既有 SSOT 区——**latest 两级契约（模块 docstring 登记的顶层七键 + timeline 条目六键）之外新增第三级 per-step 契约，属待新增非既有**）：`step`/`plan_id`/`summary`/`structured_output`/`degraded`/`degrade_reason`/`completed_steps` 七键
  - `completed_steps` = 截至该步（**含**该步）的已完成 stage 值清单 `list[str]`，**首步快照即含 `performance_gap`**（自然实现 `[e.step for e in run_state.timeline]` 含阶段 1——期望构造侧按此口径，R3 钉死）；恢复语义下清单可用性优于计数；与 latest 的 int 计数语义显式区分——R1 修订钉死）
  - `structured_output` 键**恒存在**，降级步恒 `null`（None 可 JSON 序列化，禁"降级时键缺失"形态——6-3 读侧免双兼容）
  - `plan_id` 键为快照体归属锚（并发场景逐 plan 断言的 state_data 级证据，AC-6）；读侧判别规则 = session_id 键后缀 + state_data 含 `plan_id`/`step` 双锚（区分 latest 与 per-step 两契约）
  - 恢复点位语义——6-3 叠加 persistent_note_ref 的数据面；TTL 沿用 `CheckpointSnapshot` 既有默认 86400（1 天），6-3 升级 30 天完整形态（OD-1 钦定，防误判遗漏）

#### 统一端口定义注册与管理 (Port Contract)

- [x] **预计零新增端口、零端口签名变更**（本 Story 钦定）：
  - 服务改造在 `BlmPlanningServicePort` 既有**六方法**（四执行方法 build_planning_context/run_performance_gap_analysis/run_insight_step/synthesize_insights + 两投影方法 project_timeline/project_degraded_steps）内——**仅 `run_insight_step` 扩展**（含私有助手 `_write_step_checkpoint`；`InsightStepResult` 扩展字段为 VO 向后兼容扩展，非契约破坏）
  - per-step 快照复用 `SnapshotRepositoryProtocol`（domain 基础端口，R1）+ `RedisSnapshotStore`（infrastructure 实现，R3）
  - 类型化 Schema 属 prompt 面资产（应用层），不构成端口
- [ ] 端口契约清单（唯一事实源——本 Story 全量复用，禁止语义重复新增）：

| 端口 | 层 | 注册名（composition_root） | 本 Story 动作 |
|---|---|---|---|
| `BlmPlanningServicePort` | application/ports | `blm_planning_service`（v1.0.0，L1580） | 复用，实现层扩展 |
| `AgentEnginePort` | domain/ports | `agent_engine`（v1.1.0，L1555） | 复用，零改动 |
| `SnapshotRepositoryProtocol` | domain/ports | `snapshot_repository`（L950） | 复用（per-step 形态新增调用） |
| `LLMClientPort` | domain/ports | `llm_client`（v1.1.0，L2049） | 复用（`structured_generate(prompt, response_schema, ...)` 天生支持 per-call Schema——端口定义 L162-191） |
| `ToolExecutionServicePort` / hybrid 检索 / `EventPublisher` | — | 既有 | 复用，零改动 |
| `RunBlmPlanningUseCase` / `GetBlmPlanningStatusUseCase` | application | `blm_planning_use_case`/`blm_planning_status_use_case` | 复用，零改动 |

- [ ] 组合根 `src/composition_root.py` **预计零 diff**（Task 4 守护验证——resolve 可达性复核）
- [ ] 既有契约测试 `tests/contracts/test_port_contract_blm_planning.py` 回归通过（端口签名零变更 → 零修改通过；若需修改即契约破坏，必须回 Task 0 重审）

#### 端口契约清单执行约束（强制）

- [ ] 本清单是唯一事实源（Single Source of Truth）；实现中确需新端口时回 Task 0 补登记 + Contract Gate + 契约测试，禁止边写边加
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象（6-1 纪律沿袭）

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。

- [x] **预计零新增领域异常**（本 Story 钦定）：
  - VO 值域守卫复用 `EntityValidationError`（EXCEPTION_242，entity 子域）
  - 步级失败走既有降级路径（信封完整，不抛异常）；全降级终态复用 `PlanningExecutionError`（481）
  - per-step 快照写入失败走容错日志（与 6-1 latest 同语义），不新增异常
- [ ] **预留说明**：若实现中确需新增（如 fail-loud 场景成文），取 planning 子域 **483-489 预留段**（`src/domain/exceptions/_code_ranges.py` L184 成文"483-489 预留 planning 域"），继承 `BusinessException`，履行 4 项 Checklist：定义文件（`planning_exceptions.py` 就地追加）→ `_CLASS_TO_SUBDOMAIN` 注册 → `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP` → 码段校验测试。**禁占** financial 471-479（双重成文预留）与 tool 384（保留位）
- [ ] Story 异常契约文档：本节即小节（零新增 + 复用清单 + 预留段说明）

#### API 契约 (API Contract)

- [x] **零 REST API 变更**（本 Story 无新端点——BLM 面 REST 接线归 7-2，6.1-DF5）
- [x] CLI `sisys agent blm-plan` 子命令既有入口零破坏（`src/entrypoints/agent_cli.py`）；可选轻量增强：完成摘要打印 per-step 快照键计数（非必须，最小改动原则——若做，8 用例既有 CLI 测试扩展）

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
- **本 Story 特别注意**：六类型化 Schema 是 pydantic → 只能落应用层（`blm_planning_prompts.py`）；领域层 `InsightStepResult.structured_output` 用 `dict[str, Any] | None` 标准库形态承载，值域守卫防 pydantic 对象渗入

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

**设计规则 R1~R4 落点**（用户钦定）：
- **R1** 领域层统一抽象基础端口 → `SnapshotRepositoryProtocol`/`LLMClientPort`（既有，本 Story 零新增）
- **R2** 应用层端口组合注入基础端口 → `BlmPlanningServicePort`（应用层端口）组合注入 LLM/工具/检索/事件/快照五类端口（6-1 既有形态，本 Story 沿袭）
- **R3** 基础设施层实现端口并管理技术 → `RedisSnapshotStore`（Redis Hash）承载 per-step 快照，键构造复用 `build_key`——支持扩展其他同类存储实现
- **R4** 接口层适配外部请求 → CLI `blm-plan` 既有入口零破坏；本 Story 无新外部接口面

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_market_insight.feature`（OD-7 功能名族命名）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_market_insight.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）——建议 13~14 场景：AC-1×3 / AC-2×3 / AC-3×1 / AC-4×2 / AC-5×1 / AC-6×1 / AC-7×1~2 / 收尾×1（范围式钦定——**Subtask 0.4 定稿时钉死为确定值**并全文同步，禁带范围值进入 Task 7）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（模块级 `event_loop` fixture + `_run_async` helper——6-1 三件套）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——本 Story 异常路径 = 类型化校验失败降级（AC-4 单点+双杀注入）；**快照写入失败容错归属单测层**（Task 3 循环 B 的 AsyncMock 抛异常用例——R3 裁定：验收层 no-mock 红线下无法构造真实 Redis 写失败，stub repository 抛异常 = mock 真实服务违红线，故验收 Edge Cases 不含写失败容错，防两硬约束互斥）
- **场景分化维度表（R3 补——Subtask 0.4 钉死时的钦定输入）**：AC-1×3 = 完整流程类型化全量断言 / 六步执行序+双锚（顺序+step 值）/ synthesis 综合消费（循 6-1 形态）；AC-2×3 = 6+1 快照全量读回 / latest 零回归（读侧 GetBlmPlanningStatusUseCase）/ 降级步快照标记（与 AC-4 场景区分：此场景只断快照面）；AC-4×2 = 单点注入 / 双杀注入（**Task 7.1 勘误：原"降级双杀×2"标签失实，单点覆盖不得丢失**）；AC-7×2 = 正常四字段传导 / gap 降级 `[降级]` 标注（需 fail_schemas={GapAnalysisSchema} 独立 run——R3 钉 2 场景，7.2 同步）；20 轮采样归属集成 5.3 承载，验收层单轮断言（防全管线 60 次冗余）
- **R6 模板合规**：feature/py 组织结构对齐 `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`/`.py`（多行 @scenario 字面量路径 + 场景绑定与步骤实现交替排列 + AC 横幅分组 + 中文 Gherkin），**断言必须真实**（禁 then-pass 占位——PG 模板历史缺陷，5-3 用户裁定 2026-10-22 沿袭）；装配形态对齐 6-1 `test_acceptance_blm_planning.py`（真实服务链 + Fake LLM 唯一豁免 + 延迟 import 纪律 + 场景分档表 docstring + teardown 五步链）
- **6-1 回归面（强制）**：`InsightStepResult` 扩展与 `InsightStepSchema` 移除后，全仓 grep 消费方测试并同步适配——**三处 Fake 全量**（unit `test_blm_planning_service.py` 的返回体按两字段 `{summary, findings}` 构造 + 验收/集成的 `_make_fake_llm` 分派键 = response_schema 身份），六类型化 Schema 上线后三处必失配/必红，必须同步扩展分派面与返回体构造（适配器契约变更回归纪律：禁只跑直接文件；**适配动作随 Task 3 服务切换同批承载**——R1 修订钦定，见 Task 3 循环 A）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（六类型化 Schema 字段级定稿冻结 / per-step 快照键契约 / 事件与异常零新增裁定落档）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——**预期失败形态 = 步骤函数运行期失败**：延迟 import 抛 `ImportError`（既有模块中缺失的类名——非模块文件缺失的 `ModuleNotFoundError`）或断言步 `AssertionError`；**收集期零错误本身即延迟 import 纪律的自证**——R1 修订，原文"预期收集失败"与本 Story 延迟 import 纪律自相矛盾）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义：
  1. 组合根零 diff 复核（`blm_planning_service` 等五注册 resolve 可达——Task 4 守护）
  2. 事件零新增验证（event_channels.yaml + DEFAULT_MAPPINGS 零 diff + `CheckpointReached` 负向源码断言——契约测试承载）
  3. per-step 快照接线（服务 → `SnapshotRepositoryProtocol` → `RedisSnapshotStore` 真实链，集成测试 `load()` 读回验证——零「已实现未接线」）
  4. CLI `blm-plan` 入口回归（既有 8 用例零破坏）
- [ ] **留项裁定义务**（deferred-work 台账，Task 0 成文）：
  - L125 DC-9 注记「工具候选矩阵深化 6-2 评估」（锚词为"工具候选矩阵深化"，SOP 白名单是其下能力项——R1 修订锚词对齐台账原文）→ 本 Story 钦定：**维持 6-1 中文显示名白名单口径，不注入 SOP 白名单**（触发条件：部署验证专项（6.1-DF1 同批）真实 LLM 验证发现幻觉名率超标时再评估）；成文更新 deferred-work 台账
  - 6.1-DF2「稀疏检索消费」→ 本 Story 类型化 Schema 不新增稀疏检索依赖，**维持 deferred 留项**（触发条件不变），台账注记 6-2 评估结论

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
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言；6-1 属性形态断裂族三犯教训详见 Dev Notes）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | `InsightStepResult` VO 扩展 | structured_output 值域守卫/默认值兼容/降级步语义 | `tests/unit/domain/test_blm_domain_models.py`（扩展） | Task 1 |
| **TDD 单元测试** | 六类型化 Schema | 字段完备性/扁平形态/领域要素描述符/model_dump 键域 | `tests/unit/application/test_market_insight_schemas.py`（新建） | Task 2 |
| **TDD 单元测试** | 语义配置表 + schema 映射 SSOT | 六步映射齐备/枚举键完整/温度档零回归 | `tests/unit/application/test_market_insight_schemas.py`（同文件分组） | Task 2 |
| **TDD 单元测试** | `summarize_gap_for_downstream` 四字段 | 四字段全量/降级标注不变 | `tests/unit/application/test_market_insight_schemas.py`（同文件分组） | Task 2 |
| **TDD 单元测试** | `BlmPlanningService.run_insight_step` | 类型化分派/校验失败降级/structured_output 填充 | `tests/unit/application/test_blm_planning_service.py`（扩展） | Task 3 |
| **TDD 单元测试** | per-step 快照写入 | per-step session_id 形态/stage_id 正确/失败容错/latest 兼容 | `tests/unit/application/test_blm_planning_service.py`（扩展） | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~7 全覆盖） | `test_acceptance_market_insight.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_market_insight.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 事件通道零变更守护 | yaml/DEFAULT_MAPPINGS 零 diff + CheckpointReached 负向 | `tests/contracts/test_event_channel_mapping_blm_planning.py`（扩展） | Task 4 |
| **TDD 契约测试** | 端口契约回归 | 端口签名零变更下既有契约测试通过 | `tests/contracts/test_port_contract_blm_planning.py`（零修改回归） | Task 4 |
| **SDD 架构验证** | 六边形架构约束 | domain 零依赖（扩展后复核）/Schema 落位（pydantic 仅应用层）/**扁平化守卫**（六 Schema 字段类型白名单反射断言） | `tests/unit/architecture/test_market_insight.py`（新建，epics 钦定名恰为功能名族） | Task 6 |
| **集成测试** | 真实链协作 | 类型化全链（真 Redis/真检索/真图引擎 + Fake LLM 豁免）/per-step 快照读回/降级/并发 5（5.4a）+ P95 采样（5.4b） | `tests/integration/test_integration_market_insight.py`（新建，OD-7） | Task 5 |
| **回归测试** | 6-1 消费方适配 | 6-1 验收 14 场景/集成 4 场景/service 单测 38 用例在 Schema 切换后全绿（Fake 分派面+返回体适配——Task 3 同批落码） | `tests/unit/application/test_blm_planning_service.py`、`tests/acceptance/test_acceptance_blm_planning.py`、`tests/integration/test_integration_blm_planning.py`（适配修改） | Task 3 / Task 4 |
| **回归测试** | CLI 入口回归 | blm-plan 子命令既有 8 用例零破坏 | `tests/unit/interfaces/cli/test_agent_cli.py`（零修改回归） | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**（本 Story 主改动层——epics 钦定）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）——VO 扩展部分遵循
- [ ] **集成测试覆盖率 ≥75%**（epics 钦定）
- [ ] **关键路径覆盖率 100%**：六步类型化分派 / per-step 快照写入 / 校验失败降级三分支

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`，禁止 `--no-verify`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **BDD async 配合** | BDD 步骤函数不使用 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()`（模块级 event_loop fixture + `_run_async`） | context 数据丢失 |
| **延迟 import 纪律** | 本 Story 新交付模块一律步骤函数体内延迟 import | pytest 收集期 collection error |
| **真实服务清理** | teardown 链式清理：outbox 按 event_id 精确 DELETE / 检索 collection 删除 / Redis 键逐键精确删除（禁 flush）/ 端口覆写还原 | 跨场景污染 |
| **快照键隔离** | 并发场景 5 plan_id 用 UUID 前缀生成，per-step/latest 快照键按 plan_id 天然隔离 | 键冲突 |
| **性能场景缓存** | `_CachedEmbedding` 模块级缓存代理（embedding 查询去重——6-1 收敛先例 -98%） | 性能场景分钟级膨胀 |
| **xdist 分组** | 性能/采样场景全模块挂 `xdist_group("blm-planning-perf")`——**复用 6-1 组名**（R2 修订：pyproject addopts `-n auto --dist loadgroup` 为默认态，原钦定新组名 `market-insight-perf` 会与 6-1 旧组跨 worker 并行——冷启动 embed 并行抬双方 P95；共组使 6-1+6-2 全部采样场景全局同 worker 串行）；注：`_CachedEmbedding` 模块级缓存按文件隔离**不跨文件共享**，跨场景共享面是外部 embedding 服务——原"共享采样缓存"表述失实 | 采样冲突 |
| **事件清理** | 事件 outbox 登记入 context（`_outbox_event_ids`）供 teardown 精确删除 | 残留行 |
| **pytestmark** | 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis, ...]`（`market_insight` 文件名不含任何服务关键词、无自动 marker——必须显式声明全套 marker） | marker 漏打 |

**禁止行为：**
- ❌ 验收/集成测试 mock 真实服务（Fake LLM 唯一豁免——外部 SaaS；sandbox 替身须 `AsyncMock(spec=)` + 显式真实 dict return_value）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio` / pytest-xdist 并行时 BDD 步骤内 `asyncio.run()`
- ❌ autouse fixture 删除全局匹配资源
- ❌ `@pytest.mark.skip` 写死跳过（用 `pytest.skip()` 动态探测跳过）
- ❌ 修改阈值/规则消除告警；`# noqa`/`# type: ignore`/`# pylint: disable` 等抑制注释（红线）
- ❌ 裸 `pytest tests/`（会挂起——显式四目录：`pytest tests/unit tests/integration tests/contracts tests/acceptance`）

**验证要求：**
- [ ] `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance` 四目录全量通过（含 6-1 全部既有测试零回归）
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` / `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 六步类型化 Schema 定义与领域要素 | Task 0 | 0.1 Schema 规范定稿冻结 | feature（红） |
| AC-1 | 六类型化 Schema 实现 + SSOT 映射 | Task 2 | 2.1 Schema 实现 / 2.2 映射表 | `test_market_insight_schemas.py` |
| AC-1 | run_insight_step 类型化分派 | Task 3 | 3.1 分派改造 | `test_blm_planning_service.py` |
| AC-1 | 扁平化守卫（架构级） | Task 6 | 6.3 扁平化验证器 | `test_market_insight.py` |
| AC-1 | 类型化全链集成验证 | Task 5 | 5.1 场景① 领域要素键族逐步断言 | `test_integration_market_insight.py` |
| AC-2 | per-step 快照 VO/键契约 | Task 0 | 0.2 快照形态钦定 | feature（红） |
| AC-2 | InsightStepResult 扩展 | Task 1 | 1.1-1.2 红测与 structured_output 字段实现 | `test_blm_domain_models.py` |
| AC-2 | per-step 快照写入实现 | Task 3 | 3.3 快照写入 | `test_blm_planning_service.py` |
| AC-2 | 真实链读回验证 | Task 5 | 5.2 快照读回 | `test_integration_market_insight.py` |
| AC-3 | 事件零新增/负向断言 | Task 0 / Task 4 | 0.3 裁定 / 4.1 守护测试 | `test_event_channel_mapping_blm_planning.py` |
| AC-4 | 校验失败降级 | Task 3 | 3.2 降级路径 | `test_blm_planning_service.py` |
| AC-4 | 双杀注入采样 | Task 5 / Task 7 | 5.3 / 7.1 | 集成 + 验收 |
| AC-5 | 市场洞察段 P95<25s | Task 5 / Task 7 | 5.4b 性能采样 / 7.2 | 集成 + 验收（xdist_group） |
| AC-6 | 并发 5 任务 | Task 5 / Task 7 | 5.4a 并发场景 / 7.2 | 集成 + 验收 |
| AC-7 | gap 四字段全量传导 | Task 2 | 2.3 summarize 扩展 | `test_market_insight_schemas.py` |
| AC-7 | prompt 注入断言 | Task 7 | 7.2 验收 AC-7 场景 | `test_acceptance_market_insight.py` |
| 全 AC | 6-1 回归面适配 | Task 3 / Task 4 | 3.1 Fake 分派面同批适配 / 4.2 回归验证兜底（R1 修订） | 6-1 既有文件 |
| 全 AC | 架构约束验证 | Task 6 | 6.1~6.4 四验证器 | `test_market_insight.py` |
| 全 AC | 收尾完成清单 | Task 7 | 7.3 收尾场景 + 7.4 四目录回归 | 验收收尾 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7（全部规范面）

> **目的：** 在进入代码实现前，明确六类型化 Schema 字段级契约、per-step 快照形态、事件/异常/端口零新增裁定与验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定稿六类型化 Schema 字段级契约（按上文规范表逐字段定义：字段名/类型（限 str/float/list[str]、禁 Optional/None 默认值字段——R1 修订）/中文 description（领域语义）/**按 OD-8 产物化映射核对** or.md L386-415：or.md 产物名逐项映射到字段族，两处工具产物化（PESTEL/波特五力）附 delta 注记——非逐字核对；**SSOT 映射容器形态钦定（R3 补）= 形态 A 独立 dict `MARKET_INSIGHT_STEP_SCHEMA: dict[MarketInsightStep, type[BaseModel]]`**——不用 StepSemanticConfig 加 schema_cls 字段形态，避免配置表承载类型对象使耦合扩散，Task 2 循环 B 按此落笔）；冻结后登记于本 Story 文件（实现 Task 不得增删字段）
- [ ] Subtask 0.2: 钦定 per-step 快照形态：session_id = `f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step.value}"`、stage_id = `market_insight_{step.value}`、state_data **七键**契约（step/plan_id/summary/structured_output/degraded/degrade_reason/completed_steps——completed_steps 为含该步的 stage 值清单 `list[str]`，structured_output 键恒在恒 null，见数据模型节 R1 修订）、TTL 沿用 `CheckpointSnapshot` 既有默认 86400（6-3 升级 30 天）；登记端口文件序列化契约区（latest 两级契约外新增第三级）
- [ ] Subtask 0.3: 裁定事件面零新增（`CheckpointReached` 继续不发布）与异常面零新增（预留 483-489 说明）；偏离声明 OD-1~OD-8 落档（见 Dev Notes「关键架构决策」——R2 勘误：OD-8 已于 R1 新增，落档指令同步）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_market_insight.feature`（13~14 场景上限内**定稿钉死确定值**，AC 横幅分组——钉死后全文同步，禁范围值进入后续 Task）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_market_insight.py`（docstring 五段：模板基准声明/场景三属性分档表/门控档位/延迟 import 纪律/Run with + 隔离清单；模块级期望常量独立构造——六步领域要素键族禁经被测服务生成）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——预期运行期 `ImportError`（延迟 import 缺失类名）或 `AssertionError`，收集期零错误；记录失败形态）
- [ ] Subtask 0.7: 链路接线断言清单四项定义（组合根零 diff / 事件零新增 / per-step 快照真实链 / CLI 回归）
- [ ] Subtask 0.8: 留项裁定义务落档：deferred-work L125（SOP 白名单——裁定不注入+触发条件）与 6.1-DF2（稀疏检索——维持 deferred）台账更新
- [ ] Subtask 0.9: 既有资产复核：`InsightStepSchema` 移除的引用面清单（全仓 grep：`blm_planning_prompts.py`/`blm_planning_service.py` L339/6-1 测试 Fake 分派——作为 Task 2/3/4 的改动输入）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（Schema 字段表冻结 / 快照键契约 / 三零裁定）
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] OD-1~OD-8 落档 + deferred-work 台账更新

---

### Task 1: 领域层——`InsightStepResult` 扩展

**关联 AC:** AC-1 / AC-2（structured_output 承载面）

#### TDD 循环 A：信封扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/test_blm_domain_models.py`：structured_output 默认 None 兼容 / 正常填充（键 str + 值标量与 list[str]） / 值域违例抛 `EntityValidationError`（pydantic 对象、嵌套 dict、list[dict] 三类违例用例）/ 降级步语义约定 |
| 🟢 绿 | `src/domain/value_objects/blm_phases.py` `InsightStepResult` 就地新增字段 `structured_output`（类型注解 `dict[str, Any] | None = None`——签名移出表格单元格呈现，R2 修订：单元格内未转义管道符会裂列）+ `__post_init__` 值域守卫（纯标准库校验——isinstance 白名单 + 递归 list 元素检查） |
| 🟡 变异 | 删除守卫分支 → 值域违例用例红 → 还原绿 |
| 🔄 重构 | docstring 全中文 Google 风格更新（属性说明 + 降级语义 + **可哈希性注记**：新增 dict 字段使 frozen dataclass `hash()` 抛 TypeError——当前消费面不哈希信封，属潜伏性契约变化需 docstring 声明——R3 补）；`ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 VO 扩展失败测试（上述四组用例）
- [ ] Subtask 1.2: 🟢 绿 — 实现 structured_output 字段与值域守卫
- [ ] Subtask 1.3: 🟡 变异 — 守卫分支突变实证
- [ ] Subtask 1.4: 🔄 重构 — 注释/类型/命名收敛

**完成标准/Definition of Done:**
- [ ] VO 扩展完成，6-1 既有 38 用例零回归（带默认值向后兼容）
- [ ] 领域层零依赖复核（扩展后仍纯标准库）
- [ ] 覆盖率：VO 扩展分支 100%

---

### Task 2: 应用层 Schema 面——六类型化 Schema + SSOT 映射 + gap 四字段传导

**关联 AC:** AC-1 / AC-7

#### TDD 循环 A：六类型化 Schema

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `tests/unit/application/test_market_insight_schemas.py`：六 Schema 类存在性 / 每步领域要素字段齐备（期望字段名族**独立构造**——禁 import Schema 后反射自证恒真）/ 字段类型白名单（str/float/list[str]——与 Task 6 架构验证器双承载）/ 公共 summary+findings 双字段 / Field description 非空 |
| 🟢 绿 | `src/application/services/blm_planning_prompts.py` 按 Task 0.1 冻结契约实现六 Schema（pydantic BaseModel + Field(description=中文领域语义)）；**`InsightStepSchema` 暂留**（`__all__` 保序 + docstring 标注"deprecated——Task 3 六类型化切换后移除"；服务层零改动，本 Task 自然全绿——R1 修订：原钦定"本 Task 切 L339 查表"会使三处 6-1 Fake（unit 返回体/验收集成分派）即刻全红且 unit 适配不在任何任务清单，同时架空 Task 3 分派红测） |
| 🟡 变异 | 删除某步某领域要素字段 → 对应用例红 → 还原绿 |
| 🔄 重构 | description 措辞对齐 or.md 输出产物栏；`ruff` + `mypy` |

#### TDD 循环 B：schema 映射 SSOT + gap 四字段

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 同文件扩展：schema 映射六枚举键齐备且值互异（SSOT 映射形态已钦定——Subtask 0.1 形态 A 独立 dict `MARKET_INSIGHT_STEP_SCHEMA: dict[MarketInsightStep, type[BaseModel]]`，R3 去悬空引用）；`summarize_gap_for_downstream` 正常态含四字段全量文本 / 降级态 `[降级]` 标注不变 |
| 🟢 绿 | 实现映射表 + 扩展 `summarize_gap_for_downstream` 四字段（financial_gap/operational_gap/root_causes/portfolio_health——降级分支零改动） |
| 🟡 变异 | 映射表错配一步（trend→SelfInsightSchema）→ 用例红 → 还原绿；gap 摘要回退单字段 → 用例红 → 还原绿 |
| 🔄 重构 | 命名/类型注解收敛（`StepSemanticConfig` 若加字段须 frozen 兼容） |

- [ ] Subtask 2.1: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 六类型化 Schema（循环 A）
- [ ] Subtask 2.2: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — schema 映射 SSOT（循环 B）
- [ ] Subtask 2.3: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — gap 四字段全量传导（循环 B；**子串兼容钦定**：四字段摘要必须保留 `财务差距=` 中文标签子串——6-1 单测 `test_gap_normal_summary_injected_into_phase2_prompt` L533 以此子串断言，扩展为四字段（`财务差距=…；运营差距=…` 形态）时该子串存活则 Task 2 自然全绿成立，改英文键/改标签措辞则 Task 2 结束即红——R2 修订，消解 Task 2 DoD"自然全绿"的隐含条件）
- [ ] Subtask 2.4: 🔄 重构 — `InsightStepSchema` deprecated 标注（docstring + `__all__` 保序暂留）；消费面清单核对移交 Task 3（生产消费方 = 服务层 import L52/注解 L337/调用 L339 三位；tests 消费面 3 文件 19 位——unit 11 位/验收 6 位/集成 3 位，含验收 L931 `__name__ == "InsightStepSchema"` 字符串口径断言）；**Task 2 单测禁写 `__all__` 穷尽性/模块级全类反射穷尽断言**（deprecated 暂留期该形态必红——穷尽断言归 Task 3 移除后，R2 补）

**完成标准/Definition of Done:**
- [ ] 六 Schema + 映射 + gap 扩展全部实现，TDD 循环通过
- [ ] **Task 2 = 纯 prompt 面资产交付，服务层与测试面零改动，自然全绿**（R1 修订钦定：`InsightStepSchema` 暂留 deprecated；"L339 切表 + `InsightStepSchema` 移除 + 三处 Fake 适配（unit 返回体/验收分派/集成分派）"**整体归 Task 3 循环 A 同批承载**——服务切换与 6-1 回归面适配必须在同一 Task 红绿闭环内完成，拆到两个 Task 必产生中间全红态或恒绿红测）
- [ ] 应用层覆盖率≥85% 维持

---

### Task 3: 服务层——类型化分派 + per-step Checkpoint 快照

**关联 AC:** AC-1 / AC-2 / AC-4

#### TDD 循环 A：run_insight_step 类型化分派、InsightStepSchema 移除与三处 Fake 适配（R1 修订：同批承载）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/test_blm_planning_service.py`：六步各调用时传入的 response_schema 为该步类型化 Schema（Fake LLM calls 记录断言）/ 类型化结果填充 structured_output（model_dump 键域=Schema 字段族）/ 校验失败（Fake 返回不合 Schema 数据→pydantic 校验异常路径）→ 降级信封 + structured_output=None / 既有降级三规则与两级重试零回归 |
| 🟢 绿 | `run_insight_step` L339 调用点由硬编码 `InsightStepSchema` 改为 SSOT 映射查表；结果组装填充 `structured_output=validated.model_dump()`；校验失败走既有步级降级路径；**同批完成**：①移除 `InsightStepSchema`（prompts 定义 L40 + `__all__` + 服务 import L52/注解 L337）②unit Fake 分派与返回体按六 Schema 八键族适配（`is InsightStepSchema` 过滤断言 6 位 + `fail_schemas` 注入位同步）③6-1 验收/集成 `_make_fake_llm` 分派面三 Schema 族扩展为八键族（GapAnalysis + 六类型化 + InsightSynthesis；验收 L931 字符串口径断言同步）——服务切换与三处 Fake 适配必须同一提交闭环（中间态必全红，R1-2 裁定——R2 勘误：原悬空编号"R1-F2"） |
| 🟡 变异 | 映射查询回退固定 Schema → 六步分派用例红 → 还原绿；structured_output 填充删除 → 填充用例红 → 还原绿 |
| 🔄 重构 | 类型注解（`type[BaseModel]`）/docstring 更新 |

#### TDD 循环 B：per-step Checkpoint 快照写入

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 同文件扩展：每步完成时额外 save 一份 per-step 快照（session_id 后缀 `:{step.value}` / stage_id=`market_insight_{step.value}` / state_data 七键契约——R2 勘误：原"六键"系 R1-6 漏改残留）/ 降级步同样触发（degraded 标记入 state_data）/ 快照写入异常被吞且记日志（容错——AsyncMock 抛异常，流程不中断，后续步骤正常）/ latest 快照 save 调用形态与 6-1 一致（既有用例零回归） |
| 🟢 绿 | `_write_snapshot_and_publish` 扩展或新增私有助手 `_write_step_checkpoint(context, step, result)`：构造 per-step `CheckpointSnapshot` 经既有 `self._snapshot_repository.save()` 写入（零新依赖注入——repository 已在） |
| 🟡 变异 | per-step 写入调用删除 → 用例红 → 还原绿；session_id 后缀删 → 键形态断言红 → 还原绿 |
| 🔄 重构 | 与 `_write_snapshot_and_publish` 的职责边界注释（latest=读侧状态面 / per-step=6-3 恢复点位面） |

- [ ] Subtask 3.1: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 类型化分派、structured_output 填充、`InsightStepSchema` 移除与三处 Fake 适配（循环 A——R1 修订同批承载）
- [ ] Subtask 3.2: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — 校验失败降级路径（循环 A）
- [ ] Subtask 3.3: 🔴 红/🟢 绿/🟡 变异/🔄 重构 — per-step 快照写入（循环 B）

**完成标准/Definition of Done:**
- [ ] 服务层三分支（正常/降级/快照容错）关键路径 100% 覆盖
- [ ] 6-1 既有 service 单测 **38** 用例零回归（信封构造兼容 + latest 行为不变 + Fake 分派面适配后全绿；R1 修订：原文"37"失实——以运行时收集数为准）
- [ ] **6-1 验收 14 场景/集成 4 场景在 Fake 适配同批完成后全绿**（R1-2 裁定的提交闭环判据——服务切换/移除/三 Fake 适配同一提交，Task 3 结束时点无中间红窗口）
- [ ] `ruff` + `mypy` 通过

---

### Task 4: 接线守护与 6-1 回归面适配

**关联 AC:** AC-3 / 全 AC 回归

> **性质说明：** 本 Task 是 SDD 规范验证（守护型）+ 适配器契约变更回归面（记忆纪律：改共享契约后全仓 grep 消费方测试，禁只跑直接文件）。

- [ ] Subtask 4.1: 扩展 `tests/contracts/test_event_channel_mapping_blm_planning.py`：零新增守护（event_channels.yaml 与 DEFAULT_MAPPINGS 无 market-insight 新键——快照键非事件键，负向断言 BLM 事件族仍仅 PlanningStarted/BlmStageCompleted/StrategicDeviationWarning）+ `CheckpointReached` 负向源码 grep 沿袭
- [ ] Subtask 4.2: **6-1 回归面全量验证**（R1 修订：Fake 分派面/返回体适配已在 Task 3 循环 A 同批落码，本 Subtask 为验证+缺口兜底）：6-1 验收 14 场景/集成 4 场景/单测 38 用例在八键族分派下全绿；断言面核查（InsightStepResult 构造含新默认字段零破坏，findings/summary 语义未变；验收 L931 字符串口径断言已同步）；发现适配缺口即回补（兜底，主责在 Task 3）
- [ ] Subtask 4.3: 组合根零 diff 复核 + `test_port_contract_blm_planning.py` 零修改回归 + CLI `test_agent_cli.py` 8 用例回归
- [ ] Subtask 4.4: 范围限定 grep `InsightStepSchema` 残留清零（**范围 = `src/` 与 `tests/`**：`grep -rn InsightStepSchema src/ tests/` 零输出——含字符串口径 `__name__ == "InsightStepSchema"` 断言位；**`_bmad-output` 两份 Story 文档中的历史引用是记录性审计轨迹、明确不在清零范围**——R2 修订：原"全仓 grep"字面会诱导 dev 删改 6-1 Story 审计记录）

**完成标准/Definition of Done:**
- [ ] 6-1 全部既有测试零回归通过（R1 修订按 HEAD 实测逐文件列基线，**以运行时收集数为准**：验收 14 场景 / 集成 4 场景 / 单测 domain models 38（31 函数含 8 值参数化）、service 38、exceptions 15、use_cases 18、arch 13 / 契约 端口契约 11（9 函数含 ×3 参数化）、事件通道 8 / CLI blm-plan 块 8——原文"38+37+17/契约 11+8"计数失实且两文件对调）
- [ ] 守护测试通过（事件零新增/组合根零 diff）
- [ ] `InsightStepSchema` 在 src/ 与 tests/ 零残留（范围限定口径——同 Subtask 4.4，_bmad-output 记录性引用除外）

---

### Task 5: 集成测试——真实链四场景

**关联 AC:** AC-1 / AC-2 / AC-4 / AC-5 / AC-6

> **模式：** 6-1 `test_integration_blm_planning.py` 同款——真实 Redis/真实守卫链/真实实例化/真实档案加载/真实工具链/真实检索（门控 `_ensure_retrieval()` 双探测 skip）/真实图引擎 + **Fake LLM 唯一豁免**；`try/finally` 自包含（teardown：`_dispose_retrieval` + outbox 按 event_id 精确 DELETE + Redis 键逐键删除）。

- [ ] Subtask 5.1: 场景① 类型化全链：真实链完整跑通，六步 structured_output 领域要素键族逐步断言（期望键族独立构造）
- [ ] Subtask 5.2: 场景② per-step 快照读回：`snapshot_repository.load()` 逐键读回 6 份 per-step 快照 + latest，stage/state_data（七键契约含 plan_id 归属锚）/**版本写读一致**断言（R2 修订措辞：服务构造 `CheckpointSnapshot` 不传 state_version——实体默认 0 且无递增语义，断言口径 = 写读一致为 0，非版本递增）；outbox 零 CheckpointReached 负向（行筛选路径 `payload->'payload'->>'plan_id'`——AC-3 R1 修订）
- [ ] Subtask 5.3: 场景③ 降级：双杀注入（相邻两步的两 Schema 按 response_schema 身份恒败——AC-4 R1 钦定注入键；集成 Fake 需扩展 schema 身份注入参数）→ 恰两步降级、信封完整、per-step 快照含降级标记、20 轮采样成功率 100%（信封完整口径）；**采样轮边界钦定（R2 补）**：①每轮新铸 plan_id（`run_blm_planning` execute 内 uuid——禁固定 plan_id 复用，第 2 轮起触发 482 重跑守卫全轮炸）②20 轮采样用 recorder 总线口径（6-1 场景④先例——真实发布形态下 20×9=180 outbox 行的清理成本无谓）③快照键清理：采样轮 latest/per-step 键沿 6-1 先例 TTL 86400 吸收（20 轮 × 7 键 ≈ 140 键不逐删），断言场景（5.2/并发）才逐键精确删除
- [ ] Subtask 5.4a: 场景④-A 并发正确性：5 个不同 plan_id（UUID 前缀）`asyncio.gather` 全成功 + 互不串扰（per-step 键/outbox 计数按 `payload->'payload'->>'plan_id'` 逐 plan 断言；**总线形态钦定（R3 补）= 真实 publisher + 真实 PG outbox，装配沿 6-1 集成场景③ 先例**（clear_singleton + resolve("event_publisher") 覆写 + PG 双预检 skip + event_id 收集 teardown 批量 DELETE）——默认 recorder 装配零落行会使 outbox 断言空真，禁止弱化为 recorder 计数；**per-plan 预期计数钉死 = 9 行**（PlanningStarted×1 + BlmStageCompleted×8；AgentDecided 由引擎发布且 payload 无 plan_id 子键、两级路径过滤天然排除），5×9=45 行逐 plan 分组计数）——**不断言 P95**（R1 修订：并发争用延迟与 AC-5 单任务串行口径不同质，混测即口径污染）
- [ ] Subtask 5.4b: 场景④-B 性能采样：市场洞察段 P95<25s 独立串行采样（**≥20 轮**，`_CachedEmbedding` 缓存代理，Fake LLM 管线开销口径——docstring 声明 OD-3 口径差；观测点 = timeline 两端 started_at/completed_at，AC-5 R1 修订；**采样轮 task 文本固定**（6-1 场景④ 同款）——query 文本恒同是模块级缓存命中前提，每轮换 task 文本则 140 次 embed 全 miss，25s 门禁假红——R3 补）
- [ ] Subtask 5.5: 验证型变异：对 5.1 领域要素断言与 5.2 键形态断言做突变注入-还原实证（集成层断言活体证明）

**完成标准/Definition of Done:**
- [ ] 四场景全部通过（检索不可达环境动态 skip）
- [ ] 性能场景 xdist_group 串行无采样冲突
- [ ] 集成覆盖率≥75% 维持

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-1（扁平化）/ 六边形架构全局

> **性质说明：** 本 Task 是 **SDD 规范验证测试**（验证架构/约束是否被遵守），非 TDD 单元测试。

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_market_insight.py` 验证器 A——domain 零依赖：扩展后 `blm_phases.py` AST/import 扫描零第三方（沿 6-1 `test_blm_planning_arch.py` 验证器 A 形态）
- [ ] Subtask 6.2: 验证器 B——Schema 落位：六类型化 Schema 仅存在于应用层 `blm_planning_prompts.py`，`src/domain/` 全目录零 pydantic import（结构断言 + 源码 grep 双形态）
- [ ] Subtask 6.3: 验证器 C——**扁平化守卫**（本 Story 特有）：反射遍历六 Schema 全部字段，类型白名单 **{str, float, list[str]}** 断言（与 AC-1/OD-5 声明面同集——R1 修订：原 `{str, float, int, list[str]}` 含 int 与声明面口径分裂，int 字段可穿透验证器绿而 AC-1 红；`model_fields` 注解解析——嵌套 BaseModel/list[dict]/Optional 即红）
- [ ] Subtask 6.4: 验证器 D——服务分派零硬编码：`run_insight_step` 源码不含六 Schema 类名字面量（分派仅经 SSOT 映射——grep 负向断言，防 if-else 硬编码回潮）
- [ ] Subtask 6.5: 运行完整测试套件并生成报告（四目录全量）

**完成标准/Definition of Done:**
- [ ] 四验证器通过，任何违规即测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-7 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已建 N 场景（N = Subtask 0.4 定稿钉死值，红阶段已验证）；本 Task 补充收尾场景 |
| 🟢 绿 | 实现全部 BDD 步骤（真实服务装配链对齐 6-1 helper 族：`_assemble_blm_chain` 形态复用/扩展），全场景转绿 |
| 🟡 变异 | 验收级断言抽检突变（领域要素键族断言/per-step 键形态断言/负向断言各一） |
| 🔄 重构 | 收敛场景命名、统一断言表达（断言消息含实测值 + 规则锚——6-1 风格） |

- [ ] Subtask 7.1: AC-1~AC-4 场景全绿（类型化输出×3 / per-step 快照×3 / 事件分立×1 / 降级 单点+双杀×2——R3 勘误：原"降级双杀×2"标签致单点覆盖丢失）
- [ ] Subtask 7.2: AC-5~AC-7 场景全绿（性能 P95 / 并发 5 / gap 四字段传导×2——正常+降级标注，R3 钉 2 场景与分化维度表同步）
- [ ] Subtask 7.3: 收尾场景——src 完成清单（六 Schema/VO 扩展/服务改造/端口契约登记）+ 四测试目录完成清单（本 Story 测试分类表全文件存在性）逐项断言
- [ ] Subtask 7.4: 四目录全量回归（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`）+ `ruff check` + `mypy` 收尾校验
- [ ] Subtask 7.5: deferred-work 台账最终更新（本 Story 新增留项若有——如真实 LLM 口径、SOP 白名单触发条件）

**完成标准/Definition of Done:**
- [ ] src 与四测试目录完成清单逐项验证确认
- [ ] 开发结束验收测试通过（含 6-1 零回归）
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（双通道）+ LangGraph 图编排（`SpBlmGraph` 8 节点纯顺序）
- **设计约束:** 领域层零依赖（import-linter 强制）；pydantic 仅应用层/基础设施层边界；`@dataclass(frozen=True)` + `dataclasses.replace` 不可变更新
- **接口治理:** 统一端口注册（PortSpec：name/version/interface/impl/module/lifetime/owner/compatibility/tags）、Registry/Resolver/ContractGate、组合根唯一装配、契约优先
- **技术栈:** Python 3.11+ / LangGraph 1.0.9+ / pydantic V2 / Redis 7.0+ / pytest-bdd
- **系统公理二（外部化记忆）:** L3 压缩触发 = Checkpoint 创建 → StrategicArchive——**归 6-3**；6-2 仅铺 per-step 恢复点位（骨架）

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | Checkpoint 边界：6-2 落**触发面骨架**（per-step 快照，复用 1-14a/1-15 交付的 CheckpointSnapshot + SnapshotRepositoryProtocol + RedisSnapshotStore 基建）；6-3 落机制完整面（PersistentNoteTaker 持久化笔记/上下文压缩≥70%/persistent_note_ref 强制关联/CheckpointReached 发布/Replay-Override 恢复/msgpack-SHA256-TTL30 天完整形态）；6-2 保持 CheckpointReached 不发布（负向断言沿 6-1 AC-4 / 5-10 OD-6 先例） | architecture.md §11.2.12 L1587「Checkpoint 持久化由 Epic 6/Story 6.3 实现」+ 6-1 边界表 + epics 6.2/6.3 两 Story 定义并读 |
| **OD-2** | 第 6 步口径 = **机会差距分析**（非 core-domain §17.4.2 的"看风险"过时表述——6-1 OD-2 已裁定架构稿不采用，本次直接继承） | or.md 五.2.(2) L386-415 权威序 + prd.md FR-SP-02 |
| **OD-3** | P95<25s 口径 = **市场洞察段**（六子步骤+synthesis）Fake LLM 管线开销；真实 LLM 延迟显式出栈，口径差声明落测试 docstring；真实计时归 6.1-DF1 部署验证 | 6-1 DC-7 先例 + epics L2100「市场洞察执行延迟」语义（非全流程；R1 勘误：原引 L2099 为标题行，off-by-one） |
| **OD-4** | 并发 5 任务 = 5 个**不同 plan_id**；同 plan_id 并发 482 竞态窗口归 7-2 | 6.1-DF6 成文（R3-2 三项之一） |
| **OD-5** | 类型化 Schema **扁平化强制**：字段仅 str/float/list[str]，禁嵌套 | GLM-5.3 anthropic 端点嵌套 Schema 服务端栈溢出（litellm_llm_client.py L631-637 注记） |
| **OD-6** | gap 四字段全量传导（执行 6-1 **代码审查** R2-3 成文裁定：扩展 `summarize_gap_for_downstream`——"四字段全量传导归 6-2 类型化 Schema 消费面定夺"） | 6-1 代码审查 R2-3 + 看自己/机会差距分析步需 gap 数据 |
| **OD-7** | 测试文件命名：unit/architecture 用 epics 钦定 `test_market_insight.py`（恰为功能名族）；integration 调整为 `test_integration_market_insight.py`（仓规 `test_integration_` 前缀——6-1 先例）；acceptance `test_acceptance_market_insight.feature/.py`；**禁止故事编号后缀** | 6-1 OD-1 先例 + 记忆「禁止故事编号命名文件」 |
| **OD-8** | **输出产物工具产物化映射**（R1 新增）：六 Schema 必含领域要素以 or.md L386-415 输出产物栏为基准，其中两处以方法论工具产物化替换——看趋势"宏观趋势报告"→"PESTEL 六维度评估"（or.md 建议工具栏 L389 产物化，结构化粒度改进）、看竞争"行业竞争结构图"→"波特五力五维评估"（L399 同理）；"图/报告"类产物（价值主张地图/增长路径图/机会差距量化报告/雷达图）以**要点字段族**承载，图本体生成归 6-5 报告面；要素命名与 or.md 原产物名逐字对齐（尾词不漂移；**空格归一例外**：or.md"能力 - 机会匹配矩阵"连字符两侧空格在本文档归一为"能力-机会匹配矩阵"——R2 注记，实害为零仅声明精度） | R1 审查发现：原表头声称"or.md 输出产物推导"但六步中五步改写（工具名替换×2/尾词漂移×5），下游 6-5/6-7 以本表为契约源做 or.md 引文锚会引用不存在的产物名——溯源链源头断裂 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/
│   ├── value_objects/blm_phases.py          ▲ InsightStepResult 扩展 structured_output（Task 1）
│   └── exceptions/planning_exceptions.py    = 零改动（483-489 预留不占用）
├── application/
│   ├── ports/blm_planning.py                ▲ 序列化契约区扩展 per-step state_data 键契约（Task 0）
│   ├── services/
│   │   ├── blm_planning_prompts.py          ▲ 六类型化 Schema 新增 + InsightStepSchema deprecated 暂留（Task 2；移除归 Task 3——R2 勘误：原标 Task 2 与 R1-2 边界裁定矛盾）+ SSOT 映射 + gap 四字段（Task 2）
│   │   └── blm_planning_service.py          ▲ run_insight_step 类型化分派 + per-step 快照写入（Task 3）
│   └── use_cases/                           = 零改动
├── infrastructure/
│   ├── agent_orch/graphs/sp_blm_graph.py    = 零改动（六节点闭包同构——类型化对图透明）
│   └── storage/redis/redis_snapshot_store.py = 零改动（键=build_key(namespace, session_id)——per-step session_id 天然区分）
├── interfaces/                              = 零改动
└── composition_root.py                      = 预计零 diff（Task 4 守护验证）

tests/
├── unit/
│   ├── domain/test_blm_domain_models.py             ▲ 扩展（Task 1）
│   ├── application/
│   │   ├── test_market_insight_schemas.py           ★ 新建（Task 2）
│   │   └── test_blm_planning_service.py             ▲ 扩展（Task 3）
│   └── architecture/test_market_insight.py          ★ 新建（Task 6，epics 钦定名）
├── integration/test_integration_market_insight.py   ★ 新建（Task 5）
├── contracts/
│   ├── test_event_channel_mapping_blm_planning.py   ▲ 扩展守护（Task 4）
│   └── test_port_contract_blm_planning.py           = 零修改回归（Task 4）
└── acceptance/
    ├── test_acceptance_market_insight.feature/.py   ★ 新建（Task 0/7，R6 模板）
    └── test_acceptance_blm_planning.py              ▲ Fake 分派面适配（Task 3 同批，6-1 资产演进——R1 修订：仅 .py，.feature Gherkin 文本零改动）

configs/event_channels.yaml                  = 零 diff（守护）
_bmad-output/implementation-artifacts/deferred-work.md  ▲ 留项裁定更新（Task 0/7）
```

（▲ 修改 / ★ 新建 / = 零改动 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——R1 审查后逐行核验修正；行号基准 HEAD@d1af99bd，实施前以 Task 0.9 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| `InsightStepResult` | `src/domain/value_objects/blm_phases.py:198` | 九字段现状（step/summary/findings/tool_used/evidence_refs/degraded/degrade_reason/started_at/completed_at）——扩展基线 |
| `InsightStepSchema`（待移除） | `src/application/services/blm_planning_prompts.py:40` | 两字段（summary/findings）；生产唯一调用点 `blm_planning_service.py:339` |
| `StepSemanticConfig` | `src/application/services/blm_planning_prompts.py:58` | 六字段 frozen dataclass（step_key/display_name/role_prefix/tool_candidates/retrieval_query_template/output_focus；R1 勘误：装饰器 L58/类 L59，原引 L56 偏 -2） |
| `MARKET_INSIGHT_STEP_CONFIG` | `src/application/services/blm_planning_prompts.py:94` | 六步语义配置 SSOT（中文显示名工具口径——勿改回 slug，6-1 R1 教训） |
| `_structured_call_with_retry` | `src/application/services/blm_planning_service.py:489` | **已参数化 schema_cls**——天生支持 per-step Schema，改造仅传参 |
| `_write_snapshot_and_publish` | `src/application/services/blm_planning_service.py:653` | latest 快照 + BlmStageCompleted（失败不阻断）——per-step 写入的相邻扩展位 |
| 快照键构造 | `src/infrastructure/storage/redis/key_builder.py:11`（定义）+ `redis_snapshot_store.py:111`（save 内调用点） | `build_key(namespace, *parts)` 产出 `sisys:{namespace}:{parts 用 : 连接}`——**键仅由 session_id 决定，stage_id 不参与键**；session_id 内部冒号原样保留（per-step session_id `blm-planning-{plan_id}:{step}` → 键 `sisys:snapshot:blm-planning-{plan_id}:{step}` 可实现——R1 修订双锚：原单引 :111 未区分定义/调用点） |
| `BLM_PLANNING_SESSION_PREFIX` | `src/application/ports/blm_planning.py:40` | `"blm-planning-"` 单源常量（per-step session_id 复用此前缀） |
| `summarize_gap_for_downstream` | `src/application/services/blm_planning_prompts.py:280` | 现仅传导 financial_gap 单字段（L295——R1 勘误：原引 L293 实为 degrade_reason 读取行）——四字段扩展点 |
| `STAGE_VALUE_DOMAIN` | `src/domain/value_objects/blm_phases.py:64` | 8 值 frozenset（零扩展——守护） |
| 温度档 | `blm_planning_prompts.py` `BLM_TEMPERATURE_PROFILE` | 8 步温度（零改动） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-1 BLM 前两阶段流程](./6-1-blm-first-two-phases.md)（5 轮代码审查 R1~R5 收敛 + 性能优化收敛）

**关键学习/Key Learnings:**
- **属性形态断裂族（两犯 R1-1/R2-1 + 三重掩盖形态）**：`getattr(item,"text")` vs TypedDict 键（R1-1）/ `tool.name` vs `ToolMetadata.tool_name`（R2-1——6-1 原文"三重掩盖"指掩盖层数非次数，在案缺陷两例）——**跨对象取属性前先核对该类型真实字段形态**；本 Story `structured_output=validated.model_dump()` 与 Fake LLM 返回构造同理（Fake 返回 dict 键族必须与 Schema 字段族原子对齐）
- **断言判别力**：禁恒真断言（any()/键存在/循环自证）；期望值**独立构造**禁经被测服务生成；本 Story 六步领域要素键族常量独立定义
- **双杀注入**：单点失败注入可能被重试兜住（20 轮 degraded 恒 0 教训）——降级验证必须相邻两步 {k,k+1} 同时注入 + "每轮恰 N 降级"鉴别锚
- **工具候选口径**：中文显示名（与 `ceo_agent.yaml allowed_tools` 及 `get_tool(tool_name=)` 同口径）——6-2 勿动 tool_candidates，白名单名必已注册（R3-3 生产不可达前提）
- **Fake LLM 分派键 = response_schema 身份**：6-1 Fake 只认三 Schema——本 Story 六新 Schema 上线 = 6-1 Fake 必失配（**Task 3 服务切换同批适配**三处 Fake（unit 返回体/验收/集成分派）+ Task 4 验证兜底——R2 勘误：原"Task 4 强制适配"与 R1-2 边界裁定矛盾，最大回归风险点）
- **BDD 三件套**：模块级 event_loop + context dict fixture + `_run_async`；teardown 五步链"断言失败也执行"（K8 先例）
- **性能场景 embedding 缓存**：`_CachedEmbedding` 模块级缓存代理（-98%）——性能/并发场景必配
- **图身份锚**：图挂载双点漏分支会静默回退 BasicAgent——本 Story 图零改动，但集成测试保留图身份断言
- **红线三处漏网教训**（R5）：tests 中 `# type: ignore[method-assign]` 用 stub 属性根因修复——本 Story 全程零抑制注释

**应用到本故事/Applied to This Story:**
- [ ] Task 3 Fake 分派面适配清单化（三处：unit 返回体 + 6-1 验收/集成双文件——R2 勘误归属）；Task 4 回归验证兜底
- [ ] 领域要素期望键族独立构造（验收/集成/单测三面）
- [ ] 双杀注入降级验证（AC-4）
- [ ] 性能场景 `_CachedEmbedding` + xdist_group 串行
- [ ] 全程禁抑制注释 + 提交信息禁 AI 署名

### 其他约束速查

- **风险集中登记（R1 补）**：①最大回归风险 = 6-1 三处 Fake 适配（Task 3 同批承载，漏 unit 即全红）；②键形态风险 = per-step/latest 双契约共存（读侧判别规则见 state_data 七键契约）；③口径风险 = 白名单两层/P95 串行口径/outbox 两级路径（各 AC 已钦定，禁混）；④覆盖率风险 = application ≥85% 主改动层维持
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore；提交信息禁 AI 署名（`Co-Authored-By` 等）
- **覆盖率**：整体≥80% / domain≥90% / application≥85%（主改动层）/ 集成≥75%
- **验收/集成禁 mock**（真实服务优先 + `pytest.skip()` 动态跳过；Fake LLM 唯一豁免——外部 SaaS；sandbox 替身 `AsyncMock(spec=)` + 显式真实 dict）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-01 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.2 L2079-2118） |
| **架构文档** | `docs/architecture/architecture.md`（§8/§10/§17.5/L1587） |
| **需求权威** | `_bmad-output/planning-artifacts/or.md`（五.2.(2) L386-415）+ `prd.md`（FR-SP-02 L1869） |
| **Checkpoint 设计** | `docs/architecture/sisys-checkpoint-timetravel-design.md`（§2.1——6-3 范围边界依据） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-1-blm-first-two-phases.md` |
| **留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L125/L327/L326-332） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 6.2 节）
- [x] 架构约束从 `architecture.md` + 4 份子设计文档提取
- [x] 前一个故事学习经验整合（6-1 五轮审查 + 性能收敛 + 边界表）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0~7 / 40 Subtask——R1 修订：原"29+"概数失实，逐行点数 0.1-0.9/1.1-1.4/2.1-2.4/3.1-3.3/4.1-4.4/5.1-5.3+5.4a+5.4b+5.5/6.1-6.5/7.1-7.5）
- [x] 项目结构对齐统一规范（六类型化 Schema 扁平化 / per-step 快照键契约 / 三零裁定）
- [x] 五 Agent 并行调研（前故事情报/现有代码/架构文档/验收风格/端口异常体系）+ 关键代码事实独立核验

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-2-market-insight-six-substeps.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `tests/unit/application/test_market_insight_schemas.py` - 六类型化 Schema 单测（Task 2）
- `tests/unit/architecture/test_market_insight.py` - 架构验证四验证器（Task 6）
- `tests/integration/test_integration_market_insight.py` - 集成四场景（Task 5）
- `tests/acceptance/test_acceptance_market_insight.feature` - Gherkin 场景（Task 0）
- `tests/acceptance/test_acceptance_market_insight.py` - BDD 步骤实现（Task 0/7）

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/domain/value_objects/blm_phases.py` - InsightStepResult 扩展（Task 1）
- `src/application/services/blm_planning_prompts.py` - 六 Schema/映射/gap 扩展（Task 2）
- `src/application/services/blm_planning_service.py` - 类型化分派 + per-step 快照（Task 3）
- `src/application/ports/blm_planning.py` - 序列化契约区扩展（Task 0）
- `tests/unit/domain/test_blm_domain_models.py` / `tests/unit/application/test_blm_planning_service.py` - 扩展（Task 1/3）
- `tests/contracts/test_event_channel_mapping_blm_planning.py` - 守护扩展（Task 4）
- `tests/acceptance/test_acceptance_blm_planning.py` / `tests/integration/test_integration_blm_planning.py` - Fake 分派面适配（**Task 3 同批**——R2 勘误：原标 Task 4 会复活中间全红窗口；Task 4 仅回归验证兜底）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 留项裁定更新（Task 0/7）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.2 |
| **Story Key** | 6-2-market-insight-six-substeps |
| **File** | `_bmad-output/implementation-artifacts/stories/6-2-market-insight-six-substeps.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力 |
| **优先级** | P0-2 |
| **覆盖 FR** | FR-SP-02 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/扁平化/Checkpoint 边界/事件与异常三零裁定）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-1 五轮审查教训全量应用）
5. [x] Sprint status synced to `ready-for-dev`（sprint-status.yaml L179 已同步——R1 修订勘误）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | AC-4"双杀注入 {k,k+1}"按调用序算术失实：验收/集成 Fake 注入键=调用序且重试同占序号，相邻两步真降级需 4 序号；20 轮采样下序号累计漂移 | P1 | 注入键钦定按 `response_schema` 身份（`fail_schemas` 语义移植验收/集成 Fake——schema 恒败轮无关）；与 6-1 代码审查 R1-8"双杀"同词不同义显式声明（AC-4/Subtask 5.3 双口径） |
| R1-2 | Task 2 DoD"L339 切表"与 Task 3 循环 A 绿双钦定同一改动；切表后三处 6-1 Fake（unit 返回体两字段构造/验收集成分派）即刻全红且 unit 适配不在任何任务清单；Task 3 分派红测恒绿 | P1 | Task 2 收缩为纯 prompt 面（`InsightStepSchema` 暂留 deprecated、服务零改动、自然全绿）；"切表+移除+三处 Fake 适配"整体归 Task 3 循环 A 同批承载；Task 4.2 降级为回归验证+缺口兜底 |
| R1-3 | AC-6/AC-3 outbox 断言主键 `payload->>'aggregate_id'` 失实：`BlmStageCompleted.aggregate_id` 实测=agent_id 非 plan_id（5 任务共享 CEO agent 不可分离，且无 agent_id 时随机 uuid4）；`plan_id` 实位于 to_dict 的 payload 子字典 | P1 | 主键改 `payload->'payload'->>'plan_id'` 两级 JSONB 路径（6-1 集成既有先例 `->'payload'->>'stage'` 同构）；AC-3/AC-6/5.2/5.4a 四处同步 |
| R1-4 | or.md 溯源口径失实：Schema 表头声称"L386-415 输出产物推导"但六步中五步改写（工具名替换×2/尾词漂移×5/丢"核心能力"）；"增长路径建议"与被 OD-2 判过时的 core-domain 措辞雷同 | P2 | 新增 OD-8 工具产物化映射（两处工具产物化 delta 注记 + 图/报告类以要点字段族承载）；要素列与 AC-1 checklist 回正 or.md 原产物名；Subtask 0.1 核对口径改"按 OD-8 映射核对" |
| R1-5 | 字段类型白名单三处口径分裂（AC-1 str/float/list[str] vs VO 守卫含 int/bool vs 6.3 验证器含 int）；Optional 字段 model_dump 产 None 会炸守卫且在降级 try/except 之外 | P2 | 声明面统一 str/float/list[str]（6.3 删 int、补 Optional 即红）；VO 守卫两层显式声明（纵深防御刻意宽一格）；扁平化强制补禁 Optional/None 默认值 |
| R1-6 | per-step state_data 六键契约歧义：completed_steps 双读法（计数 vs 清单）、缺 plan_id 归属锚、structured_output 键恒在性未钉 | P2 | 六键→七键（补 plan_id）；completed_steps 钉"含该步的 stage 值清单 list[str]"；structured_output 键恒在恒 null；读侧判别规则注记；TTL 86400 与 6-3 升 30 天关系注记 |
| R1-7 | Subtask 5.4 并发 5 任务与 P95<25s 同场景互相污染（并发争用延迟≠单任务串行口径）；AC-5 观测点未指明（InsightSynthesis VO 无时间戳）；n=10 时 P95≡最大值 | P2 | 拆 5.4a 并发正确性（不断言 P95）/5.4b P95 独立串行采样；观测点钦定 timeline 两端；采样下限 ≥20 轮 |
| R1-8 | `BlmPlanningServicePort`"既有四方法"失实（实测六方法，漏 project_timeline/project_degraded_steps）；端口清单 LLMClientPort 行形态不齐 | P2 | 改"六方法（四执行+两投影），仅 run_insight_step 扩展"；LLMClientPort 行补注册名/版本/行号 |
| R1-9 | 6-1 测试计数失实族："37 用例"（实测 38）、"38+37+17"（17 无对应文件）、"契约 11+8"两文件计数对调、漏 use_cases/arch/CLI 三面 | P2 | Task 3/Task 4 DoD 按 HEAD 实测逐文件列基线 + "以运行时收集数为准"；测试分类表回归行具名 |
| R1-10 | 锚点表四处失实：StepSemanticConfig L56（实测 L58/L59）、gap 单字段 L293（实测 L295）、build_key 单引调用点（定义在 key_builder.py L11）、OD-3 引 epics L2099（实测 L2100）；与"已独立核验"声明矛盾 | P2 | 四处更正 + build_key 双锚 + 锚点表标题改"HEAD 基准 + Task 0.9 复核"注记 |
| R1-11 | 追溯矩阵漏 AC-1/Task 5 行（Subtask 5.1 无归属）；AC-2 行 subtask 引用精度（1.1→1.1-1.2）；AC-5/6/7 Task 7 侧无编号；收尾行漏 7.4 | P2 | 补 AC-1/Task 5 行；四处 subtask 引用精化；F2 重划后 6-1 回归面行改 Task 3/Task 4 双承载 |
| R1-12 | 边界表节标题"6-1 边界表钦定"罩住全表六行，实测仅两行出自边界表（性能行出自 epics、传导行出自 R2-3） | P2 | 节标题出处逐行声明 + 表内"面（出处）"列逐行标注 |
| R1-13 | 测试分类表缺 CLI 回归行；"回归测试"行无具体文件名 | P2 | 补 CLI 行（零修改回归）；回归行具名三文件 + Task 3/4 双归属 |
| R1-14 | P3 杂项批：Task 0 红形态"收集失败"与延迟 import 纪律矛盾（实为运行期 ImportError）；Lessons"三犯"实为两犯+三重掩盖；"13~14 场景"范围值未钉死；6-1 R1-8/R2-3 编号缺审查轮命名空间；"29+ Subtask"概数；Sprint 勾选失实；.feature 适配归属错标；pytestmark 自问自答式；L125 锚词与台账不一致 | P3 | 逐项修正（红形态统一"运行期 ImportError/收集期零错误"；两犯勘正；0.4 钉死注记；"代码审查 R"前缀；40 Subtask 点数；勾选勘误；结构图仅 .py；陈述化；锚词对齐"工具候选矩阵深化"） |

> **Round 1 审查方法记录**：四视角并行调研（服务层 VO/快照基建组合根/6-1 测试资产/规划文档一致性）+ 双评审员并行审查（科学性正确性可行性 / 一致性完备性结构性）+ 主会话独立取证定谳（outbox payload 嵌套形态、build_key 冒号保留实测、评审员误报 2 例驳回）。误报驳回记录：调研 Agent 判"per-step 键形失实"系将 Story 目标态误读为现状声称（AC-2 括号内已注明 session_id 后缀机制，build_key 实测支持）；评审员 B 对计数的"17"溯源（use_cases 18/arch 13/exceptions 15 均不匹配）确认为 6-1 创建期陈旧值。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-1 | R1-2 Task 边界重划的传播漏网 5 处：循环B 红行"六键"残留、结构树 Lessons/File List 三处"Task 4 适配"旧归属（File List 残留会复活中间全红窗口——服务切换在 Task 3 而 Fake 适配推迟 Task 4）、Subtask 0.3 与 Task 0 DoD "OD-1~OD-7"未升 OD-8 | P2 | 六键→七键勘误；三处 Task 4 归属改"Task 3 同批 + Task 4 验证兜底"；Task 3 DoD 补提交闭环判据（验收/集成 Fake 适配同批完成）；OD-1~OD-8 两处升级 + sprint-status 注释同步 |
| R2-2 | xdist 组名钦定冲突：pyproject `-n auto --dist loadgroup` 默认态下新组名 `market-insight-perf` 与 6-1 `blm-planning-perf` 跨 worker 并行采样（冷启动 embed 并行抬双方 P95）；"与验收共享采样缓存"表述失实（`_CachedEmbedding` 按文件模块级隔离，共享面是外部 embedding 服务） | P2 | 复用 6-1 组名 `blm-planning-perf`（跨 Story 采样场景全局同 worker 串行）；隔离表行改写并注明缓存隔离事实 |
| R2-3 | Task 2.3 gap 四字段扩展非行为中性：6-1 单测 L533 以 `财务差距=` 子串断言（注释"正常态单字段口径"），四字段实现若改英文键/改标签则 Task 2 结束即红——"自然全绿" DoD 是未声明条件命题 | P2 | Subtask 2.3 钉死子串兼容（四字段摘要保留 `财务差距=` 中文标签子串） |
| R2-4 | "全仓 grep InsightStepSchema 清零"字面会诱导 dev 删改 6-1 Story 审计记录（_bmad-output 历史引用是记录性轨迹） | P3 | Task 4.4 与 DoD 改范围限定口径（`grep -rn InsightStepSchema src/ tests/` 零输出；_bmad-output 明确除外） |
| R2-5 | 组合推演边界批：场景③ 20 轮采样未声明 recorder 总线口径（真实发布 180 行清理无谓）/禁固定 plan_id（第 2 轮触发 482）/快照键 TTL 吸收 vs 逐删二选一；5.2"版本断言"超实际可断言面（state_version 恒 0 无递增）；Task 2 测试若写 `__all__` 穷尽断言在暂留期必红；OD-8"逐字对齐"空格自违（or.md"能力 - 机会"两侧空格） | P3 | 5.3 三边界钦定；5.2 改"版本写读一致"口径；2.4 禁穷尽断言注记；OD-8 空格归一例外声明 |
| R2-6 | 形态批：Task 1 循环A 绿行表格单元格内 `dict[str, Any] \| None` 未转义管道符裂列；Task 3 绿行悬空编号"R1-F2" | P3 | 签名移出单元格文字化呈现；编号改 R1-2 |

> **Round 2 审查方法记录**：回归核查双 Agent——①传播完备性（git show 取证 + 修复关键词 17 组全出现位 grep + R1 标注文本 20+ 处破损抽查 + 40 Subtask 点数复核 + 外部事实锚点独立验证全通过）②组合交互推演（8 组合面：R1-2×R1-5/R1-2×4.4/R1-1×R1-3×20轮/R1-6×归属锚×并发/R1-7×xdist/R1-4×键族/R1-2×R1-9×DoD/R1-2×FileList）+ 主会话预验组合面 7（6-1 L533 子串断言——与 Agent 结论互证）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-1 | **findings 信封契约三叉未定（P1）**：服务成功分支信封构造 L350-352 直读 `schema_result.findings`——六类型化 Schema 仅钦定 summary 公共字段，缺 findings 则切表即 AttributeError（Task 3 阻断）；Task 4.2"findings/summary 语义未变"声明在未冻结形态下不成立 | P1 | 六 Schema 钦定 `summary: str` + `findings: list[str]` **双公共字段**（数据模型节/AC-1 VC/Task 2 循环A 红行三处同步）——服务直读成立、降级空分支对称、4.2 回归声明成立 |
| R3-2 | SSOT 映射容器形态悬空引用：Task 2 循环 B"按 Task 0 定稿形态"但 Task 0 无钦定载体（0.1~0.9 均不涉映射容器） | P2 | Subtask 0.1 钦定形态 A 独立 dict `MARKET_INSIGHT_STEP_SCHEMA`（避免 StepSemanticConfig 承载类型对象耦合扩散）；Task 2 循环 B 去悬空 |
| R3-3 | 5.4a/AC-3/AC-6 的 outbox 断言隐含真实 publisher + PG 装配但全文未钦定总线形态（默认 recorder 零落行使断言空真或被弱化降维）；AC-3 负向断言 recorder 下空真恒过 | P2 | 5.4a 钦定沿 6-1 集成场景③ 真实发布装配先例 + per-plan 计数钉死 9 行（PlanningStarted×1+BlmStageCompleted×8，AgentDecided 无 plan_id 子键天然排除）；AC-3 补非空锚前置（≥9 行再负向） |
| R3-4 | AC-2×3 场景分化维度未钦定（降级步快照与 AC-4 场景天然同质，dev 易写出重复覆盖）；"快照写入失败容错"列为验收 Edge Case 与 no-mock 红线互斥（真实 Redis 写失败不可构造、stub 抛异常 = mock 真实服务） | P2 | BDD 约束节补场景分化维度表（AC-1/AC-2/AC-4/AC-7 逐组钦定）；写失败容错归属单测层 Task 3 循环 B，验收 Edge Cases 剔除 |
| R3-5 | AC-7"类型化摘要含领域要素要点"双读法：`summarize_step_for_downstream` 实测仅读四字段不读 structured_output——读法 ii（扩展 summarize）无 Task 承载且验收不可判别 | P2 | 消歧收敛读法 i（summary 经 Schema description 约束与信封同源）+ 显式裁定不扩展 summarize_step_for_downstream |
| R3-6 | P3 簇：Task 7.1"降级双杀×2"标签致单点覆盖丢失；AC-7 场景数 7.2 未同步（钉 2：正常+降级标注）；5.4b 采样轮 task 文本未钉固定（每轮换文本则 140 次 embed 全 miss 假红）；completed_steps 是否含 performance_gap 未钉；VO 加 dict 字段后 hash() 抛 TypeError 未注记；20 轮采样验收/集成双层未分配 | P3 | 7.1 改"单点+双杀×2"；7.2 钉 2 场景同步；5.4b 钉 task 固定；completed_steps 钉"首步即含 performance_gap"；Task 1 重构行补可哈希性注记；20 轮归属集成 5.3、验收单轮（分化维度表载明） |

> **Round 3 审查方法记录**：单深度推演 Agent（8 项推演：场景期望唯一性干跑/P95 数学与预热口径/并发 outbox 全链/Task 0→7 依赖干跑/SSOT 形态×验证器 D/null round-trip/AC-7 摘要机制/信封语义层）+ 主会话 L350-352 实测定谳 P1。**安全定谳（免修留痕）**：P95 次大值数学自洽+预热属 DC-7 既定口径（次大值档自愈单冷轮）；structured_output=null 双层 JSON round-trip 全链闭合；图并发隔离三锚（thread_id=run_id/节点显式传 context/_runs 按 plan 键控）；Task 0→7 无硬倒挂（契约测试不钉 docstring，0.2 修改安全）。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** [待实施后填写]
**审查模式:** [待填写]

#### 需决策 Decision Needed

- [ ] （待实施后填写）

#### 已修复 Patch

- [ ] （待实施后填写）

#### 已推迟 Defer

- [ ] （待实施后填写）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.0
**创建日期/Created:** 2026-11-01
**最后更新/Last Updated:** 2026-11-01
**更新说明/Description:**
- v1.0.0: 创建故事文件（五 Agent 并行调研 + 关键代码事实独立核验；钦定 OD-1~OD-7 偏离声明；六类型化 Schema 规范冻结表；per-step 快照键契约）
- v1.1.0: Round 1 文档审查修订（四视角调研 + 双评审员 + 主会话独立定谳；P1×3 + P2×10 + P3×15；修复 R1-1~R1-14 详见 Docs Review Fixes 表；新增 OD-8；Task 2/3 边界重划——InsightStepSchema 移除与三 Fake 适配归 Task 3 同批；outbox 断言主键改两级 JSONB 路径；双杀注入键钦定 schema 身份）
- v1.2.0: Round 2 回归核查修订（传播完备性 + 组合交互推演双 Agent + 主会话预验互证；P2×3 + P3×3 簇 R2-1~R2-6：R1-2 传播漏网 5 处收敛（File List 残留复活中间红窗口）、xdist 组名钦定复用 blm-planning-perf、Task 2.3 财务差距=子串兼容钉死、全仓 grep 范围限定、采样轮三边界、形态批）
- v1.3.0: Round 3 深度推演修订（单深度 Agent 8 项推演 + 主会话 L350-352 实测定谳；P1×1 + P2×5 + P3 簇 R3-1~R3-6：findings 双公共字段钦定（切表 AttributeError 阻断修复）、SSOT 映射形态 A 钦定、outbox 真实发布装配+非空锚+9 行计数钉死、场景分化维度表（快照写失败容错与 no-mock 红线互斥裁定）、AC-7 摘要机制消歧、P3 簇批）
