# Story 6-5a: Markdown 报告生成（基础）（BLM 面双源聚合 + 领域渲染纯函数 + L0/L2 持久化 + ReportGenerated 事件首激活）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统按 plan_id 生成 Markdown 格式战略规划报告（BLM 前两阶段：业绩差距分析 + 市场洞察）,
**So that** MVP 阶段可以导出和分享规划结果，支持后续高管视图（6-8）、白标报告基础（6-11）与 PDF 引文索引（6-5b）。

### 业务价值

BLM 前两阶段（6-1~6-4）已交付完整的流程/快照/思维链/归档数据面，但产物止于 CLI 打印与 Redis/PG 内部形态——高管与顾问无法直接消费。本 Story 是 Epic 6「规划结果可交付」的第一跳：把八步结构化产物渲染为**结构化章节 + 基础格式化（标题/列表/表格）** 的 Markdown 文档并持久化（L0 文件 + L2 元数据行 + ReportGenerated 事件），为 6-5b（PDF+引文，Given 钦定「Markdown 报告已生成」）、6-8（高管视图）、6-11（白标）三个下游 Story 提供统一报告基座。

### 与 6-1/6-2/6-3/6-4/6-5b/6-8/6-11 的范围边界（出处逐行声明）

| 面 | 本 Story（6-5a） | 归属（出处） |
|---|---|---|
| 报告数据聚合（chain 归档 + latest 快照双源按 plan_id） | ✅ 本 Story 新建 | epics L2232「Given BLM 前两阶段完成 When 生成报告」事后语义；6-3 L23「6-5a 报告（消费 Checkpoint 面数据）」 |
| 报告章节结构 / Markdown 渲染规则 | ✅ 本 Story 新建（领域层纯函数） | epics L2234「结构化章节（业绩差距分析、市场洞察）」+ L2235「标题、列表、表格」 |
| 报告文件落盘（L0）+ 元数据（L2 新表） | ✅ 本 Story 新建 | architecture.md 交互流程 37/38「元数据保存→Relational_Storage」（L413-417）；L4 证据包 defer 6-5b |
| ReportGenerated 事件生产 | ✅ 本 Story 首激活（事件 Epic 1 已定义零新增） | workflow_events.py:60 docstring 钦定「由 Epic 6 故事实现生产者」 |
| CLI `report-generate` 入口 | ✅ 本 Story 新建 | 6-3 checkpoint-create / 6-4 chain-query 同族先例 |
| PDF 转换 / 可点击引文索引 / Bounding Box 溯源 | ❌ | Story 6-5b（epics L2266-2279；reportlab 依赖已预留 pyproject L126） |
| 白标品牌（Logo/配色/字体/模板） | ❌ | Story 6-11（epics L2036「白标报告基础仅需 Markdown 基础，品牌配置可独立实现」） |
| 高管简化视图 / REST 查询面 | ❌ REST 归后续 Story | Story 6-8（epics L2034）；REST `/plans/{id}/export`（interface-design.md:1466 P0）归 Epic 7 API 入口立项——6-4 OD-1「REST 查询面归后续 Story」同款渐进裁定 |
| 图本体（位图/SVG/mermaid）渲染 | ❌ 表格/列表承载 | 本 Story OD-9 声明（6-2 OD-8「图本体生成归 6-5 报告面」的 6-5a 落位=表格化，位图 defer 6-5b） |
| 思维链全文附录 | ❌ | 6-4 chain.to_display() 资产已可消费；附录呈现归 6-5b/6-7 立项定夺（YAGNI） |
| BLM 流程执行 / 快照写 / 归档写 | ❌ 零改动纯读侧 | 6-1/6-2/6-3/6-4 全部冻结面零触碰（AC-6） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 报告生成主链（双源聚合 → 渲染 → 持久化 → 事件）

**Given** BLM 前两阶段已完成（八步 chain 归档行在位，plan_id 已知）
**When** 调用报告生成（CLI `report-generate --plan-id` 或用例 `GenerateMarkdownReportUseCase.execute(plan_id)`）
**Then** 执行五段编排：①chain 归档主源聚合（query_chain_trace）→ ②latest 快照辅源（可选容错）→ ③领域渲染纯函数生成 Markdown 文本 → ④L0 写 `.md` 文件 + L2 `strategic_reports` 元数据行 → ⑤发布 `ReportGenerated` 事件
**And** 返回 `StrategicReport` 实体（report_id/plan_id/report_type="markdown"/file_path/section_count/degraded_section_count/generation_ms）
**And** 同 plan_id 重复生成产生新报告（幂等锚=report_id，非 plan_id——重跑语义与 blm-plan `--plan-id` 透传幂等锚对齐，不拦截；**时间戳锚秒级精度注记**：`YYYYMMDDHHMMSS` 秒内连跑 memory_id 相同 → L0 文件覆写为一份，重复生成断言锚 = report_id 新增 + L2 行 +1，L0 文件件数唯一性断言需跨秒（场景间隔 sleep ≥1.05s）或不断言件数）

**验证标准/Validation Criteria:**
- [ ] 全链真实服务验收：Fake LLM/Embedding 双豁免跑 8 步 → report-generate → 断言五段全部落位
- [ ] L0 文件可读回：memory_id 经实体 file_path 反解（`Path(file_path).stem`——file_path 含 memory_id 单源派生）；读回内容断言含 AC-2 冻结章节标题族（期望由 display_name 配置源独立构造——非报告文本自证）
- [ ] L2 元数据行可读回（`get_latest_by_plan(plan_id)` 返回最新行，字段与实体一致）
- [ ] ReportGenerated 事件经 outbox 真实落行（outbox 断言键 `payload->'payload'->>'report_id'` 两级路径——子类字段经 to_dict 并入嵌套 payload 键；6-3 集成② `plan_id` 键先例同构——仓内无 archive_id 键的 outbox 断言，勿寻）

### AC-2: 结构化章节（章节结构冻结）

**Given** 八步归档行齐备（gap/六子步骤/synthesis）
**When** 报告生成
**Then** Markdown 文本按冻结章节结构输出：H1 封面标题 + 元信息表（两列表）+ 目录（锚点链接）+ `## 1 业绩差距分析`（四小节：财务差距/运营差距/根因分析/业务组合健康度）+ `## 2 市场洞察`（六小节：看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析——display_name 逐字对齐 `MARKET_INSIGHT_STEP_CONFIG`）+ `### 2.7 市场洞察综合`（`SYNTHESIS_DISPLAY_NAME` 逐字源——conclusions + degraded_inputs 显式列举）+ 附录 A 执行时间线（latest 快照在位时）+ 附录 B 降级与数据缺失记录
**And** 每个章节小节的要素字段渲染形态符合「要素渲染映射冻结表」（Task 0.1 定稿）

**验证标准/Validation Criteria:**
- [ ] 全部章节标题逐字断言（display_name 源：`PERFORMANCE_GAP_CONFIG`/`MARKET_INSIGHT_STEP_CONFIG`/`SYNTHESIS_DISPLAY_NAME`——不二次硬编码）
- [ ] gap 四字段四小节全量渲染（financial_gap/operational_gap/root_causes/portfolio_health）
- [ ] 六 Schema 全字段渲染（六类型化 Schema 冻结表 6-2 逐字段覆盖，无遗漏字段）
- [ ] synthesis.conclusions 列表 + degraded_inputs 显式列举（6-1 AC-6⑥「结论必须列举降级输入」语义在报告面延续）

### AC-3: 基础格式化（标题/列表/表格）

**Given** 报告生成
**When** 检查 Markdown 文本
**Then** 格式化三要素齐备且语法正确：ATX 标题层级（`#`/`##`/`###` 严格递进不跳级）、GFM 管道表格（表头 + `| --- |` 分隔行 + 行列对齐，PESTEL 六维表/五力五维表/时间线表/元信息表）、无序列表（`- ` 前缀逐项）
**And** 表格承载图类产物（OD-9：雷达图→能力维度表、价值主张地图→要点列表、增长路径图→路径列表）

**验证标准/Validation Criteria:**
- [ ] 标题层级断言（逐行 `#` 计数与冻结结构一致）
- [ ] 每张表格断言：表头行 + 分隔行 + 数据行数（PESTEL 表 6 行、五力表 5 行）
- [ ] 列表项数与源数据项数一致（findings/root_causes/technology_roadmap 等）
- [ ] 中文字符原样输出（`ensure_ascii=False` 语义——json/渲染不转义中文）

### AC-4: 数据源降级与缺失语义（可观测面非流程面）

**Given** 归档行部分缺失（某步 chain 归档行不存在于 PG——物理形态：compose 445 失败的 chain 缺席台账 / Step1 L2 写失败；注意 6-4 的 `archived=False` 是 compose 返回的内存态不进快照，284 后段失败形态下 L2 行通常已独立会话 commit 在位且正常渲染——报告读侧以 PG 行为准）
**When** 报告生成
**Then** 该步骤章节降级标注（`> ⚠️ [数据缺失] {display_name}：该步骤归档记录不可用`）+ 计入 `degraded_section_count` + 附录 B 记录行，报告照常生成；缺失判定 = 八 stage 期望集 − records stage 集差集（期望集派生公式见端口契约节——配置键序派生禁硬编码八清单）
**And** 源步骤 `degraded=True`（chain 归档行 degraded 锚）时章节携带 `> ⚠️ [降级] {display_name}：{原因}` 标注——**原因解析次序冻结**：`payload.get("degrade_reason")` → 缺席时固定兜底文案「降级（原因未随归档行结构化持久化）」（六子部分降级 R2-F2/synthesis 降级两形态 payload 无 reason 键——6-4 归档配方历史局限；**禁止解析 chain VO reflection 文本**）
**And** **渲染三态判定以 payload 形态为准**（非 degraded 锚——信封态行在/锚 True/无业务字段三信号并存）：①payload 解析失败或非 dict 形态不可识别 → [数据缺失]；②六子 payload 键集 ⊆ {degraded, degrade_reason}（降级信封态）→ [降级] callout（带 payload.degrade_reason）+ 跳过字段渲染；③其余 → 正常渲染 + 行 degraded 锚 True 时叠加 [降级] callout（原因按解析次序）。gap 型 payload 恒为 asdict 六键不适用②
**And** 数据源全缺（chain total==0）→ 抛 `ReportGenerationError`（EXCEPTION_490——404 语义；plan 从未跑过与跑过归档全失败两形态在持久真源同形同判，message 陈述可观测事实「该 plan_id 无思维链归档记录，无法生成报告」；最新快照在位亦同判：时间线摘要非报告素材）
**And** latest 快照缺失/TTL 过期（86400）→ 附录 A 省略 + L2 `metadata.timeline_available=false` 可观测，不阻断（R3 载体修正：「实体标注」原措辞无载体——实体七字段冻结表无标注位且 `get_latest_by_plan` 读回不携带 metadata；可观测面=落库时直查 PG JSONB——快照缺失场景断言面同步钦定此形态）

**验证标准/Validation Criteria:**（R2 逐条标层——验收 13 场景 AC-4×3=部分缺失/全缺/快照缺失三场景，其余归集成/单测）
- [ ] 部分缺失场景【验收场景+集成场景③】（**构造手段钦定：逐 stage 归档七次跳过目标步——6-3 `_archive_eight_steps` 先例变体；禁止跑完 8 步后删行构造**，仓内 `DELETE FROM strategic_archives` 仅 teardown 清理先例零场景构造先例；**跳步类别钦定（R3——期望唯一性）：验收与集成③目标步=六子步**（期望 degraded_section_count==1 与集成③对齐）；gap 缺行变体（期望 4 + 四小节 H3 骨架在位——缺行小节骨架渲染冻结）与 synthesis 缺行变体（期望 1）**归单测层参数化**，不进验收 13 场景）→ 章节标注 + degraded_section_count==1 + 报告成功
- [ ] 缺三步场景【集成 5.2 ③b——不占 13 场景名额】（六子缺三步 → degraded_section_count==3 ≤ section_count==11 不变量成立，无 242——锁死计数口径）
- [ ] 全缺场景【验收场景+集成场景④】（**从未归档的独立 plan_id**——天然 total==0 无需清空）→ 异常 490（code/message/context 断言）
- [ ] 快照缺失场景【验收场景】→ 无附录 A + 报告成功
- [ ] 降级标注注入断言【单测层——R1-8 钉死验收不含信封态注入】（6-1 R1-4「降级事实+原因完整传导」同语义；信封态断言 reason 传导 + 兜底文案形态各一用例；信封态计入/锚叠加不计入的 R2 口径各钉一用例）

### AC-5: ReportGenerated 事件首激活

**Given** 报告生成成功
**When** 事件发布
**Then** 发布 `ReportGenerated`（report_id=实体 report_id / report_type="markdown" / file_path=实体 file_path / aggregate_id=report_id / aggregate_type="Report"——**事件类字段面冻结零改动**，无 tenant_id 字段不得自行追加；**构造点必显式传 report_id/report_type/file_path 三键**——事件类三键均有缺省空串，漏传不炸产空串事件，唯一防线在构造点+单测三键非空断言）
**And** 事件通道零新增零 diff（event_channels.yaml L273 + DEFAULT_MAPPINGS :346 既有登记直接复用——reliable 单通道 + Outbox）
**And** 发布失败 → **宽容语义**（宽容**结果语义**同构 checkpoint ⑤——不回滚+返回成功；L0/L2 是报告真相源、事件是通知面。**防线形态为增强**：⑤先例仅单 `except` 在吞异常语义下对失败 PublishResult 静默无 warning，本 Story 显式加 `is_success` 判定修正该缺陷——R2 措辞精确化，勿照抄先例单防线）：`logger.warning`（含 report_id/event_type/error）+ 报告正常返回成功，**不上抛**（491 上抛回滚不了已落盘 L0/L2，且 CLI exit 1 误导重跑叠加多份——OD-6 裁定）。**失败检出双防线强制**：`if not result.is_success` 先判（实现层经 `DualChannelEventBus` 委托 `RabbitMQEventBus.publish`——吞异常返回失败 `PublishResult`，纯 `except Exception` 恒不触发）+ `except Exception` 兜底；两防线任一命中均走 warning。**outbox 断言等价机理注记**：publish 仅做 outbox 落行**无 MQ 直发**（MQ 投递归 AsyncOutboxPoller 基建——现状未运行，deferred-work L170）→ 「outbox 有行 ⟺ is_success True」是强信号等价——断言以 outbox 行为唯一面，**禁止追加 MQ 消费侧断言**（集成环境无 RabbitMQ 会挂）

**验证标准/Validation Criteria:**
- [ ] outbox 落行断言（event_type/report_id/file_path 三键值级断言——非仅存在性）
- [ ] 组装映射值级断言（独立构造期望事件对象比对——非读回自比，6-3 R1-F6 教训；含三键非空断言）
- [ ] 发布失败两形态单测（①mock 返回 `PublishResult(event_id=str(uuid4()), results=(ChannelResult("reliable", False, "..."),))`——**event_id 是必填无缺省首参（publish_result.py:30），漏传即 TypeError** → 断言 warning + 返回成功 ②mock raise → 同断言——双防线各钉一用例，防只写 except 假绿）
- [ ] `configs/event_channels.yaml` 与 `channel_router.py` 零 diff（契约测试守护）

### AC-6: 契约零破坏（6-1/6-2/6-3/6-4/5-3 冻结面零触碰）

**Given** 本 Story 实施
**When** 回归验证
**Then** 以下冻结面零改动：①6-2 六 Schema 字段级冻结表（blm_planning_prompts.py 零 diff）②per-step/latest 快照契约（blm_planning.py docstring 契约区 + 6-3 13 键）③chain 归档载荷映射（6-4 冻结配方）④`ReportGenerated` 事件类与双登记 ⑤既有 6-x/5-3 验收/集成/契约测试零修改通过
**And** 新增代码不引入对 6-x 写路径的任何调用（纯读侧：query_chain_trace + snapshot load + L0 write 新 memory_type）

**验证标准/Validation Criteria:**
- [ ] 四目录全量回归两轮稳定（`pytest tests/unit tests/integration tests/contracts tests/acceptance`）
- [ ] AC-6×1 验收场景断言面处方（R3 钉死——对齐 6-4 S8/S9「契约键集字面基线全等」形态，防现场发明/恒真断言）：真实 8 步 run + 报告生成后断言①chain 读侧 records 五键结构（stage/chain/archive_id/degraded/blob_content）与冻结面全等【字面键集基线在测试内——防漂移即守护】②ReportGenerated outbox 行 payload 键族与事件类冻结字段面全等（report_id/report_type/file_path/aggregate_id/aggregate_type/event_type）；**不重复** Task 4.1 事件登记键集合面（契约测试已载）与 Task 6 架构扫描面（SDD 验证已载）——验收层只做「读侧消费面契约」两断言
- [ ] `poetry run ruff check` + `poetry run mypy src/` 零错误

### AC-7: 性能与持久化成功率

**Given** 数据源在位
**When** 生成报告
**Then** 生成窗口 P95<30s（口径：数据聚合起点→事件发布返回；**不含 BLM 流程本身**——run 是前置，OD-8 口径差声明）
**And** 生成成功率 100%（口径：正常路径 N 次生成 N 次文件可读回+元数据行在位+事件落行——N 与性能采样轮数同源（20）；**「文件可读回」=每轮生成后即时经该轮实体 file_path stem 反解读回**（秒级覆写形态下事后统一断言 20 文件会假失败——AC-1 秒级注记联动，件数断言豁免）；数据源全缺 490 是业务异常非失败，6-4 OD-5 同款口径重读）
**And** 并发生成 3 个报告（asyncio.gather 独立 plan_id，互不干扰；**服务无状态约束**——`report_generation_service` SINGLETON 实例并发共享，实现禁持每次调用的可变实例态，并发安全仅依赖注入依赖的线程/协程安全性）

**验证标准/Validation Criteria:**
- [ ] 性能采样 ≥20 轮（**单一数据源 plan_id × 20 次生成**——OD-10 幂等锚语义下重复生成是合法采样形态，构造成本=8 步归档一次而非 20 套；断言锚=每轮新 report_id + L2 行数 20；采样断言 report_id 集合无重复。n=20 注记：`sorted[ceil(0.95*20)-1]`=sorted[18] 即**次大值**——单个离群即破阈值，噪声敏感性与 6-3 先例一致如实承受）；sorted P95 数学口径——6-3 同款：`sorted(durations)[ceil(0.95*n)-1]`
- [ ] 并发 3 场景（三 plan_id 全部成功且文件/行/事件三元互不串扰）
- [ ] 口径差落测试 docstring（OD-8）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **零新增事件**——`ReportGenerated` 复用首激活（`src/domain/events/workflow_events.py:56-72`，Epic 1 定义；docstring :60 钦定「由 Epic 6 故事实现生产者」；双登记已在位：`configs/event_channels.yaml:273-276` + `channel_router.py:346-351` reliable 单通道——**零 diff**）
- [x] 发布点唯一落位 = `ReportGenerationService` 编排尾部（L2 元数据行落库之后；save 与 publish 分属独立会话**无共同事务**——发布失败处置按 AC-5 宽容语义 warning 不回滚）

#### 数据模型 (Data Models)

**领域实体** `StrategicReport`（`src/domain/entities/strategic_report.py` ★ 新建，frozen dataclass 零依赖）：

| 字段 | 类型 | 约束 |
|---|---|---|
| `report_id` | `uuid.UUID` | 主键（default_factory=uuid4） |
| `plan_id` | `str` | 非空（UUID 字符串——与 chain 归档 plan_id 同源） |
| `report_type` | `ReportType` | 枚举 `MARKDOWN="markdown"` / `PDF="pdf"`（6-5b 预留值，本 Story 仅产 MARKDOWN） |
| `file_path` | `str` | 非空（**L0 逻辑路径** `reports/{memory_id}.md` 单源派生——非绝对路径：base 物理路径归 infrastructure `MemoryConfig`，application 层不得知悉（六边形依赖方向）；逻辑路径可移植（审计语义）且消费方经端口 `read(memory_id, "reports")` 读取无需 base；memory_id 可经 `Path(file_path).stem` 反解——OD-4 裁定） |
| `section_count` | `int` | ≥0（**正文 H3 小节总数**——gap 4 + 六子 6 + synthesis 1 = 11；目录/附录不计。计数单位钦定 H3 小节而非 H2 章数（H2 口径=2 时缺 ≥3 步即破坏 degraded ≤ section 不变量炸 242——load-bearing 选择，AC-4 缺三步场景锁死） |
| `degraded_section_count` | `int` | ≥0 且 ≤section_count（**内容缺失类 H3 小节数**——R2 钉死口径：①归档行缺→[数据缺失] 计入（六子缺→1/synthesis 缺→1/gap 缺→4）；②降级信封态（行在位但业务字段缺席跳过渲染）计入（六子信封→1/synthesis 无信封恒 asdict 走③）；③锚叠加类（payload 完整+degraded 锚 True，内容在位仅 [降级] 标注）**不计**——内容完整非缺失，可观测面归附录 B [降级] 行。上限 11 天然成立：单小节至多一种标注形态（缺行时无锚可叠/信封时锚 True 但算一种），极端形态 gap 缺行 4 + 六子全信封 6 + synthesis 缺行 1 = 11（缺行 2 条 total=6≠0 不触发 490；synthesis 恒 asdict 两键无信封形态——内容缺失只能来自缺行）） |
| `generation_ms` | `int` | ≥0（生成窗口毫秒——**实际窗口 = 聚合起点→L2 落库前**【CR1-F16 勘误注记：frozen 实体须先于 save/publish 构造（publish 依赖 report_id），物理上不可能含发布段；AC-7 全窗口「→事件发布返回」口径由测试侧 execute 包裹计时承载——OD-8 联动】） |
| `created_at` | `datetime` | default_factory=now(UTC) |

