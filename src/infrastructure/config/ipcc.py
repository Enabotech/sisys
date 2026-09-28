"""基础设施层 IPCC 数据源配置（Story 4.1b）

IPCC 环境数据（CSV 下载为主，公开免费，无需 API Key）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


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
    max_bytes: int = 10_485_760  # 响应体大小上限（默认 10 MiB，流式超限拒绝——R2-2-B2 无界读取修复）

    @classmethod
    def from_env(cls) -> IPCCConfig:
        """从环境变量加载配置

        Raises:
            ConfigurationError: 数值类型环境变量解析失败或范围非法时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("IPCC_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("IPCC_TTL_SECONDS", str(cls.ttl_seconds))
        max_bytes_raw = os.getenv("IPCC_MAX_BYTES", str(cls.max_bytes))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"IPCC_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"IPCC_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        try:
            max_bytes = int(max_bytes_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"IPCC_MAX_BYTES 值非法: {max_bytes_raw!r}（需要整数）") from None
        if max_bytes <= 0:
            raise ConfigurationError(message=f"IPCC_MAX_BYTES 必须为正整数，当前值: {max_bytes}")
        if timeout <= 0:
            raise ConfigurationError(message=f"IPCC_TIMEOUT 必须为正数，当前值: {timeout}")
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"IPCC_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            csv_base_url=os.getenv("IPCC_CSV_BASE_URL", cls.csv_base_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
            max_bytes=max_bytes,
        )


__all__ = ["IPCCConfig"]
