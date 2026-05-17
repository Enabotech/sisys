"""Protocol 结构化类型验证测试。

验证所有 domain port Protocol 的 runtime_checkable 装饰器和
结构化子类型检查行为。
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.ports.connection_manager import ConnectionManager
from src.domain.ports.hash_router_protocol import HashRouterProtocol
from src.domain.ports.sandbox_executor_protocol import SandboxExecutorProtocol
from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol


class TestHashRouterProtocol:
    """HashRouterProtocol 结构化类型测试。"""

    def test_runtime_checkable_with_compatible_class(self) -> None:
        """实现 route 方法的类应通过 isinstance 检查。"""

        class CompatibleRouter:
            def route(self, session_id: str) -> str:
                return f"node-{session_id}"

        instance = CompatibleRouter()
        assert isinstance(instance, HashRouterProtocol)

    def test_runtime_checkable_with_incompatible_class(self) -> None:
        """不实现 route 方法的类不应通过 isinstance 检查。"""

        class IncompatibleClass:
            def other_method(self) -> None:
                pass

        instance = IncompatibleClass()
        assert not isinstance(instance, HashRouterProtocol)

    def test_route_method_signature(self) -> None:
        """route 方法应接受 session_id:str 返回 str。"""

        class RouterImpl:
            def route(self, session_id: str) -> str:
                return "node-1"

        router = RouterImpl()
        result = router.route("session-123")
        assert isinstance(result, str)


class TestSemanticRouterProtocol:
    """SemanticRouterProtocol 结构化类型测试。"""

    def test_runtime_checkable_with_compatible_class(self) -> None:
        """实现 async route 方法的类应通过 isinstance 检查。"""

        class CompatibleRouter:
            async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                return "target", 0.95

        instance = CompatibleRouter()
        assert isinstance(instance, SemanticRouterProtocol)

    def test_runtime_checkable_with_incompatible_class(self) -> None:
        """不实现 async route 方法的类不应通过 isinstance 检查。"""

        class IncompatibleClass:
            def sync_route(self) -> str:
                return "target"

        instance = IncompatibleClass()
        assert not isinstance(instance, SemanticRouterProtocol)


class TestSandboxExecutorProtocol:
    """SandboxExecutorProtocol 结构化类型测试。"""

    def test_runtime_checkable_with_compatible_class(self) -> None:
        """实现所有三个方法的类应通过 isinstance 检查。"""

        class CompatibleExecutor:
            async def start_container(self, session_id: str) -> None:
                pass

            async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
                return {"status": "ok"}

            async def stop_container(self, session_id: str) -> None:
                pass

        instance = CompatibleExecutor()
        assert isinstance(instance, SandboxExecutorProtocol)

    def test_runtime_checkable_missing_method(self) -> None:
        """缺少方法不应通过 isinstance 检查。"""

        class PartialExecutor:
            async def start_container(self, session_id: str) -> None:
                pass

        instance = PartialExecutor()
        assert not isinstance(instance, SandboxExecutorProtocol)

    @pytest.mark.asyncio
    async def test_execute_code_returns_dict(self) -> None:
        """execute_code 应返回 dict。"""

        class ExecutorImpl:
            async def start_container(self, session_id: str) -> None:
                pass

            async def execute_code(self, session_id: str, code: str) -> dict[str, Any]:
                return {"status": "success", "output": "hello"}

            async def stop_container(self, session_id: str) -> None:
                pass

        executor = ExecutorImpl()
        result = await executor.execute_code("sess-1", "print('hello')")
        assert isinstance(result, dict)
        assert "status" in result


class TestSnapshotRepositoryProtocol:
    """SnapshotRepositoryProtocol 结构化类型测试。"""

    def test_runtime_checkable_with_compatible_class(self) -> None:
        """实现所有方法的类应通过 isinstance 检查。"""

        class CompatibleRepo:
            async def save(self, snapshot: Any) -> None:
                pass

            async def load(self, session_id: str) -> Any:
                return None

            async def delete(self, session_id: str) -> None:
                pass

        instance = CompatibleRepo()
        assert isinstance(instance, SnapshotRepositoryProtocol)

    def test_runtime_checkable_missing_method(self) -> None:
        """缺少方法不应通过 isinstance 检查。"""

        class PartialRepo:
            async def save(self, snapshot: Any) -> None:
                pass

        instance = PartialRepo()
        assert not isinstance(instance, SnapshotRepositoryProtocol)


class TestConnectionManager:
    """ConnectionManager Protocol 测试。

    注意：Python @runtime_checkable 对含 async def 的 Protocol 的
    isinstance 检查存在已知限制（仅检查方法名存在性，不区分同步/异步）。
    因此 ConnectionManager 的健康检查方法签名通过行为测试验证。
    """

    def test_health_check_is_async(self) -> None:
        """health_check 应为异步方法。"""
        import asyncio

        assert asyncio.iscoroutinefunction(ConnectionManager.health_check)

    def test_close_is_async(self) -> None:
        """close 应为异步方法。"""
        import asyncio

        assert asyncio.iscoroutinefunction(ConnectionManager.close)

    def test_get_client_default_raises_not_implemented(self) -> None:
        """默认 get_client 应抛出 NotImplementedError。"""

        class _StubManager(ConnectionManager):
            """委托 get_client 到 Protocol 默认实现。"""

            async def health_check(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            def get_client(self) -> Any:
                return ConnectionManager.get_client(self)

        manager = _StubManager()
        with pytest.raises(NotImplementedError, match="get_client"):
            manager.get_client()

    def test_neo4j_manager_is_instance(self) -> None:
        """Neo4jManager 应满足 ConnectionManager Protocol。"""
        from unittest.mock import MagicMock

        from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager

        driver = MagicMock()
        manager = Neo4jManager(driver)
        assert isinstance(manager, ConnectionManager)

    def test_incompatible_class_not_instance(self) -> None:
        """不实现必要方法的类不应通过 isinstance 检查。"""

        class IncompatibleClass:
            def other_method(self) -> None:
                pass

        instance = IncompatibleClass()
        assert not isinstance(instance, ConnectionManager)
