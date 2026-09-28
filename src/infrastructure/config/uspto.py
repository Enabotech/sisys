"""基础设施层 USPTO 数据源配置（Story 4.1b）

USPTO PatentsView API（专利数据库，v1 端点强制 API Key 鉴权——
v0 旧端点「公开免费」的结论已过期，R3-P1-3 修正）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class USPTOConfig:
    """USPTO PatentsView API 配置

    Attributes:
        api_url: API 基础地址
        api_key: PatentsView API Key（env USPTO_API_KEY；空串/None 视为未配置，
            组合根将跳过该适配器注册——对齐 newsapi/tavily 既有模式）
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（专利数据低频更新，默认 30 天上界内）
    """

    api_url: str = "https://search.patentsview.org"
    api_key: str | None = field(default=None, repr=False)
    timeout: float = 30.0
    ttl_seconds: int = 2592000

    @classmethod
    def from_env(cls) -> USPTOConfig:
        """从环境变量加载配置

        Raises:
            ConfigurationError: 数值类型环境变量解析失败时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("USPTO_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("USPTO_TTL_SECONDS", str(cls.ttl_seconds))
        api_key_raw = os.getenv("USPTO_API_KEY")
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"USPTO_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"USPTO_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if timeout <= 0:
            raise ConfigurationError(message=f"USPTO_TIMEOUT 必须为正数，当前值: {timeout}")
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"USPTO_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            api_url=os.getenv("USPTO_API_URL", cls.api_url),
            api_key=api_key_raw or None,
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["USPTOConfig"]
