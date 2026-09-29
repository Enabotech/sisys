---
slug: value-chain-analysis
name: 价值链分析
version: 1.0.0
tool_name: 价值链分析
description: Porter 价值链（主活动 + 支持活动）成本/价值分析
when_to_use:
  - 成本结构诊断
  - 竞争优势定位
  - 运营优化
when_not_to_use:
  - 战略定位选择
capabilities:
  - value_chain
  - cost_analysis
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - competitive
data_sources:
  - name: tavily
    url: https://api.tavily.com
    api_type: rest_json
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
  - name: china-nbs
    url: https://www.stats.gov.cn
    api_type: crawler
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required: [enterprise_data]
  properties:
    enterprise_data:
      type: object
      description: 企业内部数据（ERP 导出 + 流程访谈，模板 value_chain_activities_inventory.md）。条目编码——primary/support_activities 逐条「贡献分值（1-5）—— 活动描述」（贡献分值 = 首个『 —— 』前的 1-5 整数；优势环节判定阈值 ≥4 依赖分值解析）；cost_structure 键值形态「活动 → 对象（键为 成本金额/占比）」（证据来源留档模板）
      required: [primary_activities, support_activities, cost_structure]
      properties:
        primary_activities:
          type: array
          description: 主要活动清单（进料储运/生产/发货/营销/服务）
          items:
            type: string
        support_activities:
          type: array
          description: 支持活动清单（采购/技术开发/人力资源/企业基础设施）
          items:
            type: string
        cost_structure:
          type: object
          description: 成本归属（活动 → 成本金额/占比）
output_schema:
  type: object
  required: [value_chain_analysis, data_sources]
  properties:
    value_chain_analysis:
      type: object
      description: 价值链分析结果（价值贡献 + 竞争优势定位）
      required: [value_contribution, competitive_advantages]
      properties:
        value_contribution:
          type: object
          description: 各活动价值贡献度
        competitive_advantages:
          type: array
          description: 竞争优势环节清单（对照行业基准）
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 价值链分析

> Porter 价值链分解（主要活动 + 支持活动）+ 成本/价值驱动分析 + 行业基准对照，定位竞争优势环节。
> 混合数据型工具：内部数据（ERP 导出 + 流程访谈的活动清单与成本归属）是分析主体，
> 外部数据源（Tavily/国家统计局）仅提供行业价值链结构与成本基准的对照参照。

## 1. 适用场景
- 成本结构诊断（活动级成本归属与降本机会识别）
- 竞争优势定位（识别价值创造环节 vs 行业基准）
- 运营优化（跨活动流程改进优先级排序）

## 2. 负向触发
- 战略定位选择（内外部态势与战略匹配）：请用 swot-tows 或 ge-mckinsey-matrix
- 外部环境扫描（宏观/政策/技术趋势）：请用 pestel-analysis
- 单纯的组织与职责设计：请用 org-design-framework

## 3. 输入字段（input_schema）

`enterprise_data` 为嵌套对象（容器键以分区承载），字段表用「容器.字段」表示：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| enterprise_data | object | ✅ | 企业内部数据（ERP 导出 + 流程访谈；条目编码见下三行） |
| enterprise_data.primary_activities | array[string] | ✅ | 主要活动清单（逐条「贡献分值（1-5）—— 活动描述」） |
| enterprise_data.support_activities | array[string] | ✅ | 支持活动清单（采购/技术开发/人力资源/企业基础设施） |
| enterprise_data.cost_structure | object | ✅ | 成本归属（活动 → 成本金额/占比） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| value_chain_analysis | object | 价值链分析结果（价值贡献 + 竞争优势定位） |
| value_chain_analysis.value_contribution | object | 各活动价值贡献度 |
| value_chain_analysis.competitive_advantages | array[string] | 竞争优势环节清单（对照行业基准） |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，ERP 导出 + 流程访谈）：** 经 `templates/value_chain_activities_inventory.md`
活动盘点清单由流程访谈采集（活动清单逐条登记）+ ERP 财务模块按活动科目导出成本归属
（会前 T-3 天分发预填指引，见 `references/workshop_guide.md`），会后将模板字段构造为
`ToolCall.arguments` 的 `enterprise_data` 传入。

