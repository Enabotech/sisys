"""基础设施层 NewsAPI 数据源配置（Story 4.1b）

NewsAPI（实时新闻流，替代 Reuters Connect 付费 API；免费档 100 次/天，需 API Key）。
安全约束：api_key 字段 field(repr=False) 脱敏。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class NewsAPIConfig:
    """NewsAPI 配置

    Attributes:
        api_key: API 密钥（env: NEWSAPI_API_KEY，repr 脱敏）
        api_url: API 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（新闻时效性高，默认 6 小时）
    """

    api_key: str = field(default="", repr=False)
    api_url: str = "https://newsapi.org"
    timeout: float = 30.0
    ttl_seconds: int = 21600

    @classmethod
    def from_env(cls) -> NewsAPIConfig:
        """从环境变量加载配置（NEWSAPI_API_KEY 等）"""
        return cls(
            api_key=os.getenv("NEWSAPI_API_KEY", ""),
            api_url=os.getenv("NEWSAPI_API_URL", cls.api_url),
            timeout=float(os.getenv("NEWSAPI_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("NEWSAPI_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["NewsAPIConfig"]
