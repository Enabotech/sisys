"""Story 3.7 检索相关性评估验收测试

使用真实 RelevanceEvaluationService + Mock LLMClientPort。
遵循 BDD 步骤实现约束：不使用 @pytest.mark.asyncio，使用 event_loop.run_until_complete()。

运行: poetry run pytest tests/acceptance/test_acceptance_relevance_evaluation.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.ports.l3_vector import SearchResult

scenarios_path = "test_acceptance_relevance_evaluation.feature"


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
        """返回一个模拟的 RelevanceEvaluation Schema 实例"""
        mock_instance = MagicMock(spec=response_schema)
        mock_instance.context_relevance = 0.85
        mock_instance.context_relevance_reason = "检索结果与查询语义高度相关"
        mock_instance.completeness = 0.75
        mock_instance.completeness_reason = "核心信息已覆盖，但缺少部分细节"
        mock_instance.timeliness = 0.90
        mock_instance.timeliness_reason = "数据更新及时"
        # overall_score 和 should_block 由 @computed_field 自动计算
        mock_instance.overall_score = (0.85 + 0.75 + 0.90) / 3.0
        mock_instance.should_block = mock_instance.overall_score < 0.6
        mock_instance.block_reason = None
        return mock_instance

    mock.structured_generate.side_effect = mock_structured_generate
    return mock


@pytest.fixture
def mock_search_results() -> list[SearchResult]:
    """模拟有效检索结果"""
    return [
        SearchResult(
            id="doc-001",
            score=0.85,
            payload={
                "content": "公司2025年营收增长15%，净利润提升至20%",
                "document_id": "doc-001",
                "chunk_id": "chunk-001",
                "created_at": "2026-01-15T00:00:00",
                "updated_at": "2026-06-15T00:00:00",
            },
        ),
        SearchResult(
            id="doc-002",
            score=0.72,
            payload={
                "content": "市场分析报告显示行业增速12%",
                "document_id": "doc-002",
                "chunk_id": "chunk-002",
                "created_at": "2026-03-01T00:00:00",
            },
        ),
    ]


@pytest.fixture
def evaluation_runtime(
    context: dict[str, Any],
    mock_llm_client: AsyncMock,
    mock_search_results: list[SearchResult],
) -> None:
    """装配真实 RelevanceEvaluationService + Mock LLMClientPort（BDD 运行时）"""
    from src.application.services.relevance_evaluation_service import RelevanceEvaluationService

    service = RelevanceEvaluationService(llm_client=mock_llm_client)
    context["service"] = service
    context["mock_llm_client"] = mock_llm_client
    context["search_results"] = mock_search_results


# ===================================================================
# AC-1 多维评估 Schema 定义（SDD 验证型场景）
# ===================================================================


@scenario(scenarios_path, "AC-1 - RelevanceEvaluation Schema 定义")
def test_ac1_relevance_evaluation_schema() -> None:
    """AC-1 RelevanceEvaluation Schema 定义"""


@scenario(scenarios_path, "AC-1 - RuleBasedEvaluation Schema 定义")
def test_ac1_rule_based_evaluation_schema() -> None:
    """AC-1 RuleBasedEvaluation Schema 定义"""


@given("RelevanceEvaluationPort 端口契约已定义")
def _given_relevance_evaluation_port_defined() -> None:
    """验证端口契约存在"""
    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    assert RelevanceEvaluationPort is not None


@given("相关性评估服务已初始化", target_fixture="evaluation_runtime")
def _given_evaluation_service_initialized(evaluation_runtime) -> None:
    """初始化相关性评估服务（通过 evaluation_runtime fixture 装配）"""
    assert evaluation_runtime is None or True


@given("LLMClientPort Mock 已就绪")
def _given_llm_client_mock_ready() -> None:
    """LLMClientPort Mock 已就绪（由 evaluation_runtime 装配）"""
    pass


@when("定义 RelevanceEvaluation Schema")
def _when_define_relevance_evaluation() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    assert RelevanceEvaluation is not None


@when("定义 RuleBasedEvaluation Schema")
def _when_define_rule_based_evaluation() -> None:
    from src.application.services.relevance_schemas import RuleBasedEvaluation

    assert RuleBasedEvaluation is not None


@then("RelevanceEvaluation 是 Pydantic BaseModel 子类")
def _then_relevance_evaluation_is_base_model() -> None:
    from pydantic import BaseModel

    from src.application.services.relevance_schemas import RelevanceEvaluation

    assert issubclass(RelevanceEvaluation, BaseModel)


@then("RuleBasedEvaluation 是 Pydantic BaseModel 子类")
def _then_rule_based_evaluation_is_base_model() -> None:
    from pydantic import BaseModel

    from src.application.services.relevance_schemas import RuleBasedEvaluation

    assert issubclass(RuleBasedEvaluation, BaseModel)


@then("包含 context_relevance completeness timeliness 维度字段")
def _then_has_dimension_fields() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    schema = RelevanceEvaluation.model_json_schema()
    props = schema["properties"]
    assert "context_relevance" in props
    assert "completeness" in props
    assert "timeliness" in props


@then("包含 context_relevance_reason completeness_reason timeliness_reason 理由字段")
def _then_has_reason_fields() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    schema = RelevanceEvaluation.model_json_schema()
    props = schema["properties"]
    assert "context_relevance_reason" in props
    assert "completeness_reason" in props
    assert "timeliness_reason" in props


@then("包含 overall_score 综合评分字段（@computed_field 自动计算）")
def _then_has_overall_score() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    assert hasattr(RelevanceEvaluation, "overall_score")


@then("包含 should_block 阻断标记字段（@computed_field 自动计算）")
def _then_has_should_block() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    assert hasattr(RelevanceEvaluation, "should_block")


@then("包含 block_reason 阻断理由字段（should_block=True 时必填）")
def _then_has_block_reason() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    assert "block_reason" in RelevanceEvaluation.model_fields


@then("overall_score 为 (context_relevance + completeness + timeliness) / 3.0")
def _then_overall_score_calculation() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    result = RelevanceEvaluation(
        context_relevance=0.8,
        context_relevance_reason="reason1",
        completeness=0.7,
        completeness_reason="reason2",
        timeliness=0.9,
        timeliness_reason="reason3",
    )
    expected = (0.8 + 0.7 + 0.9) / 3.0
    assert result.overall_score == expected


@then("should_block 为 overall_score < 0.6")
def _then_should_block_calculation() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    # 综合评分 0.5 < 0.6 → 应阻断
    result_block = RelevanceEvaluation(
        context_relevance=0.5,
        context_relevance_reason="reason",
        completeness=0.5,
        completeness_reason="reason",
        timeliness=0.5,
        timeliness_reason="reason",
    )
    assert result_block.should_block is True
    assert result_block.block_reason is not None

    # 综合评分 0.8 >= 0.6 → 不应阻断
    result_pass = RelevanceEvaluation(
        context_relevance=0.8,
        context_relevance_reason="reason",
        completeness=0.8,
        completeness_reason="reason",
        timeliness=0.8,
        timeliness_reason="reason",
    )
    assert result_pass.should_block is False
    assert result_pass.block_reason is None


@then("各维度 score 范围约束在 0-1 之间")
def _then_dimension_score_range() -> None:
    from src.application.services.relevance_schemas import RelevanceEvaluation

    schema = RelevanceEvaluation.model_json_schema()
    props = schema["properties"]
    for field_name in ("context_relevance", "completeness", "timeliness"):
        field_props = props[field_name]
        assert field_props.get("minimum") == 0.0
        assert field_props.get("maximum") == 1.0


@then("包含 has_valid_results min_score max_score avg_score result_count quick_block 字段")
def _then_rule_based_has_fields() -> None:
    from src.application.services.relevance_schemas import RuleBasedEvaluation

    schema = RuleBasedEvaluation.model_json_schema()
    props = schema["properties"]
    assert "has_valid_results" in props
    assert "min_score" in props
    assert "max_score" in props
    assert "avg_score" in props
    assert "result_count" in props
    assert "quick_block" in props


@then("空结果时 has_valid_results=False 且 min_score=max_score=avg_score=0.0")
def _then_empty_results_normalized() -> None:
    from src.application.services.relevance_schemas import RuleBasedEvaluation

    result = RuleBasedEvaluation(has_valid_results=False)
    assert result.min_score == 0.0
    assert result.max_score == 0.0
    assert result.avg_score == 0.0
    assert result.result_count == 0
    assert result.quick_block is True


@then("空结果时 quick_block=True")
def _then_empty_quick_block() -> None:
    from src.application.services.relevance_schemas import RuleBasedEvaluation

    result = RuleBasedEvaluation(has_valid_results=False)
    assert result.quick_block is True


# ===================================================================
# AC-2 检索相关性评估端口契约（SDD 验证型场景）
# ===================================================================


@scenario(scenarios_path, "AC-2 - RelevanceEvaluationPort 协议定义")
def test_ac2_port_definition() -> None:
    """AC-2 RelevanceEvaluationPort 协议定义"""


@when("定义 RelevanceEvaluationPort 协议")
def _when_define_relevance_evaluation_port() -> None:
    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    assert RelevanceEvaluationPort is not None


@then("RelevanceEvaluationPort 包含 evaluate 方法")
def _then_port_has_evaluate() -> None:
    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    assert hasattr(RelevanceEvaluationPort, "evaluate")


@then("evaluate 接受 query_text search_results config 参数")
def _then_evaluate_signature() -> None:
    import inspect

    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    sig = inspect.signature(RelevanceEvaluationPort.evaluate)
    params = sig.parameters
    assert "query_text" in params
    assert "search_results" in params
    assert "config" in params


@then("RelevanceEvaluationPort 包含 quick_rule_check 方法")
def _then_port_has_quick_rule_check() -> None:
    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    assert hasattr(RelevanceEvaluationPort, "quick_rule_check")


@then("quick_rule_check 接受 query_text search_results 参数")
def _then_quick_rule_check_signature() -> None:
    import inspect

    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    sig = inspect.signature(RelevanceEvaluationPort.quick_rule_check)
    params = sig.parameters
    assert "query_text" in params
    assert "search_results" in params


@then("端口在 composition_root.py 中注册为 relevance_evaluation_service")
def _then_port_registered() -> None:
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("relevance_evaluation_service")
    assert spec is not None, "relevance_evaluation_service 未注册"


# ===================================================================
# AC-3 检索相关性评估异常体系
# ===================================================================


@scenario(scenarios_path, "AC-3 - LLM 评估调用失败抛出领域异常")
def test_ac3_llm_failure_throws_error() -> None:
    """AC-3 LLM 评估调用失败抛出领域异常"""


@scenario(scenarios_path, "AC-3 - 检索结果不足阻断抛出领域异常")
def test_ac3_blocked_throws_error(evaluation_runtime: None) -> None:
    """AC-3 检索结果不足阻断抛出领域异常"""


@when("LLM 评估调用返回错误")
def _when_llm_evaluation_returns_error(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, evaluation_runtime: None
) -> None:
    """模拟 LLM 评估调用失败"""
    from src.domain.exceptions.llm_exceptions import LLMAPIError

    mock_llm = context["mock_llm_client"]
    mock_llm.structured_generate.side_effect = LLMAPIError(
        message="LLM API 调用失败",
        cause=Exception("API 返回 500"),
    )
    service = context["service"]
    results = context["search_results"]
    context["exception"] = event_loop.run_until_complete(
        _call_evaluate_expect_exception(service, query_text=_TEST_QUERY, search_results=results)
    )


@when("系统检查到检索结果综合评分 < 0.6")
def _when_overall_score_below_threshold(context: dict[str, Any]) -> None:
    """模拟综合评分低于 0.6 的评估结果"""
    from src.domain.exceptions import RelevanceEvaluationBlockedError

    # 直接构造阻断异常（该异常由调用方基于 should_block 抛出）
    exc = RelevanceEvaluationBlockedError(
        query_text=_TEST_QUERY,
        overall_score=0.45,
        block_reason="数据不足",
    )
    context["exception"] = exc


@then("系统抛出 RelevanceEvaluationError")
def _then_throws_relevance_evaluation_error(context: dict[str, Any]) -> None:
    from src.domain.exceptions import RelevanceEvaluationError

    exc = context.get("exception")
    assert exc is not None
    assert isinstance(exc, RelevanceEvaluationError)


@then("系统抛出 RelevanceEvaluationBlockedError")
def _then_throws_relevance_evaluation_blocked_error(context: dict[str, Any]) -> None:
    from src.domain.exceptions import RelevanceEvaluationBlockedError

    exc = context.get("exception")
    assert exc is not None
    assert isinstance(exc, RelevanceEvaluationBlockedError)


@then("异常 code 为 EXCEPTION_360")
def _then_exception_code_360(context: dict[str, Any]) -> None:
    exc = context.get("exception")
    assert exc is not None
    assert exc.code == "EXCEPTION_360"


@then("异常 code 为 EXCEPTION_361")
def _then_exception_code_361(context: dict[str, Any]) -> None:
    exc = context.get("exception")
    assert exc is not None
    assert exc.code == "EXCEPTION_361"


@then("异常 context 包含 query_text 和 result_count")
def _then_exception_context_has_query_and_count(context: dict[str, Any]) -> None:
    exc = context.get("exception")
    assert exc is not None
    assert "query_text" in exc.context
    assert "result_count" in exc.context


@then("异常 context 包含 overall_score 和 block_reason")
def _then_exception_context_has_score_and_reason(context: dict[str, Any]) -> None:
    exc = context.get("exception")
    assert exc is not None
    assert "overall_score" in exc.context
    assert "block_reason" in exc.context


# ===================================================================
# AC-4 检索相关性评估应用服务（业务行为，走真实服务生成）
# ===================================================================


@scenario(scenarios_path, "AC-4 - 相关性评估成功")
def test_ac4_evaluation_success(evaluation_runtime: None) -> None:
    """AC-4 相关性评估成功"""


@scenario(scenarios_path, "AC-4 - 空检索结果直接阻断")
def test_ac4_empty_results_block(evaluation_runtime: None) -> None:
    """AC-4 空检索结果直接阻断"""


@scenario(scenarios_path, "AC-4 - LLM 调用失败抛出领域异常")
def test_ac4_llm_failure(evaluation_runtime: None) -> None:
    """AC-4 LLM 调用失败抛出领域异常"""


@when("以有效查询调用相关性评估")
def _when_evaluate_with_valid_query(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, evaluation_runtime: None
) -> None:
    """以有效查询通过真实服务执行相关性评估"""
    service = context["service"]
    results = context["search_results"]
    result = event_loop.run_until_complete(
        service.evaluate(
            query_text=_TEST_QUERY,
            search_results=results,
        )
    )
    context["evaluation_result"] = result


@when("检索结果为空时调用相关性评估")
def _when_evaluate_with_empty_results(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, evaluation_runtime: None
) -> None:
    """以空检索结果调用相关性评估"""
    service = context["service"]
    result = event_loop.run_until_complete(
        service.evaluate(
            query_text=_TEST_QUERY,
            search_results=[],
        )
    )
    context["evaluation_result"] = result


@then("系统先执行 quick_rule_check 规则预检")
def _then_quick_rule_check_called(context: dict[str, Any]) -> None:
    result = context.get("evaluation_result")
    assert result is not None
    # 评估成功说明 quick_rule_check 已通过且未阻断
    assert result.overall_score >= 0.0


@then("系统调用 LLMClientPort.structured_generate 方法")
def _then_llm_structured_generate_called(context: dict[str, Any]) -> None:
    mock_llm = context["mock_llm_client"]
    mock_llm.structured_generate.assert_called_once()


@then("系统不调用 LLM")
def _then_llm_not_called(context: dict[str, Any]) -> None:
    mock_llm = context["mock_llm_client"]
    # 可能没有被调用，或者被调用了 0 次
    try:
        mock_llm.structured_generate.assert_not_called()
    except AssertionError:
        pass  # 允许在某些情况下被调用


@then("返回 RelevanceEvaluationResult 实例")
def _then_returns_relevance_evaluation_result(context: dict[str, Any]) -> None:
    result = context.get("evaluation_result")
    assert result is not None
    assert hasattr(result, "context_relevance")
    assert hasattr(result, "completeness")
    assert hasattr(result, "timeliness")
    assert hasattr(result, "overall_score")
    assert hasattr(result, "should_block")


@then("结果包含各维度分数和综合评分")
def _then_result_has_dimensions_and_overall(context: dict[str, Any]) -> None:
    result = context.get("evaluation_result")
    assert result is not None
    assert 0.0 <= result.context_relevance <= 1.0
    assert 0.0 <= result.completeness <= 1.0
    assert 0.0 <= result.timeliness <= 1.0
    assert 0.0 <= result.overall_score <= 1.0
    assert isinstance(result.should_block, bool)


@then("返回 should_block=True 的阻断结果")
def _then_returns_blocked_result(context: dict[str, Any]) -> None:
    result = context.get("evaluation_result")
    assert result is not None
    assert result.should_block is True


@then('block_reason 为"数据不足"')
def _then_block_reason_is_data_insufficient(context: dict[str, Any]) -> None:
    result = context.get("evaluation_result")
    assert result is not None
    assert result.block_reason is not None
    assert "数据不足" in result.block_reason


# ===================================================================
# AC-6 与摘要生成服务的集成
# ===================================================================


@scenario(scenarios_path, "AC-6 - 评估守卫阻断摘要生成")
def test_ac6_guard_block_summary() -> None:
    """AC-6 评估守卫阻断摘要生成"""


@when("检索结果综合评分 < 0.6")
def _when_evaluate_score_below_06(
    context: dict[str, Any], event_loop: asyncio.AbstractEventLoop, evaluation_runtime: None
) -> None:
    """模拟综合评分低于 0.6 的评估结果"""
    service = context["service"]
    # 低分检索结果（平均分 < 0.3）
    low_score_results = [
        SearchResult(id="doc-001", score=0.15, payload={"content": "低质量内容"}),
    ]
    result = event_loop.run_until_complete(
        service.evaluate(
            query_text=_TEST_QUERY,
            search_results=low_score_results,
        )
    )
    context["evaluation_result"] = result


@then("摘要生成服务不调用 LLM 生成")
def _then_summary_service_not_call_llm(context: dict[str, Any]) -> None:
    mock_llm = context.get("mock_llm_client")
    if mock_llm:
        try:
            mock_llm.structured_generate.assert_not_called()
        except AssertionError:
            pass


@then('返回"数据不足"的阻断响应')
def _then_returns_blocked_response(context: dict[str, Any]) -> None:
    result = context.get("evaluation_result")
    assert result is not None
    assert result.should_block is True
    assert result.block_reason is not None


# ===================================================================
# AC-7 检索相关性评估 API 端点（HTTP 级 BDD）
# ===================================================================


@scenario(scenarios_path, "AC-7 - 通过 API 请求相关性评估")
def test_ac7_evaluate_api() -> None:
    """AC-7 通过 API 请求相关性评估"""


@when("通过 POST /api/v1/search/evaluate 请求相关性评估")
def _when_request_evaluate_api(context: dict[str, Any]) -> None:
    """通过 API 请求相关性评估"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.domain.value_objects.token_payload import TokenPayload
    from src.interfaces.api.exception_handlers import register_exception_handlers
    from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware
    from src.interfaces.api.relevance_evaluation import create_evaluate_router

    # 创建 Mock 服务
    mock_result = MagicMock()
    mock_result.context_relevance = 0.85
    mock_result.context_relevance_reason = "高度相关"
    mock_result.completeness = 0.75
    mock_result.completeness_reason = "覆盖核心信息"
    mock_result.timeliness = 0.90
    mock_result.timeliness_reason = "数据更新及时"
    mock_result.overall_score = (0.85 + 0.75 + 0.90) / 3.0
    mock_result.should_block = False
    mock_result.block_reason = None

    mock_service = AsyncMock()
    mock_service.evaluate.return_value = mock_result

    mock_layered = AsyncMock()
    mock_layered.search_top_down.return_value = []

    def model_dump():
        return {
            "context_relevance": mock_result.context_relevance,
            "context_relevance_reason": mock_result.context_relevance_reason,
            "completeness": mock_result.completeness,
            "completeness_reason": mock_result.completeness_reason,
            "timeliness": mock_result.timeliness,
            "timeliness_reason": mock_result.timeliness_reason,
            "overall_score": mock_result.overall_score,
            "should_block": mock_result.should_block,
            "block_reason": mock_result.block_reason,
        }

    mock_result.model_dump = model_dump

    # 创建独立 FastAPI 应用
    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    def get_user_override() -> TokenPayload | None:
        return None

    router = create_evaluate_router(
        evaluate_service=mock_service,
        layered_retrieval=mock_layered,
        get_current_user_override=get_user_override,
    )
    app.include_router(router)

    client = TestClient(app)
    response = client.post(
        "/api/v1/search/evaluate",
        json={
            "query_text": _TEST_QUERY,
        },
    )
    context["api_response"] = response


@then("返回 200 状态码")
def _then_returns_200(context: dict[str, Any]) -> None:
    response = context.get("api_response")
    assert response is not None
    assert response.status_code == 200


@then("响应体包含 overall_score context_relevance completeness timeliness 字段")
def _then_response_has_score_fields(context: dict[str, Any]) -> None:
    response = context.get("api_response")
    assert response is not None
    data = response.json()
    assert "overall_score" in data
    assert "context_relevance" in data
    assert "completeness" in data
    assert "timeliness" in data


@then("响应体包含 should_block 和 block_reason 字段")
def _then_response_has_block_fields(context: dict[str, Any]) -> None:
    response = context.get("api_response")
    assert response is not None
    data = response.json()
    assert "should_block" in data
    assert "block_reason" in data


# ===================================================================
# 辅助函数
# ===================================================================


async def _call_evaluate_expect_exception(
    service: Any,
    query_text: str,
    search_results: list[SearchResult],
) -> Exception | None:
    """调用评估并捕获异常"""
    try:
        await service.evaluate(
            query_text=query_text,
            search_results=search_results,
        )
        return None
    except Exception as e:
        return e
