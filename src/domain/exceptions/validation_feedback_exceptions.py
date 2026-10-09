"""领域层 Validation Feedback 异常模块

Story 4.7 — Validation Feedback 闭环（增强重试与不可行标记）。

异常清单（仅 1 个，占用既定预留码位 EXCEPTION_399——4.1b/4.3 两度预留的兑现；
toolchain 子域 390-399 第 10 个也是最后一个码位）：
- ValidationFeedbackRetryExhaustedError: 3 次增强重试均失败，任务被判定不可行

语义区分（防同义混淆——必须显式写明）：
- ToolExecutionRetryExhaustedError（EXCEPTION_383）= **基础**重试（stage 级
  RetryPolicy）耗尽——仍可进入增强闭环；
- ValidationFeedbackRetryExhaustedError（EXCEPTION_399）= **增强**重试（反馈
  闭环级）耗尽——终态不可行结论。

对外契约：399 为闭环内部耗尽信号，由 ValidationFeedbackDecorator 捕获并转换为
ToolResult(INFEASIBLE) 结果返回（对外不抛异常——DAG 编排按 status 分支感知）。

HTTP 映射：422 Unprocessable Entity（与 396 出参校验失败语义对齐——「语义上
不可处理」而非 502「可重试下游故障」；不可行标记恰是「重试无意义」的终态结论）。

消息安全性：错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException

__all__ = ["ValidationFeedbackRetryExhaustedError"]


class ValidationFeedbackRetryExhaustedError(BusinessException):
    """增强重试（反馈闭环级）耗尽——任务终态不可行的内部信号

    与 EXCEPTION_383 的语义区分：383 = 基础重试（stage 级 RetryPolicy）耗尽，
    仍可进入增强闭环；本异常（399）= 增强重试耗尽，为终态结论——由装饰器
    捕获转换为 ToolResult(status=INFEASIBLE)，对外不抛。

    Attributes:
        code: 错误码 EXCEPTION_399
        message: 默认消息
    """

    code = "EXCEPTION_399"
    message = "Validation feedback enhanced retries exhausted (task marked infeasible)"

    def __init__(
        self,
        message: str | None = None,
        execution_id: str | None = None,
        tool_id: str | None = None,
        enhanced_retry_count: int | None = None,
        error_signature: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """初始化并组装 context 四字段.

        Args:
            message: 错误消息（默认类消息）
            execution_id: 触发执行的 execution id（与演进日志幂等键同源）
            tool_id: 工具 ID
            enhanced_retry_count: 增强尝试总数（1-3）
            error_signature: 归一化错误签名（64 hex）
            cause: 原始异常（耗尽前最后一次失败的触发异常，透传保留链路）
        """
        context: dict = {}
        if execution_id is not None:
            context["execution_id"] = execution_id
        if tool_id is not None:
            context["tool_id"] = tool_id
        if enhanced_retry_count is not None:
            context["enhanced_retry_count"] = enhanced_retry_count
        if error_signature is not None:
            context["error_signature"] = error_signature
        super().__init__(message=message, cause=cause, context=context)
