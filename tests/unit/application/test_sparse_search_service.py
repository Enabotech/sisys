"""Bm25SparseSearchService 单元测试

验证 BM25 稀疏检索服务的 embed_sparse→search_sparse 编排逻辑和 tenant_id 注入。
严格镜像 DenseSemanticSearchService 的架构模式：
- MagicMock(spec=EmbeddingServicePort) mock 嵌入服务
- AsyncMock(spec=L3VectorPort) mock 向量存储
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.sparse_search_service import Bm25SparseSearchService
from src.domain.exceptions import ValidationError
from src.domain.ports.embedding_service import EmbeddingServicePort, SparseEmbedding
from src.domain.ports.l3_vector import L3VectorPort


def _make_sparse_service(
    sparse_embedding: SparseEmbedding | None = None,
    search_result: list[dict[str, Any]] | None = None,
) -> tuple[Bm25SparseSearchService, MagicMock, AsyncMock]:
    """构造测试用 Bm25SparseSearchService 及其 mock 依赖

    使用 spec=Protocol 约束 mock 行为契约，仅暴露端口声明的方法
    防止 mock 因属性拼写错误"假绿"通过
    """
    embedding_svc = MagicMock(spec=EmbeddingServicePort)
    default_embedding: SparseEmbedding = {"indices": [0, 5, 10], "values": [1.0, 0.5, 0.8]}
    embedding_svc.embed_sparse.return_value = [sparse_embedding or default_embedding]

    vector_storage = AsyncMock(spec=L3VectorPort)
    vector_storage.search_sparse.return_value = search_result or []

    service = Bm25SparseSearchService(embedding_svc, vector_storage)
    return service, embedding_svc, vector_storage


class TestBm25SparseSearchServiceBasic:
    """Bm25SparseSearchService 基本检索"""

    @pytest.mark.asyncio
    async def test_search_calls_embed_sparse(self) -> None:
        """search() 应调用 embedding_service.embed_sparse([query_text]) 一次"""
        service, embedding_svc, _ = _make_sparse_service()
        await service.search("test_collection", "查询文本", limit=5)
        embedding_svc.embed_sparse.assert_called_once_with(["查询文本"])

    @pytest.mark.asyncio
    async def test_search_calls_vector_search_sparse(self) -> None:
        """search() 应调用 vector_storage.search_sparse 一次"""
        service, _, vector_storage = _make_sparse_service()
        await service.search("test_collection", "查询文本", limit=5)
        vector_storage.search_sparse.assert_called_once()
        call_args = vector_storage.search_sparse.call_args
        assert call_args[1]["collection"] == "test_collection"
        assert call_args[1]["limit"] == 5
        # 验证稀疏向量正确传递
        sparse_arg = call_args[1]["sparse_vector"]
        assert "indices" in sparse_arg
        assert "values" in sparse_arg

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        """search() 应返回 SearchResult 格式的检索结果"""
        results = [
            {"id": "doc1", "score": 0.95, "payload": {"text": "doc1"}},
            {"id": "doc2", "score": 0.85, "payload": {"text": "doc2"}},
        ]
        service, _, _ = _make_sparse_service(search_result=results)
        actual = await service.search("test_collection", "查询文本")
        assert len(actual) == 2
        assert actual[0]["score"] == 0.95
        assert actual[0]["id"] == "doc1"

    @pytest.mark.asyncio
    async def test_search_empty_result(self) -> None:
        """无匹配结果返回空列表"""
        service, _, _ = _make_sparse_service(search_result=[])
        actual = await service.search("test_collection", "查询文本")
        assert actual == []


class TestBm25SparseSearchServiceValidation:
    """输入验证（与 DenseSemanticSearchService 一致）"""

    @pytest.mark.asyncio
    async def test_search_raises_on_empty_query(self) -> None:
        """空查询文本应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="查询文本不能为空"):
            await service.search("test_collection", "")

    @pytest.mark.asyncio
    async def test_search_raises_on_whitespace_query(self) -> None:
        """纯空白查询文本应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="查询文本不能为空"):
            await service.search("test_collection", "   ")

    @pytest.mark.asyncio
    async def test_search_raises_on_empty_collection(self) -> None:
        """空 collection 名称应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="Collection 名称不能为空"):
            await service.search("", "查询文本")

    @pytest.mark.asyncio
    async def test_search_raises_on_whitespace_collection(self) -> None:
        """纯空白 collection 名称应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="Collection 名称不能为空"):
            await service.search("   ", "查询文本")

    @pytest.mark.asyncio
    async def test_search_raises_on_zero_limit(self) -> None:
        """limit=0 应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="limit 必须为正整数"):
            await service.search("test_collection", "查询文本", limit=0)

    @pytest.mark.asyncio
    async def test_search_raises_on_negative_limit(self) -> None:
        """负数 limit 应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="limit 必须为正整数"):
            await service.search("test_collection", "查询文本", limit=-1)

    @pytest.mark.asyncio
    async def test_search_raises_on_empty_tenant_id(self) -> None:
        """空字符串 tenant_id 应抛出 ValidationError"""
        service, _, _ = _make_sparse_service()
        with pytest.raises(ValidationError, match="tenant_id 不能为空"):
            await service.search("test_collection", "查询文本", tenant_id="")


class TestBm25SparseSearchServiceTenantFilter:
    """tenant_id 自动注入到 filter_payload"""

    @pytest.mark.asyncio
    async def test_tenant_id_injected_into_filter(self) -> None:
        """tenant_id 应注入到 filter_payload"""
        service, _, vector_storage = _make_sparse_service()
        await service.search("test_collection", "查询文本", tenant_id="tenant-123")
        call_args = vector_storage.search_sparse.call_args
        filter_payload = call_args[1]["filter_payload"]
        assert filter_payload["tenant_id"] == "tenant-123"

    @pytest.mark.asyncio
    async def test_existing_filter_preserved(self) -> None:
        """现有 filter_payload 应保留"""
        service, _, vector_storage = _make_sparse_service()
        await service.search(
            "test_collection",
            "查询文本",
            tenant_id="tenant-123",
            filter_payload={"business_domain": "finance"},
        )
        call_args = vector_storage.search_sparse.call_args
        filter_payload = call_args[1]["filter_payload"]
        assert filter_payload["tenant_id"] == "tenant-123"
        assert filter_payload["business_domain"] == "finance"

    @pytest.mark.asyncio
    async def test_no_tenant_id_no_filter(self) -> None:
        """无 tenant_id 且无 filter_payload 时 filter_payload 为 None"""
        service, _, vector_storage = _make_sparse_service()
        await service.search("test_collection", "查询文本")
        call_args = vector_storage.search_sparse.call_args
        assert call_args[1]["filter_payload"] is None

    @pytest.mark.asyncio
    async def test_filter_payload_only(self) -> None:
        """仅有 filter_payload 无 tenant_id 时保留原始 filter"""
        service, _, vector_storage = _make_sparse_service()
        await service.search(
            "test_collection",
            "查询文本",
            filter_payload={"business_domain": "finance"},
        )
        call_args = vector_storage.search_sparse.call_args
        filter_payload = call_args[1]["filter_payload"]
        assert filter_payload == {"business_domain": "finance"}


class TestBm25SparseSearchServiceEmbedSparse:
    """embed_sparse 批量接口调用模式验证"""

    @pytest.mark.asyncio
    async def test_embed_sparse_called_with_list(self) -> None:
        """embed_sparse 应接收 [query_text] 列表（批量接口取首元素）"""
        service, embedding_svc, _ = _make_sparse_service()
        await service.search("test_collection", "单查询文本")
        call_arg = embedding_svc.embed_sparse.call_args[0][0]
        assert call_arg == ["单查询文本"]
        assert len(call_arg) == 1

    @pytest.mark.asyncio
    async def test_embed_sparse_failure_propagates(self) -> None:
        """embed_sparse 异常应向上传播（应用层不捕获）"""
        service, embedding_svc, _ = _make_sparse_service()
        embedding_svc.embed_sparse.side_effect = RuntimeError("API 不可达")
        with pytest.raises(RuntimeError, match="API 不可达"):
            await service.search("test_collection", "查询文本")


class TestBm25SparseSearchServiceSignature:
    """方法签名与 DenseSemanticSearchService 一致性验证"""

    @pytest.mark.asyncio
    async def test_search_parameter_order_matches_dense(self) -> None:
        """参数顺序 (collection, query_text, limit, tenant_id, filter_payload) 与 Dense 一致"""
        service, _, vector_storage = _make_sparse_service()
        await service.search(
            "my_collection",
            "my query",
            limit=20,
            tenant_id="tenant-abc",
            filter_payload={"domain": "finance"},
        )
        call_args = vector_storage.search_sparse.call_args
        assert call_args[1]["collection"] == "my_collection"
        assert call_args[1]["limit"] == 20
        assert call_args[1]["filter_payload"]["tenant_id"] == "tenant-abc"
        assert call_args[1]["filter_payload"]["domain"] == "finance"

    @pytest.mark.asyncio
    async def test_default_limit_is_10(self) -> None:
        """默认 limit=10 与 Dense 服务一致"""
        service, _, vector_storage = _make_sparse_service()
        await service.search("test_collection", "查询文本")
        call_args = vector_storage.search_sparse.call_args
        assert call_args[1]["limit"] == 10
