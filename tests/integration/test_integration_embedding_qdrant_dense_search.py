"""Dense 语义检索端到端集成测试

验证 BGE3EmbeddingService + Qdrant + DenseSemanticSearchService 在真实环境下的协作
依赖：真实 bge-m3 模型 + 真实 Qdrant 服务
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import datetime, timezone

import pytest
from qdrant_client import AsyncQdrantClient

from src.infrastructure.config.embedding import EmbeddingConfig
from src.infrastructure.storage.qdrant.collection_manager import (
    QdrantCollectionManager,
)
from src.infrastructure.storage.qdrant.models import VectorPoint
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env

pytestmark = [pytest.mark.integration, pytest.mark.qdrant]


@pytest.fixture
async def qdrant_client():
    """创建 Qdrant 客户端，连接失败时 skip"""
    env = get_test_env()
    client = AsyncQdrantClient(host=env.qdrant.host, port=env.qdrant.port)
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def collection_name() -> str:
    """生成唯一 Collection 名称"""
    return f"test_dense_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def embedding_service():
    """加载 bge-m3 模型，不可用时 skip"""
    try:
        from src.infrastructure.external_services.embedding.bge3_embedding_service import (
            BGE3EmbeddingService,
        )

        return BGE3EmbeddingService(EmbeddingConfig.from_env())
    except Exception as e:
        pytest.skip(f"bge-m3 模型不可用: {e}")


class TestDenseSearchEndToEnd:
    """端到端 Dense 检索集成测试"""

    @pytest.mark.asyncio
    async def test_embed_and_search_e2e(self, qdrant_client, collection_name, embedding_service) -> None:
        """端到端：embed → upsert → search → 验证排序"""
        cm = QdrantCollectionManager(qdrant_client)
        await cm.create_collection(name=collection_name, vector_size=1024, distance="Cosine")
        try:
            storage = QdrantVectorStorage(qdrant_client)
            texts = ["企业战略规划报告", "财务分析总结", "市场调研数据", "技术架构文档", "人力资源计划"]
            vectors = embedding_service.encode_texts(texts)
            points = [
                VectorPoint(
                    id=f"doc_{i}",
                    vector=vectors[i],
                    payload={"text": texts[i], "doc_index": i},
                    created_at=datetime.now(timezone.utc),
                )
                for i in range(len(texts))
            ]
            await storage.upsert_points(collection_name, points)

            query_vector = embedding_service.encode_text("战略规划")
            results = await storage.search(collection_name, query_vector, limit=3)

            assert len(results) > 0
            assert len(results) <= 3
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)
            assert results[0]["payload"]["text"] == "企业战略规划报告"
        finally:
            await cm.delete_collection(collection_name)

    @pytest.mark.asyncio
    async def test_payload_filter(self, qdrant_client, collection_name, embedding_service) -> None:
        """Payload 过滤集成测试"""
        cm = QdrantCollectionManager(qdrant_client)
        await cm.create_collection(name=collection_name, vector_size=1024, distance="Cosine")
        try:
            storage = QdrantVectorStorage(qdrant_client)
            texts = ["财务审计报告", "投资风险评估", "技术架构设计", "财务预算分析", "产品技术方案"]
            domains = ["finance", "finance", "technology", "finance", "technology"]
            vectors = embedding_service.encode_texts(texts)
            points = [
                VectorPoint(
                    id=f"doc_{i}",
                    vector=vectors[i],
                    payload={"text": texts[i], "business_domain": domains[i]},
                    created_at=datetime.now(timezone.utc),
                )
                for i in range(len(texts))
            ]
            await storage.upsert_points(collection_name, points)

            query_vector = embedding_service.encode_text("财务")
            results = await storage.search(
                collection_name, query_vector, limit=10, filter_payload={"business_domain": "finance"}
            )

            assert len(results) > 0
            for r in results:
                assert r["payload"]["business_domain"] == "finance"
        finally:
            await cm.delete_collection(collection_name)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_search_latency(self, qdrant_client, collection_name, embedding_service) -> None:
        """检索延迟基准测试（P95 < 200ms GPU / < 500ms CPU）"""
        cm = QdrantCollectionManager(qdrant_client)
        await cm.create_collection(name=collection_name, vector_size=1024, distance="Cosine")
        try:
            storage = QdrantVectorStorage(qdrant_client)
            texts = [f"测试文档内容编号{i}" for i in range(100)]
            vectors = embedding_service.encode_texts(texts)
            points = [
                VectorPoint(
                    id=f"doc_{i}",
                    vector=vectors[i],
                    payload={"text": texts[i]},
                    created_at=datetime.now(timezone.utc),
                )
                for i in range(len(texts))
            ]
            await storage.upsert_points(collection_name, points)

            # 预热
            for _ in range(5):
                qv = embedding_service.encode_text("预热查询")
                await storage.search(collection_name, qv, limit=5)

            # 50 次查询
            latencies = []
            for _ in range(50):
                start = time.perf_counter()
                qv = embedding_service.encode_text("性能测试查询文本"[:512])
                await storage.search(collection_name, qv, limit=5)
                latencies.append((time.perf_counter() - start) * 1000)

            latencies.sort()
            p95 = latencies[int(len(latencies) * 0.95)]
            config = EmbeddingConfig.from_env()
            threshold = 200 if config.device == "cuda" else 500
            assert p95 < threshold, f"P95={p95:.1f}ms 超过阈值 {threshold}ms"
        finally:
            await cm.delete_collection(collection_name)


class TestEmbeddingNormalization:
    """嵌入归一化验证"""

    def test_l2_norm_approx_one(self, embedding_service) -> None:
        """bge-m3 输出向量 L2 范数 ≈ 1.0"""
        vector = embedding_service.encode_text("测试归一化")
        norm = math.sqrt(sum(x * x for x in vector))
        assert abs(norm - 1.0) < 0.01, f"L2 范数 {norm} 不接近 1.0"

    def test_dimension_is_1024(self, embedding_service) -> None:
        """bge-m3 输出维度为 1024"""
        vector = embedding_service.encode_text("测试维度")
        assert len(vector) == 1024
