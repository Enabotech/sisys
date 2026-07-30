"""领域层 OCR 异常模块

OCR 子域专属异常，用于区分 OCR 服务连接错误和处理错误。
对标业界最佳实践，为 OCR 子系统分配独立异常编码，提升监控可观测性和故障定位效率。

异常编码范围：EXCEPTION_320 ~ EXCEPTION_329（预留 10 个码）
- 320: OCR 连接错误（PaddleOCR-VL 服务不可达/连接超时）
- 321: OCR 处理错误（PaddleOCR-VL 返回错误/响应解析失败）
- 322-329: 预留扩展位

设计理由（继承链选择）：
OCRConnectionError 和 OCRProcessingError 均直接继承 ExternalException（而非 ThirdPartyError），
原因如下：
- OCRConnectionError(320)→504 与 TimeoutError(302)→504 同属"上游未响应"类别，
  但 TimeoutError 是通用超时（ExternalException 子类），OCRConnectionError 是 OCR 专用连接错误
- EmbeddingAPIError 继承 ThirdPartyError（默认 502）是因为 embedding 服务的所有错误
  本质都是"第三方返回错误响应"，而 OCR 的错误类型需要区分"连接不可达（504）"和
  "处理错误（502）"两种语义
- 直接继承 ExternalException 并通过 HTTP 映射显式区分 504/502 是最清晰的设计，
  与 sandbox 子域（SandboxError 直接继承 ExternalException，映射到 502）模式一致
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class OCRConnectionError(ExternalException):
    """OCR 连接错误

    PaddleOCR-VL 服务不可达或连接超时。
    继承 ExternalException，HTTP 映射至 504 Gateway Timeout。

    Attributes:
        code: EXCEPTION_320
        message: OCR 连接错误描述
        service_url: 目标服务 URL（脱敏处理，不暴露完整 URL）
    """

    code = "EXCEPTION_320"
    message = "OCR 连接失败"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        service_url: str = "",
    ) -> None:
        """初始化 OCR 连接错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            service_url: 目标服务 URL（仅用于日志，不暴露给外部响应）
        """
        # 消息安全性：不泄露完整 URL
        safe_url = ""
        if service_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(service_url)
                safe_url = f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else ""
            except Exception:
                safe_url = ""
        context = dict(context or {})
        if safe_url:
            context["service_host"] = safe_url
        super().__init__(message=message, cause=cause, context=context)


class OCRProcessingError(ExternalException):
    """OCR 处理错误

    PaddleOCR-VL 返回错误响应或响应解析失败。
    继承 ExternalException，HTTP 映射至 502 Bad Gateway。

    Attributes:
        code: EXCEPTION_321
        message: OCR 处理错误描述
        service_url: 目标服务 URL（脱敏处理，不暴露完整 URL）
        status_code: HTTP 状态码（如有）
    """

    code = "EXCEPTION_321"
    message = "OCR 处理失败"

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
        service_url: str = "",
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """初始化 OCR 处理错误

        Args:
            message: 错误描述
            cause: 原始异常
            context: 错误上下文
            service_url: 目标服务 URL（仅用于日志，不暴露给外部响应）
            status_code: HTTP 状态码
            response_body: 响应体摘要（截断至 200 字符，不泄露完整响应内容）
        """
        safe_url = ""
        if service_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(service_url)
                safe_url = f"{parsed.scheme}://{parsed.hostname}" if parsed.hostname else ""
            except Exception:
                safe_url = ""
        ctx = dict(context or {})
        if safe_url:
            ctx["service_host"] = safe_url
        if status_code is not None:
            ctx["status_code"] = status_code
        # 消息安全性：截断至 200 字符，不暴露完整响应体
        if response_body:
            truncated = response_body[:200]
            ctx["response_summary"] = truncated
        super().__init__(message=message, cause=cause, context=ctx)


__all__ = [
    "OCRConnectionError",
    "OCRProcessingError",
]