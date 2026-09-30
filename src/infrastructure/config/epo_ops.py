"""基础设施层 EPO OPS 数据源配置（Story 4.1f）

EPO Espacenet OPS（Open Patent Services）——欧洲专利局官方检索 API：
- 认证：OAuth2 client-credentials（Consumer Key/Secret 双凭据，非单 API Key）
- 免费配额：4 GB/周（响应数据量，官方 Fair Use Charter）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class EpoOpsConfig:
    """EPO OPS API 配置（5 变量：双凭据 + 通用三键）

    Attributes:
        consumer_key: OAuth2 Consumer Key（env: EPO_OPS_CONSUMER_KEY，repr 脱敏）
        consumer_secret: OAuth2 Consumer Secret（env: EPO_OPS_CONSUMER_SECRET，repr 脱敏）
        api_url: API 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（专利数据周更——7 天）
    """

    consumer_key: str = field(default="", repr=False)
    consumer_secret: str = field(default="", repr=False)
    api_url: str = "https://ops.epo.org"
    timeout: float = 30.0
    ttl_seconds: int = 604800

    @classmethod
    def from_env(cls) -> EpoOpsConfig:
        """从环境变量加载配置（EPO_OPS_CONSUMER_KEY 等 5 变量）

        Raises:
            ConfigurationError: 数值类型环境变量解析失败时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("EPO_OPS_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("EPO_OPS_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"EPO_OPS_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"EPO_OPS_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if timeout <= 0:
            raise ConfigurationError(message=f"EPO_OPS_TIMEOUT 必须为正数，当前值: {timeout}")
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"EPO_OPS_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            consumer_key=os.getenv("EPO_OPS_CONSUMER_KEY", ""),
            consumer_secret=os.getenv("EPO_OPS_CONSUMER_SECRET", ""),
            api_url=os.getenv("EPO_OPS_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["EpoOpsConfig"]
