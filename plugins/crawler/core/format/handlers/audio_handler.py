"""音频文件格式处理器模块

使用 tinytag 提取音频文件元数据
"""

from __future__ import annotations

import os

from plugins.crawler.core.value_objects import FileMetadata


class AudioFormatHandler:
    """音频文件格式处理器 — 使用 tinytag 提取元数据"""

    EXTENSIONS: tuple[str, ...] = (
        "mp3",
        "wav",
        "ogg",
        "flac",
        "aac",
        "wma",
        "m4a",
    )
    MIME_TYPES: tuple[str, ...] = (
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        "audio/flac",
        "audio/aac",
        "audio/x-ms-wma",
        "audio/mp4",
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
        """从音频文件提取元数据

        Args:
            file_path: 音频文件路径

        Returns:
            文件元数据
        """
        try:
            from tinytag import TinyTag

            tag = TinyTag.get(file_path)
            title = tag.title or ""
            author = tag.artist or ""

            return FileMetadata(
                title=title,
                author=author,
            )
        except Exception:
            return FileMetadata()