- [ ] `__post_init__` 校验（**CR1-F6 五查补全**——原三查漏 plan_id 非空与三计数非负值域）：report_type 枚举成员校验（裸 str 拒绝——ArchiveType validate :90-94 同款形态）/ file_path 非空（纯空白拒）/ **plan_id 非空**（字段表「非空（UUID 字符串）」契约落地）/ 计数不变量（degraded ≤ total）+ **三计数 ≥0**（section_count/degraded_section_count/generation_ms 负值拒——字段表 ≥0 约束），违例抛 `EntityValidationError`（242 复用——实体不变量场景钦定）

**领域 VO——报告文档模型**（`src/domain/value_objects/markdown_report.py` ★ 新建，渲染器入参载体；**domain 不得依赖 application**——importlinter 方向矩阵，故不直接吃 `ChainOfThoughtTraceView`/`BlmPlanningResult` 等应用层 DTO）：

| VO | 字段 | 说明 |
|---|---|---|
| `ReportSection` | `title: str` / `level: int`（**1-3**——R2 收窄：与冻结表「严格 1-3 不开 H4」/AC-3 字面/校验三方对齐，原 1-4 值域会放行无渲染语法的 level=4 对象）/ `blocks: tuple[ReportBlock, ...]` | 章节（display_name 逐字源） |
| `ReportBlock`（联合形态单类+kind 判别） | `kind: str`（`paragraph`/`bullet_list`/`table`/`callout`）/ `text: str`（paragraph/callout）/ `items: tuple[str, ...]`（bullet_list）/ `headers: tuple[str, ...]` + `rows: tuple[tuple[str, ...], ...]`（table） | 四块型冻结——AC-3 三要素 + callout（降级/缺失标注） |
| `MarkdownReportDocument` | `plan_id: str` / `title: str` / `meta_rows: tuple[tuple[str, str], ...]`（元信息表）/ `sections: tuple[ReportSection, ...]` / `toc_enabled: bool = True` | 文档根（应用层聚合产物→渲染器入参） |

- [ ] `__post_init__` 校验：level 值域 1-3（R2 收窄同 VO 表）/ kind 白名单 / table 列数一致（rows 每行 len==len(headers)），违例抛 242

**L2 元数据表** `strategic_reports`（alembic `017_strategic_reports.py` ★ 新建——只增 migration，已合入 migration 禁改红线）：

| 列 | 类型 | 约束 |
|---|---|---|
| `report_id` | `UUID` | PK |
| `plan_id` | `UUID` | 非空，idx（get_latest_by_plan 查询面） |
| `report_type` | `String(20)` | 非空 |
| `file_path` | `String(500)` | 非空 |
| `section_count` | `Integer` | 非空 |
| `degraded_section_count` | `Integer` | 非空 |
| `generation_ms` | `Integer` | 非空 |
| `metadata` | `JSONB` | 扩展元数据（timeline_available/缺失步清单等，6-8/6-11 扩展点） |
| `created_at` | `DateTime(timezone=True)` | 非空 server_default=now() |

- ORM 模型 `src/infrastructure/storage/postgresql/models/report.py`（`ArchiveModel` 同款形态——Mapped/mapped_column/Base 继承 outbox.py）

#### 报告章节结构与要素渲染映射冻结表（实现 Task 的权威输入——Task 0.1 复核确认，不得增删）

**章节结构冻结**（display_name 逐字源=6-1/6-2 语义配置，禁二次硬编码；level 严格 1-3 递进不跳级——组内行标签用**加粗行标签**形态承载（`**客户细分画像**` 等前置行），不开 H4——与 AC-3「`#`/`##`/`###` 严格递进」字面锁定，R1 预裁定不再开放；**章节标题拼接规范冻结**：`{位置编号} {display_name}`（编号+半角空格+逐字 display_name——如 `## 1 业绩差距分析`/`### 2.7 市场洞察综合`，断言字面按此拼接构造）；**目录锚点算法冻结**：GitHub 风格 slug（标题小写化 + 空格→连字符 + 去除标点、中文原样保留）——`## 1 业绩差距分析` → `#1-业绩差距分析`）：

| 位置 | 标题（level） | 标题源 | 素材源 | 块型序列 |
|---|---|---|---|---|
| 封面 | `战略规划报告（BLM 前两阶段）`（H1） | `REPORT_TITLE_TEMPLATE` 端口常量 | plan_id/生成时间/执行耗时 ms/正文章节数/降级章节数 | table（元信息两列表：`| 项目 | 值 |`） |
| 目录 | `目录`（H2，toc_enabled 时） | 固定 | 章节标题派生锚点链接 | bullet_list |
| 第 1 章 | `{业绩差距分析}`（H2） | `PERFORMANCE_GAP_CONFIG.display_name` | gap 归档行 payload | 见小节映射 |
| 1.1 | `财务差距`（H3） | 固定小节名 | `financial_gap` | paragraph |
| 1.2 | `运营差距`（H3） | 固定 | `operational_gap` | paragraph |
| 1.3 | `根因分析`（H3） | 固定 | `root_causes` | bullet_list（逐项） |
| 1.4 | `业务组合健康度`（H3） | 固定 | `portfolio_health` | paragraph |
| 第 2 章 | `市场洞察`（H2） | 固定章名 | — | 章引导语可选 |
| 2.1~2.6 | `{看趋势}` 等（H3） | `MARKET_INSIGHT_STEP_CONFIG[step].display_name` 六值 | 各步归档行 payload | 见要素映射表 |
| 2.7 | `{市场洞察综合}`（H3） | `SYNTHESIS_DISPLAY_NAME` | synthesis 归档行 payload | conclusions→bullet_list + degraded_inputs→callout 显式列举 |
| 附录 A | `附录 A 执行时间线`（H2） | 固定 | latest 快照 timeline（在位时） | table（`| 步骤 | 开始 | 完成 | 状态 | 降级 |`） |
| 附录 B | `附录 B 降级与数据缺失记录`（H2） | 固定 | 聚合过程登记清单 | table（`| 类型 | 步骤 | 原因 |`——**类型列值域 {[数据缺失],[降级]}，收录范围=两类全收**：缺行→[数据缺失] 行/信封态与锚叠加态→[降级] 行（callout 即时可见 + 附录 B 汇总可观测双面；R2 口径与 degraded_section_count 只计内容缺失类相区分）；登记清单是**单次调用局部累积**（函数内列表随返回丢弃——非服务实例态，AC-7 并发/20 轮防互扰） |

**六子步骤要素渲染映射冻结**（每步公共前缀：`summary`→paragraph + `findings`→bullet_list；标注 callout 见下）：

| 步骤（step 枚举值） | 字段 → 块型 | 行标签/表头（中文语义源=6-2 冻结表 description 列） |
|---|---|---|
| trend | `pestel_*` 六字段 → table（`| 维度 | 评估 |` 6 行）；`technology_roadmap` → bullet_list；`scenario_plans` → bullet_list | 维度行标签：政治/经济/社会/技术/环境/法律 |
| market_customer | `customer_segments`/`demand_priority_matrix`/`value_proposition_map` → 三组 bullet_list（各组前置**加粗行标签**——章节结构冻结节预裁定，不开 H4） | 客户细分画像/需求优先级矩阵（$APPEALS）/价值主张地图 |
| competition | `five_forces_*` 五字段 → table（`| 五力 | 评估 |` 5 行）；`competitor_radar` → table（`| 能力维度 | 评估要点 |`——**图类产物表格承载 OD-9**）；`strategy_recommendations` → bullet_list | 五力行标签：供应商议价能力/购买者议价能力/新进入者威胁/替代品威胁/现有竞争者强度 |
| self | `internal_capabilities`/`vrio_assessment`/`resource_constraints` → 三组 bullet_list | 内部能力清单/核心能力 VRIO 评估/资源约束分析 |
| opportunity | `opportunity_list`/`priority_ranking`/`growth_path` → 三组 bullet_list | 机会清单/机会优先级排序/增长路径图（安索夫矩阵路径） |
| opportunity_gap | `gap_quantification`/`capability_match_matrix`/`closure_strategies` → 三组 bullet_list | 机会差距量化报告要点/能力-机会匹配矩阵/差距弥合策略 |

**标注形态冻结**（callout 块型两形态——6-1「降级事实+原因完整传导」报告面延续；**三态判定与原因解析次序以 AC-4 冻结版为准**——payload 形态优先于 degraded 锚，信封态键集判定勿并入「解析失败」）：
- **缺行小节骨架渲染冻结（R3 补——load-bearing 前提）**：归档行缺失的小节**仍渲染 H3 骨架**（`### {编号} {display_name}` 标题 + [数据缺失] callout 为该小节唯一块）——section_count 恒 11 与数据缺否无关（省略小节的分叉实现会使极端形态 section_count=6 < degraded_section_count=11 炸 242，击穿「报告照常生成」——R2-2 不变量算术的隐含前提在此显式化；gap 缺行时 1.1~1.4 四小节共享步骤级 display_name 锚定骨架）
- 源步降级：`> ⚠️ [降级] {display_name}：{原因}`（章节标题后首块；原因 = `payload.get("degrade_reason")` 缺席时固定兜底「降级（原因未随归档行结构化持久化）」——synthesis payload 恒无 reason 键/六子部分降级（R2-F2）payload=structured_output 原样亦无——两形态走兜底；**禁止解析 chain VO reflection 文本后缀**；信封态与锚叠加态均落本形态 callout + 附录 B [降级] 行——**是否计入 degraded_section_count 见实体表 R2 口径**：信封态计（内容缺失）/锚叠加不计）
- 归档行缺失：`> ⚠️ [数据缺失] {display_name}：该步骤归档记录不可用`（章节标题后唯一块 + 附录 B [数据缺失] 行 + degraded_section_count 计入）

**渲染语法冻结**：ATX 标题（`#`/`##`/`###`，禁 Setext）；GFM 管道表格（表头 + `| --- |` 分隔行 + 数据行，列数严格一致）；无序列表 `- ` 前缀；callout `> ` 前缀；中文与特殊字符原样输出（渲染层禁转义——`ensure_ascii=False` 语义）。**GFM 结构性字符处理限定（CR1-F4/F5 勘误）**：「禁转义」条款针对 unicode/中文语义转义，**不豁免 GFM 结构性字符**——表格单元格内 `|` 转义为 `\|`、换行符归一空格（GFM 语法内在要求，防 LLM 自由文本 payload 值破坏列对齐/注入表格行）；callout 文本多行时逐行补 `> ` 前缀（合法多行 blockquote，防后续行脱离标注形态）。

**附录 A 表定稿（R3 补全映射源清单）**：「步骤」列取 **display_name 映射**——timeline 条目是三种 step 值形态（**CR1-F1 勘误：写侧实证 `blm_planning_service.py:309/:414/:504` record_step 三值**——六子裸值 trend 等（`step.value`）/`performance_gap`/`market_insight_synthesis`【原记裸值 `synthesis` 系对端口 docstring 简称的误读，写侧 timeline 实际记录 stage 全值——单测臆造值同步改喂真实值】），映射源**三源**：`performance_gap`→`PERFORMANCE_GAP_CONFIG.display_name`、六子裸值→`MARKET_INSIGHT_STEP_CONFIG`、`market_insight_synthesis`→`SYNTHESIS_DISPLAY_NAME`（R3 补第三源——两源版下 synthesis 条目无源可映射，期望不唯一）；映射 miss（未知 step 值）**直显裸值**（防未来配置增步炸渲染）；`summary_excerpt` 键**显式省略**（时间线表五列不含摘要——附录是执行过程记录非内容面）。

**目录（TOC）收录面冻结（R3 补）**：收录 **H2 章级 + 附录**（第 1/2 章 + 附录 A/B——条目数随附录 A 有无非恒定，断言按实际收录数构造期望）；H3 小节不进目录（报告篇幅短，两级目录足够——渲染器单测断言目录条目数与收录规则联动）。

#### 统一端口定义注册与管理 (Port Contract)

**新建端口 1：应用层 `ReportGenerationServicePort`**（`src/application/ports/report_generation.py` ★——R2 具体应用端口，组合注入 R1 基础端口）：

```python
@runtime_checkable
class ReportGenerationServicePort(Protocol):
    async def generate_markdown_report(self, plan_id: uuid.UUID) -> StrategicReport: ...
```
（R1 修订：删除 `tenant_id: str = ""` 死参数——L2 表无 tenant 列/事件无 tenant_id 字段（AC-5 禁追加）/L0 无租户隔离，全链零消费面）
- 模块常量：`REPORT_FILE_MEMORY_TYPE = "reports"`（L0 memory_type 单源——禁两处字面量）、`REPORT_TITLE_TEMPLATE = "战略规划报告（BLM 前两阶段）"`
- **八 stage 期望集派生公式**（缺失判定单源——禁硬编码八清单，配置增步自动跟随）：`expected_stages = ("performance_gap", *(f"market_insight_{key}" for key in MARKET_INSIGHT_STEP_CONFIG), "market_insight_synthesis")`；缺失集 = expected_stages − {record["stage"] for record in records}（注【R5 改述】：`STAGE_VALUE_DOMAIN` **有**运行时 frozenset 定义（`src/domain/value_objects/blm_phases.py:69-71`，`__all__` :324 导出）——R1 原注「仅 docstring 无定义+6-4 漂移」双重失实（6-4 Story 正确引用无漂移）；本 Story 派生公式仍取 `MARKET_INSIGHT_STEP_CONFIG` 键序而非该常量，因键序**有序**且与章节标题 display_name 同源，frozenset 无序不适配差集判定与渲染顺序）

**新建端口 2：领域层 `ReportRepositoryProtocol`**（`src/domain/ports/report_repository.py` ★——R1 基础端口；查询参数决策规则：单字段标识查找→直接参数）：

```python
@runtime_checkable
class ReportRepositoryProtocol(Protocol):
    async def save(self, report: StrategicReport, metadata: dict[str, Any] | None = None) -> StrategicReport: ...
    async def get_latest_by_plan(self, plan_id: uuid.UUID) -> StrategicReport | None: ...
```

- [ ] 端口契约定义位于上述两文件；端口注册中心 `src/domain/ports/registry.py` 登记 `PortSpec`（name/version/interface/impl/module/lifetime/owner/tags）
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册（三注册块：`report_repository` SCOPED + session_factory 注入【**6-4 P0 教训——第一天就带 session_factory，不走裸构造后补 fallback**】；`report_generation_service` SINGLETON 五依赖；`report_generation_use_case` SINGLETON），禁止业务代码直接实例化具体实现
- [ ] 端口解析器 `src/domain/ports/resolver.py` resolve() 可达；契约门禁 `contract_gate.py` 通过
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_report_generation.py` ★——五断言族：注册存在/spec 元数据（interface/lifetime/tags/owner）/v 前缀版本/getsource 注入面【chain_trace + snapshot + l0 + report_repository + event_publisher 五依赖包含性】/resolve isinstance——6-4 契约测试形态模板）
- [ ] 接口命名单一职责；跨模块调用仅依赖抽象接口；禁止服务文件本地定义 Protocol

#### 端口契约清单执行约束（强制）

- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> 完整检查清单与全量异常分类详见 [`sisys-uni-exception-design.md §3.12`](../../docs/architecture/sisys-uni-exception-design.md#312-异常注册检查清单)。

**开段裁定**：planning 段 (480,489) 中 485 预留、486-489 成文「留 6-6 恢复执行面」（`_code_ranges.py:189`）不可占；report 语义独立（报告交付物 ≠ 规划流程）→ 按「前段满/双重成文预留不可占/语义独立 → 开独立段」八代先例（data_source 410/debate 420/tool_version 430/agent 440/evaluation 450/sap 460/financial 470/planning 480——`_code_ranges.py:170-175`）**开 report 段 (490, 499)**。Task 0.1 运行 `grep -r "EXCEPTION_49" src/domain/exceptions/` 验证零碰撞。

| 异常类 | code | 基类 | 触发场景 | HTTP |
|---|---|---|---|---|
| `ReportGenerationError` | EXCEPTION_490 | `BusinessException` | 报告数据源全缺（chain total==0——plan 从未跑过与归档全失败两形态同判；404 语义——PlanningNotFoundError 480 同族；message 钦定可观测事实口径「该 plan_id 无思维链归档记录，无法生成报告」） | 404 |
| `ReportStorageError` | EXCEPTION_491 | `BusinessException` | 报告持久化失败（L0 写失败 layer="l0" / L2 落库失败 layer="l2"——**二元值域**；事件发布失败不走本异常：AC-5 宽容语义 warning（R1 裁定：上抛回滚不了已落盘 L0/L2 且误导重跑）。layer 参数**语境借鉴** 284 但**值域自有**：`_VALID_LAYERS = ("l0", "l2")` 自有元组——**禁复用 284 常量**（284 值域 ("l2","l3","l4","l5") 不含 l0，照抄即漏；非法 layer 抛 242 的守卫形态同构保留） | 500 |

- [ ] 归属模块：`src/domain/exceptions/report_exceptions.py` ★ 新建（report 子域）
- [ ] 唯一编码分配：490/491（grep 零碰撞实证）；`_code_ranges.py` `CODE_RANGES` 增 `"report": (490, 499)` + `_CLASS_TO_SUBDOMAIN` 注册两类
- [ ] 构造器参数（家族形态对齐——领域参在前 + 覆写参数缺省在后，284 `:88-93`/480 `:49-55` 同构）：`ReportGenerationError(plan_id, message=None, cause=None, context_extra=None)` / `ReportStorageError(layer, message=None, cause=None)`——context 字典暴露领域上下文（plan_id / layer），非法 layer 值抛 242
- [ ] 消息安全性：面向调用方可理解，不泄露内部细节
- [ ] 导出完整性：模块 `__all__` + `src/domain/exceptions/__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射（490→404 / 491→500——未注册直系子类回退基类 400，精确注册是必要动作）
- [ ] 编码分配表更新：`sisys-uni-exception-design.md` §3.3.2 完整编码分配表 + §3.3.2 子域编码范围表（business 段后追加 report 段行；**顺带回填既有文档债**：6-3 已落码的 483 CheckpointCreationError（500）/484 CheckpointIntegrityError（409）两行按 `_code_ranges.py:184-188`（R2 校正——原 :178-181 是 481/482 条目）+ `exception_handlers.py:309-310` 为准修正「483~489 预留」失实行——**同 §3.3.2 两张表**（:755 分配表与 :837 范围表）同次编辑修正，属偿还既有漂移非扩面，R1 裁定不留静默失真）
- [ ] 测试覆盖：`tests/unit/domain/exceptions/` 构造/`to_dict()`/HTTP 映射 + 编码唯一性 + 子域范围（`test_error_code_uniqueness.py` + `test_code_ranges.py` 全绿——前者经 `__all__` 自动发现零改动，后者注意新子域继承 BusinessException 经 abstract_names 跳过无需白名单）+ `tests/unit/interfaces/api/test_exception_handlers.py`
- [ ] BDD 验收场景：490 异常路径纳入 Gherkin Edge Cases（AC-4 全缺场景）；491 归单测层承载（BDD 约束节 no-mock 红线互斥裁定）

#### API 契约 (API Contract)

- [x] **本 Story 零 REST 面豁免声明**：CLI-only 入口（6-3/6-4 同族——openapi.yaml 至今无 BLM 面 endpoint 惯例，`/api/v1/archive` 已交付亦未登记）；`/plans/{id}/export`（interface-design.md:1466 P0）归 Epic 7 API 入口立项/6-8 立项时补契约（deferred-work 登记触发条件）
- [ ] `docs/api/openapi.yaml` 零 diff（契约测试守护——不引入任何 API 契约变更）

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

