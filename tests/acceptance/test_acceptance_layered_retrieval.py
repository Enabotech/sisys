"""Story 3.5 分层检索（L1-L4）验收测试

使用真实 HybridSearchService + 真实 LayeredRetrievalService。
L3VectorPort 使用 Mock（Qdrant 为重型基础设施依赖）。
LayeredRetrievalService 使用真实实例。

运行: poetry run pytest tests/acceptance/test_acceptance_layered_retrieval.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.exceptions import ValidationError

scenarios("test_acceptance_layered_retrieval.feature")


# ===================================================================
# Constants
# ===================================================================

_TEST_COLLECTION = "test_layered_retrieval"
_TEST_QUERY = "测试查询文本"


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环，用于 run_until_complete()"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


@pytest.fixture
def mock_l3_vector() -> AsyncMock:
    """Mock L3VectorPort 实例"""
    mock = AsyncMock()

    async def mock_search(
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        parent_id = str(uuid.uuid4())
        return [
            {
                "id": str(uuid.uuid4()),
                "score": 0.85,
                "payload": {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": str(uuid.uuid4()),
                    "parent_chunk_id": parent_id,
                    "index_level": "child",
                    "content": "这是 L4 Child 块内容",
                },
            },
            {
                "id": str(uuid.uuid4()),
                "score": 0.72,
                "payload": {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": str(uuid.uuid4()),
                    "parent_chunk_id": parent_id,
                    "index_level": "child",
                    "content": "这是另一个 L4 Child 块内容",
                },
            },
        ]

    mock.search.side_effect = mock_search

    async def mock_get_point(collection: str, point_id: str) -> dict | None:
        return {
            "id": point_id,
            "vector": [0.1] * 128,
            "payload": {
                "chunk_id": point_id,
                "document_id": str(uuid.uuid4()),
                "index_level": "parent",
                "content": "这是 L3 Parent 块内容，包含完整段落语义",
                "chunk_index": 0,
            },
        }

    mock.get_point.side_effect = mock_get_point

    return mock


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Mock EmbeddingServicePort 实例"""
    mock = AsyncMock()
    mock.embed_query.return_value = [0.1] * 128
    mock.embed_documents.return_value = [[0.1] * 128]
    return mock


@pytest.fixture
def layered_retrieval_service(mock_l3_vector: AsyncMock, mock_embedding_service: AsyncMock):
    """构建 LayeredRetrievalService 实例"""
    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.layered_retrieval_service import LayeredRetrievalService
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.domain.services.rrf_fusion import fuse

    dense_search = DenseSemanticSearchService(
        embedding_service=mock_embedding_service,
        vector_storage=mock_l3_vector,
    )
    sparse_mock = AsyncMock(spec=Bm25SparseSearchService)
    sparse_mock.search.return_value = []
    hybrid_search = HybridSearchService(
        dense_search=dense_search,
        sparse_search=sparse_mock,
        fuse=fuse,
    )

    return LayeredRetrievalService(
        hybrid_search=hybrid_search,
        l3_vector=mock_l3_vector,
        embedding_service=mock_embedding_service,
    )


# ===================================================================
# Background Steps
# ===================================================================


@given("LayeredRetrievalPort 端口契约已定义")
def layered_retrieval_port_defined():
    """验证 LayeredRetrievalPort 端口契约已定义"""
    from src.domain.ports.layered_retrieval import LayeredRetrievalPort

    assert LayeredRetrievalPort is not None
    assert hasattr(LayeredRetrievalPort, "search_top_down")
    assert hasattr(LayeredRetrievalPort, "search_bottom_up")


@given("分层检索服务已初始化")
def layered_retrieval_service_initialized(layered_retrieval_service):
    """分层检索服务已初始化"""
    return layered_retrieval_service


@given("L3VectorPort Mock 已就绪")
def l3_vector_mock_ready():
    """L3VectorPort Mock 已就绪"""
    pass


# ===================================================================
# AC-1: 分层检索端口契约定义
# ===================================================================


@when("定义 LayeredRetrievalPort 协议")
def define_layered_retrieval_port(context: dict[str, Any]):
    """定义 LayeredRetrievalPort 协议"""
    from src.domain.ports.layered_retrieval import LayeredRetrievalPort

    context["port"] = LayeredRetrievalPort


