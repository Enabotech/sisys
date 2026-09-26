---
slug: porters-five-forces
name: 波特五力
version: 1.0.0
tool_name: 波特五力
description: 行业竞争结构五力分析（供应商/买方/替代品/新进入者/现有竞争），基于 3 个权威外部数据源自动采集实证数据
when_to_use:
  - 行业吸引力评估
  - 竞争结构分析
  - 进入新市场决策
when_not_to_use:
  - 企业内部诊断请用 value-chain-analysis
capabilities:
  - industry_analysis
  - competitive_structure
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - external
data_sources:
  - name: newsapi
    url: https://newsapi.org
    api_type: rest_json
    ttl_seconds: 21600
    required_fields:
      - indicator
      - value
  - name: world-bank
    url: https://api.worldbank.org/v2
    api_type: rest_json
    ttl_seconds: 604800
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
    - industry
    - region_scope
  properties:
    industry:
      type: string
      description: 目标行业
    region_scope:
      type: string
      description: 地域范围
    incumbent_players:
      type: array
      description: 可选已知在位企业清单
      items:
        type: string
output_schema:
  type: object
  required:
    - five_forces
    - overall_attractiveness
    - data_sources
  properties:
    five_forces:
      type: array
      description: 五力评估结果（每力含评分/证据/来源）
      items:
        type: object
        required: [force, score, evidence, sources]
        properties:
          force:
            type: string
            enum: [现有竞争, 新进入者威胁, 替代品威胁, 供应商议价力, 购买者议价力]
            description: 五力名称
          score:
            type: number
            description: 力量强度评分（0-1，越大压力越强）
          evidence:
            type: array
            description: 支撑证据列表
            items:
              type: string
          sources:
            type: array
            description: 数据来源
            items:
              type: string
    overall_attractiveness:
      type: string
      enum: [高, 中, 低]
      description: 行业综合吸引力评级
    data_sources:
      type: array
      description: 溯源元数据（source/freshness/confidence）
      items:
        type: object
---

# 波特五力

> 行业竞争结构五力分析工作坊操作手册。数据采集经 `$DATA_SOURCE` 标记由宿主机侧
> DataSourceResolver 完成（沙箱无网络不变量），本 SOP 引导 LLM 生成正确的采集代码
> 并基于注入的真实数据完成五力强度评分与行业吸引力综合研判。

## 1. 适用场景

- 行业吸引力评估：进入/退出/加码某行业前对竞争结构强度的系统性评估
- 竞争结构分析：SP 制定期对现有竞争/新进入者/替代品/供应商/购买者五力的结构化诊断
- 进入新市场决策：为新市场进入（market entry）决策提供行业盈利潜力实证依据

## 2. 负向触发

- 企业内部诊断请用 value-chain-analysis（内部价值链视角，非行业结构）
- 宏观环境六维度扫描请用 pestel-analysis（宏观外部环境，非中观行业结构）
- 企业内部资源能力评估请用 vrio-framework（内部视角，非行业竞争）
- 纯定性专家判断场景（本工具以数据驱动为核心价值，无数据需求的快速研讨不必调用）

## 3. 输入字段（input_schema）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `industry` | string | ✅ | 目标行业（如 "动力电池"） |
| `region_scope` | string | ✅ | 地域范围（"global" / "china" / "eu" 等） |
| `incumbent_players` | array | 可选 | 已知在位企业清单（聚焦竞争与舆情采集） |

## 4. 输出字段（output_schema）

| 字段 | 类型 | 说明 |
|------|------|------|
| `five_forces[]` | array | 五力评估（force/score/evidence/sources），score 0-1 越大压力越强 |
| `overall_attractiveness` | enum | 行业综合吸引力评级（高 / 中 / 低） |
| `data_sources[]` | array | 溯源元数据（source/freshness/confidence） |

## 5. 数据采集计划（Think 阶段引导）

Think 阶段必须先输出**五力 → 指标 → 数据源**映射计划，再生成采集代码：

| 五力 | 关键指标 | 数据源 |
|------|---------|--------|
| 现有竞争 | 市场集中度、产能利用率、价格战舆情、并购动态 | newsapi（竞争/并购新闻）、world-bank（行业增加值与集中度旁证）、eurostat（欧盟行业企业数/营业额结构） |
| 新进入者威胁 | 进入壁垒、资本开支门槛、新玩家融资/建厂动态 | newsapi（新进入者/融资新闻）、world-bank（营商便利度、固定资产投资） |
| 替代品威胁 | 替代技术渗透率、跨行业替代舆情 | newsapi（替代技术新闻）、eurostat（欧盟相关行业产出结构变化） |
| 供应商议价力 | 上游集中度、原材料价格波动、供应商纵向整合 | newsapi（供应链/涨价新闻）、world-bank（大宗商品与贸易指标） |
| 购买者议价力 | 下游集中度、转换成本、采购招标动态 | newsapi（大客户/招标新闻）、eurostat（欧盟下游行业采购结构） |

