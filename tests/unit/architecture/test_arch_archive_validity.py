"""档案有效期管理架构验证测试

验证六边形架构约束（依赖方向、领域层零依赖）。
"""

from __future__ import annotations


class TestArchiveValidityArchitecture:
    """档案有效期管理架构约束"""

    def test_domain_entity_imports_only_standard_lib(self) -> None:
        """StrategicArchive 实体仅依赖标准库和领域异常"""
        import ast
        import pathlib

        filepath = pathlib.Path("src/domain/entities/strategic_archive.py")
        assert filepath.exists(), f"{filepath} 不存在"
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # 允许标准库和 src.domain 前缀
                    if not any(
                        alias.name.startswith(p)
                        for p in ("src.domain", "typing", "dataclasses", "datetime", "enum", "uuid", "__future__")
                    ):
                        assert False, f"领域实体导入外部模块: {alias.name}"
            if isinstance(node, ast.ImportFrom):
                if node.module and not any(
                    node.module.startswith(p)
                    for p in ("src.domain", "typing", "dataclasses", "datetime", "enum", "uuid", "__future__")
                ):
                    assert False, f"领域实体导入外部模块: {node.module}"

    def test_domain_events_imports_only_standard_lib(self) -> None:
        """档案事件仅依赖标准库和领域层"""
        import ast
        import pathlib

        filepath = pathlib.Path("src/domain/events/archive_events.py")
        assert filepath.exists(), f"{filepath} 不存在"
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not any(
                        alias.name.startswith(p) for p in ("src.domain", "dataclasses", "datetime", "uuid", "__future__")
                    ):
                        assert False, f"领域事件导入外部模块: {alias.name}"
            if isinstance(node, ast.ImportFrom):
                if node.module and not any(
                    node.module.startswith(p) for p in ("src.domain", "dataclasses", "datetime", "uuid", "__future__")
                ):
                    assert False, f"领域事件导入外部模块: {node.module}"

    def test_application_service_imports_only_domain_and_standard_lib(self) -> None:
        """应用层服务仅依赖领域层和标准库"""
        import ast
        import pathlib

        filepath = pathlib.Path("src/application/services/strategic_archive_service.py")
        assert filepath.exists(), f"{filepath} 不存在"
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "src.infrastructure" in alias.name or "src.interfaces" in alias.name:
                        assert False, f"应用层服务依赖基础设施/接口层: {alias.name}"

    def test_infrastructure_imports_no_interfaces(self) -> None:
        """基础设施层不依赖接口层"""
        import ast
        import pathlib

        filepath = pathlib.Path("src/infrastructure/storage/postgresql/repository/archive_repository.py")
        assert filepath.exists(), f"{filepath} 不存在"
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "src.interfaces" in alias.name:
                        assert False, f"基础设施层导入接口层: {alias.name}"
            if isinstance(node, ast.ImportFrom):
                if node.module and "src.interfaces" in node.module:
                    assert False, f"基础设施层导入接口层: {node.module}"

    def test_staleness_weight_service_imports_no_infrastructure(self) -> None:
        """StalenessWeightService 不依赖基础设施和接口层"""
        import ast
        import pathlib

        filepath = pathlib.Path("src/application/services/staleness_weight_service.py")
        assert filepath.exists(), f"{filepath} 不存在"
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "src.infrastructure" in alias.name or "src.interfaces" in alias.name:
                        assert False, f"StalenessWeightService 依赖基础设施/接口层: {alias.name}"

    def test_archive_handlers_imports_no_infrastructure(self) -> None:
        """archive_handlers 不依赖基础设施和接口层"""
        import ast
        import pathlib

        filepath = pathlib.Path("src/application/event_handlers/archive_handlers.py")
        assert filepath.exists(), f"{filepath} 不存在"
        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "src.infrastructure" in alias.name or "src.interfaces" in alias.name:
                        assert False, f"archive_handlers 依赖基础设施/接口层: {alias.name}"
