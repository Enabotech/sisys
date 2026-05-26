"""领域层检查点快照实体模块

定义会话状态快照领域实体，用于中断恢复和时间旅行调试
遵循系统公理二（外部化记忆）：LLM 上下文 = 缓存，磁盘记忆 = 真相来源
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class CheckpointSnapshot:
    """会话状态快照领域实体

    创建后不可变。序列化/反序列化由基础设施层适配器负责

    Attributes:
        snapshot_id: Unique identifier for this snapshot
        session_id: Session this snapshot belongs to
        stage_id: Current execution stage (e.g., "planning", "execution")
        state_version: Version number for optimistic locking
        state_data: The actual state as key-value pairs
        timestamp: When this snapshot was created
        ttl_seconds: Time-to-live in seconds (24h-30d range: 86400-2592000)
    """

    snapshot_id: uuid.UUID = field(default_factory=uuid.uuid4)
    session_id: str = ""
    stage_id: str = ""
    state_version: int = 0
    state_data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = 86400  # Default 24 hours

    def with_updated_state(self, state_data: dict[str, Any], new_version: int | None = None) -> CheckpointSnapshot:
        """创建包含更新状态数据的新快照

        Args:
            state_data: 要合并的新状态数据
            new_version: 可选的新版本号（默认 state_version + 1）

        Returns:
            合并状态后的新 CheckpointSnapshot
        """
        merged_state = {**self.state_data, **state_data}
        return CheckpointSnapshot(
            snapshot_id=uuid.uuid4(),  # New snapshot ID
            session_id=self.session_id,
            stage_id=self.stage_id,
            state_version=new_version if new_version is not None else self.state_version + 1,
            state_data=merged_state,
            timestamp=datetime.now(UTC),
            ttl_seconds=self.ttl_seconds,
        )