**外部基准（对照参照，双源交叉）：**

| 外部对照目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业价值链结构情报（分工形态/外包惯例/标杆环节） | tavily | 自然语言关键词（如 "动力电池 价值链 分工 结构"） |
| 行业统计对标（分行业成本/收益官方统计） | china-nbs | 站点相对路径（如 "sj/zxfb" 最新发布 / "sj/hyf" 分行业数据——路径不携带行业参数，行业定位经返回数据判读） |

**内外交叉验证要求：** 每个活动的价值贡献判断须有至少一条外部基准对照（或显式标注
「内部判断，未经外部对照」）；成本占比明显高于行业基准的环节须在分析结论中单独列示；
外部基准与内部成本数据矛盾时的处置见 `references/data_fusion.md`（冲突分级处理：
内部漏判 → 外部基准优先补正；外部无印证 → 双方并列不下结论；方向相反 → 暂停判断，以最新一手内部数据为准复议）。**同源多 query（name/name#2 键）不构成独立来源**——外部印证须来自不同源。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `enterprise_data`（内部数据经 Think prompt 进入分析上下文——
   活动盘点与 ERP 成本归属在此参与推理）
2. Think 阶段：规划价值链分解、成本/价值驱动分析与基准对照的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
web = $DATA_SOURCE("tavily", "动力电池 价值链 分工 结构 外包")
nbs = $DATA_SOURCE("china-nbs", "sj/zxfb")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
web_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
nbs_payload = (DATA_SOURCES.get("china-nbs") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（arguments）与外部基准（DATA_SOURCES）完成活动价值贡献评分
   （锚点见 `references/scoring_anchors.md`）与竞争优势环节定位
6. Validate 阶段：校验分析结果完备性（活动覆盖 + 价值贡献 + 优势清单 + 溯源元数据）
7. 输出 `value_chain_analysis` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；
**禁止**任何形式的沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；
标记数据源名必须在 frontmatter 白名单内（207 策略违规）。每源采集结果量以适配器默认分页为准（SOP 引导代码不得显式请求超量数据）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（Tavily API Key 缺失，`os.environ['TAVILY_API_KEY']` 未配置） | 411 | **Key 敏感降级**：企业内部数据是分析主体——基于 ERP 成本归属完成价值链分解与贡献评分，行业结构对照标注「未经外部印证的数据缺口」，建议配置 Key 后重跑 |
| china-nbs crawler daemon 未运行（爬虫源不可用） | 411 | **crawler 降级**：基于内部数据 + tavily 其余源继续分析，行业统计对标标注数据缺口，待 crawler daemon 恢复后补采 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（活动清单缺失/成本归属空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办流程访谈与 ERP 导出（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "enterprise_data": {
    "primary_activities": [
      "3 —— 进料储运：电芯原材料入库与仓储",
      "5 —— 生产：电芯组装与化成分容（直通率行业领先）",
      "3 —— 发货：整机厂直供物流",
      "3 —— 营销：车企大客户拓展",
      "3 —— 服务：质保与残值评估"
    ],
    "support_activities": [
      "4 —— 采购：正极材料集中采购（议价能力）",
      "5 —— 技术开发：电芯配方研发",
      "3 —— 人力资源：产线技师培养",
      "2 —— 企业基础设施：财务与合规"
    ],
    "cost_structure": {
      "生产": {"成本金额": "3.2 亿元", "占比": "58%"},
      "采购": {"成本金额": "1.1 亿元", "占比": "20%"}
    }
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
web = $DATA_SOURCE("tavily", "动力电池 价值链 分工 结构")
nbs = $DATA_SOURCE("china-nbs", "sj/zxfb")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（对照流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — 活动价值贡献 1-5 评分锚点（每档含义 + 正反例 + 聚合规则）
- `references/workshop_guide.md` — 流程访谈 + ERP 导出引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/value_chain_activities_inventory.md` — 活动盘点清单（字段与 input_schema 一一对应，访谈现场填写）
