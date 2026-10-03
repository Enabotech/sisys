---
slug: vrio-framework
name: VRIO 框架
version: 1.0.0
tool_name: VRIO 框架
description: 资源/能力 VRIO 四维评估（价值/稀缺性/可模仿性/组织）
when_to_use:
  - 资源能力评估
  - 竞争优势识别
  - 战略资源审计
when_not_to_use:
  - 市场吸引力分析
capabilities:
  - resource_evaluation
  - competitive_advantage
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - internal
data_sources:
  - name: uspto
    url: https://search.patentsview.org
    api_type: rest_json
    ttl_seconds: 2592000
    required_fields:
      - indicator
      - value
  - name: google-patents
    url: https://bigquery.googleapis.com
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - publication_number
      - assignee
      - filing_date
  - name: epo-ops
    url: https://ops.epo.org
    api_type: rest_json
    ttl_seconds: 604800
    required_fields:
      - title
      - applicant
      - filing_date
  - name: tavily
    url: https://api.tavily.com
    api_type: rest_json
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required: [resources]
  properties:
    resources:
      type: array
      description: 资源/能力清单（内部审计 + 高管访谈，模板 vrio_resources_checklist.md）
      items:
        type: object
        required: [name, vrio_scores]
        properties:
          name:
            type: string
            description: 资源/能力名称
          vrio_scores:
            type: object
            description: V-R-I-O 四维度判定（0-1）
            required: [value, rarity, imitability, organization]
            properties:
              value:
                type: number
                description: 价值性 V（是否抓住机会/化解威胁）
              rarity:
                type: number
                description: 稀缺性 R（对照行业专利/能力密度基准）
              imitability:
                type: number
                description: 可模仿性 I（获取难度，对照行业情报）
              organization:
                type: number
                description: 组织利用能力 O（组织是否支持利用）
output_schema:
  type: object
  required: [vrio_assessment, data_sources]
  properties:
    vrio_assessment:
      type: object
      description: VRIO 评估结果（分类 + 可持续性判定）
      required: [classification, sustainability]
      properties:
        classification:
          type: object
          description: 各资源五分类结果（持续竞争优势/暂时竞争优势/未实现潜在优势/竞争均势/竞争劣势，判定链见 scoring_anchors.md）
        sustainability:
          type: string
          description: 持续竞争优势综合判定
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# VRIO 框架

> Barney VRIO：对内部资源/能力逐项做 价值性 V / 稀缺性 R / 可模仿性 I / 组织利用 O 四维判定，
> 经判定链输出 竞争劣势 / 竞争均势 / 暂时竞争优势 / 未实现潜在优势 / 持续竞争优势 五类分类。
> 混合数据型工具：内部数据（内部审计 + 高管访谈的资源清单与判定）是分析主体，外部数据源
> （USPTO/EPO OPS/Tavily）仅提供行业专利密度与能力情报的外部印证基准。

## 1. 适用场景
- 资源能力评估（SP 前内部能力盘点）
- 竞争优势识别（持续优势 vs 暂时优势的判定链甄别）
- 战略资源审计（哪些资源值得追加投入/哪些应维持现状）

## 2. 负向触发
- 市场吸引力分析（行业/市场外部评估）：请用 ge-mckinsey-matrix
- 外部环境扫描（政策/经济/社会/技术/环境/法律）：请用 pestel-analysis
- 内外部因素四象限态势盘点（非逐资源核查）：请用 swot-tows

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| resources | array[object] | ✅ | 资源/能力清单（内部审计 + 高管访谈） |
| resources[].name | string | ✅ | 资源/能力名称 |
| resources[].vrio_scores.value | number | ✅ | 价值性 V（是否抓住机会/化解威胁，0-1） |
| resources[].vrio_scores.rarity | number | ✅ | 稀缺性 R（对照行业专利/能力密度基准，0-1） |
| resources[].vrio_scores.imitability | number | ✅ | 可模仿性 I（获取难度，对照行业情报，0-1） |
| resources[].vrio_scores.organization | number | ✅ | 组织利用能力 O（组织是否支持利用，0-1） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| vrio_assessment | object | VRIO 评估结果（分类 + 可持续性判定） |
| vrio_assessment.classification | object | 各资源五分类结果（持续竞争优势/暂时竞争优势/未实现潜在优势/竞争均势/竞争劣势，判定链见 scoring_anchors.md） |
| vrio_assessment.sustainability | string | 持续竞争优势综合判定 |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，内部审计 + 高管访谈）：** 经 `templates/vrio_resources_checklist.md`
逐资源 V-R-I-O 核查表采集（会前 T-3 天分发审计底稿模板与访谈提纲，见 `references/workshop_guide.md`），
内部审计定 V/O 两维（价值判断与组织利用），高管访谈校准组织利用裁定，会后将模板字段构造为
`ToolCall.arguments` 的 `resources` 传入（逐资源 name + vrio_scores 四维判定）。

