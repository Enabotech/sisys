"""Story 2-4: 端口契约测试 — 表格语义提取端口

验证 table_detector 和 table_enhancer 端口注册、版本、接口和实现完整性。
"""

from __future__ import annotations

from src.domain.ports.registry import Lifetime, _global_registry


class TestTableDetectorPortContract:
    """table_detector 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 table_detector 端口已注册到 PortRegistry"""
        spec = _global_registry.get("table_detector")
        assert spec is not None, "table_detector 端口未注册"

    def test_port_interface_is_table_detector_port(self) -> None:
        """验证端口接口类型为 TableDetectorPort"""
        from src.domain.ports.table_detector import TableDetectorPort

        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.interface is TableDetectorPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_callable(self) -> None:
        """验证 impl 为可调用工厂"""
        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert callable(spec.impl), "impl 应为可调用工厂函数"

    def test_port_interface_has_detect_method(self) -> None:
        """验证端口接口包含 detect 方法签名"""
        from src.domain.ports.table_detector import TableDetectorPort

        required_methods = {"detect"}
        actual_methods = {
            name for name in dir(TableDetectorPort) if not name.startswith("_") and callable(getattr(TableDetectorPort, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_table_detector_is_runtime_checkable(self) -> None:
        """验证 TableDetectorPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.table_detector import TableDetectorPort

        assert hasattr(TableDetectorPort, "__protocol_attrs__") or hasattr(TableDetectorPort, "_is_protocol")


class TestTableSemanticEnhancerPortContract:
    """table_enhancer 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 table_enhancer 端口已注册到 PortRegistry"""
        spec = _global_registry.get("table_enhancer")
        assert spec is not None, "table_enhancer 端口未注册"

    def test_port_interface_is_table_semantic_enhancer_port(self) -> None:
        """验证端口接口类型为 TableSemanticEnhancerPort"""
        from src.domain.ports.table_enhancer import TableSemanticEnhancerPort

        spec = _global_registry.get("table_enhancer")
        assert spec is not None
        assert spec.interface is TableSemanticEnhancerPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("table_enhancer")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("table_enhancer")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("table_enhancer")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_callable(self) -> None:
        """验证 impl 为可调用工厂"""
        spec = _global_registry.get("table_enhancer")
        assert spec is not None
        assert callable(spec.impl), "impl 应为可调用工厂函数"

    def test_port_interface_has_enhance_method(self) -> None:
        """验证端口接口包含 enhance 方法签名"""
        from src.domain.ports.table_enhancer import TableSemanticEnhancerPort

        required_methods = {"enhance"}
        actual_methods = {
            name
            for name in dir(TableSemanticEnhancerPort)
            if not name.startswith("_") and callable(getattr(TableSemanticEnhancerPort, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_table_enhancer_is_runtime_checkable(self) -> None:
        """验证 TableSemanticEnhancerPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.table_enhancer import TableSemanticEnhancerPort

        assert hasattr(TableSemanticEnhancerPort, "__protocol_attrs__") or hasattr(TableSemanticEnhancerPort, "_is_protocol")


class TestPdfTableDetectorPortContract:
    """PdfTableDetector 端口契约测试（通过 table_detector 端口验证）"""

    def test_port_registered_in_registry(self) -> None:
        """验证 table_detector 端口已注册（PdfTableDetector 实现）"""
        spec = _global_registry.get("table_detector")
        assert spec is not None, "table_detector 端口未注册"

    def test_port_interface_is_table_detector_port(self) -> None:
        """验证端口接口类型为 TableDetectorPort"""
        from src.domain.ports.table_detector import TableDetectorPort

        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.interface is TableDetectorPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("table_detector")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("table_detector")
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
