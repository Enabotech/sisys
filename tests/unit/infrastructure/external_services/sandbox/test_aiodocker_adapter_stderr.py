"""Story 4.7: aiodocker 沙箱适配器 STDERR 数据链单元测试.

覆盖失败路径异常 context 携带 stderr（截断 ≤2000）与 exit_code（AC-1——
现状 stderr 在 adapter :511-518 仅 logger.debug 后丢弃，本测试锁定修复契约）。

对齐 4.4 既有 adapter 测试形态（@patch aiodocker.Docker + fake container/exec）。

TDD 红→绿：本文件先于 adapter 填充实现（Subtask 3.1）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiodocker.stream import Message

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.exceptions import ExecutionError
from src.infrastructure.external_services.sandbox.aiodocker_sandbox_adapter import (
    AioDockerSandboxAdapter,
)
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)


def _make_docker_mock() -> MagicMock:
    """构造 mock aiodocker Docker 实例."""
    docker = MagicMock()
    docker.containers.get = AsyncMock()
    return docker


def _make_container_mock() -> MagicMock:
    """构造 mock Container（read_out 对齐 aiodocker 0.21 协议——4.4 测试同款）."""
    container = MagicMock()
    container.delete = AsyncMock(return_value=True)
    container.show = AsyncMock(return_value={"State": {"Running": True}})

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


def _wire_stream(mock_container: MagicMock, messages: list[Message], exit_code: int) -> None:
    """重配 exec 流与退出码.

    Args:
        mock_container: fake container
        messages: read_out 序列（Message(1, stdout) / Message(2, stderr)，None=EOF 由最后一项自动补）
        exit_code: inspect 返回的 ExitCode
    """
    exec_instance = mock_container.exec.return_value

    async def _start_cm(detach: bool = False) -> Any:
        stream = MagicMock()
        stream.read_out = AsyncMock(side_effect=[*messages, None])
        return stream

    exec_instance.start.return_value.__aenter__ = AsyncMock(side_effect=_start_cm)
    exec_instance.inspect = AsyncMock(return_value={"ExitCode": exit_code})


@pytest.fixture
def repo() -> InMemorySandboxSessionRepository:
    """内存沙箱会话仓储."""
    return InMemorySandboxSessionRepository()


@pytest.fixture
def adapter(repo: InMemorySandboxSessionRepository) -> AioDockerSandboxAdapter:
    """被测适配器（SessionRepo 注入）."""
    return AioDockerSandboxAdapter(session_repo=repo)


async def _save_session(repo: InMemorySandboxSessionRepository, session_id: str) -> None:
    """预置 RUNNING 会话."""
    await repo.save(
        SandboxSession(
            session_id=session_id,
            tenant_id=uuid.uuid4(),
            container_id="container-xyz",
        )
    )


class TestAdapterStderrDataChain:
    """失败路径异常 context 填充（AC-1 验证标准 :511-518）."""

    @patch("aiodocker.Docker")
    async def test_nonzero_exit_carries_stderr_and_exit_code(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """非零退出码：异常 context 携带 stderr（截断 ≤2000）与 exit_code."""
        await _save_session(repo, "sess-stderr-1")
        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        _wire_stream(
            mock_container,
            [Message(1, b"partial out\n"), Message(2, b"Traceback ... KeyError: 'data'\n")],
            exit_code=1,
        )
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ExecutionError) as exc_info:
            await adapter.execute_code("sess-stderr-1", "raise KeyError('data')")
        assert exc_info.value.code == "EXCEPTION_313"
        assert "KeyError: 'data'" in exc_info.value.context.get("stderr", "")
        assert exc_info.value.context.get("exit_code") == 1

    @patch("aiodocker.Docker")
    async def test_stderr_nonempty_with_zero_exit_carries_stderr(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """exit 0 但 stderr 非空：同样携带 stderr 与 exit_code=0."""
        await _save_session(repo, "sess-stderr-2")
        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        _wire_stream(
            mock_container,
            [Message(1, b"ok\n"), Message(2, b"DeprecationWarning: something")],
            exit_code=0,
        )
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ExecutionError) as exc_info:
            await adapter.execute_code("sess-stderr-2", "print('ok')")
        assert "DeprecationWarning" in exc_info.value.context.get("stderr", "")
        assert exc_info.value.context.get("exit_code") == 0

    @patch("aiodocker.Docker")
    async def test_stderr_truncated_to_2000(
        self, mock_docker_cls: MagicMock, adapter: AioDockerSandboxAdapter, repo: InMemorySandboxSessionRepository
    ) -> None:
        """超长 stderr 截断至 2000 字符（防 DoS）."""
        await _save_session(repo, "sess-stderr-3")
        mock_docker = _make_docker_mock()
        mock_container = _make_container_mock()
        _wire_stream(
            mock_container,
            [Message(2, b"x" * 5000)],
            exit_code=1,
        )
        mock_docker.containers.get.return_value = mock_container
        mock_docker_cls.return_value = mock_docker

        with pytest.raises(ExecutionError) as exc_info:
            await adapter.execute_code("sess-stderr-3", "fail")
        assert len(exc_info.value.context.get("stderr", "")) == 2000
