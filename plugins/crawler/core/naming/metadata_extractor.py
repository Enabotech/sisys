"""统一元数据提取门面模块

委托 FileFormatHandlerRegistry 提取文件元数据
零外部依赖，仅使用标准库
"""

from __future__ import annotations

from plugins.crawler.core.format.registry import FileFormatHandlerRegistry
from plugins.crawler.core.value_objects import FileMetadata


class MetadataExtractor:
    """统一元数据提取门面 — 委托 FileFormatHandlerRegistry"""

    def __init__(self, registry: FileFormatHandlerRegistry):
        self._registry = registry

    def extract(
        self,
        file_path: str,
        extension: str,
        mime_type: str = "",
    ) -> FileMetadata:
        """提取文件元数据

        先尝试按扩展名查找处理器，再尝试 MIME 检测

        Args:
            file_path: 文件路径
            extension: 文件扩展名
            mime_type: MIME 类型（可选）

        Returns:
            文件元数据（提取失败返回空 FileMetadata）
        """
        handler = self._registry.get_handler(extension)

        if handler is None and mime_type:
            handler = self._registry.detect_format(file_path, mime_type)

        if handler is None:
            return FileMetadata()

        try:
            return handler.extract_metadata(file_path)
        except Exception:
            return FileMetadata()
