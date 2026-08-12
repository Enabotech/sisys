"""领域层混合检索编排异常模块

HybridSearchError 用于三路检索通道（Dense + Sparse + Graph）均失败时。

设计理由（继承链选择）：
- HybridSearchError(209) 继承 BusinessException：检索编排属于业务子域，
  非外部服务错误（替换 RuntimeError 历史违规）
- HTTP 映射至 500 Internal Server Error（服务端处理失败）
- 编码 209 落在 business 子域扩展范围 (201, 209) 内
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException


class HybridSearchError(BusinessException):
    """混合检索编排错误

    三路检索通道（Dense + Sparse + Graph）均失败时抛出，
    替代 RuntimeError 历史违规（Hard Constraints 禁止裸内置异常）。

    Attributes:
        code: EXCEPTION_209
        message: 检索编排错误描述
    """

    code = "EXCEPTION_209"
    message = "Hybrid search error"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        """初始化混合检索编排错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
        """
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "HybridSearchError",
]
