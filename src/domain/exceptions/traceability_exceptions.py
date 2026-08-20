"""领域层 溯源异常模块

高保真溯源专属异常，包含 LLM 评估调用失败和引文查询未找到两类异常。

异常编码范围：EXCEPTION_370 ~ EXCEPTION_379（预留 10 个码）

设计理由（继承链选择）：
- TraceabilityError(370) 继承 ExternalException：LLM 评估是外部模型服务调用，
  属于外部异常范畴，HTTP 映射至 500 Internal Server Error
  （精确注册避免 isinstance 回退到 ExternalException 基类 502）
- TraceabilityNotFoundError(371) 继承 BusinessException：引文查询未找到属于
  业务规则违反，HTTP 映射至 404 Not Found（精确注册避免回退到 BusinessException 基类 400）

语义澄清：
- trace() 主流程在置信度 < min_confidence 时返回空 citations 列表（正常业务结果，不抛异常）
- TraceabilityNotFoundError 仅用于查询类方法（get_citation_detail / get_citation_by_document）
  找不到目标引文时抛出

消息安全性：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException
from src.domain.exceptions.external_exceptions import ExternalException


class TraceabilityError(ExternalException):
    """LLM 评估调用失败

    当 LLM 引文质量评估调用出现不可恢复的错误（如 API 调用失败、响应解析失败等）时抛出。

    继承 ExternalException，HTTP 映射至 500 Internal Server Error
    （与 RelevanceEvaluationError 一致，评估失败是服务端处理失败）。

    Attributes:
        code: EXCEPTION_370
        message: 默认消息
        claim: 结论文本（截断至 100 字符）
        citation_count: 引文数量
    """

    code = "EXCEPTION_370"
    message = "溯源评估调用失败"

    def __init__(
        self,
        claim: str,
        citation_count: int,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化 LLM 评估调用失败错误

        Args:
            claim: 结论文本（截断至 100 字符）
            citation_count: 引文数量
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str | int] = {
            "claim": claim[:100],
            "citation_count": citation_count,
        }
        super().__init__(message=message, cause=cause, context=context)


class TraceabilityNotFoundError(BusinessException):
    """按 ID/文档查询引文未找到

    当 get_citation_detail() / get_citation_by_document() 查询类方法
    找不到目标引文时抛出。

    Attention: trace() 主流程不抛此异常——置信度 < min_confidence 时
    返回空 citations 列表（正常业务结果）。

    继承 BusinessException，HTTP 映射至 404 Not Found
    （与 NotFoundError 一致，资源不存在属于业务规则违反）。

    Attributes:
        code: EXCEPTION_371
        message: 默认消息
        claim: 结论文本（截断至 100 字符）
        min_confidence: 最小置信度阈值
    """

    code = "EXCEPTION_371"
    message = "未找到溯源引文"

    def __init__(
        self,
        claim: str,
        min_confidence: float,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化引文查询未找到错误

        Args:
            claim: 结论文本（截断至 100 字符）
            min_confidence: 最小置信度阈值
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str | float] = {
            "claim": claim[:100],
            "min_confidence": min_confidence,
        }
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "TraceabilityError",
    "TraceabilityNotFoundError",
]
