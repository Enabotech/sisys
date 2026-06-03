"""领域层 PDF 页面渲染端口

定义 PDF 页面渲染器的 Protocol 接口，将 PDF 文件的指定页面渲染为 PNG 图像字节。
实现类通过 pypdfium2 + Pillow 完成光栅化渲染。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PdfPageRendererPort(Protocol):
    """PDF 页面渲染端口协议

    将 PDF 文件的指定页面渲染为图像字节（PNG 格式），
    供 LayoutDetector.detect() 消费进行版面检测。

    Methods:
        render_page: 渲染 PDF 文件的指定页面为 PNG 图像字节
    """

    def render_page(self, file_path: str, page_number: int) -> bytes:
        """渲染 PDF 文件的指定页面为 PNG 图像字节

        Args:
            file_path: PDF 文件本地路径
            page_number: 页码（1-indexed）

        Returns:
            PNG 图像的二进制数据
        """
        ...
