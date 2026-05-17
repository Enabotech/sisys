"""Session state data model.

SessionState is a cache storage structure in the infrastructure layer (consistent with OutboxEntity).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SessionState:
    """会话状态缓存数据模型

    Attributes:
        session_id: 会话唯一标识
        agent_id: Agent 唯一标识
        state: 会话状态数据（字典）
        created_at: 创建时间
        updated_at: 更新时间
        ttl: 过期时间（秒）
    """

    session_id: str
    agent_id: str
    state: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl: int = 86400  # 默认 24 小时

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionState:
        """从字典反序列化

        Args:
            data: 包含会话状态字段的字典

        Returns:
            SessionState 实例
        """
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            state=data.get("state", {}),
            created_at=datetime.fromisoformat(data["created_at"])
            if isinstance(data.get("created_at"), str)
            else data.get("created_at", datetime.now(UTC)),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if isinstance(data.get("updated_at"), str)
            else data.get("updated_at", datetime.now(UTC)),
            ttl=data.get("ttl", 86400),
        )
