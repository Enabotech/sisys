"""基础设施层 IPCC 数据源配置（Story 4.1b）

IPCC 环境数据（CSV 下载为主，公开免费，无需 API Key）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class IPCCConfig:
    """IPCC 数据源配置

    Attributes:
        csv_base_url: CSV 文件基础地址（query 为相对路径键）
        timeout: 请求超时秒数（大文件下载放宽）
        ttl_seconds: 缓存 TTL（报告类静态数据，默认 30 天上界）
    """

    csv_base_url: str = "https://www.ipcc.ch/data"
    timeout: float = 60.0
    ttl_seconds: int = 2592000

    @classmethod
    def from_env(cls) -> IPCCConfig:
        """从环境变量加载配置"""
        return cls(
            csv_base_url=os.getenv("IPCC_CSV_BASE_URL", cls.csv_base_url),
            timeout=float(os.getenv("IPCC_TIMEOUT", str(cls.timeout))),
            ttl_seconds=int(os.getenv("IPCC_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["IPCCConfig"]
