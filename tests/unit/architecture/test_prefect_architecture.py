"""Prefect 工作流架构约束验证测试

验证六边形架构约束：
- infrastructure/workflow/ 以外零 Prefect 导入
- WorkflowEnginePort 仅使用 stdlib 类型
- PrefectEngine 满足 WorkflowEnginePort Protocol
- OrchestrationService 不导入 infrastructure 层
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.domain.ports.workflow_engine import WorkflowEnginePort


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


class TestPrefectImportBoundary:
    """验证 infrastructure/workflow/ 以外零 Prefect 导入"""

    def test_domain_layer_no_prefect_imports(self) -> None:
        """domain 层不应导入 prefect"""
        domain_dir = Path("src/domain")
        for f in _get_python_files(domain_dir):
            imports = _scan_file_imports(f)
            assert "prefect" not in imports, f"{f} 导入了 prefect"

    def test_application_layer_no_prefect_imports(self) -> None:
        """application 层不应导入 prefect"""
        app_dir = Path("src/application")
        for f in _get_python_files(app_dir):
            imports = _scan_file_imports(f)
            assert "prefect" not in imports, f"{f} 导入了 prefect"

    def test_interfaces_layer_no_prefect_imports(self) -> None:
        """interfaces 层不应导入 prefect"""
        if_dir = Path("src/interfaces")
        if not if_dir.exists():
            pytest.skip("interfaces 目录不存在")
        for f in _get_python_files(if_dir):
            imports = _scan_file_imports(f)
            assert "prefect" not in imports, f"{f} 导入了 prefect"

    def test_prefect_imports_confined_to_workflow(self) -> None:
        """infrastructure 层 prefect 导入仅限于 workflow/ 子目录"""
        infra_dir = Path("src/infrastructure")
        workflow_dir = infra_dir / "workflow"
        for f in _get_python_files(infra_dir):
            if workflow_dir in f.parents or f.parent == workflow_dir:
                continue
            imports = _scan_file_imports(f)
            assert "prefect" not in imports, f"{f} 导入了 prefect（仅限 workflow/）"


class TestWorkflowEnginePortTypePurity:
    """验证 WorkflowEnginePort 仅使用 stdlib 类型"""

    def test_port_file_no_external_imports(self) -> None:
        """WorkflowEnginePort 文件不应有外部依赖导入"""
        port_file = Path("src/domain/ports/workflow_engine.py")
        imports = _scan_file_imports(port_file)

        external = {"src"}  # src 是项目内部
        non_stdlib = [i for i in imports if i not in external]
        # 允许的标准库模块
        stdlib_allowed = {
            "__future__",
            "typing",
            "abc",
            "dataclasses",
            "enum",
            "uuid",
            "datetime",
            "collections",
            "functools",
            "runtime_checkable",
        }
        violations = [i for i in non_stdlib if i not in stdlib_allowed and not i.startswith("src")]
        assert not violations, f"WorkflowEnginePort 有非标准库导入: {violations}"


class TestPrefectEngineProtocolCompliance:
    """验证 PrefectEngine 满足 WorkflowEnginePort Protocol"""

    def test_prefect_engine_satisfies_protocol(self) -> None:
        """PrefectEngine 应满足 WorkflowEnginePort Protocol"""
        from src.infrastructure.config.prefect import PrefectConfig
        from src.infrastructure.workflow.prefect_engine import PrefectEngine

        config = PrefectConfig()

        # PrefectEngine 需要 EventPublisher，使用 duck typing 验证
        class FakePublisher:
            async def publish(self, event):
                pass

        engine = PrefectEngine(config, FakePublisher())
        assert isinstance(engine, WorkflowEnginePort)


class TestOrchestrationServiceLayerPurity:
    """验证 OrchestrationService 不导入 infrastructure 层"""

    def test_orchestration_service_no_infrastructure_imports(self) -> None:
        """OrchestrationService 不应导入 infrastructure 层"""
        service_file = Path("src/application/services/orchestration_service.py")
        source = service_file.read_text(encoding="utf-8")
        assert "infrastructure" not in source, "OrchestrationService 不应导入 infrastructure 层"
        assert "prefect" not in source, "OrchestrationService 不应导入 prefect"


class TestEventChannelYamlConfig:
    """验证 RAGIndexed/ReportGenerated 注册于 configs/event_channels.yaml"""

    def test_rag_indexed_in_yaml(self) -> None:
        """RAGIndexed 应在 event_channels.yaml 中有 RELIABLE 映射"""
        import yaml

        with open("configs/event_channels.yaml") as f:
            config = yaml.safe_load(f)

        channels = config["event_channels"]
        assert "RAGIndexed" in channels
        assert channels["RAGIndexed"]["delivery_mode"] == "reliable"

    def test_report_generated_in_yaml(self) -> None:
        """ReportGenerated 应在 event_channels.yaml 中有 RELIABLE 映射"""
        import yaml

        with open("configs/event_channels.yaml") as f:
            config = yaml.safe_load(f)

        channels = config["event_channels"]
        assert "ReportGenerated" in channels
        assert channels["ReportGenerated"]["delivery_mode"] == "reliable"
