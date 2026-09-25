"""基础设施层 Eurostat 数据源配置（Story 4.1b）

Eurostat SDMX REST API（欧盟 27 国 + EFTA，公开免费，PoC v1 验证可用）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EurostatConfig:
    """Eurostat API 配置

    Attributes:
        api_url: SDMX REST 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（季度/年度统计数据，默认 7 天）
    """

    api_url: str = "https://ec.europa.eu/eurostat/api/dissemination"
    timeout: float = 30.0
    ttl_seconds: int = 604800

    @classmethod
    def from_env(cls) -> EurostatConfig:
        """从环境变量加载配置"""
        return cls(
            api_url=os.getenv("EUROSTAT_API_URL", cls.api_url),
            timeout=float(os.getenv("EUROSTAT_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("EUROSTAT_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["EurostatConfig"]
