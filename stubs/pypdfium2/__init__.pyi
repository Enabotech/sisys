"""pypdfium2 类型存根

基于 pypdfium2 v4.x 公开 API 提供完整类型定义。
pypdfium2 是 PDFium 的 Python 绑定，核心类为 PdfDocument/PdfPage/PdfBitmap。
覆盖 PdfPageRenderer 使用的方法。
来源: src/infrastructure/document_parsing/pdf_page_renderer.py
"""

from types import TracebackType

import PIL.Image

class PdfDocument:
    """PDF 文档 — 封装 PDF 文件的打开、页面访问与资源管理

    支持上下文管理器协议和索引访问。
    使用完毕后应调用 close() 或通过 with 语句释放原生 PDFium 资源。
    """

    def __init__(self, path: str) -> None: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> "PdfPage": ...
    def close(self) -> None: ...
    def __enter__(self) -> "PdfDocument": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


class PdfPage:
    """PDF 页面 — 提供页面渲染能力

    通过 PdfDocument.__getitem__ 获取，支持指定缩放比例渲染为位图。
    """

    def render(self, scale: float = ...) -> "PdfBitmap": ...


class PdfBitmap:
    """PDF 位图 — 页面渲染结果

    通过 PdfPage.render() 生成，可转换为 PIL Image 进行后续处理或编码导出。
    """

    def to_pil(self) -> PIL.Image.Image: ...
