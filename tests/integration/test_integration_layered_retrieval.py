"""Story 3.5 分层检索集成测试

验证真实 DenseSemanticSearchService + 真实 LayeredRetrievalService 协作。
L3VectorPort 使用 Mock（Qdrant 为重型基础设施依赖），
EmbeddingService 使用 Mock（外部 API）。

覆盖场景：
- 自底向上（L4→L3 回溯）集成
- 自顶向下（L3→L4 展开）集成
- 降级策略集成
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.services.dense_search_service import DenseSemanticSearchService
from src.application.services.layered_retrieval_service import LayeredRetrievalService
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import L3VectorPort


def _make_child_result(score: float, parent_id: str) -> dict:
    """构造 L4 Child 块检索结果 dict

    Args:
        score: 相似度得分
        parent_id: 父块 ID

    Returns:
        Qdrant SearchResult 原始 dict
    """
    return {
        "id": str(uuid.uuid4()),
        "score": score,
        "payload": {
            "chunk_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "parent_chunk_id": parent_id,
            "index_level": "child",
            "content": f"L4 Child 块内容（分数 {score}）",
        },
    }


class TestLayeredRetrievalIntegration:
    """分层检索集成测试"""

    @pytest.fixture
    def embedding_service(self) -> AsyncMock:
        """Mock EmbeddingServicePort 实例"""
        mock = AsyncMock(spec=EmbeddingServicePort)
        mock.embed_query.return_value = [0.1] * 128
        return mock

    @pytest.fixture
    def l3_vector(self) -> AsyncMock:
        """Mock L3VectorPort 实例"""
        mock = AsyncMock(spec=L3VectorPort)

        async def _get_point(collection: str, point_id: str) -> dict | None:
            return {
                "id": point_id,
                "vector": [0.1] * 128,
                "payload": {
                    "chunk_id": point_id,
                    "document_id": str(uuid.uuid4()),
                    "index_level": "parent",
                    "content": "L3 Parent 块内容",
                },
            }

        mock.get_point.side_effect = _get_point
        return mock

    @pytest.fixture
    def dense_search(self, embedding_service: AsyncMock, l3_vector: AsyncMock) -> DenseSemanticSearchService:
        """真实 DenseSemanticSearchService（注入 mock 端口）"""
        return DenseSemanticSearchService(
            embedding_service=embedding_service,
            vector_storage=l3_vector,
        )

    @pytest.fixture
    def service(
        self,
        dense_search: DenseSemanticSearchService,
        l3_vector: AsyncMock,
    ) -> LayeredRetrievalService:
        """真实 LayeredRetrievalService（注入真实 Dense + mock L3Vector）"""
        return LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=l3_vector,
        )

    # --- 自底向上（L4→L3 回溯）集成 ---

    @pytest.mark.asyncio
    async def test_bottom_up_integration(
        self,
        service: LayeredRetrievalService,
        l3_vector: AsyncMock,
    ) -> None:
        """端到端自底向上：L4 Child 命中 → L3 Parent 回溯"""
        parent_id = str(uuid.uuid4())

        async def _search(
            collection: str,
            query_vector: list[float],
            limit: int = 10,
            filter_payload: dict | None = None,
        ) -> list[dict]:
            return [_make_child_result(0.9, parent_id), _make_child_result(0.8, parent_id)]

        l3_vector.search.side_effect = _search

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="documents",
        )

        assert len(results) == 1
        assert results[0]["id"] == parent_id
        assert results[0]["payload"]["child_count"] == 2
        assert results[0]["payload"]["index_level"] == "parent"
        assert results[0]["score"] == 0.9

        # 验证 get_point 被调用（按 ID 回溯）
        l3_vector.get_point.assert_called()

    @pytest.mark.asyncio
    async def test_bottom_up_no_match_integration(
        self,
        service: LayeredRetrievalService,
        l3_vector: AsyncMock,
    ) -> None:
        """端到端自底向上：无 Child 匹配时返回空列表"""
        l3_vector.search.side_effect = None
        l3_vector.search.return_value = []

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="documents",
        )

        assert results == []

    # --- 自顶向下（L3→L4 展开）集成 ---

    @pytest.mark.asyncio
    async def test_top_down_integration(
        self,
        service: LayeredRetrievalService,
        l3_vector: AsyncMock,
    ) -> None:
        """端到端自顶向下：L3 Parent 命中 → L4 Child 展开"""
        parent_id = str(uuid.uuid4())

        call_count = 0

        async def _search(
            collection: str,
            query_vector: list[float],
            limit: int = 10,
            filter_payload: dict | None = None,
        ) -> list[dict]:
            nonlocal call_count
            call_count += 1
            if filt := (filter_payload or {}):
                if filt.get("index_level") == "child":
                    return [_make_child_result(0.7, parent_id) for _ in range(4)]
            return [
                {
                    "id": parent_id,
                    "score": 0.8,
                    "payload": {
                        "chunk_id": parent_id,
                        "document_id": str(uuid.uuid4()),
                        "index_level": "parent",
                        "content": "L3 Parent 块内容",
                    },
                }
            ]

        l3_vector.search.side_effect = _search

        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L4",
            collection="documents",
        )

        # Top-3 展开
        assert len(results) == 3
        assert all(r["payload"]["index_level"] == "child" for r in results)
        assert all(r["payload"]["parent_chunk_id"] == parent_id for r in results)
        assert all("parent_content" in r["payload"] for r in results)
        # 1 次 L3 检索 + 1 次 Child 展开
        assert call_count == 2

    # --- 降级策略集成 ---

    @pytest.mark.asyncio
    async def test_degrade_to_l3_integration(
        self,
        l3_vector: AsyncMock,
        embedding_service: AsyncMock,
    ) -> None:
        """L4 检索失败 → 降级为 L3 检索"""
        parent_id = str(uuid.uuid4())

        async def _search(
            collection: str,
            query_vector: list[float],
            limit: int = 10,
            filter_payload: dict | None = None,
        ) -> list[dict]:
            filt = filter_payload or {}
            if filt.get("index_level") == "child":
                raise RuntimeError("L4 检索失败")
            return [
                {
                    "id": parent_id,
                    "score": 0.8,
                    "payload": {
                        "chunk_id": parent_id,
                        "document_id": str(uuid.uuid4()),
                        "index_level": "parent",
                        "content": "L3 Parent 块内容",
                    },
                }
            ]

        l3_vector.search.side_effect = _search

        dense_search = DenseSemanticSearchService(
            embedding_service=embedding_service,
            vector_storage=l3_vector,
        )
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=l3_vector,
        )

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="documents",
        )

        # 降级后返回 L3 结果（不含 child_count）
        assert len(results) == 1
        assert results[0]["payload"]["index_level"] == "parent"

    # --- 输入验证集成 ---

    @pytest.mark.asyncio
    async def test_input_validation_integration(
        self,
        service: LayeredRetrievalService,
    ) -> None:
        """集成场景下的输入验证"""
        from src.domain.exceptions import ValidationError

        with pytest.raises(ValidationError):
            await service.search_top_down(
                query_text="",
                target_level="L4",
                collection="documents",
            )

    # --- 返回类型验证 ---

    @pytest.mark.asyncio
    async def test_return_type_is_search_result(
        self,
        service: LayeredRetrievalService,
        l3_vector: AsyncMock,
    ) -> None:
        """双向遍历均返回 list[SearchResult]"""
        parent_id = str(uuid.uuid4())
        l3_vector.search.side_effect = None
        l3_vector.search.return_value = [_make_child_result(0.9, parent_id)]

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="documents",
        )

        assert isinstance(results, list)
        from src.domain.ports.l3_vector import SearchResult as SearchResultType

        # TypedDict 不支持 isinstance，改为结构验证
        for r in results:
            assert "id" in r and "score" in r and "payload" in r
        assert sorted(SearchResultType.__annotations__.keys()) == ["id", "payload", "score"]
