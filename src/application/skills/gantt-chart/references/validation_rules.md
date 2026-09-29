# 甘特图确定性校验规则（结构型 validation_rules）

> 逐条编号规则集：时长编码 / 归一基准 / CPM 前推后推 / 里程碑裁定 / 依赖边语法。
> 违规经输出根键 `gantt_visualization` 相应字段结构化呈现（时长违规登记数据缺口，
> 环违规经依赖图结构呈现），不映射为运行时异常或整体失败。

## 规则集（逐条编号）

- 规则 1 —— 时长格式正则：durations 值必须匹配 `^\d+ *[天周月]$`（数字 + 可选
  空格 + 单字符单位）；「3 个月」「2 weeks」「1.5 天」等形态均为非规范——违规
  任务时长登记数据缺口（不中断其余任务推算），禁「个月」与英文单位
- 规则 2 —— 归一基准＝天：周＝5 工作日、月＝20 工作日；CPM 前推/后推全部算术
  在归一后的天基准上进行（禁止周/月混算）
- 规则 3 —— 前推/后推（ES/EF/LS/LF）：前推 ES = max(前驱 EF)（无前驱取 0）、
  EF = ES + 归一时长；后推 LF = min(后继 LS)（无后继取项目终点 EF）、
  LS = LF - 归一时长；零浮动（LS - ES = 0）任务连通链 = CPM 关键路径
- 规则 4 —— 里程碑裁定：durations 值「0 天」的零时长任务即里程碑（ES=EF）；
  非规范零时长（0 周/0 月）统一归一为 0 天判里程碑（模板规范写法「0 天」）；
  里程碑仅当处于零浮动链才进入 critical_path，否则以 milestones 标记承载
  （不强行入关键路径）
- 规则 5 —— 依赖边语法：dependencies 条目编码「任务名 ← 前置任务列表」（同
  dependency-graph 语法，模板行内前置列表以顿号「、」分隔）；任务名禁含
  「、」与「←」；依赖引用的任务必须 ∈ tasks（引用不存在任务 = 数据缺口）；
  依赖图 DAG 无环（环违规经依赖结构呈现——本 Skill 时间排程语义的入口校验，
  纯拓扑分析请用 dependency-graph）

## 与 dependency-graph 的语义分工

| 维度 | dependency-graph | gantt-chart（本 Skill） |
| --- | --- | --- |
| 输入 | task_list（name + dependencies，无时长） | project_plan（含 durations/resources） |
| critical_path 语义 | 跳数最长链的无时长结构代理 | ES/EF/LS/LF 零浮动链（时长归一真 CPM） |
| 关系 | 无时长退化形态 | 含时间的完整形态 |

dependency-graph 的结构代理是本 Skill 真关键路径在输入无时长时的退化形态；
两 Skill 同用时以本 Skill 的时间推算为准。
