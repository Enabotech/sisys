# 战略地图因果链采集表

> 工作坊现场填写；采集字段与 SKILL.md `input_schema` 一一对应（bsc_indicators
> 为嵌套分区，分区内字段即 Schema 叶子键）。因果箭头语法与方向校验见
> `references/validation_rules.md`。

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 企业/业务单元名称 |
| 战略周期 | 如 2026-2030 |
| 工作坊日期 | 填写日期 |
| 引导者/记录员 | 名字 |

## 采集表格

### bsc_indicators

| 字段 | 指标陈述 | 证据来源 |
| --- | --- | --- |
| learning_growth（必填） | 一线数字化技能覆盖率 = 45% | 人才盘点报告 2026-H1 |
| learning_growth（必填） | 关键岗位继任者就绪率 = 38% | 人才盘点报告 2026-H1 |

> learning_growth 逐条一行（每行一条指标，指标名与现状量级），下行示例可替换。

| 字段 | 指标陈述 | 证据来源 |
| --- | --- | --- |
| internal_process（必填） | 订单处理周期 = 5.2 天 | 流程绩效月报 |
| internal_process（必填） | 一次交付合格率 = 91% | 质量台账 |

| 字段 | 指标陈述 | 证据来源 |
| --- | --- | --- |
| customer（必填） | 客户满意度 NPS = 32 | 客户调研 2026-Q2 |
| customer（必填） | 大客户续约率 = 78% | CRM 系统 |

| 字段 | 指标陈述 | 证据来源 |
| --- | --- | --- |
| financial（必填） | 营业收入 = 4.2 亿元，年增 12% | 财务报表 2025 |
| financial（必填） | 毛利率 = 21% | 财务报表 2025 |

| 字段 | 因果箭头（原因维度 → 结果维度：假设描述） | 证据来源 |
| --- | --- | --- |
| causal_relationships（必填） | learning_growth → internal_process：一线数字化技能提升缩短订单处理周期 | 运营复盘纪要 |
| causal_relationships（必填） | internal_process → customer：订单处理周期缩短提升大客户续约率 | 客户流失分析 |
| causal_relationships（必填） | customer → financial：大客户续约率提升带动营业收入增长 | 财务归因分析 |

## 校验规则

因果箭头语法正则、闭合校验与 Kaplan-Norton 标准方向（自下而上
learning_growth → internal_process → customer → financial）等规则见
`references/validation_rules.md`；四层因果思考步骤与 bsc-scorecard
互查映射见 `references/framework_logic.md`。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
| learning_growth | 数字化技能覆盖率统计口径未统一 | 人事系统培训记录 / 现场抽测 |
| causal_relationships | 客户维度到财务维度的传导弹性未验证 | 财务归因分析（会后补） |
