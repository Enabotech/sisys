---
slug: appeals-analysis
name: $APPEALS
version: 1.0.0
tool_name: $APPEALS
description: 顾客价值 8 维度分析（$/A/P/P/E/A/L/S），基于 3 个外部数据源自动采集顾客洞察实证数据
when_to_use:
  - 顾客需求洞察
  - 产品价值定位
  - 市场细分
when_not_to_use:
  - 成本结构分析请用 value-chain-analysis
capabilities:
  - customer_analysis
  - market_segmentation
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - customer
data_sources:
  - name: tavily
    url: https://api.tavily.com
    api_type: rest_json
    ttl_seconds: 86400
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
  required: [product_category, target_segment]
  properties:
    product_category:
      type: string
      description: 产品类别（如 "智能手表"）
    target_segment:
      type: string
      description: 目标客群细分市场
    region_scope:
      type: string
      description: 地域范围（缺省 china）
output_schema:
  type: object
  required: [appeals_dimensions, overall_score, data_sources]
  properties:
    appeals_dimensions:
      type: array
      description: $APPEALS 八维度评估（价格/可获得性/包装/性能/易用性/保证程度/生命周期成本/社会接受度）
      items:
        type: object
        required: [dimension, score, customer_evidence, sources]
        properties:
          dimension:
            type: string
            enum: [价格, 可获得性, 包装, 性能, 易用性, 保证程度, 生命周期成本, 社会接受度]
            description: 维度名称
          score:
            type: number
            description: 维度评分（0-1）
          customer_evidence:
            type: array
            description: 顾客洞察证据列表
            items:
              type: string
          sources:
            type: array
            description: 数据来源
            items:
              type: string
    overall_score:
      type: number
      description: 综合顾客价值评分（0-1）
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# $APPEALS

> 顾客价值八维度（价格/可获得性/包装/性能/易用性/保证程度/生命周期成本/社会接受度）
> 评估工作坊操作手册。数据采集经 `$DATA_SOURCE` 标记由宿主机侧 DataSourceResolver
> 完成（沙箱无网络不变量），本 SOP 引导 LLM 生成正确的采集代码并基于注入的真实
> 数据完成八维度评分与综合研判。

## 1. 适用场景

- 顾客需求洞察：新产品立项/现有产品迭代前，对目标客群购买决策要素的系统性洞察
- 产品价值定位：SP/BP 制定期对顾客价值主张的八维度结构化评估与差异化定位
- 市场细分：基于八维度偏好差异识别细分客群，为价值曲线、VPC 提供顾客侧实证输入

## 2. 负向触发

- 成本结构分析请用 value-chain-analysis（企业内部成本视角，非顾客价值视角）
- 宏观环境扫描请用 pestel-analysis（外部环境，非顾客需求）
- 纯定性头脑风暴场景（本工具以顾客实证数据驱动为核心价值，无数据需求的快速研讨不必调用）

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `product_category` | string | ✅ | 产品类别（如 "智能手表"） |
| `target_segment` | string | ✅ | 目标客群细分市场（如 "一线城市 25-35 岁运动人群"） |
| `region_scope` | string | 可选 | 地域范围（缺省 "china"） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `appeals_dimensions[]` | array | 八维度评估（dimension/score/customer_evidence/sources） |
| `overall_score` | number | 综合顾客价值评分（0-1，八维度等权均值） |
| `data_sources[]` | array | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

Think 阶段必须先输出**维度 → 顾客洞察指标 → 数据源**映射计划，再生成采集代码：

