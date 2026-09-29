---
slug: change-management
name: 变革管理模型
version: 1.0.0
tool_name: 变革管理模型
description: Kotter 8 步法变革管理（紧迫感→联盟→愿景→沟通→赋能→胜利→巩固→固化）
when_to_use:
  - 组织变革
  - 战略转型
  - 文化重塑
when_not_to_use:
  - 运营优化
capabilities:
  - change_management
  - transformation
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - execution
  - change
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
  required: [change_data]
  properties:
    change_data:
      type: object
      description: 变革数据（访谈采集：变革内容 + 利益相关者立场，模板 change_stakeholder_assessment.md）。条目编码（R2-F7）——stakeholders 逐条「姓名/角色（立场：支持/中立/反对；影响力 1-5；阻力 1-5）」（专项转化规则「影响力 ≥4 且反对」依赖分值解析）
      required: [change_content, stakeholders, resistance_analysis]
      properties:
        change_content:
          type: string
          description: 变革内容描述（范围/目标/驱动因素）
        stakeholders:
          type: array
          description: 利益相关者清单及立场评估
          items:
            type: string
        resistance_analysis:
          type: object
          description: 阻力分析（阻力来源 → 强度/根因）
output_schema:
  type: object
  required: [change_roadmap, data_sources]
  properties:
    change_roadmap:
      type: object
      description: 变革路线图（Kotter 8 步路径 + 里程碑 + 沟通计划）
      required: [path, milestones, communication_plan, risk_mitigation]
      properties:
        path:
          type: array
          description: 变革路径（Kotter 8 步裁剪适配）
          items:
            type: string
        milestones:
          type: array
          description: 里程碑清单（含时间点）
          items:
            type: string
        communication_plan:
          type: object
          description: 沟通计划（对象/渠道/频率/责任人）
        risk_mitigation:
          type: array
          description: 风险缓解措施清单
          items:
            type: string
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 变革管理模型

> Kotter 8 步法：紧迫感 → 联盟 → 愿景 → 沟通 → 赋能 → 短期胜利 → 巩固加速 → 制度固化。
> 混合数据型工具：内部数据（访谈采集的变革内容与利益相关者立场评估）是分析主体，外部数据源
> （NewsAPI/Tavily）仅提供行业变革趋势与实践情报的外部印证参照。

## 1. 适用场景
- 组织变革（组织架构/流程/权责的结构性调整落地）
- 战略转型（SP→BP 转换期的组织承接路径规划）
- 文化重塑（价值观与行为规范的长期变革路线）

## 2. 负向触发
- 运营优化（流程效率/精益改善，非组织性变革）：请用 value-chain-analysis
- 执行排期与责任分配（无组织变革语义）：请用 gantt-chart 或 raci-matrix
- 绩效指标体系设计：请用 bsc-scorecard

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| change_data | object | ✅ | 变革数据（访谈采集：变革内容 + 利益相关者立场；条目编码见下行） |
| change_data.change_content | string | ✅ | 变革内容描述（范围/目标/驱动因素） |
| change_data.stakeholders | array[string] | ✅ | 利益相关者清单（逐条「姓名/角色（立场：支持/中立/反对；影响力 1-5；阻力 1-5）」） |
| change_data.resistance_analysis | object | ✅ | 阻力分析（阻力来源 → 强度/根因） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| change_roadmap | object | 变革路线图（Kotter 8 步路径 + 里程碑 + 沟通计划） |
| change_roadmap.path | array[string] | 变革路径（Kotter 8 步裁剪适配） |
| change_roadmap.milestones | array[string] | 里程碑清单（含时间点） |
| change_roadmap.communication_plan | object | 沟通计划（对象/渠道/频率/责任人） |
| change_roadmap.risk_mitigation | array[string] | 风险缓解措施清单 |
| data_sources | array[object] | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

**内部数据（分析主体，利益相关者访谈采集）：** 经 `templates/change_stakeholder_assessment.md`
变革内容 + 利益相关者立场评估在访谈中逐人填写（会前 T-3 天分发访谈提纲与预填指引，见
`references/workshop_guide.md`），会后将模板字段构造为 `ToolCall.arguments` 的 `change_data`
传入（change_content = 变革范围/目标/驱动因素，stakeholders = 逐人立场与影响力，
resistance_analysis = 阻力来源 → 强度/根因）。

**外部基准（印证参照，双源交叉）：**

| 外部印证目标 | 数据源 | 采集 query 规范 |
| --- | --- | --- |
| 行业变革趋势新闻（同业转型/组织调整动态参照） | newsapi | 自然语言关键词（如 "制造业 组织架构 转型"） |
| 变革实践情报（行业变革方法论/案例/沟通工具参照） | tavily | 自然语言关键词（如 "数字化转型 变革管理 案例"） |

**内外交叉验证要求：** 变革紧迫性论证与行业趋势判断至少有一条外部基准印证（或显式标注「内部认知，
未经外部印证」）；外部趋势与内部变革驱动判断矛盾时的处置见 `references/data_fusion.md`
（冲突分级处理：内部漏判 → 外部基准优先补正；外部无印证 → 双方并列不下结论；方向相反 → 暂停判断，以最新一手内部数据为准复议）。

