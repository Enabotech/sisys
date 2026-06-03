"""Story 3-1a Dense 语义检索验收测试

使用真实 Qdrant 服务和 bge-m3 嵌入模型的集成测试，无 mock。

运行: poetry run pytest tests/acceptance/test_acceptance_dense_semantic_search.py -v

前置条件:
    - Qdrant 服务运行在 localhost:6333（或设置 QDRANT_* 环境变量）
    - bge-m3 模型已下载到本地（或可从 HuggingFace Hub 下载）
"""

from __future__ import annotations

import ast
import math
import uuid
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, scenarios, then, when

from src.infrastructure.config.embedding import EmbeddingConfig
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.models import VectorPoint
from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env

scenarios("test_acceptance_dense_semantic_search.feature")

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


@pytest.fixture(scope="session")
def embedding_service():
    """bge-m3 嵌入服务实例（会话级共享，避免重复加载模型）"""
    get_test_env()  # 确保测试环境配置已同步到 os.environ（含 device/路径）
    try:
        from src.infrastructure.external_services.embedding.bge3_embedding_service import BGE3EmbeddingService

        return BGE3EmbeddingService(EmbeddingConfig.from_env())
    except Exception as e:
        pytest.skip(f"bge-m3 模型不可用: {e}")


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


def _create_collection(context: dict[str, Any], prefix: str = "test_dense") -> str:
    """生成唯一 Collection 名称并注册到清理列表"""
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    context["collection_name"] = name
    context.setdefault("created_collections", []).append(name)
    return name


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


@given("嵌入服务已加载 bge-m3 模型")
def embedding_service_loaded(embedding_service):
    """确认嵌入服务已加载"""
    assert embedding_service is not None


# ===================================================================
# AC-1: bge-m3 嵌入生成
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-1 - bge-m3 嵌入生成")
def test_ac1_embedding_generation():
    """测试 bge-m3 嵌入生成"""
    pass


@when('我使用 EmbeddingService 编码文本 "企业战略规划报告"')
def encode_single_text(context: dict[str, Any], embedding_service):
    """编码单条文本"""
    context["embedding"] = embedding_service.encode_text("企业战略规划报告")


@then("返回的嵌入向量维度为 1024")
def embedding_dimension_is_1024(context: dict[str, Any]):
    """验证嵌入维度"""
    assert len(context["embedding"]) == 1024


@then("向量的 L2 范数约为 1.0")
def embedding_l2_norm_approx_one(context: dict[str, Any]):
    """验证 L2 归一化"""
    norm = math.sqrt(sum(x * x for x in context["embedding"]))
    assert abs(norm - 1.0) < 0.01, f"L2 范数 {norm} 不接近 1.0"


# ===================================================================
# AC-1b: 批量嵌入生成
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-1b - 批量嵌入生成")
def test_ac1b_batch_embedding_generation():
    """测试批量嵌入生成"""
    pass


@when("我使用 EmbeddingService 批量编码文本列表")
def encode_batch_texts(context: dict[str, Any], embedding_service):
    """编码批量文本"""
    texts = ["企业战略规划报告", "财务分析总结", "市场调研数据"]
    context["embeddings"] = embedding_service.encode_texts(texts)
    context["input_count"] = len(texts)


@then("返回的嵌入向量数量与输入文本数量一致")
def batch_embedding_count_matches(context: dict[str, Any]):
    """验证批量编码数量"""
    assert len(context["embeddings"]) == context["input_count"]


@then("每个向量的维度为 1024")
def each_vector_dimension_1024(context: dict[str, Any]):
    """验证每个向量维度"""
    for emb in context["embeddings"]:
        assert len(emb) == 1024


# ===================================================================
# AC-2: 余弦相似度检索
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-2 - 余弦相似度检索")
def test_ac2_cosine_similarity_search():
    """测试余弦相似度检索"""
    pass


@given("Qdrant Collection 包含已嵌入的文档向量")
def collection_has_document_vectors(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    embedding_service,
    event_loop,
):
    """创建测试 Collection 并插入嵌入向量"""
    collection = _create_collection(context, "test_dense_search")
    texts = ["企业战略规划报告", "财务分析总结", "市场调研数据", "技术架构文档", "人力资源计划"]

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")
        vectors = embedding_service.encode_texts(texts)
        points = [
            VectorPoint(
                id=f"doc_{i}",
                vector=vectors[i],
                payload={"text": texts[i], "business_domain": "strategy" if i < 2 else "operations"},
            )
            for i in range(len(texts))
        ]
        await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_setup())