| 维度 | 顾客洞察指标 | 数据源 |
|------|-------------|--------|
| $ 价格 | 目标客群价格敏感度、主流价格带、促销弹性 | tavily（顾客价格讨论）、newsapi（定价舆情） |
| A 可获得性 | 渠道覆盖、购买便利性、缺货率 | tavily（渠道讨论）、china-nbs（零售业态统计） |
| P 包装 | 外观偏好、开箱体验、环保包装诉求 | tavily（顾客评价）、newsapi（包装趋势） |
| P 性能 | 核心功能满意度、性能痛点、竞品性能口碑 | tavily（产品评测）、newsapi（性能舆情） |
| E 易用性 | 学习成本、操作复杂度抱怨、上手体验 | tavily（用户体验讨论）、newsapi（易用性报道） |
| A 保证程度 | 质保期望、售后满意度、服务口碑 | tavily（售后评价）、newsapi（服务舆情） |
| L 生命周期成本 | 使用成本、维护成本、置换成本感知 | tavily（TCO 讨论）、china-nbs（居民消费支出结构） |
| S 社会接受度 | 社会认同、环保/伦理关注、潮流契合度 | newsapi（社会舆情）、china-nbs（消费倾向统计） |

**三角化要求**：每个维度的关键洞察必须由全 3 个声明源交叉印证（三角化规范见
`references/triangulation.md`）；3 个声明源全部参与采集，禁止仅用单一来源下结论。

## 6. SOP 执行步骤

1. **解析输入**：校验 `product_category` / `target_segment` 必填字段，`region_scope` 缺省取 "china"
2. **Think**：输出维度 → 指标 → 数据源映射（§5），声明八维度采集目标
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源恰好一个标记；query 为自然语言指标描述（含产品类别/目标客群/地域上下文）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取，**必须使用 `.get()` 防御性读取**，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`。
     **部分失败语义**：采集失败的源其键**不在** `DATA_SOURCES` 中（对应标记位注入 `None`）——
     读取返回 `None` 时按 §7 降级话术处理，禁止直接下标（`["payload"]` 会 KeyError 中断）。
     **同源多 query**：同一数据源的多个不同 query 依次分配 `"<name>"` / `"<name>#2"` 键
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成八维度评分（评分锚点见 `references/scoring_anchors.md`）
6. **聚合评分**：计算八维度等权均值得出 `overall_score`（确定性算术，代码优先）
7. **输出**：按 output_schema 组装，每维度 `sources` 字段如实登记实际印证来源

采集代码骨架示例：

```python
customer_insights = $DATA_SOURCE("tavily", "智能手表 一线城市 25-35 岁运动人群 顾客评价 价格 性能 易用性 售后")
market_sentiment = $DATA_SOURCE("newsapi", "智能手表 消费者 口碑 舆情 社会接受度")
cn_consumption = $DATA_SOURCE("china-nbs", "中国居民消费支出结构 智能穿戴 零售统计")

# 采集后通过注入的 DATA_SOURCES dict 读取
tavily_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，本次分析基于其余 N-1 个来源完成，该维度结论置信度下调并标注」 |
| 411 未注册（Key 缺失） | tavily/newsapi 未配置 API Key，冷启动未注册 | 「数据源 X 因 API Key 未配置未注册，相应维度基于其余来源完成，**输出中显式标注数据缺口**：顾客洞察搜索/市场舆情维度缺失实时印证」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造顾客证据」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 3 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：部分失败不中断分析；所有降级必须在输出 `data_sources` 溯源元数据与
维度 `sources` 字段中如实反映，禁止以估计值冒充采集值。

## 8. input_examples

```json
{
  "product_category": "智能手表",
  "target_segment": "一线城市 25-35 岁运动人群",
  "region_scope": "china"
}
```

对应采集 query 构造示例（环境变量引用形式，禁止写入真实 API Key）：
`api_key=os.environ['TAVILY_API_KEY']`（由宿主机侧适配器配置持有，沙箱代码不可见）。

## 9. References 指引

- `references/triangulation.md` — 顾客洞察多源三角化规范（全 3 源交叉印证流程与冲突裁决）
- `references/scoring_anchors.md` — 八维度评分锚点（0-1 分档定义与示例）
- `references/workshop_guide.md` — $APPEALS 工作坊引导方法论（研讨流程/角色/产出物）
- `templates/appeals_customer_questionnaire.md` — $APPEALS 顾客问卷模板（八维度问题清单）
