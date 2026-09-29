---
slug: strategy-map
name: 战略地图
version: 1.0.0
tool_name: 战略地图
description: Kaplan/Norton 战略地图（4 视角因果链）
when_to_use:
  - 战略主题设计
  - 因果链路梳理
  - 战略沟通
when_not_to_use:
  - KPI 数值计算
capabilities:
  - strategic_theming
  - visual_communication
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - strategy
input_schema:
  type: object
  required: [bsc_indicators]
  properties:
    bsc_indicators:
      type: object
      description: BSC 四维度指标（内部框架输入，模板 strategy_map_causal_links.md）。四维度清单条目编码：指标陈述（指标名与现状量级，如「营业收入 = 4.2 亿元，年增 12%」）
      required: [financial, customer, internal_process, learning_growth, causal_relationships]
      properties:
        financial:
          type: array
          description: 财务维度指标清单
          items:
            type: string
        customer:
          type: array
          description: 客户维度指标清单
          items:
            type: string
        internal_process:
          type: array
          description: 内部流程维度指标清单
          items:
            type: string
        learning_growth:
          type: array
          description: 学习与成长维度指标清单
          items:
            type: string
        causal_relationships:
          type: array
          description: 因果关系假设清单。条目编码：因果箭头语法「原因维度 → 结果维度：假设描述」（全角冒号；标准方向自下而上 learning_growth → internal_process → customer → financial——Kaplan-Norton）
          items:
            type: string
output_schema:
  type: object
  required: [strategy_visualization]
  properties:
    strategy_visualization:
      type: object
      description: 战略地图可视化（定性因果链图——不含 KPI 量化，量化验证移交 bsc-scorecard）
      required: [nodes, causal_arrows, theme_cards]
      properties:
        nodes:
          type: array
          description: 因果链节点清单（每节点含 node_id 节点标识、label 节点名称、dimension 所属维度三键——自由 object，4.3 defer）
          items:
            type: object
        causal_arrows:
          type: array
          description: 因果箭头清单（标准方向自下而上；逆向或同层箭头以 warning 级标记待澄清假设，不硬失败）
          items:
            type: string
        theme_cards:
          type: array
          description: 战略主题卡清单（每卡含 theme 主题名、dimensions 涉及维度、hypothesis_chain 假设链三键——自由 object，4.3 defer）
          items:
            type: object
---

# 战略地图

> Kaplan/Norton 战略地图：BSC 四维度（learning_growth / internal_process / customer / financial）
> 的定性因果链可视化。纯内部框架型工具：分析主体是用户输入的内部战略信息（经
> `ToolCall.arguments` 进入 Think prompt 主通道），不依赖任何外部数据源。

## 1. 适用场景
- 战略主题设计（跨维度因果假设的结构化表述）
- 因果链路梳理（自下而上的战略传导逻辑验证）
- 战略沟通（一页式因果图对齐管理层共识）

## 2. 负向触发
- KPI 数值计算与目标定档（定量计分卡）：请用 bsc-scorecard
- 单一 KPI 分解树（不含四维度因果假设）：请用 kpi-tree

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| bsc_indicators | object | ✅ | BSC 四维度指标（四维度清单条目编码：指标陈述——指标名与现状量级） |
| bsc_indicators.financial | array[string] | ✅ | 财务维度指标清单（指标陈述） |
| bsc_indicators.customer | array[string] | ✅ | 客户维度指标清单（指标陈述） |
| bsc_indicators.internal_process | array[string] | ✅ | 内部流程维度指标清单（指标陈述） |
| bsc_indicators.learning_growth | array[string] | ✅ | 学习与成长维度指标清单（指标陈述） |
| bsc_indicators.causal_relationships | array[string] | ✅ | 因果关系假设清单（因果箭头语法） |

