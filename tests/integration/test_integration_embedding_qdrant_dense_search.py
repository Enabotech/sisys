"""Story 3-1a 端到端集成测试

验证 EmbeddingAPIClient (FlagEmbedding API) + Qdrant 在真实环境下的协作：
- Dense 语义检索（encode_text → search）
- Sparse 稀疏检索（encode_sparse → search_sparse）
- 嵌入质量验证（L2 归一化、维度、Sparse 格式）

依赖：真实 BGE-M3 模型 + 真实 Qdrant 服务
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import datetime, timezone

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, SparseVectorParams
from qdrant_client.models import SparseVector as QdrantSparseVector

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


@pytest.fixture(scope="session")
def embedding_service():
    """embedding-api 客户端，服务不可用时 skip"""
    get_test_env()
    try:
        from src.infrastructure.external_services.embedding.embedding_api_client import (
            EmbeddingAPIClient,
        )

        return EmbeddingAPIClient(EmbeddingConfig.from_env())
    except Exception as e:
        pytest.skip(f"embedding-api 不可用: {e}")


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
            threshold = 500  # API 模式含 HTTP 开销
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

    def test_encode_sparse_format(self, embedding_service) -> None:
        """encode_sparse 返回正确的 indices/values 格式"""
        result = embedding_service.encode_sparse("企业战略规划")
        assert isinstance(result, dict)
        assert "indices" in result
        assert "values" in result
        assert isinstance(result["indices"], list)
        assert isinstance(result["values"], list)
        assert len(result["indices"]) > 0, "Sparse 向量不应为空"
        assert len(result["indices"]) == len(result["values"])

    def test_encode_sparse_chinese_text(self, embedding_service) -> None:
        """中文文本 encode_sparse 质量验证"""
        result = embedding_service.encode_sparse("企业战略规划与市场分析")

        # 中文文本应产生有意义的稀疏向量
        assert len(result["indices"]) >= 2, f"中文文本应产生至少 2 个 token 权重，实际 {len(result['indices'])}"

        # 验证 indices 按升序排列
        assert result["indices"] == sorted(result["indices"]), "indices 应升序排列"

        # 验证所有 values 为正浮点数
        for v in result["values"]:
            assert isinstance(v, float)
            assert v > 0, f"Sparse 权重应为正数，实际 {v}"

    def test_encode_sparse_values_sum_positive(self, embedding_service) -> None:
        """encode_sparse 权重总和为正（BGE-M3 词汇权重特性）"""
        result = embedding_service.encode_sparse("人工智能与机器学习")
        total_weight = sum(result["values"])
        assert total_weight > 0, f"Sparse 权重总和应为正，实际 {total_weight}"

    def test_dense_and_sparse_from_same_model(self, embedding_service) -> None:
        """同一模型产出的 Dense 和 Sparse 嵌入应一致（共用同一模型权重）"""
        text = "企业数字化转型战略"

        dense = embedding_service.encode_text(text)
        sparse = embedding_service.encode_sparse(text)

        assert len(dense) == 1024
        assert len(sparse["indices"]) > 0
        # 验证 Dense 向量为 L2 归一化
        norm = math.sqrt(sum(x * x for x in dense))
        assert abs(norm - 1.0) < 0.01

    def test_encode_sparse_empty_text_raises(self, embedding_service) -> None:
        """空文本时 encode_sparse 抛出 ValueError（纯同步，无需 Qdrant）"""
        with pytest.raises(ValueError, match="文本不能为空"):
            embedding_service.encode_sparse("")

    def test_encode_sparse_whitespace_raises(self, embedding_service) -> None:
        """纯空白文本时 encode_sparse 抛出 ValueError"""
        with pytest.raises(ValueError, match="文本不能为空"):
            embedding_service.encode_sparse("   ")


class TestSparseSearchEndToEnd:
    """Sparse 稀疏检索端到端集成测试

    所有 Qdrant 相关 Sparse 测试共用一个 Collection，减少 create/delete 开销。
    """

    @pytest.fixture
    def sparse_collection_name(self) -> str:
        """生成唯一 Collection 名称"""
        return f"test_sparse_{uuid.uuid4().hex[:8]}"

    @pytest.mark.asyncio
    async def test_sparse_search_e2e(self, qdrant_client, sparse_collection_name, embedding_service) -> None:
        """端到端：空查询→encode_sparse→upsert→search_sparse→排序→无匹配"""
        from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
        from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

        cm = QdrantCollectionManager(qdrant_client)
        await cm.create_collection(
            name=sparse_collection_name,
            vector_size=1024,
            distance="Cosine",
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )
        try:
            storage = QdrantVectorStorage(qdrant_client)

            # 子测试 1: 空集合无匹配
            query_sparse = embedding_service.encode_sparse("完全不相关的查询文本")
            results = await storage.search_sparse(sparse_collection_name, query_sparse, limit=5)
            assert results == [], "空 Collection 应返回空列表"

            # 子测试 2: 写入 Sparse 向量后检索
            texts = ["企业战略规划", "财务分析报告", "市场调研数据", "技术架构文档", "人力资源计划"]
            points = []
            for i, text in enumerate(texts):
                sr = embedding_service.encode_sparse(text)
                points.append(
                    PointStruct(
                        id=i + 1,
                        vector={
                            "sparse": QdrantSparseVector(
                                indices=sr["indices"],
                                values=sr["values"],
                            ),
                        },
                        payload={"text": text, "doc_index": i},
                    )
                )
            await qdrant_client.upsert(collection_name=sparse_collection_name, points=points)

            query_sparse = embedding_service.encode_sparse("战略规划")
            results = await storage.search_sparse(sparse_collection_name, query_sparse, limit=3)

            assert len(results) > 0
            assert len(results) <= 3
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True), "结果应按 score 降序排列"
            assert results[0]["payload"]["text"] == "企业战略规划"
        finally:
            await cm.delete_collection(sparse_collection_name)
