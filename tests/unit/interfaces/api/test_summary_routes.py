"""Story 3.6 摘要生成 API 路由单元测试

验证 create_summary_router 检索集成、跨文档模式、异常转换等逻辑。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware


def _make_token() -> object:
    """构造测试用 TokenPayload"""
    from datetime import UTC, datetime

    from src.domain.value_objects.token_payload import TokenPayload

    return TokenPayload(
        user_id=uuid.uuid4(),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _make_search_results(count: int = 3) -> list[dict[str, Any]]:
    """构造测试用检索结果"""
    return [
        {
            "id": f"chunk-{i}",
            "score": 1.0 - i * 0.1,
            "payload": {
                "content": f"测试文档内容 {i}",
                "document_id": f"doc-{i}",
                "index_level": "child",
            },
        }
        for i in range(1, count + 1)
    ]


def _make_app(
    summary_result: dict[str, Any] | None = None,
    search_results: list[dict[str, Any]] | None = None,
    summary_side_effect: Exception | None = None,
    search_side_effect: Exception | None = None,
) -> tuple[TestClient, AsyncMock, AsyncMock]:
    """创建带摘要路由的测试 FastAPI 应用"""
    from src.interfaces.api.summary import create_summary_router

    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    summary_service = AsyncMock()
    if summary_result:
        summary_service.generate_summary.return_value = summary_result
    if summary_side_effect:
        summary_service.generate_summary.side_effect = summary_side_effect

    layered_retrieval = AsyncMock()
    if search_results is not None:
        layered_retrieval.search_top_down.return_value = search_results
    if search_side_effect:
        layered_retrieval.search_top_down.side_effect = search_side_effect

    mock_user = _make_token()

    def get_user_override():
        return mock_user

    router = create_summary_router(
        summary_service=summary_service,
        layered_retrieval=layered_retrieval,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    return TestClient(app), summary_service, layered_retrieval


def _make_summary_dict(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造测试用摘要响应"""
    result = {
        "summary_text": "测试摘要内容",
        "key_points": ["要点1", "要点2"],
        "confidence_score": 0.85,
        "revenue_trend": "增长趋势",
        "profit_analysis": "利润分析",
        "risk_factors": ["风险1"],
        "market_position": "市场领先",
    }
    if overrides:
        result.update(overrides)
    return result


class TestNonCrossDocumentSummary:
    """非跨文档模式（单文档摘要）"""

    SUMMARY_PATH = "/api/v1/search/summary"

    def test_retrieval_called_with_top_k(self) -> None:
        """非跨文档模式调用检索层，传 top_k 参数"""
        client, summary_svc, retrieval_svc = _make_app(
            summary_result=_make_summary_dict(),
            search_results=_make_search_results(),
        )
        client.post(
            self.SUMMARY_PATH,
            json={
                "query_text": "测试查询",
                "perspective": "financial",
                "top_k": 5,
            },
        )
        retrieval_svc.search_top_down.assert_awaited_once()
        call_kwargs = retrieval_svc.search_top_down.call_args[1]
        assert call_kwargs["limit"] == 5

    def test_retrieval_failure_fallback(self) -> None:
        """检索失败时降级为空结果，请求仍成功"""
        client, summary_svc, _ = _make_app(
            summary_result=_make_summary_dict(),
            search_side_effect=RuntimeError("检索服务不可用"),
        )
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        assert response.status_code == 200

    def test_search_results_passed_to_generate_summary(self) -> None:
        """检索结果传入 generate_summary"""
        client, summary_svc, retrieval_svc = _make_app(
            summary_result=_make_summary_dict(),
            search_results=_make_search_results(),
        )
        client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        call_kwargs = summary_svc.generate_summary.call_args[1]
        assert len(call_kwargs["search_results"]) == 3

    def test_source_documents_in_response(self) -> None:
        """响应包含 source_documents（从检索结果 document_id 提取）"""
        client, summary_svc, retrieval_svc = _make_app(
            summary_result=_make_summary_dict(),
            search_results=_make_search_results(),
        )
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        data = response.json()
        assert "source_documents" in data
        assert len(data["source_documents"]) == 3
        assert "doc-1" in data["source_documents"]


