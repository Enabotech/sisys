"""Story 3.7 检索相关性评估集成测试

验证 RelevanceEvaluationService 与 LLMClientPort 的层间协作：
- 规则预检 → LLM 深度评估
- 摘要生成服务集成评估守卫（阻断/降级）
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.ports.l3_vector import SearchResult


def _make_search_result(score: float, **payload_extra: Any) -> SearchResult:
    """构造标准检索结果"""
    payload: dict[str, Any] = {"content": "测试内容", **payload_extra}
    return SearchResult(id="doc-001", score=score, payload=payload)


def run_async(coro: Any) -> Any:
    """在独立事件循环中执行协程并确保循环关闭（避免 get_event_loop 废弃警告与循环泄漏）"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRelevanceEvaluationIntegration:
    """RelevanceEvaluationService + Mock LLMClientPort 集成"""

    def test_quick_rule_check_pure_computation(self) -> None:
        """quick_rule_check 为纯计算，不触发 LLM 调用"""
        from src.application.services.relevance_evaluation_service import RelevanceEvaluationService
        from src.domain.ports.relevance_evaluation import RuleBasedResult

        mock_llm = AsyncMock()
        service = RelevanceEvaluationService(llm_client=mock_llm)
        results = [_make_search_result(0.5), _make_search_result(0.7)]

        async def _run() -> RuleBasedResult:
            return await service.quick_rule_check(query_text="query", search_results=results)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()

        assert result["quick_block"] is False
        mock_llm.assert_not_called()

    def test_evaluate_runs_rule_check_then_llm(self) -> None:
        """evaluate 先规则预检，再调用 LLM"""
        from src.application.services.relevance_evaluation_service import RelevanceEvaluationService

        mock_llm = AsyncMock()

        async def mock_structured_generate(
            prompt: str,
            response_schema: type[Any],
            config=None,
            system_prompt=None,
        ) -> Any:
            from src.application.services.relevance_schemas import RelevanceEvaluation

            return RelevanceEvaluation(
                context_relevance=0.8,
                context_relevance_reason="相关",
                completeness=0.7,
                completeness_reason="完整",
                timeliness=0.9,
                timeliness_reason="及时",
            )

        mock_llm.structured_generate.side_effect = mock_structured_generate
        service = RelevanceEvaluationService(llm_client=mock_llm)
        results = [_make_search_result(0.6)]

        async def _run() -> Any:
            return await service.evaluate(query_text="query", search_results=results)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()

        mock_llm.structured_generate.assert_called_once()
        assert result.overall_score == (0.8 + 0.7 + 0.9) / 3.0
        assert result.should_block is False


class TestSummaryGenerationGuard:
    """SummaryGenerationService + RelevanceEvaluationService 评估守卫集成"""

    def _make_summary_service(
        self,
        relevance_service: Any,
    ) -> Any:
        """构造带评估守卫的摘要生成服务"""
        from src.application.services.summary_generation_service import SummaryGenerationService

        mock_llm = AsyncMock()
        mock_layered = AsyncMock()
        mock_embedding = AsyncMock()
        mock_l3 = AsyncMock()
        return SummaryGenerationService(
            llm_client=mock_llm,
            layered_retrieval=mock_layered,
            embedding_service=mock_embedding,
            l3_vector=mock_l3,
            relevance_evaluation_service=relevance_service,
        )

    def test_guard_blocked_raises(self) -> None:
        """规则预检阻断 → 抛出 RelevanceEvaluationBlockedError"""
        from src.application.services.relevance_evaluation_service import RelevanceEvaluationService
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        mock_llm = AsyncMock()
        relevance_service = RelevanceEvaluationService(llm_client=mock_llm)
        service = self._make_summary_service(relevance_service)
        results = [_make_search_result(0.15)]

        async def _run() -> Any:
            return await service.generate_summary(
                query_text="query",
                search_results=results,
                perspective="financial",
            )

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(RelevanceEvaluationBlockedError):
                loop.run_until_complete(_run())
        finally:
            loop.close()

    def test_guard_degraded_when_llm_fails(self) -> None:
        """LLM 评估调用失败 → 降级跳过评估，直接生成摘要"""
        from src.application.services.relevance_evaluation_service import RelevanceEvaluationService
        from src.domain.exceptions.llm_exceptions import LLMAPIError

        eval_mock_llm = AsyncMock()
        eval_mock_llm.structured_generate.side_effect = LLMAPIError(
            message="LLM API 调用失败",
        )
        relevance_service = RelevanceEvaluationService(llm_client=eval_mock_llm)
        service = self._make_summary_service(relevance_service)

        summary_fake = MagicMock()
        summary_fake.summary_text = "测试摘要"
        summary_fake.key_points = ["要点"]
        summary_fake.confidence_score = 0.8

        service._llm_client.structured_generate.side_effect = lambda **kwargs: summary_fake

        # 摘要生成不应抛异常（评估降级）
        result = run_async(
            service.generate_summary(
                query_text="query",
                search_results=[_make_search_result(0.6)],
                perspective="financial",
            )
        )
        assert result is not None

    def test_guard_skipped_when_service_none(self) -> None:
        """评估服务未注入（None）→ 跳过评估直接生成摘要"""
        from src.application.services.summary_generation_service import SummaryGenerationService

        mock_llm = AsyncMock()
        mock_layered = AsyncMock()
        mock_embedding = AsyncMock()
        mock_l3 = AsyncMock()

        summary_fake = MagicMock()
        summary_fake.summary_text = "测试摘要"
        summary_fake.key_points = ["要点"]
        summary_fake.confidence_score = 0.8
        mock_llm.structured_generate.return_value = summary_fake

        service = SummaryGenerationService(
            llm_client=mock_llm,
            layered_retrieval=mock_layered,
            embedding_service=mock_embedding,
            l3_vector=mock_l3,
            relevance_evaluation_service=None,
        )

        result = run_async(
            service.generate_summary(
                query_text="query",
                search_results=[_make_search_result(0.6)],
                perspective="financial",
            )
        )
        assert result is not None

    def test_guard_passes_when_evaluation_succeeds(self) -> None:
        """评估通过 → 正常生成摘要"""
        from src.application.services.relevance_evaluation_service import RelevanceEvaluationService

        eval_mock_llm = AsyncMock()

        async def mock_eval_structured_generate(
            prompt: str,
            response_schema: type[Any],
            config=None,
            system_prompt=None,
        ) -> Any:
            from src.application.services.relevance_schemas import RelevanceEvaluation

            return RelevanceEvaluation(
                context_relevance=0.8,
                context_relevance_reason="相关",
                completeness=0.7,
                completeness_reason="完整",
                timeliness=0.9,
                timeliness_reason="及时",
            )

        eval_mock_llm.structured_generate.side_effect = mock_eval_structured_generate
        relevance_service = RelevanceEvaluationService(llm_client=eval_mock_llm)
        service = self._make_summary_service(relevance_service)

        summary_fake = MagicMock()
        summary_fake.summary_text = "测试摘要"
        summary_fake.key_points = ["要点"]
        summary_fake.confidence_score = 0.8
        service._llm_client.structured_generate.return_value = summary_fake

        result = run_async(
            service.generate_summary(
                query_text="query",
                search_results=[_make_search_result(0.6)],
                perspective="financial",
            )
        )
        assert result is not None
