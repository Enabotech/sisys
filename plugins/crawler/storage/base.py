"""存储抽象端口模块

定义 StoragePort 协议，抽象文件存储行为

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StoragePort(Protocol):
    """存储抽象端口

    定义文件存储的统一接口，支持本地存储和 MinIO 存储实现
    """

    async def store_file(
        self,
        file_name: str,
        file_path: str,
        content_type: str,
        metadata: dict[str, str],
    ) -> str:
        """存储文件

        Args:
            file_name: 目标文件名
            file_path: 本地源文件路径
            content_type: MIME 类型
            metadata: 文件元数据字典

        Returns:
            存储后的文件路径或对象键
        """
        ...

    async def file_exists(self, file_name: str) -> bool:
        """检查文件是否已存在

        Args:
            file_name: 文件名

        Returns:
            是否存在
        """
        ...
