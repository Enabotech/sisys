"""压缩包格式处理器模块

使用标准库 zipfile/tarfile 提取内部文件名列表

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
import tarfile
import zipfile

from plugins.crawler.core.value_objects import FileMetadata


class ArchiveFormatHandler:
    """压缩包格式处理器 — 支持 ZIP/TAR/GZ/BZ2"""

    EXTENSIONS: tuple[str, ...] = ("zip", "tar", "gz", "bz2", "tgz")
    MIME_TYPES: tuple[str, ...] = (
        "application/zip",
        "application/x-tar",
        "application/gzip",
        "application/x-bzip2",
    )
    MAX_NAMES: int = 5

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
        """从压缩包提取元数据（内部文件名列表）

        Args:
            file_path: 压缩包路径

        Returns:
            文件元数据
        """
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".zip":
                names = self._list_zip(file_path)
            elif ext in (".tar", ".tgz"):
                names = self._list_tar(file_path)
            elif ext in (".gz", ".bz2"):
                names = self._list_tar(file_path)
            else:
                return FileMetadata()

            if names:
                title = "包含: " + ", ".join(names[: self.MAX_NAMES])
                if len(names) > self.MAX_NAMES:
                    title += f" 等 {len(names)} 个文件"
                return FileMetadata(title=title)
            return FileMetadata()
        except Exception:
            return FileMetadata()

    def _list_zip(self, file_path: str) -> list[str]:
        """列出 ZIP 内文件名"""
        with zipfile.ZipFile(file_path, "r") as zf:
            return [os.path.basename(name) for name in zf.namelist() if not name.endswith("/")]

    def _list_tar(self, file_path: str) -> list[str]:
        """列出 TAR 内文件名"""
        with tarfile.open(file_path, "r:*") as tf:
            return [m.name.split("/")[-1] for m in tf.getmembers() if m.isfile()]
