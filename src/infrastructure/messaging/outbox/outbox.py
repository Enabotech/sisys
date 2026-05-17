"""基础设施层发件箱实体模块

定义事务发件箱实体（OutboxEntity），包含状态机管理：
pending -> published/failed, failed -> pending(重试)/archived(终态)

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
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
    状态机: pending -> published/failed, failed -> pending(重试)/archived(终态)

    Attributes:
        id: 自增主键
        event_id: 事件唯一标识
        event_type: 事件类型名称
        payload: 事件负载数据
        status: 当前状态（pending/published/failed/archived）
        created_at: 创建时间
        published_at: 发布时间
        retry_count: 已重试次数
        max_retries: 最大重试次数
        error_message: 错误信息
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
        """标记为已发布

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 时
        """
        if self.status != "pending":
            raise InvalidStateTransitionError(self.status, "published")
        self.status = "published"
        self.published_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """标记为失败，递增 retry_count

        Args:
            error: 错误信息

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 或 failed 时
        """
        if self.status not in ("pending", "failed"):
            raise InvalidStateTransitionError(self.status, "failed")
        self.status = "failed"
        self.retry_count += 1
        self.error_message = error

    def mark_pending(self) -> None:
        """重置为 pending（用于重试）

        Raises:
            InvalidStateTransitionError: 当当前状态不是 failed 或超过最大重试次数时
        """
        if self.status != "failed":
            raise InvalidStateTransitionError(self.status, "pending")
        if self.retry_count >= self.max_retries:
            raise InvalidStateTransitionError(self.status, "pending", f"Max retries ({self.max_retries}) exceeded")
        self.status = "pending"
        self.error_message = None

    def mark_archived(self) -> None:
        """归档（终态，不可逆）

        Raises:
            InvalidStateTransitionError: 当当前状态不是 failed 时
        """
        if self.status != "failed":
            raise InvalidStateTransitionError(self.status, "archived")
        self.status = "archived"
