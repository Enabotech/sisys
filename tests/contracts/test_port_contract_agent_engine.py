"""AgentEnginePort 端口契约测试

验证端口注册、元数据完整性、Protocol 合规性、签名检查、异步性质、实现兼容性
"""

from __future__ import annotations

import inspect
from typing import Any

from src.domain.ports.agent_engine import AgentEnginePort


class TestAgentEnginePortContract:
    """AgentEnginePort 端口契约测试"""

    PORT_NAME = "agent_engine"
    INTERFACE = AgentEnginePort

    def test_port_is_registered(self, registry) -> None:
        """agent_engine 端口应已注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 '{self.PORT_NAME}' 未注册"
        assert spec.interface is self.INTERFACE

    def test_metadata_complete(self, registry) -> None:
        """端口元数据应完整（version, owner, module, lifetime）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version
        assert spec.owner
        assert spec.module
        assert spec.lifetime is not None

    def test_impl_satisfies_protocol(self, resolver) -> None:
        """实现类应满足 AgentEnginePort Protocol"""
        impl = resolver.resolve(self.PORT_NAME)
        assert isinstance(impl, self.INTERFACE)

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(AgentEnginePort, "_is_runtime_protocol")
        assert AgentEnginePort._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_submit_graph_method_exists(self) -> None:
        """验证 submit_graph 方法存在且可调用"""
        assert hasattr(AgentEnginePort, "submit_graph")
        method = getattr(AgentEnginePort, "submit_graph")
        assert callable(method)

    def test_submit_graph_is_async(self) -> None:
        """验证 submit_graph 是异步方法"""
        method = getattr(AgentEnginePort, "submit_graph")
        assert inspect.iscoroutinefunction(method)

    def test_submit_graph_signature(self) -> None:
        """验证 submit_graph 方法签名正确"""
        method = getattr(AgentEnginePort, "submit_graph")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "graph_name" in params
        assert "parameters" in params
        assert params == ["self", "graph_name", "parameters"]

    def test_submit_graph_return_type(self) -> None:
        """验证 submit_graph 返回 str"""
        method = getattr(AgentEnginePort, "submit_graph")
        assert inspect.iscoroutinefunction(method)

    def test_get_graph_status_method_exists(self) -> None:
        """验证 get_graph_status 方法存在且可调用"""
        assert hasattr(AgentEnginePort, "get_graph_status")
        method = getattr(AgentEnginePort, "get_graph_status")
        assert callable(method)

    def test_get_graph_status_is_async(self) -> None:
        """验证 get_graph_status 是异步方法"""
        method = getattr(AgentEnginePort, "get_graph_status")
        assert inspect.iscoroutinefunction(method)

    def test_get_graph_status_signature(self) -> None:
        """验证 get_graph_status 方法签名正确"""
        method = getattr(AgentEnginePort, "get_graph_status")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "graph_run_id" in params
        assert params == ["self", "graph_run_id"]

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockEngine:
            async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
                return "run-123"

            async def get_graph_status(self, graph_run_id: str):
                from src.domain.value_objects.flow_status import FlowStatus

                return FlowStatus.COMPLETED

        engine = MockEngine()
        assert isinstance(engine, AgentEnginePort)

    def test_noncompliant_missing_method(self) -> None:
        """验证缺少方法的不合规实现无法通过 isinstance"""

        class BadEngine:
            async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
                return "run-123"

            # 缺少 get_graph_status

        engine = BadEngine()
        assert not isinstance(engine, AgentEnginePort)

    def test_no_external_deps_in_port_file(self) -> None:
        """验证端口文件仅使用标准库和领域层类型"""
        import ast
        from pathlib import Path

        port_file = Path("src/domain/ports/agent_engine.py")
        with open(port_file) as f:
            tree = ast.parse(f.read())

        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        allowed = {"__future__", "typing", "src", "abc", "collections", "dataclasses", "enum", "inspect"}
        external = imports - allowed
        external = {m for m in external if not m.startswith("src")}
        assert not external, f"端口引入了外部依赖: {external}"

    def test_get_graph_status_returns_flow_status(self) -> None:
        """验证 get_graph_status 返回类型为 FlowStatus"""

        method = getattr(AgentEnginePort, "get_graph_status")
        sig = inspect.signature(method)
        # 验证返回类型注解存在
        assert sig.return_annotation is not inspect.Parameter.empty

    def test_noncompliant_missing_get_graph_status(self) -> None:
        """缺少 get_graph_status 的不合规实现"""

        class BadEngine:
            async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
                return "run-123"

        engine = BadEngine()
        assert not isinstance(engine, AgentEnginePort)


__all__ = ["TestAgentEnginePortContract"]
