"""MinIO S3 存储实现模块

将爬取的文件存储到 MinIO 对象存储
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MinIOStorage:
    """MinIO S3 存储实现"""

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "",
        secret_key: str = "",
        bucket_prefix: str = "sisys",
        secure: bool = False,
    ):
        """初始化 MinIO 存储

        Args:
            endpoint: MinIO 端点地址
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket_prefix: 桶前缀
            secure: 是否使用 HTTPS
        """
        from minio import Minio

        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket_prefix = bucket_prefix
        self._default_bucket = f"{bucket_prefix}-raw-documents-default"
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保默认存储桶存在"""
        if not self._client.bucket_exists(self._default_bucket):
            self._client.make_bucket(self._default_bucket)
            logger.info("创建存储桶: %s", self._default_bucket)

    async def store_file(
        self,
        file_name: str,
        file_path: str,
        content_type: str,
        metadata: dict[str, str],
    ) -> str:
        """存储文件到 MinIO

        Args:
            file_name: 目标文件名
            file_path: 本地源文件路径
            content_type: MIME 类型
            metadata: 文件元数据（含 task_id）

        Returns:
            对象存储键
        """
        task_id = metadata.get("task_id", "unknown")
        object_key = f"crawled/{task_id}/{file_name}"
        self._client.fput_object(
            self._default_bucket,
            object_key,
            file_path,
            content_type=content_type,
        )
        logger.info("文件已上传: %s → %s", file_name, object_key)
        return object_key

    async def file_exists(self, file_name: str) -> bool:
        """检查文件是否已存在

        Args:
            file_name: 文件名

        Returns:
            是否存在
        """
        objects = self._client.list_objects(
            self._default_bucket,
            prefix="crawled/",
            recursive=True,
        )
        for obj in objects:
            if obj.object_name.endswith(f"/{file_name}"):
                return True
        return False
