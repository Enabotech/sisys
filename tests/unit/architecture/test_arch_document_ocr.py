"""Story 2-5: 架构约束验证测试

验证 OCR 相关代码的六边形架构约束：
- 领域层零外部依赖
- 依赖方向正确（domain ← application ← infrastructure）
- 端口注册完整性
"""

from __future__ import annotations

import importlib
import inspect


class TestDomainLayerNoExternalDependencies:
    """领域层零外部依赖验证"""

    def test_ocr_port_no_external_deps(self) -> None:
        """验证 OCRPort 端口无第三方导入"""

        # 验证 Protocol 仅使用 stdlib
        module = importlib.import_module("src.domain.ports.ocr")
        source = inspect.getsource(module)
        # 应仅导入 typing 和 domain 内部模块
        import_lines = [
            line for line in source.split("\n") if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        suspicious = [
            line for line in import_lines if not line.startswith("from __future__") and not line.startswith("from src.domain")
        ]
        # 允许 from typing import 和 from __future__ import
        suspicious = [line for line in suspicious if "import typing" not in line and "from typing" not in line]
        assert not suspicious, f"OCRPort 包含潜在外部依赖: {suspicious}"

    def test_ocr_result_no_external_deps(self) -> None:
        """验证 OCRResult 值对象无第三方导入"""
        import ast

        with open("src/domain/value_objects/ocr_result.py") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith("src.domain"):
                        continue
                    if module in ("__future__", "typing", "dataclasses"):
                        continue
                    assert False, f"ocr_result.py 包含外部导入: {module}"
                else:
                    for alias in node.names:
                        if alias.name not in ("__future__", "typing", "dataclasses"):
                            assert False, f"ocr_result.py 包含外部导入: {alias.name}"

    def test_scanned_page_detector_no_external_deps(self) -> None:
        """验证扫描页检测服务无第三方导入"""
        import ast

        with open("src/domain/services/scanned_page_detector.py") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith("src.domain"):
                        continue
                    if module in ("__future__", "typing", "os"):
                        continue
                    assert False, f"scanned_page_detector.py 包含外部导入: {module}"


class TestPortRegistration:
    """端口注册完整性验证"""

    def test_ocr_port_registered(self) -> None:
        """验证 ocr 端口在 registry.py 中注册"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("ocr")
        assert spec is not None, "ocr 端口未注册"

    def test_ocr_port_name(self) -> None:
        """验证 ocr 端口名称正确"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("ocr")
        assert spec is not None
        assert spec.name == "ocr"

    def test_ocr_port_version(self) -> None:
        """验证 ocr 端口版本"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("ocr")
        assert spec is not None
        assert spec.version == "v1.0.0"


class TestDependencyDirection:
    """依赖方向验证"""

    def test_domain_does_not_import_infrastructure(self) -> None:
        """验证领域层不导入基础设施层"""
        import ast

        domain_files = [
            "src/domain/ports/ocr.py",
            "src/domain/value_objects/ocr_result.py",
            "src/domain/services/scanned_page_detector.py",
            "src/domain/exceptions/ocr_exceptions.py",
        ]
        for filepath in domain_files:
            with open(filepath) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module.startswith("src.infrastructure"):
                            assert False, f"{filepath} 不能导入基础设施层: {module}"

    def test_application_does_not_import_infrastructure(self) -> None:
        """验证应用层不直接导入基础设施层"""
        import ast

        with open("src/application/services/document_parsing_service.py") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("src.infrastructure"):
                    # 允许在 TYPE_CHECKING 块中的导入
                    # 也允许 _apply_ocr 中的动态导入（os.path.getsize 是 stdlib）
                    assert False, f"application 不应直接导入 infrastructure: {module}"
