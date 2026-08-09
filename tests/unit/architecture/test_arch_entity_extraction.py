"""实体抽取架构约束测试

验证六边形架构约束：
- 领域层零外部依赖
- 依赖方向正确（infrastructure → domain）
"""

from __future__ import annotations

import ast
import os


def _get_imports(filepath: str) -> list[str]:
    """解析 Python 文件中的所有 import 语句"""
    imports: list[str] = []
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # 处理相对导入（如 from .base import ... → node.module="base", node.level=1）
                    prefix = "." * node.level
                    imports.append(prefix + node.module)
                else:
                    # 仅有相对导入（如 from .. import ...）
                    imports.append("." * node.level)
    except SyntaxError:
        pass
    return imports


class TestDomainLayerZeroDependency:
    """领域层零外部依赖验证"""

    DOMAIN_PORTS_FILE = "src/domain/ports/entity_extraction.py"
    DOMAIN_EVENTS_FILE = "src/domain/events/entity_extraction_events.py"
    DOMAIN_EXCEPTIONS_FILE = "src/domain/exceptions/entity_extraction_exceptions.py"

    NON_STDLIB_PREFIXES = (
        "src.infrastructure",
        "src.application",
        "src.interfaces",
        "pydantic",
        "litellm",
        "ahocorasick",
        "neo4j",
        "redis",
        "sqlalchemy",
        "fastapi",
        "typer",
    )

    def _check_stdlib_only(self, filepath: str) -> list[str]:
        """检查文件是否仅导入标准库"""
        violations: list[str] = []
        if not os.path.exists(filepath):
            violations.append(f"文件不存在: {filepath}")
            return violations

        for imp in _get_imports(filepath):
            # 允许项目内领域层导入
            if imp.startswith("src.domain"):
                continue
            # 允许 Python 标准库
            if imp.startswith(("typing", "dataclasses", "enum", "abc", "re", "uuid", "datetime", "__future__")):
                continue
            # 允许相对导入（.base 等）
            if imp.startswith("."):
                continue
            # 检查是否导入非标准库
            if any(imp.startswith(prefix) for prefix in self.NON_STDLIB_PREFIXES):
                violations.append(f"{filepath}: 导入了非标准库 {imp}")
            # 检查第三方库（不在标准库中）
            if not imp.startswith("src") and not imp.startswith("_"):
                # 标准库白名单
                stdlib_modules = {
                    "os",
                    "sys",
                    "re",
                    "json",
                    "math",
                    "time",
                    "uuid",
                    "typing",
                    "abc",
                    "dataclasses",
                    "datetime",
                    "enum",
                    "inspect",
                    "functools",
                    "itertools",
                    "collections",
                    "copy",
                    "pathlib",
                    "importlib",
                    "ast",
                    "logging",
                    "threading",
                    "asyncio",
                    "contextlib",
                    "fractions",
                    "decimal",
                    "io",
                    "textwrap",
                    "string",
                    "types",
                    "__future__",
                }
                base = imp.split(".")[0]
                if base not in stdlib_modules:
                    violations.append(f"{filepath}: 可能导入了第三方库 {imp}")

        return violations

    def test_entity_extraction_port_stdlib_only(self) -> None:
        """验证 EntityExtractionPort 仅使用标准库"""
        violations = self._check_stdlib_only(self.DOMAIN_PORTS_FILE)
        assert not violations, "领域层零依赖违规:\n" + "\n".join(violations)

    def test_entity_extraction_events_stdlib_only(self) -> None:
        """验证 EntitiesExtracted 事件仅使用标准库"""
        violations = self._check_stdlib_only(self.DOMAIN_EVENTS_FILE)
        assert not violations, "领域层零依赖违规:\n" + "\n".join(violations)

    def test_entity_extraction_exceptions_stdlib_only(self) -> None:
        """验证 EntityExtractionError 异常仅使用标准库"""
        violations = self._check_stdlib_only(self.DOMAIN_EXCEPTIONS_FILE)
        assert not violations, "领域层零依赖违规:\n" + "\n".join(violations)


class TestLayerLocation:
    """各组件所在层验证"""

    def test_entity_extraction_port_in_domain(self) -> None:
        """验证 EntityExtractionPort 位于领域层"""
        path = "src/domain/ports/entity_extraction.py"
        assert os.path.exists(path), f"文件不存在: {path}"

    def test_rule_extractor_in_infrastructure(self) -> None:
        """验证 RuleBasedExtractor 位于基础设施层"""
        path = "src/infrastructure/external_services/entity_extraction/rule_extractor.py"
        assert os.path.exists(path), f"文件不存在: {path}"

    def test_llm_extractor_in_infrastructure(self) -> None:
        """验证 LLMEntityExtractor 位于基础设施层"""
        path = "src/infrastructure/external_services/entity_extraction/llm_extractor.py"
        assert os.path.exists(path), f"文件不存在: {path}"

    def test_conflict_arbitrator_in_infrastructure(self) -> None:
        """验证 ConflictArbitrator 位于基础设施层"""
        path = "src/infrastructure/external_services/entity_extraction/conflict_arbitrator.py"
        assert os.path.exists(path), f"文件不存在: {path}"

    def test_entity_extraction_service_in_application(self) -> None:
        """验证 EntityExtractionService 位于应用层"""
        path = "src/application/services/entity_extraction_service.py"
        assert os.path.exists(path), f"文件不存在: {path}"


class TestDependencyDirection:
    """依赖方向验证"""

    def test_infrastructure_imports_domain(self) -> None:
        """验证基础设施层导入领域层"""
        infra_files = [
            "src/infrastructure/external_services/entity_extraction/rule_extractor.py",
            "src/infrastructure/external_services/entity_extraction/llm_extractor.py",
            "src/infrastructure/external_services/entity_extraction/conflict_arbitrator.py",
        ]
        for filepath in infra_files:
            imports = _get_imports(filepath)
            domain_imports = [imp for imp in imports if imp.startswith("src.domain")]
            assert len(domain_imports) > 0, f"{filepath}: 应导入领域层端口"

    def test_application_imports_domain(self) -> None:
        """验证应用层导入领域层"""
        imports = _get_imports("src/application/services/entity_extraction_service.py")
        domain_imports = [imp for imp in imports if imp.startswith("src.domain")]
        assert len(domain_imports) > 0, "应用层应导入领域层端口"
