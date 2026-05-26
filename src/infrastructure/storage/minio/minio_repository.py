"""基础设施层 MinIO 仓储模块

MinIO 对象存储内部实现，被 MinIOAdapter（L4ObjectPort）组合委托，
方法签名与 L4ObjectPort 匹配
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from redis.asyncio import Redis

from src.infrastructure.storage.minio.bucket_manager import BucketManager
from src.infrastructure.storage.minio.object_operations import ObjectOperations
from src.infrastructure.storage.minio.worm_lifecycle import WORMManager


class MinIORepository:
    """MinIO 对象存储内部实现

    被 MinIOAdapter(L4ObjectPort) 组合委托，
    不声明 Protocol 继承
    """

    def __init__(
        self,
        bucket_manager: BucketManager,
        object_operations: ObjectOperations,
        worm_manager: WORMManager,
        tenant_id: str | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        """初始化仓储实现

        Args:
            bucket_manager: Bucket 管理器
            object_operations: 对象操作管理器
            worm_manager: WORM 管理器
            tenant_id: 租户 ID（用于 bucket 名称解析）
            redis_client: Redis 客户端（用于断点续传状态持久化）
        """
        self._bucket_manager = bucket_manager
        self._object_operations = object_operations
        self._worm_manager = worm_manager
        self._tenant_id = tenant_id
        self._redis_client = redis_client

    async def store(
        self,
        bucket_type: str,
        object_key: str,
        file_path: str,
        content_type: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        """存储对象，大文件自动分片上传

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            version_id
        """
        import asyncio

        bucket_name = self._resolve_bucket_name(bucket_type)
        return await asyncio.to_thread(
            self._object_operations.upload_object,
            bucket_name=bucket_name,
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
        """流式下载对象，防止大文件 OOM

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            字节流异步迭代器
        """
        bucket_name = self._resolve_bucket_name(bucket_type)
        return self._object_operations.download_object(
            bucket_name=bucket_name,
            object_key=object_key,
            version_id=version_id,
        )

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象，WORM 锁定对象抛出 ComplianceLockError

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            是否删除成功

        Raises:
            ComplianceLockError: 尝试删除 WORM 锁定对象时抛出
        """
        import asyncio

        bucket_name = self._resolve_bucket_name(bucket_type)
        return await asyncio.to_thread(
            self._worm_manager.delete_object,
            bucket_name=bucket_name,
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
        import asyncio

        bucket_name = self._resolve_bucket_name(bucket_type)
        return await asyncio.to_thread(
            self._object_operations.get_object_metadata,
            bucket_name=bucket_name,
            object_key=object_key,
            version_id=version_id,
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
        import asyncio

        bucket_name = self._resolve_bucket_name(bucket_type)
        return await asyncio.to_thread(
            self._list_objects_via_client,
            bucket_name,
            prefix,
            recursive,
        )

    def _list_objects_via_client(self, bucket_name: str, prefix: str, recursive: bool) -> list[dict]:
        """通过 MinIO 客户端列出对象（同步）

        Args:
            bucket_name: Bucket 名称
            prefix: 前缀过滤
            recursive: 是否递归

        Returns:
            对象元数据列表
        """
        client = self._bucket_manager._client.client
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=recursive)
        return [
            {
                "object_name": obj.object_name,
                "size": obj.size,
                "etag": obj.etag,
                "last_modified": obj.last_modified,
            }
            for obj in objects
        ]

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
            content: 对象内容（bytes），None 表示仅对已有对象设置 retention
            retention_days: 保留天数（默认 2555 天 = 7 年）

        Returns:
            对象键（归档成功后返回 object_key）
        """
        import asyncio
        from io import BytesIO

        bucket_name = self._resolve_bucket_name(bucket_type)

        # Upload content if provided
        if content is not None:
            client = self._bucket_manager._client.client
            await asyncio.to_thread(
                client.put_object,
                bucket_name=bucket_name,
                object_name=object_key,
                data=BytesIO(content),
                length=len(content),
            )

        # Set WORM retention
        await asyncio.to_thread(
            self._worm_manager.archive_object,
            bucket_name=bucket_name,
            object_key=object_key,
            retention_days=retention_days,
        )

        return object_key

    # -- Internal helpers -----------------------------------------------------------

    def _resolve_bucket_name(self, bucket_type: str) -> str:
        """将 bucket_type 解析为完整的物理 bucket 名称

        格式: {bucket_prefix}-{bucket_type}-{tenant_id}
        如果 tenant_id 未配置，使用 "default" 作为默认值
        """
        prefix = self._bucket_manager.bucket_prefix
        tenant_id = self._tenant_id if self._tenant_id else "default"
        return f"{prefix}-{bucket_type}-{tenant_id}"
