"""Story 2-4: 端口契约测试 — 表格语义提取端口

验证 table_extractor 和 pdf_table_extractor 端口注册、版本、接口和实现完整性。
"""

from __future__ import annotations

from src.domain.ports.registry import Lifetime, _global_registry


class TestTableExtractorPortContract:
    """table_extractor 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 table_extractor 端口已注册到 PortRegistry"""
        spec = _global_registry.get("table_extractor")
        assert spec is not None, "table_extractor 端口未注册"

    def test_port_interface_is_table_extractor_port(self) -> None:
        """验证端口接口类型为 TableExtractorPort"""
        from src.domain.ports.table_extractor import TableExtractorPort

        spec = _global_registry.get("table_extractor")
        assert spec is not None
        assert spec.interface is TableExtractorPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("table_extractor")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("table_extractor")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("table_extractor")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_callable(self) -> None:
        """验证 impl 为可调用工厂"""
        spec = _global_registry.get("table_extractor")
        assert spec is not None
        assert callable(spec.impl), "impl 应为可调用工厂函数"

    def test_port_interface_has_extract_method(self) -> None:
        """验证端口接口包含 extract 方法签名"""
        from src.domain.ports.table_extractor import TableExtractorPort

        required_methods = {"extract"}
        actual_methods = {
            name for name in dir(TableExtractorPort) if not name.startswith("_") and callable(getattr(TableExtractorPort, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_table_extractor_is_runtime_checkable(self) -> None:
        """验证 TableExtractorPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.table_extractor import TableExtractorPort

        assert hasattr(TableExtractorPort, "__protocol_attrs__") or hasattr(TableExtractorPort, "_is_protocol")


class TestPdfTableExtractorPortContract:
    """pdf_table_extractor 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 pdf_table_extractor 端口已注册到 PortRegistry"""
        spec = _global_registry.get("pdf_table_extractor")
        assert spec is not None, "pdf_table_extractor 端口未注册"

    def test_port_interface_is_table_extractor_port(self) -> None:
        """验证端口接口类型为 TableExtractorPort"""
        from src.domain.ports.table_extractor import TableExtractorPort

        spec = _global_registry.get("pdf_table_extractor")
        assert spec is not None
        assert spec.interface is TableExtractorPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("pdf_table_extractor")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("pdf_table_extractor")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("pdf_table_extractor")
        assert spec is not None
        assert spec.owner == "epic-2"


class TestExistingDocumentPortsStillWork:
    """验证新增端口不影响已有文档端口"""

    def test_document_parser_still_registered(self) -> None:
        spec = _global_registry.get("document_parser")
        assert spec is not None

    def test_document_parsing_service_still_registered(self) -> None:
        spec = _global_registry.get("document_parsing_service")
        assert spec is not None

    def test_layout_detector_still_registered(self) -> None:
        spec = _global_registry.get("layout_detector")
        assert spec is not None

    def test_document_repository_still_registered(self) -> None:
        spec = _global_registry.get("document_repository")
        assert spec is not None
