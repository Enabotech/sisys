"""SISYS 领域层 L4 MinIO WORM 对象存储抽象端口模块

对应 architecture.md §11.1：
- 原始文档、证据包存储
- Object Lock COMPLIANCE 模式 7 年 retention

设计说明：
- 与 ObjectStorageRepository Protocol 语义完全兼容
- 使用 file_path 流式上传（防 OOM）
- WORM 合规存储通过 archive_with_retention 实现

设计原则：
- 领域层零外部依赖（仅用 abc + typing）
- 异步优先（async def）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class L4ObjectPort(Protocol):
    """L4 MinIO WORM 对象存储接口

    对应 architecture.md §11.1：
    - 原始文档、证据包存储
    - Object Lock COMPLIANCE 模式 7 年 retention
    """

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
            bucket_type: Bucket 类型（如 "raw-documents"）
            object_key: 对象键（路径）
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            版本 ID 或 ETag
        """

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

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象（WORM 锁定对象抛出 ComplianceLockError）

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            是否成功
        """

    async def get_metadata(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict:
        """获取对象元数据

        注意：MinIO SDK 对不存在的对象会抛出异常，此方法不返回 None
        调用方应使用 try/catch 处理异常

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            元数据字典（对象不存在时 SDK 抛出异常）
        """

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,  # 7 年
    ) -> str:
        """归档对象（带 WORM retention）

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            content: 对象内容（bytes），None 表示只设置 retention
            retention_days: retention 天数（默认 2555 = 7 年）

        Returns:
            对象 ID 或 ETag
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
