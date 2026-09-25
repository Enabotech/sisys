"""基础设施层 World Bank 数据源配置（Story 4.1b）

dataclass + from_env() 模式（对齐 EmbeddingConfig/RedisConfig 惯例）。
World Bank API 公开免费，无需 API Key。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WorldBankConfig:
    """World Bank API 配置

    Attributes:
        api_url: API 基础地址（默认 v2 REST）
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（年度统计数据，默认 7 天）
    """

    api_url: str = "https://api.worldbank.org/v2"
    timeout: float = 30.0
    ttl_seconds: int = 604800

    @classmethod
    def from_env(cls) -> WorldBankConfig:
        """从环境变量加载配置（WORLDBANK_API_URL / WORLDBANK_TIMEOUT / WORLDBANK_TTL_SECONDS）"""
        return cls(
            api_url=os.getenv("WORLDBANK_API_URL", cls.api_url),
            timeout=float(os.getenv("WORLDBANK_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("WORLDBANK_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["WorldBankConfig"]
