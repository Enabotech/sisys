"""SISYS 领域层哈希路由协议模块。

定义基于哈希的路由适配器接口协议。
基础设施层实现此协议以完成一致性会话路由。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HashRouterProtocol(Protocol):
    """哈希路由协议（由基础设施层实现）。

    基于 session_id 哈希进行会话路由，
    确保会话到节点的一致性映射。
    """

    def route(self, session_id: str) -> str:
        """基于 session_id 哈希进行路由。

        Args:
            session_id: 会话标识符

        Returns:
            目标节点/代理 ID
        """
        ...