因果箭头编码：条目按「原因维度 → 结果维度：假设描述」书写（全角冒号）；标准方向自下而上 learning_growth → internal_process → customer → financial（Kaplan-Norton），逆向或同层箭头标记 warning 级待澄清假设。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| strategy_visualization | object | 战略地图可视化（定性因果链图） |
| strategy_visualization.nodes | array[object] | 因果链节点清单（维度/指标/主题） |
| strategy_visualization.causal_arrows | array[string] | 因果箭头清单（标准方向自下而上；逆向或同层以 warning 级标记） |
| strategy_visualization.theme_cards | array[object] | 战略主题卡清单（主题名/涉及维度/假设链） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/strategy_map_causal_links.md` 因果链采集表在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键一级枚举：`bsc_indicators`（financial / customer / internal_process / learning_growth / causal_relationships 五叶子），构造示例见 §8。

**采集引导（自下而上的维度序）：**

| 采集块 | 内容 | 编码形态 |
| --- | --- | --- |
| learning_growth | 学习与成长维度指标 | 指标陈述（如「一线数字化技能覆盖率 = 45%」） |
| internal_process | 内部流程维度指标 | 指标陈述（如「订单处理周期 = 5.2 天」） |
| customer | 客户维度指标 | 指标陈述（如「客户满意度 NPS = 32」） |
| financial | 财务维度指标 | 指标陈述（如「营业收入 = 4.2 亿元，年增 12%」） |
| causal_relationships | 因果关系假设 | 因果箭头「learning_growth → internal_process：假设描述」 |

因果链构建与战略主题卡设计步骤见 `references/framework_logic.md`；箭头语法与方向校验规则见 `references/validation_rules.md`。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `bsc_indicators`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划定性因果链构建的执行步骤（四维度指标梳理 → 因果假设表述 → 闭合检查 → 主题卡设计）
3. Code 阶段：生成分析代码（纯内部数据直算——解析因果箭头语法，构建 nodes 与 causal_arrows）
4. Execute 阶段：沙箱执行（纯内部型无外部采集，代码不含任何 `$DATA_SOURCE` 标记）
5. Observe 阶段：校验因果链闭合性（孤立维度与断链识别）与方向合规（逆向或同层箭头标 warning）
6. Validate 阶段：校验输出完备性（nodes / causal_arrows / theme_cards 三键齐备）
7. 输出 `strategy_visualization`（定性因果链图——量化验证移交 bsc-scorecard）

**编码解析规范：** 分析代码以「原因维度 → 结果维度：假设描述」正则解析因果条目（维度名 ∈ 四维度枚举）；系统化思考步骤见 `references/framework_logic.md`。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 因果箭头方向逆向或同层（如 financial → learning_growth） | —（warning 级） | 不硬失败：标记为待澄清假设列入 causal_arrows 附注，工作坊复议方向或补正表述 |
| 因果链断链（维度未参与任何箭头） | —（warning 级） | 不硬失败：孤立维度列入主题卡复议清单 |
| 内部数据不足（模板字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |

## 8. input_examples

```json
{
  "bsc_indicators": {
    "learning_growth": ["一线数字化技能覆盖率 = 45%", "关键岗位继任者就绪率 = 38%"],
    "internal_process": ["订单处理周期 = 5.2 天", "一次交付合格率 = 91%"],
    "customer": ["客户满意度 NPS = 32", "大客户续约率 = 78%"],
    "financial": ["营业收入 = 4.2 亿元，年增 12%", "毛利率 = 21%"],
    "causal_relationships": [
      "learning_growth → internal_process：一线数字化技能提升缩短订单处理周期",
      "internal_process → customer：订单处理周期缩短提升大客户续约率",
      "customer → financial：大客户续约率提升带动营业收入增长"
    ]
  }
}
```

## 9. References 指引

- `references/framework_logic.md` — 四层因果假设系统化思考（编号步骤 + 与 bsc-scorecard 互查映射表 + 填写指引）
- `references/validation_rules.md` — 因果箭头语法与方向校验规则（规则 1 起序：箭头正则 / 闭合校验 / Kaplan-Norton 标准方向 / 量化移交）
- `references/workshop_guide.md` — 战略地图工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/strategy_map_causal_links.md` — 因果链采集表（字段与 input_schema 一一对应，工作坊现场填写）
