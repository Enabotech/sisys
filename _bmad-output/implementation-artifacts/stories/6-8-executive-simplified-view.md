# Story 6-8: 高管简化视图（四段聚合查询——规划态势/审批中心/审计摘要/报告可得性 + RAG 三色健康状态 + CLI `executive-view`）

**Status:** `ready-for-dev`（R1 修订——6-7 R2-4 三口径复发清扫）

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行文档审查修订循环（参照 6-6/6-7 五轮形态）+ 人工按 story-template 合规清单核对后再执行 `dev-story`（`validate-create-story` 系上游模板措辞，本仓无该名 skill）。

---

## 📖 Story 描述

**As a** CEO（高管）,
**I want** 系统按 plan_id 输出高管简化视图——单命令聚合规划态势（进度/降级/最近活动）、审批中心（Checkpoint 完成与同步分布+最近恢复留痕）、审计摘要（时间窗事件总量+最近动态）与报告可得性（最新报告标识与降级计数）四段，并给出红/黄/绿三色健康状态（RAG——green=健康/amber=关注/red=危险）,
**So that** 快速理解态势并做出决策——不读全文报告即可在 30 秒内掌握「规划走到哪、可信度如何、待办审批什么、合规面有无异常」（epics L2397 用户价值；prd L121 高管价值主张「30 秒理解战略态势」）。

### 业务价值

- **Epic 6 价值组「战略规划与审批能力」的高管收口面**：生成侧（6-1~6-5b）与审批侧（6-6）、溯源面（6-7）已 done，本 Story 交付 **P0-8 高管一屏速览面**——前序七 Story 交付物的单点聚合投影（epics L2018 依赖列钦定「依赖 Story 6.5a」不含 6-5b/6-7）
- **范围权威收窄（epics L2391-2393 取代注记钦定）**：原「3 个关键指标」仪表盘 UI **已被 Epic 21 Story 21.1 决策舱总览仪表盘（KPI 10 项+风险雷达+BG 健康矩阵）取代**，本 Story 保留作为 **MVP 最简版本的 fallback 参考**——Web/前端面归 Epic 21，本 Story 交付其**后端聚合口径与 CLI 呈现**（Epic 6 第七个 CLI-only Story——6.1-DF5 六连先例延续；epics L4023「Epic 21 Story 21.1（KPI 数据源）」供给注记的本 Story 侧兑现）
- **FR Coverage Map 无独立 FR（同 6-6/6-7 形态）**：FR-UI-04（决策舱总览仪表盘）映射 Epic 21 Story 21.1（epics L476）；FR-UI-11（多格式报告）已由 6-5a/6-5b 交付——本 Story 是既有能力的**聚合展示面**（查询型故事先例族第七连）
- **激活一个零消费方查询面**：`ReportRepositoryProtocol.get_latest_by_plan`（`src/domain/ports/report_repository.py:38`）已实现但 src 内零生产消费方（主会话亲验 grep）——本 Story 是其**首个消费方**（6-6 `checkpoint-show` 首消费 `RecoverCheckpointUseCase` 零消费方同款钦定先例）
- **清偿/处置 deferred-work 六条留项**（Task 0.7 逐条落档——**四条 6-8 锚定+两条例行顺延**，R1 口径统一）：6.5a-DF1（REST 导出面——顺延 Epic 7）/6.5a-DF2（L0 撕裂——触发条件不变顺延）/6.7-DF2（bbox 四元组——重锚 Epic 21/22 Web 面）/L129 data_pipeline 轨（维持注记）+L170 事件消费基建/L17 langgraph retry 两条例行顺延
- Epic 6 内部顺序：6-7（done，溯源面）→ **6-8（本 Story，高管速览面）** → 6-9 分析师视图（backlog——UX 三页面驾驶舱 P1 面，与本 Story 无依赖）

### 范围边界（出处逐行声明）

| 面（出处） | 已交付（禁重复造轮） | 6-8 增量（本 Story） |
|---|---|---|
| 规划进度数据面（6-1/6-2） | latest 快照 `blm-planning-{plan_id}`（state_data 七键：plan_id/phase/current_step/completed_steps/total_steps/degraded_steps/timeline——端口 SSOT `blm_planning.py:9-15`）；`BlmPlanningStatus.progress_percent` property（`blm_phases.py:173-176`）；读用例 `GetBlmPlanningStatusUseCase`（load None 抛 480——单点查询面语义） | 服务直读 `snapshot_repository.load`（聚合枚举面空态不抛——480 语义分立裁定 OD-3）；**零改动**既有用例/端口 |
| 审批数据面（6-3/6-6） | `list_checkpoints(plan_id)` 全量 probe CP-1..8 + 恢复记录 join sync_status 三态（`checkpoint_service.py:520-569`）；`CheckpointSummaryView` 8 键；恢复记录 12 键（`blm-checkpoint-recovery-{plan_id}`）；审批动作三命令（list/show/recover）+ `apply_correction` | **只聚合不操作**：段内分布计数+恢复留痕三键；审批动作零重复（6-6 已交付——本 Story 无任何写路径） |
| 审计数据面（1-10） | `AuditRepositoryPort.search(AuditSearchCriteria) -> AuditSearchResult`（items+total——`audit_repository.py:85`）；`AuditActionType` **24 值**枚举（R1-F8 订正——18 值失实）；PG 复合索引 `ix_audit_log_timestamp_action_type` 在位；**全局窗无 plan 维度**（查询仅 start/end——审计摘要聚合系统级事件，语义注记 OD-10）；**search 现状无 ContextVar session 即 RuntimeError**（fallback 仅 save 有 impl `:93-96`——HTTP 路由唯一消费方历史） | 时间窗 total+最近样本段（OD-10 口径——**断言体系为差值形态**，R1-F6）；**端口契约零演进+impl 单点增量**（search 增加 session_factory fallback ~6 行——OD-12 R2 重开：本 Story CLI 消费面是 search 首个非 HTTP 消费方，无 fallback 则 CLI 面审计段恒降级——AC-6 生产可用性；无分组计数需求）；分布分桶 defer（无 GROUP BY 端口实证——`audit_repository_impl.py` grep `func.count|group_by` 零命中） |
| 报告数据面（6-5a/6-5b） | `get_latest_by_plan(plan_id: uuid.UUID) -> StrategicReport \| None`（**参数 UUID 类型**——服务内 str→UUID 显式转换钦定 OD-13；已实现零消费方——本 Story 首激活）；`StrategicReport` **8 字段**实体（report_id/plan_id/report_type/file_path/section_count/degraded_section_count/generation_ms/created_at——6-5a 冻结面）；`aggregate_report_document` 公开函数（双链同源聚合） | 仅消费 `get_latest_by_plan` 单方法；**不动 `StrategicReport` 实体/不动 `ReportType` 枚举**（exec 视图非报告类型——OD-1）；报告正文/执行摘要章节零触碰（简化视图是指标态非内容态） |
| RAG 三色状态（UX v2.1） | **词族全零占用**（`RAG/traffic_light/status_indicator/红黄绿/green-yellow-red` src 内 grep 零命中——Agent C 亲验）；全仓无三值分级枚举（最近先例全是两值：`ValidityStatus` valid/expired、staleness stale/fresh、树节点 status） | **新建 `ExecutiveHealth` 三值枚举**（green/amber/red——全仓首个三值分级枚举，落应用层 ports 文件——OD-4/OD-12）；推导规则表 Task 0 冻结（OD-5） |
| Web 仪表盘/前端（Epic 21） | 未立项（epics L3369 Story 21.1 决策舱总览——KPI 10 项+风险雷达+BG 健康矩阵） | **不做**（epics L2391 取代注记钦定——UI 面归 Epic 21；本 Story CLI 呈现即 MVP fallback 形态） |
| REST 端点（Epic 7） | openapi.yaml 至今无 BLM 面 endpoint（6.1~6-7 惯例） | **不做**（CLI-only 第七连——6.1-DF5 先例；6.5a-DF1 顺延注记落档）；openapi.yaml 零 diff |
| bbox 四元组（6.7-DF2） | 6-7 已清偿半边（page_start/page_end）；树读侧 `payload.get("bbox")` 透传就绪 | **不做**（Web PDF.js 高亮是真实消费方——6-8 CLI-only 无 Web 高亮面，重锚 Epic 21/22 Web 前端立项——OD-8） |
| KPI 财务指标（FR-UI-04） | 10 项经营 KPI（全球销售收入/净利润等——prd L1938）数据源不在 BLM MVP 面（财务建模 5-12 输出/外部数据接入均非本 Story 依赖链） | **不做**（6-8 的「核心经营指标」= 规划态势指标聚合口径——OD-1 范围注记；财务 KPI 归 Epic 21+数据接入立项） |
| 事件消费 | L170 消费基建四件（poller 宿主等） | **不做**（纯查询面零事件订阅——七连「纯生产方/零消费」+ 6-7 双向皆无形态延续；锚位顺延 Epic 8，Task 0.7 注记） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 四段聚合数据结构（ExecutiveView 键契约）

**Given** 某 plan_id 下已存在 BLM 运行数据（latest 快照 `blm-planning-{plan_id}` 七键在位）与 Checkpoint 快照族（CP-1..8 至少一行）、最新战略报告（L2 `strategic_reports` 行）、时间窗内审计日志行（各数据面预置形态见 Task 0.5）
**When** 高管请求简化视图（编程面 `ExecutiveViewService.build_executive_view(plan_id)` 或 CLI `executive-view --plan-id <uuid>`）
**Then** 返回 `ExecutiveView` **8 键** frozen VO（`plan_id`/`generated_at`/`health`/`build_degraded`/`planning`/`approval`/`audit`/`report`——全键契约见 Task 0.1 冻结表），四段各自键恒在：
- **规划态势段** `PlanningSection` **8 键**：`available`（快照在位 bool）/`degraded`（数据源异常 bool——段级降级哨兵）/`completed_steps`/`total_steps`（期望 8——`BLM_TOTAL_STEPS` 常量单源）/`progress_percent`（int 0-100——`int(completed_steps / total_steps * 100)` 向下取整，**与 `BlmPlanningStatus.progress_percent`（round-2 float，`blm_phases.py:174-176`）口径有意分立**——同源分母分子、VO 侧 int 截断为高管视图整数口径钦定，R1-F3 裁定）/`current_step`/`degraded_step_count`（降级步计数——**派生自 state_data `degraded_steps`（`list[str]` 步骤标识清单）的 `len()`**，非直读计数键）/`last_activity_at`（timeline 末位条目 `completed_at` 键——timeline 条目六键 step/started_at/completed_at/status/summary_excerpt/degraded、ISO 字符串形态 `blm_planning.py:12-13`；无 timeline 降 None）
- **审批中心段** `ApprovalSection` **10 键**：`available`（probe 到 ≥1 checkpoint）/`degraded`/`total_checkpoints`/`completed_count`/`in_sync_count`/`pending_sync_count`/`invalidated_count`（sync_status 三态分布）/`last_recovery_mode`/`last_recovery_confirmed_by`/`last_recovered_at`（恢复记录 12 键直读留痕三键——无恢复记录降 None）
- **审计摘要段** `AuditSection` **7 键**：`degraded`/`window_days`（默认 7——服务常量 `DEFAULT_AUDIT_WINDOW_DAYS`）/`window_start`/`window_end`（ISO 字符串）/`total_events`（时间窗内总数——`AuditSearchResult.total` 单源）/`recent_events`（最近 5 条 `AuditEventSummary` **4 键** 元组：action_type/actor/target_resource/timestamp）/`last_event_at`（无事件降 None）——审计段**无 available 键**（窗口零事件是合法空态非不可得，与规划/审批/报告三段的 available 语义分立——OD-4）
- **报告可得性段** `ReportSection` **8 键**：`available`（`get_latest_by_plan` 非 None）/`degraded`/`report_id`（`str(StrategicReport.report_id)`——实体为 `uuid.UUID` 类型，str 化钦定）/`report_type`（"markdown"/"pdf"——`ReportType` 值域透传）/`file_path`/`section_count`/`degraded_section_count`/`generated_at`（**派生映射 = `StrategicReport.created_at.isoformat()`**——实体无 generated_at 字段（8 字段清单见范围边界表），R1-F4 裁定；ISO 字符串与 audit 段 window 键同型；`generation_ms` 是实体毫秒耗时字段**非**本 VO 键）；顶层 `ExecutiveView.generated_at` 同钦定 ISO 字符串（`datetime.now(UTC).isoformat()`——服务生成时刻，三时间键同型）；无报告时 report_id/file_path 等降 None、计数降 0——键恒在纪律，6-2 R1-6 七键契约同族）

**And** 段内计数均派生自既有单源（`total_steps` 快照 state_data 直读+`BLM_TOTAL_STEPS` 对照注记；sync 三态计数派生 `CheckpointSummaryView.sync_status`；报告计数派生 `StrategicReport` 实体字段）——**服务不新算任何跨源复合指标**（复合判定仅 health 一处——AC-2）

**验证标准/Validation Criteria:**
- [ ] 全数据预置场景：8 键 exact set（`{f.name for f in fields(ExecutiveView)}`——6-6 R1-F10 激活先例）+ 四段嵌套键集各自 exact set + 值级断言（completed_steps/total_checkpoints/section_count 与预置一致；**total_events 为差值断言**——预置前后两次查询差值==预置窗内行数，全局窗背景行不进断言，R1-F6）
- [ ] progress_percent 整数口径断言（`int(completed_steps / total_steps * 100)` 向下取整——3/8 完成 → 37 非 37.5；**与 `BlmPlanningStatus.progress_percent`（`round(x,2)` float——`blm_phases.py:174-176`）口径分立注记**：同源分母分子、VO 侧 int 截断为高管视图钦定，单点查询面 float 口径归该 property——两口径并存有意不互斥，R1-F3 裁定）
- [ ] recent_events 恰 5 条上限（预置 ≥5 条时取 5；<5 条时如数）+ 每条 4 键 exact set

### AC-2: RAG 三色健康状态推导（规则表三色判别）

**Given** 三个 plan_id 各持不同数据形态：**P-green**（8 步全完成零降级+checkpoint 全 in_sync+报告在位零降级小节+四源无异常）、**P-amber**（部分完成或存在降级或 checkpoint 有非 in_sync 或报告降级计数 >0 或任一源异常——五形态至少构造其二）、**P-red**（快照在位且已完成步全部降级——`degraded_step_count == completed_steps > 0`）
**When** 构建简化视图
**Then** `health` 按**确定性短路规则表**取值（优先级 red > green > amber——Task 0.2 冻结，实现为纯函数 `derive_health`，禁散落 if 链）：
1. **red**：`planning.available and planning.completed_steps > 0 and planning.degraded_step_count == planning.completed_steps`（已完成产出全部降级——可信度危险；UX L1250-1252 RAG 状态色语义「红色=危险」——R1 订正行号）
2. **green**：`planning.available and completed_steps == total_steps and degraded_step_count == 0 and (approval.total_checkpoints == 0 or approval.in_sync_count == approval.total_checkpoints) and report.available and report.degraded_section_count == 0 and build_degraded == False`（全链健康）
3. **amber**：其余一切（含：未完成/部分降级/sync 异常/无报告/段降级/空 plan 零数据——「关注」兜底态；空 plan 的 health==amber 是「无可判绿红的中间态」语义注记，非错误）
**And** 三色值域 = `ExecutiveHealth` 三值 str-Enum（`GREEN="green"/AMBER="amber"/RED="red"`——应用层 ports 文件新建，全仓首个三值分级枚举——OD-4；值对齐 UX「绿色=健康/琥珀=关注/红色=危险」用词，amber 不用 yellow——UX v2.1 英文用词单源）
**And** `build_degraded == True`（任一数据源顶层异常——AC-5）时 health 恒非 green（规则 2 显式含 `build_degraded == False` 条件——「拿不到数据不得报绿」读模型诚实性，6-7 build_degraded 哲学延续）

**验证标准/Validation Criteria:**
- [ ] 三 plan 三色值级断言（P-green→GREEN/P-amber→AMBER/P-red→RED——三场景数据形态互斥可判别：amber 形态钦定「3/8 完成+1 降级」组合；**P-green 构造路径钦定** = 8/8 快照+**零 checkpoint**（green 规则 `total_checkpoints == 0` 支路——最简构造不触恢复）+报告在位零降级，R1-F15；in_sync 退化语义注记：恢复记录 None→全量 in_sync（`checkpoint_service.py:526/:535` 实证），故「≥1 checkpoint+无恢复记录」亦全 in_sync 为 P-green 备选路径——钦定主路径零 checkpoint 防构造歧义）
- [ ] 空数据 plan（零快照零 checkpoint 零报告）→ health==AMBER + **三段 available 全 False（planning/approval/report——审计段无 available 键，AC-1/OD-4 三处钦定一致）+ 审计空态差值断言**（total_events 与场景基线一致——AC-4 差值体系，R1-F6；空态幂等读——AC-5 联动）
- [ ] 规则表单测矩阵全覆盖（Task 2 承载：三色×数据形态全枚举 ≥9 格——每格独立断言；验收面三 plan 是抽样锚）

### AC-3: 审批中心段聚合（分布+恢复留痕）

