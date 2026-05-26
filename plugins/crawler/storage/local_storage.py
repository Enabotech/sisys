"""本地文件系统存储实现模块

将爬取的文件存储到本地目录

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import shutil
from pathlib import Path


class LocalStorage:
    """本地文件系统存储实现"""

    def __init__(self, output_dir: str = "./crawl_output"):
        """初始化本地存储

        Args:
            output_dir: 输出目录路径
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def store_file(
        self,
        file_name: str,
        file_path: str,
        content_type: str,
        metadata: dict[str, str],
    ) -> str:
        """存储文件到本地目录

        Args:
            file_name: 目标文件名
            file_path: 本地源文件路径
            content_type: MIME 类型（本地存储忽略）
            metadata: 文件元数据（本地存储忽略）

        Returns:
            目标文件完整路径
        """
        dest = self._output_dir / file_name
        shutil.copy2(file_path, dest)
        return str(dest)

    async def file_exists(self, file_name: str) -> bool:
        """检查文件是否已存在

        Args:
            file_name: 文件名

        Returns:
            是否存在
        """
        return (self._output_dir / file_name).exists()
