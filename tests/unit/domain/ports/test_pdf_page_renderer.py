"""PdfPageRendererPort Protocol 行为验证测试

验证 PDF 页面渲染端口的运行时类型检查、同步方法签名和返回类型契约
"""

from __future__ import annotations

import asyncio

from src.domain.ports.pdf_page_renderer import PdfPageRendererPort


class TestPdfPageRendererPortRuntimeCheckable:
    """PdfPageRendererPort 结构化子类型检查"""

    def test_compatible_class_passes_isinstance(self) -> None:
        """实现 render_page 方法的类应通过 isinstance 检查"""

        class FakeRenderer:
            def render_page(self, file_path: str, page_number: int) -> bytes:
                return b"\x89PNG\r\n"

        assert isinstance(FakeRenderer(), PdfPageRendererPort)

    def test_incompatible_class_fails_isinstance(self) -> None:
        """不实现 render_page 方法的类不应通过 isinstance 检查"""

        class Incompatible:
            def other(self) -> None:
                pass

        assert not isinstance(Incompatible(), PdfPageRendererPort)

    def test_class_with_method_name_exists_passes(self) -> None:
        """runtime_checkable 仅检查方法名存在，不验证参数签名（Python 限制）"""

        class NoParams:
            def render_page(self) -> bytes:  # 缺少参数但方法名存在
                return b""

        # Python runtime_checkable 只检查方法名，不检查签名
        assert isinstance(NoParams(), PdfPageRendererPort)


class TestPdfPageRendererPortMethodSignature:
    """PdfPageRendererPort 方法签名验证"""

    def test_render_page_is_synchronous(self) -> None:
        """render_page 应为同步方法"""
        assert not asyncio.iscoroutinefunction(PdfPageRendererPort.render_page)

    def test_render_page_returns_bytes(self) -> None:
        """render_page 应返回 bytes"""

        class FakeRenderer:
            def render_page(self, file_path: str, page_number: int) -> bytes:
                return b"\x89PNG\r\n\x1a\nimage_data"

        renderer = FakeRenderer()
        result = renderer.render_page("/tmp/test.pdf", 1)
        assert isinstance(result, bytes)

    def test_render_page_receives_file_path_and_page_number(self) -> None:
        """render_page 应正确接收 file_path 和 page_number 参数"""
        received: dict[str, object] = {}

        class SpyRenderer:
            def render_page(self, file_path: str, page_number: int) -> bytes:
                received["file_path"] = file_path
                received["page_number"] = page_number
                return b"png_data"

        renderer = SpyRenderer()
        renderer.render_page("/docs/report.pdf", 3)
        assert received["file_path"] == "/docs/report.pdf"
        assert received["page_number"] == 3

    def test_render_page_accepts_different_page_numbers(self) -> None:
        """render_page 应接受不同页码"""
        results: list[bytes] = []

        class FakeRenderer:
            def render_page(self, file_path: str, page_number: int) -> bytes:
                return f"page_{page_number}".encode()

        renderer = FakeRenderer()
        for page in [1, 5, 10, 100]:
            result = renderer.render_page("/test.pdf", page)
            results.append(result)

        assert results[0] == b"page_1"
        assert results[3] == b"page_100"
