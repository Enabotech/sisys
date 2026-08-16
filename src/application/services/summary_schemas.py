"""应用层 摘要生成 Pydantic Schema 模块

定义财务（FinancialSummary）、市场（MarketSummary）、技术（TechnicalSummary）
三个视角的结构化摘要 Schema，作为 LLM 结构化输出的契约化目标格式。

每个 Schema 包含三个固有字段和四个视角特有字段，通过 Pydantic V2 严格模式验证。

设计决策：
- 定义在应用层（src/application/），允许依赖 Pydantic
- 领域层零外部依赖约束不适用于此
- 使用 Pydantic V2 BaseModel + Field 验证
- confidence_score 范围 [0.0, 1.0]，语义为"LLM 自评置信度"
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FinancialSummary(BaseModel):
    """财务视角结构化摘要

    包含财务分析所需的核心字段，聚焦收入趋势、利润分析、风险因素和市场地位。

    Attributes:
        summary_text: 摘要正文
        key_points: 关键要点列表
        confidence_score: LLM 自评置信度（0-1）
        revenue_trend: 收入趋势描述
        profit_analysis: 利润分析
        risk_factors: 风险因素列表
        market_position: 市场地位
    """

    summary_text: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="摘要正文，防止空摘要或超长内容",
    )
    key_points: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="关键要点列表",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM 自评置信度，基于检索结果相关性和生成质量",
    )
    revenue_trend: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="收入趋势描述",
    )
    profit_analysis: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="利润分析",
    )
    risk_factors: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="风险因素列表",
    )
    market_position: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="市场地位",
    )


class MarketSummary(BaseModel):
    """市场视角结构化摘要

    包含市场分析所需的核心字段，聚焦市场规模、竞争格局、增长驱动力和客户洞察。

    Attributes:
        summary_text: 摘要正文
        key_points: 关键要点列表
        confidence_score: LLM 自评置信度（0-1）
        market_size: 市场规模描述
        competitive_landscape: 竞争格局描述
        growth_drivers: 增长驱动力列表
        customer_insights: 客户洞察
    """

    summary_text: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="摘要正文，防止空摘要或超长内容",
    )
    key_points: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="关键要点列表",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM 自评置信度，基于检索结果相关性和生成质量",
    )
    market_size: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="市场规模描述",
    )
    competitive_landscape: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="竞争格局描述",
    )
    growth_drivers: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="增长驱动力列表",
    )
    customer_insights: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="客户洞察",
    )


class TechnicalSummary(BaseModel):
    """技术视角结构化摘要

    包含技术分析所需的核心字段，聚焦技术栈、创新点、技术风险和架构概述。

    Attributes:
        summary_text: 摘要正文
        key_points: 关键要点列表
        confidence_score: LLM 自评置信度（0-1）
        technology_stack: 技术栈描述
        innovation_points: 创新点列表
        technical_risks: 技术风险列表
        architecture_overview: 架构概述
    """

    summary_text: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="摘要正文，防止空摘要或超长内容",
    )
    key_points: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="关键要点列表",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM 自评置信度，基于检索结果相关性和生成质量",
    )
    technology_stack: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="技术栈描述",
    )
    innovation_points: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="创新点列表",
    )
    technical_risks: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="技术风险列表",
    )
    architecture_overview: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="架构概述",
    )


# 视角类型到 Schema 类的映射字典
PERSPECTIVE_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "financial": FinancialSummary,
    "market": MarketSummary,
    "technical": TechnicalSummary,
}


__all__ = [
    "FinancialSummary",
    "MarketSummary",
    "TechnicalSummary",
    "PERSPECTIVE_SCHEMA_MAP",
]
