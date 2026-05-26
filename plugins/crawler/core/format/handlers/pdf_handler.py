"""PDF 格式处理器模块

使用 pypdf2 提取 PDF 文件元数据

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from plugins.crawler.core.value_objects import FileMetadata


class PdfFormatHandler:
    """PDF 格式处理器 — 使用 pypdf2 提取元数据"""

    EXTENSIONS: tuple[str, ...] = ("pdf",)
    MIME_TYPES: tuple[str, ...] = ("application/pdf",)

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
            info = reader.metadata or {}

            title = info.get("/Title", "") or info.get("Title", "")
            author = info.get("/Author", "") or info.get("Author", "")
            subject = info.get("/Subject", "") or info.get("Subject", "")
            created = info.get("/CreationDate", "") or info.get("CreationDate", "")

            return FileMetadata(
                title=str(title) if title else "",
                author=str(author) if author else "",
                subject=str(subject) if subject else "",
                created=str(created) if created else "",
            )
        except Exception:
            return FileMetadata()
