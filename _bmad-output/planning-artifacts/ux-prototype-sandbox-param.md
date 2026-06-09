# SISYS 组织级统一参数体系 — BLM/BEM SP六阶段 × BP六阶段 × 市场洞察六子步 全对齐（终版）

## 总览

| 归属 | 阶段 | 参数数 |
|---|---|---|
| **SP** | [1]业绩差距分析 [2]市场洞察(六子步) [3]战略意图 [4]创新焦点 [5]业务设计 [6]执行设计 | **56** |
| **BP** | [1]澄清战略方向 [2]导出战略举措 [3]导出衡量指标 [4]确定措施目标 [5]分解措施目标 [6]导出工作计划 | **30** |
| **合计** | **SP六阶段×BP六阶段×市场洞察六子步** | **86** |

---

# 上卷：SP 六阶段 56 参数（BLM 战略环）

## SP[1] 业绩差距分析 — 7 参数
> 对标：SWOT-TOWS、KPI历史对比、价值链分析、GE-麦肯锡矩阵
> 主导 CEO + CFO + COO | 协作 AUD
> or.md 产出物：业绩差距量化报告、根因分析矩阵、业务组合健康度图谱

| # | 参数键 | 中文名 | 单位 | 定义 | 对应产出物 |
|---|---|---|---|---|---|
| 1 | `revenue_gap_pct` | 收入差距率 | % | (目标-实际)/目标 | 业绩差距量化报告 |
| 2 | `profit_gap_pct` | 利润差距率 | % | (目标-实际)/目标 | 业绩差距量化报告 |
| 3 | `mkt_share_gap_pct` | 市占率差距 | % | 目标-当前市占率 | 业绩差距量化报告 |
| 4 | `operational_efficiency_gap` | 运营效率差距 | % | 行业标杆-自身效率 | 根因分析矩阵 |
| 5 | `portfolio_health_score` | 业务组合健康度 | 1-5 | GE-麦肯锡综合评分 | 业务组合健康度图谱 |
| 6 | `gap_root_cause_clarity` | 差距根因清晰度 | 1-5 | 有明确根因的差距占比(5=全明确) | 根因分析矩阵 |
| 7 | `historical_trend_alignment` | 历史趋势一致性 | 1-5 | 当前业绩与3年趋势吻合度 | 历史绩效对比 |

## SP[2] 市场洞察 — 18 参数
> 对标：PESTEL、$APPEALS、波特五力、价值链、VRIO、安索夫矩阵、GE-麦肯锡、情景规划
> 主导 CEO+CTO+CMO+COO+CFO+CHO

### (1) 看趋势 — 5 参数
> 对标：PESTEL、情景规划 | 主导 CEO+CTO | 协作 CMO+CFO

| # | 参数键 | 中文名 | 单位 | 定义 |
|---|---|---|---|---|
| 8 | `mkt_size_tam` | 总可用市场 | ¥亿 | TAM—100%渗透理想规模 |
| 9 | `mkt_growth_cagr` | 市场复合增速 | % | 未来3-5年CAGR |
| 10 | `policy_support_level` | 政策支持度 | 1-5 | 产业政策/补贴/准入综合 |
| 11 | `tech_maturity` | 技术成熟度 | TRL 1-9 | 核心技术就绪水平 |
| 12 | `scenario_plausibility_range` | 情景可信度区间 | % | 多情景推演基准情景概率范围 |

### (2) 看市场与客户 — 3 参数
> 对标：$APPEALS、价值主张画布 | 主导 CMO+COO | 协作 CEO+CFO

| # | 参数键 | 中文名 | 单位 | 定义 |
|---|---|---|---|---|
| 13 | `customer_need_clarity` | 客户需求清晰度 | 1-5 | $APPEALS九维度覆盖完整度 |
| 14 | `value_prop_competitiveness` | 价值主张竞争力 | 1-5 | 客户痛点-收益映射优于竞品程度 |
| 15 | `mkt_segment_attractiveness` | 市场细分吸引力 | 1-5 | 规模×增速×竞争强度综合 |

### (3) 看竞争 — 4 参数
> 对标：波特五力、竞争对手分析 | 主导 CEO+CMO | 协作 CTO+CFO

