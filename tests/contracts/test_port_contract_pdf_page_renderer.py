"""PdfPageRendererPort 端口契约测试

验证 PdfPageRendererPort 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.pdf_page_renderer import PdfPageRendererPort


class TestPdfPageRendererPortContract:
    """测试 PdfPageRendererPort 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(PdfPageRendererPort, "_is_runtime_protocol")
        assert PdfPageRendererPort._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_render_page_method_exists(self) -> None:
        """验证 render_page 方法存在"""
        assert hasattr(PdfPageRendererPort, "render_page")
        method = getattr(PdfPageRendererPort, "render_page")
        assert callable(method)

    def test_render_page_method_signature(self) -> None:
        """验证 render_page(file_path, page_number) -> bytes"""
        method = getattr(PdfPageRendererPort, "render_page")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "file_path", "page_number"]
        assert sig.return_annotation == "bytes"

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockRenderer:
            def render_page(self, file_path: str, page_number: int) -> bytes:
                return b""

        renderer = MockRenderer()
        assert isinstance(renderer, PdfPageRendererPort)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadRenderer:
            pass

        assert not isinstance(BadRenderer(), PdfPageRendererPort)


__all__ = ["TestPdfPageRendererPortContract"]
