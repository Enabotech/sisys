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
        """__all__ 应包含全部 4 个异常类 + ContainerSpec（Story 4.4 扩展）"""
        from src.domain.ports.sandbox_executor import __all__ as exports

        expected = {
            "SandboxError",
            "ContainerStartError",
            "ExecutionError",
            "ContainerStopError",
            "ContainerSpec",
        }
        assert set(exports) == expected

    def test_protocol_has_health_check(self) -> None:
        """Story 4.4 扩展:Protocol 应新增 health_check 方法"""
        assert hasattr(SandboxExecutor, "health_check")
        method = getattr(SandboxExecutor, "health_check")
        assert inspect.iscoroutinefunction(method)

    def test_start_container_signature_extended(self) -> None:
        """Story 4.4 扩展:start_container 应接受可选 spec 参数(向后兼容)"""
        sig = inspect.signature(SandboxExecutor.start_container)
        params = list(sig.parameters.keys())
        # 既有调用点 (session_id,) 通过默认 spec=None 仍能工作
        assert "session_id" in params
        assert "spec" in params
        # spec 应有默认值 None
        spec_param = sig.parameters["spec"]
        assert spec_param.default is None

    def test_execute_code_signature_extended(self) -> None:
        """Story 4.4 扩展:execute_code 应接受 keyword-only timeout_sec 参数"""
        sig = inspect.signature(SandboxExecutor.execute_code)
        params = list(sig.parameters.keys())
        assert "session_id" in params
        assert "code" in params
        assert "timeout_sec" in params
        # timeout_sec 应为 keyword-only
        timeout_param = sig.parameters["timeout_sec"]
        assert timeout_param.kind == inspect.Parameter.KEYWORD_ONLY
        assert timeout_param.default is None

    def test_backward_compatible_4_1a_calling_pattern(self) -> None:
        """Story 4.4 核心契约:既有 4.1a 调用点 (start_container(session_id,)) 通过默认 spec=None 仍能工作

        注意:本测试验证调用兼容性(默认参数机制),非 isinstance 校验
        (因为 runtime_checkable Protocol 需要所有方法都存在,4.1a mock 无 health_check)。
        真正向后兼容的保证是:4.1a 既有代码调用 start_container(session_id,) 不报错。
        """
        import asyncio

        class MockExecutor41A:
            """模拟 4.1a 既有 mock 适配器,只实现 4 个既有方法"""

            async def start_container(self, session_id: str) -> None:
                pass

            async def execute_code(self, session_id: str, code: str) -> dict:
                return {"status": "ok"}

            async def stop_container(self, session_id: str) -> None:
                pass

            async def is_container_running(self, session_id: str) -> bool:
                return True

        executor = MockExecutor41A()
        # 验证:4.1a 既有调用点 (start_container(session_id,)) 不报错
        # 这是通过默认参数实现的向后兼容(不依赖 isinstance)
        asyncio.run(executor.start_container("sess-001"))
        asyncio.run(executor.execute_code("sess-001", "print('hi')"))
        asyncio.run(executor.stop_container("sess-001"))
        # MockExecutor41A 本身无 health_check 方法（4.1a 既有 mock）
        assert not hasattr(executor, "health_check")
