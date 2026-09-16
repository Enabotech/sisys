"""ToolInputValidator 装饰器单元测试(Story 4.3 AC-3)

覆盖范围:
1. strict 模式下入参校验失败抛 ToolInputSchemaValidationError(EXCEPTION_395)
2. lenient 模式下入参校验失败记录 warning 后继续执行
3. 入参校验通过时直接委托 wrapped.execute
4. 事件发布行为:is_final=True / tenant_id / execution_id 共享
5. payload 门禁截断(条数 + path 深度)
6. fire-and-forget 异步发布不阻塞主流程
7. execution_id 透传到 context.extensions(供 OUTPUT 装饰器复用,P0-F 修复)
8. event_publisher 为 None 时不发布事件
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.services.schema_event_helpers import (
    EVENT_MAX_PATH_DEPTH_DEFAULT,
    EVENT_MAX_VIOLATIONS_DEFAULT,
)
from src.application.services.tool_input_validator import ToolInputValidator
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.events.tool_schema_events import ToolSchemaValidationFailed
from src.domain.exceptions import ToolInputSchemaValidationError
from src.domain.services.schema_validator import (
    SchemaValidationResult,
    SchemaViolation,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)

# ---------------------------------------------------------------------------
# 测试 fixtures
# ---------------------------------------------------------------------------


def _make_tool(
    input_schema: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
    tool_id: uuid.UUID | None = None,
) -> Tool:
    """构造测试用 Tool 实体"""
    now = datetime.now(UTC)
    return Tool(
        tool_id=tool_id or uuid.uuid4(),
        name="test-tool",
        description="test",
        category=ToolCategory.ANALYSIS,
        input_schema=input_schema,
        output_schema=output_schema or {},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_context(tenant_id: uuid.UUID | None = None) -> ExecutionContext:
    """构造测试用 ExecutionContext"""
    return ExecutionContext(tenant_id=tenant_id or uuid.uuid4())


def _make_tool_call(tool_id: uuid.UUID, arguments: dict[str, Any]) -> ToolCall:
    return ToolCall(tool_id=tool_id, arguments=arguments)


def _make_violation(path: str = "/name", expected: str = "string", actual: Any = 123) -> SchemaViolation:
    return SchemaViolation(path=path, expected=expected, actual=actual, message=f"{path} expected {expected}")


def _make_result(
    tool_id: uuid.UUID,
    output: dict[str, Any] | None = None,
    status: ToolResultStatus = ToolResultStatus.SUCCESS,
) -> ToolResult:
    return ToolResult(
        tool_id=tool_id,
        status=status,
        output=output or {},
    )


def _build_validator(
    wrapped: ToolExecutionServicePort | None = None,
    schema_validator: SchemaValidatorPort | None = None,
    tool_registry: ToolRegistryServicePort | None = None,
    event_publisher: Any | None = None,
    failure_policy: str = "strict",
) -> ToolInputValidator:
    """构造 ToolInputValidator 默认所有依赖为 AsyncMock/MagicMock"""
    return ToolInputValidator(
        wrapped=wrapped or AsyncMock(spec=ToolExecutionServicePort),
        schema_validator=schema_validator or MagicMock(spec=SchemaValidatorPort),
        tool_registry=tool_registry or MagicMock(spec=ToolRegistryServicePort),
        event_publisher=event_publisher,
        failure_policy=cast(Literal["strict", "lenient"], failure_policy),
    )


# ---------------------------------------------------------------------------
# 1. strict 模式 + 入参校验失败
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strict_raises_tool_input_schema_validation_error() -> None:
    """strict 模式 + 入参校验失败 → 抛 EXCEPTION_395 + 不进入 wrapped"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object", "required": ["name"]}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)
    wrapped.execute = AsyncMock(return_value=_make_result(tool_id))

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(path="/name"),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={"missing": "name"})

    with pytest.raises(ToolInputSchemaValidationError) as exc_info:
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    # 验证异常 code 是 EXCEPTION_395
    assert exc_info.value.code == "EXCEPTION_395"
    # 验证 wrapped.execute 未被调用(校验失败不进 Engine)
    wrapped.execute.assert_not_called()
    # 验证 registry.get_tool 被调用以解析 Tool 元数据
    registry.get_tool.assert_called_once_with(tool_id=tool_id)


