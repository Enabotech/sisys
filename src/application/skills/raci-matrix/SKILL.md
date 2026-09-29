---
slug: raci-matrix
name: RACI 矩阵
version: 1.0.0
tool_name: RACI 矩阵
description: RACI 责任矩阵（Responsible/Accountable/Consulted/Informed）
when_to_use:
  - 角色职责澄清
  - 跨部门协作
  - 治理设计
when_not_to_use:
  - 个人绩效评估
capabilities:
  - responsibility_assignment
  - governance
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - governance
input_schema:
  type: object
  required: [roles_tasks]
  properties:
    roles_tasks:
      type: object
      description: 角色与任务分配（工作坊矩阵采集——任务为行、角色为列，模板 raci_roles_tasks.md）。assignments 条目编码：双层「任务名→角色名＝RACI 字母组合」（值为单字母或斜线组合如 A/R；恰 1 A 硬规则 + ≥1 R 软规则——A/R 计为已承担 R，违规经输出 conflicts 结构化呈现非整体失败）
      required: [roles, tasks, assignments]
      properties:
        roles:
          type: array
          description: 角色名清单（矩阵列头）
          items:
            type: string
        tasks:
          type: array
          description: 任务名清单（矩阵行首）
          items:
            type: string
        assignments:
          type: object
          description: 任务×角色分配（自由 object——外层键为任务名，内层键为角色名，值为 RACI 字母组合；字段化 defer 至 Story 4.3）
output_schema:
  type: object
  required: [raci_matrix]
  properties:
    raci_matrix:
      type: object
      description: RACI 分配结果
      required: [matrix, conflicts, suggestions]
      properties:
        matrix:
          type: object
          description: 规整化分配矩阵（任务名→角色名→字母组合）
        conflicts:
          type: array
          description: 规则违规清单（恰 1 A 硬规则与 ≥1 R 软规则的逐任务违规——结构化呈现非整体失败）
          items:
            type: string
        suggestions:
          type: array
          description: 职责优化建议清单（负载均衡/单点问责）
          items:
            type: string
---

# RACI 矩阵

> RACI 责任矩阵：任务×角色的职责分配（R 执行 / A 问责 / C 咨询 / I 知会）。
> 纯内部框架型工具：分析主体是用户输入的角色分工与任务分配（经
> `ToolCall.arguments` 进入 Think prompt 主通道），不依赖任何外部数据源。

## 1. 适用场景
- 角色职责澄清（跨部门协作的职责边界划分）
- 治理设计（决策权与执行权的分离安排）
- 流程再造（职责缺口与重叠诊断）

## 2. 负向触发
- 个人绩效评估（人员考核打分）：非职责分配范畴
- 项目排期与工期推算：请用 gantt-chart
- 任务依赖拓扑梳理：请用 dependency-graph

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| roles_tasks | object | ✅ | 角色与任务分配（工作坊矩阵采集——任务为行、角色为列） |
| roles_tasks.roles | array[string] | ✅ | 角色名清单（矩阵列头） |
| roles_tasks.tasks | array[string] | ✅ | 任务名清单（矩阵行首） |
| roles_tasks.assignments | object | ✅ | 任务×角色分配（双层编码） |

assignments 双层编码：任务名→角色名＝RACI 字母组合——外层键为任务名（per-task「恰 1 A」规则的计算粒度），内层键为角色名，值为单字母或斜线组合如 A/R；录入规范见 `references/validation_rules.md`。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| raci_matrix | object | RACI 分配结果 |
| raci_matrix.matrix | object | 规整化分配矩阵（任务名→角色名→字母组合） |
| raci_matrix.conflicts | array[string] | 规则违规清单（恰 1 A 硬规则与 ≥1 R 软规则的逐任务违规——结构化呈现非整体失败） |
| raci_matrix.suggestions | array[string] | 职责优化建议清单（负载均衡/单点问责） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/raci_roles_tasks.md` 采集模板在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键一级枚举：`roles_tasks`（roles/tasks/assignments 三叶子），构造示例见 §8。

**矩阵采集引导（任务为行、角色为列）：**

1. 工作坊现场先以「RACI 矩阵速查」段的任务×角色矩阵表格讨论（行首列任务名 = assignments 外层键，表头列角色名 = 内层键）
2. 定稿后逐任务转录为 assignments 双层编码：任务名→角色名＝RACI 字母组合（单元格字母组合直接映射为内层值）
3. roles 列头与 tasks 行首分别转录为两个数组（与矩阵表格一一对应）

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `roles_tasks`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划矩阵规整与规则校验的执行步骤
3. Code 阶段：生成分析代码（纯内部数据直算——双层 assignments 展开、逐任务规则校验、冲突清单汇总）
4. Execute 阶段：沙箱执行（纯内部型无外部采集，代码不含任何 `$DATA_SOURCE` 标记）
5. Observe 阶段：结合矩阵事实完成规则违规与负载分布印证
6. Validate 阶段：校验输出完备性（matrix/conflicts/suggestions 三键齐备）
7. 输出 `raci_matrix`（规则违规经 conflicts 结构化呈现，非整体失败）

**编码解析规范：** 分析代码以双层结构读入 assignments（外层键为任务名，内层键为角色名，值按斜线拆分为字母集合）；规则判定见 `references/validation_rules.md`，系统化思考步骤见 `references/framework_logic.md`。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 内部数据不足（模板字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |
| 规则违规（恰 1 A 硬规则 / ≥1 R 软规则 / 非法字母） | 非异常 | 经 `raci_matrix.conflicts` 结构化呈现（逐任务违规条目），不映射为运行时异常、不触发整体失败 |

## 8. input_examples

```json
{
  "roles_tasks": {
    "roles": ["产品经理", "架构师", "开发负责人", "测试负责人"],
    "tasks": ["需求分析", "方案设计", "编码实现", "系统测试"],
    "assignments": {
      "需求分析": {"产品经理": "A/R", "架构师": "C", "测试负责人": "I"},
      "方案设计": {"架构师": "A/R", "产品经理": "C", "开发负责人": "C"},
      "编码实现": {"开发负责人": "A/R", "架构师": "C"},
      "系统测试": {"测试负责人": "A/R", "开发负责人": "R", "产品经理": "I"}
    }
  }
}
```

## 9. References 指引

- `references/framework_logic.md` — 职责分配系统化思考（编号步骤：任务→角色映射→单点问责检查→负载均衡审视 + 填写指引）
- `references/validation_rules.md` — RACI 确定性规则集（逐条编号：恰 1 A 硬规则 + ≥1 R 软规则 + 无空任务 + 字母组合语法 + conflicts 出口）
- `references/workshop_guide.md` — 职责澄清工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/raci_roles_tasks.md` — 角色任务采集模板（字段与 input_schema 一一对应 + 矩阵速查段，工作坊现场填写）