## 6. SOP 执行步骤

1. 解析 `ToolCall.arguments` 中的 `change_data`（内部数据经 Think prompt 进入分析上下文——
   访谈采集的变革数据在此参与推理）
2. Think 阶段：规划变革准备度评估 + 利益相关者矩阵 + 沟通计划的执行步骤
3. Code 阶段：生成含 `$DATA_SOURCE` 标记的采集代码（每声明源至少 1 个标记，query 按 §5 规范）：

```python
# 每源至少一个标记（沙箱无网络，标记由宿主机侧采集后注入）
news = $DATA_SOURCE("newsapi", "制造业 数字化转型 组织变革 动态")
practice = $DATA_SOURCE("tavily", "数字化转型 变革管理 实践案例 沟通策略")

# 采集结果经注入的 DATA_SOURCES dict 读取（防御性 .get()——失败位为 None）
news_payload = (DATA_SOURCES.get("newsapi") or {}).get("payload")
practice_payload = (DATA_SOURCES.get("tavily") or {}).get("payload")
# 同源多 query 时键为 name#2、name#3（首 query 为裸 name）
```

4. Execute 阶段：宿主机并发采集（部分失败不中断）→ preamble 注入 → 沙箱执行
5. Observe 阶段：结合内部数据（立场与阻力评估）与外部基准（DATA_SOURCES）完成变革准备度评估、
   利益相关者矩阵（影响力 × 立场四象限）与行业变革趋势参照
6. Validate 阶段：校验路线图完备性（Kotter 8 步路径 + 里程碑 + 沟通计划 + 风险缓解 + 溯源元数据）
7. 输出 `change_roadmap` + `data_sources`（溯源元数据：source/freshness/confidence）

**标记使用规范：** `$DATA_SOURCE("<数据源名>", "<query>")` 仅写在 Code 产物代码中；**禁止**任何形式的
沙箱内网络访问（沙箱 `network_mode="none"` 为领域不变量）；标记数据源名必须在 frontmatter 白名单内
（207 策略违规）。

## 7. 失败处理

| 异常场景 | 编码 | 处置 |
| --- | --- | --- |
| 数据源不可用（5xx/连接失败） | 411 | 部分失败收敛：基于内部数据 + 其余源继续分析，输出标注数据缺口 |
| 数据源未注册（NewsAPI/Tavily API Key 缺失，`NEWSAPI_API_KEY`/`TAVILY_API_KEY` 未配置） | 411 | **双 Key 敏感降级**：访谈采集的变革数据是分析主体——基于利益相关者立场与阻力分析完成变革准备度评估与 Kotter 路线图，行业变革趋势参照标注「未经外部印证的数据缺口」，建议配置 Key 后重跑 |
| 数据源限流（429） | 412 | 等待退避重试；重试耗尽按 411 降级话术处理 |
| 响应解析失败 | 413 | 不可重试：丢弃该源数据，按数据缺口降级 |
| 标记源不在白名单 | 207 | 立即失败（策略违规），修正代码标记 |
| 内部数据不足（利益相关者立场缺失/阻力分析空洞） | — | 状态置 `INSUFFICIENT_DATA`，引导补办利益相关者访谈（模板缺口登记区记录） |

## 8. input_examples

```json
{
  "change_data": {
    "change_content": "从职能制转向产品制组织：跨职能产品团队承载端到端损益，2027 年前完成三个试点事业部切换",
    "stakeholders": [
      "CEO（支持；影响力 5；阻力 1：战略转型发起人）",
      "事业部总经理 A（中立；影响力 4；阻力 3：担心试点失败回摆）",
      "职能中台负责人 B（反对；影响力 4；阻力 5：权限与编制被稀释）",
      "一线产品经理群体（支持；影响力 2；阻力 1：授权与成长空间增加）"
    ],
    "resistance_analysis": {
      "职能中台编制焦虑": {"强度": 4, "根因": "岗位重构不确定性"},
      "考核口径切换冲突": {"强度": 3, "根因": "新旧 KPI 并行期目标打架"}
    }
  }
}
```

外部基准 query 独立标记示例（不入 arguments JSON）：

```python
news = $DATA_SOURCE("newsapi", "组织架构 转型 制造业 2026")
practice = $DATA_SOURCE("tavily", "产品制组织 变革 案例 赋能机制")
```

## 9. References 指引

- `references/data_fusion.md` — 内外数据融合规范（交叉验证流程/冲突处理/内外结论权重/基准粒度限制）
- `references/scoring_anchors.md` — 变革准备度/利益相关者影响力 1-5 评分锚点（每档含义 + 正反例）
- `references/workshop_guide.md` — 利益相关者访谈引导（会前准备/流程/角色分工/纪律/跟进）
- `templates/change_stakeholder_assessment.md` — 变革内容与利益相关者立场评估表（字段与
  input_schema 一一对应，访谈现场填写）
