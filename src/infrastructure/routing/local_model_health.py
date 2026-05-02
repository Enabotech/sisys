"""Local model health check for Ollama.

.. deprecated::
    此类已被 :class:`OllamaHealthAdapter` 取代。
    请使用 OllamaHealthAdapter 获取异步健康检查能力。
"""

from __future__ import annotations

import warnings

# 向后兼容导入
from src.infrastructure.routing.ollama_health_adapter import (
    DEFAULT_OLLAMA_ENDPOINT,
    LocalModelHealth,
    OllamaHealthAdapter,
    _get_session,
)

# 保留旧版 global session 用于向后兼容
_session = None

__all__ = [
    "OllamaHealthAdapter",
    "LocalModelHealth",
    "_get_session",
    "DEFAULT_OLLAMA_ENDPOINT",
]


def __getattr__(name: str):
    """支持旧代码直接导入 LocalModelHealth 类。"""
    if name == "LocalModelHealth":
        warnings.warn(
            "LocalModelHealth is deprecated, use OllamaHealthAdapter instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return OllamaHealthAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
