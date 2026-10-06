---
slug: competitor-analysis
name: 竞争对手分析
version: 1.0.0
tool_name: 竞争对手分析
description: 竞争对手画像 + 四维对标（战略动向/专利布局/产品组合/市场份额）矩阵分析
when_to_use:
  - 已知竞品系统画像
  - 战略对标
  - 市场份额分析
when_not_to_use:
  - 单一企业内部诊断
capabilities:
  - competitor_profiling
  - strategic_benchmarking
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - competitive
data_sources:
  - name: newsapi
    url: https://newsapi.org
    api_type: rest_json
    ttl_seconds: 21600
    required_fields:
      - indicator
      - value
  - name: uspto
    url: https://search.patentsview.org
    api_type: rest_json
    ttl_seconds: 2592000
    required_fields:
      - indicator
      - value
  - name: google-patents
    url: https://bigquery.googleapis.com
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - publication_number
      - assignee
      - filing_date
  - name: epo-ops
    url: https://ops.epo.org
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - title
      - applicant
      - filing_date
  - name: sec-edgar
    url: https://efts.sec.gov
    api_type: rest_json
    ttl_seconds: 2592000
    required_fields:
      - company
      - form
      - filed_at
  - name: tavily
    url: https://api.tavily.com
    api_type: rest_json
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
  - name: china-nbs
    url: https://www.stats.gov.cn
    api_type: crawler
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required: [industry, competitors]
  properties:
    industry:
      type: string
      description: 目标行业
    competitors:
      type: array
      description: 竞品企业清单（≥2 家，推荐 3-5 家——单竞品输入时输出退化为单竞品画像并标注）
      minItems: 2
      items:
        type: string
    analysis_dimensions:
      type: array
      description: 可选对标维度子集（缺省全维度）
      items:
        type: string
        enum: [战略动向, 专利布局, 产品组合, 市场份额]
output_schema:
  type: object
  required: [competitor_profiles, benchmark_matrix, data_sources]
  properties:
    competitor_profiles:
      type: array
      description: 竞品画像列表
      items:
        type: object
        required: [name, strategy_summary, patent_signals, sources]
        properties:
          name:
            type: string
            description: 竞品企业名称
          strategy_summary:
            type: string
            description: 战略动向摘要
          patent_signals:
            type: array
            description: 专利技术信号（uspto+google-patents+epo-ops 三库口径——三库均未注册或采集失败时输出空数组，并在 sources 与数据缺口登记中如实标注）
            items:
              type: string
          sources:
            type: array
            description: 实际印证来源（源名与 data_sources 溯源元数据对齐，禁止登记未采集来源）
            items:
              type: string
    benchmark_matrix:
      type: object
      description: 竞品对标矩阵（维度 × 企业评分）
      properties:
        dimensions:
          type: array
          description: 参与对标的维度清单（战略动向/专利布局/产品组合/市场份额）
          items:
            type: string
        companies:
          type: array
          description: 对标企业清单
          items:
            type: string
        scores:
          type: object
          description: 评分矩阵（外层键为维度名，内层键为企业名，值为 0-1 评分）
        data_gaps:
          type: array
          description: 数据缺口登记（源缺失或印证不足的维度及影响）
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 竞争对手分析

> 竞品对标矩阵方法论 + 竞品调研工作坊操作手册。数据采集经 `$DATA_SOURCE` 标记由宿主机侧
> DataSourceResolver 完成（沙箱无网络不变量），本 SOP 引导 LLM 生成正确的采集代码
> 并基于注入的真实数据完成竞品画像、专利信号研判与对标矩阵评分。

## 1. 适用场景

- 已知竞品系统画像：对已识别竞品企业的系统性画像深化（竞品发现不在本工具范围——无已知竞品清单时先经行业研究建立清单）
- 战略对标：SP 制定期对竞品战略动向/专利布局/产品组合/市场份额的结构化对标
- 市场份额分析：为 SWOT-TOWS、战略地图提供竞争格局实证依据（O/T 象限的竞争侧输入）

## 2. 负向触发

