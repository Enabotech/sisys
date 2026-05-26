"""AgentEnginePort 单元测试

验证 Protocol 签名、runtime_checkable、FlowStatus 返回类型、零外部依赖
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, get_type_hints

from src.domain.value_objects.flow_status import FlowStatus


class TestAgentEnginePortProtocol:
    """AgentEnginePort Protocol 定义验证"""

    def test_agent_engine_port_is_runtime_checkable(self) -> None:
        """AgentEnginePort 应使用 @runtime_checkable 装饰器"""
        from src.domain.ports.agent_engine import AgentEnginePort

        assert hasattr(AgentEnginePort, "__protocol_attrs__") or hasattr(AgentEnginePort, "_is_protocol"), (
            "AgentEnginePort 应为 Protocol"
        )

    def test_agent_engine_port_has_submit_graph(self) -> None:
        """AgentEnginePort 应定义 submit_graph 方法"""
        from src.domain.ports.agent_engine import AgentEnginePort

        assert hasattr(AgentEnginePort, "submit_graph"), "AgentEnginePort 应有 submit_graph 方法"

    def test_agent_engine_port_has_get_graph_status(self) -> None:
        """AgentEnginePort 应定义 get_graph_status 方法"""
        from src.domain.ports.agent_engine import AgentEnginePort

        assert hasattr(AgentEnginePort, "get_graph_status"), "AgentEnginePort 应有 get_graph_status 方法"

    def test_submit_graph_signature(self) -> None:
        """submit_graph 签名：(self, graph_name: str, parameters: dict[str, Any]) -> str"""
        from src.domain.ports.agent_engine import AgentEnginePort

        hints = get_type_hints(AgentEnginePort.submit_graph)
        assert "graph_name" in hints
        assert "return" in hints
        assert hints["return"] is str

    def test_get_graph_status_returns_flow_status(self) -> None:
        """get_graph_status 返回类型应为 FlowStatus"""
        from src.domain.ports.agent_engine import AgentEnginePort

        hints = get_type_hints(AgentEnginePort.get_graph_status)
        assert "return" in hints
        assert hints["return"] is FlowStatus

    def test_structural_subtyping(self) -> None:
        """满足签名的类应通过 isinstance 检查"""

        class FakeEngine:
            async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
                return "run-123"

            async def get_graph_status(self, graph_run_id: str) -> FlowStatus:
                return FlowStatus.COMPLETED

        from src.domain.ports.agent_engine import AgentEnginePort

        assert isinstance(FakeEngine(), AgentEnginePort)

    def test_port_file_no_external_imports(self) -> None:
        """AgentEnginePort 文件不应有外部依赖导入"""
        port_file = Path("src/domain/ports/agent_engine.py")
        imports: list[str] = []
        tree = ast.parse(port_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])

        external_forbidden = {
            "langgraph",
            "langchain",
            "prefect",
            "fastapi",
            "pydantic",
            "sqlalchemy",
            "redis",
            "neo4j",
            "qdrant",
            "minio",
        }
        violations = [i for i in imports if i in external_forbidden]
        assert not violations, f"AgentEnginePort 有外部依赖导入: {violations}"

    def test_file_starts_with_future_annotations(self) -> None:
        """文件首行应为 from __future__ import annotations"""
        content = Path("src/domain/ports/agent_engine.py").read_text(encoding="utf-8")
        assert "from __future__ import annotations" in content
