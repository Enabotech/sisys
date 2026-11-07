# Story 6-9: 分析师视图（三段聚合查询——专业工具箱/BLM 六阶段进度/溯源摘要 + CLI `analyst-view`）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行文档审查修订循环（参照 6-6/6-7/6-8 五轮形态）+ 人工按 story-template 合规清单核对后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略与市场人员（分析师）,
**I want** 系统按 plan_id 输出分析师视图——单命令聚合专业工具箱（23 种战略工具清单+分类分组）、BLM 六阶段进度全景（前两阶段实数据派生+后四阶段规划态标注）与溯源摘要（四层树规模统计+文档跳转就绪计数）三段,
**So that** 高效完成战略规划和分析工作——单命令掌握「有哪些专业工具可用、规划流程走到哪个阶段、结论可溯源到哪些原始文档」（epics L2436-2438 用户价值；epics L2444-2446 AC 三要素）。

### 业务价值

- **Epic 6 价值组「战略规划与审批能力」的分析师作业面**：生成侧（6-1~6-5b）、审批侧（6-6）、溯源面（6-7）、高管速览面（6-8）已 done，本 Story 交付 **P1-9 分析师视图**——面向专业作业者的工具/进度/溯源三合一入口（epics L2019 依赖列钦定「依赖 Story 6.1/6.7」——两依赖均 done）
- **范围权威（epics L655 + UX 三页面驾驶舱格局）**：Story 6.9 是「UX 三页面驾驶舱（分析师）」的后端承载位——**Web/前端交互面归 Epic 21/22**（快捷键→Story 21.9 FR-UI-23（epics L485）；工作台批量操作/证据勾选→Story 22.1 FR-UI-13（epics L541 映射行——R1 行号勘误，创建期误标 L550）；角色自适应「分析师默认决策卡片」→Story 22.8 FR-IF-05（epics L3408））；本 Story 交付其**后端聚合口径与 CLI 呈现**（Epic 6 第八个 CLI-only Story——6.1-DF5 七连先例延续；6-8「CLI 呈现即 MVP fallback 形态」直系复刻）
- **FR Coverage Map 无独立 FR（同 6-6/6-7/6-8 形态）**：FR-ST-01（23 种工具注册）已由 Epic 4 Story 4.1 交付（epics L452 映射行）——本 Story 是既有工具注册面的**展示消费方**；FR-UI-23/FR-UI-13/FR-IF-05 归 Epic 21/22——本 Story 是**聚合展示面**（查询型故事先例族第八连）
- **激活既有查询面的组合消费**：`SkillSelectorPort.list_active_skills()`（组合根 `skill_selector` :3011——Story 5-2 交付，既有**生产码**消费方仅 LoadAgentProfileUseCase[R1 限定语：tests 侧另有夹具/直调消费——纯读共享零影响]）+ `snapshot_repository.load`（latest 快照——6-1/6-8 同链）+ `traceability_tree_service.build_trace_tree`（6-7 交付，既有消费方仅 trace-tree CLI）——三既有通道首次单点聚合
- **Epic 6 内部顺序**：6-8（done，高管速览面）→ **6-9（本 Story，分析师作业面）** → 6-10 顾问视图（backlog）→ 6-11 白标报告（backlog）

### 范围边界（出处逐行声明）

| 面（出处） | 已交付（禁重复造轮） | 6-9 增量（本 Story） |
|---|---|---|
| 专业工具箱数据面（4.1/4.1a/5-2） | `SkillSelectorPort.list_active_skills() -> tuple[ToolMetadata, ...]`（ACTIVE 纯过滤+slug 清单稳定序——`ports/skill_selector.py:28`；实现 `registry/selector.py:27` 组合注入 skill_loader）；`ToolMetadata` frozen dataclass（tool_name/slug/category/description/tags/status 等——`ports/skill_loader.py:29`）；`InMemorySkillLoader` L1 缓存纯内存读 TOOLS.md 打包文件（**零外部服务依赖**——`skills/loader.py:96-104` `__init__` 同步建缓存）；`get_all_slugs()` 23 slug 静态真源（`skill_manifest.py`）；`ToolRegistryServicePort.list_all_tools()`（同步 Tool 实体含 schema dict——`ports/tool_registry_service.py:60`，**不采**：schema 是执行面载荷对展示冗余） | **只消费不执行**：工具箱段 = ACTIVE 工具清单+分类分组计数（L1 元数据投影白名单五键）；工具执行链零触碰（4-1a/5-3 已交付执行链——本 Story 无任何工具调用） |
| BLM 进度数据面（6-1/6-2） | latest 快照 `blm-planning-{plan_id}`（state_data 七键：plan_id/phase/current_step/completed_steps/total_steps/degraded_steps/timeline——端口 SSOT `blm_planning.py:10-12`）；`BlmPhase` 枚举**仅 2 值**（performance_gap/market_insight——`blm_phases.py:42-50`，**docstring 钦定「六阶段完整版（战略意图/创新焦点/业务设计/执行设计）归 Epic 10 Story 10-1（FR-SP-05）在同文件扩展——本枚举预留扩展锚」**）；timeline 条目六键（step/started_at/completed_at/status/summary_excerpt/degraded），step 实值三种形态（"performance_gap"/六子裸值/"market_insight_synthesis"）；`BLM_TOTAL_STEPS=8`；`BlmPlanningStatus.progress_percent` property（round-2 float——`blm_phases.py:173-176`） | 六阶段进度全景（**应用层静态清单+派生规则**——OD-5）：六元组常量（阶段序 or.md L379 权威）+前两阶段状态派生自 timeline+后四阶段恒 not_started（V1 归 Epic 10-1 注记）；步级计数直读（completed/total/degraded_step_count）；**零改动** `BlmPhase` 枚举（扩展锚归 10-1 钦定不可僭越） |
| 溯源数据面（6-7） | `TraceabilityTreePort.build_trace_tree(*, plan_id, depth=4)`（组合根 `traceability_tree_service` :2021 SINGLETON）；`TraceabilityTree` 7 键顶层（plan_id/root/adopted_archives/total_archives/degraded_stages/build_degraded/generated_at）；四层 VO 7/5/9/6/9 键；`DocumentNode.jump_ready` 派生布尔（object_key 非空且 page 非 None——「30 秒溯源」节点级观测面，`ports/traceability_tree.py:24-27`）；空 plan 幂等空树；CLI `trace-tree`（--plan-id/--depth/--stage） | **只统计不重建**：溯源摘要段 = 树统计派生（三层有效计数[stage/chunk/document]+jump_ready 计数+degraded_stages 计数+树顶层哨兵透传——**结论层恒单根节点**[root 即唯一 ConclusionNode，空树同构造]不计入统计面，depth=4 钦定——jump_ready 在文档层——R1-F1 修订）；树构建逻辑零触碰；CLI 操作提示「可执行 trace-tree 查看完整树」指向既有命令（6-8「可先执行 report-generate」同款形态） |
| 高管视图（6-8） | `ExecutiveViewPort`+四段（planning/approval/audit/report）+`ExecutiveHealth` RAG 三色+CLI `executive-view` | **不重复**：报告段/审批段/审计段零消费（epics 6.9 AC 无报告/审批/审计面——高管速览已交付）；6-8 与 6-9 的 planning 口径**有意分立**（6-8 步级摘要 vs 6-9 阶段级全景——两视图服务正交） |
| Web 交互面（Epic 21/22） | 未立项（21.9 快捷键+响应式/22.1 工作台三栏+证据勾选+批量操作/22.8 三页面架构+角色自适应） | **不做**（快捷键=前端键盘事件语义、批量操作=工作台证据勾选 Web 交互——两者均无后端独立承载面；口径差声明 OD-7；Web 面归 Epic 21/22 立项） |
| REST 端点（Epic 7） | openapi.yaml 至今无 BLM/视图面 endpoint（6.1~6-8 惯例——grep `blm\|view\|executive\|analyst` 仅 TrafficViewResponse 监控面无关命中） | **不做**（CLI-only 第八连——6.1-DF5 先例；openapi.yaml 零 diff） |
| 后四阶段流程（Epic 10） | 未立项（BlmPhase 扩展锚+Epic 10 Story 10-1 FR-SP-05 P1 V1——prd L454「前两阶段覆盖 80% 场景 V1 手动补充后四阶段」） | **不做**（六阶段清单仅呈现框架——后四阶段 not_started 规划态+V1 注记，非流程实现） |
| 工具版本/灰度统计（L13 锚） | `EvolutionLogQuery.list_by_tool` 数据面就绪（灰度推进/per-version 统计视图——deferred-work L13 触发=产品立项） | **不做**（工具箱段是 ACTIVE 状态清单非版本统计面；锚位维持「产品立项」——Task 0.7 注记） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 三段聚合数据结构（AnalystView 键契约）

