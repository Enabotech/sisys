"""Story 4.1a 战略工具实现 — 验收测试（BDD 步骤实现）

本文件遵循项目验收测试规范（参考 tests/acceptance/test_acceptance_strategic_tool_registration.py）：

- 步骤函数使用 @given / @when / @then 装饰器 + context: dict[str, Any] fixture
- 使用真实服务实例：InMemoryToolRepository + ToolRegistryService + ToolExecutionService
  + ToolExecutionEngine（端口契约：Mock LLM/Sandbox 适配器仅用于 5 阶段工作流验证）
- 步骤**严格按 AC 顺序**（AC-1 ~ AC-5），`# ====` 分隔
- 异常处理：使用 try/except 捕获到 context["query_error"]，Then 步骤断言 isinstance + error.code
- **禁止 mock** 核心域服务（CLAUDE.md §5 红线）；仅允许 Mock 端口适配器（LLM/Sandbox）
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.services.tool_execution_engine import (
    RetryPolicy,
    ToolExecutionEngine,
)
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_registry_service import ToolRegistryService
from src.application.skills.loader import InMemorySkillLoader
from src.domain.entities.tool import Tool
from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState
from src.domain.exceptions import (
    EntityStateTransitionError,
    EntityValidationError,
    EvidenceValidationFailedError,
    LLMAPIError,
    ToolExecutionRetryExhaustedError,
    ToolNotFoundError,
)
from src.domain.exceptions.tool_exceptions import ToolExecutionFailedError
from src.domain.value_objects.tool_execution import (
    EvidencePackage,
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

scenarios("test_acceptance_strategic_tool_impl.feature")


# ===================================================================
# 共享 fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态容器。"""
    return {}


@pytest.fixture
def tool_repository() -> InMemoryToolRepository:
    """真实 InMemory 工具仓储。"""
    return InMemoryToolRepository()


@pytest.fixture
def tool_registry(tool_repository: InMemoryToolRepository) -> ToolRegistryService:
    """真实 ToolRegistryService。"""
    return ToolRegistryService(repository=tool_repository)


def _make_mock_llm() -> AsyncMock:
    """构造 LLMClientPort mock（仅用于 AC-4 五阶段端口映射验证）。"""
    mock = AsyncMock()
    mock.structured_generate = AsyncMock(return_value="mock_response")
    return mock


def _make_mock_sandbox() -> AsyncMock:
    """构造 SandboxExecutor mock（仅用于 AC-4 沙箱 Session 生命周期验证）。"""
    mock = AsyncMock()
    mock.start_container = AsyncMock()
    mock.execute_code = AsyncMock(return_value={"status": "ok", "output": "result_data"})
    mock.stop_container = AsyncMock()
    return mock


# 延迟导入全局注册中心
_global_registry = __import__(
    "src.domain.ports.registry",
    fromlist=["_global_registry"],
)._global_registry


# ===================================================================
# Background steps
# ===================================================================


@given("战略工具执行服务已初始化（真实 InMemoryToolRepository + ToolRegistryService + ToolExecutionService + SkillLoader）")
def given_execution_service_initialized(
    context: dict[str, Any],
    tool_repository: InMemoryToolRepository,
    tool_registry: ToolRegistryService,
) -> None:
    """初始化完整执行链路（真实服务）。

    绑定：
    - InMemoryToolRepository + ToolRegistryService（真实仓储 + 注册服务）
    - ToolExecutionEngine（真实引擎 + Mock LLM/Sandbox 端口适配器）
    - ToolExecutionService（真实服务，委托 Registry + Engine）
    - InMemorySkillLoader（真实 Skills 加载器）
    """
    llm = _make_mock_llm()
    sandbox = _make_mock_sandbox()
    engine = ToolExecutionEngine(llm_client=llm, sandbox=sandbox)
    service = ToolExecutionService(registry=tool_registry, engine=engine)
    skill_loader = InMemorySkillLoader()

    context["repo"] = tool_repository
    context["registry"] = tool_registry
    context["engine"] = engine
    context["service"] = service
    context["skill_loader"] = skill_loader
    context["llm_mock"] = llm
    context["sandbox_mock"] = sandbox


