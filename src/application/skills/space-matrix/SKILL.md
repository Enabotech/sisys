---
slug: space-matrix
name: SPACE 矩阵
version: 1.0.0
tool_name: SPACE 矩阵
description: 战略地位与行动评估矩阵（4 维度 × 2 极）
when_to_use:
  - 战略定位评估
  - 行动方向选择
  - 竞争态势分析
when_not_to_use:
  - 业务组合管理
capabilities:
  - strategic_positioning
  - action_selection
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - positioning
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
  required: [strategic_factors]
  properties:
    strategic_factors:
      type: object
      description: 四维度因子评分（问卷打分 + 专家访谈，模板 space_dimension_scoring.md）
      required: [financial_strength, competitive_advantage, industry_strength, environmental_stability]
      properties:
        financial_strength:
          type: number
          description: FS 财务实力评分（内部数据）
        competitive_advantage:
          type: number
          description: CA 竞争优势评分（内部数据）
        industry_strength:
          type: number
          description: IS 产业实力评分（外部基准：IMF WEO 产业展望）
        environmental_stability:
          type: number
          description: ES 环境稳定性评分（外部基准：WB 治理/通胀指标）
output_schema:
  type: object
  required: [space_positioning, data_sources]
  properties:
    space_positioning:
      type: object
      description: SPACE 定位结果（坐标定向 + 战略姿态）
      required: [position, strategic_posture, recommendations]
      properties:
        position:
          type: string
          description: 坐标定向结果（进取/保守/防御/竞争）
        strategic_posture:
          type: string
          description: 战略姿态描述
        recommendations:
          type: array
          description: 行动建议清单
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# SPACE 矩阵

> 战略地位与行动评估矩阵：FS 财务实力 / CA 竞争优势（内部维度）×
> IS 产业实力 / ES 环境稳定性（外部维度），四维度评分坐标定向战略姿态（进取/保守/防御/竞争）。
> 混合数据型工具：内部评分（问卷打分 + 专家访谈）是分析主体，
> 外部数据源（World Bank/IMF 宏观指标）仅支撑 IS/ES 两外部维度的基准校准。

## 1. 适用场景
- 战略定位评估（四维度坐标定向）
- 行动方向选择（进取/保守/防御/竞争四姿态）
- 竞争态势分析（财务实力与竞争位势联合诊断）

## 2. 负向触发
- 业务组合管理（多业务单元投资优先级）：请用 ge-mckinsey-matrix
- 增长路径选择（产品 × 市场四象限）：请用 ansoff-matrix
- 单一内部能力审计（资源 VRIO 检验）：请用 vrio-framework

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| strategic_factors | object | ✅ | 四维度因子评分（问卷打分 + 专家访谈） |
| strategic_factors.financial_strength | number | ✅ | FS 财务实力评分（内部数据） |
| strategic_factors.competitive_advantage | number | ✅ | CA 竞争优势评分（内部数据） |
| strategic_factors.industry_strength | number | ✅ | IS 产业实力评分（外部基准：IMF WEO 产业展望） |
| strategic_factors.environmental_stability | number | ✅ | ES 环境稳定性评分（外部基准：WB 治理/通胀指标） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| space_positioning | object | SPACE 定位结果（坐标定向 + 战略姿态） |
| space_positioning.position | string | 坐标定向结果（进取/保守/防御/竞争） |
| space_positioning.strategic_posture | string | 战略姿态描述 |
| space_positioning.recommendations | array[string] | 行动建议清单 |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，问卷 + 专家访谈采集）：** 经 `templates/space_dimension_scoring.md` 以问卷打分 + 专家访谈采集四维度因子评分（FS/CA 纯内部维度以工作坊共识为准，IS/ES 先内部预评再经外部基准校准；会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 的 `strategic_factors` 传入（维度分 = 因子均分，SPACE 惯例 1-7 刻度：FS/IS 为正值、CA/ES 为负值）。

**外部基准（IS/ES 维度校准，双源交叉）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| ES 环境稳定性（治理/通胀/宏观波动） | world-bank | 点分指标码 + 国家代码（如 "FP.CPI.TOTL.ZG;CHN" / "CC.EST;CHN"） |
| IS 产业实力（增长展望/需求环境） | imf | 大写下划线指标码 + 国家代码（如 "NGDP_RPCH;CHN" / "PCPIPCH;CHN"） |

**内外交叉验证要求：** IS/ES 评分必须对照 WB/IMF 宏观基准校准（换算档位偏离一档以上需给出内部依据）；FS/CA 为纯内部维度以工作坊共识为准，外部源不评判内部能力；宏观指标为国家维度而非行业维度的粒度边界见 `references/data_fusion.md`（冲突分级处理：方向相反 → 暂停判断列入复议清单；同向幅度存疑 → 双方并列，保守值参与定向；指标缺失 → 沿用内部预评并标注数据缺口）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `strategic_factors`（内部数据经 Think prompt 进入分析上下文——问卷/访谈评分在此参与推理）
2. Think 阶段：规划 IS/ES 外部校准与四维度坐标定向步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
stability = $DATA_SOURCE("world-bank", "FP.CPI.TOTL.ZG;CHN;2021:2026")
outlook = $DATA_SOURCE("imf", "NGDP_RPCH;CHN")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
wb_payload = (DATA_SOURCES.get("world-bank") or {}).get("payload")
imf_payload = (DATA_SOURCES.get("imf") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部评分（FS/CA）与外部基准（IS/ES 校准）计算坐标：x = CA + IS，y = FS + ES
6. Validate 阶段：校验定位完备性（坐标定向 + 战略姿态 + 行动建议 + 溯源元数据）
7. 输出 `space_positioning` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：FS/CA 纯内部维度仍可定向，IS/ES 沿用工作坊预评，输出标注数据缺口 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败（指标码不存在/时序缺失） | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（四维度评分缺失/越界） | — | 状态置 `INSUFFICIENT_DATA`，引导补办问卷/访谈采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "strategic_factors": {
    "financial_strength": 5.0,
    "competitive_advantage": -3.3,
    "industry_strength": 5.7,
    "environmental_stability": -2.7
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
gov = $DATA_SOURCE("world-bank", "CC.EST;CHN;2020:2025")
industry = $DATA_SOURCE("imf", "NGDP_RPCH;CHN")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/宏观指标粒度边界）
- `references/scoring_anchors.md` — SPACE 四维度 1-7 刻度评分锚点（每档含义 + 正反例）
- `references/workshop_guide.md` — 评分工作坊 2-4 小时引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/space_dimension_scoring.md` — 四维度因子评分表（字段与 input_schema 一一对应，问卷/访谈现场填写）
