---
slug: gantt-chart
name: 甘特图
version: 1.0.0
tool_name: 甘特图
description: 项目时间线甘特图（任务 + 起止 + 里程碑）
when_to_use:
  - 项目排期
  - 里程碑规划
  - 资源时间分配
when_not_to_use:
  - 纯任务依赖拓扑梳理（无需时间排程）
  - 角色职责分配
capabilities:
  - project_scheduling
  - timeline_planning
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - timeline
input_schema:
  type: object
  required: [project_plan]
  properties:
    project_plan:
      type: object
      description: 项目计划（工作坊采集，模板 gantt_project_plan.md）。durations 条目编码：时长格式「N 天/周/月」（正则 ^\d+ *[天周月]$——禁「个月」与英文单位；归一基准＝天，周＝5 工作日、月＝20 工作日；里程碑＝durations 值「0 天」，零时长任务 ES=EF）
      required: [tasks, dependencies, durations, resources]
      properties:
        tasks:
          type: array
          description: 任务名清单（与 dependency-graph 任务名规范一致——禁含「、」与「←」）
          items:
            type: string
        dependencies:
          type: array
          description: 依赖边清单（条目编码「任务名 ← 前置任务列表」——同 dependency-graph 语法，模板行内前置列表以顿号分隔）
          items:
            type: string
        durations:
          type: object
          description: 任务时长（自由 object——外层键为任务名，值为「N 天/周/月」时长串；非规范零时长（0 周/0 月）统一归一为 0 天判里程碑；字段化 defer 至 Story 4.3）
        resources:
          type: object
          description: 资源分配（自由 object——外层键为任务名，值为资源投入描述（人员/设备/预算）；字段化 defer 至 Story 4.3）
output_schema:
  type: object
  required: [gantt_visualization]
  properties:
    gantt_visualization:
      type: object
      description: 甘特图可视化
      required: [timeline, milestones, critical_path]
      properties:
        timeline:
          type: array
          description: 时间线条目清单（前推 ES/EF 与后推 LS/LF——天基准归一后推算）
          items:
            type: object
        milestones:
          type: array
          description: 里程碑清单（durations 值「0 天」的零时长任务——ES=EF）
          items:
            type: string
        critical_path:
          type: array
          description: CPM 关键路径（ES/EF/LS/LF 零浮动链——时长归一真 CPM，与 dependency-graph 跳数最长链的结构代理语义分工；里程碑仅当处于零浮动链才进入本字段，否则以 milestones 标记承载）
          items:
            type: string
---

# 甘特图

> 项目时间线甘特图：任务 × 依赖 × 时长 → CPM 前推/后推（ES/EF/LS/LF）→ 零浮动关键路径
> 与里程碑标记。纯内部框架型工具：分析主体是用户输入的项目计划信息（经
> `ToolCall.arguments` 进入 Think prompt 主通道），不依赖任何外部数据源。

## 1. 适用场景
- 项目排期（任务时间线与关键路径推算）
- 里程碑规划（零时长节点锚定）
- 资源时间分配（任务与资源的冲突审视）

## 2. 负向触发
- 纯任务依赖拓扑梳理（无需时间排程）：请用 dependency-graph
- 角色职责分配（任务×角色矩阵）：请用 raci-matrix

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| project_plan | object | ✅ | 项目计划（工作坊采集——单容器四字段） |
| project_plan.tasks | array[string] | ✅ | 任务名清单（禁含「、」与「←」——与 dependency-graph 任务名规范一致） |
| project_plan.dependencies | array[string] | ✅ | 依赖边清单（条目编码「任务名 ← 前置任务列表」——同 dependency-graph 语法，模板行内以顿号分隔） |
| project_plan.durations | object | ✅ | 任务时长（自由 object——外层键为任务名，值为「N 天/周/月」时长串；里程碑＝值「0 天」） |
| project_plan.resources | object | ✅ | 资源分配（自由 object——外层键为任务名，值为资源投入描述） |

时长编码规范：时长格式「N 天/周/月」（正则 `^\d+ *[天周月]$`——禁「个月」与英文单位）；归一基准＝天（周＝5 工作日、月＝20 工作日），CPM 算术在归一后的天基准进行。

里程碑输入编码：durations 值「0 天」＝零时长任务即里程碑（ES=EF）；非规范零时长（0 周/0 月）统一归一为 0 天判里程碑（模板规范写法「0 天」）。

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| gantt_visualization | object | 甘特图可视化 |
| gantt_visualization.timeline | array[object] | 时间线条目清单（前推 ES/EF 与后推 LS/LF——天基准归一后推算） |
| gantt_visualization.milestones | array[string] | 里程碑清单（durations 值「0 天」的零时长任务——ES=EF） |
| gantt_visualization.critical_path | array[string] | CPM 关键路径（ES/EF/LS/LF 零浮动链——时长归一真 CPM；里程碑仅当处于零浮动链才进入本字段） |

