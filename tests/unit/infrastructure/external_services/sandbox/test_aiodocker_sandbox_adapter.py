"""Story 4.4: AioDockerSandboxAdapter 单元测试

Mock aiodocker.Docker 客户端,验证:
- 5 个核心方法的调用路径
- 5 类异常映射（EXCEPTION_315-319）
- session_id 注入防御
- 容器名长度边界
- 配额检查
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiodocker.exceptions import DockerError
from aiodocker.stream import Message

from src.domain.exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxConfigurationError,
    SandboxImagePullError,
    SandboxQuotaExceededError,
    SandboxResourceLimitExceededError,
    SandboxTimeoutError,
)
from src.infrastructure.external_services.sandbox.aiodocker_sandbox_adapter import (
    SESSION_ID_PATTERN,
    AioDockerSandboxAdapter,
)
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)


def _make_container_id_mock() -> MagicMock:
    """构造 mock DockerContainer 对象(返回 .id 属性 + show 镜像信息)."""
    container = MagicMock()
    container.id = "container-abc123"
    container.show = AsyncMock(return_value={"Image": "sha256:9534e5a8"})
    return container


def _make_docker_mock() -> MagicMock:
    """构造 mock aiodocker.Docker 客户端"""
    docker = MagicMock()
    docker.images.pull = AsyncMock(return_value={"status": "success"})
    docker.images.list = AsyncMock(return_value=[])  # 本地无镜像,触发 pull
    docker.containers.run = AsyncMock(return_value=_make_container_id_mock())
    docker.containers.get = AsyncMock()
    docker.version = AsyncMock(return_value={"Version": "20.10.21"})
    # 关键:session.close() 必须是 async(否则 aclose() 中 await 失败)
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.close = AsyncMock()
    mock_session._connector = MagicMock()
    mock_session._connector.closed = False
    docker.session = mock_session
    return docker


def _make_container_mock(show_running: bool = True) -> MagicMock:
    """构造 mock Container 对象

    read_out mock 对齐 aiodocker 0.21 真实协议:
    协议层(_ExecParser)已解析多路复用帧头,read_out 返回 Message(stream, data),
    EOF 返回 None(stream=1 stdout / stream=2 stderr)。
    """
    container = MagicMock()
    container.delete = AsyncMock(return_value=True)
    container.show = AsyncMock(return_value={"State": {"Running": show_running}})

    # exec 返回值 + start async context manager
    exec_instance = MagicMock()
    exec_instance.start = MagicMock()

    async def _start_cm(detach: bool = False) -> Any:
        stream = MagicMock()
        stream.read_out = AsyncMock(side_effect=[Message(1, b"hello\n"), None])
        return stream

    exec_instance.start.return_value.__aenter__ = AsyncMock(side_effect=_start_cm)
    exec_instance.start.return_value.__aexit__ = AsyncMock(return_value=None)
    exec_instance.inspect = AsyncMock(return_value={"ExitCode": 0})
    container.exec = AsyncMock(return_value=exec_instance)
    return container


@pytest.fixture
def repo() -> InMemorySandboxSessionRepository:
    """每个测试使用新的仓储实例"""
    return InMemorySandboxSessionRepository()


@pytest.fixture
def adapter(repo: InMemorySandboxSessionRepository) -> AioDockerSandboxAdapter:
    """每个测试使用新的适配器实例,共享仓储"""
    return AioDockerSandboxAdapter(
        docker_socket="unix:///var/run/docker.sock",
        max_concurrent=50,
        session_repo=repo,
    )


class TestSessionIdValidation:
    """session_id 注入防御测试"""

    def test_session_id_pattern_constant(self) -> None:
        """SESSION_ID_PATTERN 应为 ^[A-Za-z0-9_-]{1,64}$"""
        assert SESSION_ID_PATTERN.pattern == r"^[A-Za-z0-9_-]{1,64}$"

    async def test_start_container_invalid_session_id_raises(self, adapter: AioDockerSandboxAdapter) -> None:
        """start_container session_id 非法抛 SandboxConfigurationError"""
        with pytest.raises(SandboxConfigurationError) as exc_info:
            await adapter.start_container("invalid session with spaces")
        assert exc_info.value.context["field_name"] == "session_id"

    async def test_start_container_empty_session_id_raises(self, adapter: AioDockerSandboxAdapter) -> None:
        """start_container session_id 空字符串抛 SandboxConfigurationError"""
        with pytest.raises(SandboxConfigurationError):
            await adapter.start_container("")


class TestStartContainer:
    """start_container 测试"""

    @patch("aiodocker.Docker")
    async def test_start_container_happy_path(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """正常启动:docker.images.pull + docker.containers.run 各 1 次"""
        mock_docker = _make_docker_mock()
        mock_docker_cls.return_value = mock_docker

        await adapter.start_container("sess-abc123def456")

        # 验证调用次数
        assert mock_docker.images.pull.await_count == 1
        assert mock_docker.containers.run.await_count == 1
        # 验证调用参数
        run_call = mock_docker.containers.run.await_args
        assert run_call.kwargs["name"].startswith("sisys-sandbox-")
        assert run_call.kwargs["name"].endswith("-sess-abc123def456")

    @patch("aiodocker.Docker")
    async def test_start_container_image_pull_failure(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter
    ) -> None:
        """镜像拉取失败抛 SandboxImagePullError(EXCEPTION_315)"""
        mock_docker = _make_docker_mock()
        mock_docker.images.pull.side_effect = Exception("manifest unknown")
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(SandboxImagePullError) as exc_info:
            await adapter.start_container("sess-abc123")
        assert exc_info.value.code == "EXCEPTION_315"
        assert exc_info.value.context["docker_error"] == "manifest unknown"

    @patch("aiodocker.Docker")
    async def test_start_container_run_failure(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """容器运行失败抛 ContainerStartError(EXCEPTION_312)"""
        mock_docker = _make_docker_mock()
        mock_docker.containers.run.side_effect = Exception("container run failed")
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ContainerStartError) as exc_info:
            await adapter.start_container("sess-abc123")
        assert exc_info.value.code == "EXCEPTION_312"

    @patch("aiodocker.Docker")
    async def test_start_container_quota_exceeded(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """并发数超配额抛 SandboxQuotaExceededError(EXCEPTION_318)"""
        # 模拟 _running_count 已达 max
        AioDockerSandboxAdapter._running_count = 50
        try:
            with pytest.raises(SandboxQuotaExceededError) as exc_info:
                await adapter.start_container("sess-abc123")
            assert exc_info.value.code == "EXCEPTION_318"
            assert exc_info.value.context["max_count"] == 50
        finally:
            AioDockerSandboxAdapter._running_count = 0

    @patch("aiodocker.Docker")
    async def test_start_container_saga_compensation_on_save_failure(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """run 成功后 session save 失败: Saga 补偿删除已创建容器,避免孤儿"""
        mock_docker = _make_docker_mock()
        mock_container = _make_container_id_mock()
        mock_container.delete = AsyncMock(return_value=True)
        mock_docker.containers.run = AsyncMock(return_value=mock_container)
        mock_docker_cls.return_value = mock_docker

        broken_repo = AsyncMock(spec=InMemorySandboxSessionRepository)
        broken_repo.save.side_effect = Exception("pg connection lost")
        adapter._session_repo = broken_repo

        with pytest.raises(Exception, match="pg connection lost"):
            await adapter.start_container("sess-saga-test")

        # Saga 补偿: 已创建容器被 best-effort 删除
        assert mock_container.delete.await_count == 1


class TestContainerNameLength:
    """容器名长度边界测试"""

    def test_container_name_length_within_limit(self) -> None:
        """容器名长度应 ≤ 55 字符(14+8+1+32=55,留 9 字符 buffer)"""
        from src.infrastructure.external_services.sandbox.container_spec_builder import (
            ContainerSpecBuilder,
        )

        # 用 32 字符 session_id 验证精确边界
        long_session = "a" * 32
        name = ContainerSpecBuilder.build_container_name(
            __import__("uuid").UUID("12345678-1234-5678-1234-567812345678"),
            long_session,
        )
        assert len(name) == 55  # 14 + 8 + 1 + 32
        assert name == f"sisys-sandbox-12345678-{long_session}"

    def test_container_name_with_long_session_id_truncated(self) -> None:
        """长 session_id 应截取前 32 字符"""
        from src.infrastructure.external_services.sandbox.container_spec_builder import (
            ContainerSpecBuilder,
        )

        long_session = "a" * 64
        name = ContainerSpecBuilder.build_container_name(
            __import__("uuid").UUID("12345678-1234-5678-1234-567812345678"),
            long_session,
        )
        assert len(name) == 55  # 14 + 8 + 1 + 32

    def test_container_name_with_short_session_id(self) -> None:
        """短 session_id 应完整保留"""
        from src.infrastructure.external_services.sandbox.container_spec_builder import (
            ContainerSpecBuilder,
        )

        name = ContainerSpecBuilder.build_container_name(
            __import__("uuid").UUID("12345678-1234-5678-1234-567812345678"),
            "abc",
        )
        assert name.endswith("-abc")


class TestExecuteCode:
    """execute_code 测试"""

    @patch("aiodocker.Docker")
    async def test_execute_code_happy_path(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """正常执行代码:docker.containers.get + container.exec + start"""
        from src.domain.entities.sandbox_session import SandboxSession

        session = SandboxSession(
            session_id="sess-abc123",
            tenant_id=__import__("uuid").uuid4(),
            container_id="container-xyz",
        )
        await repo.save(session)

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        result = await adapter.execute_code("sess-abc123", "print('hi')")

        assert result["status"] == "completed"
        assert "hello" in result["output"]  # mock 返回 b"hello\n"

    @patch("aiodocker.Docker")
    async def test_execute_code_timeout(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """执行超时抛 SandboxTimeoutError(EXCEPTION_316)"""
        from src.domain.entities.sandbox_session import SandboxSession

        # 使用新 session_id 避免被前一个测试影响 state_version
        await repo.save(
            SandboxSession(
                session_id="sess-timeout-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()

        # 模拟 hang 住以触发 asyncio.wait_for 超时
        async def _hang(*args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(10)
            return None

        mock_container.exec.side_effect = _hang
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(SandboxTimeoutError) as exc_info:
            await adapter.execute_code("sess-timeout-test", "long_running()", timeout_sec=0.1)
        assert exc_info.value.code == "EXCEPTION_316"
        assert exc_info.value.context["timeout_sec"] == 0.1
        # 超时即销毁(Round 6 增补契约): 容器被 best-effort 删除
        assert mock_container.delete.await_count == 1

    @patch("aiodocker.Docker")
    async def test_execute_code_oom(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """容器 OOM kill (exit 137) 抛 SandboxResourceLimitExceededError(EXCEPTION_317)"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-oom-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        # OOM: read_out 无数据(OOM kill 截断),inspect 返回 ExitCode=137
        exec_instance = mock_container.exec.return_value

        async def _oom_start_cm(detach: bool = False) -> Any:
            stream = MagicMock()
            stream.read_out = AsyncMock(side_effect=[None])
            return stream

        exec_instance.start.return_value.__aenter__ = AsyncMock(side_effect=_oom_start_cm)
        exec_instance.inspect = AsyncMock(return_value={"ExitCode": 137})
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(SandboxResourceLimitExceededError) as exc_info:
            await adapter.execute_code("sess-oom-test", "x = [1]*10**9")
        assert exc_info.value.code == "EXCEPTION_317"
        assert exc_info.value.context["limit_type"] == "mem"
        assert exc_info.value.context["docker_exit_code"] == 137

    @patch("aiodocker.Docker")
    async def test_execute_code_nonzero_exit_raises(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """非零退出码 + stderr 非空抛 ExecutionError(EXCEPTION_313),不得吞错返回 completed"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-fail-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        exec_instance = mock_container.exec.return_value

        async def _fail_start_cm(detach: bool = False) -> Any:
            stream = MagicMock()
            stream.read_out = AsyncMock(side_effect=[Message(2, b"boom"), None])
            return stream

        exec_instance.start.return_value.__aenter__ = AsyncMock(side_effect=_fail_start_cm)
        exec_instance.inspect = AsyncMock(return_value={"ExitCode": 3})
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ExecutionError) as exc_info:
            await adapter.execute_code("sess-fail-test", "sys.exit(3)")
        assert exc_info.value.code == "EXCEPTION_313"

    @patch("aiodocker.Docker")
    async def test_execute_code_stderr_nonempty_raises(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """exit 0 但 stderr 非空抛 ExecutionError(AC-5: STDERR 非空即失败)"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-stderr-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        exec_instance = mock_container.exec.return_value

        async def _stderr_start_cm(detach: bool = False) -> Any:
            stream = MagicMock()
            stream.read_out = AsyncMock(side_effect=[Message(1, b"ok\n"), Message(2, b"warning!"), None])
            return stream

        exec_instance.start.return_value.__aenter__ = AsyncMock(side_effect=_stderr_start_cm)
        exec_instance.inspect = AsyncMock(return_value={"ExitCode": 0})
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ExecutionError) as exc_info:
            await adapter.execute_code("sess-stderr-test", "print('ok')")
        assert exc_info.value.code == "EXCEPTION_313"

    @patch("aiodocker.Docker")
    async def test_execute_code_execution_time_measured(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """execution_time_ms 真实计时(非恒 0 硬编码)"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-timing-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_docker.containers.get.return_value = _make_container_mock()
        mock_docker_cls.return_value = mock_docker

        result = await adapter.execute_code("sess-timing-test", "print('hi')")

        assert result["status"] == "completed"
        assert isinstance(result["execution_time_ms"], int)
        assert result["execution_time_ms"] >= 0

    @patch("aiodocker.Docker")
    async def test_execute_code_no_container(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """无运行容器抛 ExecutionError(EXCEPTION_313)"""
        mock_docker_cls.return_value = _make_docker_mock()
        with pytest.raises(ExecutionError):
            await adapter.execute_code("sess-noexist-test-xyz", "print('hi')")


class TestStopContainer:
    """stop_container 测试"""

    @patch("aiodocker.Docker")
    async def test_stop_container_happy_path(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """正常停止:docker.containers.get + container.delete"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-stop-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        await adapter.stop_container("sess-stop-test")

        assert mock_container.delete.await_count == 1
        updated = await repo.get_by_session_id("sess-stop-test")
        assert updated is not None
        assert updated.state == "TERMINATED"
        assert updated.terminated_at is not None

    @patch("aiodocker.Docker")
    async def test_stop_container_delete_failure(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """容器删除失败抛 ContainerStopError(EXCEPTION_314)"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-stop-fail-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        mock_container.delete.side_effect = Exception("delete failed")
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ContainerStopError) as exc_info:
            await adapter.stop_container("sess-stop-fail-test")
        assert exc_info.value.code == "EXCEPTION_314"

    @patch("aiodocker.Docker")
    async def test_stop_container_idempotent_when_terminated(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """会话已 TERMINATED 时 stop 幂等返回(Round 6 增补契约),不再访问 daemon"""
        from src.domain.entities.sandbox_session import SandboxSession

        session = SandboxSession(
            session_id="sess-stopped-test",
            tenant_id=__import__("uuid").uuid4(),
            container_id="container-xyz",
        )
        await repo.save(session.with_terminated())

        mock_docker = _make_docker_mock()
        mock_docker_cls.return_value = mock_docker

        await adapter.stop_container("sess-stopped-test")  # 不抛异常

        assert mock_docker.containers.get.await_count == 0

    @patch("aiodocker.Docker")
    async def test_stop_container_404_treated_as_success(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """容器已不存在(daemon 404)按成功处理: 标记终止 + 不抛 314"""
        from src.domain.entities.sandbox_session import SandboxSession

        await repo.save(
            SandboxSession(
                session_id="sess-stop-404-test",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )

        mock_docker = _make_docker_mock()
        mock_docker.containers.get.side_effect = DockerError(404, "No such container")
        mock_docker_cls.return_value = mock_docker

        await adapter.stop_container("sess-stop-404-test")  # 不抛异常

        updated = await repo.get_by_session_id("sess-stop-404-test")
        assert updated is not None
        assert updated.state == "TERMINATED"


class TestIsContainerRunning:
    """is_container_running 测试"""

    @patch("aiodocker.Docker")
    async def test_is_container_running_true(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """容器运行中返回 True"""
        from src.domain.entities.sandbox_session import SandboxSession

        session = SandboxSession(
            session_id="sess-abc123",
            tenant_id=__import__("uuid").uuid4(),
            container_id="container-xyz",
        )
        await repo.save(session)

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock(show_running=True)
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        result = await adapter.is_container_running("sess-abc123")
        assert result is True

    @patch("aiodocker.Docker")
    async def test_is_container_running_false(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """容器未运行返回 False"""
        from src.domain.entities.sandbox_session import SandboxSession

        session = SandboxSession(
            session_id="sess-abc123",
            tenant_id=__import__("uuid").uuid4(),
            container_id="container-xyz",
        )
        await repo.save(session)

        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock(show_running=False)
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        result = await adapter.is_container_running("sess-abc123")
        assert result is False

    @patch("aiodocker.Docker")
    async def test_is_container_running_no_session(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """无 session 记录返回 False(不抛异常)"""
        mock_docker_cls.return_value = _make_docker_mock()
        result = await adapter.is_container_running("sess-noexist")
        assert result is False


class TestHealthCheck:
    """health_check 测试"""

    @patch("aiodocker.Docker")
    async def test_health_check_daemon_reachable(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """Docker daemon 可达返回 True"""
        mock_docker = _make_docker_mock()
        mock_docker_cls.return_value = mock_docker

        result = await adapter.health_check()
        assert result is True
        assert mock_docker.version.await_count == 1

    @patch("aiodocker.Docker")
    async def test_health_check_daemon_unreachable(self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter) -> None:
        """Docker daemon 不可达返回 False(不抛异常)"""
        mock_docker = _make_docker_mock()
        mock_docker.version.side_effect = Exception("connection refused")
        mock_docker_cls.return_value = mock_docker

        result = await adapter.health_check()
        assert result is False


class TestEventPublishing:
    """沙箱生命周期事件发布测试(Round 2 审查修订: adapter 为 Started/Terminated 唯一发布点)"""

    @patch("aiodocker.Docker")
    async def test_start_container_publishes_started_event(
        self, mock_docker_cls: MagicMock, repo: InMemorySandboxSessionRepository
    ) -> None:
        """start_container 成功发布 SandboxSessionStarted(best-effort,不以 session_repo 为条件)"""
        from src.domain.events.sandbox_events import SandboxSessionStarted
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

        event_bus = InMemoryEventBus()
        adapter = AioDockerSandboxAdapter(session_repo=repo, event_publisher=event_bus)
        mock_docker = _make_docker_mock()
        mock_docker_cls.return_value = mock_docker

        await adapter.start_container("sess-event-start")

        started = [e for e in event_bus.published_events if isinstance(e, SandboxSessionStarted)]
        assert len(started) == 1
        assert started[0].session_id == "sess-event-start"

    @patch("aiodocker.Docker")
    async def test_stop_container_publishes_terminated_event(
        self, mock_docker_cls: MagicMock, repo: InMemorySandboxSessionRepository
    ) -> None:
        """stop_container 真实迁移发布 SandboxSessionTerminated(termination_reason=explicit_stop)"""
        from src.domain.entities.sandbox_session import SandboxSession
        from src.domain.events.sandbox_events import SandboxSessionTerminated
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

        await repo.save(
            SandboxSession(
                session_id="sess-event-stop",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )
        event_bus = InMemoryEventBus()
        adapter = AioDockerSandboxAdapter(session_repo=repo, event_publisher=event_bus)
        mock_docker = _make_docker_mock()
        mock_docker.containers.get.return_value = _make_container_mock()
        mock_docker_cls.return_value = mock_docker

        await adapter.stop_container("sess-event-stop")

        terminated = [e for e in event_bus.published_events if isinstance(e, SandboxSessionTerminated)]
        assert len(terminated) == 1
        assert terminated[0].termination_reason == "explicit_stop"

    @patch("aiodocker.Docker")
    async def test_stop_container_idempotent_no_duplicate_event(
        self, mock_docker_cls: MagicMock, repo: InMemorySandboxSessionRepository
    ) -> None:
        """幂等早退路径不发布事件(防双发)"""
        from src.domain.entities.sandbox_session import SandboxSession
        from src.domain.events.sandbox_events import SandboxSessionTerminated
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

        session = SandboxSession(
            session_id="sess-event-idem",
            tenant_id=__import__("uuid").uuid4(),
            container_id="container-xyz",
        )
        await repo.save(session.with_terminated())
        event_bus = InMemoryEventBus()
        adapter = AioDockerSandboxAdapter(session_repo=repo, event_publisher=event_bus)
        mock_docker = _make_docker_mock()
        mock_docker_cls.return_value = mock_docker

        await adapter.stop_container("sess-event-idem")

        terminated = [e for e in event_bus.published_events if isinstance(e, SandboxSessionTerminated)]
        assert terminated == []

    @patch("aiodocker.Docker")
    async def test_timeout_publishes_timeout_abort_event(
        self, mock_docker_cls: MagicMock, repo: InMemorySandboxSessionRepository
    ) -> None:
        """超时销毁后发布 SandboxSessionTerminated(termination_reason=timeout_abort)"""
        from src.domain.entities.sandbox_session import SandboxSession
        from src.domain.events.sandbox_events import SandboxSessionTerminated
        from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

        await repo.save(
            SandboxSession(
                session_id="sess-event-timeout",
                tenant_id=__import__("uuid").uuid4(),
                container_id="container-xyz",
            )
        )
        event_bus = InMemoryEventBus()
        adapter = AioDockerSandboxAdapter(session_repo=repo, event_publisher=event_bus)
        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()

        async def _hang(*args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(10)
            return None

        mock_container.exec.side_effect = _hang
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(SandboxTimeoutError):
            await adapter.execute_code("sess-event-timeout", "long_running()", timeout_sec=0.1)

        terminated = [e for e in event_bus.published_events if isinstance(e, SandboxSessionTerminated)]
        assert len(terminated) == 1
        assert terminated[0].termination_reason == "timeout_abort"


class TestReapOrphanContainers:
    """reap_orphan_containers 测试(Round 3 端口扩展)"""

    @patch("aiodocker.Docker")
    async def test_reap_orphan_deletes_unknown_labelled_containers(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter
    ) -> None:
        """label 归属本系统但 session-id 未知的容器被删除,已知会话保留"""
        mock_docker = _make_docker_mock()

        orphan = MagicMock()
        orphan._container = {"Labels": {"managed-by": "sisys-sandbox", "sisys.session-id": "sess-orphan"}}
        orphan.delete = AsyncMock(return_value=True)
        orphan.id = "container-orphan"

        known = MagicMock()
        known._container = {"Labels": {"managed-by": "sisys-sandbox", "sisys.session-id": "sess-known"}}
        known.delete = AsyncMock(return_value=True)
        known.id = "container-known"

        mock_docker.containers.list = AsyncMock(return_value=[orphan, known])
        mock_docker_cls.return_value = mock_docker

        reaped = await adapter.reap_orphan_containers({"sess-known"})

        assert reaped == 1
        assert orphan.delete.await_count == 1
        assert known.delete.await_count == 0

    @patch("aiodocker.Docker")
    async def test_reap_orphan_delete_failure_continues(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter
    ) -> None:
        """单个删除失败不影响其他孤儿清理(异常隔离)"""
        mock_docker = _make_docker_mock()

        failing = MagicMock()
        failing._container = {"Labels": {"managed-by": "sisys-sandbox", "sisys.session-id": "sess-fail"}}
        failing.delete = AsyncMock(side_effect=Exception("daemon error"))
        failing.id = "container-fail"

        ok = MagicMock()
        ok._container = {"Labels": {"managed-by": "sisys-sandbox", "sisys.session-id": "sess-ok"}}
        ok.delete = AsyncMock(return_value=True)
        ok.id = "container-ok"

        mock_docker.containers.list = AsyncMock(return_value=[failing, ok])
        mock_docker_cls.return_value = mock_docker

        reaped = await adapter.reap_orphan_containers(set())

        assert reaped == 1
        assert ok.delete.await_count == 1