class TestCrossDocumentSummary:
    """跨文档摘要模式"""

    SUMMARY_PATH = "/api/v1/search/summary"

    def test_cross_document_returns_200(self) -> None:
        """跨文档模式返回 200"""
        client, summary_svc, _ = _make_app(
            summary_result=_make_summary_dict(),
        )
        response = client.post(
            self.SUMMARY_PATH,
            json={
                "query_text": "测试查询",
                "perspective": "financial",
                "cross_document": True,
            },
        )
        assert response.status_code == 200

    def test_cross_document_passed_to_generate_summary(self) -> None:
        """cross_document 参数透传到 generate_summary"""
        client, summary_svc, _ = _make_app(
            summary_result=_make_summary_dict(),
        )
        client.post(
            self.SUMMARY_PATH,
            json={
                "query_text": "测试查询",
                "perspective": "financial",
                "cross_document": True,
            },
        )
        call_kwargs = summary_svc.generate_summary.call_args[1]
        assert call_kwargs["cross_document"] is True

    def test_limit_passed_to_generate_summary(self) -> None:
        """top_k 作为 limit 透传到 generate_summary"""
        client, summary_svc, _ = _make_app(
            summary_result=_make_summary_dict(),
        )
        client.post(
            self.SUMMARY_PATH,
            json={
                "query_text": "测试查询",
                "perspective": "financial",
                "cross_document": True,
                "top_k": 20,
            },
        )
        call_kwargs = summary_svc.generate_summary.call_args[1]
        assert call_kwargs["limit"] == 20


class TestErrorHandling:
    """API 路由异常处理"""

    SUMMARY_PATH = "/api/v1/search/summary"

    def test_summary_generation_error_returns_500(self) -> None:
        """SummaryGenerationError 返回 500"""
        from src.domain.exceptions.summary_exceptions import SummaryGenerationError

        client, _, _ = _make_app(
            summary_side_effect=SummaryGenerationError(perspective="financial", query_text="test"),
        )
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        assert response.status_code == 500

    def test_perspective_not_supported_returns_400(self) -> None:
        """SummaryPerspectiveNotSupportedError 返回 400"""
        from src.domain.exceptions.summary_exceptions import (
            SummaryPerspectiveNotSupportedError,
        )

        client, _, _ = _make_app(
            summary_side_effect=SummaryPerspectiveNotSupportedError(perspective="invalid"),
        )
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        assert response.status_code == 400

    def test_invalid_perspective_returns_400(self) -> None:
        """非法 perspective 返回 400（被 domain 异常处理器捕获）"""
        client, _, _ = _make_app(summary_result=_make_summary_dict())
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "INVALID"},
        )
        assert response.status_code == 400

    def test_empty_query_text_returns_400(self) -> None:
        """空查询文本返回 400"""
        client, _, _ = _make_app(summary_result=_make_summary_dict())
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "", "perspective": "financial"},
        )
        assert response.status_code == 400


class TestResponseFormat:
    """API 响应格式"""

    SUMMARY_PATH = "/api/v1/search/summary"

    def test_response_contains_all_fields(self) -> None:
        """响应包含所有必需字段"""
        summary_dict = _make_summary_dict()
        client, _, _ = _make_app(summary_result=summary_dict)
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        data = response.json()
        assert "summary" in data
        assert "query_text" in data
        assert "perspective" in data
        assert "confidence_score" in data
        assert "source_documents" in data

    def test_confidence_score_from_response(self) -> None:
        """置信度从摘要结果提取"""
        summary_dict = _make_summary_dict({"confidence_score": 0.75})
        client, _, _ = _make_app(summary_result=summary_dict)
        response = client.post(
            self.SUMMARY_PATH,
            json={"query_text": "测试查询", "perspective": "financial"},
        )
        data = response.json()
        assert data["confidence_score"] == 0.75
