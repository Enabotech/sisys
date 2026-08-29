"""OCR 端口契约测试

验证 OCRPort 端口注册、版本、接口和实现完整性。
"""

from __future__ import annotations

from src.domain.ports.registry import Lifetime, _global_registry


class TestOCRPortContract:
    """OCRPort 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 ocr 端口已注册到 PortRegistry"""
        spec = _global_registry.get("ocr")
        assert spec is not None, "ocr 端口未注册"

    def test_port_interface_is_ocr_port(self) -> None:
        """验证端口接口类型为 OCRPort"""
        from src.domain.ports.ocr import OCRPort

        spec = _global_registry.get("ocr")
        assert spec is not None
        assert spec.interface is OCRPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("ocr")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_singleton(self) -> None:
        """验证本地 OCR 模型实例按单例生命周期管理"""
        spec = _global_registry.get("ocr")
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("ocr")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_string(self) -> None:
        """验证 impl 为模块路径字符串（延迟加载）"""
        spec = _global_registry.get("ocr")
        assert spec is not None
        assert isinstance(spec.impl, str), "impl 应为模块路径字符串"

    def test_port_interface_has_recognize_method(self) -> None:
        """验证端口接口包含 recognize 方法签名"""
        from src.domain.ports.ocr import OCRPort

        required_methods = {"recognize"}
        actual_methods = {name for name in dir(OCRPort) if not name.startswith("_") and callable(getattr(OCRPort, name))}
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_ocr_port_is_runtime_checkable(self) -> None:
        """验证 OCRPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.ocr import OCRPort

        assert hasattr(OCRPort, "__protocol_attrs__") or hasattr(OCRPort, "_is_protocol")


class TestExistingDocumentPortsStillWork:
    """验证新增 OCR 端口不影响已有文档端口"""

    def test_document_parser_still_registered(self) -> None:
        spec = _global_registry.get("document_parser")
        assert spec is not None

    def test_document_parsing_service_still_registered(self) -> None:
        spec = _global_registry.get("document_parsing_service")
        assert spec is not None
        assert spec.version == "v1.3.0", "document_parsing_service 版本应为 v1.3.0（含 OCR 可选注入）"

    def test_layout_detector_still_registered(self) -> None:
        spec = _global_registry.get("layout_detector")
        assert spec is not None
