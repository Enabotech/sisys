"""Story 3.8 高保真溯源集成测试

验证 TraceabilityService 与 LayeredRetrievalPort 的层间协作，
以及 TraceabilityPort 端口解析、异常路径降级。

两种子模式：
1. Mock 工厂：AsyncMock(spec=LayeredRetrievalPort) + _make_*() 工厂函数
   （溯源不涉及数据库持久化，基础设施端口用 Mock 替代）
2. 端口解析真实验证：通过 Resolver 验证 DI 容器解析出真实 TraceabilityService 实例
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import TraceabilityError
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.layered_retrieval import LayeredRetrievalPort
from src.domain.ports.traceability import TraceabilityPort


def _make_search_result(
    chunk_id: str,
    score: float,
    document_id: str | None = None,
    content: str = "测试切片内容",
    page_start: int = 1,
    bbox: dict | None = None,
) -> SearchResult:
    """构造测试用 SearchResult"""
    if document_id is None:
        document_id = str(uuid.uuid4())
    return SearchResult(
        id=chunk_id,
        score=score,
        payload={
            "chunk_id": chunk_id,
            "document_id": document_id,
            "content": content,
            "page_start": page_start,
            "page_end": page_start,
            "parent_chunk_id": None,
            "index_level": "parent",
            "chunk_header": "[文档: 测试文档]",
            **({"bbox": bbox} if bbox else {}),
        },
    )


def _make_mock_retrieval(results: list[SearchResult] | None = None) -> AsyncMock:
    """构造 Mock LayeredRetrievalPort"""
    mock = AsyncMock(spec=LayeredRetrievalPort)

    async def mock_search_top_down(
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        return results or []

    mock.search_top_down.side_effect = mock_search_top_down
    return mock


def _make_service(retrieval_port: Any) -> Any:
    """构造 TraceabilityService 实例"""
    from src.application.services.traceability_service import TraceabilityService

    return TraceabilityService(retrieval_port=retrieval_port)


class TestIntegrationTraceSuccess:
    """溯源成功集成测试"""

    @pytest.mark.asyncio
    async def test_trace_returns_citations_from_retrieval(self) -> None:
        """trace() 从 LayeredRetrievalPort 检索结果构造引文"""
        doc_id = str(uuid.uuid4())
        results = [
            _make_search_result("chunk-001", 0.92, doc_id, "切片一"),
            _make_search_result("chunk-002", 0.85, doc_id, "切片二"),
        ]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim="测试结论", top_k=10, min_confidence=0.7)
        assert result["citation_count"] == 2
        assert all(c.document_id == uuid.UUID(doc_id) for c in result["citations"])

    @pytest.mark.asyncio
    async def test_trace_min_confidence_filters_low_scores(self) -> None:
        """min_confidence 过滤低分引文"""
        results = [
            _make_search_result("high", 0.95),
            _make_search_result("low", 0.60),
        ]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim="测试结论", min_confidence=0.7)
        assert result["citation_count"] == 1
        assert result["citations"][0].chunk_id == "high"

    @pytest.mark.asyncio
    async def test_trace_empty_retrieval_returns_empty(self) -> None:
        """空检索结果返回空引文列表"""
        service = _make_service(_make_mock_retrieval([]))
        result = await service.trace(claim="无关查询")
        assert result["citation_count"] == 0
        assert result["highest_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_trace_bbox_extracted_correctly(self) -> None:
        """bbox 从 payload 正确提取"""
        bbox_data = {"x": 100.0, "y": 200.0, "width": 300.0, "height": 50.0, "page": 2}
        results = [_make_search_result("chunk-001", 0.92, bbox=bbox_data)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim="测试结论")
        assert result["has_bbox_support"] is True
        assert result["citations"][0].bbox is not None
        assert result["citations"][0].bbox.page == 2


class TestIntegrationTraceErrors:
    """溯源异常集成测试"""

    @pytest.mark.asyncio
    async def test_retrieval_exception_wraps_traceability_error(self) -> None:
        """检索异常包装为 TraceabilityError"""
        mock = AsyncMock(spec=LayeredRetrievalPort)
        mock.search_top_down.side_effect = Exception("Qdrant 连接超时")
        service = _make_service(mock)
        with pytest.raises(TraceabilityError):
            await service.trace(claim="测试结论")

    @pytest.mark.asyncio
    async def test_get_citation_detail_after_trace(self) -> None:
        """trace() 后通过 get_citation_detail 获取引文"""
        results = [_make_search_result("chunk-001", 0.92)]
        service = _make_service(_make_mock_retrieval(results))
        await service.trace(claim="测试结论")
        citation = await service.get_citation_detail("chunk-001-cit")
        assert citation is not None

    @pytest.mark.asyncio
    async def test_get_citation_by_document_after_trace(self) -> None:
        """trace() 后通过 get_citation_by_document 获取引文"""
        doc_id = str(uuid.uuid4())
        results = [
            _make_search_result("chunk-001", 0.92, doc_id),
            _make_search_result("chunk-002", 0.85, doc_id),
        ]
        service = _make_service(_make_mock_retrieval(results))
        await service.trace(claim="测试结论")
        citations = await service.get_citation_by_document(uuid.UUID(doc_id))
        assert len(citations) == 2


class TestIntegrationPortResolver:
    """端口解析集成测试"""

    @pytest.mark.asyncio
    async def test_traceability_service_resolves_from_registry(self) -> None:
        """traceability_service 端口可从注册中心解析为真实实例"""
        from src.domain.ports.resolver import Resolver

        resolver = Resolver()
        service = resolver.resolve("traceability_service")
        assert isinstance(service, TraceabilityPort)
        assert hasattr(service, "trace")
        assert hasattr(service, "get_citation_detail")
        assert hasattr(service, "get_citation_by_document")
