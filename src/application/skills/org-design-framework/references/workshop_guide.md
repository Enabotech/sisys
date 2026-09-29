# 组织设计工作坊引导（2-4 小时结构化）

> 纯内部框架型工作坊：无外部数据采集环节，以用户结构化输入工作坊替代——
> 全部判断基于组织内部信息（战略陈述/结构现状/流程/激励/人才）的现场对齐。

## 会前准备（T-3 天）

| 时点 | 动作 | 产出 |
| --- | --- | --- |
| T-3 天 | 分发 `templates/org_star_model_assessment.md` 与预填指引给业务专家 | 各自预填草稿（不汇总，防锚定） |
| T-2 天 | 收集内部材料：战略规划文档、组织架构图、制度文件、人才盘点表 | 材料清单 |
| T-1 天 | 引导者汇总战略维陈述速览（标题级，不预判对齐） | 速览页 |

## 现场流程（2-4 小时）

| 环节 | 时长 | 产出物 |
| --- | --- | --- |
| 开场与规则宣讲 | 15 min | 纪律共识（战略基准唯一/防锚定） |
| 战略维陈述定稿（strategy.statements） | 30 min | 战略方向陈述清单（对齐基准） |
| 结构维评审（functions/reporting_lines/decentralization_level） | 40 min | structure 维条目 + 对齐度分值 |
| 流程维评审（processes.core_processes） | 30 min | 核心流程清单 + 分值 |
| 奖励维评审（rewards.incentive_policies） | 30 min | 激励政策清单 + 分值 |
| 人员维评审（people.talent_measures） | 30 min | 人才举措清单 + 分值 |
| 五维对齐预演与缺口登记 | 30 min | 模板定稿（含缺口登记区） |

## 时间压缩指引（2 小时精简变体）

| 环节（精简版） | 时长 | 说明 |
| --- | --- | --- |
| 开场与规则宣讲 | 15 min | 纪律宣讲不可压缩 |
| 战略维陈述定稿 | 25 min | 条目上限 3 条 |
| structure + processes 连续评审 | 45 min | structure 三字段连续，条目上限各 3 条 |
| rewards + people 连续评审 | 25 min | 条目上限各 2 条 |
| 对齐预演与缺口登记 | 10 min | 仅核对最低分维度 |

- **压缩代价**：维度内条目深度下降，被裁条目转入缺口登记区会后补齐
- **不可压缩项**：战略基准宣讲、五维逐维评审顺序、缺口登记——省略即失效

## 角色分工

- **引导者**：控流程/控时/执行纪律，不参与内容判断
- **业务专家**（2-5 人，跨战略/HR/运营职能）：条目提出与评分主体
- **记录员**：实时填写模板表格，逐条登记依据与缺口

## 引导纪律

- **战略基准唯一**：全部对齐评分以 strategy.statements 为唯一基准，禁止临时改基准迁就现状
- **防锚定**：预填草稿开场后才同时公开；战略维先于其他四维定稿
- **防从众**：分值采用先独立举牌后讨论收敛；职级不参与评分权重
- **防溢出**：单条目讨论超 5 分钟即登记「待议」移入缺口登记区
- 每条目必须落到模板行（字段/分值与描述/依据三列齐全才算完成）

## 会后跟进

1. 记录员 24h 内回收定稿模板，补齐缺口登记区的替代来源
2. 按模板「采集表格」字段构造 `ToolCall.arguments` 参数（模板→arguments 构造闭环）：
   `org_structure.{functions, reporting_lines, decentralization_level}` +
   四维子容器 `org_structure.{strategy.statements, processes.core_processes,
   rewards.incentive_policies, people.talent_measures}`
   （每条携带对齐度分值与描述，供 Agent 逐维聚合并诊断失配）
3. 调用本 Skill 执行：Agent 基于 Galbraith 五维框架逻辑生成 design_recommendation
4. 结果回传业务专家确认（重点：最低分维度的调整建议与跨维联动失配项）
