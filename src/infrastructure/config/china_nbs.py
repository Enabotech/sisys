"""基础设施层中国国家统计局数据源配置（Story 4.1b）

中国国家统计局（经 crawler 插件采集，PoC v2 验证直连 HTTP 403 反爬拒绝）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


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
        """从环境变量加载配置

        Raises:
            ConfigurationError: 数值类型环境变量解析失败时（禁止 ValueError 透传）
        """
        interval_raw = os.getenv("CHINA_NBS_POLL_INTERVAL_SEC", str(cls.poll_interval_sec))
        timeout_raw = os.getenv("CHINA_NBS_POLL_TIMEOUT_SEC", str(cls.poll_timeout_sec))
        ttl_raw = os.getenv("CHINA_NBS_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            poll_interval_sec = float(interval_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"CHINA_NBS_POLL_INTERVAL_SEC 值非法: {interval_raw!r}") from None
        try:
            poll_timeout_sec = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"CHINA_NBS_POLL_TIMEOUT_SEC 值非法: {timeout_raw!r}") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"CHINA_NBS_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if poll_interval_sec <= 0:
            raise ConfigurationError(message=f"CHINA_NBS_POLL_INTERVAL_SEC 必须为正数，当前值: {poll_interval_sec}")
        if poll_timeout_sec <= 0:
            raise ConfigurationError(message=f"CHINA_NBS_POLL_TIMEOUT_SEC 必须为正数，当前值: {poll_timeout_sec}")
        if poll_interval_sec >= poll_timeout_sec:
            raise ConfigurationError(
                message=(
                    f"CHINA_NBS_POLL_INTERVAL_SEC({poll_interval_sec}) 必须小于 "
                    f"POLL_TIMEOUT_SEC({poll_timeout_sec})（否则首轮即超时）"
                )
            )
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"CHINA_NBS_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            base_url=os.getenv("CHINA_NBS_BASE_URL", cls.base_url),
            domain=os.getenv("CHINA_NBS_DOMAIN", cls.domain),
            poll_interval_sec=poll_interval_sec,
            poll_timeout_sec=poll_timeout_sec,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["ChinaNBSConfig"]
