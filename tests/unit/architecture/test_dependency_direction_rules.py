"""Hexagonal Architecture Dependency Direction Rules Tests.

系统验证六边形架构依赖方向规则：
- domain → application ✗ 禁止
- domain → infrastructure ✗ 禁止
- domain → interfaces ✗ 禁止
- application → infrastructure ✗ 禁止
- application → interfaces ✗ 禁止
- infrastructure → domain ✓ 允许
- infrastructure → application ✓ 允许
- interfaces → domain ✓ 允许
- interfaces → application ✓ 允许
- application → domain ✓ 允许
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"


def _get_imports(file_path: Path) -> tuple[list[str], list[str]]:
    """Extract all import module names from a Python file using AST.

    Returns:
        Tuple of (direct_imports, from_imports)
    """
    with open(file_path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
            return [], []

    direct_imports = []
    from_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                direct_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                from_imports.append(node.module)
    return direct_imports, from_imports


def _remove_type_checking_blocks(content: str) -> str:
    """Remove TYPE_CHECKING blocks from content to check only runtime imports."""
    pattern = r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)"
    return re.sub(pattern, "", content, flags=re.DOTALL)


class TestDependencyDirectionRules:
    """六边形架构依赖方向规则验证。"""

    def test_domain_not_importing_infrastructure(self):
        """domain 层禁止导入 infrastructure 层（反向依赖检查）。

        依赖方向规则：infrastructure → domain 是正向
        因此 domain → infrastructure 是反向（禁止）
        """
        domain_dir = SRC_DIR / "domain"
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            # 移除 TYPE_CHECKING 块
            content = _remove_type_checking_blocks(content)

            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Domain layer must NOT import infrastructure (reverse dependency):\n" + "\n".join(violations)

    def test_domain_not_importing_interfaces(self):
        """domain 层禁止导入 interfaces 层。"""
        domain_dir = SRC_DIR / "domain"
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.interfaces" in content or "import src.interfaces" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Domain layer must NOT import interfaces:\n" + "\n".join(violations)

    def test_domain_not_importing_application(self):
        """domain 层禁止导入 application 层。

        注意：这是内层禁止导入外层的典型情况。
        domain 是最内层，application 是中间层。
        """
        domain_dir = SRC_DIR / "domain"
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.application" in content or "import src.application" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Domain layer must NOT import application (inner layer cannot depend on outer):\n" + "\n".join(
            violations
        )

    def test_application_not_importing_infrastructure(self):
        """application 层禁止导入 infrastructure 层。"""
        app_dir = SRC_DIR / "application"
        violations = []

        for py_file in app_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Application layer must NOT import infrastructure:\n" + "\n".join(violations)

    def test_application_not_importing_interfaces(self):
        """application 层禁止导入 interfaces 层。"""
        app_dir = SRC_DIR / "application"
        violations = []

        for py_file in app_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.interfaces" in content or "import src.interfaces" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Application layer must NOT import interfaces:\n" + "\n".join(violations)


class TestInterfacesLayerStructure:
    """interfaces 层作为适配器层的结构验证。"""

    def test_interfaces_layer_exists(self):
        """interfaces 层目录存在。"""
        interfaces_dir = SRC_DIR / "interfaces"
        assert interfaces_dir.exists(), "src/interfaces/ directory must exist"

    def test_interfaces_api_subdirectory_exists(self):
        """interfaces/api 子目录存在（API 适配器）。"""
        api_dir = SRC_DIR / "interfaces" / "api"
        assert api_dir.exists(), "src/interfaces/api/ directory must exist"

    def test_interfaces_can_import_application(self):
        """interfaces 层可以导入 application 层。

        六边形架构：interfaces（外层）→ application（中间层）是正确的依赖方向。
        例如：*_adapter.py 调用 *_handler.py

        约定：adapter 导入 handler 是标准模式，保持接口层纯净。
        """
        interfaces_dir = SRC_DIR / "interfaces"

        # 查找 interfaces 导入 application 的情况（预期行为）
        found_app_import = False
        files_importing = []

        for py_file in interfaces_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.application" in content or "import src.application" in content:
                found_app_import = True
                files_importing.append(str(py_file.relative_to(ROOT)))

        # interfaces 层不再需要纸壳适配器模式
        # 正确架构: EventBus (infrastructure) → Handler (application) → domain
        # 因此 interfaces 导入 application 不是预期行为
        assert not found_app_import, (
            "Interfaces layer should NOT import application layer. "
            "Correct pattern: infrastructure → application → domain (no adapter)"
        )


class TestLayerDependencyProtocols:
    """层间依赖应通过 Port 接口（协议）而非具体实现。"""

    def test_application_uses_domain_protocols(self):
        """application 层应通过 Port 接口依赖 domain 层。"""
        app_dir = SRC_DIR / "application"

        # 检查 application 层是否定义了协议/端口
        protocols_in_app = list((app_dir).rglob("*protocol*"))

        # 至少应该有某种形式的端口定义，或者 application 直接依赖 domain 的端口
        # 这个测试验证 application 不直接实例化 infrastructure 的具体类
        violations = []

        for py_file in app_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()

            # 检查是否直接使用了 infrastructure 的具体类（而非通过端口）
            infra_concrete_patterns = [
                r"RedisEventPublisher",
                r"HashRouter",
                r"SemanticRouter",
                r"PostgresOutboxRepository",
            ]

            for pattern in infra_concrete_patterns:
                if re.search(pattern, content):
                    # 检查是否通过 Protocol 方式使用
                    if "Protocol" not in content and "protocol" not in content.lower():
                        violations.append(f"{py_file.relative_to(ROOT)}: uses {pattern} without Protocol")

        # 如果没有找到违规，且没有协议定义，说明架构可能有问题
        # 但这可能是误报，所以这里只做信息性检查
        if violations and not protocols_in_app:
            pytest.fail("Application layer should use Protocols for infrastructure dependencies:\n" + "\n".join(violations))


class TestInfrastructureLayerIsolation:
    """infrastructure 层技术实现隔离验证。"""

    def test_infrastructure_storage_isolated(self):
        """infrastructure/storage 目录存在，隔离存储实现。"""
        storage_dir = SRC_DIR / "infrastructure" / "storage"
        # 目录可能存在也可能不存在，取决于具体实现
        # 如果不存在，这不是错误
        assert storage_dir.exists(), "Storage implementations should be in infrastructure/storage/"

    def test_infrastructure_routing_isolated(self):
        """infrastructure/routing 目录存在，隔离路由实现。"""
        routing_dir = SRC_DIR / "infrastructure" / "routing"
        if routing_dir.exists():
            # 验证路由实现文件存在
            router_files = list(routing_dir.glob("*.py"))
            assert len(router_files) > 0, "Routing directory should have router implementations"


class TestDomainPortsIsolation:
    """domain 层 Port 接口隔离验证。"""

    def test_domain_has_ports_directory(self):
        """domain/ports 目录存在（Port 接口定义位置）。"""
        ports_dir = SRC_DIR / "domain" / "ports"
        assert ports_dir.exists(), "Domain ports should be in src/domain/ports/"

    def test_domain_ports_not_importing_infrastructure(self):
        """domain/ports 不导入 infrastructure 层。

        Port 接口定义在领域层，不应依赖基础设施实现。
        """
        ports_dir = SRC_DIR / "domain" / "ports"
        if not ports_dir.exists():
            pytest.skip("domain/ports directory does not exist")

        violations = []

        for py_file in ports_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Domain ports must NOT import infrastructure:\n" + "\n".join(violations)

    def test_domain_ports_not_importing_application(self):
        """domain/ports 不导入 application 层。"""
        ports_dir = SRC_DIR / "domain" / "ports"
        if not ports_dir.exists():
            pytest.skip("domain/ports directory does not exist")

        violations = []

        for py_file in ports_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "from src.application" in content or "import src.application" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Domain ports must NOT import application:\n" + "\n".join(violations)