**Given** 某 plan_id 下已直写 3 个 Checkpoint 快照（2 个 completed + 1 个非 completed 混合形态——`snapshot_repository.save` 直写通道，session_id=`{CHECKPOINT_SESSION_PREFIX}{plan_id}:{cp_no}`、state_data 十键 = 6-3 per-step 契约七键（plan_id/step/summary/structured_output/degraded/degrade_reason/completed_steps）+ `list_checkpoints` 读取面 `.get` 三键（stage_id/completed/created_via）——`checkpoint_service.py:560-564` 亲验；与预置纪律②键清单同源——R2 统一）——**R1-F11 通道裁定：直写而非 create_checkpoint 全链**（后者五步编排触 Fake LLM/Embedding/L3/L4 写，与「装配面零 LLM 零 Embedding」声明互斥且产五类编排副产物），6-7 归档直写同精神先例，**CP 快照构造钦定空 checkpoint_no**（:78-84 守卫双条件）），且恢复记录 12 键已直写（`blm-checkpoint-recovery-{plan_id}`——与 `checkpoint_service.py:693-714` 构造键面同源直写，`pending_sync_checkpoints`/`invalidated_checkpoints` 钦定空清单→全量 in_sync 退化语义）
**When** 构建简化视图
**Then** 审批中心段计数与既有单源一致：`total_checkpoints == len(views)`（list_checkpoints probe 到的行数）/`completed_count`（`CheckpointSummaryView.completed` True 计数）/`in_sync_count + pending_sync_count + invalidated_count == total_checkpoints`（三态分布完备恒等式——**三态分布和恒等于总数**是不变量断言，缺行/重复计数即红）
**And** 恢复留痕三键值级断言：`last_recovery_mode == 恢复记录["recovery_mode"]`（"replay"/"override" 小写——entities 版枚举值域）/`last_recovery_confirmed_by == 恢复记录["confirmed_by"]`（高管审批身份——6-6 AC-4 审批留痕语义的聚合面兑现）/`last_recovered_at == 恢复记录["recovered_at"]`（恢复记录经 `snapshot_repository.load(f"blm-checkpoint-recovery-{plan_id}")` 直读 12 键 dict——`CHECKPOINT_RECOVERY_SESSION_PREFIX` 常量单源 `ports/checkpoint.py:90`，服务禁硬编码前缀字符串）
**And** 无恢复记录（未执行过恢复）→ 留痕三键恒在值 None（键恒在纪律；**真实仓储退化语义注记 R1-F2**：`RedisSnapshotStore.load` 吞一切异常归一 None（`:179-181`），「从无恢复」与「恢复记录损坏」在真实链路**同归空态三键 None**不可分立——「损坏→段降级」语义仅单测 AsyncMock 面承载，AC-5 注记同源）

**验证标准/Validation Criteria:**
- [ ] 混合分布值级断言（预置 2 completed + 1 非 completed → total==3/completed_count==2——计数与预置锚一致）
- [ ] 三态分布完备恒等式断言（和==total；三态判定链 invalidated > pending_sync > in_sync 清单命中制+None→全量 in_sync 退化语义——`checkpoint_service.py:535-556`，分布具体值与预置恢复记录清单直推）
- [ ] 恢复留痕三键值级断言（confirmed_by 值与预置恢复记录一致——值可判别非默认空串；recovered_at ISO 字符串值级相等——`:708` `datetime.now(UTC).isoformat()` 同源）
- [ ] 无恢复记录 plan → 三键 is None（对照腿）

### AC-4: 审计摘要段聚合（时间窗+最近样本）

