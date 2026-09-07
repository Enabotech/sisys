# TOOLS.md — Skills L1 元数据索引

> 23 种战略工具元数据索引，供 Agent 启动时全量加载（<200 tokens）。
> 完整 SOP 见各 `<slug>/SKILL.md`。

| slug | 工具名称 | 分类 | input_schema 摘要 | output_schema 摘要 |
|------|---------|------|-------------------|-------------------|
| pestel-analysis | PESTEL 分析 | environment_analysis | {macro_environment} | {analysis_report} |
| porters-five-forces | 波特五力 | environment_analysis | {industry} | {five_forces_report} |
| appeals-analysis | $APPEALS | environment_analysis | {market_data} | {appeals_analysis} |
| competitor-analysis | 竞争对手分析 | competitive_analysis | {competitors[]} | {competitive_landscape} |
| value-chain-analysis | 价值链分析 | competitive_analysis | {company} | {value_chain_map} |
| vrio-framework | VRIO 框架 | competitive_analysis | {resource} | {vrio_assessment} |
| ansoff-matrix | 安索夫矩阵 | strategic_selection | {products[], markets[]} | {ansoff_matrix} |
| swot-tows | SWOT-TOWS | strategic_selection | {strengths, weaknesses, opportunities, threats} | {tows_strategy} |
| ge-mckinsey-matrix | GE-麦肯锡矩阵 | strategic_selection | {business_units[]} | {portfolio_grid} |
| space-matrix | SPACE 矩阵 | strategic_selection | {financial, industry, stability, competitive} | {space_position} |
| scenario-planning | 情景规划 | strategic_selection | {scenarios[]} | {scenario_analysis} |
| value-curve-analysis | 价值曲线分析 | strategic_selection | {factors[]} | {value_curve} |
| value-proposition-canvas | 价值主张画布 | business_model | {customer_jobs, gains, pains} | {value_proposition} |
| business-model-canvas | 商业模式画布 | business_model | {9_blocks} | {business_model} |
| disruptive-innovation | 破坏性创新模型 | business_model | {industry} | {disruption_analysis} |
| bsc-scorecard | BSC 平衡计分卡 | execution_management | {perspectives[]} | {scorecard} |
| strategy-map | 战略地图 | execution_management | {objectives[]} | {strategy_map} |
| org-design-framework | 组织设计框架 | execution_management | {org_structure} | {org_design} |
| dependency-graph | 依赖关系图 | execution_management | {tasks[]} | {dependency_graph} |
| raci-matrix | RACI 矩阵 | execution_management | {roles, tasks} | {raci_matrix} |
| gantt-chart | 甘特图 | execution_management | {tasks[], milestones} | {gantt_chart} |
| kpi-tree | KPI | execution_management | {objectives[]} | {kpi_tree} |
| change-management | 变革管理模型 | execution_management | {change_scope} | {change_plan} |