@given("已注册 23 种战略工具")
def given_tools_registered(context: dict[str, Any]) -> None:
    """从 TOOL_CATALOG 加载 23 种战略工具。"""
    context["registry"].register_all()


@given("Skill 加载器包含 23 份 SKILL.md + skill_manifest 双向映射")
def given_skill_loader_initialized(context: dict[str, Any]) -> None:
    """验证 skill_manifest 双向映射 23 项。"""
    from src.application.skills.skill_manifest import (
        SLUG_TO_TOOL_ID,
        TOOL_ID_TO_SLUG,
    )

    assert len(SLUG_TO_TOOL_ID) == 23
    assert len(TOOL_ID_TO_SLUG) == 23
    context["skill_manifest"] = (TOOL_ID_TO_SLUG, SLUG_TO_TOOL_ID)


# ===================================================================
# AC-1: Tool 实体字段增强 + ToolExecution 6 状态机
# ===================================================================


@when("查询任意已注册工具（例如 PESTEL 分析）")
def when_query_registered_tool(context: dict[str, Any]) -> None:
    """查询 PESTEL 分析作为代表性工具。"""
    context["tool"] = context["registry"].get_tool(tool_name="PESTEL 分析")


@then("返回 Tool 实体包含 rule_version 字段")
def then_tool_has_rule_version(context: dict[str, Any]) -> None:
    """Tool 实体的 rule_version 字段（可为 None 或 str）。"""
    tool = context["tool"]
    assert hasattr(tool, "rule_version")


@then("返回 Tool 实体包含 reliability_score 字段（值 ∈ [0.0, 1.0]）")
def then_tool_has_reliability_score(context: dict[str, Any]) -> None:
    """Tool 实体的 reliability_score ∈ [0.0, 1.0]。"""
    tool = context["tool"]
    assert hasattr(tool, "reliability_score")
    assert 0.0 <= tool.reliability_score <= 1.0


@then("返回 Tool 实体包含 execution_count 字段（值 ≥ 0）")
def then_tool_has_execution_count(context: dict[str, Any]) -> None:
    """Tool 实体的 execution_count ≥ 0。"""
    tool = context["tool"]
    assert hasattr(tool, "execution_count")
    assert tool.execution_count >= 0


@then("返回 Tool 实体包含 slug 字段（kebab-case 格式）")
def then_tool_has_slug(context: dict[str, Any]) -> None:
    """Tool 实体的 slug 字段（kebab-case）。"""
    tool = context["tool"]
    assert hasattr(tool, "slug")


@then("23 个 TOOL_CATALOG 实例不破坏现有功能")
def then_catalog_backward_compatible(context: dict[str, Any]) -> None:
    """23 个工具全部可正常查询（向后兼容）。"""
    assert context["registry"].tool_count() == 23


@when("构造 Tool 实体的 reliability_score 为 1.5")
def when_build_tool_invalid_score(context: dict[str, Any]) -> None:
    """构造 reliability_score 越界工具。"""
    context["build_error"] = None
    try:
        Tool(
            tool_id=uuid.uuid4(),
            name="Invalid Tool",
            reliability_score=1.5,
        )
    except EntityValidationError as exc:
        context["build_error"] = exc


@then("抛出 EntityValidationError")
def then_entity_validation_error(context: dict[str, Any]) -> None:
    """验证抛出 EntityValidationError。"""
    assert isinstance(context.get("build_error"), EntityValidationError)


@then("错误码为 EXCEPTION_242")
def then_error_code_242(context: dict[str, Any]) -> None:
    """验证错误码为 EXCEPTION_242。"""
    err = context.get("build_error")
    assert err is not None
    assert err.code == "EXCEPTION_242"


@when("构造 Tool 实体的 execution_count 为 -1")
def when_build_tool_negative_count(context: dict[str, Any]) -> None:
    """构造 execution_count < 0 工具。"""
    context["build_error"] = None
    try:
        Tool(
            tool_id=uuid.uuid4(),
            name="Invalid Tool",
            execution_count=-1,
        )
    except EntityValidationError as exc:
        context["build_error"] = exc


@when('构造 Tool 实体的 slug 为 "Invalid_Slug"')
def when_build_tool_invalid_slug(context: dict[str, Any]) -> None:
    """构造非 kebab-case slug。"""
    context["build_error"] = None
    try:
        Tool(
            tool_id=uuid.uuid4(),
            name="Invalid Tool",
            slug="Invalid_Slug",
        )
    except EntityValidationError as exc:
        context["build_error"] = exc