**Given** 审计日志表内已预置时间窗内行（**6 条钉死**——3 种 action_type 各 2 条，`timestamp` 钦定 **`now() − i×100µs 递减微秒偏移**（i=1..6）**——R2-F1 修正原「+i 秒未来偏移」：窗口 end_time=服务调用时刻且边界**闭区间含端点**（impl `:143` `<=`），未来秒级偏移会使预置行出窗（差值==6 恒 0 红）；递减微秒偏移三性质兼得：全部 ≤ end_time 在窗内 ✓ + 严格互异去并列（PG timestamptz 微秒精度承载 ✓——impl 无次级排序键 R1-F5）+ 新于一切已存在背景行（**best-effort 占头**——xdist 同组串行下成立，他组并行写入不免疫——残余风险注记非「背景免疫」），经 `AuditRepositoryPort.save(audit_data)` 真实通道——**dict 必填双键 `log_id`（str UUID）+`timestamp`（ISO 字符串）**（impl `:62-63` 下标取值缺则抛——R1-F1），可选键 actor/action_type/target_resource/old_value/new_value）与窗口外行（1 条——`timestamp = now()-8 天`），时间窗默认 7 天（`DEFAULT_AUDIT_WINDOW_DAYS=7` 服务常量）
**When** 构建简化视图
**Then** **total_events 差值断言**（全局窗无 plan 维度——审计摘要聚合系统级事件 OD-10 语义注记；断言 = 预置前基线查询 total 与预置后查询 total 的**差值==6**，窗口外行不进差值——`AuditSearchCriteria(start_time=window_start, end_time=window_end)` 构造查询，total 单源；**窗口边界双端闭区间**（`>=`/`<=`——impl `:141/:143` 亲验，R1-F7）；`window_start == generated_at - timedelta(days=7)` 时间锚一致性——generated_at ISO 字符串解析对照）
**And** `recent_events` 为最近 5 条（`AuditSearchCriteria` 实现按 timestamp 降序——`audit_repository_impl.py:167` 亲验，**无次级排序键——timestamp 并列序不稳定**，故预置行微秒递减去并列为断言前置（R1-F5/R2-F1）；**6 条预置取 5 的取舍钦定 = 丢弃最旧 1 条（i=6 行）——断言序列为预置 i=1..5 行降序**（R2-F7）；每条 4 键：action_type/actor/target_resource/timestamp——从 items dict 挑键投影，**禁透传整行 dict**——`to_dict()` 实为 **15 键**（id/log_id/timestamp/actor/action_type/target_resource/old_value/new_value/correction_level/checksum/created_at/archived/archived_at/correlation_id/integrity_verified——R2 订正，R1 曾误 14 键漏 correction_level）不得进高管视图——安全面注记：投影白名单四键）
**And** `last_event_at == 预置行 max(timestamp)`（**同组串行前提下预置行占头**——best-effort 注记 R2-F1；与 recent_events[0].timestamp 同源一致性断言恒可写）；**本场景零新增**（合法空态）→ total_events 差值==0 + 段不降级不抛异常 + 键恒在（**「窗口内零事件」的字面绝对空断言在共享测试库全局窗下不可写**——背景行必在，R1-F6 改差值语义；recent_events/last_event_at 放弃绝对空断言改「与基线视图一致」）
**And** 审计段查询样本 limit 钦定 `limit=5`（只需最近 5 条样本——total 由 `AuditSearchResult.total` 独立承载不经 items 计数；**禁大 limit 拉全量样本客户端计数**——total 全行取回实现形态下 items 拉大 limit 是双重浪费，OD-10 口径）

**验证标准/Validation Criteria:**
- [ ] 窗口边界判别：差值形态（预置前后 total 差值==6，窗口外行不进差值——内外行数可判别）
- [ ] recent_events 5 条上限 + 4 键 exact set + 值级（action_type 与预置一致——预置行占降序头部背景免疫）+ 降序断言（recent_events[0].timestamp >= recent_events[-1].timestamp）
- [ ] last_event_at 与 recent_events[0].timestamp 值级相等
- [ ] 零新增空态（独立 plan_id 视图）→ 差值==0+不降级+键恒在（合法空态注记——审计段无 available 键的语义落位；**「独立极窄窗构造」不可行已删除**——7 天服务常量+零可选参数自锁，R1-F6）

### AC-5: 段级容错与空 plan 幂等读

**Given** 空 plan_id（零快照/零 checkpoint/零报告/**本场景零审计预置行**——全局窗背景行恒在，空态语义为「零新增」非「窗口绝对空」，R1-F6/R2 残留订正）或某数据源查询异常（异常形态归单测承载——验收面真实服务无故障注入通道，6-7 AC-5 顶层容错同款分立裁定）
**When** 构建简化视图
**Then** **段级独立容错**（6-7 节点级降级的段级版）：四源各自 try 包裹——单源异常仅该段 `degraded=True`（段内计数/标识降默认值），**其余段照常聚合，视图整体不抛**（「某段拿不到不得炸整体」——聚合面容错哲学；对照 6-7「树是唯一产物顶层空树」——本 Story 四段独立产物，顶层哨兵 `build_degraded = 任一段 degraded` 聚合）；**真实链路异常面注记（R1-F2）**：snapshot 源的 `RedisSnapshotStore.load` 捕获一切异常归一 None（`redis_snapshot_store.py:179-181`——连接失败/键缺失/JSON 损坏三态归一，6-6 `ports/checkpoint.py:60-67` 退化语义自注在案），故「损坏 vs 缺失」分立在真实 Redis 链路**不可达**（均落空态）；段 degraded 的异常面真实链路仅 **PG 两源**（audit search/report 查询的 session 异常）可触发，snapshot 源容错分支归单测 AsyncMock 面承载（6-7 DR1-5 同族裁定——「真实端口不可写断言归单测」原则转述）
**And** 空 plan 幂等读：视图正常返回 8 键（planning.available==False/approval.available==False/report.available==False/audit 空态**差值断言**——AC-4 差值体系）、`build_degraded==False`（「没有数据」非「拿不到数据」——6-7 空树分立语义延续）、health==AMBER（AC-2 规则 3）、**不抛异常**（6-4 `ChainOfThoughtTraceView`「空档案返回 total=0 不抛异常」+ 6-6 空清单+ 6-7 空树三先例族——枚举聚合面语义）
**And** 畸形 plan_id（非 UUID）→ 用例层 242 `EntityValidationError`（`GetTraceabilityTreeUseCase`/`GetBlmChainTraceUseCase` UUID 守卫直系先例——服务层不守卫，分工钦定同 6-7 OD-3）；编程面 `pytest.raises` 形态、CLI stderr 形态分立（AC-6）
**And** 快照在位但 state_data 畸形（缺键/类型错）→ planning 段降级（`degraded=True` + available==False + 计数降 0），不抛（读侧脏数据守卫——6-5b 脏形态守卫同款形态；归单测矩阵承载畸形形态枚举）

**验证标准/Validation Criteria:**
- [ ] 空 plan 幂等读三断言（8 键恒在+build_degraded==False+health==AMBER）
- [ ] 畸形 plan_id → 242（code 值级断言——编程面）
- [ ] 段级容错归单测（四源×AsyncMock 抛异常 → 各段 degraded=True+其余段正常+build_degraded==True——Task 2 矩阵；验收面零 mock 红线不承载异常注入，6-7 DR1-5 分立同款）
- [ ] state_data 畸形守卫归单测（缺 completed_steps 键/非 int 形态 → 段降级不抛）

### AC-6: CLI `executive-view` 命令（高管速览入口）

**Given** 全数据在位（AC-1 形态）
**When** 执行 `sisys-agent executive-view --plan-id <uuid>`
**Then** 四段结构化输出（纯标准库 print——「输出即契约」6-6 checkpoint-list 同哲学；**无 JSON 输出模式**——仓内 CLI 全 stdlib print 惯例，Agent A 亲验 `grep "json" agent_cli.py` 零命中）：首行 `高管简化视图（plan: {plan_id}）` + 健康行 `健康状态: {green|amber|red}（{健康|关注|危险}）`（**build_degraded 时追加「（部分数据降级）」标记**）+ 四段各以 `── {段名} ──` 分隔行承载：
- 规划态势：`进度: {completed}/{total}（{percent}%） | 当前: {current_step} | 降级: {n} 步 | 最近活动: {last_activity_at or 无}`
- 审批中心：`Checkpoint: 共 {total} | 已完成 {completed} | in_sync {n} | pending_sync {n} | invalidated {n}` + 恢复行（留痕在位时 `最近恢复: {mode} by {confirmed_by} at {recovered_at}`；无恢复 `最近恢复: 无`）
- 审计摘要：`近 {window_days} 天事件: {total} | 最近: {action_type} by {actor} at {timestamp}`（total 为**全局窗动态值**非恒 0——共享库背景行在窗内，R1-F6；无窗内事件时降 `最近: 无`——空态半行形态钦定 R1-F16；S9 空态断言对审计行用 in 判定（`"近 7 天事件:" in stdout`）非整行精确）
- 报告：`最新报告: {report_type} {file_path} | 章节 {section_count}（降级 {degraded_section_count}）`（无报告 `最新报告: 无（可先执行 report-generate）`——**指向既有命令的操作提示**，非新功能）
**And** 退出语义：正常 exit 0（含空 plan 空态——空态是正常态非错误，AC-5 语义；空态输出=首行+健康行 amber+四段各自空态行）；畸形 plan_id → exit 1 + stderr `[EXCEPTION_242]`（6-3 R1-F18 前缀统一先例；`_run_trace_tree_cli` 五步定式 :1423-1458 直系样板）
**And** 本 Story CLI 面无角色门槛（「CEO/高管」是 UX 语义——3-8/6-6/6-7 查询命令先例均无角色检查；RBAC 门槛归 7-2 REST 入口立项时评估——6-7 AC-6 同款注记落档）；参数面仅 `--plan-id` 必填单参数（**零可选参数**——YAGNI：无 --window-days/--format 需求来源，审计窗/输出形态均服务常量钉死）

**验证标准/Validation Criteria:**
- [ ] 全数据输出断言：健康行精确匹配 + 四段分隔行 + 至少各一段值级行（CLI 单测承载完整覆盖；验收场景经 CLI in-process 直调保红——6-6 S2/6-7 S9 双清先例）
- [ ] 空 plan 输出断言（四段空态行齐备+exit 0）
- [ ] 242 stderr 形态（`[EXCEPTION_242]` in stderr + exit 1）

### AC-7: 性能与并发（三段口径——OD-7）

**Given** 全数据在位（AC-1 形态，服务面已预热）
**When** 采样计时（20 轮——`sorted(durations)[ceil(0.95*n)-1]` 数学口径，6-3 AC-8/6-6 AC-6/6-7 AC-7 同款公式与模块级期望常量独立构造）
**Then** **视图加载 P95<500ms**（epics L2414「仪表盘加载延迟 P95<500ms」的聚合服务面等价口径）：口径 = `build_executive_view` 服务面窗口（snapshot load + list_checkpoints（内部 = 恢复记录 join load 1 + CP probe 8）+ 审批段恢复记录直读 + get_latest_by_plan 单行查 + audit search 窗口查询——五读串行；**Redis 点查×11/视图**（latest 1 + list_checkpoints 内部 9 + 审批段恢复记录第二次直读 1——R1-F10 订正，×9 失实；恢复记录同键双载事实声明：`CheckpointSummaryView` 不含恢复记录内容故审批段直读必要）+ PG 单行/窗口查——实测锚定；**审计 search 的 total 全行取回实现形态**（`audit_repository_impl.py:159-164`）在 MVP 数据量级（时间窗内百行级）远小于门禁——**风险注记**：审计量增长至万行级时 total 全行取回成为热点，分组计数端口立项锚 Epic 7/21，落 docstring）
**And** **并发查看 20 个仪表盘**（epics L2416 的读面等价口径）：**单一数据源 plan_id × 20 路并发读**（asyncio.gather 20 路 `build_executive_view(plan_id)`——读面幂等无副作用，并发安全证明充分；**服务无状态约束**——SINGLETON 实例并发共享，实现禁持每次调用的可变实例态——6-5a AC-7 服务无状态先例+OD-8「单一数据源×N」采样形态同构；**场景内禁 set_session**——20 路共享单一 AsyncSession 非并发安全（R2-F2e），每路走 fallback 独立会话天然 per-task 隔离；20 路结果两两相等断言 + 全部成功不抛；**对照排除集钦定 R1-F5/R2-F4（六键）**：`generated_at`/`audit.window_start`/`audit.window_end` 三键每次调用新生成（ISO 时间戳）+ **`audit.total_events`/`audit.recent_events`/`audit.last_event_at` 三键受全局窗并发写入抖动**（他 xdist 组在 gather 期间 commit 的审计行仅进晚于该行的各路窗口——两两相等 flake，R2-F4）——**不入对照**；audit 段并发对照仅 `degraded`/`window_days` 两稳定键（并发安全证明目标=服务无状态+四源读不互损，audit 段值级对照对该目标无增量证明力）；逐路键值对照形态钦定为「tuple 序列化剔除六键后逐路相等」；预置审计行微秒递减去并列（impl 无次级排序键——R1-F5）；六 VO 全标量+tuple 可序列化（`CheckpointSnapshot` 含 dict 字段不可哈希的约束不波及 VO——对照形态用 dataclasses.asdict+tuple 化而非实体入 set））；**「20 个独立 plan」的写面变体不采**（需 20 套四源预置，构造成本与读面并发安全证明目标不成比例——6-5a OD-8 构造成本工程评估先例）
**And** **「信息密度达标（Lighthouse 评分≥90）」与「状态指示器实时更新」为前端指标后端不定义**（epics L2415 自注「前端指标，后端不定义」原文钦定——口径差声明落验收 docstring；Web 面指标归 Epic 21 Story 21.1 届时验收——OD-7 第三段声明）

**验证标准/Validation Criteria:**
- [ ] 20 轮采样 P95<500ms（预检服务可达 + 预热含首次 load——R8-F5 注记继承）
- [ ] 并发 20 路全部成功 + 两两相等（对照排除集六键 {generated_at, window_start, window_end, total_events, recent_events, last_event_at}——tuple 序列化剔除后逐路相等，R1-F5/R2-F4）
- [ ] 前端指标口径差声明落 docstring（Lighthouse/实时更新两项）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **零新增领域事件、零事件发布调用、零事件订阅**（本 Story 钦定——OD-2）：纯查询聚合面零状态变更——「查询不发布事件」architecture.md:1293 成文 + 6-7 OD-2 零事件先例族延续（6-4 OD-6/6-5a OD-6/6-6 OD-2）——**查询型故事零事件第七连**；`configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` **零 diff**；`_FROZEN_EVENT_COUNT=56` 冻结键数基线零变化（`tests/contracts/test_event_channel_mapping_pdf_report.py:23-24`——Task 4 守护复跑）；蓝图无高管视图事件定义（epics 6.8 无事件载体要求——读侧聚合非状态变更；`CorrectionApproved` 无生产者现状维持不激活——Agent B 亲验 src 零生产者，6-6 已裁定不激活）
- [ ] 守护承载：Task 4 复跑 `_FROZEN_EVENT_COUNT=56` 断言（零新增=登记数不变）；架构验证器 B 含「视图服务零 publish 调用」源码断言（6-7 树服务零发布守护的同款变体——`test_traceability_tree.py:111-155` 样板）

#### 数据模型 (Data Models)

- [ ] **零 domain 改动**（OD-12 三零 Story）：`src/domain/` 零 diff——四段 VO+枚举全部落**应用层** `src/application/ports/executive_view.py`（读侧 DTO 归应用层——6-6 `CheckpointSummaryView`/6-7 五 VO 先例族；对照 6-5b `CitationEntry` 入 domain 是报告域特例非先例强制——6-7 OD-4 论证沿用）
- [ ] `ExecutiveHealth`（str-Enum 三值 GREEN/AMBER/RED）——**全仓首个三值分级枚举**（对照先例族全两值：`ValidityStatus`/staleness/树节点 status——OD-4 显式注记）；值域对齐 UX v2.1「绿色=健康/琥珀=关注/红色=危险」（prd L1938 三色状态分类）
- [ ] 六 VO frozen dataclass 键契约（Task 0.1 冻结唯一版本——实现禁增删键）：`ExecutiveView` **8 键**（plan_id/generated_at/health/build_degraded/planning/approval/audit/report）+ `PlanningSection` **8 键** + `ApprovalSection` **10 键** + `AuditSection` **7 键** + `ReportSection` **8 键** + `AuditEventSummary` **4 键**（全键定义见 AC-1；`recent_events: tuple[AuditEventSummary, ...]` 恒元组——frozen 纪律；可变 dict/None 逃逸口**不需要**——本 Story 无 dict 字段（对照 6-7 DocumentNode bbox MappingProxyType 特例——无此形态））
- [ ] 构造守卫：`__post_init__` 校验 plan_id 非空字符串 + health 枚举成员校验（裸 str 拒绝——`ArchiveType` validate 同款形态）+ 计数非负（**四段计数 ≥0**——planning（completed/total/degraded_step_count）/approval（total_checkpoints 与三态计数）/report（section 双计数）/audit（total_events）——R1 订正「三段」漏 audit；`recent_events` 元组不适用此守卫注记；`StrategicReport` 五查先例）；违例抛 `EntityValidationError`（242 复用——实体不变量场景钦定）
- [ ] **不动既有冻结面**：`StrategicReport` 实体（6-5a 冻结）/`CheckpointSummaryView` 8 键（6-6 冻结）/`BlmPlanningStatus`（6-1 冻结）/`CheckpointStatus` 4 值枚举/`ReportType` 两值枚举——全零 diff（服务只读消费）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] 新端口 `ExecutiveViewPort`（应用层 `src/application/ports/executive_view.py`，`@runtime_checkable Protocol`，docstring 版本注记「（v1.0.0）」——`TraceabilityTreePort` :148 样板）：单 async 方法 `async def build_executive_view(self, *, plan_id: str) -> ExecutiveView`（keyword-only——6-7 签名风格）
- [ ] 端口注册中心登记：`register_port`（PortSpec：name=`executive_view_service`/version="v1.0.0"/interface=ExecutiveViewPort/impl=lambda/SINGLETON/tags=("executive","view","application")/owner）+ 用例注册 `executive_view_use_case`——组合根 `composition_root.py:2012-2060`（6-7 traceability 双注册块）邻近落位
- [ ] 端口契约测试：`tests/contracts/test_port_contract_executive_view.py`（五断言族——注册可达/spec 元数据/lambda 注入链 getsource/resolve 可达/方法签名——`test_port_contract_traceability_tree.py` 样板直系复刻）
- [ ] **复用四既有注册名**（组合根 lambda resolve 目标，主会话亲验）：`snapshot_repository`（:950）/`checkpoint_service`（:2347，v1.1.0）/`report_repository`（:3434）/`audit_repo`（:487）——**零新 infra 依赖、零新仓储成员**（6-4 CLI session P0 三步排查法核验：lambda 无新 PG 构造——OD-11）；**服务报告段编排钦定 `uuid.UUID(plan_id)` 显式转换**（`get_latest_by_plan` 参数为 `uuid.UUID` 类型——`report_repository.py:38`，畸形已在用例层 242 拦截故转换安全，R1-F7）

#### 端口契约清单执行约束（强制）

- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口（`ExecutiveViewPort` 聚合视图 vs `ReportGenerationServicePort` 生成语义 vs `CheckpointServicePort` 单域查询——语义正交非同义重复；`get_latest_by_plan` 经 `report_repository` 消费而非新开报告查询端口——单方法消费不构成端口重复）
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

- [ ] **零新增领域异常、零既有异常改动**（OD-3）：242 复用（畸形 plan_id——用例层 UUID 守卫+VO 构造守卫两消费面）；空 plan 幂等读不抛（三先例族——6-4/6-6/6-7）；段级容错走 degraded 键承载（非异常路径——6-5b「引文是增强面非阻断面」聚合版+6-7 节点降级树形版之后的段级版）；480 **不消费不复现**（`GetBlmPlanningStatusUseCase` load None 抛 480 是单点查询面语义——本 Story 聚合枚举面空态不抛，语义分立钦定；planning 段 load None → available=False 非异常）；planning 段 480-489/report 段 490-499/traceability 段 372-379 三段预留维持零触碰（R1 依据链订正：traceability 段权威源是 `_code_ranges.py:61-62`（traceability (370,379) 段现仅占 370/371）+6-7 注记——异常设计文档 §3.3.2 无该段落，按设计文档对表会查无此段）
- [ ] **否决备选**：开新码（如 `ExecutiveViewError` 500+）——四段全降级+畸形 242 后无真实 raise 触发面（YAGNI）；开码即引入「空 plan 误报」反语义面（6-7 OD-3 否决论证同构）
- [ ] 提交前三条 grep 自查零输出（`raise ValueError`/`HTTPException`/`Exception(` 继承——三红线）

#### API 契约 (API Contract)

- [ ] **零 REST 面**（CLI-only 第七连——OD-1）：`docs/api/openapi.yaml` 零 diff（契约测试守护——`test_api_contract_*` 既有族零破坏）；6.5a-DF1（`/plans/{id}/export` REST 导出面）顺延 Epic 7 注记落档（Task 0.7）
- [ ] CLI 契约：`sisys-agent executive-view --plan-id <uuid>`（argparse 扁平子命令——`build_parser` add_parser 族 :525 trace-tree 邻位；单必填参数；退出码 0/1 语义见 AC-6）

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖（**本 Story 零改动——OD-12**） |
| application | `src/application/` | 用例编排（端口+VO+服务+用例新建四件） |
| interfaces | `src/interfaces/` | 适配器（**零改动**） |
| infrastructure | `src/infrastructure/` | 技术实现（**单点增量——OD-12 R2 重开**：`audit_repository_impl.py` search 增加 session_factory fallback ~6 行，唯一 infra 改动） |

**依赖方向矩阵**（本 Story 新增文件落位）
| 起点 \ 终点 | domain | application | interfaces | infrastructure | entrypoints |
|---|---|---|---|---|---|
| **application/ports/executive_view.py** | ✓ 允许（仅标准库+domain ports 类型引用） | — | ✗ | ✗ | ✗ |
| **application/services/executive_view_service.py** | ✓ 允许 | ✓ 允许 | ✗ | ✗ | ✗ |
| **application/use_cases/get_executive_view.py** | ✓ | ✓ | ✗ | ✗ | ✗ |
| **entrypoints/agent_cli.py**（▲ 扩展） | ✓ | ✓ | ✗ | ✗ | — |

- 服务 import 白名单（架构验证器 C 断言面）：`src.domain.ports.*`（SnapshotRepositoryProtocol 等类型）/`src.domain.entities.*`（StrategicReport 类型）/`src.application.ports.*`（四消费端口+自有 VO）——**禁 infrastructure import**（6-7 `SERVICE_ALLOWED_PREFIXES` 白名单同款）

**设计规则 R1~R4 落点**（R1 补节——6-6/6-7 连续两 Story 钦定件对齐）：
- **R1（复用既有基础端口）**：四源全既有端口零新增基础端口（snapshot_repository/checkpoint_service/report_repository/audit_repo 四注册名 resolve——OD-11）
- **R2（应用层具体端口组合注入）**：`ExecutiveViewPort`（应用层新端口）组合注入四既有依赖——读侧聚合 CQRS 投影形态（架构模式节同源）
- **R3（infrastructure 适配器全复用）**：零 infra 改动零新仓储成员（OD-12 三零 Story）
- **R4（入口组装）**：CLI `executive-view` 子命令（agent_cli add_parser 邻位注册+五步定式分发）+组合根双注册（`executive_view_service`/`executive_view_use_case`——Task 3）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_executive_view.feature`（OD-9 命名——executive_view 功能名族，禁故事编号后缀；对 epics L2428 钦定名 `test_executive_dashboard.py` 的显式偏离——词族统一 executive_view：dashboard 词面向 UI 仪表盘（Epic 21 取代面），view 词对齐 CLI 查询形态；6-7 OD-9 对 provenance 偏离同款拆分声明）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_executive_view.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）——钉死 **12 场景**（AC-1×2 / AC-2×1 / AC-3×1 / AC-4×2 / AC-5×1 / AC-6×2 / AC-7×2 / 收尾×1，Task 0.4 定稿钉死确定值并全文同步，禁范围值进入后续 Task）；**epics 架构测试三项落位对账**（epics L2409-2411）：仪表盘显示测试（10 项 KPI+状态指示器）→S1/S2（**四段聚合+三色即 KPI 面的 MVP 口径对账**——10 项财务 KPI 归 Epic 21 范围注记 OD-1；状态指示器=health 三色 S2 承载）/信息密度测试→AC-7 前端指标口径差声明（Lighthouse 后端不定义——epics L2415 自注原文）/审批中心测试→S3——功能等价重分布（6-6 OD-5/6-7 OD-6 先例）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（模块级 `event_loop` fixture + `_run_async` helper——6-x 三件套）
- 同一中文文本可能需要同时支持 given/when 装饰器（共用文本按模块各自重新定义一份 @given——6-x 样板实证形态）
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——本 Story 异常面窄化（242 单码——OD-3）：畸形 plan_id 242 入 S7（编程面腿）；CLI 242 stderr 形态入 S9；段级容错归单测（验收面真实服务无故障注入通道——「真实端口不可写断言归单测」同族裁定，6-7 DR1-5 为原则转述非逐字——R1 注记）；**epics 模板「404/403/409」资源端点三例外码注记**：本 Story 无 REST 资源端点（CLI-only——OD-1），空态走幂等读（AC-5）非 404；403/409 无触发面（无角色门槛无状态变更——注记落 Task 0.4）
- **R6 模板合规**：feature/py 组织结构对齐 `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`/`.py`——`# language: zh-CN` 中文 Gherkin + AC 横幅注释分组（`# ===` 分隔）+ `@scenario(...)` 多行字面量路径绑定 + **12 场景全绑定**（R6 自身仅绑定 30 场景中 17 个属旧模板欠账，新文件禁沿用）；pytestmark/context dict/`_run_async` 三件套基建承载；**断言必须真实**（禁 then-pass 占位）；装配形态对齐 6-7（验收装配面零 LLM 零 Embedding——纯读侧聚合无生成调用）
- **场景分化维度表（Task 0.4 钉死输入——含收尾共 12 场景全枚举 S1~S12；S 编号为 6-8 自有编号，跨故事引用一律带故事号前缀）**：S1（AC-1）= 四段全落位（快照+checkpoint 混合直写+恢复记录直写+报告+审计窗内行全预置→8 键/四段键集 exact set+值级断言（**total_events 差值形态**）+progress_percent 整数口径）；S2（AC-2）= 三色规则表（三 plan 三形态：P-green **钦定「8/8 快照+零 checkpoint+报告在位零降级」**（green total==0 支路最简构造，R1-F15）/P-amber「3/8 完成+1 降级」/P-red「已完成步全降级」→三色值级+空数据第四腿 health==AMBER——四断言段单场景）；S3（AC-3）= 审批中心分布+留痕（直写 3 CP 混合 completed 分布计数+三态完备恒等式+恢复留痕三键值级）；S4（AC-4）= 审计时间窗+样本（6 窗内（3 种 action_type 各 2 条，**timestamp=now−i×100µs 递减微秒偏移去并列**——R2-F1）+1 窗外行（now-8d）→**total 差值==6**+recent 5 条 4 键（**断言序列=预置 i=1..5 行降序**）+降序+last_event_at 一致性（同组串行占头前提）——钉死值 R1/R2 修订）；S5（AC-4）= 审计零新增空态（独立 plan_id 视图差值==0+不降级+键恒在——**绝对空断言不可写已改差值语义**，R1-F6；独立场景保判别力）；S6（AC-1/AC-5）= 段缺席形态（有快照无报告无恢复记录——部分可得：report.available==False+留痕三键 None+planning 正常聚合——「部分数据」与「零数据」分立锚）；S7（AC-5）= 空 plan 幂等读+畸形 242（空 plan 三断言（审计腿差值）+畸形腿 pytest.raises 两段）；S8（AC-6）= CLI 全数据输出（**期望 health 钦定 GREEN**——预置 8/8 快照+2 CP 直写（completed）+恢复记录直写空清单（→全 in_sync）+报告零降级，R1-F15；健康行精确匹配+四段分隔行+值级行——in-process 直调）；S9（AC-6）= CLI 空态+242 stderr（空态四段行齐备 exit 0——审计行 total 为全局窗动态值用 in 判定，R1-F6/F16+畸形 exit 1 stderr——两腿）；S10（AC-7）= 性能采样（20 轮 P95<500ms+预热；**C 面禁 set_session 走 fallback**——R2-F3 性能口径含 fallback 连接开销更保守真实）；S11（AC-7）= 并发 20 路（gather 20 路全成功+两两相等——**排除集六键** R1-F5/R2-F4+**禁 set_session** R2-F2e）；S12（收尾）= src 与四测试目录完成清单存在性断言（**断言对象=File List 的 src/测试项存在性；两 md 台账（deferred-work/sprint-status）与故事文件不入断言面**——6-7 S12/DR3-10 同款）
- **逐场景调用面矩阵（Task 0.5 钦定）**：S1~S7 = **编程面 A 组**（服务/用例直调+**sync 层 set_session 回滚式**——R2-F3；断言锚 VO 在编程面单源可达；S7 畸形腿经用例）；S10/S11 = **编程面 C 组**（服务直调**禁 set_session**——每路 fallback 独立会话+commit 式预置+定向 DELETE——R2-F2e/F3）；S8/S9 = **CLI 面 in-process 直调 B 组**（`agent_cli.main(argv)` + SystemExit 捕获——6-7 `_run_cli_trace_tree` :948-967 样板：**每次 CLI 直调前 `get_resolver().clear_singleton()` + `clear_scoped()` 双清钦定**——6-6 R3-1 纪律+6-7 先例+**`reset_session` 清 ContextVar**（R2-F3 陷阱：asyncio.run 新循环继承上下文的 fixture session 会「Future attached to a different loop」——必清使服务走 fallback）；**禁重新 bootstrap**——`_ensure_bootstrapped` 自动短路；本 Story 服务依赖四注册名全在默认 bootstrap 装配链——无 env 桥接面（对照 6-7 BLM_SEARCH_COLLECTION monkeypatch——本 Story 零新 env 依赖，双清后 resolve 全可达）；B 组 PG 预置 commit 式+teardown 定向 DELETE 行数断言；**CLI 交互面的完整参数/输出覆盖由 `tests/unit/interfaces/cli/test_agent_cli.py` 承载**）；S12 收尾=文件存在性断言，无服务调用面
- **pytestmark**：显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.database, pytest.mark.redis, pytest.mark.qdrant, pytest.mark.xdist_group("blm-planning-perf")]`（**qdrant marker 保留理由**：bootstrap/组合根 resolve 装配链含 Qdrant 适配器（`tests/conftest.py` `_bootstrap_once` session autouse——6-7 同款注记：装配链依赖非业务依赖）；**无 minio marker**——零 MinIO 依赖（读侧不触 L4）；服务不可达环境 `pytest.skip()` 动态跳过（禁 `@pytest.mark.skip` 写死）；xdist_group 整模块——与 6-x 验收+集成同组串行）
- **数据面预置纪律**：四通道全真实服务（零 mock 红线）——**R1-F11/F12 通道体系修订+R2-F3 PG 面三分面钦定（直写+按调用面分通道）**：① BLM latest 快照：经 `snapshot_repository.save(CheckpointSnapshot)` 直写（session_id=`blm-planning-{plan_id}`、state_data 七键、`BLM_PLANNING_SESSION_PREFIX` 常量构造——构造形态参照 6-1 timeline 条目六键；`CheckpointSnapshot` 构造守卫注记：`checkpoint_no and not persistent_note_ref` 双条件才抛 484——**空 checkpoint_no legacy 形态不触发**（`checkpoint_snapshot.py:78-84` 亲验），预置钦定空 checkpoint_no）；② Checkpoint 快照族+恢复记录：**全部直写**（CP 快照 session_id=`{CHECKPOINT_SESSION_PREFIX}{plan_id}:{cp_no}`、state_data 含 `plan_id/step/summary/structured_output/degraded/degrade_reason/completed_steps`（6-3 per-step 契约七键）+`stage_id/completed/created_via`（`list_checkpoints` 读取面 `.get` 键——`checkpoint_service.py:560-564`）；恢复记录 12 键直写与 `checkpoint_service.py:693-714` 构造键面同源、`pending_sync_checkpoints`/`invalidated_checkpoints` 钦定空清单→全量 in_sync 退化语义、`recovery_mode` 小写 str、`recovered_at` ISO 字符串）——**不走 `create_checkpoint`/`execute_recovery` 编排通道**（前者五步编排触 Fake LLM/Embedding/L3/L4 写与「装配面零 LLM 零 Embedding」声明互斥且产五类编排副产物（L2 归档行/L3 向量/L4 WORM 对象/outbox 行/note+compressed 缓存键），后者事件发布产 outbox 行——直写零副产物免五类清理面，6-7 归档直写同精神；CP 快照构造同样钦定空 checkpoint_no（:78-84 守卫——R2-F7 重申②面））；③ 报告行：经 `report_repository.save(StrategicReport, metadata)` 真实写（实体构造**八字段**+守卫——`test_acceptance_markdown_report` 报告构造先例）④ 审计行：经 `audit_repo.save(audit_data dict)` 真实写（**必填双键 log_id（str UUID）+timestamp（ISO 字符串）**——impl `:62-63` 下标取值缺则抛，R1-F1；可选键 actor/action_type/target_resource/old_value/new_value——键面已实证免 Task 0.5 复核）；**PG 面（③④）按调用面三分（R2-F3）**——**A. 编程面回滚组（S1~S7）**：`set_session` 注入 fixture session（**必须在 sync 层调用**——unified_audit_log `:143-149` 先例：sync fixture 内 set_session 传播进每个 `run_until_complete` task 上下文，async fixture 内 set 不外泄到步骤 task——R2-F5 实现陷阱注记；行号订正：R1 曾引 :126-140 实为 pg_session fixture，set_session 在 :143-149 audit_repository fixture）→ 预置 flush 不 commit → 服务读同 session 同事务可见（audit search 经 `get_session()` ContextVar impl `:48-50`；report 同路径）→ teardown `rollback` 整体回收（**零 DELETE 通道**——R1-F9 裁定对该面维持：RLS 四策略+无 FORCE RLS+create_all 兜底不建 RLS+deny 静默 0 行四态漂移下 DELETE 不可靠）；**B. CLI 面（S8/S9）**：**`reset_session` 清 ContextVar**（R2-F3 陷阱：ContextVar 进程级——CLI 五步定式 `asyncio.run` 新循环继承当前上下文的 session，但 fixture session 连接绑定模块 event_loop，新 loop 内使用触发「Future attached to a different loop」——必须先清使服务走 fallback 独立会话）→ 预置经 `async with session_context(session_factory)` **commit 式**（fallback 会话读已提交行——report get_latest fallback `:153-161` 先例；audit search fallback 为 OD-12 新增）→ teardown **定向 DELETE**（按预置 log_id 集/report_id——**owner 身态注记**：无 FORCE RLS 下表 owner 绕过 RLS，测试建表用户即 owner 时 DELETE 可行；**行数断言防静默 0 行假绿**——DELETE 后按 log_id 计数==0 复核）；**C. 并发/性能面（S10/S11）**：**场景内禁 set_session**（20 路 gather 共享单一 AsyncSession 非并发安全——asyncpg「another operation in progress」，R2-F2e 定谳）→ 每路各自走 fallback 独立会话（ContextVar 无 session 时 impl 层自建——天然 per-task 隔离）→ 预置 commit 式+teardown 定向 DELETE（同 B 形态）；**Redis 面（①②）teardown 定向清理**：latest/CP 键族/恢复记录按 session_id 定向 DEL（uuid plan_id 天然隔离；CP 键族按预置 cp_no 清单删）；键计数净增 0 纪律——6-3 R1-F1（B/C 面 DELETE 行数断言承载）
- **回归面（强制）**：本 Story 纯新增（零既有源文件改动除 agent_cli.py/composition_root.py 两扩展）——回归验证=四目录全量零失败+6-6 checkpoint 验收/6-5a 报告验收零破坏（新增端口/命令不触既有断言面）；`_FROZEN_EVENT_COUNT=56` 复跑（Task 4.2）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（六 VO+枚举键契约/端口签名/derive_health 规则表/零事件零异常裁定/CLI 命令/OD 裁定落档）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态 = 步骤函数运行期失败：延迟 import 抛 `ImportError`（缺失 `executive_view` 模块/类）或断言步 `AssertionError`；收集期零错误本身即延迟 import 纪律的自证——6-2/6-3/6-6/6-7 先例）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：① 组合根新注册 resolve 可达（`executive_view_service`/`executive_view_use_case`——注入链非 None + 四依赖 resolve 真实可达）② CLI `executive-view` 入口接线（单测用例承载）③ 视图服务零事件发布守护（架构验证器 B）④ `get_latest_by_plan` 首消费激活接线（聚合→报告段 round-trip——集成场景承载）；「已实现未接线」组件登记 deferred-work（本 Story 无新未接线件——get_latest_by_plan 由本 Story 接线终结零消费方状态）
- [ ] **锚定义务六条处置落档**（Task 0.7——deferred-work 台账更新；**四条 6-8 锚定+两条例行顺延**，R1 口径统一）：6.5a-DF1（REST 导出面顺延 Epic 7）/6.5a-DF2（L0 撕裂顺延——触发条件不变注记）/6.7-DF2（bbox 四元组重锚 Epic 21/22——Web 高亮消费方裁定）/L129 data_pipeline 轨（读侧聚合非批量管线维持注记）/L170 事件消费基建（顺延 Epic 8）/L17 langgraph retry（不触发顺延）

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
| **TDD 单元测试** | 六 VO+枚举 | 键集 exact set/构造守卫 242（裸 str 拒绝/负计数拒/plan_id 空 拒）/health 枚举值域 | `tests/unit/application/test_executive_view_vos.py`（新建） | Task 1 |
| **TDD 单元测试** | 视图服务四段编排 | 四段聚合（Mock 四端口——AsyncMock spec=Protocol）/derive_health 规则表矩阵（三色×数据形态 ≥9 格全枚举）/段级容错（四源×抛异常→段 degraded+其余正常+build_degraded）/空 plan 幂等读/state_data 畸形守卫/恢复记录留痕三键/审计窗口构造与投影白名单 | `tests/unit/application/test_executive_view_service.py`（新建） | Task 2 |
| **TDD 单元测试** | 用例层 | UUID 守卫 242+透传 | `tests/unit/application/use_cases/test_executive_view_use_case.py`（新建） | Task 3 |
| **TDD 单元测试** | CLI executive-view | 参数解析/四段输出行/空态输出/242 stderr/exit code/五步定式 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~AC-7 全覆盖） | `test_acceptance_executive_view.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_executive_view.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约 | 新端口注册/spec 元数据（v1.0.0/SINGLETON/tags）/resolve 可达/注入链 getsource/新用例 PORT_NAMES | `tests/contracts/test_port_contract_executive_view.py`（新建——五断言族） | Task 3/4 |
| **SDD 架构验证** | 六边形架构约束 | 服务/VO 落位（application 层/禁本地 Protocol）/零 publish 守护/零 domain 改动守护（本 Story diff 面核验）/CLI 接线 | `tests/unit/architecture/test_executive_view.py`（新建——OD-9 对 epics 钦定名 `test_executive_dashboard.py` 的显式偏离） | Task 6 |
| **集成测试** | 四源真实链聚合 | 真实 Redis 快照/CP 族+PG 报告/审计行→服务直调四段 round-trip（含 `get_latest_by_plan` 首消费激活验证） | `tests/integration/test_integration_executive_view.py`（新建——OD-9 对 epics 钦定名 `test_executive_dashboard_integration.py` 显式偏离） | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**（本 Story 主改动层——epics L2419「应用层覆盖率≥85%」对齐）
- [ ] **领域层 ≥90% 维持**（本 Story 零 domain 改动——既有覆盖率不降）
- [ ] **集成测试覆盖 ≥75%**（epics L2420「集成测试覆盖率≥75%」对齐）
- [ ] **关键路径覆盖率 100%**（derive_health 规则表三分支/四段聚合路径/段级容错路径——Task 2 矩阵承载）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`——基线 756 零新增错误）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`——命令环境拒绝时提交时钩子承载）

