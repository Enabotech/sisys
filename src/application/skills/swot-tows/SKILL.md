---
slug: swot-tows
name: SWOT-TOWS
version: 1.0.0
tool_name: SWOT-TOWS
description: SWOT 内外部因素 + TOWS 四象限战略匹配
when_to_use:
  - 战略态势评估
  - 内外部因素整合
  - 战略选项生成
when_not_to_use:
  - 具体执行规划
capabilities:
  - strategic_assessment
  - option_generation
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - swot
data_sources:
  - name: newsapi
    url: https://newsapi.org
    api_type: rest_json
    ttl_seconds: 21600
    required_fields:
      - indicator
      - value
  - name: tavily
    url: https://api.tavily.com
    api_type: rest_json
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required: [internal_factors, external_factors]
  properties:
    internal_factors:
      type: object
      description: 内部因素（工作坊采集：优势/劣势清单，模板 swot_factors_collection.md）。条目编码：强度分值（1-5）—— 因素描述（R2-F7，TOWS 匹配阈值 ≥3 依赖分值解析）
      required: [strengths, weaknesses]
      properties:
        strengths:
          type: array
          description: 内部优势清单（资源/能力维度）
          items:
            type: string
        weaknesses:
          type: array
          description: 内部劣势清单（短板维度）
          items:
            type: string
    external_factors:
      type: object
      description: 外部因素（机会/威胁，经 NewsAPI/Tavily 外部基准印证）。条目编码：强度分值（1-5）—— 因素描述（R2-F7，与内部象限同格式）
      required: [opportunities, threats]
      properties:
        opportunities:
          type: array
          description: 外部机会清单（行业时政/竞争情报印证）
          items:
            type: string
        threats:
          type: array
          description: 外部威胁清单（行业时政/竞争情报印证）
          items:
            type: string
output_schema:
  type: object
  required: [tows_matrix, data_sources]
  properties:
    tows_matrix:
      type: object
      description: TOWS 策略矩阵（内外因素交叉匹配战略）
      required: [so_strategies, wo_strategies, st_strategies, wt_strategies, priority]
      properties:
        so_strategies:
          type: array
          description: SO 战略（优势×机会：增长型）
          items:
            type: string
        wo_strategies:
          type: array
          description: WO 战略（劣势×机会：扭转型）
          items:
            type: string
        st_strategies:
          type: array
          description: ST 战略（优势×威胁：多元化）
          items:
            type: string
        wt_strategies:
          type: array
          description: WT 战略（劣势×威胁：防御型）
          items:
            type: string
        priority:
          type: array
          description: 战略优先级排序（含依据）
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# SWOT-TOWS

> SWOT 内部因素（优势/劣势）× 外部因素（机会/威胁）四象限态势评估 + TOWS 交叉战略匹配。
> 混合数据型工具：内部数据（工作坊采集）是分析主体，外部数据源（NewsAPI/Tavily）仅提供行业时政与竞争情报的外部印证基准。

## 1. 适用场景
- 战略态势评估（内外部因素系统整合）
- 年度战略规划前的现状盘点
- 战略选项生成（SO/WO/ST/WT 四象限匹配）

