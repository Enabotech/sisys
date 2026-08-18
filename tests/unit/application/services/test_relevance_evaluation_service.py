"""Story 3.7 检索相关性评估服务单元测试

验证 RelevanceEvaluationService 的完整评估流程：
- 规则预检 → LLM 评估
- 空结果/低分阻断
- LLM 调用失败异常
- 时效性评估
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMConfig


def _make_service(llm_client: Any = None) -> Any:
    """创建评估服务实例"""
    from src.application.services.relevance_evaluation_service import RelevanceEvaluationService

    if llm_client is None:
        llm_client = AsyncMock()
    return RelevanceEvaluationService(llm_client=llm_client)


def _make_search_result(score: float, **payload_extra: Any) -> SearchResult:
    """构造标准检索结果"""
    payload: dict[str, Any] = {"content": "测试内容", **payload_extra}
    return SearchResult(id="doc-001", score=score, payload=payload)


def _make_mock_llm(result_kwargs: dict[str, Any] | None = None) -> AsyncMock:
    """创建 Mock LLMClientPort，返回标准 RelevanceEvaluation 结果"""
    mock = AsyncMock()

    async def mock_structured_generate(
        prompt: str,
        response_schema: type[Any],
        config: Any = None,
        system_prompt: str | None = None,
    ) -> Any:
        from src.application.services.relevance_schemas import RelevanceEvaluation

        kwargs: dict[str, Any] = {
            "context_relevance": 0.85,
            "context_relevance_reason": "检索结果与查询高度相关",
            "completeness": 0.75,
            "completeness_reason": "核心信息已覆盖",
            "timeliness": 0.90,
            "timeliness_reason": "数据更新及时",
        }
        if result_kwargs:
            kwargs.update(result_kwargs)
        return RelevanceEvaluation(**kwargs)

    mock.structured_generate.side_effect = mock_structured_generate
    return mock


class TestEvaluateSuccess:
    """评估正常流程"""

    @pytest.mark.asyncio
    async def test_evaluate_with_valid_results(self) -> None:
        """有效检索结果 → 正常评估返回"""
        mock_llm = _make_mock_llm()
        service = _make_service(mock_llm)
        results = [
            _make_search_result(0.8, updated_at="2026-06-01T00:00:00"),
            _make_search_result(0.7, updated_at="2026-05-01T00:00:00"),
        ]

        result = await service.evaluate(query_text="测试查询", search_results=results)

        assert result.context_relevance == 0.85
        assert result.completeness == 0.75
        assert result.timeliness == 0.90
        assert result.overall_score == pytest.approx((0.85 + 0.75 + 0.90) / 3.0)
        assert result.should_block is False
        assert result.block_reason is None

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_prompt(self) -> None:
        """LLM 被传入正确的 Prompt 和 Schema"""
        mock_llm = _make_mock_llm()
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8, updated_at="2026-06-01T00:00:00")]

        await service.evaluate(query_text="测试查询", search_results=results)

        mock_llm.structured_generate.assert_called_once()
        call_kwargs = mock_llm.structured_generate.call_args[1]
        assert "prompt" in call_kwargs
        assert "response_schema" in call_kwargs
        assert "system_prompt" in call_kwargs
        # 验证 response_schema 是 RelevanceEvaluation
        from src.application.services.relevance_schemas import RelevanceEvaluation

        assert call_kwargs["response_schema"] is RelevanceEvaluation

    @pytest.mark.asyncio
    async def test_config_passed_through(self) -> None:
        """config 参数透传给 LLMClientPort"""
        mock_llm = _make_mock_llm()
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8, updated_at="2026-06-01T00:00:00")]
        config = LLMConfig(model="gpt-4", temperature=0.5)

        await service.evaluate(query_text="测试查询", search_results=results, config=config)

        call_kwargs = mock_llm.structured_generate.call_args[1]
        assert call_kwargs["config"] is config


class TestEvaluateRuleCheckBlock:
    """规则预检阻断场景"""

    @pytest.mark.asyncio
    async def test_empty_results_returns_blocked(self) -> None:
        """空检索结果 → 直接返回阻断结果，不调用 LLM"""
        mock_llm = AsyncMock()
        service = _make_service(mock_llm)

        result = await service.evaluate(query_text="测试查询", search_results=[])

        assert result.should_block is True
        assert result.block_reason is not None
        mock_llm.structured_generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_low_avg_score_returns_blocked(self) -> None:
        """平均分 < 0.3 → 直接返回阻断结果，不调用 LLM"""
        mock_llm = AsyncMock()
        service = _make_service(mock_llm)
        results = [
            _make_search_result(0.2),
            _make_search_result(0.25),
        ]

        result = await service.evaluate(query_text="测试查询", search_results=results)

        assert result.should_block is True
        assert result.block_reason is not None
        mock_llm.structured_generate.assert_not_called()


class TestEvaluateLLMFailure:
    """LLM 调用失败场景"""

    @pytest.mark.asyncio
    async def test_llm_api_error_wraps_to_relevance_error(self) -> None:
        """LLMAPIError 包装为 RelevanceEvaluationError"""
        from src.domain.exceptions import RelevanceEvaluationError
        from src.domain.exceptions.llm_exceptions import LLMAPIError

        mock_llm = AsyncMock()
        mock_llm.structured_generate.side_effect = LLMAPIError(
            message="LLM API 调用失败",
            cause=Exception("API 返回 500"),
        )
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8)]

        with pytest.raises(RelevanceEvaluationError) as exc_info:
            await service.evaluate(query_text="测试查询", search_results=results)

        assert exc_info.value.code == "EXCEPTION_360"
        assert "query_text" in exc_info.value.context
        assert exc_info.value.context["result_count"] == 1

    @pytest.mark.asyncio
    async def test_llm_response_error_wraps_to_relevance_error(self) -> None:
        """LLMResponseError 包装为 RelevanceEvaluationError"""
        from src.domain.exceptions import RelevanceEvaluationError
        from src.domain.exceptions.llm_exceptions import LLMResponseError

        mock_llm = AsyncMock()
        mock_llm.structured_generate.side_effect = LLMResponseError(
            message="LLM 响应解析错误",
        )
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8)]

        with pytest.raises(RelevanceEvaluationError) as exc_info:
            await service.evaluate(query_text="测试查询", search_results=results)

        assert exc_info.value.code == "EXCEPTION_360"

    @pytest.mark.asyncio
    async def test_llm_config_error_passthrough(self) -> None:
        """LLMConfigError 透传不包装"""
        from src.domain.exceptions.llm_exceptions import LLMConfigError

        mock_llm = AsyncMock()
        mock_llm.structured_generate.side_effect = LLMConfigError(
            message="LLM 配置错误",
            config_key="api_key",
        )
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8)]

        with pytest.raises(LLMConfigError):
            await service.evaluate(query_text="测试查询", search_results=results)

    @pytest.mark.asyncio
    async def test_generic_exception_wraps_to_relevance_error(self) -> None:
        """通用异常（非 LLM 异常）被兜底捕获并包装为 RelevanceEvaluationError"""
        from src.domain.exceptions import RelevanceEvaluationError

        mock_llm = AsyncMock()
        mock_llm.structured_generate.side_effect = RuntimeError("意外的运行时错误")
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8)]

        with pytest.raises(RelevanceEvaluationError) as exc_info:
            await service.evaluate(query_text="测试查询", search_results=results)

        assert exc_info.value.code == "EXCEPTION_360"
        assert "query_text" in exc_info.value.context
        assert exc_info.value.context["result_count"] == 1

    @pytest.mark.asyncio
    async def test_cancelled_error_passthrough(self) -> None:
        """CancelledError 透传不包装，避免干扰协程取消机制"""
        import asyncio

        mock_llm = AsyncMock()
        mock_llm.structured_generate.side_effect = asyncio.CancelledError()
        service = _make_service(mock_llm)
        results = [_make_search_result(0.8)]

        with pytest.raises(asyncio.CancelledError):
            await service.evaluate(query_text="测试查询", search_results=results)


class TestEvaluateTimeliness:
    """时效性评估验证"""

    def test_timeliness_valid_until_expired(self) -> None:
        """valid_until < now → 时效性 0.0"""
        service = _make_service()
        from datetime import timedelta

        payload = {
            "content": "测试内容",
            "valid_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }
        result = _make_search_result(0.8, **payload)
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 0.0

    def test_timeliness_updated_at_old(self) -> None:
        """updated_at > 365 天 → 时效性 0.3"""
        service = _make_service()
        from datetime import timedelta

        payload = {
            "content": "测试内容",
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(),
        }
        result = _make_search_result(0.8, **payload)
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 0.3

    def test_timeliness_updated_at_medium(self) -> None:
        """updated_at 180-365 天 → 时效性 0.6"""
        service = _make_service()
        from datetime import timedelta

        payload = {
            "content": "测试内容",
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        }
        result = _make_search_result(0.8, **payload)
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 0.6

    def test_timeliness_updated_at_recent(self) -> None:
        """updated_at 30-180 天 → 时效性 0.8"""
        service = _make_service()
        from datetime import timedelta

        payload = {
            "content": "测试内容",
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        }
        result = _make_search_result(0.8, **payload)
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 0.8

    def test_timeliness_updated_at_fresh(self) -> None:
        """updated_at < 30 天 → 时效性 1.0"""
        service = _make_service()
        from datetime import timedelta

        payload = {
            "content": "测试内容",
            "updated_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        }
        result = _make_search_result(0.8, **payload)
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 1.0

    def test_timeliness_no_timestamp(self) -> None:
        """无时效性字段 → 默认 1.0"""
        service = _make_service()
        result = _make_search_result(0.8, content="测试内容")
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 1.0

    def test_timeliness_created_at_fallback(self) -> None:
        """无 updated_at 但有 created_at → 使用 created_at"""
        service = _make_service()
        from datetime import timedelta

        payload = {
            "content": "测试内容",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        }
        result = _make_search_result(0.8, **payload)
        timeliness = service._evaluate_timeliness([result])
        assert timeliness == 1.0

    def test_timeliness_average(self) -> None:
        """多结果时效性评分取平均值"""
        service = _make_service()
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        results = [
            _make_search_result(0.8, updated_at=(now - timedelta(days=10)).isoformat()),  # 1.0
            _make_search_result(0.7, updated_at=(now - timedelta(days=200)).isoformat()),  # 0.6
        ]
        timeliness = service._evaluate_timeliness(results)
        assert timeliness == pytest.approx((1.0 + 0.6) / 2.0)

    def test_timeliness_empty_results(self) -> None:
        """空结果 → 默认 1.0"""
        service = _make_service()
        timeliness = service._evaluate_timeliness([])
        assert timeliness == 1.0


class TestBuildSearchContextWithTimeliness:
    """含时效性标记的检索上下文构建验证"""

    def test_build_context_with_timeliness_marker(self) -> None:
        """检索上下文包含时效性标记"""
        service = _make_service()
        results = [
            _make_search_result(0.8, content="内容1", updated_at="2026-06-15T00:00:00"),
        ]
        context = service._build_search_context_with_timeliness(results)
        assert "[时效性:" in context
        assert "updated_at=2026-06-15T00:00:00" in context
        assert "内容1" in context

    def test_build_context_without_timeliness(self) -> None:
        """无时效性字段时不附加标记"""
        service = _make_service()
        results = [
            _make_search_result(0.8, content="内容1"),
        ]
        context = service._build_search_context_with_timeliness(results)
        assert "[时效性:" not in context
        assert "内容1" in context

    def test_build_context_empty_results(self) -> None:
        """空结果返回默认文本"""
        service = _make_service()
        context = service._build_search_context_with_timeliness([])
        assert "无相关检索结果" in context
