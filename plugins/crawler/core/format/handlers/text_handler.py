"""文本文件格式处理器模块

提取 TXT/CSV/Markdown 首行作为标题

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os

from plugins.crawler.core.value_objects import FileMetadata


class TextFormatHandler:
    """文本文件格式处理器 — 支持 TXT/CSV/Markdown"""

    EXTENSIONS: tuple[str, ...] = ("txt", "csv", "md", "markdown")
    MIME_TYPES: tuple[str, ...] = (
        "text/plain",
        "text/csv",
        "text/markdown",
    )
    MAX_TITLE_LENGTH: int = 100

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self.EXTENSIONS

    @property
    def supported_mime_types(self) -> tuple[str, ...]:
        return self.MIME_TYPES

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        return ext in self.EXTENSIONS or mime_type.lower().startswith("text/")

    def extract_metadata(self, file_path: str) -> FileMetadata:
        """从文本文件提取元数据（首个非空行作为标题）

        Args:
            file_path: 文件路径

        Returns:
            文件元数据
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if content.startswith("﻿"):
                content = content[1:]

            for line in content.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue

                if stripped.startswith("#"):
                    stripped = stripped.lstrip("# ").strip()

                if stripped and len(stripped) > 2:
                    title = stripped[: self.MAX_TITLE_LENGTH]
                    return FileMetadata(title=title, content_title=title)

            return FileMetadata()
        except Exception:
            return FileMetadata()
