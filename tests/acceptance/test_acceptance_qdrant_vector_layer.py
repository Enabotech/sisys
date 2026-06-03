"""Qdrant 向量存储层验收测试

使用真实 Qdrant 服务实例的集成测试，无 mock。

运行: poetry run pytest tests/acceptance/test_acceptance_qdrant_vector_layer.py -v

前置条件:
    - Qdrant 服务运行在 localhost:6333（或设置 QDRANT_* 环境变量）
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, scenarios, then, when

from src.infrastructure.storage.qdrant.bm25_builder import BM25Builder
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.models import VectorPoint
from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env

scenarios("test_acceptance_qdrant_vector_layer.feature")

# ===================================================================
# 常量
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"


# ===================================================================
# Fixtures
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
def bm25_builder() -> BM25Builder:
    """BM25 构建器实例"""
    return BM25Builder()


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


def _ensure_finance_collection(context: dict[str, Any]) -> str:
    """确保 context 中存在 finance_collection 名称"""
    if "finance_collection" not in context:
        name = f"sisys_documents_finance_{uuid.uuid4().hex[:8]}"
        context["finance_collection"] = name
        context.setdefault("created_collections", []).append(name)
    return str(context["finance_collection"])


# ===================================================================
# Background Steps
# ===================================================================


@given("Qdrant 服务可用")
def qdrant_service_available(qdrant_client: QdrantManager, event_loop):
    """验证 Qdrant 服务可用"""

    async def _check():
        try:
            await qdrant_client.health_check()
            return True
        except Exception:
            return False

    is_available = event_loop.run_until_complete(_check())
    if not is_available:
        pytest.skip("Qdrant 服务不可用")


@given('Collection 命名规范为 "sisys:{collection_type}:{namespace}"')
def collection_naming_convention(context: dict[str, Any]):
    """定义 Collection 命名规范"""
    context["naming_convention"] = "sisys:{collection_type}:{namespace}"


# ===================================================================
# AC-1: Collection 创建与删除
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-1 - Collection 创建与删除")
def test_ac1_collection_create_and_delete():
    """测试 Collection 创建与删除"""
    pass


@when('我创建 Collection "sisys:documents:finance" 向量维度 1024')
def create_finance_collection(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """创建 finance Collection"""
    name = _ensure_finance_collection(context)

    async def _create():
        await collection_manager.create_collection(name=name, vector_size=1024, distance="Cosine")

    event_loop.run_until_complete(_create())


@then("Collection 应该存在")
def verify_collection_exists(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """验证 Collection 存在"""

    async def _check():
        name = context["finance_collection"]
        exists = await collection_manager.collection_exists(name)
        assert exists, f"Collection {name} 应该存在"

    event_loop.run_until_complete(_check())


@when('我删除 Collection "sisys:documents:finance"')
def delete_finance_collection(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """删除 finance Collection"""

    async def _delete():
        await collection_manager.delete_collection(context["finance_collection"])

    event_loop.run_until_complete(_delete())


@then("Collection 应该不存在")
def verify_collection_not_exists(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """验证 Collection 不存在"""

    async def _check():
        name = context["finance_collection"]
        exists = await collection_manager.collection_exists(name)
        assert not exists, f"Collection {name} 不应该存在"

    event_loop.run_until_complete(_check())


# ===================================================================
# AC-2: 向量点插入与查询
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-2 - 向量点插入与查询")
def test_ac2_vector_point_insert_and_query():
    """测试向量点插入与查询"""
    pass


@given('Collection "sisys:documents:finance" 已存在')
def ensure_finance_collection_exists(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """确保 finance Collection 已存在"""
    name = _ensure_finance_collection(context)

    async def _create():
        await collection_manager.create_collection(name=name, vector_size=1024, distance="Cosine")

    event_loop.run_until_complete(_create())


@when("我插入 10 个向量点（带 payload 元数据）")
def insert_ten_vectors(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """插入 10 个带 payload 元数据的向量点"""
    collection = context["finance_collection"]

    async def _insert():
        points = []
        for i in range(10):
            points.append(
                VectorPoint(
                    id=str(i + 1),
                    vector=[0.1 * (i + 1)] * 1024,
                    payload={
                        "document_id": f"doc-{i + 1}",
                        "chunk_id": f"chunk-{i + 1}",
                        "text": f"Document {i + 1} content",
                    },
                )
            )
        await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_insert())
    context["insert_success"] = True


@then("插入应该成功")
def verify_insert_success(context: dict[str, Any]):
    """验证向量点插入成功"""
    assert context.get("insert_success"), "向量点插入应该成功"


@when('我查询向量点 "point-1"')
def query_point_by_id(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """查询 ID 为 1 的向量点"""
    collection = context["finance_collection"]

    async def _query():
        return await vector_storage.get_point(collection, "1")

    result = event_loop.run_until_complete(_query())
    context["query_result"] = result


@then("应该返回对应的向量点数据")
def verify_point_returned(context: dict[str, Any]):
    """验证返回的向量点数据"""
    result = context.get("query_result")
    assert result is not None, "应该返回 ID 为 1 的向量点数据"


# ===================================================================
# AC-3: Dense 语义检索
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-3 - Dense 语义检索")
def test_ac3_dense_semantic_retrieval():
    """测试 Dense 语义检索"""
    pass


@given('Collection "sisys:documents:finance" 包含 100 个向量点')
def collection_contains_100_vectors(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection 包含 100 个向量点"""
    collection = _ensure_finance_collection(context)

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")

        points = []
        for i in range(100):
            points.append(
                VectorPoint(
                    id=str(i + 1),
                    vector=[0.01 * i] * 1024,
                    payload={"document_id": f"doc-{i + 1}", "index": i},
                )
            )
        await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_setup())


