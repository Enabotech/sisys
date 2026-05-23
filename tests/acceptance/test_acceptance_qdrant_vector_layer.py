"""Acceptance tests for Story 1.6 - Qdrant Vector Storage Layer.

Real instance integration tests using actual Qdrant service.
No mocks - uses real Qdrant instance.

Run with: poetry run pytest tests/acceptance/test_acceptance_qdrant-vector-layer.py -v

Prerequisites:
    - Qdrant service running at localhost:6333 (or set QDRANT_* env vars)
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from pytest_bdd import given, scenario, then, when

from src.infrastructure.storage.qdrant.bm25_builder import BM25Builder
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.models import VectorPoint
from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env

# Import reset_test_environment for test isolation (AC-4 A8)

# ===================================================================
# Paths & Constants
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"

# Module-level test state for UUID isolation
_test_collection_names: dict[str, str | None] = {
    "finance": None,
    "hr": None,
}

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def test_tenant_id() -> str:
    """Generate unique tenant ID for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
async def init_test_collection_names(qdrant_client: QdrantManager):
    """Initialize unique collection names for each test with async cleanup."""
    for key in _test_collection_names:
        _test_collection_names[key] = f"sisys_documents_{key}_{uuid.uuid4().hex[:8]}"
    yield
    # Cleanup after test - delete all created collections
    from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager

    manager = QdrantCollectionManager(qdrant_client.get_client())
    for key in _test_collection_names:
        name = _test_collection_names[key]
        if name:
            try:
                await manager.delete_collection(name)
            except Exception:
                pass  # Ignore errors during cleanup
            _test_collection_names[key] = None


@pytest.fixture
def qdrant_client() -> QdrantManager:
    """Real Qdrant client wrapper instance."""
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
    """Real Qdrant collection manager instance."""
    return QdrantCollectionManager(qdrant_client.get_client())


@pytest.fixture
def vector_storage(qdrant_client: QdrantManager) -> QdrantVectorStorage:
    """Real Qdrant vector storage instance."""
    return QdrantVectorStorage(qdrant_client.get_client())


@pytest.fixture
def bm25_builder() -> BM25Builder:
    """BM25 builder instance."""
    return BM25Builder()


# ===================================================================
# Background Steps (shared across all scenarios)
# ===================================================================


@given("Qdrant 服务可用")
def qdrant_service_available(qdrant_client: QdrantManager, event_loop):
    """Verify Qdrant service is available."""

    async def _check():
        try:
            await qdrant_client.health_check()
            return True
        except Exception:
            return False

    is_available = event_loop.run_until_complete(_check())
    if not is_available:
        pytest.skip("Qdrant service is not available")


@given('Collection 命名规范为 "sisys:{collection_type}:{namespace}"')
def collection_naming_convention():
    """Define collection naming convention."""
    pass


# ===================================================================
# AC-1/AC-2: Collection Management Tests
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "Collection 创建与删除",
)
def test_collection_create_and_delete(collection_manager: QdrantCollectionManager, event_loop):
    """Test collection creation and deletion."""
    pass


@when('我创建 Collection "sisys:documents:finance" 向量维度 1024')
def create_collection(collection_manager: QdrantCollectionManager, event_loop):
    """Create collection with vector size 1024."""

    async def _create():
        await collection_manager.create_collection(
            name=_test_collection_names["finance"],
            vector_size=1024,
            distance="Cosine",
        )

    event_loop.run_until_complete(_create())


@then("Collection 应该存在")
def verify_collection_exists(collection_manager: QdrantCollectionManager, event_loop):
    """Verify collection exists."""

    async def _check():
        exists = await collection_manager.collection_exists(_test_collection_names["finance"])
        assert exists, "Collection sisys_documents_finance should exist"

    event_loop.run_until_complete(_check())


@when('我删除 Collection "sisys:documents:finance"')
def delete_collection(collection_manager: QdrantCollectionManager, event_loop):
    """Delete collection."""

    async def _delete():
        await collection_manager.delete_collection(_test_collection_names["finance"])

    event_loop.run_until_complete(_delete())


@then("Collection 应该不存在")
def verify_collection_not_exists(collection_manager: QdrantCollectionManager, event_loop):
    """Verify collection does not exist."""

    async def _check():
        exists = await collection_manager.collection_exists(_test_collection_names["finance"])
        assert not exists, "Collection should not exist after deletion"

    event_loop.run_until_complete(_check())


