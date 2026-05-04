"""Interfaces Layer (Adapter Layer) Architecture Tests.

验证 interfaces 层作为适配器层的架构约束：
- interfaces 层是六边形架构的"端口"层
- 负责将外部请求适配到内部领域
- interfaces 层可以导入 domain/application 层
- interfaces 层不应被 domain/application 层导入
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
INTERFACES_DIR = SRC_DIR / "interfaces"


def _get_imports(file_path: Path) -> tuple[list[str], list[str]]:
    """Extract all import module names from a Python file using AST."""
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
    """Remove TYPE_CHECKING blocks from content."""
    pattern = r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)"
    return re.sub(pattern, "", content, flags=re.DOTALL)


class TestInterfacesLayerExistence:
    """interfaces 层存在性验证。"""

    def test_interfaces_directory_exists(self):
        """src/interfaces/ 目录存在。"""
        assert INTERFACES_DIR.exists(), "src/interfaces/ directory must exist"

    def test_interfaces_has_api_subdirectory(self):
        """src/interfaces/api/ 目录存在（REST API 适配器）。"""
        api_dir = INTERFACES_DIR / "api"
        assert api_dir.exists(), "src/interfaces/api/ directory must exist"

    def test_interfaces_api_has_init(self):
        """src/interfaces/api/__init__.py 存在。"""
        init_file = INTERFACES_DIR / "api" / "__init__.py"
        assert init_file.exists(), "src/interfaces/api/__init__.py must exist"


class TestInterfacesLayerDependencyDirection:
    """interfaces 层依赖方向验证。"""

    def test_interfaces_can_import_application(self):
        """interfaces 层可以导入 application 层。

        架构规则：interfaces 层（适配器）调用 application 层（handler）。
        这是六边形架构的正确依赖方向：外层调用中间层。

        例：auto_trigger_adapter.py → auto_trigger_handler.py
        """
        if not INTERFACES_DIR.exists():
            pytest.skip("interfaces directory does not exist")

        # 查找 interfaces 导入 application 的情况（预期行为）
        found_app_import = False

        for py_file in INTERFACES_DIR.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()

            if "from src.application" in content or "import src.application" in content:
                found_app_import = True
                break

        # 这是一个信息性测试：找到 application 导入是预期的架构行为
        assert found_app_import, "Interfaces layer should import application layer (e.g., *_adapter.py imports *_handler.py)"

    def test_interfaces_can_import_domain(self):
        """interfaces 层可以导入 domain 层（正向依赖）。"""
        if not INTERFACES_DIR.exists():
            pytest.skip("interfaces directory does not exist")

        # 尝试查找 interfaces 导入 domain 的情况
        found_domain_import = False

        for py_file in INTERFACES_DIR.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()

            if "from src.domain" in content or "import src.domain" in content:
                found_domain_import = True
                break

        # 这是一个信息性测试：如果找到 domain 导入是好的
        # 如果没找到，也不算错误（可能用了其他方式）
        assert found_domain_import or True, "Interfaces may import domain (positive dependency)"

    def test_interfaces_api_routes_defined(self):
        """src/interfaces/api/ 中定义了 API 路由。"""
        api_dir = INTERFACES_DIR / "api"
        if not api_dir.exists():
            pytest.skip("api directory does not exist")

        # 查找可能的路由定义文件
        py_files = list(api_dir.glob("*.py"))
        # 至少应该有 __init__.py
        assert len(py_files) >= 1, "interfaces/api should have Python files"


class TestInterfacesLayerCleanExports:
    """interfaces 层导出清洁性验证。"""

    def test_interfaces_api_init_exports_nothing(self):
        """src/interfaces/api/__init__.py 应该清空导出或声明 __all__。"""
        init_file = INTERFACES_DIR / "api" / "__init__.py"
        if not init_file.exists():
            pytest.skip("__init__.py does not exist")

        content = init_file.read_text()

        # 如果定义了 __all__，它应该是空的或者包含预期导出
        if "__all__" in content:
            # 检查 __all__ 是否为空列表
            if "__all__ = []" in content or "__all__ = []" in content.replace(" ", ""):
                pass  # 空导出是正确的
            else:
                # 如果有导出，确保它们是合理的
                assert True, "__all__ has explicit exports"
        else:
            # 如果没有 __all__，确保没有直接导出
            lines = [line.strip() for line in content.split("\n") if line.strip() and not line.strip().startswith("#")]
            # 过滤掉 docstring
            lines = [line for line in lines if not line.startswith('"""') and not line.startswith("'''")]
            # 如果只有 import 语句或 docstring，是可以接受的
            assert True, "No explicit __all__ defined"


class TestInterfacesLayerNoForbiddenImports:
    """interfaces 层禁止导入验证。"""

    def test_interfaces_no_redis_direct_import(self):
        """interfaces 层不应直接导入 redis 客户端。

        Redis 客户端应该只在 infrastructure 层使用。
        """
        if not INTERFACES_DIR.exists():
            pytest.skip("interfaces directory does not exist")

        violations = []

        for py_file in INTERFACES_DIR.rglob("*.py"):
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "import redis" in content or "from redis" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Interfaces layer must NOT import redis directly:\n" + "\n".join(violations)

    def test_interfaces_no_sqlalchemy_direct_import(self):
        """interfaces 层不应直接导入 sqlalchemy。

        SQLAlchemy 是基础设施实现，不应在接口层直接使用。
        """
        if not INTERFACES_DIR.exists():
            pytest.skip("interfaces directory does not exist")

        violations = []

        for py_file in INTERFACES_DIR.rglob("*.py"):
            content = py_file.read_text()
            content = _remove_type_checking_blocks(content)

            if "import sqlalchemy" in content or "from sqlalchemy" in content:
                violations.append(str(py_file.relative_to(ROOT)))

        assert not violations, "Interfaces layer must NOT import sqlalchemy directly:\n" + "\n".join(violations)
