"""Story 2-3: PdfPageRenderer 单元测试

使用 mock pypdfium2 验证 PDF 页面渲染逻辑，不依赖真实 PDF 文件或 pypdfium2 安装。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestPdfPageRendererInit:
    """PdfPageRenderer 初始化测试"""

    def test_init_with_default_dpi(self) -> None:
        """验证默认 DPI=150"""
        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        with patch.dict("sys.modules", {"pypdfium2": MagicMock()}):
            renderer = PdfPageRenderer()
            assert renderer._dpi == 150

    def test_init_with_custom_dpi(self) -> None:
        """验证自定义 DPI"""
        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        with patch.dict("sys.modules", {"pypdfium2": MagicMock()}):
            renderer = PdfPageRenderer(dpi=300)
            assert renderer._dpi == 300

    def test_init_pypdfium2_not_installed(self) -> None:
        """验证 pypdfium2 缺失时抛出 ImportError"""
        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        with patch.dict("sys.modules", {"pypdfium2": None}):
            with pytest.raises(ImportError, match="pypdfium2"):
                PdfPageRenderer()


class TestPdfPageRendererRenderPage:
    """PdfPageRenderer.render_page() 渲染测试"""

    def _create_renderer_with_mock(self) -> tuple[Any, dict[str, MagicMock]]:
        """创建渲染器并返回 mock 对象字典（绕过 __init__）"""
        from src.infrastructure.document_parsing.pdf_page_renderer import PdfPageRenderer

        renderer = PdfPageRenderer.__new__(PdfPageRenderer)
        renderer._dpi = 150
        # _pypdfium2 在 __init__ 中设置，mock 构建需手动注入
        # render_page 使用 self._pypdfium2.PdfDocument() 调用
        renderer._pypdfium2 = MagicMock()  # 由各测试通过 patch.dict 注入 mock
        return renderer, {}

    def test_render_page_returns_png_bytes(self) -> None:
        """验证 render_page 返回 PNG 图像字节"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_bitmap = MagicMock()
        mock_pil_image = MagicMock()

        mock_pdf.__len__ = MagicMock(return_value=3)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)
        mock_page.render.return_value = mock_bitmap
        mock_bitmap.to_pil.return_value = mock_pil_image

        # 模拟 PIL Image.save 写入字节
        def fake_save(buf: Any, format: str = "PNG") -> None:
            buf.write(b"\x89PNG\r\n\x1a\nfake_png_data")

        mock_pil_image.save = fake_save

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        # 直接注入 mock pypdfium2（__init__ 中存储为 self._pypdfium2）
        renderer._pypdfium2 = mock_pypdfium2

        with patch("src.infrastructure.document_parsing.pdf_page_renderer.Image", create=True):
            result = renderer.render_page("/path/to/doc.pdf", page_number=1)

        assert isinstance(result, bytes)
        assert result.startswith(b"\x89PNG")

    def test_render_page_file_not_found(self) -> None:
        """验证 PDF 文件不存在时抛出 FileNotFoundError"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.side_effect = Exception("无法打开文件")

        renderer._pypdfium2 = mock_pypdfium2

        with pytest.raises(FileNotFoundError, match="无法打开 PDF 文件"):
            renderer.render_page("/nonexistent/doc.pdf", page_number=1)

    def test_render_page_number_out_of_range(self) -> None:
        """验证页码超出范围时抛出 ValueError"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=5)

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        renderer._pypdfium2 = mock_pypdfium2

        with pytest.raises(ValueError, match="页码超出范围"):
            renderer.render_page("/path/to/doc.pdf", page_number=10)

    def test_render_page_negative_page_number(self) -> None:
        """验证负页码抛出 ValueError"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=5)

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        renderer._pypdfium2 = mock_pypdfium2

        with pytest.raises(ValueError, match="页码超出范围"):
            renderer.render_page("/path/to/doc.pdf", page_number=0)

    def test_render_page_scale_calculation(self) -> None:
        """验证 DPI→scale 换算：scale = dpi / 72"""
        renderer, _ = self._create_renderer_with_mock()
        renderer._dpi = 300  # 自定义 DPI

        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_bitmap = MagicMock()
        mock_pil_image = MagicMock()

        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)
        mock_page.render.return_value = mock_bitmap
        mock_bitmap.to_pil.return_value = mock_pil_image

        def fake_save(buf: Any, format: str = "PNG") -> None:
            buf.write(b"png_data")

        mock_pil_image.save = fake_save

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        renderer._pypdfium2 = mock_pypdfium2

        renderer.render_page("/path/to/doc.pdf", page_number=1)

        # 验证 scale 参数：300 / 72 ≈ 4.167
        mock_page.render.assert_called_once()
        call_kwargs = mock_page.render.call_args
        assert call_kwargs.kwargs["scale"] == pytest.approx(300 / 72)

    def test_render_page_runtime_error(self) -> None:
        """验证渲染过程失败时抛出 RuntimeError"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pdf = MagicMock()
        mock_page = MagicMock()

        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)
        mock_page.render.side_effect = RuntimeError("渲染引擎崩溃")

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        renderer._pypdfium2 = mock_pypdfium2

        with pytest.raises(RuntimeError, match="渲染 PDF 页面失败"):
            renderer.render_page("/path/to/doc.pdf", page_number=1)

    def test_render_page_closes_pdf_on_success(self) -> None:
        """验证成功渲染后关闭 PDF 文档"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_bitmap = MagicMock()
        mock_pil_image = MagicMock()

        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)
        mock_page.render.return_value = mock_bitmap
        mock_bitmap.to_pil.return_value = mock_pil_image

        def fake_save(buf: Any, format: str = "PNG") -> None:
            buf.write(b"png")

        mock_pil_image.save = fake_save

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        renderer._pypdfium2 = mock_pypdfium2

        renderer.render_page("/path/to/doc.pdf", page_number=1)

        mock_pdf.close.assert_called_once()

    def test_render_page_closes_pdf_on_error(self) -> None:
        """验证渲染失败后仍关闭 PDF 文档（资源不泄漏）"""
        renderer, _ = self._create_renderer_with_mock()

        mock_pdf = MagicMock()
        mock_page = MagicMock()

        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)
        mock_page.render.side_effect = RuntimeError("boom")

        mock_pypdfium2 = MagicMock()
        mock_pypdfium2.PdfDocument.return_value = mock_pdf

        renderer._pypdfium2 = mock_pypdfium2

        with pytest.raises(RuntimeError):
            renderer.render_page("/path/to/doc.pdf", page_number=1)

        mock_pdf.close.assert_called_once()