@when("我执行 Dense 检索（查询向量 1024 维，limit=10）")
def perform_dense_search(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """执行 Dense 语义检索"""
    collection = context["finance_collection"]

    async def _search():
        query_vector = [0.05] * 1024
        return await vector_storage.search(collection, query_vector, limit=10)

    results = event_loop.run_until_complete(_search())
    context["search_results"] = results


@then("应该返回最多 10 个结果")
def verify_max_10_results(context: dict[str, Any]):
    """验证返回最多 10 个结果"""
    results = context.get("search_results")
    assert results is not None, "应该返回检索结果"
    assert len(results) <= 10, f"应该返回最多 10 个结果，实际返回 {len(results)} 个"


@then("结果按相似度降序排列")
def verify_results_sorted_by_score(context: dict[str, Any]):
    """验证结果按相似度降序排列"""
    results = context.get("search_results")
    assert results is not None, "应该有检索结果"
    if len(results) > 1:
        scores = [r["score"] for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"结果应该按相似度降序排列，但 score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"
            )


# ===================================================================
# AC-4: Dense 检索 payload 过滤
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-4 - Dense 检索 payload 过滤")
def test_ac4_dense_search_with_filter():
    """测试 Dense 检索 payload 过滤"""
    pass


@given('Collection "sisys:documents:finance" 包含不同业务域的向量点')
def collection_has_different_domains(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection 包含不同业务域的向量点"""
    collection = _ensure_finance_collection(context)

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")

        for domain in ["report", "analysis", "summary"]:
            for i in range(10):
                points = [
                    VectorPoint(
                        id=f"{domain}-{i}",
                        vector=[0.1] * 1024,
                        payload={
                            "document_id": f"doc-{domain}-{i}",
                            "business_domain": domain,
                        },
                    )
                ]
                await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_setup())


@when('我执行 Dense 检索并过滤 business_domain="report"')
def perform_filtered_search(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """执行带 payload 过滤的 Dense 检索"""
    collection = context["finance_collection"]

    async def _search():
        query_vector = [0.1] * 1024
        return await vector_storage.search(
            collection,
            query_vector,
            limit=10,
            filter_payload={"business_domain": "report"},
        )

    results = event_loop.run_until_complete(_search())
    context["filtered_results"] = results


@then('所有结果的 business_domain 应该为 "report"')
def verify_all_results_have_report_domain(context: dict[str, Any]):
    """验证所有结果的 business_domain 为 report"""
    results = context.get("filtered_results")
    assert results is not None, "应该返回过滤后的检索结果"
    for r in results:
        domain = r["payload"].get("business_domain", "")
        assert domain == "report", f"所有结果的 business_domain 应该为 report，但发现 {domain}"


# ===================================================================
# AC-5: BM25 稀疏检索
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-5 - BM25 稀疏检索")
def test_ac5_bm25_sparse_retrieval():
    """测试 BM25 稀疏检索"""
    pass


@given('Collection "sisys:documents:finance" 包含文本向量点')
def collection_has_text_vectors(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    qdrant_client: QdrantManager,
    bm25_builder: BM25Builder,
    event_loop,
):
    """Collection 包含文本向量点（含稀疏向量索引和数据）"""
    collection = _ensure_finance_collection(context)
    raw_client = qdrant_client.get_client()

    async def _setup():
        from qdrant_client.models import PointStruct, SparseVectorParams
        from qdrant_client.models import SparseVector as QdrantSparseVector

        sparse_config = {"sparse": SparseVectorParams()}
        await collection_manager.create_collection(
            name=collection,
            vector_size=1024,
            distance="Cosine",
            sparse_vectors_config=sparse_config,
        )

        texts = [
            "financial report analysis",
            "quarterly earnings review",
            "budget projection spreadsheet",
            "market trend analysis",
            "investment portfolio summary",
        ]

        points = []
        for i, text in enumerate(texts):
            sparse_vec = bm25_builder.build_sparse_vector(text)
            points.append(
                PointStruct(
                    id=i + 1,
                    vector={
                        "": [0.1] * 1024,
                        "sparse": QdrantSparseVector(indices=sparse_vec.indices, values=sparse_vec.values),
                    },
                    payload={"document_id": f"doc-{i + 1}", "text": text},
                )
            )

        await raw_client.upsert(collection_name=collection, points=points)

    event_loop.run_until_complete(_setup())


@when("我执行 BM25 稀疏检索（稀疏向量从文本构建）")
def perform_bm25_search(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    bm25_builder: BM25Builder,
    event_loop,
):
    """执行 BM25 稀疏检索"""
    collection = context["finance_collection"]

    async def _search():
        sparse_vector = bm25_builder.build_sparse_vector("financial report analysis")
        return await vector_storage.search_sparse(collection, sparse_vector)

    results = event_loop.run_until_complete(_search())
    context["bm25_results"] = results


@then("应该返回关键词匹配的结果")
def verify_keyword_matched_results(context: dict[str, Any]):
    """验证返回关键词匹配的结果"""
    results = context.get("bm25_results")
    assert results is not None, "应该返回 BM25 检索结果"
    assert len(results) > 0, "应该返回至少一条关键词匹配结果"


# ===================================================================
# AC-6: 多租户隔离
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-6 - 多租户隔离")
def test_ac6_multi_tenant_isolation():
    """测试多租户隔离"""
    pass


@given('Collection "sisys:documents:finance" 和 "sisys:documents:hr" 存在')
def both_collections_exist(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """finance 和 hr Collection 均存在"""
    finance = _ensure_finance_collection(context)

    hr_name = f"sisys_documents_hr_{uuid.uuid4().hex[:8]}"
    context["hr_collection"] = hr_name
    context.setdefault("created_collections", []).append(hr_name)

    async def _create():
        await collection_manager.create_collection(name=finance, vector_size=1024, distance="Cosine")
        await collection_manager.create_collection(name=hr_name, vector_size=1024, distance="Cosine")

    event_loop.run_until_complete(_create())


@when('我向 "sisys:documents:finance" 插入向量点')
def insert_to_finance_collection(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """向 finance Collection 插入向量点"""
    collection = context["finance_collection"]

    async def _insert():
        points = [
            VectorPoint(
                id="1",
                vector=[0.1] * 1024,
                payload={"document_id": "finance-doc-1"},
            )
        ]
        await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_insert())


@then('"sisys:documents:hr" 不应该包含这些向量点')
def verify_hr_collection_isolated(
    context: dict[str, Any],
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """验证 hr Collection 不包含 finance 向量点"""
    hr_collection = context["hr_collection"]

    async def _check():
        return await vector_storage.get_point(hr_collection, "1")

    point = event_loop.run_until_complete(_check())
    assert point is None, "hr Collection 不应该包含 finance 的向量点"


# ===================================================================
# AC-7: 领域层零 Qdrant 依赖
# ===================================================================


@scenario("test_acceptance_qdrant_vector_layer.feature", "AC-7 - 领域层零 Qdrant 依赖")
def test_ac7_domain_zero_qdrant_dependency():
    """测试领域层零 Qdrant 依赖"""
    pass


@when("我扫描 src/domain/ 目录")
def scan_domain_directory(context: dict[str, Any]):
    """扫描 src/domain/ 目录"""
    context["domain_scanned"] = True


@then("不应该有任何 qdrant_client 导入")
def verify_no_qdrant_import():
    """验证领域层没有 qdrant 导入"""
    import ast

    qdrant_imports = []
    for py_file in DOMAIN_DIR.rglob("*.py"):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "qdrant" in alias.name.lower():
                            qdrant_imports.append(py_file)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "qdrant" in node.module.lower():
                        qdrant_imports.append(py_file)
        except SyntaxError:
            pass

    assert len(qdrant_imports) == 0, f"领域层发现 Qdrant 导入: {qdrant_imports}"
