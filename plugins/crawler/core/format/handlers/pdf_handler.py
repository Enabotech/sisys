"""PDF 格式处理器模块

使用 pypdf 提取 PDF 文件元数据
"""

from __future__ import annotations

from plugins.crawler.core.value_objects import FileMetadata


class PdfFormatHandler:
    """PDF 格式处理器 — 使用 pypdf 提取元数据"""

    EXTENSIONS: tuple[str, ...] = ("pdf",)
    MIME_TYPES: tuple[str, ...] = ("application/pdf",)
    _GARBAGE_TITLES: frozenset[str] = frozenset(
        {
            "Microsoft Word",
            "Microsoft PowerPoint",
            "Microsoft Excel",
            "Acrobat Distiller",
            "PDFCreator",
            "Adobe PDF",
            "Adobe Acrobat",
            "WPS",
            "Untitled",
        }
    )

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self.EXTENSIONS

    @property
    def supported_mime_types(self) -> tuple[str, ...]:
        return self.MIME_TYPES

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        return file_path.lower().endswith(".pdf") or mime_type.lower() == "application/pdf"

    def extract_metadata(self, file_path: str) -> FileMetadata:
        """从 PDF 文件提取元数据

        Args:
            file_path: PDF 文件路径

        Returns:
            文件元数据
        """
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            raw_meta = reader.metadata
            info: dict[str, object] = dict(raw_meta) if raw_meta else {}

            title = info.get("/Title", "") or info.get("Title", "")
            author = info.get("/Author", "") or info.get("Author", "")
            subject = info.get("/Subject", "") or info.get("Subject", "")
            created = info.get("/CreationDate", "") or info.get("CreationDate", "")

            content_title = self._extract_content_title(reader)

            return FileMetadata(
                title=str(title) if title else "",
                content_title=content_title,
                author=str(author) if author else "",
                subject=str(subject) if subject else "",
                created=str(created) if created else "",
            )
        except Exception:
            return FileMetadata()

    def _extract_content_title(self, reader) -> str:
        """从 PDF 内容提取标题

        优先级：大纲标题 > 首页首个非空行

        Args:
            reader: PdfReader 实例

        Returns:
            内容推导标题（失败返回空字符串）
        """
        outline_title = self._extract_outline_title(reader)
        if outline_title and not self._is_garbage_title(outline_title):
            return outline_title[:100]

        return self._extract_first_page_title(reader)

    def _extract_outline_title(self, reader) -> str:
        """从 PDF 大纲提取首个标题

        Args:
            reader: PdfReader 实例

        Returns:
            大纲首条标题（失败返回空字符串）
        """
        try:
            outline = reader.outline
            if not outline:
                return ""

            first_item = outline[0]
            if isinstance(first_item, list):
                first_item = first_item[0] if first_item else None
            if first_item and hasattr(first_item, "title"):
                return first_item.title or ""
            return ""
        except Exception:
            return ""

    def _extract_first_page_title(self, reader) -> str:
        """从首页提取首个非空行作为标题

        Args:
            reader: PdfReader 实例

        Returns:
            首页首行（失败返回空字符串）
        """
        try:
            if not reader.pages:
                return ""
            text = reader.pages[0].extract_text() or ""
            for line in text.split("\n"):
                line = line.strip()
                if line and len(line) > 2 and not self._is_garbage_title(line):
                    return line[:100]
            return ""
        except Exception:
            return ""

    def _is_garbage_title(self, title: str) -> bool:
        """检测工具自动生成的垃圾标题

        Args:
            title: 待检测标题

        Returns:
            是否为垃圾标题
        """
        return title.strip() in self._GARBAGE_TITLES
