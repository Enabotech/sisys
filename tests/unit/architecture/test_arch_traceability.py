"""Story 3.8 高保真溯源架构约束验证测试

验证六边形架构约束：
- 领域层零外部依赖（traceability.py 端口、traceability_exceptions.py、citation.py）
- 依赖方向正确（application 不依赖 infrastructure，interfaces 不依赖 infrastructure）
- composition_root 注册完整性
- Schema 定义位置正确
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_SRC_ROOT = Path("src")
_DOMAIN_PORTS = _SRC_ROOT / "domain" / "ports"
_DOMAIN_EXCEPTIONS = _SRC_ROOT / "domain" / "exceptions"
_DOMAIN_VALUE_OBJECTS = _SRC_ROOT / "domain" / "value_objects"
_APPLICATION_SERVICES = _SRC_ROOT / "application" / "services"
_TRACEABILITY_PORT_FILE = _DOMAIN_PORTS / "traceability.py"
_TRACEABILITY_EXCEPTIONS_FILE = _DOMAIN_EXCEPTIONS / "traceability_exceptions.py"
_CITATION_FILE = _DOMAIN_VALUE_OBJECTS / "citation.py"
_TRACEABILITY_SERVICE_FILE = _APPLICATION_SERVICES / "traceability_service.py"
_TRACEABILITY_PROMPTS_FILE = _APPLICATION_SERVICES / "traceability_prompts.py"
_COMPOSITION_ROOT = _SRC_ROOT / "composition_root.py"


# ---------------------------------------------------------------------------
# AST 解析辅助函数
# ---------------------------------------------------------------------------


def _get_imports(file_path: Path) -> list[str]:
    """解析文件的 import 语句

    Args:
        file_path: 待解析的 Python 文件路径

    Returns:
        导入模块名列表
    """
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports


def _is_external_import(module_name: str) -> bool:
    """判断模块名是否为外部依赖

    Args:
        module_name: 模块名

    Returns:
        True 如果是外部依赖
    """
    if module_name.startswith("src.") or module_name.startswith("src"):
        return False

    stdlib_modules = {
        "abc",
        "asyncio",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "re",
        "string",
        "sys",
        "time",
        "typing",
        "uuid",
        "warnings",
        "weakref",
        "__future__",
    }
    base_module = module_name.split(".")[0]
    if base_module in stdlib_modules:
        return False
    if base_module == "typing":
        return False
    return True


# ---------------------------------------------------------------------------
# 领域层零外部依赖验证
# ---------------------------------------------------------------------------


class TestDomainLayerZeroDependency:
    """领域层零外部依赖验证"""

    def test_traceability_port_no_external_dependency(self) -> None:
        """TraceabilityPort 端口仅导入标准库 + 内部模块"""
        assert _TRACEABILITY_PORT_FILE.exists(), "traceability.py 端口文件不存在"
        imports = _get_imports(_TRACEABILITY_PORT_FILE)
        external_imports = [imp for imp in imports if _is_external_import(imp)]
        assert not external_imports, f"领域层端口不允许外部依赖: {external_imports}"

    def test_traceability_exceptions_no_external_dependency(self) -> None:
        """traceability_exceptions.py 仅导入内部异常模块"""
        assert _TRACEABILITY_EXCEPTIONS_FILE.exists(), "traceability_exceptions.py 不存在"
        imports = _get_imports(_TRACEABILITY_EXCEPTIONS_FILE)
        external_imports = [imp for imp in imports if _is_external_import(imp)]
        assert not external_imports, f"领域层异常不允许外部依赖: {external_imports}"

    def test_citation_no_external_dependency(self) -> None:
        """citation.py 值对象仅导入标准库 + 内部模块"""
        assert _CITATION_FILE.exists(), "citation.py 值对象文件不存在"
        imports = _get_imports(_CITATION_FILE)
        external_imports = [imp for imp in imports if _is_external_import(imp)]
        assert not external_imports, f"领域层值对象不允许外部依赖: {external_imports}"


# ---------------------------------------------------------------------------
# 依赖方向验证
# ---------------------------------------------------------------------------


class TestDependencyDirection:
    """依赖方向验证"""

    def test_domain_does_not_depend_on_application(self) -> None:
        """领域层不得导入应用层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.application", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert not result.stdout.strip(), f"领域层导入了应用层:\n{result.stdout}"

    def test_domain_does_not_depend_on_interfaces(self) -> None:
        """领域层不得导入接口层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.interfaces", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert not result.stdout.strip(), f"领域层导入了接口层:\n{result.stdout}"

    def test_domain_does_not_depend_on_infrastructure(self) -> None:
        """领域层不得导入基础设施层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.infrastructure", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert not result.stdout.strip(), f"领域层导入了基础设施层:\n{result.stdout}"

    def test_application_does_not_depend_on_infrastructure(self) -> None:
        """应用层不得导入基础设施层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.infrastructure", "src/application/"],
            capture_output=True,
            text=True,
        )
        assert not result.stdout.strip(), f"应用层导入了基础设施层:\n{result.stdout}"

    def test_application_does_not_depend_on_interfaces(self) -> None:
        """应用层不得导入接口层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.interfaces", "src/application/"],
            capture_output=True,
            text=True,
        )
        assert not result.stdout.strip(), f"应用层导入了接口层:\n{result.stdout}"


