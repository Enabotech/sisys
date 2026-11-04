# Story 6-5b: PDF 报告生成 + 引文索引（同源双渲染 + L4 WORM 归档 + evidence_refs 首消费 + 引文溯源索引）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统按 plan_id 生成 PDF 格式战略规划报告（BLM 前两阶段），包含按步骤归档的引文索引（溯源三元组：文档名/页码/切片标识）与 PDF 内部可点击导航（目录/书签/引文锚点）,
**So that** 可以导出专业格式的规划结果交付高管与顾问（6-10 顾问视图的前置），引文索引支撑结论可信度验证与后续高保真溯源（6-7/6-8）。

### 业务价值

6-5a 已交付 Markdown 报告基座（聚合 VO + 渲染 + L0/L2 持久化 + ReportGenerated 事件）。本 Story 是 Epic 6「规划结果可交付」的第二跳：同一聚合产物（`MarkdownReportDocument` VO）以 PDF 形态渲染并归档 MinIO L4 WORM（6-5a OD-4 钦定「L4 证据包 defer 6-5b 引文证据同批」的承接点），同时**首消费** 6-4 归档的 `assumptions.evidence_refs`（chunk_id 清单——写侧在位读侧零消费），解析为「文档名 + 页码 + 切片标识」引文索引附录，兑现 FR-UI-11「可点击的引文索引」的 CLI 可达半边；为 6-10（顾问视图/白标 PDF）与 6-7/6-8（溯源树/Web 阅读器 PDF.js 高亮）提供 PDF 产物与引文数据基座。

### 与 6-5a/6-7/6-8/6-10/6-11 的范围边界（出处逐行声明）

| 面 | 本 Story（6-5b） | 归属（出处） |
|---|---|---|
| PDF 渲染（同源 VO → reportlab → bytes） | ✅ 本 Story 新建（infrastructure 渲染器） | epics L2276「将 Markdown 转换为 PDF 格式，保持格式一致」（L2274 是 Given「Markdown 报告已生成」行——OD-3 重读对象，双行号并列）；reportlab 4.5.1 已预留 pyproject:126（**当前在 test 依赖组——本 Story 移入主依赖组**） |
| 引文索引（evidence_refs 首消费 → 附录 C 引文表） | ✅ 本 Story 新建 | epics L2277「报告包含可点击的引文索引」；6-5a L842「evidence_refs 归 6-5b 引文」明文留位 |
| PDF 内部可点击（目录/书签/引文锚点 link 注释） | ✅ 本 Story 新建 | epics L2291「引文点击响应<300ms」CLI-only 口径重读（OD-8——阅读器本地跳转零网络延迟，断言面=链接注释结构正确） |
| PDF 二进制 L4 WORM 归档 | ✅ 本 Story 新建 | architecture.md 交互流程 38（L417「证据包保存→Object_Storage」）+ 代码单源桶名 `archive-evidence`（strategic_archive_service.py:40——与 6-3/6-4 证据归档同桶；蓝图名 `evidence-packages/`（architecture.md L2548）为逻辑分类未落地，实况注记 Task 7 回填，OD-4）+ 6-5a OD-4「L4 defer 6-5b（引文证据同批）」 |
| Markdown 报告链（聚合/渲染/L0/L2/事件） | ❌ 零改动纯复用（聚合函数公开化唯一例外——行为零变） | 6-5a done 面；本 Story AC-6 冻结清单 |
| Bounding Box 高亮跳转（点击→原始 PDF 坐标点） | ❌ | **数据缺口在 ingestion 侧非报告侧**：chunk_indexing_handler.py:156-168 Qdrant payload 仅 6 键无 bbox/page_start（3-8 遗留前置，story 3-8 L118 自注记未实现）；Web PDF.js 阅读器归 6-8（ux-design-specification L182/L206-210）。本 Story 交付引文**页码级溯源 + 溯源三元组完整携带**，bbox 高亮 defer 登记（OD-6） |
| 白标品牌（Logo/配色/字体/模板） | ❌ | Story 6-11（epics L2036「白标报告基础仅需 Markdown 基础」） |
| 高管简化视图 / REST 导出 `/plans/{id}/export` | ❌ REST 归后续 Story | 6-8 / Epic 7（6.5a-DF1 留项维持——本 Story CLI-only 延续，触发条件不变；「分享」承载 = PDF 文件本身分发【L4 对象 + CLI 打印键】，用户级分享通道归 6-8 REST/6-11 白标） |
| 图本体（位图/SVG）渲染 | ❌ 表格/列表承载延续 | 6-5a OD-9 冻结（「位图/SVG/mermaid defer 6-5b」的 6-5b 裁定 = **继续表格承载**——PDF 面零位图，「图像不失真」AC 口径=零位图前提下的文本/表格质量，OD-9） |
| 溯源树展示 / Traceability API 消费 | ❌ | 6-7（epics L2017）；3-8 交付的 TraceabilityPort 是检索断言面非 chunk_id 解析面（trace(claim) 按文本检索——本 Story 引文链直用 L3VectorPort.get_point，OD-3） |
| 思维链全文附录呈现 | ❌ 维持 YAGNI 归 6-7 | 6-5a 范围边界 L34 明文「附录呈现归 6-5b/6-7 立项定夺」——本 Story 立项裁定：引文索引（附录 C）已交付溯源消费面，思维链**全文**附录维持 YAGNI（`chain.to_display()` 资产在位可消费），随 6-7 溯源树立项定夺（Task 0.7 台账注记——R4N-1） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: PDF 生成主链（聚合复用 → 快照辅源 → 引文聚合 → PDF 渲染 → L4 WORM 归档 + L2 元数据 → 事件）

**Given** BLM 前两阶段已完成（八步 chain 归档行在位，plan_id 已知；与 6-5a 同数据源——**不要求 Markdown 报告行已存在**，「Markdown 报告已生成」Given 的口径重读 = 归档数据面就绪即 PDF 可生成，OD-3）
**When** 调用 PDF 报告生成（CLI `report-generate --plan-id <id> --format pdf` 或用例 `GeneratePdfReportUseCase.execute(plan_id)`）
**Then** 执行六段编排：①chain 归档主源聚合（`aggregate_report_document`——6-5a `_aggregate_document` 公开化，行为零变）→ ②latest 快照辅源（容错）→ ③引文聚合（`query_archive(ArchiveQuery(plan_id, archive_type=EVIDENCE_PACKAGE))` 每行 `assumptions["evidence_refs"]` → 去重 → 逐条解析为 `CitationEntry` → 组装附录 C section 追加进文档 VO）→ ④PDF 渲染（`PdfRendererPort.render(document) -> bytes`）→ ⑤L4 WORM 归档（`archive(bucket_type=EVIDENCE_BUCKET_TYPE（="archive-evidence"）, object_key=PDF_OBJECT_KEY_TEMPLATE 派生, content=bytes, retention_days=2555)`——archive 签名无 content_type 参数（store 才有），勿传；与 6-3/6-4 证据归档同桶，OD-4）+ L2 `strategic_reports` 元数据行（report_type="pdf"）→ ⑥发布 `ReportGenerated` 事件（report_type="pdf"）
**And** 返回 `StrategicReport` 实体（report_id/plan_id/report_type=PDF/file_path=**L4 对象键逻辑路径** `reports/{plan_id}/{report_id}.pdf`/section_count==11（H3 小节口径与 6-5a 恒同——附录 C 是 H2 附录不计入，见增量冻结表）/degraded_section_count/generation_ms——6-5a 八字段实体（含 created_at）零改动全兼容）
**And** 同 plan_id 重复生成产生新报告（幂等锚 = report_id——OD-10 延续；**L4 对象键锚 report_id 天然唯一**：每 report 恰一对象、无同秒覆写/WORM 冲突形态，6.5a-DF2 的 L0 撕裂风险面在 PDF 链路不存在——L4 put_object 服务端原子）

**验证标准/Validation Criteria:**
- [ ] 全链真实服务验收：归档八步（可复用 6-5a 归档轻装配）→ report-generate --format pdf → 断言六段全部落位
- [ ] L4 对象可读回：`retrieve(EVIDENCE_BUCKET_TYPE, object_key)` 流式收 bytes 首块非空 + pypdf 解析 `len(reader.pages) >= 1`（读回口径——OD-8）
- [ ] L2 元数据行可读回（`get_latest_by_plan` 返回最新行，report_type=="pdf" 与实体一致；metadata JSONB 含 citation_count/unresolvable_citation_count 等扩展键）
- [ ] ReportGenerated 事件经 outbox 真实落行（两级 JSONB 路径 `payload->'payload'->>'report_id'`；report_type 值级断言 =="pdf"）

### AC-2: 格式一致性（同源文档模型——与 Markdown 报告结构同源）

**Given** 八步归档行齐备
**When** 分别生成 Markdown 报告（6-5a 链）与 PDF 报告
**Then** 两者消费**同一聚合产物**（`aggregate_report_document` 同函数同入参——「保持格式一致」的承载形态 = 结构同源而非 Markdown 文本再解析，OD-3）：H1 封面 + 元信息表 + 目录 + `## 1 业绩差距分析` 四小节 + `## 2 市场洞察` 六小节 + `### 2.7 市场洞察综合` + 附录 A 执行时间线（快照在位时）+ 附录 B 降级与数据缺失记录 + **附录 C 引文索引（PDF 特有）**
**And** 三态降级判定/缺行 H3 骨架渲染/原因解析次序/计数口径与 6-5a 冻结版逐字一致（聚合复用的自然结果——**禁止在 PDF 侧重写任何降级逻辑**）
**And** 表格完整渲染（元信息表/PESTEL 六维表/五力五维表/时间线表/附录 B 表/附录 C 引文表——列数与源数据一致，reportlab Table 形态）；中文文本原样呈现（CJK 字体注册——见 AC-8）

**验证标准/Validation Criteria:**
- [ ] 同一 plan_id 双格式生成断言：两份实体 section_count 恒等（`pdf.section_count == markdown.section_count`——同聚合同 H3 小节计数单位，附录 C 是 H2 附录两侧均不计入；增量冻结表口径）
- [ ] Markdown 报告文本（经 6-5a 链生成读回）的全部章节标题族在 PDF 文本层可寻（display_name 源独立构造期望——非报告自证；中文断言口径见 AC-8 注记）
- [ ] 附录 B 降级行数与实体 degraded_section_count 口径联动断言（6-5a R2 口径零变化）

### AC-3: 引文索引（evidence_refs 首消费 → 附录 C）

**Given** 八步归档行的 `assumptions.evidence_refs` 含 chunk_id 清单（6-4 写侧在位：`chain_of_thought_archive_service.py:200-203`）
**When** PDF 报告生成
**Then** 引文聚合三段：①**收集**——`query_archive(ArchiveQuery(plan_id=plan_id, archive_type=ArchiveType.EVIDENCE_PACKAGE, limit=64))` 逐行取 `assumptions.get("evidence_refs", [])`（list[str] chunk_id），跨步骤**去重保序**（首现次序即索引号）；②**解析**——每 chunk_id 经 `L3VectorPort.get_point(collection, chunk_id)` 取 payload（document_id/chunk_header/content）→ `DocumentRepositoryPort.find(DocumentQuery(tenant_id=服务注入租户, document_id=uuid.UUID(payload["document_id"])))` 取 `filename` + `metadata["chunks"]` 按 chunk_id 匹配取 `page_start`（tenant_id 经服务构造参数注入、默认 `str(MVP_TENANT_ID)`——agent_workflow_context.py:39，5-3 单租户先例，多租户归后续 Story；DocumentQuery.tenant_id 必填且 PG find 硬过滤——document_repository.py:99-103；payload 的 document_id 是 str 而 DocumentQuery.document_id 是 UUID，必须显式转换）；③**组装**——附录 C section（H2 `附录 C 引文索引`）以 table 块型渲染（`| # | 文档名 | 页码 | 切片标识 |` 四列——切片标识列 = chunk_id 前 8 位截断显示，完整值入 L2 metadata）
**And** 引文条目形态冻结：正常条目 `[n] {filename} p.{page_start} {chunk_id_8}`；**解析降级三态**——`get_point` 无点（chunk 已删/collection 不含）→ 条目 `[n] [溯源不可用：检索点缺失]`；document 行缺失 → `[n] [溯源不可用：文档记录缺失]`；chunks 元数据无该 chunk_id → 页码列显示 `-`（文档名仍可得）。**降级不阻断报告生成**（引文是增强面非阻断面——计数入 L2 metadata `unresolvable_citation_count`，与 6-5a「部分数据报告 + 显式标注 > 全或无」哲学一致；**整体容错边界**：引文聚合整体 try 容错——解析链任一依赖异常（`query_archive`/`get_point`/`find` 抛异常——非 None 返回）时降级为空附录 C 单行说明 + log warning、报告照常生成【增强面故障不炸主链——与事件发布宽容哲学同构，citation_count==0；CR1-F2 扩 find——代码审查裁定三入口同容错】）
**And** evidence_refs 全空（八步零引用）→ 附录 C 渲染「本报告无检索证据引用」单行说明（**附录 C 恒存在**与 6-5a「缺行骨架渲染」同哲学——但 section_count 仍恒 11 不受附录 C 内容形态影响：附录 C 是 H2 附录本就不计 H3 小节口径）
**And** 每条引文在 L2 metadata 留完整溯源三元组（`citations: [{index, document_id, chunk_id, filename, page, status, stage}]` 七键——stage=首现步骤名【去重后一个 chunk_id 锚首现步骤，步骤归属信息经 metadata 保留——OD-6】；6-8 Web 阅读器/6-7 溯源树的查询面）

**验证标准/Validation Criteria:**
- [ ] 真实链引文场景：预置 Qdrant 点（payload 含 document_id/chunk_header）+ PG documents 行（tenant_id=服务实例注入的测试租户值【预置与查询同租户闭环——find 硬过滤下租户不匹配必现 document_missing 假降级】+ filename + metadata.chunks 含 chunk_id/page_start）→ 归档行 evidence_refs 喂该 chunk_id → 附录 C 值级断言（`[1] {filename} p.{page}` 逐字段）
- [ ] 去重保序断言（两步骤共享同一 chunk_id → 索引唯一 + 首现次序）
- [ ] 解析降级三态各钉一用例（单测层 AsyncMock 注入三失败形态——no-mock 红线互斥裁定：引文解析失败注入归单测层，验收/集成不含；验收层构造真实缺失：evidence_refs 喂不存在的 chunk_id → [溯源不可用] 条目）
- [ ] 全空引文场景 → 单行说明 + section_count 恒 11（附录 C 空态不漂移计数口径）
- [ ] L2 metadata citations 七键值级断言（index/document_id/chunk_id/filename/page/status/stage——stage=首现步骤名必断言【R2-3 新增键防漏实现】）

### AC-4: PDF 内部可点击导航（目录/书签/引文锚点）

**Given** PDF 报告生成
**When** 以 pypdf 读回 PDF 结构
**Then** 三层导航结构在位：①**书签 outline**（H1 文档题 + H2 章级含附录 A/B/C——附录 A 可选【快照在位时收录，与目录收录面同口径】；outline 含 H1 文档题而目录自 H2 章级起收录——两结构收录面差异注记；reportlab `bookmarkPage` + `addOutlineEntry`，层级与冻结章节结构一致）；②**目录内链**（目录条目为 link 注释指向对应章起始页锚点——reportlab `linkRect` + `linkDest`）；③**引文锚点**（附录 C 每条目注册命名锚点——为 6-8 Web 阅读器「正文引用点→引文详情」交互预留结构位；正文不插句级引用标记——evidence_refs 是**步骤级**粒度非句级，数据粒度不支持句级标记，OD-6）
**And** 全部 link 注释目标锚点存在（无悬空链接——pypdf 遍历 page `/Annots` 断言每 link 的 `/Dest` 数组首元素可解析为有效页对象；**断言形态实证注记**：reportlab save 期已将命名目标解析为 `/Dest=[IndirectObject(页), '/Fit']` 直接数组、pypdf `named_destinations` 为空——「命名目标可解析」断言形态不可实现，锚定 /Dest 数组即锚定目标页；悬空链接由 save 期抛错天然拦截（`ValueError: format not resolved … undefined destination`→492 包装路径）——R3 技术实证钉死）
**And** 「引文点击响应<300ms」的 CLI-only 口径落地 = **结构化断言非计时断言**：链接注释正确生成 + 目标锚点存在（阅读器本地跳转零网络延迟——OD-8 口径重读，epics L2291 字面指标的本 Story 承载面）

**验证标准/Validation Criteria:**
- [ ] outline 断言（pypdf `reader.outline` 层级标题族——display_name 源独立构造期望）
- [ ] 目录 link 注释断言（`/Annots` 中 Subtype==/Link 且 `/Dest` 数组首元素为有效页对象【R3 实证：命名目标已解析为 /Dest 直接数组】；条目数 == 目录收录面——H2 章级+附录 A 可选【快照在位时收录】，6-5a 目录收录冻结口径延续）
- [ ] 引文锚点存在性断言（附录 C 条目锚点可解析；负向断言 = `citation-{index}` 命名锚点仅注册于附录 C 页——正文页零命中，AC-3 步骤级粒度裁定的守护）

### AC-5: ReportGenerated 事件零新增复用（report_type="pdf"）

**Given** PDF 报告生成成功
**When** 事件发布
**Then** 发布 `ReportGenerated`（report_id=实体 report_id / **report_type="pdf"**（`report.report_type.value`）/ file_path=实体 file_path / aggregate_id=report_id / aggregate_type="Report"——**事件类字段面冻结零改动零新增**；构造点显式传三键——6-5a AC-5 钦定延续）
**And** 事件通道零新增零 diff（event_channels.yaml L273-276 + `src/infrastructure/messaging/channel_router.py` DEFAULT_MAPPINGS :346 既有登记直接复用）
**And** 发布失败 → 宽容语义原样（`is_success` 先判 + except 兜底双防线 → warning 不上抛——6-5a OD-6 冻结形态逐字复用；L4/L2 是真相源、事件是通知面）

**验证标准/Validation Criteria:**
- [ ] outbox 落行断言（event_type/report_id/file_path/report_type 四键值级断言——非仅存在性）
- [ ] `configs/event_channels.yaml` 与 `channel_router.py` 零 diff（契约测试守护——键集合冻结快照全等断言沿用 6-5a 形态，键数 56 基线不变）

### AC-6: 契约零破坏（6-5a/6-x 冻结面零触碰）

**Given** 本 Story 实施
**When** 回归验证
**Then** 以下冻结面零改动：①6-5a 聚合行为面（`_aggregate_document` → `aggregate_report_document` **公开化更名**是唯一允许改动——签名/行为/返回结构零变，测试零直接引用实证 grep tests/ 零命中）②`ReportGenerated` 事件类与双登记 ③`StrategicReport` 实体与 491 值域（`_VALID_LAYERS=("l0","l2")` **不扩**——L4 失败走新码 493，OD-10）④6-2 六 Schema/6-3 快照契约/6-4 归档配方（blm_planning_prompts.py/blm_planning.py 契约区/workflow_events.py 零 diff）⑤既有 6-x/5-3 验收/集成/契约测试零修改通过（6-5a 聚合公开化的波及面 = 仅 report_generation_service.py 内部一行改名——6-5a 单测走公共行为面零破坏）
**And** Markdown 报告链（report-generate 默认 format=markdown）行为零变化（CLI 向后兼容）

**验证标准/Validation Criteria:**
- [ ] 四目录全量回归两轮稳定（`pytest tests/unit tests/integration tests/contracts tests/acceptance`——裸 tests/ 会挂起，四目录命令纪律）
- [ ] 读侧消费面契约断言（对齐 6-5a S10 形态）：chain 读侧 records 五键结构全等 + ReportGenerated outbox 行 payload 键族全等（含 report_type=="pdf"）
- [ ] `poetry run ruff check` + `poetry run mypy src/` 零错误（当前基线 746 零错误不回退）

### AC-7: 性能与持久化成功率

