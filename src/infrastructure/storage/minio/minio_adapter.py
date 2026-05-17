"""SISYS 基础设施层 MinIO 适配器模块。

包装 MinIORepository，实现 L4ObjectPort 接口。薄适配器层，仅做接口转换，
所有方法委托给内部仓储实例。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from src.domain.ports.l4_object import L4ObjectPort

if TYPE_CHECKING:
    from src.infrastructure.storage.minio.minio_repository import MinIORepository


class MinIOAdapter(L4ObjectPort):
    """MinIO 对象存储适配器

    包装现有 MinIORepository，实现 L4ObjectPort 接口
    所有方法委托给内部仓储实例
    """

    def __init__(self, repository: MinIORepository):
        """初始化适配器

        Args:
            repository: MinIORepository 实例
        """
        self._repository = repository

    async def store(
        self,
        bucket_type: str,
        object_key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> str:
        """存储对象（流式，防 OOM）

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            版本 ID 或 ETag
        """
        return await self._repository.store(
            bucket_type=bucket_type,
            object_key=object_key,
            file_path=file_path,
            content_type=content_type,
            tags=tags,
        )

    def retrieve(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """流式下载对象（防 OOM）

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Yields:
            字节流数据块
        """
        return self._repository.retrieve(
            bucket_type=bucket_type,
            object_key=object_key,
            version_id=version_id,
        )

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            是否成功
        """
        return await self._repository.delete(
            bucket_type=bucket_type,
            object_key=object_key,
            version_id=version_id,
        )

    async def get_metadata(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict:
        """获取对象元数据

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            元数据字典
        """
        return await self._repository.get_metadata(
            bucket_type=bucket_type,
            object_key=object_key,
            version_id=version_id,
        )

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str:
        """归档对象（带 WORM retention）

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            content: 对象内容，None 表示只设置 retention
            retention_days: retention 天数

        Returns:
            对象 ID 或 ETag
        """
        return await self._repository.archive(
            bucket_type=bucket_type,
            object_key=object_key,
            content=content,
            retention_days=retention_days,
        )

    async def list_objects(
        self,
        bucket_type: str,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[dict]:
        """列出对象，支持前缀过滤

        Args:
            bucket_type: Bucket 类型
            prefix: 前缀过滤
            recursive: 是否递归列出子目录

        Returns:
            对象元数据列表
        """
        return await self._repository.list_objects(
            bucket_type=bucket_type,
            prefix=prefix,
            recursive=recursive,
        )
