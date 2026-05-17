"""OutboxEntity — 基础设施层定义

位于基础设施层，领域层不导入此模块
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidStateTransitionError

# 重新导出，保持向后兼容
__all__ = ["InvalidStateTransitionError", "OutboxEntity"]


@dataclass
class OutboxEntity:
    """事务发件箱实体（基础设施层）

    对应 PostgreSQL event_outbox 表
    状态机: pending → published/failed, failed → pending(重试)/archived(终态)
    """

    id: int = field(default=0, init=False)
    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = field(default=None)
    retry_count: int = 0
    max_retries: int = 3
    error_message: str | None = field(default=None)

    def mark_published(self) -> None:
        """标记为已发布。"""
        if self.status != "pending":
            raise InvalidStateTransitionError(self.status, "published")
        self.status = "published"
        self.published_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """标记为失败，递增 retry_count。"""
        if self.status not in ("pending", "failed"):
            raise InvalidStateTransitionError(self.status, "failed")
        self.status = "failed"
        self.retry_count += 1
        self.error_message = error

    def mark_pending(self) -> None:
        """重置为 pending（用于重试）。"""
        if self.status != "failed":
            raise InvalidStateTransitionError(self.status, "pending")
        if self.retry_count >= self.max_retries:
            raise InvalidStateTransitionError(self.status, "pending", f"Max retries ({self.max_retries}) exceeded")
        self.status = "pending"
        self.error_message = None

    def mark_archived(self) -> None:
        """归档（终态，不可逆）。"""
        if self.status != "failed":
            raise InvalidStateTransitionError(self.status, "archived")
        self.status = "archived"