**Given** 数据源在位
**When** 生成 PDF 报告
**Then** 生成窗口 P95<60s（epics L2289 钦定上限；口径 = 聚合起点→事件发布返回，**不含 BLM 流程本身**——OD-8 口径延续；PDF 链较 Markdown 链新增引文解析 N×2 次查询 + L4 上传 + reportlab 渲染，实测预期同量级（6-5a 实测亚秒级）；NFR-PERF-03「标准报告<30s」（prd）与 epics 60s 上限的双口径关系 = 30s 是 prd 更严口径、60s 是 epics 断言上限——本 Story 断言沿用 epics 60s 口径（6-5a 同判），实测预期亚秒级远优于双口径；「完整 SP/BP 报告<2 分钟」半边归 Epic 10 完整六阶段立项——BLM 前两阶段=标准报告口径，本 Story 不承载）
**And** 生成成功率 100%（口径：正常路径 N 次生成 N 次 L4 对象可 retrieve + L2 行在位 + 事件落行——N 与采样轮数同源=20；「L4 可读回」= 每轮生成后即时 retrieve 首块 + pypdf 页数>0；数据源全缺 490 是业务异常非失败）
**And** 并发生成 3 个 PDF 报告（asyncio.gather 独立 plan_id，互不干扰；服务无状态约束——SINGLETON 实例并发共享，实现禁持每次调用的可变实例态；引文解析局部累积清单与 6-5a 附录 B 登记清单同纪律）
**And** 「导出时间<1 分钟」（epics L2279）与 P95<60s 同口径覆盖（60s<1min 钦定关系成立，单指标双表述不另测）

**验证标准/Validation Criteria:**
- [ ] 性能采样 ≥20 轮（单一数据源 plan_id × 20 次生成——OD-8 采样形态延续；断言锚 = 每轮新 report_id + L2 行数累计 20 + **L4 对象数 20**（键锚 report_id 天然互异——无同秒覆写豁免问题）+ report_id 集合无重复；P95 `sorted(durations)[ceil(0.95*n)-1]`<60s——n=20 次大值口径如实承受）
- [ ] 并发 3 场景（三 plan_id 全部成功且 L4 对象/L2 行/事件三元互不串扰）
- [ ] 引文解析批量性能注记：引文数去重后 M 条 × 2 次查询（get_point+find）在 P95 窗口内（真实链实测落档 docstring——若 M 过大（>50）超窗口，瓶颈登记 deferred-work 非本 Story 扩面）

### AC-8: 渲染质量（中文清晰/表格完整/页面可渲染）

**Given** PDF 报告生成
**When** 读回验证
**Then** 中文文本以 CJK 字体渲染（reportlab `UnicodeCIDFont("STSong-Light")` 注册——**内置 CID 字体零字体文件依赖**；禁系统字体路径依赖——可移植性）；
**And** 表格完整（列数一致/表头样式/单元格文本不溢出截断——reportlab Table + 列宽策略：首列窄（序号）+ 文档名列自适应 + 页码/标识列定宽）；
**And** 页面可渲染（pypdfium2 光栅化冒烟——每页渲染非空白：`page.render().to_pil()` 后非纯白像素断言；**「图像不失真」epics 口径重读** = 本 Story PDF 面零位图（OD-9 表格承载延续），断言面 = 光栅化渲染不炸 + 非空白）；
**And** PDF 元数据（Title = REPORT_TITLE_TEMPLATE、Producer 非空——pypdf `reader.metadata` 断言）
- **中文文本断言口径注记（load-bearing，R3 实证升级）**：STSong-Light（UnicodeCIDFont + Adobe-GB1 预定义 CMap）的 `extract_text()` 对正文与表格中文**完美工作**（R3 最小实证：章节标题/表格单元格/长文件名全部正确提取）——**中文值级断言可直接用 extract_text 全文比对**（含附录 C 引文表逐字段）。分层冗余保留：①ASCII 面（页码/序号/chunk_id 前缀）与②outline 标题族作为互补断言面；③pypdfium2 渲染非空白作为视觉面兜底。**先例适用范围辨析**：test_pdf_parser.py:267 注释的 CID 限制是**其他生成器场景**（非 Adobe-GB1 预定义 CMap），不适用于本 Story 的 STSong-Light 形态——Task 0.2 复验后钉死

**验证标准/Validation Criteria:**
- [ ] 字体注册断言（渲染器单测：中文段落渲染不抛 Helvetica 缺字异常——未注册字体渲染中文抛 reportlab 异常是天然红）
- [ ] 表格结构断言（pypdf 页数 ≥ 章节数下界；表格文本断言直接经 extract_text 全文比对【R3 实证表格中文完整可提取——含长文件名/`-`/chunk_id 列】，ASCII 抽样保留为冗余面）
- [ ] pypdfium2 渲染冒烟（每页非空白像素；渲染异常即红）
- [ ] metadata 断言（Title 中文值——metadata 域 CID 无关可断言）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **零新增事件**——`ReportGenerated` 复用（6-5a 首激活后第二次生产；report_type="pdf" 经自由 str 字段流经零类改动）；双登记既有零 diff
- [ ] 发布点唯一落位 = `PdfReportGenerationService` 编排尾部（L2 落库之后；宽容语义双防线**同款代码复制**为 6-5b 服务私有方法——6-5a 文件冻结不可提取共享，重复是冻结面的代价；docstring 注明形态溯源 report_generation_service.py:243-276）

#### 数据模型 (Data Models)

**domain VO——引文条目**（`src/domain/value_objects/citation_entry.py` ★ 新建，frozen dataclass 零依赖——报告域文档模型扩展；**不复用 3-8 的 `Citation` VO**（citation.py:24-51——它是检索溯源域产物：含 text/start_offset/end_offset/page_number/bbox/confidence 检索语义字段，无 filename；报告引文条目需要 filename/解析状态——语义不同面【OD-6】）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `index` | `int` | ≥1（去重保序首现次序） |
| `document_id` | `str` | 解析成功时非空 UUID 字符串；解析失败允许空串（status 承载降级语义） |
| `chunk_id` | `str` | 非空（引文锚定标识——全量值，显示截断归渲染层） |
| `filename` | `str` | 解析成功时文档名；失败态空串 |
| `page` | `int` | ≥1；页码不可得时 0（渲染层 0→`-`） |
| `status` | `str` | 值域三元组冻结 `("resolved", "point_missing", "document_missing")`（page 缺失是 resolved 的子形态非独立态——文档在页码元数据缺，status 仍 resolved + page=0） |

- [ ] `__post_init__` 校验：index ≥1 / chunk_id 非空 / status 值域 / page ≥0（与字段表「≥1；不可得时 0」边界一致）/ document_id 非空时校验 UUID 格式（uuid.UUID 试解析兜底），违例抛 `EntityValidationError`（242 复用）

**StrategicReport 实体**：零改动（6-5a 八字段全兼容 PDF 形态——report_type=PDF 预留值/file_path 存 L4 对象键逻辑路径非空合法/计数不变量【degraded_section_count ≤ section_count 恒 11 口径】自然成立）

**L2 `strategic_reports` 表**：零 migration（report_type 列 String(20) 自由值 "pdf"；metadata JSONB 自由扩展 citation_count/unresolvable_citation_count/citations 三键——**无表结构变更**，alembic 018 无需新增）

#### 报告章节结构增量冻结（6-5a 两张冻结表零变化 + 本 Story 增量一张）

**6-5a「章节结构冻结表」与「六子步骤要素渲染映射冻结表」逐字沿用零变化**（聚合复用的自然保证——本 Story 禁止重写）。增量冻结：

| 位置 | 标题（level） | 素材源 | 块型序列 |
|---|---|---|---|
| 附录 C | `附录 C 引文索引`（H2） | 引文聚合产物 CitationEntry 列表 | table（`\| # \| 文档名 \| 页码 \| 切片标识 \|` 四列；序号列 `1..M`、页码列 resolved+page>0→`p.{page}` / resolved+page==0→`-` / 降级态→`-`、切片标识列 chunk_id 前 8 位；evidence_refs 全空 → 单行说明 callout「本报告无检索证据引用」）；每条目锚点 ID `citation-{index}`（渲染层注册） |

- 附录 C 进目录（H2 章级收录——目录收录面 = 2 章恒收录 + 附录 B/C 恒在 + 附录 A 可选（快照在位则收录），**条目数非恒定**与 6-5a「条目数随附录 A 有无非恒定」注记同口径；断言面 = 目录条目集合与实际渲染章节一致（AC-4 验证标准「条目数 == 目录收录面」按此口径断言，聚合复用的自然结果））
- section_count 口径增量：**恒 11 与 6-5a 同口径**（附录 C 是 H2 章级附录不计 H3 小节——与附录 A/B 同不计入；双格式断言式 `pdf.section_count == markdown.section_count` 恒等，两者同聚合同计数单位）
- degraded_section_count 口径：**引文降级不计入**（三态①②是数据缺失类但那是引文条目级非 H3 小节级——计数单位冻结 H3 小节，引文降级归 L2 metadata `unresolvable_citation_count` 可观测——与 6-5a「锚叠加不计」同款「可观测面归 metadata」哲学）

#### 统一端口定义注册与管理 (Port Contract)

**新建端口 1：应用层 `PdfRendererPort`**（`src/application/ports/pdf_report.py` ★——R2 具体应用端口；**落位裁定 OD-5：application 而非 domain**——domain 禁 reportlab（importlinter forbidden 面），Protocol 本身零依赖可放 domain，但渲染器仅被报告应用编排消费无领域消费者，且 application/ports 已有 ReportGenerationServicePort 先例；`pdf_page_renderer.py` 在 domain 是因为它服务文档解析域的版面检测概念——两可中取语义更贴的 application）：

```python
@runtime_checkable
class PdfRendererPort(Protocol):
    def render(self, document: MarkdownReportDocument) -> bytes: ...
```

（同步方法——reportlab 纯 CPU 渲染无 I/O；bytes 返回端口先例 PdfPageRendererPort.render_page → bytes；引文附录已在编排层组装进 document VO——渲染器单参纯渲染，与 render_markdown_report 同入参对称）

- 模块常量：`EVIDENCE_BUCKET_TYPE = "archive-evidence"`（L4 bucket_type——**与 6-3/6-4 证据归档同桶单源对齐**：strategic_archive_service.py:40 `L4_BUCKET_TYPE` / chain_of_thought_archive_service.py:63 同值——evidence_refs 上游 EVIDENCE_PACKAGE 归档即在此桶，证据流一桶贯通；对象键 `reports/` 前缀与归档键 `{archive_id}/` 前缀天然隔离零互撞；architecture.md L2548 蓝图名 `evidence-packages` 是逻辑分类未落地（src/configs 零命中、归档链路不自动建桶），实况注记 Task 7 回填——OD-4）、`PDF_OBJECT_KEY_TEMPLATE = "reports/{plan_id}/{report_id}.pdf"`（对象键逻辑路径单源——file_path 存此值）

**新建端口 2：应用层 `PdfReportGenerationServicePort`**（同文件或独立——与 ReportGenerationServicePort 并列）：

```python
@runtime_checkable
class PdfReportGenerationServicePort(Protocol):
    async def generate_pdf_report(self, plan_id: uuid.UUID) -> StrategicReport: ...
```

**复用注入端口（零改动）**：`ChainOfThoughtArchiveServicePort`（聚合主源）/ `SnapshotRepositoryProtocol`（辅源）/ `ReportRepositoryProtocol`（L2）/ `EventPublisher`（事件）/ `L4ObjectPort`（L4 归档——`archive()` bytes 直传）/ `L3VectorPort`（get_point——引文解析①）/ `DocumentRepositoryPort`（find——引文解析②）/ `StrategicArchiveService`（query_archive——assumptions 读径；**注入具体类**：application 同层引用合法，组合根 `strategic_archive_service` :2216 注册在位，blm_planning_service :2300 注入先例）——九依赖注入
- **检索 collection 注入**：引文解析 `get_point(collection, chunk_id)` 的 collection 名经服务**构造参数**注入（默认值 `"documents"` 与 chunk 索引写侧 collection 字面量对齐——`chunk_indexing_handler.py` upsert 同值；非 `BLM_SEARCH_COLLECTION` env 传导（env 覆写只影响检索服务侧——CR1-F19 实况校准）；测试经构造参数注入临时 collection——与 6-5a L0 tmp_path 服务实例层注入同款可测试性形态，不走注册表覆写【ConflictError 先例】）
- **租户注入**：引文解析 `find` 的 tenant_id 经服务**构造参数**注入（默认 `str(MVP_TENANT_ID)`——`src/application/services/agent_workflow_context.py:39`，blm_planning_service.py:733-737 5-3 MVP 单租户先例同款；DocumentQuery.tenant_id 必填 + PG find 硬过滤 document_repository.py:99-103——数据链无租户可用【StrategicArchive/ArchiveQuery/Qdrant payload 均无 tenant_id】，注入是唯一来源；测试注入测试租户 str、引文预置 PG 行用同值闭环——与 collection 注入同款可测试性形态；多租户扩展归后续 Story）

- [ ] 端口契约定义位于 `src/application/ports/pdf_report.py`；registry 登记 PortSpec ×3（pdf_renderer/pdf_report_generation_service/pdf_report_generation_use_case 三注册块——双端口定义 + use_case 亦登记 PortSpec）
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册（`=== Story 6-5b ===` 包裹式分节——6-5a/6-3 先例；**增量注册零既有 lambda 改动**）
- [ ] resolver resolve() 可达；contract_gate 通过
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_pdf_report.py` ★——五断言族：注册存在/spec 元数据/v 前缀/getsource 注入面【九依赖包含性】/resolve isinstance）
- [ ] 禁止服务文件本地定义 Protocol；跨模块调用仅依赖抽象接口

#### 端口契约清单执行约束（强制）

- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> 完整检查清单详见 [`sisys-uni-exception-design.md §3.12`](../../docs/architecture/sisys-uni-exception-design.md#312-异常注册检查清单)。

**段位**：report 段 (490,499)——490/491 已占（6-5a），**492-499 预留可用**（sisys-uni-exception-design.md L760/L843 成文）。Task 0.1 运行 `grep -r "EXCEPTION_49[2-9]" src/domain/exceptions/` 验证零碰撞。

| 异常类 | code | 基类 | 触发场景 | HTTP |
|---|---|---|---|---|
| `PdfRenderingError` | EXCEPTION_492 | `BusinessException` | PDF 渲染失败（reportlab 渲染异常/中文字体注册失败/文档模型渲染期非法/未注册锚点引用（save 期 `ValueError: format not resolved`——R3 实证样例）——reportlab 原生异常的领域包装；context 携带 plan_id） | 500 |
| `ReportEvidenceStorageError` | EXCEPTION_493 | `BusinessException` | L4 证据对象归档失败（`L4ObjectPort.archive` 抛异常/返回异常态——**新码不复用 491**：491 `_VALID_LAYERS=("l0","l2")` 二元值域是 6-5a 冻结面，扩值域破坏其负向测试（"l4" 原为非法值抛 242 的用例）；最小契约变更原则取新码——OD-10） | 500 |

- [ ] 归属模块：`src/domain/exceptions/report_exceptions.py` ▲ 扩展（report 子域同文件——492/493 两类追加）
- [ ] 唯一编码分配：492/493（grep 零碰撞实证）；`_code_ranges.py` `_CLASS_TO_SUBDOMAIN` 注册两类（段位已有零 CODE_RANGES 变更）
- [ ] 构造器参数（家族形态）：`PdfRenderingError(plan_id, message=None, cause=None, context_extra=None)` / `ReportEvidenceStorageError(plan_id, message=None, cause=None)`——领域参在前 + 覆写缺省在后（**同构 490 形态**：490 是 `(plan_id, message, cause, context_extra)`；491 是 `(layer, ...)` 形态不同构）
- [ ] 消息安全性：面向调用方可理解，不泄露内部细节
- [ ] 导出完整性：`__all__` + `__init__.py` 导入 + `EXCEPTION_HTTP_MAP`（492→500 / 493→500）+ design.md §3.3.2 两张表回填（492~499 预留行改 492/493 实占 + 494-499 预留）
- [ ] 测试覆盖：构造/`to_dict()`/HTTP 映射 + 编码唯一性 + 子域范围全绿（自动发现零改动）+ `test_exception_handlers.py` 键集合快照同步登记
- [ ] BDD 验收场景：490 异常路径复用 6-5a 场景面（PDF 链同判）；492/493 归单测层（no-mock 红线互斥裁定——渲染/存储失败注入归单测 AsyncMock，验收/集成不含，6-5a 三连先例）

#### API 契约 (API Contract)

- [ ] **本 Story 零 REST 面豁免声明**：CLI-only 入口（6-5a/6-3/6-4 同族）；`/plans/{id}/export`（interface-design.md L1466 P0——format 参数含 pdf）维持 6.5a-DF1 留项（触发条件不变：6-8 立项或 Epic 7 API 入口立项）
- [ ] `docs/api/openapi.yaml` 零 diff（契约测试守护）

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
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2, **reportlab**（本 Story 新增面——.importlinter forbidden 清单 L8-39 含 numpy/pandas 等但**未列 reportlab**：架构测试 A 验证器白名单机制（非 stdlib 非 src.domain 即红）天然拦截，无需改 importlinter）

**本 Story 层间落位**（R1~R4 设计规则映射）：
- R1：零新建 domain 基础端口（L3VectorPort/L4ObjectPort/DocumentRepositoryPort 全既有复用）
- R2：`PdfRendererPort` + `PdfReportGenerationServicePort`（application/ports——具体应用端口，组合注入 R1 基础端口 L3/L4/DocumentRepository + 既有应用端口 ChainArchive/Snapshot/EventPublisher/StrategicArchiveService + R2 同层 ReportRepository）
- R3：`ReportLabPdfRenderer`（infrastructure——reportlab 技术实现，**唯一 reportlab 宿主**）；L4 归档复用 MinIOAdapter 零新实现
- R4：CLI `report-generate --format pdf`（entrypoints/agent_cli.py——组装层经组合根 resolve；6-5a 子命令加参数扩展）

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止（importlinter application-no-infrastructure 强制） |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_pdf_report.feature` ★ 新建（13 场景——AC-1×2/AC-2×1/AC-3×3/AC-4×2/AC-5×1/AC-6×1/AC-7×2/收尾×1，Task 0 钉死无范围值；AC-8 渲染质量归单测 Task 2 + 集成场景⑤ Task 6 承载、验收层不单列场景——断言分层注记见 AC-8 load-bearing 口径）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_pdf_report.py` ★ 新建（BDD 步骤实现）
- [ ] R6 风格基准：`test_acceptance_postgresql_relational_layer.feature/.py` 的 Gherkin 组织 + 6-5a 演进三件套（全场景 `@scenario` 绑定 + pytestmark 显式 + 模块级 `event_loop` + `context` dict + `_run_async` + teardown 精确清理链 + 逐服务探测 `pytest.skip()` 动态跳过 + 新模块延迟 import + docstring 分档表与 Run with）——**6-5a 验收文件是最近演进形态，装配链整体移植**（Fake LLM 八键族/_clear_resolver_caches/teardown 七步链/L0 tmp_path 注入）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases——含 490 异常路径复用面；492/493 归单测层）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 数据源全缺（490——PDF 链同判复用）；引文解析降级（真实缺失构造：evidence_refs 喂不存在 chunk_id）；492/493 单测层承载（no-mock 红线互斥——6-5a 三连先例）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（增量冻结表/引文三段链/锚点结构落 Dev Agent Record——实现 Task 的权威输入）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——**运行期 ImportError 形态**【延迟 import 纪律】，非收集期 collection error）
- [ ] 规范文档通过人工评审或自动化校验（承载 = `validate-create-story` 质量检查——checklist.md 灾难预防清单）
- [ ] **链路接线断言清单**已定义：①组合根三注册块 resolve 可达（pdf_renderer/pdf_report_generation_service/pdf_report_generation_use_case）②ReportGenerated 事件真实发布验证（outbox 落行 + report_type=="pdf"）③**L4 WORM 归档真实落位验证**（archive 后 get_metadata 可查 + teardown bypass 清理实证——测试 bucket WORM 面先探）④pyproject reportlab 依赖组迁移实证（test 组 → 主依赖组；`poetry install` 后 `poetry run python -c "import reportlab"` 在 src 环境可用——**src 面 import 前置门**）；「已实现未接线」组件在 deferred-work.md 登记

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
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言；6-5a 变异实证×6 先例）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | `CitationEntry` VO | 不变量校验（index/chunk_id/status 值域） | `tests/unit/domain/test_citation_entry.py` ★ | Task 1 |
| **TDD 领域异常测试** | report_exceptions 扩展 | 492/493 构造/to_dict/HTTP 映射 | `tests/unit/domain/exceptions/test_report_exceptions.py` ▲ 扩展 | Task 1 |
| **TDD 单元测试** | ReportLabPdfRenderer | 字体注册/块型渲染/表格列数/中文不炸/锚点生成 | `tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py` ★ | Task 2 |
| **TDD 单元测试** | PdfReportGenerationService | 引文三段链/降级三态/六段编排/事件/L4 调用 | `tests/unit/application/test_pdf_report_generation_service.py` ★ | Task 3 |
| **TDD 单元测试** | GeneratePdfReportUseCase | plan_id 守卫/透传/返回实体 | `tests/unit/application/use_cases/test_generate_pdf_report_use_case.py` ★ | Task 4 |
| **TDD 单元测试** | CLI --format pdf | 参数解析/分发/成功打印/异常定式 | `tests/unit/interfaces/cli/test_agent_cli.py` ▲ 扩展 | Task 4 |
| **TDD 契约测试** | 端口契约 | 注册/元数据/九依赖注入面/resolve 五断言族 | `tests/contracts/test_port_contract_pdf_report.py` ★ | Task 3/5 |
| **TDD 契约测试** | 事件零新增守护 | yaml+router 零 diff + 键集合全等 | `tests/contracts/test_event_channel_mapping_pdf_report.py` ★ | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 13 场景 | `test_acceptance_pdf_report.feature` ★ | Task 0/7 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_pdf_report.py` ★ | Task 0/7 |
| **集成测试** | 真实链五场景 | 全链（真实 Redis/PG/Qdrant/MinIO+Fake LLM/Embedding 双豁免）+ 引文预置链 | `tests/integration/test_integration_pdf_report.py` ★ | Task 6 |
| **SDD 架构验证** | 六边形约束 | 层依赖/reportlab 唯一宿主/落位/禁 import | `tests/unit/architecture/test_pdf_report.py` ★（epics L2303 钦定名） | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁（L2293-2295 钦定）和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **分层覆盖率** - **P1 阻断门禁**
  - 应用层：≥85%（epics L2294 钦定——引文聚合/编排服务/用例）
  - 集成测试覆盖率 ≥75%（epics L2295 钦定）
  - 领域层：≥90%（本 Story domain 新面仅 CitationEntry VO——小幅面高覆盖）
  - 基础设施层：≥75%（渲染器）
