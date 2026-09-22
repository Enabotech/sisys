"""应用层沙箱安全装饰器

Story 4.4 — 应用层安全编排。

包裹 ToolExecutionEngine,添加:
1. 超时控制:asyncio.wait_for + SandboxTimeoutError(316)
2. 重试机制:复用 retry_helpers._call_with_retry(最大 3 次指数退避,
   显式白名单 (ContainerStartError,) — 仅瞬时启动/拉取故障可重试;
   ExecutionError 全族(313/316/317)与 318/319 为确定性失败不重试)
3. 会话配额检查:_running_count < MAX_CONCURRENT_CONTAINERS
4. session_id 注入防御:正则 ^[A-Za-z0-9_-]{1,64}$
5. 失败事件发布:捕获 ExecutionError 家族(含因果链解包)后发布 SandboxExecutionFailed

包裹类模式(4.3 经验):不修改 ToolExecutionEngine.__init__,
通过 composition_root.py 注入包裹器实例。
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any

from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.application.services.retry_helpers import RetryPolicy, _call_with_retry
from src.domain.events.sandbox_events import SandboxExecutionFailed
from src.domain.exceptions import (
    ContainerStartError,
    ExecutionError,
    SandboxConfigurationError,
    SandboxQuotaExceededError,
    SandboxTimeoutError,
)
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.sandbox_session_repository import SandboxSessionRepositoryPort

logger = logging.getLogger(__name__)

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# AC-7 职责 2 重试白名单: 仅容器启动/镜像拉取等瞬时 daemon 故障可重试;
# 排除 ExecutionError 全族(313 用户代码失败/316 超时/317 OOM 均为确定性失败,
# 重试与"超时即销毁"契约冲突)与 318/319(配额/配置错误)
_SANDBOX_RETRY_POLICY = RetryPolicy(retryable_exceptions=(ContainerStartError,))


class SandboxSecurityDecorator:
    """沙箱安全装饰器(包裹 ToolExecutionEngine)

    Attributes:
        _wrapped: 被包裹的 ToolExecutionEnginePort
        _sandbox: 沙箱执行端口
        _session_repo: 沙箱会话仓储端口(配额检查依赖 count_active())
        _event_publisher: 事件发布端口(可选,注入后失败时发布 SandboxExecutionFailed)
        _retry_policy: 重试策略(默认 _SANDBOX_RETRY_POLICY)
        _max_concurrent_containers: 最大并发容器数
    """

    def __init__(
        self,
        wrapped: ToolExecutionEnginePort,
        sandbox: SandboxExecutor,
        session_repo: SandboxSessionRepositoryPort | None = None,
        event_publisher: EventPublisher | None = None,
        retry_policy: RetryPolicy | None = None,
        max_concurrent_containers: int = 50,
    ) -> None:
        """初始化装饰器

        Args:
            wrapped: 被包裹的 ToolExecutionEnginePort
            sandbox: 沙箱执行端口
            session_repo: 沙箱会话仓储端口(可选,用于配额检查)
            event_publisher: 事件发布端口(可选)
            retry_policy: 重试策略(可选,默认仅 ContainerStartError 白名单)
            max_concurrent_containers: 最大并发容器数(默认 50)
        """
        self._wrapped = wrapped
        self._sandbox = sandbox
        self._session_repo = session_repo
        self._event_publisher = event_publisher
        self._retry_policy = retry_policy or _SANDBOX_RETRY_POLICY
        self._max_concurrent_containers = max_concurrent_containers

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """session_id 注入防御"""
        if not SESSION_ID_PATTERN.match(session_id):
            raise SandboxConfigurationError(
                f"session_id must match {SESSION_ID_PATTERN.pattern}",
                field_name="session_id",
                field_value=session_id,
                reason_detail="regex mismatch",
            )

    @staticmethod
    def _unwrap_sandbox_error(exc: BaseException) -> ExecutionError | None:
        """沿因果链解包,返回首个沙箱执行失败异常(ExecutionError 家族 313/316/317)

        判级顺序对齐 DomainError 基类既有约定(cause → __cause__ → __context__);
        命中即停(不取叶子),保留 316/317 的精确分类。

        Args:
            exc: 待解包异常(如 ToolExecutionFailedError / ToolExecutionRetryExhaustedError)

        Returns:
            首个 ExecutionError 家族异常;未命中返回 None
        """
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, ExecutionError):
                return current
            current = getattr(current, "cause", None) or current.__cause__ or current.__context__
        return None

    async def _publish_execution_failed(self, session_id: str, exc: ExecutionError) -> None:
        """best-effort 发布 SandboxExecutionFailed 事件(失败仅记日志)

        Args:
            session_id: 会话 ID
            exc: 沙箱执行失败异常(313/316/317)
        """
        if self._event_publisher is None:
            return
        try:
            await self._event_publisher.publish(
                SandboxExecutionFailed(
                    session_id=session_id,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            )
        except Exception:
            logger.warning("发布 SandboxExecutionFailed 失败 session=%s", session_id)

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Any,
        tool_call: Any,
        context: Any,
    ) -> Any:
        """委托执行到 wrapped 引擎,应用安全防护

        在五阶段工作流执行前:
        1. session_id 注入防御(从 context.session_id 提取并校验)
        2. 并发容器配额检查(从 session_repo 查询活跃数)

        超时控制由 AioDockerSandboxAdapter.execute_code 内部的
        asyncio.wait_for 实现,此处不重复包装。
        失败时沿因果链解包 ExecutionError 家族并发布 SandboxExecutionFailed
        (318/319 属执行前守卫拒绝,不发布执行失败事件)。

        Args:
            tool_id: 工具 ID
            tool: 工具实体
            tool_call: 工具调用请求
            context: 执行上下文(含 session_id)

        Returns:
            wrapped.execute() 的结果

        Raises:
            SandboxConfigurationError: session_id 非法
            SandboxQuotaExceededError: 并发容器数超配额
        """
        # 防护 1: session_id 注入防御
        session_id = getattr(context, "session_id", "")
        if session_id:
            self._validate_session_id(session_id)

        # 防护 2: 配额检查
        if self._session_repo is not None:
            active_count = await self._session_repo.count_active()
            if active_count >= self._max_concurrent_containers:
                raise SandboxQuotaExceededError(
                    "concurrent container limit reached",
                    current_count=active_count,
                    max_count=self._max_concurrent_containers,
                )

        try:
            return await self._wrapped.execute(tool_id, tool, tool_call, context)
        except Exception as exc:
            # 防护 5: 解包因果链,沙箱执行失败(313/316/317)发布事件后原样上浮
            sandbox_error = self._unwrap_sandbox_error(exc)
            if sandbox_error is not None:
                await self._publish_execution_failed(session_id or "", sandbox_error)
            raise

    async def execute_code_with_protection(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """受保护地执行代码(应用 5 项防护)

        Args:
            session_id: 会话 ID
            code: 待执行代码
            timeout_sec: 超时秒数(默认 None → 使用 30s)

        Returns:
            执行结果字典

        Raises:
            SandboxConfigurationError: session_id 非法
            SandboxQuotaExceededError: 并发容器数超配额
            SandboxTimeoutError: 执行超时
        """
        # 防护 1: session_id 注入防御
        self._validate_session_id(session_id)

        # 防护 2: 配额检查
        if self._session_repo is not None:
            active_count = await self._session_repo.count_active()
            if active_count >= self._max_concurrent_containers:
                raise SandboxQuotaExceededError(
                    "concurrent container limit reached",
                    current_count=active_count,
                    max_count=self._max_concurrent_containers,
                )

        # 防护 3: 超时控制(每次重试尝试独立计时) + 防护 4: 重试(_call_with_retry 白名单收窄)
        effective_timeout = timeout_sec if timeout_sec is not None else 30.0

        async def _attempt() -> dict[str, Any]:
            return await asyncio.wait_for(
                self._sandbox.execute_code(session_id, code, timeout_sec=timeout_sec),
                timeout=effective_timeout,
            )

        try:
            return await _call_with_retry(
                _attempt,
                self._retry_policy,
                op_name="sandbox_execute_code",
            )
        except asyncio.TimeoutError as exc:
            timeout_error = SandboxTimeoutError(
                f"execution timeout after {effective_timeout}s",
                session_id=session_id,
                timeout_sec=effective_timeout,
            )
            await self._publish_execution_failed(session_id, timeout_error)
            raise timeout_error from exc
        except Exception as exc:
            # 防护 5: 沙箱执行失败(313/316/317,含重试耗尽因果链)发布事件后原样上浮
            sandbox_error = self._unwrap_sandbox_error(exc)
            if sandbox_error is not None:
                await self._publish_execution_failed(session_id, sandbox_error)
            raise


__all__ = ["SandboxSecurityDecorator"]
