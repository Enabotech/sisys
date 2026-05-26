"""Office 文档格式处理器模块

使用 python-docx / python-pptx / openpyxl 提取 DOCX/PPTX/XLSX 元数据

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os

from plugins.crawler.core.value_objects import FileMetadata


class OfficeFormatHandler:
    """Office 文档格式处理器 — 支持 DOC/DOCX/PPT/PPTX/XLS/XLSX"""

    EXTENSIONS: tuple[str, ...] = ("doc", "docx", "ppt", "pptx", "xls", "xlsx")
    MIME_TYPES: tuple[str, ...] = (
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self.EXTENSIONS

    @property
    def supported_mime_types(self) -> tuple[str, ...]:
        return self.MIME_TYPES

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        return ext in self.EXTENSIONS or mime_type.lower() in self.MIME_TYPES

    def extract_metadata(self, file_path: str) -> FileMetadata:
        """从 Office 文档提取元数据

        Args:
            file_path: 文档路径

        Returns:
            文件元数据
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".docx",):
            return self._extract_docx(file_path)
        elif ext in (".pptx",):
            return self._extract_pptx(file_path)
        elif ext in (".xlsx",):
            return self._extract_xlsx(file_path)
        else:
            return FileMetadata()

    def _extract_docx(self, file_path: str) -> FileMetadata:
        """提取 DOCX 元数据"""
        try:
            from docx import Document

            doc = Document(file_path)
            props = doc.core_properties

            return FileMetadata(
                title=props.title or "",
                author=props.author or "",
                subject=props.subject or "",
                created=str(props.created) if props.created else "",
            )
        except Exception:
            return FileMetadata()

    def _extract_pptx(self, file_path: str) -> FileMetadata:
        """提取 PPTX 元数据"""
        try:
            from pptx import Presentation

            prs = Presentation(file_path)
            props = prs.core_properties

            return FileMetadata(
                title=props.title or "",
                author=props.author or "",
                subject=props.subject or "",
                created=str(props.created) if props.created else "",
            )
        except Exception:
            return FileMetadata()

    def _extract_xlsx(self, file_path: str) -> FileMetadata:
        """提取 XLSX 元数据"""
        try:
            from openpyxl import load_workbook

            wb = load_workbook(file_path, read_only=True)
            props = wb.properties

            return FileMetadata(
                title=props.title or "",
                author=props.creator or "",
                subject=props.subject or "",
                created=str(props.created) if props.created else "",
            )
        except Exception:
            return FileMetadata()
