"""基础设施层 Tavily 数据源配置（Story 4.1b）

Tavily Search API（Web 搜索 + 新闻聚合，需 API Key）。
安全约束：api_key 字段 field(repr=False) 脱敏（参考 RedisConfig.__repr__ 脱敏先例）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TavilyConfig:
    """Tavily API 配置

    Attributes:
        api_key: API 密钥（env: TAVILY_API_KEY，repr 脱敏）
        api_url: API 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（搜索结果时效性中等，默认 1 天）
    """

    api_key: str = field(default="", repr=False)
    api_url: str = "https://api.tavily.com"
    timeout: float = 30.0
    ttl_seconds: int = 86400

    @classmethod
    def from_env(cls) -> TavilyConfig:
        """从环境变量加载配置（TAVILY_API_KEY 等）"""
        return cls(
            api_key=os.getenv("TAVILY_API_KEY", ""),
            api_url=os.getenv("TAVILY_API_URL", cls.api_url),
            timeout=float(os.getenv("TAVILY_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("TAVILY_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["TavilyConfig"]
