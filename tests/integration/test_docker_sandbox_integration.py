"""Story 4.4 — Docker 沙箱执行集成测试(AC-8 集成层)

真实 Docker daemon + 真实组件(禁止 mock),聚焦验收层未覆盖的集成缺口:
- daemon 侧状态一致性(容器真实消失)
- 真实容器 TTL reap(idle_timeout_minutes=0 阈值收缩)
- 孤儿容器回收(managed-by label 归属校验)
- RELIABLE outbox 事件落库(真实 PG schema 隔离 + savepoint rollback)
- stop 幂等 / 404 语义

Docker daemon / PG 不可用时动态 pytest.skip(禁止写死 @pytest.mark.skip)。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest

from src.infrastructure.external_services.sandbox.aiodocker_sandbox_adapter import (
    AioDockerSandboxAdapter,
)
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)

# 与 adapter 默认 spec 一致的钉版镜像(digest 锁定)
_PINNED_IMAGE = "python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534"

pytestmark = [pytest.mark.integration, pytest.mark.docker, pytest.mark.slow, pytest.mark.xdist_group("sandbox-daemon")]


@pytest.fixture
async def docker_daemon_or_skip() -> None:
    """动态检查 Docker daemon 可用性(CLAUDE.md §5 红线)"""
    import aiodocker

    client = aiodocker.Docker()
    try:
        await client.version()
    except Exception as exc:
        await client.close()
        pytest.skip(f"Docker daemon 不可用: {exc}")
    await client.close()


@pytest.fixture
async def sandbox(
    docker_daemon_or_skip: None,
) -> AsyncGenerator[tuple[AioDockerSandboxAdapter, InMemorySandboxSessionRepository], None]:
    """真实适配器 + InMemory 仓储(aclose 显式清理防 Unclosed connector)"""
    repo = InMemorySandboxSessionRepository()
    adapter = AioDockerSandboxAdapter(session_repo=repo)
    yield adapter, repo
    await adapter.aclose()


def _session_id() -> str:
    """生成唯一会话 ID(测试隔离由 session_id 唯一性承担)"""
    return f"it-{uuid.uuid4().hex[:16]}"


async def _list_session_containers(session_id: str) -> list:
    """按归属 label 精确查询本会话容器"""
    import aiodocker
    from aiodocker.utils import clean_filters

    client = aiodocker.Docker()
    try:
        containers = await client.containers.list(
            all=True, filters=clean_filters({"label": [f"sisys.session-id={session_id}"]})
        )
        return list(containers)
    finally:
        await client.close()


class TestLifecycleDaemonConsistency:
    """全生命周期 + daemon 侧状态一致性"""

    async def test_full_lifecycle_daemon_state_consistent(
        self, sandbox: tuple[AioDockerSandboxAdapter, InMemorySandboxSessionRepository]
    ) -> None:
        adapter, _repo = sandbox
        session_id = _session_id()

        await adapter.start_container(session_id)
        assert await adapter.is_container_running(session_id) is True

        result = await adapter.execute_code(session_id, "print('integration')")
        assert result["status"] == "completed"

        await adapter.stop_container(session_id)
        assert await adapter.is_container_running(session_id) is False
        # daemon 侧无残留
        assert await _list_session_containers(session_id) == []


class TestIdleTtlReap:
    """真实容器 TTL 清理(idle_timeout_minutes=0 阈值收缩)"""

    async def test_idle_ttl_reap_real_container(
        self, sandbox: tuple[AioDockerSandboxAdapter, InMemorySandboxSessionRepository]
    ) -> None:
        from src.application.services.sandbox_session_reaper import SandboxSessionReaper

        adapter, repo = sandbox
        session_id = _session_id()
        await adapter.start_container(session_id)

        # 反向断言: 默认 30 分钟阈值下刚启动的会话不判闲
        default_reaper = SandboxSessionReaper(sandbox=adapter, session_repo=repo)
        assert await default_reaper.reap_idle_sessions() == 0

        # 阈值收缩为 0 → 立即判闲清理
        reaper = SandboxSessionReaper(sandbox=adapter, session_repo=repo, idle_timeout_minutes=0)
        assert await reaper.reap_idle_sessions() == 1

        session = await repo.get_by_session_id(session_id)
        assert session is not None
        assert session.state == "TERMINATED"
        assert await _list_session_containers(session_id) == []

    async def test_idle_ttl_publishes_terminated_with_idle_reason(self, docker_daemon_or_skip: None) -> None:
        from src.application.services.sandbox_session_reaper import SandboxSessionReaper
        from src.domain.events.sandbox_events import SandboxSessionTerminated
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

        event_bus = InMemoryEventBus()
        repo = InMemorySandboxSessionRepository()
        adapter = AioDockerSandboxAdapter(session_repo=repo, event_publisher=event_bus)
        try:
            session_id = _session_id()
            await adapter.start_container(session_id)

            reaper = SandboxSessionReaper(sandbox=adapter, session_repo=repo, idle_timeout_minutes=0)
            assert await reaper.reap_idle_sessions() == 1

            terminated = [e for e in event_bus.published_events if isinstance(e, SandboxSessionTerminated)]
            assert len(terminated) == 1
            assert terminated[0].termination_reason == "idle_timeout"
        finally:
            await adapter.aclose()


class TestOrphanReap:
    """孤儿容器回收(label 归属校验)"""

    async def test_reap_orphan_containers(self, docker_daemon_or_skip: None) -> None:
        import aiodocker
        from aiodocker.utils import clean_filters

        client = aiodocker.Docker()
        orphan_id = f"it-orphan-{uuid.uuid4().hex[:8]}"
        survivor = None
        try:
            # 手工制造孤儿: 带归属 label 但不入仓储
            orphan = await client.containers.run(
                config={
                    "Image": _PINNED_IMAGE,
                    "Cmd": ["sleep", "infinity"],
                    "Labels": {"managed-by": "sisys-sandbox", "sisys.session-id": orphan_id},
                },
                name=f"sisys-sandbox-orphan-{uuid.uuid4().hex[:8]}",
            )
            # 对照组: 无归属 label 的容器不受影响
            survivor = await client.containers.run(
                config={"Image": _PINNED_IMAGE, "Cmd": ["sleep", "infinity"]},
                name=f"it-survivor-{uuid.uuid4().hex[:8]}",
            )

            adapter = AioDockerSandboxAdapter()
            try:
                reaped = await adapter.reap_orphan_containers(set())
            finally:
                await adapter.aclose()

            assert reaped >= 1
            # 孤儿已删除
            remaining = await client.containers.list(
                all=True, filters=clean_filters({"label": [f"sisys.session-id={orphan_id}"]})
            )
            assert remaining == []
            # 对照组存活
            survivor_info = await survivor.show()
            assert survivor_info["State"]["Running"] is True
        finally:
            try:
                await orphan.delete(force=True)
            except Exception:
                pass
            if survivor is not None:
                await survivor.delete(force=True)
            await client.close()


class TestOutboxReliableChannel:
    """RELIABLE 通道 outbox 落库(真实 PG schema 隔离 + savepoint rollback)"""

    async def test_events_written_to_outbox_reliable_channel(self, docker_daemon_or_skip: None) -> None:
        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import AsyncSession

        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.messaging.channel_router import ChannelRouter
        from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository
        from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
        from src.infrastructure.storage.postgresql.models.outbox import OutboxModel
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
        from src.infrastructure.storage.postgresql.repository.sandbox_session_repository import (
            PostgreSQLSandboxSessionRepository,
        )
        from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
        from tests.environments import get_test_env

        env = get_test_env()
        pg_config = PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            database=env.postgres.database,
            username=env.postgres.username,
            password=env.postgres.password,
            pool_size=5,
            max_overflow=10,
        )
        test_schema = f"test_sisys_{uuid.uuid4().hex[:8]}"
        db_manager = PostgreSQLManager(pg_config)
        async_engine = db_manager.get_async_engine()

        # PG 不可用动态 skip
        try:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            await async_engine.dispose()
            pytest.skip(f"PostgreSQL 不可用: {exc}")

        # schema 隔离(与既有集成测试样板一致: 建 schema → create_all → 结束 drop)
        async with async_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        from src.infrastructure.storage.postgresql.models import Base

        async with async_engine.begin() as conn:
            await conn.execute(text(f'SET search_path TO "{test_schema}"'))
            await conn.run_sync(Base.metadata.create_all)

        adapter = None
        try:
            session = AsyncSession(async_engine)
            await session.execute(text(f'SET search_path TO "{test_schema}"'))
            async with session.begin_nested():
                token = set_session(session)
                try:
                    pg_repo = PostgreSQLSandboxSessionRepository()
                    bus = RabbitMQEventBus(PostgreSQLOutboxRepository(), ChannelRouter())
                    adapter = AioDockerSandboxAdapter(session_repo=pg_repo, event_publisher=bus)

                    session_id = _session_id()
                    await adapter.start_container(session_id)
                    await adapter.stop_container(session_id)

                    rows = (await session.execute(select(OutboxModel).order_by(OutboxModel.created_at))).scalars().all()
                    event_types = [r.event_type for r in rows]
                    assert "SandboxSessionStarted" in event_types
                    assert "SandboxSessionTerminated" in event_types
                    assert all(r.status == "pending" for r in rows)
                finally:
                    reset_session(token)
            await session.close()
        finally:
            if adapter is not None:
                await adapter.aclose()
            async with async_engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
            await async_engine.dispose()


class TestConcurrencyAndNaming:
    """并发与容器名 label 追溯"""

    async def test_concurrent_10_sessions_functional(
        self, sandbox: tuple[AioDockerSandboxAdapter, InMemorySandboxSessionRepository]
    ) -> None:
        adapter, _repo = sandbox
        session_ids = [_session_id() for _ in range(10)]

        async def _lifecycle(sid: str) -> None:
            await adapter.start_container(sid)
            result = await adapter.execute_code(sid, "print(1+1)")
            assert result["status"] == "completed"
            await adapter.stop_container(sid)

        await asyncio.gather(*(_lifecycle(sid) for sid in session_ids))
        # 计数归零(类变量终态断言)
        assert AioDockerSandboxAdapter._running_count == 0

    async def test_container_labels_traceable(
        self, sandbox: tuple[AioDockerSandboxAdapter, InMemorySandboxSessionRepository]
    ) -> None:
        adapter, _repo = sandbox
        session_id = _session_id()
        await adapter.start_container(session_id)
        try:
            containers = await _list_session_containers(session_id)
            assert len(containers) == 1
            labels = containers[0]._container.get("Labels") or {}
            assert labels["managed-by"] == "sisys-sandbox"
            assert labels["sisys.session-id"] == session_id
            assert "sisys.tenant-id" in labels
        finally:
            await adapter.stop_container(session_id)


class TestStopIdempotency:
    """stop 幂等 + 404 语义"""

    async def test_stop_idempotent_and_external_delete_semantics(
        self, sandbox: tuple[AioDockerSandboxAdapter, InMemorySandboxSessionRepository]
    ) -> None:
        import aiodocker
        from aiodocker.utils import clean_filters

        adapter, repo = sandbox
        session_id = _session_id()
        await adapter.start_container(session_id)
        await adapter.stop_container(session_id)
        # 幂等: 已 TERMINATED 再 stop 直接返回不抛
        await adapter.stop_container(session_id)

        # 外部强删后 stop 按 404 成功语义处理
        session_id2 = _session_id()
        await adapter.start_container(session_id2)
        client = aiodocker.Docker()
        try:
            containers = await client.containers.list(filters=clean_filters({"label": [f"sisys.session-id={session_id2}"]}))
            assert len(containers) == 1
            await containers[0].delete(force=True)
            # 等待 daemon 侧删除真正完成(409 removal-in-progress 窗口)
            for _ in range(50):
                remaining = await client.containers.list(
                    all=True, filters=clean_filters({"label": [f"sisys.session-id={session_id2}"]})
                )
                if not remaining:
                    break
                await asyncio.sleep(0.1)
        finally:
            await client.close()

        await adapter.stop_container(session_id2)  # 404 → 不抛异常
        session = await repo.get_by_session_id(session_id2)
        assert session is not None
        assert session.state == "TERMINATED"
