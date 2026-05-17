"""基础设施层 MinIO WORM 锁定与生命周期管理模块

提供 WORM（Write Once Read Many）锁定、对象归档和生命周期配置功能，
满足 SOX 合规要求

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging
from typing import Any

from minio.commonconfig import Filter
from minio.error import S3Error
from minio.lifecycleconfig import (
    Expiration,
    LifecycleConfig,
    Rule,
    Transition,
)
from minio.retention import Retention

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.entities import LifecycleRule
from src.infrastructure.storage.minio.minio_manager import (
    ComplianceLockError,
    MinioManager,
)

logger = logging.getLogger(__name__)

# SOX 合规默认保留天数：7 年
SOX_RETENTION_DAYS = 2555


class WORMManager:
    """MinIO WORM 锁定与生命周期管理器

    提供 WORM 锁定、对象归档和生命周期配置功能

    Args:
        config: MinIO 连接配置
    """

    def __init__(self, config: MinIOConfig) -> None:
        """初始化 WORM 管理器

        Args:
            config: MinIO 连接配置
        """
        self._config = config
        self._adapter = MinioManager.from_config(config)

    @property
    def _client(self) -> MinioManager:
        """获取客户端适配器

        Returns:
            MinioManager 实例
        """
        return self._adapter

    def enable_worm_lock(
        self,
        bucket_name: str,
        object_key: str,
        retention_days: int = SOX_RETENTION_DAYS,
    ) -> bool:
        """为对象启用 WORM 锁定

        设置 Governance 模式保留策略，在保留期内禁止删除或修改

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            retention_days: 保留天数（默认 2555 天 = 7 年）

        Returns:
            是否启用成功
        """
        try:
            client = self._client.client
            from datetime import UTC, datetime, timedelta

            retain_until = datetime.now(UTC) + timedelta(days=retention_days)

            # 设置对象锁定保留期
            retention = Retention(
                mode="GOVERNANCE",
                retain_until_date=retain_until,
            )
            client.set_object_retention(
                bucket_name,
                object_key,
                retention,
            )

            logger.info(
                "Enabled WORM lock for %s/%s (retention: %d days)",
                bucket_name,
                object_key,
                retention_days,
            )
            return True

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def archive_object(
        self,
        bucket_name: str,
        object_key: str,
        retention_days: int = SOX_RETENTION_DAYS,
    ) -> bool:
        """归档对象至 WORM 存储

        为对象设置长期保留策略，用于合规归档场景

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            retention_days: 保留天数（默认 2555 天 = 7 年）

        Returns:
            是否归档成功
        """
        return self.enable_worm_lock(bucket_name, object_key, retention_days)

    def configure_lifecycle(self, bucket_name: str, rules: list[LifecycleRule]) -> bool:
        """为 Bucket 配置生命周期规则

        Args:
            bucket_name: Bucket 名称
            rules: 生命周期规则列表

        Returns:
            是否配置成功
        """
        try:
            client = self._client.client

            # 构建 LifecycleConfig 对象
            rule_objects = []
            for rule in rules:
                # 构建 Expiration
                expiration = None
                if rule.expiration_days is not None:
                    expiration = Expiration(days=rule.expiration_days)

                # 构建 Transition
                transition = None
                if rule.transition_days and rule.transition_storage_class:
                    transition = Transition(
                        days=rule.transition_days,
                        storage_class=rule.transition_storage_class,
                    )

                rule_obj = Rule(
                    status=rule.status,
                    rule_filter=Filter(prefix=rule.prefix),
                    rule_id=rule.rule_id,
                    expiration=expiration,
                    transition=transition,
                )
                rule_objects.append(rule_obj)

            lifecycle = LifecycleConfig(rules=rule_objects)
            client.set_bucket_lifecycle(bucket_name, lifecycle)

            logger.info(
                "Configured %d lifecycle rules for bucket: %s",
                len(rules),
                bucket_name,
            )
            return True

        except S3Error as e:
            mapped = self._client._map_error(e)
            raise mapped

    def delete_object(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象，WORM 锁定对象抛出 ComplianceLockError

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            是否删除成功

        Raises:
            ComplianceLockError: 尝试删除 WORM 锁定对象时抛出
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
            # 仅将 Object Lock 相关错误映射为 ComplianceLockError
            # AccessDenied 可能是 IAM 策略问题，不一定是 WORM 锁定
            if e.code in (
                "InvalidObjectState",
                "ObjectLockConfigurationNotFoundError",
            ):
                raise ComplianceLockError(
                    f"Cannot delete WORM-locked object: {bucket_name}/{object_key}. Error: {e.message}"
                ) from e
            if e.code == "NoSuchKey":
                logger.warning("Object does not exist: %s/%s", bucket_name, object_key)
                return False
            mapped = self._client._map_error(e)
            raise mapped

    def get_object_retention(
        self,
        bucket_name: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict | None:
        """获取对象保留策略信息

        Args:
            bucket_name: Bucket 名称
            object_key: 对象键
            version_id: 可选版本 ID

        Returns:
            保留策略字典，如果未设置则返回 None
        """
        try:
            client = self._client.client
            retention = client.get_object_retention(
                bucket_name,
                object_key,
                version_id=version_id,
            )
            return {
                "mode": retention.mode if retention else None,
                "retain_until_date": retention.retain_until_date if retention else None,
            }

        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            mapped = self._client._map_error(e)
            raise mapped

    def list_lifecycle_rules(self, bucket_name: str) -> list[dict[str, Any]]:
        """列出 Bucket 的生命周期规则

        Args:
            bucket_name: Bucket 名称

        Returns:
            生命周期规则列表
        """
        try:
            client = self._client.client
            lifecycle = client.get_bucket_lifecycle(bucket_name)
            if lifecycle is None:
                return []
            rules = getattr(lifecycle, "rules", []) or []
            return [
                {
                    "ID": getattr(r, "id", ""),
                    "Status": getattr(r, "status", ""),
                    "Filter": getattr(r, "rule_filter", {}),
                }
                for r in rules
            ]

        except S3Error as e:
            if e.code == "NoSuchLifecycleConfiguration":
                return []
            mapped = self._client._map_error(e)
            raise mapped
