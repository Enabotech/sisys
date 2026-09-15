"""应用层 SandboxSessionReaper 服务（Story 4.4 Task 6)

实现沙箱会话 30 分钟空闲 TTL 清理 + 启动时孤儿容器扫描。

设计依据:
- 新建独立应用层服务,不修改既有 SessionNamespaceManager(4.1a 既有无 TTL)
- 阈值从 settings 读取,非硬编码 30 分钟(CLAUDE.md §2 Simplicity First)
- reap_idle_sessions 返回清理数量,便于监控告警
- 启动时孤儿容器扫描:扫描 daemon 上所有 sisys-sandbox-* 容器,
  与本地 SandboxSession 仓储对比,差异容器(daemon 有但仓储无)强制清理

孤儿容器扫描安全边界:
- 通配符仅匹配本系统 sisys-sandbox- 前缀(避免误删其他项目容器)
- 同时校验 label sisys.sandbox.session_id(启动容器时设置)确保 100% 归属本系统
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from src.application.services.sandbox_config import SandboxConfig
from src.domain.exceptions.sandbox_exceptions import ContainerStopError
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.sandbox_session_repository import SandboxSessionRepositoryPort

logger = logging.getLogger(__name__)

__all__ = ["SandboxSessionReaper"]


class SandboxSessionReaper:
    """沙箱会话清理服务（Story 4.4 Task 6)

    Attributes:
        _sandbox: SandboxExecutor 端口(用于停止容器)
        _session_repo: SandboxSession 仓储(用于查询空闲会话 + 更新状态)
        _config: SandboxConfig(settings,含 IDLE_TIMEOUT_MINUTES)
    """

    def __init__(
        self,
        sandbox: SandboxExecutor,
        session_repository: SandboxSessionRepositoryPort,
        config: SandboxConfig | None = None,
    ) -> None:
        """初始化 Reaper。

        Args:
            sandbox: SandboxExecutor 端口(用于 stop_container)
            session_repository: SandboxSession 仓储
            config: SandboxConfig(默认 None → 使用默认配置)
        """
        self._sandbox = sandbox
        self._session_repo = session_repository
        self._config = config or SandboxConfig()

    async def reap_idle_sessions(
        self,
        threshold: datetime | None = None,
    ) -> int:
        """清理空闲会话。

        Args:
            threshold: 空闲阈值(默认 None → 计算为 now - IDLE_TIMEOUT_MINUTES * 60 秒)

        Returns:
            清理的会话数量

        Raises:
            ContainerStopError: 容器停止失败(单个失败不影响整体清理)
        """
        if threshold is None:
            threshold = datetime.now(UTC) - timedelta(minutes=self._config.idle_timeout_minutes)

        idle_sessions = await self._session_repo.list_idle_sessions(threshold)
        logger.info(
            "Found %d idle sandbox sessions (threshold=%s)",
            len(idle_sessions),
            threshold.isoformat(),
        )

        reaped_count = 0
        for session in idle_sessions:
            try:
                await self._sandbox.stop_container(session.session_id)
                reaped_count += 1
                logger.info(
                    "Reaped idle sandbox session: session_id=%s last_activity=%s",
                    session.session_id,
                    session.last_activity_at.isoformat(),
                )
            except ContainerStopError as exc:
                logger.error(
                    "Failed to stop container during reaping session %s: %s",
                    session.session_id,
                    exc,
                )
                # 单个失败不影响整体清理
                continue

        return reaped_count

    async def reap_orphan_containers(self) -> int:
        """清理孤儿容器（启动时扫描)。

        孤儿容器定义:Docker daemon 上存在但本地 SandboxSession 仓储不存在的容器。
        安全边界:仅扫描 sisys-sandbox-* 前缀 + 校验 label sisys.sandbox.session_id。

        Returns:
            清理的孤儿容器数量

        注意:本方法依赖 aiodocker 真实 daemon,通过 _sandbox.health_check() 探测可用性。
        若 daemon 不可用,本方法跳过(返回 0)以避免误删。
        """
        if not await self._sandbox.health_check():
            logger.warning("Docker daemon not reachable, skipping orphan reaping")
            return 0

        try:
            # 延迟导入 aiodocker(stub 类型已知,运行时检查)
            import aiodocker
        except ImportError:
            logger.warning("aiodocker not installed, skipping orphan reaping")
            return 0

        try:
            docker = aiodocker.Docker()
            try:
                containers = await docker.containers.list(all=True, filters={"name": ["sisys-sandbox-"]})
            finally:
                await docker.close()
        except Exception as exc:
            logger.error("Failed to list Docker containers for orphan reaping: %s", exc)
            return 0

        if not containers:
            return 0

        # 获取本地活跃 session_id 集合
        all_sessions = await self._session_repo.list_all()
        known_session_ids = {s.session_id for s in all_sessions}

        orphan_count = 0
        for container in containers:
            try:
                # 通过 label 校验容器归属本系统
                container_info = await container.show() if hasattr(container, "show") else {}
                labels = container_info.get("Config", {}).get("Labels", {}) or {}
                session_id_label = labels.get("sisys.sandbox.session_id")
                container_name = container_info.get("Name", "") or ""

                # 仅匹配 sisys-sandbox- 前缀且有 session_id label 的容器
                if not container_name.startswith("sisys-sandbox-"):
                    continue
                if session_id_label is None:
                    logger.warning(
                        "Container %s missing sisys.sandbox.session_id label, skipping",
                        container_name,
                    )
                    continue
                if session_id_label in known_session_ids:
                    continue  # 已知容器,跳过

                # 孤儿容器,强制清理
                await container.delete(force=True, v=True)
                orphan_count += 1
                logger.info(
                    "Reaped orphan container: %s session_id=%s",
                    container_name,
                    session_id_label,
                )
            except Exception as exc:
                logger.error("Failed to reap orphan container: %s", exc)
                continue

        return orphan_count


__all__ = ["SandboxSessionReaper"]
