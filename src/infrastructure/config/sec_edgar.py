"""基础设施层 SEC EDGAR 数据源配置（Story 4.1f）

SEC EDGAR（美国证监会法定披露系统）：
- 免 key（无条件注册）——强制 UA 头（官方 Fair Access：「公司名 邮箱」格式）+ 10 req/s 限速
- 双端点：efts.sec.gov（全文检索）/ data.sec.gov（XBRL 结构化数据）
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class SecEdgarConfig:
    """SEC EDGAR API 配置（3 变量——无任何 Key）

    Attributes:
        api_url: 全文检索基础地址（efts）
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（财报月/季频——30 天）
    """

    api_url: str = "https://efts.sec.gov"
    timeout: float = 30.0
    ttl_seconds: int = 2592000

    @classmethod
    def from_env(cls) -> SecEdgarConfig:
        """从环境变量加载配置（SEC_EDGAR_API_URL 等 3 变量）

        Raises:
            ConfigurationError: 数值类型环境变量解析失败时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("SEC_EDGAR_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("SEC_EDGAR_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"SEC_EDGAR_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"SEC_EDGAR_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if timeout <= 0:
            raise ConfigurationError(message=f"SEC_EDGAR_TIMEOUT 必须为正数，当前值: {timeout}")
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"SEC_EDGAR_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            api_url=os.getenv("SEC_EDGAR_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["SecEdgarConfig"]
