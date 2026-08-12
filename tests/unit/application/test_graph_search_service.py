"""GraphSearchService 单元测试

验证 Graph 检索服务：L5GraphPort 注入、search_entities→find_related 检索流程、
SearchResult 转换、分数映射、异常透明降级。
使用 AsyncMock(spec=L5GraphPort) 隔离 Neo4j。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.services.graph_search_service import GraphSearchService
from src.domain.ports.l5_graph import L5GraphPort


def _make_graph_port(
    entities: list[dict] | None = None,
    related: dict[str, list[dict]] | None = None,
    side_effect_search: Exception | None = None,
    side_effect_related: Exception | None = None,
) -> AsyncMock:
    """构造 mock L5GraphPort"""
    port = AsyncMock(spec=L5GraphPort)
    if side_effect_search:
        port.search_entities.side_effect = side_effect_search
    else:
        port.search_entities.return_value = entities or []
    if side_effect_related:
        port.find_related.side_effect = side_effect_related
    else:
        related = related or {}

        async def _find_related(memory_id: str, max_depth: int = 2) -> list[dict]:
            return related.get(memory_id, [])

        port.find_related.side_effect = _find_related
    return port


def _make_service(port: AsyncMock) -> GraphSearchService:
    """构造 GraphSearchService"""
    return GraphSearchService(l5_graph=port)


class TestGraphSearchServiceHappyPath:
    """Happy Path"""

    @pytest.mark.asyncio
    async def test_search_calls_search_entities(self) -> None:
        """search() 应调用 L5GraphPort.search_entities()"""
        port = _make_graph_port(entities=[{"memory_id": "ent1", "type": "concept", "properties": {"name": "AI"}}])
        service = _make_service(port)

        await service.search("test_collection", "AI 技术")

        port.search_entities.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_converts_to_search_result(self) -> None:
        """search() 应返回兼容 SearchResult 的结果"""
        port = _make_graph_port(
            entities=[{"memory_id": "ent1", "type": "concept", "properties": {"name": "AI"}}],
            related={
                "ent1": [
                    {
                        "memory_id": "doc1",
                        "type": "document",
                        "properties": {"title": "AI 报告"},
                        "path": ["ent1", "doc1"],
                    }
                ]
            },
        )
        service = _make_service(port)

        results = await service.search("test_collection", "AI 技术")

        assert len(results) == 1
        result = results[0]
        assert "id" in result
        assert "score" in result
        assert "payload" in result
        assert result["id"] == "doc1"
        # score = type_weight * connection_count / (1 + hops)
        # document → default 0.5, connection_count=1, hops=len(path)=2
        expected = 0.5 * 1 / (1 + 2)
        assert abs(result["score"] - expected) < 1e-9

    @pytest.mark.asyncio
    async def test_score_uses_type_weight(self) -> None:
        """验证概念类型权重 0.8"""
        port = _make_graph_port(
            entities=[{"memory_id": "ent1", "type": "concept", "properties": {}}],
            related={
                "ent1": [
                    {
                        "memory_id": "doc1",
                        "type": "concept",
                        "properties": {},
                        "path": ["ent1", "mid", "doc1"],
                    }
                ]
            },
        )
        service = _make_service(port)

        results = await service.search("test_collection", "概念查询")

        assert len(results) == 1
        # concept → 0.8, connection_count=1, hops=len(path)=3
        assert abs(results[0]["score"] - 0.8 * 1 / (1 + 3)) < 1e-9

    @pytest.mark.asyncio
    async def test_signature_matches_dense(self) -> None:
        """验证 search() 签名与 Dense/Sparse 一致"""
        import inspect

        sig = inspect.signature(GraphSearchService.search)
        param_names = list(sig.parameters.keys())
        for expected in ("self", "collection", "query_text", "limit", "tenant_id", "filter_payload"):
            assert expected in param_names, f"缺少参数 {expected}"


class TestGraphSearchServiceEdgeCases:
    """Edge Cases"""

    @pytest.mark.asyncio
    async def test_no_matching_entities_returns_empty(self) -> None:
        """无匹配实体返回空列表"""
        port = _make_graph_port(entities=[])
        service = _make_service(port)

        results = await service.search("test_collection", "不存在的实体")

        assert results == []

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self) -> None:
        """空查询文本返回空列表"""
        port = _make_graph_port(entities=[])
        service = _make_service(port)

        results = await service.search("test_collection", "")

        assert results == []

    @pytest.mark.asyncio
    async def test_graph_port_exception_returns_empty(self) -> None:
        """L5GraphPort 抛出异常时透明降级返回空列表"""
        port = _make_graph_port(side_effect_search=RuntimeError("Neo4j 不可用"))
        service = _make_service(port)

        results = await service.search("test_collection", "查询")

        assert results == []

    @pytest.mark.asyncio
    async def test_find_related_exception_returns_empty(self) -> None:
        """find_related 抛出异常时返回空列表"""
        port = _make_graph_port(
            entities=[{"memory_id": "ent1", "type": "concept", "properties": {}}],
            side_effect_related=RuntimeError("图遍历失败"),
        )
        service = _make_service(port)

        results = await service.search("test_collection", "查询")

        assert results == []

    @pytest.mark.asyncio
    async def test_dedup_by_memory_id(self) -> None:
        """多个实体关联到同一文档时按 memory_id 去重"""
        port = _make_graph_port(
            entities=[
                {"memory_id": "ent1", "type": "concept", "properties": {}},
                {"memory_id": "ent2", "type": "person", "properties": {}},
            ],
            related={
                "ent1": [
                    {
                        "memory_id": "doc1",
                        "type": "document",
                        "properties": {},
                        "path": ["ent1", "doc1"],
                    }
                ],
                "ent2": [
                    {
                        "memory_id": "doc1",
                        "type": "document",
                        "properties": {},
                        "path": ["ent2", "doc1"],
                    }
                ],
            },
        )
        service = _make_service(port)

        results = await service.search("test_collection", "查询")

        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids)), f"应按 memory_id 去重: {ids}"
        assert "doc1" in ids


class TestGraphSearchServicePerformance:
    """Graph 检索延迟 P95 < 200ms（AsyncMock 模拟）"""

    @pytest.mark.asyncio
    async def test_graph_search_latency_p95_under_200ms(self) -> None:
        """Graph 检索延迟 P95 < 200ms"""
        import time

        port = _make_graph_port(
            entities=[{"memory_id": f"ent{i}", "type": "concept", "properties": {}} for i in range(10)],
            related={
                f"ent{i}": [
                    {
                        "memory_id": f"doc{i}",
                        "type": "document",
                        "properties": {},
                        "path": [f"ent{i}", f"doc{i}"],
                    }
                ]
                for i in range(10)
            },
        )
        service = _make_service(port)

        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            await service.search("test_collection", "查询")
            latencies.append((time.perf_counter() - start) * 1000)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        assert p95 < 200, f"Graph 检索延迟 P95={p95:.2f}ms，超过 200ms 门禁"