- [ ] **关键路径覆盖率 100%**（渲染器全块型/引文三段链全降级分支）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`——当前基线 746 零错误不回退；types-reportlab 已在 dev 组 pyproject:148）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：** 测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **L4 WORM 清理** | 测试 bucket 内 WORM 对象 `remove_objects(bypass_governance_mode=True)` 绕过端口直用 minio client（L4ObjectPort 无 remove_objects 方法；6-4 先例——test_acceptance_json_chain_of_thought.py:514/:1025，:58 为 docstring 注记）；桶解析复用 `_resolve_archive_bucket_name("archive-evidence")` 形态（6-4 :554-560）；对象键锚 report_id 定向删除 | WORM 7 年锁死测试 bucket |
| **引文预置清理** | Qdrant 点（FilterSelector chunk_id 面）+ PG documents 行（document_id 定向 DELETE）——teardown 登记面扩展 | 点/行残留污染后续测试 |
| **报告键清理** | L4 对象 + L2 strategic_reports 行 + outbox 行 + 归档三面（PG 档案行/Qdrant 点/MinIO WORM）+ Redis 快照键族——teardown 各步独立 try/except + 跑前跑后净增 0 断言（6-5a 七步链移植 + L4/引文预置两步扩展） | 残留污染后续测试 |
| **外部服务隔离** | Fake LLM/Embedding 双豁免（6-5a 八键族形态复用）+ 存储端口全真实（L4/Qdrant/PG/Redis 真实） | no-mock 红线 |
| **资源唯一性** | 测试数据 UUID 前缀隔离；对象键/引文 chunk_id/document_id 锚 uuid 天然唯一 | ID 冲突 |
| **并行隔离** | `xdist_group("blm-planning-perf")` 组复用（6-1~6-5a 同组）；pytest-xdist `--dist loadgroup` | 并行互扰 |
| **asyncio 上下文** | BDD 步骤用 `event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`）；集成裸 async 函数内直 await（禁 run_until_complete——6-4 集成教训）；`asyncio.Lock` 类变量 | context 丢失误 skip |
| **resolver 缓存** | `_clear_resolver_caches`（验收 context 前后）/`_fresh_resolver_per_test`（集成 autouse）——SINGLETON/SCOPED 缓存实例跨 loop 污染防线（6-5a 实施攻坚沉淀） | different loop 崩溃 |
| **延迟 import** | 本 Story 新模块一律在步骤/装配函数体内 import（收集期零 ImportError——红阶段必须是运行期） | 整文件 collection error |
| **pytestmark 完整性** | `acceptance + database + redis + qdrant + minio + xdist_group`（marker 名以 pyproject 注册为准：PG 用 `database`）；Task 7.2 专项复核 | marker 漏标漏跳 |

**禁止行为：**
- ❌ 验收/集成 mock 存储端口（mock 仅限外部 SaaS 豁免面）
- ❌ `@pytest.mark.skip` 写死跳过（必须 `pytest.skip()` 动态探测）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ autouse fixture 删除全局匹配资源
- ❌ pytest-xdist 并行时 BDD 步骤内 `asyncio.run()`

**验证要求：**
- [ ] 并行测试 `pytest tests/unit tests/integration tests/contracts tests/acceptance -n 8` 通过（四目录显式——裸 tests/ 会挂起，命令纪律）
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | PDF 主链六段编排 | Task 3 | 3.1-3.4 引文聚合+编排 | `test_pdf_report_generation_service.py` |
| AC-1 | L4 归档 + L2 + 用例 + 组合根 + CLI | Task 4 | 4.1-4.5 | `test_generate_pdf_report_use_case.py` / `test_agent_cli.py` |
| AC-1 | 全链真实服务验证 | Task 6 | 6.1-6.2 场景① | `test_integration_pdf_report.py` |
| AC-2 | 同源双渲染格式一致 | Task 3 | 3.1 聚合复用 | `test_pdf_report_generation_service.py` |
| AC-2 | 集成双格式对照断言 | Task 6 | 6.2 场景② | `test_integration_pdf_report.py` |
| AC-3 | 引文索引三段链 + 降级三态 | Task 3 | 3.1-3.3 | `test_pdf_report_generation_service.py` |
| AC-3 | 真实引文链（预置点+文档行） | Task 6 | 6.2 场景③④ | `test_integration_pdf_report.py` |
| AC-3 | 异常/降级 BDD 场景 | Task 0/7 | 0.4-0.6 + 7.1-7.2 | `test_acceptance_pdf_report.py` |
| AC-4 | 书签/目录内链/引文锚点 | Task 2 | 2.1-2.3 渲染器 | `test_reportlab_pdf_renderer.py` |
| AC-4 | 链接结构读回断言 | Task 6 | 6.2 场景⑤ | `test_integration_pdf_report.py` |
| AC-5 | 事件零新增 + report_type=pdf | Task 3 | 3.4 事件发布 | `test_pdf_report_generation_service.py` |
| AC-5 | 事件守护契约 | Task 5 | 5.1 | `test_event_channel_mapping_pdf_report.py` |
| AC-6 | 冻结面零触碰 + 全量回归 | Task 5 | 5.2-5.4 回归面 | 既有测试零修改通过 |
| AC-6 | 六边形架构验证 | Task 7 | 7.1-7.3 架构验证器 | `test_pdf_report.py`（architecture） |
| AC-7 | P95<60s/成功率/并发 3 | Task 6 | 6.4 性能采样 | `test_integration_pdf_report.py` |
| AC-7 | 清理闭环净增 0 | Task 6 | 6.5 净增断言 | `test_integration_pdf_report.py` |
| AC-8 | 中文/表格/渲染质量 | Task 2 | 2.1-2.3 | `test_reportlab_pdf_renderer.py` |
| AC-8 | pypdfium2 渲染冒烟 | Task 6 | 6.2 场景⑤ | `test_integration_pdf_report.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-8（规范源头）

> **目的：** 在进入代码实现前，明确增量冻结表、引文三段链、端口契约、异常契约、验收标准与六边形架构边界。

- [x] Subtask 0.1: 复核确认「增量冻结表」（附录 C 块型/锚点 ID/目录收录/section_count==11 恒等口径/degraded 不计入口径五项）；异常 492/493 开码——`grep -r "EXCEPTION_49[2-9]" src/domain/exceptions/` 零碰撞实证；复核引文读径锚点（`chain_of_thought_archive_service.py:200-203` assumptions 写侧 + `:239` EVIDENCE_PACKAGE 查询面 + `strategic_archive_service.py:315-323` query_archive 签名 + `l3_vector.py:85` get_point + `document_repository.py` find/DocumentQuery【tenant_id :33-34 必填 + PG 硬过滤 :99-103 + document_id UUID 类型——租户注入与 str→UUID 转换注记 OD-6】 + `agent_workflow_context.py:39` MVP_TENANT_ID + `semantic_chunk.py:158-170` chunk_id/page_start 字段）；复核 6-5a 聚合公开化波及面（`grep -rn "_aggregate_document" src/ tests/` 唯一命中 report_generation_service.py 自身——tests 零直接引用实证复跑）
- [x] Subtask 0.2: 验证 reportlab CJK 字体注册可用性（`UnicodeCIDFont("STSong-Light")` 注册 + 中文段落渲染最小脚本实证）+ pypdf 读回行为实证（outline 可读性/`/Annots` link 遍历/`extract_text` 对 CID 字体的实际行为——AC-8 断言分层钉死的实证依据；**R3 预实证结论待复验**：STSong-Light 的 extract_text 完美工作、命名目标已解析为 /Dest 直接数组、linkRect 前向引用单遍渲染可行、悬空链接 save 期抛错）+ pypdfium2 渲染冒烟可用性；**pyproject reportlab 依赖组迁移**（test 组 → 主依赖组——操作序列：手工编辑 pyproject.toml【test 组删 reportlab 行 :126 / 主组加 `reportlab = "^4.5.1"`】→ `poetry lock --no-update`【锁定 4.5.1 不重解析，避免 add/remove 命令版本漂移】→ `poetry install` 实证 src 环境 import 可用）
- [x] Subtask 0.3: 定义端口契约（pdf_report.py 模块 docstring 契约区：对象键模板/EVIDENCE_BUCKET_TYPE 单源/引文三段链契约/降级三态判定/CitationEntry 值域）
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_pdf_report.feature`（13 场景钉死——AC-1×2/AC-2×1/AC-3×3/AC-4×2/AC-5×1/AC-6×1/AC-7×2/收尾×1；场景清单须逐一标注覆盖 AC 编号，13↔8 AC 双向覆盖互检【每 AC 至少一场景归属或注记归属理由——AC-8 经单测+集成场景⑤承载】后钉死，防自拟场景覆盖面漂移）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_pdf_report.py`（6-5a 验收文件装配链整体移植：三件套骨架 + 延迟 import + teardown 七步链 + L4/引文预置清理扩展 + Fake LLM 八键族 + 归档轻装配复用；PDF 服务装配 `_make_pdf_report_service`——tmp_path L0 注入形态不适用（PDF 不落 L0），L4 走真实 resolve + 测试 bucket；collection/tenant_id 经服务构造参数注入（测试租户与引文预置 PG 行同值闭环——OD-6））
- [x] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——先 `pytest tests/acceptance/test_acceptance_pdf_report.py --collect-only -q` 确认 13 场景收集期零 error，再实跑确认失败形态为**运行期 ImportError**【延迟 import 纪律】）
- [x] Subtask 0.7: 链路接线断言清单落档（组合根三注册/事件发布点/outbox 断言键/L4 WORM 测试面先探——复用 6-4 验收探测+建桶+WORM 自愈形态 test_acceptance_json_chain_of_thought.py:995-1035，archive-evidence 桶已在位、探测以自愈为主）+ deferred-work.md 台账处置（L129 data_pipeline 再锚定注记 + L170 事件消费顺延注记 + L192 ChainOfThoughtSchema 零触发注记（6-5b 直读 assumptions JSON 与 6-5a 同理——留项维持）+ 6.5a-DF1 维持注记 + 6.5a-DF2 风险面转移注记（L4 键锚 report_id 消解 PDF 链撕裂面——留项范围收窄至 Markdown 面）+ **新留项登记**：bbox ingestion 写入缺口（3-8 遗留——chunk_indexing_handler.py 未写 bbox/page_start 入 Qdrant payload，触发=6-7 溯源树立项或 6-8 Web 高亮立项）+ REST 导出面触发条件复核并入 #4 DF1 注记（CLI-only 延续下触发条件不变——不另立条目）+ 思维链全文附录维持 YAGNI 归 6-7 注记（R4N-1——引文索引已交付溯源消费面，chain.to_display() 资产在位）+ 6-5a CR2-F12/CR3-F6 边缘形态 PDF 链评估落档注记（PDF 链结构同源直渲染【VO→reportlab】不经 Markdown 文本与转义面，`\|` 双重转义/≥4 前导空格缩进两边缘形态不影响 PDF 面——留项维持 Markdown 面归 6-11/后续统一，R4N-2））
- [x] Subtask 0.8: 关键代码锚点复核（并行会话提交会使行号漂移——上表锚点逐条 grep 复验）
- [x] Subtask 0.9: 既有契约测试回归基线（`pytest tests/contracts/ -q` 全绿记录——6-5a 基线 1479+ 为 collected 用例数【含参数化展开】口径，以本 Task 实测记录为准、不作为硬编码断言；contracts 目录 117 文件/1342 test 函数）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（增量冻结表 + 引文三段链 + 端口契约 + 异常 492/493）
- [x] 验收测试运行失败（预期行为，红阶段确认——运行期 ImportError）
- [x] 台账处置落档

---

### Task 1: 领域层——CitationEntry VO + report 异常扩展（492/493）

**关联 AC:** AC-3（引文条目载体）/ AC-1（492/493 异常契约）

> **domain 新面极小**（本 Story 主体在 application/infrastructure）；VO 零依赖高可测。

#### TDD 循环 A：CitationEntry VO

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/test_citation_entry.py`（index≥1/chunk_id 非空/status 值域三元组/page≥0 边界——242 异常码断言；解析降级三态构造合法性） |
| 🟢 绿 | 实现 `src/domain/value_objects/citation_entry.py` 最小代码 |
| 🔄 重构 | 类型注解 + Google 风格全中文 docstring + `ruff`/`mypy` |

#### TDD 循环 B：report 异常扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/exceptions/test_report_exceptions.py`（492/493 构造/context 暴露/to_dict/HTTP 映射 492→500、493→500） |
| 🟢 绿 | 扩展 `src/domain/exceptions/report_exceptions.py`（两类追加 + `_code_ranges.py` 注册 + `__init__.py` 导出 + `EXCEPTION_HTTP_MAP` + design.md §3.3.2 两张表回填） |
| 🔄 重构 | 全量异常回归（`pytest tests/unit/domain/exceptions/ -v` 含 uniqueness/code_ranges + `test_exception_handlers.py` 键集合快照同步） |

- [x] Subtask 1.1: 🔴 红 — 编写 VO/异常失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现 CitationEntry + 492/493 四处登记
- [x] Subtask 1.3: 🔄 重构 — 异常回归全绿 + ruff/mypy 零错误

**完成标准/Definition of Done:**
- [x] VO + 异常全部实现（domain 零依赖——importlinter 验证）
- [x] TDD 循环全部通过（含变异实证：status 值域守卫改坏 → 红 → 还原 → 绿）
- [x] 覆盖率 domain ≥90%（新增面 100%）

---

### Task 2: 基础设施——ReportLabPdfRenderer（渲染器）

**关联 AC:** AC-2（格式一致）/ AC-4（导航结构）/ AC-8（渲染质量）

> **reportlab 唯一宿主**（infrastructure/reporting/ 新子包）；消费 MarkdownReportDocument 单参——与 render_markdown_report 对称。

#### TDD 循环 A：渲染器核心

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py`（构造 6-5a VO 三态样例文档【经 6-5a payload 工厂族 + aggregate_report_document 聚合生成，或直接构造 VO——dev 自选；三态覆盖面固定：正常/**快照缺失（附录 A 省——目录条目非恒定的 PDF 侧敏感面）**/降级；缺行态归 6-5a 聚合测试已覆盖面不重复】→ render → bytes 非空 + pypdf 断言：页数≥1/outline 层级（display_name 源构造期望）/metadata Title==REPORT_TITLE_TEMPLATE；**中文渲染**：未注册字体渲染中文抛异常是天然红——注册 STSong-Light 后成功；表格文本全文比对（ASCII 抽样冗余——R3 升级口径）；目录 link 注释（/Annots Subtype==/Link 目标非空）；引文锚点 citation-{index} 可解析；悬空链接守护负向用例：构造引用未注册锚点的样例文档 → render 抛 ValueError【save 期天然守护——R3 实证形态；492 包装面由 Task 3 mock render raise 用例关联承载】） |
| 🟢 绿 | 实现 `src/infrastructure/reporting/reportlab_pdf_renderer.py`（`ReportLabPdfRenderer(PdfRendererPort)`：STSong-Light 注册【模块级一次】+ 块型分派渲染【paragraph/bullet_list/table/callout 四块型】+ 章节遍历 + bookmarkPage/addOutlineEntry + linkRect/linkDest 目录内链【linkRect 可前向引用 bookmarkPage 命名目标——save 时统一解析、目标缺失抛错即天然悬空链接守护；顺序渲染单遍即可无需两遍渲染】+ 附录 C 条目锚点 + Table 列宽策略 + metadata Title） |
| 🔄 重构 | 块渲染私有函数族拆分（与 markdown_report_renderer 结构对称）/类型注解/ruff+mypy |

- [x] Subtask 2.1: 🔴 红 — 编写渲染器失败测试（含变异实证：outline 层级生成改坏 → 红 → 还原 → 绿）
- [x] Subtask 2.2: 🟢 绿 — 实现渲染器（四块型 + 三层导航 + CJK 字体）
- [x] Subtask 2.3: 🔄 重构 — 渲染器代码优化（pypdfium2 渲染冒烟用例：每页非空白像素——AC-8）

**完成标准/Definition of Done:**
- [x] 渲染器实现完成（reportlab 仅此文件 import——架构测试 D 验证器守护）
- [x] TDD 循环全部通过（含变异实证）
- [x] 覆盖率 infrastructure ≥75%（渲染器新增面 ≥90%）

---

### Task 3: 应用层——PdfReportGenerationService（引文聚合 + 六段编排）+ 端口

**关联 AC:** AC-1 / AC-2 / AC-3 / AC-5

> **九依赖注入**：chain_archive_service + snapshot_repository + report_repository + event_publisher + pdf_renderer + l4_object + l3_vector + document_repository + archive_service（另有 collection 名与 tenant_id 两个**服务构造参数**——配置态注入非依赖态，九依赖数不变，见端口契约节注入小节）。**6-5a 聚合复用前置**：`_aggregate_document` → `aggregate_report_document` 公开化（同文件更名 + 内部调用点同步——行为零变）。

#### TDD 循环 A：聚合公开化（前置小步）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写公开函数引用失败测试（`from src.application.services.report_generation_service import aggregate_report_document`——ImportError 红先证；既有 6-5a 单测全绿不破坏） |
| 🟢 绿 | 更名 `_aggregate_document` → `aggregate_report_document`（docstring 补公开契约说明：入参/返回 _Aggregation 结构/被 6-5a 与 6-5b 双链消费；顺带注记返回的 `MarkdownReportDocument` 是**双渲染共用中间文档模型（IR）**——名字带 Markdown 前缀但已成 PDF 链同源 IR，防后来者误解【改名破坏 6-5a 冻结面不可行，docstring 注记是零成本消歧位——R3B-2】） |
| 🔄 重构 | 6-5a 服务内部调用点同步 + 全量单测回归（6-5a 37 用例零破坏实证） |

#### TDD 循环 B：引文聚合三段链

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_pdf_report_generation_service.py` 引文面（收集：assumptions 多行合并去重保序【跨步骤重复 chunk_id → 唯一索引】/evidence_refs 缺键容错 `.get("evidence_refs", [])`；解析：get_point→payload.document_id→find→filename+chunks 匹配 page_start 全链 mock 断言【AsyncMock(spec=Port) 九依赖 + `_make_*` 工厂——6-5a `_make_service` 形态扩展；find 调用参数值级断言：tenant_id==服务注入租户 + document_id==UUID 化值（payload str→uuid 转换链）】；降级三态：point_missing/document_missing/page 缺 0 各钉一用例 + unresolvable_citation_count 计数 + 整体容错用例（query_archive raise 与 get_point 连接级 raise 两入口同 try 块——单用例即覆盖：报告成功 + 附录 C 空态说明 + citation_count==0——AC-3 整体容错边界）；组装：附录 C section 追加【table 块型四列 + 空引文单行 callout】+ document VO 追加后原 11 小节不变【聚合复用不破坏】）——**本循环含变异锚**：去重保序断言改坏（去重逻辑移除→重复索引出现）→ 红 → 还原 → 绿（引文三段链是本 Story 核心新逻辑，断言活性与 6-5a 防御密度对齐——R3B-1） |
| 🟢 绿 | 实现 `src/application/ports/pdf_report.py`（双端口 + 常量）+ `src/application/services/pdf_report_generation_service.py` 引文聚合私有函数族（`_collect_citation_ids(records) -> list[str]`【去重保序，首现次序】/`_resolve_citation(chunk_id, stage) -> CitationEntry`【三态降级判定 + 整体容错边界】/`_build_citation_section(entries) -> 附录 C section`【table 四列/空态 callout，追加进 document VO】） |
| 🔄 重构 | 引文局部累积清单（与 6-5a 附录 B 同纪律——AC-7 并发/20 轮防互扰） |

