"""领域层 异常层次结构根类模块

定义领域异常层次结构根类 DomainError，仅使用 Python 标准库，
HTTP 状态码等 Web 层关注点由接口层异常处理器负责映射。
为避免与 Python 内置 Exception 命名冲突并遵循 pep8-naming 规范，根类命名为 DomainError。
"""

from __future__ import annotations

import re
from typing import Any

# URL query 参数中敏感字段脱敏正则（覆盖 api_key / api-key / token / apikey 等常见命名）
_REDACT_URL_PARAM_RE = re.compile(r"([?&](?:api[-_]?key|token|apikey|secret|password)=)([^&]+)", re.IGNORECASE)
_REDACT_URL_PARAM_REPLACEMENT = r"\1***REDACTED***"


def redact_url_sensitive_params(text: str) -> str:
    """脱敏任意文本中 URL 敏感 query 参数（?api_key=xxx → ?api_key=***REDACTED***）

    与 _redact_url_value 的差异：不要求整串以 http(s):// 开头——正则锚定
    [?&]param= 结构，对嵌入文本中的 URL 同样安全（用于事件 error_message 等
    自由文本通道，R2-2-C7/H7）。与 to_dict() 共用同一编译正则（脱敏策略 SSOT）。
    """
    return _REDACT_URL_PARAM_RE.sub(_REDACT_URL_PARAM_REPLACEMENT, text)


def _redact_url_value(value: Any) -> Any:
    """递归脱敏字典中所有 URL 字符串字段（移除 ?api_key=xxx 等敏感 query 参数）。

    Round 3 根因修复：BDD AC-5.1 验证发现 BaseException.to_dict() 此前直接输出 context.url 字段，
    若 url 含 ?api_key=xxx 则等于在异常 dict 中泄露 API Key。修复方案：递归遍历 dict，
    任何以 http(s):// 开头的字符串值都剥除 api_key/token/secret 等 query 参数。
    """
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return redact_url_sensitive_params(value)
        return value
    if isinstance(value, dict):
        return {k: _redact_url_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_url_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_url_value(item) for item in value)
    return value


class DomainError(Exception):
    """异常层次结构根类

    此基类定义在领域层，仅使用 Python 标准库。
    HTTP 状态码等 Web 层关注点不在此定义，由接口层异常处理器负责映射。

    注意：为避免遮蔽 Python 内置类型触发 Ruff N818 告警，
    领域根类命名为 DomainError。外部代码可通过以下两种方式引用：
    - from src.domain.exceptions.base_exceptions import DomainError（推荐）
    - from src.domain.exceptions.base_exceptions import BaseException（向后兼容别名）
    """

    code: str = "EXCEPTION_000"
    message: str = "Unknown error"
    cause: Exception | None = None
    context: dict = {}

    def __init__(
        self,
        message: str | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.cause = cause
        self.context = context or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典格式，便于序列化和日志记录。

        异常链路解析顺序（优先级递减）：
        1. self.cause — 显式 cause 参数（如 ToolChainExecutionFailedError(cause=e)）
        2. self.__cause__ — `raise X from Y` 设置的隐式 cause（PEP 3134）
        3. self.__context__ — 异常处理期间自动捕获的隐式 context

        升级原因：原实现仅读 self.cause，导致仅 `raise X from Y` 的异常链路
        在 to_dict() 输出中丢失，SRE 监控系统看不到根因编码。

        Round 3 根因修复：context 字段递归脱敏 URL 中 API Key 等敏感 query 参数
        （?api_key=xxx → ?api_key=***REDACTED***），防止异常 dict 序列化时泄露 Key。
        """
        result = {
            "code": self.code,
            "message": self.message,
            "context": _redact_url_value(self.context),
        }
        # 优先取显式 cause，降级到 __cause__（raise X from Y），最后 __context__
        cause_chain = self.cause or self.__cause__ or self.__context__
        if cause_chain:
            if isinstance(cause_chain, DomainError):
                result["cause"] = cause_chain.to_dict()
            else:
                result["cause"] = {
                    "type": type(cause_chain).__name__,
                    "message": str(cause_chain),
                }
        return result


# 向后兼容别名：旧代码可使用 BaseException 引用 DomainError
BaseException = DomainError

__all__ = ["DomainError", "BaseException", "redact_url_sensitive_params"]