- 单一企业内部诊断请用 vrio-framework（内部资源能力视角，非竞争对标）
- 行业结构吸引力评估请用 porters-five-forces（中观五力，非企业级对标）
- 宏观环境扫描请用 pestel-analysis（外部宏观六维度，非竞品企业维度）

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `industry` | string | ✅ | 目标行业（如 "新能源汽车"） |
| `competitors` | array | ✅ | 竞品企业清单（≥2 家，推荐 3-5 家，如 ["比亚迪", "特斯拉"]；minItems 2——单竞品时输出退化并标注） |
| `analysis_dimensions` | array | 可选 | 对标维度子集（enum 四值：战略动向/专利布局/产品组合/市场份额——缺省全维度） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `competitor_profiles[]` | array | 竞品画像（name/strategy_summary/patent_signals/sources） |
| `benchmark_matrix` | object | 竞品对标矩阵（维度 × 企业评分，模板见 `templates/competitor_benchmark_matrix.md`） |
| `data_sources[]` | array | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

Think 阶段必须先输出**对标维度 → 关键指标 → 数据源**映射计划，再生成采集代码：

| 对标维度 | 关键指标 | 数据源 |
|---------|---------|--------|
| 战略动向 | 竞品战略发布、并购重组、高管言论、舆情倾向 | newsapi（竞品动态舆情）、tavily（竞品 Web 情报） |
| 专利布局 | 专利申请趋势、技术领域分布、核心专利信号 | uspto（US 口径）+ google-patents（BigQuery 全球含 CN 99.96%，assignee 精确聚合）+ epo-ops（EP 口径，`pa=` 申请人归因——专利三库） |
| 产品组合 | 产品线结构、新品发布、定价策略 | tavily（官网/评测/电商情报）、newsapi（产品新闻） |
| 市场份额 | 销量/营收份额、行业排名、区域渗透率 | china-nbs（中国行业对标统计）、newsapi（行业报道）、sec-edgar（美股上市竞品法定披露——10-K 全文与 XBRL 营收印证） |

**源级三角化**：7 个声明源全部参与采集（并发覆盖，三角化规范见
`references/triangulation.md`）；维度级直接映射源数以上表为准（战略动向/产品组合 2 源，
专利布局 3 库（uspto+google-patents+epo-ops——域内一致性互证，非跨域互证），市场份额 3 源）——
直接映射不足的维度须跨维度关联印证或显式标注「印证不足」并下调置信度。
**同源多 query（name/#2 键）不构成独立来源**，不得计入印证数。

**数据源口径边界**：uspto 仅美国专利口径，且检索为 patent_title 标题关键词匹配
（非申请人结构化检索——归因经返回的 assignees 字段研判）；google-patents 为 BigQuery
公共数据集全球书目口径（CN 覆盖 99.96% SSRN 实证、assignee 精确聚合——月度更新新鲜度
低于 uspto/epo-ops，趋势结论宜结合源时效评估；月配额 1TiB 扫描字节，耗尽按 §7 降级）；
epo-ops 为 EPO 欧洲专利
口径（`pa=` 申请人结构化检索支持中文企业名，100+ 专利局含 CN——但仅 EP 申请视角，
合并后**仍缺 CNIPA 本土实时口径**（google-patents 补 CN 全景），全球布局画像按「US+全球+EP 三口径」标注）；
sec-edgar 仅覆盖美股上市公司（非上市/非美竞品无数据——XBRL 模式返回字段为
concept/unit/values 时序形态，与检索模式 filings 列表不同，营收份额经 values 序列
计算并标注口径）；china-nbs 为宏观/行业总量口径，不提供企业级份额数据（份额结论须
「行业→企业」显式映射推断并标注，或降级为行业格局定性判断）；newsapi 以英文新闻
覆盖为主；tavily 为 Web 事件级检索（非结构化指标级）。epo-ops 周配额（4GB/周）、
google-patents 月配额（1TiB）与 sec-edgar 类限流/配额场景按 §7 降级处理。

## 6. SOP 执行步骤

