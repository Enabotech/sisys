---
slug: pestel-analysis
name: PESTEL 分析
version: 1.0.0
tool_name: PESTEL 分析
description: 宏观环境六维度扫描（政治/经济/社会/技术/环境/法律），基于 6 个权威外部数据源自动采集实证数据
when_to_use:
  - 环境扫描
  - 宏观环境评估
  - 战略输入分析
when_not_to_use:
  - 行业内部五力分析请用 porters-five-forces
  - 企业内部资源能力评估请用 vrio-framework
capabilities:
  - environment_analysis
  - macro_scanning
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - external
data_sources:
  - name: world-bank
    url: https://api.worldbank.org/v2
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - indicator
      - value
  - name: imf
    url: https://www.imf.org/external/datamapper/api/v1
    api_type: sdmx_json
    ttl_seconds: 604800
    required_fields:
      - indicator
      - value
  - name: eurostat
    url: https://ec.europa.eu/eurostat/api/dissemination
    api_type: sdmx_json
    ttl_seconds: 604800
    required_fields:
      - indicator
      - value
  - name: ipcc
    url: https://www.ipcc.ch/data
    api_type: csv_download
    ttl_seconds: 2592000
    required_fields:
      - indicator
      - value
  - name: newsapi
    url: https://newsapi.org
    api_type: rest_json
    ttl_seconds: 21600
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
  required:
    - industry
    - region_scope
    - time_horizon_years
  properties:
    industry:
      type: string
      description: 目标行业（如 "新能源汽车"）
    region_scope:
      type: string
      description: 地域范围（如 "global" / "china" / "eu"）
    time_horizon_years:
      type: integer
      description: 分析年限（1-10 年）
    focus_dimensions:
      type: array
      description: 可选聚焦维度子集（缺省全六维度）
      items:
        type: string
        enum: [P, E, S, T, En, L]
output_schema:
  type: object
  required:
    - pestel_dimensions
    - weighted_total
    - score_grade
    - data_sources
  properties:
    pestel_dimensions:
      type: array
      description: 六维度评估结果（每维度含评分/指标/来源）
      items:
        type: object
        required: [dimension, score, indicators, sources]
        properties:
          dimension:
            type: string
            enum: [P, E, S, T, En, L]
            description: 维度代码
          score:
            type: number
            description: 维度评分（0-1，机会趋 1 威胁趋 0）
          indicators:
            type: array
            description: 关键指标观测值列表
            items:
              type: object
          sources:
            type: array
            description: 该维度数据来源（≥3 独立来源三角化）
            items:
              type: string
    weighted_total:
      type: number
      description: 加权总分（权重见 references/scoring_matrix.json）
    score_grade:
      type: string
      enum: [机会主导, 中性, 威胁主导]
      description: 综合评级（≥0.7 机会 / ≤0.4 威胁 / 其余中性）
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# PESTEL 分析

> 宏观环境六维度扫描工作坊操作手册。数据采集经 `$DATA_SOURCE` 标记由宿主机侧
> DataSourceResolver 完成（沙箱无网络不变量），本 SOP 引导 LLM 生成正确的采集代码
> 并基于注入的真实数据完成六维度评分与综合研判。

## 1. 适用场景

- 环境扫描：进入新市场/新区域前的宏观环境系统性扫描
- 宏观环境评估：SP 制定期对政治/经济/社会/技术/环境/法律六维度的结构化评估
- 战略输入分析：为 SWOT-TOWS、情景规划提供外部环境输入（O/T 象限实证依据）

## 2. 负向触发

- 行业内部五力分析请用 porters-five-forces（中观行业结构，非宏观环境）
- 企业内部资源能力评估请用 vrio-framework（内部视角，非外部环境）
- 纯定性专家判断场景（本工具以数据驱动为核心价值，无数据需求的快速研讨不必调用）

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `industry` | string | ✅ | 目标行业（如 "新能源汽车"） |
| `region_scope` | string | ✅ | 地域范围（"global" / "china" / "eu" 等） |
| `time_horizon_years` | integer | ✅ | 分析年限（1-10 年） |
| `focus_dimensions` | array | 可选 | 聚焦维度子集（P/E/S/T/En/L，缺省全六维度） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `pestel_dimensions[]` | array | 六维度评估（dimension/score/indicators/sources） |
| `weighted_total` | number | 加权总分（权重见 `references/scoring_matrix.json`） |
| `score_grade` | enum | 机会主导（≥0.7）/ 中性 / 威胁主导（≤0.4） |
| `data_sources[]` | array | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

Think 阶段必须先输出**维度 → 指标 → 数据源**映射计划，再生成采集代码：

