# Story 6-10: 顾问视图（三段聚合查询——多项目概况/品牌配置状态/白标导出概况 + CLI `consultant-view`）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行文档审查修订循环（参照 6-7/6-8/6-9 五轮形态）+ 人工按 story-template 合规清单核对后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 专业顾问（咨询/投资/银行）,
**I want** 系统输出顾问视图——单命令聚合多项目概况（跨 plan 归档活动清单+每项目最新报告交付物状态）、品牌模板配置状态（V1 恒系统默认态——配置实现归 Story 6-11）与白标导出概况（可交付项目计数+最新 PDF 定位）三段,
**So that** 高效交付客户项目并保证品牌一致性——单命令掌握「有哪些客户项目在进行、各项目交付物状态如何、白标 PDF 导出到哪了」（epics L2478-2480 用户价值；L2484-2488 AC 三要素）。

### 业务价值

- **Epic 6 价值组「战略规划与审批能力」的顾问交付面**：生成侧（6-1~6-5b）、审批侧（6-6）、溯源面（6-7）、高管速览面（6-8）、分析师作业面（6-9）已 done，本 Story 交付 **P1-10 顾问视图**——面向交付者的多项目/品牌/导出三合一入口（epics L2020 依赖列钦定「依赖 Story 6.5b」——PDF 报告生成已 done）
- **范围权威（epics L656 + UX 三页面驾驶舱格局）**：Story 6.10 是「UX 三页面驾驶舱（顾问）」的后端承载位——**Web/前端交互面归 Epic 21/22**（注记：Epic 21 九 Story 与 Epic 22 八 Story 均无顾问专属 Web Story，22.8 角色自适应的角色枚举为高管/分析师/企业战略人员**不含顾问**——顾问 Web 面届时归 22.8 扩展或后续 Web Story 立项，本 Story 不预建）；本 Story 交付其**后端聚合口径与 CLI 呈现**（Epic 6 第九个 CLI-only Story——6.1-DF5 八连先例延续；6-8/6-9「CLI 呈现即 MVP fallback 形态」直系复刻）
- **FR Coverage Map 无独立 FR（同 6-6/6-7/6-8/6-9 形态第五连）**：白标 REST 面 `POST /reports/whitelabel` 归 FR-SP-16（P2）→ Epic 20 Story 20.4（epics L600 映射行）；品牌模板配置实现（Logo/配色/字体+模板复用持久化）归 Story 6.11「白标报告基础」P0-11（epics L2021/L2518-2561——依赖 6.5a，**backlog 未实施**）；三页面架构+角色自适应归 FR-IF-05 → Story 22.8（prd L2199-2204——角色枚举无顾问）；本 Story 是**聚合展示面**（查询型故事先例族第九连）
- **激活既有跨 plan 查询面的首个视图服务消费**：`ArchiveRepositoryPort.find(ArchiveQuery(plan_id=None))`（组合根 `archive_repository` :2315 SCOPED v1.1.0——现成跨 plan 全量清单查询；既有生产码消费方全景：REST `/api/v1/archive/entries` 与 `/plans/{plan_id}` 两端点均经 `strategic_archive_service.query_archive` :315-325 中继、StalenessWeightService 兜底链 :95-96、SummaryGenerationService 陈旧标记兜底链 :441-446[同形态 archive_ids 批量]——find 签名零变化零影响面）+ `ReportRepositoryProtocol.get_latest_by_plan`（组合根 `report_repository` :3513 SCOPED——6-8 首消费激活后本 Story 第二消费方，循环消费形态）——两既有通道首次跨 plan 单点聚合（「首个」限定口径：plan_id=None 全量清单形态的**视图服务**消费——归档域既有消费均为单 plan 锚定或 archive_ids 批量形态）
- **Epic 6 内部顺序**：6-9（done，分析师作业面）→ **6-10（本 Story，顾问交付面）** → 6-11 白标报告基础（backlog）

### 范围边界（出处逐行声明）

| 面（出处） | 已交付（禁重复造轮） | 6-10 增量（本 Story） |
|---|---|---|
| 报告生成面（6-5a/6-5b） | `ReportGenerationServicePort.generate_markdown_report`（`ports/report_generation.py:69`）+ `PdfReportGenerationServicePort.generate_pdf_report`（`ports/pdf_report.py:118`）；L2 `strategic_reports` 表（017 migration：report_id PK/plan_id 索引/report_type/file_path/section 双计数/generation_ms/metadata JSONB/created_at）；`ReportGenerated` 事件（payload 无 plan_id——`workflow_events.py:57-72`）；CLI `report-generate --plan-id --format {markdown,pdf}`（agent_cli :342-362） | **只查询不生成**：导出段消费 `get_latest_by_plan` 循环派生（报告元数据投影）；生成链零触碰（导出执行归 report-generate 既有入口——「指向既有命令」操作提示形态，6-8 :1579 同款） |
| 跨 plan 清单查询面（3-10/6-4） | `ArchiveRepositoryPort.find(ArchiveQuery)`（`ports/archive_repository.py:123-131`）——`plan_id=None` 即全量跨 plan（软删过滤+archived_at 降序+offset/limit 1-1000 默认 20，PG `_do_find` :233-250）；`ArchiveQuery` 14 键值对象（字段区 :62-75）；`strategic_archives` 表（008 migration，plan_id 列 nullable 无外键——None 行预置可行） | **视图服务首个全量清单消费**：多项目段 = find 全量→distinct plan_id 分组→每 plan 归档计数+最新活动时间；`plan_id=None` 行剔除（`StrategicArchive.plan_id: UUID \| None` 可空——不变量仅 ASSUMPTION/DECISION/DEVIATION 强制非空亲验 :48-53，EVIDENCE_PACKAGE 思维链归档恒带 plan_id 但防御性剔除注记） |
| 单 plan 视图族（6-8/6-9） | `ExecutiveViewPort` 四段（planning/approval/audit/report——`ReportSection` 8 键单 plan 最新报告概况 :152-167）+ `AnalystViewPort` 三段（toolbox/progress/traceability）+ CLI `executive-view`/`analyst-view`（均 `--plan-id` 必填） | **不重复**：单 plan 报告概况/审批/审计/进度/溯源面零消费（6-8/6-9 已交付）；本 Story 是**跨 plan 全局面**（视图族中首个零 plan_id 输入命令——语义正当性：多项目管理面板本义跨 plan）；6-8 `ReportSection`（单 plan 可得性）与 6-10 `ExportSection`（跨 plan 派生计数+全局最新 PDF 定位）**语义正交非演进**（OD-7 分立声明） |
| 品牌模板配置实现（6-11 归属） | **未立项**（6-11 backlog——Logo/配色/字体上传保存、预设 3 套配色/2 种字体、模板复用持久化、reportlab Image 位图渲染、`report-generate` 品牌参数扩展全部归 6-11——6-5b L31/L682/L684 显式移交注记在档；`PdfRendererPort.render` 单参零品牌扩展点亲验 :96；reportlab 硬编码 STSong-Light `_FONT_NAME` :60+灰系颜色 :305/:313/:374-375——词族 brand/white_label/logo src+tests+configs 零命中亲验） | **不实现配置**：品牌段 = 配置状态展示面（V1 恒「未配置（系统默认）」静态段——零 IO）；configured 键是 6-11 对接锚（届时端口演进 v1.1.0 读配置面——docstring 触发器注记）；`BrandSection` 值级断言=V1 时点事实断言（6-11 实施后 configured 可 True——预期演进信号，非 flake） |
| 白标 REST 导出面（Epic 20） | `POST /reports/whitelabel` 归 FR-SP-16 P2 → Epic 20 Story 20.4（epics L600/L714）——未立项 | **不做**（CLI-only 第九连+REST 白标 API 归 Epic 20——openapi.yaml 零 diff） |
| 多租户存储隔离（1-11/后续） | 1-11 交付**合规面**（敏感检测/数据驻留/跨境审批——`test_acceptance_data_sovereignty_isolation.py`）；Schema per Tenant 仅架构文档设计（arch-appendix :1297-1362 伪码，`SET search_path` src 零命中亲验）；strategic_reports/strategic_archives **均无 tenant 列**；MVP 单租户 `MVP_TENANT_ID`（`pdf_report.py:54-58` docstring「多租户归后续 Story」先例） | **展示口径非实现**：测试面为共享库单 schema（R1 亲验——验收/集成均无 per-test schema 切换；预置行以 plan_id TestTenant UUID 前缀区分）；验收 S11 断言=正向可见性（预置 plan 可见+值级直推——「零跨漏」排他断言共享单 schema 下不可判别[OD-13]，隔离语义本体归 1-11 合规面测试承载）；「Schema per Tenant 完整实现归租户管理后续 Story」docstring+OD-1 注记 |
| 批量报告管线（L129 锚） | `orchestration_service/data_pipeline` 轨休眠——再锚定条件原文含「6-11 白标多用户场景或 Epic 7」（deferred-work L129） | **显式不做批量导出**（OD-8 第五轮同构裁定+本 Story 主动收窄声明：白标导出=单 plan 单次生成归 report-generate 既有入口；多项目批量导出管线不立项——L129 锚位维持「6-11/Epic 7 再锚定」不变） |
| 进度可视化（6-8/6-9 既有） | planning 快照 latest 读（`blm-planning-{plan_id}` TTL 86400——**不可作持久清单源**：过期即失）；`SnapshotRepositoryProtocol` 仅 save/load/delete 无 scan（亲验 :20/:28/:39——多项目面板快照扫描方案不可行） | **项目行不含进度列**（OD-5 裁定：进度可视化归 6-9 analyst-view 单 plan 面两视图正交；快照 TTL 24h 过期→「进度未知」列语义不稳，不入面板） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 三段聚合数据结构（ConsultantView 键契约）

