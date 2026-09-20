"""Story 4.4: SandboxSessionReaper 单元测试

验证 30 分钟空闲 TTL 清理逻辑:
- threshold 默认值(从 idle_timeout_minutes 计算)
- 配额调用 sandbox.stop_container
- 异常隔离(单个失败不影响其他会话)
- 孤儿容器清理（占位实现）
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.sandbox_session_reaper import SandboxSessionReaper
from src.domain.entities.sandbox_session import SandboxSession
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)


@pytest.fixture
def repo() -> InMemorySandboxSessionRepository:
    return InMemorySandboxSessionRepository()


@pytest.fixture
def sandbox() -> MagicMock:
    # 注意:故意不带 spec=SandboxExecutor,因为 mypy 会推断 _sandbox 为 Protocol 接口
    # 导致 stop_container 推断为 Callable 而失去 assert_not_called 等 mock 方法
    mock = MagicMock()
    mock.stop_container = AsyncMock()
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def reaper(repo: InMemorySandboxSessionRepository, sandbox: MagicMock) -> SandboxSessionReaper:
    return SandboxSessionReaper(
        sandbox=sandbox,
        session_repo=repo,
        idle_timeout_minutes=30,
    )


def _make_session(**overrides: object) -> SandboxSession:
    defaults: dict[str, Any] = {
        "session_id": f"sess-{uuid.uuid4().hex[:12]}",
        "tenant_id": uuid.uuid4(),
        "image_digest": "python:3.11-slim@sha256:abc",
    }
    defaults.update(overrides)
    return SandboxSession(**defaults)


class TestReapIdleSessions:
    """reap_idle_sessions 测试"""

    async def test_reap_no_idle_sessions(self, reaper: SandboxSessionReaper, sandbox: MagicMock) -> None:
        """无空闲会话返回 0"""
        # 启动一个最近活跃的会话
        recent = _make_session(last_activity_at=datetime.now(UTC))
        await reaper._session_repo.save(recent)

        count = await reaper.reap_idle_sessions()
        assert count == 0
        # 通过直接访问 sandbox fixture(保留 MagicMock 类型)而不是 reaper._sandbox(推断为 Protocol)
        sandbox.stop_container.assert_not_called()

    async def test_reap_idle_sessions_default_threshold(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """默认 threshold 应为 now - 30 分钟"""
        old_activity = datetime.now(UTC) - timedelta(minutes=45)
        idle = _make_session(last_activity_at=old_activity)
        await repo.save(idle)

        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
            idle_timeout_minutes=30,
        )
        count = await reaper.reap_idle_sessions()
        assert count == 1
        sandbox.stop_container.assert_called_once_with(idle.session_id)

    async def test_reap_with_explicit_threshold(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """显式 threshold 应覆盖默认值"""
        # 创建 2 个会话:一个空闲一个活跃
        idle = _make_session(last_activity_at=datetime.now(UTC) - timedelta(hours=2))
        active = _make_session(last_activity_at=datetime.now(UTC))
        await repo.save(idle)
        await repo.save(active)

        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
            idle_timeout_minutes=30,
        )
        threshold = datetime.now(UTC) - timedelta(hours=1)
        count = await reaper.reap_idle_sessions(threshold=threshold)

        assert count == 1
        sandbox.stop_container.assert_called_once_with(idle.session_id)

    async def test_reap_failure_isolation(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """单个 stop_container 失败不影响其他会话清理"""
        idle1 = _make_session(last_activity_at=datetime.now(UTC) - timedelta(hours=2))
        idle2 = _make_session(last_activity_at=datetime.now(UTC) - timedelta(hours=2))
        await repo.save(idle1)
        await repo.save(idle2)

        # 第一次 stop_container 抛异常,第二次成功
        sandbox.stop_container.side_effect = [Exception("docker error"), None]

        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
            idle_timeout_minutes=30,
        )
        threshold = datetime.now(UTC) - timedelta(hours=1)
        await reaper.reap_idle_sessions(threshold=threshold)

        # 2 个会话都被尝试 stop,但只有 1 个成功
        assert sandbox.stop_container.await_count == 2


class TestReapOrphanContainers:
    """reap_orphan_containers 测试（占位实现）"""

    async def test_reap_orphan_daemon_unavailable(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """Docker daemon 不可达返回 0"""
        sandbox.health_check.return_value = False

        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
            idle_timeout_minutes=30,
        )
        count = await reaper.reap_orphan_containers()
        assert count == 0

    async def test_reap_orphan_daemon_available_placeholder(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """Docker daemon 可达返回 0（占位）"""
        sandbox.health_check.return_value = True

        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
            idle_timeout_minutes=30,
        )
        count = await reaper.reap_orphan_containers()
        assert count == 0  # 占位实现


class TestReaperConfiguration:
    """Reaper 配置测试"""

    def test_default_idle_timeout_30_minutes(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """默认 idle_timeout_minutes 应为 30"""
        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
        )
        assert reaper._idle_timeout_minutes == 30

    def test_custom_idle_timeout(
        self,
        repo: InMemorySandboxSessionRepository,
        sandbox: MagicMock,
    ) -> None:
        """支持自定义 idle_timeout_minutes"""
        reaper = SandboxSessionReaper(
            sandbox=sandbox,
            session_repo=repo,
            idle_timeout_minutes=60,
        )
        assert reaper._idle_timeout_minutes == 60
