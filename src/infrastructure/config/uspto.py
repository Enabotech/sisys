"""基础设施层 USPTO 数据源配置（Story 4.1b）

USPTO PatentsView API（专利数据库，公开免费，无需 API Key）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


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
        """从环境变量加载配置"""
        return cls(
            api_url=os.getenv("USPTO_API_URL", cls.api_url),
            timeout=float(os.getenv("USPTO_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("USPTO_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["USPTOConfig"]
