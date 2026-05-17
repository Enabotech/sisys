"""SISYS 领域层 Token 黑名单仓储端口模块。

领域层接口，定义 Token 黑名单数据访问的契约。
遵循六边形架构：领域层零依赖，仅使用标准库。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenBlacklistPort(Protocol):
    """Token 黑名单仓储端口（领域层定义，仅使用标准库）

    负责存储已撤销的 JWT token。
    """

    async def add(self, token: str) -> None:
        """将 token 加入黑名单。

        Args:
            token: JWT token 字符串
        """

    async def is_blacklisted(self, token: str) -> bool:
        """检查 token 是否在黑名单中。

        Args:
            token: JWT token 字符串

        Returns:
            True 如果 token 已被撤销
        """
