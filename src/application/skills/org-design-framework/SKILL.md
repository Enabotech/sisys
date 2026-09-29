---
slug: org-design-framework
name: 组织设计框架
version: 1.0.0
tool_name: 组织设计框架
description: Galbraith 星形模型（战略/结构/流程/奖励/人员）
when_to_use:
  - 组织架构设计
  - 战略落地
  - 组织变革
when_not_to_use:
  - 个人绩效评估
capabilities:
  - org_design
  - org_transformation
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - organization
input_schema:
  type: object
  required: [org_structure]
  properties:
    org_structure:
      type: object
      description: 组织架构数据（历史根键，扩展后承载 Galbraith Star Model 全五维——structure 维由本容器三字段承载，strategy/processes/rewards/people 四维由子容器承载）。条目编码：维度对齐度分值（1-5）—— 条目描述（分值 = 首个『 —— 』之前前缀中的独立 1-5 整数，前缀不得含其它数字）
      required: [functions, reporting_lines, decentralization_level, strategy, processes, rewards, people]
      properties:
        functions:
          type: array
          description: 职能清单（structure 维）
          items:
            type: string
        reporting_lines:
          type: array
          description: 汇报线清单（structure 维）
          items:
            type: string
        decentralization_level:
          type: string
          description: 分权程度定性描述（structure 维——如高度集权/中度分权/高度分权）
        strategy:
          type: object
          description: 战略维（方向陈述）
          required: [statements]
          properties:
            statements:
              type: array
              description: 战略方向陈述清单（业务范围/竞争优势来源/里程碑）
              items:
                type: string
        processes:
          type: object
          description: 流程维
          required: [core_processes]
          properties:
            core_processes:
              type: array
              description: 核心流程清单（集成流/管理流）
              items:
                type: string
        rewards:
          type: object
          description: 奖励维
          required: [incentive_policies]
          properties:
            incentive_policies:
              type: array
              description: 激励政策清单（薪酬/晋升/认可）
              items:
                type: string
        people:
          type: object
          description: 人员维
          required: [talent_measures]
          properties:
            talent_measures:
              type: array
              description: 人才举措清单（人才标准/培养/招聘）
              items:
                type: string
output_schema:
  type: object
  required: [design_recommendation]
  properties:
    design_recommendation:
      type: object
      description: 组织设计建议
      required: [fit_assessment, optimization_suggestions]
      properties:
        fit_assessment:
          type: object
          description: 五维对齐度评估（外层键为维度名，值为对齐度分值与依据——自由 object，4.3 defer；与 value-proposition-canvas 输出根 fit_assessment 同名异构，互查时防混淆）
        optimization_suggestions:
          type: array
          description: 组织优化建议清单（维度失配处的调整方向）
          items:
            type: string
---

# 组织设计框架

> Galbraith Star Model 五维对齐评估：战略（strategy）/ 结构（structure）/ 流程
> （processes）/ 奖励（rewards）/ 人员（people）。纯内部框架型工具：分析主体是
> 用户输入的组织内部信息（经 `ToolCall.arguments` 进入 Think prompt 主通道），
> 不依赖任何外部数据源。

## 1. 适用场景
- 组织架构设计（新业务单元/区域扩张的组织形态决策）
- 战略落地（战略与组织五维的一致性校验）
- 组织变革（维度失配诊断与调整优先级）

## 2. 负向触发
- 角色职责分配（任务×角色矩阵）：请用 raci-matrix
- 业务活动分析（主活动/支持活动价值链）：请用 value-chain-analysis
- 个人绩效评估（个体考核指标）：超出组织设计范畴

## 3. 输入字段（input_schema）

