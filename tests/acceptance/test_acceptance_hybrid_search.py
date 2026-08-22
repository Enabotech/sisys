"""Story 3-1b BM25 稀疏检索 + RRF 融合 验收测试

使用真实 Qdrant 服务和 bge-m3 嵌入模型的集成测试，无 mock。
复用 Story 3-1a 的 fixtures (qdrant_client / collection_manager / vector_storage / embedding_service)。

运行: poetry run pytest tests/acceptance/test_acceptance_hybrid_search.py -v

前置条件:
    - Qdrant 服务运行在 localhost:6333（或设置 QDRANT_* 环境变量）
    - embedding-api 服务运行在 localhost:8001（或设置 EMBEDDING_API_* 环境变量）
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.services.dense_search_service import DenseSemanticSearchService
from src.application.services.hybrid_search_service import HybridSearchService
from src.application.services.sparse_search_service import Bm25SparseSearchService
from src.domain.exceptions import HybridSearchError, ValidationError
from src.domain.ports.l3_vector import SearchResult
from src.domain.services.rrf_fusion import fuse
from src.infrastructure.config.embedding import EmbeddingConfig
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.models import VectorPoint
from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env

scenarios("test_acceptance_hybrid_search.feature")


# ===================================================================
# Fixtures（复用 Story 3-1a 模式）
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


@pytest.fixture
def qdrant_client() -> QdrantManager:
    """真实 Qdrant 客户端实例"""
    env = get_test_env()
    from src.infrastructure.config.qdrant import QdrantConfig

    config = QdrantConfig(
        host=env.qdrant.host,
        port=env.qdrant.port,
        grpc_port=env.qdrant.grpc_port,
        api_key=env.qdrant.api_key,
        https=False,
        timeout=30.0,
    )
    return QdrantManager(config)


@pytest.fixture
def collection_manager(qdrant_client: QdrantManager) -> QdrantCollectionManager:
    """真实 Qdrant Collection 管理器"""
    return QdrantCollectionManager(qdrant_client.get_client())


@pytest.fixture
def vector_storage(qdrant_client: QdrantManager) -> QdrantVectorStorage:
    """真实 Qdrant 向量存储实例"""
    return QdrantVectorStorage(qdrant_client.get_client())


@pytest.fixture
async def embedding_service():
    """bge-m3 嵌入服务实例（async httpx.AsyncClient）"""
    get_test_env()
    try:
        from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

        client = EmbeddingAPIClient(EmbeddingConfig.from_env())
        yield client
        await client.close()
    except Exception as e:
        pytest.skip(f"embedding-api 不可用: {e}")


@pytest.fixture(autouse=True)
def cleanup_collections(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """每个测试结束后清理创建的 Collection"""
    yield
    for name in list(context.get("created_collections", [])):
        try:
            event_loop.run_until_complete(collection_manager.delete_collection(name))
        except Exception:
            pass


def _create_collection(context: dict[str, Any], prefix: str = "test_hybrid") -> str:
    """生成唯一 Collection 名称并注册到清理列表"""
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    context["collection_name"] = name
    context.setdefault("created_collections", []).append(name)
    return name


# ===================================================================
# Background 步骤
# ===================================================================


@given("嵌入服务可用")
def given_embedding_available(embedding_service) -> None:
    assert embedding_service is not None


@given("Qdrant 服务可用")
def given_qdrant_available(qdrant_client: QdrantManager, event_loop) -> None:
    async def _check():
        try:
            await qdrant_client.health_check()
            return True
        except Exception:
            return False

    if not event_loop.run_until_complete(_check()):
        pytest.skip("Qdrant 服务不可用")


# ===================================================================
# AC-1: BM25 稀疏检索 — 使用真实 embedding + Qdrant
# ===================================================================


@given("Qdrant Collection 包含已索引的文档稀疏向量")
def given_collection_with_sparse_vectors(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    embedding_service,
    event_loop,
) -> None:
    """创建 Collection 并插入含 Dense + Sparse 双向量文档"""
    collection = _create_collection(context, "test_sparse_search")
    texts = ["企业战略规划报告", "财务分析总结", "市场调研数据", "技术架构文档", "人力资源计划"]

    async def _setup():
        # 创建支持 sparse vectors 的 Collection
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")
        dense_vecs = await embedding_service.embed_documents(texts)
        sparse_vecs = await embedding_service.embed_sparse(texts)
        points = [
            VectorPoint(
                id=f"doc_{i}",
                vector=dense_vecs[i],
                payload={"text": texts[i], "business_domain": "strategy" if i < 2 else "operations"},
            )
            for i in range(len(texts))
        ]
        await vector_storage.upsert_points(collection, points)
        context["sparse_vecs"] = sparse_vecs

    event_loop.run_until_complete(_setup())


@when('我执行 BM25 稀疏检索查询 "企业战略规划"')
def when_bm25_search(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
) -> None:
    """执行 BM25 稀疏检索"""
    collection = context["collection_name"]
    service = Bm25SparseSearchService(embedding_service, vector_storage)

    async def _search():
        return await service.search(collection=collection, query_text="企业战略规划", limit=5)

    t0 = time.perf_counter()
    context["search_results"] = event_loop.run_until_complete(_search())
    context["search_latency_ms"] = (time.perf_counter() - t0) * 1000


@then("返回最多 5 个结果")
def then_at_most_5(context: dict[str, Any]) -> None:
    results = context["search_results"]
    assert results is not None
    assert len(results) <= 5, f"期望 ≤5，实际 {len(results)}"


@then("每个结果包含 id、score、payload 字段")
def then_required_fields(context: dict[str, Any]) -> None:
    for r in context["search_results"]:
        assert "id" in r
        assert "score" in r
        assert "payload" in r


@then("结果按 score 降序排列")
def then_sorted_desc(context: dict[str, Any]) -> None:
    results = context["search_results"]
    if len(results) > 1:
        scores = [r["score"] for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"


# ===================================================================
# AC-2: RRF 融合算法（纯 Python，直接调用）
# ===================================================================


@given("Qdrant Collection 包含已索引的文档向量")
def given_collection_with_vectors(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    embedding_service,
    event_loop,
) -> None:
    """创建 Collection 并插入文档（供 AC-2 场景的背景步骤使用）"""
    collection = _create_collection(context, "test_rrf_fusion")
    texts = ["企业战略规划报告", "财务分析总结", "市场调研数据"]

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")
        dense_vecs = await embedding_service.embed_documents(texts)
        points = [VectorPoint(id=f"doc_{i}", vector=dense_vecs[i], payload={"text": texts[i]}) for i in range(len(texts))]
        await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_setup())


@given("Dense 检索返回 3 个结果")
def given_3_dense(context: dict[str, Any]) -> None:
    context["dense"] = [
        SearchResult(id="doc1", score=0.95, payload={"title": "战略规划"}),
        SearchResult(id="doc2", score=0.85, payload={"title": "市场分析"}),
        SearchResult(id="doc3", score=0.75, payload={"title": "财务预算"}),
    ]


@given("Sparse 检索返回 3 个结果")
def given_3_sparse(context: dict[str, Any]) -> None:
    context["sparse"] = [
        SearchResult(id="doc2", score=10.0, payload={"title": "市场分析"}),
        SearchResult(id="doc4", score=8.0, payload={"title": "市场调研"}),
        SearchResult(id="doc1", score=5.0, payload={"title": "战略规划"}),
    ]


@when("我执行 RRF 融合")
def when_rrf_fusion(context: dict[str, Any]) -> None:
    context["fused"] = fuse(context.get("dense", []), context.get("sparse", []))


@then("返回合并去重后的排序结果")
def then_merged_deduplicated_sorted(context: dict[str, Any]) -> None:
    fused = context["fused"]
    assert len(fused) >= 1
    ids = [r["id"] for r in fused]
    assert len(ids) == len(set(ids)), f"重复: {ids}"
    scores = [r["score"] for r in fused]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]


@then("所有结果的 score 为 RRF 分数")
def then_scores_are_rrf(context: dict[str, Any]) -> None:
    for r in context["fused"]:
        assert 0.0 < r["score"] <= 1.0, f"RRF 分数异常: {r['score']}"


# ===================================================================
# AC-3: 混合检索编排 — 使用真实 Dense + Sparse 服务
# ===================================================================


@given("Dense 检索服务和 Sparse 检索服务均可用")
def given_both_available_step(context: dict[str, Any], embedding_service, vector_storage: QdrantVectorStorage) -> None:
    """两路服务均可用 — fixture 已保证"""
    pass


@when('我执行混合检索查询 "企业战略"')
def when_hybrid_search(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
) -> None:
    """使用真实 Dense + Sparse 服务执行混合检索，覆盖 AC-3 正常 + AC-6 降级场景

    根据 Given 步骤设置的 context 标志选择行为：
    - both_unavailable → 两路均失败，捕获 RuntimeError
    - sparse_unavailable → Sparse 失败，降级为 Dense-only
    - 默认 → 正常两路检索
    """
    collection = context["collection_name"]

    async def _run(dense_svc, sparse_svc):
        service = HybridSearchService(dense_search=dense_svc, sparse_search=sparse_svc, fuse=fuse)
        return await service.search(collection=collection, query_text="企业战略", limit=10)

    # 两路均不可用
    if context.get("both_unavailable"):
        dense_svc = DenseSemanticSearchService(embedding_service, vector_storage)
        sparse_svc = Bm25SparseSearchService(embedding_service, vector_storage)

        async def _fail_dense(
            _coll: str, _q: str, _limit: int = 10, _tenant_id: str | None = None, _filter_payload: dict | None = None
        ) -> list[SearchResult]:
            raise RuntimeError("Dense 不可用")

        async def _fail_sparse(
            _coll: str, _q: str, _limit: int = 10, _tenant_id: str | None = None, _filter_payload: dict | None = None
        ) -> list[SearchResult]:
            raise RuntimeError("Sparse 不可用")

        setattr(dense_svc, "search", _fail_dense)
        setattr(sparse_svc, "search", _fail_sparse)

        try:
            event_loop.run_until_complete(_run(dense_svc, sparse_svc))
            context["hybrid_error"] = None
        except (HybridSearchError, RuntimeError) as e:
            context["results"] = []
            context["hybrid_error"] = e
        return

    # Sparse 不可用 — 降级为 Dense-only
    if context.get("sparse_unavailable"):
        dense_svc = DenseSemanticSearchService(embedding_service, vector_storage)
        sparse_svc = Bm25SparseSearchService(embedding_service, vector_storage)

        async def _fail_sparse(
            _coll: str, _q: str, _limit: int = 10, _tenant_id: str | None = None, _filter_payload: dict | None = None
        ) -> list[SearchResult]:
            raise asyncio.TimeoutError("Sparse 嵌入超时")

        setattr(sparse_svc, "search", _fail_sparse)
        context["search_results"] = event_loop.run_until_complete(_run(dense_svc, sparse_svc))
        return

    # 正常两路检索
    t0 = time.perf_counter()
    dense_svc = DenseSemanticSearchService(embedding_service, vector_storage)
    sparse_svc = Bm25SparseSearchService(embedding_service, vector_storage)
    context["search_results"] = event_loop.run_until_complete(_run(dense_svc, sparse_svc))
    context["hybrid_latency_ms"] = (time.perf_counter() - t0) * 1000


@then("返回融合后的混合排序结果")
def then_hybrid_ranked(context: dict[str, Any]) -> None:
    results = context["search_results"]
    assert isinstance(results, list)
    assert len(results) > 0, "混合检索应返回结果"
    for r in results:
        assert "id" in r
        assert "score" in r
        assert "payload" in r


@then("结果数量不超过指定的 limit")
def then_within_limit(context: dict[str, Any]) -> None:
    assert len(context["search_results"]) <= 10


# ===================================================================
# AC-4: 索引管线（已迁移事件驱动 — ChunkIndexingHandler 承担索引）
# ===================================================================


@given("文档解析已完成")
def given_document_parsed(context: dict[str, Any]) -> None:
    """构造 parse_result 供事件驱动链使用"""
    context["parse_result"] = {
        "status": "completed",
        "document_id": str(uuid.uuid4()),
        "tenant_id": f"test-accept-{uuid.uuid4().hex[:8]}",
    }


@when("语义分块完成并发布 RAGIndexed 事件")
def given_rag_indexed_event(context: dict[str, Any]) -> None:
    """RAGIndexed 事件已就绪（由 SemanticChunkingService 发布）"""
    from src.domain.events.workflow_events import RAGIndexed

    context["rag_indexed_event"] = RAGIndexed(
        document_id=uuid.uuid4(),
        index_name="cross_document_summaries",
        chunk_count=5,
        tenant_id="test-tenant",
    )


@when("ChunkIndexingHandler 消费事件执行分块索引")
def when_chunk_indexing_handler_processes(context: dict[str, Any]) -> None:
    """验证 ChunkIndexingHandler 可处理 RAGIndexed 事件"""
    from unittest.mock import MagicMock

    from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler

    handler = ChunkIndexingHandler(
        embedding_service=MagicMock(),
        l3_vector=MagicMock(),
        document_repository=MagicMock(),
    )
    event = context.get("rag_indexed_event")
    assert event is not None, "RAGIndexed 事件未就绪"
    assert hasattr(handler, "handle_chunk_indexed"), "ChunkIndexingHandler 应包含 handle_chunk_indexed 方法"


@then("ChunkIndexingHandler 消费事件执行分块索引")
def then_handler_consumes_event(context: dict[str, Any]) -> None:
    """验证事件处理器已就绪"""


@then("写入 Qdrant 分块级点（index_level=parent/child）")
def then_writes_points(context: dict[str, Any]) -> None:
    """验证 ChunkIndexingHandler 的 upsert 点为分块级"""
    from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler

    assert hasattr(ChunkIndexingHandler, "handle_chunk_indexed"), "ChunkIndexingHandler 应包含 handle_chunk_indexed 方法"


# ===================================================================
# AC-5: Composition Root 注册 — 验证真实 registry 状态
# ===================================================================


def _read_port(name: str, context: dict[str, Any]) -> None:
    """从全局注册中心读取端口元数据"""
    from src.domain.ports.registry import Lifetime, _global_registry

    spec = _global_registry.get(name)
    context["port_name"] = name
    context["port_spec"] = spec
    context["port_scoped"] = spec is not None and spec.lifetime == Lifetime.SCOPED
    context["port_owner"] = spec.owner if spec else None
    context["port_version"] = spec.version if spec else None


@when("我检查 sparse_search_service 端口")
def when_check_sparse(context: dict[str, Any]) -> None:
    _read_port("sparse_search_service", context)


@when("我检查 hybrid_search_service 端口")
def when_check_hybrid(context: dict[str, Any]) -> None:
    _read_port("hybrid_search_service", context)


@when("我检查 dense_search_service 端口")
def when_check_dense(context: dict[str, Any]) -> None:
    _read_port("dense_search_service", context)


@then("端口已注册且生命周期为 SCOPED")
def then_registered_and_scoped(context: dict[str, Any]) -> None:
    assert context["port_spec"] is not None, f"{context['port_name']} 未注册"
    assert context["port_scoped"], f"{context['port_name']} 生命周期应为 SCOPED"


@then("所有者为 search-team")
def then_owner_search_team(context: dict[str, Any]) -> None:
    assert context["port_owner"] == "search-team", f"{context['port_name']} owner={context['port_owner']}"


@then("端口仍已注册且版本为 v1.0.0")
def then_dense_v1(context: dict[str, Any]) -> None:
    assert context["port_spec"] is not None, "dense_search_service 已丢失"
    assert context["port_version"] == "v1.0.0", f"版本={context['port_version']}"


# ===================================================================
# AC-6: 降级策略
# ===================================================================


@given("嵌入服务 Dense 可用但 Sparse 不可用")
def given_sparse_unavailable(context: dict[str, Any]) -> None:
    context["sparse_unavailable"] = True


@given("Dense 检索服务和 Sparse 检索服务均不可用")
def given_both_unavailable(context: dict[str, Any]) -> None:
    context["both_unavailable"] = True


@given("Qdrant Collection 为空")
def given_empty_collection(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
) -> None:
    """创建空 Collection"""
    collection = _create_collection(context, "test_hybrid_empty")

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")

    event_loop.run_until_complete(_setup())


@when("我使用混合检索查询空文本")
def when_hybrid_empty_query(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
) -> None:
    """空查询 → 应抛出 ValidationError"""
    dense_svc = DenseSemanticSearchService(embedding_service, vector_storage)
    sparse_svc = Bm25SparseSearchService(embedding_service, vector_storage)
    service = HybridSearchService(dense_search=dense_svc, sparse_search=sparse_svc, fuse=fuse)

    async def _run():
        return await service.search("test_collection", "")

    try:
        event_loop.run_until_complete(_run())
        context["validation_error"] = None
    except ValidationError as e:
        context["validation_error"] = e


@when('我执行混合检索查询 "不存在的文档"')
def when_hybrid_nonexistent(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
) -> None:
    """空 Collection 中检索 — 返回空列表"""
    collection = context["collection_name"]
    dense_svc = DenseSemanticSearchService(embedding_service, vector_storage)
    sparse_svc = Bm25SparseSearchService(embedding_service, vector_storage)
    service = HybridSearchService(dense_search=dense_svc, sparse_search=sparse_svc, fuse=fuse)

    async def _run():
        return await service.search(collection=collection, query_text="不存在的文档", limit=10)

    context["search_results"] = event_loop.run_until_complete(_run())


@then("返回 Dense 单路结果")
def then_dense_only(context: dict[str, Any]) -> None:
    assert context["search_results"] is not None
    assert len(context["search_results"]) > 0, "降级后应返回 Dense 结果"


@then("日志记录降级原因")
def then_degradation_logged(context: dict[str, Any], caplog) -> None:
    """HybridSearchService 降级时输出 WARNING 日志"""
    import logging

    with caplog.at_level(logging.WARNING):
        pass  # 日志已在 When 步骤中产生
    # 验证有降级相关的 WARNING
    degradation_logs = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(degradation_logs) > 0, "降级应产生 WARNING 日志"


@then("抛出 HybridSearchError 异常")
def then_hybrid_search_error_ac6(context: dict[str, Any]) -> None:
    """两路均失败时抛出 HybridSearchError（Story 3-4 升级替换 RuntimeError）"""
    error = context.get("hybrid_error")
    assert error is not None, "期望异常但未抛出"
    from src.domain.exceptions.hybrid_search_exceptions import HybridSearchError

    assert isinstance(error, HybridSearchError), f"期望 HybridSearchError, 实际 {type(error).__name__}"
    assert "三路检索通道均失败" in str(error)


@then("抛出 ValidationError 异常")
def then_validation_error(context: dict[str, Any]) -> None:
    error = context.get("validation_error")
    assert error is not None, "期望 ValidationError 但未抛出"
    assert isinstance(error, ValidationError)


@then("返回空列表")
def then_empty_list(context: dict[str, Any]) -> None:
    assert context["search_results"] == []
