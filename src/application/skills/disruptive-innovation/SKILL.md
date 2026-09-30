---
slug: disruptive-innovation
name: 破坏性创新模型
version: 1.0.0
tool_name: 破坏性创新模型
description: Christensen 破坏性创新（低端/新市场颠覆），基于专利双库（USPTO+EPO）与 Web 情报跨域交叉验证颠覆信号
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
  - name: epo-ops
    url: https://ops.epo.org
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - title
      - applicant
      - filing_date
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
            description: 数据来源（专利双库 + 市场单源跨域交叉验证）
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
> 本 SOP 引导 LLM 生成正确的采集代码并基于专利双库 + 市场单源跨域交叉验证的真实数据完成颠覆信号识别
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
| 专利信号 | 专利申请趋势、核心专利布局、新进入者专利占比 | uspto（US 口径）+ epo-ops（EP 口径，`pa=` 申请人归因——专利双库） |
| 市场信号 | 新创企业融资、低端/边缘市场采纳、价格性能比拐点 | tavily（Web 情报——市场单源） |
| 技术信号 | 性能提升斜率、关键突破报道、产学研动态 | 专利双库 + tavily 跨域互证 |

**专利双库 + 市场单源，评级互证跨域（决策 D4——4-1f D8 重开后升级）**：
- **采集分工**：专利信号采自 uspto+epo-ops 专利双库、市场信号采自 tavily（上表采集分工——每源各司其职；专利双库在 US/EP 两口径上互相印证专利域内部一致性）；
- **评级互证**：颠覆信号强度评级必须跨域互证——仅专利域（双库或单库）或仅市场源支撑的信号强度上限 0.5，专利域 × 市场域跨域互证后方可评级 >0.5（降级语义见 §7）；交叉验证流程见 `references/triangulation.md`；
- **同源多 query（name/#2 键）不构成独立来源**，不得计入互证数。

**数据源口径边界**：uspto 仅美国专利口径（评估中日韩主导技术域时样本系统性偏低，结论须标注口径），检索为 patent_title 标题关键词匹配（非申请人结构化检索——新进入者占比等归因统计经返回的 assignees 字段研判）；epo-ops 为 EPO 欧洲专利口径（`pa=` 申请人结构化检索支持中文企业名直接归因，100+ 专利局含 CN——合并后仍缺 CNIPA 中国本土口径，按「US+EP 双口径」标注；周配额 4GB/周，耗尽时按 §7 限流行降级并回落 uspto 单库）；tavily 为 Web 事件级检索（非结构化指标级；CJK query 自动注入 country=china）。

## 6. SOP 执行步骤

1. **解析输入**：校验 `technology_domain` 必填字段
2. **Think**：输出颠覆信号假设与数据源映射（§5），明确专利双库 + 市场单源跨域互证计划
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源至少一个标记；**query 必须为该源的规范格式**（R3-P1-2 契约对齐）：
     - `uspto`：**英文**检索关键词（匹配 patent_title 全文，如 `"solid-state battery"`）
     - `epo-ops`：**CQL 结构化检索式**（非自然语言）——`ti=`/`ab=` 关键词 + 可选 `pa=` 申请人（如 `ti="solid-state battery"`；新进入者归因统计用 `pa=` 申请人检索）
     - `tavily`：检索关键词（自然语言关键词为**正确**格式，含技术领域上下文）
   - 每源采集结果量以适配器默认分页为准（SOP 引导代码不得显式请求超量数据）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取，**必须使用 `.get()` 防御性读取**，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`。
     **部分失败语义**：采集失败的源其键**不在** `DATA_SOURCES` 中（对应标记位注入 `None`）——
     读取返回 `None` 时按 §7 降级话术处理，禁止直接下标（`["payload"]` 会 KeyError 中断）。
     **同源多 query**：同一数据源的多个不同 query 依次分配 `"<name>"` / `"<name>#2"` 键
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成信号强度评级与技术成熟度判定
   （锚点见 `references/scoring_anchors.md`）
6. **综合评估**：按 Christensen 框架判定颠覆路径（低端/新市场/无颠覆信号），
   输出 `innovation_assessment` 结论
7. **输出**：按 output_schema 组装，每个信号 `sources` 字段如实登记互证来源

采集代码骨架示例：

```python
patents = $DATA_SOURCE("uspto", "solid-state battery")   # 英文关键词匹配 patent_title
epo_patents = $DATA_SOURCE("epo-ops", 'ti="solid-state battery"')  # CQL 关键词检索（EP 口径）
market = $DATA_SOURCE("tavily", "固态电池 创业公司 融资 商业化进展")

# 采集后通过注入的 DATA_SOURCES dict 读取
uspto_payload = (DATA_SOURCES.get("uspto") or {}).get("payload")
epo_payload = (DATA_SOURCES.get("epo-ops") or {}).get("payload")
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，颠覆信号仅单域支撑，强度评级封顶 0.5 并显式标注」 |
| 411 未注册（Key 缺失） | tavily/uspto/epo-ops 未配置 API Key/凭据，冷启动未注册（uspto 自 R3 起条件注册；epo-ops 双凭据门——Key/Secret 任一缺失即不注册） | 「数据源 X 因 API Key 未配置未注册（tavily 缺失→市场域缺失；uspto/epo-ops 均缺失→专利域缺失，单库缺失→专利域降为单口径），**输出中显式标注数据缺口**：跨域互证前提不成立——strength 按单域封顶 0.5 输出、sources 仅登记实际可用源（禁止登记未采集来源）、technology_maturity 锚点判定标注『单域证据基础』」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 3 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：单域降级（仅专利域或仅市场域支撑）时所有信号强度评级封顶 0.5（不满足跨域互证前提）；
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

- `references/triangulation.md` — 跨域交叉验证规范（专利双库 ↔ 市场情报互证流程）
- `references/scoring_anchors.md` — 技术成熟度锚点 + 颠覆信号强度分级
- `references/workshop_guide.md` — 颠覆性创新评估工作坊 + 专家访谈提纲
- `templates/technology_assessment_matrix.md` — 技术评估矩阵模板