| # | 参数键 | 中文名 | 单位 | 定义 |
|---|---|---|---|---|
| 16 | `mkt_concentration` | 市场集中度 | % | Top3品牌合计份额 |
| 17 | `comp_lead_months` | 竞品先发优势 | 月 | 主要竞品领先时间窗口 |
| 18 | `substitution_threat` | 替代品威胁 | 1-5 | 可获得性×性价比×转换成本 |
| 19 | `entry_barrier_strength` | 进入壁垒强度 | 1-5 | 资金/技术/渠道/品牌综合 |

### (4) 看自己 — 3 参数
> 对标：价值链、VRIO、SWOT-TOWS | 主导 COO+CFO | 协作 CHO+CTO

| # | 参数键 | 中文名 | 单位 | 定义 |
|---|---|---|---|---|
| 20 | `core_capability_vrio_score` | 核心能力VRIO得分 | 1-5 | 有价值/稀缺/难模仿/组织支持均值 |
| 21 | `resource_constraint_index` | 资源约束指数 | 1-5 | 资金/人才/时间三维综合(5=极强) |
| 22 | `internal_process_efficiency` | 内部流程效率 | % | 价值链各环节 vs 行业基准 |

### (5) 看机会 — 2 参数
> 对标：安索夫矩阵、SWOT-TOWS | 主导 CEO+CMO | 协作 CTO+CFO

| # | 参数键 | 中文名 | 单位 | 定义 |
|---|---|---|---|---|
| 23 | `opportunity_pool_size` | 机会池规模 | 个 | 可量化战略机会总数 |
| 24 | `growth_path_feasibility` | 增长路径可行性 | 1-5 | 安索夫四象限最可行路径成功概率 |

### (6) 机会差距分析 — 1 参数
> 对标：GE-麦肯锡、SWOT-TOWS | 主导 CEO+CFO | 协作 COO+CMO

| # | 参数键 | 中文名 | 单位 | 定义 |
|---|---|---|---|---|
| 25 | `capability_opportunity_match` | 能力-机会匹配度 | 1-5 | GE-麦肯锡高能-高机会象限占比 |

## SP[3] 战略意图与目标 — 9 参数
> 对标：BSC四维度、战略地图 | 主导 CEO+CFO | 协作 COO+CHO+AUD

| # | 参数键 | 中文名 | 单位 | BSC维度 | 定义 |
|---|---|---|---|---|---|
| 26 | `revenue_target_3y` | 三年营收目标 | ¥亿 | 财务 | SP规划期末年营收 |
| 27 | `gross_margin_target` | 毛利率目标 | % | 财务 | 规划期末综合毛利率 |
| 28 | `roe_target` | 净资产收益率目标 | % | 财务 | 规划期末ROE |
| 29 | `mkt_share_target` | 市场份额目标 | % | 客户 | 规划期末目标市占率 |
| 30 | `brand_awareness_target` | 品牌认知度目标 | % | 客户 | 目标客群提示后认知率 |
| 31 | `innovation_revenue_ratio` | 创新收入占比 | % | 流程 | 新产品/新业务收入占比 |
| 32 | `patent_count_target` | 专利目标数 | 项 | 流程 | 年度新增发明专利申请 |
| 33 | `talent_density_target` | 人才密度目标 | % | 学习成长 | 关键岗位高级人才占比 |
| 34 | `strategy_map_coherence` | 战略地图一致性 | 1-5 | — | BSC四维度因果链逻辑一致性 |

## SP[4] 创新焦点 — 6 参数
> 对标：破坏性创新模型、价值曲线分析、商业模式画布、安索夫矩阵
> 主导 CTO+CEO | 协作 CMO+CFO

