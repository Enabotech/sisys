"""应用层 Schema 事件辅助工具模块

为 ToolInputValidator / ToolOutputValidator 装饰器共享的工具函数:
- execution_id 透传:确保 INPUT / OUTPUT 事件使用同一 execution_id(P0-F 修复)
- payload 大小门禁:截断 violations 列表防止 DoS(P0-H 修复)
- 事件异步发布:fire-and-forget 不阻塞主流程(P0-I 修复)

设计依据:Story 4.3 AC-3 + AC-6 + AC-7
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from src.domain.events.tool_schema_events import ToolSchemaValidationFailed
from src.domain.ports.event_publisher import EventPublisher
from src.domain.services.schema_validator import SchemaViolation
from src.domain.value_objects.tool_execution import ExecutionContext

logger = logging.getLogger(__name__)

# P0-I 修复:模块级 _background_tasks 集合持有 task 强引用,防止 fire-and-forget task
# 被 GC 回收导致事件丢失(PEP 3156 规定 task 必须有强引用);task 完成时自动 discard
_background_tasks: set[asyncio.Task[None]] = set()


# P0-H:事件 payload 大小门禁常量(对标 Story AC-6 验证清单)
EVENT_MAX_VIOLATIONS_DEFAULT = 10
EVENT_MAX_PATH_DEPTH_DEFAULT = 10
EVENT_MAX_TOTAL_BYTES_DEFAULT = 16 * 1024  # 16 KB


@dataclass(frozen=True)
class TruncatedViolations:
    """事件 payload 截断结果

    Attributes:
        violations: 截断后的 violations 列表(已截断 path 深度)
        truncated: 是否发生截断(用于监控告警)
        original_count: 原始 violations 数量
        truncation_reason: 截断原因(violations_exceeded / path_truncated / size_exceeded)
    """

    violations: tuple[SchemaViolation, ...] = ()
    truncated: bool = False
    original_count: int = 0
    truncation_reason: str = ""


def truncate_violations_for_event(
    violations: tuple[SchemaViolation, ...] | list[SchemaViolation],
    *,
    max_violations: int = EVENT_MAX_VIOLATIONS_DEFAULT,
    max_path_depth: int = EVENT_MAX_PATH_DEPTH_DEFAULT,
    max_total_bytes: int = EVENT_MAX_TOTAL_BYTES_DEFAULT,
) -> TruncatedViolations:
    """截断 violations 用于事件发布(P0-H 修复)

    截断规则:
    1. 超过 max_violations → 截断到前 max_violations 条
    2. 单条 violation.path 深度超过 max_path_depth → 截断 path(保留前缀 + '.../<truncated>')
    3. 序列化后总字节数超过 max_total_bytes → 进一步截断直到 ≤ max_total_bytes

    Args:
        violations: 原始 violations 列表
        max_violations: violations 条数上限(默认 10)
        max_path_depth: path 深度上限(默认 10)
        max_total_bytes: 事件总字节数上限(默认 16 KB)

    Returns:
        TruncatedViolations: 截断结果(用于事件 payload)
    """
    original_count = len(violations)
    truncated = False
    reason = ""

    # 1) 截断 violations 条数
    if len(violations) > max_violations:
        violations = violations[:max_violations]
        truncated = True
        reason = "violations_exceeded"

    # 2) 截断 path 深度
    if max_path_depth > 0:
        path_truncated_list: list[SchemaViolation] = []
        for v in violations:
            parts = v.path.split("/") if v.path else [""]
            if len(parts) > max_path_depth:
                truncated_path = "/".join(parts[:max_path_depth]) + "/...<truncated>"
                path_truncated_list.append(
                    SchemaViolation(
                        path=truncated_path,
                        expected=v.expected,
                        actual=v.actual,
                        message=v.message,
                    ),
                )
                truncated = True
                if not reason:
                    reason = "path_truncated"
            else:
                path_truncated_list.append(v)
        violations = tuple(path_truncated_list)

    # 3) 截断总字节数(保留最早的 N 条,与 violations_exceeded 方向一致)
    if max_total_bytes > 0:
        # 二分查找最大可保留条数(保留最早 N 条)
        # 时间复杂度 O(log N) 次 json.dumps;相比线性 pop 提升显著
        lo, hi = 0, len(violations)
        max_kept = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = violations[:mid]
            serialized_bytes = len(
                json.dumps([v.to_dict() for v in candidate], default=str, ensure_ascii=False).encode("utf-8"),
            )
            if serialized_bytes <= max_total_bytes:
                max_kept = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if max_kept < len(violations):
            violations = violations[:max_kept]
            truncated = True
            reason = "size_exceeded"

    return TruncatedViolations(
        violations=tuple(violations),
        truncated=truncated,
        original_count=original_count,
        truncation_reason=reason,
    )


def extract_schema_execution_id(context: ExecutionContext) -> Any | None:
    """从 ExecutionContext 提取 schema execution_id(P0-F 修复 + Round 3 类型安全)

    优先级:
    1. context.extensions["schema_execution_id"](装饰器间透传)
    2. context.session_id(向下兼容既有 session 维度,仅当是合法 UUID 字符串时)

    Returns:
        execution_id(uuid.UUID 实例),否则 None
        (Round 3 P0-2:统一返回 UUID 类型,避免传给 ToolSchemaValidationFailed.execution_id 触发 TypeError)
    """
    import uuid as _uuid

    extensions = getattr(context, "extensions", None) or {}
    if "schema_execution_id" in extensions:
        extracted = extensions["schema_execution_id"]
        if isinstance(extracted, _uuid.UUID):
            return extracted
        # 字符串 → 尝试转 UUID,失败则生成新 UUID
        if isinstance(extracted, str):
            try:
                return _uuid.UUID(extracted)
            except (ValueError, AttributeError):
                return _uuid.uuid4()
        return _uuid.uuid4()
    # session_id fallback:仅当合法 UUID 时才用,否则 None(强制重新生成)
    session_id = getattr(context, "session_id", None)
    if isinstance(session_id, _uuid.UUID):
        return session_id
    if isinstance(session_id, str) and session_id:
        try:
            return _uuid.UUID(session_id)
        except (ValueError, AttributeError):
            return None
    return None


def publish_schema_event_async(
    event_publisher: EventPublisher,
    event: ToolSchemaValidationFailed,
    log: logging.Logger,
    *,
    op_name: str,
) -> asyncio.Task[None]:
    """异步发布 Schema 验证事件(P0-I 修复)

    使用 asyncio.create_task 实现 fire-and-forget:
    - 不阻塞装饰器主流程
    - 模块级 _background_tasks 持有 task 强引用,防止 GC 回收丢失事件
    - 任务异常通过 add_done_callback 统一收集日志(单一日志路径)

    Args:
        event_publisher: 事件发布器
        event: 待发布事件
        log: 日志记录器
        op_name: 操作名(用于日志上下文)

    Returns:
        asyncio.Task 引用(供测试断言完成)
    """

    async def _publish() -> None:
        # 异常不在此处理:由 add_done_callback 统一捕获,避免双日志
        await event_publisher.publish(event)

    task = asyncio.create_task(_publish())
    # 模块级 set 持有强引用,防止事件循环关闭前 GC(task 必须有强引用,PEP 3156)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # 异常捕获统一通过 add_done_callback 收集到日志(显式函数避免 mypy lambda 返回值误判)
    def _log_task_exception(t: asyncio.Task[None]) -> None:
        exc = t.exception()
        if exc is not None:
            log.exception("[%s] fire-and-forget publish task failed: %s", op_name, exc)

    task.add_done_callback(_log_task_exception)
    return task


async def drain_schema_events(timeout: float = 5.0) -> None:
    """优雅排空所有挂起的 schema 事件 task(Round 4 P0-3 修复)

    在 graceful shutdown / 测试 fixture teardown 时调用,
    等待所有 _background_tasks 完成(或超时),避免事件丢失。

    Args:
        timeout: 等待超时秒数(默认 5.0)
    """
    if not _background_tasks:
        return
    pending = list(_background_tasks)
    try:
        await asyncio.wait_for(
            asyncio.gather(*pending, return_exceptions=True),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "drain_schema_events timeout after %.2fs, %d pending tasks cancelled",
            timeout,
            len(pending),
        )
        for t in pending:
            if not t.done():
                t.cancel()


__all__ = [
    "TruncatedViolations",
    "EVENT_MAX_VIOLATIONS_DEFAULT",
    "EVENT_MAX_PATH_DEPTH_DEFAULT",
    "EVENT_MAX_TOTAL_BYTES_DEFAULT",
    "truncate_violations_for_event",
    "extract_schema_execution_id",
    "publish_schema_event_async",
    "drain_schema_events",
]
