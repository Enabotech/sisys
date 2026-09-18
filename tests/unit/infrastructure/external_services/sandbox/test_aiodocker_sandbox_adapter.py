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
    """构造 mock DockerContainer 对象(返回 .id 属性)."""
    container = MagicMock()
    container.id = "container-abc123"
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
    """构造 mock Container 对象"""
    container = MagicMock()
    container.delete = AsyncMock(return_value=True)
    container.show = AsyncMock(return_value={"State": {"Running": show_running}})

    # exec 返回值 + start async context manager
    exec_instance = MagicMock()
    exec_instance.start = MagicMock()

    async def _start_cm(detach: bool = False) -> Any:
        stream = MagicMock()
        stream.read_out = AsyncMock(return_value=MagicMock(data=b"hello\n"))
        return stream

    exec_instance.start.return_value.__aenter__ = AsyncMock(side_effect=_start_cm)
    exec_instance.start.return_value.__aexit__ = AsyncMock(return_value=None)
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
        mock_container.exec.side_effect = Exception("container killed (exit 137): out of memory")
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(SandboxResourceLimitExceededError) as exc_info:
            await adapter.execute_code("sess-oom-test", "x = [1]*10**9")
        assert exc_info.value.code == "EXCEPTION_317"
        assert exc_info.value.context["limit_type"] == "mem"

    async def test_execute_code_no_container(self, adapter: AioDockerSandboxAdapter) -> None:
        """无运行容器抛 ExecutionError(EXCEPTION_313)"""
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

    async def test_is_container_running_no_session(self, adapter: AioDockerSandboxAdapter) -> None:
        """无 session 记录返回 False(不抛异常)"""
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