| # | 参数键 | 中文名 | 单位 | 创新类型 | 定义 |
|---|---|---|---|---|---|
| 35 | `tech_innovation_level` | 技术创新度 | 1-5 | 价值创新 | 核心技术相对行业领先度 |
| 36 | `value_curve_differentiation` | 价值曲线差异度 | 1-5 | 价值创新 | 价值曲线相对竞品偏离度 |
| 37 | `disruptive_risk_readiness` | 破坏性创新就绪度 | 1-5 | 价值创新 | 对破坏性创新的防御/进攻能力 |
| 38 | `business_model_innovativeness` | 商业模式创新度 | 1-5 | 模式创新 | 画布九要素新颖程度 |
| 39 | `new_market_entry_feasibility` | 新市场进入可行性 | 1-5 | 模式创新 | 新产品×新市场成功概率 |
| 40 | `innovation_pipeline_strength` | 创新管道强度 | 个 | — | 在研/在测/待发项目数 |

## SP[5] 业务设计 — 8 参数
> 对标：商业模式画布、GE-麦肯锡、SPACE矩阵、价值主张画布
> 主导 CEO+CFO | 协作 COO+CTO+CMO

| # | 参数键 | 中文名 | 单位 | 业务设计要素 | 定义 |
|---|---|---|---|---|---|
| 41 | `customer_selection_clarity` | 客户选择清晰度 | 1-5 | 客户选择 | 目标客户细分与优先级明确度 |
| 42 | `value_prop_clarity` | 价值主张清晰度 | 1-5 | 价值主张 | 差异化与认知一致性 |
| 43 | `profit_model_viability` | 盈利模式可行性 | 1-5 | 盈利模式 | 收入流×成本结构可持续性 |
| 44 | `strategic_control_strength` | 战略控制点强度 | 1-5 | 战略控制 | 护城河/粘性/转换成本综合 |
| 45 | `business_portfolio_balance` | 业务组合均衡度 | 1-5 | 业务组合 | GE-麦肯锡各象限分布合理度 |
| 46 | `strategic_position_score` | 战略定位得分 | 1-5 | 战略定位 | SPACE矩阵四维度综合 |
| 47 | `activity_system_fit` | 活动系统匹配度 | 1-5 | 活动系统 | 各要素内部一致性 |
| 48 | `customer_retention_rate` | 客户留存率 | % | 客户粘性 | 年度续约/复购率 |

## SP[6] 执行设计 — 8 参数
> 对标：BSC（CSF识别）、KPI体系、ADKAR变革模型、组织设计框架
> 主导 COO+CHO | 协作 CEO+CFO+CTO

| # | 参数键 | 中文名 | 单位 | 执行要素 | 定义 |
|---|---|---|---|---|---|
| 49 | `critical_task_readiness` | 关键任务就绪度 | 1-5 | 关键任务 | 依赖解决+资源到位任务占比 |
| 50 | `task_dependency_complexity` | 任务依赖复杂度 | 条 | 关键任务 | 前置/依赖关系总数 |
| 51 | `kpi_system_completeness` | KPI体系完整度 | % | KPI体系 | 四BSC维度均有KPI的比例 |
| 52 | `org_capability_gap` | 组织能力差距 | 1-5 | 组织能力 | 需求能力-现有能力差距 |
| 53 | `change_readiness_score` | 变革就绪度 | 1-5 | 变革管理 | ADKAR五阶段平均得分 |
| 54 | `culture_alignment` | 文化一致性 | 1-5 | 文化 | 现有-目标文化差距 |
| 55 | `talent_pipeline_strength` | 人才管道强度 | % | 人力策略 | 关键岗位继任就绪率 |
| 56 | `resource_allocation_efficiency` | 资源分配效率 | % | 资源匹配 | 实际 vs 最优分配偏差 |

---

# 下卷：BP 六阶段 30 参数（BEM 执行环）

## BP[1] 澄清战略方向与运营定义 — 5 参数
> 对标：BSC（战略目标澄清）、战略地图（因果链校验）
> 主导 CEO+COO | 协作 CFO+AUD
> or.md 产出物：年度战略主题、运营定义文档、战略-运营对齐矩阵

| # | 参数键 | 中文名 | 单位 | 定义 | 输入依赖 |
|---|---|---|---|---|---|
| 57 | `sp_bp_alignment_rate` | SP-BP映射完整度 | % | 有BP举措支撑的SP控制点比例 | SP[5]→BP[1] |
| 58 | `strategic_theme_clarity` | 战略主题清晰度 | 1-5 | 年度战略主题被各层级理解程度 | SP[3]#34→#58 |
| 59 | `operational_definition_precision` | 运营定义精确度 | 1-5 | SP战略语言→可量化运营定义的程度 | SP[5]→#59 |
| 60 | `strategy_op_consistency` | 战略-运营一致性 | % | 战略-运营对齐矩阵中无冲突项占比 | AUD审计 |
| 61 | `annual_theme_cascading_rate` | 年度主题穿透率 | % | 各部门规划中明确引用年度主题的比例 | — |

