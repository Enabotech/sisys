# Story 6-7: 溯源树展示（四层追溯聚合查询——结论→分析→数据切片→原始文档 + 页码级跳转载荷 + ingestion payload 扩键半边清偿）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行文档审查修订循环（参照 6-6 五轮形态）+ 人工按 story-template 合规清单核对后再执行 `dev-story`（`validate-create-story` 系上游模板措辞，本仓无该名 skill）。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统按 plan_id 展示溯源树——从结论逐层展开至原始数据（结论→分析→数据切片→原始文档四层），节点携带页码级跳转载荷（文档/页码/对象键/bbox 透传）并支持按深度交互式展开,
**So that** 验证分析结论的可靠性——30 秒内从任一 BLM 结论追溯至原始文档证据出处（数据溯源时间<30s，prd L243）。

### 业务价值

- **Epic 6 价值组「战略规划与审批能力」的可信度支柱**：生成侧（6-1~6-5b）与审批侧（6-6）已 done，本 Story 交付「规划结果可验证」面（P0-7）——RAG 结论的可信度由溯源可达性背书（prd L149「数据驱动决策——支持高保真视觉级溯源」、L1075「AI 幻觉防护 - 高保真溯源 + 人工 Checkpoint」）
- **深化 FR-SR-08 (P0) 的展示侧语义**（prd L1788/or.md 二.7.(1)）：FR Coverage Map 中 Story 6.7 **无独立 FR**（同 6-6 形态）——FR-SR-08 数据面（三元组保留）已由 Epic 3 Story 3.8 交付，本 Story 兑现其「展示」半边：**evidence_refs 引用链的四层树形聚合查询面**（3-8 交付的 `TraceabilityPort.trace(claim)` 是按文本重检索的断言面，与按 plan_id 遍历既有引用链的树查询语义正交——6-5b OD-6 裁定延续）
- **6-4 思维链证据链的消费闭环**（6-4 story L14「支撑后续 6-7 溯源树展示」、L21「下游 6-7 溯源树展示消费思维链证据链」钦定的兑现）：EVIDENCE_PACKAGE 归档行 `assumptions.evidence_refs`（chunk_id 清单）写侧在位、读侧仅 6-5b 引文 flat 表一处消费——本 Story 交付第二个读侧消费方（树形、含思维链「计算逻辑」三元组）
- **清偿两条钦定 6-7 承接的台账留项**（deferred-work 成文「触发=6-7 立项」）：
  - **6.5b-DF1 (P2) 半边清偿**：`chunk_indexing_handler.py:151-168`（deferred-work 台账原文 :156-168）Qdrant payload 扩键 `page_start/page_end`（数据已在位——`SemanticChunk.to_dict()` 含页码键、PG `metadata["chunks"]` 已持久化，仅 handler payload 构造未透传）；**bbox 四元组另半边 defer 归 6-8**（OD-8——chunk 级 bbox 语义未定+版面模型在位依赖+Web 阅读器是真实消费方）
  - **6.4-DF3 (P3) 清偿**：同 plan_id 跨进程重跑叠加行的读侧判别（OD-5——stage 分组 last-write-wins + adopted/total 截断对照）
- **为 Epic 21/22 供给后端能力**：Story 21.1 证据面板依赖 Epic 3 Story 3.8 溯源接口（epics L3369/L3381）；Story 22.1 工作台证据树（FR-UI-13「七步证据树折叠/展开」）与本树查询面同构——本 Story 的 depth 懒展开端口是其后端供给基座
- Epic 6 内部顺序：6-6（done，审批面）→ **6-7（本 Story，溯源面）** → 6-8 高管简化视图（并列 backlog——epics L2018 依赖列为「依赖 Story 6.5a」不含 6-7，括注明示「不依赖 Story 6.5b」——6-8 与 6-7 无依赖关系）

### 范围边界（出处逐行声明）

| 面（出处） | 已交付（禁重复造轮） | 6-7 增量（本 Story） |
|---|---|---|
| 溯源数据面（3-8） | `TraceabilityPort.trace(claim)` 按文本重检索断言面 + `Citation` VO（bbox/page_number 字段族在位）+ `/api/v1/search/trace` REST 面 | **零触碰**（语义正交——claim 重检索 vs 引用链遍历；6-5b OD-6 裁定延续）；本 Story 新建树聚合查询端口 |
| 引文解析三段链（6-5b OD-6） | `query_archive(EVIDENCE_PACKAGE)` → `get_point` → `document_repository.find` → `metadata["chunks"].page_start` 匹配；降级三态（resolved/point_missing/document_missing）；`CitationEntry` 七键 | **链路蓝本复刻**（同端口同顺序，独立服务承载）；引文 flat 表零改动 |
| 思维链追溯查询（6-4） | `query_chain_trace` 读回五键 records（stage/chain/archive_id/degraded/blob_content）——**不含 evidence_refs**（assumptions 列需自行读取） | 树服务直接 `query_archive` 读 `assumptions["evidence_refs"]`（6-5b 收集段同款）；6-4 端口零改动 |
| BBox ingestion（2-3/3-8） | `OnnxLayoutDetector` 元素级 bbox → PG `parse_result`；3-8 读侧 `payload.get("bbox")` 就绪 | payload 扩键 `page_start/page_end`（半边清偿）；**bbox 四元组 defer 6-8**（OD-8）；读侧 `.get()` 缺省兼容存量点 |
| REST 查询端点（interface-design.md:1406 `GET /documents/{id}/trace` P0） | openapi.yaml 至今无 BLM 面 endpoint（6.1~6.6 惯例） | **不做**（归 7-2/Epic 7——CLI-only 第六连先例，6.1-DF5 同锚）；openapi.yaml 零 diff |
| Web 阅读器/高亮（6-8） | 未立项 | **不做**（PDF.js/Bounding Box 高亮归 6-8——epics L2018 依赖链不含 6-7；UX spec L182「内置阅读器基于 PDF.js」是 Web 面） |
| 事件消费 | L170 消费基建四件（poller 宿主等） | **不做**（纯查询面零事件订阅——锚位顺延 Epic 8，Task 0.7 注记） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 四层溯源树结构（结论→分析→数据切片→原始文档）

**Given** 某 plan_id 下已存在 BLM 归档链（经完整 run 或 6-4 归档轻装配通道逐 stage 直交 EVIDENCE_PACKAGE 归档行，行含 `assumptions.evidence_refs`（chunk_id 清单）与 `decision_basis.{kind,stage,chain,degraded}`），且 evidence chunk 已预置 Qdrant 点（payload 含 document_id）与 PG documents 行（filename/`metadata["chunks"]` 含 page_start）
**When** 分析师请求溯源树（编程面 `TraceabilityTreeService.build_trace_tree(plan_id, depth=4)` 或 CLI `trace-tree --plan-id`）
**Then** 返回 `TraceabilityTree`：根节点为**结论层** `ConclusionNode`（plan_id/title/summary——summary 优先取 `market_insight_synthesis` 行 `chain.final_answer` JSON 的 conclusions 联展（**联展格式钦定 `"\n".join(conclusions)`——list 保序；非 list/空/解析失败降空串，DR3-8**；**synthesis 行入同一 stage 分组 last-write-wins——多行 synthesis 取最新行供 root.summary，其采纳行计入 adopted（全 run total=8/adopted=8、stage_count=7——DR3-2）**，行缺失降级空串不抛异常；**synthesis 行不产生 StageNode——结论层即其呈现位（OD-4/DR1-13）**，分析层为七 stage 值域（`STAGE_VALUE_DOMAIN` 八值去 market_insight_synthesis），ConclusionNode.stage_count=分析层节点数（全 run=7）），其下为**分析层** `StageNode` 逐 stage 挂接（每 stage 一节点；**root.children 序=BLM 流程规范序**（performance_gap 在前+六子按 `MARKET_INSIGHT_STEP_CONFIG` 枚举序——与 display_name 三源同族常量零新常量；仓储返回序是 archived_at DESC（archive_repository.py:246），服务必须重排，禁透传遍历序——DR3-1）；**stage∉七值域的链行不产生 StageNode——计入 total、不计 adopted（收集段读侧过滤不抛，同 kind 过滤语义——DR3-4）**；核心键：stage/display_name/summary/degraded/degrade_reason/tools_used/reflection_excerpt/evidence_count/children——全键契约见 Task 0.1；「数据来源→计算逻辑→中间结论」三元组由 evidence_count（来源）/tools_used+reflection_excerpt（计算逻辑）/summary（中间结论）承载——or.md L344「每层三元组」经适配：切片/文档层无「计算逻辑」可示，三元组落位分析层（OD-4 适配论证））
**And** depth≥3 时 StageNode 下挂接**切片层** `ChunkNode`（chunk_id/content_excerpt（300 字符截断——6-1 证据文本截断同族口径，`blm_planning_service.py:98`）/page_start/page_end/status/children）；depth=4 时 ChunkNode 下挂接**原始文档层** `DocumentNode`（document_id/filename/version/page/object_key/bucket/bbox/status/jump_ready 九键（全键契约见 Task 0.1）——page 取 PG `metadata["chunks"]` 按 chunk_id 匹配 `page_start`（6-5b `:360-368` 同款，脏形态守卫降 None），object_key/bucket 取 `metadata["storage_object_key"]`/`"raw-documents"`（`document_parsing_service.py:161` 解析下载路径单源），bbox 取 Qdrant `payload.get("bbox")` 透传（现状恒 None——OD-8））
**And** 同 document_id 多 chunk 引用时文档查询按 document_id 去重（每 document_id 恰一次 `document_repository.find`——服务内缓存字典；性能窗口友好 + 6.5b-DF4 会话抖动知悉注记；**find 恰一次调用计数断言归 Task 2 单测承载**——验收面真实服务无调用记录面，DR1-5 同款分立，DR2-9）

**验证标准/Validation Criteria:**
- [x] 全树四层落位：预置 **2 stage 各 1 chunk 且同一 document_id**（DR3-6——顺带断言两 DocumentNode 值等且各自在位（嵌套重复非共享——语义注记的验收级断言锚收编））→ 树节点层级/键集/值级断言（chunk_id 与预置一致、filename/page 值级、document_id 经 get_point payload 解析值级；**root.children 序=流程规范序值级断言**（DR3-1））
- [x] 结论层 summary：**腿1=synthesis+gap 双行预置**（取 conclusions 联展非空+stage_count==1——DR1-13 错实现给 2 必红，DR3-6）；**腿2=gap-only**（无 synthesis 行）降级空串+stage_count==1、树正常返回
- [x] 三元组承载：StageNode.tools_used 非空（预置行 chain.tools_used 值级）+ summary 非空 + evidence_count == len(evidence_refs)

### AC-2: 交互式展开（depth 懒加载语义）

**Given** 同 AC-1 归档链在位
**When** 以 `depth=2` 请求溯源树（端口签名 `build_trace_tree(plan_id, depth=2)`；depth 值域 {1,2,3,4}，默认 4——CLI `--depth` 透传）
**Then** 树仅构建结论层+分析层（StageNode.children 恒空元组），**切片层零解析**——`l3_vector.get_point` 零调用（call_order 断言归 Task 2 单测矩阵承载——6-3 R1-F2 形态；DR1-5；懒展开是 6-8 Web「折叠/展开」的后端口径——FR-UI-13 工作台证据树，Web 面跳转性能先例参照 epics Story 21.6「追溯跳转<100ms」L3374，非本 Story 门禁）
**And** depth=3 时切片层解析但文档层零解析（同款分层懒加载）；depth=4 全树（默认值）；**depth=1 仅结论层**（root.children==() 恒空——收集/kind 过滤/判 run 段照常执行（stage_count 可用），切片与文档层零解析——归单测矩阵第四档断言，DR1-2）；depth 越域（0 与 5 双边界）→ 用例层 242 `EntityValidationError`（用例层守卫直系先例=`GetBlmChainTraceUseCase` UUID 守卫同层同码；值域枚举形态（`not in {1,2,3,4}`）为仓内新形态注记——无完全同构先例，DR1-21）

**验证标准/Validation Criteria:**
- [x] depth=2：树形断言 StageNode.children==()（验收面真实服务无调用记录面——**call_order 零调用断言归 Task 2 单测矩阵承载**（AsyncMock assert_not_called 天然可写），DR1-5）
- [x] depth=3：切片层 ChunkNode 在位 + 树内零 DocumentNode（find 零调用断言同归单测）
- [x] depth=1（单测矩阵第四档）：root.children==() + get_point/find 双零调用（DR1-2）
- [x] depth 越域 242（0 与 5 双边界——值级断言 code）

### AC-3: 页码级跳转载荷与 bbox 透传（Bounding Box 跳转的 MVP 口径）

**Given** 树已构建（depth=4）
**When** 分析师查看任一 ChunkNode→DocumentNode 路径
**Then** DocumentNode 携带**跳转载荷六键**：document_id/filename/version/page/object_key/bucket——「30 秒内从结论跳转至原始文档坐标点」（prd L243/UX spec L165）的数据面：page（页码级定位——`metadata["chunks"].page_start` 通道）+ object_key/bucket（MinIO 原始文件直取——6-8 Web 阅读器消费面）齐备
**And** bbox 键恒在（`payload.get("bbox")` 透传——payload 扩键后新点若有则带，现状生产恒 None）：**bbox 四元组写入归 6-8**（OD-8——chunk 级 bbox 语义未定：一 chunk 跨多元素需聚合语义设计 + `SISYS_LAYOUT_MODEL_PATH` 模型在位依赖 + Web 高亮是真实消费方）；epics「Bounding Box 跳转测试」以**跳转载荷组装口径**承载（OD-7 口径差声明——CLI 无跳转运行时）
**And** 3-8 `TraceabilityService.trace` 的 `payload.get("page_start", 1)` 读取面（`traceability_service.py:125`）因 Task 1 扩键对新索引点**自然受益**（page_number 不再恒 1）——3-8 代码零改动（受益注记，非本 Story 断言面）

**验证标准/Validation Criteria:**
- [x] 跳转载荷六键值级断言（预置 filename/version/object_key 与 PG 行一致）
- [x] bbox 键存在性断言（值 None 或 dict——透传语义，不合成坐标；**R1-F2 收口注记**：S4 预置 8 业务键无 bbox → 断言强化为 `is None`（合成坐标变异即红——防按 VC 字面写回恒真形态））
- [x] page 取值：预置 chunks 元数据 page_start 值级；chunk 不在 chunks 列表（脏形态）→ page=None 不抛异常（6-5b 脏形态守卫同款形态——**降级值按本 Story VO 契约取 None**（DocumentNode.page: int|None），非 6-5b `CitationEntry.page` 的 0 值语义——防复刻漂移注记；**S4 预置钦定=1 stage 2 chunk（1 干净+1 脏）**——DR3-6）

### AC-4: 多 run 叠加判别与截断对照（6.4-DF3 清偿）

**Given** 同 plan_id 存在跨进程重跑叠加的 EVIDENCE_PACKAGE 行（同 stage ≥2 行、archived_at 不同——CLI 一次性进程模型下 482 守卫跨进程失效的产物，6.4-DF3 实证形态；验收以「同 stage 直交两行归档」构造）
**When** 构建溯源树
**Then** **stage 分组 last-write-wins**：每 stage 取 `archived_at` 最新一行采纳，**并列以 `archive_id` 决胜（`key=(archived_at or _EPOCH_FLOOR, archive_id)` 全序确定性——单键时间戳仅偏序，DR1-11）**；**None 行回落 epoch 永不获胜**（6-4 `_EPOCH_FLOOR` 同款先例——None 仅历史脏数据形态；全 None stage 采纳 epoch 行计入 adopted）（与 Redis latest 快照同构语义——最新 run 优先；6-4 升序全量与本树 last-write-wins 是同数据的两读面：审计序 vs 当前态投影），旧 run 行不产生重复 stage 节点（6.4-DF3「按 stage 过滤将现双节点」缺口的闭合形态）；evidence_refs 取采纳行
**And** `TraceabilityTree.total_archives`（**kind 过滤后的思维链候选行数**——对照信号纯化为 run 压制单现象，DR1-12）与 `adopted_archives`（判 run 后采纳行数）对照可见——run 压制丢弃面明示（6.4-DF3「静默丢弃最旧行无可见性」缺口的对照面）；查询 `limit=1000`（`ArchiveQuery` clamp 上限——树是**正确性窗口**非 6-5b 引文展示窗口 64（`_CITATION_QUERY_LIMIT` 语义面不同）：每 run 8 行需 125 次重跑触顶；**total==1000 即饱和探针——截断弱可观测注记**，禁虚假「可观测」声明，DR1-12）
**And** 非思维链归档行（`decision_basis["kind"] != CHAIN_ARCHIVE_KIND`——同 plan 的 EVIDENCE_PACKAGE 行中 kind 非思维链者；查询已按 archive_type=EVIDENCE_PACKAGE 过滤、其他 ArchiveType 行不进结果集——S6 构造形态注记：直交一行 kind 非链的 EVIDENCE_PACKAGE 行，DR1-12）不进树且不计 total（kind 过滤——`CHAIN_ARCHIVE_KIND` 常量消费，6-5b 收集段同款）

**验证标准/Validation Criteria:**
- [x] 同 stage 两行（**同 stage 连续两次直交归档**——archived_at 由服务自动 `datetime.now(UTC)` 生成、签名不可外传（`strategic_archive_service.py:107-118` 实证），两次直交含 PG 往返毫秒级间隔、Linux µs 分辨率下稳定非并列；新旧行以 `_make_material(stage, index=i)` 生成的不同 evidence_refs chunk_id 为判别锚，DR1-4；**行型钦定 gap 型**（input_summary 判别链最短——DR3-11））→ 树中该 stage 恰一节点 + **summary+tools_used（+reflection_excerpt）取新行值级断言**（判别锚——旧行值不同以区分；StageNode 无 chain 键——chain 派生键承载，DR3-11）+ adopted==3/total==4 对照值级断言（预置形态钦定：3 stage 各一行 + 第 4 行为某 stage 旧行——4 行全思维链）
- [x] kind 过滤：混入非思维链行（EVIDENCE_PACKAGE 且 kind≠CHAIN_ARCHIVE_KIND）→ 不进树且 total==3（kind 口径值级断言，DR1-12）
- [x] adopted/total 键恒在（空时为 0——键恒在纪律，6-2 R1-6 七键契约同族）

### AC-5: 降级链路三态两层承载与空计划幂等读

