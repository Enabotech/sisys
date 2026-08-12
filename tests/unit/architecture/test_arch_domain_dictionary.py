"""领域词典架构约束测试

验证六边形架构依赖方向正确性。
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # tests/unit/architecture -> project root


def _get_imports(filepath: Path) -> list[str]:
    """获取文件中的导入模块名"""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


class TestDomainDictionaryArchitecture:
    """领域词典架构约束测试"""

    def test_domain_port_zero_external_dependency(self):
        """src/domain/ports/domain_dictionary.py 零外部依赖"""
        filepath = ROOT / "src/domain/ports/domain_dictionary.py"
        assert filepath.exists(), f"File not found: {filepath}"

        source = filepath.read_text()
        # 禁止第三方库导入
        forbidden = ["pydantic", "sqlalchemy", "redis", "ahocorasick"]
        for lib in forbidden:
            assert lib not in source, f"domain_dictionary.py 不应依赖 {lib}"

    def test_domain_event_zero_external_dependency(self):
        """src/domain/events/dictionary_events.py 零外部依赖"""
        filepath = ROOT / "src/domain/events/dictionary_events.py"
        assert filepath.exists(), f"File not found: {filepath}"

        source = filepath.read_text()
        forbidden = ["pydantic", "sqlalchemy", "redis"]
        for lib in forbidden:
            assert lib not in source, f"dictionary_events.py 不应依赖 {lib}"

    def test_domain_exception_zero_external_dependency(self):
        """src/domain/exceptions/dictionary_exceptions.py 零外部依赖"""
        filepath = ROOT / "src/domain/exceptions/dictionary_exceptions.py"
        assert filepath.exists(), f"File not found: {filepath}"

        source = filepath.read_text()
        forbidden = ["pydantic", "sqlalchemy", "redis"]
        for lib in forbidden:
            assert lib not in source, f"dictionary_exceptions.py 不应依赖 {lib}"

    def test_infrastructure_repo_imports_domain(self):
        """基础设施仓储可导入领域层"""
        filepath = ROOT / "src/infrastructure/storage/postgresql/repository/domain_dictionary_repository.py"
        assert filepath.exists(), f"File not found: {filepath}"

        imports = _get_imports(filepath)
        domain_imports = [i for i in imports if "src.domain" in i]
        assert len(domain_imports) > 0, "基础设施仓储应导入领域层"

    def test_application_service_imports_domain(self):
        """应用层服务可导入领域层"""
        filepath = ROOT / "src/application/services/domain_dictionary_service.py"
        assert filepath.exists(), f"File not found: {filepath}"

        imports = _get_imports(filepath)
        domain_imports = [i for i in imports if "src.domain" in i]
        assert len(domain_imports) > 0, "应用层服务应导入领域层"
