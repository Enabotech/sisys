"""SISYS 基础设施层会话命名空间管理器模块。

管理会话到命名空间的映射和资源限制，确保相同会话的任务在同一命名空间中运行。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.ports.sandbox_port import SandboxExecutor

logger = logging.getLogger(__name__)


class SessionNamespaceManager:
    """会话命名空间管理器。

    负责会话到命名空间的映射、资源限制执行、活跃会话跟踪和资源清理。

    Attributes:
        _sandbox: 沙箱执行器实例（可选，用于容器管理）
        _active_sessions: 活跃会话字典，键为会话 ID，值为会话状态信息
    """

    def __init__(self, sandbox: SandboxExecutor | None = None):
        """初始化会话命名空间管理器。

        Args:
            sandbox: 沙箱执行器实例，None 时用于测试
        """
        self._sandbox = sandbox
        self._active_sessions: dict[str, dict[str, Any]] = {}

    async def get_or_create_namespace(self, session_id: str) -> str:
        """获取已有命名空间或为新会话创建命名空间。

        Args:
            session_id: 会话标识符

        Returns:
            命名空间标识符（与 session_id 相同）
        """
        if session_id in self._active_sessions:
            logger.debug("Reusing namespace for session: %s", session_id)
            return session_id

        # Create new namespace
        if self._sandbox:
            await self._sandbox.start_container(session_id)

        self._active_sessions[session_id] = {
            "namespace": session_id,
            "created_at": "now",  # Would use datetime in production
            "resource_usage": {"cpu": 0, "memory": 0},
        }

        logger.info("Created namespace for session: %s", session_id)
        return session_id

    async def release_namespace(self, session_id: str) -> None:
        """释放命名空间并清理会话资源。

        Args:
            session_id: 会话标识符
        """
        if session_id not in self._active_sessions:
            logger.debug("No namespace to release for session: %s", session_id)
            return

        if self._sandbox:
            await self._sandbox.stop_container(session_id)

        del self._active_sessions[session_id]
        logger.info("Released namespace for session: %s", session_id)

    def get_active_sessions(self) -> list[str]:
        """获取活跃会话 ID 列表。

        Returns:
            活跃会话 ID 列表
        """
        return list(self._active_sessions.keys())

    def is_session_active(self, session_id: str) -> bool:
        """检查会话是否活跃。

        Args:
            session_id: 会话标识符

        Returns:
            活跃返回 True，否则返回 False
        """
        return session_id in self._active_sessions

    async def update_resource_usage(
        self,
        session_id: str,
        cpu_delta: float = 0,
        memory_delta: int = 0,
    ) -> None:
        """更新会话的资源使用量。

        Args:
            session_id: 会话标识符
            cpu_delta: CPU 使用增量（核数）
            memory_delta: 内存使用增量（字节）
        """
        if session_id not in self._active_sessions:
            logger.warning("Cannot update resources for unknown session: %s", session_id)
            return

        self._active_sessions[session_id]["resource_usage"]["cpu"] += cpu_delta
        self._active_sessions[session_id]["resource_usage"]["memory"] += memory_delta

        logger.debug(
            "Updated resources: session_id=%s cpu=%.2f memory=%d",
            session_id,
            self._active_sessions[session_id]["resource_usage"]["cpu"],
            self._active_sessions[session_id]["resource_usage"]["memory"],
        )
