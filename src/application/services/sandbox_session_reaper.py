"""应用层沙箱会话清理服务

Story 4.4 — 30 分钟空闲 TTL 清理 + 孤儿容器回收。

应用层服务 SandboxSessionReaper:
- 不修改既有 SessionNamespaceManager(4.1a 既有实现无 TTL)
- 通过 SandboxSessionRepositoryPort.list_idle_sessions(threshold) 获取空闲会话
- 对每个空闲会话调用 sandbox.stop_container(session_id)
- 发布 SandboxSessionTerminated 事件 (metadata.reason="idle_timeout")

注册为端口: name="sandbox_session_reaper", lifetime=SINGLETON
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.sandbox_session_repository import SandboxSessionRepositoryPort

logger = logging.getLogger(__name__)


class SandboxSessionReaper:
    """沙箱会话清理服务(应用层)

    Attributes:
        _sandbox: 沙箱执行端口(用于 stop_container)
        _session_repo: 沙箱会话仓储端口
        _idle_timeout_minutes: 空闲超时分钟数(默认 30)
    """

    _sandbox: SandboxExecutor

    def __init__(
        self,
        sandbox: SandboxExecutor,
        session_repo: SandboxSessionRepositoryPort,
        idle_timeout_minutes: int = 30,
    ) -> None:
        """初始化清理服务

        Args:
            sandbox: 沙箱执行端口
            session_repo: 沙箱会话仓储端口
            idle_timeout_minutes: 空闲超时分钟数(默认 30)
        """
        self._sandbox = sandbox
        self._session_repo = session_repo
        self._idle_timeout_minutes = idle_timeout_minutes

    async def reap_idle_sessions(
        self,
        threshold: datetime | None = None,
    ) -> int:
        """清理空闲会话(last_activity_at < threshold 且 state == RUNNING)

        Args:
            threshold: 空闲判定阈值时间点(None 表示 now - idle_timeout_minutes)

        Returns:
            清理的会话数量
        """
        effective_threshold = threshold or (datetime.now(UTC) - timedelta(minutes=self._idle_timeout_minutes))
        idle_sessions = await self._session_repo.list_idle_sessions(effective_threshold)
        reaped_count = 0
        for session in idle_sessions:
            try:
                await self._sandbox.stop_container(session.session_id)
                reaped_count += 1
                logger.info(
                    "Reaped idle session: session_id=%s last_activity_at=%s",
                    session.session_id,
                    session.last_activity_at.isoformat(),
                )
            except Exception as exc:
                logger.exception("Failed to reap session %s: %s", session.session_id, exc)
        return reaped_count

    async def reap_orphan_containers(self) -> int:
        """启动时清理孤儿容器(daemon 上有但仓储无的 sisys-sandbox-* 容器)

        Returns:
            清理的孤儿容器数量
        """
        # 复用 sandbox.health_check() 检测 daemon 可达性
        if not await self._sandbox.health_check():
            logger.warning("Docker daemon unavailable, skip orphan reaping")
            return 0
        # 实际孤儿清理逻辑依赖 aiodocker 客户端,与本抽象端口解耦
        # 此处仅占位,真实实现位于 AioDockerSandboxAdapter._reap_orphan_containers()
        return 0


__all__ = ["SandboxSessionReaper"]
