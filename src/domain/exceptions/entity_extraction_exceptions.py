"""领域层实体抽取异常模块

实体抽取专属异常，继承 ExternalException。
异常编码范围：EXCEPTION_340 ~ EXCEPTION_349（预留 10 个码）

设计理由（继承链选择）：
- EntityExtractionError(340) 继承 ExternalException：与 LLMConfigError(332)→ExternalException 一致，
  实体抽取属于外部抽取服务异常（规则引擎/LLM 调用/仲裁异常）
- HTTP 映射至 500 Internal Server Error（服务端处理失败）
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class EntityExtractionError(ExternalException):
    """实体抽取错误

    实体抽取过程中发生的不可恢复错误，包括：
    - 规则引擎初始化失败
    - LLM 调用异常（非透明降级场景）
    - 冲突仲裁失败
    - Neo4j 持久化失败

    继承 ExternalException，HTTP 映射至 500 Internal Server Error。

    Attributes:
        code: EXCEPTION_340
        message: 实体抽取错误描述
        content_preview: 内容预览（截断至 200 字符）
        extraction_strategy: 抽取策略（"rule" / "llm" / "hybrid"）
        entity_count: 已抽取实体数量
    """

    code = "EXCEPTION_340"
    message = "Entity extraction error"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        content_preview: str = "",
        extraction_strategy: str = "",
        entity_count: int = 0,
    ) -> None:
        """初始化实体抽取错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            content_preview: 内容预览（截断至 200 字符）
            extraction_strategy: 抽取策略
            entity_count: 已抽取实体数量
        """
        ctx = dict(context or {})
        # 消息安全性：截断 content_preview 至 200 字符
        if content_preview:
            truncated = content_preview[:200]
            ctx["content_preview"] = truncated
            ctx["content_preview_truncated"] = len(content_preview) > 200
        if extraction_strategy:
            ctx["extraction_strategy"] = extraction_strategy
        ctx["entity_count"] = entity_count
        super().__init__(message=message, cause=cause, context=ctx)


__all__ = [
    "EntityExtractionError",
]