#### 测试隔离约束

> ⚠️ **核心原则：** 测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。

**约束规则（本 Story 特有面加粗）：**

| 约束类型 | 规则 |
|---------|------|
| **审计行清理** | **PG 事务回滚式（R1-F9 裁定）**：预置经 `pg_session` fixture 注入的 ContextVar session（set_session）→ save 只 flush 不 commit → teardown `rollback` 整体回收（`test_acceptance_unified_audit_log` :126-140 先例）——**零 DELETE 通道**（RLS DELETE 四态漂移风险整体消解：UPDATE/DELETE 显式 deny+无 FORCE RLS+create_all 兜底不建 RLS+deny 静默 0 行） |
| **快照键清理** | **BLM latest 快照/CP 快照族/恢复记录按 session_id 定向 DEL（`blm-planning-{plan_id}`/`{CHECKPOINT_SESSION_PREFIX}{plan_id}:{cp_no}` 键族/`blm-checkpoint-recovery-{plan_id}` 三键族——uuid plan_id 天然隔离，CP 键族按预置 cp_no 清单删）** |
| **报告行清理** | **PG 事务回滚式（同审计行——R1-F9）**：经 fixture session flush 不 commit，teardown rollback 回收 |
| 事务隔离 | 集成测试 PG 面用 savepoint rollback / 验收面按调用面三分（A 编程面 set_session 回滚式·B/C CLI·并发面 commit+定向 DELETE 行数断言——R2-F3，预置纪律节钦定） |
| 资源唯一性 | 测试数据 UUID plan_id 前缀隔离 |
| 并行隔离 | xdist_group("blm-planning-perf") 整模块串行 + 审计窗口断言只对预置行计数（total 判别锚=**预置前后差值**而非绝对数——并行窗口内他测行不破坏判别；**「独立极窄窗」不可构造已删除**——7 天服务常量+零可选参数自锁 R1-F6；残余并行风险由 xdist 同组串行承载——差值窗内两次查询间的他组写入风险注记） |
| asyncio 上下文 | BDD 步骤 `event_loop.run_until_complete()`；asyncio.Lock 类变量 |
| pytest-asyncio | 禁 scope=module event_loop fixture；BDD 步骤禁 `@pytest.mark.asyncio` |
| 外部客户端 | AsyncMock spec=Protocol 四端口（单测）——验收/集成零 mock 全真实 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate` 全表（定向清理例外仅限自建行）
- ❌ autouse fixture 删除全局匹配资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 验收/集成测试 mock 端口（真实服务四通道）

**验证要求：**
- [ ] 并行测试 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）通过
- [ ] 连续 2 轮全量零失败（6-7 双轮标准）
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过（756 基线零新增）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **编号语义注记（R1 修订）**：Subtask 列引用的 2.2/2.3 等为 **TDD 循环语义位**（循环 A 四段编排/循环 B 规则表/循环 C 容错）——Task 内 Subtask 编号（2.1 红/2.2 绿/2.3 重构/2.4 变异）是 TDD 阶段序，两套编号体系分立防混引；**验收场景统一归 Task 0 编写/Task 7 收尾承载**（矩阵仅列实现 Task 行——除 AC-2 示例行外不再逐 AC 重复列验收场景行，R1 注记）。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 四段聚合 8 键结构 | Task 1 | 1.1-1.3 VO+枚举 | `test_executive_view_vos.py` |
| AC-1 | 四段聚合编排 | Task 2 | 循环 A 服务编排 | `test_executive_view_service.py` |
| AC-1 | 全数据 round-trip | Task 5 | 5.1-5.2 集成场景① | `test_integration_executive_view.py` |
| AC-2 | 三色规则表 | Task 2 | 循环 B derive_health 矩阵 | `test_executive_view_service.py` |
| AC-2 | 三 plan 三色验收 | Task 0 | 0.4 S2 场景 | `test_acceptance_executive_view.py` |
| AC-3 | 审批分布+留痕 | Task 2 | 循环 A 审批段+恢复记录直读 | `test_executive_view_service.py` |
| AC-4 | 审计窗口+样本 | Task 2 | 循环 A 审计段投影 | `test_executive_view_service.py` |
| AC-5 | 段级容错+空态幂等读 | Task 2 | 循环 C 容错矩阵 | `test_executive_view_service.py` |
| AC-5 | 畸形 242 | Task 3 | 3.1 用例守卫 | `test_executive_view_use_case.py` |
| AC-6 | CLI 命令 | Task 3 | 3.2-3.4 CLI+注册 | `test_agent_cli.py` |
| AC-7 | P95<500ms+并发 20 | Task 5 | 5.3-5.4 性能场景 | `test_integration_executive_view.py` |
| 全 AC | 收尾完成清单 | Task 7 | 7.1-7.4 | `test_acceptance_executive_view.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-7（全量——规范冻结是全部实现的前置）

> **目的：** 在进入代码实现前，明确 VO 键契约、端口契约、health 规则表、验收场景与六边形架构边界，并处置 deferred-work 六条锚定义务（四条 6-8 锚定+两条例行顺延）。

- [ ] Subtask 0.1: 冻结六 VO+枚举键契约（Task 0.1 冻结表落 Dev Agent Record——8/8/10/7/8/4 键 + ExecutiveHealth 三值 + 构造守卫清单——实现禁增删键）
- [ ] Subtask 0.2: 冻结 derive_health 规则表（red>green>amber 短路链三条件原文——AC-2 规则 1/2/3 逐字冻结；实现为纯函数 `derive_health(planning, approval, report, build_degraded) -> ExecutiveHealth`——四参显式入参禁读全局）
- [ ] Subtask 0.3: 定义端口契约（ExecutiveViewPort v1.0.0 签名+四依赖注册名+组合根落位邻近锚）+ 契约测试文件骨架
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_executive_view.feature`（12 场景 S1~S12 钉死+epics 架构测试三项落位对账）
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_executive_view.py`（三件套+四通道预置函数+PG 面三分面通道落地（A 编程面 sync 层 set_session 回滚式/B CLI 面 reset_session+commit 式+定向 DELETE 行数断言/C 并发面禁 set_session——R2-F3）+审计窗口差值判别形态）；运行验收测试，确认失败（🔴 红阶段验证——延迟 import ImportError 形态）
- [ ] Subtask 0.6: 定义逐场景红锚符号表（S1~S12 每场景的预期红形态：ImportError/AssertionError/exit code——S7/S9 畸形腿天然绿路由纠正注记——6-6 Task 0.6 先例）
- [ ] Subtask 0.7: deferred-work 六条锚定义务处置落档（四条 6-8 锚定：6.5a-DF1 顺延 Epic 7/6.5a-DF2 顺延/6.7-DF2 重锚 Epic 21-22/data_pipeline 维持——OD-8；两条例行顺延：L170/L17——R1 口径统一）
- [ ] Subtask 0.8: 关键代码锚点行号复核（并行会话提交会使行号漂移——锚点表以 HEAD 为基准实施前复核）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（键契约/规则表/端口/场景钉死/锚定义务）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 应用层端口与六 VO——`ports/executive_view.py`（含 ExecutiveHealth 枚举）

**关联 AC:** AC-1

> **六边形落位：** 全部应用层（`src/application/ports/`）——零 domain 零 infra（OD-12）。

#### TDD 循环 A：六 VO + 枚举

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_executive_view_vos.py`（六 VO 键集 exact set+构造守卫 242 三形态+health 枚举成员/值断言） |
| 🟢 绿 | 实现 `src/application/ports/executive_view.py`（ExecutiveHealth str-Enum+六 frozen dataclass+`__post_init__` 守卫+ExecutiveViewPort Protocol v1.0.0） |
| 🔄 重构 | docstring 全中文 Google 风格+类型注解收口，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 VO 键集/守卫失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现六 VO+枚举+端口最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化 VO 代码（默认值语义注记：无报告/无恢复/无活动各降级键的 None 语义 docstring 化）
- [ ] Subtask 1.4: 🟡 变异 — 键集断言突变实证（删 AuditSection 一键 → exact set 红 → 还原绿；守卫断言突变——去负计数校验 → 构造负值红）

**完成标准/Definition of Done:**
- [ ] 六 VO+枚举+端口实现完成，键契约与 Task 0.1 冻结表逐键一致
- [ ] TDD 循环全部通过（红绿变异三态留痕）
- [ ] 覆盖率：新增文件 ≥95%

---

### Task 2: 应用层视图服务——`ExecutiveViewService` 四段编排 + derive_health

**关联 AC:** AC-1/AC-2/AC-3/AC-4/AC-5

> **四依赖注入：** snapshot_repository/checkpoint_service/report_repository/audit_repo（keyword-only 构造——6-7 服务五依赖同风格）；服务无状态（SINGLETON 并发共享——AC-7 并发约束；R1 订正：原引「AC-11」悬空——本 Story 仅 AC-1~AC-7）。

#### TDD 循环 A：四段聚合编排（Mock 四端口）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_executive_view_service.py` 循环 A 用例（四段聚合：快照 state_data 解析→PlanningSection（**degraded_step_count=len(degraded_steps) 派生断言**）；list_checkpoints→分布计数；恢复记录 load→留痕三键；get_latest_by_plan→ReportSection（**入参 uuid.UUID 转换断言**——R1-F7）；audit search→窗口+样本投影——**Mock spec 形态分述（R1 修订）**：snapshot_repository/report_repository/audit_repo 三者 `AsyncMock(spec=对应Protocol)`（SnapshotRepositoryProtocol/ReportRepositoryProtocol/AuditRepositoryPort）+ checkpoint_service `AsyncMock(spec=CheckpointService)` 具体类（仓内无同名 Port——6-7 `AsyncMock(spec=StrategicArchiveService)` 先例 `test_traceability_tree_service.py:294`）+ `_make_*` 工厂） |
| 🟢 绿 | 实现 `src/application/services/executive_view_service.py` 四段私有方法+`build_executive_view` 编排 |
| 🔄 重构 | 段方法职责收口（每段一方法——`_build_planning/_build_approval/_build_audit/_build_report`） |

#### TDD 循环 B：derive_health 规则表矩阵

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写规则表矩阵用例（三色×数据形态 ≥9 格全枚举：red 触发/不触发边界、green 全条件与每一条件破坏、amber 兜底含空态/build_degraded） |
| 🟢 绿 | 实现 `derive_health` 纯函数（短路链 red→green→amber——Task 0.2 冻结规则逐字） |
| 🔄 重构 | 规则表 docstring 化（三条件原文注释——与 AC-2 逐字对齐） |

#### TDD 循环 C：段级容错与畸形守卫

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写容错矩阵（四源×AsyncMock 抛异常 → 段 degraded=True+其余段正常+build_degraded==True+health 非 green）+空 plan 幂等读+state_data 畸形（缺键/类型错）守卫 |
| 🟢 绿 | 实现段级 try 包裹+畸形守卫降级 |
| 🔄 重构 | 降级 warning 日志统一（`logger.warning` 段名+异常摘要——6-5b 降级日志同款） |