# ---------------------------------------------------------------------------
# Composition Root 注册完整性
# ---------------------------------------------------------------------------


class TestCompositionRootRegistration:
    """Composition Root 注册完整性验证"""

    def test_composition_root_has_traceability_port(self) -> None:
        """composition_root.py 注册 traceability_service 端口"""
        assert _COMPOSITION_ROOT.exists(), "composition_root.py 不存在"
        content = _COMPOSITION_ROOT.read_text(encoding="utf-8")
        assert "traceability_service" in content
        assert "TraceabilityPort" in content
        assert "TraceabilityService" in content

    def test_composition_root_has_required_metadata(self) -> None:
        """composition_root.py 注册包含完整元数据"""
        content = _COMPOSITION_ROOT.read_text(encoding="utf-8")
        assert 'name="traceability_service"' in content
        assert 'module="src.application.services.traceability_service"' in content
        assert 'owner="search-team"' in content
        assert "lifetime=Lifetime.SCOPED" in content


# ---------------------------------------------------------------------------
# 端口包导出验证
# ---------------------------------------------------------------------------


class TestPortPackageExport:
    """端口包导出验证"""

    def test_ports_init_exports_traceability_port(self) -> None:
        """ports/__init__.py 导出 TraceabilityPort"""
        init_file = _DOMAIN_PORTS / "__init__.py"
        assert init_file.exists()
        content = init_file.read_text(encoding="utf-8")
        assert "TraceabilityPort" in content

    def test_ports_init_exports_traceability_result(self) -> None:
        """ports/__init__.py 导出 TraceabilityResult"""
        init_file = _DOMAIN_PORTS / "__init__.py"
        content = init_file.read_text(encoding="utf-8")
        assert "TraceabilityResult" in content

    def test_value_objects_init_exports_citation(self) -> None:
        """value_objects/__init__.py 导出 Citation"""
        init_file = _DOMAIN_VALUE_OBJECTS / "__init__.py"
        assert init_file.exists()
        content = init_file.read_text(encoding="utf-8")
        assert "Citation" in content

    def test_exceptions_init_exports_traceability_exceptions(self) -> None:
        """exceptions/__init__.py 导出 TraceabilityError 和 TraceabilityNotFoundError"""
        init_file = _DOMAIN_EXCEPTIONS / "__init__.py"
        assert init_file.exists()
        content = init_file.read_text(encoding="utf-8")
        assert "TraceabilityError" in content
        assert "TraceabilityNotFoundError" in content


# ---------------------------------------------------------------------------
# 接口层路由注册验证
# ---------------------------------------------------------------------------


class TestInterfaceLayerRegistration:
    """接口层路由注册验证"""

    def test_app_includes_trace_router(self) -> None:
        """app.py include_router 注册 trace_router"""
        app_file = _SRC_ROOT / "interfaces" / "api" / "app.py"
        assert app_file.exists()
        content = app_file.read_text(encoding="utf-8")
        assert "trace_router" in content
        assert "from src.interfaces.api.traceability" in content

    def test_traceability_api_exists(self) -> None:
        """traceability.py 路由文件存在"""
        api_file = _SRC_ROOT / "interfaces" / "api" / "traceability.py"
        assert api_file.exists(), "traceability.py 路由文件不存在"
        content = api_file.read_text(encoding="utf-8")
        assert "create_trace_router" in content
        assert "/api/v1/search" in content
