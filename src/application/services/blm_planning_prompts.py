"""应用层 BLM 规划 prompt 模板与语义配置表（Story 6-1）

六子步骤语义配置表 SSOT（Task 0.1 钦定——AC-5 温度断言期望值唯一源）：
每步 = 视角前缀句（or.md 主导角色语义——MVP 由 CEO Agent 单角色承载，
角色语义经 prompt 视角前缀实现，DC-2）+ 工具候选 slug 白名单（or.md 建议
工具映射到 23 工具注册面）+ 检索 query 模板 + 产物要点 + 温度档。

温度档设计（对齐 5-3 TEMPERATURE_PROFILE 五档值域 0.1~0.4）：分析量化类
低（0.2——差距量化/机会差距）、扫描综合类中低（0.3~0.4）、机会生成类中
（0.5——看机会）。8 步温度映射（performance_gap/trend/market_customer/
competition/self/opportunity/opportunity_gap/synthesis）。

结构化输出 Schema（pydantic——应用层边界合法依赖）：BLM 面三 Schema 与
prompt 模板同文件（结构化输出契约是 prompt 面的一部分——Task 0.1 钦定）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from src.domain.value_objects.blm_phases import MarketInsightStep

# ===================================================================
# 结构化输出 Schema（BLM 面三 Schema——Fake LLM 分派键）
# ===================================================================


class GapAnalysisSchema(BaseModel):
    """阶段 1 业绩差距分析结构化输出（§17.4.2 四字段语义）。"""

    financial_gap: str = Field(description="财务差距量化结论（达成率/毛利率等关键指标差距）")
    operational_gap: str = Field(description="运营差距分析结论（交付/产能/效率差距）")
    root_causes: list[str] = Field(description="根因清单（SWOT-TOWS 差距根因识别）")
    portfolio_health: str = Field(description="业务组合健康度评估（GE-麦肯锡矩阵语义）")


class MarketInsightSchemaBase(BaseModel):
    """六步类型化 Schema 公共基类（R3-1 双公共字段单源——代码审查 R1-F4）。

    六子步骤 Schema 共有的信封双字段在此单源定义；各步 Schema 继承后仅声明
    领域要素字段。pydantic 继承形态与手工重复形态的 model_json_schema 逐字节
    等价（字段顺序=基类字段先序，与既有手工顺序一致）。注意：本基类不进
    MARKET_INSIGHT_STEP_SCHEMA 值域（非第七个业务 Schema）。
    """

    summary: str = Field(description="步骤结论摘要（≤200 字）")
    findings: list[str] = Field(description="结构化发现清单")


class TrendInsightSchema(MarketInsightSchemaBase):
    """看趋势类型化结构化输出（PESTEL/情景规划——or.md「宏观趋势报告」经
    PESTEL 六维度工具产物化——OD-8）。"""

    pestel_political: str = Field(description="PESTEL 政治维度评估（宏观趋势报告工具产物化——OD-8）")
    pestel_economic: str = Field(description="PESTEL 经济维度评估")
    pestel_social: str = Field(description="PESTEL 社会维度评估")
    pestel_technological: str = Field(description="PESTEL 技术维度评估")
    pestel_environmental: str = Field(description="PESTEL 环境维度评估")
    pestel_legal: str = Field(description="PESTEL 法律维度评估")
    technology_roadmap: list[str] = Field(description="技术演进路线图（演进阶段要点清单）")
    scenario_plans: list[str] = Field(description="情景规划方案集（多趋势组合推演要点）")


class MarketCustomerInsightSchema(MarketInsightSchemaBase):
    """看市场与客户类型化结构化输出（$APPEALS/价值主张画布）。"""

    customer_segments: list[str] = Field(description="客户细分画像（细分群体要点）")
    demand_priority_matrix: list[str] = Field(description="需求优先级矩阵（$APPEALS 需求排序要点）")
    value_proposition_map: list[str] = Field(description="价值主张地图（客户痛点-收益映射要点）")


class CompetitionInsightSchema(MarketInsightSchemaBase):
    """看竞争类型化结构化输出（波特五力/竞争对手分析——or.md「行业竞争结构图」
    经波特五力五维工具产物化——OD-8）。"""

    five_forces_supplier_power: str = Field(description="波特五力：供应商议价能力评估（行业竞争结构图工具产物化——OD-8）")
    five_forces_buyer_power: str = Field(description="波特五力：购买者议价能力评估")
    five_forces_new_entrants: str = Field(description="波特五力：新进入者威胁评估")
    five_forces_substitutes: str = Field(description="波特五力：替代品威胁评估")
    five_forces_rivalry: str = Field(description="波特五力：现有竞争者强度评估")
    competitor_radar: list[str] = Field(description="竞争对手能力雷达图评估（能力维度要点）")
    strategy_recommendations: list[str] = Field(description="竞争策略建议")


class SelfInsightSchema(MarketInsightSchemaBase):
    """看自己类型化结构化输出（价值链分析/SWOT-TOWS/VRIO 框架）。"""

    internal_capabilities: list[str] = Field(description="内部能力清单")
    vrio_assessment: list[str] = Field(description="核心能力 VRIO 评估（价值/稀缺/难模仿/组织维度要点）")
    resource_constraints: list[str] = Field(description="资源约束分析")


class OpportunityInsightSchema(MarketInsightSchemaBase):
    """看机会类型化结构化输出（SWOT-TOWS/安索夫矩阵）。"""

    opportunity_list: list[str] = Field(description="机会清单")
    priority_ranking: list[str] = Field(description="机会优先级排序")
    growth_path: list[str] = Field(description="增长路径图（安索夫矩阵路径要点）")


class OpportunityGapInsightSchema(MarketInsightSchemaBase):
    """机会差距分析类型化结构化输出（GE-麦肯锡矩阵/SWOT-TOWS）。"""

    gap_quantification: list[str] = Field(description="机会差距量化报告要点")
    capability_match_matrix: list[str] = Field(description="能力-机会匹配矩阵（GE-麦肯锡矩阵匹配要点）")
    closure_strategies: list[str] = Field(description="差距弥合策略")


#: 六步类型化 Schema SSOT 映射（形态 A 独立 dict——Subtask 0.1 钦定：不用
#: StepSemanticConfig 加 schema_cls 字段形态，避免配置表承载类型对象使耦合扩散；
#: 服务层 run_insight_step 经此查表分派，零 if-else 硬编码）
MARKET_INSIGHT_STEP_SCHEMA: dict[MarketInsightStep, type[BaseModel]] = {
    MarketInsightStep.TREND: TrendInsightSchema,
    MarketInsightStep.MARKET_CUSTOMER: MarketCustomerInsightSchema,
    MarketInsightStep.COMPETITION: CompetitionInsightSchema,
    MarketInsightStep.SELF: SelfInsightSchema,
    MarketInsightStep.OPPORTUNITY: OpportunityInsightSchema,
    MarketInsightStep.OPPORTUNITY_GAP: OpportunityGapInsightSchema,
}


class InsightSynthesisSchema(BaseModel):
    """综合洞察结构化输出。"""

    conclusions: list[str] = Field(description="综合结论清单（聚合六子步骤产物）")


# ===================================================================
# 六子步骤语义配置表（SSOT）
# ===================================================================


@dataclass(frozen=True)
class StepSemanticConfig:
    """子步骤语义配置（语义配置表行——Task 0.1 钦定）。

    Attributes:
        step_key: 步骤标识（MarketInsightStep 值）。
        display_name: 中文名（or.md 钦定）。
        role_prefix: 视角前缀句（or.md 主导角色双重视角——AC-2 断言锚）。
        tool_candidates: 工具候选白名单（**中文显示名**口径——与隔离白名单
            真源 configs/agents/ceo_agent.yaml allowed_tools 及注册表
            get_tool(tool_name=) 同口径；确定性先行执行——R3-3 生产不可达
            380 的设计前提：白名单名必已注册）。
        retrieval_query_template: 检索 query 模板（{task} 占位符替换）。
        output_focus: 产物要点（prompt 产物要求段）。
    """

    step_key: str
    display_name: str
    role_prefix: str
    tool_candidates: tuple[str, ...]
    retrieval_query_template: str
    output_focus: str


#: 阶段 1 业绩差距分析配置（or.md [1]——CFO 财务差距量化/COO 运营差距主导；
#: 工具候选=显示名口径——CEO 白名单 23 名子集）
PERFORMANCE_GAP_CONFIG = StepSemanticConfig(
    step_key="performance_gap",
    display_name="业绩差距分析",
    role_prefix="以 CFO 财务差距量化与 COO 运营差距分析的双重视角",
    tool_candidates=("SWOT-TOWS", "KPI", "价值链分析", "GE-麦肯锡矩阵"),
    retrieval_query_template="业绩差距 历史绩效 财务与运营数据：{task}",
    output_focus="产出业绩差距量化结论（financial_gap/operational_gap/root_causes/portfolio_health 四要素）",
)

#: 六子步骤语义配置表（or.md L385-415 钦定序——dict 有序保枚举序）
MARKET_INSIGHT_STEP_CONFIG: dict[MarketInsightStep, StepSemanticConfig] = {
    MarketInsightStep.TREND: StepSemanticConfig(
        step_key="trend",
        display_name="看趋势",
        role_prefix="以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角",
        tool_candidates=("PESTEL 分析", "情景规划"),
        retrieval_query_template="宏观环境趋势 技术演进路线：{task}",
        output_focus="识别宏观环境与技术趋势信号，产出趋势判断要点",
    ),
    MarketInsightStep.MARKET_CUSTOMER: StepSemanticConfig(
        step_key="market_customer",
        display_name="看市场与客户",
        role_prefix="以 CMO 客户需求洞察与 COO 市场细分分析的双重视角",
        tool_candidates=("$APPEALS", "价值主张画布"),
        retrieval_query_template="客户需求 市场细分 客户画像：{task}",
        output_focus="洞察客户需求与市场细分结构，产出客户价值要点",
    ),
    MarketInsightStep.COMPETITION: StepSemanticConfig(
        step_key="competition",
        display_name="看竞争",
        role_prefix="以 CEO 竞争格局判断与 CMO 竞争对手分析的双重视角",
        tool_candidates=("波特五力", "竞争对手分析"),
        retrieval_query_template="行业竞争结构 竞争对手动态：{task}",
        output_focus="评估行业竞争结构与竞争对手能力，产出竞争态势要点",
    ),
    MarketInsightStep.SELF: StepSemanticConfig(
        step_key="self",
        display_name="看自己",
        role_prefix="以 COO 内部能力评估与 CFO 财务健康度分析的双重视角",
        tool_candidates=("价值链分析", "SWOT-TOWS", "VRIO 框架"),
        retrieval_query_template="内部能力 财务健康度 组织能力：{task}",
        output_focus="盘点内部能力与资源约束，产出能力评估要点",
    ),
    MarketInsightStep.OPPORTUNITY: StepSemanticConfig(
        step_key="opportunity",
        display_name="看机会",
        role_prefix="以 CEO 机会识别与 CMO 市场机会验证的双重视角",
        tool_candidates=("SWOT-TOWS", "安索夫矩阵"),
        retrieval_query_template="市场机会 增长路径 机会清单：{task}",
        output_focus="识别与优先级排序市场机会，产出机会清单要点",
    ),
    MarketInsightStep.OPPORTUNITY_GAP: StepSemanticConfig(
        step_key="opportunity_gap",
        display_name="机会差距分析",
        role_prefix="以 CEO 机会差距量化与 CFO 机会价值评估的双重视角",
        tool_candidates=("GE-麦肯锡矩阵", "SWOT-TOWS"),
        retrieval_query_template="机会差距 能力匹配 差距弥合：{task}",
        output_focus="量化机会与能力的差距，产出差距弥合策略要点",
    ),
}

#: 8 步温度档映射（AC-5 断言期望值唯一源——Task 0.1 钦定值）
BLM_TEMPERATURE_PROFILE: dict[str, float] = {
    "performance_gap": 0.2,
    "trend": 0.4,
    "market_customer": 0.4,
    "competition": 0.4,
    "self": 0.3,
    "opportunity": 0.5,
    "opportunity_gap": 0.2,
    "market_insight_synthesis": 0.3,
}

#: 单调用超时上限（秒）——对齐 5-3 _DEFAULT_PER_CALL_TIMEOUT_SEC
BLM_PER_CALL_TIMEOUT_SEC: float = 8.0


# ===================================================================
# prompt 构造（语义配置表参数化）
# ===================================================================


def build_performance_gap_prompt(
    task: str,
    evidence_texts: tuple[str, ...] = (),
    tool_output_summary: str = "",
) -> str:
    """构造阶段 1 prompt（视角前缀+工具白名单+证据+任务）。

    Args:
        task: 规划任务描述。
        evidence_texts: 检索证据片段（空=无证据推理）。
        tool_output_summary: 工具输出摘要（空=工具未执行）。

    Returns:
        prompt 字符串。
    """
    config = PERFORMANCE_GAP_CONFIG
    sections = [
        f"{config.role_prefix}，执行 BLM 阶段 1「{config.display_name}」。",
        f"可用分析工具候选（白名单）：{', '.join(config.tool_candidates)}。",
        f"规划任务：{task}",
        f"产物要求：{config.output_focus}。",
    ]
    if tool_output_summary:
        sections.append(f"工具分析输出：\n{tool_output_summary}")
    if evidence_texts:
        sections.append("检索证据：\n" + "\n".join(f"- {t}" for t in evidence_texts))
    else:
        sections.append("检索证据：（无可用证据，基于任务描述推理）")
    return "\n".join(sections)


def build_insight_step_prompt(
    step: MarketInsightStep,
    task: str,
    evidence_texts: tuple[str, ...] = (),
    tool_output_summary: str = "",
    prior_outputs_summary: str = "",
    degradation_notes: tuple[str, ...] = (),
    gap_summary: str = "",
) -> str:
    """构造子步骤 prompt（视角前缀+该步工具候选白名单+证据+上游产物）。

    Args:
        step: 子步骤枚举。
        task: 规划任务描述。
        evidence_texts: 该步检索证据片段。
        tool_output_summary: 工具输出摘要。
        prior_outputs_summary: 上游产物摘要（降级产物以「[降级]+原因」标注）。
        degradation_notes: 上游降级标注（⑥规则 1——显式注入下游）。
        gap_summary: 阶段 1 业绩差距分析产物摘要（跨阶段传导——降级时带
            「[降级]+原因」标注；空串表示无阶段 1 产物注入）。

    Returns:
        prompt 字符串。
    """
    config = MARKET_INSIGHT_STEP_CONFIG[step]
    sections = [
        f"{config.role_prefix}，执行 BLM 市场洞察子步骤「{config.display_name}」。",
        f"可用分析工具候选（白名单）：{', '.join(config.tool_candidates)}。",
        f"规划任务：{task}",
        f"产物要求：{config.output_focus}。",
    ]
    if gap_summary:
        sections.append(f"阶段 1 业绩差距分析产物摘要：{gap_summary}")
    if prior_outputs_summary:
        sections.append(f"上游步骤产物摘要：\n{prior_outputs_summary}")
    for note in degradation_notes:
        sections.append(f"[降级] 上游步骤 {note}")
    if tool_output_summary:
        sections.append(f"工具分析输出：\n{tool_output_summary}")
    if evidence_texts:
        sections.append("检索证据：\n" + "\n".join(f"- {t}" for t in evidence_texts))
    else:
        sections.append("检索证据：（无可用证据，基于任务描述推理）")
    return "\n".join(sections)


def build_synthesis_prompt(step_summaries: tuple[str, ...], degraded_inputs: tuple[str, ...]) -> str:
    """构造综合洞察 prompt（注入侧锚——六步产物摘要逐一注入）。

    Args:
        step_summaries: 六子步骤产物摘要（顺序注入——漏传可判别）。
        degraded_inputs: 降级步骤清单（结论必须列举——⑥规则 2）。

    Returns:
        prompt 字符串。
    """
    sections = ["综合以上市场洞察六子步骤的全部产物，产出结构化综合洞察结论。"]
    for index, summary in enumerate(step_summaries, start=1):
        sections.append(f"子步骤 {index} 产物摘要：{summary}")
    if degraded_inputs:
        sections.append("以下子步骤为降级产物（结论必须显式列举这些降级输入，不可无标注吞并）：" + ", ".join(degraded_inputs))
    sections.append("产物要求：聚合六子步骤产物的结构化综合结论清单。")
    return "\n".join(sections)


#: 降级标注前缀（⑥规则 1——显式标注注入下游 prompt）
DEGRADATION_MARKER_PREFIX: str = "[降级]"


def summarize_step_for_downstream(step_result: Any) -> str:
    """构造注入下游的步骤产物摘要（降级步以「[降级]+原因」显式标注）。

    Args:
        step_result: InsightStepResult 信封。

    Returns:
        摘要字符串。
    """
    if step_result.degraded:
        return f"{DEGRADATION_MARKER_PREFIX} 步骤 {step_result.step} 降级（{step_result.degrade_reason}）"
    return f"步骤 {step_result.step}：{step_result.summary}"


def summarize_gap_for_downstream(gap_artifacts: Any) -> str:
    """构造阶段 1 产物注入阶段 2 各步的摘要（跨阶段传导——AC-6⑥ 规则 1）。

    四字段全量传导（6-2 OD-6——执行 6-1 代码审查 R2-3 成文裁定：扩展自
    financial_gap 单字段）；「财务差距=」标签子串兼容 6-1 先例（R2-3 钉死）。
    降级时以「[降级]+原因」显式标注（与 summarize_step_for_downstream 同款
    形态——DEGRADATION_MARKER_PREFIX 单源；降级分支零改动不携带四字段内容）。

    Args:
        gap_artifacts: PerformanceGapArtifacts 产物。

    Returns:
        摘要字符串（四标签「财务差距=/运营差距=/根因=/组合健康度=」全量形态）。
    """
    if getattr(gap_artifacts, "degraded", False):
        reason = getattr(gap_artifacts, "degrade_reason", "")
        return f"{DEGRADATION_MARKER_PREFIX} 步骤 performance_gap 降级（{reason}）"
    return (
        f"步骤 performance_gap：财务差距={getattr(gap_artifacts, 'financial_gap', '')}"
        f"；运营差距={getattr(gap_artifacts, 'operational_gap', '')}"
        f"；根因={'、'.join(getattr(gap_artifacts, 'root_causes', ()))}"
        f"；组合健康度={getattr(gap_artifacts, 'portfolio_health', '')}"
    )


__all__ = [
    "BLM_PER_CALL_TIMEOUT_SEC",
    "BLM_TEMPERATURE_PROFILE",
    "DEGRADATION_MARKER_PREFIX",
    "CompetitionInsightSchema",
    "GapAnalysisSchema",
    "MARKET_INSIGHT_STEP_CONFIG",
    "MARKET_INSIGHT_STEP_SCHEMA",
    "MarketCustomerInsightSchema",
    "MarketInsightSchemaBase",
    "OpportunityGapInsightSchema",
    "OpportunityInsightSchema",
    "PERFORMANCE_GAP_CONFIG",
    "SelfInsightSchema",
    "StepSemanticConfig",
    "TrendInsightSchema",
    "InsightSynthesisSchema",
    "build_insight_step_prompt",
    "build_performance_gap_prompt",
    "build_synthesis_prompt",
    "summarize_gap_for_downstream",
    "summarize_step_for_downstream",
]
