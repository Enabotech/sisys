"""WhitelistServicePort — Interface for external API whitelist service.

遵循六边形架构：端口接口定义，仅依赖 ABC 和 Python 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist


class WhitelistServicePort(ABC):
    """外部 API 白名单服务端口（抽象接口）."""

    @abstractmethod
    def is_allowed(self, api_endpoint: str) -> bool:
        """检查 API 端点是否在白名单中且有效。

        Args:
            api_endpoint: API 端点

        Returns:
            True 如果在白名单中且未过期
        """
        ...

    @abstractmethod
    def add_to_whitelist(self, api: ExternalAPIWhitelist) -> None:
        """添加 API 到白名单。

        Args:
            api: 外部 API 白名单条目
        """
        ...
