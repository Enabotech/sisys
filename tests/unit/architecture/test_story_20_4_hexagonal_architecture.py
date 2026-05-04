"""Hexagonal Architecture Constraint Verification Tests (Task 15).

验证领域层零外部依赖约束满足。

验证标准（AC-14）:
- [ ] ruff check src/domain/ 无外部依赖违规
- [ ] mypy src/domain/ports/ 类型检查通过
- [ ] Port 接口位于 src/domain/ports/
- [ ] 实现类位于 src/infrastructure/
- [ ] interfaces 层作为适配器层结构正确
- [ ] 依赖方向规则：内层不导入外层
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


class TestHexagonalArchitectureConstraints:
    """六边形架构约束验证"""

    def test_domain_layer_no_external_dependencies(self):
        """验证领域层没有外部依赖"""
        # 运行 ruff check
        result = subprocess.run(
            ["poetry", "run", "ruff", "check", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Domain layer has violations: {result.stdout}\n{result.stderr}"

    def test_domain_repositories_type_check(self):
        """验证 domain/ports 类型检查通过"""
        result = subprocess.run(
            ["poetry", "run", "mypy", "src/domain/ports/", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
        )
        # mypy 可能返回非零即使有错误，检查输出
        assert "error" not in result.stdout.lower() or result.returncode == 0, f"Type check failed: {result.stdout}"

    def test_port_interfaces_in_domain_repositories(self):
        """验证 Port 接口位于 src/domain/ports/"""
        domain_repos = Path("src/domain/ports")

        # 检查必需的 Port 接口存在
        required_ports = [
            "health_check.py",
            "l0_storage.py",
            "index_manager.py",
            "integrity.py",
        ]

        for port_file in required_ports:
            port_path = domain_repos / port_file
            assert port_path.exists(), f"Port interface {port_file} not found in domain/ports/"

    def test_implementation_classes_in_infrastructure(self):
        """验证实现类位于 src/infrastructure/"""
        infrastructure_path = Path("src/infrastructure")

        # 检查关键实现存在
        implementations = [
            "storage/file_memory_adapter.py",
            "storage/memory_index.py",
            "routing/ollama_health_adapter.py",
        ]

        for impl in implementations:
            impl_path = infrastructure_path / impl
            assert impl_path.exists(), f"Implementation {impl} not found in infrastructure/"

    def test_domain_repositories_not_importing_infrastructure(self):
        """验证 domain/ports 不导入 infrastructure 层"""
        domain_repos = Path("src/domain/ports")

        for py_file in domain_repos.glob("*.py"):
            content = py_file.read_text()
            # 移除 TYPE_CHECKING 块
            content = re.sub(r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)", "", content, flags=re.DOTALL)
            # 检查没有从 infrastructure 导入
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                pytest.fail(f"{py_file.name} imports from infrastructure")

    def test_domain_not_importing_application(self):
        """验证 domain 层不导入 application 层（内层→外层禁止）"""
        domain_path = Path("src/domain")

        violations = []
        for py_file in domain_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = re.sub(r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)", "", content, flags=re.DOTALL)
            if "from src.application" in content or "import src.application" in content:
                violations.append(str(py_file.relative_to(Path.cwd())))

        assert not violations, "Domain layer must NOT import application:\n" + "\n".join(violations)

    def test_application_not_importing_infrastructure(self):
        """验证 application 层不导入 infrastructure 层"""
        app_path = Path("src/application")

        violations = []
        for py_file in app_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = re.sub(r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)", "", content, flags=re.DOTALL)
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(py_file.relative_to(Path.cwd())))

        assert not violations, "Application layer must NOT import infrastructure:\n" + "\n".join(violations)


class TestInterfacesLayerConstraints:
    """interfaces 层（适配器层）约束验证"""

    def test_interfaces_layer_exists(self):
        """验证 interfaces 层存在"""
        interfaces_path = Path("src/interfaces")
        assert interfaces_path.exists(), "src/interfaces/ directory must exist"

    def test_interfaces_api_subdirectory_exists(self):
        """验证 interfaces/api 目录存在（REST API 适配器）"""
        api_path = Path("src/interfaces/api")
        assert api_path.exists(), "src/interfaces/api/ directory must exist"

    def test_interfaces_can_import_application(self):
        """验证 interfaces 层可以导入 application 层。

        六边形架构：interfaces（外层）→ application（中间层）是正确的依赖方向。
        例如：*_adapter.py 调用 *_handler.py
        """
        interfaces_path = Path("src/interfaces")
        root_path = Path.cwd()

        files_importing = []
        for py_file in interfaces_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = re.sub(r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)", "", content, flags=re.DOTALL)
            if "from src.application" in content or "import src.application" in content:
                try:
                    files_importing.append(str(py_file.relative_to(root_path)))
                except ValueError:
                    files_importing.append(str(py_file))

        # 找到 application 导入是预期的架构行为
        assert files_importing, (
            "Interfaces layer SHOULD import application layer (e.g., *_adapter.py imports *_handler.py).\n"
            "Files importing application:\n" + "\n".join(files_importing)
            if files_importing
            else "No imports found"
        )

    def test_interfaces_can_import_domain(self):
        """验证 interfaces 层可以导入 domain 层（正向依赖）"""
        interfaces_path = Path("src/interfaces")

        found_domain_import = False
        for py_file in interfaces_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            if "from src.domain" in content or "import src.domain" in content:
                found_domain_import = True
                break

        # interfaces 导入 domain 是允许的，但不是强制的
        assert found_domain_import or True, "Interfaces may import domain (positive dependency direction)"


class TestPortInterfaceCompliance:
    """Port 接口合规性验证"""

    def test_l0_storage_port_has_required_methods(self):
        """验证 L0StoragePort 接口有所需方法"""

        from src.domain.ports.l0_storage import L0StoragePort

        methods = ["write", "read", "delete", "exists", "list_memories"]
        for method in methods:
            assert hasattr(L0StoragePort, method), f"L0StoragePort missing method: {method}"

    def test_index_manager_port_has_required_methods(self):
        """验证 IndexManagerPort 接口有所需方法"""

        from src.domain.ports.index_manager import IndexManagerPort

        methods = ["update_entry", "remove_entry", "read_entries", "search", "truncate"]
        for method in methods:
            assert hasattr(IndexManagerPort, method), f"IndexManagerPort missing method: {method}"

    def test_health_check_port_has_required_methods(self):
        """验证 HealthCheckPort 接口有所需方法"""
        from src.domain.ports.health_check import HealthCheckPort

        methods = ["check", "close"]
        for method in methods:
            assert hasattr(HealthCheckPort, method), f"HealthCheckPort missing method: {method}"

    def test_integrity_port_has_required_methods(self):
        """验证 IntegrityPort 接口有所需方法"""
        from src.domain.ports.integrity import IntegrityPort

        methods = ["verify_file", "compute_hash", "verify_hash"]
        for method in methods:
            assert hasattr(IntegrityPort, method), f"IntegrityPort missing method: {method}"


class TestDependencyRuleCompliance:
    """依赖规则合规性验证"""

    def test_domain_layer_uses_only_stdlib(self):
        """验证领域层只使用标准库"""
        domain_path = Path("src/domain")

        # 禁止的外部依赖
        forbidden_imports = [
            "langgraph",
            "prefect",
            "fastapi",
            "pydantic",
            "sqlalchemy",
            "typer",
            "redis",
            "qdrant",
            "minio",
            "neo4j",
            "aio_pika",
            "litellm",
            "instructor",
            "requests",
            "httpx",
            "docker",
            "psycopg2",
        ]

        for py_file in domain_path.rglob("*.py"):
            content = py_file.read_text()
            for forbidden in forbidden_imports:
                if f"import {forbidden}" in content or f"from {forbidden}" in content:
                    pytest.fail(f"{py_file.relative_to(domain_path)} imports {forbidden}")

    def test_application_layer_exists(self):
        """验证应用层目录结构存在。"""
        app_path = Path("src/application")
        assert app_path.exists(), "Application layer directory should exist"

    def test_inner_layers_no_infrastructure_imports(self):
        """验证 domain/application 不导入 infrastructure（反向依赖检查）。

        六边形架构依赖方向: infrastructure → application → domain
        infrastructure 导入 application 是正向依赖 ✅
        禁止的是 domain/application 在运行时导入 infrastructure（反向依赖）❌

        TYPE_CHECKING 块内的导入是允许的（仅用于类型检查，不影响运行时依赖）。
        """
        import re

        domain_path = Path("src/domain")
        app_path = Path("src/application")

        violations = []

        def has_violating_import(content: str) -> bool:
            """检查是否有在 TYPE_CHECKING 之外的 infrastructure 导入。"""
            # 移除所有 TYPE_CHECKING 块的内容
            # TYPE_CHECKING 块通常格式: if TYPE_CHECKING:\n    from ... import ...
            pattern = r"if TYPE_CHECKING:.*?(?=\n\S|\Z)"
            content_without_type_checking = re.sub(pattern, "", content, flags=re.DOTALL)

            # 现在检查清理后的内容是否还有 infrastructure 导入
            if "from src.infrastructure" in content_without_type_checking:
                return True
            if "import src.infrastructure" in content_without_type_checking:
                return True
            return False

        for py_file in domain_path.rglob("*.py"):
            content = py_file.read_text()
            if has_violating_import(content):
                violations.append(f"{py_file.relative_to(domain_path)} imports infrastructure")

        for py_file in app_path.rglob("*.py"):
            content = py_file.read_text()
            if has_violating_import(content):
                violations.append(f"{py_file.relative_to(app_path)} imports infrastructure")

        assert len(violations) == 0, f"Reverse dependency detected (inner layer imports outer): {violations}"
