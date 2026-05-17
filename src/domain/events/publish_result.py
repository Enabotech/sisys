"""SISYS 领域层 发布结果类型模块

领域层定义，用于返回发布操作的结果
使用DomainEvent作为基础，不感知传输细节

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishResult:
    """发布结果，包含各通道状态

    语义定义：
    - redis_success: Redis 通道是否成功（尽力而为，可能丢失）
    - outbox_saved: 消息是否已存入 Outbox（可靠路径，Poller 保证最终一致）

    注意：
    - 移除了 rabbitmq_success（因为 RabbitMQ 成功 = Outbox 保存成功，由 Poller 保证）
    - outbox_saved=True 表示可靠投递最终会成功
    """

    event_id: str
    redis_success: bool = False
    redis_error: str | None = None
    outbox_saved: bool = False
    outbox_error: str | None = None

    @property
    def is_success(self) -> bool:
        """任意通道成功即为成功。"""
        return self.redis_success or self.outbox_saved

    @property
    def is_full_failure(self) -> bool:
        """所有通道都失败。"""
        return not self.redis_success and not self.outbox_saved

    @property
    def partial_error(self) -> str | None:
        """返回第一个错误信息。"""
        if self.outbox_error:
            return self.outbox_error
        if self.redis_error:
            return self.redis_error
        return None
