---
slug: ge-mckinsey-matrix
name: GE-麦肯锡矩阵
version: 1.0.0
tool_name: GE-麦肯锡矩阵
description: GE/McKinsey 9 宫格业务组合矩阵
when_to_use:
  - 业务组合管理
  - 投资优先级
  - 资源分配
when_not_to_use:
  - 单业务战略
capabilities:
  - portfolio_management
  - resource_allocation
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - portfolio
data_sources:
  - name: world-bank
    url: https://api.worldbank.org/v2
    api_type: rest_json
    ttl_seconds: 604800
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
  required: [business_units]
  properties:
    business_units:
      type: array
      description: 业务单元列表（高管访谈评分表采集，模板 ge_business_unit_scoresheet.md）
      items:
        type: object
        required: [name, industry_attractiveness, competitive_strength]
        properties:
          name:
            type: string
            description: 业务单元名称
          industry_attractiveness:
            type: number
            description: 行业吸引力评分（1-10，0.5 步进；外部基准支撑 WB 宏观指标 + Tavily 市场情报）。取评分表该维度行前缀分值（R2-F7），证据来源列留档模板不入参
          competitive_strength:
            type: number
            description: 业务实力评分（1-10，0.5 步进；内部数据市场份额/利润率）。取评分表该维度行前缀分值（R2-F7），证据来源列留档模板不入参
output_schema:
  type: object
  required: [portfolio_map, data_sources]
  properties:
    portfolio_map:
      type: object
      description: 业务组合图谱（九宫格定位 + 投资建议）
      required: [grid_position, recommendation]
      properties:
        grid_position:
          type: object
          description: 各业务单元九宫格坐标定位
        recommendation:
          type: string
          description: 投资优先级建议（投资/选择性发展/收割/退出）
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# GE-麦肯锡矩阵

> 行业吸引力（外部）× 业务实力（内部）九宫格业务组合矩阵，输出投资优先级建议。
> 混合数据型工具：内部数据（高管访谈业务单元评分表）是分析主体，外部数据源（World Bank/Tavily）
> 仅提供行业吸引力维度的宏观与市场情报印证基准。

## 1. 适用场景
- 业务组合管理（多业务单元整体盘点与分类治理）
- 投资优先级排序（投资/选择性发展/收割/退出四类决策）
- 资源分配（跨业务单元的资本与人力再平衡）

## 2. 负向触发
- 单业务战略（无组合维度）：请用 swot-tows 或 space-matrix
- 新市场进入决策（产品×市场组合）：请用 ansoff-matrix
- 内部运营成本诊断：请用 value-chain-analysis

## 3. 输入字段（input_schema）

`business_units` 为 array of object（逐业务单元一行），字段表用「容器.字段」表示展开形态：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| business_units | array[object] | ✅ | 业务单元列表（高管访谈评分表采集） |
| business_units[].name | string | ✅ | 业务单元名称 |
| business_units[].industry_attractiveness | number | ✅ | 行业吸引力评分（1-10，0.5 步进；取评分表行前缀分值，证据留档模板） |
| business_units[].competitive_strength | number | ✅ | 业务实力评分（1-10，0.5 步进；取评分表行前缀分值，证据留档模板） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| portfolio_map | object | 业务组合图谱（九宫格定位 + 投资建议） |
| portfolio_map.grid_position | object | 各业务单元九宫格坐标定位 |
| portfolio_map.recommendation | string | 投资优先级建议（投资/选择性发展/收割/退出） |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，高管访谈采集）：** 经 `templates/ge_business_unit_scoresheet.md` 业务单元评分表
由高管访谈现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为
`ToolCall.arguments` 的 `business_units` 数组传入（每业务单元一项：name / 双维评分——评分表中的
证据来源列留档模板与定位依据，不进入 arguments 数值字段）。

**外部基准（印证参照，双源交叉，仅支撑行业吸引力维度）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业宏观基本面（市场规模/增速的宏观锚定） | world-bank | 点分指标码 + 国家代码（如 "NY.GDP.MKTP.CD;CHN"、"NE.GDI.TOTL.ZS;CHN"） |
| 市场情报（行业增速/竞争烈度/新兴需求事件） | tavily | 自然语言关键词（如 "动力电池 行业增速 竞争格局"） |

**内外交叉验证要求：** 每个业务单元的 `industry_attractiveness` 评分须有至少一条外部基准印证
（或显式标注「内部判断，未经外部印证」）；`competitive_strength` 以内部数据为准（外部源不评判内部实力）；
外部情报与内部评分矛盾时的处置见 `references/data_fusion.md`（冲突分级处理：内部漏判 → 外部基准
优先补正；外部无印证 → 双方并列不下结论；方向相反 → 暂停判断，以最新一手内部数据为准复议）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `business_units`（内部数据经 Think prompt 进入分析上下文——
   评分表采集的成果在此参与推理）
2. Think 阶段：规划双维评分校准与九宫格定位的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
macro = $DATA_SOURCE("world-bank", "NY.GDP.MKTP.CD;CHN")
web = $DATA_SOURCE("tavily", "动力电池 行业增速 竞争格局 新兴需求")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
macro_payload = (DATA_SOURCES.get("world-bank") or {}).get("payload")
web_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部评分（arguments）与外部基准（DATA_SOURCES）校准行业吸引力，
   按锚点（`references/scoring_anchors.md`）完成九宫格定位
6. Validate 阶段：校验组合图谱完备性（全部业务单元坐标 + 投资建议 + 溯源元数据）
7. 输出 `portfolio_map` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；
**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；
标记数据源名必须在 frontmatter 白名单内（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部评分 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（Tavily API Key 缺失，`os.environ['TAVILY_API_KEY']` 未配置） | 411 | **Key 敏感降级**：GE 内部评分是分析主体——基于高管访谈评分表完成九宫格定位与投资建议，行业吸引力标注「未经外部印证的数据缺口」，建议配置 Key 后重跑 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（business_units 缺失/评分空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办高管访谈采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "business_units": [
    {
      "name": "动力电池单元",
      "industry_attractiveness": 8.5,
      "competitive_strength": 6.0
    },
    {
      "name": "消费电池单元",
      "industry_attractiveness": 4.5,
      "competitive_strength": 8.0
    }
  ]
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
macro = $DATA_SOURCE("world-bank", "NY.GDP.MKTP.CD;CHN")
web = $DATA_SOURCE("tavily", "动力电池 行业增速 竞争格局")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（评分校准流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — 行业吸引力/业务实力 1-10 评分锚点（每档含义 + 正反例 + 聚合规则）
- `references/workshop_guide.md` — 高管访谈引导（会前准备/访谈流程/角色分工/纪律/跟进）
- `templates/ge_business_unit_scoresheet.md` — 业务单元评分表（字段与 input_schema 一一对应，访谈现场填写）
