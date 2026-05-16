"""MinIO 对象存储层适配器。

L4 对象存储层 — MinIO S3 兼容实现。
"""

from __future__ import annotations

from src.infrastructure.storage.minio.bucket_manager import BucketManager
from src.infrastructure.storage.minio.entities import LifecycleRule, ObjectMetadata
from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter
from src.infrastructure.storage.minio.minio_manager import (
    BucketNotFoundError,
    ComplianceLockError,
    MinIOConnectionError,
    MinioManager,
    PermissionDeniedError,
)
from src.infrastructure.storage.minio.minio_repository import MinIORepository
from src.infrastructure.storage.minio.object_operations import ObjectOperations
from src.infrastructure.storage.minio.worm_lifecycle import WORMManager

__all__ = [
    "BucketManager",
    "BucketNotFoundError",
    "ComplianceLockError",
    "LifecycleRule",
    "MinIOAdapter",
    "MinIOConnectionError",
    "MinIORepository",
    "MinioManager",
    "ObjectMetadata",
    "ObjectOperations",
    "PermissionDeniedError",
    "WORMManager",
]