## BP[2] 导出中长期关键战略举措 — 5 参数
> 对标：SPACE矩阵、安索夫矩阵、GE-麦肯锡矩阵
> 主导 CEO+CFO | 协作 COO+CTO
> or.md 产出物：战略举措清单、举措优先级排序、资源分配建议

| # | 参数键 | 中文名 | 单位 | 定义 | 输入依赖 |
|---|---|---|---|---|---|
| 62 | `initiative_coverage_rate` | 举措覆盖完整度 | % | 覆盖SP全部战略意图的举措占比 | SP[3]→#62 |
| 63 | `priority_consensus_score` | 优先级共识度 | 1-5 | 高管团队对举措优先级排序的一致程度 | — |
| 64 | `resource_allocation_rationality` | 资源分配合理度 | 1-5 | GE-麦肯锡优先级与资源分配一致性 | SP[1]#5→#64 |
| 65 | `initiative_feasibility_score` | 举措可行性得分 | 1-5 | 基于历史同类举措成功率+资源约束 | — |
| 66 | `cross_initiative_synergy` | 跨举措协同度 | 1-5 | 举措间相互增强关系 vs 冲突关系比例 | — |

## BP[3] 导出战略衡量指标 — 5 参数
> 对标：BSC（指标分解）、KPI、平衡计分卡指标库
> 主导 CFO+COO | 协作 CEO+AUD
> or.md 产出物：战略衡量指标体系、指标定义文档、指标目标值

| # | 参数键 | 中文名 | 单位 | 定义 | 输入依赖 |
|---|---|---|---|---|---|
| 67 | `metric_coverage_rate` | 指标覆盖率 | % | 每个战略举措有≥1个量化指标的比例 | BP[2]→#67 |
| 68 | `metric_cascading_depth` | 指标穿透层级 | 层 | KPI公司→部门→个人分解层级(理想≥3) | — |
| 69 | `metric_target_ambition` | 指标目标挑战度 | 1-5 | 目标值相对行业基准的挑战程度 | — |
| 70 | `metric_measurability` | 指标可度量性 | % | 有明确数据源+采集频率的指标占比 | — |
| 71 | `lead_lag_indicator_ratio` | 先导/滞后指标比 | 比率 | 先导性指标数/滞后性指标数(理想>1) | — |

## BP[4] 确定年度业务关键措施并导出具体目标 — 5 参数
> 对标：BSC（措施-目标映射）、KPI（年度目标分解）、价值链分析
> 主导 COO+CFO | 协作 CHO+CTO+CMO
> or.md 产出物：年度业务关键措施清单、具体目标文档、预算分配方案

| # | 参数键 | 中文名 | 单位 | 定义 | 输入依赖 |
|---|---|---|---|---|---|
| 72 | `measure_smart_concreteness` | 措施SMART具体度 | 1-5 | Specific+Measurable+Achievable+Relevant+Time-bound满足度 | — |
| 73 | `budget_measure_alignment` | 预算-措施匹配度 | % | 预算分配与措施优先级一致性 | — |
| 74 | `target_achievability_score` | 目标可实现性 | 1-5 | 基于历史达成率+资源约束的可行性 | SP[1]→#74 |
| 75 | `measure_strategy_traceability` | 措施-战略可追溯性 | % | 能追溯到具体SP控制点的措施比例 | BP[1]→#75 |
| 76 | `cross_functional_coverage` | 跨功能覆盖度 | % | 涉及≥2个部门的措施占比(理想>40%) | — |

## BP[5] 分解关键措施和目标 — 5 参数
> 对标：BSC（层级分解）、KPI（目标-责任矩阵）、RACI矩阵
> 主导 COO+CHO | 协作 CFO+各功能 Agent
> or.md 产出物：措施分解结构、目标-责任矩阵、部门级行动计划

