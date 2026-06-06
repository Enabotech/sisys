"""视频文件格式处理器模块

使用 ffmpeg-python 的 ffprobe 接口提取视频文件元数据
"""

from __future__ import annotations

import os
from typing import Any

from plugins.crawler.core.value_objects import FileMetadata


class VideoFormatHandler:
    """视频文件格式处理器 — 使用 ffmpeg.probe() 提取元数据"""

    EXTENSIONS: tuple[str, ...] = (
        "mp4",
        "avi",
        "mov",
        "mkv",
        "webm",
        "wmv",
        "flv",
        "m4v",
        "3gp",
    )
    MIME_TYPES: tuple[str, ...] = (
        "video/mp4",
        "video/x-msvideo",
        "video/quicktime",
        "video/x-matroska",
        "video/webm",
        "video/x-ms-wmv",
        "video/x-flv",
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
        """从视频文件提取元数据

        Args:
            file_path: 视频文件路径

        Returns:
            文件元数据
        """
        try:
            import ffmpeg

            probe = ffmpeg.probe(file_path)
            format_info: dict[str, Any] = probe.get("format", {})

            tags: dict[str, Any] = format_info.get("tags", {})
            title = tags.get("title", "") or tags.get("TITLE", "")
            author = tags.get("artist", "") or tags.get("ARTIST", "")

            return FileMetadata(
                title=str(title) if title else "",
                author=str(author) if author else "",
            )
        except Exception:
            return FileMetadata()
