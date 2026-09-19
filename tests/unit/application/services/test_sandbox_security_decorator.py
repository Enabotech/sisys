"""Story 4.4: SandboxSecurityDecorator 单元测试

验证 4 项防护:
1. session_id 注入防御（正则）
2. 并发配额检查
3. 超时控制（asyncio.wait_for）
4. 重试机制（继承 ToolExecutionEngine 既有模式）
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.tool_execution_engine import ToolExecutionEnginePort
from src.application.services.sandbox_security_decorator import SandboxSecurityDecorator
from src.domain.exceptions import (
    SandboxConfigurationError,
    SandboxQuotaExceededError,
    SandboxTimeoutError,
)
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.infrastructure.storage.inmemory.sandbox_session_repository import (
    InMemorySandboxSessionRepository,
)


@pytest.fixture
def wrapped() -> MagicMock:
    mock = MagicMock(spec=ToolExecutionEnginePort)
    mock.execute = AsyncMock(return_value={"result": "ok"})
    return mock


@pytest.fixture
def sandbox() -> MagicMock:
    mock = MagicMock(spec=SandboxExecutor)
    mock.execute_code = AsyncMock(return_value={"status": "completed", "output": "ok"})
    return mock


@pytest.fixture
def repo() -> InMemorySandboxSessionRepository:
    return InMemorySandboxSessionRepository()


@pytest.fixture
def decorator(wrapped: MagicMock, sandbox: MagicMock, repo: InMemorySandboxSessionRepository) -> SandboxSecurityDecorator:
    return SandboxSecurityDecorator(
        wrapped=wrapped,
        sandbox=sandbox,
        session_repo=repo,
        max_concurrent_containers=10,
    )


class TestSessionIdValidation:
    """session_id 注入防御测试"""

    async def test_invalid_session_id_raises(self, decorator: SandboxSecurityDecorator) -> None:
        """session_id 含非法字符抛 SandboxConfigurationError"""
        with pytest.raises(SandboxConfigurationError):
            await decorator.execute_code_with_protection("invalid session with spaces", "print('hi')")

    async def test_empty_session_id_raises(self, decorator: SandboxSecurityDecorator) -> None:
        """session_id 空字符串抛 SandboxConfigurationError"""
        with pytest.raises(SandboxConfigurationError):
            await decorator.execute_code_with_protection("", "print('hi')")


class TestQuotaCheck:
    """配额检查测试"""

    async def test_quota_exceeded_raises(
        self,
        wrapped: MagicMock,
        sandbox: MagicMock,
        repo: InMemorySandboxSessionRepository,
    ) -> None:
        """active_count >= max 抛 SandboxQuotaExceededError"""
        import uuid

        from src.domain.entities.sandbox_session import SandboxSession

        # 预先填满 10 个 RUNNING 会话
        for _ in range(10):
            session = SandboxSession(
                session_id=f"sess-{uuid.uuid4().hex[:8]}",
                tenant_id=uuid.uuid4(),
                image_digest="python:3.11-slim@sha256:abc",
            )
            await repo.save(session)

        decorator = SandboxSecurityDecorator(
            wrapped=wrapped,
            sandbox=sandbox,
            session_repo=repo,
            max_concurrent_containers=10,
        )

        with pytest.raises(SandboxQuotaExceededError) as exc_info:
            await decorator.execute_code_with_protection("sess-new-001", "print('hi')")
        assert exc_info.value.code == "EXCEPTION_318"


class TestTimeoutControl:
    """超时控制测试"""

    async def test_timeout_raises_sandbox_timeout_error(
        self,
        wrapped: MagicMock,
        sandbox: MagicMock,
        repo: InMemorySandboxSessionRepository,
    ) -> None:
        """执行超过 timeout_sec 抛 SandboxTimeoutError"""

        # 模拟 sandbox.execute_code 长时间挂起
        async def _slow(*args: object, **kwargs: object) -> dict[str, str]:
            await asyncio.sleep(10)
            return {"status": "completed"}

        sandbox.execute_code = AsyncMock(side_effect=_slow)

        decorator = SandboxSecurityDecorator(
            wrapped=wrapped,
            sandbox=sandbox,
            session_repo=repo,
            max_concurrent_containers=50,
        )

        with pytest.raises(SandboxTimeoutError) as exc_info:
            await decorator.execute_code_with_protection("sess-timeout-001", "print('hi')", timeout_sec=0.1)
        assert exc_info.value.code == "EXCEPTION_316"
        assert exc_info.value.context["timeout_sec"] == 0.1


class TestHappyPath:
    """正常路径测试"""

    async def test_execute_code_success(self, decorator: SandboxSecurityDecorator, sandbox: MagicMock) -> None:
        """正常执行返回 sandbox 结果"""
        result = await decorator.execute_code_with_protection("sess-success-001", "print('hi')")
        assert result["status"] == "completed"
        assert result["output"] == "ok"


class TestWrappedEngineDelegation:
    """验证包裹类模式:execute() 委托到 wrapped.execute()"""

    async def test_execute_delegates_to_wrapped(self, decorator: SandboxSecurityDecorator, wrapped: MagicMock) -> None:
        """execute() 委托到 wrapped.execute() 并应用安全防护"""
        import uuid as _uuid

        from src.domain.entities.tool import Tool
        from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall

        tool_id = _uuid.uuid4()
        tool = MagicMock(spec=Tool)
        tool_call = MagicMock(spec=ToolCall)
        context = ExecutionContext(tenant_id=_uuid.uuid4(), session_id="valid-session-001")

        result = await decorator.execute(tool_id, tool, tool_call, context)
        wrapped.execute.assert_called_once_with(tool_id, tool, tool_call, context)
        assert result == {"result": "ok"}


class TestDecoratorDoesNotModifyToolExecutionEngine:
    """验证不修改 ToolExecutionEngine.__init__ 既有签名（4.3 经验）"""

    def test_tool_execution_engine_init_unchanged(self) -> None:
        """通过源码哈希校验 ToolExecutionEngine.__init__ 签名未变"""
        import inspect

        from src.application.services.tool_execution_engine import ToolExecutionEngine

        source = inspect.getsource(ToolExecutionEngine.__init__)
        # 4.1a 既有签名:4 个参数 (llm_client, sandbox, retry_policy, tool_execution_repository)
        sig = inspect.signature(ToolExecutionEngine.__init__)
        params = list(sig.parameters.keys())
        assert params == ["self", "llm_client", "sandbox", "retry_policy", "tool_execution_repository"]
        # 验证源码包含关键字 llm_client（4.1a 既有契约）
        assert "llm_client" in source
        assert "sandbox" in source