**本 Story 层间落位**（R1~R4 设计规则映射）：
- R1：`ReportRepositoryProtocol`（domain/ports——基础端口）
- R2：`ReportGenerationServicePort`（application/ports——具体应用端口，组合注入 R1 基础端口 `SnapshotRepositoryProtocol`/`EventPublisher`/应用层 `ChainOfThoughtArchiveServicePort` + R1 `L0StoragePort`/`ReportRepositoryProtocol`）
- R3：`PostgreSQLReportRepository`（infrastructure——L2 实现，session_factory 注入）；L0 复用 `FileMemoryAdapter` 零新实现；alembic migration（infrastructure 侧 deploy/postgresql）
- R4：CLI `report-generate`（entrypoints/agent_cli.py——组装层，经组合根 resolve；6-3/6-4 同族先例）；渲染器=domain/services 纯函数（领域知识——BLM 报告章节结构是方法论的一部分）

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止（importlinter application-no-infrastructure 强制） |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_markdown_report.feature` ★ 新建（13 场景——AC-1×2/AC-2×2/AC-3×1/AC-4×3/AC-5×1/AC-6×1/AC-7×2/收尾×1，Task 0 钉死无范围值）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_markdown_report.py` ★ 新建（BDD 步骤实现）
- [ ] R6 风格基准：`test_acceptance_postgresql_relational_layer.feature/.py` 的 Gherkin 组织与场景结构 + 6-3/6-4 演进三件套（全场景 `@scenario` 绑定 + `pytestmark` 显式 + 模块级 `event_loop` + `context` dict + `_run_async` + teardown 精确清理链 + 逐服务探测 `pytest.skip()` 动态跳过 + 新模块延迟 import + docstring 分档表与 Run with）——**postgresql_relational 样板的 R6 旧欠账（部分绑定/无 pytestmark/无三件套）不承袭**（6-3 docstring L4-7 钦定先例）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases——含 490 异常路径；491 持久化失败归单测层，见 BDD 步骤实现约束）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 数据源全缺（490）/持久化失败语义（491 单测层承载——no-mock 红线互斥裁定：L0/L2 写失败注入归单测 AsyncMock 承载，验收/集成不含——6-2 R3-4/6-3 0.8⑧/6-4 OD-5 三连先例）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（章节结构冻结表/要素渲染映射冻结表落 Dev Agent Record——实现 Task 的权威输入）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——**运行期 ImportError 形态**【延迟 import 纪律】，非收集期 collection error）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义：①组合根三注册块 resolve 可达（report_repository/report_generation_service/report_generation_use_case——含 CLI 生产通道 PG session 可达性【6-4 P0 三重遮蔽教训：CLI 入口文件 grep `set_session/session_context` 组合根侧 session_factory 注入实证——**新增 CLI 入口消费既有 PG 仓储的 P0 排查法必跑**】）②ReportGenerated 事件真实发布验证（发布点代码位 + outbox 落行断言 + 订阅方可达）③alembic 017 migration 升级可用（`alembic upgrade head` 幂等）；「已实现未接线」组件在 deferred-work.md 登记

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
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言；6-4 R2-2「evidence_refs 回填零断言」在修复自身重现的教训）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | `StrategicReport` 实体 + 报告 VO | 不变量校验（枚举/计数/列一致）/构造 | `tests/unit/domain/test_strategic_report.py` ★ | Task 1 |
| **TDD 单元测试** | 渲染器纯函数 | 章节结构/格式化三要素/降级标注渲染 | `tests/unit/domain/services/test_markdown_report_renderer.py` ★ | Task 1 |
| **TDD 领域异常测试** | report_exceptions | 构造/属性/`to_dict()`/cause 链 | `tests/unit/domain/exceptions/test_report_exceptions.py` ★ | Task 1 |
| **TDD 单元测试** | ReportGenerationService | 双源聚合/降级语义/五段编排/事件发布 | `tests/unit/application/test_report_generation_service.py` ★ | Task 2 |
| **TDD 单元测试** | GenerateMarkdownReportUseCase | plan_id 守卫/透传/返回实体 | `tests/unit/application/use_cases/test_generate_markdown_report_use_case.py` ★ | Task 3 |
| **TDD 单元测试** | PostgreSQLReportRepository | save/get_latest_by_plan 双向（真实 PG——Schema 隔离） | `tests/unit/infrastructure/storage/postgresql/test_report_repository.py` ★ | Task 3 |
| **TDD 单元测试** | CLI report-generate | 参数解析/成功打印/双层异常定式 exit 1 | `tests/unit/interfaces/cli/test_agent_cli.py` ▲ 扩展 | Task 3 |
| **TDD 契约测试** | 端口契约 | 注册/元数据/注入面/resolve 五断言族 | `tests/contracts/test_port_contract_report_generation.py` ★ | Task 2/4 |
| **TDD 契约测试** | 事件零新增守护 | yaml+router 零 diff 负向断言 | `tests/contracts/test_event_channel_mapping_report.py` ★ | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 13 场景 | `test_acceptance_markdown_report.feature` ★ | Task 0/7 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_markdown_report.py` ★ | Task 0/7 |
| **集成测试** | 真实链五场景 | 全链（真实 Redis/PG/Qdrant/MinIO+Fake LLM/Embedding 双豁免） | `tests/integration/test_integration_markdown_report.py` ★ | Task 5 |
| **SDD 架构验证** | 六边形约束 | 层依赖/落位/禁 import | `tests/unit/architecture/test_markdown_report.py` ★（epics L2260 钦定名） | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **分层覆盖率** - **P1 阻断门禁**
  - 领域层：≥90%（本 Story 主改动层之一——实体/VO/渲染器纯函数，零依赖高可测）
  - 应用层：≥85%（epics L2251 钦定——聚合服务/用例）
  - 基础设施层：≥75%（report_repository）
  - 集成测试覆盖率 ≥75%（epics L2252）
- [ ] **关键路径覆盖率 100%**（渲染器全块型/聚合全降级分支）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`——当前基线 736 零错误不回退）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **报告键清理** | L0 报告文件（reports/{plan_id}_*）/L2 strategic_reports 行/chain 归档三面残留（PG 档案行/Qdrant 点/MinIO WORM）/Redis 快照键族——teardown 各步独立 try/except + 跑前跑后净增 0 断言（6-3 R1-F1 泄漏 1117+ 键教训；6-4 teardown 六步链+`_cleanup_archive_residues` 直接移植） | 残留污染后续测试 |
| **MinIO WORM 清理** | `remove_objects(bypass_governance_mode=True)`（6-3 集成先例） | WORM 对象 7 年锁死测试 bucket |
| **外部服务隔离** | Fake LLM/Embedding 双豁免（AsyncMock(spec=Port) 外部 SaaS 豁免面——6-2 `_make_fake_llm` **八键族**身份分派形态复用：六类型化 + GapAnalysis + InsightSynthesis）+ 存储端口全真实 | no-mock 红线 |
| **资源唯一性** | 测试数据 UUID 前缀隔离（TestTenant）；报告 memory_id 锚 plan_id 天然唯一 | ID 冲突 |
| **并行隔离** | `xdist_group("blm-planning-perf")` 组复用（6-1/6-2/6-3/6-4 同组）；pytest-xdist `--dist loadgroup` | 并行互扰 |
| **asyncio 上下文** | BDD 步骤用 `event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`）；集成裸 async 函数内直 await（**禁 run_until_complete——已运行 loop 上抛 RuntimeError 会误触发 skip**，6-4 集成教训）；`asyncio.Lock` 类变量 | context 丢失误 skip |
| **savepoint 不适用** | 服务内含 L2 落库链——集成/验收用「真实提交 + 按 plan_id/report_id 定向 DELETE 清理」（6-4 docstring L17-18 钦定口径；**禁手动 delete/truncate 共享表**——定向清理例外钦定） | 回滚不覆盖独立会话 |
| **延迟 import** | 本 Story 新模块一律在步骤/装配函数体内 import（收集期零 ImportError——红阶段必须是运行期） | 整文件 collection error |
| **pytestmark 完整性** | `acceptance + database + redis + qdrant + minio + xdist_group`（marker 名以 pyproject 注册为准：PG 用 `database` 非 `postgresql`——6-3 R2-F23）；Task 7.2 专项复核（6-3 丢失修复教训） | marker 漏标漏跳 |

**禁止行为：**
- ❌ 验收/集成 mock 存储端口（mock 仅限外部 SaaS 豁免面）
- ❌ `@pytest.mark.skip` 写死跳过（必须 `pytest.skip()` 动态探测）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ autouse fixture 删除全局匹配资源
- ❌ pytest-xdist 并行时 BDD 步骤内 `asyncio.run()`

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 报告生成主链五段编排 | Task 2 | 2.1-2.6 聚合服务 | `test_report_generation_service.py` |
| AC-1 | L0/L2 持久化 + 用例 + 组合根 | Task 3 | 3.1-3.6 仓储/用例/组合根 | `test_report_repository.py` / `test_generate_markdown_report_use_case.py` |
| AC-1 | CLI `report-generate` 入口 | Task 3 | 3.7-3.9 CLI | `test_agent_cli.py` |
| AC-1 | 全链真实服务验证 | Task 5 | 5.1-5.2 场景① | `test_integration_markdown_report.py` |
| AC-1/2/3/5/6/7 | 验收场景（13 场景主体） | Task 0/7 | 0.4-0.6 Gherkin + 7.1-7.2 步骤 | `test_acceptance_markdown_report.feature/.py` |
| AC-2 | 章节结构冻结（章节/小节/display_name） | Task 1 | 1.1-1.3 实体/VO + 1.4-1.6 渲染器 | `test_strategic_report.py` / `test_markdown_report_renderer.py` |
| AC-2 | 全链章节断言 | Task 5 | 5.2 场景①（含章节结构断言——R3 校正：原标②系场景号错位） | `test_integration_markdown_report.py` |
| AC-3 | 标题/列表/表格格式化 | Task 1 | 1.4-1.5 渲染器块型 | `test_markdown_report_renderer.py` |
| AC-3 | 集成格式化断言 | Task 5 | 5.2 场景② | `test_integration_markdown_report.py` |
| AC-4 | 部分缺失降级/全缺 490/快照过期容错 | Task 2 | 2.1-2.3 降级语义 | `test_report_generation_service.py` |
| AC-4 | 缺失/缺三步/全缺集成验证 | Task 5 | 5.2 场景③③b④ | `test_integration_markdown_report.py` |
| AC-4 | 异常 490 BDD 场景 | Task 0/7 | 0.4 Gherkin + 7.2 步骤 | `test_acceptance_markdown_report.py` |
| AC-5 | ReportGenerated 发布 + outbox 断言 | Task 2 | 2.4-2.5 事件发布 | `test_report_generation_service.py` |
| AC-5 | 事件零新增守护 | Task 4 | 4.1 契约测试 | `test_event_channel_mapping_report.py` |
| AC-6 | 6-x 冻结面零触碰 + 全量回归 | Task 4 | 4.2-4.4 回归面 | 既有测试零修改通过 |
| AC-6 | 六边形架构约束验证 | Task 6 | 6.1-6.4 架构验证器 | `test_markdown_report.py` |
| AC-7 | P95<30s/成功率/并发 3 | Task 5 | 5.4 性能采样 | `test_integration_markdown_report.py` |
| AC-7 | 清理闭环净增 0 | Task 5 | 5.5 净增断言 | `test_integration_markdown_report.py` |
| AC-7 | 性能口径落档 | Task 0 | 0.2 OD-8 口径 | docstring 断言面 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7（规范源头）

> **目的：** 在进入代码实现前，明确章节结构冻结表、要素渲染映射、端口契约、异常契约、验收标准与六边形架构边界。

- [x] Subtask 0.1: 复核确认「报告章节结构与要素渲染映射冻结表」（本 Story SDD 节已定稿——四步「三组 bullet_list 前置行标签」已预裁定**加粗行标签**形态（章节结构冻结节——不开 H4，R1 裁定不再二选一）；六 Schema 全字段→块型映射不得增删；含图类产物表格承载映射 OD-9；**三态判定/原因解析次序/计数单位（section_count=11 口径）三项 R1 定稿复核确认**）；开 report 异常段 (490,499)——`grep -r "EXCEPTION_49" src/domain/exceptions/` 零碰撞实证；复核 chain 归档 `final_answer` payload 三态（gap asdict 六键 :327/六子 structured_output 原样 :436-440/synthesis asdict 两键 :527——**行号基准 HEAD@6bc6878f，Task 0.8 复核为准**）与降级信封态字段形态（信封键集 ⊆ {degraded, degrade_reason}——三态判定②的判别依据，AC-4 冻结版）
- [x] Subtask 0.2: 冻结「性能口径差声明」（OD-8：生成窗口=聚合起点→事件发布返回，不含 BLM run 前置；P95 数学口径 `sorted(durations)[ceil(0.95*n)-1]`——n=20 即次大值噪声敏感如实承受；**采样形态=单一数据源 plan_id × 20 次生成**（OD-10 幂等锚合法采样，构造成本=归档链一次）——R1 裁定替代原「20 独立 plan_id」；成功率口径=正常路径 N 生成 N 三元可读回，N 与采样轮数同源=20）
- [x] Subtask 0.3: 定义端口契约（report_generation.py / report_repository.py 模块 docstring 契约区：L0 memory_type="reports" 命名约定/文件命名 `{plan_id}_{YYYYMMDDHHMMSS}`/双源读径契约/降级判别规则）【Task 2/3 端口文件落地——report_generation.py 模块 docstring 全契约区在位（memory_type/文件命名/file_path 逻辑路径/双源读径/三态降级判别/八 stage 期望集派生公式 EXPECTED_REPORT_STAGES 常量）】
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_markdown_report.feature`（13 场景钉死——AC-1×2/AC-2×2/AC-3×1/AC-4×3/AC-5×1/AC-6×1/AC-7×2/收尾×1）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_markdown_report.py`（三件套骨架 + 延迟 import + teardown 清理链设计：报告三元 + 6-4 `_cleanup_archive_residues` 移植；**L0 写路径隔离验收层同钦定【R2 补——与 Task 5.1 同款三理由：真实 resolve 写运行机器 ~/.sisys/memory/reports/ 污染 + SCOPED lambda 缓存 resolve 后 setenv 不生效 + 并行计数互扰】**：tmp_path 自建 `FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path)))` 覆写注入 + _restorers 还原——6-3 端口覆写先例）【实施修正：注册表 register_port 同名异 spec 抛 ConflictError 不支持覆写——落地形态为服务实例层注入 tmp_path L0（6-3 验收 CheckpointService 手动构造同款先例），teardown ① restorers 链保留】
- [x] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——运行期 ImportError 形态，13 场景收集期零错误）【实证：13 collected 零收集错误；12 场景 ModuleNotFoundError(src.application.ports.report_generation) + S13 收尾场景 NotImplementedError——均为运行期失败】
- [x] Subtask 0.7: 链路接线断言清单落档（组合根三注册/事件发布点/outbox 断言键/alembic 017 幂等）+ deferred-work.md 台账处置（L129 data_pipeline 轨再锚定注记 + 新留项登记：REST 导出面触发条件）【四处处置落档：L129 OD-2 偏离注记/L170 事件消费基建顺延注记/L192 ChainOfThoughtSchema 零触发注记/新登记 6.5a-DF1 REST 导出留项】
- [x] Subtask 0.8: 关键代码锚点复核（并行会话提交会使行号漂移——上表锚点逐条 grep 复验；payload 三态/降级信封字段形态亲验定稿渲染容错规则）【五 Agent 并行调研+主会话亲验双重复核——锚点 36 处全量吻合 + 两处校正：484 是 CheckpointIntegrityError 非 CheckpointStorageError（(layer,...) 形态真身=ArchiveStorageError 284 archive_exceptions.py:77-111——491 直接模板）；EXCEPTION_HTTP_MAP 在 exception_handlers.py:152 非 exceptions/__init__.py】
- [x] Subtask 0.9: 既有契约测试回归基线（`pytest tests/contracts/ -q` 全绿记录）【基线：1479 passed in 23.81s（2026-11-03）】

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（两张冻结表 + 口径 + 契约）
- [x] 验收测试运行失败（预期行为，红阶段确认——运行期 ImportError）
- [x] 台账处置落档

---

### Task 1: 领域层——报告文档 VO + 渲染器纯函数 + StrategicReport 实体 + report 异常

**关联 AC:** AC-2 / AC-3 / AC-4（标注形态）/ AC-1（实体）

> **零外部依赖纯函数域**——本 Story 覆盖率主仓区（domain≥90%）；渲染规则=BLM 方法论领域知识（R5：领域层承载业务规则）。

#### TDD 循环 A：StrategicReport 实体 + 报告 VO

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/test_strategic_report.py`（实体不变量：report_type 枚举成员校验拒绝裸 str/file_path 非空/degraded≤total；VO：level 值域/kind 白名单/表格列一致——242 异常码断言） |
| 🟢 绿 | 实现 `src/domain/entities/strategic_report.py` + `src/domain/value_objects/markdown_report.py` 最小代码 |
| 🔄 重构 | 类型注解 + Google 风格全中文 docstring + `ruff`/`mypy` |

- [x] Subtask 1.1: 🔴 红 — 编写实体/VO 失败测试【24 用例；实施发现并修复守卫盲区：str 行 len 巧合撞列数静默通过——VO 增 tuple 形态守卫先于列数校验】
- [x] Subtask 1.2: 🟢 绿 — 实现 `StrategicReport`/`ReportType`/`ReportSection`/`ReportBlock`/`MarkdownReportDocument`
- [x] Subtask 1.3: 🔄 重构 — 优化实体/VO 代码【ruff+mypy 零错误】

#### TDD 循环 B：Markdown 渲染器纯函数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_markdown_report_renderer.py`（章节结构渲染：H1/H2/H3 递进/目录锚点/元信息表；块型渲染：paragraph/bullet_list/table【表头+分隔行+行】/callout【`> ⚠️ [降级]`/`> ⚠️ [数据缺失]` 双形态】；中文字符原样；空 items/空 rows 边界） |
| 🟢 绿 | 实现 `src/domain/services/markdown_report_renderer.py`（`render_markdown_report(document: MarkdownReportDocument) -> str` 纯函数 + 块渲染私有函数族） |
| 🔄 重构 | 函数拆分/命名统一/注解 |

- [x] Subtask 1.4: 🔴 红 — 编写渲染器失败测试（含变异实证：改坏表格分隔行渲染→红→还原→绿）【17 用例；变异实证完成：分隔行 `---`→`-` 注入 → 3 failed（断言活着）→ 还原 → 全绿】
- [x] Subtask 1.5: 🟢 绿 — 实现渲染器【render_markdown_report 纯函数 + _render_block/_render_table/_github_slug/_render_section 私有函数族；GitHub slug 锚点（中文原样+空格→连字符）；目录收录 H2 章级冻结】
- [x] Subtask 1.6: 🔄 重构 — 优化渲染器【walrus 过滤空块；空表头零列表格返回空列表；ruff+mypy 零错误】

#### TDD 循环 C：report 异常双类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_report_exceptions.py`（构造/context 暴露/to_dict/HTTP 映射 490→404、491→500） |
| 🟢 绿 | 实现 `src/domain/exceptions/report_exceptions.py` + `_code_ranges.py` 开段注册 + `__init__.py` 导出 + `EXCEPTION_HTTP_MAP` + design.md 编码分配表更新 |
| 🔄 重构 | 全量异常回归（`pytest tests/unit/domain/exceptions/ -v` 含 uniqueness/code_ranges 8 项 + `test_exception_handlers.py`） |

- [x] Subtask 1.7: 🔴 红 — 编写异常失败测试【20 用例（双类构造/登记联动——CR1-F28 勘误：原记 21，实测收集 20）】
- [x] Subtask 1.8: 🟢 绿 — 实现异常双类 + 四处登记（文件/码段/导出/映射）【report_exceptions.py + _code_ranges 开 report 段 (490,499)+双类注册 + __init__ 导出 + EXCEPTION_HTTP_MAP（exception_handlers.py——调研校正：映射在 handlers 非 exceptions/__init__）+ design.md 两张表回填（report 段行 + 483/484 既有漂移顺带修正——R1-18 钦定）；联动既有 test_exception_handlers.py 键集合快照同步登记】
- [x] Subtask 1.9: 🔄 重构 — 异常回归全绿【tests/unit/domain/exceptions/ 全量 672+ passed 含 uniqueness/code_ranges 自动发现零改动】

**完成标准/Definition of Done:**
- [x] 实体/VO/渲染器/异常全部实现（domain 零依赖——importlinter 验证）【lint-imports 5 kept 0 broken】
- [x] TDD 循环全部通过（含变异实证）【循环 A 24 用例 + 循环 B 17 用例（变异实证）+ 循环 C 20 用例（CR1-F28 勘误：原记 21 实测 20）；tests/unit/domain/ 全量 3620 passed】
- [ ] 覆盖率 domain ≥90%（本 Story 新增面 100% 关键路径）【Task 7 全量覆盖率门禁复核】

---

### Task 2: 应用层——ReportGenerationService（双源聚合 + 降级 + 渲染编排 + 事件）+ 端口

**关联 AC:** AC-1 / AC-4 / AC-5

> **五依赖注入**：`chain_archive_service: ChainOfThoughtArchiveServicePort` + `snapshot_repository: SnapshotRepositoryProtocol` + `l0_storage: L0StoragePort` + `report_repository: ReportRepositoryProtocol` + `event_publisher: EventPublisher`（R2——应用端口组合注入 R1 基础端口 + 应用层端口）。

#### TDD 循环 A：双源聚合与降级语义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_report_generation_service.py`（聚合分派：八 stage → gap/六节/synthesis 章节【stage 锚匹配 `performance_gap`/`market_insight_{step}`/`market_insight_synthesis`】；payload JSON 解析【gap 六键/六子 dict/synthesis 两键】；降级三态：源 degraded→callout、归档行缺→[数据缺失]、全缺→490；latest 快照 timeline→附录 A、缺→省略） |
| 🟢 绿 | 实现 `src/application/services/report_generation_service.py` + `src/application/ports/report_generation.py`（聚合私有函数族 + 文档 VO 组装 + 渲染调用） |
| 🔄 重构 | 分派表驱动化/纯函数提取 |

