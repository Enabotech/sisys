---
slug: scenario-planning
name: 情景规划
version: 1.0.0
tool_name: 情景规划
description: 未来情景构建 + 战略鲁棒性测试，基于 3 个权威外部数据源自动采集驱动因素实证数据
when_to_use:
  - 长期战略规划
  - 不确定性管理
  - 战略鲁棒性测试
when_not_to_use:
  - 短期战术决策
capabilities:
  - scenario_planning
  - long_term_strategy
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - uncertainty
data_sources:
  - name: tavily
    url: https://api.tavily.com
    api_type: rest_json
    ttl_seconds: 86400
    required_fields:
      - indicator
      - value
  - name: ipcc
    url: https://www.ipcc.ch/data
    api_type: csv_download
    ttl_seconds: 2592000
    required_fields:
      - indicator
      - value
  - name: eurostat
    url: https://ec.europa.eu/eurostat/api/dissemination
    api_type: sdmx_json
    ttl_seconds: 604800
    required_fields:
      - indicator
      - value
input_schema:
  type: object
  required:
    - focal_issue
    - time_horizon_years
  properties:
    focal_issue:
      type: string
      description: 核心议题（如 "2035 年欧洲能源结构"）
    time_horizon_years:
      type: integer
      description: 情景年限（5-30 年）
    region_scope:
      type: string
      description: 地域范围（缺省 global）
output_schema:
  type: object
  required:
    - scenarios
    - uncertainty_matrix
    - data_sources
  properties:
    scenarios:
      type: array
      description: 情景剧本列表（2×2 矩阵四情景）
      items:
        type: object
        required: [name, driving_forces, narrative, indicators]
        properties:
          name:
            type: string
            description: 情景名称
          driving_forces:
            type: array
            description: 关键驱动因素
            items:
              type: string
          narrative:
            type: string
            description: 情景叙事
          indicators:
            type: array
            description: 先行指标观测值
            items:
              type: object
    uncertainty_matrix:
      type: object
      description: 不确定性矩阵（双关键不确定性轴定义）
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 情景规划

> 2×2 不确定性矩阵四情景剧本构建工作坊操作手册。数据采集经 `$DATA_SOURCE` 标记由
> 宿主机侧 DataSourceResolver 完成（沙箱无网络不变量），本 SOP 引导 LLM 生成正确的
> 采集代码并基于注入的真实数据完成驱动因素识别、不确定性排序与情景叙事。

## 1. 适用场景

- 长期战略规划：5-30 年视野的战略方向鲁棒性检验（SP 制定期核心输入）
- 不确定性管理：识别高影响 × 高不确定性的关键变量并构建应对预案
- 战略鲁棒性测试：检验现有战略在多种未来情景下的生存能力

## 2. 负向触发

- 短期战术决策（<2 年）：情景规划的时间尺度与方法论不匹配，请直接基于 PESTEL 当前评估决策
- 单一确定性预测场景：本工具产出多情景集合而非点预测，需单点预测请用定量预测工具

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `focal_issue` | string | ✅ | 核心议题（如 "2035 年欧洲能源结构"） |
| `time_horizon_years` | integer | ✅ | 情景年限（5-30 年） |
| `region_scope` | string | 可选 | 地域范围（缺省 "global"） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `scenarios[]` | array | 情景剧本（name/driving_forces/narrative/indicators），2×2 矩阵四情景 |
| `uncertainty_matrix` | object | 双关键不确定性轴定义（ axis 命名 + 两端极值描述） |
| `data_sources[]` | array | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

Think 阶段必须先输出**驱动因素 → 数据源**映射计划，再生成采集代码：

| 驱动因素类别 | 关键指标 | 数据源 |
|-------------|---------|--------|
| 气候与环境 | 排放情景、温控路径、极端天气频次 | ipcc（AR6 情景数据） |
| 能源与经济结构 | 能源结构、产业占比、绿色转型指标 | eurostat（欧盟统计） |
| 技术与社会趋势 | 新兴技术扩散、社会舆情、政策风向 | tavily（趋势 Web 搜索） |

**三角化要求**：每个关键驱动因素必须由全 3 源交叉覆盖（官方情景数据 ipcc + 区域统计
eurostat + 趋势情报 tavily），禁止仅凭单一来源构建情景轴；三角化规范见
`references/triangulation.md`。

## 6. SOP 执行步骤

1. **解析输入**：校验 `focal_issue` / `time_horizon_years` 必填字段
2. **Think**：输出驱动因素清单与数据源映射（§5），初判影响度 × 不确定性
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源至少一个标记；query 为自然语言指标描述（含议题/年限上下文）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取，**必须使用 `.get()` 防御性读取**，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`。
     **部分失败语义**：采集失败的源其键**不在** `DATA_SOURCES` 中（对应标记位注入 `None`）——
     读取返回 `None` 时按 §7 降级话术处理，禁止直接下标（`["payload"]` 会 KeyError 中断）。
     **同源多 query**：同一数据源的多个不同 query 依次分配 `"<name>"` / `"<name>#2"` 键
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成驱动因素影响度 × 不确定性评分
   （锚点见 `references/scoring_anchors.md`），选出双关键不确定性轴
6. **情景构建**：2×2 矩阵生成 4 个情景剧本（框架见 `templates/scenario_narrative_framework.md`），
   每个情景含名称/驱动因素/叙事/先行指标
7. **输出**：按 output_schema 组装，先行指标观测值如实标注来源

采集代码骨架示例：

```python
trends = $DATA_SOURCE("tavily", "欧洲能源转型 技术趋势 2035")
climate = $DATA_SOURCE("ipcc", "IPCC AR6 SSP 排放情景数据")
eu_energy = $DATA_SOURCE("eurostat", "欧盟 能源结构 可再生能源占比")

# 采集后通过注入的 DATA_SOURCES dict 读取
ipcc_payload = (DATA_SOURCES.get("ipcc") or {}).get("payload")
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，情景构建基于其余来源完成，相关驱动因素置信度下调并标注」 |
| 411 未注册（Key 缺失） | tavily 未配置 API Key，冷启动未注册 | 「数据源 tavily 因 API Key 未配置未注册，趋势情报维度基于官方数据完成，**输出中显式标注数据缺口**：缺少实时趋势舆情印证」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在溯源字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 3 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：部分失败不中断情景构建；所有降级必须在输出 `data_sources` 溯源元数据中
如实反映，禁止以估计值冒充采集值。

## 8. input_examples

```json
{
  "focal_issue": "2035 年欧洲能源结构",
  "time_horizon_years": 10,
  "region_scope": "eu"
}
```

对应采集 query 构造示例（环境变量引用形式，禁止写入真实 API Key）：
`api_key=os.environ['TAVILY_API_KEY']`（由宿主机侧适配器配置持有，沙箱代码不可见）。

## 9. References 指引

- `references/triangulation.md` — 情景数据三角化规范（3 源分工与冲突裁决）
- `references/scoring_anchors.md` — 不确定性矩阵锚点（影响度 × 不确定性分级定义）
- `references/workshop_guide.md` — 情景构建工作坊引导（剧本开发流程/角色/话术）
- `templates/scenario_narrative_framework.md` — 情景剧本框架模板（4 情景结构）
