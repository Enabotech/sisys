---
slug: ansoff-matrix
name: 安索夫矩阵
version: 1.0.0
tool_name: 安索夫矩阵
description: 产品 × 市场 2×2 增长策略矩阵
when_to_use:
  - 增长策略选择
  - 市场扩张决策
  - 产品组合优化
when_not_to_use:
  - 运营效率分析
capabilities:
  - growth_strategy
  - market_expansion
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - growth
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
input_schema:
  type: object
  required: [market_product_data]
  properties:
    market_product_data:
      type: object
      description: 市场/产品数据（工作坊采集：产品 × 市场现有位置，模板 ansoff_product_market_matrix.md）。条目编码：风险档（低/中/高）—— 条目描述（风险档 = 首个『 —— 』前的枚举词；象限风险判定与外部增速基准交叉依赖风险档解析）
      required: [existing_products, new_products, existing_markets, new_markets]
      properties:
        existing_products:
          type: array
          description: 现有产品清单
          items:
            type: string
        new_products:
          type: array
          description: 拟开发新产品清单
          items:
            type: string
        existing_markets:
          type: array
          description: 现有市场清单
          items:
            type: string
        new_markets:
          type: array
          description: 拟进入新市场清单
          items:
            type: string
output_schema:
  type: object
  required: [growth_strategy, data_sources]
  properties:
    growth_strategy:
      type: object
      description: 增长战略建议（四象限定位 + 风险评估）
      required: [quadrant_position, recommended_strategy, risk_assessment]
      properties:
        quadrant_position:
          type: string
          description: 当前所处象限（市场渗透/市场开发/产品延伸/多样化）
        recommended_strategy:
          type: string
          description: 推荐增长战略
        risk_assessment:
          type: object
          description: 风险等级评估（增长率基准：WB GDP 指标 + IMF WEO 展望对照）
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 安索夫矩阵

> 产品 × 市场 2×2 增长策略矩阵（市场渗透/市场开发/产品延伸/多样化四象限）。
> 混合数据型工具：内部数据（工作坊采集的产品 × 市场现有位置）是分析主体，
> 外部数据源（World Bank/IMF 宏观增长指标）仅提供目标市场增长率参照与风险校准基准。

## 1. 适用场景
- 增长策略选择（四象限路径比较与优先级排序）
- 市场扩张决策（新市场进入的增长性论证）
- 产品组合优化（新产品方向的风险分级）

## 2. 负向触发
- 运营效率分析（流程瓶颈/成本结构诊断）：请用 value-chain-analysis
- 业务组合管理（多业务单元投资优先级）：请用 ge-mckinsey-matrix
- 战略定位与行动评估（四维度坐标定向）：请用 space-matrix

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| market_product_data | object | ✅ | 市场/产品数据（工作坊采集；条目编码：风险档（低/中/高）—— 条目描述） |
| market_product_data.existing_products | array[string] | ✅ | 现有产品清单 |
| market_product_data.new_products | array[string] | ✅ | 拟开发新产品清单 |
| market_product_data.existing_markets | array[string] | ✅ | 现有市场清单 |
| market_product_data.new_markets | array[string] | ✅ | 拟进入新市场清单 |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| growth_strategy | object | 增长战略建议（四象限定位 + 风险评估） |
| growth_strategy.quadrant_position | string | 当前所处象限（市场渗透/市场开发/产品延伸/多样化） |
| growth_strategy.recommended_strategy | string | 推荐增长战略 |
| growth_strategy.risk_assessment | object | 风险等级评估（WB GDP 指标 + IMF WEO 展望对照） |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，工作坊采集）：** 经 `templates/ansoff_product_market_matrix.md` 在战略工作坊现场盘点产品 × 市场四象限现有位置（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 的 `market_product_data` 传入。

**外部基准（增长率参照，双源交叉）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 目标市场 GDP 规模/增长率基准 | world-bank | 点分指标码 + 国家代码（如 "NY.GDP.MKTP.CD" / "NY.GDP.MKTP.KD.ZG;CHN"） |
| 目标市场中长期增长展望 | imf | 大写下划线指标码 + 国家代码（如 "NGDP_RPCH;CHN"） |

**内外交叉验证要求：** 新市场/新产品的增长预期必须对照 WB/IMF 宏观增长率基准（显著高于基准的预期需给出份额/客单内部依据）；宏观指标为国家维度而非行业维度，行业增长率推断的粒度边界见 `references/data_fusion.md`（冲突分级处理：增长预期高于宏观基准 → 并列呈现、风险档保守采用；方向相反（宏观负增长 vs 内部正增长预期）→ 暂停判断列入工作坊复议清单）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `market_product_data`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划四象限定位分析与目标市场增长率基准采集步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
gdp = $DATA_SOURCE("world-bank", "NY.GDP.MKTP.KD.ZG;CHN;2020:2026")
outlook = $DATA_SOURCE("imf", "NGDP_RPCH;CHN")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
wb_payload = (DATA_SOURCES.get("world-bank") or {}).get("payload")
imf_payload = (DATA_SOURCES.get("imf") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（四象限现有位置）与外部基准（目标市场增长率）完成风险等级评估
6. Validate 阶段：校验增长战略完备性（象限定位 + 推荐战略 + 风险评估 + 溯源元数据）
7. 输出 `growth_strategy` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部四象限数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败（指标码不存在/时序缺失） | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（四象限字段缺失/空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办工作坊采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "market_product_data": {
    "existing_products": ["低 —— 智能座舱域控制器 Gen2（已量产配套）", "低 —— 车载中控显示屏（成熟品类）"],
    "new_products": ["中 —— 舱驾一体域控制器 Gen3（技术跨度大）", "中 —— 车载软件订阅服务（商业模式待验证）"],
    "existing_markets": ["低 —— 国内新能源乘用车（在位优势）", "低 —— 国内商用车（渠道成熟）"],
    "new_markets": ["中 —— 东南亚乘用车（宏观增速 5%+ 但渠道待建）", "高 —— 欧洲商用车（认证周期长）"]
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
gdp = $DATA_SOURCE("world-bank", "NY.GDP.MKTP.KD.ZG;IDN;2020:2030")
growth = $DATA_SOURCE("imf", "NGDP_RPCH;VNM")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/宏观指标粒度边界）
- `references/scoring_anchors.md` — 增长路径风险等级锚点（每档含义 + 正反例）
- `references/workshop_guide.md` — 战略工作坊 2-4 小时引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/ansoff_product_market_matrix.md` — 产品 × 市场四象限采集矩阵（字段与 input_schema 一一对应，工作坊现场填写）
