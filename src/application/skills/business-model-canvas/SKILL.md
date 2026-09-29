---
slug: business-model-canvas
name: 商业模式画布
version: 1.0.0
tool_name: 商业模式画布
description: Osterwalder 商业模式画布（9 区块完整模型）
when_to_use:
  - 商业模式设计
  - 新业务规划
  - 战略对齐
when_not_to_use:
  - 执行细节规划
capabilities:
  - business_model_design
  - strategic_alignment
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - model
  - business
input_schema:
  type: object
  required: [business_model]
  properties:
    business_model:
      type: object
      description: 商业模式九宫格（工作坊采集，模板 bmc_nine_blocks_canvas.md）。条目编码：块成熟度分值（1-5）—— 条目描述（分值 = 首个『 —— 』之前前缀中的独立 1-5 整数，前缀不得含其它数字）
      required: [customer_segments, value_propositions, channels, customer_relationships, revenue_streams, key_resources, key_activities, key_partnerships, cost_structure]
      properties:
        customer_segments:
          type: array
          description: 客户细分清单
          items:
            type: string
        value_propositions:
          type: array
          description: 价值主张清单
          items:
            type: string
        channels:
          type: array
          description: 渠道通路清单
          items:
            type: string
        customer_relationships:
          type: array
          description: 客户关系清单
          items:
            type: string
        revenue_streams:
          type: array
          description: 收入来源清单（与 cost_structure 成本-收入对称）
          items:
            type: string
        key_resources:
          type: array
          description: 核心资源清单
          items:
            type: string
        key_activities:
          type: array
          description: 关键业务清单
          items:
            type: string
        key_partnerships:
          type: array
          description: 重要伙伴清单（catalog 锚定名 key_partnerships——存量资产已按此收敛，D7）
          items:
            type: string
        cost_structure:
          type: object
          description: 成本结构（自由 object——外层键为成本项名，值为成本说明；字段化 defer 至 Story 4.3）
output_schema:
  type: object
  required: [canvas_assessment]
  properties:
    canvas_assessment:
      type: object
      description: 画布评估结果
      required: [dimension_scores, consistency_analysis]
      properties:
        dimension_scores:
          type: object
          description: 九块成熟度分值聚合（外层键为块名，值为 1-5 分值与依据——自由 object，4.3 defer）
        consistency_analysis:
          type: object
          description: 块间一致性分析（外层键为对照关系名（如 value_propositions_customer_segments、cost_structure_revenue_streams），值为一致性判定与依据——自由 object，4.3 defer；核心匹配 value_propositions↔customer_segments 与成本-收入对称 cost_structure↔revenue_streams 双侧对照）
---

# 商业模式画布

> Osterwalder 商业模式九宫格：客户细分/价值主张/渠道通路/客户关系/收入来源/
> 核心资源/关键业务/重要伙伴/成本结构九块联动评估。纯内部框架型工具：分析主体
> 是用户输入的内部业务信息（经 `ToolCall.arguments` 进入 Think prompt 主通道），
> 不依赖任何外部数据源。

## 1. 适用场景
- 商业模式设计（九块完整模型的系统化描述）
- 新业务规划（新业务的价值创造与获取逻辑）
- 战略对齐（九块间一致性诊断）

## 2. 负向触发
- 单块价值匹配深化（客户画像×价值图双侧）：请用 value-proposition-canvas
- 组织维度设计（结构/流程/激励/人员）：请用 org-design-framework
- 执行细节规划（项目排期/资源分配）：请用 gantt-chart 或 raci-matrix

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| business_model | object | ✅ | 商业模式九宫格（条目编码：块成熟度分值（1-5）—— 条目描述） |
| business_model.customer_segments | array[string] | ✅ | 客户细分清单 |
| business_model.value_propositions | array[string] | ✅ | 价值主张清单 |
| business_model.channels | array[string] | ✅ | 渠道通路清单 |
| business_model.customer_relationships | array[string] | ✅ | 客户关系清单 |
| business_model.revenue_streams | array[string] | ✅ | 收入来源清单（与 cost_structure 成本-收入对称） |
| business_model.key_resources | array[string] | ✅ | 核心资源清单 |
| business_model.key_activities | array[string] | ✅ | 关键业务清单 |
| business_model.key_partnerships | array[string] | ✅ | 重要伙伴清单（catalog 锚定名——存量资产已收敛，D7） |
| business_model.cost_structure | object | ✅ | 成本结构（自由 object——外层键为成本项名，值为成本说明） |

