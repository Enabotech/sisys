"""Story 3.5 分层检索应用服务单元测试

验证 LayeredRetrievalService 的自底向上（L4→L3）、自顶向下（L3→L4）、
输入验证、降级策略和 L2/L1 骨架实现。
遵循 TDD 循环：Mock 端口验证服务逻辑。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.services.layered_retrieval_service import LayeredRetrievalService
from src.domain.exceptions import ValidationError
from src.domain.exceptions.layered_retrieval_exceptions import (
    LayeredRetrievalError,
    LevelTransitionError,
)
from src.domain.exceptions.system_exceptions import StorageError
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import L3VectorPort, SearchResult


def _make_dense_search(
    search_results: list[SearchResult] | None = None,
    search_side_effect: Exception | None = None,
) -> AsyncMock:
    """构造 Dense 检索服务 mock

    Args:
        search_results: search() 返回的结果列表
        search_side_effect: search() 抛出的异常

    Returns:
        带 search() 方法的 mock 服务
    """
    mock = AsyncMock()
    if search_side_effect is not None:
        mock.search.side_effect = search_side_effect
    else:
        mock.search.return_value = search_results or []
    return mock


def _make_l3_vector(
    points: dict[str, dict] | None = None,
    search_results: list[dict] | None = None,
) -> AsyncMock:
    """构造 L3VectorPort mock

    Args:
        points: get_point() 返回的点 dict
        search_results: search() 返回的结果列表

    Returns:
        带 get_point() 和 search() 方法的 mock
    """
    mock = AsyncMock(spec=L3VectorPort)

    async def _get_point(collection: str, point_id: str) -> dict | None:
        if points and point_id in points:
            return points[point_id]
        return None

    mock.get_point.side_effect = _get_point
    if search_results is not None:
        mock.search.return_value = search_results
    else:
        mock.search.return_value = []
    return mock


def _make_embedding_service() -> AsyncMock:
    """构造 EmbeddingServicePort mock

    Returns:
        带 embed_query() 方法的 mock 端口
    """
    mock = AsyncMock(spec=EmbeddingServicePort)
    mock.embed_query.return_value = [0.1] * 128
    return mock


def _make_child_result(
    score: float,
    parent_id: str,
    child_id: str | None = None,
) -> SearchResult:
    """构造 L4 Child 块检索结果

    Args:
        score: 相似度得分
        parent_id: 父块 ID
        child_id: 子块 ID（默认随机）

    Returns:
        SearchResult TypedDict
    """
    return SearchResult(
        id=child_id or str(uuid.uuid4()),
        score=score,
        payload={
            "chunk_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "parent_chunk_id": parent_id,
            "index_level": "child",
            "content": f"L4 Child 块内容（分数 {score}）",
        },
    )


def _make_parent_result(
    parent_id: str,
    score: float = 0.8,
) -> SearchResult:
    """构造 L3 Parent 块检索结果

    Args:
        parent_id: 父块 ID
        score: 相似度得分

    Returns:
        SearchResult TypedDict
    """
    return SearchResult(
        id=parent_id,
        score=score,
        payload={
            "chunk_id": parent_id,
            "document_id": str(uuid.uuid4()),
            "index_level": "parent",
            "content": f"L3 Parent 块内容（分数 {score}）",
        },
    )


@pytest.fixture
def service() -> LayeredRetrievalService:
    """构建 LayeredRetrievalService 实例（空依赖）"""
    return LayeredRetrievalService(
        dense_search=_make_dense_search(),
        l3_vector=_make_l3_vector(),
        embedding_service=_make_embedding_service(),
    )


# ===================================================================
# AC-2: L4→L3 自底向上遍历
# ===================================================================


class TestBottomUpL4ToL3:
    """自底向上（L4→L3）遍历测试"""

    async def test_bottom_up_l4_to_l3_basic(self) -> None:
        """基本 L4→L3 回溯"""
        parent_id = str(uuid.uuid4())
        dense_search = _make_dense_search(
            search_results=[
                _make_child_result(0.85, parent_id),
                _make_child_result(0.72, parent_id),
            ]
        )
        l3_vector = _make_l3_vector(
            points={
                parent_id: {
                    "id": parent_id,
                    "payload": {
                        "index_level": "parent",
                        "content": "L3 Parent 块内容",
                        "document_id": str(uuid.uuid4()),
                    },
                }
            }
        )
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="test_collection",
        )

        # 同一 Parent 的多个 Child 命中合并为一条结果
        assert len(results) == 1
        assert results[0]["id"] == parent_id
        assert results[0]["payload"]["parent_chunk_id"] == parent_id
        assert results[0]["payload"]["child_count"] == 2
        assert results[0]["payload"]["index_level"] == "parent"
        # 按最高 Child 分数
        assert results[0]["score"] == 0.85

    async def test_bottom_up_dedup_multiple_children(self) -> None:
        """同一 Parent 的多个 Child 命中合并为一条结果"""
        parent_id = str(uuid.uuid4())
        dense_search = _make_dense_search(search_results=[_make_child_result(0.9, parent_id) for _ in range(3)])
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=_make_l3_vector(
                points={parent_id: {"id": parent_id, "payload": {"content": "父块内容", "index_level": "parent"}}}
            ),
            embedding_service=_make_embedding_service(),
        )
        """合并后结果按最高 Child 分数降序排列"""
        parent1 = str(uuid.uuid4())
        parent2 = str(uuid.uuid4())
        dense_search = _make_dense_search(
            search_results=[
                _make_child_result(0.5, parent1),
                _make_child_result(0.95, parent2),
            ]
        )
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=_make_l3_vector(
                points={
                    parent1: {"id": parent1, "payload": {"content": "父块1", "index_level": "parent"}},
                    parent2: {"id": parent2, "payload": {"content": "父块2", "index_level": "parent"}},
                }
            ),
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="test_collection",
        )

        assert len(results) == 2
        assert results[0]["id"] == parent2
        assert results[0]["score"] == 0.95
        assert results[1]["id"] == parent1

    async def test_bottom_up_no_match_returns_empty(self) -> None:
        """无 Child 匹配时返回空列表"""
        service = LayeredRetrievalService(
            dense_search=_make_dense_search(search_results=[]),
            l3_vector=_make_l3_vector(),
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="test_collection",
        )

        assert results == []


# ===================================================================
# AC-3: L3→L4 自顶向下展开
# ===================================================================


class TestTopDownL3ToL4:
    """自顶向下（L3→L4）展开测试"""

    async def _make_top_down_scenario(
        self,
        parent_id: str,
        score: float = 0.8,
        child_count: int = 2,
        child_score: float = 0.7,
    ) -> LayeredRetrievalService:
        """构造自顶向下展开测试场景

        Args:
            parent_id: 父块 ID
            score: 父块分数
            child_count: 子块数
            child_score: 子块分数

        Returns:
            配置好的 LayeredRetrievalService
        """
        dense_search = _make_dense_search()
        l3_vector = _make_l3_vector(
            search_results=[
                {
                    "id": parent_id,
                    "score": score,
                    "payload": {
                        "chunk_id": parent_id,
                        "document_id": str(uuid.uuid4()),
                        "index_level": "parent",
                        "content": f"L3 Parent 块内容（分数 {score}）",
                    },
                }
            ]
        )

        def _child_search(
            collection: str,
            query_vector: list[float],
            limit: int = 10,
            filter_payload: dict | None = None,
        ) -> list[dict]:
            if filter_payload and filter_payload.get("index_level") == "child":
                return [_make_child_result_raw(child_score, parent_id) for _ in range(child_count)]
            return [
                {
                    "id": parent_id,
                    "score": score,
                    "payload": {
                        "chunk_id": parent_id,
                        "document_id": str(uuid.uuid4()),
                        "index_level": "parent",
                        "content": f"L3 Parent 块内容（分数 {score}）",
                    },
                }
            ]

        l3_vector.search.side_effect = _child_search
        return LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )

    async def test_top_down_l3_to_l4_basic(self) -> None:
        """基本 L3→L4 展开"""
        parent_id = str(uuid.uuid4())
        service = await self._make_top_down_scenario(parent_id, child_count=2)

        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L4",
            collection="test_collection",
        )

        assert len(results) == 2
        assert results[0]["payload"]["index_level"] == "child"
        assert results[0]["payload"]["parent_chunk_id"] == parent_id
        assert "parent_content" in results[0]["payload"]

    async def test_top_down_expands_top3_children(self) -> None:
        """每个命中 Parent 展开 Top-3 Child 子块"""
        parent_id = str(uuid.uuid4())
        service = await self._make_top_down_scenario(parent_id, child_count=6)

        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L4",
            collection="test_collection",
        )

        # Top-3 展开，即使 Child 有 6 个
        assert len(results) == 3

    async def test_top_down_combined_score_sort(self) -> None:
        """结果按 Parent 分数 × Child 分数降序排列"""
        parent_id = str(uuid.uuid4())
        dense_search = _make_dense_search()
        l3_vector = _make_l3_vector(
            search_results=[
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
        )

        def _search(
            collection: str,
            query_vector: list[float],
            limit: int = 10,
            filter_payload: dict | None = None,
        ) -> list[dict]:
            if filter_payload and filter_payload.get("index_level") == "child":
                return [
                    _make_child_result_raw(0.9, parent_id),
                    _make_child_result_raw(0.6, parent_id),
                ]
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
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L4",
            collection="test_collection",
        )

        # 0.8*0.9=0.72 > 0.8*0.6=0.48
        assert results[0]["score"] == pytest.approx(0.72)
        assert results[1]["score"] == pytest.approx(0.48)

    async def test_top_down_parent_content_preview(self) -> None:
        """结果 payload 包含 parent_content 截断摘要（前 200 字符）"""
        parent_id = str(uuid.uuid4())
        dense_search = _make_dense_search()
        l3_vector = _make_l3_vector(
            search_results=[
                {
                    "id": parent_id,
                    "score": 0.8,
                    "payload": {
                        "chunk_id": parent_id,
                        "document_id": str(uuid.uuid4()),
                        "index_level": "parent",
                        "content": "长" * 300,
                    },
                }
            ]
        )

        l3_vector.search.return_value = [
            {
                "id": parent_id,
                "score": 0.8,
                "payload": {
                    "chunk_id": parent_id,
                    "document_id": str(uuid.uuid4()),
                    "index_level": "parent",
                    "content": "长" * 300,
                },
            }
        ]
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L4",
            collection="test_collection",
        )

        assert len(results[0]["payload"]["parent_content"]) <= 200

    async def test_top_down_no_match_returns_empty(self) -> None:
        """L3 无匹配时自顶向下返回空列表"""
        l3_vector = _make_l3_vector(search_results=[])
        service = LayeredRetrievalService(
            dense_search=_make_dense_search(),
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L4",
            collection="test_collection",
        )

        assert results == []


def _make_child_result_raw(score: float, parent_id: str, child_id: str | None = None) -> dict:
    """构造 L4 Child 块原始检索结果 dict

    Args:
        score: 相似度得分
        parent_id: 父块 ID
        child_id: 子块 ID（默认随机）

    Returns:
        Qdrant 格式的检索结果 dict
    """
    return {
        "id": child_id or str(uuid.uuid4()),
        "score": score,
        "payload": {
            "chunk_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "parent_chunk_id": parent_id,
            "index_level": "child",
            "content": f"L4 Child 块内容（分数 {score}）",
        },
    }


# ===================================================================
# AC-4: 分层检索编排服务（输入验证 + 降级策略）
# ===================================================================


class TestLayeredRetrievalService:
    """分层检索编排服务测试"""

    async def test_search_input_validation_empty_query(self, service: LayeredRetrievalService) -> None:
        """空查询文本抛出 ValidationError"""
        with pytest.raises(ValidationError):
            await service.search_bottom_up(
                query_text="",
                target_level="L3",
                collection="test_collection",
            )

    async def test_search_input_validation_empty_collection(self, service: LayeredRetrievalService) -> None:
        """空 collection 抛出 ValidationError"""
        with pytest.raises(ValidationError):
            await service.search_bottom_up(
                query_text="测试查询",
                target_level="L3",
                collection="",
            )

    async def test_search_input_validation_invalid_limit(self, service: LayeredRetrievalService) -> None:
        """无效 limit 抛出 ValidationError"""
        with pytest.raises(ValidationError):
            await service.search_bottom_up(
                query_text="测试查询",
                target_level="L3",
                collection="test_collection",
                limit=0,
            )

    async def test_search_input_validation_oversized_limit(self, service: LayeredRetrievalService) -> None:
        """超上限 limit 抛出 ValidationError"""
        with pytest.raises(ValidationError):
            await service.search_bottom_up(
                query_text="测试查询",
                target_level="L3",
                collection="test_collection",
                limit=10_000,
            )

    async def test_search_input_validation_blank_tenant_id(self, service: LayeredRetrievalService) -> None:
        """空白 tenant_id 抛出 ValidationError"""
        with pytest.raises(ValidationError, match="tenant_id"):
            await service.search_bottom_up(
                query_text="测试查询",
                target_level="L3",
                collection="test_collection",
                tenant_id="   ",
            )

    async def test_bottom_up_input_validation_also_applies_top_down(self, service: LayeredRetrievalService) -> None:
        """search_top_down 也执行输入验证"""
        with pytest.raises(ValidationError):
            await service.search_top_down(
                query_text="",
                target_level="L4",
                collection="test_collection",
            )

    async def test_invalid_target_level_raises_level_transition_error(self, service: LayeredRetrievalService) -> None:
        """非法层级抛出 LevelTransitionError"""
        with pytest.raises(LevelTransitionError):
            await service.search_bottom_up(
                query_text="测试查询",
                target_level="L5",
                collection="test_collection",
            )

    async def test_degrade_strategy_l4_failure_to_l3(self) -> None:
        """L4 检索失败 → 降级为 L3 检索"""

        # L4 层检索（index_level=child）失败
        async def _search(
            collection: str,
            query_text: str,
            limit: int = 10,
            tenant_id: str | None = None,
            filter_payload: dict | None = None,
        ):
            if filter_payload and filter_payload.get("index_level") == "child":
                raise RuntimeError("L4 检索失败")
            return [_make_parent_result(str(uuid.uuid4()), score=0.8)]

        dense_search = AsyncMock()
        dense_search.search.side_effect = _search
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=_make_l3_vector(),
            embedding_service=_make_embedding_service(),
        )

        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L3",
            collection="test_collection",
        )

        # 降级后返回 L3 结果
        assert len(results) == 1
        assert results[0]["payload"]["index_level"] == "parent"

    async def test_degrade_system_exception_propagates(self) -> None:
        """SystemException 不降级，直接传播"""

        async def _search(
            collection: str,
            query_text: str,
            limit: int = 10,
            tenant_id: str | None = None,
            filter_payload: dict | None = None,
        ):
            raise StorageError("Qdrant 不可用")

        dense_search = _make_dense_search()
        dense_search.search.side_effect = _search
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=_make_l3_vector(),
            embedding_service=_make_embedding_service(),
        )
        from src.domain.exceptions.system_exceptions import SystemException

        with pytest.raises(SystemException):
            await service.search_bottom_up(
                query_text="测试查询",
                target_level="L3",
                collection="test_collection",
            )

    async def test_l3_direct_search_failure_raises_layered_retrieval_error(self) -> None:
        """L3 直接检索失败抛出 LayeredRetrievalError"""
        dense_search = _make_dense_search(search_side_effect=RuntimeError("Dense 不可用"))
        service = LayeredRetrievalService(
            dense_search=dense_search,
            l3_vector=_make_l3_vector(),
            embedding_service=_make_embedding_service(),
        )
        with pytest.raises(LayeredRetrievalError):
            await service.search_top_down(query_text="测试查询", target_level="L3", collection="test_collection")

    async def test_merge_filter_with_tenant_none(self) -> None:
        """tenant_id=None 时不注入 tenant_id"""
        result = LayeredRetrievalService._merge_filter_with_tenant({"index_level": "parent"}, None, None)
        assert result == {"index_level": "parent"}
        assert "tenant_id" not in result

    async def test_merge_filter_with_tenant_valid(self) -> None:
        """tenant_id 有效时注入到 filter"""
        result = LayeredRetrievalService._merge_filter_with_tenant(
            {"index_level": "parent"}, {"doc_type": "report"}, "tenant_abc"
        )
        assert result == {"index_level": "parent", "doc_type": "report", "tenant_id": "tenant_abc"}

    async def test_fetch_parent_get_point_returns_none(self) -> None:
        """get_point 返回 None 时 _fetch_parent 返回 None"""
        l3_vector = _make_l3_vector(points={})
        service = LayeredRetrievalService(
            dense_search=_make_dense_search(),
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )
        result = await service._fetch_parent(
            collection="test",
            parent_id="nonexistent",
            info={"max_child_score": 0.8, "child_count": 1, "parent_chunk_id": "id"},
        )
        assert result is None

    async def test_fetch_parent_get_point_raises_exception(self) -> None:
        """get_point 抛异常时 _fetch_parent 返回 None"""
        l3_vector = AsyncMock(spec=L3VectorPort)
        l3_vector.get_point.side_effect = RuntimeError("Qdrant 不可用")
        service = LayeredRetrievalService(
            dense_search=_make_dense_search(),
            l3_vector=l3_vector,
            embedding_service=_make_embedding_service(),
        )
        result = await service._fetch_parent(
            collection="test",
            parent_id="id",
            info={"max_child_score": 0.8, "child_count": 1, "parent_chunk_id": "id"},
        )
        assert result is None


# ===================================================================
# AC-6/AC-7: L2/L1 骨架实现
# ===================================================================


class TestL2L1Skeleton:
    """L2/L1 骨架实现测试"""

    async def test_search_top_down_l2_returns_empty(self, service: LayeredRetrievalService) -> None:
        """L2 文档摘要检索返回空列表"""
        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L2",
            collection="test_collection",
        )
        assert results == []

    async def test_search_top_down_l1_returns_empty(self, service: LayeredRetrievalService) -> None:
        """L1 跨文档摘要检索返回空列表"""
        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L1",
            collection="test_collection",
        )
        assert results == []

    async def test_search_bottom_up_l2_returns_empty(self, service: LayeredRetrievalService) -> None:
        """search_bottom_up L2 也返回空列表"""
        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L2",
            collection="test_collection",
        )
        assert results == []

    async def test_search_bottom_up_l1_returns_empty(self, service: LayeredRetrievalService) -> None:
        """search_bottom_up L1 也返回空列表"""
        results = await service.search_bottom_up(
            query_text="测试查询",
            target_level="L1",
            collection="test_collection",
        )
        assert results == []

    async def test_returns_search_result_type(self, service: LayeredRetrievalService) -> None:
        """返回结果是 SearchResult TypedDict 结构"""
        results = await service.search_top_down(
            query_text="测试查询",
            target_level="L2",
            collection="test_collection",
        )
        assert isinstance(results, list)
        # SearchResult 字段类型验证
        from src.domain.ports.l3_vector import SearchResult as SearchResultType

        assert sorted(SearchResultType.__annotations__.keys()) == ["id", "payload", "score"]