> 名实注记：`org_structure` 为历史根键，扩展后承载 Galbraith Star Model 全五维——
> structure 维由本容器三字段（functions/reporting_lines/decentralization_level）承载，
> strategy/processes/rewards/people 四维由子容器承载。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| org_structure | object | ✅ | 组织架构数据（条目编码：维度对齐度分值（1-5）—— 条目描述） |
| org_structure.functions | array[string] | ✅ | 职能清单（structure 维） |
| org_structure.reporting_lines | array[string] | ✅ | 汇报线清单（structure 维） |
| org_structure.decentralization_level | string | ✅ | 分权程度定性描述（高度集权/中度分权/高度分权） |
| org_structure.strategy.statements | array[string] | ✅ | 战略方向陈述清单（strategy 维——条目分值 = 陈述完备性，见 scoring_anchors.md 刻度声明） |
| org_structure.processes.core_processes | array[string] | ✅ | 核心流程清单（processes 维） |
| org_structure.rewards.incentive_policies | array[string] | ✅ | 激励政策清单（rewards 维） |
| org_structure.people.talent_measures | array[string] | ✅ | 人才举措清单（people 维） |

分值解析锚点：每条目分值 = 首个『 —— 』之前前缀中的独立 1-5 整数（前缀不得含其它数字，防「P1 —— 4」误判）；decentralization_level 为定性描述单值，不打分。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| design_recommendation | object | 组织设计建议 |
| design_recommendation.fit_assessment | object | 五维对齐度评估（维度名 → 分值与依据） |
| design_recommendation.optimization_suggestions | array[string] | 组织优化建议清单（维度失配处的调整方向） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/org_star_model_assessment.md` 五维采集表在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键 `org_structure`（三字段 + 四子容器各一叶子，共 7 个采集字段），构造示例见 §8。

**五维采集引导：** structure 维（functions 职能/reporting_lines 汇报线/decentralization_level 分权程度）→ strategy 维（statements）→ processes 维（core_processes）→ rewards 维（incentive_policies）→ people 维（talent_measures）；逐维评维度对齐度分值（1-5——strategy 维条目分值 = 陈述完备性，见 `references/scoring_anchors.md` 刻度声明），对齐逻辑见 `references/framework_logic.md`。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `org_structure`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划五维对齐评估的执行步骤（逐维评估 + 维度间对齐检查）
3. Code 阶段：生成分析代码（纯内部数据直算——解析条目分值前缀，逐维聚合对齐度）
4. Execute 阶段：沙箱执行（纯内部型无外部采集，代码不含任何 `$DATA_SOURCE` 标记）
5. Observe 阶段：结合五维条目完成维度间交叉印证（战略-结构/流程-奖励-人员联动）
6. Validate 阶段：校验输出完备性（fit_assessment 五维齐备 + optimization_suggestions 非空）
7. 输出 `design_recommendation`（fit_assessment 五维对齐 + 失配调整建议）

**编码解析规范：** 分析代码以「首个『 —— 』之前前缀中的独立 1-5 整数」解析条目分值（前缀含其它数字即判格式违规，登记数据缺口）；五维系统化思考步骤见 `references/framework_logic.md`。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 内部数据不足（模板字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |

## 8. input_examples

```json
{
  "org_structure": {
    "functions": ["4 —— 区域销售职能（含大客户拓展）", "3 —— 集中采购职能"],
    "reporting_lines": ["4 —— 区域总经理向销售副总裁汇报", "2 —— 采购经理向区域总经理汇报"],
    "decentralization_level": "中度分权（区域有定价权，预算集权）",
    "strategy": {"statements": ["5 —— 聚焦区域企业客户市场（业务范围），以本地化服务网络构筑竞争优势（竞争优势来源），三年内市场份额进入前三（里程碑）"]},
    "processes": {"core_processes": ["3 —— 区域订单履约流程"]},
    "rewards": {"incentive_policies": ["4 —— 区域利润分享计划"]},
    "people": {"talent_measures": ["2 —— 区域销售认证培训"]}
  }
}
```

## 9. References 指引

- `references/framework_logic.md` — Galbraith 五维对齐系统化思考（编号步骤 + 维度间对齐检查 + 填写指引）
- `references/scoring_anchors.md` — 维度对齐度 1-5 评分锚点（刻度声明 + 分档含义 + 正例与反例）
- `references/workshop_guide.md` — 组织设计工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/org_star_model_assessment.md` — 五维采集表（字段与 input_schema 一一对应，工作坊现场填写）
