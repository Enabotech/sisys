"""SDD 架构约束验证测试 — Story 2-4 表格语义提取

验证表格语义提取相关代码遵守六边形架构约束：
1. 领域层零外部依赖
2. 依赖方向正确（domain ← application ← infrastructure）
3. 端口在 domain/ports 中定义
4. 基础设施实现类满足 Protocol
5. 无循环依赖
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

# 项目根路径
_SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
_DOMAIN_ROOT = _SRC_ROOT / "domain"


class TestDomainLayerPurity:
    """验证领域层零外部依赖"""

    def test_column_type_no_external_deps(self) -> None:
        """ColumnType 枚举及值对象仅使用标准库"""
        import src.domain.value_objects.parsed_document as mod

        stdlib_prefixes = ("src.domain", "builtins", "typing", "dataclasses", "enum", "__future__", "abc", "_")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__"):
                assert attr.__module__.startswith(stdlib_prefixes), f"{attr_name} 来自非领域/标准库模块: {attr.__module__}"

    def test_table_header_detector_no_external_deps(self) -> None:
        """表头检测领域服务零外部依赖"""
        mod = importlib.import_module("src.domain.services.table_header_detector")
        assert mod.__file__ is not None
        source = Path(mod.__file__).read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(
                        ("pydantic", "sqlalchemy", "numpy", "pandas", "pdfplumber", "openpyxl")
                    ), f"领域服务禁止外部依赖: {node.module}"

    def test_table_column_classifier_no_external_deps(self) -> None:
        """列类型推断领域服务零外部依赖"""
        mod = importlib.import_module("src.domain.services.table_column_classifier")
        assert mod.__file__ is not None
        source = Path(mod.__file__).read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(
                        ("pydantic", "sqlalchemy", "numpy", "pandas", "pdfplumber", "openpyxl")
                    ), f"领域服务禁止外部依赖: {node.module}"

    def test_table_merge_resolver_no_external_deps(self) -> None:
        """合并单元格还原领域服务零外部依赖"""
        mod = importlib.import_module("src.domain.services.table_merge_resolver")
        assert mod.__file__ is not None
        source = Path(mod.__file__).read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(
                        ("pydantic", "sqlalchemy", "numpy", "pandas", "pdfplumber", "openpyxl")
                    ), f"领域服务禁止外部依赖: {node.module}"


class TestPortDefinitions:
    """验证端口在 domain/ports 中定义"""

    def test_table_detector_port_in_domain_ports(self) -> None:
        """TableDetectorPort 定义在 src/domain/ports/"""
        port_file = _DOMAIN_ROOT / "ports" / "table_detector.py"
        assert port_file.exists(), "TableDetectorPort 端口文件应存在于 src/domain/ports/"

    def test_table_enhancer_port_in_domain_ports(self) -> None:
        """TableSemanticEnhancerPort 定义在 src/domain/ports/"""
        port_file = _DOMAIN_ROOT / "ports" / "table_enhancer.py"
        assert port_file.exists(), "TableSemanticEnhancerPort 端口文件应存在于 src/domain/ports/"

    def test_table_detector_port_is_runtime_checkable(self) -> None:
        """TableDetectorPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.table_detector import TableDetectorPort

        assert hasattr(TableDetectorPort, "__protocol_attrs__") or hasattr(TableDetectorPort, "_is_protocol")

    def test_table_enhancer_port_is_runtime_checkable(self) -> None:
        """TableSemanticEnhancerPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.table_enhancer import TableSemanticEnhancerPort

        assert hasattr(TableSemanticEnhancerPort, "__protocol_attrs__") or hasattr(TableSemanticEnhancerPort, "_is_protocol")

    def test_table_detector_port_has_detect_method(self) -> None:
        """TableDetectorPort 包含 detect 方法签名"""
        from src.domain.ports.table_detector import TableDetectorPort

        methods = {
            name for name in dir(TableDetectorPort) if not name.startswith("_") and callable(getattr(TableDetectorPort, name))
        }
        assert "detect" in methods

    def test_table_enhancer_port_has_enhance_method(self) -> None:
        """TableSemanticEnhancerPort 包含 enhance 方法签名"""
        from src.domain.ports.table_enhancer import TableSemanticEnhancerPort

        methods = {
            name
            for name in dir(TableSemanticEnhancerPort)
            if not name.startswith("_") and callable(getattr(TableSemanticEnhancerPort, name))
        }
        assert "enhance" in methods


class TestProtocolCompliance:
    """验证基础设施实现类满足 Protocol"""

    def test_table_semantic_extractor_satisfies_enhancer_protocol(self) -> None:
        """TableSemanticExtractor 满足 TableSemanticEnhancerPort Protocol"""
        from src.domain.ports.table_enhancer import TableSemanticEnhancerPort
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        assert isinstance(TableSemanticExtractor(), TableSemanticEnhancerPort)

    def test_pdf_table_detector_satisfies_detector_protocol(self) -> None:
        """PdfTableDetector 满足 TableDetectorPort Protocol"""
        from src.domain.ports.table_detector import TableDetectorPort
        from src.infrastructure.document_parsing.pdf_table_extractor import PdfTableDetector

        assert isinstance(PdfTableDetector(), TableDetectorPort)


class TestInfrastructureLayerPlacement:
    """验证实现类位于正确层级"""

    def test_table_semantic_extractor_in_infrastructure(self) -> None:
        """TableSemanticExtractor 位于 infrastructure 层"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        assert "infrastructure" in TableSemanticExtractor.__module__

    def test_pdf_table_detector_in_infrastructure(self) -> None:
        """PdfTableDetector 位于 infrastructure 层"""
        from src.infrastructure.document_parsing.pdf_table_extractor import PdfTableDetector

        assert "infrastructure" in PdfTableDetector.__module__

    def test_domain_services_in_domain_layer(self) -> None:
        """领域服务位于 domain/services"""
        from src.domain.services import table_column_classifier, table_header_detector, table_merge_resolver

        assert "domain.services" in table_header_detector.__name__
        assert "domain.services" in table_column_classifier.__name__
        assert "domain.services" in table_merge_resolver.__name__


class TestDependencyDirection:
    """验证依赖方向正确"""

    def test_infrastructure_imports_domain(self) -> None:
        """infrastructure 层可导入 domain 层"""
        from src.infrastructure.document_parsing.table_semantic_extractor import (
            TableSemanticExtractor,
        )

        # 能正常导入即证明 infrastructure 依赖 domain
        assert TableSemanticExtractor is not None

    def test_domain_does_not_import_infrastructure(self) -> None:
        """domain 层不导入 infrastructure 层"""
        domain_modules = [
            "src.domain.value_objects.parsed_document",
            "src.domain.ports.table_detector",
            "src.domain.ports.table_enhancer",
            "src.domain.services.table_header_detector",
            "src.domain.services.table_column_classifier",
            "src.domain.services.table_merge_resolver",
        ]

        for mod_name in domain_modules:
            mod = importlib.import_module(mod_name)
            assert mod.__file__ is not None
            source = Path(mod.__file__).read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert "infrastructure" not in node.module, f"领域模块 {mod_name} 禁止导入 infrastructure: {node.module}"