- [ ] Subtask 2.1: 🔴 红 — 循环 A/B/C 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 四段编排+规则函数+容错实现
- [ ] Subtask 2.3: 🔄 重构 — 服务代码优化（投影白名单四键常量化/`BLM_TOTAL_STEPS`/`CHECKPOINT_RECOVERY_SESSION_PREFIX`/`DEFAULT_AUDIT_WINDOW_DAYS` 常量单源引用——禁字面量）
- [ ] Subtask 2.4: 🟡 变异 — 规则表断言突变实证（red 条件 `==` 改 `>=` → 边界格红；green 漏 build_degraded 条件 → 容错格红；投影白名单加一键 → exact set 红）

**完成标准/Definition of Done:**
- [ ] 四段编排+规则表+容错实现完成
- [ ] TDD 循环全部通过（变异锚 ≥5 处：规则表×2/投影×1/容错×1/留痕×1）
- [ ] 覆盖率：服务文件 ≥95%（规则表三分支 100%）

---

### Task 3: 用例 + CLI `executive-view` + 组合根注册

**关联 AC:** AC-5（守卫）/AC-6（CLI）

> **组装层扩展：** `src/entrypoints/agent_cli.py`（argparse 扁平子命令——trace-tree :525 邻位注册）+ `src/composition_root.py`（6-7 :2012-2060 邻位双注册）。

#### TDD 循环 A：用例 + 组合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_executive_view_use_case.py`（UUID 守卫 242 两边界：非 UUID/空串+透传）+ `tests/contracts/test_port_contract_executive_view.py` 五断言族 |
| 🟢 绿 | 实现 `src/application/use_cases/get_executive_view.py`（守卫+透传——`GetTraceabilityTreeUseCase` 直系样板）+ 组合根双注册块（executive_view_service SINGLETON lambda 四依赖 resolve+executive_view_use_case SINGLETON 透传） |
| 🔄 重构 | 注册块注释（SINGLETON 捕获 SCOPED 声明+未来 7-2 REST 面改 SCOPED 触发器注记——6-7 OD-11 同款） |

#### TDD 循环 B：CLI executive-view

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（`_StubExecutiveViewUseCase` 替身+专用 patcher（`_patch_executive_view_entry`——`monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)` + `setattr(agent_cli, "resolve", lambda name: stub)` 形态——**R1-F11 实名订正**：6-7 样板替身实名 `_StubTreeUseCase`（:2830）/patcher 实名 `_patch_trace_tree_entry`（:2845），`_patch_entry`（:63）是 5-1 命令注入器**禁照抄**；trace-tree 块全幅 :2764-3087 含 Parser+Execution 两组——每命令族新建专用 patcher 纪律）：解析/全数据输出行（健康行 GREEN 精确+动态值 in 判定——S8 期望色钦定联动）/空态输出（审计行动态值 in）/242 stderr+exit 1/exit 0） |
| 🟢 绿 | 实现 CLI：`build_parser` 注册（`--plan-id` required）+分发分支+`_run_executive_view_cli` 五步定式（UUID 守卫→ensure_bootstrapped→asyncio.run+resolve→打印→DomainError exit 1）+`_run_executive_view` async 壳（finally `_close_connection_pools`）+`_print_executive_view` 四段打印 |
| 🔄 重构 | 输出行格式统一（「输出即契约」——空态行恒在与三分化对齐 6-7 空树三分化先例） |

- [ ] Subtask 3.1: 🔴 红 — 用例/契约/CLI 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 用例+组合根+CLI 实现
- [ ] Subtask 3.3: 🔄 重构 — CLI 打印面优化
- [ ] Subtask 3.4: 🟡 变异 — CLI 输出断言突变实证（健康行文案改一字 → 精确匹配红；242 stderr 前缀去 `[` → 断言红）

**完成标准/Definition of Done:**
- [ ] 用例+CLI+组合根实现完成（resolve 可达+分发接线）
- [ ] TDD 循环全部通过（变异锚 ≥2 处——R1 订正：与 Lessons「Task3×2」口径一致，原「≥3」为多口径漂移）
- [ ] 覆盖率：用例 100%/CLI 新增面 ≥90%

---

### Task 4: 契约守护与回归面

**关联 AC:** AC-1（端口契约）/OD-2（零事件）/OD-3（零异常）

> **性质说明：** 契约级守护复跑+新增端口契约测试定稿——非功能实现 Task。