**Given** 归档链中 evidence_refs 含失效引用（Qdrant 点已删——point_missing；或 PG 文档行已删——document_missing），或 plan_id 零归档行
**When** 构建溯源树
**Then** **链路降级三态两层承载**（`CitationEntry.VALID_STATUSES` 同款值域——chunk 层两值/document 层两值，DR2-10）：`get_point` 返 None → ChunkNode.status="point_missing"（children 空）；point 在而 `document_repository.find` 返 None → DocumentNode.status="document_missing"（filename 等降空值）；正常 → "resolved"——**树整体不因单点失效失败**（6-5b「引文是增强面非阻断面」哲学的树形版）
**And** 单依赖异常（get_point/find 抛出）按节点捕获降级（该 chunk/status 走 missing 分支 + warning 日志），**query_archive 顶层异常** → 空树降级 + **`build_degraded=True`**（`TraceabilityTree` 第 7 键——与「plan 真无归档」的空树（build_degraded=False, total=0）显式分立，不抛异常；6-5b「query_archive 异常降级空附录 C」同构但本 Story 树是唯一产物——**空结果必须自我解释是「没有数据」还是「拿不到数据」**，顶层失败可观测，DR1-9）；**`degraded_stages`** = 含 ≥1 非 resolved 后代节点的采纳 stage 值元组（stage 级降级上卷——节点 status 的树级汇总面，升序去重，正常空元组——DR1-9）
**And** 零归档行 plan（空计划）→ 仅根节点空树（adopted=0/total=0/**build_degraded=False**）**不抛异常**（幂等读语义——6-4 `ChainOfThoughtTraceView`「空档案返回 total=0 不抛异常」docstring 钦定先例；与 6-6 AC-1「空 plan 返回空清单不抛 480——清单是枚举面非单点面」语义分立同款）；畸形 plan_id（非 UUID）→ 242（用例层守卫——`GetBlmChainTraceUseCase` 直系先例）

**验证标准/Validation Criteria:**
- [x] point_missing/document_missing **两态各一专属断言段**（S7=单场景单 plan、两 stage 各带一失效引用——status 值级 + 树整体正常返回 + degraded_stages==(stage_a, stage_b) 升序值级断言（stage 命名保升序判别力）+ **resolved/(resolved+missing) 占比值级断言**（如 2/4——AC-7 VC 降级统计可观测的落位锚，DR3-3/DR3-5））
- [x] 空计划空树（键恒在 + 零异常 + build_degraded==False）
- [x] 畸形 plan_id → 242（code 值级断言——编程面 `pytest.raises` 形态；CLI stderr 形态归 AC-6/S10，DR1-15）

### AC-6: CLI `trace-tree` 命令（分析视入口）

**Given** 归档链在位
**When** 执行 `sisys-agent trace-tree --plan-id <uuid> [--depth {1,2,3,4}] [--stage <stage>]`
**Then** 树形层级输出（缩进表达四层——每层两级空格缩进 + 层级标签前缀「结论/分析/切片/文档」；纯标准库打印形态——6-6 `checkpoint-list` 表格「输出即契约」同哲学；**行序=root.children 流程规范序**（DR3-1））：结论层（plan summary 首行）、分析层每 stage 一行（stage/display_name/degraded 标记/evidence_count）、切片层每 chunk 一行（chunk_id 前 8 位/content_excerpt 60 字符/**page=ChunkNode.page_start**——DR3-7）、文档层每文档一行（filename/page/对象键）
**And** `--stage` 客户端过滤（**按 `--depth` 构建后**客户端过滤展示——depth×stage 组合语义钦定：过滤作用于 depth 构建结果（DR1-15）；**过滤保留结论层行**（「其余 stage 零输出」仅指分析层以下——DR3-7）；服务端不支持 stage 过滤参数，YAGNI：全树 ≤8 stage 量级；epics/UX 无服务端过滤需求）；`--depth` 默认 4（全树）透传端口（**runner 签名钦定 `_run_trace_tree_cli(plan_id: str, depth: str, stage: str | None) -> int`**——原始字符串入参（checkpoint-show :1275 样板同构）+runner 内 `int(depth)` 转换——DR3-7）
**And** 退出语义：正常 exit 0（含空树——空树是正常态非错误，AC-5 语义；**空树输出三分化（R1-F3）**：build_degraded=True 时打「⚠ 归档查询失败（已降级）」、total==0 打「该 plan 无归档行」提示、total>0 无分析层节点打「归档对照: 采纳 X / 候选 Y（无分析层节点——depth 折叠或 stage 越域）」——DR1-9 读模型诚实性：空结果自我解释是「没有数据」「拿不到数据」还是「有数据未展开」）；畸形 plan_id → exit 1 + stderr `[EXCEPTION_242]`（6-3 R1-F18 前缀统一先例）；**CLI 面越域 depth 由 argparse choices 拦截 exit 2 不走 242**（分工钦定见 API 契约节——DR1-1：R1-1 修复只达 VC 未达正文，本行补齐）
**And** 本 Story CLI 面无角色门槛（「分析师」是 UX 语义——3-8/3-6 查询端点先例仅 Bearer 认证无角色检查，`interface-design.md:2006` 分析师视图是 Web 面；RBAC 门槛归 7-2 REST 入口立项时评估——注记落档）

**验证标准/Validation Criteria:**
- [x] 树形输出断言：层级标签行精确匹配 + 至少一行 chunk 前 8 位值级 + 文档行 filename 值级（CLI 单测承载完整覆盖；验收场景经 CLI in-process 直调保红——6-6 S2/S8 双清先例）
- [x] `--stage` 过滤：仅展示指定 stage 层（其余 stage 零输出断言）
- [x] 242 stderr 形态 + exit code 分工（畸形 plan_id → `[EXCEPTION_242]` stderr + exit 1；`--depth 0`（CLI 面）→ argparse choices 拦截 exit 2 **不走 242**——AC-6/API 契约节钦定分工；depth 越域 242 归编程面用例单测承载（0 与 5 双边界——AC-2 VC））

### AC-7: 性能与解析成功率（三段口径——OD-7）

**Given** 归档链在位（多 stage + 多 chunk，服务面已预热）
**When** 采样计时（20 轮——`sorted(durations)[ceil(0.95*n)-1]` 数学口径，6-3 AC-8/6-6 AC-6 同款公式与模块级期望常量独立构造）
**Then** **溯源树加载 P95<300ms**（epics L2371）：口径 = `build_trace_tree` 服务面窗口（query_archive + get_point×N + find×M 去重后——串行循环，6-5b 引文链同款串行先例（串行 YAGNI：~35 点查×毫秒级 + M 次 find（每次一次会话 checkout——6.5b-DF4）≈100-200ms 余量成立；**触发器注记**：P95 逼近门禁或 evidence_refs 契约上限放开时改 gather——落 docstring；**get_point 不做跨 stage 调用级去重**：树语义节点每路径独立，与 find 去重分立是刻意取舍，DR1-23）；N≤40（8 stage×5 chunk——写侧现行上界 `_MAX_EVIDENCE_TEXTS=5`/步（`blm_planning_service.py:95`）；归档契约对单行 evidence_refs 长度**不设上限**（6-5b `:74` 注）——N≤40 是经验锚非契约、超限线性退化不炸，DR1-23）、M≤N 去重后——点查 id 直查毫秒级，实测锚定）
**And** **「Bounding Box 跳转响应<300ms」以跳转载荷组装口径承载**（epics L2372 的 CLI 形态等价改写——OD-7 口径差声明）：跳转载荷已在树内组装（depth=4 窗口覆盖），无独立跳转运行时（Web 点击跳转归 6-8——届时 Web 侧计时归其 Story）；断言形态 = depth=4 全树窗口（含载荷组装）<300ms 即覆盖
**And** **溯源定位准确率≥95%**（epics L2373）以**解析成功率口径**承载：预置数据全解析场景 resolved 节点占比 ==100%≥95%（树节点 status 统计——resolved/(resolved+missing)）；真值口径（人工抽检坐标正确性，prd L373「随机抽样 1000 次验证」）归部署验证（6.1-DF1 同族口径差声明——Fake/预置数据无真值面）
**And** 空树/depth=2 窗口天然远小于门禁（懒加载语义的性能证明——不做独立断言，depth 窗口对照注记落 docstring）

**验证标准/Validation Criteria:**
- [x] 20 轮采样 P95<300ms（预检服务可达 + 预热含首次 load——R8-F5 注记继承）
- [x] resolved 占比 100% 断言（预置全可解析数据）+ 混入失效引用后占比值级断言（**落位 S7**（resolved/(resolved+missing) 节点统计——DR3-3））
- [x] 口径差三声明（跳转载荷/真值/懒加载）落验收 docstring

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **零新增领域事件、零事件发布调用**（本 Story 钦定——OD-2）：纯查询展示面零状态变更——「查询不发布事件」architecture.md:1293 成文 + 6-6 OD-2（**零新增领域事件**——CheckpointRecovered 为既有登记键首激活非新增，精确转述 DR1-21）/6-4 OD-6/6-5a OD-6 零发布查询面先例——**查询型故事零事件先例族**；`configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` **零 diff**；`_FROZEN_EVENT_COUNT=56` 冻结键数基线零变化（`tests/contracts/test_event_channel_mapping_pdf_report.py:23-24`——Task 4 守护复跑）；蓝图无溯源树事件定义（or.md L240/L344 溯源树语义无事件载体——读侧聚合非状态变更）
- [x] 守护承载：Task 4 复跑 `_FROZEN_EVENT_COUNT=56` 断言（零新增=登记数不变）；架构验证器 B 含「树服务零 publish 调用」源码断言（grep `publish` 于服务文件——6-6「发布点守护」的零发布变体；字母口径对齐 Task 6.2/OD-2——DR1-15）

#### 数据模型 (Data Models)

**零领域层改动**（无新领域实体/值对象/事件/异常/纯函数——树 VO 是应用层读侧 DTO；6-6「应用层 VO 落 ports 文件」先例 + 6-5b `CitationEntry` 是报告域特例对照）：

- [x] **新增应用层 VO 五个**（全部 frozen dataclass，落 `src/application/ports/traceability_tree.py` 新文件——Task 0 冻结唯一版本，键集 exact set 断言锚）：
  - `TraceabilityTree`（**7 键**）：`plan_id`(str)/`root`(`ConclusionNode`)/`adopted_archives`(int——判 run 后采纳行数)/`total_archives`(int——kind 过滤后思维链候选行数)/`degraded_stages`(tuple[str,...]——含 ≥1 非 resolved 后代节点的采纳 stage 值元组，升序去重，正常空元组——DR1-9)/`build_degraded`(bool——query_archive 顶层异常降级标记：空树与真空树分立哨兵——DR1-9)/`generated_at`(isoformat str——服务层 datetime→isoformat 转换，6-6 `CheckpointSummaryView.timestamp` 同款转换纪律)
  - `ConclusionNode`（**5 键**）：`plan_id`(str)/`title`(str——恒「BLM 战略规划溯源」固定文案)/`summary`(str——synthesis conclusions 联展，缺失降空串)/`stage_count`(int——分析层 StageNode 节点数（全 run=7——synthesis 不入分析层，DR1-13）)/`children`(tuple[`StageNode`,...])
  - `StageNode`（**9 键**）：`stage`(str——分析层七值（STAGE_VALUE_DOMAIN 八值去 synthesis——DR1-13）)/`display_name`(str——**三源拼装**：`PERFORMANCE_GAP_CONFIG`（:162）+`MARKET_INSIGHT_STEP_CONFIG` dict（:172，六子）+synthesis 归结论层（无单一映射表——Task 0.2 钉拼装形态，DR1-22）)/`summary`(str——**中间结论，三型分支钉死（DR1-14）**：六子型 payload{summary,findings} 取 summary；gap 型 payload 六键（financial_gap/operational_gap/root_causes/portfolio_health/degraded/degrade_reason）**无 summary**→降 `chain.input_summary`；payload 解析失败（非 JSON/非 dict）→同降)/`degraded`(bool——取 `decision_basis["degraded"]` 顶层布尔)/`degrade_reason`(str——取 `json.loads(chain.final_answer)` payload 的 `degrade_reason` 键缺省空串（gap 六键与六子降级信封{degraded,degrade_reason}含此键；六子正常形态{summary,findings}无则空串——与 degraded 布尔独立取值，DR1-14）)/`tools_used`(tuple[str,...]——取 `chain["tools_used"]`（assumptions 同名双写，单源取 chain；**.get 缺省空元组**——脏行兜底不抛，DR3-4）)/`reflection_excerpt`(str——取 `chain["reflection"]` 前 200 字符（**.get 缺省空串**——DR3-4）——**源键名是 reflection 非 reflection_excerpt**，DR1-14)/`evidence_count`(int)/`children`(tuple[`ChunkNode`,...])
  - `ChunkNode`（**6 键**）：`chunk_id`(str)/`content_excerpt`(str——300 字符截断)/`page_start`(int|None)/`page_end`(int|None)（两页码键取 Qdrant payload 扩键 page_start/page_end——Task 1 通道；point_missing 态为 None，DR1-23)/`status`(str——值域 "resolved"/"point_missing"——`CitationEntry.VALID_STATUSES` 三值中去掉 document_missing（该态归 DocumentNode——链路三态两层承载)/`children`(tuple[`DocumentNode`,...])
  - `DocumentNode`（**9 键**）：`document_id`(str)/`filename`(str)/`version`(int)/`page`(int|None)/`object_key`(str|None)/`bucket`(str——恒 "raw-documents")/`bbox`(dict|None——payload 透传，现状恒 None；**frozen 纪律例外显式化**：构造时 `types.MappingProxyType` 包裹防 dict 原地突变——DR1-23)/`status`(str——"resolved"/"document_missing")/`jump_ready`(bool——跳转载荷六键齐备判定：object_key 非空且 page 非 None；「30 秒溯源」可达性的节点级布尔面)
- [x] **语义注记**（Task 0 钉死）：树形嵌套 VO 中 chunk 在不同 stage 下重复出现（每条 stage→chunk 路径独立——6-5b 引文去重保序是 flat 表语义，树形不做跨 stage 去重；文档查询去重仅指 find 调用次数（AC-1），节点形态仍嵌套）；`jump_ready` 是读侧派生布尔非持久面（**半跳转语义由 object_key 非 None 直接判别（文档级）——不建 partial 三值枚举（对已暴露六键的冗余派生，YAGNI）——论证落 docstring**，DR1-23）；synthesis 行不产生 StageNode（结论层即其呈现位——conclusions 联展即根 summary，DR1-13）

#### 统一端口定义注册与管理 (Port Contract)

- [x] **新增应用层端口 1 个**（v1.0.0）：`TraceabilityTreePort`（`src/application/ports/traceability_tree.py`）单方法：
  - `async def build_trace_tree(*, plan_id: str, depth: int = 4) -> TraceabilityTree`（**async 协程钦定**——三依赖 query_archive/get_point/find 全 async（D1 实证），同步签名物理不可实现，DR1-10；depth 值域 {1,2,3,4} 默认 4——越域守卫归用例层 242（服务层不重复守卫——6-6 list_checkpoints 服务层无 UUID 守卫先例一致）；单标识查找直接参数形态——端口查询参数决策规则「单字段标识查找→直接参数」；**无 Query Object**（非多字段组合分页——ArchiveQuery/DocumentQuery 既有 Query VO 复用不动）
- [x] **新增应用服务与用例**：
  - `TraceabilityTreeService`（`src/application/services/traceability_tree_service.py` 新文件）：四段编排（①收集 `strategic_archive_service.query_archive(ArchiveQuery(plan_id, archive_type=EVIDENCE_PACKAGE, limit=1000))` → kind 过滤 → ②判 run stage 分组 last-write-wins + 结论层 synthesis 提取 → ③depth≥3 切片解析 `l3_vector.get_point(collection, chunk_id)` 逐个 + 去重文档清单 → ④depth=4 文档解析 `document_repository.find(DocumentQuery(tenant_id, document_id))` 去重缓存 + chunks page 匹配 + 跳转载荷组装；全方法 async）；构造注入 `strategic_archive_service`/`l3_vector`/`document_repository` 三依赖（**strategic_archive_service 是具体应用类注入——仓内无 `StrategicArchiveServicePort`（组合根 interface 面即具体类 `StrategicArchiveService`，6-5b `pdf_report_generation_service.py:42/:119` 先例；单测 `AsyncMock(spec=StrategicArchiveService)` 可行——spec 不调 `__init__`、async 方法自动子 mock，DR1-8）**）+ `search_collection: str = "documents"`（组合根 env 传导——`BLM_SEARCH_COLLECTION` 单源，6-1 组合根 :1592 先例；**合流形态注记**：构造默认值（6-5b 形态）+env 传导（6-1 形态）——无完全同构先例、可行性实证，DR1-18）+ `tenant_id: str = str(MVP_TENANT_ID)`（6-5b 构造注入先例——数据链无租户可用，单租户口径）
  - `GetTraceabilityTreeUseCase`（`src/application/use_cases/get_traceability_tree.py` 新文件）：plan_id UUID 守卫 242 + depth 值域守卫 242 + 透传（`GetBlmChainTraceUseCase` 直系粒度——薄透传+双守卫；`async def execute`——直系先例同构，DR1-10）
- [x] **既有端口零改动复用清单**：`StrategicArchiveService`（**具体应用类**——query_archive 既有方法只读消费，DR1-8）/`L3VectorPort`（get_point）/`DocumentRepositoryPort`（find+DocumentQuery）/`ChainOfThoughtArchiveServicePort`（零触碰——树服务不经此端口，直读 query_archive 通道，6-5b 同款）/`TraceabilityPort`（3-8——零触碰，语义正交）
- [x] **ingestion 演进 1 处**（Task 1 承载）：`chunk_indexing_handler.py` payload 6→8 键（+page_start/page_end）——handler 无端口变更（内部 payload 构造，ChunkIndexingHandler 注册 spec 零变化）
- [x] 组合根注册 2 个新块：`traceability_tree_service`（SINGLETON——无状态聚合读服务；lambda 注入三 resolve + env collection/tenant 参数）/`traceability_tree_use_case`（SINGLETON 无状态透传——6-6 用例注册形态同构）；**既有注册行零删改**（Task 4 diff 审计）
- [x] 端口契约清单（唯一事实源——禁止语义重复新增）：

| 端口 | 层 | 注册名（composition_root） | 本 Story 动作 |
|---|---|---|---|
| `TraceabilityTreePort` | application/ports | `traceability_tree_service`（新增） | 新增 v1.0.0 + 契约测试 |
| `GetTraceabilityTreeUseCase` | application/use_cases | `traceability_tree_use_case`（新增） | 新增 + resolve 可达测试 |
| `StrategicArchiveService`（具体应用类——**仓内无同名 Port**，DR1-8） | application/services | `strategic_archive_service`（:2216 既有，SCOPED） | 复用零改动（query_archive 只读消费） |
| `L3VectorPort` | domain/ports | `l3_vector`（:363 既有） | 复用零改动（get_point） |
| `DocumentRepositoryPort` | domain/ports | `document_repository`（:1176 既有） | 复用零改动（find） |
| `ChainOfThoughtArchiveServicePort` | application/ports | `chain_of_thought_archive_service`（:2364 既有） | 零触碰（树服务不经此端口——复用清单一致性补行，DR1-8） |
| `ChunkIndexingHandler` | application/event_handlers | `chunk_indexing_handler`（:1980 既有） | **payload 构造扩键**（spec 零变化——内部实现演进） |
| `TraceabilityPort`（3-8） | domain/ports | `traceability_service`（:2000 既有） | 复用零触碰（语义正交——OD-1） |

#### 端口契约清单执行约束（强制）

- [x] 本清单是唯一事实源（Single Source of Truth）；实现中确需新端口时回 Task 0 补登记 + Contract Gate + 契约测试，禁止边写边加
- [x] 禁止在服务文件中本地定义 Protocol / Port 抽象（6-1~6-6 纪律沿袭）
- [x] 禁止绕过 `StrategicArchiveService` 直持 PG 会话读归档（读档=经既有服务）；禁止绕过 `L3VectorPort`/`DocumentRepositoryPort` 直连 Qdrant/PG；**禁止绕过 `L3VectorPort` 用裸 Qdrant client 预置/查询**（点 id 经 `_normalize_point_id` MD5 归一在 infra 层读写对称闭环——裸 client 原始 id 直写会被 get_point 漏查，6-5b 已踩坑；`point["id"]` 是 MD5 整数、chunk_id 原文以 `payload["chunk_id"]` 为准——DR1-3 防御注记）
- [x] 禁止演进 `ChainOfThoughtArchiveServicePort`（6-4 冻结面——evidence_refs 读取经 query_archive 通道，不动 6-4 端口方法族与其 call_order 断言族）

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> 完整检查清单详见 [`sisys-uni-exception-design.md §3.12`](../../docs/architecture/sisys-uni-exception-design.md)；编码分配策略详见 §3.3。

- [x] **零新增领域异常、零既有异常改动**（本 Story 钦定——OD-3）：
  - **畸形输入 242 复用**：`EntityValidationError`（plan_id 非 UUID/depth 越域）——用例层守卫，`GetBlmChainTraceUseCase` UUID 守卫直系先例
  - **空计划不抛异常**（幂等读——6-4 `ChainOfThoughtTraceView` docstring 钦定先例 + 6-6 空清单先例）：枚举面/树面返回空态非异常态
  - **依赖失效走节点降级**（point_missing/document_missing——status 值域承载，非异常路径）+ **顶层 query_archive 异常空树降级 + build_degraded=True**（6-5b 整体容错边界同构；空树与真空树分立——顶层失败可观测）——**异常语义纯度**：失败可观测（status/jump_ready/total/build_degraded 四对照面）而非 raise
  - **traceability 段 372-379 空位维持预留**（`_code_ranges.py` traceability (370,379) 段现仅占 370/371——本 Story 零取码；「树构建失败」类异常语义经降级承载后无真实触发面——YAGNI）
  - **无 404 语义面**：空树即「不存在」的语义承载（6-6 AC-1「清单是枚举面非单点面」语义分立先例——树是 plan 级枚举面）
- [x] **Story 异常契约文档**：本节即小节（复用码 242 单码 + 触发场景 + 守卫层位）
- [x] 异常路径 Gherkin 场景纳入 Edge Cases（AC-5/AC-6 场景钉死）

#### API 契约 (API Contract)

- [x] **零 REST API 变更**（BLM/溯源树面 REST 接线归 7-2——6.1-DF5 先例第六次沿袭；interface-design.md:1406 `GET /documents/{id}/trace` P0 端点归 Epic 7 API 入口立项）；`docs/api/openapi.yaml` **零 diff**（契约测试守护——6-5a/6-5b 同款）
- [x] CLI 新增子命令 **1 个**（argparse 扁平子命令族——`add_parser` 块 + `main()` 分发分支 + `_run_trace_tree_cli` 五步定式函数，`_run_checkpoint_show_cli` 直系样板（DomainError `[code]` exit 1）；现存子命令扁平族（`add_parser` 全量清单以 grep 为准）无重名——`trace-tree` 全仓零占用实证）：
  - `trace-tree --plan-id <uuid> [--depth {1,2,3,4}] [--stage <stage>]`：树形缩进输出（四层标签前缀「结论/分析/切片/文档」+ 两空格逐层缩进——纯标准库 print 形态，输出即契约）；`--depth` choices 拦截（argparse 层）+ 服务端用例层守卫双落位（直接编程调用面归用例守卫——同 6-6 `--mode` choices+RecoveryMode 双层先例；**choices 用 str 元组（"1"~"4"）+ int 转换后传端口**——仓内 choices 先例均 str 元组（--format :353/--mode :503），DR1-22）；`--stage` 客户端过滤（AC-6）；CLI 面既有合规形态 = 直 import application.ports（VO/Protocol）+ `resolve("traceability_tree_use_case")` 字符串取用例——**禁在 CLI 顶部 import 用例类/服务类**（仓内无此先例，DR1-21）；**domain 异常 import 不在禁列**（checkpoint-show CLI 层 UUID 守卫先例 :1285-1294 需 EntityValidationError——trace-tree 同款 CLI 层守卫+用例层守卫双防线，两路径输出同 `[EXCEPTION_242]` stderr+exit 1 形态，S10 断言不区分——DR2-10）
  - exit 0 口径：树构建完成（含空树——空树是正常态）；exit 1=DomainError `[code] {message}` stderr；exit 2=argparse 用法错误（缺参/choices 越域由 argparse 拦截——`--depth 5` argparse choices 直接 exit 2，编程面越域才走 242——**缺参与守卫分工**钦定：argparse 可拦截的形态（choices 枚举）归 argparse exit 2，语义守卫（UUID 解析）归 242）
- [x] CLI 参数守卫前缀统一：`[EXCEPTION_xxx]` 形态（6-3 R1-F18 真实异常构造纪律——禁字面前缀）

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
- **本 Story 特别注意**：**本 Story 零 domain 层改动**（无新实体/VO/事件/异常——树 VO 全部在 application/ports；`CitationEntry` 是 6-5b domain VO 对照先例非本 Story 面）；**唯一 infrastructure 零改动核验**：payload 扩键在 application/event_handlers（handler 是应用层事件处理器——非 infrastructure）；零新存储设施/零 migration

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

> 注：上表是模板通用四层定义；本 Story 的 CLI 入口落位 `src/entrypoints/agent_cli.py`（entrypoints 组装层——D1 方案 A，与项目结构节/Task 6.3 口径一致），interfaces 行非本 Story 落位声明（DR1-23）。

**设计规则 R1~R4 落点**（用户钦定）：
- **R1** 领域层统一抽象基础端口 → 复用 `L3VectorPort`/`DocumentRepositoryPort`/`ArchiveQuery`（本 Story 零新增基础端口）
- **R2** 应用层端口组合注入基础端口 → `TraceabilityTreePort` 组合注入三既有依赖（兄弟应用服务 `StrategicArchiveService` + 两基础端口 L3VectorPort/DocumentRepositoryPort——如实表述，DR1-8；6-5b `PdfReportGenerationService` 九依赖组合先例的同族轻量版）
- **R3** 基础设施层实现端口并管理技术 → 复用 QdrantAdapter/PostgreSQLDocumentRepository/PostgreSQLArchiveRepository **全部零改动**（本 Story 是纯读侧聚合——零 infra 改动 Story，6-6 OD-12 同款）
- **R4** 接口层适配外部请求 → CLI `trace-tree` 子命令（agent_cli.py 既有五步定式）；无 REST 面

#### 验收标准 Gherkin (Acceptance Tests)

- [x] 功能测试文件：`tests/acceptance/test_acceptance_traceability_tree.feature`（OD-9 命名——traceability_tree 功能名族，禁故事编号后缀；与 3-8 既有 `test_acceptance_traceability.*` 文件名区分）
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_traceability_tree.py`
- [x] 业务方评审通过
- [x] 所有场景覆盖（Happy Path + Edge Cases）——钉死 **12 场景**（AC-1×2 / AC-2×1 / AC-3×1 / AC-4×2 / AC-5×2 / AC-6×2 / AC-7×1 / 收尾×1，Task 0.4 定稿钉死确定值并全文同步，禁范围值进入后续 Task）；**epics 架构测试三项落位对账**（epics L2366-2368）：溯源树结构测试→S1/S2、交互式展开测试→S3、Bounding Box 跳转测试→S4（跳转载荷组装口径——OD-7 显式对账）——功能等价重分布（6-6 OD-5 先例）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（模块级 `event_loop` fixture + `_run_async` helper——6-x 三件套）
- 同一中文文本可能需要同时支持 given/when 装饰器（共用文本按模块各自重新定义一份 @given——6-x 样板实证形态）
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——本 Story 异常面窄化（242 单码——OD-3）：畸形 plan_id 242 入 S8（畸形腿）；CLI 242 stderr 形态入 S10；depth 越域 242 **归用例单测矩阵承载**（编程面 0 与 5 双边界——CLI 面由 argparse choices 拦截 exit 2 不走 242，AC-6/API 契约节分工钦定）；其余「失效」走 status 降级（S7）非异常路径——**epics 模板「404/403/409」资源端点三例外码注记**：本 Story 无 REST 资源端点（CLI-only——OD-1），空态走幂等读（AC-5）非 404；403/409 无触发面（无角色门槛无状态变更——注记落 Task 0.4）
- **R6 模板合规**：feature/py 组织结构对齐 `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`/`.py`——`# language: zh-CN` 中文 Gherkin + AC 横幅注释分组（`# ===` 分隔）+ `@scenario(...)` 多行字面量路径绑定 + **12 场景全绑定**（R6 自身仅绑定 30 场景中 17 个属旧模板欠账，新文件禁沿用）；pytestmark/context dict/`_run_async` 三件套基建承载；**断言必须真实**（禁 then-pass 占位）；装配形态对齐 6-5b（数据面三预置通道：归档行直交 + Qdrant 点预置 + PG documents 行预置——6-5b S4 引文预置形态直系复刻；**本 Story 验收装配面零 LLM 零 Embedding**（集成场景④ Fake-embedding 豁免——DR1-7；纯读侧聚合无生成调用——与 6-3~6-6 创建链前置的根本差异），装配成本更低）
- **场景分化维度表（Task 0.4 钉死输入——含收尾共 12 场景全枚举 S1~S12；S 编号为 6-7 自有编号，跨故事引用一律带故事号前缀）**：S1（AC-1）= 全树四层落位（2 stage 各 1 chunk 同一 document_id 预置——DR3-6→四层节点/键集/值级断言+root.children 流程规范序断言）；S2（AC-1）= 结论层双形态（synthesis 行在位取 conclusions 联展 + 仅 performance_gap 降级空串——AC-1 VC 落位；**双形态各钉 stage_count 值级**（DR1-13 后 synthesis 不入分析层：synthesis-only 预置=0、synthesis+gap 预置=1、gap-only 预置=1——Task 0.4 钉死预置形态与期望值，DR2-10））；S3（AC-2）= depth 懒加载三档（depth=2 树形断言 StageNode.children==() + depth=3 切片在位且零 DocumentNode + depth=4 全树——单场景三断言段；**真实服务无调用记录面——call_order 零调用断言归 Task 2 单测矩阵（四档含 depth=1 root.children==() 退化）**，DR1-5）；S4（AC-3）= 跳转载荷（1 stage 2 chunk——1 干净+1 脏（DR3-6）→六键值级 + bbox 透传 + page 脏形态降 None）；S5（AC-4）= 多 run 叠加判别（同 stage 连续两次直交→最新行采纳值级（index 区分 chunk_id 判别锚——DR1-4）+ adopted==3/total==4 对照）；S6（AC-4）= kind 过滤（非思维链行不进树且 total==3——DR1-12）；S7（AC-5）= 降级链路三态两层承载（单场景单 plan、两 stage 各带一失效引用——point_missing + document_missing 双断言段 + degraded_stages==(stage_a, stage_b) 升序值级 + resolved 占比统计值级——DR3-3/DR3-5）；S8（AC-5）= 空计划空树+畸形 242（幂等读（build_degraded==False）+ UUID 守卫——空树腿编程面/畸形腿两形态）；S9（AC-6）= CLI 树形输出（四层标签+值级行——行序=流程规范序 DR3-1）；S10（AC-6）= CLI `--stage` 过滤+242 stderr（过滤面（保留结论层行——DR3-7）+ 畸形退出形态）；S11（AC-7）= 性能采样（20 轮 P95<300ms + resolved 占比 100%）；S12（收尾）= src 与四测试目录完成清单存在性断言（**断言对象=File List 的 src/测试 15 项存在性；两 md 台账（deferred-work/sprint-status）与故事文件不入断言面**——修改性断言物理不可写，Task 0.7/7.5 操作面承载，DR3-10）
- **逐场景调用面矩阵（Task 0.5 钦定）**：S1~S8（S8 空树腿）+S11 = **编程面**（服务/用例直调——断言锚树 VO 在编程面单源可达；call_order 断言归单测，见 S3）；S9/S10 = **CLI 面 in-process 直调** `_run_trace_tree_cli`（CLI-only 输出面必须驱动 CLI；**每次 CLI 直调前 `get_resolver().clear_singleton()` + `clear_scoped()` 双清钦定 + monkeypatch `BLM_SEARCH_COLLECTION=<测试 collection>`**——双清=6-6 R3-1 纪律 + `test_acceptance_markdown_report.py:144-148` 先例；**collection 桥接=DR1-6 钦定**：组合根 lambda 在 resolve 实例化时读 env（注册在 bootstrap、取值在实例化——机制可行），不 patch 则 CLI 查默认 "documents" 找不到预置点假 point_missing；**禁重新 bootstrap**——`_ensure_bootstrapped` 自动短路）；S8 畸形腿=编程面（242 用例守卫单源）；**CLI 交互面的完整参数/输出覆盖由 `tests/unit/interfaces/cli/test_agent_cli.py` 承载**（验收只覆盖 S9/S10 关键路径 CLI 形态）；S12 收尾=文件存在性断言，无服务调用面
- **pytestmark**：显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.database, pytest.mark.redis, pytest.mark.qdrant, pytest.mark.xdist_group("blm-planning-perf")]`（**无 minio marker**——本 Story 零 MinIO 依赖（读侧不触 L4——object_key 是 PG 元数据字符串非对象取用）；redis marker 保留理由=装配链 bootstrap/组合根 resolve 的连接池依赖（`tests/conftest.py` `_bootstrap_once` session autouse）；marker 名以 pyproject 注册为准；xdist_group 整模块——与 6-x 验收+集成同组串行）；服务不可达环境 `pytest.skip()` 动态跳过（禁 `@pytest.mark.skip` 写死）
- **数据面预置纪律**：归档行经 `StrategicArchiveService`（**全 None 依赖构造**——`StrategicArchiveService(archive_repo=resolve("archive_repository"), embedding_service=None, vector_storage=None, object_storage=None, graph_storage=None, event_publisher=None, staleness_service=None)` 纯 L2 预置，archive_plan 对 None 依赖各步优雅跳过实证——**勿照抄 6-4 轻装配的 Fake embedding+真实 MinIO 形态**（会引入 L4 依赖与 minio marker 面），DR1-7）`archive_plan` 直交（无 LLM）；archived_at 由服务自动生成不可外传——多 run 先后=同 stage 连续两次直交（自动 now 微秒差稳定非并列，DR1-4）；Qdrant 点经 `l3_vector.upsert_points` 预置（payload 8 业务键——**扩键后形态**，含 page_start/page_end——同时兼作 Task 1 扩键的验收级回归面；**Qdrant 实存第 9 键 created_at**（infra upsert 追加——`vector_storage.py:85`）——读回断言用 8 业务键值级 + created_at 存在不计数，**禁 9 键 exact set 误断言**，DR1-3；vector 用字面量 `[0.1]*1024`——非 embedding、维度对齐适配器校验；独立 collection 需先 `create_collection(size=1024)`（6-5b `_ensure_citation_collection` :655-671 样板））；PG documents 行经**原生 SQL INSERT 定向预置**（6-5b `:905-935` 样板直系复刻——非 document_repository（6-5b 实况通道，DR1-16）；metadata 需含 **chunks+storage_object_key 两键**——jump_ready 依赖后者，缺则假 False，DR1-16）；**collection 隔离**：预置点入独立测试 collection（`TestTenant`/uuid 前缀——服务构造注入同 collection 单源 + CLI 面 monkeypatch env 桥接见调用面矩阵）；teardown：归档行按 plan_id 定向 DELETE + PG 行定向 DELETE + Qdrant collection 整删——执行序（R2-F2 对齐）（键计数净增 0 纪律——6-3 R1-F1）
- **回归面（强制）**：payload 扩键后全仓 grep 消费方测试——6-1 BLM 证据提取（payload text/content 双键——不受影响实证）/3-8 traceability（`payload.get("page_start")` 受益注记——mock 自构 payload 不受影响）/LayeredRetrieval（parent 重构 4 键不含新键——透传面无断言冲突）/chunk_indexing 既有单测集成（**零预期适配实证**——四文件（index_payload/document_tasks/document_processing_flow/arch_layered_retrieval）实测零 payload 键集 exact set 断言，扩键不打破任何既有断言；Task 1 是**新增** 8 键断言面，DR1-19）；6-4/6-5b 全部既有测试零适配（纯新增服务+handler payload 纯增键）

**Task 0 完成标志：**
- [x] 上述规范项全部定义完毕（五 VO 键契约/端口签名/零事件零异常裁定/CLI 命令/OD 裁定落档）
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证——预期失败形态 = 步骤函数运行期失败：延迟 import 抛 `ImportError`（缺失 `traceability_tree` 模块/类）或断言步 `AssertionError`；收集期零错误本身即延迟 import 纪律的自证——6-2/6-3/6-6 先例）
- [x] 规范文档通过人工评审或自动化校验
- [x] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：① 组合根新注册 resolve 可达（`traceability_tree_service`/`traceability_tree_use_case`——注入链非 None + 三依赖 resolve 真实可达）② CLI `trace-tree` 入口接线（单测用例承载）③ 树服务零事件发布守护（架构验证器 B）④ payload 扩键接线（ingestion→Qdrant 8 业务键→get_point 读回 round-trip（实存第 9 键 created_at 存在不计——DR1-3）——集成场景承载）；「已实现未接线」组件登记 deferred-work
- [x] **锚定义务五条处置落档**（Task 0.7——deferred-work 台账更新）：6.5b-DF1（半边清偿+半边 defer 注记）/6.4-DF3（清偿注记）/6-5b R4N-1（思维链全文附录维持 YAGNI 裁定——OD-10）/L170 消费基建（顺延 Epic 8 注记——纯查询面零订阅）/L17 langgraph retry-timeout（顺延注记——零图引擎/checkpoint_table 消费）

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
| **TDD 单元测试** | ingestion payload 扩键 | 8 键构造/页码透传/缺键容错（chunk dict 无 page 键——legacy chunks 降 None）/既有 6 键不变 | `tests/unit/infrastructure/workflow/test_document_tasks_index_payload.py`（Story 3.5 索引管道 payload 测试宿主——`test_handler_writes_chunk_level_payload` 断言面扩展；主会话 grep 亲验定位 2026-11-05） | Task 1 |
| **TDD 单元测试** | 树服务四段编排 | 收集 kind 过滤/判 run last-write-wins/depth 分层懒加载（get_point/find 零调用 call_order）/降级链路三态两层/去重缓存/跳转载荷组装/空树/顶层容错 | `tests/unit/application/test_traceability_tree_service.py`（新建） | Task 2 |
| **TDD 单元测试** | 用例层 | UUID/depth 双守卫 242+透传 | `tests/unit/application/use_cases/test_traceability_tree_use_case.py`（新建） | Task 3 |
| **TDD 单元测试** | CLI trace-tree | 参数解析/树形输出/`--stage` 过滤/242 stderr/exit code/五步定式 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~AC-7 全覆盖） | `test_acceptance_traceability_tree.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_traceability_tree.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约 | 新端口注册/spec 元数据（v1.0.0/SINGLETON/tags）/resolve 可达/注入链 getsource/新用例 PORT_NAMES | `tests/contracts/test_port_contract_traceability_tree.py`（新建——五断言族） | Task 3/4 |
| **SDD 架构验证** | 六边形架构约束 | 树服务落位（application 层/禁本地 Protocol）/零 publish 守护/零 domain 改动守护（本 Story diff 面核验）/CLI 接线 | `tests/unit/architecture/test_traceability_tree.py`（新建——OD-9 对 epics 钦定名 `test_provenance_tree.py` 的显式偏离） | Task 6 |
| **集成测试** | 真实链树构建 | 归档预置+Qdrant 点（8 业务键 payload——实存含 created_at）+PG 行预置→树 round-trip/多 run 判别/降级/性能采样/payload 扩键 ingestion→get_point 读回 round-trip | `tests/integration/test_integration_traceability_tree.py`（新建，OD-9） | Task 5 |
| **回归测试** | payload 扩键传播面 | 6-1 证据提取/3-8 traceability/LayeredRetrieval/chunk_indexing 既有测试全绿 | 既有测试文件（chunk_indexing **零适配预期**——四文件零键集断言实测，DR2-5；唯一新测试面=Task 1 新增 8 键断言） | Task 1/4 |
| **回归测试** | 6-4/6-5b 面 | 纯新增服务假设实证（零适配） | 6-4/6-5b 既有测试（预期零修改） | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [x] **整体覆盖率 ≥80%**（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`——**显式四目录禁裸收集**：裸 `tests/` 回落 testpaths 即挂起形态，记忆钦定；addopts 已带 --cov=src 无需重复）- **P0 阻断门禁**
- [x] **应用层覆盖率 ≥85%**（`pytest --cov=src/application` 语义——**口径注记**：addopts `--cov=src` 累积使 TOTAL 行为全 src 并集，分层百分比按报告内 application 组 per-file 行人工聚合判读，或以剥离单跑——**完整命令字面量**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/application -o addopts="--cov=src/application --cov-report=term-missing:skip-covered"`（-o 覆写剥 -n/--strict-markers——6-6 口径注记升级为字面量，DR1-17））- **P1 阻断门禁**（本 Story 主改动层——epics L2376 钦定）
- [x] **领域层覆盖率 ≥90%** 维持（本 Story 零 domain 改动——存量基线不回退即可）
- [x] **集成测试覆盖率 ≥75%**（epics 钦定——**口径钦定**：集成测试对本 Story 交付面的行覆盖，`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_traceability_tree.py --cov=src.application.services.traceability_tree_service --cov=src.application.use_cases.get_traceability_tree --cov-report=term-missing` 人工核新增方法行 ≥75%（pytest-cov 多 `--cov` 取并集——命令可跑）；**顶层容错分支（query_archive 抛出→空树）在真实服务集成无触发面——归单测承载**（口径预声明防收口争议，DR1-17）；禁「只跑集成目录+--cov=src 全量」的无意义口径——6-6 AC 口径先例）
- [x] **关键路径 100% 覆盖（枚举分支逐一有专属用例口径）**：四段编排调用序（含 kind 过滤分支/**脏 stage 读侧过滤**（DR3-4）/判 run 分支（含双 synthesis 决胜——DR3-2）/depth 四档（含 depth=1 退化——DR1-2）/降级链路三态两层（**None 返回与 Exception 抛出两分支各一腿**——DR3-9）/顶层容错分支）/CLI exit 0/1 形态（argparse exit 2 由用法错误原生承载——DR1-23）/242 双守卫/去重缓存命中与未命中

#### 代码质量门禁
- [x] **Ruff 检查通过**（`poetry run ruff check src/ tests/`——双目录）
- [x] **MyPy 类型检查通过**（`mypy src/`——当前基线 753 零错误不回退（6-6 R4 实证基线），新增面零新增错误）
- [x] **无 P0/P1 级别问题**（代码审查）
- [x] **预提交 Hooks 通过**（`pre-commit run --all-files`；push-stage 注记：validate-schemas/validate-openapi/pytest-bdd 三钩子 stages=[push]，`--all-files` 默认 commit stage 跳过——全覆盖补 `--hook-stage push` 或以逐提交 push 证据链收窄，6-3/6-6 先例）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **归档行清理** | 验收/集成 teardown **原生 SQL 定向 DELETE**（`strategic_archives` 表——`DELETE ... WHERE plan_id = ...`（或 6-5b `:731/:795` 先例：SELECT 收集 archive_id 再 `ANY(:ids)`）；预登记 plan_id 清单。**勿寻 `archive_repository.delete`——仓储与服务均无删除方法面**（save/find/find_for_update/mark_stale/list_by_plan/list_by_archive_type/count——DR2-8） | 归档行累积污染后续查询 |
| **Qdrant 点清理** | 预置 collection 测试后整 collection 删除（独立测试 collection——`TestTenant` 前缀；服务构造注入同 collection 单源——预置与读回必须同 collection，配置单源常量钉死）；**例外：集成场景④ handler 通道落共享 "documents"（`chunk_indexing_handler.py:215` 硬编码）——该场景点清理经 `L3VectorPort.delete_points` 按 chunk_id 定向点删，禁对共享 collection 整删（DR2-3）** | 点残留跨文件误命中 |
| **PG 文档行清理** | 预置 documents 行按 document_id 定向 DELETE（6-5b 预置/清理形态直系复刻） | 行累积 |
| **事务隔离** | 集成测试自包含装配类模式（真实提交+定向 DELETE——savepoint 不适用于含多存储预置链，6-3/6-4/6-5b 钦定口径） | 数据泄漏 |
| **资源唯一性** | plan_id/document_id/chunk_id 全 uuid4 独立（多 run 场景同 plan 同 stage 两行——**连续两次直交**（archived_at 服务自动生成不可外传）+ `_make_material(stage, index=i)` 不同 chunk_id 判别锚，禁 sleep 依赖——DR1-4） | ID 冲突/时序不稳定 |
| **外部服务隔离** | Redis/PG/Qdrant 真实服务探测 skip（本 Story 零 MinIO/零 LLM；Embedding 仅集成场景④ Fake 豁免（DR1-7）——探测面比 6-3~6-6 少两项） | 环境不一致 |
| **并行隔离** | xdist_group("blm-planning-perf") 整模块挂法——与 6-x 验收+集成同 worker 串行 | 跨文件执行窗口重叠 |
| **asyncio 上下文** | BDD 步骤 event_loop.run_until_complete（三件套）；集成裸 async def（asyncio_mode=auto）；性能采样场景级串行（单 loop） | 循环关闭错误 |
| **CLI 直调双清** | S9/S10 CLI in-process 直调前 `clear_singleton()`+`clear_scoped()` 双清 + monkeypatch `BLM_SEARCH_COLLECTION` 测试 collection 桥接（6-6 R3-1 钦定——SCOPED `document_repository` 缓存不随单清驱逐；`l3_vector` SCOPED 同族；DR1-6） | 跨 loop 死客户端静默失败/假 point_missing |
| **性能采样纪律** | 期望常量独立构造（300ms/占比 0.95/limit 1000 模块级字面量）；采样前预热含首次真实 load（连接池建立——R8-F5 注记继承） | 恒真/失真 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（定向 DELETE 例外已钦定——6-3 模式）
- ❌ autouse fixture 删除全局匹配资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ pytest-xdist 并行时 BDD 步骤内 asyncio.run()
- ❌ 裸 `tests/` 运行（显式四目录）
- ❌ 验收 mock（验收面全真实服务——零 LLM/零 Embedding）；集成仅场景④ Fake-embedding 豁免（AsyncMock spec EmbeddingServicePort——外部 SaaS 豁免先例，DR1-7/DR2-2）；「点已删/document 已删」两形态均用真实删除构造，非 mock 返回 None

**验证要求：**
- [x] 并行测试 `SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance -n 8` 通过（显式四目录；-n 8 为对 addopts -n auto 的有意 cap——6-3/6-5b/6-6 同款）
- [x] 连续运行无随机失败**等效证据链**（四目录全量双轮零失败+验收单文件 ≥5 轮+关键场景（S1/S7/S9/S12）场景级多轮复跑稳定——6-6 先例形态）
- [x] `poetry run ruff check` 通过
- [x] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 四层树结构+值级断言 | Task 2 | 2.1~2.6（四段编排+五 VO） | `test_traceability_tree_service.py` |
| AC-1 | 结论层双形态+全树场景 | Task 0/7 | 0.4 场景 S1/S2；7.x 收尾 | 验收 feature/py |
| AC-2 | depth 懒加载四档（验收三档+depth=1 归单测）+越域 242 | Task 2/3 | 2.x（分层解析）+3.x（用例守卫） | 验收 S3+单测 |
| AC-3 | 跳转载荷六键+bbox 透传+page 脏形态 | Task 2 | 2.x（载荷组装） | 验收 S4+单测 |
| AC-4 | 多 run 判别+adopted/total+kind 过滤 | Task 2 | 2.4~2.6（四段编排——收集与判 run） | 验收 S5/S6 |
| AC-5 | 降级链路三态两层+空树+顶层容错 | Task 2 | 2.4~2.6 | 验收 S7/S8 |
| AC-5 | 畸形 plan_id 242 | Task 3 | 3.1~3.3（用例守卫） | 验收 S8+单测 |
| AC-6 | CLI 树形输出+--stage+exit 语义 | Task 3 | 3.4~3.6 | 验收 S9/S10+CLI 单测 |
| AC-7 | P95<300ms+resolved 占比 | Task 2/5 | 2.x（窗口）+5.4（采样） | 验收 S11+集成③ |
| 全 AC | 端口契约+注入链+接线 | Task 3/4 | 3.x/4.1 | 契约测试 |
| 全 AC | payload 扩键（6.5b-DF1 半边） | Task 1 | 1.1~1.4 | 单测扩展+集成④ |
| 全 AC | 收尾清单断言 | Task 7 | 7.3 | 验收 S12（收尾场景） |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-7（全部）

> **目的：** 在进入代码实现前，明确 VO 键契约、端口契约、零事件零异常裁定、CLI 入口、验收场景与架构边界。

- [x] Subtask 0.1: 冻结数据模型规范——五 VO 键契约（TraceabilityTree **7 键**（含 build_degraded 顶层降级哨兵 + degraded_stages stage 级上卷语义——DR1-9）/ConclusionNode 5 键/StageNode 9 键/ChunkNode 6 键/DocumentNode 9 键——含 `jump_ready` 派生布尔语义与 summary/degrade_reason/reflection_excerpt 三键**数据源链**（三型 payload 分支 + chain 键名映射（源键 reflection 非 reflection_excerpt）——DR1-14）+synthesis 行不产生 StageNode 裁定（DR1-13）+summary/reflection_excerpt/content_excerpt 三截断口径（synthesis 联展/200 字符/300 字符——6-1 证据文本截断同族，`blm_planning_service.py:98`））/树形嵌套 chunk 重复语义注记/去重缓存语义（find 调用次数 vs 节点形态）
- [x] Subtask 0.2: 冻结端口契约——`async build_trace_tree(plan_id, depth=4)` 签名（**async 钦定——DR1-10**；depth 值域+守卫层位：用例层 242/argparse choices exit 2 分工/choices=str 元组+int 转换位——DR1-22）/三依赖注入面（strategic_archive_service 具体类——DR1-8）+search_collection/tenant_id 构造参数（组合根 env 传导单源）+display_name 三源拼装形态（PERFORMANCE_GAP_CONFIG+MARKET_INSIGHT_STEP_CONFIG+synthesis 归结论层——DR1-22）
- [x] Subtask 0.3: 冻结零事件零异常裁定落档（OD-2/OD-3——含 traceability 段 372-379 维持预留注记与空树幂等读语义先例引用）
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_traceability_tree.feature`（12 场景钉死：AC-1×2/AC-2×1/AC-3×1/AC-4×2/AC-5×2/AC-6×2/AC-7×1/收尾×1——AC 横幅分组+中文 Gherkin，R6 模板；epics 三项架构测试落位对账注记）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_traceability_tree.py` 骨架（docstring 场景三属性分档表/pytestmark 全套+xdist_group（无 minio marker）/12 场景全绑定/模块级期望常量独立构造/三件套/数据面三预置通道（归档直交+Qdrant 点+PG 行）+teardown 三步链（归档行/Qdrant collection/PG 行——各步独立 try/except）/CLI 直调双清契约/延迟 import 纪律）
- [x] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——预期失败形态：12 场景运行期 ImportError（`traceability_tree` 模块缺失）为主形态；收集期零错误（`--co` 12 collected——延迟 import 纪律自证）；S12 红色形态=**Then 文件存在性断言 AssertionError**（Background 装配触既有模块绿——先行红在断言步非装配步，DR1-23））
- [x] Subtask 0.7: deferred-work.md 五条锚定义务处置注记落档（6.5b-DF1 半边清偿+半边 defer 6-8/6.4-DF3 清偿/R4N-1 维持 YAGNI/L170 顺延 Epic 8/L17 顺延——见 Dev Notes 锚定义务表）
- [x] Subtask 0.8: 既有资产复核（四 Agent 调研+主会话亲验已完成——2026-11-05；实施期 Task 0.8 复核行号漂移：query_archive 签名/ArchiveQuery 字段/get_point 签名/DocumentQuery 签名/payload 6 键构造位/CLI 子命令清单（add_parser 全量）/`traceability_tree` 词族零占用/3.5 payload 测试宿主文件位/display_name 三源常量族/StrategicArchiveService 全 None 构造可行性——DR1-22/DR1-7）
- [x] Subtask 0.9: 链路接线断言清单四项定义（Task 0 完成标志节钦定内容落档）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）
- [x] 五条锚定义务处置落档

---

### Task 1: ingestion payload 扩键——chunk_indexing_handler 6→8 键（6.5b-DF1 半边清偿）

**关联 AC:** AC-3（page_start 通道源头）/ 全 AC（回归面）

> **改动面极小且数据已在位**：`SemanticChunk.to_dict()` 已含 `page_start/page_end`（semantic_chunk.py:188-189）、PG `metadata["chunks"]` 已持久化该两键——handler 从 `doc.metadata.get("chunks")` 读 chunk_dicts（dict 列表），payload 构造未透传（:151-168 仅 6 键）。扩键 = payload 构造加两行 `.get()`。

#### TDD 循环 A：payload 扩键

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 定位 chunk_indexing 既有单测文件（全仓 grep `ChunkIndexingHandler` 测试——Task 1.0）并扩展：payload 8 键 exact set 断言（**构造面 8 键**——handler 层断言不含 infra 追加的 created_at；Qdrant 实存 9 键口径分立注记进 docstring，DR1-3。含 page_start/page_end 值级——预置 chunk dict 带页码）/legacy chunks（dict 无 page 键——历史文档 metadata 旧形态）降 None 不炸断言/既有 6 键值级不变断言 |
| 🟢 绿 | `chunk_indexing_handler.py:151-168` payload 构造追加 `"page_start": chunk.get("page_start")` / `"page_end": chunk.get("page_end")` 两键（.get 缺省 None——存量兼容读取侧天然降级，无需 collection 迁移） |
| 🔄 重构 | docstring payload 键清单更新（5. 注释行「payload 包含 …」同步 8 键）+ 3-8 受益注记（`traceability_service.py:125` `payload.get("page_start", 1)` 对新点自然命中——代码零改动） |

- [x] Subtask 1.0: 全仓 grep 复核 chunk_indexing 测试宿主与 payload 键断言面（主会话已定位 `tests/unit/infrastructure/workflow/test_document_tasks_index_payload.py`——Story 3.5 索引管道 payload 测试（`test_handler_writes_chunk_level_payload` 断言面）；另 `test_document_processing_flow.py`/`test_document_tasks.py`/`test_arch_layered_retrieval.py`/验收 hybrid_search 引用 handler——实施期复核断言强度并核验**零适配预期**（四文件零键集断言实测+hybrid_search 验收 handler 步为 hasattr 退化断言——DR2-5）
- [x] Subtask 1.1: 🔴 红 — payload 8 键失败测试
- [x] Subtask 1.2: 🟢 绿 — 两键扩键最小实现
- [x] Subtask 1.3: 🔄 重构 — docstring 与受益注记
- [x] Subtask 1.4: 回归面全绿——6-1 BLM 证据提取（payload text/content 键不受影响）/3-8 traceability 单测（mock 自构 payload 不受影响）/LayeredRetrieval 单测（parent 重构 4 键面）/chunk_indexing 既有全部测试（**零适配预期**——四文件零 payload 键集断言实测，DR1-19）

**完成标准/Definition of Done:**
- [x] payload 8 键落地（.get 缺省兼容）
- [x] 变异实证×1（删 page_start 键 → exact set 红）
- [x] 回归面全绿零适配（既有断言零打破实证——四文件零键集断言；若现红即回 Task 1 修实现而非改其他测试，DR1-19）

---

### Task 2: 应用层树服务——TraceabilityTreeService 四段编排 + 五 VO

**关联 AC:** AC-1（四层结构）/AC-2（depth 懒加载）/AC-3（跳转载荷）/AC-4（判 run）/AC-5（降级与空树）/AC-7（窗口）

#### TDD 循环 A：五 VO + 端口签名

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/test_traceability_tree_service.py` 编写 VO 键集 exact set 断言（frozenset(fields()) 形态——6-6 `EXPECTED_OUTCOME_KEYS` 激活先例）+ 端口 Protocol 签名存在性（inspect.signature 键位断言——6-4 CR1-R3 手法） |
| 🟢 绿 | `src/application/ports/traceability_tree.py` 新建：五 VO（Task 0.1 冻结键契约）+ `TraceabilityTreePort` Protocol 单方法 |
| 🔄 重构 | docstring 序列化契约区（键契约+树形嵌套语义+jump_ready 派生说明） |

#### TDD 循环 B：四段编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | TestBuildTraceTree 组（AsyncMock spec 三依赖替身+工厂函数——单测 Mock 红线合规；**strategic_archive_service spec 具体类**（仓无同名 Port——DR1-8）、l3_vector/document_repository spec Protocol）：①收集段 kind 过滤+空归档空树+**脏 stage 行**（stage∉七值域的链行→不产生 StageNode/计 total 不计 adopted——DR3-4）②判 run 段 stage 分组 last-write-wins（同 stage 两行构造——archived_at 显式先后（实体直造单测可控）+并列 tiebreak（archive_id 决胜——DR1-11）取新行值级）+**双 synthesis 行取新**（synthesis 入同一分组+计入 adopted——DR3-2）+adopted/total 对照（kind 过滤后口径——DR1-12）+synthesis 提取双形态+**乱序输入→有序 children**（mock 返回 archived_at DESC 乱序行→root.children 流程规范序断言——DR3-1）③切片段 depth 四档（**depth=1 root.children==() 且 get_point/find 双零调用**（DR1-2）/depth=2 get_point 零调用 call_order（AsyncMock assert_not_called 天然可写——DR1-5）/depth=3 find 零调用 /depth=4 全链）+point_missing 降级（**None 返回与 side_effect=Exception 两分支各一腿**——DR3-9）④文档段 document 去重缓存（同 document_id 两 chunk→find 恰一次调用计数断言）+page 匹配（脏形态降 None）+document_missing（**None/Exception 两分支**——DR3-9）+跳转载荷六键值级+bbox 透传+jump_ready 派生 ⑤顶层容错（query_archive 抛出→空树+build_degraded=True+warning——DR1-9）+degraded_stages 上卷 |
| 🟢 绿 | `src/application/services/traceability_tree_service.py` 实现（四段私有方法拆分——编排可读性；perf_counter 窗口不入 VO（性能窗口归测试计时——树 VO 无 execution_ms 键，YAGNI：6-6 Outcome.execution_ms 是执行面语义，纯读面窗口归采样） |
| 🔄 重构 | 分段私有方法+Raises/降级语义 docstring |

- [x] Subtask 2.1: 🔴 红 — VO/端口失败测试
- [x] Subtask 2.2: 🟢 绿 — 五 VO+Protocol 实现
- [x] Subtask 2.3: 🔄 重构 — 契约 docstring
- [x] Subtask 2.4: 🔴 红 — 四段编排失败测试（全场景矩阵）
- [x] Subtask 2.5: 🟢 绿 — 服务实现
- [x] Subtask 2.6: 🔄 重构 — 私有方法拆分

**完成标准/Definition of Done:**
- [x] 树服务全链实现（四段+降级+容错）
- [x] 变异实证×5（判 run 改旧行采纳→值级红/depth 懒加载边界破坏（如 `>=3` 改 `>=1`——depth=1 root.children+双零调用红与 depth=2 call_order 红一锚双档，DR2-4）/去重缓存删除→find 计数红/jump_ready 恒 True→降级场景红/**build_degraded 恒 False→顶层容错空树分立场景红（DR1-9 两键断言活着——DR2-4）**）
- [x] 单测 Mock 纪律合规（AsyncMock spec=ProtocolClass——验收/集成零 mock）

---

### Task 3: 用例 + CLI trace-tree + 组合根注册

**关联 AC:** AC-2（越域 242）/AC-5（畸形 242）/AC-6（CLI 全面）

#### TDD 循环 A：用例 + 组合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_traceability_tree_use_case.py`（UUID 守卫 242/depth 值域守卫 242（0 与 5 双边界）/透传）+ 契约测试 `tests/contracts/test_port_contract_traceability_tree.py`（五断言族：PORT_NAMES 两注册/spec 元数据 v1.0.0+SINGLETON+tags 含 "traceability"/resolve+isinstance/lambda getsource 三依赖注入链/新方法 inspect.signature） |
| 🟢 绿 | `GetTraceabilityTreeUseCase` 实现（双守卫+透传）+ 组合根两注册块（`traceability_tree_service` lambda resolve 三依赖+env collection/tenant；`traceability_tree_use_case`）——既有注册行零删改 |
| 🔄 重构 | 用例 Raises docstring |

#### TDD 循环 B：CLI trace-tree

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/interfaces/cli/test_agent_cli.py` 扩展（参数解析+树形输出四层标签精确匹配+chunk 前 8 位值级+filename 值级/`--stage` 过滤零输出断言/畸形 plan_id 242 stderr+exit 1/**空树输出断言（R1-F3 三腿）**（stub VO 构造 build_degraded=True/False/折叠三腿——「⚠ 归档查询失败（已降级）」/「该 plan 无归档行」/「归档对照（无分析层节点）」各自精确匹配+互斥反断言（DR1-17 归单测+DR2-7 断言孤儿消解））/五步定式） |
| 🟢 绿 | CLI 注册块+分发分支+`_run_trace_tree_cli`（`_run_checkpoint_show_cli` 直系样板——树形打印纯标准库递归缩进函数） |
| 🔄 重构 | 打印函数 getattr 形态（零 VO 强耦合——6-3 `_print_checkpoint_result` 先例） |

- [x] Subtask 3.1: 🔴 红 — 用例/契约失败测试
- [x] Subtask 3.2: 🟢 绿 — 用例+组合根两注册
- [x] Subtask 3.3: 🔄 重构 — Raises docstring
- [x] Subtask 3.4: 🔴 红 — CLI 失败测试
- [x] Subtask 3.5: 🟢 绿 — CLI trace-tree 实现
- [x] Subtask 3.6: 🔄 重构 — 打印函数形态统一

**完成标准/Definition of Done:**
- [x] 用例/CLI/组合根全链实现
- [x] 变异实证×2（depth 守卫删除→242 场景红/树形打印层级标签删除→精确匹配红）
- [x] 组合根 diff 纯新增（2 注册块——Task 4 审计）

---

### Task 4: 契约守护与回归面

**关联 AC:** 全 AC（接线与回归）

- [x] Subtask 4.1: 契约测试收口——五断言族全绿+新方法签名键位断言
- [x] Subtask 4.2: 事件面守护——`_FROZEN_EVENT_COUNT=56` 复跑零变化（零新增事件实证）+ 6-4/6-5b/6-6 既有事件契约断言面零修改复跑
- [x] Subtask 4.3: 回归面全绿——payload 扩键传播面（Task 1.4 清单复跑）+ 6-4 `query_chain_trace` 既有测试零适配（树服务不经 6-4 端口实证）+ 6-5b 引文链测试零适配 + 3-8 traceability 全部测试
- [x] Subtask 4.4: 组合根 diff 审计——功能行纯新增（2 注册块；git diff 形态检查——6-6 Task 4.5 同款）
- [x] Subtask 4.5: 「已实现未接线」排查——树服务/用例注册即接线（CLI 消费方在位）；无休眠组件产生（新注册全有消费方——`traceability_tree_use_case`→CLI、`traceability_tree_service`→use_case lambda）

**完成标准/Definition of Done:**
- [x] 全部契约/守护测试通过
- [x] payload 扩键传播面零意外回归实证
- [x] 6-4/6-5b/3-8 回归面零适配实证

---

### Task 5: 集成测试——真实链树构建

**关联 AC:** AC-1/AC-3/AC-4/AC-5/AC-7（真实服务面）

- [x] Subtask 5.1: 新建 `tests/integration/test_integration_traceability_tree.py`——自包含装配类 `_TreeChain`（真实 PG/Qdrant/Redis + 组合根 resolve；**零 LLM/零 MinIO**；**embedding 仅场景④ Fake 豁免**（AsyncMock spec EmbeddingServicePort——**按批次等长返回**，见 5.4/DR2-6——6-5b `_make_fake_embedding` 外部 SaaS 豁免面直系先例，DR1-7）；**集成 pytestmark 无 minio marker**（handler 直调不触 MinIO——对齐验收口径，勿整块复刻 6-5b 集成 markers，DR2-10）；归档预置 StrategicArchiveService 全 None 依赖构造（纯 L2——见验收预置纪律）；teardown 三步链各步独立 try/except+预登记；裸 async def+`_fresh_resolver_per_test` 双清 autouse——6-5b 集成形态）
- [x] Subtask 5.2: 场景①全链 round-trip（归档两 stage 直交→Qdrant 点 8 业务键预置（**扩键后形态**——page_start 值级读回；实存第 9 键 created_at 存在不计数——DR1-3）→PG 行原生 SQL 预置→树构建四层值级断言+`jump_ready==True`）
- [x] Subtask 5.3: 场景②多 run 判别+降级（同 stage 连续两次直交（自动 now 先后）→新行采纳（index 区分 chunk_id 判别锚——DR1-4）+adopted/total 对照；Qdrant 点删除→point_missing 真实降级；PG 行删除→document_missing 真实降级——**真实删除构造非 mock**）
- [x] Subtask 5.4: 场景③性能采样（20 轮 P95<300ms+预热；resolved 占比断言）+ 场景④ingestion 扩键 round-trip（经 RAGIndexed 事件链或 handler 直调（两路均需 embedding——Fake 豁免 DR1-7；**fake.embed_documents 须按批次长度返回等长向量列表**（side_effect 按 len(batch) 构造）——6-5b fake 恒返长度 1 是单文本形态，直抄则第 2+ chunk 缺 vector 不可预期，DR2-6）→Qdrant 点 payload 8 业务键读回（+created_at 存在）；**collection 偏离钦定（DR2-3）**：handler 写目标硬编码 "documents"（`chunk_indexing_handler.py:215`）不受 BLM_SEARCH_COLLECTION 影响——读回经 `get_point("documents", chunk_id)`、清理经 `delete_points("documents", [chunk_id])` 定向点删（L3VectorPort.delete_points :70 在位），**禁对共享 collection 整删**——**扩键的生产通道级验证**，验收预置形态之外的补充）
- [x] Subtask 5.5: 变异验证型×2（判 run 规则反转→场景②红还原绿；depth 懒加载破坏→红——6-3 Task 5 验证型变异先例；**R1-F11 归属澄清**：真实端口无调用记录面（DR1-5），call_order 零调用断言由 Task 2 单测矩阵承载，集成侧实际红点=树形/值级断言）

**完成标准/Definition of Done:**
- [x] 真实链场景全绿（服务不可达环境 skip）
- [x] 预置资源清理闭环（跑前后计数净增 0——归档行/Qdrant 点/PG 行三面）
- [x] 集成覆盖率 ≥75%（口径见覆盖率要求节）

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 架构合规（六边形+零改动面守护）

- [x] Subtask 6.1: 新建 `tests/unit/architecture/test_traceability_tree.py`（**OD-9**：对 epics L2385 钦定名 `test_provenance_tree.py` 的显式偏离——词族统一 traceability_tree；与既有 `test_arch_traceability.py`（3-8）不同名并存）验证器 A：树服务/用例/VO 落位（application 层内——AST/import 扫描；VO 在 ports 文件非服务文件本地定义——禁本地 Protocol 守护）
- [x] Subtask 6.2: 验证器 B：零 publish 守护（`traceability_tree_service.py` 源码零 `publish` 调用——grep 断言）+ 零事件构造（零 DomainEvent 子类构造位）
- [x] Subtask 6.3: 验证器 C：零 domain 改动守护（本 Story 新增文件全部在 application/entrypoints 层——`src/domain/` 零新文件断言；payload 扩键仅触 application/event_handlers）+ 依赖方向（树服务 import 面=domain ports+application ports 白名单）
- [x] Subtask 6.4: 验证器 D：CLI 接线（agent_cli.py 含 trace-tree 分发分支+resolve `traceability_tree_use_case` 调用锚）
- [x] Subtask 6.5: 变异实证×2（pydantic 注入 VO→A 红（若实证 domain 零依赖扫描面）；publish 调用注入→B 红——6-3/6-6 Task 6 先例）

**完成标准/Definition of Done:**
- [x] 四验证器全绿
- [x] 任何违规导致测试失败
- [x] 循环依赖检测经 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1~AC-7（最终验收）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已建 12 场景含收尾场景骨架（红阶段已验证）；本 Task 实现收尾场景步骤断言（不新增场景数——6-3 R2B-17 off-by-one 家族修复语继承） |
| 🟢 绿 | BDD 步骤实现收尾断言（文件存在性+关键符号存在性——6-3 S13/6-6 S14 形态先例） |
| 🔄 重构 | 场景命名收敛、断言统一 |

- [x] Subtask 7.1: 12 场景全绿（数据面三预置通道回灌+teardown 三步链+xdist 同组串行验证+S9/S10 CLI 双清形态）
- [x] Subtask 7.2: 四目录全量回归（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`——显式四目录）双轮零失败
- [x] Subtask 7.3: 收尾清单断言（src 新增/修改文件+四测试目录文件逐项存在性）
- [x] Subtask 7.4: 质量收口——ruff+mypy 全过（753 基线不回退）/专项覆盖率（application ≥85% 门禁+`traceability_tree_service.py`/`get_traceability_tree.py` 全新文件按文件级覆盖即新增面覆盖——6-6 口径钦定）/三红线 grep 自查零输出（raise ValueError/HTTPException/内置 Exception 继承——新增行）/提交信息禁 AI 署名
- [x] Subtask 7.5: 台账终态——deferred-work 五条处置注记核销状态回写+新留项登记（finding 级断言粒度引文 defer V1/bbox 四元组 defer 6-8——OD 登记）；sprint-status 注记更新

**完成标准/Definition of Done:**
- [x] 12 验收场景全绿+四目录全量双轮零失败
- [x] 完成清单逐项确认
- [x] Story 可进入 `code-review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) + [`sisys-core-domain-design.md`](../../../docs/architecture/sisys-core-domain-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 读侧聚合查询（CQRS 读面轻量形态——`src/application/queries/` 规划位 architecture.md:1904 标注 TODO V1/V2，当前查询走 ports+use_cases 形态——本 Story 沿当前形态不引入 queries 目录）+ 高保真溯源引用链（§17.1.7 CitationTracer.trace 含「溯源树构建 build_citation_tree」参考实现——蓝图，本 Story 以 evidence_refs 引用链落地）
- **设计约束:** 领域层零依赖（本 Story 零 domain 改动——最严格形态）；frozen dataclass 不可变 VO；6-4 `ChainOfThoughtArchiveServicePort` 冻结面零触碰（evidence_refs 读经 query_archive 通道）；3-8 `TraceabilityPort` 语义正交零触碰（6-5b OD-6 裁定延续）
- **接口治理:** 统一端口注册（新端口 v1.0.0 一次到位）、Registry/Resolver、组合根唯一装配、契约优先、禁同义接口重复（树聚合 vs claim 检索是两语义——两端口并立正当）
- **技术栈:** Python 3.11+ / PostgreSQL（strategic_archives/documents）/ Qdrant（get_point 点查）/ Redis（本 Story 仅经组合根装配链依赖——树服务零 Redis 直连）/ pytest-bdd
- **关键设计条款:** architecture.md:2467-2468 `GET /api/v1/documents/{doc_id}/trace` 钦定端点形态（归 7-2 REST 立项——本 Story CLI 形态）; :3246 FR-SR-08 Citation 值对象承载坐标（bbox 字段族在位——本 Story 透传）; :1293 查询不发布事件; :2549-2553 archive-evidence 桶族（本 Story 读侧不触 L4）; or.md L175/L240/L344 溯源树三层语义（三元组承载）

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | **范围边界——MVP = 树聚合查询面（端口+服务+用例+CLI `trace-tree`）+ payload 扩键半边（page_start/page_end）。不含**：bbox 四元组写入（OD-8 defer 6-8）/REST 端点（interface-design.md:1406 `GET /documents/{id}/trace` P0 归 7-2——6.1-DF5 第六连 CLI-only 先例，openapi.yaml 零 diff）/Web 阅读器与高亮（6-8——epics L2018 独立依赖链钦定）/finding 级断言粒度引文（evidence_refs 步骤级粒度——6-5b「正文不插句级引用标记」同因裁定，V1 defer 登记）/`TraceabilityPort` 演进（3-8 trace(claim) 是按文本重检索断言面，与按 plan_id 遍历引用链的树查询语义正交——6-5b OD-6「不复用 3-8 TraceabilityPort」裁定延续；两端口并立非同义重复）/3-8-P2-1 单引文 API 路由（3-8 自身 defer 维持——本 Story 不消费该面） | epics L2350-2389 范围权威 + 6-5b OD-6 直系先例 + 6.1-DF5 CLI-only 惯例 + UX spec L182/L193（PDF.js/单页溯源是 Web 面——MVP 标注「单页溯源」V1 多页）+ YAGNI |
| **OD-2** | **零新增领域事件、零发布调用**：纯查询展示面零状态变更——architecture.md:1293「查询不发布事件」成文 + 6-4 OD-6/6-5a OD-6 零发布查询面先例 + 6-6 OD-2 零新增领域事件（CheckpointRecovered 为既有登记键首激活非新增——精确转述 DR1-21）——**查询型故事零事件先例族**；event_channels.yaml/DEFAULT_MAPPINGS 零 diff；`_FROZEN_EVENT_COUNT=56` 零变化（Task 4.2 守护）；蓝图无溯源树事件（or.md 溯源树语义无事件载体）；架构验证器 B 零 publish 守护 | 查询语义纯度 + 先例族 + 零 yaml/router diff 红利 |
| **OD-3** | **零新增领域异常、零既有异常改动**：242 复用（畸形 plan_id+depth 越域——用例层守卫，GetBlmChainTraceUseCase 直系）；空计划幂等读不抛（6-4 ChainOfThoughtTraceView「空档案返回 total=0 不抛异常」+ 6-6 空清单两先例——树是 plan 级枚举面非单点面）；依赖失效走节点 status 降级（非异常路径——6-5b 降级三态哲学树形版）+ 顶层 query_archive 异常空树降级（6-5b 整体容错边界同构）；traceability 段 372-379 空位维持预留（「树构建失败」经降级承载后无真实 raise 触发面——YAGNI）；无 404 语义面（空树即不存在语义）。**否决备选**：开 372 `TraceabilityTreeNotFoundError`——空态非错误态（枚举面语义），开码即引入「空 plan 误报 404」的反语义面 | 异常语义纯度 + 三先例 + 空态幂等读语义 |
| **OD-4** | **树 VO 键契约（Task 0.1 冻结）**：五 VO 全应用层 frozen dataclass（ports/traceability_tree.py）——`TraceabilityTree` **7 键**（含 `build_degraded` 顶层降级哨兵——空树与真空树分立：**空结果必须自我解释是「没有数据」还是「拿不到数据」**（读模型诚实性）；`degraded_stages`=非 resolved 后代 stage 上卷）/`ConclusionNode` 5 键/`StageNode` 9 键/`ChunkNode` 6 键/`DocumentNode` 9 键（含 `jump_ready` 派生布尔——跳转载荷齐备判定，「30 秒溯源」可达性节点级观测面；半跳转由 object_key 非 None 判别不建 partial 枚举——YAGNI 论证落 docstring）；**synthesis 行不产生 StageNode**（结论层即其呈现位——分析层七 stage 值域、stage_count=全 run 7，DR1-13）；or.md L344「每层三元组」适配论证：切片/文档层无「计算逻辑」可示、三元组落位分析层；or.md 三层→本树四层映射=数据层细分切片+文档（页码与对象键分立的跳转载荷）；三截断口径（summary=synthesis conclusions 联展或降空串/reflection_excerpt 200 字符（源键 chain.reflection）/content_excerpt 300 字符——6-1 证据文本截断同族 `blm_planning_service.py:98`）；树形嵌套 chunk 跨 stage 重复（每路径独立——flat 去重是 6-5b 引文语义非树语义）；文档 find 去重缓存（调用次数 vs 节点形态分立——AC-1）；**零 domain VO**（读侧 DTO 归应用层——CheckpointSummaryView 先例；6-5b CitationEntry 入 domain 是报告域特例对照非先例强制） | 键恒在纪律（6-2 R1-6 七键契约同族）+ 读侧 DTO 层位先例 + CLI 树形打印量级（≤8 stage×≤5 chunk） |
| **OD-5** | **多 run 判别 = stage 分组 last-write-wins + adopted/total 对照**（6.4-DF3 清偿）：每 stage 取 `archived_at` 最新行，**并列以 archive_id 决胜**（`key=(archived_at or _EPOCH_FLOOR, archive_id)` 全序——单键时间戳仅偏序，并列即掷骰子，DR1-11）；**None 行回落 epoch 永不获胜**（6-4 `_EPOCH_FLOOR` 同款——全 None stage 采纳 epoch 行计入 adopted）；与 Redis latest 快照同构——最新 run 优先（6-4 升序全量与本树 last-write-wins=同数据两读面：审计序 vs 当前态投影）；`total_archives`（**kind 过滤后思维链候选行数**）/`adopted_archives`（判 run 后采纳行数）对照使 run 压制丢弃面可见（对照信号纯化为单现象，DR1-12）；limit=1000（`ArchiveQuery` clamp 上限——**正确性窗口**非 6-5b 引文展示窗口 64：每 run 8 行需 125 次重跑触顶；total==1000 即饱和探针——截断弱可观测）。**否决备选**：a) decision_basis 增 run 锚——动 6-4 冻结四键契约+其 exact set 断言族（写侧演进成本+存量行无锚仍需读侧兜底判别——两案并存反而复杂）；b) archived_at 时间窗聚簇（阈值语义模糊：跨天重跑窗口难定）——last-write-wins+全序决胜是唯一无参数确定性规则 | 6-4 冻结面零触碰 + 无参数全序确定性 + latest 语义同构先例 + 6.4-DF3 台账钦定「按 archived_at 时间窗聚簇判 run 或 decision_basis 增 run 锚」两候选中的语义最优解（时间窗思想经 stage 分组内最新行承载——组内单点比较无窗口阈值） |
| **OD-6** | **交互式展开 = depth 参数懒加载（{1,2,3,4} 默认 4）**：depth=2 切片层零解析（get_point 零调用 call_order 断言）/depth=3 文档层零解析（find 零调用）——懒展开是 6-8 Web「证据树折叠/展开」（FR-UI-13）的后端供给口径；CLI `--depth` 透传（默认 4 全树——CLI 单次输出场景无交互折叠面）。**epics「交互式展开测试——节点可正确展开/收起」的功能等价改写**：Web 折叠语义在 CLI/端口形态=depth 分层返回（展开=深 depth、收起=浅 depth）——6-6 OD-5「wait_for_human_confirmation CLI 同步形态等价改写」同款裁定 | epics AC 措辞与 CLI-only 形态的等价性论证 + 6-8 供给 + 分层懒加载性能证明（depth 窗口对照；Web 面跳转性能先例参照 epics Story 21.6「追溯跳转<100ms」——非本 Story 门禁） |
| **OD-7** | **性能三段口径声明**：① 加载 P95<300ms = `build_trace_tree` 服务面窗口（query_archive+get_point×N≤40+find×M 去重后——串行点查毫秒级实测锚定；20 轮 `sorted[ceil(0.95*n)-1]` 数学口径）；② 「Bounding Box 跳转响应<300ms」（epics L2372）以**跳转载荷组装口径**承载——CLI 无跳转运行时（Web 点击跳转归 6-8，届时 Web 侧计时归其 Story）；断言形态=depth=4 全树窗口（含载荷组装）<300ms 即覆盖；③ 「溯源定位准确率≥95%」（epics L2373）以**解析成功率口径**承载（resolved/(resolved+missing) 节点统计——预置全解析场景 100%）；真值口径（人工抽检坐标正确性——prd L373「随机抽样 1000 次」）归部署验证（6.1-DF1 同族口径差声明——Fake/预置数据无真值面） | epic 性能行与 CLI 交付面口径对齐（6-3 OD-6/6-6 OD-8 口径差声明纪律）+ 三口径落验收 docstring |
| **OD-8** | **payload 扩键半边清偿 + bbox 四元组 defer 6-8**（6.5b-DF1 处置）：半边清偿 = `chunk_indexing_handler` payload 6→8 键（page_start/page_end——`.get()` 缺省 None 存量兼容，旧点天然降级**无需 collection 迁移**；数据已在位：`SemanticChunk.to_dict()` 含页码键/PG chunks 已持久化——改动两行）；3-8 `TraceabilityService` page_number 读取面自然受益（代码零改动）。**bbox 四元组 defer**（6.5b-DF1 另半边）：chunk 级 bbox 语义未定（一 chunk 跨多元素——聚合语义需设计：并集/列表/首元素）+ 版面模型在位依赖（`SISYS_LAYOUT_MODEL_PATH` 缺失时元素 bbox 恒 None——写入侧无稳定数据源）+ Web 高亮是真实消费方（6-8 PDF.js——epics L2018 独立依赖链）；树读侧 `payload.get("bbox")` 透传就绪（未来扩键零树侧改动）。deferred-work 注记半边清偿+半边顺延 | 6.5b-DF1 台账钦定「6-7/6-8 立项时评估」的双承接方裁定 + 数据在位实证（低成本高收益半边先做）+ bbox 三依赖论证（语义/数据源/消费方均在 6-8 侧收敛） |
| **OD-9** | **测试文件命名（禁故事编号后缀）+ 词族统一 traceability_tree**：acceptance `test_acceptance_traceability_tree.feature/.py`；integration `test_integration_traceability_tree.py`（**对 epics L2386 钦定名 `test_provenance_tree_integration.py` 的显式偏离**——仓规 test_integration_* 前缀，6-3 OD-8/6-6 OD-11 同款拆分声明）；unit/architecture `test_traceability_tree.py`（**对 epics L2385 钦定名 `test_provenance_tree.py` 的显式偏离**——词族统一 traceability_tree：与 3-8 traceability 域词汇同族（TraceabilityPort/traceability_service/test_arch_traceability 全族在位），避免 provenance/traceability 双词分裂（epics 措辞 provenance 是规划期用词，代码域已定型 traceability）；6-6 OD-11 半采半离先例——落位仓规 unit/architecture/ 子目录承载 SDD 架构验证）；与既有 `test_arch_traceability.py`/`test_acceptance_traceability.*`（3-8）不同名并存；service 单测 `test_traceability_tree_service.py`；契约 `test_port_contract_traceability_tree.py`（五断言族新式） | 记忆「禁止故事编号命名文件」+ 仓规目录前缀惯例 + 域词汇一致性（epics 钦定名的采纳/偏离逐处声明） |
| **OD-10** | **思维链全文附录维持 YAGNI**（6-5b R4N-1 钦定「随 6-7 溯源树立项定夺」的裁定）：6-5b 立项时已裁定「引文索引已交付溯源消费面，chain.to_display() 资产在位」——本 Story 立项复核：树 StageNode 已承载「计算逻辑」三元组摘要（tools_used/reflection_excerpt 200 字符）+ 全文呈现无消费方（CLI 树形输出的信息密度目标是导航不是阅读——阅读面归 6-8 Web 节点详情）；维持 YAGNI，台账注记落档 | R4N-1 钦定承接 + 树节点三元组已承载「查看详细信息」（or.md L344 口径）+ YAGNI |
| **OD-11** | **组合根两注册 + 三依赖复用 + collection/tenant 构造参数单源**：`traceability_tree_service`（SINGLETON——无状态聚合读；lambda resolve 三既有依赖+`os.getenv("BLM_SEARCH_COLLECTION","documents")`+`str(MVP_TENANT_ID)`——6-1 组合根 :1592 与 6-5b 服务构造 :121 双先例**合流形态**（构造默认值+env 传导——无完全同构先例、可行性实证注记，DR1-18）；**SINGLETON 捕获 SCOPED 三依赖声明**（strategic_archive_service/l3_vector/document_repository 全 SCOPED——CLI 一次性进程+测试双清下无故障面（6-6 checkpoint_service 同款先例已跑通）；未来 7-2 长驻 REST 面改 SCOPED（3-8 traceability_service 同构）——触发器注记，DR1-18））+ `traceability_tree_use_case`（SINGLETON 透传）；**零新 PG 仓储家族成员**（document_repository 既有组合根会话包装 `_SessionScopedDocumentRepository` 消费——6.5b-DF4 会话抖动知悉：CLI 读场景每 find 一次会话，树服务文档去重缓存将其压至每 document 一次）；6-4 CLI session P0 三步排查法核验（OD-12 同款预防性）：组合根 lambda 无新 PG 构造/无新仓储成员——无 session_factory 缺口面 | 6-6 OD-12 三步排查法教训应用 + 单租户口径先例（6.1-DF4 MVP 单租户注记延续） |
| **OD-12** | **本 Story 零 infrastructure 改动 + 零 migration + 零 domain 改动**：payload 扩键在 application/event_handlers（handler 是应用层——非 infra）；树服务纯读侧聚合（QdrantAdapter/PostgreSQL 仓储全复用零改动）；三「零」Story 是 Epic 6 最小改动面形态（6-6「零 infra 改动」的加强版——再减 domain）；风险集中度最低 | 读侧聚合本质 + 6-6 OD-12 先例延伸 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── application/
│   ├── ports/traceability_tree.py            ★ 新建（五 VO+TraceabilityTreePort——Task 2）
│   ├── services/traceability_tree_service.py ★ 新建（四段编排——Task 2）
│   ├── use_cases/get_traceability_tree.py    ★ 新建（双守卫+透传——Task 3）
│   └── event_handlers/chunk_indexing_handler.py ▲ payload 6→8 键（Task 1——唯一既有源文件改动）
├── entrypoints/agent_cli.py                  ▲ trace-tree 子命令（Task 3——R4）
└── composition_root.py                       ▲ 两注册块（Task 3）

（src/domain/ 与 src/infrastructure/ 零改动——OD-12 三零 Story）

tests/
├── unit/
│   ├── application/test_traceability_tree_service.py        ★ 新建（Task 2）
│   ├── application/use_cases/test_traceability_tree_use_case.py ★ 新建（Task 3）
│   ├── infrastructure/workflow/test_document_tasks_index_payload.py ▲ 8 键断言扩展（Task 1——3.5 payload 测试宿主；同族四文件零键集断言——复核面零适配预期（DR1-19））
│   ├── architecture/test_traceability_tree.py               ★ 新建（Task 6——OD-9 偏离声明）
│   └── interfaces/cli/test_agent_cli.py                     ▲ trace-tree 扩展（Task 3）
├── integration/test_integration_traceability_tree.py        ★ 新建（Task 5，OD-9）
├── contracts/test_port_contract_traceability_tree.py        ★ 新建（Task 3/4——五断言族）
└── acceptance/
    ├── test_acceptance_traceability_tree.feature/.py        ★ 新建（Task 0/7，R6 模板）
    └──（6-4/6-5b/3-8 既有测试文件零修改——Task 4 回归验证；chunk_indexing 既有测试**零适配预期**（四文件零键集断言实测，DR2-5）——Task 1 唯一新测试面=新增 8 键断言）

_bmad-output/implementation-artifacts/deferred-work.md  ▲ 五条处置注记+新留项（Task 0/7）
```

（▲ 修改 / ★ 新建 / = 零改动 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话亲验 2026-11-05；行号基准 HEAD@420c8cdc，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| `query_archive` | `src/application/services/strategic_archive_service.py:315` | `async query_archive(query: ArchiveQuery) -> list[StrategicArchive]`——树服务①收集段消费面（6-5b `_aggregate_citations` 同款通道） |
| `ArchiveQuery` | `src/domain/ports/archive_repository.py:39` | frozen VO：plan_id: UUID\|None/archive_type/limit 默认 20 上限 1000（clamp 非抛异常）——树查询构造 `ArchiveQuery(plan_id=uuid, archive_type=ArchiveType.EVIDENCE_PACKAGE, limit=1000)` |
| `StrategicArchive` 实体 | `src/domain/entities/strategic_archive.py:55-73`（assumptions/decision_basis :61-62、archived_at :69） | plan_id/archive_type/assumptions(dict)/decision_basis(dict)/archived_at(datetime\|None)——evidence_refs 在 assumptions、stage/chain 在 decision_basis、判 run 锚在 archived_at |
| `CHAIN_ARCHIVE_KIND` | `src/application/ports/chain_of_thought_archive.py:40` | `"blm_chain_of_thought"`——kind 过滤常量（6-4 冻结面零触碰，值消费） |
| `query_chain_trace`（对照面） | `src/application/services/chain_of_thought_archive_service.py:224-275` | 6-4 既有读面五键 records **不含 evidence_refs**——树服务不经此方法直读 query_archive 的依据（6-5b 同款） |
| `L3VectorPort.get_point` | `src/domain/ports/l3_vector.py:85` | `get_point(collection, point_id) -> dict\|None`——返回 {id, vector, payload}，不存在返 None（point_missing 判据） |
| `DocumentQuery` | `src/domain/ports/document_repository.py:17-39` | `tenant_id: str` 必填+`document_id: UUID\|None`——find(DocumentQuery(tenant_id, document_id))；tenant 默认 str(MVP_TENANT_ID)（构造注入） |
| `MVP_TENANT_ID` | `src/application/services/agent_workflow_context.py`（import 位 `pdf_report_generation_service.py:37`） | 单租户常量——6-5b 构造注入先例（服务签名 `tenant_id: str = str(MVP_TENANT_ID)`） |
| payload 6 键构造位 | `src/application/event_handlers/chunk_indexing_handler.py:151-168` | 点 ID=chunk_id（供 get_point 回溯）；payload {chunk_id/document_id/parent_chunk_id/index_level/content/chunk_header}——**Task 1 扩键落点（+page_start/page_end 两行 `.get()`）**；chunk_dicts 源自 `doc.metadata.get("chunks")`（dict 列表——页码键已在其中）；**Qdrant 实存另含 infra 追加 created_at**（`vector_storage.py:85`——实存 9 键，读回断言口径见预置纪律 DR1-3） |
| `SemanticChunk.to_dict()` | `src/domain/value_objects/semantic_chunk.py:172-195` | 含 page_start/page_end 键（:188-189）——PG chunks 元数据页码在位的实证（扩键数据源） |
| page 匹配先例 | `src/application/services/pdf_report_generation_service.py:360-368` | `metadata["chunks"]` 按 chunk_id 匹配 page_start+脏形态守卫降级——树服务④文档段同款复刻 |
| 引文三段链契约 | `src/application/ports/pdf_report.py:23-49` | 6-5b OD-6 收集/解析/组装三段 docstring——树服务链路蓝本（同端口同顺序） |
| `CitationEntry.VALID_STATUSES` | `src/domain/value_objects/citation_entry.py:40` | ("resolved","point_missing","document_missing")——树节点 status 值域分立依据（chunk 层两值/document 层两值） |
| 3-8 受益面 | `src/application/services/traceability_service.py:125` | `payload.get("page_start", 1)`——扩键后新点自然命中（受益注记，代码零改动）；:109 `payload.get("bbox")` 透传就绪 |
| `STAGE_VALUE_DOMAIN` | `src/domain/value_objects/blm_phases.py:69-71` | 八 stage 值域（performance_gap+market_insight_{六}+market_insight_synthesis）——**StageNode.stage 七值域来源（八值去 synthesis——DR1-13）**与 synthesis 行判据（market_insight_synthesis 行→结论层 summary） |
| `StepSemanticConfig.display_name` | `src/application/services/blm_planning_prompts.py:136-157`（display_name :153） | display_name **三源常量族**（无单一映射表——Task 0.2 钉拼装形态 DR1-22）：六子 `MARKET_INSIGHT_STEP_CONFIG` dict（:172，枚举键）+performance_gap 独立常量 `PERFORMANCE_GAP_CONFIG`（:162）+synthesis 常量 `SYNTHESIS_DISPLAY_NAME`（`chain_of_thought_archive.py:45`——归结论层承载 DR1-13） |
| BLM collection 单源 | `src/composition_root.py:1591-1592` | `os.getenv("BLM_SEARCH_COLLECTION","documents")`——树服务 search_collection 构造参数的组合根传导先例 |
| CLI 五步定式样板 | `src/entrypoints/agent_cli.py:435-452`（checkpoint_show 注册块）+ `_run_checkpoint_show_cli`（:1275-1308 五步定式；分发分支族 :1865-1913） | 参数守卫→ensure_bootstrapped→asyncio.run+resolve→打印（getattr 形态）→DomainError `[code]` exit 1——trace-tree 直系样板；现存 13 子命令扁平族（add_parser 全量以 grep 为准）无 trace-tree 重名（亲验 grep 零命中） |
| 既有注册块 | `src/composition_root.py` | l3_vector :363/document_repository :1176/chunk_indexing_handler :1980/strategic_archive_service :2216——树服务 lambda resolve 三依赖目标；新增两注册块落其邻近 |
| 6-5b 预置/清理样板 | `tests/acceptance/test_acceptance_pdf_report.py`（S4 引文预置 :851-932）+ `tests/integration/test_integration_pdf_report.py` | Qdrant 点预置经 `l3_vector.upsert_points`（:881/:897——MD5 归一在通道内部读写对称）+**PG 行原生 SQL INSERT（:905-935——非 document_repository）**+teardown 定向清理（Qdrant 按 payload.chunk_id FilterSelector :423-431+PG DELETE :443-447）——`_TreeChain` 基座（DR1-16） |
| 6-4 归档轻装配 | `tests/acceptance/test_acceptance_markdown_report.py:1106`（`_assemble_archive_only`） | 逐 stage 直交归档无 LLM——验收/集成的归档预置通道（**注意其 Fake embedding+真实 MinIO 装配形态——6-7 预置改全 None 构造（DR1-7）**） |
| 3.5 payload 测试宿主 | `tests/unit/infrastructure/workflow/test_document_tasks_index_payload.py` | Story 3.5 索引管道 payload 测试（`test_handler_writes_chunk_level_payload` :40 起）——Task 1 扩键断言扩展宿主（主会话 grep 亲验定位）；同族 `test_document_processing_flow.py`/`test_document_tasks.py` 复核面 |
| R6 钦定模板 | `tests/acceptance/test_acceptance_postgresql_relational_layer.feature/.py` | feature 组织+@scenario 绑定形态承袭；py 欠账（部分绑定/无三件套）禁沿用 |
| CLI 双清先例 | `tests/acceptance/test_acceptance_markdown_report.py:144-148` | `clear_singleton()`+`clear_scoped()`——S9/S10 CLI 直调前钦定（+monkeypatch env 桥接——DR1-6） |
| 冻结键数基线 | `tests/contracts/test_event_channel_mapping_pdf_report.py:23-24` | `_FROZEN_EVENT_COUNT=56`——零新增事件守护（Task 4.2） |
| epics Story 6.7 定义 | `_bmad-output/planning-artifacts/epics_v1.0.md:2350-2389` | AC/性能三项/测试文件名钦定源（三项架构测试落位对账+性能三段口径——OD-6/OD-7） |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-7 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L371（6.5b-DF1·P2） | bbox ingestion 写入缺口（chunk_indexing_handler payload 无 bbox/page_start——3-8 遗留前置；触发=6-7 溯源树立项或 6-8 Web 高亮立项） | **半边清偿 + 半边 defer 6-8**（OD-8）：page_start/page_end 两键本 Story 落地（数据在位实证——SemanticChunk.to_dict/PG chunks 已含）；bbox 四元组 defer 6-8（chunk 级 bbox 聚合语义未定+版面模型在位依赖+Web 高亮是真实消费方）；deferred-work 注记半边清偿+6-8 顺延（台账钦定双承接方的显式分流） |
| 2 | L363（6.4-DF3·P3） | 同 plan_id 跨进程重跑叠加行读侧判别缺口（追溯按 archived_at 升序输出重复 stage 锚——6-7 溯源树按 stage 过滤将现双节点；截断面静默丢弃） | **本 Story 清偿**（OD-5）：stage 分组 last-write-wins + adopted/total 对照可见（截断面闭合）；decision_basis 增 run 锚备选否决论证落 OD-5 |
| 3 | 6-5b story R4N-1（Task 0.7 注记位） | 思维链全文附录维持 YAGNI「随 6-7 溯源树立项定夺」 | **本 Story 立项定夺：维持 YAGNI**（OD-10）——树 StageNode 三元组摘要已承载「查看详细信息」；全文阅读面归 6-8 Web 节点详情；台账注记定夺完成 |
| 4 | L170（事件消费基建四件） | 消费基建激活锚位候选「Epic 6 首个事件消费 Story」 | **顺延 Epic 8**：6-7 是纯查询面零事件订阅（**六连「纯生产方/零消费」裁定延续（5-3/6-3/6-4/6-5a/6-5b/6-6）+ 本 Story 零发布零订阅双向皆无——查询面先例族新形态**，DR2-10）；register_handler 队列名语义错位未修复前禁止激活约束维持；注记落档 |
| 5 | L17（langgraph retry/timeout） | 锚位候选「checkpoint_table/图引擎字段消费方」 | **不触发，锚位顺延**：6-7 纯读侧聚合零图引擎/checkpoint_table 消费（四轮同款裁定——5-10/6-1/6-6 先例延续）；注记落档 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-6 Checkpoint 摘要查看与恢复](./6-6-checkpoint-summary-and-recovery.md)（五轮文档审查+五轮代码审查收敛 done）+ 6-4/6-5b（引文链/482 让位/受益注记）

**关键学习/Key Learnings:**
- **Agent 误报主会话复核**（6-5b R1/6-6 教训）：调研结论关键锚点（行号/字段形态/签名）主会话亲验后方可入 Story——本 Story 已亲验 9 组关键事实（query_archive 签名/ArchiveQuery 字段/get_point 签名/DocumentQuery 必填序/payload 6 键构造位/CLI 子命令清单/`traceability_tree` 词族零占用/SemanticChunk.to_dict 页码键/3.5 payload 测试宿主定位）
- **读侧消费既有冻结面纪律**（6-5b OD-6 直系）：新消费方直读 query_archive 通道，不演进 6-4 端口方法族（query_chain_trace 不含 evidence_refs 是其契约现状——绕行而非扩约）
- **降级哲学树形化**（6-5b「引文是增强面非阻断面」）：树节点 status 降级 + 顶层容错空树——失效可观测（status/jump_ready）而非 raise
- **幂等读语义**（6-4 ChainOfThoughtTraceView docstring + 6-6 空清单）：枚举面/树面空态返回非异常态——「不存在」经空树承载
- **断言判别力**：exact set 键集断言（frozenset(fields())——6-6 R1-F10 激活先例）；call_order 零调用断言（懒加载哨兵——6-3 R1-F2 形态）；值级断言防「忘填用默认值」（6-3 R3-2/6-6 R1-F2）
- **CLI 直调双清**（6-6 R3-1 实跑证伪教训）：clear_singleton+clear_scoped 双清+禁二次 bootstrap——S9/S10 钦定
- **性能口径差声明**（6-1 DC-7/6-6 OD-8）：epic 性能行与 CLI 交付面的口径差落 OD+docstring（OD-7 三段）
- **payload 改动的传播面 grep**（CLAUDE.md「适配器契约变更回归面」纪律）：payload 扩键后全仓 grep 消费方（6-1 证据提取/3-8 traceability/LayeredRetrieval/chunk_indexing 测试）——Task 1.4/4.3 承载
- **红绿变异全链**（Epic 4 行动项 7.1-2）：新断言变异实证——本 Story 变异锚钦定 12 处（Task 1×1/Task 2×5/Task 3×2/Task 5×2 验证型/Task 6×2——DR2-4 扩 build_degraded 锚）

**应用到本故事/Applied to This Story:**
- [x] 9 组关键锚点主会话亲验（创建期已执行——锚点表承载）
- [x] 6-4 端口零触碰+query_archive 直读（OD-1/OD-5）
- [x] 降级链路三态两层+顶层容错+空树幂等读（AC-5/OD-3）
- [x] exact set/call_order 零调用/值级三类断言形态（Task 2 矩阵）
- [x] CLI 双清+禁二次 bootstrap（S9/S10）
- [x] 性能三段口径差声明（OD-7）
- [x] payload 传播面 grep 回归（Task 1.4/4.3）
- [x] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep

### 其他约束速查

- **风险集中登记**：①回归风险=payload 扩键传播面（Task 1.4/4.3 grep 全集——**零适配预期**：四文件零键集断言实测（DR1-19），新增 8 键断言是唯一新测试面）；②契约风险=五 VO 键契约（Task 0.1 冻结唯一版本——实现禁增删键）；③口径风险=性能三段（OD-7）+payload 构造面 8 键/Qdrant 实存 9 键分立（DR1-3）；④懒加载风险=depth 分层边界（get_point/find 零调用断言是唯一判别锚——变异实证钦定；验收面树形断言+单测面 call_order 分立 DR1-5）；⑤判 run 风险=last-write-wins 规则（同 stage 两行值级断言——旧行值需与新行可区分；并列 archive_id 决胜 DR1-11）；⑥装配风险=collection 单源（预置与读回同 collection——服务构造注入+CLI 面 monkeypatch env 桥接（DR1-6），配置漂移则假 point_missing）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore/pylint disable；提交信息禁 AI 署名
- **覆盖率**：整体≥80% / application≥85%（主改动层）/ domain≥90% 维持 / 集成≥75%
- **验收零 mock 全真实**（pytest.skip() 动态跳过；**集成仅场景④ Fake-embedding 豁免**（外部 SaaS 豁免先例——DR1-7/DR2-2）；「点已删/文档已删」用真实删除构造）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）
- **xdist 串行组**：pytestmark `xdist_group("blm-planning-perf")` 整模块挂法

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-05 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.7 L2350-2389 + 依赖链 L2017/L2025-2026 + P0-7） |
| **架构文档** | `docs/architecture/architecture.md`（:1293 查询不发事件/:1904 CQRS 规划位/:2467-2468 trace 端点钦定/:3246 FR-SR-08）+ `sisys-core-domain-design.md` §17.1.7 CitationTracer 蓝图 |
| **需求权威** | `_bmad-output/planning-artifacts/prd.md`（L149/L243 溯源<30s/L373 准确率/L419 响应）+ `or.md`（L175/L240/L344 溯源树三层语义）+ `ux-design-specification.md`（L182/L193）+ `docs/architecture/interface-design.md`（:1406/:2006——实际路径在 docs/architecture/ 非 planning-artifacts/，DR1-22） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-6-checkpoint-summary-and-recovery.md`（OD-2 零事件/OD-3 载载形态/OD-11 命名半采半离/R3-1 CLI 双清）+ 6-5b（OD-6 引文三段链蓝图/降级三态/R4N-1 承接）+ 6-4（query_chain_trace 读面/DF3） |
| **留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L363 6.4-DF3/L371 6.5b-DF1/L170/L17 + 6-5b R4N-1 注记位） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml`（L185——创建时 backlog，已同步 ready-for-dev——DR1-23） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 6.7 节 + 依赖链 + FR 定位核实——无独立 FR，深化 FR-SR-08 展示侧）
- [x] 架构约束从 architecture.md + sisys-core-domain-design.md §17.1.7 + 6-5b OD-6 引文链蓝图提取
- [x] 前一个故事学习经验整合（6-6 双五轮 + 6-5b 引文链 + 6-4 追溯读面）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（三零 Story/payload 扩键/两注册/CLI 一命令/锚定义务五条处置）
- [x] 多 Agent 并行调研（四视角：BBox 溯源数据面/结论证据链/验收测试样板/架构治理与 API 模式）+ 主会话独立亲验 9 组关键代码事实（query_archive/ArchiveQuery/get_point/DocumentQuery/payload 6 键/CLI 子命令/词族零占用/SemanticChunk.to_dict/3.5 payload 测试宿主）
- [x] dev-story 实施完成（2026-11-05，Task 0~7）：四 Agent 并行锚点复核（43 项锚点 39 项精确命中/4 项轻微漂移：pdf_report docstring :15-29/vector_storage 路径 qdrant 子包/chain 注册 :2370/契约样板名）+ Task 0 红阶段（12 collected 零错误+12 failed 预期形态）+ Task 1 payload 6→8 键（变异×1+回归面 94+37 passed 零适配）+ Task 2 五 VO+四段编排（33 单测+变异×5——判 run 反转/depth 边界/去重缓存/jump_ready/build_degraded）+ Task 3 用例双守卫+CLI 五步定式+组合根两注册（195 passed+变异×2）+ Task 4 事件冻结 56 复跑/组合根 50 行纯新增（R1-F11 勘误——原记 40 为功能行约数，实测 +50/-0）/消费方接线排查 + Task 5 集成四场景（双轮全绿+变异×2+覆盖率 82%/并集 79%）+ Task 6 架构四验证器（11 passed+变异×2——pydantic 注入/publish 注入）+ Task 7 收尾
- [x] 实施攻坚三项：① 裸 document_repository 严格 ContextVar 会话（CLI/测试直调无会话——组合根 lambda _SessionScopedDocumentRepository 包装注入+测试 _SessionScopedFind 镜像双面修复，6-5b 同款先例）；② 6-4 EVIDENCE_PACKAGE 唯一构造位守护将查询消费面误判构造位（许可清单正当扩展——树服务为第二个钦定查询消费面，6-5b 同款演进）；③ sparse fake 返回 None 元素是畸形形态（改抛异常走 handler 真实降级分支）
- [x] 质量门禁全过：ruff 双目录 All checks passed / mypy 756 source files 零错误（基线 753+3 新文件零回退）/ 三红线 grep 零输出 / application 覆盖率 91%（≥85%——树服务 93%/用例 100%）/ 集成交付面覆盖率 82%（≥75%）/ 整体覆盖率 93%（≥80%）
- [x] 验收 12 场景全绿×6 轮稳定（S1~S12 含收尾存在性断言）+ 集成四场景双轮 + 四目录全量回归双轮（14977 passed ×2——第二轮数字见下）零失败
- [x] 全仓 mypy 口径清零（`mypy .` 1924 文件——tests 面类型修复 12 处×4 文件，全根因修复零抑制）：is_dataclass TypeIs 窄化（vo_class Any 注解+helper 签名放宽）/typing.Protocol 特殊形态不可作 issubclass 第二参（改 `_is_protocol` 标记断言——运行时等价语义）/payload dict 首分支 list 值窄化（显式 dict[str, Any] 注解）/getsource 实参联合含 str（callable 窄化局部变量）/Redis `aclose()`→`close()` ×2（对齐仓内 6-5b 探测先例形态）/验收包装 cast 契约面收窄（组合根 _SessionScopedDocumentRepository 同款注记）；修复后 mypy . 1924 零错误+ruff 全绿+受影响四文件 56 passed 零行为变

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-7-traceability-tree-display.md`
- `src/application/ports/traceability_tree.py` - 五 VO+端口契约（Task 2 循环 A）
- `src/application/services/traceability_tree_service.py` - 四段编排服务（Task 2 循环 B）
- `src/application/use_cases/get_traceability_tree.py` - 查询用例（Task 3 循环 A）
- `tests/unit/application/test_traceability_tree_service.py` - 服务单测（33 用例）
- `tests/unit/application/use_cases/test_traceability_tree_use_case.py` - 用例单测（6 用例）
- `tests/unit/architecture/test_traceability_tree.py` - 架构四验证器（11 用例）
- `tests/integration/test_integration_traceability_tree.py` - 集成四场景
- `tests/contracts/test_port_contract_traceability_tree.py` - 端口契约五断言族
- `tests/acceptance/test_acceptance_traceability_tree.feature` - Gherkin 12 场景
- `tests/acceptance/test_acceptance_traceability_tree.py` - BDD 步骤实现

**修改的文件/Modified Files (Dev Story 实施):**
- `src/application/event_handlers/chunk_indexing_handler.py` - payload 6→8 键（+page_start/page_end）
- `src/entrypoints/agent_cli.py` - trace-tree 子命令（注册块+分发+runner+打印函数）
- `src/composition_root.py` - 两注册块（+50/-0 纯新增含 import/注释——document_repository 会话包装注入；R1-F11 口径订正）
- `tests/unit/interfaces/cli/test_agent_cli.py` - CLI 扩展（12 用例）
- `tests/unit/infrastructure/workflow/test_document_tasks_index_payload.py` - payload 8 键断言扩展（新增 1 用例）
- `tests/unit/architecture/test_json_chain_of_thought.py` - EVIDENCE_PACKAGE 唯一构造位守护许可扩展（6-5b 同款正当演进——树服务为第二个钦定查询消费面）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 五条处置注记+6-7 区段两条新留项
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 状态流转注记

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.7 |
| **Story Key** | 6-7-traceability-tree-display |
| **File** | `_bmad-output/implementation-artifacts/stories/6-7-traceability-tree-display.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 6: 战略规划流程 (BLM 前两阶段) |
| **价值组** | 战略规划与审批能力（epics L2005——可信度面） |
| **优先级** | P0-7（依赖 Epic 2 Story 2.3 ✅ done + Epic 3 Story 3.8 ✅ done——epics L2017） |
| **覆盖 FR** | FR-SR-08 (P0) 展示侧语义深化（数据面归 3-8）；PRD 指标 L243/L373/L419；FR-UI-13（Epic 22 工作台证据树）后端供给 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7+12 场景钉死）
3. [x] Architecture constraints extracted 架构约束已提取（三零 Story/四段编排/端口并立正当性）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-6/6-5b/6-4）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则**：R1/R2/R3 = 创建期独立审查三轮（2026-11-05）；DR<n>-<序号> = 文档审查修订循环 Round n（DR1 = Round 1，2026-11-05——四 Agent 代码调研【归档链证据面/存储检索 payload/CLI 组合根接线/测试样板治理文档】+ 三视角并行审查【正确性一致性/可行性可满足性/科学性合理性】+ 主会话亲验裁决【total 口径采纳 kind 过滤后/limit 升 1000/synthesis 不产生 StageNode/S3 验收改树形断言】；DR2 = Round 2，2026-11-05——回归核查+组合交互面双 Agent）——两命名空间分立防混淆；**DR 行内引用的正文行号是该轮修复时点快照，不随后续修订维护**（6-6 同款惯例）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | AC-6 VC「畸形 plan_id 与 depth=0 双腿」242 断言物理不可能（`--depth` choices 在 argparse 层 exit 2 永不到用例层）且与 API 契约节钦定分工自相矛盾 | P1 | VC 改分工钦定：畸形 plan_id → `[EXCEPTION_242]` exit 1；`--depth 0` CLI 面 argparse exit 2 不走 242；depth 越域 242 归编程面用例单测（0/5 双边界） |
| R2-1 | BDD 约束行陈旧 S 编号三处矛盾（「双腿入 S12」——S12 是收尾场景无服务调用；「降级（S9/S10）」——降级在 S7）+ depth 越域 242 验收归属悬空（S1~S12 无落位） | P2 | 改「畸形 242 入 S8、CLI stderr 形态入 S10、depth 越域 242 归用例单测矩阵（编程面）」；降级引用改 S7 |
| R2-2 | VO 计数「四」vs「五」不一致（数据模型节/Task 2 标题/TDD 循环 A 三处「四 VO」vs Task 0.1/OD-4/项目结构「五 VO」） | P2 | 三处统一改「五 VO」（TraceabilityTree 根+四节点型） |
| R2-3 | UX spec L493「证据树展开<100ms」引文虚构（实读 L488-498 是竞品灵感表，全文档唯一「<100ms」在 L892 品牌模板切换）——AC-2/OD-6/调试日志三处 | P2 | 三处删除该引文；AC-2 改引 FR-UI-13 + epics Story 21.6「追溯跳转<100ms」（L3374——Web 面先例参照，注明非本 Story 门禁）；调试日志行 L493 移除 |
| R2-4 | 完成总结第 5 项勾选「Sprint status synced」时 sprint-status.yaml 实际仍 backlog | P2 | 由本轮工作流末尾同步兑现（yaml L185 backlog→ready-for-dev——勾选随同步成真） |
| R3-1 | 追溯矩阵两行集成场景编号漂移（AC-7 行④应为③——④是扩键 round-trip③是性能；payload 行⑤不存在应为④） | P3 | 两行就地订正 |
| R3-2 | 亲验组数 8 vs 9 两口径（Lessons 应用行/版本说明「8 组」vs 亲验行「9 组」） | P3 | 统一 9 组（含 3.5 payload 测试宿主定位） |
| R3-3 | 变异锚总数 9 漏计 Task 6.5 的×2（各 Task DoD 合计实为 11） | P3 | 改「11 处（Task 1×1/Task 2×4/Task 3×2/Task 5×2/Task 6×2）」 |
| R3-4 | epics L2018 引文「不依赖 6-7」非原文（实文「P0-8（不依赖 Story 6.5b）」，依赖列「依赖 Story 6.5a」） | P3 | 改准确表述：依赖列不含 6-7+括注原文「不依赖 Story 6.5b」（业务价值与 OD-1 两处+范围边界表一处） |
| R3-5 | 6-4 story 行号 ±1（L15→L14、L22→L21——引文文字逐字真实仅行号漂移） | P3 | 就地订正 |
| R3-6 | 「键恒在纪律，6-2 R1-F6」家族级编号漂移（6-2 实际 R1-F6 是 five_forces 修复；键恒在原始出处是 6-2 R1-6 state_data 七键契约——6-3/6-6 沿袭同误） | P3 | 本 Story 两处正名为「6-2 R1-6 七键契约同族」 |
| R3-7 | page 脏形态降级值措辞（6-5b 实际降 page=0（CitationEntry 语义），本 Story VO 是 int|None 降 None——防 dev 复刻 0 值漂移） | P3 | AC-3 VC 补注「降级值按本 Story VO 契约取 None 非 6-5b 的 0 值语义」 |
| R3-8 | payload 构造位行号两口径（:151-168 vs :156-168——deferred-work 台账原文后者） | P3 | 统一 :151-168；业务价值处保留台账原文口径注记 |
| DR1-1 | AC-6 正文 Then「畸形 plan_id/越域 depth → exit 1 + 242」与三处钦定分工矛盾（R1-1 修复只达 VC 未达正文——CLI choices 物理拦截越域值到不了用例层） | P1 | 正文改分工钦定：畸形 plan_id → exit 1 + stderr 242；CLI 面越域 argparse exit 2 不走 242 |
| DR1-2 | depth=1 值域合法但行为全文未定义；L258 声称「归单测矩阵」而 Task 2 红/覆盖率均只列三档——声称落位不存在 | P1 | AC-2 And 补 depth=1 语义（仅结论层/判 run 照常/零解析）；Task 2 红③与覆盖率关键路径改四档（depth=1 用例真实落位）；AC-2 VC 补第四档 |
| DR1-3 | 「Qdrant 点 8 键预置/读回」与实存冲突——infra upsert 追加 created_at（vector_storage.py:85 实存 9 键），exact set 断言必红；另防御注记缺失（裸 client 预置被 MD5 归一漏查 6-5b 已踩坑/point["id"] 是 MD5 整数） | P1 | 构造面 8 键 exact（单测）与实存 9 键（读回 8 业务键值级+created_at 存在不计）口径分立；预置纪律/Task 5.2/5.4/回归面四处同步；执行约束补「禁绕 L3VectorPort 裸 client」防御注记 |
| DR1-4 | 「archived_at 显式先后构造」与 archive_plan 自动 now（:107-118 签名不可外传）矛盾——钦定预置通道上不可实现 | P1 | 改「同 stage 连续两次直交（PG 往返毫秒级间隔+Linux µs 分辨率稳定非并列）+_make_material(index=) 不同 chunk_id 判别锚」；AC-4 VC/隔离表/Task 5.3 三处同步；单测面保留实体直造显式先后（mock 返回可控）口径分立注记 |
| DR1-5 | S3「get_point/find 零调用 call_order」与「验收禁 mock」正面冲突——真实端口无调用记录面，断言物理不可写 | P1 | S3 验收改树形断言（depth=2 StageNode.children==()/depth=3 零 DocumentNode）；call_order 零调用断言归 Task 2 单测矩阵（AsyncMock 天然可写）；AC-2 VC 同步 |
| DR1-6 | S9/S10 CLI 面 resolve 默认 collection "documents" 与独立测试 collection 钦定冲突——CLI 查默认 collection 找不到预置点假 point_missing 断言必红 | P1 | CLI 直调前 monkeypatch BLM_SEARCH_COLLECTION+双清钦定（组合根 lambda 在 resolve 实例化时读 env——注册在 bootstrap/取值在实例化机制实证）；调用面矩阵/隔离表同步 |
| DR1-7 | 集成场景④经真实 ChunkIndexingHandler 必需 embedding（构造必填+逐批 embed_documents）与「零 Embedding」矛盾；归档预置照抄 6-4 轻装配会引入 Fake embedding+真实 MinIO 依赖（minio marker 面缺失则真连失败） | P1 | 场景④显式 Fake-embedding 豁免注记（6-5b _make_fake_embedding :685-696 外部 SaaS 豁免先例）；归档预置钉死 StrategicArchiveService 全 None 依赖构造（纯 L2——archive_plan 对 None 优雅跳过实证）；「零 Embedding」措辞改「仅场景④豁免」 |
| DR1-8 | 端口契约表「StrategicArchiveServicePort」仓内不存在（全仓 grep 零命中；组合根 :2216 interface=具体类 StrategicArchiveService）——dev 按名导入第一步 ImportError 且可能反向发明 Protocol 撞「禁本地 Protocol」红线 | P1 | 表/复用清单/执行约束/R2 落点四处正名具体类注入（6-5b :42/:119 先例）；Task 2 红 spec 注记（AsyncMock spec 具体类可行）；表补 ChainOfThoughtArchiveServicePort 行（正文清单一致性） |
| DR1-9 | TraceabilityTree.degraded_stages 键语义全 Story 零定义（exact set 断言锚空转）；顶层 query_archive 异常空树与「plan 真无归档」空树不可区分（皆 total=0）——违反自述「失败可观测」原则（树是唯一产物，6-5b 附录 C 先例报告主体还在不适用） | P1 | TraceabilityTree 6→7 键新增 build_degraded: bool；degraded_stages=含 ≥1 非 resolved 后代的采纳 stage 值元组（升序去重）；CLI 空树分立输出（⚠ 查询失败 vs 无归档行）；AC-5 正文/VC/S7/S8/单测⑤/变异锚联动 |
| DR1-10 | 端口/服务/用例签名未标 async——三依赖 query_archive/get_point/find 全 async（D1 实证），同步签名物理不可实现 | P1 | async def build_trace_tree / async def execute / 服务全方法 async 钦定（GetBlmChainTraceUseCase 直系同构）；端口契约节/Task 0.2/锚点表同步 |
| DR1-11 | last-write-wins 并列非确定（单键时间戳仅偏序——仓储 order_by 无二级排序键，DB 并列返回序不定，与「唯一无参数确定性规则」自述矛盾）；archived_at=None 行地位未定义 | P2 | 并列以 archive_id 决胜（key=(archived_at or _EPOCH_FLOOR, archive_id) 全序零参数）；None 行回落 epoch 永不获胜（6-4 _EPOCH_FLOOR 同款先例——全 None stage 采纳 epoch 行）；OD-5/AC-4 同步+「审计序 vs 当前态投影」两读面注记 |
| DR1-12 | total_archives 口径未钉死（kind 过滤前后悬空——S5 夹具不可判别/S6 无断言；含非链行则对照信号混入两种现象）；「截断可观测」言过其实（total≤limit 封顶与恰满不可区分）；L88 括注误导 S6 构造（其他 ArchiveType 行进不了 EVIDENCE_PACKAGE 查询结果） | P2 | total=kind 过滤后思维链候选行数（对照纯化为 run 压制单现象——主会话裁决）；adopted=判 run 后采纳数；limit 64→1000（clamp 上限——正确性窗口非 6-5b 展示窗口）+total==1000 饱和探针注记；L88 括注改「EVIDENCE_PACKAGE 且 kind≠CHAIN_ARCHIVE_KIND」+S6 补 total==3 断言 |
| DR1-13 | synthesis 行双呈现未定义——八值字面含 synthesis 会产生 StageNode，而结论层 summary 又取自同一行（同数据树内两处）；stage_count 是否含 synthesis 未定义 | P2 | 钉死 synthesis 不产生 StageNode（结论层即其呈现位——conclusions 联展即根 summary）；分析层七值域；stage_count=分析层节点数（全 run=7）；AC-1/StageNode/OD-4 三处同步 |
| DR1-14 | StageNode 三键数据源链未钉死——chain 五键无 summary/degrade_reason（degrade_reason 仅 gap payload/六子降级信封有；六子正常 {summary,findings} 无）；源键名是 reflection 非 reflection_excerpt；gap payload 无 summary 键 | P2 | Task 0.1 三型分支钉死：summary（六子取 payload.summary/gap 无 summary 降 chain.input_summary/解析失败同降）；degrade_reason=payload.get("degrade_reason","") 与 degraded 布尔独立；reflection_excerpt=chain["reflection"][:200]；tools_used 单源 chain |
| DR1-15 | 五处小矛盾：AC-1 键枚举不齐（StageNode 漏 children/DocumentNode 漏 jump_ready）；验证器字母漂移两处（零 publish 是 B 非 C）；追溯矩阵 AC-4 行 2.1~2.3 应为 2.4~2.6；AC-2「非整数」无测试落位；AC-5 VC「CLI stderr 形态」越位（R2-1 残留） | P2 | 五处就地订正（键枚举补齐/字母 B/区间 2.4~2.6/删非整数/VC 归 AC-6）；--stage「全量构建」措辞钦定「按 --depth 构建后过滤」 |
| DR1-16 | 「PG documents 行经 document_repository 直造（6-5b 预置形态）」归因错误——6-5b 实况 AsyncSession+原生 SQL INSERT（:905-935）不经 repository；且 metadata 缺 storage_object_key 则 jump_ready 假 False（6-5b 预置只含 chunks） | P2 | 改「原生 SQL INSERT 定向预置（6-5b 样板直系复刻）」；metadata 钉死 chunks+storage_object_key 两键；预置纪律/Task 5.2/锚点表同步 |
| DR1-17 | application ≥85% 的「-o addopts 剥离单跑」完整命令未写字面量（dev 自行拼装）；顶层容错分支在真实服务集成无触发面（真实 PG 不抛）——收口争议未预防 | P2 | 剥离单跑完整命令补字面量；「容错分支归单测承载」口径预声明（覆盖率要求节+集成覆盖率行） |
| DR1-18 | SINGLETON 捕获 SCOPED 三依赖未声明（strategic_archive_service/l3_vector/document_repository 全 SCOPED——长驻面 6.5b-DF4 会话抖动显形风险）；search_collection「默认值+env 传导」合流形态无完全同构先例未注记 | P2 | OD-11 补捕获声明（CLI 一次性进程+双清下无故障面——6-6 checkpoint_service 同款先例）+7-2 长驻面改 SCOPED 触发器注记；合流形态可行性注记 |
| DR1-19 | 「chunk_indexing 键集断言适配是 Task 1 唯一预期修改面」前提不符——实测四同族文件零 payload 键集 exact set 断言（回归风险高估、方向无损） | P2 | 回归面措辞改「零适配预期实证（四文件零键集断言）」；Task 1.0/1.4/DoD/测试分类表/项目结构/风险①六处同步；断言面扩展是新增非适配 |
| DR1-20 | 行号微偏五处：StrategicArchive :56-69→:55-73（键位 :61-62/:69）；_assemble_archive_only :1102→:1106；StepSemanticConfig :137-156→:136-157（display_name :153）；checkpoint-show 注册块 :435-453→:435-452；双清先例 :145-148→:144-148 | P3 | 锚点表五处订正（附键位/形态精化：五步定式 :1275-1308/13 子命令清单） |
| DR1-21 | 先例引用精确化三处：depth 守卫直系先例应指 GetBlmChainTraceUseCase 用例层（IsolationSwitchLogQuery 是 Query VO post_init 非用例层；值域枚举形态是仓内新形态）；「CLI 直 import use_cases」无先例（既有形态=ports import+resolve 字符串）；6-6 OD-2 转述添加语「查询面零 publish」（6-6 实文无此措辞且有 CheckpointRecovered 真实发布） | P3 | AC-2 守卫先例改指用例层+新形态注记；API 契约节补 CLI import 纪律；OD-2/零事件行转述精确化（「零新增领域事件——CheckpointRecovered 首激活」+「先例族」措辞） |
| DR1-22 | 引用与形态注记四处：interface-design.md 实际路径 docs/architecture/（非 planning-artifacts/）；argparse choices 仓内先例均 str 元组（int choices 无先例需注转换位）；「raw-documents :161 单源」措辞过宽（minio_document_storage 7 处字面量——应限定「解析下载路径单源」）；display_name「import 单源映射」与三源常量族事实不符 | P3 | 调试日志补路径；API 契约补 choices=str 元组+int 转换；AC-1 桶名限定措辞；锚点表/Task 0.2 三源拼装钉死（无单一映射表） |
| DR1-23 | 杂项口径十四处：AC-1 去重 find 断言归单测注记；S12「src 4 新文件」与 File List 3 新建不符；S12 红形态措辞（Then 断言步非 Background）；R4N-1 注记位在 6-5b story 非 deferred-work；四层架构表 interfaces 行与 CLI 落位 entrypoints 不符；「CLI 两 exit 形态」与三 exit 码口径；ChunkNode 页码数据源（Qdrant payload 通道）未注；N≤40 缺写侧锚（_MAX_EVIDENCE_TEXTS=5）与契约无上限声明；串行缺触发器注记+get_point 不去重取舍；bbox dict 是 frozen 逃逸口；「降级三态」术语易误读；jump_ready 半跳转 YAGNI 论证未落 docstring；or.md「每层三元组」适配论证缺失；sprint-status 调试行 backlog 描述过时 | P3 | 十四处就地订正/注记落档（各落位见正文 DR1-23 标记）；「三态」改「链路三态两层承载」；MappingProxyType 钉死；S12 断言对象以 File List 为准 |
| DR2-1 | Round 1 修复正文标记使用未定义编号 DR1-30/DR1-37（修复表仅定义到 DR1-23）——8 处悬空引用破坏可追溯性 | P1 | 全局订正：DR1-30→DR1-22（display_name 三源）、DR1-37→DR1-14（三键数据源链）——sed 全局替换 8 处清零 |
| DR2-2 | DR1-7（场景④ Fake embedding 豁免）与三处绝对化反声明互斥——禁止行为行/其他约束/外部服务隔离表仍写「无 LLM/Embedding 豁免面」「零 Embedding 依赖」，钦定红线与钦定测试设计互斥（dev 必违其一） | P1 | 三处改分立口径：验收全真实零 LLM 零 Embedding；集成仅场景④ Fake-embedding 豁免（AsyncMock spec——外部 SaaS 先例）；探测面「少两项」 |
| DR2-3 | DR1-6（monkeypatch BLM_SEARCH_COLLECTION 桥接）物理上够不着 DR1-7 打开的 handler 写通道——`chunk_indexing_handler.py:215` 硬编码 `upsert_points("documents", ...)`（主会话亲验）：场景④ 点必落共享 "documents"，按「独立 collection 读回」假红、按「整 collection 删」摧毁其他测试预置 | P1 | 场景④ collection 偏离钦定：读回 `get_point("documents", chunk_id)` + 清理 `delete_points` 定向点删（:70 在位）禁整删；隔离表 Qdrant 行补例外注记 |
| DR2-4 | DR1-9（build_degraded/degraded_stages 新键）无变异锚——违反自述「新断言未经突变验证即视为不可信」；DR1-2（depth=1）判别锚形态未钉（`>=3` 改 `>=2` 变异下 depth=1 断言仍绿） | P1 | Task 2 DoD 变异×4→×5（+build_degraded 恒 False→空树分立场景红）；depth 锚改「`>=3` 改 `>=1`」一锚双档形态钉死；总数 11→12（Lessons 行同步） |
| DR2-5 | DR1-19「零适配预期」三处残留：测试分类表回归行/Task 1.0「预期适配点清单」/项目结构 acceptance 括注（与同块已修口径自相矛盾） | P2 | 三处就地改「零适配预期——四文件零键集断言实测；唯一新测试面=新增 8 键断言」 |
| DR2-6 | DR1-7 引用的 6-5b `_make_fake_embedding` 恒返长度 1（单文本形态）× handler 逐批消费（`j >= len(dense_vectors): break`）——直抄先例则预置 ≥2 chunk 时第 2+ 点缺 vector 不可预期 | P2 | Task 5.1/5.4 补「fake.embed_documents 按批次长度等长返回（side_effect 按 len(batch) 构造）——非 6-5b 单文本形态直抄」 |
| DR2-7 | DR1-9（CLI 空树双形态输出）无断言落位——S8 空树腿编程面/S9 预置非空/S10 过滤畸形，build_degraded=True 输出行成断言孤儿（顶层容错真实服务无触发面） | P2 | Task 3 CLI 红清单改「空树双形态输出断言」（stub VO 构造两腿各自精确匹配——CLI 面唯一可测位） |
| DR2-8 | 隔离表「archive_repository 既有 delete 通道」实名不存在——`PostgreSQLArchiveRepository` 方法面仅 save/find/find_for_update/mark_stale/list_by_plan/list_by_archive_type/count（无 delete；服务亦无）——「命名通道失实」第三例（DR1-8/DR1-16 同族） | P2 | 钉死唯一通道：原生 SQL 定向 DELETE（6-5b `:731/:795` 先例——SELECT 收集 archive_id 再 ANY(:ids) 或按 plan_id 直删）；隔离表归档行清理行重写 |
| DR2-9 | 杂项订正簇 A：AC-1 find 恰一次断言归属未注（验收面无调用记录面）；AC-2 Then 裸「call_order 断言」与 VC「归单测」注记形态不一致；追溯矩阵 AC-2 行残留「三档」；锚点表 STAGE 行八值直述（应为 StageNode 七值域来源） | P3 | 四处就地订正（AC-1 补归属注记/Then 补「归单测」/矩阵行改四档/STAGE 行补七值域来源） |
| DR2-10 | 杂项订正簇 B：「降级三态」旧术语 4 处残留（AC-5 Then/测试分类表/追溯矩阵/Lessons）；S2 场景 stage_count 无值级落位（DR1-13 后期望值已变）；锚定义务表「七连纯生产方」把 6-7 错计生产方序列；DR1-23 行内「十二处」vs「十四处」自相矛盾；端口表补行标注归属错（DR1-15→DR1-8）；CLI 层守卫需 import domain 异常未在合规枚举（字面读误判样板越线）；集成 pytestmark 未钉 minio 继承面（6-5b 集成含 minio marker 整块复刻则引入不必要耦合） | P3 | 八处就地订正（术语→「链路三态两层承载」×4/S2 补三形态 stage_count 钉死/「六连+双向皆无新形态」/十二→十四/归属改 DR1-8/API 契约补 domain 异常 import 不在禁列+双防线同形态说明/Task 5.1 补无 minio marker） |
| DR3-1 | root.children（StageNode）挂接顺序全 Story 未定义——底层仓储返回序 archived_at DESC（archive_repository.py:246 实证）直接透传则 CLI「输出即契约」行序颠倒（完整 run 下六子倒序 performance_gap 殿后）；两种实现（透传遍历序/自行规范序）都满足现有文本——期望不可唯一写，S1/S9 序敏感断言随实现选择翻转 | P1 | 钉死 root.children 序=BLM 流程规范序（performance_gap 在前+六子按 MARKET_INSIGHT_STEP_CONFIG 枚举序——与 display_name 三源同族零新常量；服务必须重排禁透传）；AC-1/AC-6/S1/S9 断言面注记+Task 2 红矩阵补乱序输入→有序 children 断言 |
| DR3-2 | synthesis 行多条时结论层 summary 取哪条未定义（重跑含 synthesis 场景链路 A 直接触发——「取最新行」两解皆合理）；synthesis 行是否计入 adopted 未钉（全 run adopted=8 还是 7——S5 预置无 synthesis 不暴露该歧义） | P2 | 钦定：synthesis 行入同一 stage 分组 last-write-wins（最新 synthesis 行供 root.summary）+其采纳行计入 adopted（全 run total=8/adopted=8、stage_count=7）；AC-1 补注+Task 2 单测②补双 synthesis 行取新一腿 |
| DR3-3 | AC-7 VC「混入失效引用后占比值级断言」是断言孤儿——12 场景/单测/集成四场景零落位（DR2-7 同族复发） | P2 | 落位钦定 S7：预置含失效引用树上 resolved/(resolved+missing) 节点统计值级断言（如 2/4）；AC-7 VC/AC-5 VC/S7 场景表三处同步 |
| DR3-4 | kind 合法但 stage 越七值域的链行行为未定义——进分组则 display_name 三源拼装查无此键 KeyError 炸树（违「树整体不因单点失效失败」自述）；chain dict 缺三键的兜底未定义 | P2 | 钦定：stage∉七值域链行不产生 StageNode——计入 total 不计 adopted（收集段读侧过滤不抛，同 kind 过滤语义）；chain 三键 .get 缺省（空元组/空串/同降 input_summary）注记进三键数据源链；Task 2 红①补脏 stage 腿 |
| DR3-5 | S7 双腿组织形态不唯一——AC-5 VC「两态各一专属场景」与场景表「单场景双腿」冲突（照 VC 拆两场景则 13 场景破 12 全绑定）；两腿共享/独立 plan 使 degraded_stages 期望值漂移 | P2 | VC 改「两态各一专属断言段」；钦定 S7=单场景单 plan、两 stage 各带一失效、degraded_stages==(stage_a, stage_b) 升序值级（stage 命名保升序判别力） |
| DR3-6 | S1/S2/S4 预置形态未钉死（「≥2 stage」范围值与自述「禁范围值进入后续 Task」张力；S5 逐行钦定形成钉死密度不对称）：S1 两 chunk 同/异文档未定且「同文档嵌套重复形态」无验收断言锚；S2 腿型指派未定；S4 脏 chunk 数量未写 | P3 | 钦定：S1=2 stage 各 1 chunk 同一 document_id（顺带收编「两 DocumentNode 值等且各在位」验收断言锚）；S2 腿1=synthesis+gap（stage_count==1——DR1-13 错实现给 2 必红）腿2=gap-only（==1+summary==""）；S4=1 stage 2 chunk（1 干净+1 脏）——AC-1 VC/AC-3 VC/场景表落位 |
| DR3-7 | `_run_trace_tree_cli` 签名与 depth str→int 转换位未钉（S9/S10 直调传 "4" 还是 4 两解）；CLI 输出两小空档：切片行 page 取源未注（ChunkNode.page_start vs DocumentNode.page）；--stage 过滤后结论层首行保留与否未写 | P3 | API 契约/AC-6 钦定：runner 签名 (plan_id: str, depth: str, stage: str\|None) -> int（样板同构原始字符串+runner 内 int(depth)）；切片行 page=ChunkNode.page_start；--stage 过滤保留结论层行 |
| DR3-8 | 「conclusions 联展」联结格式未定义（"\n".join vs "；".join 两实现皆合理——单测期望值无锚）；结论层 final_answer 解析失败分支缺失（StageNode 有「解析失败同降」结论层没有） | P3 | 钉死联展格式 `"\n".join(conclusions)`（list 保序；非 list/空/解析失败降空串——与 DR1-14 三型分支对齐补结论层失败分支）入 AC-1/Task 0.1 |
| DR3-9 | AC-5「单依赖异常按节点捕获降级+warning」无测试锚——红矩阵③④只列 None 返回态（AsyncMock side_effect=Exception 与 return_value=None 是两条分支，异常路径零覆盖） | P3 | Task 2 红③④各补 side_effect=Exception 腿→对应 missing status；覆盖率关键路径行补「None 返回与 Exception 抛出两分支」 |
| DR3-10 | S12「断言对象以 File List 节为准」口径过宽——File List 17 项含两 md 台账+故事文件自身（三者恒真/修改不可断言——dev 照字面写三条恒真断言，违「断言必须真实」精神）且与随附 15 项计数不一致 | P3 | S12 措辞改「src/测试 15 项存在性为准；两 md 台账与故事文件不入断言面（修改性断言物理不可写——Task 0.7/7.5 操作面承载）」 |
| DR3-11 | S5 断言「summary/chain 取新行值级」中 chain 非 VO 键（StageNode 无 chain 键——实际指 chain 派生键未收敛）；S5 行型未钦定（gap/六子判别锚书写面不同） | P3 | VC 改「summary+tools_used（+reflection_excerpt）取新行值级」+行型钦定 gap 型（input_summary 判别链最短） |
| DR4-1 | sprint-status.yaml 6-7 行注记含创建时点旧数字（键契约 6/5/9/6/9/变异锚 11 处/Fixes 13 项+「降级三态承载」「四连先例」旧口径词）——被三轮 44 项修订实质超越，dev 快读 yaml 有按 6 键 VO 开工的误导面（R4 纯验证轮唯一发现） | P3 | 收敛提交清偿：注记五片段刷新（7/5/9/6/9+build_degraded/degraded_stages 注/12 处/57 项累计口径/链路三态两层/先例族）+多 run 与 CLI 桥接等 DR 期裁定同步入注 |
| DR5-1 | R6 模板合规行「本 Story 零 LLM 零 Embedding 豁免面」——DR2-2 分立口径第四处漏网（主语应收窄验收装配面；与集成场景④ Fake 豁免字面互斥） | P3 | 改「验收装配面零 LLM 零 Embedding（集成场景④ Fake 豁免——DR1-7）」（R5 终审残留扫描发现，就地清扫） |
| DR5-2 | AC-5 标题「降级三态容错」未升级新口径（标题位漏改——DR1-23/DR2-10 改了正文四+一处非标题位） | P3 | 标题改「降级链路三态两层承载与空计划幂等读」（R5 发现，就地清扫） |
| DR5-3 | 场景分化维度表 S1 行仍「≥2 stage 预置」范围值、S4 行未带钉死形态——DR3-6 声称「场景表落位」未兑现（钉死仅在 AC-1/AC-3 VC；与「禁范围值进入后续 Task」自述有张力） | P3 | S1 改「2 stage 各 1 chunk 同一 document_id」+S4 补「1 stage 2 chunk——1 干净+1 脏」（R5 终审 git diff 实证发现，就地清扫） |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-11-06（Round 1 起）
**审查模式:** 暂存 diff（19 文件）四视角并行调研（A 树服务编排/B 接线层/C 测试质量/D payload 传播红线）+ 主会话逐条复核定谳 + 双评审员方案评审（非「优秀」不落码）+ 五轮循环（C1~C5）

#### 需决策 Decision Needed

- [x] R1-保留-1：架构 A :84「application in path.parts」/C :148 同源断言——调研报恒真微瑕，主会话复核**改判保留**：对常量漂移有防呆判别力（常量被误改指向他层时红），非遗漏（对视角C P3-5 部分改判——仅契约 :36 死断言删除）

#### 已修复 Patch

- [x] R1-F1（P2·视角A）：服务六处 `(x or {})`/isinstance 混用守卫统一为 `_as_dict()`（非 dict 脏形态降空 dict）——消除 decision_basis/assumptions 为 truthy 非 dict（JSONB 外部可写面）时 AttributeError 逃逸（违反端口「本方法不抛业务异常」+「树整体不因单点失效失败」）；+2 单测（非 dict decision_basis 排除出 total 不炸/非 dict assumptions 降 evidence_count=0 不炸——变异①实证红）；+1 升格锚（payload 缺 document_id → chunk 保持 resolved 无文档子节点+find 零调用——评审员②建议）；+4 docstring 注记（哨兵复用/version 双口径/payload 无 document_id/空串 summary 回退）+ `_empty_tree` docstring 失实修正（「共用」→顶层降级专责——真空树走正常构造路径）
- [x] R1-F2（P2·视角C）：bbox「透传不合成」断言收口——验收 S4 恒真形态 `is None or isinstance(dict)` 改 `is None`（预置 8 业务键无 bbox——合成坐标变异②实证红）+ 单测 None 分支锚（`assert doc.bbox is None`——全仓首个「不合成」判别锚；dict 分支 :758 值级锚既有）+ AC-3 VC 行收口注记（防写回恒真形态——评审员②传播面）
- [x] R1-F3（P3·视角B）：CLI 空树分支三分化（build_degraded=True→⚠；total==0→「该 plan 无归档行」；total>0 无分析层节点→归档对照行+「depth 折叠或 stage 越域」提示）——消除 depth=1 有归档/全脏 stage 两形态下输出假话「该 plan 无归档行」（DR1-9 读模型诚实性的 CLI 面补全）+ 单测第三腿（折叠 stub 断言对照行出现+「无归档行」不出现）+ AC-6 正文与 Task 3 红清单三腿同步（评审员②传播面）
- [x] R1-F4（P3·视角C）：验收+集成 teardown 归档 DELETE 与 PG DELETE 拆独立 try/except（对齐 Subtask 0.5 钦定三步各步独立——消除归档步失败连坐 PG 清理；集成侧原无 except 异常直接上抛一并回归钦定形态）
- [x] R1-F5（P3·视角C·评审员②升级）：架构 B 事件构造 AST 扫描升级为 **DomainEvent 子类名全集比对**（运行时递归 `__subclasses__()`+包级导入注册+Name/Attribute 双形态）——原方案补后缀启发式对 56 事件类覆盖率仅 ~15%（RAGIndexed 不命中四后缀——钦定变异例仍绿被证伪；实测全集为 53——R1-F5 记 56 为当轮口径偏差，R2-F1 补注）；`events.RAGIndexed(...)` 注入变异③实证红
- [x] R1-F6（P3·视角C·评审员①修订）：架构 D 注册锚改精确形态 `'add_parser(\n        "trace-tree"' in source`（删 or 右支恒真吞噬）——原方案 `count>=2` 被证伪：`"trace-tree"` 字面量实为 3 处（:526 注册/:1417 异常 context/:2026 分发——删注册后 count=2 仍绿漏报）；分发锚由第二测试独立承载
- [x] R1-F7（P3·视角C）：契约测试删恒真死断言 `spec.version.startswith("v")`（前一行已 `== "v1.0.0"` 精确断言）
- [x] R1-F8（P3·视角C）：payload 新增用例三裸 `AsyncMock()` 补 `spec=L3VectorPort/EmbeddingServicePort/DocumentRepositoryPort`（仅新增行——宿主 3.5 既有形态不触碰，Surgical）
- [x] R1-F9（P3·视角B）：`get_traceability_tree.py` 补 `__all__ = ["GetTraceabilityTreeUseCase"]`（直系先例 get_blm_chain_trace.py:61 对齐——评审员①核 11/17 混合惯例，低价值微项保留）
- [x] R1-F10（P3·视角C）：`_match_page`「匹配到但页码非正整数（字符串脏值）」子分支补单测锚（test_page_match_and_dirty_chunk 扩 chunk-badpage 腿）+ `test_guard_order_uuid_before_depth` 改名 `test_combined_invalid_uuid_and_depth_raises_242`（名实相符——顺序对调用方不可观测，docstring 同步）
- [x] R1-F11（P3·视角D/C）：故事文件「40 行纯新增」三处订正实测口径（+50/-0——File List/完成清单内联勘误/sprint-status）+ Task 5.5「depth 懒加载破坏→call_order 红」归属措辞澄清（集成无 call_order 面——DR1-5 单测承载，锚活）

#### 已推迟 Defer

- [ ] （Round 1 无 defer 项——P3 全数清偿或保留改判；后续轮补充）

**Round 2（回归核查双 Agent——Agent E「修复的修复」+ Agent F 传播完备性/组合交互，2026-11-06；快评单评审员裁定优秀后落码）：P0:0 / P1:0 / P2:0 / P3×4**

- [x] R2-F1（P3·AgentE）：R1-F5「全集比对」声称过宽——`__init__.py` re-export 面仅收集 47/53（漏 saga/sandbox/tool_chain/tool_schema 四模块 6 类：SagaStatusChanged/SandboxSessionStarted/SandboxSessionTerminated/SandboxExecutionFailed/ToolChainExecuted/ToolSchemaValidationFailed）；修复=测试内 `pkgutil.iter_modules` 强制全子模块导入（实测 53 全集——根因修复对齐声称非弱化）+ docstring 改写（失实的「包级 import 确保全注册」句）+ 双防线注记（验证器 C import 白名单兜底——构造必先 import 被 :179-184 拦截）
- [x] R2-F2（P3·AgentF）：验收/集成 teardown docstring 声明序「归档/Qdrant/PG」与实现执行序「归档→PG→Qdrant」互换（三处：验收 :457/集成头注/故事 :265 预置纪律行）——docstring 就实现非反向（事务性删除先于 collection 整删是合理序；「三步各步独立」钦定不含顺序约束）
- [x] R2-F3（P3·AgentE·登记不落码）：`--stage` 过滤零命中时输出仅结论行+归档对照行+零分析行、无「零命中」提示——设计空白观察：AC-6 VC 仅要求「其余 stage 零输出」、DR3-7 仅钦定保留结论层行、:114 明文服务端过滤 YAGNI；归档对照行计数已给自判材料——YAGNI 裁定登记留痕
- [x] R2-F4（P3·AgentF·零动作）：R1 台账两处行号快照漂移（:1417/:2026→:1420/:2029 等——R1 落码自身致偏）——适用 :815 快照惯例（「行内引用行号是修复时点快照不随后续维护」），计数与存在性均准确，零动作

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行文档审查修订循环（参照 6-6 五轮形态——R1~R5 五轮收敛定稿 v1.4.0：57 项累计修复+证伪留痕 26 组+严重度递减链 P1 10→4→1→0+零 P0/P1 残留）+ story-template 合规人工核对（R4 三轴/R5 六节终审承载——人工按模板清单最终核对仍建议在 dev-story 前过目一遍）
- [x] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.4.0
**创建日期/Created:** 2026-11-05
**最后更新/Last Updated:** 2026-11-05
**更新说明/Description:**
- v1.4.0: 文档审查 Round 4 纯验证 + Round 5 独立终审**五轮收敛定稿**——R4 三轴全过（epics 需求覆盖 6/6 零遗漏零未声明超范围+锚点存续 24/24 精确命中当前 HEAD 零漂移+门禁结构 7/7）+DR4-1（P3：sprint-status 注记旧数字——本提交清偿）；R5 独立终审（新鲜上下文不轻信自报）六节全过（周期闭合零游离/关键修复双向取证 12/12 正文在位/残留 13 词根扫描 10 零残留+3 P3 就地清扫 DR5-1~3/红线零残留/收敛判据通过/R4 留项处置核验）。
  **收敛声明**：①周期形态=create-story（四 Agent 调研+主会话亲验 9 组锚点+独立终审 13 项）+文档审查修订循环五轮——R1 四调研×三审查/R2 回归+组合双 Agent/R3 单深度推演/R4 纯验证/R5 独立终审；提交链 c1fc8092→0b5abdc9→2f42ff7e+本收敛提交，故事变更零游离。②累计修复 57 项=创建期 13（P1×1+P2×4+P3×8）+修订循环 44（DR1×23 簇【P1×10+P2×9+P3×4 簇】/DR2×10【P1×4+P2×4+P3×2 簇】/DR3×11【P1×1+P2×4+P3×6】+DR4×1/DR5×3），Docs Review Fixes 表 57 行双向对码全在位。③严重度递减链成立：P1 10→4→1→0、P2 9→4→4→0、P0 全程零——实施规范面零 P0/P1 残留。④证伪留痕 26 组（R2 8+R3 18）——零事实性错误存留。⑤锚点精度 24/24（含并行会话期零漂移）+基准 HEAD@420c8cdc+Task 0.8 实施期复核双保险。⑥红线零残留（三红线声明/noqa 禁令/AI 署名禁令+周期提交逐条核验）。⑦DR4-1 清偿随本提交落地（sprint-status 注记刷新 7 键/12 处/57 项+两旧口径词）。⑧**放行结论：Status ready-for-dev、12 场景全绑定、键契约三处一致（7/5/9/6/9）、命令字面量在位——dev-story 放行判据通过，可进实施**。
- v1.3.0: 文档审查 Round 3（单 Agent 深度推演——12 场景期望唯一性三轴推演+三条长链路时间线全推演+Task 0→7 依赖干跑+VO 构造终态）——DR3-1~DR3-11 共 11 项：P1×1【root.children 挂接顺序未定义（仓储 archived_at DESC 透传则 CLI 输出即契约行序颠倒——钉死流程规范序+服务必重排+乱序输入单测锚）】+P2×4【synthesis 多行决胜+adopted 计数（入同一分组+计入 adopted——全 run 8/8/7）/AC-7 占比断言孤儿落位 S7/stage 越七值域链行 KeyError 面（读侧过滤+chain 三键 .get 兜底）/S7 双腿组织形态与 degraded_stages 期望钉死】+P3×6【S1/S2/S4 预置形态钉死（同文档嵌套重复断言锚收编/腿型指派/1 干净+1 脏）/CLI runner 签名+page 取源+--stage 保留结论层/conclusions 联展格式 "\n".join+结论层解析失败分支/AC-5 异常路径测试锚（side_effect 两分支）/S12 断言口径 15 项/S5 判别锚 chain 派生键+gap 型钦定】；**推演排除留痕 18 组**（S3 树形断言可写/S5 旧行无需预置点/S6 非链行自由构造/S8/S11 口径齐备/Task 0→7 依赖闭合/提交批次缺席属仓惯例/VO 构造面完整/archived_at 非并列成立/tiebreak 不受 DESC 序影响等——零事实性错误，基础事实层经 44 项修复后高度可信）
- v1.2.0: 文档审查 Round 2（回归核查+组合交互面双 Agent 并行——DR1 修复传播完备性逐项对码 + 多修复组合交互推演+主会话亲验 handler:215 硬编码 collection）——DR2-1~DR2-10 共 10 项：P1×4【悬空编号 DR1-30/37×8 处全局订正/「无 LLM/Embedding 豁免面」三处与场景④ Fake 豁免互斥（钦定红线 vs 钦定测试设计——分立口径化）/handler 硬编码 "documents" × collection 单源互斥（场景④ 偏离钦定：读回 documents+delete_points 定向点删禁整删）/变异锚缺口（build_degraded 锚补位+depth=1 一锚双档形态钉死——总数 11→12）】+P2×4【DR1-19 三处残留/6-5b fake 单文本形态×handler 批量消费（按批次等长返回注记）/CLI 空树双形态断言孤儿（Task 3 红清单双腿）/archive_repository 无 delete 方法实名失实（原生 SQL 唯一通道钦定）】+P3×2 簇【杂项 A×4/杂项 B×8——三态术语×4/S2 stage_count 三形态/七连句正名/行内计数矛盾/端口表归属/CLI 守卫 import 措辞/集成无 minio marker】；证伪留痕 8 组（limit 1000×断言/monkeypatch 顺序/变异总数/S2 自洽等——推演排除不成立项）
- v1.1.0: 文档审查 Round 1（D1 四 Agent 并行代码调研【归档链证据面/存储检索 payload/CLI 组合根接线/测试样板治理文档】+ D2 三视角并行审查【正确性一致性 P1×4+P2×7+P3×9/可行性可满足性 P1×5+P2 若干/科学性合理性 P1×1+P2×3】+ 主会话亲验裁决四项【total 口径采纳 kind 过滤后/limit 64→1000/synthesis 不产生 StageNode/S3 验收改树形断言】——DR1-1~DR1-23 共 23 簇：P1×10【AC-6 正文越域残留/depth=1 语义空洞/payload 实存 9 键 created_at/archived_at 显式构造矛盾/S3 验收禁 mock 冲突/CLI collection 桥接/场景④ Fake embedding 豁免/StrategicArchiveServicePort 正名具体类/build_degraded+degraded_stages 语义钉死/async 签名】+P2×9【tiebreak archive_id 全序/total 口径+limit 1000/synthesis 单呈现/三键数据源链/五处小矛盾/PG 原生 SQL 归因/覆盖率命令字面量/SINGLETON 捕获声明/零适配实证】+P3×4 簇【行号×5/先例引用×3/引用形态×4/杂项×14】；TraceabilityTree 6→7 键；四条对标格言入档【读模型诚实性/确定性要求全序/截断可见性最低标准/树不分页】）
- v1.0.0: 创建故事文件（四 Agent 并行调研【BBox 溯源数据面/结论证据链/验收测试样板/架构治理】+ 主会话亲验 9 组关键锚点+独立审查 Agent 终审【代码事实对码全命中/1 P1+4 P2+8 P3 修复应用——depth 越域 CLI/编程面分工/S 编号残留/UX L493 虚构引文改 epics 21.6 参照/五 VO 计数统一/R1-6 正名/变异锚 11 处/集成场景编号/亲验组数/6-4 行号/L2018 引文/page 降级值注记/payload 行号统一】；钦定 OD-1~OD-12 十二裁定：范围边界（CLI-only 第六连+bbox defer 6-8+finding 级 defer V1+TraceabilityPort 语义正交零触碰）/零新增事件（查询型四连先例）/零新增异常（空树幂等读+降级承载——traceability 段 372-379 维持预留）/树 VO 五枚键契约（jump_ready 派生布尔）/多 run 判别 stage last-write-wins+adopted/total 对照（6.4-DF3 清偿）/depth 懒加载语义（交互展开等价改写）/性能三段口径（跳转载荷组装/解析成功率/真值归部署验证）/payload 扩键半边清偿（page_start/page_end——bbox 四元组 defer 6-8）/命名词族统一 traceability_tree（epics provenance 名显式偏离）/思维链全文附录维持 YAGNI（R4N-1 定夺）/组合根两注册+三依赖复用+collection 单源/三零 Story（零 infra/零 migration/零 domain）；12 验收场景钉死；锚定义务五条处置（6.5b-DF1 半边清偿/6.4-DF3 清偿/R4N-1 定夺/L170 顺延/L17 顺延））
