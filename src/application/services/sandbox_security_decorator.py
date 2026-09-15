"""应用层 SandboxSecurityDecorator 模块（Story 4.4 Task 7)

包裹 SandboxExecutor 端口（不修改 4.1a 既有签名,沿用 4.3 装饰器模式）,
提供 4 项安全防护:

1. 超时控制(asyncio.wait_for) — 防止执行 hang
2. 重试机制(复用 _call_with_retry) — 4.3 经验抽取,最大 3 次指数退避
3. 会话配额检查 — 执行前校验 _running_count < MAX_CONCURRENT_CONTAINERS
4. session_id 注入防御 — 校验 ^[A-Za-z0-9_-]{1,64}$(防注入)

设计依据:
- 装饰器模式（Story 4.3 经验):不修改 ToolExecutionEngine.__init__,通过 composition_root
  注入时将 sandbox_executor 实例从 AioDockerSandboxAdapter 替换为 SandboxSecurityDecorator 包裹的实例
- 复用 _call_with_retry(retry_helpers.py:62)而非私有 _retry_call
- session_id 校验使用既有的 SESSION_ID_REGEX 实体常量
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.application.services.retry_helpers import (
    RetryPolicy,
    _call_with_retry,
)
from src.domain.entities.sandbox_session import SESSION_ID_REGEX
from src.domain.exceptions.sandbox_exceptions import (
    ContainerStopError,
    SandboxConfigurationError,
    SandboxError,
    SandboxQuotaExceededError,
    SandboxTimeoutError,
)
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.value_objects.container_spec import ContainerSpec

logger = logging.getLogger(__name__)

__all__ = ["SandboxSecurityDecorator"]


class SandboxSecurityDecorator(SandboxExecutor):
    """沙箱执行安全装饰器（Story 4.4 Task 7,包裹 SandboxExecutor)

    Attributes:
        _wrapped: 被装饰的 SandboxExecutor 实例
        _retry_policy: 重试策略(默认 RetryPolicy 默认值)
        _max_concurrent: 最大并发容器数(默认 50)
        _running_count: 当前活跃容器计数(实例变量)
    """

    def __init__(
        self,
        wrapped: SandboxExecutor,
        retry_policy: RetryPolicy | None = None,
        max_concurrent: int = 50,
    ) -> None:
        """初始化装饰器。

        Args:
            wrapped: 被装饰的 SandboxExecutor 实例
            retry_policy: 重试策略(默认 None → 使用 RetryPolicy 默认值)
            max_concurrent: 最大并发容器数(默认 50,触发 SandboxQuotaExceededError)
        """
        self._wrapped = wrapped
        self._retry_policy = retry_policy or RetryPolicy()
        self._max_concurrent = max_concurrent
        self._running_count = 0

    async def start_container(
        self,
        session_id: str,
        spec: ContainerSpec | None = None,
    ) -> None:
        """启动容器(装饰 wrapped.start_container)。

        4 项防护:
        1. session_id 注入防御(正则 ^[A-Za-z0-9_-]{1,64}$)
        2. 配额检查(_running_count < max_concurrent)
        3. 重试机制(复用 _call_with_retry)
        """
        # 防护 1:session_id 注入防御
        if not SESSION_ID_REGEX.match(session_id):
            raise SandboxConfigurationError(
                message=f"session_id must match ^[A-Za-z0-9_-]{{1,64}}$, got '{session_id}'",
                field_name="session_id",
                field_value=session_id,
                reason="invalid format (potential injection)",
            )

        # 防护 2:配额检查
        if self._running_count >= self._max_concurrent:
            raise SandboxQuotaExceededError(
                message=(f"Concurrent container count {self._running_count} >= max {self._max_concurrent}"),
                current_count=self._running_count,
                max_count=self._max_concurrent,
                tenant_id=None,
            )

        # 防护 3:重试机制(仅对可重试异常)
        async def _do_start() -> None:
            await self._wrapped.start_container(session_id, spec)
            self._running_count += 1

        await _call_with_retry(
            _do_start,
            self._retry_policy,
            on_failure_callback=self._on_start_failure,
            execution_id=None,
            tool_id=None,
            op_name="sandbox.start_container",
        )

    async def _on_start_failure(
        self,
        exc: Exception,
        current_attempt: int,
        max_attempts: int,
        will_retry: bool,
    ) -> None:
        """start_container 失败回调(异常吞噬不传播)。"""
        if will_retry:
            logger.warning(
                "start_container 失败,准备重试 %d/%d: %s",
                current_attempt,
                max_attempts,
                exc,
            )

    async def execute_code(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """执行代码(装饰 wrapped.execute_code)。

        4 项防护:
        1. session_id 注入防御
        2. 超时控制(asyncio.wait_for + timeout_sec)
        3. 重试机制(复用 _call_with_retry)
        """
        # 防护 1:session_id 注入防御
        if not SESSION_ID_REGEX.match(session_id):
            raise SandboxConfigurationError(
                message=f"session_id must match ^[A-Za-z0-9_-]{{1,64}}$, got '{session_id}'",
                field_name="session_id",
                field_value=session_id,
                reason="invalid format (potential injection)",
            )

        # 防护 2 + 3:超时控制 + 重试机制
        effective_timeout = timeout_sec if timeout_sec is not None else 30.0

        async def _do_execute() -> dict[str, Any]:
            try:
                return await asyncio.wait_for(
                    self._wrapped.execute_code(session_id, code, timeout_sec=timeout_sec),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError as exc:
                raise SandboxTimeoutError(
                    message=f"Execution timeout after {effective_timeout}s",
                    session_id=session_id,
                    timeout_sec=effective_timeout,
                ) from exc

        return await _call_with_retry(
            _do_execute,
            self._retry_policy,
            on_failure_callback=self._on_execute_failure,
            execution_id=None,
            tool_id=None,
            op_name="sandbox.execute_code",
        )

    async def _on_execute_failure(
        self,
        exc: Exception,
        current_attempt: int,
        max_attempts: int,
        will_retry: bool,
    ) -> None:
        """execute_code 失败回调(异常吞噬不传播)。"""
        if will_retry:
            logger.warning(
                "execute_code 失败,准备重试 %d/%d: %s",
                current_attempt,
                max_attempts,
                exc,
            )

    async def stop_container(self, session_id: str) -> None:
        """停止容器(装饰 wrapped.stop_container)。

        注:stop_container 不重试(破坏性操作)。
        """
        if not SESSION_ID_REGEX.match(session_id):
            raise SandboxConfigurationError(
                message=f"session_id must match ^[A-Za-z0-9_-]{{1,64}}$, got '{session_id}'",
                field_name="session_id",
                field_value=session_id,
                reason="invalid format (potential injection)",
            )

        try:
            await self._wrapped.stop_container(session_id)
            self._running_count = max(0, self._running_count - 1)
        except (ContainerStopError, SandboxError) as exc:
            logger.error("stop_container 失败 session=%s: %s", session_id, exc)
            raise

    async def is_container_running(self, session_id: str) -> bool:
        """检查容器是否运行(直接委托 wrapped)。"""
        if not SESSION_ID_REGEX.match(session_id):
            return False
        return await self._wrapped.is_container_running(session_id)

    async def health_check(self) -> bool:
        """健康检查(直接委托 wrapped,**不抛异常**)。"""
        return await self._wrapped.health_check()


__all__ = ["SandboxSecurityDecorator"]
