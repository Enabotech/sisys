"""基础设施层巨潮资讯数据源配置（Story 4.1f Task 10——D-10 范围扩展）

巨潮资讯网（cninfo——证监会指定上市公司法定信息披露网站）：
- 免 key（无条件注册——A 组范式，EDGAR 同款「官方免费通道可达即注册」逻辑）
- 两段式检索：topSearch 公司匹配（keyword → code/orgId）→ hisAnnouncement 公告查询
- 使用边界：公告元数据 + PDF 内部分析引用、不再分发（预筛法务确认自限口径）
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass(frozen=True)
class CninfoConfig:
    """巨潮资讯数据源配置（3 变量——无任何 Key）

    Attributes:
        api_url: 巨潮资讯基础地址（www.cninfo.com.cn）
        timeout: 请求超时秒数
        ttl_seconds: 缓存 TTL（公告日/周频——7 天保守值）
    """

    api_url: str = "https://www.cninfo.com.cn"
    timeout: float = 30.0
    ttl_seconds: int = 604800

    @classmethod
    def from_env(cls) -> CninfoConfig:
        """从环境变量加载配置（CNINFO_API_URL / CNINFO_TIMEOUT / CNINFO_TTL_SECONDS）

        Raises:
            ConfigurationError: 数值类型环境变量解析失败或非正数时（禁止 ValueError 透传）
        """
        timeout_raw = os.getenv("CNINFO_TIMEOUT", str(cls.timeout))
        ttl_raw = os.getenv("CNINFO_TTL_SECONDS", str(cls.ttl_seconds))
        try:
            timeout = float(timeout_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"CNINFO_TIMEOUT 值非法: {timeout_raw!r}（需要数值）") from None
        try:
            ttl_seconds = int(ttl_raw)
        except (ValueError, TypeError):
            raise ConfigurationError(message=f"CNINFO_TTL_SECONDS 值非法: {ttl_raw!r}（需要整数）") from None
        if timeout <= 0:
            raise ConfigurationError(message=f"CNINFO_TIMEOUT 必须为正数，当前值: {timeout}")
        if ttl_seconds <= 0:
            raise ConfigurationError(message=f"CNINFO_TTL_SECONDS 必须为正整数，当前值: {ttl_seconds}")
        return cls(
            api_url=os.getenv("CNINFO_API_URL", cls.api_url),
            timeout=timeout,
            ttl_seconds=ttl_seconds,
        )


__all__ = ["CninfoConfig"]