## 5. 数据采集计划（Think 阶段引导——用户输入采集）

> 纯内部型语义承载：本章节的「数据采集」= 用户输入采集（模板引导 + arguments 构造），无外部数据源映射表。

**内部数据（分析主体，工作坊采集）：** 经 `templates/gantt_project_plan.md` 排程采集表格在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 传入——根键 `project_plan`（tasks / dependencies / durations / resources 四叶子），构造示例见 §8。

**排程采集引导（四要素）：**

| 采集要素 | 编码格式 | 说明 |
| --- | --- | --- |
| 任务清单 | 任务名（顿号分隔——禁含「、」与「←」） | 与 dependency-graph 任务名规范一致 |
| 依赖边 | 「任务名 ← 前置任务列表」（行内顿号分隔） | 同 dependency-graph 语法 |
| 时长 | 「N 天/周/月」（正则 `^\d+ *[天周月]$`） | 归一基准＝天：周＝5 工作日、月＝20 工作日 |
| 里程碑 | durations 值「0 天」 | 零时长任务即里程碑（ES=EF）——Epic「时间线+里程碑」输入侧承接 |

排程系统化思考步骤见 `references/framework_logic.md`；确定性校验规则（DAG 无环 + 正则 + CPM 前推/后推）见 `references/validation_rules.md`。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `project_plan`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划 CPM 排程分析的执行步骤（归一→前推→后推→关键路径→里程碑）
3. Code 阶段：生成分析代码（纯内部数据直算——时长归一到天基准，按 validation_rules 规则 3 前推/后推推算 ES/EF/LS/LF）
4. Execute 阶段：沙箱执行（纯内部型无外部采集，代码不含任何 `$DATA_SOURCE` 标记）
5. Observe 阶段：结合任务/依赖/时长完成时间线与零浮动链印证（资源冲突审视为 LLM 分析项）
6. Validate 阶段：校验输出完备性（timeline 逐任务 + milestones 含 0 天条目 + critical_path 零浮动链）
7. 输出 `gantt_visualization`（timeline / milestones / critical_path）

**时长解析规范：** 分析代码以正则 `^\d+ *[天周月]$` 校验时长格式（违规登记数据缺口，不中断），单位归一（周＝5 工作日、月＝20 工作日）后天基准推算；非规范零时长（0 周/0 月）归一为 0 天判里程碑。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | 207 | 立即失败（策略违规）——纯内部框架 Skill 不声明任何外部数据源，标记即误用，修正代码移除标记 |
| 代码含标记但引擎未注入解析器 | 101 | 部署配置问题（fail-fast），不应出现在纯内部型链路 |
| 时长格式非规范（如「3 个月」「2 weeks」） | — | 不硬失败：该任务时长登记数据缺口（模板缺口登记区），其余任务按规范继续推算 |
| 内部数据不足（模板字段缺失/空洞） | INSUFFICIENT_DATA | 引导补办采集：按模板「数据缺口登记」区登记缺口字段与替代来源，补齐后重跑（状态语义见 ToolResultStatus） |

## 8. input_examples

```json
{
  "project_plan": {
    "tasks": ["需求分析", "架构设计", "开发实现", "里程碑评审", "发布上线"],
    "dependencies": ["架构设计 ← 需求分析", "开发实现 ← 架构设计", "里程碑评审 ← 开发实现", "发布上线 ← 里程碑评审"],
    "durations": {
      "需求分析": "5 天",
      "架构设计": "2 周",
      "开发实现": "1 月",
      "里程碑评审": "0 天",
      "发布上线": "3 天"
    },
    "resources": {
      "需求分析": "产品经理 1 人",
      "架构设计": "架构师 1 人 + 技术负责人 0.5 人",
      "开发实现": "后端 4 人 + 前端 2 人",
      "里程碑评审": "全体核心成员",
      "发布上线": "运维 1 人 + 值守 2 人"
    }
  }
}
```

## 9. References 指引

- `references/framework_logic.md` — 排程系统化思考（编号步骤：任务拆分粒度→依赖确认→时长估算→里程碑锚定→资源冲突审视 + 填写指引）
- `references/validation_rules.md` — 确定性校验规则（规则 1-5：时长正则 / 归一基准 / CPM 前推后推（ES/EF/LS/LF）/ 里程碑 0 天裁定 / 依赖边语法——含 CPM 关键字）
- `references/workshop_guide.md` — 排程工作坊 2-4 小时引导（会前准备/流程/角色分工/会后模板→arguments 构造）
- `templates/gantt_project_plan.md` — 排程采集表格（字段与 input_schema 一一对应，工作坊现场填写）
