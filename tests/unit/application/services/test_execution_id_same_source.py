"""execution_id 全链同源守护测试（Story 4.7 决策 #16 / 代码审查 R1-F4 补交）

Task 6 循环 D 承诺的五断言（dev 周期实现落地但测试缺位——C 视角突变实验
证明 revert 生产代码零红，本文件补齐守护）：

1. 入口注入 spy：ToolExecutionService.execute 无条件路径注入 schema_execution_id
2. 引擎聚合 id 复用：预置注入 id → 引擎持久化的聚合 execution_id == 注入值
3. TOV 透传：389 触发时异常 context id == 注入值（真实 TOV 链）
4. 未注入兜底：无注入（且无合法 UUID session_id）时引擎新铸非空 id
   （优先级链：注入值 > session_id > 新铸——D-P3a 登记行为）
5. 条件注入负分支：已有注入不覆写（sentinel 保持原值）
6. 双未注入独立新铸：TOV 与引擎各自新铸（id 不同——4.3 既有语义钉死）

单测纪律：真实 ToolExecutionService/ToolExecutionEngine/ToolOutputValidator
类 + 可编程 LLM/Sandbox/仓储替身（Mock/Fake/Real 三层策略）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.schema_validator import SchemaValidatorPort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.services.retry_helpers import RetryPolicy
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_output_validator import ToolOutputValidator
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.exceptions import ToolResultValidationError
from src.domain.services.schema_validator import SchemaValidationResult, SchemaViolation
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolCall,
)

_TENANT = uuid.uuid4()


def _make_tool() -> Tool:
    """构造执行用 Tool 实体."""
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name="t",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema={},
        output_schema={"type": "object"},
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _make_llm() -> AsyncMock:
    """可编程 LLM（structured_generate 三阶段固定返回——Think/Code/Validate）."""
    llm = AsyncMock()

    async def _structured(prompt: str, config: Any = None, **kwargs: Any) -> str:
        return "ok"

    llm.structured_generate = AsyncMock(side_effect=_structured)
    return llm


def _make_sandbox() -> AsyncMock:
    """可编程沙箱（execute_code 恒成功）."""
    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock(return_value=None)
    sandbox.stop_container = AsyncMock(return_value=None)

    async def _exec(session_id: str, code: str) -> dict[str, Any]:
        return {"output": "OK_result"}

    sandbox.execute_code = AsyncMock(side_effect=_exec)
    return sandbox


class _RecordingRepo:
    """录制引擎持久化面：捕获 save 收到的 ToolExecution 聚合."""

    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, entity: Any) -> Any:
        self.saved.append(entity)
        return entity


def _make_engine(repo: _RecordingRepo) -> ToolExecutionEngine:
    """真实引擎（录制仓储注入——聚合 id 经 save 面可观测）."""
    from typing import cast

    return ToolExecutionEngine(
        llm_client=_make_llm(),
        sandbox=_make_sandbox(),
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0, max_delay_sec=0),
        tool_execution_repository=cast(Any, repo),
    )


@pytest.mark.asyncio
async def test_entry_point_injects_schema_execution_id() -> None:
    """断言①：链入口 ToolExecutionService.execute 注入 schema_execution_id."""
    tool = _make_tool()
    engine = AsyncMock()
    engine.execute = AsyncMock(return_value=MagicMock())

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool
    service = ToolExecutionService(registry=registry, tool_version_service=None, engine=engine)

    context = ExecutionContext(tenant_id=_TENANT)
    await service.execute(tool_id=tool.tool_id, tool_call=ToolCall(tool_id=tool.tool_id, arguments={}), context=context)

    injected = engine.execute.call_args_list[0].kwargs.get("context").extensions.get("schema_execution_id")
    assert isinstance(injected, uuid.UUID), f"入口应注入 UUID 形态 id，实际: {injected!r}"


@pytest.mark.asyncio
async def test_entry_point_does_not_overwrite_existing_id() -> None:
    """断言⑤：条件注入负分支——已有 schema_execution_id 不覆写（sentinel 保持原值）."""
    tool = _make_tool()
    engine = AsyncMock()
    engine.execute = AsyncMock(return_value=MagicMock())

    registry = MagicMock(spec=ToolRegistryServicePort)
    registry.get_tool.return_value = tool
    service = ToolExecutionService(registry=registry, tool_version_service=None, engine=engine)

    sentinel = uuid.uuid4()
    context = ExecutionContext(tenant_id=_TENANT).with_extension("schema_execution_id", sentinel)
    await service.execute(tool_id=tool.tool_id, tool_call=ToolCall(tool_id=tool.tool_id, arguments={}), context=context)

    received = engine.execute.call_args_list[0].kwargs.get("context").extensions.get("schema_execution_id")
    assert received == sentinel, "已有注入不覆写（R8-16 条件形态——防未来 TIV 入链时 INPUT/OUTPUT id 分裂）"


@pytest.mark.asyncio
async def test_engine_aggregate_id_reuses_injected_value() -> None:
    """断言②：引擎聚合 id 复用——预置注入 id → 持久化聚合 execution_id == 注入值."""
    tool = _make_tool()
    repo = _RecordingRepo()
    engine = _make_engine(repo)

    injected = uuid.uuid4()
    context = ExecutionContext(tenant_id=_TENANT).with_extension("schema_execution_id", injected)
    await engine.execute(
        tool_id=tool.tool_id,
        tool=tool,
        tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
        context=context,
    )

    assert repo.saved, "引擎应持久化聚合"
    assert repo.saved[0].execution_id == injected, "聚合 id 应复用链入口注入值（决策 #16）"


@pytest.mark.asyncio
async def test_engine_mints_fresh_id_when_uninjected() -> None:
    """断言④：未注入兜底——优先级链「注入值 > session_id > 新铸」的无前两级形态：
    无 schema_execution_id 且无合法 UUID session_id → 新铸非空 id."""
    tool = _make_tool()
    repo = _RecordingRepo()
    engine = _make_engine(repo)

    context = ExecutionContext(tenant_id=_TENANT)
    await engine.execute(
        tool_id=tool.tool_id,
        tool=tool,
        tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
        context=context,
    )

    assert repo.saved, "引擎应持久化聚合"
    minted = repo.saved[0].execution_id
    assert isinstance(minted, uuid.UUID) and minted, "未注入时兜底新铸非空 id"


@pytest.mark.asyncio
async def test_tov_389_context_id_matches_injected_value() -> None:
    """断言③：TOV 透传——校验耗尽 389 的 context execution_id == 注入值（真实 TOV 链）."""
    tool = _make_tool()
    repo = _RecordingRepo()
    engine = _make_engine(repo)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(SchemaViolation(path="/result", expected="string", actual=1, message="bad"),),
    )
    tov = ToolOutputValidator(
        wrapped=engine,
        schema_validator=schema_validator,
        event_publisher=None,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0, max_delay_sec=0),
    )

    injected = uuid.uuid4()
    context = ExecutionContext(tenant_id=_TENANT).with_extension("schema_execution_id", injected)
    with pytest.raises(ToolResultValidationError) as exc_info:
        await tov.execute(
            tool_id=tool.tool_id,
            tool=tool,
            tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
            context=context,
        )

    assert exc_info.value.context.get("execution_id") == str(injected), (
        "389 context id 应与注入值同源（决策 #16——TOV 零改动命中）"
    )
    # 聚合行 id 同源（引擎 save 面复核）
    assert repo.saved, "引擎应持久化聚合"
    assert repo.saved[0].execution_id == injected


@pytest.mark.asyncio
async def test_tov_and_engine_mint_independently_when_uninjected() -> None:
    """断言⑥：两级都未注入时 TOV 与引擎各自独立新铸（id 不同）——4.3 既有语义钉死
    （生产全路径经 ToolExecutionService.execute 注入，本形态仅直连链路可达）."""
    tool = _make_tool()
    repo = _RecordingRepo()
    engine = _make_engine(repo)

    schema_validator = MagicMock(spec=SchemaValidatorPort)
    schema_validator.validate_output.return_value = SchemaValidationResult(
        is_valid=False,
        violations=(SchemaViolation(path="/result", expected="string", actual=1, message="bad"),),
    )
    tov = ToolOutputValidator(
        wrapped=engine,
        schema_validator=schema_validator,
        event_publisher=None,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0, max_delay_sec=0),
    )

    context = ExecutionContext(tenant_id=_TENANT)
    with pytest.raises(ToolResultValidationError) as exc_info:
        await tov.execute(
            tool_id=tool.tool_id,
            tool=tool,
            tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
            context=context,
        )

    tov_id = exc_info.value.context.get("execution_id")
    engine_id = str(repo.saved[0].execution_id)
    assert tov_id and engine_id
    assert tov_id != engine_id, "双未注入时两级独立新铸（直连形态已知边界——D-P3a 注记）"
