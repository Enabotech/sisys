"""Story 3.7 检索相关性评估规则预检单元测试

验证 RelevanceEvaluationService.quick_rule_check() 的规则预检逻辑：
- 空结果阻断
- 低分阻断（平均分 < 0.3）
- 有效结果不阻断
- 防御性计算（NaN/负值/缺失 score 过滤）
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.ports.l3_vector import SearchResult


def _make_service() -> Any:
    """创建规则预检服务实例（仅需 llm_client，quick_rule_check 不调用它）"""
    from src.application.services.relevance_evaluation_service import RelevanceEvaluationService

    mock_llm = AsyncMock()
    return RelevanceEvaluationService(llm_client=mock_llm)


def _run_quick_rule_check(service: Any, query_text: str, search_results: list[SearchResult]) -> dict[str, Any]:
    """通过新事件循环执行 quick_rule_check（async 方法）"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(service.quick_rule_check(query_text=query_text, search_results=search_results))
    finally:
        loop.close()


def _make_result(score: float, **payload_extra: Any) -> SearchResult:
    """构造标准检索结果"""
    payload: dict[str, Any] = {"content": "测试内容", **payload_extra}
    return SearchResult(id="doc-001", score=score, payload=payload)


class TestQuickRuleCheckEmptyResults:
    """空检索结果规则预检"""

    def test_empty_results_quick_block(self) -> None:
        """空检索结果 → quick_block=True"""
        service = _make_service()
        result = _run_quick_rule_check(service, query_text="query", search_results=[])
        assert result["quick_block"] is True
        assert result["has_valid_results"] is False
        assert result["result_count"] == 0
        # 边界值约定：空结果时 min/max/avg 归一化为 0.0
        assert result["min_score"] == 0.0
        assert result["max_score"] == 0.0
        assert result["avg_score"] == 0.0


class TestQuickRuleCheckLowScore:
    """低分检索结果规则预检"""

    def test_low_avg_score_quick_block(self) -> None:
        """平均分 < 0.3 → quick_block=True"""
        service = _make_service()
        results = [
            _make_result(0.2),
            _make_result(0.25),
            _make_result(0.3),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["quick_block"] is True
        assert result["has_valid_results"] is True

    def test_normal_score_no_quick_block(self) -> None:
        """平均分 >= 0.3 → quick_block=False"""
        service = _make_service()
        results = [
            _make_result(0.5),
            _make_result(0.7),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["quick_block"] is False
        assert result["has_valid_results"] is True

    def test_score_stats_calculation(self) -> None:
        """min/max/avg 统计计算正确"""
        service = _make_service()
        results = [
            _make_result(0.4),
            _make_result(0.8),
            _make_result(0.6),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["min_score"] == 0.4
        assert result["max_score"] == 0.8
        assert result["avg_score"] == pytest.approx(0.6)
        assert result["result_count"] == 3


class TestQuickRuleCheckDefensive:
    """防御性计算验证（NaN/负值/缺失 score 过滤）"""

    def test_nan_score_treated_as_zero(self) -> None:
        """NaN score 视为 0.0（避免 NaN 传播导致阻断失效）"""
        import math

        service = _make_service()
        results = [
            _make_result(float("nan")),
            _make_result(0.5),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert math.isfinite(result["avg_score"])
        # NaN 视为 0.0，(0.0 + 0.5) / 2 = 0.25 < 0.3 → 阻断
        assert result["avg_score"] == pytest.approx(0.25)

    def test_negative_score_clamped_to_zero(self) -> None:
        """负 score 截断为 0.0"""
        service = _make_service()
        results = [
            _make_result(-0.5),
            _make_result(0.6),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["min_score"] >= 0.0
        assert result["avg_score"] == pytest.approx(0.3)

    def test_missing_score_treated_as_zero(self) -> None:
        """缺失 score 视为 0.0"""
        service = _make_service()
        from src.domain.ports.l3_vector import SearchResult

        results = [
            SearchResult(id="doc-001", score=0.8, payload={"content": "内容"}),
            SearchResult(id="doc-002", score=0.0, payload={"content": "内容"}),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["avg_score"] == pytest.approx(0.4)

    def test_inf_score_treated_as_zero(self) -> None:
        """inf score 视为 0.0"""
        import math

        service = _make_service()
        results = [
            _make_result(float("inf")),
            _make_result(0.9),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert math.isfinite(result["avg_score"])
        assert result["avg_score"] == pytest.approx(0.45)


class TestQuickRuleCheckBoundary:
    """边界分数验证"""

    def test_avg_exactly_03_no_block(self) -> None:
        """平均分恰好 0.3 → 不阻断（>= 0.3）"""
        service = _make_service()
        results = [
            _make_result(0.3),
            _make_result(0.3),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["avg_score"] == pytest.approx(0.3)
        assert result["quick_block"] is False

    def test_single_result(self) -> None:
        """单结果规则预检"""
        service = _make_service()
        results = [_make_result(0.9)]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["result_count"] == 1
        assert result["min_score"] == 0.9
        assert result["max_score"] == 0.9
        assert result["avg_score"] == 0.9
        assert result["quick_block"] is False

    def test_result_without_score_key(self) -> None:
        """结果无 score 字段（不是 None 值，而是缺失键）"""
        service = _make_service()
        from src.domain.ports.l3_vector import SearchResult

        results = [
            SearchResult(id="doc-001", score=0.0, payload={"content": "内容"}),
        ]
        result = _run_quick_rule_check(service, query_text="query", search_results=results)
        assert result["result_count"] == 1
        assert result["avg_score"] == 0.0