- [ ] Subtask 4.1: 端口契约测试五断言族定稿（注册可达/spec 元数据 v1.0.0+SINGLETON+tags/lambda 注入链 getsource 四 resolve 锚/resolve 可达 isinstance/方法签名 keyword-only——`test_port_contract_traceability_tree.py` 逐段对齐；**R1 注记：剔除样板 :55 `assert "BLM_SEARCH_COLLECTION" in source` env 专用锚**——本 Story 零 env 依赖，注入链锚改四依赖注册名）
- [ ] Subtask 4.2: 零事件守护复跑（`tests/contracts/test_event_channel_mapping_pdf_report.py` `_FROZEN_EVENT_COUNT=56` 通过——event_channels.yaml/DEFAULT_MAPPINGS 零 diff 实证）
- [ ] Subtask 4.3: 回归面验证（四目录全量 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance` 零失败——6-6 checkpoint/6-5a 报告既有验收零破坏；agent_cli/composition_root 扩展面的既有单测零适配预期——纯新增子命令/注册块不触既有断言）
- [ ] Subtask 4.4: 三红线 grep 自查（`raise ValueError`/`HTTPException`/`Exception(` 继承——新增面零输出）

**完成标准/Definition of Done:**
- [ ] 契约测试全绿+冻结键数基线零变化
- [ ] 四目录全量零失败

---

### Task 5: 集成测试——真实四源链聚合

**关联 AC:** AC-1/AC-7

> **真实服务 Schema 隔离子模式**（6-x 集成双子模式选型：真实服务面——四源全真实）+ xdist 同组串行。

#### TDD 循环 A：真实链四段聚合 + 性能并发

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_executive_view.py`（场景① 全数据四段 round-trip：真实快照+CP 直写族+恢复记录直写+报告+审计行预置→服务直调值级断言（**含 `get_latest_by_plan` 首消费激活断言**——报告段 report_id（str 化）与预置一致；**total_events 差值形态**）；场景② 空数据 plan 幂等读（审计腿差值）；场景③ 性能 20 轮 P95<500ms（模块级期望常量+sorted 数学口径+预热；C 面禁 set_session——R2-F3）；场景④ 并发 20 路 gather 全成功+两两相等（**排除集六键剔除对照**——R1-F5/R2-F4；禁 set_session——R2-F2e）） |
| 🟢 绿 | 预置/清理通道落地（Redis 三键族直写+定向 DEL；PG 面 `pg_session` 事务回滚式——R1-F9/F11 通道体系）+断言通过 |
| 🔄 重构 | 预置工厂函数收口（`_make_snapshot_state/_make_checkpoint_material/_make_report_row/_make_audit_row` 四工厂——6-5b `_make_material` 先例） |

- [ ] Subtask 5.1: 🔴 红 — 四场景失败测试
- [ ] Subtask 5.2: 🟢 绿 — 预置通道+断言通过
- [ ] Subtask 5.3: 🔄 重构 — 工厂收口+docstring（性能三段口径差声明落模块 docstring——OD-7）
- [ ] Subtask 5.4: 🟡 变异 — 集成断言突变实证（验证型 ≥2 处：报告段 report_id 断言改常量 → 值级红；并发两两相等改单路 → 等价性红——6-7 集成验证型先例）

**完成标准/Definition of Done:**
- [ ] 四场景全绿（真实服务零 mock）
- [ ] 性能 P95 断言通过+口径声明落档
- [ ] 覆盖率：集成新增面 ≥75%

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 六边形架构约束（全 AC 底座）

> **性质说明：** 本 Task 是 **SDD 规范验证测试**——验证代码是否符合架构规则（非功能 TDD）。

#### 架构验证测试实现（四验证器——`test_traceability_tree.py` 样板）

- [ ] Subtask 6.1: 验证器 A 落位守护（交付文件在 application 层/六 VO 定义于 ports 文件非服务本地/服务与用例禁本地 Protocol——AST 扫 ClassDef bases）
- [ ] Subtask 6.2: 验证器 B 零 publish 守护（服务源码 token grep `publish`/`event_publisher` 零出现+AST 零事件构造——pkgutil 强制导入 events 全子模块后 DomainEvent 子类名全集比对 Call 节点）
- [ ] Subtask 6.3: 验证器 C 零 domain/infra 改动+依赖方向（`SERVICE_ALLOWED_PREFIXES` 白名单逐 import startswith 断言+三方禁 import frozenset+本 Story diff 面核验——`git diff --name-only` 对 src/domain|src/infrastructure 零命中守护）
- [ ] Subtask 6.4: 验证器 D CLI 接线（源码含 `add_parser("executive-view"` 精确锚+`args.command == "executive-view"` 分发+`resolve("executive_view_use_case")` 调用锚；**缩进敏感注记**：6-7 样板锚为 `add_parser(\n        "trace-tree"` 8 空格缩进逐字匹配形态（:213）——本 Story 断言字符串与注册代码格式必须完全一致否则恒红）
- [ ] Subtask 6.5: 运行完整测试套件并生成报告（ruff E/I 循环依赖检测——不引入 pylint）
- [ ] Subtask 6.6: 🟡 变异 — 架构断言突变实证（验证器 B token grep 断言：源码临时注入 `publish` token → 测试红 → 还原绿——R1 补齐：Lessons 变异锚 Task 6×1 的正文落位）

**完成标准/Definition of Done:**
- [ ] 四验证器全绿（任何违规即测试失败）
- [ ] 循环依赖检测用 ruff/isort

---

### Task 7: 开发结束验收测试

**关联 AC:** 全 AC 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_executive_view.feature` 收尾场景（S12 完成清单存在性断言） |
| 🟢 绿 | 编写 `test_acceptance_executive_view.py` 收尾 BDD 步骤（`_COMPLETION_SRC_FILES`/`_COMPLETION_TEST_FILES` dict 常量+`path.is_file()` 断言——6-7 S12 形态） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 7.1: 场景 S12 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 7.2: 场景 S12 — 验证四测试目录完成清单的逐项确认
- [ ] Subtask 7.3: 运行开发结束验收测试并确认通过（12/12 场景全绿）
- [ ] Subtask 7.4: 运行 `pytest`（四目录）、`ruff check`、`mypy` 进行收尾校验+deferred-work 台账六条处置注记核对（R2 残留订正）

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] 四测试目录完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构严格分层（本 Story 纯应用层+组装层扩展——零 domain/零 infra/零 migration）；读侧聚合 CQRS 投影形态（聚合视图=多源读模型）
- **设计约束:** 领域层零依赖（本 Story 零 domain 改动天然满足）；读侧 DTO 归应用层（六 VO+枚举 ports 文件承载）；查询不发布事件（architecture.md:1293）
- **接口治理:** 统一端口注册（新端口 v1.0.0 一次到位）、Registry/Resolver、组合根唯一装配、契约优先、禁同义接口重复（聚合视图 vs 单域查询 vs 报告生成——三语义正交）；`get_latest_by_plan` 经既有 `report_repository` 消费不新开端口
- **技术栈:** Python 3.11+ / Redis（快照+恢复记录点查）/ PostgreSQL（strategic_reports 单行查+audit_log 窗口查）/ pytest-bdd；**零 Qdrant/零 MinIO 业务依赖**（装配链依赖除外）
- **关键设计条款:** architecture.md:1293 查询路径零事件（**引用形态注记 R1**：该行是记忆子系统表格「系统记忆查询」单行「不触发压缩，不发布事件」——沿 6-7 先例引用，语义为查询路径零事件先例+六查询型 Story 零事件族实践，非无条件化全仓原则句）；interface-design.md:2005 三视图表「高管视图=仪表盘（3 个关键指标）/审批中心/审计摘要」为**陈旧口径**（FR-UI-07 引用错位+3 指标旧标准——epics L2391 取代注记与 UX v2.1 决策舱为现行权威——本 Story 三要素对应四段聚合形态，显式注记不采旧口径）；prd L121「30 秒理解战略态势」高管价值主张

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | **范围边界——MVP = 四段聚合查询面（ExecutiveViewPort+ExecutiveViewService+GetExecutiveViewUseCase+CLI `executive-view`）。不含**：Web 仪表盘/前端（epics L2391 取代注记钦定——UI 面归 Epic 21 Story 21.1 决策舱；本 Story CLI 呈现即 MVP fallback 形态）/REST 端点（6.1-DF5 第七连 CLI-only 先例；openapi.yaml 零 diff；6.5a-DF1 顺延）/bbox 四元组（6.7-DF2 重锚——Web PDF.js 高亮是真实消费方且在 Epic 21/22 Web 面，本 Story CLI-only 无高亮面）/审批动作（6-6 已交付 recover/apply_correction/confirmed_by——本 Story 只聚合不操作，零写路径）/KPI 财务指标（FR-UI-04 十项经营 KPI 的数据源不在 BLM MVP 依赖链——本 Story「核心经营指标」=规划态势指标聚合口径：进度/降级/审批分布/审计量/报告降级五族；财务 KPI 归 Epic 21+数据接入）/审计分组计数端口（无 GROUP BY 端口实证——读侧消费冻结面纪律；分布分桶 defer Epic 7/21）/`StrategicPlan.PlanStatus` 接线（draft/in_review/approved/archived 骨架与 BLM 运行态零接线现状维持——不碰，接线归 Epic 10 规划文档生命周期立项）/`ReportType` 扩值（exec 视图非报告类型——查询面产物不入报告域枚举）/执行摘要文本面（简化视图是指标态非内容态——conclusions/摘要文本消费归报告与 Epic 21 阅读面） | epics L2391-2432 范围权威+取代注记 + 6.1-DF5 六连 CLI-only 先例 + 6-7 OD-1 边界先例 + YAGNI |
| **OD-2** | **零新增领域事件、零发布、零订阅**（查询型故事第七连）：纯查询聚合面零状态变更——architecture.md:1293 查询零事件先例（引用形态注记见 Dev Notes）+6-4 OD-6/6-5a OD-6/6-6 OD-2/6-7 OD-2 零事件先例族；event_channels.yaml/DEFAULT_MAPPINGS 零 diff；`_FROZEN_EVENT_COUNT=56` 零变化（Task 4.2 守护复跑）；`CorrectionApproved` 无生产者现状维持不激活（Agent B 亲验 src 零生产者——6-6 已裁定不激活，本 Story 不消费该事件）；蓝图无高管视图事件载体；架构验证器 B 零 publish 守护 | 查询语义纯度+先例族+零 yaml/router diff 红利 |
| **OD-3** | **零新增领域异常、零既有异常改动**：242 复用（畸形 plan_id 用例层 UUID 守卫+VO 构造守卫两消费面——`GetTraceabilityTreeUseCase` 直系先例）；空 plan 幂等读不抛（6-4 ChainOfThoughtTraceView/6-6 空清单/6-7 空树三先例族——聚合枚举面语义）；480 **不消费不复现**（`GetBlmPlanningStatusUseCase` load None 抛 480 是单点查询面语义——本 Story 聚合枚举面 load None→planning.available=False 非异常，语义分立钦定——同 6-6 AC-1「空清单不抛 480」分立先例）；段级容错走 degraded 键（非异常路径——6-5b 降级哲学/6-7 节点降级之后的段级版）；planning 480-489/report 490-499/traceability 372-379 三段预留维持零触碰（traceability 段权威源 `_code_ranges.py:61-62`——异常契约节同款依据链注记）。**否决备选**：开 500+ 新码（ExecutiveViewError）——四段降级+242 后无真实 raise 触发面，开码即引入「空 plan 误报」反语义面（6-7 OD-3 否决论证同构） | 异常语义纯度+三先例+空态幂等读语义 |
| **OD-4** | **六 VO 键契约+全仓首个三值分级枚举**（Task 0.1 冻结）：`ExecutiveView` 8 键（含 `build_degraded` 顶层降级哨兵——「拿不到数据不得报绿」读模型诚实性，6-7 哲学延续；`generated_at` 视图生成锚——**ISO 字符串**（`datetime.now(UTC).isoformat()`），审计窗一致性锚）/`PlanningSection` 8/`ApprovalSection` 10/`AuditSection` 7（**无 available 键**——窗口零事件是合法空态非不可得，与三段 available 语义分立）/`ReportSection` 8（`generated_at = StrategicReport.created_at.isoformat()` 派生映射钦定+`report_id = str(...)` str 化——R1-F4；实体 8 字段无 generated_at 名）/`AuditEventSummary` 4——全应用层 frozen dataclass（ports 文件——6-6 CheckpointSummaryView/6-7 五 VO 先例族；**零 domain VO**——OD-12）；`ExecutiveHealth` 三值 str-Enum（green/amber/red——**全仓首个三值分级枚举**：对照先例族全两值（ValidityStatus/staleness/树节点 status）；值域对齐 **UX v2.1 L1250-1252**「绿色（健康）/琥珀（关注）/红色（危险）」与 **prd L1938** 三色状态分类中文语义（R1 订正：三色措辞锚 UX L1250-1252 非引言行 L1246；KPI 十项清单锚 prd L1938——两文件同行号系巧合分置注记）；amber 不用 yellow——**英文词取通行 RAG 用语 amber**（注记：UX RAG 表全中文无英文词、epics L2403 原文用「红/黄/绿」——本 Story 以 prd/UX「琥珀」语义覆盖 epics「黄」用词，权威间冲突显式声明 R1-F18；UX 内 scoreYellow（评分条 0.6-0.75 关注区间）与 scoreAmber（0.4-0.6 警告区间）是另一套色值体系非 RAG 状态色，不受此选词影响））；audit 段 recent_events **投影白名单四键**（action_type/actor/target_resource/timestamp——审计行 `to_dict()` 实为 **15 键**（id/log_id/old_value/new_value/correction_level/checksum/created_at/archived/archived_at/correlation_id/integrity_verified 等内部载荷——R2 订正主会话亲验 models/audit.py:166-182）禁入高管视图——安全面 R1 实证强化）；键恒在纪律（None/0/() 降级值——6-2 R1-6 七键契约同族） | 键恒在纪律+读侧 DTO 层位先例+三色中文语义单源（prd/UX）+审计载荷安全面 |
| **OD-5** | **RAG 三色推导规则表（确定性短路链 red>green>amber，Task 0.2 冻结）**：red=快照在位且已完成步全部降级（`degraded_step_count == completed_steps > 0`——产出可信度危险）；green=**七合取全满足**（R1 订正「八条件」——and 链原子条件数 7，其一含两原子析取：①planning.available ②completed==total ③degraded_step_count==0 ④(approval.total==0 or in_sync==total) ⑤report.available ⑥report.degraded_section_count==0 ⑦build_degraded==False）；amber=其余一切（含未完成/部分降级/sync 异常/无报告/段降级/**空 plan 零数据**——空态 amber 是「无可判绿红的中间态」语义注记非错误态）。实现为纯函数 `derive_health` 四参显式入参（禁读全局/禁散落 if 链——单测矩阵 ≥9 格全枚举承载；主会话 9 格数学推演零矛盾格零不可达格留痕）；**「状态指示器实时更新」前端指标后端不定义**（epics L2415 自注原文——静态查询面无实时语义，Web 联动归 Epic 21） | epics AC「红/黄/绿状态指示器」+ UX RAG 语义映射 + 确定性无参数规则（6-7 OD-5 last-write-wins 全序同款确定性论证）+ 6-7 OD-7 口径差声明纪律 |
| **OD-6** | **审批中心聚合口径——无审批状态机事实下的合成面**：`CheckpointStatus` 仅 4 值（pending/in_progress/completed/recovered——**零审批态**，主会话+Agent B 双亲验 checkpoint.py:52-58）；MVP 审批语义=CheckpointReached.user_feedback_request 事件+execute_recovery(confirmed_by) 留痕+CorrectionRecord（6-6 裁定延续）；本 Story 聚合=**completed 分布+sync_status 三态分布+恢复记录留痕三键**（恢复记录 12 键经 `snapshot_repository.load(CHECKPOINT_RECOVERY_SESSION_PREFIX+plan_id)` 直读——前缀常量单源 :90 禁硬编码）；`user_feedback_request` 事件不消费（outbox 溯源面归 6-6 checkpoint-show——本视图聚合当前态投影非事件回放）；三态分布和==total 完备恒等式断言（缺行/重复计数即红） | CheckpointStatus 零审批态实证 + 6-6 审批语义裁定 + 当前态投影语义 |
| **OD-7** | **性能三段口径声明**：① 视图加载 P95<500ms = `build_executive_view` 服务面窗口（五读串行：**Redis 点查×11**（latest 1 + list_checkpoints 内部 9[恢复记录 join load 1+CP probe 8] + 审批段恢复记录第二次直读 1——R1-F10 订正 ×9 失实；恢复记录同键双载事实：`CheckpointSummaryView` 不含恢复记录内容故审批段直读必要）+PG 单行查+audit 窗口查——20 轮 `sorted[ceil(0.95*n)-1]` 数学口径；**audit total 全行取回实现形态**（impl :159-164）MVP 百行级远小于门禁——审计量万行级触发分组计数端口立项锚 Epic 7/21，docstring 注记）；② 并发 20 = 单一数据源 plan_id×20 路并发读（asyncio.gather+服务无状态约束+两两相等断言——**对照排除集 {generated_at, window_start, window_end} 三键每次调用新生成不入对照**+预置行 timestamp 去并列 R1-F5；读面幂等无副作用，并发安全证明充分；「20 独立 plan」写面变体不采——构造成本与证明目标不成比例，6-5a OD-8 同构裁定）；③ Lighthouse 信息密度/状态指示器实时更新=前端指标后端不定义（epics L2415 自注原文逐字注「实时更新」一项、Lighthouse 为等价推理扩展——R1 注记；Web 面指标归 Epic 21 届时验收）——三口径落验收/集成 docstring | epics L2414-2416 性能行与 CLI 交付面口径对齐（6-3 OD-6/6-6 OD-8/6-7 OD-7 四连口径差声明纪律）+ 构造成本工程评估（6-5a 先例） |
| **OD-8** | **锚定义务六条处置**（Task 0.7 落档——四条 6-8 锚定+两条例行顺延，R1 口径统一；表载六行）：**6.5a-DF1**（REST 导出面 `/plans/{id}/export`）——本 Story CLI-only 第七连，顺延 Epic 7 API 入口（触发条件原文「6-8 高管视图立项或 Epic 7」的后者路径成立——本 Story 立项形态=CLI）；**6.5a-DF2**（L0 同秒撕裂）——触发条件原文「6-8 REST 读侧上线前」，本 Story 无 REST 读侧（CLI 只读不生成——撕裂形态触发面为写侧并发，本 Story 零写路径），触发条件未至顺延（Epic 7 REST 面或 L0 专项）；**6.7-DF2**（bbox 四元组）——三依赖中「Web PDF.js 高亮是真实消费方」在 6-8 CLI-only 形态下不成立（epics L2391 取代注记钦定 UI 归 Epic 21），**重锚 Epic 21/22 Web 前端立项**（deferred-work 注记改锚——树读侧透传已就绪零改动）；**L129 data_pipeline 轨**——本 Story 是读侧聚合非批量报告管线（单次读四源毫秒级无 DAG 编排需求），维持注记顺延（6-11 白标多用户/Epic 7 再评估）；**L170 事件消费基建四件**（顺延 Epic 8——纯查询面零订阅）+**L17 langgraph retry/timeout**（不触发顺延——零图引擎消费）两条例行 | deferred-work L369/L370/L396/L129 原文触发条件逐条对表 + CLI-only 形态裁定连锁 |
| **OD-9** | **测试文件命名（禁故事编号后缀）+ 词族统一 executive_view**：acceptance `test_acceptance_executive_view.feature/.py`；integration `test_integration_executive_view.py`（**对 epics L2429 钦定名 `test_executive_dashboard_integration.py` 的显式偏离**——仓规 test_integration_* 前缀）；unit/architecture `test_executive_view.py`（**对 epics L2428 钦定名 `test_executive_dashboard.py` 的显式偏离**——词族统一 executive_view：dashboard 面向 UI 仪表盘（Epic 21 取代面），view 对齐 CLI 查询形态与既有 trace-tree/checkpoint-list 命名族；epics 措辞 dashboard 是 UI 规划期用词）；`executive` 词族 src+tests 零占用亲验（grep 命中仅无关文案）；CLI 子命令 `executive-view` 无重名亲验（add_parser 族 grep）；service 单测 `test_executive_view_service.py`+VO 单测 `test_executive_view_vos.py`；契约 `test_port_contract_executive_view.py`（五断言族新式） | 记忆「禁止故事编号命名文件」+ 仓规目录前缀惯例 + 词族一致性（epics 钦定名的采纳/偏离逐处声明——6-7 OD-9 同款） |
| **OD-10** | **审计摘要口径——时间窗 total+最近 5 条样本，分布分桶 defer**：窗口默认 7 天（`DEFAULT_AUDIT_WINDOW_DAYS=7` 服务常量——无参数化 YAGNI：epics/UX 无窗口调节需求来源）；样本 limit=5（`AuditSearchCriteria` 实现按 timestamp 降序+total 独立承载——items 只作样本源不作计数源，**禁大 limit 拉全量客户端计数**——total 全行取回形态下双重浪费）；**分布分桶 defer**（无分组计数端口实证：impl grep `func.count|group_by` 零命中、total=全行 len()——伪精确分布禁令：客户端分桶在 total>limit 形态下是采样不是统计，禁做禁声明；分组计数端口+`ix_audit_log_timestamp_action_type` 复合索引利用归 Epic 7/21 立项——索引在位是物理基础非端口面）；窗口内外判别=timestamp 条件边界（start_time 含端点语义以 impl `>=` 实测为准——Task 0.5 复核） | 零端口演进纪律 + 读侧消费冻结面（6-7 先例）+ 伪精确禁令（读模型诚实性族）+ MVP 数据量工程评估 |
| **OD-11** | **组合根双注册+四既有依赖复用+零新仓储成员**：`executive_view_service`（SINGLETON——无状态聚合读；lambda resolve 四既有注册名：`snapshot_repository` :950/`checkpoint_service` :2347/`report_repository` :**3434**（R1 订正——:3433 是 register_port 开行，name= kwarg 在 :3434）/`audit_repo` :487——**三 SCOPED 依赖（snapshot/report/audit 仓库）+一 SINGLETON 依赖（checkpoint_service :2358）的 SINGLETON 捕获声明**（R1-F19 订正「全 SCOPED」失实；CLI 一次性进程+测试双清下无故障面——6-6 checkpoint_service/6-7 traceability_tree 双先例已跑通；未来 7-2 长驻 REST 面改 SCOPED 触发器注记））+`executive_view_use_case`（SINGLETON 透传）；**零新 PG 仓储家族成员**（report_repository 既有组合根会话包装消费——CLI 读场景单行查无会话抖动面：list_checkpoints 内部 Redis probe+恢复记录单键 load 无 PG 依赖，audit search 走 audit_repo 既有包装）；checkpoint_service **具体类注入**（6-7 StrategicArchiveService 具体类注入同款先例——list_checkpoints 是其端口方法族；单测 spec=CheckpointService 具体类——6-7 `AsyncMock(spec=StrategicArchiveService)` 先例）；6-4 CLI session P0 三步排查法核验：lambda 无新 PG 构造/无新仓储成员——无 session_factory 缺口面 | 6-6 OD-12/6-7 OD-11 组合根先例 + 单租户口径（6.1-DF4 MVP 单租户注记延续——审计无 tenant 维度实证） |
| **OD-12** | **准三零 Story：单点 infra 增量+零 migration+零 domain 改动**（R2-F2 重开裁定——原 R1「三零」被 CLI 面通道核查推翻）：六 VO+枚举全应用层（读侧 DTO 归应用层——零 domain 依据）；**唯一 infra 增量 = `audit_repository_impl.py` 的 `search` 增加 session_factory fallback**（~6 行——镜像同文件 `save` 的双模式先例 `:93-107`（get_session 优先+RuntimeError fallback）与 `report_repository.py:153-161` get_latest 同款形态；现状 search 无 ContextVar session 即 RuntimeError——impl `:93-96` 注释自证「其余四方法消费方均为 HTTP 路由，middleware 恒有 session」，本 Story CLI 消费面是 search 的**首个非 HTTP 消费方**，无 fallback 则 CLI 面审计段恒降级——**AC-6 交付物生产可用性缺陷**，R2-F2d 定谳）；无新表无 schema 变更（零 migration）；本 Story 改动面=**11 新建+4 扩展**（R1-F24 订正「六新文件」——src 面 3 新建+3 扩展（agent_cli/composition_root/**audit_repository_impl**）；tests 面 8 新建+1 扩展；另两 md 台账注记——File List/项目结构树三方对账 R2 同步）——最小改动面形态维持，风险集中度最低 | CLI 消费面激活的必要缺口修复（get_latest_by_plan 有 fallback 正是其可被 CLI 消费的前提——同族对称性）+6-7 OD-12 先例的有界突破 |
| **OD-13** | **报告段 UUID 类型边界**（R1 新增裁定）：`get_latest_by_plan(plan_id: uuid.UUID)` 参数为 UUID 类型（`report_repository.py:38` 端口与实现一致；`ReportModel.plan_id` SA_UUID 列直比）——服务四段编排的报告段入口钦定 `uuid.UUID(plan_id)` 显式转换（str→UUID）；畸形 plan_id 已由用例层 242 守卫拦截故转换无抛出面；**禁直传 str**（str 绑定行为依 SA 适配层而定，异常则被段级 try 吞为 report.degraded=True 的误导形态——R1-F7） | 端口签名实证+段级容错的误导形态防御 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── application/
│   ├── ports/executive_view.py              ★ 新建（ExecutiveHealth 枚举+六 VO+ExecutiveViewPort v1.0.0——Task 1）
│   ├── services/executive_view_service.py   ★ 新建（四段编排+derive_health——Task 2）
│   └── use_cases/get_executive_view.py      ★ 新建（UUID 守卫+透传——Task 3）
├── entrypoints/agent_cli.py                 ▲ executive-view 子命令（Task 3——trace-tree :525 邻位）
└── composition_root.py                      ▲ 双注册块（Task 3——:2012-2060 6-7 块邻位）

src/infrastructure/security/audit_repository_impl.py  ▲ search session_factory fallback（Task 2——OD-12 R2 重开唯一 infra 增量 ~6 行）

（src/domain/ 零改动；src/infrastructure/ 单点增量——OD-12 R2 重开：`audit_repository_impl.py` search fallback ~6 行唯一 infra 改动；src/interfaces/ 零改动）

tests/
├── unit/
│   ├── application/test_executive_view_vos.py                ★ 新建（Task 1）
│   ├── application/test_executive_view_service.py            ★ 新建（Task 2——规则表矩阵+容错矩阵）
│   ├── application/use_cases/test_executive_view_use_case.py ★ 新建（Task 3）
│   ├── architecture/test_executive_view.py                   ★ 新建（Task 6——四验证器，OD-9 偏离声明）
│   └── interfaces/cli/test_agent_cli.py                      ▲ executive-view 扩展（Task 3）
├── integration/test_integration_executive_view.py            ★ 新建（Task 5，OD-9）
├── contracts/test_port_contract_executive_view.py            ★ 新建（Task 3/4——五断言族）
└── acceptance/
    ├── test_acceptance_executive_view.feature/.py            ★ 新建（Task 0/7，R6 模板+OD-9）
    └──（6-5a/6-6/6-7 既有测试文件零修改——Task 4 回归验证）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 六条处置注记（Task 0.7/7.4——R2 残留订正）
```

（▲ 修改 / ★ 新建 / = 零改动 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话亲验 2026-11-06+四 Agent 调研交叉；行号基准 HEAD@d3f0d335，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| latest 快照读径 | `src/application/ports/blm_planning.py:63`（`BLM_PLANNING_SESSION_PREFIX`）+ state_data 七键 SSOT :9-15 | session_id=`blm-planning-{plan_id}`；`snapshot_repository.load(session_id)` → `CheckpointSnapshot.state_data` 七键（plan_id/phase/current_step/completed_steps/total_steps/degraded_steps/timeline） |
| 快照仓储端口 | `src/domain/ports/snapshot_repository_protocol.py:14-28` | `save(snapshot: CheckpointSnapshot)`/`load(session_id) -> CheckpointSnapshot \| None`——planning 段数据源 |
| 进度反序列化先例 | `src/application/use_cases/get_blm_planning_status.py:59-88` | state_data→`BlmPlanningStatus` 反序列化样板（6-8 服务解析参考；**其 :55-56 load None 抛 480 是单点面语义——本 Story 不复现**，OD-3） |
| `BLM_TOTAL_STEPS` | `src/domain/value_objects/blm_phases.py:31` | total_steps 期望 8 常量单源（对照断言用——快照值与常量双源一致性注记） |
| `progress_percent` 口径 | `src/domain/value_objects/blm_phases.py:173-176` | 实体 property 实为 `round(x,2)` **返回 float**（R2 订正原「int 复刻」双重失实）——本 Story VO 侧钦定 `int(completed/total*100)` 向下取整（int 0-100），与实体 float 口径**有意分立**（同源分母分子、高管视图整数口径——R1-F3 裁定，AC-1 正文/VC 同源） |
| `list_checkpoints` | `src/application/ports/checkpoint.py:227-243`（实现 `checkpoint_service.py:520-569`） | `list_checkpoints(*, plan_id: str) -> list[CheckpointSummaryView]`——全量 probe CP-1..8+恢复记录 join sync_status 三态（approval 段数据源） |
| `CheckpointSummaryView` | `src/application/ports/checkpoint.py:337-366` | 8 键（checkpoint_no/stage_id/completed/summary/state_version/created_via/timestamp/sync_status）——分布计数派生源（sync_status 值域 in_sync/pending_sync/invalidated） |
| 恢复记录键族 | `src/application/ports/checkpoint.py:90`（`CHECKPOINT_RECOVERY_SESSION_PREFIX`）+ 12 键构造 `checkpoint_service.py:693-714` | `blm-checkpoint-recovery-{plan_id}`——留痕三键源（recovery_mode 小写/confirmed_by/recovered_at）；无记录 load None 合法空态 |
| `get_latest_by_plan` | `src/domain/ports/report_repository.py:38`（实现 `report_repository.py:141-180`——R1 订正方法体延至 :180） | `get_latest_by_plan(plan_id: uuid.UUID) -> StrategicReport \| None`——**参数 UUID 类型（OD-13 转换钦定）**；已实现零消费方，本 Story 首激活（report 段数据源；order_by created_at desc+report_id desc limit 1） |
| `StrategicReport` 实体 | `src/domain/entities/strategic_report.py:32-64` | **8 字段**（report_id: uuid.UUID/plan_id/report_type/file_path/section_count/degraded_section_count/generation_ms/created_at——R1-F4 订正「7 字段」）+构造守卫（report_type 枚举成员/UUID 格式/degraded ≤ section 不变量）——报告段派生源：report_id/report_type/file_path/section_count/degraded_section_count 五键直源 + **generated_at←created_at.isoformat() 派生映射**（generation_ms 是耗时字段非 VO 键） |
| `ReportType` | `src/domain/entities/strategic_report.py:20-29` | 仅 MARKDOWN/PDF 两值——值透传不扩（OD-1） |
| `AuditSearchCriteria` | `src/domain/ports/audit_repository.py:15-37` | frozen：start_time/end_time/actor/action_type/target_resource/offset/limit=20/match_any——窗口查询构造 `AuditSearchCriteria(start_time=..., end_time=..., limit=5)` |
| `AuditRepositoryPort.search` | `src/domain/ports/audit_repository.py:85`（实现 `audit_repository_impl.py:128-181`——R1 订正行号） | `search(criteria) -> AuditSearchResult`（items tuple[dict]+total+offset/limit 分页回显）；**timestamp 降序** :167（**无次级排序键——并列序不稳定，预置行去并列为断言前置** R1-F5）；**total=全行取回 len()** :159-164（OD-7/OD-10 风险注记锚）；limit 透传无 clamp :168；**窗口边界双端闭区间** `>=`/`<=`（:141/:143——R1-F7） |
| `audit_repo` 保存通道 | `src/domain/ports/audit_repository.py:65`（`save(audit_data: dict) -> UUID`） | 验收/集成审计行预置通道——**必填双键 log_id（str UUID）+timestamp（ISO 字符串）**（impl :62-63 下标取值——R1-F1 已实证键面，免 Task 0.5 复核）+可选 actor/action_type/target_resource/old_value/new_value |
| audit 表结构与索引 | `deploy/postgresql/alembic/versions/002_audit_tables.py:33-63` | audit_log 表+六索引（含 `ix_audit_log_timestamp_action_type` 复合——分布计数 defer 的物理基础注记）；RLS **四策略** :103-143（INSERT/SELECT 放行+UPDATE/DELETE 显式 deny，DELETE 仅 USING(false)——R2 订正；**无 FORCE RLS：表 owner 绕过策略**，B/C 面 teardown DELETE 可行性=owner 身态——预置纪律节钦定行数断言防静默假绿） |
| `AuditActionType` | `src/domain/events/audit_events.py:31-75` | **24 值** `域:动作` 枚举（R1-F8 订正——原「18 值」失实；BLM 零使用实证——审计摘要聚合系统级事件非 BLM 流程事件，语义注记） |
| `CheckpointStatus` | `src/domain/entities/checkpoint.py:52-58` | 仅 4 值零审批态——OD-6 聚合口径合成依据 |
| 两值枚举先例族 | `src/domain/ports/archive_repository.py:24-35`（ValidityStatus）等 | 全仓无三值分级枚举——ExecutiveHealth 首个（OD-4 注记对照锚） |
| CLI 注册样板 | `src/entrypoints/agent_cli.py`：trace-tree 注册 :525-550/async 壳 :1350-1359/打印 :1362-1420/五步定式 :1423-1458/分发 :2049-2050 | executive-view 直系样板（argparse 非 typer——模块 docstring :4 钦定零依赖）；空结果双形态另参照 checkpoint-list :1273-1276 |
| CLI 表格先例 | `agent_cli.py:1224-1247` | 纯 stdlib 两遍法动态列宽（本 Story 段内行用键值行形态——表格非必需） |
| 组合根注册样板 | `src/composition_root.py:2012-2060` | 6-7 traceability 双注册块——executive_view 双注册直系复刻（注释块+SINGLETON 捕获 SCOPED 声明+触发器注记） |
| 四依赖注册名 | `composition_root.py`：snapshot_repository :950/checkpoint_service :2347/report_repository :3433/audit_repo :487 | lambda resolve 四目标（主会话亲验） |
| 端口契约测试样板 | `tests/contracts/test_port_contract_traceability_tree.py`（91 行五断言族） | 本 Story 契约测试直系复刻 |
| 架构验证样板 | `tests/unit/architecture/test_traceability_tree.py`（四验证器 A/B/C/D） | 本 Story 架构验证直系复刻 |
| 验收样板 | `tests/acceptance/test_acceptance_traceability_tree.feature/.py`（12 场景+三件套+CLI 直调 :948-967+S12 完成清单） | R6 模板合规+6-7 最新形态 |
| 快照/CP/恢复预置样板 | `tests/acceptance/test_acceptance_checkpoint_recovery.py`（6-6）+ `test_acceptance_markdown_report.py:1106`（`_assemble_archive_only`） | 快照构造参数面/CP 真实通道/恢复留痕构造——Task 0.5 复核 |
| 冻结键数基线 | `tests/contracts/test_event_channel_mapping_pdf_report.py:23-24` | `_FROZEN_EVENT_COUNT=56`——零新增事件守护（Task 4.2） |
| epics Story 6.8 定义 | `_bmad-output/planning-artifacts/epics_v1.0.md:2391-2432` | AC/性能三项/测试文件名钦定源（取代注记 :2391-2393 范围权威） |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-8 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L369（6.5a-DF1·P3） | REST 导出面 `/plans/{id}/export` 无契约与实现（触发=6-8 高管视图立项或 Epic 7 API 入口立项；归宿 Story 6-8/Epic 7） | **顺延 Epic 7**（OD-8）：本 Story CLI-only 第七连（6.1-DF5 先例+openapi.yaml 零 diff 惯例），REST 导出面随 Epic 7 API 入口立项补契约与 report_routes；台账注记「6-8 立项形态=CLI——DF1 未触发」 |
| 2 | L370（6.5a-DF2·P3） | 同 plan_id 同秒并发生成 L0 撕裂文件（触发=6-8 高管视图 REST 读侧上线前必须处置；归宿 Story 6-8 或 L0 专项） | **顺延，触发条件不变**（OD-8）：本 Story 无 REST 读侧且零写路径（CLI 只读聚合——撕裂形态触发面是写侧 report-generate 并发，本 Story 不生成报告）；REST 读侧上线（Epic 7）前处置义务维持；台账注记 |
| 3 | L396（6.7-DF2·P2） | bbox 四元组 ingestion 写入 defer 6-8（三依赖：chunk 级聚合语义+SISYS_LAYOUT_MODEL_PATH 版面模型+Web PDF.js 高亮真实消费方） | **重锚 Epic 21/22 Web 前端立项**（OD-8）：epics L2391 取代注记钦定 6-8 UI 归 Epic 21——本 Story CLI-only 无 Web 高亮面，「Web 消费方」依赖在 6-8 侧不成立；树读侧 `payload.get("bbox")` 透传已就绪（6-7 交付）零改动；deferred-work 主登记位（L371 6.5b-DF1 处置注记）+独立锚双位同步改锚注记 |
| 4 | L129（data_pipeline 轨） | orchestration_service/data_pipeline 轨再锚定条件「批量报告管线需求（6-8 高管视图/6-11 白标多用户场景）或 Epic 7」 | **维持注记顺延**（OD-8）：本 Story 是读侧聚合（单次四源毫秒级查询）非批量报告管线——无 DAG 编排需求（6-5a OD-2 四理由同构第五连）；再锚定条件收敛为 6-11/Epic 7；台账注记 |
| 5 | L170（事件消费基建四件） | 消费基建激活锚位候选「Epic 6 首个事件消费 Story」 | **顺延 Epic 8**：本 Story 纯查询聚合面零事件订阅（七连零消费延续+6-7 双向皆无形态）；register_handler 队列名语义错位未修复前禁止激活约束维持；注记落档 |
| 6 | L17（langgraph retry/timeout） | 锚位候选「checkpoint_table/图引擎字段消费方」 | **不触发，锚位顺延**：本 Story 纯读侧聚合零图引擎/checkpoint_table 消费（五轮同款裁定——5-10/6-1/6-6/6-7 先例延续）；注记落档 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-7 溯源树展示](./6-7-traceability-tree-display.md)（五轮文档审查+五轮代码审查收敛 done）+ 6-6（审批面/CLI 双清）+ 6-5a（报告链/并发采样）

