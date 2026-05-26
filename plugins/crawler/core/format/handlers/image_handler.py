"""图片文件格式处理器模块

使用 Pillow 提取 JPEG/PNG EXIF 元数据
"""

from __future__ import annotations

import os

from plugins.crawler.core.value_objects import FileMetadata


class ImageFormatHandler:
    """图片文件格式处理器 — 支持 JPEG/PNG/GIF"""

    EXTENSIONS: tuple[str, ...] = ("jpeg", "jpg", "png", "gif")
    MIME_TYPES: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/gif",
    )

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self.EXTENSIONS

    @property
    def supported_mime_types(self) -> tuple[str, ...]:
        return self.MIME_TYPES

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        return ext in self.EXTENSIONS or mime_type.lower().startswith("image/")

    def extract_metadata(self, file_path: str) -> FileMetadata:
        """从图片文件提取 EXIF 元数据

        Args:
            file_path: 图片文件路径

        Returns:
            文件元数据
        """
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                exif = img.getexif() if hasattr(img, "getexif") else {}

                title = exif.get(270, "")  # ImageDescription
                if isinstance(title, bytes):
                    title = title.decode("utf-8", errors="ignore")

                return FileMetadata(title=str(title) if title else "")
        except Exception:
            return FileMetadata()