1. **解析输入**：校验 `industry` / `competitors` 必填字段（competitors 至少 2 家——minItems 2）
2. **Think**：输出对标维度 → 指标 → 数据源映射（§5），声明各维度采集目标
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源至少 1 个标记（同源多 query 依次分配 name/name#2 键——见下方同源多 query 说明）；**query 必须为该源的规范格式**（R3-P1-2 契约对齐）：
     - `newsapi` / `tavily`：检索关键词（自然语言关键词为**正确**格式，**按竞品逐家拆分 query**——每竞品一查，禁止单 query 混入多家竞品名导致归因混淆）
     - `uspto`：**英文**检索关键词（匹配 patent_title 全文）——**含竞品英文名 + 技术域词实现标题软归因**（如 `"BYD battery"`）；适配器不支持 assignee 结构化检索，采集后经返回的 assignees 字段做研判归因（口径边界见 §5）
     - `google-patents`：**管道串**（非自然语言）——`assignee=`/`cpc=`/`country=`/`year=`/`keyword=` 至少一项（如 `assignee=比亚迪|keyword=battery`；空条件被适配器拒绝防全表扫描；assignee/keyword 匹配大小写敏感——英文企业名建议大小写双形态或经 keyword 通道）
     - `epo-ops`：**CQL 结构化检索式**（非自然语言）——`pa=` 申请人（支持中文企业名直接归因）+ `ti=`/`ab=` 关键词（如 `pa="比亚迪" and ti="battery"`；多条件以 and 组合）
     - `sec-edgar`：检索式或 XBRL 前缀——检索模式 `"<关键词> forms=10-K"`（如 `"market share" forms=10-K`）；XBRL 模式 `xbrl:CIK:概念`（如 `xbrl:CIK0001318605:Revenues`——单指标营收时序，CIK 经检索模式获取）
     - `china-nbs`：站点相对路径（如 `"sj/zxfb"`=数据发布；非自然语言描述）
   - 每源采集结果量以适配器默认分页为准（SOP 引导代码不得显式请求超量数据）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取，**必须使用 `.get()` 防御性读取**，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`。
     **部分失败语义**：采集失败的源其键**不在** `DATA_SOURCES` 中（对应标记位注入 `None`）——
     读取返回 `None` 时按 §7 降级话术处理，禁止直接下标（`["payload"]` 会 KeyError 中断）。
     **同源多 query**：同一数据源的多个不同 query 依次分配 `"<name>"` / `"<name>#2"` 键
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成竞品画像与维度评分（评分锚点见 `references/scoring_anchors.md`）
6. **结论研判与工作坊衔接**：本 SOP 生成初步画像、对标矩阵与证据链、待议清单（数据缺口与冲突项）；专家研判由用户侧工作坊进行（引导见 `references/workshop_guide.md`——**所有研讨观点须溯源至注入数据或显式标注为待验证假设，禁止生成无出处的专家意见**），研讨结论回填模板 `templates/competitor_benchmark_matrix.md`
7. **输出**：按 output_schema 组装，每竞品 `sources` 字段如实登记实际印证来源

采集代码骨架示例（query 按竞品逐家拆分——每竞品一查实现归因）：

```python
# newsapi 按竞品拆分：首 query 为裸 name，第二家竞品为 name#2
news_byd = $DATA_SOURCE("newsapi", "比亚迪 战略动态 并购 新能源汽车 最新报道")
news_tesla = $DATA_SOURCE("newsapi#2", "特斯拉 战略动态 市场份额 最新报道")
# uspto 标题软归因：竞品英文名 + 技术域词（采集后经 assignees 字段研判归因）
patents_byd = $DATA_SOURCE("uspto", "BYD battery")       # 英文关键词匹配 patent_title
patents_tesla = $DATA_SOURCE("uspto#2", "Tesla battery")
# google-patents BigQuery 公共数据集（管道串——CN 全景 99.96%，与 uspto/epo-ops 构成三库域内互补）
gp_byd = $DATA_SOURCE("google-patents", "assignee=比亚迪|keyword=battery")
# epo-ops 申请人结构化检索（CQL——pa= 支持中文企业名直接归因，与 uspto/google-patents 三库域内互证）
epo_byd = $DATA_SOURCE("epo-ops", 'pa="比亚迪" and ti="battery"')
epo_tesla = $DATA_SOURCE("epo-ops#2", 'pa="Tesla" and ti="battery"')
# sec-edgar 美股上市竞品法定披露（检索模式取 10-K；XBRL 模式取营收时序）
edgar_tesla = $DATA_SOURCE("sec-edgar", '"Tesla" forms=10-K')
edgar_revenue = $DATA_SOURCE("sec-edgar#2", "xbrl:CIK0001318605:Revenues")
# tavily 按竞品拆分
web_byd = $DATA_SOURCE("tavily", "比亚迪 产品组合 定价策略 竞品情报")
web_tesla = $DATA_SOURCE("tavily#2", "特斯拉 产品组合 定价 竞品情报")
cn_stats = $DATA_SOURCE("china-nbs", "sj/zxfb")           # 国家局数据发布（行业总量口径）