| # | 参数键 | 中文名 | 单位 | 定义 | 输入依赖 |
|---|---|---|---|---|---|
| 77 | `owner_accountability_rate` | 责任人明确度 | % | 有唯一明确负责人的措施/子措施比例 | — |
| 78 | `decomposition_granularity` | 分解粒度 | 层 | 公司→部门→个人有效分解层级数 | — |
| 79 | `raci_completeness` | RACI完整度 | % | RACI矩阵中无遗漏/无冲突项占比 | — |
| 80 | `dept_commitment_rate` | 部门承诺率 | % | 部门负责人已签署确认的措施占比 | — |
| 81 | `cascading_consistency` | 分解一致性 | 1-5 | 分解后子目标加总=父目标的程度 | AUD审计 |

## BP[6] 导出重点工作计划 — 5 参数
> 对标：BSC（行动方案模板）、KPI行动方案（措施-资源-时间三维）、甘特图
> 主导 COO+CFO | 协作 CHO+各功能 Agent
> or.md 产出物：年度重点工作计划、资源需求计划、时间轴里程碑

| # | 参数键 | 中文名 | 单位 | 定义 | 输入依赖 |
|---|---|---|---|---|---|
| 82 | `plan_3d_completeness` | 三维规划完整度 | % | 措施-资源-时间三维完整比例 | — |
| 83 | `resource_commitment_rate` | 资源承诺率 | % | 已确认资源的措施/总措施 | — |
| 84 | `milestone_achievability` | 里程碑可达成性 | 1-5 | 基于历史数据的按期完成概率 | SP[1]→#84 |
| 85 | `timeline_resource_feasibility` | 时间-资源可行性 | 1-5 | 甘特图资源负载率(无过载节点) | — |
| 86 | `risk_mitigation_coverage` | 风险缓解覆盖率 | % | 已识别风险中有应对预案的比例 | — |

---

## 三重信任分与全链路参数映射

| 信任维度 | 含义 | 参数层 | 参数数 | 权重分布 |
|---|---|---|---|---|
| 🎯 **方向可信** | 战略方向对吗？ | SP[1]~SP[6] (#1~56) | 56 | 差距认知(0.1)+洞察(0.25)+意图(0.2)+创新(0.15)+设计(0.2)+执行设计(0.1) |
| 🔗 **解码可信** | 战略→执行的翻译质量 | BP[1]~BP[3] (#57~71) | 15 | 方向澄清(0.35)+举措导出(0.35)+指标导出(0.3) |
| ✅ **执行可信** | 能执行并取得结果吗？ | BP[4]~BP[6] (#72~86) | 15 | 措施可行(0.35)+组织到位(0.35)+资源到位(0.3) |

## SP→BP 战略解码衔接

```
SP输出                                   BP输入
──────                                  ──────
SP[1] 业绩差距 → BP[4] 目标可实现性      (#1-7 → #74, #84)
SP[3] 战略意图 → BP[2] 举措覆盖完整度     (#26-34 → #62)
SP[5] 业务设计 → BP[1] SP-BP映射完整度    (#41-48 → #57, #59)
SP[6] 执行设计 → BP[5] 责任明确度         (#49-56 → #77-81)
```

## or.md 全对齐验证

| or.md 条款 | 参数对齐 |
|---|---|
| SP严格遵循BLM六阶段 | ✅ 一~六层每阶段对应，参数标注产出物 |
| 市场洞察包含六子步骤 | ✅ 第二层拆为(1)-(6)共18参 |
| BP严格依赖SP最终输出 | ✅ 每BP参数标注输入依赖(SP#→BP#) |
| 构建战略解码器 | ✅ BP[1]作为解码衔接层，SP[5]→BP[1] |
| Checkpoint机制 | ✅ 86参数=12个Checkpoint×每阶段参数量化快照 |
| 各阶段工具组合 | ✅ 每层标注对标工具(共引用14种战略工具) |
| Agent职责 | ✅ 每层标注主导/协作Agent(7角色全覆盖) |
| 输出JSON思维链 | ✅ 参数=思维链结构化输出维度 |
