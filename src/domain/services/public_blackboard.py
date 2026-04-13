"""PublicBlackboard Protocol — 领域层定义。

定义公共黑板的接口，基础设施层负责实现（如 Redis 实现）。
支持多 Agent 之间的信息共享和协作。
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol


class PublicBlackboard(Protocol):
    """公共黑板协议接口。

    支持多 Agent 在会话中发布和读取共享信息。
    """

    @abstractmethod
    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict,
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """发布内容到黑板。

        Args:
            conversation_id: 会话唯一标识
            agent_id: Agent 唯一标识
            content: 内容数据
            confidence: 置信度（0.0-1.0）
            citations: 引用来源列表

        Returns:
            版本号
        """

    @abstractmethod
    async def get(self, conversation_id: str) -> list[dict]:
        """获取会话的所有内容。

        Args:
            conversation_id: 会话唯一标识

        Returns:
            内容列表
        """

    @abstractmethod
    async def get_by_agent(self, conversation_id: str, agent_id: str) -> dict | None:
        """获取指定 Agent 的最新内容。

        Args:
            conversation_id: 会话唯一标识
            agent_id: Agent 唯一标识

        Returns:
            内容数据，如果不存在则返回 None
        """

    @abstractmethod
    async def get_latest(self, conversation_id: str) -> dict | None:
        """获取会话的最新内容。

        Args:
            conversation_id: 会话唯一标识

        Returns:
            最新内容数据，如果不存在则返回 None
        """