# 采集后通过注入的 DATA_SOURCES dict 读取（键含 #2 后缀形态）
uspto_payload = (DATA_SOURCES.get("uspto") or {}).get("payload")
gp_payload = (DATA_SOURCES.get("google-patents") or {}).get("payload")
epo_payload = (DATA_SOURCES.get("epo-ops") or {}).get("payload")
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，本次对标基于其余 N-1 个来源完成，该维度结论置信度下调并标注」 |
| 411 未注册（Key 缺失） | newsapi/tavily/uspto/epo-ops/google-patents 未配置 API Key/凭据，冷启动未注册（uspto 自 R3 起条件注册；epo-ops 双凭据门——Consumer Key/Secret 任一缺失即不注册（休眠保留，key 到位自动激活）；google-patents GCP 双门——GOOGLE_APPLICATION_CREDENTIALS 凭据文件 + GOOGLE_PATENTS_PROJECT_ID 任一缺失即不注册；sec-edgar/china-nbs 免 key 恒注册） | 「数据源 X 因 API Key/凭据未配置未注册，相应维度基于其余来源完成，**输出中显式标注数据缺口**：竞品舆情/Web 情报/专利维度缺失实时印证（patent_signals 输出空数组承载缺口——schema 必填指键存在，空数组合法；禁止编造专利信号）」 |
| 412 限流 | 429 配额耗尽 / epo-ops 周配额（4GB/周）前置拦截 / google-patents 月配额（1TiB 扫描字节/月）前置拦截 | 「数据源 X 触发限流或配额耗尽，使用缓存快照（freshness_score 已折算）并标注数据时效；专利库配额耗尽时专利维度回落其余可用库（uspto/google-patents/epo-ops 三库中剩余者）并标注「缺失库口径」」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 7 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：部分失败不中断对标；所有降级必须在输出 `data_sources` 溯源元数据与
竞品 `sources` 字段中如实反映，禁止以估计值冒充采集值。

## 8. input_examples

```json
{
  "industry": "新能源汽车",
  "competitors": ["比亚迪", "特斯拉"],
  "analysis_dimensions": ["战略动向", "专利布局", "市场份额"]
}
```

对应采集 query 构造示例（环境变量引用形式，禁止写入真实 API Key）：
`api_key=os.environ['NEWSAPI_API_KEY']` / `api_key=os.environ['TAVILY_API_KEY']`
（由宿主机侧适配器配置持有，沙箱代码不可见）。

## 9. References 指引

- `references/triangulation.md` — 竞品情报三角化规范（源级三角化印证流程、独立性纪律与冲突裁决）
- `references/scoring_anchors.md` — 对标矩阵评分锚点（0-1 分档定义与示例）
- `references/workshop_guide.md` — 竞品调研工作坊引导方法论（研讨流程/角色/产出物）
- `templates/competitor_benchmark_matrix.md` — 竞品对标矩阵模板（维度 × 企业，工作坊填写用）
