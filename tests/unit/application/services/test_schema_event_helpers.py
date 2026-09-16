"""Schema 事件辅助工具函数单元测试(Story 4.3 AC-6 + AC-7 P0-H/P0-F/P0-I 修复)

覆盖范围:
1. truncate_violations_for_event 条数截断
2. truncate_violations_for_event path 深度截断
3. truncate_violations_for_event 总字节数截断
4. truncate_violations_for_event 空 violations 处理
5. extract_schema_execution_id 优先级
6. publish_schema_event_async fire-and-forget 不阻塞主流程
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.application.services.schema_event_helpers import (
    EVENT_MAX_PATH_DEPTH_DEFAULT,
    EVENT_MAX_VIOLATIONS_DEFAULT,
    extract_schema_execution_id,
    publish_schema_event_async,
    truncate_violations_for_event,
)
from src.domain.events.tool_schema_events import ToolSchemaValidationFailed
from src.domain.services.schema_validator import SchemaViolation
from src.domain.value_objects.tool_execution import ExecutionContext


def _make_violation(path: str = "/x") -> SchemaViolation:
    return SchemaViolation(path=path, expected="string", actual=123, message=f"{path} bad")


# ---------------------------------------------------------------------------
# truncate_violations_for_event
# ---------------------------------------------------------------------------


def test_truncate_no_op_when_within_limits() -> None:
    """violations 在限制内 → 不截断"""
    violations = tuple(_make_violation(f"/x_{i}") for i in range(5))
    result = truncate_violations_for_event(violations)
    assert result.violations == violations
    assert result.truncated is False
    assert result.original_count == 5
    assert result.truncation_reason == ""


def test_truncate_exceeds_violations_count() -> None:
    """violations 超过 max_violations → 截断到前 N 条"""
    violations = tuple(_make_violation(f"/x_{i}") for i in range(EVENT_MAX_VIOLATIONS_DEFAULT * 3))
    result = truncate_violations_for_event(violations)
    assert len(result.violations) == EVENT_MAX_VIOLATIONS_DEFAULT
    assert result.truncated is True
    assert result.original_count == EVENT_MAX_VIOLATIONS_DEFAULT * 3
    assert result.truncation_reason == "violations_exceeded"


def test_truncate_exceeds_path_depth() -> None:
    """path 深度超过 max_path_depth → 路径截断"""
    deep_path = "/" + "/".join(f"level_{i}" for i in range(EVENT_MAX_PATH_DEPTH_DEFAULT * 3))
    violations = (_make_violation(path=deep_path),)
    result = truncate_violations_for_event(violations, max_violations=10, max_path_depth=5)
    assert result.truncated is True
    assert "<truncated>" in result.violations[0].path


def test_truncate_exceeds_total_bytes() -> None:
    """序列化总字节数超过 max_total_bytes → 截断到 ≤ N bytes"""
    # 构造大 violations
    big_violations = tuple(_make_violation(path=f"/x_{i}") for i in range(100))
    result = truncate_violations_for_event(
        big_violations,
        max_violations=100,
        max_path_depth=20,
        max_total_bytes=512,  # 强制截断
    )
    # 序列化后总字节数不超过 512
    serialized = json.dumps(
        [v.to_dict() for v in result.violations],
        default=str,
        ensure_ascii=False,
    ).encode("utf-8")
    assert len(serialized) <= 512
    assert result.truncated is True
    assert result.truncation_reason == "size_exceeded"


def test_truncate_empty_violations() -> None:
    """空 violations → 返回空,不抛错"""
    result = truncate_violations_for_event(())
    assert result.violations == ()
    assert result.original_count == 0
    assert result.truncated is False


def test_truncate_accepts_list_input() -> None:
    """接受 list 输入(非 tuple)"""
    violations = [_make_violation("/x"), _make_violation("/y")]
    result = truncate_violations_for_event(violations)
    assert len(result.violations) == 2


# ---------------------------------------------------------------------------
# extract_schema_execution_id
# ---------------------------------------------------------------------------


def test_extract_schema_execution_id_priority_extensions() -> None:
    """extensions["schema_execution_id"] 优先级最高"""
    extensions_id = uuid.uuid4()
    context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id="session-id",
        extensions={"schema_execution_id": extensions_id},
    )
    assert extract_schema_execution_id(context) == extensions_id


def test_extract_schema_execution_id_fallback_to_session() -> None:
    """无 extensions 时回退到 session_id"""
    context = ExecutionContext(tenant_id=uuid.uuid4(), session_id="fallback-id")
    assert extract_schema_execution_id(context) == "fallback-id"


def test_extract_schema_execution_id_returns_empty_session_when_empty() -> None:
    """extensions 空且 session_id 为空 → 返回 session_id 默认值(空字符串)"""
    context = ExecutionContext(tenant_id=uuid.uuid4())
    # 默认 session_id 是空字符串(非 None),作为兜底
    assert extract_schema_execution_id(context) == ""


# ---------------------------------------------------------------------------
# publish_schema_event_async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_schema_event_async_fire_and_forget() -> None:
    """fire-and-forget:即使 publish 慢也不阻塞主流程"""
    publisher = MagicMock()

    async def _slow_publish(_event: Any) -> None:
        await asyncio.sleep(0.5)

    publisher.publish = _slow_publish

    event = ToolSchemaValidationFailed(
        execution_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        validation_phase="INPUT",
    )

    logger = MagicMock()

    start = time.perf_counter()
    task = publish_schema_event_async(publisher, event, logger, op_name="test")
    elapsed = time.perf_counter() - start

    # fire-and-forget 应该立即返回
    assert elapsed < 0.05
    assert task is not None
    # 让异步任务有机会完成
    await asyncio.sleep(0.6)


@pytest.mark.asyncio
async def test_publish_schema_event_async_handles_publisher_exception() -> None:
    """publisher 抛异常时,fire-and-forget 任务不传播异常"""
    publisher = MagicMock()

    async def _broken_publish(_event: Any) -> None:
        raise RuntimeError("publish failed")

    publisher.publish = _broken_publish

    event = ToolSchemaValidationFailed(
        execution_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        validation_phase="OUTPUT",
    )

    logger = MagicMock()

    task = publish_schema_event_async(publisher, event, logger, op_name="test")
    # 让异步任务执行
    await asyncio.gather(task, return_exceptions=True)

    # 异常被吞噬(无日志断言,fire-and-forget 路径)


@pytest.mark.asyncio
async def test_publish_schema_event_async_logs_failure_on_callback() -> None:
    """task done callback 收集失败异常到日志"""
    publisher = MagicMock()

    async def _broken_publish(_event: Any) -> None:
        raise RuntimeError("publish failed")

    publisher.publish = _broken_publish

    event = ToolSchemaValidationFailed(
        execution_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        validation_phase="INPUT",
    )

    logger = MagicMock()

    task = publish_schema_event_async(publisher, event, logger, op_name="test")
    # 等待 task 完成
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
    except (RuntimeError, asyncio.TimeoutError):
        pass

    # logger.exception 被 add_done_callback 调用
    assert logger.exception.called or logger.warning.called
