"""SandboxExecutor Protocol 端口契约测试

验证沙箱执行端口的协议定义、异常重导出和运行时检查行为。
"""

from __future__ import annotations

import inspect

from src.domain.ports.sandbox_executor import SandboxExecutor


class TestSandboxExecutorProtocol:
    """Protocol 端口契约测试"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol 应支持运行时检查"""
        assert hasattr(SandboxExecutor, "_is_runtime_protocol")

    def test_protocol_has_start_container(self) -> None:
        """协议应定义 start_container 方法"""
        assert hasattr(SandboxExecutor, "start_container")
        sig = inspect.signature(SandboxExecutor.start_container)
        assert "session_id" in sig.parameters

    def test_protocol_has_execute_code(self) -> None:
        """协议应定义 execute_code 方法"""
        assert hasattr(SandboxExecutor, "execute_code")
        sig = inspect.signature(SandboxExecutor.execute_code)
        assert "session_id" in sig.parameters
        assert "code" in sig.parameters

    def test_protocol_has_stop_container(self) -> None:
        """协议应定义 stop_container 方法"""
        assert hasattr(SandboxExecutor, "stop_container")
        sig = inspect.signature(SandboxExecutor.stop_container)
        assert "session_id" in sig.parameters

    def test_protocol_has_is_container_running(self) -> None:
        """协议应定义 is_container_running 方法"""
        assert hasattr(SandboxExecutor, "is_container_running")
        sig = inspect.signature(SandboxExecutor.is_container_running)
        assert "session_id" in sig.parameters

    def test_non_conforming_class_fails_isinstance(self) -> None:
        """不符合协议的类无法通过 isinstance 检查"""

        class NonConforming:
            pass

        assert not isinstance(NonConforming(), SandboxExecutor)


class TestSandboxExecutorAllExports:
    """验证 __all__ 中重导出的异常类可从端口模块导入"""

    def test_sandbox_error_exported(self) -> None:
        """SandboxError 应可从端口模块导入"""
        from src.domain.exceptions.sandbox_exceptions import SandboxError as Orig
        from src.domain.ports.sandbox_executor import SandboxError

        assert SandboxError is Orig

    def test_container_start_error_exported(self) -> None:
        """ContainerStartError 应可从端口模块导入"""
        from src.domain.exceptions.sandbox_exceptions import ContainerStartError as Orig
        from src.domain.ports.sandbox_executor import ContainerStartError

        assert ContainerStartError is Orig

    def test_execution_error_exported(self) -> None:
        """ExecutionError 应可从端口模块导入"""
        from src.domain.exceptions.sandbox_exceptions import ExecutionError as Orig
        from src.domain.ports.sandbox_executor import ExecutionError

        assert ExecutionError is Orig

    def test_container_stop_error_exported(self) -> None:
        """ContainerStopError 应可从端口模块导入"""
        from src.domain.exceptions.sandbox_exceptions import ContainerStopError as Orig
        from src.domain.ports.sandbox_executor import ContainerStopError

        assert ContainerStopError is Orig

    def test_all_exports_completeness(self) -> None:
        """__all__ 应包含全部 4 个异常类"""
        from src.domain.ports.sandbox_executor import __all__ as exports

        expected = {"SandboxError", "ContainerStartError", "ExecutionError", "ContainerStopError"}
        assert set(exports) == expected