分值解析锚点：每条目分值 = 首个『 —— 』之前前缀中的独立 1-5 整数（前缀不得含其它数字，防「P1 —— 4」误判）。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| canvas_assessment | object | 画布评估结果 |
| canvas_assessment.dimension_scores | object | 九块成熟度分值聚合（外层键为块名，值为 1-5 分值与依据） |
| canvas_assessment.consistency_analysis | object | 块间一致性分析（核心匹配 value_propositions↔customer_segments 与成本-收入对称 cost_structure↔revenue_streams 双侧对照） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/bmc_nine_blocks_canvas.md` 九宫格采集矩阵在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键 `business_model`（九叶子：customer_segments / value_propositions / channels / customer_relationships / revenue_streams / key_resources / key_activities / key_partnerships / cost_structure），构造示例见 §8。

**九块填写引导：** 条目编码 = 块成熟度分值（1-5）—— 条目描述；九块联动思考（填写顺序与匹配逻辑）见 `references/framework_logic.md`；存量模板基型 `references/canvas_template.json`（9 块空骨架）可直接用于线下预填。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `business_model`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划九块联动分析的执行步骤（分块成熟度 + 双侧对照）
3. Code 阶段：生成分析代码（纯内部数据直算——解析条目分值前缀，逐块聚合成熟度；可复用 `scripts/validate_canvas.py` 的九块完整性与关键连接校验逻辑）
4. Execute 阶段：沙箱执行（纯内部型无外部采集，代码不含任何 `$DATA_SOURCE` 标记）
5. Observe 阶段：结合九块条目完成块间印证（核心匹配与成本-收入对称双侧对照）
6. Validate 阶段：校验输出完备性（dimension_scores 九块齐备 + consistency_analysis 双侧对照）
7. 输出 `canvas_assessment`（dimension_scores + consistency_analysis）

**编码解析规范：** 分析代码以「首个『 —— 』之前前缀中的独立 1-5 整数」解析条目分值（前缀含其它数字即判格式违规，登记数据缺口）；系统化思考步骤见 `references/framework_logic.md`。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 内部数据不足（九块字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |

## 8. input_examples

```json
{
  "business_model": {
    "customer_segments": ["5 —— 网约车与出租车车队（高频补能刚需）", "3 —— 私家车主（长续航诉求）"],
    "value_propositions": ["4 —— 超快充与换电双补能体系", "3 —— 电池银行降低购置门槛"],
    "channels": ["4 —— 城市超充站网络", "3 —— 4S 店与网约车公司合作渠道"],
    "customer_relationships": ["3 —— 车队专属客户成功经理", "2 —— App 会员运营"],
    "revenue_streams": ["4 —— 车辆销售与电池租赁", "3 —— 充电服务订阅"],
    "key_resources": ["4 —— 宁德时代电芯独家供应协议", "3 —— 超充站选址与电力容量资源"],
    "key_activities": ["4 —— 整车平台研发与产线运营", "3 —— 充电网络建设与运营"],
    "key_partnerships": ["4 —— 宁德时代（电芯联合开发）", "3 —— 国家电网（电力容量合作）"],
    "cost_structure": {"电池成本": "占整车 BOM 38%，随锂价波动", "渠道成本": "4S 店返点约 6%"}
  }
}
```

## 9. References 指引

- `references/framework_logic.md` — 九块联动系统化思考（编号步骤 + 核心匹配 value_propositions↔customer_segments + 成本-收入对称 cost_structure↔revenue_streams + 填写指引）
- `references/scoring_anchors.md` — 块成熟度 1-5 评分锚点（刻度声明 + 分档含义 + 正例与反例）
- `references/workshop_guide.md` — 画布工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/bmc_nine_blocks_canvas.md` — 九宫格采集矩阵（字段与 input_schema 一一对应，工作坊现场填写）
- `references/canvas_template.json` — 模板基型（9 块空骨架，线下预填用——存量资产保留）
- `scripts/validate_canvas.py` — 九块校验器（缺失块 + 关键连接 VP↔CS/KR↔KA 校验——存量资产保留）
