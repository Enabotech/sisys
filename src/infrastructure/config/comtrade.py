"""基础设施层 UN Comtrade 数据源配置（Story 4.1f）

UN Comtrade API（联合国官方贸易统计，Azure APIM 前置）：
- key 可选：preview 端点免 key 兜底（低配额）；有 key 加 Ocp-Apim-Subscription-Key
  头提升至 500 次/天（无条件注册——「官方免费通道可达即注册，key 为增强」）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class ComtradeConfig:
    """UN Comtrade API 配置（4 变量——key 可选，缺失缺省空串走 preview 裸模式）

    Attributes:
        api_key: 订阅密钥（env: COMTRADE_API_KEY，repr 脱敏；空串 = 无 key 模式）
        api_url: API 基础地址
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（贸易数据周/月频——7 天保守值）
    """

    api_key: str = field(default="", repr=False)
    api_url: str = "https://comtradeapi.un.org"
    timeout: float = 30.0
    ttl_seconds: int = 604800

    @classmethod
    def from_env(cls) -> ComtradeConfig:
        """从环境变量加载配置（COMTRADE_API_KEY 等 4 变量）。

        key 缺失语义：缺省空串 = 无 key 走 preview 裸模式（构造器不抛——与
        newsapi/tavily 条件注册形态不同，见 Story 决策 D5）。

        Raises:
            ConfigurationError: 数值类型环境变量解析失败时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("COMTRADE_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("COMTRADE_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"COMTRADE_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"COMTRADE_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if timeout <= 0:
            raise ConfigurationError(message=f"COMTRADE_TIMEOUT 必须为正数，当前值: {timeout}")
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"COMTRADE_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            api_key=os.getenv("COMTRADE_API_KEY", ""),
            api_url=os.getenv("COMTRADE_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["ComtradeConfig"]
