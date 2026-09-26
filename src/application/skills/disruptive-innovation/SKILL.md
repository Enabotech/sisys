---
slug: disruptive-innovation
name: 破坏性创新模型
version: 1.0.0
tool_name: 破坏性创新模型
description: Christensen 破坏性创新（低端/新市场颠覆），基于专利与 Web 情报双源交叉验证颠覆信号
when_to_use:
  - 颠覆风险评估
  - 新兴市场识别
  - 创新战略
when_not_to_use:
  - 渐进式创新分析
capabilities:
  - disruption_analysis
  - innovation_strategy
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - model
  - innovation
data_sources:
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
input_schema:
  type: object
  required:
    - technology_domain
  properties:
    technology_domain:
      type: string
      description: 技术领域（如 "固态电池"）
    incumbent_industry:
      type: string
      description: 可选在位行业（评估颠覆对象）
output_schema:
  type: object
  required:
    - disruption_signals
    - technology_maturity
    - innovation_assessment
    - data_sources
  properties:
    disruption_signals:
      type: array
      description: 颠覆信号清单（专利/市场/技术信号）
      items:
        type: object
        required: [signal_type, description, strength, sources]
        properties:
          signal_type:
            type: string
            enum: [专利信号, 市场信号, 技术信号]
            description: 信号类型
          description:
            type: string
            description: 信号描述
          strength:
            type: number
            description: 信号强度（0-1）
          sources:
            type: array
            description: 数据来源（双源交叉验证）
            items:
              type: string
    technology_maturity:
      type: string
      enum: [萌芽期, 成长期, 成熟期, 衰退期]
      description: 技术成熟度评级
    innovation_assessment:
      type: string
      description: 颠覆性创新综合评估结论
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 破坏性创新模型

> Christensen 破坏性创新评估工作坊操作手册（低端颠覆 / 新市场颠覆双路径）。
> 数据采集经 `$DATA_SOURCE` 标记由宿主机侧 DataSourceResolver 完成（沙箱无网络不变量），
> 本 SOP 引导 LLM 生成正确的采集代码并基于双源交叉验证的真实数据完成颠覆信号识别
> 与技术成熟度评估。

## 1. 适用场景

- 颠覆风险评估：在位企业评估新兴技术/商业模式对现有业务的颠覆威胁
- 新兴市场识别：识别低端切入或新市场切入的颠覆机会窗口
- 创新战略：制定颠覆者进攻策略或在位者防御策略

## 2. 负向触发

- 渐进式创新分析：维持性技术改进不适用破坏性创新框架，请用 competitor-analysis 对标
- 纯技术可行性评估：本工具聚焦市场颠覆动力学，非技术成熟度深度评测（TRL 评估请用专项工具）

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `technology_domain` | string | ✅ | 技术领域（如 "固态电池"） |
| `incumbent_industry` | string | 可选 | 在位行业（评估颠覆对象） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `disruption_signals[]` | array | 颠覆信号清单（signal_type/description/strength/sources） |
| `technology_maturity` | enum | 萌芽期 / 成长期 / 成熟期 / 衰退期 |
| `innovation_assessment` | string | 颠覆性创新综合评估结论 |
| `data_sources[]` | array | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

Think 阶段必须先输出**颠覆信号 → 数据源**映射计划，再生成采集代码：

| 信号类型 | 观测指标 | 数据源 |
|---------|---------|--------|
| 专利信号 | 专利申请趋势、核心专利布局、新进入者专利占比 | uspto（PatentsView） |
| 市场信号 | 新创企业融资、低端/边缘市场采纳、价格性能比拐点 | tavily（Web 情报） |
| 技术信号 | 性能提升斜率、关键突破报道、产学研动态 | uspto + tavily 双源互证 |

**双源交叉验证要求（决策 D4）**：本工具声明 2 个数据源，每个颠覆信号必须由
专利数据（uspto）与市场情报（tavily）交叉印证——单一来源信号强度上限 0.5，
双源互证后方可评级 >0.5；交叉验证流程见 `references/triangulation.md`。

## 6. SOP 执行步骤

1. **解析输入**：校验 `technology_domain` 必填字段
2. **Think**：输出颠覆信号假设与数据源映射（§5），明确双源互证计划
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源至少一个标记；query 为自然语言指标描述（含技术领域上下文）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取：`DATA_SOURCES["uspto"]["payload"]`，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成信号强度评级与技术成熟度判定
   （锚点见 `references/scoring_anchors.md`）
6. **综合评估**：按 Christensen 框架判定颠覆路径（低端/新市场/无颠覆信号），
   输出 `innovation_assessment` 结论
7. **输出**：按 output_schema 组装，每个信号 `sources` 字段如实登记互证来源

采集代码骨架示例：

```python
patents = $DATA_SOURCE("uspto", "固态电池 专利申请趋势 核心专利布局")
market = $DATA_SOURCE("tavily", "固态电池 创业公司 融资 商业化进展")

# 采集后通过注入的 DATA_SOURCES dict 读取
uspto_payload = DATA_SOURCES["uspto"]["payload"]
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，颠覆信号仅单源支撑，强度评级封顶 0.5 并显式标注」 |
| 411 未注册（Key 缺失） | tavily 未配置 API Key，冷启动未注册 | 「数据源 tavily 因 API Key 未配置未注册，市场情报维度缺失，**输出中显式标注数据缺口**：颠覆信号仅专利单源支撑，强度评级封顶 0.5」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 2 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：单源降级时所有信号强度评级封顶 0.5（不满足双源互证前提）；
所有降级必须在输出 `data_sources` 溯源元数据与信号 `sources` 字段中如实反映。

## 8. input_examples

```json
{
  "technology_domain": "固态电池",
  "incumbent_industry": "锂离子电池"
}
```

对应采集 query 构造示例（环境变量引用形式，禁止写入真实 API Key）：
`api_key=os.environ['TAVILY_API_KEY']`（由宿主机侧适配器配置持有，沙箱代码不可见）。

## 9. References 指引

- `references/triangulation.md` — 双源交叉验证规范（专利 ↔ 市场情报互证流程）
- `references/scoring_anchors.md` — 技术成熟度锚点 + 颠覆信号强度分级
- `references/workshop_guide.md` — 颠覆性创新评估工作坊 + 专家访谈提纲
- `templates/technology_assessment_matrix.md` — 技术评估矩阵模板