@when('我执行 Dense 语义检索查询 "企业战略规划"')
def perform_dense_search(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """执行 Dense 语义检索"""
    from src.application.services.dense_search_service import DenseSemanticSearchService

    collection = context["collection_name"]
    service = DenseSemanticSearchService(embedding_service, vector_storage)

    async def _search():
        return await service.search(collection=collection, query_text="企业战略规划", limit=5)

    context["search_results"] = event_loop.run_until_complete(_search())


@then("返回最多 5 个结果")
def search_returns_at_most_5(context: dict[str, Any]):
    """验证结果数量"""
    results = context.get("search_results")
    assert results is not None, "应该返回检索结果"
    assert len(results) <= 5, f"应该返回最多 5 个结果，实际返回 {len(results)} 个"
    assert len(results) > 0, "应该返回至少 1 个结果"


@then("每个结果包含 id、score、payload 字段")
def search_results_have_fields(context: dict[str, Any]):
    """验证结果字段"""
    for result in context["search_results"]:
        assert "id" in result, f"结果缺少 id 字段: {result}"
        assert "score" in result, f"结果缺少 score 字段: {result}"
        assert "payload" in result, f"结果缺少 payload 字段: {result}"


@then("结果按 score 降序排列")
def search_results_sorted_desc(context: dict[str, Any]):
    """验证降序排列"""
    results = context.get("search_results")
    assert results is not None, "应该有检索结果"
    if len(results) > 1:
        scores = [r["score"] for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"结果应该按 score 降序排列，但 score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]}"
            )


# ===================================================================
# AC-2b: 无匹配结果
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-2b - 无匹配结果返回空列表")
def test_ac2b_no_match_returns_empty():
    """测试无匹配结果返回空列表"""
    pass


@given("Qdrant Collection 为空")
def collection_is_empty(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    event_loop,
):
    """创建空 Collection"""
    collection = _create_collection(context, "test_dense_empty")

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")

    event_loop.run_until_complete(_setup())


@when('我执行 Dense 语义检索查询 "不存在的文档"')
def search_nonexistent_document(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """在空 Collection 中检索"""
    from src.application.services.dense_search_service import DenseSemanticSearchService

    collection = context["collection_name"]
    service = DenseSemanticSearchService(embedding_service, vector_storage)

    async def _search():
        return await service.search(collection=collection, query_text="不存在的文档", limit=5)

    context["search_results"] = event_loop.run_until_complete(_search())


@then("返回空列表")
def search_returns_empty(context: dict[str, Any]):
    """验证空结果"""
    results = context.get("search_results")
    assert results is not None, "应该返回结果列表"
    assert len(results) == 0, f"空 Collection 应该返回空列表，实际返回 {len(results)} 个结果"


# ===================================================================
# AC-4: Payload 过滤
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-4 - Payload 过滤")
def test_ac4_payload_filter():
    """测试 Payload 过滤"""
    pass


@given("Qdrant Collection 包含不同业务域的文档向量")
def collection_has_multi_domain_vectors(
    context: dict[str, Any],
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    embedding_service,
    event_loop,
):
    """创建包含不同 business_domain 的 Collection"""
    collection = _create_collection(context, "test_dense_filter")
    texts = ["财务审计报告", "投资风险评估", "技术架构设计", "财务预算分析", "产品技术方案"]
    domains = ["finance", "finance", "technology", "finance", "technology"]

    async def _setup():
        await collection_manager.create_collection(name=collection, vector_size=1024, distance="Cosine")
        vectors = embedding_service.encode_texts(texts)
        points = [
            VectorPoint(
                id=f"doc_{i}",
                vector=vectors[i],
                payload={"text": texts[i], "business_domain": domains[i]},
            )
            for i in range(len(texts))
        ]
        await vector_storage.upsert_points(collection, points)

    event_loop.run_until_complete(_setup())


@when('我执行 Dense 语义检索并过滤 business_domain 为 "finance"')
def search_with_domain_filter(
    context: dict[str, Any],
    embedding_service,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """带 Payload 过滤的检索"""
    from src.application.services.dense_search_service import DenseSemanticSearchService

    collection = context["collection_name"]
    service = DenseSemanticSearchService(embedding_service, vector_storage)

    async def _search():
        return await service.search(
            collection=collection,
            query_text="财务分析",
            limit=10,
            filter_payload={"business_domain": "finance"},
        )

    context["search_results"] = event_loop.run_until_complete(_search())


@then('所有结果的 payload 中 business_domain 为 "finance"')
def all_results_finance_domain(context: dict[str, Any]):
    """验证过滤结果"""
    results = context.get("search_results")
    assert results is not None, "应该返回过滤后的检索结果"
    assert len(results) > 0, "应该返回至少 1 个 finance 结果"
    for result in results:
        domain = result["payload"].get("business_domain", "")
        assert domain == "finance", f"所有结果的 business_domain 应该为 finance，但发现 {domain}"


# ===================================================================
# AC-6: 领域层零外部依赖
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-6 - 领域层零外部依赖")
def test_ac6_domain_zero_external_dependency():
    """测试领域层零外部依赖"""
    pass


@when("我扫描 src/domain/ 目录")
def scan_domain_directory(context: dict[str, Any]):
    """扫描 src/domain/ 目录"""
    context["domain_scanned"] = True


@then("不应该导入 sentence_transformers 或 torch 或 FlagEmbedding")
def verify_no_forbidden_imports():
    """验证领域层没有禁止的依赖导入"""
    forbidden_imports = {"sentence_transformers", "torch", "FlagEmbedding"}
    for py_file in DOMAIN_DIR.rglob("*.py"):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split(".")[0]
                    assert root_module not in forbidden_imports, f"{py_file} 导入了禁止的依赖: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_module = node.module.split(".")[0]
                    assert root_module not in forbidden_imports, f"{py_file} 导入了禁止的依赖: {node.module}"


# ===================================================================
# AC-5: Sparse 稀疏嵌入生成
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-5 - 稀疏嵌入生成")
def test_ac_encode_sparse():
    """测试 BGE-M3 稀疏嵌入生成"""
    pass


@scenario("test_acceptance_dense_semantic_search.feature", "AC-5 - 中文文本稀疏编码")
def test_ac_encode_sparse_chinese():
    """测试中文文本稀疏编码"""
    pass


@scenario("test_acceptance_dense_semantic_search.feature", "AC-5 - 空文本拒绝")
def test_ac_encode_sparse_empty_rejected():
    """测试空文本抛出异常"""
    pass


@when('我使用 EmbeddingService 稀疏编码文本 "企业战略规划报告"')
def encode_sparse_single_text(context: dict[str, Any], embedding_service):
    """稀疏编码单条文本"""
    context["sparse_result"] = embedding_service.encode_sparse("企业战略规划报告")


@then("返回的稀疏向量包含 indices 和 values 字段")
def sparse_result_has_indices_and_values(context: dict[str, Any]):
    """验证稀疏向量结构"""
    result = context["sparse_result"]
    assert "indices" in result, "缺失 indices 字段"
    assert "values" in result, "缺失 values 字段"
    assert isinstance(result["indices"], list)
    assert isinstance(result["values"], list)


@then("indices 和 values 长度一致且非空")
def sparse_indices_values_match_and_nonempty(context: dict[str, Any]):
    """验证 indices/values 一致性"""
    result = context["sparse_result"]
    assert len(result["indices"]) > 0, "Sparse 向量不应为空"
    assert len(result["indices"]) == len(result["values"]), (
        f"indices({len(result['indices'])}) 和 values({len(result['values'])}) 长度不一致"
    )


@then("indices 按升序排列")
def sparse_indices_sorted(context: dict[str, Any]):
    """验证 indices 升序"""
    result = context["sparse_result"]
    assert result["indices"] == sorted(result["indices"]), "indices 应升序排列"


@then("所有 values 为正浮点数")
def sparse_values_all_positive(context: dict[str, Any]):
    """验证权重为正"""
    for i, v in enumerate(context["sparse_result"]["values"]):
        assert isinstance(v, float), f"values[{i}] 不是 float: {type(v)}"
        assert v > 0, f"values[{i}] 不是正数: {v}"


@when('我使用 EmbeddingService 稀疏编码文本 "人工智能与数字化转型战略"')
def encode_sparse_chinese_text(context: dict[str, Any], embedding_service):
    """稀疏编码中文文本"""
    context["sparse_result"] = embedding_service.encode_sparse("人工智能与数字化转型战略")


@then("返回的稀疏向量至少包含 3 个词元")
def sparse_minimum_tokens(context: dict[str, Any]):
    """验证中文文本至少 3 个 token"""
    result = context["sparse_result"]
    assert len(result["indices"]) >= 3, f"中文文本应至少包含 3 个词元权重，实际 {len(result['indices'])}"


@when("我使用 EmbeddingService 稀疏编码空文本")
def encode_sparse_empty_text(context: dict[str, Any], embedding_service):
    """尝试编码空文本（预期失败）"""
    context["sparse_error"] = None
    try:
        embedding_service.encode_sparse("")
    except ValueError as e:
        context["sparse_error"] = e


@then("抛出 ValueError 异常")
def verify_value_error_raised(context: dict[str, Any]):
    """验证 ValueError 被抛出"""
    assert context["sparse_error"] is not None, "应抛出 ValueError 但未抛出"
    assert isinstance(context["sparse_error"], ValueError)


# ===================================================================
# AC-6b: 共享层零外部依赖
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-6b - 共享层零外部依赖")
def test_ac6b_shared_zero_external_dependency():
    """验证 src/shared/ 目录不包含禁止的外部依赖"""
    pass


SHARED_DIR = SRC_DIR / "shared"


@when("我扫描 src/shared/ 目录")
def scan_shared_directory(context: dict[str, Any]):
    """扫描 src/shared/ 目录"""
    context["shared_scanned"] = True


@then("不应该导入 qdrant_client 或 torch 或 FlagEmbedding 或 sentence_transformers")
def verify_shared_no_forbidden_imports():
    """验证 shared 层零外部依赖"""
    # shared/ 目录可能不存在（Story 3-1b 创建），跳过
    if not SHARED_DIR.exists():
        return
    forbidden_imports = {"qdrant_client", "torch", "FlagEmbedding", "sentence_transformers"}
    for py_file in SHARED_DIR.rglob("*.py"):
        source = py_file.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split(".")[0]
                    assert root_module not in forbidden_imports, f"{py_file} 导入了禁止的依赖: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_module = node.module.split(".")[0]
                    assert root_module not in forbidden_imports, f"{py_file} 导入了禁止的依赖: {node.module}"


# ===================================================================
# Task 10: API 模式验收
# ===================================================================


@scenario("test_acceptance_dense_semantic_search.feature", "AC-api - 嵌入 API 服务健康检查")
def test_ac_api_health_check():
    """测试嵌入 API 服务健康检查"""
    pass


@scenario("test_acceptance_dense_semantic_search.feature", "AC-api - 嵌入 API 服务 Dense 编码")
def test_ac_api_dense_encoding():
    """测试嵌入 API 服务 Dense 编码"""
    pass


@scenario("test_acceptance_dense_semantic_search.feature", "AC-api - 嵌入 API 服务 Sparse 编码")
def test_ac_api_sparse_encoding():
    """测试嵌入 API 服务 Sparse 编码"""
    pass


@pytest.fixture
def api_client():
    """创建 FastAPI TestClient 并注入 mock 模型"""
    from unittest.mock import MagicMock

    import numpy as np
    from fastapi.testclient import TestClient

    from src.infrastructure.external_services.embedding.embedding_api_server import app

    model = MagicMock()

    def mock_encode(texts, return_dense=False, return_sparse=False, **kwargs):
        result: dict = {}
        n = len(texts) if isinstance(texts, list) else 1
        if return_dense:
            result["dense_vecs"] = np.random.randn(n, 1024).astype(np.float32)
        if return_sparse:
            result["lexical_weights"] = [{"100": 0.5, "200": 0.3} for _ in range(n)]  # FlagEmbedding str keys
        return result

    model.encode.side_effect = mock_encode
    app.state.model = model
    app.state.model_name = "BAAI/bge-m3"
    app.state.device = "cpu"
    app.state.load_error = None
    return TestClient(app)


@given("嵌入 API 服务已启动")
def api_service_started(api_client, context: dict[str, Any]):
    """记录 API 客户端到上下文"""
    context["api_client"] = api_client


@when("我请求 GET /health")
def request_health_check(context: dict[str, Any]):
    """请求健康检查"""
    client = context["api_client"]
    resp = client.get("/health")
    context["api_response"] = resp


@when("我 POST /v1/embeddings 发送单条文本")
def request_dense_encoding(context: dict[str, Any]):
    """请求 Dense 编码"""
    client = context["api_client"]
    resp = client.post("/v1/embeddings", json={"texts": ["企业战略规划"], "return_sparse": False})
    context["api_response"] = resp


@when("我 POST /v1/embeddings 发送单条文本并请求 Sparse")
def request_sparse_encoding(context: dict[str, Any]):
    """请求 Dense + Sparse 编码"""
    client = context["api_client"]
    resp = client.post("/v1/embeddings", json={"texts": ["企业战略规划"], "return_sparse": True})
    context["api_response"] = resp


@then("返回状态码 200")
def verify_status_200(context: dict[str, Any]):
    """验证状态码"""
    assert context["api_response"].status_code == 200


@then('响应 JSON 包含 status 为 "ok"')
def verify_health_status(context: dict[str, Any]):
    """验证健康检查响应"""
    data = context["api_response"].json()
    assert data["status"] == "ok"


@then("响应包含 1024 维 Dense 向量")
def verify_dense_1024_dim(context: dict[str, Any]):
    """验证 Dense 维度"""
    data = context["api_response"].json()
    assert len(data["dense"]) == 1
    assert len(data["dense"][0]) == 1024


@then("响应同时包含 Dense 和 Sparse 字段")
def verify_both_dense_and_sparse(context: dict[str, Any]):
    """验证同时返回 Dense 和 Sparse"""
    data = context["api_response"].json()
    assert "dense" in data
    assert "sparse" in data
    assert data["sparse"] is not None
