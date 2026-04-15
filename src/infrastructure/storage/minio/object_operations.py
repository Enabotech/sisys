"""MinIO 对象操作。

提供流式上传/下载、分片上传、断点续传等对象操作。
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from minio.error import S3Error

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.client_adapter import MinioClientAdapter

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# 大小阈值常量（字节）
MB = 1024 * 1024
GB = 1024 * MB

# <100MB 不分片
SINGLE_UPLOAD_THRESHOLD = 100 * MB
# 100MB-1GB 使用 10MB 分片
MEDIUM_PART_SIZE = 10 * MB
MEDIUM_THRESHOLD = 1 * GB
# 1GB-10GB 使用 50MB 分片
LARGE_PART_SIZE = 50 * MB
LARGE_THRESHOLD = 10 * GB
# >10GB 使用 100MB 分片
XLARGE_PART_SIZE = 100 * MB


def calculate_part_size(file_size: int) -> int:
    """根据文件大小计算分片大小。

    Args:
        file_size: 文件大小（字节）

    Returns:
        分片大小（字节）
    """
    if file_size < SINGLE_UPLOAD_THRESHOLD:
        return 0  # 0 表示不需要分片
    if file_size < MEDIUM_THRESHOLD:
        return MEDIUM_PART_SIZE
    if file_size < LARGE_THRESHOLD:
        return LARGE_PART_SIZE
    return XLARGE_PART_SIZE


class ObjectOperations:
    """MinIO 对象操作。

    提供流式上传/下载、分片上传、断点续传等功能。

    Args:
        config: MinIO 连接配置
    """

    def __init__(self, config: MinIOConfig) -> None:
        """初始化对象操作。

        Args:
            config: MinIO 连接配置
        """
        self._config = config
        self._adapter = MinioClientAdapter(config)

    @property
    def _client(self) -> MinioClientAdapter:
        """获取客户端适配器。

        Returns:
            MinioClientAdapter 实例
        """
        return self._adapter

    def upload_object(
        self,
        bucket_name: str,
        object_key: str,
        file_path: str,
        content_type: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        """上传对象，大文件自动分片。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            version_id: 对象版本 ID
        """
        file_size = os.path.getsize(file_path)
        part_size = calculate_part_size(file_size)

        if part_size > 0:
            return self._multipart_upload(bucket_name, object_key, file_path, content_type, part_size, tags)

        return self._single_upload(bucket_name, object_key, file_path, content_type, tags)

    def _single_upload(
        self,
        bucket_name: str,
        object_key: str,
        file_path: str,
        content_type: str,
        tags: dict[str, str] | None = None,
    ) -> str:
        """单文件上传（<100MB）。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            version_id: 对象版本 ID
        """
        try:
            client = self._client.client

            # 构建 tags 参数
            tags_param = None
            if tags:
                from minio.commonconfig import Tags

                tags_param = Tags()
                for k, v in tags.items():
                    tags_param[k] = v

            result = client.fput_object(
                bucket_name,
                object_key,
                file_path,
                content_type=content_type,
                tags=tags_param,
            )
            logger.info("Uploaded object: %s/%s", bucket_name, object_key)
            return result.version_id or ""

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def _multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        file_path: str,
        content_type: str,
        part_size: int,
        tags: dict[str, str] | None = None,
    ) -> str:
        """分片上传（>=100MB）。

        使用 MinIO 公开 API `fput_object`，它会根据 part_size 自动分片，
        避免使用私有 API（`_create_multipart_upload` 等）导致的不稳定。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            part_size: 分片大小（字节）
            tags: 对象标签

        Returns:
            version_id: 对象版本 ID
        """
        try:
            client = self._client.client

            # 构建 tags 参数
            tags_param = None
            if tags:
                from minio.commonconfig import Tags

                tags_param = Tags()
                for k, v in tags.items():
                    tags_param[k] = v

            result = client.fput_object(
                bucket_name,
                object_key,
                file_path,
                content_type=content_type,
                part_size=part_size,
                tags=tags_param,
            )
            logger.info(
                "Multipart uploaded object: %s/%s (part_size: %d bytes)",
                bucket_name,
                object_key,
                part_size,
            )
            return result.version_id or ""

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    async def download_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """流式下载对象。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Yields:
            字节流数据块
        """
        try:
            client = self._client.client
            response = client.get_object(
                bucket_name,
                object_key,
                version_id=version_id,
            )
            try:
                chunk_size = 8192
                while True:
                    data = response.read(chunk_size)
                    if not data:
                        break
                    yield data
            finally:
                response.close()
                response.release_conn()

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def get_object_metadata(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        """获取对象元数据。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            对象元数据字典
        """
        try:
            client = self._client.client
            stat = client.stat_object(
                bucket_name,
                object_key,
                version_id=version_id,
            )

            metadata: dict[str, Any] = {
                "bucket_name": bucket_name,
                "object_key": object_key,
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "version_id": version_id,
            }
            if stat.version_id:
                metadata["version_id"] = stat.version_id
            return metadata

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def delete_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            是否删除成功
        """
        try:
            client = self._client.client
            client.remove_object(
                bucket_name,
                object_key,
                version_id=version_id,
            )
            logger.info("Deleted object: %s/%s", bucket_name, object_key)
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning("Object does not exist: %s/%s", bucket_name, object_key)
                return False
            mapped = self._client._map_error(e)
            raise mapped

    async def resume_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        redis_client: aioredis.Redis,
    ) -> None:
        """恢复分片上传。

        从 Redis 读取已上传的分片状态，继续上传未完成的部分。
        Redis 状态更新采用批量策略（每 N 个分片或完成时写入），避免写风暴。

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            upload_id: 分片上传 ID
            redis_client: Redis 客户端（用于读取已上传分片状态）

        Raises:
            KeyError: 当 Redis 中不存在该上传记录时抛出
        """
        state_key = f"minio:multipart:{upload_id}"

        # 从 Redis 读取状态
        state_data = await redis_client.get(state_key)
        if state_data is None:
            raise KeyError(f"No multipart upload state found for upload_id: {upload_id}")

        state = json.loads(state_data)
        file_path = state["file_path"]
        part_size = state["part_size"]
        uploaded_parts = state.get("uploaded_parts", [])
        completed_part_numbers = {p["PartNumber"] for p in uploaded_parts}

        # 批量写入阈值
        redis_batch_interval = 5
        parts_since_flush = 0

        try:
            client = self._client.client
            parts = list(uploaded_parts)
            part_number = 1

            with open(file_path, "rb") as f:
                while True:
                    data = f.read(part_size)
                    if not data:
                        break

                    if part_number not in completed_part_numbers:
                        etag = client._put_object(  # type: ignore[call-arg]
                            bucket_name,
                            object_key,
                            data,
                            length=len(data),
                            part_number=part_number,
                            upload_id=upload_id,
                        )
                        parts.append({"PartNumber": part_number, "ETag": etag})
                        parts_since_flush += 1

                        # 批量写入 Redis（每 N 个分片写入一次）
                        if parts_since_flush >= redis_batch_interval:
                            state["uploaded_parts"] = parts
                            await redis_client.set(state_key, json.dumps(state))
                            parts_since_flush = 0

                    part_number += 1

            # 完成分片上传 — 最终写入 Redis 状态
            state["uploaded_parts"] = parts
            await redis_client.set(state_key, json.dumps(state))

            client._complete_multipart_upload(bucket_name, object_key, upload_id, parts)

            # 清理 Redis 状态
            await redis_client.delete(state_key)

            logger.info(
                "Resumed and completed multipart upload: %s/%s",
                bucket_name,
                object_key,
            )

        except S3Error as e:
            # 失败时也写入当前状态，以便下次恢复
            if parts:
                state["uploaded_parts"] = parts
                await redis_client.set(state_key, json.dumps(state))
            mapped = self._client._map_error(e)
            raise mapped

    async def save_multipart_state(
        self,
        upload_id: str,
        file_path: str,
        content_type: str,
        part_size: int,
        redis_client: aioredis.Redis,
    ) -> None:
        """保存分片上传状态到 Redis。

        Args:
            upload_id: 分片上传 ID
            file_path: 本地文件路径
            content_type: MIME 类型
            part_size: 分片大小
            redis_client: Redis 客户端
        """
        state_key = f"minio:multipart:{upload_id}"
        state = {
            "upload_id": upload_id,
            "file_path": file_path,
            "content_type": content_type,
            "part_size": part_size,
            "uploaded_parts": [],
        }
        await redis_client.set(state_key, json.dumps(state))