#### TDD 循环 C：六段编排 + 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展同文件（六段编排顺序断言【聚合→latest 快照辅源（容错）→引文→渲染→L4 archive 调用参数值级（bucket=="archive-evidence"/object_key 模板渲染比对——archive 签名无 content_type 勿断言）→L2 save→事件】——与 AC-1 ⑥段同构、⑤段=L4+L2 两动作细粒度展开；490 全缺同判；492 渲染异常包装【mock render raise → PdfRenderingError 492 context.plan_id】；493 L4 失败包装【mock archive raise → ReportEvidenceStorageError 493】；事件组装值级断言【report_type=="pdf" 三键非空——独立构造期望比对】；发布失败两形态宽容【失败 PublishResult/raise 各钉一用例——is_success 双防线】；L2 metadata citations/citation_count 键断言） |
| 🟢 绿 | 实现编排主体（`generate_pdf_report`：计时窗口→490 判定→聚合复用→latest 快照辅源（容错——与 6-5a :174 同形态）→引文聚合→渲染【同步调用——CPU 密集直接调用不经 to_thread，注记落 docstring；量级评估：亚秒级 CPU 段在 gather 3 并发下互斥执行放大有限（3×<100ms 级），L4/PG 侧全 to_thread/async 不阻塞 loop——口径维持】→L4 archive【exception 包装 493】→实体构造【file_path=PDF_OBJECT_KEY_TEMPLATE 派生】→L2 save→事件发布→返回） |
| 🔄 重构 | 计时窗口注记（generation_ms = 聚合起点→L2 落库前——6-5a CR1-F16 口径同款；与 P95 窗口【聚合起点→事件发布返回】双窗口辨析：起点同、终点异，generation_ms 是实体字段记录单次耗时、P95 是 AC-7 采样统计口径，非同一窗口）+ ruff/mypy |

- [x] Subtask 3.1: 🔴 红 — 聚合公开化 + 引文聚合失败测试
- [x] Subtask 3.2: 🟢 绿 — 端口 + 引文聚合实现
- [x] Subtask 3.3: 🔴 红 — 编排/事件失败测试（含变异实证：report_type 组装改坏 → 红 → 还原 → 绿）
- [x] Subtask 3.4: 🟢 绿 — 六段编排实现 + 端口契约测试 `tests/contracts/test_port_contract_pdf_report.py`（五断言族——服务面注册在 Task 4 组合根落地后 resolve 断言转绿；构造参数默认值断言归单测【服务构造默认 str(MVP_TENANT_ID)/"documents" 各一用例】，契约测试仅断言九依赖注入面——防过度断言）

**完成标准/Definition of Done:**
- [x] 引文聚合 + 编排服务 + 端口实现完成
- [x] TDD 循环全部通过（含变异实证×3：report_type 组装 / 引文去重保序【R3B-1 补】/ outline 层级生成【归 Task 2 Subtask 2.1 实锚——全 Story 变异锚四处：T1 status 值域/T2 outline 层级/T3 report_type+引文去重】）
- [x] 覆盖率 application ≥85%（epics L2294 钦定）

---

### Task 4: 用例 + 组合根 + CLI

**关联 AC:** AC-1（CLI 入口 + 组合根装配）

> **6-4 P0 教训延续**：L4/l3/document_repository 经组合根 resolve 注入（服务构造签名九依赖全 keyword-only）；CLI 生产通道可达性排查（三步法——组合根 lambda 依赖 resolve 链实证）。

#### TDD 循环 A：用例 + 组合根三注册块

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_generate_pdf_report_use_case.py`（plan_id UUID 守卫 242/透传/返回实体——6-5a 用例三用例同构） |
| 🟢 绿 | 实现 `src/application/use_cases/generate_pdf_report.py` + 组合根 `=== Story 6-5b ===` 三注册块（pdf_renderer SINGLETON【ReportLabPdfRenderer 无状态】/ pdf_report_generation_service SINGLETON 九依赖 / pdf_report_generation_use_case SINGLETON——增量注册零既有 lambda 改动；collection/tenant_id 构造参数组合根**不显式传参即用服务默认值**（"documents"/str(MVP_TENANT_ID)）——测试经服务构造参数覆写注入，生产走默认，与 6-5a 服务实例默认值形态一致） |
| 🔄 重构 | 契约测试 resolve 断言转绿 + 既有组合根断言零破坏复核 |

#### TDD 循环 B：CLI --format 参数扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（`--format` 参数解析【默认 markdown 向后兼容——既有用例零修改通过】/`--format pdf` 分发到 pdf_report_generation_use_case/成功打印【report_id/file_path（L4 对象键）/报告类型 pdf/引文计数/生成耗时——打印面含 citation_count 汇总】/490/492/493 双层异常定式【DomainError=`[{code}] {message}` stderr + return 1】/CLI 生产通道 L4 resolve 可达断言） |
| 🟢 绿 | 扩展 `src/entrypoints/agent_cli.py`：report-generate 加 `--format {markdown,pdf}` choices 参数（default=markdown）+ `_run_report_generate` 按 format 分发 resolve（`report_generation_use_case` / `pdf_report_generation_use_case`）+ `_print_report_summary` 扩展（format 感知：memory_id 反解仅 markdown 分支——PDF 分支打印对象键与 bucket【bucket = `EVIDENCE_BUCKET_TYPE` 常量，CLI 自 application/ports/pdf_report import——实体不携 bucket 字段】） |
| 🔄 重构 | 打印格式统一 + CLI 全量回归（既有 markdown 用例零破坏实证） |

- [x] Subtask 4.1: 🔴 红 — 编写用例失败测试
- [x] Subtask 4.2: 🟢 绿 — 实现用例 + 三注册块
- [x] Subtask 4.3: 🔴 红 — 编写 CLI 失败测试
- [x] Subtask 4.4: 🟢 绿 — 实现 --format 扩展
- [x] Subtask 4.5: 🔄 重构 — CLI 全量回归 + ruff/mypy

**完成标准/Definition of Done:**
- [x] 用例/组合根/CLI 全部实现
- [x] `alembic upgrade head` 零变化（无新 migration）+ 四目录相关测试全绿
- [x] CLI 生产通道 resolve 链实证（三步排查法）

---

### Task 5: 契约守护与 6-5a/6-x 回归面

**关联 AC:** AC-5（零新增）/ AC-6

> **性质说明：** 负向契约断言 + 全量回归（复用面 Story 的回归面守卫）。

- [x] Subtask 5.1: 🔴🟢 编写 `tests/contracts/test_event_channel_mapping_pdf_report.py`（event_channels.yaml + DEFAULT_MAPPINGS 零 diff 守护——键集合冻结快照全等断言：56 键基线 + ReportGenerated 既有登记存在性【6-5a test_event_channel_mapping_report.py 形态平移】）
- [x] Subtask 5.2: 冻结面零触碰验证（workflow_events.py/event_channels.yaml/channel_router.py/blm_planning_prompts.py/blm_planning.py/strategic_report.py **全文件零 diff**——git diff 逐文件实证；report_generation_service.py 与 report_exceptions.py 为**本 Story 钦定改动文件**【前者仅聚合更名一行、后者仅 492/493 两类追加】——diff 范围限钦定改动行，491 既有行零触碰即非冻结违例 + 聚合公开化更名的唯一允许改动注记）
- [x] Subtask 5.3: 全量回归（四目录显式两轮稳定）
- [x] Subtask 5.4: 红线三查（`grep -rn "raise ValueError" src/` + `grep -rn "HTTPException" src/ | grep -v handlers` + `grep -rn "# noqa\|# type: ignore\|# pylint" src/ tests/` 本 Story 新建/修改文件零输出）+ 提交信息禁 AI 署名

**完成标准/Definition of Done:**
- [x] 契约测试全绿 + 冻结面零 diff 实证（聚合更名唯一例外注记）
- [x] 四目录全量回归两轮稳定
- [x] 三条 grep 本 Story 面零输出

---

### Task 6: 集成测试——真实链五场景

**关联 AC:** AC-1 / AC-2 / AC-3 / AC-7

> **真实服务四件（Redis/PG/Qdrant/MinIO）+ Fake LLM/Embedding 双豁免**；服务内含 L2 落库链——真实提交 + 定向 DELETE 清理（6-5a 钦定口径）；teardown 链 + 跑前跑后净增 0；**引文预置链**（集成面新增装配：Qdrant 点 upsert + PG documents 行插入）。

- [x] Subtask 6.1: 编写 `tests/integration/test_integration_pdf_report.py` 装置（6-5a 集成装配函数族移植：`_fresh_resolver_per_test` autouse + `_make_material` 三型分派 + `_make_fake_embedding` + `_probe_services` 直 await 探测 + 归档构造 `_archive_steps`；**引文预置** `_preset_citation_fixture`：**复用既有测试 collection**（裁定：零 collection 生命周期管理，点级 FilterSelector chunk_id 定向清理即闭环——不用临时 collection 形态避免残留污染【6-5a 测试 Qdrant 清卷重建环境教训】）upsert 点（point_id=chunk_id，payload={document_id/chunk_header/content}）+ PG documents 插行（tenant_id=服务实例注入的测试租户值【预置与查询同租户闭环——find 硬过滤下租户不匹配必现 document_missing 假降级】+ filename + metadata["chunks"]=[{chunk_id/page_start}]）；**L4 真实通道**：resolve l4_object + 测试 bucket WORM 面探测；teardown 扩展：L4 对象定向删（bypass）+ 引文预置两面清理 + 6-5a 七步清理链移植）
- [x] Subtask 6.2: 五场景：①全链生成（八步归档含 evidence_refs→generate_pdf_report→实体/L4 读回（retrieve+pypdf 页数）/L2 行（report_type=="pdf"+metadata citations）/outbox 四键/引文附录 C 值级【display_name 源独立构造期望】）②双格式对照（同 plan_id 先 markdown 后 pdf——section_count 恒等 + 章节标题族双面对照 + 附录 B 降级行数 == degraded_section_count 联动断言【AC-2 第三条承载——聚合复用自然保证双格式两侧同值】）③引文降级（evidence_refs 喂不存在 chunk_id → [溯源不可用] 条目 + unresolvable_citation_count==M + 报告成功 + section_count 恒 11）④490 全缺（独立 plan_id → code/message/context + 零落库零对象）⑤导航结构与渲染质量（outline 层级/link 注释/引文锚点/pypdfium2 每页非空白/metadata Title）
- [x] Subtask 6.3: 🔴 红→🟢 绿循环（首跑装配缺口排查 → 全绿 + xdist 并行两轮稳定）
- [x] Subtask 6.4: 性能采样（单一数据源 plan_id × 20 次【归档链+引文预置一次构造】；每轮新 report_id + L2 行累计 20 + **L4 对象数 20**；P95<60s 断言【实测预期同 6-5a 亚秒级——引文解析+L4 上传增量；**P95 上限常量自定 60.0——勿照抄 6-5a 源码的 `_P95_LIMIT_SECONDS=30.0`**（那是 6-5a epics 口径，本 Story epics 钦定 60s）】；并发 3（asyncio.gather 三 plan_id——互不串扰 = 每份 L2 行 plan_id↔report_id 一一对应值级断言 + 三 report file_path 对象键互异集合断言）；OD-8 口径声明落 docstring）
- [x] Subtask 6.5: 净增 0 断言（跑前基线 → 清理后对照【报告行/L4 对象/outbox 行/引文预置面 全净增 0】；口径注记：归档三面属测试自构造预置【归入引文预置面口径合并对照】、Redis 快照键族归 6-5a 七步链对照面——净增 0 四项为 PDF 链新增面）
- [x] Subtask 6.6: 覆盖率集成 ≥75% 复核（epics L2295 钦定）

**完成标准/Definition of Done:**
- [x] 五场景全绿（真实服务环境）单进程 + xdist 双模式两轮稳定
- [x] 净增 0 + P95/并发断言通过
- [x] 引文预置清理闭环实证

---

### Task 7: SDD 架构约束验证测试 + 开发结束验收

**关联 AC:** AC-6（架构面）+ 全 AC 收尾

> **性质说明：** Task 7.1-7.3 是 SDD 规范验证测试（验证架构约束）；7.4-7.5 是 Story 收尾验收。

#### 架构验证测试实现

- [x] Subtask 7.1: 🔴 编写 `tests/unit/architecture/test_pdf_report.py`（epics L2303 钦定名——四验证器：A domain 零依赖【citation_entry.py 白名单双向校验】/B 应用层隔离【pdf_report_generation_service 零 infrastructure import + 禁本地 Protocol】/**C reportlab 唯一宿主**【全 src/ AST 扫描 import reportlab 仅命中 reportlab_pdf_renderer.py——本 Story 特有验证器】/D 落位守护【新文件冻结路径清单——单源 = 「项目结构说明」节硬编码进验证器 + rglob 防散落 + CLI resolve 端口名】）
- [x] Subtask 7.2: 实现 + 循环依赖检测（ruff `I` 规则——不引入 pylint）+ 验收 13 场景转绿 + pytestmark 复核（六项齐备）+ Run with docstring
- [x] Subtask 7.3: 运行 `pytest`（四目录显式）、`ruff check`、`mypy` 收尾校验 + 覆盖率门禁复核（整体≥80%/application≥85%/integration≥75%/domain≥90%）
- [x] Subtask 7.4: 三红线 grep + 提交信息审查（禁 AI 署名）+ deferred-work 留项终置 + architecture.md 桶表 evidence-packages 行实况注记回填（蓝图名保留为逻辑分类、证据归档实况统一落 archive-evidence 复合物理桶【3-10 起】——OD-4 裁定伴生义务）
- [x] Subtask 7.5: sprint-status.yaml 状态流转（ready-for-dev→in-progress→review；review→done 归 code-review 环节）

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过（含 reportlab 唯一宿主验证器）
- [x] 13 验收场景全绿 × 双模式 + 四目录全量两轮稳定
- [x] Story 可进入 `review`/`done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)（活文档在 `docs/architecture/`）

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（ReportGenerated 复用零新增）+ 五层存储（**本 Story 首用 L4 证据包通道**——PDF bytes WORM 归档；L2 元数据复用；L0 零触碰）
- **设计约束:** 领域层零依赖（importlinter 四契约——**reportlab 禁入 domain**）；`@dataclass(frozen=True)` 不可变 VO；服务经端口组合注入（R2 九依赖）
- **接口治理:** 统一端口注册（PortSpec）、Registry/Resolver/ContractGate、组合根唯一装配、增量注册零破坏既有 lambda
- **技术栈:** Python 3.11+ / reportlab 4.5.1（**依赖组迁移：test → 主依赖组**）/ pypdf 6.14.2（读回断言——主依赖组已在位 pyproject:74 零迁移）/ pypdfium2 5.12.1（渲染冒烟——主依赖组已在位 :82 零迁移）/ MinIO（L4ObjectPort archive bytes 直传 + WORM GOVERNANCE）
- **关键架构条款:** 交互流程 38（L417「证据包保存→Object_Storage」——本 Story 兑现 6-5a defer 面）；L2543-2550 桶设计蓝图（逻辑桶表 `evidence-packages/` 为逻辑分类未落地——代码实况单源 strategic_archive_service.py:40 `archive-evidence`，实况注记 Task 7 回填，OD-4）；§10.1 L884 ReportGenerated 7 年存储；prd FR-UI-11（L1997「可点击的引文索引」+ 验收「引文索引准确率 100%」——口径=条目溯源三元组与数据源一致，AC-3 值级断言承载）；NFR-PERF-03（<30s 更严口径与 epics 60s 上限双口径注记见 AC-7）；FR-SR-08（L1788 原始三元组=文档ID/切片ID/字符范围——本 Story 交付=文档名/页码/切片标识是其消费面变体，字符范围归 bbox defer OD-6）

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | 范围边界：6-5b = 同源 PDF 渲染（infrastructure reportlab）+ 引文索引（evidence_refs 首消费→附录 C）+ PDF 内部导航（书签/目录内链/引文锚点）+ L4 WORM 归档 + L2 元数据（report_type="pdf"）+ ReportGenerated 复用（report_type="pdf"）+ CLI `--format pdf`。**不含**：bbox 高亮跳转（数据缺口在 ingestion 侧+Web 阅读器归 6-8——defer 登记）、白标（6-11）、REST 导出（6.5a-DF1 维持）、图本体位图（OD-9 表格承载延续）、溯源树（6-7）、Markdown 链任何行为变化（零改动复用） | epics L2266-2307 + 6-5a 范围边界表 L30（PDF/引文明文留位）+ 依赖链 L2015/2020/2035 |
| **OD-2** | **宿主形态延续零新偏离**：应用服务+用例+CLI 直交（6-5a OD-2 偏离 Prefect 的既定形态直接沿用——PDF 生成同为单次同步 <60s 纯读+渲染+写，无 DAG 编排需求）；data_pipeline 轨不激活（deferred-work L129 注记维持） | 6-5a OD-2 全部四理由对本 Story 同构成立 |
| **OD-3** | **同源双渲染**：「将 Markdown 转换为 PDF，保持格式一致」（epics L2276；L2274 是 Given「Markdown 报告已生成」行恰为下句重读对象）的承载形态 = **同一聚合产物（aggregate_report_document → MarkdownReportDocument VO）双渲染器分派**（render_markdown_report→str / PdfRendererPort.render→bytes），非 Markdown 文本再解析（round-trip 解析需引入 Markdown 解析依赖且 GFM 转义面复杂——结构同源是更强的一致性保证）。聚合复用前置 = `_aggregate_document` 公开化（更名 `aggregate_report_document`——同文件内更名行为零变，tests 零直接引用实证）。Given「Markdown 报告已生成」口径重读 = 归档数据面就绪即 PDF 可生成（同数据源平行生成——不要求 Markdown 报告行存在，不引入顺序耦合） | report_generation_service.py:176-177 聚合/渲染两步分离实证 + 单源优先 + epics Given 语义重读（6-5a Given「八步归档在位」同构） |
| **OD-4** | **PDF 二进制走 L4 WORM 归档**（不走 L0——L0 全通道 str 钉死：write `content: str` 文本模式 + `.md` 扩展名六处硬编码【src/infrastructure/storage/fs/file_memory_adapter.py :49-69/:71-89/:91-109/:111-125/:127-143/:251-261】，扩端口波及 Protocol/适配器/组合根/既有 mock 且与「L0=markdown 记忆文件」定位冲突）：`L4ObjectPort.archive(bucket_type="archive-evidence", object_key=f"reports/{plan_id}/{report_id}.pdf", content=bytes, retention_days=2555)`——**桶名对齐代码单源**（strategic_archive_service.py:40 `L4_BUCKET_TYPE`——与 6-3/6-4 证据归档同桶：evidence_refs 上游 EVIDENCE_PACKAGE 归档即在此桶，证据流一桶贯通；对象键 `reports/` 前缀与归档键 `{archive_id}/` 前缀天然隔离零互撞；architecture.md L2548 蓝图名 `evidence-packages` 为逻辑分类未落地且归档链路不自动建桶——新桶全环境首建是纯增量风险，蓝图分歧实况注记 Task 7 回填）；bytes 直传 + WORM 7 年（报告交付物审计语义恰配 architecture §10.1「7 年存储」+ L4 定位「原始文档、证据包、审计归档」）；**对象键锚 report_id**（非 memory_id 秒级时间戳——每 report 恰一对象天然唯一：无同秒覆写、无 WORM 冲突、幂等锚语义完美；6.5a-DF2 撕裂风险面在 PDF 链路不存在——L4 put 服务端原子，留项范围收窄至 Markdown 面）。file_path = 对象键逻辑路径（可移植审计语义延续 6-5a OD-4 哲学；CLI 打印 bucket+对象键定位）。**GOVERNANCE 模式注记**（architecture L1024 警告现状未升 COMPLIANCE）：**WORM 生效前提 = 桶已开 object lock**（无锁桶 `set_object_retention` 抛 S3Error→493 上抛非静默——测试面探测自愈链 make_bucket(object_lock=True) 确保【6-4 先例】，生产面 archive-evidence 桶 6-3/6-4 归档先例已带锁）；archive 两步非原子（put→set retention，set 失败残留无锁半归档态可接受——report_id 唯一键下重试覆盖再 set，493 语义不受损）；测试清理 bypass_governance_mode=True 先例在位 | architecture.md L417/L2548/L1024 + 代码桶名单源（strategic_archive_service.py:40 / chain_of_thought_archive_service.py:63——6-3/6-4 全线沿用）+ L4ObjectPort.archive bytes 签名（l4_object.py:107-124 + minio_repository.py:207-249 BytesIO put 实证）+ 6-5a OD-4 defer 钦定 + 最小契约变更（L0 零扩展） |
| **OD-5** | **PDF 渲染器层位 = application 端口 + infrastructure 实现**：`PdfRendererPort`（application/ports——R2 具体应用端口，仅被报告编排消费无领域消费者，ReportGenerationServicePort 同层先例）+ `ReportLabPdfRenderer`（infrastructure/reporting/——**reportlab 唯一宿主**，架构测试 C 验证器守护）。**与 6-5a markdown 渲染器 domain 落位的差异是必然非不一致**：markdown 渲染=纯字符串拼接零依赖可进 domain；PDF 渲染=第三方库依赖（importlinter forbidden 面）必须出 domain——「渲染规则是领域知识，渲染技术是基础设施」的分界线 | importlinter domain-no-external-dependencies + pdf_page_renderer（domain 端口 bytes 先例）与 ReportGenerationServicePort（application 端口先例）双先例中取语义贴合面 + R2/R3 设计规则 |
| **OD-6** | **引文索引数据链与降级**：三段链（收集 `query_archive(ArchiveQuery(plan_id, archive_type=EVIDENCE_PACKAGE))` → assumptions["evidence_refs"] 去重保序；解析 chunk_id → `L3VectorPort.get_point(collection, chunk_id)` → payload.document_id（str→uuid.UUID 转换）→ `DocumentRepositoryPort.find(DocumentQuery(tenant_id, document_id))`（tenant_id 服务构造注入默认 str(MVP_TENANT_ID)——数据链无租户可用【StrategicArchive/ArchiveQuery/Qdrant payload 均无 tenant_id】，5-3 单租户先例，多租户归后续 Story）→ filename + metadata["chunks"] 匹配 page_start；组装附录 C table 四列）。**降级三态宽容**（point_missing/document_missing/page 缺——引文是增强面非阻断面，unresolvable_citation_count 入 metadata）。**bbox 缺口 defer**：Qdrant payload 现状仅 6 键无 bbox/page_start（chunk_indexing_handler.py:156-168——3-8 story L118 自注记前置未实现，属 ingestion 侧遗留非报告侧）；本 Story 交付页码级溯源（chunks 元数据 page_start 真实可得）+ 溯源三元组完整携带（L2 metadata citations——6-8 Web PDF.js 高亮/6-7 溯源树的查询面）；**不复用 3-8 TraceabilityPort**（trace(claim) 按文本检索非 chunk_id 解析；get_citation_detail 内存缓存不持久——语义不匹配，直用 L3 get_point）；**不复用 Citation VO**（检索溯源域语义：text/offset/bbox/confidence 无 filename——报告引文条目新 VO）。正文不插句级引用标记（evidence_refs 步骤级粒度不支持——附录 C 按步骤分组语义经「首现次序索引」承载，步骤归属信息经 L2 metadata stage 关联保留） | chain_of_thought_archive_service.py:200-209 实证（assumptions 写侧 + EVIDENCE_PACKAGE）+ Agent 双验数据面 + FR-SR-08 三元组口径 + 6-5a 降级哲学延续 + YAGNI |
| **OD-7** | **测试文件命名**（epics 半采半离——6-5a OD-7 同款）：unit/architecture 用 epics 钦定 `test_pdf_report.py`（L2303 采）；integration `test_integration_pdf_report.py`（**对 epics L2304 `test_pdf_report_integration.py` 显式偏离**——仓规 test_integration_* 惯例，6-3 OD-8/6-4 OD-7/6-5a OD-7 四连先例）；acceptance `test_acceptance_pdf_report.feature/.py`；渲染器 `test_reportlab_pdf_renderer.py`；服务 `test_pdf_report_generation_service.py`；用例 `test_generate_pdf_report_use_case.py`；契约 `test_port_contract_pdf_report.py`/`test_event_channel_mapping_pdf_report.py` | epics 钦定名半采半离 + 记忆「禁止故事编号命名文件」+ 四连先例 |
| **OD-8** | **性能口径**：P95<60s（epics L2289——上限钦定；口径=聚合起点→事件发布返回不含 BLM run，6-5a OD-8 延续）；「导出<1 分钟」（L2279）由 60s<1min 钦定关系覆盖单指标承载；采样形态=单一数据源 plan_id × 20 次（6-5a OD-8 先例——引文预置一次构造；断言锚=新 report_id + L2 行 20 + **L4 对象 20**——键锚 report_id 无同秒覆写豁免问题，比 6-5a 更强）；成功率=N 生成 N 三元可读回（L4 retrieve+pypdf 页数>0/L2 行/事件）；**「引文点击响应<300ms」CLI-only 口径重读**：该指标语义本源是 PDF.js 阅读器点击→定位原文档坐标（prd L419 溯源跳转/epic_3 L445/UX L893——Web 交互面归 6-8）；CLI 形态下引文点击=PDF 文件内部链接注释跳转（阅读器本地执行零网络延迟）——落地为**结构化断言**（link 注释存在 + 目标锚点可解析——AC-4），非计时断言 | epics L2289-2291 + prd L419/L2397 口径谱系 + 6-5a OD-8 四连先例 + 「图像不失真」同款口径重读（零位图面前提 OD-9） |
| **OD-9** | **图类产物继续表格承载**：6-5a OD-9「位图/SVG/mermaid defer 6-5b」的 6-5b 裁定 = **PDF 面继续表格/列表承载零位图**（六 Schema 字段仍是要点字段族——PDF 渲染以文本+表格兑现；「图像不失真」（epics L2278）口径重读 = 零位图前提下的渲染质量：中文清晰/表格完整/页面可渲染【pypdfium2 冒烟】——AC-8 承载）。位图渲染（品牌 logo/图表）归 6-11 白标模板立项（reportlab Image 能力届时启用） | 6-5a OD-9 断链预防 + epics 三要素字面无图像项 + YAGNI |
| **OD-10** | **异常开新码 492/493 不扩 491 值域**：`PdfRenderingError` 492（渲染失败——reportlab 异常领域包装）/`ReportEvidenceStorageError` 493（L4 归档失败）。**不复用/不扩 491**：其 `_VALID_LAYERS=("l0","l2")` 二元值域是 6-5a 冻结面且有负向测试钉死（"l4" 现为非法值抛 242——扩值域即破坏该用例）；最小契约变更原则取新码（6-5a OD-6 开段哲学同款）。引文解析失败**零新码**（宽容降级非异常——OD-6）；490 全缺 PDF 链同判复用 | sisys-uni-exception-design.md L760（492-499 预留成文）+ 491 值域冻结实证 + 最小契约变更 |
| **OD-11** | **CLI `--format` 参数形态**（非新子命令）：`report-generate --plan-id <id> --format {markdown,pdf}`（default=markdown 向后兼容——既有用户脚本零破坏）；interface-design.md L526 `sisys plan export --format <pdf\|markdown\|json>` format 参数形态钦定先例；单入口演进友好（6-11 白标模板参数同入口扩展）。CLI 内按 format 分发 resolve 两用例（report_generation_use_case / pdf_report_generation_use_case） | interface-design.md L526/L1466 format 参数先例 + 向后兼容 + argparse 扁平多参先例（checkpoint-create :352-401） |
| **OD-12** | **pyproject 依赖组迁移**：reportlab 从 `[tool.poetry.group.test.dependencies]`（pyproject:126）移入主依赖组 `[tool.poetry.dependencies]`——src 面首次消费该库（现状 src/ 零 import，仅测试 fixture 用）；types-reportlab 已在 dev 组（:148）mypy 支持在位；poetry.lock 同版本跨组迁移（4.5.1 锁定不变——Task 0.2 实证 install 可用）。**architecture.md §12 技术栈回填义务**（L1670「选型参考及时更新」）：Task 7 落档 reportlab 条目 | pyproject 实证 + architecture.md 回填义务条款 + 6-5a「依赖已预留未用」先例闭环 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/
│   ├── value_objects/citation_entry.py         ★ 新建（CitationEntry VO——Task 1）
│   └── exceptions/
│       ├── report_exceptions.py                ▲ 扩展（492/493 两类追加——Task 1）
│       ├── _code_ranges.py                     ▲ _CLASS_TO_SUBDOMAIN 注册两类（Task 1）
│       └── __init__.py                         ▲ 导出 + __all__（Task 1）
├── application/
│   ├── ports/pdf_report.py                     ★ 新建（PdfRendererPort + PdfReportGenerationServicePort + 常量——Task 3）
│   ├── services/
│   │   ├── report_generation_service.py        ▲ 唯一改动：_aggregate_document → aggregate_report_document 公开化（Task 3 前置——行为零变）
│   │   └── pdf_report_generation_service.py    ★ 新建（引文三段链 + 六段编排——Task 3）
│   └── use_cases/generate_pdf_report.py        ★ 新建（Task 4）
├── infrastructure/
│   └── reporting/
│       ├── __init__.py                         ★ 新建（子包）
│       └── reportlab_pdf_renderer.py           ★ 新建（reportlab 唯一宿主——Task 2）
├── entrypoints/agent_cli.py                    ▲ report-generate --format 扩展（Task 4）
├── interfaces/api/exception_handlers.py        ▲ EXCEPTION_HTTP_MAP 两行（Task 1）
└── composition_root.py                         ▲ 三注册块 === Story 6-5b ===（Task 4——纯新增零既有改动）

