"""应用层重试工具函数模块

定义 _call_with_retry(func, retry_policy, on_failure_callback) 共享工具函数,
供 ToolExecutionEngine._retry_call 与 ToolOutputValidator 装饰器共享重试逻辑。

设计依据：Story 4.3 AC-3 / AC-7
- 抽离 _call_with_retry 共享工具函数,避免 Engine 私有方法被装饰器访问
- 指数退避(沿用 4.1a ToolExecutionEngine._compute_backoff 行为)
- on_failure_callback 在每次失败时调用,异常吞噬不传播
- execution_id / tool_id / op_name 透传到异常 context 与日志
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal, Optional, TypeVar

from src.domain.exceptions import (
    ExecutionError,
    LLMAPIError,
    LLMResponseError,
    TimeoutError,
    ToolExecutionRetryExhaustedError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
OnFailureCallback = Callable[[Exception, int, int, bool], Awaitable[None]]
"""失败回调协议:(exception, current_attempt, max_attempts, will_retry) -> awaitable None"""


@dataclass(frozen=True)
class RetryPolicy:
    """重试策略 frozen dataclass(从 tool_execution_engine 抽离到 retry_helpers)

    Attributes:
        max_attempts: 最大尝试次数(默认 3)
        backoff_strategy: 退避策略(exponential / linear / constant)
        initial_delay_sec: 初始延迟秒数(默认 1.0)
        max_delay_sec: 最大延迟秒数(默认 30.0)
        max_total_duration_sec: 总时长上限秒数(默认 120.0)
        retryable_exceptions: 可重试异常类型元组
    """

    max_attempts: int = 3
    backoff_strategy: Literal["exponential", "linear", "constant"] = "exponential"
    initial_delay_sec: float = 1.0
    max_delay_sec: float = 30.0
    max_total_duration_sec: float = 120.0
    retryable_exceptions: tuple[type[Exception], ...] = (
        LLMAPIError,
        LLMResponseError,
        ExecutionError,
        TimeoutError,
    )


async def _call_with_retry(
    func: Callable[[], Awaitable[T]],
    retry_policy: RetryPolicy,
    on_failure_callback: Optional[OnFailureCallback] = None,
    *,
    execution_id: str | None = None,
    tool_id: uuid.UUID | None = None,
    op_name: str = "retry_call",
) -> T:
    """带指数退避的重试调用(共享工具函数)

    Args:
        func: 无参异步函数,返回 T
        retry_policy: RetryPolicy(max_attempts + backoff_strategy + retryable_exceptions)
        on_failure_callback: 失败回调(异常 + 当前 attempt + max + will_retry);异常吞噬不传播
        execution_id: 透传到 ToolExecutionRetryExhaustedError context
        tool_id: 透传到 ToolExecutionRetryExhaustedError context
        op_name: 操作名(用于日志 + metrics)

    Returns:
        func() 调用结果

    Raises:
        ToolExecutionRetryExhaustedError: 重试耗尽
    """
    last_exc: Exception | None = None
    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            return await func()
        except retry_policy.retryable_exceptions as exc:
            last_exc = exc
            will_retry = attempt < retry_policy.max_attempts
            # 调用失败回调(异常吞噬不传播)
            if on_failure_callback is not None:
                try:
                    await on_failure_callback(exc, attempt, retry_policy.max_attempts, will_retry)
                except Exception as cb_exc:  # pragma: no cover - 回调自身异常吞噬
                    logger.exception("[%s] on_failure_callback raised: %s", op_name, cb_exc)
            if not will_retry:
                break
            delay = _compute_backoff(retry_policy, attempt)
            logger.warning(
                "[%s] 重试 %d/%d after %.2fs: %s",
                op_name,
                attempt,
                retry_policy.max_attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    raise ToolExecutionRetryExhaustedError(
        retry_count=retry_policy.max_attempts,
        execution_id=execution_id,
        tool_id=str(tool_id) if tool_id is not None else None,
        cause=last_exc,
    )


def _compute_backoff(retry_policy: RetryPolicy, attempt: int) -> float:
    """计算退避延迟(指数 / 线性 / 常量)"""
    if retry_policy.backoff_strategy == "exponential":
        delay: float = retry_policy.initial_delay_sec * (2 ** (attempt - 1))
    elif retry_policy.backoff_strategy == "linear":
        delay = retry_policy.initial_delay_sec * attempt
    else:  # constant
        delay = retry_policy.initial_delay_sec
    return min(delay, retry_policy.max_delay_sec)


__all__ = ["_call_with_retry", "OnFailureCallback", "RetryPolicy"]
