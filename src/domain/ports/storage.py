"""SISYS 领域层对象存储仓储模块（DEPRECATED）

已废弃：请使用 L4ObjectPort（src.domain.ports.l4_object）
本文件仅保留向后兼容

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from src.domain.exceptions.service_exceptions import ComplianceLockError

__all__ = ["ComplianceLockError"]


@runtime_checkable
class ObjectStorageRepository(Protocol):
    """对象存储领域仓储接口（DEPRECATED — 使用 L4ObjectPort）

    定义领域操作（store/retrieve/delete/archive），
    不暴露 S3 原生概念（bucket/key/ETag 等）

    DEPRECATED:
        请使用 L4ObjectPort 替代
    """

    async def store(
        self,
        bucket_type: str,
        object_key: str,
        file_path: str,
        content_type: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        """存储对象，返回 version_id。大文件自动分片上传

        Args:
            bucket_type: Bucket 类型（如 "raw-documents"、"audit-archives"）
            object_key: 对象键（路径）
            file_path: 本地文件路径（流式上传，防止 OOM）
            content_type: MIME 类型
            tags: 对象标签（用于生命周期管理）

        Returns:
            version_id: 对象版本 ID（启用版本控制时）
        """

    def retrieve(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """流式下载对象，防止大文件 OOM

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 可选版本 ID

        Yields:
            字节流数据块
        """

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象。WORM 锁定对象抛出 ComplianceLockError

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            是否删除成功

        Raises:
            ComplianceLockError: 尝试删除 WORM 锁定对象
        """

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
            version_id: 可选版本 ID

        Returns:
            对象元数据字典
        """

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

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str:
        """归档对象至 WORM 存储，启用 Object Lock

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            content: 对象内容，None 表示仅对已有对象设置 retention
            retention_days: 保留天数（默认 2555 天 = 7 年）

        Returns:
            对象 ID 或 ETag
        """
