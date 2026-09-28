# SPACE 四维度因子评分表

> 问卷打分 + 专家访谈现场填写；采集字段与 SKILL.md `input_schema` 一一对应
>（战略因素为嵌套分区，分区内字段即 Schema 叶子键）。评分刻度见 `references/scoring_anchors.md`。

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 目标企业/业务单元名称 |
| 分析期间 | 如 2026-2030 战略周期 |
| 工作坊日期 | 填写日期 |
| 引导者/记录员 | 名字 |

## 采集表格

### strategic_factors

| 字段 | 维度分与因子明细 | 证据来源 |
| --- | --- | --- |
| financial_strength（必填） | +5.2 —— 现金流 +6（连续 8 季为正）/ 负债率 +5（28%）/ ROE +4（13%）均分 | 三年财务报表 |
| competitive_advantage（必填） | -3.4 —— 市场份额 -3（12%）/ 成本位 -4（高于龙头 8%）/ 客户黏性 -3 均分 | 竞争复盘 + 拆解报告 |
| industry_strength（必填） | +5.8 —— 需求增速 +6 / 盈利性 +5 / 产能利用 +6 均分（预评，待 IMF 校准） | 行业研究笔记 |
| environmental_stability（必填） | -2.6 —— 通胀 -2（CPI 2.3%）/ 政策连续性 -3 / 技术变革 -3 均分（预评，待 WB 校准） | 政策梳理纪要 |

> 每行一个维度的聚合分与因子明细（因子分 1-7：FS/IS 正值、CA/ES 负值），
> 维度分 = 因子均分；IS/ES 两行在外部基准校准后更新。

## 评分锚点

评分刻度（1-7，SPACE 惯例）与每档判定标准、正反例锚点见 `references/scoring_anchors.md`；
IS/ES 外部校准规则见 `references/data_fusion.md`。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
| industry_strength | 细分行业产能利用率数据缺口 | 外部 Agent 采集印证 / 行业协会统计 |
| environmental_stability | 技术变革速率定量数据缺口 | 技术情报服务 / 专利检索 |