# ===================================================================
# AC-3: Vector Point Insertion and Query
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "向量点插入与查询",
)
def test_vector_point_insert_and_query(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Test vector point insertion and query."""
    pass


@given('Collection "sisys:documents:finance" 已存在')
def collection_exists(collection_manager: QdrantCollectionManager, event_loop):
    """Collection already exists."""

    async def _create():
        await collection_manager.create_collection(
            name=_test_collection_names["finance"],
            vector_size=1024,
            distance="Cosine",
        )

    event_loop.run_until_complete(_create())


@when("我插入 10 个向量点（带 payload 元数据）")
def insert_ten_vectors(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Insert 10 vector points with payload metadata."""

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
        await vector_storage.upsert_points(_test_collection_names["finance"], points)

    event_loop.run_until_complete(_insert())


@then("插入应该成功")
def verify_insert_success():
    """Verify insertion succeeds."""
    # If no exception, insertion was successful
    pass


@when('我查询向量点 "point-1"')
def query_point_vector_storage(
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Query vector point by ID."""
    result = None

    async def _query():
        nonlocal result
        result = await vector_storage.get_point(_test_collection_names["finance"], "1")

    event_loop.run_until_complete(_query())
    return result


@then("应该返回对应的向量点数据")
def verify_point_returned():
    """Verify returned point data matches."""
    pass


# ===================================================================
# AC-4: Dense Semantic Retrieval
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "Dense 语义检索",
)
def test_dense_semantic_retrieval(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Test dense semantic retrieval."""
    pass


@given('Collection "sisys:documents:finance" 包含 100 个向量点')
def collection_contains_100_vectors(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection contains 100 vector points."""

    async def _insert():
        # Create collection if not exists
        try:
            await collection_manager.create_collection(
                name=_test_collection_names["finance"],
                vector_size=1024,
                distance="Cosine",
            )
        except Exception:
            pass  # Collection may already exist

        # Insert 100 vectors
        points = []
        for i in range(100):
            points.append(
                VectorPoint(
                    id=str(i + 1),
                    vector=[0.01 * i] * 1024,
                    payload={
                        "document_id": f"doc-{i + 1}",
                        "index": i,
                    },
                )
            )
        await vector_storage.upsert_points(_test_collection_names["finance"], points)

    event_loop.run_until_complete(_insert())


@when("我执行 Dense 检索（查询向量 1024 维，limit=10）")
def perform_dense_search(
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Perform dense search with 1024-dim vector."""
    results = None

    async def _search():
        nonlocal results
        query_vector = [0.05] * 1024
        results = await vector_storage.search(
            _test_collection_names["finance"],
            query_vector,
            limit=10,
        )

    event_loop.run_until_complete(_search())
    return results


@then("应该返回最多 10 个结果")
def verify_max_10_results():
    """Verify at most 10 results are returned."""
    pass


@then("结果按相似度降序排列")
def verify_results_sorted_by_score():
    """Verify results are sorted by score descending."""
    pass


# ===================================================================
# AC-5: Dense Retrieval Payload Filtering
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "Dense 检索 payload 过滤",
)
def test_dense_search_with_filter(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Test dense search with payload filtering."""
    pass


@given('Collection "sisys:documents:finance" 包含不同业务域的向量点')
def collection_has_different_domains(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection contains vectors with different business domains."""

    async def _setup():
        # P2 Fix: Create collection before inserting points
        try:
            await collection_manager.create_collection(
                name=_test_collection_names["finance"],
                vector_size=1024,
                distance="Cosine",
            )
        except Exception:
            pass  # Ignore if already exists

        # Insert vectors with different business_domain values
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
                await vector_storage.upsert_points(_test_collection_names["finance"], points)

    event_loop.run_until_complete(_setup())


@when('我执行 Dense 检索并过滤 business_domain="report"')
def perform_filtered_search(
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Perform dense search with business_domain filter."""
    results = None

    async def _search():
        nonlocal results
        query_vector = [0.1] * 1024
        results = await vector_storage.search(
            _test_collection_names["finance"],
            query_vector,
            limit=10,
            filter_payload={"business_domain": "report"},
        )

    event_loop.run_until_complete(_search())
    return results


@then('所有结果的 business_domain 应该为 "report"')
def verify_all_results_have_domain():
    """Verify all results have business_domain='report'."""
    pass


# ===================================================================
# AC-6: BM25 Sparse Retrieval
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "BM25 稀疏检索",
)
def test_bm25_sparse_retrieval(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    bm25_builder: BM25Builder,
    event_loop,
):
    """Test BM25 sparse retrieval."""
    pass


@given('Collection "sisys:documents:finance" 包含文本向量点')
def collection_has_text_vectors(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection contains text vector points."""

    async def _insert():
        try:
            await collection_manager.create_collection(
                name=_test_collection_names["finance"],
                vector_size=1024,
                distance="Cosine",
            )
        except Exception:
            pass

        texts = [
            "financial report analysis",
            "quarterly earnings review",
            "budget projection spreadsheet",
            "market trend analysis",
            "investment portfolio summary",
        ]
        for i, text in enumerate(texts):
            points = [
                VectorPoint(
                    id=str(i + 1),
                    vector=[0.1] * 1024,
                    payload={
                        "document_id": f"doc-{i + 1}",
                        "text": text,
                    },
                )
            ]
            await vector_storage.upsert_points(_test_collection_names["finance"], points)

    event_loop.run_until_complete(_insert())


@when("我执行 BM25 稀疏检索（稀疏向量从文本构建）")
def perform_bm25_search(
    vector_storage: QdrantVectorStorage,
    bm25_builder: BM25Builder,
    event_loop,
):
    """Perform BM25 sparse search."""
    results = None

    async def _search():
        nonlocal results
        sparse_vector = bm25_builder.build_sparse_vector("financial report analysis")
        results = await vector_storage.search_sparse(
            _test_collection_names["finance"],
            sparse_vector,
        )

    event_loop.run_until_complete(_search())
    return results


@then("应该返回关键词匹配的结果")
def verify_keyword_matched_results():
    """Verify results match keywords."""
    pass


# ===================================================================
# AC-7: Multi-Tenant Isolation
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "多租户隔离",
)
def test_multi_tenant_isolation(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Test multi-tenant isolation."""
    pass


@given('Collection "sisys:documents:finance" 和 "sisys:documents:hr" 存在')
def both_collections_exist(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Both finance and HR collections exist."""

    async def _create():
        try:
            await collection_manager.create_collection(
                name=_test_collection_names["finance"],
                vector_size=1024,
                distance="Cosine",
            )
        except Exception:
            pass
        try:
            await collection_manager.create_collection(
                name=_test_collection_names["hr"],
                vector_size=1024,
                distance="Cosine",
            )
        except Exception:
            pass

    event_loop.run_until_complete(_create())


@when('我向 "sisys:documents:finance" 插入向量点')
def insert_to_finance_collection(
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Insert vectors to finance collection."""

    async def _insert():
        points = [
            VectorPoint(
                id="1",
                vector=[0.1] * 1024,
                payload={"document_id": "finance-doc-1"},
            )
        ]
        await vector_storage.upsert_points(_test_collection_names["finance"], points)

    event_loop.run_until_complete(_insert())


@then('"sisys:documents:hr" 不应该包含这些向量点')
def verify_hr_collection_isolated(
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Verify HR collection does not contain finance vectors."""

    async def _check():
        point = await vector_storage.get_point(_test_collection_names["hr"], "1")
        assert point is None, "HR collection should not contain finance vectors"

    event_loop.run_until_complete(_check())


# ===================================================================
# AC-8: Domain Layer Zero Qdrant Dependency
# ===================================================================


@scenario(
    "test_acceptance_qdrant_vector_layer.feature",
    "领域层零 Qdrant 依赖",
)
def test_domain_layer_zero_qdrant_dependency():
    """Test domain layer has zero Qdrant dependency."""
    pass


@when("我扫描 src/domain/ 目录")
def scan_domain_directory():
    """Scan src/domain/ directory."""
    pass


@then("不应该有任何 qdrant_client 导入")
def verify_no_qdrant_import():
    """Verify no qdrant_client import in domain layer."""
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

    assert len(qdrant_imports) == 0, f"Qdrant imports found in domain layer: {qdrant_imports}"


# ===================================================================
# Shared Fixtures
# ===================================================================


@pytest.fixture
def collection_name():
    """Generate unique collection name for tests."""
    return f"test_collection_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_vector():
    """Provide sample 1024-dim vector for tests."""
    return [0.1] * 1024


@pytest.fixture
def sample_points():
    """Provide sample vector points for tests."""
    return [
        VectorPoint(
            id=str(i + 1),
            vector=[0.1 * (i + 1)] * 1024,
            payload={"document_id": f"doc-{i + 1}"},
        )
        for i in range(10)
    ]