## 2. 负向触发
- 具体执行规划（项目排期/资源分配）：请用 gantt-chart 或 raci-matrix
- 运营效率分析（流程瓶颈诊断）：请用 value-chain-analysis
- 单一维度的外部环境扫描（无需内部数据）：请用 pestel-analysis

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| internal_factors | object | ✅ | 内部因素（工作坊采集；条目编码：强度分值（1-5）—— 因素描述） |
| internal_factors.strengths | array[string] | ✅ | 内部优势清单（资源/能力维度；条目编码：强度分值（1-5）—— 因素描述） |
| internal_factors.weaknesses | array[string] | ✅ | 内部劣势清单（短板维度；条目编码同上） |
| external_factors | object | ✅ | 外部因素（条目编码：强度分值（1-5）—— 因素描述） |
| external_factors.opportunities | array[string] | ✅ | 外部机会清单（经外部基准印证） |
| external_factors.threats | array[string] | ✅ | 外部威胁清单（经外部基准印证） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| tows_matrix | object | TOWS 策略矩阵（SO/WO/ST/WT 四象限 + 优先级） |
| tows_matrix.so_strategies | array[string] | SO 战略（优势×机会：增长型） |
| tows_matrix.wo_strategies | array[string] | WO 战略（劣势×机会：扭转型） |
| tows_matrix.st_strategies | array[string] | ST 战略（优势×威胁：多元化） |
| tows_matrix.wt_strategies | array[string] | WT 战略（劣势×威胁：防御型） |
| tows_matrix.priority | array[string] | 战略优先级排序（含依据） |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，工作坊采集）：** 经 `templates/swot_factors_collection.md` 四象限采集矩阵在工作坊现场填写（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 的 `internal_factors` / `external_factors` 传入。

**外部基准（印证参照，双源交叉）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业时政新闻（机会/威胁的政策与市场动态印证） | newsapi | 自然语言关键词（如 "新能源汽车 补贴政策"） |
| Web 竞争情报（竞品动向/新进入者威胁印证） | tavily | 自然语言关键词（如 "固态电池 创业公司 融资"） |

**内外交叉验证要求：** 每条机会/威胁至少有一条外部基准印证（或显式标注「内部认知，未经外部印证」）；外部情报与内部认知矛盾时的处置见 `references/data_fusion.md`（冲突分级处理：内部漏判 → 外部基准优先补正；外部无印证 → 双方并列不下结论；方向相反 → 暂停判断，以最新一手内部数据为准复议）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `internal_factors` / `external_factors`（内部数据经 Think prompt 进入分析上下文——模板采集的成果在此参与推理）
2. Think 阶段：规划四象限分析与 TOWS 匹配的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
news = $DATA_SOURCE("newsapi", "新能源汽车 补贴政策")
web = $DATA_SOURCE("tavily", "固态电池 创业公司 融资 商业化进展")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
news_payload = (DATA_SOURCES.get("newsapi") or {}).get("payload")
web_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（arguments）与外部基准（DATA_SOURCES）完成四象限交叉印证
6. Validate 阶段：校验 TOWS 矩阵完备性（四象限策略 + 优先级 + 溯源元数据）
7. 输出 `tows_matrix` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（NewsAPI/Tavily API Key 缺失，`NEWSAPI_API_KEY`/`TAVILY_API_KEY` 未配置） | 411 | **双 Key 敏感降级**：SWOT 内部数据是分析主体——基于工作坊采集的内部因素完成四象限与 TOWS 匹配，机会/威胁标注「未经外部印证的数据缺口」，建议配置 Key 后重跑 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（四象限字段缺失/空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办工作坊采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "internal_factors": {
    "strengths": ["5 —— 固态电池专利储备行业前五（含 3 项独占许可）", "4 —— 与头部车企联合研发关系"],
    "weaknesses": ["3 —— 量产良率 65% 低于行业 80% 基准", "2 —— 品牌认知度不足（B 端渗透率 12%）"]
  },
  "external_factors": {
    "opportunities": ["4 —— 2027 年补贴政策向高能量密度电池倾斜", "3 —— eVTOL 新市场打开"],
    "threats": ["4 —— 宁德时代同类路线量产在即", "3 —— 上游锂价波动"]
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
news = $DATA_SOURCE("newsapi", "新能源汽车 电池补贴 政策 2027")
web = $DATA_SOURCE("tavily", "固态电池 量产 竞争格局")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — SWOT 因素强度 1-5 评分锚点（每档含义 + 正反例）
- `references/workshop_guide.md` — 战略工作坊 2-4 小时引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/swot_factors_collection.md` — 四象限采集矩阵（字段与 input_schema 一一对应，工作坊现场填写）