**Given** 测试库已预置跨 plan 数据（≥2 个 plan 的思维链归档行族——6-4/6-7 形态 EVIDENCE_PACKAGE 行带 plan_id；其中 plan-A 另有 markdown+pdf 两报告行、plan-B 仅 markdown 报告行——L2 `strategic_reports` 行直写预置；预置时间戳用**未来偏移构造**（基准 now+微秒递减——find 无时间窗过滤无出窗风险，与 6-8 审计窗「未来偏移出窗」教训场景分立注记；保证预置行恒新于共享库背景行→行序/latest_pdf 断言免疫背景行），品牌配置面未实施（6-11 backlog——系统默认态是唯一可达形态）
**When** 顾问请求顾问视图（编程面 `ConsultantViewService.build_consultant_view()` 或 CLI `consultant-view`——**零输入参数**，全局多项目面板）
**Then** 返回 `ConsultantView` **5 键** frozen VO（`generated_at`/`build_degraded`/`projects`/`brand`/`export`——全键契约见 Task 0.1 冻结表；**顶层无 plan_id 键**——全局视图零输入 OD-1 钦定，与 6-8 `ExecutiveView` 8 键/6-9 `AnalystView` 6 键的分立点），三段各自键恒在：
- **多项目段** `ProjectsSection` **4 键**：`available`（==plan_count>0——有规划活动项目在位）/`degraded`（段级降级哨兵——find 异常或循环读异常两源）/`plan_count`（distinct plan_id 计数）/`projects`（tuple[`ProjectSummary` **6 键**：plan_id[str 化钦定——实体 UUID→str，6-8 report_id 同款]/archive_count[该 plan 归档行数]/latest_activity_at[该 plan 最大 archived_at ISO]/latest_report_type[None|\"markdown\"|\"pdf\"——get_latest_by_plan 循环派生]/latest_report_at/latest_degraded_section_count]——**行序钦定 latest_activity_at 降序、tie-break plan_id 字典序升序**（确定性排序——顾问作业面「最新活动优先」语义））
- **品牌段** `BrandSection` **5 键**：`degraded`（恒 False——零 IO 静态段无降级面）/`configured`（恒 False V1——6-11 对接锚）/`logo_status`（恒「未配置（系统默认）」）/`color_scheme_status`（同上）/`font_status`（恒「STSong-Light（内置）」——与渲染器 `_FONT_NAME` 冻结字体事实单源对齐注记：**字面量+docstring 锚承载，禁 import infra**（application 层不得依赖 `src.infrastructure.reporting`——依赖方向矩阵；reportlab_pdf_renderer.py:60 锚注记））
- **导出段** `ExportSection` **7 键**：`available`（==plans_with_reports>0）/`degraded`（与 projects 段同源联动——派生源受损即降级）/`plans_with_reports`（latest_report_type 非 None 的 plan 数）/`plans_with_latest_pdf`（latest_report_type==\"pdf\" 的 plan 数——**「最新报告类型分布」口径**非「历史曾生成计数」：先生成 PDF 后又生成 markdown 的 plan，其 latest=markdown 不入 pdf 计数——latest 遮蔽语义诚实注记 OD-7）/`latest_pdf_plan_id`/`latest_pdf_object_key`（file_path 直传——PDF 行即 L4 对象键 `reports/{plan_id}/{report_id}.pdf`，`PDF_OBJECT_KEY_TEMPLATE` :79 单源）/`latest_pdf_generated_at`（三键 None 态=零 PDF 最新报告）

**And** 顶层 `generated_at` 为 ISO 字符串（`datetime.now(UTC).isoformat()`——服务入口**单时间锚**取一次 now，6-8/6-9 单锚派生直系第三连；三段值全派生自既有单源（归档行/报告行）——**服务不新算任何跨源复合指标**（导出段计数=项目段循环结果的纯投影，单源纪律 OD-7））

**验证标准/Validation Criteria:**
- [ ] 全数据场景：5 键 exact set（`{f.name for f in fields(ConsultantView)}`）+ 三段嵌套键集各自 exact set + 值级断言（**membership 全含口径 OD-13**：预置双 plan ∈ 清单+各恰一行——背景行免疫；两预置行 archive_count 与预置直推/latest_pdf 定位三键与预置行直推[预置 pdf 行 created_at 未来偏移→恒为全库最新]）
- [ ] `ProjectSummary` 6 键 exact set + `BrandSection` 5 键 exact set + `ExportSection` 7 键 exact set（投影白名单防扩散）
- [ ] 计数恒等式（判别锚）：`plans_with_reports == sum(1 for p in projects.projects if p.latest_report_type is not None)` + `plans_with_latest_pdf == sum(1 for p in projects.projects if p.latest_report_type == "pdf")` + `plan_count == len(projects.projects)`（恒等式是 VO 内部不变量——对任意行集成立，背景行免疫，验收面直接断言）
- [ ] brand 恒值事实断言（V1 时点——configured is False + 三 status 值级；6-11 演进信号注记落 docstring）

### AC-2: 多项目段聚合（跨 plan 清单+每 plan 交付物概况）

**Given** 三个 plan 预置形态：**plan-A**（3 条归档行+markdown+pdf 报告行——pdf created_at 最新）、**plan-B**（2 条归档行+仅 markdown 报告行）、**plan-C**（1 条归档行+零报告行——「有活动无交付物」形态）；另预置 1 条 `plan_id=None` 归档行（EVIDENCE_PACKAGE 可空防御形态）；**预置归档行 archived_at 与报告行 created_at 均用未来偏移构造**（基准 now 起微秒级递减分配——三 plan 的 latest_activity_at 相互判别+恒新于共享库背景行——背景行免疫 OD-13；无时间窗过滤无 6-8 出窗风险）
**When** 构建顾问视图
**Then** 项目段与归档单源一致（**背景行免疫口径 OD-13 membership 全含**）：预置三 plan ∈ 清单 plan 集且各恰一行（**None 行剔除判别含于行级值**：`plan_id=None` 行不计入任何预置 plan 的 archive_count——三行 archive_count 精确值 3/2/1 即判别[错计入则红]；防御性注记：当前写侧思维链归档恒带 plan_id，None 仅可达于手工修数/未来写入方，读侧守卫廉价且诚实）；`projects` 行序——**预置三 plan 恒占清单首三**（预置行 archived_at 未来偏移恒新于背景行）且首三内部序==plan-A→plan-B→plan-C（降序判别——plan-A 最新偏移）；每预置行 `archive_count` 与预置行数直推（3/2/1）、`latest_activity_at`==该 plan 归档行最大 archived_at、plan-A/plan-B `latest_report_type`==预置最新报告类型、**plan-C 三报告键全 None**（「有活动无交付物」诚实态——无报告非降级）
**And** 查询口径钦定：`ArchiveQuery(plan_id=None, limit=1000)`（**上限声明**：单租户 MVP 量级归档行数 << 1000；超限截断是 MVP 外量级——docstring 风险注记「归档行超千级触发 SQL 化清单端口立项锚 Epic 7/21」；默认 limit 20 显式覆写 1000——find 默认 20 行会截断多项目面板，**禁用默认值**是本段正确性前提）
**And** 报告概况循环口径：逐 plan `get_latest_by_plan(uuid.UUID(plan_id))`（N+1 点查形态——MVP plan 数个位数量级 <50ms 实测预期；**风险注记**：plan 数百级时 N+1 成热点，「DISTINCT plan_id+JOIN LATERAL 单查询化」立项锚 Epic 7/21，docstring 承载）；单 plan 点查异常→该行报告列 None+**双段 degraded=True**（保守诚实——「拿不到」与「没有」经段哨兵区分，行内 None 同形但段降级标记在场）

**验证标准/Validation Criteria:**
- [ ] 三 plan 清单值级断言（membership 全含三 plan ∈ 清单+各恰一行/预置行占首三+内部降序/逐行 archive_count/latest_activity_at/latest_report_type——背景行免疫 OD-13）
- [ ] None 行剔除断言（预置 None 行后三 plan 行 archive_count 仍精确 3/2/1——None 行不计入任何 plan 计数，防御格）
- [ ] plan-C 零报告行报告三键 None（有活动无交付物形态）
- [ ] 排序判别锚（预置三行未来偏移内部递减≥微秒量级——降序+首三占位断言可判别；同时间戳 tie-break plan_id 字典序单测承载）
- [ ] limit=1000 覆写断言（服务源码 getsource 锚或行为断言——默认 20 截断形态红）

### AC-3: 品牌段（V1 恒系统默认态——6-11 对接锚）

**Given** 品牌配置面未实施（6-11 backlog——词族 brand/white_label/logo src+tests+configs 零命中亲验；`PdfRendererPort.render` 单参零品牌参数亲验 :96）
**When** 构建顾问视图
**Then** 品牌段恒系统默认态：`configured is False` + `logo_status == "未配置（系统默认）"` + `color_scheme_status == "未配置（系统默认）"` + `font_status == "STSong-Light（内置）"` + `degraded is False`——**零 IO 静态段**（三段中唯一无数据源段——与 6-9 toolbox 段「静态真源恒有数据」镜像对称：本段是「静态默认态恒在」；空态/降级全场景值恒不变——S5 空态断言可精确落笔）
**And** 值级断言语义=「V1 交付时点品牌面未配置事实」（6-11 实施后 configured 可 True、logo_status 可为已配置值——断言红是**预期演进信号**非 flake，防面板静默漂移；同 6-9 23 工具事实断言语义）；`font_status` 值与渲染器冻结字体 `_FONT_NAME = "STSong-Light"`（reportlab_pdf_renderer.py:60）事实对齐——**字面量承载禁 import**（依赖方向：application 禁 import infrastructure——`SERVICE_ALLOWED_PREFIXES` 白名单外；锚注记落 VO docstring）

**验证标准/Validation Criteria:**
- [ ] 品牌段 5 键 exact set + 五值级恒等断言（configured/degraded False+三 status 字面量精确）
- [ ] V1 事实断言语义注记落 VO docstring（6-11 演进信号+禁 import infra 锚注记）
- [ ] 空态场景品牌段值恒不变断言（S5 承载——空态与全数据品牌段逐值相等）

### AC-4: 导出段（跨 plan 报告派生+最新 PDF 定位）

**Given** AC-2 预置形态（plan-A markdown+pdf——pdf 最新；plan-B 仅 markdown；plan-C 零报告；预置报告行 created_at 未来偏移恒新于背景行——latest_pdf 三键免疫背景行 OD-13）
**When** 构建顾问视图
**Then** 导出段为项目段循环结果的**纯投影派生**（零新读——服务仅两读源 archives+reports，导出段不发起第三次 IO）：预置面断言——plan-A/plan-B 行 `latest_report_type` 非None/plan-A 行 =="pdf"（**行级断言按预置 plan 定位——背景行免疫**）；`latest_pdf_plan_id == 预置 plan-A`/`latest_pdf_object_key == 预置 pdf 行 file_path`（L4 对象键 `reports/{plan_id}/{report_id}.pdf` 直传）/`latest_pdf_generated_at == 预置 pdf 行 created_at ISO`（三键绝对断言成立依据：预置 pdf 行未来偏移恒为全库最新；**多 plan latest 均 pdf 时按口径三选择**[latest_report_at 最大者+tie-break plan_id 升序——Task 0.2 冻结]）；计数恒等式（AC-1 承载——VO 内部不变量背景行免疫）
**And** 计数口径注记（OD-7）：`plans_with_latest_pdf` 是「**最新**报告为 pdf 的 plan 数」——历史曾生成 PDF 但 latest 被 markdown 遮蔽的 plan 不计入（latest 遮蔽语义：`get_latest_by_plan` created_at 降序首行唯一——「当前交付物形态」非「累计交付史」；呈现语义=顾问面板关注「现在可交付什么」）
**And** 零 PDF 形态（全 plan latest 均 markdown 或零报告）→ `available` 判定钦定：`plans_with_reports>0` 即 True（**有报告可导出**——markdown 亦是可交付物；latest_pdf 三键 None+`plans_with_latest_pdf==0` 承载「无 PDF」诚实态——available 不随 PDF 缺席降 False，「可导出」与「已导出 PDF」分立）
**And** 操作提示归 CLI 承载（AC-6）——导出执行归 `report-generate --plan-id <uuid> --format pdf` 既有入口（6-5b OD-11 单入口钦定；本 Story 零导出执行面）

**验证标准/Validation Criteria:**
- [ ] 派生行级断言（预置 A/B 行 latest_report_type 非 None/A 行=="pdf"——按预置 plan 定位行断言，背景行免疫）+ 两计数恒等式（AC-1 承载——VO 内部不变量）
- [ ] latest_pdf 三键值级与预置 pdf 行直推（plan_id/object_key/generated_at——未来偏移保全库最新）
- [ ] 零 PDF 形态断言（仅 markdown 预置 → latest_pdf 三键 None——对照腿；「available True」按行级口径：预置 plan 行 latest_report_type=="markdown" 非 None 且非 "pdf"）
- [ ] latest 遮蔽口径单测格（构造 plan 先 pdf 后 markdown 两行 → latest=markdown → plans_with_latest_pdf 不含该 plan——判别计数面错接）

### AC-5: 段级容错与空态幂等读

**Given** 空租户形态（零归档行零报告行——**brand 段静态恒在**，与数据面正交：空租户的品牌段照常返回默认态五键）或某数据源查询异常（异常形态归单测承载——验收面真实服务无故障注入通道，6-8 AC-5/6-9 AC-5 分立裁定直系第三连）
**When** 构建顾问视图
**Then** **段级独立容错**（6-8/6-9 段级容错直系延续+本 Story 双段联动特有面）：`archive find` 异常 → projects 段 `degraded=True`（plan_count=0+projects 空 tuple+available=False——段值降默认）+ **export 段连带 `degraded=True`**（派生源受损——available=False+计数 0+latest_pdf 三键 None）+ brand 段照常默认态 + 视图整体不抛 + 顶层 `build_degraded=True`；循环内 `get_latest_by_plan` 单 plan 异常 → 该行报告列三键 None + **双段 degraded=True**（保守诚实裁定——行级 None 与「无报告」同形，段哨兵是唯一区分面；其余 plan 行照常聚合）；brand 段无降级面（零 IO 恒稳）
**And** 空态幂等读（**断言承载分立 OD-13**：`projects.available==False+plan_count==0+空 tuple/export.available==False+计数 0` 的**绝对空态断言归单测承载**——共享测试库存在背景行（实测 3 条归档行/1 个背景 plan），「零行全库」物理不可构造，单测 find 返回空列表形态承载空态值语义[Task 2 循环 C 空态格]+CLI stub 直构空 VO 格承载空态输出语义；**验收/集成面承载核心四断言**——零预置下 视图正常返回 5 键 + **brand 段完整默认态五键**（三段中唯一恒数据段——6-9 toolbox 段镜像，背景行免疫——零 IO 恒在）+ `build_degraded==False`（「没有数据」非「拿不到数据」——6-4/6-6/6-7/6-8/6-9 五连空态分立语义第六连）+ **不抛异常**（五先例族）——6-8 审计窗差值断言体系直系适配[背景行无清理且跨 xdist 组的先例教训]）
**And** **零输入零守卫面注记**（OD-3）：本 Story 无 plan_id 输入——6-8/6-9 的畸形 plan_id 242 守卫面**语义自然缺席**（零输入即零畸形面，非缺失；用例为 `execute()` 无参透传——242 无触发面是设计结果；验收无 242 场景属正确形态，与 6-8/6-9 的 S7 分立声明）

**验证标准/Validation Criteria:**
- [ ] 验收空态幂等读断言（5 键恒在+build_degraded False+brand 完整默认态五键+不抛——核心四断言口径 OD-13）
- [ ] 绝对空态断言归单测（find 返回空列表 → available False+plan_count 0+空 tuple+计数 0+latest_pdf 三键 None——Task 2 循环 C 空态格承载值语义）
- [ ] find 异常双段降级归单测（AsyncMock 抛异常 → 双段 degraded+brand 照常+不抛——Task 2 容错矩阵）
- [ ] 循环单 plan 异常归单测（AsyncMock side_effect 定向抛 → 该行报告列 None+双段 degraded+其余行照常）
- [ ] 验收面零 mock 红线（段级容错三格全归单测承载——验收场景不设异常注入）

### AC-6: CLI `consultant-view` 命令（顾问交付入口——零参数全局视图）

**Given** 全数据在位（AC-2 形态）
**When** 执行 `sisys-agent consultant-view`（**零参数——零 add_argument（parser 无任何参数定义）**：16 命令族实测形态为 6 个 `--plan-id` 必填读命令[chain-query/checkpoint-list/checkpoint-show/trace-tree/executive-view/analyst-view]+7 个写命令[instantiate/run-task/blm-plan/report-generate/checkpoint-create/checkpoint-recover/set-isolation]+2 个 `--agent-id` 锚定读命令（load-profile :255/isolation-status :582）+1 个可选参数全局检索命令（isolation-logs :623——六参数全 required=False 可裸调但带可选过滤/分页面；6+7+2+1=16 加法闭合）；consultant-view 是**首个零 add_argument 命令**（参数面真空——与 isolation-logs 的「可裸调但带可选过滤面」分立：全局面板无过滤/分页需求来源，YAGNI，6-8/6-9 零可选参数裁定直系）
**Then** 三段结构化输出（纯标准库 print——「输出即契约」6-8/6-9 同哲学；无 JSON 输出模式——仓内 CLI 全 stdlib print 惯例）：首行 `顾问视图（全局多项目面板）` + 三段各以 `── {段名} ──` 分隔行承载：
- 多项目概况：`项目: 共 {plan_count} 个` + 逐项目行（`  {plan_id} | 归档: {n} | 最新活动: {YYYY-MM-DD HH:MM}` + `    最新报告: {type}（{ts}，降级小节 {n}）` 两行形态——信息密度呈现形态拆两行[非源码行宽约束——输出行 ~78 字符本不超 128]；无报告行降 `    最新报告: 无`；**段降级两形态分立（OD-12 呈现面对齐——R1-F1）**：find 级[degraded+空清单——服务段值降默认]降 `项目清单获取失败` 单行；循环级[degraded+清单保留——行报告列 None]照常呈现清单[行内 `    最新报告: 无`+首行「（部分数据降级）」标记承载降级信号]）
- 品牌配置：`品牌模板: 未配置（系统默认） | Logo: 默认 | 配色: 默认 | 字体: STSong-Light（内置）` + 恒在注记行 `提示: 品牌模板配置归 Story 6-11（白标报告基础）`（6-11 对接锚的呈现面——提示行恒在非降级行）
- 白标导出：`可交付: {plans_with_reports} 项目有报告 | 最新 PDF: {n} 项目` + 最新 PDF 定位行（`  最新 PDF: {plan_id}` + `  对象键: {object_key}`——latest_pdf_plan_id None 时降 `  最新 PDF: 无`）+ 恒在提示行 `提示: 执行 report-generate --plan-id <uuid> --format pdf 生成白标 PDF`（指向既有命令——6-8 :1579「可先执行 report-generate」/6-9「执行 trace-tree」同款形态第三连）
**And** 退出语义：正常 exit 0（含空态——空态是正常态非错误）；**验收输出断言口径（OD-13 背景行免疫）**：CLI 输出含全库行（全局视图本义），验收断言用**包含断言**（预置三 plan 的逐行输出在 stdout 中+品牌段两行+导出段行+提示行逐字 in 断言）与**格式断言**（`项目: 共 ` 前缀+` 个` 后缀模式），**不断言完整输出集/总行数**（背景行计入输出）；「空态输出=`项目: 共 0 个` 后无行」的**精确空态输出断言归 CLI 单测 stub 直构空 VO 格承载**（S8 验收面断言格式模式+brand 两行恒在+提示行恒在+exit 0）；`build_degraded` 时首行后追加 `（部分数据降级）`标记（6-8/6-9 降级标记直系——单测 stub 格承载）；DomainError 兜底 stderr `[EXCEPTION_{code}]` exit 1（防御性兜底——段级容错下不可达，兜底结构照设[名保留注记：五步定式名沿先例、实态四步去守卫步——Task 3 docstring 差异注记]）
**And** 本 Story CLI 面无角色门槛（「顾问」是 UX 语义——查询命令族先例均无角色检查；RBAC 门槛归 7-2 REST 入口立项时评估——6-8/6-9 同款注记第三连）；**零参数与 D6-9-R1-1 命令族关系注记**：本命令无 `--plan-id` 输入面——**不入**「`*--plan-id` 命令族非 canonical UUID 观察项」波及面（deferred-work L409——该锚处置见 OD-8）

**验证标准/Validation Criteria:**
- [ ] 全数据输出断言双承载：CLI 单测 stub 格**精确断言**（三段分隔行+项目段首行+两 plan 四行两行/项目形态+品牌两行+导出三行+提示行——stub 数据无背景行可精确）；验收场景**包含断言**（预置三 plan 逐行输出+品牌两行+导出段行+提示行 in stdout+exit 0——CLI in-process 直调，6-9 S8/S9 双清先例；背景行免疫 OD-13）
- [ ] 空态输出断言双承载：CLI 单测 stub 空 VO 格**精确断言**（`项目: 共 0 个` 后无行+品牌两行恒在+导出空态行）；验收场景**格式断言**（`项目: 共 ` 模式+brand 两行+提示行恒在+exit 0）
- [ ] 降级标记形态（build_degraded=True → 首行含「（部分数据降级）」——stub 直构降级 VO 单测格；**段降级两形态分立（R1-F1）**：find 级格[空清单+degraded]断言 `项目清单获取失败` 单行+导出段值级降 0；循环级格[清单保留+degraded]断言清单行在场+行内「最新报告: 无」+不降获取失败单行）
- [ ] 零参数断言（parser 无任何 add_argument 调用——getsource 切块断言零参数面；`sisys-agent consultant-view --plan-id x` → argparse unrecognized exit 2 格）

### AC-7: 性能与并发（三段口径——OD-8）

**Given** 全数据在位（AC-2 形态，服务面已预热）
**When** 采样计时（20 轮——`sorted(durations)[ceil(0.95*n)-1]` 数学口径，6-3/6-6/6-7/6-8/6-9 五连同款公式与模块级期望常量独立构造）
**Then** **视图加载 P95<800ms**（epics L2498「视图加载延迟 P95<800ms」的聚合服务面等价口径）：口径 = `build_consultant_view` 服务面窗口（两读源：archive find 1 次 PG 查询[1000 行内聚合在应用层]+plan_count 次 get_latest_by_plan 点查[plan_id 索引命中——017 migration ix_strategic_reports_plan_id]——20 轮数学口径；**N+1 风险注记**：plan 数百级时点查链成热点，「DISTINCT+JOIN LATERAL 单查询化」立项锚 Epic 7/21，落 docstring；**find 截断风险注记**：归档行超 1000 截断——SQL 化清单端口同锚）
**And** **并发 20 路读（对照口径重定义 OD-13——预置子集过滤对照）**：**20 路并发读**（asyncio.gather 20 路 `build_consultant_view()`——读面幂等无副作用；**服务无状态约束**——SINGLETON 实例并发共享禁持可变实例态——6-8/6-9 同款第三连；20 路全部成功不抛；**对照形态=预置 plan 子集过滤后逐路相等**：asdict 序列化后 projects 列表按预置 plan_id 集合 membership 过滤+brand 段逐路相等+每路 build_degraded False——**全集相等断言禁用**：全局无窗查询在并发窗内受其他 worker 写入抖动[6-8 R2-F2「排除集不可收缩」教训同源——收缩为只排 generated_at 假红；且本 Story projects/export 全排除后判别力归零，故改预置子集稳定对照——过滤后子集含背景行免疫的全量键]；**禁 set_session**——每路独立会话天然 per-task 隔离，6-8 R2-F3 C 面纪律直系第三连；Task 5.4 并发变异锚的篡改位同步钦定为「篡改一路的预置 plan 行派生值」（不进过滤对照则变异不红））
**And** **「白标报告导出时间<1 分钟」与「多租户隔离测试 100% 通过」为既有面/继承面口径差声明**：导出时间<1min = `report-generate --format pdf` 既有入口的生成性能面（6-5b 性能验收已承载——本 Story 导出段是**导出状态展示面**非导出执行面，同 6-9「溯源跳转<300ms 归 6-7 既有面」裁定形态第三连）；多租户隔离 100% = 继承口径（1-11 合规面测试承载；**S11 断言口径 OD-13**：共享测试库单 schema 下「零跨漏」排他断言不可判别——S11 改**正向可见性断言**（预置 plan 在面板可见+值级直推+membership 全含）+隔离继承口径声明 docstring 注记；「Schema per Tenant 完整实现」归租户管理后续 Story——OD-1 注记）——两项口径差声明落验收/集成 docstring；**性能场景背景量级敏感处置**（S9/集成③）：性能窗口含全库 distinct plan 数 N 次点查（N 含背景 plan）——预置前动态清点背景 distinct plan 数，超阈值（50——N+1 风险注记同源门限）`pytest.skip()`（验收动态跳过先例形态）+docstring 声明环境量级敏感性

**验证标准/Validation Criteria:**
- [ ] 20 轮采样 P95<800ms（预检服务可达+预热含首轮+背景 distinct plan 数>50 时 pytest.skip 动态跳过——环境量级敏感 OD-13）
- [ ] 并发 20 路全部成功+预置子集过滤后逐路相等（membership 过滤 projects+brand 段+build_degraded——全集相等禁用 OD-13；6-8 R2-F2 排除集不可收缩教训直系适配）
- [ ] 口径差声明落 docstring（导出<1min 归 6-5b 既有面+隔离 100% 继承口径+S11 正向可见性口径——模块 docstring 承载）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **零新增领域事件、零发布、零订阅**（OD-2——查询型故事第九连：纯查询聚合面零状态变更；6-4/6-5a/6-5b/6-6/6-7/6-8/6-9 七连零事件先例族延续[七员枚举+本 Story=第九连——连号按查询型 Story 定位计]；`event_channels.yaml`/`DEFAULT_MAPPINGS` 零 diff；`_FROZEN_EVENT_COUNT=56` 零变化——Task 4.2 守护复跑；蓝图无顾问视图事件载体）

#### 数据模型 (Data Models)

- [x] 五 VO 全应用层 `src/application/ports/consultant_view.py`（frozen dataclass——6-6 CheckpointSummaryView/6-7 五 VO/6-8 七 VO/6-9 七 VO 先例族；零 domain VO——OD-11）：`ConsultantView` 5 键/`ProjectsSection` 4/`ProjectSummary` 6/`BrandSection` 5/`ExportSection` 7（Task 0.1 冻结表——实现禁增删键）
- [x] 品牌段默认值两常量钦定应用层 ports 文件（OD-6——品牌面恰两常量[logo/color 共用 BRAND_STATUS_UNCONFIGURED]：`BRAND_STATUS_UNCONFIGURED="未配置（系统默认）"`/`BRAND_FONT_STATUS="STSong-Light（内置）"`——字面量单源+reportlab :60 锚注记；6-11 对接触发器 docstring 注记）
- [x] 面板查询常量：`PANEL_ARCHIVE_LIMIT=1000`（ArchiveQuery limit 覆写单源——默认 20 截断防御）

#### 统一端口定义注册与管理 (Port Contract)

- [x] `ConsultantViewPort`（应用层 `src/application/ports/consultant_view.py`，`@runtime_checkable Protocol` v1.0.0）：`async def build_consultant_view(self) -> ConsultantView`（**零参数**——全局视图 OD-1；ExecutiveViewPort/AnalystViewPort keyword-only plan_id 形态的分立点）
- [x] 端口注册中心/解析器/契约门禁零改动（既有机制消费）；组合根双注册（OD-10）：`consultant_view_service`（SINGLETON）+ `consultant_view_use_case`（SINGLETON）——落位 analyst_view 块后（:2139 邻位）
- [x] 两依赖复用既有注册名零新端口：`archive_repository`（:2315 SCOPED v1.1.0）/`report_repository`（:3513 SCOPED）——**两 SCOPED 无混态**（6-8 三 SCOPED+一 SINGLETON/6-9 两 SINGLETON+一 SCOPED 混态后的最简形态）
- [x] 端口契约测试：`tests/contracts/test_port_contract_consultant_view.py`（五断言族——`test_port_contract_analyst_view.py` 直系复刻）
- [x] 禁止在服务文件中本地定义 Protocol / Port 抽象

#### 端口契约清单执行约束（强制）

- [x] 本清单是唯一事实源；禁止新增未登记端口（本 Story 零新底层端口——仅一个视图聚合端口）；禁止语义重复端口（consultant_view 跨 plan 交付面 vs executive_view 单 plan 速览面 vs analyst_view 单 plan 作业面——三语义正交：交付者全局/高管单点/分析师单点）
- [x] 端口具备唯一名称、版本 v1.0.0、owner、tags；未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

- [x] **零新增领域异常、零既有异常改动**（OD-3）：**本 Story 无 242 消费面**（零输入零畸形面——6-8/6-9 连续两 Story 242 UUID 守卫后本 Story 语义自然缺席，用例 `execute()` 无参透传无守卫；空态幂等读不抛——五先例族第六连）；report 段 490-493 已用/494-499 预留**不占**（490 ReportGenerationError 是生成面语义——本 Story 零生成零触碰；`_code_ranges.py` report 域引用口径统一 :199-212（R4 勘误——原 :192-212 含 planning 段首行））；report/archive 两域零异常改动；planning 480-489/report 490-499/traceability 372-379 三段预留维持零触碰（无 view 码段亲验维持）。**否决备选**：开新码（ConsultantViewError）——段级容错+空态幂等读后无真实 raise 触发面，开码即引入「空租户误报」反语义面（6-7/6-8/6-9 OD-3 否决论证同构第四连）

#### API 契约 (API Contract)

- [x] **零 REST 端点**（CLI-only 第九连——openapi.yaml 零 diff；6.1-DF5 八连先例；epics L2512-2513 钦定测试文件为 CLI/编程面测试非 API 契约；白标 REST 面 `/reports/whitelabel` 归 Epic 20 Story 20.4——epics L600）

#### 六边形架构约束（必须遵守）

- [x] **R1~R4 设计规则落点**：R1 领域层基础端口零改动（本 Story 零 domain——消费的 ArchiveRepositoryPort/ReportRepositoryProtocol 均既有 R1 端口）；R2 应用层具体端口 `ConsultantViewPort` 组合注入两既有 R1 端口（archive_repository+report_repository——ExecutiveViewPort 四依赖/AnalystViewPort 三依赖同构延续）；R3 基础设施层零改动（OD-11 三零）；R4 接口层零改动（CLI 归 entrypoints 组装层——D1 方案 A 既有格局）
- [x] 依赖方向矩阵合规：application→domain（ports 消费）/entrypoints→application（CLI resolve）；domain/interfaces/infrastructure 零触碰

#### 验收标准 Gherkin (Acceptance Tests)

- [x] 功能测试文件：`tests/acceptance/test_acceptance_consultant_view.feature`（12 场景——R6 模板 `test_acceptance_postgresql_relational_layer.feature` 形态：AC 横幅分节+zh-CN 步骤）
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_consultant_view.py`（6-9 R6 合规最新形态：三件套/双清/context dict/CLI 直调/完成清单）
- [x] 所有场景覆盖（Happy Path + Edge Cases）；Edge Cases 含空态幂等读+None 行剔除防御形态（异常路径归单测分立——AC-5 裁定）
- [x] **BDD 步骤实现约束**：步骤函数 `event_loop.run_until_complete()`；同一中文文本双装饰器支持（仓内先例锚 `test_acceptance_autonomous_invocation_route.py:505-506`——R1 注记：6-9 验收步骤文本全唯一无此形态）；禁 `@pytest.mark.asyncio`

**Task 0 完成标志：**
- [x] 规范项全部定义完毕（键契约/排序与派生口径/端口/12 场景钉死/锚定义务处置）
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [x] **链路接线断言清单**：组合根 `register_port` 双注册 resolve 可达（契约测试承载）/零事件零中间件接线面（查询型 Story——接线断言归架构验证器 D CLI 锚）

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
- ❌ 先写代码后写测试 / 测试集中到最后 Task / 跳过红阶段 / 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 恒真断言）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 五 VO+常量 | 键集 exact set+构造守卫+品牌默认值常量 | `tests/unit/application/test_consultant_view_vos.py` | Task 1 |
| **TDD 单元测试** | ConsultantViewService | 三段编排/排序与派生矩阵/容错矩阵 | `tests/unit/application/test_consultant_view_service.py` | Task 2 |
| **TDD 单元测试** | GetConsultantViewUseCase | 零参透传（无守卫面注记） | `tests/unit/application/use_cases/test_consultant_view_use_case.py` | Task 3 |
| **TDD 单元测试** | CLI consultant-view | 解析/输出/退出码 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_consultant_view.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数 | `test_acceptance_consultant_view.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | 完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约/registry/resolver | 注册/元数据/注入链/可达/签名 | `tests/contracts/test_port_contract_consultant_view.py` | Task 3/4 |
| **SDD 架构验证** | 六边形架构约束 | 落位/零事件/依赖方向/CLI 接线 | `tests/unit/architecture/test_consultant_view.py` | Task 6 |
| **集成测试** | 真实双源链 | 跨 plan 聚合 round-trip+性能并发 | `tests/integration/test_integration_consultant_view.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（基线 93%——6-9 定稿轮实测；本 Story 纯新增不降基线）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（主改动层——epics L2503 对齐；新增文件目标 ≥95%）- **P1 阻断门禁**
- [ ] domain ≥90% 维持（零改动不降）/ 集成 ≥75%（epics L2504 对齐）

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/` + `ruff format --check`——6-9 R1-F2 教训：多行推导式压行，提交前 format 亲验）
- [ ] **MyPy 类型检查通过**（基线 mypy 762 文件零错误——6-9 定稿轮；零新增错误）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`——提交时钩子承载）
- [ ] **三红线 grep 自查零输出**（`raise ValueError`/手动 HTTPException/继承内置 Exception）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**本 Story 关键隔离面**（6-8/6-9 隔离纪律直系延续+本 Story 特有面）：

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **品牌段隔离** | 静态默认态零预置零清理（零 IO——段测试无资源生命周期） | 无风险面（本 Story 设计收益） |
| **PG 归档行隔离** | 归档行 repo.save 直写+定向清理（repo.save 通道 R5 改钦——archived_at 实体构造可编程；`_teardown_tree_assets` 定向清理直系样板 6-7；plan_id TestTenant UUID 前缀天然隔离） | 跨 plan 污染 |
| **PG 报告行隔离** | 报告行直写+定向 DELETE 行数断言（report_repository.save 直写通道；report_id uuid4 唯一——幂等锚 report_id 语义天然隔离） | 行冲突 |
| **PG 面三分面** | A 编程面 sync 层 set_session 回滚式 / B CLI 面 clear_session+commit 式+定向 DELETE 行数断言 / C 并发·性能面禁 set_session+每路独立会话+commit+定向 DELETE（6-8 R2-F3/6-9 直系第三连） | 并发炸/假绿 |
| **BDD async** | 步骤函数禁 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()` | context 数据丢失 |
| **CLI 直调双清** | clear_singleton()+clear_scoped() 双清+禁二次 bootstrap（6-6 R3-1 实跑证伪教训钦定第三连） | 假数据/ConflictError |
| **xdist 串行组** | pytestmark `xdist_group("blm-planning-perf")` 整模块挂法（6-7/6-8/6-9 同组） | 并行互扰 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（回滚式/定向 DELETE 行数断言）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio` / asyncio.run()
- ❌ 验收面 mock（真实服务双通道——PG 归档行+报告行；段级容错归单测 AsyncMock——6-8 DR1-5/6-9 分立同款）

**验证要求：**
- [ ] 四目录全量 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）零失败×2 轮
- [ ] `poetry run ruff check` + `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **编号语义注记**（6-8/6-9 同款）：Subtask 列引用的循环 A/B/C 为 **TDD 循环语义位**；Task 内 Subtask 编号（2.1 红/2.2 绿/2.3 重构/2.4 变异）是 TDD 阶段序，两套编号体系分立防混引；验收场景统一归 Task 0 编写/Task 7 收尾承载。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 三段聚合 5 键结构 | Task 1 | 1.1-1.3 五 VO | `test_consultant_view_vos.py` |
| AC-1 | 三段聚合编排 | Task 2 | 循环 A 服务编排 | `test_consultant_view_service.py` |
| AC-1 | 全数据 round-trip | Task 5 | 5.1-5.2 集成场景① | `test_integration_consultant_view.py` |
| AC-2 | 跨 plan 清单+行概况+排序 | Task 2 | 循环 A 多项目段聚合 | `test_consultant_view_service.py` |
| AC-2 | 三 plan 形态验收 | Task 0 | 0.4 场景 S2 | `test_acceptance_consultant_view.py` |
| AC-3 | 品牌段恒默认态 | Task 2 | 循环 A 品牌段构造 | `test_consultant_view_service.py` |
| AC-3 | 品牌段键值验收 | Task 0 | 0.4 场景 S3 | `test_acceptance_consultant_view.py` |
| AC-4 | 导出段派生+最新 PDF 定位 | Task 2 | 循环 A/B 导出段投影+派生矩阵 | `test_consultant_view_service.py` |
| AC-5 | 段级容错+空态幂等读+单源判别 | Task 2 | 循环 C 容错矩阵（S5/S6 验收承载） | `test_consultant_view_service.py` |
| AC-6 | CLI 命令 | Task 3 | 3.2-3.4 CLI+注册 | `test_agent_cli.py` |
| AC-7 | P95<800ms+并发 20 | Task 5 | 5.1-5.2 性能场景（变异锚 5.4） | `test_integration_consultant_view.py` |
| AC-7 | 隔离继承断言 | Task 0 | 0.4 场景 S11 | `test_acceptance_consultant_view.py` |
| 全 AC | 收尾完成清单 | Task 7 | 7.1-7.4 | `test_acceptance_consultant_view.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-7（全量——规范冻结是全部实现的前置）

> **目的：** 在进入代码实现前，明确 VO 键契约、排序与派生口径、端口契约、验收场景与六边形架构边界，并处置 deferred-work 锚定义务（Epic 6 锚七行[L13/L17/L107/L117/L170/L127/L129]归并六组+两条 6.7-DF 维持+两条 D6-8-R 维持+一条 D6-9-R 注记+两条 6.5a-DF 顺延——13 锚位归并 11 行台账，OD-8）。

- [x] Subtask 0.1: 冻结五 VO 键契约（Task 0.1 冻结表落 Dev Agent Record——5/4/6/5/7 键+品牌默认值两常量+PANEL_ARCHIVE_LIMIT[共三常量]——实现禁增删键）
- [x] Subtask 0.2: 冻结排序与派生口径（口径一：行序 latest_activity_at 降序+plan_id 字典序 tie-break+None 时间戳恒排尾；口径二：latest 遮蔽计数口径；口径三：latest_pdf 三键选择[latest_report_at 最大者+tie-break plan_id 升序]；口径四：None 行剔除；口径五：双段联动降级语义——AC-2/AC-4/AC-5 规则逐字冻结）
- [x] Subtask 0.3: 定义端口契约（ConsultantViewPort v1.0.0 零参签名+两依赖注册名+组合根落位 :2139 邻位锚）+ 契约测试文件骨架
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_consultant_view.feature`（12 场景钉死——**每场景 Then 均有可执行断言**[6-9 先例形态——注记型场景禁用]；epics L2493-2495 架构测试三项落位对账：多项目显示→S2/白标报告→S4+口径差声明/多租户隔离→S11 正向可见性口径[OD-13]）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_consultant_view.py`（6-9 R6 合规形态：三件套+双清+context dict+**归档行预置走 repo.save 直写通道**[R5 终审改钦——与报告行通道完全对称：`StrategicArchive` 实体直构造[archived_at 未来偏移可编程——dataclass 构造参数]+`archive_repository.save(entity)`[经 L2RdbPort 基类继承在册 :36+PG 实装 :191 UPSERT+`_to_model` :108-127 archived_at 实体值直传]；R3-F1 原钦定 PG model 直写通道保留为备选[ArchiveModel+session.add 亦可实施]；**禁复刻 6-7 `_archive_row` 编排通道**——其走 `service.archive_plan` 时间戳服务内部生成不可控，与 OD-13① 结构性冲突；R3-F1「ArchiveRepositoryPort 无 save 方法」系伪实证勘误[R5-F1：六扩展方法枚举漏基类四继承方法——save/get_by_id/delete/list_all 经 L2RdbPort 继承在册且服务三处生产消费 :124/:249/:443]]+报告行直写[report_repository.save——集成直写先例 6-8 `_save_report` :504-512 单参形态+实体 created_at 可编程 `_make_report_entity` :448-461 样板]+PG 三分面通道+CLI 直调 helper；**py 模块级零 consultant_view 词族 import 硬纪律**——src 符号全部延迟到步骤函数内 import[含类型注解用途——模块级 import 会使收集期 ImportError 全文件 ERROR，S7/S8 exit 2 与 S12 AssertionError 红形态全部不可达——6-9 :55-68 形态逐字复刻]；**归档行预置带 plan_id=None 形态行**（S2 防御格）+**时间戳未来偏移判别构造**（预置归档行 archived_at 与报告行 created_at 均自基准 now 起微秒级递减——三 plan 相互判别+恒新于背景行[背景行免疫 OD-13]；find/get_latest_by_plan 均无时间窗过滤、无 6-8 审计窗「未来偏移出窗」风险——场景分立注记；禁 `now()` 双调同值形态）；**S9 背景清点步骤**（仅性能场景：预置前 distinct plan 背景数清点——skip 门[>50 跳过]专用；membership 全含断言体系无需差值基线[R2 勘误：差值法对基线后外来写入假红，废止——OD-13②]）；**pytestmark xdist_group("blm-planning-perf") 整模块挂法**（R4-F2 清偿——与全部 strategic_archives 提交型写入方[6-7 验收/集成+checkpoint 系，全仓普查实证]同 worker 串行：背景行稳定+S10 并发窗免疫的结构前提——漏挂则与 6-7 并行产生间歇假红[最难溯源形态]；6-7/6-8/6-9 同组惯例））；运行验收测试，确认失败（🔴 红阶段验证——延迟 import ImportError 形态）
- [x] Subtask 0.6: 定义逐场景红锚符号表（12 场景预期红形态：ImportError/exit code/AssertionError）
- [x] Subtask 0.7: deferred-work 锚定义务处置落档（OD-8 表——L13/L17/L107/L117+L170/L127/L129 六条 Epic 6 锚+6.7-DF1/DF2 两条维持+D6-8-R1/R2 两条维持+D6-9-R1-1 不入命令族注记+6.5a-DF1/DF2 两条顺延——**台账形态：13 个锚位归并 10 行处置+第 11 行不登记新锚裁定=11 行**，计数口径按行[R1 勘误：原稿「共 11 条」与枚举算术 13 锚不自洽]）
- [x] Subtask 0.8: 关键代码锚点行号复核（并行会话提交会使行号漂移——锚点表基准 HEAD@b9525f8b，实施前复核；本 Story 锚点表按当前 HEAD 校正 6-9 期漂移注记：6-9 故事锚组合根 analyst_view 块 :2102-2139 实测吻合）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（键契约/排序派生口径/端口/场景钉死/锚定义务）
- [x] 验收测试运行失败（预期行为，红阶段确认——12 场景全红；预期 S1~S6/S9/S10/S11 ImportError 形态/S7/S8 CLI 未注册 exit 2 红/S12 文件不存在 AssertionError——Task 0.6 符号表）

---

### Task 1: 应用层端口与五 VO——`ports/consultant_view.py`（含品牌默认值常量+面板查询常量）

**关联 AC:** AC-1/AC-3

> **六边形落位：** 全部应用层（`src/application/ports/`）——零 domain（OD-11；消费的两 R1 端口均既有零演进）。

#### TDD 循环 A：五 VO + 常量 + 端口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_consultant_view_vos.py`（五 VO 键集 exact set+品牌默认值两常量值级断言+PANEL_ARCHIVE_LIMIT==1000 断言+构造守卫 242 四形态：plan_id 非空字符串/latest_report_type 值域 {None,"markdown","pdf"}/计数 ≥0（plan_count/archive_count/三计数）/latest_degraded_section_count ≥0 或 None；frozen 断言 `setattr` 形态——6-9 R1-F9 mypy 教训直系） |
| 🟢 绿 | 实现 `src/application/ports/consultant_view.py`（五 frozen dataclass+`__post_init__` 守卫+品牌两常量+PANEL_ARCHIVE_LIMIT+ConsultantViewPort Protocol v1.0.0 零参签名） |
| 🔄 重构 | docstring 全中文 Google 风格+类型注解收口（品牌段 V1 事实断言语义+6-11 对接触发器+禁 import infra 锚注记+font_status 字面量 reportlab :60 单源注记落 VO docstring），运行 `ruff` + `mypy` |

- [x] Subtask 1.1: 🔴 红 — 编写 VO 键集/常量/守卫失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现五 VO+常量+端口最小代码
- [x] Subtask 1.3: 🔄 重构 — 优化 VO 代码（None/0/() 降级值语义 docstring 化——空租户三段降级键注记）
- [x] Subtask 1.4: 🟡 变异 — 键集断言突变实证（删 BrandSection 一键 → exact set 红 → 还原绿；品牌常量改值 → 值级断言红）

**完成标准/Definition of Done:**
- [x] 五 VO+常量+端口实现完成，键契约与 Task 0.1 冻结表逐键一致
- [x] TDD 循环全部通过（红绿变异三态留痕）
- [x] 覆盖率：新增文件 ≥95%（21 用例全绿——三常量值级/五键集 exact/守卫负例全枚举/frozen 纪律/零参签名全覆盖）

---

### Task 2: 应用层视图服务——`ConsultantViewService` 三段编排

**关联 AC:** AC-1/AC-2/AC-3/AC-4/AC-5

> **两依赖注入：** archive_repository/report_repository（keyword-only 构造——ExecutiveViewService 四依赖/AnalystViewService 三依赖同风格）；服务无状态（SINGLETON 并发共享——AC-7 约束）。

#### TDD 循环 A：三段聚合编排（Mock 两依赖）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_consultant_view_service.py` 循环 A 用例（三段聚合：archive find→ProjectsSection[None 行剔除+分组计数+最新活动+行序降序+循环 get_latest_by_plan 报告概况]；BrandSection[默认值常量构造——零 IO+**行为断言**：`_build_brand` 返回值与品牌两常量恒等断言（服务行为锚——V1 无配置面变异不可构造，行为断言足额注记 R1）]；ExportSection[纯投影派生——两计数+latest_pdf 三键]——**Mock spec 形态**：archive_repository `AsyncMock(spec=ArchiveRepositoryPort)`+report_repository `AsyncMock(spec=ReportRepositoryProtocol)`（两端口 Protocol 全在册——组合根 interface 注册面，无需具体类 spec）+ `_make_*` 工厂——`_make_archive`（plan_id/archive_type/archived_at 可编程——含 archived_at=None 形态）+`_make_report`（report_type/file_path/created_at 可编程）+`_make_archive_repo`/`_make_report_repo`/`_make_service`） |
| 🟢 绿 | 实现 `src/application/services/consultant_view_service.py` 三段私有方法+`build_consultant_view` 编排（入口单时间锚一次 now——顶层 generated_at 唯一时间键；零参数签名） |
| 🔄 重构 | 段方法职责收口（每段一方法——`_build_projects`/`_build_brand`/`_build_export`；export 段入参=项目段循环结果——纯投影零 IO 钦定） |

#### TDD 循环 B：排序与派生规则矩阵

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编排序与派生矩阵用例（**行序格**：三 plan 活动时间降序+同时间戳 tie-break plan_id 字典序[两 plan 同 archived_at 构造]；**None 时间戳格**：latest_activity_at=None 行恒排尾[全行 archived_at=None 的 plan 构造——口径一钦定]；**None 行剔除格**：plan_id=None 行混入 → plan_count 不含；**latest 遮蔽格**：同 plan 先 pdf 后 markdown 两行 → latest=markdown → plans_with_latest_pdf==0；**双 plan pdf 判别格**：两 plan latest 均 pdf 且 latest_report_at 可分 → latest_pdf 三键取最大者[tie-break plan_id 升序构造同时间戳格]——口径三判别；**零 PDF 格**：全 latest markdown → available True+latest_pdf 三键 None；**单报告行格**：latest pdf → 定位三键直推；**limit 覆写格**：find 调用参数断言 limit==1000——spec Mock call_args 锚） |
| 🟢 绿 | 实现排序与派生（Task 0.2 冻结口径逐字——**两趟稳定排序钦定形态**[plan_id 升序先排+latest_activity_at 归一降序后排]，禁 `key=(-ts, plan_id)` 伪码[str 无一元负]与 `reverse=True` 整键复合反转[tie-break 连带反转]；latest 遮蔽口径=get_latest_by_plan 结果直判零补查；latest_pdf 选择=口径三） |
| 🔄 重构 | 口径 docstring 化（排序钦定+遮蔽语义+None 剔除+limit 上限风险注记——与 AC-2/AC-4 逐字对齐；N+1 与截断风险立项锚注记） |

#### TDD 循环 C：段级容错与空态幂等读

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写容错矩阵（**find 异常格**：AsyncMock side_effect 抛 → projects+export 双段 degraded=True+默认值+brand 照常+build_degraded=True+不抛；**循环单 plan 异常格**：report_repo side_effect 定向抛（首次调用抛/其余返回——side_effect 列表形态）→ 该行报告列三键 None+双段 degraded+其余 plan 行照常；**空态格**：find 返回空列表 → 三段空态默认值+brand 完整+build_degraded=False+不抛） |
| 🟢 绿 | 实现段级 try 包裹+双段联动降级（find 级+循环级两捕获位分立；warning 日志段名+异常摘要——6-8/6-9 同款） |
| 🔄 重构 | 降级 warning 日志统一+降级值语义 docstring（「段值降默认」与「清单保留+报告列 None」两形态分立注记——AC-5 钦定） |

- [x] Subtask 2.1: 🔴 红 — 循环 A/B/C 失败测试
- [x] Subtask 2.2: 🟢 绿 — 三段编排+排序派生+容错实现
- [x] Subtask 2.3: 🔄 重构 — 服务代码优化（品牌常量/PANEL_ARCHIVE_LIMIT 单源引用禁字面量——6-9 Subtask 2.3 投影白名单常量教训：值单源在 VO 文件常量，服务禁再镜像第二源）
- [x] Subtask 2.4: 🟡 变异 — 规则断言突变实证五锚（行序比较器反转 → 行序格红；latest 遮蔽判定改全量历史 → 遮蔽格红；**双段联动改单段置位**[循环异常只置 projects.degraded 不置 export.degraded] → 循环格联动断言红——OD-12 新容错形态的专属锚；find 容错改 raise → 容错格红；None 行剔除删除断言侧 → None 格红——还原后全绿）

**完成标准/Definition of Done:**
- [x] 三段编排+排序派生+容错实现完成
- [x] TDD 循环全部通过（变异锚 5 处全实证红→还原绿留痕——含双段联动专属锚）
- [x] 覆盖率：服务文件 ≥95%（排序派生三分支+容错两捕获位 100%）

---

### Task 3: 用例 + CLI `consultant-view` + 组合根注册

**关联 AC:** AC-6（CLI）

> **组装层扩展：** `src/entrypoints/agent_cli.py`（argparse 扁平子命令——analyst-view 注册块 :567-580 邻位）+ `src/composition_root.py`（:2139 analyst_view_use_case 块尾邻位双注册）。

#### TDD 循环 A：用例 + 组合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_consultant_view_use_case.py`（零参透传——`execute()` 无参调用服务一次+返回直传；**无守卫面注记测试**：用例源码零 `EntityValidationError` token 断言——「242 语义自然缺席」架构注记落测试）+ `tests/contracts/test_port_contract_consultant_view.py` 五断言族 |
| 🟢 绿 | 实现 `src/application/use_cases/get_consultant_view.py`（零参透传——`GetExecutiveViewUseCase`/`GetAnalystViewUseCase` 直系样板去守卫形态）+ 组合根双注册块（consultant_view_service SINGLETON lambda 两依赖 resolve+consultant_view_use_case SINGLETON 透传） |
| 🔄 重构 | 注册块注释（两 SCOPED 依赖无混态注记——比 6-8/6-9 混态更简；未来 7-2 REST 面改 SCOPED 触发器注记——6-8/6-9 OD 同款第三连） |

#### TDD 循环 B：CLI consultant-view

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（`_StubConsultantViewUseCase` 替身+专用 patcher（`_patch_consultant_view_entry`——`monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)` + `setattr(agent_cli, "resolve", lambda name: stub)` 形态——**每命令族新建专用 patcher 纪律**[6-8 R1-F11/6-9 第三连]）：解析（注册锚/`--plan-id` 传入 → exit 2 unrecognized 格/**零参数面 getsource 断言**——`add_parser("consultant-view"` 切块后零 `add_argument` 调用）/全数据输出（三段分隔行+两 plan 四行+品牌两行+导出三行+提示行）/空态输出（`项目: 共 0 个`+品牌两行恒在+导出空态行+exit 0）/降级两形态格（**R1-F1 分立**：find 级格[plans=()+plan_count=0+导出七键置零——矛盾 VO 纪律]断言首行含「（部分数据降级）」+`项目清单获取失败`+导出段值级降 0；循环级格[清单保留+行报告列 None]断言清单行在场+不降获取失败单行）/DomainError 兜底格（stub error → stderr `[EXCEPTION_` 前缀+exit 1——防御性兜底判别）/exit 0） |
| 🟢 绿 | 实现 CLI：`build_parser` 注册（**零 add_argument**）+分发分支+`_run_consultant_view_cli` 五步定式（无守卫步——四步实态：`_ensure_bootstrapped`→`asyncio.run`+resolve→打印→DomainError/Exception 双 except exit 1；五步定式名保留注记——去守卫步差异 docstring）+`_run_consultant_view` async 壳（finally `_close_connection_pools`）+`_print_consultant_view` 三段打印（getattr 零 VO import 形态——6-9 直系） |
| 🔄 重构 | 输出行格式统一（「输出即契约」——空态行恒在+两行/项目形态+时间戳 `%Y-%m-%d %H:%M` 截断呈现注记） |

- [x] Subtask 3.1: 🔴 红 — 用例/契约/CLI 失败测试
- [x] Subtask 3.2: 🟢 绿 — 用例+组合根+CLI 实现
- [x] Subtask 3.3: 🔄 重构 — CLI 打印面优化（注册注释措辞注意：**禁出现 `--format`/`--plan-id` 字样于 consultant-view 注释块**——6-9 R1「注释字样污染 6-8 既有 getsource 块边界断言」教训预防性纪律：新注释块措辞自查不触既有命令族切块断言边界）
- [x] Subtask 3.4: 🟡 变异 — CLI 输出断言突变实证（四锚：①项目段首行「共」改「总」②品牌注记行删除③导出提示行删除④降级标记置空——还原后全绿）

**完成标准/Definition of Done:**
- [x] 用例+CLI+组合根实现完成（resolve 可达+分发接线）
- [x] TDD 循环全部通过（变异锚 4 处全实证）
- [x] 覆盖率：用例 100%/CLI 新增面 ≥90%

---

### Task 4: 契约守护与回归面

**关联 AC:** AC-1（端口契约）/OD-2（零事件）/OD-3（零异常）

> **性质说明：** 契约级守护复跑+新增端口契约测试定稿——非功能实现 Task。

- [x] Subtask 4.1: 端口契约测试五断言族复跑确认（禁改断言——改动需回 Task 3 循环重走红绿；注册可达/spec 元数据 v1.0.0+SINGLETON+tags/lambda 注入链 getsource 两依赖注册名锚/resolve 可达 isinstance/方法签名零参——`test_port_contract_analyst_view.py` 逐段对齐；签名断言 `build_consultant_view` == {self} 零参——与 6-8/6-9 {self, plan_id} 分立注记）
- [x] Subtask 4.2: 零事件守护复跑（`tests/contracts/test_event_channel_mapping_pdf_report.py` 6 passed——_FROZEN_EVENT_COUNT=56 零变化；event_channels.yaml/DEFAULT_MAPPINGS 零 diff git 实证）
- [x] Subtask 4.3: 回归面验证（四目录全量零失败——6-7/6-8/6-9 既有验收零破坏；agent_cli/composition_root 扩展面既有单测零适配[纯新增子命令/注册块——**6-9 教训预防**：新注释块与既有 test_no_optional_arguments/getsource 切块断言边界复核]；archive_repository 既有生产码消费方**全景**[R2-F8 清偿——REST 两端点 /entries+/plans/{plan_id} 经 strategic_archive_service.query_archive :315-325 中继+StalenessWeightService 兜底链 :95-96+SummaryGenerationService 陈旧标记兜底链 :441-446] 零影响[find 既有方法消费无签名变化]；report_repository 既有消费方 executive_view_service+report_generation_service 零影响[get_latest_by_plan 消费无变化]）
- [x] Subtask 4.4: 三红线 grep 自查（`raise ValueError`/`HTTPException`/`Exception(` 继承——新增面零输出；noqa/type: ignore/pylint disable 全部新增文件零输出）

**完成标准/Definition of Done:**
- [x] 契约测试全绿+冻结键数基线零变化
- [x] 四目录全量零失败（第一轮 no-cov+第二轮覆盖率——Task 7.4 承载最终确认）（第一轮实测 15260 passed——既有 15000+ 面零破坏，失败项均为本 Story 新增面当时未竟态+已修复）

---

### Task 5: 集成测试——真实双源链聚合

**关联 AC:** AC-1/AC-7

> **真实服务 Schema 隔离子模式**（6-x 集成双子模式选型：真实服务面——双源全真实[PG 归档行+PG 报告行]）+ xdist 同组串行。

#### TDD 循环 A：真实链三段聚合 + 性能并发

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_consultant_view.py`（**集成面同为共享库**[事务回滚式非独立 schema——背景行同在，OD-13 断言口径同验收面]：场景① 全数据三段 round-trip：真实归档行直写[repo.save 直写通道 R5 改钦——三 plan 形态+None 行+archived_at 未来偏移]+报告行直写[report_repository.save——plan-A markdown+pdf/plan-B markdown，预置时间戳未来偏移]→服务直调断言[**membership 全含口径 OD-13**：三 plan ∈ 清单+各恰一行/预置行占首三+内部降序/逐行 archive_count 与 latest_report_type 直推/latest_pdf 三键与预置 pdf 行直推/品牌恒默认/计数恒等式三联——VO 内部不变量背景行免疫]（**判别形态**：plan-C 零报告行判别「有活动无交付物」、plan-A pdf 最新判别遮蔽口径）；场景② 空态幂等读（零预置 → 5 键恒在+brand 完整+build_degraded False+不抛——核心四断言口径；绝对空态值断言归单测[Task 2 空态格]；6-8 集成侧「绝对空断言不可写 R1-F6」先例直系）；场景③ 性能 20 轮 P95<800ms（模块级期望常量+sorted 数学口径+预热；C 面禁 set_session；**背景 distinct plan 数>50 时 pytest.skip**——环境量级敏感）；场景④ 并发 20 路 gather 全成功+**预置子集过滤后逐路相等**（membership 过滤 projects+brand+build_degraded 对照——全集相等禁用[6-8 R2-F2 直系]；禁 set_session）） |
| 🟢 绿 | 预置/清理通道落地（归档行+报告行 PG 直写+定向清理[行数断言]；PG 三分面按场景分组——6-8 R2-F3/6-9 直系第三连）+断言通过 |
| 🔄 重构 | 预置工厂函数收口（`_make_archive_row`[repo.save 直写——archived_at 实体构造参数化]/`_make_report_row`——时间戳未来偏移显式构造形态固化） |

- [x] Subtask 5.1: 🔴 红 — 四场景失败测试
- [x] Subtask 5.2: 🟢 绿 — 预置通道+断言通过
- [x] Subtask 5.3: 🔄 重构 — 工厂收口+docstring（性能三段口径差声明落模块 docstring——OD-8；N+1/截断风险注记）
- [x] Subtask 5.4: 🟡 变异 — 集成断言突变实证（验证型 2 处：membership 全含断言改期望集缺一 plan → 值级红[实施注记：期望集缺员形态被首三占位断言兜底不红——断言体系三重冗余防御实证；改用期望 count 1→2 形态直接判别「各恰一行」断言活着→红]；并发篡改一路的**预置 plan 行派生值**[archive_count+1 形态——须进 membership 过滤对照面] → 子集等价性红——还原后 4 passed）

**完成标准/Definition of Done:**
- [x] 四场景全绿（真实服务零 mock——P95<800ms 实测通过[背景量级 skip 门]+并发 20 路 subsetting 过滤对照通过[OD-13]）
- [x] 性能 P95 断言通过+口径声明落档
- [x] 覆盖率：集成新增面 ≥75%

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 六边形架构约束（全 AC 底座）

> **性质说明：** 本 Task 是 **SDD 规范验证测试**——验证代码是否符合架构规则（非功能 TDD）。

#### 架构验证测试实现（四验证器——`test_analyst_view.py` 直系样板）

- [x] Subtask 6.1: 验证器 A 落位守护（交付文件在 application 层/五 VO+两常量+端口定义于 ports 文件非服务本地/服务与用例禁本地 Protocol——AST 扫 ClassDef bases+模块级 AnnAssign 常量形态——6-9 实施攻坚教训直系）
- [x] Subtask 6.2: 验证器 B 零 publish 守护（服务源码 token grep `publish`/`event_publisher` 零出现+AST 零事件构造——pkgutil 强制导入 events 全子模块后 DomainEvent 子类名全集比对 Call 节点）
- [x] Subtask 6.3: 验证器 C 零 domain/infra 改动+依赖方向（`SERVICE_ALLOWED_PREFIXES` 白名单逐 import startswith 断言+三方禁 import frozenset+rglob 零命中结构断言——OD-11 纯三零：src/domain+src/infrastructure 双目录 consultant 词零命中——与 6-9 零命中形态直系、与 6-8 白名单形态分立注记）
- [x] Subtask 6.4: 验证器 D CLI 接线（源码含 `add_parser(\n        "consultant-view"` 缩进敏感锚+`args.command == "consultant-view"` 分发+`resolve("consultant_view_use_case")` 调用锚+组合根双注册块锚+**两依赖注入锚** `'"archive_repository"'`/`'"report_repository"'`）
- [x] Subtask 6.5: 运行完整测试套件并生成报告（ruff E/I 循环依赖检测——不引入 pylint）
- [x] Subtask 6.6: 🟡 变异 — 架构断言突变实证（验证器 B token grep 断言：源码临时注入 `publish` token → 测试红 → 还原绿）

**完成标准/Definition of Done:**
- [x] 四验证器全绿（任何违规即测试失败）
- [x] 循环依赖检测用 ruff/isort

---

### Task 7: 开发结束验收测试

**关联 AC:** 全 AC 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_consultant_view.feature` 收尾场景（完成清单存在性断言） |
| 🟢 绿 | 编写 `test_acceptance_consultant_view.py` 收尾 BDD 步骤（`_COMPLETION_SRC_FILES`/`_COMPLETION_TEST_FILES` dict 常量+`path.is_file()` 断言——6-7/6-8/6-9 S12 形态第四连） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 7.1: 场景 12 — 验证 `src` 完成清单的逐项确认
- [x] Subtask 7.2: 场景 12 — 验证四测试目录完成清单的逐项确认
- [x] Subtask 7.3: 运行开发结束验收测试并确认通过（12/12 场景全绿）
- [x] Subtask 7.4: 运行 `pytest` 四目录全量、`ruff check`+`ruff format --check`、`mypy` 进行收尾校验+deferred-work 处置注记终检（Task 0.7 11 条落档确认——实测 14 锚位逐行追加=先例行内注记形态，台账 10 行归并口径+第 11 行不登记裁定在锚定义务清单表）+纯三零 git diff 实证（src/domain+src/infrastructure+src/interfaces 三目录零 diff）

**完成标准/Definition of Done:**
- [x] `src` 与四测试目录完成清单已逐项验证确认
- [x] 开发结束验收测试通过（12/12 场景全绿）
- [x] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构严格分层（本 Story 纯应用层+组装层扩展——**纯三零：零 domain/零 migration/零 infra**，6-9 直系第二连；读侧聚合 CQRS 投影形态（三段聚合视图=两源读模型——6-8/6-9 第三连+跨 plan 全局投影首例））
- **设计约束:** 领域层零依赖（零 domain 改动天然满足）；读侧 DTO 归应用层（五 VO ports 文件承载）；查询不发布事件（architecture.md:1293——引用形态注记+七查询型 Story 零事件族实践）
- **接口治理:** 统一端口注册（新端口 v1.0.0 一次到位）、Registry/Resolver、组合根唯一装配、契约优先、禁同义接口重复（consultant_view 跨 plan 交付面 vs executive_view 单 plan 速览面 vs analyst_view 单 plan 作业面——三语义正交）；两依赖全既有注册名消费不新开底层端口
- **技术栈:** Python 3.11+ / PostgreSQL（archive find 1 次+get_latest_by_plan N 次点查——plan_id 索引命中）/ pytest-bdd；品牌段零 IO（应用层常量构造）
- **关键设计条款:** prd L423-424（MVP 基础多租户+白标输出基础——「品牌元素 100% 准确，导出<1 分钟」验收归 6-11 生成面/6-5b 既有性能面）；prd L1898-1901 FR-SP-16（白标 REST API 归 Epic 20 Story 20.4）；prd L2199-2204 FR-IF-05（三页面角色枚举无顾问）；ux-design-specification L1401-1405（顾问视图=视图布局差异化表中「基于品牌模板调整」行——Web 面口径）；interface-design.md 13.2 三视图表（:2001-2007——高管/分析师/**企业战略与市场人员**三行，**无顾问行**；:2090「实现 Web 前端三视图[高管/分析师/战略人员]｜Story 6.9/6.10」行是本 Story 真实锚位——顾问视图在 interface-design 的呈现即 CLI-only 裁定与 epics L2476 现行权威一致，6-8/6-9 同款注记先例第三连）

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | **范围边界——MVP = 三段聚合查询面（ConsultantViewPort+ConsultantViewService+GetConsultantViewUseCase+CLI `consultant-view` 零参数全局视图）。不含**：Web 顾问面板（归 Epic 21/22——注记：21/22 均无顾问专属 Story、22.8 角色枚举[高管/分析师/企业战略人员]不含顾问——顾问 Web 面归 22.8 扩展或后续 Web Story 立项，本 Story 不预建）/品牌模板配置实现（Logo/配色/字体上传保存+预设选择+模板复用+reportlab Image 位图渲染+report-generate 品牌参数——**全部归 Story 6.11** P0-11；epics L2036「品牌配置可独立实现」+6-5b L31/L682/L684 显式移交在档；本 Story 品牌段=状态展示面 V1 恒默认态）/白标渲染与品牌 100% 准确（6.11 AC 逐字重叠面——本 Story 零渲染零触碰 `PdfRendererPort` 签名）/REST 端点（CLI-only 第九连 6.1-DF5 先例+openapi.yaml 零 diff；白标 REST `/reports/whitelabel` 归 Epic 20 Story 20.4）/批量导出管线（L129 显式裁定不做——白标导出=单 plan 单次生成归 report-generate 既有入口 6-5b OD-11 单入口钦定）/多租户存储隔离实现（Schema per Tenant 归租户管理后续 Story——1-11 交付合规面；本 Story 展示口径+隔离继承断言）/单 plan 视图要素（报告可得性/审批/审计/进度/溯源归 6-8/6-9 已交付——禁重复聚合）/plan 生命周期管理（StrategicPlan 实体孤岛零消费亲验——plan 注册表/状态机是独立立项面非本 Story 增量） | epics L2476-2516 范围权威+L656/L2020 依赖行 + 6.1-DF5 八连 CLI-only 先例 + 6-8/6-9 OD-1 边界先例 + YAGNI |
| **OD-2** | **零新增领域事件、零发布、零订阅**（查询型故事第九连）：纯查询聚合面零状态变更——七连零事件先例族延续；event_channels.yaml/DEFAULT_MAPPINGS 零 diff；`_FROZEN_EVENT_COUNT=56` 零变化（Task 4.2 守护复跑）；蓝图无顾问视图事件载体；架构验证器 B 零 publish 守护 | 查询语义纯度+七连先例族+零 yaml/router diff 红利 |
| **OD-3** | **零新增领域异常、零既有异常改动+零 242 消费面**：本 Story **零输入**（build_consultant_view 无参）——畸形 plan_id 守卫面语义自然缺席（6-8/6-9 连续 242 UUID 守卫后本 Story 无输入即无畸形面——设计结果非缺失；验收无 242 场景属正确形态）；空态幂等读不抛（五先例族第六连）；report 段 490-493 已用/494-499 预留**不占**（490 生成面语义零触碰——`_code_ranges.py:199-212（R4 统一口径）` 亲验）；archive/report 两域零异常改动。**否决备选**：开新码（ConsultantViewError）——段级容错+空态幂等读后无真实 raise 触发面，开码即引入「空租户误报」反语义面（6-7/6-8/6-9 否决论证同构第四连） | 异常语义纯度+五先例族+空态幂等读语义+零输入设计连锁 |
| **OD-4** | **五 VO 键契约**（Task 0.1 冻结）：`ConsultantView` 5 键（generated_at[ISO 单时间锚]/build_degraded[顶层降级哨兵]/三段——**顶层无 plan_id 键**：全局视图零输入的 VO 投影，与 6-8 8 键/6-9 6 键分立点）/`ProjectsSection` 4（available[==plan_count>0]/degraded/plan_count/projects）/`ProjectSummary` 6（plan_id[str 化——实体 UUID→str，6-8 report_id 钦定直系]/archive_count/latest_activity_at[该 plan 最大 archived_at ISO]/latest_report_type[None\|"markdown"\|"pdf"——ReportType 值域直传]/latest_report_at/latest_degraded_section_count[None\|int]）/`BrandSection` 5（degraded 恒 False/configured 恒 False V1/logo_status/color_scheme_status/font_status——**零 IO 静态段**：三段中唯一无数据源段，空态/降级全场景值恒不变）/`ExportSection` 7（available[==plans_with_reports>0——「有报告可导出」与「已导出 PDF」分立：markdown 亦是可交付物，PDF 缺席不降 available]/degraded[与 projects 段同源联动]/plans_with_reports/plans_with_latest_pdf[latest 遮蔽口径——OD-7]/latest_pdf_plan_id/latest_pdf_object_key[file_path 直传——PDF 行即 L4 对象键 :79 单源]/latest_pdf_generated_at）——全应用层 frozen dataclass；键恒在纪律（None/0/() 降级值）；构造守卫 242 四形态（计数 ≥0/plan_id 非空/latest_report_type 值域/latest_degraded_section_count ≥0 或 None——R1-F11 补值域；VO 不变量面守卫归 VO，与服务容错分立） | 键恒在纪律+读侧 DTO 层位先例+空态幂等读语义第六连 |
| **OD-5** | **多项目段数据源裁定——archives 反推 plan 清单+报告循环 enrichment**：plan 清单 = `ArchiveRepositoryPort.find(ArchiveQuery(plan_id=None, limit=1000))` 全量行 distinct plan_id（**该查询面 plan_id=None 全量清单形态的视图服务首个消费**——既有生产码消费方全景：REST 两端点经 `strategic_archive_service.query_archive` :315-325 中继+StalenessWeightService 兜底链 :95-96+SummaryGenerationService 陈旧标记兜底链 :441-446[同形态 archive_ids 批量]；find 现成跨 plan 查询零新端口零新 SQL——纯三零 Story 的关键裁定[R1-F8 全景口径]）；`plan_id=None` 行剔除（实体可空亲验 :56——防御性守卫）；每 plan 报告概况 = 循环 `get_latest_by_plan`（N+1 点查——plan_id 索引命中 MVP 量级 <50ms；**风险注记双联**：plan 数百级 N+1 成热点+归档行超 1000 截断——「DISTINCT+JOIN LATERAL 单查询化/SQL 清单端口」立项锚 Epic 7/21，docstring 承载）；**项目行不含进度列**（进度可视化归 6-9 analyst-view 单 plan 面两视图正交；快照 TTL 86400 过期语义不稳+SnapshotRepositoryProtocol 无 scan 亲验——快照扫描方案结构性不可行亦排除）；**不选** ReportRepository 新增 list 方法（需 domain port 扩展+infra 实现破坏纯三零；get_latest_by_plan 循环已足——报告计数口径本就是「最新分布」非「全史」）；**不选** L4 list_objects/L0 list_memories（L4 仅 PDF 对象+L4/L0 面报告元数据不全——section 双计数在 L2；两源引入第三依赖徒增复杂度） | find 现成面实证+纯三零收益+N+1 风险可控（MVP 量级）+两视图正交原则 |
| **OD-6** | **品牌段 V1 恒系统默认态+6-11 对接锚**：零 IO 静态段（构造无任何仓储调用——服务 `_build_brand` 纯常量构造）；品牌两常量钦定 ports 文件（BRAND_STATUS_UNCONFIGURED/BRAND_FONT_STATUS[与 PANEL_ARCHIVE_LIMIT 共三常量——Task 0.1 冻结表口径]——`font_status` 值「STSong-Light（内置）」与渲染器 `_FONT_NAME` :60 冻结字体事实对齐——**字面量承载禁 import infra**：application→infrastructure 依赖方向禁止+锚注记落 docstring）；`configured` 键是 6-11 对接锚（届时品牌配置面落地后本段演进读配置面——端口 v1.1.0 触发器 docstring 注记）；值级断言=V1 时点事实断言（6-11 实施后红是预期演进信号——6-9「23 工具事实断言」语义直系第二连） | 6-11 边界（epics L2036+6-5b 移交注记）+依赖方向矩阵+零 IO 恒稳段设计收益（空态断言可钉死） |
| **OD-7** | **导出段纯投影派生+latest 遮蔽口径声明**：export 段零新读（入参=项目段循环结果——服务仅两读源 archives+reports，第三段纯投影——单源纪律）；`plans_with_latest_pdf` =「**最新**报告为 pdf 的 plan 数」非「历史曾生成计数」（get_latest_by_plan created_at 降序首行唯一——先生成 PDF 后又生成 markdown 的 plan 其 latest=markdown 不入 pdf 计数——「当前交付物形态」呈现语义：顾问面板关注「现在可交付什么」非「累计交付史」；遮蔽判别格钦定入 Task 2 循环 B）；available==plans_with_reports>0（「可导出」与「已导出 PDF」分立——markdown 亦是可交付物）；与 6-8 `ReportSection`（单 plan 可得性 8 键）**语义正交非演进**（跨 plan 全局投影 vs 单 plan 可得性——两段 VO 各自独立禁共享，消费方/演进节奏不同——6-9 OD-13 两视图正交原则直系第二连） | 单源纪律+呈现语义+读侧投影独立演进原则 |
| **OD-8** | **性能三段口径声明+锚定义务 11 条处置**：① 视图加载 P95<800ms = `build_consultant_view` 服务面窗口（两读源：find 1 次+N 次点查；20 轮 `sorted[ceil(0.95*n)-1]` 数学口径六连；N+1/截断双风险注记立项锚 Epic 7/21）；② 并发 20 路=零输入全局读 20 路并发（gather+服务无状态+**预置子集过滤后逐路相等[OD-13——全集相等禁用：全局无窗查询并发窗内受其他 worker 写入抖动，6-8 R2-F2「排除集不可收缩」教训同源；membership 过滤 projects+brand 恒稳对照；原「排除集单键 {generated_at}」设计经 R1 证伪废止]**；禁 set_session C 面第三连）；③ 「白标导出<1 分钟」=report-generate 既有入口性能面（6-5b 承载——本 Story 导出段是状态展示面非执行面，6-9「溯源跳转<300ms 归 6-7」裁定形态第三连）+「多租户隔离 100%」=继承口径（1-11 合规面承载+S11 正向可见性断言[OD-13]+完整实现归租户管理后续 Story）——③ 两项口径差声明落验收/集成 docstring。**锚定义务 11 条**（Task 0.7 落档）：L13 第七轮不触发（无版本统计面）/L17 第七轮同构顺延（纯读侧零图引擎）/L107 不触发（本 Story 零 Skills 消费——无 skill_selector 依赖，比 6-9 更远）/L117+L170 第九连零消费顺延 Epic 8/L127 第七轮不触发（零记忆消费）/L129 **第五轮维持+显式不做批量裁定**（读侧聚合非批量报告管线——本 Story 主动收窄：批量导出不立项，锚位维持「6-11/Epic 7 再锚定」不变）/6.7-DF1·DF2 维持 Epic 21-22/D6-8-R1·R2 第三连维持（新增子命令沿用既有入口形态+json_chain 零触碰）/D6-9-R1-1 **不入命令族注记**（consultant-view 零 --plan-id 输入面——该观察项波及面 `*--plan-id` 命令族不含本命令；deferred-work L409 处置注记追加）/6.5a-DF1·DF2 顺延 Epic 7（REST 导出面/L0 撕裂——CLI-only 形态触发条件不含本 Story） | epics L2498-2500 性能行与 CLI 交付面口径对齐（六连口径差声明纪律）+deferred-work 原文触发条件逐条对表+七轮先例链 |
| **OD-9** | **测试文件命名（禁故事编号后缀）+ 词族统一 consultant_view**：acceptance `test_acceptance_consultant_view.feature/.py`；integration `test_integration_consultant_view.py`（**对 epics L2513 钦定名 `test_consultant_view_integration.py` 的显式偏离**——仓规 test_integration_* 前缀，6-8/6-9 OD-9 同款偏离声明第三连）；unit/architecture `test_consultant_view.py`（**对齐 epics L2512 钦定名**——零偏离）；`consultant` 词族 src+tests+configs+docs/api 零占用亲验（grep 全域零命中）；CLI 子命令 `consultant-view` 无重名亲验（add_parser 16 命令族逐一比对——本 Story 落地后 17）；service 单测 `test_consultant_view_service.py`+VO 单测 `test_consultant_view_vos.py`；契约 `test_port_contract_consultant_view.py`（五断言族） | 记忆「禁止故事编号命名文件」+仓规前缀惯例+词族零占用亲验（epics 钦定名的采纳/偏离逐处声明——6-8/6-9 同款第三连） |
| **OD-10** | **组合根双注册+两既有依赖复用+CLI 零参数先例**：`consultant_view_service`（SINGLETON——无状态聚合读；lambda resolve 两既有注册名：`archive_repository` :2315[SCOPED v1.1.0]+`report_repository` :3513[SCOPED]——**两 SCOPED 无混态捕获**注记：6-8 三 SCOPED+一 SINGLETON/6-9 两 SINGLETON+一 SCOPED 后的最简形态，SINGLETON 捕获 SCOPED 声明照写[CLI 一次性进程+测试双清下无故障面——三连注记先例]）+`consultant_view_use_case`（SINGLETON 透传）；**零新 PG 仓储家族成员/零 infra 面**；两依赖注入端口面（AsyncMock spec=ArchiveRepositoryPort/ReportRepositoryProtocol——两 Protocol 全在册无需具体类 spec）；6-4 CLI session P0 三步排查法核验：lambda 无新 PG 构造/无新仓储成员——无 session_factory 缺口面（两仓储均组合根 session_factory 注入形态既有）；**CLI 零参数先例声明（R1 修正口径）**：consultant-view 是 CLI 族**首个零 add_argument 命令**（参数面真空）——16 命令族实测形态：6 个 --plan-id 必填读+7 个写命令+2 个 --agent-id 锚定读（load-profile/isolation-status）+1 个可选参数全局检索（isolation-logs :623——六参数全 required=False **可裸调但带可选过滤/分页面**；6+7+2+1=16 加法闭合）；语义分立点=「参数面真空」vs isolation-logs 的「零必填含可选面」（多项目面板无过滤/分页需求来源——YAGNI）；语义分立注记落注册块注释；**注释措辞纪律**：禁 `--format` 字样入 consultant-view 注释块（getsource 切块断言实际 token 面——6-8 :3215 检 --window-days/--format、6-9 :3492 检 --format/--category；`--plan-id` 字样禁令为过度谨慎预防位，一并保持） | 6-8/6-9 组合根先例+端口 Protocol 在册实证+单租户口径延续+CLI 命令族语义分立 |
| **OD-11** | **纯三零 Story：零 domain+零 migration+零 infra**（6-9 直系第二连——Epic 6 视图族两个纯三零连员）：五 VO+三常量全应用层（ports 文件——读侧 DTO 归应用层+消费的两 R1 端口均既有零演进双依据）；本 Story 改动面 = **src 面 3 新建+2 扩展**（新建：ports/consultant_view.py+services/consultant_view_service.py+use_cases/get_consultant_view.py；扩展：agent_cli.py+composition_root.py）；tests 面 8 新建+1 扩展（test_agent_cli.py 扩展）；**架构验证器 C 零命中断言**（src/domain+src/infrastructure 均零 consultant 词命中——与 6-8 白名单形态分立[彼有钦定 infra 增量]、与 6-9 零命中形态直系） | 两源既有零缺口（find 现成跨 plan+get_latest_by_plan 既有）+最小改动面形态 |
| **OD-12** | **段级容错双段联动+行级同形裁定**：archive find 异常 → projects+export **双段联动降级**（export 派生源受损——段级容错族的复合段新形态：6-8/6-9 各段独立互不波及，本 Story export 段结构性依赖 projects 段循环结果，联动降级是诚实语义非耦合缺陷）；循环内单 plan `get_latest_by_plan` 异常 → 该行报告列三键 None+**双段 degraded=True**（保守诚实裁定：行级 None 与「无报告」同形——段哨兵是唯一「拿不到 vs 没有」区分面[6-7/6-8/6-9 诚实性纪律延续]；否决「行级 degraded 键」备选：判别价值低+VO 键面膨胀，YAGNI）；降级值两形态分立注记（find 级=段值全默认[plan_count 0+空 tuple]；循环级=清单保留+报告列 None——「部分降级」语义 docstring 钦定）；brand 段零降级面（零 IO 恒稳——degraded 键恒 False 是结构性承诺非断言缺失） | 段级容错先例族+派生段结构性依赖+诚实性纪律（「拿不到」vs「没有」两层分立） |
| **OD-13** | **共享库全局面断言体系（R1 新增——本 Story 特有结构性裁定）**：验收/集成 PG 是**共享库共享 schema**（验收 pg_session 直连 env PG 无 search_path；集成为事务回滚式非独立 schema——ensure_alembic_migration 是默认 schema 全局迁移），库中存在其他测试已提交、无清理、跨 xdist 组的背景行（R1 实测 3 条归档行/1 个背景 plan；6-8 审计周期同源实证）。`find(plan_id=None)` 是 Epic 6 视图族**首个跨 plan 全局无窗查询**——6-8/6-9 单 plan 锚定先例（plan_id 前缀天然免疫背景行）结构性失效。**断言体系四件套（R2 修订——②差值法升格 membership 全含）**：① 预置时间戳**未来偏移**（基准 now 起微秒递减——预置行恒新于背景行→行序「占首三」/latest_pdf 三键恢复绝对可判别；find/get_latest_by_plan 均无时间窗过滤，无 6-8 审计窗「未来偏移出窗」风险——场景分立注记；现存测试时间戳均为 now/过去形态亲验——免疫假设成立；**未登记假设补强[R4-F5]**：「占首三」结构性依赖「全库无更新时间戳行」——本 Story 首创未来偏移预置模式，后续 Story 复刻该模式且清理泄漏时将互拆本断言[间歇假红]——复刻方须与本断言互斥登记或采 ≥1s 显式量级登记；另：全部值级断言为「与预置值直推相等」形态无 now 比较面——挂起/时钟极端形态无影响[R2-B 第 2 组证伪留痕]）；② **membership 全含断言**（预置 plan_id 集 ⊆ 清单 plan 集+各预置 plan 恰一行+行级值直推——外来 plan 免疫；**R2 勘误：原差值法[预置前后集合差==预置集]对基线后外来写入假红**——差集无过滤面，外来 plan 入差集即红；membership 全含无需基线查询且判别更强[漏读预置行同样红]；**窗口稳定结构前提[R4-F2 登记]**：全仓 strategic_archives 提交型写入方仅 6-7 验收/集成+checkpoint 系且全部挂 blm-planning-perf 组——本 Story 同组串行后预置可见性与行集稳定闭合；**前向约束登记**：新增提交型归档写入测试必须挂同组，否则重开并发窗抖动）；③ CLI/清单**包含断言+格式断言**（预置行输出 in stdout/`项目: 共 ` 模式——不断言完整输出集）；④ **绝对空态断言分立**（available==False/plan_count==0/`共 0 个` 精确输出归单测承载[find 空返回格+stub 空 VO 格]；验收/集成承载核心四断言[5 键恒在+brand 完整+build_degraded False+不抛]——6-8 集成侧「绝对空断言不可写 R1-F6」先例直系）。**并发对照**改预置子集 membership 过滤后逐路相等（全集相等禁用——6-8 R2-F2「排除集不可收缩」直系；projects/export 全排除则判别力归零故改子集对照）。**S11 隔离**改正向可见性（单 schema 下「零跨漏」排他断言不可判别——隔离语义本体归 1-11 合规面测试）。**性能场景**背景量级敏感（全库 distinct plan 数 N 次点查——预置前清点，>50 skip 动态跳过）。**S6 重定义**为单源契约绊线场景（零归档+报告行在场→报告行 plan_id ∉ 清单——membership 措辞[R5-F2 勘误：原「plan 集差==∅」差值表述随 ② 升格联动]；当前端口面下恒绿——判别力面向未来端口扩展[R4-F3 重标语义]；原「注记型场景」无 Then 可执行断言[6-9 先例每场景均有断言]废止） | 共享库实证（R1 实测背景行）+6-8 差值断言体系/R2-F2 排除集教训/R1-F6 空断言禁令三大先例直系适配+Gherkin 场景可执行性纪律 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── application/
│   ├── ports/consultant_view.py              ★ 新建（五 VO+品牌默认值两常量+PANEL_ARCHIVE_LIMIT+ConsultantViewPort v1.0.0 零参——Task 1）
│   ├── services/consultant_view_service.py   ★ 新建（三段编排+排序派生+双段联动容错——Task 2）
│   └── use_cases/get_consultant_view.py      ★ 新建（零参透传——Task 3）
├── entrypoints/agent_cli.py                  ▲ consultant-view 子命令（Task 3——analyst-view 注册块 :567-580 邻位）
└── composition_root.py                       ▲ 双注册块（Task 3——:2139 analyst_view_use_case 块尾邻位）

（src/domain/ 零改动；src/infrastructure/ 零改动；src/interfaces/ 零改动——OD-11 纯三零第二连）

tests/
├── unit/
│   ├── application/test_consultant_view_vos.py                ★ 新建（Task 1）
│   ├── application/test_consultant_view_service.py            ★ 新建（Task 2——排序派生矩阵+容错矩阵）
│   ├── application/use_cases/test_consultant_view_use_case.py ★ 新建（Task 3）
│   ├── architecture/test_consultant_view.py                   ★ 新建（Task 6——四验证器）
│   └── interfaces/cli/test_agent_cli.py                       ▲ consultant-view 扩展（Task 3）
├── integration/test_integration_consultant_view.py            ★ 新建（Task 5，OD-9）
├── contracts/test_port_contract_consultant_view.py            ★ 新建（Task 3/4——五断言族）
└── acceptance/
    ├── test_acceptance_consultant_view.feature/.py            ★ 新建（Task 0/7，R6 模板+OD-9）
    └──（6-7/6-8/6-9 既有测试文件零修改——Task 4 回归验证）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 11 条处置注记（Task 0.7/7.4）
```

（▲ 修改 / ★ 新建 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话亲验 2026-11-08+四 Agent 调研交叉；行号基准 HEAD@b9525f8b，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| epics Story 6.10 定义 | `_bmad-output/planning-artifacts/epics_v1.0.md:2476-2516` | AC 三要素/性能三项/测试文件名钦定源（L656/L2020/L2035 依赖行） |
| 跨 plan 清单查询端口 | `src/domain/ports/archive_repository.py:123-131`（`ArchiveRepositoryPort.find`——def 行 :123+方法体至 :131，与范围边界表统一口径） | `async def find(self, query: ArchiveQuery) -> list[StrategicArchive]`——**plan_id=None 即全量跨 plan**（软删过滤+archived_at 降序+offset/limit）；本 Story 多项目段数据源 OD-5 钦定 |
| ArchiveQuery 值对象 | `src/domain/ports/archive_repository.py:39-75`（字段区 :62-75） | 14 键 Query Object（R1 勘误：原稿 15 键系误数——plan_id: UUID\|None 默认 None/limit 1-1000 默认 20——**默认 20 截断防御：服务显式传 1000**）；`__post_init__` limit 范围校验 :80-85（超界 clamp 非 raise） |
| find PG 实现 | `src/infrastructure/storage/postgresql/repository/archive_repository.py:233-250`（`_do_find`） | 软删过滤+多条件+`order_by(archived_at.desc()).offset().limit()`——排序单源（服务层分组不改此序） |
| StrategicArchive.plan_id 可空 | `src/domain/entities/strategic_archive.py:56`（`plan_id: UUID \| None = None`——R1 勘误原稿 :55 漂 1 行）+ 不变量 :48-53 | None 行剔除防御依据（OD-5）；archived_at 字段 :69（**datetime \| None 可空默认 None**——latest_activity_at 派生源+None 排尾口径依据[R1-B2]） |
| archive_repository 注册 | `src/composition_root.py:2315-2326` | SCOPED v1.1.0，lambda 注入 session_factory（6-4 CR1-F1 形态第五成员注记）——SINGLETON 服务捕获注记依据 |
| 报告仓储端口 | `src/domain/ports/report_repository.py:23/:38` | save+`get_latest_by_plan(plan_id: uuid.UUID) -> StrategicReport \| None`（created_at 降序+report_id 降序 tie-break+limit 1——PG :172-177）——报告概况循环数据源 |
| report_repository 注册 | `src/composition_root.py:3513-3521` | SCOPED v1.0.0，PostgreSQLReportRepository(session_factory 注入)——双模式 fallback（CLI 直调可达 :153-161） |
| StrategicReport 实体 | `src/domain/entities/strategic_report.py:57-64` | 八字段（report_id/plan_id[str]/report_type[ReportType 枚举 markdown\|pdf]/file_path/section_count/degraded_section_count/generation_ms/created_at）——投影源 |
| L2 报告表结构 | `deploy/postgresql/alembic/versions/017_strategic_reports.py:21-41` | plan_id 有索引（ix_strategic_reports_plan_id）——N+1 点查性能依据；无 tenant 列（租户隔离 schema 承载注记） |
| PDF 对象键模板 | `src/application/ports/pdf_report.py:79`（`PDF_OBJECT_KEY_TEMPLATE`） | `reports/{plan_id}/{report_id}.pdf`——latest_pdf_object_key=file_path 直传依据（PDF 行 file_path 存此值——6-5b OD-4） |
| 渲染器冻结字体锚 | `src/infrastructure/reporting/reportlab_pdf_renderer.py:60`（`_FONT_NAME = "STSong-Light"`） | BrandSection.font_status 值单源锚（**字面量对齐禁 import**——OD-6）；零品牌扩展点（:96 render 单参亲验） |
| 6-8 报告段对照 | `src/application/ports/executive_view.py:152-167`（`ReportSection` 8 键） | 单 plan 可得性段——与 6-10 ExportSection 语义正交注记依据（OD-7） |
| 6-8 复刻样板（服务） | `src/application/services/executive_view_service.py`（编排 :126-153/四段私有方法+段级 try :155-290） | 段级 try+单时间锚直系样板 |
| 6-9 复刻样板（端口/服务/用例） | `src/application/ports/analyst_view.py`+`services/analyst_view_service.py`+`use_cases/get_analyst_view.py` | 最近直系样板（2026-11-07 交付——五轮代码审查收敛 v1.6.0） |
| CLI 注册样板 | `src/entrypoints/agent_cli.py`：analyst-view 注册 :567-580/异步壳 :1620-1629/打印 :1632-1698/五步定式 :1701-1734（`_ensure_bootstrapped` :101）/分发 :2329-2330 | consultant-view 直系样板（argparse；**零参数面**——本 Story 去掉 add_argument 段与守卫步，四步实态+五步定式名保留注记） |
| CLI 单测样板 | `tests/unit/interfaces/cli/test_agent_cli.py`：6-9 节 :3367-3664（`_make_stub_analyst_view` :3371/`_StubAnalystViewUseCase` :3456/`_patch_analyst_view_entry` :3471-3474） | consultant-view 测试直系复刻（**每命令族专用 patcher 纪律**第三连） |
| 组合根注册样板 | `src/composition_root.py:2102-2139`（analyst_view 双注册块——主会话亲验吻合） | consultant_view 双注册直系复刻（**追加位 :2139 后**；注释块+两 SCOPED 无混态注记+触发器注记） |
| 端口契约测试样板 | `tests/contracts/test_port_contract_analyst_view.py`（五断言族 :21-92——文件总 92 行，族 2 含两函数） | 本 Story 契约测试直系复刻（签名断言零参分立注记） |
| 架构验证样板 | `tests/unit/architecture/test_analyst_view.py`（四验证器 :56-197+SERVICE_ALLOWED_PREFIXES :30-37） | 本 Story 架构验证直系复刻（验证器 C 零命中形态——OD-11） |
| 验收样板（R6 模板） | `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`（243 行）/.py（863 行） | **用户钦定 R6 模板**：AC 横幅分节+@scenario 双行字面量+docstring+pass 形态 |
| 验收样板（6-9 最新） | `tests/acceptance/test_acceptance_analyst_view.py`（1545 行——R6 合规最新形态） | 三件套 :148-208/双清 :161-167/context dict :177-208/CLI 直调 :717-738——本 Story 直系复刻 |
| 归档行预置样板 | 6-7 `_archive_row` :319[编排通道——**本 Story 禁复刻**：archived_at 服务内部生成，R3-F1]+`_teardown_tree_assets` :473[定向清理三步链直系]；**repo.save 直写通道（R5 改钦——与报告行通道对称）**：`StrategicArchive` 实体直构造+`archive_repository.save`[经 L2RdbPort 继承在册 l2_rdb.py:36+PG 实装 :191+`_to_model` archived_at 直传 :108-127]；PG model 直写[ArchiveModel+add]为备选；raw INSERT 备选先例 6-9 documents 直插 :547-554 | 多项目段归档行预置（archived_at 未来偏移可编程——OD-13①；定向清理复刻 6-7 teardown 链） |
| 报告行预置通道 | `report_repository.save(report)`（PG 直写——**集成直写先例 6-8** `_save_report` acceptance :504-512/integration :383/:454 均单参调用[R1 勘误：原稿「6-5a 集成先例」标签错挂——metadata 两参实调先例仅 6-5a 单测 test_report_repository.py:117]）+ `StrategicReport` 构造（八字段——6-8 `_make_report_entity` :448-461 样板） | 报告概况预置直写通道（markdown+pdf 双行+时间戳未来偏移判别构造[OD-13]） |
| 6-8 遮蔽教训锚 | 6-8 R2「未来秒级 timestamp×闭区间出窗→递减微秒偏移」裁定 | 预置时间戳判别构造纪律（本 Story 未来偏移形态自基准 now 微秒级递减——Task 0.5/OD-13①；量级口径微秒[非 ≥1s]——三 plan 相互判别+背景行免疫双目标） |
| 6-8 差值断言体系锚（R1 新增） | `tests/acceptance/test_acceptance_executive_view.py:627-641/:783-788`（audit_baseline_total 基线+delta 断言）+:87-89（R2-F2 排除集不可收缩注记）+`tests/integration/test_integration_executive_view.py:436`（R1-F6「绝对空断言不可写」） | 共享库全局面断言体系先例（OD-13 四件套的直系样板——基线查询/差值/子集对照/空态分立） |
| report 异常码段 | `src/domain/exceptions/_code_ranges.py:199-212`（report 域注释区+映射行——R4 统一口径；490-493 已用注释 :199-208/494-499 预留 :210） | 零新码不占预留依据（OD-3） |
| 冻结键数基线 | `tests/contracts/test_event_channel_mapping_pdf_report.py:24` 等（三处 56） | `_FROZEN_EVENT_COUNT=56`——零新增事件守护（Task 4.2） |
| deferred-work 锚位 | `_bmad-output/implementation-artifacts/deferred-work.md`：L13/L17/L107/L117+L170/L127/L129（Epic 6 锚七行归并六组）+L369/L370（6.5a-DF）+L395/L396（6.7-DF）+L402/L403（D6-8-R）+L409（D6-9-R1-1） | 锚定义务 11 行处置原文位（Task 0.7——主会话亲验行号 2026-11-08） |
| MVP 单租户先例 | `src/application/ports/pdf_report.py:54-58`（tenant_id 构造参数 docstring「多租户归后续 Story」） | 租户隔离展示口径注记援引先例（OD-1） |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-10 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L13（灰度推进/per-version 统计视图） | 工具版本统计视图（触发=产品立项） | **第七轮同构不触发，锚位维持**（OD-8）：多项目段是 plan 维度聚合非工具版本统计面；注记落档 |
| 2 | L17（langgraph retry/timeout 字段） | 触发=checkpoint_table/图引擎字段消费方 | **第七轮同构不触发，锚位顺延**（OD-8）：纯读侧聚合零图引擎/零 checkpoint_table 消费（五轮+6-9 先例延续）；注记落档 |
| 3 | L107（B2 事件驱动摄取+持续数据供给） | 触发=Epic 6 首个 Skills 消费场景定型 | **不触发**（OD-8）：本 Story 零 Skills 消费（无 skill_selector 依赖——比 6-9 工具箱段消费更远）；锚位不变；注记落档 |
| 4 | L117/L170（RabbitMQ 消费侧零接线+事件消费基建四件） | 触发=首个消费方 Story | **顺延 Epic 8**（OD-8）：纯查询聚合面零事件订阅（九连零消费延续）；注记落档 |
| 5 | L127（unified_storage+L0/memory 12 端口休眠） | 触发=Epic 6（多轮顺延） | **第七轮同构不触发，锚位顺延**（OD-8）：纯读侧聚合零记忆消费（6-1/6-3/6-9 同款）；注记落档 |
| 6 | L129（orchestration_service/data_pipeline 轨） | 再锚定=批量报告管线需求（6-11/Epic 7） | **第五轮维持注记顺延+显式不做批量裁定**（OD-8）：读侧聚合非批量报告管线（6-5a/6-5b/6-8/6-9 四轮同构+本 Story 主动收窄：批量导出不立项，白标导出=单 plan 单次归 report-generate 既有入口）；再锚定条件「6-11/Epic 7」不变；注记落档 |
| 7 | L369/L370（6.5a-DF1 REST 导出面/DF2 L0 撕裂） | 触发=Epic 7 API 入口立项 | **顺延 Epic 7**（OD-8）：CLI-only 形态触发条件不含本 Story（6-8 处置先例延续）；注记落档 |
| 8 | L395/L396（6.7-DF1 finding 级引文/DF2 bbox 四元组） | 锚位 Epic 21/22 | **锚位维持 Epic 21/22**（OD-8）：CLI-only 无 Web 高亮/句级面（6-8/6-9 维持先例延续）；注记落档 |
| 9 | L402/L403（D6-8-R1-1 CLI .env 加载/R1-2 json_chain S 编号） | 触发=CLI 入口标准化/下次触及 | **非 6-10 修复面维持**（OD-8 第三连）：新增子命令沿用既有 agent_cli 入口形态（.env 缺口波及全命令族非本 Story 引入）；json_chain 文件零触碰；注记落档 |
| 10 | L409（D6-9-R1-1 CLI `*--plan-id` 命令族非 canonical UUID 观察项） | 触发=CLI 输入标准化专项或 7-2 REST 契约 | **不入命令族注记**（OD-8）：consultant-view **零 `--plan-id` 输入面**——该观察项波及面（`*-view`/trace-tree 等 `--plan-id` 命令族）不含本命令；锚位不变；注记落档 |
| 11 | （新增观察面候选登记评估） | 品牌段 V1 恒默认态的 6-11 对接锚 | **不登记新锚**（裁定：BrandSection.configured 是 VO 契约面非 deferred-work 留项——6-11 实施时经端口版本演进 v1.1.0 承载，触发器 docstring 注记已足；登记属双源冗余） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-9 分析师视图](./6-9-analyst-view.md)（五轮文档审查+五轮代码审查收敛 done v1.6.0——2026-11-07）+ 6-8（四段聚合+段级容错+audit 白名单投影）+ 6-5a（并发采样）

**关键学习/Key Learnings:**
- **Agent 误报主会话复核**（五连教训）：调研结论关键锚点主会话亲验后方可入 Story——本 Story 已亲验 18 组关键事实（epics 六行原文/ArchiveQuery 14 键[R1 勘误：创建期自报 15 键系误数——四调研+主会话双重复核定谳 14]与 limit 默认 20/find PG 实现排序软删/StrategicArchive.plan_id 可空+不变量/archive+report 两注册名行号 lifetime/ReportRepositoryProtocol 仅两方法/StrategicReport 八字段/017 表列+plan_id 索引/PDF_OBJECT_KEY_TEMPLATE/_FONT_NAME :60+render 单参/consultant 词族全域零命中/CLI 16 命令族+样板四区行号[命令参数形态 R1 复核补全四分类]/组合根 analyst_view 块 :2102-2139 吻合/_FROZEN_EVENT_COUNT 三处/report 码段 490-493 已用/openapi 零视图端点/deferred-work 11 锚行号/MVP_TENANT_ID docstring 先例）
- **读侧消费既有冻结面纪律**（6-5b/6-7/6-8/6-9 直系）：两源全既有端口消费零演进——find 既有跨 plan 查询首个应用层消费+get_latest_by_plan 第二消费方循环形态；纯三零第二连
- **降级哲学段级化演进**（6-5b 节点→6-7 树形→6-8 段级→6-9 段级+两层哨兵→本 Story **双段联动**）：派生段结构性依赖主源段→联动降级诚实语义（OD-12）——段级容错族的复合段新形态
- **投影白名单+恒在段**（6-8 审计 15 键→6-9 ToolMetadata 18 字段面→本 Story StrategicReport 八字段投影六键）：展示面 VO 只投影消费键（generation_ms/metadata JSONB 不入 ProjectSummary——呈现面零消费）；brand 段零 IO 恒在段（6-9 toolbox 静态恒在段镜像）
- **断言判别力**：exact set 键集/计数恒等式三联（plan_count==len/plans_with_reports==sum/plans_with_latest_pdf==sum）/行序降序判别（时间戳递减偏移构造）/latest 遮蔽判别格（先 pdf 后 markdown→pdf 计数 0）/None 行剔除防御格/品牌 V1 事实断言（预期演进信号语义）
- **CLI 直调双清**（6-6 R3-1 实跑证伪教训第三连）：clear_singleton+clear_scoped 双清+禁二次 bootstrap——S7/S8 钦定直系
- **性能口径差声明**（六连纪律）：P95/并发/既有面指标（导出<1min 归 6-5b）+继承面口径（隔离 100% 归 1-11 合规面承载+S11 正向可见性——OD-13）三段落 OD+docstring
- **实施攻坚预防**（6-9 五项教训前置）：注释措辞纪律（禁 `--plan-id`/`--format` 字样入新注释块——防 getsource 切块断言边界污染）/BDD 步骤文本重复绑定合并自足/时间戳显式偏移构造（6-8 出窗教训）/ruff format 提交前亲验/集成 collection 场景级生命周期幂等

**应用到本故事/Applied to This Story:**
- [x] 18 组关键锚点主会话亲验（创建期已执行——锚点表承载）
- [x] 两既有端口零演进+组合消费（OD-5/OD-10）
- [x] 段级容错+双段联动+空态幂等读第六连（AC-5/OD-12）
- [x] 投影白名单/exact set/恒等式三联/行序判别/遮蔽格五类断言形态（Task 2 矩阵）
- [x] CLI 双清+禁二次 bootstrap（S7/S8）
- [x] 性能三段口径差声明（OD-8）
- [x] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep

### 其他约束速查

- **风险集中登记**：①口径风险=排序与 latest 遮蔽与 latest_pdf 选择口径（Task 0.2 冻结五口径唯一版本+单测矩阵全枚举——同时间戳 tie-break 格+遮蔽格+双 plan pdf 判别格+None 时间戳排尾格）；②契约风险=五 VO 键契约+品牌恒值（Task 0.1 冻结——实现禁增删键禁改默认值）；③清理风险=PG 面三分面（A 编程面回滚式/B CLI 面 clear_session+commit+定向 DELETE 行数断言/C 并发面禁 set_session 每路独立——6-8/6-9 直系第三连；归档行+报告行双资产定向清理）；④判别风险=品牌 V1 事实断言语义注记（防误判 flake——预期演进信号）+行级 None 同形（段哨兵唯一区分面——OD-12）；⑤性能风险=N+1 点查+find 截断双联（MVP 量级远小于门限——立项锚 Epic 7/21 docstring 注记）+背景 distinct plan 量级（>50 skip 门——OD-13）；⑥装配风险=两依赖注册名漂移（lambda resolve 以 grep 为准——Task 0.8 复核；本 Story 锚点按 HEAD@b9525f8b 校正）；⑦**共享库背景行风险（R1 新增——本 Story 最大结构性风险）**=全局无窗查询见全库已提交行（R1 实测 3 条背景归档行）——断言体系四件套硬纪律（未来偏移/差值/包含格式/绝对空态分立——OD-13；dev 实施时 Task 0.5/Task 5 场景断言禁回退绝对计数断言）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore/pylint disable；提交信息禁 AI 署名
- **覆盖率**：整体 ≥80%（基线 93%）/ application ≥85%（主改动层——epics L2503 对齐；新增文件 ≥95%）/ domain ≥90% 维持 / 集成 ≥75%（epics L2504 对齐）
- **验收零 mock 全真实**（pytest.skip() 动态跳过；双通道真实服务——PG 归档行+报告行；段级异常容错归单测 AsyncMock——验收面无故障注入通道，6-8/6-9 分立同款第三连）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）
- **xdist 串行组**：pytestmark `xdist_group("blm-planning-perf")` 整模块挂法（6-7/6-8/6-9 同组第四连）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（create-story：GLM 调度） |
| **Version** | create-story workflow（bmad-create-story skill v6.3.0） |
| **Execution Date** | 2026-11-08 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.10 定义 L2476-2516；依赖行 L656/L2020/L2035；Epic 20 L600/L714、Epic 21 L3354+、Epic 22 L3388+） |
| **架构文档** | `docs/architecture/architecture.md` + `docs/architecture/arch-appendix.md`（Schema per Tenant 伪码 :1297-1362——未实现注记）+ `docs/architecture/interface-design.md`（三视图表陈旧口径注记先例） |
| **UX/需求规范** | `_bmad-output/planning-artifacts/prd.md`（FR-SP-16 L1898-1901/FR-IF-05 L2199-2204/白标假设 L423-424/多租户 L1474+L2607/顾问 Persona L674-708）+ `ux-design-specification.md`（顾问视图布局差异化 L1401-1405/品牌配置旅程 L2100-2119）+ `roadmap.md`（白标 L29/L60/L73/L114） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-9-analyst-view.md`（v1.6.0 收敛定稿——直系样板） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 实现计划与规范冻结 Implementation Plan & Frozen Specs（Task 0——dev-story 实施时落档）

#### Task 0.1 五 VO 键契约冻结表（实现禁增删键）

| VO | 键数 | 键清单（序=字段序） |
|---|---|---|
| `ConsultantView` | 5 | generated_at: str / build_degraded: bool / projects: ProjectsSection / brand: BrandSection / export: ExportSection（**无 plan_id 键**——全局视图零输入 OD-1） |
| `ProjectsSection` | 4 | available: bool（==plan_count>0） / degraded: bool / plan_count: int / projects: tuple[ProjectSummary, ...] |
| `ProjectSummary` | 6 | plan_id: str / archive_count: int / latest_activity_at: str \| None / latest_report_type: str \| None（值域 None/"markdown"/"pdf"） / latest_report_at: str \| None / latest_degraded_section_count: int \| None |
| `BrandSection` | 5 | degraded: bool（恒 False） / configured: bool（恒 False V1） / logo_status: str（恒 BRAND_STATUS_UNCONFIGURED） / color_scheme_status: str（同上） / font_status: str（恒 BRAND_FONT_STATUS——"STSong-Light（内置）"） |
| `ExportSection` | 7 | available: bool（==plans_with_reports>0） / degraded: bool（与 projects 段联动） / plans_with_reports: int / plans_with_latest_pdf: int / latest_pdf_plan_id: str \| None / latest_pdf_object_key: str \| None / latest_pdf_generated_at: str \| None |

**常量冻结**：`BRAND_STATUS_UNCONFIGURED = "未配置（系统默认）"` / `BRAND_FONT_STATUS = "STSong-Light（内置）"` / `PANEL_ARCHIVE_LIMIT = 1000`——三常量均 ports 文件模块级。

构造守卫（`__post_init__` 抛 242）：plan_id 非空字符串；latest_report_type ∈ {None, "markdown", "pdf"}（值域守卫 R1 补——值域外字符串静默通过会使 plans_with_reports 入计而 pdf 计数漏计，语义悬空；**值域钦定模块常量 frozenset 单源**[演进单点]+**6-11 对接触发器对称注记[R4-F6]**：6-11 新增 report_type[如 branded_pdf]时服务 str 化直传→守卫抛 242 属预期演进信号[与 BrandSection configured 演进信号对称]；**守卫 raise 落位钦定**：ProjectSummary 构造不得落 OD-12 循环级 try 内——否则「新类型未适配」被误表为「拿不到」降级[演进信号须走顶层红非段降级]）；计数 ≥0（plan_count/archive_count/plans_with_reports/plans_with_latest_pdf）；latest_degraded_section_count ≥0 或 None。**派生键不设守卫的明示裁定（R1）**：available 恒等式（==对应计数>0）不设构造守卫——available 是服务派生投影键，stub 直构矛盾 VO 属测试自身缺陷由断言面暴露，守卫面收窄到「外部输入可错的字段」（plan_id/值域/计数非负），禁扩到服务内派生键。**空态/段降级共用默认值钦定**：plan_count=0/projects=空 tuple/两计数 0/latest_pdf 三键 None/brand 五键恒默认——brand 段无空态（恒在段）。

#### Task 0.2 排序与派生口径冻结

```python
# 口径一（行序钦定——确定性排序）：latest_activity_at 降序（最新活动优先——顾问作业面
# 语义），同时间戳 tie-break plan_id 字典序升序（判别确定性）。latest_activity_at 为
# None 的行恒排尾（该 plan 全行 archived_at=None 时可达——StrategicArchive.archived_at
# 可空默认 None，_do_find 的 order_by 不过滤 NULL；None 与 str 不可比较故钦定排尾位）。
# 实现形态钦定（可执行——str 不支持一元负号，禁写 key=(-ts, plan_id) 伪码；禁
# reverse=True 整键反转——会连带把 tie-break plan_id 反转为降序）：两趟稳定排序
#     rows = sorted(rows, key=lambda r: r.plan_id)            # 第二键升序先排
#     rows = sorted(rows, key=lambda r: r.latest_activity_at or "", reverse=True)
#     # None 排尾：非 None 时 ISO 字符串字典序==时间序；None 归一 "" 在 reverse 后居尾
# （等价形态：functools.cmp_to_key 显式比较器；禁依赖 find 返回序——find 序是行级
#  archived_at 降序非 plan 聚合序，两序分立注记）。
#
# 口径二（latest 遮蔽）：latest_report_type == get_latest_by_plan 结果直判（created_at
# 降序首行唯一）——plans_with_latest_pdf 计「最新为 pdf 的 plan 数」非「历史曾生成计数」
#（先生成 pdf 后又生成 markdown 的 plan 不入 pdf 计数——「当前交付物形态」呈现语义）。
#
# 口径三（latest_pdf 三键选择）：latest_pdf_* 取 latest_report_type=="pdf" 的
# ProjectSummary 中 latest_report_at 最大者（tie-break plan_id 字典序升序——与口径一
# tie-break 一致；全无 pdf 行时三键 None）。多 plan latest 均 pdf 的取谁由本口径唯一
# 钦定（禁「行序首个 pdf」备选——两口径在 tie-break 方向分叉）。
#
# 口径四（None 行剔除）：StrategicArchive.plan_id is None 的行不入 plan 清单（防御性
# ——当前写侧恒带 plan_id，None 仅可达于手工修数/未来写入方）。
#
# 口径五（双段联动降级）：find 异常或循环内单 plan get_latest_by_plan 异常 →
# projects.degraded 与 export.degraded 同置 True（派生源受损联动）；brand 段零降级面
#（零 IO 恒稳）。
```

（实现形态 dev-story 时按冻结口径落码；五口径与 AC-2/AC-4/AC-5 逐字对齐。）

#### Task 0.3 端口契约定义

- `ConsultantViewPort`（应用层 `src/application/ports/consultant_view.py`，`@runtime_checkable Protocol` v1.0.0）：`async def build_consultant_view(self) -> ConsultantView`（**零参数**——全局视图）
- 两依赖注册名（组合根既有——主会话亲验 HEAD@b9525f8b）：`archive_repository`（:2315 SCOPED v1.1.0）/ `report_repository`（:3513 SCOPED v1.0.0）
- 组合根双注册：`consultant_view_service`（SINGLETON，tags=("consultant","view","application")）+ `consultant_view_use_case`（SINGLETON，tags=("consultant","use_case","application")）——落位 :2139 analyst_view_use_case 块之后
- 契约测试：`tests/contracts/test_port_contract_consultant_view.py`（五断言族）

#### Task 0.6 逐场景红锚符号表（12 场景预期形态）

> **前置条件（Task 0.5 硬纪律）**：BDD py 模块级零 consultant_view 词族 import——否则收集期 ImportError 全文件 ERROR，下表场景级红形态全部不可达。

| 场景 | 红阶段形态（Task 0.5 运行实测） |
|---|---|
| S1~S6/S10/S11 | 运行期 ImportError（`consultant_view` 模块缺失——预置/构建步骤延迟 import 抛出） |
| S7/S8 | CLI 未注册 → argparse invalid choice exit 2 → 断言步红（`cli_exit_code == 0` 断言失败） |
| S9 | 性能场景 ImportError 同 S1 形态（服务符号缺失） |
| S12 | Then 文件不存在 AssertionError（`_COMPLETION_SRC_FILES` 路径缺失） |

（**红锚演进注记**——6-9 R3-F7 直系：红锚形态随实现 Task 落地演进——Task 1 后 ImportError 从 ports 模块迁至 services 模块→Task 2 后迁断言/注册红——属预期非做错信号；中途零意外绿推演：全场景依赖服务符号或注册名，部分绿仅出现在其依赖 Task 完成后；Task 1→2→3 串行（Task 2 断言需 Task 1 VO 符号）隐含于任务序，dev 按序执行。）

#### 12 验收场景钉死（S1~S12）

| 场景 | AC | 内容摘要 |
|---|---|---|
| S1 | AC-1 | 全数据三段 5 键 exact set+嵌套键集+值级（AC-1 双 plan 形态：**membership 全含双 plan+各恰一行**+两行 archive_count 直推+latest_pdf 定位三键与预置直推[未来偏移]+计数恒等式三联——三 plan 扩展形态归 S2——背景行免疫 OD-13） |
| S2 | AC-2 | 多项目段三 plan 形态（plan-A 活动+双报告/plan-B 活动+markdown/plan-C 活动零报告+None 行剔除[差值不含 None 行]——**预置行占首三+内部降序判别**+archive_count 直推+plan-C 报告三键 None） |
| S3 | AC-3 | 品牌段恒默认态（5 键 exact set+五值级恒等——V1 事实断言语义；零 IO 背景行天然免疫） |
| S4 | AC-4 | 导出段派生（预置行级断言：A/B 行 latest_report_type 非 None/A 行=="pdf"+latest_pdf 定位三键与预置直推[未来偏移保全库最新]+计数恒等式；零 PDF 对照腿归单测[Task 2 循环 B 承载]） |
| S5 | AC-5 | 空态幂等读核心四断言（零预置 → 5 键恒在+brand 完整默认态+build_degraded False+不抛——绝对空态断言归单测[OD-13 分立]） |
| S6 | AC-5 | **单源契约绊线场景**（零归档行预置+报告行在场 → 报告行 plan_id ∉ 清单 plan 集——R4-F3 诚实重标：ReportRepositoryProtocol 无 plan 枚举 API[get_latest_by_plan 是 plan_id 入参点查]，「从报告行聚合 plan」变异在两端口注入面内无实现通道，本场景当前端口面下恒绿——判别力面向未来端口扩展[6-11/7-x 若加 list/distinct 方法后 union 清单立即红]；段级容错归单测的注记随场景 docstring 承载） |
| S7 | AC-6 | CLI 全数据输出包含断言（预置三 plan 逐行输出+品牌两行+导出段行+提示行 in stdout+exit 0——双清直调；完整输出集断言归 CLI 单测 stub 格[OD-13]） |
| S8 | AC-6 | CLI 输出格式与恒在行断言（真库任意行数下的冒烟面——R4-F4 更名：`项目: 共 ` 模式+brand 两行+提示行恒在+exit 0；「空态输出」精确语义全量归 CLI 单测 stub 空 VO 格[OD-13④ 双承载——验收面不可构造空态]） |
| S9 | AC-7 | 性能 20 轮 P95<800ms（服务面两读窗口+背景 distinct plan 数>50 时 pytest.skip——环境量级敏感） |
| S10 | AC-7 | 并发 20 路全成功+**预置子集过滤后逐路相等**（membership 过滤对照——全集相等禁用 6-8 R2-F2 直系[OD-13]） |
| S11 | AC-7 | 租户隔离**正向可见性**断言（预置 plan 在面板可见+值级直推+membership 全含——「零跨漏」排他断言共享单 schema 下不可判别，归隔离继承口径声明 docstring[OD-13]） |
| S12 | 收尾 | src+四测试目录完成清单存在性断言 |

（epics L2493-2495 架构测试三项对账：多项目显示测试→S2；白标报告测试→S4+口径差声明[导出执行归 report-generate 既有入口——OD-8 docstring 承载]；多租户隔离测试→S11 正向可见性口径[OD-13——1-11 合规面测试承载隔离语义本体]。）

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（L2476-2516+依赖行 L656/L2020/L2035）
- [x] 架构约束从 architecture.md/arch-appendix.md/interface-design.md 提取（三视图表陈旧口径+Schema per Tenant 未实现注记）
- [x] 前一个故事学习经验整合（6-9 五轮双审查收敛样板+6-8 段级容错+6-5a 并发+实施攻坚五项预防）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（五 VO 键契约/排序派生口径/12 场景/Task 0~7 共 8 Task）
- [x] 项目结构对齐统一规范（纯三零 Story 第二连+src 面 3 新建+2 扩展）
- [x] 四 Agent 并行调研（报告白标数据面/多项目快照面/CLI 组合根 R6 模板/治理面与边界）+ 主会话 18 组关键锚点亲验

### dev-story 实施摘要 Implementation Summary（2026-11-08 dev-story 执行）

**交付面**（src 3 新建+2 扩展/tests 8 新建+1 扩展——与项目结构图零偏差）：
- `src/application/ports/consultant_view.py`——五 VO（5/4/6/5/7 键与 Task 0.1 冻结表逐键一致）+三常量（BRAND_STATUS_UNCONFIGURED/BRAND_FONT_STATUS/PANEL_ARCHIVE_LIMIT=1000）+LATEST_REPORT_TYPE_DOMAIN 值域 frozenset 单源+ConsultantViewPort v1.0.0 零参签名
- `src/application/services/consultant_view_service.py`——三段编排（`_build_projects_section` find 全量→None 剔除→分组→循环 get_latest_by_plan→两趟稳定排序；`_build_brand_section` 零 IO 常量构造；`_build_export_section` 纯投影派生[入参=summaries+file_paths 映射——ProjectSummary 白名单不含 file_path，映射是循环结果组成部分]）+双段联动容错（find 级段值降默认/循环级行级 None——两捕获位分立）+单时间锚
- `src/application/use_cases/get_consultant_view.py`——零参透传（无守卫面——OD-3 零输入零畸形面；无守卫面注记测试 inspect.getsource 零 EntityValidationError token 承载）
- `src/entrypoints/agent_cli.py`——consultant-view 零 add_argument 注册（CLI 族首个）+分发+`_run_consultant_view` 异步壳+`_print_consultant_view` 三段打印（getattr 零 VO import）+`_run_consultant_view_cli` 四步实态（五步定式名保留 docstring 差异注记）
- `src/composition_root.py`——双注册块（consultant_view_service/use_case 均 SINGLETON，两 SCOPED 依赖 resolve——OD-10）

**TDD 全循环实证**（红→绿→重构→变异四态留痕）：
- Task 1 VO：21 用例（红=ModuleNotFoundError 21 failed→绿→变异①删 BrandSection.font_status 双红+②常量改值双红→还原绿）
- Task 2 服务：18 用例（红=18 failed→绿→变异五锚[行序反转三格红/遮蔽改全量三格红/双段联动改单段两格红/find 容错改 raise 一格红/None 剔除移除一格红]→还原绿）
- Task 3 用例+CLI：用例 4+契约 6+CLI 8 用例（红=9 failed→绿→变异四锚[共→总两红/品牌注记删除红/导出提示删除红/降级标记置空红]→还原绿；期间一次 Edit 误删 projects_section 赋值行即测得 8 failed 修复——回归防护有效性实证）
- Task 5 集成：4 场景全绿（变异两锚[membership count 1→2 红/并发篡改一路派生值红]——原拟「期望集缺员」形态被断言体系三重冗余兜底不红，改 count 形态直接判别，实施注记留档）
- Task 6 架构：四验证器 13 用例绿（变异 publish token 注入红→还原绿）

**实施攻坚两项**（真缺陷修复）：
1. 预置时间戳单基准锚：初版 `_future_offset` 逐行取 now——微秒级偏移被调用间漂移淹没（集成场景①首三降序断言红实证捕获），修正为 `_preset_anchor()` 单一基准+偏移函数（六预置函数全注入——「禁 now() 双调」纪律的变体形态教训）
2. A 面回查不可见：S1/S4 `latest_pdf` 三键原经独立连接回查预置行——A 面（set_session 事务内未提交）对独立连接不可见（回查 None 红），修正为预置侧登记定位三元组（report_id/file_path/created_at ISO）断言直推——「值级直推」更纯形态

**验证收官**：
- 验收 12/12 场景全绿（S1~S12——S12 完成清单随 Task 6 架构文件落位转绿）
- 集成 4 场景全绿（真实双源 round-trip/空态/P95 实测远低门限/并发 20 路子集过滤对照）
- 四目录全量两轮：第一轮 15260 passed+6 failed（全为本 Story 当轮未竟态）→第二轮 **15280 passed+2 skipped 零失败**
- 覆盖率：新增三 src 文件 100%（63+59+8 语句全覆盖——json 报告实测，≥95% 门禁达成）
- ruff check+format --check 全仓过；mypy 765 文件零错误（基线 762+新增 3）
- 纯三零 git diff 实证：src/domain+src/infrastructure+src/interfaces 三目录零 diff 零未跟踪
- deferred-work 14 锚位处置注记落档（Task 0.7——逐锚行内追加=6-9 先例形态；**分母口径注记（R1-F8 消歧）**：14=锚位**行**实数——Task 0.7 预案的 L117/L170 归并一组在 deferred-work 中是两行、各得一处注记；预案口径「13 锚位」为归并**组**数——两口分母差非计数冲突）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-10-consultant-view.md`

**修改的文件/Modified Files:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 6-10 状态流转 backlog→ready-for-dev

**待创建的文件/To Be Created (Dev Story 实施):** —— 已全部创建/扩展（2026-11-08 dev-story 完成）
- `src/application/ports/consultant_view.py` - 五 VO+品牌两常量+PANEL_ARCHIVE_LIMIT+ConsultantViewPort ✅
- `src/application/services/consultant_view_service.py` - 三段编排+排序派生+双段联动容错 ✅
- `src/application/use_cases/get_consultant_view.py` - 用例（零参透传） ✅
- `src/entrypoints/agent_cli.py` - consultant-view 子命令（扩展——零参数） ✅
- `src/composition_root.py` - 双注册块（扩展——:2139 邻位） ✅
- `tests/unit/application/test_consultant_view_vos.py` - VO 单测 ✅（21 用例）
- `tests/unit/application/test_consultant_view_service.py` - 服务单测（排序派生矩阵+容错矩阵） ✅（18 用例）
- `tests/unit/application/use_cases/test_consultant_view_use_case.py` - 用例单测 ✅（4 用例）
- `tests/unit/interfaces/cli/test_agent_cli.py` - CLI 单测（扩展） ✅（+8 用例族）
- `tests/unit/architecture/test_consultant_view.py` - 架构验证（四验证器） ✅（13 用例）
- `tests/integration/test_integration_consultant_view.py` - 集成测试（四场景） ✅
- `tests/contracts/test_port_contract_consultant_view.py` - 端口契约测试（五断言族） ✅（6 用例）
- `tests/acceptance/test_acceptance_consultant_view.feature` - Gherkin 场景（12 场景——R6 模板） ✅
- `tests/acceptance/test_acceptance_consultant_view.py` - BDD 步骤实现（6-9 R6 合规形态） ✅
- `_bmad-output/implementation-artifacts/deferred-work.md` - 11 条锚定义务处置注记（扩展） ✅（14 锚位行内追加）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.10 |
| **Story Key** | 6-10-consultant-view |
| **File** | `_bmad-output/implementation-artifacts/stories/6-10-consultant-view.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力 / UX 三页面驾驶舱（顾问） |
| **优先级** | P1-10（依赖 Story 6.5b——epics L2020 钦定，PDF 报告生成已 done） |
| **覆盖 FR** | 无独立 FR（跨 plan 聚合展示面——同 6-6/6-7/6-8/6-9 形态第五连；FR-SP-16 白标 REST 归 Epic 20 Story 20.4、品牌配置实现归 6.11、FR-IF-05 三页面归 22.8） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7 含 TDD 循环+变异锚）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7+12 场景钉死）
3. [x] Architecture constraints extracted 架构约束已提取（纯三零 Story 第二连+依赖方向矩阵）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（8 学习点+7 应用项）
5. [x] Sprint status synced to `ready-for-dev`
6. [x] OD-1~OD-13 十三裁定落档（范围收窄 CLI-only 第九连/零事件/零异常+零 242 面/五 VO 键契约/archives 反推数据源/品牌段 6-11 对接锚/导出段纯投影+遮蔽口径/性能三段+锚定义务 11 条/命名/组合根+零参数先例/纯三零/双段联动容错/共享库全局面断言体系[R1 新增 OD-13]）
7. [x] deferred-work 11 行锚定义务处置预案落档（Task 0.7——Epic 6 锚七行归并六组+两条 6.5a-DF 顺延+两条 6.7-DF 维持+两条 D6-8-R 维持+一条 D6-9-R 不入命令族注记——13 锚位归并 10 行处置+第 11 行不登记新锚裁定）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 文档审查修订循环 Round 1~5（D1~D5 形态——四调研 Agent[数据面/CLI 组合根/验收形态/治理面]+主会话亲验+双审查员[①一致性六轴晚归并入/②可满足性推演]+R2 双 Agent[回归传播/组合交互]+R3 单深度+R4 验证清偿+R5 独立终审[配额受限主会话六节承接]。编号规则 R{轮}-Fn（R1-F1~F19/R2-F1~F7/R3-F1~F2/R4-F1~F6 共 34 行）；行号为修复时点快照；台账原文保留+勘误内联（不改历史记录行）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-F1 | 「16 命令族先例均为单 plan 锚定或写命令」全称断言失实（isolation-logs :623 六参数全 required=False 可裸调全局检索；load-profile/isolation-status 为 agent-id 锚定只读）——AC-6/OD-10 两处「均」字断言与「CLI 族首个零参数查询命令」论据链断裂 | P0 | AC-6/OD-10 改「首个零 add_argument 命令（参数面真空）」+16 命令实测四分类（7 plan 读+7 写+2 agent 读+1 可选全局检索）+与 isolation-logs 语义分立点重述 |
| R1-F2 | 共享库全局查询断言体系不可满足：验收/集成 PG 共享库共享 schema（集成为事务回滚式非独立 schema），find(plan_id=None) 全局无窗查询见全库背景行（R1 实测 3 条归档背景行）——S1/S2/S4/S5/S7/S8 绝对计数/行序/空态断言+AC-1「当前租户 schema」表述全部失真；6-8 差值断言体系/R1-F6/R2-F2 三大先例未适配 | P0 | 新增 OD-13 断言体系四件套（预置时间戳未来偏移/distinct plan 集差值/CLI 包含+格式断言/绝对空态断言归单测分立）+8 场景断言口径全面改写（AC-1/2/4/5/6/7+Task 0.5 基线查询步骤+Task 5 集成四场景同步）+风险登记⑦ |
| R1-F3 | S10 并发「排除集单键 {generated_at}」与 6-8 R2-F2「排除集不可收缩」实证教训冲突（全局无窗查询并发窗内受其他 worker 写入抖动；projects/export 全排除则判别力归零） | P0 | 并发对照改「预置 plan membership 过滤后逐路相等」（AC-7/OD-8②/S10/Task 5 场景④/Task 5.4 变异锚篡改位五处联动改写） |
| R1-F4 | 排序冻结口径含不可执行伪码（`sorted(key=(-ts, plan_id))`——str 无一元负号；reverse=True 连带反转 tie-break 方向）+latest_activity_at=None 排序位未冻结（StrategicArchive.archived_at 可空默认 None，_do_find 不过滤 NULL） | P1 | Task 0.2 口径一重写：两趟稳定排序钦定形态（可运行示例码+None 归一 "" 降序排尾）+循环 B 增 None 时间戳格+绿格禁伪码/禁整键反转 |
| R1-F5 | latest_pdf 三键「全局最新 PDF」选择口径未冻结（多 plan latest 均 pdf 时取谁无钦定——单 pdf 预置下两种实现均满足全部已冻结口径） | P1 | Task 0.2 新增口径三（latest_report_at 最大者+tie-break plan_id 升序；禁「行序首个 pdf」备选）+循环 B 增双 plan pdf 判别格 |
| R1-F6 | S6「段级容错分立声明」注记型场景无 Then 可执行断言（6-9 先例每场景均有断言；Task 0.6 又给它分配红形态——绿阶段断言悬空） | P1 | S6 重定义为「单源口径判别场景」（零归档+报告行在场→报告行 plan_id ∉ 清单——判别清单源纯 archives 反推，错接则红；容错分立注记随 docstring 承载）[R2 勘误：原「plan 集差==∅」差值表述随 OD-13② membership 升格同步修订] |
| R1-F7 | ArchiveQuery「15 键」失实（实际 14 键——:62-75 逐字段清点）；StrategicArchive.plan_id :55→:56/archived_at :70→:69 漂移；契约样板 :21-93→:21-92 | P1 | 三处锚点表+范围边界表勘误（R1 勘误内联标注） |
| R1-F8 | find 既有生产码消费方全称断言失准（漏 SummaryGenerationService :441-446 同形态兜底+第二 REST 端点 /plans/{plan_id}+REST 实经 strategic_archive_service.query_archive :315-325 中继）；「应用层服务首个消费」口径过宽 | P1 | 消费方全景改写（两端点中继+两兜底链）+「首个」限定为「plan_id=None 全量清单形态的视图服务消费」+Task 4.3 回归面补 SummaryGenerationService |
| R1-F9 | interface-design.md 三视图表无「顾问行」（第三行=企业战略与市场人员视图——原稿「三视图表（高管/分析师/顾问）」失实） | P1 | L530 改真实锚位（:2001-2007 三行实测+:2090「Story 6.9/6.10」行是真实引用位） |
| R1-F10 | S9 性能背景量级不稳（N=全库 distinct plan 数含背景 plan——环境量级非实现质量；find limit=1000 截断随机丢 plan） | P1 | AC-7/Task 5 场景③/S9 增「预置前清点背景 distinct plan 数>50 pytest.skip」+docstring 环境量级敏感性声明 |
| R1-F11 | 构造守卫缺口：latest_report_type 值域无守卫（值域外字符串语义悬空）；available 恒等式无守卫也无豁免裁定 | P2 | 守卫清单增值域四形态（Task 0.1 冻结表+Task 1 红格联动）+available 派生键不设守卫的明示裁定（守卫面收窄原则） |
| R1-F12 | 双段联动（OD-12 本 Story 唯一新容错形态）无变异锚 | P2 | Task 2.4 增第五锚「联动改单段置位→循环格红」+DoD 4→5 联动 |
| R1-F13 | Task 0.6 符号表成立性系于「py 模块级零 consultant_view import」未钉死（模块级 import→收集期全文件 ERROR→S7/S8/S12 红形态全部不可达） | P2 | Task 0.5 增硬纪律（含类型注解用途禁令——6-9 :55-68 形态逐字复刻）+Task 0.6 表头前置条件注记 |
| R1-F14 | report_repository.save「6-5a 集成先例」标签错挂（集成直写先例是 6-8 executive_view 单参调用；metadata 两参实调仅 6-5a 单测） | P2 | 锚点表报告行预置通道行改真实先例（6-8 `_save_report` :504-512 单参形态） |
| R1-F15 | 「锚定义务 11 条」枚举算术不自洽（6+2+2+1+2=13 锚 vs 11 行） | P3 | Task 0.7 改「13 个锚位归并 10 行处置+第 11 行不登记裁定=11 行」计数口径按行（R1 勘误内联） |
| R1-F16 | 「行宽 128 纪律拆两行」归因不准（输出行 ~78 字符不超源码行宽 128——拆行是信息密度呈现选择） | P3 | AC-6 项目行形态注记改「信息密度呈现形态拆两行[非源码行宽约束]」 |
| R1-F17 | 「禁 --plan-id 字样入注释块」超出 getsource 断言实际 token 面（实测仅 --format/--category/--window-days） | P3 | OD-10 注释措辞纪律改双注记（实际 token 面锚+--plan-id 保持为过度谨慎预防位） |
| R1-F18 | 双装饰器先例不在 6-9 文件（实际锚 autonomous_invocation_route:505-506） | P3 | BDD 约束行补真实先例锚注记 |
| R1-F19 | 调研附带观察：OD-9 词族声明范围（src+tests+configs+docs/api）外有 docs/images/architecture.svg:22 "Consultant View" 图形标签 | 证伪留痕 | 非缺陷——OD-9 声明范围本就限定四代码域且准确（svg 图形域不在内）；登记免后续轮重查 |
| R2-F1 | R1-F2 的差值断言（预置前后集合差==预置集）存在窗口竞态：基线查询后其他 worker 写入外来 plan 入差集即假红（差集无过滤面；6-8 audit 差值是窗内减法窄窗口形态，6-10 集合全等更宽） | P1 | OD-13② 升格 **membership 全含断言**（预置集 ⊆ 清单+各恰一行+行级值直推——外来免疫+判别更强+无需基线查询）——AC-1/AC-2/AC-4/AC-5/S1/S2/S5/S6/S11/Task 0.5 基线步骤[改 S9 专用清点]/Task 5 场景①②/Task 5.4 变异锚 十四处联动+R1-F2/R1-F6 台账勘误内联 |
| R2-F2 | R1-F1 修复引入新算术错：「7 个 --plan-id 必填读+7 写」加总 17≠16（AC-6/OD-10 两处——调研报告计数误差被照抄） | P1 | 主会话逐命令重数定谳 **6 plan 读**[chain-query/checkpoint-list/checkpoint-show/trace-tree/executive-view/analyst-view]+7 写+2 agent 读+1 全局检索=16 加法闭合——两处修正+逐命令枚举内联（审查员①发现） |
| R2-F3 | 常量计数三口径并存冲突：「品牌三常量+PANEL」（4 个）vs 冻结表实际品牌 2 常量+PANEL（3 个）——Task 1 红/绿照字面会造第 4 个常量违冻结 | P1 | 全文统一「品牌两常量+PANEL_ARCHIVE_LIMIT[共三常量]」——7 处修正（L163/L316/L341/L342/L367/L542/L556/L797；OD-11/L701 的「三常量」指全集正确保留）（审查员①发现） |
| R2-F4 | R1-F8 消费方修复的传播漏网：OD-5 行仍留旧口径（「仅 REST+StalenessWeightService」+「应用层服务首个消费」未限定+「亲验 :55」漂移） | P2 | OD-5 全行更新（消费方全景+「plan_id=None 全量清单形态的视图服务首个消费」限定+:56） |
| R2-F5 | R1 修复扇出欠账族（正文已改、汇总/枚举/锚点表未跟随——审查员①系统发现）：零事件「八连」应七连（族枚举 7 员）×3 处；L614 Epic 6 锚漏 L170；完成总结「十二裁定」应十三；L106「六先例族」应五；「6-9 两单一 SCOPED」丢字乱码×2（应为两 SINGLETON+一 SCOPED）；「四口径」应五口径（Task 0.2 重写后 Subtask 0.2 枚举与尾注未跟随+AC-4 缺口径三引用）；find 锚 :120-123/:123-131 两说 | P2 | 十二处定向修正（七连×3/L170 入列/十三裁定/五先例族/乱码复原×2/五口径三联动/锚统一 :123-131） |
| R2-F6 | P3 欠账族：锚定义务旧枚举残留（Task 0 目的/完成总结第 7 条与新按行口径并存）；矩阵 AC-7 行「5.3-5.4」映射错位（应为 5.1-5.2）+AC-4 行漏循环 B；完成标志红形态漏 S9；S4「可选」与钦定矛盾 | P3 | 五处修正（按行口径改写×2/矩阵两行/补 S9/删「可选」） |
| R2-F7 | 疑点证伪留痕：未来偏移免疫假设依赖「其他测试时间戳均为 now/过去」——实地核查 6-7/6-8 归档与报告预置构造形态 | 证伪留痕 | 现存测试均为 now/过去形态（6-7 archived_at 服务侧 now 生成/6-8 created_at=now(UTC)）——免疫假设成立；OD-13① 已加「未来偏移同构形态出现时重评」注记 |
| R3-F1 | 归档行预置通道钦定错误：Task 0.5/隔离表/锚点表/Task 5 引用「6-7 `_archive_row` 直系」——该样板走 `service.archive_plan` 编排通道（archived_at 服务内部生成**不可编程**），与 OD-13① 未来偏移构造结构性冲突；且 ArchiveRepositoryPort **无 save 方法**（六方法枚举实证——写入面在服务编排非仓储），「实体直构造+repo.save」通道亦不可达——dev 照抄样板将卡死或被迫放弃未来偏移 | P1 | 钦定 **PG model 直写通道**（ArchiveModel 构造+session.add+flush/commit——与 `_do_find` 同源模型，A/B/C 三面按既有分派；raw INSERT 备选[6-9 documents :547-554 先例]）——Task 0.5/隔离表/锚点表/Task 5 场景①/工厂收口 五处联动修正；6-7 样板降级为「定向清理链直系+编排通道禁复刻注记」[**R5-F1 勘误**：「无 save 方法」系伪实证——六扩展方法枚举漏 L2RdbPort 基类四继承方法[save/get_by_id/delete/list_all，archive_repository.py:110-115 docstring 明文+PG :191 实装+服务三处生产消费]，repo.save 通道实际可达；R5 终审改钦 repo.save 直写通道（与报告行通道对称），PG model 直写降为备选] |
| R3-F2 | 疑点证伪留痕：S6 任意 UUID 报告行（无对应归档行 plan）的可写性——017 strategic_reports.plan_id 是否有 FK 约束 | 证伪留痕 | 017 :26 纯 Column+索引**无 FK**——任意 UUID 报告行可写 ✓ S6 预置形态成立 |
| R4-F1 | R2-A 回归核查报告的开放项清偿（6 项）：①Task 4.3 回归面未补 SummaryGenerationService（R1-F8 声称联动位漏改——[P1]）②追溯矩阵 AC-5 行未随 S6 重定义联动 ③锚点表 6-8 教训锚「≥1s」与 canonical 微秒级量级冲突 ④Lessons「隔离 100% schema-scoped」旧口径残留 ⑤_code_ranges 引用分裂（:192-212×2 vs :199-211×1）⑥OD-4 守卫摘要未含值域+v1.1.0 版本说明「归单务」笔误 | P1/P3 | 六处定向清偿（Task 4.3 消费方全景[两端点中继+双兜底链]/矩阵 AC-5 行+S5/S6 承载注记/微秒量级统一/1-11 承载口径/:199-212 统一[源码依据：report 域注释区 :199+映射行 :212——原 :192 含 planning 首行]/OD-4 四形态+笔误勘误）；R4 三轴验证并行（锚点 8/8 精确/计数终扫全过：OD 13 行+修复表 28 行+场景 12+加法闭合 3 处+八连零残留/版本脚注一致） |
| R4-F2 | R2-B 第 5 组[P1]：OD-13② 免疫的窗口稳定结构前提未声明且落点缺位——全仓 strategic_archives 提交型写入方仅 6-7 验收/集成+checkpoint 系且全挂 blm-planning-perf 组（拓扑闭合使竞态今日不点火），但 Task 0.5 硬纪律清单漏列 pytestmark xdist_group——dev 逐字实现产出无组验收文件→与 6-7 并行间歇假红（最难溯源形态）；与 R1-F3 已有的并发窗意识不自恰（同一意识未回灌差值窗口） | P1 | Task 0.5 补硬纪律行（pytestmark xdist_group 整模块挂法+结构前提说明）+OD-13② 补前提句与**前向约束登记**（新增提交型归档写入测试必须挂同组） |
| R4-F3 | R2-B 第 3 组[P2]：R1-F6 的 S6「单源判别」宣称在 OD-5 端口面内不可达——ReportRepositoryProtocol 无 plan 枚举 API（get_latest_by_plan 是 plan_id 入参点查——R2-B 实测），「从报告行聚合 plan」变异无实现通道（歪实现由架构验证器 C 拦截非 S6）——S6 实效=恒绿契约绊线 | P2 | S6 诚实重标「单源契约绊线场景」（当前端口面下恒绿——判别力面向未来端口扩展的回归守护[6-11/7-x 加 list/distinct 后 union 清单立即红]；保留场景不删——绊线价值+无假红风险） |
| R4-F4 | R2-B 第 4 组[P3]：S8 场景名「CLI 空态输出」与实效脱节（真库任意行数格式+恒在行冒烟——空态精确语义已全量委托 CLI 单测 stub 格），命名误导后续维护者 | P3 | S8 更名「CLI 输出格式与恒在行断言」+双承载注记显式化 |
| R4-F5 | R2-B 第 1 组附注[P3]：「占首三」依赖的「全库无更新时间戳行」假设未登记（本 Story 首创未来偏移预置模式——后续复刻+清理泄漏即互拆） | P3 | OD-13① 补未登记假设段（互斥登记义务+≥1s 显式量级备选）+第 2 组证伪留痕并入（断言全直推相等无 now 比较面） |
| R4-F6 | R2-B 第 7 组[P3]：值域守卫缺 6-11 演进触发器对称注记（BrandSection 有此注记）+守卫 raise 若落 OD-12 循环级 try 内会把「新类型未适配」误表为「拿不到」降级（演进信号被劫持为段降级——部分掩埋） | P3 | 值域守卫处挂 6-11 对称注记+值域钦定 frozenset 模块常量单源+**守卫 raise 落位钦定**（ProjectSummary 构造不入循环级容错位——演进信号走顶层红） |
| R5-F1 | R3-F1 事实谓词被终审四重证据证伪：「ArchiveRepositoryPort 无 save 方法（六方法枚举实证）」——枚举只数本文件六扩展方法，漏 L2RdbPort 基类四继承方法（save/get_by_id/delete/list_all——archive_repository.py:110-115 docstring 明文+PG :191 实装+strategic_archive_service :124/:249/:443 三处生产消费）；「写入面在服务编排非仓储」架构表述颠倒；且 repo.save 通道可达且与报告行通道完全同构（更简通道被错误排除——同 Story 两资产通道不对称） | P1 | 改钦 **repo.save 直写通道**（StrategicArchive 实体直构造[archived_at 可编程]+archive_repository.save[_to_model :108-127 archived_at 直传]——与报告行 _save_report 通道对称）；PG model 直写降为备选；Task 0.5/隔离表/锚点表/Task 5 场景①/工厂收口 五处联动+R3-F1 台账勘误内联（伪实证教训留档：**端口方法枚举必须含基类继承面**） |
| R5-F2 | OD-13 尾句 S6 复述未随两轮升格联动：残留 R1 期「plan 集差==∅」差值措辞（R2 membership 升格只改了台账未改本句）+「判别清单源」主动判别语义（R4-F3 绊线重标只改了场景表）——活性 OD 行内扇出欠账（R2-F5 同类第三例） | P2 | OD-13 尾句改 membership 措辞+绊线重标语义（一次改写双联动） |

### 📋 文档审查循环收敛声明（Round 5 终审定稿——v1.3.2 随收敛提交生效）

**周期概述**：Story 6-10（顾问视图——三段聚合查询+CLI consultant-view 零参数全局视图）2026-11-08 创建（v1.0.0，aa63914e），随后完成五轮文档审查修订循环（D1~D5×5），收敛于 v1.3.2。

**五轮结构**：R1 四调研 Agent+主会话亲验+双审查员（19 项）→ R2 回归核查+组合交互+审查员①一致性六轴晚归并入（7 项）→ R3 单深度推演·预置通道深水区（2 项）→ R4 纯验证+双 Agent 晚归清偿（6 项）→ R5 独立终审双向取证 12 项+全文终扫+门禁/收敛判据（2 项特权发现随收敛提交清偿）。

**处置统计（按修复表实际行数）**：36 行 = P0×3 + P1×14 + P2×8 + P3×8 + 证伪留痕×3。核心结构裁定：新增 **OD-13 共享库全局面断言体系**（未来偏移/membership 全含/包含格式断言/绝对空态分立四件套+并发子集对照+隔离正向可见性+性能量级 skip 门——8 个验收场景断言口径全面重造）；Task 0.2 冻结口径 4→5（latest_pdf 选择+None 排尾+可执行两趟排序）；S6/S8 诚实重标；归档预置通道终定 repo.save 对称通道。

**收敛判据达成声明**：① 周期闭合 ✅（六提交链[创建+R1~R5]全部仅涉本 Story 文件/工作区干净/零游离）；② 关键修复落地 ✅（36 项全落地，R5 终审双向取证 12/12[含 R5-F1 对 R3-F1 的证伪勘误闭环]）；③ 计数与残留终扫 ✅（OD 13 行/修复表 36 行/场景 12/键数四处/五版本链/活性旧口径零残留——终审第三节）；④ 门禁结构 ✅（ready-for-dev 维持/Next Steps 勾选/deferred-work 11 行三处一致）；⑤ 零 P0/P1 残留 ✅（R5 特权发现 2 项已随本收敛提交清偿——「不轻信自报」终审实证有效第十次复现）。

**遗留事项**：无 P0/P1/P2 残留。信息级留痕：修复表 blurb 轮次覆盖已扩（R{轮}-Fn）；R3-F1 伪实证教训（端口方法枚举须含基类继承面）与「未来偏移预置模式」前向约束（OD-13①/②登记）供后续 Story 援引。

**放行建议**：✅ **放行 dev-story**——五轮收敛达成，文档 v1.3.2 为实施基线。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-11-08（Round 1）
**审查模式:** full（四视角并行调研+双评审员 C3 门禁——6-9 审查形态直系；R1 四视角=A 契约符合性/B 测试判别力/C 真实通道隔离纪律/D 运行面实测——零 P0/P1，运行面全量 15280 passed+2 skipped 零失败/三 src 覆盖 100%/纯三零 diff 实证全复核属实）

#### 需决策 Decision Needed

- 无（Round 1 双评审员①裁定优秀+②最小清单增补，合并后落码——无悬置决策）

#### 已修复 Patch

| # | 严重度 | 问题 | 修复 |
|---|--------|------|------|
| R1-F1 | P2 | CLI 段降级呈现与 OD-12 两形态分立错位：循环级降级（清单保留+行报告列 None）时已取到的全清单被丢弃、统一降「项目清单获取失败」——VO 层「部分降级」语义在呈现面失真（AC-6 原文仅定义单形态——规范缺口，服务层两形态分立本身正确） | `_print_consultant_view` 分支拆两形态：`degraded+空清单`（find 级——服务段值降默认的结构不变量：degraded 仅在分组循环内置位⟹循环级清单恒非空）降获取失败单行；`degraded+清单保留`（循环级）照常呈现清单+行内「最新报告: 无」+首行降级标记承载信号；既有降级格整形为 find 级格（plans=()+plan_count=0+导出七键置零——矛盾 VO 纪律）+新增循环级格 `test_partial_degraded_keeps_listing`；docstring/AC-6 L121/L130/L417 三承载位联动（评审员①2×2 完备格证明+②stub 整形联动位——突变实证：删判别键→循环级格红→还原绿） |
| R1-F2 | P2 | `test_empty_state_defaults` 半恒真回读（显式传默认值再断言回读）——ExportSection 七键默认值全仓零承载位（服务恒显式传七键、VO 测试经工厂显式传值），默认值漂移无测试变红 | 改零参裸构造断默认（ProjectsSection 四键+ExportSection 七键——find 级降级路径 load-bearing 契约面；突变实证：latest_pdf_plan_id 默认改值→红→还原绿） |
| R1-F8 | P2 | DoD 完成总结七项全未勾而 v1.4.0 自报「DoD 全过」（6-9 done 终态同位七项全勾——F-1 勾选卫生缺口第三例）；L815「14 锚位」vs Task 0.7「13 锚位」两口分母差无消歧（评审员②发现） | 七项补勾 `[x]`；L815 补分母口径注记（14=锚位行实数[L117/L170 一组两行拆计] vs 13=归并组数——非计数冲突） |
| R1-F3 | P3 | 「变异 13 锚」计数笔误——分项枚举 2+5+4+2+1=14（与已纠正的 R1-F15/R2-F2 同族；L949/L959 两处；同文件另有 4 处「13 锚位」系 deferred-work 概念不误伤） | 两处 13→14 勘误（评审员①分项亲验闭合） |
| R1-F4 | P3 | ports :9「Story 6.11」连字符——全仓统一「6-11」（唯一命中位） | 改「6-11」 |
| R1-F5 | P3 | `_run_consultant_view` docstring 引用「代码审查 R1-F17」对本 Story 为伪溯源（dev 期照抄 6-9 形态——本 Story 审查无此编号；存量 7 处同注记系 6-4~6-9 期合入不动） | 去编号改实名（「同 _run_analyst_view 注记：resolve 抛出时 finally 仍关闭连接池」——真源性优先于形态统一） |
| R1-F6 | P3 | 验收 context fixture `_monkeypatch_ref` 登记后全程零消费（死产物；`_capsys_ref` 有两处真消费保留） | 删除该行 |
| R1-F7 | P3 | Story L128/L417「三 plan 六行」失实——CLI stub 实际 2 plan 四行（判别力等价：两行覆盖有/无报告两形态） | 两处措辞勘误（「两 plan 四行」；L128 同句验收半句「预置三 plan」保留） |
| R1-F9 | P3 | CLI stub 工厂 docstring「plans 五元组」实列六元素（plan_id/archive_count/latest_activity_at/latest_report_type/latest_report_at/latest_degraded_section_count） | 勘误「六元组」（随 R1-F1 同文件顺手修——评审员②发现） |

#### 已推迟 Defer（留档注记——非缺陷或先例一致）

- VO 守卫 8 格中 3 格仅断异常类型未断 code（代表格有 `code=="EXCEPTION_242"` 断言、模块单异常类仅守卫 raise——替换遮蔽风险低）
- 服务单测循环级容错格 side_effect 为按 plan_id 分派函数（Story 钦定「列表形态」）——顺序无关判别等价且更强，良性偏离注记
- 架构验证器 C 的 rglob 零命中为文件名级匹配（Story 措辞隐含内容级）——主会话内容级 grep 实证当前零命中，当下等价留档
- `test_generated_at_single_time_anchor` 判别力弱于命名（「单次 now」无行为可观测面——结构性不可测，注记性测试）
- limit 覆写行为断言不判别「传入超上限被 clamp」形态（对钦定变异形态[默认 20 截断]判别成立）
- 并发对照含未过滤 plan_count/available/degraded 键——等价性依赖 blm-planning-perf 组串行前提（R4-F2 前向约束已在册）
- 验收 teardown 非 AssertionError 异常 print 容错（6-9 同款先例一致——行数断言 AssertionError 正确 re-raise）
- S9 性能 skip 门计数经 `find(limit=1000)`——背景行超千级时 distinct plan 数被截断低估（archived_at 降序近似合理；量级逼近 50 阈值时改 SQL COUNT(DISTINCT)——deferred 触发条件）
- 集成 `_fresh_resolver_per_test` 为 async fixture（6-9 是 sync monkeypatch 形态）——asyncio_mode=auto 下可用，语义等价最小偏差
- 集成场景④在剥掉 `-n auto --dist loadgroup` 的非标准形态下偶发时序敏感（标准门禁形态 3 次全绿——R4-F2 组串行正是免疫手段，非门禁风险）
- CLI stub 工厂导出段默认值形态（无 latest_pdf_plan_id 显式 None 时的三键派生）与生产 ExportSection 构造面存在形态差——stub 内部自洽已由矛盾 VO 纪律约束（R1-F1 整形后两降级格显式置零）
- 本地 `.env` PG 凭据失配致 CLI 真实运行多项目段降级（预存环境问题与本 Story 零交集；降级路径行为本身正确且被双测覆盖）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行文档审查修订循环（参照 6-7/6-8/6-9 五轮形态——R1 四视角调研+双审查/R2 回归+组合/R3 单深度/R4 纯验证/R5 独立终审；五轮收敛 v1.3.2——收敛声明见 Docs Review Fixes 节；六提交 486fb0e1→85706c14→8366d2af→72d8291a→本收敛提交）
- [x] 运行 `dev-story` 开始实施（2026-11-08 完成——Task 0~7 全勾：12/12 验收全绿+四目录全量 15280 passed+2 skipped 零失败+新增三 src 文件覆盖率 100%+mypy 765 零错+变异 14 锚全实证+纯三零 diff 实证——详 Dev Agent Record 实施摘要）
- [ ] 运行 `code-review` 进行代码审查（auto-marks done）
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-11-08
**最后更新/Last Updated:** 2026-11-08
**更新说明/Description:**
- v1.5.0: 代码审查 Round 1（四视角并行调研+双评审员 C3 门禁——评审①裁定优秀[2×2 完备格证明]+②最小清单增补[stub 整形/DoD 补勾/六元组]后落码）：P2×3+P3×6 落码 9 项——**R1-F1** CLI 段降级呈现拆两形态（OD-12 呈现面对齐：find 级[degraded+空清单]降获取失败单行/循环级[清单保留]照常呈现+行内「最新报告: 无」+首行标记；判别键结构不变量=服务 degraded 仅循环内置位⟹循环级清单恒非空；既有降级格整形 find 级+新增循环级格——双突变实证）；**R1-F2** VO 空态默认测试改零参裸构造断默认（ExportSection 七键默认值获承载位——突变实证）；**R1-F8** DoD 七项补勾+deferred-work 14/13 锚位分母口径注记（行数 vs 组数）；R1-F3/F7 Story 计数措辞勘误（变异 14 锚×2/两 plan 四行×2）；R1-F4/F5/F6/F9 注记卫生四小项（6-11 连字符/伪溯源编号去除/死产物行删除/六元组勘误）；留档 12 项注记（Defer 表）——运行面 D 视角全量复核属实（15280 passed/ruff+mypy 零错/覆盖 100%/纯三零）
- v1.4.0: dev-story 实施完成 in-progress→review（Task 0~7 全勾+DoD 全过）。交付面：五 VO+三常量+值域 frozenset+ConsultantViewPort 零参+三段编排服务（两趟稳定排序+latest 遮蔽+双段联动容错）+零参透传用例+CLI consultant-view（族首个零 add_argument）+组合根双注册；验收 12/12+集成 4/4+四目录全量 15280 passed+2 skipped 零失败；变异 14 锚全实证（VO 2+服务 5+CLI 4+集成 2+架构 1）；实施攻坚两项留痕（预置时间戳单基准锚——逐行取 now 微秒漂移真缺陷[A 面回查不可见→预置侧登记直推]）；新增三 src 文件覆盖率 100%+mypy 765 零错+ruff 全仓过+纯三零 diff 实证+deferred-work 14 锚位处置落档
- v1.3.2: 文档审查 Round 5 独立终审+收敛（不轻信自报六节取证——双向取证 12 项[11 过 1 证伪]+全文终扫+门禁/收敛判据；特权发现 2 项随收敛提交清偿）：**R5-F1**[P1] R3-F1「ArchiveRepositoryPort 无 save」伪实证勘误（六扩展方法枚举漏 L2RdbPort 基类四继承方法——save :36/:110-115/:191/服务三处消费四重证据；改钦 repo.save 对称通道五处联动+R3-F1 台账勘误内联——端口方法枚举须含基类继承面教训留档）；R5-F2[P2] OD-13 尾句 S6 复述双升格联动（membership 措辞+绊线语义）；收敛声明入档（五轮六提交 36 项处置=P0×3+P1×14+P2×8+P3×8+证伪×3；收敛判据五节全过；Next Steps 循环项勾选——**放行 dev-story**）
- v1.3.1: 文档审查 Round 4（纯验证+双 Agent 晚归发现清偿轮——R2-A 回归核查 6 项开放+R2-B 组合推演 5 项新发现[事实基座：全仓提交型写入方普查+xdist 拓扑+时间戳构造普查]）：**R4-F1**[P1] Task 4.3 消费方全景清偿+5 项 P3 欠账；**R4-F2**[P1] Task 0.5 漏列 pytestmark xdist_group 硬纪律（提交型写入方全组串行的窗口免疫结构前提+前向约束登记）；R4-F3[P2] S6 诚实重标「单源契约绊线」（ReportRepository 无 plan 枚举 API——变异无实现通道，判别力面向未来端口扩展）；R4-F4 S8 更名；R4-F5 占首三未登记假设补强；R4-F6 值域守卫 6-11 对称注记+raise 落位钦定；三轴验证全过（锚点 8/8+计数终扫+版本一致）
- v1.3.0: 文档审查 Round 3（单深度推演——主会话直执：12 场景最终态复推/预置通道深水区/可写性验证）——2 项处置：**R3-F1** 归档行预置通道钦定错误（6-7 `_archive_row` 编排通道 archived_at 不可编程+ArchiveRepositoryPort 无 save 方法——与 OD-13① 未来偏移结构性冲突；钦定 PG model 直写通道五处联动）；R3-F2 017 无 FK 证伪留痕（S6 任意 UUID 报告行可写）
- v1.2.0: 文档审查 Round 2（回归核查+组合交互——审查员①[一致性六轴，晚归全量并入]+主会话亲验[差值竞态定谳/未来偏移免疫假设核查/时间戳形态实证]+双 Agent 配额降级承接）——7 项处置（P1×3+P2×2+P3×1+证伪 1）：**R2-F1** R1 差值断言窗口竞态升格 membership 全含（十四处联动——外来 plan 免疫+判别更强+基线查询废止）；R2-F2 命令族分解算术勘误（6+7+2+1=16 加法闭合）；R2-F3 常量口径统一（品牌两常量+PANEL=三常量，7 处）；R2-F4 OD-5 消费方传播漏网；R2-F5 扇出欠账族 12 处（七连/L170/十三裁定/五先例族/乱码/五口径/锚统一）；R2-F6 P3 欠账 5 处；R2-F7 未来偏移免疫假设证伪留痕
- v1.1.0: 文档审查 Round 1（四调研 Agent+主会话亲验[测试库背景行实测/isolation-logs 参数面亲验/008 migration FK 亲验/排序先例亲验]+审查员②可满足性推演回归+审查员①配额降级主会话承接一致性六轴）——19 项修复登记（P0×3+P1×7+P2×4+P3×4+证伪留痕 1）：**R1-F1** 命令族全称断言失实（isolation-logs 可裸调——「首个零 add_argument」口径重述）；**R1-F2** 共享库全局查询断言体系不可满足（新增 **OD-13 四件套**：未来偏移/plan 集差值/CLI 包含格式/绝对空态归单测——8 场景断言口径全面改写+Task 0.5 基线查询步骤+「当前租户 schema」表述勘误）；**R1-F3** 并发对照与 6-8 R2-F2 冲突（membership 子集过滤对照五处联动）；R1-F4 排序伪码不可执行（两趟稳定排序钦定+None 排尾口径）；R1-F5 latest_pdf 选择口径冻结（口径三新增+双 plan pdf 判别格）；R1-F6 S6 重定义单源口径判别场景；R1-F7~F9/F14 锚点勘误族（14 键/:56/:69/:21-92/save 先例标签/三视图表真实锚位）；R1-F8 find 消费方全景改写+Task 4.3 回归面补全；R1-F10 性能背景量级 skip 门；R1-F11~F13 守卫增值域/第五变异锚/模块级零 import 硬纪律；R1-F15~F18 计数口径/行宽归因/注释纪律双注记/双装饰器先例锚
- v1.0.0: 创建故事文件（四 Agent 并行调研【报告白标数据面/多项目与快照清单面/CLI+组合根+R6 模板/治理面与范围边界】+主会话亲验 18 组关键锚点；OD-1~OD-12 十二裁定：范围收窄 CLI-only 第九连（零参数全局视图——CLI 族首个零参数查询命令；Web 归 Epic 21/22+顾问角色枚举缺口注记；品牌配置实现归 6-11——品牌段 V1 恒默认态对接锚；白标 REST 归 Epic 20 Story 20.4；批量导出显式不做——L129 第五轮维持）/零新增事件第九连（_FROZEN_EVENT_COUNT=56 零变化）/零新增异常+零 242 消费面（零输入语义自然缺席——report 段 494-499 预留不占）/五 VO 5-4-6-5-7 键契约（顶层无 plan_id 键+brand 零 IO 恒在段+latest 遮蔽计数口径）/多项目段 archives 反推数据源（ArchiveQuery(plan_id=None, limit=1000) find 现成跨 plan 查询首个应用层消费+None 行剔除+N+1 双风险注记立项锚 Epic 7/21+项目行不含进度列两视图正交）/品牌段三常量+禁 import infra（STSong-Light 字面量 :60 锚）/导出段纯投影派生（零新读单源纪律+与 6-8 ReportSection 语义正交）/性能三段口径（P95<800ms 服务面+并发 20 排除集单键第三连+导出<1min 归 6-5b 既有面+隔离 100% 继承口径——口径差声明六连）/锚定义务 11 条处置（L13/L17/L107/L117+L170/L127/L129 六 Epic6 锚+6.5a-DF1·DF2 顺延+6.7-DF1·DF2 维持+D6-8-R1·R2 第三连+D6-9-R1-1 不入命令族注记+品牌对接锚不登记裁定）/命名 consultant_view 词族（integration 前缀对 epics 钦定名显式偏离第三连）/组合根双注册+两 SCOPED 无混态（最简形态）+CLI 注释措辞纪律/纯三零 Story 第二连（零 domain+零 migration+零 infra——src 面 3 新建+2 扩展）/双段联动容错（find 级+循环级两捕获位+行级 None 同形段哨兵区分裁定）；12 验收场景钉死（S1~S12——epics 架构测试三项对账：多项目→S2/白标→S4+口径差声明/隔离→S11 继承口径））
