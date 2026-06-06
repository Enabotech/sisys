"""SemanticRouterProtocol Protocol 行为验证测试

验证语义路由端口的运行时类型检查、异步方法签名和返回类型契约
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol


class TestSemanticRouterProtocolRuntimeCheckable:
    """SemanticRouterProtocol 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 async route 方法的类应通过 isinstance 检查"""

        class FakeRouter:
            async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                return "target-1", 0.95

        assert isinstance(FakeRouter(), SemanticRouterProtocol)

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现 route 方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def sync_route(self) -> str:
                return ""

        assert not isinstance(Incompatible(), SemanticRouterProtocol)

    def test_sync_route_does_not_satisfy_async_protocol(self) -> None:
        """同步 route 方法虽然通过 isinstance 但不满足异步契约"""

        class SyncRouter:
            def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                return "target", 0.5

        instance = SyncRouter()
        # runtime_checkable 不区分同步/异步，isinstance 可能通过
        # 但行为上 route 不是协程函数
        assert not asyncio.iscoroutinefunction(instance.route)


class TestSemanticRouterProtocolMethodSignature:
    """SemanticRouterProtocol 方法签名验证"""

    def test_route_is_async(self) -> None:
        """route 应为异步方法"""
        assert asyncio.iscoroutinefunction(SemanticRouterProtocol.route)

    async def test_route_returns_tuple_str_float(self) -> None:
        """route 应返回 tuple[str, float]"""

        class FakeRouter:
            async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                return "target-1", 0.95

        router = FakeRouter()
        result = await router.route({"description": "test task"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], float)

    async def test_route_accepts_dict_context(self) -> None:
        """route 应接受 dict 参数"""
        received: dict[str, Any] = {}

        class SpyRouter:
            async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                received.update(task_context)
                return "matched", 0.8

        router = SpyRouter()
        context = {"description": "战略分析", "priority": "high"}
        await router.route(context)
        assert received["description"] == "战略分析"
        assert received["priority"] == "high"

    async def test_route_with_empty_context(self) -> None:
        """空上下文应返回有效元组"""

        class FakeRouter:
            async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                if not task_context:
                    return "", 0.0
                return "target", 0.5

        router = FakeRouter()
        target, score = await router.route({})
        assert target == ""
        assert score == 0.0

    async def test_route_returns_zero_score_for_no_match(self) -> None:
        """无匹配时应返回零分"""

        class FakeRouter:
            async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
                return "", 0.0

        router = FakeRouter()
        target, score = await router.route({"description": "unknown"})
        assert score == 0.0
