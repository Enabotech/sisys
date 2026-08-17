"""领域层 LLM 异常模块

LLM 调用专属异常，用于区分 API 传输层错误、响应格式错误和配置错误。
对标业界最佳实践，为 LLM 子系统分配独立异常编码，提升监控可观测性。

异常编码范围：EXCEPTION_330 ~ EXCEPTION_339（预留 10 个码）
- 330: LLM API 传输层错误（HTTP 4xx/5xx）
- 331: LLM 响应格式错误（JSON 解析、Schema 验证失败）
- 332: LLM 配置错误（API Key 缺失、endpoint 无效等）
- 333-339: 预留扩展位

设计理由（继承链选择）：
- LLMAPIError(330) 继承 ThirdPartyError：与 EmbeddingAPIError(306)→ThirdPartyError 一致，
  LLM API 返回错误响应本质是"第三方返回错误"
- LLMResponseError(331) 继承 ThirdPartyError：与 EmbeddingResponseError(307)→ThirdPartyError 一致，
  响应解析失败源于第三方返回格式异常
- LLMConfigError(332) 继承 ExternalException：与 EmbeddingModelError(308)→ExternalException 一致，
  LLM 配置是外部服务连接配置，非系统配置错误
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException, ThirdPartyError


class LLMAPIError(ThirdPartyError):
    """LLM API 传输层错误

    LLM API HTTP 调用返回非预期状态码（4xx/5xx）。
    继承 ThirdPartyError，HTTP 映射自动回退至 502 Bad Gateway。

    Attributes:
        code: EXCEPTION_330
        message: LLM API 错误描述
        model: 目标模型名称
        endpoint: API 端点（脱敏处理）
        status_code: HTTP 状态码
        response_body: 响应体摘要（截断至 200 字符）
    """

    code = "EXCEPTION_330"
    message = "LLM API error"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        model: str = "",
        endpoint: str = "",
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """初始化 LLM API 错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            model: 目标模型名称
            endpoint: API 端点（脱敏处理，不暴露完整 URL）
            status_code: HTTP 状态码
            response_body: 响应体摘要（截断至 200 字符）
        """
        ctx = dict(context or {})
        if model:
            ctx["model"] = model
        if status_code is not None:
            ctx["status_code"] = status_code
        # 消息安全性：脱敏 endpoint（仅保留 scheme 和 hostname）
        if endpoint:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(endpoint)
                safe_url = f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else ""
                if safe_url:
                    ctx["service_host"] = safe_url
            except (ValueError, AttributeError) as e:
                # URL 解析失败时不阻断上下文构建（消息安全性优先）
                ctx["service_host_error"] = str(e)[:100]
        # 消息安全性：截断 response_body 至 200 字符
        if response_body:
            truncated = response_body[:200]
            ctx["response_summary"] = truncated
        super().__init__(message=message, cause=cause, context=ctx)


class LLMResponseError(ThirdPartyError):
    """LLM 响应格式错误

    LLM 服务返回的响应结构不符合预期，包括：
    - JSON 解析失败
    - Pydantic Schema 验证失败
    - 响应字段缺失

    继承 ThirdPartyError，HTTP 映射自动回退至 502 Bad Gateway。

    Attributes:
        code: EXCEPTION_331
        message: LLM 响应格式错误描述
        model: 目标模型名称
        response_summary: 响应摘要（截断处理）
    """

    code = "EXCEPTION_331"
    message = "LLM response format error"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        model: str = "",
        response_summary: str = "",
    ) -> None:
        """初始化 LLM 响应格式错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            model: 目标模型名称
            response_summary: 响应摘要
        """
        ctx = dict(context or {})
        if model:
            ctx["model"] = model
        if response_summary:
            ctx["response_summary"] = response_summary
        super().__init__(message=message, cause=cause, context=ctx)


class LLMConfigError(ExternalException):
    """LLM 配置错误

    LLM 调用配置错误，包括：
    - API Key 缺失
    - endpoint 无效
    - 不支持的 api_type

    注意：此异常继承 ExternalException（而非 ThirdPartyError），
    与 EmbeddingModelError(308)→ExternalException 一致。
    HTTP 映射至 500 Internal Server Error。

    Attributes:
        code: EXCEPTION_332
        message: LLM 配置错误描述
        config_key: 配置项键名
    """

    code = "EXCEPTION_332"
    message = "LLM configuration error"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        config_key: str = "",
    ) -> None:
        """初始化 LLM 配置错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            config_key: 配置项键名
        """
        ctx = dict(context or {})
        if config_key:
            ctx["config_key"] = config_key
        super().__init__(message=message, cause=cause, context=ctx)


__all__ = [
    "LLMAPIError",
    "LLMResponseError",
    "LLMConfigError",
]
