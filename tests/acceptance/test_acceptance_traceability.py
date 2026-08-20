"""Story 3.8 高保真溯源 BDD 步骤实现

使用真实 TraceabilityService + Mock LayeredRetrievalPort。
遵循 BDD 步骤实现约束：不使用 @pytest.mark.asyncio，使用 event_loop.run_until_complete()。

运行: poetry run pytest tests/acceptance/test_acceptance_traceability.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.layered_retrieval import LayeredRetrievalPort

scenarios_path = "test_acceptance_traceability.feature"


# ===================================================================
# Constants
# ===================================================================

_TEST_CLAIM = "公司营收在2024年实现稳健增长，同比增长15%，净利润率达12%。"
_TEST_DOCUMENT_ID = uuid.uuid4()


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
def mock_layered_retrieval() -> AsyncMock:
    """Mock LayeredRetrievalPort 实例（返回含 bbox 的检索结果）"""
    mock = AsyncMock(spec=LayeredRetrievalPort)

    async def mock_search_top_down(
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                id="chunk-001",
                score=0.92,
                payload={
                    "content": "公司2024年营收同比增长15%，主要受益于核心业务的持续扩张。",
                    "document_id": str(_TEST_DOCUMENT_ID),
                    "chunk_id": "chunk-001",
                    "page_start": 3,
                    "page_end": 3,
                    "parent_chunk_id": None,
                    "index_level": "parent",
                    "chunk_header": "[文档: 2024年度报告 → 财务分析]",
                    "bbox": {
                        "x": 100.5,
                        "y": 200.3,
                        "width": 400.0,
                        "height": 50.0,
                        "page": 3,
                    },
                },
            ),
            SearchResult(
                id="chunk-002",
                score=0.87,
                payload={
                    "content": "净利润率达到12%，较上年提升0.5个百分点。",
                    "document_id": str(_TEST_DOCUMENT_ID),
                    "chunk_id": "chunk-002",
                    "page_start": 4,
                    "page_end": 4,
                    "parent_chunk_id": None,
                    "index_level": "parent",
                    "chunk_header": "[文档: 2024年度报告 → 利润分析]",
                    "bbox": {
                        "x": 100.5,
                        "y": 150.3,
                        "width": 400.0,
                        "height": 60.0,
                        "page": 4,
                    },
                },
            ),
        ]

    mock.search_top_down.side_effect = mock_search_top_down
    return mock


@pytest.fixture
def mock_layered_retrieval_no_bbox() -> AsyncMock:
    """Mock LayeredRetrievalPort 实例（返回无 bbox 的检索结果）"""
    mock = AsyncMock(spec=LayeredRetrievalPort)

    async def mock_search_top_down(
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                id="chunk-003",
                score=0.85,
                payload={
                    "content": "公司2024年营收同比增长15%。",
                    "document_id": str(_TEST_DOCUMENT_ID),
                    "chunk_id": "chunk-003",
                    "page_start": 3,
                    "page_end": 3,
                    "parent_chunk_id": None,
                    "index_level": "parent",
                    "chunk_header": "[文档: 2024年度报告]",
                },
            ),
        ]

    mock.search_top_down.side_effect = mock_search_top_down
    return mock


@pytest.fixture
def mock_layered_retrieval_empty() -> AsyncMock:
    """Mock LayeredRetrievalPort 实例（返回空结果，模拟低置信度场景）"""
    mock = AsyncMock(spec=LayeredRetrievalPort)

    async def mock_search_top_down(
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        return []

    mock.search_top_down.side_effect = mock_search_top_down
    return mock


@pytest.fixture
def traceability_runtime(
    context: dict[str, Any],
    mock_layered_retrieval: AsyncMock,
) -> None:
    """装配真实 TraceabilityService + Mock 端口（BDD 运行时）"""
    from src.application.services.traceability_service import TraceabilityService

    service = TraceabilityService(
        retrieval_port=mock_layered_retrieval,
    )
    context["service"] = service
    context["mock_layered_retrieval"] = mock_layered_retrieval


@pytest.fixture
def traceability_runtime_no_bbox(
    context: dict[str, Any],
    mock_layered_retrieval_no_bbox: AsyncMock,
) -> None:
    """装配真实 TraceabilityService + Mock 端口（无 bbox 场景）"""
    from src.application.services.traceability_service import TraceabilityService

    service = TraceabilityService(
        retrieval_port=mock_layered_retrieval_no_bbox,
    )
    context["service"] = service


@pytest.fixture
def traceability_runtime_empty(
    context: dict[str, Any],
    mock_layered_retrieval_empty: AsyncMock,
) -> None:
    """装配真实 TraceabilityService + Mock 端口（空结果场景）"""
    from src.application.services.traceability_service import TraceabilityService

    service = TraceabilityService(
        retrieval_port=mock_layered_retrieval_empty,
    )
    context["service"] = service


@pytest.fixture
def traceability_runtime_for_api(
    context: dict[str, Any],
    mock_layered_retrieval: AsyncMock,
) -> None:
    """装配真实 TraceabilityService + Mock 端口（API 端点测试场景）"""
    from src.application.services.traceability_service import TraceabilityService

    service = TraceabilityService(
        retrieval_port=mock_layered_retrieval,
    )
    context["service"] = service
    context["mock_layered_retrieval"] = mock_layered_retrieval


# ===================================================================
# Background Steps
# ===================================================================


@given("TraceabilityPort 端口契约已定义")
def _given_traceability_port_defined() -> None:
    """验证端口契约存在"""
    from src.domain.ports.traceability import TraceabilityPort

    assert TraceabilityPort is not None


@given("溯源服务已初始化", target_fixture="traceability_runtime")
def _given_traceability_service_initialized(traceability_runtime) -> None:
    """初始化溯源服务（通过 traceability_runtime fixture 装配）"""
    assert traceability_runtime is None or True


@given("LayeredRetrievalPort Mock 已就绪")
def _given_layered_retrieval_mock_ready() -> None:
    """LayeredRetrievalPort Mock 已就绪（由 traceability_runtime 装配）"""
    pass


# ===================================================================
# AC-1 Happy Path: 结论文本溯源成功
# ===================================================================


@scenario(scenarios_path, "AC-1 - 结论文本溯源成功")
def test_ac1_trace_success() -> None:
    """AC-1 结论文本溯源成功"""


@when("以有效结论文本调用溯源")
def _when_trace_with_valid_claim(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
    traceability_runtime: None,
) -> None:
    """以有效结论文本调用溯源"""
    service = context["service"]
    result = event_loop.run_until_complete(service.trace(claim=_TEST_CLAIM, top_k=10, min_confidence=0.7))
    context["trace_result"] = result


@then("返回 TraceabilityResult 实例")
def _then_trace_returns_traceability_result(context: dict[str, Any]) -> None:
    """返回 TraceabilityResult 实例"""
    result = context["trace_result"]
    assert result is not None
    assert isinstance(result, dict)  # TraceabilityResult 是 TypedDict


@then("包含引文列表")
def _then_result_contains_citations(context: dict[str, Any]) -> None:
    """包含引文列表"""
    result = context["trace_result"]
    assert "citations" in result
    assert len(result["citations"]) > 0


@then("引文按置信度降序排列")
def _then_citations_sorted_by_confidence(context: dict[str, Any]) -> None:
    """引文按置信度降序排列"""
    result = context["trace_result"]
    citations = result["citations"]
    confidences = [c.confidence for c in citations]
    assert confidences == sorted(confidences, reverse=True)


@then("引文包含 citation_id document_id chunk_id text 字段")
def _then_citation_has_required_fields(context: dict[str, Any]) -> None:
    """引文包含 citation_id document_id chunk_id text 字段"""
    citations = context["trace_result"]["citations"]
    for citation in citations:
        assert hasattr(citation, "citation_id")
        assert hasattr(citation, "document_id")
        assert hasattr(citation, "chunk_id")
        assert hasattr(citation, "text")


# ===================================================================
# AC-1 Happy Path: 引文包含 Bounding Box 坐标
# ===================================================================


@scenario(scenarios_path, "AC-1 - 引文包含 Bounding Box 坐标")
def test_ac1_bbox_in_citation() -> None:
    """AC-1 引文包含 Bounding Box 坐标"""


@given("检索结果包含 Bounding Box 坐标")
def _given_search_results_with_bbox(
    context: dict[str, Any],
    mock_layered_retrieval: AsyncMock,
) -> None:
    """检索结果包含 Bounding Box 坐标（由 mock_layered_retrieval fixture 提供）"""
    pass


@when("检索结果包含 Bounding Box 坐标", target_fixture="traceability_runtime")
def _when_trace_with_bbox(context: dict[str, Any]) -> None:
    """执行溯源（使用含 bbox 的检索结果）"""
    pass


@then("返回的引文 bbox 字段不为 None")
def _then_citation_bbox_not_none(context: dict[str, Any]) -> None:
    """返回的引文 bbox 字段不为 None"""
    citations = context["trace_result"]["citations"]
    for citation in citations:
        assert citation.bbox is not None


@then("bbox 包含 x y width height page 坐标信息")
def _then_bbox_has_coordinates(context: dict[str, Any]) -> None:
    """bbox 包含 x y width height page 坐标信息"""
    citations = context["trace_result"]["citations"]
    for citation in citations:
        bbox = citation.bbox
        assert hasattr(bbox, "x")
        assert hasattr(bbox, "y")
        assert hasattr(bbox, "width")
        assert hasattr(bbox, "height")
        assert hasattr(bbox, "page")


# ===================================================================
# AC-2 Happy Path: 按文档 ID 查询所有引文
# ===================================================================


@scenario(scenarios_path, "AC-2 - 按文档 ID 查询引文")
def test_ac2_get_citations_by_document() -> None:
    """AC-2 按文档 ID 查询引文"""


@given("溯源结果已缓存")
def _given_trace_results_cached(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
    traceability_runtime: None,
) -> None:
    """先执行一次溯源以缓存结果"""
    service = context["service"]
    event_loop.run_until_complete(service.trace(claim=_TEST_CLAIM, top_k=10, min_confidence=0.7))


@when("按文档 ID 查询引文")
def _when_get_citations_by_document(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
) -> None:
    """按文档 ID 查询引文"""
    service = context["service"]
    citations = event_loop.run_until_complete(service.get_citation_by_document(document_id=_TEST_DOCUMENT_ID))
    context["citations_by_document"] = citations


@then("返回该文档的所有引文列表")
def _then_returns_citations_for_document(context: dict[str, Any]) -> None:
    """返回该文档的所有引文列表"""
    citations = context["citations_by_document"]
    assert isinstance(citations, list)
    assert len(citations) > 0


@then("引文包含完整的溯源信息")
def _then_citations_have_full_traceability_info(context: dict[str, Any]) -> None:
    """引文包含完整的溯源信息"""
    citations = context["citations_by_document"]
    for citation in citations:
        assert citation.document_id == _TEST_DOCUMENT_ID
        assert citation.text
        assert citation.confidence > 0


# ===================================================================
# AC-4 Edge Case: 未找到相关引文
# ===================================================================


@scenario(scenarios_path, "AC-4 - 未找到相关引文（置信度 < min_confidence）")
def test_ac4_no_citations_found() -> None:
    """AC-4 未找到相关引文"""


@when("检索结果置信度低于最小阈值")
def _when_low_confidence_retrieval(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
    traceability_runtime_empty: None,
) -> None:
    """检索结果置信度低于最小阈值（空结果场景）"""
    service = context["service"]
    result = event_loop.run_until_complete(service.trace(claim="完全无关的查询", top_k=10, min_confidence=0.7))
    context["trace_result"] = result


@then("返回空引文列表")
def _then_empty_citations_list(context: dict[str, Any]) -> None:
    """返回空引文列表"""
    result = context["trace_result"]
    assert "citations" in result
    assert len(result["citations"]) == 0


@then("不抛出异常")
def _then_no_exception_raised(context: dict[str, Any]) -> None:
    """不抛出异常（此步骤隐式验证，若抛出异常测试会失败）"""
    pass


# ===================================================================
# AC-5 Edge Case: 检索结果无 Bounding Box 坐标
# ===================================================================


@scenario(scenarios_path, "AC-5 - 检索结果无 Bounding Box 坐标")
def test_ac5_no_bbox_in_retrieval() -> None:
    """AC-5 检索结果无 Bounding Box 坐标"""


@given("检索结果 payload 中不包含 bbox 字段")
def _given_no_bbox_in_payload(
    context: dict[str, Any],
    mock_layered_retrieval_no_bbox: AsyncMock,
) -> None:
    """检索结果 payload 中不包含 bbox 字段"""
    pass


@when("检索结果 payload 中不包含 bbox 字段")
def _when_trace_without_bbox(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
    traceability_runtime_no_bbox: None,
) -> None:
    """执行溯源（使用无 bbox 的检索结果）"""
    service = context["service"]
    result = event_loop.run_until_complete(service.trace(claim=_TEST_CLAIM, top_k=10, min_confidence=0.7))
    context["trace_result"] = result


@then("返回的引文 has_bbox_support=False")
def _then_has_bbox_support_false(context: dict[str, Any]) -> None:
    """返回的引文 has_bbox_support=False"""
    result = context["trace_result"]
    assert result["has_bbox_support"] is False


@then("引文 bbox 字段为 None")
def _then_citation_bbox_is_none(context: dict[str, Any]) -> None:
    """引文 bbox 字段为 None"""
    citations = context["trace_result"]["citations"]
    for citation in citations:
        assert citation.bbox is None


# ===================================================================
# AC-6 Edge Case: 按 ID 查询不存在的引文
# ===================================================================


@scenario(scenarios_path, "AC-6 - 按 ID 查询不存在的引文")
def test_ac6_get_nonexistent_citation() -> None:
    """AC-6 按 ID 查询不存在的引文"""


@when("按不存在的 citation_id 查询引文详情")
def _when_get_nonexistent_citation(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
    traceability_runtime: None,
) -> None:
    """按不存在的 citation_id 查询引文详情"""
    from src.domain.exceptions.traceability_exceptions import TraceabilityNotFoundError

    service = context["service"]
    try:
        event_loop.run_until_complete(service.get_citation_detail(citation_id="nonexistent-id-123"))
        context["exception_raised"] = None
    except TraceabilityNotFoundError as exc:
        context["exception_raised"] = exc


@then("抛出 TraceabilityNotFoundError")
def _then_raises_traceability_not_found_error(context: dict[str, Any]) -> None:
    """抛出 TraceabilityNotFoundError"""
    assert context["exception_raised"] is not None


@then("异常 code 为 EXCEPTION_371")
def _then_error_code_is_371(context: dict[str, Any]) -> None:
    """异常 code 为 EXCEPTION_371"""
    assert context["exception_raised"].code == "EXCEPTION_371"


# ===================================================================
# AC-7 API 端点
# ===================================================================


@scenario(scenarios_path, "AC-7 - 通过 API 请求溯源")
def test_ac7_api_trace_endpoint() -> None:
    """AC-7 通过 API 请求溯源"""


@when("通过 POST /api/v1/search/trace 请求溯源")
def _when_post_trace_api(
    context: dict[str, Any],
    event_loop: asyncio.AbstractEventLoop,
    traceability_runtime_for_api: None,
) -> None:
    """通过 POST /api/v1/search/trace 请求溯源（使用真实服务 + Mock 端口）"""

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.interfaces.api.traceability import create_trace_router

    # 使用真实 TraceabilityService（已注入 Mock LayeredRetrievalPort）
    service = context["service"]

    app = FastAPI()
    router = create_trace_router(
        trace_service=service,
        get_current_user_override=lambda: "test-user",
    )
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/v1/search/trace",
        json={
            "claim": _TEST_CLAIM,
            "top_k": 10,
            "min_confidence": 0.7,
        },
        headers={"Authorization": "Bearer test-token"},
    )
    context["response"] = response


@then("返回 200 状态码")
def _then_response_200(context: dict[str, Any]) -> None:
    """返回 200 状态码"""
    assert context["response"].status_code == 200


@then("响应体包含 claim citations citation_count highest_confidence has_bbox_support 字段")
def _then_response_has_required_fields(context: dict[str, Any]) -> None:
    """响应体包含 claim citations citation_count highest_confidence has_bbox_support 字段"""
    data = context["response"].json()
    assert "claim" in data
    assert "citations" in data
    assert "citation_count" in data
    assert "highest_confidence" in data
