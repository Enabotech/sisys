---
slug: value-proposition-canvas
name: 价值主张画布
version: 1.0.0
tool_name: 价值主张画布
description: Osterwalder 价值主张画布（客户工作/收益/痛点）
when_to_use:
  - 产品价值定位
  - 客户契合度验证
  - 新业务设计
when_not_to_use:
  - 成本结构分析
capabilities:
  - value_proposition
  - product_market_fit
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - model
  - customer
input_schema:
  type: object
  required: [customer_profile, value_map]
  properties:
    customer_profile:
      type: object
      description: 客户画像（右侧画布三块，工作坊采集，模板 vpc_canvas_matching.md）。条目编码：严重度或重要性分值（1-5）—— 条目描述（分值 = 首个『 —— 』之前前缀中的独立 1-5 整数，前缀不得含其它数字）
      required: [pains, gains, jobs]
      properties:
        pains:
          type: array
          description: 客户痛点清单（pains 打严重度分值——5 为最痛）
          items:
            type: string
        gains:
          type: array
          description: 客户期望收益清单（gains 打重要性分值——5 为最关键）
          items:
            type: string
        jobs:
          type: array
          description: 客户待办任务清单（jobs 打重要性分值——分析起点，jobs→pains→gains 序）
          items:
            type: string
    value_map:
      type: object
      description: 价值图（左侧画布三块，产品侧）。条目编码：匹配强度分值（1-5）—— 条目描述（匹配强度属一对条目语义挂 value_map 侧；分值 = 首个『 —— 』之前前缀中的独立 1-5 整数，前缀不得含其它数字）
      required: [products, pain_relievers, gain_creators]
      properties:
        products:
          type: array
          description: 产品与服务清单（与 jobs 成对匹配）
          items:
            type: string
        pain_relievers:
          type: array
          description: 止痛药清单（与 pains 成对匹配——每条含匹配强度分值）
          items:
            type: string
        gain_creators:
          type: array
          description: 收益创造器清单（与 gains 成对匹配——每条含匹配强度分值）
          items:
            type: string
output_schema:
  type: object
  required: [fit_assessment]
  properties:
    fit_assessment:
      type: object
      description: 匹配度评估（6 块三对匹配）
      required: [fit_score, improvement_suggestions]
      properties:
        fit_score:
          type: number
          description: 整体匹配分值 = 三对匹配分值的最小值（木桶原则——jobs↔products、pains↔pain_relievers、gains↔gain_creators 三对中最低者，1-5）
        improvement_suggestions:
          type: array
          description: 改进建议清单（缺口侧补强方向）
          items:
            type: string
---

# 价值主张画布

> Osterwalder 价值主张画布：客户画像（jobs/pains/gains）× 价值图（products/pain_relievers/gain_creators）
> 6 块双侧匹配评估。纯内部框架型工具：分析主体是用户输入的内部业务信息（经
> `ToolCall.arguments` 进入 Think prompt 主通道），不依赖任何外部数据源。

## 1. 适用场景
- 产品价值定位（价值主张与客户需求的契合度验证）
- 新业务设计（目标客群与价值主张的匹配推演）
- 产品迭代优先级（按匹配缺口排序补强方向）

## 2. 负向触发
- 成本结构分析（九块完整商业模式）：请用 business-model-canvas
- 商业模式整体设计（画布九块联动）：请用 business-model-canvas

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| customer_profile | object | ✅ | 客户画像（条目编码：严重度或重要性分值（1-5）—— 条目描述） |
| customer_profile.pains | array[string] | ✅ | 客户痛点清单（严重度分值——5 为最痛） |
| customer_profile.gains | array[string] | ✅ | 客户期望收益清单（重要性分值——5 为最关键） |
| customer_profile.jobs | array[string] | ✅ | 客户待办任务清单（重要性分值——分析起点） |
| value_map | object | ✅ | 价值图（条目编码：匹配强度分值（1-5）—— 条目描述） |
| value_map.products | array[string] | ✅ | 产品与服务清单（与 jobs 成对匹配） |
| value_map.pain_relievers | array[string] | ✅ | 止痛药清单（与 pains 成对匹配——含匹配强度分值） |
| value_map.gain_creators | array[string] | ✅ | 收益创造器清单（与 gains 成对匹配——含匹配强度分值） |

