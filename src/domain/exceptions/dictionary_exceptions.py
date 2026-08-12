"""领域层词典管理异常模块

定义词典管理相关的领域异常，包括词条不存在、词条冲突、版本冲突等。
词典管理是业务子域，继承 BusinessException 层次（NotFoundError/ConflictError）。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import (
    ConflictError,
    NotFoundError,
)


class DictionaryNotFoundError(NotFoundError):
    """词典词条/快照不存在异常

    Attributes:
        code: 异常编码 EXCEPTION_270
        term: 不存在的词条文本（或快照版本标识）
    """

    code = "EXCEPTION_270"

    def __init__(
        self,
        term: str = "",
        version: int | None = None,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化词典词条不存在异常

        Args:
            term: 不存在的词条文本
            version: 不存在的版本号（回滚场景）
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.term = term
        self.version = version
        if message is None:
            if version is not None:
                message = f"词典版本 {version} 不存在"
            else:
                message = f"词典词条 '{term}' 不存在"
        merged_context: dict[str, object] = {"term": term}
        if version is not None:
            merged_context["version"] = version
        super().__init__(message, cause=cause, context=merged_context)


class DictionaryEntryConflictError(ConflictError):
    """词典词条重复/冲突异常

    Attributes:
        code: 异常编码 EXCEPTION_271
        term: 冲突的词条文本
    """

    code = "EXCEPTION_271"

    def __init__(
        self,
        term: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化词典词条冲突异常

        Args:
            term: 冲突的词条文本
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.term = term
        if message is None:
            message = f"词典词条 '{term}' 已存在"
        super().__init__(message, cause=cause, context={"term": term})


class DictionaryVersionConflictError(ConflictError):
    """词典版本号不匹配（乐观锁冲突）异常

    Attributes:
        code: 异常编码 EXCEPTION_272
        expected_version: 期望的版本号
        actual_version: 实际的版本号
    """

    code = "EXCEPTION_272"

    def __init__(
        self,
        expected_version: int,
        actual_version: int,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化词典版本冲突异常

        Args:
            expected_version: 期望的版本号
            actual_version: 实际的版本号
            message: 异常消息，默认使用标准格式
            cause: 导致此异常的原因
        """
        self.expected_version = expected_version
        self.actual_version = actual_version
        if message is None:
            message = f"词典版本冲突: expected={expected_version}, actual={actual_version}"
        super().__init__(
            message,
            cause=cause,
            context={
                "expected_version": expected_version,
                "actual_version": actual_version,
            },
        )


__all__ = [
    "DictionaryNotFoundError",
    "DictionaryEntryConflictError",
    "DictionaryVersionConflictError",
]
