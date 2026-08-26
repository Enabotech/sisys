"""Story 3.8 高保真溯源 TraceabilityService 单元测试

验证 TraceabilityService 的溯源逻辑、置信度计算、Bounding Box 提取、
排序、缓存和异常行为。使用 Mock LayeredRetrievalPort。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.layered_retrieval import LayeredRetrievalPort
from src.domain.value_objects.parsed_document import BoundingBox

_TEST_DOCUMENT_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_TEST_CLAIM = "公司营收2024年同比增长15%"


def _make_search_result(
    chunk_id: str,
    score: float,
    document_id: str = str(_TEST_DOCUMENT_ID),
    content: str = "测试切片内容",
    page_start: int = 1,
    bbox: dict | None = None,
) -> SearchResult:
    """构造测试用 SearchResult"""
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


def _make_service(retrieval_port: AsyncMock):
    """构造 TraceabilityService 实例"""
    from src.application.services.traceability_service import TraceabilityService

    return TraceabilityService(retrieval_port=retrieval_port)


class TestTraceSuccess:
    """溯源成功路径测试"""

    @pytest.mark.asyncio
    async def test_trace_returns_traceability_result(self) -> None:
        """trace() 返回 TraceabilityResult 结构"""
        results = [
            _make_search_result("chunk-001", 0.92, content="切片一内容"),
            _make_search_result("chunk-002", 0.87, content="切片二内容"),
        ]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM, top_k=10, min_confidence=0.7)
        assert isinstance(result, dict)
        assert result["claim"] == _TEST_CLAIM
        assert "citations" in result
        assert "citation_count" in result
        assert "highest_confidence" in result
        assert "has_bbox_support" in result

    @pytest.mark.asyncio
    async def test_trace_calls_search_top_down(self) -> None:
        """trace() 调用 search_top_down(target_level=L4)"""
        mock = _make_mock_retrieval([_make_search_result("chunk-001", 0.92)])
        service = _make_service(mock)
        await service.trace(claim=_TEST_CLAIM, top_k=10, min_confidence=0.7)
        mock.search_top_down.assert_called_once()
        call_kwargs = mock.search_top_down.call_args.kwargs
        assert call_kwargs["target_level"] == "L4"
        assert call_kwargs["query_text"] == _TEST_CLAIM

    @pytest.mark.asyncio
    async def test_confidence_normalized_from_score(self) -> None:
        """置信度 = score 归一化（0-1）"""
        results = [_make_search_result("chunk-001", 0.92)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        assert result["citations"][0].confidence == 0.92

    @pytest.mark.asyncio
    async def test_citations_sorted_by_confidence_desc(self) -> None:
        """引文按置信度降序排序"""
        results = [
            _make_search_result("low", 0.65),
            _make_search_result("high", 0.95),
            _make_search_result("mid", 0.80),
        ]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM, min_confidence=0.5)
        confidences = [c.confidence for c in result["citations"]]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_min_confidence_filter(self) -> None:
        """过滤置信度 < min_confidence 的切片"""
        results = [_make_search_result("low", 0.60)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM, min_confidence=0.7)
        assert result["citation_count"] == 0
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_highest_confidence(self) -> None:
        """highest_confidence 为最高置信度"""
        results = [_make_search_result("a", 0.8), _make_search_result("b", 0.95)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM, min_confidence=0.5)
        assert result["highest_confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self) -> None:
        """检索结果为空时返回空引文列表（不抛异常）"""
        service = _make_service(_make_mock_retrieval([]))
        result = await service.trace(claim=_TEST_CLAIM)
        assert result["citations"] == []


class TestTraceBoundingBox:
    """Bounding Box 提取测试"""

    @pytest.mark.asyncio
    async def test_bbox_extracted_from_payload(self) -> None:
        """payload 中的 bbox 被提取为 BoundingBox"""
        bbox_data = {"x": 10.0, "y": 20.0, "width": 300.0, "height": 50.0, "page": 2}
        results = [_make_search_result("chunk-001", 0.92, bbox=bbox_data)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        citation = result["citations"][0]
        assert isinstance(citation.bbox, BoundingBox)
        assert citation.bbox.x == 10.0
        assert citation.bbox.y == 20.0
        assert citation.bbox.page == 2

    @pytest.mark.asyncio
    async def test_has_bbox_support_true_when_bbox_present(self) -> None:
        """存在 bbox 时 has_bbox_support=True"""
        bbox_data = {"x": 10.0, "y": 20.0, "width": 300.0, "height": 50.0, "page": 2}
        results = [_make_search_result("chunk-001", 0.92, bbox=bbox_data)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        assert result["has_bbox_support"] is True

    @pytest.mark.asyncio
    async def test_has_bbox_support_false_without_bbox(self) -> None:
        """无 bbox 时 has_bbox_support=False"""
        results = [_make_search_result("chunk-001", 0.92)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        assert result["has_bbox_support"] is False
        assert result["citations"][0].bbox is None

    @pytest.mark.asyncio
    async def test_malformed_bbox_ignored(self) -> None:
        """畸形 bbox 数据被忽略（不抛异常）"""
        results = [_make_search_result("chunk-001", 0.92, bbox={"x": "invalid", "page": "bad"})]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        assert result["citations"][0].bbox is None
        assert result["has_bbox_support"] is False


class TestTraceCitationFields:
    """Citation 字段构造测试"""

    @pytest.mark.asyncio
    async def test_citation_contains_document_id(self) -> None:
        """引文包含 document_id"""
        results = [_make_search_result("chunk-001", 0.92)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        citation = result["citations"][0]
        assert citation.document_id == _TEST_DOCUMENT_ID

    @pytest.mark.asyncio
    async def test_citation_contains_chunk_id_and_text(self) -> None:
        """引文包含 chunk_id 和 text"""
        results = [_make_search_result("chunk-001", 0.92, content="切片内容ABC")]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        citation = result["citations"][0]
        assert citation.chunk_id == "chunk-001"
        assert citation.text == "切片内容ABC"

    @pytest.mark.asyncio
    async def test_citation_id_generation(self) -> None:
        """citation_id 由 document_id + chunk_id 生成"""
        results = [_make_search_result("chunk-001", 0.92)]
        service = _make_service(_make_mock_retrieval(results))
        result = await service.trace(claim=_TEST_CLAIM)
        citation = result["citations"][0]
        assert citation.citation_id.endswith("chunk-001-cit")
        assert ":" in citation.citation_id

    @pytest.mark.asyncio
    async def test_missing_document_id_derives_deterministic_uuid(self) -> None:
        """无合法 document_id 时基于 chunk_id 确定性派生 UUID（同 chunk 稳定归并）"""
        # document_id 为空
        result_without_doc = _make_search_result("chunk-001", 0.92, document_id="")
        service = _make_service(_make_mock_retrieval([result_without_doc]))
        result = await service.trace(claim=_TEST_CLAIM)
        citation = result["citations"][0]
        assert citation.document_id is not None
        derived_id = citation.document_id

        # 再次 trace 相同 chunk → 相同派生 UUID（确定性）
        result2 = await service.trace(claim=_TEST_CLAIM)
        citation2 = result2["citations"][0]
        assert citation2.document_id == derived_id

    @pytest.mark.asyncio
    async def test_invalid_document_id_derives_deterministic_uuid(self) -> None:
        """非法 document_id（非 UUID 字符串）时确定性派生"""
        result_invalid = _make_search_result("chunk-002", 0.8, document_id="not-a-uuid")
        service = _make_service(_make_mock_retrieval([result_invalid]))
        result = await service.trace(claim=_TEST_CLAIM)
        citation = result["citations"][0]
        assert citation.document_id is not None
        # citation_id 纳入 document_id 前缀，且不包含非法字符串
        assert "not-a-uuid" not in citation.citation_id


class TestTraceErrors:
    """异常行为测试"""

    @pytest.mark.asyncio
    async def test_retrieval_failure_wraps_traceability_error(self) -> None:
        """检索失败包装为 TraceabilityError"""
        from src.domain.exceptions.traceability_exceptions import TraceabilityError

        mock = AsyncMock(spec=LayeredRetrievalPort)
        mock.search_top_down.side_effect = Exception("Qdrant 连接超时")
        service = _make_service(mock)
        with pytest.raises(TraceabilityError) as exc_info:
            await service.trace(claim=_TEST_CLAIM)
        assert exc_info.value.context["claim"] == _TEST_CLAIM
        assert "检索" in exc_info.value.message


class TestGetCitationDetail:
    """get_citation_detail 测试"""

    @pytest.mark.asyncio
    async def test_get_citation_detail_returns_cached(self) -> None:
        """从当次缓存返回引文详情"""
        results = [_make_search_result("chunk-001", 0.92)]
        service = _make_service(_make_mock_retrieval(results))
        await service.trace(claim=_TEST_CLAIM)
        # citation_id 现在包含 document_id 前缀
        expected_id = f"{_TEST_DOCUMENT_ID}:chunk-001-cit"
        citation = await service.get_citation_detail(citation_id=expected_id)
        assert citation is not None
        assert citation.chunk_id == "chunk-001"

    @pytest.mark.asyncio
    async def test_get_citation_detail_raises_not_found(self) -> None:
        """未找到引文时抛出 TraceabilityNotFoundError，context 含 citation_id"""
        from src.domain.exceptions.traceability_exceptions import TraceabilityNotFoundError

        service = _make_service(_make_mock_retrieval([]))
        with pytest.raises(TraceabilityNotFoundError) as exc_info:
            await service.get_citation_detail(citation_id="not-exists")
        assert exc_info.value.context["citation_id"] == "not-exists"
        assert "claim" not in exc_info.value.context
        assert "min_confidence" not in exc_info.value.context


class TestGetCitationByDocument:
    """get_citation_by_document 测试"""

    @pytest.mark.asyncio
    async def test_get_citations_by_document_returns_cached(self) -> None:
        """按文档 ID 返回缓存的引文"""
        results = [
            _make_search_result("chunk-001", 0.92),
            _make_search_result("chunk-002", 0.87),
        ]
        service = _make_service(_make_mock_retrieval(results))
        await service.trace(claim=_TEST_CLAIM)
        citations = await service.get_citation_by_document(document_id=_TEST_DOCUMENT_ID)
        assert len(citations) == 2
        assert all(c.document_id == _TEST_DOCUMENT_ID for c in citations)

    @pytest.mark.asyncio
    async def test_get_citations_by_document_raises_not_found(self) -> None:
        """无引文时抛出 TraceabilityNotFoundError，context 含 document_id"""
        from src.domain.exceptions.traceability_exceptions import TraceabilityNotFoundError

        service = _make_service(_make_mock_retrieval([]))
        with pytest.raises(TraceabilityNotFoundError) as exc_info:
            await service.get_citation_by_document(document_id=_TEST_DOCUMENT_ID)
        assert exc_info.value.context["document_id"] == str(_TEST_DOCUMENT_ID)
        assert "claim" not in exc_info.value.context
        assert "min_confidence" not in exc_info.value.context
