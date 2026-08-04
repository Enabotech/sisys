"""SandboxExecutor 端口契约测试

验证 SandboxExecutor Protocol 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.sandbox_executor import SandboxExecutor


class TestSandboxExecutorContract:
    """测试 SandboxExecutor 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(SandboxExecutor, "_is_runtime_protocol")
        assert SandboxExecutor._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_start_container_method_exists(self) -> None:
        assert hasattr(SandboxExecutor, "start_container")
        method = getattr(SandboxExecutor, "start_container")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_execute_code_method_exists(self) -> None:
        assert hasattr(SandboxExecutor, "execute_code")
        method = getattr(SandboxExecutor, "execute_code")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_stop_container_method_exists(self) -> None:
        assert hasattr(SandboxExecutor, "stop_container")
        method = getattr(SandboxExecutor, "stop_container")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_is_container_running_method_exists(self) -> None:
        assert hasattr(SandboxExecutor, "is_container_running")
        method = getattr(SandboxExecutor, "is_container_running")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_start_container_signature(self) -> None:
        method = getattr(SandboxExecutor, "start_container")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "session_id"]

    def test_compliant_implementation(self) -> None:
        class MockExecutor:
            async def start_container(self, session_id: str) -> None:
                pass

            async def execute_code(self, session_id: str, code: str) -> dict:
                return {"status": "ok"}

            async def stop_container(self, session_id: str) -> None:
                pass

            async def is_container_running(self, session_id: str) -> bool:
                return True

        executor = MockExecutor()
        assert isinstance(executor, SandboxExecutor)

    def test_noncompliant_implementation_fails(self) -> None:
        class BadExecutor:
            pass

        assert not isinstance(BadExecutor(), SandboxExecutor)


__all__ = ["TestSandboxExecutorContract"]
