# TOOLS.md — Skills L1 元数据索引（23 个战略工具）

> 启动时全量加载到 L1 metadata cache。Token 预算 ≤1200 tokens（23 行 × ~52 字符）。
> 列：slug | tool_name | category | input | output | description | capabilities | tags

| slug | tool_name | category | input | output | description | capabilities | tags |
|------|---------|----------|-------|--------|-------------|--------------|------|
| pestel-analysis | PESTEL 分析 | environment_analysis | macro_environment | analysis_report | 宏观环境六维度扫描（政治/经济/社会/技术/环境/法律） | environment_analysis, macro_scanning | strategy, external |
| porters-five-forces | 波特五力 | environment_analysis | industry | five_forces_report | 行业竞争结构五力分析（供应商/买方/替代品/新进入者/现有竞争） | industry_analysis, competitive_structure | strategy, external |
| appeals-analysis | $APPEALS | environment_analysis | market_data | appeals_analysis | 顾客价值 8 维度分析（$/A/P/P/E/A/L/S） | customer_analysis, market_segmentation | strategy, customer |
| competitor-analysis | 竞争对手分析 | competitive_analysis | competitors | competitive_landscape | 竞争对手画像 + 战略 + 优势劣势综合分析 | competitor_profiling, strategic_benchmarking | strategy, competitive |
| value-chain-analysis | 价值链分析 | competitive_analysis | company | value_chain_map | Porter 价值链（主活动 + 支持活动）成本/价值分析 | value_chain, cost_analysis | strategy, competitive |
| vrio-framework | VRIO 框架 | competitive_analysis | resource | vrio_assessment | 资源/能力 VRIO 四维评估（价值/稀缺性/可模仿性/组织） | resource_evaluation, competitive_advantage | strategy, internal |
| ansoff-matrix | 安索夫矩阵 | strategic_selection | products, markets | ansoff_matrix | 产品 × 市场 2×2 增长策略矩阵 | growth_strategy, market_expansion | strategy, growth |
| swot-tows | SWOT-TOWS | strategic_selection | swot_factors | tows_strategy | SWOT 内外部因素 + TOWS 四象限战略匹配 | strategic_assessment, option_generation | strategy, swot |
| ge-mckinsey-matrix | GE-麦肯锡矩阵 | strategic_selection | business_units | portfolio_grid | GE/McKinsey 9 宫格业务组合矩阵 | portfolio_management, resource_allocation | strategy, portfolio |
| space-matrix | SPACE 矩阵 | strategic_selection | financial, industry | space_position | 战略地位与行动评估矩阵（4 维度 × 2 极） | strategic_positioning, action_selection | strategy, positioning |
| scenario-planning | 情景规划 | strategic_selection | scenarios | scenario_analysis | 未来情景构建 + 战略鲁棒性测试 | scenario_planning, long_term_strategy | strategy, uncertainty |
| value-curve-analysis | 价值曲线分析 | strategic_selection | factors | value_curve | W. Chan Kim 价值曲线（行业竞争因素可视化） | value_innovation, blue_ocean | strategy, differentiation |
| value-proposition-canvas | 价值主张画布 | business_model | customer_jobs, gains, pains | value_proposition | Osterwalder 价值主张画布（客户工作/收益/痛点 × 产品） | value_proposition, product_market_fit | model, customer |
| business-model-canvas | 商业模式画布 | business_model | nine_blocks | business_model | Osterwalder 商业模式画布（9 区块完整模型） | business_model_design, strategic_alignment | model, business |
| disruptive-innovation | 破坏性创新模型 | business_model | industry | disruption_analysis | Christensen 破坏性创新（低端/新市场颠覆） | disruption_analysis, innovation_strategy | model, innovation |
| bsc-scorecard | BSC 平衡计分卡 | execution_management | perspectives | scorecard | Kaplan/Norton 平衡计分卡（4 视角 KPI 设计） | performance_management, kpi_design | execution, kpi |
| strategy-map | 战略地图 | execution_management | objectives | strategy_map | Kaplan/Norton 战略地图（4 视角因果链） | strategic_theming, visual_communication | execution, strategy |
| org-design-framework | 组织设计框架 | execution_management | org_structure | org_design | Galbraith 星形模型（战略/结构/流程/奖励/人员） | org_design, org_transformation | execution, organization |
| dependency-graph | 依赖关系图 | execution_management | tasks | dependency_graph | 任务依赖关系图（DAG 节点 + 边） | project_planning, critical_path | execution, project |
| raci-matrix | RACI 矩阵 | execution_management | roles, tasks | raci_matrix | RACI 责任矩阵（Responsible/Accountable/Consulted/Informed） | responsibility_assignment, governance | execution, governance |
| gantt-chart | 甘特图 | execution_management | tasks, milestones | gantt_chart | 项目时间线甘特图（任务 + 起止 + 里程碑） | project_scheduling, timeline_planning | execution, timeline |
| kpi-tree | KPI | execution_management | objectives | kpi_tree | KPI 树（战略目标 → 部门目标 → 个人目标） | kpi_decomposition, goal_cascade | execution, kpi |
| change-management | 变革管理模型 | execution_management | change_scope | change_plan | Kotter 8 步法变革管理（紧迫感→联盟→愿景→沟通→赋能→胜利→巩固→固化） | change_management, transformation | execution, change |
