"""战略档案六边形架构约束验证测试

验证 StrategicArchive 组件的依赖方向：
- 领域层零外部依赖
- 应用层仅依赖领域层
- 基础设施层可依赖领域层和应用层
- 接口层可依赖领域层和应用层
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def _get_all_imports(filepath: str) -> set[str]:
    """获取文件的所有 import 语句"""
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_parts = node.module.split(".")
                # 排除相对导入和 __future__
                if module_parts[0] == "src":
                    imports.add(module_parts[0] + "." + module_parts[1] if len(module_parts) > 1 else module_parts[0])
    return imports


def _get_files_in_dir(dir_path: str) -> list[str]:
    """获取目录下所有 Python 文件（递归扫描子目录）

    Args:
        dir_path: 目录路径

    Returns:
        该目录及其子目录下所有 .py 文件路径列表
    """
    if not os.path.isdir(dir_path):
        return []
    py_files = []
    for root, _dirs, files in os.walk(dir_path):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files


class TestDomainLayer:
    """领域层架构约束"""

    DOMAIN_DIR = str(SRC_DIR / "domain")

    def test_domain_has_no_external_dependencies(self) -> None:
        """领域层零外部依赖"""
        for filepath in _get_files_in_dir(self.DOMAIN_DIR):
            imports = _get_all_imports(filepath)
            # src/domain/ 允许导入 src.domain.*，禁止导入其他 src.* 层级
            domain_file_imports = {i for i in imports if i.startswith("src.") and not i.startswith("src.domain")}
            assert not domain_file_imports, f"{filepath} 引入了外部依赖: {domain_file_imports}"


class TestApplicationLayer:
    """应用层架构约束"""

    APP_DIR = str(SRC_DIR / "application")

    def test_application_does_not_import_infrastructure(self) -> None:
        """应用层不直接导入基础设施层"""
        for filepath in _get_files_in_dir(self.APP_DIR):
            imports = _get_all_imports(filepath)
            infra_imports = {i for i in imports if i.startswith("src.infrastructure")}
            assert not infra_imports, f"{filepath} 直接引入了基础设施层: {infra_imports}"

    def test_application_does_not_import_interfaces(self) -> None:
        """应用层不导入接口层"""
        for filepath in _get_files_in_dir(self.APP_DIR):
            imports = _get_all_imports(filepath)
            interface_imports = {i for i in imports if i.startswith("src.interfaces")}
            assert not interface_imports, f"{filepath} 直接引入了接口层: {interface_imports}"


class TestInterfaceLayer:
    """接口层架构约束"""

    API_DIR = str(SRC_DIR / "interfaces" / "api")

    def test_interface_does_not_import_infrastructure(self) -> None:
        """接口层不直接导入基础设施层"""
        api_files = [os.path.join(self.API_DIR, f) for f in os.listdir(self.API_DIR) if f.endswith(".py")]
        for filepath in api_files:
            imports = _get_all_imports(filepath)
            infra_imports = {i for i in imports if i.startswith("src.infrastructure")}
            # exception_handlers.py 和 app.py 可能导入基础设施，那是例外
            basename = os.path.basename(filepath)
            if basename in ("exception_handlers.py", "app.py", "__init__.py"):
                continue
            assert not infra_imports, f"{filepath} 直接引入了基础设施层: {infra_imports}"


class TestStrategicArchiveFiles:
    """StrategicArchive 相关文件的架构约束"""

    def test_entity_has_no_external_imports(self) -> None:
        """StrategicArchive 实体零外部依赖"""
        entity_file = str(SRC_DIR / "domain" / "entities" / "strategic_archive.py")
        imports = _get_all_imports(entity_file)
        src_imports = {i for i in imports if i.startswith("src.")}
        # 允许导入 src.domain.exceptions
        allowed = {"src.domain"}
        disallowed = {i for i in src_imports if not any(i.startswith(a) for a in allowed)}
        assert not disallowed, f"strategic_archive.py 引入了外部依赖: {disallowed}"

    def test_port_has_no_external_imports(self) -> None:
        """ArchiveRepositoryPort 零外部依赖"""
        port_file = str(SRC_DIR / "domain" / "ports" / "archive_repository.py")
        imports = _get_all_imports(port_file)
        src_imports = {i for i in imports if i.startswith("src.")}
        allowed = {"src.domain"}
        disallowed = {i for i in src_imports if not any(i.startswith(a) for a in allowed)}
        assert not disallowed, f"archive_repository.py 引入了外部依赖: {disallowed}"