**三角化要求**：本 Skill 声明源共 3 个，三角化 = **全 3 源覆盖**——每个力的关键指标
须由 newsapi + world-bank + eurostat 三源共同印证（三角化规范见
`references/triangulation.md`）；任何一力缺失任一来源印证时，必须在 `sources`
字段如实登记并在 `evidence` 中标注证据强度下调。

## 6. SOP 执行步骤

1. **解析输入**：校验 `industry` / `region_scope` 必填字段，读取可选 `incumbent_players`
2. **Think**：输出五力 → 指标 → 数据源映射（§5），声明各力采集目标
3. **Code**：生成含 `$DATA_SOURCE` 标记的采集代码。**标记使用规范**：
   - 语法：`$DATA_SOURCE("<name>", "<query>")`，name 仅限 frontmatter `data_sources` 白名单
   - 每个声明源恰好一个标记；query 为自然语言指标描述（含行业/地域上下文）
   - **禁止**在沙箱代码中发起任何网络访问（沙箱 `network_mode="none"` 为领域不变量）
   - 采集结果经全局 `DATA_SOURCES` dict 注入读取：`DATA_SOURCES["newsapi"]["payload"]`，
     每项含 `payload` / `source_timestamp` / `freshness_score` / `confidence` / `cache_hit`
4. **Execute**：宿主机侧并发采集并注入 preamble，沙箱执行分析代码
5. **Observe/Validate**：基于注入数据完成五力强度评分（评分锚点见 `references/scoring_anchors.md`）
6. **综合研判**：五力加权汇总得出行业吸引力评级（高/中/低），
   工作坊研讨引导见 `references/workshop_guide.md`
7. **输出**：按 output_schema 组装，每力 `sources` 字段如实登记实际印证来源

采集代码骨架示例：

```python
industry_news = $DATA_SOURCE("newsapi", "动力电池 行业竞争 并购 价格战 新进入者 最新动态")
macro_indicators = $DATA_SOURCE("world-bank", "中国 制造业增加值 固定资产投资 营商便利度指标")
eu_industry_stats = $DATA_SOURCE("eurostat", "欧盟 制造业 结构企业统计 行业营业额与企业数")

# 采集后通过注入的 DATA_SOURCES dict 读取
news_payload = DATA_SOURCES["newsapi"]["payload"]
```

## 7. 失败处理

| 异常 | 语义 | LLM 应对话术 |
|------|------|-------------|
| 411 数据源不可用 | 5xx/连接失败/熔断 | 「数据源 X 暂不可用，本次分析基于其余 N-1 个来源完成，该力结论置信度下调并标注」 |
| 411 未注册（Key 缺失） | newsapi 未配置 API Key，冷启动未注册 | 「数据源 newsapi 因 API Key 未配置未注册，相应力基于其余来源完成，**输出中显式标注数据缺口**：竞争舆情/并购动态维度缺失实时新闻印证」 |
| 412 限流 | 429 配额耗尽 | 「数据源 X 触发限流，使用缓存快照（freshness_score 已折算）并标注数据时效」 |
| 413 解析失败 | 响应格式异常（不可重试） | 「数据源 X 响应解析失败，跳过该源并在 sources 字段中剔除，禁止编造观测值」 |
| 207 白名单违规 | 标记引用未声明数据源 | 不发生（本 SOP 标记严格使用白名单内 3 源）；若出现说明代码生成偏离 SOP，重新按 §6 生成 |

**降级总原则**：部分失败不中断分析；所有降级必须在输出 `data_sources` 溯源元数据与
五力 `sources` 字段中如实反映，禁止以估计值冒充采集值。

## 8. input_examples

```json
{
  "industry": "动力电池",
  "region_scope": "china",
  "incumbent_players": ["宁德时代", "比亚迪", "中创新航", "亿纬锂能"]
}
```

对应采集 query 构造示例（环境变量引用形式，禁止写入真实 API Key）：
`api_key=os.environ['NEWSAPI_API_KEY']`（由宿主机侧适配器配置持有，沙箱代码不可见）。

## 9. References 指引

- `references/triangulation.md` — 五力三角化规范（3 源分工与冲突裁决流程）
- `references/scoring_anchors.md` — 五力强度 0-1 评分锚点（分档定义与示例）
- `references/workshop_guide.md` — 五力工作坊引导方法论（研讨流程/角色/话术）
- `templates/porters_industry_questionnaire.md` — 行业问卷模板（五力逐项问题清单，工作坊填写用）