pyproject.toml                                  ▲ reportlab test 组 → 主依赖组（Task 0.2——OD-12）

tests/
├── unit/
│   ├── domain/test_citation_entry.py                     ★ 新建（Task 1）
│   ├── domain/exceptions/test_report_exceptions.py       ▲ 扩展（Task 1）
│   ├── infrastructure/reporting/test_reportlab_pdf_renderer.py ★ 新建（Task 2）
│   ├── application/test_pdf_report_generation_service.py ★ 新建（Task 3）
│   ├── application/use_cases/test_generate_pdf_report_use_case.py ★ 新建（Task 4）
│   ├── interfaces/cli/test_agent_cli.py                  ▲ --format pdf 用例扩展（Task 4）
│   ├── interfaces/api/test_exception_handlers.py         ▲ EXCEPTION_HTTP_MAP 键集合快照同步 492/493（Task 1）
│   └── architecture/test_pdf_report.py                   ★ 新建（Task 7，epics 钦定名）
├── integration/test_integration_pdf_report.py            ★ 新建（Task 6，OD-7）
├── contracts/
│   ├── test_port_contract_pdf_report.py                  ★ 新建（Task 3/5）
│   └── test_event_channel_mapping_pdf_report.py          ★ 新建（Task 5）
└── acceptance/
    ├── test_acceptance_pdf_report.feature/.py            ★ 新建（Task 0/7，13 场景）
    └── （6-x 既有验收文件零修改——Task 5 回归验证）

