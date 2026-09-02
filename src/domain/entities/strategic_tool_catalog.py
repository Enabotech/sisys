"""战略工具目录常量模块

定义 23 种战略工具的完整元数据，作为工具注册的数据源。
每种工具包含唯一标识、名称、分类、描述、输入/输出 JSON Schema。

设计依据：
- 架构文档 sisys-core-domain-design.md §17.2.2
- Story 4.1 战略工具注册
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.domain.entities.tool import Tool, ToolCategory

# 23 种战略工具元数据常量
# 每个工具的 input_schema/output_schema 使用 JSON Schema Draft-07 格式
TOOL_CATALOG: list[Tool] = [
    # === 环境分析类（ENVIRONMENT_ANALYSIS）===
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="PESTEL 分析",
        description="宏观环境六维度分析（政治/经济/社会/技术/环境/法律）",
        category=ToolCategory.ENVIRONMENT_ANALYSIS,
        input_schema={
            "type": "object",
            "properties": {
                "macro_environment": {
                    "type": "object",
                    "description": "宏观环境数据",
                    "properties": {
                        "political": {"type": "object", "description": "政治因素"},
                        "economic": {"type": "object", "description": "经济因素"},
                        "social": {"type": "object", "description": "社会因素"},
                        "technological": {"type": "object", "description": "技术因素"},
                        "environmental": {"type": "object", "description": "环境因素"},
                        "legal": {"type": "object", "description": "法律因素"},
                    },
                },
            },
            "required": ["macro_environment"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "analysis_report": {
                    "type": "object",
                    "description": "PESTEL 分析报告",
                    "properties": {
                        "scores": {"type": "object", "description": "六维度评分"},
                        "impact_assessment": {"type": "object", "description": "影响评估"},
                        "opportunity_threat_matrix": {
                            "type": "object",
                            "description": "机会威胁矩阵",
                        },
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="波特五力",
        description="行业竞争五力模型分析（供应商/买方/替代品/新进入者/竞争强度）",
        category=ToolCategory.ENVIRONMENT_ANALYSIS,
        input_schema={
            "type": "object",
            "properties": {
                "industry_data": {
                    "type": "object",
                    "description": "行业竞争数据",
                    "properties": {
                        "supplier_power": {"type": "object"},
                        "buyer_power": {"type": "object"},
                        "competitive_rivalry": {"type": "object"},
                        "threat_of_substitution": {"type": "object"},
                        "threat_of_new_entry": {"type": "object"},
                    },
                },
            },
            "required": ["industry_data"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "five_forces_analysis": {
                    "type": "object",
                    "description": "五力模型分析结果",
                    "properties": {
                        "scores": {"type": "object"},
                        "industry_attractiveness": {"type": "string"},
                        "strategic_recommendations": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
        name="$APPEALS",
        description="客户需求九维度分析（性能/价格/获取/包装/体验/售后/保证/社会/易用性）",
        category=ToolCategory.ENVIRONMENT_ANALYSIS,
        input_schema={
            "type": "object",
            "properties": {
                "customer_needs": {
                    "type": "object",
                    "description": "客户需求数据",
                    "properties": {
                        "performance": {"type": "object"},
                        "price": {"type": "object"},
                        "availability": {"type": "object"},
                        "packaging": {"type": "object"},
                        "experience": {"type": "object"},
                        "after_sales": {"type": "object"},
                        "guarantee": {"type": "object"},
                        "social": {"type": "object"},
                        "ease_of_use": {"type": "object"},
                    },
                },
                "weights": {
                    "type": "object",
                    "description": "各维度权重",
                },
            },
            "required": ["customer_needs"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "appeals_analysis": {
                    "type": "object",
                    "description": "APPEALS 分析结果",
                    "properties": {
                        "scores": {"type": "object"},
                        "priority_ranking": {"type": "array"},
                        "improvement_suggestions": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    # === 竞争分析类（COMPETITIVE_ANALYSIS）===
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        name="竞争对手分析",
        description="竞争对手能力雷达图与竞争定位分析",
        category=ToolCategory.COMPETITIVE_ANALYSIS,
        input_schema={
            "type": "object",
            "properties": {
                "competitor_info": {
                    "type": "array",
                    "description": "竞争对手列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "capabilities": {"type": "object"},
                        },
                    },
                },
            },
            "required": ["competitor_info"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "competitor_radar": {
                    "type": "object",
                    "description": "竞争雷达图数据",
                    "properties": {
                        "radar_data": {"type": "object"},
                        "competitive_position": {"type": "string"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000005"),
        name="价值链分析",
        description="企业内部价值环节分析（主要活动+支持活动+成本结构）",
        category=ToolCategory.COMPETITIVE_ANALYSIS,
        input_schema={
            "type": "object",
            "properties": {
                "enterprise_data": {
                    "type": "object",
                    "description": "企业内部数据",
                    "properties": {
                        "primary_activities": {"type": "array"},
                        "support_activities": {"type": "array"},
                        "cost_structure": {"type": "object"},
                    },
                },
            },
            "required": ["enterprise_data"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "value_chain_analysis": {
                    "type": "object",
                    "description": "价值链分析结果",
                    "properties": {
                        "value_contribution": {"type": "object"},
                        "competitive_advantages": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000006"),
        name="VRIO 框架",
        description="资源能力竞争优势评估（价值/稀缺/难模仿/组织）",
        category=ToolCategory.COMPETITIVE_ANALYSIS,
        input_schema={
            "type": "object",
            "properties": {
                "resources": {
                    "type": "array",
                    "description": "资源/能力清单",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "vrio_scores": {"type": "object"},
                        },
                    },
                },
            },
            "required": ["resources"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "vrio_assessment": {
                    "type": "object",
                    "description": "VRIO 评估结果",
                    "properties": {
                        "classification": {"type": "object"},
                        "sustainability": {"type": "string"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    # === 战略选择类（STRATEGIC_SELECTION）===
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000007"),
        name="安索夫矩阵",
        description="市场/产品增长战略四象限分析",
        category=ToolCategory.STRATEGIC_SELECTION,
        input_schema={
            "type": "object",
            "properties": {
                "market_product_data": {
                    "type": "object",
                    "description": "市场/产品数据",
                    "properties": {
                        "existing_products": {"type": "array"},
                        "new_products": {"type": "array"},
                        "existing_markets": {"type": "array"},
                        "new_markets": {"type": "array"},
                    },
                },
            },
            "required": ["market_product_data"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "growth_strategy": {
                    "type": "object",
                    "description": "增长战略建议",
                    "properties": {
                        "quadrant_position": {"type": "string"},
                        "recommended_strategy": {"type": "string"},
                        "risk_assessment": {"type": "object"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000008"),
        name="SWOT-TOWS",
        description="内外因素策略匹配矩阵（SO/WO/ST/WT 四策略）",
        category=ToolCategory.STRATEGIC_SELECTION,
        input_schema={
            "type": "object",
            "properties": {
                "internal_factors": {
                    "type": "object",
                    "description": "内部因素",
                    "properties": {
                        "strengths": {"type": "array"},
                        "weaknesses": {"type": "array"},
                    },
                },
                "external_factors": {
                    "type": "object",
                    "description": "外部因素",
                    "properties": {
                        "opportunities": {"type": "array"},
                        "threats": {"type": "array"},
                    },
                },
            },
            "required": ["internal_factors", "external_factors"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "tows_matrix": {
                    "type": "object",
                    "description": "TOWS 策略矩阵",
                    "properties": {
                        "so_strategies": {"type": "array"},
                        "wo_strategies": {"type": "array"},
                        "st_strategies": {"type": "array"},
                        "wt_strategies": {"type": "array"},
                        "priority": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000009"),
        name="GE-麦肯锡矩阵",
        description="业务组合九宫格分析（行业吸引力×竞争实力）",
        category=ToolCategory.STRATEGIC_SELECTION,
        input_schema={
            "type": "object",
            "properties": {
                "business_units": {
                    "type": "array",
                    "description": "业务单元列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "industry_attractiveness": {"type": "number"},
                            "competitive_strength": {"type": "number"},
                        },
                    },
                },
            },
            "required": ["business_units"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "portfolio_map": {
                    "type": "object",
                    "description": "业务组合图谱",
                    "properties": {
                        "grid_position": {"type": "object"},
                        "recommendation": {"type": "string"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="SPACE 矩阵",
        description="战略定位分析（进取/保守/防御/竞争四定位）",
        category=ToolCategory.STRATEGIC_SELECTION,
        input_schema={
            "type": "object",
            "properties": {
                "strategic_factors": {
                    "type": "object",
                    "description": "战略因素数据",
                    "properties": {
                        "competitive_advantage": {"type": "number"},
                        "industry_strength": {"type": "number"},
                        "environmental_stability": {"type": "number"},
                        "financial_strength": {"type": "number"},
                    },
                },
            },
            "required": ["strategic_factors"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "space_positioning": {
                    "type": "object",
                    "description": "SPACE 定位结果",
                    "properties": {
                        "position": {"type": "string"},
                        "strategic_posture": {"type": "string"},
                        "recommendations": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        name="情景规划",
        description="多情景方案集与应对策略规划",
        category=ToolCategory.STRATEGIC_SELECTION,
        input_schema={
            "type": "object",
            "properties": {
                "trends": {
                    "type": "array",
                    "description": "关键不确定因素",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "trend_data": {"type": "object"},
                        },
                    },
                },
            },
            "required": ["trends"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "scenarios": {
                    "type": "array",
                    "description": "多情景方案集",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "probability": {"type": "number"},
                            "response_strategy": {"type": "string"},
                        },
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
        name="价值曲线分析",
        description="竞争对手差异化曲线与创新机会识别",
        category=ToolCategory.STRATEGIC_SELECTION,
        input_schema={
            "type": "object",
            "properties": {
                "competition_data": {
                    "type": "object",
                    "description": "竞争数据",
                    "properties": {
                        "competitors": {"type": "array"},
                        "value_factors": {"type": "object"},
                    },
                },
            },
            "required": ["competition_data"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "value_curve": {
                    "type": "object",
                    "description": "价值曲线分析结果",
                    "properties": {
                        "curves": {"type": "object"},
                        "innovation_opportunities": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    # === 商业模式类（BUSINESS_MODEL）===
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000013"),
        name="价值主张画布",
        description="客户痛点/收益与产品价值匹配度评估",
        category=ToolCategory.BUSINESS_MODEL,
        input_schema={
            "type": "object",
            "properties": {
                "customer_profile": {
                    "type": "object",
                    "description": "客户画像",
                    "properties": {
                        "pains": {"type": "array"},
                        "gains": {"type": "array"},
                        "jobs": {"type": "array"},
                    },
                },
                "value_map": {
                    "type": "object",
                    "description": "价值地图",
                    "properties": {
                        "products": {"type": "array"},
                        "pain_relievers": {"type": "array"},
                        "gain_creators": {"type": "array"},
                    },
                },
            },
            "required": ["customer_profile", "value_map"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "fit_assessment": {
                    "type": "object",
                    "description": "匹配度评估",
                    "properties": {
                        "fit_score": {"type": "number"},
                        "improvement_suggestions": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000014"),
        name="商业模式画布",
        description="商业模式九宫格画布（客户细分/价值主张/渠道/收入等）",
        category=ToolCategory.BUSINESS_MODEL,
        input_schema={
            "type": "object",
            "properties": {
                "business_model": {
                    "type": "object",
                    "description": "商业模式数据",
                    "properties": {
                        "customer_segments": {"type": "array"},
                        "value_propositions": {"type": "array"},
                        "channels": {"type": "array"},
                        "customer_relationships": {"type": "array"},
                        "revenue_streams": {"type": "array"},
                        "key_resources": {"type": "array"},
                        "key_activities": {"type": "array"},
                        "key_partnerships": {"type": "array"},
                        "cost_structure": {"type": "object"},
                    },
                },
            },
            "required": ["business_model"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "canvas_assessment": {
                    "type": "object",
                    "description": "画布评估结果",
                    "properties": {
                        "dimension_scores": {"type": "object"},
                        "consistency_analysis": {"type": "object"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000015"),
        name="破坏性创新模型",
        description="技术成熟度与市场颠覆潜力评估",
        category=ToolCategory.BUSINESS_MODEL,
        input_schema={
            "type": "object",
            "properties": {
                "technology_market_data": {
                    "type": "object",
                    "description": "技术/市场数据",
                    "properties": {
                        "technology_maturity": {"type": "string"},
                        "market_landscape": {"type": "object"},
                        "disruption_potential": {"type": "number"},
                    },
                },
            },
            "required": ["technology_market_data"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "innovation_assessment": {
                    "type": "object",
                    "description": "创新评估结果",
                    "properties": {
                        "disruption_type": {"type": "string"},
                        "strategic_recommendations": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    # === 执行管理类（EXECUTION_MANAGEMENT）===
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000016"),
        name="BSC 平衡计分卡",
        description="四维度战略目标指标体系（财务/客户/内部流程/学习成长）",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "strategic_objectives": {
                    "type": "object",
                    "description": "战略目标",
                    "properties": {
                        "financial": {"type": "array"},
                        "customer": {"type": "array"},
                        "internal_process": {"type": "array"},
                        "learning_growth": {"type": "array"},
                    },
                },
            },
            "required": ["strategic_objectives"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "bsc_metrics": {
                    "type": "object",
                    "description": "BSC 指标体系",
                    "properties": {
                        "kpi_indicators": {"type": "array"},
                        "target_values": {"type": "object"},
                        "weights": {"type": "object"},
                        "action_plans": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000017"),
        name="战略地图",
        description="BSC 四维度因果关系战略可视化图",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "bsc_indicators": {
                    "type": "object",
                    "description": "BSC 四维度指标",
                    "properties": {
                        "financial": {"type": "array"},
                        "customer": {"type": "array"},
                        "internal_process": {"type": "array"},
                        "learning_growth": {"type": "array"},
                        "causal_relationships": {"type": "array"},
                    },
                },
            },
            "required": ["bsc_indicators"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "strategy_visualization": {
                    "type": "object",
                    "description": "战略地图可视化",
                    "properties": {
                        "nodes": {"type": "array"},
                        "causal_arrows": {"type": "array"},
                        "theme_cards": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000018"),
        name="组织设计框架",
        description="组织架构匹配度评估与优化建议",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "org_structure": {
                    "type": "object",
                    "description": "组织架构数据",
                    "properties": {
                        "functions": {"type": "array"},
                        "reporting_lines": {"type": "array"},
                        "decentralization_level": {"type": "string"},
                    },
                },
            },
            "required": ["org_structure"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "design_recommendation": {
                    "type": "object",
                    "description": "组织设计建议",
                    "properties": {
                        "fit_assessment": {"type": "object"},
                        "optimization_suggestions": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000019"),
        name="依赖关系图",
        description="任务依赖关系网络与关键路径分析",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "task_list": {
                    "type": "array",
                    "description": "任务列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "dependencies": {"type": "array"},
                        },
                    },
                },
            },
            "required": ["task_list"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "dependency_network": {
                    "type": "object",
                    "description": "依赖关系网络",
                    "properties": {
                        "dag": {"type": "object"},
                        "critical_path": {"type": "array"},
                        "risk_nodes": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000020"),
        name="RACI 矩阵",
        description="角色职责分配矩阵（负责/批准/咨询/知会）",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "roles_tasks": {
                    "type": "object",
                    "description": "角色与任务分配",
                    "properties": {
                        "roles": {"type": "array"},
                        "tasks": {"type": "array"},
                        "assignments": {"type": "object"},
                    },
                },
            },
            "required": ["roles_tasks"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "raci_matrix": {
                    "type": "object",
                    "description": "RACI 分配结果",
                    "properties": {
                        "matrix": {"type": "object"},
                        "conflicts": {"type": "array"},
                        "suggestions": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
        name="甘特图",
        description="项目进度时间线与里程碑可视化",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "project_plan": {
                    "type": "object",
                    "description": "项目计划",
                    "properties": {
                        "tasks": {"type": "array"},
                        "dependencies": {"type": "array"},
                        "durations": {"type": "object"},
                        "resources": {"type": "object"},
                    },
                },
            },
            "required": ["project_plan"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "gantt_visualization": {
                    "type": "object",
                    "description": "甘特图可视化",
                    "properties": {
                        "timeline": {"type": "array"},
                        "milestones": {"type": "array"},
                        "critical_path": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000022"),
        name="KPI",
        description="关键绩效指标定义与监控体系",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "business_objectives": {
                    "type": "object",
                    "description": "业务目标",
                    "properties": {
                        "objectives": {"type": "array"},
                        "baseline_data": {"type": "object"},
                    },
                },
            },
            "required": ["business_objectives"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "kpi_definitions": {
                    "type": "array",
                    "description": "KPI 定义列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "target_value": {"type": "number"},
                            "weight": {"type": "number"},
                            "monitoring_frequency": {"type": "string"},
                        },
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
    Tool(
        tool_id=uuid.UUID("00000000-0000-0000-0000-000000000023"),
        name="变革管理模型",
        description="变革路径规划、利益相关者分析与风险缓解",
        category=ToolCategory.EXECUTION_MANAGEMENT,
        input_schema={
            "type": "object",
            "properties": {
                "change_data": {
                    "type": "object",
                    "description": "变革数据",
                    "properties": {
                        "change_content": {"type": "string"},
                        "stakeholders": {"type": "array"},
                        "resistance_analysis": {"type": "object"},
                    },
                },
            },
            "required": ["change_data"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "change_roadmap": {
                    "type": "object",
                    "description": "变革路线图",
                    "properties": {
                        "path": {"type": "array"},
                        "milestones": {"type": "array"},
                        "communication_plan": {"type": "object"},
                        "risk_mitigation": {"type": "array"},
                    },
                },
            },
        },
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    ),
]