**外部基准（印证参照，专利双库 + 市场单源）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业专利密度（稀缺性/可模仿性的专利维度印证——US 口径） | uspto | 英文关键词（如 "solid-state battery"） |
| 行业专利密度（稀缺性/可模仿性的专利维度印证——全球含 CN 口径，assignee 精确聚合） | google-patents | 管道串（如 "keyword=solid-state battery|year=2020-2026"） |
| 行业专利密度（稀缺性/可模仿性的专利维度印证——EP 口径，`pa=` 申请人归因） | epo-ops | CQL 结构化检索式（如 `pa="宁德时代" and ti="solid-state battery"`） |
| 行业能力情报（竞对能力建设/人才/合作动向印证） | tavily | 自然语言关键词（如 "固态电池 专利布局 产能"） |

**内外交叉验证要求：** 每项稀缺性 R / 可模仿性 I 判定至少有一条外部基准印证（或显式标注「内部认知，
未经外部印证」）；外部情报与内部审计判定矛盾时的处置见 `references/data_fusion.md`（冲突分级处理：
内部漏判 → 外部基准优先补正；外部无印证 → 双方并列不下结论；方向相反 → 暂停判断，以最新一手内部数据为准复议）。**同源多 query（name/name#2 键）不构成独立来源**——「至少一条外部基准印证」须来自不同源。

**数据源口径边界**：uspto 仅美国专利口径（评估中日韩主导技术域时样本系统性偏低，结论须标注口径），检索为标题关键词匹配（非申请人结构化检索）；google-patents 为 BigQuery 公共数据集全球书目口径（CN 覆盖 99.96% SSRN 实证、assignee 精确聚合——月度更新新鲜度较低；月配额 1TiB 扫描字节，耗尽按 §7 降级）；epo-ops 为 EPO 欧洲专利口径（`pa=` 申请人结构化检索支持中文企业名直接归因，100+ 专利局含 CN——合并后仍缺 CNIPA 本土实时口径（google-patents 补 CN 全景），按「US+全球+EP 三口径」标注；周配额 4GB/周，耗尽时按 §7 限流行降级并回落可用库口径）；tavily 为 Web 事件级检索（非结构化指标级；CJK query 自动注入 country=china）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `resources`（内部数据经 Think prompt 进入分析上下文——核查表
   采集的逐资源判定在此参与推理）
2. Think 阶段：规划逐资源 V-R-I-O 核查与判定链分类的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
patents = $DATA_SOURCE("uspto", "solid-state battery")
gp_patents = $DATA_SOURCE("google-patents", "keyword=solid-state battery|year=2020-2026")
epo_patents = $DATA_SOURCE("epo-ops", 'ti="solid-state battery"')
intel = $DATA_SOURCE("tavily", "固态电池 专利布局 产能 竞对动向")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
patents_payload = (DATA_SOURCES.get("uspto") or {}).get("payload")
gp_payload = (DATA_SOURCES.get("google-patents") or {}).get("payload")
epo_payload = (DATA_SOURCES.get("epo-ops") or {}).get("payload")
intel_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（V-R-I-O 判定）与外部基准（DATA_SOURCES）复核 R/I 两维——
   专利密度与能力情报是否支持稀缺/难模仿判定
6. Validate 阶段：校验判定链完备性（逐资源分类 + 综合可持续判定 + 溯源元数据）
7. 输出 `vrio_assessment`（classification + sustainability）+ `data_sources`（溯源元数据：
   source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的
沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内
（207 策略违规）。每源采集结果量以适配器默认分页为准（SOP 引导代码不得显式请求超量数据）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（Tavily API Key 缺失 `TAVILY_API_KEY` / uspto Key 缺失 `USPTO_API_KEY` / epo-ops 双凭据门任一缺失 `EPO_OPS_CONSUMER_KEY`+`EPO_OPS_CONSUMER_SECRET`） | 411 | **Key 敏感降级**：VRIO 内部审计数据是分析主体——基于内部审计 + 高管访谈完成 V/O 判定与全判定链分类，R/I 两维标注「未经行业基准印证的数据缺口」（专利双库部分缺失时回落单库/内部口径并标注），建议配置 Key 后重跑 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（资源清单缺失/vrio_scores 四维不全） | — | 状态置 `INSUFFICIENT_DATA`，引导补办内部审计采集（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "resources": [
    {
      "name": "固态电池电解质专利族",
      "vrio_scores": {"value": 1, "rarity": 1, "imitability": 1, "organization": 1}
    },
    {
      "name": "中层项目经理梯队",
      "vrio_scores": {"value": 1, "rarity": 0, "imitability": 0, "organization": 1}
    }
  ]
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
patents = $DATA_SOURCE("uspto", "solid-state battery electrolyte")
intel = $DATA_SOURCE("tavily", "固态电池 竞对 扩产 2026")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — V/R/I/O 判定 0-1 锚点（判定链含义 + 正反例）
- `references/workshop_guide.md` — 内部审计 + 高管访谈引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/vrio_resources_checklist.md` — 逐资源 V-R-I-O 核查表（字段与 input_schema 一一对应，审计现场填写）
