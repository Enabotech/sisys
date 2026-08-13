"""SemanticRouterProtocol 端口契约测试

验证 SemanticRouterProtocol 的结构化子类型合规性。
端口为 Protocol-only，基础设施层实现。
"""

from __future__ import annotations

import inspect

from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol


class TestSemanticRouterProtocolContract:
    """测试 SemanticRouterProtocol 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(SemanticRouterProtocol, "_is_runtime_protocol")
        assert SemanticRouterProtocol._is_runtime_protocol is True

    def test_route_method_exists(self) -> None:
        """验证 route 方法存在且为异步"""
        assert hasattr(SemanticRouterProtocol, "route")
        method = getattr(SemanticRouterProtocol, "route")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_route_method_signature(self) -> None:
        """验证 route(task_context) -> tuple[str, float]"""
        method = getattr(SemanticRouterProtocol, "route")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "task_context"]
        assert sig.return_annotation == "tuple[str, float]"

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockRouter:
            async def route(self, task_context: dict) -> tuple[str, float]:
                return "", 0.0

        router = MockRouter()
        assert isinstance(router, SemanticRouterProtocol)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadRouter:
            pass

        assert not isinstance(BadRouter(), SemanticRouterProtocol)


__all__ = ["TestSemanticRouterProtocolContract"]
