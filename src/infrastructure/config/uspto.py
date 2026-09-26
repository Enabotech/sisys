"""基础设施层 USPTO 数据源配置（Story 4.1b）

USPTO PatentsView API（专利数据库，公开免费，无需 API Key）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class USPTOConfig:
    """USPTO PatentsView API 配置

    Attributes:
        api_url: API 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（专利数据低频更新，默认 30 天上界内）
    """

    api_url: str = "https://search.patentsview.org"
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
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"USPTO_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"USPTO_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        return cls(
            api_url=os.getenv("USPTO_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["USPTOConfig"]
