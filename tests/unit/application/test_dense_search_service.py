"""DenseSemanticSearchService 单元测试

验证 Dense 语义检索服务的 embed→search 编排逻辑和 tenant_id 注入
使用 mock 隔离 EmbeddingServicePort 和 L3VectorPort
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.dense_search_service import DenseSemanticSearchService


def _make_search_service(
    embedding_result: list[float] | None = None,
    search_result: list[dict[str, Any]] | None = None,
) -> DenseSemanticSearchService:
    """构造测试用 DenseSemanticSearchService"""
    embedding_svc = MagicMock()
    embedding_svc.encode_text.return_value = embedding_result or [0.1] * 1024

    vector_storage = AsyncMock()
    vector_storage.search.return_value = search_result or []

    return DenseSemanticSearchService(embedding_svc, vector_storage)  # type: ignore[arg-type]


class TestDenseSearchServiceBasic:
    """DenseSemanticSearchService 基本检索"""

    @pytest.mark.asyncio
    async def test_search_calls_encode_text(self) -> None:
        """search() 应调用 embedding_service.encode_text 一次"""
        service = _make_search_service()
        await service.search("test_collection", "查询文本", limit=5)
        service._embedding.encode_text.assert_called_once_with("查询文本")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_search_calls_vector_search(self) -> None:
        """search() 应调用 vector_storage.search 一次并传入正确向量"""
        expected_vector = [0.2] * 1024
        service = _make_search_service(embedding_result=expected_vector)
        await service.search("test_collection", "查询文本", limit=5)
        service._vector.search.assert_called_once()  # type: ignore[attr-defined]
        call_args = service._vector.search.call_args  # type: ignore[attr-defined]
        assert call_args[1]["collection"] == "test_collection"
        assert call_args[1]["query_vector"] == expected_vector
        assert call_args[1]["limit"] == 5

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        """search() 应返回检索结果"""
        results = [
            {"id": "doc1", "score": 0.95, "payload": {"text": "doc1"}},
            {"id": "doc2", "score": 0.85, "payload": {"text": "doc2"}},
        ]
        service = _make_search_service(search_result=results)
        actual = await service.search("test_collection", "查询文本")
        assert len(actual) == 2
        assert actual[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_empty_result(self) -> None:
        """无匹配结果返回空列表"""
        service = _make_search_service(search_result=[])
        actual = await service.search("test_collection", "查询文本")
        assert actual == []


class TestDenseSearchServiceTenantFilter:
    """tenant_id 自动注入到 filter_payload"""

    @pytest.mark.asyncio
    async def test_tenant_id_injected_into_filter(self) -> None:
        """tenant_id 应注入到 filter_payload"""
        service = _make_search_service()
        await service.search("test_collection", "查询文本", tenant_id="tenant-123")
        call_args = service._vector.search.call_args  # type: ignore[attr-defined]
        filter_payload = call_args[1]["filter_payload"]
        assert filter_payload["tenant_id"] == "tenant-123"

    @pytest.mark.asyncio
    async def test_existing_filter_preserved(self) -> None:
        """现有 filter_payload 应保留"""
        service = _make_search_service()
        await service.search(
            "test_collection",
            "查询文本",
            tenant_id="tenant-123",
            filter_payload={"business_domain": "finance"},
        )
        call_args = service._vector.search.call_args  # type: ignore[attr-defined]
        filter_payload = call_args[1]["filter_payload"]
        assert filter_payload["tenant_id"] == "tenant-123"
        assert filter_payload["business_domain"] == "finance"

    @pytest.mark.asyncio
    async def test_no_tenant_id_no_filter(self) -> None:
        """无 tenant_id 且无 filter_payload 时 filter_payload 为 None"""
        service = _make_search_service()
        await service.search("test_collection", "查询文本")
        call_args = service._vector.search.call_args  # type: ignore[attr-defined]
        assert call_args[1]["filter_payload"] is None

    @pytest.mark.asyncio
    async def test_filter_payload_only(self) -> None:
        """仅有 filter_payload 无 tenant_id 时保留原始 filter"""
        service = _make_search_service()
        await service.search(
            "test_collection",
            "查询文本",
            filter_payload={"business_domain": "finance"},
        )
        call_args = service._vector.search.call_args  # type: ignore[attr-defined]
        filter_payload = call_args[1]["filter_payload"]
        assert filter_payload == {"business_domain": "finance"}
        assert "tenant_id" not in filter_payload

    @pytest.mark.asyncio
    async def test_limit_passed_correctly(self) -> None:
        """limit 应正确传递"""
        service = _make_search_service()
        await service.search("test_collection", "查询文本", limit=3)
        call_args = service._vector.search.call_args  # type: ignore[attr-defined]
        assert call_args[1]["limit"] == 3
