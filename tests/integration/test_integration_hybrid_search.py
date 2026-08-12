"""Story 3-1b 混合检索端到端集成测试

验证 embed→Dense search + Sparse search→RRF fusion 完整链路。
需要真实 Qdrant 服务和嵌入 API 服务。

运行: SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_hybrid_search.py -v
"""

from __future__ import annotations

import time

import pytest

from src.domain.ports.l3_vector import SearchResult
from src.domain.services.rrf_fusion import RRF_K_DEFAULT, fuse


class TestRrfFusionIntegration:
    """RRF 融合算法集成测试（纯内存计算，无外部依赖）"""

    @pytest.mark.asyncio
    async def test_fuse_two_realistic_result_sets(self) -> None:
        """模拟真实 Dense + Sparse 结果集的两路融合"""
        dense_results: list[SearchResult] = [
            SearchResult(id="doc-1", score=0.95, payload={"title": "战略规划报告"}),
            SearchResult(id="doc-2", score=0.88, payload={"title": "市场分析报告"}),
            SearchResult(id="doc-3", score=0.82, payload={"title": "财务预算报告"}),
            SearchResult(id="doc-4", score=0.75, payload={"title": "人力资源报告"}),
            SearchResult(id="doc-5", score=0.70, payload={"title": "技术发展报告"}),
        ]
        sparse_results: list[SearchResult] = [
            SearchResult(id="doc-2", score=12.5, payload={"title": "市场分析报告"}),
            SearchResult(id="doc-6", score=10.0, payload={"title": "市场调研报告"}),
            SearchResult(id="doc-1", score=8.5, payload={"title": "战略规划报告"}),
        ]

        result = fuse(dense_results, sparse_results)

        # doc-2 和 doc-1 跨通道出现，RRF 分数累加
        # doc-2: rank2 in dense (1/62) + rank1 in sparse (1/61) ≈ 0.03252
        # doc-1: rank1 in dense (1/61) + rank3 in sparse (1/63) ≈ 0.03227
        # doc-6: rank2 in sparse (1/62) ≈ 0.01613
        # doc-3: rank3 in dense (1/63) ≈ 0.01587
        # doc-4: rank4 in dense (1/64) ≈ 0.01563
        # doc-5: rank5 in dense (1/65) ≈ 0.01538

        assert len(result) == 6  # 5 dense + 3 sparse - 2 duplicates = 6
        assert result[0]["id"] == "doc-2"  # 跨通道共识 → 最高 RRF
        assert result[1]["id"] == "doc-1"
        # 验证降序
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_fuse_with_mock_results_large(self) -> None:
        """大结果集（50 路各 50 结果）的融合性能"""
        dense = []
        sparse = []
        for i in range(50):
            dense.append(SearchResult(id=f"d_{i}", score=0.9 - i * 0.01, payload={}))
            sparse.append(SearchResult(id=f"s_{i}", score=20.0 - i * 0.2, payload={}))
        # 加入跨通道重复
        for i in range(10):
            sparse[i] = SearchResult(id=f"d_{i}", score=10.0 - i * 0.5, payload={})

        start = time.perf_counter()
        result = fuse(dense, sparse)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) == 90  # 50 + 50 - 10 duplicates = 90
        assert elapsed_ms < 50  # P95 门禁

    @pytest.mark.asyncio
    async def test_symmetric_fusion_with_same_results(self) -> None:
        """两路结果完全相同时的对称融合"""
        same: list[SearchResult] = [
            SearchResult(id="a", score=0.9, payload={}),
            SearchResult(id="b", score=0.8, payload={}),
        ]
        result = fuse(same, same)
        assert len(result) == 2
        # a: 1/(60+1) + 1/(60+1) = 2/61
        # b: 1/(60+2) + 1/(60+2) = 2/62
        assert result[0]["id"] == "a"
        assert result[0]["score"] > result[1]["score"]

    @pytest.mark.asyncio
    async def test_three_way_fusion_v1(self) -> None:
        """三路融合 V1 预留接口（Story 3-4）"""
        dense: list[SearchResult] = [SearchResult(id="d1", score=0.9, payload={})]
        sparse: list[SearchResult] = [SearchResult(id="s1", score=10.0, payload={})]
        graph: list[SearchResult] = [SearchResult(id="d1", score=0.5, payload={"from_graph": True})]

        result = fuse(dense, sparse, graph, weights=[0.4, 0.4, 0.2])

        assert len(result) == 2  # d1 (duplicate) + s1
        # d1: rank1 in dense (w=0.4) + rank1 in graph (w=0.2) = 0.6/61
        d1 = next(r for r in result if r["id"] == "d1")
        expected_d1 = 0.4 / (RRF_K_DEFAULT + 1) + 0.2 / (RRF_K_DEFAULT + 1)
        assert abs(d1["score"] - expected_d1) < 1e-9
        # payload 保留首次出现（dense 在前，payload={}）
        assert d1["payload"] == {}

    @pytest.mark.asyncio
    async def test_single_list_passthrough(self) -> None:
        """单路直通 — 原样返回"""
        results: list[SearchResult] = [
            SearchResult(id="x", score=0.5, payload={}),
            SearchResult(id="y", score=0.3, payload={}),
        ]
        result = fuse(results)
        assert result == results


