"""领域层 检索相关性评估异常模块

相关性评估专属异常，包含 LLM 评估调用失败和检索结果不足阻断两类异常。

异常编码范围：EXCEPTION_360 ~ EXCEPTION_369（预留 10 个码）

设计理由（继承链选择）：
- RelevanceEvaluationError(360) 继承 ExternalException：LLM 评估是外部模型服务调用，
  属于外部异常范畴（与 RerankError(350) 一致），HTTP 映射至 500 Internal Server Error
  （精确注册避免 isinstance 回退到 ExternalException 基类 502）
- RelevanceEvaluationBlockedError(361) 继承 BusinessException：检索结果不足阻断属于
  业务规则违反，HTTP 映射至 422 Unprocessable Entity（精确注册避免回退到 BusinessException 基类 400）

消息安全性：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException
from src.domain.exceptions.external_exceptions import ExternalException


class RelevanceEvaluationError(ExternalException):
    """LLM 评估调用失败

    当 LLM-as-a-Judge 评估调用出现不可恢复的错误（如 API 调用失败、响应解析失败等）时抛出。

    继承 ExternalException，HTTP 映射至 500 Internal Server Error
    （与 RerankError 一致，评估失败是服务端处理失败）。

    Attributes:
        code: EXCEPTION_360
        message: 默认消息
        query_text: 查询文本（截断至 100 字符）
        result_count: 检索结果数量
    """

    code = "EXCEPTION_360"
    message = "LLM 评估调用失败"

    def __init__(
        self,
        query_text: str,
        result_count: int,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化 LLM 评估调用失败错误

        Args:
            query_text: 查询文本（截断至 100 字符）
            result_count: 检索结果数量
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str | int] = {
            "query_text": query_text[:100],
            "result_count": result_count,
        }
        super().__init__(message=message, cause=cause, context=context)


class RelevanceEvaluationBlockedError(BusinessException):
    """检索结果不足被阻断

    当检索结果综合评分 < 0.6 时，由调用方（SummaryGenerationService 或 API 路由）
    基于 RelevanceEvaluationResult.should_block 抛出此异常。

    Attention: evaluate() 本身不抛出此异常，阻断信息通过 should_block/block_reason 字段传递。

    继承 BusinessException，HTTP 映射至 422 Unprocessable Entity
    （与 BusinessRuleViolationError 一致，检索结果不足属于业务规则违反）。

    Attributes:
        code: EXCEPTION_361
        message: 默认消息
        query_text: 查询文本（截断至 100 字符）
        overall_score: 综合评分
        block_reason: 阻断理由
    """

    code = "EXCEPTION_361"
    message = "检索结果不足被阻断"

    def __init__(
        self,
        query_text: str,
        overall_score: float,
        block_reason: str,
        message: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化检索结果不足阻断错误

        Args:
            query_text: 查询文本（截断至 100 字符）
            overall_score: 综合评分
            block_reason: 阻断理由，如"数据不足"
            message: 错误描述
            cause: 原始异常
        """
        context: dict[str, str | float] = {
            "query_text": query_text[:100],
            "overall_score": overall_score,
            "block_reason": block_reason,
        }
        super().__init__(message=message, cause=cause, context=context)


__all__ = [
    "RelevanceEvaluationError",
    "RelevanceEvaluationBlockedError",
]
