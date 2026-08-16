"""Story 3.6 摘要 Pydantic Schema 单元测试

验证 FinancialSummary、MarketSummary、TechnicalSummary 的字段定义、验证约束和反序列化。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.application.services.summary_schemas import (
    PERSPECTIVE_SCHEMA_MAP,
    FinancialSummary,
    MarketSummary,
    TechnicalSummary,
)


class TestFinancialSummary:
    """FinancialSummary Schema 验证"""

    def test_valid_financial_summary(self) -> None:
        """有效的 FinancialSummary 实例创建成功"""
        summary = FinancialSummary(
            summary_text="这是一个财务摘要，用于测试财务数据的结构化分析能力。",
            key_points=["收入增长", "利润稳定", "市场扩张"],
            confidence_score=0.85,
            revenue_trend="收入呈上升趋势，年增长率约15%",
            profit_analysis="利润率稳定，保持在20%左右",
            risk_factors=["市场竞争加剧", "原材料价格波动"],
            market_position="市场领先者，占有约30%市场份额",
        )
        assert summary.summary_text
        assert len(summary.key_points) == 3
        assert summary.confidence_score == 0.85
        assert summary.revenue_trend == "收入呈上升趋势，年增长率约15%"

    def test_confidence_score_range_validation(self) -> None:
        """confidence_score 超出 [0, 1] 范围时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            FinancialSummary(
                summary_text="这是一个财务摘要，用于测试财务数据的结构化分析能力。",
                key_points=["收入增长"],
                confidence_score=1.5,  # 超出范围
                revenue_trend="收入增长",
                profit_analysis="利润稳定",
                risk_factors=["市场竞争"],
                market_position="市场领先者",
            )

    def test_negative_confidence_score(self) -> None:
        """confidence_score 为负数时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            FinancialSummary(
                summary_text="这是一个财务摘要，用于测试财务数据的结构化分析能力。",
                key_points=["收入增长"],
                confidence_score=-0.1,  # 负数
                revenue_trend="收入增长",
                profit_analysis="利润稳定",
                risk_factors=["市场竞争"],
                market_position="市场领先者",
            )

    def test_summary_text_min_length(self) -> None:
        """summary_text 过短时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            FinancialSummary(
                summary_text="太短",  # min_length=10
                key_points=["收入增长"],
                confidence_score=0.5,
                revenue_trend="收入增长",
                profit_analysis="利润稳定",
                risk_factors=["市场竞争"],
                market_position="市场领先者",
            )

    def test_empty_key_points(self) -> None:
        """key_points 为空列表时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            FinancialSummary(
                summary_text="这是一个财务摘要，用于测试财务数据的结构化分析能力。",
                key_points=[],
                confidence_score=0.5,
                revenue_trend="收入增长",
                profit_analysis="利润稳定",
                risk_factors=["市场竞争"],
                market_position="市场领先者",
            )

    def test_too_many_key_points(self) -> None:
        """key_points 超过 max_length=10 时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            FinancialSummary(
                summary_text="这是一个财务摘要，用于测试财务数据的结构化分析能力。",
                key_points=[f"要点{i}" for i in range(11)],
                confidence_score=0.5,
                revenue_trend="收入增长",
                profit_analysis="利润稳定",
                risk_factors=["市场竞争"],
                market_position="市场领先者",
            )

    def test_model_dump_serialization(self) -> None:
        """FinancialSummary 可序列化为 dict"""
        summary = FinancialSummary(
            summary_text="这是一个财务摘要，用于测试财务数据的结构化分析能力。",
            key_points=["收入增长", "利润稳定"],
            confidence_score=0.85,
            revenue_trend="收入增长",
            profit_analysis="利润稳定",
            risk_factors=["市场竞争"],
            market_position="市场领先者",
        )
        data = summary.model_dump()
        assert isinstance(data, dict)
        assert data["confidence_score"] == 0.85
        assert "revenue_trend" in data


class TestMarketSummary:
    """MarketSummary Schema 验证"""

    def test_valid_market_summary(self) -> None:
        """有效的 MarketSummary 实例创建成功"""
        summary = MarketSummary(
            summary_text="这是一个市场摘要，用于测试市场数据的结构化分析能力。",
            key_points=["市场规模大", "增长快速"],
            confidence_score=0.9,
            market_size="市场规模约1000亿元",
            competitive_landscape="竞争格局分散",
            growth_drivers=["技术升级", "政策支持"],
            customer_insights="客户满意度评分4.2/5",
        )
        assert summary.market_size == "市场规模约1000亿元"
        assert len(summary.growth_drivers) == 2

    def test_confidence_score_boundary(self) -> None:
        """confidence_score 边界值 0.0 和 1.0 有效"""
        summary_low = MarketSummary(
            summary_text="这是一个市场摘要，用于测试市场数据的结构化分析能力。",
            key_points=["市场规模大"],
            confidence_score=0.0,
            market_size="市场规模大",
            competitive_landscape="竞争激烈",
            growth_drivers=["技术升级"],
            customer_insights="客户满意度高",
        )
        assert summary_low.confidence_score == 0.0

        summary_high = MarketSummary(
            summary_text="这是一个市场摘要，用于测试市场数据的结构化分析能力。",
            key_points=["市场规模大"],
            confidence_score=1.0,
            market_size="市场规模大",
            competitive_landscape="竞争激烈",
            growth_drivers=["技术升级"],
            customer_insights="客户满意度高",
        )
        assert summary_high.confidence_score == 1.0


class TestTechnicalSummary:
    """TechnicalSummary Schema 验证"""

    def test_valid_technical_summary(self) -> None:
        """有效的 TechnicalSummary 实例创建成功"""
        summary = TechnicalSummary(
            summary_text="这是一个技术摘要，用于测试技术数据的结构化分析能力。",
            key_points=["技术架构先进", "安全性高"],
            confidence_score=0.75,
            technology_stack="Python/React/PostgreSQL",
            innovation_points=["多Agent协作", "高保真溯源"],
            technical_risks=["数据安全合规"],
            architecture_overview="六边形架构，微服务部署",
        )
        assert summary.technology_stack == "Python/React/PostgreSQL"
        assert len(summary.innovation_points) == 2

    def test_risk_factors_validation(self) -> None:
        """technical_risks 字段验证"""
        with pytest.raises(ValidationError):
            TechnicalSummary(
                summary_text="这是一个技术摘要，用于测试技术数据的结构化分析能力。",
                key_points=["技术先进"],
                confidence_score=0.5,
                technology_stack="Python",
                innovation_points=["创新点"],
                technical_risks=[],  # 空列表，但 risk_factors 是 required 字段
                architecture_overview="微服务架构",
            )


class TestPerspectiveSchemaMap:
    """PERSPECTIVE_SCHEMA_MAP 映射验证"""

    def test_map_contains_all_perspectives(self) -> None:
        """映射包含所有三个视角"""
        assert "financial" in PERSPECTIVE_SCHEMA_MAP
        assert "market" in PERSPECTIVE_SCHEMA_MAP
        assert "technical" in PERSPECTIVE_SCHEMA_MAP

    def test_map_correct_types(self) -> None:
        """映射指向正确的 Schema 类"""
        assert PERSPECTIVE_SCHEMA_MAP["financial"] is FinancialSummary
        assert PERSPECTIVE_SCHEMA_MAP["market"] is MarketSummary
        assert PERSPECTIVE_SCHEMA_MAP["technical"] is TechnicalSummary
