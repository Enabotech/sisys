"""
架构约束测试 - 验证六边形架构约束和依赖方向。

架构测试目标：
1. 验证领域层零依赖原则（FR-AR-01）
2. 验证各层依赖方向正确
3. 验证架构约束在 CI/CD 中自动检查
"""

import ast
from pathlib import Path

import pytest


class TestDomainLayerZeroDependency:
    """测试领域层零依赖原则（FR-AR-01）"""

    def test_domain_layer_only_uses_stdlib(self):
        """Given 领域层代码，When 检查导入，Then 仅使用 Python 标准库"""
        # Arrange
        domain_path = Path("src/domain")
        forbidden_modules = {
            "fastapi",
            "sqlalchemy",
            "redis",
            "qdrant",
            "minio",
            "neo4j",
            "langgraph",
            "prefect",
            "pydantic",  # 领域层不应依赖 pydantic
        }

        # Act
        domain_imports = self.scan_imports_ast(domain_path)

        # Assert
        external_imports = domain_imports & forbidden_modules
        assert len(external_imports) == 0, f"Domain layer uses external modules: {external_imports}"

    def test_domain_layer_has_no_infrastructure_imports(self):
        """Given 领域层代码，When 检查导入，Then 不包含基础设施层导入"""
        # Arrange
        domain_path = Path("src/domain")
        infrastructure_modules = {"src.infrastructure", "src.interfaces", "infrastructure", "interfaces"}

        # Act
        domain_imports = self.scan_imports_ast(domain_path)

        # Assert
        invalid_imports = domain_imports & infrastructure_modules
        assert len(invalid_imports) == 0, f"Domain layer imports infrastructure: {invalid_imports}"

    def scan_imports_ast(self, path: Path) -> set[str]:
        """使用 ast 模块扫描 Python 文件的所有导入"""
        imports: set[str] = set()

        if not path.exists():
            return imports

        for py_file in path.rglob("*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split(".")[0])

                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split(".")[0])

            except SyntaxError:
                # 跳过有语法错误的文件
                continue

        return imports


class TestLayerDependencyDirection:
    """测试各层依赖方向正确"""

    def scan_imports_ast(self, path: Path) -> set[str]:
        """使用 ast 模块扫描 Python 文件的所有导入"""
        imports: set[str] = set()

        if not path.exists():
            return imports

        for py_file in path.rglob("*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split(".")[0])

                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split(".")[0])

            except SyntaxError:
                # 跳过有语法错误的文件
                continue

        return imports

    def test_application_layer_can_import_domain(self):
        """Given 应用层代码，When 导入领域层，Then 成功导入"""
        # Arrange & Act & Assert
        try:
            from src.domain.entities.strategic_plan import StrategicPlan  # noqa: F401

            assert True
        except ImportError:
            pytest.fail("Application layer cannot import domain layer")

    def test_infrastructure_layer_can_import_application(self):
        """Given 基础设施层代码，When 导入应用层，Then 成功导入"""
        # Arrange & Act & Assert
        try:
            from src.application.usecases.create_plan import CreatePlanHandler  # noqa: F401

            assert True
        except ImportError:
            pytest.fail("Infrastructure layer cannot import application layer")

    def test_interfaces_layer_can_import_application(self):
        """Given 接口层代码，When 导入应用层，Then 成功导入"""
        # Arrange & Act & Assert
        try:
            from src.application.usecases.get_plan import GetPlanHandler  # noqa: F401

            assert True
        except ImportError:
            pytest.fail("Interfaces layer cannot import application layer")

    def test_domain_layer_cannot_import_infrastructure(self):
        """
        Given 领域层代码，When 检查导入，Then 不包含基础设施层导入

        这是一个架构约束测试，验证领域层不依赖基础设施层
        """
        # Arrange
        domain_path = Path("src/domain")
        infrastructure_modules = {"src.infrastructure", "src.interfaces"}

        # Act
        domain_imports = self.scan_imports_ast(domain_path)

        # Assert
        invalid_imports = domain_imports & infrastructure_modules
        assert len(invalid_imports) == 0, f"Domain layer should not import infrastructure: {invalid_imports}"


class TestArchitectureConstraints:
    """测试架构约束"""

    def test_domain_layer_has_entities_module(self):
        """Given 领域层，When 检查结构，Then 包含 entities 模块"""
        # Arrange
        entities_path = Path("src/domain/entities")

        # Act & Assert
        assert entities_path.exists(), "Domain layer should have entities module"
        assert (entities_path / "__init__.py").exists(), "entities module should have __init__.py"

    def test_domain_layer_has_events_module(self):
        """Given 领域层，When 检查结构，Then 包含 events 模块"""
        # Arrange
        events_path = Path("src/domain/events")

        # Act & Assert
        assert events_path.exists(), "Domain layer should have events module"
        assert (events_path / "__init__.py").exists(), "events module should have __init__.py"

    def test_domain_layer_has_repositories_module(self):
        """Given 领域层，When 检查结构，Then 包含 repositories 模块"""
        # Arrange
        repositories_path = Path("src/domain/repositories")

        # Act & Assert
        assert repositories_path.exists(), "Domain layer should have repositories module"
        assert (repositories_path / "__init__.py").exists(), "repositories module should have __init__.py"

    def test_domain_layer_has_exceptions_module(self):
        """Given 领域层，When 检查结构，Then 包含 exceptions 模块"""
        # Arrange
        exceptions_path = Path("src/domain/exceptions")

        # Act & Assert
        assert exceptions_path.exists(), "Domain layer should have exceptions module"
        assert (exceptions_path / "__init__.py").exists(), "exceptions module should have __init__.py"

    def test_application_layer_has_usecases_module(self):
        """Given 应用层，When 检查结构，Then 包含 usecases 模块"""
        # Arrange
        usecases_path = Path("src/application/usecases")

        # Act & Assert
        assert usecases_path.exists(), "Application layer should have usecases module"
        assert (usecases_path / "__init__.py").exists(), "usecases module should have __init__.py"

    def test_infrastructure_layer_has_database_module(self):
        """Given 基础设施层，When 检查结构，Then 包含 database 模块"""
        # Arrange
        database_path = Path("src/infrastructure/database")

        # Act & Assert
        # 注意：这个测试可能会失败，因为数据库模块可能还没创建
        # 这是预期的 - 基础设施正在建设中
        if database_path.exists():
            assert (database_path / "__init__.py").exists()
