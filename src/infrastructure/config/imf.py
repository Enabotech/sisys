"""基础设施层 IMF 数据源配置（Story 4.1b）

IMF DataMapper API（World Economic Outlook 指标，公开免费）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class IMFConfig:
    """IMF DataMapper API 配置

    Attributes:
        api_url: API 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（WEO 半年度发布，默认 7 天）
    """

    api_url: str = "https://www.imf.org/external/datamapper/api/v1"
    timeout: float = 30.0
    ttl_seconds: int = 604800

    @classmethod
    def from_env(cls) -> IMFConfig:
        """从环境变量加载配置"""
        return cls(
            api_url=os.getenv("IMF_API_URL", cls.api_url),
            timeout=float(os.getenv("IMF_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("IMF_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["IMFConfig"]
