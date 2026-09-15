"""SandboxExecutor 端口契约测试

验证 SandboxExecutor Protocol 的结构化子类型合规性。

Story 4.4 扩展:
- start_container 新增可选 spec: ContainerSpec | None = None 参数(向后兼容)
- execute_code 新增可选 timeout_sec: float | None = None keyword-only 参数
- 新增 health_check() 方法(Docker daemon 健康检查)
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

    def test_health_check_method_exists(self) -> None:
        """Story 4.4 新增 health_check 方法"""
        assert hasattr(SandboxExecutor, "health_check")
        method = getattr(SandboxExecutor, "health_check")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_start_container_signature(self) -> None:
        """start_container 签名:self, session_id, spec=None(Story 4.4 默认参数扩展)"""
        method = getattr(SandboxExecutor, "start_container")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        # Story 4.4 新增可选 spec 参数(默认 None),向后兼容 4.1a 调用
        assert params == ["self", "session_id", "spec"]

    def test_execute_code_signature(self) -> None:
        """execute_code 签名:self, session_id, code, *, timeout_sec=None(Story 4.4)"""
        method = getattr(SandboxExecutor, "execute_code")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        # Story 4.4 新增 keyword-only timeout_sec 参数
        assert params == ["self", "session_id", "code", "timeout_sec"]

    def test_compliant_implementation(self) -> None:
        class MockExecutor:
            """Story 4.4 要求 health_check 也存在(新增方法)"""

            async def start_container(self, session_id: str, spec: object = None) -> None:
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

    def test_compliant_implementation_without_health_check_fails(self) -> None:
        """缺少 health_check 方法的实现不再合规(Story 4.4 新增约束)"""

        class LegacyExecutor:
            """4.1a 既有实现,缺少 health_check 方法"""

            async def start_container(self, session_id: str, spec: object = None) -> None:
                pass

            async def execute_code(self, session_id: str, code: str, *, timeout_sec: float | None = None) -> dict:
                return {"status": "ok"}

            async def stop_container(self, session_id: str) -> None:
                pass

            async def is_container_running(self, session_id: str) -> bool:
                return True

        # 缺 health_check 方法 → 不再是 SandboxExecutor 实例
        assert not isinstance(LegacyExecutor(), SandboxExecutor)

    def test_noncompliant_implementation_fails(self) -> None:
        class BadExecutor:
            pass

        assert not isinstance(BadExecutor(), SandboxExecutor)


__all__ = ["TestSandboxExecutorContract"]