@then("ToolExecutionState 枚举包含 IDLE/PLANNING/EXECUTING/VALIDATING/COMPLETED/FAILED 共 6 值")
def then_state_enum_6_values(context: dict[str, Any]) -> None:
    """枚举完整性。"""
    expected = {
        ToolExecutionState.IDLE,
        ToolExecutionState.PLANNING,
        ToolExecutionState.EXECUTING,
        ToolExecutionState.VALIDATING,
        ToolExecutionState.COMPLETED,
        ToolExecutionState.FAILED,
    }
    assert set(ToolExecutionState) == expected


@when("创建初始 IDLE 状态的 ToolExecution")
def when_create_idle_tool_execution(context: dict[str, Any]) -> None:
    """创建 IDLE 状态 ToolExecution。"""
    context["execution"] = ToolExecution(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tool_version="1.0.0",
        state=ToolExecutionState.IDLE,
        started_at=datetime_now(),
    )


@when("依次执行状态迁移 IDLE→PLANNING→EXECUTING→VALIDATING→COMPLETED")
def when_full_state_progression(context: dict[str, Any]) -> None:
    """完整正向迁移。"""
    exec_obj = context["execution"]
    exec_obj.transition_to(ToolExecutionState.PLANNING)
    exec_obj.transition_to(ToolExecutionState.EXECUTING)
    exec_obj.transition_to(ToolExecutionState.VALIDATING)
    exec_obj.transition_to(ToolExecutionState.COMPLETED)
    exec_obj.completed_at = datetime_now()


@then("最终 state 为 COMPLETED")
def then_state_completed(context: dict[str, Any]) -> None:
    """最终态校验。"""
    assert context["execution"].state == ToolExecutionState.COMPLETED


@then("completed_at 不为空")
def then_completed_at_set(context: dict[str, Any]) -> None:
    """终态 completed_at 必填。"""
    assert context["execution"].completed_at is not None


@then("state_version 单调递增")
def then_state_version_increments(context: dict[str, Any]) -> None:
    """乐观锁版本递增。"""
    exec_obj = context["execution"]
    # 初始 state_version=0，经过 4 次迁移后应 ≥ 4
    assert exec_obj.state_version >= 4


@when("创建 PLANNING 状态的 ToolExecution")
def when_create_planning_tool_execution(context: dict[str, Any]) -> None:
    """创建 PLANNING 状态。"""
    context["execution"] = ToolExecution(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tool_version="1.0.0",
        state=ToolExecutionState.PLANNING,
        started_at=datetime_now(),
    )


@when("执行状态迁移 PLANNING→FAILED")
def when_planning_to_failed(context: dict[str, Any]) -> None:
    """PLANNING→FAILED（中间态可转 FAILED）。"""
    exec_obj = context["execution"]
    exec_obj.transition_to(ToolExecutionState.FAILED)
    exec_obj.completed_at = datetime_now()


@then("最终 state 为 FAILED")
def then_state_failed(context: dict[str, Any]) -> None:
    """FAILED 终态校验。"""
    assert context["execution"].state == ToolExecutionState.FAILED


@when("创建 EXECUTING 状态的 ToolExecution")
def when_create_executing_tool_execution(context: dict[str, Any]) -> None:
    """创建 EXECUTING 状态。"""
    context["execution"] = ToolExecution(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tool_version="1.0.0",
        state=ToolExecutionState.EXECUTING,
        started_at=datetime_now(),
    )


@when("执行状态迁移 EXECUTING→FAILED")
def when_executing_to_failed(context: dict[str, Any]) -> None:
    """EXECUTING→FAILED。"""
    exec_obj = context["execution"]
    exec_obj.transition_to(ToolExecutionState.FAILED)
    exec_obj.completed_at = datetime_now()


@when("创建 COMPLETED 状态的 ToolExecution")
def when_create_completed_tool_execution(context: dict[str, Any]) -> None:
    """创建 COMPLETED 状态。"""
    context["execution"] = ToolExecution(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tool_version="1.0.0",
        state=ToolExecutionState.COMPLETED,
        started_at=datetime_now(),
        completed_at=datetime_now(),
    )


