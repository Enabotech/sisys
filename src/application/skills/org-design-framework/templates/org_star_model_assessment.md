# 组织设计五维采集表（Galbraith Star Model）

> 工作坊现场填写；采集字段与 SKILL.md `input_schema` 一一对应（org_structure
> 单分区承载五维——structure 维三字段 + 四维子容器叶子）。对齐度评分标准见
> `references/scoring_anchors.md`。

## 基本信息

| 字段 | 说明 |
| --- | --- |
| 分析对象 | 组织/业务单元名称 |
| 战略周期 | 如 2026-2028 |
| 工作坊日期 | 填写日期 |
| 引导者/记录员 | 名字 |

## 采集表格

### org_structure

| 字段 | 对齐度（1-5）与描述 | 依据 |
| --- | --- | --- |
| functions（必填） | 4 —— 区域销售职能（含大客户拓展） | 组织架构图 2026-Q2 |
| functions（必填） | 3 —— 集中采购职能 | 制度文件 |

> functions 逐条一行（每行一条职能，对齐度分值），下行示例可替换。

| 字段 | 对齐度（1-5）与描述 | 依据 |
| --- | --- | --- |
| reporting_lines（必填） | 4 —— 区域总经理向销售副总裁汇报 | 组织架构图 |
| reporting_lines（必填） | 2 —— 采购经理向区域总经理汇报 | 组织架构图 |

| 字段 | 分权程度定性描述 | 依据 |
| --- | --- | --- |
| decentralization_level（必填） | 中度分权（区域有定价权，预算集权） | 授权管理制度 |

| 字段 | 对齐度（1-5）与描述 | 依据 |
| --- | --- | --- |
| statements（必填） | 5 —— 三年内区域市场份额进入前三 | 战略规划文档 |

| 字段 | 对齐度（1-5）与描述 | 依据 |
| --- | --- | --- |
| core_processes（必填） | 3 —— 区域订单履约流程 | 流程手册 |

| 字段 | 对齐度（1-5）与描述 | 依据 |
| --- | --- | --- |
| incentive_policies（必填） | 3 —— 区域利润分享计划 | 薪酬制度 |

| 字段 | 对齐度（1-5）与描述 | 依据 |
| --- | --- | --- |
| talent_measures（必填） | 2 —— 区域销售认证培训 | 培训计划 |

> 字段对应关系：statements 属 strategy 维 / core_processes 属 processes 维 /
> incentive_policies 属 rewards 维 / talent_measures 属 people 维（详见 SKILL.md §3）。

## 评分锚点

维度对齐度刻度（1-5）与每档判定标准、正例与反例锚点见 `references/scoring_anchors.md`；
五维对齐系统化思考步骤见 `references/framework_logic.md`。

## 数据缺口登记

| 字段 | 缺口描述 | 替代来源 |
| --- | --- | --- |
| core_processes | 跨区域协同流程现状未梳理 | 会后流程专项访谈 |
| incentive_policies | 关键岗位激励水平市场对标缺口 | HR 薪酬调研报告 |
