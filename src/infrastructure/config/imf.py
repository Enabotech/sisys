"""基础设施层 IMF 数据源配置（Story 4.1b）

IMF DataMapper API（World Economic Outlook 指标，公开免费）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


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
        """从环境变量加载配置

        Raises:
            ConfigurationError: 数值类型环境变量解析失败时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("IMF_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("IMF_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"IMF_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"IMF_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        return cls(
            api_url=os.getenv("IMF_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["IMFConfig"]
