# GE 矩阵业务单元评分表

> 高管访谈现场填写；采集字段与 SKILL.md `input_schema` 一一对应（business_units 为
> array of object 展开形态，分区内字段即 Schema 叶子键）。评分标准见 `references/scoring_anchors.md`。

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 目标企业名称 |
| 组合盘点期间 | 如 2026-2030 战略周期 |
| 访谈日期 | 填写日期 |
| 引导者/记录员 | 名字 |

## 采集表格

### business_units

> 每业务单元两行（吸引力一行 + 实力一行），逐单元一组，下行示例可替换。

| 字段 | 评分（1-10）与描述 | 证据来源 |
| --- | --- | --- |
| name（必填） | 动力电池单元 | 组织架构清单 |
| industry_attractiveness（必填） | 8.5 —— 储能/电动车双轮驱动，需求年增 30%+ | WB 宏观指标 + 行业协会报告 |
| competitive_strength（必填） | 6.0 —— 份额前 3，毛利率与行业中位持平 | 财务报表 2026-Q2 |

| 字段 | 评分（1-10）与描述 | 证据来源 |
| --- | --- | --- |
| name（必填） | 消费电池单元 | 组织架构清单 |
| industry_attractiveness（必填） | 4.5 —— 行业增速与大盘持平，价格战常态化 | 行业统计年鉴 |
| competitive_strength（必填） | 8.0 —— 份额行业第 2，毛利率高于中位 5pct | 财务报表 2026-Q2 |

## 评分锚点

评分刻度（1-10）与每档判定标准、正反例锚点见 `references/scoring_anchors.md`；
外部印证后的评分校准规则见 `references/data_fusion.md`。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
| industry_attractiveness | 分行业增速定量数据缺口（WB 为国家维度） | 行业协会付费报告 / Tavily 情报定性印证 |
| competitive_strength | 相对市场份额口径未统一（含/不含代工） | 第三方渠道监测数据 |