分值解析锚点：每条目分值 = 首个『 —— 』之前前缀中的独立 1-5 整数（前缀不得含其它数字，防「P1 —— 4」误判）。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| fit_assessment | object | 匹配度评估（6 块三对匹配） |
| fit_assessment.fit_score | number | 整体匹配分值 = 三对匹配分值的最小值（木桶原则，1-5） |
| fit_assessment.improvement_suggestions | array[string] | 改进建议清单（缺口侧补强方向） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/vpc_canvas_matching.md` 双侧采集矩阵在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键两级枚举：`customer_profile`（pains/gains/jobs 三叶子）与 `value_map`（products/pain_relievers/gain_creators 三叶子），构造示例见 §8。

**三对匹配引导（填写顺序 = jobs→pains→gains 序，jobs 为分析起点）：**

| 匹配对 | 客户侧（严重度/重要性） | 产品侧（匹配强度） |
| --- | --- | --- |
| 任务对 | jobs（重要性分值） | products |
| 痛点对 | pains（严重度分值） | pain_relievers |
| 收益对 | gains（重要性分值） | gain_creators |

分值语义（R2-5 裁定）：customer 侧评 pains 严重度 / gains 与 jobs 重要性（客户视角事实），value_map 侧评匹配强度（一对条目语义）；匹配逻辑见 `references/framework_logic.md`。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `customer_profile` / `value_map`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划双侧匹配分析的执行步骤（三对匹配 + 木桶聚合）
3. Code 阶段：生成分析代码（纯内部数据直算——解析条目分值前缀，计算三对匹配分值与最小值聚合）
4. Execute 阶段：沙箱执行（纯内部型无外部采集，代码不含任何 `$DATA_SOURCE` 标记）
5. Observe 阶段：结合双侧条目完成三对匹配印证（缺口侧识别）
6. Validate 阶段：校验输出完备性（fit_score ∈ 1-5 + improvement_suggestions 非空）
7. 输出 `fit_assessment`（fit_score = 三对匹配分值最小值——木桶原则）

**编码解析规范：** 分析代码以「首个『 —— 』之前前缀中的独立 1-5 整数」解析条目分值（前缀含其它数字即判格式违规，登记数据缺口）；系统化思考步骤见 `references/framework_logic.md`。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 内部数据不足（模板字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |

## 8. input_examples

```json
{
  "customer_profile": {
    "jobs": ["5 —— 城际通勤中可靠补能", "3 —— 车队统一充电结算"],
    "pains": ["5 —— 公共快充站充电等待 40 分钟超出接受度", "3 —— 冬季续航衰减达 30%"],
    "gains": ["4 —— 补能时间压缩到一刻钟内", "3 —— 电池残值可评估可交易"]
  },
  "value_map": {
    "products": ["4 —— 800V 高压平台整车产品", "3 —— 车队充电管理 SaaS"],
    "pain_relievers": ["4 —— 800V 高压平台将补能缩短至 12 分钟", "3 —— 热泵热管理降低冬季衰减至 15%"],
    "gain_creators": ["4 —— 超充网络会员权益（补能≤15 分钟）", "2 —— 电池健康度报告与残值评估服务"]
  }
}
```

## 9. References 指引

- `references/framework_logic.md` — 双侧匹配系统化思考（编号步骤 + 三对匹配镜像结构 + fit_score 木桶聚合逻辑 + 填写指引）
- `references/scoring_anchors.md` — 双侧分值 1-5 评分锚点（刻度声明 + 分档含义 + 正例与反例）
- `references/workshop_guide.md` — 价值主张工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/vpc_canvas_matching.md` — 双侧采集矩阵（字段与 input_schema 一一对应，工作坊现场填写）
