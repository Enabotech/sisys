"""领域层 摘要生成异常模块

定义契约化摘要生成领域的业务异常。
遵循统一异常设计规范。

子域：summary（290-299）

设计与继承链选择：
- SummaryGenerationError（EXCEPTION_290）继承 BusinessException 但映射 HTTP 500——
  摘要编排属于业务子域，非外部服务错误（与 HybridSearchError/LayeredRetrievalError/
  ArchiveStorageError 先例一致），通过 EXCEPTION_HTTP_MAP 显式注册覆盖基类默认 400 映射。
- SummaryPerspectiveNotSupportedError（EXCEPTION_291）继承 ValidationError——
  不支持的视角属于请求参数校验错误，映射 HTTP 400 合理。

消息安全性：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException, ValidationError


class SummaryGenerationError(BusinessException):
    """摘要生成整体失败

    当摘要生成流程出现不可恢复的错误（如 LLM API 调用失败、
    Schema 验证失败等）时抛出。

    Attributes:
        code: 错误码 EXCEPTION_290
        message: 默认消息
    """

    code = "EXCEPTION_290"
    message = "摘要生成失败"

    def __init__(
        self,
        perspective: str,
        query_text: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化摘要生成错误

        Args:
            perspective: 视角类型
            query_text: 查询文本（截断至 100 字符）
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str] = {
            "perspective": perspective,
            "query_text": query_text[:100],
        }
        super().__init__(message=message, cause=cause, context=context)


class SummaryPerspectiveNotSupportedError(ValidationError):
    """不支持的视角类型

    当视角参数不属于（"financial"/"market"/"technical"）时抛出。

    Attributes:
        code: 错误码 EXCEPTION_291
        message: 默认消息
    """

    code = "EXCEPTION_291"
    message = "不支持的摘要视角"

    def __init__(
        self,
        perspective: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化不支持的视角错误

        Args:
            perspective: 不支持的视角
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str] = {"perspective": perspective}
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "SummaryGenerationError",
    "SummaryPerspectiveNotSupportedError",
]
