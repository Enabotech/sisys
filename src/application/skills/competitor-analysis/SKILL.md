---
slug: competitor-analysis
name: 竞争对手分析
version: 1.0.0
tool_name: 竞争对手分析
description: 竞争对手画像 + 战略 + 优势劣势综合分析
when_to_use:
  - 竞争对手识别
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
      description: 竞品企业清单（≥1 家）
      items:
        type: string
    analysis_dimensions:
      type: array
      description: 可选对标维度子集（缺省全维度）
      items:
        type: string
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
            description: 专利技术信号（USPTO）
            items:
              type: string
          sources:
            type: array
            description: 数据来源
            items:
              type: string
    benchmark_matrix:
      type: object
      description: 竞品对标矩阵（维度 × 企业评分）
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

- 竞争对手识别：进入新市场/新产品线前对主要竞品企业的系统性画像
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
| `competitors` | array | ✅ | 竞品企业清单（≥1 家，如 ["比亚迪", "特斯拉"]） |
| `analysis_dimensions` | array | 可选 | 对标维度子集（缺省全维度：战略动向/专利布局/产品组合/市场份额） |

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
| 专利布局 | 专利申请趋势、技术领域分布、核心专利信号 | uspto（竞品专利，USPTO 技术信号采集引导） |
| 产品组合 | 产品线结构、新品发布、定价策略 | tavily（官网/评测/电商情报）、newsapi（产品新闻） |
| 市场份额 | 销量/营收份额、行业排名、区域渗透率 | china-nbs（中国行业对标统计）、newsapi（行业报道） |

**三角化要求**：每个对标维度的关键指标必须由 ≥3 个独立来源印证（三角化规范见
`references/triangulation.md`）；本 Skill 4 个声明源全部参与采集、全维度覆盖，
禁止仅用单一来源下结论。

## 6. SOP 执行步骤

1. **解析输入**：校验 `industry` / `competitors` 必填字段（competitors 至少 1 家）
2. **Think**：输出对标维度 → 指标 → 数据源映射（§5），声明各维度采集目标
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源恰好一个标记；query 为自然语言指标描述（含行业/竞品名/时间上下文）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取，**必须使用 `.get()` 防御性读取**，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`。
     **部分失败语义**：采集失败的源其键**不在** `DATA_SOURCES` 中（对应标记位注入 `None`）——
     读取返回 `None` 时按 §7 降级话术处理，禁止直接下标（`["payload"]` 会 KeyError 中断）。
     **同源多 query**：同一数据源的多个不同 query 依次分配 `"<name>"` / `"<name>#2"` 键
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成竞品画像与维度评分（评分锚点见 `references/scoring_anchors.md`）
6. **工作坊**：按竞品调研工作坊流程（引导见 `references/workshop_guide.md`）
   组织专家研判，将对标结论填入矩阵模板 `templates/competitor_benchmark_matrix.md`
7. **输出**：按 output_schema 组装，每竞品 `sources` 字段如实登记实际印证来源

采集代码骨架示例：

```python
news = $DATA_SOURCE("newsapi", "新能源汽车 比亚迪 特斯拉 战略动态 市场份额 最新报道")
patents = $DATA_SOURCE("uspto", "BYD Tesla 电动汽车 电池技术 专利申请趋势")
web_intel = $DATA_SOURCE("tavily", "比亚迪 特斯拉 产品组合 定价策略 竞品分析")
cn_stats = $DATA_SOURCE("china-nbs", "中国新能源汽车 行业产销量 企业市场份额统计")

# 采集后通过注入的 DATA_SOURCES dict 读取
uspto_payload = (DATA_SOURCES.get("uspto") or {}).get("payload")
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，本次对标基于其余 N-1 个来源完成，该维度结论置信度下调并标注」 |
| 411 未注册（Key 缺失） | newsapi/tavily 未配置 API Key，冷启动未注册 | 「数据源 X 因 API Key 未配置未注册，相应维度基于其余来源完成，**输出中显式标注数据缺口**：竞品舆情/Web 情报维度缺失实时印证」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 4 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

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

- `references/triangulation.md` — 竞品情报三角化规范（≥3 独立来源印证流程与冲突裁决）
- `references/scoring_anchors.md` — 对标矩阵评分锚点（0-1 分档定义与示例）
- `references/workshop_guide.md` — 竞品调研工作坊引导方法论（研讨流程/角色/产出物）
- `templates/competitor_benchmark_matrix.md` — 竞品对标矩阵模板（维度 × 企业，工作坊填写用）
