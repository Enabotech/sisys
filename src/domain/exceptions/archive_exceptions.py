"""领域层档案异常模块

定义战略档案管理相关的领域异常，包括档案不存在、冲突、存储层协同失败等。
档案管理是业务子域，继承 BusinessException 层次（NotFoundError/ConflictError）。
编码分配：archive 子域（282-289）。
"""

from __future__ import annotations

from uuid import UUID

from src.domain.exceptions.business_exceptions import (
    BusinessException,
    ConflictError,
    NotFoundError,
)


class ArchiveNotFoundError(NotFoundError):
    """档案不存在异常

    Attributes:
        code: 异常编码 EXCEPTION_282
        archive_id: 不存在的档案 ID
    """

    code = "EXCEPTION_282"

    def __init__(
        self,
        archive_id: UUID,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化档案不存在异常

        Args:
            archive_id: 不存在的档案 ID
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.archive_id = archive_id
        if message is None:
            message = f"Archive not found: {archive_id}"
        super().__init__(message, cause=cause, context={"archive_id": str(archive_id)})


class ArchiveConflictError(ConflictError):
    """档案重复/冲突异常

    Attributes:
        code: 异常编码 EXCEPTION_283
        archive_id: 冲突的档案 ID
    """

    code = "EXCEPTION_283"

    def __init__(
        self,
        archive_id: UUID,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化档案冲突异常

        Args:
            archive_id: 冲突的档案 ID
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.archive_id = archive_id
        if message is None:
            message = f"Archive conflict: {archive_id}"
        super().__init__(message, cause=cause, context={"archive_id": str(archive_id)})


class ArchiveStorageError(BusinessException):
    """存储层协同失败异常

    Attributes:
        code: 异常编码 EXCEPTION_284
        layer: 指示失败存储层（l2/l3/l4/l5）
    """

    code = "EXCEPTION_284"

    def __init__(
        self,
        layer: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化存储层协同失败异常

        Args:
            layer: 指示失败存储层（l2/l3/l4/l5）
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.layer = layer
        if message is None:
            message = f"Archive storage error at layer {layer}"
        super().__init__(message, cause=cause, context={"layer": layer})


__all__ = [
    "ArchiveNotFoundError",
    "ArchiveConflictError",
    "ArchiveStorageError",
]
