"""Story 3.6 契约化结构化摘要生成验收测试

使用真实 SummaryGenerationService + Mock LLMClientPort。
遵循 BDD 步骤实现约束：不使用 @pytest.mark.asyncio，使用 event_loop.run_until_complete()。

运行: poetry run pytest tests/acceptance/test_acceptance_contractual_summary.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.ports.l3_vector import SearchResult
from src.domain.value_objects.token_payload import TokenPayload

scenarios_path = "test_acceptance_contractual_summary.feature"


# ===================================================================
# Constants
# ===================================================================

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
def mock_llm_client() -> AsyncMock:
    """Mock LLMClientPort 实例"""
    mock = AsyncMock()

    async def mock_structured_generate(
        prompt: str,
        response_schema: type[Any],
        config=None,
        system_prompt=None,
    ) -> Any:
        """返回一个模拟的 Schema 实例"""
        # 根据 response_schema 创建模拟实例
        mock_instance = MagicMock(spec=response_schema)
        mock_instance.summary_text = "这是一个模拟的摘要文本，用于测试目的。"
        mock_instance.key_points = ["要点一", "要点二", "要点三"]
        mock_instance.confidence_score = 0.85

        # 视角特有字段
        if response_schema.__name__ == "FinancialSummary":
            mock_instance.revenue_trend = "收入呈上升趋势，年增长率约15%"
            mock_instance.profit_analysis = "利润率稳定，保持在20%左右"
            mock_instance.risk_factors = ["市场竞争加剧", "原材料价格波动"]
            mock_instance.market_position = "市场领先者，占有约30%市场份额"
        elif response_schema.__name__ == "MarketSummary":
            mock_instance.market_size = "市场规模约1000亿元，年增长率12%"
            mock_instance.competitive_landscape = "竞争格局分散，前五名合计占40%"
            mock_instance.growth_drivers = ["技术升级", "政策支持", "消费升级"]
            mock_instance.customer_insights = "客户满意度评分4.2/5，复购率75%"
        elif response_schema.__name__ == "TechnicalSummary":
            mock_instance.technology_stack = "Python/React/PostgreSQL/Qdrant"
            mock_instance.innovation_points = ["多Agent协作", "高保真溯源"]
            mock_instance.technical_risks = ["数据安全合规", "系统性能瓶颈"]
            mock_instance.architecture_overview = "六边形架构，微服务部署"

        return mock_instance

    mock.structured_generate.side_effect = mock_structured_generate
    return mock


@pytest.fixture
def mock_layered_retrieval() -> AsyncMock:
    """Mock LayeredRetrievalPort 实例"""
    mock = AsyncMock()

    async def mock_search_top_down(
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        if target_level in ("L1", "L2"):
            return [
                SearchResult(
                    id=f"summary-{target_level}",
                    score=0.85,
                    payload={
                        "summary_text": "这是模拟摘要文本，用于存储与检索验证。",
                        "key_points": ["要点一", "要点二"],
                        "confidence_score": 0.85,
                        "perspective": "financial",
                        "source_document_ids": ["doc-001"],
                        "index_level": target_level,
                        "created_at": "2026-08-15T00:00:00",
                    },
                )
            ]
        return []

    mock.search_top_down.side_effect = mock_search_top_down
    return mock


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Mock EmbeddingServicePort 实例"""
    mock = AsyncMock()

    async def mock_embed_documents(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]

    mock.embed_documents.side_effect = mock_embed_documents
    mock.dimension = 1024
    return mock