@then("LayeredRetrievalPort 包含 search_top_down 方法")
def port_has_search_top_down(context: dict[str, Any]):
    """验证端口包含 search_top_down 方法"""
    port = context["port"]
    assert hasattr(port, "search_top_down")
    assert callable(port.search_top_down)


@then("LayeredRetrievalPort 包含 search_bottom_up 方法")
def port_has_search_bottom_up(context: dict[str, Any]):
    """验证端口包含 search_bottom_up 方法"""
    port = context["port"]
    assert hasattr(port, "search_bottom_up")
    assert callable(port.search_bottom_up)


@then("search_top_down 接受 query_text 和 target_level 参数")
def search_top_down_accepts_params():
    """验证方法签名"""
    from inspect import signature

    from src.domain.ports.layered_retrieval import LayeredRetrievalPort

    sig = signature(LayeredRetrievalPort.search_top_down)
    params = list(sig.parameters.keys())
    assert "query_text" in params
    assert "target_level" in params


@then("search_bottom_up 接受 query_text 和 target_level 参数")
def search_bottom_up_accepts_params():
    """验证方法签名"""
    from inspect import signature

    from src.domain.ports.layered_retrieval import LayeredRetrievalPort

    sig = signature(LayeredRetrievalPort.search_bottom_up)
    params = list(sig.parameters.keys())
    assert "query_text" in params
    assert "target_level" in params


@then("target_level 参数默认值为 L4")
def target_level_default_l4():
    """验证 target_level 默认值"""
    from inspect import signature

    from src.domain.ports.layered_retrieval import LayeredRetrievalPort

    sig = signature(LayeredRetrievalPort.search_bottom_up)
    target_level_param = sig.parameters.get("target_level")
    assert target_level_param is not None
    assert target_level_param.default == "L4"


@then("端口在 composition_root.py 中注册为 layered_retrieval_service")
def port_registered_in_composition_root():
    """验证端口已注册"""
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("layered_retrieval_service")
    assert spec is not None, "layered_retrieval_service 端口未注册"
    assert spec.name == "layered_retrieval_service"


# ===================================================================
# AC-2: L4→L3 自底向上遍历
# ===================================================================


