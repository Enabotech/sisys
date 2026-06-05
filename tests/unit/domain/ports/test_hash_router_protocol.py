"""HashRouterProtocol Protocol 行为验证测试

验证哈希路由端口的运行时类型检查、同步方法签名和一致性映射行为
"""

from __future__ import annotations

import asyncio

from src.domain.ports.hash_router_protocol import HashRouterProtocol


class TestHashRouterProtocolRuntimeCheckable:
    """HashRouterProtocol 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 route 方法的类应通过 isinstance 检查"""

        class FakeRouter:
            def route(self, session_id: str) -> str:
                return f"node-{hash(session_id) % 3}"

        assert isinstance(FakeRouter(), HashRouterProtocol)

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现 route 方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def other(self) -> None:
                pass

        assert not isinstance(Incompatible(), HashRouterProtocol)

    def test_class_with_async_route_passes_isinstance(self) -> None:
        """异步 route 方法也能通过 isinstance（运行时限制，不区分同步/异步）"""

        class AsyncRouter:
            async def route(self, session_id: str) -> str:
                return "node-1"

        # runtime_checkable 只检查方法名存在性
        assert isinstance(AsyncRouter(), HashRouterProtocol)


class TestHashRouterProtocolMethodSignature:
    """HashRouterProtocol 方法签名验证"""

    def test_route_is_synchronous(self) -> None:
        """route 应为同步方法"""
        assert not asyncio.iscoroutinefunction(HashRouterProtocol.route)

    def test_route_returns_str(self) -> None:
        """route 应返回 str"""

        class FakeRouter:
            def route(self, session_id: str) -> str:
                return "node-1"

        router = FakeRouter()
        result = router.route("session-abc")
        assert isinstance(result, str)

    def test_route_receives_session_id(self) -> None:
        """route 应正确接收 session_id 参数"""
        received: list[str] = []

        class SpyRouter:
            def route(self, session_id: str) -> str:
                received.append(session_id)
                return "node-1"

        router = SpyRouter()
        router.route("sess-123")
        assert received == ["sess-123"]

    def test_route_deterministic_mapping(self) -> None:
        """相同 session_id 应映射到同一节点"""

        class ConsistentRouter:
            def __init__(self) -> None:
                self._mapping: dict[str, str] = {}

            def route(self, session_id: str) -> str:
                if session_id not in self._mapping:
                    self._mapping[session_id] = f"node-{hash(session_id) % 3}"
                return self._mapping[session_id]

        router = ConsistentRouter()
        result1 = router.route("session-x")
        result2 = router.route("session-x")
        assert result1 == result2

    def test_route_different_sessions_may_map_differently(self) -> None:
        """不同 session_id 可能映射到不同节点"""

        class HashBasedRouter:
            def route(self, session_id: str) -> str:
                return f"node-{hash(session_id) % 5}"

        router = HashBasedRouter()
        results = {router.route(f"session-{i}") for i in range(20)}
        # 20 个不同 session 应映射到至少 2 个不同节点
        assert len(results) >= 2
