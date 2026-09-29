---
slug: kpi-tree
name: KPI
version: 1.0.0
tool_name: KPI
description: KPI 树（战略目标 → 部门目标 → 个人目标）
when_to_use:
  - KPI 分解
  - 目标对齐
  - 绩效指标设计
when_not_to_use:
  - 战略选择
capabilities:
  - kpi_decomposition
  - goal_cascade
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - kpi
data_sources:
  - name: china-nbs
    url: https://www.stats.gov.cn
    api_type: crawler
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
  - name: newsapi
    url: https://newsapi.org
    api_type: rest_json
    ttl_seconds: 21600
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required: [business_objectives]
  properties:
    business_objectives:
      type: object
      description: 业务目标（战略规划文件 + 数据仓库导出，模板 kpi_tree_decomposition.md）。条目编码——objectives 逐条「目标档位（基准/挑战/突破）—— 层级：目标描述」（档位=首个『 —— 』前的枚举词，层级=其后『：』前的枚举词；档位换算与逐级校验依赖档位前缀解析；baseline_data 键值形态「指标 → 对象（键为 现值/口径）」）
      required: [objectives, baseline_data]
      properties:
        objectives:
          type: array
          description: 战略目标分解链（战略 → 部门 → 个人）
          items:
            type: string
        baseline_data:
          type: object
          description: KPI 现值基线（指标 → 现值，数据仓库导出）
output_schema:
  type: object
  required: [kpi_definitions, data_sources]
  properties:
    kpi_definitions:
      type: array
      description: KPI 定义列表（含口径/目标/权重/监控频率）
      items:
        type: object
        required: [name, target_value, weight, monitoring_frequency]
        properties:
          name:
            type: string
            description: KPI 名称（含指标口径定义）
          target_value:
            type: number
            description: 目标值（行业指标统计参照）
          weight:
            type: number
            description: 权重（分解树层级）
          monitoring_frequency:
            type: string
            description: 监控频率（日/周/月/季/年）
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# KPI 树

> 战略目标 → 部门目标 → 个人目标逐层分解树 + 指标口径定义 + 行业指标参照。
> 混合数据型工具：内部数据（战略规划文件目标 + 数据仓库 KPI 现值导出）是分析主体，
> 外部数据源（国家统计局/NewsAPI）仅提供行业指标统计与绩效动态的参照基准。

## 1. 适用场景
- KPI 分解（战略 → 部门 → 个人目标逐层对齐）
- 目标对齐（跨部门目标一致性校验与冲突识别）
- 绩效指标设计（指标口径/目标值/权重/监控频率四要素定义）

## 2. 负向触发
- 战略选择（战略选项生成与匹配）：请用 swot-tows 或 ge-mckinsey-matrix
- 平衡计分卡四维度体系设计：请用 bsc-scorecard
- 单纯的任务排期与责任分配：请用 gantt-chart 或 raci-matrix

## 3. 输入字段（input_schema）

`business_objectives` 为嵌套对象（`objectives` 为 array items 形态），字段表用「容器.字段」表示：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| business_objectives | object | ✅ | 业务目标（战略规划文件 + 数据仓库导出；条目编码见下两行） |
| business_objectives.objectives | array[string] | ✅ | 战略目标分解链（逐条「目标档位（基准/挑战/突破）—— 层级（主体）：目标描述」） |
| business_objectives.baseline_data | object | ✅ | KPI 现值基线（指标 → 现值，数据仓库导出） |

## 4. 输出字段（output_schema）

`kpi_definitions` 为 array of object（逐 KPI 一项），字段表用「容器.字段」表示展开形态：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| kpi_definitions | array[object] | KPI 定义列表（含口径/目标/权重/监控频率） |
| kpi_definitions[].name | string | KPI 名称（含指标口径定义） |
| kpi_definitions[].target_value | number | 目标值（行业指标统计参照） |
| kpi_definitions[].weight | number | 权重（分解树层级） |
| kpi_definitions[].monitoring_frequency | string | 监控频率（日/周/月/季/年） |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，战略规划文件 + 数据仓库导出）：** 经 `templates/kpi_tree_decomposition.md`
目标分解表在战略解码工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），
`objectives` 来自战略规划文件的目标陈述，`baseline_data` 由数据仓库按指标口径导出现值，
会后将模板字段构造为 `ToolCall.arguments` 的 `business_objectives` 传入。

