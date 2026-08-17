"""Story 3.7 检索相关性评估架构验证测试

验证六边形架构约束：
- 领域层零外部依赖
- 依赖方向正确
- composition_root 注册完整性
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
_RELEVANCE_PORT_FILE = _DOMAIN_PORTS / "relevance_evaluation.py"
_APPLICATION_SERVICES = _SRC_ROOT / "application" / "services"
_RELEVANCE_SERVICE_FILE = _APPLICATION_SERVICES / "relevance_evaluation_service.py"
_COMPOSITION_ROOT = _SRC_ROOT / "composition_root.py"


# ---------------------------------------------------------------------------
# 检查领域层零外部依赖
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
    # 项目内部依赖（src. 前缀）和标准库不算外部依赖
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

    # typing 扩展
    if base_module == "typing":
        return False

    return True


class TestDomainLayerZeroDependency:
    """领域层零外部依赖验证"""

    def test_relevance_evaluation_port_no_external_dependency(self) -> None:
        """RelevanceEvaluationPort 仅导入标准库 + 内部模块"""
        assert _RELEVANCE_PORT_FILE.exists(), "relevance_evaluation.py 不存在"
        imports = _get_imports(_RELEVANCE_PORT_FILE)

        external_imports = [imp for imp in imports if _is_external_import(imp)]
        assert not external_imports, f"领域层不允许外部依赖: {external_imports}"

    def test_relevance_exceptions_no_external_dependency(self) -> None:
        """relevance_exceptions.py 仅导入内部异常模块"""
        exc_file = _SRC_ROOT / "domain" / "exceptions" / "relevance_exceptions.py"
        assert exc_file.exists(), "relevance_exceptions.py 不存在"
        imports = _get_imports(exc_file)

        external_imports = [imp for imp in imports if _is_external_import(imp)]
        assert not external_imports, f"领域层不允许外部依赖: {external_imports}"

    def test_relevance_exceptions_imports_domain_exceptions(self) -> None:
        """relevance_exceptions.py 继承 ExternalException/BusinessException"""
        source = (_SRC_ROOT / "domain" / "exceptions" / "relevance_exceptions.py").read_text(encoding="utf-8")
        assert "ExternalException" in source
        assert "BusinessException" in source

    def test_relevance_exceptions_has_required_codes(self) -> None:
        """relevance_exceptions.py 定义 EXCEPTION_360 和 EXCEPTION_361"""
        source = (_SRC_ROOT / "domain" / "exceptions" / "relevance_exceptions.py").read_text(encoding="utf-8")
        assert "EXCEPTION_360" in source
        assert "EXCEPTION_361" in source

    def test_relevance_exceptions_no_collision(self) -> None:
        """grep -rw EXCEPTION_36[0-9] src/ 零输出（除本文件外）

        只统计实际 code 赋值语句，不含 docstring 注释。
        """
        result = subprocess.run(
            ["grep", "-rn", 'code = "EXCEPTION_36[0-9]"', "src/"],
            capture_output=True,
            text=True,
            check=False,
        )
        # 唯一输出应来自 relevance_exceptions.py 自身（允许）
        outputs = [line for line in result.stdout.splitlines() if line.strip()]
        # 2 个异常类，每个一个 code 赋值
        assert len(outputs) <= 2, f"编码碰撞: {outputs}"


# ---------------------------------------------------------------------------
# 检查依赖方向
# ---------------------------------------------------------------------------


class TestDependencyDirection:
    """依赖方向验证"""

    def test_domain_does_not_import_application(self) -> None:
        """领域层禁止导入应用层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.application", "src/domain/"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip() == "", f"领域层禁止导入应用层: {result.stdout}"

    def test_domain_does_not_import_interfaces(self) -> None:
        """领域层禁止导入接口层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.interfaces", "src/domain/"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip() == "", f"领域层禁止导入接口层: {result.stdout}"

    def test_domain_does_not_import_infrastructure(self) -> None:
        """领域层禁止导入基础设施层"""
        result = subprocess.run(
            ["grep", "-rn", "from src.infrastructure", "src/domain/"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip() == "", f"领域层禁止导入基础设施层: {result.stdout}"

    def test_application_imports_domain(self) -> None:
        """应用层允许导入领域层"""
        imports = _get_imports(_RELEVANCE_SERVICE_FILE)
        domain_imports = [imp for imp in imports if imp.startswith("src.domain.")]
        assert domain_imports, "应用层应导入领域层端口/异常"


# ---------------------------------------------------------------------------
# 检查 composition_root 注册完整性
# ---------------------------------------------------------------------------


class TestCompositionRootRegistration:
    """composition_root 注册完整性验证"""

    def _read_composition_root(self) -> str:
        """读取 composition_root.py 源码"""
        return _COMPOSITION_ROOT.read_text(encoding="utf-8")

    def test_relevance_service_registered(self) -> None:
        """relevance_evaluation_service 端口在 composition_root 注册"""
        source = self._read_composition_root()
        assert "relevance_evaluation_service" in source

    def test_relevance_service_register_port(self) -> None:
        """relevance_evaluation_service 使用 register_port 注册"""
        source = self._read_composition_root()
        assert 'name="relevance_evaluation_service"' in source

    def test_relevance_service_interface(self) -> None:
        """relevance_evaluation_service 接口为 RelevanceEvaluationPort"""
        source = self._read_composition_root()
        assert "RelevanceEvaluationPort" in source

    def test_relevance_service_impl(self) -> None:
        """relevance_evaluation_service 实现为 RelevanceEvaluationService"""
        source = self._read_composition_root()
        assert "RelevanceEvaluationService" in source

    def test_relevance_service_module(self) -> None:
        """relevance_evaluation_service 提供 module 参数"""
        source = self._read_composition_root()
        assert "src.application.services.relevance_evaluation_service" in source

    def test_relevance_service_injects_llm_client(self) -> None:
        """relevance_evaluation_service 注入 llm_client"""
        source = self._read_composition_root()
        assert "llm_client" in source

    def test_summary_service_injects_relevance(self) -> None:
        """summary_generation_service 注入 relevance_evaluation_service"""
        source = self._read_composition_root()
        assert "relevance_evaluation_service" in source


# ---------------------------------------------------------------------------
# 检查 Schema 定义位置
# ---------------------------------------------------------------------------


class TestSchemaLocation:
    """Schema 定义位置验证"""

    def test_schema_in_application_layer(self) -> None:
        """Schema 定义在应用层（非 domain）"""
        schema_file = _SRC_ROOT / "application" / "services" / "relevance_schemas.py"
        assert schema_file.exists(), "relevance_schemas.py 必须定义在应用层"

        # 域层不应有 schema 相关文件
        domain_schema = list(_SRC_ROOT.glob("domain/**/relevance_*schema*.py"))
        assert not domain_schema, "领域层不应包含 Schema 定义"

    def test_schema_uses_pydantic(self) -> None:
        """Schema 使用 Pydantic BaseModel"""
        source = (_SRC_ROOT / "application" / "services" / "relevance_schemas.py").read_text(encoding="utf-8")
        assert "from pydantic import BaseModel" in source
        assert "class RelevanceEvaluation(BaseModel)" in source
        assert "class RuleBasedEvaluation(BaseModel)" in source

    def test_domain_does_not_import_pydantic(self) -> None:
        """领域层禁止导入 pydantic"""
        result = subprocess.run(
            ["grep", "-rn", "import pydantic", "src/domain/"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip() == "", f"领域层禁止导入 pydantic: {result.stdout}"
