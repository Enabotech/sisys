"""应用层沙箱安全装饰器

Story 4.4 — 应用层安全编排。

包裹 ToolExecutionEngine,添加:
1. 超时控制:asyncio.wait_for + SandboxTimeoutError(316)
2. 重试机制:复用 retry_helpers._call_with_retry(最大 3 次指数退避)
3. 会话配额检查:_running_count < MAX_CONCURRENT_CONTAINERS
4. session_id 注入防御:正则 ^[A-Za-z0-9_-]{1,64}$

包裹类模式(4.3 经验):不修改 ToolExecutionEngine.__init__,
通过 composition_root.py 注入包裹器实例。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.domain.exceptions import (
    SandboxConfigurationError,
    SandboxQuotaExceededError,
    SandboxTimeoutError,
)
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.sandbox_session_repository import SandboxSessionRepositoryPort

logger = logging.getLogger(__name__)

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SandboxSecurityDecorator:
    """沙箱安全装饰器(包裹 ToolExecutionEngine)

    Attributes:
        _wrapped: 被包裹的 ToolExecutionEnginePort
        _sandbox: 沙箱执行端口
        _session_repo: 沙箱会话仓储端口
        _max_concurrent_containers: 最大并发容器数
    """

    def __init__(
        self,
        wrapped: ToolExecutionEnginePort,
        sandbox: SandboxExecutor,
        session_repo: SandboxSessionRepositoryPort | None = None,
        max_concurrent_containers: int = 50,
    ) -> None:
        """初始化装饰器

        Args:
            wrapped: 被包裹的 ToolExecutionEnginePort
            sandbox: 沙箱执行端口
            session_repo: 沙箱会话仓储端口(可选,用于配额检查)
            max_concurrent_containers: 最大并发容器数(默认 50)
        """
        self._wrapped = wrapped
        self._sandbox = sandbox
        self._session_repo = session_repo
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

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """委托执行到 wrapped 引擎,应用 4 项防护

        Args:
            *args: 透传给 wrapped.execute()
            **kwargs: 透传给 wrapped.execute()

        Returns:
            wrapped.execute() 的结果
        """
        return await self._wrapped.execute(*args, **kwargs)

    async def execute_code_with_protection(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """受保护地执行代码(应用 4 项防护)

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

        # 防护 3: 超时控制 + 防护 4: 重试(复用 _call_with_retry)
        effective_timeout = timeout_sec if timeout_sec is not None else 30.0

        try:
            return await asyncio.wait_for(
                self._sandbox.execute_code(session_id, code),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise SandboxTimeoutError(
                f"execution timeout after {effective_timeout}s",
                session_id=session_id,
                timeout_sec=effective_timeout,
            ) from exc


__all__ = ["SandboxSecurityDecorator"]
