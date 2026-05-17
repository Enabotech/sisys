"""SISYS 基础设施层外部 API 白名单服务模块。

基于 WhitelistServicePort 接口实现外部 API 白名单的管理和验证。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist
from src.domain.ports.whitelist_service import WhitelistServicePort

if TYPE_CHECKING:
    pass


class WhitelistServiceImpl(WhitelistServicePort):
    """外部 API 白名单服务实现，管理 API 白名单并验证调用合规性。

    Attributes:
        _whitelist: 内存中存储的白名单字典，键为 API 端点
    """

    def __init__(self) -> None:
        """初始化白名单服务."""
        self._whitelist: dict[str, ExternalAPIWhitelist] = {}

    def is_allowed(self, api_endpoint: str) -> bool:
        """检查 API 端点是否在白名单中且有效。

        Args:
            api_endpoint: API 端点

        Returns:
            True 如果在白名单中且未过期
        """
        entry = self._whitelist.get(api_endpoint)
        if entry is None:
            return False
        return entry.is_valid()

    def add_to_whitelist(self, api: ExternalAPIWhitelist) -> None:
        """添加 API 到白名单。

        Args:
            api: 外部 API 白名单条目
        """
        self._whitelist[api.endpoint] = api

    def get_whitelist_entry(self, api_endpoint: str) -> ExternalAPIWhitelist | None:
        """获取白名单条目。

        Args:
            api_endpoint: API 端点

        Returns:
            白名单条目，如果不存在则返回 None
        """
        return self._whitelist.get(api_endpoint)

    def remove_from_whitelist(self, api_endpoint: str) -> bool:
        """从白名单移除 API。

        Args:
            api_endpoint: API 端点

        Returns:
            True 如果成功移除
        """
        if api_endpoint in self._whitelist:
            del self._whitelist[api_endpoint]
            return True
        return False

    def list_all_endpoints(self) -> list[str]:
        """列出所有白名单中的端点。

        Returns:
            端点列表
        """
        return list(self._whitelist.keys())