docs/architecture/sisys-uni-exception-design.md           ▲ §3.3.2 两张表 492/493 回填（Task 1）
docs/architecture/architecture.md                          ▲ §12 技术栈 reportlab 条目回填（Task 7——OD-12）
_bmad-output/implementation-artifacts/deferred-work.md     ▲ 处置注记 + bbox 留项新登记（Task 0.7）
_bmad-output/implementation-artifacts/sprint-status.yaml   ▲ 状态流转（Task 7.5）
```

（▲ 修改 / ★ 新建 / 禁整文件覆盖——就地扩展纪律；`src/domain/events/workflow_events.py`、`configs/event_channels.yaml`、`channel_router.py`、`src/domain/entities/strategic_report.py`、alembic versions/ **零改动**——事件/实体/表结构全复用）

### 关键代码锚点（实现直读——四 Agent 并行调研+主会话亲验双重核验；行号基准 HEAD@d09e31bb，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| 聚合/渲染分离点 | `src/application/services/report_generation_service.py:176-177` | `aggregation = _aggregate_document(...)` → `render_markdown_report(aggregation.document)` 两步分离——OD-3 同源双渲染的直接依据 |
| `_aggregate_document` 签名 | `report_generation_service.py:428-433` | 模块级私有函数（plan_id/records/snapshot/started → _Aggregation）；`_Aggregation` :279-294（class :279/`__slots__=("document","degraded_count","metadata")`）；私有辅助族 `_classify_payload` :297/`_resolve_degrade_reason` :327/`_appendix_a_rows` :340/`_step_field_blocks` :611——公开化仅更名入口零内部改动 |
| 五段编排形态 | `report_generation_service.py:154-193` | generate_markdown_report 编排（计时 :168/490 判定 :170-172/快照容错 :174/聚合渲染 :176-177/L0+实体+L2 :179-190/事件 :192）——PDF 六段编排的形态模板（L0 段替换为引文+渲染+L4） |
| 事件发布宽容形态 | `report_generation_service.py:243-276` | `_publish_event`：三键显式构造 :256-260（`report_type=report.report_type.value`）/`is_success` 先判 :263/except 兜底 :270——逐字复用模板 |
| ReportType.PDF 预留 | `src/domain/entities/strategic_report.py:28-29` | `PDF = "pdf"` 枚举成员在位（docstring :25 钦定「6-5b 预留值」）；实体六查校验全兼容 |
| L2 写侧 report_type | `src/infrastructure/storage/postgresql/repository/report_repository.py:94` | `report_type=report.report_type.value` 自动落 "pdf" 零改动；读侧 `_to_entity` :48-70（脏行回退 try/except :57-66；pdf 在枚举内无回退风险）；`get_latest_by_plan` :141-180（created_at.desc + report_id.desc tie-breaker——CR2-F3 修复形态） |
| assumptions 写侧（引文数据源） | `src/application/services/chain_of_thought_archive_service.py:200-203` | `assumptions = {"tools_used": ..., "evidence_refs": list(material.evidence_refs)}`——evidence_refs 持久化位置（**不在 payload 三态**）；`StepChainMaterial.evidence_refs` 端口定义 `chain_of_thought_archive.py:88`（tuple[str,...]——元素=Qdrant 点 ID 即 chunk_id） |
| EVIDENCE_PACKAGE 查询面 | `chain_of_thought_archive_service.py:209/:239` | 6-4 归档 archive_type=EVIDENCE_PACKAGE（写 :209 / query_chain_trace 内部查询 :239 同型）——引文收集的 ArchiveQuery 参数实证 |
| `query_archive` 签名 | `src/application/services/strategic_archive_service.py:315-323` | `query_archive(query: ArchiveQuery) -> list[StrategicArchive]`；`ArchiveQuery`（domain/ports/archive_repository.py:39-75：plan_id/archive_type/limit 默认 20——**引文收集 limit 显式传 64**：八步现值 8 行虽低于默认 20，显式传参为未来同型行扩展余量、对齐 6-4 `_TRACE_QUERY_LIMIT=50` 显式传参先例 chain_of_thought_archive_service.py:66）；`StrategicArchive.assumptions: dict`（strategic_archive.py:61） |
| get_point | `src/domain/ports/l3_vector.py:85-98` | `get_point(collection, point_id)` 单点查询——引文解析①；collection 组合根 `BLM_SEARCH_COLLECTION` 默认 "documents"（composition_root.py:1592 env 同源——测试注入临时 collection 通道） |
| documents 行结构 | `src/domain/entities/document.py:49-87` + `src/domain/ports/document_repository.py:43-127` | `filename`（引文显示文档名唯一来源）/`metadata["chunks"]`（SemanticChunk.to_dict :182 chunk_id str + page_start int——页码解析链闭合）；`DocumentQuery`（class :18 + 字段 :33-34：tenant_id: str **必填** + document_id: UUID——多字段组合 Query Object 形态；PG find 硬过滤 tenant_id :99-103、Qdrant payload 的 document_id 是 str 需 uuid.UUID() 转换） |
| MVP_TENANT_ID | `src/application/services/agent_workflow_context.py:39` | 引文链租户默认值（str() 化传入 DocumentQuery；blm_planning_service.py:733-737 5-3 MVP 单租户先例同款——多租户扩展归后续 Story） |
| Qdrant payload 现状（bbox 缺口） | `src/application/event_handlers/chunk_indexing_handler.py:156-168` | 生产 ingestion payload 仅 6 键（chunk_id/document_id/parent_chunk_id/index_level/content/chunk_header）——**无 bbox/page_start**（3-8 L118 自注记前置未实现）——OD-6 bbox defer 的实证依据 |
| L4 archive bytes 通道 | `src/domain/ports/l4_object.py:107-124` + `src/infrastructure/storage/minio/minio_repository.py:207-249` | `archive(bucket_type: str, object_key: str, content: bytes \| None, retention_days: int = 2555)`——无 content_type（store :32-39 才有）勿传；BytesIO put_object + WORMManager.archive_object（worm_lifecycle.py :35 类定义/:109 方法【enable_worm_lock 别名】，经 minio_repository 构造注入——两步非原子：put → 单独 set_object_retention）；组合根注册名 `"l4_object"` :375-419 SCOPED；测试清理 bypass 先例 test_acceptance_json_chain_of_thought.py:514/:1025（:58 为 docstring 注记）——绕过端口直用 minio client（L4ObjectPort 无 remove_objects 方法） |
| 桶名双源 | `strategic_archive_service.py:40`（代码单源）+ `docs/architecture/architecture.md:2543-2550`（蓝图逻辑桶表） | 代码实况 `L4_BUCKET_TYPE = "archive-evidence"`（6-3/6-4 证据归档同桶——chain_of_thought_archive_service.py:63 同值；EVIDENCE_BUCKET_TYPE 对齐此单源，OD-4）；蓝图名 `evidence-packages/`（L2548）为逻辑分类未落地（src/configs 零命中）——实况注记 Task 7 回填；物理桶名 `{prefix}-{bucket_type}-{tenant_id}`（minio_repository.py:253-261）；GOVERNANCE 模式注记 :1024 |
| CLI 先例 | `src/entrypoints/agent_cli.py:337-350`（report-generate 注册）+ `:838-851`（异步执行器）+ `:940-980`（五步定式）+ `:916-937`（_print_report_summary——memory_id 反解 `.md` 钉死 :926 仅 markdown 分支适用）；checkpoint-create :352-401（argparse 扁平多参先例） | `--format` 参数扩展位；双层异常定式；resolve 分发点 |
| 组合根注册模板 | `src/composition_root.py:3346-3400`（6-5a 三注册块）+ `:2216`（strategic_archive_service）+ `:2300`（注入先例 `archive_service=resolver.resolve(...)`） | `=== Story 6-5b ===` 包裹式分节（6-3/6-5a 先例）；九依赖 resolve lambda 形态 |
| 单测 mock 工厂 | `tests/unit/application/test_report_generation_service.py:273-330`（_make_service）+ `:163-199`（_make_trace_view）+ payload 工厂族 :38-160 | 九依赖 AsyncMock(spec=Port) 扩展模板——`StepChainMaterial.evidence_refs` 参数喂引文测试数据 |
| 验收装配先例 | `tests/acceptance/test_acceptance_markdown_report.py:135-148`（_clear_resolver_caches）+ `:190-466`（teardown 七步链）+ `:555-635`（探测+L0 注入）+ `:709-798`（Fake LLM 八键族）+ `:1106-1136`（归档轻装配） | 整体移植 + L4/引文预置清理扩展；`_make_material` :1139 起喂 evidence_refs |
| 集成先例 | `tests/integration/test_integration_markdown_report.py:71-87`（_fresh_resolver_per_test）+ `:188-206`（_make_report_service tmp_path）+ `:295-325`（_archive_steps 归档构造）+ `:328+`（查询/清理辅助）+ `:727-779`（性能采样 P95 数学口径） | 函数族装配形态；净增 0 断言；gather 并发先例 |
| PDF fixture 先例 | `tests/unit/infrastructure/document_parsing/test_pdf_parser.py:270-281`（reportlab canvas 生成）+ `:266-267`（中文 CMap 限制注释——AC-8 断言分层依据） | reportlab 测试侧用法先例；pypdf **报告域**读侧断言为新面（文档解析域先例在位：pdf_parser.py:15 / rapidocr_adapter.py:137 / pypdfium2 pdf_page_renderer.py:36——pypdf/pypdfium2 均在主依赖组 pyproject:74/:82，src 面 import 零迁移；报告域断言分层 Task 0.2 实证后钉死） |
| pytest 配置 | `pyproject.toml:245-299` | asyncio_mode=auto/-n auto --dist loadgroup/--strict-markers；marker 注册清单（database 非 postgresql）；reportlab :126 test 组 + types-reportlab :148 dev 组 |
| 异常段位现状 | `docs/architecture/sisys-uni-exception-design.md:758-760`（分配表）+ `:843`（范围表） | 490/491 已占；492-499 预留成文——492/493 开码零冲突 |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-5b 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L129 | data_pipeline 轨（6-5a OD-2 注记在位） | **维持注记**：6-5b 同形态应用服务直交（OD-2 零新偏离）；data_pipeline 轨再锚定条件不变（批量报告管线/6-8/6-11/Epic 7） |
| 2 | L170 | 事件消费基建四件 | **顺延注记**：6-5b 是 ReportGenerated 第二次生产（report_type="pdf"）非消费方——锚位继续顺延 6-6/Epic 8 |
| 3 | L192 | ChainOfThoughtSchema 演进触发 | **零触发注记**：6-5b 消费 assumptions.evidence_refs 与 payload JSON 直读（与 6-5a 同理不经 Schema）——留项维持 |
| 4 | L369（6.5a-DF1） | REST 导出面 `/plans/{id}/export` | **维持注记**：CLI-only 延续（`--format pdf` 扩展不改变入口形态）；触发条件不变（6-8/Epic 7 立项） |
| 5 | L370（6.5a-DF2） | 同 plan 同秒并发 L0 撕裂文件 | **范围收窄注记**：PDF 链 L4 键锚 report_id + put 服务端原子——撕裂面在 PDF 链不存在；留项范围收窄至 Markdown 链（6-8 REST 读侧上线前处置不变） |
| 6 | 新登记 | **bbox ingestion 写入缺口**（3-8 遗留） | **新留项登记**：chunk_indexing_handler.py Qdrant payload 未写 bbox/page_start（3-8 story L118 自注记前置未实现）——引文索引页码级溯源经 chunks 元数据兑现（OD-6），bbox 高亮完整形态依赖该缺口闭合 + Web 阅读器（6-8）；触发 = 6-7 溯源树立项或 6-8 Web 高亮立项 |
| 7 | 新登记 | 引文解析批量性能瓶颈（条件性） | **条件性登记**：M>50 引文 × 2 查询若实测超 P95 窗口——批量 get/缓存优化登记（处置归 **Task 6.4** 实测后定夺：达标则不登记；Task 0.7 仅条件性占位） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-5a Markdown 报告生成](./6-5a-markdown-report-basic.md)（文档五轮+代码五轮双收敛 done 2026-11-04）

**关键学习/Key Learnings:**
- **既有资产复用优先（6-3 头号教训 + 6-5a 再证）**：本 Story 复用面实证——聚合函数（公开化零行为变）/ReportType.PDF 预留/L2 仓储 report_type.value 自动落值/ReportGenerated report_type 自由 str/CLI 五步定式/组合根分节/验收集成装配链整体移植。**唯一 reportlab 宿主 = infrastructure 渲染器**（6-5a 唯一新建面哲学延续——报告领域知识在 VO/聚合已交付，6-5b 新建面 = 渲染技术 + 引文链 + L4 通道）
- **属性形态断裂族**（6-1~6-5a 五连犯）：evidence_refs 是 tuple[str,...] 裸 chunk_id（非 dict 结构——引文字段须解析链展开）；`StepChainMaterial.evidence_refs`（端口 DTO）vs `InsightStepResult.evidence_refs`（领域信封）同名异层；`assumptions` JSONB round-trip 后 list[str] 形态；`SemanticChunk.chunk_id` 是 uuid.UUID（to_dict 后 str——metadata["chunks"] 读侧是 str 匹配 get_point 入参 str）；`DocumentQuery.document_id` 是 UUID（Qdrant payload 的 document_id 是 str——构造前 uuid.UUID() 转换）+ `tenant_id` 必填 str（PG find 硬过滤——引文链注入 MVP_TENANT_ID，预置与查询同租户闭环）；CLI stub 设真实 `ReportType.PDF` 枚举成员非裸 str（6-5a CR1-F9 教训）
- **断言判别力**（6-5a CR1-F2/F3 恒真断言族教训）：引文条目值级断言（display_name/文档名/页码独立构造期望）；L4 调用参数值级断言（bucket/object_key 模板渲染比对——非仅 called）；outline/link 结构断言禁「存在即绿」（逐条目层级与目标锚点可解析）；**pypdf 读侧断言分层**（R3 实证升级：STSong-Light extract_text 完美工作——全文值级比对为主 + ASCII/outline 冗余 + pypdfium2 视觉面兜底）
- **no-mock 红线互斥裁定**（三连先例+6-5a）：渲染失败 492/L4 失败 493 注入归单测层 AsyncMock；引文解析降级验收层用**真实缺失构造**（喂不存在 chunk_id——非 mock）
- **键清理闭环**（6-3 泄漏教训）：本 Story 清理面 = L4 WORM 对象（bypass）+ 引文预置两面（Qdrant 点/PG documents 行）+ 报告三元（L2/outbox/归档三面）+ Redis 键族——净增 0 断言
- **resolver 跨 loop 缓存防线**（6-5a 实施攻坚沉淀）：`_clear_resolver_caches`/`_fresh_resolver_per_test` 双面清缓存**第一天就带**（不重蹈 6-5a 集成首跑 4 failed 排查）
- **L0 tmp_path 覆写修正先例**（6-5a 实施修正）：注册表 register_port 同名异 spec 抛 ConflictError——服务实例层注入是真身；本 Story PDF 不落 L0 该面不适用，但引文预置的 Qdrant collection 注入同理（服务构造参数注入非注册表覆写）
- **红线纪律**（6-5a 过程 4 次误写即时清除）：全程零抑制注释/零裸异常/提交信息禁 AI 署名/三条 grep 自查

**应用到本故事/Applied to This Story:**
- [ ] 聚合复用公开化 + ReportType/L2/事件/CLI 模板全复用（Task 3 前置 + Task 4）
- [ ] 引文条目/调用参数/outline 三类断言值级独立构造（Task 2/3/6）
- [ ] 492/493 失败注入落单测层；引文降级验收层真实缺失构造（Task 3/6）
- [ ] 清理链八面 + 净增 0 断言（Task 6.1/6.5）
- [ ] resolver 双面清缓存第一天就带（Task 6.1）
- [ ] 全程禁抑制注释+禁 AI 署名+三红线 grep（Task 5.4/7.4）

### 其他约束速查

- **风险集中登记**：①最大回归风险 = 聚合公开化更名（波及面 grep 实证仅同文件——Task 3 循环 A 红绿锁死 + 6-5a 37 用例零破坏实证）；②L4 WORM 测试面风险（测试 bucket WORM 探测先行——Task 0.7 复用 6-4 探测自愈形态；bypass 清理链实证）；③渲染质量风险 = CJK 字体（Task 0.2 最小脚本实证前置——STSong-Light 注册失败则降级方案裁定【系统字体路径 or 内嵌 TTF——届时 OD 补档】）；④引文链风险 = assumptions 键缺席形态（`.get` 容错 + 三态降级单测锁死）+ 租户/类型形态（DocumentQuery.tenant_id 必填硬过滤 + payload str→UUID 转换——预置与查询同租户闭环，AC-3/OD-6）；⑤CLI 兼容风险 = `--format` 默认值（既有 markdown 用例零修改是验收标准——Task 4.5 全量回归）；⑥并发风险 = 引文局部累积（AC-7 无状态约束——与 6-5a 附录 B 登记清单同纪律）；⑦依赖组迁移风险 = poetry.lock 变更（Task 0.2 实证 install + import）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type:ignore/pylint:disable；提交信息禁 AI 署名
- **覆盖率**：整体≥80% / application≥85%（epics L2294 钦定）/ 集成≥75%（epics L2295 钦定）/ domain≥90% / infrastructure≥75%
- **覆盖率豁免不适用**：本 Story 非骨架 Story（渲染器/引文链/编排全实质实现）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code） |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-04 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 6 节 L1999-2364；Story 6.5b L2266-2307） |
| **架构文档** | `docs/architecture/architecture.md` + `sisys-uni-exception-design.md` + `interface-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-5a-markdown-report-basic.md`（done 2026-11-04，五轮文档+五轮代码双收敛） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 实施计划与规范落档 Implementation Plan（Task 0 权威输入）

**Task 0 SDD 规范落档（2026-11-04，四 Agent 并行调研 + 主会话亲验 + R3 复验）：**

- **端口契约定稿**（`src/application/ports/pdf_report.py`——Task 3 落地为代码）：`PdfRendererPort.render(document: MarkdownReportDocument) -> bytes`（同步——reportlab 纯 CPU 渲染无 I/O）+ `PdfReportGenerationServicePort.generate_pdf_report(plan_id: uuid.UUID) -> StrategicReport`；模块常量 `EVIDENCE_BUCKET_TYPE = "archive-evidence"`（代码单源对齐 strategic_archive_service.py:40）+ `PDF_OBJECT_KEY_TEMPLATE = "reports/{plan_id}/{report_id}.pdf"`（file_path 存此值——OD-4）；引文三段链契约（收集 limit=64 去重保序 / 解析 get_point→payload.document_id str→UUID→find(tenant_id 注入) / 组装附录 C table 四列）；CitationEntry 值域冻结（status 三元组 resolved/point_missing/document_missing——page 缺失是 resolved 子形态 page=0）
- **引文锚点断言形态裁定（Task 0.2 复验新事实，R3 结论增补）**：孤立 `bookmarkPage("citation-N")` 在最终 PDF 中**零留存**（named_destinations 恒空——reportlab 不写 name tree）；锚点承载形态 = **附录 C 条目行 link 注释自指**（条目行 linkRect 引用同条目 bookmarkPage 注册的目标——save 期解析为 /Dest 直接数组，6-8 Web 阅读器可经 /Annots 寻址条目行位置）；断言面 = 附录 C 页 link 数 == 引文条目数（自指本页）+ 正文页（非目录非附录 C）零 link 负向断言；outline 断言 = `get_destination_page_number` 逐条目目标页有效
- **R3 预实证复验结论（8/8 成立，1 项脚本假象澄清）**：STSong-Light 注册/中文渲染/extract_text 中文完美工作（逐字符样本全命中；首验 p1 失败系脚本跨 showPage 未重设字体回落 Helvetica 画出 .notdef 方块——**渲染器实现必须全程 STSong-Light 样式含表格**）/named_destinations 恒空与 /Dest=[IndirectObject(页),'/Fit'] 直接数组/悬空链接 save 期 `ValueError: format not resolved`（492 包装路径）/pypdfium2 渲染非空白/metadata.title 中文读回/outline 嵌套 list 形态
- **链路接线断言清单（Task 0.7）**：①组合根三注册块 resolve 可达（pdf_renderer/pdf_report_generation_service/pdf_report_generation_use_case——Task 4 落地）②ReportGenerated 真实发布（outbox 落行 + 两级 JSONB 路径 `payload->'payload'->>'report_id'` + report_type=="pdf" 值级）③L4 WORM 真实归档（archive-evidence 桶 WORM 探测自愈已入验收 `_probe_minio_worm`——6-4 :995-1035 形态移植；teardown bypass 清理 `_cleanup_pdf_objects` 在位）④pyproject reportlab 依赖组迁移实证完成（test 组→主依赖组，poetry lock 仅组归属变更零版本漂移，install + import 4.5.1 OK）
- **锚点行号校正（Task 0.8——四 Agent 复核 + 主会话 grep 复验）**：`_VALID_LAYERS` 实位于 report_exceptions.py:67（故事 AC-6 表述为「StrategicReport 实体与 491 值域」——值域本体即在 491 类属性，裁定不受影响）；组合根 :2300 `archive_service=resolve(...)` 注入先例属 checkpoint_service 注册块（ChainOfThoughtArchiveService 注入 strategic_archive_service 先例在 :2343-2346——注入形态先例成立）；6-5a 端口契约测试实际文件名 `test_port_contract_report_generation.py`（6-5b 用钦定名 `test_port_contract_pdf_report.py` 零冲突）；pypdf 主组版本约束 `^6.12.1`（实装 6.14.2 满足）。其余锚点（:176-177/:428/:200-203/:209/:239/:40/:315-323/:85-98/:33-34/:99-103/:39/:158-170/:156-168/:1592/:2216/:3346-3400/:337-350/:838-851/:940-980/:916-937）全部命中零漂移
- **R4N-1 注记（思维链全文附录维持 YAGNI 归 6-7）**：6-5b 立项裁定——引文索引（附录 C）已交付溯源消费面，思维链全文附录维持 YAGNI（`chain.to_display()` 资产在位可消费），随 6-7 溯源树立项定夺
- **R4N-2 注记（6-5a CR2-F12/CR3-F6 边缘形态 PDF 链评估）**：PDF 链结构同源直渲染（VO→reportlab）不经 Markdown 文本与转义面，`\|` 双重转义/≥4 前导空格缩进两边缘形态不影响 PDF 面——留项维持 Markdown 面归 6-11/后续统一
- **既有契约基线（Task 0.9）**：`pytest tests/contracts/ -q` → **1498 passed**（46.15s）——本 Story 新增契约测试后以此为回归对照基线

### 实施攻坚调试日志 Debug Log（dev-story 2026-11-04）

**六项实施攻坚发现（全部根因修复非绕过）：**
1. **引文锚点承载形态裁定**（Task 0.2 复验）：孤立 `bookmarkPage("citation-N")` 在最终 PDF 中零留存（named_destinations 恒空）——锚点实现改为**附录 C 条目行序号列 link 自指**（`<a name="citation-{n}"/>` + `<link href="#citation-{n}">`，6-8 可经 /Annots 寻址）；断言面同步为「非目录页 link == 引文数且全自指附录 C 页」。
2. **Qdrant 点 id MD5 归一实证**（验收 S4 攻坚）：生产通道 `_normalize_point_id` 把字符串 id 映射为 MD5 整数（upsert/get_point 同归一闭环）——预置 fixture 以裸 client 原始 uuid 直写被 get_point 漏查；修复=预置走 `l3_vector.upsert_points` 生产通道（归一一致），清理改 payload.chunk_id FilterSelector 面（点 id 非稳定清理锚）。
3. **document_repository 严格 ContextVar 会话**（集成攻坚）：find 在无活动会话抛 `InvalidStateError`（与 archive/report 仓储的 factory fallback 不同族）；CLI/entrypoints 禁 import infrastructure（4 架构测试钉死）——正位修复=**组合根 6-5b 块内 `_SessionScopedDocumentRepository` 包装**（装配层是 infrastructure import 唯一合法宿主；cast 契约面收窄注记——6-5a cast 先例）；验收/集成装配同款镜像。
4. **引文收集段排序缺失**（验收 S4 攻坚）：query_archive 返回序不稳定致首现次序漂移（stage 断言 `opportunity_gap ≠ performance_gap`）——服务收集段补 `archived_at` 升序排序（6-4 query_chain_trace 同款 + `_EPOCH_FLOOR` 回落）。
5. **两守护测试正当演进**：`test_json_chain_of_thought` EVIDENCE_PACKAGE 构造点唯一守护——许可清单增 pdf_report_generation_service.py（Story 钦定**查询消费面** AC-1 ③，docstring 注记构造/查询分立）；`test_markdown_report` CLI resolve 字面守护——分发改显式两分支保字面。
6. **Qdrant FD 上限 1024 环境铁证**（Task 7.3 攻坚）：重载全量跑（--cov 模式）触发 RocksDB `Too many open files`（175 条/8min 日志实证）→ 跨文件随机失败（qdrant_vector_layer/hybrid_search 等，单文件复跑全绿）；**清卷重建后四目录两轮 14756 passed 零失败稳定**（环境损伤非代码回归——6-5a「Qdrant FD 耗尽表象」同象闭环）；环境治理项登记 **6.5b-DF3**（compose ulimits 根治）。
7. **全仓 mypy（含 tests）23 错误清零**（用户复验发现——src 面门禁 752 零错误之外的全量口径）：①`stubs/pypdfium2` 存根与运行时 API 不符（`__init__` 标 `path: str` 实为 `input: bytes | str` 双形态 + 漏标 `__iter__`）——存根修正（根因修复非绕过）；②`_saved_metadata` 返回 Optional 致 17 处索引未收窄——None/dict 检查内聚进辅助函数（返回 `dict[str, Any]`）；③集成/验收 `_SessionScopedFind` 注入两处 cast 契约面收窄（组合根同款注记）；④pypdfium2 冒烟改 `getdata()` 全量灰度（PIL `PixelAccess.load()` 存根 Optional 不可下标——6-5a 验收先例形态）+ 集成 `pdf_page` 变量名与页索引 `page` 分立；终态**全仓 mypy 1910 文件零错误 + ruff 全绿 + 受影响 61 测试全绿行为零变**。

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 6.5b 节 L2266-2307 + Epic 6 头部 L1999-2036 + 依赖链 L2014-2036）
- [x] 架构约束从 `docs/architecture/architecture.md` 提取（交互流程 38 L417 证据包/§10.1 L884/桶设计 L2543-2550/importlinter 四契约）+ prd FR-UI-11/NFR-PERF-03 + UX 规范溯源交互口径
- [x] 前一个故事学习经验整合（6-5a 五轮代码审查 38 修复 6 留档全量吸收 + defer 钩子逐条承接）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0~7 / 39 Subtask——0.1-0.9（9）/1.1-1.3（3）/2.1-2.3（3）/3.1-3.4（4）/4.1-4.5（5）/5.1-5.4（4）/6.1-6.6（6）/7.1-7.5（5））
- [x] 项目结构对齐统一规范（同源双渲染 / L4 WORM 归档 / 引文首消费 / 事件零新增 / 异常开码 492-493）
- [x] 四 Agent 并行调研（报告链路现状/引文数据面/测试样板/架构文档治理）+ 主会话亲验（聚合解耦点 :176-177/L4 端口签名/archive_type=EVIDENCE_PACKAGE/strategic_archive_service 注册/get_point/_aggregate_document 测试零引用/SemanticChunk 字段八项关键事实）
- [x] dev-story 实施完成（2026-11-04——Task 0~7 / 39 Subtask 全勾）：**13 验收场景全绿 + 集成五场景×两轮稳定 + 四目录全量 14756 passed × 2 轮零失败 + 覆盖率 93.10%（≥80 门禁）+ mypy 752 文件零错误 + ruff 全绿**；变异实证四处全落（T1 status 值域/T2 outline 层级/T3 report_type+引文去重保序）；R3 预实证复验 8/8 成立（extract_text 中文/锚点形态/悬空守护等）+ 一项脚本假象澄清（Helvetica 回落 .notdef）；pyproject reportlab 依赖组迁移（4.5.1 锁定零漂移）；红线三查本 Story 面零输出；实施攻坚六项见调试日志

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-5b-pdf-report-citation-index.md`

