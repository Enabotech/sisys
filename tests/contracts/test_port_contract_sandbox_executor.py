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
        assert SandboxExecutor._is_runtime_protocol is True

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
        """Story 4.4 扩展:start_container 接受 session_id + 可选 spec"""
        method = getattr(SandboxExecutor, "start_container")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "session_id" in params
        assert "spec" in params
        # spec 应有默认值 None(向后兼容)
        assert sig.parameters["spec"].default is None

    def test_execute_code_signature(self) -> None:
        """Story 4.4 扩展:execute_code 接受 session_id + code + keyword-only timeout_sec"""
        method = getattr(SandboxExecutor, "execute_code")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "session_id" in params
        assert "code" in params
        assert "timeout_sec" in params
        # timeout_sec 应为 keyword-only + 默认 None
        timeout_param = sig.parameters["timeout_sec"]
        assert timeout_param.kind == inspect.Parameter.KEYWORD_ONLY
        assert timeout_param.default is None

    def test_health_check_method_exists(self) -> None:
        """Story 4.4 新增:health_check 方法存在"""
        method = getattr(SandboxExecutor, "health_check")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_compliant_implementation(self) -> None:
        class MockExecutor:
            async def start_container(self, session_id: str, spec: object | None = None) -> None:
                pass

            async def execute_code(self, session_id: str, code: str, *, timeout_sec: float | None = None) -> dict:
                return {"status": "ok"}

            async def stop_container(self, session_id: str) -> None:
                pass

            async def is_container_running(self, session_id: str) -> bool:
                return True

            async def health_check(self) -> bool:
                return True

        executor = MockExecutor()
        assert isinstance(executor, SandboxExecutor)

    def test_noncompliant_implementation_fails(self) -> None:
        class BadExecutor:
            pass

        assert not isinstance(BadExecutor(), SandboxExecutor)


__all__ = ["TestSandboxExecutorContract"]
