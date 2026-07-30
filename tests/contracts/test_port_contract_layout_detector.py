"""Story 2-3: 端口契约测试 — 版面检测端口与 PDF 页面渲染端口

验证 layout_detector 和 pdf_page_renderer 端口注册、版本、接口和实现完整性。
"""

from __future__ import annotations

from src.domain.ports.registry import Lifetime, _global_registry


class TestLayoutDetectorPortContract:
    """LayoutDetector 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 layout_detector 端口已注册到 PortRegistry"""
        spec = _global_registry.get("layout_detector")
        assert spec is not None, "layout_detector 端口未注册"

    def test_port_interface_is_layout_detector(self) -> None:
        """验证端口接口类型为 LayoutDetector"""
        from src.domain.ports.layout_detector import LayoutDetector

        spec = _global_registry.get("layout_detector")
        assert spec is not None
        assert spec.interface is LayoutDetector

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("layout_detector")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_singleton(self) -> None:
        """验证端口生命周期为 SINGLETON（ONNX 模型会话可复用）"""
        spec = _global_registry.get("layout_detector")
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("layout_detector")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_callable(self) -> None:
        """验证 impl 为可调用工厂"""
        spec = _global_registry.get("layout_detector")
        assert spec is not None
        assert callable(spec.impl), "impl 应为可调用工厂函数"

    def test_port_interface_has_detect_method(self) -> None:
        """验证端口接口包含 detect 方法签名"""
        from src.domain.ports.layout_detector import LayoutDetector

        required_methods = {"detect"}
        actual_methods = {
            name for name in dir(LayoutDetector) if not name.startswith("_") and callable(getattr(LayoutDetector, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_layout_detector_is_runtime_checkable(self) -> None:
        """验证 LayoutDetector 是 @runtime_checkable Protocol"""
        from src.domain.ports.layout_detector import LayoutDetector

        assert hasattr(LayoutDetector, "__protocol_attrs__") or hasattr(LayoutDetector, "_is_protocol")


class TestPdfPageRendererPortContract:
    """PdfPageRendererPort 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 pdf_page_renderer 端口已注册到 PortRegistry"""
        spec = _global_registry.get("pdf_page_renderer")
        assert spec is not None, "pdf_page_renderer 端口未注册"

    def test_port_interface_is_pdf_page_renderer_port(self) -> None:
        """验证端口接口类型为 PdfPageRendererPort"""
        from src.domain.ports.pdf_page_renderer import PdfPageRendererPort

        spec = _global_registry.get("pdf_page_renderer")
        assert spec is not None
        assert spec.interface is PdfPageRendererPort

    def test_port_version_is_v1_0(self) -> None:
        """验证端口版本为 v1.0.0"""
        spec = _global_registry.get("pdf_page_renderer")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("pdf_page_renderer")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("pdf_page_renderer")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_callable(self) -> None:
        """验证 impl 为可调用工厂"""
        spec = _global_registry.get("pdf_page_renderer")
        assert spec is not None
        assert callable(spec.impl), "impl 应为可调用工厂函数"

    def test_port_interface_has_render_page_method(self) -> None:
        """验证端口接口包含 render_page 方法签名"""
        from src.domain.ports.pdf_page_renderer import PdfPageRendererPort

        required_methods = {"render_page"}
        actual_methods = {
            name
            for name in dir(PdfPageRendererPort)
            if not name.startswith("_") and callable(getattr(PdfPageRendererPort, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_pdf_page_renderer_is_runtime_checkable(self) -> None:
        """验证 PdfPageRendererPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.pdf_page_renderer import PdfPageRendererPort

        assert hasattr(PdfPageRendererPort, "__protocol_attrs__") or hasattr(PdfPageRendererPort, "_is_protocol")


class TestExistingDocumentPortsStillWork:
    """验证新增端口不影响已有文档端口"""

    def test_document_parser_still_registered(self) -> None:
        spec = _global_registry.get("document_parser")
        assert spec is not None

    def test_document_parsing_service_still_registered(self) -> None:
        spec = _global_registry.get("document_parsing_service")
        assert spec is not None
        assert spec.version == "v1.3.0", "document_parsing_service 版本应为 v1.3.0（含 OCR 可选注入）"

    def test_document_repository_still_registered(self) -> None:
        spec = _global_registry.get("document_repository")
        assert spec is not None