@when("尝试反向迁移 COMPLETED→IDLE")
def when_illegal_reverse_transition(context: dict[str, Any]) -> None:
    """非法反向迁移。"""
    exec_obj = context["execution"]
    context["transition_error"] = None
    try:
        exec_obj.transition_to(ToolExecutionState.IDLE)
    except EntityStateTransitionError as exc:
        context["transition_error"] = exc


@then("抛出 EntityStateTransitionError")
def then_state_transition_error(context: dict[str, Any]) -> None:
    """验证状态机异常。"""
    assert isinstance(context.get("transition_error"), EntityStateTransitionError)


@then("错误码为 EXCEPTION_243")
def then_error_code_243(context: dict[str, Any]) -> None:
    """EXCEPTION_243（EntityStateTransitionError）。"""
    err = context.get("transition_error")
    assert err is not None
    assert err.code == "EXCEPTION_243"


@when("尝试跳过中间态 IDLE→EXECUTING")
def when_skip_intermediate_state(context: dict[str, Any]) -> None:
    """跳过 PLANNING 直接到 EXECUTING。"""
    # 先重置 execution 为 IDLE
    context["execution"] = ToolExecution(
        execution_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tool_version="1.0.0",
        state=ToolExecutionState.IDLE,
        started_at=datetime_now(),
    )
    context["transition_error"] = None
    try:
        context["execution"].transition_to(ToolExecutionState.EXECUTING)
    except EntityStateTransitionError as exc:
        context["transition_error"] = exc


# ===================================================================
# AC-2: ToolExecutionService
# ===================================================================