| 维度 | 关键指标 | 数据源 |
|------|---------|--------|
| P 政治 | 治理指数、政策稳定性、监管动态 | world-bank（治理指标）、newsapi（时政新闻） |
| E 经济 | GDP 增速、通胀率、汇率、经济展望 | world-bank（GDP）、imf（世界经济展望）、china-nbs（中国维度） |
| S 社会 | 人口结构、城镇化率、消费倾向 | world-bank（人口指标）、china-nbs（中国社会统计） |
| T 技术 | 研发投入占比、技术扩散速率 | world-bank（R&D 指标）、newsapi（技术动态） |
| En 环境 | 碳排放、气候情景、环境规制 | ipcc（气候数据）、eurostat（欧盟环境统计） |
| L 法律 | 法规变更、合规成本 | newsapi（法规新闻）、eurostat（欧盟法规维度） |

**三角化要求**：每个维度的关键指标必须由 ≥3 个独立来源印证（三角化规范见
`references/triangulation.md`）；6 个声明源全部参与采集，禁止仅用单一来源下结论。

## 6. SOP 执行步骤

1. **解析输入**：校验 `industry` / `region_scope` / `time_horizon_years` 必填字段
2. **Think**：输出维度 → 指标 → 数据源映射（§5），声明各维度采集目标
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源至少一个标记；query 为自然语言指标描述（含行业/地域/年限上下文）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取，**必须使用 `.get()` 防御性读取**，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`。
     **部分失败语义**：采集失败的源其键**不在** `DATA_SOURCES` 中（对应标记位注入 `None`）——
     读取返回 `None` 时按 §7 降级话术处理，禁止直接下标（`["payload"]` 会 KeyError 中断）。
     **同源多 query**：同一数据源的多个不同 query 依次分配 `"<name>"` / `"<name>#2"` 键
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成六维度评分（评分锚点见 `references/scoring_anchors.md`）
6. **聚合评分**：调用 `scripts/aggregate_scores.py`（确定性任务，代码优先），
   输入六维度评分 JSON，输出加权总分与机会/威胁分类（权重对齐 `references/scoring_matrix.json`）
7. **输出**：按 output_schema 组装，每维度 `sources` 字段如实登记实际印证来源

采集代码骨架示例：

```python
gdp = $DATA_SOURCE("world-bank", "中国 GDP 增速 2020-2025")
outlook = $DATA_SOURCE("imf", "世界经济展望 中国经济预测")
eu_stats = $DATA_SOURCE("eurostat", "欧盟 绿色经济 环境统计")
climate = $DATA_SOURCE("ipcc", "IPCC AR6 排放情景数据")
news = $DATA_SOURCE("newsapi", "新能源汽车 政策 法规 最新动态")
cn_stats = $DATA_SOURCE("china-nbs", "中国社会消费品零售 人口统计")

# 采集后通过注入的 DATA_SOURCES dict 防御性读取（失败源键不存在 → None → 按 §7 降级）
wb_payload = (DATA_SOURCES.get("world-bank") or {}).get("payload")
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，本次分析基于其余 N-1 个来源完成，该维度结论置信度下调并标注」 |
| 411 未注册（Key 缺失） | newsapi/tavily 未配置 API Key，冷启动未注册 | 「数据源 X 因 API Key 未配置未注册，相应维度基于其余来源完成，**输出中显式标注数据缺口**：时政新闻/中国消费维度缺失实时舆情印证」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 6 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：部分失败不中断分析；所有降级必须在输出 `data_sources` 溯源元数据与
维度 `sources` 字段中如实反映，禁止以估计值冒充采集值。

## 8. input_examples

```json
{
  "industry": "新能源汽车",
  "region_scope": "china",
  "time_horizon_years": 5,
  "focus_dimensions": ["P", "E", "T", "En"]
}
```

对应采集 query 构造示例（环境变量引用形式，禁止写入真实 API Key）：
`api_key=os.environ['NEWSAPI_API_KEY']`（由宿主机侧适配器配置持有，沙箱代码不可见）。

## 9. References 指引

- `references/triangulation.md` — 多源三角化规范（≥3 独立来源印证流程与冲突裁决）
- `references/scoring_anchors.md` — 六维度评分锚点（0-1 分档定义与示例）
- `references/workshop_guide.md` — PESTEL 工作坊引导方法论（研讨流程/角色/产出物）
- `references/scoring_matrix.json` — 六维度权重与指标清单（aggregate_scores.py 的权重 SSOT）
- `templates/pestel_collection_matrix.md` — PESTEL 数据采集矩阵模板（工作坊填写用）
- `scripts/aggregate_scores.py` — 加权评分聚合脚本（stdin 输入六维评分 JSON → 加权总分）
