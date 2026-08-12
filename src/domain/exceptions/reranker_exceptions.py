"""领域层重排序异常模块

重排序专属异常，继承 ExternalException。
异常编码范围：EXCEPTION_350 ~ EXCEPTION_359（预留 10 个码）

设计理由（继承链选择）：
- RerankError(350) 继承 ExternalException：重排序是外部模型服务调用，
  属于外部异常范畴（与 EntityExtractionError 一致）
- HTTP 映射至 500 Internal Server Error（服务端处理失败），
  显式注册在 EXCEPTION_HTTP_MAP 中，避免 isinstance 回退到基类 502
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class RerankError(ExternalException):
    """重排序错误

    重排序过程中发生的不可恢复错误，包括：
    - 重排序模型加载失败
    - 重排序 API 调用超时
    - 重排序结果异常

    继承 ExternalException，HTTP 映射至 500 Internal Server Error
    （与 EntityExtractionError 先例一致，重排序失败是服务端处理失败）。

    Attributes:
        code: EXCEPTION_350
        message: 重排序错误描述
        model_name: 重排序模型名称
        top_k: 重排序的 Top-K 数量
        result_count: 输入结果数量
    """

    code = "EXCEPTION_350"
    message = "Rerank error"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        model_name: str = "",
        top_k: int = 0,
        result_count: int = 0,
    ) -> None:
        """初始化重排序错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            model_name: 重排序模型名称
            top_k: 重排序的 Top-K 数量
            result_count: 输入结果数量
        """
        ctx = dict(context or {})
        if model_name:
            ctx["model_name"] = model_name
        if top_k:
            ctx["top_k"] = top_k
        if result_count:
            ctx["result_count"] = result_count
        super().__init__(message=message, cause=cause, context=ctx)


__all__ = [
    "RerankError",
]
