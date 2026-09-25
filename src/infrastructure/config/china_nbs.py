"""基础设施层中国国家统计局数据源配置（Story 4.1b）

中国国家统计局（经 crawler 插件采集，PoC v2 验证直连 HTTP 403 反爬拒绝）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChinaNBSConfig:
    """中国国家统计局数据源配置

    Attributes:
        base_url: 国家局站点基础地址
        domain: 爬取域名白名单（限定 stats.gov.cn）
        poll_interval_sec: 任务状态轮询间隔（默认 2s）
        poll_timeout_sec: 轮询总超时（默认 300s）
        ttl_seconds: 缓存 TTL（月度/季度统计数据，默认 1 天）
    """

    base_url: str = "https://www.stats.gov.cn"
    domain: str = "www.stats.gov.cn"
    poll_interval_sec: float = 2.0
    poll_timeout_sec: float = 300.0
    ttl_seconds: int = 86400

    @classmethod
    def from_env(cls) -> ChinaNBSConfig:
        """从环境变量加载配置"""
        return cls(
            base_url=os.getenv("CHINA_NBS_BASE_URL", cls.base_url),
            domain=os.getenv("CHINA_NBS_DOMAIN", cls.domain),
            poll_interval_sec=float(os.getenv("CHINA_NBS_POLL_INTERVAL_SEC", str(cls.poll_interval_sec))),
            poll_timeout_sec=float(os.getenv("CHINA_NBS_POLL_TIMEOUT_SEC", str(cls.poll_timeout_sec))),
            ttl_seconds=int(os.getenv("CHINA_NBS_TTL_SECONDS", str(cls.ttl_seconds))),
        )


__all__ = ["ChinaNBSConfig"]