**Given** 某 plan_id 下已存在 BLM 运行数据（latest 快照 `blm-planning-{plan_id}` 七键在位——全数据形态：phase=market_insight、completed_steps≥1、timeline 含 performance_gap 与至少一个子步骤条目）与溯源归档族（6-7 形态：结论层/分析层/切片层/文档层四层预置，含 ≥1 个 jump_ready 文档节点），工具箱面为**打包静态真源**（23 工具 L1 元数据——`InMemorySkillLoader` 内存缓存零外部依赖，无需预置）
**When** 分析师请求分析师视图（编程面 `AnalystViewService.build_analyst_view(plan_id)` 或 CLI `analyst-view --plan-id <uuid>`）
**Then** 返回 `AnalystView` **6 键** frozen VO（`plan_id`/`generated_at`/`build_degraded`/`toolbox`/`progress`/`traceability`——全键契约见 Task 0.1 冻结表），三段各自键恒在：
- **专业工具箱段** `ToolboxSection` **4 键**：`degraded`（段级降级哨兵）/`total_tools`（ACTIVE 工具总数——当前 23）/`tools`（tuple[`ToolSummary` **5 键**：slug/tool_name/category/description/status——L1 元数据**投影白名单五键**，`ToolMetadata` **18 字段**面其余 13 字段（input_schema/output_schema/when_to_use/when_not_to_use/capabilities/tags/version/rule_version/token_budget_l1/token_budget_l2/depends_on/triggers/data_sources）禁入视图——R1-F2 勘误）/`categories`（tuple[`ToolCategorySummary` **2 键**：category/tool_count]——按 category 分组计数，**组序钦定 slug 清单稳定序去重序**——selector 返回序派生，禁字母序重排）
- **BLM 进度段** `ProgressSection` **9 键**：`available`（快照在位 bool）/`degraded`/`phase`（快照 phase 直读 str——值域当前 2 值；空态/段降级 None——R1 补注记）/`current_step`/`completed_steps`/`total_steps`（int 计数直读）/`progress_percent`（int 0-100——`int(completed_steps / total_steps * 100)` 向下取整，total_steps==0 服务层守卫归 0[除零形态——R1-F6]，**与 6-8 PlanningSection.progress_percent 同口径**（VO 侧 int 截断）+与实体 property float 口径分立注记——6-8 R1-F3 裁定直系延续）/`degraded_step_count`（派生自 state_data `degraded_steps`（list[str]）的 `len()`——6-8 同款派生）/`stages`（tuple[`PhaseProgress` **5 键**]——六阶段全景，见 AC-3）
- **溯源摘要段** `TraceabilitySection` **8 键**：`available`（stage_count > 0——有分析层数据可溯源）/`degraded`（本段编排异常哨兵——与树顶层哨兵分立）/`stage_count`（分析层 StageNode 节点数==len(tree.root.children)——depth=4 下与 root.stage_count 等值）/`chunk_count`（切片层 ChunkNode **节点实例数**——跨 stage 重复引用按实例计（6-7 端口「每条 stage→chunk 路径独立」直系），同 document_count 口径——R2 补注记）/`document_count`（文档层 DocumentNode 节点实例计数——同文档多 chunk 嵌套重复计，6-7「文档缓存仅省 find 调用、节点形态仍嵌套」注记直系）/`jump_ready_count`（jump_ready=True 文档节点数——「30 秒溯源」可达性观测锚）/`degraded_stage_count`（len(tree.degraded_stages)——stage 级降级上卷计数）/`tree_build_degraded`（透传 6-7 树顶层哨兵——「拿不到数据」vs「没有数据」两层分立，6-7 读模型诚实性在聚合面的延续）（**结论层恒单根节点**：root 即唯一 ConclusionNode[title 固定文案/summary=synthesis conclusions 联展可空]，空树同构造——统计面剔除恒定值，四层规模统计以三层有效计数+jump_ready 承载——R1-F1 修订）

**And** 顶层 `generated_at` 为 ISO 字符串（`datetime.now(UTC).isoformat()`——服务入口**单时间锚**取一次 now，6-8 R1-F2 单锚派生直系延续；段内不透传树 `generated_at`——并发对照排除集最小化裁定 OD-6）；段内计数均派生自既有单源（工具计数派生 selector 返回序、进度计数派生快照七键、溯源计数派生树遍历）——**服务不新算任何跨源复合指标**

**验证标准/Validation Criteria:**
- [ ] 全数据场景：6 键 exact set（`{f.name for f in fields(AnalystView)}`——6-8 R1-F10 激活先例）+ 三段嵌套键集各自 exact set + 值级断言（total_tools==23/total_steps 与预置一致/completed_steps 与预置一致/jump_ready_count 与预置归档形态一致；**溯源五计数值级断言归 AC-4 验证标准承载——分工指路 R2 注**）
- [ ] `ToolSummary` 5 键 exact set（投影白名单——`ToolMetadata` 字段面防扩散断言：构造入参仅五键）
- [ ] progress_percent 整数口径断言（3/8 完成 → 37 非 37.5——int 向下取整）
- [ ] categories 恒等式（`sum(c.tool_count for c in categories) == total_tools`——分组计数完备性，缺组/重复计数即红）

### AC-2: 专业工具箱段聚合（23 工具清单+分类分组）

**Given** 工具箱静态真源在位（打包 TOOLS.md 23 行+23 个 SKILL.md frontmatter 全 status="active"——当前事实主会话亲验 `get_all_slugs()` 23 slug）
**When** 构建分析师视图
**Then** 工具箱段与既有单源一致：`total_tools == 23`（**当前全 ACTIVE 事实断言**——若未来工具转 deprecated 该断言红是**预期退化信号**非 flake，注记：断言语义=「MVP 交付时点 23 工具全 ACTIVE」防清单静默缩水）；`tools` 序 == slug 清单稳定序（selector 返回序契约——`registry/selector.py` docstring「返回顺序与清单一致是 AC-3.2 断言契约」；**禁排序重排**——全序列断言 `tuple(t.slug for t in tools) == tuple(get_all_slugs())` 静态真源直比[R1 补强：首末锚仅捕首尾错位，中段乱序不红]，首末锚保留作快速失败锚：tools[0].slug=="pestel-analysis"/tools[-1].slug=="change-management"）
**And** `categories` 覆盖 5 个战略分类（environment_analysis/competitive_analysis/strategic_selection/business_model/execution_management——ToolCategory 5 战略分类值域[枚举共 10 成员另含 5 功能分类，此处指战略子集]，配比 3/3/6/3/8=23——Story 4.1 AC-2 钦定配比；`len(categories)==5` 断言补强——R1：防第六类静默出现时和恒等式仍绿）：各分类 tool_count 值级断言（environment_analysis==3/competitive_analysis==3/strategic_selection==6/business_model==3/execution_management==8）
**And** `ToolSummary` 五键值级：slug/tool_name/category/description 均非空 str、status=="active"（投影源字段直传零变形）

**验证标准/Validation Criteria:**
- [ ] total_tools==23 + 首末 slug 锚（清单序稳定）+ **全序列断言 `tuple(t.slug for t in tools) == tuple(get_all_slugs())`（R1-F11 主锚——中段乱序判别，首末锚仅快速失败——R2 补入承载位）**
- [ ] 5 分类各 tool_count 值级断言（3/3/6/3/8）+ 分组和恒等式 + len(categories)==5（R1 补强）
- [ ] 每条 ToolSummary 五键 exact set + 值非空 + status=="active"
- [ ] 抽样值级锚（≥3 工具的 tool_name/description 与 TOOLS.md 原文一致——静态真源对照）

### AC-3: BLM 六阶段进度段（阶段状态派生矩阵）

**Given** 三个 plan_id 各持不同快照形态：**P-mid**（phase=market_insight、timeline 含 performance_gap+趋势子步骤 trend——无 synthesis：市场洞察进行中）、**P-full**（timeline 含 performance_gap+全六子步骤+market_insight_synthesis——8 步全完成）、**P-empty**（零快照——空 plan）
**When** 构建分析师视图
**Then** `stages` 为六元组（**六阶段静态清单钦定**——应用层常量，阶段序 or.md L379 权威原文「业绩差距分析、市场洞察(包括六个子步骤)、战略意图与目标、创新焦点、业务设计、执行设计六个阶段」）：
1. `performance_gap`（业绩差距分析）——step_completed/step_total 钦定 1/1
2. `market_insight`（市场洞察）——7/7（六子步骤+synthesis）
3. `strategic_intent`（战略意图与目标）——0/0（V1 归 Epic 10-1 注记）
4. `innovation_focus`（创新焦点）——0/0（同上）
5. `business_design`（业务设计）——0/0（同上）
6. `execution_design`（执行设计）——0/0（同上）

每 `PhaseProgress` **5 键**：`phase_key`/`phase_name`（中文全名——上表钦定）/`status`（`PhaseStatus` 三值 str-Enum：completed/in_progress/not_started）/`step_completed`/`step_total`
**And** 状态派生**确定性规则表**（Task 0.2 冻结，实现为纯函数 `derive_stage_status`，禁散落 if 链）：
- 阶段1：timeline 含 "performance_gap" 条目 → completed；否则 not_started
- 阶段2：timeline 含 "market_insight_synthesis" → completed；含任一六子步骤裸值（trend/market_customer/competition/self/opportunity/opportunity_gap）→ in_progress；否则 not_started
- 阶段3~6：**恒 not_started**（`step_total==0` 的规划态——「未启动」非「不可用」；V1 交付注记归 phase_name 后缀呈现，不进 status 值域）
- step_completed 派生：与 `derive_stage_status` 同一 `stage_steps` 集合的基数（服务层按阶段值域过滤**去重**后 len——R1-F3 口径钦定）：阶段1 ∈{0,1}；阶段2 ∈[0,7]（六子裸值+synthesis 值域基数）；阶段3~6 恒 0；重复 timeline 条目（写侧 `record_step` 纯 append 无幂等防护——`blm_planning_service.py:117` 亲验，六子步骤无重跑守卫）天然去重，计数恒 ≤ step_total（VO 不变量结构可满足，无需服务层钳制）。（注记——R2 补：progress 段 completed_steps/progress_percent 是快照 int 直读口径（写侧 min 钳制 ≤8），与 stages 派生计数分立——timeline 含值域外脏值时两者可不一致（如 8 条前缀脏值条目：直读 8/8 而六阶段全 not_started），属「快照计数 vs 派生计数」预期语义非 bug；derive_stage_status 单集合参数可判别三规则的依据是三阶段值域两两不相交——{performance_gap}/六子+synthesis 七值/∅）
**And** 三 plan 形态值级：P-mid → stages[0].status==completed+stages[1].status==in_progress+stages[1].step_completed==1+stages[2..5] 全 not_started；P-full → stages[0..1] 全 completed（step_completed==step_total）+后四 not_started；P-empty → progress.available==False+六阶段全 not_started（**空 plan 六阶段框架恒在**——静态清单不依赖快照，「工具/框架恒在+数据缺席降级」语义）
**And** `PhaseStatus` 为三值 str-Enum（`COMPLETED="completed"/IN_PROGRESS="in_progress"/NOT_STARTED="not_started"`——**进度态语义域**，与 `ExecutiveHealth`（健康分级域 green/amber/red）正交分立——6-8 OD-4「全仓首个三值分级枚举」注记不冲突：本枚举是首个三值**进度态**枚举，落应用层 ports 文件同 6-8 先例）

**验证标准/Validation Criteria:**
- [ ] 三 plan 三形态 stages 六元组值级断言（P-mid/P-full/P-empty 各 6 阶段 status+step_completed 逐项）
- [ ] 六阶段静态清单序断言（phase_key 六元组精确匹配钦定清单——防清单漂移）
- [ ] 派生规则表单测矩阵全覆盖（Task 2 承载：三状态×数据形态全枚举——completed/in_progress/not_started 判别格+synthesis 优先于子步骤边界格）
- [ ] 后四阶段 step_total==0+status==not_started 恒等（V1 注记形态钦定）

### AC-4: 溯源摘要段聚合（树统计+jump_ready 计数）

**Given** 某 plan_id 下已预置 6-7 形态溯源归档族（直写思维链归档行+Qdrant 点+文档元数据——`_archive_row`/`_spec_chunk` 预置样板，6-7 验收 `test_acceptance_traceability_tree.py:319/:366` 直系复用）：≥1 结论归档行（synthesis 行——结论层呈现位）、≥2 分析 stage、**≥2 切片实例（R2 勘误：原「≥1 切片」与混合判别联合不可满足——每 chunk 至多挂 1 个文档节点[单 payload 单 document_id，`_resolve_document` 实码钦定]，jump_ready True/False 两态必跨 chunk；预置**钦定**使 chunk_count≠stage_count 判别计数面错接——R3-F4 收紧措辞）**、≥2 文档节点（其中 ≥1 个 jump_ready=True（object_key+page 齐备）、≥1 个 jump_ready=False（object_key 缺席））
**When** 构建分析师视图
**Then** 溯源段计数与树单源一致：`stage_count == len(tree.root.children)`（分析层——depth=4 下与 root.stage_count 等值）/`chunk_count`（切片层计数）/`document_count`（文档层计数）/`jump_ready_count == sum(1 for d in 文档层 if d.jump_ready)`（**depth=4 钦定**——jump_ready 在文档层，depth<4 不可达；OD-6）/`degraded_stage_count == len(tree.degraded_stages)`/`tree_build_degraded == tree.build_degraded`（顶层哨兵透传零变形）；结论层恒单根节点（root 自身）不计入计数——统计面语义注记（R1-F1）
**And** 预置形态值级断言：jump_ready_count 与预置的 jump_ready 文档节点数一致（可判别形态：预置 ≥1 True+≥1 False——计数既非全 0 亦非全量）；chunk_count 与预置 chunk 实例数直推（R2 补）
**And** 无归档 plan_id（零思维链归档）→ 树幂等空树（6-7 空树语义）→ 溯源段 available==False（stage_count==0）+五计数全 0+tree_build_degraded==False+不抛异常（「没有数据」非「拿不到数据」——空树分立哨兵语义透传）；树顶层降级形态（query_archive 异常被 6-7 服务内捕获返回 build_degraded=True 空树——**Mock 面以正常返回降级树形态模拟，非抛异常**；验收面无故障注入通道，该分支归单测承载——6-8 AC-5「段级容错归单测」分立同款——R1-F5）

**验证标准/Validation Criteria:**
- [ ] 预置归档族统计值级断言（五计数与预置形态直推——含 jump_ready True/False 混合形态判别）
- [ ] 空归档 plan → available False+五计数 0+tree_build_degraded False+不抛（对照腿）
- [ ] 树顶层降级透传归单测注记（**两条分立**——R1-F5：① AsyncMock 正常返回 build_degraded=True 的树 → tree_build_degraded==True 透传+段 degraded==False；② AsyncMock 抛异常 → 段 degraded==True+tree_build_degraded==False（段降级默认值）+其余段正常+顶层 build_degraded==True——Task 2 矩阵承载）

### AC-5: 段级容错与空 plan 幂等读

**Given** 空 plan_id（零快照/零归档——工具箱段为静态真源**恒有数据**，与 plan 无关：空 plan 的 toolbox 段照常返回 23 工具）或某数据源查询异常（异常形态归单测承载——验收面真实服务无故障注入通道，6-8 AC-5 同款分立裁定）
**When** 构建分析师视图
**Then** **段级独立容错**（6-8 段级容错直系延续）：三源各自 try 包裹——单源异常仅该段 `degraded=True`（段内计数降默认值/清单降空 tuple），其余段照常聚合，视图整体不抛；顶层 `build_degraded = 任一段 degraded`；**段降级语义三分**：toolbox 段 degraded（selector/list_active_skills 抛 SkillNotFoundError 传播被捕获——「缺档案是资产缺陷」fail-loud 语义在聚合面收敛为段降级+warning 日志）/progress 段 degraded（快照读异常——真实链路注记：`RedisSnapshotStore.load` 吞一切异常归一 None（`redis_snapshot_store.py:179-181`），「异常 vs 缺失」真实 Redis 链路不可分立均落空态，该分支仅单测 AsyncMock 面可达——6-8 R1-F2 同款注记）/traceability 段 degraded（build_trace_tree 调用异常——与树顶层 build_degraded 哨兵分立：前者是本段编排异常、后者是 6-7 服务内降级）
**And** 空 plan 幂等读：视图正常返回 6 键（progress.available==False+六阶段 not_started 框架恒在（AC-3）/traceability.available==False+五计数 0/**toolbox 段完整 23 工具**（静态真源与 plan 正交——三段中唯一恒数据段））、`build_degraded==False`（「没有数据」非「拿不到数据」——6-7/6-8 空态分立语义第三连）、**不抛异常**（6-4/6-6/6-7/6-8 四先例族）
**And** 畸形 plan_id（非 UUID）→ 用例层 242 `EntityValidationError`（`GetExecutiveViewUseCase`/`GetTraceabilityTreeUseCase` UUID 守卫直系先例——服务层不守卫，分工钦定同 6-8 OD-3）；编程面 `pytest.raises` 形态、CLI stderr 形态分立（AC-6）
**And** 快照在位但 state_data 畸形（缺键/类型错）→ progress 段降级（degraded=True+available==False+计数降 0[含 total_steps——R3-F2：AC-1 直读口径仅在快照在位且非降级形态生效，降级/空态默认值钦定见 Task 0.1 冻结表]+progress_percent==0+六阶段框架恒在 not_started），不抛（读侧脏数据守卫——**逐键处置复刻 6-8 `executive_view_service.py:169-188`**——R1-F6：completed_steps 必备缺→段降级/total_steps `.get` 默认 BLM_TOTAL_STEPS 且 ≤0 显式段降级[除零形态守卫——progress_percent 归 0]/timeline、degraded_steps 缺→空列表/**phase、current_step `.get` 缺→None（空态同形——6-8 :188 `current_step=state_data.get(...)` 先例直系；phase 无 6-8 对应键钦定同一宽容面：值现为 str→采用、缺→None，不触发段降级——R2 补遗）**；「宽容-严格」三分界钦定直系延续：缺键且有单源常量→默认/值现且可强转→采用/值现且不可用→降级）

**验证标准/Validation Criteria:**
- [ ] 空 plan 幂等读四断言（6 键恒在+build_degraded==False+toolbox 段完整+两段空态框架）
- [ ] 畸形 plan_id → 242（code 值级断言——编程面）
- [ ] 段级容错归单测（三源×AsyncMock 抛异常 → 各段 degraded=True+其余段正常+build_degraded==True——Task 2 矩阵；验收面零 mock 红线不承载异常注入）
- [ ] state_data 畸形守卫归单测（缺 completed_steps 键/非 int 形态 → 段降级不抛+六阶段框架恒在）

### AC-6: CLI `analyst-view` 命令（分析师作业入口）

**Given** 全数据在位（AC-1 形态）
**When** 执行 `sisys-agent analyst-view --plan-id <uuid>`
**Then** 三段结构化输出（纯标准库 print——「输出即契约」6-8 同哲学；无 JSON 输出模式——仓内 CLI 全 stdlib print 惯例）：首行 `分析师视图（plan: {plan_id}）` + 三段各以 `── {段名} ──` 分隔行承载：
- 专业工具箱：`工具: 共 {total_tools} 种（ACTIVE） | 分类: {category}×{n} ...`（5 分类计数连排）+ **逐工具清单**（`  {slug} — {tool_name}（{category}）`每工具一行——23 行全量打印，专业作业面语义：工具箱是「可用的工具」清单非计数摘要；**段降级时**降 `工具清单获取失败` 单行）
- BLM 进度：`进度: {completed}/{total}（{percent}%） | 当前: {current_step} | 降级: {n} 步`（current_step None→『无』fallback——6-8 :1519 直系先例，R3-F5；呈现语义注记——R3-F6：进度行=快照 int 直读口径/阶段行=timeline 派生口径，两口径可不一致[AC-3 分立注记呈现面延续]，注记落 `_print_analyst_view` docstring 义务——Task 3 重构格承载） + **六阶段进度条**（每阶段一行：`  {序}. {phase_name}: [{█×k}{░×(10-k)}] {status中文}（{step_completed}/{step_total}）`——进度条 10 格字符形态（k=round(step_completed/step_total×10)，step_total==0 时恒 ░；k 表单测枚举 c=0..7 钉 [0,1,3,4,6,7,9,10]——10c/7 与 10 互质无 .5 tie 面[banker's rounding 无触发面，确定性安全]，k 公式 ±1 即红：R1 补强变异锚）+status 中文映射（completed=已完成/in_progress=进行中/not_started=未启动）+后四阶段行尾追加 `（V1 交付）`注记；快照缺席时六阶段框架行恒在（全 not_started）+首行降 `进度: 无快照`）
- 溯源摘要：`分析: {n} | 切片: {n} | 文档: {n} | 可跳转: {n}` + 降级行（`降级 stage: {n}`——degraded_stage_count>0 时）+ 树降级标记（tree_build_degraded 时追加 `（部分树数据降级）`）+ 操作提示行（恒在：`提示: 执行 trace-tree --plan-id {plan_id} 查看完整溯源树`——指向既有命令，6-8「可先执行 report-generate」同款形态；统计行改三层计数——R1-F1）
**And** 退出语义：正常 exit 0（含空 plan 空态——空态是正常态非错误；空态输出=首行+三段各自空态行[工具箱段照常全量 23 行；progress 段首行降「进度: 无快照」+六阶段框架行恒在；**溯源段统计行恒在全 0 形态「分析: 0 | 切片: 0 | 文档: 0 | 可跳转: 0」+提示行恒在（降级行/树降级标记缺席）——R2 钉死：S9 断言可精确落笔**]；progress/traceability 段降级行形态归实现期 CLI 单测冻结——低危注记）；畸形 plan_id → exit 1 + stderr `[EXCEPTION_242]`（6-8 前缀统一先例；`_run_executive_view_cli` 五步定式 :1567-1600 直系样板）
**And** 本 Story CLI 面无角色门槛（「分析师」是 UX 语义——查询命令族先例均无角色检查；RBAC 门槛归 7-2 REST 入口立项时评估——6-8 AC-6 同款注记）；参数面仅 `--plan-id` 必填单参数（**零可选参数**——YAGNI：无 --format/--category 过滤需求来源，输出形态服务常量钉死——6-8 同款裁定）
**And** build_degraded 时首行后追加 `（部分数据降级）`标记（6-8 健康行降级标记同款形态——本 Story 无 health 三色，降级标记承载诚实性）

**验证标准/Validation Criteria:**
- [ ] 全数据输出断言：三段分隔行+工具箱首行精确+23 工具行计数+六阶段 6 行（status 中文映射+V1 注记后四阶段）+溯源统计行+提示行（CLI 单测承载完整覆盖；验收场景经 CLI in-process 直调保红——6-8 S8/S9 双清先例）
- [ ] 空 plan 输出断言（六阶段框架行恒在+工具箱照常+**溯源统计行全 0 形态**+exit 0——R2 补）
- [ ] 242 stderr 形态（`[EXCEPTION_242]` in stderr + exit 1）

### AC-7: 性能与并发（三段口径——OD-7）

**Given** 全数据在位（AC-1 形态，服务面已预热）
**When** 采样计时（20 轮——`sorted(durations)[ceil(0.95*n)-1]` 数学口径，6-3/6-6/6-7/6-8 四连同款公式与模块级期望常量独立构造）
**Then** **视图加载 P95<800ms**（epics L2456「视图加载延迟 P95<800ms」的聚合服务面等价口径）：口径 = `build_analyst_view` 服务面窗口（三读串行：list_active_skills 内存遍历[23 次 load_metadata 缓存命中——L1 启动全量缓存，微秒级]+snapshot load 1 次 Redis 点查+build_trace_tree 全树[query_archive PG 归档查+get_point/find Qdrant 点查——三读中最重，6-7 全树构建已在交付期验证]——20 轮数学口径；**风险注记**：trace_tree 全树成本随归档量增长，万行级归档时该段成为热点——分组统计端口立项锚 Epic 7/21，落 docstring）
**And** **并发 20 路读**（「支持批量操作」epics L2446 的读面等价口径声明——批量操作本义是工作台证据勾选 Web 交互（Epic 22.1），后端无独立承载面；本 Story 以并发批量读作读面等价锚）：**单一数据源 plan_id × 20 路并发读**（asyncio.gather 20 路 `build_analyst_view(plan_id)`——读面幂等无副作用；**服务无状态约束**——SINGLETON 实例并发共享禁持可变实例态——6-8 AC-7 同款；20 路结果两两相等断言+全部成功不抛；**对照排除集钦定 {generated_at} 单键**（顶层唯一每次调用新生成键——toolbox 段静态真源恒稳/progress 段单键快照读恒稳/traceability 段不透传树 generated_at（OD-6 裁定）故段值全稳定——排除集最小化是本 Story VO 设计的直接收益）；逐路对照形态=「dataclasses.asdict 序列化剔除 generated_at 后逐路相等」；**禁 set_session**——每路独立会话天然 per-task 隔离，6-8 R2-F3 C 面纪律直系）
**And** **「快捷键响应<100ms」与「溯源跳转响应<300ms」为前端/既有面指标**：快捷键是键盘事件响应（前端指标后端不定义——epics L2457 原文，Web 面归 Epic 21 Story 21.9 届时验收）；溯源跳转<300ms 已由 6-7 跳转载荷组装承载（6-7 性能三段口径原裁定——本 Story 溯源段是**统计摘要面**非跳转执行面，跳转执行归 trace-tree 既有命令；口径差声明落验收 docstring——OD-7）

**验证标准/Validation Criteria:**
- [ ] 20 轮采样 P95<800ms（预检服务可达+预热含首次 load）
- [ ] 并发 20 路全部成功+两两相等（排除集单键 {generated_at}——asdict 序列化剔除后逐路相等）
- [ ] 前端/既有面指标口径差声明落 docstring（快捷键/溯源跳转两项）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **零新增领域事件、零发布、零订阅**（OD-2——查询型故事第八连：纯查询聚合面零状态变更；6-4/6-5a/6-5b/6-6/6-7/6-8 六连零事件先例族延续；`event_channels.yaml`/`DEFAULT_MAPPINGS` 零 diff；`_FROZEN_EVENT_COUNT=56` 零变化——Task 4.2 守护复跑；蓝图无分析师视图事件载体）

#### 数据模型 (Data Models)

- [x] 七 VO+PhaseStatus 枚举全应用层 `src/application/ports/analyst_view.py`（frozen dataclass——6-6 CheckpointSummaryView/6-7 五 VO/6-8 七 VO 先例族；零 domain VO——OD-12）：`AnalystView` 6 键/`ToolboxSection` 4/`ToolSummary` 5/`ToolCategorySummary` 2/`ProgressSection` 9/`PhaseProgress` 5/`TraceabilitySection` 8（Task 0.1 冻结表——实现禁增删键）
- [x] 六阶段静态清单钦定应用层常量（OD-5：六元组 (phase_key, phase_name)——序 or.md L379 权威；**零改动 `BlmPhase` 枚举**——扩展锚归 Epic 10 Story 10-1 docstring 钦定）

#### 统一端口定义注册与管理 (Port Contract)

- [x] `AnalystViewPort`（应用层 `src/application/ports/analyst_view.py`，`@runtime_checkable Protocol` v1.0.0）：`async def build_analyst_view(self, *, plan_id: str) -> AnalystView`（keyword-only——ExecutiveViewPort 直系形态）
- [x] 端口注册中心/解析器/契约门禁零改动（既有机制消费）；组合根双注册（OD-11）：`analyst_view_service`（SINGLETON）+ `analyst_view_use_case`（SINGLETON）——落位 executive_view 块后（:2100 邻位）
- [x] 三依赖复用既有注册名零新端口：`skill_selector`（:3011 SINGLETON）/`snapshot_repository`（:950 SCOPED）/`traceability_tree_service`（:2021 SINGLETON）
- [x] 端口契约测试：`tests/contracts/test_port_contract_analyst_view.py`（五断言族——`test_port_contract_executive_view.py` 直系复刻）
- [x] 禁止在服务文件中本地定义 Protocol / Port 抽象

#### 端口契约清单执行约束（强制）

- [x] 本清单是唯一事实源；禁止新增未登记端口（本 Story 零新底层端口——仅一个视图聚合端口）；禁止语义重复端口（analyst_view 聚合面 vs executive_view 聚合面 vs traceability_tree 单域聚合——三语义正交：分析师作业面/高管速览面/溯源树完整面）
- [x] 端口具备唯一名称、版本 v1.0.0、owner、tags；未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

- [x] **零新增领域异常、零既有异常改动**（OD-3）：242 复用（畸形 plan_id 用例层 UUID 守卫——`GetExecutiveViewUseCase` 直系先例）；`SkillNotFoundError` 既有传播被段级容错捕获（消费非新增——fail-loud 资产缺陷语义在聚合面收敛为段降级）；空 plan 幂等读不抛（6-4/6-6/6-7/6-8 四先例族）；480 **不消费不复现**（`GetBlmPlanningStatusUseCase` load None 抛 480 是单点查询面语义——本 Story 聚合面 load None→available=False 非异常，6-8 OD-3 语义分立直系）；planning 480-489/report 490-499/traceability 372-379 三段预留维持零触碰（无 view 码段——主会话亲验 grep 零命中）

#### API 契约 (API Contract)

- [x] **零 REST 端点**（CLI-only 第八连——openapi.yaml 零 diff；6.1-DF5 七连先例；epics L2470-2471 钦定测试文件为 CLI/编程面测试非 API 契约）

#### 六边形架构约束（必须遵守）

- [x] **R1~R4 设计规则落点**：R1 领域层基础端口零改动（本 Story 零 domain）；R2 应用层具体端口 `AnalystViewPort` 组合注入三既有端口/服务（skill_selector+snapshot_repository+traceability_tree_service——ExecutiveViewPort 四依赖同构）；R3 基础设施层零改动（OD-12 三零）；R4 接口层零改动（CLI 归 entrypoints 组装层——D1 方案 A 既有格局）
- [x] 依赖方向矩阵合规：application→application（ports 消费）/entrypoints→application（CLI resolve）；domain/interfaces/infrastructure 零触碰

#### 验收标准 Gherkin (Acceptance Tests)

- [x] 功能测试文件：`tests/acceptance/test_acceptance_analyst_view.feature`（12 场景——R6 模板 `test_acceptance_postgresql_relational_layer.feature` 形态：AC 横幅分节+zh-CN 步骤）
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_analyst_view.py`（6-8 R6 合规最新形态：三件套/双清/context dict/CLI 直调/完成清单）
- [x] 所有场景覆盖（Happy Path + Edge Cases）；Edge Cases 含 242 异常路径（AC-5 分立形态）
- [x] **BDD 步骤实现约束**：步骤函数 `event_loop.run_until_complete()`；同一中文文本双装饰器支持；禁 `@pytest.mark.asyncio`

**Task 0 完成标志：**
- [x] 规范项全部定义完毕（键契约/派生规则表/端口/12 场景钉死/锚定义务八条处置）
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [x] **链路接线断言清单**：组合根 `register_port` 双注册 resolve 可达（契约测试承载）/零事件零中间件接线面（查询型 Story——接线断言归架构验证器 D CLI 锚）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试 / 测试集中到最后 Task / 跳过红阶段 / 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 恒真断言）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 七 VO+枚举 | 键集 exact set+构造守卫+静态清单序 | `tests/unit/application/test_analyst_view_vos.py` | Task 1 |
| **TDD 单元测试** | AnalystViewService | 三段编排/派生规则矩阵/容错矩阵 | `tests/unit/application/test_analyst_view_service.py` | Task 2 |
| **TDD 单元测试** | GetAnalystViewUseCase | UUID 守卫+透传 | `tests/unit/application/use_cases/test_analyst_view_use_case.py` | Task 3 |
| **TDD 单元测试** | CLI analyst-view | 解析/输出/退出码 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_analyst_view.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数 | `test_acceptance_analyst_view.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | 完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约/registry/resolver | 注册/元数据/注入链/可达/签名 | `tests/contracts/test_port_contract_analyst_view.py` | Task 3/4 |
| **SDD 架构验证** | 六边形架构约束 | 落位/零事件/依赖方向/CLI 接线 | `tests/unit/architecture/test_analyst_view.py` | Task 6 |
| **集成测试** | 真实三源链 | 聚合 round-trip+性能并发 | `tests/integration/test_integration_analyst_view.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（基线 93.22%——6-8 定稿轮实测；本 Story 纯新增不降基线）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（主改动层——epics L2461 对齐；新增文件目标 ≥95%）- **P1 阻断门禁**
- [ ] domain ≥90% 维持（零改动不降）/ 集成 ≥75%（epics L2462 对齐）

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（基线 mypy 759 文件零错误——6-8 定稿轮；零新增错误）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`——提交时钩子承载）
- [ ] **三红线 grep 自查零输出**（`raise ValueError`/手动 HTTPException/继承内置 Exception）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**本 Story 关键隔离面**（6-8 隔离纪律直系延续+本 Story 特有面）：

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **工具箱段隔离** | 静态真源零预置零清理（TOOLS.md 打包文件只读——段测试无资源生命周期） | 无风险面（本 Story 设计收益） |
| **Redis 快照隔离** | latest 快照直写+定向 DEL（`blm-planning-{plan_id}` 单键族——6-8 同款；TestTenant UUID 前缀 plan_id 天然隔离） | 键冲突 |
| **归档族隔离** | PG 归档行+Qdrant 点直写+定向清理（6-7 `_preset_qdrant_points_and_pg_rows`/`_teardown_tree_assets` 直系样板；Qdrant collection TestTenant 前缀） | 跨 plan 污染 |
| **PG 面三分面** | A 编程面 sync 层 set_session 回滚式 / B CLI 面 clear_session+commit 式+定向 DELETE 行数断言 / C 并发·性能面禁 set_session+每路 fallback 独立会话+commit+定向 DELETE（6-8 R2-F3 三分面直系） | 并发炸/假绿 |
| **BDD async** | 步骤函数禁 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()` | context 数据丢失 |
| **CLI 直调双清** | clear_singleton()+clear_scoped() 双清+禁二次 bootstrap（6-6 R3-1 实跑证伪教训钦定） | 假数据/ConflictError |
| **xdist 串行组** | pytestmark `xdist_group("blm-planning-perf")` 整模块挂法（6-7/6-8 同组） | 并行互扰 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（回滚式/定向 DELETE 行数断言）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio` / asyncio.run()
- ❌ 验收面 mock（真实服务三通道；段级容错归单测 AsyncMock——6-8 DR1-5 分立同款）

**验证要求：**
- [ ] 四目录全量 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）零失败×2 轮
- [ ] `poetry run ruff check` + `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **编号语义注记**（6-8 R1-F30 同款）：Subtask 列引用的循环 A/B/C 为 **TDD 循环语义位**；Task 内 Subtask 编号（2.1 红/2.2 绿/2.3 重构/2.4 变异）是 TDD 阶段序，两套编号体系分立防混引；验收场景统一归 Task 0 编写/Task 7 收尾承载。（R1 粒度注记：仅 AC-2/AC-3 列「Task 0 场景」行系其验收值级断言主承载位；Task 4 契约守护/Task 6 架构验证是全 AC 底座性 Task 不单列行。）

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 三段聚合 6 键结构 | Task 1 | 1.1-1.3 VO+枚举 | `test_analyst_view_vos.py` |
| AC-1 | 三段聚合编排 | Task 2 | 循环 A 服务编排 | `test_analyst_view_service.py` |
| AC-1 | 全数据 round-trip | Task 5 | 5.1-5.2 集成场景① | `test_integration_analyst_view.py` |
| AC-2 | 23 工具清单+分类分组 | Task 2 | 循环 A 工具箱段投影 | `test_analyst_view_service.py` |
| AC-2 | 真实 selector 清单 | Task 0 | 0.4 场景 S3 | `test_acceptance_analyst_view.py` |
| AC-3 | 六阶段派生矩阵 | Task 2 | 循环 B 派生规则矩阵 | `test_analyst_view_service.py` |
| AC-3 | 三 plan 形态验收 | Task 0 | 0.4 场景 S2 | `test_acceptance_analyst_view.py` |
| AC-4 | 树统计+jump_ready | Task 2 | 循环 A 溯源段统计 | `test_analyst_view_service.py` |
| AC-5 | 段级容错+空态幂等读 | Task 2 | 循环 C 容错矩阵 | `test_analyst_view_service.py` |
| AC-5 | 畸形 242 | Task 3 | 3.1 用例守卫 | `test_analyst_view_use_case.py` |
| AC-6 | CLI 命令 | Task 3 | 3.2-3.4 CLI+注册 | `test_agent_cli.py` |
| AC-7 | P95<800ms+并发 20 | Task 5 | 5.3-5.4 性能场景 | `test_integration_analyst_view.py` |
| 全 AC | 收尾完成清单 | Task 7 | 7.1-7.4 | `test_acceptance_analyst_view.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-7（全量——规范冻结是全部实现的前置）

> **目的：** 在进入代码实现前，明确 VO 键契约、阶段派生规则表、端口契约、验收场景与六边形架构边界，并处置 deferred-work 锚定义务（六条 Epic 6 锚+两条 6.7-DF 维持+两条 D6-8-R 维持——OD-8——R2-2 勘误：R1-F8 漏传播位）。

- [x] Subtask 0.1: 冻结七 VO+枚举键契约（Task 0.1 冻结表落 Dev Agent Record——6/4/5/2/9/5/8 键 + PhaseStatus 三值 + 六阶段静态清单六元组——实现禁增删键）
- [x] Subtask 0.2: 冻结阶段派生规则表（`derive_stage_status` 纯函数两规则+后四恒 not_started——AC-3 规则逐字冻结；实现为纯函数禁读全局禁散落 if 链）
- [x] Subtask 0.3: 定义端口契约（AnalystViewPort v1.0.0 签名+三依赖注册名+组合根落位邻近锚）+ 契约测试文件骨架
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_analyst_view.feature`（12 场景钉死+epics L2451-2453 架构测试三项落位对账——R1 行号勘误：checkbox 实际在 L2451-2453，L2450 是节标题行；显示/快捷键/溯源三要素映射声明）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_analyst_view.py`（6-8 R6 合规形态：三件套+双清+context dict+归档族预置[6-7 `_archive_row`/`_spec_chunk` 直系]+快照直写+PG 三分面通道+CLI 直调 helper；**快照 timeline step 值形态禁复刻 6-8 `_STEP_SEQUENCE`**——R1-F4：6-8 预置序列（`test_acceptance_executive_view.py:100-108` 与集成 :56 双文件）是 `market_insight_trend` 等前缀形态且子步名不符 `MarketInsightStep` 值域（strategy/org/risk/execution 非六子值），是计数面专用非 canonical step 值；本 Story 是首个 timeline step 值消费者，预置必须按写侧实值三形态构造（"performance_gap"/裸六子值/"market_insight_synthesis"——`blm_planning_service.py:309/:414/:504` 写入点实证），八步全序列常量（R2 命名勘误：原「六子序列」易误读为六元组）`('performance_gap','trend','market_customer','competition','self','opportunity','opportunity_gap','market_insight_synthesis')` 期望独立构造）；运行验收测试，确认失败（🔴 红阶段验证——延迟 import ImportError 形态）
- [x] Subtask 0.6: 定义逐场景红锚符号表（12 场景预期红形态：ImportError/exit code/AssertionError——畸形腿天然绿路由纠正注记 6-6 先例）
- [x] Subtask 0.7: deferred-work 锚定义务八条处置落档（OD-8 表——L13/L17/L107/L117+L170/L127/L129 六条 Epic 6 锚+6.7-DF1/DF2 两条维持+D6-8-R1/R2 两条维持——R1-F8 口径统一）
- [x] Subtask 0.8: 关键代码锚点行号复核（并行会话提交会使行号漂移——锚点表基准 HEAD@1a7aa345，实施前复核；**已知漂移注记**：6-8 故事锚 checkpoint_service :2347 实为 :2387/report_repository :3434 实为 :3474——本 Story 锚点表已按当前 HEAD 校正）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（键契约/派生规则/端口/场景钉死/锚定义务）
- [x] 验收测试运行失败（预期行为，红阶段确认——12 场景全红；S1 实测 ModuleNotFoundError: src.application.services.analyst_view_service 与 Task 0.6 符号表 S1~S7/S10/S11 ImportError 形态吻合）

---

### Task 1: 应用层端口与七 VO——`ports/analyst_view.py`（含 PhaseStatus 枚举+六阶段静态清单）

**关联 AC:** AC-1/AC-3

> **六边形落位：** 全部应用层（`src/application/ports/`）——零 domain（OD-12：`BlmPhase` 扩展锚归 Epic 10-1 钦定不可僭越，六阶段静态清单落应用层）。

#### TDD 循环 A：七 VO + 枚举 + 静态清单

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_analyst_view_vos.py`（七 VO 键集 exact set+PhaseStatus 枚举成员/值断言+六阶段静态清单六 (phase_key, phase_name) 对**逐对全量精确匹配（中文全名逐字）**断言——R3-F3 明示：匹配单位是键值对非仅序+构造守卫 242 三形态：plan_id 非空/枚举成员校验裸 str 拒绝/计数 ≥0） |
| 🟢 绿 | 实现 `src/application/ports/analyst_view.py`（PhaseStatus str-Enum+七 frozen dataclass+`__post_init__` 守卫+`BLM_SIX_PHASES` 六元组常量+AnalystViewPort Protocol v1.0.0） |
| 🔄 重构 | docstring 全中文 Google 风格+类型注解收口（六阶段清单 or.md L379 出处注记+V1 归属注记落 phase 常量 docstring），运行 `ruff` + `mypy` |

- [x] Subtask 1.1: 🔴 红 — 编写 VO 键集/静态清单/守卫失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现七 VO+枚举+清单+端口最小代码
- [x] Subtask 1.3: 🔄 重构 — 优化 VO 代码（None/0/() 降级值语义 docstring 化——空 plan 三段降级键注记）
- [x] Subtask 1.4: 🟡 变异 — 键集断言突变实证（删 ToolboxSection 一键 → exact set 红 → 还原绿；六阶段清单序换两元素 → 序断言红）

**完成标准/Definition of Done:**
- [x] 七 VO+枚举+清单+端口实现完成，键契约与 Task 0.1 冻结表逐键一致
- [x] TDD 循环全部通过（红绿变异三态留痕——变异 1 删 categories 键 8 failed/变异 2 清单换序 1 failed/还原 26 passed）
- [x] 覆盖率：新增文件 ≥95%

---

### Task 2: 应用层视图服务——`AnalystViewService` 三段编排 + derive_stage_status

**关联 AC:** AC-1/AC-2/AC-3/AC-4/AC-5

> **三依赖注入：** skill_selector/snapshot_repository/traceability_tree_service（keyword-only 构造——ExecutiveViewService 四依赖同风格）；服务无状态（SINGLETON 并发共享——AC-7 约束）。

#### TDD 循环 A：三段聚合编排（Mock 三依赖）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_analyst_view_service.py` 循环 A 用例（三段聚合：list_active_skills→ToolboxSection[投影白名单五键+categories 分组]；snapshot load→ProgressSection[state_data 解析+degraded_step_count=len() 派生+六阶段派生]；build_trace_tree→TraceabilitySection[三层有效计数（stage/chunk/document）+jump_ready 计数+degraded_stage_count（len(degraded_stages)——R2 补全枚举）+哨兵透传——结论层单根节点注记（R1-F1）]——**Mock spec 形态分述**：skill_selector `AsyncMock(spec=SkillSelectorPort)`+snapshot_repository `AsyncMock(spec=SnapshotRepositoryProtocol)`+traceability_tree_service `AsyncMock(spec=TraceabilityTreePort)`（三端口 Protocol 全在册——组合根 interface 注册面，无需具体类 spec；6-8 checkpoint_service 具体类 spec 是无同名 Port 的例外形态本 Story 不适用）+ `_make_*` 工厂） |
| 🟢 绿 | 实现 `src/application/services/analyst_view_service.py` 三段私有方法+`build_analyst_view` 编排（入口单时间锚一次 now——顶层 generated_at 唯一时间键） |
| 🔄 重构 | 段方法职责收口（每段一方法——`_build_toolbox/_build_progress/_build_traceability`） |

#### TDD 循环 B：derive_stage_status 派生规则矩阵

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编派生矩阵用例（三状态×timeline 形态全枚举 **≥10 格**——R1-F3/F4 补格：阶段1 有/无 performance_gap；阶段2 含 synthesis/仅子步骤/空三种+synthesis-without-subs 脏形态边界格；后四阶段恒 not_started；step_completed 计数边界[子步骤部分完成 1-6/全 7]；**重复条目去重格**（2×trend→step_completed==1+status==in_progress——集合口径判别格）+**值域外脏值格**（`market_insight_trend` 前缀形态→阶段2 not_started——写侧裸值契约防御）） |
| 🟢 绿 | 实现 `derive_stage_status` 纯函数（Task 0.2 冻结规则逐字——timeline step 集合判别；step_completed = len(stage_steps) 与状态派生共用同一集合，禁二次遍历 timeline 计数——R1-F3） |
| 🔄 重构 | 规则表 docstring 化（两规则原文注释——与 AC-3 逐字对齐；synthesis 优先序注记） |

#### TDD 循环 C：段级容错与畸形守卫

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写容错矩阵（三源各一格按语义专属异常：toolbox→SkillNotFoundError/progress→RuntimeError/traceability→通用 Exception——各格断言本段 degraded=True+其余段正常+build_degraded==True；**traceability 双分支格**——R1-F5：抛异常→段降级+tree_build_degraded==False（段降级默认值）/正常返回 build_degraded=True 的树→仅 tree_build_degraded 透传+段 degraded==False）+空 plan 幂等读+state_data 畸形守卫（**逐键处置复刻 6-8 `executive_view_service.py:169-188`**——R1-F6：completed_steps 必备缺→段降级/total_steps `.get` 默认 BLM_TOTAL_STEPS 且 ≤0 显式段降级[除零形态守卫]/timeline、degraded_steps 缺→空列表/phase、current_step `.get` 缺→None[空态同形——6-8 :188 先例；R2 补遗]；「宽容-严格」三分界——6-8 R3-F1 直系） |
| 🟢 绿 | 实现段级 try 包裹+畸形守卫降级（六阶段框架恒在——静态清单不依赖快照） |
| 🔄 重构 | 降级 warning 日志统一（`logger.warning` 段名+异常摘要——6-8 同款） |

- [x] Subtask 2.1: 🔴 红 — 循环 A/B/C 失败测试
- [x] Subtask 2.2: 🟢 绿 — 三段编排+派生函数+容错实现
- [x] Subtask 2.3: 🔄 重构 — 服务代码优化（投影白名单五键常量化/`BLM_PLANNING_SESSION_PREFIX`/`BLM_SIX_PHASES` 常量单源引用——禁字面量；实施攻坚：六阶段值域单源上移 ports 文件 `PHASE_STEP_DOMAINS`/`PHASE_STEP_TOTALS`——空态框架 step_total=[1,7,0,0,0,0] 恒在语义修正，服务与 VO 默认工厂共用单源。**代码审查 R1-F3 勘误：投影白名单半句改为「注释枚举形态（对齐 6-8 executive_view_service :241-244 先例）」——dev 落的 `_TOOL_SUMMARY_FIELDS` 常量全仓零消费是无守护第二源镜像（ToolSummary 字段定义即白名单 SSOT），已删除+构造点注释承载**）
- [x] Subtask 2.4: 🟡 变异 — 规则断言突变实证（阶段2 规则 synthesis 与子步骤判定互换 → 边界格红；投影白名单加一键 → exact set 红；jump_ready 计数改全量 → 混合形态格红）

**完成标准/Definition of Done:**
- [x] 三段编排+派生规则+容错实现完成
- [x] TDD 循环全部通过（变异锚 5 处全实证：①synthesis 优先序互换 2 红②阶段1 判定删除 2 红③投影白名单加 tags 键 2 红④traceability 容错改 raise 2 红⑤jump_ready 改全量 1 红——还原后 61 passed）
- [x] 覆盖率：服务文件 ≥95%（派生规则三分支 100%）

---

### Task 3: 用例 + CLI `analyst-view` + 组合根注册

**关联 AC:** AC-5（守卫）/AC-6（CLI）

> **组装层扩展：** `src/entrypoints/agent_cli.py`（argparse 扁平子命令——executive-view :555 邻位注册）+ `src/composition_root.py`（:2072-2100 executive_view 块邻位双注册）。

#### TDD 循环 A：用例 + 组合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_analyst_view_use_case.py`（UUID 守卫 242 两形态：非 UUID/空串[同分支两输入——6-8 Task 0.8 复核结论]+透传）+ `tests/contracts/test_port_contract_analyst_view.py` 五断言族 |
| 🟢 绿 | 实现 `src/application/use_cases/get_analyst_view.py`（守卫+透传——`GetExecutiveViewUseCase` 直系样板）+ 组合根双注册块（analyst_view_service SINGLETON lambda 三依赖 resolve+analyst_view_use_case SINGLETON 透传） |
| 🔄 重构 | 注册块注释（SINGLETON 捕获 SCOPED 声明[两 SINGLETON+一 SCOPED 混态]+未来 7-2 REST 面改 SCOPED 触发器注记——6-8 OD-11 同款） |

#### TDD 循环 B：CLI analyst-view

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（`_StubAnalystViewUseCase` 替身+专用 patcher（`_patch_analyst_view_entry`——`monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)` + `setattr(agent_cli, "resolve", lambda name: stub)` 形态——**每命令族新建专用 patcher 纪律**[6-8 R1-F11]）：解析/全数据输出（工具箱 23 行计数+六阶段 6 行 status 中文+V1 注记后四+溯源统计行+提示行+**六阶段进度条 k 表枚举（c=0..7 → [0,1,3,4,6,7,9,10] 逐格断言——AC-6 钦定值，进度条形态函数在 `_print_analyst_view`——R2 补入承载位）**）/空态输出（六阶段框架恒在+工具箱照常）/242 stderr+exit 1/exit 0/零可选参数 inspect.getsource 断言/**降级标记双形态格（R3-F1：stub 视图 build_degraded=True+traceability.tree_build_degraded=True → 首行含「（部分数据降级）」+溯源统计行含「（部分树数据降级）」双标记并存断言——stub use case 直构降级 VO 零依赖）**） |
| 🟢 绿 | 实现 CLI：`build_parser` 注册（`--plan-id` required）+分发分支+`_run_analyst_view_cli` 五步定式（UUID 守卫→`_ensure_bootstrapped`→asyncio.run+resolve→打印→DomainError exit 1——R1 勘误：实际函数名带下划线前缀）+`_run_analyst_view` async 壳（finally `_close_connection_pools`）+`_print_analyst_view` 三段打印 |
| 🔄 重构 | 输出行格式统一（「输出即契约」——空态行恒在+进度条 10 格字符形态函数化） |

- [x] Subtask 3.1: 🔴 红 — 用例/契约/CLI 失败测试
- [x] Subtask 3.2: 🟢 绿 — 用例+组合根+CLI 实现
- [x] Subtask 3.3: 🔄 重构 — CLI 打印面优化（实施攻坚：注册注释「--format」字样污染 6-8 既有 test_no_optional_arguments 块边界断言——改写注释措辞消解跨测试块边界耦合）
- [x] Subtask 3.4: 🟡 变异 — CLI 输出断言突变实证（五锚全红实证：①工具箱首行「共」改「总」②242 stderr 前缀去 [③V1 注记置空④k 公式 round 改 int 截断⑤降级标记置空——还原后 4148 passed）

**完成标准/Definition of Done:**
- [x] 用例+CLI+组合根实现完成（resolve 可达+分发接线）
- [x] TDD 循环全部通过（变异锚 5 处全实证）
- [x] 覆盖率：用例 100%/CLI 新增面 ≥90%

---

### Task 4: 契约守护与回归面

**关联 AC:** AC-1（端口契约）/OD-2（零事件）/OD-3（零异常）

> **性质说明：** 契约级守护复跑+新增端口契约测试定稿——非功能实现 Task。

- [x] Subtask 4.1: 端口契约测试五断言族定稿（注册可达/spec 元数据 v1.0.0+SINGLETON+tags/lambda 注入链 getsource 三依赖注册名锚/resolve 可达 isinstance/方法签名 keyword-only——`test_port_contract_executive_view.py` 逐段对齐；6 用例全绿）
- [x] Subtask 4.2: 零事件守护复跑（`tests/contracts/test_event_channel_mapping_pdf_report.py` 6 passed——_FROZEN_EVENT_COUNT=56 零变化；event_channels.yaml/DEFAULT_MAPPINGS 零 diff git 实证）
- [x] Subtask 4.3: 回归面验证（四目录全量零失败——6-7/6-8 既有验收零破坏；agent_cli/composition_root 扩展面既有单测零适配[纯新增子命令/注册块——实测 6-8 既有 test_no_optional_arguments 一次块边界污染已修]；skill_selector 既有生产码消费方 LoadAgentProfileUseCase 零影响；traceability_tree_service 既有消费方 trace-tree CLI 零影响）
- [x] Subtask 4.4: 三红线 grep 自查（`raise ValueError`/`HTTPException`/`Exception(` 继承——新增面零输出；noqa/type: ignore/pylint disable 全部新增文件零输出）

**完成标准/Definition of Done:**
- [x] 契约测试全绿+冻结键数基线零变化
- [x] 四目录全量零失败（第一轮 no-cov+第二轮覆盖率——Task 7.4 承载最终确认）

---

### Task 5: 集成测试——真实三源链聚合

**关联 AC:** AC-1/AC-7

> **真实服务 Schema 隔离子模式**（6-x 集成双子模式选型：真实服务面——三源全真实[工具箱静态真源+Redis 快照+PG/Qdrant 归档族]）+ xdist 同组串行。

#### TDD 循环 A：真实链三段聚合 + 性能并发

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_analyst_view.py`（场景① 全数据三段 round-trip：真实快照直写+归档族预置[6-7 集成样板]（**钦定 chunk_count≠stage_count 形态——如 2 stage×3 chunk 实例，判别计数面错接——R3-F4**）→服务直调值级断言[23 工具+分类 3/3/6/3/8+阶段派生+树统计]；场景② 空 plan 幂等读（工具箱段完整 23——静态真源正交性断言）；场景③ 性能 20 轮 P95<800ms（模块级期望常量+sorted 数学口径+预热；C 面禁 set_session）；场景④ 并发 20 路 gather 全成功+两两相等（**排除集单键 {generated_at}** 剔除对照——asdict 序列化形态；禁 set_session）） |
| 🟢 绿 | 预置/清理通道落地（Redis latest 单键直写+定向 DEL；归档族 PG/Qdrant 直写+定向清理[行数断言]；PG 三分面按场景分组——6-8 R2-F3 直系）+断言通过 |
| 🔄 重构 | 预置工厂函数收口（`_make_snapshot_state`/归档预置复用 6-7 helper 形态） |

- [x] Subtask 5.1: 🔴 红 — 四场景失败测试
- [x] Subtask 5.2: 🟢 绿 — 预置通道+断言通过（实施攻坚：collection 场景级生命周期——teardown 整删后每场景幂等 ensure 重建；集成 ctx 补 _a_mode 键对齐验收 helper 契约）
- [x] Subtask 5.3: 🔄 重构 — 工厂收口+docstring（性能三段口径差声明落模块 docstring——OD-7；归档预置 helper 复用验收形态——_ensure_collection/_preset_qdrant_points_and_pg_rows 参数化 collection 注入）
- [x] Subtask 5.4: 🟡 变异 — 集成断言突变实证（验证型 2 处：total_tools 断言改 22 → 值级红；并发篡改一路 progress → 等价性红——还原后 4 passed）

**完成标准/Definition of Done:**
- [x] 四场景全绿（真实服务零 mock——P95<800ms 实测通过+并发 20 路排除集单键两两相等通过）
- [x] 性能 P95 断言通过+口径声明落档
- [x] 覆盖率：集成新增面 ≥75%

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 六边形架构约束（全 AC 底座）

> **性质说明：** 本 Task 是 **SDD 规范验证测试**——验证代码是否符合架构规则（非功能 TDD）。

#### 架构验证测试实现（四验证器——`test_traceability_tree.py`/`test_executive_view.py` 样板）

- [x] Subtask 6.1: 验证器 A 落位守护（交付文件在 application 层/七 VO+PhaseStatus 定义于 ports 文件非服务本地/服务与用例禁本地 Protocol——AST 扫 ClassDef bases；实施攻坚：模块级常量扫描补 AnnAssign 形态——BLM_SIX_PHASES 等带类型注解常量）
- [x] Subtask 6.2: 验证器 B 零 publish 守护（服务源码 token grep `publish`/`event_publisher` 零出现+AST 零事件构造——pkgutil 强制导入 events 全子模块后 DomainEvent 子类名全集比对 Call 节点）
- [x] Subtask 6.3: 验证器 C 零 domain/infra 改动+依赖方向（`SERVICE_ALLOWED_PREFIXES` 白名单逐 import startswith 断言+三方禁 import frozenset+rglob 零命中结构断言——OD-12 纯三零：src/domain+src/infrastructure 双目录 analyst 词零命中，与 6-8 白名单形态分立）
- [x] Subtask 6.4: 验证器 D CLI 接线（源码含 `add_parser("analyst-view"` 精确锚+`args.command == "analyst-view"` 分发+`resolve("analyst_view_use_case")` 调用锚+组合根双注册块锚）
- [x] Subtask 6.5: 运行完整测试套件并生成报告（ruff E/I 循环依赖检测——不引入 pylint）
- [x] Subtask 6.6: 🟡 变异 — 架构断言突变实证（验证器 B token grep 断言：源码临时注入 `publish` token → 测试红 → 还原绿）

**完成标准/Definition of Done:**
- [x] 四验证器全绿（任何违规即测试失败——13 passed）
- [x] 循环依赖检测用 ruff/isort

---

### Task 7: 开发结束验收测试

**关联 AC:** 全 AC 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_analyst_view.feature` 收尾场景（完成清单存在性断言） |
| 🟢 绿 | 编写 `test_acceptance_analyst_view.py` 收尾 BDD 步骤（`_COMPLETION_SRC_FILES`/`_COMPLETION_TEST_FILES` dict 常量+`path.is_file()` 断言——6-7/6-8 S12 形态） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 7.1: 场景 12 — 验证 `src` 完成清单的逐项确认
- [x] Subtask 7.2: 场景 12 — 验证四测试目录完成清单的逐项确认
- [x] Subtask 7.3: 运行开发结束验收测试并确认通过（12/12 场景全绿）
- [x] Subtask 7.4: 运行 `pytest` 四目录全量、`ruff check`、`mypy` 进行收尾校验+deferred-work 处置注记终检（Task 0.7 八条落档确认）

**完成标准/Definition of Done:**
- [x] `src` 与四测试目录完成清单已逐项验证确认
- [x] 开发结束验收测试通过（12/12 场景全绿）
- [x] Story 可进入 `review`

> **Task 7.4 收尾校验实录（2026-11-07）**：四目录全量两轮——第一轮 no-cov 15193 passed+1 failed（market_insight 集成——单独复跑 5 绿定谳环境负载偶发）/第二轮覆盖率轮 15192 passed+2 failed（blm_planning/market_insight 验收性能类——单独复跑 28 绿定谳同族）——6-9 全部新增测试（26 VO+35 服务+6 用例+12 CLI+13 架构+6 契约+4 集成+12 验收）两轮全绿零失败；覆盖率整体 93%（≥80% 门禁，基线 93.22% 持平不降）+新增三 src 文件 100%（95/81/14 语句零 missing）+ruff 全绿+mypy 762 文件零错误（基线 759+3 新增）+三红线/抑制注释新增面零输出+deferred-work 八条 11 处处置注记终检在位+纯三零 git diff 实证（src/domain+src/infrastructure+src/interfaces 三目录零 diff）。

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构严格分层（本 Story 纯应用层+组装层扩展——**纯三零：零 domain/零 migration/零 infra**，比 6-8 准三零[search fallback 单点增量]更纯——OD-12）；读侧聚合 CQRS 投影形态（三段聚合视图=三源读模型——6-8 第四连直系）
- **设计约束:** 领域层零依赖（零 domain 改动天然满足）；读侧 DTO 归应用层（七 VO+枚举 ports 文件承载）；查询不发布事件（architecture.md:1293——6-8 引用形态注记同款：该行是记忆子系统单行先例+七查询型 Story 零事件族实践）
- **接口治理:** 统一端口注册（新端口 v1.0.0 一次到位）、Registry/Resolver、组合根唯一装配、契约优先、禁同义接口重复（analyst_view 分析师作业面 vs executive_view 高管速览面 vs traceability_tree 溯源完整面——三语义正交）；三依赖全既有注册名消费不新开底层端口
- **技术栈:** Python 3.11+ / Redis（latest 快照单键点查）/ PostgreSQL+Qdrant（经 trace_tree 服务间接——归档族查询）/ pytest-bdd；工具箱段零外部依赖（TOOLS.md 打包文件内存读）
- **关键设计条款:** interface-design.md:2006 三视图表「分析师视图=专业工具执行、溯源树展示、报告生成」为**陈旧口径**（R1 行号勘误：分析师视图行实际 :2006，:2005 是高管视图行）（FR-UI-06/09 引用错位——现 FR-UI-06 决策卡片/FR-UI-09 解码追溯带均 Epic 21 面；本 Story 按 epics L2434 现行权威+「展示不执行」裁定——显式注记不采旧口径，6-8 interface-design 同款注记先例）；prd L1813 FR-ST-01 23 工具清单（or.md 三.前言源）；prd L454「前两阶段覆盖 80% 场景 V1 手动补充后四阶段」MVP 边界

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | **范围边界——MVP = 三段聚合查询面（AnalystViewPort+AnalystViewService+GetAnalystViewUseCase+CLI `analyst-view`）。不含**：Web UI/快捷键/批量操作交互（Web 交互语义——快捷键=键盘事件[Story 21.9 FR-UI-23]、批量操作=工作台证据勾选[Story 22.1 FR-UI-13]、角色自适应[Story 22.8 FR-IF-05]——三者均无后端独立承载面，口径差声明 OD-7）/REST 端点（CLI-only 第八连 6.1-DF5 先例+openapi.yaml 零 diff）/后四阶段流程（`BlmPhase` docstring 钦定 Epic 10 Story 10-1 扩展锚+prd L454 V1 边界——六阶段清单仅呈现框架）/工具执行与 Schema 详情（4-1/4-1a/5-3 已交付执行链——本 Story 展示面非执行面；input/output_schema 是执行面载荷禁入视图）/工具版本统计（L13 灰度锚产品立项）/报告段/审批段/审计段（epics 6.9 AC 无此三面——6-8 已交付，禁重复聚合）/工具箱版本管理 REST 面（4-6 已交付 6 端点——零触碰） | epics L2434-2474 范围权威+L655 UX 三页面格局 + 6.1-DF5 七连 CLI-only 先例 + 6-8 OD-1 边界先例 + YAGNI |
| **OD-2** | **零新增领域事件、零发布、零订阅**（查询型故事第八连）：纯查询聚合面零状态变更——architecture.md:1293 查询零事件先例（引用形态注记见 Dev Notes）+6-4/6-5a/6-5b/6-6/6-7/6-8 六连零事件先例族；event_channels.yaml/DEFAULT_MAPPINGS 零 diff；`_FROZEN_EVENT_COUNT=56` 零变化（Task 4.2 守护复跑）；蓝图无分析师视图事件载体；架构验证器 B 零 publish 守护 | 查询语义纯度+先例族+零 yaml/router diff 红利 |
| **OD-3** | **零新增领域异常、零既有异常改动**：242 复用（畸形 plan_id 用例层 UUID 守卫——`GetExecutiveViewUseCase` 直系先例）；`SkillNotFoundError` 既有异常**消费不新增**（selector fail-loud「缺档案是资产缺陷」语义在聚合面收敛为段降级+warning——段级容错承载非异常路径）；空 plan 幂等读不抛（6-4/6-6/6-7/6-8 四先例族）；480 **不消费不复现**（单点查询面抛 vs 聚合面空态——6-8 OD-3 语义分立直系）；planning 480-489[488/489 预留]/report 490-499[494-499 预留]/traceability 372-379 预留三段零触碰（无 view 码段亲验）。**否决备选**：开新码（AnalystViewError）——三段降级+242 后无真实 raise 触发面，开码即引入「空 plan 误报」反语义面（6-7/6-8 OD-3 否决论证同构） | 异常语义纯度+四先例+空态幂等读语义 |
| **OD-4** | **七 VO 键契约+PhaseStatus 三值枚举**（Task 0.1 冻结）：`AnalystView` 6 键（plan_id/generated_at[ISO 单时间锚]/build_degraded[顶层降级哨兵]/三段）/`ToolboxSection` 4（degraded/total_tools/tools/categories）/`ToolSummary` 5（**投影白名单**：slug/tool_name/category/description/status——`ToolMetadata` **18 字段**面防扩散：白名单外 13 字段 input_schema/output_schema/when_to_use/when_not_to_use/capabilities/tags/version/rule_version/token_budget_l1/token_budget_l2/depends_on/triggers/data_sources 禁入视图——R1-F2 勘误）/`ToolCategorySummary` 2/`ProgressSection` 9（步级计数直读+stages 六阶段全景）/`PhaseProgress` 5/`TraceabilitySection` 8（**两层哨兵分立**：段 degraded[本段编排异常] vs tree_build_degraded[6-7 树顶层降级透传]；available==stage_count>0——结论层恒单根节点剔除统计面、conclusion_count 键位改 chunk_count 补齐切片层计数：R1-F1 修订）——全应用层 frozen dataclass；`PhaseStatus` 三值 str-Enum（completed/in_progress/not_started——**进度态语义域**与 `ExecutiveHealth` 健康分级域正交分立；全仓首个三值进度态枚举——6-8「全仓首个三值分级枚举」注记不冲突，落 ports 文件同先例）；键恒在纪律（None/0/() 降级值——6-2 R1-6 七键契约族）；**不透传树 generated_at**（并发对照排除集最小化——排除集仅顶层 {generated_at} 单键，OD-6 联动） | 键恒在纪律+读侧 DTO 层位先例+投影白名单安全面（6-8 审计 15 键投影白名单同款）+语义域正交 |
| **OD-5** | **六阶段静态清单+派生规则表（Task 0.2 冻结）**：六元组常量 `BLM_SIX_PHASES` 落应用层 ports 文件（阶段序 or.md L379 权威原文：performance_gap 业绩差距分析/market_insight 市场洞察/strategic_intent 战略意图与目标/innovation_focus 创新焦点/business_design 业务设计/execution_design 执行设计；**零改动 `BlmPhase` 枚举**——:45-46 docstring「六阶段完整版归 Epic 10 Story 10-1（FR-SP-05）在同文件扩展——本枚举预留扩展锚」钦定不可僭越，应用层静态清单是呈现框架非流程扩展）；派生规则确定性纯函数 `derive_stage_status`（阶段1=timeline 含 "performance_gap"→completed；阶段2=含 "market_insight_synthesis"→completed/含任一六子裸值→in_progress/否则 not_started——synthesis 优先序；阶段3-6 恒 not_started——step_total==0 规划态+「V1 交付」注记归 CLI 呈现不进 status 值域）；step_completed 计数同源 timeline（阶段2=六子裸值+synthesis **集合基数——去重口径**，R1-F3——R2-1 勘误：创建期「条目数」旧口径残留位）；空 plan 六阶段框架恒在（静态清单不依赖快照——「框架恒在+数据缺席降级」） | or.md L379 权威+BlmPhase 扩展锚钦定+prd L454 V1 边界+确定性规则（6-8 derive_health 纯函数先例） |
| **OD-6** | **溯源段口径——depth=4 全树统计+纯派生**：`build_trace_tree(plan_id, depth=4)` 钦定全树（jump_ready_count 需文档层——depth<4 不可达；统计语义完整性优先）；段五计数+哨兵全派生自树对象（stage=分析层 len(root.children)/chunk=切片层/document=文档层节点实例/jump_ready=True 计数/degraded_stage=len(degraded_stages)——**结论层恒单根节点（root 自身）不计入统计面**：R1-F1）——**树构建逻辑零触碰**（6-7 交付面只消费）；两层哨兵分立（段 degraded vs tree_build_degraded 透传——「本段编排拿不到」vs「树内拿不到」语义正交）；available==stage_count>0（空树幂等非异常——6-7 空树语义在聚合面透传）；操作提示「执行 trace-tree 查看完整树」指向既有命令（6-8「可先执行 report-generate」同款——**指向既有命令的操作提示非新功能**） | 6-7 交付面只消费+jump_ready 观测锚（「30 秒溯源」节点级观测面 :24-27 docstring 钦定）+空树幂等语义 |
| **OD-7** | **性能三段口径声明**：① 视图加载 P95<800ms = `build_analyst_view` 服务面窗口（三读串行：list_active_skills 内存遍历微秒级+snapshot load Redis 单键点查+build_trace_tree 全树[三读最重——query_archive PG+get_point/find Qdrant]；20 轮 `sorted[ceil(0.95*n)-1]` 数学口径；**风险注记**：trace_tree 全树成本随归档量增长——万行级归档触发统计端口/物化视图立项锚 Epic 7/21，docstring 注记）；② 并发 20 = 单一数据源 plan_id×20 路并发读（asyncio.gather+服务无状态+两两相等——**排除集单键 {generated_at}**：toolbox 静态真源恒稳/progress 单键读恒稳/traceability 段不透传树 generated_at[OD-4 联动设计收益]——排除集最小化；asdict 序列化剔除对照；禁 set_session 每路独立[6-8 R2-F3 C 面]；「批量操作」读面等价口径声明——本义工作台证据勾选 Web 交互归 22.1）；③ 快捷键<100ms=前端指标后端不定义（epics L2457 原文——键盘事件响应归 Epic 21 Story 21.9 届时验收）+溯源跳转<300ms=6-7 已交付口径（跳转载荷组装承载——本 Story 溯源段是统计摘要面非跳转执行面，跳转执行归 trace-tree 既有命令）——③ 两项口径差声明落验收/集成 docstring | epics L2456-2458 性能行与 CLI 交付面口径对齐（6-3/6-6/6-7/6-8 五连口径差声明纪律）+OD-4 排除集最小化联动 |
| **OD-8** | **锚定义务八条处置**（Task 0.7 落档）：**L13**（灰度推进/per-version 统计视图——触发=产品立项）：不触发（工具箱段是 ACTIVE 状态清单非版本统计面；锚位维持）；**L17**（langgraph retry/timeout——第六轮同构不触发）：纯读侧聚合零图引擎/checkpoint_table 消费（5-10/6-1/6-6/6-7/6-8 五轮先例延续）；**L107**（B2 事件驱动摄取——触发=Epic 6 首个 Skills 消费场景定型）：**甄别声明不触发**——本 Story 消费 skill_selector 是 L1 元数据静态清单展示（TOOLS.md 打包文件内存读），非 B2 摄取桥语境的「Skills 外部数据消费场景」（crawl 产物注册文档管道+data_source 持续供给——B2 关注的是工具执行时的外部数据摄取形态），锚位不变；**L117/L170**（RabbitMQ 消费侧零接线——触发=首个消费方 Story）：顺延 Epic 8（纯查询面零事件订阅——八连零消费延续）；**L127**（unified_storage+L0/memory 12 端口——触发=Epic 6）：不触发锚位顺延（纯读侧聚合零记忆消费——6-1/6-3 同款）；**L129**（orchestration_service/data_pipeline 轨）：第四轮维持注记顺延（读侧聚合非批量报告管线——6-5a/6-5b/6-8 三轮同构；再锚定条件 6-11/Epic 7 不变）；**6.7-DF1/DF2**（finding 级引文/bbox 四元组）：锚位维持 Epic 21/22（6-8 已重锚——CLI-only 无 Web 高亮面，树读侧透传已就绪零改动）；**D6-8-R1/R2**（CLI .env 加载/json_chain S 编号残留——L402-403）：非 6-9 修复面维持（新增子命令沿用既有 agent_cli 入口形态——.env 缺口波及全命令族非本 Story 引入；json_chain 文件零触碰——表 :640 行处置；R1-F8 补登：创建期 OD-8 枚举漏此组与八条表不符） | deferred-work 原文触发条件逐条对表+六轮先例链+CLI-only 形态裁定连锁 |
| **OD-9** | **测试文件命名（禁故事编号后缀）+ 词族统一 analyst_view**：acceptance `test_acceptance_analyst_view.feature/.py`；integration `test_integration_analyst_view.py`（**对 epics L2471 钦定名 `test_analyst_view_integration.py` 的显式偏离**——仓规 test_integration_* 前缀，6-8 OD-9 同款偏离声明）；unit/architecture `test_analyst_view.py`（**对齐 epics L2470 钦定名**——本 Story 无偏离）；`analyst` 词族 src+tests 零占用亲验（grep 命中均非视图词族：role.py:19 docstring 角色名示例+约 9 个测试文件的 agent_role/agent_id/accessor 夹具值——R1 枚举放宽）；CLI 子命令 `analyst-view` 无重名亲验（add_parser **15** 命令族 grep——本 Story 落地后 16；R1-F7 计数勘误：创建期误计 16）；service 单测 `test_analyst_view_service.py`+VO 单测 `test_analyst_view_vos.py`；契约 `test_port_contract_analyst_view.py`（五断言族） | 记忆「禁止故事编号命名文件」+仓规前缀惯例+词族零占用亲验（epics 钦定名的采纳/偏离逐处声明——6-8 OD-9 同款） |
| **OD-10** | **工具箱口径——SkillSelectorPort 消费+ACTIVE 清单+23 事实断言**：选 `list_active_skills()`（async——与服务编排签名一致；ACTIVE 纯过滤语义正确；L1 元数据贴合展示——description 是一句话功能描述；**Agent 系统同源口径**：LoadAgentProfileUseCase 拼 Agent 工具上下文同链——「分析师看到的工具箱=Agent 可用的工具箱」口径一致性）**不选** `ToolRegistryServicePort.list_all_tools()`（sync 签名风格不一致+Tool 实体 schema dict 是执行面载荷对展示冗余）；23 断言语义=「MVP 交付时点 23 工具全 ACTIVE 事实」（get_all_slugs 静态真源 23 slug+当前全 active 亲验——未来工具转 deprecated 断言红是**预期退化信号**非 flake，防清单静默缩水）；分类分组序=slug 清单稳定序去重序（selector 返回序派生禁字母序重排——`registry/selector.py` docstring「返回顺序与清单一致是断言契约」）；分类计数配比 3/3/6/3/8（Story 4.1 AC-2 钦定——environment_analysis 3/competitive_analysis 3/strategic_selection 6/business_model 3/execution_management 8） | 端口选型实证（签名/语义/载荷三轴）+Story 4.1 AC-2 配比权威+防退化断言语义 |
| **OD-11** | **组合根双注册+三既有依赖复用+零新仓储成员**：`analyst_view_service`（SINGLETON——无状态聚合读；lambda resolve 三既有注册名：`skill_selector` :3011[**SINGLETON**]/`snapshot_repository` :950[SCOPED]/`traceability_tree_service` :2021[**SINGLETON**]——**两 SINGLETON+一 SCOPED 混态的 SINGLETON 捕获声明**（6-8 OD-11 三 SCOPED+一 SINGLETON 混态同款注记先例；CLI 一次性进程+测试双清下无故障面）+`analyst_view_use_case`（SINGLETON 透传）；**零新 PG 仓储家族成员/零 infra 面**；三依赖注入端口面（AsyncMock spec=SkillSelectorPort/SnapshotRepositoryProtocol/TraceabilityTreePort——三 Protocol 全在册无需具体类 spec）；6-4 CLI session P0 三步排查法核验：lambda 无新 PG 构造/无新仓储成员——无 session_factory 缺口面（trace_tree 服务内部经组合根会话包装消费——6-7 交付形态只读复用） | 6-8 OD-11 组合根先例+端口 Protocol 在册实证+单租户口径延续 |
| **OD-12** | **纯三零 Story：零 domain+零 migration+零 infra**（比 6-8 准三零更纯——6-8 有 audit search fallback ~6 行单点增量，本 Story 三源全既有零适配缺口）：七 VO+PhaseStatus+六阶段静态清单全应用层（ports 文件——`BlmPhase` 扩展锚归 10-1 钦定+读侧 DTO 归应用层双依据）；本 Story 改动面=**src 面 3 新建+2 扩展**（R2-3 勘误：创建期 headline「4 新建+2 扩展」计数失实——src 3 新建[ports/analyst_view.py+services/analyst_view_service.py+use_cases/get_analyst_view.py]+2 扩展[agent_cli.py+composition_root.py]；tests 面 8 新建+1 扩展[test_agent_cli.py 扩展；infra 测试零扩展——R1 勘误：创建期误写「2 扩展」与 File List 不符]）——**架构验证器 C 零命中断言**（src/domain+src/infrastructure 均零命中——与 6-8 白名单形态分立：彼有钦定单文件增量故白名单，此零 infra 改动故零命中） | 三源既有零缺口（工具箱内存读/快照单键读/树服务只读复用）+最小改动面形态 |
| **OD-13** | **progress 段与 6-8 planning 段口径分立声明**：两视图服务正交非演进——6-8 `PlanningSection` 是**步级摘要**（completed/total 8 步+int percent——高管速览语义）；6-9 `ProgressSection` 是**阶段级全景**（六阶段框架+stages 逐段 status+步级计数并存——分析师作业语义「流程走到哪个阶段」）；progress_percent 公式同口径（int 向下取整——6-8 R1-F3 VO 侧整数口径钦定直系）但**两 VO 各自独立字段非共享**（禁抽象共享段 VO——两视图消费方/演进节奏不同，YAGNI；共享的是数据源[快照七键]非投影） | epics 6.9「六阶段进度可视化」vs 6.8「仪表盘」需求语义分立+读侧投影独立演进原则 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── application/
│   ├── ports/analyst_view.py              ★ 新建（PhaseStatus 枚举+BLM_SIX_PHASES 常量+七 VO+AnalystViewPort v1.0.0——Task 1）
│   ├── services/analyst_view_service.py   ★ 新建（三段编排+derive_stage_status——Task 2）
│   └── use_cases/get_analyst_view.py      ★ 新建（UUID 守卫+透传——Task 3）
├── entrypoints/agent_cli.py               ▲ analyst-view 子命令（Task 3——executive-view :555 邻位）
└── composition_root.py                    ▲ 双注册块（Task 3——:2072-2100 executive_view 块邻位）

（src/domain/ 零改动；src/infrastructure/ 零改动；src/interfaces/ 零改动——OD-12 纯三零）

tests/
├── unit/
│   ├── application/test_analyst_view_vos.py                ★ 新建（Task 1）
│   ├── application/test_analyst_view_service.py            ★ 新建（Task 2——派生矩阵+容错矩阵）
│   ├── application/use_cases/test_analyst_view_use_case.py ★ 新建（Task 3）
│   ├── architecture/test_analyst_view.py                   ★ 新建（Task 6——四验证器）
│   └── interfaces/cli/test_agent_cli.py                    ▲ analyst-view 扩展（Task 3）
├── integration/test_integration_analyst_view.py            ★ 新建（Task 5，OD-9）
├── contracts/test_port_contract_analyst_view.py            ★ 新建（Task 3/4——五断言族）
└── acceptance/
    ├── test_acceptance_analyst_view.feature/.py            ★ 新建（Task 0/7，R6 模板+OD-9）
    └──（6-7/6-8 既有测试文件零修改——Task 4 回归验证）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 八条处置注记（Task 0.7/7.4）
```

（▲ 修改 / ★ 新建 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话亲验 2026-11-07+四 Agent 调研交叉；行号基准 HEAD@1a7aa345，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| 工具清单查询端口 | `src/application/ports/skill_selector.py:28`（`SkillSelectorPort.list_active_skills`） | `async def list_active_skills() -> tuple[ToolMetadata, ...]`——ACTIVE 纯过滤+slug 清单稳定序；`SkillNotFoundError`（EXCEPTION_387——tool_exceptions.py:208，8 处 raise 全在 loader.py——R1 补锚）传播（工具箱段数据源——OD-10 选型钦定） |
| ToolMetadata | `src/application/ports/skill_loader.py:29`（字段区 :53-72） | L1 元数据 frozen dataclass **18 字段**（tool_name/slug/category/input_schema/output_schema/description/when_to_use/when_not_to_use/capabilities/tags/version/status/rule_version/token_budget_l1/token_budget_l2/depends_on/triggers/data_sources——**投影白名单五键外 13 字段禁入视图** OD-4——R1-F2 勘误） |
| selector 实现 | `src/application/skills/registry/selector.py:27`（`SkillSelector.list_active_skills` :35——R1 行号勘误） | get_all_slugs 枚举→逐 slug load_metadata→status=="active" 过滤——返回序契约 docstring 钦定 |
| L1 缓存机制 | `src/application/skills/loader.py:96-104`（`InMemorySkillLoader.__init__`→`_init_metadata_cache`） | TOOLS.md 打包文件 markdown 表解析内存缓存——**零外部服务依赖**（验收面天然真实可达） |
| 23 slug 静态真源 | `src/application/skills/skill_manifest.py`（`get_all_slugs()`）+ `TOOLS.md` 23 行 | 配比 3/3/6/3/8（Story 4.1 AC-2）；首 slug=pestel-analysis/末=change-management（首末锚） |
| 备选端口（不采） | `src/application/ports/tool_registry_service.py:60`（`list_all_tools`） | 同步 Tool 实体含 schema dict——OD-10 选型裁定不采依据 |
| latest 快照读径 | `src/application/ports/blm_planning.py:63`（`BLM_PLANNING_SESSION_PREFIX`）+ state_data 七键 SSOT :10-12 | session_id=`blm-planning-{plan_id}`；timeline 条目六键；step 实值三形态（"performance_gap"/六子裸值/"market_insight_synthesis"——派生规则输入面） |
| 快照仓储端口 | `src/domain/ports/snapshot_repository_protocol.py:14-28` | `load(session_id) -> CheckpointSnapshot \| None`——progress 段数据源；load 吞异常归一 None 退化语义注记（`redis_snapshot_store.py:179-181`——6-8 R1-F2 同款） |
| `BlmPhase` 扩展锚 | `src/domain/value_objects/blm_phases.py:42-50` | **仅 2 值**+docstring「六阶段完整版归 Epic 10 Story 10-1 在同文件扩展——本枚举预留扩展锚」——**零改动钦定依据**（OD-5） |
| 六子步骤枚举 | `src/domain/value_objects/blm_phases.py:53-65`（`MarketInsightStep`） | TREND/MARKET_CUSTOMER/COMPETITION/SELF/OPPORTUNITY/OPPORTUNITY_GAP——阶段2 in_progress 判别值域 |
| `BLM_TOTAL_STEPS` | `src/domain/value_objects/blm_phases.py:31` | total_steps 期望 8 常量（对照注记） |
| 进度反序列化先例 | `src/application/use_cases/get_blm_planning_status.py:59-88` | state_data→VO 反序列化样板（:55-56 load None 抛 480 是单点面语义——本 Story 不复现 OD-3） |
| 溯源树端口 | `src/application/ports/traceability_tree.py:146-173`（`TraceabilityTreePort.build_trace_tree`） | `(*, plan_id: str, depth: int = 4) -> TraceabilityTree`——**不抛业务异常/空树幂等**（溯源段数据源） |
| 树顶层 7 键 | `src/application/ports/traceability_tree.py:124-143`（`TraceabilityTree`） | plan_id/root/adopted_archives/total_archives/degraded_stages/build_degraded/generated_at 七键（R1 补全：原列 5 缺 plan_id/root）——段统计派生源（root.children 分析层/degraded_stages len/build_degraded 透传） |
| `DocumentNode.jump_ready` | `src/application/ports/traceability_tree.py:24-27/:41-65` | 跳转载荷六键+jump_ready 派生布尔（object_key 非空且 page 非 None）——「30 秒溯源」节点级观测面（prd L243）；**depth=4 钦定依据**（文档层第四层——OD-6） |
| 四层 VO 结构 | `src/application/ports/traceability_tree.py`（ConclusionNode/StageNode/ChunkNode/DocumentNode） | 结论层 children→分析层 children→切片层 children→文档层——段计数遍历路径 |
| 6-8 复刻样板（端口） | `src/application/ports/executive_view.py:214-232`（`ExecutiveViewPort`）+ 六 VO :28-211 | AnalystViewPort 直系形态（keyword-only+空态幂等 docstring） |
| 6-8 复刻样板（服务） | `src/application/services/executive_view_service.py`（derive_health :67/编排 :126-153/四段私有方法 :155-290） | 三段编排+段级 try+单时间锚直系样板 |
| 6-8 复刻样板（用例） | `src/application/use_cases/get_executive_view.py:25-48` | UUID 守卫 242+透传直系样板 |
| CLI 注册样板 | `src/entrypoints/agent_cli.py`：executive-view 注册 :555-565/async 壳 :1481/打印 :1493-1564/五步定式 :1567-1600（`_ensure_bootstrapped` :1589）/分发 :2193-2194 | analyst-view 直系样板（argparse；零可选参数 inspect 断言样板见下行 CLI 单测 :3215-3222——R1 归属勘误：该锚在 test_agent_cli.py 非 agent_cli.py） |
| CLI 单测样板 | `tests/unit/interfaces/cli/test_agent_cli.py`：6-8 节 :3090-3363（`_StubExecutiveViewUseCase` :3179/`_patch_executive_view_entry` :3194/in-process 直调 :3246） | analyst-view 测试直系复刻（**每命令族专用 patcher 纪律**） |
| 组合根注册样板 | `src/composition_root.py:2072-2100`（executive_view 双注册块） | analyst_view 双注册直系复刻（注释块+SINGLETON 捕获声明+触发器注记） |
| 三依赖注册名 | `composition_root.py`：skill_selector :3011（SINGLETON）/snapshot_repository :950（SCOPED）/traceability_tree_service :2021（SINGLETON） | lambda resolve 三目标（主会话亲验 HEAD@1a7aa345——**6-8 故事锚 :2347/:3434 已漂移至 :2387/:3474 本表按当前 HEAD**） |
| 端口契约测试样板 | `tests/contracts/test_port_contract_executive_view.py`（五断言族 :20/:27/:38/:51/:68/:85） | 本 Story 契约测试直系复刻 |
| 架构验证样板 | `tests/unit/architecture/test_executive_view.py`（四验证器）+ `test_traceability_tree.py` | 本 Story 架构验证直系复刻（验证器 C 零命中形态——OD-12 分立注记） |
| 验收样板（R6 模板） | `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`（243 行）/.py（863 行） | **用户钦定 R6 模板**：AC 横幅分节+@scenario 双行字面量+docstring+pass 形态 |
| 验收样板（6-8 最新） | `tests/acceptance/test_acceptance_executive_view.py`（1495 行——R6 合规修正后） | 三件套 :139-149/双清 :152-158/context dict :168-197/CLI 直调 :1252-1272——本 Story 直系复刻 |
| 归档族预置样板 | `tests/acceptance/test_acceptance_traceability_tree.py`：`_archive_row` :319/`_spec_chunk` :366/`_preset_qdrant_points_and_pg_rows` :388/`_teardown_tree_assets` :473 | 溯源段验收预置直系样板（6-7 交付） |
| 快照预置样板 | `tests/acceptance/test_acceptance_executive_view.py`（`_save_snapshot` :496）+ 6-6 `test_acceptance_checkpoint_recovery.py` | latest 快照直写通道——progress 段预置；**⚠️ 6-8 `_STEP_SEQUENCE`（:100-108，`market_insight_trend` 前缀形态且子步名不符 `MarketInsightStep` 值域）是计数面专用非 canonical step 值——6-9 派生规则按裸值值域过滤，禁直系复刻**（R1-F4——本 Story 预置序列按写侧三形态重定义，见 Subtask 0.5） |
| 冻结键数基线 | `tests/contracts/test_event_channel_mapping_pdf_report.py:24` 等 | `_FROZEN_EVENT_COUNT=56`——零新增事件守护（Task 4.2） |
| epics Story 6.9 定义 | `_bmad-output/planning-artifacts/epics_v1.0.md:2434-2474` | AC 三要素/性能三项/测试文件名钦定源（L655/L2019 依赖行） |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-9 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L13（灰度推进/per-version 统计视图） | 工具版本统计视图（触发=产品立项；数据面 `list_by_tool` 已就绪） | **不触发，锚位维持「产品立项」**（OD-8）：工具箱段是 ACTIVE 状态清单非版本统计面；台账注记 |
| 2 | L17（langgraph retry/timeout 字段） | 触发=checkpoint_table/图引擎字段消费方 | **第六轮同构不触发，锚位顺延**（OD-8）：纯读侧聚合零图引擎/零 checkpoint_table 消费（5-10/6-1/6-6/6-7/6-8 五轮先例延续）；注记落档 |
| 3 | L107（B2 事件驱动摄取+持续数据供给） | 摄取桥触发=Epic 6 首个 Skills 消费场景定型（消费形态决定注册粒度与解析深度） | **甄别声明不触发**（OD-8）：本 Story 消费 skill_selector 是 L1 元数据静态清单展示（TOOLS.md 打包文件内存读零外部数据），非 B2 语境的「工具执行外部数据消费场景」；锚位不变；台账注记 |
| 4 | L117/L170（RabbitMQ 消费侧零接线） | reliable 通道只发不收；触发=首个消费方 Story（register_handler 键语义错位未修复前禁止激活） | **顺延 Epic 8**（OD-8）：纯查询聚合面零事件订阅（八连零消费延续）；注记落档 |
| 5 | L127（unified_storage+L0/memory 12 端口休眠） | 触发=Epic 6（6-1/6-3 均已裁定顺延） | **不触发，锚位顺延**（OD-8）：纯读侧聚合零记忆消费（6-1/6-3 同款）；注记落档 |
| 6 | L129（orchestration_service/data_pipeline 轨） | 再锚定=批量报告管线需求（6-11/Epic 7）或废弃定夺 Epic 7 | **第四轮维持注记顺延**（OD-8）：读侧聚合非批量报告管线（6-5a/6-5b/6-8 三轮同构）；注记落档 |
| 7 | L395/L396（6.7-DF1 finding 级引文/6.7-DF2 bbox 四元组——R1 行号勘误：DF1 实际 L395，L394 空行） | finding 级引文 defer V1；bbox 触发=「6-8 Web 高亮立项」——6-8 已重锚 Epic 21/22 | **锚位维持 Epic 21/22**（OD-8）：CLI-only 无 Web 高亮/句级面；树读侧 payload 透传已就绪零改动；注记落档 |
| 8 | L402-403（D6-8-R1-1 CLI .env 加载/D6-8-R1-2 json_chain S 编号残留） | 6-8 审查登记两条（触发=CLI 入口标准化部署形态立项/下次触及该文件） | **非 6-9 修复面维持**：本 Story 新增子命令沿用既有 agent_cli 入口形态（.env 缺口波及全命令族非本 Story 引入）；json_chain 文件零触碰；注记落档 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-8 高管简化视图](./6-8-executive-simplified-view.md)（五轮文档审查+五轮代码审查收敛 done v1.6.0）+ 6-7（溯源树/归档预置）+ 6-5a（并发采样）

**关键学习/Key Learnings:**
- **Agent 误报主会话复核**（6-5b/6-6/6-7/6-8 四连教训）：调研结论关键锚点主会话亲验后方可入 Story——本 Story 已亲验 14 组关键事实（epics 三行依赖/BlmPhase 扩展锚 docstring/skill_selector 签名与 ACTIVE 序契约/loader 内存缓存零外部依赖/get_all_slugs 23+配比 3/3/6/3/8/trace_tree 端口签名与空树幂等/jump_ready 派生条件/组合根 11 注册名行号[含 6-8 故事锚漂移订正 :2387/:3474]/analyst 词族零占用/CLI 15 命令族无重名（R1 勘误——创建期误计 16）/deferred-work 八锚原文/_FROZEN_EVENT_COUNT=56 三处/openapi 零 BLM 端点/R6 模板 @scenario 形态）
- **读侧消费既有冻结面纪律**（6-5b/6-7/6-8 直系）：三源全既有端口消费零演进——skill_selector 单方法消费/快照单键读/树服务只读复用；480 语义分立（单点面抛 vs 聚合面空态——第三连）
- **降级哲学段级化**（6-5b 节点→6-7 树形→6-8 段级→本 Story 段级+两层哨兵）：顶层 build_degraded+段级 degraded+树顶层哨兵透传（tree_build_degraded 与段 degraded 语义正交——「本段拿不到」vs「树内拿不到」）——**空态四连先例族**（6-4/6-6/6-7/6-8）续写空 plan 幂等读
- **投影白名单**（6-8 审计 15 键→本 Story ToolMetadata 18 字段面——R1-F2 勘误）：展示面 VO 只投影消费键——输入/输出 schema/负向触发词/token 预算 L1/L2 等执行面载荷禁入视图（安全面+载荷面双收益）
- **断言判别力**：exact set 键集/分类和恒等式（sum==total）/首末 slug 序锚/阶段状态值级（三 plan 三形态）/jump_ready True-False 混合形态判别（计数既非全 0 亦非全量）/23 事实断言语义（预期退化信号非 flake）
- **CLI 直调双清**（6-6 R3-1 实跑证伪教训）：clear_singleton+clear_scoped 双清+禁二次 bootstrap——S8/S9 钦定直系
- **性能口径差声明**（五连纪律）：P95/并发/前端指标三段口径落 OD+docstring——「批量操作」读面等价口径声明（本义 Web 交互归 22.1）
- **行号漂移防御**（本 Story 实例）：6-8 故事锚 checkpoint_service :2347 在 6-8 后续提交中漂移至 :2387——本 Story 锚点表按当前 HEAD@1a7aa345 校正+Task 0.8 复核惯例维持

**应用到本故事/Applied to This Story:**
- [x] 14 组关键锚点主会话亲验（创建期已执行——锚点表承载）
- [x] 三既有端口零演进+组合消费（OD-1/OD-11）
- [x] 段级容错+顶层哨兵+两层哨兵分立+空态幂等读（AC-5/OD-4/OD-6）
- [x] 投影白名单/exact set/恒等式/序锚/混合形态五类断言形态（Task 2 矩阵）
- [x] CLI 双清+禁二次 bootstrap（S8/S9）
- [x] 性能三段口径差声明（OD-7）
- [x] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep

### 其他约束速查

- **风险集中登记**：①口径风险=阶段派生规则表（Task 0.2 冻结唯一版本+单测矩阵全枚举——synthesis 优先序边界格）；②契约风险=七 VO 键契约+投影白名单（Task 0.1 冻结——实现禁增删键禁扩投影）；③清理风险=PG 面三分面（A 编程面回滚式/B CLI 面 clear_session+commit+定向 DELETE 行数断言/C 并发面禁 set_session 每路独立——6-8 R2-F3 直系；Redis latest 单键定向 DEL；归档族 PG/Qdrant 定向清理[6-7 `_teardown_tree_assets` 样板]）；④判别风险=23 事实断言语义注记（防误判 flake——预期退化信号）；⑤性能风险=trace_tree 全树成本随归档量增长（MVP 量级远小于门限——万行级触发统计端口立项锚 Epic 7/21，docstring 注记）；⑥装配风险=三依赖注册名漂移（lambda resolve 以 grep 为准——Task 0.8 复核；本 Story 已按 HEAD@1a7aa345 校正 6-8 期漂移两处）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore/pylint disable；提交信息禁 AI 署名
- **覆盖率**：整体 ≥80%（基线 93.22%）/ application ≥85%（主改动层——epics L2461 对齐；新增文件 ≥95%）/ domain ≥90% 维持 / 集成 ≥75%（epics L2462 对齐）
- **验收零 mock 全真实**（pytest.skip() 动态跳过；三通道真实服务——静态真源[工具箱]/Redis[快照]/PG+Qdrant[归档族]；段级异常容错归单测 AsyncMock——验收面无故障注入通道，6-8 分立同款）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）
- **xdist 串行组**：pytestmark `xdist_group("blm-planning-perf")` 整模块挂法（6-7/6-8 同组）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（create-story：GLM 调度） |
| **Version** | create-story workflow（bmad-create-story skill v6.3.0） |
| **Execution Date** | 2026-11-07 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.9 定义 L2434-2474；依赖行 L655/L2019；Epic 21/22 章 L3354/L3388） |
| **架构文档** | `docs/architecture/architecture.md` + `docs/architecture/interface-design.md`（三视图表 L2006 陈旧口径注记——R1 行号勘误） |
| **UX/需求规范** | `_bmad-output/planning-artifacts/ux-design-specification.md`（三页面 L1630/工作台 L1758 区）+ `prd.md`（FR-ST-01 L1813/BLM 六阶段 L454/L484/L1875）+ `or.md`（六阶段 L379/工具箱 L215） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-8-executive-simplified-view.md`（v1.6.0 收敛定稿——直系样板） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 实现计划与规范冻结 Implementation Plan & Frozen Specs（Task 0——dev-story 实施时落档）

#### Task 0.1 七 VO+枚举键契约冻结表（实现禁增删键）

| VO/枚举 | 键数 | 键清单（序=字段序） |
|---|---|---|
| `AnalystView` | 6 | plan_id: str / generated_at: str / build_degraded: bool / toolbox: ToolboxSection / progress: ProgressSection / traceability: TraceabilitySection |
| `ToolboxSection` | 4 | degraded: bool / total_tools: int / tools: tuple[ToolSummary, ...] / categories: tuple[ToolCategorySummary, ...] |
| `ToolSummary` | 5 | slug: str / tool_name: str / category: str / description: str / status: str（**投影白名单**——ToolMetadata 其余字段禁入） |
| `ToolCategorySummary` | 2 | category: str / tool_count: int |
| `ProgressSection` | 9 | available: bool / degraded: bool / phase: str \| None / current_step: str \| None / completed_steps: int / total_steps: int / progress_percent: int / degraded_step_count: int / stages: tuple[PhaseProgress, ...]（六元组恒在）。**空态/段降级共用默认值钦定（R3-F2）：phase=None/current_step=None/completed_steps=0/total_steps=0/progress_percent=0/degraded_step_count=0/stages=六阶段 not_started——与 6-8 PlanningSection.total_steps 默认 8 口径分立注记（高管视图无阶段框架故保留 8 呈现总数；本 Story 总数语义由 stages 框架承载，空态 0 是「没有数据」诚实语义）** |
| `PhaseProgress` | 5 | phase_key: str / phase_name: str / status: PhaseStatus / step_completed: int / step_total: int |
| `TraceabilitySection` | 8 | available: bool（==stage_count>0） / degraded: bool / stage_count: int / chunk_count: int / document_count: int / jump_ready_count: int / degraded_stage_count: int / tree_build_degraded: bool（结论层恒单根节点不计入统计面——R1-F1） |
| `PhaseStatus` | 3 值 | COMPLETED="completed" / IN_PROGRESS="in_progress" / NOT_STARTED="not_started"（str-Enum——进度态语义域，与 ExecutiveHealth 健康分级域正交） |
| `BLM_SIX_PHASES` | 6 元组 | (performance_gap, 业绩差距分析) / (market_insight, 市场洞察) / (strategic_intent, 战略意图与目标) / (innovation_focus, 创新焦点) / (business_design, 业务设计) / (execution_design, 执行设计)——序 or.md L379 权威 |

构造守卫（`__post_init__` 抛 242）：plan_id 非空字符串；PhaseStatus 枚举成员校验（裸 str 拒绝）；计数 ≥0（total_tools/三计数/step_completed/step_total/五计数）；step_completed ≤ step_total（进度不变量——后四阶段 0≤0 恒真；step_completed 与 status 同源派生自同一 stage_steps 集合基数[set 去重——R1-F3]，计数天然有界于阶段值域基数，脏 timeline 重复形态结构不可触发，无需服务层钳制）。

#### Task 0.2 阶段派生规则表冻结

```python
def derive_stage_status(stage_steps: set[str]) -> PhaseStatus:
    """按 timeline step 集合判别阶段状态（确定性纯函数——AC-3 规则逐字）.

    Args:
        stage_steps: 该阶段归属的 timeline step 值集合（服务层按阶段归属过滤后传入）.
    """
    # 阶段1（performance_gap）：timeline 含 performance_gap 条目 → completed
    # 阶段2（market_insight）：含 market_insight_synthesis → completed（synthesis 优先序）；
    #   含任一六子裸值 → in_progress；否则 not_started
    # 阶段3~6：恒 not_started（step_total==0 规划态——V1 归 Epic 10-1，注记归 CLI 呈现）
```

（实现形态 dev-story 时按冻结规则落码；两规则+后四恒量的三分支结构与 AC-3 逐字对齐。）

#### Task 0.3 端口契约定义

- `AnalystViewPort`（应用层 `src/application/ports/analyst_view.py`，`@runtime_checkable Protocol` v1.0.0）：`async def build_analyst_view(self, *, plan_id: str) -> AnalystView`（keyword-only）
- 三依赖注册名（组合根既有——主会话亲验 HEAD@1a7aa345）：`skill_selector`（:3011 SINGLETON）/ `snapshot_repository`（:950 SCOPED）/ `traceability_tree_service`（:2021 SINGLETON）
- 组合根双注册：`analyst_view_service`（SINGLETON，tags=("analyst","view","application")）+ `analyst_view_use_case`（SINGLETON，tags=("analyst","use_case","application")）——落位 :2072-2100 executive_view 块之后
- 契约测试：`tests/contracts/test_port_contract_analyst_view.py`（五断言族）

#### Task 0.6 逐场景红锚符号表（12 场景预期形态）

| 场景 | 红阶段形态（Task 0.5 运行实测） |
|---|---|
| S1~S7/S10/S11 | 运行期 ImportError（`analyst_view` 模块缺失——预置/构建步骤延迟 import 抛出） |
| S8/S9 | CLI 未注册 → argparse invalid choice exit 2 → 断言步红（`cli_exit_code == 0` 断言失败） |
| S12 | Then 文件不存在 AssertionError（`_COMPLETION_SRC_FILES` 路径缺失） |

（**红锚演进注记——R3-F7**：红锚形态随实现 Task 落地演进——Task 1 后 S1~S7/S10/S11 的 ImportError 从 ports 模块迁至 services 模块→Task 2 后迁断言/注册红——属预期非做错信号；中途零意外绿推演：全场景依赖服务符号或注册名，部分绿仅出现在其依赖 Task 完成后；Task 1→2→3 串行（Task 2 断言需 Task 1 VO 符号）隐含于任务序，dev 按序执行。）

#### 12 验收场景钉死（S1~S12）

| 场景 | AC | 内容摘要 |
|---|---|---|
| S1 | AC-1 | 全数据三段 6 键 exact set+嵌套键集+值级（23 工具+进度+树统计） |
| S2 | AC-3 | 三 plan 形态六阶段派生（P-mid 进行中/P-full 完成/P-empty 框架恒在） |
| S3 | AC-2 | 工具箱真实清单（23+5 分类配比 3/3/6/3/8+全 slug 序==get_all_slugs() 直比[R1-F11 主锚——R2 补入]+首末 slug 序锚+和恒等式+len(categories)==5） |
| S4 | AC-4 | 溯源段统计（预置归档族+stage/chunk/document 三层计数+degraded_stage_count 计数+jump_ready True-False 混合判别+树顶层键透传——R1-F1 新键集） |
| S5 | AC-5 | 空 plan 幂等读（toolbox 恒 23+两段空态+框架恒在+build_degraded False） |
| S6 | AC-1 | ToolSummary 投影白名单（5 键 exact set+值非空+status=="active"+抽样值级锚） |
| S7 | AC-5 | 空 plan+畸形 plan_id 242（编程面 pytest.raises+分立声明） |
| S8 | AC-6 | CLI 全数据输出（三段分隔行+23 工具行+六阶段 6 行+V1 注记+溯源统计行「分析/切片/文档/可跳转」+提示行——双清直调——R2 补摘要） |
| S9 | AC-6 | CLI 空态输出（六阶段框架恒在+工具箱照常+exit 0）+242 stderr 形态 |
| S10 | AC-7 | 性能 20 轮 P95<800ms（服务面三读窗口） |
| S11 | AC-7 | 并发 20 路全成功+两两相等（排除集单键 {generated_at}——asdict 剔除对照） |
| S12 | 收尾 | src+四测试目录完成清单存在性断言 |

（epics L2451-2453 架构测试三项对账——R1 行号勘误：显示测试→S1/S3；快捷键测试→OD-7 前端指标口径差声明[Scenario 不设快捷键断言——docstring 声明承载]；快速溯源测试→S4+jump_ready 观测锚。）

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（L2434-2474+依赖行 L655/L2019）
- [x] 架构约束从 architecture.md/interface-design.md 提取（三视图表陈旧口径显式注记）
- [x] 前一个故事学习经验整合（6-8 五轮双审查收敛样板+6-7 归档预置+6-5a 并发）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（七 VO 键契约/派生规则表/12 场景/Task 0~7 共 8 Task）
- [x] 项目结构对齐统一规范（纯三零 Story+src 面 3 新建+2 扩展——R2-3 勘误）
- [x] 四 Agent 并行调研（工具箱数据面/BLM 进度+溯源数据面/CLI+组合根+R6 模板/治理面与词族）+ 主会话 14 组关键锚点亲验

### dev-story 实施完成注记 Dev Story Implementation Notes（2026-11-07）

**交付面**：七 VO（6/4/5/2/9/5/8 键）+ PhaseStatus 三值进度态枚举 + BLM_SIX_PHASES 六阶段静态清单 + PHASE_STEP_DOMAINS/PHASE_STEP_TOTALS 值域单源（ports 文件）+ AnalystViewService 三段编排（derive_stage_status 纯函数+段级容错+两层哨兵分立+单时间锚）+ GetAnalystViewUseCase 242 守卫透传 + CLI `analyst-view`（五步定式+三段打印+10 格进度条+V1 注记+降级双标记）+ 组合根双注册（两 SINGLETON+一 SCOPED 捕获声明）。

**TDD 全循环**：Task 1 VO（26 用例+2 变异）/Task 2 服务（35 用例+5 变异）/Task 3 用例+CLI+契约（6+12+6 用例+5 变异）/Task 5 集成（4 场景+2 变异）/Task 6 架构（13 用例+1 变异）——变异锚累计 15 处全实证（红→还原绿留痕）。

**实施攻坚五项**：
1. 六阶段值域单源上移 ports（`PHASE_STEP_DOMAINS`）——空态框架 step_total=[1,7,0,0,0,0] 恒在语义修正（「框架恒在」=阶段名+步数规划恒在，数据缺席仅影响 status/step_completed——服务与 VO 默认工厂共用单源禁双源漂移）
2. CLI 注册注释「--format」字样污染 6-8 既有 `test_no_optional_arguments` 的 getsource 块边界断言——改写注释措辞消解跨测试块边界耦合
3. 集成 collection 场景级生命周期——teardown 整删后每场景幂等 ensure 重建（模块级 fixture 建一次+场景①teardown 删掉的 404 冲突）
4. BDD 步骤文本重复绑定消解（「构建分析师视图」S1/S3 合并自足单函数——pytest-bdd 同文本单绑定约束）
5. 验收 S8 六阶段行过滤词缺陷（三阶段名→六阶段全名）+ R6 合规双文件按模板逐特征对齐

**质量门禁**：ruff 全绿+mypy 762 文件零错误（基线 759+3 新增）+三红线+抑制注释全部新增面零输出+验收 12/12 全绿+集成 4/4 全绿（P95<800ms 实测通过+并发 20 路排除集单键两两相等）+deferred-work 八条 11 处处置注记落档+CLI 真实冒烟（空 plan 幂等读输出与 AC-6 逐字一致；命中 D6-8-R1-1 已登记 .env 存量缺口——`set -a; . .env` 形态验证通过，非 6-9 引入）。

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-9-analyst-view.md`

**修改的文件/Modified Files:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 6-9 状态流转 backlog→ready-for-dev

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/analyst_view.py` - PhaseStatus 枚举+BLM_SIX_PHASES 常量+七 VO+AnalystViewPort ✅ 已交付
- `src/application/services/analyst_view_service.py` - 三段编排+derive_stage_status ✅ 已交付
- `src/application/use_cases/get_analyst_view.py` - 用例（UUID 守卫+透传） ✅ 已交付
- `src/entrypoints/agent_cli.py` - analyst-view 子命令（扩展） ✅ 已交付
- `src/composition_root.py` - 双注册块（扩展） ✅ 已交付
- `tests/unit/application/test_analyst_view_vos.py` - VO 单测 ✅ 已交付（26 用例）
- `tests/unit/application/test_analyst_view_service.py` - 服务单测（派生矩阵+容错矩阵） ✅ 已交付（35 用例）
- `tests/unit/application/use_cases/test_analyst_view_use_case.py` - 用例单测 ✅ 已交付（6 用例——代码审查 R1-F7 勘误：原记 7 实测 6）
- `tests/unit/interfaces/cli/test_agent_cli.py` - CLI 单测（扩展） ✅ 已交付（+12 用例——工厂/stub/patcher 三件套+Parser 3+Execution 9）
- `tests/unit/architecture/test_analyst_view.py` - 架构验证（四验证器） ✅ 已交付（13 用例）
- `tests/integration/test_integration_analyst_view.py` - 集成测试（四场景） ✅ 已交付（4 场景）
- `tests/contracts/test_port_contract_analyst_view.py` - 端口契约测试（五断言族） ✅ 已交付（6 用例）
- `tests/acceptance/test_acceptance_analyst_view.feature` - Gherkin 场景（12 场景——R6 模板） ✅ 已交付
- `tests/acceptance/test_acceptance_analyst_view.py` - BDD 步骤实现（6-8 R6 合规形态） ✅ 已交付（12 场景全绑定）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 八条锚定义务处置注记（扩展） ✅ 已落档（11 处追加）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.9 |
| **Story Key** | 6-9-analyst-view |
| **File** | `_bmad-output/implementation-artifacts/stories/6-9-analyst-view.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力 / UX 三页面驾驶舱（分析师） |
| **优先级** | P1-9（依赖 Story 6.1/6.7——epics L2019 钦定，两依赖均 done） |
| **覆盖 FR** | 无独立 FR（聚合展示面——同 6-6/6-7/6-8 形态；FR-ST-01 归 Epic 4 Story 4.1 已交付、FR-UI-23/FR-UI-13/FR-IF-05 归 Epic 21/22） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7 含 TDD 循环+变异锚）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7+12 场景钉死）
3. [x] Architecture constraints extracted 架构约束已提取（纯三零 Story+依赖方向矩阵）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（8 学习点+7 应用项）
5. [x] Sprint status synced to `ready-for-dev`
6. [x] OD-1~OD-13 十三裁定落档（范围收窄/零事件/零异常/键契约+投影白名单/六阶段静态清单/溯源段口径/性能三段/锚定义务八条/命名/工具箱口径/组合根/纯三零/progress 口径分立）
7. [x] deferred-work 八条锚定义务处置预案落档（Task 0.7——六条 Epic 6 锚+两条 6.7-DF 维持+两条 D6-8-R 维持——R1-F8 口径统一）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-F1 | TraceabilitySection `conclusion_count` 锚错层：`len(tree.root.children)` 实为分析层（root 即唯一 ConclusionNode 单节点，空树同构造）——恒 1 与 available==False 矛盾/与 stage_count 重复键/CLI「结论: 7」误导三方矛盾（16 处传播/9 个节位：范围表/AC-1/AC-4/AC-6/OD-4/OD-6/Task 0.1 冻结表/Task 2/S4——R2 口径注：处数=出现位计数、节名=承载区） | P0 | conclusion_count→**chunk_count**（补齐切片层计数，8 键不变）+available 重锚 **stage_count>0**+CLI 统计行改「分析/切片/文档/可跳转」+结论层单根节点统计面注记（对标 CQRS 读模型「剔除恒定值」惯例） |
| R1-F2 | ToolMetadata 字段枚举失实：漏 `when_not_to_use`、`token_budget` 实为 `token_budget_l1/l2` 两字段、「12+ 字段面」实 18 字段（AC-1/OD-4/Lessons/锚表 4 处） | P1 | 统一「18 字段/白名单外 13 字段」全枚举口径（4 处传播位） |
| R1-F3 | step_completed「条目数」口径与 Task 0.2 `set[str]` 签名分叉：record_step 纯 append 无幂等防护（:117 亲验），重复条目下条目数>step_total 触发 VO 守卫 242 崩溃违反 AC-5 不抛承诺；「服务层钳制」规则未定义 | P1 | 钦定**集合去重单源派生**：step_completed==len(stage_steps) 与 status 共用同一集合（AC-3/Task 2 绿/守卫句 3 处+派生矩阵补重复条目判别格） |
| R1-F4 | 6-8 `_STEP_SEQUENCE`（`market_insight_trend` 前缀形态且子步名 strategy/org/risk/execution 不符 `MarketInsightStep` 值域）是计数面专用非 canonical 值——6-9 是首个 timeline step 值消费者，直系复刻必红（S2 恒红/诱导腐蚀派生规则） | P1 | 预置值形态禁复刻警告+6-9 专属裸值序列常量（写侧三形态实证 blm_planning_service :309/:414/:504）落 Task 0.5+锚表+派生矩阵值域外脏值格 |
| R1-F5 | AC-4 验证标准「AsyncMock 抛异常→tree_build_degraded 透传断言」测试不可满足：抛异常走段级容错（tree_build_degraded==False 段降级默认值）；透传需 Mock 正常返回 build_degraded=True 的树（6-7 服务内降级形态 :186-192 亲验） | P1 | 两条单测分立（①正常返回降级树→透传+段不降级；②抛异常→段降级+默认值）——AC-4 正文/验证标准/Task 2 循环 C 三处 |
| R1-F6 | state_data 畸形逐键处置未冻结（completed_steps 缺 vs total_steps 缺矛盾悬空）；total_steps==0 除零路径未钦定 | P2 | 复刻 6-8 `executive_view_service.py:169-188` 逐键处置表+progress_percent 除零守卫归 0（AC-5/AC-1/Task 2 循环 C） |
| R1-F7 | 「add_parser 16 命令族」实测 **15**（OD-9/亲验清单 2 处+sprint-status 注记） | P2 | 改「15 命令族（本 Story 落地后 16）」3 处 |
| R1-F8 | 锚定义务八条计数三口径打架：OD-8 枚举漏 D6-8-R1/R2 组与「八条」表行数不符（OD-8/Subtask 0.7/完成总结 3 处） | P2 | OD-8 补 D6-8 维持处置+三处口径统一「六 Epic6 锚+两 6.7-DF+两 D6-8-R」 |
| R1-F9 | 行号/归属勘误批：epics L550→**L541**（FR-UI-13 行）/L2450-2452→**L2451-2453**/interface-design :2005→**:2006**/deferred-work L394→**L395**/selector :37→**:35**/CLI 单测 :3215-3222 归属越界（agent_cli.py 仅 2218 行） | P2 | 逐处勘误（7 处）+`_ensure_bootstrapped` 下划线前缀（Task 3） |
| R1-F10 | skill_selector「既有消费方仅 LoadAgentProfileUseCase」缺生产码限定（tests 侧另有夹具/直调消费） | P2 | 两处加「生产码」限定+tests 消费注记 |
| R1-F11 | 断言判别力补强：首末 slug 锚中段乱序不红/categories 缺第六类防护/k 表无枚举锚 | P3 | 全序列 `==get_all_slugs()` 断言+len(categories)==5+k 表 [0,1,3,4,6,7,9,10] 枚举变异锚 |
| R1-F12 | 措辞级批：phase 空态 None 注记/树顶层 7 键补全（plan_id/root）/OD-12「2 扩展」勘误/词族枚举放宽/SkillNotFoundError=387 补锚/ToolCategory 10 成员注记/追溯矩阵粒度注记 | P3 | 7 处就地修正 |
| 证伪 | 调研 A4 报「prd『前两阶段覆盖 80%』在 L453」——主会话 grep 定谳 **L454 现状正确**（B1 同判），Story 不改 | — | 证伪留痕（审查员事实冲突主会话实测定谳——记忆纪律） |

**Round 1 审查形态**：四视角并行调研（工具箱数据面/BLM 进度+溯源面/CLI+组合根+模板/治理面）+双视角并行审查（正确性+一致性/科学性+可行性）+主会话亲验 5 组关键争议（树结构/ToolMetadata 字段/record_step 幂等/prd L454/_STEP_SEQUENCE）；P0×1+P1×4+P2×5+P3×2+证伪×1。

### Round 2 修复（回归核查+组合交互面——双 Agent 并行）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-1 | OD-5 行内「阶段2=六子裸值+synthesis 条目数」——R1-F3 集合口径漏传播位（全文唯一「条目数」旧语义存活位，OD 是落码决策依据面） | P2 | 改「集合基数——去重口径」（:552） |
| R2-2 | Task 0 目的行「六条 Epic 6 锚+两条 6.7-DF」——R1-F8 口径统一漏传播位（6+2=8 旧口径第四处残留） | P2 | 补「+两条 D6-8-R 维持」（:325） |
| R2-3 | OD-12 headline「改动面=4 新建+2 扩展」与括注算术矛盾（src 实为 3 新建+2 扩展）——三处同口径（OD-12/完成清单/v1.0.0 版本注） | P2 | 统一「src 面 3 新建+2 扩展」（:559/:774/:884 内联勘误） |
| R2-4 | R1-F11 全序列断言未达承载面：AC-2 验证标准 checkbox 与 S3 摘要均只列首末锚——中段乱序判别主锚悬空 | P2 | 全序列断言补入 :69 验证标准+S3 :754 摘要 |
| R2-5 | k 表枚举与 ±1 变异锚无 Task 承载位（Task 3 循环 B 红格与 Subtask 3.4 均无 k 表）+归属文件未点名 | P2 | 补入 :428 红格（k 表逐格断言+`_print_analyst_view` 归属）+:435 第四变异锚 |
| R2-6 | R1-F6 逐键处置表漏 phase/current_step 两键——6-8 :188 实码实证含 current_step `.get` 处置，phase 处置悬空（两文本三处同漏） | P2 | 两处处置表同步补「phase、current_step `.get` 缺→None（空态同形——6-8 :188 先例；不触发段降级）」（:120/:394） |
| R2-7 | AC-6 溯源段空态行形态未钉死——S9 断言不可精确落笔（progress 与 traceability 空态钦定不对称） | P2 | 钉死「统计行恒在全 0 形态+提示行恒在（降级行/树降级标记缺席）」（:136）+:142 断言补 |
| R2-8 | chunk_count 实例计数口径未注记（跨 stage 重复引用）+AC-4 Given「≥1 切片」与混合判别联合不可满足（每 chunk 至多 1 文档节点——`_resolve_document` 单 payload 实码亲验） | P3 | :49 补实例计数注记+Given 改「≥2 切片实例（预置使 chunk_count≠stage_count 判别计数面错接）」+:105 补直推断言 |
| R2-9 | degraded_stage_count 在 Task 2 循环 A 与 S4 摘要枚举缺失（两处逐键点名其余键独漏此键） | P3 | 两处补全枚举 |
| R2-10 | 「快照计数 vs 派生计数」分立注记缺失——脏值格两断言并存（直读 8/8 vs 六阶段全 not_started）易误判 bug | P3 | :90 补分立注记+derive_stage_status 单集合签名可满足性论证（三阶段值域两两不相交） |
| R2-11 | 「六子序列常量」命名误读（实为 8 元组全序列）/S8 摘要漏溯源统计行/修复表 F1「16 传播位」双计数口径混排/AC-1 与 AC-4 五计数承载分工 | P3 | 四处就地修正（:331/:759/:832/:54） |

**Round 2 审查形态**：回归核查（R1 十二项修复台账 vs 实际改动对账——9 项完全一致/2 项清单外漏传播位/1 项连带新计数矛盾，零「声称 N 实改 N-k」执行缺口）+组合交互面（键契约六面走查/派生规则组合/断言组合判别力/R1×未修复面残留）+主会话亲验 1 组（`_resolve_document` 每 chunk ≤1 文档节点）；净新增 11 项（P2×7+P3×4），无 P0/P1——R1 修复主体组合自洽。

### Round 3 修复（单深度推演——长状态时间线/判别力穷举/Task 干跑/数理终扫）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-F1 | CLI 双降级标记 present 形态无断言承载位——AC-6 VC 三断言形态均不触发 present、Task 3 红格与变异锚四项均无标记项，实现漏掉 append 逻辑将全绿 | P2 | Task 3 循环 B 补降级标记双形态格（stub 直构降级 VO——build_degraded+tree_build_degraded 双标记并存断言）+Subtask 3.4 第五变异锚（append 删除→红） |
| R3-F2 | ProgressSection 空态/段降级默认值未冻结——「计数降 0」与「复刻 6-8 :169-188」在 total_steps 上分叉（6-8 默认 8），三处口径两可 0/8 两实现均绿 | P2 | Task 0.1 冻结表钦定空态/段降级默认值（total_steps=0+与 6-8 默认 8 分立注记——本 Story 总数语义由 stages 框架承载）+AC-5 括注 |
| R3-F3 | phase_name 中文值级断言承载位不明（Task 1 红格「六元组序精确断言」匹配单位歧义） | P3 | 明示 (phase_key, phase_name) 对逐对全量精确匹配（中文逐字） |
| R3-F4 | chunk_count≠stage_count 判别构造「建议」措辞约束力不足+集成场景①未落实（镜像错接不红） | P3 | 「建议」→「钦定」+场景①补 2 stage×3 chunk 形态 |
| R3-F5 | CLI 进度行 current_step=None 形态未定义（会打印「当前: None」） | P3 | None→『无』fallback（6-8 :1519 直系） |
| R3-F6 | 「快照直读 vs 派生计数」CLI 呈现层语义注记缺失（3/8 与阶段合计 2/8 并存的 apparent 矛盾） | P3 | 呈现语义注记+docstring 义务落 Task 3 重构格 |
| R3-F7 | Task 1~3 中间态红锚演进无注记（红形态变化易被误读为做错）+串行依赖隐含未明示 | P3 | 红锚符号表后补演进注记（零意外绿推演+Task 1→2→3 串行） |

**Round 3 审查形态**：单 Agent 深度推演（六条长状态时间线逐字段终态/断言判别力穷举/Task 0→7 依赖干跑/边界数理终扫——全部以实码亲验为底座）；零 P0/P1+P2×2+P3×5+证伪留痕 7 条（重复条目可达性实证/并发窗口改写三重排除/asdict 排除集数理成立/提交批次对齐先例/phase 快照恒 market_insight/k 表无 tie/配比复核提示——勿用裸 grep 复核配比，capabilities 列含同类子串会过计）。R1/R2 修复主体在逐字段推演下全部成立且与实码一致——收敛趋势延续。

### Round 4~5 纯验证+独立终审（收敛定稿）

> **文档审查周期收敛声明（Round 5 独立终审——新鲜上下文独立取证，v1.3.1 定稿）**
>
> Story 6-9 文档审查修订循环五轮收敛：**R1** 四视角并行调研+双视角审查（P0×1+P1×4+P2×5+P3×2+证伪×1，13 项修复）→ **R2** 回归核查+组合交互面双 Agent（P2×7+P3×4，11 项修复）→ **R3** 单深度推演（P2×2+P3×5，7 项修复+证伪留痕 7 条）→ **R4** 纯验证三轴（词根终扫零残留/锚点存续 12/12/结构完整——零发现无提交）→ **R5** 独立终审五节全过。周期累计 **31 项修复+证伪留痕 8 条**；严重度递减链：P0 1→0→0→0、P1 4→0→0→0、P2 5→7→2→0——R2 起 P0/P1 双零，R4 起零新发现。提交链恰 3 笔（a1983852 v1.1.0/394ccefc v1.2.0/0c588697 v1.3.0）全部仅触 story+sprint-status 两文件、零 AI 署名、零游离提交。
>
> R5 五节取证结论：①**周期闭合通过**；②**10 项关键修复双向取证 10/10 全属实**（ToolMetadata 18 字段/root: ConclusionNode 单根/record_step 纯 append/_ensure_bootstrapped 下划线 4 组代码现实亲验吻合；写侧三形态 :309/:414/:504、6-8 :188 current_step 处置、`_resolve_document` 每 chunk ≤1 文档节点等实锚逐行验证）；③**独立快扫通过**——八词根残留活位全零（conclusion_count/条目数/token_budget 裸词/ensure_bootstrapped 无下划线/16 命令/L2450-2452/:2005/建议使）+9 章节结构齐备+九组数值全文一致+15 组附加实锚吻合（add_parser=15/get_all_slugs=23/_FROZEN_EVENT_COUNT=56/组合根四注册行/BlmPhase 2 值+扩展锚/SkillNotFoundError=387/loader 8 raise/redis 吞异常/epics 各行原文）；④**红线零违**（抑制注释仅禁止项形态、四目录命令/xdist 组/BDD 禁 asyncio/集成禁 delete 等纪律表述与项目规则一致）。
>
> **收敛判据达成：零 P0/P1/P2 残留+独立取证通过——文档定稿 v1.3.1，放行进入 dev-story。**

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-11-07（Round 1）
**审查模式:** full（四视角并行调研：契约一致性/测试质量判别力/架构合规红线/运行面实测 + 双评审员 C3 门禁[正确性最小性/科学性一致性] + 主会话亲验三组关键事实）

**Round 1 审查形态**：四路调研均「基于亲读代码行/实测命令」——契约面五轴全过（七 VO 键契约/派生规则/三段编排/组合根/CLI 逐字格式忠实度极高）+5 组真实突变全红（判别力实证）+运行面 15 项实测零 P0/P1/P2（AC-6 空态逐字一致/幂等 byte-identical/P95=15.5ms 余量 51 倍/验收 12/12 零 skip）。C3 双评审员裁定「良好→并档修正清单后放行」：评审①证伪 F5 原拟修法（`not in lines` list 全等负断言仍恒真——死断言换死法）+裁定 F1 提交信息禁用未证实措辞；评审②独立定谳 F6 缓存面已被既有 fixture 闭合+F7 第三处（:530）——修正清单 7 条全部并档后落码。主会话亲验：写侧 timeline 裸值形态（blm_planning_service :309/:414/:414 落点——排除 STAGE_VALUE_DOMAIN 前缀形态误判 P0）、`_fresh_resolver_per_test` 既有防线、F7 第三处漏报补全。

#### 需决策 Decision Needed

- 无（Round 1 全部发现已裁定处置——见 Patch/Defer/未落码注记）

#### 已修复 Patch

| # | 问题 | 严重度 | 修复方案 |
|---|---|---|---|
| R1-F1 | docker-compose.yml +8 行游离变更（两处 qdrant ulimits nofile 65535——Story File List 零记录/全文 grep 零命中/与 6-9 零技术因果；Task 7.4 纯三零取证范围仅限 src 三目录，掩盖 deploy 面游离变更——三方汇合[调研 A+C+主会话]定谳） | P1 | 剥离独立提交 `b7f2235e build(deploy): qdrant 服务补充 ulimits nofile 65535 文件描述符上限加固`（评审①约束：措辞用运维加固——「qdrant 官方建议」现行官方文档未证实禁用；e1d5a066/c7ed56bb 独立 build(deploy) 先例）；6-9 提交面与 File List 对齐 |
| R1-F2 | `analyst_view_service.py` ruff format --check 失败（:207-213 set 推导式多行——全仓 1826 文件唯一违例；pre-commit ruff-format 钩子会改写文件中断首次提交） | P2 | 单文件 format 压行（123 字符<128 行宽合法，零行为变化；format 后 35 服务用例全绿复验） |
| R1-F3 | `_TOOL_SUMMARY_FIELDS` 死常量（service :59-61 定义全仓零消费——Subtask 2.3「投影白名单五键常量化」名义落地：构造面 :145-152 硬编码五 kwargs 未从常量派生；ToolSummary 字段定义即白名单 SSOT，常量是无守护第二源镜像——4-1f「第 N 源漏扩」教训形态） | P3 | 删除常量+构造点行内注释承载白名单（对齐 6-8 executive_view_service :241-244 注释+硬编码 kwargs 先例形态）；Subtask 2.3 行内勘误注记（评审②裁定推翻冻结项的正确形态=修复表登记+行内注记）；评审②否决「测试守护等集断言」备选（为无人消费的源加守护是仪式） |
| R1-F4 | 架构测试 test_use_case_import_direction 尾行恒真断言（:178 相对 :177 白名单断言恒真——or 右支死分支[以 src.domain. 开头的名字不可能以 src.interfaces./src.infrastructure. 开头]）+:43 `_FORBIDDEN_LAYER_PREFIXES` 孤儿常量（唯一消费方即 :178） | P3 | 删两处（判别力全在 :177 白名单断言——`import src.infrastructure.x` 仍红[前缀互斥性亲证]；6-8 样板无此行属超模板自加，回归样板平价；删后 13 用例全绿复验） |
| R1-F5 | CLI 单测 test_empty_plan_output 尾断言 capsys 双读恒真（:3583 `lines = capsys.readouterr().out.splitlines()` 已消费缓冲，:3590 二次 `readouterr().out` 读新空缓冲→`not in ""` 恒真——「降级 stage 行缺席」VC 半腿失活，AC-6 R2 钉死项无承载；全仓无其他活守护） | P1 | 改 `assert not any("降级 stage:" in line for line in lines)` 子串扫描（评审①实测证伪原拟 `not in lines`——list 成员是全等比较非子串，`'a:' in ['a: 0']`→False，死断言换死法；any 形态对任意「降级 stage: {n}」值均红）；**突变实证留痕**：临时去 agent_cli :1696 `if degraded_stage_count > 0` 守卫→test_empty_plan_output 红（断言复活）→还原守卫→全绿 |
| R1-F6 | 集成测试 setenv worker 级环境泄漏（:141 `os.environ["BLM_SEARCH_COLLECTION"] = _COLLECTION` 直写不恢复——组合根 lambda 在 resolve 时刻读 env[composition_root :1592/:2038]，teardown 删 collection 后同 xdist worker 后续模块[6-2/6-4 planning 族同组]resolve 链读残留 env 指向已删 collection 毒化 404；伴生注释「集成面无 monkeypatch」是泄漏自我合理化——验收面 :708/:727 monkeypatch.setenv 先例在案） | P2 | setenv 折入既有 `_fresh_resolver_per_test` autouse fixture（fixture 加 monkeypatch 参数+1 行 setenv——per-test 注入+测试退出自动恢复 env，与后置双清同点原子收尾[评审①形态 c：3 触点最小，优于 9 触点参数化形态]）；删 `_build_service` 内 os.environ 行+clear_singleton 冗余行+`import os`+注释改写（评审①②独立定谳：缓存面已被既有 autouse fixture 每测试双清闭合，方案原拟「新增模块级 teardown」为冗余防线违反 Simplicity First——已裁撤）；集成 4 场景真实服务复验全绿 |
| R1-F7 | 用例单测计数失实三处（「7 用例」——:530 Task 7.4 收尾实录「26 VO+35 服务+7 用例…」/:785 TDD 全循环「7+12+6」/:812 File List；`--collect-only` 实测 6 个测试函数；调研 B 报两处漏 :530——主会话亲验补全[「同源锚点全出现位」纪律]） | P2 | 三处勘误 7→6（其余计数逐一复核全对：VO 26/服务 35/CLI 12/架构 13/契约 6/验收 12/集成 4） |
| R1-F8 | CLI 单测 :3557 运算符优先级脆弱写法（`"[" in line and "█" in line or "[" in line and "░" in line`——and 先于 or 当前语义正确，无括号纯可读性脆弱） | P3 | 括号化（零行为变化，6-9 新增面自有代码） |

**Round 1 落码后回归**：服务 35+架构 13（48 passed）/CLI 172 passed/集成 4 场景（SISYS_USE_TEST_PORTS=1 真实服务）全绿；ruff format --check 归零。

#### 已推迟 Defer

- **D6-9-R1-1 [P3]**：CLI `*--plan-id` 命令族非 canonical UUID 形态静默落空态（大写/URN/无连字符全过 `uuid.UUID` 宽松守卫，原始串键拼接 miss 写侧恒小写 → 幂等空态 exit 0——运行面实测证；6-8 executive-view 同款守卫直系非 6-9 引入，「非 UUID→242」契约已兑现、canonical 归一属未定义面）——已登记 deferred-work【6.9-R1-DF1·P3】（触发：CLI 输入标准化专项 或 7-2 REST 输入契约立项；归宿：命令族统一治理）

#### 未落码注记（维持项台账——评审裁定不修留痕）

- 变异留痕形态：15 变异锚仅存 Story 叙事复选框（测试文件零 in-file 留痕注释）——与 6-8 先例一致维持；本轮调研 B 独立 5 组真实突变（/tmp 拷贝注入）全红佐证锚实质可信
- vos:358 `_make_stage(step_completed=0, step_total=0).status is COMPLETED` 工厂默认同源断言——零成本留（评审②裁定）
- service:437 `len(stage_steps)==7` 断言——**非纯同源**：synthesis 单独在场即 COMPLETED 的「全量格」判别前提唯一守护，必须留
- service:443 set 字面量去重断言——真去重锚在服务级格 11（突变可红），此处弱锚留档
- arch:66 路径常量断言——弱守护（is_file 是真锚），零成本留
- 派生矩阵三空集格同调用（格 2/5/7 均 `derive_stage_status(set())`）——单集合签名纯函数层无法判别阶段维（三阶段值域两两不相交依据），阶段维由服务层 `_derive_stages` 测试承载——矩阵覆盖声明按此口径理解，冗余非缺陷
- progress_percent 脏快照 >100 无读侧钳制——6-8 executive_view_service :187 同款忠实复刻（R1-F6 复刻钦定），两 Story 共享形态，如修属 6-8 联动面非 6-9 单独面

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行文档审查修订循环（参照 6-6/6-7/6-8 五轮形态——R1 四视角调研+双审查/R2 回归+组合/R3 单深度/R4 纯验证/R5 独立终审五节全过，31 项修复+证伪 8 条，零 P0/P1/P2 残留，v1.3.1 定稿收敛）
- [x] 运行 `dev-story` 开始实施（2026-11-07 完成——Task 0~7 全 Subtask 勾选：12/12 验收场景全绿+四目录全量两轮 15193/15192 passed[3 例既有环境负载偶发单独复跑全绿定调，与 6-9 零交集]+覆盖率 93%[新增三 src 文件 100%]+mypy 762 零错误+ruff 全绿+变异实证 15 锚；交付面：七 VO+PhaseStatus+六阶段静态清单+值域单源+三段编排服务+242 用例+CLI analyst-view[五步定式+三段打印+进度条]+组合根双注册；实施攻坚五项+CLI 真实冒烟通过）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-11-07
**最后更新/Last Updated:** 2026-11-07
**更新说明/Description:**
- v1.5.0: 代码审查 Round 1 修订（四视角并行调研[契约一致性/测试判别力/架构红线/运行面实测]+双评审员 C3 门禁+主会话亲验三组：P1×2[docker-compose +8 行游离变更剥离独立提交 b7f2235e/CLI 单测 capsys 双读恒真断言——评审①证伪原拟 not-in-list 形态改 not any 子串扫描+突变实证留痕]+P2×3[ruff format 压行/集成 setenv worker 级泄漏——折入既有 _fresh_resolver_per_test fixture 形态 c 三触点/用例计数 7→6 三处勘误含主会话补全 :530]+P3×3[_TOOL_SUMMARY_FIELDS 死常量删除——SSOT 第二源清除+Subtask 2.3 行内勘误/架构测试恒真断言+孤儿常量删除/运算符括号化]——落码 8+deferred 登记 1[D6-9-R1-1 非 canonical UUID 命令族观察项]+未落码注记 7 条台账；契约面五轴全过+5 组真实突变全红+运行面 15 项实测零缺陷[P95=15.5ms/幂等 byte-identical]；落码后回归 48+172+4 全绿）
- v1.4.0: dev-story 实施完成 ready-for-dev→in-progress→review（Task 0~7 全 Subtask 勾选：12/12 验收场景全绿+四目录全量两轮 15193/15192 passed[3 例既有环境负载偶发单独复跑全绿定谳，与 6-9 零交集]+覆盖率 93%[新增三 src 文件 100%]+mypy 762 零错误+ruff 全绿+变异实证 15 锚；交付面：七 VO+PhaseStatus+六阶段静态清单+值域单源+三段编排服务+242 用例+CLI analyst-view+组合根双注册；实施攻坚五项+R6 合规双文件+deferred-work 八条 11 处处置落档+纯三零 diff 实证+CLI 真实冒烟）
- v1.3.1: 文档审查周期收敛定稿（R4 纯验证三轴零发现+R5 独立终审五节全过——周期闭合/10 项关键修复双向取证 10/10+代码组 4/4/八词根残留活位全零+15 组实锚吻合/红线零违；收敛判据达成：零 P0/P1/P2 残留——放行 dev-story；收敛声明入档）
- v1.3.0: 文档审查 Round 3 修订（单深度推演：六条长状态时间线逐字段终态/断言判别力穷举/Task 0→7 依赖干跑/边界数理终扫——零 P0/P1+P2×2+P3×5+证伪×7；R1/R2 修复主体逐字段推演全部成立与实码一致：P2[CLI 双降级标记补断言承载位——Task 3 红格+第五变异锚/ProgressSection 空态默认值冻结——total_steps=0 与 6-8 默认 8 分立注记]+P3[phase_name 逐对全量精确匹配明示/chunk≠stage 钦定+集成场景①落实/current_step None fallback/呈现语义注记+docstring 义务/红锚演进注记+串行依赖]）
- v1.2.0: 文档审查 Round 2 修订（回归核查+组合交互面双 Agent+主会话亲验 `_resolve_document` 基数：净新增 11 项 P2×7+P3×4 无 P0/P1——R1 修复主体组合自洽：R1-F3/F8 各漏传播 1 位[OD-5 条目数残留/Task 0 目的]/OD-12 headline 计数矛盾三处/R1-F11 全序列断言+k 表枚举补承载位[AC-2 VC+S3/Task 3 红格+变异锚]/逐键处置补 phase·current_step[6-8 :188 实码含 current_step 处置]/溯源段空态行形态钉死/chunk_count 实例口径+Given ≥2 切片[每 chunk 至多 1 文档节点实码亲验——混合判别联合不可满足消解]/degraded_stage_count 补全枚举/快照 vs 派生计数分立注记+值域互斥论证/措辞批 4 处）
- v1.1.0: 文档审查 Round 1 修订（四视角调研+双视角审查+主会话亲验 5 组争议：P0×1[TraceabilitySection conclusion_count 锚错层→chunk_count 替换+available 重锚 stage_count>0——对标 CQRS 剔除恒定值惯例，16 传播位]+P1×4[ToolMetadata 18 字段勘误/step_completed 集合去重单源钦定——record_step 无幂等防护亲验/6-8 _STEP_SEQUENCE 前缀形态禁复刻——本 Story 首个 timeline step 值消费者/AC-4 树顶层降级两条单测分立——测试不可满足性消解]+P2×5[state_data 逐键处置表+除零守卫/16→15 命令族/锚定义务八条口径统一/行号勘误 7 处/消费方生产码限定]+P3×2[断言判别力补强：slug 全序列+len(categories)==5+k 表枚举锚/措辞级 7 处]+证伪×1[prd L454 现状正确——调研误报留痕]）
- v1.0.0: 创建故事文件（四 Agent 并行调研【工具箱数据面/BLM 进度+溯源数据面/CLI+组合根+R6 模板/治理面与词族】+主会话亲验 14 组关键锚点；OD-1~OD-13 十三裁定：范围收窄 CLI-only 第八连（UX 三页面驾驶舱 Web 面归 Epic 21/22——快捷键 21.9/批量操作 22.1/角色自适应 22.8，本 Story 后端聚合口径+CLI 呈现）/零新增事件（查询型第八连+_FROZEN_EVENT_COUNT=56 零变化）/零新增异常（242 复用+SkillNotFoundError 消费不新增+480 语义分立第三连）/七 VO+PhaseStatus 三值枚举（6/4/5/2/9/5/8 键契约+投影白名单五键+两层哨兵分立）/六阶段静态清单应用层常量（BlmPhase 扩展锚归 Epic 10-1 钦定零 domain 改动+派生规则纯函数）/溯源段 depth=4 全树统计（jump_ready 观测锚+树顶层哨兵透传）/性能三段口径（P95<800ms 服务面+并发 20 排除集单键最小化+快捷键/溯源跳转口径差声明）/锚定义务八条处置（L13 不触发/L17 第六轮/L107 甄别声明/L117 顺延 Epic 8/L127 不触发/L129 第四轮/6.7-DF1·DF2 维持 Epic 21-22/D6-8-R1·R2 维持）/命名 analyst_view 词族（integration 前缀对 epics 钦定名显式偏离）/工具箱口径 SkillSelectorPort 消费（ACTIVE 清单+23 事实断言+配比 3/3/6/3/8 恒等式）/组合根双注册+三既有依赖复用（两 SINGLETON+一 SCOPED 捕获声明）/纯三零 Story（零 domain+零 migration+零 infra——比 6-8 准三零更纯，src 面 3 新建+2 扩展[R2-3 勘误：创建期误写「4 新建+2 扩展」]）/progress 与 6-8 planning 口径分立（阶段级全景 vs 步级摘要——两视图正交）；12 验收场景钉死（S1~S12——epics 架构测试三项对账：显示→S1/S3、快捷键→口径差声明、溯源→S4+jump_ready）；deferred-work 八条处置预案落档）
