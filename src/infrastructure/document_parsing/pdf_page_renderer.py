"""基础设施层 PDF 页面渲染器实现

基于 pypdfium2 + Pillow 将 PDF 文件的指定页面渲染为 PNG 图像字节。
"""

from __future__ import annotations

import io
import logging

from src.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PdfPageRenderer:
    """PDF 页面渲染器

    使用 pypdfium2 将 PDF 页面光栅化为 PNG 图像字节，
    供 LayoutDetector.detect() 消费。

    Args:
        dpi: 渲染分辨率（默认 150，平衡速度与质量）

    Raises:
        ImportError: pypdfium2 未安装
    """

    def __init__(self, dpi: int = 150) -> None:
        """初始化 PDF 页面渲染器

        Args:
            dpi: 渲染分辨率
        """
        try:
            import pypdfium2 as _pypdfium2

            self._pypdfium2 = _pypdfium2
        except ImportError as e:
            raise ImportError("pypdfium2 未安装。请执行: pip install pypdfium2") from e
        self._dpi = dpi

    def render_page(self, file_path: str, page_number: int) -> bytes:
        """渲染 PDF 文件的指定页面为 PNG 图像字节

        Args:
            file_path: PDF 文件本地路径
            page_number: 页码（1-indexed）

        Returns:
            PNG 图像的二进制数据

        Raises:
            FileNotFoundError: PDF 文件不存在
            ValidationError: 页码超出范围
            RuntimeError: 渲染失败
        """
        try:
            pdf = self._pypdfium2.PdfDocument(file_path)
        except Exception as e:
            logger.warning("无法打开 PDF 文件: %s", file_path, exc_info=True)
            raise FileNotFoundError(f"无法打开 PDF 文件: {file_path}") from e

        try:
            # pypdfium2 页码为 0-indexed
            page_idx = page_number - 1
            if page_idx < 0 or page_idx >= len(pdf):
                logger.warning("页码超出范围: %d（总页数: %d）", page_number, len(pdf))
                raise ValidationError(message=f"页码超出范围: {page_number}（总页数: {len(pdf)}）")

            page = pdf[page_idx]
            bitmap = page.render(scale=self._dpi / 72)
            pil_image = bitmap.to_pil()

            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            return buf.getvalue()
        except (ValueError, FileNotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.exception("渲染 PDF 页面失败 (file=%s, page=%d)", file_path, page_number)
            raise RuntimeError(f"渲染 PDF 页面失败: {e}") from e
        finally:
            pdf.close()
