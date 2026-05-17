"""SISYS 领域层会话状态存储协议模块

定义会话状态存储的接口，基础设施层负责实现（如 Redis 实现）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SessionStorage(Protocol):
    """会话状态存储协议接口

    所有方法均为异步方法，支持会话的增删查存在性检查
    """

    async def save(self, session_id: str, agent_id: str, state: dict, ttl: int = 86400) -> None:
        """保存会话状态

        Args:
            session_id: 会话唯一标识
            agent_id: Agent 唯一标识
            state: 会话状态数据
            ttl: 过期时间（秒）
        """

    async def load(self, session_id: str) -> dict | None:
        """加载会话状态

        Args:
            session_id: 会话唯一标识

        Returns:
            会话状态数据，如果不存在则返回 None
        """

    async def delete(self, session_id: str) -> None:
        """删除会话状态

        Args:
            session_id: 会话唯一标识
        """

    async def exists(self, session_id: str) -> bool:
        """检查会话状态是否存在

        Args:
            session_id: 会话唯一标识

        Returns:
            如果存在返回 True，否则返回 False
        """
