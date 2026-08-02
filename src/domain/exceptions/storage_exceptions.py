"""领域层存储异常模块

定义存储服务相关异常，如记忆版本冲突、记忆不存在、Bucket 操作失败等

异常来源：
- src/domain/services/memory_service.py → MemoryVersionConflictError, MemoryNotFoundError
- src/infrastructure/storage/minio/bucket_manager.py → BucketNameValidationError
- src/infrastructure/storage/minio/minio_manager.py → BucketNotFoundError, MinIOConnectionError
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions.business_exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
    BusinessRuleViolationError,
)
from src.domain.exceptions.system_exceptions import NetworkError


class MinIOConnectionError(NetworkError):
    """MinIO 连接错误

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_106"
    message = "MinIO connection error"


class MemoryNotFoundError(NotFoundError):
    """记忆不存在异常

    Attributes:
        code: 异常编码
        memory_id: 未找到的记忆标识
    """

    code = "EXCEPTION_211"

    def __init__(self, memory_id: UUID, message: str = "记忆不存在") -> None:
        """初始化记忆不存在异常

        Args:
            memory_id: 未找到的记忆标识
            message: 异常消息，默认为"记忆不存在"
        """
        self.memory_id = memory_id
        super().__init__(message)


class BucketNotFoundError(NotFoundError):
    """Bucket 不存在异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_212"
    message = "Bucket not found"


class MemoryVersionConflictError(ConflictError):
    """记忆版本冲突异常

    Attributes:
        code: 异常编码
        memory_id: 冲突的记忆标识
    """

    code = "EXCEPTION_213"

    def __init__(self, memory_id: UUID, message: str = "版本冲突") -> None:
        """初始化记忆版本冲突异常

        Args:
            memory_id: 冲突的记忆标识
            message: 异常消息，默认为"版本冲突"
        """
        self.memory_id = memory_id
        super().__init__(f"{message}: memory_id={memory_id}")


class BucketNameValidationError(ValidationError):
    """Bucket 名称验证失败异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_214"
    message = "Bucket name validation failed"


class MemoryAccessDeniedError(PermissionDeniedError):
    """记忆访问被拒绝异常

    Attributes:
        code: 异常编码
        message: 异常消息
    """

    code = "EXCEPTION_215"
    message = "Memory access denied"


class DocumentVersionConflictError(ConflictError):
    """文档版本冲突异常

    当乐观锁检查发现文档版本不匹配时抛出。

    Attributes:
        code: 异常编码
        document_id: 冲突的文档标识
        expected_version: 期望的版本号
        actual_version: 实际的版本号
    """

    code = "EXCEPTION_216"

    def __init__(
        self,
        document_id: UUID,
        expected_version: int,
        actual_version: int,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        """初始化文档版本冲突异常

        Args:
            document_id: 冲突的文档标识
            expected_version: 期望的版本号
            actual_version: 实际的版本号
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
            context: 额外上下文信息
        """
        self.document_id = document_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        if message is None:
            message = f"文档版本冲突: document_id={document_id}, expected={expected_version}, actual={actual_version}"
        merged_context = dict(context or {})
        merged_context["document_id"] = str(document_id)
        merged_context["expected_version"] = expected_version
        merged_context["actual_version"] = actual_version
        super().__init__(message, cause=cause, context=merged_context)


class MetadataValidationError(BusinessRuleViolationError):
    """文档元数据校验失败异常

    当入库文档的元数据不满足最小元字段集要求时抛出。

    Attributes:
        code: 异常编码 EXCEPTION_217
        document_id: 校验失败的文档标识
        missing_fields: 缺失的必需字段列表
        tenant_id: 租户标识符
    """

    code = "EXCEPTION_217"

    def __init__(
        self,
        document_id: UUID,
        missing_fields: list[str],
        tenant_id: str = "",
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化文档元数据校验失败异常

        Args:
            document_id: 校验失败的文档标识
            missing_fields: 缺失的必需字段列表
            tenant_id: 租户标识符
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.document_id = document_id
        self.missing_fields = missing_fields
        self.tenant_id = tenant_id
        if message is None:
            message = f"文档元数据校验失败: document_id={document_id}, missing_fields={missing_fields}"
        merged_context = {
            "document_id": str(document_id),
            "missing_fields": missing_fields,
            "tenant_id": tenant_id,
        }
        super().__init__(message, cause=cause, context=merged_context)


__all__ = [
    "DocumentVersionConflictError",
    "MemoryVersionConflictError",
    "MemoryNotFoundError",
    "BucketNotFoundError",
    "MinIOConnectionError",
    "BucketNameValidationError",
    "MemoryAccessDeniedError",
    "MetadataValidationError",
]
