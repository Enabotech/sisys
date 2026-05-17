"""SISYS 领域层检查点快照仓储协议模块

定义检查点快照存储适配器的接口协议，基础设施层负责持久化实现

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot


@runtime_checkable
class SnapshotRepositoryProtocol(Protocol):
    """快照存储协议端口，由基础设施层实现

    定义保存、加载、删除检查点快照的接口，用于会话状态恢复
    """

    async def save(self, snapshot: CheckpointSnapshot) -> None:
        """保存快照到存储

        Args:
            snapshot: 待持久化的检查点快照
        """
        ...

    async def load(self, session_id: str) -> CheckpointSnapshot | None:
        """加载会话的最新快照

        Args:
            session_id: 会话标识

        Returns:
            最新快照，不存在则返回 None
        """
        ...

    async def delete(self, session_id: str) -> None:
        """删除会话的快照

        Args:
            session_id: 会话标识
        """
        ...
