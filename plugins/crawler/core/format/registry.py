"""文件格式处理器注册表模块

管理所有格式处理器的注册、查找和自动检测
零外部依赖，仅使用标准库
"""

from __future__ import annotations

from plugins.crawler.core.format.base import FileFormatHandler


class FileFormatHandlerRegistry:
    """文件格式处理器注册表"""

    def __init__(self) -> None:
        self._handlers: dict[str, FileFormatHandler] = {}

    def register(self, handler: FileFormatHandler) -> None:
        """注册格式处理器（按扩展名索引）

        Args:
            handler: 格式处理器实例
        """
        for ext in handler.supported_extensions:
            self._handlers[ext.lower()] = handler

    def get_handler(self, extension: str) -> FileFormatHandler | None:
        """按扩展名获取处理器

        Args:
            extension: 文件扩展名

        Returns:
            格式处理器，或 None
        """
        return self._handlers.get(extension.lower())

    def detect_format(self, file_path: str, mime_type: str) -> FileFormatHandler | None:
        """自动检测文件格式并返回对应处理器

        Args:
            file_path: 文件路径
            mime_type: MIME 类型

        Returns:
            匹配的格式处理器，或 None
        """
        for handler in set(self._handlers.values()):
            if handler.can_handle(file_path, mime_type):
                return handler
        return None

    def supported_extensions_list(self) -> list[str]:
        """列出所有已注册的扩展名"""
        return sorted(self._handlers.keys())

    def register_default_handlers(self) -> None:
        """注册内置默认处理器"""
        from plugins.crawler.core.format.handlers.archive_handler import (
            ArchiveFormatHandler,
        )
        from plugins.crawler.core.format.handlers.image_handler import (
            ImageFormatHandler,
        )
        from plugins.crawler.core.format.handlers.office_handler import (
            OfficeFormatHandler,
        )
        from plugins.crawler.core.format.handlers.pdf_handler import PdfFormatHandler
        from plugins.crawler.core.format.handlers.text_handler import TextFormatHandler

        self.register(PdfFormatHandler())
        self.register(OfficeFormatHandler())
        self.register(TextFormatHandler())
        self.register(ImageFormatHandler())
        self.register(ArchiveFormatHandler())

    def clear(self) -> None:
        """清空所有已注册的处理器"""
        self._handlers.clear()
