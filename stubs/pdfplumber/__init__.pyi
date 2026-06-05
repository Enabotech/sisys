"""pdfplumber 类型存根

基于 pdfplumber 公开 API 提供类型定义。
pdfplumber 用于 PDF 表格检测和结构提取。
覆盖 PdfTableExtractor 使用的方法。
来源: src/infrastructure/document_parsing/pdf_table_extractor.py
"""

from typing import Any


class Table:
    """pdfplumber 检测到的表格对象"""

    @property
    def bbox(self) -> tuple[float, float, float, float]: ...

    @property
    def extract_text(self) -> str | None: ...

    def extract(self, **kwargs: Any) -> list[list[str | None]]: ...


class Page:
    """pdfplumber PDF 页面对象"""

    @property
    def page_number(self) -> int: ...

    @property
    def width(self) -> float: ...

    @property
    def height(self) -> float: ...

    def find_tables(self, **kwargs: Any) -> list[Table]: ...

    def extract_text(self, **kwargs: Any) -> str | None: ...

    def extract_tables(self, **kwargs: Any) -> list[list[list[str | None]]]: ...

    def to_image(self, resolution: int = ...) -> Any: ...

    def close(self) -> None: ...


class PDF:
    """pdfplumber PDF 文档对象"""

    def __init__(self, path_or_fp: Any, **kwargs: Any) -> None: ...

    @property
    def pages(self) -> list[Page]: ...

    @property
    def metadata(self) -> dict[str, Any] | None: ...

    def close(self) -> None: ...

    def __enter__(self) -> "PDF": ...

    def __exit__(self, *args: Any) -> None: ...


def open(path_or_fp: Any, **kwargs: Any) -> PDF: ...
