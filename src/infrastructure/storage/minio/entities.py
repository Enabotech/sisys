"""基础设施层 MinIO 对象存储实体模块

定义 ObjectMetadata 和 LifecycleRule 等存储结构体，位于基础设施层（非领域层）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass
class ObjectMetadata:
    """对象存储元数据

    Attributes:
        object_id: 对象唯一标识（UUID）
        bucket_name: Bucket 名称
        object_key: 对象键（路径）
        version_id: 版本 ID（启用版本控制时）
        content_type: MIME 类型
        size_bytes: 对象大小（字节）
        etag: ETag 哈希
        upload_id: 分片上传 ID（断点续传时使用）
        uploaded_parts: 已上传分片信息
        worm_locked: 是否启用 WORM 锁定
        retention_until: 保留期限
        created_at: 创建时间
        created_by: 创建者
        tags: 对象标签（用于生命周期管理）
    """

    object_id: UUID
    bucket_name: str
    object_key: str
    content_type: str
    size_bytes: int
    etag: str
    version_id: str | None = None
    upload_id: str | None = None
    uploaded_parts: list[dict[str, Any]] = field(default_factory=list)
    worm_locked: bool = False
    retention_until: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """将对象元数据序列化为字典

        Returns:
            包含所有元数据字段的字典
        """
        return {
            "object_id": str(self.object_id),
            "bucket_name": self.bucket_name,
            "object_key": self.object_key,
            "version_id": self.version_id,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "etag": self.etag,
            "upload_id": self.upload_id,
            "uploaded_parts": self.uploaded_parts,
            "worm_locked": self.worm_locked,
            "retention_until": self.retention_until.isoformat() if self.retention_until else None,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ObjectMetadata:
        """从字典反序列化

        Args:
            data: 包含对象元数据字段的字典

        Returns:
            ObjectMetadata 实例
        """
        return cls(
            object_id=UUID(data["object_id"]) if isinstance(data["object_id"], str) else data["object_id"],
            bucket_name=data["bucket_name"],
            object_key=data["object_key"],
            content_type=data["content_type"],
            size_bytes=data["size_bytes"],
            etag=data["etag"],
            version_id=data.get("version_id"),
            upload_id=data.get("upload_id"),
            uploaded_parts=data.get("uploaded_parts", []),
            worm_locked=data.get("worm_locked", False),
            retention_until=_parse_optional_datetime(data.get("retention_until")),
            created_at=_parse_datetime(data.get("created_at", datetime.now(UTC))),
            created_by=data.get("created_by", ""),
            tags=data.get("tags", {}),
        )


@dataclass
class LifecycleRule:
    """对象生命周期规则

    Attributes:
        rule_id: 规则唯一标识
        status: 规则状态（"Enabled" / "Disabled"）
        prefix: 前缀过滤
        expiration_days: 过期天数（None 表示不过期）
        transition_days: 转换存储类型天数
        transition_storage_class: 目标存储类型（如 "GLACIER"）
    """

    rule_id: str
    status: str
    prefix: str
    expiration_days: int | None = None
    transition_days: int | None = None
    transition_storage_class: str | None = None

    def to_minio_dict(self) -> dict:
        """转换为 MinIO 生命周期规则字典

        Returns:
            MinIO LifecycleConfig 兼容的规则字典
        """
        rule: dict[str, Any] = {
            "ID": self.rule_id,
            "Status": self.status,
            "Filter": {"Prefix": self.prefix},
        }
        if self.expiration_days is not None:
            rule["Expiration"] = {"Days": self.expiration_days}
        if self.transition_days is not None and self.transition_storage_class:
            rule["Transition"] = {
                "Days": self.transition_days,
                "StorageClass": self.transition_storage_class,
            }
        return rule


def _parse_optional_datetime(value: str | datetime | None) -> datetime | None:
    """解析可选的 ISO 格式日期时间字符串

    Args:
        value: ISO 格式日期时间字符串、datetime 对象或 None

    Returns:
        解析后的 datetime 对象，输入为 None 时返回 None
    """
    if value is None:
        return None
    return _parse_datetime(value)


def _parse_datetime(value: str | datetime) -> datetime:
    """解析 ISO 格式日期时间字符串或直接返回 datetime 对象

    Args:
        value: ISO 格式字符串或 datetime 对象

    Returns:
        datetime 对象
    """
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
