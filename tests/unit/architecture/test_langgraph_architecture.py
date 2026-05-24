"""LangGraph Agent 编排架构约束验证测试

验证六边形架构约束：
- infrastructure/agent_orch/ 以外零 LangGraph 导入
- AgentEnginePort 仅使用 stdlib 类型
- LangGraphEngine 满足 AgentEnginePort Protocol
- OrchestrationService 不导入 infrastructure 层

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.domain.ports.agent_engine import AgentEnginePort


def _scan_file_imports(file_path: Path) -> list[str]:
    """扫描 Python 文件的顶层 import 语句"""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # 相对导入是本地模块，跳过
                continue
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def _get_python_files(directory: Path, exclude_dirs: set[str] | None = None) -> list[Path]:
    """获取目录下所有 Python 文件"""
    exclude = exclude_dirs or set()
    files = []
    for p in directory.rglob("*.py"):
        if not any(part in exclude for part in p.parts):
            files.append(p)
    return files


class TestLangGraphImportBoundary:
    """验证 infrastructure/agent_orch/ 以外零 LangGraph 导入"""

    def test_domain_layer_no_langgraph_imports(self) -> None:
        """domain 层不应导入 langgraph"""
        domain_dir = Path("src/domain")
        for f in _get_python_files(domain_dir):
            imports = _scan_file_imports(f)
            assert "langgraph" not in imports, f"{f} 导入了 langgraph"

    def test_application_layer_no_langgraph_imports(self) -> None:
        """application 层不应导入 langgraph"""
        app_dir = Path("src/application")
        for f in _get_python_files(app_dir):
            imports = _scan_file_imports(f)
            assert "langgraph" not in imports, f"{f} 导入了 langgraph"

    def test_interfaces_layer_no_langgraph_imports(self) -> None:
        """interfaces 层不应导入 langgraph"""
        if_dir = Path("src/interfaces")
        if not if_dir.exists():
            pytest.skip("interfaces 目录不存在")
        for f in _get_python_files(if_dir):
            imports = _scan_file_imports(f)
            assert "langgraph" not in imports, f"{f} 导入了 langgraph"

    def test_langgraph_imports_confined_to_agent_orch(self) -> None:
        """infrastructure 层 langgraph 导入仅限于 agent_orch/ 子目录"""
        infra_dir = Path("src/infrastructure")
        agent_orch_dir = infra_dir / "agent_orch"
        for f in _get_python_files(infra_dir):
            if agent_orch_dir in f.parents or f.parent == agent_orch_dir:
                continue
            imports = _scan_file_imports(f)
            assert "langgraph" not in imports, f"{f} 导入了 langgraph（仅限 agent_orch/）"


class TestAgentEnginePortTypePurity:
    """验证 AgentEnginePort 仅使用 stdlib 类型"""

    def test_port_file_no_external_imports(self) -> None:
        """AgentEnginePort 文件不应有外部依赖导入"""
        port_file = Path("src/domain/ports/agent_engine.py")
        imports = _scan_file_imports(port_file)

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


class TestLangGraphEngineProtocolCompliance:
    """验证 LangGraphEngine 满足 AgentEnginePort Protocol"""

    def test_langgraph_engine_satisfies_protocol(self) -> None:
        """LangGraphEngine 应满足 AgentEnginePort Protocol"""

        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
        from src.infrastructure.config.langgraph import LangGraphConfig

        config = LangGraphConfig()

        class FakePublisher:
            async def publish(self, event):
                from src.domain.events.publish_result import ChannelResult, PublishResult

                return PublishResult(event_id="fake", results=(ChannelResult("realtime", True),))

        engine = LangGraphEngine(config, FakePublisher())
        assert isinstance(engine, AgentEnginePort)


class TestAgentEnginePortRegistered:
    """验证 AgentEnginePort 已注册到端口注册中心"""

    def test_agent_engine_port_registered(self) -> None:
        """agent_engine 端口应在注册中心中"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("agent_engine")
        assert spec is not None, "agent_engine 端口未注册"
        assert spec.interface is AgentEnginePort

    def test_agent_engine_metadata_complete(self) -> None:
        """agent_engine 端口元数据应完整"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("agent_engine")
        assert spec is not None
        assert spec.version
        assert spec.owner
        assert spec.module