- [x] Subtask 2.1: 🔴 红 — 编写聚合/降级失败测试（AsyncMock(spec=Port) 五依赖 + `_make_*` 工厂——6-4 `_make_material` 形态；**TraceView 构造面提示**：records 每条五键含 chain VO（5 必填字段+全字段校验），建议参数化工厂 `_make_trace_view(stages, payload_kind)` 三态分派【正常/信封/缺失】——6-4 先例只构造空 view，本 Story 构造面显著更重，预估 60-80 行工厂）【落地：_make_trace_view 三态工厂 + ENVELOP 哨兵 + _full_stages_payload 覆盖映射——六组测试类 30 用例】
- [x] Subtask 2.2: 🟢 绿 — 实现端口 + 聚合服务【report_generation.py 端口（契约 docstring Task 0.3 落档）+ report_repository.py R1 端口 + report_generation_service.py 双源聚合（三态判定/原因解析次序/缺行骨架/附录 A 三源映射/附录 B 两类全收/五段编排）】
- [x] Subtask 2.3: 🔄 重构 — 优化聚合代码【聚合抽 _aggregate_document 模块级纯函数 + _Aggregation 局部累积（AC-7 无状态约束）；ruff+mypy 零错误】

#### TDD 循环 B：持久化编排 + 事件发布

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展同文件（L0 write 调用断言【memory_type="reports"/文件名锚 plan_id】+ L2 save 断言 + ReportGenerated 组装值级断言【独立构造期望事件比对——report_id/report_type/file_path 三键非空】+ **发布失败两形态**【①mock 返回 `PublishResult(event_id=str(uuid4()), results=(ChannelResult("reliable", False, "..."),))`→断言 warning+返回成功（event_id 必填首参） ②mock raise→同断言——双防线各钉一用例，防只写 except 恒绿假象】+ L0/L2 失败→491【layer 二元；L0 检出口径=R2 钦定：真实适配器 write 从不返回 False 只抛 OSError（目录创建/写文件失败均 OSError）——服务层 except OSError 包装 layer="l0" 为主，`write() is False` 返回值同查（端口契约面）】） |
| 🟢 绿 | 实现五段编排尾部（L0 write→L2 save→事件发布→实体返回；发布失败双防线检出【`if not result.is_success` 先判 + `except Exception` 兜底】→warning 宽容；L0/L2 失败 491 包装【layer="l0"/"l2"】） |
| 🔄 重构 | 无共同事务语境注释（save/publish 独立会话）+ 计时窗口（generation_ms） |

- [x] Subtask 2.4: 🔴 红 — 编写编排/事件失败测试（含变异实证：改坏事件 report_type 组装→红→还原→绿）【变异实证完成：report_type 组装改坏 → three_keys 断言红 → 还原 → 30 passed】
- [x] Subtask 2.5: 🟢 绿 — 实现编排尾部【L0 双检出口径（OSError 主形态 + write() is False 端口契约面）/L2 491 包装/事件双防线宽容（is_success 先判+except 兜底——warning 消息含 report_id/event_type/error）】
- [x] Subtask 2.6: 🟢 端口契约测试 `tests/contracts/test_port_contract_report_generation.py`（五断言族——服务面注册在 Task 3 组合根落地后 resolve 断言转绿）【编写完成待 Task 3 注册后转绿】

**完成标准/Definition of Done:**
- [x] 聚合服务 + 端口实现完成
- [x] TDD 循环全部通过（含变异实证）【30 用例全绿 + 事件变异实证】
- [ ] 覆盖率 application ≥85%【Task 7 全量覆盖率门禁复核】

---

### Task 3: 基础设施 + 用例 + 组合根 + CLI

**关联 AC:** AC-1（CLI 入口 + L2 落地）

> **工具先行**：alembic migration 先行（017_strategic_reports）——ORM 模型/仓储/migration 三件同 Task；**6-4 P0 教训直接应用**：report_repository 组合根注册从第一天带 `session_factory` 注入（archive_repository CR1-F1 双模式 fallback 修复后的形态为基准，不做裸构造后补）。

#### TDD 循环 A：L2 报告仓储（migration + ORM + repository）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/postgresql/test_report_repository.py`（save→get_latest_by_plan 双向/多报告取最新 created_at/真实 PG Schema 隔离——savepoint 或定向 DELETE 清理，按本 Task 事务面钦定） |
| 🟢 绿 | 实现 `models/report.py`（ReportModel）+ `deploy/postgresql/alembic/versions/017_strategic_reports.py`（只增）+ `src/infrastructure/storage/postgresql/repository/report_repository.py`（PostgreSQLReportRepository，session_factory 可选尾参构造——**application 层禁 import infrastructure 由端口注入隔离**） |
| 🔄 重构 | `alembic upgrade head` 幂等验证 + migration downgrade 链验证 |

- [x] Subtask 3.1: 🔴 红 — 编写仓储失败测试【mock-session 模式（isolation 模板）四测试类 12 用例】
- [x] Subtask 3.2: 🟢 绿 — 实现 ORM/migration/repository【ReportModel（metadata_ 属性名避开保留字）+ 017 migration + PostgreSQLReportRepository（session_factory 第一天注入 + save/get 双模式 fallback + 直调 get_session catch RuntimeError 防呆）】
- [x] Subtask 3.3: 🔄 重构 — migration 幂等验证【测试库 5433 实证：016→017 升级成功 + 二次 upgrade 幂等零输出 + 9 列 2 索引与冻结基线一致；实施修正：_persist 私有名避免覆写基类 _do_save 钩子（LSP）+ add/flush 纯 INSERT 编排（report_id 恒新 uuid4）】