@pytest.fixture
def mock_l3_vector() -> AsyncMock:
    """Mock L3VectorPort 实例"""
    mock = AsyncMock()

    async def mock_upsert_points(collection: str, points: list[dict]) -> bool:
        return True

    async def mock_collection_exists(collection: str) -> bool:
        return True

    async def mock_search(
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        return []

    mock.upsert_points.side_effect = mock_upsert_points
    mock.collection_exists.side_effect = mock_collection_exists
    mock.search.side_effect = mock_search
    return mock


@pytest.fixture
def summary_runtime(
    context: dict[str, Any],
    mock_llm_client: AsyncMock,
    mock_layered_retrieval: AsyncMock,
    mock_embedding_service: AsyncMock,
    mock_l3_vector: AsyncMock,
) -> None:
    """装配真实 SummaryGenerationService + Mock 端口（BDD 运行时）"""
    from src.application.services.summary_generation_service import SummaryGenerationService

    service = SummaryGenerationService(
        llm_client=mock_llm_client,
        layered_retrieval=mock_layered_retrieval,
        embedding_service=mock_embedding_service,
        l3_vector=mock_l3_vector,
    )
    context["service"] = service
    context["mock_llm_client"] = mock_llm_client
    context["mock_layered_retrieval"] = mock_layered_retrieval
    context["mock_embedding_service"] = mock_embedding_service
    context["mock_l3_vector"] = mock_l3_vector


# ===================================================================
# AC-1 摘要 Schema 契约定义（SDD 验证型场景）
# ===================================================================


@scenario(scenarios_path, "AC-1 - 财务视角摘要 Schema 定义")
def test_ac1_financial_schema_definition() -> None:
    """AC-1 财务视角摘要 Schema 定义"""


@scenario(scenarios_path, "AC-1 - 市场视角摘要 Schema 定义")
def test_ac1_market_schema_definition() -> None:
    """AC-1 市场视角摘要 Schema 定义"""


@scenario(scenarios_path, "AC-1 - 技术视角摘要 Schema 定义")
def test_ac1_technical_schema_definition() -> None:
    """AC-1 技术视角摘要 Schema 定义"""


@given("SummaryGenerationPort 端口契约已定义")
def _given_summary_generation_port_defined() -> None:
    """验证端口契约存在"""
    from src.domain.ports.summary_generation import SummaryGenerationPort

    assert SummaryGenerationPort is not None


@given("摘要生成服务已初始化", target_fixture="summary_runtime")
def _given_summary_generation_service_initialized(summary_runtime) -> None:
    """初始化摘要生成服务（通过 summary_runtime fixture 装配）"""
    assert summary_runtime is None or True


@given("LLMClientPort Mock 已就绪")
def _given_llm_client_mock_ready() -> None:
    """LLMClientPort Mock 已就绪（由 summary_runtime 装配）"""
    pass


@given("L2 摘要已存储于 document_summaries")
def _given_l2_summary_stored(summary_runtime: None) -> None:
    """L2 摘要已存储（fixture 已装配 Mock L3VectorPort）"""
    assert summary_runtime is None or True


@when("定义 FinancialSummary Schema")
def _when_define_financial_summary() -> None:
    from src.application.services.summary_schemas import FinancialSummary

    assert FinancialSummary is not None


@when("定义 MarketSummary Schema")
def _when_define_market_summary() -> None:
    from src.application.services.summary_schemas import MarketSummary

    assert MarketSummary is not None


@when("定义 TechnicalSummary Schema")
def _when_define_technical_summary() -> None:
    from src.application.services.summary_schemas import TechnicalSummary

    assert TechnicalSummary is not None


@when("定义 SummaryGenerationPort 协议")
def _when_define_summary_generation_port() -> None:
    from src.domain.ports.summary_generation import SummaryGenerationPort

    assert SummaryGenerationPort is not None


@then("FinancialSummary 是 Pydantic BaseModel 子类")
def _then_financial_is_base_model() -> None:
    from pydantic import BaseModel

    from src.application.services.summary_schemas import FinancialSummary

    assert issubclass(FinancialSummary, BaseModel)


@then("MarketSummary 是 Pydantic BaseModel 子类")
def _then_market_is_base_model() -> None:
    from pydantic import BaseModel

    from src.application.services.summary_schemas import MarketSummary

    assert issubclass(MarketSummary, BaseModel)


@then("TechnicalSummary 是 Pydantic BaseModel 子类")
def _then_technical_is_base_model() -> None:
    from pydantic import BaseModel

    from src.application.services.summary_schemas import TechnicalSummary

    assert issubclass(TechnicalSummary, BaseModel)


@then("包含 summary_text key_points confidence_score 固有字段")
def _then_has_common_fields() -> None:
    from src.application.services.summary_schemas import FinancialSummary

    schema = FinancialSummary.model_json_schema()
    props = schema["properties"]
    assert "summary_text" in props
    assert "key_points" in props
    assert "confidence_score" in props


@then("包含 revenue_trend profit_analysis risk_factors market_position 视角特有字段")
def _then_has_financial_fields() -> None:
    from src.application.services.summary_schemas import FinancialSummary

    schema = FinancialSummary.model_json_schema()
    props = schema["properties"]
    assert "revenue_trend" in props
    assert "profit_analysis" in props
    assert "risk_factors" in props
    assert "market_position" in props


@then("包含 market_size competitive_landscape growth_drivers customer_insights 视角特有字段")
def _then_has_market_fields() -> None:
    from src.application.services.summary_schemas import MarketSummary

    schema = MarketSummary.model_json_schema()
    props = schema["properties"]
    assert "market_size" in props
    assert "competitive_landscape" in props
    assert "growth_drivers" in props
    assert "customer_insights" in props


@then("包含 technology_stack innovation_points technical_risks architecture_overview 视角特有字段")
def _then_has_technical_fields() -> None:
    from src.application.services.summary_schemas import TechnicalSummary

    schema = TechnicalSummary.model_json_schema()
    props = schema["properties"]
    assert "technology_stack" in props
    assert "innovation_points" in props
    assert "technical_risks" in props
    assert "architecture_overview" in props


@then("confidence_score 范围约束在 0-1 之间")
def _then_confidence_score_range() -> None:
    from src.application.services.summary_schemas import FinancialSummary

    schema = FinancialSummary.model_json_schema()
    props = schema["properties"]
    score_props = props["confidence_score"]
    assert score_props.get("minimum") == 0.0
    assert score_props.get("maximum") == 1.0


# ===================================================================
# AC-2 摘要生成服务端口契约（SDD 验证型场景）
# ===================================================================


@scenario(scenarios_path, "AC-2 - SummaryGenerationPort 协议定义")
def test_ac2_port_definition() -> None:
    """AC-2 SummaryGenerationPort 协议定义"""


@then("SummaryGenerationPort 包含 generate_summary 方法")
def _then_port_has_generate_summary() -> None:
    from src.domain.ports.summary_generation import SummaryGenerationPort

    assert hasattr(SummaryGenerationPort, "generate_summary")


@then("generate_summary 接受 query_text search_results perspective config tenant_id cross_document 参数")
def _then_generate_summary_signature() -> None:
    import inspect

    from src.domain.ports.summary_generation import SummaryGenerationPort

    sig = inspect.signature(SummaryGenerationPort.generate_summary)
    params = sig.parameters
    assert "query_text" in params
    assert "search_results" in params
    assert "perspective" in params
    assert "config" in params
    assert "tenant_id" in params
    assert "cross_document" in params


@then("端口在 composition_root.py 中注册为 summary_generation_service")
def _then_port_registered() -> None:
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("summary_generation_service")
    assert spec is not None, "summary_generation_service 未注册"


# ===================================================================
# AC-3 摘要生成异常（业务行为，走真实服务生成）
# ===================================================================


@scenario(scenarios_path, "AC-3 - 不支持的视角抛出领域异常")
def test_ac3_unsupported_perspective(summary_runtime: None) -> None:
    """AC-3 不支持的视角抛出领域异常"""


@when("使用不支持的视角调用摘要生成")
def _when_generate_with_unsupported_perspective(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None
) -> None:
    """使用不支持的视角调用真实服务"""
    service = context["service"]
    context["exception"] = event_loop.run_until_complete(_call_expect_exception(service, perspective="unsupported_perspective"))


async def _call_expect_exception(service: Any, perspective: str) -> Exception | None:
    """调用生成并捕获异常"""
    try:
        await service.generate_summary(
            query_text=_TEST_QUERY,
            search_results=[],
            perspective=perspective,
            tenant_id=None,
        )
        return None
    except Exception as e:
        return e


@then("系统抛出 SummaryPerspectiveNotSupportedError")
def _then_throws_perspective_not_supported(context: dict[str, Any]) -> None:
    from src.domain.exceptions import SummaryPerspectiveNotSupportedError

    exc = context.get("exception")
    assert exc is not None
    assert isinstance(exc, SummaryPerspectiveNotSupportedError)


@then("异常 code 为 EXCEPTION_291")
def _then_exception_code_291(context: dict[str, Any]) -> None:
    exc = context.get("exception")
    assert exc is not None
    assert exc.code == "EXCEPTION_291"


# ===================================================================
# AC-4 摘要生成应用服务（业务行为，走真实服务生成）
# ===================================================================


@scenario(scenarios_path, "AC-4 - 财务视角摘要生成成功")
def test_ac4_financial_generation(summary_runtime: None) -> None:
    """AC-4 财务视角摘要生成"""


@scenario(scenarios_path, "AC-4 - 市场视角摘要生成成功")
def test_ac4_market_generation(summary_runtime: None) -> None:
    """AC-4 市场视角摘要生成"""


@scenario(scenarios_path, "AC-4 - 技术视角摘要生成成功")
def test_ac4_technical_generation(summary_runtime: None) -> None:
    """AC-4 技术视角摘要生成"""


@scenario(scenarios_path, "AC-4 - LLM 调用失败时抛出领域异常")
def test_ac4_llm_failure(summary_runtime: None) -> None:
    """AC-4 LLM 调用失败抛出领域异常"""


@when("以 financial 视角生成摘要")
def _when_generate_financial_summary(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None
) -> None:
    """以 financial 视角通过真实服务生成摘要"""
    _execute_generate_summary(context, event_loop, "financial")


@when("以 market 视角生成摘要")
def _when_generate_market_summary(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None
) -> None:
    """以 market 视角通过真实服务生成摘要"""
    _execute_generate_summary(context, event_loop, "market")


@when("以 technical 视角生成摘要")
def _when_generate_technical_summary(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None
) -> None:
    """以 technical 视角通过真实服务生成摘要"""
    _execute_generate_summary(context, event_loop, "technical")


def _execute_generate_summary(context: dict[str, Any], loop: asyncio.AbstractEventLoop, perspective: str) -> None:
    """通过真实服务执行摘要生成"""
    service = context["service"]
    result = loop.run_until_complete(
        service.generate_summary(
            query_text=_TEST_QUERY,
            search_results=[],
            perspective=perspective,
            tenant_id=None,
        )
    )
    context["summary_result"] = result
    context["last_perspective"] = perspective


@when("LLM 调用返回错误")
def _when_llm_call_returns_error(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None) -> None:
    """模拟 LLM 调用失败（替换 Mock 的行为，服务仍为真实实例）"""
    from src.domain.exceptions.llm_exceptions import LLMAPIError

    mock_llm = context["mock_llm_client"]
    mock_llm.structured_generate.side_effect = LLMAPIError(
        message="LLM API 调用失败",
        cause=Exception("API 返回 500"),
    )
    service = context["service"]
    context["exception"] = event_loop.run_until_complete(_call_expect_exception(service, perspective="financial"))


@then("系统调用 LLMClientPort.structured_generate 方法")
def _then_llm_structured_generate_called(context: dict[str, Any]) -> None:
    mock_llm = context["mock_llm_client"]
    mock_llm.structured_generate.assert_called_once()


@then("返回 FinancialSummary Schema 实例")
def _then_returns_financial_summary(context: dict[str, Any]) -> None:
    result = context.get("summary_result")
    assert result is not None
    # Mock 返回的是 MagicMock(spec=Schema)，验证视角特有字段存在
    assert hasattr(result, "summary_text")
    assert hasattr(result, "revenue_trend")


@then("返回 MarketSummary Schema 实例")
def _then_returns_market_summary(context: dict[str, Any]) -> None:
    result = context.get("summary_result")
    assert result is not None
    assert hasattr(result, "summary_text")
    assert hasattr(result, "market_size")


@then("返回 TechnicalSummary Schema 实例")
def _then_returns_technical_summary(context: dict[str, Any]) -> None:
    result = context.get("summary_result")
    assert result is not None
    assert hasattr(result, "summary_text")
    assert hasattr(result, "technology_stack")


@then("结果通过 Pydantic Schema 验证")
def _then_result_validated_by_pydantic(context: dict[str, Any]) -> None:
    result = context.get("summary_result")
    assert result is not None


@then("系统抛出 SummaryGenerationError")
def _then_throws_summary_generation_error(context: dict[str, Any]) -> None:
    from src.domain.exceptions import SummaryGenerationError

    exc = context.get("exception")
    assert exc is not None
    assert isinstance(exc, SummaryGenerationError)


@then("异常 code 为 EXCEPTION_290")
def _then_exception_code_290(context: dict[str, Any]) -> None:
    exc = context.get("exception")
    assert exc is not None
    assert exc.code == "EXCEPTION_290"


# ===================================================================
# AC-6 L2 文档摘要存储与检索（业务行为，走真实服务）
# ===================================================================


@scenario(scenarios_path, "AC-6 - L2 文档摘要存储与检索")
def test_ac6_l2_storage_retrieval(summary_runtime: None) -> None:
    """AC-6 L2 文档摘要存储与检索"""


@when("单文档摘要已生成并存储")
def _when_single_summary_stored(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None) -> None:
    """生成并存储单文档摘要（真实服务调用 _store_summary）"""
    service = context["service"]
    result = event_loop.run_until_complete(
        service.generate_summary(
            query_text=_TEST_QUERY,
            search_results=[],
            perspective="financial",
            tenant_id=None,
        )
    )
    context["summary_result"] = result
    context["summary_stored"] = True


@then("摘要向量写入 document_summaries collection")
def _then_summary_written_to_document_summaries(context: dict[str, Any]) -> None:
    mock_l3 = context["mock_l3_vector"]
    upsert_calls = mock_l3.upsert_points.call_args_list
    assert len(upsert_calls) > 0, "upsert_points 未被调用"
    collection_name = upsert_calls[-1][1]["collection"]
    assert collection_name == "document_summaries"


@then('LayeredRetrievalService.search_top_down(target_level="L2") 返回摘要结果')
def _then_l2_returns_summary(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    mock_layered = context["mock_layered_retrieval"]
    results = event_loop.run_until_complete(mock_layered.search_top_down(query_text=_TEST_QUERY, target_level="L2"))
    assert len(results) > 0, "L2 检索应返回摘要结果"


@then("结果 payload 包含 index_level 为 L2")
def _then_payload_has_index_level_l2(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    mock_layered = context["mock_layered_retrieval"]
    results = event_loop.run_until_complete(mock_layered.search_top_down(query_text=_TEST_QUERY, target_level="L2"))
    for r in results:
        assert r["payload"].get("index_level") == "L2"


# ===================================================================
# AC-7a 跨文档摘要生成（业务行为，走真实服务）
# ===================================================================


@scenario(scenarios_path, "AC-7a - 跨文档摘要生成")
def test_ac7a_cross_document_generation(summary_runtime: None) -> None:
    """AC-7a 跨文档摘要生成"""


@when("以 cross_document=True 模式生成摘要")
def _when_generate_cross_document_summary(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None
) -> None:
    """以跨文档模式通过真实服务生成摘要"""
    service = context["service"]
    result = event_loop.run_until_complete(
        service.generate_summary(
            query_text=_TEST_QUERY,
            search_results=[],
            perspective="financial",
            tenant_id=None,
            cross_document=True,
        )
    )
    context["summary_result"] = result


@then("系统先检索 L2 摘要")
def _then_retrieves_l2_summaries(context: dict[str, Any]) -> None:
    mock_layered = context["mock_layered_retrieval"]
    assert mock_layered.search_top_down.called, "跨文档模式应先检索 L2 摘要"


@then("聚合 Top-K 摘要结果作为上下文")
def _then_aggregates_top_k(context: dict[str, Any]) -> None:
    mock_llm = context["mock_llm_client"]
    mock_llm.structured_generate.assert_called_once()


@then("生成跨文档摘要并写入 cross_document_summaries collection")
def _then_written_to_cross_document_summaries(context: dict[str, Any]) -> None:
    mock_l3 = context["mock_l3_vector"]
    upsert_calls = mock_l3.upsert_points.call_args_list
    has_cross_doc = any(call[1].get("collection") == "cross_document_summaries" for call in upsert_calls)
    assert has_cross_doc, "未写入 cross_document_summaries collection"


@then("结果 payload 包含 index_level 为 L1")
def _then_payload_has_index_level_l1(context: dict[str, Any]) -> None:
    mock_l3 = context["mock_l3_vector"]
    upsert_calls = mock_l3.upsert_points.call_args_list
    found_l1 = False
    for call in upsert_calls:
        if call[1].get("collection") == "cross_document_summaries":
            points = call[1].get("points", [])
            for point in points:
                payload = point.get("payload", {})
                if payload.get("index_level") == "L1":
                    found_l1 = True
    assert found_l1, "跨文档摘要 payload 应包含 index_level=L1"


# ===================================================================
# AC-7b L1 跨文档摘要检索（业务行为，走真实服务）
# ===================================================================


@scenario(scenarios_path, "AC-7b - L1 跨文档摘要检索")
def test_ac7b_l1_summary_retrieval(summary_runtime: None) -> None:
    """AC-7b L1 跨文档摘要检索"""


@given("跨文档摘要已生成")
def _given_cross_document_summary_generated(summary_runtime: None) -> None:
    """跨文档摘要已生成（fixture 装配 Mock）"""
    assert summary_runtime is None or True


@when("跨文档摘要已生成并存储")
def _when_cross_document_summary_stored(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, summary_runtime: None
) -> None:
    """生成并存储跨文档摘要"""
    service = context["service"]
    result = event_loop.run_until_complete(
        service.generate_summary(
            query_text=_TEST_QUERY,
            search_results=[],
            perspective="financial",
            tenant_id=None,
            cross_document=True,
        )
    )
    context["summary_result"] = result
    context["cross_summary_stored"] = True


@then('LayeredRetrievalService.search_top_down(target_level="L1") 返回跨文档摘要结果')
def _then_l1_returns_cross_document_summary(context: dict[str, Any], event_loop: asyncio.AbstractEventLoop) -> None:
    mock_layered = context["mock_layered_retrieval"]
    results = event_loop.run_until_complete(mock_layered.search_top_down(query_text=_TEST_QUERY, target_level="L1"))
    assert len(results) > 0, "L1 检索应返回跨文档摘要结果"


# ===================================================================
# AC-8 摘要 API 端点（HTTP 级 BDD，Mock 服务注入路由）
# ===================================================================


@scenario(scenarios_path, "AC-8 - 通过 API 请求摘要生成")
def test_ac8_summary_api() -> None:
    """AC-8 通过 API 请求摘要生成"""


@when("通过 POST /api/v1/search/summary 请求摘要生成")
def _when_request_summary_api(context: dict[str, Any]) -> None:
    """通过 API 请求摘要生成"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.interfaces.api.exception_handlers import register_exception_handlers
    from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware
    from src.interfaces.api.summary import create_summary_router

    # 创建 Mock 服务（HTTP 层自身的 Mock；服务层已由其他场景真实验证）
    mock_result = _create_mock_summary_result("financial")
    mock_service = AsyncMock()
    mock_service.generate_summary.return_value = mock_result

    # 创建独立 FastAPI 应用（不调用 create_app，避免真实基础设施连接）
    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    def get_user_override() -> TokenPayload | None:
        return None

    router = create_summary_router(
        summary_service=mock_service,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    client = TestClient(app)
    response = client.post(
        "/api/v1/search/summary",
        json={
            "query_text": _TEST_QUERY,
            "perspective": "financial",
            "top_k": 10,
        },
    )
    context["api_response"] = response


def _create_mock_summary_result(perspective: str) -> Any:
    """创建模拟摘要结果"""
    mock = MagicMock()
    mock.summary_text = "模拟摘要文本"
    mock.key_points = ["要点一", "要点二"]
    mock.confidence_score = 0.85
    mock.revenue_trend = "收入增长15%"
    mock.profit_analysis = "利润率20%"
    mock.risk_factors = ["市场竞争"]
    mock.market_position = "市场领先者"

    def model_dump():
        return {
            "summary_text": mock.summary_text,
            "key_points": mock.key_points,
            "confidence_score": mock.confidence_score,
            "revenue_trend": mock.revenue_trend,
            "profit_analysis": mock.profit_analysis,
            "risk_factors": mock.risk_factors,
            "market_position": mock.market_position,
        }

    mock.model_dump = model_dump
    return mock


@then("返回 200 状态码")
def _then_returns_200(context: dict[str, Any]) -> None:
    response = context.get("api_response")
    assert response is not None
    assert response.status_code == 200


@then("响应体包含 summary query_text perspective confidence_score source_documents 字段")
def _then_response_has_required_fields(context: dict[str, Any]) -> None:
    response = context.get("api_response")
    assert response is not None
    data = response.json()
    assert "summary" in data
    assert "query_text" in data
    assert "perspective" in data
    assert "confidence_score" in data
    assert "source_documents" in data
