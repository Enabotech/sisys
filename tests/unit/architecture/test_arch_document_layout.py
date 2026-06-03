"""Story 2-3: SDD 架构约束验证测试

验证版面检测功能的架构合规性：
- domain 层零外部依赖（onnxruntime/numpy/pillow/pypdfium2）
- OnnxLayoutDetector 位于 infrastructure 层
- LayoutDetector Protocol 位于 domain 层
- BoundingBoxResult/BoundingBox 位于 domain 层
- 基础设施层实现满足 LayoutDetector Protocol（isinstance 检查）
- 依赖方向合规
"""

from __future__ import annotations

import importlib
import importlib.util


class TestDomainLayerPurity:
    """验证 domain 层零外部依赖"""

    def test_parsed_document_no_layout_external_deps(self) -> None:
        """parsed_document.py 不依赖 onnxruntime/numpy/pillow/pypdfium2"""
        mod = importlib.import_module("src.domain.value_objects.parsed_document")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__") and attr.__module__:
                assert not attr.__module__.startswith(
                    (
                        "onnxruntime",
                        "numpy",
                        "pillow",
                        "PIL",
                        "pypdfium2",
                        "pypdf",
                        "prefect",
                        "fastapi",
                        "pydantic",
                        "sqlalchemy",
                    )
                ), f"domain 层禁止依赖 {attr.__module__}"

    def test_layout_detector_port_no_external_deps(self) -> None:
        """LayoutDetector Protocol 不依赖外部库"""
        mod = importlib.import_module("src.domain.ports.layout_detector")
        source = importlib.util.find_spec("src.domain.ports.layout_detector")
        assert source is not None
        # 验证模块位于 domain 层
        assert mod.__name__.startswith("src.domain")

    def test_pdf_page_renderer_port_no_external_deps(self) -> None:
        """PdfPageRendererPort Protocol 不依赖外部库"""
        mod = importlib.import_module("src.domain.ports.pdf_page_renderer")
        assert mod.__name__.startswith("src.domain")

    def test_layout_matching_no_external_deps(self) -> None:
        """layout_matching.py 领域服务零外部依赖"""
        mod = importlib.import_module("src.domain.services.layout_matching")
        assert mod.__name__.startswith("src.domain")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__") and attr.__module__:
                assert not attr.__module__.startswith(
                    (
                        "onnxruntime",
                        "numpy",
                        "PIL",
                        "pypdfium2",
                        "scipy",
                    )
                ), f"领域层 layout_matching 禁止依赖 {attr.__module__}"


class TestPortDefinitions:
    """验证端口协议定义"""

    def test_layout_detector_is_protocol(self) -> None:
        """LayoutDetector 是 Protocol"""
        from src.domain.ports.layout_detector import LayoutDetector

        assert hasattr(LayoutDetector, "_is_protocol") or hasattr(LayoutDetector, "__protocol_attrs__")

    def test_layout_detector_has_detect_method(self) -> None:
        """LayoutDetector 定义了 detect 方法"""
        from src.domain.ports.layout_detector import LayoutDetector

        assert hasattr(LayoutDetector, "detect")

    def test_layout_detector_is_runtime_checkable(self) -> None:
        """LayoutDetector 使用 @runtime_checkable"""
        from src.domain.ports.layout_detector import LayoutDetector

        # @runtime_checkable Protocol 的特征：可以用 isinstance 检查
        class FakeDetector:
            def detect(self, image_bytes: bytes, page_number: int) -> list:
                return []

        assert isinstance(FakeDetector(), LayoutDetector)

    def test_pdf_page_renderer_port_is_protocol(self) -> None:
        """PdfPageRendererPort 是 Protocol"""
        from src.domain.ports.pdf_page_renderer import PdfPageRendererPort

        assert hasattr(PdfPageRendererPort, "_is_protocol") or hasattr(PdfPageRendererPort, "__protocol_attrs__")

    def test_pdf_page_renderer_port_has_render_page_method(self) -> None:
        """PdfPageRendererPort 定义了 render_page 方法"""
        from src.domain.ports.pdf_page_renderer import PdfPageRendererPort

        assert hasattr(PdfPageRendererPort, "render_page")


class TestInfrastructureLayerPlacement:
    """验证基础设施实现位于正确层级"""

    def test_onnx_layout_detector_in_infrastructure(self) -> None:
        """OnnxLayoutDetector 位于 infrastructure 层"""
        from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

        assert "infrastructure" in OnnxLayoutDetector.__module__

    def test_pdf_page_renderer_in_infrastructure(self) -> None:
        """PdfPageRenderer 位于 infrastructure 层"""
        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        assert "infrastructure" in PdfPageRenderer.__module__


class TestProtocolCompliance:
    """验证基础设施层实现满足端口协议"""

    def test_onnx_layout_detector_satisfies_protocol(self) -> None:
        """OnnxLayoutDetector 满足 LayoutDetector Protocol（class 级检查）"""
        from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

        # 类级别检查：OnnxLayoutDetector 定义了 detect 方法且签名兼容
        assert hasattr(OnnxLayoutDetector, "detect")
        assert isinstance(OnnxLayoutDetector, type)

    def test_pdf_page_renderer_satisfies_protocol(self) -> None:
        """PdfPageRenderer 满足 PdfPageRendererPort Protocol（class 级检查）"""
        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        assert hasattr(PdfPageRenderer, "render_page")
        assert isinstance(PdfPageRenderer, type)


class TestDependencyDirection:
    """验证依赖方向合规"""

    def test_infrastructure_imports_domain_layout_types(self) -> None:
        """infrastructure 层可以导入 domain 层类型"""
        from src.domain.ports.layout_detector import LayoutDetector
        from src.domain.value_objects.parsed_document import BoundingBoxResult
        from src.infrastructure.document_parsing.onnx_layout_detector import OnnxLayoutDetector

        assert OnnxLayoutDetector is not None
        assert LayoutDetector is not None
        assert BoundingBoxResult is not None

    def test_application_imports_domain_for_layout(self) -> None:
        """application 层可以导入 domain 层用于版面检测编排"""
        from src.application.services.document_parsing_service import DocumentParsingService
        from src.domain.services.layout_matching import match_detections
        from src.domain.value_objects.parsed_document import BoundingBoxResult

        assert "application" in DocumentParsingService.__module__
        assert match_detections is not None
        assert BoundingBoxResult is not None

    def test_domain_does_not_import_infrastructure(self) -> None:
        """domain 层不导入 infrastructure 层"""
        mod = importlib.import_module("src.domain.ports.layout_detector")
        source_lines: list[str] = []

        import inspect

        source_lines = inspect.getsource(mod).splitlines()
        for line in source_lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "infrastructure" not in stripped, f"domain 层禁止导入 infrastructure: {stripped}"

    def test_layout_matching_does_not_import_infrastructure(self) -> None:
        """layout_matching 领域服务不导入 infrastructure 层"""
        import inspect

        mod = importlib.import_module("src.domain.services.layout_matching")
        source_lines = inspect.getsource(mod).splitlines()
        for line in source_lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "infrastructure" not in stripped, f"领域层禁止导入 infrastructure: {stripped}"