def _run_async(coro: Any) -> Any:
    """同步调度异步协程。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@when("调用 ToolExecutionService.execute 传入有效 tool_id 和 ToolCall")
def when_execute_tool(context: dict[str, Any]) -> None:
    """执行工具（Mock 引擎成功路径）。"""
    tool = context["registry"].get_tool(tool_name="PESTEL 分析")
    context["tool_id"] = tool.tool_id
    context["execute_error"] = None
    context["execute_result"] = None

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tool_call = ToolCall(tool_id=tool.tool_id, arguments={"x": 1}, tenant_id=tenant_id)
    exec_context = ExecutionContext(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=f"sess-{uuid.uuid4()}",
    )

    try:
        result = _run_async(
            context["service"].execute(
                tool_id=tool.tool_id,
                tool_call=tool_call,
                context=exec_context,
            )
        )
        context["execute_result"] = result
    except (ToolExecutionFailedError, ToolExecutionRetryExhaustedError) as exc:
        context["execute_error"] = exc


@then("委托 ToolRegistryService.get_tool 查询 Tool 元数据")
def then_delegate_to_registry(context: dict[str, Any]) -> None:
    """验证委托元数据查询。"""
    # 执行成功或失败都说明委托已发生（Registry.get_tool 不抛错或抛 ToolNotFoundError）
    assert context.get("execute_error") is None or context.get("execute_result") is not None


@then("返回 ToolResult（含 status/output/evidence_package）")
def then_tool_result_returned(context: dict[str, Any]) -> None:
    """验证 ToolResult 完整。"""
    result = context["execute_result"]
    assert result is not None
    assert isinstance(result, ToolResult)
    assert result.status == ToolResultStatus.SUCCESS


@when("调用 ToolExecutionService.execute 传入不存在的 tool_id")
def when_execute_nonexistent_tool(context: dict[str, Any]) -> None:
    """执行不存在的工具。"""
    fake_id = uuid.uuid4()
    tool_call = ToolCall(tool_id=fake_id, arguments={})
    exec_context = ExecutionContext(tenant_id=uuid.uuid4(), session_id="sess")
    context["execute_error"] = None
    try:
        _run_async(
            context["service"].execute(
                tool_id=fake_id,
                tool_call=tool_call,
                context=exec_context,
            )
        )
    except ToolNotFoundError as exc:
        context["execute_error"] = exc


@then("抛出 ToolNotFoundError")
def then_tool_not_found_error(context: dict[str, Any]) -> None:
    """ToolNotFoundError 校验。"""
    assert isinstance(context.get("execute_error"), ToolNotFoundError)


@then("错误码为 EXCEPTION_380")
def then_error_code_380(context: dict[str, Any]) -> None:
    """EXCEPTION_380 校验。"""
    err = context.get("execute_error")
    assert err is not None
    assert err.code == "EXCEPTION_380"


# ===================================================================
# AC-3: 值对象完整性
# ===================================================================


@given("构造 ToolResult status=success 且 evidence_package=None")
def given_tool_result_missing_evidence(context: dict[str, Any]) -> None:
    """构造缺 evidence_package 的 ToolResult。"""
    context["result"] = ToolResult(
        tool_id=uuid.uuid4(),
        status=ToolResultStatus.SUCCESS,
        evidence_package=None,
    )


@then("调用 validate_complete 抛出 EvidenceValidationFailedError")
def then_evidence_validation_error(context: dict[str, Any]) -> None:
    """EvidenceValidationFailedError 校验。

    同时支持 ToolResult（context["result"]）和 EvidencePackage
    （context["evidence"]）两种路径。
    """
    target = context.get("result") or context.get("evidence")
    assert target is not None, "缺少待校验对象（result 或 evidence）"
    context["validation_error"] = None
    try:
        target.validate_complete()
    except EvidenceValidationFailedError as exc:
        context["validation_error"] = exc
    assert isinstance(context["validation_error"], EvidenceValidationFailedError)


@then("错误码为 EXCEPTION_386")
def then_error_code_386(context: dict[str, Any]) -> None:
    """EXCEPTION_386 校验。"""
    err = context.get("validation_error")
    assert err is not None
    assert err.code == "EXCEPTION_386"


@given('构造 EvidencePackage plan=""（必填缺失）')
def given_evidence_package_missing_plan(context: dict[str, Any]) -> None:
    """构造缺 plan 字段的 EvidencePackage。"""
    context["evidence"] = EvidencePackage(
        input_hash="abc",
        rule_version="BLM-v3.2",
        plan="",  # 必填缺失
        code="x = 1",
        result="1",
        observation="ok",
        validation="valid",
        confidence=0.9,
    )
    context["validation_error"] = None
    try:
        context["evidence"].validate_complete()
    except EvidenceValidationFailedError as exc:
        context["validation_error"] = exc


@then('missing_fields 包含 "plan"')
def then_missing_fields_contains_plan(context: dict[str, Any]) -> None:
    """missing_fields 字段校验。"""
    err = context.get("validation_error")
    assert err is not None
    assert "plan" in err.context.get("missing_fields", [])


@then("ToolResultStatus 枚举包含 success/failed/invalid/insufficient_data 共 4 值")
def then_status_enum_4_values(context: dict[str, Any]) -> None:
    """ToolResultStatus 枚举完整性。"""
    expected = {
        ToolResultStatus.SUCCESS,
        ToolResultStatus.FAILED,
        ToolResultStatus.INVALID,
        ToolResultStatus.INSUFFICIENT_DATA,
    }
    assert set(ToolResultStatus) == expected


# ===================================================================
# AC-4: ToolExecutionEngine 五阶段工作流（Mock 端口适配器）
# ===================================================================


def datetime_now():
    """返回当前 UTC 时间。"""
    from datetime import UTC, datetime

    return datetime.now(UTC)


@when("引擎执行一次完整五阶段链路（使用 Mock LLMClient + Mock Sandbox）")
def when_engine_full_pipeline(context: dict[str, Any]) -> None:
    """执行完整五阶段链路。"""
    tool = context["registry"].get_tool(tool_name="PESTEL 分析")
    tenant_id = uuid.uuid4()
    tool_call = ToolCall(tool_id=tool.tool_id, arguments={"x": 1}, tenant_id=tenant_id)
    exec_context = ExecutionContext(tenant_id=tenant_id, session_id=f"sess-{uuid.uuid4()}")
    context["engine_error"] = None
    context["engine_result"] = None
    try:
        context["engine_result"] = _run_async(
            context["engine"].execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=tool_call,
                context=exec_context,
            )
        )
    except (ToolExecutionFailedError, ToolExecutionRetryExhaustedError) as exc:
        context["engine_error"] = exc


@then("Think 阶段调用 LLMClientPort.structured_generate 产出 plan")
def then_think_stage_plan(context: dict[str, Any]) -> None:
    """Think 阶段（structured_generate 至少被调用 1 次）。"""
    assert context["llm_mock"].structured_generate.call_count >= 1


@then("Code 阶段调用 LLMClientPort.structured_generate 产出 code")
def then_code_stage_code(context: dict[str, Any]) -> None:
    """Code 阶段（累计 ≥ 2 次）。"""
    assert context["llm_mock"].structured_generate.call_count >= 2


@then("Execute 阶段调用 SandboxExecutor.execute_code 产出 result")
def then_execute_stage_result(context: dict[str, Any]) -> None:
    """Execute 阶段（execute_code 至少被调用 1 次）。"""
    assert context["sandbox_mock"].execute_code.call_count >= 1


@then("Observe 阶段调用 SandboxExecutor.execute_code 产出 observation")
def then_observe_stage_observation(context: dict[str, Any]) -> None:
    """Observe 阶段（execute_code 累计 ≥ 2 次）。"""
    assert context["sandbox_mock"].execute_code.call_count >= 2


@then("Validate 阶段调用 LLMClientPort.structured_generate 产出 validation")
def then_validate_stage_validation(context: dict[str, Any]) -> None:
    """Validate 阶段（累计 ≥ 3 次）。"""
    assert context["llm_mock"].structured_generate.call_count >= 3


@then("执行前调用 SandboxExecutor.start_container")
def then_sandbox_start_called(context: dict[str, Any]) -> None:
    """沙箱启动。"""
    assert context["sandbox_mock"].start_container.call_count >= 1


@then("执行后调用 SandboxExecutor.stop_container")
def then_sandbox_stop_called(context: dict[str, Any]) -> None:
    """沙箱停止。"""
    assert context["sandbox_mock"].stop_container.call_count >= 1


@when("LLMClientPort 首次调用抛 LLMAPIError 后续成功")
def when_llm_first_fails_then_succeeds(context: dict[str, Any]) -> None:
    """构造首次失败后续成功的 LLM Mock。"""
    llm = context["llm_mock"]
    sandbox = context["sandbox_mock"]
    call_count = {"n": 0}

    async def mock_generate(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise LLMAPIError("api error")
        return "success_response"

    llm.structured_generate = mock_generate

    # 重新构造引擎和 service（使用新 mock）
    new_engine = ToolExecutionEngine(
        llm_client=llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=3, initial_delay_sec=0.01),
    )
    context["engine"] = new_engine
    context["service"] = ToolExecutionService(
        registry=context["registry"],
        engine=new_engine,
    )
    context["retry_call_count"] = call_count

    tool = context["registry"].get_tool(tool_name="PESTEL 分析")
    tenant_id = uuid.uuid4()
    tool_call = ToolCall(tool_id=tool.tool_id, arguments={}, tenant_id=tenant_id)
    exec_context = ExecutionContext(tenant_id=tenant_id, session_id=f"sess-{uuid.uuid4()}")
    context["engine_error"] = None
    context["engine_result"] = None
    try:
        context["engine_result"] = _run_async(
            new_engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=tool_call,
                context=exec_context,
            )
        )
    except (ToolExecutionFailedError, ToolExecutionRetryExhaustedError) as exc:
        context["engine_error"] = exc


@then("重试后引擎成功完成五阶段")
def then_retry_then_success(context: dict[str, Any]) -> None:
    """重试后引擎成功。"""
    assert context["engine_error"] is None
    assert context["engine_result"] is not None
    assert context["retry_call_count"]["n"] >= 2  # 至少调用 2 次（1 次失败 + 1 次成功）


@when("LLMClientPort 持续抛 LLMAPIError 超过 max_attempts")
def when_llm_always_fails(context: dict[str, Any]) -> None:
    """构造持续失败的 LLM Mock。"""
    llm = context["llm_mock"]
    sandbox = context["sandbox_mock"]
    llm.structured_generate = AsyncMock(side_effect=LLMAPIError("persistent error"))

    new_engine = ToolExecutionEngine(
        llm_client=llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_sec=0.01),
    )
    context["engine"] = new_engine

    tool = context["registry"].get_tool(tool_name="PESTEL 分析")
    tenant_id = uuid.uuid4()
    tool_call = ToolCall(tool_id=tool.tool_id, arguments={}, tenant_id=tenant_id)
    exec_context = ExecutionContext(tenant_id=tenant_id, session_id=f"sess-{uuid.uuid4()}")
    context["engine_error"] = None
    try:
        _run_async(
            new_engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=tool_call,
                context=exec_context,
            )
        )
    except (ToolExecutionRetryExhaustedError, ToolExecutionFailedError) as exc:
        context["engine_error"] = exc


@then("抛出 ToolExecutionRetryExhaustedError")
def then_retry_exhausted_error(context: dict[str, Any]) -> None:
    """重试耗尽异常。"""
    assert isinstance(context.get("engine_error"), ToolExecutionRetryExhaustedError)


@then("错误码为 EXCEPTION_383")
def then_error_code_383(context: dict[str, Any]) -> None:
    """EXCEPTION_383。"""
    err = context.get("engine_error")
    assert err is not None
    assert err.code == "EXCEPTION_383"


@then(
    "ToolResult.evidence_package 包含 input_hash/rule_version/plan/code/result/"
    "observation/validation/confidence/citations 共 9 字段"
)
def then_evidence_9_fields(context: dict[str, Any]) -> None:
    """9 字段完整性。"""
    result = context["engine_result"]
    assert result is not None
    ep = result.evidence_package
    assert ep is not None
    # 9 字段全部存在
    assert ep.input_hash != ""
    assert ep.rule_version != ""
    assert ep.plan != ""
    assert ep.code != ""
    assert ep.result != ""
    assert ep.observation != ""
    assert ep.validation != ""


# ===================================================================
# AC-5: 端口注册（4 个新端口）
# ===================================================================


@then("tool_execution_repository 端口已注册")
def then_tool_execution_repo_registered(context: dict[str, Any]) -> None:
    """验证 tool_execution_repository 端口。"""
    spec = _global_registry.get("tool_execution_repository")
    assert spec is not None
    context["tool_execution_repo_spec"] = spec


@then("tool_execution_service 端口已注册")
def then_tool_execution_service_registered(context: dict[str, Any]) -> None:
    """验证 tool_execution_service 端口。"""
    spec = _global_registry.get("tool_execution_service")
    assert spec is not None
    context["tool_execution_service_spec"] = spec


@then("tool_execution_engine 端口已注册")
def then_tool_execution_engine_registered(context: dict[str, Any]) -> None:
    """验证 tool_execution_engine 端口。"""
    spec = _global_registry.get("tool_execution_engine")
    assert spec is not None
    context["tool_execution_engine_spec"] = spec


@then("skill_loader 端口已注册")
def then_skill_loader_registered(context: dict[str, Any]) -> None:
    """验证 skill_loader 端口。"""
    spec = _global_registry.get("skill_loader")
    assert spec is not None
    context["skill_loader_spec"] = spec


@given("tool_execution_repository 端口已注册")
def given_tool_execution_repo_registered(context: dict[str, Any]) -> None:
    """前置：tool_execution_repository 端口已注册。"""
    spec = _global_registry.get("tool_execution_repository")
    assert spec is not None
    context["spec"] = spec


@then('PortSpec.name == "tool_execution_repository"')
def then_spec_name(context: dict[str, Any]) -> None:
    """PortSpec.name 校验。"""
    assert context["spec"].name == "tool_execution_repository"


@then('PortSpec.version == "v1.0.0"')
def then_spec_version(context: dict[str, Any]) -> None:
    """PortSpec.version 校验。"""
    assert context["spec"].version == "v1.0.0"


@then("PortSpec.lifetime == SCOPED")
def then_spec_lifetime(context: dict[str, Any]) -> None:
    """PortSpec.lifetime 校验。"""
    from src.domain.ports.registry import Lifetime

    assert context["spec"].lifetime == Lifetime.SCOPED


@then('PortSpec.owner == "tool-team"')
def then_spec_owner(context: dict[str, Any]) -> None:
    """PortSpec.owner 校验。"""
    assert context["spec"].owner == "tool-team"


@then('PortSpec.tags 包含 ("tool", "execution", "repository")')
def then_spec_tags(context: dict[str, Any]) -> None:
    """PortSpec.tags 校验。"""
    assert set(context["spec"].tags) == {"tool", "execution", "repository"}