**外部基准（参照印证，双源交叉）：**

| 外部参照目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业指标统计（行业增速/效率类官方指标的目标值参照） | china-nbs | 站点相对路径（如 "sj/zxfb" 最新发布的行业统计数据） |
| 行业绩效动态（同业绩效事件/指标实践的时效印证） | newsapi | 自然语言关键词（如 "动力电池 产能利用率 行业动态"） |

**内外交叉验证要求：** 每个战略层 KPI 的目标值设定须有至少一条行业指标参照
（或显式标注「内部目标，未经行业参照」）；目标值显著偏离行业统计趋势时须在口径定义中
登记依据；外部参照与内部基线矛盾时的处置见 `references/data_fusion.md`
（冲突分级处理：内部定档高于官方统计 → 统计优先修正并要求降档或补强依据；外部无参照 → 双方并列不下结论；新闻绩效事件与官方统计方向相反 → 以官方统计为准、事件列入复议清单）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `business_objectives`（内部数据经 Think prompt 进入
   分析上下文——目标分解链与 KPI 现值基线在此参与推理）
2. Think 阶段：规划目标逐层分解、指标口径定义与行业参照的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
nbs = $DATA_SOURCE("china-nbs", "sj/zxfb")
news = $DATA_SOURCE("newsapi", "动力电池 产能利用率 行业动态")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
nbs_payload = (DATA_SOURCES.get("china-nbs") or {}).get("payload")
news_payload = (DATA_SOURCES.get("newsapi") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（arguments）与外部参照（DATA_SOURCES）完成目标逐层分解、
   口径定义与目标值档位设定（锚点见 `references/scoring_anchors.md`）
6. Validate 阶段：校验 KPI 定义完备性（口径/目标/权重/监控频率四要素 + 溯源元数据）
7. 输出 `kpi_definitions` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；
**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；
标记数据源名必须在 frontmatter 白名单内（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（NewsAPI API Key 缺失，`os.environ['NEWSAPI_API_KEY']` 未配置） | 411 | **Key 敏感降级**：内部 KPI 数据是分析主体——基于目标分解链与现值基线完成 KPI 定义，行业绩效动态参照标注「未经外部印证的数据缺口」，建议配置 Key 后重跑 |
| china-nbs crawler daemon 未运行（爬虫源不可用） | 411 | **crawler 降级**：基于内部数据 + newsapi 其余源继续分析，行业指标统计参照标注数据缺口，待 crawler daemon 恢复后补采 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（objectives 缺失/基线空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办战略解码工作坊采集与数据仓库导出（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "business_objectives": {
    "objectives": [
      "突破档 —— 战略：2027 年动力电池业务营收翻番（新建产线 + 海外定点支撑）",
      "挑战档 —— 部门（销售部）：新签车企定点 12 家",
      "挑战档 —— 部门（制造部）：直通率提升至 92%",
      "基准档 —— 个人（电芯产线组长）：化成分容批次合格率 95%"
    ],
    "baseline_data": {
      "营收": {"现值": "18.5 亿元", "口径": "含税营业收入"},
      "直通率": {"现值": "85%", "口径": "一次合格率"},
      "新签定点数": {"现值": "4 家", "口径": "年度累计"}
    }
  }
}
```

外部参照 query 独立标记示例（不入 arguments JSON）：

```python
nbs = $DATA_SOURCE("china-nbs", "sj/zxfb")
news = $DATA_SOURCE("newsapi", "动力电池 行业 营收 增速")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（参照流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — KPI 目标档位锚点（每档含义 + 正反例 + 聚合规则）
- `references/workshop_guide.md` — 战略解码工作坊引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/kpi_tree_decomposition.md` — 目标分解表（字段与 input_schema 一一对应，工作坊现场填写）