**关键学习/Key Learnings:**
- **Agent 误报主会话复核**（6-5b R1/6-6/6-7 三连教训）：调研结论关键锚点主会话亲验后方可入 Story——本 Story 已亲验 12 组关键事实（epics 取代注记/FR 映射/CheckpointStatus 4 值/AuditSearchCriteria 与 total 全行形态/get_latest_by_plan 零消费方/组合根四注册名/快照端口签名/executive 词族零占用/CLI argparse 非 typer/6-5a 并发先例/marker 注册表/deferred-work 四锚）
- **读侧消费既有冻结面纪律**（6-5b OD-6/6-7 直系）：四源全既有端口消费零演进——get_latest_by_plan 单方法激活、list_checkpoints 透传、search 窗口构造、snapshot load 直读；480 语义分立（单点面抛 vs 聚合面空态）
- **降级哲学段级化**（6-5b 节点→6-7 树形→本 Story 段级）：顶层哨兵 build_degraded+段级 degraded+键恒在降级值——「拿不到数据不得报绿」（health 规则 2 显式含 build_degraded==False）
- **空态幂等读三先例族**（6-4/6-6/6-7）：空 plan 返回非异常态——「不存在」经空视图+available False 承载
- **断言判别力**：exact set 键集（6-6 R1-F10）/三态完备恒等式（和==total）/值级断言防默认值（confirmed_by 可判别值预置）/序断言（recent 降序）
- **CLI 直调双清**（6-6 R3-1 实跑证伪教训）：clear_singleton+clear_scoped 双清+禁二次 bootstrap——S8/S9 钦定
- **性能口径差声明**（四连纪律）：P95/并发/前端指标三段口径落 OD+docstring——「20 独立 plan」写面变体不采（6-5a OD-8 构造成本论证同构）
- **红绿变异全链**：新断言变异实证——本 Story 变异锚钦定 ≥12 处（Task 1×2/Task 2×5/Task 3×2/Task 5×2 验证型/Task 6×1——对齐 6-7 12 锚量级）

**应用到本故事/Applied to This Story:**
- [x] 12 组关键锚点主会话亲验（创建期已执行——锚点表承载）
- [x] 四既有端口零演进+get_latest_by_plan 首激活（OD-1/OD-11）
- [x] 段级容错+顶层哨兵+空态幂等读（AC-5/OD-4）
- [x] exact set/完备恒等式/值级三类断言形态（Task 2 矩阵）
- [x] CLI 双清+禁二次 bootstrap（S8/S9）
- [x] 性能三段口径差声明（OD-7）
- [x] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep

### 其他约束速查

