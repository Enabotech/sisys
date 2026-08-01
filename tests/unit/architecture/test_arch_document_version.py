"""文档版本快照架构约束验证测试

验证严格的六边形架构约束：
- 领域层零外部依赖
- 依赖方向正确
- 端口方法签名正确
"""

from __future__ import annotations

import ast
import pathlib


class TestDocumentVersionArchitecture:
    """验证文档版本快照模块的架构约束"""

    def test_domain_value_object_no_external_deps(self) -> None:
        """领域层值对象仅使用标准库"""
        filepath = pathlib.Path("src/domain/value_objects/document_version.py")
        assert filepath.exists(), f"{filepath} 不存在"
        source = filepath.read_text()
        tree = ast.parse(source)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full = f"{module}.{alias.name}" if module else alias.name
                    # __future__ 是标准库的特殊引用
                    if module == "__future__":
                        continue
                    imports.append(full)

        # 仅允许标准库和领域内部引用
        allowed_prefixes = ("dataclasses", "datetime", "typing", "uuid", "src.domain.")
        for imp in imports:
            is_allowed = any(imp.startswith(p) for p in allowed_prefixes)
            is_stdlib = imp in ("dataclasses", "uuid", "datetime", "typing")
            assert is_allowed or is_stdlib, f"禁止的外部依赖: {imp}"

    def test_domain_service_no_external_deps(self) -> None:
        """领域层差异计算服务仅使用标准库"""
        filepath = pathlib.Path("src/domain/services/document_version_diff_service.py")
        assert filepath.exists(), f"{filepath} 不存在"
        source = filepath.read_text()
        tree = ast.parse(source)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full = f"{module}.{alias.name}" if module else alias.name
                    if module == "__future__":
                        continue
                    imports.append(full)

        allowed_prefixes = ("difflib", "typing", "src.domain.")
        for imp in imports:
            is_allowed = any(imp.startswith(p) for p in allowed_prefixes)
            is_stdlib = imp in ("difflib", "typing")
            assert is_allowed or is_stdlib, f"禁止的外部依赖: {imp}"

    def test_port_method_signatures(self) -> None:
        """验证 DocumentRepositoryPort 新增方法签名"""
        filepath = pathlib.Path("src/domain/ports/document_repository.py")
        assert filepath.exists(), f"{filepath} 不存在"
        source = filepath.read_text()

        # 验证方法名存在
        assert "save_version_snapshot" in source
        assert "list_versions" in source
        assert "get_version" in source
        assert "save_with_version_check" in source

        # 验证 DocumentVersionSnapshot 引用
        assert "DocumentVersionSnapshot" in source

    def test_application_service_imports_correctly(self) -> None:
        """应用层服务使用 TYPE_CHECKING 模式"""
        filepath = pathlib.Path("src/application/services/document_version_service.py")
        assert filepath.exists(), f"{filepath} 不存在"
        source = filepath.read_text()

        assert "TYPE_CHECKING" in source
        assert "from __future__ import annotations" in source
