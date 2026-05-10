"""MinIO Bucket 管理器。

提供 Bucket 创建、删除、存在性检查及命名验证功能。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from minio.error import S3Error
from minio.objectlockconfig import ObjectLockConfig
from minio.versioningconfig import VersioningConfig

from src.domain.exceptions.storage_exceptions import BucketNameValidationError
from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.client_adapter import MinioClientAdapter

logger = logging.getLogger(__name__)

# Bucket 命名模式: {prefix}-{type}-{tenant_id}
BUCKET_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")


class BucketManager:
    """MinIO Bucket 管理器。

    负责 Bucket 的创建、删除、存在性检查及命名验证。

    Args:
        config: MinIO 连接配置
    """

    def __init__(self, config: MinIOConfig) -> None:
        """初始化 Bucket 管理器。

        Args:
            config: MinIO 连接配置
        """
        self._config = config
        self._adapter = MinioClientAdapter(config)

    @property
    def bucket_prefix(self) -> str:
        """获取 Bucket 前缀。

        Returns:
            Bucket 名称前缀
        """
        return self._config.bucket_prefix

    @property
    def _client(self) -> MinioClientAdapter:
        """获取客户端适配器。

        Returns:
            MinioClientAdapter 实例
        """
        return self._adapter

    def validate_bucket_name(self, bucket_name: str) -> bool:
        """验证 Bucket 名称是否符合命名规范。

        命名模式: {prefix}-{type}-{tenant_id}，其中各部分均为小写字母数字和连字符。

        Args:
            bucket_name: Bucket 名称

        Returns:
            如果名称有效返回 True

        Raises:
            BucketNameValidationError: 名称不符合规范时抛出
        """
        if not bucket_name:
            raise BucketNameValidationError("Bucket name cannot be empty")

        if not BUCKET_NAME_PATTERN.match(bucket_name):
            raise BucketNameValidationError(
                f"Invalid bucket name '{bucket_name}': must match pattern "
                f"{{prefix}}-{{type}}-{{tenant_id}} (lowercase alphanumeric with hyphens)"
            )

        # 验证至少包含两个连字符分隔的部分
        parts = bucket_name.split("-")
        if len(parts) < 3:
            raise BucketNameValidationError(
                f"Invalid bucket name '{bucket_name}': must have at least 3 parts "
                f"separated by hyphens: {{prefix}}-{{type}}-{{tenant_id}}"
            )

        return True

    def build_bucket_name(self, bucket_type: str, tenant_id: str) -> str:
        """根据 bucket_type 和 tenant_id 构建 Bucket 名称。

        格式: {bucket_prefix}-{bucket_type}-{tenant_id}

        Args:
            bucket_type: Bucket 类型（如 "raw-documents"、"audit-archives"）
            tenant_id: 租户 ID

        Returns:
            构建的 Bucket 名称
        """
        bucket_name = f"{self._config.bucket_prefix}-{bucket_type}-{tenant_id}"
        self.validate_bucket_name(bucket_name)
        return bucket_name

    def create_bucket(
        self,
        bucket_name: str,
        enable_versioning: bool = False,
        enable_object_lock: bool = False,
    ) -> bool:
        """创建 Bucket。

        Args:
            bucket_name: Bucket 名称
            enable_versioning: 是否启用版本控制
            enable_object_lock: 是否启用对象锁定（WORM）

        Returns:
            是否创建成功

        Raises:
            BucketNameValidationError: Bucket 名称无效时抛出
        """
        self.validate_bucket_name(bucket_name)

        try:
            client = self._client.client
            client.make_bucket(
                bucket_name,
                object_lock=enable_object_lock,
            )
            logger.info("Created bucket: %s", bucket_name)

            if enable_versioning:
                versioning = VersioningConfig(status="Enabled")
                client.set_bucket_versioning(bucket_name, versioning)
                logger.info("Enabled versioning for bucket: %s", bucket_name)

            return True

        except S3Error as e:
            if e.code == "BucketAlreadyExists" or e.code == "BucketAlreadyOwnedByYou":
                logger.warning("Bucket already exists: %s", bucket_name)
                return False
            mapped = self._client._map_error(e)
            raise mapped

    def enable_object_lock(self, bucket_name: str, retention_days: int = 2555) -> bool:
        """为 Bucket 启用对象锁定（WORM）。

        Args:
            bucket_name: Bucket 名称
            retention_days: 默认保留天数（默认 2555 天 = 7 年）

        Returns:
            是否启用成功
        """
        self.validate_bucket_name(bucket_name)

        try:
            client = self._client.client
            lock_config = ObjectLockConfig(
                mode="GOVERNANCE",
                duration=retention_days,
                duration_unit="Days",
            )
            client.set_object_lock_config(bucket_name, lock_config)
            logger.info(
                "Enabled object lock for bucket: %s (retention: %d days)",
                bucket_name,
                retention_days,
            )
            return True

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """删除 Bucket。

        Args:
            bucket_name: Bucket 名称
            force: 是否强制删除（先清空 Bucket 内所有对象）

        Returns:
            是否删除成功
        """
        self.validate_bucket_name(bucket_name)

        try:
            client = self._client.client

            if force:
                # 先删除 Bucket 内所有对象和版本
                objects = client.list_objects(bucket_name, recursive=True)
                for obj in objects:
                    client.remove_object(bucket_name, obj.object_name)
                logger.info("Force-deleted all objects in bucket: %s", bucket_name)

            client.remove_bucket(bucket_name)
            logger.info("Deleted bucket: %s", bucket_name)
            return True

        except S3Error as e:
            if e.code == "NoSuchBucket":
                logger.warning("Bucket does not exist: %s", bucket_name)
                return False
            mapped = self._client._map_error(e)
            raise mapped

    def bucket_exists(self, bucket_name: str) -> bool:
        """检查 Bucket 是否存在。

        Args:
            bucket_name: Bucket 名称

        Returns:
            如果存在返回 True
        """
        self.validate_bucket_name(bucket_name)

        try:
            client = self._client.client
            buckets = client.list_buckets()
            return any(b.name == bucket_name for b in buckets)

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def list_buckets(self) -> list[dict[str, Any]]:
        """列出所有 Bucket。

        Returns:
            Bucket 信息列表，每个字典包含 name 和 creation_date
        """
        try:
            client = self._client.client
            buckets = client.list_buckets()
            return [
                {
                    "name": b.name,
                    "creation_date": b.creation_date,
                }
                for b in buckets
            ]

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped
