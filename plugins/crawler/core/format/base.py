"""文件格式处理器协议模块

定义 FileFormatHandler Protocol，所有格式处理器必须实现此接口
零外部依赖，仅使用标准库
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from plugins.crawler.core.value_objects import FileMetadata


@runtime_checkable
class FileFormatHandler(Protocol):
    """文件格式处理器协议

    每种文件格式实现此接口，提供元数据提取和格式识别能力
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        """支持的文件扩展名"""
        ...

    @property
    def supported_mime_types(self) -> tuple[str, ...]:
        """支持的 MIME 类型"""
        ...

    def can_handle(self, file_path: str, mime_type: str) -> bool:
        """判断是否能处理该文件

        Args:
            file_path: 文件路径
            mime_type: MIME 类型

        Returns:
            是否能处理
        """
        ...

    def extract_metadata(self, file_path: str) -> FileMetadata:
        """提取文件元数据

        Args:
            file_path: 文件路径

        Returns:
            文件元数据
        """
        ...
