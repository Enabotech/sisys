"""Storage Exceptions — 存储服务相关异常.

异常来源：
- src/domain/services/memory_service.py → MemoryVersionConflictError, MemoryNotFoundError
- src/infrastructure/storage/minio/bucket_manager.py → BucketNameValidationError
- src/infrastructure/storage/minio/client_adapter.py → BucketNotFoundError, MinIOConnectionError
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions.business_exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from src.domain.exceptions.system_exceptions import NetworkError


class MemoryVersionConflictError(ConflictError):
    """版本冲突异常（保留 memory_id 属性）."""

    code = "EXCEPTION_203"

    def __init__(self, memory_id: UUID, message: str = "版本冲突") -> None:
        self.memory_id = memory_id
        super().__init__(f"{message}: memory_id={memory_id}")


class MemoryNotFoundError(NotFoundError):
    """记忆不存在异常（保留 memory_id 属性）."""

    code = "EXCEPTION_202"

    def __init__(self, memory_id: UUID, message: str = "记忆不存在") -> None:
        self.memory_id = memory_id
        super().__init__(message)


class BucketNotFoundError(NotFoundError):
    """Bucket 不存在异常."""

    code = "EXCEPTION_202"
    message = "Bucket not found"


class MinIOConnectionError(NetworkError):
    """MinIO 连接错误."""

    code = "EXCEPTION_102"
    message = "MinIO connection error"


class BucketNameValidationError(ValidationError):
    """Bucket 名称验证失败异常."""

    code = "EXCEPTION_201"
    message = "Bucket name validation failed"


class MemoryAccessDeniedError(PermissionDeniedError):
    """记忆访问被拒绝异常."""

    code = "EXCEPTION_204"
    message = "Memory access denied"


__all__ = [
    "MemoryVersionConflictError",
    "MemoryNotFoundError",
    "BucketNotFoundError",
    "MinIOConnectionError",
    "BucketNameValidationError",
    "MemoryAccessDeniedError",
]