class TestHybridSearchCompositionValidation:
    """验证 Composition Root 端口注册正确性（无 DI 实例化）"""

    @pytest.mark.asyncio
    async def test_all_ports_registered(self) -> None:
        """三个搜索端口均已注册"""

        # 确保 bootstrap 已运行
        from src.domain.ports.registry import _global_registry

        specs = _global_registry.list_all()
        names = {s.name for s in specs}

        assert "dense_search_service" in names
        assert "sparse_search_service" in names
        assert "hybrid_search_service" in names

    @pytest.mark.asyncio
    async def test_search_ports_have_search_team_owner(self) -> None:
        """所有搜索端口的所有者为 search-team"""
        from src.domain.ports.registry import _global_registry

        search_ports = ["dense_search_service", "sparse_search_service", "hybrid_search_service"]
        for name in search_ports:
            spec = _global_registry.get(name)
            assert spec is not None, f"{name} 未注册"
            assert spec.owner == "search-team", f"{name} owner={spec.owner}"


class TestHybridSearchEndToEnd:
    """端到端混合检索：embed → Dense + Sparse → RRF fusion

    使用真实 Qdrant + 嵌入 API。每个测试自包含（创建→检索→清理 Collection）。
    """

    @staticmethod
    async def _create_test_collection(context: dict) -> str:
        """创建含文档的测试 Collection，返回 Collection 名称"""
        import uuid

        from src.infrastructure.config.embedding import EmbeddingConfig
        from src.infrastructure.config.qdrant import QdrantConfig
        from src.infrastructure.external_services.embedding.embedding_api_client import (
            EmbeddingAPIClient,
        )
        from src.infrastructure.storage.qdrant.collection_manager import (
            QdrantCollectionManager,
        )
        from src.infrastructure.storage.qdrant.models import VectorPoint
        from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
        from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
        from tests.environments import get_test_env

        env = get_test_env()
        qdrant = QdrantManager(QdrantConfig(host=env.qdrant.host, port=env.qdrant.port, timeout=30.0))
        collection_mgr = QdrantCollectionManager(qdrant.get_client())
        storage = QdrantVectorStorage(qdrant.get_client())
        embed = EmbeddingAPIClient(EmbeddingConfig.from_env())

        name = f"e2e_hybrid_{uuid.uuid4().hex[:8]}"
        texts = [
            "企业战略规划报告 2026年度",
            "财务预算与分析总结",
            "市场调研与竞争分析",
            "技术架构设计文档",
            "人力资源发展规划",
        ]

        await collection_mgr.create_collection(name=name, vector_size=1024, distance="Cosine")
        dense = await embed.embed_documents(texts)
        points = [VectorPoint(id=f"doc_{i}", vector=dense[i], payload={"text": texts[i]}) for i in range(len(texts))]
        await storage.upsert_points(name, points)
        await embed.close()

        context["_cleanup"] = name
        return name

    @staticmethod
    async def _cleanup(context: dict) -> None:
        """清理测试 Collection"""

        name = context.get("_cleanup")
        if not name:
            return
        from src.infrastructure.config.qdrant import QdrantConfig
        from src.infrastructure.storage.qdrant.collection_manager import (
            QdrantCollectionManager,
        )
        from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
        from tests.environments import get_test_env

        env = get_test_env()
        qdrant = QdrantManager(QdrantConfig(host=env.qdrant.host, port=env.qdrant.port, timeout=30.0))
        collection_mgr = QdrantCollectionManager(qdrant.get_client())
        await collection_mgr.delete_collection(name)

    @pytest.mark.asyncio
    async def test_full_hybrid_search_pipeline(self) -> None:
        """完整端到端链路：embed → Dense + Sparse → RRF fusion → 结果验证"""
        import time

        from src.application.services.dense_search_service import DenseSemanticSearchService
        from src.application.services.hybrid_search_service import HybridSearchService
        from src.application.services.sparse_search_service import Bm25SparseSearchService
        from src.domain.services.rrf_fusion import fuse
        from src.infrastructure.config.embedding import EmbeddingConfig
        from src.infrastructure.config.qdrant import QdrantConfig
        from src.infrastructure.external_services.embedding.embedding_api_client import (
            EmbeddingAPIClient,
        )
        from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
        from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
        from tests.environments import get_test_env

        context: dict = {}

        try:
            # 1. 创建测试 Collection 并索引文档
            collection = await self._create_test_collection(context)

            env = get_test_env()
            qdrant = QdrantManager(QdrantConfig(host=env.qdrant.host, port=env.qdrant.port, timeout=30.0))
            vector_storage = QdrantVectorStorage(qdrant.get_client())
            embed = EmbeddingAPIClient(EmbeddingConfig.from_env())

            # 2. 构造服务（两路注入，向后兼容）
            dense_svc = DenseSemanticSearchService(embed, vector_storage)
            sparse_svc = Bm25SparseSearchService(embed, vector_storage)
            hybrid_svc = HybridSearchService(dense_svc, sparse_svc, fuse)

            # 3. 执行混合检索
            t0 = time.perf_counter()
            results = await hybrid_svc.search(collection, "企业战略", limit=5)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            # 4. 验证结果
            assert isinstance(results, list)
            assert len(results) > 0, f"端到端混合检索返回空结果，耗时 {elapsed_ms:.0f}ms"
            assert len(results) <= 5
            for r in results:
                assert "id" in r
                assert "score" in r
                assert "payload" in r
            # 验证降序
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)

            # 5. 延迟门禁（CPU 环境 <1500ms）
            assert elapsed_ms < 1500, f"端到端延迟 {elapsed_ms:.0f}ms 超过 1500ms 门禁"

        finally:
            await self._cleanup(context)

    @pytest.mark.asyncio
    async def test_three_way_hybrid_search_with_mock_graph(self) -> None:
        """三路混合检索集成：Dense + Sparse（真实）+ Graph（Mock）→ 三路 RRF 加权融合"""
        from src.application.services.dense_search_service import DenseSemanticSearchService
        from src.application.services.hybrid_search_service import HybridSearchService
        from src.application.services.sparse_search_service import Bm25SparseSearchService
        from src.domain.ports.l3_vector import SearchResult
        from src.domain.services.rrf_fusion import fuse
        from src.infrastructure.config.embedding import EmbeddingConfig
        from src.infrastructure.config.qdrant import QdrantConfig
        from src.infrastructure.external_services.embedding.embedding_api_client import (
            EmbeddingAPIClient,
        )
        from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
        from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
        from tests.environments import get_test_env

        context: dict = {}

        try:
            # 1. 创建测试 Collection 并索引文档
            collection = await self._create_test_collection(context)

            env = get_test_env()
            qdrant = QdrantManager(QdrantConfig(host=env.qdrant.host, port=env.qdrant.port, timeout=30.0))
            vector_storage = QdrantVectorStorage(qdrant.get_client())
            embed = EmbeddingAPIClient(EmbeddingConfig.from_env())

            # 2. 构造 Mock Graph 检索服务
            class MockGraphService:
                async def search(self, collection, query_text, limit=10, tenant_id=None, filter_payload=None):
                    return [
                        SearchResult(id="doc_0", score=0.5, payload={"title": "战略规划", "from_graph": True}),
                    ]

            # 3. 三路混合检索
            dense_svc = DenseSemanticSearchService(embed, vector_storage)
            sparse_svc = Bm25SparseSearchService(embed, vector_storage)
            hybrid_svc = HybridSearchService(
                dense_search=dense_svc,
                sparse_search=sparse_svc,
                fuse=fuse,
                graph_search=MockGraphService(),
                weights=[1.0, 1.0, 0.5],
            )

            # 4. 执行三路混合检索
            results = await hybrid_svc.search(collection, "企业战略", limit=5)

            # 5. 验证结果
            assert isinstance(results, list)
            assert len(results) > 0
            for r in results:
                assert "id" in r
                assert "score" in r
                assert "payload" in r

        finally:
            await self._cleanup(context)

    @pytest.mark.asyncio
    async def test_rerank_integration_with_mock(self) -> None:
        """重排序集成：Mock 重排序器对 RRF 融合结果进行精排"""
        from src.application.services.hybrid_search_service import HybridSearchService
        from src.domain.ports.l3_vector import SearchResult
        from src.domain.services.rrf_fusion import fuse

        dense_results = [
            SearchResult(id="doc1", score=0.95, payload={"title": "战略规划"}),
            SearchResult(id="doc2", score=0.85, payload={"title": "市场分析"}),
            SearchResult(id="doc3", score=0.75, payload={"title": "财务预算"}),
        ]
        sparse_results = [
            SearchResult(id="doc2", score=10.0, payload={"title": "市场分析"}),
            SearchResult(id="doc4", score=8.0, payload={"title": "市场调研"}),
        ]

        class MockReranker:
            def __init__(self) -> None:
                self.called = False

            async def rerank(self, query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]:
                self.called = True
                for r in results:
                    r["payload"]["rerank_score"] = r["score"]
                return sorted(results, key=lambda r: r["score"], reverse=True)[:top_k]

        class MockDense:
            async def search(self, collection, query_text, limit=10, tenant_id=None, filter_payload=None):
                return dense_results

        class MockSparse:
            async def search(self, collection, query_text, limit=10, tenant_id=None, filter_payload=None):
                return sparse_results

        reranker = MockReranker()
        hybrid_svc = HybridSearchService(
            dense_search=MockDense(),
            sparse_search=MockSparse(),
            fuse=fuse,
            reranker=reranker,
        )

        results = await hybrid_svc.search("test", "查询", limit=5)

        assert isinstance(results, list)
        assert len(results) > 0
        assert reranker.called, "重排序器应被调用"
