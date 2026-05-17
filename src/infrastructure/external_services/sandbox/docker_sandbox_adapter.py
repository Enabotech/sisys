"""SISYS 基础设施层 Docker 沙箱适配器模块

使用 Docker 容器提供沙箱化代码执行能力，支持 CPU/内存/网络/文件系统隔离

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.ports.sandbox_port import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxExecutor,
)

logger = logging.getLogger(__name__)


class DockerSandboxAdapter(SandboxExecutor):
    """基于 Docker 的沙箱执行适配器

    使用 Docker 容器提供任务执行隔离，每个会话获得独立容器和资源限制

    Attributes:
        _running_containers: 正在运行的容器状态字典（类级别共享）

    Note:
        资源限制 — CPU: 1 核, 内存: 512MB, 网络: 禁用, 文件系统: 隔离临时目录
    """

    _running_containers: dict[str, bool] = {}

    async def start_container(self, session_id: str) -> None:
        """启动指定会话的 Docker 容器

        Args:
            session_id: 会话唯一标识符

        Raises:
            ContainerStartError: 容器启动失败时抛出
        """
        if session_id in self._running_containers and self._running_containers[session_id]:
            logger.debug("Container already running for session: %s", session_id)
            return

        try:
            # For MVP: mock container startup
            # In production, this would use Docker SDK:
            # docker_client.containers.run(
            #     "python:3.11-slim",
            #     detach=True,
            #     mem_limit="512m",
            #     cpu_period=100000,
            #     cpu_quota=100000,
            #     network_mode="none",
            #     volumes={temp_dir: {"bind": "/workspace", "mode": "rw"}},
            #     name=f"sisys-sandbox-{session_id}",
            # )
            logger.info("Started container for session: %s", session_id)
            self._running_containers[session_id] = True

        except Exception as e:
            logger.error("Failed to start container for session %s: %s", session_id, e)
            raise ContainerStartError(f"Failed to start container: {e}") from e

    async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
        """在 Docker 沙箱中执行代码

        Args:
            session_id: 会话标识符
            code: 待执行的 Python 代码

        Returns:
            执行结果字典，包含 status/output/error/execution_time_ms

        Raises:
            ExecutionError: 执行失败时抛出
        """
        if session_id not in self._running_containers or not self._running_containers[session_id]:
            raise ExecutionError(f"No running container for session: {session_id}")

        try:
            # For MVP: mock execution
            # In production, this would use Docker SDK exec_create/exec_start
            logger.debug("Executing code in sandbox: session_id=%s", session_id)

            # Simulate execution
            result: dict[str, Any] = {
                "status": "completed",
                "output": "Code executed successfully",
                "error": None,
                "execution_time_ms": 100,
            }

            logger.info("Code execution completed: session_id=%s", session_id)
            return result

        except Exception as e:
            logger.error("Execution failed: session_id=%s error=%s", session_id, e)
            raise ExecutionError(f"Execution failed: {e}") from e

    async def stop_container(self, session_id: str) -> None:
        """停止并移除 Docker 容器

        Args:
            session_id: 会话标识符

        Raises:
            ContainerStopError: 容器停止失败时抛出
        """
        if session_id not in self._running_containers:
            logger.debug("No container to stop for session: %s", session_id)
            return

        try:
            # For MVP: mock container stop
            # In production: docker_client.containers.get(name).remove(force=True)
            logger.info("Stopped container for session: %s", session_id)
            self._running_containers[session_id] = False

        except Exception as e:
            logger.error("Failed to stop container for session %s: %s", session_id, e)
            raise ContainerStopError(f"Failed to stop container: {e}") from e

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行

        Args:
            session_id: 会话标识符

        Returns:
            正在运行返回 True，否则返回 False
        """
        return self._running_containers.get(session_id, False)

    @classmethod
    def reset_all_containers(cls) -> None:
        """重置所有容器状态（仅用于测试）"""
        cls._running_containers.clear()
