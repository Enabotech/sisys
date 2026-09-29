---
slug: value-curve-analysis
name: 价值曲线分析
version: 1.0.0
tool_name: 价值曲线分析
description: W. Chan Kim 价值曲线（行业竞争因素可视化）
when_to_use:
  - 蓝海战略识别
  - 价值创新机会
  - 竞争差异化
when_not_to_use:
  - 运营效率提升
capabilities:
  - value_innovation
  - blue_ocean
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - differentiation
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
input_schema:
  type: object
  required: [competition_data]
  properties:
    competition_data:
      type: object
      description: 竞争数据（客户调研 + 竞品情报，模板 value_curve_factors_grid.md）。条目编码——competitors 逐条「竞品名 —— 关注理由」（关注理由 = 首个『 —— 』后的文本）；value_factors 键值形态「要素名 → 当前/目标水平（各 1-5，对象键为 当前/目标）」（证据来源留档模板不入参）
      required: [competitors, value_factors]
      properties:
        competitors:
          type: array
          description: 竞品清单（行业战略轮廓绘制对象）
          items:
            type: string
        value_factors:
          type: object
          description: 价值要素水平（要素名 → 我方当前水平/目标值，三列网格采集）
output_schema:
  type: object
  required: [value_curve, data_sources]
  properties:
    value_curve:
      type: object
      description: 价值曲线分析结果（行业轮廓 + 四行动框架）
      required: [curves, innovation_opportunities]
      properties:
        curves:
          type: object
          description: 各主体价值曲线（行业/竞品/我方当前/我方目标）
        innovation_opportunities:
          type: array
          description: 消除-减少-增加-创造四行动机会点
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 价值曲线分析

> W. Chan Kim 价值曲线：以行业竞争要素为横轴、投入/水平为纵轴，绘制行业战略轮廓与「我方当前/目标」双曲线，
> 通过消除-减少-增加-创造（ERRC）四行动重构价值要素，迈向蓝海。
> 混合数据型工具：内部数据（客户调研采集的价值要素网格）是分析主体，外部数据源（Tavily/NewsAPI）仅提供
> 竞品要素情报与市场动态的外部印证基准。

## 1. 适用场景
- 蓝海战略识别（行业竞争要素重构与新价值曲线设计）
- 价值创新机会挖掘（消除-减少-增加-创造四行动框架）
- 竞争差异化定位（相对行业战略轮廓的曲线形态决策）

## 2. 负向触发
- 运营效率提升（流程瓶颈诊断）：请用 value-chain-analysis
- 内部资源/能力逐项竞争优势核查：请用 vrio-framework
- 竞争态势量化评分（CA/ES/IS/FS 四维坐标）：请用 space-matrix

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| competition_data | object | ✅ | 竞争数据（客户调研 + 竞品情报；条目编码见下两行） |
| competition_data.competitors | array[string] | ✅ | 竞品清单（逐条「竞品名 —— 关注理由」） |
| competition_data.value_factors | object | ✅ | 价值要素水平（要素名 → {当前: 1-5, 目标: 1-5}，证据留档模板） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| value_curve | object | 价值曲线分析结果（行业轮廓 + 四行动框架） |
| value_curve.curves | object | 各主体价值曲线（行业/竞品/我方当前/我方目标） |
| value_curve.innovation_opportunities | array[string] | 消除-减少-增加-创造四行动机会点 |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，客户调研 + 三列网格采集）：** 经 `templates/value_curve_factors_grid.md` 三列网格
（价值要素 / 我方当前水平 / 我方目标值）在客户调研与工作坊现场填写（会前 T-3 天分发客户调研问卷与预填指引，
见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 的 `competition_data` 传入
（competitors = 行业战略轮廓绘制对象清单，value_factors = 逐要素当前/目标水平）。

**外部基准（印证参照，双源交叉）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 竞品价值要素情报（竞品各要素投入/定价/服务水平） | tavily | 自然语言关键词（竞品水平定位优先在 query 中点名竞品——input competitors 传入时按竞品逐家采集，如 "华为 Watch 续航 定价"；同源逐竞品多 query 依次命名 name/name#2） |
| 市场动态（要素偏好迁移/新品发布/价格战） | newsapi | 自然语言关键词（如 "智能手表 血压监测 上市"） |

**内外交叉验证要求：** 每个价值要素的行业/竞品水平定位至少有一条外部基准印证（或显式标注「内部认知，未经外部**同源多 query（name/name#2 键）不构成独立来源**——「至少一条外部基准印证」须来自不同源。
印证」）；竞品要素情报与内部调研认知矛盾时的处置见 `references/data_fusion.md`（冲突分级处理：内部漏判 →
外部基准优先补正；外部无印证 → 双方并列不下结论；方向相反 → 暂停判断，以最新一手内部数据为准复议）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `competition_data`（内部数据经 Think prompt 进入分析上下文——模板采集的
   价值要素网格在此参与推理）
2. Think 阶段：规划行业战略轮廓绘制与四行动框架的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
web = $DATA_SOURCE("tavily", "智能手表 健康监测 续航 定价 竞品对比")
news = $DATA_SOURCE("newsapi", "智能手表 血压监测 新品上市")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
web_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
news_payload = (DATA_SOURCES.get("newsapi") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（价值要素网格）与外部基准（DATA_SOURCES）绘制行业/竞品/我方当前曲线，
   识别曲线形态分化点
6. Validate 阶段：校验曲线完备性（四主体曲线 + 四行动机会点 + 溯源元数据）
7. 输出 `value_curve`（含我方目标曲线 + ERRC 四行动机会点）+ `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的沙箱内
网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内（207 策略违规）。每源采集结果量以适配器默认分页为准（SOP 引导代码不得显式请求超量数据）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（Tavily/NewsAPI API Key 缺失，`TAVILY_API_KEY`/`NEWSAPI_API_KEY` 未配置） | 411 | **双 Key 敏感降级**：价值要素网格（客户调研）是分析主体——基于内部当前/目标水平完成我方双曲线与 ERRC 四行动框架，行业/竞品轮廓标注「未经外部印证的数据缺口」，建议配置 Key 后重跑 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（价值要素网格缺失/要素少于 3 项） | — | 状态置 `INSUFFICIENT_DATA`，引导补办客户调研采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "competition_data": {
    "competitors": ["华为 Watch GT 系列 —— 行业健康要素押注代表", "小米手环 Pro —— 价格带锚点主体", "Apple Watch Series —— 生态互联标杆"],
    "value_factors": {
      "价格竞争力": {"当前": 3, "目标": 4},
      "健康监测精度": {"当前": 2, "目标": 5},
      "续航能力": {"当前": 4, "目标": 4},
      "生态互联": {"当前": 2, "目标": 3}
    }
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
web = $DATA_SOURCE("tavily", "智能手表 健康监测 精度 评测 对比")
news = $DATA_SOURCE("newsapi", "智能手表 血压监测 上市 2026")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — 价值要素水平 1-5 评分锚点（每档含义 + 正反例）
- `references/workshop_guide.md` — 客户调研与价值曲线工作坊 2-4 小时引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/value_curve_factors_grid.md` — 价值要素三列网格（字段与 input_schema 一一对应，调研现场填写）