#### TDD 循环 B：用例 + 组合根三注册块

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_generate_markdown_report_use_case.py`（plan_id UUID 守卫【非法→EntityValidationError 242——get_blm_chain_trace 先例】/透传/返回实体） |
| 🟢 绿 | 实现 `src/application/use_cases/generate_markdown_report.py` + 组合根三注册块（report_repository SCOPED session_factory 注入 / report_generation_service SINGLETON 五依赖 resolve / report_generation_use_case SINGLETON——`=== Story 6-5a ===` 分节注释，checkpoint_service :2293-2308 形态模板——R4 传播修复：锚点表 R1 校正值同步） |
| 🔄 重构 | 契约测试 resolve 断言转绿 + 既有组合根断言零破坏复核（增量注册不动既有 lambda——6-4 0.8⑥ 亲验先例） |

- [x] Subtask 3.4: 🔴 红 — 编写用例失败测试【3 用例（守卫 242 context 三键/守卫先于调用/透传返回）】
- [x] Subtask 3.5: 🟢 绿 — 实现用例 + 三注册块【组合根 `=== Story 6-5a ===` 包裹式分节（6-3 先例）；report_repository SCOPED session_factory 注入 / report_generation_service SINGLETON 五依赖 / report_generation_use_case SINGLETON】
- [x] Subtask 3.6: 🔄 重构 — 契约断言全绿【test_port_contract_report_generation.py 11 passed（组合根落地后 resolve isinstance 全转绿）；既有组合根断言零破坏——契约全量回归 Task 4.3 覆盖】

#### TDD 循环 C：CLI report-generate 子命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（参数解析 `--plan-id`/成功打印【report_id/file_path（逻辑路径）/memory_id/章节计数汇总行——**R2 补 memory_id 打印**：人类用户经 memory_id + `L0StoragePort.read(memory_id,"reports")` 或 base 目录提示定位物理文件，逻辑路径单独打印不构成定位信息】/双层异常定式【DomainError 分支=`[{code}] {message}` stderr + return 1；Exception 分支=仅 logger.error + return 1】/CLI 生产通道 PG session 可达【组合根 session_factory 注入实证——**6-4 P0 排查法三步必跑**】） |
| 🟢 绿 | 实现 `src/entrypoints/agent_cli.py` `report-generate` 子命令（argparse 扁平——checkpoint-create :337-392 模板——R4 传播修复：锚点表 R1 校正值同步；resolve `"report_generation_use_case"`） |
| 🔄 重构 | 打印格式统一（`_print_report_summary` 辅助） |

- [x] Subtask 3.7: 🔴 红 — 编写 CLI 失败测试【Parser 两例 + Execution 四例（成功摘要含 memory_id 打印/490 stderr/242 守卫先于用例/意外异常 logger-only）】
- [x] Subtask 3.8: 🟢 绿 — 实现子命令【argparse 扁平（--plan-id required）+ _run_report_generate 执行器 + _run_report_generate_cli 五步定式（chain-query 模板）+ _print_report_summary（report_id/报告类型/逻辑路径/memory_id/章节计数汇总/耗时）+ main if 链分发】
- [x] Subtask 3.9: 🔄 重构 — CLI 代码优化【CLI 全量 102 passed；mypy 746 零错误】

**完成标准/Definition of Done:**
- [x] migration/ORM/仓储/用例/组合根/CLI 全部实现
- [x] `alembic upgrade head` 幂等 + 四目录相关测试全绿【单测相关面 3512+102+117 passed；全量回归 Task 4.3 两轮】
- [x] CLI 生产通道 session 可达性实证（非三重遮蔽态）【三步排查实证：①组合根 lambda 带 session_factory=resolver.resolve("session_factory") ②session_factory 端口注册在位 ③agent_cli 全文零 set_session/session_context——CLI 可达性全靠组合根 lambda + 仓储双模式 fallback】

---

### Task 4: 契约守护与 6-1/6-2/6-3/6-4/5-3 回归面

**关联 AC:** AC-5（零新增）/ AC-6

> **性质说明：** 负向契约断言 + 全量回归（纯读侧Story 的回归面守卫）。

- [x] Subtask 4.1: 🔴🟢 编写 `tests/contracts/test_event_channel_mapping_report.py`（event_channels.yaml + DEFAULT_MAPPINGS 零 diff 守护——**登记集合冻结快照相等断言**：①ReportGenerated 既有登记存在性【yaml :273-276 与 DEFAULT_MAPPINGS :346-351 双侧——routing key `sisys.events.reliable.report_generated` + reliable 单通道】②事件登记键集合与冻结基线全等【yaml 事件名集合 == 基线集合，防本 Story 意外新增事件名】。**R1 裁定：6-4「缺席断言 token 零命中」范式在本 Story 不适用**——`report_generated` 是 Epic 1 既有登记 token（routing key 内在位），按零命中断言必当场误伤既有登记；本 Story 零新事件，负向守护面=键集合全等而非 token 缺席）【6 用例：双侧登记存在性/单通道无 redis/运行时查表/键数 56 冻结/双侧键集互等】
- [x] Subtask 4.2: 6-x 冻结面零触碰验证（blm_planning_prompts.py/blm_planning.py 契约区/chain 归档配方/ReportGenerated 事件类——git diff 逐文件零改动实证 + 负向断言）【git diff --stat HEAD 五文件零输出实证（prompts/blm_planning 端口/workflow_events/event_channels.yaml/channel_router）】
- [x] Subtask 4.3: 全量回归（四目录显式：`pytest tests/unit tests/integration tests/contracts tests/acceptance`——裸 `tests/` 会挂起，全量回归四目录命令纪律；两轮稳定）【两轮实证：R1=14574 passed + 14 failed（13 本 Story 验收骨架预期红 + 1 sqlalchemy 架构测试误报——docstring 提及 SQLAlchemyError 字样触发字符串匹配，改措辞修复）；R2=14575 passed + 13 failed（仅验收骨架预期红）——两轮稳定】
- [x] Subtask 4.4: 红线三查（`grep -rn "raise ValueError" src/` + `grep -rn "HTTPException" src/ | grep -v handlers` + `grep -rn "# noqa\|# type: ignore\|# pylint" src/ tests/` 零输出）+ 提交信息禁 AI 署名【①raise ValueError 零输出 ✓；②HTTPException 10 处 + ③抑制注释 23 处经归属甄别均为既有存量（91-1 立项面/既有测试文件）——本 Story 全部新建/修改文件零命中 ✓】

**完成标准/Definition of Done:**
- [x] 契约测试全绿 + 零 diff 实证【事件契约 6 passed + 端口契约 11 passed + 既有契约 1479 基线】
- [x] 四目录全量回归两轮稳定
- [x] 三条 grep 零输出【本 Story 面零输出——存量残留属 91-1 既有立项】

---

### Task 5: 集成测试——真实链五场景（①②③④⑤——③b 为③的第二断言块非独立场景，R2 计数澄清）

**关联 AC:** AC-1 / AC-2 / AC-4 / AC-7

> **真实服务四件（Redis/PG/Qdrant/MinIO）+ Fake LLM/Embedding 双豁免**——服务内含 L2 落库链：**真实提交 + 按 plan_id/report_id 定向 DELETE 清理**（savepoint 不适用——6-4 钦定口径）； teardown 链 + 跑前跑后净增 0。

- [x] Subtask 5.1: 编写 `tests/integration/test_integration_markdown_report.py` 装配（`_ReportChain` 装配类——6-4 `_CheckpointChain` 形态模板：真实 resolve + Fake LLM **八键族**身份分派【集成数据面为逐 stage 归档构造（不经 LLM run）——Fake 面仅 Embedding 豁免；归档素材 _make_material 三型分派移植】+ Fake Embedding 1024 维 + `_probe_services` async 直 await 探测【禁 run_until_complete】+ **L0 写路径隔离**【tmp_path 自建 FileMemoryAdapter 服务实例层注入——R1-17 三理由；实施修正：注册表 register_port 同名异 spec 抛 ConflictError 不支持覆写，6-3 验收先例真身即服务实例注入】+ teardown：报告侧【outbox report 行 + L2 行定向 DELETE】+ 归档三面【6-4 `_cleanup_by_plan_id` 移植：PG 档案行/Qdrant 点/MinIO WORM】）【实施追加：`_fresh_resolver_per_test` autouse fixture——SCOPED/SINGLETON 缓存实例 asyncpg 池绑首用 loop，pytest-asyncio 每函数新 loop 跨测试复用必炸 different loop（6-1 场景③ clear_singleton 先例防线 + clear_scoped 补全）】
- [x] Subtask 5.2: 场景①全链生成（八步归档 → generate → 报告三元断言 + 章节结构断言【display_name 源独立构造期望——MARKET_INSIGHT_STEP_CONFIG.values() 迭代构造 2.1~2.6】）+ 场景②格式化断言（ATX 层级遍历/PESTEL 表头定位法 6 行/五力 5 行/列表项数/中文原样）+ 场景③降级语义（**逐 stage 归档七次跳过目标步——AC-4 冻结版钦定构造** → [数据缺失] callout + degraded==1 + 附录 B 行）+ 场景③b 缺三步不变量（六子缺三步 → degraded==3 ≤ section==11 无 242 报告成功）+ 场景④490 全缺（**从未归档的独立 plan_id** 天然 total==0 → code/message/context 断言 + 零落库断言）
- [x] Subtask 5.3: 🔴 红→🟢 绿循环（首跑 4 failed【装配缺口：跨 loop 缓存实例 + fallback 未触达】→ `_fresh_resolver_per_test` 防线修复 → 单进程 5 passed + xdist 并行两轮稳定——装配型红绿以「场景断言值级失败→全绿」为准 ✓）
- [x] Subtask 5.4: 场景⑤性能采样（**单一数据源 plan_id × 20 次生成**——OD-10 幂等锚合法采样，归档链只构造一次；每轮新 report_id【集合无重复断言】+ L2 行数累计 20 + 每轮即时读回【秒级覆写豁免口径】；execute 包裹计时（聚合→发布窗口）；P95 `sorted[ceil(0.95*20)-1]` <30s 断言通过【实测亚秒级】；OD-8 口径差声明落模块 docstring）+ 并发 3（asyncio.gather 三 plan_id——裸 async 测试函数内直 await，无 BDD 跨 loop 陷阱；三元互不串扰断言【每 plan 恰 1 行 + report_id 互异】）
- [x] Subtask 5.5: 净增 0 断言（跑前基线计数 → 清理后对照【报告行净增 0 + outbox 报告行残留 0】——场景①/⑤双承载）
- [x] Subtask 5.6: 覆盖率集成 ≥75% 复核【整体 92%（三目录 cov run）≥75% ✓】

**完成标准/Definition of Done:**
- [x] 五场景全绿（真实服务环境）【单进程 5 passed + xdist 并行两轮 5 passed 稳定】
- [x] 净增 0 + 两轮稳定
- [x] P95/并发断言通过

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-6（架构面）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 6.1: 🔴 编写 `tests/unit/architecture/test_markdown_report.py`（epics L2260 钦定名——AST/import 扫描：渲染器/VO/实体零第三方 import【domain 零依赖】/聚合服务零 infrastructure import【application-no-infrastructure】/落位守护【新文件在冻结路径清单内】/CLI 不直依赖实现类）
- [x] Subtask 6.2: 实现四验证器（依赖方向/禁 import 黑名单/文件落位/端口经 resolver 解耦——test_checkpoint.py:1-60 形态模板）【四验证器 9 用例：A 零依赖双向校验【黑名单+白名单+src.domain 越层】/B 应用层隔离+本地 Protocol 禁令/C 落位存在+散落防护【__pycache__ 过滤修正】/D CLI resolve 端口名+服务依赖面全端口】
- [x] Subtask 6.3: 循环依赖检测（ruff `I` 规则/isort——不引入 pylint）【ruff I 规则承载——全仓 import 排序检查零错误】
- [x] Subtask 6.4: 运行完整测试套件并生成报告（四目录全量）【Task 7.3：14602 passed×2 轮稳定——架构测试 9 用例全绿在内】

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过【9 passed】
- [x] 测试输出清晰的合规报告
- [x] 任何违规都会导致测试失败
- [x] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-7（收尾）

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 完善 `tests/acceptance/test_acceptance_markdown_report.feature` 中的收尾验收场景（13 场景含收尾——Task 0 已钉死，此处补齐断言面） |
| 🟢 绿 | 完善 `tests/acceptance/test_acceptance_markdown_report.py` 的 BDD 步骤实现（收尾场景步骤：src 与四测试目录交付件存在性逐项断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达、pytestmark 完整性专项复核（6-3 丢失修复教训） |

- [x] Subtask 7.1: 收尾场景断言面补齐（src 交付件【实体/VO/渲染器/异常/端口/服务/用例/仓储/ORM/migration/CLI】+ 四测试目录交付件逐项存在性）【Task 0 骨架→完整实现：6-4 装配链移植（Fake LLM 八 Schema __name__ 分派/guard 链/CEO 实例化/图引擎/真实检索 R 门控）+ 双装配形态（完整 run/归档轻装配）+ 26 个 then 断言面全实现——display_name 源独立构造期望/表头定位法/两级 outbox 路径/jsonb 键族机理核实（子类三键嵌套 + 核心三键顶层）】
- [x] Subtask 7.2: 全部 13 场景转绿 + pytestmark 复核（acceptance/database/redis/qdrant/minio/xdist_group 六项齐备）+ Run with docstring【13 passed 单进程+xdist 双模式；实施攻坚记录：①`_clear_resolver_caches` 前后清防线（SINGLETON/SCOPED 缓存跨 loop/跨文件污染——xdist 组内被 6-x 先跑缓存污染+反向污染他人）；②环境故障排查（测试 Qdrant 容器假死→重启→RocksDB 残锁→清卷重建；测试库 migration 中间态→upgrade head 恢复）——均为环境损伤非代码回归，环境恢复后既有验收 51 passed 实证】
- [x] Subtask 7.3: 运行 `pytest`（四目录显式）、`ruff check`、`mypy` 收尾校验【**14602 passed / 2 skipped / 0 failed × 两轮完全稳定**（外部 LLM 门控 2 skip 动态跳过）；ruff All checks passed；mypy 746 零错误；覆盖率：整体 92%≥80% ✓ / domain+application 91%（≥90%/85%）✓ / 本 Story 新增文件 96-100%（renderer 98%/service 96%/实体 VO 异常 100%）✓】
- [x] Subtask 7.4: 三红线 grep + 提交信息审查（禁 AI 署名）+ deferred-work 留项终置（REST 导出面触发条件注记）【红线三查本 Story 全部交付文件零输出（仓内存量残留属 91-1 既有立项面——HTTPException docstring 提及×1/test_tool_domain_entities 既有 noqa×1）；deferred-work 四处处置已 Task 0.7 落档 + 6.5a-DF1 REST 导出留项在位】
- [x] Subtask 7.5: sprint-status.yaml 状态流转（review→done 由 code-review 环节）【in-progress→review 已落档 2026-11-04；review→done 归 code-review 环节】

**完成标准/Definition of Done:**
- [x] `src` 完成清单已逐项验证确认【S13 交付件存在性 11 项断言通过】
- [x] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认【S13 四目录 12 项断言通过】
- [x] 开发结束验收测试通过【13 场景全绿×双模式 + 14602×2 全量稳定】
- [x] Story 可进入 `review`/`done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)（活文档在 `docs/architecture/`——`_bmad-output/planning-artifacts/architecture.md` 是失效引用，勿寻）

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（ReportGenerated reliable 单通道 + Outbox——§10.1 L884「报告生成完成 | RabbitMQ + Outbox | 7 年存储 | 工作流型」）+ 五层存储（L0 文件/L2 关系/L4 对象——本 Story 用 L0+L2，L4 defer 6-5b）
- **设计约束:** 领域层零依赖（import-linter 四契约：domain-no-external-dependencies/dependency-direction/application-no-infrastructure/interfaces-no-infrastructure）；`@dataclass(frozen=True)` 不可变 VO；服务经端口组合注入（R2）
- **接口治理:** 统一端口注册（PortSpec：name/version/interface/impl/module/lifetime/owner/compatibility/tags）、Registry/Resolver/ContractGate、组合根唯一装配、契约优先、增量注册零破坏既有 lambda
- **技术栈:** Python 3.11+ / SQLAlchemy 2.0（ReportModel Mapped/mapped_column）/ alembic（017 只增）/ aiofiles（L0 既有）/ pytest-bdd + pytest-xdist（loadgroup）
- **关键架构条款:** architecture.md 交互流程 35-38（L413-417：PlanningUC→PrefectEngine→ReportFlow→L2 元数据+L4 证据包——**本 Story OD-2 偏离声明：宿主形态应用服务直交，存储去向设计保留**）；prd FR-UI-11（L1997 P0：标准报告 <30s）；NFR-PERF-03（L2397）；§13.17.1 L2487-2489（REST /reports/* 归后续 Story）

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | 范围边界：6-5a = 按 plan_id 事后聚合生成（CLI `report-generate`）+ 领域渲染纯函数 + L0 落盘 + L2 `strategic_reports` 元数据 + ReportGenerated 首激活。**不含**：PDF/引文（6-5b——其 Given 钦定「Markdown 报告已生成」即本 Story 持久化产物）、白标（6-11）、高管视图（6-8）、REST `/plans/{id}/export`（interface-design.md:1466 P0 归 Epic 7 API 入口立项——6-4 OD-1「REST 归后续 Story」先例）、图本体位图渲染（OD-9 表格承载）、思维链全文附录（YAGNI——chain.to_display() 资产已可消费，呈现归 6-5b/6-7） | epics L2224-2264 + L2033-2036 三下游依赖钦定 + 6-4 OD-1 渐进形态先例 |
| **OD-2** | **宿主形态偏离声明**：应用服务+用例+CLI 直交（**偏离** architecture.md 交互流程 35-38 Prefect 拓扑与 6-1 边界表 L38「报告归 Prefect 数据管线」预判）。理由：①MVP 单次同步生成（<30s 纯读+渲染+写）无 DAG 编排/重试/批处理需求 ②Prefect flows 轨现状：document_processing_flow 至今无生产触发方（deferred-work L129）③6-2/6-3/6-4 连续三期应用服务+用例+CLI 形态（checkpoint-create/chain-query 事后操作同族）④Prefect server 依赖与 no-mock 红线下验收/集成真实链可测性冲突。**存储去向设计保留**：L2 元数据落地（交互流程 37）；L4 证据包 defer 6-5b（引文证据同批）。data_pipeline 轨再锚定批量管线需求/Epic 7 定夺（deferred-work L129 注记——Task 0.7 落档） | 物理可达性 + 既有形态连续性 + 最小契约变更原则 + 6-1 DC-10「候选宿主」措辞本就是候选非钦定 |
| **OD-3** | **双源聚合**（gap 四字段无独立快照缺口的正解）：主源 = `query_chain_trace(plan_id)`（PG 档案行 7 年——八步 `final_answer` payload JSON 三态：gap asdict 六键/六子 structured_output 原样/synthesis asdict 两键 + degraded 锚 + stage 锚）；辅源 = latest 快照（timeline→附录 A + phase 元信息；TTL 86400 过期容错省略）。**不读 per-step 快照**（chain 归档已覆盖 structured_output，避免双源不一致 + TTL 事后不可靠）。**零改动**：6-1/6-2/6-3/6-4 全部冻结面零触碰（纯读侧） | chain 归档是全量结构化产物唯一持久面（agent 调研+主会话双验）+ 单源优先原则 + 6-2「下游 6-5 需要结构化字段而非自由文本」的契约源兑现 |
| **OD-4** | **持久化三件**：L0 文件（`memory_type="reports"` 端口常量单源；`memory_id=f"{plan_id}_{YYYYMMDDHHMMSS}"`；**file_path=L0 逻辑路径 `reports/{memory_id}.md` 单源派生——R1 裁定（非绝对路径）**：`L0StoragePort.write` 返回 bool 不返回路径、base 物理路径归 infrastructure `MemoryConfig`（application 禁知悉），逻辑路径零端口契约变更+可移植审计语义+消费方经端口 read 无需 base；memory_id 可经 `Path(file_path).stem` 反解）+ L2 `strategic_reports` 表（alembic 017 只增——交互流程 37「元数据保存→Relational_Storage」钦定 + 三下游查询面 + 7 年审计；对照 6-3 Redis 先例：报告是交付产物非流程状态，L2 正当）+ ReportGenerated 事件。L4 WORM defer 6-5b（引文证据包同批——reportlab 依赖同样预留未用先例） | 架构钦定存储去向 + 消费方清单（6-5b 找报告/6-8 展示/6-11 多模板管理）+ 审计 7 年（§10.1）+ 六边形依赖方向（application-no-infrastructure） |
| **OD-5** | **数据源降级语义**（可观测面非流程面——6-4 OD-5 同哲学；**R1 机理修正**：「archived=False」是 compose 返回的内存态不进快照，trace 读侧无此形态——「归档行缺」的物理形态= compose 445 失败 chain 缺席台账 / Step1 L2 写失败，284 后段失败形态下行通常在位正常渲染，报告读侧以 PG 行为准）：归档行部分缺 → 章节 `[数据缺失]` callout + degraded_section_count + 附录 B 记录，报告照常生成；**三态判定以 payload 形态为准**（解析失败→[数据缺失]/信封键集→[降级]带 reason/其余正常+锚叠加——AC-4 冻结版）+ 原因解析次序（payload.degrade_reason → 固定兜底文案，禁解析 reflection）；chain total==0 → `ReportGenerationError` 490（404——**最新快照在位亦同判**：时间线摘要非报告素材）；latest 快照缺/过期 → 附录 A 省略不阻断。epics「成功率 100%」口径重读 = 正常路径 N 生成 N 三元可读回，全缺 490 是业务异常非失败 | 降级可观测哲学三连先例（6-1 快照容错/6-4 归档降级）+ 报告完整性 vs 可用性权衡（部分数据报告 + 显式标注 > 全或无）+ 双 Agent 机理实证（archived=False 内存态/284 独立会话 commit） |
| **OD-6** | **事件零新增 + 异常开新段 + 发布失败宽容语义（R1 裁定）**：ReportGenerated 复用首激活（Epic 1 定义 + 双登记在位零 diff——docstring 钦定 Epic 6 生产者）；新增 report 异常段 (490,499)（`ReportGenerationError` 490 BusinessException 404 语义 / `ReportStorageError` 491 BusinessException layer 二元 {l0,l2} 语境——**值域自有元组禁复用 284 常量**）——planning 段 485 预留 486-489 留 6-6 不可占，report 语义独立按八代开段先例（410/420/430/440/450/460/470/480）开 490 段。**发布失败处置 = checkpoint ⑤ 宽容语义同构**（warning + 返回成功——非 284 上抛族：①报告真相源是 L0/L2 落盘，事件是通知面 ②284 上抛的回滚价值在 HTTP 同事务，CLI/报告面 save 与 publish 分属独立会话无共同事务，上抛回滚不了任何东西 ③上抛→exit 1→误导重跑→OD-10 不拦截→L0/L2 叠加多份 ④outbox 无 poller 现状下上抛换不来投递成功）。**失败检出双防线强制**：`is_success` 判定 + except 兜底（实现层吞异常只返回失败 PublishResult——纯 except 恒不触发，AC-5 两形态单测锁死） | `_code_ranges.py:189` 成文预留 + `:170-175` 开段先例 + YAGNI（零新事件=零 yaml/router diff）+ 事件双登记纪律 + checkpoint ⑤ 成文先例（`checkpoint_service.py:280`（快照真相源语义声明）+`:289-296`（宽容块）——R5 锚校正：原 :285-296 引述词与区间头错位；**结果语义同构、防线形态为增强**：先例单 except 对失败 PublishResult 静默，本 Story is_success 判定修正）+ EventPublisher 端口契约「错误内部消化返回 PublishResult」+ publish 仅 outbox 落行无 MQ 直发实证（断言等价机理） |
| **OD-7** | 测试文件命名（禁故事编号后缀）：unit/architecture 用 epics 钦定 `test_markdown_report.py`（L2260 一致）；integration `test_integration_markdown_report.py`（**对 epics L2261 钦定名 `test_markdown_report_integration.py` 的显式偏离**——仓规 tests/integration/ 全目录 test_integration_* 惯例，6-3 OD-8/6-4 OD-7 双先例）；acceptance `test_acceptance_markdown_report.feature/.py`；服务单测 `test_report_generation_service.py`；渲染器 `test_markdown_report_renderer.py`；仓储 `test_report_repository.py`；用例 `test_generate_markdown_report_use_case.py` | epics 钦定名半采半离 + 记忆「禁止故事编号命名文件」+ 双先例 |
| **OD-8** | **性能口径差声明**：生成窗口 P95<30s = 数据聚合起点→事件发布返回（纯内存渲染 + L0 写 + L2 insert + 事件发布）；**不含 BLM 流程本身**（run 是前置——epic 未预见 run 与报告生成两段分离，含 run 则物理不可达口径混淆）；**采样形态 = 单一数据源 plan_id × 20 次生成（R1 裁定）**——OD-10 幂等锚语义下重复生成是合法采样形态，构造成本=归档链一次（原「20 独立 plan_id」需 160 次 LLM+归档三面 I/O+三量级清理成本，与 6-3 先例【纯内存 25 次调用】不同量级）；成功率口径见 OD-5（N 与采样同源=20）；并发 3 = asyncio.gather 独立 plan_id + 服务无状态约束。口径差落测试 docstring（集成场景⑤） | 6-1 DC-7/6-2 OD-3/6-3 OD-6/6-4 OD-10 四连先例 + epic 指标物理可达性论证 + 构造成本工程评估（审查员 B 实证） |
| **OD-9** | **图类产物表格承载**：6-2 OD-8「图本体生成归 6-5 报告面」的 6-5a 落位 = Markdown 表格/列表承载（雷达图→能力维度表/价值主张地图→要点列表/增长路径图→路径列表/机会差距量化报告→要点列表——六 Schema 字段本就是要点字段族形态）；位图/SVG/mermaid 渲染 defer 6-5b（PDF 排版同批）。6-2 预判「图本体生成」在 Markdown 基础版以结构化表格兑现，断链声明落档 | epics L2235「基础格式化（标题、列表、表格）」钦定三要素无图片项 + 6-2 OD-8 断链预防 + YAGNI |
| **OD-10** | **幂等锚 = report_id 非plan_id**：同 plan_id 重复生成产生新报告（新 report_id/新 L2 行——get_latest_by_plan 取 created_at 最新）。**秒级时间戳窗口注记（R1 补）**：`YYYYMMDDHHMMSS` 秒内连跑 memory_id 相同 → L0 文件覆写一份，「新文件名」断言需跨秒或不断言 L0 件数（锚 report_id/L2 行——性能采样 20 轮同 plan_id 均按此锚断言）。不拦截重跑（blm-plan `--plan-id` 透传幂等锚语义对齐——重跑是预期用法而非防御面，6-1 CLI P1/P3 分歧裁定先例；AC-7 采样即依赖此语义）；报告版本链管理（旧报告保留）归 6-11 白标多模板立项定夺 | 6-1 重跑守卫裁定语义区分（plan 执行面拦截 vs 报告导出面放行）+ 最小面原则 + 秒级精度物理事实（FileMemoryAdapter 同名覆写实证） |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/                                    # R1 基础端口 + 报告领域知识（渲染规则=BLM 方法论）
│   ├── entities/strategic_report.py           ★ 新建（StrategicReport + ReportType——Task 1）
│   ├── value_objects/markdown_report.py       ★ 新建（ReportSection/ReportBlock/MarkdownReportDocument——Task 1）
│   ├── services/markdown_report_renderer.py   ★ 新建（render_markdown_report 纯函数——Task 1）
│   ├── exceptions/report_exceptions.py        ★ 新建（490/491——Task 1）
│   ├── exceptions/_code_ranges.py             ▲ 开 report 段 (490,499) + 两类注册（Task 1）
│   ├── exceptions/__init__.py                 ▲ 导入 + __all__ + EXCEPTION_HTTP_MAP（Task 1）
│   └── ports/report_repository.py             ★ 新建（ReportRepositoryProtocol——Task 2 定义 Task 3 实现）
├── application/
│   ├── ports/report_generation.py             ★ 新建（ReportGenerationServicePort + 常量 REPORT_FILE_MEMORY_TYPE——Task 2）
│   ├── services/report_generation_service.py  ★ 新建（双源聚合+五段编排——Task 2）
│   └── use_cases/generate_markdown_report.py  ★ 新建（Task 3）
├── infrastructure/
│   └── storage/postgresql/
│       ├── models/report.py                   ★ 新建（ReportModel——Task 3）
│       └── repository/report_repository.py    ★ 新建（PostgreSQLReportRepository——session_factory 注入【6-4 P0 教训】）
├── entrypoints/agent_cli.py                   ▲ report-generate 子命令（Task 3）
└── composition_root.py                        ▲ 三注册块 === Story 6-5a ===（Task 3——纯新增零既有改动）

deploy/postgresql/alembic/versions/017_strategic_reports.py ★ 新建（只增——Task 3）

tests/
├── unit/
│   ├── domain/test_strategic_report.py                 ★ 新建（Task 1）
│   ├── domain/services/test_markdown_report_renderer.py ★ 新建（Task 1）
│   ├── domain/exceptions/test_report_exceptions.py     ★ 新建（Task 1）
│   ├── application/test_report_generation_service.py   ★ 新建（Task 2）
│   ├── application/use_cases/test_generate_markdown_report_use_case.py ★ 新建（Task 3）
│   ├── infrastructure/storage/postgresql/test_report_repository.py     ★ 新建（Task 3）
│   ├── interfaces/cli/test_agent_cli.py                ▲ report-generate 用例扩展（Task 3）
│   └── architecture/test_markdown_report.py            ★ 新建（Task 6，epics 钦定名）
├── integration/test_integration_markdown_report.py     ★ 新建（Task 5，OD-7）
├── contracts/
│   ├── test_port_contract_report_generation.py         ★ 新建（Task 2/4）
│   └── test_event_channel_mapping_report.py            ★ 新建（Task 4）
└── acceptance/
    ├── test_acceptance_markdown_report.feature/.py     ★ 新建（Task 0/7，13 场景）
    └── （6-1/6-2/6-3/6-4/5-3 既有验收文件零修改——Task 4 回归验证）

docs/architecture/sisys-uni-exception-design.md          ▲ §3.3.2 编码分配表 + 子域范围表 report 段行（Task 1）
_bmad-output/implementation-artifacts/deferred-work.md   ▲ 处置注记（Task 0.7——L129 再锚定 + REST 导出留项）
_bmad-output/implementation-artifacts/sprint-status.yaml ▲ 状态流转（Task 7）
```

（▲ 修改 / ★ 新建 / 禁整文件覆盖——就地扩展纪律；`src/domain/events/workflow_events.py` 与 `configs/event_channels.yaml` 与 `channel_router.py` **零改动**——ReportGenerated 既有资产复用）

### 关键代码锚点（实现直读——五 Agent 并行调研+主会话亲验双重核验；行号基准 HEAD@6bc6878f，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| `ReportGenerated` 事件 | `src/domain/events/workflow_events.py:56-72` | Epic 1 定义零改动复用；字段 `report_id: UUID`（kw_only 必填）/`report_type: str = ""`/`file_path: str = ""`（**两键有缺省空串——构造点必显式传三键，漏传不炸产空串**）；`__post_init__` aggregate_id←report_id（仅 None 时）、aggregate_type="Report"（仅空时）；无 tenant_id 字段；docstring :60 钦定「由 Epic 6 故事实现生产者」——**本 Story 首激活** |
| 事件双登记（既有） | `configs/event_channels.yaml:273-276` + `src/infrastructure/messaging/channel_router.py:346-351` | reliable 单通道（rabbitmq key `sisys.events.reliable.report_generated`）——**零 diff**；outbox 断言键 `payload->'payload'->>'report_id'` 两级路径（子类字段经 to_dict 并入嵌套 payload 键——base.py:131-151；6-3 集成② `plan_id` 键先例同构，仓内无 archive_id 键 outbox 断言） |
| chain 归档查询面 | `src/application/services/chain_of_thought_archive_service.py:224-275` | `query_chain_trace(plan_id, include_blob=False) -> ChainOfThoughtTraceView`——records list[dict] 五键（stage/chain VO/archive_id/degraded/blob_content）；archived_at 升序（None 回落 epoch 下界）；空档案 total=0（490 判据）；**trace 读侧无「archived=False」形态**（records 全来自 PG 档案行——archived_count 恒= total） |
| payload 三态（渲染素材源） | `src/application/services/chain_of_thought_archive_service.py:19` docstring + `blm_planning_service.py:327/:436-440/:527` | `final_answer = json.dumps(payload, ensure_ascii=False)`——gap=asdict 六键（financial_gap/operational_gap/root_causes/portfolio_health/degraded/degrade_reason）/六子=structured_output dict 原样/synthesis=asdict 两键（conclusions/degraded_inputs）；**部分降级产物在位原样**（R2-F2）；降级信封态字段形态 Task 0.8 复核（渲染容错依据） |
| `ChainOfThoughtTraceView` | `src/application/ports/chain_of_thought_archive.py:116-132` | plan_id/records/total/archived_count——聚合主源 DTO（应用层内消费合法） |
| 六 Schema 冻结面（渲染字段源） | `src/application/services/blm_planning_prompts.py:31-129` | GapAnalysisSchema :31-37/六类型化 :53-109/`MARKET_INSIGHT_STEP_SCHEMA` :115-122/InsightSynthesisSchema :125-129——**零改动只读**；6-2 字段级冻结表（Story 文件 L752-791）是渲染映射契约源；注意 `summarize_gap_for_downstream`（:358-380）/`summarize_step_for_downstream`（:344-355）是 **prompt 注入用平文本**格式化（「财务差距=」四标签）——报告渲染**不复用**（报告要结构化块非平文本），勿混淆两个格式化面 |
| display_name（章节标题源） | `src/application/services/blm_planning_prompts.py:162-221` | `PERFORMANCE_GAP_CONFIG.display_name="业绩差距分析"` :164/`MARKET_INSIGHT_STEP_CONFIG` 六值（看趋势 :175/看市场与客户 :183/看竞争 :191/看自己 :199/看机会 :207/机会差距分析 :215——R1 校正：:194/:202 为旧行号）/`SYNTHESIS_DISPLAY_NAME="市场洞察综合"`（chain_of_thought_archive.py:45）——**逐字源不二次硬编码** |
| latest 快照读径 | `src/application/ports/blm_planning.py:18-22` + `GetBlmPlanningStatusUseCase`（get_blm_planning_status.py:41-57） | session_id=`blm-planning-{plan_id}`（前缀常量 :63 单源）；state_data 七键（timeline 条目六键含 started_at/completed_at/status/summary_excerpt/degraded）；TTL 86400（过期 None 容错）；480 PlanningNotFoundError 语义知悉（本 Story 对快照缺失降级省略——不透传 480，改判附录省略） |
| `SnapshotRepositoryProtocol` | `src/domain/ports/snapshot_repository_protocol.py:14-39` | R1 基础端口——load(session_id)->CheckpointSnapshot/None；聚合辅源注入 |
| L0 端口与实现 | `src/domain/ports/l0_storage.py:16-75` + `src/infrastructure/storage/fs/file_memory_adapter.py:49-69` | `write(memory_id, memory_type, content: str)->bool`（aiofiles 文本写）**——不返回路径（file_path 逻辑路径裁定 OD-4 的直接依据）**；`read(memory_id, memory_type)->str`（文件不存在抛 NotFoundError）；路径 `{base}/{memory_type}/{memory_id}.md`（.md 后缀适配器强加——memory_id 传参禁带 .md）；memory_type 自由字符串无枚举校验（"reports" 合法）；组合根注册 :261-275（SCOPED lambda 工厂——**缓存于 resolver 实例，resolve 后 setenv 不生效**，测试隔离须覆写注入）；`FileMemoryAdapter.get_path()` :251-261 已存在但不在 Protocol 契约面全仓零消费（不提升——零端口变更）；**无租户隔离**（memory_id 锚 plan_id 天然唯一——TestTenant 前缀叠加） |
| `StrategicArchiveService.query_archive` | `strategic_archive_service.py:315-324` | ArchiveQuery(plan_id, archive_type, limit)——chain 查询面内部已用（聚合经 ChainOfThoughtArchiveServicePort 间接消费，不直连） |
| L2 仓储形态模板 | `src/infrastructure/storage/postgresql/repository/archive_repository.py` | **session_factory 可选尾参 + 双模式 fallback 修复后形态**（6-4 CR1-F1）——report_repository 从第一天按此形态构造（不走裸构造后补）；组合根 `archive_repository` :2185-2194 注册样式（`lambda resolver: ...(session_factory=resolver.resolve("session_factory"))`） |
| ORM 模型模板 | `src/infrastructure/storage/postgresql/models/archive.py:20-50` | ArchiveModel Mapped/mapped_column/SA_UUID/JSONB/Base 继承（outbox.py Base）——ReportModel 同款形态 |
| alembic 先例 | `deploy/postgresql/alembic/versions/016_isolation_switch_log_domain_guard.py` | 最新 migration（017 顺位）；只增红线；`alembic -c deploy/postgresql/alembic/alembic.ini upgrade head` |
| 事件发布注入先例 | `src/application/services/checkpoint_service.py:108-130` | EventPublisher（domain/ports R1 基础端口）构造注入（**keyword-only——`*` 在前**）+ reliable 单通道注释形态——report_generation_service 五依赖之一；**发布容错两族分层先例**：③内 ArchiveCreated 失败→284 上抛（strategic_archive_service.py:285-294 双防线 `is_success`+except）/ ⑤CheckpointReached 失败→warning 宽容（:285-296 快照真相源）——本 Story ReportGenerated 归⑤族（OD-6 R1 裁定） |
| 组合根注册模板 | `src/composition_root.py:2293-2308`（checkpoint_service——R1 校正原 :2287-2302）+ `:2339-2363`（chain_of_thought_archive_service + blm_chain_trace_use_case 两注册块；**6-4 三处改动=本两块 + archive_repository v1.1.0 升级 :2185-2194 + blm_planning_service 尾部注入 :1584——原表述「三注册块 :2339-2363」失实，R1 校正**） | 分节注释两先例并存（6-3 包裹式 `# === Story 6-3 — 标题 ===` / 6-4 无包裹式）——6-5a 取 6-3 包裹式 `# === Story 6-5a — ... ===`；register_port(name/version/interface/impl/module/lifetime/owner/tags)；PortSpec 全字段另含 compatibility/deprecated 共 10；纯新增块零既有 lambda 改动 |
| CLI 先例 | `src/entrypoints/agent_cli.py:317-335`（chain-query）+ `:337-392`（checkpoint-create——R1 校正：原两区间混叠错标） | argparse 扁平+守卫形态；resolve `"report_generation_use_case"`；**双层异常定式**（DomainError=`[{code}] {message}` stderr+return 1 / Exception=仅 logger.error+return 1——6-4 终审形态）；**CLI 生产通道 PG session P0 排查法三步必跑**（6-4 教训：①组合根 impl=lambda 是否带 session_factory ②家族成员缺口排查 ③CLI 入口 grep set_session/session_context 断链检查——实证：agent_cli 全文零 set_session 调用，CLI 可达性全靠组合根 lambda 带 session_factory + 仓储双模式 fallback） |
| 验收装配先例 | `tests/acceptance/test_acceptance_checkpoint_snapshot.py:274-300`（teardown 六步链）+ `:346-430`（`_cleanup_archive_residues`——R1 校正区间）+ `test_acceptance_json_chain_of_thought.py:318-350` | teardown 六步链+`_cleanup_archive_residues`（PG 档案行/Qdrant 点/MinIO WORM 三面）——**本 Story 直接移植 + 报告三元清理扩展**（L0 文件 delete/L2 行定向 DELETE/outbox 行）；Fake LLM 复用 6-2 `_make_fake_llm` **八键族**身份分派（六类型化 + GapAnalysis + InsightSynthesis） |
| 集成真实链先例 | `tests/integration/test_integration_checkpoint.py` + `test_integration_chain_of_thought.py` | 四真实+双豁免+性能采样数学口径+真实提交定向清理（savepoint 不适用钦定 docstring L17-18——R4 勘误：R1-26 将原锚误校为 L16-17 偏前 1 行，实证语句跨 L17-18）；async 探测禁 run_until_complete（L125-126）；P95 采样先例 :616-621（**纯内存 25 次调用**——非全链采样，本 Story 构造成本对照见 OD-8） |
| 异常开段先例 | `src/domain/exceptions/_code_ranges.py:170-175`（八代开段成文）+ `:189`（planning 段预留声明） | 「前段满/双重成文预留不可占/语义独立→开独立段」；report 段 (490,499) 空置实证（grep EXCEPTION_49 零命中——Task 0.1 复跑） |
| pytest 配置 | `pyproject.toml:245-299` | asyncio_mode=auto/-n auto --dist loadgroup/--strict-markers；marker 注册清单（database 非 postgresql——R2-F23）；验收 conftest 自动加 acceptance+服务 marker（文件名关键词） |

### 锚定义务清单（deferred-work 台账——Task 0.9 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-5a 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L129 | orchestration_service/data_pipeline 轨废弃评估（6-1 注记：data_pipeline 轨=「Epic 6.5 报告管线候选宿主」） | **OD-2 偏离注记落档**：6-5a 落应用服务直交形态（候选宿主预判未采纳——理由 OD-2）；data_pipeline 轨再锚定批量报告管线需求（6-8/6-11 多用户场景）或 Epic 7 API 入口立项时一并定夺；orchestration_service 废弃定夺锚点不变 |
| 2 | 新登记 | REST 导出面 `/plans/{id}/export`（interface-design.md:1466 P0）无 API 契约与实现 | **新留项登记**：6-5a CLI-only（OD-1）；触发=6-8 高管视图立项或 Epic 7 API 入口立项（届时补 openapi.yaml 契约 + report_routes——architecture.md :2115/:2127 规划位） |
| 3 | L170 | 事件消费基建四件（归档事件消费方） | 预判**顺延**：6-5a 是 ReportGenerated 生产路径叠加非消费方（5-3/6-3/6-4 同款裁定）——注记落档 |
| 4 | L192（6-4 注记） | ChainOfThoughtSchema 演进触发条件 | **零触发注记**：6-5a 渲染消费 payload JSON 不经 ChainOfThoughtSchema——Schema 零触碰，留项维持 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-4 JSON 思维链输出](./6-4-json-chain-of-thought-output.md)（文档五轮+代码五轮双收敛 done 2026-11-03）+ Story 6-1/6-2/6-3（同款双五轮）

**关键学习/Key Learnings:**
- **Epic 1 骨架资产复用（6-3 头号教训 + 6-4 再证）**：立 Story 钦定「新建」前必须全仓 grep 同语义类型——本 Story 已执行：ReportGenerated 事件（Epic 1 定义+双登记+docstring 钦定 Epic 6 生产者）**零新增复用首激活**；L0StoragePort（reports memory_type）零新实现复用；六 Schema/display_name/payload 三态全部既有数据面只读消费。**唯一新建面 = 报告领域知识（实体/VO/渲染器）+ 聚合服务 + L2 仓储/migration + CLI**（应用层新服务与新表是合理增量——既有资产无此职责）
- **CLI 生产通道 PG session 三重遮蔽 P0（6-4 最高价值教训）**：「新增 CLI 入口消费既有 PG 仓储」必跑三步排查：①组合根 impl=lambda 是否裸构造（无 session_factory）②家族成员已修而它漏修的缺口 ③CLI 入口 grep set_session/session_context 断链。**本 Story report_repository 从第一天带 session_factory 注入**（Task 3 钦定 + CLI 单测断言生产通道可达）；测试绿 ≠ 生产通道可达
- **属性形态断裂族**（6-1 两犯+6-3 R1+6-4 R1-F2/R1-F9）：payload 三态（gap=asdict 六键 dict/六子=structured_output dict/synthesis=asdict 两键）**JSON round-trip 后 list[str] 与 tuple 形态**（渲染侧吃 dict 不重构 VO——避免 tuple 归一陷阱）；`InsightStepResult.tool_used` 单数 str vs `ChainOfThought.tools_used` tuple（本 Story 报告不消费工具字段——evidence_refs 归 6-5b 引文）；display_name 是配置值非字面量（**逐字源取用禁二次硬编码**——6-4 锚点表同款纪律）
- **断言判别力**（6-3 R1-F6/6-4 OD 表）：事件组装=独立构造期望对象值级比对（非读回自比）；章节断言=display_name 源取期望（非报告文本自证）；表格断言=行列数级（非仅含 `|` 字符）
- **no-mock 红线互斥裁定**（6-2 R3-4/6-3 0.8⑧/6-4 OD-5 三连先例）：L0/L2 写失败注入（491 layer 二元）归单测层 AsyncMock 承载；发布失败两形态（失败 PublishResult/raise）亦归单测层（宽容语义断言 warning+成功返回）——验收/集成 Edge Cases 不含持久化写失败容错
- **键清理闭环**（6-3 R1-F1 泄漏 1117+ 键）：本 Story 清理面=报告三元（L0 文件/L2 行/outbox 行）+ 归档三面（6-4 `_cleanup_archive_residues` 移植）+ Redis 快照键族——teardown 各步独立 try/except + 净增 0 断言（Task 5.5）
- **TDD Task 边界**（6-2 R1-2）：聚合降级语义（Task 2）与回归验证（Task 4.3）分离依据=纯读侧零改动假设——若回归发现 6-x 面意外受扰即回 Task 2/3 修根因（而非适配测试）
- **BDD 三件套+性能口径**（6-1~6-4 四连先例）：模块级 event_loop+context dict+`_run_async`；teardown 链断言失败也执行；P95 口径差声明落 docstring（OD-8）；xdist_group blm-planning-perf 组复用；pytestmark 完整性复核（Task 7.2 专项——6-3 丢失修复教训）
- **git diff HEAD 断言是 dev 窗口态守护**（6-4 R3 教训）：冻结面零触碰断言用「结构断言或缺席断言」非 git diff（提交后恒真空断言失效）；缺席断言 token 防既有登记误伤（锚定本 Story 专属 token + grep 四文件零命中实证后才写）
- **红线三处漏网教训**（6-1 R5 + 6-4 主会话自犯）：全程零抑制注释+提交信息禁 AI 署名+三条 grep 自查（Task 4.4/7.4）

**应用到本故事/Applied to This Story:**
- [ ] ReportGenerated/L0 端口/display_name/payload 三态全复用（Task 0.1 实证复跑 + Task 1/2 实现）
- [ ] report_repository session_factory 第一天注入 + CLI P0 排查法三步（Task 3 + CLI 单测）
- [ ] payload 三态渲染容错 + display_name 逐字源（Task 2 聚合）
- [ ] 事件/章节/表格三类断言值级独立构造（Task 2/5 + 单测）
- [ ] 持久化失败注入落位单测层（Task 2——OD-5/AC-4 钦定）
- [ ] 六面清理链+净增 0 断言（Task 5.1/5.5）
- [ ] 性能口径 OD-8 + xdist_group 复用 + pytestmark 复核（Task 5.4/7.2）
- [ ] 冻结面零触碰用结构/缺席断言（Task 4.2——git diff 仅 dev 窗口辅助）
- [ ] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep（Task 4.4/7.4）

### 其他约束速查

- **风险集中登记**：①最大回归风险 = 组合根三注册块（纯新增块零既有 lambda 改动——契约测试 getsource 断言面零破坏复核）；②CLI 生产通道风险 = report_repository session 注入（6-4 P0 同族——第一天带 factory + 三步排查）；③数据面风险 = payload 降级信封态误分类（**三态判定已冻结 AC-4——信封键集判定勿并入「解析失败」**，解析失败/形态不可识别才走 [数据缺失]；原因兜底文案防 reflection 文本解析）；④发布面风险 = 实现层吞异常（**is_success 双防线检出**——纯 except 恒不触发，两形态单测锁死）；⑤清理风险 = 报告三元+归档三面（净增 0 断言；L0 写路径 tmp_path 覆写隔离）；⑥migration 风险 = 017 只增红线（downgrade 链验证）；⑦计数口径风险 = section_count H3 小节口径（load-bearing——H2 口径下缺≥3 步炸 242，AC-4 缺三步场景锁死）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type:ignore/pylint:disable；提交信息禁 AI 署名
- **覆盖率**：整体≥80% / domain≥90%（渲染器主仓区）/ application≥85%（epics L2251 钦定）/ 集成≥75%（epics L2252）
- **覆盖率豁免不适用**：本 Story 非骨架 Story（渲染器/聚合服务/仓储全实质实现）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code） |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-11-03 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 6 节 L1999-2364；Story 6.5a L2224-2264） |
| **架构文档** | `docs/architecture/architecture.md`（活文档）+ `docs/architecture/sisys-uni-exception-design.md` + `docs/architecture/interface-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-4-json-chain-of-thought-output.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 6.5a 节 L2224-2264 + Epic 6 头部 L1999-2036）
- [x] 架构约束从 `docs/architecture/architecture.md` 提取（交互流程 35-38/§10.1 事件表/§13.17.1 接口规划）+ importlinter 四契约
- [x] 前一个故事学习经验整合（6-4 双五轮 + 6-1/6-2/6-3 锚点表）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0~7 / 52 Subtask——逐行点数：0.1-0.9（9）/1.1-1.9（9）/2.1-2.6（6）/3.1-3.9（9）/4.1-4.4（4）/5.1-5.6（6）/6.1-6.4（4）/7.1-7.5（5））
- [x] 项目结构对齐统一规范（双源聚合 / L0+L2 持久化 / 事件零新增 / 异常开段 490）
- [x] 五 Agent 并行调研（数据面/报告现状/存储端口与组合根/验收集成样板/UX 与架构文档）+ 主会话亲验（planning 异常形态/query_chain_trace 结构/payload 三态/L0 write/migration 目录/ORM 模型/事件双登记/284 基类/EventPublisher 注入九项关键事实）
- [x] Round 1 文档审查修订（2026-11-03：四视角调研 Agent【数据面/存储组合根/事件异常/测试样板】+ 三视角审查 Agent【一致性完备性/可行性可达性/科学性机理】——34 项处置 P0×2+P1×10+P2×10+P3×12；OD-4/5/6/8/10 五项修订 + 追溯矩阵重排 + 修复台账 R1-1~R1-26 落档；传播面 grep 核查零残留）
- [x] **dev-story 实施完成（2026-11-04——Task 0~7 全 52 Subtask 闭环）**：
  - 五 Agent 并行调研锚点复核（36+ 锚点吻合 + 两处校正：EXCEPTION_HTTP_MAP 真实在 exception_handlers.py:152；`(layer,...)` 家族形态真身 ArchiveStorageError 284 非 484）
  - 领域层（实体 24/渲染器 17 含分隔行变异实证/异常 20 用例【CR1-F28 勘误：原记 21 实测 20】+ 四处登记 + design.md 双表回填含 483/484 顺带修正）
  - 应用层（聚合服务 30 用例含事件变异实证 + 三态判定/原因解析次序/缺行骨架/锚叠加不计全套口径）
  - 基础设施（017 migration 测试库幂等实证 + ReportModel + 仓储 12 用例双模式 fallback + CLI 五步定式 102 passed + 三步排查实证）
  - 契约（端口五断言族 11 + 事件键集合冻结全等 6 + 冻结面零 diff + 红线三查本 Story 面零输出）
  - 集成五场景（含③b）单进程+xdist 双模式两轮稳定 + 集成净增 0
  - 验收 13 场景全绿双模式 + 全量回归 **14602 passed × 2 轮完全稳定**
  - 覆盖率：整体 92%（≥80%）/domain+application 91%/新增文件 96-100%
  - **实施攻坚沉淀**（非代码回归的环境/基建发现）：①resolver SINGLETON/SCOPED 缓存跨 loop/跨文件污染——验收与集成双面清缓存防线（`_clear_resolver_caches`/`_fresh_resolver_per_test`——6-1 场景③先例扩展）；②测试 Qdrant 容器强杀致假死+RocksDB 残锁——清卷重建恢复（既有 51 验收全绿实证非代码回归）；③测试库 migration 中间态（全量挂起被 pkill）——upgrade head 恢复；④验收 L0 覆写落地形态修正：注册表 register_port 同名异 spec 抛 ConflictError——服务实例层注入是 6-3 验收先例真身
  - 全程零 noqa/type:ignore/AI 署名（过程中 4 次误写即时清除——红线纪律自查闭环）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-5a-markdown-report-basic.md`
- `src/domain/entities/strategic_report.py` - 报告实体 + ReportType 枚举（Task 1 ✅）
- `src/domain/value_objects/markdown_report.py` - 报告文档 VO 三件（Task 1 ✅）
- `src/domain/services/markdown_report_renderer.py` - Markdown 渲染纯函数（Task 1 ✅）
- `src/domain/exceptions/report_exceptions.py` - 490/491 异常双类（Task 1 ✅）
- `src/domain/ports/report_repository.py` - 报告仓储端口（Task 2 ✅）
- `src/application/ports/report_generation.py` - 报告生成服务端口（Task 2 ✅）
- `src/application/services/report_generation_service.py` - 双源聚合+五段编排服务（Task 2 ✅）
- `src/application/use_cases/generate_markdown_report.py` - 生成用例（Task 3 ✅）
- `src/infrastructure/storage/postgresql/models/report.py` - ReportModel ORM（Task 3 ✅）
- `src/infrastructure/storage/postgresql/repository/report_repository.py` - L2 仓储（Task 3 ✅）
- `deploy/postgresql/alembic/versions/017_strategic_reports.py` - migration 只增（Task 3 ✅）
- `tests/unit/domain/test_strategic_report.py` - 实体/VO 单测 24 用例（Task 1 ✅）
- `tests/unit/domain/services/test_markdown_report_renderer.py` - 渲染器单测 17 用例（Task 1 ✅）
- `tests/unit/domain/exceptions/test_report_exceptions.py` - 异常单测 20 用例（Task 1 ✅——CR1-F28 勘误：原记 21 实测 20）
- `tests/unit/application/test_report_generation_service.py` - 聚合服务单测 30 用例（Task 2 ✅）
- `tests/unit/application/use_cases/test_generate_markdown_report_use_case.py` - 用例单测 3 用例（Task 3 ✅）
- `tests/unit/infrastructure/storage/postgresql/test_report_repository.py` - 仓储单测 12 用例（Task 3 ✅）
- `tests/unit/architecture/test_markdown_report.py` - 架构验证四验证器 9 用例（Task 6 ✅）
- `tests/integration/test_integration_markdown_report.py` - 集成五场景（Task 5 ✅）
- `tests/contracts/test_port_contract_report_generation.py` - 端口契约五断言族 11 用例（Task 2/3 ✅）
- `tests/contracts/test_event_channel_mapping_report.py` - 事件零新增守护 6 用例（Task 4 ✅）
- `tests/acceptance/test_acceptance_markdown_report.feature` - Gherkin 13 场景（Task 0/7 ✅）
- `tests/acceptance/test_acceptance_markdown_report.py` - BDD 步骤实现 13 场景全绑定（Task 0/7 ✅）

**修改的文件/To Be Modified (Dev Story 实施):**
- `src/domain/exceptions/_code_ranges.py` - 开 report 段 + 两类注册（Task 1 ✅）
- `src/domain/exceptions/__init__.py` - 导出 + __all__（Task 1 ✅——EXCEPTION_HTTP_MAP 在 exception_handlers.py 见下）
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 两行 + import（Task 1 ✅）
- `src/entrypoints/agent_cli.py` - report-generate 子命令（Task 3 ✅）
- `src/composition_root.py` - 三注册块 === Story 6-5a === 分节（Task 3 ✅）
- `tests/unit/interfaces/api/test_exception_handlers.py` - 键集合快照同步登记双类（Task 1 ✅）
- `tests/unit/interfaces/cli/test_agent_cli.py` - report-generate 用例扩展 6 用例（Task 3 ✅）
- `docs/architecture/sisys-uni-exception-design.md` - 编码分配表 report 段行 + 483/484 顺带回填（Task 1 ✅）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 台账四处处置注记（Task 0.7 ✅）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 状态流转（Task 7）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.5a |
| **Story Key** | 6-5a-markdown-report-basic |
| **File** | `_bmad-output/implementation-artifacts/stories/6-5a-markdown-report-basic.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 📦 战略规划与审批能力（用户可以生成战略规划并审批） |
| **优先级** | P0-5a |
| **覆盖 FR** | FR-UI-11（P0——Markdown 基础半边；PDF/引文半边归 6-5b）；NFR-PERF-03 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7 / 52 Subtask）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7）
3. [x] Architecture constraints extracted 架构约束已提取（OD-2 偏离声明 + importlinter 四契约）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-4 P0 教训等九项）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则**：R<轮>-<序号>（Round 内递增）；本表 2026-11-03 起由五轮审查循环（D1 调研→D2 审查→D3 修复→D4 提交）维护。

**Round 1**（四视角调研 Agent + 三视角审查 Agent 并行；P0×2 + P1×10 + P2×10 + P3×12，去重后 34 项，关键修复如下）：

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | file_path「L0 绝对路径」处方物理不可达：`L0StoragePort.write` 返回 bool 不返回路径；三条出路（自拼路径违 importlinter/端口加方法系未声明契约变更/存相对路径违表述）全部与 Story 现文冲突 | P0 | OD-4/实体表/锚点表：file_path 改 **L0 逻辑路径 `reports/{memory_id}.md` 单源派生**（六边形正形+可移植+零端口变更+消费方经端口 read 无需 base；memory_id 经 stem 反解） |
| R1-2 | AC-5 发布失败检出机制缺失：`RabbitMQEventBus.publish` 吞异常只返回失败 `PublishResult`，纯 `except` 恒不触发且 `AsyncMock(side_effect)` 假绿 | P0 | AC-5/Task 2.4：双防线钦定（`if not result.is_success` 先判 + `except` 兜底）+ 单测两失败形态各钉一用例 |
| R1-3 | 491 上抛语义与 284 先例不构成类比（284 raise 触发 HTTP 同事务回滚 load-bearing；报告面 save/publish 无共同事务上抛回滚不了 L0/L2，且 exit 1 误导重跑叠加多份）+「同事务语境」表述失实 | P1 | AC-5/OD-6/SDD 事件节：改 **checkpoint ⑤ 宽容语义同构**（warning+返回成功；真相源=L0/L2 落盘，事件是通知面）；491 值域收窄二元 {l0,l2}；删「同事务语境」 |
| R1-4 | 「6-4 archived=False 台账态」机理误述：该值是 compose 返回的内存态不进快照，trace 读侧无此形态；284 后段失败形态下 PG 行通常在位 | P1 | AC-4 Given/OD-5：改述「归档行不存在的物理形态 = compose 445 缺席 / Step1 L2 写失败；读侧以 PG 行为准」 |
| R1-5 | 渲染容错三态未钉死：「解析失败→[数据缺失]」会把降级信封态误分类吞掉 degrade_reason | P1 | AC-4/标注形态冻结：三态判定以 payload 形态为准（解析失败→[数据缺失]/信封键集⊆{degraded,degrade_reason}→[降级]带 reason/其余正常+锚叠加） |
| R1-6 | `[降级]{原因}` 在 3/5 降级形态不可得（六子部分降级 payload 无 reason 键/synthesis asdict 两键无 reason/行锚仅 bool） | P1 | 原因解析次序冻结：`payload.get("degrade_reason")` → 固定兜底「降级（原因未随归档行结构化持久化）」；禁解析 reflection 文本 |
| R1-7 | degraded_section_count 计数单位未定义——H2 章数口径（2）下缺 ≥3 步破坏 degraded≤section 不变量炸 242，违背「报告照常生成」 | P1 | 实体表/AC-4：计数单位钦定 **H3 小节**（section_count=11；六子缺→1/synthesis 缺→1/gap 缺→4；上限 8≤11 恒成立）+ 缺三步场景锁不变量 |
| R1-8 | L280「490/491 纳入 Gherkin（AC-4 场景 7/8）」与 L329「491 单测层承载验收不含」直接矛盾 +「场景 7/8」编号推演双错（13 场景排布下 AC-4=#6/7/8=部分缺失/全缺/快照缺失） | P1 | L280/L323：改「490 纳入 Gherkin（AC-4 全缺场景）；491 归单测层」 |
| R1-9 | Subtask 4.1 把 6-4「缺席断言 token 零命中」范式套在已存在的 `report_generated` token 上（Epic 1 既有登记在 routing key 内）——按字面实现当场误伤 | P1 | Subtask 4.1：改**登记集合冻结快照相等断言**（既有登记存在性 + 键集合全等基线）；显式声明零命中范式不适用 |
| R1-10 | 性能场景「≥20 轮独立 plan_id」构造成本与 6-3 先例（纯内存 25 次调用）差三个量级（160 次 LLM+归档三面 I/O+三量级清理）；OD-10 幂等锚本就钦定重复生成合法 | P1 | AC-7/OD-8/Task 5.4：改**单一数据源 plan_id×20 次生成**（归档链一次；锚=新 report_id+L2 行数+20+集合无重复） |
| R1-11 | AC-2「### 2.7 综合洞察」≠钦定逐字源 SYNTHESIS_DISPLAY_NAME=「市场洞察综合」——AC 正文自身违反「逐字源」纪律 | P1 | L59 改「### 2.7 市场洞察综合」 |
| R1-12 | AC-2「元信息引用块」与冻结表/AC-3/VO 三处「table 两列表」互斥矛盾 | P1 | L59 改「元信息表（两列表）」 |
| R1-13 | 追溯矩阵 Subtask 归属错位（1.1-1.3 渲染器实为 1.4-1.6 等 3 处）+ 缺 AC-6→Task 6 行 + 验收侧行整体缺席 | P2 | 矩阵重排（**R2 勘误：原记「18 行」实为 17 数据行**——表头计入才 18）：归属逐项校正 + 补 AC-6 架构行 + 补 Task 0/7 验收行 + AC-7 5.4/5.5 拆行 |
| R1-14 | 完成总结「39 Subtask」与逐行点数「52」矛盾（grep 实证 52） | P2 | 改 52 |
| R1-15 | 同 plan_id 秒内重复生成 memory_id 相同 → L0 覆盖，「新文件名」断言同秒窗口假 | P2 | AC-1/OD-10：秒级窗口注记（锚 report_id/L2 行；件数断言需跨秒或不断言） |
| R1-16 | 「构造缺一步归档」构造手段未钦定——跑后删行零先例且定向 DELETE 例外限清理语境 | P2 | AC-4/Task 5.2：钦定**逐 stage 归档七次跳过目标步**（6-3 `_archive_eight_steps` 变体；禁删行构造）+ 场景④改「从未归档的独立 plan_id」 |
| R1-17 | L0 测试写路径污染：真实 resolve 通道写运行机器 `~/.sisys/memory/reports/`；组合根 SCOPED lambda 缓存使 resolve 后 setenv 不生效；xdist 净增 0 计数互扰 | P2 | Task 5.1：tmp_path 自建 FileMemoryAdapter 覆写注入（_restorers 还原——6-3 端口覆写先例） |
| R1-18 | §3.3.2 既有漂移：6-3 落码 483/484 未回填（仍写「483~489 预留」），Task 1 同表编辑相撞 | P2 | 异常契约节/File List：钦定**顺带回填**（同表同次编辑两行修正——偿还既有债非扩面） |
| R1-19 | 八 stage 期望集派生源未定义——硬编码八清单将随配置增步静默漂移【R5 勘误：本行括号注「STAGE_VALUE_DOMAIN 仅 docstring 无运行时定义」失实——`blm_phases.py:68-71` frozenset 定义在位，见 L247 R5 改述】 | P2 | 端口契约节：派生公式钦定（`performance_gap` + 配置键序 + `market_insight_synthesis`） |
| R1-20 | ReportGenerated 三键有缺省空串，漏传不炸产空串事件 | P2 | AC-5：构造点必显式传三键 + 单测三键非空断言 |
| R1-21 | AC-1「内容与返回实体一致」无可断言载体（实体无 content 字段）；memory_id 时间戳测试不可预知 | P2 | AC-1 验证标准：改「memory_id 经 file_path stem 反解 + 读回内容含冻结章节标题族（display_name 源独立构造期望）」 |
| R1-22 | outbox 断言先例引用失实（6-3 集成键实为 plan_id，仓内无 archive_id 键 outbox 断言） | P2 | AC-1/锚点表：改「plan_id 键先例同构」+ 两级路径机理解注 |
| R1-23 | 标题层级口径三处不一致（1-3 vs 1-4/H4 二选一开放） | P2 | 章节结构冻结：预裁定**加粗行标签不开 H4**（与 AC-3 字面锁定）；Task 0.1 同步 |
| R1-24 | synthesis 降级 callout `{degrade_reason}` 无数据源（asdict 两键无 reason） | P2 | 并入 R1-6 原因解析次序（synthesis 走兜底文案） |
| R1-25 | 284 layer 值域实为 (l2,l3,l4,l5) 不含 l0/event——「同构」措辞诱导照抄值域 | P2 | 异常契约：改「语境借鉴值域自有」+ `_VALID_LAYERS=("l0","l2")` 自有元组钦定 |
| R1-26 | 行号锚点漂移簇（display_name :194/:202→:191/:199；checkpoint_service :2287-2302→:2293-2308；「6-4 三注册块 :2339-2363」实为 2 块；CLI 两子命令区间对调；验收样板六步链区间；ReportGenerated :57→:56；6-4 docstring L17-18→L16-17【**R4 勘误：此项校正反了——原锚 L17-18 才与仓库吻合，已在锚点表回调**】）+ 构造签名偏离家族形态 + 490 消息文案 + 章节编号拼接/目录锚点算法/附录 A 两处未定稿 + tenant_id 死参数 + File List 缺 sprint-status + n=20 P95 次大值注记 + 服务无状态约束 + mock 工厂提示 | P3 | 锚点表/异常契约/冻结表/端口定义/AC-7/Task 2.1 逐项修正（构造签名对齐家族 `(layer, message=None, cause=None)`；490 message 可观测事实口径；拼接规范 `{编号} {display_name}`；GitHub slug 锚点；附录 A display_name 映射+summary_excerpt 显式省略；删 tenant_id；补 File List） |

Round 1 未修留项：无 P0/P1 残留（34 项全部处置：26 修复簇 + 8 项并入修复簇）。

**Round 2**（回归核查 Agent + 组合交互面审查 Agent 并行——R1 八裁定单独 8/8 成立实证 + 两两组合推演；P1×1 + P2×6 + P3×6）：

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-1 | 计数语义空洞：degraded_section_count 与附录 B 只定义了「归档行缺」形态——三态②信封态（内容缺失）与③锚叠加（内容在位仅标注）是否计入/入册零裁定，信封态场景验收期望值不可写 | P1 | 实体表/标注形态冻结/附录 B 行 R2 口径钉死：**degraded_section_count 计内容缺失类**（缺行+信封态；锚叠加不计——内容完整归附录 B [降级] 行可观测）；附录 B 类型列值域 {[数据缺失],[降级]} 两类全收；登记清单单次调用局部累积非实例态 |
| R2-2 | 实体表「上限 8 ≤ 11」算术失实（任何一致口径推不出 8；错误上限诱导反推错误口径） | P2 | 重算：极端形态 gap 缺行 4 + 六子全信封 6 + synthesis 缺行 1 = 11（缺行 2 条 total=6≠0）；补「单小节至多一种标注形态，不变量天然成立」 |
| R2-3 | `PublishResult(results=...)` 测试处方缺必填首参 `event_id`（publish_result.py:30）——照抄必 TypeError | P2 | AC-5 验证标准/Task 2.4 两处补 `event_id=str(uuid4())` |
| R2-4 | AC-4 验证标准 5 条与 13 场景/集成③b/单测的层级映射缺口 + 追溯矩阵缺 AC-4→Task 5 行 | P2 | 验证标准逐条标层【验收/集成/单测】+ 矩阵补 AC-4 Task 5 行（5.2 场景③③b④） |
| R2-5 | R1-17 L0 写路径隔离未传播到验收层（三理由对验收层同样成立） | P2 | Task 0.5 补同款 tmp_path FileMemoryAdapter 覆写注入 + _restorers 还原钦定 |
| R2-6 | `ReportSection.level` 值域 1-4 与「严格 1-3 不开 H4」冻结矛盾（level=4 渲染行为未定义） | P2 | VO 表与 __post_init__ 校验双处收窄 1-3（三方对齐） |
| R2-7 | AC-7「N 次文件可读回」在单 plan_id×20 同秒覆写形态下事后断言 20 文件会假失败 | P3 | 钦定「每轮生成后即时经该轮 file_path stem 反解读回；件数断言按 AC-1 注记豁免」 |
| R2-8 | 集成「五场景」声明与清单编号（含 ③b 共 6）不一致——R1 两修复各自增补的接缝 | P3 | Task 5 标题声明「③b 为③的第二断言块非独立场景」 |
| R2-9 | 「checkpoint ⑤ 同构」措辞弱化双防线裁定（⑤先例单 except 对失败 PublishResult 静默——是缺陷非范本） | P3 | AC-5/OD-6 措辞改「宽容结果语义同构 + 防线形态为增强（is_success 判定修正先例缺陷）」 |
| R2-10 | CLI 打印逻辑路径无定位信息（人类用户拿相对路径找不到物理文件） | P3 | Task 3 CLI 测试处方补 memory_id 打印（经端口 read / base 目录提示定位） |
| R2-11 | 「outbox 落行 ⟺ is_success」等价机理未点破（publish 无 MQ 直发）——误追加 MQ 消费侧断言在无 MQ 集成环境会挂 | P3 | AC-5 补机理注记：断言以 outbox 行为唯一面，禁止追加 MQ 断言（投递归 poller 基建 L170） |
| R2-12 | R1 修订文本的次生修正簇：`_code_ranges.py` 回填锚点 :178-181→:184-188（481/482 vs 483/484 错位）；「同表」→「同 §3.3.2 两张表」；L0 失败检出口径未钉死（真实适配器从不返回 False 只抛 OSError）；「实现层 RabbitMQEventBus」漏「经 DualChannelEventBus 委托」；R1-13 台账「18 行」勘误 17 数据行 | P3 | 异常契约/Task 2.4/AC-5/R1-13 台账逐处修正 |

Round 2 未修留项：无 P0/P1 残留（13 项全部处置：12 修复 + R1-13 勘误内联）。

**Round 3**（单深度推演 Agent——13 Gherkin 场景逐个三轴推演【前置可达/期望唯一可写/环境可观测】+ 6 条长时间线 + 不变量数学核验；P1×1 + P2×2 + P3×4 + 证伪留痕 11 条）：

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-1 | 缺行小节 H3 骨架渲染形态未冻结——R2-2「极端=11≤11 天然成立」的算术证明隐含「缺行小节仍渲染骨架（section_count 恒 11）」但正文未字面化；「省略小节」分叉实现下极端形态 section_count=6 < degraded=11 炸 242 击穿「照常生成」；且验收部分缺失场景跳步类别未钦定（gap/六子/synthesis 三类期望值不同——期望只能自证反推） | P1 | 标注形态冻结补「缺行小节仍渲染 H3 骨架 + section_count 恒 11 与数据缺否无关（load-bearing 前提显式化）」；AC-4 验收/集成③目标步钦定六子步（期望 ==1）；gap/synthesis 缺行变体归单测层参数化 |
| R3-2 | AC-6×1 验收场景断言面全文无处方（13 场景钉死它但 Given/When/Then 不可推定——验证标准是 CI 动作与「留待设计」委托，不构成场景内断言面；最劣路径=现场发明恒真断言） | P2 | AC-6 验证标准钉死断言面处方（对齐 6-4 S8/S9 字面基线全等形态）：chain 读侧五键结构全等 + ReportGenerated payload 键族全等；显式不重复 4.1/Task 6 面 |
| R3-3 | AC-4「附录 A 省略 + 实体标注」载体不存在——实体七字段无标注位、get_latest_by_plan 读回不携带 metadata（悬空契约：诱导实体扩字段或断言不可达） | P2 | 改「L2 `metadata.timeline_available=false` 可观测（直查 PG JSONB）」+ 快照缺失场景断言面同步钦定 |
| R3-4 | 追溯矩阵 AC-2 集成锚场景号错位（章节断言在 5.2 场景①非②）+ AC-3 缺集成行 | P3 | 矩阵 AC-2 行改场景① + 补 AC-3 Task 5 行 |
| R3-5 | AC-7 并发 3 的 gather 步骤形态未锚先例——BDD 步骤顶层裸 gather 经 run_until_complete 跨 loop 绑定炸 RuntimeError（与验收 Redis 跨循环问题同族陷阱） | P3 | Task 5.4 补 gather 形态锚（async 辅助函数体内 await + _run_async——6-4 :2066-2068 先例；禁顶层裸 gather） |
| R3-6 | 附录 A「步骤」列映射源清单缺 synthesis 条目（timeline 第三种 step 值无源——期望不唯一：裸值直显 vs 显示名两实现都对） | P3 | 补第三源 SYNTHESIS_DISPLAY_NAME + 映射 miss 直显裸值钦定 |
| R3-7 | 目录收录粒度未冻结（仅 H2 vs H2+H3 两种实现都满足现文本——目录条目断言期望不唯一） | P3 | 冻结收录面 = H2 章级 + 附录（H3 不进目录；条目数随附录 A 有无非恒定注记） |

Round 3 证伪留痕（推演过并排除的疑点——防后续轮重推）：①AC-1 sleep≥1.05s 跨秒数学恒成立（T1+1.05>S+1）②同秒覆写 teardown delete 契约返 False 不抛（l0_storage.py:53-62——R4 校正区间，原记 :46-53 偏前）③SINGLETON 缓存冻结 L0 覆写——6-3 先例 clear_singleton() 还原链关闭（checkpoint_snapshot.py:1275-1281）④并发 3 会话隔离——session_factory 每操作独立会话 + 6-4 gather 10 并发先例实证⑤发布失败轮不破坏「N 次事件落行」（采样纯正常路径，失败注入钦定单测层）⑥缺步 plan_id 重复生成计数恒稳定⑦信封+快照缺失组合期望唯一（R2 口径三分支互斥）⑧P95 n=20 数学正确（次大值=已注记设计选择）⑨13/52/23/③b 四组计数全自洽⑩③态单字段缺席真实链不可达（instructor 全 schema 或信封二值 + Fake 八键族恒全字段）⑪覆盖率分层无数学矛盾。

Round 3 未修留项：无 P0/P1 残留（7 项全部修复）。

**Round 4**（纯验证轮——锚点存续 36 处实地核验 + 三轮修复传播 19 项旧措辞 grep + 结构四线核验；零 P0/P1/P2，5 项 P3 随 R5 收敛提交清偿）：

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R4-1 | R1-26 校正值「checkpoint_service :2293-2308」未传播到 Task 3 TDD 循环 B 绿阶段（仍 :2287-2302） | P3 | L610 同步 :2293-2308 |
| R4-2 | 同族：Task 3 TDD 循环 C 绿阶段仍「checkpoint-create :320-371」（正确 :337-392） | P3 | L622 同步 :337-392 |
| R4-3 | **R1-26 对 6-4 docstring 锚「L17-18→L16-17」的校正反向**（实证语句跨 L17-18，原锚才对）——锚点表 L822 已回调 + R1-26 台账勘误注记 | P3 | L822 回调 L17-18 + R1-26 内联勘误 |
| R4-4 | R3 证伪留痕②「l0_storage.py:46-53」区间错位（delete 契约实在 :53-62） | P3 | 留痕②校正 :53-62 |
| R4-5 | v1.2.0 版本说明「P2×5（分项和 12）」与 Round 2 节头「P2×6（和 13）」口径不齐（第 13 项勘误未纳入分项） | P3 | 版本说明改「12 命名修复 + 1 项勘误内联」口径与节头对齐 |

Round 4 验证结论：36 锚点 34 匹配（2 偏移即 R4-3/R4-4）；19 项旧措辞 13 项干净零残留（其余 6 项中 3 项为 R4-1/2/3 传播缝隙已修、3 项为台账/勘误历史语境预期命中）；标题序列 58 个连续完整/Subtask 52 无跳号/13 场景三处一致/文件清单与结构树逐名一致；版本链 v1.0.0→v1.3.0 与提交链 440d9dae→b41858ff→722fb1a7 对应；sprint-status ready-for-dev 同步。

**Round 5 独立终审（收敛——2026-11-03）**：五节终审（周期闭合/十项双向取证/一致性快扫/红线终扫/收敛判定）全数通过。周期闭合——提交链 440d9dae→b41858ff→722fb1a7 三审查提交零游离，工作区 R4 五项 P3 修复逐块核验在位；十项关键修复（file_path 逻辑路径/is_success 双防线/宽容语义/三态判定/计数口径 11≤11/491 家族形态/采样口径/逐 stage 构造/事件守护全等/派生公式键序）经文档-代码双侧独立取证全部成立，不采信台账自述；20+ 组正文内嵌锚点与 File List 快扫吻合；红线终扫零违规（grep 处方/三层 mock 纪律/冻结面与修改清单零矛盾）。R5 特权发现 R5-1（P3）：L247 `STAGE_VALUE_DOMAIN`「仅 docstring 无运行时定义 + 6-4 漂移」双重失实（`blm_phases.py:69-71` frozenset 定义在位、6-4 Story 正确引用无漂移）——已随本轮清偿改述（派生公式仍取 CONFIG 键序：有序 + display_name 同源）；OD-6 ⑤先例锚微瑕（引述词与区间头错位 5 行）一并校正。

**五轮总账**：R1 34（P0×2+P1×10+P2×10+P3×12）+ R2 13（P1×1+P2×6+P3×6）+ R3 7（P1×1+P2×2+P3×4）+ R4 5（P3×5 纯验证轮）+ R5 终审（R5-1 + OD-6 锚微瑕）= **60 项处置**；投入递减 34→13→7→5→终审；**P0/P1/P2/P3 残留均为零**。Story 文档收敛于 v1.4.0，`ready-for-dev` 状态维持，可进入 `dev-story` 实施。

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-11-04（Round 1）
**审查模式:** full（五视角并行调研 Agent【领域层正确性/应用层正确性/基础设施组装/测试质量断言/一致性契约】+ 主会话亲验交叉验证——P1 级发现全部经主会话独立实证）

**Round 1**（2026-11-04；五 Agent 并行 + 主会话 12 文件亲验矩阵 + P1×3 逐项独立实证；去重后 29 项：**P1×3 + P2×10 + P3×16**；本轮处置 19 项【P1×3+P2×10+联动 P3×6】，10 项 P3 留后续轮次）：

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| CR1-F1 | 附录 A `_timeline_step_display` 判别 `step == "synthesis"` 与写侧 timeline 实际记录值 `"market_insight_synthesis"`（`blm_planning_service.py:504` record_step 实证 + `STAGE_VALUE_DOMAIN` frozenset 成员实证）错配——三分支全不命中走 miss 裸值，**真实 8 步 run 的每份报告附录 A 末行「步骤」列显示裸串**；单测 `:561` 喂臆造值 `"synthesis"` 把错误假设钉绿；story 附录 A 表定稿「synthesis」系对端口 docstring 简称的误读 | P1 | 判别改 `step == "market_insight_synthesis"`；单测臆造值改真实值；story 表定稿勘误（本文件已完成） | ✅ R1 |
| CR1-F2 | `get_latest_by_plan` 排序方向全仓零杀伤：单测 `test_latest_ordering_by_created_at_desc` 是 `inspect.getsource` + `"created_at" in source or "order_by" in source` 恒真断言（`created_at` 在 docstring 命中；真正 `.order_by` 在 `_do_get_latest`）；集成测试全文件零调用 `get_latest_by_plan`；验收 S2 只断言行数与 report_id 互异不验证取最新——`.asc()` 突变全套件 14602 用例仍绿 | P1 | 单测改断言 `_do_get_latest` 编译产物 `_order_by_clauses` 含 created_at DESC；验收 S2 补 `get_latest_by_plan` 值级断言（两行在位取第二份 report_id）；集成场景① 补 get_latest 读回比对 | ✅ R1 |
| CR1-F3 | AC-2「六 Schema 全字段渲染无遗漏」大面积断言缺口：六子公共前缀 **summary/findings 正向渲染零断言**（`_FAKE_STEP_SUMMARY_PREFIX` 常量定义后全仓零消费——被遗弃的断言锚）；scenario_plans/demand_priority_matrix/value_proposition_map/internal_capabilities/vrio_assessment/resource_constraints/priority_ranking/capability_match_matrix/closure_strategies/competitor_radar 数据行**全部零断言**（grep 实证 assert 消费计数 0）——删掉 `_step_field_blocks` 十余个冻结字段渲染全套件仍绿（Epic 4 恒真断言族当代复发） | P1 | 验收 S4 补全字段值级断言（summary 前缀×6 循环 + 零断言字段逐项抽样补齐）；单测补 `_step_field_blocks` 输出块型序列断言 | ✅ R1 |
| CR1-F4 | GFM 表格单元格含 `\|`/换行破坏列对齐：VO 列数守卫只查 tuple 元素个数，单元格文本内管道符原样进入管道语法——payload 值（LLM 自由文本）含「政策 \| 稳定」→ 3 数据列 vs 2 表头；含 `\n` 表格拆断。暴露面覆盖全部四张表（PESTEL/五力/时间线/附录 B 原因列） | P2 | `_render_table` 单元格 GFM 结构性转义（`\|` → `\\|`、换行归一空格）+ 渲染语法冻结条款补限定（结构性字符转义≠unicode 转义禁令范围——story 已更新）+ 单测转义用例 | ✅ R1 |
| CR1-F5 | callout 文本含换行丢失 `> ` 前缀：`f"> {block.text}"` 仅首行有前缀，`degrade_reason="原因A\n\| 伪造表格行"` 第二行裸奔被解析为表格行——标注形态冻结破坏 + 块结构注入面 | P2 | callout 渲染逐行补 `> ` 前缀（合法多行 blockquote）+ 单测多行用例 | ✅ R1 |
| CR1-F6 | StrategicReport 冻结表约束未落地：`plan_id` 非空（默认 `""` 无守卫——脏实体落 L2 毒化查询面）/ `file_path` 纯空白（`" "` 通过）/ 三计数负值（`section_count=-5` 通过——字段表 ≥0 约束） | P2 | `__post_init__` 五查补全（plan_id 非空 + file_path strip 非空 + 三计数 ≥0）+ 242 断言用例（story 校验清单已更新） | ✅ R1 |
| CR1-F7 | `_SECTION_COUNT=11` 硬编码与「配置增步自动跟随」原则自相矛盾：`degraded_count` 按 CONFIG 循环递增而 section_count 钉死字面量——CONFIG 增第七步且缺行时 degraded=12 > 11 触发 242 崩溃（恰是「缺行骨架渲染」要防的形态）；synthesis 编号 `2.7` 硬编码会与增步后第七子小节撞号 | P2 | `_SECTION_COUNT` 改派生 `4 + len(MARKET_INSIGHT_STEP_CONFIG) + 1`；synthesis 编号改 `2.{len(CONFIG)+1}` 派生 | ✅ R1 |
| CR1-F8 | ReportModel 漏聚合进 `models/__init__.py`（唯一例外——既有 17 模型全聚合）：集成/验收 conftest 的 `Base.metadata.create_all` 兜底建表缺 `strategic_reports`（实证 `'strategic_reports' in Base.metadata.tables` → False）——alembic 失败/超时时兜底 schema 缺表误报「PostgreSQL 不可达」skip 或 save 抛 UndefinedTable | P2 | `models/__init__.py` 补 import + `__all__` 登记 | ✅ R1 |
| CR1-F9 | CLI 成功打印 `报告类型: {report_type}` 输出枚举 repr「ReportType.MARKDOWN」而非「markdown」（f-string 渲染枚举成员）；单测 stub 设裸 str `"markdown"` 掩蔽真实属性形态（6-1/6-3/6-4「属性形态断裂族」在替身层复发） | P2 | 打印侧取 `.value`（getattr 二级取值保零 import）；stub 改真实 ReportType.MARKDOWN + 补「报告类型: markdown」值级断言 | ✅ R1 |
| CR1-F10 | CLI memory_id 打印断言被 file_path 子串遮蔽：断言 `"plan-1_20261103120000" in out`，逻辑路径行 `reports/plan-1_20261103120000.md` 自含该子串——删掉 memory_id 打印行断言仍绿（R2-10 钦定打印面零守护） | P2 | 改按行断言 `f"  memory_id: plan-1_20261103120000" in out.splitlines()` | ✅ R1 |
| CR1-F11 | `test_entity_to_model_fields` 恒绿断言：只断言 fixture 实体的枚举值（`report.report_type.value == "markdown"`——test_strategic_report 已测），与 `_to_model`/ORM 映射零相关；`_to_model` 映射改错（如 metadata 恒空/列写串位）该单测绿 | P2 | 重写为捕获 `mock_session.add` 的模型实例逐字段断言（metadata_/report_type/计数双列/created_at） | ✅ R1 |
| CR1-F12 | 三态判定①「payload 非 dict 形态」分支零覆盖：`final_answer='["a","b"]'`（合法 JSON 数组）/`None`（TypeError 路径）→ missing 分支无用例——删掉 isinstance 守卫后含数组形态归档行的报告生成 AttributeError 500 而非降级标注，现有测试全绿无感知 | P2 | 单测参数化补 list/None 两用例（期望 degraded 计入 + [数据缺失] callout） | ✅ R1 |
| CR1-F13 | `_load_snapshot` 容错分支（读异常→None→附录 A 省略）零单测：现有用例只覆盖返回 None 形态——删掉 try/except 后 Redis 抖动直接炸报告生成（辅源阻断主链违反 AC-4「不阻断」） | P2 | 补 `snapshot_repo.load.side_effect = RuntimeError` → 报告成功 + 无附录 A + timeline_available=false 用例 | ✅ R1 |
| CR1-F14 | 空 dict payload `{}` 归信封态：`{}.keys() <= _ENVELOPE_KEYS` 恒真——常量注释自称「且非空即为信封」与行为矛盾；`final_answer='{}'` 判 [降级] 而语义应为 [数据缺失]（附录 B 类型值域错位） | P3 | 判定改 `payload and payload.keys() <= _ENVELOPE_KEYS`（空归①缺失态，与注释对齐）+ 钉一用例 | ✅ R1 |
| CR1-F16 | generation_ms 口径双 docstring 矛盾：实体 docstring 称「聚合起点→事件发布返回——AC-7 口径」实际截断于 L2 落库前（frozen 实体先构造的结构必然）；service docstring 自认近似——同字段两套口径 | P3 | 实体 docstring 改述「聚合起点→L2 落库前（近似）」与服务对齐；story 实体表勘误注记（本文件已完成） | ✅ R1 |
| CR1-F24 | `_save_passthrough` 死代码 helper（定义未用——疑为被丢弃的「save 返回值消费面」断言残骸，误导覆盖认知） | P3 | 删除 | ✅ R1 |
| CR1-F27 | `_REPORT_EVENT_PAYLOAD_KEY_BASELINE` 冻结基线常量声明后未消费（then 步骤断言写死字面量）——baseline 形成假单源，后续 6-5b/6-11 加字段时常量与断言静默漂移 | P3 | 断言处改消费常量派生期望 | ✅ R1 |
| CR1-F28 | 异常单测用例数台账 21 vs pytest 实际收集 20（两处口径失实——违反「禁概数」可复核纪律） | P3 | 台账 5 处改 20 + 勘误注记（本文件已完成） | ✅ R1 |
| CR1-F29 | ruff I001 import 块排序（`test_report_generation_service.py:16`） | P3 | 实测确认：dev-story 攻坚期 typing import 变更已顺带修复（本轮 ruff 全绿零操作；评审期首次运行报 F821 系缓存陈旧，无缓存复跑仅 I001 且已被后续 import 调整消化） | ✅ R1 |
| CR1-F15 | MarkdownReportDocument 零构造期校验：meta_rows 混入裸 str 行时 `' | '.join(str)` 退化为字符级拼接（`("k","v"),"abc"` → 三列静默错位——ReportBlock 已修的「str 行 len 巧合」同族隐患守卫不对称）；title/plan_id 空串放行 | P3 | 补 `__post_init__`（meta_rows 每行 tuple len==2 + title/plan_id 非空） | ⏳ R2 |
| CR1-F17 | `_to_entity` 裸 `ReportType(model.report_type)`：脏行（'docx'）抛原生 ValueError 逃逸异常体系——archive 家族 try/except+warning+默认值守卫形态未沿用；017 未加 CHECK 值域 | P3 | 沿用 archive 守卫形态（except ValueError → warning + 回退）或 018 补 CHECK | ⏳ R2 |
| CR1-F18 | `_to_model` 裸 `uuid.UUID(report.plan_id)` 可抛原生 ValueError；F6 修复后入口收窄但脏实体直调端口（6-8 REST 面绕过用例）仍可触发 | P3 | 与 F17 同点处置（守卫前置） | ⏳ R2 |
| CR1-F19 | `order_by(created_at.desc())` 无并列 tie-breaker：同一 plan 两行 created_at 完全相同（数据回填/时钟粒度）时「最新」不确定 | P3 | `.order_by(created_at.desc(), report_id.desc())` | ⏳ R2 |
| CR1-F20 | 单测 `_View` 手搓替身 + `ENVELOP` 死哨兵：服务消费面用结构同构替身而非真实 `ChainOfThoughtTraceView`（DTO 契约漂移单测恒绿）；ENVELOP 定义后零使用 | P3 | `_make_trace_view` 直接构造真实 DTO（四参 frozen dataclass 零成本）；删 ENVELOP | ⏳ R2 |
| CR1-F21 | CLI 成功路径未断言 plan_id 向用例透传值（stub.calls 记录未消费——执行器传错/硬编码测试仍绿）；契约测试 use_case 缺 spec/resolve 断言（宣称五断言族实覆盖两项）+ report_repository 缺 tags | P3 | 成功用例补 `stub.calls` 值级断言（✅ R1 已修——独立构造期望形态）；契约测试补齐留 R2 | 🔶 R1 部分 |
| CR1-F22 | 「ATX 严格递进不跳级」断言弱于步骤名：只断首行==1 且 ∈{1,2,3}，H1→H3 跳级不红（间接由 S3 全序列等价承载） | P3 | 补相邻层级差 ≤ +1 循环断言 | ⏳ R2 |
| CR1-F23 | 验收层 teardown 七步链每步 `except Exception: pass` 全静默 + 13 场景零净增断言（净增 0 仅集成承载）——清理失败不可见 | P3 | finalizer 末尾 COUNT==0 断言或清理失败 logger.error | ⏳ R3 |
| CR1-F25 | S11 分档表写「逐 stage 八步归档」实际走 `_assemble_full_flow` 完整 run + 计时窗口含真实 commit/read_text 宽于 OD-8 口径（偏严不假绿，文档漂移） | P3 | 修分档表措辞与计时包裹面 | ⏳ R3 |
| CR1-F26 | 架构测试 `test_service_consumes_ports_only` 与 B1 逐字重复（docstring 宣称五依赖 Port 类型检查实未检查） | P3 | 合并或改查构造签名注解 | ⏳ R3 |
| CR1-F30 | 渲染器无 ATX 递进校验（任意 level 序列照渲染——当前组装层顺序正确属结构信任边界） | P3 | 可选：渲染器/VO 增「sections 内禁 level=1」约定（H1 单源=document.title） | ⏳ R4 |
| CR1-F31 | paragraph/bullet 文本内嵌换行同族注入残留面（评审员 1 F4 评审发现）：`financial_gap` 含 `\n### 伪造标题` 可注入块结构——本轮冻结条款只限定表格/callout 两块型，paragraph/bullet 出口 `_str_field`/`_str_items` 未归一 | P3 | R2 评估：威胁模型同源（LLM 自由文本）——`_str_field`/`_str_items` 出口换行归一或 VO 构造期守卫 | ⏳ R2 |

**Round 1 主会话亲验通过项**（五 Agent 与主会话双重复核一致，不计 findings）：五段编排顺序与 L0 失败短路/三态判定主路径/原因解析次序/事件双防线+aggregate 自动派生（`ReportGenerated.__post_init__`）/双模式 fallback 与 session_factory 第一天到位/组合根三注册八字段/migration 017 链形态与九列镜像/异常四处登记+HTTP 映射+键集合快照/渲染器 slug+GFM+目录不自收录/BDD 三件套+13 场景对位/冻结面零 diff（AC-6 全清单）/红线三查零命中。

**Round 1 实施验证记录**（2026-11-04）：
- **评审放行**：双评审员（正确性风险/完整性联动面）均「合格」并给出明确放行条件——F14 表达式反写阻断项按评审形态修正（isinstance 后前置 `if not payload: return "missing", None`）；F7 定义序陷阱（`_GAP_SUBSECTIONS` 上移）+ 双站点枚举 + F2 编译 SQL 断言形态 + F12 SimpleNamespace 直击 TypeError + F27 顶层三键独立命名 + F1 冻结面边界裁定（blm_planning.py:39/:811「stage 形态」措辞语义正确不改——误读责任在消费侧）全部吸收后实施
- **变异实证**：F2 新断言 `.asc()` 注入 → 红 → 还原 → 绿（旧 getsource 断言同变异下不红——杀伤力差异实证）
- **测试结果**：本 Story 单测+契约 246 passed；集成 5 passed；验收 13 passed（含全部新增断言：F1 附录 A synthesis 行值级 + F2 get_latest 行为级 + F3 全字段 + F27 基线派生）；ruff 零错误 + mypy 746 零错误 + lint-imports 5 kept
- **全量回归**：四目录 14613 passed（第三轮）；首轮 20 failed / 次轮 19 failed 根因排查 = **Qdrant 容器 FD 耗尽**（docker 默认 ulimit 1024 + Qdrant segment FD 滞留累积——进程实测 974/1024；表象 RocksDB「IO error: While open directory」）——环境基础设施问题与 6-5a 零关联，处置 = 两容器 `--ulimit nofile=65535` 重建后 Qdrant 验收 14 passed×2 稳定；残余 1 个 hybrid_search flaky（Epic 2/3 面，单独复跑 PASSED）
- **回归面自查**：修复后 12 文件 diff 全部可追溯到 CR1 台账；F4 转义对既有断言零破坏（fixture 值无管道符——评审员 grep 实证）；F6 五查对既有 9 处实体构造零误伤；F7 派生值恒等（11/2.7 字符串全等）

#### 已推迟 Defer

- [ ] CR1-F15/F17/F18/F19/F20/F21/F22 → Round 2 处置（7 项 P3——防御面/断言收紧族）
- [ ] CR1-F23/F25/F26 → Round 3 处置（3 项 P3——验收文档/结构族）
- [ ] CR1-F30 → Round 4 处置（1 项 P3——渲染结构信任边界）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.6.0
**创建日期/Created:** 2026-11-03
**最后更新/Last Updated:** 2026-11-04
**更新说明/Description:**
- v1.0.0: 创建故事文件（五 Agent 并行调研 + 主会话九项亲验；OD-1~OD-10 十项架构裁定落档——宿主形态偏离声明/双源聚合/持久化三件/异常开段 490/图类表格承载为五大关键裁定）
- v1.1.0: Round 1 文档审查修订（四视角调研 + 三视角审查并行，34 项处置——P0×2：file_path 改 L0 逻辑路径裁定（write 不返回路径三路全断）/发布失败 is_success 双防线（实现层吞异常）；P1×10：491 宽容语义改判（无共同事务上抛无效）/archived=False 机理修正/渲染三态判定冻结/原因解析次序/计数单位 H3 口径/491-Gherkin 矛盾/事件守护范式重设计/性能采样单 plan_id×20/2.7 标题逐字源/元信息表；OD-4/5/6/8/10 五项修订 + 26 修复簇详见 Docs Review Fixes 表）
- v1.2.0: Round 2 回归核查+组合交互面修订（R1 八裁定单独 8/8 成立实证；13 项处置=P1×1+P2×6+P3×6 的 12 命名修复 + 1 项 R1-13 勘误内联——P1：degraded_section_count 计数语义空洞（信封态计入/锚叠加不计/附录 B 两类全收 R2 口径）；P2：上限算术重算/PublishResult event_id 必填/AC-4 层级映射/验收层 L0 隔离传播/level 值域收窄 1-3 等；P3：同构措辞增强/outbox 断言等价机理/CLI memory_id 打印等——R2-1~R2-12 详见修复台账；分项口径 R4 对齐节头）
- v1.3.0: Round 3 单深度推演修订（13 场景三轴推演+6 时间线+不变量数学；7 项处置——P1×1：缺行小节 H3 骨架渲染冻结（R2-2 算术证明的隐含前提显式化——省略分叉下极端形态炸 242）+ 跳步类别钦定六子步；P2×2：AC-6×1 断言面处方（字面基线全等形态）/「实体标注」载体修正（metadata.timeline_available 直查）；P3×4：矩阵场景号校正/gather 形态锚（跨 loop 陷阱）/附录 A 第三映射源/目录收录面冻结；11 条证伪留痕防重推——R3-1~R3-7 详见修复台账）
- v1.4.0: Round 4 纯验证 + Round 5 独立终审收敛（R4：36 锚点 34 匹配+结构四线全过，5 项 P3 传播缝隙/勘误修复——R1-26「L17-18→L16-17」校正反向回调等；R5：五节终审全过——十项关键修复文档-代码双向取证 10/10 成立、周期闭合零游离提交、红线零违规；特权发现 R5-1 清偿：STAGE_VALUE_DOMAIN 注记双重失实改述（blm_phases.py:69 frozenset 在位）+ OD-6 ⑤锚校正；五轮总账 60 项处置、P0-P3 残留全零、投入递减 34→13→7→5→终审收敛）
- v1.5.0: **dev-story 实施完成**（2026-11-04——Task 0~7 全 52 Subtask 闭环：Task 0 红阶段实证【12×运行期 ImportError+收集零错误】→ Task 1 领域层【24+17【分隔行变异实证】+20 用例/四处登记/design.md 双表回填含 483/484 顺带修正】→ Task 2 应用层【30 用例【事件变异实证】/三态判定全套口径/端口契约 docstring】→ Task 3 基础设施【017 幂等实证/仓储双模式 fallback/CLI 五步定式/三步排查实证/组合根三注册块】→ Task 4 契约守护【事件键集合冻结全等 6 用例/冻结面零 diff/红线三查】→ Task 5 集成五场景【双模式两轮稳定/净增 0/P95 实测亚秒级】→ Task 6 架构四验证器 9 用例 → Task 7 验收 13 场景全绿双模式 + 全量 **14602 passed×2 轮完全稳定** + 覆盖率 92%/91%/新增 96-100% + mypy 746 零错误；状态流转 ready-for-dev→in-progress→**review**）
- v1.6.0: **代码审查 Round 1**（2026-11-04：五视角并行调研 Agent【领域/应用/基础设施组装/测试质量/一致性契约】+ 主会话 12 文件亲验矩阵 + P1×3 逐项独立实证；29 项 findings=P1×3+P2×10+P3×16，本轮处置 19 项【P1：附录 A synthesis 值形态错配【写侧实证 market_insight_synthesis】/get_latest 排序零杀伤恒真断言族/AC-2 十余冻结字段断言缺口；P2：GFM 结构字符转义+callout 多行前缀/实体五查补全/section_count 派生化/models 聚合/CLI 枚举 repr+断言遮蔽×2/映射恒绿断言/非 dict 分支+快照容错覆盖；P3 联动：空 dict 信封/口径 docstring/死代码死常量/台账勘误/I001】；10 项 P3 留后续轮次——CR1-F1~F30 详见 Review Findings 表；冻结表述四处勘误：附录 A 三源映射 synthesis 真实值形态/渲染语法冻结补 GFM 结构性转义限定/实体表 generation_ms 实际窗口注记+五查校验清单/异常用例数 21→20）