**待创建的文件/To Be Created (Dev Story 实施):**（全部已创建 ✅ 2026-11-04）
- `src/domain/value_objects/citation_entry.py` - 引文条目 VO（Task 1 ✅）
- `src/application/ports/pdf_report.py` - PDF 双端口 + 常量（Task 3 ✅）
- `src/application/services/pdf_report_generation_service.py` - 引文聚合+六段编排（Task 3 ✅）
- `src/application/use_cases/generate_pdf_report.py` - PDF 生成用例（Task 4 ✅）
- `src/infrastructure/reporting/__init__.py` + `reportlab_pdf_renderer.py` - PDF 渲染器（Task 2 ✅）
- `tests/unit/domain/test_citation_entry.py` - VO 单测 13 用例（Task 1 ✅）
- `tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py` - 渲染器单测 19 用例（Task 2 ✅）
- `tests/unit/application/test_pdf_report_generation_service.py` - 编排服务单测 23 用例（Task 3 ✅）
- `tests/unit/application/use_cases/test_generate_pdf_report_use_case.py` - 用例单测 3 用例（Task 4 ✅）
- `tests/unit/architecture/test_pdf_report.py` - 架构验证四验证器 10 用例（Task 7 ✅）
- `tests/integration/test_integration_pdf_report.py` - 集成五场景+性能/并发/净增 0 共 6 测试（Task 6 ✅）
- `tests/contracts/test_port_contract_pdf_report.py` - 端口契约 13 用例（Task 3/5 ✅）
- `tests/contracts/test_event_channel_mapping_pdf_report.py` - 事件守护 6 用例（Task 5 ✅）
- `tests/acceptance/test_acceptance_pdf_report.feature/.py` - Gherkin 13 场景 + BDD 步骤（Task 0/7 ✅ 全绿）