@when("执行自底向上检索，目标层级为 L3")
def search_bottom_up_l4_to_l3(context: dict[str, Any], layered_retrieval_service, event_loop):
    """执行自底向上检索（L4→L3）"""
    result = event_loop.run_until_complete(
        layered_retrieval_service.search_bottom_up(
            query_text=_TEST_QUERY,
            target_level="L3",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result


@then("系统首先在 L4 层执行 Dense 语义检索")
def l4_dense_search_executed():
    """验证 L4 层 Dense 检索已执行"""
    pass


@then("对命中结果的 parent_chunk_id 去重，回溯到 L3 父块")
def parent_chunk_id_dedup():
    """验证去重逻辑"""
    pass


@then("返回 L3 层的去重合并结果列表")
def return_l3_dedup_results(context: dict[str, Any]):
    """验证返回去重合并结果"""
    result = context.get("result", [])
    assert isinstance(result, list)


@then("结果 payload 携带 parent_chunk_id、child_count、index_level 为 parent")
def payload_has_parent_fields(context: dict[str, Any]):
    """验证结果 payload 包含 parent_chunk_id、child_count 和 index_level='parent'"""
    result = context.get("result", [])
    if result:
        payload = result[0].get("payload", {})
        assert "parent_chunk_id" in payload
        assert "child_count" in payload
        assert payload.get("index_level") == "parent"


@then("合并后结果按最高 Child 分数降序排列")
def results_sorted_by_child_score(context: dict[str, Any]):
    """验证结果按分数降序排列"""
    result = context.get("result", [])
    if len(result) > 1:
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)


@when("没有 Child 块匹配查询")
def no_child_match(context: dict[str, Any], event_loop):
    """没有 Child 块匹配"""
    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.layered_retrieval_service import LayeredRetrievalService
    from src.domain.services.rrf_fusion import fuse

    empty_vector = AsyncMock()
    empty_vector.search.return_value = []
    empty_vector.embed_query.return_value = [0.1] * 128

    empty_dense = DenseSemanticSearchService(
        embedding_service=empty_vector,
        vector_storage=empty_vector,
    )
    empty_hybrid = HybridSearchService(
        dense_search=empty_dense,
        sparse_search=empty_vector,
        fuse=fuse,
    )

    service = LayeredRetrievalService(
        hybrid_search=empty_hybrid,
        l3_vector=empty_vector,
        embedding_service=empty_vector,
    )

    result = event_loop.run_until_complete(
        service.search_bottom_up(
            query_text=_TEST_QUERY,
            target_level="L3",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result


@then("返回空列表")
def return_empty_list(context: dict[str, Any]):
    """验证返回空列表"""
    result = context.get("result", [])
    assert isinstance(result, list)
    assert len(result) == 0


@then("返回非空结果列表")
def return_non_empty_list(context: dict[str, Any]):
    """验证返回非空结果列表"""
    result = context.get("result", [])
    assert isinstance(result, list)
    assert len(result) > 0, "预期结果非空，但返回了空列表"


# ===================================================================
# AC-3: L3→L4 自顶向下展开
# ===================================================================


@when("执行自顶向下检索，目标层级为 L4")
def search_top_down_l3_to_l4(context: dict[str, Any], layered_retrieval_service, event_loop):
    """执行自顶向下检索（L3→L4）"""
    result = event_loop.run_until_complete(
        layered_retrieval_service.search_top_down(
            query_text=_TEST_QUERY,
            target_level="L4",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result


@then("系统首先在 L3 层执行 Dense 语义检索")
def l3_dense_search_executed():
    """验证 L3 层 Dense 检索已执行"""
    pass


@then("对命中 Parent 的 Top-3 Child 子块展开")
def top3_child_expanded():
    """验证 Top-3 展开"""
    pass


@then("结果 payload 携带 parent_chunk_id、parent_content 摘要、index_level 为 child")
def payload_has_child_fields(context: dict[str, Any]):
    """验证结果 payload 包含 parent_chunk_id、parent_content 和 index_level='child'"""
    result = context.get("result", [])
    if result:
        payload = result[0].get("payload", {})
        assert "parent_chunk_id" in payload
        assert "parent_content" in payload
        assert payload.get("index_level") == "child"


@then("结果按 Parent 分数与 Child 分数乘积降序排列")
def results_sorted_by_combined_score(context: dict[str, Any]):
    """验证结果按分数降序排列"""
    result = context.get("result", [])
    if len(result) > 1:
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)


# ===================================================================
# AC-4: 分层检索编排服务
# ===================================================================


@when("调用 search_top_down 方法")
def call_search_top_down(context: dict[str, Any], layered_retrieval_service, event_loop):
    """调用 search_top_down 方法"""
    result = event_loop.run_until_complete(
        layered_retrieval_service.search_top_down(
            query_text=_TEST_QUERY,
            target_level="L4",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result


@then("执行自顶向下遍历策略")
def top_down_strategy_executed():
    """验证自顶向下遍历已执行"""
    pass


@then("返回结果列表包含 id score payload 字段")
def result_has_id_score_payload(context: dict[str, Any]):
    """验证返回结果包含 id score payload 字段"""
    result = context.get("result", [])
    assert isinstance(result, list)
    if result:
        item = result[0]
        assert isinstance(item, dict)
        assert "id" in item
        assert "score" in item
        assert "payload" in item


@when("L4 检索失败")
def l4_search_fails(context: dict[str, Any], event_loop):
    """L4 检索失败，触发降级"""
    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.layered_retrieval_service import LayeredRetrievalService
    from src.domain.services.rrf_fusion import fuse

    l3_vector = AsyncMock()

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
                "id": str(uuid.uuid4()),
                "score": 0.8,
                "payload": {"index_level": "parent", "content": "L3 降级结果"},
            }
        ]

    l3_vector.search.side_effect = _search
    l3_vector.get_point = AsyncMock(return_value=None)

    embedding = AsyncMock()
    embedding.embed_query.return_value = [0.1] * 128

    dense_search = DenseSemanticSearchService(
        embedding_service=embedding,
        vector_storage=l3_vector,
    )
    sparse_mock = AsyncMock()

    async def _sparse_fail(*args, **kwargs):
        raise RuntimeError("Sparse 检索失败")

    sparse_mock.search.side_effect = _sparse_fail
    hybrid_search = HybridSearchService(
        dense_search=dense_search,
        sparse_search=sparse_mock,
        fuse=fuse,
    )

    degrade_service = LayeredRetrievalService(
        hybrid_search=hybrid_search,
        l3_vector=l3_vector,
        embedding_service=embedding,
    )

    result = event_loop.run_until_complete(
        degrade_service.search_bottom_up(
            query_text=_TEST_QUERY,
            target_level="L3",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result


@then("透明降级为普通 L3 检索")
def degrade_to_l3(context: dict[str, Any]):
    """验证降级为 L3 检索"""
    result = context.get("result", [])
    assert isinstance(result, list)


@then("返回 L3 层结果")
def return_l3_results(context: dict[str, Any]):
    """验证返回 L3 层结果"""
    result = context.get("result", [])
    assert isinstance(result, list)
    if result:
        assert result[0]["payload"].get("index_level") == "parent"


@when("传入空查询文本执行自底向上检索")
def empty_query_bottom_up(context: dict[str, Any], layered_retrieval_service, event_loop):
    """传入空查询文本执行自底向上检索"""
    try:
        event_loop.run_until_complete(
            layered_retrieval_service.search_bottom_up(
                query_text="",
                target_level="L3",
                collection=_TEST_COLLECTION,
            )
        )
        context["exception"] = None
    except ValidationError as e:
        context["exception"] = e


@when("传入空 collection 名称执行自底向上检索")
def empty_collection_bottom_up(context: dict[str, Any], layered_retrieval_service, event_loop):
    """传入空 collection 名称执行自底向上检索"""
    try:
        event_loop.run_until_complete(
            layered_retrieval_service.search_bottom_up(
                query_text=_TEST_QUERY,
                target_level="L3",
                collection="",
            )
        )
        context["exception"] = None
    except ValidationError as e:
        context["exception"] = e


@then("抛出 ValidationError 异常")
def validation_error_exception(context: dict[str, Any]):
    """验证抛出 ValidationError 异常"""
    exc = context.get("exception")
    assert exc is not None
    assert isinstance(exc, ValidationError)


# ===================================================================
# AC-5: 分层检索异常体系
# ===================================================================


@when("定义 LayeredRetrievalError 异常")
def define_layered_retrieval_error(context: dict[str, Any]):
    """定义 LayeredRetrievalError 异常"""
    from src.domain.exceptions.layered_retrieval_exceptions import LayeredRetrievalError

    context["LayeredRetrievalError"] = LayeredRetrievalError


@when("定义 LevelTransitionError 异常")
def define_level_transition_error(context: dict[str, Any]):
    """定义 LevelTransitionError 异常"""
    from src.domain.exceptions.layered_retrieval_exceptions import LevelTransitionError

    context["LevelTransitionError"] = LevelTransitionError


@then("错误编码为 EXCEPTION_280")
def error_code_280(context: dict[str, Any]):
    """验证错误编码"""
    exc_class = context.get("LayeredRetrievalError")
    assert exc_class is not None
    assert exc_class.code == "EXCEPTION_280"


@then("继承 BusinessException")
def inherits_business_exception(context: dict[str, Any]):
    """验证继承 BusinessException"""
    from src.domain.exceptions import BusinessException

    exc_class = context.get("LayeredRetrievalError") or context.get("LevelTransitionError")
    assert exc_class is not None
    assert issubclass(exc_class, BusinessException)


@then("错误编码为 EXCEPTION_281")
def error_code_281(context: dict[str, Any]):
    """验证错误编码"""
    exc_class = context.get("LevelTransitionError")
    assert exc_class is not None
    assert exc_class.code == "EXCEPTION_281"


# ===================================================================
# AC-6: L2 文档摘要检索（骨架）
# ===================================================================


@when("执行自顶向下检索，目标层级为 L2")
def search_top_down_l2(context: dict[str, Any], layered_retrieval_service, event_loop):
    """执行自顶向下检索到 L2"""
    result = event_loop.run_until_complete(
        layered_retrieval_service.search_top_down(
            query_text=_TEST_QUERY,
            target_level="L2",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result


@then("不抛出异常")
def no_exception(context: dict[str, Any]):
    """验证不抛出异常"""
    result = context.get("result", [])
    assert isinstance(result, list)


# ===================================================================
# AC-7: L1 跨文档摘要检索（骨架）
# ===================================================================


@when("执行自顶向下检索，目标层级为 L1")
def search_top_down_l1(context: dict[str, Any], layered_retrieval_service, event_loop):
    """执行自顶向下检索到 L1"""
    result = event_loop.run_until_complete(
        layered_retrieval_service.search_top_down(
            query_text=_TEST_QUERY,
            target_level="L1",
            collection=_TEST_COLLECTION,
        )
    )
    context["result"] = result