- **风险集中登记**：①口径风险=三色规则表（Task 0.2 冻结唯一版本+单测矩阵全枚举——实现禁散落 if 链）；②契约风险=六 VO 键契约（Task 0.1 冻结——实现禁增删键）；③清理风险=PG 面 B/C 面定向 DELETE（R2-F3 三分面后：A 编程面回滚式零 DELETE 零风险；B/C 面 DELETE 可行性=owner 身态（无 FORCE RLS 表 owner 绕过策略）+**行数断言防静默 0 行假绿**；快照/恢复记录 Redis 三键族定向 DEL 均有 6-x 先例）；④判别风险=审计窗口并行互扰（xdist 同组串行+窗口判别锚=预置行数差值形态+预置行微秒递减 best-effort 占头——R1-F6/R2-F1 残余风险注记）；⑤性能风险=audit total 全行取回（MVP 百行级远小于门禁——万行级触发分组计数端口立项锚 Epic 7/21，docstring 注记）；⑥装配风险=四依赖注册名漂移（lambda resolve 以 grep 为准——Task 0.8 复核）；⑦通道风险=CLI/并发面 session 供给（OD-12 search fallback 新增+reset_session 陷阱+禁 set_session 并发——R2-F2/F3 三个实现陷阱注记在预置纪律节）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore/pylint disable；提交信息禁 AI 署名
- **覆盖率**：整体 ≥80% / application ≥85%（主改动层——epics L2419 对齐）/ domain ≥90% 维持（零改动不降）/ 集成 ≥75%（epics L2420 对齐）
- **验收零 mock 全真实**（pytest.skip() 动态跳过；四通道真实服务——快照/CP/恢复/报告/审计；段级异常容错归单测 AsyncMock——验收面无故障注入通道，6-7 DR1-5 分立同款）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）
- **xdist 串行组**：pytestmark `xdist_group("blm-planning-perf")` 整模块挂法

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（create-story：GLM 调度） |
| **Version** | create-story workflow（bmad-create-story skill v6.3.0） |
| **Execution Date** | 2026-11-06 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.8 定义 L2391-2432） |
| **架构文档** | `docs/architecture/architecture.md` + `docs/architecture/interface-design.md`（三视图表 L2001-2007 陈旧口径注记） |
| **UX 规范** | `_bmad-output/planning-artifacts/ux-design-specification.md`（RAG 三色 L1250-1252/L284——R1 订正行号）+ **prd.md**（KPI 体系 L1938 对照——R1-F17 归档订正：十项 KPI 清单与三色状态分类在 prd 非 UX，正文两处引用本正确） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-7-traceability-tree-display.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（L2391-2432 含取代注记范围收窄）
- [x] 架构约束从 architecture.md/interface-design.md 提取（陈旧口径显式注记）
- [x] 前一个故事学习经验整合（6-7 五轮收敛样板+6-6 审批面+6-5a 报告链）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（六 VO 键契约/规则表/12 场景/Task 0~7 共 8 Task——R1 订正「7 Task」口径）
- [x] 项目结构对齐统一规范（准三零 Story+11 新建+4 扩展——R1-F24 订正口径（原误归 R1-F8——R2 勘误），与 File List/项目结构树三方对账；R2-F2 重开后含 audit_repository_impl 扩展）
- [x] 四 Agent 并行调研（报告链路/Checkpoint 审批/审计与状态先例/测试样板与契约治理）+ 主会话 12 组关键锚点亲验

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-8-executive-simplified-view.md`

**修改的文件/Modified Files（R1 补节——6-7 File List 惯例对齐，三方对账补齐）:**
- `_bmad-output/implementation-artifacts/deferred-work.md` - 六条锚定义务处置注记（Task 0.7/7.4）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 6-8 状态流转与周期注记

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/executive_view.py` - ExecutiveHealth 枚举+六 VO+ExecutiveViewPort
- `src/application/services/executive_view_service.py` - 四段编排+derive_health
- `src/application/use_cases/get_executive_view.py` - 用例（UUID 守卫+透传）
- `src/entrypoints/agent_cli.py` - executive-view 子命令（扩展）
- `src/composition_root.py` - 双注册块（扩展）
- `src/infrastructure/security/audit_repository_impl.py` - search session_factory fallback（扩展——OD-12 R2 重开唯一 infra 增量，CLI 消费面激活缺口修复）
- `tests/unit/application/test_executive_view_vos.py` - VO 单测
- `tests/unit/application/test_executive_view_service.py` - 服务单测（规则表+容错矩阵）
- `tests/unit/application/use_cases/test_executive_view_use_case.py` - 用例单测
- `tests/unit/interfaces/cli/test_agent_cli.py` - CLI 单测（扩展）
- `tests/unit/architecture/test_executive_view.py` - 架构验证（四验证器）
- `tests/integration/test_integration_executive_view.py` - 集成测试（四场景）
- `tests/contracts/test_port_contract_executive_view.py` - 端口契约测试
- `tests/acceptance/test_acceptance_executive_view.feature` - Gherkin 场景（12 场景）
- `tests/acceptance/test_acceptance_executive_view.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.8 |
| **Story Key** | 6-8-executive-simplified-view |
| **File** | `_bmad-output/implementation-artifacts/stories/6-8-executive-simplified-view.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力 |
| **优先级** | P0-8（依赖 6-5a，不依赖 6-5b——epics L2018/L2034 钦定） |
| **覆盖 FR** | 无独立 FR（聚合展示面——同 6-6/6-7 形态；FR-UI-04 归 Epic 21） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7 含 TDD 循环+变异锚）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7+12 场景钉死）
3. [x] Architecture constraints extracted 架构约束已提取（三零 Story+依赖方向矩阵）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（8 学习点+7 应用项）
5. [x] Sprint status synced to `ready-for-dev`
6. [x] OD-1~OD-12 十二裁定落档（范围收窄/零事件/零异常/键契约/三色规则/审批口径/性能三段/锚定义务/命名/审计口径/组合根/三零）
7. [x] deferred-work 六条锚定义务处置预案落档（Task 0.7——四条 6-8 锚定+两条例行顺延，R1 口径统一）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则（R1 起）**：R<轮>-F<序号>；「主会话预登记」为 D1 前通读疑点，与调研/评审发现合并定级。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-F1 | audit save 预置键面漏必填双键——log_id（str UUID）+timestamp（ISO 字符串）下标取值缺则抛，六键清单照写预置即 KeyError | P1 | AC-4 Given/数据面预置④/隔离表/锚点表四处补必填双键（键面实证免 Task 0.5 复核） |
| R1-F2 | snapshot load 捕获一切异常归一 None（redis_snapshot_store.py:179-181）——「load 抛异常=段降级」二分对真实适配器不可实现，AC-5 try 包裹对 snapshot 源真实链路死代码 | P1 | AC-3/AC-5 补真实链路异常面注记（退化语义与 6-6 docstring 对表；段 degraded 异常面真实链路仅 PG 两源可达，snapshot 源容错归单测 AsyncMock 面） |
| R1-F3 | progress_percent 口径三处悬空——实体 property 实为 round(x,2) float，AC-1「int 0-100+同式复刻」不可兼得 | P1 | 钦定 VO 侧 `int(completed/total*100)` 向下取整+与实体 float 口径分立注记（AC-1 正文与 VC 两处） |
| R1-F4 | ReportSection.generated_at 无派生单源（实体 8 字段无此名）+「7 字段」两处失实+report_id UUID 类型 str 化未钦定+generated_at 类型未钦定 | P1 | 钦定 generated_at=created_at.isoformat() 派生映射+report_id=str()+8 字段订正（AC-1/范围边界/OD-4/锚点表四处）+ExecutiveView.generated_at ISO 字符串三键同型 |
| R1-F5 | S11 并发「两两相等」×generated_at 每路新生成恒红——排除集不全（audit.window_start/window_end 亦生成键）+recent_events 并列序不稳定 | P1 | 排除集钦定 {generated_at, window_start, window_end}+预置行 timestamp 去并列+对照形态 dataclasses 序列化（AC-7/OD-7/S11/VC 四处） |
| R1-F6 | 审计段全局窗无 plan 维度——S5/S7/S9「窗口零事件」绝对空断言在共享库下必红（背景行无清理且不同 xdist 组）；「独立极窄窗」不可构造（7 天常量自锁） | P1（近 P0） | 断言体系全面改差值形态（预置前后差值/零新增差值==0）+预置行 timestamp 递增占降序头部+CLI 空态行 in 判定（AC-1 VC/AC-4/AC-5/AC-6/S4/S5/S7/S9/隔离表九处） |
| R1-F7 | get_latest_by_plan(plan_id: uuid.UUID) 参数 UUID 类型——服务 str 直传被段级 try 吞为 degraded 误导形态 | P2 | OD-13 新增裁定：服务报告段入口 uuid.UUID(plan_id) 显式转换（端口契约清单/锚点表/Task 2 循环 A 三处） |
| R1-F8 | AuditActionType 18 值失实（实为 24 值）两处 | P2 | 两处订正 24 值（范围边界表/锚点表） |
| R1-F9 | RLS 表述失实+清理通道漂移——实际四策略（UPDATE/DELETE 显式 deny）+无 FORCE RLS+create_all 兜底不建 RLS+deny 静默 0 行；「定向 DELETE 实测核验」四态漂移不可靠 | P2 | PG 面（审计+报告行）钦定 pg_session 事务回滚式清理（unified_audit_log 先例）——零 DELETE 通道整体消解 RLS 风险（预置纪律/隔离表两处重写） |
| R1-F10 | Redis 点查 ×9 失准（实为 11 次/视图——list_checkpoints 内部 9+审批段恢复记录第二次直读 1+latest 1；恢复记录同键双载事实未声明） | P2 | AC-7/OD-7 两处统一 ×11+分解式+双载必要性声明 |
| R1-F11 | CLI 单测样板三锚失真——_StubTraceTreeUseCase（实名 _StubTreeUseCase:2830）/_patch_entry（:63 是 5-1 注入器，trace-tree 是 _patch_trace_tree_entry:2845）/区间 :2765-2884 截掉执行块 | P2 | Task 3 循环 B 重写样板实名+专用 patcher 形态+全幅区间（:2764-3087） |
| R1-F12 | 预置通道互斥——「经 create_checkpoint 真实通道」（五步编排触 Fake LLM/Embedding/L3/L4）×「装配面零 LLM 零 Embedding/无 minio marker」声明矛盾+五类编排副产物不在 teardown（违键计数净增 0） | P1 | 通道体系修订：CP 快照+恢复记录全直写（R1-F11 同处）——零编排副产物免五类清理面，6-7 归档直写同精神；AC-3 Given/预置纪律②/隔离表重写 |
| R1-F13 | 契约测试复刻须剔除样板 :55 BLM_SEARCH_COLLECTION env 锚（本 Story 零 env） | P3 | Subtask 4.1 补剔除注记（改四依赖注册名锚） |
| R1-F14 | 验收 CLI 直调样板含 6-7 专属 env 桥接腿（:953 setenv） | P3 | 逐场景调用面矩阵已声明零 env 依赖——直调 helper 形态注记「双清+SystemExit 保留、env 腿删」（Subtask 0.5 语境已含） |
| R1-F15 | S2 P-green 构造路径未钉死（in_sync 退化语义未记载——按 6-6 样板恢复 CP-1 会使 P-green 误变 amber 恒红）+S8 期望 health 色未钉死（精确匹配断言不可落笔） | P2 | S2 钦定 P-green=8/8+零 checkpoint（total==0 支路最简）+退化语义注记；S8 钦定期望 GREEN+构造路径（空清单恢复记录→全 in_sync） |
| R1-F16 | AC-6 审计段零事件「最近:」半行形态未钦定（其余三段空态行均有定义） | P2 | 钦定降「最近: 无」+total 为全局窗动态值+S9 审计行 in 判定 |
| R1-F17 | 调试日志表 KPI 体系 L1938 归错文件（十项 KPI 在 prd 非 UX）+三色措辞锚 UX L1246 失准（实 L1250-1252）+「amber 英文用词单源」论据薄弱 | P2 | 调试日志表归档订正（UX+prd 分置）+行号订正+OD-4 论据改写（中文语义单源 prd/UX+amber 通行 RAG 用语+scoreYellow 另套体系注记） |
| R1-F18 | 三色用词权威冲突未点破——epics L2403「红/黄/绿」vs prd/UX「琥珀」（以 UX/prd 覆盖范围权威 epics 原文） | P2 | OD-4 显式冲突声明（epics 用词不采注记） |
| R1-F19 | OD-11「全 SCOPED 的 SINGLETON 捕获」失实——checkpoint_service 实为 SINGLETON（:2358），三 SCOPED+一 SINGLETON 混态 | P2 | OD-11 措辞订正+注释块照抄提醒 |
| R1-F20 | qdrant marker 理由可强化——checkpoint_service→strategic_archive_service→resolve_optional("l3_vector")→QdrantAdapter 构造期即触达（resolve 链传递性） | P3 | pytestmark 注记已含装配链声明（保留）——验收探测步含 Qdrant 形态对齐 6-7（Subtask 0.5 语境） |
| R1-F21 | Status 三口径——L3 backlog vs 完成清单/Next Steps ready-for-dev vs sprint-status 实况（6-7 R2-4 复发） | P2 | L3 改 ready-for-dev |
| R1-F22 | AC-2 VC-2「四段 available 全 False」物理不可写——审计段无 available 键（键契约自反） | P1 | 改「三段 available False+审计空态差值断言」（与 AC-5 正确口径对齐） |
| R1-F23 | 变异锚多口径漂移——Lessons Task3×2 vs Task 3 DoD「≥3 处」；Lessons Task6×1 vs Task 6 正文零变异落位 | P2 | Task 3 DoD 订正 ≥2；Task 6 补 Subtask 6.6 变异（验证器 B token 注入） |
| R1-F24 | 「六新文件」计数失实——File List 14 项=11 新建+3 扩展（src 面 3 新+2 扩），已外溢 sprint-status | P2 | OD-12/完成清单/sprint-status 三处统一「11 新建+3 扩展」 |
| R1-F25 | AC-11 悬空引用（本 Story 仅 AC-1~AC-7——grep 证唯一 AC>7 引用） | P2 | Task 2 引言改 AC-7+订正注记 |
| R1-F26 | 锚定义务「四条/六条」三口径（正文四条 vs 表六行 vs 版本说明六条） | P3 | 五处统一「六条=四条 6-8 锚定+两条例行顺延」 |
| R1-F27 | OD-5「八条件」vs 规则 2 实为 7 合取（其一含两原子析取） | P3 | OD-5 改七合取+逐条枚举 |
| R1-F28 | 构造守卫「三段计数 ≥0」漏 audit.total_events（携带计数段实为四段） | P3 | 改四段计数逐段枚举 |
| R1-F29 | S4「≥6」/AC-3「≥2」范围值×「Task 0.4 钉死确定值禁范围值」自律冲突 | P3 | S4 钉死 6+1（3 种 action_type 各 2 条）；AC-3 钉死 3（2 completed+1 非 completed） |
| R1-F30 | 追溯矩阵仅 AC-2 有验收场景行（不对称）+Subtask 编号与 TDD 循环编号两体系混用 | P3 | 矩阵头加编号语义注记+验收场景统一归 Task 0/7 声明+「循环 A/B/C」语义化 |
| R1-F31 | File List 缺「修改的文件」节——deferred-work/sprint-status 两台账交付无落点（三方对账差一件） | P3 | 补 Modified Files 节 |
| R1-F32 | 六边形架构约束节缺 R1~R4 设计规则落点（6-6/6-7 连续两 Story 钦定件） | P3 | 补 R1~R4 落点五行 |
| R1-F33 | 行号漂移三处——组合根 report_repository name= 在 :3434（:3433 是开括号行）/report 实现方法体延至 :180/audit impl search 实为 :128-181 | P3 | 锚点表/OD-11 三处订正 |
| R1-F34 | degraded_steps 是 list[str]（步骤标识清单）非计数——degraded_step_count 需 len() 派生转换未声明 | P3 | AC-1 planning 段补派生注记+Task 2 循环 A 补断言 |
| R1-F35 | 引用形态四项——architecture.md:1293 语义升格（记忆子系统单行）/DR1-5 借名（6-7 无「故障注入」字样）/traceability 372-379 依据链（设计文档无该段）/L2415 自注扩展适用（Lighthouse 是等价推理） | P3 | 四处补转述/依据链/等价推理注记 |
| R1-F36 | 「7 Task」vs Task 0~7 两口径+审计窗口闭区间（end_time <= 含端点）未注记 | P3 | 完成清单改「Task 0~7 共 8 Task」；OD-10/AC-4 补闭区间 |

**R1 修复对码**：36 项全部落码于本 v1.1.0 修订（P1×8 簇：F1/F2/F3/F4/F5/F6/F12/F22——F6 近 P0；P2×13；P3×15）；证伪留痕：S1 快照直写 484 触发疑点（checkpoint_no 空不触发——亲验 :78-84）/P-green 必须先恢复疑点（None→全量 in_sync 退化语义实证 :526/:535）/execute_recovery 改写规划快照疑点（只写恢复记录）/checkpoint 通道自动写 audit 疑点（StrategicArchiveService 无 audit 依赖+6-6 audit_service=None）/limit clamp 疑点（透传实证）/12 场景计数疑点（求和恰 12）/SCOPED 并发缺陷疑点（session_factory 每调用独立会话）——7 条推演排除防重推。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-F1 | S4/S1「预置行 timestamp=now()+i 秒未来偏移」×「窗口边界闭区间 end_time<=generated_at」组合互拆——预置行全部出窗，差值==6/recent 值级/last_event_at 三连红（R1-F6×R1-F7 互拆） | P1（近 P0） | 改递减微秒偏移（now−i×100µs：窗内 ✓+微秒去并列 ✓+新于背景行 best-effort 占头）；「背景免疫」措辞降格「同组串行 best-effort+残余风险注记」（AC-4 Given/Then/S4/隔离表） |
| R2-F2 | **CLI 面（S8/S9）审计段恒降级**——audit search 无 ContextVar session 即 RuntimeError（fallback 仅 save 有，impl :93-96 自证「其余四方法消费方均为 HTTP 路由」）→ S8 GREEN 不可达+AC-5 build_degraded==False 被 CLI 腿打破+**AC-6 交付物生产可用性缺陷**（CLI 高管速览审计行恒 0/无）；report fallback 读不到回滚式未 commit 行 | P1 | **OD-12 重开裁定**：准三零 Story——search 增加 session_factory fallback ~6 行（唯一 infra 增量，镜像 save 双模式 :93-107+get_latest :153-161 先例——「CLI 消费面激活的必要缺口修复」）；CLI 面 B 组通道钦定 reset_session+commit 式预置+定向 DELETE 行数断言 |
| R2-F3 | **S11 20 路 gather × 共享回滚 session**——AsyncSession 单连接非并发安全（asyncpg「another operation in progress」）；CLI asyncio.run 新循环继承 ContextVar session 触发「Future attached to a different loop」 | P1 | **PG 面三分面钦定**：A 编程面（S1~S7）sync 层 set_session 回滚式 / B CLI 面（S8/S9）reset_session+commit+定向 DELETE / C 并发·性能面（S10/S11）禁 set_session+每路 fallback 独立会话+commit+定向 DELETE（预置纪律/调用面矩阵/隔离表/风险⑦联动） |
| R2-F4 | S11 排除集（三键）漏 audit.total_events/recent_events/last_event_at——他 xdist 组 gather 期间 commit 审计行仅进晚于该行各路窗口→两两相等 flake | P1 偏 P2 | 排除集扩为六键；audit 段并发对照仅 degraded/window_days 两稳定键（AC-7/OD-7/S11/VC/Task 5 五处联动） |
| R2-F5 | set_session 必须 sync 层调用（async fixture 内 set 不外泄到 run_until_complete task）——unified_audit_log 先例行号指偏（:126-140 实为 pg_session，set_session 在 :143-149） | P2 | 预置纪律 A 面补实现陷阱注记+先例行号订正 |
| R2-F6 | R1 修复残留 8 处——L321 事务隔离行/L380 Subtask 0.5/L661 锚点表/L712 风险③「定向 DELETE/RLS 实测核验」旧指令 ×4 与回滚式裁定同文件矛盾；L651 progress_percent 锚点表「int 复刻同式」双重失实（词序倒置躲过词根 grep）；L109 Given 措辞/L572·L638「四条」×2 | P2 | 八处全部订正（残留清单逐位落码——R2 回归核查实证「修复的声称联动位」漏网形态） |
| R2-F7 | to_dict() 实为 **15 键**（R1 曾误 14 键——Agent B 漏数 correction_level，主会话亲验 models/audit.py:166-182 定谳）；「6 条预置取 5」取舍未钦定；CP 快照空 checkpoint_no 注记未在②面重申；「最近: 无」半行形态验收面不可达（共享库背景行恒在）未注记 | P3 | 15 键两处订正；取舍钦定「丢弃最旧 1 条——断言序列=预置 i=1..5 行降序」；②面重申空 checkpoint_no；「最近: 无」注记仅单测 stub 面可达 |
| R2-F8 | 修复编号错标 2 处（「六新文件→11+3」订正误归 R1-F8——实为 R1-F24） | P3 | 完成清单勘误（OD-12 重写时已正） |

**R2 修复对码**：8 项（P1×4 簇/P2×2/P3×2）全部落码于 v1.2.0；证伪留痕（Agent F）：search 走 session_factory 疑点（实走 ContextVar :48-50）/SCOPED 实例绑独立会话疑点（session 每调用动态取）/close_pools 破坏 teardown 疑点（peek 单例不影响自建 fixture）×11 算术疑点（1+9+1 实证）/恢复记录 12 键三面不一致疑点（逐键一致）/三场景构造互斥疑点（独立 plan 隔离）/load 归一注记失实疑点（实证在位）/三前缀键冲突疑点（互异实证）——8 条推演排除防重推。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 待代码审查周期
**审查模式:** 待定（full：Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] （待代码审查周期填写）

#### 已修复 Patch

- [ ] （待代码审查周期填写）

#### 已推迟 Defer

- [ ] （待代码审查周期填写）

---

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行文档审查修订循环（参照 6-6/6-7 五轮形态）
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.2.0
**创建日期/Created:** 2026-11-06
**最后更新/Last Updated:** 2026-11-06
**更新说明/Description:**
- v1.2.0: 文档审查 Round 2 修订（回归核查+组合交互面双 Agent——R1 修复的传播完备性 28/36 落地+8 处残留清扫；**三处组合互拆定谳**：① S4 未来秒级 timestamp×闭区间出窗（P1 近 P0）→ 递减微秒偏移体系；② **CLI 面审计段恒降级**（search 无 fallback——AC-6 生产可用性缺陷）→ **OD-12 重开为准三零 Story**（search session_factory fallback 唯一 infra 增量 ~6 行）；③ S11 共享回滚 session×20 路并发（AsyncSession 非并发安全）→ **PG 面三分面通道体系**（A 编程面回滚式/B CLI 面 reset+commit+DELETE 行数断言/C 并发面禁 set_session 每路独立会话）；S11 排除集三键→六键（audit 值级三键 flake 消解）；to_dict 15 键订正/取舍钦定/编号错标勘误——8 项修复（P1×4 簇/P2×2/P3×2）+8 条证伪留痕）
- v1.1.0: 文档审查 Round 1 修订（四视角调研 Agent【四源数据面/审计面与清理通道/CLI 与测试样板/文档权威面】+双评审员【场景三轴推演/一致性交叉】+主会话预登记 12 疑点与亲验 6 项——36 项修复落码：P1×8 簇/P2×13/P3×15；核心裁定：**审计段断言体系改差值形态**（全局窗无 plan 维度，绝对空断言共享库下必红——R1-F6 近 P0）/**预置通道体系修订**（CP 快照+恢复记录全直写+PG 面事务回滚式清理——消解「零 LLM 声明×create_checkpoint 重通道」互斥与五类编排副产物+RLS 四态漂移风险——R1-F12/F9）/progress_percent 钦定 int 截断与实体 float 口径分立（R1-F3）/ReportSection.generated_at=created_at.isoformat() 派生映射+8 字段订正（R1-F4）/S11 并发对照排除集三键（R1-F5）/snapshot load 异常归一 None 退化语义注记（R1-F2）/OD-13 新增（get_latest_by_plan UUID 转换钦定）；事实订正：Redis 点查 ×11/AuditActionType 24 值/组合根 :3434/CLI 样板实名/三色措辞锚 UX L1250-1252/锚定义务六条口径；结构补齐：R1~R4 落点节/Modified Files 节/Task 6.6 变异/矩阵编号语义注记；Status 三口径统一 ready-for-dev）
- v1.0.0: 创建故事文件（四 Agent 并行调研【报告链路/Checkpoint 审批/审计与状态先例/测试样板与契约治理】+主会话亲验 12 组关键锚点；OD-1~OD-12 十二裁定：范围收窄 CLI-only 第七连（epics L2391 取代注记钦定——UI 归 Epic 21，本 Story 后端聚合口径+CLI 呈现）/零新增事件（查询型第七连+_FROZEN_EVENT_COUNT=56 零变化）/零新增异常（242 复用+空态幂等读+480 语义分立）/六 VO+ExecutiveHealth 三值枚举（全仓首个三值分级枚举——8/8/10/7/8/4 键契约）/RAG 三色确定性短路规则表（red>green>amber）/审批中心聚合口径（CheckpointStatus 零审批态实证——completed+sync 三态分布+恢复留痕三键合成）/性能三段口径（P95<500ms 服务面+并发 20 单数据源读面+前端指标后端不定义）/锚定义务四条处置（6.5a-DF1 顺延 Epic 7/6.5a-DF2 触发未至顺延/6.7-DF2 重锚 Epic 21-22/data_pipeline 维持）/命名词族 executive_view（对 epics dashboard 钦定名显式偏离）/审计摘要口径（7 天窗+total+5 条样本——分布分桶 defer 伪精确禁令）/组合根双注册+四既有依赖复用+get_latest_by_plan 首激活/三零 Story（零 infra/零 migration/零 domain）；12 验收场景钉死（S1~S12——epics 架构测试三项落位对账+性能三项口径声明在位）；deferred-work 六条处置预案（含 L170/L17 顺延）
