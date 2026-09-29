---
slug: dependency-graph
name: 依赖关系图
version: 1.0.0
tool_name: 依赖关系图
description: 任务依赖关系图（DAG 节点 + 边）
when_to_use:
  - 项目依赖梳理
  - 关键路径识别
  - 并行化机会
when_not_to_use:
  - 战略选择
capabilities:
  - project_planning
  - critical_path
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - project
input_schema:
  type: object
  required: [task_list]
  properties:
    task_list:
      type: array
      description: 任务列表（顶层对象数组，模板 dependency_task_inventory.md）。条目编码：依赖边语法「任务名 ← 前置任务列表」（name 为单任务名，dependencies 为其前置任务名数组；任务名禁含顿号「、」与箭头「←」——模板行内前置列表以顿号分隔）
      items:
        type: object
        required: [name, dependencies]
        properties:
          name:
            type: string
            description: 任务名（唯一标识，禁含「、」与「←」）
          dependencies:
            type: array
            description: 前置任务名清单（可为空数组——显式空表无依赖）
            items:
              type: string
output_schema:
  type: object
  required: [dependency_network]
  properties:
    dependency_network:
      type: object
      description: 依赖关系网络
      required: [dag, critical_path, risk_nodes]
      properties:
        dag:
          type: object
          description: 有向无环图结构（邻接表——环违规以 cycles 键结构化呈现于本对象，不映射运行时异常）
        critical_path:
          type: array
          description: 关键路径（跳数最长链的无时长结构代理——与 gantt-chart 的时长归一 CPM 语义分工，输入无时长时的退化形态）
          items:
            type: string
        risk_nodes:
          type: array
          description: 风险节点清单（扇入 ≥3 的汇聚节点、扇出 ≥3 的发散节点与零依赖/零被依赖的孤立节点——机械规则，其余风险为 LLM 分析项）
          items:
            type: string
---

# 依赖关系图

> 任务依赖 DAG 拓扑分析：任务清单（task_list）→ 有向无环图 → 拓扑分层、关键路径
> （跳数最长链）与风险节点识别。纯内部框架型工具：分析主体是用户输入的内部
> 业务信息（经 `ToolCall.arguments` 进入 Think prompt 主通道），不依赖任何外部数据源。

## 1. 适用场景
- 项目依赖梳理（任务间前置关系系统化登记）
- 关键路径识别（无工期输入的结构代理——跳数最长链）
- 并行化机会发现（拓扑分层后同层任务可并行）

## 2. 负向触发
- 含时间排程与工期估算的项目计划（任务时长/里程碑/资源日历）：请用 gantt-chart
- 角色职责分配（谁负责/谁审批）：请用 raci-matrix
- 战略选择（多方案比选）：请用 swot-tows 或 space-matrix

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_list | array[object] | ✅ | 任务列表（顶层对象数组——模板以 task_list 分区标题承载） |
| task_list[].name | string | ✅ | 任务名（唯一标识，禁含「、」与「←」） |
| task_list[].dependencies | array[string] | ✅ | 前置任务名清单（可为空数组——显式空表无依赖） |

条目编码：依赖边语法「任务名 ← 前置任务列表」（模板行内前置列表以顿号「、」分隔；任务名禁含「、」与「←」，防顿号分隔歧义与箭头语法冲突）。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| dependency_network | object | 依赖关系网络 |
| dependency_network.dag | object | 有向无环图结构（邻接表——环违规以 cycles 键结构化呈现，不映射运行时异常） |
| dependency_network.critical_path | array[string] | 关键路径（跳数最长链的无时长结构代理） |
| dependency_network.risk_nodes | array[string] | 风险节点清单（扇入 ≥3 汇聚节点、扇出 ≥3 发散节点与零依赖/零被依赖孤立节点） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/dependency_task_inventory.md` 任务清单采集表在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键枚举：`task_list`（对象数组，每对象 name 单任务名 + dependencies 前置任务名数组），构造示例见 §8。

**依赖边采集引导（逐任务一行）：**

| 列 | 填写形态 | 约束 |
| --- | --- | --- |
| 任务名（name） | 单任务名（如「架构设计」） | 禁含顿号「、」与箭头「←」（防分隔歧义与语法冲突） |
| 前置任务（dependencies） | 模板行内顿号分隔（如「需求分析、技术选型」） | 仅引用已登记任务名；无前置填「无」（构造为空数组） |

依赖方向与拓扑分层规则见 `references/framework_logic.md`。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `task_list`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划 DAG 构建与拓扑分析的执行步骤（建图 → 校验 → 分层 → 推算）
3. Code 阶段：生成分析代码（纯内部数据直算——由 task_list 构建邻接表，执行无环校验/拓扑排序/跳数最长链推算，零 `$DATA_SOURCE` 标记）
4. Execute 阶段：沙箱执行（纯内部型无外部采集）
5. Observe 阶段：核对拓扑分层与风险节点（扇入/扇出/孤立节点机械规则命中情况）
6. Validate 阶段：校验输出完备性（dag 邻接表 + critical_path 非空 + risk_nodes 列表）
7. 输出 `dependency_network`（critical_path = 跳数最长链的无时长结构代理）

**编码解析规范：** 分析代码按「name 取单任务名、dependencies 取前置任务名数组」解析条目（模板行内顿号分隔形态由记录员转写为数组）；确定性规则集见 `references/validation_rules.md`。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 内部数据不足（模板字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |
| 任务依赖成环（DAG 无环校验不过） | — | 非异常：环违规经 `dependency_network.dag` 的 cycles 键结构化呈现（逐环列出任务名），引导澄清依赖方向后重跑 |

## 8. input_examples

```json
{
  "task_list": [
    {"name": "需求分析", "dependencies": []},
    {"name": "技术选型", "dependencies": ["需求分析"]},
    {"name": "架构设计", "dependencies": ["需求分析", "技术选型"]},
    {"name": "开发实施", "dependencies": ["架构设计"]},
    {"name": "集成测试", "dependencies": ["开发实施"]}
  ]
}
```

## 9. References 指引

- `references/framework_logic.md` — 依赖拓扑系统化思考（编号步骤 + 拓扑分层 + 关键路径结构代理推算 + 填写指引）
- `references/validation_rules.md` — 确定性规则集（DAG 无环校验 / 依赖方向 / 跳数最长链推算 / risk_nodes 判定 / 任务名字符约束）
- `references/workshop_guide.md` — 依赖梳理工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/dependency_task_inventory.md` — 任务清单采集表（字段与 input_schema 一一对应，工作坊现场填写）
