# 商业模式画布工作坊引导（2-4 小时结构化）

> 纯内部框架型工作坊：无外部数据采集环节，以用户结构化输入工作坊替代——
> 全部判断基于内部业务事实的现场对齐（可携客诉台账/成本表等内部材料佐证）。

## 会前准备（T-3 天）

| 时点 | 动作 | 产出 |
| --- | --- | --- |
| T-3 天 | 分发 `templates/bmc_nine_blocks_canvas.md` 与 `references/canvas_template.json` 骨架给业务专家 | 各自预填草稿（不汇总，防锚定） |
| T-2 天 | 收集内部材料：客户台账、渠道协议摘要、成本结构表、伙伴协议清单 | 材料清单 |
| T-1 天 | 引导者汇总九块现状速览（标题级，不预判成熟度） | 速览页 |

## 现场流程（2-4 小时）

| 环节 | 时长 | 产出物 |
| --- | --- | --- |
| 开场与规则宣讲 | 15 min | 纪律共识（防锚定/防从众） |
| 客户侧四块评审（细分/主张/渠道/关系） | 60 min | customer_segments / value_propositions / channels / customer_relationships 清单 + 分值 |
| 供给侧三块评审（业务/资源/伙伴） | 45 min | key_activities / key_resources / key_partnerships 清单 + 分值 |
| 双侧核算（收入/成本） | 30 min | revenue_streams / cost_structure + 成本-收入对照 |
| 块间一致性与缺口登记 | 30 min | 模板定稿（含缺口登记区） |

## 时间压缩指引（2 小时精简变体）

| 环节（精简版） | 时长 | 说明 |
| --- | --- | --- |
| 开场与规则宣讲 | 15 min | 纪律宣讲不可压缩 |
| 客户侧四块连续评审 | 45 min | 每块条目上限 3 条 |
| 供给侧三块连续评审 | 30 min | 每块条目上限 3 条 |
| 双侧核算与缺口登记 | 30 min | 成本-收入对照不可省 |

- **压缩代价**：条目深度下降，被裁条目转入缺口登记区会后补齐
- **不可压缩项**：核心匹配检验（value_propositions ↔ customer_segments）、
  成本-收入对称检验、缺口登记——省略即失效

## 角色分工

- **引导者**：控流程/控时/执行纪律，不参与内容判断
- **业务专家**（2-4 人，跨职能：市场/产品/供应链/财务）：条目提出与评分主体
- **记录员**：实时填写模板表格，逐条登记证据与缺口

## 引导纪律

- **防锚定**：预填草稿开场后才同时公开；客户细分先于价值主张评审（起点锚定）
- **防从众**：分值采用先独立举牌后讨论收敛；职级不参与评分权重
- **防溢出**：单条目讨论超 5 分钟即登记「待议」移入缺口登记区
- 每条目必须落到模板行（字段/分值与描述/证据三列齐全才算完成）

## 会后跟进

1. 记录员 24h 内回收定稿模板，补齐缺口登记区的替代来源
2. 按模板「采集表格」字段构造 `ToolCall.arguments` 参数（模板→arguments 构造闭环）：
   `business_model.{customer_segments, value_propositions, channels, customer_relationships,
   revenue_streams, key_resources, key_activities, key_partnerships, cost_structure}`
   （每条携带分值与描述，cost_structure 为成本项名→说明映射）
3. 调用本 Skill 执行：Agent 基于框架逻辑生成 canvas_assessment
   （dimension_scores 九块聚合 + consistency_analysis 双侧对照）
4. 结果回传业务专家确认（重点：核心匹配缺口与成本-收入失衡项的处置）
