---
slug: bsc-scorecard
name: BSC 平衡计分卡
version: 1.0.0
tool_name: BSC 平衡计分卡
description: Kaplan/Norton 平衡计分卡（4 视角 KPI 设计）
when_to_use:
  - 战略执行评估
  - KPI 设计
  - 绩效管理
when_not_to_use:
  - 战略选择
capabilities:
  - performance_management
  - kpi_design
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - kpi
data_sources:
  - name: china-nbs
    url: https://www.stats.gov.cn
    api_type: crawler
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
  - name: world-bank
    url: https://api.worldbank.org/v2
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required: [strategic_objectives]
  properties:
    strategic_objectives:
      type: object
      description: 战略目标（高管工作坊采集：四维度目标/KPI 现值，模板 bsc_kpi_scorecard.md）
      required: [financial, customer, internal_process, learning_growth]
      properties:
        financial:
          type: array
          description: 财务维度目标与 KPI 现值
          items:
            type: string
        customer:
          type: array
          description: 客户维度目标与 KPI 现值
          items:
            type: string
        internal_process:
          type: array
          description: 内部流程维度目标与 KPI 现值
          items:
            type: string
        learning_growth:
          type: array
          description: 学习成长维度目标与 KPI 现值
          items:
            type: string
output_schema:
  type: object
  required: [bsc_metrics, data_sources]
  properties:
    bsc_metrics:
      type: object
      description: BSC 指标体系（KPI/目标值/权重/行动计划）
      required: [kpi_indicators, target_values, weights, action_plans]
      properties:
        kpi_indicators:
          type: array
          description: KPI 指标清单（含因果链假设）
          items:
            type: string
        target_values:
          type: object
          description: 目标值（KPI → 目标，行业统计对标参照）
        weights:
          type: object
          description: 权重分配（维度/指标 → 权重）
        action_plans:
          type: array
          description: 行动计划清单
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# BSC 平衡计分卡

> Kaplan/Norton 四视角平衡计分卡：财务/客户/内部流程/学习成长四维度 KPI 体系 +
> 因果链假设 + 行动计划。混合数据型工具：内部数据（战略规划要点 + KPI 现值，高管工作坊采集）
> 是设计主体，外部数据源（国家统计局/World Bank）仅提供财务维度的行业与宏观对标基准。

## 1. 适用场景
- 战略执行评估（四维度 KPI 体系设计）
- 战略目标逐层分解（目标 → 指标 → 目标值 → 行动计划）
- 绩效管理（跨维度权重分配与因果链校验）

## 2. 负向触发
- 战略选择（多战略方案比选）：请用 swot-tows 或 space-matrix
- 增长路径决策（产品 × 市场四象限）：请用 ansoff-matrix
- 单一 KPI 分解树（不含四维度因果假设）：请用 kpi-tree

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| strategic_objectives | object | ✅ | 战略目标（高管工作坊采集） |
| strategic_objectives.financial | array[string] | ✅ | 财务维度目标与 KPI 现值 |
| strategic_objectives.customer | array[string] | ✅ | 客户维度目标与 KPI 现值 |
| strategic_objectives.internal_process | array[string] | ✅ | 内部流程维度目标与 KPI 现值 |
| strategic_objectives.learning_growth | array[string] | ✅ | 学习成长维度目标与 KPI 现值 |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| bsc_metrics | object | BSC 指标体系（KPI/目标值/权重/行动计划） |
| bsc_metrics.kpi_indicators | array[string] | KPI 指标清单（含因果链假设） |
| bsc_metrics.target_values | object | 目标值（KPI → 目标，行业统计对标参照） |
| bsc_metrics.weights | object | 权重分配（维度/指标 → 权重） |
| bsc_metrics.action_plans | array[string] | 行动计划清单 |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（设计主体，高管工作坊采集）：** 经 `templates/bsc_kpi_scorecard.md` 在高管工作坊采集四维度战略目标、KPI 现值与战略规划文件要点（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 的 `strategic_objectives` 传入（每条格式建议「目标：KPI = 现值（期间）」）。

**外部基准（仅财务维度对标，双源交叉）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业财务统计对标（行业营收/成本/薪酬水平） | china-nbs | 站点相对路径（如 "sj/zxfb" 最新发布 / "sj/hyf" 分行业数据） |
| 宏观增长与利率环境（目标值合理性参照） | world-bank | 点分指标码 + 国家代码（如 "NY.GDP.MKTP.KD.ZG;CHN" / "FR.INR.RINR;CHN"） |

**内外交叉验证要求：** 仅财务维度 KPI 目标值对照行业/宏观基准校准（偏离基准需给出份额/结构内部依据）；客户/内部流程/学习成长三维度以历史值/目标值为基准，**禁止伪造外部对标**；粒度边界见 `references/data_fusion.md`（冲突处理：外部基准优先修正内部目标值，修正前双方并列呈现）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `strategic_objectives`（内部数据经 Think prompt 进入分析上下文——工作坊采集的成果在此参与推理）
2. Think 阶段：规划四维度 KPI 体系设计与财务维度外部对标步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
nbs = $DATA_SOURCE("china-nbs", "sj/zxfb")
macro = $DATA_SOURCE("world-bank", "NY.GDP.MKTP.KD.ZG;CHN;2021:2030")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
nbs_payload = (DATA_SOURCES.get("china-nbs") or {}).get("payload")
wb_payload = (DATA_SOURCES.get("world-bank") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（四维度目标/现值）与外部基准（仅财务维度）设计 KPI 体系、目标档位与因果链假设
6. Validate 阶段：校验计分卡完备性（KPI/目标值/权重/行动计划 + 溯源元数据 + 因果链闭合）
7. 输出 `bsc_metrics` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部四维度数据继续设计，财务对标标注数据缺口 |
| china-nbs 爬虫源不可用（crawler 连接失败/反爬拦截/页面改版） | 411 | 行业对标降级：改用 world-bank 宏观基准粗粒度参照 + 内部历史值基准，标注「行业统计对标缺口」 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败（指标码不存在/页面结构变化） | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（维度缺失/KPI 现值空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办高管工作坊采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "strategic_objectives": {
    "financial": ["营收增长：年营收 = 4.2 亿元（2026 实际）", "盈利改善：毛利率 = 31%（2026 实际）"],
    "customer": ["客户留存：大客户续约率 = 78%（2026 实际）", "客户拓展：新行业客户数 = 6 家（2026 实际）"],
    "internal_process": ["交付提效：准时交付率 = 85%（2026 实际）", "质量提升：批次不良率 = 3.2%（2026 实际）"],
    "learning_growth": ["人才储备：关键岗位任职率 = 82%（2026 实际）", "能力建设：年度人均培训 = 24 学时（2026 实际）"]
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
industry = $DATA_SOURCE("china-nbs", "sj/hyf")
macro = $DATA_SOURCE("world-bank", "FR.INR.RINR;CHN")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/对标粒度边界）
- `references/scoring_anchors.md` — KPI 目标档位锚点（保守/基准/挑战，每档含义 + 正反例）
- `references/workshop_guide.md` — 高管工作坊 2-4 小时引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/bsc_kpi_scorecard.md` — 四维度 KPI 计分卡（字段与 input_schema 一一对应，工作坊现场填写）