**待修改的文件/To Be Modified (Dev Story 实施):**（全部已修改 ✅ 2026-11-04）
- `src/domain/exceptions/report_exceptions.py` - 492/493 两类追加（Task 1 ✅）
- `src/domain/exceptions/_code_ranges.py` + `__init__.py` - 注册 + 导出（Task 1 ✅）
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 两行（Task 1 ✅）
- `src/application/services/report_generation_service.py` - 聚合函数公开化更名（Task 3 ✅ 唯一允许改动实证）
- `src/entrypoints/agent_cli.py` - --format 参数扩展（Task 4 ✅ 分发显式两分支保 resolve 字面）
- `src/composition_root.py` - 三注册块 === Story 6-5b === + _SessionScopedDocumentRepository 包装（Task 4 ✅ 增量零既有 lambda 改动 + typing import cast 扩展一行——CR1-F22 台账补记）
- `pyproject.toml` + `poetry.lock` - reportlab 依赖组迁移 test→主组（Task 0.2 ✅ 4.5.1 锁定零漂移）
- `tests/unit/domain/exceptions/test_report_exceptions.py` - 492/493 用例扩展（Task 1 ✅）
- `tests/unit/interfaces/api/test_exception_handlers.py` - EXCEPTION_HTTP_MAP 键集合快照同步 492/493（Task 1 ✅）
- `tests/unit/interfaces/cli/test_agent_cli.py` - --format pdf 用例 8 个（Task 4 ✅ 既有 102 用例零破坏）
- `tests/unit/architecture/test_json_chain_of_thought.py` - EVIDENCE_PACKAGE 守护许可清单扩展（查询消费面 6-5b 注记 ✅）
- `docs/architecture/sisys-uni-exception-design.md` - §3.3.2 两张表 492/493 回填（Task 1 ✅）
- `docs/architecture/architecture.md` - §12 reportlab 条目 + 桶表 evidence-packages 实况注记（Task 7 ✅）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 台账处置七条 + 6.5b-DF1/DF2/DF3 三留项（Task 0.7/6.4/7.4 ✅）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 状态流转 review（Task 7.5 ✅）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.5b |
| **Story Key** | 6-5b-pdf-report-citation-index |
| **File** | `_bmad-output/implementation-artifacts/stories/6-5b-pdf-report-citation-index.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 📦 战略规划与审批能力（用户可以生成战略规划并审批） |
| **优先级** | P0-5b |
| **覆盖 FR** | FR-UI-11（P0——PDF+引文索引半边；Markdown 半边 6-5a 已交付）；NFR-PERF-03（<30s 更严口径与 epics 60s 双口径注记见 AC-7）；FR-SR-08（L1788 引文三元组消费面——原始形态=文档ID/切片ID/字符范围，本 Story 交付=文档名/页码/切片标识为其消费面变体，字符范围归 bbox defer OD-6） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7 / 39 Subtask）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-8）
3. [x] Architecture constraints extracted 架构约束已提取（OD-1~OD-12 十二项裁定——同源双渲染/L4 WORM 归档/PDF 渲染器层位/引文三段链/异常开码 492-493/依赖组迁移为六大关键裁定）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-5a defer 钩子逐条承接 + 五轮审查教训八项）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则**：R<轮>-<序号>（Round 内递增）。

**Round 1（2026-11-04，代码事实核查 ×4 Agent + 一致性内审 + P0 方案设计共 6 Agent 并行）：**

**P0 修复（2 项）：**
- R1-1【P0】引文解析链 tenant_id 缺失——`DocumentQuery.tenant_id` 必填且 PG find 硬过滤（document_repository.py:99-103），原稿 `find(DocumentQuery(document_id))` 运行时 TypeError。修复：tenant_id 经服务构造参数注入、默认 `str(MVP_TENANT_ID)`（agent_workflow_context.py:39——数据链无租户可用【StrategicArchive/ArchiveQuery/Qdrant payload 均无 tenant_id】注入是唯一来源；5-3 单租户先例；测试注入测试租户、引文预置 PG 行同值闭环）。联动修订 AC-3/OD-6/端口契约节（租户注入小节）/Task 0.1/0.5/3 循环 B/Task 6.1/锚点表（MVP_TENANT_ID 新行 + documents 行结构）九处
- R1-2【P0】L4 桶名与代码现状冲突——原稿 `EVIDENCE_BUCKET_TYPE = "evidence-packages"`（architecture.md L2548 蓝图名）但代码现状 6-3/6-4 证据归档全线用 `"archive-evidence"`（strategic_archive_service.py:40），蓝图名 src/configs 零命中且归档链路不自动建桶（新桶全环境首建纯增量风险）。修复：桶名对齐代码单源 "archive-evidence"（evidence_refs 上游 EVIDENCE_PACKAGE 归档同桶——证据流一桶贯通；`reports/` 键前缀与归档键天然隔离；蓝图分歧为 3-10 起存量治理债，architecture.md 桶表实况注记 Task 7.4 回填）。联动修订 AC-1/OD-4/端口常量/锚点表（桶名双源行）/测试隔离表/Task 0.7/7.4/Dev Notes 八处

**P1 修复（7 项）：**
- R1-3【P1】StrategicReport 字段数三处口径矛盾（AC-1「六字段」列举 7 个 vs 数据模型节「八字段」）——实际 8 字段（含 created_at），统一为「八字段实体零改动」
- R1-4【P1】异常「490/491 同构」表述失准——491 构造器是 `(layer,...)` 形态，改「同构 490 形态」（context_extra 参数名原稿本正确，Agent 误报经原文复核排除）
- R1-5【P1】`channel_router.py` 全路径缺失——补 `src/infrastructure/messaging/channel_router.py`（AC-5）
- R1-6【P1】epics「L2274 Markdown→PDF 转换」行号错位——实际 L2276（L2274 是 Given 行恰为 OD-3 重读对象，改双行号并列）
- R1-7【P1】验证要求「`pytest tests/ -n 8`」裸命令与 AC-6「裸 tests/ 会挂起」自相矛盾——改四目录显式形态
- R1-8【P1】目录条目数「恒 5」与「附录 A 可选」同句矛盾——改「条目数非恒定，断言面=目录条目集合与实际渲染章节一致」（与 6-5a 口径同构）
- R1-9【P1】桶类型标识三形态不统一（`EVIDENCE_PACKAGES` 枚举样式未定义即引用）——统一为常量 `EVIDENCE_BUCKET_TYPE` 单一引用形态（AC-1 改 `bucket_type=EVIDENCE_BUCKET_TYPE（="archive-evidence"）`）

**P2 修复（8 项）：**
- R1-10【P2】「6-5a 30 用例」实为 37（两处：Task 3 循环 A + 风险登记①）
- R1-11【P2】bypass 先例行号 :58/:513 → :514/:1025（:58 为 docstring）+ 补「绕过端口直用 minio client（L4ObjectPort 无 remove_objects）」+ 桶解析复用 `_resolve_archive_bucket_name` 形态
- R1-12【P2】「pypdf 仓内 0 先例」失准——文档解析域先例在位（pdf_parser.py:15 等），改「报告域 0 先例」；顺带 pypdf/pypdfium2 已在主依赖组（pyproject:74/:82）零迁移利好落 Dev Notes 技术栈
- R1-13【P2】AC-1 六段编排含「②latest 快照辅源」但 Task 3 循环 C 实现序列漏快照步——红/绿两行补齐（与 6-5a :174 同形态）
- R1-14【P2】`limit=64` 与「防 8 行截断」理由不自洽（8<20 默认不截断）——改「未来同型行扩展余量、对齐 6-4 `_TRACE_QUERY_LIMIT=50` 显式传参先例」
- R1-15【P2】「PortSpec ×2」与「三注册块」矛盾——改 PortSpec ×3（双端口 + use_case 亦登记）
- R1-16【P2】`test_exception_handlers.py` 改动要求未入文件清单——待修改清单补列（Task 1）
- R1-17【P2】Task 0.7 台账处置漏 #3（L192 ChainOfThoughtSchema 零触发注记）——锚定义务清单七条对齐补全
- （另）NFR-PERF-03 <30s 与 epics 60s 双口径关系注记落 AC-7/Dev Notes/覆盖 FR 三处；OD-11 checkpoint-create 先例行号 :337-392→:352-401 且定性为「扁平多参先例」；Citation VO 字段列举补 page_number；FR-SR-08 变体关系注记落覆盖 FR/Dev Notes

**P3 修复（5 项）：** R1-18 `_Aggregation` 行号 :284-294→:279-294；R1-19 `_to_entity` :61-69→:48-70（回退 :57-66）；R1-20 `citation-{n}`→`citation-{index}` 统一 + 降级条目占位符 `[n]` 统一；R1-21 worm_manager→WormLifecycle（worm_lifecycle.py:109）+ archive 签名精确化（content `bytes | None`）；R1-22 13 场景分解补 AC-8 归属注记 + 人工评审承载注记 + generation_ms/P95 双窗口辨析 + 集成先例锚点标签修正（_archive_steps :295-325）

**统计：P0×2 + P1×7 + P2×8（+4 附注）+ P3×5 = 26 项修复落档；6 Agent 并行审查（代码事实×4/一致性内审/P0 方案设计）+ 主会话逐项复核（Agent 误报 1 项经原文复核排除）**

**Round 2（2026-11-04，回归核查 + 交叉引用 + 深度推演共 3 Agent 并行）：**

**回归核查（Round 1 修复联动完整性——24/26 落位完整，2 项联动残留）：**
- R2-1【P1】AC-1 验证标准残留 `retrieve(EVIDENCE_PACKAGES, ...)` 未定义标识（R1-9 桶标识统一漏此一处）→ 改 `retrieve(EVIDENCE_BUCKET_TYPE, ...)`
- R2-2【P2】OD-3 表内残留旧行号「epics L2274」（R1-6 只修了范围边界表）→ L2276 双行号并列

**交叉引用与深层一致性：**
- R2-3【P2】citations 结构与 OD-6「stage 保留」矛盾——AC-3 citations 六键无 stage → 补 stage 键（七键，stage=首现步骤名——6-7/6-8 溯源展示查询面）
- R2-4【P2】锚定义务清单 #7 处置在 Task 6.4 非 Task 0.7 + REST 复核与 #4 重叠 → #7 注明归 Task 6.4 / REST 并入 #4
- R2-5【P3】AC-4 outline 断言缺「附录 A 可选」限定 + outline 含 H1/目录自 H2 起的差异注记 → 补
- R2-6【P3】增量冻结节括号未闭合（R1-8 修订引入）→ 补
- R2-7【P3】项目结构树缺 test_exception_handlers.py 行 → 补
- R2-8【P3】OD-4 file_memory_adapter.py 裸文件名 → 补全路径 src/infrastructure/storage/fs/

**深度推演（模拟 dev agent 按 Task 0~7 走查——路径 47/48 存在 + 锚点抽查 10/10 命中 + contracts 1342 test 函数实测）：**
- R2D-1【P1】**引文聚合整体故障容错未定义行为**——query_archive 抛异常/get_point 连接级异常时上抛会炸主链 → 裁定：整体 try 容错降级空附录 C + warning（增强面不阻断——与事件发布宽容哲学同构）；AC-3 补边界 + Task 3 循环 B 补用例
- R2D-2【P1】Task 5.2 冻结面 git diff 清单含本 Story 必改文件（report_exceptions.py）操作性矛盾 → 改「钦定改动文件 diff 限钦定行，491 既有行零触碰即非违例」
- R2D-3【P2】poetry 依赖组迁移无操作序列（add/remove 会重解析版本）→ 补手工编辑 + `poetry lock --no-update` 序列
- R2D-4【P2】13 场景「钉死」缺机制 → 补「场景逐一标注覆盖 AC 编号 + 双向覆盖互检」
- R2D-5【P2】`__post_init__` 校验清单与字段表不对齐（漏 page≥0/document_id UUID 格式）→ 补齐
- R2D-6【P2】`_publish_event`「逐字复用」复制 vs 共享未裁定 → 裁定同款代码复制（6-5a 文件冻结不可提取，docstring 注形态溯源）
- R2D-7~13【P3】collect-only 验证命令 / 1479+ 口径注明（collected 含参数化） / 三态样例构造来源 / linkRect 前向引用机制提示（单遍渲染） / 三私有函数签名 / CLI bucket 打印来源（EVIDENCE_BUCKET_TYPE 常量 import） / 冻结路径清单单源指回

**统计：P1×3 + P2×7 + P3×11 = 21 项修复（两 Agent 重复发现已去重——R2-1 系回归核查与交叉引用共见；含 2 项 Round 1 联动残留清偿）；AC-1 标题与 Then 六段切分统一（聚合→快照→引文→渲染→L4+L2→事件）；组合根构造参数默认值形态注记补齐**

**Round 3（2026-11-04，技术实证 + WORM/并发复核 + 方案合理性终审共 3 Agent 并行）：**

**技术实证（/tmp 最小脚本实跑 8/8 通过——方案可行性完全成立）：**
- R3T-1【P1】AC-4「命名目标可解析」断言形态不可实现（pypdf `named_destinations` 为空——reportlab save 期已解析为 /Dest 直接数组）→ 改「/Dest 数组首元素可解析为有效页对象」；悬空链接由 save 期抛错天然拦截（→492 包装路径实证）
- R3T-2【P1】AC-8「extract_text 对 CID 兼容性受限」被实证**证伪**——STSong-Light（Adobe-GB1 预定义 CMap）正文/表格中文完美提取 → 断言分层升级为中文值级全文比对（ASCII/outline 面保留冗余、pypdfium2 保留视觉面）；先例 test_pdf_parser.py:267 适用范围辨析（其他生成器场景）
- R3T-3【P2】492 触发场景补「未注册锚点引用（save 期 ValueError）」实证样例
- R3T-4【P3】表格断言升级全文比对（ASCII 抽样降为冗余面）

**WORM 链路与并发复核（代码级，7 项全可行）：**
- R3W-1【P2】类名笔误修正：WormLifecycle → **WORMManager**（worm_lifecycle.py:35 类/:109 方法——R1 修订引入）+ 两步非原子注记（put→set_object_retention）
- R3W-2【P2】OD-4 补 WORM 生效前提（桶须开 object lock——无锁桶 set retention 抛 S3Error→493 非静默；测试自愈链/生产带锁桶先例注记）
- R3W-3【P3】493 半归档态可接受注记（report_id 唯一键重试覆盖）
- R3W-4【P3】Task 6.4 补 P95 常量防照抄注记（6-5a 源码 30.0 是其口径，本 Story 60.0）
- R3W-5【P3】渲染同步阻塞量级评估注记（3×<100ms 级无害，口径维持不经 to_thread）
- 附：Task 0.2 补 R3 预实证结论待复验注记（extract 完美//Dest 直接数组/前向引用单遍/悬空抛错）

**方案合理性终审（10 维度对标：9 项「合理维持」+1 项可选补强，无 P1/P2）：**
- R3B-1【P3 采纳】Task 3 循环 B 补引文去重保序变异锚（核心新逻辑断言活性与 6-5a 防御密度对齐）；Task 3 DoD 变异实证 ×2→×3
- R3B-2【P3 采纳】聚合公开化 docstring 顺带注记 MarkdownReportDocument 双渲染共用 IR 语义（VO 本体冻结不可改，docstring 消歧位）
- R3B-3【P3 不采纳】citations 独立表触发条件台账登记——裁定不登（避免台账膨胀；6-8 直读 metadata 设计已使触发概率极低，10 项评审中 C9 已留演化触发点口径）

**统计：P1×2 + P2×3 + P3×6 = 11 项修复/采纳 + 1 项裁定不采纳；技术实证 8/8 通过（STSong-Light 注册/outline 层级/linkRect 前向引用单遍/pypdf 读回/pypdfium2 冒烟/Table 四列/4 线程并发/悬空拦截）；L4/并发/性能 7 项可行性全成立**

**Round 4（2026-11-04，需求覆盖核查 + 测试矩阵核查 + 门禁复核共 3 Agent 并行）：**

**需求覆盖（六输入源核查——epics 11 需求点/Epic 6 头部/prd/6-5a defer 钩子 11 处/deferred-work 台账/下游交接面全承接，4 项遗漏）：**
- R4N-1【P2】6-5a 钦定「思维链全文附录归 6-5b/6-7 立项定夺」裁定义务未接 → 范围边界表新行：维持 YAGNI 归 6-7（引文索引已交付溯源消费面，chain.to_display() 资产在位）+ Task 0.7 台账注记
- R4N-2【P3】6-5a CR2-F12/CR3-F6「PDF 渲染立项统一评估转义边缘形态」落档缺失 → Task 0.7 补评估注记（PDF 链结构同源直渲染不经转义面——留项维持 Markdown 面）
- R4N-3【P3】NFR-PERF-03「完整 SP/BP 报告<2 分钟」半边无裁定 → AC-7 补口径（归 Epic 10 完整六阶段）
- R4N-4【P3】「分享」承载位无显式裁定 → REST 边界行补（CLI-only 下分享=PDF 文件分发，用户级通道归 6-8/6-11）

**测试矩阵（7 维度核查——AC-2 第三条/清理链/附录 A 两态等 9 项缺口）：**
- R4T-1【P2】AC-2 第三条验证标准（附录 B 联动断言）无承载 → 集成场景②补第三项断言（聚合复用双格式同值）
- R4T-2【P2】引文预置 collection 形态二选一未裁定 → 裁定复用既有测试 collection + 点级 FilterSelector 清理（零生命周期管理，避 6-5a Qdrant 清卷教训）
- R4T-3【P2】附录 A 缺失态（无快照——目录条目非恒定敏感面）无测试 → 渲染器三态改「正常/快照缺失/降级」（缺行态归 6-5a 聚合测试已覆盖 8+ 用例实证）
- R4T-4/5【P3】get_point 连接级 raise 用例两入口合一 + 悬空锚点负向用例（render 抛 ValueError——save 期守护实证，492 包装面关联 Task 3）
- R4T-6【P3】citations 断言口径滞后 → 七键值级断言（stage 必断言防漏实现）
- R4T-7【P3】并发「互不串扰」值级形态定义（plan_id↔report_id 对应 + 对象键互异集合）
- R4T-8【P3】契约测试构造参数默认值断言归属单测注记（防过度断言）
- R4T-9【P3】净增 0 对照面口径差注记（归档三面并口径/Redis 归 6-5a 链——四项为 PDF 新增面）

**门禁复核（13 项修订全部落位正确、引用真实——6-5a L34 逐字命中/缺行测试 8+ 用例实证/grep 零残留）：**
- R4G-1【P2】学习经验「断言判别力」条目 R3 联动遗漏（仍写旧口径「extract_text 受限三层分工」）→ 改 R3 实证升级口径
- R4G-2/3【P3】结构树 ├── 符号修正 + Task 2 表格断言表述对齐 R3 升级口径

**统计：P2×5 + P3×11 = 16 项修复；收敛判据：P0 2→0→0→0、P1 7→3→2→0 双零达成、联动噪声 2→1 递减——满足进入 Round 5 终审条件（结构修复→细节钉死阶段转换完成）**

**Round 5（2026-11-04，独立终审——general-purpose 新鲜上下文 1 Agent，无前四轮确认偏误）：**

**终审通过面（方案与结构全部经受住新鲜视角复核）：**
- 代码锚点抽样 5+7 全命中零漂移（聚合/渲染分离 :176-177、archive-evidence :40、MVP_TENANT_ID :39、evidence_refs 写侧 :200-203、_VALID_LAYERS :67 + archive 签名/payload 6 键/桶常量/组合根三锚/query_archive 等附加七项）
- 残留旧口径 16 词 grep 活文本零残留（命中均合法语境：审查记录引旧稿/蓝图名框架/outbox 四键/防照抄注记）
- 结构树符号/39 Subtask 编号连续/8 张 TDD 表/章节层级全收敛；四轮编号唯一无重复
- 数字口径：13 场景/恒 11 六处/citations 七键/九依赖/六段编排四处同构/PortSpec×3 全通过

**终审修复 8 项（P2×2 + P3×6，全文字级）：**
- R5-1【P2】R2 统计行三重失准（声称 P1×3+P2×6+P3×9=25，机械核对实为 P1×3+P2×7+P3×11=21 且原算术 18≠25 不闭合——两 Agent 重复发现未去重所致）→ 统计行/v1.2.0 说明/sprint-status 注记三处联动订正（「计数纪律」红线复发清偿）
- R5-2【P2】增量冻结表附录 C 行内联表格四管道未转义——GFM 渲染下切为 9 列、块型序列整段（Task 0 权威输入）渲染丢失 → 管道转义 `\|`
- R5-3【P3】R4 统计分项失准（实为 P2×5+P3×11 非 4+12，总数 16 恰对）→ 分项订正
- R5-4【P3】OD-11 `--format <pdf|markdown|json>` 两管道未转义 5 列错位 → 转义
- R5-5【P3】数据模型 VO 段外层括号未闭合（R2-6 修的是另一处，此处漏网）→ 内层换【】消歧
- R5-6【P3】Task 3 DoD 变异第三锚名「渲染锚点结构」与 Task 2 实锚「outline 层级生成」漂移 → 对齐 + 全 Story 变异锚四处全景注记（T1×1/T2×1/T3×2）
- R5-7【P3】R1「26 项」两处传播缺「22 编号+4 附注」限定 → 补限定
- R5-8【P3】「计数不变量 12 系口径」无溯源（6-5a 与实体均无 12 系表述）→ 改可溯源表述（degraded≤section_count 恒 11）

**定稿判定：五轮收敛完成，v1.5.0 定稿**——P0 2→0→0→0→0、P1 7→3→2→0→0、发现级别全程递减、联动噪声 2→1→0；方案裁定（同源双渲染/L4 键锚 report_id/引文三段链/492-493 开码/tenant_id 构造注入/archive-evidence 同桶）全部经代码实证与新鲜视角复核成立；残留清零。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**Round 1（2026-11-04，四 Agent 并行调研【核心链路/渲染器与PDF结构/契约架构组合根CLI/测试矩阵判别力】+ 主会话亲验 + C3 双评审员【技术正确性/纪律最小变更】+ 复评一轮收敛）：**

发现总计 P1×4 + P2×7 + P3×13（交叉去重后；双评审确认根因诊断全部成立、无越界、无漏项）。落码 20 项（F1~F20，F21 drop，F22 台账补记）+ 改判 4 项维持；变异红证三锚（F1 占位文案/F4 page>0 守护/F2 find 容错）；新增/强化断言 12 条；回归面：单测 27+22、契约 14、集成 6、验收 13 全绿。

**P1 修复（4 项）：**
- CR1-F1 document_missing 附录 C「文档名」列渲染空串——实现仅特判 point_missing 占位（svc:361），端口契约 pdf_report.py:32-33 与 AC-3 双冻结「[溯源不可用：文档记录缺失]」，测试三面零断言（单测仅 status/集成验收仅 point_missing 形态）。修复：`_UNAVAILABLE_TEXTS` 双态映射（status 值域三元组冻结使 KeyError 不可达）+ 单测 IR 行断言（rows 全等含冻结文案）+ 变异红证
- CR1-F2 find 连接级异常裸逃逸主链——`:321` find 在 try 外（try 仅包 get_point/query_archive），Agent 实证 ConnectionError 逃逸 generate_pdf_report，违背 R2D-1 整体容错裁定。修复：find 纳入 try（解析链任一依赖异常 → 整体降级空附录 C）+ doc 联动三处（服务模块 docstring/端口契约/AC-3 容错枚举）+ 单测 + 变异红证
- CR1-F3 bullet 前缀 `•`（U+2022）豆腐块——STSong-Light（Adobe-GB1）无该字形，pypdfium2 光栅化实证 □；extract_text 走 CMap 解码与字形无关 + 冒烟只查非空白像素——测试双盲区；每份 PDF 每条列表项方块（高管交付物不可接受）。修复：改 ASCII `- `（与 markdown 渲染器 :149 对称恢复；`·`/`※` 同豆腐块，ASCII 唯一稳态——实证）+ 值级断言（前缀+载荷连续序列，预研实证 extract_text 完整保留）
- CR1-F4 页码列 resolved+page=0→`-` 冻结契约零守护——Agent 变异注入实证：删 `and entry.page > 0` 后 42 用例全绿存活（渲染 "p.0" 无断言红）。修复：单测补 IR rows 全等断言 + 变异红证；渲染器 dash 直喂用例 docstring 口径校正（dash 决策在服务层）

**P2 修复（7 项）：**
- CR1-F5 chunks/page_start 脏形态守卫缺失——`metadata={"chunks": None}` TypeError / `page_start="3x"` ValueError 裸逃逸（与 uuid.UUID 守卫防御密度不对称）；顺带消除负 page_start 经 int() 触发 VO 242 炸链路径。修复：isinstance 守卫（list/int/bool 排除/>0）+ 两脏形态单测
- CR1-F6 L2 save 失败误包装 493——493 契约三处均 L4-only、6-5a `_save_l2` 先例与 491 docstring 明文「L2 元数据行落库失败（layer="l2"）」。修复：改 `ReportStorageError(layer="l2")`（491 语义精确归宿，493 契约文档零改动——实现回归契约）+ 单测 + 服务/端口 Raises 节联动
- CR1-F7 generation_ms 计时点在渲染/L4 前——PDF 链最重两段被排除（6-5a 实测点在 L0 写后含渲染）；**Story :549 绿桩钦定顺序本就是「渲染→L4→实体构造→L2 save」——F7 是回归钦定**。修复：实体构造（含 generation_ms）移至 L4 后 + 双窗口辨析注释（metadata 执行耗时行 vs 实体字段 vs P95 采样口径）
- CR1-F8/F9 渲染器文本净化层——上游发射源（⚠️×7 callout 前缀 + `**{label}**` paragraph）均在 6-5a 冻结面（本 Story 仅聚合更名权），STSong-Light 无 U+26A0/U+FE0F 字形、PDF 链无 GFM 解释器。修复：`_pdf_text()` 净化函数（GFM 行内强调剥除——markdown 渲染器原样透传由 GFM 查看器解释，PDF 无下游解释器故渲染侧剥除；`⚠️ ` 装饰前缀移除——语义由 [降级] 文字标记承载）应用于全部文本出口（含 _OutlineMarker title/表格 cell/封面标题——F13 title 转义合并）；markdown 链测试零回归（断言全在 markdown 输出面）+ 两条净化单测
- CR1-F10 会话包装 docstring 失实——「活动会话优先/嵌套复用」实为无条件新建遮蔽（session_context 无 optional 分支）。修复：docstring 按实况校准（不参与请求事务/每次 checkout 已知形态）+ 6.5b-DF4 台账登记（会话抖动债务）
- CR1-F11 验收 S2「零事件落位」断言缺——feature 三面承诺 vs 断言两面。修复：`_count_outbox_rows`（plan 维度，与清理面同源通道）+ outbox==0 断言
- CR1-F12 集成净增 0 引文预置面无对照断言——docstring 四面声明 vs 断言三面。修复：`_count_citation_documents`/`_count_citation_points` helper + 两组 presets 清理后两面零断言 + 采样轮 outbox==20 基线对照 + 并发 plan outbox==1（S11 taxonomy 修正并入）

**P3 修复（8 项 + F13 并入 F8/F9 净化出口）：** CR1-F14 chain_archive_service Any→Port 类型（6-5a 同位先例）；CR1-F15 _APPENDIX_C_TITLE 双源上提 ports 单源（`__all__` 登记，两侧 import 引用常量名；**列数守卫经评审裁定删除**——静默回退违「修根因不抑制」，reportlab ValueError→492 天然 fail-loud）；CR1-F16 桶常量等值钉（EVIDENCE_BUCKET_TYPE == L4_BUCKET_TYPE 契约断言——值级镜像漂移必红）；CR1-F17 测试判别力四条（幂等 spy 委托真实 registerFont+计数/count==1、tags 收紧 `{"report","pdf"} <= set()`、getsource 收紧 resolve 调用锚定注释免疫、dash 用例 docstring 口径）；CR1-F18 point_missing 吸收形态文档化（缺 document_id/非法 UUID 同判——检索点信息缺失伞形）；CR1-F19 collection 表述校准（写侧字面量对齐非 env 传导——ports/Story :220 两处落地 + svc 侧 R2 补齐）；CR1-F20 `__all__` 私有名移除；CR1-F22 :893 台账补 typing import cast 行。

**drop 1 项（评审裁定）：** CR1-F21 B 验证器 ast.Attribute 分支——理论威胁（服务文件无 `import typing` 形态）+ 只改 PDF 副本造成守护家族不对称（test_markdown_report.py:146 同款 Name-only）。

**改判维持 4 项：** outline 跳级（不可达+命中即 492 fail-loud 可辩护）/callout 空行差异（callout 恒单行实证）/会话包装显式失败桩（方法集合不可穷举——docstring 指引替代）/document_missing 时 document_id 丢弃（VO 契约允许空串+status 可判别+chunk_id 可回查）。

**统计：发现 24 = P1×4 + P2×7 + P3×13【10 编号项 F13~F22 + 3 项 P3 级改判（outline 跳级/callout 空行/document_id 丢弃）】；处置 = 落码 19【F1~F20 减 F21，F13 并入 F8/F9】+ drop 1（F21）+ Story 台账补记 1（F22）+ 改判维持 4【3 项 P3 发现 + 1 项 F10 内裁定延伸（会话包装桩）】；变异红证 ×3；新增断言 12 条；单测 49（27+22）/契约 14/集成 6/验收 13 全绿——四目录全量两轮稳定归 Round 4 纯验证轮承载。**

**Round 2（2026-11-04，回归核查 + 交叉面传播双 Agent 并行 + 主会话复核）：** R1 修复 19/20 完整落位 + 三锚变异红证复验存活；发现 P2×2 + P3×6 全部 R1 传播面/自伤面——R2-1【P2】F19 svc :133-134 半落地（「三处」承诺漏 svc 构造参数 docstring，与 ports/组合根双矛盾——补落地）；R2-2【P2】F12③ 验收 S11 outbox==20 落位漂移至集成（方案明文移入落码但仅集成侧兑现——feature/.py 锁步补断言）；R2-3 F2 注释重复两份（变异还原编辑自伤——删）；R2-4 ⚠️ filename 保真度注记不对称（与 `**` 注记合并）；R2-5 集成并发三 plan 清理后 outbox==0 缺断言（净增 0 承诺面并发分支补齐）；R2-6 引文锚点序号列 isdigit 守卫（XML 属性位 fail-loud 前移——paraparser 对 `<`/`&` 宽容静默形态以断言在渲染入口即红）；R2-7 方法级 docstring「连接级异常」措辞残留（:284/:287/测试 :439 统一「解析链依赖异常」）；R2-8 统计行计数闭合重构（本段统计行）；R2-9 6-5a 契约测试 or/裸子串旧形态家族不对称——deferred-work 登记（6.5b-DF5）。

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施（2026-11-04 完成——Status → review）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.7.1
**创建日期/Created:** 2026-11-04
**最后更新/Last Updated:** 2026-11-04
**更新说明/Description:**
- v1.7.1: 代码审查 Round 2 回归核查+交叉面修订（双 Agent 并行：R1 修复 19/20 落位确认+三锚变异红证复验存活；P2×2+P3×6 全传播面/自伤面——F19 svc 侧补落地/验收 S11 outbox 补断言【feature/.py 锁步】/注释重复清理/⚠️ 注记对称/并发 outbox 断言/isdigit 守卫/措辞统一/统计行闭合/6.5b-DF5 登记）
- v1.7.0: 代码审查 Round 1 修订（四 Agent 并行调研 + C3 双评审员 + 复评收敛；P1×4+P2×7+P3×13 发现，落码 F1~F20 + F21 drop + F22 台账 + 改判 4 维持；变异红证×3 + 新增断言 12 条；六项核心修复——document_missing 占位文案/find 容错边界扩展/bullet U+2022 豆腐块改 ASCII/页码列守护锚/chunks 脏形态守卫/L2 save 失败归 491；渲染器净化层（⚠️/**）+ generation_ms 回归钦定顺序 + 净增 0 断言四面补齐；6.5b-DF4 登记；详见 Review Findings）
- v1.6.0: dev-story 实施完成（Task 0~7 / 39 Subtask 全勾——四 Agent 并行调研 + 主会话亲验；13 验收场景全绿 + 集成五场景两轮稳定 + 四目录全量 14756 passed × 2 零失败 + 覆盖率 93.10% + mypy 752 零错误 + 变异实证×4 + 红线三查零输出；实施攻坚六项：引文锚点 link 自指承载/Qdrant 点 id MD5 归一走生产通道/document_repository 组合根会话包装/收集段 archived_at 排序/两守护测试正当演进/Qdrant FD 环境铁证清卷闭环+6.5b-DF3 登记；Status → review）
- v1.5.0: 文档审查 Round 5 独立终审收敛定稿（general-purpose 新鲜上下文终审：锚点 5+7 全命中零漂移/残留旧口径 16 词零残留/结构编号层级全收敛；终修 8 项 P2×2+P3×6——R2/R4 统计行计数纪律订正/增量冻结表与 OD-11 管道转义/括号闭合/变异锚名对齐/「12 系」无溯源表述改写；五轮收敛 P0-P1 双零残留清零，定稿）
- v1.4.0: 文档审查 Round 4 修订（3 Agent 并行：需求覆盖六输入源核查 + 测试矩阵七维度核查 + 门禁复核；P2×5+P3×11 共 16 项——6-5a 钦定思维链附录裁定义务承接【YAGNI 归 6-7】/AC-2 附录 B 联动断言补承载/引文预置 collection 形态裁定/渲染器三态改快照缺失敏感面/citations 七键断言/互不串扰值级形态/R3 联动残留清偿等；收敛判据 P0/P1 双零达成；详见 Docs Review Fixes）
- v1.3.0: 文档审查 Round 3 修订（3 Agent 并行：技术实证【/tmp 脚本实跑 8/8 通过】+ WORM/并发复核 + 方案合理性终审【10 维度对标 9 维持】；P1×2+P2×3+P3×6 共 11 项——AC-4 断言形态修正【/Dest 数组非命名目标】/AC-8 断言分层升级【extract_text 中文完美工作证伪旧注记】/WORMManager 类名修正/object lock 生效前提注记/引文链变异锚补强等；详见 Docs Review Fixes）
- v1.2.0: 文档审查 Round 2 修订（3 Agent 并行：回归核查 + 交叉引用 + 深度推演；P1×3+P2×7+P3×11 共 21 项（重复发现去重后）——R1 联动残留清偿【EVIDENCE_PACKAGES 残留/L2274】/引文聚合整体容错边界裁定【query_archive 异常降级空附录 C 不炸主链】/Task 5.2 冻结面与必改文件操作性矛盾修正/citations 补 stage 键/AC-1 六段切分统一/poetry 迁移操作序列/13 场景覆盖互检机制/_publish_event 复制裁定/linkRect 前向引用提示等；详见 Docs Review Fixes）
- v1.1.0: 文档审查 Round 1 修订（6 Agent 并行：代码事实核查×4 + 一致性内审 + P0 方案设计；P0×2+P1×7+P2×8+P3×5 共 26 项（22 编号+4 附注）——tenant_id 构造注入裁定【MVP_TENANT_ID 单源】/L4 桶名对齐代码单源 archive-evidence【蓝图注记 Task 7 回填】/字段数口径统一/行号漂移修正/limit=64 理由重述/快照步补齐等；详见 Docs Review Fixes）
- v1.0.0: 创建故事文件（四 Agent 并行调研【报告链路/引文数据面/测试样板/架构治理】+ 主会话八项亲验；OD-1~OD-12 十二项架构裁定落档——同源双渲染（聚合公开化复用）/L4 WORM 归档（键锚 report_id）/PDF 渲染器 application 端口+infrastructure 实现（reportlab 唯一宿主）/引文 evidence_refs 首消费三段链（bbox 缺口 defer）/异常开码 492-493（不扩 491 值域）/CLI --format 参数/依赖组迁移为关键裁定；6-5a defer 钩子五条+新留项两条逐条处置）
