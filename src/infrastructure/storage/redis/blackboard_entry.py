"""基础设施层黑板条目数据模型模块

定义公共黑板的存储实体结构

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class BlackboardEntry:
    """黑板条目数据模型

    Attributes:
        conversation_id: 会话唯一标识
        agent_id: Agent 唯一标识
        content: 内容数据
        confidence: 置信度（0.0-1.0）
        citations: 引用来源列表
        timestamp: 时间戳
        version: 版本号（用于 MVCC）
    """

    conversation_id: str
    agent_id: str
    content: dict
    confidence: float = 1.0
    citations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 1

    def to_dict(self) -> dict:
        """序列化为字典

        Returns:
            包含黑板条目字段的字典
        """
        return {
            "conversation_id": self.conversation_id,
            "agent_id": self.agent_id,
            "content": self.content,
            "confidence": self.confidence,
            "citations": self.citations,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BlackboardEntry:
        """从字典反序列化

        Args:
            data: 包含黑板条目字段的字典

        Returns:
            BlackboardEntry 实例
        """
        return cls(
            conversation_id=data["conversation_id"],
            agent_id=data["agent_id"],
            content=data["content"],
            confidence=data.get("confidence", 1.0),
            citations=data.get("citations", []),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if isinstance(data.get("timestamp"), str)
                else data.get("timestamp", datetime.now(UTC))
            ),
            version=data.get("version", 1),
        )