# ---------------------------------------------------------------------------
# 2. lenient 模式 + 入参校验失败:记录 warning 继续执行
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lenient_continues_execution_on_invalid_args(caplog: pytest.LogCaptureFixture) -> None:
    """lenient 模式 + 入参校验失败 → 记录 warning 后继续委托 wrapped.execute"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)
    expected_result = _make_result(tool_id)
    wrapped.execute = AsyncMock(return_value=expected_result)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        failure_policy="lenient",
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    with caplog.at_level("WARNING"):
        result = await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    # lenient 模式不抛异常,继续执行
    assert result == expected_result
    wrapped.execute.assert_awaited_once()
    # 记录 warning 日志
    assert any("lenient" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# 3. 入参校验通过时直接委托
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_through_on_valid_args() -> None:
    """入参校验通过 → 直接委托 wrapped.execute(不发布事件)"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)
    expected_result = _make_result(tool_id)
    wrapped.execute = AsyncMock(return_value=expected_result)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(is_valid=True)

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={"valid": True})

    result = await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    assert result == expected_result
    wrapped.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. 事件发布行为(INPUT 失败)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publishes_event_with_is_final_true_on_input_failure() -> None:
    """INPUT 校验失败 → 发布 1 次事件,is_final=True"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object", "required": ["name"]}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    event_publisher = MagicMock()
    event_publisher.publish = AsyncMock()

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    with pytest.raises(ToolInputSchemaValidationError):
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    # fire-and-forget:让事件循环有机会调度异步任务
    await asyncio.sleep(0)

    # 验证事件被发布
    event_publisher.publish.assert_awaited_once()
    published_event = event_publisher.publish.await_args.args[0]
    assert isinstance(published_event, ToolSchemaValidationFailed)
    assert published_event.is_final is True
    assert published_event.validation_phase == "INPUT"
    assert published_event.tool_id == tool_id
    assert published_event.tenant_id == context.tenant_id


@pytest.mark.asyncio
async def test_does_not_publish_event_when_event_publisher_is_none() -> None:
    """event_publisher=None 时,INPUT 失败仍抛异常但不发布事件"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=None,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    with pytest.raises(ToolInputSchemaValidationError):
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)


@pytest.mark.asyncio
async def test_event_publisher_exception_does_not_break_strict_flow() -> None:
    """event_publisher 抛异常时,严格模式仍抛 ToolInputSchemaValidationError"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    event_publisher = MagicMock()
    event_publisher.publish = AsyncMock(side_effect=RuntimeError("publish failed"))

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    with pytest.raises(ToolInputSchemaValidationError):
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    # 让 fire-and-forget 任务有机会运行(异常被吞噬)
    await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# 5. execution_id 透传到 context.extensions(P0-F 修复)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_id_propagates_to_context_extensions() -> None:
    """校验通过时,execution_id 写入 context.extensions(供后续 OUTPUT 装饰器复用)"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)
    expected_result = _make_result(tool_id)
    wrapped.execute = AsyncMock(return_value=expected_result)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(is_valid=True)

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    # 验证 wrapped.execute 被调用时传入的 context.extensions["schema_execution_id"] 已设置
    call_kwargs = wrapped.execute.await_args.kwargs
    assert "context" in call_kwargs
    passed_context = call_kwargs["context"]
    assert "schema_execution_id" in passed_context.extensions


# ---------------------------------------------------------------------------
# 6. payload 门禁截断(条数 + path 深度)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_violations_truncated_when_exceed_max() -> None:
    """violations 超过 EVENT_MAX_VIOLATIONS → 事件 payload 截断到 ≤ 10 条"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)

    many_violations = tuple(_make_violation(path=f"/field_{i}") for i in range(EVENT_MAX_VIOLATIONS_DEFAULT * 3))
    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=many_violations,
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    event_publisher = MagicMock()
    event_publisher.publish = AsyncMock()

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    with pytest.raises(ToolInputSchemaValidationError):
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    await asyncio.sleep(0)

    published_event = event_publisher.publish.await_args.args[0]
    # 事件 payload 截断到 ≤10 条
    assert len(published_event.schema_violations) <= EVENT_MAX_VIOLATIONS_DEFAULT


@pytest.mark.asyncio
async def test_event_path_truncated_when_too_deep() -> None:
    """path 深度超过 EVENT_MAX_PATH_DEPTH → 路径截断"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)

    # 构造深度超限的 path
    deep_path = "/" + "/".join(f"level_{i}" for i in range(EVENT_MAX_PATH_DEPTH_DEFAULT * 3))
    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(path=deep_path),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    event_publisher = MagicMock()
    event_publisher.publish = AsyncMock()

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    with pytest.raises(ToolInputSchemaValidationError):
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)

    await asyncio.sleep(0)

    published_event = event_publisher.publish.await_args.args[0]
    assert len(published_event.schema_violations) == 1
    # path 截断(包含 <truncated> 标记)
    assert "<truncated>" in published_event.schema_violations[0]["path"]


# ---------------------------------------------------------------------------
# 7. event_publisher publish 异常被吞噬,不阻塞主流程
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_failure_does_not_block_main_flow() -> None:
    """fire-and-forget:即使 publish 抛异常,strict 模式正常抛 ToolInputSchemaValidationError"""
    tool_id = uuid.uuid4()
    tool = _make_tool(input_schema={"type": "object"}, tool_id=tool_id)
    wrapped = AsyncMock(spec=ToolExecutionServicePort)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_arguments.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(_make_violation(),),
    )

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool

    # publish 抛慢错误(100ms 后触发),验证不阻塞主流程
    async def _slow_publish(_event: Any) -> None:
        await asyncio.sleep(0.1)
        raise RuntimeError("publish failed")

    event_publisher = MagicMock()
    event_publisher.publish = _slow_publish

    validator = _build_validator(
        wrapped=wrapped,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=event_publisher,
    )
    context = _make_context()
    tool_call = _make_tool_call(tool_id, arguments={})

    start = asyncio.get_event_loop().time()
    with pytest.raises(ToolInputSchemaValidationError):
        await validator.execute(tool_id=tool_id, tool_call=tool_call, context=context)
    elapsed = asyncio.get_event_loop().time() - start

    # 验证 execute 在 100ms 内返回(publish 慢错误不阻塞主流程)
    assert elapsed < 0.1
